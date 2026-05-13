# extras.py — translation, summarization, file extraction, and review inspection helpers

import os
import re
from pathlib import Path

from config import TRANSLATION_MODELS, SUMMARY_MODEL, MAX_TOKENS

try:
    from transformers import pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from langdetect import detect as detect_language_code
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

_TRANSLATION_PIPELINES = {}
_SUMMARY_PIPELINE = None
_FAKE_PIPELINE = None


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "en"
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "hi"
    if any(ch in text for ch in ["¿", "¡", "á", "é", "í", "ó", "ú", "ñ"]):
        return "es"
    if any(ch in text for ch in ["à", "â", "ç", "é", "è", "ê", "ô", "û", "œ"]):
        return "fr"
    if LANGDETECT_AVAILABLE:
        try:
            code = detect_language_code(text)
            if code.startswith("mr"):
                return "mr"
            if code.startswith("hi"):
                return "hi"
            if code.startswith("fr"):
                return "fr"
            if code.startswith("es"):
                return "es"
            return "en"
        except Exception:
            return "en"
    return "en"


def translate_to_english(text: str) -> tuple[str, str]:
    lang = detect_language(text)
    if lang == "en" or not TRANSFORMERS_AVAILABLE:
        return text, lang

    model_name = TRANSLATION_MODELS.get(lang)
    if not model_name:
        return text, lang

    translator = _TRANSLATION_PIPELINES.get(lang)
    if translator is None:
        translator = hf_pipeline("translation", model=model_name)
        _TRANSLATION_PIPELINES[lang] = translator

    translated = translator(text, max_length=MAX_TOKENS)
    return translated[0]["translation_text"], lang


def summarize_text(text: str) -> str:
    if not TRANSFORMERS_AVAILABLE:
        raise RuntimeError("transformers is required for summarization")
    global _SUMMARY_PIPELINE
    if _SUMMARY_PIPELINE is None:
        _SUMMARY_PIPELINE = hf_pipeline("summarization", model=SUMMARY_MODEL)
    summary = _SUMMARY_PIPELINE(text, max_length=120, min_length=30, do_sample=False)
    return summary[0]["summary_text"]


def detect_fake_review(text: str) -> dict:
    clean = text.strip()
    if not clean:
        return {"label": "unknown", "score": 0.0}

    spam_score = 0.0
    if clean.isupper() and len(clean) > 5:
        spam_score += 0.4
    if clean.count("!") > 2 or clean.count("?") > 2:
        spam_score += 0.2
    if any(word in clean.lower() for word in ["buy now", "best seller", "free", "visit", "click"]):
        spam_score += 0.3
    if len(clean.split()) < 6:
        spam_score += 0.2

    if TRANSFORMERS_AVAILABLE:
        global _FAKE_PIPELINE
        if _FAKE_PIPELINE is None:
            _FAKE_PIPELINE = hf_pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        labels = ["fake review", "spam review", "bot-generated review", "genuine review"]
        result = _FAKE_PIPELINE(clean[:MAX_TOKENS], candidate_labels=labels)
        top = result["labels"][0]
        top_score = result["scores"][0]
        if top in ["fake review", "spam review", "bot-generated review"]:
            spam_score = max(spam_score, top_score)
        else:
            spam_score = min(spam_score, 1 - top_score)

    label = "Fake/Spam" if spam_score >= 0.5 else "Likely Genuine"
    return {"label": label, "score": float(min(1.0, spam_score))}


def extract_texts_from_file(file_path: str) -> list[str]:
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return [f.read()]
    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8") as f:
            lines = []
            for line in f:
                if line.strip():
                    parts = line.strip().split(",")
                    lines.append(parts[0])
            return lines
    if ext == ".pdf":
        if not PDF_AVAILABLE:
            raise RuntimeError("PyPDF2 is required to read PDF files")
        reader = PyPDF2.PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return ["\n".join(pages)]
    if ext == ".docx":
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx is required to read DOCX files")
        document = docx.Document(file_path)
        return ["\n".join(p.text for p in document.paragraphs if p.text.strip())]
    raise RuntimeError(f"Unsupported file type: {ext}")


def extract_text_from_file(file_path: str) -> str:
    texts = extract_texts_from_file(file_path)
    return texts[0] if texts else ""