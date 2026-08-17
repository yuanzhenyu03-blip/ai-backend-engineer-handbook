"""Day66 — pure Queue-backed Permissioned Browser-Worker decision/orchestration core (stdlib only).

Turns the Day62-Day65 browser capability into a DURABLE, QUEUE-BACKED, PERMISSIONED AI TOOL. The LLM may
PROPOSE a tool call, but the backend owns authorization, durable task truth, queue dispatch, Worker
execution authority, recovery, and audit. This is a DECISION CORE only — no real Provider/LLM, no real
PostgreSQL/Redis/Celery/Outbox Relay, no real Playwright, no Object Storage — so the RULES are
unit-testable WITHOUT a broker, a database, or a browser. It REUSES the Day63 final fence
(``day63_session_gate.final_fence``) for lease/fence checks and the Day65 recovery core
(``day65_recovery_security_policy``) for UNKNOWN_OUTCOME reconciliation and the bounded-retry gate.

Boundaries modelled (one area per classroom exercise):
  1. tool-call proposal validation: an LLM ``browser.export_report`` proposal is UNTRUSTED request input.
     ``idempotency_key`` identifies one intent ONLY when bound to a request fingerprint (tenant +
     operation + exact Origin + report/data scope); same key + different fingerprint is rejected. User
     approval is necessary but NOT sufficient — backend policy is the enforceable authority.
  2. acceptance lifecycle boundary: a Provider tool-call is a PROPOSAL (step 3); validation is next;
     durable acceptance happens ONLY at the committed transaction.
  3. atomic acceptance: Browser Task/Job + Permissioned Tool Contract + Outbox dispatch intent commit in
     ONE transaction; any partial write rolls back ALL — only a full commit returns ``202 + task_id``.
     Dispatch goes through an independent Outbox Relay AFTER commit, never a direct in-request publish.
  4. minimal versioned Queue Envelope: only ``envelope_version``/``event_id``/``task_id``/``trace_id``/
     ``event_type``. NEVER Cookies, storage state, Authorization, Provider keys, raw diagnostics, raw page
     data, or executable capabilities. An unsupported version is dead-lettered + ACKed WITHOUT loading a
     Job/credentials/Playwright. Envelope fields are NEVER authorization.
  5. guarded claim + lease: a queue message is a NOTIFICATION; a guarded PostgreSQL ``UPDATE ... RETURNING``
     claim (attempt_id + lease owner/token/expiry) is temporary EXECUTION AUTHORITY. Exactly one winner.
  6. stale-write rejection: a terminal write requires the CURRENT task state + matching owner/token +
     unexpired lease (the Day63 final fence). A stale Worker cannot publish just because it has valid bytes.
  7. commit-before-ACK + terminal dedupe: commit the durable result BEFORE ACK; a redelivered Worker that
     reads a terminal state does NOT re-run Playwright — it ACKs the duplicate and lets the caller read
     durable state.
  8. Day65 recovery on the durable lifecycle: lease expiry = loss of authority, NOT proof the external
     action did not happen -> UNKNOWN_OUTCOME reconciliation by strict identity; only a proven non-start
     enters the bounded-retry gate; a retry is a NEW auditable Attempt (new attempt_id + lease token).
  9. cancellation/revocation: durable ``cancellation_requested`` (not immediate ``cancelled``) when an
     external effect may have begun; the current lease holder cooperatively stops and reconciles.
 10. async permissioned-tool response: ``202 Accepted + task_id``; ``accepted != running != succeeded !=
     published Artifact``; the Tool Result returned to the Provider/LLM is a safe verified summary + a
     protected Artifact reference ONLY — never raw CSV/trace/Cookies/storage-state/headers/DOM/network.
 11. correlation identity: ``task_id`` is stable across attempts; ``attempt_id`` changes per attempt;
     ``lease_token`` fences one authority grant; ``outbox_event_id`` is dispatch intent; ``trace_id`` links.
 12. incident rollback (fence-removal regression): ``contain -> scope -> classify -> repair ->
     controlled rollout``; a stale-published Artifact is quarantined, never trusted/returned to the LLM.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``tests/test_day66_queue_backed_permissioned_worker.py``. They prove the RULES only — NOT a real
Provider/LLM tool loop, real guarded PostgreSQL concurrent claims, a real Outbox Relay/Broker, real
Celery ACK/redelivery, real lease expiry/recovery, real Playwright BrowserContext execution, real
Session revocation/cancellation, real Object Storage publication, integration, or production (all NOT
RUN — see the design/runbook). The live classroom artifact was ``CONCEPTUAL_STATIC``. No secrets, real
credentials, real URLs, Cookies, storage state, Authorization headers, Provider keys, customer data, raw
traces/screenshots/DOM/network payloads, or real Provider calls live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional, Sequence

from day63_session_gate import Outcome, SessionMeta, final_fence
from day65_recovery_security_policy import (
    FenceInputs,
    ReconcileNextStep,
    ReconcileResult,
    RetryContext,
    RetryDecision,
    RetryPolicy,
    authorize_retry,
    reconcile_next_step,
    reconcile_permits_publication,
    reconcile_permits_replay,
)


# ---------------------------------------------------------------------------
# 1) Tool-call proposal validation — an LLM proposal is untrusted request input.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RequestFingerprint:
    """The bound business intent. ``idempotency_key`` identifies ONE intent only together with this."""
    tenant_id: str
    operation: str
    target_origin: str
    report_scope: str


@dataclass(frozen=True)
class ToolCallProposal:
    """An LLM/Provider tool-call proposal — UNTRUSTED request input, never authorization. It carries NO
    self-asserted approval: a proposal can never prove the user approved it (any such claim would be
    forgeable). Approval is a SERVER fact carried by ``ServerAuthorizedContract``."""
    is_tool_call: bool
    operation: str
    tenant_id: str
    target_origin: str
    report_scope: str
    idempotency_key: Optional[str]


@dataclass(frozen=True)
class ServerAuthorizedContract:
    """The SERVER-authorized context/contract — the ONLY source of authorization facts. Built by the
    backend from the authenticated tenant, its policy, and an approved Session binding. The LLM proposal's
    ``tenant_id`` / ``target_origin`` / ``report_scope`` are UNTRUSTED and must match this EXACTLY; the
    proposal never widens what the contract permits."""
    tenant_id: str
    allowed_operation: str
    approved_origin: str          # exact scheme+host+port the Session is bound to
    allowed_report_scope: str
    session_authorized: bool      # a valid Session/authorization binding exists for this tenant+Origin
    approval_granted: bool        # a durable, server-side user-approval fact (never taken from the proposal)
    approval_id: Optional[str] = None  # an auditable reference to the persisted approval decision


@dataclass(frozen=True)
class ExistingAcceptance:
    """A previously committed acceptance for the same idempotency_key (or ``None`` if new)."""
    idempotency_key: str
    fingerprint: RequestFingerprint


class ProposalDecision(str, Enum):
    ACCEPT_NEW = "ACCEPT_NEW"                             # validated -> may proceed to atomic acceptance
    REPLAY_EXISTING = "REPLAY_EXISTING"                   # same key + same fingerprint -> return existing task_id
    REJECT_NOT_A_TOOL_CALL = "REJECT_NOT_A_TOOL_CALL"
    REJECT_MISSING_IDEMPOTENCY = "REJECT_MISSING_IDEMPOTENCY"
    REJECT_UNAPPROVED = "REJECT_UNAPPROVED"               # no server-side approval fact (never self-asserted)
    REJECT_POLICY_BLOCKED = "REJECT_POLICY_BLOCKED"       # operation not permitted by the server contract
    REJECT_TENANT_MISMATCH = "REJECT_TENANT_MISMATCH"     # proposal tenant != authorized tenant
    REJECT_ORIGIN_NOT_APPROVED = "REJECT_ORIGIN_NOT_APPROVED"  # target Origin not the approved Origin
    REJECT_SCOPE_NOT_ALLOWED = "REJECT_SCOPE_NOT_ALLOWED"  # report/data scope outside the contract
    REJECT_SESSION_UNAUTHORIZED = "REJECT_SESSION_UNAUTHORIZED"  # no valid Session/authorization binding
    REJECT_FINGERPRINT_MISMATCH = "REJECT_FINGERPRINT_MISMATCH"  # same key, DIFFERENT intent -> reject


def fingerprint_of(proposal: ToolCallProposal) -> RequestFingerprint:
    return RequestFingerprint(proposal.tenant_id, proposal.operation, proposal.target_origin,
                              proposal.report_scope)


def validate_tool_proposal(
    proposal: ToolCallProposal,
    contract: ServerAuthorizedContract,
    existing: Optional[ExistingAcceptance] = None,
) -> ProposalDecision:
    """Backend validation of an UNTRUSTED proposal against the SERVER-authorized contract. A tool call is
    NOT authorization or durable acceptance: it must be a real tool call, carry an idempotency key, and
    match the server contract EXACTLY on tenant, operation, approved Origin, and report scope, with a valid
    Session/authorization binding AND a server-side approval fact (``contract.approval_granted``) — the
    proposal's own tenant/Origin/scope are never trusted and can never widen the contract, and the proposal
    can never self-assert approval. When the key was seen before, the request fingerprint must match (same
    key + same authorized intent = idempotent replay; same key + different intent = reject)."""
    if not proposal.is_tool_call:
        return ProposalDecision.REJECT_NOT_A_TOOL_CALL
    if not proposal.idempotency_key:
        return ProposalDecision.REJECT_MISSING_IDEMPOTENCY
    if not contract.approval_granted:
        return ProposalDecision.REJECT_UNAPPROVED   # approval is a SERVER fact, never from the proposal
    if proposal.tenant_id != contract.tenant_id:
        return ProposalDecision.REJECT_TENANT_MISMATCH
    if proposal.operation != contract.allowed_operation:
        return ProposalDecision.REJECT_POLICY_BLOCKED
    if proposal.target_origin != contract.approved_origin:
        return ProposalDecision.REJECT_ORIGIN_NOT_APPROVED
    if proposal.report_scope != contract.allowed_report_scope:
        return ProposalDecision.REJECT_SCOPE_NOT_ALLOWED
    if not contract.session_authorized:
        return ProposalDecision.REJECT_SESSION_UNAUTHORIZED
    if existing is not None and existing.idempotency_key == proposal.idempotency_key:
        return (ProposalDecision.REPLAY_EXISTING
                if existing.fingerprint == fingerprint_of(proposal)
                else ProposalDecision.REJECT_FINGERPRINT_MISMATCH)
    return ProposalDecision.ACCEPT_NEW


# ---------------------------------------------------------------------------
# 2) Acceptance lifecycle boundary — proposal (step 3) -> validated -> durably accepted.
# ---------------------------------------------------------------------------
class AcceptanceStage(str, Enum):
    PROVIDER_PROPOSAL = "PROVIDER_PROPOSAL"     # step 3: the Provider returned a tool-call proposal
    VALIDATED = "VALIDATED"                     # backend policy/fingerprint validation passed
    DURABLY_ACCEPTED = "DURABLY_ACCEPTED"       # ONE transaction committed Task + Contract + Outbox


def becomes_durable_task_at(stage: AcceptanceStage) -> bool:
    """A model suggestion becomes an executable DURABLE task ONLY at the committed-transaction stage — not
    when the Provider responds (a proposal) and not merely when validation passes."""
    return stage is AcceptanceStage.DURABLY_ACCEPTED


# ---------------------------------------------------------------------------
# 3) Atomic Task/Contract/Outbox acceptance + Relay-after-commit.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AcceptanceBundle:
    """Did each write of the single acceptance transaction commit? ``202`` requires ALL three."""
    task_inserted: bool
    contract_inserted: bool
    outbox_inserted: bool


class AcceptanceOutcome(str, Enum):
    ACCEPTED_202 = "ACCEPTED_202"      # Browser Task + Permissioned Contract + Outbox intent all committed
    ROLLED_BACK = "ROLLED_BACK"        # any partial write -> roll back ALL, NO 202, NO task_id


def atomic_acceptance(bundle: AcceptanceBundle) -> AcceptanceOutcome:
    """The Job/Task, the Permissioned Tool Contract and the Outbox dispatch intent commit together or not
    at all. A committed Task without a committed Outbox intent (or vice-versa) is never a ``202``."""
    if bundle.task_inserted and bundle.contract_inserted and bundle.outbox_inserted:
        return AcceptanceOutcome.ACCEPTED_202
    return AcceptanceOutcome.ROLLED_BACK


def dispatch_via_relay_after_commit() -> bool:
    """Dispatch is emitted by an INDEPENDENT Outbox Relay AFTER the DB commit — a direct in-request broker
    publish can be lost after commit but before send; a committed Outbox row lets the Relay recover it."""
    return True


def direct_in_request_publish_is_safe() -> bool:
    return False


# ---------------------------------------------------------------------------
# 4) Minimal versioned Queue Envelope — identity only, never authorization/secrets.
# ---------------------------------------------------------------------------
SUPPORTED_ENVELOPE_VERSIONS: FrozenSet[int] = frozenset({1})

# The COMPLETE, exclusive set of fields a valid envelope may carry — a strict ALLOWLIST, not a denylist.
# ANY field outside this set (a credential, a future field, an unknown key) is rejected on sight.
ALLOWED_ENVELOPE_FIELDS: FrozenSet[str] = frozenset({
    "envelope_version", "event_id", "task_id", "trace_id", "event_type",
})

# The only event types that are a browser-task dispatch notification.
ALLOWED_EVENT_TYPES: FrozenSet[str] = frozenset({"browser.task.dispatch"})

_REQUIRED_ENVELOPE_IDENTITY = ("event_id", "task_id", "trace_id", "event_type")


@dataclass(frozen=True)
class QueueEnvelope:
    envelope_version: int
    event_id: str
    task_id: str
    trace_id: str
    event_type: str
    extra_field_names: FrozenSet[str] = frozenset()   # any field names present BEYOND the five allowed ones


class EnvelopeDecision(str, Enum):
    ACCEPT = "ACCEPT"
    DEAD_LETTER_UNSUPPORTED_VERSION = "DEAD_LETTER_UNSUPPORTED_VERSION"  # classify + ACK, load nothing
    REJECT_UNKNOWN_FIELD = "REJECT_UNKNOWN_FIELD"        # any field outside the strict allowlist -> reject
    REJECT_MISSING_IDENTITY = "REJECT_MISSING_IDENTITY"
    REJECT_EVENT_TYPE = "REJECT_EVENT_TYPE"              # not a browser-task dispatch event


def validate_envelope(env: QueueEnvelope) -> EnvelopeDecision:
    """The envelope is validated by a STRICT ALLOWLIST — it may carry ONLY ``envelope_version``,
    ``event_id``, ``task_id``, ``trace_id`` and ``event_type``; ANY extra field (a credential like
    ``session_token``, or any unknown/future field) is rejected without a denylist. An unsupported
    ``envelope_version`` is durably dead-lettered and ACKed WITHOUT loading a Job, Session, or Playwright.
    A message whose ``event_type`` is not a browser-task dispatch is rejected. A valid envelope is only a
    NOTIFICATION — never authorization."""
    if env.envelope_version not in SUPPORTED_ENVELOPE_VERSIONS:
        return EnvelopeDecision.DEAD_LETTER_UNSUPPORTED_VERSION
    # Strict allowlist: any field beyond the five canonical identity fields is rejected.
    if set(env.extra_field_names) - ALLOWED_ENVELOPE_FIELDS:
        return EnvelopeDecision.REJECT_UNKNOWN_FIELD
    if not all(getattr(env, f) for f in _REQUIRED_ENVELOPE_IDENTITY):
        return EnvelopeDecision.REJECT_MISSING_IDENTITY
    if env.event_type not in ALLOWED_EVENT_TYPES:
        return EnvelopeDecision.REJECT_EVENT_TYPE
    return EnvelopeDecision.ACCEPT


def envelope_payload_is_authorization() -> bool:
    """Queue payload fields are NEVER authorization; fresh DB/policy/Session checks are always required."""
    return False


# ---------------------------------------------------------------------------
# 5) Task state + guarded claim (temporary execution authority).
# ---------------------------------------------------------------------------
class TaskState(str, Enum):
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLED = "CANCELLED"


_TERMINAL_STATES = frozenset({TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED})
_CLAIMABLE_STATES = frozenset({TaskState.ACCEPTED, TaskState.RUNNING})


def is_terminal(state: TaskState) -> bool:
    return state in _TERMINAL_STATES


@dataclass(frozen=True)
class ClaimRequest:
    task_state: TaskState
    lease_owner: Optional[str]        # attempt_id currently holding the lease, or None
    lease_expires_at: Optional[int]   # epoch seconds
    now: int
    attempt_id: str                   # the claiming Attempt


class ClaimDecision(str, Enum):
    CLAIMED = "CLAIMED"                          # guarded UPDATE ... RETURNING succeeded (exactly one winner)
    DENIED_TERMINAL = "DENIED_TERMINAL"          # already terminal -> do not execute
    DENIED_NOT_CLAIMABLE = "DENIED_NOT_CLAIMABLE"  # cancellation requested/other non-claimable state
    DENIED_LEASE_ACTIVE = "DENIED_LEASE_ACTIVE"  # another Attempt holds an unexpired lease


def guarded_claim(req: ClaimRequest) -> ClaimDecision:
    """Model ``UPDATE tasks SET lease_owner=:a, lease_token=:t, lease_expires_at=:exp WHERE task_id=:id
    AND state IN (claimable) AND (lease_owner IS NULL OR lease_owner=:a OR lease_expires_at<=:now)
    RETURNING``. Queue delivery does NOT grant authority — this guarded claim does, and only to ONE
    Attempt. A terminal task is never re-executed."""
    if is_terminal(req.task_state):
        return ClaimDecision.DENIED_TERMINAL
    if req.task_state not in _CLAIMABLE_STATES:
        return ClaimDecision.DENIED_NOT_CLAIMABLE
    # A claim may ONLY take a task with NO lease or an EXPIRED lease. A still-valid lease is rejected even
    # for the SAME attempt_id — a duplicate/concurrent path must NOT re-claim (that would overwrite the
    # live lease). Extending a lease held by this Attempt is a separate operation: renew_lease().
    lease_present_and_valid = (
        req.lease_owner is not None
        and req.lease_expires_at is not None
        and req.lease_expires_at > req.now
    )
    if lease_present_and_valid:
        return ClaimDecision.DENIED_LEASE_ACTIVE
    return ClaimDecision.CLAIMED


@dataclass(frozen=True)
class RenewLeaseRequest:
    task_state: TaskState
    lease_owner: Optional[str]        # attempt_id currently holding the lease
    lease_token: Optional[str]        # the token currently fencing the lease
    lease_expires_at: Optional[int]   # epoch seconds
    now: int
    attempt_id: str                   # the Attempt asking to extend ITS OWN lease
    worker_token: str                 # the token the Attempt currently holds
    new_expires_at: int               # the requested extended expiry


class RenewDecision(str, Enum):
    RENEWED = "RENEWED"                          # same owner+token, still-valid lease -> extend expiry only
    DENIED_NOT_RUNNING = "DENIED_NOT_RUNNING"
    DENIED_OWNER_MISMATCH = "DENIED_OWNER_MISMATCH"
    DENIED_TOKEN_MISMATCH = "DENIED_TOKEN_MISMATCH"
    DENIED_LEASE_EXPIRED = "DENIED_LEASE_EXPIRED"  # an expired lease is re-acquired via guarded_claim, not renewed


def renew_lease(req: RenewLeaseRequest) -> RenewDecision:
    """Extend an Attempt's OWN still-valid lease. Renewal is NOT a re-claim and NEVER re-executes
    Playwright: it requires a RUNNING task, the CURRENT ``lease_owner`` == this ``attempt_id``, the
    CURRENT ``lease_token`` == this ``worker_token``, and an UNEXPIRED lease; it then pushes out only the
    expiry (via ``renewed_expiry``) and preserves the existing token (a renewal never rotates the token).
    An expired lease can never be renewed — it must be re-acquired through ``guarded_claim``."""
    if req.task_state is not TaskState.RUNNING:
        return RenewDecision.DENIED_NOT_RUNNING
    if req.lease_owner != req.attempt_id:
        return RenewDecision.DENIED_OWNER_MISMATCH
    if req.lease_token != req.worker_token:
        return RenewDecision.DENIED_TOKEN_MISMATCH
    if req.lease_expires_at is None or req.lease_expires_at <= req.now:
        return RenewDecision.DENIED_LEASE_EXPIRED
    return RenewDecision.RENEWED


def renewed_expiry(req: RenewLeaseRequest) -> Optional[int]:
    """The new lease expiry to persist on a successful renewal (the token is left unchanged); ``None`` when
    the renewal is denied."""
    return req.new_expires_at if renew_lease(req) is RenewDecision.RENEWED else None


# ---------------------------------------------------------------------------
# 6) Stale-write rejection on a terminal publish — reuse the Day63 final fence.
# ---------------------------------------------------------------------------
def terminal_publish_allowed(fence: FenceInputs) -> bool:
    """A terminal ``succeeded`` write / Artifact publication is allowed ONLY when the Day63 final fence
    still holds (active + session-expiry + lease_owner==attempt + lease_token + unexpired lease + version).
    A stale Worker whose token/version was superseded or whose lease expired can NEVER publish — even with
    valid bytes."""
    return final_fence(fence.meta, fence.worker_token, fence.claimed_version, fence.attempt_id,
                       fence.now, timed_out=fence.timed_out) is Outcome.AUTHORIZED


def stale_bytes_are_trusted_artifact() -> bool:
    """A stale Attempt's candidate data is NOT automatically a trusted Artifact."""
    return False


