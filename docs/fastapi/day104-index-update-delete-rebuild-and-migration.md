# Day104 — Index Update, Delete, Rebuild and Migration

## 1. Lesson Metadata

- **Status:** Completed at guided classroom L2 and local integration L3
- **Template:** `LESSON_TEMPLATE_v2`
- **Phase:** 7C — Production RAG Engineering
- **Difficulty:** Advanced
- **Estimated study time:** 8–10 hours
- **Prerequisites:** Day95–Day103, especially document lifecycle, authorization,
  immutable embeddings, vector generations and evaluation hard gates
- **Previous lesson:** [Day103 formal
  lesson](day103-retrieval-evaluation-and-rag-answer-evaluation.md)
- **Next lesson:** Day105 — RAG Security: Prompt Injection, Poisoned Documents and
  Data-leakage Boundaries
- **Main artifact:** immutable index-generation lifecycle with BuildSnapshot, Manifest,
  READY gate, pointer CAS, leased ReadViews, deletion ledger and rollback eligibility
- **Learning assessment:** 90/100 after explicit remediation
- **Evidence:** `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE` plus
  `EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR`
- **Production readiness:** `MORE_EVIDENCE_NEEDED`

The 90/100 score is evidence of learner understanding. The score itself is not
infrastructure evidence; the separate saved L3 report supplies the bounded local
PostgreSQL/pgvector evidence. Neither proves zero downtime or production
readiness.

## 2. Learning Objectives

By the end of Day104, the learner can:

- separate durable business truth from a derived retrieval view;
- explain immutable Generation identity versus mutable pointer revision;
- freeze `S/P/E/IS/W/D` into a BuildSnapshot before construction;
- use Expected-versus-Actual Manifest read-back instead of trusting write ACKs;
- bind Day103 evaluation evidence to one exact Generation and ruler;
- distinguish `PASS`, `FAIL`, `INCONCLUSIVE` and `NOT_RUN`;
- activate a READY Generation with CAS, fencing and an append-only record;
- keep Provider alias projection outside the application transaction;
- pin each request to one Generation without allowing a revoked authorization;
- drain old ReadViews before retirement;
- persist Tombstones and prevent deletion resurrection during rebuild;
- distinguish logical release, serving-index absence and physical purge;
- reject stale rollback targets under changed source, authorization or deletion facts;
- explain ABA prevention through monotonic pointer revisions;
- map each invariant to deterministic L2 code and failure tests;
- explain what the local L3 run adds beyond L2;
- state which claims remain outside L3 and require L4 evidence.

## 3. Why This Matters

An index rebuild can produce correct vectors and still be unsafe. It may include a
superseded 30-day policy, omit the current application channel, carry stale ACL
metadata, resurrect a deleted occurrence, or switch half of the requests before
the new Generation is ready. A retry can overwrite an earlier operation binding,
and an old Worker can return correct bytes after losing commit authority.

Day104 therefore asks a different question from Day103. Day103 determines whether
a candidate performs acceptably under a frozen ruler. Day104 determines which
exact candidate may become active, how readers move between generations, and how
the system recovers without rewriting business truth or history.

## 4. Roadmap Position

```text
Day95  document versions, durable lifecycle and Tombstones
Day97  authorization and provenance snapshots
Day98  Embedding contract and immutable EmbeddingSet
Day99  shadow Generation, vector Manifest and Provider read-back
Day100 request-time authorization and selected retrieval bundle
Day103 independent labels, metrics, slices and hard gates
Day104 update/delete/rebuild/migration control plane
```

Day104 consumes the frozen Day103 handoff. A comparison is meaningful only when
dataset, labels, source and authorization snapshots, evaluator, metric definitions,
slices, thresholds and hard gates are explicitly bound.

Related records:

- [Day103 → Day104 handoff](../../projects/ai-agent/docs/DAY103_TO_DAY104_HANDOFF.md)
- [Day104 application design](../../projects/ai-agent/docs/DAY104_INDEX_GENERATION_LIFECYCLE.md)
- [Record](../../projects/ai-agent/docs/day104-index-generation-lifecycle-classroom-draft.md)

