"""Day64 — EXECUTED_LOCAL_RUNTIME tests for the pure Extraction / Artifact decision core.

Standard-library only; no browser, no Object Storage, no PostgreSQL. Proves the RULES and the
required FAILURE PATHS: a `generating` status blocks publication; a background GET poll cannot match
the required POST + client_request_id; a schema/contract mismatch blocks publication; an invalid
file/schema/checksum blocks the Artifact; a HEAD-verified object with a failed DB reference is
RETAINED (not deleted); a final-fence failure blocks publication; and the broad-listener release has
a safe rollback classification. NOT integration evidence.
"""

from day63_session_gate import SessionMeta
from day64_extraction_contract import (
    AffectedClass,
    ArtifactManifest,
    AssemblyInputs,
    Correlation,
    DownloadCandidate,
    DownloadOutcome,
    ExportAction,
    HeadMetadata,
    HeadOutcome,
    NetworkEvidence,
    PersistDecision,
    PublishDecision,
    Readiness,
    ReportObservation,
    SchemaOutcome,
    SourceRole,
    TaskContract,
    UploadOutcomeFacts,
    UploadResult,
    assemble_trusted_artifact,
    assert_safe_network_metadata,
    choose_primary_source,
    classify_affected_item,
    classify_persist,
    classify_schema,
    classify_upload,
    correlate_export,
    evaluate_readiness,
    final_publish_decision,
    validate_download,
    verify_head,
)

NOW = 1_000
REQUIRED = frozenset({"row_id", "score", "label"})
ORIGIN = "https://research.example.test"


def _contract(allow_partial=False):
    return TaskContract("42", "ready", REQUIRED, "v1", allow_partial_import=allow_partial)


def _ready_records():
    return [{"row_id": 1, "score": 0.5, "label": "a"}, {"row_id": 2, "score": 0.6, "label": "b"}]


def _ok_inputs(**over):
    contract = over.get("contract", _contract())
    version = 3
    manifest = over.get("manifest", ArtifactManifest(
        "tenantA", "job1", "att-1", "sess-A1", version, "results/tenantA/job1/att-1/export.csv",
        "text/csv", 1234, "sha256:abc"))
    d = dict(
        contract=contract,
        observation=ReportObservation("42", "ready", _ready_records()),
        expected_action=ExportAction(ORIGIN, "POST", "/api/exports", "42", "crq-1"),
        observed_network=NetworkEvidence(ORIGIN, "POST", "/api/exports", "42", "crq-1", "exp-1", 200,
                                         "sha256:pay", NOW),
        stored_metadata={"normalized_endpoint": "/api/exports", "method": "POST",
                         "client_request_id": "crq-1", "status": 200, "checksum": "sha256:pay"},
        observed_fields=frozenset(REQUIRED),
        reviewed_compat=None,
        download=DownloadCandidate("act-1", True, 1234, "text/csv", "text/csv", "sha256:abc",
                                   True, True, True),
        upload=UploadOutcomeFacts("imp-1", "imported", 500, 0),
        manifest=manifest,
        head=HeadMetadata(True, 1234, "sha256:abc", "text/csv"),
        db_ref_committed=True,
        fence_meta=SessionMeta("active", NOW + 100, version, "att-1", "wtok-1", NOW + 50),
        worker_token="wtok-1",
        attempt_id="att-1",
        now=NOW,
    )
    d.update(over)
    return AssemblyInputs(**d)


# ---- happy path --------------------------------------------------------------------------
def test_full_chain_publishes_when_everything_passes():
    r = assemble_trusted_artifact(_ok_inputs())
    assert r.published is True and r.stage == "published"
    assert r.trace == ["readiness", "correlation", "network_metadata", "schema",
                       "download", "upload", "persist", "final_fence"]


def test_primary_source_role():
    assert choose_primary_source(False) is SourceRole.NETWORK_PRIMARY
    assert choose_primary_source(True) is SourceRole.DOM_PRIMARY


