"""Dependency-free Day98 embedding workflow over synthetic authorized text."""

from __future__ import annotations

from dataclasses import dataclass
import json

from examples.day97_authorized_chunk_access import build_fixture, request_for
from rag_authorized_chunk_reader import AuthorizedEmbeddingInput
from rag_embedding_adapter import (
    DeterministicFakeEmbeddingAdapter,
    FakeResponseMode,
)
from rag_embedding_committer import EmbeddingCommitter, InMemoryEmbeddingStore
from rag_embedding_contracts import (
    BatchLimits,
    DeploymentKind,
    EgressPolicy,
    EmbeddingAttemptIdentity,
    EmbeddingContract,
    InputRole,
    ModelIdentity,
    NormalizationPolicy,
    NumericType,
    OverflowPolicy,
    TokenizerIdentity,
)
from rag_embedding_experiments import run_selection_experiment
from rag_embedding_orchestrator import (
    EmbeddingOrchestrator,
    EmbeddingRunRequest,
)
from rag_embedding_validator import EmbeddingCandidateValidator
from rag_tokenizer_adapter import ClassroomTokenizer


@dataclass(frozen=True)
class Day98Fixture:
    day97: object
    handoff: AuthorizedEmbeddingInput
    contract: EmbeddingContract
    adapter: DeterministicFakeEmbeddingAdapter
    store: InMemoryEmbeddingStore
    committer: EmbeddingCommitter
    orchestrator: EmbeddingOrchestrator


def classroom_contract(
    *,
    contract_version: str = "embedding-contract.v1",
    preprocessing_version: str = "prefix-only-v1",
    dimensions: int = 8,
    hard_max_tokens: int = 1_024,
    max_items: int = 2,
) -> EmbeddingContract:
    """Synthetic executable contract, deliberately not a real model claim."""

    return EmbeddingContract(
        contract_version=contract_version,
        model=ModelIdentity(
            "classroom-fake",
            "deterministic-hash-embedding",
            "sha256:day98-fake-revision-v1",
            DeploymentKind.SELF_HOSTED,
        ),
        tokenizer=TokenizerIdentity(
            "classroom-lexical",
            "1.0.0",
            "sha256:day96-classroom-tokenizer-v1",
        ),
        preprocessing_version=preprocessing_version,
        input_role=InputRole.DOCUMENT,
        input_prefix="document: ",
        hard_max_tokens=hard_max_tokens,
        overflow_policy=OverflowPolicy.REJECT,
        dimensions=dimensions,
        numeric_type=NumericType.FLOAT32,
        normalization=NormalizationPolicy.UNIT_L2,
        api_version="fake-port.v1",
        response_schema_version="embedding-response.v1",
        batch_limits=BatchLimits(max_items, 4_096, 64_000),
        egress=EgressPolicy(False, "local-only", "none", True),
    )


def authorized_handoff(day97: object) -> AuthorizedEmbeddingInput:
    authorization = day97.service.authorize(request_for(
        day97,
        "worker",
        action="chunk:read_for_embedding",
        purpose="day98-embedding",
    ))
    assert authorization.permit is not None
    read = day97.reader.read(
        permit=authorization.permit,
        principal=day97.principals["worker"],
        expected_action="chunk:read_for_embedding",
        expected_audience="guarded-chunk-reader",
        expected_purpose="day98-embedding",
    )
    return day97.reader.embedding_handoff(
        permit=authorization.permit,
        result=read,
    )


def build_day98_fixture(
    *,
    mode: FakeResponseMode = FakeResponseMode.NORMAL,
    contract: EmbeddingContract | None = None,
) -> Day98Fixture:
    day97 = build_fixture()
    handoff = authorized_handoff(day97)
    actual_contract = contract or classroom_contract()
    adapter = DeterministicFakeEmbeddingAdapter(mode)
    store = InMemoryEmbeddingStore()
    store.select_contract(handoff.tenant_id, actual_contract.fingerprint)
    committer = EmbeddingCommitter(
        store=store,
        authorization=day97.authorization,
        provenance=day97.provenance,
        clock=day97.clock,
    )
    orchestrator = EmbeddingOrchestrator(
        tokenizer=ClassroomTokenizer(),
        provider=adapter,
        validator=EmbeddingCandidateValidator(),
        committer=committer,
    )
    return Day98Fixture(
        day97,
        handoff,
        actual_contract,
        adapter,
        store,
        committer,
        orchestrator,
    )


def run_request(
    fixture: Day98Fixture,
    *,
    operation_id: str = "op-day98-classroom-v1",
    idempotency_key: str = "idem-day98-classroom-v1",
    attempt_number: int = 1,
    request_id: str = "request-day98-classroom-v1",
    generation: int = 1,
    expected_selected_id: str | None = None,
    expected_selection_revision: int = 0,
    expected_contract_selection_revision: int = 1,
):
    return fixture.orchestrator.run(EmbeddingRunRequest(
        handoff=fixture.handoff,
        contract=fixture.contract,
        operation_id=operation_id,
        idempotency_key=idempotency_key,
        attempt=EmbeddingAttemptIdentity(
            operation_id,
            attempt_number,
            request_id,
            generation,
        ),
        expected_selected_id=expected_selected_id,
        expected_selection_revision=expected_selection_revision,
        expected_contract_selection_revision=(
            expected_contract_selection_revision
        ),
    ))


def run_example() -> dict[str, object]:
    fixture = build_day98_fixture()
    result = run_request(fixture)
    assert result.commit is not None and result.commit.embedding_set is not None
    selection = run_selection_experiment()
    return {
        "workflow_outcome": result.outcome.value,
        "commit_outcome": result.commit.outcome.value,
        "safe_reason": result.safe_reason,
        "authorized_chunk_count": len(fixture.handoff.chunks),
        "deterministic_batch_count": result.validated_batch_count,
        "provider_request_count": len(fixture.adapter.observations),
        "provider_input_tokens": sum(
            item.input_tokens for item in fixture.adapter.observations
        ),
        "provider_input_utf8_bytes": sum(
            item.input_utf8_bytes for item in fixture.adapter.observations
        ),
        "provider_latency_ms": sum(
            item.latency_ms for item in fixture.adapter.observations
        ),
        "provider_cost_microunits": sum(
            item.cost_microunits for item in fixture.adapter.observations
        ),
        "provider_cost_confidence": "ESTIMATED",
        "embedding_record_count": len(result.commit.embedding_set.records),
        "contract_fingerprint": fixture.contract.fingerprint,
        "embedding_set_id": result.commit.embedding_set.embedding_set_id,
        "outbox_intent_count": len(fixture.store.outbox_intents()),
        "vectors_in_report": False,
        "selection_outcome": selection["outcome"],
        "provisional_real_model_candidate": selection["selected_candidate_id"],
        "real_provider_execution": "NOT_RUN",
        "real_local_retrieval_quality": "NOT_RUN",
        "execution_evidence": "EXECUTED_LOCAL_RUNTIME_WITH_DETERMINISTIC_FAKE",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
        "day99_handoff": "IMMUTABLE_EMBEDDING_SET_METADATA_ONLY",
    }


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2, sort_keys=True))
