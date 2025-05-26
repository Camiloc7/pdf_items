from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline
import spacy
import schedule
import time
from typing import Dict, Any  # Importación corregida
from learning.feedback_handler import FeedbackHandlerML
from extraction.nlp_parser import NLPParserML
from database.crud import CorrectedFieldCRUD
from database.models import SessionLocal
import logging

logger = logging.getLogger(__name__)

nlp = spacy.load("es_core_news_sm")
text = "Factura No: 12345, Proveedor: Empresa XYZ, Monto: $1,234.56"
doc = nlp(text)

for ent in doc.ents:
    print(ent.text, ent.label_)

db_session = SessionLocal()
corrected_field_crud = CorrectedFieldCRUD(db_session)

class InvoiceClassifier:
    def __init__(self, model_path: str):
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        logger.info(f"Modelo de clasificación de facturas cargado desde '{model_path}'.")

    def classify_invoice(self, text: str) -> str:
        prediction = self.model.predict([text])[0]
        return prediction

def retrain_correction_model():
    # Recolectar datos de correcciones
    corrections = corrected_field_crud.get_all_corrected_fields()
    data = pd.DataFrame([{
        "field_name": c.nombre_campo,
        "original_value": c.valor_original,
        "corrected_value": c.valor_corregido
    } for c in corrections])

    # Validar datos antes del entrenamiento
    if data.isnull().any().any():
        logger.error("Los datos contienen valores nulos. No se puede entrenar el modelo.")
        return

    # Vectorización y entrenamiento
    vectorizer = TfidfVectorizer()
    model = RandomForestClassifier()
    pipeline = make_pipeline(vectorizer, model)
    pipeline.fit(data["original_value"], data["corrected_value"])

    # Guardar el pipeline completo
    with open("models/correction_model.pkl", "wb") as f:
        pickle.dump(pipeline, f)

    # Cargar el pipeline completo
    with open("models/correction_model.pkl", "rb") as f:
        pipeline = pickle.load(f)

    logger.info("Modelo de corrección reentrenado y guardado.")

class InvoiceProcessingPipeline:
    def __init__(self, classifier_path: str, ner_model_path: str, correction_model_path: str):
        self.classifier = InvoiceClassifier(classifier_path)
        self.ner_parser = NLPParserML(ner_model_path)
        self.correction_handler = FeedbackHandlerML(correction_model_path)

    def process_invoice(self, text: str) -> Dict[str, Any]:
        try:
            # Clasificar proveedor
            provider = self.classifier.classify_invoice(text)
            logger.info(f"Proveedor identificado: {provider}")
        except Exception as e:
            logger.error(f"Error al clasificar proveedor: {e}")
            provider = None

        try:
            # Extraer entidades
            extracted_data = self.ner_parser.extract_entities(text)
        except Exception as e:
            logger.error(f"Error al extraer entidades: {e}")
            extracted_data = {}

        try:
            # Aplicar correcciones
            for field, value in extracted_data.items():
                corrected_value = self.correction_handler.predict_correction(field, value)
                extracted_data[field] = corrected_value
        except Exception as e:
            logger.error(f"Error al aplicar correcciones: {e}")

        return extracted_data

# Programar reentrenamiento diario
schedule.every().day.at("02:00").do(retrain_correction_model)

while True:
    schedule.run_pending()
    time.sleep(1)