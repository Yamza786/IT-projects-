#!/usr/bin/env python3
"""Validate a tidy public-data CSV and generate a standalone interactive report."""

import argparse
import csv
import html
import json
import math
import sys
from pathlib import Path

REQUIRED = {"area", "year", "indicator", "value"}


def read_data(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            missing = sorted(REQUIRED - set(reader.fieldnames or []))
            raise ValueError("Missing columns: " + ", ".join(missing))
        records, seen = [], set()
        for line_no, row in enumerate(reader, start=2):
            try:
                area = row["area"].strip()
                year = int(row["year"])
                indicator = row["indicator"].strip()
                value = float(row["value"])
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid area, year, indicator, or numeric value on row {line_no}") from exc
            if not area or not indicator or not 1800 <= year <= 2200 or not math.isfinite(value):
                raise ValueError(f"Invalid or empty value on row {line_no}")
            key = (area, year, indicator)
            if key in seen:
                raise ValueError(f"Duplicate observation for {area}, {year}, {indicator}")
            seen.add(key)
            records.append({"area": area, "year": year, "indicator": indicator, "value": value})
    if not records:
        raise ValueError("CSV contains no observations")
    return records


def build(records: list[dict], title: str, source: str) -> str:
    safe_json = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    safe_title, safe_source = html.escape(title), html.escape(source)
    template = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#172337;font:15px/1.5 system-ui,sans-serif}main{max-width:1000px;margin:auto;padding:30px 20px}.tag{font-size:12px;font-weight:700;letter-spacing:.12em;color:#356cc4}h1{font-size:clamp(30px,5vw,44px);margin:8px 0}section{background:white;border:1px solid #dde5f0;border-radius:14px;padding:18px;margin:16px 0}label{font-weight:650;margin-right:8px}select{font:inherit;padding:8px;border:1px solid #c9d5e5;border-radius:7px}canvas{width:100%;height:360px;border-radius:8px}table{width:100%;border-collapse:collapse}th,td{text-align:left;border-bottom:1px solid #e5ebf2;padding:8px}small,.muted{color:#60708a}a{color:#356cc4}@media(max-width:600px){canvas{height:260px}}
    </style></head><body><main><div class="tag">OPEN DATA · EXPLORATORY VIEW</div><h1>__TITLE__</h1><p>Source: __SOURCE__</p><section><label for="indicator">Indicator</label><select id="indicator"></select> <label for="year">Year</label><select id="year"></select><p class="muted">Descriptive comparison only. Differences may reflect definitions, population, or data quality.</p><canvas id="chart" aria-label="Bar chart comparing areas" role="img"></canvas></section><section><h2>Observations</h2><div style="overflow:auto"><table><thead><tr><th>Area</th><th>Year</th><th>Indicator</th><th>Value</th></tr></thead><tbody id="rows"></tbody></table></div></section><p class="muted">Generated as a standalone report. Verify source definitions, units, dates, and coverage before interpretation.</p></main><script>
    const data=__DATA__;const ind=document.getElementById('indicator'),yr=document.getElementById('year');const indicators=[...new Set(data.map(x=>x.indicator))].sort();const years=[...new Set(data.map(x=>x.year))].sort((a,b)=>b-a);indicators.forEach(x=>ind.add(new Option(x,x)));years.forEach(x=>yr.add(new Option(x,x)));function draw(){const subset=data.filter(x=>x.indicator===ind.value&&x.year===Number(yr.value));document.getElementById('rows').innerHTML=subset.map(x=>`<tr><td>${esc(x.area)}</td><td>${x.year}</td><td>${esc(x.indicator)}</td><td>${x.value}</td></tr>`).join('');const c=document.getElementById('chart'),dpr=window.devicePixelRatio||1,box=c.getBoundingClientRect();c.width=box.width*dpr;c.height=box.height*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,box.width,box.height);if(!subset.length){ctx.fillText('No values for this selection',20,30);return}const max=Math.max(...subset.map(x=>x.value),0),min=Math.min(...subset.map(x=>x.value),0),range=max-min||1;const pad=42,w=(box.width-pad*2)/subset.length;subset.forEach((x,i)=>{const h=(x.value-min)/range*(box.height-90);const xx=pad+i*w,yy=box.height-45-h;ctx.fillStyle='#5688db';ctx.fillRect(xx+8,yy,Math.max(8,w-16),h);ctx.fillStyle='#172337';ctx.font='12px system-ui';ctx.fillText(String(x.value),xx+8,yy-6);ctx.fillStyle='#60708a';ctx.fillText(x.area.slice(0,16),xx+8,box.height-20)})}function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}ind.onchange=yr.onchange=draw;window.onresize=draw;draw()
    </script></body></html>'''
    return template.replace("__TITLE__", safe_title).replace("__SOURCE__", safe_source).replace("__DATA__", safe_json)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="South African Open-Data Explorer")
    parser.add_argument("--source", required=True, help="publisher and dataset reference; identify synthetic data as such")
    args = parser.parse_args()
    try:
        report = build(read_data(args.csv_file), args.title, args.source)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Could not generate report: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
