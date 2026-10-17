# South African Open-Data Intelligence

A dependency-free CSV-to-dashboard tool for exploring public datasets. It validates a small, documented schema and builds a standalone HTML report with filters and an interactive chart. Users must supply the dataset and cite its source; the demo does not invent statistics or claim that correlation implies causation.

## Input format

CSV columns: `area,year,indicator,value`. Include one observation per area, year, and indicator. Example:

```csv
area,year,indicator,value
Example District,2022,Example measure,12.4
Example District,2023,Example measure,14.1
```

The example values above are synthetic. Generate a report:

```sh
python dashboard.py sample.csv report.html --title "Example analysis" --source "Synthetic sample"
```

For real data, the command also requires source URL, access date, units, indicator definitions, geographic coverage, and missing-data handling. These values appear in the report provenance block:

```sh
python dashboard.py data.csv report.html --source "Publisher · Dataset name" \
  --source-url "https://example.org/dataset" --accessed-on 2026-10-17 \
  --units "people" --definitions "Resident population at year end" \
  --coverage "South African provinces" --missing-data "Blank values excluded; none imputed"
```

Open the generated HTML file in a browser. The tool runs locally and embeds the supplied data in the report.

## Responsible interpretation

Record the publisher, dataset URL, access date, units, definitions, missing-data handling, and geographic coverage. Check whether comparisons use the same definitions and population. This descriptive dashboard does not establish causality.
