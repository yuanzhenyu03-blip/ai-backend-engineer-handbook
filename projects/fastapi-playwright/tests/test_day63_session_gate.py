"""Day63 — EXECUTED_LOCAL_RUNTIME tests for the pure Browser-Session authorization/claim core.

Standard-library only; no browser, no PostgreSQL, no credential store. Proves the RULES and the
NEGATIVE effects the class insisted on: a rejected claim reads no credential and builds no Context;
an identity mismatch performs no browser business action and publishes nothing; a failed/UNKNOWN
final fence publishes nothing; an unapproved Origin closes the Context and marks SECURITY_FAILURE;
storage state is filtered to explicit allowlists. NOT integration evidence.
"""

from day63_session_gate import (
    ClaimResult,
    JobRequest,
    ObservedIdentity,
    Outcome,
    PersistOutcome,
    SessionBinding,
    SessionMeta,
    TaskCompletion,
    TaskDeps,
    blocks_publication,
    check_navigation,
    classify_claim,
    classify_login_persist,
    default_cookie_domains,
    filter_storage_state,
    final_fence,
    may_blind_retry,
    run_task_authorization,
    task_succeeded,
    validate_job_binding,
    verify_identity,
)

NOW = 1_000
BINDING = SessionBinding(
    tenant_id="tenantB", session_id="sess-B1", target_origin="https://research.example.test",
    owner="attempt-owner", expected_principal_id="prin_B", expected_organization_id="org_B",
    credential_ref="cred://ref/B1",
)
JOB = JobRequest(tenant_id="tenantB", session_id="sess-B1",
                 target_origin="https://research.example.test", attempt_id="att-1")
ACTIVE = SessionMeta(status="active", expires_at=NOW + 100, version=3,
                     lease_owner=None, lease_token=None, lease_expires_at=None)


# ---- individual rules --------------------------------------------------------------------
def test_binding_mismatch_is_precondition_failed():
    assert validate_job_binding(JOB, BINDING) is Outcome.AUTHORIZED
    other = JobRequest("tenantA", "sess-B1", "https://research.example.test", "att-1")
    assert validate_job_binding(other, BINDING) is Outcome.AUTHENTICATION_PRECONDITION_FAILED


def test_claim_active_free_lease_is_claimed():
    assert classify_claim(ACTIVE, "att-1", NOW) is ClaimResult.CLAIMED


def test_claim_revoked_or_expired_is_precondition_failed():
    revoked = SessionMeta("revoked", NOW + 100, 3, None, None, None)
    expired = SessionMeta("active", NOW - 1, 3, None, None, None)
    assert classify_claim(revoked, "att-1", NOW) is ClaimResult.PRECONDITION_FAILED
    assert classify_claim(expired, "att-1", NOW) is ClaimResult.PRECONDITION_FAILED


def test_second_attempt_cannot_seize_unexpired_lease():
    held = SessionMeta("active", NOW + 100, 3, lease_owner="att-OTHER",
                       lease_token="tok-x", lease_expires_at=NOW + 50)
    assert classify_claim(held, "att-1", NOW) is ClaimResult.LEASE_HELD
    # after expiry a new Attempt may claim
    expired_lease = SessionMeta("active", NOW + 100, 3, "att-OTHER", "tok-x", NOW - 1)
    assert classify_claim(expired_lease, "att-1", NOW) is ClaimResult.CLAIMED


def test_identity_rules_positive_fact_required():
    ok = ObservedIdentity(False, "prin_B", "org_B")
    assert verify_identity(ok, BINDING) is Outcome.AUTHORIZED
    assert verify_identity(ObservedIdentity(True, None, None), BINDING) is Outcome.AUTHENTICATION_PRECONDITION_FAILED
    # absence of redirect is NOT proof; a mutable display name is NOT proof
    assert verify_identity(ObservedIdentity(False, None, None, display_name="Someone"), BINDING) is Outcome.AUTHORIZATION_SESSION_FAILURE
    assert verify_identity(ObservedIdentity(False, "prin_OTHER", "org_B"), BINDING) is Outcome.AUTHORIZATION_SESSION_FAILURE
    assert verify_identity(ObservedIdentity(False, "prin_B", "org_OTHER"), BINDING) is Outcome.AUTHORIZATION_SESSION_FAILURE


