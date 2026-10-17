"""Tests that every English page ends with its closing sections, in one order.

A page opens with its one `#` title. Any `##` sections may follow, and the
closing sections, where a page has them, come last and in this order:

1. Best Practices - `## Best Practices` or `## Performance Best Practices`
2. `## Version Notes`
3. Related - any `## Related ...` heading, such as Related Functions, Related
   Modules or Related Types, or `## See Also`; a page may have more than one
4. `## Further Reading`

Once a closing section appears, every later `##` section is a closing section
in a slot no earlier than the one before it. Headings inside fenced code blocks
are not headings.

Not settled here: translations. Their headings are translated, so they cannot
be matched by name; `scripts/validate_translations.py` holds their heading
levels to the English ones, which does not catch two swapped sections of the
same shape.
"""

from __future__ import annotations

import pathlib
import re

from scripts.validate_translations import FENCE_RE, LOCALES

DOCS = pathlib.Path(__file__).parent.parent / "docs"
SLOTS = ("Best Practices", "Version Notes", "Related", "Further Reading")


def _slot(heading: str) -> int | None:
    if heading in ("Best Practices", "Performance Best Practices"):
        return 0
    if heading == "Version Notes":
        return 1
    if heading.startswith("Related ") or heading == "See Also":
        return 2
    if heading == "Further Reading":
        return 3
    return None


def headings(text: str) -> list[tuple[int, str]]:
    """Every `#` and `##` heading outside fenced code, as (level, text)."""
    found: list[tuple[int, str]] = []
    fence: str | None = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if fence is not None:
            if (
                match is not None
                and match.group("fence")[0] == fence[0]
                and len(match.group("fence")) >= len(fence)
                and not match.group("info").strip()
            ):
                fence = None
            continue
        if match is not None:
            fence = match.group("fence")
            continue
        heading = re.match(r"^(#{1,2}) (.+?)\s*$", line)
        if heading is not None:
            found.append((len(heading.group(1)), heading.group(2)))
    return found


def problems(text: str) -> list[str]:
    """What is out of place on one page; empty when the order holds."""
    found = headings(text)
    titles = [heading for level, heading in found if level == 1]
    if len(titles) != 1 or found[0][0] != 1:
        return [f"expected one # title before any ## section, found {titles}"]

    issues: list[str] = []
    last: int | None = None
    for heading in [heading for level, heading in found if level == 2]:
        slot = _slot(heading)
        if last is None:
            last = slot
        elif slot is None:
            issues.append(f"'{heading}' follows the closing section {SLOTS[last]}")
        elif slot < last or (slot == last and slot != 2):
            issues.append(f"'{heading}' follows {SLOTS[last]}")
        else:
            last = slot
    return issues


def english_pages() -> list[pathlib.Path]:
    return sorted(
        page
        for page in DOCS.rglob("*.md")
        if page.relative_to(DOCS).parts[0] not in {*LOCALES, "overrides"}
    )


def test_every_english_page_keeps_its_closing_sections_in_order() -> None:
    failures = [
        f"{page.relative_to(DOCS)}: {issue}"
        for page in english_pages()
        for issue in problems(page.read_text(encoding="utf-8"))
    ]

    assert not failures, "\n".join(failures)


def test_the_pages_use_every_slot() -> None:
    used = {
        _slot(heading)
        for page in english_pages()
        for level, heading in headings(page.read_text(encoding="utf-8"))
        if level == 2
    }

    assert used >= {0, 1, 2, 3}


class TestTheCheckItself:
    """Synthetic pages, so each rule is seen to reject what it should."""

    def test_the_full_order_passes(self) -> None:
        page = (
            "# X Complexity\n\n## Complexity Reference\n\n## Common Patterns\n\n"
            "## Performance Best Practices\n\n## Version Notes\n\n"
            "## Related Modules\n\n## Related Types\n\n## Further Reading\n"
        )

        assert problems(page) == []

    def test_missing_closing_sections_pass(self) -> None:
        assert problems("# X\n\n## Usage\n\n## Version Notes\n\n## Further Reading\n") == []

    def test_a_page_with_no_sections_passes(self) -> None:
        assert problems("# X\n\nText.\n") == []

    def test_swapped_closing_sections_fail(self) -> None:
        page = "# X\n\n## Best Practices\n\n## Related Functions\n\n## Version Notes\n"

        assert problems(page) == ["'Version Notes' follows Related"]

    def test_a_body_section_after_a_closing_one_fails(self) -> None:
        page = "# X\n\n## Version Notes\n\n## Limitations\n\n## Related Modules\n"

        assert problems(page) == ["'Limitations' follows the closing section Version Notes"]

    def test_a_repeated_closing_slot_fails(self) -> None:
        page = "# X\n\n## Best Practices\n\n## Performance Best Practices\n"

        assert problems(page) == ["'Performance Best Practices' follows Best Practices"]

    def test_a_heading_inside_a_code_block_is_ignored(self) -> None:
        page = "# X\n\n## Version Notes\n\n```python\n## Limitations\n```\n\n## See Also\n"

        assert problems(page) == []

    def test_a_shorter_fence_does_not_close_a_longer_one(self) -> None:
        page = "# X\n\n## Version Notes\n\n````md\n```\n## Limitations\n````\n\n## See Also\n"

        assert problems(page) == []

    def test_a_section_before_the_title_fails(self) -> None:
        assert problems("## Usage\n\n# X\n") != []
