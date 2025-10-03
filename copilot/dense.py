from __future__ import annotations

import json
import os
from pathlib import Path
from types import NoneType
from typing import Optional, List, Dict, Any

import numpy as np

# Make tiny boxes happy
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# Optional FAISS
try:
    import faiss  # type: ignore
except Exception:
    faiss = None

if os.getenv("COPILOT_DISABLE_FAISS", "0") == "1":
    faiss = None

BASE = Path(os.environ.get("COPILOT_INDEX_DIR", "copilot_index"))
MODEL_PATH = os.environ.get("COPILOT_EMBED_MODEL", "models/copilot-embed")
USE_MEMMAP = os.getenv("COPILOT_MEMMAP", "1") != "0"

# Lazy singletons
_model = None  # SentenceTransformer
_index = None  # FAISS index
_corpus: Optional[List[Dict]] = None
_vecs: Optional[np.ndarray] = None


def _load() -> None:
    """Lazy-load model, corpus, and either FAISS index or mem-mapped numpy."""
    global _model, _index, _corpus, _vecs

    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_PATH)

    if _corpus is None:
        corpus_path = BASE / "corpus.jsonl"
        if not corpus_path.exists():
            raise FileNotFoundError(f"Corpus not found at {corpus_path}. Build your index.")
        with corpus_path.open("r", encoding="utf-8") as f:
            _corpus = [json.loads(line) for line in f if line.strip()]

    if faiss and _index is None and (BASE / "faiss.index").exists():
        _index = faiss.read_index(str(BASE / "faiss.index"))

    if _index is None and _vecs is None:
        vec_path = BASE / "embeddings.npy"
        if not vec_path.exists():
            raise FileNotFoundError(f"Embeddings not found at {vec_path}. Build your index.")
        _vecs = np.load(vec_path, mmap_mode="r" if USE_MEMMAP else None)
        if _vecs.dtype != np.float32:
            _vecs = _vecs.astype(np.float32, copy=False)
        if _vecs.ndim != 2:
            raise ValueError(f"embeddings.npy must be 2D, got {_vecs.shape}")


def search_dense(query: str, k: int = 6) -> list[tuple[type[NoneType[Any]], float]]:
    """
    Return top-K [(payload_dict, score)] for the query.
    payload_dict must contain: title, url, text (as created by your builder).
    """
    _load()
    assert _model is not None and _corpus is not None

    qv = _model.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
    k = int(max(1, min(k, len(_corpus))))

    if _index is not None:
        scores, idx = _index.search(qv, k)
        return [(_corpus[i], float(s)) for i, s in zip(idx[0].tolist(), scores[0].tolist())]

    # numpy fallback
    assert _vecs is not None
    sims = np.dot(_vecs, qv[0])  # (N,)
    topk = np.argpartition(sims, -k)[-k:]
    topk = topk[np.argsort(sims[topk])][::-1]
    return [(_corpus[i], float(sims[i])) for i in topk]


def reload_index() -> None:
    """Hot-reload on next query (keeps model to save RAM)."""
    global _index, _corpus, _vecs
    _index = None
    _corpus = None
    _vecs = None
