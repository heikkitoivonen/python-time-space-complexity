"""Tests to verify documented behaviour of the urllib package.

docs/stdlib/urllib.md covers local processing in five modules. Network waits
are external to these bounds. File and data handlers are exercised locally.

Measurement scope:

* `urlsplit()` memoizes. Splitting the same string twice returns the *same
  object* on every supported version, which needs no stopwatch. The machinery
  differs - a hand-rolled `_parse_cache` dict on 3.10, `functools.lru_cache`
  with maxsize 128 from 3.11 - and so does the payoff: a repeat split of a long
  URL costs x1.5 less on 3.10, where the cache is consulted after a pass over
  the string, and x142 less on 3.14. `urlparse()` builds a fresh six-field
  result on top; result identity alone does not establish the scanning cost.
* `urlencode()` and `parse_qsl()` charge per field, not per character. Ten
  fields of 1,000 characters against a thousand fields of ten, at comparable
  total length, cost x27 more for `urlencode` and x40 more for `parse_qsl` on
  3.10 and 3.14 alike. That is why both rows carry two size variables.
* `quote()` is linear in its input: x9.2 to x10.1 per 10x on both boundaries.
* `file:` opening is bounded relative to body size: a 4 MB body peaks at 7 KB
  during open and 4.19 MB during read. `data:` opening retains the decoded
  body before read. At 10 KB and 1 MB of literal payload, peaks are 41 KB and
  4 MB on 3.10, and 31 KB and 3 MB on 3.14.
* Opener registration counts comparisons and displaced list entries for equal,
  ascending, and descending priorities at 128 and 2,048 handlers. Each handler
  has one protocol method; callback and constructor cost are not varied.
* Robot parsing and lookup vary literal path length from 10 KB to 1 MB at one
  rule. Peaks grow from about 30 KB to 3 MB on both boundary versions. Separate
  checks vary rule count with fixed text lengths. The documented upper bounds
  cover literal paths and distinct agent groups; no supported version matches
  `*` or `$` in a rule, and a repeated agent group is never consulted, both of
  which are asserted rather than assumed.
* Warm `urlsplit` calls on the same string object at 10 KB and 1 MB take about
  10 us and 965 us on 3.10, but about 75 ns at both sizes on 3.14. The same
  object matters: an equal but newly built 1 MB URL costs about 397 us on 3.14
  against 77 ns for the object already in the cache, because a fresh string has
  to be hashed before the lookup can miss or hit.

Source evidence: Lib/urllib/{parse,request,robotparser}.py on released CPython
3.10 through 3.14 branches. In parse.py, 3.10 sanitizes before the cache lookup;
3.11+ wraps urlsplit in lru_cache. Request registration uses bisect.insort,
install_opener assigns _opener, and DataHandler decodes into BytesIO. Robot
lookup normalizes the URL and compares configured text; literal RuleLine paths
use prefix matching on every supported version.
https://github.com/python/cpython/blob/3.10/Lib/urllib/parse.py
https://github.com/python/cpython/blob/3.11/Lib/urllib/parse.py
https://github.com/python/cpython/blob/3.14/Lib/urllib/request.py
https://github.com/python/cpython/blob/3.14/Lib/urllib/robotparser.py

Not settled here:

* Anything needing an HTTP peer: redirect chains, authentication challenges,
  proxies, FTP, and `RobotFileParser.read()`. There is no server, and standing
  one up would test the server. The handler rows are read from the CPython
  source; what is exercised is the `data:` and `file:` schemes, whose handlers
  are installed by default and need no network.
* The eight fenced blocks on the page that fetch `https://example.com` are
  identified and counted rather than run, for the same reason. The other eight
  run.
* `URLopener` and `FancyURLopener` were removed in 3.14, so their row is
  version-marked and the coverage check allows them to be absent.

Axes not varied: non-ASCII and IDNA host names, `bytes` URLs through the
`*ResultBytes` types, and any `safe` set for `quote()` beyond the default.
"""

import bisect
import email.message
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
import urllib.robotparser
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "urllib.md"

EXPECTED_BLOCKS = 16
EXPECTED_NETWORK_BLOCKS = 8

SUBMODULES = {
    "parse": urllib.parse,
    "request": urllib.request,
    "error": urllib.error,
    "response": urllib.response,
    "robotparser": urllib.robotparser,
}

# Documented, but gone from 3.14. Their row has to say so.
REMOVED_IN_314 = {"URLopener", "FancyURLopener"}


