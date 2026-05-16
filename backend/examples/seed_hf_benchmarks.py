"""
Seed real benchmark data from HuggingFace into the Leaderboard DB.

Usage (from Leaderboard/backend/):
    python examples/seed_hf_benchmarks.py

Each entry pulls from HuggingFace and inserts into benchmark_datasets.
Datasets already in the DB (by name) are skipped.

Requires: pip install datasets
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from anywhere inside backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
_bd = Path(__file__).resolve().parent.parent
load_dotenv(_bd / ".env")
load_dotenv(_bd.parent.parent / ".env", override=True)

from shared import get_db_connection, _STORE  # noqa: E402

try:
    from datasets import load_dataset
except ImportError:
    print("ERROR: Install the 'datasets' package first: pip install datasets")
    sys.exit(1)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _exists(name: str) -> bool:
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute("SELECT id FROM benchmark_datasets WHERE name = %s", (name,))
            return cursor.fetchone() is not None
        finally:
            try: cursor.close(); conn.close()
            except Exception: pass
    return any(d.get("name") == name for d in _STORE["datasets"])


def _insert(name: str, task_type: str, metric: str, reference_data: Dict[str, Any]) -> bool:
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active)"
                " VALUES (%s, %s, %s, %s, TRUE)",
                (name, task_type, metric, json.dumps(reference_data)),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"  DB error: {e}")
            return False
        finally:
            try: cursor.close(); conn.close()
            except Exception: pass
    # In-memory fallback
    _STORE["datasets"].append({"name": name, "task_type": task_type,
                                "evaluation_metric": metric, "reference_data": reference_data})
    return True


def seed(name: str, task_type: str, metric: str, reference_data: Dict[str, Any]) -> None:
    if _exists(name):
        print(f"  SKIP  {name!r} (already in DB)")
        return
    ok = _insert(name, task_type, metric, reference_data)
    n_q = len(reference_data.get("source_texts") or [])
    if ok:
        print(f"  OK    {name!r} — {n_q} questions, task={task_type}, metric={metric}")
    else:
        print(f"  FAIL  {name!r}")


# ── Dataset loaders ──────────────────────────────────────────────────────────

def _load_sst2(limit: int = 872) -> None:
    """GLUE SST-2 validation split (sentiment classification, 872 items)."""
    name = "GLUE SST-2 - Sentiment Classification"
    print(f"\nLoading {name}…")
    ds = load_dataset("nyu-mll/glue", "sst2", split="validation")
    label_names = ["negative", "positive"]
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        sentence = str(row["sentence"])
        label = int(row["label"])
        if label not in (0, 1): continue
        source_texts.append(sentence)
        ground_truth.append({"id": idx, "question": sentence, "answer": label_names[label]})
    seed(name, "text_classification", "accuracy", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "label_names": label_names,
        "url": "https://huggingface.co/datasets/nyu-mll/glue",
        "description": f"GLUE SST-2 validation split — {len(source_texts)} sentiment examples.",
        "hf_dataset": "nyu-mll/glue", "hf_config": "sst2", "hf_split": "validation",
    })


def _load_ag_news(limit: int = 1000) -> None:
    """AG News test split (4-class news topic classification)."""
    name = "AG News - Topic Classification"
    print(f"\nLoading {name}…")
    ds = load_dataset("ag_news", split="test")
    label_names = ["World", "Sports", "Business", "Sci/Tech"]
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        text = str(row["text"])
        label = int(row["label"])
        source_texts.append(text)
        ground_truth.append({"id": idx, "question": text, "answer": label_names[label]})
    seed(name, "text_classification", "accuracy", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "label_names": label_names,
        "url": "https://huggingface.co/datasets/ag_news",
        "description": f"AG News test split — {len(source_texts)} news topic examples.",
        "hf_dataset": "ag_news", "hf_config": "default", "hf_split": "test",
    })


def _load_squad(limit: int = 500) -> None:
    """SQuAD validation split (extractive QA)."""
    name = "SQuAD - Extractive Q&A"
    print(f"\nLoading {name}…")
    try:
        ds = load_dataset("squad", split="validation")
    except Exception:
        ds = load_dataset("rajpurkar/squad", split="validation")
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        q = str(row["question"])
        ctx = str(row["context"])
        texts = row["answers"]["text"]
        if not texts: continue
        answer = texts[0] if len(texts) == 1 else list(texts)
        display = f"Context: {ctx[:300]}{'…' if len(ctx)>300 else ''}\n\nQuestion: {q}"
        source_texts.append(display)
        ground_truth.append({"id": str(row["id"]), "question": q, "context": ctx, "answer": answer})
    seed(name, "document_qa", "exact_match", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "url": "https://huggingface.co/datasets/rajpurkar/squad",
        "description": f"SQuAD v1.1 validation split — {len(source_texts)} QA pairs.",
        "hf_dataset": "squad", "hf_config": "default", "hf_split": "validation",
    })


def _load_conll2003(limit: int = 500) -> None:
    """CoNLL-2003 English NER validation split."""
    name = "CoNLL-2003 NER"
    print(f"\nLoading {name}…")
    ds = load_dataset("conll2003", split="validation", trust_remote_code=True)
    ner_feature = ds.features["ner_tags"]
    tag_names = list(ner_feature.feature.names)

    def iob_to_spans(tokens, tags):
        spans, start, ctype = [], None, None
        def close(i):
            nonlocal start, ctype
            if start is not None:
                spans.append([" ".join(tokens[start:i]), ctype])
            start = ctype = None
        for i, t in enumerate(tags):
            t = str(t)
            if t in ("O", "0", ""): close(i); continue
            if t.startswith("B-"): close(i); start = i; ctype = t[2:]
            elif t.startswith("I-"):
                if start is None: start = i; ctype = t[2:]
                elif t[2:] != ctype: close(i); start = i; ctype = t[2:]
        close(len(tokens))
        return spans

    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        tokens = [str(t) for t in row["tokens"]]
        tags = [tag_names[int(i)] for i in row["ner_tags"]]
        text = " ".join(tokens)
        entities = iob_to_spans(tokens, tags)
        source_texts.append(text)
        ground_truth.append({"id": f"conll_{idx}", "question": text, "tokens": tokens, "answer": entities})
    seed(name, "named_entity_recognition", "f1", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "url": "https://huggingface.co/datasets/conll2003",
        "description": f"CoNLL-2003 English NER validation — {len(source_texts)} sentences.",
        "hf_dataset": "conll2003", "hf_config": "default", "hf_split": "validation",
    })


def _load_gsm8k(limit: int = 500) -> None:
    """GSM8K math word problems test split."""
    name = "GSM8K - Math Reasoning"
    print(f"\nLoading {name}…")
    ds = load_dataset("openai/gsm8k", "main", split="test")
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        q = str(row["question"])
        ans_raw = str(row["answer"])
        # Final numeric answer follows "#### "
        numeric = ans_raw.split("####")[-1].strip().replace(",", "")
        source_texts.append(q)
        ground_truth.append({"id": idx, "question": q, "answer": numeric, "full_solution": ans_raw})
    seed(name, "math_reasoning", "accuracy", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "url": "https://huggingface.co/datasets/openai/gsm8k",
        "description": f"GSM8K test split — {len(source_texts)} grade-school math word problems.",
        "hf_dataset": "openai/gsm8k", "hf_config": "main", "hf_split": "test",
    })


def _load_snli(limit: int = 500) -> None:
    """SNLI validation split (natural language inference)."""
    name = "SNLI - Natural Language Inference"
    print(f"\nLoading {name}…")
    ds = load_dataset("stanfordnlp/snli", split="validation")
    label_names = ["entailment", "neutral", "contradiction"]
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        label = int(row["label"])
        if label == -1: continue  # unlabeled
        premise = str(row["premise"])
        hypothesis = str(row["hypothesis"])
        display = f"Premise: {premise}\nHypothesis: {hypothesis}"
        source_texts.append(display)
        ground_truth.append({"id": idx, "question": display, "premise": premise,
                              "hypothesis": hypothesis, "answer": label_names[label]})
    seed(name, "natural_language_inference", "accuracy", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "label_names": label_names,
        "url": "https://huggingface.co/datasets/stanfordnlp/snli",
        "description": f"SNLI validation split — {len(source_texts)} NLI examples.",
        "hf_dataset": "stanfordnlp/snli", "hf_config": "default", "hf_split": "validation",
    })


def _load_xsum(limit: int = 300) -> None:
    """XSum validation split (summarization)."""
    name = "XSum - News Summarization"
    print(f"\nLoading {name}…")
    ds = load_dataset("EdinburghNLP/xsum", split="validation")
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        doc = str(row["document"])
        summary = str(row["summary"])
        display = doc[:500] + ("…" if len(doc) > 500 else "")
        source_texts.append(display)
        ground_truth.append({"id": str(row["id"]), "question": display, "answer": summary})
    seed(name, "summarization", "rouge", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "url": "https://huggingface.co/datasets/EdinburghNLP/xsum",
        "description": f"XSum validation split — {len(source_texts)} news summarization examples.",
        "hf_dataset": "EdinburghNLP/xsum", "hf_config": "default", "hf_split": "validation",
    })


def _load_arc(limit: int = 500) -> None:
    """ARC Challenge test split (multiple-choice science QA)."""
    name = "ARC Challenge - Science Q&A"
    print(f"\nLoading {name}…")
    ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test")
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        q = str(row["question"])
        choices = row["choices"]
        labels_list = choices["label"]
        texts_list = choices["text"]
        answer_key = str(row["answerKey"])
        options = "\n".join(f"{l}) {t}" for l, t in zip(labels_list, texts_list))
        display = f"{q}\n{options}"
        source_texts.append(display)
        ground_truth.append({"id": str(row["id"]), "question": q, "choices": dict(zip(labels_list, texts_list)),
                              "answer": answer_key})
    seed(name, "multiple_choice_qa", "accuracy", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "url": "https://huggingface.co/datasets/allenai/ai2_arc",
        "description": f"ARC Challenge test split — {len(source_texts)} multiple-choice science questions.",
        "hf_dataset": "allenai/ai2_arc", "hf_config": "ARC-Challenge", "hf_split": "test",
    })


def _load_tweet_eval_sentiment(limit: int = 500) -> None:
    """TweetEval sentiment test split."""
    name = "TweetEval - Sentiment"
    print(f"\nLoading {name}…")
    ds = load_dataset("cardiffnlp/tweet_eval", "sentiment", split="test")
    label_names = ["negative", "neutral", "positive"]
    source_texts, ground_truth = [], []
    for idx, row in enumerate(ds):
        if idx >= limit: break
        text = str(row["text"])
        label = int(row["label"])
        source_texts.append(text)
        ground_truth.append({"id": idx, "question": text, "answer": label_names[label]})
    seed(name, "text_classification", "accuracy", {
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "label_names": label_names,
        "url": "https://huggingface.co/datasets/cardiffnlp/tweet_eval",
        "description": f"TweetEval sentiment test — {len(source_texts)} tweet sentiment examples.",
        "hf_dataset": "cardiffnlp/tweet_eval", "hf_config": "sentiment", "hf_split": "test",
    })


# ── Main ─────────────────────────────────────────────────────────────────────

BENCHMARKS = [
    ("SST-2 sentiment",         _load_sst2),
    ("AG News",                 _load_ag_news),
    ("SQuAD QA",                _load_squad),
    ("CoNLL-2003 NER",          _load_conll2003),
    ("GSM8K math",              _load_gsm8k),
    ("SNLI NLI",                _load_snli),
    ("XSum summarization",      _load_xsum),
    ("ARC Challenge",           _load_arc),
    ("TweetEval sentiment",     _load_tweet_eval_sentiment),
]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed HF benchmark datasets into the leaderboard DB")
    parser.add_argument("--only", nargs="*", help="Run only these benchmarks by keyword (e.g. sst2 squad)")
    args = parser.parse_args()

    only = [k.lower() for k in (args.only or [])]

    print("=== Seeding HuggingFace benchmarks ===")
    for label, fn in BENCHMARKS:
        if only and not any(k in label.lower() for k in only):
            continue
        try:
            fn()
        except Exception as e:
            print(f"  ERROR loading {label}: {e}")

    print("\n=== Done ===")
