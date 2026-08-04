"""Day52 — tests for Authorization, Tenant Isolation, Quotas and API Security.

EVIDENCE LABEL: these run an IN-MEMORY model of the admission boundary — Membership/role
authorization, tenant/owner-scoped reads, a guarded quota reservation modeling
`UPDATE ... WHERE available >= amount RETURNING`, atomic Reservation+Job+Outbox with
rollback, a fail-closed rate limiter, idempotent recovery, and guarded policy repair. This
is APPLICATION CONTROL FLOW only. NOT real PostgreSQL (constraints/tx/isolation/RETURNING/
RLS), NOT real Redis (distributed atomics/TTL/failover), NOT real FastAPI/proxy/browser
(Dependency/CORS/cookie/CSRF/routes), NOT Provider/Worker/integration/production. No real
JWT, Provider key, password, prompt, or user data is used.
"""

import threading
from datetime import datetime, timedelta, timezone

import pytest

from day52_authorization_tenant_quota_security import (
    AdmissionOutcome,
    AdmissionStore,
    AuthenticatedIdentity,
    AuthorizationError,
    AuthorizedTenantContext,
    CancelIntent,
    CancelIntentLedger,
    CancelIntentState,
    JobRepository,
    LimiterUnavailable,
    MembershipDirectory,
    NotFoundError,
    PolicyStore,
    ReconcileState,
    RepairOutcome,
    ReservationRollback,
    TenantBudget,
    TenantMembership,
    TokenBucketRateLimiter,
    admit_job,
    authorize,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


def _memberships():
    d = MembershipDirectory()
    d.add(TenantMembership("user-alice", "tenant-a", "member"))
    d.add(TenantMembership("user-bob", "tenant-a", "operator"))
    d.add(TenantMembership("user-carol", "tenant-b", "admin"))
    return d


def _limiter():
    return TokenBucketRateLimiter(capacity=20, refill_per_minute=100)


# ===========================================================================
# 1. Authentication vs authorization; Membership/action authority
# ===========================================================================
def test_client_tenant_is_a_selector_not_authority():
    # Alice is a member of tenant-a only. She cannot gain authority by selecting tenant-b.
    ms = _memberships()
    identity = AuthenticatedIdentity("user-alice")
    ctx = authorize(identity, "tenant-a", "job.create", memberships=ms, policy=PolicyStore())
    assert ctx.tenant_id == "tenant-a" and "job.create" in ctx.permissions
    with pytest.raises(AuthorizationError):
        authorize(identity, "tenant-b", "job.create", memberships=ms, policy=PolicyStore())


def test_missing_action_is_generic_forbidden():
    ms = _memberships()
    identity = AuthenticatedIdentity("user-alice")  # member role: no job.cancel
    with pytest.raises(AuthorizationError):
        authorize(identity, "tenant-a", "job.cancel", memberships=ms, policy=PolicyStore())


def test_membership_removal_revokes_authority_immediately():
    ms = _memberships()
    identity = AuthenticatedIdentity("user-bob")
    authorize(identity, "tenant-a", "job.cancel", memberships=ms, policy=PolicyStore())  # ok now
    ms.remove_membership("user-bob", "tenant-a")  # role downgrade / removal is a fact change
    with pytest.raises(AuthorizationError):
        authorize(identity, "tenant-a", "job.cancel", memberships=ms, policy=PolicyStore())


# ===========================================================================
# 2. Tenant- and owner-scoped resource reads (IDOR/BOLA safe)
# ===========================================================================
def test_cross_tenant_read_returns_not_found_no_oracle():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=100000))
    ms = _memberships()
    created = admit_job(
        AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key="k1",
        request_fingerprint="fp1", max_tokens=1000, now=NOW,
        memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
    )
    job_id = created.job.job_id
    repo = JobRepository(store.jobs)
    # Carol (tenant-b admin) cannot see tenant-a's Job — a public 404, not a 403 oracle.
    carol_ctx = authorize(AuthenticatedIdentity("user-carol"), "tenant-b", "job.read_all",
                          memberships=ms, policy=PolicyStore())
    with pytest.raises(NotFoundError):
        repo.read_job(carol_ctx, job_id)


