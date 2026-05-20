from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import requests
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from chatbot.llm import AgriAILLM, ModelConfig
from prompt_templates import AGRIAI_PROVIDER_PROMPT, GENERAL_CHAT_PROMPT, IMAGE_ANALYSIS_PROMPT, SAFETY_RESPONSE_PROMPT, language_name
from services.ocr_service import OCRService
from services.ollama_service import OllamaClient
from services.cloud_chat_service import GitHubModelsClient
from services.pesticide_service import PesticideKnowledgeBase
from services.rag_service import RAGService
from services.voice_service import speech_to_text, text_to_speech_audio


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "pesticides.json"
DOCS_DIR = BASE_DIR / "knowledge"
VECTOR_DIR = BASE_DIR / "vector_store"

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "ollama").lower().strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_URL = os.getenv("OLLAMA_URL", f"{OLLAMA_BASE_URL}/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "3"))
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.3")
HF_LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "1") == "1"
AI_IMAGE_EXPLANATION = os.getenv("AI_IMAGE_EXPLANATION", "0") == "1"

app = Flask(__name__)
KB = PesticideKnowledgeBase(DATA_PATH)
OCR = OCRService(
    trocr_model=os.getenv("HF_OCR_MODEL", "microsoft/trocr-base-printed"),
    local_only=HF_LOCAL_ONLY,
    enable_deep_ocr=os.getenv("AGRIAI_DEEP_OCR", "1") == "1",
    enable_trocr=os.getenv("AGRIAI_ENABLE_TROCR", "0") == "1",
)
RAG = RAGService(DATA_PATH, DOCS_DIR, VECTOR_DIR)
OLLAMA = OllamaClient(OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT)
SELECTED_LLM = AgriAILLM(
    ModelConfig(
        provider=MODEL_PROVIDER,
        ollama_base_url=OLLAMA_BASE_URL,
        ollama_model=OLLAMA_MODEL,
        xai_api_key=XAI_API_KEY,
        grok_model=GROK_MODEL,
        timeout=OLLAMA_TIMEOUT,
    )
)
CLOUD_CHAT = GitHubModelsClient()


