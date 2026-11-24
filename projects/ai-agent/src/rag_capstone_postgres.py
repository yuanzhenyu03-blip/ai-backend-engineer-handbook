"""PostgreSQL persistence boundary for the Day106 L3A capstone.

The repository stores only content-safe identities, digests, states, reason
codes, and timestamps.  It binds the existing Day104 lifecycle rows to the
existing Day106 request/retrieval/release contracts in one database
transaction.  It never stores source text, protected chunks, prompts, answer
text, provider responses, vectors, credentials, or a database URL.

Importing this module does not require psycopg2.  Database access is opt-in and
fails closed unless ``DAY106_L3_INTEGRATION=1`` is set (or a focused unit test
supplies ``integration_enabled=True``).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import re
from typing import Any, cast

from rag_capstone_contracts import (
    AnswerReleaseRecord,
    CapstoneRequestBinding,
    DispatchObservation,
    RecoveryAndIncidentRecord,
    ResponseIntent,
    ResponseIntentState,
    RetrievalAndContextReceipt,
)
from rag_chunking_contracts import stable_hash
from rag_index_lifecycle_postgres import (
    ConnectionFactory,
    CursorPort,
    psycopg2_connection_factory,
)


SCHEMA = "day106_l3"
INTEGRATION_FLAG = "DAY106_L3_INTEGRATION"
DATABASE_URL_ENV = "DAY106_L3_DATABASE_URL"
RESET_CONFIRMATION = "RESET_DAY106_L3_SCHEMAS"
RESET_DATABASE_NAME = "day106_l3"


class CapstoneRepositoryOutcome(str, Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    NOT_FOUND = "NOT_FOUND"
    STALE_CHAIN = "STALE_CHAIN"
    WINNER = "WINNER"
    LATE_DUPLICATE = "LATE_DUPLICATE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


class ProviderCallStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ProviderMode(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class CapstoneRepositoryResult:
    outcome: CapstoneRepositoryOutcome
    safe_reason: str
    durable_transition: bool = False
    identity_digest: str | None = None
    response_intent_id: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class StoredResponseIntent:
    intent_id: str
    release_record_id: str
    request_binding_digest: str
    output_release_decision_digest: str
    candidate_digest: str
    destination_digest: str
    dispatch_idempotency_key_digest: str
    identity_digest: str
    state: str
    created_at: str


@dataclass(frozen=True)
class StoredRecoveryRecord:
    record_id: str
    response_intent_id: str
    previous_record_id: str | None
    transport_attempt_id: str
    observation: str
    safe_reason_code: str
    provider_message_digest: str | None
    winner_status: str
    identity_digest: str
    observed_at: str


_SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_sha256(*values: str) -> None:
    if any(_SHA256_DIGEST.fullmatch(value) is None for value in values):
        raise ValueError("all durable digests must use canonical sha256 form")


@dataclass(frozen=True)
class ModelInvocationRecord:
    model_invocation_id: str
    model_invocation_digest: str
    request_binding_digest: str
    retrieval_context_receipt_digest: str
    retrieval_bundle_digest: str
    context_manifest_digest: str
    provider_mode: ProviderMode
    provider_identity_digest: str
    model_identity_digest: str
    config_digest: str
    contract_digest: str
    created_at: str

    def __post_init__(self) -> None:
        if not self.model_invocation_id.strip() or not self.created_at.strip():
            raise ValueError("model invocation identity and creation time are required")
        _require_sha256(
            self.model_invocation_digest,
            self.request_binding_digest,
            self.retrieval_context_receipt_digest,
            self.retrieval_bundle_digest,
            self.context_manifest_digest,
            self.provider_identity_digest,
            self.model_identity_digest,
            self.config_digest,
            self.contract_digest,
        )

    @property
    def digest(self) -> str:
        return stable_hash({**self.__dict__, "provider_mode": self.provider_mode.value})


@dataclass(frozen=True)
class ProviderCallAttempt:
    attempt_id: str
    request_binding_digest: str
    retrieval_context_receipt_digest: str
    model_invocation_id: str
    model_invocation_digest: str
    call_ordinal: int
    provider_request_idempotency_digest: str
    created_at: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.attempt_id, self.model_invocation_id, self.created_at)
        ):
            raise ValueError("provider attempt requires complete pre-send identity")
        if not 1 <= self.call_ordinal <= 10:
            raise ValueError("provider call ordinal must be between 1 and 10")
        _require_sha256(
            self.request_binding_digest,
            self.retrieval_context_receipt_digest,
            self.model_invocation_digest,
            self.provider_request_idempotency_digest,
        )

    @property
    def digest(self) -> str:
        return stable_hash(self.__dict__)


@dataclass(frozen=True)
class ProviderCallReceipt:
    """Content-safe L3B seam; raw provider data is deliberately impossible."""

    receipt_id: str
    provider_attempt_id: str
    request_binding_digest: str
    retrieval_context_receipt_digest: str
    model_invocation_id: str
    model_invocation_digest: str
    call_ordinal: int
    requested_model_id: str
    observed_model_id: str | None
    provider_response_id_digest: str | None
    answer_candidate_digest: str | None
    input_token_count: int | None
    output_token_count: int | None
    total_token_count: int | None
    status: ProviderCallStatus
    safe_reason_code: str
    observed_at: str

    def __post_init__(self) -> None:
        required = (
            self.receipt_id,
            self.provider_attempt_id,
            self.request_binding_digest,
            self.retrieval_context_receipt_digest,
            self.model_invocation_id,
            self.model_invocation_digest,
            self.requested_model_id,
            self.safe_reason_code,
            self.observed_at,
        )
        if not all(value.strip() for value in required):
            raise ValueError("provider call receipt requires complete identities")
        if not 1 <= self.call_ordinal <= 10:
            raise ValueError("provider call ordinal must be between 1 and 10")
        unsafe_model_identity = re.compile(
            r"postgres(?:ql)?://|(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}",
            re.IGNORECASE,
        )
        model_values = (self.requested_model_id,) + (
            () if self.observed_model_id is None else (self.observed_model_id,)
        )
        if any(
            len(value) > 256
            or "\x00" in value
            or "\n" in value
            or unsafe_model_identity.search(value)
            for value in model_values
        ):
            raise ValueError("provider model identity is not content-safe")
        counts = (
            self.input_token_count,
            self.output_token_count,
            self.total_token_count,
        )
        if any(value is not None and value < 0 for value in counts):
            raise ValueError("provider token counts cannot be negative")
        if self.total_token_count is not None and (
            self.input_token_count is None
            or self.output_token_count is None
            or self.total_token_count
            != self.input_token_count + self.output_token_count
        ):
            raise ValueError("observed total token count must be exact")
        for label, value in (
            ("provider response ID", self.provider_response_id_digest),
            ("answer candidate", self.answer_candidate_digest),
        ):
            if value is not None and _SHA256_DIGEST.fullmatch(value) is None:
                raise ValueError(f"{label} must be supplied only as a sha256 digest")
        if self.status is ProviderCallStatus.SUCCEEDED and (
            self.observed_model_id is None
            or self.provider_response_id_digest is None
            or self.answer_candidate_digest is None
            or self.input_token_count is None
            or self.output_token_count is None
            or self.total_token_count is None
        ):
            raise ValueError("successful provider call requires complete observed evidence")
        _require_sha256(
            self.request_binding_digest,
            self.retrieval_context_receipt_digest,
            self.model_invocation_digest,
        )

    @property
    def digest(self) -> str:
        return stable_hash(
            {
                "receipt_id": self.receipt_id,
                "provider_attempt_id": self.provider_attempt_id,
                "request_binding_digest": self.request_binding_digest,
                "retrieval_context_receipt_digest": self.retrieval_context_receipt_digest,
                "model_invocation_id": self.model_invocation_id,
                "model_invocation_digest": self.model_invocation_digest,
                "call_ordinal": self.call_ordinal,
                "requested_model_id": self.requested_model_id,
                "observed_model_id": self.observed_model_id,
                "provider_response_id_digest": self.provider_response_id_digest,
                "answer_candidate_digest": self.answer_candidate_digest,
                "input_token_count": self.input_token_count,
                "output_token_count": self.output_token_count,
                "total_token_count": self.total_token_count,
                "status": self.status.value,
                "safe_reason_code": self.safe_reason_code,
                "observed_at": self.observed_at,
            }
        )


def psycopg2_day106_connection_factory(dsn: str) -> ConnectionFactory:
    """Return the Day106-specific lazy psycopg2 connection factory."""

    return psycopg2_connection_factory(
        dsn,
        application_name="day106-l3-production-rag-capstone",
    )


def _destination_digest(destination: str) -> str:
    if not destination.strip():
        raise ValueError("authorized destination is required")
    return stable_hash(("DAY106_DESTINATION", destination))


def _idempotency_key_digest(key: str) -> str:
    if not key.strip():
        raise ValueError("dispatch idempotency key is required")
    return stable_hash(("DAY106_DISPATCH_IDEMPOTENCY_KEY", key))


def _provider_message_digest(message_id: str | None) -> str | None:
    if message_id is None:
        return None
    if not message_id.strip():
        raise ValueError("provider message ID cannot be empty")
    return stable_hash(("DAY106_PROVIDER_MESSAGE_ID", message_id))


class PostgresRagCapstoneRepository:
    """Application-owned durable Day106 execution and delivery repository."""

    def __init__(
        self,
        connect: ConnectionFactory,
        *,
        schema_path: str | Path | None = None,
        day104_schema_path: str | Path | None = None,
        day105_schema_path: str | Path | None = None,
        integration_enabled: bool | None = None,
    ) -> None:
        root = Path(__file__).resolve().parent.parent / "integration"
        self._connect = connect
        self._schema_path = Path(schema_path) if schema_path else root / "day106" / "schema.sql"
        self._day104_schema_path = (
            Path(day104_schema_path)
            if day104_schema_path
            else root / "day104" / "schema.sql"
        )
        self._day105_schema_path = (
            Path(day105_schema_path)
            if day105_schema_path
            else root / "day105" / "schema.sql"
        )
        self._integration_enabled = (
            os.environ.get(INTEGRATION_FLAG) == "1"
            if integration_enabled is None
            else integration_enabled
        )

    def _require_enabled(self) -> None:
        if not self._integration_enabled:
            raise RuntimeError(
                "Day106 L3 PostgreSQL access requires DAY106_L3_INTEGRATION=1"
            )

    @contextmanager
    def _transaction(self) -> Iterator[CursorPort]:
        self._require_enabled()
        connection = self._connect()
        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _lock(cursor: CursorPort, *identities: str) -> None:
        for identity in sorted(set(identities)):
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (identity,),
            )

    def install_schema(self) -> None:
        ddl = self._schema_path.read_text(encoding="utf-8")
        if not ddl.strip():
            raise ValueError("Day106 L3 schema cannot be empty")
        with self._transaction() as cursor:
            cursor.execute(ddl)

    def install_all_lab_schemas(self) -> None:
        """Install Day104, Day105, then Day106 in one transaction."""

        ddls = tuple(
            path.read_text(encoding="utf-8")
            for path in (
                self._day104_schema_path,
                self._day105_schema_path,
                self._schema_path,
            )
        )
        if any(not ddl.strip() for ddl in ddls):
            raise ValueError("all Day106 L3 prerequisite schemas must be non-empty")
        with self._transaction() as cursor:
            for ddl in ddls:
                cursor.execute(ddl)

    def reset_lab_schemas(self, *, confirmation: str) -> None:
        if confirmation != RESET_CONFIRMATION:
            raise ValueError(
                f"schema reset requires confirmation {RESET_CONFIRMATION!r}"
            )
        with self._transaction() as cursor:
            cursor.execute("SELECT current_database()")
            row = cursor.fetchone()
            if row is None or row[0] != RESET_DATABASE_NAME:
                raise ValueError("schema reset is restricted to the day106_l3 database")
            cursor.execute(
                "SELECT public.reset_day106_l3_schemas(%s, %s)",
                ("1", confirmation),
            )

    @staticmethod
    def _find_digest(
        cursor: CursorPort,
        *,
        table: str,
        id_column: str,
        identity: str,
    ) -> str | None:
        allowed = {
            ("request_bindings", "request_binding_id"),
            ("retrieval_context_receipts", "receipt_id"),
            ("answer_release_records", "record_id"),
            ("response_intents", "intent_id"),
            ("dispatch_recovery_delivery_records", "record_id"),
            ("provider_call_receipts", "receipt_id"),
            ("model_invocations", "model_invocation_id"),
            ("provider_call_attempts", "attempt_id"),
        }
        if (table, id_column) not in allowed:
            raise ValueError("unsupported immutable identity lookup")
        cursor.execute(
            f"SELECT identity_digest FROM {SCHEMA}.{table} "
            f"WHERE {id_column} = %s FOR UPDATE",
            (identity,),
        )
        row = cursor.fetchone()
        return None if row is None else cast(str, row[0])

    @staticmethod
    def _verify_cross_binding(
        binding: CapstoneRequestBinding,
        receipt: RetrievalAndContextReceipt,
    ) -> None:
        if receipt.request_binding_digest != binding.digest:
            raise ValueError("retrieval receipt does not bind the exact request")
        if (
            receipt.prompt_authorization_scope_fingerprint
            != binding.retrieval_authorization_scope_fingerprint
            or receipt.prompt_authorization_revision_digest
            != binding.retrieval_authorization_revision_digest
        ):
            raise ValueError("prompt authorization binding mismatch")
        if receipt.unauthorized_prompt_count != 0:
            raise ValueError("Unauthorized occurrence entering Prompt must equal zero")

    @staticmethod
    def _verify_lifecycle_rows(
        cursor: CursorPort,
        binding: CapstoneRequestBinding,
        receipt: RetrievalAndContextReceipt,
    ) -> None:
        cursor.execute(
            """
            SELECT view.pointer_name, view.generation_id, view.pointer_revision,
                   view.fencing_token, view.build_snapshot_fingerprint,
                   view.authorization_snapshot_id, view.status,
                   generation.manifest_digest, generation.state,
                   snapshot.source_snapshot_id, snapshot.deletion_snapshot_id
            FROM day104_l3.read_views AS view
            JOIN day104_l3.generations AS generation
              ON generation.generation_id = view.generation_id
            JOIN day104_l3.build_snapshots AS snapshot
              ON snapshot.build_snapshot_id = generation.build_snapshot_id
            WHERE view.view_id = %s
            FOR SHARE OF view, generation, snapshot
            """,
            (binding.read_view_id,),
        )
        row = cursor.fetchone()
        expected = (
            binding.pointer_name,
            binding.generation_id,
            binding.pointer_revision,
            binding.read_view_fence,
            binding.build_snapshot_fingerprint,
            binding.authorization_snapshot_id,
        )
        if row is None or tuple(row[:6]) != expected:
            raise ValueError("READ_VIEW_DATABASE_BINDING_MISMATCH")
        if row[6] != "OPEN" or row[7] != binding.generation_manifest_digest:
            raise ValueError("READ_VIEW_OR_MANIFEST_NOT_CURRENT_FOR_EXECUTION")
        if row[8] not in {"ACTIVE", "DRAINING"}:
            raise ValueError("READ_VIEW_GENERATION_NOT_SERVABLE")
        if row[9] != binding.source_snapshot_id or row[10] != binding.deletion_snapshot_id:
            raise ValueError("BUILD_SNAPSHOT_CURRENTNESS_BINDING_MISMATCH")

        cursor.execute(
            """
            SELECT occurrence_id, content_digest, tenant_id
            FROM day104_l3.index_points
            WHERE generation_id = %s AND occurrence_id = ANY(%s)
            ORDER BY occurrence_id
            FOR SHARE
            """,
            (binding.generation_id, list(receipt.exact_occurrence_ids)),
        )
        points = cursor.fetchall()
        observed = tuple((str(item[0]), str(item[1])) for item in points)
        expected_points = tuple(
            sorted(zip(receipt.exact_occurrence_ids, receipt.exact_content_digests))
        )
        if observed != expected_points or any(
            str(item[2]) != binding.tenant_id for item in points
        ):
            raise ValueError("EXACT_OCCURRENCE_DATABASE_BINDING_MISMATCH")

        cursor.execute(
            """
            SELECT current.snapshot_id, current.revision,
                   snapshot.authorization_snapshot_id,
                   snapshot.occurrence_ids,
                   snapshot.security_policy_digest
            FROM day105_l3.current_security_snapshots AS current
            JOIN day105_l3.security_snapshots AS snapshot
              ON snapshot.tenant_id = current.tenant_id
             AND snapshot.snapshot_id = current.snapshot_id
             AND snapshot.revision = current.revision
            WHERE current.tenant_id = %s
            FOR SHARE OF current, snapshot
            """,
            (binding.tenant_id,),
        )
        security = cursor.fetchone()
        if security is None:
            raise ValueError("CURRENT_SECURITY_SNAPSHOT_NOT_FOUND")
        current_occurrences = {str(item) for item in security[3]}
        if (
            security[0] != binding.authorization_snapshot_id
            or security[2] != binding.authorization_snapshot_id
            or int(security[1]) <= 0
            or not set(receipt.exact_occurrence_ids).issubset(current_occurrences)
            or security[4] != binding.policy_fingerprint
        ):
            raise ValueError("CURRENT_SECURITY_SNAPSHOT_BINDING_MISMATCH")

    @staticmethod
    def _insert_request_binding(
        cursor: CursorPort,
        binding: CapstoneRequestBinding,
    ) -> None:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.request_bindings
                (request_binding_id, request_attempt_id, request_id,
                 principal_id, tenant_id, purpose, audience, pointer_name,
                 generation_id, generation_artifact_digest,
                 generation_manifest_digest, build_snapshot_fingerprint,
                 pointer_revision, read_view_id, read_view_fence,
                 read_view_digest, source_snapshot_id,
                 authorization_snapshot_id, deletion_snapshot_id,
                 policy_fingerprint, security_binding_fingerprint,
                 retrieval_authorization_revision_digest,
                 retrieval_authorization_scope_fingerprint,
                 selected_retrieval_bundle_id,
                 selected_retrieval_bundle_revision,
                 selected_retrieval_bundle_fingerprint,
                 identity_digest, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s)
            """,
            (
                binding.request_attempt_id,
                binding.request_attempt_id,
                binding.request_id,
                binding.principal_id,
                binding.tenant_id,
                binding.purpose,
                binding.audience,
                binding.pointer_name,
                binding.generation_id,
                binding.generation_artifact_digest,
                binding.generation_manifest_digest,
                binding.build_snapshot_fingerprint,
                binding.pointer_revision,
                binding.read_view_id,
                binding.read_view_fence,
                binding.read_view_digest,
                binding.source_snapshot_id,
                binding.authorization_snapshot_id,
                binding.deletion_snapshot_id,
                binding.policy_fingerprint,
                binding.security_binding_fingerprint,
                binding.retrieval_authorization_revision_digest,
                binding.retrieval_authorization_scope_fingerprint,
                binding.selected_retrieval_bundle_id,
                binding.selected_retrieval_bundle_revision,
                binding.selected_retrieval_bundle_fingerprint,
                binding.digest,
                binding.created_at,
            ),
        )

    @staticmethod
    def _insert_retrieval_receipt(
        cursor: CursorPort,
        receipt: RetrievalAndContextReceipt,
    ) -> None:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.retrieval_context_receipts
                (receipt_id, request_binding_digest, retrieval_operation_id,
                 retrieval_request_id, day101_execution_receipt_digest,
                 day101_handoff_digest,
                 prompt_authorization_scope_fingerprint,
                 prompt_authorization_revision_digest, retrieval_bundle_id,
                 retrieval_bundle_digest, retrieval_security_decision_digest,
                 bundle_security_decision_digest, exact_occurrence_ids,
                 exact_content_digests, context_manifest_id,
                 context_manifest_digest, context_occurrence_ids,
                 assembled_context_digest, unauthorized_prompt_count,
                 identity_digest, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                receipt.receipt_id,
                receipt.request_binding_digest,
                receipt.retrieval_operation_id,
                receipt.retrieval_request_id,
                receipt.day101_execution_receipt_digest,
                receipt.day101_handoff_digest,
                receipt.prompt_authorization_scope_fingerprint,
                receipt.prompt_authorization_revision_digest,
                receipt.retrieval_bundle_id,
                receipt.retrieval_bundle_digest,
                receipt.retrieval_security_decision_digest,
                receipt.bundle_security_decision_digest,
                list(receipt.exact_occurrence_ids),
                list(receipt.exact_content_digests),
                receipt.context_manifest_id,
                receipt.context_manifest_digest,
                list(receipt.context_occurrence_ids),
                receipt.assembled_context_digest,
                receipt.unauthorized_prompt_count,
                receipt.digest,
                receipt.created_at,
            ),
        )

    def append_cross_bound_execution(
        self,
        binding: CapstoneRequestBinding,
        receipt: RetrievalAndContextReceipt,
    ) -> CapstoneRepositoryResult:
        """Atomically bind real lifecycle rows to the Day106 request chain."""

        self._verify_cross_binding(binding, receipt)
        with self._transaction() as cursor:
            self._lock(
                cursor,
                f"request-attempt:{binding.request_attempt_id}",
                f"retrieval-context:{receipt.receipt_id}",
            )
            binding_digest = self._find_digest(
                cursor,
                table="request_bindings",
                id_column="request_binding_id",
                identity=binding.request_attempt_id,
            )
            receipt_digest = self._find_digest(
                cursor,
                table="retrieval_context_receipts",
                id_column="receipt_id",
                identity=receipt.receipt_id,
            )
            if binding_digest is not None or receipt_digest is not None:
                if binding_digest == binding.digest and receipt_digest == receipt.digest:
                    return CapstoneRepositoryResult(
                        CapstoneRepositoryOutcome.EXACT_REPLAY,
                        "EXACT_CROSS_BOUND_EXECUTION_REPLAY",
                        identity_digest=receipt.digest,
                    )
                if (binding_digest is None) != (receipt_digest is None):
                    return CapstoneRepositoryResult(
                        CapstoneRepositoryOutcome.INTEGRITY_FAILED,
                        "PARTIAL_CROSS_BOUND_EXECUTION_FOUND",
                    )
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "REQUEST_OR_RETRIEVAL_ID_REUSED_WITH_DIFFERENT_CONTENT",
                )
            self._verify_lifecycle_rows(cursor, binding, receipt)
            self._insert_request_binding(cursor, binding)
            self._insert_retrieval_receipt(cursor, receipt)
            return CapstoneRepositoryResult(
                CapstoneRepositoryOutcome.APPLIED,
                "REAL_LIFECYCLE_AND_DAY106_EXECUTION_BOUND_ATOMICALLY",
                durable_transition=True,
                identity_digest=receipt.digest,
            )

    def append_model_invocation(
        self,
        invocation: ModelInvocationRecord,
    ) -> CapstoneRepositoryResult:
        """Persist the exact invocation identity before any provider send."""

        with self._transaction() as cursor:
            self._lock(cursor, f"model-invocation:{invocation.model_invocation_id}")
            existing = self._find_digest(
                cursor,
                table="model_invocations",
                id_column="model_invocation_id",
                identity=invocation.model_invocation_id,
            )
            if existing is not None:
                exact = existing == invocation.digest
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_MODEL_INVOCATION_REPLAY"
                    if exact
                    else "MODEL_INVOCATION_ID_REUSED",
                    identity_digest=invocation.digest,
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.model_invocations
                    (model_invocation_id, model_invocation_digest,
                     request_binding_digest, retrieval_context_receipt_digest,
                     retrieval_bundle_digest, context_manifest_digest,
                     provider_mode, provider_identity_digest,
                     model_identity_digest, config_digest, contract_digest,
                     identity_digest, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    invocation.model_invocation_id,
                    invocation.model_invocation_digest,
                    invocation.request_binding_digest,
                    invocation.retrieval_context_receipt_digest,
                    invocation.retrieval_bundle_digest,
                    invocation.context_manifest_digest,
                    invocation.provider_mode.value,
                    invocation.provider_identity_digest,
                    invocation.model_identity_digest,
                    invocation.config_digest,
                    invocation.contract_digest,
                    invocation.digest,
                    invocation.created_at,
                ),
            )
            return CapstoneRepositoryResult(
                CapstoneRepositoryOutcome.APPLIED,
                "MODEL_INVOCATION_PERSISTED_BEFORE_SEND",
                durable_transition=True,
                identity_digest=invocation.digest,
            )

    def reserve_provider_call_attempt(
        self,
        attempt: ProviderCallAttempt,
    ) -> CapstoneRepositoryResult:
        """Append the pre-send reservation; no network call is performed here."""

        with self._transaction() as cursor:
            self._lock(
                cursor,
                f"provider-attempt:{attempt.model_invocation_id}:{attempt.call_ordinal}",
            )
            existing = self._find_digest(
                cursor,
                table="provider_call_attempts",
                id_column="attempt_id",
                identity=attempt.attempt_id,
            )
            if existing is not None:
                exact = existing == attempt.digest
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_PROVIDER_ATTEMPT_REPLAY"
                    if exact
                    else "PROVIDER_ATTEMPT_ID_REUSED",
                    identity_digest=attempt.digest,
                )
            cursor.execute(
                f"""
                SELECT attempt_id FROM {SCHEMA}.provider_call_attempts
                WHERE model_invocation_id = %s AND call_ordinal = %s FOR UPDATE
                """,
                (attempt.model_invocation_id, attempt.call_ordinal),
            )
            if cursor.fetchone() is not None:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "PROVIDER_CALL_ORDINAL_ALREADY_RESERVED",
                )
            cursor.execute(
                f"""
                SELECT provider_mode FROM {SCHEMA}.model_invocations
                WHERE model_invocation_id = %s
                  AND model_invocation_digest = %s
                  AND request_binding_digest = %s
                  AND retrieval_context_receipt_digest = %s
                FOR SHARE
                """,
                (
                    attempt.model_invocation_id,
                    attempt.model_invocation_digest,
                    attempt.request_binding_digest,
                    attempt.retrieval_context_receipt_digest,
                ),
            )
            invocation = cursor.fetchone()
            if invocation is None or invocation[0] != ProviderMode.EXTERNAL.value:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.INTEGRITY_FAILED,
                    "PROVIDER_ATTEMPT_REQUIRES_EXACT_EXTERNAL_INVOCATION",
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.provider_call_attempts
                    (attempt_id, request_binding_digest,
                     retrieval_context_receipt_digest, model_invocation_id,
                     model_invocation_digest, call_ordinal,
                     provider_request_idempotency_digest, state,
                     identity_digest, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'RESERVED', %s, %s)
                """,
                (
                    attempt.attempt_id,
                    attempt.request_binding_digest,
                    attempt.retrieval_context_receipt_digest,
                    attempt.model_invocation_id,
                    attempt.model_invocation_digest,
                    attempt.call_ordinal,
                    attempt.provider_request_idempotency_digest,
                    attempt.digest,
                    attempt.created_at,
                ),
            )
            return CapstoneRepositoryResult(
                CapstoneRepositoryOutcome.APPLIED,
                "PROVIDER_CALL_ATTEMPT_RESERVED_BEFORE_SEND",
                durable_transition=True,
                identity_digest=attempt.digest,
            )

    def append_provider_call_receipt(
        self,
        receipt: ProviderCallReceipt,
    ) -> CapstoneRepositoryResult:
        """Append an L3B call receipt without accepting any raw provider value."""

        with self._transaction() as cursor:
            self._lock(
                cursor,
                f"provider-call:{receipt.request_binding_digest}:"
                f"{receipt.model_invocation_id}:{receipt.call_ordinal}",
                f"provider-call-receipt:{receipt.receipt_id}",
            )
            existing = self._find_digest(
                cursor,
                table="provider_call_receipts",
                id_column="receipt_id",
                identity=receipt.receipt_id,
            )
            if existing is not None:
                exact = existing == receipt.digest
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.EXACT_REPLAY
                    if exact
                    else CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_PROVIDER_CALL_RECEIPT_REPLAY"
                    if exact
                    else "PROVIDER_CALL_RECEIPT_ID_REUSED",
                    identity_digest=receipt.digest,
                )
            cursor.execute(
                f"""
                SELECT receipt_id, identity_digest
                FROM {SCHEMA}.provider_call_receipts
                WHERE request_binding_digest = %s
                  AND model_invocation_id = %s
                  AND call_ordinal = %s
                FOR UPDATE
                """,
                (
                    receipt.request_binding_digest,
                    receipt.model_invocation_id,
                    receipt.call_ordinal,
                ),
            )
            ordinal = cursor.fetchone()
            if ordinal is not None:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "PROVIDER_CALL_ORDINAL_ALREADY_BOUND",
                    identity_digest=receipt.digest,
                )
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.provider_call_receipts
                    (receipt_id, provider_attempt_id, request_binding_digest,
                     retrieval_context_receipt_digest, model_invocation_id,
                     model_invocation_digest, call_ordinal,
                     requested_model_id, observed_model_id,
                     provider_response_id_digest, answer_candidate_digest,
                     input_token_count, output_token_count, total_token_count,
                     status, safe_reason_code, identity_digest, observed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    receipt.receipt_id,
                    receipt.provider_attempt_id,
                    receipt.request_binding_digest,
                    receipt.retrieval_context_receipt_digest,
                    receipt.model_invocation_id,
                    receipt.model_invocation_digest,
                    receipt.call_ordinal,
                    receipt.requested_model_id,
                    receipt.observed_model_id,
                    receipt.provider_response_id_digest,
                    receipt.answer_candidate_digest,
                    receipt.input_token_count,
                    receipt.output_token_count,
                    receipt.total_token_count,
                    receipt.status.value,
                    receipt.safe_reason_code,
                    receipt.digest,
                    receipt.observed_at,
                ),
            )
            return CapstoneRepositoryResult(
                CapstoneRepositoryOutcome.APPLIED,
                "CONTENT_SAFE_PROVIDER_CALL_RECEIPT_APPENDED",
                durable_transition=True,
                identity_digest=receipt.digest,
            )

    def read_provider_call_receipts(
        self,
        request_binding_digest: str,
    ) -> tuple[ProviderCallReceipt, ...]:
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT receipt_id, provider_attempt_id, request_binding_digest,
                       retrieval_context_receipt_digest, model_invocation_id,
                       model_invocation_digest, call_ordinal,
                       requested_model_id, observed_model_id,
                       provider_response_id_digest, answer_candidate_digest,
                       input_token_count, output_token_count, total_token_count,
                       status, safe_reason_code, observed_at::text
                FROM {SCHEMA}.provider_call_receipts
                WHERE request_binding_digest = %s
                ORDER BY call_ordinal
                """,
                (request_binding_digest,),
            )
            return tuple(
                ProviderCallReceipt(
                    receipt_id=str(row[0]),
                    provider_attempt_id=str(row[1]),
                    request_binding_digest=str(row[2]),
                    retrieval_context_receipt_digest=str(row[3]),
                    model_invocation_id=str(row[4]),
                    model_invocation_digest=str(row[5]),
                    call_ordinal=int(row[6]),
                    requested_model_id=str(row[7]),
                    observed_model_id=None if row[8] is None else str(row[8]),
                    provider_response_id_digest=(
                        None if row[9] is None else str(row[9])
                    ),
                    answer_candidate_digest=(
                        None if row[10] is None else str(row[10])
                    ),
                    input_token_count=None if row[11] is None else int(row[11]),
                    output_token_count=None if row[12] is None else int(row[12]),
                    total_token_count=None if row[13] is None else int(row[13]),
                    status=ProviderCallStatus(str(row[14])),
                    safe_reason_code=str(row[15]),
                    observed_at=str(row[16]),
                )
                for row in cursor.fetchall()
            )

    @staticmethod
    def _validate_release_and_intent(
        release: AnswerReleaseRecord,
        intent: ResponseIntent | None,
    ) -> None:
        releases = release.result == "PASS" and release.disposition == "RELEASE"
        if not releases:
            if intent is not None:
                raise ValueError("blocked/abstained release cannot create an intent")
            return
        if intent is None:
            raise ValueError("PASS/RELEASE requires an atomically bound intent")
        if (
            intent.intent_id != release.response_intent_id
            or intent.request_binding_digest != release.request_binding_digest
            or intent.output_release_decision_digest
            != release.output_release_decision_digest
            or intent.candidate_digest != release.answer_candidate_digest
            or intent.destination != release.authorized_destination
            or intent.dispatch_idempotency_key != release.dispatch_idempotency_key
            or intent.state is not ResponseIntentState.PENDING
            or intent.revision != 1
        ):
            raise ValueError("response intent does not exactly bind the release")

    @staticmethod
    def _insert_release_record(
        cursor: CursorPort,
        release: AnswerReleaseRecord,
    ) -> None:
        destination_digest = (
            None
            if release.authorized_destination is None
            else _destination_digest(release.authorized_destination)
        )
        key_digest = (
            None
            if release.dispatch_idempotency_key is None
            else _idempotency_key_digest(release.dispatch_idempotency_key)
        )
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.answer_release_records
                (record_id, request_binding_digest,
                 retrieval_context_receipt_digest, model_invocation_id,
                 model_invocation_digest, answer_candidate_id,
                 answer_candidate_digest, release_evidence_id,
                 release_evidence_digest, output_release_decision_id,
                 output_release_decision_digest, disclosure_envelope_digest,
                 tenant_id, principal_id, action, purpose,
                 current_authorization_scope_fingerprint,
                 current_authorization_revision_digest,
                 release_currentness_snapshot_id,
                 release_currentness_snapshot_digest,
                 release_currentness_revision, released_occurrence_ids,
                 authorized_destination_digest,
                 dispatch_idempotency_key_digest, result, disposition,
                 safe_reason_codes, response_intent_id,
                 response_dispatch_state, identity_digest, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                release.record_id,
                release.request_binding_digest,
                release.retrieval_context_receipt_digest,
                release.model_invocation_id,
                release.model_invocation_digest,
                release.answer_candidate_id,
                release.answer_candidate_digest,
                release.release_evidence_id,
                release.release_evidence_digest,
                release.output_release_decision_id,
                release.output_release_decision_digest,
                release.disclosure_envelope_digest,
                release.tenant_id,
                release.principal_id,
                release.action,
                release.purpose,
                release.current_authorization_scope_fingerprint,
                release.current_authorization_revision_digest,
                release.release_currentness_snapshot_id,
                release.release_currentness_snapshot_digest,
                release.release_currentness_revision,
                list(release.released_occurrence_ids),
                destination_digest,
                key_digest,
                release.result,
                release.disposition,
                list(release.safe_reason_codes),
                release.response_intent_id,
                release.response_dispatch_state.value,
                release.digest,
                release.created_at,
            ),
        )

    @staticmethod
    def _insert_intent(
        cursor: CursorPort,
        release: AnswerReleaseRecord,
        intent: ResponseIntent,
    ) -> None:
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.response_intents
                (intent_id, release_record_id, request_binding_digest,
                 output_release_decision_digest, candidate_digest,
                 destination_digest, dispatch_idempotency_key_digest,
                 initial_state, revision, identity_digest, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                intent.intent_id,
                release.record_id,
                intent.request_binding_digest,
                intent.output_release_decision_digest,
                intent.candidate_digest,
                _destination_digest(intent.destination),
                _idempotency_key_digest(intent.dispatch_idempotency_key),
                intent.state.value,
                intent.revision,
                intent.digest,
                intent.created_at,
            ),
        )

    def commit_release_and_intent(
        self,
        release: AnswerReleaseRecord,
        intent: ResponseIntent | None,
    ) -> CapstoneRepositoryResult:
        """Atomically commit the durable decision and optional release intent."""

        self._validate_release_and_intent(release, intent)
        with self._transaction() as cursor:
            self._lock(
                cursor,
                f"release-decision:{release.output_release_decision_id}",
                f"release-record:{release.record_id}",
                *(tuple() if intent is None else (f"response-intent:{intent.intent_id}",)),
            )
            release_digest = self._find_digest(
                cursor,
                table="answer_release_records",
                id_column="record_id",
                identity=release.record_id,
            )
            intent_digest = None
            if intent is not None:
                intent_digest = self._find_digest(
                    cursor,
                    table="response_intents",
                    id_column="intent_id",
                    identity=intent.intent_id,
                )
            if release_digest is not None or intent_digest is not None:
                expected_intent = None if intent is None else intent.digest
                if release_digest == release.digest and intent_digest == expected_intent:
                    return CapstoneRepositoryResult(
                        CapstoneRepositoryOutcome.EXACT_REPLAY,
                        "EXACT_RELEASE_AND_INTENT_REPLAY",
                        identity_digest=release.digest,
                        response_intent_id=release.response_intent_id,
                    )
                if intent is not None and (release_digest is None) != (intent_digest is None):
                    return CapstoneRepositoryResult(
                        CapstoneRepositoryOutcome.INTEGRITY_FAILED,
                        "PARTIAL_RELEASE_INTENT_TRANSACTION_FOUND",
                    )
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "RELEASE_OR_INTENT_ID_REUSED_WITH_DIFFERENT_CONTENT",
                )
            cursor.execute(
                f"""
                SELECT provider_mode FROM {SCHEMA}.model_invocations
                WHERE model_invocation_id = %s
                  AND model_invocation_digest = %s
                  AND request_binding_digest = %s
                  AND retrieval_context_receipt_digest = %s
                FOR SHARE
                """,
                (
                    release.model_invocation_id,
                    release.model_invocation_digest,
                    release.request_binding_digest,
                    release.retrieval_context_receipt_digest,
                ),
            )
            invocation = cursor.fetchone()
            if invocation is None:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.INTEGRITY_FAILED,
                    "RELEASE_MODEL_INVOCATION_BINDING_MISSING",
                )
            releases = release.result == "PASS" and release.disposition == "RELEASE"
            if invocation[0] == ProviderMode.EXTERNAL.value and releases:
                cursor.execute(
                    f"""
                    SELECT receipt_id FROM {SCHEMA}.provider_call_receipts
                    WHERE request_binding_digest = %s
                      AND retrieval_context_receipt_digest = %s
                      AND model_invocation_id = %s
                      AND model_invocation_digest = %s
                      AND answer_candidate_digest = %s
                      AND status = 'SUCCEEDED'
                    FOR SHARE
                    """,
                    (
                        release.request_binding_digest,
                        release.retrieval_context_receipt_digest,
                        release.model_invocation_id,
                        release.model_invocation_digest,
                        release.answer_candidate_digest,
                    ),
                )
                if cursor.fetchone() is None:
                    return CapstoneRepositoryResult(
                        CapstoneRepositoryOutcome.INTEGRITY_FAILED,
                        "EXTERNAL_RELEASE_REQUIRES_EXACT_SUCCEEDED_PROVIDER_RECEIPT",
                    )
            self._insert_release_record(cursor, release)
            if intent is not None:
                self._insert_intent(cursor, release, intent)
            return CapstoneRepositoryResult(
                CapstoneRepositoryOutcome.APPLIED,
                "RELEASE_DECISION_AND_INTENT_COMMITTED_ATOMICALLY",
                durable_transition=True,
                identity_digest=release.digest,
                response_intent_id=release.response_intent_id,
                state=release.response_dispatch_state.value,
            )

    @staticmethod
    def _winner(
        cursor: CursorPort,
        intent_id: str,
    ) -> Sequence[Any] | None:
        cursor.execute(
            f"""
            SELECT winner_record_id, provider_message_digest,
                   transport_attempt_id, identity_digest
            FROM {SCHEMA}.dispatch_winners
            WHERE response_intent_id = %s
            FOR UPDATE
            """,
            (intent_id,),
        )
        return cursor.fetchone()

    @staticmethod
    def _append_winner(
        cursor: CursorPort,
        record: RecoveryAndIncidentRecord,
        provider_digest: str,
    ) -> str:
        identity_digest = stable_hash(
            {
                "response_intent_id": record.response_intent_id,
                "winner_record_id": record.record_id,
                "provider_message_digest": provider_digest,
                "transport_attempt_id": record.transport_attempt_id,
                "won_at": record.observed_at,
            }
        )
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.dispatch_winners
                (response_intent_id, winner_record_id,
                 provider_message_digest, transport_attempt_id,
                 identity_digest, won_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                record.response_intent_id,
                record.record_id,
                provider_digest,
                record.transport_attempt_id,
                identity_digest,
                record.observed_at,
            ),
        )
        return identity_digest

    @staticmethod
    def _current_tail(cursor: CursorPort, intent_id: str) -> str | None:
        cursor.execute(
            f"""
            SELECT item.record_id
            FROM {SCHEMA}.dispatch_recovery_delivery_records AS item
            WHERE item.response_intent_id = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM {SCHEMA}.dispatch_recovery_delivery_records AS successor
                  WHERE successor.previous_record_id = item.record_id
              )
            FOR UPDATE
            """,
            (intent_id,),
        )
        rows = cursor.fetchall()
        if len(rows) > 1:
            raise RuntimeError("DISPATCH_HISTORY_ALREADY_BRANCHES")
        return None if not rows else cast(str, rows[0][0])

    def append_recovery_record(
        self,
        record: RecoveryAndIncidentRecord,
    ) -> CapstoneRepositoryResult:
        """Append an observation and converge duplicate outcomes with one winner."""

        key_digest = _idempotency_key_digest(record.dispatch_idempotency_key)
        provider_digest = _provider_message_digest(record.provider_message_id)
        with self._transaction() as cursor:
            self._lock(cursor, f"response-intent:{record.response_intent_id}")
            existing = self._find_digest(
                cursor,
                table="dispatch_recovery_delivery_records",
                id_column="record_id",
                identity=record.record_id,
            )
            if existing is not None:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.EXACT_REPLAY
                    if existing == record.digest
                    else CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "EXACT_RECOVERY_RECORD_REPLAY"
                    if existing == record.digest
                    else "RECOVERY_RECORD_ID_REUSED_WITH_DIFFERENT_CONTENT",
                    identity_digest=record.digest,
                    response_intent_id=record.response_intent_id,
                )

            cursor.execute(
                f"""
                SELECT dispatch_idempotency_key_digest
                FROM {SCHEMA}.response_intents
                WHERE intent_id = %s FOR UPDATE
                """,
                (record.response_intent_id,),
            )
            intent = cursor.fetchone()
            if intent is None:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.NOT_FOUND,
                    "RESPONSE_INTENT_NOT_FOUND",
                )
            if intent[0] != key_digest:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.IDENTITY_CONFLICT,
                    "DISPATCH_IDEMPOTENCY_AUTHORITY_MISMATCH",
                )
            tail = self._current_tail(cursor, record.response_intent_id)
            if tail != record.previous_record_id:
                return CapstoneRepositoryResult(
                    CapstoneRepositoryOutcome.STALE_CHAIN,
                    "RECOVERY_PREDECESSOR_IS_NOT_CURRENT_TAIL",
                    response_intent_id=record.response_intent_id,
                )

            winner_status = "NONE"
            winner = self._winner(cursor, record.response_intent_id)
            if record.observation is DispatchObservation.ACCEPTED:
                if provider_digest is None:
                    raise ValueError("ACCEPTED requires provider message identity")
                if winner is None:
                    self._append_winner(cursor, record, provider_digest)
                    winner_status = "WINNER"
                elif winner[1] == provider_digest:
                    winner_status = "DUPLICATE"
                else:
                    winner_status = "CONFLICT"
            elif record.observation in {
                DispatchObservation.DELIVERED,
                DispatchObservation.DUPLICATE_RECEIPT,
            }:
                if provider_digest is None:
                    raise ValueError("delivery evidence requires provider message identity")
                if winner is None:
                    return CapstoneRepositoryResult(
                        CapstoneRepositoryOutcome.INTEGRITY_FAILED,
                        "DELIVERY_RECEIPT_WITHOUT_DISPATCH_WINNER",
                    )
                winner_status = "DUPLICATE" if winner[1] == provider_digest else "CONFLICT"

            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.dispatch_recovery_delivery_records
                    (record_id, response_intent_id, previous_record_id,
                     transport_attempt_id, dispatch_idempotency_key_digest,
                     observation, safe_reason_code, evidence_digests,
                     provider_message_digest, winner_status,
                     identity_digest, observed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.record_id,
                    record.response_intent_id,
                    record.previous_record_id,
                    record.transport_attempt_id,
                    key_digest,
                    record.observation.value,
                    record.safe_reason_code,
                    list(record.evidence_digests),
                    provider_digest,
                    winner_status,
                    record.digest,
                    record.observed_at,
                ),
            )
            if winner_status == "CONFLICT":
                outcome = CapstoneRepositoryOutcome.IDEMPOTENCY_CONFLICT
                reason = "IDEMPOTENCY_CONFLICT_RECORDED_AND_RELEASE_BLOCKED"
            elif winner_status == "WINNER":
                outcome = CapstoneRepositoryOutcome.WINNER
                reason = "FIRST_ACCEPTED_RESULT_WON_FENCE"
            elif winner_status == "DUPLICATE":
                outcome = CapstoneRepositoryOutcome.LATE_DUPLICATE
                reason = "LATE_DUPLICATE_RECORDED_WITHOUT_REWRITING_WINNER"
            else:
                outcome = CapstoneRepositoryOutcome.APPLIED
                reason = "RECOVERY_OBSERVATION_APPENDED"
            return CapstoneRepositoryResult(
                outcome,
                reason,
                durable_transition=True,
                identity_digest=record.digest,
                response_intent_id=record.response_intent_id,
                state=self._read_state(cursor, record.response_intent_id),
            )

    @staticmethod
    def _read_state(cursor: CursorPort, intent_id: str) -> str | None:
        cursor.execute(
            f"SELECT state FROM {SCHEMA}.current_response_states WHERE intent_id = %s",
            (intent_id,),
        )
        row = cursor.fetchone()
        return None if row is None else cast(str, row[0])

    def read_response_intent(self, intent_id: str) -> StoredResponseIntent | None:
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                SELECT intent.intent_id, intent.release_record_id,
                       intent.request_binding_digest,
                       intent.output_release_decision_digest,
                       intent.candidate_digest, intent.destination_digest,
                       intent.dispatch_idempotency_key_digest,
                       intent.identity_digest, state.state,
                       intent.created_at::text
                FROM {SCHEMA}.response_intents AS intent
                JOIN {SCHEMA}.current_response_states AS state
                  ON state.intent_id = intent.intent_id
                WHERE intent.intent_id = %s
                """,
                (intent_id,),
            )
            row = cursor.fetchone()
            return None if row is None else StoredResponseIntent(*row)

    def read_recovery_history(
        self,
        intent_id: str,
    ) -> tuple[StoredRecoveryRecord, ...]:
        with self._transaction() as cursor:
            cursor.execute(
                f"""
                WITH RECURSIVE history AS (
                    SELECT item.*, 1 AS depth
                    FROM {SCHEMA}.dispatch_recovery_delivery_records AS item
                    WHERE item.response_intent_id = %s
                      AND item.previous_record_id IS NULL
                    UNION ALL
                    SELECT item.*, history.depth + 1
                    FROM {SCHEMA}.dispatch_recovery_delivery_records AS item
                    JOIN history ON item.previous_record_id = history.record_id
                )
                SELECT record_id, response_intent_id, previous_record_id,
                       transport_attempt_id, observation, safe_reason_code,
                       provider_message_digest, winner_status,
                       identity_digest, observed_at::text
                FROM history ORDER BY depth
                """,
                (intent_id,),
            )
            return tuple(StoredRecoveryRecord(*row) for row in cursor.fetchall())

    def durable_state_identity(self, intent_id: str) -> str | None:
        """Content-safe restart identity for one complete durable response chain."""

        intent = self.read_response_intent(intent_id)
        if intent is None:
            return None
        history = self.read_recovery_history(intent_id)
        return stable_hash(
            {
                "intent_identity_digest": intent.identity_digest,
                "state": intent.state,
                "recovery_record_digests": tuple(item.identity_digest for item in history),
            }
        )


__all__ = [
    "CapstoneRepositoryOutcome",
    "CapstoneRepositoryResult",
    "DATABASE_URL_ENV",
    "INTEGRATION_FLAG",
    "PostgresRagCapstoneRepository",
    "ModelInvocationRecord",
    "ProviderCallAttempt",
    "ProviderCallReceipt",
    "ProviderCallStatus",
    "ProviderMode",
    "RESET_CONFIRMATION",
    "StoredRecoveryRecord",
    "StoredResponseIntent",
    "psycopg2_day106_connection_factory",
]
