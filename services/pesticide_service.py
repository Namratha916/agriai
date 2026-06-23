from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


CHEMICAL_GROUPS = {
    "organophosphate": {
        "aliases": ["organophosphate", "organophosphates", "op pesticide", "op poison"],
        "danger_level": "High",
        "toxicity_category": "Nerve agent-like pesticide group",
        "usage": "Insect control in agriculture",
        "environmental_impact": "Can harm beneficial insects, aquatic life, birds, and soil organisms.",
    },
    "carbamate": {
        "aliases": ["carbamate", "carbamates"],
        "danger_level": "High",
        "toxicity_category": "Cholinesterase-inhibiting pesticide group",
        "usage": "Insect control",
        "environmental_impact": "Can harm non-target insects, birds, and aquatic organisms.",
    },
    "pyrethroid": {
        "aliases": ["pyrethroid", "pyrethroids"],
        "danger_level": "Moderate",
        "toxicity_category": "Synthetic pyrethroid pesticide group",
        "usage": "Insect control",
        "environmental_impact": "Highly toxic to fish and aquatic organisms.",
    },
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


class PesticideKnowledgeBase:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.pesticides = self._load()
        self.index = {
            normalize(alias): pesticide
            for pesticide in self.pesticides
            for alias in [pesticide["name"], *pesticide.get("aliases", [])]
        }

    def _load(self) -> list[dict[str, Any]]:
        with self.data_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def find(self, query: str) -> dict[str, Any] | None:
        clean_query = normalize(query)
        if not clean_query:
            return None

        if clean_query in self.index:
            return self.index[clean_query]

        for alias, pesticide in self.index.items():
            if alias and (alias in clean_query or clean_query in alias):
                return pesticide

        query_tokens = set(clean_query.split())
        best_match = None
        best_score = 0.0
        for alias, pesticide in self.index.items():
            alias_tokens = set(alias.split())
            if not alias_tokens:
                continue
            overlap = len(query_tokens & alias_tokens)
            score = overlap / len(alias_tokens)
            if overlap and score > best_score:
                best_score = score
                best_match = pesticide
        if best_score >= 0.5:
            return best_match

        return self.find_group(query)

    def find_in_text(self, text: str) -> dict[str, Any] | None:
        clean_text = normalize(text)
        for alias, pesticide in self.index.items():
            if alias and alias in clean_text:
                return pesticide
        for word in clean_text.split():
            if len(word) >= 5 and word in self.index:
                return self.index[word]
        best_match = None
        best_score = 0.0
        tokens = clean_text.split()
        for alias, pesticide in self.index.items():
            alias_tokens = alias.split()
            if not alias_tokens or len(alias) < 5:
                continue
            window_size = len(alias_tokens)
            candidates = [
                " ".join(tokens[index:index + window_size])
                for index in range(max(1, len(tokens) - window_size + 1))
            ]
            for candidate in candidates:
                score = SequenceMatcher(None, alias, candidate).ratio()
                if score > best_score:
                    best_score = score
                    best_match = pesticide
        if best_score >= 0.82:
            return best_match
        return self.find_group(text)

    def find_group(self, text: str) -> dict[str, Any] | None:
        clean_text = normalize(text)
        for group_name, group in CHEMICAL_GROUPS.items():
            if any(normalize(alias) in clean_text for alias in group["aliases"]):
                return {
                    "name": group_name.title(),
                    "aliases": group["aliases"],
                    "category": "Chemical group",
                    "danger_level": group["danger_level"],
                    "toxicity_category": group["toxicity_category"],
                    "usage": group["usage"],
                    "environmental_impact": group["environmental_impact"],
                    "symptoms": ["vomiting", "sweating", "salivation", "dizziness", "breathing difficulty"],
                    "first_aid": "Treat serious or swallowed exposure as urgent. Go to hospital or call poison control.",
                    "notes": "Chemical group match from user/OCR text.",
                    "routes": ["skin", "eye", "inhalation", "ingestion"],
                }
        return None

    def identify_from_ocr(self, ocr_text: str, filename: str = "", notes: str = "", chemical_hint: str = "") -> dict[str, Any]:
        combined = f"{chemical_hint}\n{filename}\n{notes}\n{ocr_text}"
        pesticide = self.find_in_text(combined)
        if pesticide is None and chemical_hint:
            pesticide = self.find(chemical_hint)
        active_ingredients = extract_active_ingredients(combined)
        product_guess = guess_product_name(combined)

        if pesticide is None and active_ingredients:
            pesticide = self.find(" ".join(active_ingredients))

        if pesticide is None and product_guess:
            pesticide = self.find(product_guess)
        if pesticide:
            active_ingredients = prefer_detected_pesticide_name(active_ingredients, pesticide.get("name", ""))

        return {
            "pesticide": pesticide,
            "active_ingredients": active_ingredients,
            "product_guess": product_guess,
            "toxicity_level": toxicity_level(pesticide, combined),
            "toxicity_category": toxicity_category(pesticide, combined),
            "matched_text": combined[:4000],
        }

    def structured_details(self, pesticide: dict[str, Any] | None, active_ingredients: list[str], product_guess: str = "", label_text: str = "") -> dict[str, Any]:
        usage = infer_usage(
            pesticide.get("usage") if pesticide else "",
            pesticide.get("category") if pesticide else "",
            " ".join([product_guess or "", label_text or "", " ".join(active_ingredients or [])]),
        )
        if pesticide is None:
            return {
                "product_name": product_guess or (active_ingredients[0] if active_ingredients else "Not detected from image"),
                "pesticide_name": active_ingredients[0] if active_ingredients else (product_guess or "Not detected from image"),
                "active_ingredients": active_ingredients,
                "usage": usage or "Not detected. Type the product name or active ingredient visible on the label.",
                "harmfulness_level": "Needs label text",
                "toxicity_category": "Needs OCR/manual label text",
                "side_effects": ["Cannot identify exact side effects until pesticide name or active ingredient is readable."],
                "first_aid": "If symptoms are present, contact a doctor or poison control.",
                "safety_precautions": ["Use PPE", "Avoid skin/eye contact", "Do not inhale spray mist"],
                "decontamination_steps": ["Remove contaminated clothes", "Wash exposed skin with soap and water"],
                "environmental_impact": "Avoid contaminating water, soil, food, and animal areas.",
            }

        return {
            "product_name": product_guess or pesticide.get("name", "Unknown"),
            "pesticide_name": pesticide.get("name", "Unknown"),
            "active_ingredients": active_ingredients or [pesticide.get("name", "Unknown")],
            "usage": usage or f"{pesticide.get('category', 'Pesticide')} use; verify on label.",
            "harmfulness_level": pesticide.get("danger_level", "Unknown"),
            "toxicity_category": pesticide.get("toxicity_category", pesticide.get("category", "Unknown")),
            "side_effects": pesticide.get("symptoms", []),
            "first_aid": pesticide.get("first_aid", "Seek medical help if symptoms appear."),
            "safety_precautions": [
                "Wear gloves, mask/respirator, goggles, long sleeves, and boots.",
                "Do not eat, drink, or touch face while handling pesticide.",
                "Keep children, family members, animals, and food away from contaminated items.",
            ],
            "decontamination_steps": [
                "Move to fresh air and away from spray area.",
                "Remove contaminated clothes, shoes, and gloves.",
                "Wash skin and hair with soap and running water.",
                "Rinse eyes with clean water for 15 minutes if exposed.",
            ],
            "environmental_impact": pesticide.get(
                "environmental_impact",
                "Avoid drift and runoff. Keep pesticide away from water bodies, bees, animals, and food storage.",
            ),
        }


def extract_active_ingredients(text: str) -> list[str]:
    patterns = [
        r"active\s+ingredient[s]?\s*[:\-]?\s*([a-zA-Z0-9, ./%\-]+)",
        r"\ba\.?i\.?\b\s*[:\-]?\s*([a-zA-Z0-9, ./%\-]+)",
        r"contains\s+([a-zA-Z0-9, ./%\-]+)",
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text or "", flags=re.IGNORECASE):
            cleaned = re.split(r"\n|warning|caution|danger|net|batch|mfg|exp", match, flags=re.IGNORECASE)[0]
            cleaned = cleaned.strip(" :-,.")
            if cleaned and cleaned not in found:
                for name in split_ingredient_names(cleaned[:120]):
                    add_unique(found, name)
    for match in re.findall(r"\b([A-Za-z][A-Za-z\-]{3,})\s+\d+(?:\.\d+)?\s*%?\s*(?:EC|SC|WP|SL|WG|GR|DP|SP|FS)\b", text or "", flags=re.IGNORECASE):
        clean = clean_candidate_name(match)
        add_unique(found, clean)
    return found[:5]


def infer_usage(explicit_usage: str = "", category: str = "", label_text: str = "") -> str:
    if explicit_usage:
        return explicit_usage

    clean = normalize(f"{category} {label_text}")
    if "insecticide" in clean or "pyrethroid" in clean or "organophosphate" in clean or "carbamate" in clean:
        return "Used to control insect pests on crops. Follow the crop, dose, and waiting-period directions on the product label."
    if "fungicide" in clean or "mancozeb" in clean or "carbendazim" in clean:
        return "Used to control fungal diseases on crops. Follow the crop and disease directions on the product label."
    if "herbicide" in clean or "glyphosate" in clean or "weed" in clean:
        return "Used to control weeds. Avoid drift onto crops, people, animals, and water."
    if "rodenticide" in clean or "rat" in clean or "rodent" in clean:
        return "Used to control rodents. Keep away from children, animals, food, and water sources."
    if "pesticide" in clean:
        return "Used for pest control. Confirm the exact pest/crop instructions on the product label."
    return ""


def guess_product_name(text: str) -> str:
    skip = {"danger", "warning", "caution", "poison", "pesticide", "insecticide", "fungicide", "herbicide"}
    formulation_line = best_formulation_line(text)
    if formulation_line:
        return formulation_line
    for line in (text or "").splitlines():
        clean = re.sub(r"[^A-Za-z0-9 %.\-]", " ", line).strip()
        words = [word for word in clean.split() if len(word) >= 4 and normalize(word) not in skip]
        if words:
            return " ".join(words[:4])[:80]
    return ""


def split_ingredient_names(value: str) -> list[str]:
    parts = re.split(r",|/|\+| and |\(|\)|\d+(?:\.\d+)?\s*%| w/?w| w/?v| ec| sc| wp| sl| wg| gr| dp| sp| fs", value, flags=re.IGNORECASE)
    names = []
    for part in parts:
        clean = clean_candidate_name(part)
        if clean and clean not in names:
            names.append(clean)
    return names


def clean_candidate_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9 .\-]", " ", value or "")
    clean = re.sub(r"\b(active|ingredient|contains|technical|formulation|insecticide|fungicide|herbicide|pesticide)\b", " ", clean, flags=re.IGNORECASE)
    clean = " ".join(clean.split()).strip(" .-")
    if len(clean) < 4:
        return ""
    return clean[:80]


