# Day105 L3 — Real PostgreSQL/pgvector Security Integration

Date: 2026-11-16

Status: `PASS` — bounded local runtime, container restart and offline replay executed

Production readiness: `MORE_EVIDENCE_NEEDED`

## Purpose and present evidence state

This document defines the bounded Level 3 promotion for Day105 RAG security.
The target is a real local PostgreSQL/pgvector data and control path with
database-backed currentness, append-only security records, transaction/CAS
failure injection, real vector retrieval and restart readback.

The Docker run, real integration tests, application-process reconstruction,
database-container restart and offline replay executed, and checksummed reports
were saved. The result is intentionally narrower than production readiness.

Saved evidence artifacts:

- [Day105 L3 evidence schema](../evidence/day105-l3-evidence-schema.json);
- [main integration report](../evidence/day105-l3-integration-report.json);
- [container-restart replay report](../evidence/day105-l3-restart-replay.json);
- [offline saved-evidence replay](../evals/run_day105_l3_evidence_replay.py).

The executed evidence level is:

```text
EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR_WITH_DETERMINISTIC_SECURITY_ADAPTERS
```

The final phrase matters. PostgreSQL and pgvector are real processes, but the
scanner, detector, DLP and model remain deterministic application-owned test
adapters. The run must not be described as production model-security evidence.

## Frozen prerequisites

Day105 L3 binds two earlier reports without changing them:

- Day104 real lifecycle baseline:
  `projects/ai-agent/evidence/day104-l3-integration-report.json`;
- Day104 checksum:
  `sha256:41e4b36ca1ccd589ca6ddcd99026bc6b48fc57e5a47c231ca8d32433b479ba85`;
- Day105 deterministic security baseline:
  `projects/ai-agent/evidence/day105-rag-security-report.json`;
- Day105 checksum:
  `sha256:b7cb38a8d7191d1404b162f88aae935c28f12628362e01b600c685299579f477`.

Neither report may be rewritten or relabeled. The L3 report is a new artifact
that cites both canonical checksums.

## Bounded architecture

The isolated local environment uses:

- PostgreSQL 16 with pgvector 0.8.7;
- the same pinned pgvector image digest as Day104 L3;
- a dedicated `day105_l3` database, user, Compose project, volume and loopback
  port;
- the Day104 lifecycle schema for Generation, pointer, ReadView and real vector
  rows;
- a separate Day105 schema for security snapshots, append-only artifacts,
  response intents and incident corrections.

This division preserves one authority per concern:

- the Day104 lifecycle tables decide which immutable Generation a ReadView pins;
- application-owned Day105 gates decide which retrieved occurrences may enter
  context and which candidate, if any, may leave the system;
- the vector database returns candidates but cannot grant instruction authority,
  authorization, destination or disclosure scope;
- the model may produce an `AnswerCandidate`, but cannot create a release
  decision or invoke a tool directly.

The database stores identities, digests, safe reason codes and decisions. It
must not store full prompts, protected chunks, raw attack payloads, candidate
answer text, secrets, cross-tenant text or raw vectors as security evidence.

## Required G2 to G3 sequence

The integration must preserve the request semantics established in the lesson:

1. P1, BS1, G2 and pointer revision 8 are current.
2. An old request opens a G2 ReadView and completes real pgvector retrieval while
   P1 is still current.
3. The application writes authoritative P2, which revokes A.
4. It freezes BS2, builds G3 with only C, and activates G3 at pointer revision 9.
5. The old request remains historically bound to G2; it cannot be rebound to G3
   or combine G2 and G3 results.
6. A new query attempt through the old ReadView fails the lifecycle adapter's
   current-authorization check.
7. The already-created old candidate is retained as historical derived evidence,
   but output release rechecks P2 and returns `FAIL/BLOCKED` with no citations.
8. Only a new request acquires G3/r9 and may release a C-backed answer.

ReadView pinning therefore gives repeatable identity, not permission to ignore a
later revocation.

## Scenario identities

The normalized report fixes these content-safe states:

```text
initial: P1 + BS1 + G2/r8 + Manifest {A@v1, C@v1}
current: P2 + BS2 + G3/r9 + Manifest {C@v1}
tombstone: B@v1
quarantine: X@v1, Y@v1
versioned rescan: Y@v1 remains immutable; Y@v2 is a new record and is not served
cross tenant: T@v1
cross-document chain: Z1@v1, Z2@v1
```

Q1, Q2 and Q3 must preserve the Day104 normal-quality ruler before P2:

```text
Q1 -> A@v1
Q2 -> C@v1
Q3 -> A@v1 + C@v1
```

After P2, a new Q2 request on G3 must still release C. A reject-all system fails
the `normal_quality_preserved` hard gate.

## Stage result is not defense outcome

Every security case records both the stage decision and the defense outcome.
For example, confirmed document injection must produce a stage `FAIL` and a
blocked serving action. That expected stage failure is successful defense, so
the case's `defense_outcome` is `PASS`.

The required case set is:

