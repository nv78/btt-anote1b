from flask import Blueprint, Response, current_app, request, jsonify, redirect
from typing import Optional, List, Dict, Any

from shared import *

bp = Blueprint("submissions", __name__)
app = bp

@bp.post('/public/submit_model')
@rate_limit("SUBMIT_MODEL_RATE_LIMIT", "10/minute")
@require_api_key
def submit_model():
    """Submit model results to a benchmark dataset and compute evaluation.

    Expected JSON:
    {
      "benchmarkDatasetName": "flores_spanish_translation",
      "modelName": "my-model-v1",
      "modelResults": ["Traducción 1", ...],
      "sentence_ids": [0, 1, 2]
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        benchmark_dataset_name = validate_text(data.get('benchmarkDatasetName'), "benchmarkDatasetName")
        model_name = validate_text(data.get('modelName'), "modelName")
        submitted_by = validate_text(data.get("submittedBy", "public@anote.ai"), "submittedBy", 255)
        metadata = validate_metadata(data.get("metadata"))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    model_results = data.get('modelResults')
    sentence_ids = data.get('sentence_ids')
    is_public = 0 if str(data.get("is_public", True)).lower() in ("false", "0", "no", "private") else 1

    if not isinstance(model_results, list):
        return jsonify({
            "success": False,
            "error": "Missing required fields: benchmarkDatasetName, modelName, modelResults (list)",
        }), 400

    submitter_id = resolve_submitter_id(request, data)
    quota_submitter_id = submitter_id or submitted_by or "anonymous"
    quota_ok, submissions_remaining, quota_resets_at = _consume_submission_quota(quota_submitter_id)
    if not quota_ok:
        resp = jsonify({
            "success": False,
            "error": "Daily submission limit reached",
            "limit": daily_submission_limit(),
            "resets_at": quota_resets_at,
        })
        resp.status_code = 429
        resp.headers["X-Submissions-Remaining"] = "0"
        return resp
    want_async = bool(data.get("async"))

    # Pull dataset metadata if available
    dataset = None
    conn_meta, cursor_meta = get_db_connection()
    if conn_meta and cursor_meta:
        try:
            cursor_meta.execute(
                "SELECT id, task_type, evaluation_metric, reference_data FROM benchmark_datasets WHERE name = %s",
                (benchmark_dataset_name,)
            )
            dataset = cursor_meta.fetchone()
        finally:
            try:
                cursor_meta.close()
                conn_meta.close()
            except Exception:
                pass

    if not dataset:
        dataset = next((d for d in _STORE["datasets"] if d.get("name") == benchmark_dataset_name), None)

    task_type_for_ids = (dataset or {}).get("task_type")
    task_type_key = str(task_type_for_ids or "").lower()
    reference_data_for_ids = None
    if dataset:
        try:
            raw_reference_data = dataset.get("reference_data")
            reference_data_for_ids = json.loads(raw_reference_data) if isinstance(raw_reference_data, str) else raw_reference_data
        except Exception:
            reference_data_for_ids = None
    has_inline_reference_rows = isinstance(reference_data_for_ids, dict) and any(
        isinstance(reference_data_for_ids.get(key), list)
        for key in ("source_texts", "ground_truth", "reference_translations", "labels", "entities", "answers")
    )
    requires_explicit_ids = task_type_key in ("translation", "document_qa") and not has_inline_reference_rows
    if sentence_ids is None:
        if requires_explicit_ids:
            return jsonify({
                "success": False,
                "error": "Missing required field: sentence_ids (list)",
            }), 400
        sentence_ids = list(range(len(model_results)))
    elif not isinstance(sentence_ids, list):
        return jsonify({
            "success": False,
            "error": "sentence_ids must be a list",
        }), 400
    # Do NOT override sentence_ids for any task type — respect what the caller provided.

    if len(model_results) != len(sentence_ids):
        return jsonify({
            "success": False,
            "error": "Length of sentence_ids must match length of modelResults",
        }), 400

    task_type = None
    metric = None
    reference_sentences = None
    reference_labels = None
    reference_entities = None
    reference_answers = None
    if dataset:
        task_type = dataset.get('task_type')
        metric = dataset.get('evaluation_metric')
        try:
            rd = json.loads(dataset.get('reference_data')) if isinstance(dataset.get('reference_data'), str) else dataset.get('reference_data')
            if isinstance(rd, dict):
                if isinstance(rd.get('reference_translations'), list):
                    # map by sentence_ids
                    all_refs = rd['reference_translations']
                    reference_sentences = [all_refs[i] for i in sentence_ids if 0 <= i < len(all_refs)]
                    if len(reference_sentences) != len(sentence_ids):
                        reference_sentences = None
                if isinstance(rd.get('labels'), list):
                    all_labels = rd['labels']
                    reference_labels = [all_labels[i] for i in sentence_ids if 0 <= i < len(all_labels)]
                    if len(reference_labels) != len(sentence_ids):
                        reference_labels = None
                if isinstance(rd.get('entities'), list):
                    all_ents = rd['entities']
                    reference_entities = [all_ents[i] for i in sentence_ids if 0 <= i < len(all_ents)]
                    if len(reference_entities) != len(sentence_ids):
                        reference_entities = None
                if isinstance(rd.get('answers'), list):
                    all_ans = rd['answers']
                    reference_answers = [all_ans[i] for i in sentence_ids if 0 <= i < len(all_ans)]
                    if len(reference_answers) != len(sentence_ids):
                        reference_answers = None
                if isinstance(rd.get('ground_truth'), list) and sentence_ids:
                    gtlist = rd['ground_truth']
                    try:
                        if all(0 <= int(i) < len(gtlist) for i in sentence_ids):
                            rows = [gtlist[int(i)] for i in sentence_ids]
                            _tt = (task_type or '').lower()
                            if not reference_labels and _tt == 'text_classification':
                                reference_labels = [
                                    r.get('answer') if isinstance(r, dict) else r
                                    for r in rows
                                ]
                            if not reference_entities and _tt in ('ner', 'named_entity_recognition'):
                                reference_entities = [
                                    r.get('answer') if isinstance(r, dict) else r
                                    for r in rows
                                ]
                            if not reference_answers and _tt in (
                                'chatbot', 'prompting', 'qa', 'document_qa', 'line_qa',
                                'math_reasoning', 'multiple_choice_qa', 'natural_language_inference',
                                'fact_verification', 'semantic_similarity', 'code_generation',
                                'summarization', 'retrieval', 'dialogue',
                            ):
                                reference_answers = [
                                    r.get('answer') if isinstance(r, dict) else r
                                    for r in rows
                                ]
                            if not reference_sentences and _tt in ('translation', ''):
                                reference_sentences = [
                                    r.get('answer') if isinstance(r, dict) else r
                                    for r in rows
                                ]
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        try:
            from eval_core.leaderboard_bridge import (  # type: ignore
                normalize_eval_metric,
                normalize_task_type,
                run_personal_eval,
            )
        except ImportError:
            from backend.eval_core.leaderboard_bridge import (  # type: ignore
                normalize_eval_metric,
                normalize_task_type,
                run_personal_eval,
            )

        task_norm = normalize_task_type(task_type)
        if task_norm == 'translation':
            if reference_sentences is None:
                if benchmark_dataset_name.startswith('flores_spanish_translation'):
                    references_pool = _SPANISH_REFERENCES
                    for sid in sentence_ids:
                        if sid < 0 or sid >= len(references_pool):
                            return jsonify({
                                "success": False,
                                "error": f"sentence_id {sid} is out of range (0-{len(references_pool)-1})",
                            }), 400
                    reference_sentences = [references_pool[sid] for sid in sentence_ids]
                else:
                    return jsonify({
                        "success": False,
                        "error": "No reference translations found for this dataset. "
                                 "Ensure the dataset was imported with reference data.",
                    }), 400
            if metric is None:
                metric = 'bertscore' if benchmark_dataset_name.endswith('_bertscore') else 'bleu'

        score, detailed_scores = run_personal_eval(
            task_type,
            metric,
            sentence_ids,
            reference_labels,
            reference_entities,
            reference_answers,
            reference_sentences,
            model_results,
        )
        metric = normalize_eval_metric(metric, task_norm)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        print(f"Evaluation failed: {e}")
        return jsonify({"success": False, "error": "Evaluation failed"}), 500

    eval_details = {"metric": metric, "metadata": metadata, "detailed_scores": detailed_scores}

    def _persist_and_build_response():
        submission_id = None
        conn, cursor = get_db_connection()
        if conn and cursor:
            try:
                cursor.execute(
                    "SELECT id FROM benchmark_datasets WHERE name = %s",
                    (benchmark_dataset_name,),
                )
                row = cursor.fetchone()
                if row:
                    dataset_id = row['id']
                else:
                    cursor.execute(
                        "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (benchmark_dataset_name, 'translation', metric, json.dumps([]), True),
                    )
                    dataset_id = cursor.lastrowid

                try:
                    cursor.execute(
                        "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, submitter_id, model_results, is_public) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (dataset_id, model_name, submitted_by, submitter_id, json.dumps(model_results), is_public),
                    )
                except Exception as ins_err:
                    err_s = str(ins_err).lower()
                    if "is_public" in err_s or ("no column" in err_s and "is_public" in err_s):
                        # DB predates is_public column — migrate then retry
                        try:
                            cursor.execute("ALTER TABLE model_submissions ADD COLUMN is_public INTEGER NOT NULL DEFAULT 1")
                            conn.commit()
                        except Exception:
                            pass
                        cursor.execute(
                            "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, submitter_id, model_results, is_public) "
                            "VALUES (%s, %s, %s, %s, %s, %s)",
                            (dataset_id, model_name, submitted_by, submitter_id, json.dumps(model_results), is_public),
                        )
                    elif "submitter_id" in err_s or "unknown column" in err_s:
                        cursor.execute(
                            "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, model_results) "
                            "VALUES (%s, %s, %s, %s)",
                            (dataset_id, model_name, submitted_by, json.dumps(model_results)),
                        )
                    else:
                        raise
                submission_id = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) "
                    "VALUES (%s, %s, %s)",
                    (submission_id, float(score), json.dumps(eval_details)),
                )
                conn.commit()
            except Exception as e:
                print(f"DB write failed, storing in memory instead: {e}")
                submission_id = None
            finally:
                try:
                    cursor.close()
                    conn.close()
                except Exception:
                    pass
        else:
            submission_id = None

        if submission_id is None:
            submission_id = len(_STORE["submissions"]) + 1
            _STORE["submissions"].append({
                "id": submission_id,
                "benchmark_dataset_name": benchmark_dataset_name,
                "model_name": model_name,
                "submitted_by": submitted_by,
                "submitter_id": submitter_id,
                "metadata": metadata,
                "results": model_results,
                "is_public": is_public,
                "created": utc_now(),
            })
            _STORE["evaluations"].append({
                "submission_id": submission_id,
                "score": float(score),
                "metric": metric,
                "evaluation_details": eval_details,
                "created": utc_now(),
            })

        logger.info(
            "model_submitted",
            extra={"dataset": benchmark_dataset_name, "model": model_name, "score": float(score)},
        )
        return {
            "success": True,
            "submission_id": submission_id,
            "score": float(score),
            "metric": metric,
            "detailed_scores": detailed_scores,
            "is_public": bool(is_public),
        }

    if want_async:

        def _worker(job_id: str):
            try:
                out = _persist_and_build_response()
                with _EVAL_JOBS_LOCK:
                    created = _EVAL_JOBS.get(job_id, {}).get("_created", utc_now().timestamp())
                    _EVAL_JOBS[job_id] = {"status": "completed", "_created": created, **out}
            except Exception as e:
                with _EVAL_JOBS_LOCK:
                    created = _EVAL_JOBS.get(job_id, {}).get("_created", utc_now().timestamp())
                    _EVAL_JOBS[job_id] = {"status": "failed", "_created": created, "error": str(e)}

        job_id = str(uuid.uuid4())
        _now = utc_now().timestamp()
        with _EVAL_JOBS_LOCK:
            _EVAL_JOBS[job_id] = {"status": "pending", "_created": _now}
            # Evict completed/failed jobs older than 1 hour
            expired = [k for k, v in _EVAL_JOBS.items() if _now - v.get("_created", _now) > 3600]
            for k in expired:
                del _EVAL_JOBS[k]
        t = threading.Thread(target=_worker, args=(job_id,), daemon=True)
        t.start()
        resp = jsonify({"success": True, "job_id": job_id, "status": "pending"})
        resp.status_code = 202
        resp.headers["X-Submissions-Remaining"] = str(submissions_remaining)
        return resp

    out = _persist_and_build_response()
    resp = jsonify(out)
    resp.headers["X-Submissions-Remaining"] = str(submissions_remaining)
    return resp


@bp.get("/public/eval_jobs/<job_id>")
def eval_job_status(job_id):
    """Poll async submit job created with ``{\"async\": true}`` on ``/public/submit_model``."""
    with _EVAL_JOBS_LOCK:
        row = _EVAL_JOBS.get(job_id)
    if not row:
        return jsonify({"success": False, "error": "Unknown job"}), 404
    return jsonify({"success": True, **row})


@bp.get("/public/submission_quota")
def submission_quota():
    """Return today's submission quota usage for a submitter id or caller IP."""
    submitter_id = (request.args.get("submitter_id") or "").strip()
    quota_submitter_id = submitter_id or request.remote_addr or "anonymous"
    limit = daily_submission_limit()
    day = utc_now().date().isoformat()
    key = f"{quota_submitter_id}:{day}"
    used_today = int(_STORE.setdefault("submission_counts", {}).get(key, 0))
    remaining = max(0, limit - used_today)
    return jsonify({
        "daily_limit": limit,
        "used_today": used_today,
        "remaining": remaining,
    })


@bp.get("/public/my_submissions")
def my_submissions():
    """List submissions for a submitter (JWT ``sub`` or ``submitter_id`` query with API key).

    Pagination: ``page`` + offset (default), or ``cursor`` (keyset on ``created DESC``, ``id DESC``; ignores ``page``).
    """
    sub = jwt_sub_from_request(request)
    if not sub:
        configured = [k.strip() for k in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if k.strip()]
        supplied = request.headers.get("X-API-Key", "").strip()
        # Only allow submitter_id fallback when a valid API key is presented
        if configured and supplied in configured:
            sub = (request.args.get("submitter_id") or "").strip()
        elif not configured:
            # Dev mode: no API keys configured — require JWT; reject bare submitter_id param
            # to prevent users from peeking at each other's submissions.
            pass
    if not sub:
        return jsonify({
            "success": False,
            "error": "Unauthorized — sign in (JWT) or provide a valid X-API-Key to view submissions",
        }), 401

    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", 25))))
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
            try:
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM model_submissions WHERE submitter_id = %s",
                    (sub,),
                )
            except Exception:
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM model_submissions WHERE submitted_by = %s",
                    (sub,),
                )
            total = int((cursor.fetchone() or {}).get("n", 0))
            cur_sql = ""
            cur_params: list = []
            if use_cursor:
                cur_sql = " AND ((ms.created < %s) OR (ms.created = %s AND ms.id < %s))"
                cur_params = [anchor_c, anchor_c, anchor_id]
            try:
                if use_cursor:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.created, ms.is_public, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitter_id = %s " + cur_sql +
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s",
                        tuple([sub] + cur_params + [page_size]),
                    )
                else:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.created, ms.is_public, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitter_id = %s "
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s OFFSET %s",
                        (sub, page_size, offset),
                    )
            except Exception:
                if use_cursor:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.created, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitted_by = %s " + cur_sql +
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s",
                        tuple([sub] + cur_params + [page_size]),
                    )
                else:
                    cursor.execute(
                        "SELECT ms.id, ms.model_name, ms.submitted_by, ms.created, "
                        "bd.name AS dataset_name, bd.task_type, er.score, er.evaluation_details "
                        "FROM model_submissions ms "
                        "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                        "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                        "WHERE ms.submitted_by = %s "
                        "ORDER BY ms.created DESC, ms.id DESC LIMIT %s OFFSET %s",
                        (sub, page_size, offset),
                    )
            rows = cursor.fetchall()
            items = []
            for r in rows:
                det = {}
                if r.get("evaluation_details"):
                    try:
                        det = json.loads(r["evaluation_details"]) if isinstance(r["evaluation_details"], str) else r["evaluation_details"]
                    except Exception:
                        det = {}
                items.append({
                    "submission_id": r["id"],
                    "dataset_name": r["dataset_name"],
                    "task_type": r.get("task_type"),
                    "model_name": r["model_name"],
                    "submitted_by": r.get("submitted_by"),
                    "score": float(r["score"]),
                    "primary_metric": det.get("metric") if isinstance(det, dict) else None,
                    "detailed_scores": det.get("detailed_scores") if isinstance(det, dict) else None,
                    "submitted_at": r["created"].isoformat() if r.get("created") else None,
                    "is_public": bool(r.get("is_public", 1)),
                })
            out = {
                "success": True,
                "submissions": items,
                "page": page if not use_cursor else None,
                "page_size": page_size,
                "total": total,
            }
            ms_more = len(rows) == page_size and (use_cursor or offset + len(rows) < total)
            if ms_more and rows:
                lr = rows[-1]
                ca = lr["created"].isoformat() if lr.get("created") else ""
                out["next_cursor"] = my_submissions_cursor_encode(ca, int(lr["id"]))
            return jsonify(out)
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
        sid = sub_row.get("submitter_id") or sub_row.get("submitted_by")
        if sid != sub:
            continue
        det = ev.get("evaluation_details") or {}
        if not isinstance(det, dict):
            det = {}
        mem_raw.append({
            "submission_id": sub_row["id"],
            "dataset_name": sub_row["benchmark_dataset_name"],
            "task_type": next(
                (d.get("task_type") for d in _STORE["datasets"] if d.get("name") == sub_row["benchmark_dataset_name"]),
                None,
            ),
            "model_name": sub_row["model_name"],
            "submitted_by": sub_row.get("submitted_by"),
            "score": ev["score"],
            "primary_metric": det.get("metric"),
            "detailed_scores": det.get("detailed_scores"),
            "_created": sub_row["created"],
            "_id": sub_row["id"],
        })
    mem_raw.sort(key=lambda x: (x["_created"], x["_id"]), reverse=True)
    total = len(mem_raw)
    if use_cursor:
        page_rows = []
        for r in mem_raw:
            if (r["_created"] < anchor_c) or (r["_created"] == anchor_c and r["_id"] < anchor_id):
                page_rows.append(r)
            if len(page_rows) >= page_size:
                break
    else:
        page_rows = mem_raw[offset:offset + page_size]

    items = []
    for r in page_rows:
        items.append({
            "submission_id": r["submission_id"],
            "dataset_name": r["dataset_name"],
            "task_type": r.get("task_type"),
            "model_name": r["model_name"],
            "submitted_by": r["submitted_by"],
            "score": r["score"],
            "primary_metric": r["primary_metric"],
            "detailed_scores": r["detailed_scores"],
            "submitted_at": r["_created"].isoformat(),
        })
    out = {
        "success": True,
        "submissions": items,
        "page": page if not use_cursor else None,
        "page_size": page_size,
        "total": total,
    }
    ms_more = len(page_rows) == page_size and (use_cursor or offset + page_size < total)
    if ms_more and page_rows:
        last = page_rows[-1]
        out["next_cursor"] = my_submissions_cursor_encode(last["_created"].isoformat(), int(last["_id"]))
    return jsonify(out)


