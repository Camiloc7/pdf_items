import unittest
from invoice_parser.main import process_invoice
class TestFullFlow(unittest.TestCase):

    def setUp(self):
        self.sample_invoice_path = 'data/sample_invoices/invoice_format_A.pdf'
        self.expected_output = {
            'invoice_number': '12345',
            'date': '2023-01-01',
            'total': 100.00
        }

    def test_full_flow(self):
        result = process_invoice(self.sample_invoice_path)
        self.assertEqual(result, self.expected_output)

    def tearDown(self):
        pass

if __name__ == '__main__':
    unittest.main()