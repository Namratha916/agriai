from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class GitHubModelsClient:
    model: str = os.getenv("GITHUB_MODEL", "gpt-4o-mini")
    endpoint: str = os.getenv("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")

    def chat(self, messages: list[dict[str, str]], safety_mode: bool = False) -> str | None:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return None
        try:
            from azure.ai.inference import ChatCompletionsClient
            from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
            from azure.core.credentials import AzureKeyCredential

            converted = []
            for item in messages:
                role = item.get("role", "user")
                content = item.get("content", "")
                if role == "system":
                    converted.append(SystemMessage(content=content))
                elif role == "assistant":
                    converted.append(AssistantMessage(content=content))
                else:
                    converted.append(UserMessage(content=content))

            client = ChatCompletionsClient(endpoint=self.endpoint, credential=AzureKeyCredential(token))
            response = client.complete(
                messages=converted,
                temperature=0.25 if safety_mode else 0.65,
                top_p=0.9,
                max_tokens=420 if safety_mode else 700,
                model_extras={"model": self.model},
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return None
