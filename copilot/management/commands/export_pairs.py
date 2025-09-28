# copilot/management/commands/export_pairs.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from django.core.management.base import BaseCommand, CommandParser

from copilot.models import Doc, Paragraph
from copilot.retrieval import _split_paragraphs  # tiny helper we added earlier

WS = re.compile(r"\s+")
TRASH = re.compile(
    r"(cookie|©|\ball rights reserved\b|privacy|terms|javascript required|no description yet)",
    re.I,
)


def _clean(s: str) -> str:
    s = re.sub(WS, " ", s).strip()
    s = TRASH.sub("", s)
    return s


def _candidate_queries(doc: Doc, paras: List[Paragraph]) -> List[str]:
    qs: List[str] = []
    if doc.title:
        qs.append(doc.title)
    # first paragraph(s) of the page are usually the page summary
    for p in paras[:2]:
        if len(p.text) > 40:
            qs.append(p.text[:140])
    # lightweight Turkish hints for your site
    hints = ["iletişim", "work sayfası", "oyun", "bambi copilot", "bambi game", "workshops"]
    qs.extend(hints)
    # de-dupe
    seen = set()
    out = []
    for q in qs:
        q = _clean(q)
        if len(q) >= 4 and q.lower() not in seen:
            out.append(q);
            seen.add(q.lower())
    return out


def _negatives(from_doc_id: str, k: int) -> List[str]:
    # pick other paragraphs (other docs) as negatives
    negs = (Paragraph.objects
    .exclude(doc_id=from_doc_id)
    .order_by("?")
    .values_list("text", flat=True)[: max(k, 8)])
    return [_clean(t) for t in negs if len(_clean(t)) > 40][:k]


class Command(BaseCommand):
    help = "Export positive/negative text pairs for contrastive training (jsonl)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--out", type=str, default="data/pairs.jsonl")
        parser.add_argument("--neg_per_pos", type=int, default=3)
        parser.add_argument("--min_len", type=int, default=40)
        parser.add_argument("--max_pairs", type=int, default=200)

    def handle(self, *args, **opts):
        out_path = Path(opts["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        neg_per_pos: int = int(opts["neg_per_pos"])
        min_len: int = int(opts["min_len"])
        max_pairs: int = int(opts["max_pairs"])

        docs = list(Doc.objects.all().order_by("?"))
        if not docs:
            self.stderr.write("No docs indexed yet. Run: python manage.py copilot_index")
            return

        n_written = 0
        with out_path.open("w", encoding="utf-8") as f:
            for doc in docs:
                paras = list(Paragraph.objects.filter(doc=doc).order_by("order")[:10])
                if not paras:
                    # fallback split from the Doc body if Paragraphs table is empty
                    for t in _split_paragraphs(doc.text or "")[:10]:
                        paras.append(Paragraph(text=t, doc=doc, order=0))  # fake

                # choose a “positive passage” that actually carries meaning
                good_paras = [p for p in paras if len(_clean(p.text)) >= min_len]
                if not good_paras:
                    continue
                pos = _clean(max(good_paras, key=lambda p: len(p.text)).text)

                for q in _candidate_queries(doc, paras):
                    negs = _negatives(doc.id, neg_per_pos)
                    if not negs:
                        continue
                    item = {
                        "q": q,
                        "pos": pos,
                        "neg": negs,
                        "url": doc.url,
                        "title": _clean(doc.title or ""),
                    }
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    n_written += 1
                    if n_written >= max_pairs:
                        break
                if n_written >= max_pairs:
                    break

        self.stdout.write(f"Wrote {n_written} pairs → {out_path}")
