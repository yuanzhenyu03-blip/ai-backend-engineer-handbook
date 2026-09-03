# Day83 Human Approval, Interrupt and Escalation — classroom Artifact v0.1

Status: completed at guided classroom scope; integrated into the repository, not production-ready.
Final Chinese synthesis was assistant-authored at the student's request; independent synthesis was not assessed.

## Provenance and boundaries

This design originated in an independent classroom archive and was integrated after the user explicitly
requested a repository update. Archive facts below describe that historical stage, not this Git checkout.
Current lesson: [Day83](../../../docs/fastapi/day83-human-approval-interrupt-and-escalation-boundaries.md).
Fresh update-time commands/results: [validation](../evidence/day83-repository-validation.json).

- Baseline: `e285adcc1573c91dcd9937e452e821c682efd4ff`, freshly verified as remote main on 2026-09-03.
- The earlier temporary clone had disappeared. A fresh public clone was obtained; its clean tracked files
  were exported with `git archive` into an independent, non-Git classroom directory.
- A byte comparison found no changed original tracked files. Existing prompts, lesson template, status
  documents and source files are unchanged. No remote writes, commit, push or PR occurred.
- That archive's original status documents still say Day83 Planned. They describe the fixed published
  baseline, not the new uncommitted classroom overlay. Do not mistake that for a new publication.
- Actual interpreter: Python 3.11.5. Repository-standard Python 3.12+ was not available on PATH;
  Python 3.12 validation is NOT RUN. No dependency installation was performed.

## Why this design

Approval is exact, time-limited human consent within current authorization, not a replacement for it.
Authentication establishes identity; authorization limits permitted actions; business validation checks
whether the target/action is valid; approval adds a required human decision. None substitutes for another.
Policy, identity and execution facts are application inputs, never derived from model claims, chat text,
email, callback correlation, UI click, n8n success, framework interrupt or Provider success alone.

The local model composes the Day82 Job/Checkpoint/Reservation/Outbox types and classified recovery.
It keeps frozen snapshots and uses one RLock-protected final snapshot swap. This models an atomic
conditional apply, but does not implement a database transaction, crash persistence or distributed locks.

```text
trusted application facts -> pure candidate
-> snapshot/identity/lifecycle/current-fact recheck
-> conditional local apply
-> state + Approval/Interrupt/Escalation + Checkpoint + Reservation + Audit + Outbox
-> separate local dispatch claim + current execution guards
-> existing Day78/Day74 local execution and verification
```

No external I/O occurs in apply. Candidate equality is recomputed from fresh trusted facts; a forged
execution-allowed result cannot bypass the guard. Replayed decisions add evidence only. Command identity
is separate from decision identity: a new gate after an earlier pending decision needs its own command.

## Approval

`ApprovalRequest` binds tenant, Job, Step, Attempt/planned operation, Tool name/version, normalized argument
fingerprint, Artifact identity/version, requester, policy identity/version, risk and execution bindings.
It also records request/response/expiry times, eligible roles, separation policy and issuance state/fence.
`ApprovalDecision` has a distinct identity, exact request/action fingerprint, actor, decision time and reason.
Current state/version/fence are rechecked at each apply; issuance versions are history, not a rule that any
legitimate later lifecycle update invalidates the same planned-operation approval.

Statuses: NOT_REQUIRED, PENDING, APPROVED, REJECTED, EXPIRED, REVOKED, SUPERSEDED, CANCELLED, CONFLICT.
High risk cannot silently become NOT_REQUIRED. Low-risk examples remain subject to ordinary authorization
and admission. The tool risk classification is injected by a trusted fixture; no production risk engine ran.

Same decision identity and identical content is duplicate-safe. Different content using the same identity
creates conflict evidence and escalation; the original decision is retained. A different decision identity
cannot overwrite the first decision either. Invalid cross-tenant/self/role callbacks cannot approve.
Request expiry is distinct from response-overdue escalation. Late decisions cannot revive cancelled requests.
Request creation is represented by a pre-bound initial store record plus notification intent; issuing and
replacing requests through a real authenticated API, and persistent successor-request creation, are NOT RUN.

## Interrupt and stale results

Pre-dispatch interrupt closes the path, releases proven-unused held units, revokes the local lease and
advances the fence. It retains history. Post-claim/dispatch interrupt conservatively retains original identity
and held capacity in PENDING_RECONCILIATION. Claim is marked before the local port call: interruption in the
claim-to-call gap is NOT treated as proof of no external effect.

Interrupt accepted != cancellation observed != execution stopped != external effect absent.
The observed-cancellation record is separate. Late results are retained by an evidence-only path; stale
fences cannot advance current business state. Results are references requiring subsequent verification.

The local effect is outside the human-control lock. No check-and-network-send atomicity is claimed.
Already-dispatched remote work may continue. Local thread claim tests are not cross-process Worker tests.
The existing Day82 lease takeover test is rerun as prerequisite regression; the new scenario exercises
interrupt revocation/fence advancement, not a real second Worker process.

## Escalation and accounting

