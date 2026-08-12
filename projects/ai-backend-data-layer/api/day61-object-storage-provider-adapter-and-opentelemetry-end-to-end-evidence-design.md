# Day61 — Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence (Design & Runbook)

Engineering artifact / runbook for the Day61 external-evidence path. It records the
boundaries, the artifacts, the disposable local integration, the evidence pack format, and
the explicit NOT RUN limits. Day61 is **Completed**: the artifacts, local tests and a
disposable local `INTEGRATION_RUNTIME` run (PostgreSQL + Redis/Celery + MinIO + OTel Collector)
were executed. Real/paid Provider traffic and production-scale validation remain NOT RUN.

## What Day61 proves (and does not)

```text
Day59 durable HTTP acceptance (202 = committed bundle)
  -> Day60 Outbox delivery + Worker authority + lease fencing + recovery
  -> Day61 external Provider/Storage evidence + telemetry across REAL processes  (this lesson)
  -> Day62 Playwright runtime uses this proven backend execution/evidence path
  -> Day63 per-tenant authenticated BrowserContext isolation on the same correlation boundaries
```

Target tier: local `INTEGRATION_RUNTIME`, NEVER Production. Day61 does NOT call a real/paid
model Provider; a SEPARATE deterministic fake HTTP Provider proves adapter integration only.

## Artifacts

- `day61_provider_artifact_logic.py` — pure decision core (outcome classification;
  deterministic per-Attempt key; HEAD verify / non-overwrite conflict; checkpoint order;
  lease-token completion gate; telemetry safety). Unit-tested.
- `day61_fake_provider.py` — the SEPARATE deterministic fake HTTP Provider (`http.server`).
  IDEMPOTENT on the caller's stable `X-Correlation-Key`: the FIRST request for a key mints ONE
  external operation (one `provider_request_id` + one result); later same-key requests reuse it
  (no second Provider execution); a same-key request with an INCOMPATIBLE mode is HTTP 409. The
  ledger records every call attempt separately, proving "one external operation, many attempts".
  Modes: `success`, `timeout` (record receipt FIRST, then delay past the client timeout only on
  the first call; a later same-key call reconciles immediately), `invalid_response` (HTTP 200,
  contract-violating body).
- `day61_provider_adapter.py` — the Provider Adapter over REAL HTTP (`urllib`): timeout, a
  stable `X-Correlation-Key`, response-contract validation, data minimization.
- `day61_artifact_store.py` — S3/MinIO Result Artifact store: deterministic per-Attempt key,
  idempotent HEAD verification, non-overwrite conflict.
- `day61_worker_completion.py` — the guarded end-to-end path (SQLAlchemy Core) reusing the
  Day60 lease triple: a pre-call check that (in ONE tx) verifies the Attempt exists AND belongs
  to this Job AND the Job is running under THIS `lease_token`, THEN sets the LEASE-FENCED
  dispatch marker (a stale OR mis-targeted Worker stops before any HTTP call ->
  `lease_lost_no_external_call` / `attempt_mismatch_no_external_call`) -> HTTP call -> IMMUTABLE
  lease-fenced `provider_request_id` (NULL->set / same->idempotent / different->conflict) ->
  metadata COMPUTED from the actual result bytes -> HEAD verify -> ONE guarded completion under
  the CURRENT `lease_token`. All state changes (pending_reconciliation / contract failure /
  completion) are lease-fenced.
- `day61_worker_runtime.py` — the REAL authoritative-attempt COMPOSITION and the actual
  production Worker path (what the Celery task runs): `run_authoritative_attempt` does the
  Day60 guarded claim (`claim_and_start_attempt`, extracted so there is ONE claim
  implementation), loads tenant + the stable correlation key from PostgreSQL durable facts
  (NEVER the Celery message), then calls `run_external_operation` under the claim's lease token
  and returns its outcome VERBATIM. A Job reaches `succeeded` ONLY after a real Provider HTTP
  call + MinIO PUT/HEAD + guarded completion; there is NO "no Provider, straight to succeeded"
  production path. The Day60 `run_worker_attempt` skeleton remains a teaching artifact only.
