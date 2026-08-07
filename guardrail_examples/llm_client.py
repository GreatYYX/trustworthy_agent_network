"""Shared LLM client for OpenAI and Anthropic models.

Configure via ``guardrail_examples/.env``:

- ``OPENAI_API_KEY`` — GPT / OpenAI-compatible endpoints
- ``ANTHROPIC_API_KEY`` — Claude via the Anthropic API
- ``API_URL`` — optional OpenAI-compatible base URL
- ``MODEL`` — model id (default ``gpt-4o-mini``)
"""

from __future__ import annotations

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

DEFAULT_MODEL = "gpt-4o-mini"


def model_rejects_temperature(model_name: str) -> bool:
    name = (model_name or "").lower()
    if name.startswith("o1") or name.startswith("o3"):
        return True
    if name.startswith("gpt-5") and "chat" not in name:
        return True
    if "claude" in name:
        return True
    return False


def is_claude_model(model_name: str) -> bool:
    return "claude" in (model_name or "").lower()


def get_model_name() -> str:
    return os.environ.get("MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_llm():
    model = get_model_name()
    api_url = (os.environ.get("API_URL") or "").strip() or None
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    # Native Anthropic when using Claude without an OpenAI-compatible API_URL.
    use_native_anthropic = is_claude_model(model) and bool(anthropic_key) and not api_url

    if use_native_anthropic:
        kwargs: dict[str, Any] = {
            "model": model,
            "model_provider": "anthropic",
            "api_key": anthropic_key,
        }
    else:
        api_key = openai_key or (anthropic_key if is_claude_model(model) else None)
        if not api_key:
            needed = "OPENAI_API_KEY" if not is_claude_model(model) else "ANTHROPIC_API_KEY or OPENAI_API_KEY"
            raise RuntimeError(f"{needed} is not set. Add it to guardrail_examples/.env")
        kwargs = {
            "model": model,
            "model_provider": "openai",
            "api_key": api_key,
        }
        if api_url:
            kwargs["base_url"] = api_url

    if model_rejects_temperature(model):
        kwargs["temperature"] = None
    return init_chat_model(**kwargs)


def complete(prompt: str, *, max_tokens: int = 512) -> str:
    llm = get_llm()
    out = llm.invoke([HumanMessage(content=prompt)], max_tokens=max_tokens)
    text = getattr(out, "content", None)
    if text is None and isinstance(out, dict):
        text = out.get("content") or out.get("output") or str(out)
    return str(text).strip()
