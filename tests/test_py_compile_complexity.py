"""Tests for docs/stdlib/py_compile.md.

The page prices one `compile()` call at O(n) time and space in the source
bytes, with nothing kept between calls. Space is settled by traced
allocation across source sizes, in a band that separates linear from
constant and quadratic growth with room to spare; that nothing is
cached and that only the hash modes hash are settled by counting calls at
the loader boundary; time is a ratio across sizes. Return values, error
reporting and the invalidation modes are settled by observation, the modes
by re-importing an edited module.

Measurement scope:

* `compile()` peak traced allocation over sources of 2,000, 8,000 and 32,000
  one-assignment lines (about 32 KB to 590 KB) grows between 3x and 6x per 4x
  step, so it is linear in n; a warm-up compile runs first. In a timing test
  the fastest of five compiles of 500 and 8,000 lines differ by more than 4x
  and less than 64x for 16x the source, which excludes both a constant and a
  quadratic cost. Only one statement shape is measured.
* Two `compile()` calls on an unchanged file call
  `SourceFileLoader.source_to_code` twice: nothing is cached. TIMESTAMP calls
  `importlib.util.source_hash` zero times and both hash modes once. A timing
  test bounds CHECKED_HASH under 1.5x TIMESTAMP on a 4,000-line source, so
  the hash is not a pass comparable to compiling.
* The return value is the `__pycache__` path from
  `importlib.util.cache_from_source`, or `cfile` exactly as passed, and `None`
  on a syntax error. `doraise=True` raises `PyCompileError` at `quiet` 0 and
  1 and returns `None` with empty stderr at `quiet=2`; without `doraise`,
  `quiet` 0 and 1 write the same message to stderr. A missing source raises
  `FileNotFoundError` with and without `doraise` and at `quiet=2`, and a
  symlink or a directory as `cfile` raises `FileExistsError` with
  `doraise=True, quiet=2`.
* The header flags word is 0, 3 and 1 for TIMESTAMP, CHECKED_HASH and
  UNCHECKED_HASH. With `SOURCE_DATE_EPOCH` unset or empty `compile()` writes
  a TIMESTAMP header, and with a non-empty value a CHECKED_HASH one.
* After an in-place edit that keeps the source's size and mtime, re-importing
  a TIMESTAMP module serves the old value and a CHECKED_HASH module the new
  one. After an edit that changes the size, an UNCHECKED_HASH module still
  serves the old value.
* `python -m py_compile` with a broken file between two good ones exits 1,
  writes the `SyntaxError` to stderr and leaves only the first file compiled;
  `-` reads the file names from stdin.
* Every fenced Python block runs in its own subprocess and working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That `main()` holds only one file's O(n) at a time, besides its list of
  names, is read from Lib/py_compile.py, where each name is a separate
  `compile()` call; the peak is not measured across files.
* `PyCompileError`'s O(e) is read from its constructor, which formats the
  message once with `traceback.format_exception_only`; e is defined as that
  message's length, so there is nothing further to vary.
* Filesystem costs (`stat`, `makedirs`, the atomic rename) are priced at
  O(1) by the page's cost model and are not varied.
* Import-time cost of each invalidation mode is outside this module and is
  not measured; only the behaviour of the check is.
* Lib/py_compile.py is unchanged in behaviour from 3.10 through 3.14, so no
  test is version-gated.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.machinery
import importlib.util
import io
import os
import pathlib
import py_compile
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "py_compile.md"
EXPECTED_BLOCKS = 5

MODES = py_compile.PycInvalidationMode


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def source_of(directory: pathlib.Path, name: str, lines: int) -> pathlib.Path:
    path = directory / name
    path.write_text("\n".join(f"y{index} = {index} * 2" for index in range(lines)) + "\n")
    return path


def broken_source(directory: pathlib.Path) -> pathlib.Path:
    path = directory / "broken.py"
    path.write_text("def (\n")
    return path


def header_flags(pyc: str | None) -> int:
    assert pyc is not None, "compile() returned None"
    return int.from_bytes(pathlib.Path(pyc).read_bytes()[4:8], "little")


class TestCompileIsLinear:
    """`compile()`: O(n) time and O(n) space in the source bytes."""

    def test_peak_memory_grows_with_the_source(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "out.pyc"
        sizes = (2_000, 8_000, 32_000)
        sources = [source_of(tmp_path, f"m{lines}.py", lines) for lines in sizes]
        py_compile.compile(str(sources[0]), cfile=str(target), doraise=True)

        peaks = [
            peak_bytes(lambda s=s: py_compile.compile(str(s), cfile=str(target), doraise=True))
            for s in sources
        ]

        for small, large in zip(peaks, peaks[1:], strict=False):
            assert 3 < large / small < 6, f"4x the source should be ~4x the peak: {peaks}"

    @pytest.mark.timing
    def test_time_grows_with_the_source(self, tmp_path: pathlib.Path) -> None:
        small = source_of(tmp_path, "small.py", 500)
        large = source_of(tmp_path, "large.py", 8_000)
        target = str(tmp_path / "out.pyc")

        small_ns = best_ns(lambda: py_compile.compile(str(small), cfile=target, doraise=True))
        large_ns = best_ns(lambda: py_compile.compile(str(large), cfile=target, doraise=True))

        ratio = large_ns / small_ns
        assert 4 < ratio < 64, f"16x the source: {small_ns:.0f}ns vs {large_ns:.0f}ns"


class TestNothingIsCached:
    """Each call compiles again; only the hash modes hash the source."""

    def _counting(self, monkeypatch: pytest.MonkeyPatch, owner: Any, name: str) -> list[int]:
        calls: list[int] = []
        original = getattr(owner, name)

        def counted(*args: Any, **kwargs: Any) -> Any:
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(owner, name, counted)
        return calls

    def test_compiling_twice_compiles_twice(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = source_of(tmp_path, "module.py", 3)
        calls = self._counting(monkeypatch, importlib.machinery.SourceFileLoader, "source_to_code")

        py_compile.compile(str(module), doraise=True)
        py_compile.compile(str(module), doraise=True)

        assert len(calls) == 2

    def test_only_the_hash_modes_hash_the_source(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = source_of(tmp_path, "module.py", 3)
        calls = self._counting(monkeypatch, importlib.util, "source_hash")
        counts = {}
        for mode in MODES:
            before = len(calls)
            py_compile.compile(
                str(module), cfile=str(tmp_path / f"{mode.name}.pyc"), invalidation_mode=mode
            )
            counts[mode.name] = len(calls) - before

        assert counts == {"TIMESTAMP": 0, "CHECKED_HASH": 1, "UNCHECKED_HASH": 1}

    @pytest.mark.timing
    def test_hashing_is_cheap_next_to_compiling(self, tmp_path: pathlib.Path) -> None:
        module = source_of(tmp_path, "big.py", 4_000)

        def run(mode: py_compile.PycInvalidationMode) -> float:
            target = str(tmp_path / f"{mode.name}.pyc")
            return best_ns(
                lambda: py_compile.compile(str(module), cfile=target, invalidation_mode=mode)
            )

        timestamp = run(MODES.TIMESTAMP)
        hashed = run(MODES.CHECKED_HASH)

        assert hashed < timestamp * 1.5, f"timestamp {timestamp:.0f}ns, hashed {hashed:.0f}ns"


class TestReturnValue:
    """The path written, or `None` on a compilation error."""

    def test_the_default_is_the_pep_3147_path(self, tmp_path: pathlib.Path) -> None:
        module = source_of(tmp_path, "module.py", 2)

        written = py_compile.compile(str(module))

        assert written is not None
        assert written == importlib.util.cache_from_source(str(module))
        assert pathlib.Path(written).is_file()

    def test_cfile_is_returned_exactly_as_passed(self, tmp_path: pathlib.Path) -> None:
        module = source_of(tmp_path, "module.py", 2)
        target = str(tmp_path / "explicit.pyc")

        assert py_compile.compile(str(module), cfile=target) is target
        assert pathlib.Path(target).is_file()

    def test_a_compilation_error_returns_none(self, tmp_path: pathlib.Path) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            assert py_compile.compile(str(broken_source(tmp_path))) is None


class TestReportingFailures:
    """`doraise` raises below quiet=2; quiet=2 swallows; I/O errors always raise."""

    def test_doraise_raises_at_quiet_zero_and_one(self, tmp_path: pathlib.Path) -> None:
        broken = broken_source(tmp_path)
        for quiet in (0, 1):
            with pytest.raises(py_compile.PyCompileError) as caught:
                py_compile.compile(str(broken), doraise=True, quiet=quiet)
            assert caught.value.file == str(broken)
            assert caught.value.exc_type_name == "SyntaxError"
            assert "SyntaxError" in caught.value.msg

    def test_quiet_two_overrides_doraise(self, tmp_path: pathlib.Path) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = py_compile.compile(str(broken_source(tmp_path)), doraise=True, quiet=2)

        assert result is None
        assert stderr.getvalue() == ""

    def test_quiet_zero_and_one_write_the_same_message(self, tmp_path: pathlib.Path) -> None:
        broken = broken_source(tmp_path)
        written = []
        for quiet in (0, 1):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                assert py_compile.compile(str(broken), quiet=quiet) is None
            written.append(stderr.getvalue())

        assert written[0] == written[1]
        assert "SyntaxError" in written[0]

    def test_a_missing_source_raises_whatever_the_flags(self, tmp_path: pathlib.Path) -> None:
        absent = str(tmp_path / "absent.py")
        flag_sets: list[dict[str, Any]] = [
            {},
            {"doraise": True},
            {"quiet": 2},
            {"doraise": True, "quiet": 2},
        ]
        for kwargs in flag_sets:
            with pytest.raises(FileNotFoundError):
                py_compile.compile(absent, **kwargs)

    def test_a_directory_cfile_raises(self, tmp_path: pathlib.Path) -> None:
        module = source_of(tmp_path, "module.py", 2)
        directory = tmp_path / "dir.pyc"
        directory.mkdir()

        with pytest.raises(FileExistsError):
            py_compile.compile(str(module), cfile=str(directory), doraise=True, quiet=2)

    def test_a_symlink_cfile_raises(self, tmp_path: pathlib.Path) -> None:
        module = source_of(tmp_path, "module.py", 2)
        real = tmp_path / "real.pyc"
        real.write_bytes(b"")
        link = tmp_path / "link.pyc"
        try:
            link.symlink_to(real)
        except OSError as error:
            pytest.skip(f"missing symlinks: {error}")

        with pytest.raises(FileExistsError):
            py_compile.compile(str(module), cfile=str(link), doraise=True, quiet=2)
        assert real.read_bytes() == b"", "the link target is left alone"


class TestInvalidationModes:
    """TIMESTAMP misses a same-size, same-mtime edit; the hash modes record a hash."""

    def _import_after_edit(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        mode: py_compile.PycInvalidationMode,
        new_text: str,
        keep_stat: bool,
    ) -> tuple[str, str]:
        """Compile, import, edit the source, import again."""
        name = f"probe_{mode.name.lower()}"
        monkeypatch.syspath_prepend(str(tmp_path))
        module = tmp_path / f"{name}.py"
        module.write_text("VALUE = 'first'\n")
        py_compile.compile(str(module), invalidation_mode=mode, doraise=True)
        try:
            before = importlib.import_module(name).VALUE
            stat = module.stat()
            module.write_text(new_text)
            if keep_stat:
                os.utime(module, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            del sys.modules[name]
            importlib.invalidate_caches()
            after = importlib.import_module(name).VALUE
        finally:
            sys.modules.pop(name, None)
        return before, after

    def test_timestamp_serves_stale_bytecode(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before, after = self._import_after_edit(
            tmp_path, monkeypatch, MODES.TIMESTAMP, "VALUE = 'secnd'\n", keep_stat=True
        )
        assert (before, after) == ("first", "first")

    def test_checked_hash_notices(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before, after = self._import_after_edit(
            tmp_path, monkeypatch, MODES.CHECKED_HASH, "VALUE = 'secnd'\n", keep_stat=True
        )
        assert (before, after) == ("first", "secnd")

    def test_unchecked_hash_never_notices(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before, after = self._import_after_edit(
            tmp_path,
            monkeypatch,
            MODES.UNCHECKED_HASH,
            "VALUE = 'a longer value'\n",
            keep_stat=False,
        )
        assert (before, after) == ("first", "first")

    def test_the_mode_is_in_the_header_flags(self, tmp_path: pathlib.Path) -> None:
        module = source_of(tmp_path, "module.py", 2)
        flags = {}
        for mode in MODES:
            target = tmp_path / f"{mode.name}.pyc"
            py_compile.compile(str(module), cfile=str(target), invalidation_mode=mode)
            flags[mode.name] = header_flags(str(target))

        assert flags == {"TIMESTAMP": 0, "CHECKED_HASH": 3, "UNCHECKED_HASH": 1}

    def test_the_default_follows_source_date_epoch(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = source_of(tmp_path, "module.py", 2)

        monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
        assert header_flags(py_compile.compile(str(module))) == 0

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "")
        assert header_flags(py_compile.compile(str(module))) == 0

        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
        assert header_flags(py_compile.compile(str(module))) == 3


class TestCommandLine:
    """`python -m py_compile` stops at the first failure; `-` reads stdin."""

    def _run(self, args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "py_compile", *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def test_it_stops_at_the_first_failure(self, tmp_path: pathlib.Path) -> None:
        first = source_of(tmp_path, "first.py", 2)
        broken = broken_source(tmp_path)
        later = source_of(tmp_path, "later.py", 2)

        result = self._run([str(first), str(broken), str(later)])

        assert result.returncode == 1
        assert "SyntaxError" in result.stderr
        assert pathlib.Path(importlib.util.cache_from_source(str(first))).is_file()
        assert not pathlib.Path(importlib.util.cache_from_source(str(later))).exists()

    def test_a_dash_reads_names_from_stdin(self, tmp_path: pathlib.Path) -> None:
        names = [source_of(tmp_path, f"m{index}.py", 2) for index in range(3)]

        result = self._run(["-"], stdin="".join(f"{name}\n" for name in names))

        assert result.returncode == 0, result.stderr
        for name in names:
            assert pathlib.Path(importlib.util.cache_from_source(str(name))).is_file()


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
    env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=env,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and directory and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert flags(target) == expected" in s)
        mutated = source.replace("(modes.CHECKED_HASH, 3)", "(modes.CHECKED_HASH, 1)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
