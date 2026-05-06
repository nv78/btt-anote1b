#!/usr/bin/env python3
"""
Run a fixed set of Hugging Face models against datasets that exist in the local DB.
Uses subprocess so each job loads/releases its own model (slower but safer on memory).

Requires: pip install transformers torch (and network for first-time model download).

This does NOT use OpenAI/Anthropic keys — inference is local HF only.

Example:
  cd Personal && PYTHONPATH=. python scripts/run_all_hf_evals.py
  PYTHONPATH=. python scripts/run_all_hf_evals.py --dry-run

Retry only QA + AG News (skip duplicate SST/IMDB/NER runs):
  PYTHONPATH=. python scripts/run_all_hf_evals.py --subset qa --subset classification \\
    --classification-dataset "AG News - Text Classification"
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _dataset_id_by_name(name: str) -> Optional[str]:
    from database import SessionLocal, init_db
    from models import Dataset

    init_db()
    db = SessionLocal()
    try:
        row = db.query(Dataset).filter(Dataset.name == name).first()
        return row.id if row else None
    finally:
        db.close()


def _run(cmd: List[str], *, dry_run: bool) -> int:
    print("\n" + "=" * 72, file=sys.stderr)
    print(" ", " ".join(cmd), file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    if dry_run:
        return 0
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    return int(r.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch HF model evaluations on leaderboard DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands only",
    )
    parser.add_argument(
        "--subset",
        action="append",
        choices=("classification", "qa", "ner"),
        help="Run only these groups (repeatable). Default: all three.",
    )
    parser.add_argument(
        "--classification-dataset",
        action="append",
        dest="classification_datasets",
        metavar="NAME",
        help="With classification subset: limit to these exact dataset names (repeatable).",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    subsets = set(args.subset) if args.subset else {"classification", "qa", "ner"}
    cls_filter = set(args.classification_datasets) if args.classification_datasets else None

    classification: List[Tuple[str, str, str]] = [
        ("SST-2 - Sentiment Analysis", "distilbert/distilbert-base-uncased-finetuned-sst-2-english", "sentiment-analysis"),
        ("SST-2 - Sentiment Analysis", "textattack/roberta-base-SST-2", "sentiment-analysis"),
        ("IMDB - Movie Review Sentiment", "distilbert/distilbert-base-uncased-finetuned-sst-2-english", "sentiment-analysis"),
        ("IMDB - Movie Review Sentiment", "textattack/roberta-base-SST-2", "sentiment-analysis"),
        (
            "Financial PhraseBank - Sentiment Analysis",
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "text-classification",
        ),
        ("FiQA - Financial Opinion Mining", "cardiffnlp/twitter-roberta-base-sentiment-latest", "text-classification"),
        ("AG News - Text Classification", "textattack/bert-base-uncased-ag-news", "text-classification"),
    ]

    qa_datasets = [
        "SQuAD - Question Answering",
        "XQUAD - Cross-Lingual Question Answering",
        "FinQA - Financial Numerical Reasoning",
    ]
    qa_models = [
        "distilbert-base-cased-distilled-squad",
        "deepset/roberta-base-squad2",
    ]

    ner_dataset = "Financial NER - Entity Recognition"
    ner_models = [
        "dslim/bert-base-NER",
        "dbmdz/bert-large-cased-finetuned-conll03-english",
    ]

    py = sys.executable
    failures: List[str] = []

    if "classification" in subsets:
        for ds_name, model_id, pipeline_task in classification:
            if cls_filter is not None and ds_name not in cls_filter:
                continue
            ds_id = _dataset_id_by_name(ds_name)
            if not ds_id:
                print(f"SKIP (dataset not in DB): {ds_name}", file=sys.stderr)
                continue
            cmd = [
                py,
                os.path.join(ROOT, "scripts", "run_hf_model_on_dataset.py"),
                "--dataset-id",
                ds_id,
                "--model-id",
                model_id,
                "--pipeline-task",
                pipeline_task,
                "--allow-missing-sentence-key",
            ]
            label = f"classification {ds_name!r} / {model_id}"
            code = _run(cmd, dry_run=args.dry_run)
            if code != 0:
                failures.append(label)

    if "qa" in subsets:
        for ds_name in qa_datasets:
            ds_id = _dataset_id_by_name(ds_name)
            if not ds_id:
                print(f"SKIP (dataset not in DB): {ds_name}", file=sys.stderr)
                continue
            for model_id in qa_models:
                cmd = [
                    py,
                    os.path.join(ROOT, "scripts", "run_hf_qa_on_dataset.py"),
                    "--dataset-id",
                    ds_id,
                    "--model-id",
                    model_id,
                ]
                label = f"qa {ds_name!r} / {model_id}"
                code = _run(cmd, dry_run=args.dry_run)
                if code != 0:
                    failures.append(label)

    if "ner" in subsets:
        ds_id = _dataset_id_by_name(ner_dataset)
        if not ds_id:
            print(f"SKIP (dataset not in DB): {ner_dataset}", file=sys.stderr)
        else:
            for model_id in ner_models:
                cmd = [
                    py,
                    os.path.join(ROOT, "scripts", "run_hf_ner_on_dataset.py"),
                    "--dataset-id",
                    ds_id,
                    "--model-id",
                    model_id,
                ]
                label = f"ner {ner_dataset!r} / {model_id}"
                code = _run(cmd, dry_run=args.dry_run)
                if code != 0:
                    failures.append(label)

    if failures:
        print("\nFailed jobs:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)
    print("\nAll HF batch jobs finished OK.", file=sys.stderr)


if __name__ == "__main__":
    main()
