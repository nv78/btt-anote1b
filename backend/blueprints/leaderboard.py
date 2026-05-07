from flask import Blueprint, Response, current_app, request, jsonify, redirect

from shared import *

bp = Blueprint("leaderboard", __name__)
app = bp

@bp.get('/public/submission_format')
def submission_format():
    """Return expected POST /public/submit_model JSON shape for a dataset name."""
    raw = request.args.get("dataset") or request.args.get("benchmarkDatasetName")
    if not raw:
        return jsonify({"success": False, "error": "Missing query parameter: dataset or benchmarkDatasetName"}), 400
    try:
        name = validate_text(raw, "dataset")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    dataset = None
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT name, task_type, evaluation_metric, reference_data FROM benchmark_datasets "
                "WHERE name = %s AND active = TRUE",
                (name,),
            )
            dataset = cursor.fetchone()
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    if not dataset:
        dataset = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
    if not dataset:
        return jsonify({"success": False, "error": "Dataset not found"}), 404

    try:
        from eval_core.leaderboard_bridge import submission_format_for_dataset  # type: ignore
    except ImportError:
        from backend.eval_core.leaderboard_bridge import submission_format_for_dataset  # type: ignore

    payload = submission_format_for_dataset(
        dataset.get("name", name),
        dataset.get("task_type"),
        dataset.get("evaluation_metric"),
        dataset.get("reference_data"),
    )
    return jsonify(payload)


def _questions_from_reference_data(reference_data: object) -> list[dict[str, Any]]:
    if isinstance(reference_data, str):
        try:
            reference_data = json.loads(reference_data)
        except Exception:
            reference_data = {}
    if not isinstance(reference_data, dict):
        return []

    ground_truth = reference_data.get("ground_truth")
    if isinstance(ground_truth, list) and ground_truth:
        if not all(isinstance(row, dict) for row in ground_truth):
            source_texts = reference_data.get("source_texts")
            if isinstance(source_texts, list):
                contexts = reference_data.get("contexts") if isinstance(reference_data.get("contexts"), list) else []
                return [
                    {
                        "id": idx,
                        "input": str(text),
                        "context": str(contexts[idx]) if idx < len(contexts) and contexts[idx] is not None else None,
                    }
                    for idx, text in enumerate(source_texts)
                ]
            return []
        items = []
        for idx, row in enumerate(ground_truth):
            input_text = (
                row.get("input")
                or row.get("question")
                or row.get("sentence")
                or row.get("text")
                or row.get("source")
                or row.get("prompt")
                or ""
            )
            context = row.get("context") or row.get("passage") or row.get("document")
            items.append({
                "id": int(row.get("id", idx)) if str(row.get("id", idx)).isdigit() else idx,
                "input": str(input_text),
                "context": str(context) if context is not None else None,
            })
        return items

    source_texts = reference_data.get("source_texts")
    if isinstance(source_texts, list):
        contexts = reference_data.get("contexts") if isinstance(reference_data.get("contexts"), list) else []
        return [
            {
                "id": idx,
                "input": str(text),
                "context": str(contexts[idx]) if idx < len(contexts) and contexts[idx] is not None else None,
            }
            for idx, text in enumerate(source_texts)
        ]
    return []


@bp.get('/public/dataset_questions')
def dataset_questions() -> Any:
    """Return benchmark inputs/questions without reference labels or answers."""
    raw = request.args.get("dataset")
    if not raw:
        return jsonify({"success": False, "error": "Missing query parameter: dataset"}), 400
    try:
        name = validate_text(raw, "dataset")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    dataset = None
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT name, task_type, evaluation_metric, reference_data FROM benchmark_datasets "
                "WHERE name = %s AND active = TRUE",
                (name,),
            )
            dataset = cursor.fetchone()
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    if not dataset:
        dataset = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
    if not dataset:
        return jsonify({"success": False, "error": "Dataset not found"}), 404

    return jsonify({
        "success": True,
        "dataset": dataset.get("name", name),
        "task_type": dataset.get("task_type"),
        "questions": _questions_from_reference_data(dataset.get("reference_data")),
    })


def _mem_leaderboard_row_after_anchor(item, dataset_filter, single_ds, an_d, an_s, an_i):
    """True if item sorts strictly after anchor (DB order: dataset ASC, score DESC, id DESC)."""
    ev, sub = item
    name = sub["benchmark_dataset_name"]
    sc = float(ev["score"])
    sid = int(sub["id"])
    if dataset_filter:
        return (sc < float(an_s)) or (sc == float(an_s) and sid < int(an_i))
    return (name > an_d) or (name == an_d and sc < float(an_s)) or (name == an_d and sc == float(an_s) and sid < int(an_i))


