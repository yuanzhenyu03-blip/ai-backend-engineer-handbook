"""Day70 — Phase 6 capstone: a standalone, deterministic decision model (standard library only).

This is the executable local decision core the class built to encode the Phase 6 responsibility and
failure boundaries in one place. It is intentionally self-contained (no cross-project imports) so it runs
from ``projects/n8n-workflows/`` on any Python 3 with ``pytest``. It models SIX decision areas:

  1. acceptance recovery after a lost response (OUTCOME_UNKNOWN; reissue only on proven NEVER_ACCEPTED
     with a still-valid idempotency retention window; NOT_FOUND is ambiguous, never proof);
  2. Callback event dedupe / conflict (same event_id + same fingerprint = no-op; same event_id +
     different fingerprint = conflict; a genuinely new event proceeds);
  3. exact Approval binding (an Approval authorizes only its exact tenant/actor/action/artifact-version/
     policy within a bounded lifetime; a v7 approval can never authorize v8);
  4. Publication recovery classification (SUCCEEDED/PROCESSING/FAILED_TERMINAL/PENDING_RECONCILIATION/
     NOT_FOUND);
  5. credential-failure classification (a 401 is not automatically "rotate": rotate only when
     expiry/revocation/compromise/leak/invalid is established; fix configuration for
     audience/issuer/scheme/header/endpoint/clock-skew);
  6. incident Task classification (durable cancellation for a provably-unstarted Task; reconciliation for a
     Provider-dispatched unknown outcome; preserve + policy-violation + compensation for a publication that
     succeeded without approval).

Plus the polling/observation boundary: polling always observes the SAME task_id, and an observation
failure or a disappearing n8n execution never mutates or replaces the durable Task.

EVIDENCE: when driven by ``test_day70_capstone.py`` these are ``EXECUTED_LOCAL_RUNTIME`` (pure decision
logic over in-memory inputs). They prove the RULES only — NOT a real n8n workflow, FastAPI process,
PostgreSQL transaction, Worker/Provider call, Approval/Publication runtime, or credential rotation. No
secrets, tokens, real URLs, tenant data, or Provider payloads live here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional, Sequence


# ---------------------------------------------------------------------------
# 1) Acceptance recovery after a lost response.
# ---------------------------------------------------------------------------
class BackendAcceptanceState(str, Enum):
    ACCEPTED = "ACCEPTED"              # authoritative: the acceptance committed
    NEVER_ACCEPTED = "NEVER_ACCEPTED"  # authoritative: proven not accepted / not started
    UNKNOWN = "UNKNOWN"               # backend could not prove either way
    NOT_FOUND = "NOT_FOUND"           # AMBIGUOUS: wrong identity/route/env, replica delay, retention, or true absence


class AcceptanceRecovery(str, Enum):
    RETURN_EXISTING = "RETURN_EXISTING"            # ACCEPTED -> use the existing task_id, never re-accept
    REISSUE_SAME_KEY = "REISSUE_SAME_KEY"          # proven NEVER_ACCEPTED AND retention still valid
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"  # everything else: unknown / ambiguous / expired retention


def acceptance_recovery(state: BackendAcceptanceState, idempotency_retention_valid: bool) -> AcceptanceRecovery:
    """A lost acceptance response is OUTCOME_UNKNOWN. n8n never writes the durable state; it preserves the
    original request/operation/idempotency identity and queries authenticated FastAPI. Reissue with the
    same key ONLY when the backend proves NEVER_ACCEPTED and the idempotency retention window is still
    valid — a same idempotency key is not unconditional proof of safety."""
    if state is BackendAcceptanceState.ACCEPTED:
        return AcceptanceRecovery.RETURN_EXISTING
    if state is BackendAcceptanceState.NEVER_ACCEPTED and idempotency_retention_valid:
        return AcceptanceRecovery.REISSUE_SAME_KEY
    return AcceptanceRecovery.PENDING_RECONCILIATION


def not_found_proves_never_accepted() -> bool:
    """A 404/NOT_FOUND does NOT prove the command was never accepted — it may mean wrong
    tenant/auth/route/environment, replica delay, retention/archival, wrong key type, or true absence."""
    return False


# ---------------------------------------------------------------------------
# 2) Callback event dedupe / conflict.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DeliveredEvent:
    event_id: str
    fingerprint: str   # a stable digest of the event's business meaning (type/task/correlation/version/artifact)


class EventDecision(str, Enum):
    IDEMPOTENT_NO_OP = "IDEMPOTENT_NO_OP"      # same event_id + same fingerprint -> return the same outcome
    CONFLICT = "CONFLICT"                       # same event_id + different fingerprint -> investigate, no action
    PROCESS_NEW = "PROCESS_NEW"                 # a genuinely new event_id -> process under the normal gate


def classify_event(seen: Optional[DeliveredEvent], incoming: DeliveredEvent) -> EventDecision:
    """Delivery identity (event_id) and business meaning (fingerprint) are separate. A redelivery of the
    same event is a no-op; a reused event_id carrying different meaning is a conflict, never a new
    approval/publication."""
    if seen is None or seen.event_id != incoming.event_id:
        return EventDecision.PROCESS_NEW
    if seen.fingerprint == incoming.fingerprint:
        return EventDecision.IDEMPOTENT_NO_OP
    return EventDecision.CONFLICT


# ---------------------------------------------------------------------------
# 3) Exact Approval binding.
# ---------------------------------------------------------------------------
REQUIRED_APPROVAL_FIELDS: FrozenSet[str] = frozenset({
    "approval_id", "tenant_id", "task_id", "artifact_id", "artifact_version", "action",
    "approver_actor", "approver_role", "policy_version", "expires_at", "decision", "decided_at",
})


@dataclass(frozen=True)
class Approval:
    approval_id: str
    tenant_id: str
    task_id: str
    artifact_id: str
    artifact_version: str
    action: str
    approver_actor: str
    approver_role: str
    policy_version: str
    expires_at: int
    decision: str        # "APPROVED" / "REJECTED"
    decided_at: int


@dataclass(frozen=True)
class AuthorizationContext:
    """The COMPLETE expected authorization context the caller must pass. EVERY field is required and is
    compared against the persisted Approval; a match on only some fields never authorizes the action.
    ``approver_actor`` and ``approver_role`` are mandatory — there is deliberately NO default that would let
    a caller omit the approver identity or role and still obtain authorization."""
    tenant_id: str
    task_id: str
    artifact_id: str
    artifact_version: str
    action: str
    policy_version: str
    approver_actor: str    # required: the exact approver identity the caller expects
    approver_role: str     # required: the exact approver role the caller expects


def approval_binding_complete(field_names: Sequence[str]) -> bool:
    """An Approval must carry the complete exact-binding field set; a partial binding (e.g. only
    task_id + artifact_version + approval_id) is insufficient."""
    return REQUIRED_APPROVAL_FIELDS <= set(field_names)


def approval_authorizes(approval: Approval, ctx: AuthorizationContext, now: int) -> bool:
    """An Approval authorizes an action ONLY when it is APPROVED, not expired, and EXACTLY binds the
    requested tenant + task + artifact id/version + action + policy + approver identity + approver role.
    Every field is compared unconditionally: a caller cannot skip the approver actor or role check, because
    both are required fields of ``AuthorizationContext``. Any single mismatch — different tenant, task,
    artifact_id, artifact_version, action, policy, approver_actor, or approver_role, a REJECTED decision, or
    an expired Approval — denies authorization. A v7 approval can never authorize v8. The Approval itself is
    a durable FastAPI/PostgreSQL fact; n8n never owns this decision, it only asks."""
    return (
        approval.decision == "APPROVED"
        and approval.expires_at > now
        and approval.tenant_id == ctx.tenant_id
        and approval.task_id == ctx.task_id
        and approval.artifact_id == ctx.artifact_id
        and approval.artifact_version == ctx.artifact_version
        and approval.action == ctx.action
        and approval.policy_version == ctx.policy_version
        and approval.approver_actor == ctx.approver_actor
        and approval.approver_role == ctx.approver_role
    )


# Identity plan for a legitimate v7 -> v8 re-approval.
STABLE_IDENTITIES_V7_TO_V8: FrozenSet[str] = frozenset({"tenant_id", "task_id", "correlation_id"})
NEW_IDENTITIES_V7_TO_V8: FrozenSet[str] = frozenset({
    "artifact_version", "approval_id", "approval_event_id", "publication_operation_id",
    "publication_idempotency_key",
})
# The same policy/action/actor MAY apply but must be REVALIDATED (not assumed stable).
REVALIDATE_V7_TO_V8: FrozenSet[str] = frozenset({"policy_version", "action", "approver_actor"})


def identity_is_stable_v7_to_v8(field: str) -> bool:
    return field in STABLE_IDENTITIES_V7_TO_V8


def identity_is_new_v7_to_v8(field: str) -> bool:
    return field in NEW_IDENTITIES_V7_TO_V8


# ---------------------------------------------------------------------------
# 4) Publication recovery classification.
# ---------------------------------------------------------------------------
class PublicationStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    PROCESSING = "PROCESSING"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    NOT_FOUND = "NOT_FOUND"


class PublicationRecovery(str, Enum):
    DONE_NO_REPUBLISH = "DONE_NO_REPUBLISH"
    OBSERVE_SAME_OPERATION = "OBSERVE_SAME_OPERATION"
    TERMINAL_NO_RETRY = "TERMINAL_NO_RETRY"
    RECONCILE = "RECONCILE"
    VERIFY_BEFORE_ANY_REISSUE = "VERIFY_BEFORE_ANY_REISSUE"   # NOT_FOUND is ambiguous


def publication_recovery(status: PublicationStatus) -> PublicationRecovery:
    """A publish timeout is OUTCOME_UNKNOWN; recover by querying the authoritative operation status and a
    strictly-matching external receipt. Confirmed success is recorded (no republish); proven non-start may
    be reissued under the same identity; unknown stays reconciliation; business rejection is terminal;
    NOT_FOUND is ambiguous and must be verified before any reissue."""
    return {
        PublicationStatus.SUCCEEDED: PublicationRecovery.DONE_NO_REPUBLISH,
        PublicationStatus.PROCESSING: PublicationRecovery.OBSERVE_SAME_OPERATION,
        PublicationStatus.FAILED_TERMINAL: PublicationRecovery.TERMINAL_NO_RETRY,
        PublicationStatus.PENDING_RECONCILIATION: PublicationRecovery.RECONCILE,
        PublicationStatus.NOT_FOUND: PublicationRecovery.VERIFY_BEFORE_ANY_REISSUE,
    }[status]


# ---------------------------------------------------------------------------
# 5) Credential-failure classification (a 401 is not automatically "rotate").
# ---------------------------------------------------------------------------
class CredentialCause(str, Enum):
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    COMPROMISED = "COMPROMISED"
    LEAKED = "LEAKED"
    INVALID = "INVALID"                 # established invalid credential
    AUDIENCE = "AUDIENCE"
    ISSUER = "ISSUER"
    AUTH_SCHEME = "AUTH_SCHEME"
    MISSING_HEADER = "MISSING_HEADER"
    WRONG_ENDPOINT = "WRONG_ENDPOINT"
    CLOCK_SKEW = "CLOCK_SKEW"
    UNKNOWN = "UNKNOWN"


class CredentialDecision(str, Enum):
    ROTATE = "ROTATE"                   # credential itself is expired/revoked/compromised/leaked/invalid
    FIX_CONFIGURATION = "FIX_CONFIGURATION"  # audience/issuer/scheme/header/endpoint/clock-skew
    STOP_AND_CLASSIFY = "STOP_AND_CLASSIFY"  # unknown -> stop blind retry, gather evidence, do not rotate yet


_ROTATE_CAUSES = frozenset({CredentialCause.EXPIRED, CredentialCause.REVOKED, CredentialCause.COMPROMISED,
                            CredentialCause.LEAKED, CredentialCause.INVALID})
_CONFIG_CAUSES = frozenset({CredentialCause.AUDIENCE, CredentialCause.ISSUER, CredentialCause.AUTH_SCHEME,
                            CredentialCause.MISSING_HEADER, CredentialCause.WRONG_ENDPOINT,
                            CredentialCause.CLOCK_SKEW})


def classify_credential_failure(cause: CredentialCause) -> CredentialDecision:
    """Stop blind retry and classify. Rotate/refresh ONLY when expiration/revocation/compromise/leak/
    established-invalidity is proven; fix configuration for audience/issuer/scheme/header/endpoint/clock
    skew; an unknown cause stops and gathers evidence before any rotation."""
    if cause in _ROTATE_CAUSES:
        return CredentialDecision.ROTATE
    if cause in _CONFIG_CAUSES:
        return CredentialDecision.FIX_CONFIGURATION
    return CredentialDecision.STOP_AND_CLASSIFY


def blind_retry_on_401() -> bool:
    """A 401 never permits a blind retry; stop and classify first."""
    return False


# ---------------------------------------------------------------------------
# 6) Incident Task classification.
# ---------------------------------------------------------------------------
class IncidentTaskClass(str, Enum):
    DURABLE_CANCELLATION = "DURABLE_CANCELLATION"          # provably unstarted -> guarded FastAPI cancellation
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"      # Provider-dispatched, outcome unknown
    PRESERVE_AND_COMPENSATE = "PRESERVE_AND_COMPENSATE"    # published without approval -> keep + violation + compensate
    RECLASSIFY = "RECLASSIFY"                              # guarded cancel changed 0 rows -> facts moved, reclassify


@dataclass(frozen=True)
class IncidentTask:
    published: bool
    approved: bool
    has_worker_claim: bool
    provider_dispatched: bool
    has_artifact: bool


def classify_incident_task(t: IncidentTask) -> IncidentTaskClass:
    """Rollback stops future harm; it does not undo committed facts or external effects. Classify each
    durable Task from evidence: a publication that succeeded without approval is preserved with a
    policy-violation record and compensation (never rewritten or retro-approved); a provably-unstarted Task
    (no claim/dispatch/artifact) takes a guarded durable cancellation; a Provider-dispatched unknown outcome
    is reconciled."""
    if t.published and not t.approved:
        return IncidentTaskClass.PRESERVE_AND_COMPENSATE
    if t.provider_dispatched and not t.published:
        return IncidentTaskClass.PENDING_RECONCILIATION
    if not t.has_worker_claim and not t.provider_dispatched and not t.has_artifact and not t.published:
        return IncidentTaskClass.DURABLE_CANCELLATION
    return IncidentTaskClass.PENDING_RECONCILIATION


def guarded_cancellation_result(rows_affected: int) -> IncidentTaskClass:
    """A guarded FastAPI/PostgreSQL cancellation that changes zero rows means the facts moved; stop
    automatic cancellation and reclassify."""
    return IncidentTaskClass.DURABLE_CANCELLATION if rows_affected == 1 else IncidentTaskClass.RECLASSIFY


# ---------------------------------------------------------------------------
# 7) Polling / observation boundary.
# ---------------------------------------------------------------------------
class TaskObservation(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PollDecision(str, Enum):
    WAIT_AND_REQUERY = "WAIT_AND_REQUERY"    # bounded backoff, poll the SAME task_id
    CONSUME_RESULT = "CONSUME_RESULT"
    TERMINAL = "TERMINAL"


def poll_decision(state: TaskObservation) -> PollDecision:
    """Every Poll observes the same task_id with bounded backoff and an observation deadline. For a QUEUED
    Task n8n may wait/re-query and send non-authoritative progress — it may not start a Worker, mutate
    state, fail the Task, or publish."""
    if state in (TaskObservation.QUEUED, TaskObservation.RUNNING):
        return PollDecision.WAIT_AND_REQUERY
    if state is TaskObservation.SUCCEEDED:
        return PollDecision.CONSUME_RESULT
    return PollDecision.TERMINAL


def observation_failure_changes_durable_state() -> bool:
    """An observation failure (e.g. a 503) or a disappearing n8n execution never mutates or replaces the
    durable Task; a new execution may resume observation of the same task_id without a new command."""
    return False


# ---------------------------------------------------------------------------
# 8) Static contract inspection of the importable Workflow JSON (Fix 3 + Fix 4).
# ---------------------------------------------------------------------------
def _find_node(workflow: dict, node_type: str) -> dict:
    for node in workflow.get("nodes", []):
        if node.get("type") == node_type:
            return node
    raise KeyError(node_type)


def http_request_body_expression(workflow: dict) -> str:
    """Return the HTTP Request node's JSON body expression string (the source of the FastAPI request body)."""
    node = _find_node(workflow, "n8n-nodes-base.httpRequest")
    return str(node.get("parameters", {}).get("jsonBody", ""))


