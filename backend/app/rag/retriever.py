from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.app.rag.embeddings import get_embeddings
from backend.app.rag.ingest import COLLECTION_NAME, DEFAULT_CHROMA_DIR

DEFAULT_TOP_K = 3
DEFAULT_RELEVANCE_THRESHOLD = 0.30


def retrieve_relevant_chunks(
    query: str,
    persist_directory: Path | str = DEFAULT_CHROMA_DIR,
    collection_name: str = COLLECTION_NAME,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
) -> list[Document]:
    """Retrieve top-k semantically relevant chunks above the relevance threshold."""
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    persist_path = Path(persist_directory)
    if not persist_path.exists():
        return []

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_path),
        collection_metadata={"hnsw:space": "cosine"},
    )

    if vectorstore._collection.count() == 0:
        return []

    results_with_scores = vectorstore.similarity_search_with_relevance_scores(
        cleaned_query,
        k=top_k,
    )

    relevant_docs: list[Document] = []
    for doc, score in results_with_scores:
        if score >= score_threshold:
            relevant_docs.append(doc)

    return relevant_docs
