"""Small, deterministic TAN transition kernel used by the security experiments.

The classes in this module are intentionally narrower than a general agent
framework.  They demonstrate the paper's central distinction: policy is part of
the state transition itself, rather than an LLM monitor applied after an
unconstrained action has already been proposed.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


class TransitionDenied(RuntimeError):
    """Raised when an action is not part of the kernel's valid transition set."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProvenanceEvent:
    transition_id: str
    agent_id: str
    action: str
    outcome: str
    parent_ids: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass
class ProvenanceLedger:
    events: list[ProvenanceEvent] = field(default_factory=list)

    def record(
        self,
        *,
        agent_id: str,
        action: str,
        outcome: str,
        parent_ids: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
    ) -> str:
        parents = tuple(parent_ids)
        detail = metadata or {}
        payload = json.dumps(
            {
                "sequence": len(self.events),
                "agent_id": agent_id,
                "action": action,
                "outcome": outcome,
                "parent_ids": parents,
                "metadata": detail,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        transition_id = hashlib.sha256(payload.encode()).hexdigest()[:20]
        self.events.append(
            ProvenanceEvent(
                transition_id=transition_id,
                agent_id=agent_id,
                action=action,
                outcome=outcome,
                parent_ids=parents,
                metadata=detail,
            )
        )
        return transition_id


@dataclass(frozen=True)
class TransferCapability:
    capability_id: str
    amount_cents: int
    account_suffix: str
    purpose: str
    issuer: str
    signature: str


@dataclass(frozen=True)
class TransferIntent:
    amount_cents: int
    account_suffix: str
    purpose: str
    capability: TransferCapability | None = None


@dataclass
class FinanceState:
    executed: list[dict[str, Any]] = field(default_factory=list)
    consumed_capabilities: set[str] = field(default_factory=set)


class FinanceKernel:
    """Only capability-bound transfers are representable as valid transitions."""

    def __init__(
        self,
        ledger: ProvenanceLedger,
        secret: bytes | None = None,
        trusted_issuers: Iterable[str] = ("operator",),
    ) -> None:
        self.ledger = ledger
        self.state = FinanceState()
        self._secret = secret or secrets.token_bytes(32)
        self._trusted_issuers = frozenset(trusted_issuers)

    @staticmethod
    def _capability_payload(
        capability_id: str,
        amount_cents: int,
        account_suffix: str,
        purpose: str,
        issuer: str,
    ) -> bytes:
        return json.dumps(
            [capability_id, amount_cents, account_suffix, purpose, issuer],
            separators=(",", ":"),
        ).encode()

    def issue_capability(
        self,
        *,
        amount_cents: int,
        account_suffix: str,
        purpose: str,
        issuer: str,
    ) -> TransferCapability:
        # `issuer` is assumed to be an authenticated transport identity.  The
        # allowlist makes that protocol-level identity part of the transition.
        if issuer not in self._trusted_issuers:
            raise TransitionDenied("unauthorized_issuer", "issuer cannot mint transfer capabilities")
        if amount_cents <= 0 or not account_suffix.isdigit():
            raise ValueError("capability scope must contain a positive amount and numeric account suffix")
        capability_id = secrets.token_hex(12)
        payload = self._capability_payload(
            capability_id, amount_cents, account_suffix, purpose, issuer
        )
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        cap = TransferCapability(
            capability_id=capability_id,
            amount_cents=amount_cents,
            account_suffix=account_suffix,
            purpose=purpose,
            issuer=issuer,
            signature=signature,
        )
        self.ledger.record(
            agent_id=issuer,
            action="finance.capability.issue",
            outcome="allowed",
            metadata={"capability_id": capability_id, "amount_cents": amount_cents},
        )
        return cap

    def _valid_capability(self, cap: TransferCapability) -> bool:
        payload = self._capability_payload(
            cap.capability_id,
            cap.amount_cents,
            cap.account_suffix,
            cap.purpose,
            cap.issuer,
        )
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, cap.signature)

    def execute(self, intent: TransferIntent, *, agent_id: str) -> str:
        cap = intent.capability
        denial: str | None = None
        if cap is None:
            denial = "missing_capability"
        elif not self._valid_capability(cap):
            denial = "invalid_capability"
        elif cap.capability_id in self.state.consumed_capabilities:
            denial = "replayed_capability"
        elif (
            cap.amount_cents != intent.amount_cents
            or cap.account_suffix != intent.account_suffix
            or cap.purpose != intent.purpose
        ):
            denial = "scope_mismatch"

        if denial:
            self.ledger.record(
                agent_id=agent_id,
                action="finance.transfer",
                outcome="denied",
                metadata={"reason": denial, "amount_cents": intent.amount_cents},
            )
            raise TransitionDenied(denial, "transfer is outside the valid transition set")

        assert cap is not None
        self.state.consumed_capabilities.add(cap.capability_id)
        self.state.executed.append(
            {
                "amount_cents": intent.amount_cents,
                "account_suffix": intent.account_suffix,
                "purpose": intent.purpose,
                "capability_id": cap.capability_id,
            }
        )
        return self.ledger.record(
            agent_id=agent_id,
            action="finance.transfer",
            outcome="allowed",
            metadata={"capability_id": cap.capability_id, "amount_cents": intent.amount_cents},
        )


@dataclass(frozen=True)
class RouteOption:
    route_id: str
    duration_minutes: int
    risk: int
    is_open: bool = True


@dataclass(frozen=True)
class RouteIntent:
    origin: str
    destination: str
    max_risk: int
    require_open: bool = True


class RouteKernel:
    """Binds a receiver's route choice to a typed sender intent."""

    def __init__(self, routes: Iterable[RouteOption], ledger: ProvenanceLedger) -> None:
        self.routes = {route.route_id: route for route in routes}
        self.ledger = ledger
        self.committed_route: RouteOption | None = None

    def commit(self, intent: RouteIntent, route_id: str, *, agent_id: str) -> str:
        route = self.routes.get(route_id)
        reason: str | None = None
        if route is None:
            reason = "unknown_route"
        elif route.risk > intent.max_risk:
            reason = "risk_constraint"
        elif intent.require_open and not route.is_open:
            reason = "closed_route"

        if reason:
            self.ledger.record(
                agent_id=agent_id,
                action="route.commit",
                outcome="denied",
                metadata={"reason": reason, "route_id": route_id},
            )
            raise TransitionDenied(reason, "route violates the typed intent")

        assert route is not None
        self.committed_route = route
        return self.ledger.record(
            agent_id=agent_id,
            action="route.commit",
            outcome="allowed",
            metadata={"route_id": route_id, "risk": route.risk},
        )

    def fastest_compliant(self, intent: RouteIntent) -> RouteOption:
        valid = [
            route
            for route in self.routes.values()
            if route.risk <= intent.max_risk and (route.is_open or not intent.require_open)
        ]
        if not valid:
            raise TransitionDenied("no_compliant_route", "no route satisfies the typed intent")
        return min(valid, key=lambda item: item.duration_minutes)


@dataclass(frozen=True)
class DataArtifact:
    name: str
    rows: tuple[dict[str, Any], ...]
    direct_identifiers: frozenset[str]
    quasi_identifiers: frozenset[str]
    sensitive_fields: frozenset[str]
    provenance_id: str


class PrivacyKernel:
    """Rejects joins that turn sensitive quasi-identifiers into identities."""

    def __init__(self, ledger: ProvenanceLedger) -> None:
        self.ledger = ledger
        self.artifacts: dict[str, DataArtifact] = {}

    def register(
        self,
        *,
        name: str,
        rows: Iterable[dict[str, Any]],
        direct_identifiers: Iterable[str] = (),
        quasi_identifiers: Iterable[str] = (),
        sensitive_fields: Iterable[str] = (),
        agent_id: str,
    ) -> DataArtifact:
        frozen_rows = tuple(dict(row) for row in rows)
        provenance_id = self.ledger.record(
            agent_id=agent_id,
            action="privacy.artifact.register",
            outcome="allowed",
            metadata={"name": name, "rows": len(frozen_rows)},
        )
        artifact = DataArtifact(
            name=name,
            rows=frozen_rows,
            direct_identifiers=frozenset(direct_identifiers),
            quasi_identifiers=frozenset(quasi_identifiers),
            sensitive_fields=frozenset(sensitive_fields),
            provenance_id=provenance_id,
        )
        self.artifacts[name] = artifact
        return artifact

    @staticmethod
    def _creates_reidentification(left: DataArtifact, right: DataArtifact, on: set[str]) -> bool:
        pairs = ((left, right), (right, left))
        return any(
            sensitive.sensitive_fields
            and identity.direct_identifiers
            and on
            and on <= sensitive.quasi_identifiers
            and on <= identity.quasi_identifiers
            for sensitive, identity in pairs
        )

    def join(
        self,
        left: DataArtifact,
        right: DataArtifact,
        *,
        on: Iterable[str],
        agent_id: str,
    ) -> list[dict[str, Any]]:
        keys = set(on)
        if not keys:
            raise ValueError("join keys must be non-empty")
        if self.artifacts.get(left.name) is not left or self.artifacts.get(right.name) is not right:
            self.ledger.record(
                agent_id=agent_id,
                action="privacy.join",
                outcome="denied",
                metadata={"reason": "unregistered_artifact"},
            )
            raise TransitionDenied(
                "unregistered_artifact",
                "join inputs must be policy-labelled artifacts registered in this state",
            )
        if self._creates_reidentification(left, right, keys):
            self.ledger.record(
                agent_id=agent_id,
                action="privacy.join",
                outcome="denied",
                parent_ids=(left.provenance_id, right.provenance_id),
                metadata={"reason": "reidentification_path", "keys": sorted(keys)},
            )
            raise TransitionDenied(
                "reidentification_path",
                "join would connect sensitive attributes to direct identity",
            )

        right_index = {tuple(row.get(key) for key in keys): row for row in right.rows}
        joined: list[dict[str, Any]] = []
        for row in left.rows:
            match = right_index.get(tuple(row.get(key) for key in keys))
            if match is not None:
                joined.append({**row, **match})
        self.ledger.record(
            agent_id=agent_id,
            action="privacy.join",
            outcome="allowed",
            parent_ids=(left.provenance_id, right.provenance_id),
            metadata={"keys": sorted(keys), "rows": len(joined)},
        )
        return joined


@dataclass
class RepairState:
    remaining_budget: int
    attempts: int = 0
    terminal: str | None = None
    last_test_passed: bool | None = None


class RepairKernel:
    """Uses a real bounded test and makes budget consumption part of state."""

    _ALLOWED_AST = (
        ast.Module,
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.Return,
        ast.Assign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
    )

    def __init__(self, *, max_attempts: int, ledger: ProvenanceLedger) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.state = RepairState(remaining_budget=max_attempts)
        self.ledger = ledger

    @classmethod
    def _test_increment(cls, source: str) -> bool:
        if len(source) > 2_000:
            return False
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        nodes = list(ast.walk(tree))
        if len(nodes) > 50 or any(not isinstance(node, cls._ALLOWED_AST) for node in nodes):
            return False
        if any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and abs(node.value) > 1_000_000
            for node in nodes
        ):
            return False
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        if len(functions) != 1 or len(tree.body) != 1:
            return False
        function = functions[0]
        if function.name != "increment" or len(function.args.args) != 1 or function.decorator_list:
            return False
        namespace: dict[str, Any] = {}
        try:
            exec(compile(tree, "<repair-candidate>", "exec"), {"__builtins__": {}}, namespace)
            increment = namespace["increment"]
            return increment(4) == 5 and increment(-1) == 0
        except Exception:
            return False

    def submit(self, source: str, *, agent_id: str) -> bool:
        if self.state.terminal is not None:
            raise TransitionDenied("terminal_state", "repair process has already terminated")

        self.state.attempts += 1
        self.state.remaining_budget -= 1
        passed = self._test_increment(source)
        self.state.last_test_passed = passed
        if passed:
            self.state.terminal = "success"
        elif self.state.remaining_budget == 0:
            self.state.terminal = "safe_failure"

        self.ledger.record(
            agent_id=agent_id,
            action="repair.submit",
            outcome="allowed" if passed else "test_failed",
            metadata={
                "attempt": self.state.attempts,
                "remaining_budget": self.state.remaining_budget,
                "terminal": self.state.terminal,
            },
        )
        return passed


def event_dicts(ledger: ProvenanceLedger) -> list[dict[str, Any]]:
    """Return JSON-friendly provenance for experiment reporting."""

    return [asdict(event) for event in ledger.events]
