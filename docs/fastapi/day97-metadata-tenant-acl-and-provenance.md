# Day 97 — Metadata, Tenant, ACL and Provenance

## 1. Lesson Metadata

- Phase: 7C — Production RAG Engineering.
- Prerequisites: Day95 active immutable `DocumentVersion`/`ParsedArtifact`; Day96 committed current selected
  `ChunkSet` with exact source spans; Day92 minimized `AuthenticatedPrincipal`.
- Evidence: dependency-free, deterministic in-process implementation on synthetic data.
- Execution evidence: `EXECUTED_LOCAL_RUNTIME`.
- Production readiness: `MORE_EVIDENCE_NEEDED`.
- Scope boundary: no embedding, vector index, retrieval, answer generation, citation rendering, production
  policy engine, PostgreSQL RLS, OIDC deployment, or customer data.

## 2. Learning Objectives

By the end of Day97, the learner can:

1. distinguish authentication, tenant membership, ACL/grant, decision, permit, enforcement, metadata and
   provenance;
2. admit only the current Day95/Day96 lineage and reject stale, unselected or incomplete evidence;
3. keep untrusted descriptive metadata from creating authorization facts;
4. evaluate `ALLOW`, `DENY` and `INDETERMINATE` with default-deny and deny-overrides semantics;
5. issue a short, signed permit bound to principal, tenant, resource, action, audience, purpose and revisions;
6. revalidate epoch, revisions, document fence and selected pointer at the PEP before releasing Chunk text;
7. update metadata snapshots without re-ingestion/re-chunking and update ACLs without changing ChunkSet;
8. hand Day98 only provenance-preserving input authorized for `chunk:read_for_embedding`.

## 3. Why This Matters

A RAG pipeline can parse and chunk perfectly and still disclose another customer's text. `tenant_id` is an
isolation attribute, not proof that a principal has a current grant. A selected pointer proves which ChunkSet
is current, not who may read it. Provenance proves where content came from, not whether access is allowed.

Day97 adds the missing security boundary between “these are the current chunks” and “this exact principal may
receive these exact protected bytes for this exact purpose.” It also preserves an audit trail when mutable ACL
or policy state changes without rewriting immutable source lineage.

## 4. Roadmap Position

```text
Day92 verified principal and authorization vocabulary
    +
Day95 SourceArtifact → active DocumentVersion → ParsedArtifact
    +
Day96 immutable selected ChunkSet → exact Chunk source spans
    ↓
Day97 metadata contract + current ACL + provenance + narrow permit + guarded read
    ↓
Day98 authorized embedding input and model/version contract
    ↓
Day99 index; Day100 retrieval; Day102 citations; Day103 evaluation
```

Day97 reuses existing identity and lifecycle truth. It does not recreate authentication, ingestion, chunking,
operation identity, retry, selected-pointer, or Committer authority.

## 5. Lesson Map

```text
AuthenticatedPrincipal
→ PIP rereads current membership, ACL/policy, epoch/revisions and Day95/Day96 lineage
→ PDP compares facts with PAP-published versioned rules
→ DENY / INDETERMINATE: no permit, no protected text
→ ALLOW: trusted PermitIssuer signs a narrow, short-lived permit
→ PEP revalidates signature + subject + audience + action + expiry + revisions + epoch
→ GuardedChunkReader exposes only bound chunks
→ content-safe audit evidence
→ Day98 authorized embedding-input handoff
```

The parallel metadata path is:

```text
trusted system/derived facts + untrusted source declarations
→ candidate
→ namespace/origin/type/sensitivity/authority-field validation
→ sole MetadataCommitter CAS
→ immutable MetadataSnapshot + current pointer + Outbox intent
```

## 6. Core Mental Model

Think of a secure archive:

- authentication checks the visitor's verified identity;
- membership says which organization the visitor currently belongs to;
- PAP publishes the rulebook; PIP fetches current facts; PDP makes the decision;
- the PermitIssuer prints a signed, short-lived ticket for one door and purpose;
- the PEP is the guard at that door and checks the ticket against the live revocation board;
- `GuardedChunkReader` opens only the labeled drawer;
- provenance is the chain-of-custody card attached to the document;
- metadata is the catalog description, not a key to the archive.

Durable memory:

```text
identity ≠ membership ≠ grant ≠ permit
metadata ≠ authority
provenance ≠ authorization
selected pointer ≠ permit
```

## 7. Main Concepts

### Concept 1: Current eligibility and exact lineage

#### Tech Lead Question

Can an embedding worker trust a Day96 Outbox notification that names `tenant-a` and selected ChunkSet B?

#### Student Thinking and Answer

The learner correctly rejected tenant equality and Outbox delivery as permission. The durable current state
must be reread, including active version, selected pointer and exact provenance.

