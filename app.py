from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "pesticides.json"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "90"))

app = Flask(__name__)


def load_pesticides() -> list[dict[str, Any]]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


PESTICIDES = load_pesticides()
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
    if any(word in clean_text for word in ("swallow", "swallowed", "drink", "drank", "ingest", "ingested", "ate")):
        return "ingestion"
    if any(word in clean_text for word in ("eye", "eyes", "splash")):
        return "eye"
    if any(word in clean_text for word in ("breathe", "breathing", "inhale", "inhaled", "smell", "spray mist")):
        return "inhalation"
    if any(word in clean_text for word in ("skin", "hand", "hands", "clothes", "body", "touch", "touched")):
        return "skin"
    return None


def classify_chat_intent(user_message: str, chemical_name: str = "", symptoms_text: str = "") -> str:
    clean_message = normalize(user_message)
    combined = normalize(f"{user_message} {chemical_name} {symptoms_text}")

    greetings = {"hi", "hello", "hey", "namaste", "good morning", "good evening", "good afternoon"}
    if clean_message in greetings:
        return "greeting"

    info_question_starts = (
        "what is",
        "what are",
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
    if clean_message.startswith(info_question_starts) and not any(word in combined for word in exposure_story_words):
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


def build_base_reply(user_message: str, chemical_name: str = "", symptoms_text: str = "") -> tuple[str, str]:
    intent = classify_chat_intent(user_message, chemical_name, symptoms_text)

    if intent == "greeting":
        return (
            intent,
            "Hi, I am Safe Return. Tell me the chemical name, how it touched you, and any symptoms. For example: 'I sprayed chlorpyrifos and feel dizzy.' I will guide you step by step.",
        )

    if intent == "emergency_help":
        return (
            intent,
            "If the person has breathing trouble, fainting, seizures, confusion, chest pain, severe vomiting, or chemical in the eyes, go to the nearest hospital now or call emergency services. In India, you can also call poison helpline 1800-116-117. Carry the chemical bottle or label.",
        )

    if intent == "app_help":
        return (
            intent,
            "You can use Safe Return in three quick steps: enter the chemical name, select symptoms, and follow the decontamination checklist. If symptoms are serious, use the emergency alert and hospital finder instead of waiting for the chatbot.",
        )

    if intent == "exposure_question" and not find_pesticide(chemical_name) and not find_pesticide_in_text(user_message) and not extract_symptoms(f"{user_message} {symptoms_text}"):
        return (
            intent,
            "Please tell me the chemical name from the label and what happened: skin contact, eye splash, breathing spray, or swallowing. Also tell me symptoms such as dizziness, vomiting, headache, sweating, eye burning, or breathing difficulty.",
        )

    if intent == "general":
        return (
            intent,
            "I can help with pesticide exposure, symptoms, first aid, decontamination steps, emergency messages, and hospital guidance. Tell me what happened in one sentence and include the chemical name if you know it.",
        )

    return intent, build_safety_reply(user_message, chemical_name, symptoms_text)


def build_domain_info_reply(user_message: str) -> str | None:
    clean_message = normalize(user_message)
    if "what is pesticide" in clean_message or "what are pesticides" in clean_message or "define pesticide" in clean_message:
        return (
            "A pesticide is a chemical or natural substance used to control pests such as insects, weeds, fungi, or rodents. "
            "Farmers use pesticides to protect crops, but some pesticides can harm people if they touch the skin, get into the eyes, are breathed in, or are swallowed. "
            "That is why workers should use protective gear, wash properly after spraying, and get medical help quickly if symptoms appear."
        )

    if "safe return" in clean_message or "this project" in clean_message:
        return (
            "Safe Return is a chemical decontamination alert and guide system for farmers and spray workers. "
            "It helps users identify a chemical, check symptoms, follow decontamination steps, create an emergency alert, find nearby medical help, and chat with an assistant for guidance."
        )

    if "washing" in clean_message and "spray" in clean_message:
        return (
            "Washing after spraying pesticide is important because it removes chemical residue from your skin and hair before it can keep absorbing into the body. "
            "It also prevents carrying pesticide into the home, where it could touch children, family members, food, bedding, or other clothes. "
            "After spraying, remove contaminated clothing, wash exposed skin with soap and running water, and keep work clothes separate from family laundry."
        )

    if "organophosphate" in clean_message and not detect_exposure_route(clean_message):
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
    return render_template("index.html", pesticides=PESTICIDES)


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


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    user_message = str(payload.get("message", "")).strip()
    chemical_name = str(payload.get("chemical", "")).strip()
    symptoms = str(payload.get("symptoms", "")).strip()
    history = payload.get("history", [])

    if not user_message:
        return jsonify({"reply": "Tell me what happened, the chemical name if known, and the symptoms you are seeing."}), 400

    intent, safety_reply = build_base_reply(user_message, chemical_name, symptoms)
    domain_info_reply = build_domain_info_reply(user_message)

    if domain_info_reply and intent == "general":
        return jsonify({"reply": domain_info_reply, "model": "safe-return-knowledge"})

    if intent in {"greeting", "app_help"}:
        return jsonify({"reply": safety_reply, "model": "safe-return-instant"})

    is_safety_intent = intent in {"exposure", "exposure_question", "emergency_help"}
    urgent_safety = is_safety_intent and (
        detect_exposure_route(f"{user_message} {symptoms}") == "ingestion"
        or any(symptom in normalize(f"{user_message} {symptoms}") for symptom in HIGH_RISK_SYMPTOMS)
    )
    if urgent_safety:
        return jsonify({"reply": safety_reply, "model": "safe-return-urgent"})

    ollama_options = {
        "num_predict": 110 if is_safety_intent else 180,
        "num_ctx": 1400,
        "temperature": 0.2 if is_safety_intent else 0.7,
        "top_p": 0.85,
    }
    if is_safety_intent:
        system_prompt = (
            "You are Safe Return, a ChatGPT-like assistant for farmers and chemical workers. "
            "Reply naturally and directly. The user may be in danger, so use the provided safety guidance as the source of truth. "
            "Do not add unsafe medical instructions. Never tell the user to eat, drink, induce vomiting, or take medicine. "
            "Keep hospital and poison-control advice when present. Ask one useful follow-up question only if needed."
        )
        user_content = (
            f"User message: {user_message}\n"
            f"Detected intent: {intent}\n"
            f"Safe guidance you must preserve: {safety_reply}"
        )
    else:
        system_prompt = (
            "You are Safe Return, a friendly ChatGPT-like assistant. "
            "You can answer general questions, explain this project, help with code, and chat normally. "
            "If the user asks about pesticide or chemical exposure, switch to urgent safety guidance. "
            "Use simple English and be helpful, natural, and concise."
        )
        user_content = user_message

    messages = [{"role": "system", "content": system_prompt}]
    if isinstance(history, list):
        for item in history[-8:]:
            role = item.get("role")
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[:1000]})
    messages.append({"role": "user", "content": user_content})

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "keep_alive": "10m",
                "options": ollama_options,
                "messages": messages,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        reply = data.get("message", {}).get("content", "").strip()
        unsafe_additions = ("eat", "food", "drink water", "induce vomiting", "take medicine")
        if reply and (not is_safety_intent or not any(term in reply.lower() for term in unsafe_additions)):
            return jsonify({"reply": reply, "model": OLLAMA_MODEL})
    except requests.RequestException:
        pass

    if is_safety_intent:
        return jsonify({"reply": safety_reply, "model": "safe-return-fast"})

    return jsonify(
        {
            "reply": (
                "I could not get a generated answer from the local Ollama model in time. "
                "Please make sure Ollama is open, then try again. I will still answer pesticide safety and project questions immediately."
            ),
            "model": "ollama-timeout",
        }
    )


def warm_ollama_model() -> None:
    try:
        requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "keep_alive": "10m",
                "options": {"num_predict": 8, "num_ctx": 512},
                "messages": [{"role": "user", "content": "Say ready."}],
            },
            timeout=60,
        )
    except requests.RequestException:
        pass


if __name__ == "__main__":
    threading.Thread(target=warm_ollama_model, daemon=True).start()
    app.run(debug=True)
