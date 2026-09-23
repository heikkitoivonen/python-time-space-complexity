"""Tests for docs/stdlib/urllib.md.

The page prices parsing as one pass over the text, opening a URL as the work
up to the headers with the body left unread, and every handler, cookie,
password and robots.txt lookup by what it scans. Parsing rows are settled by
traced allocation over inputs 100x apart, which separates allocation that grows
with the input from allocation that does not, with no tolerance, while the
linear upper bounds are read from source; dispatch, cookie, password and robots.txt
scans are settled by counting the calls a scan makes; and every row that needs
an HTTP peer is driven through an in-process handler that answers `http:`
requests, so the redirect and authentication round trips are counted rather
than assumed.

Measurement scope:

* `urlsplit()` returns the same object for the same string on every
  supported version, a new one after `clear_cache()`, and a new one after 500
  other URLs, so the cache is bounded. On 3.11+ a warm split of a 1,000,000
  character URL costs under 5x a 10,000 character one (about 75 ns at both
  sizes on 3.14); on 3.10 it costs over 20x, because the URL is scanned
  before the cache is consulted. `urlparse()` returns a new, equal result on
  every call.
* Linear space, one probe per row: the traced peak grows more than 20x from
  10,000 to 1,000,000 characters for `urlsplit` (cache cleared), `urlparse`,
  `urlunsplit`, `urlunparse`, `urljoin`, `urldefrag`, `unwrap`, the six quote
  and unquote functions, `geturl()`, `encode()`, `decode()`, `pathname2url`,
  `url2pathname`, `Request()`, `RobotFileParser()` and `set_url()`. Growth
  shows the n term; that none is worse than linear is read from
  Lib/urllib/parse.py and Lib/urllib/request.py. A timing test adds that 10x
  the input costs `quote()` over 4x and `urlsplit()` over 2.5x.
* `hostname`, `port`, `username` and `password` are properties, and each
  access allocates more than 20x as much for a 1,000,000 character `netloc` as
  for a 10,000 character one.
* Per-field cost: ten 1,000-character fields against a thousand 10-character
  ones, about 1.6x the characters, cost `urlencode` over 5x more (x27
  measured); the thousand-field query is the shorter string and costs
  `parse_qsl` over 5x more (x40 measured). `max_num_fields=1` on a
  1,000,000-character, 200,000-field query raises with a traced peak under
  64 KB, so the query is not split; that the count comes before any field is
  built is read from `parse_qsl` in Lib/urllib/parse.py. `doseq`, `separator` and `parse_qs` grouping
  are asserted by output.
* Opening a 4 MB `file:` URL peaks under 512 KB, reading it over 3.6 MB, and
  `read(1024)` under 64 KB. The first line of a one-line 4 MB file peaks over
  3.6 MB; the first line of a 4 MB file of short lines peaks under 64 KB.
  Opening a `data:` URL of 1,000,000 characters allocates more than 20x the
  10,000-character one, percent- and base64-encoded, and the response is a
  `BytesIO` already holding the decoded body.
* `urlretrieve()` of a 4 MB `file:` URL to a named file peaks under 512 KB
  and calls `reporthook` 513 times with the same block size, one call per
  block plus one before the first. A `file:` URL with no filename returns the
  source's own path and creates no temporary file; `data:` URLs with no
  filename create k temporary files, and `urlcleanup()` removes exactly those
  k with k `os.unlink` calls at k = 3 and 30, and uninstalls the installed
  opener. A response that stops short of its `Content-Length` raises
  `ContentTooShortError` carrying `(filename, headers)`.
* `build_opener()` registration counts comparisons and displaced list
  entries at 128 and 2,048 handlers: equal and ascending priorities displace
  nothing, descending ones displace h(h - 1) entries, so the worst case is
  quadratic. `OpenerDirector.open()` calls each of 10 or 100 registered
  request processors exactly once, and `error()` each of 10 or 100
  `http_error_418` handlers once before the default.
* Round trips, through the in-process handler: a redirect to a new URL each
  time stops with `HTTPError` after 11 requests, one to the same URL after 5,
  and a cycle through three URLs after 13, so the limits count distinct URLs
  and visits per URL rather than redirects. Each redirect response's body is
  read to the end, 1,000,000 bytes of it, and closed before the next
  request; the final response's body is untouched. That the read is one
  unbounded `fp.read()`, so O(b) space, is read from
  `HTTPRedirectHandler.http_error_302` in Lib/urllib/request.py. 308 is followed on 3.11+ and raised on 3.10.
  `redirect_request()` keeps an ordinary header and `Content-Encoding`, and
  drops the body with `Content-Length` and `Content-Type`. Basic and digest challenges each take 2 requests; basic
  with `HTTPPasswordMgrWithPriorAuth` and `is_authenticated=True` takes 1,
  and the handler asks that manager `is_authenticated()` once per request.
* Scans: a request through `HTTPCookieProcessor` calls the policy's
  `domain_return_ok` once per domain, 10 and 1,000 times for one cookie per
  domain on an unrelated host. The sort of the matching cookies by path, the
  log c in the row, is read from `CookieJar._cookie_attrs` in
  Lib/http/cookiejar.py and is not measured. A missed `find_user_password()` and a false
  `is_authenticated()` call `is_suburi` the same number of times per stored
  URI at u = 10 and 1,000, so the scan is linear in u.
  `ProxyHandler` installs one `<scheme>_open` per entry, calls `getproxies()`
  once when given no mapping, and `getproxies()` takes items from an
  environment of 10 and 1,000 variables in proportion, returning only the
  `*_proxy` ones.
* `Request` behaviour is asserted directly: parts after construction,
  `capitalize()`d keys, exact-case lookups, `header_items()` returning a new
  list of both header sets, `data` reassignment dropping `Content-length`,
  the fragment rejoined by `full_url` and carried into the selector by
  `set_proxy()`, and re-splitting on assignment.
* robots.txt: `can_fetch()` is `False` and `crawl_delay()` `None` before a
  parse. An agent matching none of g named groups makes `can_fetch()`,
  `crawl_delay()` and `request_rate()` call `Entry.applies_to` g times at
  g = 10 and 1,000. A single group naming A agents is scanned once per
  unmatched lookup before RFC 9309 and A times on the RFC 9309 releases,
  whose name-to-group map lists the group once per agent, so each lookup
  there costs A² name comparisons; the page prices a group as naming a few
  agents, and this test records the shape at A = 10 and 100. The selected
  group's rules are each tested once for an
  allowed URL at 10 and 1,000 rules, and a blocked URL stops at the first on
  releases before RFC 9309. Parse and lookup peaks grow more than 20x from a
  10,000 to a 1,000,000 character rule path at one rule. Repeating one agent
  across g single-rule groups copies 2 + 3 + ... + g rule references on the
  RFC 9309 releases (3.13.14+, 3.14.5+) and none before; one group holding
  the same rules copies none. Wildcard rules are compiled once, at parse
  time, and reused by lookups. The version-dependent answers - wildcards,
  `$`, longest match with `Allow` winning ties, merged groups - are asserted
  per release, including a longer `Disallow` beating a shorter `Allow`,
  which is what separates longest-match from "Allow wins". `read()` is
  exercised through a `file:` URL, and through the in-process peer a 401 or
  403 answer disallows everything and a 404 allows everything.
  `site_maps()` returns the same list object each time.
* On 3.10 to 3.13, `URLopener` warns on construction and calls `getproxies()`
  with no mapping, `open()` returns a stream over an unread local file,
  `retrieve()` returns a local file's own path,
  `open_unknown()` raises `OSError`, and `FancyURLopener.prompt_user_passwd()`
  returns what `input()` and `getpass()` supplied. Both classes are asserted
  absent from 3.14.
* `urlopen()` is asserted to take `cafile` before 3.13 and not from it.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Real network behaviour: HTTP and HTTPS connection cost, TLS, FTP and
  `CacheFTPHandler` reuse, proxies in use, and `read()` of a real
  `robots.txt`. The in-process handler stands in for the peer, so what is
  settled is how many requests urllib makes, not what they cost on a wire.
* The fixed number of hashes per digest retry is read from
  `AbstractDigestAuthHandler.get_authorization` in Lib/urllib/request.py;
  only the retry count is observed.
* `getproxies()` on macOS and Windows reads system settings when no
  `*_proxy` variable is set; only Linux runs here, so that fallback is
  sourced, not run, and the environment test is skipped elsewhere.
* A wildcard rule's matching cost is the regular expression's, which is
  `re`'s to document; only that the matcher is prepared once is observed.
* The audit lists `BaseHandler.default_open`, `unknown_open` and
  `http_error_default` as unresolved because they are hooks a subclass
  defines rather than attributes of `BaseHandler`, and
  `urllib.parse.urllib.parse.SplitResult.geturl` because the official
  inventory spells it that way. All four are documented.

Axes not varied: URI length in password lookups, which the n in O(u·n)
reads from `is_suburi` in Lib/urllib/request.py; non-ASCII and IDNA host names, `safe` sets beyond the
default, header counts on the in-process peer, several agents per robots.txt
group, and user-agent name length, which the page prices at O(1).
"""

