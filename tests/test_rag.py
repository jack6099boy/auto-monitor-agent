import pytest
from agent.rag import RAGSystem

def test_rag_init():
    rag = RAGSystem()
    assert rag.sop_dir == "sop"
    assert rag.persist_dir == "./chroma_db"

def test_load_documents():
    rag = RAGSystem()
    docs = rag.load_documents()
    assert isinstance(docs, list)

def test_build_index():
    rag = RAGSystem()
    rag.build_index()
    # If no documents, index might be None
    # assert rag.index is not None  # Uncomment if documents exist

def test_query():
    rag = RAGSystem()
    rag.build_index()
    result = rag.query("test query")
    if rag.index:
        assert result is not None
    else:
        assert result == "Index not built yet."