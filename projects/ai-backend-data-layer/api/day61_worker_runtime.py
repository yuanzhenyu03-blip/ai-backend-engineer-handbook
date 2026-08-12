"""Day61 — the REAL authoritative-attempt composition (the production Worker path).

This is what the Celery task actually runs. It stitches the Day60 guarded claim to the Day61
external-operation path so a Job can only reach ``succeeded`` AFTER a real Provider HTTP call,
a real Object Storage PUT + HEAD verification, and a guarded DB completion under the CURRENT
lease token. There is NO "no Provider, straight to succeeded" production path.

Boundaries preserved from Day60:
  * The Relay is the ONLY broker publisher; Celery delivery is NOT execution authority.
  * The lease TOKEN written by the claim fences every external operation and the final
    completion — a stale Worker (token superseded) commits nothing to the successor's Job.
Durable-facts discipline:
  * tenant and the stable correlation/idempotency key come from PostgreSQL (``app.jobs`` +
    the durable Attempt), NEVER from the Celery message (which carries only identity + a
    diagnostic trace carrier).

Evidence tier: INTEGRATION_RUNTIME. The updating agent runs only ``py_compile`` + the pure /
static / real-loopback-HTTP tests; the full PostgreSQL + Redis/Celery + MinIO + OTel-Collector
matrix is NOT RUN (see the design/runbook). No secrets/URLs are hardcoded; the Provider URL is
the SEPARATE fake HTTP Provider, read from the environment by the caller.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from day60_delivery_runtime import claim_and_start_attempt
from day61_worker_completion import run_external_operation

# Outcomes for which the Job is NOT terminal-success and MUST NOT be re-committed by any outer
# layer. run_external_operation already performed (or safely skipped) the guarded transition;
# the composition returns its tag verbatim.
_NON_SUCCESS_OUTCOMES = frozenset({
    "attempt_mismatch_no_external_call",
    "lease_lost_no_external_call",
    "lease_lost_no_commit",
    "pending_reconciliation",
    "contract_failure",
    "provider_request_id_conflict",
    "artifact_conflict",
    "artifact_unverified",
})


def _load_job_facts(engine: Engine, job_id: str):
    """Read the tenant + request fingerprint from the durable ``app.jobs`` row. These are the
    ONLY trustworthy tenant/command facts — the Celery message is not trusted for them."""
    with engine.begin() as conn:
        return conn.execute(
            text("SELECT tenant_id, request_fingerprint FROM app.jobs WHERE job_id=:j"),
            {"j": job_id},
        ).first()


def stable_correlation_key(tenant_id: str, job_id: str, attempt_id: str) -> str:
    """OUR stable correlation/idempotency key: derived from durable facts, created BEFORE the
    Provider call, and identical for any retry of the SAME Attempt (so the fake Provider dedupes
    to ONE external operation). It is per-Attempt — a NEW Attempt is a NEW external operation,
    matching the per-Attempt Result Artifact key. Distinct from the Provider's own
    ``provider_request_id`` (minted on receipt)."""
    return f"corr:{tenant_id}:{job_id}:{attempt_id}"


def run_authoritative_attempt(
    engine: Engine,
    job_id: str,
    worker_id: str,
    *,
    provider_url: str,
    trace_carrier: Optional[dict] = None,
    store: Optional[object] = None,
    provider_name: str = "fake",
    mode: str = "success",
) -> str:
    """Claim the Job, then run the Day61 external operation under the SAME lease token, and
    return that outcome verbatim (never an outer success/overwrite).

    Steps:
      1) guarded ``queued->running`` claim + Attempt (Day60 ``claim_and_start_attempt``);
      2) load tenant + fingerprint from PostgreSQL durable facts (never the message);
      3) ``run_external_operation`` — Provider HTTP -> MinIO PUT/HEAD -> guarded completion,
         all fenced by the claim's lease token, spans continuing the propagated trace;
      4) return the external-operation outcome. Success comes ONLY from the guarded completion
         inside ``run_external_operation``; every non-success tag is surfaced unchanged."""
    claim = claim_and_start_attempt(engine, job_id, worker_id)
    if claim is None:
        return "not_claimed"  # duplicate/redelivery — the sweeper/reconciliation owns it
    lease_token, attempt_id = claim

    facts = _load_job_facts(engine, job_id)
    if facts is None or facts.tenant_id is None:
        # The Job/tenant vanished under our just-acquired lease (should be impossible while we
        # hold it). Do NOT fabricate success: leave the lease to EXPIRE so the sweeper recovers
        # it, and report a non-success tag.
        return "job_facts_missing"

    correlation_key = stable_correlation_key(str(facts.tenant_id), str(job_id), str(attempt_id))

    outcome = run_external_operation(
        engine,
        provider_url,
        str(facts.tenant_id),
        str(job_id),
        str(attempt_id),
        str(lease_token),
        correlation_key,
        mode=mode,
        store=store,
        provider_name=provider_name,
        trace_carrier=trace_carrier,
    )
    # run_external_operation owns the guarded transition; we surface its tag as-is. No outer
    # commit, no overwrite of a transition it already made.
    return outcome
