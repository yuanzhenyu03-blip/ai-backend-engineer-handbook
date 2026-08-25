"""Day74 deterministic output-contract and tool-admission tests.

These are EXECUTED_LOCAL_RUNTIME tests for pure functions and in-memory state
models.  They do not call a Provider, SDK, HTTP endpoint, database, queue, or
real tool and do not prove external exactly-once execution.
"""

import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from output_tool_contracts import (  # noqa: E402
    AdmissionStatus,
    AuthContext,
    CompletionStatus,
    ExecutionStatus,
    InMemoryDurableStore,
    InMemoryToolExecutor,
    JobRecord,
    JobStatus,
    OutcomeDecision,
    OutcomeStatus,
    ToolDefinition,
    ToolRegistry,
    admit_tool_call,
    default_registry,
    default_report_store,
    validate_schema_subset,
    verify_publish_outcome,
)


def candidate(**changes):
    value = {
        "kind": "tool_call",
        "tool_call_id": "tc-1",
        "tool_name": "publish_report",
        "tool_version": "v1",
        "arguments": {
            "tenant_id": "tenant-a",
            "report_id": "report-7",
        },
    }
    value.update(changes)
    return json.dumps(value)


class Day74Fixture:
    def setUp(self):
        self.registry = default_registry()
        self.reports = default_report_store()
        self.publisher = AuthContext(
            tenant_id="tenant-a",
            user_id="user-1",
            role="publisher",
        )

    def admit(self, raw, auth=None):
        return admit_tool_call(
            raw,
            attempt_id="A1",
            job_id="job-1",
            registry=self.registry,
            auth=auth or self.publisher,
            reports=self.reports,
        )


