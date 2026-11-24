# Phase 4 — Interview Questions & Answers: Document Processing & Hybrid Retrieval

> **Focus Area:** Technical and architectural interview preparation covering Document Ingestion, Boundary-Aware Chunking, Vector Embeddings, Okapi BM25, Reciprocal Rank Fusion (RRF), and Security Governance.

---

## 1. Document Chunking & Text Processing

### Q1: Why is document chunking necessary in Retrieval-Augmented Generation (RAG), and what are the trade-offs of chunk size?
**Answer:**
Chunking is necessary because:
1. **Context Window Constraints:** Embedding models and LLMs have finite context limits (e.g., 512–8192 tokens for embeddings). Feeding entire documents dilutes semantic representations.
2. **Signal-to-Noise Ratio (The "Lost in the Middle" phenomenon):** When an LLM receives 50 pages of text to answer a single specific query, retrieval accuracy drops. Small, highly relevant chunks maximize answer grounding and minimize token costs.
3. **Chunk Size Trade-offs:**
   - **Small Chunks (100–300 chars):** High precision; excellent for specific factual lookups (dates, numbers). Trade-off: Lacks broader contextual narrative.
   - **Large Chunks (1000–2000 chars):** Captures complete concepts and paragraphs. Trade-off: Lower retrieval precision; increases risk of irrelevant text distracting the generator.
   - **Our Choice:** Target size of ~500 characters (~100 words) with 50-character overlap strikes an optimal balance for enterprise documentation.

---

### Q2: Why is "chunk overlap" essential, and how does your `TextChunker` handle boundaries?
**Answer:**
If text is sliced strictly at fixed character boundaries (e.g., exactly at character 500), sentences and critical thoughts can be severed mid-word or mid-sentence, destroying semantic meaning.  
Our `TextChunker` implements two techniques:
1. **Boundary Hierarchy:** It splits on double newlines (`\n\n`) first to keep paragraphs intact, then on punctuation marks (`[.!?]`) for sentences, and only splits words as a last resort for giant sentences.
2. **Sliding Overlap Window:** Each subsequent chunk prepends the final units of the preceding chunk (default: 50 characters). This guarantees that any thought spanning the boundary is represented fully in at least one chunk.

---

## 2. Vector Embeddings & Similarity Metrics

### Q3: What is the mathematical difference between Cosine Similarity, Dot Product, and Euclidean Distance, and why is Cosine Similarity preferred for text embeddings?
**Answer:**
- **Dot Product:** $A \cdot B = \sum A_i B_i$. It reflects both the angle between vectors and their magnitudes. If document $A$ is longer or has higher embedding magnitude, its dot product will be artificially inflated.
- **Euclidean (L2) Distance:** $\|A - B\|_2 = \sqrt{\sum (A_i - B_i)^2}$. Measures physical distance in multi-dimensional space; sensitive to vector magnitude.
- **Cosine Similarity:**
  $$\text{Cosine}(A, B) = \frac{A \cdot B}{\|A\|_2 \|B\|_2} = \cos(\theta)$$
  It measures the **angle** between the two vectors regardless of magnitude, normalizing length to $[-1, 1]$.
- When embeddings are pre-normalized to unit length ($\|A\|_2 = 1$), Cosine Similarity and Dot Product become mathematically identical ($A \cdot B$), allowing ultra-fast matrix multiplication.

---

### Q4: How does `DeterministicFakeEmbeddings` work without calling external AI providers?
**Answer:**
To support 100% offline testing, CI/CD execution, and zero-cost local development, `DeterministicFakeEmbeddings` generates a 128-dimensional dense unit vector:
1. It computes a SHA-256 hash over the full document text to create a uniform baseline vector.
2. It hashes individual whitespace-tokenized words and adds positive weight to deterministic coordinate indices ($idx = \text{hash}(w) \pmod D$).
3. It normalizes the resulting vector using L2 norm ($\|V\|_2 = 1.0$).
This guarantees two vital properties:
- **Determinism:** The same text always produces the exact same vector.
- **Semantic Overlap:** Two texts sharing keywords (e.g., "Kubernetes cluster") produce higher positive cosine similarity than unrelated texts, verifying vector search logic without third-party APIs.

---

## 3. Sparse Keyword Search & Okapi BM25

### Q5: Why is Okapi BM25 superior to standard TF-IDF for keyword retrieval?
**Answer:**
1. **Term Frequency Saturation:** In standard TF-IDF, if a term appears 20 times in a document, its score is 20 times higher than if it appeared once. In BM25, the parameter $k_1$ (typically 1.2–1.5) provides a non-linear asymptotic curve: after a few occurrences, additional repetitions yield diminishing returns.
2. **Document Length Normalization:** Long documents naturally contain more words. Standard TF penalizes short documents. BM25 incorporates parameter $b$ (typically 0.75) which normalizes term frequencies against the average document length ($|D| / \text{avgdl}$), preventing long documents from dominating results unfairly.

---

## 4. Hybrid Search & Reciprocal Rank Fusion (RRF)

### Q6: What is Reciprocal Rank Fusion (RRF), and why is it better than linearly adding scores ($\alpha \cdot S_{\text{dense}} + (1 - \alpha) \cdot S_{\text{sparse}}$)?
**Answer:**
- **The Problem with Linear Score Combination:** Vector similarity produces cosine scores in $[-1, 1]$ (or $[0, 1]$), whereas BM25 produces unbounded scores in $[0, \infty)$ depending on corpus size. Normalizing and tuning a linear weighting hyperparameter ($\alpha$) is fragile and breaks whenever new documents change the BM25 distribution.
- **Reciprocal Rank Fusion (RRF):** RRF is rank-based rather than score-based. It ignores raw score magnitudes and uses only the ordinal rank of items:
  $$\text{RRF Score}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  Where $M$ is the set of retrieval strategies (semantic + BM25), $r_m(d)$ is the 1-based rank of document $d$ in system $m$, and $k$ is a smoothing constant (standard: 60).
- **Advantages:** RRF requires zero parameter tuning, treats dense and sparse rankings democratically, and strongly rewards documents that appear near the top of both lists.

---

## 5. Architecture, Storage & Governance

### Q7: How does the system guarantee relational and vector synchronization during document deletion?
**Answer:**
In our `DocumentService.delete_document(document_id)`:
1. **Relational Cascading:** The `Document` entity declares `chunks: relationship(..., cascade="all, delete-orphan")`. Deleting the document automatically deletes all associated `DocumentChunk` records from PostgreSQL/SQLite.
2. **Vector Eviction:** `InMemoryVectorStore.delete_by_document_id(document_id)` traverses the vector index and removes all vector entries matching that document ID.
3. **Transaction Commit:** Only once both database rows and vector records are purged is the database transaction committed.

---

### Q8: Why are document ingestion and deletion protected by different RBAC roles?
**Answer:**
Following the principle of least privilege and enterprise separation of duties:
- **`analyst` role:** Can upload, chunk, and index documents (`POST /api/v1/documents/ingest`) to conduct research.
- **`viewer` role:** Can search and read documents (`GET`, `POST /search`), but cannot mutate knowledge.
- **`admin` role only:** Only administrators can delete documents (`DELETE /api/v1/documents/{id}`). In accordance with PRD requirement F17, destructive deletion is governed by an administrative approval gate to prevent accidental loss of enterprise knowledge or tampering with compliance records.
