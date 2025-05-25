import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from typing import Dict, Any, List, Optional
from .models import Factura, ItemFactura, CampoCorregido, ItemCorregido
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class InvoiceCRUD:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_invoice(self, invoice_data: Dict[str, Any], items_data: List[Dict[str, Any]] = None) -> Optional[Factura]:
        try:
            existing_invoice = self.db.query(Factura).filter(
                Factura.ruta_archivo == invoice_data.get("ruta_archivo")
            ).first()
            if existing_invoice:
                logger.info(f"Factura con ruta '{invoice_data.get('ruta_archivo')}' ya existe. Actualizando factura ID: {existing_invoice.id}")
                return self.update_invoice(existing_invoice.id, invoice_data, items_data)

            if isinstance(invoice_data.get("fecha_emision"), str):
                try:
                    if len(invoice_data["fecha_emision"]) == 10 and invoice_data["fecha_emision"].count('-') == 2:
                        invoice_data["fecha_emision"] = datetime.strptime(invoice_data["fecha_emision"], "%Y-%m-%d").date()
                    elif len(invoice_data["fecha_emision"]) >= 10 and invoice_data["fecha_emision"].count('/') == 2:
                        invoice_data["fecha_emision"] = datetime.strptime(invoice_data["fecha_emision"].split(',')[0].strip(), "%d/%m/%Y").date()
                    else:
                        logger.warning(f"Formato de fecha de emisión desconocido para '{invoice_data['fecha_emision']}'. Se deja como string o None.")
                        invoice_data["fecha_emision"] = None
                except ValueError:
                    logger.warning(f"No se pudo parsear fecha_emision '{invoice_data['fecha_emision']}'. Se deja como string o None.")
                    invoice_data["fecha_emision"] = None

            if isinstance(invoice_data.get("fecha_vencimiento"), str):
                try:
                    if len(invoice_data["fecha_vencimiento"]) == 10 and invoice_data["fecha_vencimiento"].count('-') == 2:
                        invoice_data["fecha_vencimiento"] = datetime.strptime(invoice_data["fecha_vencimiento"], "%Y-%m-%d").date()
                    elif len(invoice_data["fecha_vencimiento"]) >= 10 and invoice_data["fecha_vencimiento"].count('/') == 2:
                        invoice_data["fecha_vencimiento"] = datetime.strptime(invoice_data["fecha_vencimiento"].split(',')[0].strip(), "%d/%m/%Y").date()
                    else:
                        logger.warning(f"Formato de fecha de vencimiento desconocido para '{invoice_data['fecha_vencimiento']}'. Se deja como string o None.")
                        invoice_data["fecha_vencimiento"] = None
                except ValueError:
                    logger.warning(f"No se pudo parsear fecha_vencimiento '{invoice_data['fecha_vencimiento']}'. Se deja como string o None.")
                    invoice_data["fecha_vencimiento"] = None

            new_invoice = Factura(**invoice_data)
            self.db.add(new_invoice)
            self.db.flush()

            if items_data:
                for item_data in items_data:
                    item = ItemFactura(id_factura=new_invoice.id, **item_data)
                    self.db.add(item)

            self.db.commit()
            self.db.refresh(new_invoice)
            logger.info(f"Factura '{new_invoice.numero_factura}' creada exitosamente.")
            return new_invoice
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Error de integridad al crear factura: {e}")
            logger.error(f"Posiblemente el número de factura '{invoice_data.get('numero_factura')}' ya existe.")
            return None
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al crear factura: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al crear factura: {e}", exc_info=True)
            return None

    def get_invoice_by_number(self, numero_factura: str) -> Optional[Factura]:
        try:
            return self.db.query(Factura).filter(Factura.numero_factura == numero_factura).first()
        except OperationalError as e:
            logger.error(f"Error operacional de base de datos al obtener factura por número: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al obtener factura por número: {e}", exc_info=True)
            return None

    def get_invoice_by_id(self, id_factura: int) -> Optional[Factura]:
        try:
            return self.db.query(Factura).filter(Factura.id == id_factura).first()
        except OperationalError as e:
            logger.error(f"Error operacional de base de datos al obtener factura por ID: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al obtener factura por ID: {e}", exc_info=True)
            return None

    def update_invoice(self, id_factura: int, update_data: Dict[str, Any], new_items_data: List[Dict[str, Any]] = None) -> Optional[Factura]:
        try:
            factura = self.get_invoice_by_id(id_factura)
            if not factura:
                logger.warning(f"Factura con ID {id_factura} no encontrada para actualizar.")
                return None

            for key, value in update_data.items():
                if hasattr(factura, key):
                    if key in ["fecha_emision", "fecha_vencimiento"] and isinstance(value, str):
                        try:
                            if len(value) == 10 and value.count('-') == 2:
                                setattr(factura, key, datetime.strptime(value, "%Y-%m-%d").date())
                            elif len(value) >= 10 and value.count('/') == 2:
                                setattr(factura, key, datetime.strptime(value.split(',')[0].strip(), "%d/%m/%Y").date())
                            else:
                                logger.warning(f"Formato de fecha desconocido para '{value}' en campo '{key}'. No se actualiza la fecha.")
                        except ValueError:
                            logger.warning(f"Error al parsear fecha '{value}' para el campo '{key}'. Se mantiene el valor existente o se ignora.")
                    elif "monto" in key and isinstance(value, str):
                        try:
                            cleaned_amount = value.replace('.', '').replace(',', '.')
                            setattr(factura, key, float(cleaned_amount))
                        except ValueError:
                            logger.warning(f"No se pudo convertir '{value}' a float para {key}. Se guardará como string.")
                            setattr(factura, key, value)
                    else:
                        setattr(factura, key, value)
                else:
                    logger.warning(f"Intento de actualizar campo '{key}' que no existe en el modelo Factura.")

            if new_items_data is not None:
                self.db.query(ItemFactura).filter(ItemFactura.id_factura == id_factura).delete()
                self.db.flush()

                for item_data in new_items_data:
                    item = ItemFactura(id_factura=factura.id, **item_data)
                    self.db.add(item)

            self.db.commit()
            self.db.refresh(factura)
            logger.info(f"Factura con ID {id_factura} actualizada exitosamente.")
            return factura
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al actualizar factura: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al actualizar factura: {e}", exc_info=True)
            return None

    def delete_invoice(self, id_factura: int) -> bool:
        try:
            factura = self.get_invoice_by_id(id_factura)
            if not factura:
                logger.warning(f"Factura con ID {id_factura} no encontrada para eliminar.")
                return False

            self.db.delete(factura)
            self.db.commit()
            logger.info(f"Factura con ID {id_factura} eliminada exitosamente junto con sus ítems y correcciones (si el cascade está configurado).")
            return True
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al eliminar factura: {e}")
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al eliminar factura: {e}", exc_info=True)
            return False