#### Tech Lead Review

`CurrentRAGProvenanceValidator` accepts only an ACTIVE Day95 head whose active pointer matches the immutable
version, whose ingestion completed, whose source/parsed checksums bind, and whose committed Day96 selection
matches the same version and ChunkSet. The validator verifies the ChunkSet manifest, every Chunk content hash
and exact canonical source-span coordinates. Candidate IDs, guessed IDs and stale selections fail closed.

Repeated text keeps distinct `chunk_id` and source occurrences even when content hashes match. Content
deduplication may share internal bytes, but it must never merge tenant ACL, provenance or deletion state.

#### Exercise

Remove the SourceArtifact binding or change the selected revision. The protected reader must release zero
chunks.

### Concept 2: Metadata describes; trusted authority grants

#### Tech Lead Question

May document front matter declare `owner=attacker` or `acl=allow` and become authoritative after validation?

#### Student Thinking and Answer

The initial English answer gave `MetadataValidator` too much power. The corrected model is that validation and
commit can admit descriptive facts but cannot manufacture authority.

#### Tech Lead Review

Each application-owned field definition binds namespace, type, allowed origin, sensitivity and filterability.
Source-declared metadata remains an untrusted declaration. Authority-bearing leaf names such as `acl`,
`grant`, `role`, `membership`, `owner` and `tenant_id` are rejected. Unknown fields and wrong types fail closed.

`MetadataProjector` creates only a candidate. `MetadataCandidateValidator` is pure. The sole
`MetadataCommitter` claims the operation and rechecks current Day95/Day96 guards before atomically appending an
immutable snapshot, moving its pointer and inserting an Outbox intent. A contract change creates a new
snapshot; old history remains. It creates neither a `DocumentVersion` nor a `ChunkSet`.

#### Exercise

Submit `source.acl=allow attacker`; verify `AUTHORITY_FIELD_REJECTED` and zero durable transition.

### Concept 3: PAP, PIP, PDP, PermitIssuer and PEP

#### Tech Lead Question

Which component provides facts, which decides, and which actually blocks the text?

#### Student Thinking and Answer

The learner's final model was correct: PIP supplies facts; PDP compares them with PAP rules; PermitIssuer signs
after ALLOW; PEP executes and revalidates; GuardedChunkReader controls the minimal content exit.

#### Tech Lead Review

- PAP is represented by the trusted, versioned action catalog, ACL and policy snapshot.
- PIP reads current membership, policy/ACL, epoch, revisions and provenance. It makes no decision.
- PDP uses default deny. Any applicable explicit deny wins over allow. An unavailable policy dependency is
  `INDETERMINATE`, not permanent `DENY`.
- PermitIssuer consumes only a complete ALLOW decision. The classroom HMAC demonstrates tamper detection, not
  production key custody or rotation.
- PEP owns enforcement. It never reinterprets a raw credential or accepts the permit as permanent truth.

Same tenant with no applicable grant is denied. A service principal needs an exact
`chunk:read_for_embedding` grant; ordinary `chunk.text.read` does not imply it.

#### Exercise

Give a same-tenant member no grant and a worker only the embedding action. Confirm the member and the worker's
unrelated action are both denied.

### Concept 4: Narrow permit and revocation

#### Tech Lead Question

What makes a permit narrow, and how does a grant revocation invalidate it immediately?

#### Student Thinking and Answer

The learner named service identity, exact chunks, exact action and audience, then added tenant, purpose,
issuer, expiry, epoch and revisions.

#### Tech Lead Review

The signed claims bind:

```text
issuer + subject + tenant + audience + purpose + action
+ DocumentVersion + ChunkSet + exact Chunk IDs
+ policy/ACL/membership/role/action-catalog revisions
+ authorization_epoch
+ selected-pointer revision + document state version/fence
+ issued_at + expires_at + one-time permit_id
```

Revoking a grant increments the relevant ACL revision and resource `authorization_epoch`. Cached decisions
are keyed by all relevant bindings/revisions and contain decision evidence only, never a reusable permit.
Existing permits then fail the PEP comparison. ACL changes do not re-ingest or re-chunk content.

#### Exercise

Authorize the embedding worker, revoke its grant, and try the old permit. Expect zero text and
`PERMIT_AUTHORIZATION_REVISION_MISMATCH`.

### Concept 5: TOCTOU, safe denial and observability

#### Tech Lead Question

What if policy, active version or selected pointer changes after the PDP returned ALLOW?

#### Student Thinking and Answer

The learner correctly required the PEP to revalidate permit, epoch and revisions immediately before release.

#### Tech Lead Review

