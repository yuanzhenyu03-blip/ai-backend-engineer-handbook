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
    OverageRecord,
    compute_request_fingerprint,
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
        max_tokens=1000, now=NOW,
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
        max_tokens=1000, now=NOW,
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
            max_tokens=5000, now=NOW,
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
            max_tokens=5000, now=NOW,
            memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
            fail_after_reserve=True,
        )
    budget = store.budgets["tenant-a"]
    assert budget.reserved_tokens == 0 and budget.used_tokens == 0  # no ghost reservation
    assert store.jobs == {} and store.outbox == []                  # no unfunded Job/Outbox


def _admit_5000(store, ms):
    return admit_job(
        AuthenticatedIdentity("user-alice"), "tenant-a", idempotency_key="k1",
        max_tokens=5000, now=NOW,
        memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter(),
    )


def test_reconcile_unknown_holds_reservation_pending():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=None) is ReconcileState.RECONCILIATION_PENDING
    assert store.budgets["tenant-a"].reserved_tokens == 5000  # reservation retained
    assert jid not in store.overages


def test_reconcile_negative_actual_is_rejected_without_budget_change():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    with pytest.raises(ValueError):
        store.reconcile(jid, actual_tokens=-1)
    b = store.budgets["tenant-a"]
    assert b.reserved_tokens == 5000 and b.used_tokens == 0  # no budget fact changed


def test_reconcile_actual_below_reserved_settles_and_releases_remainder():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    assert b.used_tokens == 3000 and b.reserved_tokens == 0 and b.available == 7000
    assert jid not in store.overages


def test_reconcile_actual_equals_reserved_settles_exactly():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=5000) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    assert b.used_tokens == 5000 and b.reserved_tokens == 0 and b.available == 5000
    assert jid not in store.overages


def test_reconcile_actual_above_reserved_requires_overage_no_truncation_no_release():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    # Provider reported 6,000 actual against a 5,000 reservation.
    assert store.reconcile(jid, actual_tokens=6000) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED
    b = store.budgets["tenant-a"]
    assert b.reserved_tokens == 5000  # reservation NOT released as if settled
    assert b.used_tokens == 0         # no silently-truncated settle to used_tokens
    rec = store.overages[jid]         # exact observed usage preserved for controlled settlement
    assert rec.reserved_tokens == 5000 and rec.observed_actual_tokens == 6000
    assert store._observed_usage[jid] == 6000 and rec.reason


def test_reconcile_is_idempotent_for_repeat_same_actual_after_settled():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.SETTLED  # (a) first
    b = store.budgets["tenant-a"]
    before = (b.used_tokens, b.reserved_tokens, dict(store.overages))
    # (b) at-least-once redelivery of the SAME actual -> idempotent no-op, no budget change.
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.SETTLED
    assert (b.used_tokens, b.reserved_tokens, dict(store.overages)) == before
    assert b.used_tokens == 3000 and b.reserved_tokens == 0 and jid not in store.overages


def test_reconcile_different_actual_after_settled_is_conflict_not_resettle_or_overage():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.SETTLED
    # (c) a DIFFERENT actual after settlement -> conflict; no re-settle, no fake overage.
    assert store.reconcile(jid, actual_tokens=4000) is ReconcileState.RECONCILIATION_CONFLICT
    b = store.budgets["tenant-a"]
    assert b.used_tokens == 3000 and b.reserved_tokens == 0  # existing settlement fact preserved
    assert jid not in store.overages                          # no fabricated overage
    assert store._settled_actual[jid] == 3000                 # audit of the original settlement


def test_reconcile_after_overage_does_not_bypass_to_settled():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=6000) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED  # (d)
    # (e) further plain reconciles (repeat 6000, or a smaller 3000) never bypass overage to settle.
    assert store.reconcile(jid, actual_tokens=6000) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED
    b = store.budgets["tenant-a"]
    assert b.reserved_tokens == 5000 and b.used_tokens == 0   # no plain reconcile changed the facts
    assert store.overages[jid].observed_actual_tokens == 6000  # original evidence intact


def test_settle_overage_with_existing_headroom_settles_and_is_idempotent():
    # token_limit 10000 with a single 5000 reservation -> the 6000 actual fits within the
    # tenant's remaining budget headroom, so no extra credit is needed and available stays >= 0.
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    store.reconcile(jid, actual_tokens=6000)  # -> OVERAGE_RECONCILIATION_REQUIRED
    assert store.settle_overage(jid) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    assert b.used_tokens == 6000 and b.reserved_tokens == 0 and b.available == 4000  # never negative
    assert jid in store.overages                              # audit evidence retained
    # After controlled settlement, a plain reconcile is idempotent for the settled actual...
    assert store.reconcile(jid, actual_tokens=6000) is ReconcileState.SETTLED
    # ...and a different actual is a conflict, not a re-settle.
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.RECONCILIATION_CONFLICT
    assert b.used_tokens == 6000 and b.reserved_tokens == 0   # unchanged


