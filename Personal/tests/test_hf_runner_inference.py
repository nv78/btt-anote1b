"""Tests for HF sentiment runner helpers (mocked pipeline; no model download)."""
import os
import sys
import uuid

import pytest

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
from database import init_db
from seed_data import clear_database
from models import Submission, SubmissionStatus
from evaluation_service import evaluate_submission
from dataset_import import persist_imported_dataset
from hf_dataset_recipes import hf_rows_to_glue_sst2_ground_truth
from hf_runner_inference import (
    normalize_hf_sentiment_label,
    ground_truth_to_id_sentences,
    build_predictions_json,
    run_sentiment_pipeline_batched,
    submission_model_name_from_id,
)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    clear_database()
    try:
        yield
    finally:
        clear_database()


def test_normalize_pos_neg_variants():
    assert normalize_hf_sentiment_label("POSITIVE") == "positive"
    assert normalize_hf_sentiment_label("negative") == "negative"
    assert normalize_hf_sentiment_label({"label": "NEGATIVE", "score": 0.1}) == "negative"
    assert normalize_hf_sentiment_label("LABEL_1") == "positive"
    assert normalize_hf_sentiment_label("LABEL_0") == "negative"


def test_normalize_neutral_three_way():
    assert normalize_hf_sentiment_label("NEUTRAL") == "neutral"


def test_normalize_rejects_garbage():
    with pytest.raises(ValueError, match="Unexpected"):
        normalize_hf_sentiment_label("GARBAGE_LABEL_XYZ")


def test_ground_truth_requires_sentence_for_sst2():
    gt = [{"id": "1", "question": "only q", "answer": "positive"}]
    with pytest.raises(ValueError, match="sentence"):
        ground_truth_to_id_sentences(gt, require_sentence_key=True)


def test_ground_truth_accepts_sentence():
    gt = hf_rows_to_glue_sst2_ground_truth(
        [{"sentence": "hi", "label": 1}],
        "validation",
    )
    rows = ground_truth_to_id_sentences(gt, require_sentence_key=True)
    assert rows == [("sst2_validation_0", "hi")]


def test_build_predictions_json_mismatch():
    with pytest.raises(ValueError, match="count"):
        build_predictions_json(["a"], ["x", "y"])


def test_submission_model_name_distilbert_sst2():
    assert (
        submission_model_name_from_id(
            "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
        )
        == "hf_distilbert_sst2"
    )


def _mock_pipeline_factory(*args, **kwargs):
    class MockPipe:
        def __call__(self, texts, batch_size=None):
            if isinstance(texts, str):
                texts = [texts]
            # Alternate labels to match mixed gold below
            out = []
            for i, _ in enumerate(texts):
                lab = "POSITIVE" if i % 2 == 0 else "NEGATIVE"
                out.append({"label": lab, "score": 0.9})
            return out

    return MockPipe()


def test_run_sentiment_pipeline_batched_mock():
    sents = ["a", "b", "c"]
    labs = run_sentiment_pipeline_batched(
        "dummy/model",
        sents,
        batch_size=2,
        pipeline_factory=_mock_pipeline_factory,
    )
    assert labs == ["positive", "negative", "positive"]


def test_evaluate_submission_uses_evaluator_not_hand_scores():
    """primary_score must match TextClassificationEvaluator on stored predictions."""
    rows = [
        {"sentence": "a", "label": 1},
        {"sentence": "b", "label": 0},
    ]
    gt = hf_rows_to_glue_sst2_ground_truth(rows, "validation")
    payload = {
        "id": "hf_runner_test",
        "name": "Runner Test",
        "description": "t",
        "url": "https://huggingface.co/datasets/nyu-mll/glue",
        "task_type": "text_classification",
        "test_set_public": False,
        "labels_public": False,
        "primary_metric": "accuracy",
        "additional_metrics": ["f1", "precision", "recall"],
        "ground_truth": gt,
    }
    db = database.SessionLocal()
    try:
        ds = persist_imported_dataset(db, payload)
        id_sentences = ground_truth_to_id_sentences(gt, require_sentence_key=True)
        sentences = [t[1] for t in id_sentences]
        labels = run_sentiment_pipeline_batched(
            "dummy/model",
            sentences,
            batch_size=16,
            pipeline_factory=_mock_pipeline_factory,
        )
        predictions = build_predictions_json([t[0] for t in id_sentences], labels)

        from evaluators import get_evaluator

        ev = get_evaluator("text_classification")
        expected = ev.evaluate(ds.ground_truth, predictions)

        submission_id = str(uuid.uuid4())
        sub = Submission(
            id=submission_id,
            dataset_id=ds.id,
            model_name="mock_hf",
            predictions=predictions,
            status=SubmissionStatus.PENDING,
            submission_metadata={"provider": "huggingface"},
            is_internal=False,
        )
        db.add(sub)
        db.commit()

        evaluate_submission(submission_id)
        db.refresh(sub)

        assert sub.status == SubmissionStatus.COMPLETED
        assert sub.primary_score == pytest.approx(expected["accuracy"])
        assert sub.detailed_scores["accuracy"] == pytest.approx(expected["accuracy"])
        # Scores must come from evaluator dict, not a single hand-written float
        assert len(sub.detailed_scores) >= 4
    finally:
        db.close()