def load_pesticides() -> list[dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_provider_messages(
    user_message: str,
    chemical_name: str,
    symptoms: str,
    rag_context: str,
    image_text: str,
    language: str,
) -> list[dict[str, str]]:
    pesticide = find_pesticide(chemical_name) or find_pesticide_in_text(user_message) or find_chemical_group(user_message)
    pesticide_name = pesticide.get("name", chemical_name or "Unknown") if pesticide else (chemical_name or "Unknown")
    context = (
        f"Detected pesticide: {pesticide_name}\n"
        f"Detected symptoms: {symptoms or ', '.join(extract_symptoms(user_message)) or 'Not provided'}\n"
        f"Exposure route: {detect_exposure_route(f'{user_message} {symptoms}') or 'Unknown'}\n\n"
        f"{rag_context or 'No pesticide context retrieved.'}"
    )
    prompt = AGRIAI_PROVIDER_PROMPT.format(
        language=language_name(language),
        context=context,
        image_text=image_text or "No image text provided.",
        question=user_message,
    )
    return [
        {"role": "system", "content": "You are AgriAI. Follow the requested pesticide safety answer format and stay medically conservative."},
        {"role": "user", "content": prompt},
    ]


def selected_llm_reply(
    messages: list[dict[str, str]],
    safety_mode: bool,
    fallback_reply: str,
) -> tuple[str | None, str, str]:
    if SELECTED_LLM.provider == "grok" and not XAI_API_KEY:
        return "Grok API is selected, but XAI_API_KEY is not configured. Add XAI_API_KEY or switch MODEL_PROVIDER=ollama.", "grok-not-configured", "grok"
    try:
        result = SELECTED_LLM.chat(messages, safety_mode=safety_mode)
        if result:
            return result.text, result.model, result.provider
    except Exception:
        pass
    return fallback_reply, "agriai-provider-fallback", "built-in"


PESTICIDES = KB.pesticides
PESTICIDE_INDEX = {
    alias.lower(): pesticide
    for pesticide in PESTICIDES
    for alias in [pesticide["name"], *pesticide.get("aliases", [])]
}

HIGH_RISK_SYMPTOMS = {
    "seizure",
    "convulsion",
    "unconscious",
    "fainting",
    "breathing difficulty",
    "shortness of breath",
    "chest pain",
    "confusion",
    "severe vomiting",
    "blurred vision",
    "pinpoint pupils",
    "excessive sweating",
    "salivation",
    "muscle twitching",
}

MODERATE_RISK_SYMPTOMS = {
    "headache",
    "dizziness",
    "vomiting",
    "nausea",
    "stomach pain",
    "skin burning",
    "rash",
    "eye irritation",
    "cough",
    "weakness",
    "diarrhea",
}

CHEMICAL_GROUPS = {
    "organophosphate": {
        "aliases": ["organophosphate", "organophosphates", "op pesticide", "op poison"],
        "danger_level": "High",
        "symptoms": [
            "vomiting",
            "sweating",
            "salivation",
            "pinpoint pupils",
            "muscle twitching",
            "breathing difficulty",
            "seizure",
            "unconscious",
        ],
        "first_aid": "Organophosphate swallowing can be life-threatening. Call emergency services or go to hospital immediately.",
    },
    "carbamate": {
        "aliases": ["carbamate", "carbamates"],
        "danger_level": "High",
        "symptoms": ["vomiting", "sweating", "salivation", "weakness", "muscle twitching", "breathing difficulty"],
        "first_aid": "Carbamate poisoning can become serious quickly. Call poison control or go to hospital if swallowed or symptomatic.",
    },
    "pyrethroid": {
        "aliases": ["pyrethroid", "pyrethroids"],
        "danger_level": "Moderate",
        "symptoms": ["skin burning", "tingling", "eye irritation", "dizziness", "nausea"],
        "first_aid": "Wash exposed skin and seek medical help if symptoms are strong or exposure was swallowed.",
    },
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def contains_kannada(text: str) -> bool:
    return any("\u0c80" <= char <= "\u0cff" for char in text)


def contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097f" for char in text)


def resolve_language(requested_language: str, *texts: str) -> str:
    if requested_language in {"en", "hi", "kn"}:
        return requested_language
    joined = " ".join(texts)
    if contains_kannada(joined):
        return "kn"
    if contains_devanagari(joined):
        return "hi"
    return "en"


KANNADA_UI_REPLIES = {
    "greeting": "ನಮಸ್ಕಾರ, ನಾನು AgriAI. ರಾಸಾಯನಿಕದ ಹೆಸರು, ಅದು ಹೇಗೆ ತಗುಲಿತು, ಮತ್ತು ನಿಮಗೆ ಇರುವ ಲಕ್ಷಣಗಳನ್ನು ಹೇಳಿ. ನಾನು ಸರಳವಾಗಿ ಮಾರ್ಗದರ್ಶನ ಮಾಡುತ್ತೇನೆ.",
    "app_help": "AgriAI ಬಳಸಲು: ರಾಸಾಯನಿಕದ ಹೆಸರನ್ನು ನಮೂದಿಸಿ, ಲಕ್ಷಣಗಳನ್ನು ಆಯ್ಕೆಮಾಡಿ, ನಂತರ decontamination checklist ಅನುಸರಿಸಿ. ಗಂಭೀರ ಲಕ್ಷಣಗಳಿದ್ದರೆ emergency alert ಮತ್ತು hospital finder ಬಳಸಿ.",
    "exposure_question": "ದಯವಿಟ್ಟು label‌ನಲ್ಲಿರುವ ರಾಸಾಯನಿಕದ ಹೆಸರು ಮತ್ತು exposure ಹೇಗೆ ಆಯಿತು ಎಂದು ಹೇಳಿ: ಚರ್ಮ, ಕಣ್ಣು, ಉಸಿರಾಟ ಅಥವಾ ನುಂಗುವಿಕೆ. ತಲೆ ಸುತ್ತುವುದು, ವಾಂತಿ, ಬೆವರು, ಕಣ್ಣು ಉರಿಯುವುದು ಅಥವಾ ಉಸಿರಾಟದ ತೊಂದರೆ ಇದ್ದರೆ ತಿಳಿಸಿ.",
    "general": "ನಾನು pesticide safety, first aid, decontamination, emergency alert, hospital guidance ಮತ್ತು farming help ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಹುದು. ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬರೆಯಿರಿ.",
}

HINDI_UI_REPLIES = {
    "greeting": "नमस्ते, मैं AgriAI हूं। रसायन का नाम, वह कैसे लगा, और कौन से लक्षण हैं, यह बताइए। मैं आपको सरल तरीके से मार्गदर्शन दूंगा।",
    "app_help": "AgriAI इस्तेमाल करने के लिए: रसायन का नाम डालें, लक्षण चुनें, और decontamination checklist follow करें। गंभीर लक्षण हों तो emergency alert और hospital finder इस्तेमाल करें।",
    "exposure_question": "कृपया label पर लिखा रसायन नाम और exposure कैसे हुआ बताएं: त्वचा, आंख, सांस या निगलना। चक्कर, उल्टी, पसीना, आंख जलना या सांस की दिक्कत हो तो बताएं।",
    "general": "मैं pesticide safety, first aid, decontamination, emergency alert, hospital guidance और farming help में मदद कर सकता हूं। अपना सवाल लिखिए।",
}


def translate_builtin_reply(reply: str, language: str) -> str:
    if language != "kn":
        return reply

    translations = {
        "Hi, I am AgriAI. Tell me the chemical name, how it touched you, and any symptoms. For example: 'I sprayed chlorpyrifos and feel dizzy.' I will guide you step by step.": (
            "ನಮಸ್ಕಾರ, ನಾನು AgriAI. ರಾಸಾಯನಿಕದ ಹೆಸರು, ಅದು ಹೇಗೆ ತಗುಲಿತು, ಮತ್ತು ಇರುವ ಲಕ್ಷಣಗಳನ್ನು ಹೇಳಿ. "
            "ಉದಾಹರಣೆ: 'ನಾನು chlorpyrifos ಸಿಂಪಡಿಸಿದೆ ಮತ್ತು ತಲೆ ಸುತ್ತುತ್ತಿದೆ.' ನಾನು ಹಂತ ಹಂತವಾಗಿ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
        ),
        "You can use AgriAI in three quick steps: enter the chemical name, select symptoms, and follow the decontamination checklist. If symptoms are serious, use the emergency alert and hospital finder instead of waiting for the chatbot.": (
            "AgriAI ಅನ್ನು ಮೂರು ಸರಳ ಹಂತಗಳಲ್ಲಿ ಬಳಸಿ: ರಾಸಾಯನಿಕದ ಹೆಸರನ್ನು ನಮೂದಿಸಿ, ಲಕ್ಷಣಗಳನ್ನು ಆಯ್ಕೆಮಾಡಿ, "
            "ಮತ್ತು ಡೀಕಂಟಾಮಿನೇಶನ್ ಚೆಕ್‌ಲಿಸ್ಟ್ ಅನುಸರಿಸಿ. ಲಕ್ಷಣಗಳು ಗಂಭೀರವಾಗಿದ್ದರೆ ಚಾಟ್‌ಬಾಟ್‌ಗಾಗಿ ಕಾಯದೆ emergency alert ಮತ್ತು hospital finder ಬಳಸಿ."
        ),
        "A pesticide is a chemical or natural substance used to control pests such as insects, weeds, fungi, or rodents. Farmers use pesticides to protect crops, but some pesticides can harm people if they touch the skin, get into the eyes, are breathed in, or are swallowed. That is why workers should use protective gear, wash properly after spraying, and get medical help quickly if symptoms appear.": (
            "ಪೆಸ್ಟಿಸೈಡ್ ಎಂದರೆ ಕೀಟಗಳು, ಕಳೆ, ಫಂಗಸ್ ಅಥವಾ ಇಲಿ ಮುಂತಾದ ಪೆಸ್ಟ್‌ಗಳನ್ನು ನಿಯಂತ್ರಿಸಲು ಬಳಸುವ ರಾಸಾಯನಿಕ ಅಥವಾ ನೈಸರ್ಗಿಕ ಪದಾರ್ಥ. "
            "ಬೆಳೆಗಳನ್ನು ರಕ್ಷಿಸಲು ರೈತರು ಪೆಸ್ಟಿಸೈಡ್ ಬಳಸುತ್ತಾರೆ, ಆದರೆ ಅದು ಚರ್ಮಕ್ಕೆ ತಗುಲಿದರೆ, ಕಣ್ಣಿಗೆ ಹೋದರೆ, ಉಸಿರಿನಲ್ಲಿ ಹೋದರೆ ಅಥವಾ ನುಂಗಿದರೆ ಅಪಾಯವಾಗಬಹುದು. "
            "ಆದ್ದರಿಂದ ರಕ್ಷಣಾ ಸಾಧನ ಬಳಸಿ, ಸಿಂಪಡಿಸಿದ ನಂತರ ಚೆನ್ನಾಗಿ ತೊಳೆಯಿರಿ, ಮತ್ತು ಲಕ್ಷಣಗಳು ಬಂದರೆ ವೈದ್ಯಕೀಯ ಸಹಾಯ ಪಡೆಯಿರಿ."
        ),
    }
    return translations.get(reply, reply)


def localized_reply(intent: str, reply: str, language: str) -> str:
    if language == "kn":
        return KANNADA_UI_REPLIES.get(intent, reply)
    if language == "hi":
        return HINDI_UI_REPLIES.get(intent, reply)
    return reply


def localized_safety_reply(user_message: str, chemical_name: str, symptoms_text: str, language: str) -> str | None:
    pesticide = find_pesticide(chemical_name) if chemical_name else None
    pesticide = pesticide or find_pesticide_in_text(user_message) or find_chemical_group(f"{user_message} {chemical_name}")
    default_name = chemical_name or ("ರಾಸಾಯನಿಕ" if language == "kn" else "रसायन")
    name = pesticide.get("name", default_name) if pesticide else default_name
    symptoms = extract_symptoms(f"{user_message} {symptoms_text}")
    exposure = detect_exposure_route(f"{user_message} {symptoms_text}")

    if language == "kn":
        danger = pesticide.get("danger_level", "ಗೊತ್ತಿಲ್ಲ") if pesticide else "ಗೊತ್ತಿಲ್ಲ"
        symptom_text = ", ".join(symptoms) if symptoms else "ಲಕ್ಷಣಗಳನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ನೀಡಿಲ್ಲ"
        if exposure == "ingestion":
            first = f"{name} ನುಂಗಿರುವುದು ತುರ್ತು ಪರಿಸ್ಥಿತಿ. ವಾಂತಿ ಮಾಡಿಸಲು ಪ್ರಯತ್ನಿಸಬೇಡಿ, ಏನನ್ನೂ ತಿನ್ನಬೇಡಿ ಅಥವಾ ಕುಡಿಯಬೇಡಿ, ವೈದ್ಯರು ಅಥವಾ poison control ಹೇಳಿದರೆ ಮಾತ್ರ ಮಾಡಿ."
        else:
            first = f"{name} exposure ಆಗಿರಬಹುದು. ಕೆಲಸ ನಿಲ್ಲಿಸಿ, spray area ಇಂದ ದೂರ ಹೋಗಿ, fresh air ಇರುವ ಸ್ಥಳದಲ್ಲಿ ಇರಿರಿ."
        return (
            f"{first}\n"
            f"ಅಪಾಯ ಮಟ್ಟ: {danger}.\n"
            f"ಲಕ್ಷಣಗಳು: {symptom_text}.\n"
            "ತಕ್ಷಣದ ಕ್ರಮ: contaminated ಬಟ್ಟೆ, shoes ಮತ್ತು gloves ತೆಗೆದು ಬೇರೆ ಇಡಿ. ಚರ್ಮ ಮತ್ತು ಕೂದಲನ್ನು soap ಮತ್ತು running water ಬಳಸಿ ಚೆನ್ನಾಗಿ ತೊಳೆಯಿರಿ. ಕಣ್ಣಿಗೆ ಹೋದರೆ 15 ನಿಮಿಷ ನೀರಿನಿಂದ ತೊಳೆಯಿರಿ.\n"
            "ವೈದ್ಯಕೀಯ ಸಲಹೆ: ಉಸಿರಾಟದ ತೊಂದರೆ, ವಾಂತಿ, ತಲೆ ಸುತ್ತುವುದು, ಗೊಂದಲ, fits ಅಥವಾ ಹೆಚ್ಚು exposure ಇದ್ದರೆ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ. Product label ಅಥವಾ bottle ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ಭಾರತದಲ್ಲಿ 1800-116-117 ಕರೆ ಮಾಡಬಹುದು."
        )

    if language == "hi":
        danger = pesticide.get("danger_level", "Unknown") if pesticide else "Unknown"
        symptom_text = ", ".join(symptoms) if symptoms else "लक्षण स्पष्ट नहीं दिए गए"
        if exposure == "ingestion":
            first = f"{name} निगलना emergency हो सकता है। उल्टी कराने की कोशिश न करें, कुछ खाएं या पिएं नहीं, जब तक doctor या poison control न कहे।"
        else:
            first = f"{name} exposure हो सकता है। काम रोकें, spray area से दूर जाएं, और fresh air में रहें।"
        return (
            f"{first}\n"
            f"खतरे का स्तर: {danger}.\n"
            f"लक्षण: {symptom_text}.\n"
            "तुरंत कदम: contaminated कपड़े, shoes और gloves हटाकर अलग रखें। त्वचा और बाल soap और running water से धोएं। आंख में गया हो तो 15 मिनट पानी से धोएं.\n"
            "Medical help: सांस की दिक्कत, उल्टी, चक्कर, confusion, fits या heavy exposure हो तो तुरंत hospital जाएं। Product label या bottle साथ ले जाएं। भारत में 1800-116-117 call करें."
        )

    return None


def find_pesticide(query: str) -> dict[str, Any] | None:
    clean_query = normalize(query)
    if not clean_query:
        return None

    if clean_query in PESTICIDE_INDEX:
        return PESTICIDE_INDEX[clean_query]

    for alias, pesticide in PESTICIDE_INDEX.items():
        if clean_query in alias or alias in clean_query:
            return pesticide
    return None


def extract_symptoms(text: str) -> list[str]:
    clean_text = normalize(text)
    known_symptoms = HIGH_RISK_SYMPTOMS | MODERATE_RISK_SYMPTOMS | {
        symptom
        for pesticide in PESTICIDES
        for symptom in pesticide.get("symptoms", [])
    }
    return sorted(symptom for symptom in known_symptoms if symptom in clean_text)


def find_pesticide_in_text(text: str) -> dict[str, Any] | None:
    for alias, pesticide in PESTICIDE_INDEX.items():
        if alias in normalize(text):
            return pesticide
    return None


def find_chemical_group(text: str) -> dict[str, Any] | None:
    clean_text = normalize(text)
    for group_name, group in CHEMICAL_GROUPS.items():
        if any(alias in clean_text for alias in group["aliases"]):
            return {"name": group_name.title(), "category": "Chemical group", **group}
    return None


def detect_exposure_route(text: str) -> str | None:
    clean_text = normalize(text)
    tokens = set(clean_text.split())
    if tokens & {"swallow", "swallowed", "drink", "drank", "ingest", "ingested", "ate"}:
        return "ingestion"
    if tokens & {"eye", "eyes", "splash", "splashed"}:
        return "eye"
    if tokens & {"breathe", "breathing", "inhale", "inhaled", "smell", "spray", "sprayed", "spraying"} or "spray mist" in clean_text:
        return "inhalation"
    if tokens & {"skin", "hand", "hands", "clothes", "body", "touch", "touched"}:
        return "skin"
    return None


def classify_chat_intent(user_message: str, chemical_name: str = "", symptoms_text: str = "") -> str:
    raw_message = (user_message or "").strip().lower()
    clean_message = normalize(user_message)
    combined = normalize(f"{user_message} {chemical_name} {symptoms_text}")

    greetings = {"hi", "hello", "hey", "namaste", "good morning", "good evening", "good afternoon", "ನಮಸ್ಕಾರ", "नमस्ते"}
    if clean_message in greetings or raw_message in greetings:
        return "greeting"

    info_question_starts = (
        "what is",
        "what are",
        "what precautions",
        "what precaution",
        "precautions",
        "safety tips",
        "safe use",
        "how to use",
        "used for",
        "use of",
        "define",
        "explain",
        "tell me",
        "tell me about",
        "give me",
        "list",
        "write about",
        "meaning of",
        "difference between",
        "benefits",
        "advantages",
        "disadvantages",
        "why",
        "how",
    )
    info_question_contains = (
        "precaution",
        "precautions",
        "safety tips",
        "used for",
        "use for",
        "usage",
        "side effects",
        "first aid",
        "toxicity",
    )
    exposure_story_words = (
        "i sprayed",
        "i swallow",
        "i swallowed",
        "i inhaled",
        "i touched",
        "fell on me",
        "splashed",
        "exposed",
        "exposure",
        "feel dizzy",
        "feeling dizzy",
        "vomiting",
        "breathing difficulty",
    )
    if (clean_message.startswith(info_question_starts) or any(word in clean_message for word in info_question_contains)) and not any(word in combined for word in exposure_story_words):
        return "general"

    if any(word in combined for word in ("hospital", "doctor", "clinic", "poison control", "helpline", "emergency", "ambulance")):
        return "emergency_help"

    if (
        find_pesticide(chemical_name)
        or find_pesticide_in_text(user_message)
        or find_chemical_group(combined)
        or extract_symptoms(combined)
        or detect_exposure_route(combined)
    ):
        return "exposure"

    if any(word in combined for word in ("spray", "sprayed", "pesticide", "chemical", "poison", "exposure", "skin", "eyes", "smell", "inhale")):
        return "exposure_question"

    if any(word in combined for word in ("how", "what", "why", "guide", "checklist", "safe return", "use this app", "help")):
        return "app_help"

    return "general"


def build_base_reply(user_message: str, chemical_name: str = "", symptoms_text: str = "", language: str = "en") -> tuple[str, str]:
    intent = classify_chat_intent(user_message, chemical_name, symptoms_text)

    if intent == "greeting":
        reply = (
            intent,
            "Hi, I am AgriAI. Tell me the chemical name, how it touched you, and any symptoms. For example: 'I sprayed chlorpyrifos and feel dizzy.' I will guide you step by step.",
        )
        return reply[0], localized_reply(intent, reply[1], language)

    if intent == "emergency_help":
        reply = (
            intent,
            "If the person has breathing trouble, fainting, seizures, confusion, chest pain, severe vomiting, or chemical in the eyes, go to the nearest hospital now or call emergency services. In India, you can also call poison helpline 1800-116-117. Carry the chemical bottle or label.",
        )
        if language == "kn":
            return intent, "ಉಸಿರಾಟದ ತೊಂದರೆ, ಮೂರ್ಛೆ, fits, ಗೊಂದಲ, ಎದೆ ನೋವು, ತೀವ್ರ ವಾಂತಿ ಅಥವಾ ಕಣ್ಣಿಗೆ ರಾಸಾಯನಿಕ ಹೋದರೆ ತಕ್ಷಣ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ ಅಥವಾ emergency services ಕರೆ ಮಾಡಿ. ಭಾರತದಲ್ಲಿ poison helpline 1800-116-117 ಕರೆ ಮಾಡಬಹುದು. ರಾಸಾಯನಿಕದ ಬಾಟಲ್ ಅಥವಾ label ತೆಗೆದುಕೊಂಡು ಹೋಗಿ."
        return reply

    if intent == "app_help":
        reply = (
            intent,
            "You can use AgriAI in three quick steps: enter the chemical name, select symptoms, and follow the decontamination checklist. If symptoms are serious, use the emergency alert and hospital finder instead of waiting for the chatbot.",
        )
        return reply[0], localized_reply(intent, reply[1], language)

    if intent == "exposure_question" and not find_pesticide(chemical_name) and not find_pesticide_in_text(user_message) and not extract_symptoms(f"{user_message} {symptoms_text}"):
        reply = (
            intent,
            "Please tell me the chemical name from the label and what happened: skin contact, eye splash, breathing spray, or swallowing. Also tell me symptoms such as dizziness, vomiting, headache, sweating, eye burning, or breathing difficulty.",
        )
        if language == "kn":
            return intent, "ದಯವಿಟ್ಟು label‌ನಲ್ಲಿರುವ ರಾಸಾಯನಿಕದ ಹೆಸರು ಮತ್ತು ಏನಾಯಿತು ಎಂದು ಹೇಳಿ: ಚರ್ಮಕ್ಕೆ ತಗುಲಿದೆಯಾ, ಕಣ್ಣಿಗೆ ಸಿಂಪಡಿದೆಯಾ, ಉಸಿರಿನಲ್ಲಿ ಹೋಯಿತಾ, ಅಥವಾ ನುಂಗಿದೀರಾ? ತಲೆ ಸುತ್ತುವುದು, ವಾಂತಿ, ತಲೆನೋವು, ಬೆವರು, ಕಣ್ಣು ಉರಿಯುವುದು ಅಥವಾ ಉಸಿರಾಟದ ತೊಂದರೆ ಇದ್ದರೆ ತಿಳಿಸಿ."
        return reply[0], localized_reply(intent, reply[1], language)

    if intent == "general":
        reply = (
            intent,
            "I can help with pesticide exposure, symptoms, first aid, decontamination steps, emergency messages, and hospital guidance. Tell me what happened in one sentence and include the chemical name if you know it.",
        )
        if language == "kn":
            return intent, "ನಾನು pesticide exposure, ಲಕ್ಷಣಗಳು, first aid, decontamination steps, emergency message ಮತ್ತು hospital guidance ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಹುದು. ಏನಾಯಿತು ಎಂದು ಒಂದು ವಾಕ್ಯದಲ್ಲಿ ಹೇಳಿ, ರಾಸಾಯನಿಕದ ಹೆಸರು ಗೊತ್ತಿದ್ದರೆ ಸೇರಿಸಿ."
        return reply[0], localized_reply(intent, reply[1], language)

    safety_reply = build_safety_reply(user_message, chemical_name, symptoms_text)
    localized = localized_safety_reply(user_message, chemical_name, symptoms_text, language)
    if localized:
        safety_reply = localized
    return intent, safety_reply


def build_domain_info_reply(user_message: str, language: str = "en") -> str | None:
    clean_message = normalize(user_message)
    if "what is pesticide" in clean_message or "what are pesticides" in clean_message or "define pesticide" in clean_message:
        reply = (
            "A pesticide is a chemical or natural substance used to control pests such as insects, weeds, fungi, or rodents. "
            "Farmers use pesticides to protect crops, but some pesticides can harm people if they touch the skin, get into the eyes, are breathed in, or are swallowed. "
            "That is why workers should use protective gear, wash properly after spraying, and get medical help quickly if symptoms appear."
        )
        return translate_builtin_reply(reply, language)

    if "safe return" in clean_message or "this project" in clean_message:
        if language == "kn":
            return "AgriAI ರೈತರು ಮತ್ತು spray workers‌ಗಾಗಿ chemical decontamination alert ಮತ್ತು guide system. ಇದು chemical identify ಮಾಡುವುದು, symptoms check ಮಾಡುವುದು, decontamination steps, emergency alert, nearby medical help ಮತ್ತು chatbot guidance ನೀಡುತ್ತದೆ."
        return (
            "AgriAI is a chemical decontamination alert and guide system for farmers and spray workers. "
            "It helps users identify a chemical, check symptoms, follow decontamination steps, create an emergency alert, find nearby medical help, and chat with an assistant for guidance."
        )

    if "washing" in clean_message and "spray" in clean_message:
        if language == "kn":
            return "Pesticide ಸಿಂಪಡಿಸಿದ ನಂತರ ತೊಳೆಯುವುದು ಮುಖ್ಯ. ಇದು ಚರ್ಮ ಮತ್ತು ಕೂದಲಿನ ಮೇಲಿರುವ chemical residue ತೆಗೆದುಹಾಕುತ್ತದೆ ಮತ್ತು ಮನೆಗೆ pesticide ಕೊಂಡೊಯ್ಯುವುದನ್ನು ಕಡಿಮೆ ಮಾಡುತ್ತದೆ. Work clothes ಅನ್ನು family laundryಯಿಂದ ಬೇರ್ಪಡಿಸಿ."
        return (
            "Washing after spraying pesticide is important because it removes chemical residue from your skin and hair before it can keep absorbing into the body. "
            "It also prevents carrying pesticide into the home, where it could touch children, family members, food, bedding, or other clothes. "
            "After spraying, remove contaminated clothing, wash exposed skin with soap and running water, and keep work clothes separate from family laundry."
        )

    if "organophosphate" in clean_message and not detect_exposure_route(clean_message):
        if language == "kn":
            return "Organophosphates ನರಮಂಡಲದ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರುವ insecticide ಗುಂಪು. Exposure ಆದರೆ ತಲೆನೋವು, ಬೆವರು, ವಾಂತಿ, salivation, pinpoint pupils, muscle twitching, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ seizures ಬರಬಹುದು. ನುಂಗಿದ್ದರೆ ಅಥವಾ heavy exposure ಆಗಿದ್ದರೆ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಬೇಕು."
        return (
            "Organophosphates are a group of insecticides that can affect the nervous system. Exposure can cause headache, sweating, vomiting, salivation, pinpoint pupils, muscle twitching, breathing trouble, or seizures. "
            "If someone swallowed or was heavily exposed to an organophosphate, it is urgent and they should go to a hospital immediately."
        )

    return None


def build_safety_reply(user_message: str, chemical_name: str = "", symptoms_text: str = "") -> str:
    pesticide = find_pesticide(chemical_name) if chemical_name else None
    pesticide = pesticide or find_pesticide_in_text(user_message) or find_chemical_group(f"{user_message} {chemical_name}")
    exposure_route = detect_exposure_route(f"{user_message} {symptoms_text}")
    symptoms = extract_symptoms(f"{user_message} {symptoms_text}")
    high_matches = [symptom for symptom in symptoms if symptom in HIGH_RISK_SYMPTOMS]
    moderate_matches = [symptom for symptom in symptoms if symptom in MODERATE_RISK_SYMPTOMS]

    chemical_label = pesticide["name"] if pesticide else (chemical_name or "the chemical")
    lines = []

    if exposure_route == "ingestion":
        lines.append(
            f"I am sorry this happened. Swallowing {chemical_label} is urgent. Do not wait for symptoms. Call emergency services or go to the nearest hospital now."
        )
        lines.append("Do not induce vomiting, do not eat or drink unless a doctor or poison-control expert tells you to.")
    elif high_matches:
        lines.append(
            f"This may be an emergency because you mentioned {', '.join(high_matches)}. Call emergency services or go to the nearest hospital now."
        )
    elif pesticide and pesticide.get("danger_level") in {"High", "Extreme"} and (moderate_matches or symptoms):
        lines.append(
            f"{chemical_label} is marked {pesticide['danger_level']} risk in this app. Because symptoms are present, contact a doctor, hospital, or poison control now."
        )
    elif symptoms:
        lines.append(
            f"Your symptoms may be related to {chemical_label} exposure. Stop work and decontaminate before resting or going home."
        )
    else:
        lines.append(
            f"If you were exposed to {chemical_label}, decontaminate now even if symptoms are not clear yet."
        )

    if exposure_route != "ingestion":
        lines.extend(
            [
                "Move to fresh air and away from the spray area.",
                "Remove contaminated clothes, shoes, and gloves. Keep them away from family laundry.",
                "Wash exposed skin and hair with soap and running water. If eyes were exposed, rinse with clean water for at least 15 minutes.",
            ]
        )

    lines.append("Carry the product bottle or label to the doctor. In India, call poison helpline 1800-116-117 for urgent advice.")

    if pesticide:
        lines.append(f"Common warning symptoms for {pesticide['name']}: {', '.join(pesticide['symptoms'][:8])}.")

    return " ".join(lines)


def build_decontamination_steps(exposure_type: str = "skin") -> list[dict[str, str]]:
    common_steps = [
        {
            "title": "Move away from the chemical",
            "detail": "Go to fresh air and keep children, family members, and animals away from contaminated clothing or tools.",
        },
        {
            "title": "Remove contaminated clothing",
            "detail": "Take off gloves, shoes, socks, and clothes touched by chemical. Cut clothes off if pulling over the head would spread chemical.",
        },
        {
            "title": "Bag contaminated items",
            "detail": "Put clothes and PPE in a plastic bag or covered container. Do not mix them with household laundry.",
        },
        {
            "title": "Wash skin and hair",
            "detail": "Use running water and mild soap. Wash hair, nails, hands, neck, underarms, and exposed skin for 15 to 20 minutes when possible.",
        },
        {
            "title": "Use clean clothing",
            "detail": "Dry with a clean towel and wear clean clothes. Keep the used towel separate for washing.",
        },
        {
            "title": "Watch symptoms",
            "detail": "If symptoms appear or exposure was heavy, call emergency help, poison control, or go to the nearest hospital with the product label.",
        },
    ]

    if exposure_type == "eye":
        return [
            {
                "title": "Rinse eyes immediately",
                "detail": "Hold eyelids open and rinse with clean running water for at least 15 minutes. Remove contact lenses if easy.",
            },
            *common_steps[:1],
            common_steps[-1],
        ]

    if exposure_type == "inhalation":
        return [
            {
                "title": "Get fresh air",
                "detail": "Move upwind and away from the spray area. Do not enter a closed area without protection.",
            },
            {
                "title": "Loosen tight clothing",
                "detail": "Rest in a sitting position. If breathing is difficult, seek emergency care immediately.",
            },
            common_steps[-1],
        ]

    return common_steps


@app.get("/")
def index():
    return redirect(url_for("chatbot_page"))


@app.get("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")


@app.get("/identifier")
def identifier_page():
    return render_template("identifier.html", pesticides=PESTICIDES)


@app.get("/identify")
def identify_redirect_page():
    return render_template("identifier.html", pesticides=PESTICIDES)


@app.get("/analyzer")
def analyzer_page():
    return render_template("analyzer.html")


@app.get("/image")
def image_redirect_page():
    return render_template("analyzer.html")


@app.get("/checklist")
def checklist_page():
    return render_template("checklist.html")


@app.get("/symptoms")
def symptoms_page():
    return render_template("symptoms.html")


@app.get("/emergency")
def emergency_page():
    return render_template("emergency.html")


@app.get("/hospital")
def hospital_page():
    return render_template("hospital.html")


@app.get("/api/pesticides")
def api_pesticides():
    return jsonify(PESTICIDES)


@app.get("/api/chemical")
def api_chemical():
    chemical_name = request.args.get("name", "")
    pesticide = find_pesticide(chemical_name)
    if pesticide is None:
        return (
            jsonify(
                {
                    "found": False,
                    "message": "Chemical not found in the local seed database. Check the product label and call poison control or a doctor if symptoms are present.",
                }
            ),
            404,
        )
    return jsonify({"found": True, "chemical": pesticide})


@app.post("/api/symptoms")
def api_symptoms():
    payload = request.get_json(silent=True) or {}
    raw_symptoms = payload.get("symptoms", [])
    chemical_name = payload.get("chemical", "")
    symptoms_text = normalize(" ".join(raw_symptoms) if isinstance(raw_symptoms, list) else str(raw_symptoms))

    high_matches = sorted(symptom for symptom in HIGH_RISK_SYMPTOMS if symptom in symptoms_text)
    moderate_matches = sorted(symptom for symptom in MODERATE_RISK_SYMPTOMS if symptom in symptoms_text)
    pesticide = find_pesticide(chemical_name)

    if high_matches:
        level = "Emergency"
        action = "Call emergency services or go to the nearest hospital now. Carry the pesticide container or label."
    elif len(moderate_matches) >= 2 or (pesticide and pesticide.get("danger_level") in {"High", "Extreme"} and moderate_matches):
        level = "High concern"
        action = "Stop exposure, decontaminate, call poison control or a doctor immediately, and do not work again today."
    elif moderate_matches:
        level = "Watch closely"
        action = "Decontaminate, rest in fresh air, drink water if fully awake, and seek medical advice if symptoms continue or worsen."
    else:
        level = "Low information"
        action = "No classic poisoning pattern detected from the entered symptoms, but chemical exposure can still be serious. Follow the label and seek help if unsure."

    return jsonify(
        {
            "level": level,
            "matched_symptoms": high_matches + moderate_matches,
            "action": action,
            "chemical": pesticide,
        }
    )


@app.get("/api/decontamination")
def api_decontamination():
    exposure_type = request.args.get("type", "skin").lower()
    if exposure_type not in {"skin", "eye", "inhalation"}:
        exposure_type = "skin"
    return jsonify({"steps": build_decontamination_steps(exposure_type)})


@app.post("/api/emergency-message")
def api_emergency_message():
    payload = request.get_json(silent=True) or {}
    chemical = payload.get("chemical") or "unknown chemical"
    symptoms = payload.get("symptoms") or "not provided"
    location = payload.get("location") or "location unavailable"
    message = (
        "Emergency: possible pesticide/chemical exposure. "
        f"Chemical: {chemical}. Symptoms: {symptoms}. Location: {location}. "
        "Please call back immediately and help contact a hospital or poison control."
    )
    return jsonify({"message": message})


@app.post("/api/analyze-image")
def api_analyze_image():
    uploaded_file = request.files.get("image")
    language = resolve_language(request.form.get("language", "auto"))

    if uploaded_file is None:
        return jsonify({"reply": "Upload a pesticide label photo first.", "model": "no-image"}), 400

    image_bytes = uploaded_file.read()
    if not image_bytes:
        return jsonify({"reply": "The uploaded image file is empty.", "model": "empty-image"}), 400

    ocr_result = OCR.analyze(image_bytes)
    readable_text = ocr_result.text.strip()
    if not readable_text:
        return jsonify(
            {
                "reply": (
                    "OCR could not read text from this image. Please retake the photo closer to the pesticide label, "
                    "keep the product name and active ingredient in focus, and avoid glare."
                ),
                "details": KB.structured_details(None, []),
                "ocr_text": "",
                "analyzed_text": "",
                "ocr_engines": ocr_result.engines_used,
                "ocr_errors": ocr_result.errors[:5],
                "toxicity_level": "Unreadable image",
                "toxicity_category": "OCR failed",
                "model": "ocr-unreadable",
            }
        ), 422

    extracted = KB.identify_from_ocr(ocr_result.text)
    details = KB.structured_details(extracted["pesticide"], extracted["active_ingredients"], extracted.get("product_guess", ""))
    rag_context = RAG.context(f"{details['pesticide_name']} {readable_text}", top_k=3)
    pesticide_context = json.dumps({**details, "rag_context": rag_context}, ensure_ascii=False, indent=2)

    fallback_reply = format_image_report(details, ocr_result, extracted, language)
    ai_reply = None
    if AI_IMAGE_EXPLANATION or SELECTED_LLM.provider == "grok":
        provider_messages = build_provider_messages(
            user_message="Analyze this pesticide label image using only OCR text.",
            chemical_name="",
            symptoms="",
            rag_context=pesticide_context,
            image_text=readable_text or "No readable text was extracted.",
            language=language,
        )
        ai_reply, _, _ = selected_llm_reply(provider_messages, True, "")
    reply = ai_reply or fallback_reply

    return jsonify(
        {
            "reply": reply,
            "details": details,
            "ocr_text": ocr_result.text,
            "analyzed_text": readable_text,
            "ocr_engines": ocr_result.engines_used,
            "ocr_errors": ocr_result.errors[:5],
            "toxicity_level": extracted["toxicity_level"],
            "toxicity_category": extracted["toxicity_category"],
            "model": f"ocr+rag+{SELECTED_LLM.provider}" if ai_reply else "fast-ocr-rag-fallback",
        }
    )


def format_image_report(details: dict[str, Any], ocr_result, extracted: dict[str, Any], language: str = "en") -> str:
    if language == "kn":
        return (
            f"1. ಪೆಸ್ಟಿಸೈಡ್ ಹೆಸರು: {details['pesticide_name']}\n"
            f"2. Active ingredients: {', '.join(details['active_ingredients']) or 'label text ಬೇಕು'}\n"
            f"3. Toxicity level: {extracted['toxicity_level']}\n"
            f"4. Danger category: {extracted['toxicity_category']}\n"
            f"5. Side effects: {', '.join(details['side_effects']) or 'ಪೆಸ್ಟಿಸೈಡ್ ಹೆಸರು ಸ್ಪಷ್ಟವಾದ ನಂತರ ಮಾತ್ರ ಖಚಿತವಾಗಿ ಹೇಳಬಹುದು'}\n"
            f"6. First aid: {details['first_aid']}\n"
            f"7. Safety precautions: {'; '.join(details['safety_precautions'])}\n"
            f"8. Decontamination: {'; '.join(details['decontamination_steps'])}\n"
            "9. Emergency warning: ಉಸಿರಾಟದ ತೊಂದರೆ, ವಾಂತಿ, ತಲೆ ಸುತ್ತುವುದು, fits, confusion ಅಥವಾ pesticide ನುಂಗಿದರೆ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ. Product label ತೆಗೆದುಕೊಂಡು ಹೋಗಿ.\n"
            f"OCR engines: {', '.join(ocr_result.engines_used) or 'OCR engine ಲಭ್ಯವಿಲ್ಲ'}"
        )
    if language == "hi":
        return (
            f"1. Pesticide नाम: {details['pesticide_name']}\n"
            f"2. Active ingredients: {', '.join(details['active_ingredients']) or 'label text चाहिए'}\n"
            f"3. Toxicity level: {extracted['toxicity_level']}\n"
            f"4. Danger category: {extracted['toxicity_category']}\n"
            f"5. Side effects: {', '.join(details['side_effects']) or 'pesticide name साफ होने के बाद ही बताया जा सकता है'}\n"
            f"6. First aid: {details['first_aid']}\n"
            f"7. Safety precautions: {'; '.join(details['safety_precautions'])}\n"
            f"8. Decontamination: {'; '.join(details['decontamination_steps'])}\n"
            "9. Emergency warning: सांस की दिक्कत, उल्टी, चक्कर, fits, confusion या pesticide निगलने पर तुरंत hospital जाएं. Product label साथ ले जाएं.\n"
            f"OCR engines: {', '.join(ocr_result.engines_used) or 'OCR engine unavailable'}"
        )
    return (
        f"Pesticide/Product Name: {details['pesticide_name']}\n"
        f"Active Ingredients: {', '.join(details['active_ingredients']) or 'Unknown'}\n"
        f"Usage: {details['usage']}\n"
        f"Harmfulness Level: {extracted['toxicity_level']}\n"
        f"Toxicity Category: {extracted['toxicity_category']}\n"
        f"Side Effects: {', '.join(details['side_effects']) or 'Unknown'}\n"
        f"First Aid: {details['first_aid']}\n"
        f"Safety Precautions: {'; '.join(details['safety_precautions'])}\n"
        f"Decontamination Steps: {'; '.join(details['decontamination_steps'])}\n"
        f"Environmental Impact: {details['environmental_impact']}\n"
        f"OCR Engines Used: {', '.join(ocr_result.engines_used) or 'None available'}"
    )


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    user_message = str(payload.get("message", "")).strip()
    chemical_name = str(payload.get("chemical", "")).strip()
    symptoms = str(payload.get("symptoms", "")).strip()
    history = payload.get("history", [])
    requested_language = str(payload.get("language", "auto"))
    language = resolve_language(requested_language, user_message, symptoms)
    prompt_language = "auto" if requested_language == "auto" and language == "en" else language

    if not user_message:
        return jsonify({"reply": "Tell me what happened, the chemical name if known, and the symptoms you are seeing."}), 400

    intent, safety_reply = build_base_reply(user_message, chemical_name, symptoms, language)
    domain_info_reply = build_domain_info_reply(user_message, language)

    if domain_info_reply and intent == "general":
        return jsonify({"reply": domain_info_reply, "model": "agriai-knowledge"})

    if intent in {"greeting", "app_help"}:
        return jsonify({"reply": safety_reply, "model": "agriai-instant"})

    is_safety_intent = intent in {"exposure", "exposure_question", "emergency_help"}
    urgent_safety = is_safety_intent and (
        detect_exposure_route(f"{user_message} {symptoms}") == "ingestion"
        or any(symptom in normalize(f"{user_message} {symptoms}") for symptom in HIGH_RISK_SYMPTOMS)
    )
    if urgent_safety:
        return jsonify({"reply": safety_reply, "model": "agriai-urgent"})

    pesticide = find_pesticide(chemical_name) or find_pesticide_in_text(user_message) or find_chemical_group(user_message)
    pesticide_name = pesticide.get("name", chemical_name or "Unknown") if pesticide else (chemical_name or "Unknown")
    exposure_route = detect_exposure_route(f"{user_message} {symptoms}") or "Unknown"
    rag_context = RAG.context(f"{user_message} {chemical_name} {symptoms}", top_k=4)

    if SELECTED_LLM.provider == "ollama":
        fallback_reply = safety_reply if is_safety_intent else build_general_fallback_reply(user_message, chemical_name, rag_context, language)
        return jsonify({"reply": fallback_reply, "model": "agriai-fast", "provider": "built-in", "rag_context_used": bool(rag_context)})

    if is_safety_intent:
        system_prompt = "You are AgriAI. Give short, medically safe pesticide guidance grounded in retrieved context."
        user_content = SAFETY_RESPONSE_PROMPT.format(
            language=language_name(prompt_language),
            pesticide_name=pesticide_name,
            symptoms=symptoms or ", ".join(extract_symptoms(user_message)) or "Not provided",
            exposure_route=exposure_route,
            rag_context=rag_context or safety_reply,
            user_message=user_message,
        )
    else:
        system_prompt = "You are AgriAI, a concise farmer assistance chatbot."
        user_content = GENERAL_CHAT_PROMPT.format(
            language=language_name(prompt_language),
            rag_context=rag_context or "No specific pesticide context retrieved.",
            user_message=user_message,
        )

    messages = [{"role": "system", "content": system_prompt}]
    if isinstance(history, list):
        for item in history[-8:]:
            role = item.get("role")
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[:1000]})
    messages.append({"role": "user", "content": user_content})
    provider_messages = build_provider_messages(
        user_message=user_message,
        chemical_name=chemical_name,
        symptoms=symptoms,
        rag_context=rag_context,
        image_text="",
        language=prompt_language,
    )

    try:
        if SELECTED_LLM.provider == "grok":
            reply, model_name, provider_name = selected_llm_reply(provider_messages, is_safety_intent, safety_reply)
        else:
            reply = OLLAMA.chat(provider_messages, safety_mode=is_safety_intent)
            model_name = OLLAMA_MODEL
            provider_name = "ollama"
        unsafe_additions = ("eat", "food", "drink water", "induce vomiting", "take medicine")
        if reply and (not is_safety_intent or not any(term in reply.lower() for term in unsafe_additions)):
            return jsonify({"reply": reply, "model": model_name, "provider": provider_name, "rag_context_used": bool(rag_context)})
    except Exception:
        pass

    try:
        reply = CLOUD_CHAT.chat(messages, safety_mode=is_safety_intent)
        unsafe_additions = ("eat", "food", "drink water", "induce vomiting", "take medicine")
        if reply and (not is_safety_intent or not any(term in reply.lower() for term in unsafe_additions)):
            return jsonify({"reply": reply, "model": os.getenv("GITHUB_MODEL", "gpt-4o-mini"), "rag_context_used": bool(rag_context)})
    except Exception:
        pass

    if is_safety_intent:
        return jsonify({"reply": safety_reply, "model": "agriai-fast"})

    return jsonify(
        {
            "reply": build_general_fallback_reply(user_message, chemical_name, rag_context, language),
            "model": "agriai-context-fallback",
        }
    )


