import os
from dotenv import load_dotenv
load_dotenv()  

class Settings:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "8889")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "facturacion") 
    DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    PDF_INPUT_DIR = os.getenv("PDF_INPUT_DIR", "data/sample_invoices")
    PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR", "data/processed_data")
    TESSERACT_CMD = os.getenv("TESSERACT_CMD", "/usr/local/bin/tesseract") 
    POPPLER_PATH = os.getenv("POPPLER_PATH", "/usr/local/bin") 
    TESSDATA_PREFIX: str = os.getenv("TESSDATA_PREFIX", "/usr/local/share/tessdata")
    TESSERACT_LANG = os.getenv("TESSERACT_LANG", "spa") 
    SPACY_MODEL = os.getenv("SPACY_MODEL", "es_core_news_sm") 
    CONFIDENCE_THRESHOLD_OCR = 0.7
    CONFIDENCE_THRESHOLD_REGEX = 0.9
    CONFIDENCE_THRESHOLD_NLP = 0.8
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    LEARNED_PATTERNS_FILE = os.path.join(os.path.dirname(__file__), 'learned_patterns.json')
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    PDF_PROCESSED_DIR: str = os.path.join(BASE_DIR, 'data', 'processed_pdfs')
settings = Settings()  