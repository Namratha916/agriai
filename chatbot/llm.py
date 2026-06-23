from __future__ import annotations

from dataclasses import dataclass

import requests


AGRI_PROMPT_TEMPLATE = """You are PestiSafe AI, a pesticide safety Generative AI assistant.
Reply in the selected language: {language}.
Use the given pesticide context.
If image text is provided, identify pesticide or chemical name.
Give short, clear, farmer-friendly answer.

Context:
{context}

Image text:
{image_text}

User question:
{question}

Answer format:
1. Identified pesticide/chemical
2. Danger level
3. Side effects
4. First aid
5. Safety precautions
6. When to visit hospital
"""


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str


@dataclass
class ModelConfig:
    provider: str
    ollama_base_url: str
    ollama_model: str
    xai_api_key: str
    grok_model: str
    timeout: float = 12


def build_agriai_prompt(language: str, context: str, image_text: str, question: str) -> str:
    return AGRI_PROMPT_TEMPLATE.format(
        language=language,
        context=context or "No pesticide context retrieved.",
        image_text=image_text or "No image text provided.",
        question=question,
    )


class AgriAILLM:
    def __init__(self, config: ModelConfig):
        self.config = config

    @property
    def provider(self) -> str:
        provider = (self.config.provider or "ollama").lower().strip()
        return provider if provider in {"ollama", "grok"} else "ollama"

    @property
    def active_model(self) -> str:
        if self.provider == "grok":
            return self.config.grok_model
        return self.config.ollama_model

    def is_configured(self) -> bool:
        if self.provider == "grok":
            return bool(self.config.xai_api_key)
        return True

    def chat(self, messages: list[dict[str, str]], safety_mode: bool = False) -> LLMResult | None:
        if self.provider == "grok":
            return self._chat_grok(messages, safety_mode)
        return self._chat_ollama(messages, safety_mode)

    def _chat_ollama(self, messages: list[dict[str, str]], safety_mode: bool) -> LLMResult | None:
        url = f"{self.config.ollama_base_url.rstrip('/')}/api/chat"
        response = requests.post(
            url,
            json={
                "model": self.config.ollama_model,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "num_predict": 160 if safety_mode else 240,
                    "num_ctx": 1800,
                    "temperature": 0.15 if safety_mode else 0.45,
                    "top_p": 0.85,
                },
                "messages": messages,
            },
            timeout=(1.5, self.config.timeout),
        )
        response.raise_for_status()
        text = response.json().get("message", {}).get("content", "").strip()
        if not text:
            return None
        return LLMResult(text=text, model=self.config.ollama_model, provider="ollama")

    def _chat_grok(self, messages: list[dict[str, str]], safety_mode: bool) -> LLMResult | None:
        if not self.config.xai_api_key:
            return None

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.xai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.grok_model,
                "messages": messages,
                "temperature": 0.15 if safety_mode else 0.45,
                "max_tokens": 600,
            },
            timeout=(1.5, self.config.timeout),
        )
        response.raise_for_status()
        choices = response.json().get("choices") or []
        text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
        if not text:
            return None
        return LLMResult(text=text, model=self.config.grok_model, provider="grok")
