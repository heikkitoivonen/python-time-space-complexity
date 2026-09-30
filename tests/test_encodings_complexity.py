"""Tests for docs/stdlib/encodings.md.

The page prices the package's own work, which is name handling: normalizing a
name, mapping it through the alias table, and importing a codec module the
first time a name reaches the search function. It also prices the three codec
modules with documented APIs of their own: `encodings.idna` (with `ToASCII`,
`ToUnicode` and `nameprep`), `encodings.utf_8_sig` and the Windows-only
`encodings.mbcs`. The other codec modules are priced by codec on the codecs
page and are not in the official API inventory. The caching rows are settled
by observation - a counting `normalize_encoding`, a counting `__import__`, the
contents of the package's cache and identity of what it returns - so they need
no tolerance, as are the IDNA rows' call sequences. Timing is used only for
growth classes, always as a ratio between input sizes or input shapes.

Measurement scope:

* `normalize_encoding()` is asserted by output on names with runs of
  punctuation, spaces, dots, mixed case, leading and trailing punctuation and
  ASCII `bytes`; non-ASCII `bytes` raise `UnicodeDecodeError`. Its traced peak
  grows between 50x and 200x from a 10,000- to a 1,000,000-character name
  (quadratic would be 10,000x), and a timing
  test over 10,000, 100,000 and 1,000,000 characters asserts each 10x step
  costs under 30x (linear would be 10x, quadratic 100x).
* `search_function()` is observed with the package's `_cache` replaced by an
  empty dict: the first call for a name calls `normalize_encoding()` once and
  `__import__` for the codec module; a second call with the same string calls
  neither and returns the same object, and a warmed hit peaks under 1,000
  traced bytes. `latin_1` and
  `latin-1` are observed to take two cache entries and two normalizations.
  With `encodings.mac_turkish` removed from `sys.modules`, the first call
  imports a new module object. 200 distinct unknown names add 200 `None`
  entries, and a retry of one calls `__import__` no more. `search_function`
  returns `None` for `UTF-8` and `L1` and a codec for `utf-8` and `l1`.
* `codecs.lookup()` is observed, after its own cache is emptied by
  registering and unregistering a search function, to call
  `normalize_encoding()` once for `Mac-Turkish` and not again for
  `mac turkish`, returning the same object; 100 distinct unknown names such
  as `No-Such-Codec 0` each raise `LookupError` and add one entry, such as
  `no_such_codec_0`, to the package's cache. Looking one up twice more
  reaches a search function registered after the package's both times, so
  the registry cached neither failure, and adds no entry. Emptying the registry's cache leaves the package's cache as
  it was.
* `win32_code_page_search_function()` is asserted absent off Windows and,
  on Windows 3.14+, to answer `cp1252` and `cp437` and to return `None` for
  `utf-8` and `cpxyz`.
* The alias table is asserted to be a `dict` whose keys normalize to
  themselves and whose values name modules in the package, and `l1` to reach
  `latin_1` through it.
* `CodecRegistryError` is raised for a codec module, installed in
  `sys.modules`, whose `getregentry()` returns a two-tuple, and for one
  returning four non-callables (other malformed returns, such as `None`,
  are not varied and raise other exceptions); it is caught as `LookupError` and
  `SystemError`, and a second call raises again. A four-tuple of callables
  becomes a `CodecInfo` named after the module.
* Encoding and decoding are timed for UTF-8, ASCII and Latin-1 with
  `'strict'`, `'ignore'` and `'replace'`, on repeats of a 15-character
  phrase mixing ASCII, Latin-1 and CJK text at 2,000 and 2,000,000
  repeats, encoded as UTF-8 for decoding, with an undecodable `\\xff` after
  each phrase for `'ignore'` and `'replace'`. The fastest of seven batches
  of five calls is measured after warming each operation. The 1,000x input
  interval must cost under 32,000x: linear predicts 1,000x and quadratic
  1,000,000x. This wide interval allows allocation and memory-bandwidth
  differences between sizes, especially for Latin-1's fast decode path.
  Phrase composition and error density stay fixed.
* The `idna` codec is observed, with `ToASCII` and `ToUnicode` replaced by
  counting wrappers, to call neither for `Example.COM` in either direction
  (returning it unchanged) and each once per label for
  `bücher.example` and `xn--bcher-kva.example`. The ASCII fast path rejects a
  64-character label and an empty one and accepts 63 characters; `'ignore'`
  and `'replace'` raise `UnicodeError` in both directions. Encoding and
  decoding names of 100 and 10,000 `example` or `bücher` labels is timed;
  the larger must cost under 1,000x the smaller (linear would be 100x,
  quadratic 10,000x), as in every 100x comparison below.
* `ToASCII()` is observed, with `nameprep` and `punycode.punycode_encode`
  counted, to call neither for an ASCII label, which is returned without
  lowercasing and length-checked (63 accepted, 64 and empty rejected), and
  each once for `Bücher` and for a 2,000-character label that is then
  rejected as too long. `Straße`, which nameprep folds to ASCII, is
  prepared once and never punycoded. `'ü' * 63` is rejected, since its
  `xn--` form exceeds 63 octets. The `u` term is timed on 2,000-character labels: 2,000 distinct
  CJK ideographs must cost over 10x one ideograph repeated (O(m) would be
  about 1x); the growth in `m` itself is the punycode bound, timed on the
  codecs page.
* `ToUnicode()` is observed, with `punycode.punycode_decode` and `ToASCII`
  counted, to decode nothing for `b'Example'` and `'example'`, and to decode
  `xn--bcher-kva` once and round-trip it through one `ToASCII()`; a non-ASCII
  `str` raises. On 3.12+ labels of 1,025 characters (`bytes` and `str`) and
  of 1,000,004 raise `label way too long` with no nameprep and no decode, and
  a 1,024-character label reaches the decoder; before 3.12 a 2,004-character
  label reaches it. The codec decodes a 1,025-character ASCII label without
  an `xn--` prefix without calling `ToUnicode()`, so the guard is not the
  codec's. The O(m²) decode bound is the punycode one, timed on the
  codecs page, not here.
* `nameprep()` is asserted by output on `Bücher`, a soft-hyphenated
  `Straße` and `a` followed by two out-of-order combining marks, and timed
  at 1,000 and 100,000 characters on soft-hyphenated `Bücher` and on `a`
  followed by alternating U+0315 and U+0300, the run of combining marks
  that NFKC reorders; the marks case holds on releases carrying the
  CVE-2026-3276 fix only (see the unicodedata page) and is skipped on others
  by `tests/patched_python.py`.
* `utf-8-sig` is asserted by output: every whole encode writes a BOM, also
  for `''` and ahead of a leading U+FEFF; decode skips one leading BOM and
  keeps a second or a later one; the incremental encoder writes the BOM on
  the first call and again after `reset()`; the incremental decoder returns
  `''` for a BOM fed a byte at a time, then the text, treats a later BOM as
  U+FEFF, strips again after `reset()`, and returns a first byte that cannot
  start a BOM at once. Whole encode and decode, and one incremental decode
  call, are timed at 2,000 and 200,000 phrase repeats; incremental decoding
  in 61-byte chunks is timed over 100 and 10,000 chunks, after asserting the
  input holds all 10,000 and the decoder consumed them.
* `mbcs` is asserted to have the aliases `ansi` and `dbcs`; off Windows all
  three names are unknown encodings and importing `encodings.mbcs` raises
  `ImportError`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `i`, the cost of importing a codec module, is a definitional term: the
  tests show the import happens on the first call only, not what it costs.
  Charmap modules build their encoding table at import; that is inside `i`.
* That nothing evicts entries from the package's cache is read from
  Lib/encodings/__init__.py, where only `search_function()` writes `_cache`,
  and from a search of Lib for other writers; the test shows only that
  emptying the registry's cache leaves it alone.
* The `punycode` exception is priced and tested on the codecs page. Other
  codecs than UTF-8, `utf-8-sig`, ASCII, Latin-1 and `idna`, and other error
  handlers, are not timed here; `test_codecs_complexity.py` times more of them.
* `search_function('UTF-8')` returning `None` depends on imports matching
  module names by case, which is observed on Linux only.
* `win32_code_page_search_function()` is Windows-only: its test runs in the
  Windows CI job and skips everywhere else.
* `encodings.mbcs` is Windows-only (category D): its row, O(n) through the
  ANSI code page, is read from Lib/encodings/mbcs.py and
  Objects/unicodeobject.c, and its round-trip test runs in the Windows CI
  job and skips everywhere else. The audit lists it, and
  `encodings.oem`, under import errors on Linux; `encodings.oem` is not in
  the official inventory and its codec functions are priced on the codecs
  page.
* The `utf-8-sig` stream reader and writer, and the `idna` incremental and
  stream classes, are not varied here; the codecs page prices the stream and
  incremental machinery they share with every codec.
* The audit's needs-classification list for this page holds some 1,600
  runtime names that are not in the official API inventory: the generic
  members every codec module defines (`Codec`, `IncrementalEncoder`,
  `IncrementalDecoder`, `StreamReader`, `StreamWriter`, `getregentry` and
  their methods), the charmap modules' `encoding_table`, `encoding_map` and
  `decoding_map`, the multibyte modules' `codec` objects, helper functions
  such as `encodings.punycode.punycode_encode` or
  `encodings.base64_codec.base64_encode`, `encodings.idna.dots`, and
  `encodings.aliases` itself. The codecs reached through them are priced by
  codec on the codecs page; `encodings.aliases.aliases` is priced here.
"""