from __future__ import annotations

import base64
import bisect
import builtins
import getpass
import http.client
import http.cookiejar
import inspect
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
import urllib.robotparser
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "urllib.md"
EXPECTED_BLOCKS = 11

# RFC 9309 was backported to these maintenance releases, not to 3.10-3.12.
ROBOT_RFC_9309 = sys.version_info >= (3, 14, 5) or ((3, 13, 14) <= sys.version_info < (3, 14))
HAS_URLOPENER = sys.version_info < (3, 14)

SMALL, LARGE = 10_000, 1_000_000


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


def clear_parse_cache() -> None:
    """`urllib.parse.clear_cache()` is undeclared in typeshed but present on
    every supported version; it is the only handle on the memoization."""
    urllib.parse.clear_cache()  # type: ignore[attr-defined]


def headers(**fields: str) -> http.client.HTTPMessage:
    """A real HTTPMessage, which is what these APIs carry."""
    message = http.client.HTTPMessage()
    for name, value in fields.items():
        message[name.replace("_", "-")] = value
    return message


class SocketLikeStream(io.RawIOBase):
    """Copies its bytes out through `readinto`, as a socket does.

    A `BytesIO`, raw or buffered, can hand back its own buffer from `read()`
    without copying, which would hide the cost of reading a body.
    """

    def __init__(self, data: bytes) -> None:
        self._data = memoryview(data)
        self.offset = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        chunk = self._data[self.offset : self.offset + len(buffer)]
        buffer[: len(chunk)] = chunk
        self.offset += len(chunk)
        return len(chunk)


class Peer(urllib.request.BaseHandler):
    """Answers `http:` requests in process and records each one."""

    def __init__(self, route: Callable[[urllib.request.Request], tuple[int, Any, bytes]]) -> None:
        self.route = route
        self.requests: list[urllib.request.Request] = []

    def http_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        self.requests.append(req)
        code, message_headers, body = self.route(req)
        stream = io.BufferedReader(SocketLikeStream(body))
        response = urllib.response.addinfourl(stream, message_headers, req.full_url, code)
        response.msg = "peer"  # type: ignore[attr-defined]
        return response


