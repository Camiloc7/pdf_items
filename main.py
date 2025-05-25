import os
import logging
import sys
from config.settings import settings
from database.models import init_db, SessionLocal, Factura
from database.crud import InvoiceCRUD, CorrectedFieldCRUD
from extraction.pdf_reader import PDFReader
from extraction.ocr_engine import OCREngine
from extraction.regex_parser import RegexParser
from extraction.nlp_parser import NLPParser
from extraction.table_extractor import TableExtractor
from extraction.combiner import ResultCombiner
from learning.feedback_handler import FeedbackHandler
from typing import Dict, Any, Optional
from datetime import datetime
import shutil

logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_invoice(pdf_path: str) -> Optional[Dict[str, Any]]:
    logger.info(f"Iniciando procesamiento de factura: {pdf_path}")

    pdf_reader = PDFReader()
    raw_text_pdf_direct = pdf_reader.extract_text(pdf_path)
    logger.debug(f"Texto directo de PDF extraído (primeros 20 chars):\n{raw_text_pdf_direct[:min(20, len(raw_text_pdf_direct))]}...")

    ocr_engine = OCREngine()
    raw_text_ocr = ocr_engine.pdf_to_text_ocr(pdf_path)
    logger.debug(f"Texto OCR extraído (primeros 20 chars):\n{raw_text_ocr[:min(20, len(raw_text_ocr))]}...")

    full_text_content = raw_text_pdf_direct if raw_text_pdf_direct else ""
    if raw_text_ocr and raw_text_ocr not in full_text_content:
        full_text_content += "\n" + raw_text_ocr

    if not full_text_content.strip():
        logger.error(f"No se pudo extraer texto del PDF {pdf_path} ni con lectura directa ni con OCR.")
        return None

    regex_parser = RegexParser()
    regex_data = regex_parser.extract_fields(full_text_content)
    logger.debug(f"Datos principales extraídos por Regex: {regex_data}")

    table_extractor = TableExtractor()
    extracted_line_items = table_extractor.extract_and_parse_line_items(pdf_path)
    logger.debug(f"Ítems de línea extraídos por TableExtractor: {extracted_line_items}")

    if not extracted_line_items:
        logger.info("TableExtractor no encontró ítems. Intentando con RegexParser como fallback.")
        extracted_line_items = regex_parser.extract_line_items(full_text_content)
        logger.debug(f"Ítems de línea extraídos por Regex (fallback): {extracted_line_items}")

    nlp_parser = NLPParser()
    nlp_data = nlp_parser.extract_entities(full_text_content)
    logger.debug(f"Datos extraídos por NLP: {nlp_data}")

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
    logger.info(f"Datos consolidados para guardar (antes del mapeo a español): {combined_data}")
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
    }

    invoice_main_data_es = {}
    for extracted_key, db_column_name in field_name_mapping.items():
        invoice_main_data_es[db_column_name] = invoice_data.get(extracted_key)

    items_data_es = []
    for item in invoice_data.get('items', []):
        items_data_es.append({
            "descripcion": item.get("description"),
            "cantidad": item.get("quantity"),
            "precio_unitario": item.get("unit_price"),
            "total_linea": item.get("line_total"),
        })

    existing_invoice = db_session.query(Factura).filter(Factura.ruta_archivo == invoice_data.get("file_path")).first()

    if existing_invoice:
        logger.info(f"Factura con ruta '{invoice_data.get('file_path')}' ya existe. Aplicando correcciones si las hay para factura ID: {existing_invoice.id}")

        corrections = corrected_field_crud.get_corrected_fields_for_invoice(existing_invoice.id)

        corrections_dict = {corr.nombre_campo: corr.valor_corregido for corr in corrections}

        for db_column_name, extracted_value in list(invoice_main_data_es.items()):
            if db_column_name in corrections_dict:
                corrected_value = corrections_dict[db_column_name]
                logger.debug(f"Aplicando corrección para '{db_column_name}': '{extracted_value}' -> '{corrected_value}'")

                if "monto" in db_column_name:
                    try:
                        invoice_main_data_es[db_column_name] = float(corrected_value.replace('.', '').replace(',', '.'))
                    except ValueError:
                        logger.warning(f"No se pudo convertir '{corrected_value}' a float para {db_column_name}. Se usará como string.")
                        invoice_main_data_es[db_column_name] = corrected_value
                elif "fecha" in db_column_name:
                    try:
                        if len(corrected_value) == 10 and corrected_value.count('-') == 2:
                            invoice_main_data_es[db_column_name] = datetime.strptime(corrected_value, "%Y-%m-%d").date()
                        elif len(corrected_value) >= 10 and corrected_value.count('/') == 2:
                            invoice_main_data_es[db_column_name] = datetime.strptime(corrected_value.split(',')[0].strip(), "%d/%m/%Y").date()
                        else:
                            logger.warning(f"Formato de fecha desconocido para '{corrected_value}' en campo '{db_column_name}'. Se usará como string.")
                            invoice_main_data_es[db_column_name] = corrected_value
                    except ValueError:
                        logger.warning(f"No se pudo convertir '{corrected_value}' a fecha para {db_column_name}. Se usará como string.")
                        invoice_main_data_es[db_column_name] = corrected_value
                else:
                    invoice_main_data_es[db_column_name] = corrected_value

        invoice_obj = invoice_crud.update_invoice(existing_invoice.id, invoice_main_data_es, items_data_es)
    else:
        invoice_obj = invoice_crud.create_invoice(invoice_main_data_es, items_data_es)

    db_session.close()

    if invoice_obj:
        logger.info(f"Factura '{invoice_obj.numero_factura}' guardada/actualizada en DB con ID: {invoice_obj.id}")
        return invoice_obj.id
    return None