def _admit_overage_at_hard_limit():
    # token_limit == the single reservation (5000) -> a 6000 actual is a true overage with
    # NO remaining budget headroom to absorb it.
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=5000))
    jid = _admit_5000(store, _memberships()).job.job_id
    assert store.reconcile(jid, actual_tokens=6000) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED
    return store, jid


def test_settle_overage_unfunded_does_not_bypass_hard_quota():
    store, jid = _admit_overage_at_hard_limit()
    # No approved extra credit -> settlement must NOT charge the overage and must NOT report SETTLED.
    assert store.settle_overage(jid) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED
    b = store.budgets["tenant-a"]
    assert b.available == 0 and b.available >= 0     # hard quota not bypassed; never negative
    assert b.used_tokens == 0 and b.reserved_tokens == 5000  # no charge, reservation retained
    assert store.overages[jid].observed_actual_tokens == 6000  # exact Provider usage preserved as audit fact
    assert jid not in store._overage_credits


def test_settle_overage_with_trusted_credit_settles_full_actual_and_keeps_audit():
    store, jid = _admit_overage_at_hard_limit()
    # A trusted accounting/ops-approved top-up (NOT a client field) covers the 1000 shortfall.
    assert store.settle_overage(jid, granted_extra_tokens=1000) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    assert b.token_limit == 6000 and b.used_tokens == 6000 and b.reserved_tokens == 0
    assert b.available == 0 and b.available >= 0     # full actual funded; never negative
    assert store.overages[jid].observed_actual_tokens == 6000  # overage audit retained
    assert store._overage_credits[jid] == 1000                 # granted credit retained (audit)


def test_settle_overage_partial_credit_stays_unfunded_until_enough():
    store, jid = _admit_overage_at_hard_limit()
    # 500 < the 1000 shortfall -> still unfunded, no mutation, no negative available.
    assert store.settle_overage(jid, granted_extra_tokens=500) is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED
    b = store.budgets["tenant-a"]
    assert b.token_limit == 5000 and b.used_tokens == 0 and b.reserved_tokens == 5000 and b.available == 0
    # A sufficient credit then settles exactly once.
    assert store.settle_overage(jid, granted_extra_tokens=1000) is ReconcileState.SETTLED
    assert b.token_limit == 6000 and b.used_tokens == 6000 and b.available == 0


def test_settle_overage_funded_is_idempotent_no_double_charge_or_credit():
    store, jid = _admit_overage_at_hard_limit()
    assert store.settle_overage(jid, granted_extra_tokens=1000) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    snapshot = (b.token_limit, b.used_tokens, b.reserved_tokens, store._overage_credits[jid])
    # A repeat controlled settlement is a no-op: no double credit, no double charge, no double release.
    assert store.settle_overage(jid, granted_extra_tokens=1000) is ReconcileState.SETTLED
    assert (b.token_limit, b.used_tokens, b.reserved_tokens, store._overage_credits[jid]) == snapshot
    # Plain reconcile stays idempotent for the settled actual; a different actual is a conflict.
    assert store.reconcile(jid, actual_tokens=6000) is ReconcileState.SETTLED
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.RECONCILIATION_CONFLICT
    assert (b.token_limit, b.used_tokens, b.reserved_tokens) == (6000, 6000, 0)


def test_settle_overage_negative_credit_is_rejected():
    store, jid = _admit_overage_at_hard_limit()
    with pytest.raises(ValueError):
        store.settle_overage(jid, granted_extra_tokens=-1)
    b = store.budgets["tenant-a"]
    assert b.token_limit == 5000 and b.used_tokens == 0 and b.reserved_tokens == 5000  # no change
    assert store._reconcile_status[jid] is ReconcileState.OVERAGE_RECONCILIATION_REQUIRED


