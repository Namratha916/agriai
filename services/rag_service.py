from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", (text or "").lower()))


class RAGService:
    def __init__(self, data_path: Path, docs_dir: Path, persist_dir: Path):
        self.data_path = data_path
        self.docs_dir = docs_dir
        self.persist_dir = persist_dir
        self.documents = self._load_seed_documents()
        self._chroma = None
        self._init_chroma()

    def _load_seed_documents(self) -> list[dict[str, Any]]:
        with self.data_path.open("r", encoding="utf-8") as file:
            pesticides = json.load(file)

        docs = []
        for item in pesticides:
            text = (
                f"{item.get('name')} {item.get('category')} danger {item.get('danger_level')}. "
                f"Symptoms: {', '.join(item.get('symptoms', []))}. "
                f"First aid: {item.get('first_aid')}. Notes: {item.get('notes')}."
            )
            docs.append({"id": item.get("name"), "text": text, "source": "pesticides.json"})

        if self.docs_dir.exists():
            for path in self.docs_dir.glob("*.txt"):
                try:
                    docs.append({"id": path.stem, "text": path.read_text(encoding="utf-8"), "source": str(path)})
                except Exception:
                    continue
        return docs

    def _init_chroma(self) -> None:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            self.persist_dir.mkdir(parents=True, exist_ok=True)
            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            client = chromadb.PersistentClient(path=str(self.persist_dir))
            collection = client.get_or_create_collection("agriai_pesticide_knowledge")
            if collection.count() == 0:
                texts = [doc["text"] for doc in self.documents]
                embeddings = model.encode(texts).tolist()
                collection.add(
                    ids=[str(index) for index in range(len(texts))],
                    documents=texts,
                    metadatas=[{"source": doc["source"], "title": doc["id"]} for doc in self.documents],
                    embeddings=embeddings,
                )
            self._chroma = (collection, model)
        except Exception:
            self._chroma = None

    def retrieve(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        if self._chroma is not None:
            try:
                collection, model = self._chroma
                embedding = model.encode([query]).tolist()[0]
                result = collection.query(query_embeddings=[embedding], n_results=top_k)
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                return [
                    {"text": text, "source": meta.get("source", "chroma"), "score": None}
                    for text, meta in zip(docs, metas)
                ]
            except Exception:
                pass

        return self._keyword_retrieve(query, top_k)

    def _keyword_retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        scored = []
        for doc in self.documents:
            doc_tokens = tokenize(doc["text"])
            overlap = len(query_tokens & doc_tokens)
            score = overlap / math.sqrt(max(len(doc_tokens), 1))
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"text": doc["text"], "source": doc["source"], "score": score}
            for score, doc in scored[:top_k]
        ]

    def context(self, query: str, top_k: int = 4, max_chars: int = 1800) -> str:
        chunks = []
        for item in self.retrieve(query, top_k):
            chunks.append(f"Source: {item['source']}\n{item['text']}")
        return "\n\n".join(chunks)[:max_chars]
