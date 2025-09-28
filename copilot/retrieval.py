# copilot/retrieval.py
from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import numpy as np

from copilot.dense import search_dense

try:
    from rank_bm25 import BM25Okapi as BM25
except Exception:
    BM25 = None  # rank-bm25 not available

from django.conf import settings
from .models import Paragraph

# ----------------------- knobs -----------------------
RETRIEVER_MODE = (getattr(settings, "COPILOT_RETRIEVER", os.getenv("COPILOT_RETRIEVER", "hybrid")) or "hybrid").lower()
LANG = (getattr(settings, "COPILOT_LANG", os.getenv("COPILOT_LANG", "tr")) or "tr").lower()
MAX_DOCS = int(getattr(settings, "COPILOT_MAX_DOCS", os.getenv("COPILOT_MAX_DOCS", 60)) or 60)


# ----------------------- tiny types ------------------
@dataclass
class Para:
    doc_id: int | str
    title: str
    url: str
    text: str


# ----------------------- globals ---------------------
_bm25: Optional[BM25] = None
_paras: List[Para] = []
_bm25_corpus_tokens: List[List[str]] = []
_built_at: float = 0.0

# dense glue (optional)
_dense_available = False
try:
    from .dense import ensure_dense_index, dense_search  # optional module

    _dense_available = True
except Exception:
    _dense_available = False

# ----------------------- utils -----------------------
_ws_re = re.compile(r"\s+")
_tok_re_tr = re.compile(r"[^\wçğıöşüâîû]+", re.IGNORECASE)
_tok_re_en = re.compile(r"[^\w]+", re.IGNORECASE)


def _tok(text: str) -> List[str]:
    text = text.lower()
    if LANG == "tr":
        text = _tok_re_tr.sub(" ", text)
    else:
        text = _tok_re_en.sub(" ", text)
    return [t for t in _ws_re.split(text) if t]


