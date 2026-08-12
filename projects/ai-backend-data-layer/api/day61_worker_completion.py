"""Day61 — the guarded end-to-end Worker completion path (SQLAlchemy Core).

Wires the pure decisions + the real HTTP adapter + Object Storage + OTel to the durable
state machine, reusing the EXISTING Day60 lease TRIPLE (``lease_owner``/``lease_token``/
``lease_expires_at``). EVERY external action and business state change is fenced by the
CURRENT matching ``lease_token``:

    guarded-claim provider_dispatch_started_at  (attempt belongs to job + running + lease_token)
      -> attempt not owned: attempt_mismatch_no_external_call ; lease lost: lease_lost_no_external_call
         (in every non-claimed case: NO Provider call, NO request_id, NO state change)
      -> call the Provider over real HTTP (adapter)
      -> persist provider_request_id (NULL->set / same->idempotent / diff->conflict), lease-fenced
      -> compute Artifact metadata from the ACTUAL result bytes; HEAD-verify on the per-Attempt key
      -> ONE guarded completion transaction under the CURRENT lease_token

Timeout with the durable marker -> ``pending_reconciliation``. Invalid/inconsistent 200 body ->
contract-failure facts. A stale Worker cannot mark the successor's Job pending/failed/succeeded.

Evidence tier: INTEGRATION_RUNTIME. The updating agent ran only ``py_compile`` + the pure-logic
and real-loopback-HTTP tests; the full PostgreSQL/MinIO/OTel-Collector matrix is NOT RUN (see the
design/runbook). No secrets hardcoded. Day61 never calls a real/paid model Provider.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from day61_artifact_store import ArtifactRef, S3ArtifactStore
from day61_provider_adapter import AdapterResult, call_provider
from day61_provider_artifact_logic import (
    ArtifactVerdict,
    ExecutionDecision,
    ProviderOutcome,
    RequestIdDecision,
    canonical_result_bytes,
    classify_provider_outcome,
    classify_request_id_write,
    compute_artifact_metadata,
    provider_declaration_matches_bytes,
)
from day61_telemetry import operation_span, record_provider_outcome

# --- lease-guard clause shared by every state-changing statement (Day60 fencing). ---
_LEASE_GUARD = "job_status='running' AND lease_token=:tok"


def _claim_dispatch_marker(engine: Engine, job_id: str, attempt_id: str, lease_token: str) -> str:
    """Guarded PRE-CALL checkpoint that ALSO verifies Attempt ownership (P1-4). In ONE short
    transaction it confirms, BEFORE any Provider HTTP, that:

      * the Attempt exists AND belongs to THIS Job (``attempt_id`` -> ``job_id``);
      * the Job is ``running`` AND the DB holds THIS Worker's ``lease_token``.

    Returns:
      * ``"claimed"``          -> ownership + lease verified and the dispatch marker set;
      * ``"attempt_mismatch"`` -> the Attempt is missing or belongs to another Job;
      * ``"lease_lost"``       -> the Attempt belongs to the Job but the Job is no longer
        running under this token.

    On any non-``claimed`` result NO marker is written, NO Provider call is made, NO
    provider_request_id is written, and NO Job state changes — a stale or mis-targeted Worker
    stops here."""
    with engine.begin() as conn:
        owned = conn.execute(
            text(
                "SELECT a.attempt_id FROM app.job_attempts a "
                "JOIN app.jobs j ON j.job_id=a.job_id "
                f"WHERE a.attempt_id=:a AND a.job_id=:j AND {_LEASE_GUARD} FOR UPDATE OF a"
            ),
            {"a": attempt_id, "j": job_id, "tok": lease_token},
        ).first()
        if owned is None:
            # Distinguish "Attempt does not belong to this Job" from "lease lost", still in-tx.
            belongs = conn.execute(
                text("SELECT 1 FROM app.job_attempts WHERE attempt_id=:a AND job_id=:j"),
                {"a": attempt_id, "j": job_id},
            ).first()
            return "lease_lost" if belongs is not None else "attempt_mismatch"
        rows = conn.execute(
            text(
                "UPDATE app.jobs SET provider_dispatch_started_at=coalesce(provider_dispatch_started_at, now()) "
                f"WHERE job_id=:j AND {_LEASE_GUARD}"
            ),
            {"j": job_id, "tok": lease_token},
        ).rowcount
        if rows != 1:
            return "lease_lost"
    return "claimed"


def _persist_provider_request_id(
    engine: Engine, job_id: str, attempt_id: str, lease_token: str, provider_request_id: str
) -> str:
    """Lease-fenced, IMMUTABLE persistence of the external-operation identity:
    NULL->set, same->idempotent success, DIFFERENT->conflict (never overwrite). The Attempt
    must belong to this Job, which must still be running under THIS lease token."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT a.provider_request_id FROM app.job_attempts a "
                "JOIN app.jobs j ON j.job_id=a.job_id "
                f"WHERE a.attempt_id=:a AND a.job_id=:j AND {_LEASE_GUARD} FOR UPDATE OF a"
            ),
            {"a": attempt_id, "j": job_id, "tok": lease_token},
        ).first()
        if row is None:
            return "lease_lost"
        decision = classify_request_id_write(row.provider_request_id, provider_request_id)
        if decision is RequestIdDecision.CONFLICT:
            return "conflict"
        if decision is RequestIdDecision.IDEMPOTENT:
            return "idempotent"
        conn.execute(
            text(
                "UPDATE app.job_attempts SET provider_request_id=:p "
                "WHERE attempt_id=:a AND provider_request_id IS NULL"
            ),
            {"p": provider_request_id, "a": attempt_id},
        )
    return "set"


