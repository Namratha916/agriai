from __future__ import annotations

import re


LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
}


def contains_kannada(text: str) -> bool:
    return any("\u0c80" <= char <= "\u0cff" for char in text)


def contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097f" for char in text)


def detect_language(text: str, requested_language: str = "auto") -> str:
    if requested_language in LANGUAGE_LABELS:
        return requested_language
    if contains_kannada(text):
        return "kn"
    if contains_devanagari(text):
        return "hi"
    return "en"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def language_label(language: str) -> str:
    return LANGUAGE_LABELS.get(language, "English")


def translate_text(text: str, target_language: str) -> str:
    if target_language == "en":
        return text

    try:
        from transformers import pipeline

        model_map = {
            "hi": "facebook/nllb-200-distilled-600M",
            "kn": "facebook/nllb-200-distilled-600M",
        }
        target_map = {"hi": "hin_Deva", "kn": "kan_Knda"}
        translator = pipeline("translation", model=model_map[target_language])
        result = translator(text, src_lang="eng_Latn", tgt_lang=target_map[target_language], max_length=256)
        return result[0]["translation_text"]
    except Exception:
        return text
