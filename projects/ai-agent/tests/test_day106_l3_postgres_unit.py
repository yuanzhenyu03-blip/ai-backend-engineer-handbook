"""Focused non-Docker tests for the Day106 L3A PostgreSQL boundary."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from rag_capstone_contracts import (
    AnswerReleaseRecord,
    CapstoneRequestBinding,
    DispatchObservation,
    RecoveryAndIncidentRecord,
    ResponseIntent,
    ResponseIntentState,
    RetrievalAndContextReceipt,
)
from rag_capstone_postgres import (
    CapstoneRepositoryOutcome,
    ModelInvocationRecord,
    PostgresRagCapstoneRepository,
    ProviderCallAttempt,
    ProviderCallReceipt,
    ProviderCallStatus,
    ProviderMode,
    RESET_CONFIRMATION,
)
from rag_chunking_contracts import stable_hash


class FakeCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, object]] = []
        self.fetchone_values: list[object] = []
        self.fetchall_values: list[list[object]] = []
        self.rowcount = 1
        self.closed = False
        self.fail_fragment: str | None = None

    def execute(self, query: str, params: object = None) -> None:
        self.executions.append((query, params))
        if self.fail_fragment and self.fail_fragment in " ".join(query.split()):
            raise RuntimeError("injected database failure")

    def fetchone(self) -> object:
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self) -> list[object]:
        return self.fetchall_values.pop(0) if self.fetchall_values else []

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor | None = None) -> None:
        self.fake_cursor = cursor or FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def digest(value: object) -> str:
    return stable_hash(value)


def request_binding() -> CapstoneRequestBinding:
    return CapstoneRequestBinding(
        request_attempt_id="R-L3A-1",
        request_id="Q-L3A-1",
        principal_id="principal-refund",
        tenant_id="tenant-refund",
        action="ANSWER",
        purpose="refund-support",
        audience="customer",
        pointer_name="refund-serving",
        generation_id="G2",
        generation_artifact_digest=digest("G2-artifact"),
        generation_manifest_digest=digest("G2-manifest"),
        build_snapshot_fingerprint=digest("BS1"),
        pointer_revision=8,
        read_view_id="read-view-R-L3A-1",
        read_view_fence=1,
        read_view_digest=digest("read-view-R-L3A-1"),
        source_snapshot_id="S1",
        authorization_snapshot_id="P1",
        deletion_snapshot_id="D1",
        policy_fingerprint=digest("policy-v1"),
        security_binding_fingerprint=digest("security-v1"),
        retrieval_authorization_revision_digest=digest("P1-revision"),
        retrieval_authorization_scope_fingerprint=digest("P1-scope"),
        selected_retrieval_bundle_id="RB-L3A-1",
        selected_retrieval_bundle_revision=1,
        selected_retrieval_bundle_fingerprint=digest("RB-L3A-1"),
        created_at="2026-11-24T01:00:00+00:00",
    )


def retrieval_receipt(
    binding: CapstoneRequestBinding | None = None,
    *,
    unauthorized_prompt_count: int = 0,
) -> RetrievalAndContextReceipt:
    bound = binding or request_binding()
    return RetrievalAndContextReceipt(
        receipt_id="RC-L3A-1",
        request_binding_digest=bound.digest,
        retrieval_operation_id="retrieval-op-L3A-1",
        retrieval_request_id="retrieval-request-L3A-1",
        day101_execution_receipt_digest=digest("day101-receipt"),
        day101_handoff_digest=digest("day101-handoff"),
        prompt_authorization_scope_fingerprint=(
            bound.retrieval_authorization_scope_fingerprint
        ),
        prompt_authorization_revision_digest=(
            bound.retrieval_authorization_revision_digest
        ),
        retrieval_bundle_id=bound.selected_retrieval_bundle_id,
        retrieval_bundle_digest=digest("RB-L3A-1-content"),
        retrieval_security_decision_digest=digest("retrieval-security"),
        bundle_security_decision_digest=digest("bundle-security"),
        exact_occurrence_ids=("A@v1", "C@v1"),
        exact_content_digests=(digest("A-content"), digest("C-content")),
        context_manifest_id="CM-L3A-1",
        context_manifest_digest=digest("CM-L3A-1"),
        context_occurrence_ids=("A@v1", "C@v1"),
        assembled_context_digest=digest("assembled-context"),
        unauthorized_prompt_count=unauthorized_prompt_count,
        created_at="2026-11-24T01:00:01+00:00",
    )


def release_record(
    binding: CapstoneRequestBinding | None = None,
    receipt: RetrievalAndContextReceipt | None = None,
) -> AnswerReleaseRecord:
    bound = binding or request_binding()
    retrieval = receipt or retrieval_receipt(bound)
    return AnswerReleaseRecord(
        record_id="release-record-L3A-1",
        request_binding_digest=bound.digest,
        retrieval_context_receipt_digest=retrieval.digest,
        model_invocation_id="MI-L3A-1",
        model_invocation_digest=digest("MI-L3A-1"),
        answer_candidate_id="AC-L3A-1",
        answer_candidate_digest=digest("AC-L3A-1"),
        release_evidence_id="RE-L3A-1",
        release_evidence_digest=digest("RE-L3A-1"),
        output_release_decision_id="ORD-L3A-1",
        output_release_decision_digest=digest("ORD-L3A-1"),
        disclosure_envelope_digest=digest("DE-L3A-1"),
        tenant_id=bound.tenant_id,
        principal_id=bound.principal_id,
        action=bound.action,
        purpose=bound.purpose,
        current_authorization_scope_fingerprint=digest("P1-current-scope"),
        current_authorization_revision_digest=digest("P1-current-revision"),
        release_currentness_snapshot_id="CURRENT-L3A-1",
        release_currentness_snapshot_digest=digest("CURRENT-L3A-1"),
        release_currentness_revision=1,
        released_occurrence_ids=("A@v1", "C@v1"),
        authorized_destination="response-channel",
        dispatch_idempotency_key="dispatch-key-L3A-1",
        result="PASS",
        disposition="RELEASE",
        safe_reason_codes=(),
        response_intent_id="intent-L3A-1",
        response_dispatch_state=ResponseIntentState.PENDING,
        created_at="2026-11-24T01:00:02+00:00",
    )


def response_intent(release: AnswerReleaseRecord | None = None) -> ResponseIntent:
    bound = release or release_record()
    assert bound.response_intent_id is not None
    assert bound.authorized_destination is not None
    assert bound.dispatch_idempotency_key is not None
    return ResponseIntent(
        intent_id=bound.response_intent_id,
        request_binding_digest=bound.request_binding_digest,
        output_release_decision_digest=bound.output_release_decision_digest,
        candidate_digest=bound.answer_candidate_digest,
        destination=bound.authorized_destination,
        dispatch_idempotency_key=bound.dispatch_idempotency_key,
        state=ResponseIntentState.PENDING,
        revision=1,
        created_at=bound.created_at,
    )


def recovery_record(
    record_id: str,
    observation: DispatchObservation,
    *,
    previous: str | None = None,
    provider_message_id: str | None = None,
    transport_attempt_id: str = "transport-L3A-1",
) -> RecoveryAndIncidentRecord:
    return RecoveryAndIncidentRecord(
        record_id=record_id,
        response_intent_id="intent-L3A-1",
        previous_record_id=previous,
        transport_attempt_id=transport_attempt_id,
        dispatch_idempotency_key="dispatch-key-L3A-1",
        observation=observation,
        safe_reason_code=f"{observation.value}_OBSERVED",
        observed_at="2026-11-24T01:00:03+00:00",
        evidence_digests=(digest(("evidence", record_id)),),
        provider_message_id=provider_message_id,
    )


def provider_call_receipt() -> ProviderCallReceipt:
    binding = request_binding()
    receipt = retrieval_receipt(binding)
    return ProviderCallReceipt(
        receipt_id="provider-call-L3B-1",
        provider_attempt_id="provider-attempt-L3B-1",
        request_binding_digest=binding.digest,
        retrieval_context_receipt_digest=receipt.digest,
        model_invocation_id="MI-L3A-1",
        model_invocation_digest=digest("MI-L3A-1"),
        call_ordinal=1,
        requested_model_id="gpt-model-requested",
        observed_model_id="gpt-model-observed",
        provider_response_id_digest=digest("raw-provider-response-id"),
        answer_candidate_digest=digest("AC-L3A-1"),
        input_token_count=100,
        output_token_count=20,
        total_token_count=120,
        status=ProviderCallStatus.SUCCEEDED,
        safe_reason_code="PROVIDER_CALL_SUCCEEDED",
        observed_at="2026-11-24T01:00:02+00:00",
    )


def model_invocation(
    provider_mode: ProviderMode = ProviderMode.DETERMINISTIC,
) -> ModelInvocationRecord:
    binding = request_binding()
    receipt = retrieval_receipt(binding)
    return ModelInvocationRecord(
        model_invocation_id="MI-L3A-1",
        model_invocation_digest=digest("MI-L3A-1"),
        request_binding_digest=binding.digest,
        retrieval_context_receipt_digest=receipt.digest,
        retrieval_bundle_digest=receipt.retrieval_bundle_digest,
        context_manifest_digest=receipt.context_manifest_digest,
        provider_mode=provider_mode,
        provider_identity_digest=digest(("provider", provider_mode.value)),
        model_identity_digest=digest(("model", provider_mode.value)),
        config_digest=digest("model-config"),
        contract_digest=digest("provider-contract"),
        created_at="2026-11-24T01:00:01+00:00",
    )


def provider_attempt() -> ProviderCallAttempt:
    invocation = model_invocation(ProviderMode.EXTERNAL)
    return ProviderCallAttempt(
        attempt_id="provider-attempt-L3B-1",
        request_binding_digest=invocation.request_binding_digest,
        retrieval_context_receipt_digest=invocation.retrieval_context_receipt_digest,
        model_invocation_id=invocation.model_invocation_id,
        model_invocation_digest=invocation.model_invocation_digest,
        call_ordinal=1,
        provider_request_idempotency_digest=digest("provider-idempotency-1"),
        created_at="2026-11-24T01:00:01+00:00",
    )


def repository(connection: FakeConnection, *, enabled: bool = True) -> PostgresRagCapstoneRepository:
    return PostgresRagCapstoneRepository(
        lambda: connection,  # type: ignore[arg-type,return-value]
        integration_enabled=enabled,
    )


class Day106L3ARepositoryTests(unittest.TestCase):
    def test_integration_flag_fails_closed_before_connect(self) -> None:
        calls = 0

        def connect() -> FakeConnection:
            nonlocal calls
            calls += 1
            return FakeConnection()

        with tempfile.TemporaryDirectory() as directory:
            schema = Path(directory) / "schema.sql"
            schema.write_text("SELECT 1;", encoding="utf-8")
            repo = PostgresRagCapstoneRepository(
                connect,  # type: ignore[arg-type]
                integration_enabled=False,
                schema_path=schema,
            )
            with self.assertRaisesRegex(RuntimeError, "DAY106_L3_INTEGRATION"):
                repo.install_schema()
        self.assertEqual(calls, 0)

    def test_cross_binding_checks_real_readview_and_exact_points(self) -> None:
        binding = request_binding()
        receipt = retrieval_receipt(binding)
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            None,
            (
                binding.pointer_name,
                binding.generation_id,
                binding.pointer_revision,
                binding.read_view_fence,
                binding.build_snapshot_fingerprint,
                binding.authorization_snapshot_id,
                "OPEN",
                binding.generation_manifest_digest,
                "ACTIVE",
                binding.source_snapshot_id,
                binding.deletion_snapshot_id,
            ),
            (
                binding.authorization_snapshot_id,
                1,
                binding.authorization_snapshot_id,
                list(receipt.exact_occurrence_ids),
                binding.policy_fingerprint,
            ),
        ]
        cursor.fetchall_values = [[
            ("A@v1", receipt.exact_content_digests[0], binding.tenant_id),
            ("C@v1", receipt.exact_content_digests[1], binding.tenant_id),
        ]]
        connection = FakeConnection(cursor)

        result = repository(connection).append_cross_bound_execution(binding, receipt)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.APPLIED)
        self.assertEqual(connection.commits, 1)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("FROM day104_l3.read_views", sql)
        self.assertIn("FROM day104_l3.index_points", sql)
        self.assertIn("FROM day105_l3.current_security_snapshots", sql)
        self.assertIn("INSERT INTO day106_l3.request_bindings", sql)
        self.assertIn("INSERT INTO day106_l3.retrieval_context_receipts", sql)

    def test_cross_binding_rejects_unauthorized_prompt_before_connect(self) -> None:
        binding = request_binding()
        receipt = retrieval_receipt(binding, unauthorized_prompt_count=1)
        connection = FakeConnection()
        with self.assertRaisesRegex(ValueError, "must equal zero"):
            repository(connection).append_cross_bound_execution(binding, receipt)
        self.assertEqual(connection.commits, 0)

    def test_cross_binding_rejects_stale_day105_current_security_snapshot(self) -> None:
        binding = request_binding()
        receipt = retrieval_receipt(binding)
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            None,
            (
                binding.pointer_name,
                binding.generation_id,
                binding.pointer_revision,
                binding.read_view_fence,
                binding.build_snapshot_fingerprint,
                binding.authorization_snapshot_id,
                "OPEN",
                binding.generation_manifest_digest,
                "ACTIVE",
                binding.source_snapshot_id,
                binding.deletion_snapshot_id,
            ),
            ("P0", 1, "P0", list(receipt.exact_occurrence_ids), binding.policy_fingerprint),
        ]
        cursor.fetchall_values = [[
            ("A@v1", receipt.exact_content_digests[0], binding.tenant_id),
            ("C@v1", receipt.exact_content_digests[1], binding.tenant_id),
        ]]
        with self.assertRaisesRegex(ValueError, "CURRENT_SECURITY"):
            repository(FakeConnection(cursor)).append_cross_bound_execution(
                binding,
                receipt,
            )

    def test_release_and_intent_are_one_transaction_and_store_only_digests(self) -> None:
        release = release_record()
        intent = response_intent(release)
        cursor = FakeCursor()
        cursor.fetchone_values = [None, None, (ProviderMode.DETERMINISTIC.value,)]
        connection = FakeConnection(cursor)

        result = repository(connection).commit_release_and_intent(release, intent)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.APPLIED)
        self.assertEqual(connection.commits, 1)
        inserts = [item for item in cursor.executions if "INSERT INTO" in item[0]]
        self.assertEqual(len(inserts), 2)
        serialized_params = repr(tuple(params for _, params in inserts))
        self.assertNotIn(intent.destination, serialized_params)
        self.assertNotIn(intent.dispatch_idempotency_key, serialized_params)

    def test_intent_insert_failure_rolls_back_release(self) -> None:
        release = release_record()
        intent = response_intent(release)
        cursor = FakeCursor()
        cursor.fetchone_values = [None, None, (ProviderMode.DETERMINISTIC.value,)]
        cursor.fail_fragment = "INSERT INTO day106_l3.response_intents"
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "injected"):
            repository(connection).commit_release_and_intent(release, intent)

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_send_started_appends_without_claiming_winner(self) -> None:
        item = recovery_record("dispatch-1", DispatchObservation.SEND_STARTED)
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            (stable_hash(("DAY106_DISPATCH_IDEMPOTENCY_KEY", item.dispatch_idempotency_key)),),
            None,
            ("PENDING",),
        ]
        cursor.fetchall_values = [[]]
        connection = FakeConnection(cursor)

        result = repository(connection).append_recovery_record(item)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.APPLIED)
        event_insert = next(
            params
            for query, params in cursor.executions
            if "INSERT INTO day106_l3.dispatch_recovery_delivery_records" in query
        )
        self.assertEqual(event_insert[9], "NONE")  # type: ignore[index]

    def test_not_found_reconciliation_does_not_require_send_on_reconcile_transport(
        self,
    ) -> None:
        item = recovery_record(
            "dispatch-not-found",
            DispatchObservation.NOT_FOUND,
            previous="dispatch-unknown",
            transport_attempt_id="reconcile-query-1",
        )
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            (
                stable_hash(
                    (
                        "DAY106_DISPATCH_IDEMPOTENCY_KEY",
                        item.dispatch_idempotency_key,
                    )
                ),
            ),
            None,
            ("PENDING",),
        ]
        cursor.fetchall_values = [[("dispatch-unknown",)]]

        result = repository(FakeConnection(cursor)).append_recovery_record(item)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.APPLIED)
        inserted = next(
            params
            for query, params in cursor.executions
            if "INSERT INTO day106_l3.dispatch_recovery_delivery_records" in query
        )
        self.assertEqual(inserted[3], "reconcile-query-1")  # type: ignore[index]
        self.assertEqual(inserted[5], DispatchObservation.NOT_FOUND.value)  # type: ignore[index]

    def test_duplicate_receipt_uses_existing_winner_without_reconcile_send(self) -> None:
        provider_message_id = "provider-message-winner"
        item = recovery_record(
            "dispatch-duplicate",
            DispatchObservation.DUPLICATE_RECEIPT,
            previous="dispatch-delivered",
            provider_message_id=provider_message_id,
            transport_attempt_id="delivery-reconcile-2",
        )
        provider_digest = stable_hash(
            ("DAY106_PROVIDER_MESSAGE_ID", provider_message_id)
        )
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            (
                stable_hash(
                    (
                        "DAY106_DISPATCH_IDEMPOTENCY_KEY",
                        item.dispatch_idempotency_key,
                    )
                ),
            ),
            (
                "dispatch-accepted",
                provider_digest,
                "transport-L3A-1",
                digest("winner-identity"),
            ),
            ("DELIVERED",),
        ]
        cursor.fetchall_values = [[("dispatch-delivered",)]]

        result = repository(FakeConnection(cursor)).append_recovery_record(item)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.LATE_DUPLICATE)
        inserted = next(
            params
            for query, params in cursor.executions
            if "INSERT INTO day106_l3.dispatch_recovery_delivery_records" in query
        )
        self.assertEqual(inserted[3], "delivery-reconcile-2")  # type: ignore[index]
        self.assertEqual(inserted[9], "DUPLICATE")  # type: ignore[index]

    def test_provider_receipt_is_cross_bound_append_only_and_content_safe(self) -> None:
        item = provider_call_receipt()
        cursor = FakeCursor()
        cursor.fetchone_values = [None, None]
        connection = FakeConnection(cursor)

        result = repository(connection).append_provider_call_receipt(item)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.APPLIED)
        insert = next(
            (query, params)
            for query, params in cursor.executions
            if "INSERT INTO day106_l3.provider_call_receipts" in query
        )
        self.assertIn(item.request_binding_digest, insert[1])  # type: ignore[operator]
        self.assertIn(item.retrieval_context_receipt_digest, insert[1])  # type: ignore[operator]
        serialized = repr(insert[1])
        self.assertNotIn("raw-provider-response-id", serialized)
        self.assertNotIn("prompt", serialized.lower())
        self.assertNotIn("answer text", serialized.lower())

    def test_provider_receipt_rejects_raw_provider_response_identity(self) -> None:
        item = provider_call_receipt()
        with self.assertRaisesRegex(ValueError, "sha256 digest"):
            ProviderCallReceipt(
                **{
                    **item.__dict__,
                    "provider_response_id_digest": "provider-response-raw-123",
                }
            )

    def test_failed_or_unknown_provider_outcome_allows_unobserved_fields(self) -> None:
        complete = provider_call_receipt()
        for status in (ProviderCallStatus.FAILED, ProviderCallStatus.UNKNOWN):
            with self.subTest(status=status):
                incomplete = ProviderCallReceipt(
                    **{
                        **complete.__dict__,
                        "receipt_id": f"provider-{status.value.lower()}",
                        "observed_model_id": None,
                        "provider_response_id_digest": None,
                        "answer_candidate_digest": None,
                        "input_token_count": None,
                        "output_token_count": None,
                        "total_token_count": None,
                        "status": status,
                        "safe_reason_code": f"PROVIDER_{status.value}",
                    }
                )
                self.assertIsNone(incomplete.observed_model_id)
                self.assertIsNone(incomplete.total_token_count)

    def test_failed_provider_outcome_round_trips_null_observations(self) -> None:
        complete = provider_call_receipt()
        failed = ProviderCallReceipt(
            **{
                **complete.__dict__,
                "receipt_id": "provider-failed-roundtrip",
                "observed_model_id": None,
                "provider_response_id_digest": None,
                "answer_candidate_digest": None,
                "input_token_count": None,
                "output_token_count": None,
                "total_token_count": None,
                "status": ProviderCallStatus.FAILED,
                "safe_reason_code": "PROVIDER_TIMEOUT",
            }
        )
        write_cursor = FakeCursor()
        write_cursor.fetchone_values = [None, None]
        write_result = repository(
            FakeConnection(write_cursor)
        ).append_provider_call_receipt(failed)
        self.assertEqual(write_result.outcome, CapstoneRepositoryOutcome.APPLIED)

        read_cursor = FakeCursor()
        read_cursor.fetchall_values = [[
            (
                failed.receipt_id,
                failed.provider_attempt_id,
                failed.request_binding_digest,
                failed.retrieval_context_receipt_digest,
                failed.model_invocation_id,
                failed.model_invocation_digest,
                failed.call_ordinal,
                failed.requested_model_id,
                None,
                None,
                None,
                None,
                None,
                None,
                failed.status.value,
                failed.safe_reason_code,
                failed.observed_at,
            )
        ]]
        observed = repository(
            FakeConnection(read_cursor)
        ).read_provider_call_receipts(failed.request_binding_digest)
        self.assertEqual(observed, (failed,))

    def test_successful_provider_outcome_requires_complete_observation(self) -> None:
        complete = provider_call_receipt()
        with self.assertRaisesRegex(ValueError, "complete observed evidence"):
            ProviderCallReceipt(
                **{
                    **complete.__dict__,
                    "observed_model_id": None,
                    "input_token_count": None,
                    "output_token_count": None,
                    "total_token_count": None,
                }
            )

    def test_model_invocation_rejects_noncanonical_digest(self) -> None:
        invocation = model_invocation()
        with self.assertRaisesRegex(ValueError, "canonical sha256"):
            ModelInvocationRecord(
                **{
                    **invocation.__dict__,
                    "contract_digest": "not-a-digest",
                }
            )

    def test_model_invocation_and_external_attempt_are_pre_send_records(self) -> None:
        invocation = model_invocation(ProviderMode.EXTERNAL)
        invocation_cursor = FakeCursor()
        invocation_cursor.fetchone_values = [None]
        invocation_result = repository(
            FakeConnection(invocation_cursor)
        ).append_model_invocation(invocation)
        self.assertEqual(invocation_result.outcome, CapstoneRepositoryOutcome.APPLIED)
        self.assertTrue(
            any(
                "INSERT INTO day106_l3.model_invocations" in query
                for query, _ in invocation_cursor.executions
            )
        )

        attempt = provider_attempt()
        attempt_cursor = FakeCursor()
        attempt_cursor.fetchone_values = [
            None,
            None,
            (ProviderMode.EXTERNAL.value,),
        ]
        attempt_result = repository(
            FakeConnection(attempt_cursor)
        ).reserve_provider_call_attempt(attempt)
        self.assertEqual(attempt_result.outcome, CapstoneRepositoryOutcome.APPLIED)

    def test_external_release_without_exact_success_receipt_is_blocked(self) -> None:
        release = release_record()
        intent = response_intent(release)
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            None,
            (ProviderMode.EXTERNAL.value,),
            None,
        ]
        result = repository(FakeConnection(cursor)).commit_release_and_intent(
            release,
            intent,
        )
        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.INTEGRITY_FAILED)
        self.assertEqual(
            result.safe_reason,
            "EXTERNAL_RELEASE_REQUIRES_EXACT_SUCCEEDED_PROVIDER_RECEIPT",
        )
        self.assertFalse(
            any("INSERT INTO" in query for query, _ in cursor.executions)
        )

    def test_external_release_with_exact_success_receipt_can_commit(self) -> None:
        release = release_record()
        intent = response_intent(release)
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            None,
            (ProviderMode.EXTERNAL.value,),
            ("provider-call-L3B-1",),
        ]
        result = repository(FakeConnection(cursor)).commit_release_and_intent(
            release,
            intent,
        )
        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.APPLIED)

    def test_deterministic_invocation_cannot_reserve_external_attempt(self) -> None:
        attempt = provider_attempt()
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            None,
            (ProviderMode.DETERMINISTIC.value,),
        ]
        result = repository(FakeConnection(cursor)).reserve_provider_call_attempt(
            attempt
        )
        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.INTEGRITY_FAILED)

    def test_first_accepted_result_claims_insert_only_winner_fence(self) -> None:
        item = recovery_record(
            "dispatch-2",
            DispatchObservation.ACCEPTED,
            previous="dispatch-1",
            provider_message_id="provider-message-1",
        )
        cursor = FakeCursor()
        cursor.fetchone_values = [
            None,
            (stable_hash(("DAY106_DISPATCH_IDEMPOTENCY_KEY", item.dispatch_idempotency_key)),),
            None,
            ("DISPATCHED",),
        ]
        cursor.fetchall_values = [[("dispatch-1",)]]
        connection = FakeConnection(cursor)

        result = repository(connection).append_recovery_record(item)

        self.assertEqual(result.outcome, CapstoneRepositoryOutcome.WINNER)
        sql = "\n".join(query for query, _ in cursor.executions)
        self.assertIn("INSERT INTO day106_l3.dispatch_winners", sql)
        self.assertIn("INSERT INTO day106_l3.dispatch_recovery_delivery_records", sql)
        self.assertNotIn("UPDATE day106_l3.dispatch_winners", sql)

    def test_reset_requires_exact_confirmation_and_database(self) -> None:
        connection = FakeConnection()
        repo = repository(connection)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            repo.reset_lab_schemas(confirmation="yes")

        connection.fake_cursor.fetchone_values = [("not-day106",)]
        with self.assertRaisesRegex(ValueError, "day106_l3 database"):
            repo.reset_lab_schemas(confirmation=RESET_CONFIRMATION)
        self.assertEqual(connection.rollbacks, 1)


class Day106L3ASchemaContractTests(unittest.TestCase):
    def test_schema_declares_append_only_cross_binding_and_winner_contracts(self) -> None:
        schema = (
            Path(__file__).resolve().parents[1]
            / "integration"
            / "day106"
            / "schema.sql"
        ).read_text(encoding="utf-8")
        for required in (
            "request_bindings",
            "retrieval_context_receipts",
            "model_invocations",
            "provider_call_attempts",
            "provider_call_receipts",
            "answer_release_records",
            "response_intents",
            "dispatch_winners",
            "dispatch_recovery_delivery_records",
            "reject_row_mutation",
            "unauthorized_prompt_count",
            "sha256_digest_is_valid",
            "IDEMPOTENCY_CONFLICT",
            "RESET_DAY106_L3_SCHEMAS",
        ):
            self.assertIn(required, schema)
        self.assertNotIn("DROP DATABASE", schema.upper())
        self.assertLess(
            schema.index("winner_status = 'CONFLICT'"),
            schema.index("item.observation = 'DELIVERED'"),
        )

    def test_reconciliation_and_duplicate_receipt_do_not_require_send(self) -> None:
        schema = (
            Path(__file__).resolve().parents[1]
            / "integration"
            / "day106"
            / "schema.sql"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "NEW.observation IN ('UNKNOWN', 'ACCEPTED', 'DELIVERED')",
            schema,
        )
        self.assertNotIn("NEW.observation <> 'SEND_STARTED' AND NOT EXISTS", schema)
        self.assertIn("NEW.observation = 'NOT_FOUND' AND NOT EXISTS", schema)
        self.assertIn("observation = 'UNKNOWN'", schema)
        self.assertIn("observed_at < NEW.observed_at", schema)
        self.assertIn("NEW.observation = 'DUPLICATE_RECEIPT'", schema)
        self.assertIn(
            "winner.provider_message_digest IS DISTINCT FROM NEW.provider_message_digest",
            schema,
        )


if __name__ == "__main__":
    unittest.main()