class Day74AdmissionTests(Day74Fixture, unittest.TestCase):

    def test_malformed_json_is_parse_failure(self):
        result = self.admit('{"kind": "tool_call"')
        self.assertIs(result.status, AdmissionStatus.PARSE_FAILURE)

    def test_valid_json_array_is_schema_invalid_not_parse_failure(self):
        result = self.admit("[]")
        self.assertIs(result.status, AdmissionStatus.SCHEMA_INVALID)

    def test_missing_required_field_is_schema_invalid(self):
        result = self.admit(candidate(tool_call_id=""))
        self.assertIs(result.status, AdmissionStatus.SCHEMA_INVALID)

    def test_wrong_report_id_type_is_schema_invalid(self):
        raw = candidate(
            arguments={"tenant_id": "tenant-a", "report_id": 7},
        )
        self.assertIs(self.admit(raw).status, AdmissionStatus.SCHEMA_INVALID)

    def test_empty_report_id_is_schema_invalid(self):
        raw = candidate(
            arguments={"tenant_id": "tenant-a", "report_id": ""},
        )
        self.assertIs(self.admit(raw).status, AdmissionStatus.SCHEMA_INVALID)

    def test_unknown_force_field_is_schema_invalid(self):
        raw = candidate(
            arguments={
                "tenant_id": "tenant-a",
                "report_id": "report-7",
                "force": True,
            },
        )
        self.assertIs(self.admit(raw).status, AdmissionStatus.SCHEMA_INVALID)

    def test_unknown_envelope_field_is_schema_invalid(self):
        result = self.admit(candidate(provider_debug=True))
        self.assertIs(result.status, AdmissionStatus.SCHEMA_INVALID)

    def test_unknown_tool_fails_closed(self):
        result = self.admit(candidate(tool_name="delete_report"))
        self.assertIs(result.status, AdmissionStatus.UNKNOWN_TOOL)
        self.assertIsNone(result.admitted_call)

    def test_incompatible_tool_version_fails_closed(self):
        result = self.admit(candidate(tool_version="v2"))
        self.assertIs(
            result.status,
            AdmissionStatus.INCOMPATIBLE_TOOL_VERSION,
        )

    def test_disabled_tool_version_cannot_be_admitted(self):
        self.registry.disable("publish_report", "v1")
        result = self.admit(candidate())
        self.assertIs(result.status, AdmissionStatus.TOOL_DISABLED)
        self.assertIsNone(result.admitted_call)

    def test_model_tenant_cannot_override_server_tenant(self):
        raw = candidate(
            arguments={"tenant_id": "tenant-b", "report_id": "report-7"},
        )
        self.assertIs(self.admit(raw).status, AdmissionStatus.UNAUTHORIZED)

    def test_viewer_cannot_publish(self):
        viewer = AuthContext("tenant-a", "user-2", "viewer")
        result = self.admit(candidate(), auth=viewer)
        self.assertIs(result.status, AdmissionStatus.UNAUTHORIZED)

    def test_already_published_report_is_semantically_invalid(self):
        raw = candidate(
            arguments={
                "tenant_id": "tenant-a",
                "report_id": "report-published",
            },
        )
        result = self.admit(raw)
        self.assertIs(result.status, AdmissionStatus.SEMANTICALLY_INVALID)
        self.assertEqual(result.safe_reason_code, "REPORT_NOT_PUBLISHABLE")

    def test_missing_report_uses_same_safe_semantic_failure(self):
        raw = candidate(
            arguments={
                "tenant_id": "tenant-a",
                "report_id": "report-missing",
            },
        )
        result = self.admit(raw)
        self.assertIs(result.status, AdmissionStatus.SEMANTICALLY_INVALID)
        self.assertEqual(result.safe_reason_code, "REPORT_NOT_PUBLISHABLE")

    def test_valid_candidate_is_server_normalized_but_not_executed(self):
        result = self.admit(candidate())
        self.assertIs(result.status, AdmissionStatus.ALLOWED)
        self.assertIsNotNone(result.admitted_call)
        admitted = result.admitted_call
        self.assertEqual(admitted.attempt_id, "A1")
        self.assertEqual(admitted.job_id, "job-1")
        self.assertEqual(admitted.tenant_id, "tenant-a")
        self.assertEqual(admitted.report_id, "report-7")
        self.assertEqual(admitted.expected_report_version, 7)
        self.assertTrue(admitted.idempotency_key.startswith("sha256:"))

    def test_duplicate_registry_definition_is_rejected(self):
        definition = ToolDefinition("tool", "v1", {"type": "object"})
        with self.assertRaises(ValueError):
            ToolRegistry((definition, definition))


class Day74SchemaSubsetTests(unittest.TestCase):
    def test_bool_is_not_an_integer(self):
        errors = validate_schema_subset(True, {"type": "integer"})
        self.assertTrue(errors)

    def test_array_items_are_recursively_checked(self):
        schema = {"type": "array", "items": {"type": "string"}}
        errors = validate_schema_subset(["ok", 7], schema)
        self.assertEqual(errors, ("$[1]: expected string",))

    def test_unsupported_keyword_fails_closed(self):
        with self.assertRaises(ValueError):
            validate_schema_subset("x", {"type": "string", "pattern": "x"})