# ---------------------------------------------------------------------------
# 7) Delivery handling — commit-before-ACK, terminal dedupe, in-flight, cancellation.
# ---------------------------------------------------------------------------
class DeliveryDecision(str, Enum):
    EXECUTE = "EXECUTE"                              # ACCEPTED, no live lease -> claim + run
    SKIP_TERMINAL_ACK = "SKIP_TERMINAL_ACK"          # already SUCCEEDED/FAILED/CANCELLED -> ACK duplicate, no run
    SKIP_ACTIVE_LEASE_ACK = "SKIP_ACTIVE_LEASE_ACK"  # RUNNING with a LIVE lease -> another Attempt owns it; ACK duplicate, no run
    RECONCILE_IN_FLIGHT = "RECONCILE_IN_FLIGHT"      # RUNNING with an EXPIRED lease -> Day65 reconciliation
    STOP_CANCELLATION_REQUESTED = "STOP_CANCELLATION_REQUESTED"  # cooperative stop / reconcile if needed


def on_delivery(task_state: TaskState, lease_expired: bool) -> DeliveryDecision:
    """Decide what a (possibly duplicate) Broker delivery should do from CURRENT durable truth. A
    redelivered message whose task is already terminal is ACKed WITHOUT re-running Playwright; a RUNNING
    task whose lease is STILL LIVE is owned by another Attempt, so this duplicate is ACKed WITHOUT entering
    the Playwright path (``SKIP_ACTIVE_LEASE_ACK``); only a RUNNING task whose lease EXPIRED is reconciled
    (Day65); a cancellation request stops."""
    if is_terminal(task_state):
        return DeliveryDecision.SKIP_TERMINAL_ACK
    if task_state is TaskState.CANCELLATION_REQUESTED:
        return DeliveryDecision.STOP_CANCELLATION_REQUESTED
    if task_state is TaskState.RUNNING:
        return (DeliveryDecision.RECONCILE_IN_FLIGHT if lease_expired
                else DeliveryDecision.SKIP_ACTIVE_LEASE_ACK)
    return DeliveryDecision.EXECUTE


