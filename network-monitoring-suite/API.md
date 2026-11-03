# CLI and result format

The executable accepts one target host and optional bounded checks:

| Flag | Required | Meaning |
|---|---|---|
| `-target HOST` | Yes | One IPv4/IPv6 literal or DNS hostname that the operator is authorized to check |
| `-tcp PORT` | No | One integer TCP port from 1 through 65535 |
| `-http URL` | No | One HTTP(S) URL whose hostname exactly matches `-target` |
| `-timeout DURATION` | No | Timeout per probe, from 100ms through 10s (default 3s) |

The program writes a JSON array to stdout. Each record has `target`, `check`, `ok`, and `duration_ms`; failed checks include an `error` string. HTTP redirects are returned as reachable responses and never followed. HTTP status codes 500 and above are reported as failures. Invalid command-line values exit with status 2; successful report generation exits 0 even if one probe failed, so automation should inspect each `ok` field.

The CLI never accepts CIDR blocks or port ranges. Do not use it against systems without authorization.