# ---- REQUIRED failure paths --------------------------------------------------------------
def test_generating_status_blocks_publication():
    obs = ReportObservation("42", "generating", [])
    assert evaluate_readiness(_contract(), obs) is Readiness.NOT_READY_STATUS
    r = assemble_trusted_artifact(_ok_inputs(observation=obs))
    assert r.published is False and r.stage == "readiness" and r.reason == "NOT_READY_STATUS"


def test_background_get_poll_cannot_match_required_post_action():
    poll = NetworkEvidence(ORIGIN, "GET", "/api/exports", "42", None, None, 200, "sha256:x", NOW)
    assert correlate_export(ExportAction(ORIGIN, "POST", "/api/exports", "42", "crq-1"), poll) is Correlation.METHOD_MISMATCH
    # even a POST without the client_request_id/export_id is too broad
    broad = NetworkEvidence(ORIGIN, "POST", "/api/exports", "42", None, None, 200, "sha256:x", NOW)
    assert correlate_export(ExportAction(ORIGIN, "POST", "/api/exports", "42", "crq-1"), broad) is Correlation.MISSING_ACTION_ID
    r = assemble_trusted_artifact(_ok_inputs(observed_network=poll))
    assert r.published is False and r.stage == "correlation" and r.reason == "METHOD_MISMATCH"


def test_schema_rename_without_reviewed_rule_is_contract_mismatch():
    drifted = frozenset({"row_id", "relevance_score", "label"})   # score -> relevance_score
    assert classify_schema(REQUIRED, drifted) is SchemaOutcome.CONTRACT_MISMATCH
    # an explicit, reviewed compatibility rule proves semantic equivalence
    assert classify_schema(REQUIRED, drifted, {"relevance_score": "score"}) is SchemaOutcome.OK
    r = assemble_trusted_artifact(_ok_inputs(observed_fields=drifted))
    assert r.published is False and r.stage == "schema" and r.reason == "CONTRACT_MISMATCH"


def test_invalid_download_blocks_artifact_publication():
    # filename ext lied (actual type differs) / bad checksum / bad schema each block publication
    assert validate_download(DownloadCandidate("a", True, 10, "text/csv", "text/html", "s", True, True, True)) is DownloadOutcome.CONTENT_TYPE_MISMATCH
    assert validate_download(DownloadCandidate("a", True, 10, "text/csv", "text/csv", None, True, True, True)) is DownloadOutcome.CHECKSUM_MISSING
    assert validate_download(DownloadCandidate("a", True, 10, "text/csv", "text/csv", "s", True, False, True)) is DownloadOutcome.SCHEMA_INVALID
    assert validate_download(DownloadCandidate(None, True, 10, "text/csv", "text/csv", "s", True, True, True)) is DownloadOutcome.NO_PROVENANCE
    assert validate_download(DownloadCandidate("a", False, 10, "text/csv", "text/csv", "s", True, True, True)) is DownloadOutcome.INCOMPLETE_TRANSFER
    assert validate_download(DownloadCandidate("a", True, 0, "text/csv", "text/csv", "s", True, True, True)) is DownloadOutcome.BAD_SIZE
    bad = DownloadCandidate("act-1", True, 1234, "text/csv", "application/octet-stream", "sha256:abc", True, True, True)
    r = assemble_trusted_artifact(_ok_inputs(download=bad))
    assert r.published is False and r.stage == "download" and r.reason == "CONTENT_TYPE_MISMATCH"


def test_object_candidate_with_failed_db_reference_is_retained_not_deleted():
    assert classify_persist(HeadOutcome.VERIFIED, db_ref_committed=False) is PersistDecision.RETAIN_CANDIDATE
    r = assemble_trusted_artifact(_ok_inputs(db_ref_committed=False))
    assert r.published is False and r.stage == "persist" and r.reason == "RETAIN_CANDIDATE"
    assert r.candidate_retained is True                 # kept for reconcile, NOT deleted


def test_upload_timeout_then_matching_head_is_forward_repair():
    assert classify_persist(HeadOutcome.VERIFIED, db_ref_committed=False, upload_timed_out=True) is PersistDecision.FORWARD_REPAIR
    r = assemble_trusted_artifact(_ok_inputs(db_ref_committed=False, upload_timed_out=True))
    assert r.published is False and r.reason == "FORWARD_REPAIR" and r.candidate_retained is True


