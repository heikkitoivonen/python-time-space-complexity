"""Tests for the claim-free code block finder.

``scripts/find_claimless_code_blocks.py`` answers one question: does this
fenced block say anything about what the code costs? The interesting cases are
all near-misses that showed up while running it over ``docs/``, and each of
them is pinned here:

* ``O(min(len(a), len(b)))`` is a claim -- the pattern has to nest parentheses
* ``StringIO()`` and ``logger.info(x)`` are not claims, though both end in a
  letter followed by ``(``
* a claim in the prose on either side of a block still covers that block, but
  the page's H1 does not, because every page here is titled "... Complexity"
"""

from pathlib import Path

from scripts.find_claimless_code_blocks import (
    Block,
    collect,
    find_claims,
    iter_blocks,
    scan,
)


def write(tmp_path: Path, text: str, name: str = "page.md") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestFindClaims:
    """Tests for find_claims."""

    def test_plain_big_o(self) -> None:
        assert find_claims("x = 1  # O(1)") == ["O(1)"]

    def test_nested_parentheses(self) -> None:
        assert find_claims("# O(min(len(a), len(b)))") == ["O(min(len(a), len(b)))"]

    def test_theta_and_omega(self) -> None:
        assert find_claims("Θ(n) and Ω(log n)") == ["Θ(n)", "Ω(log n)"]

    def test_call_ending_in_o_is_not_a_claim(self) -> None:
        assert find_claims("buf = StringIO()") == []
        assert find_claims("logger.info('hi')") == []
        assert find_claims("pos = fileinput.lineno()") == []

    def test_empty_parentheses_are_not_a_claim(self) -> None:
        assert find_claims("value = O()") == []

    def test_prose_words(self) -> None:
        assert find_claims("much faster than a list") == ["faster"]
        assert find_claims("amortised over n appends") == ["amortised"]

    def test_word_inside_an_identifier_counts(self) -> None:
        # `expensive_key` makes the same point as the word in a comment does.
        assert find_claims("sorted(items, key=expensive_key)") == ["expensive"]

    def test_word_inside_a_longer_word_does_not(self) -> None:
        assert find_claims("a costume shop") == []
        assert find_claims("collinear points") == []

    def test_duplicates_are_collapsed(self) -> None:
        assert find_claims("O(n) then O(n) again") == ["O(n)"]

    def test_no_claim(self) -> None:
        assert find_claims("d = {'a': 1}\nprint(d)") == []

    def test_big_o_only_ignores_prose(self) -> None:
        assert find_claims("much faster", big_o_only=True) == []
        assert find_claims("# O(1) and faster", big_o_only=True) == ["O(1)"]


class TestIterBlocks:
    """Tests for the Markdown fence parser."""

    def test_finds_block_and_records_language(self, tmp_path: Path) -> None:
        path = write(tmp_path, "# Title\n\n```python\nx = 1\n```\n")
        (block,) = iter_blocks(path)
        assert block.language == "python"
        assert block.lines == ["x = 1"]
        assert (block.start_line, block.end_line) == (3, 5)

    def test_block_without_info_string(self, tmp_path: Path) -> None:
        path = write(tmp_path, "```\nplain text\n```\n")
        (block,) = iter_blocks(path)
        assert block.language == ""

    def test_tildes_and_backticks_do_not_close_each_other(self, tmp_path: Path) -> None:
        path = write(tmp_path, "~~~python\n```\nstill inside\n~~~\n")
        (block,) = iter_blocks(path)
        assert block.lines == ["```", "still inside"]

    def test_longer_fence_is_not_closed_by_a_shorter_one(self, tmp_path: Path) -> None:
        path = write(tmp_path, "````\n```\ninner\n```\n````\n")
        (block,) = iter_blocks(path)
        assert block.lines == ["```", "inner", "```"]

    def test_indented_fence_inside_an_admonition(self, tmp_path: Path) -> None:
        path = write(tmp_path, '!!! note "Heads up"\n\n    ```python\n    x = 1\n    ```\n')
        (block,) = iter_blocks(path)
        assert block.lines == ["    x = 1"]

    def test_unterminated_fence_still_yields_a_block(self, tmp_path: Path) -> None:
        path = write(tmp_path, "```python\nx = 1\n")
        (block,) = iter_blocks(path)
        assert block.lines == ["x = 1"]

    def test_inline_code_is_not_a_fence(self, tmp_path: Path) -> None:
        assert iter_blocks(write(tmp_path, "See ```x``` for details.\n")) == []

    def test_heading_trail(self, tmp_path: Path) -> None:
        path = write(tmp_path, "# Page\n\n## Section\n\n### Sub\n\n```python\nx = 1\n```\n")
        (block,) = iter_blocks(path)
        assert block.heading_path == "Page > Section > Sub"

    def test_sibling_heading_pops_the_trail(self, tmp_path: Path) -> None:
        text = "# Page\n\n## First\n\n### Deep\n\n## Second\n\n```python\nx = 1\n```\n"
        (block,) = iter_blocks(write(tmp_path, text))
        assert block.heading_path == "Page > Second"


