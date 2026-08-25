"""Day74 output contracts and permissioned tool-call boundary.

The module is deliberately provider-neutral and standard-library-only.  A
Provider response is untrusted candidate data.  It must be parsed, validated,
authorized, and admitted before the executor may observe it.  A tool return is
also an untrusted candidate until outcome verification and guarded durable
completion succeed.

This is deterministic in-process evidence, not a production runtime.  The
schema validator implements only the explicitly documented teaching subset of
JSON Schema.  The stores and locks model atomic boundaries; they are not a
database, cross-process fencing, or exactly-once proof for an external service.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Dict, Iterator, Mapping, Optional, Set, Tuple


class AdmissionStatus(str, Enum):
    ALLOWED = "ALLOWED"
    PARSE_FAILURE = "PARSE_FAILURE"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    INCOMPATIBLE_TOOL_VERSION = "INCOMPATIBLE_TOOL_VERSION"
    TOOL_DISABLED = "TOOL_DISABLED"
    UNAUTHORIZED = "UNAUTHORIZED"
    SEMANTICALLY_INVALID = "SEMANTICALLY_INVALID"


class ToolLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ExecutionStatus(str, Enum):
    EXECUTED = "EXECUTED"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    REJECTED_DISABLED = "REJECTED_DISABLED"


class OutcomeStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARSE_FAILURE = "PARSE_FAILURE"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SEMANTICALLY_INVALID = "SEMANTICALLY_INVALID"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"


class JobStatus(str, Enum):
    RUNNING = "RUNNING"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    SUCCEEDED = "SUCCEEDED"
    CANCELLED = "CANCELLED"


class CompletionStatus(str, Enum):
    COMMITTED = "COMMITTED"
    PENDING_RECONCILIATION = "PENDING_RECONCILIATION"
    REJECTED_UNVERIFIED = "REJECTED_UNVERIFIED"
    NOOP_STALE = "NOOP_STALE"
    NOOP_TERMINAL = "NOOP_TERMINAL"


@dataclass(frozen=True)
class AuthContext:
    """Trusted server context; never reconstructed from model arguments."""

    tenant_id: str
    user_id: str
    role: str


@dataclass(frozen=True)
class Report:
    tenant_id: str
    report_id: str
    status: ReportStatus
    version: int


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    version: str
    arguments_schema: Mapping[str, Any]


@dataclass(frozen=True)
class AdmittedToolCall:
    """Immutable server-normalized command allowed into the executor."""

    attempt_id: str
    job_id: str
    tool_call_id: str
    tool_name: str
    tool_version: str
    tenant_id: str
    report_id: str
    expected_report_version: int
    idempotency_key: str


@dataclass(frozen=True)
class AdmissionDecision:
    status: AdmissionStatus
    tool_call_id: Optional[str] = None
    safe_reason_code: str = ""
    admitted_call: Optional[AdmittedToolCall] = None


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    operation_id: Optional[str]


@dataclass(frozen=True)
class OutcomeDecision:
    status: OutcomeStatus
    safe_reason_code: str


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    status: JobStatus
    current_attempt_id: str
    current_tool_call_id: str
    verified_operation_id: Optional[str] = None


@dataclass(frozen=True)
class CompletionDecision:
    status: CompletionStatus
    job_status: JobStatus


def _is_json_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def validate_schema_subset(
    instance: Any,
    schema: Mapping[str, Any],
    *,
    path: str = "$",
) -> Tuple[str, ...]:
    """Return deterministic errors for the documented Day74 schema subset.

    Supported keywords: type, properties, required, enum, minimum, maximum,
    minLength, maxLength, items, and additionalProperties.  An unsupported
    keyword is a programming error so this validator cannot silently weaken a
    contract.
    """

    supported = {
        "type",
        "properties",
        "required",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "items",
        "additionalProperties",
    }
    unsupported = sorted(set(schema) - supported)
    if unsupported:
        raise ValueError(
            f"unsupported schema keywords at {path}: {unsupported}"
        )

    errors = []
    expected_type = schema.get("type")
    if (
        expected_type is not None
        and not _is_json_type(instance, expected_type)
    ):
        return (f"{path}: expected {expected_type}",)

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength")

    if (
        isinstance(instance, (int, float))
        and not isinstance(instance, bool)
    ):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above maximum")

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for name in required:
            if name not in instance:
                errors.append(f"{path}: missing required property {name!r}")
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in properties:
                    errors.append(f"{path}: additional property {name!r}")
        for name, value in instance.items():
            child_schema = properties.get(name)
            if child_schema is not None:
                errors.extend(
                    validate_schema_subset(
                        value,
                        child_schema,
                        path=f"{path}.{name}",
                    )
                )

    if isinstance(instance, list) and "items" in schema:
        for index, value in enumerate(instance):
            errors.extend(
                validate_schema_subset(
                    value,
                    schema["items"],
                    path=f"{path}[{index}]",
                )
            )

    return tuple(errors)


TOOL_CALL_ENVELOPE_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["tool_call"]},
        "tool_call_id": {"type": "string", "minLength": 1},
        "tool_name": {"type": "string", "minLength": 1},
        "tool_version": {"type": "string", "minLength": 1},
        "arguments": {"type": "object"},
    },
    "required": [
        "kind",
        "tool_call_id",
        "tool_name",
        "tool_version",
        "arguments",
    ],
    "additionalProperties": False,
}


PUBLISH_REPORT_V1_ARGUMENTS_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "tenant_id": {"type": "string", "minLength": 1},
        "report_id": {"type": "string", "minLength": 1},
    },
    "required": ["tenant_id", "report_id"],
    "additionalProperties": False,
}


PUBLISH_REPORT_V1_OUTCOME_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "operation_id": {"type": "string", "minLength": 1},
        "published": {"type": "boolean"},
        "report": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string", "minLength": 1},
                "version": {"type": "integer", "minimum": 1},
            },
            "required": ["report_id", "version"],
            "additionalProperties": False,
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string", "maxLength": 256},
        },
        "error": {"type": "string", "minLength": 1, "maxLength": 256},
    },
    "required": ["operation_id", "published", "report", "warnings"],
    "additionalProperties": False,
}


class ToolRegistry:
    """Server-owned exact-name/exact-version allowlist and lifecycle."""

    def __init__(self, definitions: Tuple[ToolDefinition, ...]) -> None:
        self._lock = threading.RLock()
        self._definitions: Dict[Tuple[str, str], ToolDefinition] = {}
        self._names: Set[str] = set()
        self._status: Dict[Tuple[str, str], ToolLifecycleStatus] = {}
        for definition in definitions:
            key = (definition.name, definition.version)
            if key in self._definitions:
                raise ValueError(f"duplicate tool definition {key}")
            self._definitions[key] = definition
            self._names.add(definition.name)
            self._status[key] = ToolLifecycleStatus.ACTIVE

    def disable(self, name: str, version: str) -> None:
        with self._lock:
            key = (name, version)
            if key not in self._definitions:
                raise KeyError(f"cannot disable unknown tool version {key}")
            self._status[key] = ToolLifecycleStatus.DISABLED

    def status(self, name: str, version: str) -> ToolLifecycleStatus:
        with self._lock:
            return self._status.get(
                (name, version),
                ToolLifecycleStatus.UNKNOWN,
            )

    def is_active(self, name: str, version: str) -> bool:
        return self.status(name, version) is ToolLifecycleStatus.ACTIVE

    def resolve(
        self,
        name: str,
        version: str,
    ) -> Tuple[Optional[ToolDefinition], AdmissionStatus]:
        with self._lock:
            key = (name, version)
            definition = self._definitions.get(key)
            if definition is not None:
                if self._status[key] is ToolLifecycleStatus.DISABLED:
                    return None, AdmissionStatus.TOOL_DISABLED
                return definition, AdmissionStatus.ALLOWED
            if name in self._names:
                return None, AdmissionStatus.INCOMPATIBLE_TOOL_VERSION
            return None, AdmissionStatus.UNKNOWN_TOOL

    @contextmanager
    def active_execution_guard(
        self,
        name: str,
        version: str,
    ) -> Iterator[bool]:
        """Serialize the final in-process lifecycle check with simulation.

        Holding this lock across a real HTTP call would be inappropriate.  A
        production implementation needs a durable claim/fencing design and
        external idempotency where available.
        """

        with self._lock:
            yield self._status.get(
                (name, version),
                ToolLifecycleStatus.UNKNOWN,
            ) is ToolLifecycleStatus.ACTIVE


class InMemoryReportStore:
    """Tenant-scoped business-state fixture, not durable storage."""

    def __init__(self, reports: Tuple[Report, ...]) -> None:
        self._reports = {
            (report.tenant_id, report.report_id): report for report in reports
        }

    def get_for_authorized_tenant(
        self,
        tenant_id: str,
        report_id: str,
    ) -> Optional[Report]:
        return self._reports.get((tenant_id, report_id))


class InMemoryToolExecutor:
    """In-process atomic-claim model, not external exactly-once proof."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: Dict[str, ExecutionResult] = {}
        self._effect_counts: Dict[Tuple[str, str, int], int] = {}

    def execute(
        self,
        call: AdmittedToolCall,
        *,
        registry: ToolRegistry,
    ) -> ExecutionResult:
        with registry.active_execution_guard(
            call.tool_name,
            call.tool_version,
        ) as active:
            if not active:
                return ExecutionResult(ExecutionStatus.REJECTED_DISABLED, None)

            with self._lock:
                existing = self._operations.get(call.idempotency_key)
                if existing is not None:
                    return ExecutionResult(
                        ExecutionStatus.DUPLICATE_SUPPRESSED,
                        existing.operation_id,
                    )

                operation_id = "op:" + hashlib.sha256(
                    call.idempotency_key.encode("utf-8")
                ).hexdigest()
                effect_key = (
                    call.tenant_id,
                    call.report_id,
                    call.expected_report_version,
                )
                self._effect_counts[effect_key] = (
                    self._effect_counts.get(effect_key, 0) + 1
                )
                result = ExecutionResult(
                    ExecutionStatus.EXECUTED,
                    operation_id,
                )
                self._operations[call.idempotency_key] = result
                return result

    def effect_count(self, call: AdmittedToolCall) -> int:
        with self._lock:
            return self._effect_counts.get(
                (
                    call.tenant_id,
                    call.report_id,
                    call.expected_report_version,
                ),
                0,
            )


