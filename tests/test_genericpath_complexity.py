"""Tests for docs/stdlib/genericpath.md.

The page prices every function but `commonprefix()` by the stat-family calls it
makes, counting a syscall as O(1). Those rows are settled by replacing
`os.stat`, `os.lstat` and `os.fstat` with counters and asserting the exact
number of calls, which needs no tolerance. `commonprefix()` is settled by
timing ratios for its time bound and traced allocation for its space bound.

Measurement scope:

* Every predicate, `get*()` function and identity helper is run against a real
  file with the three stat functions counted: `exists()`, `isfile()`,
  `isdir()` and each `get*()` make one `os.stat` call, `lexists()` and
  `islink()` one `os.lstat` call, `samefile()` two `os.stat` calls,
  `sameopenfile()` two `os.fstat` calls, and `samestat()`, `isjunction()` and
  `isdevdrive()` none.
* `commonprefix()` time: items that share a 1,000-character prefix with each
  other, plus one that shares nothing, so the returned prefix is empty and
  only the min/max comparisons scale. 100, 1,000 and 10,000 such items, and
  100 items of 1,000, 10,000 and 100,000 characters: each 10x step costs
  between 3x and 30x, which excludes quadratic growth in either variable. Two
  equal 1,000-, 10,000- and 100,000-character items, distinct objects, scale
  the same way, which is the p term walked in Python.
* `commonprefix()` space: ten 1,000,000-character items with an empty answer
  peak under 10 KB, so the bound is not B; 100,000 six-character items peak
  between 400 KB and 3 MB, which is the n term (one reference per item, not a
  copy of each string); two 1,000,000-character items differing in their
  last character peak between 1 MB and 1.5 MB, which is the p term and one
  copy of it.
* `ALLOW_MISSING` passed as `os.path.realpath(strict=)` returns a path whose
  last two components are missing, where `strict=True` raises
  `FileNotFoundError`.
* Behaviour: `commonprefix()` ends mid-component on strings and compares
  whole items on component lists. The predicates return `False` for a missing
  path and one with an embedded NUL, and a broken symlink is false to
  `exists()` and `isfile()` and true to `lexists()` and `islink()` (not on
  Windows, where creating one needs Developer Mode or admin). `samefile()`
  raises `FileNotFoundError` for a missing second path and `sameopenfile()`
  raises `TypeError` for file objects. `getsize()` raises `FileNotFoundError`
  for a missing path and `ValueError` for an embedded NUL. `samestat()` is called on two plain objects
  carrying only `st_ino` and `st_dev`. `isjunction()` and `isdevdrive()`
  return `False` for a missing path and raise `TypeError` for an integer.
  `getctime()` equals `os.stat().st_ctime`.
* Every name in `genericpath.__all__` is the same object in `posixpath`.
* `islink()` is present from 3.12, `lexists()`, `isjunction()` and
  `isdevdrive()` from 3.13, and absent before; `ALLOW_MISSING` is present from
  3.10.18, 3.11.13, 3.12.11 and 3.13.4, is the object `os.path` exports, and
  is listed in `__all__`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That a syscall is O(1) is the page's cost model, shared with docs/stdlib/os.md;
  the kernel's path resolution is not measured.
* That `getctime()` is creation time on Windows is the `st_ctime` field's
  documented meaning there; the test asserts only that it is `st_ctime`.
* Which type checks Windows's `os.path` replaces with native versions is read
  from Lib/ntpath.py; those are priced on docs/stdlib/ntpath.md. This file
  covers the generic versions, which are the same on every platform.
* `commonprefix()` timing holds the character kind (ASCII) fixed and uses
  `str` items; `bytes` items and wider kinds are not varied.
"""

from __future__ import annotations

import genericpath
import os
import pathlib
import posixpath
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "genericpath.md"
EXPECTED_BLOCKS = 5


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
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