def run_external_operation(
    engine: Engine,
    provider_url: str,
    tenant_id: str,
    job_id: str,
    attempt_id: str,
    lease_token: str,
    correlation_key: str,
    mode: str = "success",
    store: Optional[object] = None,
    provider_name: str = "fake",
) -> str:
    """Execute one external operation end to end. Returns an outcome tag. INTEGRATION_RUNTIME."""
    store = store or S3ArtifactStore()

    # Fence + verify Attempt ownership BEFORE any external call: a stale OR mis-targeted
    # Worker never even reaches the Provider (no marker, no call, no request_id, no state).
    claim = _claim_dispatch_marker(engine, job_id, attempt_id, lease_token)
    if claim == "attempt_mismatch":
        record_provider_outcome(provider_name, "attempt_mismatch", "none")
        return "attempt_mismatch_no_external_call"
    if claim != "claimed":
        record_provider_outcome(provider_name, "lease_lost", "none")
        return "lease_lost_no_external_call"

    with operation_span("provider.http_call", job_id, attempt_id):
        result: AdapterResult = call_provider(provider_url, correlation_key, mode)

    decision = classify_provider_outcome(result.outcome, dispatch_marker_persisted=True)
    if decision is ExecutionDecision.PENDING_RECONCILIATION:
        record_provider_outcome(provider_name, "timeout", "none")
        _to_pending_reconciliation(engine, job_id, attempt_id, lease_token, "provider_timeout")
        return "pending_reconciliation"
    if decision is ExecutionDecision.CONTRACT_FAILURE:
        record_provider_outcome(provider_name, "invalid_body", "none")
        _record_contract_failure(engine, job_id, attempt_id, lease_token)
        return "contract_failure"
    if decision is ExecutionDecision.UNSAFE_NO_MARKER:  # defensive
        _to_pending_reconciliation(engine, job_id, attempt_id, lease_token, "unknown_no_marker")
        return "pending_reconciliation"

    # VALID: cross-check the Provider's DECLARED metadata against the ACTUAL result bytes.
    if not provider_declaration_matches_bytes(
        result.declared_checksum, result.declared_size_bytes, result.declared_content_type, result.result_data
    ):
        record_provider_outcome(provider_name, "invalid_body", "declared_mismatch")
        _record_contract_failure(engine, job_id, attempt_id, lease_token)
        return "contract_failure"

    # Persist the external identity BEFORE the Artifact/success path (lease-fenced, immutable).
    assert result.provider_request_id is not None
    rid = _persist_provider_request_id(engine, job_id, attempt_id, lease_token, result.provider_request_id)
    if rid == "lease_lost":
        return "lease_lost_no_commit"
    if rid == "conflict":
        _to_pending_reconciliation(engine, job_id, attempt_id, lease_token, "provider_request_id_conflict")
        return "provider_request_id_conflict"

    # Compute metadata from the ACTUAL bytes we will store (source of truth) — never guessed.
    result_bytes = canonical_result_bytes(result.result_data)
    expected = compute_artifact_metadata(result.result_data)
    key = store.key_for(tenant_id, job_id, attempt_id)
    with operation_span("storage.put_verify", job_id, attempt_id, result.provider_request_id):
        verdict = store.put_if_safe(key, result_bytes, expected.content_type, expected)
    if verdict is ArtifactVerdict.CONFLICT:
        record_provider_outcome(provider_name, "valid", "conflict")
        _to_pending_reconciliation(engine, job_id, attempt_id, lease_token, "artifact_conflict")
        return "artifact_conflict"
    if verdict is not ArtifactVerdict.VERIFIED:
        record_provider_outcome(provider_name, "valid", "unverified")
        _to_pending_reconciliation(engine, job_id, attempt_id, lease_token, "artifact_unverified")
        return "artifact_unverified"

    with operation_span("db.guarded_completion", job_id, attempt_id, result.provider_request_id):
        outcome = _guarded_completion(
            engine, tenant_id, job_id, attempt_id, lease_token,
            ArtifactRef(key, expected.checksum, expected.size_bytes, expected.content_type),
        )
    record_provider_outcome(provider_name, "valid", "verified" if outcome == "succeeded" else "lease_lost")
    return outcome


