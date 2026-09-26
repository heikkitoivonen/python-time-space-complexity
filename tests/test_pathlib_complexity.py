"""Tests for docs/stdlib/pathlib.md.

The page prices pure paths by the path's components (n) and characters (L),
and concrete paths by the syscalls they make, a syscall counting as O(1).
Syscalls are counted by wrapping the os functions pathlib reaches; space is
settled by traced allocation, holding one dimension fixed while another grows;
where neither separates the versions, elapsed time is compared across a wide
size step. Most rows move at a release, so most tests branch on
`sys.version_info` at the boundary the page names.

Measurement scope:

* Construction: a 100,000-character path peaks at about 100,800 B on 3.10 and
  at the same few hundred bytes as a 10-character one from 3.12, where the
  first `str()` builds the string (over 50 KB) and the second returns the same
  object. Joining a 1,000,000-character segment costs x19 a 10-character one
  on 3.10 and x27 on 3.11 by the clock, and x1.0 from 3.12. Joining onto a
  path grown one name at a time copies what that path holds: onto 10,000
  joined segments the peak is over 50 KB on every version. Onto one
  10,000-component string it is under 2 KB from 3.12 and over 50 KB before,
  where the parsed parts are copied instead. `os.path.join` with the long
  segment peaks over 500 KB; pathlib's `/` stays under 10 KB on every version.
  `Path.exists()` and `os.path.exists()` make one stat call each.
* `parts` is identity-checked: the same tuple twice before 3.12, a new one
  from 3.12. `parents` over 400 components peaks under 2 KB, and `list()` of
  it over 100 times that. `stem` and `suffix` of a 100,000-character final
  component each peak over 50 KB.
* `relative_to()` is timed at 200 and 800 components of fixed length: over x6
  from 3.12 (x8.2 to x9.1 measured) and under x4 before (x1.7 to x2.0). Its
  space against a base of 100 and 400 components grows x12.3 on 3.12 and x3.2
  to x4.0 on 3.10, 3.13 and 3.14; asserted over x8 on 3.12 and under x6
  elsewhere.
* `match()` on a path of 10,000 components peaks over 20 times what 10 cost
  from 3.13 (160,256 B against about 1,850 B), and about the same for both
  sizes before.
  On every version the peak stays under 5,000 B plus 50 B per component.
* `is_reserved()` is exercised on `PureWindowsPath`: `CON/file.txt` is
  reserved from 3.13 and not before, `x/CON` on every version, and the call
  warns from 3.13.
* Predicates, `stat()`, `lstat()`, `samefile()`, `owner()`, `group()`,
  `chmod()`, `unlink()` and `rmdir()` are counted at the os layer: one call
  each, two for `samefile()`, none for `absolute()`, and no directory read. 3.10
  reaches os through `_NormalAccessor`, which the counter patches as well.
  `is_mount()` makes the same count at depth 1 and 16 except on 3.12, where
  15 more components cost 15 more calls. `resolve()` makes eight more
  stat-family calls for eight more components.
* `Path.info` (3.14): four `exists`/`is_file`/`is_dir` queries make one stat
  call where the `Path` predicates make four, `is_symlink()` adds one lstat,
  the attribute is the same object on each access, and its answer survives the
  file's deletion while a fresh `Path` stats again. A path from `iterdir()`
  answers `is_file()`, `is_dir()` and `is_symlink()` with no os-level stat
  call, and still reports a file after it is deleted; `DirEntry`'s own
  fallback stat, where the filesystem reports no type, is not counted.
* `iterdir()` taking one item peaks over three times as much in a directory of
  1,600 entries as in one of 200, and lists the directory once; `list()` of
  the 1,600 peaks over 1.5 times what the first item does (x1.97 on 3.14). A missing
  directory raises at the call from 3.13 and at the first `next()` before.
* `glob()` with one match in a directory of 200 against 1,600 entries peaks
  over three times as much; the same holds one level down with 50 against 400
  subdirectories. `glob('**/...')` and `rglob()` over a chain of 640
  directories peak over 1.25 times a chain of 20, and a directory of 1,600
  entries over three times one of 200.
  With the widest directory held at 100 entries and the depth at 2, 10,000
  matches cost x52 what 100 cost on 3.10 and 3.11 and under x2 from 3.12
  (asserted over x10 and under x4). With no matches, 100 files on each of 50
  levels cost x13.7 what 100 files at the bottom of the same chain cost on
  3.10 and 3.11, and under x2 from 3.12 (asserted over x6 and under x4).
* `walk()` (3.12+) over 800 sibling directories peaks over 2.5 times 200.
  Bottom-up over a chain of 50 levels holding 100 files each peaks over eight
  times top-down (x20 to x35 measured).
* `mkdir(parents=True)` makes five to ten mkdir calls for five missing
  components, and its peak for 700 missing components is over twelve times that for 100
  (x25 to x29 at 800 against 100): quadratic in the depth at a fixed component
  length, as O(k·L) predicts.
* `read_text()` peaks over ten times as much for 80x the file.
  `write_bytes()` peaks the same for 1 MB and 8 MB; `write_text()` for 8 MB
  peaks over 8 MB.
* `copy()` (3.14) peaks under 1.5 times as much for an 8 MB file as for a
  1 MB one, and copies a directory tree whole; `move()` and `move_into()`
  leave nothing at the source.
* Version Notes are checked by `hasattr` against each release named, and by
  what `glob('**')` yields: directories only before 3.13, files as well from
  it.
* Every fenced Python block runs in its own subprocess and temporary
  directory. Blocks calling an API newer than the running interpreter are
  counted and skipped there, and a block with one assertion inverted is
  asserted to fail.

Not settled here:

* "O(1)" for a syscall is a choice of unit: the kernel resolves a path
  component by component. On a real filesystem a recursive glob over a chain
  is quadratic in its depth by the clock on every version, which is that
  kernel cost, so the time bounds are argued from the syscall counts and
  CPython source rather than timed.
* `owner()`, `group()` and `expanduser('~user')` resolve through the user
  database, whose cost depends on the NSS backend.
* `lchmod()` on the subject it exists for: on Linux it raises
  NotImplementedError on a symlink on every supported version.
* `rename()` and `replace()` across two filesystems, and `move()` falling back
  to a copy there: every test runs on one tmp_path.
* Windows filesystem behaviour, including `is_junction()`, `WindowsPath`
  itself and drive handling in `absolute()`. Pure Windows semantics are
  tested through `PureWindowsPath`; the symlink tests are POSIX-only and skip
  elsewhere.
* The O(w + P) and O(A + Y) space bounds for recursive globs, and the O(w + P)
  bound for `walk()`, are read from each release's Lib/pathlib and Lib/glob.py
  (3.13+) or Lib/os.py (walk from 3.13): the tests vary one term at a time and
  do not show the terms add. Patterns with more than one `**`, where 3.12
  keeps every match to drop duplicates, are not measured.
* `copy()` of a directory is O(E + b) from Lib/pathlib/__init__.py's
  recursion; only its result is checked.
* `pathlib.PathInfo`, `DirEntryInfo`, `copy_info`, `copyfileobj`,
  `ensure_different_files`, `ensure_distinct_paths` and `magic_open` appear in
  `dir(pathlib)` on 3.14 as imports from its private modules, and are not
  public API; `pathlib.types.PathInfo` is the public protocol.
* The string work in `resolve()`, and in `is_mount()` on 3.12, is read from
  `posixpath.realpath`: each component builds the path so far as a new
  string, O(n·L) in all. Only the lstat count is measured.
* Not varied: the filesystem type, symlink density inside `resolve()`, case
  sensitivity in globbing, and component length except where named.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pathlib.md"
EXPECTED_BLOCKS = 16
# Blocks calling an API newer than the oldest supported interpreter run only
# where it exists; each marker's block count is asserted so the exclusion
# cannot quietly widen.
LATER_MARKERS: dict[str, tuple[tuple[int, int], int]] = {
    ".walk(": ((3, 12), 1),
    ".info": ((3, 14), 1),
    ".copy(": ((3, 14), 1),
}

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX-only behaviour")

# gh-101362: from 3.12 PurePath keeps its arguments and parses them on first use.
DEFERRED = sys.version_info >= (3, 12)

SYSCALL_NAMES: tuple[str, ...] = (
    "stat",
    "lstat",
    "scandir",
    "listdir",
    "mkdir",
    "unlink",
    "rmdir",
    "chmod",
)


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


def warm_peak(func: Callable[[], Any]) -> int:
    """Peak traced allocation of a second run, after caches are filled."""
    func()
    return peak_bytes(func)


class SyscallCounter:
    """Counts the filesystem syscalls a pathlib operation makes."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = dict.fromkeys(SYSCALL_NAMES, 0)

    @property
    def stat_family(self) -> int:
        """stat and lstat together: which of the two a predicate reaches
        differs by version, the count does not."""
        return self.counts["stat"] + self.counts["lstat"]

    @property
    def listings(self) -> int:
        """scandir and listdir together, for the same reason."""
        return self.counts["scandir"] + self.counts["listdir"]