def ack_only_after_durable_commit() -> bool:
    """ACK is sent ONLY after the durable result commit. If a Worker crashes after commit but before ACK,
    the redelivered Worker reads the terminal state, does NOT re-run, and ACKs the duplicate."""
    return True


def redelivered_worker_returns_result_to_broker() -> bool:
    """A redelivered Worker does NOT return a result to the Broker; it reads terminal DB state and ACKs."""
    return False


# ---------------------------------------------------------------------------
# 8) Day65 UNKNOWN_OUTCOME reconciliation hand-off on the durable lifecycle.
# ---------------------------------------------------------------------------
def lease_expiry_proves_no_external_effect() -> bool:
    """Lease expiry means loss of AUTHORITY, not proof the external action did not happen."""
    return False


def recovery_next_step(result: ReconcileResult) -> ReconcileNextStep:
    """Hand a recovered ``UNKNOWN_OUTCOME`` to the Day65 reconciliation outcome: publish only under the
    current fence for a terminal completion; keep reconciling the same action for accepted/in-flight (no
    replay); or become eligible for a bounded retry only on a proven non-start."""
    return reconcile_next_step(result)


def recovery_permits_publication(result: ReconcileResult) -> bool:
    return reconcile_permits_publication(result)


def recovery_permits_replay(result: ReconcileResult) -> bool:
    return reconcile_permits_replay(result)


