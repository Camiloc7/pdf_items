import spacy
import logging
import json 
import os   
from typing import Dict, Any, List, Optional
from config.settings import settings
from datetime import datetime 
from spacy.pipeline import EntityRuler 
from spacy.matcher import PhraseMatcher
import re 

logger = logging.getLogger(__name__)

class NLPParser:
    def __init__(self):
        try:
            self.nlp = spacy.load(settings.SPACY_MODEL)
            self.matcher = PhraseMatcher(self.nlp.vocab) 
            self._add_default_patterns()
            self._load_learned_nlp_terms()
            logger.info(f"Modelo spaCy '{settings.SPACY_MODEL}' cargado exitosamente.")
        except OSError:
            logger.error(f"El modelo spaCy '{settings.SPACY_MODEL}' no está instalado. "
                         "Por favor, ejecute: python -m spacy download es_core_news_sm")
            raise
        
    def _add_default_patterns(self):
        supplier_terms = ["proveedor", "razón social", "nombre del emisor", "company name", "sold by"]
        customer_terms = ["cliente", "razón social cliente", "nombre del receptor", "billed to", "ship to"]
        
        self.matcher.add("SUPPLIER_NAME_KEYWORDS", [self.nlp(term) for term in supplier_terms])
        self.matcher.add("CUSTOMER_NAME_KEYWORDS", [self.nlp(term) for term in customer_terms])
        logger.info("Patrones por defecto añadidos al PhraseMatcher de NLPParser.")

    def _load_learned_nlp_terms(self):
        if os.path.exists(settings.LEARNED_PATTERNS_FILE):
            with open(settings.LEARNED_PATTERNS_FILE, 'r', encoding='utf-8') as f:
                try:
                    patterns_data = json.load(f)
                    learned_terms = patterns_data.get("nlp_terms", [])
                    
                    if learned_terms:
                        if "entity_ruler" not in self.nlp.pipe_names:
                            ruler = self.nlp.add_pipe("entity_ruler", before="ner")
                        else:
                            ruler = self.nlp.get_pipe("entity_ruler")
                        
                        existing_patterns_text = {p['pattern'] for p in ruler.patterns}
                        new_patterns = []
                        for term in learned_terms:
                            if term not in existing_patterns_text:
                                new_patterns.append({"label": "LEARNED_TERM", "pattern": term})
                        
                        if new_patterns:
                            ruler.add_patterns(new_patterns)
                            logger.info(f"NLPParser: Añadidos {len(new_patterns)} términos aprendidos al EntityRuler.")
                except json.JSONDecodeError as e:
                    logger.error(f"Error al decodificar JSON de patrones aprendidos para NLPParser: {e}. No se añadirán términos aprendidos.")
        else:
            logger.info("No se encontró el archivo de patrones aprendidos para NLPParser. No se añadirán términos aprendidos.")

    def _parse_amount(self, value: str) -> Optional[float]:
        value = value.strip()
        if not value:
            return None
        value = value.replace('€', '').replace('$', '').replace('EUR', '').replace('USD', '').replace('MXN', '').replace('COP', '').strip()
        
        if ',' in value and '.' in value:
            if value.rfind(',') > value.rfind('.'):
                value = value.replace('.', '').replace(',', '.')
            else:
                value = value.replace(',', '')
        elif ',' in value:
            value = value.replace(',', '.')
        
        try:
            return float(value)
        except ValueError:
            logger.warning(f"NLP: No se pudo convertir el monto '{value}' a float.")
            return None

    def _parse_date(self, value: str) -> Optional[datetime]:
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d",
            "%d de %B de %Y",
            "%d %B %Y",
            "%d de %b de %Y",
            "%d %b %Y",
        ]
        month_map = {
            "enero": "January", "febrero": "February", "marzo": "March",
            "abril": "April", "mayo": "May", "junio": "June",
            "julio": "July", "agosto": "August", "septiembre": "September",
            "octubre": "October", "noviembre": "November", "diciembre": "December"
        }
        temp_value = value.lower()
        for es_month, en_month in month_map.items():
            temp_value = temp_value.replace(es_month, en_month)

        for fmt in formats:
            try:
                parsed_date = datetime.strptime(temp_value, fmt)
                if parsed_date.year < 100:
                    current_year = datetime.now().year
                    century = (current_year // 100) * 100
                    if parsed_date.year + century > current_year + 5:
                        parsed_date = parsed_date.replace(year=parsed_date.year + century - 100)
                    else:
                        parsed_date = parsed_date.replace(year=parsed_date.year + century)
                return parsed_date
            except ValueError:
                continue
        logger.warning(f"NLP: No se pudo parsear la fecha '{value}' con los formatos conocidos.")
        return None
    
    def extract_entities(self, text: str, invoice_id: Optional[int] = None) -> Dict[str, Any]:
        doc = self.nlp(text)
        extracted_data: Dict[str, Any] = {}
        
        for ent in doc.ents:
            if ent.label_ == "ORG" and "supplier_name" not in extracted_data:
                extracted_data["supplier_name"] = ent.text
                logger.debug(f"NLP (NER): Extraído 'supplier_name': '{ent.text}'")
            elif ent.label_ == "DATE" and "issue_date" not in extracted_data:
                 extracted_data["issue_date"] = ent.text
                 logger.debug(f"NLP (NER): Extraído 'issue_date': '{ent.text}'")
            elif ent.label_ == "MONEY" and "total_amount" not in extracted_data:
                 try:
                     parsed_amount = self._parse_amount(ent.text)
                     if parsed_amount is not None:
                         extracted_data["total_amount"] = parsed_amount
                         logger.debug(f"NLP (NER): Extraído 'total_amount': '{ent.text}' -> {parsed_amount}")
                 except Exception:
                     pass
            elif ent.label_ == "LEARNED_TERM":
                if len(ent.text.split()) > 1:
                    if "supplier_name" not in extracted_data:
                        extracted_data["supplier_name"] = ent.text
                        logger.debug(f"NLP (Learned Term): Extraído 'supplier_name': '{ent.text}'")
                    elif "customer_name" not in extracted_data and extracted_data.get("supplier_name") != ent.text:
                        extracted_data["customer_name"] = ent.text
                        logger.debug(f"NLP (Learned Term): Extraído 'customer_name': '{ent.text}'")
                elif re.match(r"^\d{5,20}-?\d+$", ent.text) and "supplier_tax_id" not in extracted_data:
                    extracted_data["supplier_tax_id"] = ent.text
                    logger.debug(f"NLP (Learned Term): Extraído 'supplier_tax_id': '{ent.text}'")

        matches = self.matcher(doc)
        for match_id, start, end in matches:
            span = doc[start:end]
            label = self.nlp.vocab.strings[match_id] 
            if "SUPPLIER_NAME_KEYWORDS" in label:
                if (end + 3) < len(doc):
                    potential_name = doc[end:end+3].text.strip()
                    if potential_name and "supplier_name" not in extracted_data:
                        extracted_data["supplier_name"] = potential_name
                        logger.debug(f"NLP (Matcher): Extraído 'supplier_name' cerca de '{span.text}': '{potential_name}'")
            elif "CUSTOMER_NAME_KEYWORDS" in label:
                if (end + 3) < len(doc):
                    potential_name = doc[end:end+3].text.strip()
                    if potential_name and "customer_name" not in extracted_data:
                        extracted_data["customer_name"] = potential_name
                        logger.debug(f"NLP (Matcher): Extraído 'customer_name' cerca de '{span.text}': '{potential_name}'")
        
        return extracted_data