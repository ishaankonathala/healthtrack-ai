import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from backend.app.main import app
from backend.app.rag import chains, ingest, retriever


@pytest.fixture()
def temp_chroma_dir(tmp_path):
    """Provide an isolated temporary ChromaDB directory."""
    return tmp_path / "chroma_test_db"


def test_ingest_and_duplicate_prevention(temp_chroma_dir):
    first_stats = ingest.ingest_knowledge_base(persist_directory=temp_chroma_dir)
    assert first_stats["documents_processed"] == 4
    assert first_stats["chunks_total"] > 0
    assert first_stats["chunks_added"] == first_stats["chunks_total"]
    assert first_stats["chunks_skipped"] == 0

    second_stats = ingest.ingest_knowledge_base(persist_directory=temp_chroma_dir)
    assert second_stats["documents_processed"] == 4
    assert second_stats["chunks_total"] == first_stats["chunks_total"]
    assert second_stats["chunks_added"] == 0
    assert second_stats["chunks_skipped"] == first_stats["chunks_total"]


def test_retrieval_and_source_metadata_preservation(temp_chroma_dir):
    ingest.ingest_knowledge_base(persist_directory=temp_chroma_dir)

    docs = retriever.retrieve_relevant_chunks(
        query="What are common signs of dehydration?",
        persist_directory=temp_chroma_dir,
        top_k=3,
    )
    assert 1 <= len(docs) <= 3
    for doc in docs:
        assert "source_title" in doc.metadata
        assert "source_url" in doc.metadata
        assert doc.metadata["source_url"].startswith("https://medlineplus.gov/")

    titles = [doc.metadata["source_title"] for doc in docs]
    assert any("Dehydration" in title for title in titles)


def test_irrelevant_question_returns_safe_fallback_without_llm(temp_chroma_dir, monkeypatch):
    ingest.ingest_knowledge_base(persist_directory=temp_chroma_dir)

    called = {"llm": False}

    def fail_if_called(api_key: str, model: str):
        called["llm"] = True
        raise AssertionError("LLM should not be called for irrelevant questions")

    monkeypatch.setattr(chains, "_build_llm", fail_if_called)

    response = chains.answer_health_question(
        question="What is the capital city of France and how tall is the Eiffel Tower?",
        persist_directory=temp_chroma_dir,
    )
    assert called["llm"] is False
    assert response.sources == []
    assert "do not have enough information" in response.answer.lower()


def test_rag_empty_question_validation():
    client = TestClient(app)
    for bad_question in ["", "   ", "\n\t"]:
        resp = client.post("/rag/ask", json={"question": bad_question})
        assert resp.status_code == 422


def test_rag_grounded_answer_with_mocked_gemini(temp_chroma_dir, monkeypatch):
    ingest.ingest_knowledge_base(persist_directory=temp_chroma_dir)
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")

    captured = {}

    def fake_build_llm(api_key: str, model: str):
        def _invoke(prompt_value):
            captured["prompt"] = prompt_value.to_string()
            return AIMessage(
                content=(
                    "Common cold symptoms often include a runny or stuffy nose, sore throat, "
                    "and cough (MedlinePlus - Common Cold)."
                )
            )

        return RunnableLambda(_invoke)

    monkeypatch.setattr(chains, "_build_llm", fake_build_llm)
    monkeypatch.setattr(chains, "DEFAULT_CHROMA_DIR", temp_chroma_dir)

    # Point router's default call to temp_chroma_dir via chains.answer_health_question default
    original_fn = chains.answer_health_question

    def wrapped_answer(question: str, **kwargs):
        kwargs.setdefault("persist_directory", temp_chroma_dir)
        return original_fn(question=question, **kwargs)

    monkeypatch.setattr("backend.app.routers.rag.answer_health_question", wrapped_answer)

    client = TestClient(app)
    resp = client.post("/rag/ask", json={"question": "What are common cold symptoms?"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["question"] == "What are common cold symptoms?"
    assert "runny or stuffy nose" in data["answer"]
    assert len(data["sources"]) >= 1
    assert any("Common Cold" in s["title"] for s in data["sources"])
    assert any(s["url"] == "https://medlineplus.gov/commoncold.html" for s in data["sources"])
    assert "MedlinePlus - Common Cold" in captured["prompt"]
