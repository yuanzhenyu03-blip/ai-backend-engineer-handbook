"""Day47 — FAKE-SESSION unit tests for Unit-of-Work control flow.

IMPORTANT EVIDENCE LABEL: these are fake/mocked-session tests. They verify the
UoW/repository CONTROL FLOW (explicit commit, rollback+close on exception or
uncommitted exit, guarded zero-row stale/no-op, flush-before-dependent-write,
repos never commit, one shared Session per UoW, a fresh Session per UoW). They do
NOT connect to a database. A real PostgreSQL rollback/transaction runtime test
(fresh verification Session proving the Job stays queued with no Attempt/Event) is
POSTGRESQL RUNTIME NOT RUN — no server/driver was available, and SQLite is not
PostgreSQL evidence for this app-schema/PostgreSQL-typed contract. Executed with
pytest via asyncio.run (no pytest-asyncio dependency).
"""

import asyncio
import uuid

import pytest

from day47_async_uow import (
    ArtifactRepository,
    AttemptRepository,
    ClaimOutcome,
    CompletionOutcome,
    FakeProvider,
    JobRepository,
    ProviderUnknownOutcome,
    UnitOfWork,
    complete_job,
    start_job,
)
from day46_orm_mapping import JobAttempt, JobEvent, ResultArtifact

JOB_ID = uuid.UUID("3b2f1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
TENANT_ID = uuid.UUID("0f9b0e3a-6a1e-4c2b-9c1f-2b7a4d5e6f70")
WRONG_TENANT_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")
ATTEMPT_ID = uuid.UUID("7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d")
OBJECT_KEY = "obj://tenant/job/result.json"
CORR = "corr-0f9b0e3a-app-generated"


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeAsyncSession:
    """Records lifecycle calls; returns queued results for execute()."""

    def __init__(self, execute_rows=None, commit_raises=None, raise_on_add_type=None):
        # execute_rows: list of row-lists, one per execute() call (default 1 row).
        self._execute_rows = list(execute_rows) if execute_rows is not None else None
        self._commit_raises = commit_raises
        # raise_on_add_type: simulate a write failure (e.g. a constraint violation)
        # when an instance of this ORM class is added to the session.
        self._raise_on_add_type = raise_on_add_type
        self.added = []
        self.calls = []  # ordered log of ("add"/"flush"/"commit"/"rollback"/"close"/"execute")
        self.executed = []  # list of (sql_text, params) for each execute() call

    async def execute(self, stmt, params=None):
        self.calls.append("execute")
        self.executed.append((str(stmt), dict(params or {})))
        if self._execute_rows is not None:
            rows = self._execute_rows.pop(0)
        else:
            rows = [(JOB_ID,)]  # default: one guarded row
        return FakeResult(rows)

    def add(self, obj):
        self.calls.append("add")
        if self._raise_on_add_type is not None and isinstance(obj, self._raise_on_add_type):
            raise RuntimeError(f"simulated write failure for {type(obj).__name__}")
        self.added.append(obj)

    async def flush(self):
        self.calls.append("flush")
        # Simulate server-generated attempt_id becoming available after flush.
        for obj in self.added:
            if isinstance(obj, JobAttempt) and obj.attempt_id is None:
                obj.attempt_id = uuid.uuid4()

    async def commit(self):
        self.calls.append("commit")
        if self._commit_raises is not None:
            raise self._commit_raises

    async def rollback(self):
        self.calls.append("rollback")

    async def close(self):
        self.calls.append("close")


def factory_of(*sessions):
    """A session factory that yields the given fake sessions in order (a NEW
    Session per call — never a shared batch of live Sessions)."""
    it = iter(sessions)
    made = []

    def _factory():
        s = next(it)
        made.append(s)
        return s

    _factory.made = made
    return _factory


# 1. Claimed start flow: guarded claim (1 row) -> Attempt (flush) -> Event -> commit.
def test_start_job_claimed_commits_once_with_attempt_and_event():
    sess = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])  # 1 claimed row
    outcome = asyncio.run(start_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, correlation_key=CORR))
    assert outcome is ClaimOutcome.CLAIMED
    assert sess.calls.count("commit") == 1
    assert "rollback" not in sess.calls
    assert sess.calls[-1] == "close"  # always closed, last
    assert any(isinstance(o, JobAttempt) for o in sess.added)
    assert any(isinstance(o, JobEvent) for o in sess.added)


