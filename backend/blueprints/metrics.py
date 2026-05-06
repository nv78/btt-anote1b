from flask import Blueprint, Response, current_app, request, jsonify, redirect

from shared import *

bp = Blueprint("metrics", __name__)
app = bp

@bp.get('/api/metrics')
def list_metrics():
    """Return metric metadata for UI help text and docs clients."""
    return jsonify({"success": True, "metrics": METRICS_CATALOG})


@bp.get('/api/metrics/task/<task_type>')
def list_task_metrics(task_type):
    """Return recommended metrics for a specific task type."""
    nt = normalize_task_type_for_metrics(task_type)
    return jsonify({
        "success": True,
        "task_type": task_type,
        "task_type_normalized": nt,
        "metrics": metrics_for_task(task_type),
    })
