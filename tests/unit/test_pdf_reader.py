import pytest
import os
from extraction.pdf_reader import PDFReader
@pytest.fixture(scope="module")
def sample_pdf_path(tmp_path_factory):
    pdf_dir = tmp_path_factory.mktemp("pdfs")
    pdf_file = pdf_dir / "test_invoice.pdf"
    with open(pdf_file, "w") as f:
        f.write("%PDF-1.4\n1 0 obj<<>>endobj\nxref\n0 2\n0000000000 65535 f\n0000000009 00000 n\ntrailer<<>>startxref\n16\n%%EOF")
    return str(pdf_file)
@pytest.fixture(scope="module")
def pdf_reader():
    return PDFReader()
def test_extract_text_from_valid_pdf(pdf_reader, sample_pdf_path):
    text = pdf_reader.extract_text(sample_pdf_path)
    assert isinstance(text, str) 
def test_extract_text_from_non_existent_pdf(pdf_reader):
    non_existent_path = "non_existent.pdf"
    text = pdf_reader.extract_text(non_existent_path)
    assert text == "" 