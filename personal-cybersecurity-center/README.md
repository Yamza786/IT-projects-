# Personal Cybersecurity Command Center

A local-first defensive console for reviewing authentication logs, recording alerts, and keeping incident notes. It deliberately reuses the transparent parser from [Security Log Analyzer](../security-log-analyzer/README.md) rather than hiding detection logic.

## Run

```sh
python app.py ingest ../security-log-analyzer/sample-auth.log
python app.py alerts
python app.py note 1 "Reviewed; source is a synthetic training address"
```

The SQLite database defaults to `./security-center.db`; set `SECURITY_CENTER_DB` to choose another path. Ingest stores the report summary and alert records, not raw log lines. Re-ingesting the same file hash is idempotent. `alerts` lists unresolved findings; `note` records review context and closes that alert.

## Boundaries

Local prototype, not an EDR/SIEM or real-time monitor. It only recognizes the SSH/PAM patterns documented by the analyzer. Protect the database as incident data, preserve source evidence separately, and only inspect systems you are authorized to administer.
