#!/usr/bin/env python3
"""Summarize simple SSH authentication patterns in a local log file."""

import argparse
import hashlib
import ipaddress
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ADDRESS = re.compile(r"\b(?:from\s+|rhost=)([0-9a-fA-F:.]+)\b")
FAILED = re.compile(r"Failed password|authentication failure|Invalid user")
ACCEPTED = re.compile(r"Accepted (?:password|publickey|keyboard-interactive)")


def analyze(path: Path, threshold: int, suppress: set[str] | None = None) -> dict:
    counts = defaultdict(lambda: {"failures": 0, "successes": 0, "lines": []})
    timeline = []
    suppressed = suppress or set()
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
                timeline.append({"line":line_number,"source":address,"event":"authentication_failure"})
                total += 1
            elif ACCEPTED.search(line):
                counts[address]["successes"] += 1
                counts[address]["lines"].append((line_number, "success"))
                timeline.append({"line":line_number,"source":address,"event":"authentication_success"})
                total += 1
    alerts = []
    for address, events in sorted(counts.items()):
        if address in suppressed:
            continue
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
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"events_parsed": total, "unique_sources": len(counts), "threshold": threshold,
            "suppressed_sources": sorted(suppressed & set(counts)), "input_sha256": digest,
            "timeline": timeline, "alerts": alerts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    parser.add_argument("--threshold", type=int, default=5, help="failure events needed for an alert (default: 5)")
    parser.add_argument("--rules", type=Path, help="JSON rule pack with threshold and suppressed_sources")
    parser.add_argument("--json", type=Path, help="write the report as JSON")
    parser.add_argument("--suppress", action="append", default=[], metavar="IP", help="suppress alerts for a reviewed address; may be repeated")
    parser.add_argument("--note", action="append", default=[], help="include an incident-response note in the JSON report; may be repeated")
    args = parser.parse_args()
    threshold=args.threshold
    rule_suppress=[]
    if args.rules:
        try:
            config=json.loads(args.rules.read_text(encoding="utf-8"))
            if not isinstance(config,dict) or set(config)-{"threshold","suppressed_sources"}:
                raise ValueError("rule pack only accepts threshold and suppressed_sources")
            threshold=config.get("threshold",threshold)
            rule_suppress=config.get("suppressed_sources",[])
            if isinstance(threshold,bool) or not isinstance(threshold,int) or threshold<2:
                raise ValueError("threshold must be an integer of at least 2")
            if not isinstance(rule_suppress,list) or any(not isinstance(value,str) for value in rule_suppress):
                raise ValueError("suppressed_sources must be an array of IP strings")
        except (OSError,json.JSONDecodeError,ValueError) as exc:
            parser.error(f"invalid rule pack: {exc}")
    if threshold < 2:
        parser.error("--threshold must be at least 2")
    if not args.log_file.is_file():
        parser.error(f"not a file: {args.log_file}")
    try:
        suppress = {str(ipaddress.ip_address(value)) for value in [*args.suppress,*rule_suppress]}
    except ValueError as exc:
        parser.error(f"invalid --suppress address: {exc}")
    try:
        report = analyze(args.log_file, threshold, suppress)
    except OSError as exc:
        print(f"Could not read log: {exc}", file=sys.stderr)
        return 2
    print(f"Parsed {report['events_parsed']} SSH events from {report['unique_sources']} source addresses")
    if not report["alerts"]:
        print("No configured rules fired")
    for event in report["timeline"]:
        print(f"line {event['line']} {event['event']} source={event['source']}")
    for alert in report["alerts"]:
        print(f"{alert['severity'].upper()} {alert['rule']} source={alert['source']} failures={alert['failure_count']} successes={alert['success_count']}")
    if args.json:
        try:
            report["incident_notes"] = args.note
            args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Could not write report: {exc}", file=sys.stderr)
            return 2
    return 1 if report["alerts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
