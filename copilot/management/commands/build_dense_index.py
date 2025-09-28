# copilot/management/commands/build_dense_index.py
from __future__ import annotations
import json, os, uuid, pathlib
from django.core.management.base import BaseCommand
from sentence_transformers import SentenceTransformer
import numpy as np

try:
    import faiss  # type: ignore
except Exception:
    faiss = None

from copilot.models import Doc
from copilot.retrieval import _split_paragraphs  # you already have this

def _iter_paragraphs(min_len=50, max_len=900):
    for d in Doc.objects.all().iterator():
        text = (d.text or "").strip()
        if not text:
            continue
        for p in _split_paragraphs(text):
            p = p.strip()
            if min_len <= len(p) <= max_len:
                yield {
                    "pid": uuid.uuid4().hex[:16],
                    "doc_id": d.id,
                    "url": d.url,
                    "title": d.title or "",
                    "text": p,
                }

class Command(BaseCommand):
    help = "Encode paragraphs and build a FAISS index for dense retrieval."

    def add_arguments(self, parser):
        parser.add_argument("--model_path", default=os.environ.get("COPILOT_EMBED_MODEL", "models/copilot-embed"))
        parser.add_argument("--out_dir", default="copilot_index")
        parser.add_argument("--batch_size", type=int, default=64)

    def handle(self, *args, **opt):
        model_path = opt["model_path"]
        out_dir = pathlib.Path(opt["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        pages = list(_iter_paragraphs())
        if not pages:
            self.stdout.write(self.style.ERROR("No paragraphs found. Index your site first."))
            return

        texts = [p["text"] for p in pages]
        self.stdout.write(f"Encoding {len(texts)} paragraphs with {model_path} ...")
        model = SentenceTransformer(model_path)
        vecs = model.encode(
            texts,
            batch_size=opt["batch_size"],
            convert_to_numpy=True,
            show_progress_bar=True,
            normalize_embeddings=True,  # cosine on IP index
        )

        # Save corpus
        (out_dir / "corpus.jsonl").write_text(
            "\n".join(json.dumps(p, ensure_ascii=False) for p in pages),
            encoding="utf-8",
        )
        npy_path = out_dir / "embeddings.npy"
        np.save(npy_path, vecs)

        if faiss is None:
            self.stdout.write(self.style.WARNING("faiss not installed; saved embeddings only."))
            return

        dim = vecs.shape[1]
        index = faiss.IndexFlatIP(dim)  # cosine because we normalized
        index.add(vecs)
        faiss.write_index(index, str(out_dir / "faiss.index"))
        self.stdout.write(self.style.SUCCESS(f"Index built → {out_dir}"))
