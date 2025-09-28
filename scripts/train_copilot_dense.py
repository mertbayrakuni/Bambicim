# scripts/train_copilot_dense.py
from __future__ import annotations

import json
import random
from pathlib import Path

from sentence_transformers import SentenceTransformer, losses, InputExample
from sentence_transformers.evaluation import InformationRetrievalEvaluator
from torch.utils.data import DataLoader

PAIR_PATH = Path("data/pairs.jsonl")
OUT_DIR = Path("models/copilot-embed")
BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # small & fast

OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- load pairs ---
pairs = []
with PAIR_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        pairs.append(json.loads(line))

if len(pairs) < 10:
    raise SystemExit("Not enough pairs. Export at least ~50 (max_pairs) before training.")

random.shuffle(pairs)

# split train/dev for evaluation every N steps
cut = int(len(pairs) * 0.9)
train_pairs = pairs[:cut]
dev_pairs = pairs[cut:]

# build training examples
train_samples = []
for p in train_pairs:
    # MultipleNegativesRankingLoss: (anchor, positive) pairs. Negatives come from other batch items.
    train_samples.append(InputExample(texts=[p["q"], p["pos"]]))

train_loader = DataLoader(train_samples, shuffle=True, batch_size=64, drop_last=True)

model = SentenceTransformer(BASE_MODEL)

# loss
loss = losses.MultipleNegativesRankingLoss(model)

# lightweight IR evaluator from the held-out set
# (maps query -> {doc_id: text}, and relevant doc_ids)
corpus = {}
queries = {}
relevant = {}
for i, p in enumerate(dev_pairs):
    doc_id = f"d{i}"
    corpus[doc_id] = p["pos"]
    q_id = f"q{i}"
    queries[q_id] = p["q"]
    relevant[q_id] = {doc_id: 1}

evaluator = InformationRetrievalEvaluator(
    queries=queries, corpus=corpus, relevant_docs=relevant, name="dev",
    show_progress_bar=True
)

# train
model.fit(
    train_objectives=[(train_loader, loss)],
    epochs=2,
    warmup_steps=max(50, int(len(train_loader) * 0.1)),
    evaluator=evaluator,
    evaluation_steps=200,  # run small eval every 200 steps
    output_path=str(OUT_DIR),
    use_amp=True,  # mixed precision for speed
)
print(f"Saved fine-tuned model → {OUT_DIR}")
