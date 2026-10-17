# Developer and Office Automation Toolkit

See [RECOVERY.md](RECOVERY.md) for backup verification and restore guidance.

For optional structured operational history, pass `--log-jsonl /path/to/operations.jsonl` to `organize_files.py` or `backup.py`. Events omit file contents and write with owner-only permissions on POSIX systems. Keep logs private because relative filenames may still reveal personal information.

Small Python utilities for repetitive file and spreadsheet work. Tools are safe by default: file organization prints a plan unless `--apply` is passed. The examples operate on user-selected paths and never delete source files.

## Requirements

Python 3.10 or newer. The scripts use only the standard library.

## CSV audit

Check headers, duplicate records, and incomplete rows:

```sh
python csv_audit.py contacts.csv --required name,email --max-issues 20
```

Create an aggregate Markdown report without including the source rows:

```sh
python csv_report.py timesheet.csv --group department --value hours --output weekly-report.md
```

Exit code is `0` when no issues are found, `1` when the CSV has issues, and `2` for an input or usage error. Values are not printed, so reports do not expose row contents.

## Organize files by extension

Preview the proposed moves:

```sh
python organize_files.py ~/Downloads
```

Apply the moves after reviewing the preview:

```sh
python organize_files.py ~/Downloads --apply
```

Files with no extension go into `_no_extension`. Name collisions are skipped and reported. The tool only considers files directly inside the selected directory.

## Create a timestamped backup

```sh
python backup.py ~/Documents ~/Backups
```

This creates a ZIP archive and a SHA-256 sidecar manifest. The source is read-only; the destination must be outside the source directory. Restore by extracting the archive with a standard ZIP utility.

## Design notes

- Preview before changing file locations.
- Never overwrite a collision or delete an original.
- Report errors with nonzero status for automation.
- Keep sensitive files and backups out of Git repositories.