class InMemoryDurableStore:
    """Guarded in-process state model; not PostgreSQL evidence."""

    def __init__(self, jobs: Tuple[JobRecord, ...]) -> None:
        self._lock = threading.RLock()
        self._jobs = {job.job_id: job for job in jobs}

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    @staticmethod
    def _matches(job: JobRecord, call: AdmittedToolCall) -> bool:
        return (
            job.current_attempt_id == call.attempt_id
            and job.current_tool_call_id == call.tool_call_id
        )

    def mark_timeout_unknown(
        self,
        *,
        call: AdmittedToolCall,
    ) -> CompletionDecision:
        with self._lock:
            job = self._jobs[call.job_id]
            if not self._matches(job, call):
                return CompletionDecision(
                    CompletionStatus.NOOP_STALE,
                    job.status,
                )
            if job.status in {JobStatus.SUCCEEDED, JobStatus.CANCELLED}:
                return CompletionDecision(
                    CompletionStatus.NOOP_TERMINAL,
                    job.status,
                )
            updated = replace(job, status=JobStatus.PENDING_RECONCILIATION)
            self._jobs[job.job_id] = updated
            return CompletionDecision(
                CompletionStatus.PENDING_RECONCILIATION,
                updated.status,
            )

    def guarded_complete(
        self,
        *,
        call: AdmittedToolCall,
        outcome: OutcomeDecision,
        operation_id: str,
    ) -> CompletionDecision:
        with self._lock:
            job = self._jobs[call.job_id]
            if not self._matches(job, call):
                return CompletionDecision(
                    CompletionStatus.NOOP_STALE,
                    job.status,
                )
            if job.status in {JobStatus.SUCCEEDED, JobStatus.CANCELLED}:
                return CompletionDecision(
                    CompletionStatus.NOOP_TERMINAL,
                    job.status,
                )
            if outcome.status is not OutcomeStatus.VERIFIED:
                return CompletionDecision(
                    CompletionStatus.REJECTED_UNVERIFIED,
                    job.status,
                )
            updated = replace(
                job,
                status=JobStatus.SUCCEEDED,
                verified_operation_id=operation_id,
            )
            self._jobs[job.job_id] = updated
            return CompletionDecision(
                CompletionStatus.COMMITTED,
                updated.status,
            )


