from __future__ import annotations

import base64
from io import BytesIO


def speech_to_text(audio_bytes: bytes, language: str = "auto") -> str | None:
    try:
        from transformers import pipeline

        recognizer = pipeline("automatic-speech-recognition", model="openai/whisper-small")
        result = recognizer(audio_bytes, generate_kwargs={} if language == "auto" else {"language": language})
        return result.get("text", "").strip()
    except Exception:
        return None


def text_to_speech_base64(text: str, language: str = "en") -> str | None:
    try:
        from gtts import gTTS

        lang_map = {"en": "en", "hi": "hi", "kn": "kn"}
        buffer = BytesIO()
        gTTS(text=text, lang=lang_map.get(language, "en")).write_to_fp(buffer)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None