The guarded reader verifies signature/context/expiry, rereads current lineage and current authorization state,
compares every revision/fence, atomically consumes the one-time permit and only then materializes the minimal
Chunk views. Any stale or unavailable fact fails closed. Unauthorized and nonexistent resources use the same
external `404` message; authorization-state outage uses external `503` with internal
`AUTHORIZATION_STATE_UNAVAILABLE`.

Audit events retain decision ID, hashed permit/principal identifiers, action, outcome, content-safe reason and
count. Raw credential, Chunk text, protected title/tag/source URI and high-cardinality IDs do not become metric
labels. Detailed IDs belong only in protected logs/traces after field-level redaction.

#### Exercise

Change selection revision after permit issuance. Confirm the read is denied and that audit evidence contains no
Chunk text.

### Concept 6: Concurrency, idempotency and delayed notifications

#### Tech Lead Question

How do two metadata writers and at-least-once Outbox delivery converge?

#### Student Thinking and Answer

The learner chose a stable idempotency key plus CAS; the losing writer converges to the winner. A delayed event
is only a wake-up hint and must not roll the pointer backwards.

#### Tech Lead Review

The in-process Committer models one claim owner, attempt generation/fence, stable operation identity and pointer
baseline. Exact duplicate persistence returns the existing snapshot. Same operation plus changed contract is an
identity conflict. Two writes against one pointer baseline yield one transition. The Outbox consumer rereads the
current pointer: duplicate current delivery is absorbed; delayed old delivery is `STALE` and has no effect.

This proves application control flow, not distributed database isolation, multi-process fencing or crash
recovery.

#### Exercise

Race two threads on one validated snapshot and then deliver the first snapshot event after v2 is current.

## 8. Common Misconceptions

- **Same tenant means access.** No. Tenant match is necessary isolation context; current membership and an
  applicable exact-action grant are still required.
- **Selected ChunkSet means permitted.** No. Selection is a data-lifecycle fact.
- **Complete provenance means readable.** No. It proves lineage only.
- **Metadata can grant itself authority.** No. Source and parser output are untrusted data.
- **A vector metadata filter is the ACL.** No. It is only future prefilter/defense in depth; authoritative
  post-check remains mandatory.
- **RLS replaces application authorization.** No. RLS is an additional database boundary.
- **`INDETERMINATE` is `DENY`.** Both release zero text, but outage uncertainty must remain distinguishable
  internally and normally maps to `503`.
- **A content hash is global identity.** No. Cross-tenant equality may itself leak information and cannot merge
  authorization/provenance/deletion state.
- **ACL change requires new ChunkSet.** No. Mutable authorization and immutable content lineage are separate.
- **Permit is a bearer capability.** Not here: it is signed, short-lived, context-bound and one-time.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost / remaining risk |
|---|---|---|
| Default deny + deny overrides | Prevents accidental privilege | More explicit grant administration |
| PEP live recheck | Fast revocation and TOCTOU protection | Extra state reads and latency |
| Short one-time permits | Limits replay/blast radius | More issuance and retry coordination |
| Immutable metadata snapshots | Audit/replay clarity | Additional storage and pointer management |
| Revision-bound decision cache | Avoids repeated PDP work | Still requires current revision lookup |
| Generic denial | Resists enumeration | Less client-visible diagnostic detail |
| Exact provenance occurrences | Correct deletion/citation/audit | Cannot collapse logical records by hash |
| In-memory classroom stores | Deterministic and dependency-free | No distributed consistency/durability proof |

## 10. Hands-on Exercises

Run the deterministic example, seed and focused tests:

```bash
PYTHONPATH=projects/ai-agent/src:projects/ai-agent python3 \
  projects/ai-agent/examples/day97_authorized_chunk_access.py
PYTHONPATH=projects/ai-agent/src:projects/ai-agent python3 \
  projects/ai-agent/evals/run_day97_seed_eval.py
PYTHONPATH=projects/ai-agent/src:projects/ai-agent python3 -m unittest discover \
  -s projects/ai-agent/tests -p 'test_day97_*.py' -v
```

The tests cover current eligibility, incomplete lineage, repeated text, metadata authority rejection, immutable
snapshot/CAS/Outbox behavior, tenant isolation, ACL conflict semantics, service actions, outage, signed permit
bindings, expiry/replay/revocation, revision/epoch/pointer/fence TOCTOU, content-safe audit and Day98 handoff.

Evidence:

- [application contract](../../projects/ai-agent/docs/DAY97_METADATA_TENANT_ACL_PROVENANCE.md)
- [seed matrix](../../projects/ai-agent/evals/day97_metadata_acl_provenance_seed.jsonl)
- [validation record](../../projects/ai-agent/evidence/day97-validation.json)
- [Day98 handoff](../../projects/ai-agent/docs/DAY97_TO_DAY98_HANDOFF.md)

