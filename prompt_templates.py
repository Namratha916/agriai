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
        "Reply in {language}. Keep the answer short, medically safe, and structured.\n\n"
        "Use the retrieved pesticide context as ground truth. Do not invent dosage, antidotes, or home remedies.\n"
        "Never say to eat, drink, induce vomiting, or take medicine unless a doctor/poison-control expert says so.\n\n"
        "Provide:\n"
        "1. Danger Level\n"
        "2. Immediate Action\n"
        "3. First Aid\n"
        "4. Decontamination Steps\n"
        "5. Hospital Recommendation\n\n"
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
        "You are AgriAI. Reply in {language}. A pesticide label image was processed with OCR.\n"
        "Create a precise safety report using the extracted details.\n\n"
        "OCR Text:\n{ocr_text}\n\n"
        "Matched Pesticide Data:\n{pesticide_context}\n\n"
        "Provide:\n"
        "- Pesticide/Product Name\n"
        "- Active Ingredients\n"
        "- Usage\n"
        "- Harmfulness Level\n"
        "- Toxicity Category\n"
        "- Side Effects\n"
        "- First Aid\n"
        "- Safety Precautions\n"
        "- Decontamination Steps\n"
        "- Environmental Impact\n"
    ),
    input_variables=["language", "ocr_text", "pesticide_context"],
)


def language_name(language: str) -> str:
    return LANGUAGE_NAMES.get(language, LANGUAGE_NAMES["auto"])