@contextmanager
def counting_syscalls() -> Iterator[SyscallCounter]:
    """Wrap the filesystem calls pathlib reaches, for the duration of the block."""
    counter = SyscallCounter()
    real = {name: getattr(os, name) for name in SYSCALL_NAMES}

    def make(name: str) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            counter.counts[name] += 1
            return real[name](*args, **kwargs)

        return wrapper

    wrappers = {name: make(name) for name in SYSCALL_NAMES}
    # 3.10 reaches os through pathlib._NormalAccessor, which binds the
    # functions as class attributes at import time; patching os alone would
    # count nothing there.
    accessor = getattr(pathlib, "_NormalAccessor", None)
    saved: dict[str, Any] = {}
    for name, wrapper in wrappers.items():
        setattr(os, name, wrapper)
        if accessor is not None and accessor.__dict__.get(name) is real[name]:
            saved[name] = accessor.__dict__[name]
            setattr(accessor, name, staticmethod(wrapper))
    try:
        yield counter
    finally:
        for name, func in real.items():
            setattr(os, name, func)
        for name, func in saved.items():
            setattr(accessor, name, func)


def drain(iterator: Any) -> None:
    """Exhaust an iterator without retaining what it yields."""
    deque(iterator, maxlen=0)


def make_wide(root: pathlib.Path, count: int, suffix: str = ".txt") -> pathlib.Path:
    """One directory holding `count` empty files."""
    wide = root / f"wide{count}{suffix}d"
    wide.mkdir()
    for index in range(count):
        (wide / f"f{index:06d}{suffix}").touch()
    return wide


def make_wide_dirs(root: pathlib.Path, count: int) -> pathlib.Path:
    """One directory holding `count` empty subdirectories."""
    wide = root / f"wided{count}"
    wide.mkdir()
    for index in range(count):
        (wide / f"d{index:05d}").mkdir()
    return wide


def make_chain(root: pathlib.Path, name: str, depth: int, files_per_level: int = 0) -> pathlib.Path:
    """A chain of `depth` directories, each holding `files_per_level` files."""
    top = root / name
    top.mkdir()
    node = top
    for _ in range(depth):
        for index in range(files_per_level):
            (node / f"f{index:03d}.dat").touch()
        node = node / "d"
        node.mkdir()
    return top


def make_deep(root: pathlib.Path, depth: int) -> pathlib.Path:
    """A chain of `depth` directories with one file at the bottom."""
    deep = make_chain(root, f"deep{depth}", depth)
    node = deep.joinpath(*["d"] * depth)
    (node / "leaf.txt").touch()
    return deep


def remove_deep(root: pathlib.Path) -> None:
    """Unwind a chain from the bottom, so no recursive removal meets its depth."""
    node = root
    while True:
        children = [child for child in node.iterdir() if child.is_dir()]
        if not children:
            break
        node = children[0]
    while True:
        for entry in node.iterdir():
            if not entry.is_dir():
                entry.unlink()
        node.rmdir()
        if node == root:
            break
        node = node.parent


