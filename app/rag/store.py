"""
Lightweight RAG layer over the repo's coding-standards doc, used by the
quality agent to ground its review in something more concrete than generic
LLM taste. Prefers Chroma's embedding-based retrieval; falls back to a
keyword-overlap scorer if Chroma or its embedding model can't be loaded
(e.g. no network access to fetch the model), so the quality agent still gets
*some* grounding either way.
"""
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

# Constrain BLAS thread pools *before* chromadb (and its numpy/onnxruntime
# deps) get imported anywhere below. A large thread pool can fail to
# allocate under memory pressure ("OpenBLAS error: Memory allocation still
# failed after 10 retries") — and this app runs several agents in parallel,
# so that pressure is real, not hypothetical.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from app.config import settings

logger = logging.getLogger("codeguardian.rag")

_SECTION_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)


def _load_sections() -> list[dict]:
    path = Path(settings.coding_standards_path)
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    headers = list(_SECTION_RE.finditer(text))
    if not headers:
        return [{"id": "standards-0", "title": "Coding Standards", "text": text}]

    sections = []
    for i, match in enumerate(headers):
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        sections.append({
            "id": f"standards-{i}",
            "title": match.group(1).strip(),
            "text": text[start:end].strip(),
        })
    return sections


@lru_cache(maxsize=1)
def _get_chroma_collection():
    import chromadb

    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_or_create_collection("coding_standards")
    sections = _load_sections()
    if sections and collection.count() == 0:
        collection.add(
            ids=[s["id"] for s in sections],
            documents=[s["text"] for s in sections],
            metadatas=[{"title": s["title"]} for s in sections],
        )
    return collection


def query_standards(text: str, n_results: int = 3) -> list[str]:
    """Return up to n_results coding-standards excerpts relevant to `text`."""
    sections = _load_sections()
    if not sections:
        return []

    try:
        collection = _get_chroma_collection()
        result = collection.query(query_texts=[text], n_results=min(n_results, len(sections)))
        return result.get("documents", [[]])[0]
    except Exception:
        logger.warning("Chroma retrieval unavailable, falling back to keyword overlap", exc_info=True)
        return _keyword_fallback(text, sections, n_results)


def _keyword_fallback(text: str, sections: list[dict], n_results: int) -> list[str]:
    words = set(re.findall(r"\w+", text.lower()))
    scored = sorted(
        sections,
        key=lambda s: len(words & set(re.findall(r"\w+", s["text"].lower()))),
        reverse=True,
    )
    return [s["text"] for s in scored[:n_results]]
