# Day64 — Dynamic Extraction, Network Events and Artifact Evidence

## 1. Lesson Metadata

```text
Status:        ✅ Completed — lesson + Extraction/Artifact decision core; EXECUTED_LOCAL_RUNTIME (pure logic + HTTP loopback)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 4-5 hours
Prerequisite:  Day63 authorized/isolated BrowserSession + final fence; Day61 Object Storage HEAD rule
Previous Lesson: Day63 — Browser Authentication, Storage State and Tenant Isolation
Next Lesson:   Day65 — Browser Failure Recovery and Security Boundaries
Engineering Artifact: projects/fastapi-playwright/ (Extraction Contract + Network Evidence + Artifact Manifest decision core + controlled report page + tests)
```

Day64 turns an authorized, isolated Day63 session into STRUCTURED, CORRELATED, VALIDATED, DURABLE
Artifact evidence — without confusing browser observations, HTTP success, file existence, Object
Storage existence, or Job publication with business truth.

> Evidence honesty: the LIVE CLASSROOM session produced a `CONCEPTUAL_STATIC` artifact — no Day64
> source, real Playwright, real download/upload, Object Storage, PostgreSQL, or Worker integration ran
> in class. The repository artifact added here is a PURE Extraction/Artifact decision core plus a
> controlled loopback report page; the updating agent authored and ran:
>
> ```
> cd projects/fastapi-playwright
> python3 -m pytest -q tests/test_day64_extraction_contract.py tests/test_day64_report_page_http.py
> ```
>
> Result: **18 passed, `EXECUTED_LOCAL_RUNTIME`** (16 pure decision-core FAILURE-PATH tests + 2
> controlled report/export page tests over a REAL HTTP loopback; no browser, Object Storage, or
> PostgreSQL involved). **NOT RUN:** real Playwright extraction / network interception /
> download-upload; the REAL Day61 Object Storage HEAD; a real PostgreSQL Artifact-reference
> transaction; a real Worker; and production. Day63's test results are NOT reused as Day64 evidence.
> This core proves the DECISION RULES only — never that a real browser, bucket, or database behaved as
> described.

---

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain why a page-load signal, HTTP 200, file existence, Object Storage existence, and Job
  publication are each distinct from business truth.
* Define a task-contract readiness fact (expected identity + terminal business status + required
  schema) and reject `{status: "generating"}` despite HTTP 200.
* Assign explicit roles to DOM vs network evidence and never merge sources silently.
* Design STRICT network correlation (approved origin + method + endpoint + report_id +
  client_request_id/export_id) and reject a broad URL+200 match or a background GET poll.
* Store only safe/redacted network metadata (never Cookies, Authorization headers, credentials, or
  raw payloads).
* Validate downloads (provenance, completed transfer, bounded size, ACTUAL content type, SHA-256,
  parse, schema, business) and use precise counts (`source_/artifact_/accepted_/rejected_count`).
* Distinguish `202 Accepted` from a terminal import, and permit partial success only when the
  contract allows it.
* Handle Extraction Contract drift (a rename is a mismatch without a reviewed compatibility rule).
* Verify Object Storage with HEAD, retain a candidate on a failed DB reference (not delete it),
  forward-repair a timeout+matching HEAD, and let the Day63 final fence still block publication.
* Classify a broad-listener release rollback: confirmed / misattributed / unpublished-candidate /
  unknown.

---

## 3. Why This Matters

A browser worker that "exports a report" is trusted to feed downstream systems and AI agents. If it
treats an observation as truth, it silently corrupts data at scale:

- **`generating` published as done** — the SPA returns HTTP 200 with `status: "generating"` and zero
  rows; publishing it ships an empty/partial report as a business fact.
- **Wrong response correlated** — a background poll (`GET` on the same URL) is matched instead of the
  real `POST` export, so the Artifact is built from the wrong action's data.
