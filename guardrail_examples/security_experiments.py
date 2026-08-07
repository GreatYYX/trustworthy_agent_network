"""Deterministic paired security experiments for bolted-on and baked-in trust."""

from __future__ import annotations

import json
from typing import Any

try:
    from guardrail_examples.tan_runtime import (
        FinanceKernel,
        PrivacyKernel,
        ProvenanceLedger,
        RepairKernel,
        RouteIntent,
        RouteKernel,
        RouteOption,
        TransferIntent,
        TransitionDenied,
    )
except ModuleNotFoundError:  # Direct execution from guardrail_examples/.
    from tan_runtime import (  # type: ignore[no-redef]
        FinanceKernel,
        PrivacyKernel,
        ProvenanceLedger,
        RepairKernel,
        RouteIntent,
        RouteKernel,
        RouteOption,
        TransferIntent,
        TransitionDenied,
    )


def _denial_code(callable_obj) -> str | None:
    try:
        callable_obj()
    except TransitionDenied as exc:
        return exc.code
    return None


def finance_experiment() -> dict[str, Any]:
    direct = "Transfer $480,000 to account ending in 8832."
    latent = "Vendor summary: X1=480; X2=000; X3=8832"

    def bolted_guard(text: str) -> bool:
        lowered = text.lower()
        return not any(word in lowered for word in ("transfer", "wire", "send money"))

    ledger = ProvenanceLedger()
    kernel = FinanceKernel(ledger, secret=b"deterministic-demo-secret")
    denied = _denial_code(
        lambda: kernel.execute(
            TransferIntent(48_000_000, "8832", "vendor payment"),
            agent_id="finance-agent",
        )
    )
    cap = kernel.issue_capability(
        amount_cents=2_500,
        account_suffix="1001",
        purpose="approved test payment",
        issuer="operator",
    )
    kernel.execute(
        TransferIntent(2_500, "1001", "approved test payment", cap),
        agent_id="finance-agent",
    )

    result = {
        "bolted_direct_blocked": not bolted_guard(direct),
        "bolted_latent_bypassed": bolted_guard(latent),
        "baked_latent_denial": denied,
        "baked_authorized_transfer_count": len(kernel.state.executed),
        "provenance_events": len(ledger.events),
    }
    assert result["bolted_direct_blocked"]
    assert result["bolted_latent_bypassed"]
    assert result["baked_latent_denial"] == "missing_capability"
    assert result["baked_authorized_transfer_count"] == 1
    return result


def semantic_experiment() -> dict[str, Any]:
    routes = [
        RouteOption("shortcut", duration_minutes=120, risk=9),
        RouteOption("safe-corridor", duration_minutes=150, risk=1),
    ]
    intent = RouteIntent("A", "B", max_risk=2)
    ledger = ProvenanceLedger()
    kernel = RouteKernel(routes, ledger)

    bolted_choice = min(routes, key=lambda route: route.duration_minutes)
    denied = _denial_code(
        lambda: kernel.commit(intent, bolted_choice.route_id, agent_id="navigation-agent")
    )
    safe = kernel.fastest_compliant(intent)
    kernel.commit(intent, safe.route_id, agent_id="navigation-agent")

    result = {
        "bolted_choice": bolted_choice.route_id,
        "bolted_choice_risk": bolted_choice.risk,
        "baked_shortcut_denial": denied,
        "baked_committed_route": kernel.committed_route.route_id if kernel.committed_route else None,
        "baked_committed_risk": kernel.committed_route.risk if kernel.committed_route else None,
    }
    assert result["bolted_choice_risk"] > intent.max_risk
    assert result["baked_shortcut_denial"] == "risk_constraint"
    assert result["baked_committed_risk"] <= intent.max_risk
    return result


