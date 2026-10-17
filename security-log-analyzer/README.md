# Security Log Analyzer

A defensive, offline analyzer for SSH authentication log exports. It flags repeated failed logins by source address and successful logins from an address with repeated failures in the same file. The heuristic is intentionally transparent and will produce false positives; it is not an intrusion detection system.

## Use

```sh
python analyze.py sample-auth.log --threshold 5 --json report.json
```

Include a source timeline, input SHA-256, reviewed suppressions, and response notes in the JSON report:

```sh
python analyze.py auth.log --suppress 192.0.2.44 --note "Reviewed against the approved maintenance window" --json incident.json
```

Load a reviewed local rule pack with `--rules rules.example.json`. The supported JSON fields are `threshold` and `suppressed_sources`. The parser accepts OpenSSH `from ADDRESS` and PAM `rhost=ADDRESS` forms; review suppressions because they hide alerts for matching IPs.

Input is read only. Output includes rule, source address, counts, and a severity label; it does not retain usernames or raw log lines. Addresses in the sample file are documentation-only examples.

## Rules and limits

- `repeated_failures`: at least N parsed SSH failure events for one address.
- `success_after_failures`: at least N failure events and a later accepted SSH event from the same address.
- Parses common OpenSSH `Failed password`, `Invalid user`, and `Accepted` records.
- Does not parse every platform's logs, infer malicious intent, or contact any network host.
- Tune thresholds for the environment and investigate alerts using authorized evidence.
- Suppression removes a source from alerts but keeps its events in the timeline; record the reason for each suppression.

## Incident response note template

Record the time window, systems in scope, evidence location and hash, authorized response actions, false-positive rationale, and follow-up owner. Preserve original logs and follow the organization's incident process.
