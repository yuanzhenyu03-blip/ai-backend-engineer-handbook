from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from rag_chunking_contracts import stable_hash  # noqa: E402
from run_day106_l3_evidence_replay import (  # noqa: E402
    ARTIFACT_PATHS,
    BASE_COMMIT,
    CORRECTION_PATH,
    SUPERSEDED_REPORT_CHECKSUM,
    validate_correction_record,
    validate_reports,
)


def _digest(label: str) -> str:
    return stable_hash(("day106-l3-test", label))


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _artifacts(artifact_root: Path = ROOT) -> dict[str, object]:
    return {
        "base_commit": BASE_COMMIT,
        "files": {
            name: {
                "path": f"projects/ai-agent/{relative_path}",
                "digest": _file_digest(artifact_root / relative_path),
            }
            for name, relative_path in ARTIFACT_PATHS.items()
        },
    }


def _correction() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "day106-l3a-evidence-correction.v1",
        "record_type": "EVIDENCE_CORRECTION",
        "correction_id": "day106-l3a-v1-pre-send-claim-correction",
        "recorded_at": "2026-11-24T02:32:21+00:00",
        "status": "SUPERSEDED",
        "superseded_report_path": (
            "projects/ai-agent/evidence/day106-l3a-integration-report.json"
        ),
        "superseded_report_checksum": SUPERSEDED_REPORT_CHECKSUM,
        "reason_code": "PRE_SEND_PERSISTENCE_CLAIM_OVERSTATED",
        "superseded_claim_only": (
            "hard_gates.model_invocation_pre_send_persisted=PASS"
        ),
        "replacement_claims": [
            "hard_gates.model_invocation_persisted_before_release=PASS",
            "hard_gates.external_pre_send_reservation=NOT_RUN",
        ],
        "other_historical_facts": "PRESERVED_APPEND_ONLY_NOT_OVERRIDDEN",
        "append_only": True,
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _initial() -> dict[str, object]:
    started = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)
    payload: dict[str, object] = {
        "schema_version": "day106-l3a-evidence.v2",
        "scenario_id": "day106-production-rag-postgresql-pgvector-l3a-v1",
        "run_id": "day106-l3a-test",
        "overall_status": "PASS",
        "evidence_level": (
            "EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR_"
            "WITH_DETERMINISTIC_MODEL_DLP_ADAPTERS"
        ),
        "started_at": started.isoformat(),
        "completed_at": (started + timedelta(minutes=1)).isoformat(),
        "environment": {
            "compose_project": "day106-l3",
            "database_identity_digest": _digest("database"),
            "image_reference": "pgvector/pgvector:0.8.7-pg16",
            "image_digest": (
                "sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f"
            ),
            "postgresql_version": "16.11",
            "pgvector_version": "0.8.7",
            "driver_version": "2.9.10",
            "python_version": "3.11.5",
        },
        "artifacts": _artifacts(),
        "cross_binding": {
            "day105_same_execution_report_checksum": _digest("day105-report"),
            "request_binding_digest": _digest("request"),
            "read_view_digest": _digest("read-view"),
            "generation_manifest_digest": _digest("manifest"),
            "retrieval_context_receipt_digest": _digest("receipt"),
            "model_invocation_record_digest": _digest("invocation"),
            "answer_release_record_digest": _digest("release"),
            "response_intent_digest": _digest("intent"),
            "exact_occurrence_ids_digest": _digest("occurrences"),
            "exact_content_digests_digest": _digest("contents"),
            "unauthorized_prompt_count": 0,
        },
        "hard_gates": {
            "same_execution_real_database_cross_binding": "PASS",
            "same_execution_day105_prerequisite": "PASS",
            "real_pgvector_exact_occurrence_binding": "PASS",
            "unauthorized_occurrence_entering_prompt_zero": "PASS",
            "decision_intent_atomicity": "PASS",
            "model_invocation_persisted_before_release": "PASS",
            "external_pre_send_reservation": "NOT_RUN",
            "unknown_reconciliation_bounded_retry": "PASS",
            "winner_fence_and_duplicate_deduplication": "PASS",
            "append_only_delivery_chain": "PASS",
            "external_provider_boundary": "NOT_RUN",
            "canonical_python_3_12": "NOT_RUN",
        },
        "restart_evidence": {
            "status": "NOT_RUN",
            "pre_restart_state_digest": _digest("durable-state"),
            "post_restart_state_digest": None,
            "pre_restart_postmaster_started_at": started.isoformat(),
            "post_restart_postmaster_started_at": None,
        },
        "cleanup": {
            "status": "NOT_RUN",
            "compose_project_digest": None,
            "volume_identity_digest": None,
        },
        "raw_prompt_logged": False,
        "protected_chunk_logged": False,
        "answer_candidate_text_logged": False,
        "raw_provider_response_logged": False,
        "raw_provider_response_id_logged": False,
        "raw_secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
        "external_real_boundary": "NOT_RUN",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "claim_boundary": "bounded local integration only",
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


def _restart(initial: dict[str, object]) -> dict[str, object]:
    started = datetime(2026, 11, 24, 1, 5, tzinfo=timezone.utc)
    restart = initial["restart_evidence"]
    assert isinstance(restart, dict)
    payload: dict[str, object] = {
        "schema_version": "day106-l3-restart-replay.v2",
        "scenario_id": "day106-production-rag-postgresql-pgvector-l3a-v1",
        "run_id": "day106-l3-restart-test",
        "status": "PASS",
        "started_at": started.isoformat(),
        "completed_at": (started + timedelta(seconds=1)).isoformat(),
        "postmaster_started_at": started.isoformat(),
        "database_identity_digest": _digest("database"),
        "generation_id": "G3",
        "pointer_revision": 9,
        "authorization_snapshot_id": "P2",
        "authorization_revision": 2,
        "intent_id": "response-intent-Day106-Q2-G3",
        "intent_identity_digest": _digest("intent"),
        "final_dispatch_state": "DELIVERED",
        "recovery_record_count": 7,
        "recovery_record_digests": [_digest(f"recovery-{item}") for item in range(7)],
        "durable_state_identity_digest": restart["pre_restart_state_digest"],
        "provider_call_count": 0,
        "schemas_reinstalled": False,
        "schemas_reset": False,
        "external_provider_called": False,
        "raw_content_logged": False,
        "provider_response_logged": False,
        "secret_logged": False,
        "raw_vector_logged": False,
        "database_url_logged": False,
    }
    payload["report_checksum"] = stable_hash(payload)
    return payload


class Day106L3EvidenceReplayTests(unittest.TestCase):
    def _validate(
        self,
        initial: dict[str, object],
        restart: dict[str, object],
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            integration_path = Path(directory) / "integration.json"
            restart_path = Path(directory) / "restart.json"
            correction_path = Path(directory) / "correction.json"
            integration_path.write_text(json.dumps(initial), encoding="utf-8")
            restart_path.write_text(json.dumps(restart), encoding="utf-8")
            correction_path.write_text(
                json.dumps(_correction()),
                encoding="utf-8",
            )
            return validate_reports(
                integration_path,
                restart_path,
                correction_path=correction_path,
            )

    def test_accepts_separate_append_only_integration_and_restart_reports(self) -> None:
        initial = _initial()
        result = self._validate(initial, _restart(initial))
        self.assertEqual(result["status"], "PASS")

    def test_static_append_only_correction_record_is_valid(self) -> None:
        correction = json.loads(CORRECTION_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            validate_correction_record(correction),
            correction["report_checksum"],
        )

    def test_rejects_external_pre_send_reservation_pass_claim(self) -> None:
        initial = _initial()
        restart = _restart(initial)
        hard_gates = initial["hard_gates"]
        assert isinstance(hard_gates, dict)
        hard_gates["external_pre_send_reservation"] = "PASS"
        initial["report_checksum"] = stable_hash(
            {key: value for key, value in initial.items() if key != "report_checksum"}
        )
        with self.assertRaisesRegex(
            ValueError,
            "EXTERNAL_PRE_SEND_CLAIM_MISMATCH",
        ):
            self._validate(initial, restart)

    def test_rejects_new_connection_mislabeled_as_container_restart(self) -> None:
        initial = _initial()
        restart = _restart(initial)
        restart["postmaster_started_at"] = initial["restart_evidence"][
            "pre_restart_postmaster_started_at"
        ]  # type: ignore[index]
        restart["report_checksum"] = stable_hash(
            {key: value for key, value in restart.items() if key != "report_checksum"}
        )
        with self.assertRaisesRegex(ValueError, "DID_NOT_RESTART"):
            self._validate(initial, restart)

    def test_rejects_rewritten_initial_evidence(self) -> None:
        initial = _initial()
        restart = _restart(initial)
        changed = deepcopy(initial)
        changed["claim_boundary"] = "rewritten"
        with self.assertRaisesRegex(ValueError, "CHECKSUM_MISMATCH"):
            self._validate(changed, restart)

    def test_rejects_current_artifact_digest_drift(self) -> None:
        initial = _initial()
        restart = _restart(initial)
        artifacts = initial["artifacts"]
        assert isinstance(artifacts, dict)
        files = artifacts["files"]
        assert isinstance(files, dict)
        integration_runner = files["integration_runner"]
        assert isinstance(integration_runner, dict)
        integration_runner["digest"] = _digest("wrong-runner")
        initial["report_checksum"] = stable_hash(
            {key: value for key, value in initial.items() if key != "report_checksum"}
        )
        with self.assertRaisesRegex(ValueError, "ARTIFACT_DIGEST_MISMATCH"):
            self._validate(initial, restart)

    def test_rejects_restart_report_with_extra_field(self) -> None:
        initial = _initial()
        restart = _restart(initial)
        restart["raw_prompt"] = "short-but-forbidden"
        restart["report_checksum"] = stable_hash(
            {key: value for key, value in restart.items() if key != "report_checksum"}
        )
        with self.assertRaisesRegex(ValueError, "RESTART_REPORT_SHAPE_MISMATCH"):
            self._validate(initial, restart)

    def test_rejects_wrong_superseded_report_reference(self) -> None:
        initial = _initial()
        restart = _restart(initial)
        correction = _correction()
        correction["superseded_report_checksum"] = _digest("wrong-old-report")
        correction["report_checksum"] = stable_hash(
            {
                key: value
                for key, value in correction.items()
                if key != "report_checksum"
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            integration_path = Path(directory) / "integration.json"
            restart_path = Path(directory) / "restart.json"
            correction_path = Path(directory) / "correction.json"
            integration_path.write_text(json.dumps(initial), encoding="utf-8")
            restart_path.write_text(json.dumps(restart), encoding="utf-8")
            correction_path.write_text(json.dumps(correction), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "CORRECTION_REPORT_CHECKSUM_MISMATCH",
            ):
                validate_reports(
                    integration_path,
                    restart_path,
                    correction_path=correction_path,
                )


if __name__ == "__main__":
    unittest.main()