class TestContext:
    """Tests for the prose and headings that can cover a block."""

    def test_lead_in_prose_covers_the_block(self, tmp_path: Path) -> None:
        path = write(tmp_path, "## Section\n\nAppend is O(1) amortised.\n\n```python\nx = 1\n```\n")
        (block,) = iter_blocks(path)
        assert block.claims() == []
        assert block.context_claims() == ["O(1)", "amortised"]

    def test_trailing_prose_covers_the_block(self, tmp_path: Path) -> None:
        path = write(tmp_path, "## Section\n\n```python\nx = 1\n```\n\nThis means O(1) growth.\n")
        (block,) = iter_blocks(path)
        assert block.context_claims() == ["O(1)"]

    def test_subheading_covers_the_block(self, tmp_path: Path) -> None:
        path = write(
            tmp_path, "# Page\n\n## Base Exceptions - Time: O(1)\n\n```python\nx = 1\n```\n"
        )
        (block,) = iter_blocks(path)
        assert block.context_claims() == ["O(1)"]

    def test_h1_does_not_cover_the_block(self, tmp_path: Path) -> None:
        # Every page on this site is titled "... Complexity"; counting the H1
        # would mark the whole site covered.
        path = write(tmp_path, "# Sorted Complexity\n\n## Use Cases\n\n```python\nx = 1\n```\n")
        (block,) = iter_blocks(path)
        assert block.context_claims() == []

    def test_prose_from_another_section_does_not_carry_over(self, tmp_path: Path) -> None:
        text = "## First\n\nThis is O(1).\n\n## Second\n\n```python\nx = 1\n```\n"
        (block,) = iter_blocks(write(tmp_path, text))
        assert block.context_claims() == []

    def test_big_o_only_propagates_to_blocks(self, tmp_path: Path) -> None:
        path = write(tmp_path, "```python\n# much faster\nx = 1\n```\n")
        assert iter_blocks(path)[0].claims() == ["faster"]
        assert iter_blocks(path, big_o_only=True)[0].claims() == []


class TestCollect:
    """Tests for the file walk."""

    def test_skips_locale_directories(self, tmp_path: Path) -> None:
        write(tmp_path, "# en\n", "stdlib/heapq.md")
        write(tmp_path, "# fi\n", "fi/stdlib/heapq.md")
        assert collect(tmp_path, ("fi",)) == [tmp_path / "stdlib" / "heapq.md"]

    def test_includes_them_when_not_skipped(self, tmp_path: Path) -> None:
        write(tmp_path, "# en\n", "stdlib/heapq.md")
        write(tmp_path, "# fi\n", "fi/stdlib/heapq.md")
        assert len(collect(tmp_path, ())) == 2


class TestScan:
    """Tests for the reporting filters."""

    def _tree(self, tmp_path: Path) -> None:
        write(
            tmp_path,
            "# Page\n\n"
            "## Bare\n\n```python\nx = 1\n```\n\n"
            "## Annotated\n\n```python\ny = 2  # O(1)\n```\n\n"
            "## Covered by prose\n\nThis is O(n).\n\n```python\nz = 3\n```\n\n"
            "## Shell\n\n```bash\nls\n```\n",
            "page.md",
        )

    def test_reports_only_claim_free_blocks(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        total, hits = scan(tmp_path, (), None, 1, False, False, False)
        assert total == 4
        assert [block.heading_path.split(" > ")[-1] for block in hits] == [
            "Bare",
            "Covered by prose",
            "Shell",
        ]

    def test_uncovered_only_drops_blocks_the_section_explains(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        _, hits = scan(tmp_path, (), None, 1, False, True, False)
        assert "Covered by prose" not in [block.heading_path.split(" > ")[-1] for block in hits]

    def test_language_filter(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        _, hits = scan(tmp_path, (), {"bash"}, 1, False, False, False)
        assert [block.language for block in hits] == ["bash"]

    def test_min_lines_filter(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        total, _ = scan(tmp_path, (), None, 2, False, False, False)
        assert total == 0

    def test_invert_reports_the_blocks_that_do_claim(self, tmp_path: Path) -> None:
        self._tree(tmp_path)
        _, hits = scan(tmp_path, (), None, 1, True, False, False)
        assert [block.heading_path.split(" > ")[-1] for block in hits] == ["Annotated"]


class TestBlock:
    """Tests for the Block helpers."""

    def test_body_and_line_count(self) -> None:
        block = Block(Path("page.md"), 1, 4, "python", "Page", ["a = 1", "b = 2"])
        assert block.body == "a = 1\nb = 2"
        assert block.line_count == 2
