# AI IT Helpdesk Assistant

A small support assistant that searches a curated local troubleshooting knowledge base, returns matched steps with article citations, and records tickets. The default mode is offline and deterministic. An optional OpenAI-compatible chat endpoint can be configured, but the assistant always includes the retrieved references and should not receive secrets or personal data.

## Run

```sh
python app.py
```

Open `http://127.0.0.1:8081/docs` for the API. `POST /ask` accepts `{"question":"Wi-Fi has no internet"}`; `POST /tickets` records a ticket. Set `HELPDESK_DB` for the SQLite path. Set `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` to enable optional remote generation.

## Limits

Retrieval is a small keyword baseline, not a trained model. This is not an autonomous admin agent: it never runs commands or changes a machine. Confirm advice against organizational procedures.
