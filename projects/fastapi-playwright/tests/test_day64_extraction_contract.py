"""Day64 — EXECUTED_LOCAL_RUNTIME tests for the pure Extraction / Artifact decision core.

Standard-library only; no browser, no Object Storage, no PostgreSQL. Proves the RULES and the
required FAILURE PATHS, including the review fixes:
  * export_id can NEVER bypass the current action's client_request_id (P1-1);
  * the FINAL fence sits at the guarded durable-write boundary — a fence failure commits nothing,
    so there is no "reference committed but publication blocked" success path (P1-2);
  * the Extraction Contract validates field TYPES and VALUE constraints, not just names (P1-3);
  * network metadata uses an ALLOW-list (unknown/nested/secret keys rejected) (P2-1).
NOT integration evidence.
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
    FieldSpec,
    FieldType,
    HeadMetadata,
    HeadOutcome,
    NetworkEvidence,
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
    classify_schema,
    classify_upload,
    correlate_export,
    correlate_followup,
    decide_guarded_publish,
    evaluate_readiness,
    extract_export_id,
    validate_download,
    verify_head,
)

NOW = 1_000
ORIGIN = "https://research.example.test"
SCHEMA = {"row_id": FieldSpec(FieldType.INTEGER),
          "score": FieldSpec(FieldType.NUMBER),
          "label": FieldSpec(FieldType.NON_EMPTY_STRING)}


def _contract(allow_partial=False):
    return TaskContract("42", "ready", SCHEMA, "v1", allow_partial_import=allow_partial)


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
                         "client_request_id": "crq-1", "response_status": 200,
                         "safe_checksum": "sha256:pay", "observed_at": NOW},
        reviewed_compat=None,
        download=DownloadCandidate("act-1", True, 1234, "text/csv", "text/csv", "sha256:abc",
                                   True, [{"row_id": 1, "score": 0.5, "label": "a"}]),
        upload=UploadOutcomeFacts("imp-1", "imported", 500, 0),
        manifest=manifest,
        head=HeadMetadata(True, 1234, "sha256:abc", "text/csv"),
        guarded_txn_commits=True,
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
                       "download", "upload", "head", "guarded_publish"]


def test_primary_source_role():
    assert choose_primary_source(False) is SourceRole.NETWORK_PRIMARY
    assert choose_primary_source(True) is SourceRole.DOM_PRIMARY


# ---- P1-1: export_id cannot bypass client_request_id ------------------------------------
def test_export_id_cannot_bypass_client_request_id():
    expected = ExportAction(ORIGIN, "POST", "/api/exports", "42", "crq-1")
    # another action's response: wrong client_request_id but a non-empty export_id -> MUST reject
    other = NetworkEvidence(ORIGIN, "POST", "/api/exports", "42", "crq-other", "exp-other", 200, "s", NOW)
    assert correlate_export(expected, other) is Correlation.CLIENT_REQUEST_ID_MISMATCH
    r = assemble_trusted_artifact(_ok_inputs(observed_network=other))
    assert r.published is False and r.stage == "correlation" and r.reason == "CLIENT_REQUEST_ID_MISMATCH"


def test_background_get_poll_cannot_match_required_post_action():
    expected = ExportAction(ORIGIN, "POST", "/api/exports", "42", "crq-1")
    poll = NetworkEvidence(ORIGIN, "GET", "/api/exports", "42", None, None, 200, "s", NOW)
    assert correlate_export(expected, poll) is Correlation.METHOD_MISMATCH
    # a POST with no client_request_id at all is too broad
    broad = NetworkEvidence(ORIGIN, "POST", "/api/exports", "42", None, None, 200, "s", NOW)
    assert correlate_export(expected, broad) is Correlation.MISSING_ACTION_ID


def test_followup_correlation_uses_saved_export_id_only():
    initial = NetworkEvidence(ORIGIN, "POST", "/api/exports", "42", "crq-1", "exp-1", 200, "s", NOW)
    assert correlate_export(ExportAction(ORIGIN, "POST", "/api/exports", "42", "crq-1"), initial) is Correlation.CORRELATED
    saved = extract_export_id(initial)
    assert saved == "exp-1"
    good = NetworkEvidence(ORIGIN, "GET", "/api/exports/exp-1", "42", None, "exp-1", 200, "s", NOW + 1)
    assert correlate_followup(ORIGIN, saved, good) is Correlation.CORRELATED
    # a different action's export_id must NOT correlate as our follow-up
    other = NetworkEvidence(ORIGIN, "GET", "/api/exports/exp-9", "42", None, "exp-9", 200, "s", NOW + 1)
    assert correlate_followup(ORIGIN, saved, other) is Correlation.EXPORT_ID_MISMATCH


# ---- P1-2: final fence at the guarded durable-write boundary ----------------------------
def test_fence_failure_commits_nothing_no_reference_committed_path():
    # a timed-out fence -> RETAIN_UNPUBLISHED_FENCE regardless of whether the guarded txn 'would' commit
    d = decide_guarded_publish(HeadOutcome.VERIFIED, SessionMeta("active", NOW + 100, 3, "att-1", "wtok-1", NOW + 50),
                               "wtok-1", 3, "att-1", NOW, guarded_txn_commits=True, fence_timed_out=True)
    assert d is PublishDecision.RETAIN_UNPUBLISHED_FENCE
    r = assemble_trusted_artifact(_ok_inputs(fence_timed_out=True, guarded_txn_commits=True))
    assert r.published is False and r.stage == "guarded_publish"
    assert r.reason == "RETAIN_UNPUBLISHED_FENCE" and r.candidate_retained is True
    # a revoked session at the fence also commits nothing
    revoked = SessionMeta("revoked", NOW + 100, 3, "att-1", "wtok-1", NOW + 50)
    r2 = assemble_trusted_artifact(_ok_inputs(fence_meta=revoked))
    assert r2.published is False and r2.reason == "RETAIN_UNPUBLISHED_FENCE"
    # a superseded lease (different owner) at the fence commits nothing
    superseded = SessionMeta("active", NOW + 100, 4, "att-2", "wtok-2", NOW + 50)
    r3 = assemble_trusted_artifact(_ok_inputs(fence_meta=superseded))
    assert r3.published is False and r3.reason == "RETAIN_UNPUBLISHED_FENCE"


def test_guarded_txn_failure_after_fence_retains_candidate():
    r = assemble_trusted_artifact(_ok_inputs(guarded_txn_commits=False))
    assert r.published is False and r.stage == "guarded_publish"
    assert r.reason == "RETAIN_CANDIDATE_TXN_FAILED" and r.candidate_retained is True


def test_upload_timeout_then_matching_head_is_forward_repair():
    r = assemble_trusted_artifact(_ok_inputs(guarded_txn_commits=False, upload_timed_out=True))
    assert r.published is False and r.reason == "FORWARD_REPAIR" and r.candidate_retained is True


def test_head_absent_or_mismatch_is_not_verified():
    m = ArtifactManifest("t", "j", "a", "s", 1, "k", "text/csv", 10, "sha256:x")
    assert verify_head(m, HeadMetadata(False, None, None, None)) is HeadOutcome.ABSENT
    assert verify_head(m, HeadMetadata(True, 11, "sha256:x", "text/csv")) is HeadOutcome.MISMATCH
    assert verify_head(m, HeadMetadata(True, 10, "sha256:x", "text/csv")) is HeadOutcome.VERIFIED
    # absent object -> no candidate retained; mismatch (object exists, wrong) -> candidate retained
    r_absent = assemble_trusted_artifact(_ok_inputs(head=HeadMetadata(False, None, None, None)))
    assert r_absent.reason == "NOT_VERIFIED" and r_absent.candidate_retained is False
    r_mismatch = assemble_trusted_artifact(_ok_inputs(head=HeadMetadata(True, 9999, "sha256:abc", "text/csv")))
    assert r_mismatch.reason == "NOT_VERIFIED" and r_mismatch.candidate_retained is True


# ---- P1-3: type/value Extraction Contract -----------------------------------------------
def test_score_wrong_type_blocks_publication():
    bad = [{"row_id": 1, "score": "not-a-number", "label": "Acme"}]   # score is a string
    assert classify_schema(SCHEMA, bad) is SchemaOutcome.TYPE_MISMATCH
    r = assemble_trusted_artifact(_ok_inputs(observation=ReportObservation("42", "ready", bad)))
    assert r.published is False and r.stage == "schema" and r.reason == "TYPE_MISMATCH"


def test_schema_missing_vs_type_vs_value_vs_reviewed():
    # truly missing field (no drift candidate) -> FIELD_MISSING
    assert classify_schema(SCHEMA, [{"row_id": 1, "score": 0.5}]) is SchemaOutcome.FIELD_MISSING
    # empty label -> right type, invalid value
    assert classify_schema(SCHEMA, [{"row_id": 1, "score": 0.5, "label": "   "}]) is SchemaOutcome.VALUE_INVALID
    # bool is not an integer/number
    assert classify_schema(SCHEMA, [{"row_id": True, "score": 0.5, "label": "a"}]) is SchemaOutcome.TYPE_MISMATCH
    # rename score -> relevance_score WITHOUT a reviewed rule -> CONTRACT_MISMATCH
    drifted = [{"row_id": 1, "relevance_score": 0.5, "label": "a"}]
    assert classify_schema(SCHEMA, drifted) is SchemaOutcome.CONTRACT_MISMATCH
    # WITH a reviewed compatibility rule, the alias is validated by type -> OK
    assert classify_schema(SCHEMA, drifted, {"relevance_score": "score"}) is SchemaOutcome.OK
    # reviewed alias but wrong type -> TYPE_MISMATCH
    assert classify_schema(SCHEMA, [{"row_id": 1, "relevance_score": "x", "label": "a"}],
                           {"relevance_score": "score"}) is SchemaOutcome.TYPE_MISMATCH


# ---- P2-1: metadata allow-list ----------------------------------------------------------
def test_network_metadata_allowlist():
    ok = {"action_id": "a", "allowed_origin": ORIGIN, "method": "POST", "normalized_endpoint": "/api/exports",
          "report_id": "42", "client_request_id": "crq-1", "export_id": "exp-1", "response_status": 200,
          "safe_checksum": "sha256:x", "observed_at": NOW}
    assert assert_safe_network_metadata(ok) is True
    assert assert_safe_network_metadata({"session_token": "x"}) is False        # unknown key
    assert assert_safe_network_metadata({"request_headers": "..."}) is False    # unknown key
    assert assert_safe_network_metadata({"http_headers": "..."}) is False
    assert assert_safe_network_metadata({"custom_auth": "..."}) is False
    assert assert_safe_network_metadata({"cookie": "sid=..."}) is False
    # a nested header/body map under an allowed key is still rejected
    assert assert_safe_network_metadata({"method": {"nested": "headers"}}) is False
    assert assert_safe_network_metadata({"observed_at": ["x"]}) is False
    r = assemble_trusted_artifact(_ok_inputs(stored_metadata={"request_headers": {"Authorization": "Bearer x"}}))
    assert r.published is False and r.stage == "network_metadata"


# ---- readiness + counts + rollback ------------------------------------------------------
def test_readiness_generating_report_id_schema():
    assert evaluate_readiness(_contract(), ReportObservation("42", "generating", [])) is Readiness.NOT_READY_STATUS
    assert evaluate_readiness(_contract(), ReportObservation("99", "ready", _ready_records())) is Readiness.REPORT_ID_MISMATCH
    assert evaluate_readiness(_contract(), ReportObservation("42", "ready", [{"row_id": 1}])) is Readiness.SCHEMA_INCOMPLETE
    r = assemble_trusted_artifact(_ok_inputs(observation=ReportObservation("42", "generating", [])))
    assert r.published is False and r.stage == "readiness" and r.reason == "NOT_READY_STATUS"


def _dl(parsed, **over):
    d = dict(provenance_action_id="act-1", transfer_complete=True, byte_size=1234,
             declared_content_type="text/csv", actual_content_type="text/csv", sha256="sha256:abc",
             parsed_ok=True, parsed_records=parsed)
    d.update(over)
    return DownloadCandidate(**d)


_GOOD_ROWS = [{"row_id": 1, "score": 0.5, "label": "a"}, {"row_id": 2, "score": 0.6, "label": "b"}]


def test_download_container_level_failures_are_distinct():
    ct = _contract()
    assert validate_download(_dl(_GOOD_ROWS), ct) is DownloadOutcome.VALID
    assert validate_download(_dl(_GOOD_ROWS, provenance_action_id=None), ct) is DownloadOutcome.NO_PROVENANCE
    assert validate_download(_dl(_GOOD_ROWS, transfer_complete=False), ct) is DownloadOutcome.INCOMPLETE_TRANSFER
    assert validate_download(_dl(_GOOD_ROWS, byte_size=0), ct) is DownloadOutcome.BAD_SIZE
    assert validate_download(_dl(_GOOD_ROWS, actual_content_type="text/html"), ct) is DownloadOutcome.CONTENT_TYPE_MISMATCH
    assert validate_download(_dl(_GOOD_ROWS, sha256=None), ct) is DownloadOutcome.CHECKSUM_MISSING
    assert validate_download(_dl(_GOOD_ROWS, parsed_ok=False), ct) is DownloadOutcome.PARSE_FAILED


def test_download_content_type_mismatch_blocks_end_to_end():
    r = assemble_trusted_artifact(_ok_inputs(download=_dl(_GOOD_ROWS, actual_content_type="application/octet-stream")))
    assert r.published is False and r.stage == "download" and r.reason == "CONTENT_TYPE_MISMATCH"


def test_download_score_wrong_type_blocks_publication_end_to_end():
    # network JSON is fine; the DOWNLOADED CSV's actual row has a non-numeric score -> block at download.
    bad_rows = [{"row_id": 1, "score": "not-a-number", "label": "Acme"}]
    assert validate_download(_dl(bad_rows), _contract()) is DownloadOutcome.SCHEMA_TYPE_MISMATCH
    r = assemble_trusted_artifact(_ok_inputs(download=_dl(bad_rows)))
    assert r.published is False and r.stage == "download" and r.reason == "SCHEMA_TYPE_MISMATCH"


def test_download_missing_field_blocks_publication_end_to_end():
    r = assemble_trusted_artifact(_ok_inputs(download=_dl([{"row_id": 1, "score": 0.5}])))
    assert r.published is False and r.stage == "download" and r.reason == "SCHEMA_FIELD_MISSING"


def test_download_empty_label_value_blocks_publication_end_to_end():
    r = assemble_trusted_artifact(_ok_inputs(download=_dl([{"row_id": 1, "score": 0.5, "label": "   "}])))
    assert r.published is False and r.stage == "download" and r.reason == "SCHEMA_VALUE_INVALID"


def test_download_conforming_records_publishes():
    r = assemble_trusted_artifact(_ok_inputs(download=_dl(_GOOD_ROWS)))
    assert r.published is True and r.stage == "published"


def test_download_unreviewed_rename_blocks_reviewed_rename_passes():
    drifted = [{"row_id": 1, "relevance_score": 0.5, "label": "a"}]
    # unreviewed rename in the DOWNLOAD content -> block at download
    r = assemble_trusted_artifact(_ok_inputs(download=_dl(drifted)))
    assert r.published is False and r.stage == "download" and r.reason == "SCHEMA_CONTRACT_MISMATCH"
    # with an explicit reviewed compatibility rule, the aliased download field is accepted
    r2 = assemble_trusted_artifact(_ok_inputs(download=_dl(drifted), reviewed_compat={"relevance_score": "score"}))
    assert r2.published is True


def test_download_business_record_count_constraint():
    # empty parsed content fails the default min_download_records=1 business constraint
    assert validate_download(_dl([]), _contract()) is DownloadOutcome.BUSINESS_INVALID
    # an explicit expected count that the download does not meet -> BUSINESS_INVALID at download
    ct = TaskContract("42", "ready", SCHEMA, "v1", expected_download_record_count=2)
    assert validate_download(_dl([{"row_id": 1, "score": 0.5, "label": "a"}]), ct) is DownloadOutcome.BUSINESS_INVALID
    r = assemble_trusted_artifact(_ok_inputs(contract=ct, download=_dl([{"row_id": 1, "score": 0.5, "label": "a"}])))
    assert r.published is False and r.stage == "download" and r.reason == "BUSINESS_INVALID"


def test_upload_counts_and_partial_semantics():
    assert classify_upload(UploadOutcomeFacts(None, None, 0, 0), allow_partial=False) is UploadResult.NOT_TERMINAL
    assert classify_upload(UploadOutcomeFacts("imp", "imported", 500, 0), allow_partial=False) is UploadResult.IMPORT_SUCCESS
    assert classify_upload(UploadOutcomeFacts("imp", "imported", 498, 2), allow_partial=False) is UploadResult.PARTIAL_NOT_ALLOWED
    assert classify_upload(UploadOutcomeFacts("imp", "imported", 498, 2), allow_partial=True) is UploadResult.PARTIAL_SUCCESS
    assert classify_upload(UploadOutcomeFacts("imp", "failed", 0, 500), allow_partial=True) is UploadResult.IMPORT_FAILED
    r = assemble_trusted_artifact(_ok_inputs(upload=UploadOutcomeFacts(None, None, 0, 0)))
    assert r.published is False and r.stage == "upload" and r.reason == "NOT_TERMINAL"


def test_broad_listener_release_rollback_classification():
    assert classify_affected_item(True, True, True, True, True) is AffectedClass.CONFIRMED_CORRECT
    assert classify_affected_item(False, True, False, True, False) is AffectedClass.MISATTRIBUTED_UNVERIFIED
    assert classify_affected_item(False, False, False, False, True) is AffectedClass.UNPUBLISHED_CANDIDATE
    assert classify_affected_item(False, False, False, False, False) is AffectedClass.UNKNOWN
