"""Day64 — pure Extraction / Network-Evidence / Artifact decision core (standard library only).

Turns an AUTHORIZED, isolated Day63 browser session (tenant/session/origin/identity-bound, lease-
fenced) into STRUCTURED, CORRELATED, VALIDATED, DURABLE Artifact evidence — WITHOUT confusing any
of these observations with business truth:

    page lifecycle signal  !=  extraction readiness  !=  valid Artifact  !=  published business success

Trusted Artifact publication (the whole chain, not any single link):
    authorized Session
    AND fresh isolated Context
    AND task-contract business-ready fact
    AND correctly correlated network/DOM/download evidence
    AND schema/content validation
    AND Object Storage HEAD verification
    AND durable Artifact reference
    AND the final Day63 authorization fence

This module is the DECISION CORE only — separated from any real Playwright/Object-Storage/PostgreSQL/
Worker runtime so the RULES are unit-testable WITHOUT a browser, a bucket, or a database. It REUSES
the Day63 final fence (``day63_session_gate.final_fence``) so the Day63 authorization boundary still
governs publication.

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``tests/test_day64_extraction_contract.py`` (authored + run by the updating agent). They prove the
RULES only — NOT real dynamic-page extraction, real network interception, real download/upload, real
Object Storage HEAD, or a real DB transaction. That is a separate ``INTEGRATION_RUNTIME`` and is NOT
RUN (see the design/runbook). The live classroom artifact was ``CONCEPTUAL_STATIC``. No secrets,
Cookies, Authorization headers, credentials, real target URLs, or raw sensitive payloads live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Sequence

from day63_session_gate import Outcome, SessionMeta, final_fence


# ---------------------------------------------------------------------------
# 1) Task-contract readiness — a page load / HTTP 200 is an observation, not success.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TaskContract:
    expected_report_id: str
    terminal_status: str                 # the business-ready status, e.g. "ready"
    required_fields: frozenset            # required schema fields for a record
    extraction_contract_version: str
    allow_partial_import: bool = False


@dataclass(frozen=True)
class ReportObservation:
    report_id: str
    status: str                          # e.g. "generating" (HTTP 200 but NOT ready) or "ready"
    records: Sequence[Mapping]           # the network-JSON candidate rows


class Readiness(str, Enum):
    READY = "READY"
    NOT_READY_STATUS = "NOT_READY_STATUS"        # e.g. status="generating" despite HTTP 200
    REPORT_ID_MISMATCH = "REPORT_ID_MISMATCH"
    SCHEMA_INCOMPLETE = "SCHEMA_INCOMPLETE"


def evaluate_readiness(contract: TaskContract, obs: ReportObservation) -> Readiness:
    """A report is READY only when its expected identity, terminal business status, and required
    schema all meet the task contract. ``{report_id:"42", status:"generating", rows:[]}`` blocks
    publication despite HTTP 200."""
    if obs.report_id != contract.expected_report_id:
        return Readiness.REPORT_ID_MISMATCH
    if obs.status != contract.terminal_status:
        return Readiness.NOT_READY_STATUS
    for rec in obs.records:
        if not contract.required_fields.issubset(set(rec.keys())):
            return Readiness.SCHEMA_INCOMPLETE
    return Readiness.READY


# ---------------------------------------------------------------------------
# 2) DOM vs network roles — corroborate with explicit roles, never merge silently.
# ---------------------------------------------------------------------------
class SourceRole(str, Enum):
    NETWORK_PRIMARY = "NETWORK_PRIMARY"      # network JSON is the structured-data candidate (default)
    DOM_PRIMARY = "DOM_PRIMARY"              # only when the contract requests user-visible text
    CORROBORATING = "CORROBORATING"


def choose_primary_source(contract_wants_visible_text: bool) -> SourceRole:
    """Network JSON is the primary structured-data candidate; the DOM corroborates visible/readiness
    state (the DOM may show rounded/virtualized data). If the contract requests user-visible text, the
    DOM is primary instead. Sources are never merged without a stated role."""
    return SourceRole.DOM_PRIMARY if contract_wants_visible_text else SourceRole.NETWORK_PRIMARY


# ---------------------------------------------------------------------------
# 3) Strict network correlation — a URL substring + HTTP 200 is too broad.
# ---------------------------------------------------------------------------
_FORBIDDEN_METADATA_KEYS = frozenset({
    "cookie", "cookies", "authorization", "set-cookie", "credentials", "token", "password",
    "raw_payload", "body", "headers",
})


@dataclass(frozen=True)
class ExportAction:
    """OUR action identity, created before the click (analogous to Day61's correlation key)."""
    allowed_origin: str
    method: str                          # must be POST for the export action
    normalized_endpoint: str             # e.g. "/api/exports"
    report_id: str
    client_request_id: str


@dataclass(frozen=True)
class NetworkEvidence:
    allowed_origin: str
    method: str
    normalized_endpoint: str
    report_id: str
    client_request_id: Optional[str]
    export_id: Optional[str]
    response_status: int
    safe_checksum: str
    observed_at: int


class Correlation(str, Enum):
    CORRELATED = "CORRELATED"
    ORIGIN_MISMATCH = "ORIGIN_MISMATCH"
    METHOD_MISMATCH = "METHOD_MISMATCH"          # e.g. a background GET poll
    ENDPOINT_MISMATCH = "ENDPOINT_MISMATCH"
    REPORT_ID_MISMATCH = "REPORT_ID_MISMATCH"
    MISSING_ACTION_ID = "MISSING_ACTION_ID"      # no client_request_id/export_id -> too broad
    BAD_STATUS = "BAD_STATUS"


def correlate_export(expected: ExportAction, observed: NetworkEvidence) -> Correlation:
    """Prove the observed response belongs to THIS Export action. A background poll (``GET`` on the
    same URL) or a missing ``client_request_id``/``export_id`` must NOT correlate — a URL substring
    plus HTTP 200 is too broad."""
    if observed.allowed_origin != expected.allowed_origin:
        return Correlation.ORIGIN_MISMATCH
    if observed.method != expected.method:                 # POST action vs background GET
        return Correlation.METHOD_MISMATCH
    if observed.normalized_endpoint != expected.normalized_endpoint:
        return Correlation.ENDPOINT_MISMATCH
    if observed.report_id != expected.report_id:
        return Correlation.REPORT_ID_MISMATCH
    if not (observed.client_request_id == expected.client_request_id and observed.client_request_id) \
            and not observed.export_id:
        return Correlation.MISSING_ACTION_ID
    if not (200 <= observed.response_status < 300):
        return Correlation.BAD_STATUS
    return Correlation.CORRELATED


def assert_safe_network_metadata(metadata: Mapping) -> bool:
    """Store only SAFE/redacted metadata: normalized endpoint, method, IDs, status, timestamp, and a
    payload checksum. NEVER store Cookies, Authorization headers, credentials, or unrelated raw
    payloads. Returns True iff no forbidden key is present."""
    return all(k.lower() not in _FORBIDDEN_METADATA_KEYS for k in metadata.keys())


# ---------------------------------------------------------------------------
# 4) Extraction Contract versioning — never silently map drifted fields.
# ---------------------------------------------------------------------------
class SchemaOutcome(str, Enum):
    OK = "OK"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"      # renamed/removed/type-changed/unclear, no reviewed rule


def classify_schema(
    required_fields: frozenset,
    observed_fields: frozenset,
    reviewed_compat: Optional[Mapping[str, str]] = None,
) -> SchemaOutcome:
    """Each required field must be satisfied DIRECTLY (present in ``observed_fields``) or via an
    EXPLICIT, REVIEWED compatibility rule (``observed_name -> required_name``). Renaming ``score`` to
    ``relevance_score`` without a reviewed rule is an Extraction Contract Mismatch; do not silently map
    renamed, removed, type-changed, or semantically unclear fields."""
    reviewed_compat = reviewed_compat or {}
    satisfied_by_compat = {required for observed, required in reviewed_compat.items()
                           if observed in observed_fields}
    for req in required_fields:
        if req in observed_fields or req in satisfied_by_compat:
            continue
        return SchemaOutcome.CONTRACT_MISMATCH
    return SchemaOutcome.OK


# ---------------------------------------------------------------------------
# 5) Download validation + precise counts.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DownloadCandidate:
    provenance_action_id: Optional[str]   # ties the file to a correlated action
    transfer_complete: bool
    byte_size: int
    declared_content_type: str            # from the filename/header (NOT trusted alone)
    actual_content_type: str              # sniffed from bytes
    sha256: Optional[str]
    parsed_ok: bool
    schema_valid: bool
    business_valid: bool
    expected_content_type: str = "text/csv"


class DownloadOutcome(str, Enum):
    VALID = "VALID"
    NO_PROVENANCE = "NO_PROVENANCE"
    INCOMPLETE_TRANSFER = "INCOMPLETE_TRANSFER"
    BAD_SIZE = "BAD_SIZE"
    CONTENT_TYPE_MISMATCH = "CONTENT_TYPE_MISMATCH"   # filename ext lied; actual type differs
    CHECKSUM_MISSING = "CHECKSUM_MISSING"
    PARSE_FAILED = "PARSE_FAILED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    BUSINESS_INVALID = "BUSINESS_INVALID"


def validate_download(c: DownloadCandidate, max_bytes: int = 50_000_000) -> DownloadOutcome:
    """Download validation requires provenance, a completed transfer, a bounded NONZERO size, the
    ACTUAL content type (never the filename extension alone), a SHA-256, successful parsing, schema
    validation, and business constraints. Any failure blocks Artifact publication."""
    if not c.provenance_action_id:
        return DownloadOutcome.NO_PROVENANCE
    if not c.transfer_complete:
        return DownloadOutcome.INCOMPLETE_TRANSFER
    if c.byte_size <= 0 or c.byte_size > max_bytes:
        return DownloadOutcome.BAD_SIZE
    if c.actual_content_type != c.expected_content_type:   # trust sniffed type, not the filename
        return DownloadOutcome.CONTENT_TYPE_MISMATCH
    if not c.sha256:
        return DownloadOutcome.CHECKSUM_MISSING
    if not c.parsed_ok:
        return DownloadOutcome.PARSE_FAILED
    if not c.schema_valid:
        return DownloadOutcome.SCHEMA_INVALID
    if not c.business_valid:
        return DownloadOutcome.BUSINESS_INVALID
    return DownloadOutcome.VALID


@dataclass(frozen=True)
class UploadOutcomeFacts:
    import_id: Optional[str]              # a terminal import identity (None while only 202 Accepted)
    terminal_status: Optional[str]        # e.g. "imported"/"failed" (None while not terminal)
    accepted_count: int
    rejected_count: int
    rejection_summary: Sequence[str] = ()


class UploadResult(str, Enum):
    IMPORT_SUCCESS = "IMPORT_SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"          # rejects present AND the contract permits partial
    PARTIAL_NOT_ALLOWED = "PARTIAL_NOT_ALLOWED"  # rejects present but the contract forbids partial
    NOT_TERMINAL = "NOT_TERMINAL"                # 202 Accepted / file selection is NOT success
    IMPORT_FAILED = "IMPORT_FAILED"


def classify_upload(facts: UploadOutcomeFacts, allow_partial: bool) -> UploadResult:
    """File selection and ``202 Accepted`` do not prove target import success. A terminal
    ``import_id`` + status + accepted/rejected counts + rejection summary are required. ``498 accepted,
    2 rejected`` is successful ONLY if the explicit task contract permits partial results."""
    if not facts.import_id or facts.terminal_status is None:
        return UploadResult.NOT_TERMINAL
    if facts.terminal_status != "imported":
        return UploadResult.IMPORT_FAILED
    if facts.rejected_count > 0:
        return UploadResult.PARTIAL_SUCCESS if allow_partial else UploadResult.PARTIAL_NOT_ALLOWED
    return UploadResult.IMPORT_SUCCESS


# ---------------------------------------------------------------------------
# 6) Object Storage HEAD + DB-reference consistency (reuses the Day61 boundary rule).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ArtifactManifest:
    tenant_id: str
    job_id: str
    attempt_id: str
    session_id: str
    session_version: int
    object_key: str
    content_type: str
    byte_size: int
    sha256: str
    object_storage_head_verified: bool = False


@dataclass(frozen=True)
class HeadMetadata:
    exists: bool
    byte_size: Optional[int]
    sha256: Optional[str]
    content_type: Optional[str]


class HeadOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    ABSENT = "ABSENT"
    MISMATCH = "MISMATCH"


def verify_head(manifest: ArtifactManifest, head: HeadMetadata) -> HeadOutcome:
    """Object existence is not Job success. After a deterministic object-key upload, verify
    size/checksum/content-type with HEAD. A mismatch is a conflict (never overwrite/succeed)."""
    if not head.exists:
        return HeadOutcome.ABSENT
    if (head.byte_size == manifest.byte_size
            and head.sha256 == manifest.sha256
            and head.content_type == manifest.content_type):
        return HeadOutcome.VERIFIED
    return HeadOutcome.MISMATCH


class PersistDecision(str, Enum):
    PUBLISH = "PUBLISH"                    # HEAD verified AND DB Artifact-reference committed
    RETAIN_CANDIDATE = "RETAIN_CANDIDATE"  # HEAD verified but DB ref failed -> keep private, reconcile
    FORWARD_REPAIR = "FORWARD_REPAIR"      # upload-timeout then matching HEAD -> use verified object
    NOT_VERIFIED = "NOT_VERIFIED"          # HEAD absent/mismatch -> no publish


def classify_persist(head: HeadOutcome, db_ref_committed: bool,
                     upload_timed_out: bool = False) -> PersistDecision:
    """After HEAD verification: DB ref committed -> PUBLISH; DB ref FAILED -> RETAIN_CANDIDATE (do not
    publish, reconcile/forward-repair; orphan GC is only later, audited, retention-governed cleanup).
    An upload timeout followed by a MATCHING HEAD -> FORWARD_REPAIR (use the verified object; never
    blind re-upload/overwrite/delete)."""
    if head is not HeadOutcome.VERIFIED:
        return PersistDecision.NOT_VERIFIED
    if upload_timed_out and not db_ref_committed:
        return PersistDecision.FORWARD_REPAIR
    if not db_ref_committed:
        return PersistDecision.RETAIN_CANDIDATE
    return PersistDecision.PUBLISH


# ---------------------------------------------------------------------------
# 7) Final fence STILL controls publishing (Day63 boundary preserved).
# ---------------------------------------------------------------------------
class PublishDecision(str, Enum):
    PUBLISH = "PUBLISH"
    RETAIN_UNPUBLISHED = "RETAIN_UNPUBLISHED"   # fence failed after an Artifact exists -> private, untrusted


def final_publish_decision(
    persist: PersistDecision,
    fence_meta: SessionMeta,
    worker_token: str,
    claimed_version: int,
    attempt_id: str,
    now: int,
    *,
    fence_timed_out: bool = False,
) -> PublishDecision:
    """Even with a HEAD-verified object and a committed reference, the Day63 FINAL fence still
    governs: if the Session is revoked / the fence fails / times out, do NOT write the Artifact
    reference or Job success — retain the candidate PRIVATELY as unpublished/untrusted audit/
    reconciliation material; do not immediately GC it."""
    if persist is not PersistDecision.PUBLISH:
        return PublishDecision.RETAIN_UNPUBLISHED
    fence = final_fence(fence_meta, worker_token, claimed_version, attempt_id, now,
                        timed_out=fence_timed_out)
    return PublishDecision.PUBLISH if fence is Outcome.AUTHORIZED else PublishDecision.RETAIN_UNPUBLISHED


# ---------------------------------------------------------------------------
# 8) Orchestrator — the whole chain; proves each failure BLOCKS publication.
# ---------------------------------------------------------------------------
@dataclass
class ArtifactResult:
    published: bool
    stage: str                            # the stage that decided the outcome
    reason: str                           # the specific enum value
    candidate_retained: bool = False      # a private candidate kept for reconciliation (never GC'd now)
    trace: List[str] = field(default_factory=list)   # stages that passed, in order


@dataclass
class AssemblyInputs:
    contract: TaskContract
    observation: ReportObservation
    expected_action: ExportAction
    observed_network: NetworkEvidence
    stored_metadata: Mapping
    observed_fields: frozenset
    reviewed_compat: Optional[Mapping[str, str]]
    download: DownloadCandidate
    upload: UploadOutcomeFacts
    manifest: ArtifactManifest
    head: HeadMetadata
    db_ref_committed: bool
    fence_meta: SessionMeta
    worker_token: str
    attempt_id: str
    now: int
    upload_timed_out: bool = False
    fence_timed_out: bool = False


def assemble_trusted_artifact(x: AssemblyInputs) -> ArtifactResult:
    """Run the full trusted-Artifact chain. Publication happens ONLY if EVERY stage passes; the FIRST
    failing stage blocks publication (and a HEAD-verified-but-unpersisted or fence-blocked object is
    retained as a private candidate, never GC'd here). Reuses the Day63 final fence."""
    trace: List[str] = []

    r = evaluate_readiness(x.contract, x.observation)
    if r is not Readiness.READY:
        return ArtifactResult(False, "readiness", r.value, trace=trace)
    trace.append("readiness")

    c = correlate_export(x.expected_action, x.observed_network)
    if c is not Correlation.CORRELATED:
        return ArtifactResult(False, "correlation", c.value, trace=trace)
    trace.append("correlation")

    if not assert_safe_network_metadata(x.stored_metadata):
        return ArtifactResult(False, "network_metadata", "UNSAFE_METADATA", trace=trace)
    trace.append("network_metadata")

    sc = classify_schema(x.contract.required_fields, x.observed_fields, x.reviewed_compat)
    if sc is not SchemaOutcome.OK:
        return ArtifactResult(False, "schema", sc.value, trace=trace)
    trace.append("schema")

    d = validate_download(x.download)
    if d is not DownloadOutcome.VALID:
        return ArtifactResult(False, "download", d.value, trace=trace)
    trace.append("download")

    u = classify_upload(x.upload, x.contract.allow_partial_import)
    if u not in (UploadResult.IMPORT_SUCCESS, UploadResult.PARTIAL_SUCCESS):
        return ArtifactResult(False, "upload", u.value, trace=trace)
    trace.append("upload")

    h = verify_head(x.manifest, x.head)
    persist = classify_persist(h, x.db_ref_committed, upload_timed_out=x.upload_timed_out)
    if persist is not PersistDecision.PUBLISH:
        # HEAD-verified but unpersisted (or forward-repair) -> a private candidate is retained.
        retained = persist in (PersistDecision.RETAIN_CANDIDATE, PersistDecision.FORWARD_REPAIR)
        return ArtifactResult(False, "persist", persist.value, candidate_retained=retained, trace=trace)
    trace.append("persist")

    pub = final_publish_decision(persist, x.fence_meta, x.worker_token, x.manifest.session_version,
                                 x.attempt_id, x.now, fence_timed_out=x.fence_timed_out)
    if pub is not PublishDecision.PUBLISH:
        return ArtifactResult(False, "final_fence", pub.value, candidate_retained=True, trace=trace)
    trace.append("final_fence")

    return ArtifactResult(True, "published", "PUBLISH", trace=trace)


# ---------------------------------------------------------------------------
# 9) Rollback classification — a broad-listener release; scope past harm by evidence.
# ---------------------------------------------------------------------------
class AffectedClass(str, Enum):
    CONFIRMED_CORRECT = "CONFIRMED_CORRECT"          # correlation + contract + Artifact re-provable
    MISATTRIBUTED_UNVERIFIED = "MISATTRIBUTED_UNVERIFIED"  # untrusted; stop downstream use; no blind re-extract
    UNPUBLISHED_CANDIDATE = "UNPUBLISHED_CANDIDATE"  # retain privately; forward repair or audited GC
    UNKNOWN = "UNKNOWN"                              # reconcile; do not publish or blindly retry


def classify_affected_item(
    correlation_reprovable: bool,
    contract_ok: bool,
    artifact_verified: bool,
    was_published: bool,
    has_private_candidate: bool,
) -> AffectedClass:
    """``Rollback stops future harm. Evidence scopes past harm. Classification decides repair.`` Uses
    only ACTUALLY-preserved evidence."""
    if correlation_reprovable and contract_ok and artifact_verified:
        return AffectedClass.CONFIRMED_CORRECT
    if was_published:                       # published but cannot be re-proven -> untrusted
        return AffectedClass.MISATTRIBUTED_UNVERIFIED
    if has_private_candidate:
        return AffectedClass.UNPUBLISHED_CANDIDATE
    return AffectedClass.UNKNOWN