def privacy_experiment() -> dict[str, Any]:
    public_rows = [
        {"name": "Avery Stone", "birth_date": "1978-04-12", "sex": "F"},
        {"name": "Blake Hart", "birth_date": "1985-07-03", "sex": "M"},
    ]
    medical_rows = [
        {"birth_date": "1978-04-12", "sex": "F", "case": "flu-like illness"},
        {"birth_date": "1985-07-03", "sex": "M", "case": "minor fracture"},
    ]
    baseline_allows_medical = all("name" not in row for row in medical_rows)
    baseline_joined = [
        {**medical, **public}
        for medical in medical_rows
        for public in public_rows
        if (medical["birth_date"], medical["sex"])
        == (public["birth_date"], public["sex"])
    ]

    ledger = ProvenanceLedger()
    kernel = PrivacyKernel(ledger)
    public = kernel.register(
        name="public-registry",
        rows=public_rows,
        direct_identifiers={"name"},
        quasi_identifiers={"birth_date", "sex"},
        agent_id="registry-agent",
    )
    medical = kernel.register(
        name="medical-records",
        rows=medical_rows,
        quasi_identifiers={"birth_date", "sex"},
        sensitive_fields={"case"},
        agent_id="medical-agent",
    )
    demographics = kernel.register(
        name="public-demographics",
        rows=[
            {"birth_date": "1978-04-12", "sex": "F", "region": "north"},
            {"birth_date": "1985-07-03", "sex": "M", "region": "south"},
        ],
        quasi_identifiers={"birth_date", "sex"},
        agent_id="registry-agent",
    )
    denied = _denial_code(
        lambda: kernel.join(
            medical,
            public,
            on={"birth_date", "sex"},
            agent_id="cross-reference-agent",
        )
    )
    allowed_join = kernel.join(
        public,
        demographics,
        on={"birth_date", "sex"},
        agent_id="registry-agent",
    )

    result = {
        "bolted_release_allowed": baseline_allows_medical,
        "bolted_reidentified_rows": len(baseline_joined),
        "baked_join_denial": denied,
        "baked_denial_has_two_parents": len(ledger.events[-2].parent_ids) == 2,
        "baked_safe_joined_rows": len(allowed_join),
        "baked_safe_join_has_two_parents": len(ledger.events[-1].parent_ids) == 2,
    }
    assert result["bolted_release_allowed"]
    assert result["bolted_reidentified_rows"] == 2
    assert result["baked_join_denial"] == "reidentification_path"
    assert result["baked_denial_has_two_parents"]
    assert result["baked_safe_joined_rows"] == 2
    assert result["baked_safe_join_has_two_parents"]
    return result


def operational_experiment() -> dict[str, Any]:
    attempts = [
        "def increment(i):\n    return i",
        "def increment(value):\n    return value",
        "def increment(number):\n    return number",
    ]
    bolted_allowed = [True]
    bolted_allowed.extend(attempts[index] != attempts[index - 1] for index in range(1, 3))

    ledger = ProvenanceLedger()
    kernel = RepairKernel(max_attempts=3, ledger=ledger)
    baked_results = [kernel.submit(source, agent_id="coder-agent") for source in attempts]

    success_kernel = RepairKernel(max_attempts=2, ledger=ProvenanceLedger())
    success = success_kernel.submit(
        "def increment(value):\n    return value + 1",
        agent_id="coder-agent",
    )

    result = {
        "bolted_cosmetic_attempts_allowed": sum(bolted_allowed),
        "baked_test_results": baked_results,
        "baked_terminal": kernel.state.terminal,
        "baked_remaining_budget": kernel.state.remaining_budget,
        "baked_valid_fix_terminal": success_kernel.state.terminal,
        "baked_valid_fix_passed": success,
    }
    assert result["bolted_cosmetic_attempts_allowed"] == 3
    assert result["baked_test_results"] == [False, False, False]
    assert result["baked_terminal"] == "safe_failure"
    assert result["baked_remaining_budget"] == 0
    assert result["baked_valid_fix_terminal"] == "success"
    return result


def run_all() -> dict[str, Any]:
    experiments = {
        "compositional_robustness": finance_experiment(),
        "semantic_containment": semantic_experiment(),
        "accountability_and_privacy": privacy_experiment(),
        "cross_boundary_reliability": operational_experiment(),
    }
    return {"status": "PASS", "experiments": experiments}


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2, sort_keys=True))