# ---------------------------------------------------------------------------
# 9) Safe retry gate on the durable Worker — reuse the Day65 fenced retry gate.
# ---------------------------------------------------------------------------
def worker_retry_decision(policy: RetryPolicy, ctx: RetryContext, fence: FenceInputs) -> RetryDecision:
    """A new retry is a NEW auditable Attempt (new attempt_id + lease token), never an in-process loop or
    reuse of the old lease. Delegate to the Day65 ENFORCED gate, which recomputes authorization from the
    Day63 fence and requires a retryable class + proven non-start/idempotency + no UNKNOWN + no security
    stop + one owner + deadline/budget."""
    return authorize_retry(policy, ctx, fence)


def retry_is_new_attempt_identity(old_attempt_id: str, new_attempt_id: str,
                                  old_lease_token: str, new_lease_token: str) -> bool:
    """A safe retry must carry a NEW attempt_id AND a NEW lease token (a fresh authority grant)."""
    return old_attempt_id != new_attempt_id and old_lease_token != new_lease_token


# ---------------------------------------------------------------------------
# 10) Cancellation / revocation — durable, cooperative, fenced.
# ---------------------------------------------------------------------------
class CancellationDecision(str, Enum):
    RECORD_CANCELLATION_REQUESTED = "RECORD_CANCELLATION_REQUESTED"  # external effect may have begun
    CANCEL_IMMEDIATELY = "CANCEL_IMMEDIATELY"                        # provably nothing external happened