@app.post("/api/speech-to-text")
def api_speech_to_text():
    audio = request.files.get("audio")
    language = request.form.get("language", "auto")
    if audio is None:
        return jsonify({"error": "Upload an audio file named audio."}), 400

    text = speech_to_text(audio.read(), language)
    if not text:
        return jsonify({"error": "Speech recognition model is unavailable. Use browser voice input or install/cache Whisper."}), 503
    detected_language = resolve_language(language, text)
    return jsonify({"text": text, "language": detected_language, "model": os.getenv("HF_WHISPER_MODEL", "openai/whisper-tiny")})


@app.post("/api/text-to-speech")
def api_text_to_speech():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    language = resolve_language(str(payload.get("language", "auto")), text)
    if not text:
        return jsonify({"error": "Text is required."}), 400

    audio = text_to_speech_audio(text, language)
    if not audio:
        return jsonify({"error": "Server TTS is unavailable. Browser speech synthesis can still speak replies."}), 503
    return jsonify({"audio_base64": audio["audio_base64"], "mime_type": audio["mime_type"], "language": language})


@app.post("/api/chat-stream")
def api_chat_stream():
    payload = request.get_json(silent=True) or {}
    user_message = str(payload.get("message", "")).strip()
    symptoms = str(payload.get("symptoms", "")).strip()
    chemical_name = str(payload.get("chemical", "")).strip()
    requested_language = str(payload.get("language", "auto"))
    language = resolve_language(requested_language, user_message, symptoms)
    prompt_language = "auto" if requested_language == "auto" and language == "en" else language
    if not user_message:
        return jsonify({"error": "message is required"}), 400

    intent, safety_reply = build_base_reply(user_message, chemical_name, symptoms, language)
    domain_info_reply = build_domain_info_reply(user_message, language)
    is_safety_intent = intent in {"exposure", "exposure_question", "emergency_help"}
    urgent_safety = is_safety_intent and (
        detect_exposure_route(f"{user_message} {symptoms}") == "ingestion"
        or any(symptom in normalize(f"{user_message} {symptoms}") for symptom in HIGH_RISK_SYMPTOMS)
    )

    instant_reply = None
    if domain_info_reply and intent == "general":
        instant_reply = domain_info_reply
    elif intent in {"greeting", "app_help"} or urgent_safety:
        instant_reply = safety_reply

    if instant_reply:
        def instant_generate():
            yield f"data: {json.dumps({'token': instant_reply})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(instant_generate(), mimetype="text/event-stream")

    rag_context = RAG.context(f"{user_message} {chemical_name} {symptoms}", top_k=4)
    pesticide = find_pesticide(chemical_name) or find_pesticide_in_text(user_message) or find_chemical_group(user_message)
    pesticide_name = pesticide.get("name", chemical_name or "Unknown") if pesticide else (chemical_name or "Unknown")

    if SELECTED_LLM.provider == "ollama":
        fast_reply = safety_reply if is_safety_intent else build_general_fallback_reply(user_message, chemical_name, rag_context, language)

        def fast_generate():
            yield f"data: {json.dumps({'token': fast_reply, 'model': 'agriai-fast', 'provider': 'built-in'})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(fast_generate(), mimetype="text/event-stream")

    provider_messages = build_provider_messages(
        user_message=user_message,
        chemical_name=chemical_name,
        symptoms=symptoms,
        rag_context=rag_context,
        image_text="",
        language=prompt_language,
    )

    if is_safety_intent:
        prompt = SAFETY_RESPONSE_PROMPT.format(
            language=language_name(prompt_language),
            pesticide_name=pesticide_name,
            symptoms=symptoms or ", ".join(extract_symptoms(user_message)) or "Not provided",
            exposure_route=detect_exposure_route(f"{user_message} {symptoms}") or "Unknown",
            rag_context=rag_context or safety_reply,
            user_message=user_message,
        )
        system_prompt = "You are AgriAI. Stream concise, medically safe pesticide guidance."
    else:
        prompt = GENERAL_CHAT_PROMPT.format(
            language=language_name(prompt_language),
            rag_context=rag_context or "No specific pesticide context retrieved.",
            user_message=user_message,
        )
        system_prompt = "You are AgriAI, a concise farmer assistance chatbot."

    if SELECTED_LLM.provider == "grok":
        reply, model_name, provider_name = selected_llm_reply(provider_messages, is_safety_intent, safety_reply)

        def grok_generate():
            yield f"data: {json.dumps({'token': reply, 'model': model_name, 'provider': provider_name})}\n\n"
            yield "data: [DONE]\n\n"

        return Response(grok_generate(), mimetype="text/event-stream")

    def generate():
        try:
            with requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "stream": True,
                    "keep_alive": "10m",
                    "options": {"num_predict": 140, "num_ctx": 1400, "temperature": 0.2 if is_safety_intent else 0.55},
                    "messages": provider_messages,
                },
                stream=True,
                timeout=OLLAMA_TIMEOUT,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield f"data: {json.dumps({'token': content})}\n\n"
                    except Exception:
                        continue
        except Exception:
            try:
                cloud_reply = CLOUD_CHAT.chat(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    safety_mode=is_safety_intent,
                )
            except Exception:
                cloud_reply = None
            fallback = cloud_reply or (safety_reply if is_safety_intent else build_general_fallback_reply(user_message, chemical_name, rag_context, language))
            yield f"data: {json.dumps({'token': fallback})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


