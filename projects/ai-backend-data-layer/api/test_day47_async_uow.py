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
from day46_orm_mapping import JobAttempt, JobEvent

JOB_ID = uuid.UUID("3b2f1c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
CORR = "corr-0f9b0e3a-app-generated"


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeAsyncSession:
    """Records lifecycle calls; returns queued results for execute()."""

    def __init__(self, execute_rows=None, commit_raises=None):
        # execute_rows: list of row-lists, one per execute() call (default 1 row).
        self._execute_rows = list(execute_rows) if execute_rows is not None else None
        self._commit_raises = commit_raises
        self.added = []
        self.calls = []  # ordered log of ("add"/"flush"/"commit"/"rollback"/"close"/"execute")

    async def execute(self, stmt, params=None):
        self.calls.append("execute")
        if self._execute_rows is not None:
            rows = self._execute_rows.pop(0)
        else:
            rows = [(JOB_ID,)]  # default: one guarded row
        return FakeResult(rows)

    def add(self, obj):
        self.calls.append("add")
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
    outcome = asyncio.run(start_job(factory_of(sess), JOB_ID, correlation_key=CORR))
    assert outcome is ClaimOutcome.CLAIMED
    assert sess.calls.count("commit") == 1
    assert "rollback" not in sess.calls
    assert sess.calls[-1] == "close"  # always closed, last
    assert any(isinstance(o, JobAttempt) for o in sess.added)
    assert any(isinstance(o, JobEvent) for o in sess.added)


# 2. Zero-row guarded claim = NORMAL stale/no-op: no Attempt/Event, no commit.
def test_start_job_zero_row_claim_is_stale_noop_no_writes():
    sess = FakeAsyncSession(execute_rows=[[]])  # 0 claimed rows
    outcome = asyncio.run(start_job(factory_of(sess), JOB_ID, correlation_key=CORR))
    assert outcome is ClaimOutcome.STALE_NOOP
    assert not sess.added  # no Attempt/Event created
    assert "commit" not in sess.calls
    assert "rollback" in sess.calls  # uncommitted exit rolls back the empty UoW
    assert sess.calls[-1] == "close"


# 3. flush happens BEFORE the dependent Event write, and the Event gets the
#    flush-assigned attempt_id (no commit needed for the dependent write).
def test_flush_before_dependent_event_write():
    sess = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])
    asyncio.run(start_job(factory_of(sess), JOB_ID, correlation_key=CORR))
    assert "flush" in sess.calls
    first_add = sess.calls.index("add")
    flush_idx = sess.calls.index("flush")
    assert first_add < flush_idx < len(sess.calls)  # add attempt -> flush -> add event
    event = next(o for o in sess.added if isinstance(o, JobEvent))
    assert event.attempt_id is not None  # dependent write used the flushed id


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
        await repo.create(JOB_ID, 1, CORR)  # add + flush, but no commit/close

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


# 10. Completion is a SECOND short guarded UoW: 1 row -> commit + job_succeeded.
def test_complete_job_completed_commits_with_event():
    sess = FakeAsyncSession(execute_rows=[[(JOB_ID,)]])
    outcome = asyncio.run(
        complete_job(factory_of(sess), JOB_ID, attempt_id=uuid.uuid4(), artifact_ref="obj://a")
    )
    assert outcome is CompletionOutcome.COMPLETED
    assert sess.calls.count("commit") == 1
    assert any(isinstance(o, JobEvent) for o in sess.added)


# 11. A zero-row guarded completion is a NORMAL stale/no-op: no Event, no commit.
def test_complete_job_zero_row_is_stale_noop():
    sess = FakeAsyncSession(execute_rows=[[]])
    outcome = asyncio.run(
        complete_job(factory_of(sess), JOB_ID, attempt_id=uuid.uuid4(), artifact_ref="obj://a")
    )
    assert outcome is CompletionOutcome.STALE_NOOP
    assert not sess.added
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
        assert await JobRepository(one).mark_failed(JOB_ID) == 1
        zero = FakeAsyncSession(execute_rows=[[]])
        assert await JobRepository(zero).mark_failed(JOB_ID) == 0

    asyncio.run(scenario())
