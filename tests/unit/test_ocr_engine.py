import pytest
import os
from extraction.ocr_engine import OCREngine
from unittest.mock import patch, MagicMock
@pytest.fixture(scope="module")
def sample_image_path(tmp_path_factory):
    img_dir = tmp_path_factory.mktemp("images")
    img_file = img_dir / "test_invoice_image.png"
    from PIL import Image
    img = Image.new('RGB', (60, 30), color = 'red')
    img.save(img_file)
    return str(img_file)
@pytest.fixture(scope="module")
def ocr_engine():
    return OCREngine()
@patch('pytesseract.pytesseract.image_to_string')
def test_image_to_text_success(mock_image_to_string, ocr_engine, sample_image_path):
    mock_image_to_string.return_value = "TEXTO DE PRUEBA OCR"
    text = ocr_engine.image_to_text(sample_image_path)
    assert text == "TEXTO DE PRUEBA OCR"
    mock_image_to_string.assert_called_once()
def test_image_to_text_non_existent_image(ocr_engine):
    text = ocr_engine.image_to_text("non_existent_image.png")
    assert text == ""
@patch('pytesseract.pytesseract.image_to_string', side_effect=pytesseract.TesseractNotFoundError)
def test_image_to_text_tesseract_not_found(mock_image_to_string, ocr_engine, sample_image_path):
    text = ocr_engine.image_to_text(sample_image_path)
    assert text == ""
@patch('pytesseract.pytesseract.image_to_string')
def test_pdf_to_text_ocr_success(mock_image_to_string, ocr_engine, sample_pdf_path):
    mock_image_to_string.return_value = "TEXTO OCR DEL PDF"
    text = ocr_engine.pdf_to_text_ocr(sample_pdf_path)
    assert text == "TEXTO OCR DEL PDF"
    mock_image_to_string.assert_called_once()