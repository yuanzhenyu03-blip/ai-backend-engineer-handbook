"""Day59 — pure acceptance-boundary logic (standard library only).

These helpers are the DECISION CORE of the Day59 acceptance boundary, deliberately
separated from the FastAPI/SQLAlchemy runtime composition in ``day59_runtime_app.py``
so the rules can be unit-tested WITHOUT a database, a web server, or Docker.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``test_day59_acceptance_logic.py``. They do NOT touch PostgreSQL and therefore prove
NOTHING about real UNIQUE/partial-index/transaction behavior — that is
``INTEGRATION_RUNTIME`` and belongs to a real Alembic + PostgreSQL run
(see the Day59 design/runbook).

No secrets, URLs, passwords, tokens, or tenant fixture values live in this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

# SHA-256 hex shape; mirrors the 0008 migration CHECK constraint exactly.
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def compute_request_fingerprint(
    tenant_id: str, idempotency_key: str, business_input: Mapping[str, Any]
) -> str:
    """Deterministic SHA-256 hex of the canonical acceptance request.

    The fingerprint distinguishes an EXACT retry (same tenant + key + logical input)
    from the same idempotency key reused for a DIFFERENT logical request. It is a
    stable digest, NOT a secret and NOT a security token. ``business_input`` is
    canonicalized with sorted keys so key ordering never changes the digest.
    """
    canonical = json.dumps(
        {
            "tenant_id": tenant_id,
            "idempotency_key": idempotency_key,
            "business_input": business_input,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyDecision(str, Enum):
    RETURN_ORIGINAL = "return_original"  # exact retry: same tenant/key/fingerprint
    CONFLICT_409 = "conflict_409"        # same tenant/key, DIFFERENT fingerprint
    ACCEPT_NEW = "accept_new"            # fresh key: run a new atomic acceptance


def classify_idempotency(
    existing_fingerprint: str | None, incoming_fingerprint: str
) -> IdempotencyDecision:
    """Decide acceptance purely from durable idempotency facts.

    Idempotency state is checked BEFORE revalidating mutable Document state: an exact
    retry returns the original accepted Job even if the referenced object later became
    unavailable. ``existing_fingerprint is None`` means no prior Job for this
    (tenant, idempotency_key) — a fresh acceptance.
    """
    if existing_fingerprint is None:
        return IdempotencyDecision.ACCEPT_NEW
    if existing_fingerprint == incoming_fingerprint:
        return IdempotencyDecision.RETURN_ORIGINAL
    return IdempotencyDecision.CONFLICT_409


class Readiness(str, Enum):
    READY = "ready"            # -> 200 on /readyz
    NOT_READY = "not_ready"    # -> 503 on /readyz


@dataclass(frozen=True)
class ReadinessResult:
    state: Readiness
    reason: str


def evaluate_readiness(
    db_reachable: bool, current_revision: str | None, expected_revision: str
) -> ReadinessResult:
    """Readiness = DB reachable AND schema at the expected Alembic revision.

    Liveness (``/livez``) only asks "is the process up?". Readiness additionally
    refuses traffic when the schema revision does not match what this API build
    expects — a ready process on the WRONG revision must be a 503 readiness FAILURE,
    never silent acceptance. A readiness failure is NOT a per-request 500.
    """
    if not db_reachable:
        return ReadinessResult(Readiness.NOT_READY, "database_unreachable")
    if current_revision != expected_revision:
        return ReadinessResult(
            Readiness.NOT_READY,
            f"revision_mismatch:expected={expected_revision}:actual={current_revision}",
        )
    return ReadinessResult(Readiness.READY, "ok")
