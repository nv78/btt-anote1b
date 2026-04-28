"""
Convert Leaderboard /public/submit_model parallel lists into Personal evaluator
ground_truth + predictions shapes, run evaluators, resolve primary score.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from eval_core.evaluators import get_evaluator


def normalize_task_type(task_type: Optional[str]) -> str:
    if not task_type:
        return "translation"
    t = str(task_type).lower().strip()
    aliases = {
        "ner": "named_entity_recognition",
        "qa": "document_qa",
        "chatbot": "document_qa",
        "prompting": "line_qa",
    }
    return aliases.get(t, t)


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
    else:
        raise ValueError(f"unsupported task for Personal evaluators: {tt!r}")

    primary = normalize_eval_metric(None, tt)
    return tt, primary, ground_truth, predictions


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
    """Compute primary score and full detailed_scores dict."""
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
        order = ["bleu", "bertscore", "bertscore_unavailable"]
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
