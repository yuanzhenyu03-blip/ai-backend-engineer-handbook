# Day84 Engineering Design: Conversation Memory vs Durable Business-state Boundaries

## Scope and evidence

This is the bounded Day84 increment of the continuing `projects/ai-agent/` artifact.
It implements local, deterministic seams for context assembly, validated Tool-result
projection, compaction publication and rehydration. It does not implement a complete
memory service, RAG platform, prompt-injection defense system or multi-Agent runtime.

Evidence labels:

- `CONCEPTUAL`: production database, storage, queue and policy connections described here.
- `EXECUTED_LOCAL_RUNTIME`: Python 3.11.5, in-process stores, deterministic Fake estimator
  and Fake summarizer.
- `NOT RUN`: Python 3.12, real Provider/summarizer, PostgreSQL, object storage,
  Relay/Queue/Worker, external Tool, billing and production.

## Boundary model

```text
conversation events / memories / validated Tool views
                       |
                       v
scope + permission + provenance + version selection
                       |
                       v
context assembly -> context manifest -> Provider request candidate
                       |
            optional lossy compaction
                       |
                       v
summary candidate --conditional publish--> summary revision

rehydration
  -> use summary for continuity
  -> re-read current authoritative business records
  -> reuse Day83 guarded human-control decision
  -> dispatch only through existing business-state boundary
```

The context plane may propose model-visible representations. The control plane owns
Job, Attempt, Approval, Reservation, Outbox and verified external outcomes. No
`context_memory.py` memory or summary write API receives a business-state store.

## Memory selection

`MemoryRecord` carries memory identity/kind/version, exact scope, content, source
versions, expiry and revocation. `select_memories` checks exact scope, revocation,
expiry, source availability, current user access and source version before returning
content. Failed records produce typed omission reasons and never enter the model or
summarizer.

Only `EXPLICIT_PREFERENCE` may use `InMemoryMemoryStore.publish_preference`.
Model-inferred notes cannot use that write path. A write needs current scope,
authorization, expected revision and the next memory revision. The store is an
in-process demonstration of conditional behavior, not a durable database claim.

## Context assembly and capacity

`assemble_context` keeps required parts, then considers optional parts in policy
order. Every part carries its role, trust and source version. External data cannot
promote itself to application instruction by text. `ContextManifest` records chosen
and omitted IDs, selected versions, policy, estimator and required capacity; its
`grants_business_execution` value is always false.

```text
estimated model input
+ reserved output
+ safety margin
<= min(application limit, Provider/Profile limit)
```

The local `FakeTokenEstimator` is explicitly `FAKE_UTF8_BYTES_DIVIDED_BY_4`. It is
not a Provider-compatible token counter. Context capacity is independent of the
Day81/Day82 token and cost Reservation ledger.

## Bounded Tool-result view

`bound_validated_tool_result` accepts an already validated envelope. Its bounded view
preserves Tool call and operation IDs, result/source reference and version, status,
completeness, warnings, total/shown counts, original bytes and cursor. Truncation is
explicit. An empty excerpt never proves an empty source result.

`authorize_result_reference_read` checks current exact scope, expiry, source
availability, access and version. Every decision sets `replay_original_operation`
to false. A protected reference is a read route, not authority to repeat the Tool.

## Compaction

`SummarizerPort` permits a replaceable summarizer. Day84 runs only
`FakeSummarizer`; its modes make deterministic faithful, omitted-reference and false
approval cases. `validate_summary_draft` can check required references and reject a
next-step authority claim. It cannot establish general semantic fidelity.

`SummaryRevision` binds content to a scope-specific `SourceSpan`, event fingerprint,
context-policy version and summarizer identity. `InMemorySummaryStore.publish` checks:

1. exact scope;
2. current event head and source fingerprint;
3. expected previous summary revision;
4. next revision;
5. candidate idempotency.

A new event rejects an obsolete candidate. An injected failure before commit retains
the old revision. Replaying an already committed candidate returns `DUPLICATE`.

## Rehydration and current control facts

`rehydrate_with_current_human_control` ignores control claims in summary content and
delegates to Day83 `decide_human_control` using the current authoritative snapshot,
command and facts. If the snapshot is unavailable, it returns
`AUTHORITY_UNAVAILABLE`/`WAIT_FOR_AUTHORITY`. It never falls back to the summary.

Production integration must re-read and validate the current Job/Attempt/Step,
state/checkpoint versions, Approval and exact bindings, lease/fence, Reservation,
Outbox/dispatch marker, original operation/provider request ID and verified outcome.
The existing Day83 guarded apply remains the only business-state mutation path.

## Incident and rollback behavior

The affected set is determined from recorded provenance, not only a release-time
window. It includes policy/context/summary identities and the business execution
chain. Immediate containment quarantines the faulty policy, rejects new work under
it, invalidates unpublished candidates, blocks not-yet-called affected steps and
isolates already-dispatched Attempts without erasing evidence.

`classify_incident_attempt` implements the local A1/A2/A3 distinction:

| Evidence | Action | Reservation |
|---|---|---|
| confirmed no possible dispatch | release unused | release after proof |
| verified outcome and usage | settle verified | settle and release remainder |
| dispatch possible/outcome unknown | reconcile original | keep held |
| internally inconsistent evidence | block | retain for investigation |

An erroneous verified external effect requires a separate compensation lifecycle.
`may_close_context_incident` requires every modeled closure dimension; regression
success alone is insufficient.

## Validation commands

From `projects/ai-agent/`:

```bash
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 -m py_compile \
  src/context_memory.py tests/test_day84_context_memory.py \
  tests/test_day84_seed_grader.py evals/run_day84_seed_eval.py \
  examples/day84_context_memory_boundary.py
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 -m unittest discover \
  -s tests -p 'test_day84*.py' -v
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 -m unittest discover \
  -s tests -v
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 evals/run_day83_seed_eval.py
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 evals/run_day84_seed_eval.py
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 \
  examples/day84_context_memory_boundary.py
```

The final local results were 33 Day84 tests, 411 cumulative tests, 26/26 Day83
seed cases and 16/16 Day84 seed cases. The example exited zero and reported zero
Provider/external Tool calls. See `evidence/day84-validation.json` for source hashes,
environment, command outcomes and retained failed-attempt notes.

## Known limits

- In-memory locks and snapshots do not prove PostgreSQL transactional durability.
- Fake token estimates do not prove a Provider request fits a real model context.
- Structural summary checks do not prove semantic fidelity.
- Typed `ValidatedToolResult` marks the precondition; real Tool contract parsing and
  Outcome Verification remain the Day74 boundary.
- A result reference model does not implement object-storage authorization.
- Local reconciliation classification does not call a Provider status endpoint.
- The guided lesson is complete; the instructor authored the final synthesis, so
  independent final synthesis is `NOT ASSESSED`.
