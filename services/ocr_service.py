from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any


@dataclass
class OCRResult:
    text: str
    engines_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    confidence: float | None = None


class OCRService:
    def __init__(self, trocr_model: str = "microsoft/trocr-base-printed", local_only: bool = True):
        self.trocr_model = trocr_model
        self.local_only = local_only
        self._easyocr_reader = None
        self._trocr = None

    def analyze(self, image_bytes: bytes) -> OCRResult:
        result = OCRResult(text="")
        image = self._preprocess_image(image_bytes, result)
        if image is None:
            return result

        texts = []
        tesseract_text = self._run_tesseract(image, result)
        if tesseract_text:
            texts.append(tesseract_text)

        easyocr_text = self._run_easyocr(image, result)
        if easyocr_text:
            texts.append(easyocr_text)

        trocr_text = self._run_trocr(image, result)
        if trocr_text:
            texts.append(trocr_text)

        result.text = "\n".join(dedupe_lines(texts)).strip()
        return result

    def _preprocess_image(self, image_bytes: bytes, result: OCRResult):
        try:
            from PIL import Image, ImageEnhance, ImageFilter

            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            max_side = 1800
            image.thumbnail((max_side, max_side))
            gray = image.convert("L")
            gray = ImageEnhance.Contrast(gray).enhance(1.8)
            gray = gray.filter(ImageFilter.SHARPEN)
            return gray
        except Exception as exc:
            result.errors.append(f"image_preprocess_failed: {exc}")
            return None

    def _run_tesseract(self, image: Any, result: OCRResult) -> str:
        try:
            import pytesseract

            text = pytesseract.image_to_string(image, config="--psm 6")
            if text.strip():
                result.engines_used.append("tesseract")
            return text.strip()
        except Exception as exc:
            result.errors.append(f"tesseract_unavailable: {exc}")
            return ""

    def _run_easyocr(self, image: Any, result: OCRResult) -> str:
        try:
            import numpy as np
            import easyocr

            if self._easyocr_reader is None:
                self._easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            values = self._easyocr_reader.readtext(np.array(image), detail=1, paragraph=True)
            chunks = []
            confidences = []
            for item in values:
                if len(item) >= 2:
                    chunks.append(str(item[1]))
                if len(item) >= 3 and isinstance(item[2], (int, float)):
                    confidences.append(float(item[2]))
            if chunks:
                result.engines_used.append("easyocr")
            if confidences:
                result.confidence = sum(confidences) / len(confidences)
            return "\n".join(chunks).strip()
        except Exception as exc:
            result.errors.append(f"easyocr_unavailable: {exc}")
            return ""

    def _run_trocr(self, image: Any, result: OCRResult) -> str:
        try:
            from transformers import pipeline

            if self._trocr is None:
                self._trocr = pipeline(
                    "image-to-text",
                    model=self.trocr_model,
                    local_files_only=self.local_only,
                )
            output = self._trocr(image)
            text = output[0].get("generated_text", "") if output else ""
            if text.strip():
                result.engines_used.append("trocr")
            return text.strip()
        except Exception as exc:
            result.errors.append(f"trocr_unavailable: {exc}")
            return ""


def dedupe_lines(texts: list[str]) -> list[str]:
    seen = set()
    lines = []
    for text in texts:
        for line in text.splitlines():
            clean = " ".join(line.split())
            key = clean.lower()
            if clean and key not in seen:
                seen.add(key)
                lines.append(clean)
    return lines
