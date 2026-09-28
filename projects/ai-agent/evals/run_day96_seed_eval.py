"""Data-driven Day96 seed evaluator with content-safe result reporting."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from examples.day96_active_fixture import active_day95_store
from rag_chunking_contracts import (
    ChunkStrategy,
    ChunkingAttemptIdentity,
    ChunkingContract,
    ChunkingOperationIdentity,
    OversizedPolicy,
    TokenizerContract,
)
from rag_chunking_experiments import ControlledChunkingExperimentRunner
from rag_chunking_strategies import ChunkingStrategyAdapter
from rag_chunking_validator import ChunkSetCandidateValidator
from rag_tokenizer_adapter import ClassroomTokenizer


SEED_PATH = Path(__file__).with_name("day96_chunking_seed.jsonl")


def run(path: Path = SEED_PATH) -> dict[str, object]:
    cases = []
    tokenizer = ClassroomTokenizer()
    runner = ControlledChunkingExperimentRunner(
        ChunkingStrategyAdapter(tokenizer),
        ChunkSetCandidateValidator(tokenizer),
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        case_id = item["case_id"]
        text = item["text"]
        day95, parsed = active_day95_store(text)
        source = day95.read_source_artifact(parsed.source_artifact_id)
        if source is None:
            raise AssertionError("seed source binding missing")
        base = ChunkingContract(
            strategy=ChunkStrategy(item["strategy"]),
            strategy_version="seed-v1",
            tokenizer=tokenizer.contract,
            normalization_version="identity-v1",
            soft_target_tokens=10,
            hard_max_tokens=12,
            min_useful_tokens=1,
            overlap_tokens=1,
            max_chunk_count=100,
            max_input_chars=1000,
            max_output_chars=2000,
            deadline_seconds=10.0,
            oversized_policy=OversizedPolicy.BOUNDED_FALLBACK,
        )
        overrides = dict(item.get("contract_overrides", {}))
        if "oversized_policy" in overrides:
            overrides["oversized_policy"] = OversizedPolicy(
                overrides["oversized_policy"]
            )
        if "tokenizer" in overrides:
            overrides["tokenizer"] = TokenizerContract(**overrides["tokenizer"])
        contract = replace(base, **overrides)
        operation = ChunkingOperationIdentity(
            parsed.version,
            parsed.source_artifact_id,
            parsed.parsed_artifact_id,
            "op-seed-" + case_id,
            "idem-seed-" + case_id,
            contract.fingerprint,
        )
        attempt = ChunkingAttemptIdentity(
            operation.operation_id, 1, "request-seed-" + case_id, 1
        )
        record = runner.run(
            document=day95.read_document(parsed.version.document),
            version=day95.read_version(parsed.version),
            ingestion=day95.read_operation(parsed.manifest.operation_id),
            parsed=parsed,
            source=source,
            contract=contract,
            operation=operation,
            attempt=attempt,
            experiment_id="exp-seed-" + case_id,
        )
        expected_status = item["expected_status"]
        expected_reason = item.get("expected_reason")
        passed = record.status == expected_status and (
            expected_reason is None or record.safe_reason == expected_reason
        )
        if record.status == "VALIDATED":
            metrics = record.metrics
            passed = passed and metrics is not None and (
                metrics.coverage_ratio == 1.0
                and metrics.gap_count == 0
                and metrics.oversized_chunk_count == 0
                and metrics.deterministic_rerun_match
            )
        cases.append({
            "case_id": case_id,
            "passed": bool(passed),
            "status": record.status,
            "reason": record.safe_reason,
        })
    return {
        "passed": sum(case["passed"] for case in cases),
        "total": len(cases),
        "cases": cases,
        "evidence_scope": "DAY96_DETERMINISTIC_SEED",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] != result["total"]:
        raise SystemExit(1)