- **File extension trusted** — a `.csv` that is actually HTML/an error page is parsed as data.
- **`202 Accepted` = success** — the upload was queued, not imported; `498 accepted, 2 rejected` is
  reported as a clean success even though the contract forbids partials.
- **Object exists = Job done** — the bucket has the object but the DB reference transaction failed, so
  a later reader sees success with no durable, authorized reference — or the candidate is deleted and
  the evidence is lost.

Each of these is a real production incident: corrupted downstream analytics, an agent reasoning over
fabricated data, or an unrecoverable evidence gap. Day64 builds the contract that only publishes a
trusted Artifact when the WHOLE evidence chain holds.

---

## 4. Roadmap Position

```text
Day63 authorized authenticated browser work (session/identity/fence)
        |
        v
Day64 proves extraction, correlation, download/upload, and Artifact evidence   <-- you are here
        |
        v
Day65 recovery / diagnostics / security boundaries
        |
        v
Day66 bind the constrained browser capability to the durable queue-backed Job lifecycle
```

### Knowledge Continuity

```text
Previous Knowledge
  - Day63: authorized, isolated, revocable Session; positive identity fact; final fence governs publish
  - Day61: Object Storage object existence != success; verify with HEAD; retain/forward-repair, never blind delete
  - Day60/Day50: durable Job/Attempt, lease/fencing, Outbox
        |
        v
Current Lesson Concept
  - task-contract readiness; strict network correlation; download/upload validation + counts;
    Extraction Contract versioning; HEAD + DB-reference consistency; final fence still controls publish
        |
        v
Future Production Usage
  - Day65 uses the Extraction Contract + evidence classes for recovery/security; Day66 binds the
    contract to the durable queue-backed Job lifecycle
```

Reused mental models (named): the **Day63 final fence** (authorization still governs publication), the
**Day61 HEAD + retain/forward-repair** rule, and the **Day60/Day50 durable Job/Attempt** identity for
the Artifact Manifest.

---

## 5. Lesson Map

```text
task-contract readiness (expected id + terminal status + schema)
  -> DOM vs network roles (network primary; DOM corroborates)
    -> observe before acting (waiter before the Export click)
      -> STRICT correlation (POST + report_id + client_request_id/export_id; safe metadata)
        -> download validation + precise counts (provenance..business; 202 != import)
          -> Extraction Contract versioning (rename = mismatch without a reviewed rule)
            -> Object Storage HEAD + DB reference (retain/forward-repair, never blind delete)
              -> final Day63 fence still controls publishing
```

---

## 6. Core Mental Model

