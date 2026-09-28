"""Independent Day96 contract, validation, and in-process commit boundaries."""

from __future__ import annotations

from dataclasses import replace
import threading
import unittest

from examples.day96_active_fixture import active_day95_store
from examples.day96_chunking_experiments import run_example
from rag_chunking_committer import (
    ChunkCommitOutcome,
    ChunkSetCommitter,
    InMemoryChunkSetStore,
    SelectionOutcome,
)
from rag_chunking_contracts import (
    ChunkStrategy,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
    OversizedPolicy,
    SourceSegment,
    candidate_chunks_checksum,
)
from rag_chunking_experiments import ControlledChunkingExperimentRunner
from rag_chunking_normalization import normalize
from rag_chunking_orchestrator import (
    ChunkingRunOutcome,
    ChunkingRunRequest,
    RAGChunkingOrchestrator,
)
from rag_chunking_strategies import ChunkGenerationError, ChunkingStrategyAdapter
from rag_chunking_validator import (
    ChunkSetCandidateValidator,
    ChunkValidationOutcome,
)
from rag_ingestion_contracts import sha256_text
from rag_tokenizer_adapter import ClassroomTokenizer


class Day96ChunkingCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (
            "# Refund policy\n\nPurchase within 30 days.\n\n"
            "| Item | Limit |\n| Book | 30 days |\n\n"
            "```python\ndef refund():\n    return True\n```\n"
        )
        self.day95, self.parsed = active_day95_store(self.text)
        self.tokenizer = ClassroomTokenizer()
        self.contract = ChunkingContract(
            strategy=ChunkStrategy.FIXED_TOKEN,
            strategy_version="1.0.0",
            tokenizer=self.tokenizer.contract,
            normalization_version="identity-v1",
            soft_target_tokens=32,
            hard_max_tokens=40,
            min_useful_tokens=1,
            overlap_tokens=4,
            max_chunk_count=100,
            max_input_chars=1000,
            max_output_chars=2000,
            deadline_seconds=10.0,
            oversized_policy=OversizedPolicy.BOUNDED_FALLBACK,
        )
        self.operation = ChunkingOperationIdentity(
            version=self.parsed.version,
            source_artifact_id=self.parsed.source_artifact_id,
            parsed_artifact_id=self.parsed.parsed_artifact_id,
            operation_id="op-chunk-report-42-v2",
            idempotency_key="idem-chunk-report-42-v2",
            contract_fingerprint=self.contract.fingerprint,
        )
        self.attempt = ChunkingAttemptIdentity(
            self.operation.operation_id, 1, "chunk-request-1", 1
        )
        self.adapter = ChunkingStrategyAdapter(self.tokenizer)
        self.validator = ChunkSetCandidateValidator(self.tokenizer)
        self.chunk_store = InMemoryChunkSetStore()
        self.committer = ChunkSetCommitter(
            day95_store=self.day95,
            chunk_store=self.chunk_store,
            validator=self.validator,
        )

    def candidate(self, contract: ChunkingContract | None = None):
        selected = contract or self.contract
        operation = replace(
            self.operation, contract_fingerprint=selected.fingerprint
        )
        return self.adapter.generate(
            parsed=self.parsed,
            contract=selected,
            operation=operation,
            attempt=self.attempt,
            experiment_id="exp-day96-1",
        )

    def validate(self, candidate, contract=None):
        return self.validator.evaluate(
            document=self.day95.read_document(self.parsed.version.document),
            version=self.day95.read_version(self.parsed.version),
            ingestion=self.day95.read_operation(
                self.parsed.manifest.operation_id
            ),
            parsed=self.parsed,
            source=self.day95.read_source_artifact(
                self.parsed.source_artifact_id
            ),
            contract=contract or self.contract,
            candidate=candidate,
        )

    def test_three_strategies_cover_exact_canonical_source(self) -> None:
        for strategy in ChunkStrategy:
            with self.subTest(strategy=strategy):
                contract = replace(self.contract, strategy=strategy)
                candidate = self.candidate(contract)
                decision = self.validate(candidate, contract)
                self.assertEqual(
                    decision.outcome,
                    ChunkValidationOutcome.READY_FOR_COMMIT,
                    decision.safe_reason,
                )
                self.assertEqual(candidate.manifest.chunk_count, len(candidate.chunks))
                self.assertTrue(all(
                    chunk.token_count <= contract.hard_max_tokens
                    for chunk in candidate.chunks
                ))

    def test_contract_change_changes_stable_result_identity(self) -> None:
        changed = replace(self.contract, overlap_tokens=5)
        self.assertNotEqual(self.contract.fingerprint, changed.fingerprint)
        self.assertNotEqual(
            self.operation.stable_result_key,
            replace(
                self.operation, contract_fingerprint=changed.fingerprint
            ).stable_result_key,
        )
        changed_tokenizer = replace(
            self.contract,
            tokenizer=replace(self.tokenizer.contract, version="2.0.0"),
        )
        self.assertNotEqual(
            self.contract.fingerprint, changed_tokenizer.fingerprint
        )
        changed_normalization = replace(
            self.contract,
            normalization_version="collapse-horizontal-space-v1",
        )
        self.assertNotEqual(
            self.contract.fingerprint, changed_normalization.fingerprint
        )

    def test_normalization_maps_back_to_canonical_offsets(self) -> None:
        source = "退款  期限"
        normalized = normalize(source, "collapse-horizontal-space-v1")
        self.assertEqual(normalized.text, "退款 期限")
        self.assertEqual(normalized.source_interval(3, 5), (4, 6))
        _, parsed = active_day95_store(source)
        contract = replace(
            self.contract,
            normalization_version="collapse-horizontal-space-v1",
            soft_target_tokens=3,
            hard_max_tokens=5,
            overlap_tokens=0,
        )
        operation = replace(
            self.operation,
            parsed_artifact_id=parsed.parsed_artifact_id,
            contract_fingerprint=contract.fingerprint,
        )
        candidate = self.adapter.generate(
            parsed=parsed,
            contract=contract,
            operation=operation,
            attempt=self.attempt,
            experiment_id="exp-normalized",
        )
        self.assertEqual(candidate.chunks[-1].source_segments[-1].end, len(source))
        normalized_main = self.candidate(contract)
        self.assertEqual(
            self.validate(normalized_main, contract).outcome,
            ChunkValidationOutcome.READY_FOR_COMMIT,
        )

    def test_corrupt_manifest_and_gap_fail_before_committer(self) -> None:
        candidate = self.candidate()
        corrupt = replace(
            candidate,
            manifest=replace(candidate.manifest, chunk_count=999),
        )
        self.assertEqual(
            self.validate(corrupt).outcome,
            ChunkValidationOutcome.MANIFEST_CONFLICT,
        )
        first = candidate.chunks[0]
        shifted = replace(
            first,
            source_segments=(SourceSegment(1, first.source_segments[0].end),),
            text=self.text[1:first.source_segments[0].end],
            content_hash=sha256_text(self.text[1:first.source_segments[0].end]),
        )
        changed_chunks = (shifted,) + candidate.chunks[1:]
        gap = replace(
            candidate,
            chunks=changed_chunks,
            manifest=replace(
                candidate.manifest,
                chunks_checksum=candidate_chunks_checksum(changed_chunks),
            ),
        )
        self.assertNotEqual(
            self.validate(gap).outcome,
            ChunkValidationOutcome.READY_FOR_COMMIT,
        )
        self.assertEqual(self.chunk_store.outbox_intents(), ())

    def test_coverage_gap_is_rejected_even_with_consistent_chunk_hash(self) -> None:
        contract = replace(
            self.contract,
            soft_target_tokens=500,
            hard_max_tokens=500,
            overlap_tokens=0,
        )
        candidate = self.candidate(contract)
        self.assertEqual(len(candidate.chunks), 1)
        content = self.text[:-1]
        shortened = replace(
            candidate.chunks[0],
            text=content,
            source_segments=(SourceSegment(0, len(content)),),
            token_count=self.tokenizer.count(content),
            content_hash=sha256_text(content),
        )
        chunks = (shortened,)
        gap = replace(
            candidate,
            chunks=chunks,
            manifest=replace(
                candidate.manifest,
                chunks_checksum=candidate_chunks_checksum(chunks),
            ),
        )
        self.assertEqual(
            self.validate(gap, contract).outcome,
            ChunkValidationOutcome.COVERAGE_GAP,
        )

    def test_repeated_text_has_distinct_chunk_identity_by_source(self) -> None:
        day95, parsed = active_day95_store("same\nsame")
        contract = replace(
            self.contract,
            soft_target_tokens=1,
            hard_max_tokens=1,
            overlap_tokens=0,
        )
        operation = replace(
            self.operation,
            parsed_artifact_id=parsed.parsed_artifact_id,
            contract_fingerprint=contract.fingerprint,
        )
        candidate = self.adapter.generate(
            parsed=parsed,
            contract=contract,
            operation=operation,
            attempt=self.attempt,
            experiment_id="exp-repeated-source",
        )
        validator = ChunkSetCandidateValidator(self.tokenizer)
        source = day95.read_source_artifact(parsed.source_artifact_id)
        assert source is not None
        decision = validator.evaluate(
            document=day95.read_document(parsed.version.document),
            version=day95.read_version(parsed.version),
            ingestion=day95.read_operation(parsed.manifest.operation_id),
            parsed=parsed,
            source=source,
            contract=contract,
            candidate=candidate,
        )
        self.assertTrue(decision.ready, decision.safe_reason)
        committer = ChunkSetCommitter(
            day95_store=day95,
            chunk_store=InMemoryChunkSetStore(),
            validator=validator,
        )
        self.assertIsNotNone(committer.claim(operation, self.attempt))
        result = committer.persist(decision, contract=contract)
        assert result.chunk_set is not None
        first, _, last = result.chunk_set.chunks
        self.assertEqual(first.candidate.content_hash, last.candidate.content_hash)
        self.assertNotEqual(
            first.candidate.source_segments, last.candidate.source_segments
        )
        self.assertNotEqual(first.chunk_id, last.chunk_id)

    def test_exact_retry_converges_without_second_outbox(self) -> None:
        candidate = self.candidate()
        decision = self.validate(candidate)
        claim = self.committer.claim(self.operation, self.attempt)
        assert claim is not None
        first = self.committer.persist(decision, contract=self.contract)
        again = self.committer.persist(decision, contract=self.contract)
        self.assertEqual(first.outcome, ChunkCommitOutcome.COMMITTED)
        self.assertEqual(again.outcome, ChunkCommitOutcome.ALREADY_COMMITTED)
        self.assertEqual(first.chunk_set, again.chunk_set)
        assert first.chunk_set is not None
        document = self.day95.read_document(self.parsed.version.document)
        selected = self.committer.select(
            chunk_set_id=first.chunk_set.chunk_set_id,
            expected_selected_id=None,
            expected_selection_revision=0,
            expected_document_state_version=document.state_version,
            expected_document_fence=document.fence_token,
            claim=claim,
        )
        repeated = self.committer.select(
            chunk_set_id=first.chunk_set.chunk_set_id,
            expected_selected_id=None,
            expected_selection_revision=0,
            expected_document_state_version=document.state_version,
            expected_document_fence=document.fence_token,
            claim=claim,
        )
        self.assertEqual(selected.outcome, SelectionOutcome.SELECTED)
        self.assertEqual(repeated.outcome, SelectionOutcome.ALREADY_SELECTED)
        self.assertEqual(len(self.chunk_store.outbox_intents()), 1)

    def test_repeated_body_span_cannot_fake_full_coverage(self) -> None:
        candidate = self.candidate()
        first = candidate.chunks[0]
        second = candidate.chunks[1]
        repeated = replace(
            second,
            text=first.text,
            source_segments=first.source_segments,
            token_count=first.token_count,
            content_hash=first.content_hash,
        )
        chunks = (first, repeated) + candidate.chunks[2:]
        forged = replace(
            candidate,
            chunks=chunks,
            manifest=replace(
                candidate.manifest,
                chunks_checksum=candidate_chunks_checksum(chunks),
            ),
        )
        self.assertEqual(
            self.validate(forged).outcome,
            ChunkValidationOutcome.SOURCE_SPAN_INVALID,
        )
        self.assertIsNone(self.chunk_store.read_claim(self.operation.operation_id))

    def test_committer_claim_rejects_stale_day95_before_marker(self) -> None:
        previous = self.day95.read_document(self.parsed.version.document)
        with self.day95._lock:
            self.day95._documents[
                (previous.identity.tenant_id, previous.identity.document_id)
            ] = replace(previous, active_version_id="report-42-v3")
        self.assertIsNone(self.committer.claim(self.operation, self.attempt))
        self.assertIsNone(self.chunk_store.read_claim(self.operation.operation_id))

    def test_committer_claim_rejects_parse_lineage_conflict(self) -> None:
        with self.day95._lock:
            self.day95._parsed_artifacts[self.parsed.parsed_artifact_id] = replace(
                self.parsed,
                manifest=replace(
                    self.parsed.manifest,
                    parse_contract_version="different-parser-contract",
                ),
            )
        self.assertIsNone(self.committer.claim(self.operation, self.attempt))
        self.assertIsNone(self.chunk_store.read_claim(self.operation.operation_id))

    def test_failed_new_experiment_preserves_selected_old_set(self) -> None:
        claim = self.committer.claim(self.operation, self.attempt)
        assert claim is not None
        first = self.committer.persist(
            self.validate(self.candidate()),
            contract=self.contract,
        )
        assert first.chunk_set is not None
        document = self.day95.read_document(self.parsed.version.document)
        selected = self.committer.select(
            chunk_set_id=first.chunk_set.chunk_set_id,
            expected_selected_id=None,
            expected_selection_revision=0,
            expected_document_state_version=document.state_version,
            expected_document_fence=document.fence_token,
            claim=claim,
        )
        self.assertEqual(selected.outcome, SelectionOutcome.SELECTED)
        changed = replace(self.contract, strategy=ChunkStrategy.RECURSIVE)
        second_operation = replace(
            self.operation,
            operation_id="op-chunk-rejected-b",
            idempotency_key="idem-chunk-rejected-b",
            contract_fingerprint=changed.fingerprint,
        )
        second_attempt = replace(
            self.attempt, operation_id=second_operation.operation_id
        )
        second = self.adapter.generate(
            parsed=self.parsed,
            contract=changed,
            operation=second_operation,
            attempt=second_attempt,
            experiment_id="exp-rejected-b",
        )
        invalid = replace(
            second,
            manifest=replace(second.manifest, chunk_count=999),
        )
        decision = self.validate(invalid, changed)
        self.assertFalse(decision.ready)
        self.assertEqual(
            self.committer.persist(decision, contract=changed).outcome,
            ChunkCommitOutcome.NOT_READY,
        )
        self.assertEqual(
            self.chunk_store.read_selection(self.parsed.version.document),
            selected.selection,
        )
        self.assertEqual(len(self.chunk_store.outbox_intents()), 1)

    def test_stale_attempt_cannot_persist(self) -> None:
        decision = self.validate(self.candidate())
        first = self.committer.claim(self.operation, self.attempt)
        assert first is not None
        new_attempt = ChunkingAttemptIdentity(
            self.operation.operation_id, 2, "chunk-request-2", 2
        )
        self.assertIsNotNone(self.committer.claim(self.operation, new_attempt))
        result = self.committer.persist(decision, contract=self.contract)
        self.assertEqual(result.outcome, ChunkCommitOutcome.STALE_ATTEMPT)

    def test_active_pointer_change_rejects_selection(self) -> None:
        candidate = self.candidate()
        decision = self.validate(candidate)
        claim = self.committer.claim(self.operation, self.attempt)
        assert claim is not None
        committed = self.committer.persist(decision, contract=self.contract)
        assert committed.chunk_set is not None
        previous = self.day95.read_document(self.parsed.version.document)
        with self.day95._lock:
            self.day95._documents[
                (previous.identity.tenant_id, previous.identity.document_id)
            ] = replace(
                previous,
                active_version_id="report-42-v3",
                state_version=previous.state_version + 1,
                fence_token=previous.fence_token + 1,
            )
        result = self.committer.select(
            chunk_set_id=committed.chunk_set.chunk_set_id,
            expected_selected_id=None,
            expected_selection_revision=0,
            expected_document_state_version=previous.state_version,
            expected_document_fence=previous.fence_token,
            claim=claim,
        )
        self.assertEqual(result.outcome, SelectionOutcome.STALE_DAY95_INPUT)
        self.assertIsNone(
            self.chunk_store.read_selection(self.parsed.version.document)
        )
        self.assertEqual(self.chunk_store.outbox_intents(), ())

    def test_two_workers_only_one_creates_immutable_set(self) -> None:
        decision = self.validate(self.candidate())
        self.assertIsNotNone(self.committer.claim(self.operation, self.attempt))
        results = []
        lock = threading.Lock()

        def worker() -> None:
            result = self.committer.persist(decision, contract=self.contract)
            with lock:
                results.append(result.outcome)

        workers = [threading.Thread(target=worker) for _ in range(2)]
        for worker_thread in workers:
            worker_thread.start()
        for worker_thread in workers:
            worker_thread.join()
        self.assertCountEqual(
            results,
            [ChunkCommitOutcome.COMMITTED, ChunkCommitOutcome.ALREADY_COMMITTED],
        )

    def test_oversized_atomic_unit_fails_closed(self) -> None:
        _, oversized_parsed = active_day95_store("无标点连续超长中文片段")
        contract = replace(
            self.contract,
            strategy=ChunkStrategy.RECURSIVE,
            hard_max_tokens=6,
            soft_target_tokens=5,
            min_useful_tokens=1,
            overlap_tokens=0,
            oversized_policy=OversizedPolicy.FAIL_CLOSED,
        )
        operation = replace(
            self.operation,
            parsed_artifact_id=oversized_parsed.parsed_artifact_id,
            contract_fingerprint=contract.fingerprint,
        )
        with self.assertRaises(ChunkGenerationError):
            self.adapter.generate(
                parsed=oversized_parsed,
                contract=contract,
                operation=operation,
                attempt=self.attempt,
                experiment_id="exp-oversized",
            )

    def test_fail_closed_does_not_hide_oversized_sentence_at_spaces(self) -> None:
        _, parsed = active_day95_store(
            "first second third fourth fifth sixth seventh eighth"
        )
        contract = replace(
            self.contract,
            strategy=ChunkStrategy.RECURSIVE,
            hard_max_tokens=6,
            soft_target_tokens=5,
            overlap_tokens=0,
            oversized_policy=OversizedPolicy.FAIL_CLOSED,
        )
        operation = replace(
            self.operation,
            parsed_artifact_id=parsed.parsed_artifact_id,
            contract_fingerprint=contract.fingerprint,
        )
        with self.assertRaises(ChunkGenerationError):
            self.adapter.generate(
                parsed=parsed,
                contract=contract,
                operation=operation,
                attempt=self.attempt,
                experiment_id="exp-oversized-with-spaces",
            )

    def test_work_and_estimated_memory_budgets_reject_early(self) -> None:
        for override, reason in (
            ({"max_token_work_units": 2}, "TOKEN_WORK_BUDGET_EXCEEDED"),
            ({"max_estimated_memory_bytes": 2},
             "ESTIMATED_MEMORY_BUDGET_EXCEEDED"),
        ):
            with self.subTest(reason=reason):
                contract = replace(self.contract, **override)
                operation = replace(
                    self.operation, contract_fingerprint=contract.fingerprint
                )
                with self.assertRaises(ChunkGenerationError) as raised:
                    self.adapter.generate(
                        parsed=self.parsed,
                        contract=contract,
                        operation=operation,
                        attempt=self.attempt,
                        experiment_id="exp-budget",
                    )
                self.assertEqual(raised.exception.safe_reason, reason)

    def test_controlled_experiment_reports_structure_without_raw_text(self) -> None:
        runner = ControlledChunkingExperimentRunner(
            self.adapter, self.validator
        )
        records = []
        for strategy in ChunkStrategy:
            contract = replace(self.contract, strategy=strategy)
            operation = replace(
                self.operation,
                operation_id="op-" + strategy.value,
                idempotency_key="idem-" + strategy.value,
                contract_fingerprint=contract.fingerprint,
            )
            attempt = replace(
                self.attempt, operation_id=operation.operation_id
            )
            record = runner.run(
                document=self.day95.read_document(self.parsed.version.document),
                version=self.day95.read_version(self.parsed.version),
                ingestion=self.day95.read_operation(
                    self.parsed.manifest.operation_id
                ),
                parsed=self.parsed,
                source=self.day95.read_source_artifact(
                    self.parsed.source_artifact_id
                ),
                contract=contract,
                operation=operation,
                attempt=attempt,
                experiment_id="exp-" + strategy.value,
            )
            self.assertEqual(record.status, "VALIDATED", record.safe_reason)
            assert record.metrics is not None
            self.assertTrue(record.metrics.deterministic_rerun_match)
            self.assertEqual(record.metrics.coverage_ratio, 1.0)
            self.assertEqual(record.metrics.gap_count, 0)
            self.assertNotIn("Refund policy", str(record.safe_report()))
            records.append(record)
        self.assertEqual(len(records), 3)

    def test_section_aware_context_retains_exact_source_segments(self) -> None:
        contract = replace(
            self.contract,
            strategy=ChunkStrategy.SECTION_AWARE,
            soft_target_tokens=12,
            hard_max_tokens=24,
            overlap_tokens=0,
        )
        candidate = self.candidate(contract)
        roles = {
            segment.role
            for chunk in candidate.chunks
            for segment in chunk.source_segments
        }
        self.assertIn("heading-context", roles)
        self.assertIn("table-header-context", roles)
        self.assertEqual(
            self.validate(candidate, contract).outcome,
            ChunkValidationOutcome.READY_FOR_COMMIT,
        )
        context_index = next(
            index
            for index, chunk in enumerate(candidate.chunks)
            if len(chunk.source_segments) > 1
        )
        altered = list(candidate.chunks)
        altered[context_index] = replace(
            altered[context_index], joiner="untrusted-inserted-content"
        )
        altered_chunks = tuple(altered)
        injected = replace(
            candidate,
            chunks=altered_chunks,
            manifest=replace(
                candidate.manifest,
                chunks_checksum=candidate_chunks_checksum(altered_chunks),
            ),
        )
        self.assertEqual(
            self.validate(injected, contract).outcome,
            ChunkValidationOutcome.SOURCE_SPAN_INVALID,
        )

    def test_changed_contract_under_same_operation_is_identity_conflict(self) -> None:
        self.assertIsNotNone(self.committer.claim(self.operation, self.attempt))
        changed = replace(
            self.operation,
            contract_fingerprint=replace(
                self.contract, overlap_tokens=5
            ).fingerprint,
        )
        self.assertIsNone(
            self.committer.claim(
                changed,
                ChunkingAttemptIdentity(
                    changed.operation_id, 2, "chunk-request-2", 2
                ),
            )
        )

    def test_example_rerun_is_deterministic_and_content_safe(self) -> None:
        first = run_example()
        self.assertEqual(first, run_example())
        self.assertEqual(first["selection_outcome"], "SELECTED")
        self.assertEqual(first["outbox_intent_count"], 1)
        self.assertEqual(len(first["experiment_records"]), 4)
        self.assertEqual(
            first["experiment_records"][-1]["safe_reason"],
            "OVERSIZED_ATOMIC_UNIT",
        )
        self.assertTrue(all(
            "contract" in record for record in first["experiment_records"]
        ))
        self.assertNotIn("refund within 30 days", str(first))

    def test_orchestrator_cancellation_and_happy_path(self) -> None:
        orchestrator = RAGChunkingOrchestrator(
            day95_store=self.day95,
            adapter=self.adapter,
            validator=self.validator,
            committer=self.committer,
        )
        request = ChunkingRunRequest(
            self.operation, self.attempt, self.contract, "exp-runtime"
        )
        cancelled = orchestrator.run(replace(request, cancelled=True))
        self.assertEqual(cancelled.outcome, ChunkingRunOutcome.CANCELLED)
        self.assertEqual(cancelled.adapter_calls, 0)
        self.assertIsNone(
            self.chunk_store.read_claim(self.operation.operation_id)
        )
        result = orchestrator.run(request)
        self.assertEqual(result.outcome, ChunkingRunOutcome.COMMITTED)
        self.assertEqual(result.adapter_calls, 1)
        self.assertEqual(result.committer_persist_calls, 1)
        self.assertEqual(result.durable_chunk_set_transitions, 1)
        self.assertIsNone(
            self.chunk_store.read_selection(self.parsed.version.document)
        )

    def test_source_checksum_mismatch_blocks_before_chunk_work(self) -> None:
        source = self.day95.read_source_artifact(
            self.parsed.source_artifact_id
        )
        assert source is not None
        with self.day95._lock:
            self.day95._source_artifacts[source.source_artifact_id] = replace(
                source, checksum_sha256="sha256:corrupted"
            )
        orchestrator = RAGChunkingOrchestrator(
            day95_store=self.day95,
            adapter=self.adapter,
            validator=self.validator,
            committer=self.committer,
        )
        result = orchestrator.run(ChunkingRunRequest(
            self.operation, self.attempt, self.contract, "exp-corrupted"
        ))
        self.assertEqual(result.outcome, ChunkingRunOutcome.INELIGIBLE)
        self.assertEqual(result.adapter_calls, 0)
        self.assertIsNone(
            self.chunk_store.read_claim(self.operation.operation_id)
        )

    def test_committer_rechecks_day95_after_adapter_work(self) -> None:
        day95 = self.day95
        delegate = self.adapter
        parsed = self.parsed

        class StaleAfterGeneration:
            def generate(self, **kwargs):
                candidate = delegate.generate(**kwargs)
                previous = day95.read_document(parsed.version.document)
                with day95._lock:
                    day95._documents[
                        (previous.identity.tenant_id, previous.identity.document_id)
                    ] = replace(
                        previous,
                        active_version_id="report-42-v3",
                        state_version=previous.state_version + 1,
                    )
                return candidate

        orchestrator = RAGChunkingOrchestrator(
            day95_store=self.day95,
            adapter=StaleAfterGeneration(),
            validator=self.validator,
            committer=self.committer,
        )
        result = orchestrator.run(ChunkingRunRequest(
            self.operation, self.attempt, self.contract, "exp-stale"
        ))
        self.assertEqual(result.outcome, ChunkingRunOutcome.COMMIT_REJECTED)
        self.assertIsNone(
            self.chunk_store.read_selection(self.parsed.version.document)
        )


if __name__ == "__main__":
    unittest.main()
