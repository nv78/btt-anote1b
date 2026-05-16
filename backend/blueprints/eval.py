from flask import Blueprint, Response, current_app, request, jsonify, redirect

from shared import *

bp = Blueprint("eval", __name__)
app = bp

@bp.get('/public/get_source_sentences')
def get_source_sentences():
    """Return source sentences users should translate.

    Query params:
      - dataset_name (optional): defaults to 'flores_spanish_translation'
      - count (optional): number of sentences to return (default 3)
      - start_idx (optional): starting index in the pool (default 0)
    """
    dataset_name = request.args.get('dataset_name', 'flores_spanish_translation')
    try:
        count = int(request.args.get('count', 3))
        start_idx = int(request.args.get('start_idx', 0))
    except ValueError:
        return jsonify({"success": False, "error": "Invalid count or start_idx"}), 400

    # Try to pull from DB reference_data if available
    pool = None
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            try:
                cursor.execute(
                    "SELECT reference_data, questions_public FROM benchmark_datasets WHERE name = %s AND active = TRUE",
                    (dataset_name,)
                )
            except Exception:
                cursor.execute(
                    "SELECT reference_data FROM benchmark_datasets WHERE name = %s AND active = TRUE",
                    (dataset_name,)
                )
            row = cursor.fetchone()
            if row:
                if not bool(row.get('questions_public', 1)):
                    try:
                        ref = json.loads(row['reference_data']) if isinstance(row.get('reference_data'), str) else (row.get('reference_data') or {})
                        n = len(ref.get('source_texts') or ref.get('ground_truth') or [])
                    except Exception:
                        n = 0
                    try: cursor.close(); conn.close()
                    except Exception: pass
                    return jsonify({
                        "success": False,
                        "questions_public": False,
                        "question_count": n,
                        "error": "Questions for this dataset are hidden. Use IDs 0–{} when submitting.".format(n - 1),
                    }), 403
                if row.get('reference_data'):
                    try:
                        ref = json.loads(row['reference_data']) if isinstance(row['reference_data'], str) else row['reference_data']
                        if isinstance(ref, dict) and isinstance(ref.get('source_texts'), list):
                            pool = ref['source_texts']
                    except Exception:
                        pool = None
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

    # If DB not available or no source_texts provided, fallback pools by dataset
    if not pool:
        if dataset_name.startswith('flores_spanish_translation'):
            pool = _SPANISH_REFERENCES
        else:
            pool = _SPANISH_REFERENCES

    if start_idx < 0:
        start_idx = 0
    end_idx = min(start_idx + count, len(pool))
    selected = pool[start_idx:end_idx]
    sentence_ids = list(range(start_idx, end_idx))

    return jsonify({
        "success": True,
        "dataset_name": dataset_name,
        "sentence_ids": sentence_ids,
        "source_sentences": selected,
        "count": len(selected),
    })

