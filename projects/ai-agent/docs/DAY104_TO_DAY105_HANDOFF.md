# Day104 → Day105 Handoff

## Trusted index-lifecycle baseline

Day105 may consume a Generation only through the Day104 application-owned pointer and a request-scoped ReadView.
The minimum frozen identity is:

```text
GenerationArtifact
+ BuildSnapshot(S, P, E, IS, W, D)
+ GenerationManifest digest
+ Provider namespace/checkpoint/write fence
+ ValidationRecord digest
+ Day103 Evaluation Report checksum and evidence level
+ active pointer generation/revision
+ ReadView generation/revision/fence
```

The vector index remains derived state. Source, authorization and deletion stores remain authoritative.

## Required gates before retrieved content reaches Day105

- the Generation is the exact application-selected `ACTIVE` Generation for the pinned pointer revision;
- the ReadView is OPEN, unexpired and bound to the request owner;
- current authorization and provenance still permit the occurrence at release time;
- the occurrence belongs to the sealed Manifest and is not present in the frozen Tombstone set;
- no result from another Generation is spliced into the same request attempt;
- stale Provider aliases, duplicate events or old Worker results never override the application pointer;
- an unsafe rollback target cannot become active merely because its physical namespace still exists.

## Day105 ownership

Day104 proves lifecycle mechanics for a known corpus. Day105 owns content-origin and retrieved-instruction threats:

```text
document prompt injection
poisoned-document detection
retrieved-instruction isolation
cross-document attack chains
RAG-specific exfiltration controls
```

Day105 must not weaken Day104 identity, currentness, authorization, Tombstone or ReadView gates while adding those
content-security controls.

## Current evidence boundary

The handoff has two recorded layers:

- Level 2 policy mechanics:
  `EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE`;
- Level 3 local integration:
  `EXECUTED_LOCAL_DOCKER_INTEGRATION_POSTGRESQL_PGVECTOR`.

The [saved L3 report](../evidence/day104-l3-integration-report.json) records
PostgreSQL 16.15, pgvector 0.8.7, 32/32 adapter unit tests, 7/7 real
integration tests, 17/17 runner gates and a passing database-container restart
replay. The [offline replay](../evals/run_day104_l3_evidence_replay.py) validates
the saved, content-safe evidence without starting Docker.

PR #16 Python 3.12.16 CI run `42995652875` subsequently passed 1245 tests,
all 20 seed evaluators and all six saved evidence replays. Its append-only
record is [day104-pr16-ci-validation.json](../evidence/day104-pr16-ci-validation.json).
CI did not start Docker or re-execute the real PostgreSQL/pgvector L3 runtime.

`fixture_production_eligible=false`. Day105 may use this as a tested local
control-plane and retrieval baseline, but it must preserve the same frozen
identity and release gates. PostgreSQL HA/failover and restore,
multi-node/distributed failure behavior, physical purge, production-size
ANN/load, zero-downtime production migration and production traffic remain
`NOT_RUN` or `MORE_EVIDENCE_NEEDED`; readiness remains
`MORE_EVIDENCE_NEEDED`.
