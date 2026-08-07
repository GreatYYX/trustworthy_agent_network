from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from guardrail import check_content_safe, load_prompts, run_task


class LoopGuardrail:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts = load_prompts(prompts_dir)

    def evaluate(self, history: List[dict]) -> tuple[bool, str]:
        if len(history) < 2:
            return True, "Allowed: need at least two iterations to compare changes."

        previous_script = history[-2]["script"]
        latest_script = history[-1]["script"]
        payload = json.dumps({"previous_script": previous_script, "latest_script": latest_script})
        allowed, reply = check_content_safe(self.prompts, payload)
        print(f"  Safety check: {reply}")
        if not allowed:
            return False, "Blocked by guardrail"
        return True, "Allowed"


class CoderAgent:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts = load_prompts(prompts_dir)

    def write_same_bug(self, round_number: int) -> str:
        return self._clean(run_task(self.prompts, "coder_same_bug", round_number=str(round_number)))

    def write_renamed_bug(self, round_number: int, previous_var: str | None = None) -> str:
        ctx = {"round_number": str(round_number), "previous_var": previous_var or ""}
        return self._clean(run_task(self.prompts, "coder_rename_variable", **ctx))

    def _clean(self, text: str) -> str:
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("python"):
                text = text[6:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = re.sub(r"^Option\s*\d+:\s*\n", "", text)
        return text.strip()


class TesterAgent:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts = load_prompts(prompts_dir)

    def run_script(self, script: str) -> str:
        text = run_task(self.prompts, "tester_report", script=script)
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("text"):
                text = text[4:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        return text.strip()


def run_case_repeating_failure() -> None:
    base = Path(__file__).resolve().parent
    prompts_dir = base / "guardrails" / "operational_failure"

    guardrail = LoopGuardrail(prompts_dir)
    coder = CoderAgent(prompts_dir)
    tester = TesterAgent(prompts_dir)

    print("━" * 80)
    print("OPERATIONAL FAILURE - CASE 1: NO CODE CHANGE BLOCKED")
    print("━" * 80)
    print()

    history: List[dict] = []

    for cycle in range(1, 10):
        script = coder.write_same_bug(cycle)

        print(f"[Coder Agent] Cycle {cycle}")
        print(script)
        print()

        history.append({"cycle": str(cycle), "script": script})
        allowed, message = guardrail.evaluate(history)
        print(f"[Guardrail] {'ALLOW' if allowed else 'BLOCK'} - {message}")
        print()

        if not allowed:
            break

        tester_result = tester.run_script(script)
        print(f"[Tester Agent] Cycle {cycle}")
        print(tester_result)
        print()

    if len(history) < 3:
        print("[Result] Blocked by purpose because the code never changes.")


def run_case_variable_rename() -> None:
    base = Path(__file__).resolve().parent
    prompts_dir = base / "guardrails" / "operational_failure"

    guardrail = LoopGuardrail(prompts_dir)
    coder = CoderAgent(prompts_dir)
    tester = TesterAgent(prompts_dir)

    print()
    print("━" * 80)
    print("OPERATIONAL FAILURE - CASE 2: VARIABLE RENAME ALLOWED")
    print("━" * 80)
    print()

    history: List[dict] = []

    def _extract_param_name(script: str) -> str | None:
        m = re.search(r"def\s+increment\(\s*([a-zA-Z_]\w*)\s*\)", script)
        return m.group(1) if m else None

    for cycle in range(1, 8):
        previous_var = _extract_param_name(history[-1]["script"]) if history else None
        script = coder.write_renamed_bug(cycle, previous_var)

        print(f"[Coder Agent] Cycle {cycle}")
        print(script)
        print()

        history.append({"cycle": str(cycle), "script": script})
        allowed, message = guardrail.evaluate(history)
        print(f"[Guardrail] {'ALLOW' if allowed else 'BLOCK'} - {message}")
        print()

        if not allowed:
            break

        tester_result = tester.run_script(script)
        print(f"[Tester Agent] Cycle {cycle}")
        print(tester_result)
        print()
    else:
        print("[Result] This was intentionally stopped after 7 rounds; without guardrail detection, it could continue forever.")


if __name__ == "__main__":
    load_dotenv()
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "A2A Guardrail Operational Failure Demo".center(78) + "║")
    print("║" + "Coder/tester loop with change-only guardrail".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    run_case_repeating_failure()
    print()
    print()
    run_case_variable_rename()

    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: unchanged code is blocked; variable-renamed code is allowed".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
