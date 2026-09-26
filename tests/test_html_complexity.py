"""Tests for docs/stdlib/html.md.

The page prices `escape()` and `unescape()` as linear in the string, and
`HTMLParser` as a push parser that holds only the text it has not parsed yet
and the last start tag, calls one handler per construct, and keeps nothing
else it has handed over.
Growth is settled by timing three sizes a decade apart; what the parser holds
and which handlers it calls are settled by observation, which needs no
tolerance; the one version boundary is settled by timing on each side of it.

Measurement scope:

* `escape()` and `unescape()` are timed on 10,000, 100,000 and 1,000,000
  characters of text: for `escape()` two of every ten characters need
  replacing, for `unescape()` every ten characters hold one `&amp;`; each
  10x step costs between 4x and 30x, which excludes both a constant and a
  quadratic (100x). `escape()` output is asserted to be six characters per
  quote and at most six times the input. `unescape()` of a string with no `&`
  returns the same object, which is the page's "returned untouched"; one with
  a reference returns a new string.
* `HTMLParser()` holds nothing: `rawdata` is empty after construction, after
  `reset()`, and after `close()`. `feed()` of a whole document is timed at
  300, 3,000 and 30,000 repetitions of a paragraph with an attribute, a
  character reference and a comment: each 10x step costs between 4x and 30x.
  Single `feed()` calls on 2,000 and 20,000 repetitions of `<`, `&`, `&#1`,
  `</`, `<!`, `<?`, `<!--`, `<![CDATA[`, `<!DOCTYPE `, `<a ` and ` x="`, with
  `convert_charrefs` both ways, cost between 3x and 11x per 10x on 3.10.21,
  3.13.14 and 3.14.7 when probed; the test keeps `<`, `&#1` and `<!--`, both
  ways, and asserts under 30x, which excludes a quadratic.
* The held tail is observed through `rawdata`, the parser's unparsed buffer:
  after a 30,000-paragraph document cut inside a tag, it holds that tag and
  nothing before it; a tag cut in two is parsed when the next chunk completes
  it; text ending in a cut-off reference is held until `close()` parses it.
* Chunked feeding of one open construct: an attribute value fed ten
  characters per call, 20,000 against 200,000 characters. Releases from
  3.10.21, 3.11.16, 3.12.14, 3.13.15 and 3.14.7 wait for the held text to
  double before rescanning: 10x costs under 30x (about 10x measured). Earlier
  releases rescan on every call: 10x costs over 40x (about 90x measured on
  3.10.20, 3.12.13, 3.13.14 and 3.14.6). Which side a release is on was read
  from the `_parse_threshold` field in each release's Lib/html/parser.py.
* Handler calls are recorded by a subclass: one start tag per tag, text with
  references arriving unsplit with `convert_charrefs=True` and split at each reference
  with it false, attribute values converted either way, script content
  arriving as one text run with its `<` intact and its references left as
  text under both settings, `title` content keeping its
  `<` while references are still recognised, `<br/>` reaching
  `handle_starttag()` then `handle_endtag()` through the default
  `handle_startendtag()`, and a declaration, processing instruction, comment
  and CDATA section each reaching its own handler. The base class handlers
  are asserted to return `None` and record nothing.
* `getpos()` is asserted to report the line and offset of the tag being
  handled, and `get_starttag_text()` to be `None` before any tag and after a
  feed that ends in a cut-off start tag, the exact source text after one, and the same object
  on each call.
* The `html.entities` tables are asserted to be dicts, `html5` to hold names
  with and without `;`, some mapping to two characters, and to contain every
  HTML 4 name; `codepoint2name` is asserted to invert `name2codepoint`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That handler costs add to the parser's is a definitional scoping of the
  bounds, not a measurement.
* That the entity tables are built once at import follows from
  Lib/html/entities.py being module-level literals; lookups in them are
  ordinary dict lookups.
* `unescape()` on decimal references with thousands of digits: `int()`
  conversion applies, and past `sys.get_int_max_str_digits()` it raises
  `ValueError`. Only references of ordinary length are measured.
* Chunked feeding is measured for one open attribute value in ten-character
  chunks. Other open constructs, other chunk sizes, and documents in which
  progress alternates with a long open tail are not varied.
* `HTMLParser.handle_data()` receiving one run of text in several calls
  across `feed()` boundaries is documented behaviour; only the
  single-`feed()` case is asserted.

Coverage: the page-scoped audit reports no missing names. The regex objects
at module level of html.parser (`charref`, `entityref`, `tagfind_tolerant`
and the rest) and the methods `goahead`, `parse_*`, `check_for_whole_start_tag`,
`set_cdata_mode`, `clear_cdata_mode` and `updatepos` are parser internals
absent from the official documentation, and are not priced.
"""