# 2. Zero-row guarded claim = NORMAL stale/no-op: no Attempt/Event, no commit.
def test_start_job_zero_row_claim_is_stale_noop_no_writes():
    sess = FakeAsyncSession(execute_rows=[[]])  # 0 claimed rows
    outcome = asyncio.run(start_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, correlation_key=CORR))
    assert outcome is ClaimOutcome.STALE_NOOP
    assert not sess.added  # no Attempt/Event created
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls  # uncommitted exit rolls back the empty UoW
    assert sess.calls[-1] == "close"


# 3. flush happens BEFORE the dependent Event write, and the Event gets the
#    flush-assigned attempt_id (no commit needed for the dependent write).
def test_flush_before_dependent_event_write():
    sess = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])
    asyncio.run(start_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, correlation_key=CORR))
    assert "flush" in sess.calls
    first_add = sess.calls.index("add")
    flush_idx = sess.calls.index("flush")
    assert first_add < flush_idx < len(sess.calls)  # add attempt -> flush -> add event
    event = next(o for o in sess.added if isinstance(o, JobEvent))
    assert event.attempt_id is not None  # dependent write used the flushed id


# 3b. The correlation/idempotency key is carried by the job_started Event metadata
#     (Day46 has no correlation column on JobAttempt), written by the start flow in
#     the same UoW — NOT by AttemptRepository.create (which no longer accepts it).
def test_correlation_key_lives_in_job_started_event_metadata():
    import inspect as _inspect

    # AttemptRepository.create must not accept a correlation_key parameter anymore.
    params = _inspect.signature(AttemptRepository.create).parameters
    assert "correlation_key" not in params

    sess = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])
    asyncio.run(start_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, correlation_key=CORR))
    started = [
        o for o in sess.added
        if isinstance(o, JobEvent) and o.event_type == "job_started"
    ]
    assert len(started) == 1
    assert started[0].event_metadata.get("correlation_key") == CORR


# 4. The UoW rolls back and closes on an exception inside the block (no commit).
def test_uow_rolls_back_and_closes_on_exception():
    sess = FakeAsyncSession()

    async def scenario():
        with pytest.raises(RuntimeError):
            async with UnitOfWork(factory_of(sess)):
                raise RuntimeError("boom inside UoW")

    asyncio.run(scenario())
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 5. The UoW does NOT auto-commit on a normal exit without an explicit commit.
def test_uow_no_autocommit_on_uncommitted_exit():
    sess = FakeAsyncSession()

    async def scenario():
        async with UnitOfWork(factory_of(sess)) as uow:
            assert uow.jobs is not None  # did some work, but never called commit
        return uow

    asyncio.run(scenario())
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls  # uncommitted -> rolled back
    assert sess.calls[-1] == "close"


# 6. A repository method alone does NOT commit or close (only the UoW decides).
def test_repository_does_not_commit_or_close():
    sess = FakeAsyncSession()

    async def scenario():
        repo = AttemptRepository(sess)
        await repo.create(JOB_ID, 1)  # add + flush, but no commit/close

    asyncio.run(scenario())
    assert "add" in sess.calls and "flush" in sess.calls
    assert "commit" not in sess.calls
    assert "close" not in sess.calls


