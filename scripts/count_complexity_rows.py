#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def is_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if not set(stripped) <= set("|-: "):
        return False
    return "-" in stripped


def count_tables(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    total = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and "Time" in line and "Space" in line and "Notes" in line:
            if i + 1 < len(lines) and is_separator(lines[i + 1]):
                i += 2
                while i < len(lines):
                    row = lines[i].strip()
                    if not row.startswith("|") or row == "|":
                        break
                    if not is_separator(row):
                        total += 1
                    i += 1
                continue
        i += 1
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count complexity table rows (Time/Space/Notes) in docs."
    )
    parser.add_argument(
        "--root",
        default="docs",
        help="Root docs directory to scan (default: docs).",
    )
    args = parser.parse_args()

    root = Path(args.root)
    counts = {path: count_tables(path) for path in root.rglob("*.md")}

    total_rows = sum(counts.values())
    files_with_rows = sum(1 for v in counts.values() if v)

    def sum_for(subdir: str) -> int:
        return sum(v for p, v in counts.items() if p.parts[:2] == (root.name, subdir))

    print(f"total_rows {total_rows}")
    print(f"total_files_with_rows {files_with_rows}")
    print(f"builtins_rows {sum_for('builtins')}")
    print(f"stdlib_rows {sum_for('stdlib')}")
    print(f"versions_rows {sum_for('versions')}")
    print(f"implementations_rows {sum_for('implementations')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
