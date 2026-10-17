#!/usr/bin/env python3
"""Create a grouped numeric summary report from a CSV without copying raw rows."""

import argparse
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


def summarize(path: Path, group_column: str, value_column: str) -> tuple[int, list[dict]]:
    groups: dict[str, list[Decimal]] = defaultdict(list)
    row_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or group_column not in reader.fieldnames or value_column not in reader.fieldnames:
            raise ValueError("CSV must contain the selected group and value columns")
        for line,row in enumerate(reader,start=2):
            row_count+=1
            group=(row.get(group_column) or "").strip() or "(blank)"
            try:
                value=Decimal((row.get(value_column) or "").strip())
            except InvalidOperation:
                continue
            if not value.is_finite():
                raise ValueError(f"Non-finite number on row {line}")
            groups[group].append(value)
    result=[]
    for group,values in sorted(groups.items(),key=lambda pair:pair[0].casefold()):
        total=sum(values,Decimal(0))
        result.append({"group":group,"valid_values":len(values),"sum":total,
                       "mean":total/len(values),"min":min(values),"max":max(values)})
    return row_count,result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file",type=Path)
    parser.add_argument("--group",required=True,help="column to group by")
    parser.add_argument("--value",required=True,help="numeric column to summarize")
    parser.add_argument("--output",type=Path,help="write Markdown report to a file")
    args=parser.parse_args()
    if not args.csv_file.is_file():
        parser.error(f"not a file: {args.csv_file}")
    try:
        rows,summary=summarize(args.csv_file,args.group,args.value)
    except (OSError,UnicodeError,csv.Error,ValueError) as exc:
        print(f"Could not create report: {exc}",file=sys.stderr)
        return 2
    lines=[f"# CSV summary: {args.value} by {args.group}","",f"Rows scanned: {rows}","",
           f"| {args.group} | Count | Sum | Mean | Min | Max |","|---|---:|---:|---:|---:|---:|"]
    for item in summary:
        cells=[item["group"],str(item["valid_values"]),*(str(item[key]) for key in ("sum","mean","min","max"))]
        lines.append("| " + " | ".join(cell.replace("|","\\|").replace("\n"," ") for cell in cells) + " |")
    report="\n".join(lines)+"\n"
    if args.output:
        try:
            args.output.write_text(report,encoding="utf-8")
        except OSError as exc:
            print(f"Could not write report: {exc}",file=sys.stderr)
            return 2
        print(f"Wrote {args.output}")
    else:
        print(report,end="")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
