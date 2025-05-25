import logging
from typing import Dict, Any, Optional
from datetime import datetime
logger = logging.getLogger(__name__)
class ResultCombiner:
    def __init__(self):

        self.priority_order = {
            "regex": 3,
            "nlp": 2,
            "ocr": 1,
            "pdf_direct": 0
        }
        self.expected_fields = [
            "invoice_number",
            "issue_date",
            "total_amount",
            "currency",
            "supplier_name",
            "supplier_tax_id",
            "customer_name",
            "customer_tax_id",
        ]
    def combine_results(self,
                        pdf_direct_data: Dict[str, Any],
                        ocr_data: Dict[str, Any],
                        regex_data: Dict[str, Any],
                        nlp_data: Dict[str, Any]) -> Dict[str, Any]:
        combined_data: Dict[str, Any] = {}
        for field in self.expected_fields:
            combined_data[field] = None
        for field in self.expected_fields:
            if regex_data.get(field) is not None:
                combined_data[field] = regex_data[field]
                logger.debug(f"Combiner: '{field}' tomado de Regex: {regex_data[field]}")
        for field in self.expected_fields:
            if combined_data.get(field) is None and nlp_data.get(field) is not None:
                combined_data[field] = nlp_data[field]
                logger.debug(f"Combiner: '{field}' tomado de NLP: {nlp_data[field]}")
        for field in self.expected_fields:
            if combined_data.get(field) is None and ocr_data.get(field) is not None:
                combined_data[field] = ocr_data[field]
                logger.debug(f"Combiner: '{field}' tomado de OCR: {ocr_data[field]}")
        self._cast_types(combined_data)
        logger.info("Combinación de resultados finalizada.")
        return combined_data
    def _cast_types(self, data: Dict[str, Any]):
        if 'total_amount' in data and data['total_amount'] is not None:
            try:
                data['total_amount'] = float(str(data['total_amount']).replace(',', '.'))
            except (ValueError, TypeError):
                data['total_amount'] = None
                logger.warning(f"No se pudo convertir total_amount '{data['total_amount']}' a float.")
        if 'issue_date' in data and data['issue_date'] is not None:
            if not isinstance(data['issue_date'], datetime):
                try:
                    data['issue_date'] = self._parse_date_string(str(data['issue_date']))
                except ValueError:
                    data['issue_date'] = None
                    logger.warning(f"No se pudo parsear issue_date '{data['issue_date']}' a datetime.")
    def _parse_date_string(self, date_string: str) -> Optional[datetime]:
        """Intenta parsear una cadena de fecha en varios formatos."""
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d",
            "%d/%m/%y", "%d-%m-%y"
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        return None