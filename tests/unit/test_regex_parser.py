import pytest
from extraction.regex_parser import RegexParser
from datetime import datetime
@pytest.fixture
def regex_parser():
    return RegexParser()
def test_extract_invoice_number(regex_parser):
    text = "Número de factura: INV-2023-001"
    extracted = regex_parser.extract_fields(text)
    assert extracted.get("invoice_number") == "INV-2023-001"
def test_extract_issue_date(regex_parser):
    text = "Fecha: 23/05/2025"
    extracted = regex_parser.extract_fields(text)
    assert extracted.get("issue_date") == datetime(2025, 5, 23)
    text_dash = "Fecha: 2024-01-15"
    extracted_dash = regex_parser.extract_fields(text_dash)
    assert extracted_dash.get("issue_date") == datetime(2024, 1, 15)
def test_extract_total_amount(regex_parser):
    text = "Total: $1234.56 USD"
    extracted = regex_parser.extract_fields(text)
    assert extracted.get("total_amount") == 1234.56
    assert extracted.get("currency") == "$"
    text_comma = "IMPORTE TOTAL: 1.234,50 EUR"
    extracted_comma = regex_parser.extract_fields(text_comma)
    assert extracted_comma.get("total_amount") == 1234.50
    assert extracted_comma.get("currency") == "EUR"
def test_extract_supplier_and_customer(regex_parser):
    text = """
    Proveedor: ABC S.A. de C.V.
    RFC: ABC123XYZ
    Cliente: Cliente Ejemplo S.A.
    RFC Cliente: CEE987654321
    """
    extracted = regex_parser.extract_fields(text)
    assert extracted.get("supplier_name") == "ABC S.A. de C.V."
    assert extracted.get("supplier_tax_id") == "ABC123XYZ"
    assert extracted.get("customer_name") == "Cliente Ejemplo S.A."
    assert extracted.get("customer_tax_id") == "CEE987654321"
def test_add_custom_pattern(regex_parser):
    regex_parser.add_pattern("custom_field", r"Custom Value:\s*(.+)")
    text = "Some text. Custom Value: This is my custom data."
    extracted = regex_parser.extract_fields(text)
    assert extracted.get("custom_field") == "This is my custom data."
def test_no_match(regex_parser):
    text = "Texto sin patrones conocidos."
    extracted = regex_parser.extract_fields(text)
    assert extracted.get("invoice_number") is None
    assert extracted.get("total_amount") is None