## 5. Lesson Map

```text
fixed A/B/C + Q1/Q2/Q3 case
→ freeze S/P/E/IS/W/D
→ build and seal G2 off path
→ independent Manifest read-back
→ Day103 evaluation and READY
→ pointer CAS and request pinning
→ drain, rollback decision or retirement
→ replayable evidence and honest NOT_RUN boundary
```

### Fixed refund case and identity vocabulary

The entire lesson follows one case:

```text
A@v1 — current policy: unopened items may be refunded within 14 days
B@v1 — superseded historical policy: 30 days
C@v1 — current manual: apply through online customer service

Q1 — refund window              → A@v1
Q2 — application channel        → C@v1
Q3 — both facts                 → A@v1 + C@v1
```

`B@v1` may remain an evaluation distractor, but it is not eligible current
production content. Source history can retain it while a Deletion Snapshot prevents
it from entering later serving generations.

```text
S  Source Snapshot
P  Authorization Snapshot
E  Embedding Contract
IS Index Schema and physical contract identity
W  authoritative source watermark
D  Deletion Snapshot
BS Build Snapshot
G  immutable Generation
R  evaluation report
```

The initial build identity is:

```text
BS1 = S1 + P1 + E1 + IS1 + W1 + D1
```

Changing any build-relevant binding changes the BuildSnapshot fingerprint.

## 6. Core Mental Model

```text
Application Source/Authorization/Delete truth
                  |
                  v
          freeze BuildSnapshot
                  |
                  v
        build immutable Generation
                  |
                  v
       read-back + evaluate + READY
                  |
                  v
      CAS application active pointer
                  |
          +-------+-------+
          |               |
     new ReadViews    old ReadViews drain
```

The Source Store owns current refund facts. Authorization storage owns current
access. The deletion ledger owns logical unavailability. Their snapshots are
immutable evidence, not alternative owners.

A Generation is derived even when it is durable on disk. The application pointer
is mutable control-plane truth. A Provider alias is a derived projection, and an
Outbox event is a wake-up hint. Consumers must reread application truth because
events may be duplicated, delayed or delivered out of order.

## 7. Main Concepts

### Concept 1 — Spiral one: thin complete G1 to G2 migration

The first pass keeps business truth unchanged and connects the whole lifecycle:

```text
freeze BS1
→ build G2 off path
→ seal Provider checkpoint
→ authoritative read-back
→ Manifest Expected = Actual
→ Day103 candidate evaluation PASS
→ G2 READY
→ CAS G1/r7 to G2/r8
→ new requests pin G2
→ old requests finish on G1
→ G1 DRAINING
→ G1 RETIRED after drain and retention
```

The learner correctly began with the ownership invariant:

> “S1是经过验证的持久化事实，不能因为检索视图发生变化
> 修改持久化事实。”

They also stated the repair direction:

> “S1纠正G1，依据事实修改检索索引。”

The lesson refined the wording: current Source Store state is the owner; S1 is an
immutable point-in-time snapshot. The learner initially described `generation_id`
as an alias combined with a version. The correction separated immutable
`generation_id` from mutable `pointer generation + revision`.

Before READY, the learner independently required:

> “read-back 验证核对 counts、exact IDs、metadata/provenance、content digests；
> Day103 Candidate evaluation再检查质量阈值、关键 slices 和 hard gates。”

That answer established the complete normal path before failures were introduced.

## 8. Common Misconceptions

The second spiral exposed misconceptions by changing only one condition at a time:

```text
❌ Same operation ID means the latest payload wins.
✅ The first identity/digest binding is immutable; a changed payload conflicts.

❌ Correct late output may still commit.
✅ A Worker that lost its fence lost commit authority, even if its bytes are correct.

❌ A delete request means the data is gone everywhere.
✅ Tombstone, serving-index absence and physical purge are separate states and evidence.

❌ An old Generation is always a safe rollback target.
✅ Rollback is policy-eligible only while current S/P/E/IS/W/D still permits it.
```