from __future__ import annotations

import html
import html.entities
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "html.md"
EXPECTED_BLOCKS = 10

# The first release in each minor line whose feed() waits for held text to
# double before rescanning it.
_BATCHED_FEED_FROM = {(3, 10): 21, (3, 11): 16, (3, 12): 14, (3, 13): 15, (3, 14): 7}
BATCHED_FEED = sys.version_info.micro >= _BATCHED_FEED_FROM.get(sys.version_info[:2], 0)


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def decade_ratios(make: Callable[[int], Callable[[], Any]], sizes: tuple[int, ...]) -> list[float]:
    """Cost ratio between consecutive sizes."""
    durations = [best_ns(make(size)) for size in sizes]
    return [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]


class Recorder(HTMLParser):
    """Records every handler call as a tuple."""

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.events: list[tuple[Any, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.append(("start", tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        self.events.append(("end", tag))

    def handle_data(self, data: str) -> None:
        self.events.append(("data", data))

    def handle_entityref(self, name: str) -> None:
        self.events.append(("entity", name))

    def handle_charref(self, name: str) -> None:
        self.events.append(("char", name))

    def handle_comment(self, data: str) -> None:
        self.events.append(("comment", data))

    def handle_decl(self, decl: str) -> None:
        self.events.append(("decl", decl))

    def handle_pi(self, data: str) -> None:
        self.events.append(("pi", data))

    def unknown_decl(self, data: str) -> None:
        self.events.append(("unknown", data))


def parse(document: str, **options: Any) -> list[tuple[Any, ...]]:
    parser = Recorder(**options)
    parser.feed(document)
    parser.close()
    return parser.events


class TestEscapeIsLinear:
    """`escape(s, quote=True)` | O(n) | O(n); output at most six times the input."""

    def test_the_default_escapes_both_quotes(self) -> None:
        assert html.escape('<a href="x">it\'s & more</a>') == (
            "&lt;a href=&quot;x&quot;&gt;it&#x27;s &amp; more&lt;/a&gt;"
        )

    def test_quote_false_leaves_quotes_alone(self) -> None:
        assert html.escape("\"'<", quote=False) == "\"'&lt;"

    def test_output_is_at_most_six_times_the_input(self) -> None:
        for character in "&<>\"'":
            escaped = html.escape(character * 1_000)
            assert len(escaped) <= 6_000

        assert len(html.escape('"' * 1_000)) == 6_000

    @pytest.mark.timing
    def test_cost_grows_linearly(self) -> None:
        def make(size: int) -> Callable[[], Any]:
            text = ("abcdefgh<&" * (size // 10))[:size]
            return lambda: html.escape(text)

        ratios = decade_ratios(make, (10_000, 100_000, 1_000_000))

        assert all(4 < ratio < 30 for ratio in ratios), f"10x the text cost {ratios}"


class TestUnescapeIsLinear:
    """`unescape(s)` | O(n) | O(n); a string with no `&` is returned as is."""

    def test_html5_rules(self) -> None:
        assert html.unescape("&lt;p&gt; &amp &copy2024 &#169; &#x00A9; &#0;") == (
            "<p> & ©2024 © © �"
        )

    def test_a_string_without_a_reference_is_the_same_object(self) -> None:
        plain = "no references here" * 100

        assert html.unescape(plain) is plain

    def test_a_string_with_a_reference_is_a_new_one(self) -> None:
        text = "a &amp; b"

        assert html.unescape(text) is not text

    @pytest.mark.timing
    def test_cost_grows_linearly(self) -> None:
        def make(size: int) -> Callable[[], Any]:
            text = ("abc&amp;de" * (size // 10))[:size]
            return lambda: html.unescape(text)

        ratios = decade_ratios(make, (10_000, 100_000, 1_000_000))

        assert all(4 < ratio < 30 for ratio in ratios), f"10x the text cost {ratios}"


class TestTheParserHoldsOnlyTheOpenTail:
    """`HTMLParser()` | O(1); `feed(data)` | O(d + b); `close()` | O(b);
    `reset()` | O(1). `rawdata` is the parser's buffer of unparsed text."""

    PARAGRAPH = '<p class="c">Fish &amp; chips<!-- n --></p>\n'

    def test_a_new_parser_holds_nothing(self) -> None:
        assert HTMLParser().rawdata == ""

    def test_a_document_cut_inside_a_tag_leaves_only_that_tag(self) -> None:
        parser = HTMLParser()

        parser.feed(self.PARAGRAPH * 30_000 + '<a href="/x')

        assert parser.rawdata == '<a href="/x'

    def test_a_cut_off_tag_is_parsed_with_the_next_chunk(self) -> None:
        parser = Recorder()
        parser.feed("<p>one</p><a hr")

        assert parser.rawdata == "<a hr"

        parser.feed('ef="/x">two</a>')

        assert parser.rawdata == ""
        assert parser.events == [
            ("start", "p", []),
            ("data", "one"),
            ("end", "p"),
            ("start", "a", [("href", "/x")]),
            ("data", "two"),
            ("end", "a"),
        ]

    def test_close_parses_what_is_held(self) -> None:
        parser = Recorder()
        parser.feed("<p>one</p>two &am")

        assert parser.events == [("start", "p", []), ("data", "one"), ("end", "p")]
        assert parser.rawdata == "two &am"

        parser.close()

        assert parser.rawdata == ""
        assert parser.events[-1] == ("data", "two &am")

    def test_reset_discards_what_is_held(self) -> None:
        parser = Recorder()
        parser.feed("<p>text<a hr")

        parser.reset()
        parser.close()

        assert parser.rawdata == ""
        assert parser.events == [("start", "p", []), ("data", "text")]
        assert parser.getpos() == (1, 0)

    @pytest.mark.skipif(not BATCHED_FEED, reason="feed() parses on every call here")
    def test_handlers_can_wait_for_close(self) -> None:
        parser = Recorder()
        parser.feed('<a href="/x')
        parser.feed('">')

        assert parser.events == []

        parser.close()

        assert parser.events == [("start", "a", [("href", "/x")])]

    @pytest.mark.timing
    def test_a_whole_document_costs_linear_time(self) -> None:
        def make(repeats: int) -> Callable[[], Any]:
            document = self.PARAGRAPH * repeats

            def run() -> None:
                parser = HTMLParser()
                parser.feed(document)
                parser.close()

            return run

        ratios = decade_ratios(make, (300, 3_000, 30_000))

        assert all(4 < ratio < 30 for ratio in ratios), f"10x the document cost {ratios}"

    @pytest.mark.timing
    @pytest.mark.parametrize("convert", [True, False])
    @pytest.mark.parametrize("unit", ["<", "&#1", "<!--"])
    def test_one_feed_of_repeated_markup_is_linear(self, unit: str, convert: bool) -> None:
        def make(repeats: int) -> Callable[[], Any]:
            document = unit * repeats

            def run() -> None:
                parser = HTMLParser(convert_charrefs=convert)
                parser.feed(document)
                parser.close()

            return run

        ratios = decade_ratios(make, (2_000, 20_000))

        assert ratios[0] < 30, f"10x {unit!r} cost {ratios}"


class TestFeedingInChunks:
    """An attribute value left open across many ten-character `feed()` calls:
    O(n) in total from the releases in Version Notes, O(n²) before them."""

    @staticmethod
    def make(size: int) -> Callable[[], Any]:
        piece = "x" * 10

        def run() -> None:
            parser = HTMLParser()
            parser.feed('<a title="')
            for _ in range(size // 10):
                parser.feed(piece)
            parser.feed('">')
            parser.close()

        return run

    def test_the_tag_arrives_whole(self) -> None:
        parser = Recorder()
        parser.feed('<a title="')
        for _ in range(100):
            parser.feed("x" * 10)
        parser.feed('">')
        parser.close()

        assert parser.events == [("start", "a", [("title", "x" * 1_000)])]

    @pytest.mark.timing
    @pytest.mark.skipif(not BATCHED_FEED, reason="this release rescans on every call")
    def test_is_linear_where_feed_waits_for_the_buffer_to_double(self) -> None:
        durations = [best_ns(self.make(size), repeats=3) for size in (20_000, 200_000)]
        ratio = durations[1] / durations[0]

        assert ratio < 30, f"10x the open construct cost x{ratio:.1f}: {durations}"

    @pytest.mark.timing
    @pytest.mark.skipif(BATCHED_FEED, reason="this release waits for the buffer to double")
    def test_is_quadratic_where_feed_rescans_every_call(self) -> None:
        durations = [best_ns(self.make(size), repeats=3) for size in (20_000, 200_000)]
        ratio = durations[1] / durations[0]

        assert ratio > 40, f"10x the open construct cost x{ratio:.1f}: {durations}"


class TestHandlers:
    """One handler call per construct; the base class handlers do nothing."""

    def test_convert_charrefs_delivers_text_whole(self) -> None:
        assert parse("<p>Fish &amp; chips &#169;</p>") == [
            ("start", "p", []),
            ("data", "Fish & chips ©"),
            ("end", "p"),
        ]

    def test_without_it_text_splits_at_each_reference(self) -> None:
        assert parse("<p>Fish &amp; chips &#169;</p>", convert_charrefs=False) == [
            ("start", "p", []),
            ("data", "Fish "),
            ("entity", "amp"),
            ("data", " chips "),
            ("char", "169"),
            ("end", "p"),
        ]

    @pytest.mark.parametrize("convert", [True, False])
    def test_attribute_values_are_converted_either_way(self, convert: bool) -> None:
        events = parse('<A HREF="/p?a=1&amp;b=2">', convert_charrefs=convert)

        assert events == [("start", "a", [("href", "/p?a=1&b=2")])]

    def test_script_content_is_one_text_run(self) -> None:
        assert parse('<script>if (a<b) { x = "<b>"; }</script>') == [
            ("start", "script", []),
            ("data", 'if (a<b) { x = "<b>"; }'),
            ("end", "script"),
        ]
        assert "script" in HTMLParser.CDATA_CONTENT_ELEMENTS
        assert "style" in HTMLParser.CDATA_CONTENT_ELEMENTS

    @pytest.mark.parametrize("convert", [True, False])
    def test_script_references_stay_text_either_way(self, convert: bool) -> None:
        assert parse("<script>a &amp; b</script>", convert_charrefs=convert) == [
            ("start", "script", []),
            ("data", "a &amp; b"),
            ("end", "script"),
        ]

    def test_title_content_is_text_with_references_converted(self) -> None:
        assert parse("<title>a<b> &amp; c</title>") == [
            ("start", "title", []),
            ("data", "a<b> & c"),
            ("end", "title"),
        ]
        assert HTMLParser.RCDATA_CONTENT_ELEMENTS == ("textarea", "title")

    def test_title_content_recognises_only_references(self) -> None:
        assert parse("<title>a<b> &amp; c</title>", convert_charrefs=False) == [
            ("start", "title", []),
            ("data", "a<b> "),
            ("entity", "amp"),
            ("data", " c"),
            ("end", "title"),
        ]

    def test_startendtag_defaults_to_start_then_end(self) -> None:
        assert parse("<br/>") == [("start", "br", []), ("end", "br")]

    def test_each_construct_has_its_own_handler(self) -> None:
        document = '<!DOCTYPE html><?xml-stylesheet href="s"?><!-- c --><![CDATA[raw]]>'

        assert parse(document) == [
            ("decl", "DOCTYPE html"),
            ("pi", 'xml-stylesheet href="s"?'),
            ("comment", " c "),
            ("unknown", "CDATA[raw"),
        ]

    def test_the_base_handlers_do_nothing(self) -> None:
        parser = HTMLParser()

        assert parser.handle_starttag("a", []) is None
        assert parser.handle_endtag("a") is None
        assert parser.handle_startendtag("a", []) is None
        assert parser.handle_data("x") is None
        assert parser.handle_entityref("amp") is None
        assert parser.handle_charref("38") is None
        assert parser.handle_comment("x") is None
        assert parser.handle_decl("x") is None
        assert parser.handle_pi("x") is None
        assert parser.unknown_decl("x") is None
        assert parser.rawdata == ""


class TestPositions:
    """`getpos()` and `get_starttag_text()` | O(1): values the parser keeps."""

    def test_getpos_reports_the_construct_being_handled(self) -> None:
        positions: list[tuple[int, int]] = []

        class Positions(HTMLParser):
            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                positions.append(self.getpos())

        parser = Positions()
        parser.feed("<a>\n\n  <b>x</b><c>")
        parser.close()

        assert positions == [(1, 0), (3, 2), (3, 10)]

    def test_get_starttag_text_is_the_stored_source(self) -> None:
        parser = HTMLParser()

        assert parser.get_starttag_text() is None

        parser.feed('<IMG  SRC="a.png"/>text')

        first = parser.get_starttag_text()
        assert first == '<IMG  SRC="a.png"/>'
        assert parser.get_starttag_text() is first

    def test_a_cut_off_start_tag_can_reset_get_starttag_text(self) -> None:
        parser = HTMLParser()
        parser.feed("<a>")

        assert parser.get_starttag_text() == "<a>"

        parser.feed("<b")

        assert parser.get_starttag_text() is None


class TestEntityTables:
    """The `html.entities` tables are dicts, so lookups are O(1)."""

    def test_they_are_dicts(self) -> None:
        for table in (
            html.entities.html5,
            html.entities.name2codepoint,
            html.entities.codepoint2name,
            html.entities.entitydefs,
        ):
            assert type(table) is dict

    def test_html5_has_names_with_and_without_semicolons(self) -> None:
        html5 = html.entities.html5

        assert html5["amp;"] == html5["amp"] == "&"
        assert "hellip" not in html5
        assert html5["hellip;"] == "…"
        assert html5["NotEqualTilde;"] == "≂̸"

    def test_the_html4_names_are_a_subset(self) -> None:
        html5 = html.entities.html5

        assert all(name + ";" in html5 for name in html.entities.entitydefs)
        assert "NotEqualTilde;" not in html.entities.entitydefs

    def test_codepoint2name_inverts_name2codepoint(self) -> None:
        name2codepoint = html.entities.name2codepoint

        assert {v: k for k, v in name2codepoint.items()} == html.entities.codepoint2name
        assert html.entities.entitydefs["copy"] == chr(name2codepoint["copy"])


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "unescape(plain) is plain" in s)
        mutated = source.replace("unescape(plain) is plain", "unescape(plain) is not plain", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
