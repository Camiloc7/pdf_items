import pytesseract
from PIL import Image
import logging
from config.settings import settings
import os
import fitz
import io
logger = logging.getLogger(__name__)
class OCREngine:
    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
        self.lang = settings.TESSERACT_LANG
        os.environ['TESSDATA_PREFIX'] = settings.TESSDATA_PREFIX
        poppler_path = settings.POPPLER_PATH
        if poppler_path and os.path.exists(poppler_path):
            pytesseract.pytesseract.poppler_path = poppler_path
            logger.info(f"pytesseract.poppler_path configurado a: {poppler_path}")
        else:
            logger.warning(f"La ruta de Poppler '{poppler_path}' no está configurada o no existe. "
                           "El OCR de PDF se basará completamente en la librería de renderizado interna (PyMuPDF).")
    def image_to_text(self, image_path: str) -> str:
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang=self.lang)
            logger.info(f"OCR realizado en {image_path} exitosamente.")
            return text
        except FileNotFoundError:
            logger.error(f"Error: El archivo de imagen no se encontró en {image_path}")
            return ""
        except pytesseract.TesseractNotFoundError:
            logger.error(f"Error: Tesseract OCR no se encontró en la ruta especificada: {settings.TESSERACT_CMD}. "
                         "Asegúrate de que Tesseract esté instalado y la ruta sea correcta.")
            return ""
        except Exception as e:
            logger.error(f"Error al realizar OCR en {image_path}: {e}")
            return ""
    def pdf_to_text_ocr(self, pdf_path: str, dpi: int = 300) -> str:
        full_text = []
        try:
            doc = fitz.open(pdf_path) 
            n_pages = len(doc)
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            logger.info(f"Renderizando {n_pages} páginas de {pdf_path} para OCR con PyMuPDF (DPI: {dpi}).")
            for page_number in range(n_pages):
                page = doc.load_page(page_number) 
                pix = page.get_pixmap(matrix=mat, annots=False) 
                pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(pil_image, lang=self.lang)
                full_text.append(text)
            doc.close() 
            logger.info(f"OCR en PDF {pdf_path} completado mediante renderizado de PyMuPDF.")
            return "\n".join(full_text)
        except FileNotFoundError:
            logger.error(f"Error: El archivo PDF no se encontró en {pdf_path}")
            return ""
        except pytesseract.TesseractNotFoundError:
            logger.error(f"Error: Tesseract OCR no se encontró en la ruta especificada: {settings.TESSERACT_CMD}. "
                         "Asegúrate de que Tesseract esté instalado y la ruta sea correcta.")
            return ""
        except Exception as e:
            logger.error(f"Error al realizar OCR en PDF {pdf_path} con PyMuPDF: {e}. "
                         "Asegúrate de que PyMuPDF y Pillow estén correctamente instalados y que el PDF no esté corrupto.")
            return ""