def classify_cancellation(external_action_may_have_started: bool) -> CancellationDecision:
    """When an external action may already have begun, record a DURABLE ``cancellation_requested`` and let
    the current lease holder cooperatively stop and reconcile — never an immediate false ``cancelled``.
    Only a provable non-start may cancel immediately. The cancellation request and the external outcome are
    SEPARATE auditable facts."""
    if external_action_may_have_started:
        return CancellationDecision.RECORD_CANCELLATION_REQUESTED
    return CancellationDecision.CANCEL_IMMEDIATELY


def cancellation_checkpoints() -> tuple:
    """Both checks are required: check the latest durable truth BEFORE the claim, then revalidate the final
    fence before credential load, before each critical browser action, and before the final publication."""
    return ("before_claim", "before_credential_load", "before_critical_action", "before_publication")


# ---------------------------------------------------------------------------
# 11) Async permissioned-tool response + safe Tool Result boundary.
# ---------------------------------------------------------------------------
def accepted_is_not_succeeded() -> bool:
    """``accepted != running != succeeded != published Artifact`` — the status API returns only safe state,
    and a result reference appears ONLY after a guarded successful terminal write."""
    return True


# The COMPLETE, exclusive set of fields a Tool Result may return to the Provider/LLM — a strict ALLOWLIST,
# not a denylist. The Artifact reference is a protected, access-controlled REFERENCE only; it never grants
# the model object-read access.
ALLOWED_TOOL_RESULT_FIELDS: FrozenSet[str] = frozenset({
    "task_id", "status", "safe_summary", "artifact_ref",
})