def _extract_stringify_object(body: str) -> Optional[str]:
    """Return the object-literal substring ``{...}`` passed to ``JSON.stringify(...)`` in the controlled n8n
    HTTP body expression, or ``None`` if the shape is not recognised. Bracket-matched, not substring-based;
    no JavaScript is executed."""
    marker = "JSON.stringify("
    i = body.find(marker)
    if i == -1:
        return None
    j = body.find("{", i + len(marker))
    if j == -1:
        return None
    depth = 0
    for k in range(j, len(body)):
        ch = body[k]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return body[j:k + 1]
    return None


def _object_entries(obj_literal: str) -> dict:
    """Parse a single-level object literal ``{ key: value, ... }`` into ``{key: raw_value_str}``.
    Depth-aware over ``()[]{}`` so nested objects/arrays stay intact as raw value strings; splits top-level
    commas and the first top-level ``:`` of each entry. Keys are unquoted. No JavaScript is executed."""
    s = obj_literal.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return {}
    inner = s[1:-1]
    entries = []
    depth = 0
    start = 0
    for idx, ch in enumerate(inner):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            entries.append(inner[start:idx])
            start = idx + 1
    tail = inner[start:]
    if tail.strip():
        entries.append(tail)
    out = {}
    for entry in entries:
        depth = 0
        colon = -1
        for idx, ch in enumerate(entry):
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == ":" and depth == 0:
                colon = idx
                break
        if colon == -1:
            continue
        key = entry[:colon].strip().strip("'\"")
        value = entry[colon + 1:].strip()
        if key:
            out[key] = value
    return out


