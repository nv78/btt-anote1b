"""Tests for composite leaderboard aggregation."""

from composite_score import compute_composite_score, enrich_leaderboard_row


def test_single_metric_falls_back_to_raw_score():
    c, br = compute_composite_score("text_classification", "accuracy", None, 0.92)
    assert 91.0 <= c <= 93.0
    assert len(br) == 1
    assert br[0]["metric"] == "accuracy"


def test_multiple_metrics_weighted_aggregate():
    ds = {"accuracy": 0.9, "f1": 0.8, "precision": 0.85}
    c, br = compute_composite_score("text_classification", "f1", ds, 0.85)
    assert c > 0
    assert len(br) == 3
    assert all("normalized" in x for x in br)


def test_lower_is_better_distance():
    c, _ = compute_composite_score("geolocation", "median_distance_error", {"median_distance_error": 0.0}, 0.0)
    assert c >= 99.0
    c2, _ = compute_composite_score(
        "geolocation", "median_distance_error", {"median_distance_error": 5000.0}, 5000.0
    )
    assert c2 < c


def test_enrich_leaderboard_row_mutates():
    row = {
        "task_type": "text_classification",
        "evaluation_metric": "f1",
        "score": 0.88,
        "detailed_scores": {"f1": 0.88, "accuracy": 0.9},
    }
    enrich_leaderboard_row(row)
    assert "composite_score" in row
    assert row["composite_score"] > 0
    assert isinstance(row["composite_breakdown"], list)
