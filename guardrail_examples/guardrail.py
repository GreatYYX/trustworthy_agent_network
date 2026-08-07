"""Load prompt YAML and run a simple content-safe / unsafe guardrail check."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from llm_client import complete


def load_prompts(config_dir: Path) -> dict[str, dict[str, Any]]:
    path = config_dir / "prompts.yml"
    data = yaml.safe_load(path.read_text()) or {}
    tasks: dict[str, dict[str, Any]] = {}
    for item in data.get("prompts", []):
        tasks[item["task"]] = item
    return tasks


def render_prompt(template: str, **context: str) -> str:
    text = template
    for key, value in context.items():
        text = text.replace("{{ " + key + " }}", value)
        text = text.replace("{{" + key + "}}", value)
    return text


def parse_content_safe(reply: str) -> bool:
    """Return True when the model says the content is safe (allow)."""
    cleaned = re.sub(r"\W+", " ", (reply or "").lower()).strip()
    words = cleaned.split()[:3]
    if "unsafe" in words:
        return False
    if "safe" in words:
        return True
    # Fail closed on unexpected replies.
    return False


def check_content_safe(prompts: dict[str, dict[str, Any]], user_input: str) -> tuple[bool, str]:
    """Ask the configured self_check_input prompt whether content is safe.

    Returns (allowed, model_reply).
    """
    task = prompts["self_check_input"]
    prompt = render_prompt(task["content"], user_input=user_input)
    max_tokens = int(task.get("max_tokens") or 256)
    reply = complete(prompt, max_tokens=max_tokens)
    return parse_content_safe(reply), reply


def run_task(prompts: dict[str, dict[str, Any]], task_name: str, **context: str) -> str:
    task = prompts[task_name]
    prompt = render_prompt(task["content"], **context)
    max_tokens = int(task.get("max_tokens") or 512)
    return complete(prompt, max_tokens=max_tokens)
