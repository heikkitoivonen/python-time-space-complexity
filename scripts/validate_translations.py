#!/usr/bin/env python3
"""Validate localized documentation against its English source.

Translations live in ``docs/<locale>/`` and mirror the English tree at
``docs/``. This script checks that each translated page:

* has an English counterpart,
* carries ``source_sha`` front matter matching that counterpart (staleness),
* preserves code blocks, table shape, heading structure, and link targets.

Repository-root documents (``README.md`` and friends) are translated in place
as ``<stem>.<tag>.md`` and get the same checks. They cannot carry YAML front
matter - GitHub would render it as a table - so their metadata lives in HTML
comments at the top of the file instead.

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
LOCALES = ["fi", "ja", "zh"]

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"

# Root-level docs are translated as ``<stem>.<tag>.md``. The tag is the full
# IETF language tag rather than the bare locale, because that is the
# convention GitHub readers expect. Locales with no root translations are
# simply absent.
ROOT_DOC_TAGS = {"zh": "zh-CN"}
ROOT_DOC_STEMS = ["README", "CONTRIBUTING", "TRANSLATING"]

FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
FRONT_MATTER_RE = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n", re.DOTALL)
ROOT_META_RE = re.compile(r"^<!--\s*(?P<key>source_sha|translated):\s*(?P<value>\S+)\s*-->$")
# Every root doc opens with a language switcher, which is the one line that is
# *meant* to differ between a source and its translation.
SWITCHER_RE = re.compile(r"^(\*\*English\*\*|\[English\])")
SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


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
                    problems.append(
                        f"code block {index + 1} was modified (code must stay verbatim)"
                    )

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

    problems.extend(compare_links(source.link_targets, target.link_targets))

    return problems


def compare_links(source: list[str], target: list[str]) -> list[str]:
    """Compare link targets, allowing same-document anchors to be translated."""
    problems: list[str] = []

    def split(targets: list[str]) -> tuple[set[str], int]:
        # Headings are translated, so their slugs change. Only the count of
        # same-document anchors has to line up, not the anchors themselves.
        anchors = [link for link in targets if link.startswith("#")]
        return {link for link in targets if not link.startswith("#")}, len(anchors)

    source_links, source_anchors = split(source)
    target_links, target_anchors = split(target)

    missing = sorted(source_links - target_links)
    added = sorted(target_links - source_links)
    if missing:
        problems.append(f"link targets missing from translation: {', '.join(missing)}")
    if added:
        problems.append(f"link targets not present in English: {', '.join(added)}")
    if source_anchors != target_anchors:
        problems.append(
            f"same-document anchor count differs: English has {source_anchors}, "
            f"translation has {target_anchors}"
        )

    return problems


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_problem(
    recorded: object, source: Path, locale: str, source_label: str = "English source"
) -> str | None:
    """Describe what is wrong with a recorded source_sha, or None if it is fine.

    A brand-new translation has never had a hash recorded, so calling it stale
    and telling the translator to re-translate is both wrong and alarming.
    Anything that is not a SHA-256 -- absent, or the elided placeholder from
    the docs -- means "not recorded yet", which is a different instruction.
    """
    if not isinstance(recorded, str) or not SHA256_RE.match(recorded):
        return f"source_sha not recorded yet — run --update-hashes {locale}"
    if recorded != sha256_of(source):
        return (
            f"STALE — {source_label} changed since translation "
            f"(re-translate, then run --update-hashes {locale})"
        )
    return None


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

        problem = hash_problem(meta.get("source_sha"), source, locale)
        if problem:
            errors.append(f"{rel}: {problem}")

        if meta.get("translated") not in {"machine", "reviewed"}:
            errors.append(f"{rel}: 'translated' must be 'machine' or 'reviewed'")

        _, source_body = split_front_matter(source.read_text(encoding="utf-8"))
        errors.extend(
            f"{rel}: {problem}" for problem in compare(analyze(source_body), analyze(body))
        )

    return len(pages), errors


def split_root_meta(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata, body) for a root doc, whose metadata is HTML comments."""
    meta: dict[str, str] = {}
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        match = ROOT_META_RE.match(lines[index])
        if match is None:
            break
        meta[match.group("key")] = match.group("value")
        index += 1
    return meta, "\n".join(lines[index:]).lstrip("\n")