```text
page lifecycle signal
    != extraction readiness
    != valid Artifact
    != published business success

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

The one sentence to remember: **an observed event is not a correlated action, is not valid content,
is not a durable Artifact, is not authorized publication — only the whole evidence chain permits a
trusted result.**

---
## 7. Main Concepts

### Concept 1: Task-contract readiness — HTTP 200 is not "ready"

#### Tech Lead Question

The SPA fetched `/api/reports/42` and got HTTP 200. Can we export/publish now?

#### Student Thinking

The student first reasoned from downstream usefulness — "if it can be exported, an expert can use it"
— which is the right instinct (downstream-usable output matters) but weaker than a contract.

#### Student Answer

> 不能，事实应该是可以导出 expert 可以使用。 (later:) 不能，这不是任务合同规定的、可验证的业务完成事实。

#### Tech Lead Review

Correct, and sharpened: `page load` and HTTP 200 are OBSERVATIONS, not success. A report is ready only
when its expected identity, terminal business status, and required schema meet the task contract.
`{report_id: "42", status: "generating", rows: []}` blocks publication despite HTTP 200. Export
availability is weaker than a task-contract, verifiable business fact.

#### Engineering Thinking

- Why it exists: async SPAs return 200 long before the business result exists.
- Alternatives: "200 means done" — ships empty/partial reports as facts.
- Production risk controlled: publishing not-yet-ready data.

#### Production Example

`evaluate_readiness(contract, obs)` returns `NOT_READY_STATUS` for `generating`; only a terminal
`ready` status with the required schema is `READY`.

#### Framework Connection

Playwright can wait for the response, but readiness is a CONTRACT check on the payload, not a
lifecycle event.

---

### Concept 2: DOM vs network roles — corroborate, never merge silently

#### Tech Lead Question

The DOM shows 20 rounded rows; the network JSON has 500 full-precision rows. Which is the data?

#### Student Thinking

The student saw both matter and proposed combining them.

#### Student Answer

> 两者结合为依据。

#### Tech Lead Review

Right that they corroborate — but with EXPLICIT roles, not a silent merge. Here the network JSON is
the primary structured-data candidate (full precision, all 500 rows); the DOM corroborates
visible/readiness state (it is rounded and virtualized to 20 rows). If a contract instead requests
user-visible text, the DOM may be primary. Never merge sources without a stated role.

#### Engineering Thinking

- Why it exists: DOM rendering is lossy (rounding, virtualization); the API is the source of record.
- Alternatives: scraping the DOM as data — loses precision and rows.
- Production risk controlled: truncated/rounded data published as complete.

#### Framework Connection

`choose_primary_source(contract_wants_visible_text)` → `NETWORK_PRIMARY` by default.

---

### Concept 3: Observe before acting (and what it does NOT buy you)

#### Tech Lead Question

Do you register the response/download waiter before or after clicking Export?

#### Student Answer

> 选B，不用担心丢失重复下载，可进行恢复性下载。 (register the observer before the click.)

#### Tech Lead Review

Correct choice — register the strict download/response waiter BEFORE the Export click to avoid a
missed-observation race. But the correction matters: this prevents a MISSED OBSERVATION only; it does
NOT make a repeated click, re-download, or retry idempotent or safe. Duplicate side effects are a
Day65 recovery concern.

#### Engineering Thinking

- Why it exists: the event can fire before a late listener attaches.
- Alternatives: click then attach — races and misses the event.
- Production risk controlled: lost evidence, not duplicate actions.

---

### Concept 4: Strict network correlation — URL + 200 is too broad

#### Tech Lead Question

How do you prove the response belongs to THIS export, not a background poll?

#### Student Thinking

The student was honestly unsure at first ("不知道"), so this was taught directly, then confirmed.

#### Student Answer

> 不知道 → (after teaching) method / client_request_id.

#### Tech Lead Review

Exactly the strict fields. A URL substring + HTTP 200 is too broad — a background `GET` poll can
match. Use an explicit action identity: `POST /api/exports {report_id, client_request_id}` →
`{export_id, status}`. The INITIAL Export response must strictly match approved origin, method,
endpoint, report ID, AND `observed.client_request_id == expected.client_request_id`. A non-empty
`export_id` is NEVER a substitute for the request-id match — another action's response (its own
`export_id`) must be rejected. The `export_id` extracted from THIS verified initial response is the
only export identity a LATER poll/download/status call may correlate against. Store only
safe/redacted metadata drawn from an explicit ALLOW-list (`action_id`, `allowed_origin`, `method`,
`normalized_endpoint`, `report_id`, `client_request_id`, `export_id`, `response_status`,
`safe_checksum`, `observed_at`); reject any unknown key, any nested header/body map, Cookies,
Authorization, credentials, tokens, and raw payloads — by allow-list, not an ever-growing deny-list.

#### Engineering Thinking

- Why it exists: concurrent background traffic shares URLs and 200s.
- Alternatives: URL-substring matching — correlates the wrong response.
- Production risk controlled: building an Artifact from the wrong action.

#### Framework Connection

`correlate_export(expected, observed)` → `METHOD_MISMATCH` for a GET poll, `MISSING_ACTION_ID` for a
POST with no request id, `CLIENT_REQUEST_ID_MISMATCH` when the request id belongs to another action;
`extract_export_id(...)` + `correlate_followup(saved_export_id, ...)` for later calls;
`assert_safe_network_metadata(...)` enforces the allow-list.

---

### Concept 5: Downloads/uploads and precise counts

#### Tech Lead Question

The Export downloaded a `.csv` and the target returned `498 accepted, 2 rejected`. Success?

#### Student Thinking

The student had the right validation instinct and an honest question about what `record_count` means.

#### Student Answer

> 不能，验证输出符合 schema，以及文件要进行验证。 … 500 rows accepted，我还有个问题 record_count 是什么。 … 不能 (498/2 is not automatically success).

#### Tech Lead Review

Correct. Download validation requires provenance, a completed transfer, a bounded nonzero size, the
ACTUAL content type (never the filename extension alone), a SHA-256, parsing, schema validation, and
business constraints. And `record_count` splits into precise names: `artifact_record_count` (validated
rows parsed from the artifact), `source_record_count` (rows in source/API data), `accepted_count` /
`rejected_count` (target-system terminal import facts). File selection and `202 Accepted` do not prove
import success — a terminal `import_id`, status, accepted/rejected counts, and rejection summary are
required. `498 accepted, 2 rejected` is successful only if the explicit task contract permits partials.

#### Engineering Thinking

- Why it exists: a queued upload and a downloaded file look like success but aren't terminal facts.
- Alternatives: trusting the extension / a 202 — imports garbage or reports non-facts.
- Production risk controlled: partial/failed imports published as complete.

#### Framework Connection

`validate_download(...)` → `CONTENT_TYPE_MISMATCH`/`SCHEMA_INVALID`/…; `classify_upload(facts,
allow_partial)` → `NOT_TERMINAL`/`PARTIAL_NOT_ALLOWED`/`PARTIAL_SUCCESS`/`IMPORT_SUCCESS`.

---

### Concept 6: Extraction Contract versioning — no silent field mapping

#### Tech Lead Question

The API renamed `score` to `relevance_score`. Extract anyway?

#### Student Answer

> 是把这次任务视为提取合同不匹配。

#### Tech Lead Review

Correct — and the Contract validates VALUES, not just names. Each required field carries a type/value
spec (e.g. `row_id`=integer, `score`=number, `label`=non-empty string), validated against the ACTUAL
records: a missing field is `FIELD_MISSING`, a wrong type (e.g. `score:"not-a-number"`) is
`TYPE_MISMATCH`, an empty `label` is `VALUE_INVALID`. Renaming `score` to `relevance_score` is a
`CONTRACT_MISMATCH` unless an explicit, reviewed compatibility rule proves semantic equivalence (then
the aliased field's type is still validated). Do not silently map renamed, removed, type-changed, or
semantically unclear fields, and never substitute a hand-written `schema_valid=True` for real Contract
validation.

#### Engineering Thinking

- Why it exists: silent mapping hides breaking upstream changes and corrupts meaning.
- Alternatives: fuzzy/auto field mapping — publishes semantically wrong data.
- Production risk controlled: schema drift silently changing business meaning.

#### Framework Connection

`classify_schema(required_schema, records, reviewed_compat)` → `FIELD_MISSING` / `TYPE_MISMATCH` /
`VALUE_INVALID` / `CONTRACT_MISMATCH`; a reviewed rename validates the alias's type.

---

### Concept 7: Object Storage HEAD + DB reference; final fence still controls

#### Tech Lead Question

The object is in the bucket but the DB Artifact-reference transaction failed. Delete the object and
retry? And if the Session is revoked after the Artifact exists?

#### Student Answer

> 不能 (do not immediately delete the candidate after DB-reference failure). … 使用这个已验证对象继续做
> forward repair. … 不能，应该 gc (block publication after final-fence failure).

#### Tech Lead Review

Correct on all points, with the order made precise. Object existence is not Job success: after a
deterministic object-key upload, verify size/checksum/metadata with HEAD. Then the FINAL fence is
evaluated AT the guarded durable-write boundary — `HEAD verified -> final FULL fence -> ONE guarded
durable transaction that writes the Artifact reference + Job publication ONLY if the Session status,
expiry, lease_owner, lease_token, lease_expires_at and version still match -> commit`. So a fence
failure/timeout/revocation commits NOTHING: there is no "DB reference already committed but publication
blocked" state to undo. If the guarded transaction itself fails to commit, RETAIN the private
candidate and reconcile/forward-repair (an upload timeout then a matching HEAD forward-repairs against
the verified object; never blind re-upload/overwrite/delete). GC is a delayed, audited,
retention-governed lifecycle cleanup — NOT an immediate exception-path compensation. (A real
PostgreSQL transaction is NOT RUN; the pure model represents whether the guarded publish would commit
or was rejected.)

#### Engineering Thinking

- Why it exists: storage and business truth are separate systems that can diverge.
- Alternatives: delete-on-failure / publish-on-existence — loses evidence or fakes success.
- Production risk controlled: orphan mishandling and stale-authority publication.

#### Framework Connection

`verify_head(...)` then `decide_guarded_publish(...)` (HEAD -> final fence -> guarded txn) →
`RETAIN_UNPUBLISHED_FENCE` / `RETAIN_CANDIDATE_TXN_FAILED` / `FORWARD_REPAIR` / `PUBLISH`, reusing
`day63_session_gate.final_fence`.

---
## 8. Common Misconceptions

**HTTP 200 / page load means ready**

❌ The API returned 200, so the report is ready to publish.
✅ Readiness is a task-contract fact: expected identity + terminal business status + required schema.
`status: "generating"` blocks publication despite 200.

Why beginners think this: 200 feels like "done".
How to remember: 200 is transport; readiness is a contract.

**Combine DOM and network freely**

❌ Merge whatever the DOM shows with the JSON.
✅ Assign explicit roles — network JSON primary (full precision/rows), DOM corroborates. Never merge
without a stated role.

Why beginners think this: both "have the data".
How to remember: the DOM is a lossy view; the API is the record.

**URL + 200 correlates the response**

❌ A response whose URL contains `/api/exports` and returns 200 is our export.
✅ Prove an explicit action identity (POST + report_id + client_request_id/export_id); a background GET
poll must not match.

Why beginners think this: the URL "looks right".
How to remember: correlate the action, not the URL.

**Trust the file extension**

❌ It ends in `.csv`, so it's CSV.
✅ Validate the ACTUAL content type (sniffed), plus provenance, completed transfer, size, SHA-256,
parse, schema, and business rules.

Why beginners think this: the name says so.
How to remember: bytes, not names.

**202 Accepted / file selected = imported**

❌ The upload returned 202, so it imported.
✅ A terminal `import_id` + status + accepted/rejected counts are required; partials succeed only if
the contract allows.

Why beginners think this: the request "succeeded".
How to remember: accepted ≠ imported.

**Object in bucket = Job success (and delete on DB failure)**

❌ The object exists, so publish; if the DB ref fails, delete and retry.
✅ HEAD-verify, then require a durable DB reference; on failure retain the private candidate and
reconcile/forward-repair — never immediate delete. The final fence still governs publication.

Why beginners think this: existence feels like success.
How to remember: storage is not truth; retain, don't delete.

---

## 9. Engineering Trade-offs

**Network-primary vs DOM-primary extraction**

Network-primary (chosen default):
- Full precision and row count; a stable structured contract.
- Requires correlating the right response.

DOM-primary:
- Correct when the contract is about user-visible text.
- Lossy (rounding/virtualization) for structured data.

Tech Lead review: pick by contract intent; state the role; never silently merge.

**Strict action-identity correlation vs URL/200 matching**

Strict (chosen):
- Correlates the exact action; rejects background polls.
- Needs a client_request_id/export_id contract with the frontend.

URL/200:
- Trivial to write.
- Matches the wrong response — rejected.

**Retain candidate + forward-repair vs delete-and-retry on DB failure**

Retain + forward-repair (chosen):
- Preserves a HEAD-verified object as evidence; enables reconciliation.
- Needs an audited retention/GC lifecycle later (Day65+).

Delete-and-retry:
- "Cleans up" immediately.
- Loses evidence and can double side effects — rejected.

**Block on Extraction Contract drift vs auto-map fields**

Block (chosen): a rename/removal/type-change is a mismatch until a reviewed compatibility rule proves
equivalence. Auto-map is convenient but silently changes meaning — rejected.

---

## 10. Hands-on Exercises

### Exercise 1: Readiness contract (reusable artifact)

Question: Given `{report_id:"42", status:"generating", rows:[]}` at HTTP 200, decide publish/block.

Starter Artifact: `src/day64_extraction_contract.py::evaluate_readiness`.

Expected Output: `NOT_READY_STATUS` → block.

Follow-up: what three facts make it `READY`?

### Exercise 2: Correlate the export (design judgment)

Question: A background `GET /api/exports` returns 200 while your `POST` export is in flight. Which
correlates?

Starter Artifact: `correlate_export`.

Expected Output: the GET → `METHOD_MISMATCH`; a POST without `client_request_id`/`export_id` →
`MISSING_ACTION_ID`; only the matching POST → `CORRELATED`.

Follow-up: which metadata may you store, and which must you never store?

### Exercise 3: Counts and imports (reusable artifact)

Question: The target returns `202 Accepted`, then later `498 accepted, 2 rejected`. Success?

Starter Artifact: `classify_upload`.

Expected Output: `202` → `NOT_TERMINAL`; `498/2` → `PARTIAL_NOT_ALLOWED` unless the contract permits
partials (`PARTIAL_SUCCESS`).

Follow-up: define `source_/artifact_/accepted_/rejected_count`.

### Exercise 4: Storage + fence (design judgment)

Question: HEAD verifies the object but the DB reference fails; separately, the Session is revoked
after the Artifact exists. What happens to publication and the object?

Starter Artifact: `classify_persist` + `final_publish_decision`.

Expected Output: `RETAIN_CANDIDATE` / `RETAIN_UNPUBLISHED`; publish blocked; candidate retained (not
GC'd).

Follow-up: what makes an upload-timeout+matching-HEAD a `FORWARD_REPAIR`?

### Exercise 5: Broad-listener rollback (production judgment)

Question: A release weakened correlation to "any `/api/exports` 200". Roll back and classify affected
items.

Starter Artifact: `classify_affected_item`.

Expected Output: `CONFIRMED_CORRECT` / `MISATTRIBUTED_UNVERIFIED` / `UNPUBLISHED_CANDIDATE` /
`UNKNOWN`; rollback stops future harm, evidence scopes past harm, classification decides repair.

Follow-up: which class must be removed from downstream consumption immediately?

---

## 11. Relevant Framework Connections

**Playwright** (primary): `page.expect_response(...)` / `page.expect_download(...)` registered BEFORE
the Export click; strict response predicates (origin + method + endpoint + ids); `Download` provenance
+ completed transfer + saved bytes for validation. What to observe: the correlated response/download.
What NOT to trust: a broad URL match, a filename extension, or a lifecycle event as readiness.

**Object Storage (Day61 boundary)** — a LABELED boundary here (NOT executed): deterministic object
keys, HEAD verification of size/checksum/content-type, retain/forward-repair over blind
delete/overwrite. The Day64 core models the decision; it does not call a real bucket.

**PostgreSQL / SQLAlchemy** (planned): the durable Artifact-reference transaction and the Manifest
(tenant/job/attempt/session_id/session_version/object_key/checksum). A failed transaction retains the
candidate — a labeled boundary, not executed in Day64.

**Day63 Session Gate**: `final_publish_decision` reuses `final_fence` so authorization still governs
publication.

Future connections (labeled): Day65 recovery/diagnostics/security uses these evidence classes; Day66
binds the contract to the durable queue-backed Job lifecycle.

---
## 12. AI Backend Connections

A browser worker is a permissioned AI tool that produces Artifacts other systems and agents consume:

- **Agent data integrity**: if the tool publishes a `generating` report, an unrelated poll's data, or
  a partial import as success, the downstream agent reasons over fabricated facts and persists them.
  The Extraction Contract makes the tool's output a verified business fact, not an impression.
- **Evidence, not screenshots**: the durable Artifact is the Manifest + HEAD-verified object + safe,
  redacted Network Evidence — never Cookies/Authorization/raw payloads. This keeps credentials out of
  logs, traces, and model context.
- **Correlation as provenance**: `client_request_id`/`export_id` provenance lets a later audit prove
  which action produced which Artifact — essential when an agent's output is challenged.
- **Cost/safety of retries**: because "observe before acting" does not make retries safe, duplicate
  extraction/upload is a deliberate recovery decision (Day65), not an automatic behavior.

Production implication: an AI pipeline that cannot prove WHICH action produced an Artifact, that it is
VALID, and that it is AUTHORIZED to publish will silently poison analytics and agent memory. Day64's
chain is the provenance and validation layer that makes browser-derived data trustworthy.

---

## 13. English Interview

### Key Vocabulary

```text
task-contract readiness · extraction readiness vs page-load observation · strict network correlation
client_request_id / export_id provenance · safe/redacted metadata · Extraction Contract mismatch
artifact_/source_/accepted_/rejected_count · 202 Accepted vs terminal import · Object Storage HEAD
retain candidate / forward repair · final authorization fence · confirmed/misattributed/unpublished/unknown
```

### Useful Expressions

- "A page-load event is an observation; a valid extraction result is a verified business fact."
- "Correlate the action, not the URL."
- "Accepted is not imported; existence is not success."
- "Rollback stops future harm; evidence scopes past harm; classification decides repair."

### Beginner Question

Q: What is the difference between a page-load event and a valid extraction result?

Student answer (preserved): "page-load event is a observation, valid extraction result is a bussiness
truth."

Strong Answer: "A page-load event is only an observation about the browser lifecycle. A valid
extraction result is a verified business fact that satisfies the task contract — the expected report
is ready, the extracted data matches the schema, and the Artifact is validated before publication."

### Intermediate Question

Q: Before publishing an Artifact, how do you prove the response belongs to the current Export?

Student answer (preserved): "Monitoring and the establishment of definitive evidence of correlation
should be carried out first."

Strong Answer: "Before publishing, the worker must prove the response belongs to the current Export
action. It registers the response waiter before clicking, then validates the approved origin, HTTP
method, endpoint, report ID, and a stable client_request_id or export_id. If that correlation cannot
be proven, it must not publish the Artifact or blindly retry."

### Senior Question

Q: A release weakened correlation to "any `/api/exports` 200". Walk me through the response.

Student answer (preserved): "1. Roll back the erroneous release and pause any new, related Browser
Tasks. 2. Define a bounded 'affected set' based on version, release window, and audit evidence. 3.
Handle the items according to the classification of the actually preserved evidence."

Strong Answer: "First, roll back the faulty release and pause related Browser Tasks to stop further
harm. Next, build a bounded affected set using the release version, a time window, and preserved audit
evidence. Then classify each affected item: confirmed-correct results can remain; unverified or
misattributed results must be marked untrusted and removed from downstream use; unpublished candidates
are retained for reconciliation or audited garbage collection; and unknown outcomes must not be
blindly retried. Finally, restore the strict correlation contract and add regression tests before a
controlled rollout."

### Common Weak Answer

"The export downloaded a CSV and the API returned 200, so the report is published." This confuses
observations and file existence with a correlated, validated, authorized Artifact.

### Strong Answer (summary)

"A trusted Artifact = authorized Session + fresh isolated Context + task-contract ready fact +
correctly correlated network/DOM/download evidence + schema/content validation + Object Storage HEAD
verification + a durable Artifact reference + the final Day63 authorization fence."

---

## 14. Mental Model Summary

```text
page lifecycle signal   != extraction readiness != valid Artifact != published success
readiness               = expected id + terminal business status + required schema
sources                 = network JSON primary (full precision/rows); DOM corroborates (rounded/virtualized)
observe-before-acting   = prevents a missed observation ONLY (not safe retries)
correlation             = origin + POST + endpoint + report_id + client_request_id/export_id (URL+200 is too broad)
safe metadata           = endpoint/method/ids/status/timestamp/checksum (never cookies/authorization/raw)
download                = provenance + complete + size + ACTUAL type + sha256 + parse + schema + business
counts                  = source_/artifact_/accepted_/rejected_count ; 202 Accepted != terminal import
schema drift            = rename/remove/type-change = Extraction Contract Mismatch (no silent map)
storage                 = HEAD verify ; DB-ref fail -> retain candidate + forward repair (never blind delete)
final fence             = Day63 fence still blocks publication after an Artifact exists
rollback                = stop future harm ; scope past harm by evidence ; classify to decide repair
```

---

## 15. Today's Takeaway

- **Most important mental model**: an observed event ≠ correlated action ≠ valid content ≠ durable
  Artifact ≠ authorized publication; only the whole chain publishes.
- **Most important production risk**: publishing an observation (200 / file / object / 202) as
  business truth.
- **Most important trade-off**: strict action-identity correlation and retain+forward-repair over
  URL/200 matching and delete-on-failure.
- **Most important framework connection**: Playwright `expect_response`/`expect_download` before the
  click + strict predicates, backed by Object Storage HEAD and the Day63 fence.
- **Most important AI Backend connection**: provenance + validation make browser-derived data
  trustworthy for agents.
- **Most important interview answer**: "Correlate the action, not the URL; accepted is not imported;
  existence is not success."

---

## 16. Before Next Lesson Checklist

- [ ] I can explain why page-load/200/file/object/202 each differ from business truth.
- [ ] I can define task-contract readiness and reject `generating`.
- [ ] I can assign DOM vs network roles without merging silently.
- [ ] I can design strict correlation and reject a background GET poll / broad URL+200.
- [ ] I can list the safe metadata and the forbidden metadata.
- [ ] I can validate a download and use precise counts; 202 ≠ terminal import.
- [ ] I can treat a field rename as an Extraction Contract Mismatch without a reviewed rule.
- [ ] I can HEAD-verify, retain a candidate on DB-ref failure, forward-repair a timeout+HEAD, and let
      the final fence block publication.
- [ ] I can classify a broad-listener rollback (confirmed/misattributed/unpublished/unknown).
- [ ] I can run the artifact: `python3 -m pytest -q tests/test_day64_extraction_contract.py tests/test_day64_report_page_http.py` (= 18 passed).

---

Related: [Day64 design/runbook](../../projects/fastapi-playwright/docs/day64-dynamic-extraction-network-events-and-artifact-evidence-design.md) ·
[extraction contract](../../projects/fastapi-playwright/src/day64_extraction_contract.py) ·
[controlled report page](../../projects/fastapi-playwright/src/day64_controlled_report_page.py) ·
[tests](../../projects/fastapi-playwright/tests/test_day64_extraction_contract.py) ·
[cheat sheet](../../cheat_sheets/fastapi.md) ·
[interview](../../interview/fastapi.md) ·
Previous: [Day63 lesson](day63-browser-authentication-storage-state-and-tenant-isolation.md)
