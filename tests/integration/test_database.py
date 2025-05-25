import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Invoice
from database.crud import create_invoice, get_invoice

@pytest.fixture(scope='module')
def test_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

def test_create_invoice(test_db):
    invoice_data = {
        'invoice_number': 'INV-001',
        'amount': 100.0,
        'date': '2023-01-01'
    }
    invoice = create_invoice(test_db, invoice_data)
    assert invoice.id is not None
    assert invoice.invoice_number == invoice_data['invoice_number']

def test_get_invoice(test_db):
    invoice_data = {
        'invoice_number': 'INV-002',
        'amount': 200.0,
        'date': '2023-01-02'
    }
    create_invoice(test_db, invoice_data)
    invoice = get_invoice(test_db, invoice_data['invoice_number'])
    assert invoice is not None
    assert invoice.amount == invoice_data['amount']