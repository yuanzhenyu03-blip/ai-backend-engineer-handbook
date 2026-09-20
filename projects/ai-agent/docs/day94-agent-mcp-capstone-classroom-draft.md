# Day94 Classroom Draft — Agent + MCP Integration Capstone

## Classroom outcome

The learner completed the capstone incident sequence, the Phase 7B English
Interview and an independent final synthesis. The synthesis passed with terminology
corrections. This draft records classroom understanding; it is not a published
formal lesson and does not authorize a repository update.

## Final reusable mental model

```text
proposal ≠ authorization ≠ execution ≠ durable success
```

- The model or Framework proposes.
- Application governance, human policy and current authorization decide whether an
  exact action may proceed.
- MCP transports an attempt and the Server handler produces only a candidate.
- Correlation and validation turn a candidate into a transition proposal.
- The sole Committer turns an eligible proposal into a durable fact.
- Recovery observes existing facts; it never invents a new operation or replays an
  unknown Tool call.

## Main incident learned

Given a persisted `DISPATCH_STARTED` marker and no trusted response after restart:

- the Recovery Coordinator may arrange an authoritative status query;
- the reconciliation components may produce typed observations and transition
  proposals but cannot replay the Tool or write business truth;
- only the Committer may perform the durable transition after rechecking current
  binding, state, version and fence.

The operation remains `PENDING_RECONCILIATION` while the authority says `UNKNOWN` or
`NOT_FOUND`. An eventually consistent status interface may temporarily return
`NOT_FOUND` before a completed remote write becomes visible. This observation cannot
be converted into `PROVEN_NOT_EXECUTED`.

## Checkpoints demonstrated by the learner

- retry policy runs only after authoritative non-execution has been durably
  established;
- exactly one worker wins a conditional dispatch claim;
- stale worker, stale generation and late response cannot commit;
- approval cannot replace current authorization;
- identity conflict stops before handler, Tool and Committer;
- reconnect uses a new generation and does not expand authority;
- telemetry is historical diagnostic context, not business authority;
- Framework-native state remains behind a replaceable Adapter;
- Agent success is exposed only after the durable Committer transition.

## Independent synthesis assessment

Correctly explained:

- application-owned stable identity and exact tenant/resource/Tool binding;
- separate approval and authorization decisions;
- preflight and durable dispatch marker before transport handoff;
- candidate → correlation → protocol validation → output validation → proposal →
  Committer;
- pending reconciliation after timeout and restart;
- authoritative status branches and retry only after committed non-execution;
- production identity, distributed correctness, failure and operational gaps.

Required corrections:

- include the controlled Tool/service call between the candidate-only handler and
  returned candidate result;
- distinguish Client and Server Adapter directions: private SDK types never cross
  into application core;
- authoritative success is not routed directly into a durable write; it must remain
  bound to the original operation and pass the required correlation/validation path;
- the Committer does not grant Tool execution permission and does not execute the
  Tool—it is the sole durable transition authority;
- restart begins with read-only recovery and reconciliation, never direct retry;
- `NOT_FOUND` is not `NOT_EXECUTED`;
- circuit breaking is the correct term, not “loop breaking”; alert delivery is the
  operational requirement.

## Phase 7B English Interview result

Result: `PASS_WITH_LANGUAGE_CORRECTIONS`

The learner progressed from component lists to evidence-based answers and explained:

- proposal versus authorization;
- MCP candidate result versus durable success;
- timeout versus non-execution;
- stable operation identity versus fresh attempt identity;
- approval composed with current authorization;
- authoritative reconciliation without replay;
- Committer placement and sole durable-write authority;
- observability as diagnostic output rather than authority;
- production-readiness evidence across identity, distributed failure and operations.

Language improvements to retain:

- say “the Committer is the sole durable transition authority,” not “the real
  executor”;
- say “observability must never be treated as authority”;
- prefer concrete terms such as `authority`, `evidence`, `candidate`, `proposal` and
  `durable fact` over vague words such as “real” or “true.”

## Completion boundary

Conceptual classroom assessment and English Interview are complete. Repository
publication, commit, push and PR remain forbidden until the learner explicitly says
“更新仓库”. `prompts/master-prompt.md` has not been read for this classroom phase.
