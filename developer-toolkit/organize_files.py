#!/usr/bin/env python3
"""Preview or apply a non-destructive sort of files by extension."""

import argparse
import shutil
from pathlib import Path
from jsonl_log import append_event


def plan(directory: Path) -> list[tuple[Path, Path]]:
    moves = []
    for source in sorted(directory.iterdir(), key=lambda p: p.name.casefold()):
        if not source.is_file():
            continue
        folder = source.suffix.lower().lstrip(".") or "_no_extension"
        destination = directory / folder / source.name
        moves.append((source, destination))
    return moves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--apply", action="store_true", help="perform the moves; default is preview only")
    parser.add_argument("--log-jsonl", type=Path, help="append private operational events to this JSONL file")
    args = parser.parse_args()
    root = args.directory.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    moves = plan(root)
    if not moves:
        print("No files to organize.")
        append_event(args.log_jsonl,"file_organization_finished",mode="apply" if args.apply else "preview",planned=0,moved=0,failed=0)
        return 0
    failed = moved = 0
    for source, destination in moves:
        if destination.exists():
            print(f"SKIP collision: {source.name} -> {destination.relative_to(root)}")
            failed += 1
            append_event(args.log_jsonl,"file_move_skipped",source=source.name,destination=destination.relative_to(root).as_posix(),reason="collision")
        elif args.apply:
            try:
                destination.parent.mkdir(exist_ok=True)
                shutil.move(str(source), str(destination))
                print(f"MOVED {source.name} -> {destination.relative_to(root)}")
                moved += 1
                append_event(args.log_jsonl,"file_moved",source=source.name,destination=destination.relative_to(root).as_posix())
            except OSError as exc:
                print(f"ERROR {source.name}: {exc}")
                failed += 1
                append_event(args.log_jsonl,"file_move_failed",source=source.name,error_type=type(exc).__name__)
        else:
            print(f"PLAN  {source.name} -> {destination.relative_to(root)}")
            append_event(args.log_jsonl,"file_move_planned",source=source.name,destination=destination.relative_to(root).as_posix())
    if not args.apply:
        print("Preview only. Pass --apply to move these files.")
    append_event(args.log_jsonl,"file_organization_finished",mode="apply" if args.apply else "preview",planned=len(moves),moved=moved,failed=failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
