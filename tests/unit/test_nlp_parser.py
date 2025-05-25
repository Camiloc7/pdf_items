import pytest
from extraction.nlp_parser import NLPParser
from unittest.mock import patch, MagicMock
@pytest.fixture(scope="module")
def mock_spacy_load():
    with patch('spacy.load') as mock_load:
        mock_nlp = MagicMock()
        mock_nlp.vocab = MagicMock()
        mock_nlp.vocab.strings = MagicMock() 
        mock_nlp.vocab.strings.__getitem__.return_value = "SOME_LABEL" 
        mock_doc = MagicMock()
        mock_doc.ents = [
            MagicMock(text="XYZ Corp", label_="ORG"),
            MagicMock(text="23 de Mayo de 2025", label_="DATE"),
            MagicMock(text="$150.75", label_="MONEY")
        ]
        mock_doc.__getitem__.side_effect = lambda slice_obj: MagicMock(text=f"mock_span_text_{slice_obj.start}_{slice_obj.stop}")
        mock_nlp.return_value = mock_doc
        mock_load.return_value = mock_nlp
        yield mock_load
@pytest.fixture
def nlp_parser(mock_spacy_load):
    return NLPParser()

def test_extract_entities_ner(nlp_parser):
    text = "La empresa XYZ Corp con fecha 23 de Mayo de 2025 pagó $150.75."
    extracted = nlp_parser.extract_entities(text)
    assert extracted.get("supplier_name") == "XYZ Corp" 
    assert extracted.get("issue_date") == "23 de Mayo de 2025"
    assert extracted.get("total_amount") == 150.75

def test_extract_entities_phrase_matcher(nlp_parser, mock_spacy_load):
    mock_nlp_instance = mock_spacy_load.return_value
    mock_matcher_instance = nlp_parser.matcher 
    mock_doc = MagicMock()
    mock_doc.ents = [] 
    mock_doc.__getitem__.side_effect = lambda slice_obj: MagicMock(text=f"Mocked Entity {slice_obj.start}-{slice_obj.stop}")
    mock_matcher_instance.__call__.return_value = [
        (nlp_parser.nlp.vocab.strings.add("SUPPLIER_NAME_KEYWORDS"), 0, 1),
    ]
    mock_nlp_instance.return_value = mock_doc
    text = "Proveedor: Mocked Supplier Name."
    extracted = nlp_parser.extract_entities(text)
    assert extracted.get("supplier_name").startswith("Mocked Entity")
def test_add_custom_pattern(nlp_parser, mock_spacy_load):
    nlp_parser.add_custom_pattern("CUSTOM_ORG", ["Mi Empresa S.A."])
    mock_nlp_instance = mock_spacy_load.return_value
    mock_matcher_instance = nlp_parser.matcher
def test_nlp_model_not_found(nlp_parser):
    with patch('spacy.load', side_effect=OSError("Model not found")):
        with pytest.raises(OSError):
            NLPParser()