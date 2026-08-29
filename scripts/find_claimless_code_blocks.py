#!/usr/bin/env python3
"""Find fenced code blocks that make no performance claim.

This site documents time and space complexity, so a code block usually earns
its place by showing what an operation costs: a Big-O annotation, or a comment
comparing two approaches. A block with no such claim is not automatically
wrong - some show pure syntax or a data structure - but it is worth a look:
it should either gain a complexity note or go away.

Usage:
    uv run python scripts/find_claimless_code_blocks.py
    uv run python scripts/find_claimless_code_blocks.py --show-block --limit 20
    uv run python scripts/find_claimless_code_blocks.py --format json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Locale subdirectories of docs/. Translations mirror the English tree, so
# scanning them just reports every finding a second time in another language.
DEFAULT_SKIP_DIRS = ("fi", "ja", "zh")


# A Big-O style annotation: O(1), O(n log n), O(len(s1) + len(s2)), Theta(n),
# Omega(n). One level of nested parentheses is allowed, because annotations
# here routinely wrap a call - O(min(len(a), len(b))). The letter must not be
# preceded by an identifier character, or `logger.info(...)` would read as a
# complexity claim. Only capitals count: little-o notation is unused in these
# docs, and matching it would hit every `foo(...)` that ends in "o".
def _nested(depth: int) -> str:
    """A parenthesised group that may nest `depth` levels deep."""
    inner = r"[^()\n]"
    for _ in range(depth):
        inner = rf"(?:[^()\n]|\({inner}*\))"
    return rf"\({inner}+\)"


COMPLEXITY_RE = re.compile(rf"(?<![A-Za-z0-9_])[OΘΩ]\s*{_nested(2)}")

# Words that assert something about speed, memory or cost. Matched
# case-insensitively on word boundaries against the block's text.
CLAIM_WORDS = (
    r"fast(?:er|est)?",
    r"slow(?:er|est|ly)?",
    r"quick(?:er|est|ly)?",
    r"speed(?:s|up|ups)?",
    r"efficien(?:t|tly|cy|cies)",
    r"inefficien(?:t|tly|cy|cies)",
    r"performan(?:ce|t)",
    r"perf",
    r"overhead",
    r"expensive",
    r"cheap(?:er|est)?",
    r"costl(?:y|ier)",
    r"cost(?:s|ing)?",
    r"complexit(?:y|ies)",
    r"amorti[sz]ed",
    r"constant[- ]time",
    r"linear(?:ly)?",
    r"quadratic",
    r"logarithmic",
    r"exponential",
    r"scal(?:e|es|ing|ability)",
    r"benchmark(?:s|ed|ing)?",
    r"throughput",
    r"laten(?:cy|cies)",
    r"memory[- ]usage",
    r"in[- ]place",
    r"copies|copy|copied",
    r"allocat(?:e|es|ed|ion|ions)",
    r"n\s*log\s*n",
    r"big[- ]o",
)
# Boundaries are letters and digits only, not \b: an identifier such as
# `expensive_function` or `slow_path` is a claim about cost just as much as the
# same word in prose, and \b would not match either side of the underscore.
CLAIM_WORDS_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:" + "|".join(CLAIM_WORDS) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

# ```lang / ~~~lang, possibly indented inside an admonition or list item.
FENCE_RE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")

HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*?)\s*#*\s*$")


def find_claims(text: str, big_o_only: bool = False) -> list[str]:
    """Return the distinct performance claims in a chunk of text, in order.

    With big_o_only, prose words such as "faster" do not count - only an
    explicit Big-O annotation does.
    """
    found: list[str] = []
    seen: set[str] = set()
    patterns = (COMPLEXITY_RE,) if big_o_only else (COMPLEXITY_RE, CLAIM_WORDS_RE)
    for pattern in patterns:
        for match in pattern.finditer(text):
            claim = " ".join(match.group(0).split())
            if claim.lower() not in seen:
                seen.add(claim.lower())
                found.append(claim)
    return found


@dataclass
class Block:
    """One fenced code block and what it does or does not claim."""

    path: Path
    start_line: int  # 1-based line of the opening fence
    end_line: int  # 1-based line of the closing fence (or EOF)
    language: str
    heading_path: str
    lines: list[str] = field(default_factory=list)
    # The heading trail plus the prose between the previous block/heading and
    # this fence. A claim there covers the block without repeating itself.
    context: str = ""
    # When set, only a Big-O annotation counts as a claim.
    big_o_only: bool = False

    @property
    def body(self) -> str:
        return "\n".join(self.lines)

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def claims(self) -> list[str]:
        """Return the distinct performance claims made inside the block."""
        return find_claims(self.body, self.big_o_only)

    def context_claims(self) -> list[str]:
        """Return the claims made by the block's heading trail and lead-in prose."""
        return find_claims(self.context, self.big_o_only)


