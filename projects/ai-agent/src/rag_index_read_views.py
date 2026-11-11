"""Leased Day104 ReadViews, drain reconciliation and retirement gates."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from rag_index_lifecycle_committer import (
    InMemoryIndexLifecycleStore,
    LifecycleTransitionRecord,
)
from rag_index_lifecycle_contracts import (
    GenerationState,
    ReadView,
    ReadViewStatus,
)


def _timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


class ReadViewOutcome(str, Enum):
    ACQUIRED = "ACQUIRED"
    ALREADY_ACQUIRED = "ALREADY_ACQUIRED"
    HEARTBEAT = "HEARTBEAT"
    CLOSED = "CLOSED"
    ALREADY_CLOSED = "ALREADY_CLOSED"
    STALE_POINTER = "STALE_POINTER"
    NOT_ACTIVE = "NOT_ACTIVE"
    NOT_FOUND = "NOT_FOUND"
    STALE_FENCE = "STALE_FENCE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    INVALID_LEASE = "INVALID_LEASE"


class RetirementOutcome(str, Enum):
    RETIRED = "RETIRED"
    ALREADY_RETIRED = "ALREADY_RETIRED"
    NOT_FOUND = "NOT_FOUND"
    STALE_STATE = "STALE_STATE"
    NOT_DRAINING = "NOT_DRAINING"
    READERS_PRESENT = "READERS_PRESENT"
    LEDGER_MISMATCH = "LEDGER_MISMATCH"
    RETENTION_NOT_MET = "RETENTION_NOT_MET"


@dataclass(frozen=True)
class ReadViewResult:
    outcome: ReadViewOutcome
    safe_reason: str
    view: ReadView | None = None
    durable_transition: bool = False


@dataclass(frozen=True)
class RetirementResult:
    outcome: RetirementOutcome
    safe_reason: str
    durable_transition: bool = False


class IndexReadViewManager:
    def __init__(self, store: InMemoryIndexLifecycleStore) -> None:
        self._store = store

    def acquire(
        self,
        *,
        view_id: str,
        pointer_name: str,
        expected_generation_id: str,
        expected_pointer_revision: int,
        owner_id: str,
        now: str,
        lease_expires_at: str,
    ) -> ReadViewResult:
        store = self._store
        now_value = _timestamp(now)
        expiry = _timestamp(lease_expires_at)
        if expiry <= now_value:
            return ReadViewResult(
                ReadViewOutcome.INVALID_LEASE,
                "READ_VIEW_LEASE_MUST_EXPIRE_IN_THE_FUTURE",
            )
        with store._lock:
            existing = store._read_views.get(view_id)
            if existing is not None:
                if (
                    existing.status is ReadViewStatus.OPEN
                    and _timestamp(existing.lease_expires_at) > now_value
                    and existing.pointer_name == pointer_name
                    and existing.generation_id == expected_generation_id
                    and existing.pointer_revision == expected_pointer_revision
                    and existing.owner_id == owner_id
                    and existing.lease_expires_at == lease_expires_at
                ):
                    return ReadViewResult(
                        ReadViewOutcome.ALREADY_ACQUIRED,
                        "EXACT_READ_VIEW_REPLAY_CONVERGED",
                        existing,
                    )
                return ReadViewResult(
                    ReadViewOutcome.IDENTITY_CONFLICT,
                    "READ_VIEW_ID_ALREADY_BOUND_TO_OTHER_INPUT",
                    existing,
                )
            pointer = store._pointers.get(pointer_name)
            if (
                pointer is None
                or pointer.generation_id != expected_generation_id
                or pointer.revision != expected_pointer_revision
            ):
                return ReadViewResult(
                    ReadViewOutcome.STALE_POINTER,
                    "POINTER_CHANGED_BEFORE_READ_VIEW_ACQUIRE",
                )
            lifecycle = store._lifecycles.get(expected_generation_id)
            build = store._builds.get(expected_generation_id)
            artifact = store._artifacts.get(expected_generation_id)
            if lifecycle is None or build is None or artifact is None:
                return ReadViewResult(
                    ReadViewOutcome.NOT_FOUND,
                    "ACTIVE_GENERATION_BINDINGS_NOT_FOUND",
                )
            if lifecycle.state is not GenerationState.ACTIVE:
                return ReadViewResult(
                    ReadViewOutcome.NOT_ACTIVE,
                    "NEW_READ_VIEWS_REQUIRE_AN_ACTIVE_GENERATION",
                )
            view = ReadView(
                view_id=view_id,
                pointer_name=pointer_name,
                generation_id=expected_generation_id,
                pointer_revision=expected_pointer_revision,
                owner_id=owner_id,
                build_snapshot_fingerprint=artifact.build_snapshot_fingerprint,
                authorization_snapshot_id=(
                    build.build_snapshot.authorization_snapshot.identity
                ),
                status=ReadViewStatus.OPEN,
                fencing_token=1,
                lease_expires_at=lease_expires_at,
                last_heartbeat_at=now,
            )
            store._read_views[view_id] = view
            store._lifecycles[expected_generation_id] = replace(
                lifecycle,
                active_readers=lifecycle.active_readers + 1,
                state_version=lifecycle.state_version + 1,
            )
            return ReadViewResult(
                ReadViewOutcome.ACQUIRED,
                "READ_VIEW_AND_READER_COUNT_COMMITTED_ATOMICALLY",
                view,
                durable_transition=True,
            )

    def heartbeat(
        self,
        *,
        view_id: str,
        expected_fence: int,
        now: str,
        lease_expires_at: str,
    ) -> ReadViewResult:
        store = self._store
        now_value = _timestamp(now)
        expiry = _timestamp(lease_expires_at)
        with store._lock:
            view = store._read_views.get(view_id)
            if view is None:
                return ReadViewResult(
                    ReadViewOutcome.NOT_FOUND,
                    "READ_VIEW_NOT_FOUND",
                )
            if view.fencing_token != expected_fence:
                return ReadViewResult(
                    ReadViewOutcome.STALE_FENCE,
                    "READ_VIEW_FENCE_NOT_CURRENT",
                    view,
                )
            if (
                view.status is not ReadViewStatus.OPEN
                or _timestamp(view.lease_expires_at) <= now_value
                or expiry <= now_value
                or expiry <= _timestamp(view.lease_expires_at)
            ):
                return ReadViewResult(
                    ReadViewOutcome.INVALID_LEASE,
                    "CLOSED_OR_EXPIRED_READ_VIEW_CANNOT_HEARTBEAT",
                    view,
                )
            updated = replace(
                view,
                lease_expires_at=lease_expires_at,
                last_heartbeat_at=now,
            )
            store._read_views[view_id] = updated
            return ReadViewResult(
                ReadViewOutcome.HEARTBEAT,
                "READ_VIEW_LEASE_EXTENDED",
                updated,
                durable_transition=True,
            )

    def release(
        self,
        *,
        view_id: str,
        expected_fence: int,
        released_at: str,
    ) -> ReadViewResult:
        _timestamp(released_at)
        store = self._store
        with store._lock:
            view = store._read_views.get(view_id)
            if view is None:
                return ReadViewResult(
                    ReadViewOutcome.NOT_FOUND,
                    "READ_VIEW_NOT_FOUND",
                )
            if view.fencing_token != expected_fence:
                return ReadViewResult(
                    ReadViewOutcome.STALE_FENCE,
                    "READ_VIEW_FENCE_NOT_CURRENT",
                    view,
                )
            if view.status is not ReadViewStatus.OPEN:
                return ReadViewResult(
                    ReadViewOutcome.ALREADY_CLOSED,
                    "READ_VIEW_ALREADY_TERMINAL",
                    view,
                )
            lifecycle = store._lifecycles.get(view.generation_id)
            if lifecycle is None or lifecycle.active_readers <= 0:
                return ReadViewResult(
                    ReadViewOutcome.IDENTITY_CONFLICT,
                    "READER_LEDGER_AND_COUNTER_MISMATCH",
                    view,
                )
            closed = replace(
                view,
                status=ReadViewStatus.CLOSED,
                fencing_token=view.fencing_token + 1,
                last_heartbeat_at=released_at,
            )
            store._read_views[view_id] = closed
            store._lifecycles[view.generation_id] = replace(
                lifecycle,
                active_readers=lifecycle.active_readers - 1,
                state_version=lifecycle.state_version + 1,
            )
            return ReadViewResult(
                ReadViewOutcome.CLOSED,
                "READ_VIEW_CLOSED_AND_READER_COUNT_DECREMENTED_ONCE",
                closed,
                durable_transition=True,
            )

    def reap_expired(self, *, now: str) -> tuple[ReadView, ...]:
        now_value = _timestamp(now)
        store = self._store
        expired: list[ReadView] = []
        with store._lock:
            for view_id, view in tuple(store._read_views.items()):
                if (
                    view.status is not ReadViewStatus.OPEN
                    or _timestamp(view.lease_expires_at) > now_value
                ):
                    continue
                lifecycle = store._lifecycles.get(view.generation_id)
                if lifecycle is None or lifecycle.active_readers <= 0:
                    continue
                terminal = replace(
                    view,
                    status=ReadViewStatus.EXPIRED,
                    fencing_token=view.fencing_token + 1,
                )
                store._read_views[view_id] = terminal
                store._lifecycles[view.generation_id] = replace(
                    lifecycle,
                    active_readers=lifecycle.active_readers - 1,
                    state_version=lifecycle.state_version + 1,
                )
                expired.append(terminal)
        return tuple(expired)

    def reconcile_reader_count(
        self,
        *,
        generation_id: str,
        now: str,
        reason: str,
    ) -> int | None:
        now_value = _timestamp(now)
        if not reason:
            raise ValueError("reader reconciliation requires a reason")
        store = self._store
        with store._lock:
            lifecycle = store._lifecycles.get(generation_id)
            if lifecycle is None:
                return None
            ledger_repaired = False
            for view_id, view in tuple(store._read_views.items()):
                if (
                    view.generation_id == generation_id
                    and view.status is ReadViewStatus.OPEN
                    and _timestamp(view.lease_expires_at) <= now_value
                ):
                    store._read_views[view_id] = replace(
                        view,
                        status=ReadViewStatus.EXPIRED,
                        fencing_token=view.fencing_token + 1,
                    )
                    ledger_repaired = True
            authoritative = sum(
                1
                for view in store._read_views.values()
                if (
                    view.generation_id == generation_id
                    and view.status is ReadViewStatus.OPEN
                    and _timestamp(view.lease_expires_at) > now_value
                )
            )
            previous = lifecycle.active_readers
            if authoritative != previous or ledger_repaired:
                store._lifecycles[generation_id] = replace(
                    lifecycle,
                    active_readers=authoritative,
                    state_version=lifecycle.state_version + 1,
                )
                store._reader_reconciliations.append(
                    (
                        generation_id,
                        previous,
                        authoritative,
                        reason,
                    )
                )
            return authoritative

    def retire(
        self,
        *,
        generation_id: str,
        expected_state_version: int,
        now: str,
    ) -> RetirementResult:
        now_value = _timestamp(now)
        store = self._store
        with store._lock:
            lifecycle = store._lifecycles.get(generation_id)
            if lifecycle is None:
                return RetirementResult(
                    RetirementOutcome.NOT_FOUND,
                    "GENERATION_NOT_FOUND",
                )
            if lifecycle.state is GenerationState.RETIRED:
                return RetirementResult(
                    RetirementOutcome.ALREADY_RETIRED,
                    "GENERATION_ALREADY_RETIRED",
                )
            if lifecycle.state_version != expected_state_version:
                return RetirementResult(
                    RetirementOutcome.STALE_STATE,
                    "GENERATION_STATE_VERSION_CHANGED",
                )
            if lifecycle.state is not GenerationState.DRAINING:
                return RetirementResult(
                    RetirementOutcome.NOT_DRAINING,
                    "ONLY_DRAINING_GENERATIONS_CAN_RETIRE",
                )
            open_views = tuple(
                view
                for view in store._read_views.values()
                if (
                    view.generation_id == generation_id
                    and view.status is ReadViewStatus.OPEN
                )
            )
            if lifecycle.active_readers != len(open_views):
                return RetirementResult(
                    RetirementOutcome.LEDGER_MISMATCH,
                    "READ_VIEW_LEDGER_AND_COUNTER_MISMATCH",
                )
            if open_views or lifecycle.active_readers > 0:
                return RetirementResult(
                    RetirementOutcome.READERS_PRESENT,
                    "ACTIVE_READ_VIEWS_MUST_DRAIN_BEFORE_RETIREMENT",
                )
            if (
                lifecycle.retire_after is None
                or _timestamp(lifecycle.retire_after) > now_value
            ):
                return RetirementResult(
                    RetirementOutcome.RETENTION_NOT_MET,
                    "ROLLBACK_RETENTION_WINDOW_NOT_SATISFIED",
                )
            retired = replace(
                lifecycle,
                state=GenerationState.RETIRED,
                state_version=lifecycle.state_version + 1,
                transition_fence=lifecycle.transition_fence + 1,
            )
            store._lifecycles[generation_id] = retired
            store._transitions.append(
                LifecycleTransitionRecord(
                    generation_id,
                    GenerationState.DRAINING,
                    GenerationState.RETIRED,
                    lifecycle.state_version,
                    retired.state_version,
                    "READERS_DRAINED_AND_RETENTION_POLICY_SATISFIED",
                )
            )
            return RetirementResult(
                RetirementOutcome.RETIRED,
                "GENERATION_RETIRED_WITHOUT_PHYSICAL_PURGE_CLAIM",
                durable_transition=True,
            )
