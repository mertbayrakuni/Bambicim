# copilot/retrieval.py  (new bits for dense / hybrid)

from __future__ import annotations

import logging
import os
from typing import List, Dict, Tuple

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # we handle this gracefully

log = logging.getLogger(__name__)

# --- existing stuff you already have ---
# - Doc/Para models loading into _paras
# - your BM25 setup: _bm25, _tok, _highlight, etc.
# - _build_index() that populates _paras and _bm25

# --- NEW GLOBALS for dense ---
_dense_model = None  # SentenceTransformer
_para_embs: np.ndarray | None = None  # shape: (num_paras, dim)
_retriever_mode = os.getenv("COPILOT_RETRIEVER", "hybrid").lower()  # 'hybrid' | 'dense' | 'bm25'
_dense_weight = float(os.getenv("COPILOT_DENSE_WEIGHT", "0.65"))
_emb_model_name = os.getenv("COPILOT_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def _ensure_dense_model():
    """Lazy-load the sentence-transformers model."""
    global _dense_model
    if _dense_model is None:
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Add it to requirements.txt or choose COPILOT_RETRIEVER=bm25."
            )
        log.info("Loading embedding model: %s", _emb_model_name)
        _dense_model = SentenceTransformer(_emb_model_name)


def _embed(texts: List[str]) -> np.ndarray:
    """Return L2-normalized embeddings (np.float32)."""
    _ensure_dense_model()
    embs = _dense_model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # cosine sim = dot product
    ).astype(np.float32)
    return embs


def _norm01(x: np.ndarray) -> np.ndarray:
    """Min-max to [0,1] with small epsilon if flat."""
    xmin = float(x.min()) if x.size else 0.0
    xmax = float(x.max()) if x.size else 1.0
    if xmax - xmin < 1e-9:
        return np.zeros_like(x, dtype=np.float32)
    return ((x - xmin) / (xmax - xmin)).astype(np.float32)


def _dense_scores_for_query(q: str) -> np.ndarray:
    """Cosine sims for q vs all paragraphs (requires _para_embs)."""
    if _para_embs is None or not len(q.strip()):
        return np.zeros(0, dtype=np.float32)
    q_emb = _embed([q])[0]  # normalized
    # cosine = dot because both are normalized
    return (_para_embs @ q_emb).astype(np.float32)


# hook dense embedding computation into your index builder
# call this at the end of your existing _build_index() after _paras is ready
def _ensure_dense_index():
    """Compute paragraph embeddings if missing."""
    global _para_embs
    if _para_embs is not None:
        return
    if not _paras:
        return
    try:
        texts = [p.text for p in _paras]
        _para_embs = _embed(texts)  # shape (N, D)
        log.info("Dense index built: %s paragraphs, dim=%s", _para_embs.shape[0], _para_embs.shape[1])
    except Exception as e:
        log.warning("Dense index build failed (using bm25 only): %s", e)
        _para_embs = None


# If your current _build_index() is something like:
# def _build_index():
#     ... loads docs/paras ...
#     ... builds _bm25 ...
# Add this line at the end:
#
#     _ensure_dense_index()


def search(q: str, k: int = 6) -> List[Dict]:
    """
    Dense/BM25/Hybrid search over paragraphs; then merge by doc.
    Returns: [{id,title,url,score,snippet}]
    """
    _build_index()  # your existing function (must fill _paras, _bm25)
    if not _paras or not q.strip():
        return []

    # ---- prepare scores (dense and/or bm25) ----
    dense_scores = None
    bm25_scores = None

    if _retriever_mode in ("hybrid", "dense"):
        _ensure_dense_index()
        if _para_embs is not None:
            dense_scores = _dense_scores_for_query(q)  # cosine in [-1..1]
            # clamp to [0..1] (cos can be negative, but min-max below also handles it)
            dense_scores = _norm01(dense_scores)
        else:
            # model missing or failed; fallback
            if _retriever_mode == "dense":
                return []
            _retriever_mode = "bm25"

    if _retriever_mode in ("hybrid", "bm25"):
        if _bm25 is not None:
            qtok = _tok(q)
            bm25_scores = np.asarray(_bm25.get_scores(qtok), dtype=np.float32)
            bm25_scores = _norm01(bm25_scores)
        else:
            if _retriever_mode == "bm25":
                return []
            # else rely on dense only

    # ---- fuse scores ----
    if _retriever_mode == "dense" and dense_scores is not None:
        fused = dense_scores
    elif _retriever_mode == "bm25" and bm25_scores is not None:
        fused = bm25_scores
    else:
        # hybrid: weighted sum (dense dominates by default)
        if dense_scores is None and bm25_scores is None:
            return []
        if dense_scores is None:
            fused = bm25_scores
        elif bm25_scores is None:
            fused = dense_scores
        else:
            fused = (_dense_weight * dense_scores) + ((1.0 - _dense_weight) * bm25_scores)

    # ---- pick top paragraphs then merge by doc (same as your old logic) ----
    k_paras = max(k * 2, 8)
    ranked = list(zip(range(len(_paras)), fused.tolist()))
    ranked.sort(key=lambda x: x[1], reverse=True)
    ranked = ranked[:k_paras]

    by_doc: Dict[str, List[Tuple[float, Para]]] = {}
    for idx, sc in ranked:
        para = _paras[idx]
        by_doc.setdefault(para.doc_id, []).append((float(sc), para))

    results: List[Dict] = []
    # order docs by sum of their paragraph scores
    doc_order = sorted(by_doc.items(), key=lambda x: sum(s for s, _ in x[1]), reverse=True)[:k]
    for doc_id, items in doc_order:
        sc, best_para = max(items, key=lambda x: x[0])
        # if you want highlight to use query tokens, build them only when needed
        snippet = _highlight(best_para.text, _tok(q))
        results.append({
            "id": doc_id,
            "title": best_para.title or best_para.url,
            "url": best_para.url,
            "score": round(float(sc), 3),
            "snippet": snippet,
        })
    return results
