import logging
from typing import Dict, Any
from extraction.classifier import InvoiceClassifier
from extraction.nlp_parser import NLPParserML
from learning.feedback_handler import FeedbackHandlerML

# Inicializar logger
logger = logging.getLogger(__name__)

class InvoiceProcessingPipeline:
    def __init__(self, classifier_path: str, ner_model_path: str, correction_model_path: str):
        self.classifier = InvoiceClassifier(classifier_path)
        self.ner_parser = NLPParserML(ner_model_path)
        self.correction_handler = FeedbackHandlerML(correction_model_path)

    def process_invoice(self, text: str) -> Dict[str, Any]:
        # Clasificar proveedor
        provider = self.classifier.classify_invoice(text)
        logger.info(f"Proveedor identificado: {provider}")

        # Extraer entidades
        extracted_data = self.ner_parser.extract_entities(text)

        # Aplicar correcciones
        for field, value in extracted_data.items():
            corrected_value = self.correction_handler.predict_correction(field, value)
            extracted_data[field] = corrected_value

        return extracted_data