def workflow_sends_report_scope_in_business_input(workflow: dict) -> bool:
    """The Day59 route only reads ``document_ids`` + ``business_input``. ``report_scope`` MUST travel INSIDE
    the ``business_input`` object so it enters the request fingerprint; it must NOT be a top-level field
    Pydantic ignores, and an empty ``business_input: {}`` with a sibling top-level ``report_scope`` must be
    rejected. This performs a STRICT structural check of the controlled HTTP body expression (bracket-matched
    parsing, no substring guessing, no JavaScript execution)."""
    body = http_request_body_expression(workflow)
    obj = _extract_stringify_object(body)
    if obj is None:
        return False
    top = _object_entries(obj)
    # Required top-level keys.
    if "document_ids" not in top or "business_input" not in top:
        return False
    # report_scope must NEVER be a top-level sibling key.
    if "report_scope" in top:
        return False
    business_input = top["business_input"].strip()
    if not (business_input.startswith("{") and business_input.endswith("}")):
        return False
    return "report_scope" in _object_entries(business_input)


def if_validated_fields(workflow: dict) -> set:
    """Return the set of ``$json`` field names the IF node validates (leftValue expressions)."""
    node = _find_node(workflow, "n8n-nodes-base.if")
    fields = set()
    conds = node.get("parameters", {}).get("conditions", {}).get("conditions", [])
    for c in conds:
        left = str(c.get("leftValue", ""))
        m = re.search(r"\$json\.([A-Za-z_][A-Za-z0-9_]*)", left)
        if m:
            fields.add(m.group(1))
    return fields