@bp.post('/public/import_hf_dataset')
@rate_limit("IMPORT_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def import_hf_dataset_public():
    """Import a bounded Hugging Face dataset split into benchmark_datasets/reference_data."""
    data = request.get_json(silent=True) or {}
    try:
        try:
            from hf_importer import import_hf_dataset  # type: ignore
        except Exception:
            from backend.hf_importer import import_hf_dataset  # type: ignore
        payload = import_hf_dataset(
            dataset_name=data.get("dataset_name") or data.get("name"),
            config=data.get("config"),
            split=data.get("split", "test"),
            limit=int(data.get("limit", 100)),
            task_type=data.get("task_type"),
            display_name=data.get("display_name"),
            leaderboard_dataset_id=data.get("leaderboard_dataset_id") or data.get("dataset_id"),
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    if data.get("preview_only"):
        preview = dict(payload)
        rd = dict(preview.get("reference_data") or {})
        rd["source_texts"] = rd.get("source_texts", [])[:5]
        rd["ground_truth"] = rd.get("ground_truth", [])[:5]
        preview["reference_data"] = rd
        return jsonify({"success": True, "dataset": preview})

    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "INSERT INTO benchmark_datasets (name, task_type, evaluation_metric, reference_data, active) VALUES (%s, %s, %s, %s, TRUE)",
                (
                    payload["name"],
                    payload["task_type"],
                    payload["evaluation_metric"],
                    json.dumps(payload["reference_data"]),
                ),
            )
            conn.commit()
        except Exception as e:
            if 'Duplicate' in str(e) or 'UNIQUE' in str(e):
                return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
            return jsonify({"success": False, "error": "Failed to import dataset"}), 500
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    else:
        if any(d.get("name") == payload["name"] for d in _STORE["datasets"]):
            return jsonify({"success": False, "error": "Dataset with this name already exists"}), 400
        _STORE["datasets"].append(payload)
        LEADERBOARD_DATA.append({
            "id": str(uuid.uuid4()),
            "name": payload["name"],
            "task_type": payload["task_type"],
            "description": payload["reference_data"].get("description"),
            "url": payload["reference_data"].get("url"),
            "models": [],
        })

    return jsonify({
        "success": True,
        "message": "Dataset imported",
        "dataset": {
            "name": payload["name"],
            "task_type": payload["task_type"],
            "evaluation_metric": payload["evaluation_metric"],
            "size": len(payload["reference_data"].get("source_texts", [])),
        },
    })


def _dataset_by_name(dataset_name: str) -> dict[str, Any] | None:
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute(
                "SELECT id, name, task_type, evaluation_metric, reference_data FROM benchmark_datasets WHERE name = %s AND active = TRUE",
                (dataset_name,),
            )
            row = cursor.fetchone()
            if row:
                return row
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    return next((d for d in _STORE["datasets"] if d.get("name") == dataset_name), None)


def _reference_data_dict(reference_data: object) -> dict[str, Any]:
    if isinstance(reference_data, str):
        try:
            parsed = json.loads(reference_data)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return reference_data if isinstance(reference_data, dict) else {}


def _source_items_from_reference_data(reference_data: dict[str, Any]) -> list[dict[str, Any]]:
    ground_truth = reference_data.get("ground_truth")
    if isinstance(ground_truth, list) and ground_truth:
        items = []
        for idx, row in enumerate(ground_truth):
            row = row if isinstance(row, dict) else {"question": str(row)}
            input_text = row.get("question") or row.get("sentence") or row.get("text") or row.get("input") or row.get("source") or ""
            context = row.get("context") or row.get("passage") or row.get("document") or ""
            items.append({"id": idx, "input": str(input_text), "context": str(context) if context is not None else ""})
        return items
    source_texts = reference_data.get("source_texts") if isinstance(reference_data.get("source_texts"), list) else []
    contexts = reference_data.get("contexts") if isinstance(reference_data.get("contexts"), list) else []
    return [
        {"id": idx, "input": str(text), "context": str(contexts[idx]) if idx < len(contexts) else ""}
        for idx, text in enumerate(source_texts)
    ]


def _answers_from_reference_data(reference_data: dict[str, Any], task_type: str, ids: list[int]) -> tuple[list[Any] | None, list[Any] | None, list[Any] | None, list[Any] | None]:
    def by_key(key: str) -> list[Any] | None:
        values = reference_data.get(key)
        if not isinstance(values, list):
            return None
        try:
            return [values[i] for i in ids]
        except Exception:
            return None

    labels = by_key("labels")
    entities = by_key("entities")
    answers = by_key("answers")
    translations = by_key("reference_translations")
    gt = reference_data.get("ground_truth")
    if isinstance(gt, list):
        rows = [gt[i] for i in ids if 0 <= i < len(gt)]
        if len(rows) == len(ids):
            row_answers = [r.get("answer") if isinstance(r, dict) else r for r in rows]
            if task_type == "text_classification" and labels is None:
                labels = row_answers
            elif task_type == "named_entity_recognition" and entities is None:
                entities = row_answers
            elif task_type in ("document_qa", "line_qa", "retrieval") and answers is None:
                answers = row_answers
            elif task_type == "translation" and translations is None:
                translations = row_answers
    return labels, entities, answers, translations


def _normalize_hf_classification_label(raw_label: object, label_names: list[Any] | None) -> str:
    label = str(raw_label).strip()
    lower = label.lower()
    if lower.startswith("label_"):
        try:
            idx = int(lower.split("_", 1)[1])
            if label_names and 0 <= idx < len(label_names):
                return str(label_names[idx]).strip().lower()
        except Exception:
            pass
    return lower


def _run_hf_predictions(model_id: str, task_type: str, items: list[dict[str, Any]], batch_size: int, reference_data: dict[str, Any]) -> list[Any]:
    try:
        from transformers import pipeline  # type: ignore
    except Exception as exc:
        raise RuntimeError("Install optional transformers/torch dependencies to run Hugging Face models.") from exc

    if task_type == "text_classification":
        pipe = pipeline("text-classification", model=model_id, tokenizer=model_id)
        label_names = reference_data.get("label_names") if isinstance(reference_data.get("label_names"), list) else None
        outputs: list[Any] = []
        for start in range(0, len(items), batch_size):
            batch = [it["input"] for it in items[start:start + batch_size]]
            chunk = pipe(batch, truncation=True)
            for row in chunk:
                if isinstance(row, list):
                    row = row[0] if row else {}
                outputs.append(_normalize_hf_classification_label((row or {}).get("label", ""), label_names))
        return outputs

    if task_type in ("document_qa", "line_qa"):
        pipe = pipeline("question-answering", model=model_id, tokenizer=model_id)
        outputs = []
        for it in items:
            result = pipe(question=it["input"], context=it.get("context") or it["input"])
            outputs.append(result.get("answer", "") if isinstance(result, dict) else "")
        return outputs

    if task_type == "named_entity_recognition":
        pipe = pipeline("ner", model=model_id, tokenizer=model_id, aggregation_strategy="simple")
        outputs = []
        for it in items:
            result = pipe(it["input"])
            outputs.append([
                (str(ent.get("word", "")).strip(), str(ent.get("entity_group") or ent.get("entity") or "").strip())
                for ent in result or []
                if isinstance(ent, dict)
            ])
        return outputs

    if task_type == "translation":
        pipe = pipeline("translation", model=model_id, tokenizer=model_id)
        outputs = []
        for start in range(0, len(items), batch_size):
            batch = [it["input"] for it in items[start:start + batch_size]]
            chunk = pipe(batch)
            for row in chunk:
                if isinstance(row, list):
                    row = row[0] if row else {}
                outputs.append((row or {}).get("translation_text") or (row or {}).get("generated_text") or "")
        return outputs

    raise ValueError(f"HF model runner does not support task_type={task_type!r}")


def _persist_evaluated_submission(dataset_name: str, model_name: str, submitted_by: str, submitter_id: str, model_results: list[Any], score: float, metric: str, eval_details: dict[str, Any]) -> int:
    conn, cursor = get_db_connection()
    if conn and cursor:
        try:
            cursor.execute("SELECT id FROM benchmark_datasets WHERE name = %s", (dataset_name,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Dataset not found")
            cursor.execute(
                "INSERT INTO model_submissions (benchmark_dataset_id, model_name, submitted_by, submitter_id, model_results) VALUES (%s, %s, %s, %s, %s)",
                (row["id"], model_name, submitted_by, submitter_id, json.dumps(model_results)),
            )
            submission_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO evaluation_results (model_submission_id, score, evaluation_details) VALUES (%s, %s, %s)",
                (submission_id, float(score), json.dumps(eval_details)),
            )
            conn.commit()
            return int(submission_id)
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
    submission_id = len(_STORE["submissions"]) + 1
    _STORE["submissions"].append({
        "id": submission_id,
        "benchmark_dataset_name": dataset_name,
        "model_name": model_name,
        "submitted_by": submitted_by,
        "submitter_id": submitter_id,
        "metadata": eval_details.get("metadata"),
        "results": model_results,
        "created": utc_now(),
    })
    _STORE["evaluations"].append({
        "submission_id": submission_id,
        "score": float(score),
        "metric": metric,
        "evaluation_details": eval_details,
        "created": utc_now(),
    })
    return submission_id


def _run_hf_model_job(data: dict[str, Any]) -> dict[str, Any]:
    dataset_name = validate_text(data.get("dataset_name"), "dataset_name")
    model_id = validate_text(data.get("model_id"), "model_id", 255)
    batch_size = max(1, min(128, int(data.get("batch_size", 16))))
    dataset = _dataset_by_name(dataset_name)
    if not dataset:
        raise ValueError("Dataset not found")
    task_type = str(dataset.get("task_type") or "text_classification")
    metric = str(dataset.get("evaluation_metric") or "accuracy")
    reference_data = _reference_data_dict(dataset.get("reference_data"))
    items = _source_items_from_reference_data(reference_data)
    if not items:
        raise ValueError("Dataset has no runnable source texts")
    ids = [int(it["id"]) for it in items]
    predictions = _run_hf_predictions(model_id, task_type, items, batch_size, reference_data)
    labels, entities, answers, translations = _answers_from_reference_data(reference_data, task_type, ids)
    try:
        from eval_core.leaderboard_bridge import normalize_eval_metric, run_personal_eval  # type: ignore
    except ImportError:
        from backend.eval_core.leaderboard_bridge import normalize_eval_metric, run_personal_eval  # type: ignore
    score, detailed_scores = run_personal_eval(task_type, metric, ids, labels, entities, answers, translations, predictions)
    metric_norm = normalize_eval_metric(metric, task_type)
    eval_details = {
        "metric": metric_norm,
        "metadata": {"source": "hf_model_runner", "model_id": model_id, "batch_size": batch_size},
        "detailed_scores": detailed_scores,
    }
    submission_id = _persist_evaluated_submission(
        dataset_name,
        model_id,
        "hf_model_runner@anote.ai",
        f"hf-model:{model_id}"[:255],
        predictions,
        float(score),
        metric_norm,
        eval_details,
    )
    return {
        "success": True,
        "submission_id": submission_id,
        "dataset_name": dataset_name,
        "model_id": model_id,
        "score": float(score),
        "metric": metric_norm,
        "detailed_scores": detailed_scores,
    }


@bp.post('/public/run_hf_model')
@rate_limit("RUN_HF_MODEL_RATE_LIMIT", "3/minute")
@require_api_key
def run_hf_model_public() -> Any:
    """Run an installed Hugging Face pipeline model against a stored dataset."""
    data = request.get_json(silent=True) or {}
    if data.get("async"):
        job_id = str(uuid.uuid4())
        with _EVAL_JOBS_LOCK:
            _EVAL_JOBS[job_id] = {"status": "pending", "kind": "hf_model"}

        def _worker() -> None:
            try:
                out = _run_hf_model_job(data)
                with _EVAL_JOBS_LOCK:
                    _EVAL_JOBS[job_id] = {"status": "completed", **out}
            except Exception as e:
                with _EVAL_JOBS_LOCK:
                    _EVAL_JOBS[job_id] = {"status": "failed", "error": str(e)}

        threading.Thread(target=_worker, daemon=True).start()
        return jsonify({"success": True, "job_id": job_id, "status": "pending"}), 202
    try:
        return jsonify(_run_hf_model_job(data))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("run_hf_model_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": str(e)}), 500


@bp.post('/api/datasets/ingest')
@rate_limit("IMPORT_DATASET_RATE_LIMIT", "5/minute")
@require_api_key
def ingest_dataset():
    """Issue-compatible ingestion endpoint for Hugging Face sources."""
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "").lower()
    if source not in {"huggingface", "hf"}:
        return jsonify({"success": False, "error": "Only source=huggingface is currently supported"}), 400
    mapped = {
        "dataset_name": data.get("dataset_id") or data.get("dataset_name"),
        "config": data.get("config"),
        "split": data.get("split", "test"),
        "limit": data.get("max_samples", data.get("limit", 100)),
        "task_type": data.get("task_type"),
        "display_name": data.get("display_name"),
        "preview_only": data.get("preview_only", False),
        "leaderboard_dataset_id": data.get("leaderboard_dataset_id") or data.get("dataset_id"),
    }
    with current_app.test_request_context(
        "/public/import_hf_dataset",
        method="POST",
        json=mapped,
        headers=dict(request.headers),
    ):
        return import_hf_dataset_public()

