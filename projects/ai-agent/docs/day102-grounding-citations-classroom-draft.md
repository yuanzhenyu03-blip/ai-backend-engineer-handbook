# Day102 Classroom Record — Grounding, Citations and Source Verification

## Teaching mode

The original large-course opening was paused because the learner could name individual components but could not yet independently separate Day101 ranking from Day102 evidence. The lesson switched to a bridge-mastery mode with one fixed refund-policy scenario and one question per turn.

## Fixed scenario

```text
A: current 2026 policy — unopened items, 14-day refund window
B: superseded 2024 policy — 30-day refund window
C: current service manual — submit through online customer service
```

The same A/B/C objects were carried through authorization, ranking, Bundle construction, Claim extraction, Citation mapping, Verification and release.

## Learning progression

### Stage 1 — Day100 → Day101 → Day102 skeleton

The learner established:

```text
Authorization decides which sources may participate.
Query defines the relevance target.
Day101 returns ordered current candidates, not an answer.
Day102 verifies what can safely be said.
```

The key correction was that lexical/dense mechanisms still require a Query; they do not replace it. Query-digest change invalidates reuse but does not guarantee a different ranking order.

### Stage 2 — Day101 candidate, fusion and authority boundary

The learner correctly deduplicated one occurrence across query variants while preserving branch-rank evidence, rejected text-based deduplication across different source versions, enforced fusion output as a subset of the variant-result union, and removed revoked rank-one candidates without backfilling outsiders.

### Stage 3 — Day102 Claim/Evidence/Citation/Verification

The learner split a generated refund answer into atomic Claims, preserved modality such as “must,” mapped each Claim to exact evidence, distinguished Evidence content from Citation location, rejected valid pointers whose content did not support the Claim, and produced partial answers with explicit Abstention.

The repeated confusion between `REJECTED` and `Abstention` was resolved by direct teaching:

```text
REJECTED: an existing Claim/Citation artifact failed validation.
Abstention: a requested fact cannot be answered from current usable Evidence.
```

### Stage 4 — joint request and code mapping

The learner completed a closed-book Day100→Day102 trace, then mapped the mental model to:

```text
Contract
→ Orchestrator
→ Validator
→ Tests
```

The learner identified that `rank`, `reranker_score` and `FULL` are execution/ranking evidence, not source truth; a Day102 flow must freeze exact source windows, enforce egress, extract Claims, validate Bundle membership, independently verify support, recheck currentness and assemble only released Claims.

## Advanced production boundaries covered

- immutable Grounding Bundle and digest invalidation;
- Claim digest versus Evidence digest;
- Claim-level and Request-level Coverage;
- semantic contradiction versus source-unavailable failure;
- primary/fallback verifier state propagation;
- authority- and content-bound cache identities;
- source-as-data prompt-injection boundary;
- context planning for request facets instead of mechanical top-k;
- Day102→Day103 independent ground truth.

## English interview

The learner answered and corrected three questions:

1. why top-ranked authorized candidates are insufficient evidence;
2. valid Citation versus valid semantic support;
3. `REJECTED` versus `Abstention`.

Conceptual answers passed. English grammar still benefits from practice, but the technical model was stable before the interview began.

## Closed-book result

The learner correctly handled a final scenario where C was revoked after reranking:

- Day101 handed off `[A, B]`;
- A supported the 14-day/unopened Claim;
- B was excluded as a superseded source;
- submission channel became an abstained request item;
- the final response was a supported partial answer.

## Evidence boundary

This classroom record documents learner reasoning and the deterministic reference implementation. It does not upgrade real generator, extractor, verifier, protected egress, quality or production evidence. Those remain `NOT_RUN`; readiness remains `MORE_EVIDENCE_NEEDED`.
