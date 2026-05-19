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
    def __init__(
        self,
        trocr_model: str = "microsoft/trocr-base-printed",
        local_only: bool = False,
        enable_deep_ocr: bool = False,
    ):
        self.trocr_model = trocr_model
        self.local_only = local_only
        self.enable_deep_ocr = enable_deep_ocr
        self._easyocr_reader = None
        self._trocr = None

    def analyze(self, image_bytes: bytes) -> OCRResult:
        result = OCRResult(text="")
        images = self._preprocess_images(image_bytes, result)
        if not images:
            return result

        texts = []
        for name, image in images:
            tesseract_text = self._run_tesseract(image, result, name)
            if tesseract_text:
                texts.append(tesseract_text)

        if self.enable_deep_ocr:
            best_image = images[-1][1]
            easyocr_text = self._run_easyocr(best_image, result)
            if easyocr_text:
                texts.append(easyocr_text)

            trocr_text = self._run_trocr(best_image, result)
            if trocr_text:
                texts.append(trocr_text)
        else:
            result.errors.append("deep_ocr_disabled: set AGRIAI_DEEP_OCR=1 to enable EasyOCR/TrOCR")

        result.text = "\n".join(dedupe_lines(texts)).strip()
        if not result.text:
            result.errors.append(
                "no_text_extracted: OCR could not read the label. Type visible label text or install Tesseract/EasyOCR models."
            )
        return result

    def _preprocess_images(self, image_bytes: bytes, result: OCRResult):
        try:
            from PIL import Image, ImageEnhance, ImageFilter

            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            max_side = 2200
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            gray = image.convert("L")
            gray = ImageEnhance.Contrast(gray).enhance(2.0)
            gray = gray.filter(ImageFilter.SHARPEN)
            variants = [("gray_sharp", gray)]

            try:
                import cv2
                import numpy as np

                array = np.array(gray)
                scaled = cv2.resize(array, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
                denoised = cv2.fastNlMeansDenoising(scaled, None, 10, 7, 21)
                adaptive = cv2.adaptiveThreshold(
                    denoised,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    31,
                    11,
                )
                _, otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
                sharpened = cv2.filter2D(denoised, -1, kernel)
                variants.extend(
                    [
                        ("opencv_scaled", Image.fromarray(scaled)),
                        ("opencv_adaptive_threshold", Image.fromarray(adaptive)),
                        ("opencv_otsu_threshold", Image.fromarray(otsu)),
                        ("opencv_sharpened", Image.fromarray(sharpened)),
                    ]
                )
                result.engines_used.append("opencv-preprocess")
            except Exception as exc:
                result.errors.append(f"opencv_preprocess_unavailable: {exc}")

            return variants
        except Exception as exc:
            result.errors.append(f"image_preprocess_failed: {exc}")
            return []

    def _run_tesseract(self, image: Any, result: OCRResult, variant_name: str) -> str:
        try:
            import pytesseract

            configs = [
                "-l eng+hin+kan --oem 3 --psm 6",
                "-l eng+hin+kan --oem 3 --psm 11",
                "--oem 3 --psm 6",
            ]
            chunks = []
            for config in configs:
                text = pytesseract.image_to_string(image, config=config)
                if text.strip():
                    chunks.append(text.strip())
            if chunks:
                result.engines_used.append(f"tesseract:{variant_name}")
            return "\n".join(chunks).strip()
        except Exception as exc:
            result.errors.append(f"tesseract_unavailable: {exc}")
            return ""

    def _run_easyocr(self, image: Any, result: OCRResult) -> str:
        try:
            import numpy as np
            import easyocr

            if self._easyocr_reader is None:
                try:
                    self._easyocr_reader = easyocr.Reader(["en", "hi", "kn"], gpu=False, verbose=False)
                except Exception:
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