def warm_ollama_model() -> None:
    OLLAMA.warm()


def warm_ocr_model() -> None:
    try:
        from io import BytesIO
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (420, 120), "white")
        drawer = ImageDraw.Draw(image)
        drawer.text((12, 35), "CHLORPYRIFOS 20 EC", fill="black")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        OCR.analyze(buffer.getvalue())
    except Exception:
        pass


def _language_pack(language: str) -> dict[str, str]:
    packs = {
        "en": {
            "greeting": "Hi, I am AgriAI. Tell me the pesticide name, how it touched you, and what you feel now. I will keep it practical.",
            "need_details": "I need one more detail: pesticide name if you know it, exposure type, and symptoms. Example: 'chlorpyrifos spray touched my skin and I feel dizzy'.",
            "emergency": "This can be urgent. If there is breathing trouble, fainting, seizure, confusion, severe vomiting, eye exposure, or swallowing pesticide, call 112 or go to hospital now. Carry the label.",
        },
        "hi": {
            "greeting": "नमस्ते, मैं AgriAI हूं। कीटनाशक का नाम, संपर्क कैसे हुआ, और अभी क्या महसूस हो रहा है बताइए।",
            "need_details": "मुझे एक जानकारी और चाहिए: कीटनाशक का नाम, संपर्क कैसे हुआ, और लक्षण। जैसे: 'chlorpyrifos त्वचा पर लगा और चक्कर आ रहा है'।",
            "emergency": "यह जरूरी हो सकता है। सांस में दिक्कत, बेहोशी, दौरा, भ्रम, तेज उल्टी, आंख में रसायन या निगलने पर 112 कॉल करें या तुरंत अस्पताल जाएं। लेबल साथ ले जाएं।",
        },
        "kn": {
            "greeting": "ನಮಸ್ಕಾರ, ನಾನು AgriAI. ಕೀಟನಾಶಕದ ಹೆಸರು, ಅದು ಹೇಗೆ ತಗುಲಿತು, ಮತ್ತು ಈಗ ನಿಮಗೆ ಏನು ಅನಿಸುತ್ತಿದೆ ಎಂದು ಹೇಳಿ.",
            "need_details": "ನನಗೆ ಇನ್ನೊಂದು ವಿವರ ಬೇಕು: ಕೀಟನಾಶಕದ ಹೆಸರು, ಸಂಪರ್ಕ ಹೇಗೆ ಆಯಿತು, ಮತ್ತು ಲಕ್ಷಣಗಳು. ಉದಾ: 'chlorpyrifos ಚರ್ಮಕ್ಕೆ ತಗುಲಿತು ಮತ್ತು ತಲೆ ಸುತ್ತುತ್ತಿದೆ'.",
            "emergency": "ಇದು ತುರ್ತು ಆಗಿರಬಹುದು. ಉಸಿರಾಟ ತೊಂದರೆ, ಮೂರ್ಛೆ, ಫಿಟ್ಸ್, ಗೊಂದಲ, ತೀವ್ರ ವಾಂತಿ, ಕಣ್ಣಿಗೆ ರಾಸಾಯನಿಕ ಅಥವಾ ನುಂಗಿದರೆ 112 ಕರೆ ಮಾಡಿ ಅಥವಾ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ. ಲೇಬಲ್ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ.",
        },
    }
    return packs.get(language, packs["en"])


