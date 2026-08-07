"""Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection.

Day56 defined the admission-to-Provider control plane (guarded claim / rate permit / reservation /
circuit -> CALL / DEFER / RECONCILE / TERMINAL / NOOP). Day57 turns those POLICIES into REPEATABLE
EVIDENCE: a deterministic, controllable Fake Provider, application-owned Adapter contracts, strict
structured-output contract checks, deterministic backoff/jitter, and failure-injection scenarios —
driving the REAL Day56 functions (and Day53's real validator) rather than re-implementing them.

WHAT THIS HARNESS PROVIDES (deterministic test doubles + verification helpers):
  * FakeClock + DeterministicRandom      — no wall-clock sleeps, reproducible jitter.
  * ProviderCallLog                       — an independent call log that "survives Worker loss"
                                            (it is separate from any Job store).
  * ControllableFakeProvider              — scripted outcomes, a cross-call count, optional
                                            provider_request_id/accepted evidence, and
                                            request_received / release_response gates (threading.Event)
                                            so timeout/kill windows are controlled, not timed.
  * ProviderOutcome + Adapter             — the APPLICATION-OWNED typed outcome (failure kind,
                                            execution certainty, optional request id, safe retry info,
                                            safe metadata). The Adapter never writes Job state or cost,
                                            and never leaks SDK exception classes / HTTP codes / private
                                            SDK fields upward.
  * attempt_late_completion               — the late-result contract: complete ONLY if non-terminal,
                                            awaiting reconciliation, strictly schema-valid, and every
                                            identity (job_id + attempt_id + correlation_id +
                                            provider_request_id) matches durable evidence.
  * VALIDATION_MATRIX                      — the honest FOUR-tier evidence taxonomy.

FOUR EVIDENCE TIERS (kept explicit everywhere):
  * CONCEPTUAL_STATIC        — design/decision paths described in the runbook + lesson.
  * EXECUTED_LOCAL_RUNTIME   — what the pytest suite executes: deterministic application state-machine
                               + Adapter-contract + failure-injection control flow over in-process
                               doubles (and Day53's REAL pydantic validator for the schema contract).
                               An in-process fake/double is ALWAYS this tier, never integration.
  * INTEGRATION_RUNTIME      — real disposable PostgreSQL / Celery broker + Worker / Redis boundaries;
                               NOT RUN here, distinct from production.
  * PRODUCTION               — real Provider traffic / production validation; also NOT RUN here.

NOT RUN (no such claim): real PostgreSQL transactions/rollback/isolation, a real Celery broker +
Worker process + redelivery, a real Redis limiter/circuit, real Worker-kill fault injection, and any
real Provider traffic/credentials. An in-process double does NOT prove Worker-loss or broker
redelivery; those require the real components (see VALIDATION_MATRIX). `pytest passed` alone is not
audit-grade runtime evidence — a real run must also preserve the exact command/revision, the fault
point, committed-DB-state queries, the Fake Provider cross-process call log, and broker/Worker
lifecycle evidence.

SECURITY: no secrets, no raw prompts, no raw Provider payloads. Repair/audit records carry only safe
decision evidence (IDs, release/reason/policy, safe classification, timestamps, evidence presence).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Optional

# Reuse Day53's REAL strict structured-output validator (pydantic) for the schema-contract checks,
# and Day56's application-owned execution-certainty classifier + typed enums.
from day53_openai_provider_structured_output import (
    SchemaRegistry,
    StructuredOutputValidator,
    ValidationOutcome,
)
from day56_provider_resilience import (
    ExecutionCertainty,
    JobStatus,
    classify_execution_certainty,
)


# ===========================================================================
# 1. Deterministic time + randomness (no wall-clock sleeps)
# ===========================================================================
class FakeClock:
    """A controllable clock. Tests advance it explicitly instead of sleeping, so timeout/backoff
    behavior is deterministic and fast."""

    def __init__(self, start: Optional[datetime] = None) -> None:
        self._now = start or datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


class DeterministicRandom:
    """Returns a scripted sequence of floats in [0, 1). Makes jitter reproducible: the same script
    always yields the same wake times, so a jitter assertion is stable, never flaky."""

    def __init__(self, sequence: list[float]) -> None:
        self._seq = list(sequence)
        self._i = 0

    def __call__(self) -> float:
        v = self._seq[self._i % len(self._seq)]
        self._i += 1
        return v


# ===========================================================================
# 2. Independent Provider call log (survives "Worker loss")
# ===========================================================================
@dataclass
class ProviderCallRecord:
    call_index: int
    provider_idempotency_key: Optional[str]
    provider_request_id: Optional[str]
    accepted: Optional[bool]
    http_status: int


class ProviderCallLog:
    """Records every Provider call independently of any Job store, modeling a Fake Provider service
    whose call log OUTLIVES a Worker crash. A real Worker-loss test would run this as a separate
    process; here it is an in-memory stand-in and is labeled as such."""

    def __init__(self) -> None:
        self._records: list[ProviderCallRecord] = []
        self._lock = threading.Lock()

    def record(self, rec: ProviderCallRecord) -> None:
        with self._lock:
            self._records.append(rec)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def records(self) -> list[ProviderCallRecord]:
        with self._lock:
            return list(self._records)


# ===========================================================================
# 3. Controllable Fake Provider (scripted, gated — not timed)
# ===========================================================================
@dataclass
class ScriptedResponse:
    """One scripted Provider outcome. `accepted` models whether the Provider positively acknowledged
    it did NOT accept the request (False -> definitely not accepted); None -> unknown."""
    http_status: int = 200
    provider_request_id: Optional[str] = None
    accepted: Optional[bool] = None
    payload: dict = field(default_factory=dict)


class ControllableFakeProvider:
    """A deterministic Provider double. It is an APPLICATION TEST HARNESS, not a replacement for
    integration. `request_received` fires when a call arrives; the call blocks until
    `release_response` is set, so a test can open a controlled timeout/kill window WITHOUT sleeps."""

    def __init__(self, script: list[ScriptedResponse], *, call_log: Optional[ProviderCallLog] = None,
                 auto_release: bool = True) -> None:
        self._script = list(script)
        self._log = call_log or ProviderCallLog()
        self.calls = 0
        self.request_received = threading.Event()
        self.release_response = threading.Event()
        if auto_release:
            self.release_response.set()

    @property
    def call_log(self) -> ProviderCallLog:
        return self._log

    def call(self, *, provider_idempotency_key: Optional[str] = None) -> ScriptedResponse:
        resp = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        # Record the attempt AS SOON AS it arrives (models "request left the process"): a crash after
        # this point but before the caller persists provider_request_id is the marker crash window.
        self._log.record(ProviderCallRecord(
            call_index=self.calls, provider_idempotency_key=provider_idempotency_key,
            provider_request_id=resp.provider_request_id, accepted=resp.accepted,
            http_status=resp.http_status))
        self.request_received.set()
        self.release_response.wait()          # controlled gate; a test decides when the response returns
        return resp


# ===========================================================================
# 4. Application-owned typed outcome + Adapter (no SDK leakage)
# ===========================================================================
@dataclass(frozen=True)
class ProviderOutcome:
    """The stable, application-owned outcome the Adapter delivers to the Job layer. It carries ONLY
    application-semantic fields — an application-owned failure kind, an execution-certainty
    classification, an optional request id, and safe retry info — never SDK exception classes, raw
    HTTP status codes, or private SDK fields. `failure_kind` is a small application-owned label
    (e.g. "rate_limited"), not the raw numeric status. `safe_metadata` is reserved for future safe,
    application-owned diagnostics and is empty by default; the raw HTTP status is consumed INSIDE the
    Adapter and is deliberately NOT surfaced here."""
    failure_kind: str                          # e.g. "ok" / "rate_limited" / "timeout" / "server_error"
    execution_certainty: ExecutionCertainty
    provider_request_id: Optional[str] = None
    retry_after_seconds: Optional[float] = None
    safe_metadata: dict = field(default_factory=dict)   # app-owned safe fields only; NO raw HTTP status


class ProviderAdapter:
    """Translates a Fake Provider raw signal into a ProviderOutcome. It classifies execution certainty
    (reusing Day56) and NEVER writes Job state or cost records — that stays in the Job layer."""

    _KIND = {200: "ok", 429: "rate_limited", 408: "timeout", 500: "server_error",
             502: "server_error", 503: "server_error", 504: "timeout"}

    def to_outcome(self, resp: ScriptedResponse, *, retry_after_seconds: Optional[float] = None) -> ProviderOutcome:
        certainty = classify_execution_certainty(
            http_status=resp.http_status, provider_request_id=resp.provider_request_id,
            accepted_header=resp.accepted)
        return ProviderOutcome(
            failure_kind=self._KIND.get(resp.http_status, "server_error"),   # app-owned label, not the raw code
            execution_certainty=certainty,
            provider_request_id=resp.provider_request_id,
            retry_after_seconds=retry_after_seconds,
            safe_metadata={})   # the raw HTTP status is consumed inside the Adapter, never surfaced


# ===========================================================================
# 5. Late-result completion contract (strict identity + schema match)
# ===========================================================================
class LateResultOutcome(str, Enum):
    COMPLETED = "completed"
    REFUSED_TERMINAL = "refused_terminal"                # e.g. a CANCELLED Job — never overwritten
    REFUSED_NOT_AWAITING = "refused_not_awaiting"
    REFUSED_IDENTITY_MISMATCH = "refused_identity_mismatch"
    REFUSED_INVALID_PAYLOAD = "refused_invalid_payload"


TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "expired"})


@dataclass
class LateResult:
    job_id: str
    attempt_id: str
    correlation_id: str
    provider_request_id: str
    payload: dict


def attempt_late_completion(
    *, job_status: str, awaiting_reconciliation: bool,
    durable_job_id: str, durable_attempt_id: str, durable_correlation_id: str,
    durable_provider_request_id: Optional[str],
    schema_name: str, schema_version: str,
    late: LateResult, validator: Optional[StructuredOutputValidator] = None,
) -> LateResultOutcome:
    """A late Provider result may complete a Job ONLY if the Job is non-terminal AND awaiting
    reconciliation AND the payload strictly validates against the bound schema AND all four
    identities match the durable evidence (a missing/None durable request id is a mismatch). A
    terminal (e.g. CANCELLED) Job rejects even a fully matching late result WITHOUT overwriting
    state. Side-effect-free: it returns a decision only."""
    if job_status in TERMINAL_STATES:
        return LateResultOutcome.REFUSED_TERMINAL
    if not awaiting_reconciliation:
        return LateResultOutcome.REFUSED_NOT_AWAITING
    if (durable_provider_request_id is None
            or late.job_id != durable_job_id
            or late.attempt_id != durable_attempt_id
            or late.correlation_id != durable_correlation_id
            or late.provider_request_id != durable_provider_request_id):
        return LateResultOutcome.REFUSED_IDENTITY_MISMATCH
    validator = validator or StructuredOutputValidator(SchemaRegistry())
    vres = validator.validate(schema_name, schema_version, late.payload)
    if vres.outcome is not ValidationOutcome.VALID:
        return LateResultOutcome.REFUSED_INVALID_PAYLOAD
    return LateResultOutcome.COMPLETED


# ===========================================================================
# 6. Evidence taxonomy / validation matrix (honest FOUR tiers)
# ===========================================================================
class EvidenceTier(str, Enum):
    CONCEPTUAL_STATIC = "conceptual_static"          # design/decision paths only
    EXECUTED_LOCAL_RUNTIME = "executed_local_runtime"  # in-process deterministic doubles
    INTEGRATION_RUNTIME = "integration_runtime"      # real PostgreSQL / broker+Worker / Redis (disposable)
    PRODUCTION = "production"                         # real Provider traffic / production validation


class RunStatus(str, Enum):
    RUN = "run"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class MatrixRow:
    claim: str
    tier: EvidenceTier
    run_status: RunStatus
    note: str


# INTEGRATION_RUNTIME (real PostgreSQL / Celery broker+Worker / Redis) is DISTINCT from PRODUCTION
# (real Provider traffic + production validation). Real infra integration here is NOT RUN; it is NOT
# production. In-memory deterministic tests are EXECUTED_LOCAL_RUNTIME, NEVER integration.
VALIDATION_MATRIX: tuple[MatrixRow, ...] = (
    MatrixRow("Deterministic application state machine (dispatch outcomes, certainty, late-result contract)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "pytest over in-memory doubles + Day53 real validator"),
    MatrixRow("End-to-end bare-429 -> Adapter UNKNOWN -> PENDING_RECONCILIATION + HELD + one call + reconcile-only",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "deterministic Fake Provider + Adapter + Day56"),
    MatrixRow("Controlled Worker-timeout-after-receipt -> PENDING_RECONCILIATION + HELD + no 2nd call",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "auto_release=False gate, no sleep"),
    MatrixRow("Adapter delivers application-owned typed outcomes (no raw HTTP status / SDK leakage)",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "ProviderAdapter.to_outcome tests"),
    MatrixRow("Deterministic backoff/jitter with Retry-After floor",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "FakeClock + DeterministicRandom"),
    MatrixRow("Repair idempotency (repair_id) + single Outbox intent",
              EvidenceTier.EXECUTED_LOCAL_RUNTIME, RunStatus.RUN, "drives Day56 repair_redispatch"),
    MatrixRow("Real PostgreSQL committed rollback + guarded concurrent terminal transition",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs a real disposable PostgreSQL"),
    MatrixRow("Real Celery broker redelivery + Worker-kill recovery (no 2nd call after dispatch marker)",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs a real broker + Worker process + Fake Provider service"),
    MatrixRow("Real Redis limiter/circuit outage + restored-capacity no-herd",
              EvidenceTier.INTEGRATION_RUNTIME, RunStatus.NOT_RUN, "needs a real Redis coordination store"),
    MatrixRow("Real Provider traffic / cost / rate limits",
              EvidenceTier.PRODUCTION, RunStatus.NOT_RUN, "no production Provider credentials authorized"),
    MatrixRow("job_repair_history table + migration (forward-additive design)",
              EvidenceTier.CONCEPTUAL_STATIC, RunStatus.NOT_RUN, "designed only; not migrated or tested"),
)


def not_run_claims() -> list[str]:
    """All claims not yet executed (integration + production + design-only)."""
    return [r.claim for r in VALIDATION_MATRIX if r.run_status is RunStatus.NOT_RUN]


def integration_not_run_claims() -> list[str]:
    """Real-infrastructure integration claims that are NOT RUN (distinct from production)."""
    return [r.claim for r in VALIDATION_MATRIX
            if r.tier is EvidenceTier.INTEGRATION_RUNTIME and r.run_status is RunStatus.NOT_RUN]


def production_not_run_claims() -> list[str]:
    """Production claims that are NOT RUN (real Provider traffic / production validation)."""
    return [r.claim for r in VALIDATION_MATRIX
            if r.tier is EvidenceTier.PRODUCTION and r.run_status is RunStatus.NOT_RUN]


# ---------------------------------------------------------------------------
# Application recovery helper (EXECUTED_LOCAL_RUNTIME model, not a DB transaction)
# ---------------------------------------------------------------------------
class RecoveryDecision(str, Enum):
    RECONCILE = "reconcile"        # UNKNOWN / MAY_HAVE_EXECUTED -> PENDING_RECONCILIATION + HELD
    SAFE_RETRY = "safe_retry"      # DEFINITELY_NOT_ACCEPTED -> ordinary defer/retry, NOT reconciliation


def decide_and_apply_recovery(job, ledger, outcome: "ProviderOutcome", *, now) -> RecoveryDecision:
    """The application decision/recovery boundary, driven EXPLICITLY by the Adapter's `ProviderOutcome`
    (never by the test guessing). It reads `outcome.execution_certainty` and routes:

      * DEFINITELY_NOT_ACCEPTED -> the Provider positively did NOT accept the request. This is safe to
        ordinary-defer/retry: the Job is NOT moved to PENDING_RECONCILIATION, NO dispatch marker is
        set, and the reservation stays RESERVED. Returns SAFE_RETRY (the normal defer/retry branch).
      * UNKNOWN or MAY_HAVE_EXECUTED -> the external call may have happened. Persist the conservative
        Day55 dispatch marker (the request left the process), move the Job to PENDING_RECONCILIATION,
        and HOLD the reservation. NO Provider call, NO retry -> a later redelivery is reconcile-only
        (Day56 `evaluate_dispatch` returns RECONCILE on the marker/evidence). Returns RECONCILE.

    EXECUTED_LOCAL_RUNTIME model of a step a real deployment performs in ONE PostgreSQL transaction
    (INTEGRATION_RUNTIME, NOT RUN). It makes no Provider call and never writes cost beyond holding the
    existing reservation."""
    if outcome.execution_certainty is ExecutionCertainty.DEFINITELY_NOT_ACCEPTED:
        return RecoveryDecision.SAFE_RETRY
    if job.attempt is not None and job.attempt.provider_dispatch_started_at is None:
        job.attempt.provider_dispatch_started_at = now
    job.status = JobStatus.PENDING_RECONCILIATION
    ledger.hold_for_reconciliation(job)
    return RecoveryDecision.RECONCILE


def timeout_outcome_if_deadline_exceeded(provider: "ControllableFakeProvider", *, now, deadline):
    """Application-owned WORKER timeout decision (injectable deadline; no sleep). If the Provider has
    RECEIVED the request but has not returned a response by `deadline`, the Worker declares a timeout
    and emits an application `ProviderOutcome` with `failure_kind='timeout'` and
    `execution_certainty=UNKNOWN` — a timeout AFTER receipt is NOT proof of no execution. Returns
    None while the deadline has not passed or the request never reached the Provider (a distinct
    pre-receipt path). This produces the outcome that `decide_and_apply_recovery` then routes."""
    if now < deadline:
        return None
    if not provider.request_received.is_set():
        return None
    if provider.release_response.is_set():
        return None                            # a response is already available -> not a timeout
    return ProviderOutcome(failure_kind="timeout", execution_certainty=ExecutionCertainty.UNKNOWN,
                           provider_request_id=None, retry_after_seconds=None, safe_metadata={})
