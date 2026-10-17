# Accessible Multilingual Services Portal

A content-managed starter for public information in South African languages. Each entry is attached to an HTTPS source and a verification date. The portal does not ship unverified legal, financial, or government claims; add reviewed public information from official sources.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` to browse and add reviewed entries, `/docs` for the API. Set `PORTAL_DB` to change the SQLite file. Supported language codes: English (`en`), Afrikaans (`af`), isiZulu (`zu`), isiXhosa (`xh`), Sesotho (`st`), Sepedi (`nso`), Setswana (`tn`), siSwati (`ss`), Tshivenda (`ve`), and Xitsonga (`ts`).

Optionally seed four English-language links to official employment and education information with `python seed_resources.py --db portal.db`. These summaries were checked on 2026-10-17 and avoid time-sensitive vacancy or application claims. The seed command is idempotent and does not overwrite locally edited records. It does not provide translations; add non-English entries only after fluent-speaker review and record a new source-verification date. Review [sample-resources.json](sample-resources.json) for the complete list and provenance dates.

The page includes semantic landmarks, a skip link, keyboard-accessible controls, visible focus states, responsive layout, and status announcements. Non-English entries with no reviewer metadata are held in `GET /api/translation-review-queue` and excluded from public browsing. Add a fluent reviewer ID and reviewed date on creation, or use `POST /api/resources/{id}/translation-review` to approve the translation after checking it. `verified_on` tracks the official source, separately from the translation review date.

Set a strong `PORTAL_EDITOR_KEY` environment variable before starting the server. Resource creation, translation review queue access, and translation approval require it via `X-Editor-Key`; the page asks for the key when saving. Public browsing stays read-only. Store the key in the hosting platform secret manager, never in source control.
