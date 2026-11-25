import hashlib
import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.rag.embeddings import get_embeddings

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
DEFAULT_CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"))
COLLECTION_NAME = "health_education"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 75


def _parse_markdown_document(file_path: Path) -> tuple[dict[str, str], str]:
    """Parse YAML-style frontmatter metadata and body text from a Markdown file."""
    raw_text = file_path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {"source_title": file_path.stem, "source_url": ""}

    if raw_text.startswith("---\n"):
        parts = raw_text.split("---\n", 2)
        if len(parts) == 3:
            frontmatter, body = parts[1], parts[2].strip()
            for line in frontmatter.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key == "title":
                        metadata["source_title"] = value
                    elif key == "url":
                        metadata["source_url"] = value
            return metadata, body

    return metadata, raw_text.strip()


def load_and_split_documents(knowledge_dir: Path = KNOWLEDGE_DIR) -> list[tuple[str, Document]]:
    """Load Markdown files from knowledge_dir and split into overlapping chunks with deterministic IDs."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunk_records: list[tuple[str, Document]] = []

    for md_file in sorted(knowledge_dir.glob("*.md")):
        meta, body = _parse_markdown_document(md_file)
        if not body:
            continue

        chunks = splitter.split_text(body)
        for idx, chunk_text in enumerate(chunks):
            chunk_id = hashlib.sha256(
                f"{md_file.name}:{idx}:{chunk_text}".encode("utf-8")
            ).hexdigest()
            doc = Document(
                page_content=chunk_text,
                metadata={
                    "source_title": meta["source_title"],
                    "source_url": meta["source_url"],
                    "source_file": md_file.name,
                    "chunk_index": idx,
                },
            )
            chunk_records.append((chunk_id, doc))

    return chunk_records


def ingest_knowledge_base(
    knowledge_dir: Path = KNOWLEDGE_DIR,
    persist_directory: Path | str = DEFAULT_CHROMA_DIR,
    collection_name: str = COLLECTION_NAME,
) -> dict[str, int]:
    """Ingest curated Markdown documents into persistent ChromaDB without duplicates."""
    persist_path = Path(persist_directory)
    persist_path.mkdir(parents=True, exist_ok=True)

    md_files = list(sorted(knowledge_dir.glob("*.md")))
    chunk_records = load_and_split_documents(knowledge_dir=knowledge_dir)

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_path),
        collection_metadata={"hnsw:space": "cosine"},
    )

    if not chunk_records:
        return {
            "documents_processed": len(md_files),
            "chunks_total": 0,
            "chunks_added": 0,
            "chunks_skipped": 0,
        }

    all_ids = [chunk_id for chunk_id, _ in chunk_records]
    existing = vectorstore._collection.get(ids=all_ids, include=[])
    existing_ids = set(existing.get("ids", []))

    new_ids: list[str] = []
    new_docs: list[Document] = []
    for chunk_id, doc in chunk_records:
        if chunk_id not in existing_ids:
            new_ids.append(chunk_id)
            new_docs.append(doc)

    if new_docs:
        vectorstore.add_documents(documents=new_docs, ids=new_ids)

    return {
        "documents_processed": len(md_files),
        "chunks_total": len(chunk_records),
        "chunks_added": len(new_docs),
        "chunks_skipped": len(chunk_records) - len(new_docs),
    }


if __name__ == "__main__":
    stats = ingest_knowledge_base()
    print(
        f"Ingestion complete: {stats['documents_processed']} documents, "
        f"{stats['chunks_total']} total chunks, "
        f"{stats['chunks_added']} added, "
        f"{stats['chunks_skipped']} skipped (already indexed)."
    )