def translate_builtin_reply(reply: str, language: str) -> str:
    if language == "hi":
        return (
            "कीटनाशक ऐसा रासायनिक या प्राकृतिक पदार्थ है जो कीड़े, खरपतवार, फफूंद या चूहों जैसे कीटों को नियंत्रित करता है। "
            "यह फसल बचाता है, लेकिन त्वचा, आंख, सांस या निगलने से नुकसान कर सकता है। छिड़काव के बाद PPE पहनें, साबुन-पानी से सफाई करें, और लक्षण हों तो डॉक्टर से मदद लें।"
        )
    if language == "kn":
        return (
            "ಕೀಟನಾಶಕ ಎಂದರೆ ಕೀಟ, ಕಳೆ, ಫಂಗಸ್ ಅಥವಾ ಇಲಿ ಮುಂತಾದವುಗಳನ್ನು ನಿಯಂತ್ರಿಸಲು ಬಳಸುವ ರಾಸಾಯನಿಕ ಅಥವಾ ನೈಸರ್ಗಿಕ ಪದಾರ್ಥ. "
            "ಇದು ಬೆಳೆಗಳನ್ನು ರಕ್ಷಿಸುತ್ತದೆ, ಆದರೆ ಚರ್ಮ, ಕಣ್ಣು, ಉಸಿರಾಟ ಅಥವಾ ನುಂಗುವ ಮೂಲಕ ದೇಹಕ್ಕೆ ಹಾನಿ ಮಾಡಬಹುದು. ಸಿಂಪಡಿಸಿದ ನಂತರ PPE ಬಳಸಿ, ಸಾಬೂನು-ನೀರಿನಿಂದ ತೊಳೆಯಿರಿ, ಮತ್ತು ಲಕ್ಷಣಗಳಿದ್ದರೆ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ."
        )
    return reply


