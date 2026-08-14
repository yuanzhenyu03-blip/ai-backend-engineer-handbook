# Day64 — Dynamic Extraction, Network Events and Artifact Evidence (design / runbook)

Connected, runnable Day64 artifact inside the EXISTING `projects/fastapi-playwright/` project (no
parallel project). It turns an authorized, isolated Day63 browser session into STRUCTURED,
CORRELATED, VALIDATED, DURABLE Artifact evidence — proving the decision RULES with pure logic plus a
controlled loopback report page. It does NOT implement Day65 recovery/security or Day66 queue
integration.

## Files

- `src/day64_extraction_contract.py` — pure decision core (standard library only): task-contract
  readiness, DOM/network source roles, STRICT network correlation (approved origin + method +
  endpoint + report_id + client_request_id/export_id; safe/redacted metadata only), Extraction
  Contract schema-drift classification, download validation + precise counts, upload terminal-import
  classification, Object Storage HEAD verification, persist / candidate-retention decisions, the
  final-fence-still-controls-publish rule (REUSES `day63_session_gate.final_fence`), the
  `assemble_trusted_artifact` orchestrator (publishes ONLY if the whole chain passes; the first
  failing stage blocks publication), and the broad-listener rollback classification.
- `src/day64_controlled_report_page.py` — a genuinely DYNAMIC, synthetic localhost SPA + JSON API. Its
  page-owned JavaScript fetches `/api/reports/{id}` (`generating` before `ready`), renders the state +
  a LIMITED rounded/virtualized DOM (first 20 rows at 2-decimal precision vs 500 full-precision JSON
  rows), and triggers a real Export `POST /api/exports` (echoes the strict action identity). It is
  intended to serve a FUTURE real-Playwright local test (NOT RUN this round); the HTTP-loopback test
  drives only the JSON API (no JavaScript executes under urllib). No sensitive data.
- `tests/test_day64_extraction_contract.py` — pure-logic + all required FAILURE-PATH tests
  (EXECUTED_LOCAL_RUNTIME).
- `tests/test_day64_report_page_http.py` — REAL HTTP-loopback tests of the report/export contract
  (EXECUTED_LOCAL_RUNTIME).

The import path is provided by the existing `pytest.ini` (`pythonpath = src`); no `sys.path` hacks.

## Core mental model

```text
page lifecycle signal != extraction readiness != valid Artifact != published business success

Trusted Artifact publication
= authorized Session
AND fresh isolated Context
AND task-contract business-ready fact
AND correctly correlated network/DOM/download evidence
AND schema/content validation
AND Object Storage HEAD verification
AND durable Artifact reference
AND the final Day63 authorization fence
```

## Rules enforced

- `page load` / HTTP 200 are observations, not success; a report is ready only when its expected
  identity, terminal business status, and required schema meet the task contract
  (`{status:"generating"}` blocks publication despite HTTP 200).
- Network JSON is the primary structured-data candidate; the DOM (rounded / virtualized) corroborates.
  Sources are never merged without a stated role.
- Register the download/response waiter BEFORE the Export click — this prevents a missed-observation
  race only; it does not make a repeated click / re-download / retry idempotent or safe.
- Correlation needs an explicit action identity (`POST /api/exports {report_id, client_request_id}`);
  the INITIAL response must strictly match origin+method+endpoint+report_id AND
  `client_request_id == expected` (a non-empty `export_id` is NEVER a substitute — another action's
  response is rejected). The `export_id` from the verified initial response is what a later
  poll/download/status call correlates against. Network metadata uses an explicit ALLOW-list of flat
  fields (`action_id`, `allowed_origin`, `method`, `normalized_endpoint`, `report_id`,
  `client_request_id`, `export_id`, `response_status`, `safe_checksum`, `observed_at`); unknown keys,
  nested header/body maps, Cookies, Authorization, credentials, tokens and raw payloads are rejected.
- Downloads need provenance, a completed transfer, a bounded nonzero size, the ACTUAL content type
  (not the filename extension), a SHA-256, parsing, schema, and business constraints. Counts are
  precise: `artifact_record_count` (validated rows), `source_record_count` (source/API rows),
  `accepted_count`/`rejected_count` (terminal import). `202 Accepted` / file selection is not import
  success; a partial import succeeds only if the task contract permits it.
- The Extraction Contract validates field TYPES and VALUE constraints against the ACTUAL records
  (e.g. `row_id`=integer, `score`=number, `label`=non-empty string): a missing field is
  `FIELD_MISSING`, a wrong type is `TYPE_MISMATCH`, an empty value is `VALUE_INVALID`. Renaming
  `score` -> `relevance_score` is `CONTRACT_MISMATCH` unless a reviewed compatibility rule proves
  equivalence (then the alias's type is still validated). Never silently map renamed/removed/
  type-changed fields, and never substitute a hand-written `schema_valid=True`.
- Object existence is not Job success. The lifecycle is `HEAD verified -> final FULL fence (active +
  session-expiry + lease_owner + lease_token + lease_expires_at + version) -> ONE guarded durable
  transaction (Artifact reference + Job publication), committed ONLY if the fence still matches ->
  commit`. The fence sits AT the durable-write boundary, so a fence failure/timeout/revocation commits
  NOTHING — there is no "DB reference committed but publication blocked" state. If the guarded
  transaction fails to commit, retain the private candidate and reconcile/forward-repair (an upload
  timeout then a matching HEAD forward-repairs against the verified object; never blind
  re-upload/overwrite/delete). Orphan GC is only later, audited, retention-governed cleanup. A real
  PostgreSQL transaction is NOT RUN; the pure model represents whether the guarded publish would
  commit or was rejected.

## Rollback (broad-listener release)

`Rollback stops future harm. Evidence scopes past harm. Classification decides repair.` Items are
classified from actually-preserved evidence: `CONFIRMED_CORRECT`, `MISATTRIBUTED_UNVERIFIED` (mark
untrusted; stop downstream use), `UNPUBLISHED_CANDIDATE` (retain privately), `UNKNOWN` (reconcile;
never blindly retry).

## Run

```bash
cd projects/fastapi-playwright
python3 -m pip install pytest==7.4.3
python3 -m pytest -q tests/test_day64_extraction_contract.py tests/test_day64_report_page_http.py
# -> 18 passed: pure decision-core FAILURE-PATH tests + the controlled report/export page over a
#    REAL HTTP loopback. No browser, Object Storage, or PostgreSQL is involved.
```

## Validation matrix (evidence tiers)

```text
[CONCEPTUAL_STATIC]      The LIVE CLASSROOM session — no Day64 source/tests/Playwright/download/upload/
                         Object-Storage/PostgreSQL/Worker run was executed in class.
[EXECUTED_LOCAL_RUNTIME] Run by the updating agent: py_compile + the pure Extraction/Artifact decision
                         core (readiness, strict correlation, schema drift, download/upload counts,
                         HEAD verify, persist/candidate retention, final-fence-controls-publish,
                         rollback classification) + the controlled report/export page over REAL HTTP
                         loopback = 18 passed.
[INTEGRATION_RUNTIME]    NOT RUN — real Playwright extraction/network interception/download-upload, the
                         REAL Day61 Object Storage HEAD, and a real PostgreSQL Artifact-reference
                         transaction, only if actually executed and evidence saved.
[PRODUCTION]             NOT RUN.
```

Day63's test results are NOT reused as Day64 evidence. No secrets, real credentials, Cookies,
storage-state exports, real target URLs, customer data, raw sensitive payloads, or screenshots are
committed; all data is synthetic and the page is served on 127.0.0.1. Day65 recovery/security and
Day66 queue integration are future work.