class Day74ExecutionAndOutcomeTests(Day74Fixture, unittest.TestCase):
    def admitted(self):
        return self.admit(candidate()).admitted_call

    def test_duplicate_execution_is_suppressed(self):
        admitted = self.admitted()
        executor = InMemoryToolExecutor()
        first = executor.execute(admitted, registry=self.registry)
        duplicate = executor.execute(admitted, registry=self.registry)
        self.assertIs(first.status, ExecutionStatus.EXECUTED)
        self.assertIs(duplicate.status, ExecutionStatus.DUPLICATE_SUPPRESSED)
        self.assertEqual(first.operation_id, duplicate.operation_id)
        self.assertEqual(executor.effect_count(admitted), 1)

    def test_concurrent_duplicates_produce_one_simulated_effect(self):
        admitted = self.admitted()
        executor = InMemoryToolExecutor()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda _: executor.execute(
                        admitted,
                        registry=self.registry,
                    ),
                    range(8),
                )
            )
        statuses = [result.status for result in results]
        self.assertEqual(statuses.count(ExecutionStatus.EXECUTED), 1)
        self.assertEqual(
            statuses.count(ExecutionStatus.DUPLICATE_SUPPRESSED),
            7,
        )
        self.assertEqual(executor.effect_count(admitted), 1)

    def test_disable_after_admission_blocks_execution_with_zero_effect(self):
        admitted = self.admitted()
        self.registry.disable("publish_report", "v1")
        executor = InMemoryToolExecutor()
        result = executor.execute(admitted, registry=self.registry)
        self.assertIs(result.status, ExecutionStatus.REJECTED_DISABLED)
        self.assertIsNone(result.operation_id)
        self.assertEqual(executor.effect_count(admitted), 0)

    def test_valid_nested_tool_outcome_is_verified(self):
        admitted = self.admitted()
        execution = InMemoryToolExecutor().execute(
            admitted,
            registry=self.registry,
        )
        raw = json.dumps(
            {
                "operation_id": execution.operation_id,
                "published": True,
                "report": {"report_id": "report-7", "version": 7},
                "warnings": [],
            }
        )
        result = verify_publish_outcome(
            raw,
            call=admitted,
            expected_operation_id=execution.operation_id,
        )
        self.assertIs(result.status, OutcomeStatus.VERIFIED)

    def test_outcome_array_items_are_schema_validated(self):
        admitted = self.admitted()
        raw = json.dumps(
            {
                "operation_id": "op-1",
                "published": True,
                "report": {"report_id": "report-7", "version": 7},
                "warnings": [7],
            }
        )
        result = verify_publish_outcome(
            raw,
            call=admitted,
            expected_operation_id="op-1",
        )
        self.assertIs(result.status, OutcomeStatus.SCHEMA_INVALID)

    def test_outcome_minimum_is_schema_validated(self):
        admitted = self.admitted()
        raw = json.dumps(
            {
                "operation_id": "op-1",
                "published": True,
                "report": {"report_id": "report-7", "version": 0},
                "warnings": [],
            }
        )
        result = verify_publish_outcome(
            raw,
            call=admitted,
            expected_operation_id="op-1",
        )
        self.assertIs(result.status, OutcomeStatus.SCHEMA_INVALID)

    def test_contradictory_outcome_is_semantically_invalid(self):
        admitted = self.admitted()
        raw = json.dumps(
            {
                "operation_id": "op-1",
                "published": True,
                "error": "permission denied",
                "report": {"report_id": "report-7", "version": 7},
                "warnings": [],
            }
        )
        result = verify_publish_outcome(
            raw,
            call=admitted,
            expected_operation_id="op-1",
        )
        self.assertIs(result.status, OutcomeStatus.SEMANTICALLY_INVALID)

    def test_wrong_operation_id_is_identity_mismatch(self):
        admitted = self.admitted()
        raw = json.dumps(
            {
                "operation_id": "op-other",
                "published": True,
                "report": {"report_id": "report-7", "version": 7},
                "warnings": [],
            }
        )
        result = verify_publish_outcome(
            raw,
            call=admitted,
            expected_operation_id="op-expected",
        )
        self.assertIs(result.status, OutcomeStatus.IDENTITY_MISMATCH)

    def test_wrong_report_version_is_identity_mismatch(self):
        admitted = self.admitted()
        raw = json.dumps(
            {
                "operation_id": "op-1",
                "published": True,
                "report": {"report_id": "report-7", "version": 6},
                "warnings": [],
            }
        )
        result = verify_publish_outcome(
            raw,
            call=admitted,
            expected_operation_id="op-1",
        )
        self.assertIs(result.status, OutcomeStatus.IDENTITY_MISMATCH)