def build_domain_info_reply(user_message: str, language: str = "en") -> str | None:
    clean_message = normalize(user_message)
    if any(phrase in clean_message for phrase in ("what is pesticide", "what are pesticides", "define pesticide", "pesticide meaning")):
        return translate_builtin_reply(
            "A pesticide is a chemical or natural substance used to control pests such as insects, weeds, fungi, or rodents. Farmers use pesticides to protect crops, but some pesticides can harm people if they touch the skin, get into the eyes, are breathed in, or are swallowed. That is why workers should use protective gear, wash properly after spraying, and get medical help quickly if symptoms appear.",
            language,
        )
    if "organophosphate" in clean_message and not detect_exposure_route(clean_message):
        if language == "hi":
            return "Organophosphates कीटनाशकों का एक समूह है जो nervous system को प्रभावित कर सकता है। संपर्क के बाद सिरदर्द, उल्टी, पसीना, लार, छोटी पुतलियां, मांसपेशी फड़कना या सांस की दिक्कत हो सकती है। निगलने या ज्यादा exposure में तुरंत अस्पताल जाएं।"
        if language == "kn":
            return "Organophosphates ನರಮಂಡಲದ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರುವ ಕೀಟನಾಶಕಗಳ ಗುಂಪು. ಸಂಪರ್ಕವಾದ ನಂತರ ತಲೆನೋವು, ವಾಂತಿ, ಬೆವರು, ಲಾಲೆ, ಸಣ್ಣ ಕಣ್ಣುಮಣಿ, ಮಾಂಸಖಂಡ ಫಡಕುವುದು ಅಥವಾ ಉಸಿರಾಟ ತೊಂದರೆ ಕಾಣಬಹುದು. ನುಂಗಿದರೆ ಅಥವಾ ಹೆಚ್ಚು exposure ಇದ್ದರೆ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."
        return "Organophosphates are insecticides that can affect the nervous system. Exposure may cause headache, vomiting, sweating, salivation, pinpoint pupils, muscle twitching, or breathing trouble. Swallowing or heavy exposure needs urgent hospital care."
    if "safe return" in clean_message or "this project" in clean_message or "agriai" in clean_message:
        if language == "hi":
            return "AgriAI किसानों और spray workers के लिए pesticide safety assistant है। यह label photo analyze करता है, chemical पहचानता है, symptoms समझता है, RAG से safety जानकारी लाता है, और English/Hindi/Kannada में practical guidance देता है।"
        if language == "kn":
            return "AgriAI ರೈತರು ಮತ್ತು spray workers ಗಾಗಿ pesticide safety assistant. ಇದು label photo ವಿಶ್ಲೇಷಿಸುತ್ತದೆ, chemical ಗುರುತಿಸುತ್ತದೆ, symptoms ಅರ್ಥಮಾಡಿಕೊಳ್ಳುತ್ತದೆ, RAG ಮೂಲಕ safety ಮಾಹಿತಿ ತರುತ್ತದೆ, ಮತ್ತು English/Hindi/Kannada ನಲ್ಲಿ practical guidance ನೀಡುತ್ತದೆ."
        return "AgriAI is a pesticide safety assistant for farmers and spray workers. It analyzes label photos, identifies chemicals, checks symptoms, retrieves safety knowledge with RAG, and gives practical guidance in English, Hindi, and Kannada."
    return None