def webhook_inbound_authentication(workflow: dict) -> str:
    """Return the Webhook node's configured inbound ``authentication`` mode (e.g. "headerAuth"), or "none".
    NOTE: configuring inbound authentication in the SOURCE is not the same as it having been RUN — the
    actual class run did NOT exercise external-caller -> n8n authentication (see DAY70_CAPSTONE.md)."""
    node = _find_node(workflow, "n8n-nodes-base.webhook")
    return str(node.get("parameters", {}).get("authentication", "none"))


def if_node_name(workflow: dict) -> str:
    """Return the display name of the validation IF node."""
    return str(_find_node(workflow, "n8n-nodes-base.if").get("name", ""))


def respond_400_message(workflow: dict) -> str:
    """Return the ``message`` string of the 400 invalid-request Respond node (responseCode 400)."""
    for node in workflow.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.respondToWebhook" \
                and node.get("parameters", {}).get("responseCode") == 400:
            return str(node.get("parameters", {}).get("responseBody", ""))
    return ""


def workflow_connection_targets_all_exist(workflow: dict) -> bool:
    """Every node named in ``connections`` (both the source keys and every target) must resolve to a real
    node, so renaming a node cannot silently break the workflow graph."""
    names = {n.get("name") for n in workflow.get("nodes", [])}
    connections = workflow.get("connections", {})
    for source, outputs in connections.items():
        if source not in names:
            return False
        for output in outputs.get("main", []):
            for link in output:
                if link.get("node") not in names:
                    return False
    return True
