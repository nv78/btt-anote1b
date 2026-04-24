"""Small Hugging Face dataset importer for the Flask leaderboard.

The Personal repo contains a broader FastAPI/SQLAlchemy importer. This module
keeps the useful conversion behavior while matching this repo's lightweight
Flask API and optional dependency posture.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


TASK_DEFAULTS = {
    "text_classification": {"primary_metric": "accuracy", "answer_keys": ["label", "label_text", "answer"]},
    "document_qa": {"primary_metric": "exact", "answer_keys": ["answers", "answer"]},
    "line_qa": {"primary_metric": "exact", "answer_keys": ["answers", "answer"]},
    "translation": {"primary_metric": "bleu", "answer_keys": ["translation", "target", "answer"]},
}

KNOWN_DATASETS = {
    "ag_news": "text_classification",
    "imdb": "text_classification",
    "nyu-mll/glue": "text_classification",
    "squad": "document_qa",
    "rajpurkar/squad": "document_qa",
}


class HuggingFaceImportError(Exception):
    """Raised when a Hugging Face dataset cannot be loaded or converted."""


def _load_dataset(dataset_name: str, config: Optional[str], split: str):
    try:
        from datasets import load_dataset
    except Exception as exc:
        raise HuggingFaceImportError(
            "Install the optional 'datasets' package to import Hugging Face datasets."
        ) from exc

    try:
        if config:
            return load_dataset(dataset_name, config, split=split)
        return load_dataset(dataset_name, split=split)
    except Exception as exc:
        raise HuggingFaceImportError(f"Failed to load {dataset_name} ({split}): {exc}") from exc


def infer_task_type(dataset_name: str, requested_task_type: Optional[str] = None) -> str:
    if requested_task_type:
        return requested_task_type
    return KNOWN_DATASETS.get(dataset_name, "text_classification")


def _first_present(row: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _answer_from_row(row: Dict[str, Any], task_type: str) -> Any:
    answer = _first_present(row, TASK_DEFAULTS.get(task_type, TASK_DEFAULTS["text_classification"])["answer_keys"])
    if isinstance(answer, dict) and isinstance(answer.get("text"), list):
        return answer["text"][0] if len(answer["text"]) == 1 else answer["text"]
    if isinstance(answer, dict):
        return next(iter(answer.values()), "")
    if isinstance(answer, list) and len(answer) == 1:
        return answer[0]
    return answer


def _question_from_row(row: Dict[str, Any]) -> str:
    value = _first_present(row, ["question", "sentence", "text", "context", "premise", "review", "input"])
    if value is None:
        return str(row)
    return str(value)


def import_hf_dataset(
    dataset_name: str,
    config: Optional[str] = None,
    split: str = "test",
    limit: int = 100,
    task_type: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a bounded HF split and convert it to this leaderboard's reference_data shape."""
    if not dataset_name:
        raise HuggingFaceImportError("dataset_name is required")
    if limit < 1 or limit > 5000:
        raise HuggingFaceImportError("limit must be between 1 and 5000")

    resolved_task_type = infer_task_type(dataset_name, task_type)
    metric = TASK_DEFAULTS.get(resolved_task_type, TASK_DEFAULTS["text_classification"])["primary_metric"]
    ds = _load_dataset(dataset_name, config, split)
    count = min(limit, len(ds))

    source_texts = []
    answers = []
    labels = []
    ground_truth = []
    for idx in range(count):
        row = dict(ds[idx])
        question = _question_from_row(row)
        answer = _answer_from_row(row, resolved_task_type)
        source_texts.append(question)
        if resolved_task_type == "text_classification":
            labels.append(str(answer))
        else:
            answers.append(answer)
        ground_truth.append({"id": idx, "question": question, "answer": answer})

    reference_data: Dict[str, Any] = {
        "url": f"https://huggingface.co/datasets/{dataset_name}",
        "description": f"Imported from Hugging Face dataset {dataset_name}, split={split}.",
        "source_texts": source_texts,
        "ground_truth": ground_truth,
        "hf_dataset": dataset_name,
        "hf_config": config,
        "hf_split": split,
    }
    if labels:
        reference_data["labels"] = labels
    if answers:
        reference_data["answers"] = answers

    return {
        "name": display_name or f"{dataset_name} ({split})",
        "task_type": resolved_task_type,
        "evaluation_metric": metric,
        "reference_data": reference_data,
    }