@bp.get("/public/submissions/<int:submission_id>")
def submission_detail(submission_id: int):
    """Single submission row if it belongs to the requester (JWT or submitter_id query + API key)."""
    sub = jwt_sub_from_request(request)
    if not sub:
        configured = [k.strip() for k in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if k.strip()]
        require_key = os.getenv("REQUIRE_API_KEY", "").lower() in {"1", "true", "yes"} or bool(configured)
        if require_key:
            supplied = request.headers.get("X-API-Key", "")
            if supplied not in configured:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
        sub = (request.args.get("submitter_id") or "").strip()
    if not sub:
        return jsonify({"success": False, "error": "JWT or submitter_id required"}), 400

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            try:
                cursor.execute(
                    "SELECT ms.id, ms.model_name, ms.submitted_by, ms.submitter_id, ms.model_results, ms.created, "
                    "bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, er.score, er.evaluation_details "
                    "FROM model_submissions ms "
                    "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                    "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE ms.id = %s",
                    (submission_id,),
                )
            except Exception:
                cursor.execute(
                    "SELECT ms.id, ms.model_name, ms.submitted_by, ms.model_results, ms.created, "
                    "bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, er.score, er.evaluation_details "
                    "FROM model_submissions ms "
                    "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                    "JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE ms.id = %s",
                    (submission_id,),
                )
            r = cursor.fetchone()
            if not r:
                return jsonify({"success": False, "error": "Not found"}), 404
            owner = (r.get("submitter_id") or r.get("submitted_by") or "")
            if owner != sub:
                return jsonify({"success": False, "error": "Forbidden"}), 403
            det = {}
            if r.get("evaluation_details"):
                try:
                    det = json.loads(r["evaluation_details"]) if isinstance(r["evaluation_details"], str) else r["evaluation_details"]
                except Exception:
                    det = {}
            mr = r.get("model_results")
            if isinstance(mr, str):
                try:
                    mr = json.loads(mr)
                except Exception:
                    pass
            return jsonify({
                "success": True,
                "submission": {
                    "submission_id": r["id"],
                    "dataset_name": r["dataset_name"],
                    "task_type": r.get("task_type"),
                    "evaluation_metric": r.get("evaluation_metric"),
                    "model_name": r["model_name"],
                    "submitted_by": r.get("submitted_by"),
                    "model_results": mr,
                    "score": float(r["score"]),
                    "metric": det.get("metric") if isinstance(det, dict) else None,
                    "detailed_scores": det.get("detailed_scores") if isinstance(det, dict) else None,
                    "metadata": det.get("metadata") if isinstance(det, dict) else None,
                    "submitted_at": r["created"].isoformat() if r.get("created") else None,
                },
            })
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    sub_row = next((s for s in _STORE["submissions"] if s["id"] == submission_id), None)
    if not sub_row:
        return jsonify({"success": False, "error": "Not found"}), 404
    owner = sub_row.get("submitter_id") or sub_row.get("submitted_by")
    if owner != sub:
        return jsonify({"success": False, "error": "Forbidden"}), 403
    ev = next((e for e in _STORE["evaluations"] if e["submission_id"] == submission_id), None)
    if not ev:
        return jsonify({"success": False, "error": "Not found"}), 404
    det = ev.get("evaluation_details") or {}
    return jsonify({
        "success": True,
        "submission": {
            "submission_id": sub_row["id"],
            "dataset_name": sub_row["benchmark_dataset_name"],
            "model_name": sub_row["model_name"],
            "submitted_by": sub_row.get("submitted_by"),
            "model_results": sub_row.get("results"),
            "score": ev["score"],
            "metric": det.get("metric"),
            "detailed_scores": det.get("detailed_scores"),
            "metadata": det.get("metadata"),
            "submitted_at": sub_row["created"].isoformat(),
        },
    })