def localized_reply(intent: str, reply: str, language: str) -> str:
    pack = _language_pack(language)
    if intent == "greeting":
        return pack["greeting"]
    if intent in {"app_help", "exposure_question", "general"}:
        return pack["need_details"] if intent == "exposure_question" else reply
    if intent == "emergency_help":
        return pack["emergency"]
    return reply


def localized_safety_reply(user_message: str, chemical_name: str, symptoms_text: str, language: str) -> str | None:
    if language == "en":
        return None
    pesticide = find_pesticide(chemical_name) if chemical_name else None
    pesticide = pesticide or find_pesticide_in_text(user_message) or find_chemical_group(f"{user_message} {chemical_name}")
    name = pesticide.get("name", chemical_name or "Unknown pesticide") if pesticide else (chemical_name or "Unknown pesticide")
    danger = pesticide.get("danger_level", "Unknown") if pesticide else "Unknown"
    symptoms = ", ".join(extract_symptoms(f"{user_message} {symptoms_text}")) or "not clearly provided"
    route = detect_exposure_route(f"{user_message} {symptoms_text}") or "unknown"
    if language == "hi":
        return (
            f"1. कीटनाशक: {name}\n"
            f"2. खतरा स्तर: {danger}\n"
            f"3. लक्षण: {symptoms}\n"
            f"4. संपर्क: {route}\n"
            "5. अभी करें: स्प्रे क्षेत्र से दूर जाएं, ताजी हवा में रहें, दूषित कपड़े अलग करें।\n"
            "6. सफाई: त्वचा और बालों को साबुन और बहते पानी से धोएं। आंख में गया हो तो 15 मिनट पानी से धोएं।\n"
            "7. डॉक्टर: लक्षण बढ़ें, उल्टी/चक्कर/सांस की दिक्कत हो, या निगला हो तो तुरंत अस्पताल जाएं।"
        )
    if language == "kn":
        return (
            f"1. ಕೀಟನಾಶಕ: {name}\n"
            f"2. ಅಪಾಯ ಮಟ್ಟ: {danger}\n"
            f"3. ಲಕ್ಷಣಗಳು: {symptoms}\n"
            f"4. ಸಂಪರ್ಕ: {route}\n"
            "5. ಈಗ ಮಾಡಿ: ಸ್ಪ್ರೇ ಪ್ರದೇಶದಿಂದ ದೂರ ಹೋಗಿ, ತಾಜಾ ಗಾಳಿಯಲ್ಲಿ ಇರಿ, ಕಲುಷಿತ ಬಟ್ಟೆಗಳನ್ನು ಬೇರ್ಪಡಿಸಿ.\n"
            "6. ಸ್ವಚ್ಛತೆ: ಚರ್ಮ ಮತ್ತು ಕೂದಲನ್ನು ಸಾಬೂನು ಮತ್ತು ಹರಿಯುವ ನೀರಿನಿಂದ ತೊಳೆಯಿರಿ. ಕಣ್ಣಿಗೆ ಹೋದರೆ 15 ನಿಮಿಷ ನೀರಿನಿಂದ ತೊಳೆಯಿರಿ.\n"
            "7. ವೈದ್ಯರು: ಲಕ್ಷಣಗಳು ಹೆಚ್ಚಾದರೆ, ವಾಂತಿ/ತಲೆಸುತ್ತು/ಉಸಿರಾಟ ತೊಂದರೆ ಇದ್ದರೆ, ಅಥವಾ ನುಂಗಿದ್ದರೆ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."
        )
    return None