def peer_opener(peer: Peer, *extra: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    """An opener with only the peer, the HTTP error machinery and `extra`."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        peer,
        urllib.request.HTTPErrorProcessor(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        *extra,
    ):
        opener.add_handler(handler)
    return opener


def assert_linear_space(make: Callable[[int], Callable[[], Any]], what: str) -> None:
    """The peak grows more than 20x when the input grows 100x.

    The `urlsplit` cache is cleared inside each measured call, so a warm-up
    or an earlier test cannot turn the measurement into a cache hit.
    """

    def cold(func: Callable[[], Any]) -> Callable[[], None]:
        def run() -> None:
            clear_parse_cache()
            func()

        return run

    small, large = cold(make(SMALL)), cold(make(LARGE))
    small()
    large()
    try:
        peaks = [peak_bytes(small), peak_bytes(large)]
    finally:
        clear_parse_cache()
    assert peaks[1] > 20 * peaks[0], f"{what} did not allocate with its input: {peaks}"


class TestUrlsplitIsCached:
    """`urlsplit` | O(n), and a cache hit for the same string object is O(1)
    on 3.11+; `urlparse` builds a new result on every call."""

    URL = "https://user:pass@example.com:8080/a/b/c?x=1&y=2#frag"

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Iterator[None]:
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

    def test_the_cache_is_bounded(self) -> None:
        first = urllib.parse.urlsplit(self.URL)
        for index in range(500):
            urllib.parse.urlsplit(f"https://example.com/{index}")

        assert urllib.parse.urlsplit(self.URL) is not first

    def test_urlparse_builds_a_new_result(self) -> None:
        assert urllib.parse.urlparse(self.URL) is not urllib.parse.urlparse(self.URL)
        assert urllib.parse.urlparse(self.URL) == urllib.parse.urlparse(self.URL)

    @pytest.mark.timing
    def test_a_cache_hit_scales_with_the_python_version(self) -> None:
        urls = ["https://example.com/" + "a" * size for size in (SMALL, LARGE)]
        for url in urls:
            urllib.parse.urlsplit(url)
        durations = [best_ns(partial(urllib.parse.urlsplit, url), inner=50) for url in urls]
        ratio = durations[1] / durations[0]

        if sys.version_info < (3, 11):
            assert ratio > 20, f"3.10 must scan before a cache hit: {durations}, ratio={ratio}"
        else:
            assert ratio < 5, f"a cache hit must not scan the URL: {durations}, ratio={ratio}"


class TestParsingIsLinear:
    """Every `urllib.parse` row, the result methods, the path conversions and
    `Request()` | O(n) | O(n): the peak grows with the input."""

    @staticmethod
    def _url(size: int) -> str:
        return "https://example.com/" + "s" * size + "?q=" + "v" * size + "#f"

    CASES: dict[str, Callable[[int], Callable[[], Any]]] = {
        "urlsplit": lambda size: partial(urllib.parse.urlsplit, "http://h/" + "p" * size),
        "urlparse": lambda size: partial(urllib.parse.urlparse, "http://h/" + "p" * size),
        "urlunsplit": lambda size: partial(
            urllib.parse.urlunsplit, ("https", "h", "/" + "p" * size, "q", "")
        ),
        "urlunparse": lambda size: partial(
            urllib.parse.urlunparse, ("https", "h", "/" + "p" * size, "", "q", "")
        ),
        "urljoin": lambda size: partial(urllib.parse.urljoin, "https://h/a/b/", "../" + "p" * size),
        "urldefrag": lambda size: partial(urllib.parse.urldefrag, "http://h/" + "p" * size + "#f"),
        "unwrap": lambda size: partial(urllib.parse.unwrap, "<URL:http://h/" + "p" * size + ">"),
        "quote": lambda size: partial(urllib.parse.quote, "a b" * (size // 3)),
        "quote_plus": lambda size: partial(urllib.parse.quote_plus, "a b" * (size // 3)),
        "quote_from_bytes": lambda size: partial(
            urllib.parse.quote_from_bytes, b"a b" * (size // 3)
        ),
        "unquote": lambda size: partial(urllib.parse.unquote, "a%20" * (size // 4)),
        "unquote_plus": lambda size: partial(urllib.parse.unquote_plus, "a+b" * (size // 3)),
        "unquote_to_bytes": lambda size: partial(
            urllib.parse.unquote_to_bytes, "a%20" * (size // 4)
        ),
        "pathname2url": lambda size: partial(urllib.request.pathname2url, "/a b" * (size // 4)),
        "url2pathname": lambda size: partial(urllib.request.url2pathname, "/a%20" * (size // 5)),
        "Request": lambda size: partial(urllib.request.Request, "http://h/" + "p" * size),
        "RobotFileParser": lambda size: partial(
            urllib.robotparser.RobotFileParser, "http://h/" + "p" * size
        ),
        "set_url": lambda size: partial(
            urllib.robotparser.RobotFileParser().set_url, "http://h/" + "p" * size
        ),
    }

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_each_function_allocates_with_its_input(self, name: str) -> None:
        assert_linear_space(self.CASES[name], name)

    @pytest.mark.parametrize("method", ["geturl", "encode"])
    def test_result_methods_rebuild_the_text(self, method: str) -> None:
        results = {size: urllib.parse.urlsplit(self._url(size)) for size in (SMALL, LARGE)}

        assert_linear_space(lambda size: getattr(results[size], method), f"SplitResult.{method}")
        assert results[SMALL].geturl() == self._url(SMALL)

    def test_decode_rebuilds_the_text(self) -> None:
        results = {size: urllib.parse.urlsplit(self._url(size).encode()) for size in (SMALL, LARGE)}

        assert_linear_space(lambda size: results[size].decode, "SplitResultBytes.decode")

    def test_unwrap_strips_the_wrapper(self) -> None:
        assert urllib.parse.unwrap("<URL:http://h/p>") == "http://h/p"

    def test_urlparse_separates_params(self) -> None:
        assert urllib.parse.urlparse("https://h/docs/page;v=1?q=1").params == "v=1"

    @pytest.mark.timing
    def test_ten_times_the_url_costs_more_than_a_constant(self) -> None:
        def split(url: str) -> Callable[[], None]:
            def run() -> None:
                clear_parse_cache()
                urllib.parse.urlsplit(url)

            return run

        small_ns = best_ns(split(self._url(1_000)), inner=5)
        large_ns = best_ns(split(self._url(10_000)), inner=5)

        ratio = large_ns / small_ns
        assert ratio > 2.5, f"10x the URL cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"

    @pytest.mark.timing
    def test_ten_times_the_input_costs_quote_more_than_a_constant(self) -> None:
        small = "hello world & stuff " * 50
        large = "hello world & stuff " * 500

        small_ns = best_ns(lambda: urllib.parse.quote(small), inner=3)
        large_ns = best_ns(lambda: urllib.parse.quote(large), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 4, f"10x the input cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"


class TestComponentsAreComputedOnAccess:
    """`SplitResult.hostname`, `.port`, `.username`, `.password` | O(n) in
    `netloc`: properties, not stored fields."""

    @pytest.mark.parametrize("name", ["hostname", "port", "username", "password"])
    def test_each_is_a_property(self, name: str) -> None:
        assert isinstance(inspect.getattr_static(urllib.parse.SplitResult, name), property)

    @pytest.mark.parametrize("name", ["hostname", "port", "username", "password"])
    def test_each_access_allocates_with_the_netloc(self, name: str) -> None:
        results = {
            size: urllib.parse.urlsplit(f"https://{'u' * size}:pw@Host.example:8080/")
            for size in (SMALL, LARGE)
        }

        assert_linear_space(lambda size: partial(getattr, results[size], name), name)

    def test_the_documented_values(self) -> None:
        parts = urllib.parse.urlsplit("https://user:pass@Example.com:8080/p")

        assert (parts.hostname, parts.port) == ("example.com", 8080)
        assert (parts.username, parts.password) == ("user", "pass")


class TestQueriesChargePerField:
    """`urlencode` and `parse_qsl` | O(n + f): the field count drives them."""

    FEW_LONG = {f"k{index}": "v" * 1000 for index in range(10)}
    MANY_SHORT = {f"k{index}": "v" * 10 for index in range(1000)}

    def test_the_two_shapes_are_comparable_in_length(self) -> None:
        """Otherwise the timing below would be measuring total characters."""
        assert len(urllib.parse.urlencode(self.FEW_LONG)) == 10_039
        assert len(urllib.parse.urlencode(self.MANY_SHORT)) == 15_889

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

    def test_max_num_fields_raises_before_splitting_the_query(self) -> None:
        query = "&".join(["a=1234"] * 200_000)
        assert len(query) > 1_000_000

        def parse() -> None:
            with pytest.raises(ValueError, match="Max number of fields exceeded"):
                urllib.parse.parse_qsl(query, max_num_fields=1)

        parse()
        peak = peak_bytes(parse)

        assert peak < 64_000, f"max_num_fields split the query before raising: {peak} bytes"

    def test_parse_qs_groups_repeated_keys(self) -> None:
        query = "name=Alice&city=NYC&city=LA"

        assert urllib.parse.parse_qs(query) == {"name": ["Alice"], "city": ["NYC", "LA"]}
        assert urllib.parse.parse_qsl(query) == [
            ("name", "Alice"),
            ("city", "NYC"),
            ("city", "LA"),
        ]

    def test_only_the_separator_divides_fields(self) -> None:
        assert urllib.parse.parse_qsl("a=1;b=2") == [("a", "1;b=2")]
        assert urllib.parse.parse_qsl("a=1;b=2", separator=";") == [("a", "1"), ("b", "2")]

    def test_doseq_makes_each_item_a_field(self) -> None:
        assert urllib.parse.urlencode({"city": ["NYC", "LA"]}, doseq=True) == "city=NYC&city=LA"
        assert "%5B" in urllib.parse.urlencode({"city": ["NYC", "LA"]})


class TestResultTypesAreNamedTuples:
    """The six result types: fixed fields, O(1) access."""

    def test_the_text_and_bytes_shapes_match(self) -> None:
        text = urllib.parse.urlsplit("https://example.com/p?q=1#f")
        raw = urllib.parse.urlsplit(b"https://example.com/p?q=1#f")

        assert isinstance(text, urllib.parse.SplitResult)
        assert isinstance(raw, urllib.parse.SplitResultBytes)
        assert isinstance(text, tuple) and len(text) == len(raw) == 5
        assert text.encode() == raw and raw.decode() == text

    def test_parse_results_carry_the_params_field(self) -> None:
        assert isinstance(urllib.parse.urlparse("https://h/p"), urllib.parse.ParseResult)
        assert len(urllib.parse.urlparse("https://h/p")) == 6
        assert isinstance(urllib.parse.urlparse(b"https://h/"), urllib.parse.ParseResultBytes)

    def test_defrag_results_hold_two_fields(self) -> None:
        result = urllib.parse.urldefrag("https://example.com/p#f")

        assert isinstance(result, urllib.parse.DefragResult)
        assert tuple(result) == ("https://example.com/p", "f")
        assert isinstance(urllib.parse.urldefrag(b"https://x/#f"), urllib.parse.DefragResultBytes)


@pytest.fixture
def big_file_url(tmp_path: pathlib.Path) -> str:
    path = tmp_path / "big.bin"
    path.write_bytes(b"x" * (4 * 1024 * 1024))
    url = "file:" + urllib.request.pathname2url(str(path))
    urllib.request.urlopen(url).close()  # warm the handler machinery
    return url


class TestOpeningDoesNotReadTheBody:
    """`urlopen` returns after the headers; `data:` decodes its whole payload."""

    BODY_SIZE = 4 * 1024 * 1024

    def test_opening_holds_little_and_reading_holds_it_all(self, big_file_url: str) -> None:
        open_peak = peak_bytes(lambda: urllib.request.urlopen(big_file_url).close())
        with urllib.request.urlopen(big_file_url) as response:
            read_peak = peak_bytes(response.read)

        assert open_peak < 512_000, f"urlopen buffered {open_peak} bytes"
        assert read_peak > self.BODY_SIZE * 0.9, f"read() peaked at only {read_peak} bytes"

    def test_read_with_a_size_holds_only_that_much(self, big_file_url: str) -> None:
        with urllib.request.urlopen(big_file_url) as response:
            peak = peak_bytes(partial(response.read, 1024))

        assert peak < 64_000, f"read(1024) peaked at {peak} bytes"

    @pytest.mark.parametrize("line_length", [16, 4 * 1024 * 1024])
    def test_a_line_is_held_whole(self, tmp_path: pathlib.Path, line_length: int) -> None:
        path = tmp_path / "lines.txt"
        line = b"x" * (line_length - 1) + b"\n"
        path.write_bytes(line * (self.BODY_SIZE // line_length))
        url = "file:" + urllib.request.pathname2url(str(path))

        with urllib.request.urlopen(url) as response:
            lines = iter(response)
            peak = peak_bytes(partial(next, lines))

        if line_length == 16:
            assert peak < 64_000, f"one short line peaked at {peak} bytes"
        else:
            assert peak > self.BODY_SIZE * 0.9, f"a 4 MB line peaked at only {peak} bytes"

    def test_metadata_arrives_before_the_body(self, big_file_url: str) -> None:
        with urllib.request.urlopen(big_file_url) as response:
            assert int(response.headers["Content-Length"]) == self.BODY_SIZE
            assert response.headers["Content-type"] is not None

    @pytest.mark.parametrize("encoding", ["percent", "base64"])
    def test_data_urls_are_decoded_while_opening(self, encoding: str) -> None:
        urllib.request.urlopen("data:,warm").close()
        peaks = []
        for size in (SMALL, LARGE):
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

        assert peaks[1] > 20 * peaks[0], f"opening must decode the payload: {peaks}"


class TestUrlretrieveCopiesInBlocks:
    """`urlretrieve` | O(n + h + b) | O(n); `urlcleanup` | O(k)."""

    def test_copying_a_large_file_holds_one_block(
        self, big_file_url: str, tmp_path: pathlib.Path
    ) -> None:
        target = tmp_path / "copy.bin"
        calls: list[tuple[int, int, int]] = []

        def hook(*call: int) -> None:
            calls.append(call)  # type: ignore[arg-type]

        peak = peak_bytes(partial(urllib.request.urlretrieve, big_file_url, str(target), hook))

        assert target.stat().st_size == 4 * 1024 * 1024
        assert peak < 512_000, f"urlretrieve held {peak} bytes"
        assert len(calls) == 513, "one reporthook call per 8 KiB block, plus one before"
        assert {block_size for _, block_size, _ in calls} == {8192}

    def test_a_file_url_without_a_filename_is_not_copied(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "source.txt"
        source.write_text("body")
        monkeypatch.setattr(urllib.request, "_url_tempfiles", [])

        local, message = urllib.request.urlretrieve(
            "file:" + urllib.request.pathname2url(str(source))
        )

        assert os.path.samefile(local, source)
        assert urllib.request._url_tempfiles == []  # type: ignore[attr-defined]
        assert message["Content-Length"] == "4"

    @pytest.mark.parametrize("count", [3, 30])
    def test_urlcleanup_removes_each_temporary_file(
        self, count: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(urllib.request, "_url_tempfiles", [])
        created = [urllib.request.urlretrieve("data:,body")[0] for _ in range(count)]
        assert all(os.path.exists(name) for name in created)
        unlinked: list[str] = []
        real_unlink = os.unlink

        def unlink(path: Any) -> None:
            unlinked.append(path)
            real_unlink(path)

        monkeypatch.setattr(os, "unlink", unlink)
        urllib.request.urlcleanup()

        assert unlinked == created
        assert not any(os.path.exists(name) for name in created)

    def test_urlcleanup_uninstalls_the_opener(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(urllib.request, "_opener", None)
        urllib.request.install_opener(urllib.request.build_opener())
        assert urllib.request._opener is not None  # type: ignore[attr-defined]

        urllib.request.urlcleanup()

        assert urllib.request._opener is None  # type: ignore[attr-defined]

    def test_a_short_body_raises_content_too_short(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        peer = Peer(lambda req: (200, headers(Content_Length="10"), b"four"))
        monkeypatch.setattr(urllib.request, "_opener", None)
        urllib.request.install_opener(peer_opener(peer))
        target = tmp_path / "short.bin"

        with pytest.raises(urllib.error.ContentTooShortError) as caught:
            urllib.request.urlretrieve("http://peer/file", str(target))

        filename, message = caught.value.content
        assert filename == str(target)
        assert message["Content-Length"] == "10"


class TestRequestSplitsItsUrlOnce:
    """`Request(url, ...)` and its accessors."""

    def test_the_parts_exist_before_anything_is_sent(self) -> None:
        request = urllib.request.Request("https://example.com/path?q=1")

        assert (request.type, request.host, request.selector) == (
            "https",
            "example.com",
            "/path?q=1",
        )
        assert request.origin_req_host == "example.com"
        assert request.unverifiable is False
        assert urllib.request.Request("http://h/", method="PUT").method == "PUT"

    def test_get_method_follows_data_unless_told(self) -> None:
        assert urllib.request.Request("http://h/", data=b"x").get_method() == "POST"
        assert urllib.request.Request("http://h/").get_method() == "GET"
        assert urllib.request.Request("http://h/", data=b"x", method="PUT").get_method() == "PUT"

    def test_keys_are_stored_capitalized_and_looked_up_exactly(self) -> None:
        request = urllib.request.Request("http://h/", headers={"User-Agent": "bot"})
        request.add_unredirected_header("X-Custom-Header", "1")

        assert request.has_header("User-agent")
        assert not request.has_header("User-Agent")
        assert request.get_header("X-custom-header") == "1"
        assert request.get_header("X-Custom-Header", "absent") == "absent"

        request.remove_header("User-agent")
        assert not request.has_header("User-agent")

    def test_header_items_is_a_new_list_of_both_sets(self) -> None:
        request = urllib.request.Request("http://h/", headers={"A": "1", "B": "2"})
        request.add_unredirected_header("C", "3")

        items = request.header_items()

        assert sorted(items) == [("A", "1"), ("B", "2"), ("C", "3")]
        assert request.header_items() is not items

    def test_new_data_drops_the_old_content_length(self) -> None:
        request = urllib.request.Request("http://h/", data=b"abc")
        request.add_header("Content-length", "3")

        request.data = b"longer body"

        assert not request.has_header("Content-length")

    def test_full_url_rejoins_the_fragment_and_resplits_on_assignment(self) -> None:
        request = urllib.request.Request("http://h/p#frag")

        assert request.selector == "/p"
        assert request.full_url == request.get_full_url() == "http://h/p#frag"

        request.full_url = "https://other/q"
        assert (request.type, request.host, request.selector) == ("https", "other", "/q")

    def test_set_proxy_redirects_the_connection(self) -> None:
        request = urllib.request.Request("http://example.com/p#frag")

        request.set_proxy("proxy:3128", "http")

        assert request.host == "proxy:3128"
        assert request.selector == "http://example.com/p#frag"


class TestOpenerDispatch:
    """`build_opener` | O(h²) worst; `add_handler` | O(h); `open` and `error`
    walk the handlers registered for them."""

    def test_build_opener_includes_the_defaults(self) -> None:
        extra = urllib.request.HTTPCookieProcessor()
        opener = urllib.request.build_opener(extra)

        classes = {type(handler).__name__ for handler in opener.handlers}  # type: ignore[attr-defined]
        assert {"HTTPHandler", "FileHandler", "DataHandler", "UnknownHandler"} <= classes
        assert extra in opener.handlers  # type: ignore[attr-defined]

    @pytest.mark.parametrize("order", ["equal", "ascending", "descending"])
    def test_registration_displaces_entries_only_for_falling_priorities(
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
            assert [h.handler_order for h in registered] == sorted(priorities)
            if order == "descending":
                assert shifted == size * (size - 1), (size, shifted)
            else:
                assert shifted == 0, (order, size, shifted)

        assert 18 < counts[1] / counts[0] < 35, f"expected h log h comparisons: {counts}"

    @pytest.mark.parametrize("count", [10, 100])
    def test_open_runs_every_request_processor_once(self, count: int) -> None:
        calls: list[int] = []

        class Processor(urllib.request.BaseHandler):
            def __init__(self, index: int) -> None:
                self.index = index

            def http_request(self, req: Any) -> Any:
                calls.append(self.index)
                return req

        peer = Peer(lambda req: (200, headers(), b""))
        opener = peer_opener(peer, *(Processor(index) for index in range(count)))

        opener.open("http://peer/")

        assert sorted(calls) == list(range(count))
        assert len(peer.requests) == 1

    @pytest.mark.parametrize("count", [10, 100])
    def test_error_tries_each_code_handler_then_the_default(self, count: int) -> None:
        tried: list[int] = []

        class Declines(urllib.request.BaseHandler):
            def __init__(self, index: int) -> None:
                self.index = index

            def http_error_418(self, *args: Any) -> None:
                tried.append(self.index)

        peer = Peer(lambda req: (418, headers(), b""))
        opener = peer_opener(peer, *(Declines(index) for index in range(count)))

        with pytest.raises(urllib.error.HTTPError) as caught:
            opener.open("http://peer/")

        assert caught.value.code == 418
        assert sorted(tried) == list(range(count))

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

    def test_an_empty_director_has_no_handlers(self) -> None:
        assert urllib.request.OpenerDirector().handlers == []  # type: ignore[attr-defined]


class TestHandlerHooks:
    """The protocol, processing and base handler rows."""

    def test_add_parent_and_close(self) -> None:
        handler = urllib.request.BaseHandler()
        director = urllib.request.OpenerDirector()

        handler.add_parent(director)

        assert handler.parent is director  # type: ignore[attr-defined]
        assert handler.close() is None

    def test_an_unknown_scheme_raises_url_error(self) -> None:
        opener = urllib.request.build_opener()

        with pytest.raises(urllib.error.URLError, match="unknown url type"):
            opener.open("nosuchscheme://x/")

    def test_the_error_processor_passes_2xx_through(self) -> None:
        processor = urllib.request.HTTPErrorProcessor()
        response: Any = urllib.response.addinfourl(io.BytesIO(b""), headers(), "http://h/", 204)
        response.msg = "No Content"

        assert processor.http_response(urllib.request.Request("http://h/"), response) is response
        assert processor.https_response(urllib.request.Request("https://h/"), response) is response

    def test_the_default_error_handler_raises_http_error(self) -> None:
        handler = urllib.request.HTTPDefaultErrorHandler()

        with pytest.raises(urllib.error.HTTPError) as caught:
            handler.http_error_default(
                urllib.request.Request("http://h/"), io.BytesIO(), 500, "boom", headers()
            )

        assert caught.value.code == 500

    def test_cache_ftp_settings_are_stored(self) -> None:
        handler = urllib.request.CacheFTPHandler()

        handler.setTimeout(5)
        handler.setMaxConns(2)

        assert (handler.delay, handler.max_conns) == (5, 2)  # type: ignore[attr-defined]


class TestRoundTrips:
    """Redirects and authentication challenges repeat the request; prior
    authentication saves the repeat. Driven through the in-process peer."""

    def test_a_chain_stops_at_the_eleventh_different_url(self) -> None:
        peer = Peer(lambda req: (302, headers(Location=f"http://peer/{len(peer.requests)}"), b""))

        with pytest.raises(urllib.error.HTTPError) as caught:
            peer_opener(peer).open("http://peer/start")

        assert caught.value.code == 302
        assert len(peer.requests) == 11

    def test_a_loop_stops_at_the_fifth_visit_to_one_url(self) -> None:
        peer = Peer(lambda req: (302, headers(Location="http://peer/same"), b""))

        with pytest.raises(urllib.error.HTTPError):
            peer_opener(peer).open("http://peer/start")

        assert len(peer.requests) == 5

    def test_a_cycle_counts_visits_per_url_not_redirects(self) -> None:
        peer = Peer(
            lambda req: (302, headers(Location=f"http://peer/{len(peer.requests) % 3}"), b"")
        )

        with pytest.raises(urllib.error.HTTPError):
            peer_opener(peer).open("http://peer/start")

        assert len(peer.requests) == 13, "12 redirects: three URLs, four visits each"

    def test_each_redirect_body_is_read_before_the_next_request(self) -> None:
        streams: list[Any] = []

        class Recording(Peer):
            def http_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
                response = super().http_open(req)
                streams.append(response.fp)
                return response

        seen_by_next: list[tuple[int, bool]] = []

        def route(req: urllib.request.Request) -> tuple[int, Any, bytes]:
            if req.full_url.endswith("/start"):
                return 302, headers(Location="http://peer/next"), b"x" * 1_000_000
            seen_by_next.append((streams[0].raw.offset, streams[0].closed))
            return 200, headers(), b"final"

        response = peer_opener(Recording(route)).open("http://peer/start")

        assert seen_by_next == [(1_000_000, True)], (
            "the redirect body was not read and closed first"
        )
        assert streams[1].raw.offset == 0, "the final body was read before open() returned"
        assert response.read() == b"final"

    def test_308_is_followed_from_311(self) -> None:
        def route(req: urllib.request.Request) -> tuple[int, Any, bytes]:
            if req.full_url.endswith("/start"):
                return 308, headers(Location="http://peer/next"), b""
            return 200, headers(), b"done"

        peer = Peer(route)
        if sys.version_info >= (3, 11):
            assert peer_opener(peer).open("http://peer/start").read() == b"done"
            assert len(peer.requests) == 2
        else:
            with pytest.raises(urllib.error.HTTPError):
                peer_opener(peer).open("http://peer/start")
            assert len(peer.requests) == 1

    def test_redirect_request_drops_the_body_and_its_headers(self) -> None:
        request = urllib.request.Request(
            "http://peer/",
            data=b"abc",
            headers={
                "Content-Type": "text/plain",
                "Content-Length": "3",
                "Content-Encoding": "gzip",
                "X-Keep": "1",
            },
        )

        follow = urllib.request.HTTPRedirectHandler().redirect_request(
            request, io.BytesIO(), 302, "Found", headers(), "http://peer/new"
        )

        assert follow is not None
        assert follow.full_url == "http://peer/new"
        assert sorted(follow.header_items()) == [("Content-encoding", "gzip"), ("X-keep", "1")]
        assert follow.data is None

    @staticmethod
    def _challenge(scheme: str) -> Callable[[urllib.request.Request], tuple[int, Any, bytes]]:
        challenge = {
            "Basic": 'Basic realm="r"',
            "Digest": 'Digest realm="r", nonce="abc", qop="auth"',
        }[scheme]

        def route(req: urllib.request.Request) -> tuple[int, Any, bytes]:
            if req.has_header("Authorization") or req.get_header("Authorization"):
                return 200, headers(), b"ok"
            return 401, headers(WWW_Authenticate=challenge), b""

        return route

    @pytest.mark.parametrize("scheme", ["Basic", "Digest"])
    def test_a_challenge_costs_one_extra_request(self, scheme: str) -> None:
        manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(None, "http://peer/", "alice", "secret")
        handler = (
            urllib.request.HTTPBasicAuthHandler(manager)
            if scheme == "Basic"
            else urllib.request.HTTPDigestAuthHandler(manager)
        )
        peer = Peer(self._challenge(scheme))

        response = peer_opener(peer, handler).open("http://peer/private")

        assert response.status == 200
        assert len(peer.requests) == 2
        assert peer.requests[1].get_header("Authorization", "").startswith(scheme)

    @pytest.mark.parametrize("authenticated", [False, True])
    def test_prior_auth_sends_the_credentials_first(self, authenticated: bool) -> None:
        manager = urllib.request.HTTPPasswordMgrWithPriorAuth()
        manager.add_password(
            None, "http://peer/", "alice", "secret", is_authenticated=authenticated
        )
        peer = Peer(self._challenge("Basic"))

        peer_opener(peer, urllib.request.HTTPBasicAuthHandler(manager)).open("http://peer/x")

        assert len(peer.requests) == (1 if authenticated else 2)

    def test_prior_auth_is_asked_on_every_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        manager = urllib.request.HTTPPasswordMgrWithPriorAuth()
        asked: list[str] = []
        original = manager.is_authenticated
        monkeypatch.setattr(
            manager, "is_authenticated", lambda uri: asked.append(uri) or original(uri)
        )
        opener = peer_opener(
            Peer(lambda req: (200, headers(), b"")), urllib.request.HTTPBasicAuthHandler(manager)
        )

        for index in range(3):
            opener.open(f"http://peer/{index}")

        assert asked == [f"http://peer/{index}" for index in range(3)]

    def test_the_proxy_handlers_answer_407(self) -> None:
        assert hasattr(urllib.request.ProxyBasicAuthHandler, "http_error_407")
        assert hasattr(urllib.request.ProxyDigestAuthHandler, "http_error_407")
        assert issubclass(
            urllib.request.ProxyBasicAuthHandler, urllib.request.AbstractBasicAuthHandler
        )
        assert issubclass(
            urllib.request.ProxyDigestAuthHandler, urllib.request.AbstractDigestAuthHandler
        )


class TestCookieProcessorChecksEveryDomain:
    """A request through `HTTPCookieProcessor` | O(c)."""

    @staticmethod
    def _jar(domains: int, checked: list[str]) -> http.cookiejar.CookieJar:
        class CountingPolicy(http.cookiejar.DefaultCookiePolicy):
            def domain_return_ok(self, domain: str, request: Any) -> bool:
                checked.append(domain)
                return super().domain_return_ok(domain, request)

        jar = http.cookiejar.CookieJar(CountingPolicy())
        for index in range(domains):
            jar.set_cookie(
                http.cookiejar.Cookie(
                    0, f"c{index}", "v", None, False, f"d{index}.example", True, False,
                    "/", True, False, None, False, None, None, {},
                )
            )  # fmt: skip
        return jar

    @pytest.mark.parametrize("domains", [10, 1000])
    def test_an_unrelated_request_checks_every_domain(self, domains: int) -> None:
        checked: list[str] = []
        processor = urllib.request.HTTPCookieProcessor(self._jar(domains, checked))

        request = processor.http_request(urllib.request.Request("http://unrelated.example/"))

        assert len(checked) == domains
        assert not request.has_header("Cookie")

    def test_the_jar_is_the_one_given(self) -> None:
        jar = http.cookiejar.CookieJar()

        assert urllib.request.HTTPCookieProcessor(jar).cookiejar is jar


class TestPasswordManagersScanTheirUris:
    """`find_user_password` and `is_authenticated` | O(u·n)."""

    @staticmethod
    def _count_suburi(monkeypatch: pytest.MonkeyPatch) -> list[int]:
        calls = [0]
        original = urllib.request.HTTPPasswordMgr.is_suburi  # type: ignore[attr-defined]

        def counting(self: Any, base: Any, test: Any) -> bool:
            calls[0] += 1
            return original(self, base, test)

        monkeypatch.setattr(urllib.request.HTTPPasswordMgr, "is_suburi", counting)
        return calls

    def test_a_miss_compares_every_stored_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each stored URI is kept with and without its default port, and a
        lookup tries both forms of `authuri`, so the count is a fixed multiple
        of u; the multiple is asserted to be the same at 10 and 1,000."""
        calls = self._count_suburi(monkeypatch)
        per_uri = []
        for stored in (10, 1000):
            manager = urllib.request.HTTPPasswordMgr()
            for index in range(stored):
                manager.add_password("realm", f"https://example.com/area{index}/", "u", "p")
            calls[0] = 0

            assert manager.find_user_password("realm", "https://example.com/x") == (None, None)
            per_uri.append(calls[0] / stored)

        assert per_uri[0] == per_uri[1] >= 1, f"is_suburi calls per stored URI: {per_uri}"

    def test_is_authenticated_compares_every_marked_uri(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._count_suburi(monkeypatch)
        per_uri = []
        for stored in (10, 1000):
            manager = urllib.request.HTTPPasswordMgrWithPriorAuth()
            for index in range(stored):
                manager.update_authenticated(f"https://example.com/area{index}/", True)
            calls[0] = 0

            assert not manager.is_authenticated("https://example.com/other")
            per_uri.append(calls[0] / stored)

        assert per_uri[0] == per_uri[1] >= 1, f"is_suburi calls per marked URI: {per_uri}"

    def test_a_lookup_matches_by_path_prefix(self) -> None:
        manager = urllib.request.HTTPPasswordMgr()
        manager.add_password("realm", ["https://a.example/docs/", "https://b.example/"], "u", "p")

        assert manager.find_user_password("realm", "https://a.example/docs/x") == ("u", "p")
        assert manager.find_user_password("realm", "https://b.example/y") == ("u", "p")
        assert manager.find_user_password("realm", "https://a.example/other") == (None, None)

    def test_the_default_realm_managers_fall_back_to_none(self) -> None:
        for manager in (
            urllib.request.HTTPPasswordMgrWithDefaultRealm(),
            urllib.request.HTTPPasswordMgrWithPriorAuth(),
        ):
            manager.add_password(None, "https://example.com/", "u", "p")

            assert manager.find_user_password("any realm", "https://example.com/x") == ("u", "p")


class TestProxies:
    """`ProxyHandler` | O(p), or O(e) through `getproxies()` | O(e)."""

    def test_one_open_method_per_scheme(self) -> None:
        proxies = {f"scheme{index}": f"http://p:{index}" for index in range(50)}

        handler = urllib.request.ProxyHandler(proxies)

        assert handler.proxies == proxies  # type: ignore[attr-defined]
        assert all(hasattr(handler, f"scheme{index}_open") for index in range(50))

    def test_no_mapping_reads_getproxies_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[None] = []

        def fake() -> dict[str, str]:
            calls.append(None)
            return {"http": "http://p:1"}

        monkeypatch.setattr(urllib.request, "getproxies", fake)

        handler = urllib.request.ProxyHandler()

        assert len(calls) == 1
        assert hasattr(handler, "http_open")

    @pytest.mark.skipif(
        sys.platform in ("darwin", "win32"), reason="system proxy settings are consulted there"
    )
    def test_getproxies_takes_items_in_proportion_to_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        taken = [0]

        class CountingEnviron(dict[str, str]):
            """Counts the names handed out, whichever way the scan asks."""

            def __iter__(self) -> Iterator[str]:
                for name in super().__iter__():
                    taken[0] += 1
                    yield name

            def items(self) -> Any:
                for item in super().items():
                    taken[0] += 1
                    yield item

            def keys(self) -> Any:
                return list(self.__iter__())

        counts = []
        for size in (10, 1000):
            environ = CountingEnviron({f"VAR{index}": "x" for index in range(size)})
            environ["http_proxy"] = "http://p:1"
            monkeypatch.setattr(os, "environ", environ)
            taken[0] = 0

            assert urllib.request.getproxies() == {"http": "http://p:1"}
            counts.append(taken[0] / (size + 1))

        assert counts[0] == counts[1] and counts[0] >= 1, f"names taken per variable: {counts}"


class TestErrorsCarryTheirResponse:
    """`HTTPError` is a response as well as an exception."""

    def test_an_http_error_exposes_the_response(self) -> None:
        message = headers(Content_Type="text/plain")
        body = io.BytesIO(b"missing")
        error = urllib.error.HTTPError("https://example.com/x", 404, "Not Found", message, body)

        assert (error.code, error.reason, error.url) == (404, "Not Found", "https://example.com/x")
        assert error.headers is message
        assert error.fp is body
        assert error.read() == b"missing"

    def test_the_error_hierarchy(self) -> None:
        assert issubclass(urllib.error.HTTPError, urllib.error.URLError)
        assert issubclass(urllib.error.URLError, OSError)
        assert issubclass(urllib.error.ContentTooShortError, urllib.error.URLError)

    def test_the_other_errors_keep_what_they_were_given(self) -> None:
        reason = OSError("refused")
        content = ("partial.txt", headers())

        assert urllib.error.URLError(reason).reason is reason
        assert urllib.error.ContentTooShortError("short", content).content is content


class TestResponseWrappersAddNoBuffering:
    """`urllib.response.*`: attributes over an already-open stream."""

    def test_addinfourl_and_its_older_spellings(self) -> None:
        stream = io.BytesIO(b"body")
        message = headers(Content_Type="text/plain")
        wrapped = urllib.response.addinfourl(stream, message, "https://example.com/x", 200)

        assert wrapped.fp is stream
        assert (wrapped.url, wrapped.status, wrapped.headers) == (
            "https://example.com/x",
            200,
            message,
        )
        assert (wrapped.geturl(), wrapped.getcode(), wrapped.info(), wrapped.code) == (
            wrapped.url,
            wrapped.status,
            wrapped.headers,
            wrapped.status,
        )
        assert wrapped.read() == b"body"

    def test_the_bases_wrap_the_same_stream(self) -> None:
        stream = io.BytesIO(b"body")

        assert urllib.response.addbase(stream).fp is stream
        assert urllib.response.addinfo(io.BytesIO(b"x"), headers()).info() is not None

    def test_addclosehook_runs_one_callback(self) -> None:
        calls: list[str] = []
        hooked = urllib.response.addclosehook(io.BytesIO(b"x"), calls.append, "closed")

        hooked.close()
        hooked.close()

        assert calls == ["closed"]


class TestRobotFileParser:
    """`parse` | O(s); `can_fetch` | O(g + n·(r + 1)); `crawl_delay`,
    `request_rate` | O(g)."""

    @staticmethod
    def _parser(lines: list[str]) -> urllib.robotparser.RobotFileParser:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(lines)
        return parser

    def test_nothing_is_allowed_before_a_parse(self) -> None:
        parser = urllib.robotparser.RobotFileParser("https://example.com/robots.txt")

        assert parser.can_fetch("bot", "https://example.com/") is False
        assert parser.crawl_delay("bot") is None
        assert parser.request_rate("bot") is None
        assert parser.mtime() == 0

    def test_modified_records_the_time(self) -> None:
        parser = urllib.robotparser.RobotFileParser()

        before = time.time()
        parser.modified()

        assert parser.mtime() >= before

    def test_read_fetches_and_parses(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "robots.txt"
        path.write_text("User-agent: *\nDisallow: /private\n")
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url("file:" + urllib.request.pathname2url(str(path)))

        parser.read()

        assert parser.can_fetch("bot", "https://example.com/public")
        assert not parser.can_fetch("bot", "https://example.com/private")

    @pytest.mark.parametrize(("code", "allowed"), [(401, False), (403, False), (404, True)])
    def test_read_turns_an_error_status_into_a_verdict(
        self, monkeypatch: pytest.MonkeyPatch, code: int, allowed: bool
    ) -> None:
        peer = Peer(lambda req: (code, headers(), b""))
        monkeypatch.setattr(urllib.request, "_opener", None)
        urllib.request.install_opener(peer_opener(peer))
        parser = urllib.robotparser.RobotFileParser("http://peer/robots.txt")

        parser.read()

        assert parser.can_fetch("bot", "http://peer/page") is allowed
        assert len(peer.requests) == 1

    def test_site_maps_returns_the_stored_list(self) -> None:
        parser = self._parser(["Sitemap: https://example.com/a.xml", "User-agent: *"])
        empty = self._parser(["User-agent: *", "Disallow:"])

        assert parser.site_maps() == ["https://example.com/a.xml"]
        assert parser.site_maps() is parser.site_maps()
        assert empty.site_maps() is None

    def test_delay_and_rate_come_from_the_group(self) -> None:
        parser = self._parser(
            ["User-agent: bot", "Crawl-delay: 5", "Request-rate: 1/10", "Disallow:"]
        )

        assert parser.crawl_delay("bot") == 5
        rate = parser.request_rate("bot")
        assert rate is not None
        assert (rate.requests, rate.seconds) == (1, 10)
        assert parser.crawl_delay("other") is None

    @pytest.mark.parametrize("method", ["can_fetch", "crawl_delay", "request_rate"])
    def test_an_unmatched_agent_scans_every_group(
        self, monkeypatch: pytest.MonkeyPatch, method: str
    ) -> None:
        entry_type = urllib.robotparser.Entry  # type: ignore[attr-defined]
        original = entry_type.applies_to
        calls = [0]

        def counting(entry: Any, agent: Any) -> Any:
            calls[0] += 1
            return original(entry, agent)

        monkeypatch.setattr(entry_type, "applies_to", counting)
        for groups in (10, 1000):
            lines: list[str] = []
            for index in range(groups):
                lines += [f"User-agent: bot{index}x", "Disallow: /"]
            parser = self._parser(lines)
            calls[0] = 0

            args = ("nomatch", "https://example.com/") if method == "can_fetch" else ("nomatch",)
            getattr(parser, method)(*args)

            assert calls[0] == groups, (method, groups, calls[0])

    @pytest.mark.parametrize("agents", [10, 100])
    def test_a_group_naming_many_agents_is_scanned_once_per_agent_under_rfc_9309(
        self, monkeypatch: pytest.MonkeyPatch, agents: int
    ) -> None:
        entry_type = urllib.robotparser.Entry  # type: ignore[attr-defined]
        original = entry_type.applies_to
        calls = [0]

        def counting(entry: Any, agent: Any) -> Any:
            calls[0] += 1
            return original(entry, agent)

        monkeypatch.setattr(entry_type, "applies_to", counting)
        parser = self._parser(
            [f"User-agent: bot{index}x" for index in range(agents)] + ["Disallow: /"]
        )

        parser.can_fetch("nomatch", "https://example.com/")

        assert calls[0] == (agents if ROBOT_RFC_9309 else 1)

    def test_a_named_agent_wins_over_the_wildcard(self) -> None:
        parser = self._parser(
            ["User-agent: *", "Disallow: /", "User-agent: goodbot", "Disallow: /admin"]
        )

        assert parser.can_fetch("goodbot", "http://example.com/x") is True
        assert parser.can_fetch("otherbot", "http://example.com/x") is False

    def test_rule_count_controls_the_prefix_checks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rule_type = urllib.robotparser.RuleLine  # type: ignore[attr-defined]
        original = rule_type.applies_to
        checked = [0]

        def record(rule: Any, path: str) -> Any:
            checked[0] += 1
            return original(rule, path)

        monkeypatch.setattr(rule_type, "applies_to", record)
        for size in (10, 1000):
            parser = self._parser(["User-agent: *"] + ["Disallow: /blocked"] * size)
            assert str(parser).count("Disallow: /blocked") == size
            checked[0] = 0
            assert parser.can_fetch("bot", "https://example.com/allowed") is True
            assert checked[0] == size
            checked[0] = 0
            assert parser.can_fetch("bot", "https://example.com/blocked") is False
            assert checked[0] == (size if ROBOT_RFC_9309 else 1)

    def test_parse_and_lookup_allocate_with_text_length(self) -> None:
        parse_peaks, lookup_peaks = [], []
        try:
            for size in (SMALL, LARGE):
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
                assert peaks[1] > 20 * peaks[0], f"one rule still allocates with text: {peaks}"
        finally:
            clear_parse_cache()

    def test_wildcards_and_anchors_follow_the_release(self) -> None:
        parser = self._parser(["User-agent: *", "Disallow: /a*/secret", "Disallow: /end$"])

        assert parser.can_fetch("bot", "https://example.com/ax/secret") is not ROBOT_RFC_9309
        assert parser.can_fetch("bot", "https://example.com/a*/secret") is False
        assert parser.can_fetch("bot", "https://example.com/end") is not ROBOT_RFC_9309
        assert parser.can_fetch("bot", "https://example.com/end$") is ROBOT_RFC_9309
        assert parser.can_fetch("bot", "https://example.com/end/more") is True
        assert parser.can_fetch("bot", "https://example.com/other") is True

    @pytest.mark.parametrize("agent", ["bot", "*"])
    def test_repeated_agent_groups_follow_the_release(self, agent: str) -> None:
        parser = self._parser(
            [f"User-agent: {agent}", "Disallow: /one", f"User-agent: {agent}", "Disallow: /two"]
        )

        assert parser.can_fetch("bot", "https://example.com/one") is False
        assert parser.can_fetch("bot", "https://example.com/two") is not ROBOT_RFC_9309
        assert parser.can_fetch("bot", "https://example.com/other") is True

    @pytest.mark.parametrize(
        ("rules", "rfc_allows", "legacy_allows"),
        [
            (["Disallow: /", "Allow: /public"], True, False),
            (["Disallow: /public", "Allow: /public"], True, False),
            (["Allow: /pub", "Disallow: /public"], False, True),
        ],
    )
    def test_longest_match_and_allow_ties_follow_the_release(
        self, rules: list[str], rfc_allows: bool, legacy_allows: bool
    ) -> None:
        """Length decides before allowance, so a longer `Disallow` has to win.

        The first two rows are also what "Allow always wins" would produce.
        The third is what separates longest-match from that reading, and from
        the first-applying-rule behaviour of earlier releases, which it
        inverts.
        """
        parser = self._parser(["User-agent: *", *rules])
        expected = rfc_allows if ROBOT_RFC_9309 else legacy_allows

        assert parser.can_fetch("bot", "https://example.com/public") is expected

    def test_repeated_groups_are_merged_quadratically(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One fixed-length agent and one rule per group isolate merge work.

        The RFC implementation copies 2 + 3 + ... + g references, and one
        group holding the same rules copies none.
        """
        copied = [0]
        if ROBOT_RFC_9309:
            original = urllib.robotparser.merge_entries  # type: ignore[attr-defined]

            class CountingRules(list[Any]):
                def __add__(self, other: list[Any]) -> list[Any]:  # type: ignore[override]
                    copied[0] += len(self) + len(other)
                    return super().__add__(other)

            def merge(first: Any, second: Any) -> Any:
                first.rulelines = CountingRules(first.rulelines)
                return original(first, second)

            monkeypatch.setattr(urllib.robotparser, "merge_entries", merge)

        for size in (10, 1000):
            copied[0] = 0
            parser = self._parser(["User-agent: bot", "Disallow: /blocked"] * size)
            assert copied[0] == (size * (size + 1) // 2 - 1 if ROBOT_RFC_9309 else 0)

            copied[0] = 0
            combined = self._parser(["User-agent: bot"] + ["Disallow: /blocked"] * size)
            assert copied[0] == 0
            for path in ("/blocked", "/allowed"):
                url = "https://example.com" + path
                assert combined.can_fetch("bot", url) == parser.can_fetch("bot", url)

    def test_wildcard_rules_are_compiled_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Counts public `re.compile` requests, which may hit the regex
        cache; `re.sub` normalising paths uses its own internal requests."""
        if not ROBOT_RFC_9309:
            parser = self._parser(["User-agent: bot", "Disallow: /a*/secret"])
            rule = parser.entries[0].rulelines[0]  # type: ignore[attr-defined]
            assert not hasattr(rule, "matcher")
            return

        compiles = [0]
        original = re.compile

        def counting(*args: Any, **kwargs: Any) -> Any:
            compiles[0] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(re, "compile", counting)

        literal = self._parser(["User-agent: bot", "Disallow: /plain/secret"])
        assert compiles[0] == 0

        parser = self._parser(["User-agent: bot", "Disallow: /a*/secret", "Disallow: /b*/x"])
        assert compiles[0] == 2

        for _ in range(3):
            assert parser.can_fetch("bot", "https://example.com/ax/secret") is False
            assert literal.can_fetch("bot", "https://example.com/plain/secret") is False
        assert compiles[0] == 2


@pytest.mark.skipif(not HAS_URLOPENER, reason="URLopener and FancyURLopener were removed in 3.14")
class TestLegacyOpeners:
    """`URLopener` and `FancyURLopener`, Python 3.10 to 3.13."""

    @staticmethod
    def _opener(kind: str = "URLopener", **kwargs: Any) -> Any:
        with pytest.warns(DeprecationWarning):
            return getattr(urllib.request, kind)(**kwargs)

    def test_construction_reads_getproxies_without_a_mapping(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[None] = []
        monkeypatch.setattr(urllib.request, "getproxies", lambda: calls.append(None) or {})

        self._opener()
        self._opener(proxies={})

        assert len(calls) == 1

    def test_retrieve_returns_a_local_file_itself(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("body")

        local, _ = self._opener(proxies={}).retrieve(
            "file:" + urllib.request.pathname2url(str(source))
        )

        assert os.path.samefile(local, source)

    def test_open_returns_a_stream_and_open_unknown_raises(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "source.txt"
        source.write_text("body")
        opener = self._opener(proxies={})

        with opener.open("file:" + urllib.request.pathname2url(str(source))) as response:
            assert isinstance(response.fp, io.BufferedReader)
            assert response.fp.tell() == 0
            assert response.read() == b"body"
        with pytest.raises(OSError):
            opener.open_unknown("nosuchscheme://x/")
        assert opener.version.startswith("Python-urllib/")

    def test_prompt_user_passwd_asks_the_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(builtins, "input", lambda prompt: "alice")
        monkeypatch.setattr(getpass, "getpass", lambda prompt: "secret")

        opener = self._opener("FancyURLopener", proxies={})

        assert opener.prompt_user_passwd("host", "realm") == ("alice", "secret")


def test_urlopen_takes_cafile_only_before_313() -> None:
    parameters = inspect.signature(urllib.request.urlopen).parameters

    assert ("cafile" in parameters) is (sys.version_info < (3, 13))
    assert "context" in parameters


def test_the_legacy_openers_are_gone_from_314() -> None:
    for name in ("URLopener", "FancyURLopener"):
        assert hasattr(urllib.request, name) is HAS_URLOPENER


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
    """Each block runs in its own subprocess and asserts its own result; none
    needs a network, because the fetching examples use `file:` and `data:`
    URLs."""

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
        target = "assert first is second"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert first is not second", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