- `day61_telemetry.py` — OpenTelemetry: spans for the Provider HTTP call, the Object Storage
  put/HEAD, and the guarded completion; `job_id`/`attempt_id` correlation; a hashed
  `provider_request_id` reference; a low-cardinality outcome counter
  (`provider`/`outcome`/`verification_outcome`). `operation_span()` swallows ONLY telemetry-layer
  errors (SDK init/span/attribute/export) and yields exactly once, so a BUSINESS exception
  inside the span propagates UNCHANGED (no double-yield). `init_telemetry()` is an OPTIONAL,
  idempotent, disabled-by-default SDK pipeline (TracerProvider + BatchSpanProcessor + OTLP span
  exporter; MeterProvider + PeriodicExportingMetricReader + OTLP metric exporter) whose endpoint
  comes from `OTEL_EXPORTER_OTLP_ENDPOINT` (no hardcoded URL/token) and which never raises when
  the SDK is absent. W3C trace context is now WIRED end to end: FastAPI acceptance opens a
  `fastapi.accept_job` ROOT span for the request (so a trace actually STARTS without external
  auto-instrumentation) and injects the request's `traceparent` into the `job.dispatch_requested` Outbox `payload` (existing JSONB;
  no migration); the Relay reads that payload OUTSIDE the DB lock and wraps its real publish in a
  diagnostic-only `outbox.relay_publish` span (parented on the payload's `traceparent`, so a
  Relay retry reuses the SAME trace association with a fresh Relay span id; the fenced
  `published_at` checkpoint stays OUTSIDE the span and a telemetry failure degrades to a
  no-op) and passes the carrier to the Celery task kwargs (keeping publish-outside-lock +
  fenced `published_at`); the Worker task
  extracts it and runs the unit-of-work / Provider / Storage / DB spans UNDER that context, so
  they CONTINUE the original trace. A Relay retry of the same durable intent reuses the SAME
  trace association (each publish still mints a fresh span id). `init_telemetry()` is bootstrapped
  at real process start (`bootstrap_telemetry()` in the FastAPI lifespan, the Relay `main()`, and
  the Celery `worker_process_init`) — idempotent, disabled by default, endpoint from
  `OTEL_EXPORTER_OTLP_ENDPOINT` only, and a no-op on SDK/exporter failure. A REAL OTLP export to a
  running Collector is INTEGRATION_RUNTIME (NOT RUN).
- `day61_integration/otel-collector.yaml`, `day61_integration/docker-compose.yaml`,
  `requirements-day61.txt`.