def test_navigation_outcomes():
    assert check_navigation("https://research.example.test", BINDING.target_origin) is Outcome.AUTHORIZED
    assert check_navigation("https://billing.example.test", BINDING.target_origin) is Outcome.SECURITY_FAILURE


def test_final_fence_full_predicate():
    # AUTHORIZED requires: active + session not expired + lease_owner==attempt + token + lease not
    # expired + version. A fenced-and-owned lease authorizes.
    ok = SessionMeta("active", NOW + 100, 3, "att-1", "tok-1", NOW + 50)
    assert final_fence(ok, "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZED

    # timeout -> UNKNOWN (never blind retry)
    assert final_fence(ok, "tok-1", 3, "att-1", NOW, timed_out=True) is Outcome.UNKNOWN_AUTHORIZATION_STATE

    # session inactive/expired -> precondition failed
    assert final_fence(SessionMeta("revoked", NOW + 100, 3, "att-1", "tok-1", NOW + 50), "tok-1", 3, "att-1", NOW) is Outcome.AUTHENTICATION_PRECONDITION_FAILED
    assert final_fence(SessionMeta("active", NOW - 1, 3, "att-1", "tok-1", NOW + 50), "tok-1", 3, "att-1", NOW) is Outcome.AUTHENTICATION_PRECONDITION_FAILED

    # P1-1 regressions: an OLD Attempt must NOT publish on a stale/expired lease.
    # lease EXPIRED (same owner/token/version) -> authorization failure (no publish)
    assert final_fence(SessionMeta("active", NOW + 100, 3, "att-1", "tok-1", NOW - 1), "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZATION_SESSION_FAILURE
    assert final_fence(SessionMeta("active", NOW + 100, 3, "att-1", "tok-1", NOW), "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZATION_SESSION_FAILURE  # == now is expired
    assert final_fence(SessionMeta("active", NOW + 100, 3, "att-1", "tok-1", None), "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZATION_SESSION_FAILURE
    # lease OWNER is a different Attempt -> authorization failure
    assert final_fence(SessionMeta("active", NOW + 100, 3, "att-2", "tok-1", NOW + 50), "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZATION_SESSION_FAILURE
    # token / version mismatch -> authorization failure
    assert final_fence(SessionMeta("active", NOW + 100, 3, "att-1", "tok-OTHER", NOW + 50), "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZATION_SESSION_FAILURE
    assert final_fence(SessionMeta("active", NOW + 100, 4, "att-1", "tok-1", NOW + 50), "tok-1", 3, "att-1", NOW) is Outcome.AUTHORIZATION_SESSION_FAILURE


_STORAGE_STATE = {
    "cookies": [
        {"domain": "research.example.test", "name": "sid"},         # exact host -> kept
        {"domain": ".example.test", "name": "sso"},                 # cross-subdomain -> dropped by default
        {"domain": "billing.example.test", "name": "b"},            # unrelated subdomain -> dropped
    ],
    "origins": [
        {"origin": "https://research.example.test"},                # exact approved Origin -> kept
        {"origin": "https://billing.example.test"},                 # dropped
    ],
}


def test_default_cookie_domains_is_host_only_not_the_origin():
    # P1-2: the DEFAULT allowlist is the Origin's HOST, never the full Origin string.
    assert default_cookie_domains("https://research.example.test") == ["research.example.test"]
    assert "https://research.example.test" not in default_cookie_domains("https://research.example.test")


def test_storage_state_default_path_keeps_host_cookie_rejects_cross_subdomain():
    # End-to-end DEFAULT path: no explicit allowlist -> derive host-only domain from the Origin.
    filtered = filter_storage_state(
        _STORAGE_STATE, "https://research.example.test",
        default_cookie_domains("https://research.example.test"),
    )
    assert [c["name"] for c in filtered["cookies"]] == ["sid"]      # host cookie survives the default
    assert [o["origin"] for o in filtered["origins"]] == ["https://research.example.test"]


def test_storage_state_cross_subdomain_only_via_explicit_allowlist():
    # `.example.test` is kept ONLY when explicitly, auditably added to the allowlist.
    filtered = filter_storage_state(_STORAGE_STATE, "https://research.example.test",
                                    ["research.example.test", ".example.test"])
    assert sorted(c["name"] for c in filtered["cookies"]) == ["sid", "sso"]


def test_login_persist_all_combinations():
    # identity NOT verified -> rejected, regardless of the rest (4 combos)
    for sp in (True, False):
        for mc in (True, False):
            assert classify_login_persist(False, sp, mc) is PersistOutcome.REJECTED_NOT_VERIFIED
    # identity verified:
    assert classify_login_persist(True, True, True) is PersistOutcome.ACTIVATED
    assert classify_login_persist(True, True, False) is PersistOutcome.ORPHAN_INACTIVE   # ONLY orphan case
    # P2-2: state NOT saved is NEVER an orphan (no protected material exists)
    assert classify_login_persist(True, False, True) is PersistOutcome.PERSIST_CONSISTENCY_FAILED  # impossible combo
    assert classify_login_persist(True, False, False) is PersistOutcome.PERSIST_CONSISTENCY_FAILED  # nothing saved


def test_non_authorized_blocks_publication_and_no_blind_retry():
    for o in (Outcome.AUTHENTICATION_PRECONDITION_FAILED, Outcome.AUTHORIZATION_SESSION_FAILURE,
              Outcome.UNKNOWN_AUTHORIZATION_STATE, Outcome.SECURITY_FAILURE):
        assert blocks_publication(o) is True
        assert may_blind_retry(o) is False
    assert blocks_publication(Outcome.AUTHORIZED) is False


# ---- orchestrator: NEGATIVE effects ------------------------------------------------------
class _Spy:
    """Records which side effects ran and returns programmable observations."""
    def __init__(self, identity=None, origin=None, close_raises=False, publish_raises=False):
        self.calls = []
        self._identity = identity or ObservedIdentity(False, "prin_B", "org_B")
        self._origin = origin or "https://research.example.test"
        self._close_raises = close_raises
        self._publish_raises = publish_raises

    def deps(self):
        def read_credential(ref):
            self.calls.append("read_credential"); return {"cookies": [], "origins": []}
        def create_context(state):
            self.calls.append("create_context"); return object()
        def probe_identity(ctx):
            self.calls.append("probe_identity"); return self._identity
        def observe_origin(ctx):
            self.calls.append("observe_origin"); return self._origin
        def publish_result(ctx):
            self.calls.append("publish_result")
            if self._publish_raises:
                raise RuntimeError("publish failed")
        def close_context(ctx):
            self.calls.append("close_context")
            if self._close_raises:
                raise RuntimeError("close failed")
        return TaskDeps(read_credential, create_context, probe_identity, observe_origin,
                        publish_result, close_context)


def _run(spy, meta=ACTIVE, job=JOB, fence_meta=None, fence_timed_out=False, worker_token="tok-1"):
    # make the claimed session lease-consistent for a clean AUTHORIZED path
    claimed = SessionMeta(meta.status, meta.expires_at, meta.version, job.attempt_id, worker_token,
                          NOW + 50) if meta is ACTIVE else meta
    return run_task_authorization(job, BINDING, claimed, spy.deps(), now=NOW,
                                  worker_token=worker_token, fence_meta=fence_meta,
                                  fence_timed_out=fence_timed_out)


def test_happy_path_publishes_and_closes_is_success():
    spy = _Spy()
    r = _run(spy)
    assert r.outcome is Outcome.AUTHORIZED and r.published is True
    assert r.status is TaskCompletion.SUCCESS and task_succeeded(r) is True   # cleanup completed
    assert r.cleanup_error is None
    assert spy.calls == ["read_credential", "create_context", "probe_identity",
                         "observe_origin", "publish_result", "close_context"]


def test_rejected_claim_never_reads_credential_or_builds_context():
    spy = _Spy()
    revoked = SessionMeta("revoked", NOW + 100, 3, None, None, None)
    r = run_task_authorization(JOB, BINDING, revoked, spy.deps(), now=NOW, worker_token="tok-1")
    assert r.outcome is Outcome.AUTHENTICATION_PRECONDITION_FAILED and r.published is False
    assert spy.calls == []                       # NO credential read, NO Context factory


def test_binding_mismatch_never_touches_deps():
    spy = _Spy()
    other = JobRequest("tenantA", "sess-B1", "https://research.example.test", "att-1")
    r = run_task_authorization(other, BINDING, ACTIVE, spy.deps(), now=NOW, worker_token="tok-1")
    assert r.outcome is Outcome.AUTHENTICATION_PRECONDITION_FAILED
    assert spy.calls == []


def test_identity_mismatch_no_business_action_no_publish():
    spy = _Spy(identity=ObservedIdentity(False, "prin_WRONG", "org_B"))
    r = _run(spy)
    assert r.outcome is Outcome.AUTHORIZATION_SESSION_FAILURE and r.published is False
    assert "observe_origin" not in spy.calls and "publish_result" not in spy.calls
    assert spy.calls[-1] == "close_context"      # Context still closed


def test_unapproved_origin_marks_security_failure_and_closes():
    spy = _Spy(origin="https://billing.example.test")
    r = _run(spy)
    assert r.outcome is Outcome.SECURITY_FAILURE and r.published is False
    assert "publish_result" not in spy.calls and spy.calls[-1] == "close_context"


def test_final_fence_timeout_is_unknown_and_no_publish():
    spy = _Spy()
    fence = SessionMeta("active", NOW + 100, 3, "att-1", "tok-1", NOW + 50)
    r = _run(spy, fence_meta=fence, fence_timed_out=True)
    assert r.outcome is Outcome.UNKNOWN_AUTHORIZATION_STATE and r.published is False
    assert "publish_result" not in spy.calls and spy.calls[-1] == "close_context"


def test_final_fence_superseded_blocks_publish():
    spy = _Spy()
    superseded = SessionMeta("active", NOW + 100, 4, "att-2", "tok-2", NOW + 50)
    r = _run(spy, fence_meta=superseded)
    assert r.outcome is Outcome.AUTHORIZATION_SESSION_FAILURE and r.published is False
    assert "publish_result" not in spy.calls


def test_business_success_but_cleanup_failure_is_incomplete_not_success():
    # P1-3: a published result whose context.close() FAILED is INCOMPLETE, never SUCCESS. The
    # published flag stays True (we don't fake un-publish), but the task is not fully successful.
    spy = _Spy(close_raises=True)
    r = _run(spy)
    assert r.outcome is Outcome.AUTHORIZED and r.published is True        # result WAS published
    assert r.status is TaskCompletion.INCOMPLETE and task_succeeded(r) is False
    assert r.cleanup_error is not None and "close failed" in r.cleanup_error
    assert r.primary_error is None                                       # no business error to preserve


def test_business_failure_and_cleanup_failure_preserves_primary_error():
    # publish raises (business error) AND close raises: primary error is the business one, the
    # cleanup error is recorded separately (never overwrites it), status FAILED, nothing published.
    spy = _Spy(publish_raises=True, close_raises=True)
    r = _run(spy)
    assert r.status is TaskCompletion.FAILED and r.published is False
    assert r.primary_error is not None and "publish failed" in r.primary_error   # ORIGINAL error kept
    assert r.cleanup_error is not None and "close failed" in r.cleanup_error      # separate diagnostics
    assert r.outcome is Outcome.UNKNOWN_AUTHORIZATION_STATE                       # exception -> unknown, no publish


def test_non_authorized_business_failure_with_cleanup_failure_is_failed():
    # identity mismatch (business failure, not an exception) + cleanup failure -> FAILED, no publish.
    spy = _Spy(identity=ObservedIdentity(False, "prin_WRONG", "org_B"), close_raises=True)
    r = _run(spy)
    assert r.status is TaskCompletion.FAILED and r.published is False
    assert r.outcome is Outcome.AUTHORIZATION_SESSION_FAILURE
    assert r.cleanup_error is not None                                            # recorded
    assert "publish_result" not in spy.calls


# ---- STATIC gate-source contract (always run; no Playwright) ------------------------------
import pathlib as _pathlib

_GATE_SRC = (_pathlib.Path(__file__).parent / ".." / "src" / "day63_session_gate.py").read_text()


def test_gate_blocks_publication_on_every_non_authorized_outcome():
    assert "def blocks_publication" in _GATE_SRC
    assert "return outcome is not Outcome.AUTHORIZED" in _GATE_SRC
    # publish happens only inside the final AUTHORIZED guard
    assert "if outcome is Outcome.AUTHORIZED:\n            deps.publish_result(context)" in _GATE_SRC


def test_gate_reads_credential_only_after_a_successful_claim():
    assert _GATE_SRC.index("claim_result_to_outcome(claim)") < _GATE_SRC.index("deps.read_credential(")


def test_gate_holds_no_credential_material_or_real_identifiers():
    for forbidden in ("BEGIN RSA", "password=", "cookie:", "Bearer "):
        assert forbidden.lower() not in _GATE_SRC.lower()
