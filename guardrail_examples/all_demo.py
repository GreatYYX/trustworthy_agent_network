from __future__ import annotations

import json

from dotenv import load_dotenv

from adversarial_composition_demo import run_case_direct_attack, run_case_hidden_injection
from data_reidentification_demo import run_case_direct_reid, run_case_safe_release
from operational_failure_demo import run_case_repeating_failure, run_case_variable_rename
from security_experiments import run_all as run_paired_security_experiments
from semantic_misalignment_demo import run_case_one, run_case_two


def print_banner(title: str, subtitle: str) -> None:
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + title.center(78) + "║")
    print("║" + subtitle.center(78) + "║")
    print("╚" + "═" * 78 + "╝")
    print()


def run_adversarial_composition_demo() -> None:
    print_banner(
        "A2A Guardrail Adversarial Composition Attack",
        "Prompt Injection via Web Scraper",
    )
    run_case_direct_attack()
    print()
    print()
    run_case_hidden_injection()
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: Hidden prompt injection can bypass guardrails".center(78) + "║")
    print("╚" + "═" * 78 + "╝")


def run_semantic_misalignment_demo() -> None:
    print_banner(
        "Semantic Misalignment in Route Planning",
        "Synthetic Typed-Intent Route Selection",
    )
    run_case_one()
    print()
    print()
    run_case_two()
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: Risk definitions are vague; both routes pass the guardrail".center(78) + "║")
    print("╚" + "═" * 78 + "╝")


def run_data_reidentification_demo() -> None:
    print_banner(
        "A2A Guardrail Data Re-identification Demo",
        "Blocking direct identifiers (names) in medical records",
    )
    run_case_direct_reid()
    print()
    print()
    run_case_safe_release()
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: Guardrail blocks medical data with names; allows name-removed data".center(78) + "║")
    print("╚" + "═" * 78 + "╝")


def run_operational_failure_demo() -> None:
    print_banner(
        "A2A Guardrail Operational Failure Demo",
        "Coder/tester loop with change-only guardrail",
    )
    run_case_repeating_failure()
    print()
    print()
    run_case_variable_rename()
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: unchanged code is blocked; variable-renamed code is allowed".center(78) + "║")
    print("╚" + "═" * 78 + "╝")


def run_baked_in_security_demo() -> None:
    print_banner(
        "Paired Bolted-On vs. Baked-In Security Experiments",
        "Deterministic TAN transition invariants",
    )
    print(json.dumps(run_paired_security_experiments(), indent=2, sort_keys=True))


if __name__ == "__main__":
    load_dotenv()

    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "A2A Guardrail Combined Demo Suite".center(78) + "║")
    print("║" + "Running all demos in the same order as the single-file examples".center(78) + "║")
    print("╚" + "═" * 78 + "╝")

    run_adversarial_composition_demo()
    print()
    print()
    run_semantic_misalignment_demo()
    print()
    print()
    run_data_reidentification_demo()
    print()
    print()
    run_operational_failure_demo()
    print()
    print()
    run_baked_in_security_demo()

    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "Summary: all demo cases executed in sequence".center(78) + "║")
    print("╚" + "═" * 78 + "╝")