class CorrectedFieldCRUD:
    def __init__(self, db_session: Session):
        self.db = db_session

    def add_corrected_field(self, id_factura: int, nombre_campo: str, valor_original: str, valor_corregido: str) -> Optional[CampoCorregido]:
        try:
            existing_correction = self.db.query(CampoCorregido).filter_by(
                id_factura=id_factura,
                nombre_campo=nombre_campo
            ).first()

            if existing_correction:
                existing_correction.valor_original = valor_original
                existing_correction.valor_corregido = valor_corregido
                existing_correction.fecha_correccion = datetime.now()
                self.db.add(existing_correction)
                logger.info(f"Corrección para la factura {id_factura}, campo '{nombre_campo}' actualizada.")
                return existing_correction
            else:
                new_correction = CampoCorregido(
                    id_factura=id_factura,
                    nombre_campo=nombre_campo,
                    valor_original=valor_original,
                    valor_corregido=valor_corregido
                )
                self.db.add(new_correction)
                logger.info(f"Nueva corrección para la factura {id_factura}, campo '{nombre_campo}' registrada.")
                return new_correction
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al añadir/actualizar campo corregido: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al añadir/actualizar campo corregido: {e}", exc_info=True)
            return None

    def get_corrected_fields_for_invoice(self, id_factura: int) -> List[CampoCorregido]:
        try:
            return self.db.query(CampoCorregido).filter(CampoCorregido.id_factura == id_factura).all()
        except Exception as e:
            logger.error(f"Error al obtener campos corregidos para la factura {id_factura}: {e}", exc_info=True)
            return []

    def get_all_corrected_fields(self) -> List[CampoCorregido]:
        try:
            return self.db.query(CampoCorregido).all()
        except Exception as e:
            logger.error(f"Error al obtener todos los campos corregidos: {e}", exc_info=True)
            return []

