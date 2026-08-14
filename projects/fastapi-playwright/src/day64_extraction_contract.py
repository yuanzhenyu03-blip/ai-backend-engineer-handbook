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
class FieldType(str, Enum):
    """The declared TYPE of a required Extraction-Contract field."""
    INTEGER = "integer"
    NUMBER = "number"                    # int or float (not bool)
    NON_EMPTY_STRING = "non_empty_string"
    STRING = "string"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class FieldSpec:
    """A required field's TYPE and (implicit) value constraint. ``NON_EMPTY_STRING`` also enforces a
    non-empty value; other types enforce their type only. The Contract validates the ACTUAL record
    values — a hand-written ``schema_valid=True`` boolean can never substitute for it."""
    ftype: FieldType


@dataclass(frozen=True)
class TaskContract:
    expected_report_id: str
    terminal_status: str                 # the business-ready status, e.g. "ready"
    required_schema: Mapping[str, FieldSpec]   # field name -> type/value spec (e.g. row_id=INTEGER)
    extraction_contract_version: str
    allow_partial_import: bool = False

    @property
    def required_field_names(self) -> frozenset:
        return frozenset(self.required_schema.keys())


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
        if not contract.required_field_names.issubset(set(rec.keys())):
            return Readiness.SCHEMA_INCOMPLETE   # presence only; deep type/value checks in classify_schema
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
# P2-1: an explicit ALLOW-list of safe, flat evidence fields — not an ever-growing deny-list.
# Only these top-level keys may be stored as Network Evidence metadata; everything else (unknown
# keys, nested header/body maps, Cookies, Authorization, credentials, tokens, raw payloads) is
# rejected by default.
_ALLOWED_METADATA_KEYS = frozenset({
    "action_id", "allowed_origin", "method", "normalized_endpoint", "report_id",
    "client_request_id", "export_id", "response_status", "safe_checksum", "observed_at",
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
    METHOD_MISMATCH = "METHOD_MISMATCH"                    # e.g. a background GET poll
    ENDPOINT_MISMATCH = "ENDPOINT_MISMATCH"
    REPORT_ID_MISMATCH = "REPORT_ID_MISMATCH"
    MISSING_ACTION_ID = "MISSING_ACTION_ID"               # no client_request_id at all -> too broad
    CLIENT_REQUEST_ID_MISMATCH = "CLIENT_REQUEST_ID_MISMATCH"  # present but belongs to another action
    EXPORT_ID_MISMATCH = "EXPORT_ID_MISMATCH"             # follow-up export_id != the saved initial one
    BAD_STATUS = "BAD_STATUS"


def correlate_export(expected: ExportAction, observed: NetworkEvidence) -> Correlation:
    """Correlate the INITIAL Export response to THIS action. It must STRICTLY match the approved
    origin, the expected method, the expected endpoint, the expected report_id, AND
    ``observed.client_request_id == expected.client_request_id``. A non-empty ``export_id`` is NEVER a
    substitute for the request-id match — another Export action's response (its own ``export_id``)
    must be rejected, not published as this Job's result. A background poll (``GET``) fails on method;
    a URL substring plus HTTP 200 is too broad.

    The ``export_id`` returned in THIS verified initial response is what a LATER poll/download/status
    call correlates against — see :func:`extract_export_id` and :func:`correlate_followup`."""
    if observed.allowed_origin != expected.allowed_origin:
        return Correlation.ORIGIN_MISMATCH
    if observed.method != expected.method:                 # POST action vs background GET
        return Correlation.METHOD_MISMATCH
    if observed.normalized_endpoint != expected.normalized_endpoint:
        return Correlation.ENDPOINT_MISMATCH
    if observed.report_id != expected.report_id:
        return Correlation.REPORT_ID_MISMATCH
    if not observed.client_request_id:                     # no request id at all -> too broad
        return Correlation.MISSING_ACTION_ID
    if observed.client_request_id != expected.client_request_id:  # belongs to a DIFFERENT action
        return Correlation.CLIENT_REQUEST_ID_MISMATCH
    if not (200 <= observed.response_status < 300):
        return Correlation.BAD_STATUS
    return Correlation.CORRELATED


def extract_export_id(observed: NetworkEvidence) -> Optional[str]:
    """Return the ``export_id`` minted by the Provider in a VERIFIED initial Export response. Call
    this ONLY after :func:`correlate_export` returned ``CORRELATED`` for that response; the returned
    value is the ONLY export identity a later poll/download/status call may correlate against."""
    return observed.export_id


def correlate_followup(expected_origin: str, saved_export_id: str, observed: NetworkEvidence) -> Correlation:
    """Correlate a SUBSEQUENT poll/download/status response using the ``export_id`` SAVED from the
    verified initial response — never an arbitrary non-empty ``export_id``. Requires the approved
    origin, a matching saved ``export_id``, and a 2xx status."""
    if observed.allowed_origin != expected_origin:
        return Correlation.ORIGIN_MISMATCH
    if not saved_export_id or observed.export_id != saved_export_id:
        return Correlation.EXPORT_ID_MISMATCH
    if not (200 <= observed.response_status < 300):
        return Correlation.BAD_STATUS
    return Correlation.CORRELATED


def assert_safe_network_metadata(metadata: Mapping) -> bool:
    """Store only SAFE, FLAT, redacted evidence: `action_id`, `allowed_origin`, `method`,
    `normalized_endpoint`, `report_id`, `client_request_id`, `export_id`, `response_status`,
    `safe_checksum`, `observed_at`. Returns True ONLY if EVERY key is in the allow-list AND no value
    is a nested mapping/collection (so a `request_headers`/`http_headers` object, a Cookie, an
    Authorization header, a token, or a raw payload is rejected by default, not by enumerating every
    bad name)."""
    for k, v in metadata.items():
        if k not in _ALLOWED_METADATA_KEYS:
            return False
        if isinstance(v, (dict, list, tuple, set)):     # no nested header/body maps
            return False
    return True


# ---------------------------------------------------------------------------
# 4) Extraction Contract versioning — never silently map drifted fields.
# ---------------------------------------------------------------------------
class SchemaOutcome(str, Enum):
    OK = "OK"
    FIELD_MISSING = "FIELD_MISSING"              # a required field is simply absent (no drift candidate)
    TYPE_MISMATCH = "TYPE_MISMATCH"              # present but the wrong type (e.g. score is a string)
    VALUE_INVALID = "VALUE_INVALID"              # right type but violates the value/business constraint
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"      # renamed/removed/drifted field, no reviewed compat rule


def _type_ok(value, ftype: FieldType) -> bool:
    if ftype is FieldType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if ftype is FieldType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if ftype in (FieldType.NON_EMPTY_STRING, FieldType.STRING):
        return isinstance(value, str)
    if ftype is FieldType.BOOLEAN:
        return isinstance(value, bool)
    return False


def _value_ok(value, ftype: FieldType) -> bool:
    if ftype is FieldType.NON_EMPTY_STRING:
        return len(value.strip()) > 0
    return True


def classify_schema(
    required_schema: Mapping[str, FieldSpec],
    records: Sequence[Mapping],
    reviewed_compat: Optional[Mapping[str, str]] = None,
) -> SchemaOutcome:
    """Validate the ACTUAL record values against the Extraction Contract — distinguishing a MISSING
    field, a wrong TYPE, an invalid VALUE, an EXPLICIT reviewed compatibility rename, and unreviewed
    drift.

    For each required field of each record:
      * present directly            -> validate its type and value.
      * satisfied via a REVIEWED compatibility rule (``observed_name -> required_name``) -> validate
        the aliased field's type/value (a reviewed ``relevance_score -> score`` rename is OK).
      * otherwise absent:
          - if the record carries an UNREVIEWED extra field (a rename/drift candidate) ->
            ``CONTRACT_MISMATCH`` (never silently map ``score`` -> ``relevance_score``);
          - else ``FIELD_MISSING``.
    """
    reviewed_compat = reviewed_compat or {}
    required_names = set(required_schema.keys())
    reviewed_observed = set(reviewed_compat.keys())
    for rec in records:
        keys = set(rec.keys())
        unreviewed_extra = keys - required_names - reviewed_observed
        for name, spec in required_schema.items():
            if name in rec:
                src = name
            else:
                alias = next((o for o, r in reviewed_compat.items() if r == name and o in rec), None)
                if alias is None:
                    # a required field is unsatisfied: drift (unreviewed extra present) vs truly missing
                    return SchemaOutcome.CONTRACT_MISMATCH if unreviewed_extra else SchemaOutcome.FIELD_MISSING
                src = alias
            value = rec[src]
            if not _type_ok(value, spec.ftype):
                return SchemaOutcome.TYPE_MISMATCH
            if not _value_ok(value, spec.ftype):
                return SchemaOutcome.VALUE_INVALID
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


# 7) The FINAL fence lives INSIDE the guarded durable write — there is no "DB reference already
#    committed" state before the fence. Lifecycle:
#
#        HEAD verified
#          -> final FULL fence check (active + session-expiry + lease_owner + lease_token +
#             lease_expires_at + version)  [BEFORE any durable reference exists]
#          -> guarded durable DB transaction: Artifact reference + Job publication/Event,
#             committed ONLY if the fence still matches
#          -> commit
#
# Because the fence is evaluated at the guarded-write boundary, a fence failure means NO Artifact
# reference was ever committed and NO Job success was published (there is no "reference committed but
# publication blocked" success path to reconcile). A real PostgreSQL transaction is NOT RUN here; the
# pure model represents whether the guarded publish transaction WOULD commit or was rejected.
class PublishDecision(str, Enum):
    PUBLISH = "PUBLISH"                                  # fence held AND the guarded durable txn committed
    RETAIN_UNPUBLISHED_FENCE = "RETAIN_UNPUBLISHED_FENCE"    # fence failed/timeout/revoked -> nothing committed
    RETAIN_CANDIDATE_TXN_FAILED = "RETAIN_CANDIDATE_TXN_FAILED"  # fence held but the guarded txn did not commit
    FORWARD_REPAIR = "FORWARD_REPAIR"                    # upload-timeout + matching HEAD -> reuse verified object
    NOT_VERIFIED = "NOT_VERIFIED"                        # HEAD absent/mismatch -> no publish


def decide_guarded_publish(
    head: HeadOutcome,
    fence_meta: SessionMeta,
    worker_token: str,
    claimed_version: int,
    attempt_id: str,
    now: int,
    *,
    guarded_txn_commits: bool,
    upload_timed_out: bool = False,
    fence_timed_out: bool = False,
) -> PublishDecision:
    """Decide publication AT the guarded durable-write boundary (P1-2).

    * HEAD not verified                    -> NOT_VERIFIED (no object to reference).
    * final FULL fence fails/timeout/revoked/lease-or-version mismatch -> RETAIN_UNPUBLISHED_FENCE:
      NO Artifact reference is written, NO Job success is published, the candidate is retained
      PRIVATELY for audit/reconciliation, and it is NOT immediately GC'd.
    * fence holds:
        - upload timed out with a matching HEAD (object already exists) -> FORWARD_REPAIR (reuse the
          verified object; never blind re-upload/overwrite/delete);
        - the guarded durable transaction does NOT commit -> RETAIN_CANDIDATE_TXN_FAILED (private
          candidate; reconcile; no publish);
        - the guarded durable transaction commits -> PUBLISH (Artifact reference + Job publication
          committed atomically UNDER the fence).
    """
    if head is not HeadOutcome.VERIFIED:
        return PublishDecision.NOT_VERIFIED
    fence = final_fence(fence_meta, worker_token, claimed_version, attempt_id, now,
                        timed_out=fence_timed_out)
    if fence is not Outcome.AUTHORIZED:
        return PublishDecision.RETAIN_UNPUBLISHED_FENCE   # nothing durable was committed
    if upload_timed_out and not guarded_txn_commits:
        return PublishDecision.FORWARD_REPAIR
    if not guarded_txn_commits:
        return PublishDecision.RETAIN_CANDIDATE_TXN_FAILED
    return PublishDecision.PUBLISH


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
    reviewed_compat: Optional[Mapping[str, str]]
    download: DownloadCandidate
    upload: UploadOutcomeFacts
    manifest: ArtifactManifest
    head: HeadMetadata
    guarded_txn_commits: bool            # would the guarded durable Artifact-reference+publish tx commit?
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

    sc = classify_schema(x.contract.required_schema, x.observation.records, x.reviewed_compat)
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

    trace.append("head")
    # HEAD -> final FULL fence -> guarded durable transaction (Artifact reference + Job publication),
    # in ONE decision. The fence is at the durable-write boundary: a fence failure commits nothing.
    pub = decide_guarded_publish(
        verify_head(x.manifest, x.head), x.fence_meta, x.worker_token, x.manifest.session_version,
        x.attempt_id, x.now, guarded_txn_commits=x.guarded_txn_commits,
        upload_timed_out=x.upload_timed_out, fence_timed_out=x.fence_timed_out,
    )
    if pub is not PublishDecision.PUBLISH:
        # NOT_VERIFIED-absent has no object; every other non-publish keeps a private candidate.
        absent = pub is PublishDecision.NOT_VERIFIED and x.head.exists is False
        return ArtifactResult(False, "guarded_publish", pub.value,
                              candidate_retained=not absent, trace=trace)
    trace.append("guarded_publish")

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