class TestPurePathsDoNoIO:
    """The pure table's defining property: every operation below runs against
    a path that does not exist, under the syscall counter, and reaches the
    filesystem zero times."""

    def test_no_pure_operation_reaches_the_filesystem(self) -> None:
        pure = pathlib.PurePosixPath("/nowhere/at/all/report.tar.gz")
        other = pathlib.PurePosixPath("/nowhere")

        with counting_syscalls() as counter:
            _ = pure.parts
            _ = pure.parent
            _ = pure.parents[0]
            _ = (pure.name, pure.stem, pure.suffix, pure.suffixes)
            _ = (pure.anchor, pure.drive, pure.root)
            pure.is_absolute()
            pure.with_name("other.txt")
            pure.with_stem("other")
            pure.with_suffix(".md")
            pure.joinpath("x")
            _ = pure / "y"
            pure.relative_to(other)
            pure.is_relative_to(other)
            pure.match("*.gz")
            pure.as_posix()
            str(pure)

        assert counter.stat_family == 0, f"a pure operation stat'd: {counter.counts}"
        assert counter.listings == 0, f"a pure operation read a directory: {counter.counts}"

    def test_the_documented_pure_values(self) -> None:
        pure = pathlib.PurePosixPath("/nowhere/at/all/report.tar.gz")

        assert pure.name == "report.tar.gz"
        assert pure.stem == "report.tar"
        assert pure.suffix == ".gz"
        assert pure.suffixes == [".tar", ".gz"]
        assert pure.parts == ("/", "nowhere", "at", "all", "report.tar.gz")
        assert pathlib.PureWindowsPath("C:/Users/x").drive == "C:"
        assert pathlib.PureWindowsPath("C:/Users/x").as_posix() == "C:/Users/x"

    def test_a_pure_path_has_no_filesystem_methods(self) -> None:
        pure_surface = {n for n in dir(pathlib.PurePath) if not n.startswith("_")}

        assert "exists" not in pure_surface
        assert "iterdir" not in pure_surface

    @POSIX_ONLY
    def test_the_other_concrete_flavour_cannot_be_built(self) -> None:
        with pytest.raises(NotImplementedError):
            pathlib.WindowsPath("x")
        assert type(pathlib.Path("x")) is pathlib.PosixPath


class TestFinalComponentSlices:
    """`stem`, `suffix`, `suffixes` | O(c) | O(c), c = characters in the final
    component: each slices it, so a long name makes a long result."""

    NAME = "a" * 100_000 + ".txt"

    def test_stem_is_a_slice_of_the_name(self) -> None:
        path = pathlib.PurePosixPath("/d/" + self.NAME)

        assert warm_peak(lambda: path.stem) > 50_000

    def test_suffix_is_a_slice_of_the_name(self) -> None:
        path = pathlib.PurePosixPath("/d/a." + "b" * 100_000)

        assert warm_peak(lambda: path.suffix) > 50_000

    def test_name_is_not(self) -> None:
        path = pathlib.PurePosixPath("/d/" + self.NAME)

        assert warm_peak(lambda: path.name) < 1_000


class TestConstructionIsDeferred:
    """`PurePath(*pathsegments)` | O(L); O(s) from 3.12.

    Before 3.12 the constructor splits the string, so the peak tracks its
    length; from 3.12 it keeps the argument and the first use pays the parse.
    """

    def test_the_peak_tracks_the_string_only_before_312(self) -> None:
        short = "/" + "a" * 10
        long_path = "/" + "a" * 100_000

        short_peak = peak_bytes(lambda: pathlib.PurePath(short))
        long_peak = peak_bytes(lambda: pathlib.PurePath(long_path))

        if DEFERRED:
            assert long_peak < 2 * short_peak, f"{short_peak} B against {long_peak} B"
        else:
            assert long_peak > 50 * short_peak, f"{short_peak} B against {long_peak} B"

    def test_the_parse_is_paid_once_and_str_is_cached(self) -> None:
        path = pathlib.PurePath("/" + "a" * 100_000)

        first_peak = peak_bytes(lambda: str(path))
        second_peak = peak_bytes(lambda: str(path))

        assert first_peak > 50_000, f"the first str() should build the path: {first_peak} B"
        assert second_peak < first_peak / 50, f"{first_peak} B against {second_peak} B"
        assert str(path) is str(path)