### Spiral two — Retry, ordering, fencing and delete failures

Each failure was added separately.

### Exact retry and identity conflict

The same operation ID, target, parameters and digest converges to its first result.
The same operation ID with a different digest is an identity conflict. In one
manual trace, the learner first wrote “reflect digest-x 1.” The correction kept
the first durable binding instead:

```text
original digest = digest-A
incoming digest = digest-X
decision        = IDENTITY_CONFLICT
stored binding  = digest-A
apply count     = 1
```

The learner restated the invariant as:

> “保护原绑定的digest，目标、原版本。”

### Out-of-order source and fencing

A delayed C@v0 cannot replace C@v1 because delivery order is not source authority.
When an old Worker with fence 41 returned correct content after ownership moved to
fence 42, the learner rejected it: correct content does not restore lost commit
authority.

### DeleteIntent, Tombstone and anti-resurrection

The learner placed durable deletion intent and Outbox in the application database.
The correction separated:

```text
Tombstone/DeleteIntent  durable logical fact
Outbox                  reliable wake-up hint
Provider delete/build   derived projection
```

A future rebuild must bind D1. If the deletion ledger advances to D2 before READY,
the D1 candidate is stale; it is not patched in place.

## 9. Engineering Trade-offs

The design accepts more immutable artifacts, identity records, current-state reads and reconciliation in exchange
for reproducibility and safer failure recovery. An in-place rebuild uses fewer resources but destroys a stable
read and rollback target. Provider ACKs are cheaper than independent read-back but cannot prove what is currently
stored. Keeping `INCONCLUSIVE` in `VALIDATING` consumes capacity longer, but avoids turning missing evidence into
either a false PASS or a false observed failure.

### Manifest, Provider seal and Day103 release evidence

Builder and Validator have different responsibilities:

```text
Builder   derives Expected from trusted BS
Validator derives Actual from authoritative Provider read-back
```

Manifest comparison includes:

- count derived from exact occurrence IDs;
- sorted unique exact occurrence IDs;
- content digest;
- metadata digest;
- provenance digest;
- exact expected-absent Tombstone IDs.

Equal count cannot distinguish `{A@v1, C@v1}` from `{A@v1, B@v1}`. The learner
correctly named all four comparison groups, initially typing “content disgust” and
then adopting the correct term `content digest`.

The Provider namespace is sealed at a checkpoint and write fence. Validation for
`cp17` cannot authorize content at `cp18`. After seal, old Worker writes are
rejected.

`mark_ready()` requires lifecycle version, current BuildSnapshot, sealed physical
identity, matching Manifest, a frozen Day103 EvaluationRuler, exact Validation and
Evaluation evidence digests, and a final `PASS`. The learner
initially named only `expected_state_version`; the corrected gate includes every
identity and evidence boundary.

```text
observed violation       → FAIL
missing evaluator output → INCONCLUSIVE
all required evidence    → PASS
```

An `INCONCLUSIVE` report keeps the same sealed candidate in `VALIDATING`; it does
not prove that a rebuild is necessary.

## 10. Hands-on Exercises

### Exercise 1 — Write the activation boundary

**Question:** Given `G1/r7 ACTIVE` and `G2 READY`, which facts must change together?

**Think first:** Separate application database truth from the external Provider alias call.

**Starter artifact:** `pointer + target lifecycle + previous lifecycle + ActivationRecord + Outbox`.

**Expected output:** The transaction below, followed by idempotent alias reconciliation.

**Follow-up:** Explain why returning to G1 must use revision r9 rather than r7.

### Recorded activation, alias projection and ABA result

Activation is one modeled application transaction:

```text
pointer: G1/r7 → G2/r8
G2: READY → ACTIVE
G1: ACTIVE → DRAINING
append ActivationRecord
append INDEX_POINTER_CHANGED Outbox event
```

