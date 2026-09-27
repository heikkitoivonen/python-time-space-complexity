"""Tests for docs/stdlib/encodings.md.

The page prices the package's own work, which is name handling: normalizing a
name, mapping it through the alias table, and importing a codec module the
first time a name reaches the search function. The caching rows are settled
by observation - a counting `normalize_encoding`, a counting `__import__`, the
contents of the package's cache and identity of what it returns - so they need
no tolerance. Timing is used only for the growth class of normalizing a name
and of encoding and decoding, always as a ratio between input sizes.

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
  phrase mixing ASCII, Latin-1 and CJK text at 2,000, 20,000 and 200,000
  repeats, encoded as UTF-8 for decoding, with an undecodable `\\xff` after
  each phrase for `'ignore'` and `'replace'`; each 10x step must cost under
  30x.
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
  codecs than UTF-8, ASCII and Latin-1, and other error handlers, are not
  timed here; `test_codecs_complexity.py` times more of them.
* `search_function('UTF-8')` returning `None` depends on imports matching
  module names by case, which is observed on Linux only.
* `win32_code_page_search_function()` is Windows-only, so no run this project
  performs verifies its rows; its test skips everywhere else.
* The individual codec modules (`encodings.idna`, `encodings.utf_8_sig`,
  `encodings.mbcs` and the rest) are excluded from the page's audit and
  priced by codec on the codecs page.
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
from encodings.aliases import aliases
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "encodings.md"
EXPECTED_BLOCKS = 3


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
        operations = [
            self.operation(direction, encoding, errors, r) for r in (2_000, 20_000, 200_000)
        ]

        durations = [best_ns(operation) for operation in operations]
        ratios = [durations[1] / durations[0], durations[2] / durations[1]]

        assert all(ratio < 30 for ratio in ratios), (
            f"{direction} {encoding} {errors}: 10x steps cost {ratios} ({durations} ns); "
            "quadratic would be 100x"
        )


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
