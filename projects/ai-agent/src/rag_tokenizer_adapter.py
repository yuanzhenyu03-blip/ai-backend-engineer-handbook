"""Dependency-free deterministic tokenizer behind a Day96 application port.

This classroom tokenizer groups ASCII word runs and counts other code points and
whitespace individually. It is deliberately not a production model tokenizer.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from rag_chunking_contracts import TokenizerContract


@dataclass(frozen=True)
class TokenSpan:
    start: int
    end: int


class TokenizerPort(Protocol):
    @property
    def contract(self) -> TokenizerContract: ...

    def spans(self, text: str) -> tuple[TokenSpan, ...]: ...

    def count(self, text: str) -> int: ...


class ClassroomTokenizer:
    """Stable offline token boundaries for control-flow tests only."""

    _pattern = re.compile(r"[A-Za-z0-9_]+|\s|[^\s]", re.UNICODE)

    @property
    def contract(self) -> TokenizerContract:
        return TokenizerContract("classroom-lexical", "1.0.0")

    def spans(self, text: str) -> tuple[TokenSpan, ...]:
        spans = tuple(
            TokenSpan(match.start(), match.end())
            for match in self._pattern.finditer(text)
        )
        if "".join(text[span.start:span.end] for span in spans) != text:
            raise ValueError("tokenizer did not cover exact canonical text")
        return spans

    def count(self, text: str) -> int:
        return len(self.spans(text))