class ItemFacturaCRUD:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_item(self, invoice_id: int, item_data: Dict[str, Any]) -> Optional[ItemFactura]:
        try:
            for key in ["cantidad", "precio_unitario", "total_linea"]:
                if key in item_data and isinstance(item_data[key], str):
                    try:
                        item_data[key] = float(item_data[key].replace('.', '').replace(',', '.'))
                    except ValueError:
                        logger.warning(f"No se pudo convertir '{item_data[key]}' a float para el campo '{key}' del ítem. Se guardará como string.")
            
            new_item = ItemFactura(id_factura=invoice_id, **item_data)
            self.db.add(new_item)
            self.db.flush()
            self.db.commit()
            self.db.refresh(new_item)
            logger.info(f"Ítem creado exitosamente para la factura {invoice_id} con ID: {new_item.id}")
            return new_item
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Error de integridad al crear ítem de factura: {e}")
            return None
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al crear ítem de factura: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al crear ítem de factura: {e}", exc_info=True)
            return None

    def get_item_by_id(self, item_id: int) -> Optional[ItemFactura]:
        try:
            return self.db.query(ItemFactura).filter(ItemFactura.id == item_id).first()
        except OperationalError as e:
            logger.error(f"Error operacional de base de datos al obtener ítem por ID: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al obtener ítem por ID: {e}", exc_info=True)
            return None

    def get_items_for_invoice(self, invoice_id: int) -> List[ItemFactura]:
        try:
            return self.db.query(ItemFactura).filter(ItemFactura.id_factura == invoice_id).all()
        except Exception as e:
            logger.error(f"Error al obtener ítems para la factura {invoice_id}: {e}", exc_info=True)
            return []

    def update_item(self, item_id: int, update_data: Dict[str, Any]) -> Optional[ItemFactura]:
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                logger.warning(f"Ítem con ID {item_id} no encontrado para actualizar.")
                return None

            for key, value in update_data.items():
                if hasattr(item, key):
                    if key in ["cantidad", "precio_unitario", "total_linea"] and isinstance(value, str):
                        try:
                            value = float(value.replace('.', '').replace(',', '.'))
                        except ValueError:
                            logger.warning(f"No se pudo convertir '{value}' a float para el campo '{key}' del ítem. Se guardará como string.")
                    setattr(item, key, value)
                else:
                    logger.warning(f"Intento de actualizar campo '{key}' que no existe en el modelo ItemFactura.")
            
            self.db.commit()
            self.db.refresh(item)
            logger.info(f"Ítem con ID {item_id} actualizado exitosamente.")
            return item
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al actualizar ítem: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al actualizar ítem: {e}", exc_info=True)
            return None

    def delete_item(self, item_id: int) -> bool:
        try:
            item = self.get_item_by_id(item_id)
            if not item:
                logger.warning(f"Ítem con ID {item_id} no encontrado para eliminar.")
                return False
            
            self.db.delete(item)
            self.db.commit()
            logger.info(f"Ítem con ID {item_id} eliminado exitosamente.")
            return True
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al eliminar ítem: {e}")
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al eliminar ítem: {e}", exc_info=True)
            return False