@dataclass(frozen=True)
class ToolResultDraft:
    tenant_authorized: bool
    terminal_succeeded: bool          # a guarded successful terminal write exists
    summary_is_safe: bool             # the summary was authorized + verified + redacted
    field_names: FrozenSet[str]       # everything the draft wants to return to the model
    includes_artifact_reference: bool


class ToolResultDecision(str, Enum):
    RETURN_SAFE_SUMMARY = "RETURN_SAFE_SUMMARY"                 # safe summary (+ protected Artifact ref)
    DENY_NOT_AUTHORIZED = "DENY_NOT_AUTHORIZED"
    DENY_NOT_TERMINAL = "DENY_NOT_TERMINAL"                     # no guarded successful terminal write yet
    DENY_UNSAFE_FIELD = "DENY_UNSAFE_FIELD"                     # any field outside the strict allowlist
    DENY_UNVERIFIED_SUMMARY = "DENY_UNVERIFIED_SUMMARY"


def shape_tool_result(draft: ToolResultDraft) -> ToolResultDecision:
    """The Tool Result to the Provider/LLM is validated by a STRICT ALLOWLIST — it may carry ONLY
    ``task_id``, ``status``, ``safe_summary`` and ``artifact_ref``. ANY other field (a ``session_token``,
    ``authorization``, ``raw_prompt``, ``cookies``, ``trace``, ``raw_csv``, or any unknown/future field) is
    rejected without a denylist. The result must be tenant-authorized, backed by a guarded successful
    terminal write, and carry a verified safe summary. The Artifact reference is a protected,
    access-controlled REFERENCE only — it never grants the model object-read access."""
    if not draft.tenant_authorized:
        return ToolResultDecision.DENY_NOT_AUTHORIZED
    if not draft.terminal_succeeded:
        return ToolResultDecision.DENY_NOT_TERMINAL
    if set(draft.field_names) - ALLOWED_TOOL_RESULT_FIELDS:
        return ToolResultDecision.DENY_UNSAFE_FIELD
    if not draft.summary_is_safe:
        return ToolResultDecision.DENY_UNVERIFIED_SUMMARY
    return ToolResultDecision.RETURN_SAFE_SUMMARY


