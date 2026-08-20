#!/usr/bin/env python3
"""Validate localized documentation against its English source.

Translations live in ``docs/<locale>/`` and mirror the English tree at
``docs/``. This script checks that each translated page:

* has an English counterpart,
* carries ``source_sha`` front matter matching that counterpart (staleness),
* preserves code blocks, table shape, heading structure, and link targets.

Usage::

    python scripts/validate_translations.py               # all locales
    python scripts/validate_translations.py fi            # one locale
    python scripts/validate_translations.py --update-hashes fi
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Locales that have a docs/<locale>/ tree. Keep in sync with mkdocs.yml.
LOCALES = ["fi", "zh"]

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
FRONT_MATTER_RE = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n", re.DOTALL)


@dataclass
class Structure:
    """Structural fingerprint of a markdown document."""

    code_blocks: list[str] = field(default_factory=list)
    heading_levels: list[int] = field(default_factory=list)
    table_rows: int = 0
    link_targets: list[str] = field(default_factory=list)


def split_front_matter(text: str) -> tuple[dict[str, object], str]:
    """Return (metadata, body) for a markdown document."""
    match = FRONT_MATTER_RE.match(text)
    if match is None:
        return {}, text
    loaded = yaml.safe_load(match.group("yaml")) or {}
    meta: dict[str, object] = loaded if isinstance(loaded, dict) else {}
    return meta, text[match.end() :]


def analyze(body: str) -> Structure:
    """Extract the structural fingerprint used to compare translations."""
    structure = Structure()
    open_fence: str | None = None
    buffer: list[str] = []

    for line in body.splitlines():
        fence_match = FENCE_RE.match(line)
        if open_fence is not None:
            # Only a fence of the same character and at least the same length closes.
            if (
                fence_match is not None
                and fence_match.group("fence")[0] == open_fence[0]
                and len(fence_match.group("fence")) >= len(open_fence)
                and not fence_match.group("info").strip()
            ):
                structure.code_blocks.append("\n".join(buffer))
                buffer = []
                open_fence = None
            else:
                buffer.append(line)
            continue

        if fence_match is not None:
            open_fence = fence_match.group("fence")
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match is not None:
            structure.heading_levels.append(len(heading_match.group("hashes")))
        if line.lstrip().startswith("|"):
            structure.table_rows += 1
        structure.link_targets.extend(LINK_RE.findall(line))

    if open_fence is not None:
        structure.code_blocks.append("\n".join(buffer))

    return structure


def compare(source: Structure, target: Structure) -> list[str]:
    """Return human-readable differences between two structures."""
    problems: list[str] = []

    if source.code_blocks != target.code_blocks:
        if len(source.code_blocks) != len(target.code_blocks):
            problems.append(
                f"code block count differs: English has {len(source.code_blocks)}, "
                f"translation has {len(target.code_blocks)}"
            )
        else:
            pairs = zip(source.code_blocks, target.code_blocks, strict=True)
            for index, (a, b) in enumerate(pairs):
                if a != b:
                    problems.append(f"code block {index + 1} was modified (code must stay verbatim)")

    if source.heading_levels != target.heading_levels:
        problems.append(
            f"heading structure differs: English {source.heading_levels} "
            f"vs translation {target.heading_levels}"
        )

    if source.table_rows != target.table_rows:
        problems.append(
            f"table row count differs: English has {source.table_rows}, "
            f"translation has {target.table_rows}"
        )

    missing = sorted(set(source.link_targets) - set(target.link_targets))
    added = sorted(set(target.link_targets) - set(source.link_targets))
    if missing:
        problems.append(f"link targets missing from translation: {', '.join(missing)}")
    if added:
        problems.append(f"link targets not present in English: {', '.join(added)}")

    return problems


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def english_counterpart(translated: Path, locale: str) -> Path:
    return DOCS_DIR / translated.relative_to(DOCS_DIR / locale)


def translated_pages(locale: str) -> list[Path]:
    locale_dir = DOCS_DIR / locale
    if not locale_dir.is_dir():
        return []
    return sorted(locale_dir.rglob("*.md"))


def validate_locale(locale: str) -> tuple[int, list[str]]:
    """Validate one locale. Returns (page count, error messages)."""
    errors: list[str] = []
    pages = translated_pages(locale)

    for page in pages:
        rel = page.relative_to(DOCS_DIR)
        source = english_counterpart(page, locale)

        if not source.exists():
            errors.append(f"{rel}: no English source at {source.relative_to(DOCS_DIR)}")
            continue

        meta, body = split_front_matter(page.read_text(encoding="utf-8"))

        recorded = meta.get("source_sha")
        if not isinstance(recorded, str):
            errors.append(f"{rel}: missing 'source_sha' front matter")
        elif recorded != sha256_of(source):
            errors.append(
                f"{rel}: STALE — English source changed since translation "
                f"(re-translate, then run --update-hashes {locale})"
            )

        if meta.get("translated") not in {"machine", "reviewed"}:
            errors.append(f"{rel}: 'translated' must be 'machine' or 'reviewed'")

        _, source_body = split_front_matter(source.read_text(encoding="utf-8"))
        errors.extend(f"{rel}: {problem}" for problem in compare(analyze(source_body), analyze(body)))

    return len(pages), errors


def update_hashes(locale: str) -> int:
    """Rewrite source_sha for every page in a locale. Returns pages updated."""
    updated = 0
    for page in translated_pages(locale):
        source = english_counterpart(page, locale)
        if not source.exists():
            continue
        text = page.read_text(encoding="utf-8")
        match = FRONT_MATTER_RE.match(text)
        if match is None:
            continue
        current = sha256_of(source)
        new_yaml = re.sub(
            r"^source_sha:.*$",
            f"source_sha: {current}",
            match.group("yaml"),
            count=1,
            flags=re.MULTILINE,
        )
        if new_yaml == match.group("yaml"):
            continue
        page.write_text(f"---\n{new_yaml}\n---\n{text[match.end():]}", encoding="utf-8")
        updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locales", nargs="*", default=None, help="locales to check (default: all)")
    parser.add_argument(
        "--update-hashes",
        metavar="LOCALE",
        help="re-record source_sha for a locale after re-checking its translations",
    )
    args = parser.parse_args()

    if args.update_hashes:
        count = update_hashes(args.update_hashes)
        print(f"Updated source_sha on {count} page(s) in '{args.update_hashes}'.")
        return 0

    locales = args.locales or LOCALES
    total_errors: list[str] = []

    for locale in locales:
        count, errors = validate_locale(locale)
        status = "OK" if not errors else f"{len(errors)} problem(s)"
        print(f"{locale}: {count} translated page(s) — {status}")
        total_errors.extend(errors)

    sys.stdout.flush()
    for error in total_errors:
        print(f"  ERROR {error}", file=sys.stderr)

    if total_errors:
        print(f"\n{len(total_errors)} translation problem(s) found.", file=sys.stderr)
        return 1

    print("All translations valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