# 7. A commit exception is an UNKNOWN commit outcome: the UoW still rolls back
#    and closes local state, and the exception propagates so the caller reloads
#    durable truth by stable id rather than blindly replaying the write.
def test_commit_exception_rolls_back_and_closes_then_propagates():
    sess = FakeAsyncSession(commit_raises=RuntimeError("commit outcome unknown"))

    async def scenario():
        with pytest.raises(RuntimeError):
            async with UnitOfWork(factory_of(sess)) as uow:
                await uow.commit()

    asyncio.run(scenario())
    assert "commit" in sess.calls
    assert "rollback" in sess.calls  # __aexit__ saw the exception
    assert sess.calls[-1] == "close"


# 8. One UoW shares ONE Session across all repositories.
def test_uow_shares_one_session_across_repositories():
    sess = FakeAsyncSession()

    async def scenario():
        async with UnitOfWork(factory_of(sess)) as uow:
            assert uow.session is sess
            assert uow.jobs._session is sess
            assert uow.attempts._session is sess
            assert uow.events._session is sess

    asyncio.run(scenario())


# 9. No global Session: each UoW gets a FRESH Session from the factory.
def test_each_uow_gets_a_fresh_session():
    s1, s2 = FakeAsyncSession(), FakeAsyncSession()
    fac = factory_of(s1, s2)

    async def scenario():
        async with UnitOfWork(fac) as u1:
            first = u1.session
        async with UnitOfWork(fac) as u2:
            second = u2.session
        assert first is s1 and second is s2 and first is not second

    asyncio.run(scenario())
    assert len(fac.made) == 2


# 10. Completion = the Day33 atomic pack in ONE commit: guarded Attempt finish +
#     guarded Job transition + ResultArtifact reference + job_succeeded Event.
def test_complete_job_persists_full_atomic_pack_in_one_commit():
    # execute #1 = Attempt finish (1 row); execute #2 = Job transition (1 row).
    sess = FakeAsyncSession(execute_rows=[[(ATTEMPT_ID,)], [(JOB_ID,)]])
    outcome = asyncio.run(
        complete_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY)
    )
    assert outcome is CompletionOutcome.COMPLETED
    assert sess.calls.count("execute") == 2  # Attempt finish + Job transition guards
    artifacts = [o for o in sess.added if isinstance(o, ResultArtifact)]
    events = [o for o in sess.added if isinstance(o, JobEvent)]
    assert len(artifacts) == 1  # ResultArtifact durable reference persisted
    assert artifacts[0].object_key == OBJECT_KEY  # Object Storage KEY, not bytes
    assert artifacts[0].attempt_id == ATTEMPT_ID   # ownership derived via Attempt
    assert len(events) == 1 and events[0].event_type == "job_succeeded"
    assert sess.calls.count("commit") == 1  # ONE commit for the whole pack
    assert "rollback" not in sess.calls
    assert sess.calls[-1] == "close"