## 11. Relevant Framework Connections

OPA, Cedar or OpenFGA could sit behind an Adapter and return policy decisions/facts. They do not own the
application's `AuthenticatedPrincipal`, immutable resource identity, durable metadata truth, permit format or
protected-text exit. PostgreSQL RLS may block rows as defense in depth. A vector database filter may reduce
candidates. Neither replaces the application PDP/PEP contract or per-result authoritative post-check.

The current lesson deliberately uses no policy framework, database, vector store or model Provider. That keeps
the policy semantics observable and prevents framework-private types from becoming authority.

## 12. AI Backend Connections

For Day98, an embedding worker is a service principal, not a trusted internal bypass. It must obtain
`chunk:read_for_embedding`, and the handoff retains tenant/document/version/ChunkSet/Chunk identity, exact
source spans, protected-data classification, decision ID, authorization revisions and epoch. Vectors remain
derived protected data; they do not become public because they are not plain text.

Future retrieval must prefilter for efficiency and post-check each result authoritatively. Pagination scans
additional candidates until the requested number of authorized results is filled; it must not expose rejected
counts or candidate existence.

## 13. English Interview

### Key vocabulary

`authentication`, `authorization`, `principal`, `membership`, `grant`, `ACL`, `provenance`, `authority`,
`permit`, `issuer`, `audience`, `purpose`, `revocation`, `epoch`, `revision`, `fail closed`, `deny overrides`.

### Useful expressions

- “Authentication verifies identity; authorization determines allowed actions on a resource.”
- “A matching tenant ID does not prove a current resource/action grant.”
- “Provenance proves lineage, not permission.”
- “The PEP revalidates the permit and current revisions immediately before release.”

### Beginner question

Why is a selected `ChunkSet` not an authorization permit?

### Intermediate question

What happens to cached authorization evidence and existing permits after an ACL revision or epoch changes?

### Senior question

Design the boundary from authenticated principal through PIP/PDP/PermitIssuer/PEP to guarded Chunk release.

### Common weak answer

“The worker and ChunkSet share a tenant, so the worker may read it.” This omits current membership, exact action
grant, provenance, revisions, issuer binding and final enforcement.

### Strong answer

“PIP loads current membership, policy/ACL, epoch/revisions and current lineage. PDP compares those facts with
PAP rules. ALLOW permits a trusted issuer to sign a narrow credential. PEP verifies signature, context, expiry,
epoch, revisions, active version and selected pointer before GuardedChunkReader releases only bound chunks.
Any deny, uncertainty or stale fact releases nothing.”

The learner completed the interview with technical and language corrections. Direct teaching was required for
metadata-versus-authority, ACL inheritance, missing production evidence and the final senior synthesis; this is
recorded rather than presented as an independent fluent senior-English performance.

## 14. Mental Model Summary

```text
PAP publishes versioned rules
PIP supplies current facts
PDP decides ALLOW / DENY / INDETERMINATE
PermitIssuer signs only complete ALLOW
PEP enforces and rechecks current state
GuardedChunkReader releases minimal text

grant revoked
→ ACL revision + authorization_epoch advance
→ old cache key misses
→ old permit revision mismatch
→ PEP denies
```

Immutable lineage and mutable authorization remain separate. Decision evidence records the exact versions of
both that were used.

## 15. Today's Takeaway

Day95 and Day96 prove what the current content is. Day97 proves who may use it, for which exact action and
purpose, under which current rules, while retaining where it came from. No single tenant field, pointer, hash,
notification, metadata tag, database credential or vector filter may bypass that chain.

## 16. Before Next Lesson Checklist

- [x] Current Day95 active version and Day96 selected committed ChunkSet are reread.
- [x] Metadata namespace/type/origin/sensitivity and untrusted-source boundary are explicit.
- [x] Immutable snapshots and sole-Committer CAS/outbox model are tested.
- [x] Same-tenant without grant and cross-tenant guessed resources are denied safely.
- [x] Default deny, deny-overrides, service exact action and three-state decisions are tested.
- [x] Permit binds exact context, expiry, revisions, epoch, pointer and fence.
- [x] PEP revalidation, revocation, replay and outage paths release zero protected text.
- [x] Complete provenance and repeated-text distinct occurrences are tested.
- [x] Content-safe audit and Day98 embedding handoff are implemented.
- [ ] Production OIDC/policy engine/key custody/RLS/distributed cache are integrated.
- [ ] Durable multi-process transactions, dispatcher/recovery, telemetry backend and load/soak are run.
- [ ] Day98 selects and versions a real embedding model without weakening Day97.

Production readiness remains `MORE_EVIDENCE_NEEDED`.
