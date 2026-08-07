from __future__ import annotations

import unittest
from dataclasses import replace

from guardrail_examples.security_experiments import run_all
from guardrail_examples.tan_runtime import (
    DataArtifact,
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


class FinanceKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = ProvenanceLedger()
        self.kernel = FinanceKernel(self.ledger, secret=b"test-secret")
        self.capability = self.kernel.issue_capability(
            amount_cents=500,
            account_suffix="1234",
            purpose="test",
            issuer="operator",
        )

    def test_forged_and_scope_changed_capabilities_are_denied(self) -> None:
        forged = replace(self.capability, amount_cents=99_999)
        with self.assertRaisesRegex(TransitionDenied, "valid transition") as caught:
            self.kernel.execute(
                TransferIntent(99_999, "1234", "test", forged), agent_id="finance"
            )
        self.assertEqual(caught.exception.code, "invalid_capability")

    def test_capability_is_single_use(self) -> None:
        intent = TransferIntent(500, "1234", "test", self.capability)
        self.kernel.execute(intent, agent_id="finance")
        with self.assertRaises(TransitionDenied) as caught:
            self.kernel.execute(intent, agent_id="finance")
        self.assertEqual(caught.exception.code, "replayed_capability")

    def test_untrusted_identity_cannot_issue_capability(self) -> None:
        with self.assertRaises(TransitionDenied) as caught:
            self.kernel.issue_capability(
                amount_cents=500,
                account_suffix="1234",
                purpose="test",
                issuer="scraper-agent",
            )
        self.assertEqual(caught.exception.code, "unauthorized_issuer")


class RouteKernelTests(unittest.TestCase):
    def test_risky_route_is_not_a_valid_transition(self) -> None:
        kernel = RouteKernel(
            [RouteOption("fast", 10, 9), RouteOption("safe", 20, 1)],
            ProvenanceLedger(),
        )
        intent = RouteIntent("A", "B", max_risk=2)
        with self.assertRaises(TransitionDenied):
            kernel.commit(intent, "fast", agent_id="nav")
        kernel.commit(intent, "safe", agent_id="nav")
        self.assertEqual(kernel.committed_route.route_id, "safe")


class PrivacyKernelTests(unittest.TestCase):
    def test_sensitive_identity_join_is_denied_with_provenance(self) -> None:
        ledger = ProvenanceLedger()
        kernel = PrivacyKernel(ledger)
        public = kernel.register(
            name="public",
            rows=[{"name": "A", "dob": "1"}],
            direct_identifiers={"name"},
            quasi_identifiers={"dob"},
            agent_id="public-agent",
        )
        sensitive = kernel.register(
            name="sensitive",
            rows=[{"dob": "1", "diagnosis": "x"}],
            quasi_identifiers={"dob"},
            sensitive_fields={"diagnosis"},
            agent_id="medical-agent",
        )
        with self.assertRaises(TransitionDenied):
            kernel.join(sensitive, public, on={"dob"}, agent_id="join-agent")
        self.assertEqual(ledger.events[-1].outcome, "denied")
        self.assertEqual(len(ledger.events[-1].parent_ids), 2)

    def test_unregistered_policy_labels_cannot_bypass_join_control(self) -> None:
        kernel = PrivacyKernel(ProvenanceLedger())
        forged = DataArtifact(
            name="forged",
            rows=({"name": "A", "dob": "1"},),
            direct_identifiers=frozenset(),
            quasi_identifiers=frozenset(),
            sensitive_fields=frozenset(),
            provenance_id="fake",
        )
        with self.assertRaises(TransitionDenied) as caught:
            kernel.join(forged, forged, on={"dob"}, agent_id="join-agent")
        self.assertEqual(caught.exception.code, "unregistered_artifact")


class RepairKernelTests(unittest.TestCase):
    def test_budget_forces_safe_termination(self) -> None:
        kernel = RepairKernel(max_attempts=2, ledger=ProvenanceLedger())
        self.assertFalse(kernel.submit("def increment(i):\n    return i", agent_id="coder"))
        self.assertFalse(kernel.submit("def increment(x):\n    return x", agent_id="coder"))
        self.assertEqual(kernel.state.terminal, "safe_failure")
        with self.assertRaises(TransitionDenied):
            kernel.submit("def increment(x):\n    return x + 1", agent_id="coder")

    def test_real_fix_reaches_success(self) -> None:
        kernel = RepairKernel(max_attempts=2, ledger=ProvenanceLedger())
        self.assertTrue(
            kernel.submit("def increment(x):\n    return x + 1", agent_id="coder")
        )
        self.assertEqual(kernel.state.terminal, "success")

    def test_candidate_language_is_structurally_restricted(self) -> None:
        kernel = RepairKernel(max_attempts=1, ledger=ProvenanceLedger())
        source = "def increment(x):\n    return __import__('os').system('echo unsafe')"
        self.assertFalse(kernel.submit(source, agent_id="coder"))
        self.assertEqual(kernel.state.terminal, "safe_failure")

    def test_candidate_size_is_bounded(self) -> None:
        kernel = RepairKernel(max_attempts=1, ledger=ProvenanceLedger())
        source = "def increment(x):\n    return x + 1" + (" " * 2_001)
        self.assertFalse(kernel.submit(source, agent_id="coder"))


class PairedExperimentTests(unittest.TestCase):
    def test_all_paired_security_experiments_pass(self) -> None:
        report = run_all()
        self.assertEqual(report["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
