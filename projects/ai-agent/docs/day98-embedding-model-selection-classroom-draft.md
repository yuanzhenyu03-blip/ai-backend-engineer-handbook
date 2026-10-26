# Day98 Classroom Record — Embedding Model Selection and Versioning

## Classroom status

The guided classroom reached 100% conceptual coverage. This record preserves the learner's actual corrections
instead of presenting the result as independent production experience. The implementation and deterministic
fake were executed afterward; a real Provider/model and local retrieval-quality corpus were not run.

## Mental-model progression

The opening question was: after a model outputs an embedding vector, what happens next? The discussion moved
away from “store the vector” toward a controlled proposal/validation/commit workflow.

The learner repeatedly rejected unsafe shortcuts:

- Provider order cannot be trusted without exact correlation; every item needs a stable `chunk_id` mapping.
- Duplicate plus missing responses are not partially acceptable; the whole batch/operation must be rejected.
- Blind retry after an uncertain timeout can create a second side effect.
- Mixing vectors across contracts destroys the meaning of similarity.
- Silent truncation can remove the decisive tokens at the end of a Chunk.
- A weighted score cannot rescue a candidate that failed a hard gate.
- Public benchmarks cannot replace evidence from the system's own frozen corpus.
- Same dimensions do not mean the same vector space.
- ACL mutation does not rewrite content and therefore does not automatically require re-embedding.

The learner's final workflow was:

1. read exact action, principal, tenant, permit expiry and authorization scope;
2. freeze the EmbeddingContract;
3. preprocess;
4. build a deterministic batch plan;
5. send stable identities to the Provider;
6. validate the candidate;
7. recheck whether permission is still valid;
8. let the Committer create an immutable `EmbeddingSet`.

The tech-lead correction added the details needed for an implementation-grade boundary:

- tokenizer identity and preprocessing/input role are part of the contract;
- a stable operation is separate from a fresh attempt/request;
- Provider output is a candidate, never durable fact;
- precommit recheck covers all authorization revisions/epoch plus Day95/Day96 provenance and fences;
- one CAS winner atomically writes records, set, pointer and Outbox intent;
- model/preprocessing changes create a new set while old sets remain;
- Day99 receives metadata-only index input, not permission to retrieve.

## Detailed plain-language flow

```text
signed Day97 permission
  │
  ├─ wrong action / expired / wrong tenant / wrong scope ──> stop
  │
  └─ exact chunk:read_for_embedding
       │
       ├─ freeze model + tokenizer + preprocessing + role + token rules
       │  + dimensions/type/normalization + API/schema + batch + egress
       │
       ├─ count with the actual frozen tokenizer
       │    └─ one chunk too long ──> stop and return to Day96; do not cut it
       │
       ├─ make repeatable batches (split only between complete chunks)
       │
       ├─ stable operation + fresh attempt/request IDs
       │
       ├─ Provider returns a proposal
       │    ├─ timeout after send ──> UNKNOWN; reconcile, no blind retry
       │    └─ proven not sent ──> fresh attempt after bounded delay
       │
       ├─ validate every expected chunk exactly once
       │    └─ any missing/duplicate/unknown/partial/wrong/bad vector ──> reject all
       │
       ├─ reread current permission + provenance + fences
       │    └─ anything changed/unavailable ──> reject all
       │
       └─ sole Committer CAS
            ├─ loser converges/rejects
            └─ winner atomically creates records + set + pointer + outbox
```

## Assessment honesty

The learner demonstrated the decisive safety concepts through repeated negative answers and a correct final
eight-step synthesis. Direct teaching was still needed to name the full immutable contract, usage confidence,
exact retry/reconciliation states, atomic pointer/outbox consequences, and the Day99 boundary. English senior
interview fluency was not independently assessed. Production readiness is `MORE_EVIDENCE_NEEDED`.
