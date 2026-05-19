from __future__ import annotations

try:
    from langchain_core.prompts import PromptTemplate
except Exception:
    PromptTemplate = None


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "auto": "the same language as the user",
}


class SimplePromptTemplate:
    def __init__(self, template: str):
        self.template = template

    def format(self, **kwargs: str) -> str:
        return self.template.format(**kwargs)


def make_prompt(template: str, input_variables: list[str]):
    if PromptTemplate is None:
        return SimplePromptTemplate(template)
    return PromptTemplate(input_variables=input_variables, template=template)


SAFETY_RESPONSE_PROMPT = make_prompt(
    template=(
        "You are AgriAI, an AI pesticide safety assistant.\n"
        "Respond ONLY in: {language}\n"
        "Keep the answer short, medically safe, precise, and structured.\n\n"
        "Use the retrieved pesticide context as ground truth. Do not invent dosage, antidotes, or home remedies.\n"
        "Never say to eat, drink, induce vomiting, or take medicine unless a doctor/poison-control expert says so.\n\n"
        "Provide:\n"
        "1. Pesticide Name\n"
        "2. Danger Level\n"
        "3. Side Effects\n"
        "4. Immediate Safety Steps\n"
        "5. Decontamination Steps\n"
        "6. Hospital Recommendation\n\n"
        "Detected Pesticide: {pesticide_name}\n"
        "Detected Symptoms: {symptoms}\n"
        "Exposure Route: {exposure_route}\n"
        "Retrieved Context:\n{rag_context}\n\n"
        "User Question: {user_message}\n"
    ),
    input_variables=[
        "language",
        "pesticide_name",
        "symptoms",
        "exposure_route",
        "rag_context",
        "user_message",
    ],
)


GENERAL_CHAT_PROMPT = make_prompt(
    template=(
        "You are AgriAI, a farmer assistance chatbot. Reply in {language}.\n"
        "Be concise and practical. If the user asks about pesticide exposure, tell them to use the safety flow.\n\n"
        "Relevant Context:\n{rag_context}\n\n"
        "User Question: {user_message}\n"
    ),
    input_variables=["language", "rag_context", "user_message"],
)


IMAGE_ANALYSIS_PROMPT = make_prompt(
    template=(
        "You are AgriAI, an AI pesticide safety assistant.\n"
        "Respond ONLY in: {language}\n"
        "Create a short precise safety report using only the OCR/database details.\n\n"
        "OCR Text:\n{ocr_text}\n\n"
        "Matched Pesticide Data:\n{pesticide_context}\n\n"
        "Provide:\n"
        "1. Pesticide Name\n"
        "2. Active Ingredients\n"
        "3. Toxicity Level\n"
        "4. Danger Category\n"
        "5. Side Effects\n"
        "6. Safety Precautions\n"
        "7. Decontamination Steps\n"
        "8. Emergency Warning\n"
    ),
    input_variables=["language", "ocr_text", "pesticide_context"],
)


def language_name(language: str) -> str:
    return LANGUAGE_NAMES.get(language, LANGUAGE_NAMES["auto"])