The learner initially put `G1 ACTIVE → DRAINING` outside the transaction because
they associated DRAINING with zero readers. The correction distinguished immediate
traffic closure from later retirement:

```text
ACTIVE → DRAINING   at pointer cutover
DRAINING → RETIRED  after readers reach zero and policy permits
```

The Provider alias update runs after database commit. If it succeeds but its ACK
is lost, replay read-backs the already-correct alias and marks the original Outbox
event dispatched. It does not create a new pointer revision.

The activation fence comes from an independently issued current lease. A higher
token can invalidate an old Worker before either one commits; comparing only with
the last successful activation would not provide real fencing.

Rollback is a new forward CAS:

```text
G1/r7 → G2/r8 → G1/r9
```

Returning to `G1/r7` would create an ABA ambiguity and allow a stale Committer to
act as though the G2 interval never happened.

## 11. Relevant Framework Connections

- **PostgreSQL:** the L3 lab exercises real transactions, row/CAS competition,
  constraints, durable Inbox/Outbox records and transactional pointer/lifecycle
  changes on one pinned local PostgreSQL configuration. HA, failover and restore
  remain separate production evidence.
- **Vector database:** a collection/namespace and Provider alias are derived
  projections. The local pgvector L3 lab proves sealed generation read-back,
  filters and an HNSW index plan for the fixed fixture; other Provider alias,
  replica and consistency semantics require their own evidence.
- **Queue Worker:** at-least-once delivery makes events wake-up signals. Consumers reread application truth and
  protect commits with stable operation identity and fencing.
- **FastAPI request path:** middleware or request-scoped dependency can acquire one ReadView and carry its
  Generation and authorization binding through the whole retrieval/grounding attempt.

### ReadViews, drain, retirement and rollback eligibility

`acquire_read_view()` atomically validates pointer generation/revision and ACTIVE
state, inserts an OPEN leased ReadView, and increments the reader summary. A race
causes a complete retry against the new pointer; it never joins a DRAINING
Generation.

Each ReadView binds generation, pointer revision, BuildSnapshot, authorization,
owner, fencing token and lease deadline. A Reaper expires an abandoned lease and
decrements readers exactly once. A late release using an old fence is rejected.

The ReadView ledger is authoritative; `active_readers` is a summary. When the
learner said the system could “等待状态同步” after a mismatch, the correction
required an active, audited reconciliation and blocked retirement until ledger and
summary agreed.

Rollback eligibility is rechecked against current `S/P/E/IS/W/D`. A retained G1
that contains deleted B or stale authorization P1 is not safe merely because its
files still exist. `DRAINING → ACTIVE` is permitted only through a fresh rollback
CAS; `RETIRED` and `FAILED` are terminal for that artifact.

## 12. AI Backend Connections

RAG retrieval correctness depends on more than vectors. Chunk, metadata, authorization, embedding, schema,
deletion and evaluation identities form one release boundary. A ranker score cannot authorize stale content, and
a good average metric cannot compensate for a forbidden occurrence. The same immutable-generation pattern also
applies to feature stores, model-serving bundles and prompt/template releases.

### Spiral three — Business truth changes

The policy then changes:

```text
A@v1 = 14 days
A@v2 = 21 days

S1 → S2
P1 → P2
W1 → W2
E1, IS1 and D1 unchanged
```

The learner produced:

```text
BS2 = S2 + P2 + E1 + IS1 + W2 + D1
```

Labels become:

```text
Q1 → A@v2
Q2 → C@v1
Q3 → A@v2 + C@v1
```

G2 and G3 must be evaluated with the same current labels before comparison. The
old report remains immutable history, not a transferable release certificate.

An old request pinned to 14-day content cannot publish after an immediate 21-day
effective boundary. The entire attempt is retried under a fresh ReadView. Reusing
C@v1 from one Generation and A@v2 from another would violate request-level
consistency.

