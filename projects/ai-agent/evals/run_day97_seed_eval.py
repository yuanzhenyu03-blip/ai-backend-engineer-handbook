"""Data-driven Day97 authorization/provenance evaluator.

Reports contain only case identifiers, outcomes, and content-safe reason codes.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from examples.day97_authorized_chunk_access import build_fixture, request_for
from rag_acl_contracts import ACLEntry, AccessEffect
from rag_authorization import SignedPermit
from rag_ingestion_contracts import DocumentIdentity
from rag_metadata_contracts import (
    MetadataAssertion,
    MetadataOrigin,
    MetadataProjectionAttempt,
    MetadataProjectionOperation,
)
from rag_metadata_projection import MetadataProjector
from rag_metadata_validator import MetadataCandidateValidator


SEED_PATH = Path(__file__).with_name(
    "day97_metadata_acl_provenance_seed.jsonl"
)


def _authorize_case(item: dict[str, object]) -> tuple[str, str]:
    fixture = build_fixture()
    mutation = item.get("mutation")
    if mutation == "outage":
        fixture.authorization.set_available(False)
    elif mutation == "explicit-deny":
        policy = replace(
            fixture.policy,
            entries=fixture.policy.entries + (ACLEntry(
                "seed-explicit-deny",
                fixture.principals["viewer"].subject,
                fixture.resource.chunk(fixture.chunk_ids[0]),
                "chunk.text.read",
                AccessEffect.DENY,
            ),),
        )
        fixture.authorization.put_policy(policy)
    chunk_ids = (
        ("chunk:guessed",)
        if mutation == "unknown-chunk"
        else fixture.chunk_ids
    )
    result = fixture.service.authorize(request_for(
        fixture,
        str(item["principal"]),
        action=str(item.get("action", "chunk.text.read")),
        purpose=str(item.get("purpose", "interactive-rag-read")),
        chunk_ids=chunk_ids,
    ))
    return result.decision.outcome.value, result.decision.internal_reason_code


def _read_case(item: dict[str, object]) -> tuple[str, str]:
    fixture = build_fixture()
    principal_name = str(item["principal"])
    authorization = fixture.service.authorize(
        request_for(fixture, principal_name)
    )
    assert authorization.permit is not None
    permit = authorization.permit
    mutation = item.get("mutation")
    read_principal = fixture.principals[principal_name]
    if mutation == "expired":
        fixture.clock.value = permit.claims.expires_at
    elif mutation == "epoch":
        fixture.authorization.advance_authorization_epoch(
            tenant_id="tenant-a", document_id="report-42"
        )
    elif mutation == "selection":
        key = ("tenant-a", "report-42")
        with fixture.chunks._lock:
            fixture.chunks._selections[key] = replace(
                fixture.chunks._selections[key],
                revision=fixture.chunks._selections[key].revision + 1,
            )
    elif mutation == "document":
        identity = DocumentIdentity("tenant-a", "report-42")
        with fixture.day95._lock:
            current = fixture.day95.read_document(identity)
            fixture.day95._documents[("tenant-a", "report-42")] = replace(
                current,
                state_version=current.state_version + 1,
                fence_token=current.fence_token + 1,
            )
    elif mutation == "outage":
        fixture.authorization.set_available(False)
    elif mutation == "wrong-subject":
        read_principal = fixture.principals["viewer"]
    elif mutation == "tamper":
        permit = SignedPermit(permit.claims, "0" * len(permit.signature))
    if mutation == "replay":
        first = fixture.reader.read(
            permit=permit,
            principal=read_principal,
            expected_action="chunk.text.read",
            expected_audience="guarded-chunk-reader",
            expected_purpose="interactive-rag-read",
        )
        assert first.released
    result = fixture.reader.read(
        permit=permit,
        principal=read_principal,
        expected_action="chunk.text.read",
        expected_audience="guarded-chunk-reader",
        expected_purpose="interactive-rag-read",
    )
    return result.outcome.value, result.internal_reason_code


def _metadata_case(item: dict[str, object]) -> tuple[str, str]:
    fixture = build_fixture()
    current = fixture.provenance.evaluate(
        document=DocumentIdentity("tenant-a", "report-42")
    )
    assert current.binding is not None
    operation = MetadataProjectionOperation(
        current.binding.version,
        current.binding.chunk_set_id,
        "op-seed-metadata",
        "idem-seed-metadata",
        fixture.metadata_contract.fingerprint,
        current.binding.selection_revision,
        current.binding.document_state_version,
        current.binding.document_fence,
    )
    attempt = MetadataProjectionAttempt(operation.operation_id, 1, "r1", 1)
    assertion = (
        MetadataAssertion(
            "source.acl",
            "allow attacker",
            MetadataOrigin.SOURCE_DECLARED,
            "source:front-matter",
        )
        if item.get("mutation") == "source-acl"
        else MetadataAssertion(
            "unknown.field",
            "value",
            MetadataOrigin.SOURCE_DECLARED,
            "source:front-matter",
        )
    )
    candidate = MetadataProjector().project(
        operation=operation,
        attempt=attempt,
        assertions=(assertion,),
    )
    decision = MetadataCandidateValidator().evaluate(
        contract=fixture.metadata_contract,
        candidate=candidate,
    )
    return decision.outcome.value, decision.safe_reason


def _provenance_case(item: dict[str, object]) -> tuple[str, str]:
    repeated = item.get("mutation") == "repeated"
    fixture = build_fixture(
        "same text\nsame text" if repeated else "synthetic provenance fixture",
        soft_target_tokens=2 if repeated else 8,
        hard_max_tokens=2 if repeated else 12,
    )
    if item.get("mutation") == "gap":
        chunk_set = fixture.chunks.read_chunk_set(fixture.resource.chunk_set_id)
        assert chunk_set is not None
        with fixture.day95._lock:
            fixture.day95._source_artifacts.pop(
                chunk_set.operation.source_artifact_id
            )
    result = fixture.provenance.evaluate(
        document=DocumentIdentity("tenant-a", "report-42")
    )
    if repeated and result.valid:
        grouped: dict[str, int] = {}
        for record in result.records:
            grouped[record.chunk_content_hash] = (
                grouped.get(record.chunk_content_hash, 0) + 1
            )
        if max(grouped.values(), default=0) < 2:
            return "INVALID", "REPEATED_OCCURRENCE_NOT_PRESERVED"
    return result.outcome.value, result.safe_reason


def run(path: Path = SEED_PATH) -> dict[str, object]:
    cases = []
    handlers = {
        "authorize": _authorize_case,
        "read": _read_case,
        "metadata": _metadata_case,
        "provenance": _provenance_case,
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        outcome, reason = handlers[item["kind"]](item)
        cases.append({
            "case_id": item["case_id"],
            "passed": outcome == item["expected"],
            "outcome": outcome,
            "reason": reason,
        })
    return {
        "passed": sum(case["passed"] for case in cases),
        "total": len(cases),
        "cases": cases,
        "evidence_scope": "DAY97_DETERMINISTIC_AUTHORIZATION_PROVENANCE",
        "production_readiness": "MORE_EVIDENCE_NEEDED",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["passed"] != result["total"]:
        raise SystemExit(1)
