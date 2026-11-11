from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.day104_index_lifecycle import run_example  # noqa: E402
from rag_index_deletion_ledger import (  # noqa: E402
    DeletionLedgerCommitter,
    InMemoryDeletionLedger,
)
from rag_index_lifecycle_contracts import (  # noqa: E402
    GenerationManifest,
    ManifestFacts,
)
from rag_index_lifecycle_orchestrator import (  # noqa: E402
    DeterministicSealedIndexProvider,
    IndexedOccurrence,
)


SEED_PATH = ROOT / "evals" / "day104_index_lifecycle_seed.jsonl"


def _facts(
    occurrence_ids: tuple[str, ...] = ("A@v1", "C@v1"),
) -> ManifestFacts:
    return ManifestFacts(
        occurrence_ids=occurrence_ids,
        content_digest="sha256:content-v1",
        metadata_digest="sha256:metadata-v1",
        provenance_digest="sha256:provenance-v1",
    )


def _manifest_case(case_id: str) -> dict[str, object]:
    expected = _facts()
    if case_id == "exact-id-substitution":
        actual = _facts(("A@v1", "B@v1"))
    elif case_id == "content-drift":
        actual = replace(expected, content_digest="sha256:content-v2")
    elif case_id == "metadata-drift":
        actual = replace(expected, metadata_digest="sha256:metadata-v2")
    elif case_id == "provenance-drift":
        actual = replace(expected, provenance_digest="sha256:provenance-v2")
    elif case_id == "tombstone-resurrection":
        expected = _facts(("A@v1",))
        actual = _facts(("A@v1", "B@v1"))
    else:
        raise ValueError(f"unknown manifest seed case: {case_id}")
    return {
        "integrity_matches": GenerationManifest(
            expected,
            actual,
            expected_absent_occurrence_ids=("B@v1",),
        ).integrity_matches,
    }


def _provider_case() -> dict[str, object]:
    provider = DeterministicSealedIndexProvider()
    records = (
        IndexedOccurrence(
            "A@v1",
            "sha256:content-A",
            "sha256:metadata-A",
            "sha256:provenance-A",
        ),
    )
    written = provider.replace_generation(
        generation_id="G2",
        namespace="refund/G2",
        occurrences=records,
        fence=7,
    )
    assert written.checkpoint is not None
    provider.seal(
        generation_id="G2",
        expected_checkpoint=written.checkpoint,
        expected_fence=7,
    )
    late = provider.replace_generation(
        generation_id="G2",
        namespace="refund/G2",
        occurrences=records,
        fence=6,
    )
    return {"provider_outcome": late.outcome.value}


def _inbox_case(*, conflict: bool) -> dict[str, object]:
    committer = DeletionLedgerCommitter(InMemoryDeletionLedger())
    committer.consume(
        event_id="event-delete-B",
        payload_digest="sha256:delete-B",
        source_stream="delete-outbox",
        result_id="job-D1",
        result_digest="sha256:job-D1",
    )
    result = committer.consume(
        event_id="event-delete-B",
        payload_digest=("sha256:other" if conflict else "sha256:delete-B"),
        source_stream="delete-outbox",
        result_id="job-retry",
        result_digest="sha256:job-retry",
    )
    return {"inbox_outcome": result.outcome.value}


def _run_case(
    case_id: str,
    example: dict[str, object],
) -> dict[str, object]:
    if case_id == "normal-migration":
        pointer = example["active_pointer"]
        assert isinstance(pointer, dict)
        return {
            "activation_outcome": example["activation_outcome"],
            "active_generation": pointer["generation_id"],
            "pointer_revision": pointer["revision"],
            "retirement_outcome": example["retirement_outcome"],
        }
    if case_id in {
        "exact-id-substitution",
        "content-drift",
        "metadata-drift",
        "provenance-drift",
        "tombstone-resurrection",
    }:
        return _manifest_case(case_id)
    if case_id == "sealed-late-write":
        return _provider_case()
    if case_id == "inbox-exact-replay":
        return _inbox_case(conflict=False)
    if case_id == "inbox-payload-conflict":
        return _inbox_case(conflict=True)
    if case_id == "evidence-boundary":
        return {
            key: example[key]
            for key in (
                "physical_purge",
                "real_database",
                "real_vector_provider",
                "production_readiness",
            )
        }
    raise ValueError(f"unknown Day104 seed case: {case_id}")


def run() -> dict[str, object]:
    cases = tuple(
        json.loads(line)
        for line in SEED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    example = run_example()
    results = []
    for case in cases:
        case_id = str(case["case_id"])
        expected = dict(case["expected"])
        actual = _run_case(case_id, example)
        passed = all(actual.get(key) == value for key, value in expected.items())
        results.append(
            {
                "case_id": case_id,
                "passed": passed,
                "expected": expected,
                "actual": actual,
            }
        )
    return {
        "cases": len(results),
        "passed": sum(bool(item["passed"]) for item in results),
        "all_passed": all(bool(item["passed"]) for item in results),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
