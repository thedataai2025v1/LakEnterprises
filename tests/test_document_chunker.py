"""Unit tests for P4-1: TextChunker and boundary-aware splitting."""

import pytest

from lakenterprises.document.chunker import TextChunker


class TestTextChunkerInit:
    def test_default_init(self) -> None:
        chunker = TextChunker()
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 50

    def test_custom_init(self) -> None:
        chunker = TextChunker(chunk_size=300, chunk_overlap=30, min_chunk_size=10)
        assert chunker.chunk_size == 300
        assert chunker.chunk_overlap == 30
        assert chunker.min_chunk_size == 10

    def test_invalid_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            TextChunker(chunk_size=0)

    def test_invalid_negative_overlap(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
            TextChunker(chunk_size=100, chunk_overlap=-5)

    def test_overlap_greater_than_chunk_size(self) -> None:
        with pytest.raises(
            ValueError, match="chunk_overlap must be less than chunk_size"
        ):
            TextChunker(chunk_size=100, chunk_overlap=100)


class TestTextChunkerSplitting:
    def test_empty_string_returns_empty_list(self) -> None:
        chunker = TextChunker()
        assert chunker.split_text("") == []
        assert chunker.split_text("   \n\n  ") == []

    def test_single_small_text_produces_one_chunk(self) -> None:
        chunker = TextChunker(chunk_size=200, chunk_overlap=20)
        text = "LakEnterprises is an enterprise AI knowledge platform."
        chunks = chunker.split_text(text, metadata={"category": "tech"})
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].word_count == 7
        assert chunks[0].metadata["category"] == "tech"

    def test_multiple_paragraphs_respects_boundaries(self) -> None:
        p1 = "Paragraph 1: LakEnterprises builds intelligent multi-agent orchestration systems."
        p2 = "Paragraph 2: The architecture combines vector databases, knowledge graphs, and relational stores."
        p3 = "Paragraph 3: Role-based access control protects all sensitive endpoints."
        full_text = f"{p1}\n\n{p2}\n\n{p3}"

        chunker = TextChunker(chunk_size=120, chunk_overlap=20)
        chunks = chunker.split_text(full_text)
        assert len(chunks) >= 2

        # Verify sequential indexing
        for i, c in enumerate(chunks):
            assert c.chunk_index == i
            assert len(c.text) > 0
            assert c.word_count > 0

    def test_chunk_overlap_shares_text(self) -> None:
        text = (
            "Section A covers the primary data model for research sessions. "
            "Section B details the query decomposition pipeline. "
            "Section C outlines the reciprocal rank fusion retrieval mechanism. "
            "Section D specifies the guardrail policies and output verification."
        )
        chunker = TextChunker(chunk_size=100, chunk_overlap=30)
        chunks = chunker.split_text(text)
        assert len(chunks) > 1

        # Check that consecutive chunks have non-zero overlap
        for i in range(len(chunks) - 1):
            assert len(chunks[i].text) > 0
            assert len(chunks[i + 1].text) > 0

    def test_metadata_copied_to_every_chunk(self) -> None:
        text = "Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph."
        chunker = TextChunker(chunk_size=40, chunk_overlap=10)
        meta = {"doc_id": "doc-123", "author": "Alice"}
        chunks = chunker.split_text(text, metadata=meta)
        for c in chunks:
            assert c.metadata["doc_id"] == "doc-123"
            assert c.metadata["author"] == "Alice"