def strip_switcher(body: str) -> str:
    """Drop the leading language-switcher line, which differs by design."""
    lines = body.split("\n")
    if lines and SWITCHER_RE.match(lines[0]):
        lines = lines[1:]
    return "\n".join(lines).lstrip("\n")


def root_doc_pairs(locale: str) -> list[tuple[Path, Path]]:
    """Return (translation, English source) for every root doc in a locale."""
    tag = ROOT_DOC_TAGS.get(locale)
    if tag is None:
        return []
    pairs = []
    for stem in ROOT_DOC_STEMS:
        translated = ROOT_DIR / f"{stem}.{tag}.md"
        if translated.exists():
            pairs.append((translated, ROOT_DIR / f"{stem}.md"))
    return pairs


def validate_root_docs(locale: str) -> tuple[int, list[str]]:
    """Validate one locale's root docs. Returns (doc count, error messages)."""
    errors: list[str] = []
    pairs = root_doc_pairs(locale)

    for translated, source in pairs:
        name = translated.name

        if not source.exists():
            errors.append(f"{name}: no English source at {source.name}")
            continue

        meta, body = split_root_meta(translated.read_text(encoding="utf-8"))

        problem = hash_problem(meta.get("source_sha"), source, locale, source.name)
        if problem:
            errors.append(f"{name}: {problem}")

        if meta.get("translated") not in {"machine", "reviewed"}:
            errors.append(f"{name}: 'translated' must be 'machine' or 'reviewed'")

        source_body = strip_switcher(source.read_text(encoding="utf-8"))
        problems = compare(analyze(source_body), analyze(strip_switcher(body)))
        errors.extend(f"{name}: {problem}" for problem in problems)

    return len(pairs), errors


def stamp_front_matter(yaml_text: str, current: str) -> str:
    """Set source_sha in a front-matter block, adding the key if it is absent.

    A new translation has no hash to replace, so substitution alone would
    silently do nothing and leave the translator following an instruction that
    never takes effect.
    """
    stamped, replaced = re.subn(
        r"^source_sha:.*$",
        f"source_sha: {current}",
        yaml_text,
        count=1,
        flags=re.MULTILINE,
    )
    if replaced:
        return stamped
    return f"source_sha: {current}\n{yaml_text}" if yaml_text else f"source_sha: {current}"


def update_hashes(locale: str) -> int:
    """Rewrite source_sha for every page in a locale. Returns pages updated."""
    updated = 0
    for page in translated_pages(locale):
        source = english_counterpart(page, locale)
        if not source.exists():
            continue
        text = page.read_text(encoding="utf-8")
        current = sha256_of(source)

        match = FRONT_MATTER_RE.match(text)
        if match is None:
            # A new translation may have no front matter at all. Give it one,
            # so recording the hash is a single command either way.
            page.write_text(
                f"---\nsource_sha: {current}\ntranslated: machine\n---\n\n{text.lstrip()}",
                encoding="utf-8",
            )
            updated += 1
            continue

        new_yaml = stamp_front_matter(match.group("yaml"), current)
        if new_yaml == match.group("yaml"):
            continue
        page.write_text(f"---\n{new_yaml}\n---\n{text[match.end() :]}", encoding="utf-8")
        updated += 1

    for translated, source in root_doc_pairs(locale):
        if not source.exists():
            continue
        text = translated.read_text(encoding="utf-8")
        meta, body = split_root_meta(text)
        current = sha256_of(source)
        if meta.get("source_sha") == current:
            continue
        meta["source_sha"] = current
        meta.setdefault("translated", "machine")
        header = "".join(f"<!-- {key}: {value} -->\n" for key, value in meta.items())
        translated.write_text(f"{header}\n{body}", encoding="utf-8")
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

        root_count, root_errors = validate_root_docs(locale)
        if root_count:
            status = "OK" if not root_errors else f"{len(root_errors)} problem(s)"
            print(f"{locale}: {root_count} translated root doc(s) — {status}")
            total_errors.extend(root_errors)

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
