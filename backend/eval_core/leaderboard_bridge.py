"""
Convert Leaderboard /public/submit_model parallel lists into Personal evaluator
ground_truth + predictions shapes, run evaluators, resolve primary score.
"""
from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, Tuple

from eval_core.evaluators import get_evaluator

# Metrics where bootstrap CI is cheap (pure Python counting). Skip for
# BLEU/BERTScore/ROUGE which are slow per-call.
_CI_FAST_METRICS = frozenset({
    "accuracy", "f1", "f1_macro", "micro_f1", "exact_match",
    "precision", "recall", "balanced_accuracy",
    "retrieval_accuracy", "mrr",
})


def normalize_task_type(task_type: Optional[str]) -> str:
    if not task_type:
        return "text_classification"
    t = str(task_type).lower().strip()
    aliases = {
        "ner": "named_entity_recognition",
        "qa": "document_qa",
        "chatbot": "document_qa",
        "prompting": "line_qa",
        "mc": "multiple_choice_qa",
        "multiple_choice": "multiple_choice_qa",
        "nli": "natural_language_inference",
        "math": "math_reasoning",
        "code": "code_generation",
        "summarize": "summarization",
        "fact_check": "fact_verification",
        "retrieval_augmented_generation": "retrieval",
        "rag": "retrieval",
    }
    return aliases.get(t, t)


# Task types that compare a predicted answer string against a reference answer string (accuracy).
_ANSWER_COMPARISON_TASKS = frozenset({
    "multiple_choice_qa",
    "math_reasoning",
    "natural_language_inference",
    "fact_verification",
    "semantic_similarity",
    "code_generation",
    "summarization",
    "retrieval",
    "dialogue",
    "line_qa",
})


def normalize_eval_metric(metric: Optional[str], task_norm: str) -> str:
    m = (metric or "").lower().strip()
    if not m:
        if task_norm == "text_classification":
            return "accuracy"
        if task_norm in ("document_qa", "line_qa"):
            return "exact_match"
        if task_norm == "named_entity_recognition":
            return "f1"
        if task_norm == "translation":
            return "bleu"
        if task_norm == "summarization":
            return "rouge"
        if task_norm in _ANSWER_COMPARISON_TASKS:
            return "accuracy"
        return "accuracy"
    if m == "exact":
        return "exact_match"
    if m == "primary":
        return normalize_eval_metric(None, task_norm)
    return m