def add_trailer(block: Block | None, trailer: list[str]) -> None:
    """Fold the prose that follows a block into that block's context."""
    if block is not None and trailer:
        block.context += "\n" + "\n".join(trailer)


def iter_blocks(path: Path, big_o_only: bool = False) -> list[Block]:
    """Extract every fenced code block from a Markdown file.

    Tracks the enclosing heading trail so a finding can be located in the
    rendered page, and honours the CommonMark rule that a fence closes only on
    a fence of the same character that is at least as long as the opener.
    """
    blocks: list[Block] = []
    headings: list[tuple[int, str]] = []
    lead_in: list[str] = []
    open_block: Block | None = None
    # The block just closed: the prose that follows it, up to the next heading
    # or fence, explains it as much as the prose before it did.
    last_closed: Block | None = None
    fence_char = ""
    fence_len = 0
    indent = ""

    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if open_block is not None:
            stripped = line.strip()
            if (
                stripped
                and set(stripped) == {fence_char}
                and len(stripped) >= fence_len
                and line.startswith(indent[: len(line) - len(line.lstrip())])
            ):
                open_block.end_line = number
                blocks.append(open_block)
                last_closed = open_block
                open_block = None
                lead_in = []
                continue
            open_block.lines.append(line)
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            fence = fence_match.group("fence")
            info = fence_match.group("info").strip()
            # An info string may not contain a backtick when the fence is
            # backticks; that form is inline code, not a fence.
            if fence[0] == "`" and "`" in info:
                continue
            add_trailer(last_closed, lead_in)
            last_closed = None
            fence_char = fence[0]
            fence_len = len(fence)
            indent = fence_match.group("indent")
            language = info.split()[0].lstrip("{.").rstrip("}") if info else ""
            heading_path = " > ".join(title for _, title in headings)
            # The H1 is the page title, and every page here is titled
            # "... Complexity", so counting it as context would mark the whole
            # site covered. Sections below it are the real signal.
            subheadings = [title for level, title in headings if level > 1]
            open_block = Block(
                path=path,
                start_line=number,
                end_line=number,
                language=language,
                heading_path=heading_path,
                context="\n".join([*subheadings, *lead_in]),
                big_o_only=big_o_only,
            )
            lead_in = []
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group("hashes"))
            add_trailer(last_closed, lead_in)
            last_closed = None
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, heading_match.group("title")))
            lead_in = []
            continue

        lead_in.append(line)

    add_trailer(last_closed, lead_in)
    if open_block is not None:
        open_block.end_line = len(lines)
        blocks.append(open_block)
    return blocks


