# invoice_parser/tests/unit/test_combiner.py

import pytest
from extraction.combiner import ResultCombiner
from datetime import datetime

@pytest.fixture
def combiner():
    return ResultCombiner()

def test_combine_results_priority(combiner):
    pdf_direct_data = {"invoice_number": "INV123", "total_amount": 100.0}
    ocr_data = {"invoice_number": "INV123_OCR", "total_amount": 99.99, "supplier_name": "OCR Corp"}
    regex_data = {"invoice_number": "INV123_REGEX", "total_amount": 100.0, "issue_date": datetime(2025, 1, 1)}
    nlp_data = {"invoice_number": "INV123_NLP", "supplier_name": "NLP Solutions", "customer_name": "Customer NLP"}
    combined = combiner.combine_results(pdf_direct_data, ocr_data, regex_data, nlp_data)
    assert combined["invoice_number"] == "INV123_REGEX"
    assert combined["total_amount"] == 100.0
    assert combined["issue_date"] == datetime(2025, 1, 1)
    assert combined["supplier_name"] == "NLP Solutions"
    assert combined["customer_name"] == "Customer NLP"
    assert "OCR Corp" not in combined.values()
def test_combine_results_missing_fields(combiner):
    pdf_direct_data = {}
    ocr_data = {"supplier_name": "OCR Supplier"}
    regex_data = {}
    nlp_data = {"customer_name": "NLP Customer"}
    combined = combiner.combine_results(pdf_direct_data, ocr_data, regex_data, nlp_data)
    assert combined["invoice_number"] is None
    assert combined["supplier_name"] == "OCR Supplier"
    assert combined["customer_name"] == "NLP Customer"
def test_combine_results_type_casting(combiner):
    pdf_direct_data = {}
    ocr_data = {}
    regex_data = {"total_amount": "1,234.56", "issue_date": "15-02-2023"}
    nlp_data = {}
    combined = combiner.combine_results(pdf_direct_data, ocr_data, regex_data, nlp_data)
    assert combined["total_amount"] == 1234.56
    assert isinstance(combined["total_amount"], float)
    assert combined["issue_date"] == datetime(2023, 2, 15)
    assert isinstance(combined["issue_date"], datetime)
def test_combine_results_invalid_types(combiner):
    pdf_direct_data = {}
    ocr_data = {}
    regex_data = {"total_amount": "not_a_number", "issue_date": "invalid-date"}
    nlp_data = {}
    combined = combiner.combine_results(pdf_direct_data, ocr_data, regex_data, nlp_data)
    assert combined["total_amount"] is None
    assert combined["issue_date"] is None