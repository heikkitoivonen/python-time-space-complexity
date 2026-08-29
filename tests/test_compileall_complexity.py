"""Tests to verify documented behaviour of the compileall module.

docs/stdlib/compileall.md had no test file, two code blocks that could not
run, and a complexity table priced only in file count.

The interesting finding is not a bound. `compile_dir()` returns `False` only
when a file fails to compile; a directory it could not read at all, or a path
that is a file rather than a directory, both come back `True`. The most
likely mistake - a typo in the path - is reported as success.

Everything here runs against trees built in `tmp_path`, so nothing touches
the repository or writes `__pycache__` into it. Single-file compilation lives
in tests/test_py_compile_complexity.py.
"""

import compileall
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def best_time(func: Callable[[], Any], repeats: int = 3) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def build_tree(root: Path, files: int, lines_each: int) -> Path:
    """A directory of `files` modules, each `lines_each` statements long."""
    root.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"x{index} = {index} + 1" for index in range(lines_each))
    for number in range(files):
        (root / f"m{number}.py").write_text(body, encoding="utf-8")
    return root


def compile_fresh(root: Path) -> None:
    """Compile a tree from scratch, discarding any cached bytecode."""
    shutil.rmtree(root / "__pycache__", ignore_errors=True)
    compileall.compile_dir(root, quiet=2, force=True)


class TestReturnValueOnlyReportsCompilationFailures:
    """The gotcha the page now documents.

    `compile_dir` walks with `os.listdir` inside a try/except that swallows
    OSError and continues with an empty file list, so `success` is never set
    to False. Only a file that fails to compile flips it.
    """

    def test_valid_tree_returns_true(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path / "good", files=2, lines_each=2)
        assert compileall.compile_dir(tree, quiet=2) is True

    def test_a_syntax_error_returns_false(self, tmp_path: Path) -> None:
        tree = tmp_path / "bad"
        tree.mkdir()
        (tree / "broken.py").write_text("def (\n", encoding="utf-8")
        assert compileall.compile_dir(tree, quiet=2) is False

    def test_a_missing_directory_returns_true(self, tmp_path: Path) -> None:
        """The false positive: nothing was compiled, and it says success."""
        assert compileall.compile_dir(tmp_path / "nowhere", quiet=2) is True

    def test_a_file_instead_of_a_directory_returns_true(self, tmp_path: Path) -> None:
        source = tmp_path / "single.py"
        source.write_text("value = 1\n", encoding="utf-8")
        assert compileall.compile_dir(source, quiet=2) is True
        assert not (tmp_path / "__pycache__").exists(), "and it compiled nothing"

    def test_an_empty_directory_returns_true(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        assert compileall.compile_dir(empty, quiet=2) is True

    def test_guarding_the_path_distinguishes_the_two(self, tmp_path: Path) -> None:
        """What the page recommends instead of trusting the result."""

        def compile_tree(path: Path) -> bool:
            if not path.is_dir():
                raise NotADirectoryError(path)
            return compileall.compile_dir(path, quiet=2)

        with pytest.raises(NotADirectoryError):
            compile_tree(tmp_path / "nowhere")


class TestCompileDirComplexity:
    """The table's O(n + total bytes)."""

    def test_scales_with_the_file_count(self, tmp_path: Path) -> None:
        few = build_tree(tmp_path / "few", files=50, lines_each=20)
        many = build_tree(tmp_path / "many", files=400, lines_each=20)

        few_time = best_time(lambda: compile_fresh(few))
        many_time = best_time(lambda: compile_fresh(many))

        assert many_time > few_time * 3, (
            f"eight times the files should cost visibly more: "
            f"50 {few_time:.2e}s 400 {many_time:.2e}s"
        )

    def test_per_file_overhead_dominates_for_small_files(self, tmp_path: Path) -> None:
        """Same total source, split two ways.

        This is why the table is not priced in bytes alone: 200 ten-line
        files cost several times what 10 two-hundred-line files do.
        """
        many_small = build_tree(tmp_path / "many_small", files=200, lines_each=10)
        few_large = build_tree(tmp_path / "few_large", files=10, lines_each=200)

        many_time = best_time(lambda: compile_fresh(many_small))
        few_time = best_time(lambda: compile_fresh(few_large))

        assert many_time > few_time * 3, (
            f"the same 2000 lines, and the file count is what costs: "
            f"200 files {many_time:.2e}s, 10 files {few_time:.2e}s"
        )

    def test_file_size_still_counts(self, tmp_path: Path) -> None:
        """The other term: at a fixed file count, bigger files cost more."""
        small = build_tree(tmp_path / "small_files", files=20, lines_each=20)
        large = build_tree(tmp_path / "large_files", files=20, lines_each=800)

        small_time = best_time(lambda: compile_fresh(small))
        large_time = best_time(lambda: compile_fresh(large))

        assert large_time > small_time * 2, (
            f"forty times the source in the same file count: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_force_controls_whether_cached_bytecode_is_reused(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path / "cached", files=100, lines_each=40)
        compileall.compile_dir(tree, quiet=2)  # warm the cache

        cached_time = best_time(lambda: compileall.compile_dir(tree, quiet=2))
        forced_time = best_time(lambda: compileall.compile_dir(tree, quiet=2, force=True))

        assert forced_time > cached_time * 2, (
            f"force=True recompiles everything: cached {cached_time:.2e}s forced {forced_time:.2e}s"
        )

    def test_it_writes_the_bytecode_it_claims_to(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path / "written", files=3, lines_each=2)
        compileall.compile_dir(tree, quiet=2)

        cache = tree / "__pycache__"
        assert cache.is_dir()
        assert len(list(cache.glob("*.pyc"))) == 3


class TestParallelCompilation:
    """`workers` is not mentioned anywhere on the page except the table note."""

    def test_workers_is_accepted(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path / "parallel", files=20, lines_each=20)
        assert compileall.compile_dir(tree, quiet=2, workers=2) is True

    def test_workers_zero_means_one_per_cpu(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path / "auto", files=20, lines_each=20)
        assert compileall.compile_dir(tree, quiet=2, workers=0) is True

    def test_negative_workers_is_rejected(self, tmp_path: Path) -> None:
        tree = build_tree(tmp_path / "bad_workers", files=1, lines_each=1)
        with pytest.raises(ValueError, match="workers"):
            compileall.compile_dir(tree, quiet=2, workers=-1)
