import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
from typing import Dict, Any, List, Optional
from .models import Factura, ItemFactura, CampoCorregido
from datetime import datetime # Importar datetime

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
                    invoice_data["fecha_emision"] = datetime.strptime(invoice_data["fecha_emision"], "%d/%m/%Y")
                except ValueError:
                    logger.warning(f"No se pudo parsear fecha_emision '{invoice_data['fecha_emision']}'. Se deja como string o None.")
                    invoice_data["fecha_emision"] = None 
            if isinstance(invoice_data.get("fecha_vencimiento"), str):
                try:
                    invoice_data["fecha_vencimiento"] = datetime.strptime(invoice_data["fecha_vencimiento"], "%d/%m/%Y")
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
                                setattr(factura, key, datetime.strptime(value, "%Y-%m-%d"))
                            elif len(value) >= 10 and value.count('/') == 2: 
                                setattr(factura, key, datetime.strptime(value.split(',')[0].strip(), "%d/%m/%Y"))
                            else:
                                logger.warning(f"Formato de fecha desconocido para '{value}' en campo '{key}'. No se actualiza la fecha.")
                        except ValueError:
                            logger.warning(f"Error al parsear fecha '{value}' para el campo '{key}'. Se mantiene el valor existente o se ignora.")
                    else:
                        setattr(factura, key, value)
                else:
                    logger.warning(f"Intento de actualizar campo '{key}' que no existe en el modelo Factura.")
            if new_items_data is not None: #
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
            self.db.query(ItemFactura).filter(ItemFactura.id_factura == id_factura).delete()
            factura = self.get_invoice_by_id(id_factura)
            if not factura:
                logger.warning(f"Factura con ID {id_factura} no encontrada para eliminar.")
                return False
            self.db.delete(factura)
            self.db.commit()
            logger.info(f"Factura con ID {id_factura} eliminada exitosamente.")
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
            new_correction = CampoCorregido(
                id_factura=id_factura,
                nombre_campo=nombre_campo,
                valor_original=valor_original,
                valor_corregido=valor_corregido
            )
            self.db.add(new_correction)
            self.db.commit()
            self.db.refresh(new_correction)
            logger.info(f"Corrección para la factura {id_factura}, campo '{nombre_campo}' registrada.")
            return new_correction
        except OperationalError as e:
            self.db.rollback()
            logger.error(f"Error operacional de base de datos al añadir campo corregido: {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error inesperado al añadir campo corregido: {e}", exc_info=True)
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