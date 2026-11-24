"""Text chunking utilities for the LakEnterprises document processing pipeline.

Splits text into chunks of configurable size and overlap while respecting
paragraph and sentence boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Chunk:
    """A text chunk produced by the chunker."""

    text: str
    chunk_index: int
    word_count: int
    char_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


class TextChunker:
    """Configurable text chunker with overlap and boundary preservation.

    Parameters
    ----------
    chunk_size:
        Target character count per chunk (default: 500).
    chunk_overlap:
        Number of characters to overlap between consecutive chunks (default: 50).
    min_chunk_size:
        Minimum characters required for a valid chunk (default: 20).
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 20,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def split_text(
        self,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[Chunk]:
        """Split *text* into a list of :class:`Chunk` objects.

        Preserves paragraph and sentence boundaries where possible.
        """
        if not text or not text.strip():
            return []

        base_meta = dict(metadata or {})
        cleaned_text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split into initial paragraphs
        raw_paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
        if not raw_paragraphs:
            raw_paragraphs = [cleaned_text.strip()]

        # Break overly large paragraphs into sentences
        units: list[str] = []
        for para in raw_paragraphs:
            if len(para) <= self.chunk_size:
                units.append(para)
            else:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sent in sentences:
                    s = sent.strip()
                    if not s:
                        continue
                    if len(s) <= self.chunk_size:
                        units.append(s)
                    else:
                        # Split very long sentences by words
                        words = s.split()
                        curr_words: list[str] = []
                        curr_len = 0
                        for w in words:
                            if curr_len + len(w) + 1 > self.chunk_size and curr_words:
                                units.append(" ".join(curr_words))
                                curr_words = [w]
                                curr_len = len(w)
                            else:
                                curr_words.append(w)
                                curr_len += len(w) + 1
                        if curr_words:
                            units.append(" ".join(curr_words))

        # Merge units into chunks respecting chunk_size and chunk_overlap
        chunks: list[Chunk] = []
        current_chunk_units: list[str] = []
        current_length = 0
        chunk_idx = 0

        for unit in units:
            unit_len = len(unit)
            if (
                current_length + unit_len + (2 if current_chunk_units else 0)
                <= self.chunk_size
            ):
                current_chunk_units.append(unit)
                current_length += unit_len + (2 if len(current_chunk_units) > 1 else 0)
            else:
                if current_chunk_units:
                    chunk_text = "\n\n".join(current_chunk_units).strip()
                    if len(chunk_text) >= self.min_chunk_size or not chunks:
                        meta = dict(base_meta)
                        chunks.append(
                            Chunk(
                                text=chunk_text,
                                chunk_index=chunk_idx,
                                word_count=len(chunk_text.split()),
                                char_count=len(chunk_text),
                                metadata=meta,
                            )
                        )
                        chunk_idx += 1

                    # Compute overlap from the end of current_chunk_units
                    overlap_units: list[str] = []
                    overlap_len = 0
                    for u in reversed(current_chunk_units):
                        if overlap_len + len(u) <= self.chunk_overlap:
                            overlap_units.insert(0, u)
                            overlap_len += len(u)
                        else:
                            break

                    current_chunk_units = overlap_units + [unit]
                    current_length = sum(len(u) for u in current_chunk_units) + max(
                        0, (len(current_chunk_units) - 1) * 2
                    )
                else:
                    current_chunk_units = [unit]
                    current_length = unit_len

        # Final chunk
        if current_chunk_units:
            chunk_text = "\n\n".join(current_chunk_units).strip()
            if chunk_text:
                meta = dict(base_meta)
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        chunk_index=chunk_idx,
                        word_count=len(chunk_text.split()),
                        char_count=len(chunk_text),
                        metadata=meta,
                    )
                )

        return chunks
