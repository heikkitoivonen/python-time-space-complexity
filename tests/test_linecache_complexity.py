"""Tests for docs/stdlib/linecache.md.

The page prices the module as a cache of whole files: the first `getline()`
for a file reads all of it, later calls index a list, a miss is searched for
again on every call, and the maintenance calls walk the cache. Reads and
searches are settled by counting `os.stat()` and `tokenize.open()` calls,
which needs no tolerance; space is settled by traced allocation; only
`clearcache()` needs a stopwatch, because freeing is all it does. Tests that
fill the cache by hand replace `linecache.cache` with a dict of their own, the
tuple shape `(size, mtime, lines, fullname)` Lib/linecache.py stores on every
supported version.

Measurement scope:

* First call: after `getline(path, 1)` on a 1,000-line file, the file is
  removed and line 1,000 is still returned, so the whole file was read. The
  traced peak of that first call on a 100,000-line file is over 4x the peak
  on a 10,000-line one; each first read also carries a fixed peak of some
  140 KB from opening the file, which is why the smaller file is not smaller
  still. An out-of-range line number returns `''` and still
  caches the file. A relative name found only in the last of p `sys.path`
  directories costs p + 1 `os.stat()` calls at p = 10 and p = 1,000.
* Cached call: zero `os.stat()` and zero `tokenize.open()` calls, the same
  string object on every call, and a traced peak under 1,000 bytes on a
  100,000-line file.
* Miss: a relative name that resolves nowhere costs p + 1 `os.stat()` calls
  at p = 10 and p = 1,000, and the same again on a second call, so nothing is
  cached; its traced peak at p = 1,000 is under twice the peak at p = 10. An
  absolute missing name costs one `os.stat()` whatever p is, and `'<string>'`
  costs none.
* `lazycache()`: a counting loader's `get_source()` is not called by
  registration, is called once by the first `getline()` and not by later
  ones. Registration returns `False` for a name already holding lines and for
  a name in angle brackets.
* `checkcache()`: one `os.stat()` per file-backed entry, none for lazy or
  loader-backed entries, among 1,000 entries of each kind;
  `checkcache(filename)` costs one `os.stat()` among those 3,000 entries. Its traced peak over
  100,000 loader-backed entries, which it does not stat, is over 100x the
  peak over 100, which is the key snapshot. An unchanged file's entry
  survives it, an edited or deleted file's does not.
* `clearcache()`: time for one cached entry of 2,000, 20,000 and 200,000
  lines rises more than 4x at each 10x step, and so does time for 1,000,
  10,000 and 100,000 lazy entries holding no lines, with the cache refilled
  outside the timed call; its traced peak is under 1,000 bytes. A file is
  read again after it.
* The 3.14 `<frozen ...>` resolution is asserted on each side of the version
  guard with a temporary file standing in for `__file__`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Pricing `os.stat()` at O(1) is a cost-model choice; its real cost is a
  system call whose price depends on the filesystem.
* The O(n) first read is measured on ASCII files with no encoding cookie;
  `tokenize.open()` decoding other encodings is not varied.
* Freeing the lines of an entry `checkcache()` drops is charged to the read
  that cached them, so the page prices `checkcache()` by the entries it
  checks. `clearcache()` is priced with its freeing, because that is all it
  does.
* Empty files cache no lines before 3.13 and one `'\\n'` line from 3.13; the
  page does not document the difference, which changes no bound.
* The first-call cost of a loader-backed name adds whatever the loader's
  `get_source()` costs, which the module does not control.
* `linecache.getlines`, `linecache.updatecache` and `linecache.cache` are
  public-looking but absent from the official documentation, so the page does
  not price them; the tests use `cache` only to fill and inspect the cache.
"""

from __future__ import annotations

import linecache
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tokenize
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "linecache.md"
EXPECTED_BLOCKS = 5


