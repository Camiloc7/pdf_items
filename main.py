import os
import logging
import sys
import json
import time
import shutil
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from config.settings import settings
from database.models import init_db, SessionLocal, Factura, ItemFactura, Usuario
from database.crud import InvoiceCRUD, CorrectedFieldCRUD, ItemFacturaCRUD, ItemCorrectionCRUD
from extraction.pdf_reader import PDFReader
from extraction.ocr_engine import OCREngine
from extraction.regex_parser import RegexParser
from extraction.nlp_parser import NLPParser
from extraction.table_extractor import TableExtractor
from extraction.combiner import ResultCombiner
from learning.feedback_handler import FeedbackHandler
from ingestion.email_reader import obtener_correos_con_facturas
from ingestion.zip_handler import extraer_archivos_de_zip
from extraction.xml_parser import parse_invoice_xml, extract_nested_invoice_xml
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_document_logic(file_path: str, email_metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    extracted_data = None
    pdf_path_to_process = None
    temp_dir_for_zip_extraction = None

    if file_path.lower().endswith('.zip'):
        logger.info(f"Manejando archivo ZIP: {file_path}")
        extracted_content = extraer_archivos_de_zip(file_path)
        xml_files = extracted_content['xmls']
        pdf_files = extracted_content['pdfs']
        temp_dir_for_zip_extraction = extracted_content['temp_dir']

        # Intentar procesar los XMLs primero
        if xml_files:
            for xml_zip_path in xml_files:
                logger.info(f"  Intentando extraer XML de factura anidado de: {xml_zip_path}")
                nested_invoice_xml_string = extract_nested_invoice_xml(xml_zip_path)
                if nested_invoice_xml_string:
                    logger.info("  XML de factura anidado encontrado. Intentando parsear...")
                    extracted_data = parse_invoice_xml(nested_invoice_xml_string)
                    if extracted_data and extracted_data.get('numero_factura') and extracted_data.get('monto_total'):
                        logger.info("  Datos esenciales extraídos exitosamente del XML anidado.")
                        # Asociar el PDF si existe
                        if pdf_files:
                            pdf_path_to_process = pdf_files[0]
                        else:
                            extracted_data['file_path'] = xml_zip_path
                        break  # Salir del bucle si se procesó un XML exitosamente
                    else:
                        logger.warning("  XML parseado pero faltan datos esenciales o el parsing falló. Recurriendo a PDF.")
                        extracted_data = None  # Resetear para intentar con PDFs
                else:
                    logger.warning(f"  No se encontró XML de factura anidado válido en {xml_zip_path}.")

        # Si no se pudo procesar el XML, intentar procesar los PDFs
        if not extracted_data and pdf_files:
            logger.info("  Procesando PDFs extraídos del ZIP.")
            pdf_path_to_process = pdf_files[0]

    elif file_path.lower().endswith('.pdf'):
        pdf_path_to_process = file_path
        logger.info(f"Procesando archivo PDF directamente: {file_path}")

    # Procesar el PDF si se identificó uno para procesar
    if pdf_path_to_process:
        logger.info(f"Iniciando extracción por PDF para: {pdf_path_to_process}")
        pdf_reader = PDFReader()
        raw_text_pdf_direct = pdf_reader.extract_text(pdf_path_to_process)

        ocr_engine = OCREngine()
        raw_text_ocr = ocr_engine.pdf_to_text_ocr(pdf_path_to_process)

        full_text_content = raw_text_pdf_direct if raw_text_pdf_direct else ""
        if raw_text_ocr and raw_text_ocr not in full_text_content:
            full_text_content += "\n" + raw_text_ocr

        if not full_text_content.strip():
            logger.warning(f"No se pudo extraer texto significativo de {pdf_path_to_process}.")
            return None

        regex_parser = RegexParser()
        regex_data = regex_parser.extract_fields(full_text_content)

        table_extractor = TableExtractor()
        extracted_line_items = table_extractor.extract_and_parse_line_items(pdf_path_to_process)
        if not extracted_line_items:
            logger.info(f"No se encontraron ítems de tabla para {pdf_path_to_process}, intentando con RegexParser.")
            extracted_line_items = regex_parser.extract_line_items(full_text_content)

        nlp_parser = NLPParser()
        nlp_data = nlp_parser.extract_entities(full_text_content)

        combiner = ResultCombiner()
        extracted_data_from_pdf = combiner.combine_results(
            pdf_direct_data={},
            ocr_data={},
            regex_data=regex_data,
            nlp_data=nlp_data
        )
        extracted_data_from_pdf['items'] = extracted_line_items
        extracted_data_from_pdf['raw_text'] = full_text_content
        extracted_data_from_pdf['file_path'] = pdf_path_to_process

        # Si ya hay datos del XML, combinar priorizando los datos del XML
        if extracted_data:
            logger.info("Combinando datos del XML con los datos del PDF, priorizando los del XML.")
            extracted_data = {**extracted_data_from_pdf, **extracted_data}  # Los datos del XML sobrescriben los del PDF
        else:
            extracted_data = extracted_data_from_pdf

        logger.info(f"Extracción por PDF completada para {pdf_path_to_process}.")

    if extracted_data and email_metadata:
        extracted_data.update(email_metadata)

    # Limpiar el directorio temporal del ZIP después de procesar su contenido
    if temp_dir_for_zip_extraction and os.path.exists(temp_dir_for_zip_extraction):
        shutil.rmtree(temp_dir_for_zip_extraction)
        logger.info(f"Directorio temporal '{temp_dir_for_zip_extraction}' limpiado.")

    return extracted_data

def process_invoice(pdf_path: str) -> Optional[Dict[str, Any]]:
    logger.info(f"Iniciando extracción para PDF: {pdf_path}")
    pdf_reader = PDFReader()
    raw_text_pdf_direct = pdf_reader.extract_text(pdf_path)
    ocr_engine = OCREngine()
    raw_text_ocr = ocr_engine.pdf_to_text_ocr(pdf_path)
    full_text_content = raw_text_pdf_direct if raw_text_pdf_direct else ""
    if raw_text_ocr and raw_text_ocr not in full_text_content:
        full_text_content += "\n" + raw_text_ocr
    if not full_text_content.strip():
        logger.warning(f"No se pudo extraer texto significativo de {pdf_path}.")
        return None
    regex_parser = RegexParser()
    regex_data = regex_parser.extract_fields(full_text_content)
    table_extractor = TableExtractor()
    extracted_line_items = table_extractor.extract_and_parse_line_items(pdf_path)
    if not extracted_line_items:
        logger.info(f"No se encontraron ítems de tabla para {pdf_path}, intentando con RegexParser.")
        extracted_line_items = regex_parser.extract_line_items(full_text_content)
    nlp_parser = NLPParser()
    nlp_data = nlp_parser.extract_entities(full_text_content)
    combiner = ResultCombiner()
    combined_data = combiner.combine_results(
        pdf_direct_data={}, 
        ocr_data={},        
        regex_data=regex_data,
        nlp_data=nlp_data
    )
    combined_data['items'] = extracted_line_items
    combined_data['raw_text'] = full_text_content
    combined_data['file_path'] = pdf_path 
    logger.info(f"Extracción completada para {pdf_path}.")
    return combined_data

def save_invoice_to_db(invoice_data: Dict[str, Any]) -> Optional[int]:
    db_session = SessionLocal()
    invoice_crud = InvoiceCRUD(db_session)
    corrected_field_crud = CorrectedFieldCRUD(db_session)
    field_name_mapping = {
        "invoice_number": "numero_factura",
        "issue_date": "fecha_emision",
        "due_date": "fecha_vencimiento",
        "subtotal_amount": "monto_subtotal",
        "tax_amount": "monto_impuesto",
        "total_amount": "monto_total",
        "currency": "moneda",
        "supplier_name": "nombre_proveedor",
        "supplier_tax_id": "nit_proveedor",
        "customer_name": "nombre_cliente",
        "customer_tax_id": "nit_cliente",
        "cufe": "cufe",
        "payment_method": "metodo_pago",
        "raw_text": "texto_crudo",
        "file_path": "ruta_archivo", 
        "asunto_correo": "asunto_correo",
        "remitente_correo": "remitente_correo",
        "correo_cliente": "correo_cliente",
    }
    invoice_main_data_es = {}
    for extracted_key, db_column_name in field_name_mapping.items():
        value = invoice_data.get(extracted_key)
        if value == "No encontrado" or value == "" or value is None:
            invoice_main_data_es[db_column_name] = None
        else:
            invoice_main_data_es[db_column_name] = value

    items_data_es = []
    for item in invoice_data.get('items', []):
        items_data_es.append({
            "descripcion": item.get("description"),
            "cantidad": item.get("quantity"),
            "precio_unitario": item.get("unit_price"),
            "total_linea": item.get("line_total"),
        })
    usuario_id = None
    if invoice_main_data_es.get("correo_cliente"):
        try:
            user_obj = db_session.query(Usuario).filter(Usuario.correo == invoice_main_data_es["correo_cliente"]).first()
            if user_obj:
                usuario_id = user_obj.id
                logger.info(f"Factura asociada al usuario ID: {usuario_id} ({invoice_main_data_es['correo_cliente']})")
        except Exception as e:
            logger.error(f"Error al buscar usuario por correo '{invoice_main_data_es['correo_cliente']}': {e}")
    invoice_main_data_es['usuario_id'] = usuario_id 
    existing_invoice = db_session.query(Factura).filter(Factura.ruta_archivo == invoice_data.get("file_path")).first()
    if existing_invoice:
        logger.info(f"Actualizando factura existente para: {invoice_data.get('file_path')}")
        corrections = corrected_field_crud.get_corrected_fields_for_invoice(existing_invoice.id)
        corrections_dict = {corr.nombre_campo: corr.valor_corregido for corr in corrections}
        for db_column_name, extracted_value in list(invoice_main_data_es.items()):
            if db_column_name in corrections_dict:
                corrected_value = corrections_dict[db_column_name]
                if "monto" in db_column_name and corrected_value is not None:
                    try:
                        invoice_main_data_es[db_column_name] = float(str(corrected_value).replace('.', '').replace(',', '.'))
                    except ValueError:
                        logger.warning(f"No se pudo convertir corrección '{corrected_value}' a float para '{db_column_name}'. Se usa el valor extraído.")
                        invoice_main_data_es[db_column_name] = extracted_value 
                elif "fecha" in db_column_name and corrected_value is not None:
                    try:
                        if isinstance(corrected_value, str):
                            if len(corrected_value) == 10 and corrected_value.count('-') == 2:
                                invoice_main_data_es[db_column_name] = datetime.strptime(corrected_value, "%Y-%m-%d").date()
                            elif len(corrected_value) >= 10 and corrected_value.count('/') == 2:
                                invoice_main_data_es[db_column_name] = datetime.strptime(corrected_value.split(',')[0].strip(), "%d/%m/%Y").date()
                            else:
                                logger.warning(f"Formato de fecha corregida desconocido para '{corrected_value}'. Se usa el valor extraído.")
                                invoice_main_data_es[db_column_name] = extracted_value # Usar el valor extraído si la corrección es inválida
                        elif isinstance(corrected_value, date):
                            invoice_main_data_es[db_column_name] = corrected_value
                    except ValueError:
                        logger.warning(f"No se pudo parsear fecha corregida '{corrected_value}' para '{db_column_name}'. Se usa el valor extraído.")
                        invoice_main_data_es[db_column_name] = extracted_value
                else:
                    invoice_main_data_es[db_column_name] = corrected_value
        invoice_obj = invoice_crud.update_invoice(existing_invoice.id, invoice_main_data_es, items_data_es)
    else:
        logger.info(f"Creando nueva factura para: {invoice_data.get('file_path')}")
        invoice_obj = invoice_crud.create_invoice(invoice_main_data_es, items_data_es)
    db_session.close()
    if invoice_obj:
        logger.info(f"Factura guardada/actualizada exitosamente. ID: {invoice_obj.id}")
        return invoice_obj.id
    logger.error(f"Fallo al guardar/actualizar la factura para {invoice_data.get('file_path')}.")
    return None

def apply_header_correction(invoice_id: int, field_name: str, original_value: str, corrected_value: str):
    db_session = SessionLocal()
    crud_handler = CorrectedFieldCRUD(db_session)
    invoice_crud = InvoiceCRUD(db_session)
    feedback_handler = FeedbackHandler()
    correction = crud_handler.add_corrected_field(invoice_id, field_name, original_value, corrected_value)
    if correction:
        field_mapping = {
            "numero_factura": "numero_factura",
            "fecha_emision": "fecha_emision",
            "fecha_vencimiento": "fecha_vencimiento",
            "monto_subtotal": "monto_subtotal",
            "monto_impuesto": "monto_impuesto",
            "monto_total": "monto_total",
            "moneda": "moneda",
            "nombre_proveedor": "nombre_proveedor",
            "nit_proveedor": "nit_proveedor",
            "nombre_cliente": "nombre_cliente",
            "nit_cliente": "nit_cliente",
            "cufe": "cufe",
            "metodo_pago": "metodo_pago",
            "asunto_correo": "asunto_correo",
            "remitente_correo": "remitente_correo",
            "correo_cliente": "correo_cliente",
        }
        db_field_name = field_mapping.get(field_name)
        if db_field_name:
            update_data = {}
            value_to_set = corrected_value
            if "monto" in db_field_name:
                try:
                    value_to_set = float(str(corrected_value).replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir '{corrected_value}' a float para '{db_field_name}'.")
                    value_to_set = corrected_value
            elif "fecha" in db_field_name:
                try:
                    if isinstance(corrected_value, str):
                        if len(corrected_value) == 10 and corrected_value.count('-') == 2:
                            value_to_set = datetime.strptime(corrected_value, "%Y-%m-%d").date()
                        elif len(corrected_value) >= 10 and corrected_value.count('/') == 2:
                            value_to_set = datetime.strptime(corrected_value.split(',')[0].strip(), "%d/%m/%Y").date()
                        else:
                            logger.warning(f"Formato de fecha de corrección desconocido para '{corrected_value}'.")
                            value_to_set = corrected_value
                    elif isinstance(corrected_value, date):
                        value_to_set = corrected_value
                except ValueError:
                    logger.warning(f"No se pudo parsear fecha '{corrected_value}' para '{db_field_name}'.")
                    value_to_set = corrected_value
            update_data[db_field_name] = value_to_set
            invoice_crud.update_invoice(invoice_id, update_data)
        feedback_handler.record_correction(invoice_id, field_name, original_value, corrected_value)
        feedback_handler.learn_from_corrections()
        feedback_handler.close_db_session()
    db_session.close()

def apply_item_correction(invoice_id: int, item_id: int, field_name: str, original_value: Any, corrected_value: Any):
    db_session = SessionLocal()
    item_correction_crud = ItemCorrectionCRUD(db_session)
    item_crud = ItemFacturaCRUD(db_session)
    correction = item_correction_crud.add_item_correction(
        id_factura=invoice_id,
        id_item_original=item_id,
        tipo_correccion="item_field_correction",
        campo_corregido=field_name,
        valor_original=original_value,
        valor_corregido=corrected_value
    )
    if correction:
        update_data = {field_name: corrected_value}
        if field_name in ["cantidad", "precio_unitario", "total_linea"]:
            try:
                update_data[field_name] = float(str(corrected_value).replace('.', '').replace(',', '.'))
            except ValueError:
                logger.warning(f"No se pudo convertir '{corrected_value}' a float para el campo '{field_name}' del ítem.")
        item_crud.update_item(item_id, update_data)
        logger.info(f"Corrección de ítem aplicada para factura {invoice_id}, ítem {item_id}, campo '{field_name}'.")
    else:
        logger.error(f"Fallo al registrar corrección de ítem para factura {invoice_id}, ítem {item_id}.")
    db_session.close()

def add_item_to_invoice(invoice_id: int, item_data: Dict[str, Any]):
    db_session = SessionLocal()
    item_crud = ItemFacturaCRUD(db_session)
    item_correction_crud = ItemCorrectionCRUD(db_session)
    try:
        item_data_db = {
            "descripcion": item_data.get("description"),
            "cantidad": item_data.get("quantity"),
            "precio_unitario": item_data.get("unit_price"),
            "total_linea": item_data.get("line_total")
        }
        for key in ["cantidad", "precio_unitario", "total_linea"]:
            if key in item_data_db and isinstance(item_data_db[key], str):
                try:
                    item_data_db[key] = float(item_data_db[key].replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir '{item_data_db[key]}' a float para el campo '{key}' del nuevo ítem.")
        new_item = item_crud.create_item(invoice_id, item_data_db)
        if new_item:
            logger.info(f"Ítem agregado a la factura {invoice_id} con ID: {new_item.id}.")
            item_correction_crud.add_item_correction(
                id_factura=invoice_id,
                id_item_original=new_item.id, 
                tipo_correccion="add_item",
                campo_corregido=None, 
                valor_original=None, 
                valor_corregido=item_data_db
            )
        else:
            logger.error(f"Fallo al agregar ítem a la factura {invoice_id}.")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error al agregar ítem a la factura {invoice_id}: {e}", exc_info=True)
    finally:
        db_session.close()

def update_invoice_item(invoice_id: int, item_id: int, item_changes: Dict[str, Any]):
    db_session = SessionLocal()
    item_crud = ItemFacturaCRUD(db_session)
    item_correction_crud = ItemCorrectionCRUD(db_session)
    try:
        original_item = item_crud.get_item_by_id(item_id)
        if not original_item:
            logger.warning(f"Ítem con ID {item_id} no encontrado para actualizar en factura {invoice_id}.")
            return
        for key, value in item_changes.items():
            original_value = getattr(original_item, key, None)
            if str(original_value) != str(value): 
                item_correction_crud.add_item_correction(
                    id_factura=invoice_id,
                    id_item_original=item_id,
                    tipo_correccion="item_field_correction",
                    campo_corregido=key,
                    valor_original=original_value,
                    valor_corregido=value
                )
            if key in ["cantidad", "precio_unitario", "total_linea"] and isinstance(value, str):
                try:
                    item_changes[key] = float(value.replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir '{value}' a float para el campo '{key}' del ítem.")
        updated_item = item_crud.update_item(item_id, item_changes)
        if updated_item:
            logger.info(f"Ítem {item_id} de factura {invoice_id} actualizado.")
        else:
            logger.error(f"Error: Ítem {item_id} no encontrado o no se pudo actualizar en factura {invoice_id}.")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error al actualizar ítem {item_id} de factura {invoice_id}: {e}", exc_info=True)
    finally:
        db_session.close()

def delete_invoice_item(invoice_id: int, item_id: int):
    db_session = SessionLocal()
    item_crud = ItemFacturaCRUD(db_session)
    item_correction_crud = ItemCorrectionCRUD(db_session)
    try:
        original_item = item_crud.get_item_by_id(item_id)
        if not original_item:
            logger.warning(f"Ítem con ID {item_id} no encontrado para eliminar en factura {invoice_id}.")
            return
        deleted = item_crud.delete_item(item_id)
        if deleted:
            logger.info(f"Ítem {item_id} de factura {invoice_id} eliminado.")
            item_correction_crud.add_item_correction(
                id_factura=invoice_id,
                id_item_original=item_id,
                tipo_correccion="delete_item",
                campo_corregido=None,
                valor_original=original_item.as_dict(),
                valor_corregido=None
            )
        else:
            logger.error(f"Error: Ítem {item_id} no encontrado o no se pudo eliminar en factura {invoice_id}.")
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error al eliminar ítem {item_id} de factura {invoice_id}: {e}", exc_info=True)
    finally:
        db_session.close()

def run_invoice_processing_loop():
    init_db()
    os.makedirs(settings.PDF_INPUT_DIR, exist_ok=True)
    os.makedirs(settings.PDF_PROCESSED_DIR, exist_ok=True)
    os.makedirs(settings.PDF_ERROR_DIR, exist_ok=True)
    logger.info("Directorios de PDF verificados/creados.")
    try:
        feedback_handler = FeedbackHandler()
        feedback_handler.learn_from_corrections()
        feedback_handler.close_db_session()
        logger.info("Patrones de aprendizaje cargados/actualizados.")
    except Exception as e:
        logger.error(f"Error al cargar/actualizar patrones de aprendizaje al inicio: {e}", exc_info=True)

    while True:
        logger.info("-" * 50)
        logger.info("Iniciando ciclo de búsqueda y procesamiento de facturas...")
        logger.info("Revisando correos para nuevas facturas...")
        start_time = time.time()
        logger.info(f"Inicio del procesamiento de correos: {datetime.now()}")

        try:
            correos_encontrados = obtener_correos_con_facturas()
            if not correos_encontrados:
                logger.info("No se encontraron nuevas facturas en los correos en este ciclo.")
            else:
                for correo in correos_encontrados:
                    logger.info(f"Procesando correo de: {correo['from']} - Asunto: {correo['subject']}")
                    email_metadata_for_invoice = {
                        "asunto_correo": correo.get("subject"),
                        "remitente_correo": correo.get("from"),
                        "correo_cliente": correo.get("cliente_correo") # Asegúrate de que obtener_correos_con_facturas devuelva esto
                    }

                    # No necesitas ThreadPoolExecutor aquí directamente para los adjuntos,
                    # ya que process_document_logic maneja cada adjunto de forma individual.
                    # Si un ZIP tiene varios PDFs/XMLs, process_document_logic los gestiona.
                    for adjunto_path_temp in correo["adjuntos_temp_paths"]:
                        try:
                            # ¡Aquí llamas a la nueva función unificada!
                            extracted_data = process_document_logic(adjunto_path_temp, email_metadata_for_invoice)

                            if extracted_data:
                                invoice_id = save_invoice_to_db(extracted_data)
                                if invoice_id:
                                    logger.info(f"Archivo '{os.path.basename(extracted_data['file_path'])}' procesado y guardado exitosamente.")
                                    # Mover el archivo (original o el PDF extraído si aplica)
                                    # La limpieza del temp_dir del ZIP ya se hace en process_document_logic
                                    # Si el adjunto original es un PDF y no es un path temporal de un ZIP, lo movemos
                                    if not adjunto_path_temp.lower().endswith('.zip') and os.path.exists(adjunto_path_temp):
                                        destination_path_processed = os.path.join(settings.PDF_PROCESSED_DIR, os.path.basename(adjunto_path_temp))
                                        shutil.move(adjunto_path_temp, destination_path_processed)
                                else:
                                    logger.warning(f"No se pudo guardar la factura para '{adjunto_path_temp}'.")
                                    # Mover el adjunto original a errores si aún existe
                                    if os.path.exists(adjunto_path_temp):
                                        shutil.move(adjunto_path_temp, os.path.join(settings.PDF_ERROR_DIR, os.path.basename(adjunto_path_temp)))
                            else:
                                logger.warning(f"No se pudieron extraer datos de '{adjunto_path_temp}'. Movido a errores.")
                                if os.path.exists(adjunto_path_temp):
                                    shutil.move(adjunto_path_temp, os.path.join(settings.PDF_ERROR_DIR, os.path.basename(adjunto_path_temp)))

                        except Exception as e:
                            logger.error(f"Error general al procesar adjunto '{adjunto_path_temp}': {e}", exc_info=True)
                            if os.path.exists(adjunto_path_temp):
                                shutil.move(adjunto_path_temp, os.path.join(settings.PDF_ERROR_DIR, os.path.basename(adjunto_path_temp)))
                        finally:
                            # Asegurarse de eliminar el ZIP original después de que process_document_logic lo haya manejado
                            if adjunto_path_temp.lower().endswith('.zip') and os.path.exists(adjunto_path_temp):
                                os.remove(adjunto_path_temp)

        except Exception as e:
            logger.critical(f"Error crítico en la etapa de ingesta de correos: {e}", exc_info=True)
        logger.info(f"Tiempo total para procesar correos: {time.time() - start_time} segundos")
        time.sleep(settings.EMAIL_CHECK_INTERVAL_SECONDS)

        # --- Bloque de procesamiento de PDF_INPUT_DIR ---
        processed_count = 0
        inbox_files = os.listdir(settings.PDF_INPUT_DIR)
        if not inbox_files:
            logger.info(f"No hay nuevos PDFs en {settings.PDF_INPUT_DIR} para procesar en este ciclo.")
        for filename in inbox_files:
            file_full_path = os.path.join(settings.PDF_INPUT_DIR, filename)
            # Asegúrate de que solo procesa archivos, no directorios si hubiese
            if os.path.isfile(file_full_path) and (filename.lower().endswith(".pdf") or filename.lower().endswith(".zip")):
                logger.info(f"Iniciando procesamiento de archivo del inbox: {filename}")
                email_metadata_for_invoice = {} # No hay metadata de correo para archivos directos en inbox
                parts = filename.split('_')
                if len(parts) >= 3:
                    if len(parts) > 3 and '@' in parts[2]:
                        email_metadata_for_invoice["correo_cliente"] = parts[2]

                try:
                    # ¡Aquí también llamas a la nueva función unificada!
                    extracted_data = process_document_logic(file_full_path, email_metadata_for_invoice)

                    if extracted_data:
                        invoice_id = save_invoice_to_db(extracted_data)
                        if invoice_id:
                            processed_count += 1
                            # Mover el archivo original (PDF o ZIP)
                            destination_path_processed = os.path.join(settings.PDF_PROCESSED_DIR, filename)
                            shutil.move(file_full_path, destination_path_processed)
                            logger.info(f"Archivo '{filename}' procesado y movido a {destination_path_processed}")
                        else:
                            logger.warning(f"No se pudo guardar la factura para '{filename}'. Movido a errores.")
                            shutil.move(file_full_path, os.path.join(settings.PDF_ERROR_DIR, filename))
                    else:
                        logger.warning(f"No se pudieron extraer datos de '{filename}'. Movido a errores.")
                        shutil.move(file_full_path, os.path.join(settings.PDF_ERROR_DIR, filename))
                except Exception as e:
                    logger.error(f"Error fatal al procesar '{filename}': {e}", exc_info=True)
                    shutil.move(file_full_path, os.path.join(settings.PDF_ERROR_DIR, filename))
        if processed_count > 0:
            logger.info(f"Completado el procesamiento de {processed_count} nuevos archivos en este ciclo.")
        else:
            logger.info("No se procesaron nuevos archivos del inbox en este ciclo.")
        logger.info(f"Esperando {settings.PROCESSING_INTERVAL_SECONDS} segundos antes del siguiente ciclo de procesamiento...")
        time.sleep(settings.PROCESSING_INTERVAL_SECONDS)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        init_db()
        if command == 'apply_header_correction':
            if len(sys.argv) == 6:
                invoice_id = int(sys.argv[2])
                field_name = sys.argv[3]
                original_value = sys.argv[4]
                corrected_value = sys.argv[5]
                apply_header_correction(invoice_id, field_name, original_value, corrected_value)
                logger.info("Corrección de cabecera procesada.")
                sys.exit(0)
            else:
                logger.error("Uso incorrecto para apply_header_correction: python main.py apply_header_correction <invoice_id> <field_name> <original_value> <corrected_value>")
                sys.exit(1)
        elif command == 'apply_item_correction':
            if len(sys.argv) == 7:
                invoice_id = int(sys.argv[2])
                item_id = int(sys.argv[3])
                field_name = sys.argv[4]
                original_value = sys.argv[5]
                corrected_value = sys.argv[6]
                apply_item_correction(invoice_id, item_id, field_name, original_value, corrected_value)
                logger.info("Corrección de ítem procesada.")
                sys.exit(0)
            else:
                logger.error("Uso incorrecto para apply_item_correction: python main.py apply_item_correction <invoice_id> <item_id> <field_name> <original_value> <corrected_value>")
                sys.exit(1)
        elif command == 'add_item':
            if len(sys.argv) == 4:
                invoice_id = int(sys.argv[2])
                item_data_json = sys.argv[3]
                try:
                    item_data = json.loads(item_data_json)
                    add_item_to_invoice(invoice_id, item_data)
                    sys.exit(0)
                except json.JSONDecodeError:
                    logger.error("Error: item_data_json no es un JSON válido.")
                    sys.exit(1)
            else:
                logger.error("Uso incorrecto para add_item: python main.py add_item <invoice_id> <item_json>")
                sys.exit(1)
        elif command == 'update_item':
            if len(sys.argv) == 5:
                invoice_id = int(sys.argv[2])
                item_id = int(sys.argv[3])
                item_changes_json = sys.argv[4]
                try:
                    item_changes = json.loads(item_changes_json)
                    update_invoice_item(invoice_id, item_id, item_changes)
                    sys.exit(0)
                except json.JSONDecodeError:
                    logger.error("Error: item_changes_json no es un JSON válido.")
                    sys.exit(1)
            else:
                logger.error("Uso incorrecto para update_item: python main.py update_item <invoice_id> <item_id> <item_changes_json>")
                sys.exit(1)
        elif command == 'delete_item':
            if len(sys.argv) == 4:
                invoice_id = int(sys.argv[2])
                item_id = int(sys.argv[3])
                delete_invoice_item(invoice_id, item_id)
                sys.exit(0)
            else:
                logger.error("Uso incorrecto para delete_item: python main.py delete_item <invoice_id> <item_id>")
                sys.exit(1)
        else:
            logger.error(f"Comando desconocido: {command}")
            sys.exit(1)
    else:
        run_invoice_processing_loop()