# Day102 Grounding and Verification Approach Decision

## Decision

Use application-owned immutable Grounding Bundles, atomic Claim records, explicit Claim-to-Citation links and an independent replaceable verifier boundary. Provider-native citations may be adapted into this contract, but they do not become release authority.

## Compared approaches

| Approach | Strength | Main risk | Day102 position |
|---|---|---|---|
| Provider-native citations | Convenient structured pointers and cited text | Valid pointer can be mistaken for semantic support | Supported behind Adapter + Validator |
| Application-owned structured Claims + deterministic rules | Strong identity, replay and audit control | Rules alone have limited semantic coverage | Selected contract/control baseline |
| Cross-encoder NLI | Independent entailment/contradiction signal | Domain calibration and real quality evidence required | Replaceable verifier candidate; `NOT_RUN` |
| LLM-as-verifier | Flexible reasoning and explanations | Correlated model errors, prompt injection, cost and nondeterminism | Optional replaceable candidate; `NOT_RUN` |

## Release rule

```text
released Claim
requires
current authorized source
+ exact version/span identity
+ Citation inside the frozen Grounding Bundle
+ validated Claim/Evidence relation
+ final currentness recheck
```

Ranking, authorization, Citation syntax and schema validity are necessary inputs, not substitutes for semantic verification.

## Evidence honesty

The repository implementation uses deterministic fakes to prove contracts, control flow, identity binding, failure classification and release invariants. It does not prove real generator, Claim extractor, NLI/LLM verifier, protected-data egress, quality, latency, capacity, cost or production behavior. Readiness remains `MORE_EVIDENCE_NEEDED`.
