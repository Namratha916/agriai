from __future__ import annotations

import os
import base64
import tempfile
from io import BytesIO
from pathlib import Path

_WHISPER = None


def speech_to_text(audio_bytes: bytes, language: str = "auto") -> str | None:
    global _WHISPER
    try:
        from transformers import pipeline

        if _WHISPER is None:
            _WHISPER = pipeline(
                "automatic-speech-recognition",
                model=os.getenv("HF_WHISPER_MODEL", "openai/whisper-tiny"),
                local_files_only=os.getenv("HF_LOCAL_ONLY", "0") == "1",
            )
        language_map = {"en": "english", "hi": "hindi", "kn": "kannada"}
        generate_kwargs = {} if language == "auto" else {"language": language_map.get(language, language)}
        result = _WHISPER(audio_bytes, generate_kwargs=generate_kwargs)
        return result.get("text", "").strip()
    except Exception:
        return None


def text_to_speech_audio(text: str, language: str = "en") -> dict[str, str] | None:
    gtts_audio = _gtts_audio(text, language)
    if gtts_audio:
        return {"audio_base64": gtts_audio, "mime_type": "audio/mpeg"}

    coqui_audio = _coqui_audio(text, language)
    if coqui_audio:
        return {"audio_base64": coqui_audio, "mime_type": "audio/wav"}

    return None


def text_to_speech_base64(text: str, language: str = "en") -> str | None:
    audio = text_to_speech_audio(text, language)
    return audio["audio_base64"] if audio else None


def _gtts_audio(text: str, language: str = "en") -> str | None:
    try:
        from gtts import gTTS

        lang_map = {"en": "en", "hi": "hi", "kn": "kn"}
        buffer = BytesIO()
        gTTS(text=text, lang=lang_map.get(language, "en")).write_to_fp(buffer)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None


def _coqui_audio(text: str, language: str = "en") -> str | None:
    try:
        from TTS.api import TTS

        model_name = os.getenv("COQUI_TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
        tts = TTS(model_name)
        lang_map = {"en": "en", "hi": "hi", "kn": "kn"}
        language_code = lang_map.get(language, "en")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            output_path = Path(audio_file.name)

        try:
            if "xtts" in model_name.lower() or "multilingual" in model_name.lower():
                tts.tts_to_file(text=text, language=language_code, file_path=str(output_path))
            else:
                tts.tts_to_file(text=text, file_path=str(output_path))
            return base64.b64encode(output_path.read_bytes()).decode("ascii")
        finally:
            output_path.unlink(missing_ok=True)
    except Exception:
        return None
