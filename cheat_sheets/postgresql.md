# PostgreSQL Cheat Sheet

## Purpose

One-page review notes for PostgreSQL as the durable truth of an AI Backend. Built from Phase 3 lessons
(Day29+). Pair with [`interview/postgresql.md`](../interview/postgresql.md) and the
[data layer project](../projects/ai-backend-data-layer/README.md).

---

## Day29 PostgreSQL Foundations and Durable Relational State

Central rule:

```text
Application object/state = temporary
Database row             = durable business fact
Table schema             = enforceable contract for that fact
```

Ordering (the whole point of the lesson):

```text
WRONG: return 202 -> then write the Job row
RIGHT: write + commit the Job row -> then return 202
202 acknowledges a commitment that ALREADY exists durably.
```

### Hierarchy and session boundary

```text
Server process -> cluster -> database -> schema -> table -> row -> column
```

A `psql` session connects to **one database** (host/port/database/user). It does **not** connect to a
schema — schema resolves via a **qualified name** (`app.jobs`) or `search_path`. `public` is just the
**default namespace**, not "public information". Two senses of the word: PostgreSQL **Schema** = namespace;
**table schema** = the table definition/contract.

Session diagnostics: `\conninfo` · `SELECT current_database()` · `current_user` · `SHOW search_path` ·
`SELECT current_schema()` · `\dn` · `\dt app.*`.

### Job model types and defaults

```text
job_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid()
job_status        text        NOT NULL DEFAULT 'queued'
attempt_count     integer     NOT NULL DEFAULT 0
cancel_requested  boolean     NOT NULL DEFAULT false
provider_metadata jsonb       NOT NULL DEFAULT '{}'::jsonb   -- bounded, auxiliary only
created_at        timestamptz NOT NULL DEFAULT now()
started_at / finished_at        timestamptz NULL
error_message / result_object_key text NULL
```

UUID vs integer is a trade-off, not a ranking: UUID = distributed generation + non-enumerable public
identity, at the cost of size and index locality; integer = compact/index-friendly but centrally
generated and enumerable.

### Typed columns vs JSONB

```text
Typed columns -> identity, state, timestamps, counters, booleans, joins, indexes, integrity
Bounded JSONB -> OPTIONAL, non-authoritative auxiliary metadata
NEVER in JSONB -> large bytes, secrets, signed URLs, the only job_id, the only job_status
```

`integer`/`boolean`/`text`/`uuid`/`jsonb` are **types**. **One-to-many is cardinality**, not a type (Day31).
Large bytes stay in Object Storage; the DB stores a reference (`result_object_key`).

### NULL, DEFAULT, and what NOT NULL does not do

```text
NULL is context-dependent: unknown / not yet occurred / not available / not applicable
  started_at NULL        -> execution has not started (the Job EXISTS)
  finished_at NULL       -> not terminal yet
  error_message NULL     -> no recorded error
  result_object_key NULL -> no result artifact yet (NOT "input not uploaded")

NOT NULL rejects SQL NULL ONLY.
It ACCEPTS '' (empty string) and arbitrary text such as 'banana'.  -> CHECK/enum is Day31.
```

Prove defaults are the database's: `INSERT INTO app.jobs DEFAULT VALUES RETURNING *;`
(the client still sends an INSERT — it just **omits every business field**).

### Identity

```text
Primary key            -> identifies one ROW; prevents duplicate KEY VALUES
Idempotency/business key -> identifies one REQUEST; prevents duplicate OPERATIONS
```

A lost-202 retry creates a second row with a new UUID. The fix is a stored idempotency key + a database
**UNIQUE** rule + an **atomic insert/upsert** (read-before-write is race-prone). Day29 has neither, by design.

### timestamptz

```text
timestamptz -> ONE absolute instant, rendered in the SESSION time zone
timestamp   -> wall-clock fields only; does not identify a real moment
```

Same instant, two renderings, identical epoch. PostgreSQL does **not** preserve the original time-zone
label — store it separately if the business needs it.

### Validation ladder (never claim beyond evidence)

```text
conceptual/manual review
-> parser or PostgreSQL syntax/DDL acceptance (in a specific version)
-> real disposable-PostgreSQL behavior
-> application integration
-> production evidence
```

Reading DDL is not syntax proof. A local run is not integration or production. A process restart proves
process-lifecycle persistence only — not backups, HA, or hardware-failure durability.

### Durability vs integrity, and data repair

```text
Durability without integrity makes WRONG facts durable:
  'queud' is perfectly stored and never claimed by a worker.

Code rollback -> stops FUTURE bad writes
Data repair   -> fixes rows ALREADY persisted

Runbook: contain -> identify the exact affected set -> GUARDED update (narrow WHERE)
         -> capture evidence (row count + RETURNING) -> verify business recovery
```

Real identification needs release/time/tenant/provenance columns — absent from the Day29 minimal schema.

---

## Interview Phrases

- "The Job row is committed before 202; 202 acknowledges an existing durable commitment."
- "A psql session connects to a database, not a schema; qualify names or set search_path."
- "`public` is a default namespace, not a data classification."
- "Typed columns carry identity, state and time; bounded JSONB carries optional extras."
- "One-to-many is relationship cardinality, not a column type."
- "NOT NULL rejects NULL only — empty string and arbitrary text still pass."
- "A primary key identifies a row; an idempotency key identifies a business request."
- "timestamptz is one absolute instant rendered in the session time zone."
- "Durability is not integrity: a misspelled status is durable and unclaimable."
- "Code rollback stops future bad writes; a guarded UPDATE repairs persisted facts."
- "Never claim validation beyond the level you actually executed."
