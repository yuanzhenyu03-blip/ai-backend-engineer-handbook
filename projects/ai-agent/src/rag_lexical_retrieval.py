"""Dependency-free Day100 BM25 reference over authorized Chunk occurrences."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import math
import re

from rag_retrieval_contracts import (
    BranchCandidate,
    LexicalRetrievalContract,
    RetrievalAuthorizationScope,
    RetrievalBranch,
    RetrievalRecord,
    ScoreDirection,
    SelectedRetrievalBundle,
)
from rag_retrieval_filters import (
    FilterExpression,
    authorized_and_business_match,
)


class LexicalMode(str, Enum):
    NORMAL = "NORMAL"
    TIMEOUT = "TIMEOUT"


class LexicalRetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnalyzedDocument:
    record: RetrievalRecord
    term_frequencies: Counter[str]
    length: int


class BM25ReferenceIndex:
    """Small deterministic reference, not a production lexical engine."""

    def __init__(
        self,
        *,
        contract: LexicalRetrievalContract,
        records: tuple[RetrievalRecord, ...],
    ) -> None:
        if not records:
            raise ValueError("BM25 reference requires a non-empty corpus")
        self.contract = contract
        self.records = records
        self.documents = tuple(
            AnalyzedDocument(
                record,
                Counter(self.analyze(record.text)),
                len(self.analyze(record.text)),
            )
            for record in records
        )
        self.average_length = sum(item.length for item in self.documents) / len(
            self.documents
        )
        self.document_frequency: Counter[str] = Counter()
        for item in self.documents:
            self.document_frequency.update(item.term_frequencies.keys())

    def analyze(self, text: str) -> tuple[str, ...]:
        tokens = tuple(
            token.lower()
            for token in re.findall(r"[A-Za-z0-9_:-]+|[\u4e00-\u9fff]", text)
        )
        stop_words = frozenset(word.lower() for word in self.contract.stop_words)
        return tuple(token for token in tokens if token not in stop_words)

    def score(self, query: str, document: AnalyzedDocument) -> float:
        query_terms = self.analyze(query)
        score = 0.0
        total_documents = len(self.documents)
        for term in query_terms:
            frequency = document.term_frequencies.get(term, 0)
            if frequency == 0:
                continue
            document_frequency = self.document_frequency[term]
            inverse_document_frequency = math.log(
                1.0
                + (
                    total_documents - document_frequency + 0.5
                ) / (document_frequency + 0.5)
            )
            length_norm = 1.0 - self.contract.b + self.contract.b * (
                document.length / self.average_length
            )
            numerator = frequency * (self.contract.k1 + 1.0)
            denominator = frequency + self.contract.k1 * length_norm
            score += inverse_document_frequency * numerator / denominator
        return score


class LexicalRetrievalAdapter:
    def __init__(
        self,
        index: BM25ReferenceIndex,
        *,
        mode: LexicalMode = LexicalMode.NORMAL,
    ) -> None:
        self.index = index
        self.mode = mode
        self.database_calls = 0

    def search(
        self,
        *,
        query_text: str,
        bundle: SelectedRetrievalBundle,
        scope: RetrievalAuthorizationScope,
        business_filter: FilterExpression | None,
        system_excluded_occurrence_ids: tuple[str, ...],
        offset: int,
        limit: int,
    ) -> tuple[BranchCandidate, ...]:
        if bundle.lexical.fingerprint != self.index.contract.fingerprint:
            raise LexicalRetrievalError("LEXICAL_CONTRACT_MISMATCH")
        if scope.tenant_id != bundle.tenant_id:
            raise LexicalRetrievalError("LEXICAL_SCOPE_TENANT_MISMATCH")
        if offset < 0 or limit <= 0:
            raise LexicalRetrievalError("LEXICAL_PAGE_BOUNDS_INVALID")
        self.database_calls += 1
        if self.mode is LexicalMode.TIMEOUT:
            raise LexicalRetrievalError("LEXICAL_READ_TIMEOUT")
        scored: list[tuple[float, RetrievalRecord]] = []
        for document in self.index.documents:
            record = document.record
            if not authorized_and_business_match(
                scope=scope,
                occurrence_id=record.identity.occurrence_id,
                metadata=record.metadata_dict,
                business_filter=business_filter,
                system_excluded_occurrence_ids=system_excluded_occurrence_ids,
            ):
                continue
            score = self.index.score(query_text, document)
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].identity.occurrence_id))
        page = scored[offset: offset + limit]
        return tuple(
            BranchCandidate(
                identity=record.identity,
                branch=RetrievalBranch.LEXICAL,
                branch_rank=offset + index + 1,
                raw_score=score,
                score_direction=ScoreDirection.HIGHER_IS_BETTER,
                generation_id=bundle.generation_id,
                corpus_generation_id=bundle.lexical_corpus_generation_id,
                bundle_fingerprint=bundle.fingerprint,
                metadata=record.metadata,
            )
            for index, (score, record) in enumerate(page)
        )