def apply_correction(invoice_id: int, field_name: str, original_value: str, corrected_value: str):
    db_session = SessionLocal()
    invoice_crud = InvoiceCRUD(db_session)
    feedback_handler = FeedbackHandler()

    correction = feedback_handler.record_correction(invoice_id, field_name, original_value, corrected_value)

    if correction:
        logger.info(f"Corrección aplicada: Factura ID {invoice_id}, Campo '{field_name}', Original: '{original_value}', Corregido: '{corrected_value}'")

        update_data = {}
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
        }
        db_field_name = field_mapping.get(field_name)

        if db_field_name:
            value_to_set = corrected_value
            if "monto" in db_field_name:
                try:
                    value_to_set = float(corrected_value.replace('.', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"No se pudo convertir '{corrected_value}' a float para {db_field_name}. Se guardará como string.")
            elif "fecha" in db_field_name:
                try:
                    if len(corrected_value) == 10 and corrected_value.count('-') == 2:
                        value_to_set = datetime.strptime(corrected_value, "%Y-%m-%d").date()
                    elif len(corrected_value) >= 10 and corrected_value.count('/') == 2:
                        value_to_set = datetime.strptime(corrected_value.split(',')[0].strip(), "%d/%m/%Y").date()
                    else:
                        logger.warning(f"Formato de fecha desconocido para '{corrected_value}' en campo '{db_field_name}'. Se guarda como string.")
                except ValueError:
                    logger.warning(f"No se pudo convertir '{corrected_value}' a fecha para {db_field_name}. Se guardará como string.")

            update_data[db_field_name] = value_to_set

            updated_invoice = invoice_crud.update_invoice(invoice_id, update_data)

            if updated_invoice:
                logger.info(f"Factura ID {invoice_id} actualizada directamente en DB para el campo '{field_name}'.")
            else:
                logger.error(f"Fallo al actualizar la factura ID {invoice_id} en la DB.")
        else:
            logger.warning(f"Campo '{field_name}' no mapeado para actualización directa en la factura principal.")

        feedback_handler.learn_from_corrections()
        feedback_handler.close_db_session()
        db_session.close()
        logger.info("Sistema de aprendizaje ejecutado y patrones actualizados después de registrar corrección.")
    else:
        logger.error(f"Fallo al registrar la corrección para factura ID {invoice_id}, campo '{field_name}'.")
        db_session.close()

def main():
    logger.info("Iniciando el sistema de procesamiento de facturas.")
    init_db()
    if not os.path.exists(settings.PDF_INPUT_DIR):
        os.makedirs(settings.PDF_INPUT_DIR)
        logger.warning(f"Directorio de entrada de PDFs creado: {settings.PDF_INPUT_DIR}")
        logger.info("Por favor, coloque archivos PDF de facturas en este directorio.")
        return

    if not os.path.exists(settings.PDF_PROCESSED_DIR):
        os.makedirs(settings.PDF_PROCESSED_DIR)
        logger.info(f"Directorio de PDFs procesados creado: {settings.PDF_PROCESSED_DIR}")

    try:
        feedback_handler = FeedbackHandler()
        feedback_handler.learn_from_corrections()
        feedback_handler.close_db_session()
        logger.info("Patrones de aprendizaje cargados y actualizados al inicio del procesamiento.")
    except Exception as e:
        logger.error(f"Error al cargar/actualizar patrones de aprendizaje al inicio: {e}")

    processed_count = 0
    for filename in os.listdir(settings.PDF_INPUT_DIR):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(settings.PDF_INPUT_DIR, filename)
            logger.info(f"Procesando archivo: {pdf_path}")

            extracted_data = process_invoice(pdf_path)

            if extracted_data:
                invoice_id = save_invoice_to_db(extracted_data)
                if invoice_id:
                    processed_count += 1
                    try:
                        destination_path = os.path.join(settings.PDF_PROCESSED_DIR, filename)
                        shutil.move(pdf_path, destination_path)
                        logger.info(f"Archivo '{filename}' movido a '{settings.PDF_PROCESSED_DIR}' después de ser procesado.")
                    except Exception as e:
                        logger.error(f"Error al mover el archivo '{filename}': {e}")
                else:
                    logger.error(f"Fallo al guardar/actualizar la factura para el PDF: {pdf_path}")
            else:
                logger.error(f"Fallo al procesar el PDF: {pdf_path}")

    logger.info(f"Procesamiento de facturas finalizado. Total procesadas: {processed_count}")
    logger.info("Para probar las pruebas unitarias, ejecute 'pytest' en el directorio raíz.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'apply_correction':
        if len(sys.argv) == 6:
            invoice_id = int(sys.argv[2])
            field_name = sys.argv[3]
            original_value = sys.argv[4]
            corrected_value = sys.argv[5]
            init_db()
            apply_correction(invoice_id, field_name, original_value, corrected_value)
            print("Corrección aplicada. Ver logs para detalles.")
            sys.exit(0)
        else:
            print("Uso incorrecto. Para aplicar corrección: python main.py apply_correction <invoice_id> <field_name> <original_value> <corrected_value>")
            sys.exit(1)
    else:
        main()