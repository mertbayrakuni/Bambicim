from __future__ import annotations

import json
import os
from pathlib import Path
from types import NoneType
from typing import Optional, List, Tuple, Any

import numpy as np
from sentence_transformers import SentenceTransformer

# ---- light env hygiene (safe on Render) ------------------------------------
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

# Optional FAISS (can be force-disabled via env)
try:
    import faiss  # type: ignore
except Exception:
    faiss = None

if os.getenv("COPILOT_DISABLE_FAISS", "0") == "1":
    faiss = None  # explicit opt-out to shave a little RAM

# ---- paths & config --------------------------------------------------------
BASE = Path(os.environ.get("COPILOT_INDEX_DIR", "copilot_index"))
MODEL_PATH = os.environ.get("COPILOT_EMBED_MODEL", "models/copilot-embed")
USE_MEMMAP = os.getenv("COPILOT_MEMMAP", "1") != "0"  # mem-map embeddings.npy

# ---- singletons (lazy) -----------------------------------------------------
_model: Optional[SentenceTransformer] = None
_index = None
_corpus: Optional[List[dict]] = None
_vecs: Optional[np.ndarray] = None  # mem-mapped when possible


def _load():
    """
    Lazy-load model, corpus and either a FAISS index or mem-mapped numpy matrix.
    """
    global _model, _index, _corpus, _vecs

    # model first time only
    if _model is None:
        _model = SentenceTransformer(MODEL_PATH)

    # corpus
    if _corpus is None:
        corpus_path = BASE / "corpus.jsonl"
        if not corpus_path.exists():
            raise FileNotFoundError(f"Corpus not found at {corpus_path}. Did you run build_dense_index?")
        with corpus_path.open("r", encoding="utf-8") as f:
            _corpus = [json.loads(l) for l in f if l.strip()]

    # index (prefer FAISS if present)
    if faiss and _index is None and (BASE / "faiss.index").exists():
        _index = faiss.read_index(str(BASE / "faiss.index"))

    # numpy fallback (mem-mapped)
    if _index is None and _vecs is None:
        vec_path = BASE / "embeddings.npy"
        if not vec_path.exists():
            raise FileNotFoundError(f"Embeddings not found at {vec_path}. Did you run build_dense_index?")
        _vecs = np.load(vec_path, mmap_mode="r" if USE_MEMMAP else None)
        # ensure 2D float32 for stable dot products
        if _vecs.dtype != np.float32:
            _vecs = _vecs.astype(np.float32, copy=False)
        if _vecs.ndim != 2:
            raise ValueError(f"embeddings.npy expected 2D, got shape {_vecs.shape}")


def search_dense(query: str, k: int = 5) -> list[tuple[type[NoneType[Any]], float]]:
    """
    Dense retrieval. Returns list of (payload_dict, score) sorted by score desc.

    Notes:
    - We normalize query embeddings. build_dense_index already normalized corpus.
    - If FAISS is available, we use it. Otherwise NumPy dot-product fallback.
    """
    _load()
    assert _model is not None and _corpus is not None

    # encode query (normalized → cosine becomes inner product)
    qv = _model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
    qv = np.asarray(qv, dtype=np.float32)

    k = int(max(1, min(k, len(_corpus))))  # defensive bound

    if _index is not None:
        scores, idx = _index.search(qv, k)
        ids = idx[0].tolist()
        scs = scores[0].tolist()
        return [(_corpus[i], float(s)) for i, s in zip(ids, scs)]

    # numpy fallback (mem-mapped vectors)
    assert _vecs is not None
    # _vecs is (N, D), qv is (1, D)
    sims = np.dot(_vecs, qv[0])  # (N,)
    if isinstance(sims, np.memmap):  # just in case
        sims = np.asarray(sims)
    topk = np.argpartition(sims, -k)[-k:]
    topk = topk[np.argsort(sims[topk])][::-1]  # sort desc
    return [(_corpus[i], float(sims[i])) for i in topk]


def reload_index():
    """Hot-reload index/corpus on next query (used after /reindex)."""
    global _index, _corpus, _vecs
    _index = None
    _corpus = None
    _vecs = None
    # keep _model to avoid reloading weights unless env/model path changes