def _leaderboard_row_after_anchor(row: dict[str, Any], dataset_filter: str | None, an_d: str, an_s: float, an_i: int) -> bool:
    name = row["dataset_name"]
    score = float(row["score"])
    submission_id = int(row.get("submission_id") or 0)
    if dataset_filter:
        return (score < float(an_s)) or (score == float(an_s) and submission_id < int(an_i))
    return (
        (name > an_d)
        or (name == an_d and score < float(an_s))
        or (name == an_d and score == float(an_s) and submission_id < int(an_i))
    )


def _leaderboard_data_rows(dataset_filter: str | None, represented: set[tuple[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    synthetic_id = -1
    for dataset in LEADERBOARD_DATA:
        dataset_name = dataset.get("name")
        if not dataset_name or (dataset_filter and dataset_name != dataset_filter):
            continue
        for model in dataset.get("models") or []:
            model_name = model.get("model") or model.get("model_name")
            if not model_name:
                continue
            key = (str(dataset_name), str(model_name))
            if key in represented:
                continue
            detailed_scores = model.get("detailed_scores")
            metric = dataset.get("evaluation_metric") or model.get("primary_metric") or "score"
            if not isinstance(detailed_scores, dict):
                detailed_scores = {metric: model.get("score")}
            rows.append({
                "rank": 0,
                "submission_id": synthetic_id,
                "model_name": str(model_name),
                "dataset_name": str(dataset_name),
                "url": dataset.get("url"),
                "submission_count": len(dataset.get("models") or []),
                "task_type": dataset.get("task_type"),
                "evaluation_metric": metric,
                "score": float(model.get("score") or 0),
                "submitted_by": model.get("submitted_by") or "seed_real_benchmarks@anote.ai",
                "metadata": {
                    "source": "LEADERBOARD_DATA",
                    "rank": model.get("rank"),
                    "updated": model.get("updated"),
                    "ci": model.get("ci"),
                },
                "detailed_scores": detailed_scores,
                "primary_metric": metric,
                "submitted_at": model.get("updated"),
            })
            synthetic_id -= 1
    return rows


def _finalize_leaderboard_response(
    rows: list[dict[str, Any]],
    dataset_filter: str | None,
    page: int,
    page_size: int,
    offset: int,
    use_cursor: bool,
    rank_start: int,
    an_d: str,
    an_s: float,
    an_i: int,
) -> dict[str, Any]:
    rows.sort(key=lambda r: (r["dataset_name"], -float(r["score"]), -int(r.get("submission_id") or 0)))
    total = len(rows)
    if use_cursor:
        page_rows = []
        for row in rows:
            if not _leaderboard_row_after_anchor(row, dataset_filter, an_d, an_s, an_i):
                continue
            page_rows.append(row)
            if len(page_rows) >= page_size:
                break
    else:
        page_rows = rows[offset:offset + page_size]

    r0 = rank_start if use_cursor else offset + 1
    for j, row in enumerate(page_rows):
        row["rank"] = r0 + j
    leaderboard = enrich_leaderboard_list(page_rows)
    out = {
        "success": True,
        "leaderboard": leaderboard,
        "entries": leaderboard,
        "page": page if not use_cursor else None,
        "page_size": page_size,
        "total": total,
    }
    has_more = len(page_rows) == page_size and (use_cursor or offset + len(page_rows) < total)
    if has_more and page_rows:
        last = page_rows[-1]
        out["next_cursor"] = leaderboard_cursor_encode(
            dataset_name=last["dataset_name"],
            score=float(last["score"]),
            submission_id=int(last.get("submission_id") or 0),
            next_rank_start=r0 + len(page_rows),
            single_dataset=bool(dataset_filter),
        )
    return out


@bp.get('/public/get_leaderboard')
def get_leaderboard():
    """Get leaderboard showing model submissions and scores.
    Supports DB if configured, otherwise returns in-memory results.

    Pagination: ``page`` + offset (default), or ``cursor`` (keyset; ignores ``page``).
    Sort: ``dataset_name`` ASC, ``score`` DESC, ``submission_id`` DESC.
    """
    dataset_filter = request.args.get("dataset")
    cursor_token = (request.args.get("cursor") or "").strip()
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", request.args.get("limit", 25)))))
    offset = (page - 1) * page_size
    use_cursor = bool(cursor_token)
    rank_start = 1
    key_single = bool(dataset_filter)
    an_d = ""
    an_s = 0.0
    an_i = 0

    if use_cursor:
        cd = decode_cursor(cursor_token)
        dec = leaderboard_cursor_decode(cd) if cd else None
        if not dec:
            return jsonify({"success": False, "error": "Invalid cursor"}), 400
        key_single, an_d, an_s, an_i, rank_start = dec
        if bool(dataset_filter) != key_single:
            return jsonify({"success": False, "error": "Cursor dataset scope mismatch"}), 400
        if dataset_filter and key_single:
            an_d = ""

    conn, cursor = get_db_connection()

    def _rows_to_leaderboard(rows, r0):
        leaderboard = []
        dataset_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            dataset_counts[row["dataset_name"]] += 1
        for j, row in enumerate(rows):
            details = {}
            if row.get("evaluation_details"):
                try:
                    details = json.loads(row["evaluation_details"]) if isinstance(row["evaluation_details"], str) else row["evaluation_details"]
                except Exception:
                    details = {}
            reference_data = {}
            if row.get("reference_data"):
                try:
                    reference_data = json.loads(row["reference_data"]) if isinstance(row["reference_data"], str) else row["reference_data"]
                except Exception:
                    reference_data = {}
            leaderboard.append({
                "rank": r0 + j,
                "submission_id": row.get("submission_id"),
                "model_name": row["model_name"],
                "dataset_name": row["dataset_name"],
                "url": reference_data.get("url") if isinstance(reference_data, dict) else None,
                "submission_count": dataset_counts[row["dataset_name"]],
                "task_type": row.get("task_type"),
                "evaluation_metric": row.get("evaluation_metric"),
                "score": float(row["score"]),
                "submitted_by": row.get("submitted_by"),
                "metadata": details.get("metadata") if isinstance(details, dict) else None,
                "detailed_scores": details.get("detailed_scores") if isinstance(details, dict) else None,
                "primary_metric": details.get("metric") if isinstance(details, dict) else None,
                "submitted_at": row["submitted_at"].isoformat() if row.get("submitted_at") else None,
            })
        return leaderboard

    if conn and cursor:
        try:
            where = "WHERE bd.active = TRUE"
            params = []
            if dataset_filter:
                where += " AND bd.name = %s"
                params.append(dataset_filter)

            base_select = (
                "SELECT ms.id AS submission_id, ms.model_name, bd.name AS dataset_name, bd.task_type, bd.evaluation_metric, bd.reference_data, "
                "er.score, er.evaluation_details, ms.created AS submitted_at, "
                "ms.submitted_by, ms.model_results "
                "FROM model_submissions ms "
                "JOIN benchmark_datasets bd ON ms.benchmark_dataset_id = bd.id "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id "
            )
            order = " ORDER BY bd.name ASC, er.score DESC, ms.id DESC "
            query = base_select + where + order
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            db_leaderboard = _rows_to_leaderboard(rows, 0)
            represented = {
                (row["dataset_name"], row["model_name"])
                for row in db_leaderboard
                if row.get("dataset_name") and row.get("model_name")
            }
            all_rows = db_leaderboard + _leaderboard_data_rows(dataset_filter, represented)
            return jsonify(_finalize_leaderboard_response(
                all_rows,
                dataset_filter,
                page,
                page_size,
                offset,
                use_cursor,
                rank_start,
                an_d,
                an_s,
                an_i,
            ))
        except Exception as e:
            logger.exception("leaderboard_db_read_failed", extra={"error": str(e)})
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    # In-memory fallback
    mem_all = []
    for ev in _STORE["evaluations"]:
        sub = next((s for s in _STORE["submissions"] if s["id"] == ev["submission_id"]), None)
        if not sub:
            continue
        if dataset_filter and sub["benchmark_dataset_name"] != dataset_filter:
            continue
        mem_all.append((ev, sub))
    all_rows = []
    represented = set()
    for ev, sub in mem_all:
        ev_details = ev.get("evaluation_details") or {}
        if not isinstance(ev_details, dict):
            ev_details = {}
        ds_meta = next(
            (d for d in _STORE["datasets"] if d.get("name") == sub["benchmark_dataset_name"]),
            None,
        )
        all_rows.append({
            "rank": 0,
            "submission_id": sub["id"],
            "model_name": sub["model_name"],
            "dataset_name": sub["benchmark_dataset_name"],
            "url": ((ds_meta or {}).get("reference_data") or {}).get("url") if isinstance((ds_meta or {}).get("reference_data"), dict) else None,
            "submission_count": sum(1 for _ev, _sub in mem_all if _sub["benchmark_dataset_name"] == sub["benchmark_dataset_name"]),
            "task_type": (ds_meta or {}).get("task_type") or "translation",
            "evaluation_metric": ev["metric"],
            "score": ev["score"],
            "submitted_by": sub.get("submitted_by"),
            "metadata": ev_details.get("metadata") if ev_details else sub.get("metadata"),
            "detailed_scores": ev_details.get("detailed_scores"),
            "primary_metric": ev_details.get("metric"),
            "submitted_at": sub["created"].isoformat(),
        })
        represented.add((sub["benchmark_dataset_name"], sub["model_name"]))
    all_rows.extend(_leaderboard_data_rows(dataset_filter, represented))
    return jsonify(_finalize_leaderboard_response(
        all_rows,
        dataset_filter,
        page,
        page_size,
        offset,
        use_cursor,
        rank_start,
        an_d,
        an_s,
        an_i,
    ))

# ---------------------------
# Public dataset management
# ---------------------------
@bp.get('/public/datasets')
def list_public_datasets():
    """List active benchmark datasets with basic metadata."""
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT name, task_type, evaluation_metric, reference_data, created, active FROM benchmark_datasets WHERE active = TRUE ORDER BY name"
            )
            rows = cursor.fetchall()
            items = []
            for r in rows:
                extra = {}
                if r.get('reference_data'):
                    try:
                        rd = json.loads(r['reference_data']) if isinstance(r['reference_data'], str) else r['reference_data']
                        if isinstance(rd, dict):
                            # pass through selected user-facing fields if present
                            for k in ('url', 'description'):
                                if k in rd:
                                    extra[k] = rd[k]
                            if isinstance(rd.get('source_texts'), list):
                                extra['size'] = len(rd['source_texts'])
                    except Exception:
                        pass
                items.append({
                    "name": r['name'],
                    "task_type": r['task_type'],
                    "evaluation_metric": r['evaluation_metric'],
                    **extra,
                })
            return jsonify({"success": True, "datasets": items})
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    # Fallback if DB not configured: include curated in-memory datasets too
    fallback = [
        {"name": "flores_spanish_translation", "task_type": "translation", "evaluation_metric": "bleu"},
        {"name": "flores_spanish_translation_bertscore", "task_type": "translation", "evaluation_metric": "bertscore"},
    ]
    for ds in LEADERBOARD_DATA:
        fallback.append({
            "name": ds.get("name"),
            "task_type": ds.get("task_type"),
            "evaluation_metric": ds.get("evaluation_metric", ""),
            "url": ds.get("url"),
            "description": ds.get("description"),
        })
    for ds in _STORE["datasets"]:
        rd = ds.get("reference_data") if isinstance(ds.get("reference_data"), dict) else {}
        fallback.append({
            "name": ds.get("name"),
            "task_type": ds.get("task_type"),
            "evaluation_metric": ds.get("evaluation_metric", ""),
            "url": rd.get("url"),
            "description": rd.get("description"),
            "size": len(rd.get("source_texts", [])) if isinstance(rd.get("source_texts"), list) else None,
        })
    return jsonify({"success": True, "datasets": fallback})


@bp.post('/public/add_dataset')
@rate_limit("ADD_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def add_dataset_public():
    """Create a new benchmark dataset entry.

    Expected JSON:
    {
      "name": str,
      "task_type": str,  # e.g., translation | text_classification | ner | chatbot | prompting
      "evaluation_metric": str,  # e.g., bleu | bertscore | accuracy | f1
      "reference_data": {...}  # optional; may include url, description, source_texts, reference_translations
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        name = validate_text(data.get('name'), "name")
        task_type = validate_text(data.get('task_type'), "task_type", 100)
        evaluation_metric = validate_text(data.get('evaluation_metric'), "evaluation_metric", 100)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    reference_data = data.get('reference_data') or {}

    if not isinstance(reference_data, (dict, list)):
        return jsonify({"success": False, "error": "reference_data must be JSON object or array"}), 400

    conn, cursor = get_db_connection()
    if not (conn and cursor):
        # In-memory: store a shadow dataset in curated data for dev
        existing = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
        if existing:
            return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
        _STORE["datasets"].append({
            "name": name,
            "task_type": task_type,
            "evaluation_metric": evaluation_metric,
            "reference_data": reference_data,
        })
        LEADERBOARD_DATA.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "task_type": task_type,
            "description": reference_data.get('description') if isinstance(reference_data, dict) else None,
            "url": reference_data.get('url') if isinstance(reference_data, dict) else None,
            "models": [],
        })
        logger.info("dataset_added_memory", extra={"dataset": name, "task_type": task_type})
        return jsonify({"success": True, "message": "Dataset added (in-memory)"})

    try:
        cursor.execute(
            "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
            (name, task_type, evaluation_metric, json.dumps(reference_data))
        )
        conn.commit()
        logger.info("dataset_added", extra={"dataset": name, "task_type": task_type})
        return jsonify({"success": True, "message": "Dataset added"})
    except Exception as e:
        if 'Duplicate' in str(e) or 'UNIQUE' in str(e):
            return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
        print(f"add_dataset_public error: {e}")
        return jsonify({"success": False, "error": "Failed to add dataset"}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


def _dataset_details_payload(dataset_core: dict, top_models: list) -> dict:
    """Attach normalized task type, primary metric docs, and per-task metric catalog."""
    tt = dataset_core.get("task_type") or "translation"
    em = dataset_core.get("evaluation_metric") or ""
    tn = normalize_task_type_for_metrics(tt)
    pmd = primary_metric_catalog_entry(em)
    rec = metrics_for_task(tn)
    dataset_out = {
        **dataset_core,
        "task_type_normalized": tn,
        "primary_metric_documentation": pmd,
        "recommended_metrics_for_task": rec,
    }
    return {"success": True, "dataset": dataset_out, "top_models": top_models}


@bp.get('/public/dataset_details')
def dataset_details():
    """Return detailed information about a dataset, including curation meta and top models."""
    raw = request.args.get('name')
    if not raw:
        return jsonify({"success": False, "error": "Missing name"}), 400
    name = raw.strip()
    name_lower = name.lower()

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT id, name, task_type, evaluation_metric, reference_data, created, active "
                "FROM benchmark_datasets WHERE name = %s OR LOWER(TRIM(name)) = LOWER(TRIM(%s))",
                (name, name),
            )
            ds = cursor.fetchone()
            if ds:
                meta = {}
                examples = []
                count = None
                try:
                    rd = json.loads(ds['reference_data']) if isinstance(ds['reference_data'], str) else ds['reference_data']
                    if isinstance(rd, dict):
                        meta['url'] = rd.get('url')
                        meta['description'] = rd.get('description')
                        if isinstance(rd.get('source_texts'), list):
                            examples = rd['source_texts'][:5]
                            count = len(rd['source_texts'])
                except Exception:
                    pass

                cursor.execute(
                    "SELECT ms.model_name, er.score, ms.created as submitted_at "
                    "FROM model_submissions ms JOIN evaluation_results er ON er.model_submission_id = ms.id "
                    "WHERE ms.benchmark_dataset_id = %s ORDER BY er.score DESC LIMIT 10",
                    (ds['id'],),
                )
                rows = cursor.fetchall()
                top_models = [
                    {
                        "model": r['model_name'],
                        "score": float(r['score']),
                        "updated": r['submitted_at'].isoformat() if r.get('submitted_at') else None,
                    }
                    for r in rows
                ]
                core = {
                    "name": ds['name'],
                    "task_type": ds['task_type'],
                    "evaluation_metric": ds['evaluation_metric'],
                    **meta,
                    "size": count,
                    "examples": examples,
                }
                return jsonify(_dataset_details_payload(core, top_models))
        except Exception as e:
            logger.exception("dataset_details_db_error", extra={"error": str(e)})
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    matched = next((d for d in LEADERBOARD_DATA if (d.get('name') or '').lower() == name_lower), None)
    stored = next((d for d in _STORE["datasets"] if (d.get("name") or "").lower() == name_lower), None)
    if stored:
        rd = stored.get("reference_data") if isinstance(stored.get("reference_data"), dict) else {}
        matched = {
            "name": stored.get("name"),
            "task_type": stored.get("task_type"),
            "evaluation_metric": stored.get("evaluation_metric"),
            "url": rd.get("url"),
            "description": rd.get("description"),
            "size": len(rd.get("source_texts", [])) if isinstance(rd.get("source_texts"), list) else None,
            "examples": rd.get("source_texts", [])[:5] if isinstance(rd.get("source_texts"), list) else [],
        }
    if not matched and name_lower.startswith('flores_spanish_translation'):
        matched = {
            "name": name,
            "task_type": "translation",
            "evaluation_metric": "bleu",
            "description": "FLORES-style demo",
            "url": None,
        }
    if not matched:
        matched = UI_FALLBACK_DATASETS_BY_LOWER_NAME.get(name_lower)
    if not matched:
        return jsonify({"success": False, "error": "Dataset not found"}), 404

    fb_static = UI_FALLBACK_DATASETS_BY_LOWER_NAME.get(name_lower)
    if fb_static:
        matched = {
            **fb_static,
            **matched,
            "evaluation_metric": matched.get("evaluation_metric") or fb_static.get("evaluation_metric"),
            "task_type": matched.get("task_type") or fb_static.get("task_type"),
            "url": matched.get("url") or fb_static.get("url"),
            "description": matched.get("description") or fb_static.get("description"),
            "name": matched.get("name") or fb_static.get("name"),
        }

    mem = []
    for ev in _STORE['evaluations']:
        sub = next((s for s in _STORE['submissions'] if s['id'] == ev['submission_id']), None)
        if sub and (sub.get('benchmark_dataset_name') or '').lower() == name_lower:
            mem.append({"model": sub['model_name'], "score": ev['score'], "updated": sub['created'].isoformat()})
    mem.sort(key=lambda x: x['score'], reverse=True)
    examples = matched.get("examples") or _SPANISH_REFERENCES[:5]
    core = {
        "name": matched.get('name'),
        "task_type": matched.get('task_type', 'translation'),
        "evaluation_metric": matched.get('evaluation_metric', 'bleu'),
        "url": matched.get('url'),
        "description": matched.get('description'),
        "size": matched.get("size"),
        "examples": examples,
    }
    return jsonify(_dataset_details_payload(core, mem[:10]))


@bp.get('/public/export/leaderboard')
def export_leaderboard():
    """Export leaderboard rows as CSV or JSON (follows keyset cursors until exhausted)."""
    dataset_name = request.args.get("dataset")
    export_format = (request.args.get("format") or "json").lower()
    rows = []
    next_cur = None
    while True:
        qs: dict = {"page_size": "100"}
        if dataset_name:
            qs["dataset"] = dataset_name
        if next_cur:
            qs["cursor"] = next_cur
        with current_app.test_request_context("/public/get_leaderboard", query_string=qs):
            payload = get_leaderboard().get_json()
        if not payload or not payload.get("success"):
            break
        chunk = payload.get("leaderboard") or []
        rows.extend(chunk)
        next_cur = payload.get("next_cursor")
        if not next_cur:
            break
    if export_format == "json":
        return jsonify(rows)
    if export_format != "csv":
        return jsonify({"success": False, "error": "format must be csv or json"}), 400

    out = StringIO()
    fieldnames = [
        "rank",
        "submission_id",
        "dataset_name",
        "model_name",
        "submitted_by",
        "score",
        "evaluation_metric",
        "primary_metric",
        "detailed_scores_json",
        "submitted_at",
    ]
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        ds = row.get("detailed_scores")
        writer.writerow({
            "rank": row.get("rank"),
            "submission_id": row.get("submission_id"),
            "dataset_name": row.get("dataset_name"),
            "model_name": row.get("model_name"),
            "submitted_by": row.get("submitted_by"),
            "score": row.get("score"),
            "evaluation_metric": row.get("evaluation_metric"),
            "primary_metric": row.get("primary_metric"),
            "detailed_scores_json": json.dumps(ds, ensure_ascii=False, default=str) if ds is not None else "",
            "submitted_at": row.get("submitted_at"),
        })
    filename = f"leaderboard-{dataset_name or 'all'}.csv"
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------
# Leaderboard UI API (per README)
# ---------------------------
@bp.post('/api/leaderboard/add_dataset')
@rate_limit("ADD_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def add_dataset():
    data = request.get_json(silent=True) or {}
    try:
        name = validate_text(data.get("name"), "name")
        task_type = validate_text(data.get("task_type"), "task_type", 100)
        evaluation_metric = validate_text(data.get("evaluation_metric", data.get("metric", "accuracy")), "evaluation_metric", 100)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    dataset_id = str(uuid.uuid4())
    new_ds = {
        "id": dataset_id,
        "name": name,
        "url": data.get("url"),
        "task_type": task_type,
        "evaluation_metric": evaluation_metric,
        "description": data.get("description"),
        "models": data.get("models", []),
    }
    LEADERBOARD_DATA[:] = [ds for ds in LEADERBOARD_DATA if ds.get("name") != name]
    LEADERBOARD_DATA.append(new_ds)
    reference_data = {}
    if data.get("url"):
        reference_data["url"] = data.get("url")
    if data.get("description"):
        reference_data["description"] = data.get("description")
    if data.get("source_texts"):
        reference_data["source_texts"] = data.get("source_texts")
    if data.get("ground_truth"):
        reference_data["ground_truth"] = data.get("ground_truth")
    existing = next((d for d in _STORE["datasets"] if d.get("name") == name), None)
    if existing:
        existing.update({"task_type": task_type, "evaluation_metric": evaluation_metric, "reference_data": reference_data})
    else:
        _STORE["datasets"].append({
            "name": name,
            "task_type": task_type,
            "evaluation_metric": evaluation_metric,
            "reference_data": reference_data,
        })
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute("SELECT id FROM benchmark_datasets WHERE name = %s", (name,))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE benchmark_datasets SET task_type = %s, evaluation_metric = %s, reference_data = %s, active = TRUE WHERE name = %s",
                    (task_type, evaluation_metric, json.dumps(reference_data), name),
                )
            else:
                cursor.execute(
                    "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
                    (name, task_type, evaluation_metric, json.dumps(reference_data)),
                )
            conn.commit()
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    return jsonify({
        "status": "success",
        "message": "Dataset added to leaderboard.",
        "dataset_id": dataset_id,
    })


@bp.post('/api/leaderboard/add_model')
@rate_limit("SUBMIT_MODEL_RATE_LIMIT", "10/minute")
@require_api_key
def add_model():
    data = request.get_json(silent=True) or {}
    required = ["rank", "score", "updated"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"status": "error", "message": f"Missing required fields: {', '.join(missing)}"}), 400
    try:
        dataset_name = validate_text(data.get("dataset_name"), "dataset_name")
        model = validate_text(data.get("model"), "model")
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    target_dataset = next((ds for ds in LEADERBOARD_DATA if ds.get("name") == dataset_name), None)
    if not target_dataset:
        conn_lookup, cursor_lookup = get_db_connection()
        if conn_lookup and cursor_lookup:
            try:
                cursor_lookup.execute(
                    "SELECT name, task_type, evaluation_metric, reference_data FROM benchmark_datasets WHERE name = %s AND active = TRUE",
                    (dataset_name,),
                )
                row = cursor_lookup.fetchone()
                if row:
                    target_dataset = {
                        "name": row["name"],
                        "task_type": row.get("task_type"),
                        "evaluation_metric": row.get("evaluation_metric"),
                        "models": [],
                    }
                    LEADERBOARD_DATA.append(target_dataset)
            finally:
                try:
                    cursor_lookup.close()
                    conn_lookup.close()
                except Exception:
                    pass
    if target_dataset:
            model_row = {
                "rank": data["rank"],
                "model": model,
                "score": data["score"],
                "ci": data.get("ci"),
                "updated": data["updated"],
                "detailed_scores": data.get("detailed_scores"),
            }
            target_dataset.setdefault("models", []).append(model_row)
            # keep models sorted by rank
            target_dataset["models"].sort(key=lambda m: (m.get("rank") is None, m.get("rank")))
            ds_meta = next((d for d in _STORE["datasets"] if d.get("name") == dataset_name), None)
            metric = (ds_meta or {}).get("evaluation_metric") or target_dataset.get("evaluation_metric") or data.get("metric") or "accuracy"
            submission_id = len(_STORE["submissions"]) + 1
            _STORE["submissions"].append({
                "id": submission_id,
                "benchmark_dataset_name": dataset_name,
                "model_name": model,
                "submitted_by": data.get("submitted_by", "seed_real_benchmarks@anote.ai"),
                "submitter_id": data.get("submitter_id", "seed-real-benchmarks"),
                "metadata": {"source": "api/leaderboard/add_model", "rank": data.get("rank"), "updated": data.get("updated")},
                "results": [],
                "created": utc_now(),
            })
            _STORE["evaluations"].append({
                "submission_id": submission_id,
                "score": float(data["score"]),
                "metric": metric,
                "evaluation_details": {
                    "metric": metric,
                    "metadata": {"rank": data.get("rank"), "updated": data.get("updated"), "ci": data.get("ci")},
                    "detailed_scores": data.get("detailed_scores") if isinstance(data.get("detailed_scores"), dict) else {metric: data["score"]},
                },
                "created": utc_now(),
            })
            conn, cursor = get_db_connection()
            if conn and cursor:
                try:
                    cursor.execute("SELECT id FROM benchmark_datasets WHERE name = %s", (dataset_name,))
                    ds_row = cursor.fetchone()
                    if not ds_row:
                        return jsonify({"status": "error", "message": "Dataset not found."}), 404
                    eval_details = {
                        "metric": metric,
                        "metadata": {"rank": data.get("rank"), "updated": data.get("updated"), "ci": data.get("ci")},
                        "detailed_scores": data.get("detailed_scores") if isinstance(data.get("detailed_scores"), dict) else {metric: data["score"]},
                    }
                    cursor.execute(
                        "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, submitter_id, model_results) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (
                            ds_row["id"],
                            model,
                            data.get("submitted_by", "seed_real_benchmarks@anote.ai"),
                            data.get("submitter_id", "seed-real-benchmarks"),
                            json.dumps([]),
                        ),
                    )
                    db_submission_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) VALUES (%s, %s, %s)",
                        (db_submission_id, float(data["score"]), json.dumps(eval_details)),
                    )
                    conn.commit()
                finally:
                    try:
                        cursor.close()
                        conn.close()
                    except Exception:
                        pass
            return jsonify({"status": "success", "message": "Model added to dataset on leaderboard."})
    return jsonify({"status": "error", "message": "Dataset not found."}), 404


def _unwrapped_route(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _seed_builtin_leaderboard_data() -> dict[str, int]:
    try:
        from scripts.seed_real_benchmarks import DATASETS, detailed_scores  # type: ignore
    except ImportError:
        from backend.scripts.seed_real_benchmarks import DATASETS, detailed_scores  # type: ignore

    dataset_fn = _unwrapped_route(add_dataset)
    model_fn = _unwrapped_route(add_model)
    models_added = 0
    for dataset in DATASETS:
        with current_app.test_request_context(
            "/api/leaderboard/add_dataset",
            method="POST",
            json={
                "name": dataset["name"],
                "task_type": dataset["task_type"],
                "evaluation_metric": dataset["evaluation_metric"],
                "url": dataset["url"],
                "description": dataset.get("description", f"Seeded benchmark card for {dataset['name']}."),
                "source_texts": (dataset.get("reference_data") or {}).get("source_texts", []),
                "ground_truth": (dataset.get("reference_data") or {}).get("ground_truth", []),
            },
        ):
            dataset_fn()
        for model in dataset.get("models", []):
            payload = {
                **model,
                "dataset_name": dataset["name"],
                "detailed_scores": detailed_scores(
                    dataset["task_type"],
                    dataset["evaluation_metric"],
                    float(model["score"]),
                ),
            }
            with current_app.test_request_context("/api/leaderboard/add_model", method="POST", json=payload):
                resp = model_fn()
            status_code = getattr(resp, "status_code", 200)
            if status_code < 400:
                models_added += 1
    return {"seeded": len(DATASETS), "models_added": models_added}


@bp.post('/api/leaderboard/seed')
@require_admin
def seed_leaderboard_data() -> Any:
    """Seed built-in benchmark datasets and runnable samples."""
    return jsonify(_seed_builtin_leaderboard_data())


@bp.get('/api/leaderboard/list')
def list_leaderboard_datasets():
    """Return the curated leaderboard datasets and their models (in-memory).

    Response:
    {
      "status": "success",
      "datasets": [ { id, name, url, task_type, description, models: [...] }, ... ]
    }
    """
    return jsonify({
        "status": "success",
        "datasets": LEADERBOARD_DATA,
    })

_AUTO_SEED_DONE = False
_AUTO_SEED_LOCK = threading.Lock()
_REQUIRED_SEED_DATASETS = {"SST-2 Sentiment (Sample)"}


def _truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _leaderboard_has_any_rows() -> bool:
    if any((ds.get("models") or []) for ds in LEADERBOARD_DATA):
        return True
    if _STORE.get("evaluations"):
        return True
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT COUNT(*) AS total "
                "FROM model_submissions ms "
                "JOIN evaluation_results er ON er.model_submission_id = ms.id"
            )
            row = cursor.fetchone() or {}
            return int(row.get("total", 0)) > 0
        except Exception as e:
            logger.warning("auto_seed_count_failed", extra={"error": str(e)})
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    return False


def _ensure_required_datasets() -> dict[str, int]:
    """Add required runnable seed datasets that may be missing from an older DB."""
    try:
        from scripts.seed_real_benchmarks import DATASETS  # type: ignore
    except ImportError:
        from backend.scripts.seed_real_benchmarks import DATASETS  # type: ignore

    required = [d for d in DATASETS if d.get("name") in _REQUIRED_SEED_DATASETS]
    added = 0
    dataset_fn = _unwrapped_route(add_dataset)

    for dataset in required:
        name = dataset["name"]
        exists = any(d.get("name") == name for d in _STORE.get("datasets", []))
        if not exists:
            conn, cursor = get_db_connection()
            if conn and cursor:
                try:
                    cursor.execute("SELECT id FROM benchmark_datasets WHERE name = %s", (name,))
                    exists = bool(cursor.fetchone())
                except Exception as e:
                    logger.warning("required_dataset_check_failed", extra={"dataset": name, "error": str(e)})
                finally:
                    try:
                        cursor.close()
                        conn.close()
                    except Exception:
                        pass

        if exists:
            continue

        with current_app.test_request_context(
            "/api/leaderboard/add_dataset",
            method="POST",
            json={
                "name": name,
                "task_type": dataset["task_type"],
                "evaluation_metric": dataset["evaluation_metric"],
                "url": dataset["url"],
                "description": dataset.get("description", f"Seeded benchmark card for {name}."),
                "source_texts": (dataset.get("reference_data") or {}).get("source_texts", []),
                "ground_truth": (dataset.get("reference_data") or {}).get("ground_truth", []),
            },
        ):
            dataset_fn()
        added += 1

    return {"required_datasets_added": added}


@bp.before_request
def _auto_seed_once() -> None:
    global _AUTO_SEED_DONE
    if _AUTO_SEED_DONE:
        return
    if _truthy_env("DISABLE_LEADERBOARD_AUTO_SEED"):
        _AUTO_SEED_DONE = True
        return
    if os.getenv("PYTEST_CURRENT_TEST") and not _truthy_env("LEADERBOARD_AUTO_SEED_IN_TESTS"):
        return
    with _AUTO_SEED_LOCK:
        if _AUTO_SEED_DONE:
            return
        _AUTO_SEED_DONE = True
        try:
            if _leaderboard_has_any_rows():
                summary = _ensure_required_datasets()
                if summary.get("required_datasets_added"):
                    logger.info("leaderboard_required_datasets_seeded", extra=summary)
                return
            summary = _seed_builtin_leaderboard_data()
            logger.info("leaderboard_auto_seeded", extra=summary)
        except Exception as e:
            logger.exception("leaderboard_auto_seed_failed", extra={"error": str(e)})
