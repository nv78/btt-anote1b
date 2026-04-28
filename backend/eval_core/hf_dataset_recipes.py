"""
Hugging Face dataset recipes: canonical conversion from HF rows to leaderboard ground_truth.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from datasets import load_dataset

GLUE_HF_ID = "nyu-mll/glue"
GLUE_SST2_CONFIG = "sst2"

SQUAD_HF_ID = "squad"
CONLL_HF_ID = "conll2003"

SST2_ID_LABEL = {0: "negative", 1: "positive"}


def sst2_row_to_ground_truth_item(
    idx: int,
    split: str,
    sentence: str,
    label: int,
) -> Dict[str, Any]:
    """One leaderboard ground-truth dict for GLUE SST-2."""
    if label not in SST2_ID_LABEL:
        raise ValueError(
            f"GLUE SST-2 has no usable label for scoring at index {idx}: {label!r}. "
            "Use train or validation split; test labels are typically unset (-1)."
        )
    answer = SST2_ID_LABEL[label]
    ex_id = f"sst2_{split}_{idx}"
    return {
        "id": ex_id,
        "question": sentence,
        "sentence": sentence,
        "answer": answer,
        "metadata": {
            "source": "huggingface",
            "dataset_name": GLUE_HF_ID,
            "config": GLUE_SST2_CONFIG,
            "split": split,
            "hf_idx": idx,
        },
    }


def hf_rows_to_glue_sst2_ground_truth(
    rows: List[Dict[str, Any]],
    split: str,
) -> List[Dict[str, Any]]:
    """
    Convert HF-style row dicts (keys sentence, label) for unit tests without load_dataset.
    """
    ground_truth: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        sentence = row["sentence"]
        label = row["label"]
        ground_truth.append(sst2_row_to_ground_truth_item(idx, split, sentence, int(label)))
    return ground_truth


def load_glue_sst2_ground_truth(
    split: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Load GLUE SST-2 from Hugging Face; only rows with labels 0/1 are kept for scoring.

    Raises:
        ValueError: unlabeled / invalid labels (e.g. test split with -1).
    """
    ds = load_dataset(GLUE_HF_ID, GLUE_SST2_CONFIG, split=split)
    n = len(ds)
    if limit is not None:
        n = min(n, limit)
    ground_truth: List[Dict[str, Any]] = []
    for idx in range(n):
        row = ds[idx]
        ground_truth.append(
            sst2_row_to_ground_truth_item(
                idx,
                split,
                str(row["sentence"]),
                int(row["label"]),
            )
        )
    return ground_truth


