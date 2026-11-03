# Fraud and Anomaly Detection Workbench

A deterministic Julia baseline scorer and analyst queue. It trains category-specific amount means and sample standard deviations on a separate history set, scores a new observation set, adds explicit device/country-change reasons, stores results in SQLite, and supports review and CSV export.

```sh
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. src/cli.jl
julia --project=. src/cli.jl --review tx-102 rejected data/fraud-workbench.sqlite
julia --project=. src/cli.jl --export review.csv data/fraud-workbench.sqlite
julia --project=. -e 'using Pkg; Pkg.test()'
```

The default run uses an embedded synthetic history and synthetic observations. It never uses live account data. Scores are descriptive flags rather than fraud findings: `unusual_amount` uses an absolute z-score threshold of 3, while new-device and country-change indicators add review reasons. Categories without training history fail closed. For a category with zero variance, a different amount receives a capped z-score of 20.

## CSV input

`parse_csv(path)` accepts a UTF-8, unquoted six-column file with this exact header:

```text
transaction_id,amount_cents,category,hour_utc,new_device,country_change
```

Input is capped at 8 MiB/10,000 rows. IDs and categories use bounded ASCII identifiers; amounts use integer cents. Training history and scored observations must remain separate to avoid baseline leakage. SQLite stores the score, reasons and a `pending/accepted/rejected` analyst state. CSV exports include synthetic or user-supplied data; handle the output under the same privacy policy as the source.

CI instantiates Julia dependencies, runs reproducibility, validation, SQL persistence, review and CSV parsing tests. This MVP is not a production fraud model: it has no calibrated probabilities, fairness analysis, identity resolution, streaming ingestion, model governance or regulatory review. Never auto-decline a customer based only on these flags.
