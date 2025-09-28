# copilot/retrieval.py
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple

from django.conf import settings
from rank_bm25 import BM25Okapi

from .models import Doc

_TR_STOP = {
    # quick Turkish stop words (tiny list is enough for our site)
    "ve", "ile", "da", "de", "mi", "mı", "mu", "mü", "bir", "bu", "şu", "o", "iki", "çok", "az", "daha", "en",
    "için", "gibi", "ama", "veya", "ya", "yok", "var", "olan", "ne", "nasıl", "neden", "hangi"
}
_EN_STOP = {
    "a", "an", "the", "and", "or", "to", "of", "in", "on", "for", "with", "from", "by", "as", "is", "are", "was",
    "were", "be", "been", "being"
}

STOP = _TR_STOP | _EN_STOP

_tokenize_re = re.compile(r"[^\wçğıöşüÇĞİÖŞÜ]+")


def _tok(s: str) -> List[str]:
    toks = [t for t in _tokenize_re.split((s or "").lower()) if t and t not in STOP]
    return toks


@dataclass
class Para:
    doc_id: str
    url: str
    title: str
    text: str
    tokens: List[str]


# ---------- in-memory index ----------
_index_built_at = 0.0
_paras: List[Para] = []
_bm25: BM25Okapi | None = None


def _split_paragraphs(txt: str) -> List[str]:
    # conservative split: blank lines or long sentences
    parts = [p.strip() for p in re.split(r"\n\s*\n|(?<=\.)\s{1,}(?=[A-ZÇĞİÖŞÜ])", txt or "") if len(p.strip()) > 40]
    return parts or [(txt or "").strip()]


def _build_index(force=False):
    global _index_built_at, _paras, _bm25
    if not force and time.time() - _index_built_at < 60:  # warm cache
        return
    _paras, corp = [], []
    qs = Doc.objects.order_by("-updated_at")[: settings.COPILOT_MAX_DOCS]
    for d in qs:
        paragraphs = _split_paragraphs(d.text or (d.snippet or ""))
        for p in paragraphs:
            tokens = _tok(p)
            if tokens:
                _paras.append(Para(doc_id=d.id, url=d.url or "", title=d.title or "", text=p, tokens=tokens))
                corp.append(tokens)
    _bm25 = BM25Okapi(corp) if corp else None
    _index_built_at = time.time()


# ---------- search ----------
def search(q: str, k: int = 6) -> List[Dict]:
    _build_index()
    if not _bm25 or not _paras or not q.strip():
        return []

    qtok = _tok(q)
    scores = _bm25.get_scores(qtok)
    # pick top paragraphs, then merge by doc
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[: max(k * 2, 8)]
    by_doc: Dict[str, List[Tuple[float, Para]]] = {}
    for idx, sc in ranked:
        para = _paras[idx]
        by_doc.setdefault(para.doc_id, []).append((sc, para))

    results: List[Dict] = []
    for doc_id, items in sorted(by_doc.items(), key=lambda x: sum(s for s, _ in x[1]), reverse=True)[:k]:
        sc, best_para = max(items, key=lambda x: x[0])
        snippet = _highlight(best_para.text, qtok)
        results.append({
            "id": doc_id,
            "title": best_para.title or best_para.url,
            "url": best_para.url,
            "score": round(float(sc), 3),
            "snippet": snippet,
        })
    return results


def _highlight(text: str, qtok: List[str]) -> str:
    text = " ".join(text.split())[:420]
    if not qtok: return text
    patt = re.compile("(" + "|".join(map(re.escape, qtok)) + ")", re.I)
    return patt.sub(r"**\1**", text)


# ---------- intent helpers ----------
_email_re = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_phone_re = re.compile(r"(\+?\d[\d\s\-()]{6,}\d)")


def _extract_contact_blurb() -> Tuple[str | None, str | None]:
    d = Doc.objects.filter(url__icontains="contact").order_by("-updated_at").first() or \
        Doc.objects.filter(title__icontains="contact").order_by("-updated_at").first()
    if not d:
        d = Doc.objects.order_by("-updated_at").first()
    txt = (d.text or "") + " " + (d.snippet or "")
    email = (_email_re.search(txt) or [None])[0] if _email_re.search(txt) else None
    phone = (_phone_re.search(txt) or [None])[0] if _phone_re.search(txt) else None
    return email, phone


def answer(q: str, k: int = 6) -> Tuple[str, List[Dict]]:
    ql = q.lower()
    cites = search(q, k)

    # explicit intents first (Turkish & English)
    if any(w in ql for w in ["mail", "e-posta", "eposta", "email", "iletişim", "contact"]):
        mail, phone = _extract_contact_blurb()
        lines = ["**İletişim bilgileri**"]
        if mail:  lines.append(f"- E-posta: `{mail}`")
        if phone: lines.append(f"- Telefon: `{phone}`")
        if not (mail or phone):
            lines.append("- Sitede açık iletişim bulunamadı. Form üzerinden yazabilirsiniz.")
        if cites:
            lines.append("\n**Kaynaklar**")
            for c in cites[:3]:
                lines.append(f"- [{c['title']}]({c['url']}) — {c['snippet']}")
        return "\n".join(lines), cites

    # generic synthesis
    parts = [
        "🔎 **Hazırlanıyorum… Hızlı düşünceler**",
        "- İçeriği taradım; aşağıdaki kaynaklar doğrudan alakalı."
    ]
    if cites:
        parts.append("\n**Kaynaklar**")
        for c in cites:
            parts.append(f"- [{c['title']}]({c['url']}) — {c['snippet']}")
        # tiny summary from top hit
        lead = cites[0]["snippet"]
        parts.insert(1, f"- {lead[:180]}…")
    else:
        parts.append("\nNe yazık ki uygun içerik bulamadım. Bir iki anahtar kelime daha paylaşır mısın?")
    return "\n".join(parts), cites