def test_read_own_requires_ownership_not_just_same_tenant():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=100000))
    ms = _memberships()
    created = admit_job(
        AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key="k1",
        request_fingerprint="fp1", max_tokens=1000, now=NOW,
        memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
    )
    repo = JobRepository(store.jobs)
    # Alice (owner, member) can read her own Job.
    alice_ctx = authorize(AuthenticatedIdentity("user-alice"), "tenant-a", "job.read_own",
                          memberships=ms, policy=PolicyStore())
    assert repo.read_job(alice_ctx, created.job.job_id).job_id == created.job.job_id
    # A same-tenant colleague with only read_own cannot read Alice's Job.
    ms.add(TenantMembership("user-dan", "tenant-a", "member"))
    dan_ctx = authorize(AuthenticatedIdentity("user-dan"), "tenant-a", "job.read_own",
                        memberships=ms, policy=PolicyStore())
    with pytest.raises(NotFoundError):
        repo.read_job(dan_ctx, created.job.job_id)


# ===========================================================================
# 3. Durable quota: guarded reservation, concurrency, rollback, reconcile
# ===========================================================================
def test_two_concurrent_requests_only_one_reserves_when_budget_is_tight():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=8000))  # only 8,000 remaining
    ms = _memberships()
    results, barrier = [], threading.Barrier(2)

    def attempt(key):
        barrier.wait()
        results.append(admit_job(
            AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key=key,
            request_fingerprint="fp", max_tokens=5000, now=NOW,
            memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
        ))

    t1 = threading.Thread(target=attempt, args=("k1",))
    t2 = threading.Thread(target=attempt, args=("k2",))
    t1.start(); t2.start(); t1.join(); t2.join()
    outcomes = sorted(r.outcome for r in results)
    assert outcomes == sorted([AdmissionOutcome.CREATED, AdmissionOutcome.QUOTA_EXCEEDED])
    budget = store.budgets["tenant-a"]
    assert budget.reserved_tokens == 5000 and budget.available == 3000  # exactly one reservation


def test_rollback_after_reservation_leaves_no_ghost_reservation_or_job():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    with pytest.raises(ReservationRollback):
        admit_job(
            AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key="k1",
            request_fingerprint="fp1", max_tokens=5000, now=NOW,
            memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
            fail_after_reserve=True,
        )
    budget = store.budgets["tenant-a"]
    assert budget.reserved_tokens == 0 and budget.used_tokens == 0  # no ghost reservation
    assert store.jobs == {} and store.outbox == []                  # no unfunded Job/Outbox


def test_reconcile_settles_actual_usage_and_holds_on_unknown():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    created = admit_job(
        AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key="k1",
        request_fingerprint="fp1", max_tokens=5000, now=NOW,
        memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
    )
    jid = created.job.job_id
    # Unknown Provider outcome (timeout) -> keep the reservation, preserve evidence.
    assert store.reconcile(jid, actual_tokens=None) is ReconcileState.RECONCILIATION_PENDING
    assert store.budgets["tenant-a"].reserved_tokens == 5000
    # Known usage (3,000 of the 5,000 reserved) -> settle used, release the rest.
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    assert b.used_tokens == 3000 and b.reserved_tokens == 0 and b.available == 7000


# ===========================================================================
# 4. Rate limiting: fail-closed outage; healthy-limiter 429
# ===========================================================================
def test_limiter_outage_on_paid_path_fails_closed():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    down = TokenBucketRateLimiter(capacity=20, refill_per_minute=100, available=False)
    with pytest.raises(LimiterUnavailable):  # fail-closed -> 503, never a 429
        admit_job(
            AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key="k1",
            request_fingerprint="fp1", max_tokens=1000, now=NOW,
            memberships=ms, policy=PolicyStore(), store=store, limiter=down,
        )
    assert store.jobs == {}  # nothing admitted


def test_healthy_limiter_exhaustion_returns_rate_limited():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10_000_000))
    ms = _memberships()
    limiter = TokenBucketRateLimiter(capacity=2, refill_per_minute=0)  # 2 tokens, no refill
    outcomes = []
    for i in range(4):
        r = admit_job(
            AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key=f"k{i}",
            request_fingerprint="fp", max_tokens=10, now=NOW,
            memberships=ms, policy=PolicyStore(), store=store, limiter=limiter,
        )
        outcomes.append(r.outcome)
    assert outcomes[:2] == [AdmissionOutcome.CREATED, AdmissionOutcome.CREATED]
    assert AdmissionOutcome.RATE_LIMITED in outcomes[2:]


