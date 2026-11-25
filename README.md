# HealthTrack AI

HealthTrack AI is a patient symptom tracking, analytics, and health education application built with FastAPI, SQLAlchemy, SQLite, Streamlit, Plotly, ChromaDB, LangChain, and Gemini.

## Retrieval-Augmented Generation (RAG) Health Education Assistant

### What RAG Is and How It Works Here
Retrieval-Augmented Generation (RAG) grounds LLM responses in a curated set of reference documents rather than relying solely on the model's pretraining memory. In HealthTrack AI:

1. Curated MedlinePlus Markdown documents in `backend/app/rag/knowledge/` are split into ~500-character chunks with 75-character overlap.
2. Each chunk is embedded locally and stored in a persistent ChromaDB collection (`chroma_db/`).
3. When a user asks a question via `POST /rag/ask` (or the **AI Health Education Assistant** section in Streamlit), the retriever embeds the question and fetches the top 3 most semantically similar chunks above a relevance threshold.
4. If no chunks meet the relevance threshold, the API returns a safe fallback message without calling Gemini.
5. Otherwise, the retrieved chunks and their source metadata are passed to Gemini via LangChain with strict non-diagnostic grounding instructions, returning an answer with clickable source citations.

### Why Local Embeddings Are Used
The RAG pipeline uses the local Sentence Transformers model `sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface` (`backend/app/rag/embeddings.py`). Running embeddings locally means:
- Document ingestion and similarity search do **not** consume Gemini API quota.
- Indexing can be re-run offline or in CI without external embedding API calls.

### How ChromaDB Stores and Retrieves Chunks
- `backend/app/rag/ingest.py` stores chunks in the `health_education` collection inside `chroma_db/` using cosine similarity (`hnsw:space: cosine`).
- Deterministic SHA-256 chunk IDs prevent duplicate records when ingestion is run multiple times.
- Patient symptom logs are stored strictly in SQLite and are **never** stored in ChromaDB.
- `backend/app/rag/retriever.py` queries the top 3 chunks using `similarity_search_with_relevance_scores` and filters out low-relevance matches (`score < 0.30`).

### How to Ingest Documents
Run the ingestion script from the repository root:

```bash
.venv/bin/python -m backend.app.rag.ingest
```

Re-running the command skips already-indexed chunks so no duplicates are created.

### How Source Citations Work
Every curated Markdown document in `backend/app/rag/knowledge/` includes `title` and `url` frontmatter metadata. During chunking, `source_title` and `source_url` are attached to every chunk in ChromaDB. After retrieval, `backend/app/rag/chains.py` deduplicates those citations and returns them in the `sources` array of `POST /rag/ask`, which the Streamlit UI renders as clickable links.

## Running the Application

Start the FastAPI backend:
```bash
.venv/bin/uvicorn backend.app.main:app --reload
```

Start the Streamlit frontend in a second terminal:
```bash
.venv/bin/streamlit run frontend/app.py
```

## Running Tests

Run the full backend test suite (uses isolated temporary SQLite and ChromaDB directories and mocked Gemini calls — no paid API requests are made):
```bash
.venv/bin/pytest -v backend/tests
```
