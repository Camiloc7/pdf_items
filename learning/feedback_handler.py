import logging
import json
import os
import re
from typing import Dict, Any, Optional
from database.crud import CorrectedFieldCRUD
from database.models import SessionLocal, CampoCorregido
from datetime import datetime
from config.settings import settings

logger = logging.getLogger(__name__)

class FeedbackHandler:
    def __init__(self):
        self.db_session = SessionLocal()
        self.corrected_field_crud = CorrectedFieldCRUD(self.db_session)
        self.learned_patterns = self._load_learned_patterns()

    def _load_learned_patterns(self) -> Dict[str, Any]:
        if os.path.exists(settings.LEARNED_PATTERNS_FILE):
            with open(settings.LEARNED_PATTERNS_FILE, 'r', encoding='utf-8') as f:
                try:
                    patterns = json.load(f)
                    logger.info(f"Patrones de aprendizaje cargados desde {settings.LEARNED_PATTERNS_FILE}")
                    return patterns
                except json.JSONDecodeError as e:
                    logger.error(f"Error al decodificar JSON de patrones aprendidos: {e}. Se usará un diccionario vacío.")
                    return {"regex_patterns": {}, "nlp_terms": []}
        logger.info("No se encontró el archivo de patrones aprendidos. Se iniciará con patrones vacíos.")
        return {"regex_patterns": {}, "nlp_terms": []}

    def _save_learned_patterns(self):
        with open(settings.LEARNED_PATTERNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.learned_patterns, f, indent=4, ensure_ascii=False)
        logger.info(f"Patrones de aprendizaje guardados en {settings.LEARNED_PATTERNS_FILE}")

    def record_correction(self, invoice_id: int, field_name: str, original_value: str, corrected_value: str) -> Optional[CampoCorregido]:
        try:
            correction = self.corrected_field_crud.add_corrected_field(
                id_factura=invoice_id,
                nombre_campo=field_name,
                valor_original=original_value,
                valor_corregido=corrected_value
            )
            self.db_session.commit()
            return correction
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error al registrar corrección en DB: {e}")
            return None

    def learn_from_corrections(self) -> None:
        all_corrections = self.corrected_field_crud.get_all_corrected_fields()
        logger.info(f"Procesando {len(all_corrections)} correcciones para aprendizaje incremental.")

        new_regex_patterns = {}
        new_nlp_terms = []

        field_corrections: Dict[str, Dict[str, int]] = {}
        for correction in all_corrections:
            if correction.nombre_campo not in field_corrections:
                field_corrections[correction.nombre_campo] = {}
            field_corrections[correction.nombre_campo][correction.valor_corregido] = \
                field_corrections[correction.nombre_campo].get(correction.valor_corregido, 0) + 1

        for field_name_es, values_count in field_corrections.items():
            most_frequent_value = max(values_count, key=values_count.get)
            count = values_count[most_frequent_value]

            if count > 5:
                logger.info(f"Corrección frecuente para '{field_name_es}': '{most_frequent_value}' ({count} veces).")

                field_name_en = None
                if field_name_es == "numero_factura":
                    field_name_en = "invoice_number"
                elif field_name_es == "nombre_proveedor":
                    field_name_en = "supplier_name"
                elif field_name_es == "nit_proveedor":
                    field_name_en = "supplier_tax_id"
                elif field_name_es == "nombre_cliente":
                    field_name_en = "customer_name"
                elif field_name_es == "nit_cliente":
                    field_name_en = "customer_tax_id"
                elif field_name_es == "fecha_emision":
                    field_name_en = "issue_date"
                elif field_name_es == "fecha_vencimiento":
                    field_name_en = "due_date"
                elif field_name_es == "monto_total":
                    field_name_en = "total_amount"
                elif field_name_es == "moneda":
                    field_name_en = "currency"

                if field_name_en:
                    if field_name_en == "invoice_number":
                        new_regex_patterns[field_name_en] = f"(?i){re.escape(most_frequent_value)}"
                        logger.info(f"Regex aprendido para '{field_name_en}': '{new_regex_patterns[field_name_en]}'")
                    elif field_name_en in ["supplier_name", "customer_name", "supplier_tax_id", "customer_tax_id"]:
                        if most_frequent_value not in new_nlp_terms:
                            new_nlp_terms.append(most_frequent_value)
                        logger.info(f"NLP: Añadido término aprendido para '{field_name_en}': '{most_frequent_value}'")
                else:
                    logger.warning(f"No se encontró mapeo en inglés para el campo '{field_name_es}' para el aprendizaje.")

        self.learned_patterns["regex_patterns"] = new_regex_patterns
        self.learned_patterns["nlp_terms"] = new_nlp_terms
        self._save_learned_patterns()

        logger.info("Proceso de aprendizaje completado y patrones guardados.")

    def close_db_session(self):
        if self.db_session and self.db_session.is_active:
            self.db_session.close()
            logger.info("Sesión de base de datos cerrada en FeedbackHandler.")

    def __del__(self):
        self.close_db_session()

    def get_corrections_for_invoice(self, invoice_id: int) -> Dict[str, str]:
        corrections_list = self.corrected_field_crud.get_corrected_fields_by_invoice_id(invoice_id)
        corrections_dict = {c.nombre_campo: c.valor_corregido for c in corrections_list}
        return corrections_dict

    def apply_corrections_to_invoice_data(self, invoice_id: int, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug(f"Aplicando correcciones para la factura ID: {invoice_id}")
        corrections = self.get_corrections_for_invoice(invoice_id)

        field_mapping = {
            "numero_factura": "invoice_number",
            "fecha_emision": "issue_date",
            "fecha_vencimiento": "due_date",
            "monto_total": "total_amount",
            "moneda": "currency",
            "nombre_proveedor": "supplier_name",
            "nit_proveedor": "supplier_tax_id",
            "nombre_cliente": "customer_name",
            "nit_cliente": "customer_tax_id",
        }

        for db_field_name, corrected_value in corrections.items():
            mapped_field_name = field_mapping.get(db_field_name)
            if mapped_field_name and mapped_field_name in extracted_data:
                logger.debug(f"Aplicando corrección para '{mapped_field_name}': '{extracted_data.get(mapped_field_name)}' -> '{corrected_value}'")
                extracted_data[mapped_field_name] = corrected_value
            elif mapped_field_name:
                logger.warning(f"Campo '{mapped_field_name}' (mapeado de '{db_field_name}') no encontrado en los datos extraídos para aplicar corrección.")
            else:
                logger.warning(f"No hay mapeo para el campo de corrección '{db_field_name}' en el diccionario de datos extraídos.")

        if "issue_date" in extracted_data and isinstance(extracted_data["issue_date"], str):
            try:
                extracted_data["issue_date"] = datetime.strptime(extracted_data["issue_date"], "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"No se pudo convertir la fecha corregida '{extracted_data['issue_date']}' a formato de fecha.")

        if "due_date" in extracted_data and isinstance(extracted_data["due_date"], str):
            try:
                extracted_data["due_date"] = datetime.strptime(extracted_data["due_date"], "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"No se pudo convertir la fecha de vencimiento corregida '{extracted_data['due_date']}' a formato de fecha.")

        if "total_amount" in extracted_data and isinstance(extracted_data["total_amount"], str):
            try:
                cleaned_amount = extracted_data["total_amount"].replace('.', '').replace(',', '.')
                extracted_data["total_amount"] = float(cleaned_amount)
            except ValueError:
                logger.warning(f"No se pudo convertir el monto total corregido '{extracted_data['total_amount']}' a número.")

        return extracted_data