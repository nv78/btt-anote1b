#!/usr/bin/env python3
"""
Run an OpenAI or Anthropic chat model on a dataset in the leaderboard DB, then
submit predictions and evaluate (same path as submit_predictions_from_file).

Requires API keys in environment. Copy .env.example to .env in Personal/.

Examples:
  cd Personal && cp .env.example .env
  # edit .env with OPENAI_API_KEY or ANTHROPIC_API_KEY

  PYTHONPATH=. python scripts/run_llm_on_dataset.py \\
    --dataset-id <uuid> \\
    --model-name gpt-4o-mini_run1

  PYTHONPATH=. python scripts/run_llm_on_dataset.py \\
    --provider anthropic \\
    --dataset-id <uuid> \\
    --model-name claude_haiku_run1 \\
    --limit 50
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # Repo root .env first, then Personal/.env overrides (handy when running from Personal/)
    load_dotenv(os.path.join(REPO_ROOT, ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=True)


def _strip_code_fence(s: str) -> str:
    t = s.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _parse_json_object(raw: str) -> Dict[str, Any]:
    t = _strip_code_fence(raw)
    return json.loads(t)


def _example_text(item: Dict[str, Any]) -> str:
    for key in ("sentence", "text", "question"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    parts = []
    for key in ("title", "body"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    return " ".join(parts) if parts else ""


def _norm_label(x: Any) -> str:
    if isinstance(x, list) and x:
        x = x[0]
    return str(x).strip()


def _classification_labels(ground_truth: List[Dict[str, Any]]) -> List[str]:
    labels = {_norm_label(g["answer"]) for g in ground_truth if "answer" in g}
    return sorted(labels, key=lambda s: s.lower())


def _ner_types(ground_truth: List[Dict[str, Any]]) -> List[str]:
    types: set[str] = set()
    for g in ground_truth:
        for ent in g.get("answer") or []:
            if isinstance(ent, (list, tuple)) and len(ent) >= 2:
                types.add(str(ent[1]))
    return sorted(types)


def _complete_chat(
    *,
    provider: str,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    provider = provider.lower().strip()
    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as e:
            raise SystemExit("Install OpenAI SDK: pip install openai") from e
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("OPENAI_API_KEY is not set")
        base = os.environ.get("OPENAI_BASE_URL")
        client = OpenAI(api_key=key, base_url=base or None)
        r = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        msg = r.choices[0].message.content
        return (msg or "").strip()
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError as e:
            raise SystemExit("Install Anthropic SDK: pip install anthropic") from e
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not set")
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: List[str] = []
        for block in r.content:
            if getattr(block, "text", None):
                parts.append(block.text)
        return "".join(parts).strip()
    raise SystemExit(f"Unknown LLM_PROVIDER / --provider: {provider!r} (use openai or anthropic)")


def _predict_classification(
    item: Dict[str, Any],
    labels: Sequence[str],
    *,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    text = _example_text(item)
    if not text:
        raise ValueError("No text/sentence/question in example")
    label_line = ", ".join(repr(l) for l in labels)
    system = (
        "You are a strict text classifier. Output only a single JSON object, no markdown, "
        'with key "label". The value must be exactly one of the allowed labels (same spelling).'
    )
    user = f"Allowed labels: {label_line}\n\nText:\n{text}\n\nRespond with JSON only, e.g. {{\n  \"label\": \"...\"\n}}"
    raw = _complete_chat(
        provider=provider,
        system=system,
        user=user,
        model=model,
        temperature=temperature,
        max_tokens=max(32, min(max_tokens, 128)),
    )
    try:
        obj = _parse_json_object(raw)
        lab = obj.get("label", obj.get("answer"))
        if lab is None:
            raise KeyError("label")
        return _norm_label(lab)
    except (json.JSONDecodeError, KeyError, TypeError):
        line = raw.splitlines()[0].strip() if raw else ""
        return _norm_label(line) if line else "unknown"


def _predict_qa(
    item: Dict[str, Any],
    *,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    q = str(item.get("question") or "").strip()
    ctx = str(item.get("context") or "").strip()
    system = (
        "You answer questions concisely. Output only a single JSON object, no markdown, "
        'with key "answer" — a short string (extractive style when a passage is given).'
    )
    if ctx:
        user = f"Context:\n{ctx}\n\nQuestion:\n{q}\n\nRespond with JSON only."
    else:
        user = f"Question:\n{q}\n\nRespond with JSON only, e.g. {{\n  \"answer\": \"...\"\n}}"
    raw = _complete_chat(
        provider=provider,
        system=system,
        user=user,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        obj = _parse_json_object(raw)
        ans = obj.get("answer", obj.get("response"))
        if ans is None:
            raise KeyError("answer")
        if isinstance(ans, list):
            ans = ans[0] if ans else ""
        return str(ans).strip()
    except (json.JSONDecodeError, KeyError, TypeError):
        return raw.strip() if raw else ""


def _predict_ner(
    item: Dict[str, Any],
    types_hint: Sequence[str],
    *,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> List[List[str]]:
    text = str(item.get("text") or item.get("sentence") or item.get("question") or "").strip()
    if not text:
        raise ValueError("No text field for NER example")
    type_line = ", ".join(types_hint) if types_hint else "any reasonable type string"
    system = (
        "You are an NER system. Output only a single JSON object, no markdown, with key "
        '"entities": a list of [surface_form, TYPE] pairs. Use exact spans from the text.'
    )
    user = f"Allowed TYPE examples (use similar strings): {type_line}\n\nText:\n{text}\n\nJSON only."
    raw = _complete_chat(
        provider=provider,
        system=system,
        user=user,
        model=model,
        temperature=temperature,
        max_tokens=max(max_tokens, 2048),
    )
    try:
        obj = _parse_json_object(raw)
        ents = obj.get("entities", obj.get("spans"))
        if not isinstance(ents, list):
            raise TypeError("entities must be a list")
        out: List[List[str]] = []
        for e in ents:
            if isinstance(e, (list, tuple)) and len(e) >= 2:
                out.append([str(e[0]).strip(), str(e[1]).strip()])
            elif isinstance(e, dict):
                surf = e.get("text") or e.get("surface") or e.get("mention")
                typ = e.get("type") or e.get("label")
                if surf is not None and typ is not None:
                    out.append([str(surf).strip(), str(typ).strip()])
        return out
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _predict_translation(
    item: Dict[str, Any],
    *,
    target_lang: str,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    src = str(
        item.get("source")
        or item.get("source_text")
        or item.get("question")
        or item.get("text")
        or ""
    ).strip()
    if not src:
        raise ValueError("No source text for translation")
    system = (
        "You are a professional translator. Output only a single JSON object, no markdown, "
        f'with key "translation" in {target_lang}.'
    )
    user = f"Translate the following into {target_lang}.\n\nSource:\n{src}\n\nJSON only."
    raw = _complete_chat(
        provider=provider,
        system=system,
        user=user,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        obj = _parse_json_object(raw)
        t = obj.get("translation", obj.get("target"))
        if t is None:
            raise KeyError("translation")
        return str(t).strip()
    except (json.JSONDecodeError, KeyError, TypeError):
        return raw.strip() if raw else ""


def _resolve_provider_and_model(args: argparse.Namespace) -> Tuple[str, str]:
    prov = (args.provider or os.environ.get("LLM_PROVIDER") or "openai").lower().strip()
    if prov == "openai":
        model = args.model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        return prov, model
    if prov == "anthropic":
        model = args.model or os.environ.get("ANTHROPIC_MODEL") or "claude-3-5-haiku-20241022"
        return prov, model
    raise SystemExit(f"Unknown provider {prov!r}")


def main() -> None:
    _load_dotenv()

    parser = argparse.ArgumentParser(
        description="OpenAI/Anthropic -> full predictions -> evaluate_submission",
    )
    parser.add_argument("--dataset-id", required=True, help="Dataset.id in the leaderboard DB")
    parser.add_argument("--model-name", required=True, help="Leaderboard model_name for this run")
    parser.add_argument("--model-version", default="", help="Optional version string")
    parser.add_argument(
        "--organization",
        default="",
        help="Optional organization string stored on the submission",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="openai | anthropic (default: env LLM_PROVIDER or openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model id (default: OPENAI_MODEL or ANTHROPIC_MODEL from env)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max examples (default: all)")
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between API calls (rate limiting)",
    )
    parser.add_argument(
        "--target-lang",
        default="English",
        help="For translation task: target language name for the prompt",
    )
    parser.add_argument(
        "--predictions-out",
        default=None,
        help="Write predictions JSON array to this path before evaluate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print predictions JSON to stdout; do not write DB",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow submitting fewer predictions than the dataset has rows (scores use full GT; unevaluated rows often count as failures). Prefer a smaller imported dataset instead.",
    )
    args = parser.parse_args()

    temperature = float(os.environ.get("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "1024"))

    provider, model_id = _resolve_provider_and_model(args)

    os.chdir(ROOT)

    from database import SessionLocal, init_db
    from models import Dataset, Submission, SubmissionStatus, TaskType
    from evaluation_service import evaluate_submission, validate_complete_predictions

    init_db()
    db = SessionLocal()
    try:
        ds = db.query(Dataset).filter(Dataset.id == args.dataset_id).first()
        if not ds:
            print(f"Dataset not found: {args.dataset_id!r}", file=sys.stderr)
            sys.exit(1)

        full_gt: List[Dict[str, Any]] = list(ds.ground_truth or [])
        gt_full: List[Dict[str, Any]] = list(full_gt)
        if args.limit is not None:
            gt_full = gt_full[: max(0, args.limit)]
        if not gt_full:
            print("No examples (empty ground_truth or limit=0).", file=sys.stderr)
            sys.exit(1)
        if (
            not args.dry_run
            and not args.allow_partial
            and len(gt_full) < len(full_gt)
        ):
            print(
                "You are only predicting for a subset of the dataset (see --limit). "
                "The DB evaluator scores against the full dataset, so missing examples "
                "skew metrics. Re-run without --limit, or pass --allow-partial if you "
                "really want this.",
                file=sys.stderr,
            )
            sys.exit(1)

        task = ds.task_type
        predictions: List[Dict[str, Any]] = []

        if task == TaskType.TEXT_CLASSIFICATION:
            labels = _classification_labels(gt_full)
            for i, item in enumerate(gt_full):
                pred = _predict_classification(
                    item,
                    labels,
                    provider=provider,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                predictions.append({"id": item["id"], "prediction": pred})
                if args.sleep and i + 1 < len(gt_full):
                    time.sleep(args.sleep)
        elif task in (TaskType.DOCUMENT_QA, TaskType.LINE_QA):
            for i, item in enumerate(gt_full):
                pred = _predict_qa(
                    item,
                    provider=provider,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                predictions.append({"id": item["id"], "prediction": pred})
                if args.sleep and i + 1 < len(gt_full):
                    time.sleep(args.sleep)
        elif task == TaskType.NAMED_ENTITY_RECOGNITION:
            types_hint = _ner_types(gt_full)
            for i, item in enumerate(gt_full):
                pred = _predict_ner(
                    item,
                    types_hint,
                    provider=provider,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                predictions.append({"id": item["id"], "prediction": pred})
                if args.sleep and i + 1 < len(gt_full):
                    time.sleep(args.sleep)
        elif task == TaskType.TRANSLATION:
            for i, item in enumerate(gt_full):
                pred = _predict_translation(
                    item,
                    target_lang=args.target_lang,
                    provider=provider,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                predictions.append({"id": item["id"], "prediction": pred})
                if args.sleep and i + 1 < len(gt_full):
                    time.sleep(args.sleep)
        elif task == TaskType.RETRIEVAL:
            print(
                "Retrieval is not supported by this script (needs ranked doc ids / corpus in prompt). "
                "Use a dedicated pipeline or HF runner.",
                file=sys.stderr,
            )
            sys.exit(2)
        else:
            print(f"Unsupported task_type: {task!r}", file=sys.stderr)
            sys.exit(2)

        try:
            validate_complete_predictions(gt_full, predictions)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

        if args.predictions_out:
            with open(args.predictions_out, "w", encoding="utf-8") as f:
                json.dump(predictions, f, indent=2, ensure_ascii=False)
            print(f"wrote {args.predictions_out}", file=sys.stderr)

        if args.dry_run:
            print(json.dumps(predictions, indent=2, ensure_ascii=False))
            return

        submission_id = str(uuid.uuid4())
        org = args.organization.strip() or None
        sub = Submission(
            id=submission_id,
            dataset_id=ds.id,
            model_name=args.model_name,
            model_version=(args.model_version or None),
            organization=org,
            predictions=predictions,
            status=SubmissionStatus.PENDING,
            submission_metadata={
                "llm_provider": provider,
                "llm_model": model_id,
            },
            is_internal=False,
        )
        db.add(sub)
        db.commit()

        evaluate_submission(submission_id)
        db.refresh(sub)

        if sub.status != SubmissionStatus.COMPLETED:
            print(sub.error_message or "Evaluation failed", file=sys.stderr)
            sys.exit(1)

        print(f"submission_id={submission_id}")
        print(f"primary_score={sub.primary_score}")
        print(f"primary_metric={ds.primary_metric}")
        print("detailed_scores:")
        for k, v in sorted((sub.detailed_scores or {}).items()):
            print(f"  {k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