def build_general_fallback_reply(user_message: str, chemical_name: str, rag_context: str, language: str = "en") -> str:
    pesticide = find_pesticide(chemical_name) or find_pesticide_in_text(user_message) or find_chemical_group(user_message)
    if pesticide:
        details = KB.structured_details(pesticide, [])
        reply = (
            f"{pesticide.get('name')} is a {pesticide.get('category', 'pesticide')}. "
            f"Danger level: {pesticide.get('danger_level', 'Unknown')}. "
            f"Possible symptoms include {', '.join(pesticide.get('symptoms', [])) or 'irritation or poisoning symptoms'}. "
            f"First aid: {pesticide.get('first_aid', 'Stop exposure, wash exposed areas, and seek medical advice if symptoms appear.')} "
            f"Precautions: {'; '.join(details.get('safety_precautions', []))}"
        )
    elif rag_context:
        reply = "Here is the relevant pesticide-safety guidance I found: " + " ".join(rag_context.split())[:650]
    else:
        if language == "hi":
            return (
                f"मैंने आपका सवाल समझा: '{user_message}'। मैं pesticide और farm-chemical safety में सबसे अच्छा मदद कर सकता हूं। "
                "उत्पाद का नाम, label text, या क्या हुआ यह बताइए। उदाहरण: 'chlorpyrifos spray के बाद चक्कर आ रहा है'।"
            )
        if language == "kn":
            return (
                f"ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಅರ್ಥವಾಗಿದೆ: '{user_message}'. ನಾನು pesticide ಮತ್ತು farm-chemical safety ಬಗ್ಗೆ ಹೆಚ್ಚು ಚೆನ್ನಾಗಿ ಸಹಾಯ ಮಾಡಬಹುದು. "
                "ಉತ್ಪನ್ನದ ಹೆಸರು, label text, ಅಥವಾ ಏನಾಯಿತು ಎಂದು ಹೇಳಿ. ಉದಾ: 'chlorpyrifos spray ಮಾಡಿದ ನಂತರ ತಲೆ ಸುತ್ತುತ್ತಿದೆ'."
            )
        reply = (
            f"I understand your question: '{user_message}'. I am strongest with pesticide and farm-chemical safety, so I can help best if you tell me the product name, label text, or what happened. "
            "You can ask normally, for example: 'I feel dizzy after spraying chlorpyrifos' or 'What precautions should I take for paraquat?'"
        )
    if language == "hi":
        return "मैंने आपकी बात समझी। " + reply + " गंभीर लक्षण हों तो अस्पताल जाएं या 1800-116-117 पर कॉल करें।"
    if language == "kn":
        return "ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಅರ್ಥವಾಗಿದೆ. " + reply + " ಗಂಭೀರ ಲಕ್ಷಣಗಳಿದ್ದರೆ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ ಅಥವಾ 1800-116-117 ಗೆ ಕರೆ ಮಾಡಿ."
    return reply


def format_image_report(details: dict[str, Any], ocr_result, extracted: dict[str, Any], language: str = "en") -> str:
    name = details.get("pesticide_name", "Not detected from image")
    active = ", ".join(details.get("active_ingredients", [])) or "Unknown"
    danger = extracted.get("toxicity_level") or details.get("harmfulness_level", "Unknown")
    category = extracted.get("toxicity_category") or details.get("toxicity_category", "Unknown")
    side_effects = ", ".join(details.get("side_effects", [])) or "Unknown"
    note = "" if ocr_result.text else "\nNote: OCR could not read the image clearly. Type the visible label text or pesticide name for better accuracy."
    first_aid = details.get("first_aid") or "Move away from exposure, remove contaminated clothing, wash exposed skin, and contact a doctor if symptoms appear."
    precautions = "; ".join(details.get("safety_precautions", [])) or "Wear gloves, mask, goggles, long sleeves, and avoid inhaling spray mist."
    decontamination = "; ".join(details.get("decontamination_steps", [])) or "Wash exposed skin with soap and running water."
    hospital = "Visit hospital urgently for breathing trouble, fainting, severe vomiting, eye exposure, confusion, fits, or if pesticide was swallowed."
    return (
        f"1. Identified pesticide/chemical: {name} (active ingredient: {active})\n"
        f"2. Danger level: {danger}; category: {category}\n"
        f"3. Side effects: {side_effects}\n"
        f"4. First aid: {first_aid}\n"
        f"5. Safety precautions: {precautions} Decontamination: {decontamination}\n"
        f"6. When to visit hospital: {hospital}"
        f"{note}"
    )
    if language == "hi":
        return (
            f"1. कीटनाशक पहचान: {name}\n2. सक्रिय घटक: {active}\n3. खतरा स्तर: {danger}\n"
            f"4. विष श्रेणी: {category}\n5. दुष्प्रभाव: {side_effects}\n6. प्राथमिक उपचार: {details.get('first_aid')}\n"
            f"7. सुरक्षा: {'; '.join(details.get('safety_precautions', []))}\n8. सफाई: {'; '.join(details.get('decontamination_steps', []))}\n"
            "9. आपात सलाह: सांस की दिक्कत, बेहोशी, तेज उल्टी, आंख में रसायन या निगलने पर तुरंत अस्पताल जाएं."
            f"{note}"
        )
    if language == "kn":
        return (
            f"1. ಕೀಟನಾಶಕ ಗುರುತು: {name}\n2. ಸಕ್ರಿಯ ಪದಾರ್ಥಗಳು: {active}\n3. ಅಪಾಯ ಮಟ್ಟ: {danger}\n"
            f"4. ವಿಷ ವರ್ಗ: {category}\n5. ದುಷ್ಪರಿಣಾಮಗಳು: {side_effects}\n6. ಮೊದಲ ನೆರವು: {details.get('first_aid')}\n"
            f"7. ಸುರಕ್ಷತೆ: {'; '.join(details.get('safety_precautions', []))}\n8. ಸ್ವಚ್ಛತೆ: {'; '.join(details.get('decontamination_steps', []))}\n"
            "9. ತುರ್ತು ಸಲಹೆ: ಉಸಿರಾಟ ತೊಂದರೆ, ಮೂರ್ಛೆ, ತೀವ್ರ ವಾಂತಿ, ಕಣ್ಣಿಗೆ ರಾಸಾಯನಿಕ ಅಥವಾ ನುಂಗಿದರೆ ತಕ್ಷಣ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ."
            f"{note}"
        )
    return (
        f"1. Pesticide Identification: {name}\n"
        f"2. Active Ingredients: {active}\n"
        f"3. Danger Level: {danger}\n"
        f"4. Toxicity Category: {category}\n"
        f"5. Side Effects: {side_effects}\n"
        f"6. First Aid: {details.get('first_aid')}\n"
        f"7. Safety Tips: {'; '.join(details.get('safety_precautions', []))}\n"
        f"8. Decontamination: {'; '.join(details.get('decontamination_steps', []))}\n"
        f"9. Environmental Impact: {details.get('environmental_impact')}\n"
        "10. Emergency Recommendation: Go to hospital for breathing trouble, fainting, severe vomiting, eye exposure, or swallowing pesticide."
        f"{note}"
    )


if __name__ == "__main__":
    if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
