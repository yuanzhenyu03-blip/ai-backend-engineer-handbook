# Day95 — RAG Ingestion Pipeline, Parsing, and Document Lifecycle

## 1. Objective

Day95 converts an untrusted uploaded source into a validated, immutable document
version. It stops before chunking, embedding, indexing, retrieval, and generation.

## 2. RAG position

RAG retrieves application-controlled evidence before generation. Day95 creates the
document truth that Day96 may later chunk; it does not implement retrieval itself.

## 3. Identity model

- A filename is mutable presentation metadata.
- `document_id` identifies one logical document inside one tenant boundary.
- `document_version_id` identifies one immutable version definition.
- `source_artifact_id` identifies the admitted immutable bytes reference.
- `operation_id` and `idempotency_key` identify one ingestion intent.
- attempt number, parser request ID, and parser generation identify one parse attempt.
- state, state version, and fence are mutable durable concurrency facts.

## 4. Source admission

The admission gate verifies size, checksum, detected content signature, media
contract, filename safety, and resource limits. Request-provided MIME and extension
are not authority. Encrypted, malformed, disguised, or oversized sources fail closed
or enter quarantine without reaching the parser.

This follows the OWASP guidance to distrust request Content-Type, validate signatures,
limit size, generate storage names, and separate upload storage:
<https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>.

## 5. Object Storage boundary

Bytes are written before the database stores the immutable object result reference.
The classroom model records bucket, key, object version, checksum, size, and detected
media type. Production still requires an executed object-store consistency,
versioning, checksum, conditional-write, retention, and orphan-cleanup design.

Conditional operations can prevent accidental overwrites, as illustrated by the S3
documentation:
<https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-requests.html>.

## 6. Happy path

```text
untrusted source
→ source admission
→ immutable source artifact reference
→ document/version/operation registration
→ current preflight
→ conditional PARSE_DISPATCH_STARTED claim
→ independent Parser Adapter process
→ ParsedDocumentCandidate
→ correlation
→ parse-manifest validation
→ source/output checksum validation
→ structural and application-binding validation
→ activation proposal
→ sole Ingestion Committer
→ ACTIVE immutable version
→ verified ingestion observation
```

## 7. Parser Adapter

Parser-private types remain inside the Adapter. The application receives only a
`ParsedDocumentCandidate`. A controlled text/Markdown/HTML parser is used so the
classroom needs no model Provider, network, or paid service. PDF admission exists,
but the controlled text parser rejects PDF rather than claiming unsupported parsing.

## 8. Parse manifest

The manifest binds tenant, document, version, source, source checksum, operation,
idempotency key, parser name/version/contract, attempt/request/generation, output
checksum, counts, warnings, and errors. A manifest is evidence, not activation
authority.

## 9. Sole Committer

The Committer conditionally compares document, version, operation, state version,
and fence. A successful activation atomically records the immutable parsed artifact,
activates the new version, supersedes the previous version, moves the document active
pointer, completes the operation, and records an outbox intent.

## 10. Duplicate and re-ingestion

An exact operation/source fingerprint returns the original version and operation.
Reusing an operation or idempotency identity with different bindings is an identity
conflict. Changed content or parse contract preserves tenant and logical document
identity but creates a new source, immutable version, operation, and idempotency
identity. Equal bytes never deduplicate across tenant authority boundaries.

## 11. Unknown outcome and recovery

A timeout after dispatch is not proof of non-execution. The Committer records
`PENDING_RECONCILIATION`. The Recovery Coordinator only queries the authoritative
registry. `NOT_FOUND` and `UNKNOWN` remain pending and use bounded re-query before an
operator alert. Recovery never replays the parser.

## 12. Safe retry

Only a Committer-persisted `PROVEN_NOT_EXECUTED` operation may enter the independent
bounded retry policy. Retry preserves operation, idempotency, tenant, document,
version, and source identities; it creates a fresh attempt number and parser request
ID and uses the current parser generation. Preflight runs again before a new durable
dispatch marker.

## 13. Lifecycle

- `REGISTERED`: version exists but is not published.
- `ACTIVE`: current published version and eligible for the Day96 gate.
- `SUPERSEDED`: previously active and still auditable.
- `QUARANTINED`: unsafe or rejected; blocked from parser/model/downstream use.
- `TOMBSTONED`: deleted, withdrawn, or unavailable as a lifecycle fact.
- `STALE_RESULT`: retained late evidence that cannot activate the document.

Quarantine and tombstone preserve evidence; neither is an instruction for immediate
physical deletion.

## 14. Day96 eligibility

Day96 can receive a version only when the document is `ACTIVE`, its active pointer
names that exact version, the version is `ACTIVE`, an immutable parsed artifact is
present, and the ingestion operation is `COMPLETED`.

## 15. Executed evidence

- 60 Day95 test methods pass, including the seed grader.
- 16/16 deterministic seed cases pass.
- Independent parser-process success and response-timeout paths pass.
- The deterministic end-to-end example reaches Day96 eligibility.
- Day88–Day94 dependency-free regression groups pass.
- The 31 pinned real MCP SDK stdio, Streamable HTTP, and restart tests pass.
- Compile and whitespace checks pass.

The executed interpreter is Python 3.11.5. Python.org listed Python 3.14.7 as the
current stable feature-series release during this classroom check:
<https://www.python.org/downloads/release/python-3147/>. The version difference is
recorded rather than hidden.

## 16. Production gaps

This evidence does not prove production readiness. Missing evidence includes a real
Authorization Server/OIDC/JWKS deployment, distributed transactional lifecycle
storage, production object storage, authenticated parser service, rate/capacity and
circuit controls, production telemetry and alert delivery, load/soak/backpressure,
network-partition and deployment-failure drills, retention/purge verification, and
Day95 restart persistence against a real distributed store. `production_readiness`
remains `MORE_EVIDENCE_NEEDED`.

OpenTelemetry semantic conventions standardize names across traces, metrics, and
logs, but telemetry remains diagnostic rather than lifecycle authority:
<https://opentelemetry.io/docs/concepts/semantic-conventions/>.
