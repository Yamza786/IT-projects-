#!/usr/bin/env python3
"""Keep a private, reviewable record of open-source contribution work."""

import argparse
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

DATA_PATH = Path(os.environ.get("CONTRIBUTIONS_FILE", "contributions.json"))


def read_entries() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read {DATA_PATH}: {exc}") from exc
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError("Contribution file must contain a JSON list of entries")
    return data


def valid_github_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.netloc.lower() == "github.com" and len(parsed.path.strip("/").split("/")) >= 4


def write_entries(entries: list[dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=DATA_PATH.name + ".", dir=DATA_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(entries, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, DATA_PATH)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def markdown(entries: list[dict]) -> str:
    if not entries:
        return "# Open-Source Contributions\n\nNo entries recorded yet.\n"
    out = ["# Open-Source Contributions", ""]
    for entry in sorted(entries, key=lambda x: x["date"], reverse=True):
        out += [f"## {entry['project']} — {entry['date']}", "", entry["summary"], ""]
        if entry.get("issue_url"):
            out.append(f"- Issue: {entry['issue_url']}")
        if entry.get("pr_url"):
            out.append(f"- Pull request: {entry['pr_url']}")
        if entry.get("review_status"):
            out.append(f"- Review status: {entry['review_status']}")
        if entry.get("verification"):
            out.append(f"- Verification: {entry['verification']}")
        if entry.get("verification_note"):
            out.append(f"- Verification note: {entry['verification_note']}")
        out += [f"- What I learned: {entry['lesson']}", ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="record a contribution")
    add.add_argument("--project", required=True)
    add.add_argument("--issue-url", default="")
    add.add_argument("--pr-url", default="")
    add.add_argument("--date", default=date.today().isoformat())
    add.add_argument("--summary", required=True)
    add.add_argument("--lesson", required=True)
    add.add_argument("--review-status", choices=("draft","in-review","changes-requested","approved","merged","closed"), default="draft")
    add.add_argument("--verification", choices=("unverified","reproduced","tested","reviewed"), default="unverified")
    add.add_argument("--verification-note", default="")
    commands.add_parser("list", help="list recorded entries")
    showcase = commands.add_parser("showcase", help="print a Markdown portfolio")
    showcase.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        entries = read_entries()
        if args.command == "add":
            try:
                date.fromisoformat(args.date)
            except ValueError:
                parser.error("--date must use YYYY-MM-DD format")
            if not args.issue_url and not args.pr_url:
                parser.error("provide --issue-url or --pr-url")
            for url in (args.issue_url, args.pr_url):
                if url and not valid_github_url(url):
                    parser.error("issue and pull request links must be HTTPS GitHub repository URLs")
            entries.append({"project": args.project.strip(), "issue_url": args.issue_url, "pr_url": args.pr_url,
                            "date": args.date, "summary": args.summary.strip(), "lesson": args.lesson.strip(),
                            "review_status":args.review_status,"verification":args.verification,
                            "verification_note":args.verification_note.strip()})
            write_entries(entries)
            print(f"Saved entry to {DATA_PATH}")
        elif args.command == "list":
            for entry in sorted(entries, key=lambda x: x["date"], reverse=True):
                print(f"{entry['date']} · {entry['project']} · {entry['summary']}")
            if not entries:
                print("No contributions recorded.")
        else:
            result = markdown(entries)
            if args.output:
                args.output.write_text(result, encoding="utf-8")
                print(f"Wrote {args.output}")
            else:
                print(result, end="")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
