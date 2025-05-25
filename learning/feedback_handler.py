import logging
import json
import os
import re
from typing import Dict, Any, Optional, List
from database.crud import CorrectedFieldCRUD, ItemCorrectionCRUD 
from database.models import SessionLocal, CampoCorregido, ItemCorregido 
from datetime import datetime
from config.settings import settings
logger = logging.getLogger(__name__)
class FeedbackHandler:
    def __init__(self):
        self.db_session = SessionLocal()
        self.corrected_field_crud = CorrectedFieldCRUD(self.db_session)
        self.item_correction_crud = ItemCorrectionCRUD(self.db_session) 
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
                    return {"regex_patterns": {}, "nlp_terms": [], "item_patterns": {}}
        logger.info("No se encontró el archivo de patrones aprendidos. Se iniciará con patrones vacíos.")
        return {"regex_patterns": {}, "nlp_terms": [], "item_patterns": {}}
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
    def record_item_correction(
        self,
        invoice_id: int,
        tipo_correccion: str,
        campo_corregido: Optional[str] = None,
        valor_original: Optional[Any] = None,
        valor_corregido: Any = None,
        id_item_original: Optional[int] = None
    ) -> Optional[ItemCorregido]:
        try:
            correction = self.item_correction_crud.add_item_correction(
                id_factura=invoice_id,
                tipo_correccion=tipo_correccion,
                campo_corregido=campo_corregido,
                valor_original=valor_original,
                valor_corregido=valor_corregido,
                id_item_original=id_item_original
            )
            self.db_session.commit()
            return correction
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error al registrar corrección de ítem en DB: {e}")
            return None
    def learn_from_corrections(self) -> None:
        all_header_corrections = self.corrected_field_crud.get_all_corrected_fields()
        all_item_corrections = self.item_correction_crud.get_all_item_corrections()
        logger.info(f"Procesando {len(all_header_corrections)} correcciones de cabecera y {len(all_item_corrections)} correcciones de ítems para aprendizaje incremental.")
        new_regex_patterns = {}
        new_nlp_terms = []
        new_item_patterns = {}

        field_corrections: Dict[str, Dict[str, int]] = {}
        for correction in all_header_corrections:
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
        for item_correction in all_item_corrections:
            logger.debug(f"Procesando corrección de ítem (para aprendizaje futuro): {item_correction.tipo_correccion} - {item_correction.campo_corregido} - {item_correction.valor_corregido}")
            if item_correction.campo_corregido == 'descripcion' and item_correction.valor_corregido:
                corrected_desc = item_correction.valor_corregido
                if isinstance(corrected_desc, str) and corrected_desc.strip().startswith('{') and corrected_desc.strip().endswith('}'):
                    try:
                        item_dict = json.loads(corrected_desc)
                        if 'description' in item_dict:
                            corrected_desc = item_dict['description']
                    except json.JSONDecodeError:
                        pass 
                if corrected_desc not in new_nlp_terms:
                    new_nlp_terms.append(corrected_desc)
                    logger.info(f"NLP: Añadido término aprendido de ítem: '{corrected_desc}'")
        self.learned_patterns["regex_patterns"] = new_regex_patterns
        self.learned_patterns["nlp_terms"] = new_nlp_terms
        self.learned_patterns["item_patterns"] = new_item_patterns 
        self._save_learned_patterns()
        logger.info("Proceso de aprendizaje completado y patrones guardados.")
    def close_db_session(self):
        if self.db_session and self.db_session.is_active:
            self.db_session.close()
            logger.info("Sesión de base de datos cerrada en FeedbackHandler.")
    def __del__(self):
        self.close_db_session()
    def get_corrections_for_invoice(self, invoice_id: int) -> Dict[str, str]:
        corrections_list = self.corrected_field_crud.get_corrected_fields_for_invoice(invoice_id)
        corrections_dict = {c.nombre_campo: c.valor_corregido for c in corrections_list}
        return corrections_dict
    def apply_corrections_to_invoice_data(self, invoice_id: int, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug(f"Aplicando correcciones de cabecera para la factura ID: {invoice_id}")
        header_corrections = self.get_corrections_for_invoice(invoice_id)
        field_mapping = {
            "numero_factura": "invoice_number",
            "fecha_emision": "issue_date",
            "fecha_vencimiento": "due_date",
            "monto_subtotal": "subtotal_amount", 
            "monto_impuesto": "tax_amount",      
            "monto_total": "total_amount",
            "moneda": "currency",
            "nombre_proveedor": "supplier_name",
            "nit_proveedor": "supplier_tax_id",
            "nombre_cliente": "customer_name",
            "nit_cliente": "customer_tax_id",
            "cufe": "cufe",
            "metodo_pago": "payment_method",
            "raw_text": "raw_text",
            "ruta_archivo": "file_path",
        }
        for db_field_name, corrected_value in header_corrections.items():
            mapped_field_name = field_mapping.get(db_field_name)
            if mapped_field_name and mapped_field_name in extracted_data:
                logger.debug(f"Aplicando corrección de cabecera para '{mapped_field_name}': '{extracted_data.get(mapped_field_name)}' -> '{corrected_value}'")
                extracted_data[mapped_field_name] = corrected_value
            elif mapped_field_name:
                logger.warning(f"Campo de cabecera '{mapped_field_name}' (mapeado de '{db_field_name}') no encontrado en los datos extraídos para aplicar corrección.")
            else:
                logger.warning(f"No hay mapeo para el campo de corrección de cabecera '{db_field_name}' en el diccionario de datos extraídos.")
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

        for amount_field in ["subtotal_amount", "tax_amount", "total_amount"]:
            if amount_field in extracted_data and isinstance(extracted_data[amount_field], str):
                try:
                    cleaned_amount = extracted_data[amount_field].replace('.', '').replace(',', '.')
                    extracted_data[amount_field] = float(cleaned_amount)
                except ValueError:
                    logger.warning(f"No se pudo convertir el monto corregido '{extracted_data[amount_field]}' a número para {amount_field}.")

        extracted_data['items'] = self.apply_item_corrections_to_items_data(invoice_id, extracted_data.get('items', []))

        return extracted_data

    def apply_item_corrections_to_items_data(self, invoice_id: int, extracted_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.debug(f"Aplicando correcciones de ítems para la factura ID: {invoice_id}")
        item_corrections = self.item_correction_crud.get_item_corrections_for_invoice(invoice_id)

        current_items = {self._get_item_hash(item): item for item in extracted_items}
        
        for correction in item_corrections:
            try:
                if correction.tipo_correccion == 'eliminar':
                    item_to_remove = json.loads(correction.valor_original)
                    item_hash = self._get_item_hash(item_to_remove)
                    if item_hash in current_items:
                        del current_items[item_hash]
                        logger.debug(f"Ítem eliminado por corrección: {item_to_remove.get('description', 'N/A')}")
                elif correction.tipo_correccion == 'actualizar':

                    if correction.id_item_original: 
                        if correction.campo_corregido and correction.valor_corregido is not None:
                            try:
                                original_item_dict = json.loads(correction.valor_original) if isinstance(correction.valor_original, str) else correction.valor_original
                                corrected_item_dict = json.loads(correction.valor_corregido) if isinstance(correction.valor_corregido, str) else correction.valor_corregido

                                original_item_hash = self._get_item_hash(original_item_dict)
                                if original_item_hash in current_items:
                                    current_items[original_item_hash] = corrected_item_dict
                                    logger.debug(f"Ítem actualizado por corrección: {original_item_dict.get('description', 'N/A')} -> {corrected_item_dict.get('description', 'N/A')}")
                                else:
                                    logger.warning(f"Ítem original no encontrado para actualizar en apply_item_corrections_to_items_data: {original_item_dict.get('description', 'N/A')}")
                            except json.JSONDecodeError:
                                logger.warning(f"Error al deserializar JSON en corrección de ítem tipo 'actualizar'.")
                        else:
                            logger.warning(f"Corrección de ítem tipo 'actualizar' sin campo_corregido o valor_corregido.")

            except Exception as e:
                logger.error(f"Error al procesar corrección de ítem '{correction.id}': {e}", exc_info=True)
        for correction in item_corrections:
            try:
                if correction.tipo_correccion == 'añadir':
                    new_item_dict = json.loads(correction.valor_corregido)
                    item_hash = self._get_item_hash(new_item_dict)
                    if item_hash not in current_items:
                        current_items[item_hash] = new_item_dict
                        logger.debug(f"Ítem añadido por corrección: {new_item_dict.get('description', 'N/A')}")
            except json.JSONDecodeError:
                logger.warning(f"Error al deserializar JSON en corrección de ítem tipo 'añadir'.")
            except Exception as e:
                logger.error(f"Error al procesar corrección de ítem '{correction.id}': {e}", exc_info=True)

        final_items = list(current_items.values())
        for item in final_items:
            if 'quantity' in item and isinstance(item['quantity'], str):
                try:
                    item['quantity'] = float(item['quantity'].replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir cantidad '{item['quantity']}' a float para ítem: {item.get('description')}")
            if 'unit_price' in item and isinstance(item['unit_price'], str):
                try:
                    item['unit_price'] = float(item['unit_price'].replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir precio_unitario '{item['unit_price']}' a float para ítem: {item.get('description')}")
            if 'line_total' in item and isinstance(item['line_total'], str):
                try:
                    item['line_total'] = float(item['line_total'].replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir total_linea '{item['line_total']}' a float para ítem: {item.get('description')}")

        return final_items

    def _get_item_hash(self, item: Dict[str, Any]) -> str:
        desc = str(item.get('description', '')).strip().lower()
        qty = item.get('quantity')
        price = item.get('unit_price')
        return f"{desc}|{qty}|{price}"

    def get_item_corrections_for_invoice(self, invoice_id: int) -> List[ItemCorregido]:
        return self.item_correction_crud.get_item_corrections_for_invoice(invoice_id)

    def close_db_session(self):
        if self.db_session and self.db_session.is_active:
            self.db_session.close()
            logger.info("Sesión de base de datos cerrada en FeedbackHandler.")

    def __del__(self):
        self.close_db_session()