from app.rag.chunking import DocumentChunk
from app.rag.store import ChromaKnowledgeBase


def test_chroma_store_returns_nearest_chunk(tmp_path) -> None:
    store = ChromaKnowledgeBase(str(tmp_path), "techassist_test")
    store.upsert(
        [
            DocumentChunk(
                content="Reset the network adapter before changing firewall rules.",
                source="network-guide.md",
                page=None,
                chunk_index=0,
            )
        ],
        [[1.0, 0.0]],
        "troubleshooting guide",
    )

    results = store.search([1.0, 0.0], limit=1)

    assert len(results) == 1
    assert results[0].source == "network-guide.md"
    assert results[0].category == "troubleshooting guide"
