"""Replay saved Day105 L3 PostgreSQL/pgvector security evidence offline."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evidence" / "day105-l3-integration-report.json"
RESTART_REPORT_PATH = ROOT / "evidence" / "day105-l3-restart-replay.json"
CONTRACT_PATH = ROOT / "evidence" / "day105-l3-evidence-schema.json"
MIGRATION_PATH = ROOT / "integration" / "day105" / "schema.sql"
LIFECYCLE_MIGRATION_PATH = ROOT / "integration" / "day104" / "schema.sql"
COMPOSE_PATH = ROOT / "integration" / "day105" / "compose.yaml"
REQUIREMENTS_PATH = ROOT / "requirements-day105-l3.txt"
REPOSITORY_PATH = ROOT / "src" / "rag_security_postgres.py"
LIFECYCLE_REPOSITORY_PATH = ROOT / "src" / "rag_index_lifecycle_postgres.py"
UNIT_TEST_PATH = ROOT / "tests" / "test_day105_l3_postgres_unit.py"
INTEGRATION_TEST_PATH = ROOT / "tests" / "test_day105_l3_postgres_integration.py"
INTEGRATION_RUNNER_PATH = ROOT / "evals" / "run_day105_l3_integration.py"
RESTART_RUNNER_PATH = ROOT / "evals" / "run_day105_l3_restart_replay.py"

EVIDENCE_LEVEL = (
    "EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR_"
    "WITH_DETERMINISTIC_SECURITY_ADAPTERS"
)
SCHEMA_VERSION = "day105-l3-evidence.v1"
SCENARIO_ID = "day105-refund-rag-security-postgresql-pgvector-l3-v1"
CLAIM_BOUNDARY = (
    "Local Docker evidence for pinned PostgreSQL/pgvector transactions, "
    "constraints, CAS, restart, real vector retrieval and deterministic "
    "application-owned security adapters only; no real scanner, detector, "
    "DLP, model, Provider, production-egress or production-readiness claim."
)
DAY104_L3_CHECKSUM = (
    "sha256:41e4b36ca1ccd589ca6ddcd99026bc6b48fc57e5a47c231ca8d32433b479ba85"
)
DAY105_L2_CHECKSUM = (
    "sha256:b7cb38a8d7191d1404b162f88aae935c28f12628362e01b600c685299579f477"
)
IMAGE_DIGEST = "sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f"
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?:postgres(?:ql)?://|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bsk-[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)

REQUIRED_GATES = (
    "schema_migration_integrity",
    "postgresql_pgvector_identity_match",
    "append_only_security_record_immutability",
    "ingestion_security_evidence_binding",
    "quarantine_and_tombstone_currentness",
    "sealed_manifest_exact_binding",
    "provider_poisoning_not_served",
    "retrieval_authorization_and_tenant_isolation",
    "bundle_prompt_injection_isolation",
    "context_assembly_exact_manifest",
    "read_view_single_generation",
    "authorization_snapshot_rebuild_and_activation",
    "release_current_authorization_recheck",
    "citation_exact_binding",
    "dlp_metadata_destination_fail_closed",
    "security_snapshot_cas_and_transaction_atomicity",
    "incident_ledger_append_only",
    "normal_quality_preserved",
    "restart_durability_and_idempotency",
    "content_safe_evidence",
)

LEVEL_4_KEYS = (
    "real_scanner_detector_dlp_model_and_provider",
    "external_egress_enforcement",
    "production_iam_rls_tls_and_secret_rotation",
    "ha_replica_failover_backup_and_restore",
    "network_partition_and_split_brain",
    "physical_purge_across_wal_backups_caches_and_retained_media",
    "production_scale_recall_latency_load_cost_and_soak",
    "canary_incident_drill_and_observation_window",
)

IDENTITY_KEYS = (
    "security_policy",
    "initial_security_snapshot",
    "current_security_snapshot",
    "initial_build_snapshot",
    "current_build_snapshot",
    "initial_generation",
    "current_generation",
    "old_read_view",
    "new_read_view",
    "old_answer_candidate",
    "blocked_old_release",
    "released_new_response",
    "incident_root",
    "incident_correction",
    "y_v1_security_record",
    "y_v2_security_record",
)

CASE_EXPECTATIONS: dict[str, dict[str, object]] = {
    "normal-q1-g2": {
        "generation_id": "G2",
        "stage": "PASS",
        "action": "RELEASE",
        "prompt": ["A@v1"],
        "citations": ["A@v1"],
    },
    "normal-q2-g2": {
        "generation_id": "G2",
        "stage": "PASS",
        "action": "RELEASE",
        "prompt": ["C@v1"],
        "citations": ["C@v1"],
    },
    "normal-q3-g2": {
        "generation_id": "G2",
        "stage": "PASS",
        "action": "RELEASE",
        "prompt": ["A@v1", "C@v1"],
        "citations": ["A@v1", "C@v1"],
    },
    "poisoned-generation-not-served": {
        "generation_id": "G_BAD",
        "stage": "FAIL",
        "action": "NOT_SERVED",
        "prompt": [],
        "citations": [],
    },
    "document-injection-x-blocked": {
        "generation_id": "G_BAD",
        "stage": "FAIL",
        "action": "BLOCKED",
        "prompt": [],
        "citations": [],
    },
    "detector-timeout-y-quarantined": {
        "generation_id": "G_BAD",
        "stage": "INCONCLUSIVE",
        "action": "QUARANTINE",
        "prompt": [],
        "citations": [],
    },
    "detector-rescan-y-v2-append-only": {
        "generation_id": "NOT_SERVING",
        "stage": "PASS",
        "action": "NOT_SERVED",
        "prompt": [],
        "citations": [],
    },
    "cross-document-z-blocked": {
        "generation_id": "G_BAD",
        "stage": "FAIL",
        "action": "BLOCKED",
        "prompt": [],
        "citations": [],
    },
    "cross-tenant-t-blocked": {
        "generation_id": "G_BAD",
        "stage": "FAIL",
        "action": "BLOCKED",
        "prompt": [],
        "citations": [],
    },
    "revoked-a-old-candidate-blocked": {
        "generation_id": "G2",
        "stage": "FAIL",
        "action": "BLOCKED",
        "prompt": ["A@v1", "C@v1"],
        "citations": [],
    },
    "new-q2-g3-released": {
        "generation_id": "G3",
        "stage": "PASS",
        "action": "RELEASE",
        "prompt": ["C@v1"],
        "citations": ["C@v1"],
    },
    "wrong-citation-blocked": {
        "generation_id": "G3",
        "stage": "FAIL",
        "action": "BLOCKED",
        "prompt": ["C@v1"],
        "citations": [],
    },
    "dlp-timeout-blocked": {
        "generation_id": "G3",
        "stage": "INCONCLUSIVE",
        "action": "BLOCKED",
        "prompt": ["C@v1"],
        "citations": [],
    },
    "dlp-sensitive-blocked": {
        "generation_id": "G3",
        "stage": "FAIL",
        "action": "BLOCKED",
        "prompt": ["C@v1"],
        "citations": [],
    },
}

FAILURE_EXPECTATIONS = {
    "provider-manifest-extra-occurrence": (
        "reject generation with an extra occurrence",
        "independent readback marked generation integrity failed",
    ),
    "manifest-content-or-metadata-substitution": (
        "reject equal-count occurrence or digest substitution",
        "exact manifest identity mismatch rejected",
    ),
    "detector-timeout": (
        "treat unavailable detector evidence as inconclusive quarantine",
        "Y@v1 remained quarantined and absent from prompt",
    ),
    "document-injection-confirmed": (
        "block confirmed document prompt injection before context assembly",
        "X bundle decision failed and no context manifest was written",
    ),
    "detector-versioned-rescan": (
        "append Y@v2 with new parser scanner detector evidence without overwriting Y@v1",
        "Y@v1 remained immutable; Y@v2 used a new security record and remained "
        "outside serving generations",
    ),
    "cross-tenant-candidate": (
        "reject candidate outside request tenant",
        "T was denied and absent from prompt",
    ),
    "cross-document-bundle-chain": (
        "analyze the full bundle and block composed attack meaning",
        "Z1/Z2 bundle failed before context assembly",
    ),
    "security-artifact-exact-replay-conflict": (
        "converge identical replay and reject same ID with changed digest",
        "identical replay converged and changed digest was rejected",
    ),
    "security-snapshot-cas-race": (
        "allow exactly one current security snapshot revision winner",
        "one CAS advanced P2 and one stale revision was rejected",
    ),
    "security-transition-write-fault": (
        "roll back current snapshot pointer when transition append fails",
        "no partial snapshot pointer or transition persisted",
    ),
    "authorization-change-after-candidate": (
        "keep old candidate bound to G2 and block release after P2",
        "old candidate remained historical and output release failed closed",
    ),
    "context-projection-digest-tamper": (
        "reject context projection or serialization identity change",
        "context assembly digest mismatch was rejected",
    ),
    "wrong-citation": (
        "block citation outside exact supported occurrence",
        "output release failed with no released citations",
    ),
    "dlp-timeout": (
        "block when DLP evidence is inconclusive",
        "output release was inconclusive and blocked",
    ),
    "dlp-sensitive-category": (
        "fail when DLP identifies sensitive material",
        "output release failed and returned a content-safe blocked intent",
    ),
    "orphan-candidate-restart": (
        "default block candidate missing a durable release decision after restart",
        "orphan candidate remained non-releasable",
    ),
    "incident-overwrite-or-branch": (
        "reject incident overwrite second root and branch",
        "append-only ledger rejected changed digest and branching correction",
    ),
    "container-restart-readback": (
        "recover durable G3/P2 security and blocked-release state after restart",
        "new process read G3/P2 and did not revive the old candidate",
    ),
}

COMMANDS = {
    "day105-l3-unit": (
        "PYTHONPATH=src:tests:. python -m unittest discover -s tests "
        "-p 'test_day105_l3_postgres_unit.py' -q"
    ),
    "day105-l3-integration": (
        "DAY105_L3_INTEGRATION=1 PYTHONPATH=src:tests:. python -m unittest "
        "discover -s tests -p 'test_day105_l3_postgres_integration.py' -q"
    ),
    "day105-l3-runner": (
        "DAY105_L3_INTEGRATION=1 PYTHONPATH=src:. python "
        "evals/run_day105_l3_integration.py"
    ),
    "day105-l3-restart-replay": (
        "DAY105_L3_INTEGRATION=1 PYTHONPATH=src:. python "
        "evals/run_day105_l3_restart_replay.py"
    ),
}

TEST_EXPECTATIONS = {
    "day105-l3-unit": (20, "SUMMARY"),
    "day105-l3-integration": (9, "SUMMARY"),
    "day105-l3-runner": (20, "RUNNER_PAYLOAD"),
    "day105-l3-restart-replay": (1, "RESTART_PAYLOAD"),
}

ARTIFACT_PATHS = {
    "schema_migration_digest": MIGRATION_PATH,
    "lifecycle_schema_digest": LIFECYCLE_MIGRATION_PATH,
    "security_repository_digest": REPOSITORY_PATH,
    "lifecycle_repository_digest": LIFECYCLE_REPOSITORY_PATH,
    "compose_digest": COMPOSE_PATH,
    "requirements_digest": REQUIREMENTS_PATH,
    "unit_test_digest": UNIT_TEST_PATH,
    "integration_test_digest": INTEGRATION_TEST_PATH,
    "integration_runner_digest": INTEGRATION_RUNNER_PATH,
    "restart_replay_runner_digest": RESTART_RUNNER_PATH,
    "evidence_replay_runner_digest": Path(__file__).resolve(),
    "saved_restart_report_file_digest": RESTART_REPORT_PATH,
}

CONTENT_SAFETY_FLAGS = (
    "fixture_production_eligible",
    "raw_attack_payloads_logged",
    "raw_protected_content_logged",
    "raw_system_prompts_logged",
    "raw_answer_candidates_logged",
    "raw_secrets_logged",
    "raw_cross_tenant_content_logged",
    "raw_vectors_logged",
    "database_url_logged",
)

FORBIDDEN_CONTENT_KEYS = {
    "answer_text",
    "attack_payload",
    "candidate_text",
    "cross_tenant_content",
    "database_url",
    "dsn",
    "embedding",
    "embedding_vector",
    "password",
    "protected_chunk",
    "protected_chunks",
    "protected_content",
    "raw_attack_payload",
    "raw_attack_payloads",
    "raw_content",
    "secret",
    "secret_value",
    "system_prompt",
    "vector",
}


def stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("EXPECTED_DATETIME_STRING")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    require(parsed.tzinfo is not None, "DATETIME_REQUIRES_OFFSET")
    return parsed


def require_digest(value: object, reason: str) -> None:
    if not isinstance(value, str):
        raise ValueError(reason)
    require(DIGEST_PATTERN.fullmatch(value) is not None, reason)


def _schema_type_matches(value: object, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"UNSUPPORTED_SCHEMA_TYPE:{expected}")


def _resolve_local_ref(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    require(reference.startswith("#/"), f"NON_LOCAL_SCHEMA_REF:{reference}")
    current: object = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"SCHEMA_REF:{reference}")
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError(f"SCHEMA_REF_NOT_OBJECT:{reference}")
    return current


def _schema_matches(
    value: object,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
) -> bool:
    try:
        validate_schema_instance(value, schema, root_schema)
    except ValueError:
        return False
    return True


def validate_schema_instance(
    value: object,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> None:
    """Validate the JSON Schema keywords used by the Day105 L3 contract."""

    reference = schema.get("$ref")
    if reference is not None:
        require(isinstance(reference, str), f"SCHEMA_REF_TYPE:{path}")
        validate_schema_instance(
            value,
            _resolve_local_ref(root_schema, reference),
            root_schema,
            path,
        )

    for index, branch in enumerate(schema.get("allOf", [])):
        validate_schema_instance(value, branch, root_schema, f"{path}.allOf[{index}]")

    one_of = schema.get("oneOf")
    if one_of is not None:
        matches = sum(_schema_matches(value, branch, root_schema) for branch in one_of)
        require(matches == 1, f"SCHEMA_ONE_OF:{path}")

    conditional = schema.get("if")
    if conditional is not None:
        branch_name = (
            "then" if _schema_matches(value, conditional, root_schema) else "else"
        )
        branch = schema.get(branch_name)
        if branch is not None:
            validate_schema_instance(
                value, branch, root_schema, f"{path}.{branch_name}"
            )

    expected_type = schema.get("type")
    if expected_type is not None:
        require(isinstance(expected_type, str), f"SCHEMA_TYPE_DECLARATION:{path}")
        require(_schema_type_matches(value, expected_type), f"SCHEMA_TYPE:{path}")

    if "const" in schema:
        require(value == schema["const"], f"SCHEMA_CONST:{path}")
    if "enum" in schema:
        require(value in schema["enum"], f"SCHEMA_ENUM:{path}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        require(
            all(isinstance(item, str) for item in required), f"SCHEMA_REQUIRED:{path}"
        )
        missing = [item for item in required if item not in value]
        require(not missing, f"SCHEMA_REQUIRED_MISSING:{path}:{','.join(missing)}")
        properties = schema.get("properties", {})
        require(isinstance(properties, dict), f"SCHEMA_PROPERTIES:{path}")
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value).difference(properties))
            require(
                not extras, f"SCHEMA_ADDITIONAL_PROPERTIES:{path}:{','.join(extras)}"
            )
        for key, child_schema in properties.items():
            if key in value:
                require(isinstance(child_schema, dict), f"SCHEMA_PROPERTY:{path}.{key}")
                validate_schema_instance(
                    value[key], child_schema, root_schema, f"{path}.{key}"
                )

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        maximum_items = schema.get("maxItems")
        if minimum_items is not None:
            require(len(value) >= minimum_items, f"SCHEMA_MIN_ITEMS:{path}")
        if maximum_items is not None:
            require(len(value) <= maximum_items, f"SCHEMA_MAX_ITEMS:{path}")
        if schema.get("uniqueItems") is True:
            canonical = [
                json.dumps(
                    item, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                )
                for item in value
            ]
            require(
                len(canonical) == len(set(canonical)), f"SCHEMA_UNIQUE_ITEMS:{path}"
            )
        item_schema = schema.get("items")
        if item_schema is not None:
            require(isinstance(item_schema, dict), f"SCHEMA_ITEMS:{path}")
            for index, item in enumerate(value):
                validate_schema_instance(
                    item, item_schema, root_schema, f"{path}[{index}]"
                )

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None:
            require(len(value) >= minimum_length, f"SCHEMA_MIN_LENGTH:{path}")
        pattern = schema.get("pattern")
        if pattern is not None:
            require(re.search(pattern, value) is not None, f"SCHEMA_PATTERN:{path}")
        if schema.get("format") == "date-time":
            parse_datetime(value)

    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None:
            require(value >= minimum, f"SCHEMA_MINIMUM:{path}")
        if maximum is not None:
            require(value <= maximum, f"SCHEMA_MAXIMUM:{path}")


def validate_schema_validator_negative_checks() -> None:
    """Prove that critical nested-shape failures are rejected fail-closed."""

    root = {
        "$defs": {
            "digest": {
                "type": "string",
                "pattern": r"^sha256:[0-9a-f]{64}$",
            }
        }
    }
    shape = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "count", "digests", "observed_at", "nested"],
        "properties": {
            "kind": {"const": "SAFE", "enum": ["SAFE"]},
            "count": {"type": "integer", "minimum": 1},
            "digests": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"$ref": "#/$defs/digest"},
            },
            "observed_at": {"type": "string", "format": "date-time"},
            "nested": {
                "type": "object",
                "additionalProperties": False,
                "required": ["enabled"],
                "properties": {"enabled": {"type": "boolean"}},
            },
        },
    }
    valid_digest = "sha256:" + "a" * 64
    valid: dict[str, object] = {
        "kind": "SAFE",
        "count": 1,
        "digests": [valid_digest],
        "observed_at": "2026-11-16T00:00:00+00:00",
        "nested": {"enabled": True},
    }
    validate_schema_instance(valid, shape, root)
    invalid_values = (
        {key: value for key, value in valid.items() if key != "nested"},
        {**valid, "extra": "forbidden"},
        {**valid, "count": "1"},
        {**valid, "kind": "UNSAFE"},
        {**valid, "count": 0},
        {**valid, "digests": []},
        {**valid, "digests": [valid_digest, valid_digest]},
        {**valid, "digests": ["not-a-digest"]},
        {**valid, "observed_at": "not-a-date"},
        {**valid, "nested": {"enabled": True, "raw": "forbidden"}},
    )
    for index, invalid in enumerate(invalid_values):
        require(
            not _schema_matches(invalid, shape, root),
            f"SCHEMA_NEGATIVE_CHECK_UNEXPECTED_PASS:{index}",
        )


def validate_core_contract(report: dict[str, Any], contract: dict[str, Any]) -> None:
    properties = contract["properties"]
    require(report["schema_version"] == SCHEMA_VERSION, "SCHEMA_VERSION_MISMATCH")
    require(report["scenario_id"] == SCENARIO_ID, "SCENARIO_ID_MISMATCH")
    require(report["claim_boundary"] == CLAIM_BOUNDARY, "CLAIM_BOUNDARY_MISMATCH")
    require(
        properties["schema_version"]["const"] == SCHEMA_VERSION,
        "CONTRACT_SCHEMA_VERSION_CHANGED",
    )
    require(
        properties["scenario_id"]["const"] == SCENARIO_ID,
        "CONTRACT_SCENARIO_ID_CHANGED",
    )
    require(
        properties["claim_boundary"]["const"] == CLAIM_BOUNDARY,
        "CONTRACT_CLAIM_BOUNDARY_CHANGED",
    )
    require(
        set(report) == set(contract["required"]),
        "REPORT_TOP_LEVEL_SHAPE_MISMATCH",
    )
    require(
        set(properties["hard_gates"]["required"]) == set(REQUIRED_GATES),
        "CONTRACT_GATE_SET_CHANGED",
    )
    require(
        set(properties["level_4"]["required"]) == set(LEVEL_4_KEYS),
        "CONTRACT_LEVEL4_SET_CHANGED",
    )


def validate_baselines(report: dict[str, Any]) -> None:
    baselines = report["baselines"]
    day104 = baselines["day104_level_3"]
    day105 = baselines["day105_level_2"]
    require(day104["report_checksum"] == DAY104_L3_CHECKSUM, "DAY104_BASELINE_CHANGED")
    require(day105["report_checksum"] == DAY105_L2_CHECKSUM, "DAY105_BASELINE_CHANGED")
    local_day104 = json.loads(
        (ROOT / "evidence" / "day104-l3-integration-report.json").read_text()
    )
    local_day105 = json.loads(
        (ROOT / "evidence" / "day105-rag-security-report.json").read_text()
    )
    require(
        local_day104["report_checksum"] == DAY104_L3_CHECKSUM,
        "LOCAL_DAY104_BASELINE_CHECKSUM_CHANGED",
    )
    require(
        local_day105["report_checksum"] == DAY105_L2_CHECKSUM,
        "LOCAL_DAY105_BASELINE_CHECKSUM_CHANGED",
    )


def validate_environment(report: dict[str, Any]) -> None:
    environment = report["environment"]
    require(
        environment["image_reference"] == "pgvector/pgvector:0.8.7-pg16",
        "IMAGE_REFERENCE_MISMATCH",
    )
    require(environment["image_digest"] == IMAGE_DIGEST, "IMAGE_DIGEST_MISMATCH")
    require(environment["database_driver"] == "psycopg2-binary", "DRIVER_MISMATCH")
    require(environment["database_driver_version"] == "2.9.10", "DRIVER_VERSION")
    require(environment["pgvector_extension_version"] == "0.8.7", "PGVECTOR_VERSION")
    server_version = environment["postgresql_server_version_num"]
    require(160000 <= server_version <= 169999, "POSTGRESQL_MAJOR_VERSION_MISMATCH")
    require(
        set(environment["transaction_isolation"])
        >= {"READ COMMITTED", "REPEATABLE READ"},
        "TRANSACTION_ISOLATION_EVIDENCE_MISSING",
    )
    require_digest(environment["database_identity_digest"], "DATABASE_IDENTITY_INVALID")


def validate_scenario_and_identities(report: dict[str, Any]) -> None:
    scenario = report["scenario"]
    initial = scenario["initial_serving_state"]
    current = scenario["current_serving_state"]
    require(
        initial
        == {
            "authorization_revision": "P1",
            "build_snapshot_id": "BS1",
            "generation_id": "G2",
            "pointer_revision": 8,
            "manifest_occurrence_ids": ["A@v1", "C@v1"],
        },
        "INITIAL_SERVING_STATE_CHANGED",
    )
    require(
        current
        == {
            "authorization_revision": "P2",
            "build_snapshot_id": "BS2",
            "generation_id": "G3",
            "pointer_revision": 9,
            "manifest_occurrence_ids": ["C@v1"],
        },
        "CURRENT_SERVING_STATE_CHANGED",
    )
    require(scenario["tombstoned_occurrence_ids"] == ["B@v1"], "B_NOT_TOMBSTONED")
    require(
        scenario["quarantined_occurrence_ids"] == ["X@v1", "Y@v1"],
        "QUARANTINE_SET_CHANGED",
    )
    require(
        scenario["versioned_rescan_occurrence_ids"] == ["Y@v1", "Y@v2"],
        "VERSIONED_RESCAN_SET_CHANGED",
    )
    require(scenario["cross_tenant_occurrence_ids"] == ["T@v1"], "T_SET_CHANGED")
    require(
        scenario["cross_document_chain_occurrence_ids"] == ["Z1@v1", "Z2@v1"],
        "Z_CHAIN_CHANGED",
    )

    identities = report["identities"]
    require(set(identities) == set(IDENTITY_KEYS), "IDENTITY_SET_MISMATCH")
    for name, binding in identities.items():
        require(set(binding) == {"identity", "digest"}, f"IDENTITY_SHAPE:{name}")
        require(bool(binding["identity"]), f"IDENTITY_VALUE_MISSING:{name}")
        require_digest(binding["digest"], f"IDENTITY_DIGEST_INVALID:{name}")
    require(identities["initial_security_snapshot"]["identity"] == "P1", "P1_CHANGED")
    require(identities["current_security_snapshot"]["identity"] == "P2", "P2_CHANGED")
    require(identities["initial_build_snapshot"]["identity"] == "BS1", "BS1_CHANGED")
    require(identities["current_build_snapshot"]["identity"] == "BS2", "BS2_CHANGED")
    require(identities["initial_generation"]["identity"] == "G2", "G2_CHANGED")
    require(identities["current_generation"]["identity"] == "G3", "G3_CHANGED")
    require(
        identities["y_v1_security_record"]["digest"]
        != identities["y_v2_security_record"]["digest"],
        "Y_VERSIONED_RECORDS_COLLAPSED",
    )


def validate_security_cases(report: dict[str, Any]) -> None:
    cases = report["security_cases"]
    by_id = {item["case_id"]: item for item in cases}
    require(len(by_id) == len(cases), "DUPLICATE_SECURITY_CASE_ID")
    require(set(by_id) == set(CASE_EXPECTATIONS), "SECURITY_CASE_SET_MISMATCH")
    for case_id, expected in CASE_EXPECTATIONS.items():
        item = by_id[case_id]
        require(
            item["generation_id"] == expected["generation_id"], f"CASE_GEN:{case_id}"
        )
        require(
            item["expected_stage_result"] == expected["stage"],
            f"CASE_EXPECTED:{case_id}",
        )
        require(
            item["observed_stage_result"] == expected["stage"],
            f"CASE_OBSERVED:{case_id}",
        )
        require(
            item["expected_serving_action"] == expected["action"],
            f"CASE_ACTION:{case_id}",
        )
        require(item["serving_action"] == expected["action"], f"CASE_SERVING:{case_id}")
        require(
            item["prompt_occurrence_ids"] == expected["prompt"],
            f"CASE_PROMPT:{case_id}",
        )
        require(
            item["released_citation_occurrence_ids"] == expected["citations"],
            f"CASE_CITATIONS:{case_id}",
        )
        require(item["defense_outcome"] == "PASS", f"CASE_DEFENSE:{case_id}")
        require(item["expectation_conformant"] is True, f"CASE_CONFORMANCE:{case_id}")
        payload = dict(item)
        evidence_digest = payload.pop("evidence_digest")
        require(evidence_digest == stable_hash(payload), f"CASE_DIGEST:{case_id}")


def validate_gates(report: dict[str, Any]) -> None:
    gates = report["hard_gates"]
    require(set(gates) == set(REQUIRED_GATES), "REPORT_GATE_SET_MISMATCH")
    for name in REQUIRED_GATES:
        gate = gates[name]
        require(gate["status"] == "PASS", f"GATE_NOT_PASS:{name}")
        require(bool(gate["safe_reason"]), f"GATE_REASON_MISSING:{name}")
        require(bool(gate["evidence_ids"]), f"GATE_IDS_MISSING:{name}")
        require(
            len(gate["evidence_ids"]) == len(set(gate["evidence_ids"])),
            f"GATE_IDS:{name}",
        )
        require(bool(gate["evidence_digests"]), f"GATE_DIGESTS_MISSING:{name}")
        for digest in gate["evidence_digests"]:
            require_digest(digest, f"GATE_DIGEST_INVALID:{name}")
        parse_datetime(gate["observed_at"])


def validate_test_runs(report: dict[str, Any]) -> None:
    runs = report["test_runs"]
    by_id = {item["runner_id"]: item for item in runs}
    require(len(by_id) == len(runs), "DUPLICATE_TEST_RUNNER_ID")
    require(set(by_id) == set(TEST_EXPECTATIONS), "TEST_RUNNER_SET_MISMATCH")
    for runner_id, command in COMMANDS.items():
        item = by_id[runner_id]
        require(item["status"] == "PASS", f"TEST_NOT_PASS:{runner_id}")
        expected_count, report_rule = TEST_EXPECTATIONS[runner_id]
        require(
            (item["passed"], item["failed"], item["skipped"]) == (expected_count, 0, 0),
            f"TEST_COUNTS:{runner_id}",
        )
        require(
            item["command_digest"] == stable_hash(command),
            f"COMMAND_DIGEST_MISMATCH:{runner_id}",
        )
        if report_rule == "SUMMARY":
            expected_report_digest = stable_hash(
                {
                    "runner_id": runner_id,
                    "passed": expected_count,
                    "failed": 0,
                    "skipped": 0,
                }
            )
            require(
                item["report_digest"] == expected_report_digest,
                f"TEST_REPORT_DIGEST:{runner_id}",
            )
        else:
            require_digest(item["report_digest"], f"TEST_REPORT_DIGEST:{runner_id}")

    runner_payload = {
        "security_cases": report["security_cases"],
        "hard_gates": report["hard_gates"],
        "failure_injections": report["failure_injections"],
        "application_process_restart": report["restart_evidence"][
            "application_process_restart"
        ],
    }
    require(
        by_id["day105-l3-runner"]["report_digest"] == stable_hash(runner_payload),
        "RUNNER_PAYLOAD_CHECKSUM_MISMATCH",
    )
    require(
        report["artifacts"]["test_report_digest"] == stable_hash(runs),
        "AGGREGATE_TEST_REPORT_DIGEST_MISMATCH",
    )


def validate_failure_injections(report: dict[str, Any]) -> None:
    failures = report["failure_injections"]
    by_id = {item["checkpoint_id"]: item for item in failures}
    require(len(by_id) == len(failures), "DUPLICATE_FAILURE_CHECKPOINT")
    require(set(by_id) == set(FAILURE_EXPECTATIONS), "FAILURE_SET_MISMATCH")
    runner_digest = report["artifacts"]["integration_runner_digest"]
    for checkpoint, (expected, observed) in FAILURE_EXPECTATIONS.items():
        item = by_id[checkpoint]
        require(item["status"] == "PASS", f"FAILURE_NOT_PASS:{checkpoint}")
        require(item["expected_outcome"] == expected, f"FAILURE_EXPECTED:{checkpoint}")
        require(item["observed_outcome"] == observed, f"FAILURE_OBSERVED:{checkpoint}")
        digest_payload = {
            "checkpoint_id": checkpoint,
            "expected_outcome": expected,
            "observed_outcome": observed,
            "runner_digest": runner_digest,
        }
        require(
            item["evidence_digest"] == stable_hash(digest_payload),
            f"FAILURE_DIGEST:{checkpoint}",
        )


def _validate_restart_record(record: dict[str, Any], label: str) -> None:
    require(record["status"] == "PASS", f"RESTART_NOT_PASS:{label}")
    require(
        record["before_identity_digest"] == record["after_identity_digest"],
        f"DURABLE_IDENTITY_CHANGED:{label}",
    )
    require_digest(record["before_identity_digest"], f"RESTART_BEFORE:{label}")
    parse_datetime(record["observed_at"])
    payload = dict(record)
    evidence_digest = payload.pop("evidence_digest")
    require(evidence_digest == stable_hash(payload), f"RESTART_DIGEST:{label}")


def validate_saved_restart_report(report: dict[str, Any]) -> str:
    saved = json.loads(RESTART_REPORT_PATH.read_text(encoding="utf-8"))
    expected_keys = {
        "schema_version",
        "scenario_id",
        "run_id",
        "status",
        "started_at",
        "completed_at",
        "before_postmaster_started_at",
        "after_postmaster_started_at",
        "state_identity_digest_before",
        "state_identity_digest_after",
        "current_authorization_revision",
        "current_generation_id",
        "pointer_revision",
        "new_query_occurrence_ids",
        "old_g2_query_result",
        "old_candidate_release",
        "orphan_candidate_release",
        "exact_replay_result",
        "changed_digest_result",
        "fresh_read_view_closed",
        "raw_content_logged",
        "raw_vectors_logged",
        "database_url_logged",
        "report_checksum",
    }
    require(isinstance(saved, dict), "RESTART_REPORT_MUST_BE_OBJECT")
    require(set(saved) == expected_keys, "RESTART_REPORT_SHAPE_MISMATCH")
    require(saved["schema_version"] == "day105-l3-restart-replay.v1", "RESTART_SCHEMA")
    require(saved["scenario_id"] == SCENARIO_ID, "RESTART_SCENARIO")
    run_id = saved["run_id"]
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("RESTART_RUN_ID")
    require(saved["status"] == "PASS", "RESTART_REPORT_NOT_PASS")
    started = parse_datetime(saved["started_at"])
    completed = parse_datetime(saved["completed_at"])
    require(completed >= started, "RESTART_REPORT_TIME_ORDER")
    before_postmaster = parse_datetime(saved["before_postmaster_started_at"])
    after_postmaster = parse_datetime(saved["after_postmaster_started_at"])
    require(after_postmaster > before_postmaster, "RESTART_POSTMASTER_DID_NOT_ADVANCE")
    require_digest(saved["state_identity_digest_before"], "RESTART_STATE_BEFORE")
    require_digest(saved["state_identity_digest_after"], "RESTART_STATE_AFTER")
    require(
        saved["state_identity_digest_before"] == saved["state_identity_digest_after"],
        "RESTART_DURABLE_STATE_CHANGED",
    )
    require(saved["current_authorization_revision"] == "P2", "RESTART_AUTH_REVISION")
    require(saved["current_generation_id"] == "G3", "RESTART_GENERATION")
    require(saved["pointer_revision"] == 9, "RESTART_POINTER_REVISION")
    require(saved["new_query_occurrence_ids"] == ["C@v1"], "RESTART_QUERY_RESULT")
    require(
        saved["old_g2_query_result"] == "REJECTED_CURRENT_AUTHORIZATION",
        "RESTART_OLD_QUERY_NOT_REJECTED",
    )
    require(saved["old_candidate_release"] == "BLOCKED", "RESTART_OLD_RELEASE")
    require(saved["orphan_candidate_release"] == "BLOCKED", "RESTART_ORPHAN_RELEASE")
    require(saved["exact_replay_result"] == "EXACT_REPLAY", "RESTART_EXACT_REPLAY")
    require(saved["changed_digest_result"] == "IDENTITY_CONFLICT", "RESTART_CONFLICT")
    require(saved["fresh_read_view_closed"] is True, "RESTART_READ_VIEW_NOT_CLOSED")
    for flag in ("raw_content_logged", "raw_vectors_logged", "database_url_logged"):
        require(saved[flag] is False, f"RESTART_CONTENT_FLAG:{flag}")
    validate_no_forbidden_content(saved, "restart_report")
    serialized = json.dumps(saved, sort_keys=True).lower()
    require("postgresql://" not in serialized, "RESTART_DATABASE_URL_LEAKED")
    require("day105_l3_database_url" not in serialized, "RESTART_DATABASE_ENV_LEAKED")
    payload = dict(saved)
    checksum = payload.pop("report_checksum")
    require_digest(checksum, "RESTART_REPORT_CHECKSUM_INVALID")
    require(checksum == stable_hash(payload), "RESTART_REPORT_CHECKSUM_MISMATCH")

    binding = report["restart_evidence"]["saved_restart_report"]
    require(
        binding["evidence_path"]
        == "projects/ai-agent/evidence/day105-l3-restart-replay.json",
        "RESTART_REPORT_PATH_MISMATCH",
    )
    require(binding["report_checksum"] == checksum, "RESTART_BINDING_CHECKSUM")
    require(
        binding["file_digest"] == file_digest(RESTART_REPORT_PATH),
        "RESTART_BINDING_FILE_DIGEST",
    )
    return checksum


def validate_restart_evidence(report: dict[str, Any]) -> None:
    restart = report["restart_evidence"]
    application = restart["application_process_restart"]
    container = restart["database_container_restart"]
    _validate_restart_record(application, "application")
    _validate_restart_record(container, "container")
    before = parse_datetime(container["before_postmaster_started_at"])
    after = parse_datetime(container["after_postmaster_started_at"])
    require(after > before, "POSTMASTER_START_TIME_DID_NOT_ADVANCE")
    restart_checksum = validate_saved_restart_report(report)
    saved = json.loads(RESTART_REPORT_PATH.read_text(encoding="utf-8"))
    require(
        container["before_postmaster_started_at"]
        == saved["before_postmaster_started_at"],
        "CONTAINER_RESTART_BEFORE_TIME_NOT_BOUND",
    )
    require(
        container["after_postmaster_started_at"]
        == saved["after_postmaster_started_at"],
        "CONTAINER_RESTART_AFTER_TIME_NOT_BOUND",
    )
    run_by_id = {item["runner_id"]: item for item in report["test_runs"]}
    restart_report = run_by_id["day105-l3-restart-replay"]["report_digest"]
    require(
        restart_report == restart_checksum,
        "RESTART_TEST_RUN_NOT_BOUND",
    )
    require(
        container["restart_replay_report_digest"] == restart_checksum,
        "CONTAINER_RESTART_REPORT_NOT_BOUND",
    )
    require(
        report["artifacts"]["saved_restart_report_file_digest"]
        == file_digest(RESTART_REPORT_PATH),
        "RESTART_ARTIFACT_FILE_NOT_BOUND",
    )
    gate = report["hard_gates"]["restart_durability_and_idempotency"]
    require(
        application["evidence_digest"] in gate["evidence_digests"],
        "APP_RESTART_NOT_BOUND",
    )
    require(
        container["evidence_digest"] in gate["evidence_digests"],
        "CONTAINER_RESTART_NOT_BOUND",
    )


def validate_artifacts(report: dict[str, Any]) -> None:
    artifacts = report["artifacts"]
    for key, path in ARTIFACT_PATHS.items():
        require(path.is_file(), f"ARTIFACT_FILE_MISSING:{key}")
        require(artifacts[key] == file_digest(path), f"ARTIFACT_DIGEST_MISMATCH:{key}")


def validate_cleanup(report: dict[str, Any]) -> None:
    cleanup = report["cleanup"]
    require(cleanup["status"] == "PASS", "CLEANUP_NOT_PASS")
    require(bool(cleanup["safe_reason"]), "CLEANUP_REASON_MISSING")
    require(cleanup["compose_project"] == "day105-l3", "CLEANUP_PROJECT_CHANGED")
    require(cleanup["volume_identity"] == "day105_l3_pg_data", "CLEANUP_VOLUME_CHANGED")
    project_digest = stable_hash({"compose_project": "day105-l3"})
    volume_digest = stable_hash(
        {"compose_project": "day105-l3", "volume_identity": "day105_l3_pg_data"}
    )
    require(
        cleanup["compose_project_identity_digest"] == project_digest,
        "CLEANUP_PROJECT_DIGEST_MISMATCH",
    )
    require(
        cleanup["volume_identity_digest"] == volume_digest,
        "CLEANUP_VOLUME_DIGEST_MISMATCH",
    )
    removed = cleanup["removed_resource_identity_digests"]
    require(bool(removed), "CLEANUP_RESOURCE_IDENTITIES_MISSING")
    require(len(removed) == len(set(removed)), "CLEANUP_RESOURCE_IDENTITIES_DUPLICATE")
    require(
        {project_digest, volume_digest}.issubset(removed),
        "CLEANUP_RESOURCE_IDENTITIES_NOT_BOUND",
    )
    for digest in removed:
        require_digest(digest, "CLEANUP_RESOURCE_DIGEST_INVALID")


def validate_timeline(report: dict[str, Any]) -> None:
    started = parse_datetime(report["started_at"])
    completed = parse_datetime(report["completed_at"])
    require(completed >= started, "REPORT_TIME_ORDER_INVALID")
    structured_time_count = 0

    def walk(value: object, path: str) -> None:
        nonlocal structured_time_count
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key in {"observed_at", "completed_at"} and child is not None:
                    structured_time_count += 1
                    require(
                        parse_datetime(child) <= completed,
                        f"EVIDENCE_TIME_AFTER_REPORT:{child_path}",
                    )
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(report, "report")
    require(
        parse_datetime(report["cleanup"]["completed_at"]) == completed,
        "CLEANUP_COMPLETION_NOT_BOUND",
    )
    require(structured_time_count >= 23, "STRUCTURED_EVIDENCE_TIMES_MISSING")


def validate_content_safety_and_level4(report: dict[str, Any]) -> None:
    for name in CONTENT_SAFETY_FLAGS:
        require(report[name] is False, f"CONTENT_SAFETY_FLAG_INVALID:{name}")
    require(
        report["production_readiness"] == "MORE_EVIDENCE_NEEDED",
        "PRODUCTION_READINESS_OVERCLAIMED",
    )
    level_4 = report["level_4"]
    require(set(level_4) == set(LEVEL_4_KEYS), "LEVEL4_SET_MISMATCH")
    require(all(value == "NOT_RUN" for value in level_4.values()), "LEVEL4_OVERCLAIMED")

    validate_no_forbidden_content(report, "report")


def validate_no_forbidden_content(value: object, path: str) -> None:
    """Reject raw payload fields and complete credential-bearing strings."""

    def walk(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                require(
                    key.lower() not in FORBIDDEN_CONTENT_KEYS,
                    f"FORBIDDEN_KEY:{path}.{key}",
                )
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif isinstance(value, str):
            lowered = value.lower()
            require(
                SENSITIVE_VALUE_PATTERN.search(value) is None,
                f"SENSITIVE_VALUE_LEAKED:{path}",
            )
            require(
                "day105_l3_database_url" not in lowered, f"DATABASE_ENV_LEAKED:{path}"
            )

    walk(value, path)


def validate_content_safety_negative_checks() -> None:
    for key in (
        "candidate_text",
        "protected_chunk",
        "raw_attack_payload",
        "cross_tenant_content",
    ):
        try:
            validate_no_forbidden_content({key: "redacted-test-value"}, "synthetic")
        except ValueError:
            continue
        raise ValueError(f"CONTENT_DENYLIST_UNEXPECTED_PASS:{key}")
    for value in (
        "postgresql://user:credential@127.0.0.1/database",
        "DAY105_L3_DATABASE_URL",
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "sk-abcdefghijklmnop",
    ):
        try:
            validate_no_forbidden_content({"safe_field": value}, "synthetic")
        except ValueError:
            continue
        raise ValueError("CONTENT_VALUE_DENYLIST_UNEXPECTED_PASS")


def validate_report(report_path: Path = REPORT_PATH) -> dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    require(isinstance(report, dict), "REPORT_MUST_BE_OBJECT")
    require(isinstance(contract, dict), "CONTRACT_MUST_BE_OBJECT")
    validate_schema_validator_negative_checks()
    validate_content_safety_negative_checks()
    validate_schema_instance(report, contract, contract)
    validate_core_contract(report, contract)
    require(report["overall_status"] == "PASS", "REPORT_NOT_PASS")
    require(report["evidence_level"] == EVIDENCE_LEVEL, "EVIDENCE_LEVEL_MISMATCH")
    validate_baselines(report)
    validate_environment(report)
    validate_scenario_and_identities(report)
    validate_security_cases(report)
    validate_gates(report)
    validate_test_runs(report)
    validate_failure_injections(report)
    validate_restart_evidence(report)
    validate_artifacts(report)
    validate_cleanup(report)
    validate_timeline(report)
    validate_content_safety_and_level4(report)

    checksum_payload = dict(report)
    checksum_payload.pop("report_checksum", None)
    checksum_payload.pop("replayed_report_checksum", None)
    checksum = stable_hash(checksum_payload)
    require(report["report_checksum"] == checksum, "REPORT_CHECKSUM_MISMATCH")
    require(report["replayed_report_checksum"] == checksum, "REPLAY_CHECKSUM_MISMATCH")
    return {
        "status": "PASS",
        "checks": {
            "artifact_file_digests": True,
            "baseline_checksums": True,
            "content_safe": True,
            "content_safety_negative_checks": True,
            "failure_injection_bindings": True,
            "g2_p1_r8_to_g3_p2_r9": True,
            "report_checksum": True,
            "restart_process_and_container": True,
            "saved_restart_report_three_way_binding": True,
            "schema_nested_shape_and_negative_checks": True,
            "security_case_stage_and_defense_outcomes": True,
            "twenty_hard_gates": True,
        },
        "report_checksum": checksum,
        "saved_report_checksum": report["report_checksum"],
    }


def main() -> int:
    try:
        result = validate_report()
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "safe_reason": "DAY105_L3_EVIDENCE_REPLAY_FAILED",
                    "error_type": type(exc).__name__,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