# ---------------------------------------------------------------------------
# 12) Correlation / audit identity.
# ---------------------------------------------------------------------------
def task_id_stable_across_attempts() -> bool:
    """``task_id`` identifies the durable business task and must NOT change across repeated execution."""
    return True


def attempt_id_changes_per_attempt() -> bool:
    """``attempt_id`` identifies ONE execution/recovery attempt and must change each attempt."""
    return True


# The COMPLETE, exclusive set of fields an audit event may carry — a strict ALLOWLIST, not a denylist.
# NOTE: the raw ``lease_token`` is a fencing CAPABILITY and is NOT audit-safe; only an irreversible
# ``lease_token_fingerprint`` (a controlled, non-reversible digest/reference) may be recorded.
SAFE_AUDIT_FIELDS: FrozenSet[str] = frozenset({
    "task_id", "attempt_id", "outbox_event_id", "trace_id", "lease_token_fingerprint", "state_transition",
    "policy_version", "contract_version", "classification", "timestamp",
})


def audit_event_is_safe(field_names: Sequence[str]) -> bool:
    """A safe audit event carries ONLY allowlisted identity/metadata: task/attempt/outbox/trace identity, a
    non-reversible ``lease_token_fingerprint`` (never the raw ``lease_token`` capability), the state
    transition, policy/contract version, a safe classification and a timestamp. ANY field outside the
    allowlist — a raw ``lease_token``, a ``session_token``, or any unknown/future field — makes the event
    unsafe (strict allowlist, not a denylist)."""
    return set(field_names) <= SAFE_AUDIT_FIELDS