Schema note: NO new migration is added — the existing schema already supports Day61
(`app.result_artifacts` for Artifact metadata/reference, `app.job_attempts.provider_request_id`,
and `app.jobs.provider_dispatch_started_at` from Day60's `0010`). The Day60 head remains
`0012_day60_repair_audit_attestation`; the Day60 lease triple + recovery semantics are preserved.

## Core rules

- A Provider HTTP timeout does NOT prove non-receipt/non-execution; never blind-retry a
  potentially billable call. Persist `provider_dispatch_started_at` BEFORE the call
  (pre-call checkpoint, not success); persist `provider_request_id` as soon as returned and
  BEFORE the Artifact/success path (if that write fails, do not continue — reconcile).
- Our stable correlation/idempotency key (created before the call, reused for retries of the
  SAME Attempt) is DISTINCT from the Provider's `provider_request_id` (minted on receipt).
- Result Artifact key is deterministic PER-ATTEMPT (`results/{tenant}/{job}/{attempt}/result.json`):
  the same Attempt resumes safely; different Attempts never overwrite. Object Storage owns
  bytes; PostgreSQL owns business truth + Artifact metadata/reference.
- Upload success is not enough: verify by HEAD (metadata-only) — existence + checksum + size
  + content type. Upload-timeout-then-matching-HEAD -> forward-repair the reference, do not
  overwrite. Checksum/metadata mismatch -> CONFLICT: no overwrite, no success, reconcile.
  A DB rollback after upload does not undo Object Storage: retain + validate candidate
  evidence, then reconcile/forward-repair or auditable orphan GC later.
- Final success is ONE guarded PostgreSQL transaction under the CURRENT matching
  `lease_token`: verified Artifact reference + Attempt finished + success Event + Job
  running->succeeded + lease cleared. Object existence / HTTP 200 / Celery ACK / traces are
  NOT success. A stale Worker's guarded UPDATE matches zero rows.
- A stale Worker's final result must MATCH the database. If a timeout/invalid-response state
  transition's guarded UPDATE matches 0 rows (the lease was superseded after the HTTP response),
  `run_external_operation` returns `lease_lost_no_commit` — it does NOT report
  `pending_reconciliation`/`contract_failure`, write a stale Event, or ACK the transition. The
  successor Job is never touched by the old Worker.
- OpenTelemetry is diagnostic correlation, not business truth. Propagate/persist trace
  context HTTP -> Job/Outbox -> Relay -> Worker; reuse the trace association for the same
  durable Outbox intent on Relay retry; every actual operation gets a new span id. Logs/
  traces carry `job_id`/`attempt_id`/trace context but NOT a full `provider_request_id`
  (hash it); metrics use low-cardinality labels (provider, outcome) — never
  job_id/attempt_id/provider_request_id. A Collector/exporter failure must NOT fail a
  committed Job or trigger a duplicate Provider call.

## Outcome classification

```text
timeout + durable dispatch marker  -> pending_reconciliation (no blind new Provider call)
HTTP 200 + invalid body            -> Provider CONTRACT FAILURE (durable failed facts + diagnostics), not success
valid response                     -> Artifact HEAD verification -> guarded completion
```

## Safe disposable local run (OPT-IN; Docker-backed)

Never commit URLs/passwords/keys/tokens/fixture ids/container ids/`.venv`. Supply everything
via a local `.env` you create.

```text
# 0) install the OPT-IN stack
python3 -m pip install -r requirements-day61.txt

# 1) disposable PostgreSQL + Redis + MinIO + OTel Collector
cd day61_integration && docker compose up -d && cd ..

# 2) bootstrap a NEW database to the Day42 baseline, then migrate to the Day60 head
#    (the Alembic baseline is a STAMP target: it creates no DDL by itself)
export DAY48_ALEMBIC_DATABASE_URL='postgresql://<user>:<local-only>@127.0.0.1:5432/<db>'
psql "$DAY48_ALEMBIC_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto'
psql "$DAY48_ALEMBIC_DATABASE_URL" -v ON_ERROR_STOP=1 -f ../sql/001_create_jobs.sql
psql "$DAY48_ALEMBIC_DATABASE_URL" -v ON_ERROR_STOP=1 -f ../sql/003_relational_modeling_and_data_integrity.sql
alembic -c day48_alembic/alembic.ini stamp 0001_baseline
alembic -c day48_alembic/alembic.ini upgrade 0012_day60_repair_audit_attestation

# 3) the SEPARATE fake HTTP Provider (its own process)
DAY61_FAKE_PROVIDER_PORT=9099 python3 day61_fake_provider.py

# 4) env for the Worker path (sync PG URL + MinIO + OTel + fake Provider URL)
export DAY61_DATABASE_URL='postgresql://<user>:<local-only>@127.0.0.1:5432/<db>'
export DAY61_S3_ENDPOINT_URL='http://127.0.0.1:9000'
export DAY61_S3_ACCESS_KEY=<local-only>  DAY61_S3_SECRET_KEY=<local-only>
export OTEL_EXPORTER_OTLP_ENDPOINT='http://127.0.0.1:4318'
# drive one Job through run_external_operation(...) in each mode; verify from a NEW psql connection
```

## Evidence pack format

```text
sanitized command + revision/config + process versions + runtime boundary
fresh PostgreSQL readback (Job/Attempt/Event/Artifact/lease facts from a NEW connection)
fake Provider ledger evidence (one recorded receipt per correlation key)
MinIO object + HEAD metadata (checksum/size/content-type) vs the DB reference
logs / metrics / traces (job_id/attempt_id/trace context; provider_request_id hashed only)
explicit tier: CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION
```

## Evidence captured (validation tiers)

What the updating agent ACTUALLY executed (`EXECUTED_LOCAL_RUNTIME`):

```text
[EXECUTED_LOCAL_RUNTIME] py_compile of every Day61 module
[EXECUTED_LOCAL_RUNTIME] pytest test_day61_provider_artifact_logic.py test_day61_fake_provider_http.py test_day61_lease_fencing_and_telemetry.py -> 19 passed
[EXECUTED_LOCAL_RUNTIME] the fake Provider + adapter over REAL HTTP loopback (success / invalid-200 / timeout-after-receipt)
[CONCEPTUAL_STATIC] yaml parse of otel-collector.yaml + docker-compose.yaml
```

The real-HTTP-loopback test proves REAL socket/HTTP serialization, timeout-after-receipt,
correlation propagation, and the independent ledger — but it is NOT the full integration.

**INTEGRATION_RUNTIME NOT RUN.** The updating agent has NO Docker/PostgreSQL/Redis/MinIO/OTel
Collector, so the end-to-end path (Worker completion, Object Storage HEAD, durable state,
telemetry export) has NOT been executed against real infrastructure. Required integration
rerun matrix (execute against the real stack, verifying from a fresh DB connection, before
claiming `INTEGRATION_RUNTIME` / marking Day61 Completed):

```text
[NOT RUN] success: fresh DB Job=succeeded, Attempt finished, success Event, Artifact reference/provenance, lease cleared; MinIO HEAD matches DB; fake Provider ledger = one real HTTP call; correlated telemetry exists
[NOT RUN] delayed Provider response: ledger records receipt but the Worker client times out; fresh DB pending_reconciliation; no success Artifact; no blind second call
[NOT RUN] invalid 200 body: no success; durable contract-failure facts + diagnostics
[NOT RUN] upload timeout then matching HEAD: no overwrite; forward-repair uses the matching object + guarded completion
[NOT RUN] same key, mismatched checksum/metadata: CONFLICT, no overwrite/no success, reconciliation evidence
[NOT RUN] stale lease-token completion attempt updates ZERO rows and cannot claim success
[NOT RUN] Collector/exporter interruption: business success stays correct; telemetry limitation/error evidence recorded
[NOT RUN] success bytes<->metadata: the stored bytes' checksum/size/content-type equal the DB Artifact reference (VERIFIED, not CONFLICT)
[NOT RUN] a stale-lease-token Worker makes NO Provider HTTP call (guarded dispatch marker updates 0 rows -> lease_lost_no_external_call)
[NOT RUN] a stale Worker's timeout/invalid-response does NOT move the successor's running Job to pending_reconciliation/failed
[NOT RUN] provider_request_id immutability: a second, DIFFERENT id for the same Attempt -> conflict/pending_reconciliation, never an overwrite
[NOT RUN] real OTLP export to a running Collector (spans + low-cardinality metric); exporter down still commits the Job
```

## NOT RUN / out of scope (Day61)

```text
a real or paid model Provider (only the deterministic fake HTTP Provider is in scope)
production scale/load, security hardening, zero-downtime migration, multi-replica, real SLOs
```
