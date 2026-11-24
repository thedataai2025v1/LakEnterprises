"""Hybrid retrieval for the LakEnterprises knowledge platform.

Combines semantic (vector) search with BM25 keyword matching, merges results
via Reciprocal Rank Fusion (RRF), and optionally reranks with a custom
scorer.  The BM25 scoring is fully self-contained -- no external library is
needed.

Usage
-----
>>> from lakenterprises.retriever import HybridRetriever
>>> retriever = HybridRetriever(top_k=5)
>>> retriever.add_documents(
...     ["Python is a programming language", "Java is also a language"],
... )
>>> results = retriever.search("programming languages")
>>> for r in results:
...     print(r["text"], r["score"])
"""

from __future__ import annotations

import logging
import math
import string
from collections import Counter
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

_RerankerCallable = Callable[[list[dict[str, Any]], str], list[dict[str, Any]]]

# ---------------------------------------------------------------------------
# Tokeniser helpers (shared by BM25 and semantic pre-processing)
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Lowercase, strip punctuation, and split on whitespace."""
    cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
    return [t for t in cleaned.split() if t]


# ---------------------------------------------------------------------------
# BM25 index (self-contained, no external library)
# ---------------------------------------------------------------------------


class _BM25Index:
    """Minimal BM25 index over a corpus of documents.

    Implements the Okapi BM25 scoring function with standard parameters
    (k1=1.5, b=0.75) as described by Robertson et al.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.documents: list[str] = []
        self._token_lists: list[list[str]] = []
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._n: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, texts: list[str]) -> None:
        """Add one or more documents to the index.

        Parameters
        ----------
        texts:
            Plain-text documents to index.
        """
        old_n = len(self.documents)
        self.documents.extend(texts)
        for text in texts:
            self._token_lists.append(_tokenise(text))

        if old_n == 0 and len(self.documents) == len(texts):
            # First batch -- build from scratch
            self._build()
        else:
            # Incremental rebuild
            self._rebuild()

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the index and return scored results.

        Parameters
        ----------
        query:
            The search query string.
        top_k:
            Maximum number of results to return.

        Returns
        -------
        List of dicts with keys ``rank``, ``score``, and ``doc_index``.
        """
        if not self._token_lists:
            return []

        query_tokens = _tokenise(query)
        if not query_tokens:
            return []

        scores: list[float] = []
        for i, tokens in enumerate(self._token_lists):
            score = self._score(query_tokens, tokens, i)
            scores.append((score, i))

        # Sort by score descending, then by index ascending for stability
        scores.sort(key=lambda x: (-x[0], x[1]))

        results: list[dict[str, Any]] = []
        for rank, (score, doc_index) in enumerate(scores[:top_k], start=1):
            results.append(
                {
                    "rank": rank,
                    "score": score,
                    "doc_index": doc_index,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Internal: BM25 scoring
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Build IDF cache and average document length from scratch."""
        self._n = len(self._token_lists)
        if self._n == 0:
            return
        self._avgdl = sum(len(t) for t in self._token_lists) / self._n
        self._compute_idf()

    def _rebuild(self) -> None:
        """Rebuild the entire index after documents have been added."""
        self._build()

    def _compute_idf(self) -> None:
        """Compute IDF for every unique term in the corpus.

        Uses the standard smoothing variant:
            IDF(t) = log((N - n(t) + 0.5) / (n(t) + 0.5) + 1)
        """
        n_docs = self._n
        doc_freq: dict[str, int] = Counter()
        for tokens in self._token_lists:
            for term in set(tokens):
                doc_freq[term] += 1

        self._idf = {}
        for term, df in doc_freq.items():
            self._idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)

    def _score(
        self,
        query_tokens: list[str],
        doc_tokens: list[str],
        doc_index: int,
    ) -> float:
        """Compute the BM25 score of *query_tokens* against *doc_tokens*.

        BM25(t) = IDF(t) * (f(t,D) * (k1 + 1)) / (f(t,D) + k1 * (1 - b + b * |D|/avgdl))
        """
        tf = Counter(doc_tokens)
        doc_len = len(doc_tokens)
        score = 0.0

        for term in query_tokens:
            idf = self._idf.get(term, 0.0)
            if idf == 0.0:
                continue
            freq = tf.get(term, 0)
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (
                1 - self.b + self.b * doc_len / max(self._avgdl, 1e-9)
            )
            score += idf * (numerator / denominator)

        return score


# ---------------------------------------------------------------------------
# HybridRetriever
# ---------------------------------------------------------------------------


