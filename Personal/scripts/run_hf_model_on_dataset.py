#!/usr/bin/env python3
"""
Run a Hugging Face sentiment model on a text_classification dataset in the DB,
then evaluate via the normal Submission + evaluate_submission path.

Example:
  cd Personal && PYTHONPATH=. python scripts/run_hf_model_on_dataset.py \\
    --dataset-id hf_glue_sst2_validation \\
    --model-id distilbert/distilbert-base-uncased-finetuned-sst-2-english \\
    --limit 200
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="HF sentiment model -> predictions -> evaluate_submission")
    parser.add_argument("--dataset-id", required=True, help="Dataset.id in the leaderboard DB")
    parser.add_argument(
        "--model-id",
        default="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
        help="Hugging Face model id (sentiment-analysis)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max examples (default: all in dataset)")
    parser.add_argument("--batch-size", type=int, default=16, help="Pipeline batch size")
    parser.add_argument(
        "--allow-missing-sentence-key",
        action="store_true",
        help="Allow fallback to 'question' without a 'sentence' key (not recommended for SST-2)",
    )
    parser.add_argument(
        "--pipeline-task",
        choices=("sentiment-analysis", "text-classification"),
        default="sentiment-analysis",
        help="HF pipeline type (text-classification for AG News, 3-way sentiment, etc.)",
    )
    args = parser.parse_args()

    os.chdir(ROOT)

    from database import SessionLocal, init_db, DATABASE_URL
    from models import Dataset, Submission, SubmissionStatus, TaskType
    from evaluation_service import evaluate_submission
    from hf_runner_inference import (
        ground_truth_to_id_sentences,
        run_sentiment_pipeline_batched,
        run_text_classification_pipeline_batched,
        build_predictions_json,
        submission_model_name_from_id,
        check_transformers_torch,
    )

    check_transformers_torch()
    init_db()

    db = SessionLocal()
    try:
        ds = db.query(Dataset).filter(Dataset.id == args.dataset_id).first()
        if not ds:
            print(f"Dataset not found: {args.dataset_id!r}", file=sys.stderr)
            print(f"DATABASE_URL={DATABASE_URL!r}", file=sys.stderr)
            others = db.query(Dataset).order_by(Dataset.id).limit(30).all()
            if others:
                print("Existing datasets in this database (id — name):", file=sys.stderr)
                for row in others:
                    tt = row.task_type.value if row.task_type else "?"
                    print(f"  {row.id!r} — {row.name!r} ({tt})", file=sys.stderr)
            else:
                print("No datasets in this database yet.", file=sys.stderr)
            print(
                "Import SST-2 into the same DB first, e.g.\n"
                "  PYTHONPATH=. python scripts/import_hf_dataset.py \\\n"
                "    --dataset nyu-mll/glue --config sst2 --split validation \\\n"
                "    --dataset-id hf_glue_sst2_validation --limit 200",
                file=sys.stderr,
            )
            sys.exit(1)
        if ds.task_type != TaskType.TEXT_CLASSIFICATION:
            print(
                f"Expected task_type=text_classification, got {ds.task_type.value!r}",
                file=sys.stderr,
            )
            sys.exit(1)

        gt = list(ds.ground_truth or [])
        if args.limit is not None:
            gt = gt[: max(0, args.limit)]
        if not gt:
            print("No examples to evaluate (empty ground_truth or limit=0).", file=sys.stderr)
            sys.exit(1)

        id_sentences = ground_truth_to_id_sentences(
            gt,
            require_sentence_key=not args.allow_missing_sentence_key,
        )
        example_ids = [t[0] for t in id_sentences]
        sentences = [t[1] for t in id_sentences]

        if args.pipeline_task == "sentiment-analysis":
            labels = run_sentiment_pipeline_batched(
                args.model_id,
                sentences,
                batch_size=args.batch_size,
            )
        else:
            labels = run_text_classification_pipeline_batched(
                args.model_id,
                sentences,
                batch_size=args.batch_size,
            )
        predictions = build_predictions_json(example_ids, labels)

        pred_ids = {p["id"] for p in predictions}
        gt_ids = {item["id"] for item in gt}
        if pred_ids != gt_ids:
            missing = gt_ids - pred_ids
            extra = pred_ids - gt_ids
            print(
                f"Predictions must cover exactly all example ids. "
                f"missing={sorted(missing)[:20]!r} extra={sorted(extra)[:20]!r}",
                file=sys.stderr,
            )
            sys.exit(1)

        model_name = submission_model_name_from_id(args.model_id)
        submission_id = str(uuid.uuid4())
        meta = {
            "model_id": args.model_id,
            "provider": "huggingface",
            "task": args.pipeline_task,
            "dataset_id": args.dataset_id,
            "num_examples_evaluated": len(predictions),
            "batch_size": args.batch_size,
        }
        sub = Submission(
            id=submission_id,
            dataset_id=ds.id,
            model_name=model_name,
            model_version=args.model_id.split("/")[-1][:100],
            predictions=predictions,
            status=SubmissionStatus.PENDING,
            submission_metadata=meta,
            is_internal=False,
        )
        db.add(sub)
        db.commit()

        evaluate_submission(submission_id)
        db.refresh(sub)

        if sub.status != SubmissionStatus.COMPLETED:
            print(sub.error_message or "Evaluation failed", file=sys.stderr)
            sys.exit(1)

        print(f"submission_id={submission_id}")
        print(f"model_name={model_name}")
        print(f"dataset_id={ds.id}")
        print(f"primary_score={sub.primary_score}")
        print(f"primary_metric={ds.primary_metric}")
        print("detailed_scores:")
        for k, v in sorted((sub.detailed_scores or {}).items()):
            print(f"  {k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
