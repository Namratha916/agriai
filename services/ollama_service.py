from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class OllamaClient:
    url: str
    model: str
    timeout: int
    cache_ttl: int = 600
    cache: dict[str, tuple[float, str]] = field(default_factory=dict)

    def chat(self, messages: list[dict[str, str]], safety_mode: bool = False) -> str | None:
        key = self._cache_key(messages, safety_mode)
        cached = self.cache.get(key)
        now = time.time()
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "num_predict": 120 if safety_mode else 180,
                "num_ctx": 1400,
                "temperature": 0.15 if safety_mode else 0.55,
                "top_p": 0.85,
            },
            "messages": messages,
        }
        try:
            response = requests.post(self.url, json=payload, timeout=(1.0, min(self.timeout, 3)))
            response.raise_for_status()
            reply = response.json().get("message", {}).get("content", "").strip()
            if reply:
                self.cache[key] = (now, reply)
            return reply or None
        except requests.RequestException:
            return None

    def warm(self) -> None:
        self.chat([{"role": "user", "content": "Say ready."}], safety_mode=False)

    def _cache_key(self, messages: list[dict[str, str]], safety_mode: bool) -> str:
        raw = json.dumps({"messages": messages, "safety": safety_mode, "model": self.model}, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
