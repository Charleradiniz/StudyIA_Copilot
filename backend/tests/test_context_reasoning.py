import unittest

from app.services.context_reasoning import (
    build_structured_context,
    cluster_chunks,
    compute_chunk_similarity,
    extract_relationships,
    remove_redundant_chunks,
    run_context_aware_reasoning,
)


def make_chunk(
    *,
    doc_id: str,
    doc_label: str,
    chunk_id: int,
    page: int,
    text: str,
    score: float,
) -> dict:
    return {
        "doc_id": doc_id,
        "doc_label": doc_label,
        "doc_name": doc_label,
        "chunk_id": chunk_id,
        "id": chunk_id,
        "page": page,
        "text": text,
        "score": score,
        "retrieval_rank": chunk_id + 1,
    }


class ContextReasoningTests(unittest.TestCase):
    def test_similarity_and_redundancy_removal_preserve_best_chunks(self) -> None:
        chunks = [
            make_chunk(
                doc_id="doc-a",
                doc_label="Doc A",
                chunk_id=0,
                page=0,
                text="The retrieval layer uses embeddings and reranking to improve grounded answers.",
                score=0.92,
            ),
            make_chunk(
                doc_id="doc-a",
                doc_label="Doc A",
                chunk_id=1,
                page=1,
                text="The retrieval layer uses embeddings and reranking to improve grounded answers.",
                score=0.83,
            ),
            make_chunk(
                doc_id="doc-b",
                doc_label="Doc B",
                chunk_id=0,
                page=0,
                text="Grounded answers depend on strong retrieval quality and evidence selection.",
                score=0.88,
            ),
        ]

        similarity = compute_chunk_similarity(chunks, semantic_model=None)
        deduped = remove_redundant_chunks(
            similarity["chunks"],
            similarity["similarity_matrix"],
        )

        self.assertEqual(len(similarity["chunks"]), 3)
        self.assertEqual(len(deduped["chunks"]), 2)
        self.assertGreater(deduped["redundancy_score"], 0.0)
        traces = [chunk["trace"] for chunk in deduped["chunks"]]
        self.assertTrue(any("Doc A" in trace for trace in traces))
        self.assertTrue(any("Doc B" in trace for trace in traces))

    def test_cluster_relationships_and_structured_context_capture_multi_hop_links(self) -> None:
        chunks = [
            make_chunk(
                doc_id="doc-a",
                doc_label="Doc A",
                chunk_id=0,
                page=0,
                text="Chunking quality affects retrieval because smaller clean chunks improve semantic matching.",
                score=0.93,
            ),
            make_chunk(
                doc_id="doc-b",
                doc_label="Doc B",
                chunk_id=1,
                page=0,
                text="Retrieval depends on chunking strategy and good metadata to keep evidence aligned.",
                score=0.89,
            ),
            make_chunk(
                doc_id="doc-c",
                doc_label="Doc C",
                chunk_id=2,
                page=1,
                text="Unlike naive pipelines, the final answer should compare related evidence before responding.",
                score=0.84,
            ),
        ]

        similarity = compute_chunk_similarity(chunks, semantic_model=None)
        clusters = cluster_chunks(
            similarity["chunks"],
            similarity["similarity_matrix"],
            query="How do chunking and retrieval relate?",
        )
        relationship_result = extract_relationships(
            clusters,
            query="How do chunking and retrieval relate?",
        )
        structured_context = build_structured_context(relationship_result["clusters"])

        self.assertGreaterEqual(len(relationship_result["clusters"]), 1)
        self.assertIn("[Topic 1:", structured_context)
        self.assertIn("Coverage:", structured_context)
        self.assertIn("[Cross-topic relationships]", structured_context)
        self.assertTrue(
            any(
                marker in structured_context
                for marker in ("Relationship:", "Dependency:", "Comparison:")
            )
        )
        self.assertIn("Chunk 1", structured_context)

    def test_run_context_aware_reasoning_returns_ranked_clusters_and_metrics(self) -> None:
        chunks = [
            make_chunk(
                doc_id="doc-a",
                doc_label="Doc A",
                chunk_id=0,
                page=0,
                text="The ingestion flow extracts text, stores metadata, and prepares chunks for retrieval.",
                score=0.91,
            ),
            make_chunk(
                doc_id="doc-b",
                doc_label="Doc B",
                chunk_id=1,
                page=0,
                text="Metadata enables the viewer to highlight exact evidence and connect answers back to the PDF.",
                score=0.87,
            ),
            make_chunk(
                doc_id="doc-c",
                doc_label="Doc C",
                chunk_id=2,
                page=1,
                text="Reranking removes weaker evidence and keeps the most relevant chunks for answer generation.",
                score=0.82,
            ),
        ]

        result = run_context_aware_reasoning(
            "How does the pipeline connect retrieval and evidence?",
            chunks,
            semantic_model=None,
            desired_source_count=3,
            desired_context_count=4,
        )

        self.assertIn("structured_context", result)
        self.assertIn("[Topic 1:", result["structured_context"])
        self.assertEqual(len(result["source_chunks"]), 3)
        self.assertGreaterEqual(result["metrics"]["cluster_count"], 1)
        self.assertIn("cross_topic_link_count", result["metrics"])
        self.assertIn("similarity_backend", result["metrics"])


if __name__ == "__main__":
    unittest.main()