# ---------------------------
# CSV Benchmarks (benchmark_csvs folder)
# ---------------------------
@bp.get('/public/benchmark_csvs')
def list_benchmark_csvs():
    if not csv_bench:
        return jsonify({"success": False, "error": "CSV benchmark module unavailable"}), 500
    items = csv_bench.list_csv_datasets()
    # Only return filename and inferred task for brevity
    return jsonify({
        "success": True,
        "datasets": [
            {"filename": it["filename"], "task_type": it["task_type"], "columns": it.get("columns")}
            for it in items
        ]
    })


@bp.get('/public/benchmark_models')
def list_benchmark_models():
    try:
        import models as _mdl  # type: ignore
        models = _mdl.list_models()
        return jsonify({"success": True, "models": models})
    except Exception as e:
        print(f"list_benchmark_models error: {e}")
        return jsonify({"success": False, "error": "Model list unavailable"}), 500

@bp.post('/public/run_csv_benchmarks')
@rate_limit("RUN_CSV_RATE_LIMIT", "5/minute")
@require_api_key
def run_csv_benchmarks():
    """Run evaluations over CSV datasets using provided model configs.

    Body JSON:
      {
        "models": [
          {"name": "gpt-4o", "provider": "openai", "model": "gpt-4o-mini"},
          {"name": "llama3", "provider": "ollama", "model": "llama3:8b"},
          {"name": "echo", "provider": "echo"}
        ],
        "datasets": ["Commonsense.csv", ...],  # optional subset
        "sample_size": 25                         # optional per dataset
      }
    """
    if not csv_bench:
        return jsonify({"success": False, "error": "CSV benchmark module unavailable"}), 500
    data = request.get_json(silent=True) or {}
    models = data.get('models') or []
    datasets = data.get('datasets')
    sample_size = int(data.get('sample_size', 25))
    if not isinstance(models, list) or not models:
        # If no models provided, try backend/models.py list_models()
        try:
            import models as _mdl  # type: ignore
            models = _mdl.list_models()
        except Exception:
            return jsonify({"success": False, "error": "Missing models list"}), 400
    try:
        summary = csv_bench.run_benchmarks(models=models, datasets=datasets, sample_size=sample_size)
        return jsonify({"success": True, **summary})
    except Exception as e:
        print(f"CSV benchmarks error: {e}")
        return jsonify({"success": False, "error": "Failed to run benchmarks"}), 500
