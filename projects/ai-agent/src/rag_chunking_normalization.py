"""Versioned Day96 normalization with a reversible canonical-source map."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedText:
    text: str
    # Each output code point maps to a non-empty interval in Day95 canonical text.
    source_offsets: tuple[tuple[int, int], ...]

    def source_interval(self, start: int, end: int) -> tuple[int, int]:
        if start < 0 or end <= start or end > len(self.source_offsets):
            raise ValueError("normalized interval is invalid")
        return self.source_offsets[start][0], self.source_offsets[end - 1][1]


def normalize(text: str, version: str) -> NormalizedText:
    """Keep canonical offsets even when horizontal whitespace is collapsed."""

    if version not in {"identity-v1", "collapse-horizontal-space-v1"}:
        raise ValueError("unsupported normalization version")
    if version == "identity-v1":
        return NormalizedText(
            text,
            tuple((index, index + 1) for index in range(len(text))),
        )
    output = []
    offsets = []
    index = 0
    while index < len(text):
        if text[index] in " \t":
            end = index + 1
            while end < len(text) and text[end] in " \t":
                end += 1
            output.append(" ")
            offsets.append((index, end))
            index = end
        else:
            output.append(text[index])
            offsets.append((index, index + 1))
            index += 1
    return NormalizedText("".join(output), tuple(offsets))
