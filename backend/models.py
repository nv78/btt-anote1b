"""
Model wrappers used for benchmarking over CSV datasets.

All API keys are read from environment variables. Optionally, if python-dotenv
is installed and a .env file exists, it will be loaded automatically.

Env vars:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GOOGLE_API_KEY
- XAI_API_KEY
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List

# Optional .env loading
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()  # load .env if present
except Exception:
    pass


def _getenv(name: str) -> str | None:
    v = os.getenv(name)
    return v if v and v.strip() else None


def _trust_remote_code_for(model_name: str) -> bool:
    """Remote code execution is opt-in by exact model id."""
    allowlist = {
        item.strip()
        for item in os.getenv("TRUSTED_REMOTE_CODE_MODELS", "").split(",")
        if item.strip()
    }
    return model_name in allowlist


def zero_shot_gpt4o(prompt: str) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return "UNAVAILABLE: openai package not installed"
    key = _getenv("OPENAI_API_KEY")
    if not key:
        return "UNAVAILABLE: OPENAI_API_KEY not set"
    client = OpenAI(api_key=key)
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful, concise assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return r.choices[0].message.content or ""


def zero_shot_gpt4o_mini(prompt: str) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return "UNAVAILABLE: openai package not installed"
    key = _getenv("OPENAI_API_KEY")
    if not key:
        return "UNAVAILABLE: OPENAI_API_KEY not set"
    client = OpenAI(api_key=key)
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful, concise assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return r.choices[0].message.content or ""


def zero_shot_claude(prompt: str) -> str:
    try:
        import anthropic  # type: ignore
    except Exception:
        return "UNAVAILABLE: anthropic package not installed"
    key = _getenv("ANTHROPIC_API_KEY")
    if not key:
        return "UNAVAILABLE: ANTHROPIC_API_KEY not set"
    client = anthropic.Anthropic(api_key=key)
    r = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return r.content[0].text  # type: ignore[attr-defined]
    except Exception:
        return str(r)


def zero_shot_gemini(prompt: str) -> str:
    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        return "UNAVAILABLE: google-generativeai package not installed"
    key = _getenv("GOOGLE_API_KEY")
    if not key:
        return "UNAVAILABLE: GOOGLE_API_KEY not set"
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    r = model.generate_content(prompt)
    return getattr(r, 'text', None) or (r.candidates[0].content.parts[0].text if getattr(r, 'candidates', None) else "")


def zero_shot_llama3(prompt: str) -> str:
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline  # type: ignore
        import torch  # type: ignore
    except Exception:
        return "UNAVAILABLE: transformers/torch not installed"
    model_name = "meta-llama/Meta-Llama-3-8B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=_trust_remote_code_for(model_name),
    )
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.generation_config.pad_token_id = tokenizer.pad_token_id  # type: ignore[attr-defined]
    out = pipe(prompt, do_sample=True, max_new_tokens=200, temperature=0.3, top_k=50, top_p=0.95, num_return_sequences=1)
    return out[0].get("generated_text", "")


def zero_shot_mistral(prompt: str) -> str:
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline  # type: ignore
        import torch  # type: ignore
    except Exception:
        return "UNAVAILABLE: transformers/torch not installed"
    model_name = "mistralai/Mistral-7B-Instruct-v0.2"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=_trust_remote_code_for(model_name),
    )
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    out = pipe(prompt, do_sample=True, max_new_tokens=200, temperature=0.3, top_k=50, top_p=0.95, num_return_sequences=1)
    return out[0].get("generated_text", "")


def zero_shot_grok(prompt: str) -> str:
    try:
        import xai_sdk  # type: ignore
        import asyncio
    except Exception:
        return "UNAVAILABLE: xai_sdk not installed"
    key = _getenv("XAI_API_KEY")
    if key:
        os.environ.setdefault("XAI_API_KEY", key)

    async def _inner() -> str:
        client = xai_sdk.Client()
        convo = client.chat.create_conversation()
        resp = await convo.add_response_no_stream(prompt)
        return resp.message

    try:
        return asyncio.run(_inner())
    except RuntimeError:
        # If already in event loop, fallback
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_inner())


def list_models() -> List[Dict[str, str]]:
    """Default model set for CSV benchmarks.

    Returns a list of descriptors consumable by POST /public/run_csv_benchmarks
    when using provider 'py' (function-based models).
    """
    return [
        {"name": "gpt-4o", "provider": "py", "fn": "zero_shot_gpt4o"},
        {"name": "gpt-4o-mini", "provider": "py", "fn": "zero_shot_gpt4o_mini"},
        {"name": "claude-3-5-sonnet", "provider": "py", "fn": "zero_shot_claude"},
        {"name": "gemini-1.5-flash", "provider": "py", "fn": "zero_shot_gemini"},
        # Local/HF models (optional heavy)
        # {"name": "llama3-8b", "provider": "py", "fn": "zero_shot_llama3"},
        # {"name": "mistral-7b", "provider": "py", "fn": "zero_shot_mistral"},
        # XAI Grok (if available)
        # {"name": "grok", "provider": "py", "fn": "zero_shot_grok"},
    ]


def get_model_functions() -> Dict[str, Callable[[str], str]]:
    return {name: globals()[name] for name in globals() if name.startswith("zero_shot_") and callable(globals()[name])}