def build_glue_sst2_import_payload(
    split: str = "validation",
    limit: Optional[int] = None,
    leaderboard_dataset_id: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full dataset dict for DB persistence (matches Dataset model fields, plus optional id).
    """
    ground_truth = load_glue_sst2_ground_truth(split=split, limit=limit)
    split_slug = split.replace("-", "_")
    lid = leaderboard_dataset_id or f"hf_glue_sst2_{split_slug}"
    name = display_name or (
        "GLUE SST-2 Validation"
        if split == "validation"
        else f"GLUE SST-2 ({split})"
    )
    return {
        "id": lid,
        "name": name,
        "description": (
            f"GLUE SST-2 ({GLUE_SST2_CONFIG}) from {GLUE_HF_ID}, split={split!r}, "
            f"{len(ground_truth)} examples. Labels: 0→negative, 1→positive."
        ),
        "url": f"https://huggingface.co/datasets/{GLUE_HF_ID}",
        "task_type": "text_classification",
        "test_set_public": False,
        "labels_public": False,
        "primary_metric": "accuracy",
        "additional_metrics": ["f1", "precision", "recall"],
        "ground_truth": ground_truth,
    }


def iob_tag_strings_to_spans(tokens: List[str], tags: List[str]) -> List[Tuple[str, str]]:
    """IOB2 tags (e.g. B-PER, I-PER, O) + tokens → [(surface phrase, type), ...]."""
    spans: List[Tuple[str, str]] = []
    start: Optional[int] = None
    current_type: Optional[str] = None

    def close_end(i: int) -> None:
        nonlocal start, current_type
        if start is not None and current_type is not None:
            spans.append((" ".join(tokens[start:i]), current_type))
        start = None
        current_type = None

    for i, tag in enumerate(tags):
        t = str(tag).strip()
        if t in ("O", "0", "") or t.upper() == "O":
            close_end(i)
            continue
        if t.startswith("B-"):
            close_end(i)
            start = i
            current_type = t[2:]
        elif t.startswith("I-"):
            tname = t[2:]
            if start is None:
                start = i
                current_type = tname
            elif tname != current_type:
                close_end(i)
                start = i
                current_type = tname
        else:
            close_end(i)

    close_end(len(tokens))
    return spans


def load_squad_ground_truth(
    split: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    try:
        ds = load_dataset(SQUAD_HF_ID, split=split)
    except Exception:
        ds = load_dataset("rajpurkar/squad", split=split)
    n = len(ds)
    if limit is not None:
        n = min(n, limit)
    ground_truth: List[Dict[str, Any]] = []
    for idx in range(n):
        row = ds[idx]
        ex_id = str(row["id"])
        texts = row["answers"]["text"]
        if not texts:
            continue
        ans = texts if len(texts) == 1 else list(texts)
        if isinstance(ans, list) and len(ans) > 1:
            answer_field: Any = ans
        else:
            answer_field = ans[0] if isinstance(ans, list) else ans
        ground_truth.append(
            {
                "id": ex_id,
                "question": row["question"],
                "context": row["context"],
                "answer": answer_field,
                "metadata": {
                    "source": "huggingface",
                    "dataset_name": SQUAD_HF_ID,
                    "split": split,
                    "hf_idx": idx,
                },
            }
        )
    return ground_truth


def build_squad_import_payload(
    split: str = "validation",
    limit: Optional[int] = None,
    leaderboard_dataset_id: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    ground_truth = load_squad_ground_truth(split=split, limit=limit)
    split_slug = split.replace("-", "_")
    lid = leaderboard_dataset_id or f"hf_squad_{split_slug}"
    name = display_name or f"SQuAD ({split})"
    return {
        "id": lid,
        "name": name,
        "description": (
            f"Extractive QA from {SQUAD_HF_ID}, split={split!r}, {len(ground_truth)} examples."
        ),
        "url": "https://huggingface.co/datasets/rajpurkar/squad",
        "task_type": "document_qa",
        "test_set_public": False,
        "labels_public": False,
        "primary_metric": "exact_match",
        "additional_metrics": ["f1", "token_f1", "bleu"],
        "ground_truth": ground_truth,
    }


def load_conll2003_ground_truth(
    split: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    ds = load_dataset(CONLL_HF_ID, split=split, trust_remote_code=True)
    ner_feature = ds.features["ner_tags"]
    tag_names = list(ner_feature.feature.names)
    n = len(ds)
    if limit is not None:
        n = min(n, limit)
    ground_truth: List[Dict[str, Any]] = []
    for idx in range(n):
        row = ds[idx]
        tokens = [str(t) for t in row["tokens"]]
        tags = [tag_names[int(i)] for i in row["ner_tags"]]
        entities = iob_tag_strings_to_spans(tokens, tags)
        text = " ".join(tokens)
        ex_id = f"conll2003_{split}_{idx}"
        serializable_answers = [[e[0], e[1]] for e in entities]
        ground_truth.append(
            {
                "id": ex_id,
                "text": text,
                "question": text,
                "tokens": tokens,
                "answer": serializable_answers,
                "metadata": {
                    "source": "huggingface",
                    "dataset_name": CONLL_HF_ID,
                    "split": split,
                    "hf_idx": idx,
                },
            }
        )
    return ground_truth


def build_conll2003_import_payload(
    split: str = "validation",
    limit: Optional[int] = None,
    leaderboard_dataset_id: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    ground_truth = load_conll2003_ground_truth(split=split, limit=limit)
    split_slug = split.replace("-", "_")
    lid = leaderboard_dataset_id or f"hf_conll2003_{split_slug}"
    name = display_name or f"CoNLL-2003 English NER ({split})"
    return {
        "id": lid,
        "name": name,
        "description": (
            f"CoNLL-2003 from {CONLL_HF_ID}, split={split!r}, {len(ground_truth)} sentences."
        ),
        "url": f"https://huggingface.co/datasets/{CONLL_HF_ID}",
        "task_type": "named_entity_recognition",
        "test_set_public": False,
        "labels_public": False,
        "primary_metric": "f1",
        "additional_metrics": ["precision", "recall", "partial_f1"],
        "ground_truth": ground_truth,
    }


# Recipe key: (hf_dataset_id lowercased, config lowercased)
RECIPE_IMPORTERS = {
    (GLUE_HF_ID.lower(), GLUE_SST2_CONFIG.lower()): build_glue_sst2_import_payload,
    (SQUAD_HF_ID.lower(), "default"): build_squad_import_payload,
    (CONLL_HF_ID.lower(), "default"): build_conll2003_import_payload,
}


def try_recipe_import(
    dataset_name: str,
    config: str,
    split: str,
    limit: Optional[int],
    leaderboard_dataset_id: Optional[str],
    display_name: Optional[str],
) -> Optional[Dict[str, Any]]:
    """If a registered recipe matches, return import payload; else None."""
    key = (dataset_name.strip().lower(), config.strip().lower())
    builder = RECIPE_IMPORTERS.get(key)
    if not builder:
        return None
    return builder(
        split=split,
        limit=limit,
        leaderboard_dataset_id=leaderboard_dataset_id,
        display_name=display_name,
    )
