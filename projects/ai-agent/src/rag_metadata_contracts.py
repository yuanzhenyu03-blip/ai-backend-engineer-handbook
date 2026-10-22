"""Application-owned Day97 metadata contracts.

Metadata describes a resource; it never grants authority.  Source-declared
values remain untrusted even after they are admitted into an immutable
snapshot.  Durable publication belongs to the Day97 metadata Committer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rag_chunking_contracts import stable_hash
from rag_ingestion_contracts import DocumentVersionIdentity


class MetadataOrigin(str, Enum):
    SYSTEM = "SYSTEM"
    DERIVED = "DERIVED"
    PARSER = "PARSER"
    SOURCE_DECLARED = "SOURCE_DECLARED"


class MetadataSensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PROTECTED = "PROTECTED"


class MetadataValueType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    STRING_LIST = "STRING_LIST"


MetadataValue = str | int | bool | tuple[str, ...]


@dataclass(frozen=True)
class MetadataFieldDefinition:
    namespace: str
    name: str
    value_type: MetadataValueType
    allowed_origins: frozenset[MetadataOrigin]
    sensitivity: MetadataSensitivity
    filterable: bool = False

    def __post_init__(self) -> None:
        if not self.namespace or not self.name or not self.allowed_origins:
            raise ValueError("metadata field definition must be complete")
        if self.filterable and self.sensitivity is MetadataSensitivity.PROTECTED:
            raise ValueError("protected metadata cannot be an index filter")

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}"


@dataclass(frozen=True)
class MetadataContract:
    version: str
    fields: tuple[MetadataFieldDefinition, ...]

    def __post_init__(self) -> None:
        if not self.version or not self.fields:
            raise ValueError("metadata contract requires a version and fields")
        names = tuple(field.qualified_name for field in self.fields)
        if len(names) != len(set(names)):
            raise ValueError("metadata field names must be unique")

    @property
    def fingerprint(self) -> str:
        return stable_hash({
            "version": self.version,
            "fields": [
                {
                    "namespace": field.namespace,
                    "name": field.name,
                    "value_type": field.value_type.value,
                    "allowed_origins": sorted(
                        origin.value for origin in field.allowed_origins
                    ),
                    "sensitivity": field.sensitivity.value,
                    "filterable": field.filterable,
                }
                for field in self.fields
            ],
        })

    def field(self, qualified_name: str) -> MetadataFieldDefinition | None:
        return next(
            (
                definition
                for definition in self.fields
                if definition.qualified_name == qualified_name
            ),
            None,
        )


@dataclass(frozen=True)
class MetadataAssertion:
    qualified_name: str
    value: MetadataValue
    origin: MetadataOrigin
    origin_reference: str

    def __post_init__(self) -> None:
        if not self.qualified_name or not self.origin_reference:
            raise ValueError("metadata assertion requires name and origin evidence")


@dataclass(frozen=True)
class MetadataProjectionOperation:
    version: DocumentVersionIdentity
    chunk_set_id: str
    operation_id: str
    idempotency_key: str
    contract_fingerprint: str
    expected_selection_revision: int
    expected_document_state_version: int
    expected_document_fence: int
    expected_snapshot_id: str | None = None
    expected_snapshot_revision: int = 0

    def __post_init__(self) -> None:
        if not all((
            self.chunk_set_id,
            self.operation_id,
            self.idempotency_key,
            self.contract_fingerprint,
        )):
            raise ValueError("metadata operation bindings are required")
        numeric = (
            self.expected_selection_revision,
            self.expected_document_state_version,
            self.expected_document_fence,
            self.expected_snapshot_revision,
        )
        if any(value < 0 for value in numeric):
            raise ValueError("metadata operation revisions must be non-negative")
        if (self.expected_snapshot_id is None) != (
            self.expected_snapshot_revision == 0
        ):
            raise ValueError("metadata snapshot pointer baseline is inconsistent")

    @property
    def stable_result_key(self) -> str:
        return stable_hash((
            self.version.tenant_id,
            self.version.document_id,
            self.version.document_version_id,
            self.chunk_set_id,
            self.operation_id,
            self.contract_fingerprint,
        ))


@dataclass(frozen=True)
class MetadataProjectionAttempt:
    operation_id: str
    attempt_number: int
    request_id: str
    generation: int

    def __post_init__(self) -> None:
        if not self.operation_id or not self.request_id:
            raise ValueError("metadata attempt correlation is required")
        if self.attempt_number <= 0 or self.generation <= 0:
            raise ValueError("metadata attempt and generation must be positive")


@dataclass(frozen=True)
class MetadataProjectionCandidate:
    operation: MetadataProjectionOperation
    attempt: MetadataProjectionAttempt
    assertions: tuple[MetadataAssertion, ...]


@dataclass(frozen=True)
class MetadataSnapshot:
    snapshot_id: str
    version: DocumentVersionIdentity
    chunk_set_id: str
    contract_version: str
    contract_fingerprint: str
    assertions: tuple[MetadataAssertion, ...]
    created_by_operation_id: str
    selection_revision: int
    document_state_version: int
    document_fence: int

    def __post_init__(self) -> None:
        if not all((
            self.snapshot_id,
            self.chunk_set_id,
            self.contract_version,
            self.contract_fingerprint,
            self.created_by_operation_id,
        )):
            raise ValueError("immutable metadata snapshot bindings are required")


@dataclass(frozen=True)
class MetadataSnapshotPointer:
    tenant_id: str
    document_id: str
    document_version_id: str
    chunk_set_id: str
    snapshot_id: str
    revision: int