def test_repeat_unknown_pending_callbacks_do_not_break_reservation():
    store = AdmissionStore(); store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    jid = _admit_5000(store, _memberships()).job.job_id
    # (f) repeated unknown/pending callbacks keep the reservation intact and stay pending.
    assert store.reconcile(jid, actual_tokens=None) is ReconcileState.RECONCILIATION_PENDING
    assert store.reconcile(jid, actual_tokens=None) is ReconcileState.RECONCILIATION_PENDING
    assert store.budgets["tenant-a"].reserved_tokens == 5000 and jid not in store.overages
    # A later known actual still settles correctly after pending redeliveries.
    assert store.reconcile(jid, actual_tokens=3000) is ReconcileState.SETTLED
    b = store.budgets["tenant-a"]
    assert b.used_tokens == 3000 and b.reserved_tokens == 0


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
            max_tokens=1000, now=NOW,
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
            max_tokens=10, now=NOW,
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
    kwargs = dict(idempotency_key="k1", max_tokens=5000, now=NOW,
                  memberships=ms, policy=PolicyStore(), store=store, limiter=_limiter())
    first = admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", **kwargs)
    second = admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", **kwargs)
    assert first.outcome is AdmissionOutcome.CREATED
    assert second.outcome is AdmissionOutcome.IDEMPOTENT_REPLAY
    assert second.job.job_id == first.job.job_id
    assert store.budgets["tenant-a"].reserved_tokens == 5000  # NOT 10000 — no double reserve


def test_same_key_changed_max_tokens_is_server_detected_conflict_with_no_new_facts():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    common = dict(idempotency_key="k1", now=NOW, memberships=ms, policy=PolicyStore(),
                  store=store, limiter=_limiter())
    admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", max_tokens=5000, **common)
    # Same key, changed behavior-relevant field -> the SERVER-computed fingerprint differs.
    conflict = admit_job(AuthenticatedIdentity("user-alice"), "tenant-a", max_tokens=1000, **common)
    assert conflict.outcome is AdmissionOutcome.FINGERPRINT_CONFLICT
    assert len(store.jobs) == 1 and store.budgets["tenant-a"].reserved_tokens == 5000  # no new facts


def test_server_computed_fingerprint_replay_and_conflict_matrix():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=1_000_000))
    ms = _memberships()
    common = dict(idempotency_key="K", now=NOW, memberships=ms, policy=PolicyStore(),
                  store=store, limiter=TokenBucketRateLimiter(capacity=50, refill_per_minute=0))
    a = AuthenticatedIdentity("user-alice")
    # First: key=K, max_tokens=5000 -> CREATED
    r1 = admit_job(a, "tenant-a", max_tokens=5000, document_id="doc-1", task_type="summarize", **common)
    assert r1.outcome is AdmissionOutcome.CREATED
    # Retry: identical canonical command -> IDEMPOTENT_REPLAY (no new reservation)
    r2 = admit_job(a, "tenant-a", max_tokens=5000, document_id="doc-1", task_type="summarize", **common)
    assert r2.outcome is AdmissionOutcome.IDEMPOTENT_REPLAY and r2.job.job_id == r1.job.job_id
    # Conflict: same key, changed max_tokens -> FINGERPRINT_CONFLICT
    assert admit_job(a, "tenant-a", max_tokens=1000, document_id="doc-1", task_type="summarize",
                     **common).outcome is AdmissionOutcome.FINGERPRINT_CONFLICT
    # Conflict: same key, changed document_id -> FINGERPRINT_CONFLICT
    assert admit_job(a, "tenant-a", max_tokens=5000, document_id="doc-2", task_type="summarize",
                     **common).outcome is AdmissionOutcome.FINGERPRINT_CONFLICT
    # Conflict: same key, changed task_type -> FINGERPRINT_CONFLICT
    assert admit_job(a, "tenant-a", max_tokens=5000, document_id="doc-1", task_type="translate",
                     **common).outcome is AdmissionOutcome.FINGERPRINT_CONFLICT
    # Only the original Job/reservation exists.
    assert len(store.jobs) == 1 and store.budgets["tenant-a"].reserved_tokens == 5000


def test_fingerprint_is_stable_sha256_not_client_supplied():
    fp1 = compute_request_fingerprint(max_tokens=5000, document_id="doc-1", task_type="summarize")
    fp2 = compute_request_fingerprint(max_tokens=5000, document_id="doc-1", task_type="summarize")
    fp3 = compute_request_fingerprint(max_tokens=5001, document_id="doc-1", task_type="summarize")
    assert fp1 == fp2 and fp1 != fp3
    assert len(fp1) == 64 and all(c in "0123456789abcdef" for c in fp1)  # SHA-256 hex


def test_idempotent_recovery_is_not_an_authz_bypass():
    store = AdmissionStore()
    store.set_budget(TenantBudget("tenant-a", token_limit=10000))
    ms = _memberships()
    kwargs = dict(idempotency_key="k1", max_tokens=5000, now=NOW,
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
