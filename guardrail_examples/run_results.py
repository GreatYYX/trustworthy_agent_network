"""Run the full suite and write push-ready artifacts under repository /results."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from llm_client import get_model_name
from security_experiments import run_all as run_security_experiments


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
RESULTS_DIR = REPO_ROOT / "results"


def _revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _working_tree_dirty() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(completed.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Only run deterministic TAN experiments; do not call the configured model.",
    )
    args = parser.parse_args()

    load_dotenv(HERE / ".env")
    generated_at = datetime.now(timezone.utc).isoformat()
    deterministic = run_security_experiments()
    model_name = get_model_name()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    live_result: dict[str, object] = {
        "attempted": not args.skip_live,
        "model": model_name,
    }
    exit_code = 0

    if not args.skip_live:
        completed = subprocess.run(
            [sys.executable, str(HERE / "all_demo.py")],
            cwd=HERE,
            capture_output=True,
            text=True,
            timeout=900,
        )
        safe_model_name = "".join(
            character if character.isalnum() or character in "._-" else "-"
            for character in model_name
        )
        transcript_name = f"model-run-{safe_model_name}.txt"
        transcript = completed.stdout
        if completed.stderr:
            transcript += "\n\n[stderr]\n" + completed.stderr
        (RESULTS_DIR / transcript_name).write_text(transcript)
        live_result.update(
            {
                "exit_code": completed.returncode,
                "transcript": transcript_name,
            }
        )
        exit_code = completed.returncode

    report = {
        "schema_version": 1,
        "generated_at": generated_at,
        "revision": _revision(),
        "working_tree_dirty": _working_tree_dirty(),
        "deterministic_tan": deterministic,
        "live_bolted_on": live_result,
    }
    (RESULTS_DIR / "latest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