class TestJoiningCopiesTheSegments:
    """`path / segment` | O(L); O(s) from 3.12.

    From 3.12 the new path copies every segment of the left operand, so joining
    onto a path grown one name at a time costs its segment count, while joining
    onto a path from one string is constant. Before 3.12 the parsed parts are
    copied instead, so both cost the depth.
    """

    @staticmethod
    def _grown(count: int) -> pathlib.PurePosixPath:
        path = pathlib.PurePosixPath("r")
        for _ in range(count):
            path = path / "a"
        str(path)
        return path

    def test_joining_onto_a_grown_path_copies_it(self) -> None:
        grown = self._grown(10_000)

        assert warm_peak(lambda: grown / "x") > 50_000

    def test_joining_onto_one_string_is_constant_from_312(self) -> None:
        single = pathlib.PurePosixPath("r/" + "/".join(["a"] * 10_000))
        str(single)

        peak = warm_peak(lambda: single / "x")

        if DEFERRED:
            assert peak < 2_000, f"one stored segment should be all that is copied: {peak} B"
        else:
            assert peak > 50_000, f"the parsed parts should be copied: {peak} B"

    def test_one_joinpath_call_builds_the_same_path(self) -> None:
        names = [f"d{index}" for index in range(100)]
        grown = pathlib.PurePosixPath("/data")
        for name in names:
            grown = grown / name

        joined = pathlib.PurePosixPath("/data").joinpath(*names)

        assert joined == grown
        assert str(joined) == str(grown) == "/data/" + "/".join(names)

    @pytest.mark.timing
    def test_a_long_right_operand_is_parsed_only_before_312(self) -> None:
        """x19 on 3.10 and x27 on 3.11 for 100,000x the segment; x1.0 from 3.12.

        Timed, because a segment with no separator splits into the same string
        object, so allocation cannot separate the versions.
        """
        base = pathlib.PurePath("/tmp")
        short = best_ns(lambda: base / ("b" * 10), repeats=9, inner=50)
        long_segment = "b" * 1_000_000
        long_ns = best_ns(lambda: base / long_segment, repeats=9, inner=50)
        ratio = long_ns / short

        if DEFERRED:
            assert ratio < 3, f"{short:.0f} ns against {long_ns:.0f} ns"
        else:
            assert ratio > 5, f"{short:.0f} ns against {long_ns:.0f} ns"

    def test_os_path_join_builds_the_string_and_the_operator_does_not(self) -> None:
        long_segment = "b" * 1_000_000
        base = pathlib.PurePath("data")

        assert peak_bytes(lambda: os.path.join("data", long_segment)) > 500_000
        assert peak_bytes(lambda: base / long_segment) < 10_000

    def test_the_filesystem_call_is_the_same_either_way(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "file.txt"

        with counting_syscalls() as through_pathlib:
            path.exists()
        with counting_syscalls() as through_os_path:
            os.path.exists(str(path))

        assert through_pathlib.stat_family == through_os_path.stat_family == 1


class TestPartsAndParents:
    """`parts` is O(n) on every access from 3.12 and cached before;
    `parents` is O(1) and `list(parents)` O(n·L)."""

    def test_whether_parts_is_cached(self) -> None:
        path = pathlib.PurePosixPath("/a/b/c/d/e/f.txt")

        first, second = path.parts, path.parts

        assert first == second
        assert (first is second) is not DEFERRED

    def test_parents_is_lazy_and_listing_it_is_not(self) -> None:
        deep = pathlib.PurePosixPath("/" + "/".join(f"d{i}" for i in range(400)))
        _ = deep.parts

        lazy_peak = warm_peak(lambda: deep.parents)
        listed_peak = warm_peak(lambda: list(deep.parents))

        assert len(deep.parents) == 400
        assert lazy_peak < 2_000, f"parents should hold nothing: {lazy_peak} B"
        assert listed_peak > 100 * lazy_peak, f"{lazy_peak} B against {listed_peak} B"


def _deep(components: int) -> pathlib.PurePosixPath:
    return pathlib.PurePosixPath("/" + "/".join(f"d{i:04d}" for i in range(components)))


class TestRelativeTo:
    """`relative_to()` | O(L); O(n·L) from 3.12 | O(L); O(n·L) on 3.12."""

    def test_relative_to_returns_the_tail(self) -> None:
        path = pathlib.PurePosixPath("/a/b/c/f.txt")

        assert path.relative_to("/a") == pathlib.PurePosixPath("b/c/f.txt")
        assert path.is_relative_to("/a")
        assert not path.is_relative_to("/z")

    @pytest.mark.timing
    def test_the_time_squares_from_312(self) -> None:
        """x8.2 to x9.1 for 4x the components from 3.12; x1.7 to x2.0 before.

        Linear is x4 at this step and a clean square x16; the measured exponent
        rises towards 2 as n grows (1.21 at 100 to 1.81 at 1,600 on 3.14).
        """
        base = pathlib.PurePosixPath("/d0000")
        paths = [_deep(n) / "f.txt" for n in (200, 800)]
        for path in paths:
            _ = path.parts
        small, large = (best_ns(lambda p=p: p.relative_to(base), repeats=5) for p in paths)
        ratio = large / small

        if DEFERRED:
            assert ratio > 6, f"{small:.0f} ns against {large:.0f} ns"
        else:
            assert ratio < 4, f"{small:.0f} ns against {large:.0f} ns"

    def test_a_deep_base_costs_quadratic_space_on_312_only(self) -> None:
        peaks = []
        for components in (100, 400):
            base = _deep(components)
            child = base / "f.txt"
            _ = (str(base), str(child), base.parts, child.parts)
            peaks.append(warm_peak(lambda b=base, c=child: c.relative_to(b)))
        ratio = peaks[1] / peaks[0]

        if sys.version_info[:2] == (3, 12):
            assert ratio > 8, f"4x the base's depth: {peaks}"
        else:
            assert ratio < 6, f"4x the base's depth: {peaks}"


class TestMatchSpace:
    """`match()`, `full_match()` | O(L) | O(L): from 3.13 `match()` builds the
    parts tuple on every call; the bound holds on every version."""

    def test_the_peak_stays_linear(self) -> None:
        peaks = []
        for components in (10, 10_000):
            path = _deep(components) / "f.py"
            _ = (str(path), path.parts)
            peaks.append(warm_peak(lambda p=path: p.match("*.py")))
            assert peaks[-1] < 5_000 + 50 * components, f"{components} components: {peaks}"

        if sys.version_info >= (3, 13):
            assert peaks[1] > 20 * peaks[0], f"match() builds the parts from 3.13: {peaks}"

    def test_the_documented_results(self) -> None:
        path = pathlib.PurePosixPath("/a/b/f.py")

        assert path.match("*.py")
        assert path.match("b/*.py")
        assert not path.match("a/*.py")
        if sys.version_info >= (3, 13):
            assert path.full_match("/a/**/*.py")  # type: ignore[attr-defined]
            assert not path.full_match("*.py")  # type: ignore[attr-defined]


class TestPureRowsWithVersionMarkers:
    """The pure rows whose note names a version."""

    def test_is_reserved_checks_every_component_from_313(self) -> None:
        windows = pathlib.PureWindowsPath
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            inner = windows("CON/file.txt").is_reserved()
            final = windows("x/CON").is_reserved()
            posix = pathlib.PurePosixPath("CON").is_reserved()

        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert final is True
        assert inner is (sys.version_info >= (3, 13))
        assert bool(deprecated) is (sys.version_info >= (3, 13))
        assert posix is False

    def test_purepath_as_uri_is_deprecated_in_314(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pathlib.PurePosixPath("/a/b").as_uri()

        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert bool(deprecated) is (sys.version_info >= (3, 14))

    @POSIX_ONLY
    def test_path_as_uri_is_not(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            uri = pathlib.Path("/a/b").as_uri()

        assert uri == "file:///a/b"
        assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Path.from_uri() is 3.13+")
    def test_as_uri_and_from_uri_round_trip(self, tmp_path: pathlib.Path) -> None:
        assert pathlib.Path.from_uri(tmp_path.as_uri()) == tmp_path  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="PurePath.parser is 3.13+")
    def test_parser_is_the_flavour_module(self) -> None:
        assert pathlib.PurePosixPath("a").parser is __import__("posixpath")  # type: ignore[attr-defined]
        assert pathlib.PureWindowsPath("a").parser is __import__("ntpath")  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="with_segments() is 3.12+")
    def test_with_segments_keeps_the_type(self) -> None:
        path = pathlib.PureWindowsPath("C:/x")

        made = path.with_segments("a", "b")  # type: ignore[attr-defined]

        assert type(made) is pathlib.PureWindowsPath
        assert str(made) == "a\\b"


class TestCountingHarness:
    """The counter has to see real calls, or every count below is vacuous."""

    def test_the_counter_sees_a_stat_call(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f"
        target.write_text("x", encoding="utf-8")

        with counting_syscalls() as counter:
            target.stat()
            target.stat()

        assert counter.stat_family == 2

    def test_the_counter_sees_a_directory_read(self, tmp_path: pathlib.Path) -> None:
        with counting_syscalls() as counter:
            list(tmp_path.iterdir())

        assert counter.listings == 1

    def test_os_is_restored_afterwards(self) -> None:
        before = os.stat
        with counting_syscalls():
            assert os.stat is not before
        assert os.stat is before


class TestOneSyscallPerPredicate:
    """The O(1) rows of the Path table: one stat call each, counted."""

    def test_each_predicate_makes_exactly_one_stat_call(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("hello", encoding="utf-8")
        directory = tmp_path / "d"
        directory.mkdir()

        cases: list[tuple[str, Callable[[], object]]] = [
            ("stat", target.stat),
            ("lstat", target.lstat),
            ("exists", target.exists),
            ("is_file", target.is_file),
            ("is_dir", directory.is_dir),
            ("is_symlink", target.is_symlink),
            ("is_socket", target.is_socket),
            ("is_fifo", target.is_fifo),
            ("is_block_device", target.is_block_device),
            ("is_char_device", target.is_char_device),
        ]

        for name, call in cases:
            with counting_syscalls() as counter:
                call()
            assert counter.stat_family == 1, f"{name} made {counter.stat_family} stat calls"
            assert counter.listings == 0, f"{name} read a directory"

    def test_the_documented_example_asks_three_times(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("contents", encoding="utf-8")

        with counting_syscalls() as counter:
            path.exists()
            path.is_file()
            path.is_dir()

        assert counter.stat_family == 3

    @POSIX_ONLY
    def test_owner_and_group_make_one_stat_call_each(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("hello", encoding="utf-8")

        for name, call in (("owner", target.owner), ("group", target.group)):
            try:
                with counting_syscalls() as counter:
                    call()
            except KeyError:
                pytest.skip(f"this uid has no {name} entry in the user database")
            assert counter.stat_family == 1, f"{name} made {counter.stat_family} stat calls"

    def test_samefile_makes_two(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("hello", encoding="utf-8")

        with counting_syscalls() as counter:
            assert target.samefile(target)

        assert counter.stat_family == 2

    def test_absolute_makes_none(self) -> None:
        relative = pathlib.Path("no/such/place")

        with counting_syscalls() as counter:
            result = relative.absolute()

        assert result.is_absolute()
        assert counter.stat_family == 0

    def test_a_predicate_does_not_read_the_directory_it_lives_in(
        self, tmp_path: pathlib.Path
    ) -> None:
        crowded = make_wide(tmp_path, 400)
        target = crowded / "f000000.txt"

        with counting_syscalls() as counter:
            assert target.is_file()

        assert counter.stat_family == 1
        assert counter.listings == 0

    @POSIX_ONLY
    def test_is_junction_is_false_off_windows(self, tmp_path: pathlib.Path) -> None:
        if not hasattr(pathlib.Path, "is_junction"):
            pytest.skip("Path.is_junction() is 3.12+")

        assert tmp_path.is_junction() is False  # type: ignore[attr-defined]

    @POSIX_ONLY
    def test_is_mount_is_constant_except_on_312(self, tmp_path: pathlib.Path) -> None:
        """6 calls at any depth on 3.10 and 3.11, 2 on 3.13 and 3.14; on 3.12
        os.path.ismount resolves the parent, one lstat per component."""
        shallow = tmp_path / "d"
        shallow.mkdir()
        node = tmp_path.joinpath("n", *["x"] * 15)
        node.mkdir(parents=True)

        with counting_syscalls() as counter:
            shallow.is_mount()
        shallow_calls = counter.stat_family
        with counting_syscalls() as counter:
            node.is_mount()
        deep_calls = counter.stat_family

        if sys.version_info[:2] == (3, 12):
            assert deep_calls - shallow_calls == 15, f"{shallow_calls} against {deep_calls}"
        else:
            assert shallow_calls == deep_calls, f"{shallow_calls} against {deep_calls}"
            assert deep_calls <= 8, f"is_mount made {deep_calls} stat calls"

    @POSIX_ONLY
    def test_resolve_makes_one_lstat_per_component(self, tmp_path: pathlib.Path) -> None:
        shallow = tmp_path / "a"
        shallow.mkdir()
        deep = shallow.joinpath(*(f"lvl{index}" for index in range(8)))
        deep.mkdir(parents=True)

        with counting_syscalls() as counter:
            shallow.resolve()
        shallow_calls = counter.stat_family
        with counting_syscalls() as counter:
            deep.resolve()
        deep_calls = counter.stat_family

        assert deep_calls - shallow_calls == 8, f"{shallow_calls} against {deep_calls}"


class TestModificationRowsAreOneSyscall:
    """`chmod()`, `unlink()`, `rmdir()` | O(1): one call each, counted."""

    def test_chmod_unlink_and_rmdir_make_one_call_each(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        directory = tmp_path / "d"
        directory.mkdir()

        with counting_syscalls() as counter:
            target.chmod(0o600)
        assert counter.counts["chmod"] == 1

        with counting_syscalls() as counter:
            directory.rmdir()
        assert counter.counts["rmdir"] == 1

        with counting_syscalls() as counter:
            target.unlink()
        assert counter.counts["unlink"] == 1
        assert not target.exists()

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux has no lchmod")
    def test_lchmod_cannot_be_exercised_on_a_symlink_here(self, tmp_path: pathlib.Path) -> None:
        """Why the lchmod row is recorded as unsettled rather than tested."""
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link"
        link.symlink_to(target)

        target.lchmod(0o600)

        with pytest.raises(NotImplementedError):
            link.lchmod(0o600)


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Path.info is 3.14+")
class TestPathInfoCaches:
    """`PathInfo.exists()`, `is_dir()`, `is_file()` share one stat call;
    `is_symlink()` takes one lstat; both are kept for the object's life."""

    def test_three_questions_cost_one_stat(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")

        info = target.info  # type: ignore[attr-defined]
        with counting_syscalls() as counter:
            info.exists()
            info.is_file()
            info.is_dir()
            info.exists()
        cached = dict(counter.counts)

        with counting_syscalls() as counter:
            info.is_symlink()
            info.is_symlink()
        symlink = dict(counter.counts)

        assert (cached["stat"], cached["lstat"]) == (1, 0), cached
        assert (symlink["stat"], symlink["lstat"]) == (0, 1), symlink

    def test_the_attribute_itself_is_cached(self, tmp_path: pathlib.Path) -> None:
        assert tmp_path.info is tmp_path.info  # type: ignore[attr-defined]

    def test_the_cache_does_not_expire(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        info = target.info  # type: ignore[attr-defined]
        assert info.exists()

        target.unlink()

        assert info.exists(), "the cached answer survives the file"
        assert not pathlib.Path(str(target)).info.exists()  # type: ignore[attr-defined]

    def test_an_iterdir_path_answers_from_its_directory_entry(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "f.txt").touch()
        (entry,) = tmp_path.iterdir()

        with counting_syscalls() as counter:
            answers = [entry.info.is_file(), entry.info.is_dir(), entry.info.is_symlink()]  # type: ignore[attr-defined]
        entry.unlink()

        assert answers == [True, False, False]
        assert counter.stat_family == 0
        assert entry.info.is_file(), "the directory entry, not a stat, answered"  # type: ignore[attr-defined]
        assert not pathlib.Path(str(entry)).info.is_file()  # type: ignore[attr-defined]

    def test_the_protocol_is_public(self) -> None:
        import pathlib.types as types  # type: ignore[import-not-found]

        assert {"exists", "is_dir", "is_file", "is_symlink"} <= set(dir(types.PathInfo))


class TestIterdirReadsTheWholeDirectory:
    """`Path.iterdir()` | O(w) | O(w): the directory is read in full before the
    first item appears."""

    def test_the_first_item_costs_the_whole_listing(self, tmp_path: pathlib.Path) -> None:
        small = make_wide(tmp_path, 200)
        large = make_wide(tmp_path, 1600)

        def first(directory: pathlib.Path) -> None:
            next(iter(directory.iterdir()))

        small_peak = peak_bytes(lambda: first(small))
        large_peak = peak_bytes(lambda: first(large))

        assert large_peak > 3 * small_peak, f"{small_peak} B against {large_peak} B"

    def test_iterating_does_not_hold_the_path_objects(self, tmp_path: pathlib.Path) -> None:
        """The Path objects are made one per step, so a list of them costs
        more than the listing alone."""
        directory = make_wide(tmp_path, 1600)

        first_peak = warm_peak(lambda: next(iter(directory.iterdir())))
        listed_peak = warm_peak(lambda: list(directory.iterdir()))

        assert listed_peak > 1.5 * first_peak, f"{first_peak} B against {listed_peak} B"

    def test_iterdir_reads_the_directory_once(self, tmp_path: pathlib.Path) -> None:
        directory = make_wide(tmp_path, 20)

        with counting_syscalls() as counter:
            entries = list(directory.iterdir())

        assert len(entries) == 20
        assert counter.listings == 1

    def test_when_the_directory_is_read(self, tmp_path: pathlib.Path) -> None:
        missing = tmp_path / "nope"

        if sys.version_info >= (3, 13):
            with pytest.raises(FileNotFoundError):
                missing.iterdir()
        else:
            iterator = missing.iterdir()
            with pytest.raises(FileNotFoundError):
                next(iter(iterator))


class TestGlobScansEntriesNotMatches:
    """`Path.glob(pattern)` | O(E) | O(w): one match costs the whole directory."""

    def test_one_match_still_costs_the_whole_directory(self, tmp_path: pathlib.Path) -> None:
        def haystack(count: int) -> pathlib.Path:
            directory = make_wide(tmp_path, count, ".dat")
            (directory / "needle.txt").touch()
            return directory

        small, large = haystack(200), haystack(1600)
        assert len(list(small.glob("*.txt"))) == 1
        assert len(list(large.glob("*.txt"))) == 1

        small_peak = peak_bytes(lambda: list(small.glob("*.txt")))
        large_peak = peak_bytes(lambda: list(large.glob("*.txt")))

        assert large_peak > 3 * small_peak, f"{small_peak} B against {large_peak} B"

    def test_a_nested_pattern_costs_every_directory_it_opens(self, tmp_path: pathlib.Path) -> None:
        """Measured by peak rather than by counted scandir calls: 3.13 globs
        through a helper that captured os.scandir at import."""

        def tree(count: int) -> pathlib.Path:
            root = make_wide_dirs(tmp_path, count)
            for sub in root.iterdir():
                (sub / "note.dat").touch()
            (root / "d00000" / "only.py").touch()
            return root

        small, large = tree(50), tree(400)
        assert len(list(small.glob("*/*.py"))) == 1
        assert len(list(large.glob("*/*.py"))) == 1

        small_peak = peak_bytes(lambda: list(small.glob("*/*.py")))
        large_peak = peak_bytes(lambda: list(large.glob("*/*.py")))

        assert large_peak > 3 * small_peak, f"{small_peak} B against {large_peak} B"


class TestRecursiveGlobSpace:
    """`glob('**/' + pattern)`, `rglob(pattern)` | O(E) | O(w + P); O(A + Y)
    through 3.11.

    Each test sets out to vary one of w, the queued path length P, the matches
    already yielded (Y), and the listings on the branch being scanned (A), but
    the terms move together: widening a directory also adds retained matches
    through 3.11, and deepening a chain lengthens both the listings on the
    branch and every path yielded.
    """

    def test_rglob_is_glob_with_a_leading_double_star(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "x.py").touch()
        (tmp_path / "y.py").touch()

        assert sorted(tmp_path.rglob("*.py")) == sorted(tmp_path.glob("**/*.py"))

    def test_the_peak_grows_with_the_widest_directory(self, tmp_path: pathlib.Path) -> None:
        small = make_wide(tmp_path, 200)
        large = make_wide(tmp_path, 1600)

        small_peak = peak_bytes(lambda: drain(small.rglob("*.txt")))
        large_peak = peak_bytes(lambda: drain(large.rglob("*.txt")))

        assert large_peak > 3 * small_peak, f"the w term: {small_peak} B against {large_peak} B"

    @pytest.mark.parametrize("spelling", ["rglob", "glob"])
    def test_the_peak_grows_with_the_depth(self, tmp_path: pathlib.Path, spelling: str) -> None:
        """32x the depth at a breadth of one: x171 on 3.10 and x2.1 on 3.14.

        From 3.12 the depth reaches the peak through the length of the path
        being carried, which is what P counts.
        """
        shallow = make_deep(tmp_path, 20)
        nested = make_deep(tmp_path, 640)

        def walk(root: pathlib.Path) -> None:
            if spelling == "rglob":
                drain(root.rglob("*.txt"))
            else:
                drain(root.glob("**/*.txt"))

        shallow_peak = warm_peak(lambda: walk(shallow))
        nested_peak = warm_peak(lambda: walk(nested))
        remove_deep(nested)

        assert nested_peak > 1.25 * shallow_peak, f"{shallow_peak} B against {nested_peak} B"

    def test_matches_are_held_only_through_311(self, tmp_path: pathlib.Path) -> None:
        """100 subdirectories holding 1 or 100 matches each: w = 100, depth 2."""

        def tree(name: str, per_directory: int) -> pathlib.Path:
            root = tmp_path / name
            root.mkdir()
            for index in range(100):
                sub = root / f"s{index:03d}"
                sub.mkdir()
                for match in range(per_directory):
                    (sub / f"f{match:03d}.txt").touch()
            return root

        few, many = tree("few", 1), tree("many", 100)
        few_peak = warm_peak(lambda: drain(few.rglob("*.txt")))
        many_peak = warm_peak(lambda: drain(many.rglob("*.txt")))
        ratio = many_peak / few_peak

        if sys.version_info >= (3, 12):
            assert ratio < 4, f"100x the matches: {few_peak} B against {many_peak} B"
        else:
            assert ratio > 10, f"100x the matches: {few_peak} B against {many_peak} B"

    def test_ancestor_listings_are_held_only_through_311(self, tmp_path: pathlib.Path) -> None:
        """A chain of 50, with 100 files on every level or 100 at the bottom
        only; nothing matches, so no match is held on any version."""
        crowded = make_chain(tmp_path, "crowded", 50, files_per_level=100)
        sparse = make_chain(tmp_path, "sparse", 50)
        bottom = sparse.joinpath(*["d"] * 50)
        for index in range(100):
            (bottom / f"f{index:03d}.dat").touch()

        sparse_peak = warm_peak(lambda: drain(sparse.rglob("*.none")))
        crowded_peak = warm_peak(lambda: drain(crowded.rglob("*.none")))
        ratio = crowded_peak / sparse_peak

        if sys.version_info >= (3, 12):
            assert ratio < 4, f"{sparse_peak} B against {crowded_peak} B"
        else:
            assert ratio > 6, f"{sparse_peak} B against {crowded_peak} B"

    def test_a_pattern_ending_in_double_star_yields_files_from_313(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "f.txt").touch()

        found = {p.relative_to(tmp_path).as_posix() for p in tmp_path.glob("**")}

        assert ("a/f.txt" in found) is (sys.version_info >= (3, 13)), found
        assert "a" in found


@pytest.mark.skipif(sys.version_info < (3, 12), reason="Path.walk() is 3.12+")
class TestWalkSpace:
    """`Path.walk()` | O(E) | O(w + P); bottom-up also holds every ancestor's
    listing until its subtree is done."""

    def test_the_peak_grows_with_the_sibling_count(self, tmp_path: pathlib.Path) -> None:
        small = make_wide_dirs(tmp_path, 200)
        large = make_wide_dirs(tmp_path, 800)

        small_peak = peak_bytes(lambda: drain(small.walk()))  # type: ignore[attr-defined]
        large_peak = peak_bytes(lambda: drain(large.walk()))  # type: ignore[attr-defined]

        assert large_peak > 2.5 * small_peak, f"{small_peak} B against {large_peak} B"

    def test_bottom_up_holds_the_ancestors_listings(self, tmp_path: pathlib.Path) -> None:
        chain = make_chain(tmp_path, "chain", 50, files_per_level=100)

        top_down = warm_peak(lambda: drain(chain.walk()))  # type: ignore[attr-defined]
        bottom_up = warm_peak(lambda: drain(chain.walk(top_down=False)))  # type: ignore[attr-defined]

        assert bottom_up > 8 * top_down, f"{top_down} B against {bottom_up} B"

    def test_walk_visits_every_directory_once(self, tmp_path: pathlib.Path) -> None:
        wide = make_wide_dirs(tmp_path, 20)
        (wide / "d00000" / "leaf.txt").touch()

        visited = list(wide.walk())  # type: ignore[attr-defined]
        directories = [directory for directory, _, _ in visited]

        assert len(directories) == len(set(directories)) == 21
        assert set(directories) == {wide, *(p for p in wide.iterdir() if p.is_dir())}
        assert sum(len(files) for _, _, files in visited) == 1


class TestMkdirParents:
    """`Path.mkdir()` | O(1); O(k·L) with parents=True, recursing per component."""

    def test_each_missing_component_costs_a_call(self, tmp_path: pathlib.Path) -> None:
        with counting_syscalls() as counter:
            (tmp_path / "one").mkdir()
        plain = counter.counts["mkdir"]

        with counting_syscalls() as counter:
            (tmp_path / "a" / "b" / "c" / "d" / "e").mkdir(parents=True)
        nested = counter.counts["mkdir"]

        assert plain == 1
        assert 5 <= nested <= 10, f"five missing components, {nested} mkdir calls"
        assert (tmp_path / "a" / "b" / "c" / "d" / "e").is_dir()

    def test_the_peak_grows_faster_than_the_depth(self, tmp_path: pathlib.Path) -> None:
        """7x the missing components of fixed length: over x12, where O(k)
        would give x7 and O(k·L) x49."""
        peaks = []
        for depth in (100, 700):
            top = tmp_path / f"m{depth}"
            top.mkdir()
            target = top.joinpath(*["dd"] * depth)
            str(target)
            peaks.append(peak_bytes(lambda t=target: t.mkdir(parents=True)))
            assert target.is_dir()
            remove_deep(top)

        assert peaks[1] > 12 * peaks[0], f"7x the depth: {peaks}"


class TestFileIO:
    """The read and write rows: O(b) time, O(b) space except `write_bytes()`."""

    def test_text_round_trips(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        payload = "x" * 100_000

        target.write_text(payload, encoding="utf-8")

        assert target.stat().st_size == len(payload)
        assert target.read_text(encoding="utf-8") == payload

    def test_read_holds_the_whole_file(self, tmp_path: pathlib.Path) -> None:
        small = tmp_path / "small.txt"
        large = tmp_path / "large.txt"
        small.write_text("x" * 10_000, encoding="utf-8")
        large.write_text("x" * 800_000, encoding="utf-8")

        small_peak = peak_bytes(lambda: small.read_text(encoding="utf-8"))
        large_peak = peak_bytes(lambda: large.read_text(encoding="utf-8"))

        assert large_peak > 10 * small_peak, f"{small_peak} B against {large_peak} B"

    def test_write_text_encodes_the_whole_string(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        text = "x" * (1 << 23)

        assert peak_bytes(lambda: target.write_text(text, encoding="utf-8")) > 1 << 23

    def test_write_bytes_does_not_copy_the_buffer(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.bin"
        small, large = b"x" * (1 << 20), b"x" * (1 << 23)
        target.write_bytes(small)

        small_peak = peak_bytes(lambda: target.write_bytes(small))
        large_peak = peak_bytes(lambda: target.write_bytes(large))

        assert large_peak < 1.5 * small_peak + 1_000, f"{small_peak} B against {large_peak} B"
        assert target.stat().st_size == 1 << 23


class TestLinkAndRenameRows:
    """`readlink()`, `is_symlink()`, `rename()` and `replace()`."""

    @POSIX_ONLY
    def test_readlink_returns_the_target_it_was_given(self, tmp_path: pathlib.Path) -> None:
        short_link, long_link = tmp_path / "short", tmp_path / "long"
        short_link.symlink_to("a")
        long_link.symlink_to("b" * 200)

        assert str(short_link.readlink()) == "a"
        assert len(str(long_link.readlink())) == 200

    @POSIX_ONLY
    def test_is_symlink_describes_the_link_not_its_target(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("0123456789", encoding="utf-8")
        link = tmp_path / "link"
        link.symlink_to(target)

        assert link.is_symlink()
        assert link.stat().st_size == 10
        assert link.lstat().st_size != 10

    def test_rename_and_replace_move_without_copying(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "a.txt"
        source.write_text("payload", encoding="utf-8")
        inode = source.stat().st_ino

        destination = source.rename(tmp_path / "b.txt")

        assert destination.stat().st_ino == inode, "a rename keeps the inode"
        assert not source.exists()

        other = tmp_path / "c.txt"
        other.write_text("other", encoding="utf-8")
        other_inode = other.stat().st_ino
        other.replace(destination)

        assert destination.read_text(encoding="utf-8") == "other"
        assert destination.stat().st_ino == other_inode, "a replace keeps the inode"
        assert not other.exists()


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Path.copy() is 3.14+")
class TestCopyStreamsAndMoveRenames:
    """`Path.copy()` | O(b) | O(1) for a file; `Path.move()` | O(1) on one
    filesystem."""

    def test_copy_holds_a_constant_however_large_the_file(self, tmp_path: pathlib.Path) -> None:
        small, large = tmp_path / "small", tmp_path / "large"
        small.write_bytes(b"x" * (1 << 20))
        large.write_bytes(b"x" * (1 << 23))
        destination = tmp_path / "out"

        def copy(source: pathlib.Path) -> None:
            source.copy(destination)  # type: ignore[attr-defined]
            destination.unlink()

        copy(small)
        small_peak = peak_bytes(lambda: copy(small))
        large_peak = peak_bytes(lambda: copy(large))

        assert large_peak < 1.5 * small_peak, f"{small_peak} B against {large_peak} B"

    def test_copy_takes_a_directory_tree(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "src"
        (source / "a").mkdir(parents=True)
        (source / "a" / "f.txt").write_text("x", encoding="utf-8")

        copied = source.copy(tmp_path / "dst")  # type: ignore[attr-defined]

        assert (copied / "a" / "f.txt").read_text(encoding="utf-8") == "x"

    def test_move_renames_on_one_filesystem(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "report.txt"
        source.write_text("contents", encoding="utf-8")
        inode = source.stat().st_ino

        moved = source.move(tmp_path / "archive.txt")  # type: ignore[attr-defined]

        assert moved.stat().st_ino == inode
        assert not source.exists()

    def test_copy_into_and_move_into_take_a_directory(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "f.txt"
        source.write_text("contents", encoding="utf-8")
        first, second = tmp_path / "d", tmp_path / "e"
        first.mkdir()
        second.mkdir()

        source.copy_into(first)  # type: ignore[attr-defined]
        source.move_into(second)  # type: ignore[attr-defined]

        assert (first / "f.txt").read_text(encoding="utf-8") == "contents"
        assert (second / "f.txt").exists()
        assert not source.exists()


class TestVersionNotes:
    """Each API the Version Notes date, checked against this interpreter."""

    ADDED: dict[str, tuple[int, int]] = {
        "walk": (3, 12),
        "is_junction": (3, 12),
        "with_segments": (3, 12),
        "from_uri": (3, 13),
        "full_match": (3, 13),
        "parser": (3, 13),
        "copy": (3, 14),
        "copy_into": (3, 14),
        "move": (3, 14),
        "move_into": (3, 14),
        "info": (3, 14),
    }

    def test_the_apis_appear_when_the_page_says_they_do(self) -> None:
        for name, version in self.ADDED.items():
            assert hasattr(pathlib.Path, name) is (sys.version_info >= version), name
        assert hasattr(pathlib, "UnsupportedOperation") is (sys.version_info >= (3, 13))

    def test_link_to_is_gone_from_312(self) -> None:
        assert hasattr(pathlib.Path, "link_to") is (sys.version_info < (3, 12))
        assert hasattr(pathlib.Path, "hardlink_to")

    def test_pathlib_types_arrives_in_314(self) -> None:
        try:
            import pathlib.types  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            found = False
        else:
            found = True

        assert found is (sys.version_info >= (3, 14))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="UnsupportedOperation is 3.13+")
    def test_unsupported_operation_is_a_not_implemented_error(self) -> None:
        assert issubclass(pathlib.UnsupportedOperation, NotImplementedError)  # type: ignore[attr-defined]


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


def _needs(source: str) -> tuple[int, int]:
    """The newest release any API in the block needs."""
    versions = [version for marker, (version, _) in LATER_MARKERS.items() if marker in source]
    return max(versions, default=(3, 10))


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
    """Each block runs in its own subprocess and working directory and asserts
    its own result; a block needing a newer interpreter is skipped, by count."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS
        for marker, (_, count) in LATER_MARKERS.items():
            using = [line for line, source in blocks if marker in source]
            assert len(using) == count, f"{marker}: {using}"

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = skipped = 0
        for line, source in _blocks():
            if sys.version_info < _needs(source):
                skipped += 1
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran + skipped == EXPECTED_BLOCKS
        assert ran >= EXPECTED_BLOCKS - sum(count for _, count in LATER_MARKERS.values())
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert str(path) is text" in s)
        mutated = source.replace("assert str(path) is text", "assert str(path) is not text", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
