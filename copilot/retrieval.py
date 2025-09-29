# copilot/retrieval.py
from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import numpy as np
from django.conf import settings

from copilot.dense import search_dense  # our unified dense API
from .models import Paragraph

try:
    from rank_bm25 import BM25Okapi as BM25
except Exception:
    BM25 = None

RETRIEVER_MODE = (getattr(settings, "COPILOT_RETRIEVER", os.getenv("COPILOT_RETRIEVER", "hybrid")) or "hybrid").lower()
MAX_DOCS = int(getattr(settings, "COPILOT_MAX_DOCS", os.getenv("COPILOT_MAX_DOCS", 60)) or 60)


@dataclass
class Para:
    doc_id: str
    title: str
    url: str
    text: str


_bm25 = None
_paras: List[Para] = []
_bm_tokens: List[List[str]] = []
_built_at: float = 0.0

_ws = re.compile(r"\s+")
_tok_tr = re.compile(r"[^\wçğıöşüâîû]+", re.I)
_tok_en = re.compile(r"[^\w]+", re.I)


def _tok(s: str) -> List[str]:
    s = s.lower()
    # a tiny heuristic; you can wire a setting for LANG if needed
    is_tr = bool(re.search(r"[çğıöşüİı]", s))
    s = (_tok_tr if is_tr else _tok_en).sub(" ", s)
    return [t for t in _ws.split(s) if t]


_tag = re.compile(r"<[^>]+>")


def _highlight(text: str, qtok: List[str], width: int = 210) -> str:
    if not text:
        return ""
    lo = text[: width * 2]
    best, pos = 0, 0
    tl = lo.lower()
    for t in qtok[:6]:
        i = tl.find(t)
        if i >= 0:
            sc = max(1, len(t))
            if sc > best:
                best, pos = sc, i
    start = max(0, pos - width // 2)
    end = min(len(lo), start + width)
    snip = lo[start:end].strip()
    if start > 0: snip = "… " + snip
    if end < len(text): snip = snip + " …"
    return snip


def _split_paragraphs(html_or_text: str, max_len: int = 800) -> List[str]:
    if not html_or_text:
        return []
    raw_parts = re.split(r"(?:</p>|<br\s*/?>|\n\s*\n)+", html_or_text, flags=re.I)
    out: List[str] = []
    for part in raw_parts:
        txt = _tag.sub(" ", part)
        txt = " ".join(txt.split())
        if len(txt) < 40:
            continue
        while len(txt) > max_len:
            cut = txt.rfind(".", 0, max_len)
            if cut <= 0:
                cut = txt.rfind(" ", 0, max_len)
                if cut <= 0: break
            out.append(txt[:cut + 1].strip())
            txt = txt[cut + 1:].strip()
        if txt:
            out.append(txt)
    return out


def _build_index(force: bool = False) -> None:
    global _bm25, _paras, _bm_tokens, _built_at
    if not force and _built_at and (time.time() - _built_at) < 600 and _paras:
        return

    qs = Paragraph.objects.select_related("doc").order_by("doc_id", "order")
    if MAX_DOCS > 0:
        seen, rows = set(), []
        for p in qs.iterator(chunk_size=1000):
            rows.append(p)
            seen.add(p.doc_id)
            # take first few paras of each doc; stop early when we reached MAX_DOCS
            if len(seen) >= MAX_DOCS and p.order >= 2:
                break
    else:
        rows = list(qs)

    _paras = [
        Para(
            doc_id=str(p.doc_id),
            title=p.title or (getattr(p.doc, "title", "") or ""),
            url=p.url or (getattr(p.doc, "url", "") or ""),
            text=p.text or "",
        )
        for p in rows if (p.text or "").strip()
    ]

    _bm25, _bm_tokens = None, []
    if BM25 is not None and _paras:
        _bm_tokens = [_tok(p.text) for p in _paras]
        _bm25 = BM25(_bm_tokens)
    _built_at = time.time()


def _search_bm25(q: str) -> Optional[np.ndarray]:
    if _bm25 is None:
        return None
    qtok = _tok(q)
    scores = np.asarray(_bm25.get_scores(qtok), dtype=np.float32)
    if scores.size:
        m = float(scores.max())
        if m > 0:
            scores = scores / m
        return scores
    return None


def hybrid_search(q: str, k: int = 8, rrf_k: int = 60) -> List[Dict]:
    """
    Return list of {title,url,text?,snippet,score}
    Hybrid = Reciprocal Rank Fusion of BM25 (DB paragraphs) + Dense (prebuilt corpus.jsonl/embeddings).
    """
    _build_index()
    if not q or not q.strip():
        return []

    # BM25 from DB paragraphs
    bm_scores = _search_bm25(q)
    bm_pairs: List[Tuple[Dict, float]] = []
    if bm_scores is not None:
        order = np.argsort(-bm_scores)[: max(k * 4, 12)]
        for idx in order:
            p = _paras[int(idx)]
            bm_pairs.append((
                {"title": p.title or p.url, "url": p.url, "text": p.text},
                float(bm_scores[int(idx)]),
            ))

    # Dense from prebuilt index
    try:
        dense_pairs = search_dense(q, k=max(k, 8))  # [(payload, score)]
    except Exception:
        dense_pairs = []

    # RRF fusion
    def key_of(payload: Dict) -> Tuple[str, str]:
        return ((payload.get("text") or "")[:80], payload.get("url") or "")

    scores = defaultdict(float)
    payloads: Dict[Tuple[str, str], Dict] = {}

    for rank, (pl, _) in enumerate(dense_pairs):
        key = key_of(pl)
        scores[key] += 1.0 / (rrf_k + rank + 1)
        payloads[key] = pl

    for rank, (pl, _) in enumerate(bm_pairs):
        key = key_of(pl)
        scores[key] += 1.0 / (rrf_k + rank + 1)
        # prefer richer payload if present
        payloads[key] = payloads.get(key) or pl

    qtok = _tok(q)
    items: List[Dict] = []
    for key, sc in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]:
        pl = payloads[key]
        text = pl.get("text") or ""
        items.append({
            "title": pl.get("title") or pl.get("url") or "Result",
            "url": pl.get("url") or "",
            "text": text,
            "snippet": _highlight(text, qtok),
            "score": round(float(sc), 4),
        })
    return items