| Case | Expected stage | Serving action | Prompt / released citations |
|---|---:|---|---|
| `normal-q1-g2` | PASS | RELEASE | A / A |
| `normal-q2-g2` | PASS | RELEASE | C / C |
| `normal-q3-g2` | PASS | RELEASE | A,C / A,C |
| `poisoned-generation-not-served` | FAIL | NOT_SERVED | empty / empty |
| `document-injection-x-blocked` | FAIL | BLOCKED | empty / empty |
| `detector-timeout-y-quarantined` | INCONCLUSIVE | QUARANTINE | empty / empty |
| `detector-rescan-y-v2-append-only` | PASS | NOT_SERVED | empty / empty |
| `cross-document-z-blocked` | FAIL | BLOCKED | empty / empty |
| `cross-tenant-t-blocked` | FAIL | BLOCKED | empty / empty |
| `revoked-a-old-candidate-blocked` | FAIL | BLOCKED | A,C / empty |
| `new-q2-g3-released` | PASS | RELEASE | C / C |
| `wrong-citation-blocked` | FAIL | BLOCKED | C / empty |
| `dlp-timeout-blocked` | INCONCLUSIVE | BLOCKED | C / empty |
| `dlp-sensitive-blocked` | FAIL | BLOCKED | C / empty |

Each case binds the expected stage, observed stage, expected action, observed
action, prompt occurrence IDs, released citation IDs and an evidence digest.

## Twenty non-compensable hard gates

| Hard gate | Required executed evidence |
|---|---|
| `schema_migration_integrity` | Apply both schemas to the isolated database and prove required constraints and immutable-row triggers. |
| `postgresql_pgvector_identity_match` | Read PostgreSQL, pgvector, driver and pinned image identities. |
| `append_only_security_record_immutability` | Exact replay converges; same ID with changed digest and direct UPDATE/DELETE fail. |
| `ingestion_security_evidence_binding` | Content decisions bind occurrence, content, metadata, provenance, parser/scanner/detector and policy versions. |
| `quarantine_and_tombstone_currentness` | B, X and Y cannot become prompt context through retained rows or stale evidence. |
| `sealed_manifest_exact_binding` | Count, exact occurrence IDs, content digest, metadata version/digest and provenance revision match. |
| `provider_poisoning_not_served` | A negative-control Generation with extra occurrences cannot become serviceable. |
| `retrieval_authorization_and_tenant_isolation` | Current authorization and tenant checks deny revoked A and cross-tenant T. |
| `bundle_prompt_injection_isolation` | Full-bundle analysis blocks X and the composed Z1/Z2 attack before context assembly. |
| `context_assembly_exact_manifest` | The receipt binds exact included IDs/digests plus schema, serialization and projection versions. |
| `read_view_single_generation` | One request never combines G2 and G3; a stale G2 query fails after P2. |
| `authorization_snapshot_rebuild_and_activation` | P2 is authoritative before BS2/G3 are frozen and G3/r9 is activated. |
| `release_current_authorization_recheck` | The old G2 candidate is blocked after A is revoked. |
| `citation_exact_binding` | Claims and citations bind exact authorized occurrences; wrong citations release nothing. |
| `dlp_metadata_destination_fail_closed` | FAIL dominates unknown, and unknown alone blocks; metadata and destination checks are independent. |
| `security_snapshot_cas_and_transaction_atomicity` | Two sessions yield one CAS winner; injected transition failure leaves no partial pointer. |
| `incident_ledger_append_only` | Exact replay converges; overwrite, second root, missing predecessor and branch are rejected. |
| `normal_quality_preserved` | Normal Q1/Q2/Q3 pass before revocation and a new Q2 passes on G3. |
| `restart_durability_and_idempotency` | New repository instance and real container restart both preserve durable security state. |
| `content_safe_evidence` | Report and ledgers contain only approved identities, digests, safe outcomes and timestamps. |

Every PASS gate must reference immutable evidence IDs, SHA-256 digests and an
observation time. Aggregate test counts cannot substitute for gate evidence.

## Required failure injection

The saved report must contain individually bound checkpoints for:

- extra Provider occurrence and equal-count Manifest substitution;
- detector timeout and confirmed document injection;
- versioned Y@v2 parser/scan/detect evidence that does not overwrite Y@v1 and
  does not enter a serving Generation;
- cross-tenant candidate and cross-document bundle chain;
- artifact exact replay versus same-ID/different-digest conflict;
- security snapshot CAS race and transition-write rollback;
- authorization change after candidate creation;
- context projection digest tamper;
- wrong citation, DLP timeout and detected sensitive category;
- orphan candidate after restart;
- incident overwrite/root/branch conflict;
- database-container restart readback.

Each checkpoint records exact expected and observed outcomes, `PASS` only when
they match, and a digest bound to the integration-runner artifact. This prevents
a generic aggregate-success summary from replacing checkpoint evidence.

## Restart evidence

Application restart and database-container restart are separate claims:

- constructing a new repository and opening new connections proves only
  application-process restart;
- `docker compose restart postgres`, a later
  `pg_postmaster_start_time()` and non-destructive replay prove container restart.

