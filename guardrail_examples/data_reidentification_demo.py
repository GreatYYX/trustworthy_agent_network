from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from guardrail import check_content_safe, load_prompts, run_task


def _parse_json_array(text: str) -> list:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\[.*\]", text, re.S)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except Exception:
            return []
    return data if isinstance(data, list) else []


class PublicRegistryAgent:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts = load_prompts(prompts_dir)

    def generate(self) -> List[dict]:
        return _parse_json_array(run_task(self.prompts, "public_registry"))


class MedicalRecordsAgent:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts = load_prompts(prompts_dir)

    def generate(self, include_name: bool = True) -> List[dict]:
        task = "medical_records_full" if include_name else "medical_records_no_name"
        return _parse_json_array(run_task(self.prompts, task))

    def check_for_pii(self, records: List[dict]) -> tuple[bool, str]:
        if not records:
            return False, "Blocked by guardrail"
        allowed, reply = check_content_safe(self.prompts, json.dumps(records))
        print(f"  Safety check: {reply}")
        if not allowed:
            return False, "Blocked by guardrail"
        return True, "Allowed"


class CrossReferenceAgent:
    def __init__(self, prompts_dir: Path) -> None:
        self.prompts = load_prompts(prompts_dir)

    def cross_reference(self, public_registry: List[dict], medical_records: List[dict]) -> List[dict]:
        text = run_task(
            self.prompts,
            "cross_reference",
            public_registry=json.dumps(public_registry),
            medical_records=json.dumps(medical_records),
        )
        return _parse_json_array(text)


def run_case_direct_reid() -> None:
    base = Path(__file__).resolve().parent
    prompts_dir = base / "guardrails" / "data_reidentification"

    public_agent = PublicRegistryAgent(prompts_dir)
    public = public_agent.generate()

    med_agent = MedicalRecordsAgent(prompts_dir)
    medical = med_agent.generate(include_name=True)

    print("━" * 80)
    print("DATA RE-IDENTIFICATION - CASE 1: DIRECT RE-IDENTIFICATION (NAME INCLUDED)")
    print("━" * 80)
    print()

    print("[Public Registry] sample (3)")
    print(json.dumps(public[:3], indent=2))
    print()

    print("[Medical Records] sample (3)")
    print(json.dumps(medical[:3], indent=2))
    print()

    allowed, msg = med_agent.check_for_pii(medical)
    print(f"[Guardrail] {'ALLOW' if allowed else 'BLOCK'} - {msg}")
    print()

    if allowed:
        xref = CrossReferenceAgent(prompts_dir)
        linked = xref.cross_reference(public, medical)
        print("[CrossReference] linked records (3)")
        print(json.dumps(linked[:3], indent=2))
    else:
        print("[Result] ✓ Medical records blocked: Names present = direct re-identification risk")


def run_case_safe_release() -> None:
    base = Path(__file__).resolve().parent
    prompts_dir = base / "guardrails" / "data_reidentification"

    public_agent = PublicRegistryAgent(prompts_dir)
    public = public_agent.generate()

    med_agent = MedicalRecordsAgent(prompts_dir)
    medical = med_agent.generate(include_name=False)

    print()
    print("━" * 80)
    print("DATA RE-IDENTIFICATION - CASE 2: SAFE RELEASE (NAME REMOVED)")
    print("━" * 80)
    print()

    print("[Public Registry] sample (3)")
    print(json.dumps(public[:3], indent=2))
    print()

    print("[Medical Records] sample (3)")
    print(json.dumps(medical[:3], indent=2))
    print()

    allowed, msg = med_agent.check_for_pii(medical)
    print(f"[Guardrail] {'ALLOW' if allowed else 'BLOCK'} - {msg}")
    print()

    if allowed:
        xref = CrossReferenceAgent(prompts_dir)
        linked = xref.cross_reference(public, medical)
        print("[CrossReference] linked records (3)")
        print(json.dumps(linked[:3], indent=2))
        print()
        print("[Result] ✓ Medical records allowed (no names). Cross-reference still possible using birth_date + sex")
    else:
        print("[Result] Cross-referencing blocked due to PII risk.")


if __name__ == "__main__":
    load_dotenv()
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "A2A Guardrail Data Re-identification Demo".center(78) + "║")
    print("║" + "Blocking direct identifiers (names) in medical records".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    run_case_direct_reid()
    print()
    print()
    run_case_safe_release()

    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: Guardrail blocks medical data with names; allows name-removed data".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