class StatCounter:
    """Counts calls to `os.stat`, `os.lstat` and `os.fstat` while installed."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls = {"stat": 0, "lstat": 0, "fstat": 0}
        for name in self.calls:
            monkeypatch.setattr(os, name, self._counting(name, getattr(os, name)))

    def _counting(self, name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def counted(*args: Any, **kwargs: Any) -> Any:
            self.calls[name] += 1
            return real(*args, **kwargs)

        return counted

    def reset(self) -> None:
        for name in self.calls:
            self.calls[name] = 0


@pytest.fixture
def data_file(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "data.txt"
    path.write_text("hello")
    return path


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> Iterator[StatCounter]:
    yield StatCounter(monkeypatch)


class TestEachCheckIsOneStat:
    """`exists()`, `isfile()`, `isdir()`, `getsize()`, `getmtime()`, `getatime()`
    and `getctime()` | O(1) | one stat; `lexists()` and `islink()` one lstat.

    Exact call counts separate one stat from a check that stats twice or walks
    anything.
    """

    @pytest.mark.parametrize(
        "name", ["exists", "isfile", "isdir", "getsize", "getmtime", "getatime", "getctime"]
    )
    def test_the_function_makes_one_stat_call(
        self, name: str, data_file: pathlib.Path, counter: StatCounter
    ) -> None:
        getattr(genericpath, name)(str(data_file))

        assert counter.calls == {"stat": 1, "lstat": 0, "fstat": 0}

    @pytest.mark.parametrize("name", ["lexists", "islink"])
    def test_the_function_makes_one_lstat_call(
        self, name: str, data_file: pathlib.Path, counter: StatCounter
    ) -> None:
        if not hasattr(genericpath, name):
            pytest.skip(f"version: genericpath.{name} is not defined on this Python")
        getattr(genericpath, name)(str(data_file))

        assert counter.calls == {"stat": 0, "lstat": 1, "fstat": 0}

    def test_getctime_is_the_st_ctime_field(self, data_file: pathlib.Path) -> None:
        assert genericpath.getctime(data_file) == os.stat(data_file).st_ctime


class TestPredicatesReturnFalseAndGettersRaise:
    """`exists()` - `False` for a missing, unreachable or invalid path rather than
    an error; `getsize()` - raises `OSError` if it fails."""

    @pytest.mark.parametrize("name", ["exists", "isfile", "isdir", "islink", "lexists"])
    def test_a_predicate_is_false_for_missing_and_invalid_paths(
        self, name: str, tmp_path: pathlib.Path
    ) -> None:
        if not hasattr(genericpath, name):
            pytest.skip(f"version: genericpath.{name} is not defined on this Python")
        predicate = getattr(genericpath, name)

        assert predicate(str(tmp_path / "missing")) is False
        assert predicate("bad\0name") is False

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="creating a symlink needs Developer Mode or admin on Windows",
    )
    def test_a_broken_link_exists_only_to_the_lstat_checks(self, tmp_path: pathlib.Path) -> None:
        if sys.version_info < (3, 13):
            pytest.skip("version: genericpath gains lexists in 3.13")
        link = tmp_path / "link"
        os.symlink(tmp_path / "missing", link)

        assert genericpath.exists(link) is False
        assert genericpath.isfile(link) is False
        assert genericpath.lexists(link) is True
        assert genericpath.islink(link) is True

    def test_getsize_raises_for_missing_and_invalid_paths(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            genericpath.getsize(tmp_path / "missing")
        with pytest.raises(ValueError):
            genericpath.getsize("bad\0name")


class TestPlatformStubs:
    """`isjunction()` and `isdevdrive()` | O(1) | always `False` without touching
    the disk.

    Counted stat calls are zero, a missing path is `False` rather than an error,
    and a non-path is still rejected, so the argument is checked.
    """

    @pytest.fixture(autouse=True)
    def _requires_313(self) -> None:
        if sys.version_info < (3, 13):
            pytest.skip("version: genericpath gains isjunction and isdevdrive in 3.13")

    @pytest.mark.parametrize("name", ["isjunction", "isdevdrive"])
    def test_the_stub_makes_no_syscall(
        self, name: str, data_file: pathlib.Path, counter: StatCounter
    ) -> None:
        assert getattr(genericpath, name)(str(data_file)) is False
        assert counter.calls == {"stat": 0, "lstat": 0, "fstat": 0}

    @pytest.mark.parametrize("name", ["isjunction", "isdevdrive"])
    def test_the_stub_checks_its_argument(self, name: str, tmp_path: pathlib.Path) -> None:
        stub = getattr(genericpath, name)

        assert stub(str(tmp_path / "missing")) is False
        with pytest.raises(TypeError):
            stub(42)


class TestFileIdentity:
    """`samefile()` two stats, `sameopenfile()` two fstats, `samestat()` no
    syscall: it compares the device and inode numbers of results already
    fetched."""

    def test_samefile_stats_both_paths(self, tmp_path: pathlib.Path, counter: StatCounter) -> None:
        original = tmp_path / "a.txt"
        original.write_text("x")
        alias = tmp_path / "b.txt"
        os.link(original, alias)
        counter.reset()

        assert genericpath.samefile(original, alias)
        assert counter.calls == {"stat": 2, "lstat": 0, "fstat": 0}
        with pytest.raises(FileNotFoundError):
            genericpath.samefile(original, tmp_path / "missing")

    def test_sameopenfile_fstats_both_descriptors(
        self, data_file: pathlib.Path, counter: StatCounter
    ) -> None:
        with open(data_file) as first, open(data_file) as second:
            counter.reset()
            assert genericpath.sameopenfile(first.fileno(), second.fileno())
            assert counter.calls == {"stat": 0, "lstat": 0, "fstat": 2}
            with pytest.raises(TypeError):
                genericpath.sameopenfile(first, second)  # pyright: ignore[reportArgumentType]

    def test_samestat_reads_only_two_fields(self, counter: StatCounter) -> None:
        def fake(ino: int, dev: int) -> os.stat_result:
            return cast("os.stat_result", SimpleNamespace(st_ino=ino, st_dev=dev))

        assert genericpath.samestat(fake(7, 3), fake(7, 3))
        assert not genericpath.samestat(fake(7, 3), fake(7, 4))
        assert not genericpath.samestat(fake(7, 3), fake(8, 3))
        assert counter.calls == {"stat": 0, "lstat": 0, "fstat": 0}


def _shared(count: int, length: int) -> list[str]:
    """`count` distinct items sharing a `length`-character prefix, plus one
    that shares nothing, so the answer is empty and only min/max scale."""
    return ["a" * length + f"{index:08d}" for index in range(count)] + ["b"]


class TestCommonprefixTime:
    """`commonprefix(m)` | O(n + B), n = items, B = their total length.

    Each 10x step in item count, item length, or prefix length is asserted to
    cost between 3x and 30x, which excludes the 100x a quadratic would show.
    """

    @staticmethod
    def _assert_linear(label: str, times: list[float]) -> None:
        ratios = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(3 < ratio < 30 for ratio in ratios), f"{label}: {times} -> {ratios}"

    @pytest.mark.timing
    def test_cost_is_linear_in_the_item_count(self) -> None:
        inputs = [_shared(count, 1_000) for count in (100, 1_000, 10_000)]

        self._assert_linear(
            "items", [best_ns(lambda m=m: genericpath.commonprefix(m)) for m in inputs]
        )

    @pytest.mark.timing
    def test_cost_is_linear_in_the_item_length(self) -> None:
        inputs = [_shared(100, length) for length in (1_000, 10_000, 100_000)]

        self._assert_linear(
            "length", [best_ns(lambda m=m: genericpath.commonprefix(m)) for m in inputs]
        )

    @pytest.mark.timing
    def test_cost_is_linear_in_the_prefix_length(self) -> None:
        inputs = [["x" * length, "x" * (length - 1) + "x"] for length in (1_000, 10_000, 100_000)]
        assert all(m[0] is not m[1] for m in inputs)

        self._assert_linear(
            "prefix", [best_ns(lambda m=m: genericpath.commonprefix(m)) for m in inputs]
        )


class TestCommonprefixSpace:
    """`commonprefix(m)` | O(n + p): one reference per item and the answer, not
    a copy of the input."""

    def test_long_items_with_no_common_prefix_allocate_almost_nothing(self) -> None:
        items = ["x" * 1_000_000 + str(index) for index in range(10)] + ["y"]

        peak = peak_bytes(lambda: genericpath.commonprefix(items))

        assert peak < 10_000, f"{peak} bytes over 10 MB of input"

    def test_many_items_cost_a_reference_each(self) -> None:
        items = [f"{index:06d}" for index in range(100_000)]

        peak = peak_bytes(lambda: genericpath.commonprefix(items))

        assert 400_000 < peak < 3_000_000, f"{peak} bytes for 100,000 items"

    def test_the_answer_is_a_new_string_of_the_prefix_length(self) -> None:
        items = ["x" * 1_000_000 + "a", "x" * 1_000_000 + "b"]

        peak = peak_bytes(lambda: genericpath.commonprefix(items))

        assert 1_000_000 < peak < 1_500_000, f"{peak} bytes for a 1,000,000-character prefix"


class TestCommonprefixCompares:
    """Character by character, so it can end mid-component; a list of component
    lists compares whole components."""

    def test_strings_can_end_mid_component(self) -> None:
        assert genericpath.commonprefix(["/srv/app1/log", "/srv/app2/log"]) == "/srv/app"

    def test_component_lists_compare_whole_components(self) -> None:
        parts = [["", "srv", "app1", "log"], ["", "srv", "app2", "log"]]

        assert genericpath.commonprefix(parts) == ["", "srv"]


class TestAllowMissing:
    """`ALLOW_MISSING` | The `strict=` value for `os.path.realpath()` that
    tolerates a missing tail."""

    def test_realpath_tolerates_a_missing_tail(self, tmp_path: pathlib.Path) -> None:
        if not hasattr(genericpath, "ALLOW_MISSING"):
            pytest.skip("version: ALLOW_MISSING arrives in 3.10.18, 3.11.13, 3.12.11, 3.13.4")
        base = os.path.realpath(tmp_path)
        missing = os.path.join(base, "missing", "tail")

        assert os.path.realpath(missing, strict=genericpath.ALLOW_MISSING) == missing
        with pytest.raises(FileNotFoundError):
            os.path.realpath(missing, strict=True)


class TestOsPathReexports:
    """On POSIX `os.path` re-exports every one of them."""

    def test_posixpath_exports_the_same_objects(self) -> None:
        assert genericpath.__all__
        for name in genericpath.__all__:
            assert getattr(posixpath, name) is getattr(genericpath, name), name


class TestVersionBoundaries:
    """Version Notes: `islink()` 3.12+, `lexists()`, `isjunction()` and
    `isdevdrive()` 3.13+, `ALLOW_MISSING` 3.10.18, 3.11.13, 3.12.11 and
    3.13.4+."""

    def test_islink_arrives_in_312(self) -> None:
        assert hasattr(genericpath, "islink") == (sys.version_info >= (3, 12))

    @pytest.mark.parametrize("name", ["lexists", "isjunction", "isdevdrive"])
    def test_the_313_names_arrive_in_313(self, name: str) -> None:
        assert hasattr(genericpath, name) == (sys.version_info >= (3, 13))
        assert (name in genericpath.__all__) == (sys.version_info >= (3, 13))

    def test_allow_missing_arrives_in_the_listed_patches(self) -> None:
        firsts = {10: 18, 11: 13, 12: 11, 13: 4}
        minor, micro = sys.version_info[1], sys.version_info[2]
        expected = micro >= firsts[minor] if minor in firsts else True

        assert hasattr(genericpath, "ALLOW_MISSING") == expected
        if expected:
            assert "ALLOW_MISSING" in genericpath.__all__
            assert os.path.ALLOW_MISSING is genericpath.ALLOW_MISSING


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
    """Each block runs in its own subprocess and working directory, and asserts
    its own result. The 3.13 block is the only one that needs a version."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "isjunction" in source and sys.version_info < (3, 13):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (EXPECTED_BLOCKS if sys.version_info >= (3, 13) else EXPECTED_BLOCKS - 1)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== '/srv/app'" in s)
        mutated = source.replace("== '/srv/app'", "== '/srv/'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