class Day74GuardedCompletionTests(Day74Fixture, unittest.TestCase):
    def admitted(self):
        return self.admit(candidate()).admitted_call

    def test_timeout_unknown_enters_pending_reconciliation(self):
        admitted = self.admitted()
        store = InMemoryDurableStore(
            (JobRecord("job-1", JobStatus.RUNNING, "A1", "tc-1"),)
        )
        result = store.mark_timeout_unknown(call=admitted)
        self.assertIs(
            result.status,
            CompletionStatus.PENDING_RECONCILIATION,
        )
        self.assertIs(
            store.get("job-1").status,
            JobStatus.PENDING_RECONCILIATION,
        )

    def test_verified_current_attempt_guardedly_completes(self):
        admitted = self.admitted()
        store = InMemoryDurableStore(
            (JobRecord("job-1", JobStatus.RUNNING, "A1", "tc-1"),)
        )
        outcome = OutcomeDecision(OutcomeStatus.VERIFIED, "OUTCOME_VERIFIED")
        result = store.guarded_complete(
            call=admitted,
            outcome=outcome,
            operation_id="op-1",
        )
        self.assertIs(result.status, CompletionStatus.COMMITTED)
        self.assertIs(store.get("job-1").status, JobStatus.SUCCEEDED)
        self.assertEqual(store.get("job-1").verified_operation_id, "op-1")

    def test_valid_late_result_completes_pending_reconciliation(self):
        admitted = self.admitted()
        store = InMemoryDurableStore(
            (
                JobRecord(
                    "job-1",
                    JobStatus.PENDING_RECONCILIATION,
                    "A1",
                    "tc-1",
                ),
            )
        )
        outcome = OutcomeDecision(OutcomeStatus.VERIFIED, "OUTCOME_VERIFIED")
        result = store.guarded_complete(
            call=admitted,
            outcome=outcome,
            operation_id="op-late-valid",
        )
        self.assertIs(result.status, CompletionStatus.COMMITTED)
        self.assertIs(store.get("job-1").status, JobStatus.SUCCEEDED)

    def test_terminal_job_refuses_valid_late_result(self):
        admitted = self.admitted()
        store = InMemoryDurableStore(
            (JobRecord("job-1", JobStatus.CANCELLED, "A1", "tc-1"),)
        )
        outcome = OutcomeDecision(OutcomeStatus.VERIFIED, "OUTCOME_VERIFIED")
        result = store.guarded_complete(
            call=admitted,
            outcome=outcome,
            operation_id="op-late",
        )
        self.assertIs(result.status, CompletionStatus.NOOP_TERMINAL)
        self.assertIs(store.get("job-1").status, JobStatus.CANCELLED)

    def test_superseded_attempt_has_zero_completion_effect(self):
        admitted = self.admitted()
        store = InMemoryDurableStore(
            (JobRecord("job-1", JobStatus.RUNNING, "A2", "tc-2"),)
        )
        outcome = OutcomeDecision(OutcomeStatus.VERIFIED, "OUTCOME_VERIFIED")
        result = store.guarded_complete(
            call=admitted,
            outcome=outcome,
            operation_id="op-stale",
        )
        self.assertIs(result.status, CompletionStatus.NOOP_STALE)
        self.assertIs(store.get("job-1").status, JobStatus.RUNNING)

    def test_unverified_outcome_cannot_complete(self):
        admitted = self.admitted()
        store = InMemoryDurableStore(
            (JobRecord("job-1", JobStatus.RUNNING, "A1", "tc-1"),)
        )
        outcome = OutcomeDecision(
            OutcomeStatus.SCHEMA_INVALID,
            "OUTCOME_SCHEMA_INVALID",
        )
        result = store.guarded_complete(
            call=admitted,
            outcome=outcome,
            operation_id="op-invalid",
        )
        self.assertIs(
            result.status,
            CompletionStatus.REJECTED_UNVERIFIED,
        )
        self.assertIs(store.get("job-1").status, JobStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