def _parse_json_object(raw: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, False
    if not isinstance(parsed, dict):
        return None, True
    return parsed, True


def admit_tool_call(
    raw_provider_output: str,
    *,
    attempt_id: str,
    job_id: str,
    registry: ToolRegistry,
    auth: AuthContext,
    reports: InMemoryReportStore,
) -> AdmissionDecision:
    """Validate and admit one candidate tool call without executing it."""

    candidate, parsed = _parse_json_object(raw_provider_output)
    if not parsed:
        return AdmissionDecision(
            AdmissionStatus.PARSE_FAILURE,
            safe_reason_code="MALFORMED_JSON",
        )
    if candidate is None or validate_schema_subset(
        candidate,
        TOOL_CALL_ENVELOPE_SCHEMA,
    ):
        return AdmissionDecision(
            AdmissionStatus.SCHEMA_INVALID,
            safe_reason_code="ENVELOPE_SCHEMA_INVALID",
        )

    tool_call_id = candidate["tool_call_id"]
    definition, resolution = registry.resolve(
        candidate["tool_name"],
        candidate["tool_version"],
    )
    if definition is None:
        return AdmissionDecision(
            resolution,
            tool_call_id,
            safe_reason_code=resolution.value,
        )

    arguments = candidate["arguments"]
    if validate_schema_subset(arguments, definition.arguments_schema):
        return AdmissionDecision(
            AdmissionStatus.SCHEMA_INVALID,
            tool_call_id,
            safe_reason_code="ARGUMENT_SCHEMA_INVALID",
        )

    # Model arguments are candidate data.  Only auth is trusted identity.
    if arguments["tenant_id"] != auth.tenant_id or auth.role != "publisher":
        return AdmissionDecision(
            AdmissionStatus.UNAUTHORIZED,
            tool_call_id,
            safe_reason_code="PUBLISH_NOT_AUTHORIZED",
        )

    # Query tenant-scoped state only after coarse authorization.  Missing and
    # non-draft share a safe reason to avoid a resource-existence oracle.
    report = reports.get_for_authorized_tenant(
        auth.tenant_id,
        arguments["report_id"],
    )
    if report is None or report.status is not ReportStatus.DRAFT:
        return AdmissionDecision(
            AdmissionStatus.SEMANTICALLY_INVALID,
            tool_call_id,
            safe_reason_code="REPORT_NOT_PUBLISHABLE",
        )

    idempotency_material = ":".join(
        (
            definition.name,
            definition.version,
            auth.tenant_id,
            report.report_id,
            str(report.version),
        )
    )
    admitted = AdmittedToolCall(
        attempt_id=attempt_id,
        job_id=job_id,
        tool_call_id=tool_call_id,
        tool_name=definition.name,
        tool_version=definition.version,
        tenant_id=auth.tenant_id,
        report_id=report.report_id,
        expected_report_version=report.version,
        idempotency_key=(
            "sha256:"
            + hashlib.sha256(idempotency_material.encode("utf-8")).hexdigest()
        ),
    )
    return AdmissionDecision(
        AdmissionStatus.ALLOWED,
        tool_call_id,
        safe_reason_code="ADMISSION_PASSED",
        admitted_call=admitted,
    )


def verify_publish_outcome(
    raw_tool_outcome: str,
    *,
    call: AdmittedToolCall,
    expected_operation_id: str,
) -> OutcomeDecision:
    """Verify an untrusted tool outcome without mutating durable job state."""

    candidate, parsed = _parse_json_object(raw_tool_outcome)
    if not parsed:
        return OutcomeDecision(
            OutcomeStatus.PARSE_FAILURE,
            "MALFORMED_OUTCOME_JSON",
        )
    if candidate is None or validate_schema_subset(
        candidate,
        PUBLISH_REPORT_V1_OUTCOME_SCHEMA,
    ):
        return OutcomeDecision(
            OutcomeStatus.SCHEMA_INVALID,
            "OUTCOME_SCHEMA_INVALID",
        )

    if candidate["published"] is not True or "error" in candidate:
        return OutcomeDecision(
            OutcomeStatus.SEMANTICALLY_INVALID,
            "OUTCOME_SEMANTICALLY_INVALID",
        )

    report = candidate["report"]
    if (
        candidate["operation_id"] != expected_operation_id
        or report["report_id"] != call.report_id
        or report["version"] != call.expected_report_version
    ):
        return OutcomeDecision(
            OutcomeStatus.IDENTITY_MISMATCH,
            "OUTCOME_IDENTITY_MISMATCH",
        )
    return OutcomeDecision(OutcomeStatus.VERIFIED, "OUTCOME_VERIFIED")


def default_registry() -> ToolRegistry:
    return ToolRegistry(
        (
            ToolDefinition(
                "publish_report",
                "v1",
                PUBLISH_REPORT_V1_ARGUMENTS_SCHEMA,
            ),
        )
    )


def default_report_store() -> InMemoryReportStore:
    return InMemoryReportStore(
        (
            Report("tenant-a", "report-7", ReportStatus.DRAFT, version=7),
            Report(
                "tenant-a",
                "report-published",
                ReportStatus.PUBLISHED,
                version=3,
            ),
            Report("tenant-b", "report-8", ReportStatus.DRAFT, version=2),
        )
    )
