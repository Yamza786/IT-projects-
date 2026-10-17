# Research and Knowledge Assistant

A local document search tool that returns short, traceable evidence passages for a question. Retrieval uses sentence-level lexical matching; when it cannot find relevant passages, it says so and records the unanswered question for review.

An optional OpenAI-compatible local or HTTPS chat endpoint can generate a grounded answer from the retrieved passages. Generation is off unless both `RESEARCH_LLM_URL` and `RESEARCH_LLM_MODEL` are configured; `RESEARCH_LLM_KEY` is optional. Without it, the app returns citations and retrieval-only status. When configured, source excerpts are sent to that endpoint, so use a local model or only material approved for that provider.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` to add text documents and search. API docs: `/docs`. Set `RESEARCH_DB` for the SQLite path. Only add material you are authorized to store; this is a local demo without accounts or encryption.

## API

- `POST /api/documents` with `{ "title": "...", "text": "...", "source_uri": "...", "accessed_on": "YYYY-MM-DD" }`
- `GET /api/documents`
- `GET /api/documents/{id}/summary` — extractive sentence selection, with source sentence indices
- `DELETE /api/documents/{id}`
- `POST /api/ask` with `{ "question": "...", "limit": 5 }`
- `GET /api/unanswered`

Each result cites a document ID, title, optional source URI/access date, and exact stored passage. This is retrieval support, not a substitute for reading source material.