class ItemCorrectionCRUD:
    def __init__(self, db_session: Session):
        self.db = db_session

    def add_item_correction(
        self,
        id_factura: int,
        tipo_correccion: str,
        campo_corregido: Optional[str] = None,
        valor_original: Optional[Any] = None,
        valor_corregido: Any = None,
        id_item_original: Optional[int] = None
    ) -> Optional[ItemCorregido]:
        try:
            original_json = json.dumps(valor_original, ensure_ascii=False) if isinstance(valor_original, dict) else valor_original
            corregido_json = json.dumps(valor_corregido, ensure_ascii=False) if isinstance(valor_corregido, dict) else valor_corregido

            new_correction = ItemCorregido(
                id_factura=id_factura,
                id_item_original=id_item_original,
                tipo_correccion=tipo_correccion,
                campo_corregido=campo_corregido,
                valor_original=original_json,
                valor_corregido=corregido_json
            )
            self.db.add(new_correction)
            self.db.commit()
            self.db.refresh(new_correction)
            logger.info(f"Corrección de ítem registrada: Factura ID {id_factura}, Tipo: '{tipo_correccion}', Campo: '{campo_corregido}'.")
            return new_correction
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al añadir corrección de ítem: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al añadir corrección de ítem: {e}", exc_info=True)
            return None

    def get_item_corrections_for_invoice(self, id_factura: int) -> List[ItemCorregido]:
        try:
            return self.db.query(ItemCorregido).filter(ItemCorregido.id_factura == id_factura).all()
        except Exception as e:
            logger.error(f"Error al obtener correcciones de ítems para la factura {id_factura}: {e}", exc_info=True)
            return []

    def get_item_correction_by_id(self, correction_id: int) -> Optional[ItemCorregido]:
        try:
            return self.db.query(ItemCorregido).filter(ItemCorregido.id == correction_id).first()
        except Exception as e:
            logger.error(f"Error al obtener corrección de ítem por ID {correction_id}: {e}", exc_info=True)
            return None

    def update_item_correction(self, correction_id: int, update_data: Dict[str, Any]) -> Optional[ItemCorregido]:
        try:
            correction = self.get_item_correction_by_id(correction_id)
            if not correction:
                logger.warning(f"Corrección de ítem con ID {correction_id} no encontrada para actualizar.")
                return None

            for key, value in update_data.items():
                if hasattr(correction, key):
                    if isinstance(value, dict):
                        setattr(correction, key, json.dumps(value, ensure_ascii=False))
                    else:
                        setattr(correction, key, value)
            correction.fecha_correccion = datetime.now()
            self.db.commit()
            self.db.refresh(correction)
            logger.info(f"Corrección de ítem con ID {correction_id} actualizada exitosamente.")
            return correction
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al actualizar corrección de ítem: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al actualizar corrección de ítem: {e}", exc_info=True)
            return None

    def delete_item_correction(self, correction_id: int) -> bool:
        try:
            correction = self.get_item_correction_by_id(correction_id)
            if not correction:
                logger.warning(f"Corrección de ítem con ID {correction_id} no encontrada para eliminar.")
                return False
            self.db.delete(correction)
            self.db.commit()
            logger.info(f"Corrección de ítem con ID {correction_id} eliminada exitosamente.")
            return True
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al eliminar corrección de ítem: {e}")
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al eliminar corrección de ítem: {e}", exc_info=True)
            return False

    def get_all_item_corrections(self) -> List[ItemCorregido]:
        try:
            return self.db.query(ItemCorregido).all()
        except Exception as e:
            logger.error(f"Error al obtener todas las correcciones de ítems: {e}", exc_info=True)
            return []