# 11. Stale / already-finished Attempt (finish guard 0 rows): NO Job success, NO
#     Artifact, NO Event; rollback + close. Never overwrite a finished Attempt.
def test_complete_job_stale_attempt_writes_nothing():
    sess = FakeAsyncSession(execute_rows=[[]])  # Attempt finish returns 0 rows
    outcome = asyncio.run(
        complete_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY)
    )
    assert outcome is CompletionOutcome.STALE_NOOP
    assert sess.calls.count("execute") == 1  # stopped after the Attempt guard
    assert not sess.added  # no Job transition attempted, no Artifact, no Event
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 12. Stale Job (Attempt finished, but Job transition 0 rows): NO Artifact, NO
#     Event; rollback + close.
def test_complete_job_stale_job_writes_no_artifact_or_event():
    # Attempt finish 1 row, then Job transition 0 rows.
    sess = FakeAsyncSession(execute_rows=[[(ATTEMPT_ID,)], []])
    outcome = asyncio.run(
        complete_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY)
    )
    assert outcome is CompletionOutcome.STALE_NOOP
    assert sess.calls.count("execute") == 2  # both guards ran; Job guard returned 0
    assert not any(isinstance(o, ResultArtifact) for o in sess.added)
    assert not any(isinstance(o, JobEvent) for o in sess.added)
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 13. Artifact insert failure inside the pack: rollback + close, no commit, no
#     partial state. (Fake-session control flow only — NOT a real DB constraint.)
def test_complete_job_artifact_failure_rolls_back():
    sess = FakeAsyncSession(
        execute_rows=[[(ATTEMPT_ID,)], [(JOB_ID,)]], raise_on_add_type=ResultArtifact
    )

    async def scenario():
        with pytest.raises(RuntimeError):
            await complete_job(
                factory_of(sess), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY
            )

    asyncio.run(scenario())
    assert not any(isinstance(o, JobEvent) for o in sess.added)  # Event never reached
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 14. Success Event append failure inside the pack: rollback + close, no commit.
def test_complete_job_event_failure_rolls_back():
    sess = FakeAsyncSession(
        execute_rows=[[(ATTEMPT_ID,)], [(JOB_ID,)]], raise_on_add_type=JobEvent
    )

    async def scenario():
        with pytest.raises(RuntimeError):
            await complete_job(
                factory_of(sess), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY
            )

    asyncio.run(scenario())
    # The Artifact was added in-memory, but the failing Event means the UoW never
    # commits and rolls back — no partial PostgreSQL durable state (a fake-session
    # test proves control flow only, NOT real database rollback).
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 12. The Provider seam is OUTSIDE the DB transaction, and an unknown outcome is a
#     first-class recovery signal (never fabricated, never blindly replayed).
def test_provider_unknown_outcome_propagates_and_is_not_fabricated():
    provider = FakeProvider(raises=ProviderUnknownOutcome("timeout after call began"))

    async def scenario():
        with pytest.raises(ProviderUnknownOutcome):
            await provider.run(correlation_key=CORR)

    asyncio.run(scenario())
    assert provider.calls == 1  # called once; caller must NOT blindly re-call


# 13. A definitive Provider failure lets a guarded mark_failed record 'failed'
#     (guarded on 'running'); a zero-row guard is a stale/no-op.
def test_guarded_mark_failed_paths():
    async def scenario():
        one = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])
        assert await JobRepository(one).mark_failed(JOB_ID, TENANT_ID) == 1
        zero = FakeAsyncSession(execute_rows=[[]])
        assert await JobRepository(zero).mark_failed(JOB_ID, TENANT_ID) == 0

    asyncio.run(scenario())


# 18. Every guarded app.jobs mutation carries tenant_id as an explicit bind, and
#     the tenant_id is NOT the job_id (it is a separate durable ownership predicate
#     passed from the orchestration, not derived from the job identity).
def test_all_job_mutations_carry_tenant_predicate():
    # start_job -> guarded_claim
    s1 = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])
    asyncio.run(start_job(factory_of(s1), JOB_ID, tenant_id=TENANT_ID, correlation_key=CORR))
    claim_sql, claim_params = s1.executed[0]
    assert "tenant_id = :tenant_id" in claim_sql
    assert claim_params["tenant_id"] == TENANT_ID
    assert claim_params["tenant_id"] != claim_params["job_id"]  # not derived from job_id

    # complete_job -> guarded_complete (second execute is the Job transition)
    s2 = FakeAsyncSession(execute_rows=[[(ATTEMPT_ID,)], [(JOB_ID,)]])
    asyncio.run(
        complete_job(factory_of(s2), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY)
    )
    job_sql, job_params = s2.executed[1]
    assert "tenant_id = :tenant_id" in job_sql
    assert job_params["tenant_id"] == TENANT_ID

    # mark_failed
    s3 = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])

    async def _mf():
        return await JobRepository(s3).mark_failed(JOB_ID, TENANT_ID)

    asyncio.run(_mf())
    fail_sql, fail_params = s3.executed[0]
    assert "tenant_id = :tenant_id" in fail_sql
    assert fail_params["tenant_id"] == TENANT_ID


