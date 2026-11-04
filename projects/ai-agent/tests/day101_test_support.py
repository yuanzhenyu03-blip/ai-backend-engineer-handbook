from __future__ import annotations

from examples.day101_query_rewriting_reranking import day101_request
from rag_multi_query_fusion import MultiQueryCandidatePool, fuse_multi_query_results


def build_intermediate(fixture):
    request = day101_request(fixture)
    original = fixture.pipeline._original_query(request)
    rewrite_set = fixture.pipeline.rewriter.rewrite(original)
    retrieval = fixture.pipeline.multi_query.execute(
        base_request=request, rewrite_set=rewrite_set
    )
    pool = fuse_multi_query_results(
        retrieval, fixture.pipeline.fusion_policy
    )
    current = fixture.currentness.recheck(
        candidates=pool.candidates, request=request
    )
    current_pool = MultiQueryCandidatePool(
        pool.rewrite_set_fingerprint,
        pool.fusion_policy_fingerprint,
        tuple(item.candidate for item in current.accepted),
        pool.truncated,
    )
    rerank_request = fixture.pipeline.input_builder.build(
        original_query_digest=original.query_digest,
        protected_query=original.protected_text,
        pool=current_pool,
    )
    return request, original, rewrite_set, retrieval, current_pool, rerank_request
