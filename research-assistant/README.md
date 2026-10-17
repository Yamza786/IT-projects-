# Research and Knowledge Assistant

A local document search tool that returns short, traceable evidence passages for a question. The first release uses sentence-level lexical retrieval rather than an embedding service or generative model. It never invents a prose answer: when it cannot find relevant passages, it says so and records the unanswered question for review.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` to add text documents and search. API docs: `/docs`. Set `RESEARCH_DB` for the SQLite path. Only add material you are authorized to store; this is a local demo without accounts or encryption.

## API

- `POST /api/documents` with `{ "title": "...", "text": "..." }`
- `GET /api/documents`
- `POST /api/ask` with `{ "question": "...", "limit": 5 }`
- `GET /api/unanswered`

Each result cites a document ID, title, and exact stored passage. This is retrieval support, not a substitute for reading source material.
