"""Day61 — pure Provider/Artifact/telemetry decision logic (standard library only).

The DECISION CORE for Day61's external-evidence path, separated from the real
HTTP/SQLAlchemy/Object-Storage runtime so the RULES are unit-testable WITHOUT PostgreSQL,
Redis/Celery, MinIO, an OTel Collector, or Docker.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``test_day61_provider_artifact_logic.py``. They prove the RULES only — NOT real HTTP,
real Object Storage HEAD/metadata, real PostgreSQL transactions/lease fencing, or a real
OTel exporter. That is ``INTEGRATION_RUNTIME`` (see the Day61 design/runbook; NOT RUN).

No secrets, URLs, passwords, tokens, or provider_request_id values live in this module.
Day61 does NOT call a real/paid model Provider; a separate deterministic fake HTTP Provider
proves adapter integration only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Optional

REDISPATCH_EVENT_TYPE = "job.redispatch_requested"


# ---------------------------------------------------------------------------
# 1) Provider outcome classification (timeout / invalid-200 / valid).
# ---------------------------------------------------------------------------
class ProviderOutcome(str, Enum):
    VALID = "valid"                       # HTTP 200 + response contract satisfied
    INVALID_BODY = "invalid_body"         # HTTP 200 but violates the response contract
    TIMEOUT = "timeout"                   # client timed out (receipt/execution UNKNOWN)


class ExecutionDecision(str, Enum):
    VERIFY_ARTIFACT_THEN_COMPLETE = "verify_artifact_then_complete"
    CONTRACT_FAILURE = "contract_failure"          # durable failed Attempt/Job facts, not success
    PENDING_RECONCILIATION = "pending_reconciliation"  # unknown timeout w/ durable dispatch marker
    UNSAFE_NO_MARKER = "unsafe_no_marker"          # timeout w/o a pre-call marker: never blind-retry


def classify_provider_outcome(
    outcome: ProviderOutcome, dispatch_marker_persisted: bool
) -> ExecutionDecision:
    """Map a Provider HTTP outcome to the next durable decision.

    * VALID       -> verify the Result Artifact, THEN guarded completion.
    * INVALID_BODY-> an explicit Provider CONTRACT FAILURE (durable failed facts +
      diagnostics), NOT success and normally NOT pending_reconciliation.
    * TIMEOUT     -> the Provider may still have received/executed the request; with a
      durable ``provider_dispatch_started_at`` marker go to PENDING_RECONCILIATION and NEVER
      blind-retry a potentially billable call. Without a marker the state is unsafe/unknown
      and still must NOT blind-retry (recover conservatively).
    """
    if outcome is ProviderOutcome.VALID:
        return ExecutionDecision.VERIFY_ARTIFACT_THEN_COMPLETE
    if outcome is ProviderOutcome.INVALID_BODY:
        return ExecutionDecision.CONTRACT_FAILURE
    # TIMEOUT
    if dispatch_marker_persisted:
        return ExecutionDecision.PENDING_RECONCILIATION
    return ExecutionDecision.UNSAFE_NO_MARKER


# ---------------------------------------------------------------------------
# 2) Deterministic per-Attempt Result Artifact key.
# ---------------------------------------------------------------------------
def result_artifact_key(tenant_id: str, job_id: str, attempt_id: str) -> str:
    """Deterministic per-ATTEMPT key so the SAME Attempt safely resumes against the SAME
    key, while DIFFERENT Attempts never overwrite each other. Per-Job alone is NOT enough."""
    return f"results/{tenant_id}/{job_id}/{attempt_id}/result.json"


# ---------------------------------------------------------------------------
# 3) Object Storage HEAD verification + non-overwrite conflict decision.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HeadMetadata:
    exists: bool
    checksum: Optional[str]
    size_bytes: Optional[int]
    content_type: Optional[str]


@dataclass(frozen=True)
class ExpectedArtifact:
    checksum: str
    size_bytes: int
    content_type: str


class ArtifactVerdict(str, Enum):
    VERIFIED = "verified"                 # HEAD matches expected -> reference + complete
    ABSENT = "absent"                     # no object -> (re)upload for the SAME attempt key
    CONFLICT = "conflict"                 # object exists but checksum/size/type mismatch -> reconcile


def verify_artifact_head(head: HeadMetadata, expected: ExpectedArtifact) -> ArtifactVerdict:
    """HEAD is an HTTP metadata-only read (unlike GET which fetches bytes). Upload success is
    NOT enough: verify existence + checksum + size + content type on the deterministic key.

    * absent            -> ABSENT (safe to write for this Attempt's key).
    * present + matches  -> VERIFIED (never re-upload; forward-repair the reference).
    * present + mismatch -> CONFLICT (do NOT overwrite or succeed; preserve evidence, reconcile).
    """
    if not head.exists:
        return ArtifactVerdict.ABSENT
    if (
        head.checksum == expected.checksum
        and head.size_bytes == expected.size_bytes
        and head.content_type == expected.content_type
    ):
        return ArtifactVerdict.VERIFIED
    return ArtifactVerdict.CONFLICT


# ---------------------------------------------------------------------------
# 4) Checkpoint ordering (pre-call marker, post-call request id).
# ---------------------------------------------------------------------------
class Checkpoint(str, Enum):
    PERSIST_DISPATCH_MARKER = "persist_dispatch_marker"   # BEFORE any Provider HTTP
    PROVIDER_HTTP_CALL = "provider_http_call"
    PERSIST_PROVIDER_REQUEST_ID = "persist_provider_request_id"  # as soon as returned
    VERIFY_ARTIFACT = "verify_artifact"
    GUARDED_COMPLETION = "guarded_completion"


def external_call_checkpoint_order() -> tuple[Checkpoint, ...]:
    """Persist ``provider_dispatch_started_at`` BEFORE the HTTP call (external work may
    happen after it; it is not success). Persist ``provider_request_id`` as soon as the
    Provider returns it and BEFORE the ordinary Artifact/success path; if that local
    checkpoint write cannot succeed, do not continue the success path (retry only the
    checkpoint, else recover/reconcile conservatively)."""
    return (
        Checkpoint.PERSIST_DISPATCH_MARKER,
        Checkpoint.PROVIDER_HTTP_CALL,
        Checkpoint.PERSIST_PROVIDER_REQUEST_ID,
        Checkpoint.VERIFY_ARTIFACT,
        Checkpoint.GUARDED_COMPLETION,
    )


# ---------------------------------------------------------------------------
# 5) Guarded completion gate (CURRENT matching lease token only).
# ---------------------------------------------------------------------------
def can_complete(job_status: str, db_lease_token: Optional[str], worker_lease_token: str) -> bool:
    """Final success is ONE guarded PostgreSQL transaction under the CURRENT matching
    ``lease_token``. A stale Worker (whose token was superseded) can upload an object but
    CANNOT complete the Job — its guarded UPDATE matches zero rows. Object existence, HTTP
    200, Celery ACK and traces alone are NOT success."""
    return job_status == "running" and db_lease_token is not None and db_lease_token == worker_lease_token


# ---------------------------------------------------------------------------
# 6) Telemetry safety — low-cardinality labels; protect provider_request_id.
# ---------------------------------------------------------------------------
_HIGH_CARDINALITY = frozenset({"job_id", "attempt_id", "provider_request_id"})


def metric_labels_allowed(labels: dict[str, str]) -> bool:
    """Prometheus-style metrics use LOW-cardinality labels (e.g. provider, outcome). Never
    label with job_id/attempt_id/provider_request_id — those belong in logs/traces."""
    return all(k not in _HIGH_CARDINALITY for k in labels)


def telemetry_safe_provider_request_ref(provider_request_id: str) -> str:
    """Do NOT put a full ``provider_request_id`` in logs/traces unconditionally (sensitive /
    capability-bearing). Emit a short, non-reversible hash prefix for correlation; PostgreSQL
    owns the complete protected value."""
    return "prid:" + hashlib.sha256(provider_request_id.encode("utf-8")).hexdigest()[:12]


def exporter_failure_must_not_fail_job() -> bool:
    """An OTel Collector/exporter failure must NOT roll back a valid committed Job or cause
    another Provider request; emit bounded exporter diagnostics/metrics and state the
    telemetry-evidence limitation. Business evidence is reconstructable from PostgreSQL,
    Object Storage and Provider identity."""
    return True