def collect(root: Path, skip_dirs: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in skip_dirs:
            continue
        paths.append(path)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find fenced code blocks that make no performance claim."
    )
    parser.add_argument("--root", default="docs", help="Directory to scan (default: docs).")
    parser.add_argument(
        "--include-translations",
        action="store_true",
        help=f"Also scan locale subdirectories ({', '.join(DEFAULT_SKIP_DIRS)}).",
    )
    parser.add_argument(
        "--language",
        action="append",
        default=None,
        help="Only report blocks with this info string; repeatable (e.g. --language python).",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=1,
        help="Ignore blocks shorter than this many lines (default: 1).",
    )
    parser.add_argument(
        "--show-block", action="store_true", help="Print the body of each reported block."
    )
    parser.add_argument("--limit", type=int, default=0, help="Report at most this many blocks.")
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format (default: text)."
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Report the blocks that DO make a claim instead.",
    )
    parser.add_argument(
        "--require-big-o",
        action="store_true",
        help="Count only an explicit Big-O annotation as a claim, not words like 'faster'.",
    )
    parser.add_argument(
        "--uncovered-only",
        action="store_true",
        help=(
            "Only report blocks whose heading trail and lead-in prose are also "
            "claim-free - the blocks nothing on the page justifies."
        ),
    )
    return parser


def scan(
    root: Path,
    skip_dirs: tuple[str, ...],
    languages: set[str] | None,
    min_lines: int,
    invert: bool,
    uncovered_only: bool,
    big_o_only: bool,
) -> tuple[int, list[Block]]:
    """Return (blocks considered, blocks to report)."""
    total = 0
    hits: list[Block] = []
    for path in collect(root, skip_dirs):
        for block in iter_blocks(path, big_o_only):
            if languages is not None and block.language.lower() not in languages:
                continue
            if block.line_count < min_lines:
                continue
            total += 1
            if bool(block.claims()) != invert:
                continue
            if uncovered_only and block.context_claims():
                continue
            hits.append(block)
    return total, hits


def report_json(
    root: Path, total: int, shown: list[Block], hits: list[Block], bodies: bool
) -> None:
    payload = {
        "root": str(root),
        "blocks_scanned": total,
        "blocks_reported": len(hits),
        "blocks": [
            {
                "file": str(block.path),
                "start_line": block.start_line,
                "end_line": block.end_line,
                "language": block.language,
                "heading": block.heading_path,
                "lines": block.line_count,
                "claims": block.claims(),
                "context_claims": block.context_claims(),
                "body": block.body if bodies else None,
            }
            for block in shown
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def report_text(total: int, shown: list[Block], hits: list[Block], bodies: bool) -> None:
    for block in shown:
        language = block.language or "(none)"
        location = f"{block.path}:{block.start_line}-{block.end_line}"
        context_claims = block.context_claims()
        covered = f"  <- section says {', '.join(context_claims[:3])}" if context_claims else ""
        print(f"{location}  [{language}]  {block.heading_path}{covered}")
        if bodies:
            for line in block.lines:
                print(f"    {line}")
            print()

    by_file: dict[Path, int] = {}
    for block in hits:
        by_file[block.path] = by_file.get(block.path, 0) + 1

    uncovered = sum(1 for block in hits if not block.context_claims())
    truncated = f" (showing {len(shown)})" if len(shown) != len(hits) else ""
    print()
    print(f"blocks scanned:  {total}")
    print(f"blocks reported: {len(hits)}{truncated}")
    print(f"  of those, {uncovered} sit in a section that makes no claim either")
    print(f"files affected:  {len(by_file)}")
    if by_file:
        print("\nworst files:")
        for path, count in sorted(by_file.items(), key=lambda item: (-item[1], str(item[0])))[:15]:
            print(f"  {count:4d}  {path}")


def main() -> int:
    args = build_parser().parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    skip_dirs = () if args.include_translations else DEFAULT_SKIP_DIRS
    languages = {lang.lower() for lang in args.language} if args.language else None

    total, hits = scan(
        root,
        skip_dirs,
        languages,
        args.min_lines,
        args.invert,
        args.uncovered_only,
        args.require_big_o,
    )
    shown = hits[: args.limit] if args.limit else hits

    if args.format == "json":
        report_json(root, total, shown, hits, args.show_block)
    else:
        report_text(total, shown, hits, args.show_block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
