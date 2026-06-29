"""
scripts/build_index.py
----------------------
Run this once (and re-run whenever your /data files change) to build the
FAISS vector index that the RAG module uses at runtime.

Usage:
    python scripts/build_index.py

Output (written to /data/):
    faiss_index.bin   — the FAISS flat index
    faiss_meta.json   — parallel list of metadata dicts (one per chunk)
"""

import json
import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "faiss_index.bin"
META_PATH  = DATA_DIR / "faiss_meta.json"

# ── Embedding model ───────────────────────────────────────────────────────────
MODEL_NAME = "all-MiniLM-L6-v2"   # 384-dim, fast, multilingual-friendly


# ═════════════════════════════════════════════════════════════════════════════
# 1. CHUNKING HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def chunk_courses(filepath: Path) -> list[dict]:
    """One chunk per course entry from kayfa_courses.json."""
    if not filepath.exists():
        print(f"  ⚠️  {filepath.name} not found — skipping.")
        return []

    with open(filepath, encoding="utf-8") as f:
        courses = json.load(f)

    chunks = []
    for c in courses:
        track_text  = ", ".join(c.get("track", []))
        text = (
            f"Course: {c.get('name', '')}\n"
            f"Level: {c.get('level', '')}\n"
            f"Track: {track_text}\n"
            f"Summary: {c.get('summary', '')}"
        )
        chunks.append({
            "text":   text,
            "type":   "course",
            "name":   c.get("name", ""),
            "level":  c.get("level", ""),
            "track":  track_text,
            "summary": c.get("summary", ""),
        })
    print(f"  ✅  {len(chunks)} course chunks from {filepath.name}")
    return chunks


def chunk_roadmaps(filepath: Path) -> list[dict]:
    """One chunk per roadmap/diploma entry from kayfa_roadmaps.json."""
    if not filepath.exists():
        print(f"  ⚠️  {filepath.name} not found — skipping.")
        return []

    with open(filepath, encoding="utf-8") as f:
        roadmaps = json.load(f)

    chunks = []
    for r in roadmaps:
        skills_text = ", ".join(r.get("skills", []))
        track_text  = ", ".join(r.get("track", []))
        text = (
            f"Diploma/Roadmap: {r.get('name', '')}\n"
            f"Duration: {r.get('duration', '')}\n"
            f"Track: {track_text}\n"
            f"Skills: {skills_text}"
        )
        chunks.append({
            "text":     text,
            "type":     "roadmap",
            "name":     r.get("name", ""),
            "duration": r.get("duration", ""),
            "track":    track_text,
            "skills":   skills_text,
        })
    print(f"  ✅  {len(chunks)} roadmap chunks from {filepath.name}")
    return chunks


def chunk_markdown(filepath: Path, chunk_size: int = 400, overlap: int = 80) -> list[dict]:
    """
    Splits a Markdown file into overlapping text windows.
    chunk_size and overlap are in characters (not tokens).
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # Split on double-newlines first (paragraph boundaries) then merge
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    
    chunks   = []
    buffer   = ""
    for para in paragraphs:
        if len(buffer) + len(para) + 2 <= chunk_size:
            buffer = (buffer + "\n\n" + para).strip()
        else:
            if buffer:
                chunks.append({
                    "text":   buffer,
                    "type":   "document",
                    "source": filepath.stem,
                })
            # Start next chunk with overlap from end of previous buffer
            buffer = buffer[-overlap:] + "\n\n" + para if overlap else para

    if buffer:
        chunks.append({
            "text":   buffer,
            "type":   "document",
            "source": filepath.stem,
        })

    print(f"  ✅  {len(chunks)} chunks from {filepath.name}")
    return chunks


# ═════════════════════════════════════════════════════════════════════════════
# 2. BUILD INDEX
# ═════════════════════════════════════════════════════════════════════════════

def build():
    print("\n📦  Loading embedding model …")
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    print("\n📂  Chunking data files …")
    all_chunks: list[dict] = []
    all_chunks += chunk_courses(DATA_DIR / "kayfa_courses.json")
    all_chunks += chunk_roadmaps(DATA_DIR / "kayfa_roadmaps.json")

    for md_file in sorted(DATA_DIR.glob("*.md")):
        all_chunks += chunk_markdown(md_file)

    if not all_chunks:
        print("\n❌  No chunks produced — make sure /data has content files.")
        return

    print(f"\n🔢  Embedding {len(all_chunks)} chunks …")
    texts      = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    # L2-normalise so inner-product == cosine similarity
    faiss.normalize_L2(embeddings)

    print("\n🗂️   Building FAISS index (IndexFlatIP) …")
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # Inner-product on normalised vectors = cosine
    index.add(embeddings)

    # ── Persist ───────────────────────────────────────────────────────────────
    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\n✅  Done!")
    print(f"   Index  → {INDEX_PATH}  ({index.ntotal} vectors, dim={dim})")
    print(f"   Meta   → {META_PATH}")


if __name__ == "__main__":
    build()