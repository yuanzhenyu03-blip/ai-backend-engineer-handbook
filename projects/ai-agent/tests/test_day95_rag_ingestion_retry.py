from __future__ import annotations

import unittest

from mcp_retry_policy import (
    BoundedRetryPolicy,
    RetryContext,
    RetryDecisionKind,
    RetryDispatchContext,
    RetryDispatchDecisionKind,
)
from rag_ingestion_committer import (
    DocumentVersionLifecycle,
    DocumentVersionLifecycleRecord,
    InMemoryIngestionLifecycleStore,
    IngestionCommitter,
    IngestionDispatchClaimOutcome,
    IngestionOperationRecord,
    IngestionOperationState,
)
from rag_ingestion_contracts import (
    DocumentHeadSnapshot,
    DocumentHeadState,
    DocumentIdentity,
    DocumentVersionDefinition,
    DocumentVersionIdentity,
    IngestionOperationIdentity,
    ParserAttemptIdentity,
)
from rag_ingestion_retry import (
    IngestionRetryCoordinator,
    IngestionRetryOutcome,
    IngestionRetryRequest,
)


class Day95RAGIngestionRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version = DocumentVersionIdentity(
            "tenant-a", "report-42", "report-42-v2"
        )
        self.operation = IngestionOperationIdentity(
            tenant_id="tenant-a",
            document_id="report-42",
            document_version_id="report-42-v2",
            source_artifact_id="source-report-42-v2",
            operation_id="op-ingest-report-42-v2",
            idempotency_key="idem-ingest-report-42-v2",
        )
        self.old_attempt = ParserAttemptIdentity(
            operation_id=self.operation.operation_id,
            idempotency_key=self.operation.idempotency_key,
            attempt_number=2,
            parser_request_id="parse-request-95-2",
            parser_generation=3,
        )
        self.store = InMemoryIngestionLifecycleStore()
        self.store.register(
            document=DocumentHeadSnapshot(
                DocumentIdentity("tenant-a", "report-42"),
                DocumentHeadState.REGISTERED,
                None,
                0,
                0,
            ),
            version=DocumentVersionLifecycleRecord(
                DocumentVersionDefinition(
                    identity=self.version,
                    source_artifact_id=self.operation.source_artifact_id,
                    parse_contract_version="parser-contract-v1",
                    created_by_operation_id=self.operation.operation_id,
                ),
                DocumentVersionLifecycle.REGISTERED,
                None,
                None,
                0,
                0,
            ),
            operation=IngestionOperationRecord(
                self.operation,
                IngestionOperationState.PROVEN_NOT_EXECUTED,
                3,
                3,
                self.old_attempt,
            ),
        )
        self.coordinator = IngestionRetryCoordinator(
            store=self.store,
            committer=IngestionCommitter(self.store),
            policy=BoundedRetryPolicy(
                base_delay_seconds=0.1,
                maximum_delay_seconds=1.0,
                jitter_ratio=0.0,
            ),
        )

    def request(
        self,
        *,
        parser_request_id: str = "parse-request-95-3",
        retries_used: int = 1,
        max_retries: int = 3,
        authorization_current: bool = True,
        dispatch_authorization_current: bool = True,
    ) -> IngestionRetryRequest:
        return IngestionRetryRequest(
            operation=self.operation,
            new_parser_request_id=parser_request_id,
            current_parser_generation=4,
            retry_context=RetryContext(
                now=100.0,
                deadline=200.0,
                retries_used=retries_used,
                max_retries=max_retries,
                caller_intent_active=True,
                authorization_current=authorization_current,
                capacity_admitted=True,
                circuit_allows_request=True,
            ),
            dispatch_context=RetryDispatchContext(
                now=100.2,
                deadline=200.0,
                caller_intent_active=True,
                authorization_current=dispatch_authorization_current,
                capacity_admitted=True,
                circuit_allows_request=True,
            ),
        )

    def test_eligible_retry_preserves_identity_and_creates_attempt(self) -> None:
        result = self.coordinator.prepare(self.request())

        self.assertEqual(result.outcome, IngestionRetryOutcome.READY_FOR_PREFLIGHT)
        self.assertEqual(result.parser_calls, 0)
        self.assertEqual(result.committer_calls, 1)
        self.assertEqual(result.durable_transitions, 1)
        assert result.attempt is not None
        self.assertEqual(result.attempt.operation_id, self.operation.operation_id)
        self.assertEqual(result.attempt.idempotency_key, self.operation.idempotency_key)
        self.assertEqual(result.attempt.attempt_number, 3)
        self.assertEqual(result.attempt.parser_request_id, "parse-request-95-3")
        self.assertEqual(result.attempt.parser_generation, 4)
        current = self.store.read_operation(self.operation.operation_id)
        self.assertEqual(current.identity, self.operation)
        self.assertEqual(current.state, IngestionOperationState.READY_FOR_DISPATCH)
        self.assertEqual(current.attempt, self.old_attempt)
        self.assertEqual(current.attempt_history, (self.old_attempt,))

    def test_retry_attempt_is_still_claimed_only_after_preflight(self) -> None:
        result = self.coordinator.prepare(self.request())
        assert result.attempt is not None
        self.assertEqual(
            self.store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.READY_FOR_DISPATCH,
        )

        claim = self.store.claim_parse_dispatch(
            identity=self.operation,
            attempt=result.attempt,
            expected_state=result.expected_operation_state,
            expected_state_version=result.expected_operation_state_version,
            expected_fence=result.expected_operation_fence,
        )

        self.assertEqual(claim.outcome, IngestionDispatchClaimOutcome.CLAIMED)
        assert claim.record is not None
        self.assertEqual(
            claim.record.attempt_history,
            (self.old_attempt, result.attempt),
        )

    def test_retry_budget_exhaustion_does_not_change_lifecycle(self) -> None:
        result = self.coordinator.prepare(
            self.request(retries_used=3, max_retries=3)
        )

        self.assertEqual(result.outcome, IngestionRetryOutcome.POLICY_BLOCKED)
        self.assertEqual(
            result.policy_decision,
            RetryDecisionKind.RETRY_BUDGET_EXHAUSTED,
        )
        self.assertEqual(result.committer_calls, 0)
        self.assertEqual(
            self.store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PROVEN_NOT_EXECUTED,
        )

    def test_policy_authorization_gate_blocks_before_durable_transition(self) -> None:
        result = self.coordinator.prepare(
            self.request(authorization_current=False)
        )

        self.assertEqual(result.outcome, IngestionRetryOutcome.POLICY_BLOCKED)
        self.assertEqual(
            result.policy_decision,
            RetryDecisionKind.AUTHORIZATION_NOT_CURRENT,
        )
        self.assertEqual(result.committer_calls, 0)

    def test_fresh_post_backoff_gate_can_revoke_retry(self) -> None:
        result = self.coordinator.prepare(
            self.request(dispatch_authorization_current=False)
        )

        self.assertEqual(
            result.outcome,
            IngestionRetryOutcome.DISPATCH_GATES_BLOCKED,
        )
        self.assertEqual(
            result.dispatch_decision,
            RetryDispatchDecisionKind.AUTHORIZATION_NOT_CURRENT,
        )
        self.assertEqual(result.committer_calls, 0)
        self.assertEqual(
            self.store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PROVEN_NOT_EXECUTED,
        )

    def test_reusing_parser_request_id_is_rejected_without_state_change(self) -> None:
        result = self.coordinator.prepare(
            self.request(parser_request_id=self.old_attempt.parser_request_id)
        )

        self.assertEqual(
            result.outcome,
            IngestionRetryOutcome.ATTEMPT_IDENTITY_CONFLICT,
        )
        self.assertEqual(result.committer_calls, 0)
        self.assertEqual(
            self.store.read_operation(self.operation.operation_id).state,
            IngestionOperationState.PROVEN_NOT_EXECUTED,
        )

    def test_non_authoritative_lifecycle_cannot_enter_retry_policy(self) -> None:
        self.store._operations[self.operation.operation_id] = (
            IngestionOperationRecord(
                self.operation,
                IngestionOperationState.PENDING_RECONCILIATION,
                3,
                3,
                self.old_attempt,
            )
        )

        result = self.coordinator.prepare(self.request())

        self.assertEqual(
            result.outcome,
            IngestionRetryOutcome.LIFECYCLE_NOT_RETRYABLE,
        )
        self.assertEqual(result.committer_calls, 0)


if __name__ == "__main__":
    unittest.main()