# 19. A WRONG tenant makes the guarded Job transition match 0 rows: rollback, and
#     NO Artifact / NO Event are committed (tenant is an ownership boundary, and a
#     job_id alone does not authorize completion).
def test_wrong_tenant_completion_writes_nothing():
    # Attempt finish 1 row; Job transition 0 rows (wrong tenant).
    sess = FakeAsyncSession(execute_rows=[[(ATTEMPT_ID,)], []])
    outcome = asyncio.run(
        complete_job(
            factory_of(sess), JOB_ID, tenant_id=WRONG_TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY
        )
    )
    assert outcome is CompletionOutcome.STALE_NOOP
    assert sess.executed[1][1]["tenant_id"] == WRONG_TENANT_ID  # wrong tenant bound
    assert not any(isinstance(o, ResultArtifact) for o in sess.added)
    assert not any(isinstance(o, JobEvent) for o in sess.added)
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 20. A WRONG tenant makes the guarded CLAIM match 0 rows: stale/no-op, no
#     Attempt/Event, no commit.
def test_wrong_tenant_claim_is_stale_noop():
    sess = FakeAsyncSession(execute_rows=[[]])  # claim returns 0 rows (wrong tenant)
    outcome = asyncio.run(
        start_job(factory_of(sess), JOB_ID, tenant_id=WRONG_TENANT_ID, correlation_key=CORR)
    )
    assert outcome is ClaimOutcome.STALE_NOOP
    assert sess.executed[0][1]["tenant_id"] == WRONG_TENANT_ID
    assert not sess.added
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls
    assert sess.calls[-1] == "close"


# 21. The completion pack records the available Provider evidence
#     (provider_request_id + cost_micros) in the SAME guarded Attempt-finish
#     statement (finished_at IS NULL guard preserved).
def test_completion_records_provider_evidence_in_attempt_finish():
    sess = FakeAsyncSession(execute_rows=[[(ATTEMPT_ID,)], [(JOB_ID,)]])
    outcome = asyncio.run(
        complete_job(
            factory_of(sess),
            JOB_ID,
            tenant_id=TENANT_ID,
            attempt_id=ATTEMPT_ID,
            object_key=OBJECT_KEY,
            provider_request_id="prov-req-abc123",
            cost_micros=4200,
        )
    )
    assert outcome is CompletionOutcome.COMPLETED
    finish_sql, finish_params = sess.executed[0]  # first execute = guarded Attempt finish
    assert "finished_at = now()" in finish_sql
    assert "provider_request_id = :provider_request_id" in finish_sql
    assert "cost_micros = :cost_micros" in finish_sql
    assert "finished_at IS NULL" in finish_sql  # guard preserved
    assert finish_params["provider_request_id"] == "prov-req-abc123"
    assert finish_params["cost_micros"] == 4200
    assert finish_params["attempt_id"] == ATTEMPT_ID and finish_params["job_id"] == JOB_ID


# 22. Provider evidence may be None when not yet known (written as NULL); passing
#     None does NOT assert a verified value — the binds are literally None.
def test_completion_provider_evidence_may_be_none():
    sess = FakeAsyncSession(execute_rows=[[(ATTEMPT_ID,)], [(JOB_ID,)]])
    asyncio.run(
        complete_job(factory_of(sess), JOB_ID, tenant_id=TENANT_ID, attempt_id=ATTEMPT_ID, object_key=OBJECT_KEY)
    )
    _, finish_params = sess.executed[0]
    assert finish_params["provider_request_id"] is None
    assert finish_params["cost_micros"] is None


# 23. The FakeProvider seam models Provider evidence (request id + cost) without
#     any network I/O — a control-flow double, NOT a real Provider SDK.
def test_fake_provider_models_evidence_without_network():
    provider = FakeProvider(
        artifact_ref=OBJECT_KEY, provider_request_id="prov-req-abc123", cost_micros=4200
    )
    ref = asyncio.run(provider.run(correlation_key=CORR))
    assert ref == OBJECT_KEY
    assert provider.provider_request_id == "prov-req-abc123"
    assert provider.cost_micros == 4200
    assert provider.calls == 1