def _headers(*pairs: str) -> email.message.Message:
    """A real email.message.Message, which is what these APIs carry."""
    message = email.message.Message()
    for name, value in zip(pairs[::2], pairs[1::2], strict=True):
        message[name] = value
    return message


def clear_parse_cache() -> None:
    """`urllib.parse.clear_cache()` is undeclared in typeshed but present on
    every supported version; it is the only handle on the memoization."""
    urllib.parse.clear_cache()  # type: ignore[attr-defined]


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def _documented_names() -> dict[str, set[str]]:
    """Every `urllib.<sub>.<name>` the Complexity Reference tables mention."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("\n## URL Parsing", start)
    found: dict[str, set[str]] = {sub: set() for sub in SUBMODULES}
    pattern = r"urllib\.(parse|request|error|response|robotparser)\.([A-Za-z_][A-Za-z0-9_]*)"
    for submodule, name in re.findall(pattern, text[start:end]):
        found[submodule].add(name)
    return found


class TestEveryPublicNameIsDocumented:
    """The tables have to name every entry in each submodule's `__all__`.

    `__all__` is the module's own statement of its public surface, and it is
    narrower than `dir()` here: `urllib.parse` also holds a dozen undocumented
    `split*` helpers that the module deliberately does not export.
    """

    @pytest.mark.parametrize("submodule", sorted(SUBMODULES))
    def test_no_exported_name_is_missing_from_the_tables(self, submodule: str) -> None:
        declared = set(SUBMODULES[submodule].__all__)

        missing = sorted(declared - _documented_names()[submodule])

        assert not missing, f"urllib.{submodule} names absent from the tables: {missing}"

    @pytest.mark.parametrize("submodule", sorted(SUBMODULES))
    def test_the_tables_name_nothing_that_is_not_exported(self, submodule: str) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        declared = set(SUBMODULES[submodule].__all__)

        unknown = sorted(_documented_names()[submodule] - declared - REMOVED_IN_314)

        assert not unknown, (
            f"the tables name urllib.{submodule} attributes that do not exist: {unknown}"
        )

    def test_the_removed_openers_carry_their_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        owning = [row for row in rows if "urllib.request.URLopener" in row]
        assert len(owning) == 1, f"expected one row naming URLopener, found {len(owning)}"
        assert "3.14" in owning[0], f"the URLopener row should name the removal: {owning[0]}"
        assert "urllib.request.FancyURLopener" in owning[0]

    def test_the_package_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        total = sum(len(module.__all__) for module in SUBMODULES.values())

        assert 60 <= total <= 66, f"urllib exports {total} names; re-run the coverage audit"

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"urlsplit", "quote", "parse_qsl"} <= documented["parse"]
        assert {"urlopen", "Request", "build_opener"} <= documented["request"]

        thinned = documented["parse"] - {"urljoin"}
        assert set(urllib.parse.__all__) - thinned == {"urljoin"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestUrlsplitIsMemoized:
    """`urlsplit()` hands back the same object for a string it has already
    split; `urlparse()` rebuilds its own result on top of that."""

    URL = "https://user:pass@example.com:8080/a/b/c?x=1&y=2#frag"

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Any:
        clear_parse_cache()
        yield
        clear_parse_cache()

    def test_the_same_string_yields_the_same_object(self) -> None:
        assert urllib.parse.urlsplit(self.URL) is urllib.parse.urlsplit(self.URL)

    def test_a_cleared_cache_produces_a_new_object(self) -> None:
        """So the identity above is the cache, not interning of the result."""
        first = urllib.parse.urlsplit(self.URL)
        clear_parse_cache()

        assert urllib.parse.urlsplit(self.URL) is not first

    def test_urlparse_builds_a_fresh_result(self) -> None:
        assert urllib.parse.urlparse(self.URL) is not urllib.parse.urlparse(self.URL)
        assert urllib.parse.urlparse(self.URL) == urllib.parse.urlparse(self.URL)

    def test_the_cache_is_bounded(self) -> None:
        """A stream of distinct URLs evicts what came before it."""
        first = urllib.parse.urlsplit(self.URL)
        for index in range(500):
            urllib.parse.urlsplit(f"https://example.com/{index}")

        assert urllib.parse.urlsplit(self.URL) is not first

    @pytest.mark.timing
    def test_cache_hit_scaling_matches_the_python_version(self) -> None:
        urls = ["https://example.com/" + "a" * size for size in (10_000, 1_000_000)]
        for url in urls:
            urllib.parse.urlsplit(url)
        durations = [best_ns(partial(urllib.parse.urlsplit, url), inner=50) for url in urls]
        ratio = durations[1] / durations[0]

        if sys.version_info < (3, 11):
            assert ratio > 20, f"3.10 must scan before a cache hit: {durations}, ratio={ratio}"
        else:
            assert ratio < 5, f"cache hit must avoid a URL-length scan: {durations}, ratio={ratio}"

    @pytest.mark.timing
    def test_a_repeat_split_is_cheaper_than_the_first(self) -> None:
        url = "https://example.com/" + "seg/" * 2000 + "?q=" + "v" * 2000
        urllib.parse.urlsplit(url)

        def cold() -> None:
            clear_parse_cache()
            urllib.parse.urlsplit(url)

        warm_ns = best_ns(lambda: urllib.parse.urlsplit(url), inner=20)
        cold_ns = best_ns(cold, inner=3)

        ratio = cold_ns / warm_ns
        assert ratio > 1.2, (
            f"a cached split cost x{ratio:.2f} of an uncached one "
            f"({warm_ns:.0f}ns to {cold_ns:.0f}ns); no cache at all would give x1"
        )


class TestParsingScalesWithTheUrl:
    """`urlsplit`/`urlparse` | O(n) | O(n) | n = URL length."""

    @staticmethod
    def _url(size: int) -> str:
        return "https://example.com/" + "s" * size + "?q=" + "v" * size

    def test_the_parts_come_back_whole(self) -> None:
        parts = urllib.parse.urlsplit("https://example.com/path?query=1#frag")

        assert tuple(parts) == ("https", "example.com", "/path", "query=1", "frag")
        assert urllib.parse.urlunsplit(parts) == "https://example.com/path?query=1#frag"

    @pytest.mark.timing
    def test_ten_times_the_url_costs_far_more_than_a_constant(self) -> None:
        small = self._url(1_000)
        large = self._url(10_000)

        def split(url: str) -> Callable[[], Any]:
            def run() -> None:
                clear_parse_cache()
                urllib.parse.urlsplit(url)

            return run

        small_ns = best_ns(split(small), inner=5)
        large_ns = best_ns(split(large), inner=5)

        ratio = large_ns / small_ns
        assert ratio > 2.5, (
            f"10x the URL cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a constant-time parser would give x1"
        )


class TestQuotingScalesWithTheString:
    """`quote`/`unquote` and their variants | O(n) | O(n) | n = input length."""

    def test_the_documented_results(self) -> None:
        text = "hello world & stuff"

        assert urllib.parse.quote(text) == "hello%20world%20%26%20stuff"
        assert urllib.parse.quote_plus(text) == "hello+world+%26+stuff"
        assert urllib.parse.unquote(urllib.parse.quote(text)) == text
        assert urllib.parse.unquote_plus(urllib.parse.quote_plus(text)) == text

    def test_the_bytes_forms_round_trip_too(self) -> None:
        raw = b"hello world & stuff"

        quoted = urllib.parse.quote_from_bytes(raw)

        assert urllib.parse.unquote_to_bytes(quoted) == raw

    @pytest.mark.timing
    def test_ten_times_the_input_costs_ten_times_as_much(self) -> None:
        small = "hello world & stuff " * 50
        large = "hello world & stuff " * 500

        small_ns = best_ns(lambda: urllib.parse.quote(small), inner=3)
        large_ns = best_ns(lambda: urllib.parse.quote(large), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 4, (
            f"10x the input cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a constant-time quoter would give x1"
        )


class TestQueriesChargePerField:
    """`urlencode` and `parse_qsl` carry two size variables because the field
    count drives them, not the character count."""

    FEW_LONG = {f"k{index}": "v" * 1000 for index in range(10)}
    MANY_SHORT = {f"k{index}": "v" * 10 for index in range(1000)}

    def test_the_two_shapes_are_comparable_in_length(self) -> None:
        """Otherwise the timing below would be measuring total characters."""
        few = len(urllib.parse.urlencode(self.FEW_LONG))
        many = len(urllib.parse.urlencode(self.MANY_SHORT))

        assert few == 10_039
        assert many == 15_889

    @pytest.mark.timing
    def test_urlencode_pays_for_fields_not_characters(self) -> None:
        few_ns = best_ns(lambda: urllib.parse.urlencode(self.FEW_LONG), inner=3)
        many_ns = best_ns(lambda: urllib.parse.urlencode(self.MANY_SHORT), inner=3)

        ratio = many_ns / few_ns
        assert ratio > 5, (
            f"100x the fields at 1.6x the characters cost x{ratio:.2f} "
            f"({few_ns:.0f}ns to {many_ns:.0f}ns); a per-character cost would give about x1.6"
        )

    @pytest.mark.timing
    def test_parse_qsl_pays_for_fields_not_characters(self) -> None:
        few = "&".join(f"k{index}=" + "v" * 1000 for index in range(10))
        many = "&".join(f"k{index}=v" for index in range(1000))
        assert len(many) < len(few), "the many-field query has to be the shorter string"

        few_ns = best_ns(lambda: urllib.parse.parse_qsl(few), inner=3)
        many_ns = best_ns(lambda: urllib.parse.parse_qsl(many), inner=3)

        ratio = many_ns / few_ns
        assert ratio > 5, (
            f"100x the fields in a shorter string cost x{ratio:.2f} "
            f"({few_ns:.0f}ns to {many_ns:.0f}ns); a per-character cost would give under x1"
        )


class TestQueryParsingGuards:
    """The two documented bounds on what a query string can make the parser do."""

    QUERY = "name=Alice&age=30&city=NYC&city=LA"

    def test_parse_qs_groups_repeated_keys(self) -> None:
        assert urllib.parse.parse_qs(self.QUERY) == {
            "name": ["Alice"],
            "age": ["30"],
            "city": ["NYC", "LA"],
        }

    def test_parse_qsl_keeps_them_in_order(self) -> None:
        assert urllib.parse.parse_qsl(self.QUERY) == [
            ("name", "Alice"),
            ("age", "30"),
            ("city", "NYC"),
            ("city", "LA"),
        ]

    def test_max_num_fields_bounds_the_work(self) -> None:
        with pytest.raises(ValueError, match="Max number of fields exceeded"):
            urllib.parse.parse_qsl(self.QUERY, max_num_fields=2)

    def test_only_ampersand_separates_by_default(self) -> None:
        assert urllib.parse.parse_qsl("a=1;b=2") == [("a", "1;b=2")]
        assert urllib.parse.parse_qsl("a=1;b=2", separator=";") == [("a", "1"), ("b", "2")]

    def test_doseq_is_what_expands_a_list(self) -> None:
        assert urllib.parse.urlencode({"city": ["NYC", "LA"]}, doseq=True) == "city=NYC&city=LA"
        assert "%5B" in urllib.parse.urlencode({"city": ["NYC", "LA"]})


class TestJoiningAndDefragging:
    """`urljoin` and `urldefrag`: one pass over the combined length."""

    BASE = "https://example.com/docs/guide/"

    def test_a_relative_path_walks_the_segments(self) -> None:
        joined = urllib.parse.urljoin(self.BASE, "../api/reference.html")

        assert joined == "https://example.com/docs/api/reference.html"

    def test_an_absolute_path_replaces_the_path(self) -> None:
        assert urllib.parse.urljoin(self.BASE, "/other/page.html") == (
            "https://example.com/other/page.html"
        )

    def test_an_absolute_url_replaces_everything(self) -> None:
        assert urllib.parse.urljoin(self.BASE, "https://other.example/x") == (
            "https://other.example/x"
        )

    def test_urldefrag_splits_at_the_hash(self) -> None:
        stripped, fragment = urllib.parse.urldefrag("https://example.com/p?q=1#frag")

        assert stripped == "https://example.com/p?q=1"
        assert fragment == "frag"


class TestResultTypesAreNamedTuples:
    """The six result types: fixed fields, O(1) access, O(n) to rebuild."""

    def test_the_text_and_bytes_shapes_match(self) -> None:
        text = urllib.parse.urlsplit("https://example.com/p?q=1#f")
        raw = urllib.parse.urlsplit(b"https://example.com/p?q=1#f")

        assert isinstance(text, urllib.parse.SplitResult)
        assert isinstance(raw, urllib.parse.SplitResultBytes)
        assert len(text) == len(raw) == 5

    def test_parse_results_carry_the_extra_params_field(self) -> None:
        parsed = urllib.parse.urlparse("https://example.com/p;param?q=1#f")

        assert isinstance(parsed, urllib.parse.ParseResult)
        assert len(parsed) == 6
        assert parsed.params == "param"
        assert isinstance(urllib.parse.urlparse(b"https://x/"), urllib.parse.ParseResultBytes)

    def test_defrag_results_hold_two_fields(self) -> None:
        result = urllib.parse.urldefrag("https://example.com/p#f")

        assert isinstance(result, urllib.parse.DefragResult)
        assert len(result) == 2
        assert isinstance(urllib.parse.urldefrag(b"https://x/#f"), urllib.parse.DefragResultBytes)

    def test_geturl_rebuilds_rather_than_remembers(self) -> None:
        url = "https://example.com/p?q=1#f"

        assert urllib.parse.urlsplit(url).geturl() == url
        assert urllib.parse.urlparse(url).geturl() == url


class TestUrlopenSchemeBuffering:
    """File URLs stream; data URLs decode and retain their body during open."""

    BODY = b"x" * (4 * 1024 * 1024)

    @pytest.fixture
    def file_url(self, tmp_path: pathlib.Path) -> str:
        path = tmp_path / "big.bin"
        path.write_bytes(self.BODY)
        url = "file:" + urllib.request.pathname2url(str(path))
        urllib.request.urlopen(url).close()  # warm the handler machinery
        return url

    def test_opening_holds_nothing_and_reading_holds_it_all(self, file_url: str) -> None:
        response = urllib.request.urlopen(file_url)
        try:
            open_peak = peak_bytes(lambda: urllib.request.urlopen(file_url).close())
            read_peak = peak_bytes(response.read)
        finally:
            response.close()

        assert open_peak < len(self.BODY) // 8, f"urlopen buffered {open_peak} bytes"
        assert read_peak > len(self.BODY) * 0.9, f"read() peaked at only {read_peak} bytes"

    def test_metadata_is_available_before_the_body(self, file_url: str) -> None:
        with urllib.request.urlopen(file_url) as response:
            length = response.headers["Content-Length"]

            assert int(length) == len(self.BODY)
            assert response.read() == self.BODY

    def test_a_data_url_is_decoded_in_process(self) -> None:
        with urllib.request.urlopen("data:,hello%20world") as response:
            assert response.read() == b"hello world"

    @pytest.mark.parametrize("encoding", ["percent", "base64"])
    def test_data_open_allocates_the_body_before_reading(self, encoding: str) -> None:
        import base64
        import io

        urllib.request.urlopen("data:,warm").close()
        peaks = []
        for size in (10_000, 1_000_000):
            body = b"x" * size
            url = (
                "data:," + "%78" * size
                if encoding == "percent"
                else "data:;base64," + base64.b64encode(body).decode("ascii")
            )
            peaks.append(peak_bytes(lambda url=url: urllib.request.urlopen(url).close()))
            with urllib.request.urlopen(url) as response:
                assert isinstance(response.fp, io.BytesIO)
                assert response.fp.getvalue() == body
                assert response.fp.tell() == 0

        assert peaks[1] > 20 * peaks[0], f"opening must allocate with payload size: {peaks}"

    def test_read_with_a_size_bounds_both(self, file_url: str) -> None:
        with urllib.request.urlopen(file_url) as response:
            chunk = response.read(1024)

        assert len(chunk) == 1024


class TestRequestSplitsItsUrlOnce:
    """`Request(url, ...)`: the URL is split at construction, not per send."""

    def test_the_parts_are_available_without_sending(self) -> None:
        request = urllib.request.Request(
            "https://example.com/path?q=1", headers={"User-Agent": "MyBot/1.0"}
        )

        assert request.type == "https"
        assert request.host == "example.com"
        assert request.selector == "/path?q=1"
        assert request.get_header("User-agent") == "MyBot/1.0"

    def test_data_selects_post_without_an_explicit_method(self) -> None:
        body = urllib.parse.urlencode({"username": "alice"}).encode("utf-8")

        assert urllib.request.Request("https://example.com", data=body).get_method() == "POST"
        assert urllib.request.Request("https://example.com").get_method() == "GET"


class TestOpenerRegistration:
    """Sorted handler insertion: O(h log h) comparisons and O(h²) worst-case shifts."""

    def test_build_opener_registers_the_default_handlers(self) -> None:
        opener = urllib.request.build_opener()

        handlers = opener.handlers  # type: ignore[attr-defined]
        classes = {type(handler).__name__ for handler in handlers}
        assert {"HTTPHandler", "FileHandler", "DataHandler", "UnknownHandler"} <= classes

    def test_an_extra_handler_joins_them(self) -> None:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

        handlers = opener.handlers  # type: ignore[attr-defined]
        classes = {type(handler).__name__ for handler in handlers}
        assert "HTTPCookieProcessor" in classes

    @pytest.mark.parametrize("order", ["equal", "ascending", "descending"])
    def test_registration_comparisons_and_shifts_grow_with_handlers(
        self, monkeypatch: pytest.MonkeyPatch, order: str
    ) -> None:
        comparisons = 0
        shifted = 0

        class Handler(urllib.request.BaseHandler):
            def __init__(self, priority: int) -> None:
                self.handler_order = priority  # type: ignore[misc]

            def sample_open(self, request: Any) -> None:
                pass

            def __lt__(self, other: Any) -> bool:
                nonlocal comparisons
                comparisons += 1
                return self.handler_order < other.handler_order

        original = bisect.insort

        def record_insert(items: list[Any], handler: Any) -> None:
            nonlocal shifted
            original(items, handler)
            if isinstance(handler, Handler):
                position = next(i for i, item in enumerate(items) if item is handler)
                shifted += len(items) - position - 1

        monkeypatch.setattr(bisect, "insort", record_insert)
        counts = []
        for size in (128, 2048):
            comparisons = shifted = 0
            priorities = {
                "equal": [2000] * size,
                "ascending": list(range(2000, 2000 + size)),
                "descending": list(range(2000 + size, 2000, -1)),
            }[order]
            handlers = [Handler(priority) for priority in priorities]
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), *handlers)
            counts.append(comparisons)
            registered = opener.handle_open["sample"]  # type: ignore[attr-defined]
            assert len(registered) == size
            assert [h.handler_order for h in registered] == sorted(priorities)
            if order == "descending":
                assert shifted == size * (size - 1), (size, shifted)
            else:
                assert shifted == 0, (order, size, shifted)

        assert 18 < counts[1] / counts[0] < 35, f"expected h log h comparisons: {counts}"

    def test_install_opener_only_installs_the_supplied_object(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opener = urllib.request.OpenerDirector()
        monkeypatch.setattr(urllib.request, "_opener", None)

        def unexpected_registration(handler: Any) -> None:
            pytest.fail("install_opener must not register handlers")

        monkeypatch.setattr(opener, "add_handler", unexpected_registration)
        assert urllib.request.install_opener(opener) is None
        assert urllib.request._opener is opener  # type: ignore[attr-defined]

    def test_a_proxy_handler_installs_one_method_per_scheme(self) -> None:
        handler = urllib.request.ProxyHandler({"http": "http://p:1", "https": "http://p:2"})

        proxies = handler.proxies  # type: ignore[attr-defined]
        assert proxies == {"http": "http://p:1", "https": "http://p:2"}
        assert hasattr(handler, "http_open")
        assert hasattr(handler, "https_open")

    def test_getproxies_reads_the_environment(self) -> None:
        assert isinstance(urllib.request.getproxies(), dict)


class TestPasswordManagersScanTheirUris:
    """`HTTPPasswordMgr` and friends | O(u) | O(u) | u = stored URIs."""

    def test_a_lookup_matches_by_path_prefix(self) -> None:
        manager = urllib.request.HTTPPasswordMgr()
        manager.add_password("realm", "https://example.com/docs/", "alice", "secret")

        assert manager.find_user_password("realm", "https://example.com/docs/a") == (
            "alice",
            "secret",
        )
        assert manager.find_user_password("realm", "https://example.com/other") == (None, None)

    def test_the_default_realm_manager_falls_back(self) -> None:
        manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, "https://example.com/", "alice", "secret")

        assert manager.find_user_password("any realm", "https://example.com/x") == (
            "alice",
            "secret",
        )

    def test_the_prior_auth_manager_records_what_it_was_told(self) -> None:
        manager = urllib.request.HTTPPasswordMgrWithPriorAuth()
        manager.add_password(None, "https://example.com/", "alice", "secret", is_authenticated=True)

        assert manager.is_authenticated("https://example.com/x") is True


class TestPathAndUrlConversion:
    """`pathname2url`/`url2pathname` | O(n) | O(n) | n = path length."""

    def test_they_round_trip(self) -> None:
        path = "/tmp/a b/c#d"

        assert urllib.request.url2pathname(urllib.request.pathname2url(path)) == path

    def test_the_url_form_is_quoted(self) -> None:
        assert "%20" in urllib.request.pathname2url("/tmp/a b")


class TestErrorsCarryTheirResponse:
    """`HTTPError` is a response as well as an exception, so reading its body
    costs the same O(n) as reading a successful one."""

    def test_an_http_error_is_readable(self) -> None:
        import io

        error = urllib.error.HTTPError(
            "https://example.com/x", 404, "Not Found", _headers(), io.BytesIO(b"missing")
        )

        assert error.code == 404
        assert error.read() == b"missing"

    def test_the_error_hierarchy(self) -> None:
        assert issubclass(urllib.error.HTTPError, urllib.error.URLError)
        assert issubclass(urllib.error.URLError, OSError)
        assert issubclass(urllib.error.ContentTooShortError, urllib.error.URLError)

    def test_content_too_short_keeps_what_arrived(self) -> None:
        """urlretrieve raises it with the (filename, headers) it got so far."""
        partial = ("partial.txt", _headers())
        error = urllib.error.ContentTooShortError("short", partial)

        assert error.content == partial


class TestResponseWrappersAddNoBuffering:
    """`urllib.response.*`: attributes over an already-open stream."""

    def test_addinfourl_exposes_the_metadata(self) -> None:
        import io

        wrapped = urllib.response.addinfourl(
            io.BytesIO(b"body"),
            _headers("Content-Type", "text/plain"),
            "https://example.com/x",
            200,
        )

        assert wrapped.status == 200
        assert wrapped.url == "https://example.com/x"
        assert wrapped.read() == b"body"

    def test_addbase_and_addinfo_wrap_the_same_stream(self) -> None:
        import io

        stream = io.BytesIO(b"body")
        base = urllib.response.addbase(stream)

        assert base.fp is stream
        assert urllib.response.addinfo(io.BytesIO(b"x"), _headers()).info() is not None

    def test_addclosehook_runs_one_callback(self) -> None:
        import io

        calls: list[str] = []
        hooked = urllib.response.addclosehook(io.BytesIO(b"x"), calls.append, "closed")

        hooked.close()

        assert calls == ["closed"]


class TestRobotFileParserScansItsRules:
    """Literal rule parsing and lookup depend on text lengths as well as counts."""

    @staticmethod
    def _parser(lines: list[str]) -> urllib.robotparser.RobotFileParser:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(lines)
        return parser

    def test_a_disallowed_prefix_blocks_and_an_allowed_one_does_not(self) -> None:
        parser = self._parser(["User-agent: *", "Disallow: /private", "Allow: /public"])

        assert parser.can_fetch("bot", "http://example.com/public/a") is True
        assert parser.can_fetch("bot", "http://example.com/private/a") is False

    def test_a_named_agent_wins_over_the_wildcard(self) -> None:
        parser = self._parser(
            ["User-agent: *", "Disallow: /", "User-agent: goodbot", "Disallow: /admin"]
        )

        assert parser.can_fetch("goodbot", "http://example.com/x") is True
        assert parser.can_fetch("otherbot", "http://example.com/x") is False

    def test_crawl_delay_and_request_rate_are_read_off_the_same_entry(self) -> None:
        parser = self._parser(
            ["User-agent: bot", "Crawl-delay: 5", "Request-rate: 1/10", "Disallow:"]
        )

        assert parser.crawl_delay("bot") == 5
        rate = parser.request_rate("bot")
        assert rate is not None
        assert (rate.requests, rate.seconds) == (1, 10)

    def test_no_supported_version_matches_a_wildcard_or_anchor(self) -> None:
        """The page says rules are literal prefixes; a hedge would say maybe."""
        parser = self._parser(["User-agent: *", "Disallow: /a*/secret", "Disallow: /end$"])

        # `*` is a character in the path, not a wildcard
        assert parser.can_fetch("bot", "https://example.com/ax/secret") is True
        assert parser.can_fetch("bot", "https://example.com/a*/secret") is False

        # `$` is a character too, so it anchors nothing
        assert parser.can_fetch("bot", "https://example.com/end") is True
        assert parser.can_fetch("bot", "https://example.com/end$") is False

    def test_a_repeated_agent_group_is_never_consulted(self) -> None:
        """`can_fetch` returns on the first entry that applies."""
        parser = self._parser(
            ["User-agent: bot", "Disallow: /one", "User-agent: bot", "Disallow: /two"]
        )

        assert parser.can_fetch("bot", "https://example.com/one") is False
        assert parser.can_fetch("bot", "https://example.com/two") is True

    def test_parse_and_lookup_allocate_with_text_length_at_fixed_rule_count(self) -> None:
        parse_peaks, lookup_peaks = [], []
        try:
            for size in (10_000, 1_000_000):
                path = "/" + "a" * size
                lines = ["User-agent: *", "Disallow: " + path]
                parser = urllib.robotparser.RobotFileParser()
                clear_parse_cache()
                parse_peaks.append(peak_bytes(partial(parser.parse, lines)))
                assert path in str(parser)
                url = "https://example.com" + path
                clear_parse_cache()
                lookup_peaks.append(peak_bytes(partial(parser.can_fetch, "bot", url)))
                assert parser.can_fetch("bot", url) is False

            for peaks in (parse_peaks, lookup_peaks):
                assert peaks[1] > 20 * peaks[0], (
                    f"fixed rule count still allocates with text: {peaks}"
                )
        finally:
            clear_parse_cache()

    def test_rule_count_controls_retained_records_and_prefix_checks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rule_type = urllib.robotparser.RuleLine  # type: ignore[attr-defined]
        original = rule_type.applies_to
        checked = 0

        def record(rule: Any, path: str) -> Any:
            nonlocal checked
            checked += 1
            return original(rule, path)

        monkeypatch.setattr(rule_type, "applies_to", record)
        for size in (10, 1000):
            parser = self._parser(["User-agent: *"] + ["Disallow: /blocked"] * size)
            assert str(parser).count("Disallow: /blocked") == size
            checked = 0
            assert parser.can_fetch("bot", "https://example.com/allowed") is True
            assert checked == size

    @pytest.mark.parametrize("growing_agent", ["caller", "configured"])
    def test_lookup_allocates_with_agent_text_at_fixed_url_length(self, growing_agent: str) -> None:
        peaks = []
        for size in (10_000, 1_000_000):
            caller = "B" * size if growing_agent == "caller" else "bot"
            configured = "A" * size if growing_agent == "configured" else "otherbot"
            parser = self._parser(["User-agent: " + configured, "Disallow: /"])
            url = "https://example.com/path"
            peaks.append(peak_bytes(partial(parser.can_fetch, caller, url)))
            assert parser.can_fetch(caller, url) is True

        assert peaks[1] > 20 * peaks[0], f"agent text must count toward lookup space: {peaks}"


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


def _needs_network(source: str) -> bool:
    """A block that fetches an http(s) URL cannot run without a peer."""
    fetches = "urlopen(" in source or "urlretrieve(" in source
    return fetches and "data:," not in source


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block is either run or counted as needing a peer."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_the_unrunnable_blocks_are_the_ones_that_fetch(self) -> None:
        """Counted rather than skipped silently, so the gap stays visible."""
        network = [line for line, source in _blocks() if _needs_network(source)]

        assert len(network) == EXPECTED_NETWORK_BLOCKS, (
            f"expected {EXPECTED_NETWORK_BLOCKS} blocks needing a peer, found {network}"
        )

    def test_every_other_block_runs(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            if _needs_network(source):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS - EXPECTED_NETWORK_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = next(source for line, source in _blocks() if not _needs_network(source))
        broken = original.replace(
            "from urllib.parse import", "from urllib.parse import missing,", 1
        )
        assert broken != original, "the mutation did not reach an import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr


class TestTemporaryFileCleanup:
    """`urlcleanup()` | O(k) | O(1) | k = temporary files left by urlretrieve."""

    def test_it_is_safe_with_nothing_to_clean(self) -> None:
        urllib.request.urlcleanup()

        assert urllib.request.urlcleanup() is None

    def test_urlretrieve_writes_where_it_is_told(self, tmp_path: pathlib.Path) -> None:
        """The `file:` scheme again, so no peer is involved."""
        source = tmp_path / "source.txt"
        source.write_text("body")
        target = tmp_path / "copy.txt"

        with tempfile.TemporaryDirectory():
            filename, headers = urllib.request.urlretrieve(
                "file:" + urllib.request.pathname2url(str(source)), str(target)
            )

        assert pathlib.Path(filename) == target
        assert target.read_text() == "body"
        assert headers is not None

    def test_data_urlretrieve_buffers_despite_chunked_copy(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "data.txt"
        peaks = []
        urllib.request.urlopen("data:,warm").close()
        for size in (10_000, 1_000_000):
            url = "data:," + "x" * size
            peaks.append(peak_bytes(partial(urllib.request.urlretrieve, url, str(target))))
            assert target.stat().st_size == size

        assert peaks[1] > 20 * peaks[0], f"data URL opening retains the body: {peaks}"