def _guarded_completion(engine, tenant_id, job_id, attempt_id, lease_token, ref: ArtifactRef) -> str:
    """ONE guarded transaction under the CURRENT matching lease_token: Result Artifact
    reference, Attempt finished, success Event, Job running->succeeded, lease cleared."""
    with engine.begin() as conn:
        completed = conn.execute(
            text(
                "UPDATE app.jobs SET job_status='succeeded', finished_at=now(), attempt_count=attempt_count+1, "
                "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
                f"WHERE job_id=:j AND {_LEASE_GUARD} RETURNING job_id"
            ),
            {"j": job_id, "tok": lease_token},
        ).first()
        if completed is None:
            return "lease_lost_no_commit"  # stale Worker: object retained for reconciliation
        conn.execute(
            text(
                "INSERT INTO app.result_artifacts (attempt_id, artifact_type, object_key, "
                "content_type, size_bytes, checksum) "
                "VALUES (:a, 'result', :k, :ct, :sz, :cs) ON CONFLICT (attempt_id, object_key) DO NOTHING"
            ),
            {"a": attempt_id, "k": ref.key, "ct": ref.content_type, "sz": ref.size_bytes, "cs": ref.checksum},
        )
        conn.execute(text("UPDATE app.job_attempts SET finished_at=now() WHERE attempt_id=:a"), {"a": attempt_id})
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor) "
                "VALUES (:j, :a, 'attempt.succeeded', 'running', 'succeeded', 'worker')"
            ),
            {"j": job_id, "a": attempt_id},
        )
    return "succeeded"


def _to_pending_reconciliation(engine, job_id, attempt_id, lease_token, reason: str) -> str:
    """Lease-fenced. A stale Worker changes ZERO rows and CANNOT move the successor's Job."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(f"UPDATE app.jobs SET job_status='pending_reconciliation' WHERE job_id=:j AND {_LEASE_GUARD}"),
            {"j": job_id, "tok": lease_token},
        ).rowcount
        if rows == 0:
            return "lease_lost_no_state_change"
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor, metadata) "
                "VALUES (:j, :a, 'provider.reconcile', 'running', 'pending_reconciliation', 'worker', "
                "jsonb_build_object('reason', :r))"
            ),
            {"j": job_id, "a": attempt_id, "r": reason},
        )
    return "pending_reconciliation"


def _record_contract_failure(engine, job_id, attempt_id, lease_token) -> str:
    """Lease-fenced. A stale Worker cannot mark the successor's Job failed."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "UPDATE app.jobs SET job_status='failed', finished_at=now(), "
                "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
                f"WHERE job_id=:j AND {_LEASE_GUARD}"
            ),
            {"j": job_id, "tok": lease_token},
        ).rowcount
        if rows == 0:
            return "lease_lost_no_state_change"
        conn.execute(
            text("UPDATE app.job_attempts SET finished_at=now(), error_code='provider_contract' WHERE attempt_id=:a AND job_id=:j"),
            {"a": attempt_id, "j": job_id},
        )
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor) "
                "VALUES (:j, :a, 'provider.contract_failure', 'running', 'failed', 'worker')"
            ),
            {"j": job_id, "a": attempt_id},
        )
    return "contract_failure"
