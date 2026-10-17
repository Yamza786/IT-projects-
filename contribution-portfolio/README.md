# Open-Source Contribution Portfolio

A small local journal for documenting contribution work: issue reproduction, proposed fixes, pull requests, review feedback, and lessons. It stores a JSON file on the user's machine and does not call GitHub or publish anything.

## Record an entry

```sh
python contributions.py add \
  --project 'sample-project' \
  --issue-url 'https://github.com/example/project/issues/12' \
  --pr-url 'https://github.com/example/project/pull/34' \
  --date 2026-10-17 \
  --summary 'Fixed a reproducible input parsing edge case' \
  --lesson 'Added a focused regression case after reading the existing parser flow'
```

Entries are written to `contributions.json` in the current directory by default. Set `CONTRIBUTIONS_FILE` to choose another path; keep that file out of public repositories until its contents are reviewed.

Commands: `add`, `list`, and `showcase`. The showcase output is Markdown for manual editing and review. Links must point to GitHub issue or pull request pages.

## Contribution reflection template

For each item, record the observable behavior, reproduction steps, root cause, focused change, verification performed, reviewer feedback, and what you learned. Do not claim authorship for work you did not do.
