#!/usr/bin/env python3
"""Preview or apply a non-destructive sort of files by extension."""

import argparse
import shutil
from pathlib import Path


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
    args = parser.parse_args()
    root = args.directory.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    moves = plan(root)
    if not moves:
        print("No files to organize.")
        return 0
    failed = 0
    for source, destination in moves:
        if destination.exists():
            print(f"SKIP collision: {source.name} -> {destination.relative_to(root)}")
            failed += 1
        elif args.apply:
            try:
                destination.parent.mkdir(exist_ok=True)
                shutil.move(str(source), str(destination))
                print(f"MOVED {source.name} -> {destination.relative_to(root)}")
            except OSError as exc:
                print(f"ERROR {source.name}: {exc}")
                failed += 1
        else:
            print(f"PLAN  {source.name} -> {destination.relative_to(root)}")
    if not args.apply:
        print("Preview only. Pass --apply to move these files.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
