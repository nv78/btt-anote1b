"""
Hugging Face sentiment pipeline helpers for SST-2-style text_classification datasets.

Inference only; scoring stays in evaluation_service + evaluators.
"""
from __future__ import annotations

import re
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# Install hint (avoid confusing ImportError from the CLI script)
_DEPS_HINT = "pip install transformers torch"


def check_transformers_torch() -> None:
    """Exit with a clear message if optional ML deps are missing."""
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        print(
            "Missing optional dependencies for Hugging Face model inference.\n"
            f"  {_DEPS_HINT}\n"
            "For CPU-only PyTorch, see: https://pytorch.org/get-started/locally/",
            file=sys.stderr,
        )
        raise SystemExit(1)


def normalize_hf_sentiment_label(raw: Union[str, Dict[str, Any]]) -> str:
    """
    Map HF sentiment-analysis labels to evaluator labels (lowercase positive/negative).

    Accepts raw string or pipeline output dict with 'label' key.
    """
    if isinstance(raw, dict):
        raw = raw.get("label", "")
    if not isinstance(raw, str):
        raw = str(raw)
    u = raw.strip().upper()
    if u in ("POSITIVE", "LABEL_1", "POS", "1"):
        return "positive"
    if u in ("NEGATIVE", "LABEL_0", "NEG", "0"):
        return "negative"
    if u in ("NEUTRAL", "NEU", "NEUT"):
        return "neutral"
    raise ValueError(f"Unexpected sentiment label from model: {raw!r}")


def submission_model_name_from_id(model_id: str) -> str:
    """Short leaderboard-safe name derived from HF model id."""
    tail = model_id.split("/")[-1].lower()
    if "distilbert" in tail and "sst" in tail:
        return "hf_distilbert_sst2"
    slug = re.sub(r"[^a-z0-9]+", "_", tail).strip("_")
    return ("hf_" + slug)[:80]


def ground_truth_to_id_sentences(
    ground_truth: List[Dict[str, Any]],
    *,
    require_sentence_key: bool = True,
) -> List[Tuple[str, str]]:
    """
    Return parallel (example_id, sentence) rows.

    Raises:
        ValueError: empty GT, missing id, or missing sentence when required.
    """
    if not ground_truth:
        raise ValueError("No ground-truth examples found for this dataset.")
    rows: List[Tuple[str, str]] = []
    for i, item in enumerate(ground_truth):
        if not isinstance(item, dict):
            raise ValueError(f"ground_truth[{i}] must be a dict, got {type(item)}")
        ex_id = item.get("id")
        if ex_id is None:
            raise ValueError(f"ground_truth[{i}] missing required 'id'")
        if require_sentence_key and "sentence" not in item:
            raise ValueError(
                f"ground_truth[{i}] (id={ex_id!r}) missing required 'sentence' field; "
                "SST-2 imports must store the input under 'sentence'."
            )
        sentence = item.get("sentence")
        if sentence is None or (isinstance(sentence, str) and not sentence.strip()):
            sentence = item.get("question")
        if sentence is None or (isinstance(sentence, str) and not str(sentence).strip()):
            raise ValueError(f"No input text (sentence/question) for id={ex_id!r}")
        rows.append((str(ex_id), str(sentence)))
    return rows


def run_sentiment_pipeline_batched(
    model_id: str,
    sentences: Sequence[str],
    *,
    batch_size: int = 16,
    pipeline_factory: Optional[Callable[..., Any]] = None,
) -> List[str]:
    """
    Run HF sentiment-analysis pipeline; return normalized labels in order.

    pipeline_factory: for tests, return a callable model(pipeline_name, **kw).
    """
    if pipeline_factory is None:
        check_transformers_torch()
        from transformers import pipeline as hf_pipeline

        pipeline_factory = hf_pipeline

    pipe = pipeline_factory("sentiment-analysis", model=model_id, truncation=True)
    out: List[str] = []
    bs = max(1, int(batch_size))
    for i in range(0, len(sentences), bs):
        chunk = list(sentences[i : i + bs])
        raw_results = pipe(chunk, batch_size=min(bs, len(chunk)))
        if isinstance(raw_results, dict):
            raw_results = [raw_results]
        if not isinstance(raw_results, list):
            raw_results = list(raw_results)
        if len(raw_results) != len(chunk):
            raise RuntimeError(
                f"Pipeline returned {len(raw_results)} results for {len(chunk)} inputs"
            )
        for r in raw_results:
            out.append(normalize_hf_sentiment_label(r))
    if len(out) != len(sentences):
        raise RuntimeError("Prediction count mismatch after pipeline run")
    return out


