"""
agent/rag.py
------------
Semantic RAG using FAISS + sentence-transformers.

Replace the old keyword-based KayfaKnowledgeBase with this file.
The public API (search_courses, search_roadmaps, get_document_content)
is identical to the old version — bot.py needs zero changes.

Prerequisites (run once before starting the app):
    pip install faiss-cpu sentence-transformers
    python scripts/build_index.py
"""

import json
from pathlib import Path
from typing import Any, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = Path(__file__).resolve().parent.parent / "data"
INDEX_PATH = DATA_DIR / "faiss_index.bin"
META_PATH  = DATA_DIR / "faiss_meta.json"

# ── Embedding model (loaded once at import time) ───────────────────────────────
_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional[SentenceTransformer] = None
_index: Optional[faiss.Index]         = None
_meta:  Optional[list[dict]]          = None


def _load() -> tuple[faiss.Index, list[dict], SentenceTransformer]:
    """Lazy-load model + index into module-level singletons."""
    global _model, _index, _meta

    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)

    if _index is None:
        if not INDEX_PATH.exists() or not META_PATH.exists():
            raise FileNotFoundError(
                "FAISS index not found. Run `python scripts/build_index.py` first."
            )
        _index = faiss.read_index(str(INDEX_PATH))
        with open(META_PATH, encoding="utf-8") as f:
            _meta = json.load(f)

    return _index, _meta, _model


# ═════════════════════════════════════════════════════════════════════════════
# CORE SEMANTIC SEARCH
# ═════════════════════════════════════════════════════════════════════════════

def _semantic_search(
    query: str,
    top_k: int = 8,
    type_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
) -> list[dict]:
    """
    Embed `query` and return the top_k most similar chunks.

    Args:
        query:         Natural-language query (Arabic or English).
        top_k:         Number of results to return.
        type_filter:   If set, only return chunks with meta["type"] == type_filter.
                       Values: "course", "roadmap", "document".
        source_filter: If set, only return document chunks whose source filename
                       contains this string (case-insensitive).

    Returns:
        List of metadata dicts, each with an added "score" key (cosine sim).
    """
    index, meta, model = _load()

    vec = model.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(vec)

    # Search more candidates so we can filter without running out of results
    fetch_k = top_k * 4 if (type_filter or source_filter) else top_k
    fetch_k = min(fetch_k, index.ntotal)

    scores, indices = index.search(vec, fetch_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        chunk = dict(meta[idx])
        chunk["score"] = float(score)

        if type_filter and chunk.get("type") != type_filter:
            continue
        if source_filter and source_filter.lower() not in chunk.get("source", "").lower():
            continue

        results.append(chunk)
        if len(results) >= top_k:
            break

    return results


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API  (same signatures as the old KayfaKnowledgeBase methods)
# ═════════════════════════════════════════════════════════════════════════════

class KayfaKnowledgeBase:
    """
    Drop-in replacement for the old keyword-based knowledge base.
    All three methods keep the exact same signature and return type
    so that bot.py tool definitions need zero changes.
    """

    # ── search_courses ────────────────────────────────────────────────────────
    def search_courses(
        self, query: str, level: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Semantic search over individual courses.
        Optionally filter by level ('beginner', 'intermediate', 'advanced').
        """
        hits = _semantic_search(query, top_k=6, type_filter="course")

        results = []
        for h in hits:
            if level and h.get("level", "").lower() != level.lower():
                continue
            # Return the same shape the old code returned
            results.append({
                "name":    h.get("name", ""),
                "level":   h.get("level", ""),
                "track":   h.get("track", ""),
                "summary": h.get("summary", ""),
                "score":   h["score"],
            })
        return results

    # ── search_roadmaps ───────────────────────────────────────────────────────
    def search_roadmaps(self, query: str) -> list[dict[str, Any]]:
        """Semantic search over full diplomas / roadmaps."""
        hits = _semantic_search(query, top_k=4, type_filter="roadmap")
        return [
            {
                "name":     h.get("name", ""),
                "duration": h.get("duration", ""),
                "track":    h.get("track", ""),
                "skills":   h.get("skills", ""),
                "score":    h["score"],
            }
            for h in hits
        ]

    # ── get_document_content ──────────────────────────────────────────────────
    def get_document_content(self, doc_keyword: str) -> str:
        """
        Fetches the most relevant chunks from Markdown documents
        (Pricing, FAQs, Sales Pitches) using semantic search.

        Instead of loading an entire file, returns the top 3 most relevant
        passages — this saves tokens while staying grounded.
        """
        hits = _semantic_search(
            doc_keyword,
            top_k=3,
            type_filter="document",
        )

        if not hits:
            return (
                "SYSTEM CRITICAL ERROR: No document found in the database. "
                "RULE OVERRIDE: Do not attempt to answer using outside knowledge. "
                "You MUST reply that you do not have the specific details and "
                "offer to connect them with a human agent."
            )

        sections = []
        seen_sources = set()
        for h in hits:
            source = h.get("source", "unknown")
            seen_sources.add(source)
            sections.append(
                f"--- SOURCE: {source} (relevance: {h['score']:.2f}) ---\n{h['text']}"
            )

        return "\n\n".join(sections)


# ── Module-level singleton (imported by bot.py) ───────────────────────────────
kayfa_db = KayfaKnowledgeBase()