def best_formulation_line(text: str) -> str:
    for line in (text or "").splitlines():
        if re.search(r"\b(active|ingredient|contains|composition)\b", line, flags=re.IGNORECASE):
            continue
        clean = re.sub(r"[^A-Za-z0-9 %.\-]", " ", line)
        clean = " ".join(clean.split()).strip()
        if re.search(r"\b\d+(?:\.\d+)?\s*%?\s*(EC|SC|WP|SL|WG|GR|DP|SP|FS)\b", clean, flags=re.IGNORECASE):
            return clean[:90]
    return ""


def add_unique(values: list[str], candidate: str) -> None:
    if not candidate:
        return
    candidate_key = normalize(candidate)
    if not candidate_key:
        return
    if any(normalize(existing) == candidate_key for existing in values):
        return
    values.append(candidate)


def prefer_detected_pesticide_name(values: list[str], pesticide_name: str) -> list[str]:
    if not pesticide_name:
        return values
    pesticide_key = normalize(pesticide_name)
    cleaned: list[str] = []
    matched = False
    for value in values:
        value_key = normalize(value)
        if value_key and (pesticide_key in value_key or value_key in pesticide_key or SequenceMatcher(None, pesticide_key, value_key).ratio() >= 0.82):
            matched = True
            add_unique(cleaned, pesticide_name)
        else:
            add_unique(cleaned, value)
    if not cleaned or matched:
        return cleaned or [pesticide_name]
    return [pesticide_name, *cleaned]


def toxicity_level(pesticide: dict[str, Any] | None, text: str) -> str:
    clean_text = normalize(text)
    if "poison" in clean_text or "danger" in clean_text or (pesticide and pesticide.get("danger_level") == "Extreme"):
        return "Extreme"
    if "warning" in clean_text or (pesticide and pesticide.get("danger_level") == "High"):
        return "High"
    if "caution" in clean_text or (pesticide and "Moderate" in pesticide.get("danger_level", "")):
        return "Moderate"
    return pesticide.get("danger_level", "Unknown") if pesticide else "Needs label text"


def toxicity_category(pesticide: dict[str, Any] | None, text: str) -> str:
    clean_text = normalize(text)
    if "red triangle" in clean_text or "danger" in clean_text:
        return "High hazard label clue"
    if "yellow triangle" in clean_text or "warning" in clean_text:
        return "Moderate hazard label clue"
    if pesticide:
        return pesticide.get("toxicity_category", pesticide.get("category", "Unknown"))
    return "Needs OCR/manual label text"
