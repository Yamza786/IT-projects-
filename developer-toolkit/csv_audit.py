#!/usr/bin/env python3
"""Audit CSV structure and completeness without printing cell contents."""

import argparse
import csv
import sys
from pathlib import Path


def audit(path: Path, required: list[str], max_issues: int) -> tuple[int, list[str]]:
    issues: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames
            if not headers:
                return 0, ["CSV has no header row"]
            if len(headers) != len(set(headers)):
                issues.append("Header names are not unique")
            missing = sorted(set(required) - set(headers))
            if missing:
                issues.append("Missing required columns: " + ", ".join(missing))
            row_count = 0
            duplicate_count = 0
            seen: set[tuple[str | None, ...]] = set()
            for row_number, row in enumerate(reader, start=2):
                row_count += 1
                if None in row and len(issues) < max_issues:
                    issues.append(f"Row {row_number}: more values than header columns")
                if any(not (row.get(name) or "").strip() for name in required if name in headers) and len(issues) < max_issues:
                    issues.append(f"Row {row_number}: required value is blank")
                key = tuple((row.get(name) or "").strip() for name in headers)
                if key in seen:
                    duplicate_count += 1
                seen.add(key)
            if duplicate_count:
                issues.append(f"Found {duplicate_count} duplicate row(s)")
        return row_count, issues[:max_issues]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Could not read CSV: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--required", nargs="*", default=[], metavar="COLUMN")
    parser.add_argument("--max-issues", type=int, default=50)
    args = parser.parse_args()
    if args.max_issues < 1:
        parser.error("--max-issues must be at least 1")
    if not args.csv_file.is_file():
        parser.error(f"not a file: {args.csv_file}")
    try:
        count, issues = audit(args.csv_file, args.required, args.max_issues)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"Rows inspected: {count}")
    if not issues:
        print("CSV audit passed")
        return 0
    print(f"Issues ({len(issues)}):")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
