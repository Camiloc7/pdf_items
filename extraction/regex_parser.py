import re
import logging
import json 
import os 
from typing import Dict, Any, Optional, List
from datetime import datetime
from difflib import SequenceMatcher
from config.settings import settings 
logger = logging.getLogger(__name__)
class RegexParser:
    def __init__(self):
        self.base_patterns: Dict[str, str] = {
            "invoice_number": r"(?:número\s*de\s*factura|factura\s*no\.|no\s*\.?|nº|factura|serie|comprobante|invoice\s*no\.|invoice\s*#|bill\s*no\.)\s*[:#]?\s*([A-Za-z0-9\-\/]+)",
            "issue_date": r"(?:fecha\s*de\s*emisión|fecha|date|fec\.)\s*[:]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s*(?:de|del)?\s*(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(?:de)?\s*\d{4})",
            "due_date": r"(?:fecha\s*de\s*vencimiento|vencimiento|fecha\s*límite)\s*[:]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s*(?:de|del)?\s*(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(?:de)?\s*\d{4})",
            "subtotal_amount": r"(?:subtotal|valor\s*neto)\s*[:]?\s*(?:€|\$|EUR|USD|MXN|COP)?\s*([\d\.,]+)",
            "tax_amount": r"(?:iva|impuesto|impuestos|tax)\s*[:]?\s*(?:€|\$|EUR|MXN|COP)?\s*([\d\.,]+)",
            "total_amount": r"(?:total|importe\s*total|valor\s*total|total\s*a\s*pagar)\s*[:]?\s*(?:€|\$|EUR|MXN|COP)?\s*([\d\.,]+)",
            "currency": r"(?:total|importe\s*total|valor\s*total|subtotal|iva|impuesto|impuestos|tax)\s*[:]?\s*(€|\$|EUR|USD|MXN|COP)\s*[\d\.,]+",
            "supplier_name": r"(?:Empresa|Nombre\s*Comercial|Razón\s*Social|Proveedor|Emisor)\s*[:\s]*([A-Z][\w\s\.\-&ñÑáéíóúÁÉÍÓÚ\s]{3,})",
            "supplier_tax_id": r"(?:NIT|N\.I\.T\.|Nit\s+del\s+Emisor|cif|nif|rfc|tax\s*id|vat\s*id)\s*[:#]?\s*([\d\.\-]{5,20})",
            "customer_name": r"(?:ADQUIRENTE|Nombre\s*Comercial\s*Cliente|Razón\s*Social\s*Cliente|Cliente|Receptor)\s*[:\s]*([A-Z][\w\s\.\-&ñÑáéíóúÁÉÍÓÚ\s]{3,})",
            "customer_tax_id": r"(?:NIT\s*del\s*Adquiriente|N\.I\.T\.\s*cliente|Nit\s*cliente|Número\s*Documento\s*Cliente|cif\s*cliente|nif\s*cliente|rfc\s*cliente|tax\s*id\s*cliente|vat\s*id\s*cliente)\s*[:#]?\s*([\d\.\-]{5,20})",
            "cufe": r"(?:CUFE|Codigo\s*Unico\s*de\s*Factura\s*Electronica|UUID|GUID)[:\s]*([0-9a-fA-F\-]{32,96})",
            "payment_method": r"(?:forma\s*de\s*pago|método\s*de\s*pago)\s*[:]?\s*([A-Za-z\s]+)",
            "email": r"([\w\.-]+@[\w\.-]+(?:\.\w+)+)"        
            }
        
        self.learned_patterns = self._load_learned_patterns_from_file()
        self.combined_patterns = {**self.base_patterns, **self.learned_patterns.get("regex_patterns", {})}

        self.item_line_pattern = re.compile(
            r"(.+?)\s+"  
            r"([\d\.,]+)\s+"  
            r"([\d\.,]+)\s*" 
            r"(?:(?:€|\$|EUR|USD|MXN|COP)\s*)?([\d\.,]+)?$" 
        )
        self.month_map = {
            "enero": "January", "febrero": "February", "marzo": "March",
            "abril": "April", "mayo": "May", "junio": "June",
            "julio": "July", "agosto": "August", "septiembre": "September",
            "octubre": "October", "noviembre": "November", "diciembre": "December"
        }

    def _load_learned_patterns_from_file(self) -> Dict[str, Any]:
        """Carga los patrones aprendidos desde el archivo JSON persistente."""
        if os.path.exists(settings.LEARNED_PATTERNS_FILE):
            with open(settings.LEARNED_PATTERNS_FILE, 'r', encoding='utf-8') as f:
                try:
                    patterns_data = json.load(f)
                    logger.info(f"RegexParser ha cargado patrones aprendidos desde {settings.LEARNED_PATTERNS_FILE}")
                    return patterns_data
                except json.JSONDecodeError as e:
                    logger.error(f"Error al decodificar JSON de patrones aprendidos para RegexParser: {e}. Se usará un diccionario vacío para patrones regex.")
                    return {"regex_patterns": {}}
        logger.info("No se encontró el archivo de patrones aprendidos para RegexParser. Se iniciará con patrones base.")
        return {"regex_patterns": {}}
    def _normalizar_nit(self, nit: str) -> str:
        if nit:
            return re.sub(r'[\.\-\s]', '', nit)
        return nit

    def _similares(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _parse_amount(self, value: str) -> Optional[float]:
        value = re.sub(r'^(?:€|\$|EUR|USD|MXN|COP)\s*', '', value.strip())

        if ',' in value and '.' in value:
            if value.rfind(',') > value.rfind('.'):
                value = value.replace('.', '').replace(',', '.')
            else:
                value = value.replace(',', '')
        elif ',' in value:
            value = value.replace(',', '.')
        elif value.count('.') > 1:
            parts = value.split('.')
            value = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) <= 2 else "".join(parts)
        try:
            return float(value)
        except ValueError:
            logger.warning(f"No se pudo convertir el monto '{value}' a float.")
            return None

    def _parse_date(self, value: str) -> Optional[datetime]:
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d",
            "%d de %B de %Y",
            "%d %B %Y",
            "%d de %b de %Y",
            "%d %b %Y",
        ]
        temp_value = value.lower()
        for es_month, en_month in self.month_map.items():
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
        logger.warning(f"No se pudo parsear la fecha '{value}' con los formatos conocidos.")
        return None

    def extract_fields(self, text: str, remitente_correo: Optional[str] = None, asunto_correo: Optional[str] = None, invoice_id: Optional[int] = None) -> Dict[str, Any]:
        extracted_data: Dict[str, Any] = {}
        for field, pattern in self.combined_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and field not in extracted_data:  # Solo extraer si el campo no está en los datos del XML
                extracted_data[field] = match.group(1).strip()
                if "amount" in field:
                    extracted_data[field] = self._parse_amount(extracted_data[field])
                elif "date" in field:
                    extracted_data[field] = self._parse_date(extracted_data[field])
                elif "tax_id" in field:
                    extracted_data[field] = self._normalizar_nit(extracted_data[field])
                elif field == "currency":
                    if '$' in extracted_data[field]:
                        extracted_data[field] = 'COP'
                    elif '€' in extracted_data[field]:
                        extracted_data[field] = 'EUR'
                    elif 'USD' in extracted_data[field].upper():
                        extracted_data[field] = 'USD'
                    elif 'MXN' in extracted_data[field].upper():
                        extracted_data[field] = 'MXN'
                    else:
                        extracted_data[field] = extracted_data[field].upper() 
                elif field == "cufe":
                    url_match = re.search(r'https?:\/\/(?:www\.)?dian\.gov\.co\/validador\/.*\?cufe=([0-9a-fA-F\-]{32,96})', extracted_data[field], re.IGNORECASE)
                    if url_match:
                        extracted_data[field] = url_match.group(1).strip()
                    else:
                        extracted_data[field] = extracted_data[field]
                elif field == "email": 
                    extracted_data[field] = extracted_data[field]
                else:
                    extracted_data[field] = extracted_data[field]
                logger.debug(f"Regex: Extraído '{field}': '{extracted_data.get(field)}' de '{extracted_data[field]}'")
            else:
                extracted_data[field] = None
                logger.debug(f"Regex: No se encontró '{field}'.")

        if not extracted_data.get("supplier_name") and remitente_correo:
            if '@' in remitente_correo:
                domain_part = remitente_correo.split('@')[1].split('.')[0]
                if domain_part and len(domain_part) > 2:
                    extracted_data["supplier_name"] = domain_part.replace('-', ' ').replace('_', ' ').title()
                    logger.debug(f"Info Email: Extraído 'supplier_name': '{extracted_data['supplier_name']}' del dominio del remitente.")
        
        if asunto_correo:
            partes_asunto = asunto_correo.strip().split(";")
            if len(partes_asunto) >= 4: 
                nit_asunto = self._normalizar_nit(partes_asunto[0].strip())
                empresa_asunto = partes_asunto[1].strip()
                factura_asunto = f"{partes_asunto[2].strip()}{partes_asunto[3].strip()}".replace(' ', '').upper()
                
                if nit_asunto and (not extracted_data.get("supplier_tax_id") or self._similares(extracted_data["supplier_tax_id"], nit_asunto) < 0.7):
                    extracted_data["supplier_tax_id"] = nit_asunto
                    logger.debug(f"Info Asunto: Extraído 'supplier_tax_id': '{nit_asunto}' del asunto del correo.")
                if empresa_asunto and (not extracted_data.get("supplier_name") or self._similares(extracted_data["supplier_name"], empresa_asunto) < 0.7):
                    extracted_data["supplier_name"] = empresa_asunto
                    logger.debug(f"Info Asunto: Extraído 'supplier_name': '{empresa_asunto}' del asunto del correo.")
                if factura_asunto and (not extracted_data.get("invoice_number") or self._similares(extracted_data["invoice_number"], factura_asunto) < 0.7):
                    extracted_data["invoice_number"] = factura_asunto
                    logger.debug(f"Info Asunto: Extraído 'invoice_number': '{factura_asunto}' del asunto del correo.")

        return extracted_data

    def extract_line_items(self, text: str) -> List[Dict[str, Any]]:
        line_items: List[Dict[str, Any]] = []
        lines = text.split('\n')
        item_section_started = False
        keywords_start = [
            "descripción", "cantidad", "valor unitario", "total", "item",
            "producto", "referencia", "detalle", "concept", "qty", "unit price",
            "line total", "amount", "unit", "valor", "preciounitario"
        ]
        keywords_end = ["subtotal", "iva", "impuesto", "total", "total a pagar", "gran total"]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not item_section_started:
                if any(keyword in line.lower() for keyword in keywords_start) and \
                   any(re.search(r'\b\d+\b', line) for _ in [0]):
                    item_section_started = True
                    logger.debug(f"Regex: Posible inicio de sección de ítems detectado: '{line}'")
                    continue 
            else:
                if any(keyword in line.lower() for keyword in keywords_end) and \
                   any(re.search(r'\b\d+\b', line) for _ in [0]):
                    logger.debug(f"Regex: Posible fin de sección de ítems detectado: '{line}'")
                    break 
                match = self.item_line_pattern.search(line)
                if match:
                    try:
                        description = match.group(1).strip() if len(match.groups()) >= 1 else ""
                        quantity_str = match.group(2).strip() if len(match.groups()) >= 2 else ""
                        unit_price_str = match.group(3).strip() if len(match.groups()) >= 3 else ""
                        line_total_str = match.group(4).strip() if len(match.groups()) >= 4 else ""
                        quantity = self._parse_amount(quantity_str)
                        unit_price = self._parse_amount(unit_price_str)
                        line_total = self._parse_amount(line_total_str)
                        if description and (quantity is not None or unit_price is not None):
                            item = {
                                "description": description,
                                "quantity": quantity,
                                "unit_price": unit_price,
                                "line_total": line_total
                            }
                            line_items.append(item)
                            logger.debug(f"Regex: Ítem de línea extraído: {item}")
                        else:
                            logger.debug(f"Regex: Línea coincidió pero fue filtrada (posiblemente ruido): '{line}'")

                    except Exception as e:
                        logger.warning(f"Regex: Error al parsear línea de ítem '{line}': {e}")
                else:
                    logger.debug(f"Regex: Línea en sección de ítems no coincidió con patrón: '{line}'")
        if not line_items and item_section_started:
             logger.warning("Regex: Se detectó inicio de sección de ítems, pero no se extrajeron ítems. Revisar patrón.")
        elif not line_items and not item_section_started:
            logger.info("Regex: No se detectó sección de ítems ni se extrajeron ítems.")
        return line_items
