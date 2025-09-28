# scripts/train_copilot_dense.py
from __future__ import annotations
import os, json, random
from pathlib import Path
import torch
from sentence_transformers import SentenceTransformer, losses, InputExample
from sentence_transformers.evaluation import InformationRetrievalEvaluator
from torch.utils.data import DataLoader

PAIR_PATH = Path("data/pairs.jsonl")
OUT_DIR = Path("models/copilot-embed")
BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # fast & tiny

OUT_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

pairs = [json.loads(l) for l in PAIR_PATH.open("r", encoding="utf-8")]
if len(pairs) < 50:
    raise SystemExit(f"Need >=50 pairs, found {len(pairs)}")
random.shuffle(pairs)

# 90/10 split
cut = int(len(pairs) * 0.9)
train_pairs, dev_pairs = pairs[:cut], pairs[cut:]

train_samples = [InputExample(texts=[p["q"], p["pos"]]) for p in train_pairs]
batch_size = int(os.environ.get("BATCH", "32"))
train_loader = DataLoader(train_samples, shuffle=True, batch_size=batch_size, drop_last=True)

model = SentenceTransformer(BASE_MODEL)
loss = losses.MultipleNegativesRankingLoss(model)

# end-of-training evaluator (no step eval -> avoids HF 'eval_dataset' requirement)
corpus = {f"d{i}": p["pos"] for i, p in enumerate(dev_pairs)}
queries = {f"q{i}": p["q"] for i, p in enumerate(dev_pairs)}
relevant = {f"q{i}": {f"d{i}": 1} for i in range(len(dev_pairs))}
evaluator = InformationRetrievalEvaluator(queries, corpus, relevant, name="dev", show_progress_bar=True)

use_amp = torch.cuda.is_available()
warmup = max(50, int(len(train_loader) * 0.1))

model.fit(
    train_objectives=[(train_loader, loss)],
    epochs=2,
    warmup_steps=warmup,
    evaluator=evaluator,     # runs at end
    evaluation_steps=0,      # <- the fix
    output_path=str(OUT_DIR),
    use_amp=use_amp,
)
print(f"Saved fine-tuned model → {OUT_DIR}")