def best_ns(setup: Callable[[], Any], func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs of func, in nanoseconds, with setup untimed."""
    best: float | None = None
    for _ in range(repeats):
        setup()
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


def write_source(path: pathlib.Path, lines: int) -> pathlib.Path:
    path.write_text("".join(f"x{i} = {i}\n" for i in range(1, lines + 1)), encoding="utf-8")
    return path


class Counter:
    """Wraps a function and records every call."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.calls: list[Any] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(args[0] if args else None)
        return self.func(*args, **kwargs)


class CountingLoader:
    def __init__(self, source: str | None) -> None:
        self.source = source
        self.calls: list[str] = []

    def get_source(self, name: str) -> str | None:
        self.calls.append(name)
        return self.source


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts with an empty cache that does not outlive it."""
    monkeypatch.setattr(linecache, "cache", {})


@pytest.fixture
def stats(monkeypatch: pytest.MonkeyPatch) -> Counter:
    counter = Counter(os.stat)
    monkeypatch.setattr(os, "stat", counter)
    return counter


@pytest.fixture
def opens(monkeypatch: pytest.MonkeyPatch) -> Counter:
    counter = Counter(tokenize.open)
    monkeypatch.setattr(tokenize, "open", counter)
    return counter


def search_path(tmp_path: pathlib.Path, entries: int) -> list[str]:
    """`entries` directories that exist and are empty."""
    dirs = []
    for index in range(entries):
        directory = tmp_path / f"d{index}"
        directory.mkdir(parents=True)
        dirs.append(str(directory))
    return dirs


class TestFirstCallReadsTheWholeFile:
    """`getline()` first call | O(p + n) | O(n): the whole file is read and
    kept, whichever line is asked for; p only for a relative name searched
    along `sys.path`."""

    def test_every_line_is_cached_by_asking_for_the_first(self, tmp_path: pathlib.Path) -> None:
        path = str(write_source(tmp_path / "m.py", 1_000))

        assert linecache.getline(path, 1) == "x1 = 1\n"
        os.remove(path)

        assert linecache.getline(path, 1_000) == "x1000 = 1000\n"

    def test_an_out_of_range_line_still_reads_the_file(self, tmp_path: pathlib.Path) -> None:
        path = str(write_source(tmp_path / "m.py", 10))

        assert linecache.getline(path, 0) == ""
        assert linecache.getline(path, 11) == ""
        os.remove(path)

        assert linecache.getline(path, 10) == "x10 = 10\n"

    def test_the_peak_grows_with_the_file(self, tmp_path: pathlib.Path) -> None:
        peaks = {}
        for lines in (10_000, 100_000):
            path = str(write_source(tmp_path / f"m{lines}.py", lines))
            peaks[lines] = peak_bytes(lambda p=path: linecache.getline(p, 1))

        assert peaks[100_000] > peaks[10_000] * 4, peaks

    @pytest.mark.parametrize("entries", [10, 1_000])
    def test_a_relative_name_is_searched_along_sys_path(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        stats: Counter,
        entries: int,
    ) -> None:
        dirs = search_path(tmp_path, entries)
        write_source(pathlib.Path(dirs[-1]) / "found_last.py", 3)
        monkeypatch.setattr(sys, "path", dirs)
        monkeypatch.chdir(tmp_path)

        assert linecache.getline("found_last.py", 3) == "x3 = 3\n"
        assert len(stats.calls) == entries + 1

        linecache.getline("found_last.py", 2)
        assert len(stats.calls) == entries + 1, "a found file is cached"


class TestCachedLookupIsConstant:
    """`getline()` on a cached file | O(1) | O(1): no I/O, no stat, and no
    notice of the file changing."""

    def test_no_stat_and_no_open(
        self, tmp_path: pathlib.Path, stats: Counter, opens: Counter
    ) -> None:
        path = str(write_source(tmp_path / "m.py", 100))
        linecache.getline(path, 1)
        stats.calls.clear()
        opens.calls.clear()

        for number in range(1, 101):
            linecache.getline(path, number)

        assert stats.calls == []
        assert opens.calls == []

    def test_the_same_string_comes_back(self, tmp_path: pathlib.Path) -> None:
        path = str(write_source(tmp_path / "m.py", 100_000))

        first = linecache.getline(path, 50_000)

        assert linecache.getline(path, 50_000) is first

    def test_a_cached_call_allocates_nothing_for_the_file(self, tmp_path: pathlib.Path) -> None:
        path = str(write_source(tmp_path / "m.py", 100_000))
        linecache.getline(path, 1)
        linecache.getline(path, 2)  # warm

        peak = peak_bytes(lambda: linecache.getline(path, 99_999))

        assert peak < 1_000, f"a cached getline() peaked at {peak} bytes"

    def test_an_edit_is_not_seen(self, tmp_path: pathlib.Path) -> None:
        path = write_source(tmp_path / "m.py", 1)
        linecache.getline(str(path), 1)

        path.write_text("changed = True\n", encoding="utf-8")

        assert linecache.getline(str(path), 1) == "x1 = 1\n"


class TestMissesAreNotCached:
    """`getline()` for a file it cannot find | O(p) | O(1): `''`, and the
    search is repeated on every call."""

    @pytest.mark.parametrize("entries", [10, 1_000])
    def test_a_relative_miss_stats_every_entry_every_time(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        stats: Counter,
        entries: int,
    ) -> None:
        monkeypatch.setattr(sys, "path", search_path(tmp_path, entries))
        monkeypatch.chdir(tmp_path)

        assert linecache.getline("nowhere.py", 1) == ""
        assert len(stats.calls) == entries + 1

        assert linecache.getline("nowhere.py", 1) == ""
        assert len(stats.calls) == 2 * (entries + 1)

    def test_a_miss_does_not_hold_the_search(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        peaks = {}
        for entries in (10, 1_000):
            monkeypatch.setattr(sys, "path", search_path(tmp_path / str(entries), entries))
            linecache.getline("nowhere.py", 1)  # warm
            peaks[entries] = peak_bytes(lambda: linecache.getline("nowhere.py", 1))

        assert peaks[1_000] < peaks[10] * 2, peaks

    def test_an_absolute_miss_does_not_search(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        stats: Counter,
    ) -> None:
        monkeypatch.setattr(sys, "path", search_path(tmp_path, 100))

        assert linecache.getline(str(tmp_path / "absent.py"), 1) == ""
        assert len(stats.calls) == 1

    def test_a_pseudo_file_name_is_not_looked_up(self, stats: Counter) -> None:
        assert linecache.getline("<string>", 1) == ""
        assert stats.calls == []


class TestLazycacheDefersTheFetch:
    """`lazycache()` | O(1) | O(1): records `get_source`; the first
    `getline()` calls it once."""

    def test_registration_fetches_nothing(self, tmp_path: pathlib.Path) -> None:
        loader = CountingLoader("a = 1\nb = 2\n")
        name = str(tmp_path / "virtual.py")

        assert linecache.lazycache(name, {"__name__": "virtual", "__loader__": loader})
        assert loader.calls == []

        assert linecache.getline(name, 2) == "b = 2\n"
        assert linecache.getline(name, 1) == "a = 1\n"
        assert loader.calls == ["virtual"]

    def test_nothing_to_register_for_a_cached_or_pseudo_name(self, tmp_path: pathlib.Path) -> None:
        path = str(write_source(tmp_path / "m.py", 1))
        module_globals = {"__name__": "m", "__loader__": CountingLoader("")}
        linecache.getline(path, 1)

        assert linecache.lazycache(path, module_globals) is False
        assert linecache.lazycache("<string>", module_globals) is False


class TestCheckcacheStatsEachFile:
    """`checkcache()` | O(f) | O(f); `checkcache(filename)` | O(1) | O(1).
    Lazy and loader-backed entries are skipped."""

    @staticmethod
    def fill(tmp_path: pathlib.Path, count: int) -> dict[str, tuple[Any, ...]]:
        real = write_source(tmp_path / "real.py", 1)
        stat = os.stat(real)
        cache: dict[str, tuple[Any, ...]] = {}
        for index in range(count):
            cache[f"file{index}"] = (stat.st_size, stat.st_mtime, ["x1 = 1\n"], str(real))
            cache[f"loaded{index}"] = (1, None, ["x\n"], f"loaded{index}")
            cache[f"lazy{index}"] = (lambda: "x\n",)
        return cache

    def test_one_stat_per_file_backed_entry(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, stats: Counter
    ) -> None:
        cache = self.fill(tmp_path, 1_000)
        monkeypatch.setattr(linecache, "cache", cache)
        stats.calls.clear()

        linecache.checkcache()

        assert len(stats.calls) == 1_000
        assert len(cache) == 3_000, "unchanged and unchecked entries are kept"

    def test_one_name_is_one_stat(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, stats: Counter
    ) -> None:
        monkeypatch.setattr(linecache, "cache", self.fill(tmp_path, 1_000))
        stats.calls.clear()

        linecache.checkcache("file500")

        assert len(stats.calls) == 1

    def test_the_key_snapshot_grows_with_the_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        peaks = {}
        for count in (100, 100_000):
            cache = {f"loaded{i}": (1, None, ["x\n"], f"loaded{i}") for i in range(count)}
            monkeypatch.setattr(linecache, "cache", cache)
            linecache.checkcache()  # warm
            peaks[count] = peak_bytes(linecache.checkcache)

        assert peaks[100_000] > peaks[100] * 100, peaks

    def test_edited_and_deleted_files_are_dropped(self, tmp_path: pathlib.Path) -> None:
        kept = str(write_source(tmp_path / "kept.py", 1))
        edited = write_source(tmp_path / "edited.py", 1)
        deleted = str(write_source(tmp_path / "deleted.py", 1))
        line = linecache.getline(kept, 1)
        linecache.getline(str(edited), 1)
        linecache.getline(deleted, 1)

        edited.write_text("changed = True\n", encoding="utf-8")
        os.remove(deleted)
        linecache.checkcache()

        assert linecache.getline(kept, 1) is line
        assert linecache.getline(str(edited), 1) == "changed = True\n"
        assert linecache.getline(deleted, 1) == ""


class TestClearcacheFreesEveryLine:
    """`clearcache()` | O(f + t) | O(1): dropping the entries and freeing
    their lines is the work, and each term grows with the other held fixed."""

    @pytest.mark.timing
    def test_time_tracks_the_lines_held(self) -> None:
        times = {}
        for lines in (2_000, 20_000, 200_000):

            def fill(count: int = lines) -> None:
                linecache.cache["one.py"] = (1, 1.0, [f"line {i}\n" for i in range(count)], "x")

            times[lines] = best_ns(fill, linecache.clearcache)

        assert times[20_000] > times[2_000] * 4, times
        assert times[200_000] > times[20_000] * 4, times

    @pytest.mark.timing
    def test_time_tracks_the_entries_with_no_lines_held(self) -> None:
        times = {}
        for entries in (1_000, 10_000, 100_000):

            def fill(count: int = entries) -> None:
                def source() -> str:
                    return "x\n"

                for index in range(count):
                    linecache.cache[f"lazy{index}"] = (source,)

            times[entries] = best_ns(fill, linecache.clearcache)

        assert times[10_000] > times[1_000] * 4, times
        assert times[100_000] > times[10_000] * 4, times

    def test_it_allocates_nothing(self) -> None:
        linecache.cache["one.py"] = (1, 1.0, [f"line {i}\n" for i in range(100_000)], "x")

        peak = peak_bytes(linecache.clearcache)

        assert peak < 1_000, f"clearcache() peaked at {peak} bytes"
        assert linecache.cache == {}

    def test_the_next_call_reads_again(self, tmp_path: pathlib.Path, opens: Counter) -> None:
        path = str(write_source(tmp_path / "m.py", 1))
        linecache.getline(path, 1)

        linecache.clearcache()
        linecache.getline(path, 1)

        assert len(opens.calls) == 2


class TestFrozenModuleNames:
    """Version note: from 3.14, a `<frozen ...>` name is read through
    `module_globals['__file__']`; earlier versions return `''`."""

    def test_a_frozen_name_uses_the_file_in_module_globals(self, tmp_path: pathlib.Path) -> None:
        path = str(write_source(tmp_path / "frozen_stand_in.py", 2))

        line = linecache.getline("<frozen stand_in>", 2, {"__file__": path})

        if sys.version_info >= (3, 14):
            assert line == "x2 = 2\n"
        else:
            assert line == ""


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, and
    asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "calls == ['generated_module']" in s)
        mutated = source.replace("calls == ['generated_module']", "calls == []", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0


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
