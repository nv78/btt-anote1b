"""Metric catalog exposed by the public leaderboard API.

This is a Flask-friendly subset of the richer metric documentation from the
Personal leaderboard implementation.
"""

METRICS_CATALOG = {
    "accuracy": {
        "name": "Accuracy",
        "formula": "correct predictions / total predictions",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "Share of examples where the model prediction exactly matches the expected label.",
        "task_types": ["text_classification", "multiple_choice"],
    },
    "precision": {
        "name": "Macro Precision",
        "formula": "mean(TP / (TP + FP)) across classes",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "How often predicted labels are correct, averaged across classes.",
        "task_types": ["text_classification", "named_entity_recognition", "ner"],
    },
    "recall": {
        "name": "Macro Recall",
        "formula": "mean(TP / (TP + FN)) across classes",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "How often expected labels are recovered, averaged across classes.",
        "task_types": ["text_classification", "named_entity_recognition", "ner"],
    },
    "f1": {
        "name": "F1",
        "formula": "2 * precision * recall / (precision + recall)",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "Harmonic mean of precision and recall.",
        "task_types": ["text_classification", "named_entity_recognition", "ner", "document_qa", "line_qa", "qa"],
    },
    "exact": {
        "name": "Exact Match",
        "formula": "normalized prediction == normalized answer",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "Strict answer match after lowercase and whitespace normalization.",
        "task_types": ["chatbot", "prompting", "document_qa", "line_qa", "qa"],
    },
    "exact_match": {
        "name": "Exact Match",
        "formula": "normalized prediction == normalized answer",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "Strict answer match after lowercase and whitespace normalization.",
        "task_types": ["chatbot", "prompting", "document_qa", "line_qa", "qa"],
    },
    "bleu": {
        "name": "BLEU",
        "formula": "n-gram overlap with brevity penalty",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "Translation overlap score against reference translations.",
        "task_types": ["translation"],
    },
    "bertscore": {
        "name": "BERTScore",
        "formula": "contextual embedding similarity",
        "range": "0.0 - 1.0",
        "higher_is_better": True,
        "description": "Semantic similarity between generated text and references when the optional bert_score package is installed.",
        "task_types": ["translation", "document_qa", "line_qa", "qa"],
    },
}


TASK_METRICS = {
    "text_classification": ["accuracy", "f1", "precision", "recall"],
    "multiple_choice": ["accuracy"],
    "translation": ["bleu", "bertscore"],
    "ner": ["f1", "precision", "recall"],
    "named_entity_recognition": ["f1", "precision", "recall"],
    "chatbot": ["exact", "f1"],
    "prompting": ["exact", "f1"],
    "qa": ["exact", "f1", "bertscore"],
    "document_qa": ["exact_match", "f1", "bertscore"],
    "line_qa": ["exact_match", "f1", "bertscore"],
}


def metrics_for_task(task_type):
    """Return metric metadata for a task type."""
    keys = TASK_METRICS.get(str(task_type or "").lower(), [])
    return {key: METRICS_CATALOG[key] for key in keys if key in METRICS_CATALOG}
