"""Day61 — the guarded end-to-end Worker completion path (SQLAlchemy Core).

Wires the pure decisions + the real HTTP adapter + Object Storage to the durable state
machine, reusing the EXISTING Day60 lease TRIPLE (``lease_owner``/``lease_token``/
``lease_expires_at``) and its recovery semantics. Order (see the pure
``external_call_checkpoint_order``):

    persist provider_dispatch_started_at  (BEFORE the HTTP call)
      -> call the Provider over real HTTP (adapter)
      -> persist provider_request_id      (as soon as returned; before Artifact/success)
      -> verify the Result Artifact by HEAD on the deterministic per-Attempt key
      -> ONE guarded completion transaction under the CURRENT matching lease_token

Timeout with a durable marker -> ``pending_reconciliation`` (never a blind second call).
Invalid 200 body -> durable contract-failure facts. A stale Worker's guarded UPDATE matches
zero rows and cannot complete. Object existence / HTTP 200 / ACK / traces are NOT success.

Evidence tier: INTEGRATION_RUNTIME. Running it needs real PostgreSQL (Day60 head 0012) +
Object Storage + the fake Provider process. The updating agent ran only ``py_compile`` +
the pure-logic and real-loopback-HTTP tests — the full PostgreSQL/MinIO/OTel integration is
NOT RUN (see the design/runbook's Required integration rerun matrix). No secrets hardcoded.
Day61 never calls a real/paid model Provider.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from day61_artifact_store import ArtifactRef, S3ArtifactStore
from day61_provider_adapter import AdapterResult, call_provider
from day61_provider_artifact_logic import (
    ArtifactVerdict,
    ExecutionDecision,
    ExpectedArtifact,
    ProviderOutcome,
    can_complete,
    classify_provider_outcome,
)


def _now():
    return datetime.now(timezone.utc)


def _persist_dispatch_marker(engine: Engine, job_id: str) -> None:
    # Conservative PRE-CALL checkpoint: external work may happen after it; NOT success.
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE app.jobs SET provider_dispatch_started_at=coalesce(provider_dispatch_started_at, now()) "
                "WHERE job_id=:j AND job_status='running'"
            ),
            {"j": job_id},
        )


def _persist_provider_request_id(engine: Engine, attempt_id: str, provider_request_id: str) -> bool:
    # POST-CALL durable external-operation identity. If this cannot persist, do NOT continue
    # the success path (retry only this checkpoint; else reconcile conservatively).
    with engine.begin() as conn:
        rows = conn.execute(
            text("UPDATE app.job_attempts SET provider_request_id=:p WHERE attempt_id=:a"),
            {"p": provider_request_id, "a": attempt_id},
        ).rowcount
    return rows == 1


def run_external_operation(
    engine: Engine,
    provider_url: str,
    tenant_id: str,
    job_id: str,
    attempt_id: str,
    lease_token: str,
    correlation_key: str,
    mode: str = "success",
    store: Optional[S3ArtifactStore] = None,
) -> str:
    """Execute one external operation end to end. Returns an outcome tag. This is the real
    runtime; it is exercised in INTEGRATION_RUNTIME (NOT RUN here)."""
    store = store or S3ArtifactStore()

    _persist_dispatch_marker(engine, job_id)
    result: AdapterResult = call_provider(provider_url, correlation_key, mode)

    decision = classify_provider_outcome(
        result.outcome, dispatch_marker_persisted=True
    )
    if decision is ExecutionDecision.PENDING_RECONCILIATION:
        _to_pending_reconciliation(engine, job_id, attempt_id, reason="provider_timeout")
        return "pending_reconciliation"
    if decision is ExecutionDecision.CONTRACT_FAILURE:
        _record_contract_failure(engine, job_id, attempt_id)
        return "contract_failure"
    if decision is ExecutionDecision.UNSAFE_NO_MARKER:  # defensive; marker was persisted above
        _to_pending_reconciliation(engine, job_id, attempt_id, reason="unknown_no_marker")
        return "pending_reconciliation"

    # VALID -> persist the external identity BEFORE the Artifact/success path.
    assert result.provider_request_id is not None
    if not _persist_provider_request_id(engine, attempt_id, result.provider_request_id):
        _to_pending_reconciliation(engine, job_id, attempt_id, reason="request_id_persist_failed")
        return "pending_reconciliation"

    key = store.key_for(tenant_id, job_id, attempt_id)
    expected = ExpectedArtifact(result.checksum, result.size_bytes, result.content_type)
    verdict = store.put_if_safe(key, b"{}", result.content_type, expected)
    if verdict is ArtifactVerdict.CONFLICT:
        _to_pending_reconciliation(engine, job_id, attempt_id, reason="artifact_conflict")
        return "artifact_conflict"
    if verdict is not ArtifactVerdict.VERIFIED:
        _to_pending_reconciliation(engine, job_id, attempt_id, reason="artifact_unverified")
        return "artifact_unverified"

    return _guarded_completion(
        engine, tenant_id, job_id, attempt_id, lease_token,
        ArtifactRef(key, expected.checksum, expected.size_bytes, expected.content_type),
    )


def _guarded_completion(engine, tenant_id, job_id, attempt_id, lease_token, ref: ArtifactRef) -> str:
    """ONE guarded transaction under the CURRENT matching lease_token: Result Artifact
    reference, Attempt finished, success Event, Job running->succeeded, lease cleared."""
    with engine.begin() as conn:
        job = conn.execute(
            text("SELECT job_status, lease_token FROM app.jobs WHERE job_id=:j FOR UPDATE"),
            {"j": job_id},
        ).first()
        if job is None or not can_complete(
            job.job_status, str(job.lease_token) if job.lease_token else None, lease_token
        ):
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
        conn.execute(
            text(
                "UPDATE app.jobs SET job_status='succeeded', finished_at=now(), attempt_count=attempt_count+1, "
                "lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
                "WHERE job_id=:j AND job_status='running' AND lease_token=:tok"
            ),
            {"j": job_id, "tok": lease_token},
        )
    return "succeeded"


def _to_pending_reconciliation(engine, job_id, attempt_id, reason: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE app.jobs SET job_status='pending_reconciliation' WHERE job_id=:j AND job_status='running'"),
            {"j": job_id},
        )
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor, metadata) "
                "VALUES (:j, :a, 'provider.reconcile', 'running', 'pending_reconciliation', 'worker', "
                "jsonb_build_object('reason', :r))"
            ),
            {"j": job_id, "a": attempt_id, "r": reason},
        )


def _record_contract_failure(engine, job_id, attempt_id) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE app.job_attempts SET finished_at=now(), error_code='provider_contract' WHERE attempt_id=:a"), {"a": attempt_id})
        conn.execute(
            text(
                "INSERT INTO app.job_events (job_id, attempt_id, event_type, from_status, to_status, actor) "
                "VALUES (:j, :a, 'provider.contract_failure', 'running', 'failed', 'worker')"
            ),
            {"j": job_id, "a": attempt_id},
        )
        conn.execute(text("UPDATE app.jobs SET job_status='failed', finished_at=now(), lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL WHERE job_id=:j AND job_status='running'"), {"j": job_id})
