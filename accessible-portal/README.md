# Accessible Multilingual Services Portal

A content-managed starter for public information in South African languages. Each entry is attached to an HTTPS source and a verification date. The portal does not ship unverified legal, financial, or government claims; add reviewed public information from official sources.

## Run

```sh
python -m pip install -r ../requirements-termux.txt
uvicorn app.main:app --reload
```

Open `/` to browse and add reviewed entries, `/docs` for the API. Set `PORTAL_DB` to change the SQLite file. Supported language codes: English (`en`), Afrikaans (`af`), isiZulu (`zu`), isiXhosa (`xh`), Sesotho (`st`), Sepedi (`nso`), Setswana (`tn`), siSwati (`ss`), Tshivenda (`ve`), and Xitsonga (`ts`).

The page includes semantic landmarks, a skip link, keyboard-accessible controls, visible focus states, responsive layout, and status announcements. Translation should be reviewed by fluent speakers.
