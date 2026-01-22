"""Unit tests for difflib module operations documented in docs/stdlib/difflib.md."""

from difflib import (
    Differ,
    HtmlDiff,
    SequenceMatcher,
    context_diff,
    get_close_matches,
    ndiff,
    unified_diff,
)


class TestSequenceMatcher:
    """Test SequenceMatcher operations."""

    def test_init(self) -> None:
        """SequenceMatcher can be initialized with two sequences."""
        matcher = SequenceMatcher(None, "abc", "abd")
        # Verify it works by checking ratio
        assert matcher.ratio() > 0

    def test_find_longest_match(self) -> None:
        """find_longest_match returns the longest matching block."""
        matcher = SequenceMatcher(None, "abcd", "abcd efgh")
        match = matcher.find_longest_match(0, 4, 0, 9)
        assert match.size == 4
        assert match.a == 0  # Match starts at index 0 in first sequence

    def test_find_longest_match_no_match(self) -> None:
        """find_longest_match returns size 0 when no match."""
        matcher = SequenceMatcher(None, "abc", "xyz")
        match = matcher.find_longest_match(0, 3, 0, 3)
        assert match.size == 0

    def test_get_matching_blocks(self) -> None:
        """get_matching_blocks returns all matching blocks."""
        matcher = SequenceMatcher(None, "abxcd", "abcd")
        blocks = matcher.get_matching_blocks()
        # Last block is always (len(a), len(b), 0)
        assert blocks[-1].size == 0
        # Should find "ab" and "cd" matches
        assert len(blocks) >= 2

    def test_get_opcodes(self) -> None:
        """get_opcodes returns edit operations."""
        matcher = SequenceMatcher(None, "abc", "abd")
        opcodes = matcher.get_opcodes()
        # Should have equal and replace operations
        ops = [op[0] for op in opcodes]
        assert "equal" in ops
        assert "replace" in ops

    def test_ratio(self) -> None:
        """ratio returns similarity between 0 and 1."""
        matcher = SequenceMatcher(None, "abcd", "abcd")
        assert matcher.ratio() == 1.0

        matcher = SequenceMatcher(None, "abcd", "efgh")
        assert matcher.ratio() == 0.0

        matcher = SequenceMatcher(None, "abcd", "abef")
        ratio = matcher.ratio()
        assert 0 < ratio < 1

    def test_quick_ratio(self) -> None:
        """quick_ratio returns upper bound on ratio."""
        matcher = SequenceMatcher(None, "abcd", "abef")
        assert matcher.quick_ratio() >= matcher.ratio()

    def test_real_quick_ratio(self) -> None:
        """real_quick_ratio returns upper bound on ratio."""
        matcher = SequenceMatcher(None, "abcd", "abef")
        assert matcher.real_quick_ratio() >= matcher.ratio()

    def test_with_junk_filter(self) -> None:
        """SequenceMatcher can filter junk elements."""
        # Without junk filter
        matcher1 = SequenceMatcher(None, "a b c", "abc")
        # With space as junk
        matcher2 = SequenceMatcher(lambda x: x == " ", "a b c", "abc")
        # Filtering junk should increase similarity
        assert matcher2.ratio() >= matcher1.ratio()


class TestDiffFunctions:
    """Test diff generation functions."""

    def test_unified_diff(self) -> None:
        """unified_diff generates unified format diff."""
        a = ["line1\n", "line2\n", "line3\n"]
        b = ["line1\n", "modified\n", "line3\n"]
        diff = list(unified_diff(a, b, fromfile="a", tofile="b"))
        # Should contain header and changes
        assert any("---" in line for line in diff)
        assert any("+++" in line for line in diff)
        assert any("-line2" in line for line in diff)
        assert any("+modified" in line for line in diff)

    def test_context_diff(self) -> None:
        """context_diff generates context format diff."""
        a = ["line1\n", "line2\n", "line3\n"]
        b = ["line1\n", "modified\n", "line3\n"]
        diff = list(context_diff(a, b, fromfile="a", tofile="b"))
        # Should contain context diff markers
        assert any("***" in line for line in diff)

    def test_ndiff(self) -> None:
        """ndiff generates detailed line diff."""
        a = ["line1\n", "line2\n"]
        b = ["line1\n", "line3\n"]
        diff = list(ndiff(a, b))
        # Should have markers for changes
        assert any(line.startswith("- ") for line in diff)
        assert any(line.startswith("+ ") for line in diff)

    def test_unified_diff_no_changes(self) -> None:
        """unified_diff returns empty for identical inputs."""
        a = ["line1\n", "line2\n"]
        diff = list(unified_diff(a, a))
        assert len(diff) == 0


class TestGetCloseMatches:
    """Test get_close_matches function."""

    def test_finds_exact_match(self) -> None:
        """get_close_matches finds exact matches."""
        matches = get_close_matches("apple", ["apple", "banana", "cherry"])
        assert "apple" in matches

    def test_finds_similar_matches(self) -> None:
        """get_close_matches finds similar strings."""
        matches = get_close_matches("appel", ["apple", "banana", "cherry"])
        assert "apple" in matches

    def test_respects_n_parameter(self) -> None:
        """get_close_matches respects n parameter."""
        words = ["apple", "apply", "application", "banana"]
        matches = get_close_matches("appl", words, n=2)
        assert len(matches) <= 2

    def test_respects_cutoff(self) -> None:
        """get_close_matches respects cutoff parameter."""
        # High cutoff should return fewer matches
        matches_high = get_close_matches("app", ["apple", "xyz"], cutoff=0.9)
        matches_low = get_close_matches("app", ["apple", "xyz"], cutoff=0.1)
        assert len(matches_high) <= len(matches_low)

    def test_returns_empty_for_no_matches(self) -> None:
        """get_close_matches returns empty list when no matches."""
        matches = get_close_matches("xyz", ["apple", "banana"], cutoff=0.9)
        assert matches == []


class TestDiffer:
    """Test Differ class."""

    def test_compare(self) -> None:
        """Differ.compare generates line-by-line diff."""
        d = Differ()
        result = list(d.compare(["one\n", "two\n"], ["one\n", "three\n"]))
        # Should have unchanged, removed, and added lines
        assert any(line.startswith("  ") for line in result)
        assert any(line.startswith("- ") for line in result)
        assert any(line.startswith("+ ") for line in result)


class TestHtmlDiff:
    """Test HtmlDiff class."""

    def test_make_file(self) -> None:
        """HtmlDiff.make_file generates HTML document."""
        h = HtmlDiff()
        a = ["line1\n", "line2\n"]
        b = ["line1\n", "modified\n"]
        html = h.make_file(a, b)
        assert "<html>" in html.lower() or "<!doctype" in html.lower()
        assert "</html>" in html.lower()

    def test_make_table(self) -> None:
        """HtmlDiff.make_table generates HTML table."""
        h = HtmlDiff()
        a = ["line1\n", "line2\n"]
        b = ["line1\n", "modified\n"]
        table = h.make_table(a, b)
        assert "<table" in table.lower()
