from flask import Blueprint, Response, current_app, request, jsonify, redirect

from shared import *

bp = Blueprint("admin", __name__)
app = bp

@bp.get("/api/admin/submissions")
@require_admin
def admin_list_submissions():
    """List all submissions for moderation (``LEADERBOARD_ADMIN_API_KEYS``)."""
    dataset = (request.args.get("dataset") or "").strip() or None
    submitter_q = (request.args.get("submitter_id") or "").strip() or None
    raw_from = request.args.get("from")
    raw_to = request.args.get("to")
    date_from = _parse_iso_datetime(raw_from) if raw_from else None
    date_to = _parse_iso_datetime(raw_to) if raw_to else None
    include_outputs = (request.args.get("include_outputs") or "").lower() in {"1", "true", "yes"}
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(200, max(1, int(request.args.get("page_size", 25))))
    offset = (page - 1) * page_size
    cursor_token = (request.args.get("cursor") or "").strip()
    use_cursor = bool(cursor_token)
    anchor_c = None
    anchor_id = None
    if use_cursor:
        cd = decode_cursor(cursor_token)
        dec = my_submissions_cursor_decode(cd) if cd else None
        if not dec:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400
        c_iso, anchor_id = dec
        anchor_c = _parse_iso_datetime(c_iso)
        if anchor_c is None:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            where = ["1=1"]
            params_base: list = []
            if dataset:
                where.append("bd.name = %s")
                params_base.append(dataset)
            if submitter_q:
                where.append("(ms.submitter_id = %s OR ms.submitted_by = %s)")
                params_base.extend([submitter_q, submitter_q])
            if date_from:
                where.append("ms.created >= %s")
                params_base.append(date_from)
            if date_to:
                where.append("ms.created <= %s")
                params_base.append(date_to)
            cur_sql = ""
            cur_params: list = []
            if use_cursor:
                cur_sql = " AND ((ms.created < %s) OR (ms.created = %s AND ms.id < %s))"
                cur_params = [anchor_c, anchor_c, anchor_id]
            where_sql = " AND ".join(where)

            count_q = (
                "SELECT COUNT(*) AS n FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                f"WHERE {where_sql}"
            )
            cursor.execute(count_q, tuple(params_base))
            total = int((cursor.fetchone() or {}).get("n", 0))

            mr_col = "ms.model_results" if include_outputs else "NULL AS model_results"
            base = (
                f"SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.created, "
                f"bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details, {mr_col} "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                f"WHERE {where_sql}{cur_sql} "
                "ORDER BY ms.created DESC, ms.id DESC "
            )
            lim_params: list = [page_size]
            if not use_cursor:
                base += "LIMIT %s OFFSET %s"
                lim_params.append(offset)
            else:
                base += "LIMIT %s"
            cursor.execute(base, tuple(params_base + cur_params + lim_params))
            rows = cursor.fetchall()
            items = []
            for r in rows:
                det_raw = r.get("evaluation_details")
                snip, _ = _evaluation_snippet_and_body(det_raw, include_outputs)
                row_out = {
                    "submission_id": r["id"],
                    "dataset_name": r["dataset_name"],
                    "task_type": r.get("task_type"),
                    "model_name": r["model_name"],
                    "submitted_by": r.get("submitted_by"),
                    "submitter_id": r.get("submitter_id"),
                    "score": float(r["score"]),
                    "created": r["created"].isoformat() if r.get("created") else None,
                    "evaluation_snippet": snip,
                }
                if include_outputs:
                    ed = det_raw
                    if isinstance(ed, str):
                        try:
                            ed = json.loads(ed)
                        except Exception:
                            ed = {"raw": ed}
                    row_out["evaluation_details"] = ed if isinstance(ed, dict) else {"raw": ed}
                    mr = r.get("model_results")
                    if isinstance(mr, str):
                        try:
                            mr = json.loads(mr)
                        except Exception:
                            pass
                    row_out["model_results"] = mr
                items.append(row_out)
            out = {
                "success": True,
                "submissions": items,
                "page": page if not use_cursor else None,
                "page_size": page_size,
                "total": total,
            }
            adm_more = len(rows) == page_size and (use_cursor or offset + len(rows) < total)
            if adm_more and rows:
                lr = rows[-1]
                ca = lr["created"].isoformat() if lr.get("created") else ""
                out["next_cursor"] = my_submissions_cursor_encode(ca, int(lr["id"]))
            return jsonify(out)
        except Exception as e:
            logger.exception("admin_submissions_db_failed", extra={"error": str(e)})
            return jsonify({"success": False, "error": "Database error"}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    mem_raw = []
    for ev in _STORE["evaluations"]:
        sub_row = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
        if not sub_row:
            continue
        dname = sub_row["benchmark_dataset_name"]
        if dataset and dname != dataset:
            continue
        if submitter_q:
            if sub_row.get("submitter_id") != submitter_q and sub_row.get("submitted_by") != submitter_q:
                continue
        cr = sub_row["created"]
        if date_from and cr < date_from:
            continue
        if date_to and cr > date_to:
            continue
        det_raw = ev.get("evaluation_details")
        snip, _ = _evaluation_snippet_and_body(det_raw, include_outputs)
        mem_raw.append({
            "submission_id": sub_row["id"],
            "dataset_name": dname,
            "task_type": None,
            "model_name": sub_row["model_name"],
            "submitted_by": sub_row.get("submitted_by"),
            "submitter_id": sub_row.get("submitter_id"),
            "score": float(ev["score"]),
            "created": cr,
            "evaluation_snippet": snip,
            "_det_raw": det_raw,
            "_model_results": sub_row.get("model_results") if include_outputs else None,
            "_id": sub_row["id"],
        })
    mem_raw.sort(key=lambda x: (x["created"], x["_id"]), reverse=True)
    total = len(mem_raw)
    if use_cursor:
        page_rows = []
        for r in mem_raw:
            if (r["created"] < anchor_c) or (r["created"] == anchor_c and r["_id"] < anchor_id):
                page_rows.append(r)
            if len(page_rows) >= page_size:
                break
    else:
        page_rows = mem_raw[offset:offset + page_size]

    items = []
    for r in page_rows:
        o = {
            "submission_id": r["submission_id"],
            "dataset_name": r["dataset_name"],
            "task_type": r["task_type"],
            "model_name": r["model_name"],
            "submitted_by": r["submitted_by"],
            "submitter_id": r["submitter_id"],
            "score": r["score"],
            "created": r["created"].isoformat() if r.get("created") else None,
            "evaluation_snippet": r["evaluation_snippet"],
        }
        if include_outputs:
            ed = r["_det_raw"]
            if isinstance(ed, str):
                try:
                    ed = json.loads(ed)
                except Exception:
                    ed = {"raw": ed}
            o["evaluation_details"] = ed if isinstance(ed, dict) else {"raw": ed}
            o["model_results"] = r["_model_results"]
        items.append(o)
    out = {
        "success": True,
        "submissions": items,
        "page": page if not use_cursor else None,
        "page_size": page_size,
        "total": total,
    }
    adm_more = len(page_rows) == page_size and (use_cursor or offset + page_size < total)
    if adm_more and page_rows:
        last = page_rows[-1]
        out["next_cursor"] = my_submissions_cursor_encode(last["created"].isoformat(), int(last["_id"]))
    return jsonify(out)