def _require_submission_owner(request, submission_id: int):
    """Return (sub, error_response) — sub is the authenticated identity, error_response is None on success."""
    sub = jwt_sub_from_request(request)
    if not sub:
        configured = [k.strip() for k in os.getenv("LEADERBOARD_API_KEYS", "").split(",") if k.strip()]
        supplied = request.headers.get("X-API-Key", "").strip()
        if configured and supplied in configured:
            sub = (request.args.get("submitter_id") or "").strip()
    if not sub:
        return None, (jsonify({"success": False, "error": "Unauthorized"}), 401)
    return sub, None


@bp.delete("/public/submissions/<int:submission_id>")
def delete_submission(submission_id: int):
    """Delete a submission (owner only)."""
    sub, err = _require_submission_owner(request, submission_id)
    if err:
        return err

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT ms.id, ms.submitter_id, ms.submitted_by FROM model_submissions ms WHERE ms.id = %s",
                (submission_id,),
            )
            r = cursor.fetchone()
            if not r:
                return jsonify({"success": False, "error": "Not found"}), 404
            owner = r.get("submitter_id") or r.get("submitted_by") or ""
            if owner != sub:
                return jsonify({"success": False, "error": "Forbidden"}), 403
            cursor.execute("DELETE FROM evaluation_results WHERE model_submission_id = %s", (submission_id,))
            cursor.execute("DELETE FROM model_submissions WHERE id = %s", (submission_id,))
            conn.commit()
            return jsonify({"success": True, "deleted": submission_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    # In-memory fallback
    idx = next((i for i, s in enumerate(_STORE["submissions"]) if s["id"] == submission_id), None)
    if idx is None:
        return jsonify({"success": False, "error": "Not found"}), 404
    owner = _STORE["submissions"][idx].get("submitter_id") or _STORE["submissions"][idx].get("submitted_by")
    if owner != sub:
        return jsonify({"success": False, "error": "Forbidden"}), 403
    _STORE["submissions"].pop(idx)
    _STORE["evaluations"] = [e for e in _STORE["evaluations"] if e["submission_id"] != submission_id]
    return jsonify({"success": True, "deleted": submission_id})


@bp.patch("/public/submissions/<int:submission_id>/visibility")
def update_submission_visibility(submission_id: int):
    """Toggle a submission between public and private (owner only).

    Body: {"is_public": true|false}
    """
    sub, err = _require_submission_owner(request, submission_id)
    if err:
        return err

    body = request.get_json(silent=True) or {}
    raw = body.get("is_public")
    if raw is None:
        return jsonify({"success": False, "error": "Missing is_public field"}), 400
    is_public = 0 if str(raw).lower() in ("false", "0", "no", "private") else 1

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT ms.id, ms.submitter_id, ms.submitted_by FROM model_submissions ms WHERE ms.id = %s",
                (submission_id,),
            )
            r = cursor.fetchone()
            if not r:
                return jsonify({"success": False, "error": "Not found"}), 404
            owner = r.get("submitter_id") or r.get("submitted_by") or ""
            if owner != sub:
                return jsonify({"success": False, "error": "Forbidden"}), 403
            try:
                cursor.execute(
                    "UPDATE model_submissions SET is_public = %s WHERE id = %s",
                    (is_public, submission_id),
                )
            except Exception as upd_err:
                if "is_public" in str(upd_err).lower() or "no column" in str(upd_err).lower():
                    cursor.execute("ALTER TABLE model_submissions ADD COLUMN is_public INTEGER NOT NULL DEFAULT 1")
                    conn.commit()
                    cursor.execute(
                        "UPDATE model_submissions SET is_public = %s WHERE id = %s",
                        (is_public, submission_id),
                    )
                else:
                    raise
            conn.commit()
            return jsonify({"success": True, "submission_id": submission_id, "is_public": bool(is_public)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    # In-memory fallback
    sub_row = next((s for s in _STORE["submissions"] if s["id"] == submission_id), None)
    if not sub_row:
        return jsonify({"success": False, "error": "Not found"}), 404
    owner = sub_row.get("submitter_id") or sub_row.get("submitted_by")
    if owner != sub:
        return jsonify({"success": False, "error": "Forbidden"}), 403
    sub_row["is_public"] = is_public
    return jsonify({"success": True, "submission_id": submission_id, "is_public": bool(is_public)})


# ── LLM runner ───────────────────────────────────────────────────────────────

def _call_llm(provider: str, model_id: str, api_key: Optional[str], prompt: str) -> str:
    """Call an LLM provider and return raw text response."""
    if provider == "openai":
        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            raise RuntimeError("openai package not installed — pip install openai")
        key = api_key or os.getenv("OPENAI_API_KEY") or ""
        if not key:
            raise RuntimeError("No OpenAI API key provided")
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model=model_id or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Return ONLY valid JSON, no explanation, no markdown fences."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return r.choices[0].message.content or ""

    if provider == "anthropic":
        try:
            import anthropic as _ant  # type: ignore
        except ImportError:
            raise RuntimeError("anthropic package not installed — pip install anthropic")
        key = api_key or os.getenv("ANTHROPIC_API_KEY") or ""
        if not key:
            raise RuntimeError("No Anthropic API key provided")
        client = _ant.Anthropic(api_key=key)
        r = client.messages.create(
            model=model_id or "claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system="You are a helpful assistant. Return ONLY valid JSON, no explanation, no markdown fences.",
        )
        return r.content[0].text  # type: ignore[attr-defined]

    if provider == "google":
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError:
            raise RuntimeError("google-generativeai package not installed — pip install google-generativeai")
        key = api_key or os.getenv("GOOGLE_API_KEY") or ""
        if not key:
            raise RuntimeError("No Google API key provided")
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_id or "gemini-1.5-flash")
        r = model.generate_content(
            f"You are a helpful assistant. Return ONLY valid JSON, no explanation, no markdown fences.\n\n{prompt}"
        )
        return getattr(r, "text", None) or ""

    if provider == "ollama":
        import urllib.request as _req
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        payload_bytes = json.dumps({
            "model": model_id or "llama3",
            "prompt": f"You are a helpful assistant. Return ONLY valid JSON, no explanation, no markdown fences.\n\n{prompt}",
            "stream": False,
        }).encode()
        req = _req.Request(f"{base}/api/generate", data=payload_bytes, headers={"Content-Type": "application/json"})
        with _req.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read()).get("response", "")

    raise RuntimeError(f"Unknown provider: {provider!r}")


def _parse_llm_json_response(text: str, expected_ids: List[int]) -> List[str]:
    """Extract ordered list of prediction strings from LLM JSON output."""
    # Strip markdown code fences
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(stripped)
    except Exception:
        # Try to extract JSON array substring
        start = stripped.find("[")
        end = stripped.rfind("]")
        if start != -1 and end != -1:
            try:
                parsed = json.loads(stripped[start:end + 1])
            except Exception:
                raise ValueError(f"Could not parse LLM response as JSON: {stripped[:200]}")
        else:
            raise ValueError(f"LLM did not return a JSON array: {stripped[:200]}")

    if not isinstance(parsed, list):
        raise ValueError("LLM response is not a JSON array")

    id_to_output: dict = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id") if "id" in item else None
        output = item.get("output") or item.get("prediction") or item.get("answer") or item.get("translation") or ""
        if raw_id is not None:
            try:
                id_to_output[int(raw_id)] = str(output)
            except (ValueError, TypeError):
                pass

    # Return in expected_ids order; fall back to positional if ids don't match
    results = []
    for i, eid in enumerate(expected_ids):
        if eid in id_to_output:
            results.append(id_to_output[eid])
        elif i < len(parsed):
            item = parsed[i]
            fallback = (item.get("output") or item.get("prediction") or item.get("answer") or "") if isinstance(item, dict) else str(item)
            results.append(str(fallback))
        else:
            results.append("")
    return results


def _build_batch_prompt(task_type: str, batch_items: List[dict]) -> str:
    """Build a task-appropriate prompt for a batch of items."""
    from eval_core.leaderboard_bridge import normalize_task_type  # type: ignore
    tt = normalize_task_type(task_type)

    header_map = {
        "text_classification": (
            "Classify each text. Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<label>\"}, ...]"
        ),
        "named_entity_recognition": (
            "Extract named entities (people, orgs, locations, etc.) from each text.\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"Entity One; Entity Two\"}, ...]\n"
            "If no entities, use empty string."
        ),
        "document_qa": (
            "Answer each question with a short exact span from the context.\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<answer>\"}, ...]"
        ),
        "line_qa": (
            "Answer each question concisely.\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<answer>\"}, ...]"
        ),
        "multiple_choice_qa": (
            "Choose the correct option letter (A, B, C, D, …) for each question.\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<letter>\"}, ...]"
        ),
        "natural_language_inference": (
            "Classify each premise-hypothesis pair as entailment, neutral, or contradiction.\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"entailment|neutral|contradiction\"}, ...]"
        ),
        "math_reasoning": (
            "Solve each math problem. Output ONLY the final numeric answer (digits and decimal point only, no units).\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<number>\"}, ...]"
        ),
        "summarization": (
            "Write a one-sentence summary for each document.\n"
            "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<summary>\"}, ...]"
        ),
        "translation": (
            "Translate each text. Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<translation>\"}, ...]"
        ),
    }
    instruction = header_map.get(tt, (
        "Complete the task for each item.\n"
        "Return ONLY a JSON array: [{\"id\": <n>, \"output\": \"<answer>\"}, ...]"
    ))

    lines = [instruction, "", "Items:"]
    for item in batch_items:
        lines.append(f"[{item['id']}] {item['text']}")
    return "\n".join(lines)


@bp.post("/public/run_llm_submission")
@rate_limit("SUBMIT_MODEL_RATE_LIMIT", "10/minute")
@require_api_key
def run_llm_submission():
    """Run an LLM against a benchmark dataset and auto-submit the results.

    Body:
    {
      "benchmarkDatasetName": "GLUE SST-2 - Sentiment Classification",
      "modelName": "gpt-4o-mini",
      "provider": "openai",          // openai | anthropic | google | ollama
      "model_id": "gpt-4o-mini",
      "api_key": "sk-...",           // optional — falls back to server env var
      "batch_size": 20,              // default 20
      "is_public": true,
      "submittedBy": "you@email.com"
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        benchmark_name = validate_text(data.get("benchmarkDatasetName"), "benchmarkDatasetName")
        model_name = validate_text(data.get("modelName"), "modelName")
        submitted_by = validate_text(data.get("submittedBy", "public@anote.ai"), "submittedBy", 255)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    provider = str(data.get("provider") or "openai").lower().strip()
    model_id = str(data.get("model_id") or data.get("modelId") or "").strip()
    user_api_key = str(data.get("api_key") or data.get("apiKey") or "").strip() or None
    batch_size = max(1, min(100, int(data.get("batch_size", 20))))
    is_public = 0 if str(data.get("is_public", True)).lower() in ("false", "0", "no", "private") else 1
    submitter_id = resolve_submitter_id(request, data)

    # Load dataset
    dataset = None
    conn_d, cursor_d = get_db_connection()
    if conn_d and cursor_d:
        try:
            cursor_d.execute(
                "SELECT id, task_type, evaluation_metric, reference_data FROM benchmark_datasets WHERE name = %s",
                (benchmark_name,),
            )
            dataset = cursor_d.fetchone()
        finally:
            try:
                cursor_d.close()
                conn_d.close()
            except Exception:
                pass
    if not dataset:
        dataset = next((d for d in _STORE["datasets"] if d.get("name") == benchmark_name), None)
    if not dataset:
        return jsonify({"success": False, "error": f"Dataset not found: {benchmark_name!r}"}), 404

    try:
        rd = json.loads(dataset["reference_data"]) if isinstance(dataset["reference_data"], str) else dataset["reference_data"]
    except Exception:
        rd = {}

    source_texts = rd.get("source_texts") or []
    if not source_texts:
        return jsonify({"success": False, "error": "Dataset has no source_texts — cannot run LLM"}), 400

    task_type = dataset.get("task_type") or "text_classification"
    n = len(source_texts)
    all_ids = list(range(n))

    def _worker(job_id: str):
        try:
            all_predictions: List[str] = [""] * n
            total_batches = (n + batch_size - 1) // batch_size
            for b_idx in range(total_batches):
                start = b_idx * batch_size
                end = min(start + batch_size, n)
                batch_ids = all_ids[start:end]
                batch_texts = source_texts[start:end]
                batch_items = [{"id": bid, "text": txt} for bid, txt in zip(batch_ids, batch_texts)]
                prompt = _build_batch_prompt(task_type, batch_items)
                raw = _call_llm(provider, model_id, user_api_key, prompt)
                preds = _parse_llm_json_response(raw, batch_ids)
                for i, pred in enumerate(preds):
                    all_predictions[start + i] = pred
                with _EVAL_JOBS_LOCK:
                    _EVAL_JOBS[job_id]["batches_done"] = b_idx + 1
                    _EVAL_JOBS[job_id]["total_batches"] = total_batches

            # Evaluate
            try:
                from eval_core.leaderboard_bridge import run_personal_eval, normalize_eval_metric, normalize_task_type  # type: ignore
            except ImportError:
                from backend.eval_core.leaderboard_bridge import run_personal_eval, normalize_eval_metric, normalize_task_type  # type: ignore

            # Build reference lists by walking ground_truth
            gt_list = rd.get("ground_truth") or []
            reference_labels = rd.get("labels") or ([gt_list[i].get("answer") if isinstance(gt_list[i], dict) else gt_list[i] for i in all_ids if i < len(gt_list)] if gt_list else None)
            reference_entities = rd.get("entities") or None
            reference_answers = rd.get("answers") or ([gt_list[i].get("answer") if isinstance(gt_list[i], dict) else gt_list[i] for i in all_ids if i < len(gt_list)] if gt_list and task_type not in ("text_classification",) else None)
            reference_translations = rd.get("reference_translations") or None

            tt = normalize_task_type(task_type)
            if tt == "text_classification":
                reference_answers = None
            elif tt in ("named_entity_recognition", "ner"):
                reference_labels = None
                reference_answers = None

            score, detailed_scores = run_personal_eval(
                task_type,
                dataset.get("evaluation_metric"),
                all_ids,
                reference_labels,
                reference_entities,
                reference_answers,
                reference_translations,
                all_predictions,
            )
            metric = normalize_eval_metric(dataset.get("evaluation_metric"), tt)
            eval_details = {"metric": metric, "detailed_scores": detailed_scores}

            # Persist
            submission_id = None
            conn_w, cursor_w = get_db_connection()
            if conn_w and cursor_w:
                try:
                    cursor_w.execute("SELECT id FROM benchmark_datasets WHERE name = %s", (benchmark_name,))
                    row = cursor_w.fetchone()
                    if row:
                        dataset_id = row["id"]
                        try:
                            cursor_w.execute(
                                "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, submitter_id, model_results, is_public) "
                                "VALUES (%s, %s, %s, %s, %s, %s)",
                                (dataset_id, model_name, submitted_by, submitter_id, json.dumps(all_predictions), is_public),
                            )
                        except Exception:
                            cursor_w.execute(
                                "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, model_results) "
                                "VALUES (%s, %s, %s, %s)",
                                (dataset_id, model_name, submitted_by, json.dumps(all_predictions)),
                            )
                        submission_id = cursor_w.lastrowid
                        cursor_w.execute(
                            "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) VALUES (%s, %s, %s)",
                            (submission_id, float(score), json.dumps(eval_details)),
                        )
                        conn_w.commit()
                finally:
                    try:
                        cursor_w.close()
                        conn_w.close()
                    except Exception:
                        pass

            with _EVAL_JOBS_LOCK:
                created = _EVAL_JOBS.get(job_id, {}).get("_created", utc_now().timestamp())
                _EVAL_JOBS[job_id] = {
                    "status": "completed",
                    "_created": created,
                    "success": True,
                    "submission_id": submission_id,
                    "score": float(score),
                    "metric": metric,
                    "detailed_scores": detailed_scores,
                    "total_questions": n,
                }
        except Exception as e:
            with _EVAL_JOBS_LOCK:
                created = _EVAL_JOBS.get(job_id, {}).get("_created", utc_now().timestamp())
                _EVAL_JOBS[job_id] = {"status": "failed", "_created": created, "error": str(e)}

    job_id = str(uuid.uuid4())
    _now = utc_now().timestamp()
    with _EVAL_JOBS_LOCK:
        _EVAL_JOBS[job_id] = {
            "status": "pending", "_created": _now,
            "batches_done": 0, "total_batches": (n + batch_size - 1) // batch_size,
            "total_questions": n,
        }
        expired = [k for k, v in _EVAL_JOBS.items() if _now - v.get("_created", _now) > 3600]
        for k in expired:
            del _EVAL_JOBS[k]

    t = threading.Thread(target=_worker, args=(job_id,), daemon=True)
    t.start()
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "total_questions": n,
        "total_batches": (n + batch_size - 1) // batch_size,
    }), 202