def build_personal_eval_inputs(
    sentence_ids: List[int],
    task_type_raw: Optional[str],
    reference_labels: Optional[List[Any]],
    reference_entities: Optional[List[Any]],
    reference_answers: Optional[List[Any]],
    reference_translations: Optional[List[Any]],
    model_results: List[Any],
) -> Tuple[str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (task_norm, primary_metric, ground_truth, predictions)."""
    task_norm = normalize_task_type(task_type_raw)
    tt = task_norm

    ground_truth: List[Dict[str, Any]] = []
    predictions: List[Dict[str, Any]] = []

    if tt == "text_classification":
        if not reference_labels:
            raise ValueError("missing reference labels")
        for sid, ref, pred in zip(sentence_ids, reference_labels, model_results):
            eid = str(sid)
            ground_truth.append({"id": eid, "answer": ref})
            predictions.append({"id": eid, "prediction": pred})
    elif tt == "named_entity_recognition":
        if not reference_entities:
            raise ValueError("missing reference entities")
        for sid, ref, pred in zip(sentence_ids, reference_entities, model_results):
            eid = str(sid)
            ground_truth.append({"id": eid, "answer": ref})
            if isinstance(pred, list):
                predictions.append({"id": eid, "prediction": pred})
            else:
                parts = [p.strip() for p in str(pred).split(";") if p and str(p).strip()]
                predictions.append({"id": eid, "prediction": parts})
    elif tt in ("document_qa", "line_qa"):
        if not reference_answers:
            raise ValueError("missing reference answers")
        for sid, ref, pred in zip(sentence_ids, reference_answers, model_results):
            eid = str(sid)
            ref_s = ref if isinstance(ref, str) else (ref[0] if isinstance(ref, (list, tuple)) and ref else "")
            ground_truth.append({"id": eid, "answer": ref_s})
            predictions.append({"id": eid, "prediction": pred})
    elif tt == "translation":
        if not reference_translations:
            raise ValueError("missing reference translations")
        for sid, ref, pred in zip(sentence_ids, reference_translations, model_results):
            eid = str(sid)
            ground_truth.append({"id": eid, "answer": ref})
            predictions.append({"id": eid, "prediction": pred})
    elif tt in _ANSWER_COMPARISON_TASKS:
        # All these tasks reduce to: compare predicted string against reference answer string.
        # reference_answers is the unified field; reference_labels is an acceptable fallback
        # (e.g. NLI labels stored as classification labels).
        refs = reference_answers or reference_labels
        if not refs:
            raise ValueError(f"missing reference answers for task {tt!r}")
        for sid, ref, pred in zip(sentence_ids, refs, model_results):
            eid = str(sid)
            ref_s = ref if isinstance(ref, str) else (
                ref[0] if isinstance(ref, (list, tuple)) and ref else str(ref)
            )
            ground_truth.append({"id": eid, "answer": ref_s})
            predictions.append({"id": eid, "prediction": str(pred)})
    else:
        # Unknown task type — attempt a generic exact-match comparison.
        refs = reference_answers or reference_labels or reference_translations
        if not refs:
            raise ValueError(f"no reference data available for task {tt!r}")
        for sid, ref, pred in zip(sentence_ids, refs, model_results):
            eid = str(sid)
            ref_s = ref if isinstance(ref, str) else str(ref)
            ground_truth.append({"id": eid, "answer": ref_s})
            predictions.append({"id": eid, "prediction": str(pred)})

    primary = normalize_eval_metric(None, tt)
    return tt, primary, ground_truth, predictions


def _bootstrap_ci(
    ground_truth: List[Dict],
    predictions: List[Dict],
    evaluator,
    primary_metric: str,
    n_resamples: int = 200,
    ci_level: float = 0.95,
) -> Optional[Tuple[float, float]]:
    """Return (ci_low, ci_high) via nonparametric bootstrap, or None if not applicable."""
    if primary_metric not in _CI_FAST_METRICS:
        return None
    n = len(ground_truth)
    if n < 10:
        return None
    scores: List[float] = []
    for _ in range(n_resamples):
        idxs = [random.randint(0, n - 1) for _ in range(n)]
        # Re-index with sequential IDs so evaluator dicts don't collide on duplicate idxs
        gt_s = [{**ground_truth[i], "id": str(j)} for j, i in enumerate(idxs)]
        pr_s = [{**predictions[i], "id": str(j)} for j, i in enumerate(idxs)]
        try:
            det = evaluator.evaluate(gt_s, pr_s)
            v = det.get(primary_metric)
            if v is not None:
                scores.append(float(v))
        except Exception:
            pass
    if len(scores) < 20:
        return None
    scores.sort()
    lo = int((1 - ci_level) / 2 * len(scores))
    hi = int((1 + ci_level) / 2 * len(scores))
    return scores[lo], scores[min(hi, len(scores) - 1)]


def run_personal_eval(
    task_type_raw: Optional[str],
    evaluation_metric: Optional[str],
    sentence_ids: List[int],
    reference_labels: Optional[List[Any]],
    reference_entities: Optional[List[Any]],
    reference_answers: Optional[List[Any]],
    reference_translations: Optional[List[Any]],
    model_results: List[Any],
) -> Tuple[float, Dict[str, Any]]:
    """Compute primary score, full detailed_scores dict, and 95% bootstrap CI."""
    tt, _default_primary, gt, preds = build_personal_eval_inputs(
        sentence_ids,
        task_type_raw,
        reference_labels,
        reference_entities,
        reference_answers,
        reference_translations,
        model_results,
    )
    requested = normalize_eval_metric(evaluation_metric, tt)
    evaluator = get_evaluator(tt)
    detailed = evaluator.evaluate(gt, preds)
    score = _pick_primary(detailed, requested, tt)
    ci = _bootstrap_ci(gt, preds, evaluator, requested)
    if ci is not None:
        detailed["ci_low"] = round(ci[0], 6)
        detailed["ci_high"] = round(ci[1], 6)
        detailed["ci_level"] = 0.95
    return float(score), detailed


def _pick_primary(detailed: Dict[str, Any], requested: str, task_norm: str) -> float:
    """Map Leaderboard dataset metric names to keys returned by Personal evaluators."""
    order: List[str] = []
    if requested in ("exact_match", "exact"):
        order = ["exact_match", "exact", "f1"]
    elif requested == "f1" and task_norm in ("document_qa", "line_qa"):
        order = ["f1", "token_f1", "exact_match"]
    elif requested == "bertscore":
        order = ["bertscore", "bertscore_unavailable", "bleu"]
    elif requested == "bleu":
        order = ["bleu", "chrf", "bertscore", "bertscore_unavailable"]
    elif requested == "chrf":
        order = ["chrf", "bleu", "bertscore", "bertscore_unavailable"]
    else:
        order = [requested, "accuracy", "f1", "exact_match", "bleu"]
    for key in order:
        if key in detailed and detailed[key] is not None:
            return float(detailed[key])
    if detailed:
        return float(next(iter(detailed.values())))
    return 0.0


def recipe_payload_to_benchmark_import(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """Turn Personal hf_dataset_recipes import payload into Leaderboard hf_importer shape."""
    gt = recipe.get("ground_truth") or []
    task = recipe.get("task_type") or "text_classification"
    primary = recipe.get("primary_metric") or "accuracy"
    rd: Dict[str, Any] = {
        "url": recipe.get("url", ""),
        "description": recipe.get("description", ""),
        "ground_truth": gt,
        "hf_import": "recipe",
    }
    if task == "text_classification":
        rd["labels"] = [str(x.get("answer")) for x in gt]
        rd["source_texts"] = [
            str(x.get("sentence") or x.get("question") or x.get("text") or "") for x in gt
        ]
    elif task == "named_entity_recognition":
        rd["entities"] = [x.get("answer") for x in gt]
        rd["source_texts"] = [str(x.get("text") or x.get("question") or "") for x in gt]
    elif task in ("document_qa", "line_qa"):
        rd["answers"] = []
        for x in gt:
            a = x.get("answer")
            if isinstance(a, list) and a:
                rd["answers"].append(a[0] if not isinstance(a[0], list) else a)
            else:
                rd["answers"].append(a)
        rd["source_texts"] = [str(x.get("question") or "") for x in gt]
    name = recipe.get("name") or recipe.get("display_name") or "imported_dataset"
    return {
        "name": name,
        "task_type": task,
        "evaluation_metric": primary,
        "reference_data": rd,
    }


def submission_format_for_dataset(
    name: str,
    task_type: Optional[str],
    evaluation_metric: Optional[str],
    reference_data: Any,
) -> Dict[str, Any]:
    """Describe POST /public/submit_model body shape for a stored benchmark dataset."""
    rd: Dict[str, Any]
    if isinstance(reference_data, str):
        try:
            parsed = json.loads(reference_data)
            rd = parsed if isinstance(parsed, dict) else {}
        except Exception:
            rd = {}
    elif isinstance(reference_data, dict):
        rd = reference_data
    else:
        rd = {}

    n = 0
    for key in ("source_texts", "ground_truth", "labels", "answers", "entities", "reference_translations"):
        v = rd.get(key)
        if isinstance(v, list) and len(v) > n:
            n = len(v)

    task_norm = normalize_task_type(task_type)
    metric_norm = normalize_eval_metric(evaluation_metric, task_norm)
    example_ids = list(range(min(n, 4))) if n else [0, 1, 2]

    placeholder_results: List[str] = []
    for _ in example_ids:
        if task_norm == "text_classification":
            placeholder_results.append("<predicted_label>")
        elif task_norm == "named_entity_recognition":
            placeholder_results.append("ENTITY_ONE; ENTITY_TWO")
        elif task_norm in ("document_qa", "line_qa"):
            placeholder_results.append("<predicted_answer_text>")
        else:
            placeholder_results.append("<predicted_translation>")

    return {
        "success": True,
        "benchmarkDatasetName": name,
        "task_type": task_type,
        "task_type_normalized": task_norm,
        "evaluation_metric": evaluation_metric,
        "evaluation_metric_normalized": metric_norm,
        "dataset_size": n,
        "reference_data_keys": sorted(rd.keys()),
        "submit_model_body": {
            "benchmarkDatasetName": name,
            "modelName": "your-model-id",
            "submittedBy": "you@example.com",
            "sentence_ids": example_ids,
            "modelResults": placeholder_results,
            "metadata": {},
        },
        "notes": {
            "sentence_ids": "Must be the same length as modelResults; indices into the dataset's reference_data (e.g. labels[i], answers[i]).",
            "modelResults": "For NER, use semicolon-separated entity strings per example unless submitting structured lists.",
        },
    }