class HybridRetriever:
    """Combine semantic, keyword (BM25), and reranking for robust retrieval.

    The retrieval pipeline is:

    1. **Semantic search** -- vector similarity via an optional
       ``vectorstore`` (e.g. a LangChain vector store).
    2. **BM25 search** -- keyword matching against a locally-indexed corpus.
    3. **Reciprocal Rank Fusion** -- merge the two ranked lists into a
       single ordering.
    4. **Reranking** (optional) -- apply a custom scorer to the merged
       results.

    Parameters
    ----------
    embeddings:
        A LangChain ``Embeddings`` instance.  Used by the vector store;
        not required if the vector store manages its own embeddings.
    vectorstore:
        Any object with a ``similarity_search(query, k)`` method that
        returns documents (objects with ``page_content`` and
        ``metadata`` attributes, as in LangChain).
    bm25_corpus:
        Initial list of text documents to index for BM25.
    reranker:
        A callable ``(documents: list[dict], query: str) -> list[dict]``
        that reranks and rescores the merged results.  Set to ``None`` to
        skip reranking.
    top_k:
        Number of results returned by each sub-search and the final output.
    rrf_k:
        Rank constant for Reciprocal Rank Fusion (typical value: 60).

    Examples
    --------
    >>> retriever = HybridRetriever(
    ...     vectorstore=vs,
    ...     bm25_corpus=["Doc 1 text", "Doc 2 text"],
    ...     top_k=5,
    ... )
    >>> results = retriever.search("query")
    """

    def __init__(
        self,
        embeddings: Any = None,
        vectorstore: Any = None,
        bm25_corpus: Optional[list[str]] = None,
        reranker: Optional[_RerankerCallable] = None,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if rrf_k < 1:
            raise ValueError("rrf_k must be >= 1")

        self.embeddings = embeddings
        self.vectorstore = vectorstore
        self.reranker = reranker
        self.top_k = top_k
        self.rrf_k = rrf_k

        # Internal BM25 index
        self._bm25 = _BM25Index()

        # Track full documents so we can return text + metadata
        self._documents: list[str] = []
        self._metadata: list[dict[str, Any]] = []

        # Seed BM25 from corpus if provided
        if bm25_corpus:
            self.add_documents(bm25_corpus)

    # ------------------------------------------------------------------
    # Main public API
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[dict[str, Any]]:
        """Execute hybrid search and return scored results.

        Parameters
        ----------
        query:
            The user's search query.

        Returns
        -------
        List of dicts, each with keys:

        * ``text`` -- the matched document text.
        * ``score`` -- the final fused (and possibly reranked) score.
        * ``source`` -- origin identifier (e.g. file path, document id).
        * ``strategy`` -- which sub-search contributed the result
          (``"semantic"``, ``"bm25"``, or ``"hybrid"``).
        """
        if not query or not query.strip():
            logger.warning("Empty query passed to HybridRetriever.search()")
            return []

        semantic_results = self._semantic_search(query)
        bm25_results = self._bm25_search(query)

        if not semantic_results and not bm25_results:
            logger.warning(
                "Both semantic and BM25 searches returned no results for " "query: %s",
                query[:100],
            )
            return []

        # Reciprocal Rank Fusion
        merged = self._rrf_merge(semantic_results, bm25_results)

        # Optional reranking
        merged = self._rerank(merged, query)

        return merged[: self.top_k]

    def add_documents(
        self,
        texts: list[str],
        metadata: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Add documents to both the semantic index (vector store) and
        the BM25 index.

        Parameters
        ----------
        texts:
            Plain-text document strings to index.
        metadata:
            Optional list of dicts providing per-document metadata
            (e.g. source, id).  Must be the same length as *texts* if
            provided.
        """
        if not texts:
            return

        if metadata is not None and len(metadata) != len(texts):
            raise ValueError(
                f"metadata list length ({len(metadata)}) must equal "
                f"texts list length ({len(texts)})"
            )

        start_idx = len(self._documents)

        # Store locally
        self._documents.extend(texts)
        if metadata is not None:
            self._metadata.extend(metadata)
        else:
            for i in range(len(texts)):
                self._metadata.append(
                    {
                        "id": f"doc-{start_idx + i}",
                        "source": "unknown",
                    }
                )

        # Add to BM25 index
        self._bm25.add(texts)

        # Add to vector store if available
        if self.vectorstore is not None:
            try:
                # LangChain-style: accept list of texts and metadatas
                if metadata is not None:
                    self.vectorstore.add_texts(texts, metadata)
                else:
                    self.vectorstore.add_texts(texts)
                logger.debug("Added %d documents to vector store", len(texts))
            except Exception:
                logger.exception("Failed to add documents to vector store")

    # ------------------------------------------------------------------
    # Sub-search strategies
    # ------------------------------------------------------------------

    def _semantic_search(self, query: str) -> list[dict[str, Any]]:
        """Vector-based similarity search via the configured vector store.

        Parameters
        ----------
        query:
            The search query.

        Returns
        -------
        List of result dicts, or an empty list if no vector store is
        configured.
        """
        if self.vectorstore is None:
            logger.debug("No vector store configured; semantic search skipped")
            return []

        try:
            # Standard LangChain interface
            raw_results = self.vectorstore.similarity_search(query, k=self.top_k)
        except AttributeError:
            # Fallback: some stores use search() or query()
            logger.warning(
                "Vector store has no similarity_search method; "
                "semantic search skipped"
            )
            return []
        except Exception:
            logger.exception("Semantic search failed")
            return []

        results: list[dict[str, Any]] = []
        for rank, doc in enumerate(raw_results, start=1):
            text = getattr(doc, "page_content", str(doc))
            meta = getattr(doc, "metadata", {})

            results.append(
                {
                    "text": text,
                    "score": 1.0 / rank,  # Initial placeholder; RRF will re-score
                    "source": meta.get("source", "unknown"),
                    "strategy": "semantic",
                    "rank": rank,
                    "_raw_score": meta.get("score", 1.0 / rank),
                }
            )

        logger.debug("Semantic search returned %d results", len(results))
        return results

    def _bm25_search(self, query: str) -> list[dict[str, Any]]:
        """BM25 keyword search against the local corpus.

        Parameters
        ----------
        query:
            The search query.

        Returns
        -------
        List of result dicts.
        """
        if not self._bm25.documents:
            logger.debug("BM25 index is empty; BM25 search skipped")
            return []

        raw_results = self._bm25.search(query, top_k=self.top_k)

        results: list[dict[str, Any]] = []
        for item in raw_results:
            doc_index = item["doc_index"]
            text = (
                self._documents[doc_index] if doc_index < len(self._documents) else ""
            )
            meta = self._metadata[doc_index] if doc_index < len(self._metadata) else {}

            results.append(
                {
                    "text": text,
                    "score": item["score"],
                    "source": meta.get("source", "unknown"),
                    "strategy": "bm25",
                    "rank": item["rank"],
                    "_raw_score": item["score"],
                }
            )

        logger.debug("BM25 search returned %d results", len(results))
        return results

    # ------------------------------------------------------------------
    # Reciprocal Rank Fusion
    # ------------------------------------------------------------------

    def _rrf_merge(
        self,
        semantic_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge two ranked result lists via Reciprocal Rank Fusion.

        For each result in each list, compute:

            score = 1 / (k + rank)

        where *k* is ``self.rrf_k`` and *rank* is 1-based.  Results
        appearing in both lists accumulate scores from both sources.
        Ties in the merged list are broken by ``_raw_score`` descending.

        Parameters
        ----------
        semantic_results:
            Results from the semantic (vector) search.
        bm25_results:
            Results from the BM25 keyword search.

        Returns
        -------
        A merged and re-scored list of result dicts, sorted by RRF
        score descending.
        """
        # Accumulate RRF scores keyed by text content
        rrf_scores: dict[str, float] = {}
        result_cache: dict[str, dict[str, Any]] = {}

        def _process(
            results: list[dict[str, Any]],
            strategy_tag: str,
        ) -> None:
            for rank_offset, item in enumerate(results, start=1):
                text = item.get("text", "")
                rrf = 1.0 / (self.rrf_k + rank_offset)
                rrf_scores[text] = rrf_scores.get(text, 0.0) + rrf

                # Keep the latest (or first) full dict; mark as hybrid
                # if it appears in both lists
                if text in result_cache:
                    result_cache[text]["strategy"] = "hybrid"
                else:
                    cached = dict(item)
                    cached["strategy"] = (
                        "hybrid" if text in result_cache else strategy_tag
                    )
                    result_cache[text] = cached

        _process(semantic_results, "semantic")
        _process(bm25_results, "bm25")

        # Update strategy labels: if a document was in both lists,
        # mark as "hybrid"
        semantic_texts = {item["text"] for item in semantic_results}
        bm25_texts = {item["text"] for item in bm25_results}
        for text in result_cache:
            in_both = text in semantic_texts and text in bm25_texts
            if in_both:
                result_cache[text]["strategy"] = "hybrid"

        # Attach RRF scores
        for text, score in rrf_scores.items():
            result_cache[text]["score"] = score

        # Sort by RRF score descending, then by raw score descending
        merged = sorted(
            result_cache.values(),
            key=lambda r: (r["score"], r.get("_raw_score", 0.0)),
            reverse=True,
        )

        logger.debug("RRF merged %d unique results", len(merged))
        return merged

    # ------------------------------------------------------------------
    # Reranking
    # ------------------------------------------------------------------

    def _rerank(
        self,
        results: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Apply an optional reranker to the merged results.

        Parameters
        ----------
        results:
            The merged (RRF-scored) result list.
        query:
            The original search query.

        Returns
        -------
        Reranked results, or the input list unchanged if no reranker
        is configured.
        """
        if self.reranker is None:
            return results

        try:
            reranked = self.reranker(results, query)
            logger.debug("Reranker returned %d results", len(reranked))
            return reranked
        except Exception:
            logger.exception("Reranker failed; returning original results")
            return results

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @property
    def document_count(self) -> int:
        """Number of documents currently indexed."""
        return len(self._documents)

    def __repr__(self) -> str:
        return (
            f"HybridRetriever("
            f"docs={self.document_count}, "
            f"top_k={self.top_k}, "
            f"rrf_k={self.rrf_k}, "
            f"vectorstore={'yes' if self.vectorstore else 'no'}, "
            f"reranker={'yes' if self.reranker else 'no'}"
            f")"
        )