During the closed-book trace, the learner initially accepted an ordinary
`A@v2 → A@v1` downgrade. The correction established that
`expected_previous_version` prevents a race but does not authorize version
regression. If policy later returns to 14 days, it creates A@v3 rather than
reactivating A@v1.

## 13. English Interview

### Beginner

**Question:** Why should a vector index be treated as derived state rather than durable truth?

**Strong spoken answer:** “The application source owns business truth. A vector index is a versioned materialized
view that can be rebuilt from frozen source, authorization and deletion state. Index mutations must never rewrite
the source merely to make retrieval appear consistent.”

### Intermediate

**Question:** Why must each request pin one index Generation?

**Strong spoken answer:** “Pinning gives the request one stable corpus and Manifest. If the active pointer changes
mid-request, the old attempt either completes under its original view and current release authorization or is
retried as a whole; it never splices results from two Generations.”

### Senior

**Question:** Design a safe migration and explain when rollback is forbidden.

**Strong spoken answer:** “I build and seal a shadow Generation from a frozen BuildSnapshot, validate read-back,
run the unchanged evaluation ruler, then CAS a revisioned application pointer. I drain leased ReadViews and
reconcile the Provider alias from database truth. Rollback is another forward CAS and is forbidden when the old
Generation violates current source, authorization, deletion or query-contract facts.”

### Transfer case and recorded learner assessment

The transfer case replaced refunds with an employee moving Finance → Sales. The
learner successfully transferred the model:

- current P11 revocation overrides an old G10 ReadView;
- G11 binds `S10 + P11 + E10 + IS10 + W10 + D10`;
- equal IDs and vectors are insufficient when metadata still binds P10;
- G10 is rollback-ineligible under current P11;
- G12 may reuse valid E10 vectors but must rebuild current P11 metadata.

The learner also answered three English interview questions. Corrections clarified
that an activation pointer is current selection truth rather than a trigger, and
that an authorization revocation blocks a response for one principal rather than
making the entire Generation globally unavailable.

The final learning score was **90/100 after remediation**:

```text
Truth ownership          14/15
Update/delete/order      12/15
Manifest                 19/20
Activation               18/20
Rollback                 14/15
Evidence                  9/10
English                   4/5
```

This score measures the learner. It must not be cited as L3/L4 or production
evidence.

## 14. Mental Model Summary

```text
Source/authorization/deletion stores = durable truth owners
BuildSnapshot                       = frozen build input identity
Generation                          = immutable derived view
Manifest + read-back                = integrity evidence
Day103 report                       = independent quality evidence
READY                               = eligibility, not visibility
Pointer + revision                  = application serving selection
Provider alias                      = reconciled projection
ReadView                            = one request's pinned Generation
Tombstone                           = anti-resurrection input
Rollback                            = new forward CAS under current policy
```

### Deterministic L2 implementation and validation

The optional L2 extension translated the lesson into deterministic code:

- immutable contracts and fingerprints;
- Builder/Validator ownership and sealed fake Provider checkpoint;
- READY evidence gate;
- pointer CAS, unique successor, fencing and append-only activation records;
- post-commit alias reconciliation;
- leased ReadViews, drain, Reaper and retirement reconciliation;
- Tombstone, Inbox/Outbox and scoped deletion evidence;
- rollback eligibility and ABA tests.

Primary artifacts:

- [Executable example](../../projects/ai-agent/examples/day104_index_lifecycle.py)
- [Saved evidence report](../../projects/ai-agent/evidence/day104-index-lifecycle-report.json)
- [Evidence replay](../../projects/ai-agent/evals/run_day104_evidence_replay.py)
- [Seed evaluator](../../projects/ai-agent/evals/run_day104_seed_eval.py)
- [L3 integration evidence](../../projects/ai-agent/evidence/day104-l3-integration-report.json)
- [Offline L3 evidence replay](../../projects/ai-agent/evals/run_day104_l3_evidence_replay.py)
- [L3 evidence boundary](../../projects/ai-agent/docs/DAY104_L3_REAL_PGVECTOR_INTEGRATION.md)

