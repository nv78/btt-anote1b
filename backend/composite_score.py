"""
Aggregate leaderboard score from multiple detailed_metrics (Personal-style).

Produces composite_score on [0, 100]: weighted mean of normalized component metrics.
Higher is always better after normalization (distance-style metrics are inverted).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

_SKIP_KEYS = frozenset({"bertscore_unavailable", "metric"})

# Metrics where lower raw values mean better performance (normalized to higher = better).
_LOWER_IS_BETTER = frozenset(
    {
        "median_distance_error",
        "mean_distance_error",
        "distance_error",
        "rmse",
        "mae",
        "perplexity",
        "ter",
    }
)


def _normalize_component(metric_key: str, value: float) -> float:
    """Map one metric to [0.0, 1.0] where higher = better."""
    k = metric_key.lower().strip()
    v = float(value)
    if k in _LOWER_IS_BETTER:
        if k in {"median_distance_error", "mean_distance_error", "distance_error"}:
            scale = 500.0
            return 1.0 / (1.0 + max(0.0, v) / scale)
        if k == "perplexity":
            return 1.0 / (1.0 + max(0.0, v) / 50.0)
        return 1.0 / (1.0 + max(0.0, abs(v)))
    if 0.0 <= v <= 1.0:
        return max(0.0, min(1.0, v))
    if 1.0 < v <= 100.0:
        return max(0.0, min(1.0, v / 100.0))
    return max(0.0, min(1.0, v))


def _weights_for_keys(keys: List[str]) -> Dict[str, float]:
    """Slightly up-weight classic metrics for classification-like tasks."""
    n = len(keys)
    if n == 0:
        return {}
    base = 1.0 / n
    out = {k: base for k in keys}
    pref = {"accuracy", "f1", "macro_f1", "micro_f1", "exact_match", "bleu"}
    boost = {k for k in keys if k.lower() in pref}
    if boost and len(boost) < n:
        extra = base * 0.25
        for k in boost:
            out[k] += extra
        shrink = (extra * len(boost)) / (n - len(boost))
        for k in keys:
            if k not in boost:
                out[k] = max(base * 0.5, out[k] - shrink)
        s = sum(out.values())
        if s > 0:
            out = {k: v / s for k, v in out.items()}
    return out


def compute_composite_score(
    task_type: Optional[str],
    evaluation_metric: Optional[str],
    detailed_scores: Optional[Dict[str, Any]],
    raw_score: float,
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Returns (composite 0-100, breakdown rows for API/UI).
    If no detailed_scores, uses raw_score under evaluation_metric when possible.
    """
    _ = task_type  # reserved for task-specific weights / metric filtering
    em = (evaluation_metric or "").strip().lower().replace(" ", "_") if evaluation_metric else ""

    components: List[Tuple[str, float]] = []

    if isinstance(detailed_scores, dict):
        for key, val in detailed_scores.items():
            if key in _SKIP_KEYS:
                continue
            if val is None:
                continue
            try:
                fv = float(val)
            except (TypeError, ValueError):
                continue
            components.append((key, fv))

    if not components:
        key = em if em else "score"
        try:
            rs = float(raw_score)
        except (TypeError, ValueError):
            rs = 0.0
        components.append((key, rs))

    keys = [c[0] for c in components]
    weights = _weights_for_keys(keys)

    breakdown: List[Dict[str, Any]] = []
    aggregate = 0.0
    wsum = 0.0

    for key, val in components:
        norm = _normalize_component(key, val)
        w = weights.get(key, 1.0 / len(components))
        aggregate += w * norm
        wsum += w
        breakdown.append(
            {
                "metric": key,
                "raw": val,
                "normalized": round(norm, 6),
                "weight": round(w, 6),
            }
        )

    if wsum <= 0:
        composite = 0.0
    else:
        composite = 100.0 * (aggregate / wsum)

    composite = max(0.0, min(100.0, composite))
    return round(composite, 4), breakdown


def enrich_leaderboard_row(row: Dict[str, Any]) -> None:
    """Mutates row with composite_score and composite_breakdown."""
    ds = row.get("detailed_scores")
    if not isinstance(ds, dict):
        ds = None
    raw = row.get("score")
    try:
        raw_f = float(raw)
    except (TypeError, ValueError):
        raw_f = 0.0
    comp, br = compute_composite_score(
        row.get("task_type"),
        row.get("evaluation_metric"),
        ds,
        raw_f,
    )
    row["composite_score"] = comp
    row["composite_breakdown"] = br


def enrich_leaderboard_list(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for row in entries:
        enrich_leaderboard_row(row)
    return entries