# ===========================================================================
# 5. Idempotency ordering (recovery has no second reservation; not an authz bypass)
# ===========================================================================
def test_same_command_replay_returns_original_job_without_second_reservation():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    kwargs = dict(idempotency_key="k1", request_fingerprint="fp1", max_tokens=5000, now=NOW,
                  memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter())
    first = admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", **kwargs)
    second = admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", **kwargs)
    assert first.outcome is AdmissionOutcome.CREATED
    assert second.outcome is AdmissionOutcome.IDEMPOTENT_REPLAY
    assert second.job.job_id == first.job.job_id
    assert store.budgets["tenant-a"].reserved_tokens == 5000  # NOT 10000 — no double reserve


def test_same_key_changed_fingerprint_is_conflict_with_no_new_facts():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    base = dict(idempotency_key="k1", max_tokens=5000, now=NOW,
                memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter())
    admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", request_fingerprint="fp1", **base)
    conflict = admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", request_fingerprint="fp2", **base)
    assert conflict.outcome is AdmissionOutcome.FINGERPRINT_CONFLICT
    assert len(store.jobs) == 1 and store.budgets["tenant-a"].reserved_tokens == 5000


def test_idempotent_recovery_is_not_an_authz_bypass():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    kwargs = dict(idempotency_key="k1", request_fingerprint="fp1", max_tokens=5000, now=NOW,
                  policy=PolicyStore(), store=store, limiter=_limiter())
    admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", memberships=ms, **kwargs)
    ms.remove_membership("user-alice", "tenant-a")  # membership removed after the original create
    with pytest.raises(AuthorizationError):  # old-key recovery is blocked at authorization
        admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", memberships=ms, **kwargs)


# ===========================================================================
# 6. Production exercise: erroneous cancel grant -> contain, classify, guarded repair
# ===========================================================================
def test_policy_rollback_disables_bad_cancel_grant_without_stopping_safe_creation():
    ms = _memberships()
    policy = PolicyStore()
    policy.grant("member", "job.cancel")  # BAD release: members should not cancel
    alice = AuthenticatedIdentity("user-alice")
    authorize(alice, "tenant-a", "job.cancel", memberships=ms, policy=policy)  # wrongly allowed
    policy.revoke("member", "job.cancel")  # contain: roll back only the erroneous grant
    with pytest.raises(AuthorizationError):
        authorize(alice, "tenant-a", "job.cancel", memberships=ms, policy=policy)
    # Safe Job creation for members is unaffected by the rollback.
    authorize(alice, "tenant-a", "job.create", memberships=ms, policy=policy)


def test_guarded_repair_of_bad_intent_stops_and_reconciles_on_fact_change():
    ledger = CancelIntentLedger()
    ledger.add(CancelIntent("i1", "tenant-a", "job-1", "user-alice", policy_version=7))
    ledger.add(CancelIntent("i2", "tenant-a", "job-2", "user-alice", policy_version=7))
    # A legitimate later cancel already executed i2 -> its fact changed.
    ledger.intents["i2"].state = CancelIntentState.EXECUTED
    # Guarded repair of the still-pending bad intent succeeds and retains the record.
    assert ledger.repair_bad_intent("i1", expected_policy_version=7) is RepairOutcome.REPAIRED
    assert ledger.intents["i1"].state is CancelIntentState.INVALIDATED
    assert "i1" in ledger.intents  # never deleted — audit evidence
    # Zero-row guarded repair (fact changed) -> stop automatic repair and reconcile.
    assert ledger.repair_bad_intent("i2", expected_policy_version=7) is RepairOutcome.RECONCILE
    assert ledger.intents["i2"].state is CancelIntentState.EXECUTED  # legitimate cancel not overwritten
    # A wrong policy_version is also a fact mismatch -> reconcile, no change.
    assert ledger.repair_bad_intent("i1", expected_policy_version=999) is RepairOutcome.RECONCILE


# ===========================================================================
# 7. Evidence label present (honesty)
# ===========================================================================
def test_evidence_label_is_in_memory_control_flow_not_runtime():
    import day52_authorization_tenant_quota_security as m
    doc = m.__doc__ or ""
    assert "IN-MEMORY CONTROL-FLOW" in doc
    assert "NOT RUN" in doc and "real PostgreSQL" in doc and "real Redis" in doc
