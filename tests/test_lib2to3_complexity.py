"""Tests for docs/stdlib/lib2to3.md.

The page prices the module a file at a time: a file is parsed into a tree in
time and space linear in its tokens, the fixers walk that tree at a cost of
its tokens times its depth, and the match loop is quadratic in the candidate
nodes the busiest fixer is handed. Linear growth on flat source, and the depth factor on
nested source, are settled by timing and traced allocation over sizes six or
eight times apart; the quadratic term is settled by observation, counting the
list elements the match loop shifts. Behavioural rows - what is written, what
is skipped, what raises, what the command returns - are asserted directly on
files in a temporary directory.

`lib2to3` exists on Python 3.10 to 3.12 and is gone from 3.13, so every
runtime test is skipped on 3.13 and later; there, only the availability
boundary and the page's block count are checked. The package is the same on
3.10, 3.11 and 3.12 (`Lib/lib2to3` at v3.10.19, v3.11.14 and v3.12.12) apart
from the import warning, which is asserted on each side of the 3.11 boundary;
the other differences, in a `tok_name` loop, a deleted loop variable and a
dead `pass`, do not change behaviour.

Measurement scope:

* `Driver.parse_string()` and `RefactoringTool.refactor_string()` with every
  default fixer, over 500 and 4,000 copies of one assignment line that no
  fixer matches, with the garbage collector paused: eight times the source
  costs under 24 times the time for each, where quadratic parsing would cost
  64 times; that is consistent with linear growth for this shape, and does
  not exclude a term just below quadratic. The traced peak of `refactor_string()` over the same two sizes
  grows between 4 and 16 times.
* Depth is varied with `x = ` followed by 100 and 600 unary `+` operators,
  a tree as deep as it is long: exhausting `pre_order()` and `leaves()` and
  running `refactor_string()` under `fix_print`, which has no candidate
  there, cost over 12 times as much for six times the tokens, where O(n)
  predicts 6 and O(n·d) 36. Under the default recursion limit of 1,000,
  1,500 operators parse, and `refactor_string()` on them raises
  `RecursionError`. `str(tree)` is O(n·d) by the same
  per-level recursion in `Node.__str__`, read from Lib/lib2to3/pytree.py and
  not timed: its per-level work is a string join, which a depth that stays
  under the recursion limit does not separate from linear.
* The match loop is observed by wrapping each candidate list the bottom
  matcher returns in a list subclass that counts the elements every
  `remove()` shifts. 100 and 400 `print` statements under `fix_print` shift
  4,950 and 79,800 elements, m(m - 1) / 2, as do 100 and 400 `print()`
  calls that need no change and 100 and 400 `has_key` calls under
  `fix_has_key`; a source with no candidate shifts none. The cost of each
  shift is not timed.
* `RefactoringTool()` builds one fixer object per name it is given, and
  leaves an explicit-only fixer (`fix_idioms`) out unless `explicit` names it.
  A dotted name whose module has no `Fix...` class raises `FixerError`.
  `get_fixers_from_package('lib2to3.fixes')` returns 52 dotted names.
* `refactor_string()` is asserted to rewrite `print` and `has_key` while
  keeping a comment, to return a tree whose `str()` is a source with comments
  and irregular spacing byte for byte when nothing changes, to raise
  `ParseError` for a `match` statement and for `print()` with a keyword
  argument, and to accept that call with the `print_function` option.
  Walrus and positional-only syntax parse; a relaxed decorator does not.
* `refactor_file()` returns `None`, leaves the file alone without
  `write=True`, and leaves a file with nothing to change alone with it.
  `refactor_dir()` refactors `.py` files in nested directories, skips files
  and directories whose names start with `.`, and records in `files` only the
  file that needed changes; `wrote` is set once a file is written.
  `refactor()` takes a file and a directory in one list. Over ten files of
  2,000 `print` statements `refactor_dir()` peaks under four times its peak
  over one; holding every tree would be ten times. Collection of the trees'
  reference cycles is left to the garbage collector, which is not paused.
  `refactor_docstring()` rewrites the `>>>` lines and leaves Python 2 prose
  around them alone. `refactor_tree()` rewrites the tree in place and returns
  whether it changed.
* `Base.pre_order()`, `post_order()` and `leaves()` are generators: taking
  the first node from a 4,000-line tree's `pre_order()` is asserted to visit
  one node, and each of the three returns a generator object.
* The command is run as `python -m lib2to3`: it prints a diff and writes
  nothing by default; `-w` writes and keeps `.bak`, `-n` keeps none; `-f`
  runs only the named fixer and `-x` every default fixer but that one;
  `-o` with `-W -n` writes every file, changed or not, under the output
  directory; `-d` rewrites only the doctests; `-l` lists `print` and
  `has_key`; `-j 2` converts two files. It returns 0, and 1 when a file
  does not parse or does not exist. `lib2to3.main.main()` returns the same
  status in-process.
* Importing warns with `DeprecationWarning` on 3.11 and 3.12, and with
  `PendingDeprecationWarning` on 3.10.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail. The page's bash
  block is not run: its `2to3` lines are covered by the command-line tests
  above through `python -m lib2to3`, which is the same `main()`, and whether
  a `2to3` script is installed depends on the distribution.

Not settled here:

* The module is removed from Python 3.13, so no claim on the page is checked
  on 3.13 or 3.14; the removal itself is the availability test. That the
  `2to3` command goes with it is from the official 3.13 What's New.
* That `-j N` uses N processes is read from `MultiprocessRefactoringTool` in
  Lib/lib2to3/refactor.py; the test shows only that `-j 2` converts both
  files. That the printed diff is `difflib.unified_diff` over the file's
  lines is read from `diff_texts()` in Lib/lib2to3/main.py; its cost is
  priced on docs/stdlib/difflib.md. That the command returns 1 when a file
  cannot be written is read from `main()`, which returns whether any error
  was logged.
* Treating one fixer's work on one candidate as O(1) is a cost-model
  assumption; a fixer whose pattern or transform does more is outside the
  bounds. The `O(f)` constructor is observed as one fixer object per name,
  not timed, and fixer counts between one and the default set are not
  varied in any timing.
* The O(d) space of the traversal generators is read from their recursive
  `yield from` in Lib/lib2to3/pytree.py and is not measured. The O(t) term of
  `refactor_dir()` and `refactor()` space - `os.walk`'s listings and the
  names kept in `files` - is read from Lib/lib2to3/refactor.py; the tests
  show the names are kept, not how their memory grows.
* Source shapes other than repeated simple lines and one unary chain, files
  with many fixers
  matching at once, non-UTF-8 encodings and `doctests_only=True` on
  `refactor_file()` are not varied.
* `refactor.MultiprocessingUnsupported`, `refactor_stdin()`, `summarize()`,
  `fixer_base`, `fixer_util` and the pattern compiler are not on the page:
  the official documentation names no API but the module and the command.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any, ClassVar

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "lib2to3.md"
EXPECTED_BLOCKS = 5

refactor: Any = None
l2t_main: Any = None
pygram: Any = None
pytree: Any = None
driver: Any = None
ParseError: Any = None
if sys.version_info < (3, 13):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        refactor = importlib.import_module("lib2to3.refactor")
        l2t_main = importlib.import_module("lib2to3.main")
        pygram = importlib.import_module("lib2to3.pygram")
        pytree = importlib.import_module("lib2to3.pytree")
        driver = importlib.import_module("lib2to3.pgen2.driver")
        ParseError = importlib.import_module("lib2to3.pgen2.parse").ParseError

REQUIRES_LIB2TO3 = pytest.mark.skipif(
    refactor is None, reason="version: lib2to3 was removed in Python 3.13"
)
FIXES = "lib2to3.fixes"
NO_MATCH_LINE = "value = compute(alpha, beta) + 1  # note\n"


def best_s(func: Callable[[], Any], repeats: int = 3) -> float:
    """Fastest of `repeats` runs, in seconds, with the garbage collector paused."""
    best: float | None = None
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            best = elapsed if best is None else min(best, elapsed)
    finally:
        if enabled:
            gc.enable()
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


def tool(*fixers: str, **kwargs: Any) -> Any:
    names = [f"{FIXES}.fix_{name}" for name in fixers]
    return refactor.RefactoringTool(names, **kwargs)


def default_tool() -> Any:
    return refactor.RefactoringTool(refactor.get_fixers_from_package(FIXES))


def run_2to3(*args: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lib2to3", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestAvailability:
    """The page's scope: present on 3.10 to 3.12, removed from 3.13."""

    def test_the_module_exists_only_before_313(self) -> None:
        found = importlib.util.find_spec("lib2to3") is not None

        assert found == (sys.version_info < (3, 13))

    @REQUIRES_LIB2TO3
    def test_importing_warns(self) -> None:
        category = (
            "DeprecationWarning" if sys.version_info >= (3, 11) else "PendingDeprecationWarning"
        )
        result = subprocess.run(
            [sys.executable, "-W", f"error::{category}", "-c", "import lib2to3"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        assert result.returncode != 0
        assert category in result.stderr


@REQUIRES_LIB2TO3
class TestParsingIsLinear:
    """`Driver.parse_string(text)` | O(n) | O(n) and `refactor_string(data,
    name)` | O(n·d + m²) | O(n): with no candidates and a shallow tree, both
    follow the tokens. Eight times the source would cost 64 times if either were
    quadratic."""

    SMALL: ClassVar[str] = NO_MATCH_LINE * 500
    LARGE: ClassVar[str] = NO_MATCH_LINE * 4_000

    @pytest.mark.timing
    def test_parsing_alone(self) -> None:
        parser = driver.Driver(pygram.python_grammar, convert=pytree.convert)

        small = best_s(lambda: parser.parse_string(self.SMALL))
        large = best_s(lambda: parser.parse_string(self.LARGE))

        ratio = large / small
        assert ratio < 24, f"8x the source cost x{ratio:.1f}; linear is x8, quadratic x64"

    @pytest.mark.timing
    def test_refactoring_with_every_default_fixer(self) -> None:
        refactorer = default_tool()

        small = best_s(lambda: refactorer.refactor_string(self.SMALL, "small"))
        large = best_s(lambda: refactorer.refactor_string(self.LARGE, "large"))

        ratio = large / small
        assert ratio < 24, f"8x the source cost x{ratio:.1f}; linear is x8, quadratic x64"

    def test_the_peak_follows_the_source(self) -> None:
        refactorer = default_tool()

        small = peak_bytes(lambda: refactorer.refactor_string(self.SMALL, "small"))
        large = peak_bytes(lambda: refactorer.refactor_string(self.LARGE, "large"))

        assert small * 4 < large < small * 16, (
            f"8x the source peaked at {large} bytes against {small}; O(n) predicts x8"
        )


class ShiftCountingList(list[Any]):
    """A candidate list that counts the elements each `remove()` shifts."""

    shifted: ClassVar[int] = 0

    def remove(self, value: Any) -> None:
        ShiftCountingList.shifted += len(self) - 1 - self.index(value)
        super().remove(value)


@REQUIRES_LIB2TO3
class TestDepthMultipliesTheWalks:
    """`d` multiplies every walk over the tree: traversal and refactoring of
    a tree as deep as it is long grow with the square of its tokens, and deep
    enough nesting raises `RecursionError`."""

    @staticmethod
    def nested(depth: int) -> str:
        return "x = " + "+" * depth + "1\n"

    @pytest.mark.timing
    @pytest.mark.parametrize("walk", ["pre_order", "leaves", "refactor_string"])
    def test_six_times_the_depth_costs_far_more_than_six_times(self, walk: str) -> None:
        refactorer = tool("print")

        def cost(depth: int) -> float:
            source = self.nested(depth)
            if walk == "refactor_string":
                return best_s(lambda: refactorer.refactor_string(source, "s"), repeats=5)
            tree = refactorer.driver.parse_string(source)
            return best_s(lambda: sum(1 for _ in getattr(tree, walk)()), repeats=5)

        ratio = cost(600) / cost(100)
        assert ratio > 12, f"6x the nesting cost x{ratio:.1f}; O(n) is x6, O(n·d) x36"

    def test_deep_nesting_parses_but_does_not_refactor(self) -> None:
        refactorer = tool("print")
        source = self.nested(1_500)
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(1_000)
        try:
            assert refactorer.driver.parse_string(source) is not None
            with pytest.raises(RecursionError):
                refactorer.refactor_string(source, "s")
        finally:
            sys.setrecursionlimit(limit)


@REQUIRES_LIB2TO3
class TestTheMatchLoopIsQuadraticInCandidates:
    """`refactor_string(data, name)` | O(n·d + m²): each candidate the bottom
    matcher hands a fixer is taken off the front of that fixer's list, so m
    candidates shift m(m - 1) / 2 elements. A linear loop would shift none.
    A `print()` call is a candidate for `fix_print` though it needs no change."""

    @staticmethod
    def shifts(refactorer: Any, source: str) -> int:
        run = refactorer.BM.run

        def counted(leaves: Any) -> Any:
            found = run(leaves)
            for fixer in found:
                found[fixer] = ShiftCountingList(found[fixer])
            return found

        refactorer.BM.run = counted
        ShiftCountingList.shifted = 0
        refactorer.refactor_string(source, "shifts")
        return ShiftCountingList.shifted

    @pytest.mark.parametrize(
        ("fixer", "line"),
        [
            ("print", "print 'a'\n"),
            ("print", "print('a')\n"),
            ("has_key", "x = d.has_key(k)\n"),
        ],
        ids=["print-statement", "print-call", "has_key"],
    )
    def test_shifts_grow_with_the_square_of_the_candidates(self, fixer: str, line: str) -> None:
        assert self.shifts(tool(fixer), line * 100) == 100 * 99 // 2
        assert self.shifts(tool(fixer), line * 400) == 400 * 399 // 2

    def test_a_source_without_candidates_shifts_nothing(self) -> None:
        assert self.shifts(tool("print"), NO_MATCH_LINE * 400) == 0


@REQUIRES_LIB2TO3
class TestBuildingATool:
    """`RefactoringTool(fixer_names, options=None, explicit=None)` | O(f) |
    O(f): one fixer object per name, explicit-only fixers left out unless
    named, and `FixerError` for a module without its class."""

    def test_one_fixer_per_name(self) -> None:
        names = ["print", "has_key", "ne"]
        built = tool(*names)

        loaded = {type(fixer).__name__ for fixer in built.pre_order + built.post_order}
        assert loaded == {"FixPrint", "FixHasKey", "FixNe"}

    def test_the_package_lists_every_fixer(self) -> None:
        names = refactor.get_fixers_from_package(FIXES)

        assert len(names) == 52
        assert f"{FIXES}.fix_print" in names
        assert all(name.startswith(f"{FIXES}.fix_") for name in names)

    def test_an_explicit_only_fixer_needs_naming(self) -> None:
        idioms = f"{FIXES}.fix_idioms"
        skipped = refactor.RefactoringTool([idioms])
        named = refactor.RefactoringTool([idioms], explicit=[idioms])

        assert skipped.pre_order == skipped.post_order == []
        assert len(named.pre_order + named.post_order) == 1

    def test_a_module_without_a_fixer_class_raises(self) -> None:
        with pytest.raises(refactor.FixerError):
            refactor.RefactoringTool(["lib2to3.fixer_util"])


@REQUIRES_LIB2TO3
class TestRefactoringStrings:
    """`refactor_string()` returns the rewritten tree and raises on a parse
    error; `str(tree)` gives back unchanged code byte for byte; the grammar
    stops at Python 3.8."""

    def test_it_rewrites_and_keeps_the_comment(self) -> None:
        tree = default_tool().refactor_string("print 'total:', d.has_key(k)  # keep me\n", "s")

        assert str(tree) == "print('total:', k in d)  # keep me\n"
        assert tree.was_changed

    def test_unchanged_code_round_trips_byte_for_byte(self) -> None:
        source = "x  =  ( 1 ,\n      2 )   # spaced\n\n\n# trailing\ny=[ ]\n"
        tree = default_tool().refactor_string(source, "s")

        assert str(tree) == source
        assert not tree.was_changed

    @pytest.mark.parametrize(
        "source", ["if (y := 1): pass\n", "def f(a, /, b): pass\n", "x: int = 1\n"]
    )
    def test_python_38_syntax_parses(self, source: str) -> None:
        assert str(default_tool().refactor_string(source, "s")) == source

    @pytest.mark.parametrize(
        "source",
        ["match x:\n    case 1:\n        pass\n", "@a[0].b\ndef f(): pass\n"],
        ids=["match", "relaxed-decorator"],
    )
    def test_newer_syntax_raises(self, source: str) -> None:
        with pytest.raises(ParseError):
            default_tool().refactor_string(source, "s")

    def test_print_function_option(self) -> None:
        modern = "print('a', end='')\n"

        with pytest.raises(ParseError):
            tool("print").refactor_string(modern, "s")
        tree = tool("print", options={"print_function": True}).refactor_string(modern, "s")
        assert str(tree) == modern


@REQUIRES_LIB2TO3
class TestFilesAndDirectories:
    """`refactor_file()`, `refactor_dir()`, `refactor()`: whole files, written
    only with `write=True` and only when changed; dot names skipped."""

    def test_refactor_file_writes_only_when_asked(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "old.py"
        script.write_text("print 'x'\n")
        refactorer = tool("print")

        assert refactorer.refactor_file(str(script)) is None
        assert script.read_text() == "print 'x'\n"
        assert not refactorer.wrote

        refactorer.refactor_file(str(script), write=True)
        assert script.read_text() == "print('x')\n"
        assert refactorer.wrote

    def test_an_unchanged_file_is_not_rewritten(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "new.py"
        script.write_text("print('x')\n")
        os.utime(script, (0, 0))
        refactorer = tool("print")

        refactorer.refactor_file(str(script), write=True)

        assert script.stat().st_mtime == 0
        assert refactorer.files == []
        assert not refactorer.wrote

    def test_refactor_dir_skips_dot_names(self, tmp_path: pathlib.Path) -> None:
        for name in ("a.py", ".b.py", "sub/c.py", ".hidden/d.py", "notes.txt"):
            path = tmp_path / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("print 'x'\n")
        refactorer = tool("print")

        refactorer.refactor_dir(str(tmp_path), write=True)

        assert refactorer.files == [str(tmp_path / "a.py"), str(tmp_path / "sub" / "c.py")]
        assert (tmp_path / "sub" / "c.py").read_text() == "print('x')\n"
        for skipped in (".b.py", ".hidden/d.py", "notes.txt"):
            assert (tmp_path / skipped).read_text() == "print 'x'\n"

    def test_refactor_dir_peaks_at_a_file_not_the_directory(self, tmp_path: pathlib.Path) -> None:
        source = "print 'x'\n" * 2_000
        for count in (1, 10):
            directory = tmp_path / str(count)
            directory.mkdir()
            for index in range(count):
                (directory / f"f{index}.py").write_text(source)
        refactorer = tool("print")

        one = peak_bytes(lambda: refactorer.refactor_dir(str(tmp_path / "1")))
        ten = peak_bytes(lambda: refactorer.refactor_dir(str(tmp_path / "10")))

        assert ten < one * 4, f"ten files peaked at {ten} bytes against {one} for one"

    def test_refactor_takes_files_and_directories(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "inner.py").write_text("print 'x'\n")
        (tmp_path / "outer.py").write_text("print 'x'\n")
        refactorer = tool("print")

        refactorer.refactor([str(tmp_path / "outer.py"), str(tmp_path / "dir")], write=True)

        assert (tmp_path / "outer.py").read_text() == "print('x')\n"
        assert (tmp_path / "dir" / "inner.py").read_text() == "print('x')\n"

    def test_refactor_docstring_touches_only_the_examples(self) -> None:
        text = "print 'prose stays'\n>>> print 'x'\nx\n"

        result = tool("print").refactor_docstring(text, "doc")

        assert result == "print 'prose stays'\n>>> print('x')\nx\n"

    def test_refactor_tree_works_in_place(self) -> None:
        refactorer = tool("print")
        tree = refactorer.driver.parse_string("print 'x'\n")
        tree.future_features = frozenset()

        assert refactorer.refactor_tree(tree, "t") is True
        assert str(tree) == "print('x')\n"

        modern = refactorer.driver.parse_string("print('x')\n")
        modern.future_features = frozenset()
        assert refactorer.refactor_tree(modern, "t") is False


@REQUIRES_LIB2TO3
class TestTraversalIsLazy:
    """`Base.pre_order()`, `post_order()`, `leaves()` | O(n·d) to exhaust:
    all three are generators, and taking the first node from `pre_order()`
    visits one."""

    def test_the_first_node_visits_one(self) -> None:
        tree = driver.Driver(pygram.python_grammar, convert=pytree.convert).parse_string(
            NO_MATCH_LINE * 4_000
        )
        visited = 0
        original = pytree.Node.pre_order

        def counting(self: Any) -> Any:
            nonlocal visited
            visited += 1
            return original(self)

        pytree.Node.pre_order = counting
        try:
            assert next(tree.pre_order()) is tree
        finally:
            pytree.Node.pre_order = original

        assert visited == 1
        for name in ("pre_order", "post_order", "leaves"):
            assert type(getattr(tree, name)()).__name__ == "generator"


@REQUIRES_LIB2TO3
class TestTheCommand:
    """`python -m lib2to3` and `lib2to3.main.main()`: a diff and no writes by
    default, `-w`, `-n`, `-f`, `-x`, `-o -W`, `-d`, `-l`, `-j`, and the exit
    status."""

    def test_by_default_it_shows_a_diff_and_writes_nothing(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "s.py").write_text("print 'hi'\n")

        result = run_2to3("s.py", cwd=tmp_path)

        assert result.returncode == 0
        assert "+print('hi')" in result.stdout
        assert (tmp_path / "s.py").read_text() == "print 'hi'\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["s.py"]

    def test_w_writes_with_a_backup_and_n_without(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a.py").write_text("print 'a'\n")
        (tmp_path / "b.py").write_text("print 'b'\n")

        assert run_2to3("-w", "a.py", cwd=tmp_path).returncode == 0
        assert run_2to3("-w", "-n", "b.py", cwd=tmp_path).returncode == 0

        assert (tmp_path / "a.py").read_text() == "print('a')\n"
        assert (tmp_path / "a.py.bak").read_text() == "print 'a'\n"
        assert (tmp_path / "b.py").read_text() == "print('b')\n"
        assert not (tmp_path / "b.py.bak").exists()

    def test_f_and_x_choose_the_fixers(self, tmp_path: pathlib.Path) -> None:
        source = "print d.has_key(k)\n"
        (tmp_path / "f.py").write_text(source)
        (tmp_path / "x.py").write_text(source)

        run_2to3("-w", "-n", "-f", "print", "f.py", cwd=tmp_path)
        run_2to3("-w", "-n", "-x", "print", "x.py", cwd=tmp_path)

        assert (tmp_path / "f.py").read_text() == "print(d.has_key(k))\n"
        assert (tmp_path / "x.py").read_text() == "print k in d\n"

    def test_o_with_w_writes_every_file_elsewhere(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "old.py").write_text("print 'x'\n")
        (tmp_path / "src" / "same.py").write_text("x = 1\n")

        result = run_2to3("-n", "-W", "-o", "out", "src", cwd=tmp_path)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "out" / "old.py").read_text() == "print('x')\n"
        assert (tmp_path / "out" / "same.py").read_text() == "x = 1\n"
        assert (tmp_path / "src" / "old.py").read_text() == "print 'x'\n"

    def test_d_rewrites_only_doctests(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "README.rst").write_text("print 'prose'\n>>> print 'x'\nx\n")

        run_2to3("-w", "-n", "-d", "README.rst", cwd=tmp_path)

        converted = (tmp_path / "README.rst").read_text()
        assert converted.startswith("print 'prose'\n>>> print('x')\nx\n")

    def test_l_lists_the_fixers(self, tmp_path: pathlib.Path) -> None:
        listed = run_2to3("-l", cwd=tmp_path).stdout.split()

        assert "print" in listed
        assert "has_key" in listed

    def test_j_converts_every_file(self, tmp_path: pathlib.Path) -> None:
        for name in ("a.py", "b.py"):
            (tmp_path / name).write_text("print 'x'\n")

        result = run_2to3("-w", "-n", "-j", "2", "a.py", "b.py", cwd=tmp_path)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "a.py").read_text() == "print('x')\n"
        assert (tmp_path / "b.py").read_text() == "print('x')\n"

    def test_a_file_that_fails_returns_1_and_the_rest_still_run(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "bad.py").write_text("match x:\n    case 1:\n        pass\n")
        (tmp_path / "good.py").write_text("print 'x'\n")

        result = run_2to3("-w", "-n", "bad.py", "missing.py", "good.py", cwd=tmp_path)

        assert result.returncode == 1
        assert "Can't parse bad.py" in result.stderr
        assert "Can't open missing.py" in result.stderr
        assert (tmp_path / "good.py").read_text() == "print('x')\n"

    def test_main_returns_the_same_status(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "ok.py").write_text("print 'x'\n")

        assert l2t_main.main(FIXES, [str(tmp_path / "ok.py")]) == 0
        assert l2t_main.main(FIXES, [str(tmp_path / "missing.py")]) == 1
        assert "+print('x')" in capsys.readouterr().out


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
    """Each block runs in its own subprocess and asserts its own result, on
    the versions that still have the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @REQUIRES_LIB2TO3
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

    @REQUIRES_LIB2TO3
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "k in d)  # keep me" in s)
        mutated = source.replace("k in d)  # keep me", "d.has_key(k))  # keep me", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