From `projects/ai-agent/`, the validation entry points are:

```sh
PYTHONPATH=src:. python3.12 -m unittest discover \
  -s tests -p 'test_day104_*.py' -v
PYTHONPATH=src:. python3.12 evals/run_day104_seed_eval.py
PYTHONPATH=src:. python3.12 evals/run_day104_evidence_replay.py
PYTHONPATH=src:. python3.12 evals/run_day104_l3_evidence_replay.py
PYTHONPATH=src:. python3.12 examples/day104_index_lifecycle.py
```

L2 is `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`. It proves deterministic
mechanics, not real infrastructure behavior.

### Real PostgreSQL/pgvector L3 integration

The opt-in L3 run kept the same A/B/C corpus, D1 Tombstone and Q1/Q2/Q3 ruler.
On PostgreSQL 16.15 with pgvector 0.8.7, 32/32 PostgreSQL adapter unit tests,
7/7 real integration tests and 17/17 runner gates passed. The executed paths
include repeatable-read BuildSnapshot stability, two-connection pointer CAS,
activation transaction rollback, lease fencing, sealed-generation immutability,
exact Manifest read-back, a real HNSW plan, single-Generation ReadViews,
drain/retirement, durable Inbox/Outbox replay, deletion non-resurrection and
container restart replay.

The saved report is content-safe: it records identities, digests, decisions and
plan evidence, not a DSN, password, raw policy text or raw vector. CI runs only
the offline saved-evidence replay; it does not start Docker. This is local L3
evidence, not L4 production evidence.

## 15. Today's Takeaway

The durable mental model is: truth stays in application-owned source, authorization and deletion stores; every
index Generation is a sealed, replaceable view. A Generation becomes eligible only after independent integrity
and Day103 quality evidence, and becomes visible only through a revisioned application pointer CAS. Request
pinning protects consistency but never overrides current authorization. Rollback is a policy decision, not merely
an available alias operation. Level 2 proves deterministic mechanics; the
separate Level 3 report proves the recorded local PostgreSQL/pgvector paths only.

## 16. Before Next Lesson Checklist

- [ ] I can explain why source truth is never rewritten to match an index.
- [ ] I can write `BS = S + P + E + IS + W + D` without notes.
- [ ] I can distinguish generation identity from pointer revision.
- [ ] I can explain why ACKs cannot replace authoritative read-back.
- [ ] I can name all Manifest comparison fields.
- [ ] I can distinguish `FAIL` from `INCONCLUSIVE`.
- [ ] I can state the atomic activation transaction.
- [ ] I can explain why Provider alias projection occurs after commit.
- [ ] I can explain ReadView lease, fence, drain and retirement.
- [ ] I can prevent a Tombstone from disappearing during rebuild.
- [ ] I can distinguish logical release, serving absence and physical purge.
- [ ] I can determine whether an old Generation is rollback-eligible.
- [ ] I can explain ABA prevention using monotonic revision.
- [ ] I can state exactly what L2 does and does not prove.
- [ ] I can state exactly what local L3 proves and why it is not L4.

The following remain `NOT_RUN`:

- Python 3.12 pull-request CI;
- PostgreSQL HA, replica failover, restore drills and cross-region recovery;
- durable broker relay, distributed multi-process Worker recovery, clock skew
  and network partition;
- physical purge across Provider storage, caches and retained backups;
- production-size ANN recall, latency, capacity, cost, error-rate and soak gates;
- canary/blue-green deployment, real traffic and zero-downtime proof;
- production incident response and observation window.

Therefore local L3 integration is `PASS`, L4 production evidence is `NOT_RUN`,
and production readiness remains `MORE_EVIDENCE_NEEDED`. Advancing to L4
requires separately authorized production deployment, traffic, HA/restore and
physical-purge drills, load evidence and an adequate observation window.