def test_final_fence_failure_blocks_publication_retains_candidate():
    # a timed-out final fence -> retain unpublished, do not GC
    assert final_publish_decision(PersistDecision.PUBLISH, SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW + 50),
                                  "wtok-1", 3, "att-1", NOW, fence_timed_out=True) is PublishDecision.RETAIN_UNPUBLISHED
    r = assemble_trusted_artifact(_ok_inputs(fence_timed_out=True))
    assert r.published is False and r.stage == "final_fence" and r.candidate_retained is True
    # a revoked session at the fence also blocks
    revoked = SessionMeta("revoked", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)
    r2 = assemble_trusted_artifact(_ok_inputs(fence_meta=revoked))
    assert r2.published is False and r2.stage == "final_fence"


def test_broad_listener_release_rollback_classification():
    assert classify_affected_item(True, True, True, True, True) is AffectedClass.CONFIRMED_CORRECT
    assert classify_affected_item(False, True, False, True, False) is AffectedClass.MISATTRIBUTED_UNVERIFIED
    assert classify_affected_item(False, False, False, False, True) is AffectedClass.UNPUBLISHED_CANDIDATE
    assert classify_affected_item(False, False, False, False, False) is AffectedClass.UNKNOWN


# ---- counts + metadata safety + HEAD -----------------------------------------------------
def test_upload_counts_and_partial_semantics():
    assert classify_upload(UploadOutcomeFacts(None, None, 0, 0), allow_partial=False) is UploadResult.NOT_TERMINAL  # 202 Accepted
    assert classify_upload(UploadOutcomeFacts("imp", "imported", 500, 0), allow_partial=False) is UploadResult.IMPORT_SUCCESS
    assert classify_upload(UploadOutcomeFacts("imp", "imported", 498, 2), allow_partial=False) is UploadResult.PARTIAL_NOT_ALLOWED
    assert classify_upload(UploadOutcomeFacts("imp", "imported", 498, 2), allow_partial=True) is UploadResult.PARTIAL_SUCCESS
    assert classify_upload(UploadOutcomeFacts("imp", "failed", 0, 500), allow_partial=True) is UploadResult.IMPORT_FAILED
    # 202-accepted (not terminal) blocks publication end-to-end
    r = assemble_trusted_artifact(_ok_inputs(upload=UploadOutcomeFacts(None, None, 0, 0)))
    assert r.published is False and r.stage == "upload" and r.reason == "NOT_TERMINAL"


def test_safe_network_metadata_rejects_secrets():
    assert assert_safe_network_metadata({"method": "POST", "endpoint": "/api/exports"}) is True
    assert assert_safe_network_metadata({"cookie": "sid=..."}) is False
    assert assert_safe_network_metadata({"Authorization": "Bearer x"}) is False
    assert assert_safe_network_metadata({"raw_payload": "..."}) is False
    r = assemble_trusted_artifact(_ok_inputs(stored_metadata={"authorization": "Bearer x"}))
    assert r.published is False and r.stage == "network_metadata"


def test_head_absent_or_mismatch_is_not_verified():
    m = ArtifactManifest("t", "j", "a", "s", 1, "k", "text/csv", 10, "sha256:x")
    assert verify_head(m, HeadMetadata(False, None, None, None)) is HeadOutcome.ABSENT
    assert verify_head(m, HeadMetadata(True, 11, "sha256:x", "text/csv")) is HeadOutcome.MISMATCH
    assert verify_head(m, HeadMetadata(True, 10, "sha256:x", "text/csv")) is HeadOutcome.VERIFIED
    r = assemble_trusted_artifact(_ok_inputs(head=HeadMetadata(True, 9999, "sha256:abc", "text/csv")))
    assert r.published is False and r.stage == "persist" and r.reason == "NOT_VERIFIED"


def test_readiness_report_id_and_schema():
    assert evaluate_readiness(_contract(), ReportObservation("99", "ready", _ready_records())) is Readiness.REPORT_ID_MISMATCH
    assert evaluate_readiness(_contract(), ReportObservation("42", "ready", [{"row_id": 1}])) is Readiness.SCHEMA_INCOMPLETE