def _highlight(text: str, qtok: List[str], width: int = 210) -> str:
    if not text:
        return ""
    lo = text[: width * 2]  # inspect a small window
    # pick earliest match window
    best = 0
    pos = 0
    tl = lo.lower()
    for t in qtok[:6]:
        i = tl.find(t)
        if i >= 0:
            score = max(1, len(t))
            if score > best:
                best = score
                pos = i
    start = max(0, pos - width // 2)
    end = min(len(lo), start + width)
    snippet = lo[start:end].strip()
    if start > 0:
        snippet = "… " + snippet
    if end < len(text):
        snippet = snippet + " …"
    return snippet


# --- simple paragraph splitter (HTML-aware, dependency-free) ---
_html_tag = re.compile(r"<[^>]+>")


def _split_paragraphs(html_or_text: str, max_len: int = 800) -> list[str]:
    """
    Split HTML/text into clean paragraph-ish chunks.
    - Splits on </p>, <br>, or blank lines.
    - Strips tags.
    - Drops very short bits.
    - Further splits long paragraphs on sentence/space boundaries.
    """
    if not html_or_text:
        return []

    # 1) coarse split by HTML paragraph breaks or blank lines
    raw_parts = re.split(r"(?:</p>|<br\s*/?>|\n\s*\n)+", html_or_text, flags=re.I)

    out: list[str] = []
    for part in raw_parts:
        # strip tags, normalize whitespace
        txt = _html_tag.sub(" ", part)
        txt = " ".join(txt.split())  # collapse whitespace

        if len(txt) < 40:  # ignore very short fragments
            continue

        # 2) chunk very long bits
        while len(txt) > max_len:
            cut = txt.rfind(".", 0, max_len)
            if cut <= 0:
                cut = txt.rfind(" ", 0, max_len)
                if cut <= 0:
                    break
            out.append(txt[: cut + 1].strip())
            txt = txt[cut + 1:].strip()

        if txt:
            out.append(txt)

    return out


# ----------------------- index builder ----------------
def _build_index(force: bool = False) -> None:
    global _bm25, _paras, _bm25_corpus_tokens, _built_at

    # quick cache (rebuild at most every 10 min unless forced)
    if not force and _built_at and (time.time() - _built_at) < 600 and _paras:
        return

    qs = (
        Paragraph.objects
        .select_related("doc")
        .order_by("doc_id", "order")
    )

    if MAX_DOCS > 0:
        # cap by number of docs (not rows). we gather until MAX_DOCS distinct doc_ids.
        seen = set()
        rows = []
        for p in qs.iterator(chunk_size=1000):
            rows.append(p)
            seen.add(p.doc_id)
            if len(seen) >= MAX_DOCS and p.order >= 2:  # take first few paras per doc
                # we still keep going until we pass first 2 paras of the last doc
                break
    else:
        rows = list(qs)

    _paras = [
        Para(
            doc_id=p.doc_id,
            title=p.title or (p.doc.title if hasattr(p.doc, "title") else ""),
            url=p.url or (p.doc.url if hasattr(p.doc, "url") else ""),
            text=p.text or "",
        )
        for p in rows
        if (p.text or "").strip()
    ]

    _bm25 = None
    _bm25_corpus_tokens = []
    if BM25 is not None and _paras:
        _bm25_corpus_tokens = [_tok(p.text) for p in _paras]
        _bm25 = BM25(_bm25_corpus_tokens)

    _built_at = time.time()


# ----------------------- public search ----------------
def search(q: str, k: int = 6) -> List[Dict]:
    """
    Returns list[{id,title,url,score,snippet}]
    - bm25 only, dense only, or hybrid (weighted merge).
    - All fall back gracefully if a component is missing.
    """
    _build_index()
    if not q or not q.strip():
        return []

    qtok = _tok(q)

    # --- BM25 part (optional) ---
    bm25_scores = None
    if _bm25 is not None:
        bm25_scores = np.asarray(_bm25.get_scores(qtok), dtype=np.float32)
        if bm25_scores.size:
            # normalize to [0,1] to blend with dense
            m = float(bm25_scores.max())
            if m > 0:
                bm25_scores = bm25_scores / m
        else:
            bm25_scores = None

    # --- Dense part (optional) ---
    dense_scores = None
    if _dense_available and RETRIEVER_MODE in ("dense", "hybrid"):
        try:
            dense_scores = dense_search(q, _paras)  # returns np.array of shape [N]
        except Exception:
            dense_scores = None

    # choose mode
    mode = RETRIEVER_MODE
    if mode == "dense" and dense_scores is None:
        mode = "bm25"
    if mode in ("hybrid",) and dense_scores is None:
        mode = "bm25"
    if mode == "bm25" and (_bm25 is None or bm25_scores is None):
        # absolutely nothing available
        return []

    # final score
    if mode == "bm25":
        final = bm25_scores
    elif mode == "dense":
        final = dense_scores
    else:  # hybrid
        # simple blend; tune as you wish
        w_bm25 = 0.45
        w_dense = 0.55
        if bm25_scores is None:
            final = dense_scores
        elif dense_scores is None:
            final = bm25_scores
        else:
            final = w_bm25 * bm25_scores + w_dense * dense_scores

    # rank & group by doc
    ranked = np.argsort(-final)[: max(k * 4, 12)]
    by_doc: Dict[str, List[Tuple[float, int]]] = {}
    for idx in ranked:
        sc = float(final[idx])
        para = _paras[int(idx)]
        by_doc.setdefault(str(para.doc_id), []).append((sc, int(idx)))

    results: List[Dict] = []
    # order docs by total score
    doc_order = sorted(by_doc.items(), key=lambda x: sum(s for s, _ in x[1]), reverse=True)[:k]
    for doc_id, items in doc_order:
        sc, best_idx = max(items, key=lambda x: x[0])
        p = _paras[best_idx]
        snippet = _highlight(p.text, qtok)
        results.append({
            "id": doc_id,
            "title": p.title or p.url,
            "url": p.url,
            "score": round(sc, 3),
            "snippet": snippet,
        })
    return results


def hybrid_search(q: str, k: int = 8, rrf_k: int = 60):
    bm25 = search(q, k=k)  # your existing BM25 returns list of dicts or (item, score)
    dense = search_dense(q, k=k)

    def key_from_item(item):
        # use paragraph text + url as a stable key
        if isinstance(item, dict):
            return (item.get("text") or item.get("snippet") or "").strip(), item.get("url")
        return item[0]["text"], item[0]["url"]

    scores = defaultdict(float)
    payload = {}

    # normalize shapes for BM25: [(payload, score)]
    bm_pairs = []
    for it in bm25:
        if isinstance(it, tuple):
            payload_it, s = it
        else:
            payload_it, s = it, it.get("score", 0.0)
        bm_pairs.append((payload_it, float(s)))

    for rank, (pl, _) in enumerate(dense):
        kkey = key_from_item((pl, None))
        scores[kkey] += 1.0 / (rrf_k + rank + 1)
        payload[kkey] = pl

    for rank, (pl, _) in enumerate(bm_pairs):
        kkey = key_from_item((pl, None))
        scores[kkey] += 1.0 / (rrf_k + rank + 1)
        payload[kkey] = pl

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    return [payload[k] | {"rrf_score": v} for k, v in ranked]
