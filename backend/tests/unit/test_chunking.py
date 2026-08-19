from app.services.rag.chunking import chunk_document


def test_chunk_document_preserves_heading_and_overlap() -> None:
    text = """# GSTR-2B Reconciliation\n\n""" + " ".join(f"word{i}" for i in range(180))

    chunks = chunk_document(text, max_chars=220, overlap_chars=45)

    assert len(chunks) > 2
    assert chunks[0].heading == "GSTR-2B Reconciliation"
    assert chunks[0].content.startswith("GSTR-2B Reconciliation")
    tail_words = set(chunks[0].content.split()[-5:])
    next_words = set(chunks[1].content.split()[:12])
    assert tail_words & next_words
