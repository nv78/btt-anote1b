import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from shared import get_db_connection, require_admin, rate_limit, validate_text, logger

bp = Blueprint("dataset_requests", __name__)

VALID_TASK_TYPES = {
    "text_classification",
    "named_entity_recognition",
    "document_qa",
    "retrieval",
    "translation",
}


@bp.post("/public/request_dataset")
@rate_limit("ADD_DATASET_RATE_LIMIT", "5/minute")
def request_dataset():
    data = request.get_json(silent=True) or {}
    try:
        dataset_name = validate_text(data.get("dataset_name"), "dataset_name", 200)
        task_type = validate_text(data.get("task_type"), "task_type", 60)
        description = validate_text(data.get("description"), "description", 1000)
        requested_by = validate_text(data.get("requested_by", "anonymous"), "requested_by", 255)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    url = (data.get("url") or "").strip()[:500] or None

    if task_type not in VALID_TASK_TYPES:
        return jsonify({"success": False, "error": f"task_type must be one of: {', '.join(sorted(VALID_TASK_TYPES))}"}), 400

    conn, cursor = get_db_connection()
    if not conn or not cursor:
        return jsonify({"success": False, "error": "Database unavailable"}), 503

    try:
        cursor.execute(
            "INSERT INTO dataset_requests (dataset_name, task_type, description, url, requested_by) VALUES (%s, %s, %s, %s, %s)",
            (dataset_name, task_type, description, url, requested_by),
        )
        conn.commit()
        req_id = cursor.lastrowid
        return jsonify({"success": True, "id": req_id, "status": "pending"}), 201
    except Exception:
        logger.exception("dataset_request_insert_failed")
        return jsonify({"success": False, "error": "Failed to save request"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@bp.get("/api/admin/dataset_requests")
@require_admin
def list_dataset_requests():
    status_filter = request.args.get("status", "")
    conn, cursor = get_db_connection()
    if not conn or not cursor:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        if status_filter in ("pending", "approved", "rejected"):
            cursor.execute(
                "SELECT id, dataset_name, task_type, description, url, requested_by, status, admin_notes, created, reviewed_at FROM dataset_requests WHERE status = %s ORDER BY created DESC",
                (status_filter,),
            )
        else:
            cursor.execute(
                "SELECT id, dataset_name, task_type, description, url, requested_by, status, admin_notes, created, reviewed_at FROM dataset_requests ORDER BY created DESC"
            )
        rows = cursor.fetchall()
        return jsonify({"success": True, "requests": [dict(r) for r in rows]})
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@bp.post("/api/admin/dataset_requests/<int:req_id>/approve")
@require_admin
def approve_dataset_request(req_id):
    data = request.get_json(silent=True) or {}
    admin_notes = (data.get("admin_notes") or "").strip()[:500]
    now = datetime.now(timezone.utc).isoformat()

    conn, cursor = get_db_connection()
    if not conn or not cursor:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        cursor.execute("SELECT * FROM dataset_requests WHERE id = %s", (req_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({"success": False, "error": "Request not found"}), 404
        if req["status"] != "pending":
            return jsonify({"success": False, "error": f"Request is already {req['status']}"}), 409

        evaluation_metric = data.get("evaluation_metric", "accuracy")
        reference_data = json.dumps({"description": req["description"], "url": req["url"], "source_texts": [], "labels": []})

        cursor.execute(
            "INSERT OR IGNORE INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, 1)",
            (req["dataset_name"], req["task_type"], evaluation_metric, reference_data),
        )
        cursor.execute(
            "UPDATE dataset_requests SET status = 'approved', admin_notes = %s, reviewed_at = %s WHERE id = %s",
            (admin_notes, now, req_id),
        )
        conn.commit()
        return jsonify({"success": True, "id": req_id, "status": "approved"})
    except Exception:
        logger.exception("dataset_request_approve_failed")
        return jsonify({"success": False, "error": "Approval failed"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@bp.post("/api/admin/dataset_requests/<int:req_id>/reject")
@require_admin
def reject_dataset_request(req_id):
    data = request.get_json(silent=True) or {}
    admin_notes = (data.get("admin_notes") or "").strip()[:500]
    now = datetime.now(timezone.utc).isoformat()

    conn, cursor = get_db_connection()
    if not conn or not cursor:
        return jsonify({"success": False, "error": "Database unavailable"}), 503
    try:
        cursor.execute("SELECT id, status FROM dataset_requests WHERE id = %s", (req_id,))
        req = cursor.fetchone()
        if not req:
            return jsonify({"success": False, "error": "Request not found"}), 404
        if req["status"] != "pending":
            return jsonify({"success": False, "error": f"Request is already {req['status']}"}), 409

        cursor.execute(
            "UPDATE dataset_requests SET status = 'rejected', admin_notes = %s, reviewed_at = %s WHERE id = %s",
            (admin_notes, now, req_id),
        )
        conn.commit()
        return jsonify({"success": True, "id": req_id, "status": "rejected"})
    except Exception:
        logger.exception("dataset_request_reject_failed")
        return jsonify({"success": False, "error": "Rejection failed"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
