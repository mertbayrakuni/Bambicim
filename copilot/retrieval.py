import re
from typing import List, Dict

from django.db.models import Q

from .models import Doc

_WORD = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+")


def tokenize(s: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(s or "")]


def search(q: str, k: int = 6) -> List[Dict]:
    """
    Very simple keyword scorer. Easy to swap with pgvector later.
    """
    q = (q or "").strip()
    if not q:
        return []
    toks = tokenize(q)
    qs = Q()
    for t in set(toks):
        qs |= Q(text__icontains=t) | Q(title__icontains=t) | Q(url__icontains=t)
    hits = (Doc.objects.filter(qs)
    .only("id", "title", "url", "text")
    .order_by("-updated_at")[:200])  # cap

    scored = []
    for d in hits:
        text_l = (d.text or "").lower()
        score = sum(text_l.count(t) for t in toks) + (d.title.lower().count(toks[0]) if d.title else 0)
        if score > 0:
            # short snippet
            idx = max(text_l.find(toks[0]), 0)
            start = max(0, idx - 80)
            end = min(len(d.text), start + 220)
            snippet = (d.text[start:end] + ("…" if end < len(d.text) else "")).replace("\n", " ")
            scored.append(
                {"id": d.id, "title": d.title or d.url or d.slug, "url": d.url, "score": score, "snippet": snippet})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]
