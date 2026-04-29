"""Sanity checks for expanded per-task metric lists."""

from metrics_info_full import get_metrics_for_task, normalize_task_type_for_metrics


def test_document_qa_has_many_metrics():
    keys = get_metrics_for_task(normalize_task_type_for_metrics("document_qa"))
    assert "exact_match" in keys
    assert "rouge_l" in keys
    assert "meteor" in keys
    assert len(keys) >= 8


def test_retrieval_includes_map_and_hits():
    keys = get_metrics_for_task("retrieval")
    assert "map" in keys
    assert "hits_at_10" in keys
    assert "ndcg" in keys


def test_summarization_task_exists():
    keys = get_metrics_for_task("summarization")
    assert "rouge_1" in keys and "bleu" in keys


def test_named_entity_has_ner_and_partial():
    keys = get_metrics_for_task("named_entity_recognition")
    assert "ner_f1" in keys
    assert "partial_f1" in keys