Escalation records owner, reason, priority, deadline, alert status and evidence with source identities.
Unavailable owners use a permission-checked fallback. If no permitted owner exists, routing is UNROUTABLE
and execution stays closed. Alert delivery/acknowledgement and escalation closure are NOT implemented;
the model records an alert intent only and does not claim notification success or resolution.

Automatic recovery counters/limits/deadlines continue in the committed local history. New commands cannot
reset them. Query-intent creation consumes the local query allowance; actual external queries are NOT RUN.
Exhaustion stops new queries, creates escalation and preserves unknown/held facts. Verified accounting is
a separate permitted operation; it can settle even after query exhaustion without resetting that counter.
Duplicate settlement is a no-op; conflicting usage cannot overwrite prior settlement.

Terminal Job Goal state is independent of accounting/reconciliation: it remains terminal while unknown
accounting is reconciled or verified usage is settled. Compensation requires a new action/request identity
and applicable approval; actual compensation execution and its external reconciliation are NOT RUN.
The teaching accounting path assumes one units Reservation per Attempt and rejects ambiguous settlement.

## Runnable checkpoint and evaluation

Historical classroom commands below ran from the archive's `projects/ai-agent` directory.
The same relative commands work from this checkout's `projects/ai-agent`; the fresh evidence records its cwd:

```sh
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 -m unittest discover -s tests -p 'test_day83*.py' -v
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 -m unittest discover -s tests -v
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 evals/run_day83_seed_eval.py
PYTHONPATH=src /Users/yuanzhenyu/anaconda3/bin/python3.11 examples/day83_human_control_checkpoint.py
```

Final result: 53 Day83 tests (50 control tests + 3 grader tests), 378 cumulative tests (325 prior + 53),
26 version-1 seed cases PASS; example exits 0. Six new Python files passed py_compile.
The 325 prior tests were actually rerun, but are prerequisite regression coverage, not 325 new Day83 tests.

The example calls real existing local Day79 control, Day78 preparation, Day80 governance, Day81 guard/apply,
Day74 admission/execution/verification and Day82 recovery code. All service inputs and Tool effects remain
synthetic, in-process fixtures. The Day78 Provider-dispatch claim seeds fixture lifecycle only; no Provider
request is sent. The optional paid/real Provider Integration Gate remains NOT RUN and is not required.

Seed Eval means a small versioned scenario set; deterministic grader means fixed comparison rules rather
than an LLM judge. The runner performs exact comparison of five decision fields, required-evidence subset
checks, and observed forbidden-effect checks. Mixed rollback is one case with three items. Expectations
were authored from classroom rules before the first seed run and not changed to fit outputs. They are
reviewable teaching expectations, not an independently certified or complete production evaluation suite.
Several edge cases were assistant-authored; separate independent human review is still a release obligation.

Evidence files contain exact commands, exit codes, output, source SHA-256 hashes, Python version and failures:
[validation](../evidence/day83-validation.json), [intermediate run](../evidence/day83-intermediate-run.json).

## Actual failures and corrections

1. Old temporary clone unavailable; fresh download required. Sandbox DNS blocked public clone, then the
   approved network execution succeeded. This is environment recovery, not application crash proof.
2. First 45-test run: 1 failure. The synthetic outcome omitted Day74's required `warnings` property, so
   it was SCHEMA_INVALID. Added `warnings: []` to the fixture; expected VERIFIED and old Schema unchanged.
3. First integrated scenario: StopIteration after reusing command `gate-1`. The identity guard blocked
   the changed command, leaving no PUBLISH intent. Used a new gate identity and added regression coverage.
4. An explicit precommit injected exception is an expected scenario assertion: snapshot stays unchanged.

## Evidence honesty / NOT RUN

CONCEPTUAL + STATIC + EXECUTED_LOCAL_RUNTIME only. NOT RUN: Python 3.12; real human UI, callback ingress,
identity provider, authorization service, policy service; PostgreSQL, DB migrations, transactions and process
restart persistence; real Outbox Relay, Queue, Worker, cross-process interrupt/fencing; Provider, external
Tool/billing/compensation; alert delivery; production. Docker PostgreSQL was mentioned by the student but
not inspected, started, modified or used in this run. No secrets or credentials were requested or loaded.

The caller can construct fixture facts and mutate the test store; this module is not a secure HTTP API.
Production adapters must derive those facts from authenticated, tenant-scoped authoritative sources and
enforce database guards. In-memory storage, synthetic current-fact flags and successful tests do not prove
that real human decisions, business data validation or distributed transactions were verified.

## Classroom closeout

Beginner/Intermediate/Senior interviews and corrections are recorded in the adjacent classroom record.
The student requested an assistant-written final Chinese summary and then acknowledged it. Do not describe
that summary as an independent student answer, or infer independent mastery from guided corrections.
The unchanged master prompt was read for the standalone Repository Update Input. The subsequent user request
“帮我更新仓库” authorized local integration; the later “帮我更新远程GitHub仓库” authorized commit and push.
Day84 is the next connection, not started.
