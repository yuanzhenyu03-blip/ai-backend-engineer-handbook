# Day101 Classroom Record — Query Rewriting and Re-ranking

## Why the teaching format changed

The original large status block and terminology map left the learner “处于一种迷糊的状态.” The class switched to one fixed request and a repeated four-question method:

```text
input?
output?
owner?
what is absolutely forbidden?
```

The course then moved from a responsibility map, through one request, into failure drills and finally the real Day100 call chain.

## Mental-model evolution

### Initial model

The learner knew the first production action was not allowed but answered only “不能.” Rewrite was described as if it transformed retrieval results and then reran the pipeline.

### Correction

Rewrite output is a query variant. Different text may retrieve different occurrences, so every approved variant executes the same authorization-first Day100 boundary. “Rerun Day100” does not mean re-uploading, parsing, chunking, embedding or indexing.

### Final model

> “rewrite输出的是问题的变体……每个输出都需要经过相同的门禁和检索规则。重走day100不包括重新上传文档、切块、embedding、建立generation”

## Important learner answers preserved

- Candidate union: “使用occurrence_id进行去重同时保留各个候选在各分支中的排名……”
- Unknown output: “静默删除无法确定只是一个出问题，还是整体错位……”
- Final authorization: “授权撤销的hard gate要高于output policy.”
- External processing: “内部有权读取，不代表有权egress.”
- Evidence: deterministic tests prove bounded control flow and invariants, while baseline, quality and operational evidence remain missing.

## Important corrections preserved

- The Adapter translates Provider correlation; the Validator decides validity.
- Missing output is contract-dependent; duplicate candidate identity is never two candidates.
- `allow_lexical_only` is a policy switch; `DENSE_EGRESS_DENIED` is the observed reason.
- `rewrite_mode` is not the approved rewrite set.
- A valid reranker result followed by final authorization/provenance rejection is not a reranker validation failure.
- The learner's first instinct that `FULL` versus `PARTIAL` depends on the contract was correct. Current Day100 `FULL` means expected retrieval branches completed without declared system degradation; it does not guarantee exact top-k or zero guarded-release rejection.

## English interview completion

The learner completed three spoken answers with terminology corrections:

1. Rewrite may change only query expression; it never changes tenant, principal, purpose, filters, selected bundle or authorization scope.
2. A cursor continues one frozen retrieval result and must be rejected when bound identity changes.
3. Deterministic fake tests prove control-flow correctness, contract validation and safety invariants, not real model quality or production performance.

## Classroom evidence boundary

The teaching session used no customer query, document, secret, real rewrite Provider or real reranker. The committed code converts the learned invariants into deterministic tests. It does not claim Day103 quality evaluation or production readiness.
