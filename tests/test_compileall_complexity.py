"""Tests for docs/stdlib/compileall.md.

The page prices the module as a walk plus the compilation it triggers: every
directory entry costs a listing slot and a `stat`, and only sources whose
timestamp `.pyc` is stale are compiled. Most rows are settled by observation -
counting `compile_file()` and `py_compile.compile()` calls, the order they
arrive in, and what lands in `__pycache__` - so they need no tolerance. The
memory terms are settled by traced allocation, and the source-size term by a
stopwatch ratio.

Measurement scope:

* The e term: every non-directory entry of a tree, `.txt` files included,
  reaches `compile_file()` exactly once, in sorted order within a directory,
  and nothing under `__pycache__` does. At 10,000 copies of one six-byte
  statement split into 10 or 1,000 files, `compile_file()` runs once per file. That the
  per-directory sort is O(e log e) is read from Lib/compileall.py, not timed.
* The b term: at 20 files, 800-line sources take more than twice as long to
  compile from scratch as 20-line ones. A current tree is rerun with zero
  `py_compile.compile()` calls, and its rerun time grows less than 3x when
  the sources grow 100x (20 to 2,000 lines), so b excludes files whose `.pyc`
  is current. `force=True` compiles every file again.
* Hash invalidation: with `CHECKED_HASH` or `UNCHECKED_HASH`, and with the
  default mode while `SOURCE_DATE_EPOCH` is set, a rerun of an unchanged tree
  calls `py_compile.compile()` once per file.
* The w term: at 20,000 entries, a serial walk of one flat directory peaks
  more than 10x higher than a walk of 200 directories of 100 entries each;
  every entry is a `.txt` file, so nothing is compiled. The m term: one file of
  8,000 lines peaks more than 3x what one of 1,000 lines does, with one
  directory entry either way.
* `workers=2` exhausts the walk before the first result is consumed, observed
  by patching the module's `min` to count the walk's yields at that moment.
  `workers=0` builds the pool with `max_workers=None`, the pool's default
  size, and `workers=-1` raises `ValueError`.
* `compile_file()` calls `py_compile.compile()` once per distinct level in
  `optimize` and never for a name not ending in `.py`, and `hardlink_dupes`
  with one level raises `ValueError`.
* `compile_path()` does not recurse with its default `maxlevels=0`, skips an
  empty `sys.path` entry, and returns `False` without compiling the
  directories after one whose compilation failed.
* `main()` reads every name given with `-i -` before compiling the first, and
  with no names calls `compile_path()`.
* `rx` is observed to leave the walk unchanged: a directory whose path
  matches is still listed, and its files are skipped only in
  `compile_file()`.
* `compile_dir()` returns `False` for a syntax error and `True` for an
  empty directory, a missing one, and a regular file, compiling nothing in
  the last case.
* Every fenced Python block runs in its own subprocess and working directory,
  with `SOURCE_DATE_EPOCH` removed from its environment, and a mutated
  assertion in one of them is asserted to fail. The tests outside
  `test_source_date_epoch_makes_the_default_hash_based` run with it unset.

Not settled here:

* The j·m term of the parallel space bound is summed across worker
  processes, which `tracemalloc` in the parent cannot see; it follows from
  each worker compiling one file at a time in Lib/compileall.py.
* That compiling one source is O(m) time and space is the py_compile page's
  bound, measured in tests/test_py_compile_complexity.py.
* Treating a `stat`, a 12-byte header read and a file write as O(1) is a
  cost-model choice; filesystem latency and caching are not varied.
* Only a small `a` is used for `main()`; how the argument list grows is not
  measured.
"""

from __future__ import annotations

import compileall
import concurrent.futures
import io
import os
import pathlib
import py_compile
import re
import shutil
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import patch

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "compileall.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
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