# ---------------------------------------------------------------------------
# 13) Incident rollback — stale-Worker fence-removal regression.
# ---------------------------------------------------------------------------
class WorkerIncidentClass(str, Enum):
    BLOCKED_STALE_WRITE = "BLOCKED_STALE_WRITE"                  # fence still held; the stale write was blocked
    STALE_ARTIFACT_PUBLISHED = "STALE_ARTIFACT_PUBLISHED"       # a stale Attempt published -> quarantine
    CONFLICTING_ATTEMPTS = "CONFLICTING_ATTEMPTS"               # two Attempts raced on the same task
    UNKNOWN = "UNKNOWN"                                          # incomplete evidence -> reconcile/investigate


def classify_worker_incident(
    *,
    evidence_complete: bool,
    stale_write_blocked: bool,
    stale_artifact_published: bool,
    conflicting_attempts: bool,
) -> WorkerIncidentClass:
    """Scope past harm from ACTUALLY-preserved evidence (release version/window, task/attempt/lease token,
    Outbox/Worker records, Artifact reference). Incomplete evidence is ``UNKNOWN`` — reconciled and
    investigated, never blindly retried."""
    if not evidence_complete:
        return WorkerIncidentClass.UNKNOWN
    if stale_artifact_published:
        return WorkerIncidentClass.STALE_ARTIFACT_PUBLISHED
    if conflicting_attempts:
        return WorkerIncidentClass.CONFLICTING_ATTEMPTS
    if stale_write_blocked:
        return WorkerIncidentClass.BLOCKED_STALE_WRITE
    return WorkerIncidentClass.UNKNOWN


def incident_phases() -> tuple:
    """The incident flow: contain -> scope -> classify -> repair -> controlled rollout."""
    return ("contain", "scope", "classify", "repair", "controlled_rollout")


def stale_published_artifact_is_trusted() -> bool:
    """An Artifact published by a stale Attempt cannot immediately be trusted or returned to the LLM — it is
    quarantined and reconciled against authority and external evidence first."""
    return False


def rollback_target_is_worker_release() -> bool:
    """A Worker-code fence-removal regression is repaired by rolling back the faulty WORKER RELEASE and
    pausing risky claims/Attempts — not merely by reverting configuration."""
    return True
