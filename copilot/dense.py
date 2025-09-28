# copilot/dense.py
from __future__ import annotations

import os
import numpy as np

try:
    import faiss  # type: ignore
except Exception:
    faiss = None  # optional

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # optional

from django.conf import settings
from typing import List, Tuple
from dataclasses import dataclass

# shared tiny struct from retrieval (duplicated type hint only)
@dataclass
class Para:
    doc_id: int | str
    title: str
    url: str
    text: str

MODEL_NAME = os.getenv("COPILOT_DENSE_MODEL",
                       getattr(settings, "COPILOT_DENSE_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))

# globals
_model = None
_index = None
_vecs: np.ndarray | None = None
_built_for_n = -1

def _load_model():
    global _model
    if _model is None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not installed")
        _model = SentenceTransformer(MODEL_NAME)

def _embed(texts: List[str]) -> np.ndarray:
    _load_model()
    em = _model.encode(texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
    # ensure float32 for faiss/numpy math
    if em.dtype != np.float32:
        em = em.astype(np.float32)
    return em

def ensure_dense_index(paras: List[Para]) -> Tuple[np.ndarray, object | None]:
    """
    Build (or reuse) dense vectors and FAISS index if available.
    Returns (vecs, index_or_None)
    """
    global _index, _vecs, _built_for_n
    if _vecs is not None and _built_for_n == len(paras):
        return _vecs, _index

    texts = [p.text for p in paras]
    if not texts:
        _vecs, _index = None, None
        _built_for_n = 0
        return _vecs, _index

    _vecs = _embed(texts)
    _built_for_n = len(paras)

    if faiss is not None:
        dim = _vecs.shape[1]
        _index = faiss.IndexFlatIP(dim)  # cosine since we normalize
        _index.add(_vecs)
    else:
        _index = None
    return _vecs, _index

def dense_search(query: str, paras: List[Para]) -> np.ndarray:
    """
    Returns a numpy array of scores aligned with `paras`.
    Uses FAISS if available, else pure numpy cosine.
    """
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed")

    vecs, index = ensure_dense_index(paras)
    if vecs is None:
        return np.zeros((0,), dtype=np.float32)

    qv = _embed([query])[0:1]  # (1, dim)

    if index is not None:
        # FAISS inner product (cosine, because embeddings are normalized)
        D, _ = index.search(qv, k=vecs.shape[0])
        # FAISS returns topK only; we need a full vector aligned by row.
        # Recompute quickly as cosine to get dense vector.
        scores = (vecs @ qv.T).ravel()
    else:
        scores = (vecs @ qv.T).ravel()

    # scale to [0,1]
    mx = float(scores.max()) if scores.size else 0.0
    if mx > 0:
        scores = scores / mx
    return scores.astype(np.float32)
