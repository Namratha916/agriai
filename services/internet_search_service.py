from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import os
import re
import time
from urllib.parse import quote_plus

import requests


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str


class InternetSearchService:
    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.enabled = os.getenv("AGRIAI_ENABLE_WEB_SEARCH", "1") == "1"
        self._cache: dict[str, tuple[float, list[SearchResult]]] = {}

    def pesticide_context(self, query: str, limit: int = 3) -> str:
        query = " ".join((query or "").split())
        if not self.enabled or len(query) < 3:
            return ""

        results = self.search(f"{query} pesticide active ingredient safety first aid toxicity label", limit=limit)
        if not results:
            return ""

        chunks = []
        for item in results[:limit]:
            line = f"{item.title}. {item.snippet}".strip()
            if item.url:
                line = f"{line} Source: {item.url}"
            chunks.append(line[:700])
        return "\n".join(chunks)

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        cache_key = query.lower()
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < 3600:
            return cached[1][:limit]

        results = self._duckduckgo_html(query, limit)
        self._cache[cache_key] = (time.time(), results)
        return results[:limit]

    def _duckduckgo_html(self, query: str, limit: int) -> list[SearchResult]:
        try:
            response = requests.get(
                f"https://duckduckgo.com/html/?q={quote_plus(query)}",
                headers={"User-Agent": "PestiSafeAI/1.0 pesticide safety assistant"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            html = response.text
        except Exception:
            return []

        results: list[SearchResult] = []
        blocks = re.findall(r'<a rel="nofollow" class="result__a" href="(?P<url>.*?)".*?>(?P<title>.*?)</a>.*?<a class="result__snippet".*?>(?P<snippet>.*?)</a>', html, flags=re.S)
        for block in blocks:
            title = clean_html(block[1])
            snippet = clean_html(block[2])
            url = unescape(block[0])
            if title and snippet:
                results.append(SearchResult(title=title, snippet=snippet, url=url))
            if len(results) >= limit:
                break
        return results


def clean_html(value: str) -> str:
    value = re.sub(r"<.*?>", " ", value or "")
    value = unescape(value)
    return " ".join(value.split())