from __future__ import annotations

import builtins
import codecs
import encodings
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from encodings import idna, punycode
from encodings.aliases import aliases
from typing import Any

import pytest

from tests.patched_python import require_patched_normalization

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "encodings.md"
EXPECTED_BLOCKS = 5


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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


class Calls:
    """Wrap `normalize_encoding` and `__import__` so their calls are recorded."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.normalized: list[str] = []
        self.imported: list[str] = []
        original_normalize = encodings.normalize_encoding
        original_import = builtins.__import__

        def normalize(encoding: Any) -> str:
            self.normalized.append(encoding)
            return original_normalize(encoding)

        def counting_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.startswith("encodings."):
                self.imported.append(name)
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(encodings, "normalize_encoding", normalize)
        monkeypatch.setattr(builtins, "__import__", counting_import)


@pytest.fixture
def empty_cache(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace the package's search cache with an empty dict for one test."""
    cache: dict[str, Any] = {}
    monkeypatch.setattr(encodings, "_cache", cache)
    return cache


def empty_the_registry_cache() -> None:
    """`codecs.unregister()` of a registered function empties the lookup cache."""

    def nothing(name: str) -> None:
        return None

    codecs.register(nothing)
    codecs.unregister(nothing)


class TestNormalizeEncodingIsOnePass:
    """`normalize_encoding(encoding)` | O(k) | O(k): runs of characters other
    than letters, digits and `.` become one `_`, none at either end, case kept."""

    def test_runs_collapse_and_ends_are_trimmed(self) -> None:
        assert encodings.normalize_encoding("Latin -- 1") == "Latin_1"
        assert encodings.normalize_encoding("  -;#utf--8__") == "utf_8"
        assert encodings.normalize_encoding("iso8859.1") == "iso8859.1"
        assert encodings.normalize_encoding("  -;#") == ""

    def test_case_is_kept(self) -> None:
        assert encodings.normalize_encoding("UTF-8") == "UTF_8"

    def test_it_accepts_ascii_bytes_only(self) -> None:
        assert encodings.normalize_encoding(b"utf-8") == "utf_8"
        with pytest.raises(UnicodeDecodeError):
            encodings.normalize_encoding("ütf-8".encode())

    @staticmethod
    def _name(length: int) -> str:
        return ("Ab-- 1." * (length // 7 + 1))[:length]

    def test_the_peak_follows_the_name(self) -> None:
        small, large = self._name(10_000), self._name(1_000_000)

        peaks = [
            peak_bytes(lambda: encodings.normalize_encoding(small)),
            peak_bytes(lambda: encodings.normalize_encoding(large)),
        ]

        assert 50 * peaks[0] < peaks[1] < 200 * peaks[0], f"100x the name peaked at {peaks}"

    @pytest.mark.timing
    def test_time_is_linear_in_the_name(self) -> None:
        names = [self._name(length) for length in (10_000, 100_000, 1_000_000)]

        durations = [best_ns(lambda n=name: encodings.normalize_encoding(n)) for name in names]
        ratios = [durations[1] / durations[0], durations[2] / durations[1]]

        assert all(ratio < 30 for ratio in ratios), (
            f"10x steps in the name cost {ratios} ({durations} ns); quadratic would be 100x"
        )


class TestSearchFunctionCaches:
    """`search_function(encoding)` | O(k + i) first call per name, O(k) after:
    cached by the exact string, unknown names cached as `None`."""

    def test_the_first_call_normalizes_and_imports(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        calls = Calls(monkeypatch)

        info = encodings.search_function("latin_1")

        assert info is not None and info.name == "iso8859-1"
        assert calls.normalized == ["latin_1"]
        assert calls.imported == ["encodings.latin_1"]
        assert empty_cache == {"latin_1": info}

    def test_a_second_call_does_neither(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        first = encodings.search_function("latin_1")
        calls = Calls(monkeypatch)

        second = encodings.search_function("latin_1")

        assert second is first
        assert calls.normalized == [] and calls.imported == []

    @pytest.mark.serial
    def test_a_cache_hit_allocates_nothing(self, empty_cache: dict[str, Any]) -> None:
        name = "latin_1"
        first = encodings.search_function(name)
        encodings.search_function(name)  # warm

        peak = peak_bytes(lambda: encodings.search_function(name))

        assert encodings.search_function(name) is first
        assert peak < 1_000, f"a cache hit allocated {peak} bytes"

    def test_the_key_is_the_exact_string(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        calls = Calls(monkeypatch)

        encodings.search_function("latin_1")
        encodings.search_function("latin-1")

        assert set(empty_cache) == {"latin_1", "latin-1"}
        assert calls.normalized == ["latin_1", "latin-1"]

    def test_the_first_call_imports_the_module_afresh(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        old = sys.modules.get("encodings.mac_turkish")
        monkeypatch.delitem(sys.modules, "encodings.mac_turkish", raising=False)

        info = encodings.search_function("mac_turkish")

        assert info is not None and info.name == "mac-turkish"
        assert sys.modules["encodings.mac_turkish"] is not old

    def test_unknown_names_are_cached_as_none(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        names = [f"no_such_codec_{index}" for index in range(200)]

        assert all(encodings.search_function(name) is None for name in names)
        assert len(empty_cache) == 200
        assert all(empty_cache[name] is None for name in names)

        calls = Calls(monkeypatch)
        assert encodings.search_function(names[0]) is None
        assert calls.imported == [] and calls.normalized == []

    def test_it_expects_a_lowercased_name(self, empty_cache: dict[str, Any]) -> None:
        assert encodings.search_function("UTF-8") is None
        assert encodings.search_function("L1") is None

        utf8 = encodings.search_function("utf-8")
        latin1 = encodings.search_function("l1")

        assert utf8 is not None and utf8.name == "utf-8"
        assert latin1 is not None and latin1.name == "iso8859-1"
        assert codecs.lookup("UTF-8").name == "utf-8"


class TestTheRegistryAsksThePackageOnce:
    """The registry lowercases a name and calls `search_function()` the first
    time it sees it; after that its own cache answers. It does not cache a
    failure, so every distinct unknown name reaches the package's cache."""

    def test_a_known_name_reaches_the_package_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delitem(encodings._cache, "mac_turkish", raising=False)  # noqa: SLF001
        empty_the_registry_cache()
        calls = Calls(monkeypatch)

        first = codecs.lookup("Mac-Turkish")
        second = codecs.lookup("mac turkish")

        assert second is first
        assert calls.normalized == ["mac_turkish"]

    def test_unknown_names_each_add_an_entry(self, empty_cache: dict[str, Any]) -> None:
        for index in range(100):
            with pytest.raises(LookupError, match="unknown encoding"):
                codecs.lookup(f"No-Such-Codec {index}")

        assert len(empty_cache) == 100
        assert "no_such_codec_0" in empty_cache

        asked: list[str] = []

        def recording(name: str) -> None:
            asked.append(name)

        codecs.register(recording)
        try:
            for _ in range(2):
                with pytest.raises(LookupError):
                    codecs.lookup("no-such-codec 0")
        finally:
            codecs.unregister(recording)
        assert asked == ["no_such_codec_0", "no_such_codec_0"], "the registry cached a failure"
        assert len(empty_cache) == 100

    def test_emptying_the_registry_cache_leaves_the_package_s(
        self, empty_cache: dict[str, Any]
    ) -> None:
        with pytest.raises(LookupError):
            codecs.lookup("no-such-codec-x")
        before = dict(empty_cache)

        empty_the_registry_cache()

        assert empty_cache == before and before


class TestWin32CodePageSearchFunction:
    """`win32_code_page_search_function()` exists on Windows from 3.14 only."""

    @pytest.mark.skipif(
        sys.platform == "win32" and sys.version_info >= (3, 14),
        reason="present on Windows 3.14+",
    )
    def test_it_is_absent_here(self) -> None:
        assert not hasattr(encodings, "win32_code_page_search_function")

    @pytest.mark.skipif(
        sys.platform != "win32" or sys.version_info < (3, 14),
        reason="Windows-only API, added in 3.14",
    )
    def test_it_answers_code_pages_only(self) -> None:
        search = encodings.win32_code_page_search_function  # type: ignore[attr-defined]

        assert search("cp1252").name == "cp1252"
        assert search("CP437").name == "cp437"
        assert search("utf-8") is None
        assert search("cpxyz") is None


class TestAliasTable:
    """`encodings.aliases.aliases` is a plain dict from normalized alias to
    codec module name, consulted after normalizing."""

    def test_it_is_a_dict_of_normalized_names(self) -> None:
        assert type(aliases) is dict
        assert all(encodings.normalize_encoding(key) == key for key in aliases)
        assert aliases["l1"] == "latin_1"
        assert aliases["utf8"] == "utf_8"

    def test_every_target_is_a_module_in_the_package(self) -> None:
        package = pathlib.Path(encodings.__file__).parent

        missing = {name for name in aliases.values() if not (package / f"{name}.py").exists()}

        assert not missing

    def test_the_search_function_goes_through_it(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        calls = Calls(monkeypatch)

        info = encodings.search_function("l1")

        assert info is not None and info.name == "iso8859-1"
        assert calls.imported == ["encodings.latin_1"]


class TestCodecRegistryError:
    """`CodecRegistryError` | O(1) | O(1): raised for a module whose
    `getregentry()` returns neither a `CodecInfo` nor a valid tuple."""

    @staticmethod
    def _install(monkeypatch: pytest.MonkeyPatch, name: str, entry: Any) -> None:
        module = types.ModuleType(f"encodings.{name}")
        module.__file__ = f"{name}.py"
        module.getregentry = lambda: entry  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, f"encodings.{name}", module)

    def test_it_is_a_lookup_error_and_a_system_error(self) -> None:
        assert issubclass(encodings.CodecRegistryError, LookupError)
        assert issubclass(encodings.CodecRegistryError, SystemError)

    def test_a_short_tuple_is_rejected_every_time(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        self._install(monkeypatch, "zz_short_entry", (1, 2))

        for _ in range(2):
            with pytest.raises(encodings.CodecRegistryError, match="failed to register"):
                encodings.search_function("zz_short_entry")
        assert "zz_short_entry" not in empty_cache

    def test_non_callables_are_rejected(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        self._install(monkeypatch, "zz_bad_entry", (1, 2, 3, 4))

        with pytest.raises(LookupError, match="incompatible codecs"):
            encodings.search_function("zz_bad_entry")

    def test_a_valid_tuple_becomes_a_codec_info(
        self, monkeypatch: pytest.MonkeyPatch, empty_cache: dict[str, Any]
    ) -> None:
        self._install(monkeypatch, "zz_tuple_entry", (str, str, None, None))

        info = encodings.search_function("zz_tuple_entry")

        assert isinstance(info, codecs.CodecInfo)
        assert info.name == "zz_tuple_entry"


class TestEncodingIsLinear:
    """`str.encode()`, `bytes.decode()` | O(n) | O(n) for UTF-8, ASCII and
    Latin-1 with `'strict'`, `'ignore'` or `'replace'`."""

    PHRASE = "Hello, 世界 café "
    CASES = [
        ("encode", "utf-8", "strict"),
        ("encode", "ascii", "ignore"),
        ("encode", "ascii", "replace"),
        ("encode", "latin-1", "replace"),
        ("decode", "utf-8", "strict"),
        ("decode", "utf-8", "ignore"),
        ("decode", "utf-8", "replace"),
        ("decode", "ascii", "replace"),
        ("decode", "latin-1", "strict"),
    ]

    @classmethod
    def operation(cls, direction: str, encoding: str, errors: str, repeats: int) -> Any:
        text = cls.PHRASE * repeats
        if direction == "encode":
            return lambda: text.encode(encoding, errors)
        unit = cls.PHRASE.encode("utf-8") + (b"" if errors == "strict" else b"\xff")
        data = unit * repeats
        return lambda: data.decode(encoding, errors)

    @pytest.mark.parametrize(("direction", "encoding", "errors"), CASES)
    def test_output_follows_input(self, direction: str, encoding: str, errors: str) -> None:
        lengths = [len(self.operation(direction, encoding, errors, r)()) for r in (10, 1_000)]

        assert lengths[1] == lengths[0] * 100

    def test_ascii_and_latin_1_strict_encode(self) -> None:
        assert ("Hello " * 3).encode("ascii") == b"Hello Hello Hello "
        assert "café".encode("latin-1") == b"caf\xe9"
        with pytest.raises(UnicodeEncodeError):
            self.PHRASE.encode("latin-1")

    @pytest.mark.timing
    @pytest.mark.parametrize(("direction", "encoding", "errors"), CASES)
    def test_time_is_linear(self, direction: str, encoding: str, errors: str) -> None:
        operations = [self.operation(direction, encoding, errors, r) for r in (2_000, 2_000_000)]

        for operation in operations:
            operation()
        durations = [best_ns(operation, repeats=7, inner=5) for operation in operations]
        ratio = durations[1] / durations[0]

        assert ratio < 32_000, (
            f"{direction} {encoding} {errors}: 1,000x input costs {ratio:.1f}x "
            f"({durations} ns); quadratic would be 1,000,000x"
        )


class Counter:
    """Replace a module-level function with one that records its arguments."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, module: Any, name: str) -> None:
        self.calls: list[Any] = []
        original = getattr(module, name)

        def counting(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(args[0])
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, counting)


def distinct_cjk(length: int) -> str:
    """`length` different CJK ideographs, all kept by nameprep."""
    return "".join(chr(0x4E00 + index) for index in range(length))


def assert_hundredfold_is_linear(small: float, large: float, what: str) -> None:
    """100x the input must cost under 1,000x: linear is 100x, quadratic 10,000x."""
    ratio = large / small
    assert ratio < 1_000, f"100x {what} cost {ratio:.0f}x ({small} -> {large} ns)"


class TestIdnaCodec:
    """`str.encode('idna')`, `bytes.decode('idna')` | O(n) plus one
    `ToASCII()` or `ToUnicode()` per label | O(n): ASCII names bypass both,
    and only `'strict'` errors are accepted."""

    def test_an_ascii_name_is_encoded_as_is(self, monkeypatch: pytest.MonkeyPatch) -> None:
        to_ascii = Counter(monkeypatch, idna, "ToASCII")

        assert "Example.COM".encode("idna") == b"Example.COM"
        assert to_ascii.calls == []

    def test_ascii_labels_are_length_checked(self) -> None:
        assert ("a" * 63 + ".com").encode("idna") == b"a" * 63 + b".com"
        with pytest.raises(UnicodeError, match="too long"):
            ("a" * 64 + ".com").encode("idna")
        with pytest.raises(UnicodeError, match="empty"):
            "a..com".encode("idna")

    def test_a_non_ascii_name_converts_each_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        to_ascii = Counter(monkeypatch, idna, "ToASCII")

        assert "bücher.example".encode("idna") == b"xn--bcher-kva.example"
        assert to_ascii.calls == ["bücher", "example"]

    def test_an_ascii_name_without_xn_is_decoded_as_is(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        to_unicode = Counter(monkeypatch, idna, "ToUnicode")

        assert b"Example.COM".decode("idna") == "Example.COM"
        assert to_unicode.calls == []

    def test_an_ace_name_decodes_each_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        to_unicode = Counter(monkeypatch, idna, "ToUnicode")

        assert b"xn--bcher-kva.example".decode("idna") == "bücher.example"
        assert to_unicode.calls == [b"xn--bcher-kva", b"example"]

    @pytest.mark.parametrize("errors", ["ignore", "replace"])
    def test_only_strict_errors(self, errors: str) -> None:
        with pytest.raises(UnicodeError, match="rror handling"):
            "example.com".encode("idna", errors)
        with pytest.raises(UnicodeError, match="rror handling"):
            b"example.com".decode("idna", errors)

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["example", "bücher"])
    def test_time_is_linear_in_the_labels(self, name: str) -> None:
        small, large = (".".join([name] * labels) for labels in (100, 10_000))
        small_bytes, large_bytes = small.encode("idna"), large.encode("idna")

        assert_hundredfold_is_linear(
            best_ns(lambda: small.encode("idna")),
            best_ns(lambda: large.encode("idna")),
            f"{name} labels encoded",
        )
        assert_hundredfold_is_linear(
            best_ns(lambda: small_bytes.decode("idna")),
            best_ns(lambda: large_bytes.decode("idna")),
            f"{name} labels decoded",
        )


class TestToASCII:
    """`ToASCII(label)` | O(m) for a label that is or prepares to ASCII,
    O(m·u) otherwise | O(m): nameprep, punycode unless that left ASCII, then
    the 63-octet check on the `xn--` result."""

    def test_an_ascii_label_is_only_length_checked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        nameprep = Counter(monkeypatch, idna, "nameprep")

        assert idna.ToASCII("EXAMPLE") == b"EXAMPLE"
        assert idna.ToASCII("a" * 63) == b"a" * 63
        for label in ("a" * 64, ""):
            with pytest.raises(UnicodeError):
                idna.ToASCII(label)
        assert nameprep.calls == []

    def test_a_non_ascii_label_is_prepared_and_punycoded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nameprep = Counter(monkeypatch, idna, "nameprep")
        encode = Counter(monkeypatch, punycode, "punycode_encode")

        assert idna.ToASCII("Bücher") == b"xn--bcher-kva"
        assert nameprep.calls == ["Bücher"]
        assert encode.calls == ["bücher"]

    def test_a_label_nameprep_makes_ascii_skips_punycode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nameprep = Counter(monkeypatch, idna, "nameprep")
        encode = Counter(monkeypatch, punycode, "punycode_encode")

        assert idna.ToASCII("Stra\u00dfe") == b"strasse"
        assert nameprep.calls == ["Stra\u00dfe"]
        assert encode.calls == []

    def test_the_limit_is_checked_after_conversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        nameprep = Counter(monkeypatch, idna, "nameprep")
        encode = Counter(monkeypatch, punycode, "punycode_encode")
        label = distinct_cjk(2_000)

        with pytest.raises(UnicodeError, match="too long"):
            idna.ToASCII(label)
        assert nameprep.calls == [label]
        assert encode.calls == [label]

    def test_63_characters_can_exceed_63_octets(self) -> None:
        with pytest.raises(UnicodeError, match="too long"):
            idna.ToASCII("ü" * 63)
        assert len(idna.ToASCII("ü" * 40)) < 64

    @pytest.mark.timing
    def test_distinct_characters_cost_more_than_repeats(self) -> None:
        def attempt(label: str) -> Callable[[], None]:
            def run() -> None:
                with pytest.raises(UnicodeError):
                    idna.ToASCII(label)

            return run

        varied = best_ns(attempt(distinct_cjk(2_000)), repeats=2)
        repeated = best_ns(attempt("\u4e00" * 2_000), repeats=3)

        assert varied > 10 * repeated, (
            f"2,000 distinct characters took {varied} ns, one repeated {repeated} ns; "
            "O(m·u) predicts a ratio that grows with u, O(m) about 1x"
        )


class TestToUnicode:
    """`ToUnicode(label)` | O(m) without `xn--`, O(m²) with it | O(m); 3.12+
    rejects a label over 1,024 characters before any work."""

    def test_a_label_without_the_prefix_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        decode = Counter(monkeypatch, punycode, "punycode_decode")

        assert idna.ToUnicode(b"Example") == "Example"
        assert idna.ToUnicode("example") == "example"
        assert decode.calls == []

    def test_an_ace_label_is_decoded_and_round_tripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decode = Counter(monkeypatch, punycode, "punycode_decode")
        to_ascii = Counter(monkeypatch, idna, "ToASCII")

        assert idna.ToUnicode(b"xn--bcher-kva") == "bücher"
        assert decode.calls == [b"bcher-kva"]
        assert to_ascii.calls == ["bücher"]

    def test_a_non_ascii_str_must_prepare_to_ascii(self) -> None:
        with pytest.raises(UnicodeError):
            idna.ToUnicode("bücher")

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the length guard is 3.12+")
    def test_a_long_label_is_rejected_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        nameprep = Counter(monkeypatch, idna, "nameprep")
        decode = Counter(monkeypatch, punycode, "punycode_decode")

        with pytest.raises(UnicodeError) as at_the_limit:
            idna.ToUnicode(b"xn--" + b"a" * 1_020)  # 1,024 characters: decoded
        assert "way too long" not in str(at_the_limit.value)
        assert decode.calls == [b"a" * 1_020]
        nameprep.calls.clear()
        decode.calls.clear()

        for label in (b"xn--" + b"a" * 1_021, "ü" * 1_025, b"xn--" + b"a" * 1_000_000):
            with pytest.raises(UnicodeError, match="way too long"):
                idna.ToUnicode(label)
        assert nameprep.calls == [] and decode.calls == []

    def test_the_codec_decodes_a_long_plain_ascii_label_without_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        to_unicode = Counter(monkeypatch, idna, "ToUnicode")

        assert (b"a" * 1_025 + b".com").decode("idna") == "a" * 1_025 + ".com"
        assert to_unicode.calls == []

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="3.12+ rejects the label first")
    def test_a_long_label_is_decoded_before_3_12(self, monkeypatch: pytest.MonkeyPatch) -> None:
        decode = Counter(monkeypatch, punycode, "punycode_decode")

        with pytest.raises(UnicodeError):
            idna.ToUnicode(b"xn--" + b"a" * 2_000)
        assert decode.calls == [b"a" * 2_000]


class TestNameprep:
    """`nameprep(label)` | O(m) | O(m): map, NFKC, prohibit, bidi."""

    def test_it_maps_and_normalizes(self) -> None:
        assert idna.nameprep("Bücher") == "bücher"
        assert idna.nameprep("Stra\u00dfe\u00ad") == "strasse"
        assert idna.nameprep("a\u0315\u0300") == "\u00e0\u0315"

    @pytest.mark.timing
    @pytest.mark.parametrize("unit", ["Bücher\u00ad", "\u0315\u0300"], ids=["text", "marks"])
    def test_time_is_linear_in_the_label(self, unit: str) -> None:
        if unit == "\u0315\u0300":
            require_patched_normalization()
        small, large = ("a" + unit * (length // len(unit)) for length in (1_000, 100_000))

        assert_hundredfold_is_linear(
            best_ns(lambda: idna.nameprep(small), repeats=3),
            best_ns(lambda: idna.nameprep(large), repeats=3),
            "the label",
        )


class TestUtf8Sig:
    """`utf-8-sig`: a BOM on every whole encode, one leading BOM skipped on
    decode; the incremental encoder writes it once, the incremental decoder
    holds back a possible BOM prefix."""

    BOM = codecs.BOM_UTF8

    def test_every_encode_writes_a_bom(self) -> None:
        assert "hello".encode("utf-8-sig") == self.BOM + b"hello"
        assert "".encode("utf-8-sig") == self.BOM
        assert "\ufeffx".encode("utf-8-sig") == self.BOM * 2 + b"x"

    def test_decode_skips_one_leading_bom(self) -> None:
        assert (self.BOM + b"hello").decode("utf-8-sig") == "hello"
        assert b"hello".decode("utf-8-sig") == "hello"
        assert (self.BOM * 2).decode("utf-8-sig") == "\ufeff"
        assert (b"a" + self.BOM).decode("utf-8-sig") == "a\ufeff"

    def test_the_incremental_encoder_writes_the_bom_once(self) -> None:
        encoder = codecs.getincrementalencoder("utf-8-sig")()

        assert encoder.encode("he") == self.BOM + b"he"
        assert encoder.encode("llo") == b"llo"
        encoder.reset()
        assert encoder.encode("x") == self.BOM + b"x"

    def test_the_incremental_decoder_holds_a_possible_bom(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8-sig")()

        assert decoder.decode(self.BOM[:1]) == ""
        assert decoder.decode(self.BOM[1:2]) == ""
        assert decoder.decode(self.BOM[2:] + b"hi") == "hi"
        assert decoder.decode(self.BOM) == "\ufeff"
        decoder.reset()
        assert decoder.decode(self.BOM + b"x") == "x"

    def test_a_first_byte_that_cannot_start_a_bom_is_returned(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8-sig")()

        assert decoder.decode(b"h") == "h"
        assert decoder.decode(self.BOM + b"x") == "\ufeffx"

    @pytest.mark.timing
    def test_whole_calls_are_linear(self) -> None:
        small, large = (TestEncodingIsLinear.PHRASE * r for r in (2_000, 200_000))
        small_bytes, large_bytes = small.encode("utf-8-sig"), large.encode("utf-8-sig")

        assert_hundredfold_is_linear(
            best_ns(lambda: small.encode("utf-8-sig")),
            best_ns(lambda: large.encode("utf-8-sig")),
            "the text encoded",
        )
        assert_hundredfold_is_linear(
            best_ns(lambda: small_bytes.decode("utf-8-sig")),
            best_ns(lambda: large_bytes.decode("utf-8-sig")),
            "the bytes decoded",
        )

    @pytest.mark.timing
    def test_incremental_calls_cost_their_chunk(self) -> None:
        text = TestEncodingIsLinear.PHRASE * 40_000
        blob = text.encode("utf-8-sig")
        assert len(blob) > 10_000 * 61

        def feed(chunks: int) -> Callable[[], str]:
            def run() -> str:
                decoder = codecs.getincrementaldecoder("utf-8-sig")()
                return "".join(
                    decoder.decode(blob[index * 61 : (index + 1) * 61]) for index in range(chunks)
                )

            return run

        decoded = feed(10_000)()
        assert text.startswith(decoded) and len(decoded.encode("utf-8")) > 10_000 * 61 - 8

        assert_hundredfold_is_linear(
            best_ns(feed(100), repeats=3), best_ns(feed(10_000), repeats=3), "the 61-byte chunks"
        )

    @pytest.mark.timing
    def test_one_incremental_call_is_linear_in_its_chunk(self) -> None:
        small, large = (
            (TestEncodingIsLinear.PHRASE * r).encode("utf-8-sig") for r in (2_000, 200_000)
        )

        def decode(chunk: bytes) -> Callable[[], str]:
            return lambda: codecs.getincrementaldecoder("utf-8-sig")().decode(chunk)

        assert_hundredfold_is_linear(best_ns(decode(small)), best_ns(decode(large)), "the chunk")


class TestMbcs:
    """`mbcs`: Windows' ANSI code page, aliases `ansi` and `dbcs`."""

    def test_the_aliases(self) -> None:
        assert aliases["ansi"] == "mbcs"
        assert aliases["dbcs"] == "mbcs"

    @pytest.mark.skipif(sys.platform == "win32", reason="present on Windows")
    def test_it_is_absent_here(self) -> None:
        for name in ("mbcs", "ansi", "dbcs"):
            with pytest.raises(LookupError, match="unknown encoding"):
                codecs.lookup(name)
        with pytest.raises(ImportError):
            __import__("encodings.mbcs")

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only codec")
    def test_it_round_trips_ascii(self) -> None:
        assert codecs.lookup("dbcs").name == "mbcs"
        assert "abc".encode("mbcs") == b"abc"
        assert b"abc".decode("mbcs") == "abc"


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
    """Each block runs in its own subprocess, so the codec caches start empty
    of what the other blocks looked up, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "search_function('L1') is None" in s)
        mutated = source.replace(
            "search_function('L1') is None", "search_function('L1') is not None", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
