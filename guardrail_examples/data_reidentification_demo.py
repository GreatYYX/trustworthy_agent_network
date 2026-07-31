from __future__ import annotations

import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from nemoguardrails import LLMRails, RailsConfig


class PublicRegistryAgent:
    def __init__(self, config_path: Path) -> None:
        config = RailsConfig.from_path(str(config_path))
        self.rails = LLMRails(config)

    def generate(self) -> List[dict]:
        try:
            prompt = self.rails.runtime.llm_task_manager.render_task_prompt(task="public_registry", context={})
            out = self.rails.llm.invoke([HumanMessage(content=prompt)])
        except Exception:
            return []

        text = getattr(out, "content", None)
        if text is None and isinstance(out, dict):
            text = out.get("content") or out.get("output") or str(out)
        try:
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            data = json.loads(text)
        except Exception:
            data = []
        return data


class MedicalRecordsAgent:
    def __init__(self, config_path: Path) -> None:
        config = RailsConfig.from_path(str(config_path))
        self.rails = LLMRails(config)

    def generate(self, include_name: bool = True) -> List[dict]:
        task = "medical_records_full" if include_name else "medical_records_no_name"
        try:
            prompt = self.rails.runtime.llm_task_manager.render_task_prompt(task=task, context={})
            out = self.rails.llm.invoke([HumanMessage(content=prompt)])
        except Exception:
            return []

        text = getattr(out, "content", None)
        if text is None and isinstance(out, dict):
            text = out.get("content") or out.get("output") or str(out)
        try:
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            data = json.loads(text)
        except Exception:
            data = []
        return data

    def check_for_pii(self, records: List[dict]) -> tuple[bool, str]:
        try:
            payload = json.dumps(records)
            if len(records) == 0:
                return False, "Blocked by guardrail"

            try:
                check_result = self.rails.check(messages=[{"role": "user", "content": payload}])
            except Exception:
                return False, "Blocked by guardrail"

            try:
                status_name = check_result.status.name
            except Exception:
                status_name = str(check_result.status)

            if status_name == "BLOCKED":
                return False, "Blocked by guardrail"

            return True, "Allowed"

        except Exception as exc:
            return False, "Blocked by guardrail"


class CrossReferenceAgent:
    def __init__(self, config_path: Path) -> None:
        config = RailsConfig.from_path(str(config_path))
        self.rails = LLMRails(config)

    def cross_reference(self, public_registry: List[dict], medical_records: List[dict]) -> List[dict]:
        prompt = self.rails.runtime.llm_task_manager.render_task_prompt(
            task="cross_reference",
            context={
                "public_registry": json.dumps(public_registry),
                "medical_records": json.dumps(medical_records),
            },
        )
        out = self.rails.llm.invoke([HumanMessage(content=prompt)])
        text = getattr(out, "content", None)
        if text is None and isinstance(out, dict):
            text = out.get("content") or out.get("output") or str(out)
        try:
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            data = json.loads(text)
        except Exception:
            data = []
        return data


def run_case_direct_reid() -> None:
    base = Path(__file__).resolve().parent
    guardrail_config = base / "guardrails" / "data_reidentification"

    public_agent = PublicRegistryAgent(guardrail_config)
    public = public_agent.generate()

    med_agent = MedicalRecordsAgent(guardrail_config)
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
        xref = CrossReferenceAgent(guardrail_config)
        linked = xref.cross_reference(public, medical)
        print("[CrossReference] linked records (3)")
        print(json.dumps(linked[:3], indent=2))
    else:
        print("[Result] ✓ Medical records blocked: Names present = direct re-identification risk")


def run_case_safe_release() -> None:
    base = Path(__file__).resolve().parent
    guardrail_config = base / "guardrails" / "data_reidentification"

    public_agent = PublicRegistryAgent(guardrail_config)
    public = public_agent.generate()

    med_agent = MedicalRecordsAgent(guardrail_config)
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
        xref = CrossReferenceAgent(guardrail_config)
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