def build_tree(root: pathlib.Path, files: int, lines_each: int) -> pathlib.Path:
    """A directory of `files` modules, each `lines_each` statements long."""
    root.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"x{index} = {index} + 1" for index in range(lines_each))
    for number in range(files):
        (root / f"m{number}.py").write_text(body, encoding="utf-8")
    return root


def compile_fresh(root: pathlib.Path) -> None:
    """Compile a tree from scratch, discarding any cached bytecode."""
    shutil.rmtree(root / "__pycache__", ignore_errors=True)
    compileall.compile_dir(root, quiet=2, force=True)


@pytest.fixture(autouse=True)
def timestamp_invalidation(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SOURCE_DATE_EPOCH` makes hash-based `.pyc` files the default."""
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)


def counting_compile() -> Any:
    return patch.object(py_compile, "compile", wraps=py_compile.compile)


def counting_compile_file() -> Any:
    return patch.object(compileall, "compile_file", wraps=compileall.compile_file)


class TestTheWalkVisitsEveryEntry:
    """`compile_dir` | O(e log e + b): e counts every entry, not `.py` files.

    Separates the documented walk from one that filters by suffix before it
    stats, and from one that descends into `__pycache__`.
    """

    def test_every_non_directory_entry_reaches_compile_file(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "pkg").mkdir()
        names = ["b.py", "a.txt", "c.py", "pkg/z.py", "pkg/y.dat"]
        for name in names:
            (tmp_path / name).write_text("value = 1\n", encoding="utf-8")
        compileall.compile_dir(tmp_path, quiet=2)

        with counting_compile_file() as compile_file:
            compileall.compile_dir(tmp_path, quiet=2)

        seen = [os.path.relpath(call.args[0], tmp_path) for call in compile_file.call_args_list]
        expected = [
            "a.txt",
            "b.py",
            "c.py",
            os.path.join("pkg", "y.dat"),
            os.path.join("pkg", "z.py"),
        ]
        assert seen == expected, "each listing is sorted and every file is examined"

    @pytest.mark.parametrize("file_count", [10, 1_000])
    def test_per_file_work_at_fixed_source_bytes(
        self, tmp_path: pathlib.Path, file_count: int
    ) -> None:
        """10,000 copies of one statement, split into 10 or 1,000 files."""
        statement = b"x = 1\n"
        body = statement * (10_000 // file_count)
        sources = [tmp_path / f"m{index}.py" for index in range(file_count)]
        for source in sources:
            source.write_bytes(body)

        with counting_compile_file() as compile_file:
            assert compileall.compile_dir(tmp_path, quiet=2, force=True, workers=1)

        assert compile_file.call_count == file_count
        assert {pathlib.Path(call.args[0]) for call in compile_file.call_args_list} == set(sources)

    def test_rx_does_not_prune_the_walk(self, tmp_path: pathlib.Path) -> None:
        excluded = tmp_path / "vendor"
        excluded.mkdir()
        (excluded / "big.py").write_text("value = 1\n", encoding="utf-8")

        with counting_compile_file() as compile_file, counting_compile() as compile:
            compileall.compile_dir(tmp_path, quiet=2, rx=re.compile("vendor"))

        assert compile_file.call_count == 1, "the matched directory was still listed"
        assert compile.call_count == 0, "but its file was not compiled"


class TestOnlyStaleSourcesAreCompiled:
    """b is the source actually compiled; a current `.pyc` costs a header read."""

    @pytest.mark.timing
    def test_source_size_counts_when_compiling(self, tmp_path: pathlib.Path) -> None:
        small = build_tree(tmp_path / "small", files=20, lines_each=20)
        large = build_tree(tmp_path / "large", files=20, lines_each=800)

        small_ns = best_ns(lambda: compile_fresh(small))
        large_ns = best_ns(lambda: compile_fresh(large))

        assert large_ns > small_ns * 2, (
            f"forty times the source in the same file count: {small_ns:.0f}ns vs {large_ns:.0f}ns"
        )

    def test_a_current_tree_compiles_nothing(self, tmp_path: pathlib.Path) -> None:
        tree = build_tree(tmp_path / "tree", files=5, lines_each=5)
        compileall.compile_dir(tree, quiet=2)

        with counting_compile() as compile:
            assert compileall.compile_dir(tree, quiet=2)
        assert compile.call_count == 0

        with counting_compile() as compile:
            assert compileall.compile_dir(tree, quiet=2, force=True)
        assert compile.call_count == 5

    @pytest.mark.timing
    def test_a_current_tree_costs_the_same_whatever_the_source_size(
        self, tmp_path: pathlib.Path
    ) -> None:
        small = build_tree(tmp_path / "small", files=20, lines_each=20)
        large = build_tree(tmp_path / "large", files=20, lines_each=2_000)
        compileall.compile_dir(small, quiet=2)
        compileall.compile_dir(large, quiet=2)

        small_ns = best_ns(lambda: compileall.compile_dir(small, quiet=2))
        large_ns = best_ns(lambda: compileall.compile_dir(large, quiet=2))
        forced_ns = best_ns(lambda: compileall.compile_dir(large, quiet=2, force=True), repeats=3)

        assert large_ns < small_ns * 3, (
            f"100x the source and every .pyc current: {small_ns:.0f}ns vs {large_ns:.0f}ns"
        )
        assert forced_ns > large_ns * 10, (
            f"the forced run is what pays for the source: {large_ns:.0f}ns vs {forced_ns:.0f}ns"
        )

    @pytest.mark.parametrize(
        "mode",
        [
            py_compile.PycInvalidationMode.CHECKED_HASH,
            py_compile.PycInvalidationMode.UNCHECKED_HASH,
        ],
    )
    def test_hash_based_pycs_are_recompiled_every_run(
        self, tmp_path: pathlib.Path, mode: py_compile.PycInvalidationMode
    ) -> None:
        tree = build_tree(tmp_path / "tree", files=3, lines_each=3)
        compileall.compile_dir(tree, quiet=2, invalidation_mode=mode)

        with counting_compile() as compile:
            compileall.compile_dir(tree, quiet=2, invalidation_mode=mode)

        assert compile.call_count == 3

    def test_source_date_epoch_makes_the_default_hash_based(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SOURCE_DATE_EPOCH", "1")
        tree = build_tree(tmp_path / "tree", files=3, lines_each=3)
        compileall.compile_dir(tree, quiet=2)

        with counting_compile() as compile:
            compileall.compile_dir(tree, quiet=2)

        assert compile.call_count == 3


class TestWalkMemory:
    """Serial `compile_dir` | O(w + m): open listings plus one compilation."""

    def test_a_flat_directory_holds_more_than_a_bushy_tree(self, tmp_path: pathlib.Path) -> None:
        """Equal entry counts, so a bound in e alone predicts equal peaks."""

        def build(root: pathlib.Path, directories: int, per_directory: int) -> pathlib.Path:
            for directory in range(directories):
                target = root / f"d{directory:04}" if directories > 1 else root
                target.mkdir(parents=True, exist_ok=True)
                for index in range(per_directory):
                    (target / f"entry{index:05}_with_a_longer_name.txt").touch()
            return root

        flat = build(tmp_path / "flat", 1, 20_000)
        bushy = build(tmp_path / "bushy", 200, 100)

        flat_peak = peak_bytes(lambda: compileall.compile_dir(flat, quiet=2))
        bushy_peak = peak_bytes(lambda: compileall.compile_dir(bushy, quiet=2))

        assert flat_peak > bushy_peak * 10, (
            f"20,000 entries either way: flat {flat_peak} bytes, bushy {bushy_peak} bytes"
        )

    def test_memory_follows_the_largest_file(self, tmp_path: pathlib.Path) -> None:
        """One directory entry either way, so w is constant while m grows 8x."""

        def peak_for(lines: int) -> int:
            directory = build_tree(tmp_path / f"n{lines}", files=1, lines_each=lines)
            return peak_bytes(lambda: compileall.compile_dir(directory, quiet=2, force=True))

        small_peak = peak_for(1_000)
        large_peak = peak_for(8_000)

        assert large_peak > small_peak * 3, (
            f"one entry either way: {small_peak} bytes vs {large_peak} bytes"
        )


class TestParallelCompilation:
    """`compile_dir(..., workers=j)` | O(e + j·m): the parent queues every path."""

    def test_the_parent_exhausts_the_walk_before_the_first_result(
        self, tmp_path: pathlib.Path
    ) -> None:
        tree = build_tree(tmp_path / "parallel", files=12, lines_each=2)
        yielded: list[str] = []
        real_walk = compileall._walk_dir  # pyright: ignore[reportAttributeAccessIssue]

        def recording_walk(*args: Any, **kwargs: Any) -> Iterator[str]:
            for name in real_walk(*args, **kwargs):
                yielded.append(name)
                yield name

        seen_at_first_result: list[int] = []

        def recording_min(results: Any, **kwargs: Any) -> Any:
            seen_at_first_result.append(len(yielded))
            return min(results, **kwargs)

        with (
            patch.object(compileall, "_walk_dir", recording_walk),
            patch.object(compileall, "min", recording_min, create=True),
        ):
            assert compileall.compile_dir(tree, quiet=2, workers=2) is True

        assert seen_at_first_result == [12]
        assert len(list((tree / "__pycache__").glob("*.pyc"))) == 12

    def test_workers_zero_lets_the_pool_choose_its_size(self, tmp_path: pathlib.Path) -> None:
        tree = build_tree(tmp_path / "auto", files=4, lines_each=2)

        with patch.object(
            concurrent.futures, "ProcessPoolExecutor", wraps=concurrent.futures.ProcessPoolExecutor
        ) as pool:
            assert compileall.compile_dir(tree, quiet=2, workers=0) is True

        assert pool.call_args.kwargs["max_workers"] is None

    def test_negative_workers_is_rejected(self, tmp_path: pathlib.Path) -> None:
        tree = build_tree(tmp_path / "bad_workers", files=1, lines_each=1)
        with pytest.raises(ValueError, match="workers"):
            compileall.compile_dir(tree, quiet=2, workers=-1)


class TestCompileFile:
    """`compile_file` | O(m): once per optimization level, O(1) for non-`.py`."""

    def test_one_compile_per_optimization_level(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "module.py"
        source.write_text("value = 1\n", encoding="utf-8")

        levels: Any = [2, 0, 1, 0]  # typeshed says int; a list of levels is documented
        with counting_compile() as compile:
            assert compileall.compile_file(source, quiet=2, optimize=levels)

        assert sorted(call.kwargs["optimize"] for call in compile.call_args_list) == [0, 1, 2]

    def test_a_non_python_name_is_not_compiled(self, tmp_path: pathlib.Path) -> None:
        data = tmp_path / "data.txt"
        data.write_text("def (\n", encoding="utf-8")

        with counting_compile() as compile:
            assert compileall.compile_file(data, quiet=2) is True

        assert compile.call_count == 0

    def test_hardlink_dupes_needs_two_levels(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "module.py"
        source.write_text("value = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="optimization level"):
            compileall.compile_file(source, quiet=2, hardlink_dupes=True)


class TestCompilePath:
    """`compile_path` | O(e log e + b): no recursion, stops at a failure."""

    def test_it_does_not_recurse_and_skips_the_current_directory(
        self, tmp_path: pathlib.Path
    ) -> None:
        top = build_tree(tmp_path / "top", files=1, lines_each=1)
        build_tree(top / "sub", files=1, lines_each=1)

        with patch.object(sys, "path", ["", str(top)]), counting_compile_file() as compile_file:
            assert compileall.compile_path(quiet=2) is True

        assert [pathlib.Path(call.args[0]) for call in compile_file.call_args_list] == [
            top / "m0.py"
        ]

    def test_it_stops_at_the_first_failing_directory(self, tmp_path: pathlib.Path) -> None:
        first = tmp_path / "first"
        first.mkdir()
        (first / "broken.py").write_text("def (\n", encoding="utf-8")
        second = build_tree(tmp_path / "second", files=1, lines_each=1)

        with patch.object(sys, "path", [str(first), str(second)]):
            assert compileall.compile_path(quiet=2) is False

        assert not (second / "__pycache__").exists()


class TestMain:
    """`main()` | O(a + e log e + b): every name is held before compiling."""

    def test_names_from_stdin_are_all_read_before_the_first_compile(
        self, tmp_path: pathlib.Path
    ) -> None:
        sources = [tmp_path / f"m{index}.py" for index in range(5)]
        for source in sources:
            source.write_text("value = 1\n", encoding="utf-8")

        class CountingStdin(io.StringIO):
            taken = 0

            def __iter__(self) -> CountingStdin:
                return self

            def __next__(self) -> str:
                line = self.readline()
                if not line:
                    raise StopIteration
                self.taken += 1
                return line

        stdin = CountingStdin("".join(f"{source}\n" for source in sources))
        taken_at_compile: list[int] = []
        real_compile_file = compileall.compile_file

        def recording(*args: Any, **kwargs: Any) -> bool:
            taken_at_compile.append(stdin.taken)
            return real_compile_file(*args, **kwargs)

        with (
            patch.object(sys, "argv", ["compileall", "-q", "-i", "-"]),
            patch.object(sys, "stdin", stdin),
            patch.object(compileall, "compile_file", recording),
        ):
            assert compileall.main() is True  # pyright: ignore[reportAttributeAccessIssue]

        assert taken_at_compile == [5] * 5

    def test_no_names_runs_compile_path(self) -> None:
        with (
            patch.object(sys, "argv", ["compileall", "-q"]),
            patch.object(compileall, "compile_path", return_value=True) as compile_path,
        ):
            assert compileall.main() is True  # pyright: ignore[reportAttributeAccessIssue]
        compile_path.assert_called_once()


class TestReturnValueOnlyReportsCompilationFailures:
    """The warning: a directory it could not read is reported as success."""

    def test_a_syntax_error_returns_false(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "broken.py").write_text("def (\n", encoding="utf-8")
        assert compileall.compile_dir(tmp_path, quiet=2) is False

    def test_an_empty_directory_returns_true(self, tmp_path: pathlib.Path) -> None:
        assert compileall.compile_dir(tmp_path, quiet=2) is True

    def test_a_missing_directory_returns_true(self, tmp_path: pathlib.Path) -> None:
        assert compileall.compile_dir(tmp_path / "nowhere", quiet=2) is True

    def test_a_file_instead_of_a_directory_returns_true(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "single.py"
        source.write_text("value = 1\n", encoding="utf-8")
        assert compileall.compile_dir(source, quiet=2) is True
        assert not (tmp_path / "__pycache__").exists(), "and it compiled nothing"


def _blocks() -> list[tuple[int, str]]:
    """Every fenced Python block on the page, with its 1-based fence line."""
    blocks: list[tuple[int, str]] = []
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip() == "```python":
            start = index + 1
            end = start
            while lines[end].strip() != "```":
                end += 1
            blocks.append((index + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return blocks


def _run_block(source: str, workdir: pathlib.Path) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "SOURCE_DATE_EPOCH"}
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=workdir,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


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
        line, source = next(
            (n, s) for n, s in _blocks() if "invalidation_mode=checked) == 1  #" in s
        )
        mutated = source.replace(
            "invalidation_mode=checked) == 1  #", "invalidation_mode=checked) == 0  #", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
