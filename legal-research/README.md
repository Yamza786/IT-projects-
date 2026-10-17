# Legal Research and Case Management Toolkit

A local research organizer for cases, source records, source-linked research notes, document versions, and deadlines. It keeps source passage text beside the citation so a researcher can return to the exact material. It does not generate legal advice or make legal conclusions.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` or `/docs`. Set `LEGAL_DB` to change the SQLite path. The included interface uses only synthetic case data entered by the user. Avoid confidential or privileged information in this demo.

## API

- `POST|GET /api/cases`
- `POST|GET /api/sources`
- `POST|GET /api/notes`
- `POST /api/deadlines`
- `GET /api/deadlines?from=YYYY-MM-DD&to=YYYY-MM-DD`

Each source should include the issuing body, title, URL or collection identifier, publication date if known, and access date. Verify current law from an authoritative source.