Both paths must read back G3/r9, P2, the old blocked release, the incident chain
and the non-releasable orphan candidate. The restart runner must not install or
reset schemas. It must acquire and close a fresh G3 ReadView, and an old G2 query
must remain fail-closed.

## Report and content-safety contract

The saved report is
`projects/ai-agent/evidence/day105-l3-integration-report.json`. It must bind:

- the two frozen baseline checksums;
- database, image, driver and transaction identities;
- P1/BS1/G2/r8 and P2/BS2/G3/r9 identities;
- all security cases and twenty hard gates;
- test commands and results;
- every failure-injection checkpoint;
- repository, migration, test, runner and replay file digests;
- the Day104 lifecycle schema/repository digests, Day105 security
  schema/repository digests, Compose digest and pinned requirements digest;
- application and container restart evidence;
- the saved restart payload at
  `projects/ai-agent/evidence/day105-l3-restart-replay.json`, bound by canonical
  checksum, test-run digest and raw file digest;
- cleanup, L4 `NOT_RUN` boundaries and canonical report checksum.

These fields must all be `false`:

```text
fixture_production_eligible
raw_attack_payloads_logged
raw_protected_content_logged
raw_system_prompts_logged
raw_answer_candidates_logged
raw_secrets_logged
raw_cross_tenant_content_logged
raw_vectors_logged
database_url_logged
```

The offline replay also rejects raw-content field names, complete PostgreSQL URLs,
the database-URL environment name and private-key material.

## Executed and reproducible workflow

The integration remains opt-in and fail-closed. The executed workflow is reproducible with:

```bash
export DAY105_L3_PG_PASSWORD="$(openssl rand -hex 24)"
export DAY105_L3_DATABASE_URL="postgresql://day105_l3:${DAY105_L3_PG_PASSWORD}@127.0.0.1:55433/day105_l3"
export DAY105_L3_INTEGRATION=1

docker compose -f integration/day105/compose.yaml config --quiet
docker compose -f integration/day105/compose.yaml up -d --wait

PYTHONPATH=src:tests:. python -m unittest discover -s tests \
  -p 'test_day105_l3_postgres_unit.py' -q
DAY105_L3_INTEGRATION=1 PYTHONPATH=src:tests:. python -m unittest discover \
  -s tests -p 'test_day105_l3_postgres_integration.py' -q
DAY105_L3_INTEGRATION=1 PYTHONPATH=src:. python \
  evals/run_day105_l3_integration.py

docker compose -f integration/day105/compose.yaml restart postgres

DAY105_L3_INTEGRATION=1 PYTHONPATH=src:. python \
  evals/run_day105_l3_restart_replay.py
PYTHONPATH=src:. python evals/run_day105_l3_evidence_replay.py

docker compose -f integration/day105/compose.yaml down -v --remove-orphans
unset DAY105_L3_DATABASE_URL DAY105_L3_INTEGRATION DAY105_L3_PG_PASSWORD
```

Credentials were supplied at runtime and were never written into evidence.
Cleanup passed and bound the exact `day105-l3` Compose project and
`day105_l3_pg_data` volume identities. The report includes non-empty identity
digests for both removed resources.

The saved test records are fixed to `20/20` repository unit tests, `9/9` real
integration tests, `20/20` runner gates and `1/1` restart replay. Unit and
integration report digests are recomputed from their exact summaries. The
runner digest covers the saved cases, gates, failure injections and application
restart payload. The restart digest is the canonical checksum of the separate
saved restart report.

## What this local L3 PASS proves

Subject to the exact saved versions and fixture, PASS proves:

- real PostgreSQL constraints, transactions, locks, CAS and append-only trigger
  behavior for the tested statements;
- real pgvector storage, tenant/generation filtering and vector query behavior;
- exact Manifest readback and the refusal to serve a poisoned Generation;
- database-backed security currentness and fail-closed release orchestration;
- G2/G3 identity separation, durable incident history and restart readback.

It will not prove:

- recall or robustness of a real parser, scanner, detector, DLP or model;
- security of an external vector or model Provider;
- production IAM/RLS/TLS, secret rotation or external egress enforcement;
- HA, replication, backup restore, partitions or split-brain behavior;
- physical purge from WAL, backups, replicas, caches or retained media;
- production recall, latency, capacity, cost, load or soak;
- canary traffic, incident drill, observation window or production readiness.

## Design trade-offs and interview prompts

The security schema uses a small generic append-only artifact ledger rather than
one table per Day105 dataclass. This makes the first L3 bounded and replayable,
but requires strict application reconstruction and digest validation on read.
Production systems may choose typed tables or event schemas when query and
retention requirements justify the extra migration surface.

Useful interview questions include:

1. Why does ReadView pinning not authorize release after revocation?
2. Why must stage `FAIL` and defense `PASS` be recorded separately?
3. What does a CAS protect that an append-only audit table does not?
4. Why is a new database connection not evidence of container restart?
5. Why can a real PostgreSQL/pgvector test still rely on deterministic security
   adapters without becoming production security evidence?
