import pypdfium2 as pdfium
import logging

logger = logging.getLogger(__name__)

class PDFReader:
    def extract_text(self, pdf_path: str) -> str:
        try:
            doc = pdfium.PdfDocument(pdf_path)
            text_pages = []
            for page_index in range(len(doc)):
                page = doc.get_page(page_index)
                text_page = page.get_textpage()
                text_pages.append(text_page.get_text_range())
                text_page.close() 
                page.close() 
            doc.close()
            full_text = "\n".join(text_pages)
            logger.info(f"Texto extraído de {pdf_path} correctamente.")
            return full_text
        except FileNotFoundError:
            logger.error(f"Error: El archivo PDF no se encontró en {pdf_path}")
            return ""
        except Exception as e:
            logger.error(f"Error al extraer texto del PDF {pdf_path}: {e}")
            return ""