# copilot/dense.py
from __future__ import annotations

import json
import numpy as np
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

try:
    import faiss  # optional
except Exception:
    faiss = None

BASE = Path(os.environ.get("COPILOT_INDEX_DIR", "copilot_index"))
MODEL_PATH = os.environ.get("COPILOT_EMBED_MODEL", "models/copilot-embed")

_model = None
_index = None
_corpus = None
_vecs = None


def _load():
    global _model, _index, _corpus, _vecs
    if _model is None:
        _model = SentenceTransformer(MODEL_PATH)
    if _corpus is None:
        _corpus = [json.loads(l) for l in (BASE / "corpus.jsonl").open("r", encoding="utf-8")]
    if faiss and _index is None and (BASE / "faiss.index").exists():
        _index = faiss.read_index(str(BASE / "faiss.index"))
    if _index is None:
        # fallback to numpy-only search
        _vecs = np.load(BASE / "embeddings.npy")


def search_dense(query: str, k: int = 5):
    _load()
    qv = _model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
    if _index is not None:
        scores, idx = _index.search(qv, k)
        hits = [(_corpus[i], float(scores[0][j])) for j, i in enumerate(idx[0])]
    else:
        # CPU fallback
        sims = np.dot(_vecs, qv[0])
        topk = sims.argsort()[-k:][::-1]
        hits = [(_corpus[i], float(sims[i])) for i in topk]
    return hits
