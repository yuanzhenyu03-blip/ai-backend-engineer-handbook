# Day80 Classroom Record — Tool Registry, Tool Schema and Permission Model

This record preserves the real classroom answers, mistakes, corrections and validation events. It is not a
polished replacement for the released lesson.

## Source binding and preflight

The class was bound to remote `main` commit:

`02dc0716cc87734d3f6e95821307f0ca64e09386`

Day80's exact Curriculum scope, Day79 Completed status, Day79 Artifact, Day74 Tool Contract, Day66 browser Tool
and `projects/ai-agent/README.md` were read before teaching. No GitHub update, commit or push happened during
class.

## Visibility, Schema and current Permission

For a registered but context-forbidden Tool, the student answered:

> 应该在发送给模型之前就被过滤掉

For a permission change after the original Snapshot:

> 必须使用调用时的最新可信权限事实重新检查

For a projected Schema that contained only the currently allowed Origin:

> 需要 Permission Model 和 Day66 server-authorized contract 再检查一次 Origin

For a v1 candidate after v1 was disabled while v2 was active:

> 必须拒绝当前候选

These answers established the core separation: registered is not visible; visible is not authorized; Schema
is not Authorization; a bound version is never silently substituted.

## Permission uncertainty correction

For a deny and a pre-execution policy `UNKNOWN`, the student initially answered:

> 应该拒绝，应该进入pending_reconciliation

The deny half was correct. The reconciliation half was wrong because no external execution existed. The class
corrected the model to `POLICY_UNAVAILABLE` and zero Tool calls. In the verification scenario with no
AdmittedToolCall and no dispatch marker, the student correctly selected:

> `WAIT`,等待tenant 授权正确

The class refined “等待授权正确” to waiting for a current verifiable ALLOW/DENY fact; a new human approval is
not always required.

## Existing boundary reuse

Asked whether Day80 should reimplement browser checks, the student answered:

> 交给已有的 Day66 permissioned browser tool 边界

The Artifact therefore uses Day74's public Schema validator and calls the real local Day66 proposal validation
function in two composition tests. Day80 only decides readiness to enter those boundaries.

## Accepted result and Framework boundary

Asked whether Day66 `ACCEPT_NEW` or `202 + task_id` could be treated as verified success, the student answered:

> 不能

Asked whether a Framework could auto-discover and expose an additional Schema-valid delete Tool, the student
again answered:

> 不能

The class added a Safe Tool Result projection gate and a Snapshot-only Framework translation function.

## Failure and rollback exercise

A bad Policy exposed `browser.delete_report@v1`. For a candidate with no Admission or dispatch evidence:

> 旧候选和旧 Snapshot 应保留审计记录，没有外部调用不用进入pending_reconciliatio

The completed answer also rejects the old candidate under current facts and builds a new safe Snapshot.

When the scenario changed to an admitted/dispatched request whose external outcome was unknown:

> pending_reconciliation,不能

Correct: preserve the original identity; rollback cannot rewrite it as “not executed” or authorize a new call.

## English Interview

Beginner answer:

> A tool being registered does not mean the model is visible. Model visibility merely indicates that the tool
> is a candidate, not that it is authorized; the model only becomes usable after authorization is granted.

Correction: authorization is still distinct from Admission, execution, Outcome Verification and Goal
completion.

Intermediate answer:

> The application should reject the request, and the controller makes the decision.

Correction: reject is correct. The Permission Model is the authority; Day80 applies its fact and the Day79
Controller chooses control flow.

Senior answer:

> Day 80: Control model visibility tools and re-examine candidates using the latest, authoritative permission
> facts. Day 74: Responsible for the general schema, authorization, admission, execution, and result
> verification. Day 66: Responsible for browser-specific aspects—Origin, session, approval, fingerprint, and
> persistence execution boundaries. Day 80 must not duplicate or overlook the checks performed on Day 66.

The boundary split was strong. The instructor added exact trusted inputs and a structured blocked-or-ready
return contract.

## Final synthesis

The student explicitly requested:

> 你帮我总结吧

The final Chinese Mental Model was therefore instructor-supplied and must not be presented as the student's
own authored summary. Its core equation was:

```text
Registered != Visible != Authorized != Admitted
!= Executed != Outcome Verified != Agent Goal Completed
```

## Artifact and validation history

Temporary classroom files became the released candidates:

- `src/tool_governance.py`
- `tests/test_day80_tool_governance.py`

Actual issues preserved:

1. Initial `python3` resolved to Python 3.9; discovery loaded 190 tests and import failed on newer union syntax.
2. Environment cleanup removed the first temporary clone; the exact SHA was re-cloned before continuing.
3. The disabled-v1 test first exercised permission revocation because its fixture granted only v2; the fixture
   was corrected to isolate lifecycle.
4. A Day66 test class initially inherited another test class and inflated the discovered count. Inheritance
   was removed before evidence was reported.
5. Publication review found missing role binding and a missing-catalog `StopIteration` path. Role was bound,
   missing catalog now fails closed, and duplicate catalog tests were added.

Final actual local results before repository status updates:

- 22 Day80 tests passed;
- 273 cumulative tests passed;
- no real Provider, Framework, HTTP, PostgreSQL, queue, Worker, Playwright, Integration Runtime or Production
  system ran.
