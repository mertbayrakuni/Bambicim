# copilot/dense.py
from __future__ import annotations
import os, time, numpy as np
from typing import List, Dict
from dataclasses import dataclass
from django.conf import settings
from sentence_transformers import SentenceTransformer
try:
    import faiss  # type: ignore
except Exception:
    faiss = None  # graceful fallback

from .models import Doc
from .retrieval import _split_paragraphs, _highlight, _tok

MODEL_NAME = os.getenv("COPILOT_EMBED_MODEL",
                       "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

@dataclass
class Row:
    id: str
    url: str
    title: str
    text: str

_model: SentenceTransformer | None = None
_index = None      # FAISS index
_rows: List[Row] = []
_built_at = 0.0

def _embed(texts: List[str]) -> np.ndarray:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    vecs = _model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(vecs, dtype=np.float32)

def build(force=False):
    """Build a paragraph-level dense index in memory."""
    global _index, _rows, _built_at
    if not force and time.time() - _built_at < 60:
        return
    _rows = []
    docs = Doc.objects.order_by("-updated_at")[: settings.COPILOT_MAX_DOCS]
    paras: List[str] = []
    for d in docs:
        for p in _split_paragraphs(d.text or (d.snippet or "")):
            if len(p) < 40:  # ignore trivial
                continue
            _rows.append(Row(d.id, d.url or "", d.title or "", p))
            paras.append(p)

    if not paras:
        _index = None
        _built_at = time.time()
        return

    X = _embed(paras)

    if faiss is None:
        # light fallback: brute cosine in numpy
        _index = ("brute", X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12))
    else:
        dim = X.shape[1]
        _index = faiss.IndexFlatIP(dim)
        _index.add(X)
    _built_at = time.time()

def search_dense(query: str, k=6) -> List[Dict]:
    build()
    if _index is None or not query.strip():
        return []

    qv = _embed([query])
    if faiss is None and isinstance(_index, tuple) and _index[0] == "brute":
        X = _index[1]
        sims = (qv @ X.T).ravel()
        idx = sims.argsort()[::-1][: max(k*2, 8)]
        scores = sims[idx]
    else:
        scores, idx = _index.search(qv, max(k*2, 8))  # type: ignore
        scores, idx = scores[0], idx[0]

    seen = set()
    out: List[Dict] = []
    for sc, i in sorted(zip(scores, idx), key=lambda x: float(x[0]), reverse=True):
        if i < 0:  # faiss may return -1 if empty
            continue
        r = _rows[int(i)]
        if r.id in seen:
            continue
        seen.add(r.id)
        out.append({
            "id": r.id,
            "title": r.title or r.url,
            "url": r.url,
            "score": float(sc),
            "snippet": _highlight(r.text, _tok(query)),
        })
        if len(out) >= k:
            break
    return out
