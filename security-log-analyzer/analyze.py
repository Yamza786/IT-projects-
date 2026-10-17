#!/usr/bin/env python3
"""Summarize simple SSH authentication patterns in a local log file."""

import argparse
import ipaddress
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ADDRESS = re.compile(r"\bfrom\s+([0-9a-fA-F:.]+)\b")
FAILED = re.compile(r"Failed password|authentication failure|Invalid user")
ACCEPTED = re.compile(r"Accepted (?:password|publickey|keyboard-interactive)")


def analyze(path: Path, threshold: int) -> dict:
    counts = defaultdict(lambda: {"failures": 0, "successes": 0, "lines": []})
    total = 0
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, 1):
            if "sshd" not in line:
                continue
            match = ADDRESS.search(line)
            if not match:
                continue
            try:
                address = str(ipaddress.ip_address(match.group(1)))
            except ValueError:
                continue
            if FAILED.search(line):
                counts[address]["failures"] += 1
                counts[address]["lines"].append((line_number, "failure"))
                total += 1
            elif ACCEPTED.search(line):
                counts[address]["successes"] += 1
                counts[address]["lines"].append((line_number, "success"))
                total += 1
    alerts = []
    for address, events in sorted(counts.items()):
        failures, successes = events["failures"], events["successes"]
        if failures >= threshold:
            alerts.append({"rule": "repeated_failures", "severity": "high" if failures >= threshold * 2 else "medium",
                           "source": address, "failure_count": failures, "success_count": successes,
                           "evidence_lines": [n for n, _ in events["lines"] if _ == "failure"][:20]})
        if failures >= threshold and any(kind == "success" and line_no > max((n for n, kind in events["lines"] if kind == "failure"), default=0)
                                          for line_no, kind in events["lines"]):
            alerts.append({"rule": "success_after_failures", "severity": "high", "source": address,
                           "failure_count": failures, "success_count": successes,
                           "evidence_lines": [n for n, _ in events["lines"][-20:]]})
    return {"events_parsed": total, "unique_sources": len(counts), "threshold": threshold, "alerts": alerts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    parser.add_argument("--threshold", type=int, default=5, help="failure events needed for an alert (default: 5)")
    parser.add_argument("--json", type=Path, help="write the report as JSON")
    args = parser.parse_args()
    if args.threshold < 2:
        parser.error("--threshold must be at least 2")
    if not args.log_file.is_file():
        parser.error(f"not a file: {args.log_file}")
    try:
        report = analyze(args.log_file, args.threshold)
    except OSError as exc:
        print(f"Could not read log: {exc}", file=sys.stderr)
        return 2
    print(f"Parsed {report['events_parsed']} SSH events from {report['unique_sources']} source addresses")
    if not report["alerts"]:
        print("No configured rules fired")
    for alert in report["alerts"]:
        print(f"{alert['severity'].upper()} {alert['rule']} source={alert['source']} failures={alert['failure_count']} successes={alert['success_count']}")
    if args.json:
        try:
            args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Could not write report: {exc}", file=sys.stderr)
            return 2
    return 1 if report["alerts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
