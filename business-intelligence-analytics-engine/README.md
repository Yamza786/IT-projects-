# Business Intelligence and Analytics Engine

This R and SQL workbench imports validated transaction exports into a local SQLite warehouse, computes reproducible monthly category metrics, and reports basic data-quality totals. It addresses the need to turn inconsistent CSV exports into explainable metrics while preserving exact integer-cent arithmetic.

## Features

- SQL migrations create a constrained transaction table, migration checksum ledger and monthly category view.
- R validates the entire CSV before a transaction, rejects invalid dates/amounts/identifiers, and prevents conflicting reuse of transaction IDs.
- Re-imports of identical rows are idempotent; any conflicting row rolls the whole import back.
- Reports and quality output are stable CSV; success events are structured JSON lines.
- Synthetic fixture data only; no real personal or financial data is included.

## Setup

Requires R 4.4+, SQLite (bundled through RSQLite), and packages DBI, RSQLite, and testthat.

```sh
Rscript -e 'install.packages(c("DBI", "RSQLite", "testthat"), repos="https://cloud.r-project.org")'
Rscript tests/testthat.R
```

Set `BI_DATABASE` to a file path, or pass `--db PATH`. The default path is `./build/analytics.sqlite`; created parent directories are private on Unix and the database is chmod `0600` when supported.

## Demonstration

Run from the project directory:

```sh
Rscript scripts/bi.R init
Rscript scripts/bi.R import --csv fixtures/transactions.synthetic.csv
Rscript scripts/bi.R import --csv fixtures/transactions.synthetic.csv
Rscript scripts/bi.R report --month 2026-01
Rscript scripts/bi.R quality
```

The repeated import reports zero newly inserted rows. The report emits `month,category,direction,transaction_count,amount_cents`; amounts remain integer cents to avoid floating-point rounding. No screenshot is included for this command-line workflow; the commands above reproduce it. `docker build -t portfolio-bi .` provides a container image with R and the runtime packages.

## Input contract and architecture

The CSV must contain exactly these columns, in this order: `transaction_id,booked_on,amount_cents,direction,category,source_id`. Dates use valid `YYYY-MM-DD`, amounts are positive integer cents up to 100,000,000,000, direction is `income` or `expense`, and string sizes are bounded. `transaction_id` must be unique within a file and is the idempotency key across imports.

```text
scripts/bi.R -> R/analytics.R -> DBI/RSQLite -> SQL migration ledger + SQLite view
```

The import validates every row before opening the write transaction. Applied migrations are tracked by filename and digest; modifying an applied migration fails closed. The summary view groups by calendar month, category, and direction. SQL views keep metric definitions explicit and reviewable.

## Security, limitations and future work

The program never fetches remote data, stores credentials, or sends analytics. Use only exports you are authorized to process. Protect the database and generated reports as financial data, keep backups encrypted, and never commit local SQLite files. SQLite's local file permissions are not application-level encryption; this tool does not protect against a compromised account or device.

This MVP has no dashboard, multi-user authorization, source-specific connectors, FX conversion, budget forecasting, incremental change data capture, or formal data catalog. It is designed for small local datasets and reproducible demonstrations, not enterprise financial reporting. The GitHub workflow runs synthetic import/report tests; no deployment or real-data validation is claimed.

## Contribution

Add synthetic fixtures and tests for each new metric or source adapter. Run `Rscript tests/testthat.R` and the CLI walkthrough before submitting. Keep source identifiers synthetic and migrate schema changes forward with new numbered SQL files.
