import pytest

from eval_core.hf_dataset_recipes import try_recipe_import
from eval_core.leaderboard_bridge import run_personal_eval, submission_format_for_dataset


def test_run_personal_eval_classification():
    score, detailed = run_personal_eval(
        "text_classification",
        "accuracy",
        [0, 1],
        ["pos", "neg"],
        None,
        None,
        None,
        ["pos", "neu"],
    )
    assert score == pytest.approx(0.5)
    assert "accuracy" in detailed
    assert detailed["accuracy"] == pytest.approx(0.5)


def test_submission_format_for_dataset():
    rd = {
        "source_texts": ["a", "b"],
        "labels": ["0", "1"],
    }
    out = submission_format_for_dataset("my_ds", "text_classification", "accuracy", rd)
    assert out["success"] is True
    assert out["dataset_size"] == 2
    assert out["submit_model_body"]["sentence_ids"] == [0, 1]
    assert len(out["submit_model_body"]["modelResults"]) == 2


def test_try_recipe_import_no_match():
    assert try_recipe_import("not_a_registered_hf_recipe_xyz", "default", "test", 5, None, None) is None