def build_predictions_json(
    example_ids: Sequence[str], normalized_labels: Sequence[str]
) -> List[Dict[str, str]]:
    if len(example_ids) != len(normalized_labels):
        raise ValueError(
            f"id count ({len(example_ids)}) != label count ({len(normalized_labels)})"
        )
    return [{"id": eid, "prediction": lab} for eid, lab in zip(example_ids, normalized_labels)]


def _canonicalize_ag_news_textattack(label_lower: str) -> str:
    """Map ``textattack/bert-base-uncased-ag-news`` LABEL_* ids to seed label strings."""
    return {
        "label_0": "world",
        "label_1": "sports",
        "label_2": "business",
        "label_3": "sci/tech",
    }.get(label_lower, label_lower)


def run_text_classification_pipeline_batched(
    model_id: str,
    sentences: Sequence[str],
    *,
    batch_size: int = 8,
    pipeline_factory: Optional[Callable[..., Any]] = None,
) -> List[str]:
    """
    Generic sequence classification (HF ``text-classification`` pipeline).
    Returns one lowercase label string per input (top-1).
    """
    if pipeline_factory is None:
        check_transformers_torch()
        from transformers import pipeline as hf_pipeline

        pipeline_factory = hf_pipeline

    pipe = pipeline_factory("text-classification", model=model_id, truncation=True)
    out: List[str] = []
    bs = max(1, int(batch_size))
    for i in range(0, len(sentences), bs):
        chunk = list(sentences[i : i + bs])
        raw_results = pipe(chunk, batch_size=min(bs, len(chunk)))
        if isinstance(raw_results, dict):
            raw_results = [raw_results]
        if not isinstance(raw_results, list):
            raw_results = list(raw_results)
        if len(raw_results) != len(chunk):
            raise RuntimeError(
                f"Pipeline returned {len(raw_results)} results for {len(chunk)} inputs"
            )
        for r in raw_results:
            if isinstance(r, dict):
                lab = r.get("label", "")
            else:
                lab = r
            s = str(lab).strip().lower()
            if s.startswith("label_") and hasattr(pipe, "model") and hasattr(pipe.model, "config"):
                id2 = getattr(pipe.model.config, "id2label", None) or {}
                try:
                    idx = int(s.replace("label_", ""))
                    if idx in id2:
                        s = str(id2[idx]).strip().lower()
                except ValueError:
                    pass
            if "bert-base-uncased-ag-news" in model_id:
                s = _canonicalize_ag_news_textattack(s)
            out.append(s)
    if len(out) != len(sentences):
        raise RuntimeError("Prediction count mismatch after text-classification run")
    return out


def load_extractive_qa_model(model_id: str) -> Tuple[Any, Any, Any]:
    """
    Load tokenizer + ``AutoModelForQuestionAnswering`` for extractive QA.
    Transformers 5.x removed the ``question-answering`` pipeline task; callers
    should use :func:`extractive_qa_answer` in a loop.
    """
    check_transformers_torch()
    import torch
    from transformers import AutoModelForQuestionAnswering, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForQuestionAnswering.from_pretrained(model_id)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return tok, model, device


def extractive_qa_answer(
    tokenizer: Any,
    model: Any,
    device: Any,
    question: str,
    context: str,
    *,
    max_length: int = 384,
) -> str:
    """Single extractive QA span (truncated context)."""
    import torch

    inputs = tokenizer(
        question,
        context,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    start = int(torch.argmax(outputs.start_logits, dim=-1).item())
    end = int(torch.argmax(outputs.end_logits, dim=-1).item())
    if end < start:
        end = start
    ids = inputs["input_ids"][0]
    ans_ids = ids[start : end + 1]
    return tokenizer.decode(ans_ids, skip_special_tokens=True)
