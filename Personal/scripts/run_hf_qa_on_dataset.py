#!/usr/bin/env python3
"""
Run a Hugging Face extractive QA model on a document_qa dataset in the DB.

Example:
  cd Personal && PYTHONPATH=. python scripts/run_hf_qa_on_dataset.py \\
    --dataset-id hf_squad_validation \\
    --model-id distilbert-base-cased-distilled-squad \\
    --limit 50
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
    parser = argparse.ArgumentParser(description="HF extractive QA -> predictions -> evaluate_submission")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--model-id",
        default="distilbert-base-cased-distilled-squad",
        help="HF model id for question-answering pipeline",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    os.chdir(ROOT)

    from database import SessionLocal, init_db, DATABASE_URL
    from models import Dataset, Submission, SubmissionStatus, TaskType
    from evaluation_service import evaluate_submission
    from hf_runner_inference import check_transformers_torch, submission_model_name_from_id

    check_transformers_torch()
    init_db()

    db = SessionLocal()
    try:
        ds = db.query(Dataset).filter(Dataset.id == args.dataset_id).first()
        if not ds:
            print(f"Dataset not found: {args.dataset_id!r}\nDATABASE_URL={DATABASE_URL!r}", file=sys.stderr)
            sys.exit(1)
        if ds.task_type not in (TaskType.DOCUMENT_QA, TaskType.LINE_QA):
            print(f"Expected document_qa or line_qa, got {ds.task_type.value!r}", file=sys.stderr)
            sys.exit(1)

        gt = list(ds.ground_truth or [])
        if args.limit is not None:
            gt = gt[: max(0, args.limit)]
        if not gt:
            print("No examples to evaluate.", file=sys.stderr)
            sys.exit(1)

        for i, item in enumerate(gt):
            if "question" not in item:
                print(f"ground_truth[{i}] missing question for id={item.get('id')!r}", file=sys.stderr)
                sys.exit(1)

        from hf_runner_inference import load_extractive_qa_model, extractive_qa_answer

        tokenizer, qa_model, device = load_extractive_qa_model(args.model_id)
        predictions = []
        for item in gt:
            ctx = item.get("context")
            if ctx is None:
                ctx = ""
            answer = extractive_qa_answer(
                tokenizer,
                qa_model,
                device,
                str(item["question"]),
                str(ctx),
            )
            predictions.append({"id": item["id"], "prediction": answer})

        gt_ids = {item["id"] for item in gt}
        if {p["id"] for p in predictions} != gt_ids:
            print("Prediction id set does not match ground truth.", file=sys.stderr)
            sys.exit(1)

        model_name = submission_model_name_from_id(args.model_id)
        submission_id = str(uuid.uuid4())
        meta = {
            "model_id": args.model_id,
            "provider": "huggingface",
            "task": "question-answering",
            "dataset_id": args.dataset_id,
            "num_examples_evaluated": len(predictions),
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
