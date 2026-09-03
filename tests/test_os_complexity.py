"""Tests to verify documented behaviour of the os module.

Almost everything here is counted rather than timed: a syscall is observable,
so the page's claims about how many of them an operation makes need no
tolerance. os.stat, os.lstat and os.getcwd are wrapped for the duration of a
call and restored afterwards.

Two space bounds did not survive measurement:

* os.walk was documented O(d) for depth d, with a note that mentioned pending
  directories without counting them. The queued entries are a term of their
  own: at a fixed depth, 4x the siblings costs about 4x the peak on every
  supported version (x3.57 on 3.11, x3.89 on 3.14). Depth costs too, and how
  much depends on the version - gh-89727 replaced the recursive _walk() with
  an explicit stack in 3.12, so 3.11 spends a generator frame per level and
  raises RecursionError on a tree 2,000 deep where 3.12, 3.13 and 3.14 walk it.
  Neither term dominates on every version, so the page claims neither.
* os.makedirs was documented O(1) space, and the frames are only half of why
  that is wrong: each recursive frame keeps its own prefix of the path, so at
  a fixed depth of 100 the peak still rises from 17.5 KB to 118.6 KB as the
  components grow from 1 to 20 characters. The bound is O(n·L) for n
  components and a path of length L, and a deep enough path raises
  RecursionError besides - at depth 1,200 on both 3.11 and 3.14.
* os.removedirs was documented O(1) space too. It is iterative, which is why
  it holds one prefix rather than all of them, but each prefix is still O(L):
  799 B against 6,605 B for the same two component lengths. Iteration bounds
  how many are live at once, not how large they are.
* Both were documented O(n) time, which cannot be right beside an O(n·L)
  space bound - the characters have to be produced before they can be held.
  Counted at os.path.split, the parsing tracks n·L exactly: doubling the
  depth multiplies it by 3.8, and at a fixed depth it follows the path length
  (x4.79 for a 5.1x path, x3.19 for a 3.23x one). removedirs parses the same
  characters as makedirs, so both rows carry O(n·L) time and only the space
  differs.

The Path Operations table listed realpath among what are otherwise string
operations. Counted, realpath makes one lstat per component (4, 6, 10 and 18
calls at depths 2, 4, 8 and 16) and abspath makes one getcwd call for a
relative path, while join, split, dirname, basename, splitext and normpath
make none.

Both efficiency claims in Performance Notes hold exactly: listing 55 entries
costs 55 stat calls through listdir plus os.path.isfile and none at all
through scandir plus entry.is_file(), and the "two stat calls" the page warns
about are exactly two against one.

Code blocks: ten on the page. Nine are run, and the tenth is held back
because it calls shutil.rmtree on an absolute path - not something to run
from a test even against a path that should not exist. Of the nine, three
stop on FileNotFoundError because the page illustrates with absolute
placeholder paths (/path/to/dir, /path/to/file, /new/directory) that cannot
be created without root; the rest tolerate a missing path, since
os.path.exists returns False, os.walk yields nothing, and the last block
catches FileNotFoundError by design. The runner asserts that outcome rather
than classifying blocks by their text, so a NameError anywhere still fails.
The operations the placeholder blocks show are covered against tmp_path.

Not settled by execution:

* "Windows: Some path operations differ" and the POSIX/Windows split under
  Platform Differences. This suite runs on one platform at a time; the
  os.getuid and os.symlink tests below are POSIX-only and skip elsewhere.
* "PyPy"-style implementation claims do not appear here, but "O(1)" for a
  syscall is a choice of unit: the kernel still resolves the path component
  by component. The page counts a syscall as constant and these tests follow
  that convention rather than measuring the kernel.
"""

import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import tracemalloc
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "os.md"

EXPECTED_BLOCKS = 10
# One block calls shutil.rmtree on an absolute path. It is never run here, and
# the count is asserted so the exclusion cannot quietly widen.
DESTRUCTIVE_MARKER = "shutil.rmtree("
EXPECTED_DESTRUCTIVE_BLOCKS = 1
# Of the nine that do run, these three reach a placeholder path through a call
# that raises on a missing one; the rest tolerate it (os.path.exists returns
# False, os.walk yields nothing, and one block catches FileNotFoundError).
EXPECTED_MISSING_PATH_BLOCKS = 3

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX-only behaviour")


class SyscallCounter:
    """Counts the filesystem syscalls os.path helpers make."""

    def __init__(self) -> None:
        self.stat = 0
        self.lstat = 0
        self.getcwd = 0

    @property
    def total(self) -> int:
        return self.stat + self.lstat + self.getcwd


@contextmanager
def counting_syscalls() -> Iterator[SyscallCounter]:
    """Wrap os.stat, os.lstat and os.getcwd for the duration of the block."""
    counter = SyscallCounter()
    real_stat, real_lstat, real_getcwd = os.stat, os.lstat, os.getcwd

    def stat(*args: Any, **kwargs: Any) -> Any:
        counter.stat += 1
        return real_stat(*args, **kwargs)

    def lstat(*args: Any, **kwargs: Any) -> Any:
        counter.lstat += 1
        return real_lstat(*args, **kwargs)

    def getcwd() -> str:
        counter.getcwd += 1
        return real_getcwd()

    os.stat, os.lstat, os.getcwd = stat, lstat, getcwd  # type: ignore[assignment]
    try:
        yield counter
    finally:
        os.stat, os.lstat, os.getcwd = real_stat, real_lstat, real_getcwd  # type: ignore[assignment]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def make_wide(root: pathlib.Path, count: int) -> pathlib.Path:
    """One directory holding `count` empty subdirectories."""
    wide = root / f"wide{count}"
    wide.mkdir()
    for index in range(count):
        (wide / f"d{index:05d}").mkdir()
    return wide


def make_deep(root: pathlib.Path, depth: int) -> pathlib.Path:
    """A chain of `depth` directories, one per level."""
    deep = root / f"deep{depth}"
    deep.mkdir()
    node = deep
    for _ in range(depth):
        node = node / "d"
        node.mkdir()
    return deep


def remove_deep(root: pathlib.Path) -> None:
    """Unwind a chain from the bottom.

    shutil.rmtree recurses, so the chains built here are removed before the
    test ends rather than left for it - on 3.11 a deep enough tree breaks its
    own cleanup as readily as it breaks os.walk.
    """
    node = root
    while True:
        children = [child for child in node.iterdir() if child.is_dir()]
        if not children:
            break
        node = children[0]
    while node != root.parent:
        node.rmdir()
        node = node.parent


def drain(iterator: Any) -> None:
    """Exhaust an iterator without retaining what it yields.

    A list comprehension would grow with the tree and land in the traced peak,
    which is a measurement of the collector rather than of os.walk.
    """
    deque(iterator, maxlen=0)


class TestCountingHarness:
    """The counter has to see real calls, or every count below is vacuous."""

    def test_the_counter_sees_stat_calls(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f"
        target.write_text("x", encoding="utf-8")

        with counting_syscalls() as counter:
            os.stat(target)
            os.stat(target)

        assert counter.stat == 2

    def test_the_counter_is_restored_afterwards(self, tmp_path: pathlib.Path) -> None:
        before = os.stat
        with counting_syscalls():
            assert os.stat is not before
        assert os.stat is before


# gh-89727 rewrote _walk() around an explicit stack; the commit first ships in
# v3.12.0, and 3.11 is the only supported version that still recurses.
WALK_IS_ITERATIVE = sys.version_info >= (3, 12)


def frame_depth() -> int:
    """How many Python frames are currently on the stack."""
    depth, frame = 0, sys._getframe()
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth


class TestWalkSpaceNeedsBothTerms:
    """`os.walk(path)` | O(n) | O(w + d) - neither term can be dropped.

    The page said O(d). Breadth is missing from that, and it is the term that
    behaves the same on every supported version: 4x the siblings costs about
    4x the peak on 3.11 (x3.57) and on 3.14 (x3.89).

    Depth is the term that changed. On 3.11 _walk() recurses with `yield from`,
    so each level is a generator frame and 4x the depth costs 5.1x; from 3.12
    the walk drives an explicit stack and the same step costs 1.75x. Which term
    dominates therefore depends on the version, which is why neither the page
    nor these tests claim one outweighs the other.
    """

    def test_peak_grows_with_the_sibling_count(self, tmp_path: pathlib.Path) -> None:
        """The w term, at a fixed depth of 1."""
        small = make_wide(tmp_path, 200)
        large = make_wide(tmp_path, 800)

        small_peak = peak_bytes(lambda: drain(os.walk(small)))
        large_peak = peak_bytes(lambda: drain(os.walk(large)))

        assert large_peak > 2.5 * small_peak, (
            f"4x the siblings should cost about 4x, so O(d) alone cannot be the "
            f"bound: {small_peak} B against {large_peak} B"
        )

    def test_peak_grows_with_the_depth(self, tmp_path: pathlib.Path) -> None:
        """The d term, at a fixed breadth of 1.

        16x rather than 4x: draining the walk leaves 3.14's depth term at
        x1.57 over 50..200, too close to any threshold that also excludes a
        constant. Over 50..800 it is x3.78 on 3.14 and x39.9 on 3.11.
        """
        shallow = make_deep(tmp_path, 50)
        nested = make_deep(tmp_path, 800)

        shallow_peak = peak_bytes(lambda: drain(os.walk(shallow)))
        nested_peak = peak_bytes(lambda: drain(os.walk(nested)))
        remove_deep(nested)

        assert nested_peak > 2.0 * shallow_peak, (
            f"16x the depth should cost more: {shallow_peak} B against {nested_peak} B"
        )

    def test_walk_recurses_only_on_311(self, tmp_path: pathlib.Path) -> None:
        """The Version Note, measured at the depth scandir is called from.

        Exhausting the stack would settle this too, but only with a tree deep
        enough that shutil.rmtree - itself recursive - cannot clean it up
        afterwards on 3.11. Recording the frame depth at each scandir call
        needs 40 directories instead of 2,000: recursion makes that depth grow
        one frame per level, and the stack-based walk holds it flat.
        """
        depth = 40
        nested = make_deep(tmp_path, depth)
        real_scandir = os.scandir
        depths: list[int] = []

        def probe(path: Any) -> Any:
            depths.append(frame_depth())
            return real_scandir(path)

        os.scandir = probe  # type: ignore[assignment]
        try:
            drain(os.walk(nested))
        finally:
            os.scandir = real_scandir  # type: ignore[assignment]

        assert len(depths) == depth + 1, f"expected one scandir per directory, got {len(depths)}"
        spread = max(depths) - min(depths)
        if WALK_IS_ITERATIVE:
            assert spread == 0, f"an explicit stack should call scandir from one depth: {spread}"
        else:
            assert spread >= depth - 1, (
                f"3.11 recurses once per level, so the spread should track the depth: {spread}"
            )

    def test_walk_visits_every_entry(self, tmp_path: pathlib.Path) -> None:
        """O(n) time: the traversal is one visit per entry."""
        wide = make_wide(tmp_path, 20)
        (wide / "d00000" / "leaf.txt").write_text("x", encoding="utf-8")

        visited = list(os.walk(wide))

        assert len(visited) == 21, "the root plus each subdirectory"
        assert sum(len(files) for _, _, files in visited) == 1


class TestMakedirsRecurses:
    """`os.makedirs(path)` | O(n·L) | O(n·L), against removedirs' O(L) space.

    Both rows are about what is held, not about control flow: recursion is
    why makedirs holds every prefix at once, and iteration is why removedirs
    holds one - but iteration alone would not make it constant, since each
    prefix it builds is still O(L).
    """

    def test_makedirs_calls_itself_per_component(self, tmp_path: pathlib.Path) -> None:
        """Observed through the recursion limit rather than the source.

        A limit low enough to be crossed by the path's own depth turns the
        call into RecursionError, which an iterative implementation could not
        do. removedirs, listed beside it, survives the same treatment.
        """
        target = tmp_path.joinpath(*["y"] * 60)
        original_limit = sys.getrecursionlimit()

        sys.setrecursionlimit(80)
        try:
            with pytest.raises(RecursionError):
                os.makedirs(target)
        finally:
            sys.setrecursionlimit(original_limit)
            shutil.rmtree(tmp_path / "y", ignore_errors=True)

    def test_removedirs_is_iterative(self, tmp_path: pathlib.Path) -> None:
        """It unwinds without recursing - which is not the same as O(1) space."""
        depth = 60
        target = tmp_path.joinpath(*["z"] * depth)
        os.makedirs(target)

        original_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(80)
        try:
            os.removedirs(target)
        finally:
            sys.setrecursionlimit(original_limit)

        assert not (tmp_path / "z").exists(), "removedirs should have unwound the chain"

    def test_makedirs_keeps_every_prefix_at_once(self, tmp_path: pathlib.Path) -> None:
        """The L in O(n·L): frames hold prefixes, not just frames.

        Depth is held at 100 and the components lengthened, so a bound counting
        only frames predicts no change. Measured 17.5 KB, 42.8 KB and 118.6 KB
        for components of 1, 5 and 20 characters.
        """
        peaks = []
        for length in (1, 20):
            target = tmp_path.joinpath(f"c{length}", *["y" * length] * 100)
            peaks.append(peak_bytes(lambda target=target: os.makedirs(target)))
            remove_deep(tmp_path / f"c{length}")

        assert peaks[1] > 3 * peaks[0], (
            f"longer components should cost more at the same depth, so the frames "
            f"are not the whole bound: {peaks} bytes for 1 and 20 character components"
        )

    def test_removedirs_holds_one_prefix_at_a_time(self, tmp_path: pathlib.Path) -> None:
        """The contrast: O(L), not O(n·L) and not O(1).

        Peak follows the path length (799 B against 6,605 B for 1 and 20
        character components at depth 100) but grows only linearly with depth,
        where makedirs grows faster than linearly.
        """
        by_length = []
        for length in (1, 20):
            target = tmp_path.joinpath(f"r{length}", *["y" * length] * 100)
            os.makedirs(target)
            by_length.append(peak_bytes(lambda target=target: os.removedirs(target)))

        assert by_length[1] > 3 * by_length[0], (
            f"removedirs allocates per path length, so O(1) is not the bound: "
            f"{by_length} bytes for 1 and 20 character components"
        )

        by_depth = []
        for depth in (100, 400):
            target = tmp_path.joinpath(f"d{depth}", *["y"] * depth)
            os.makedirs(target)
            by_depth.append(peak_bytes(lambda target=target: os.removedirs(target)))

        assert by_depth[1] < 8 * by_depth[0], (
            f"4x the depth should cost about 4x, not more: {by_depth} bytes"
        )

    def test_makedirs_creates_every_component(self, tmp_path: pathlib.Path) -> None:
        """The components are created from the top down, all of them."""
        target = tmp_path / "a" / "b" / "c" / "d"

        os.makedirs(target)

        assert target.is_dir()
        assert (tmp_path / "a" / "b").is_dir()


class TestDirectoryHelperTimeIsPathWork:
    """The O(n·L) time on both rows, counted rather than timed.

    Both helpers split the path once per component, and each split processes a
    prefix, so the characters they hand to os.path.split are the work. Timing
    cannot separate that from the syscalls here - 16x the path length at a
    fixed depth moves makedirs by 25% - but the character count is exact.

    removedirs does the same split work as makedirs. Iteration changes how
    many prefixes are live at once, which is the space column; it does not
    change how many characters get parsed.
    """

    @staticmethod
    @contextmanager
    def _counting_split() -> Iterator[list[int]]:
        """Record the length of every path handed to os.path.split."""
        lengths: list[int] = []
        real_split = os.path.split

        def split(path: Any) -> Any:
            lengths.append(len(os.fspath(path)))
            return real_split(path)

        os.path.split = split  # type: ignore[assignment]
        try:
            yield lengths
        finally:
            os.path.split = real_split  # type: ignore[assignment]

    def test_the_split_counter_sees_calls(self, tmp_path: pathlib.Path) -> None:
        with self._counting_split() as lengths:
            os.path.split(tmp_path / "a" / "b")

        assert len(lengths) == 1, "the counter has to see the call it wraps"

    def test_makedirs_parses_more_than_linearly_in_the_depth(self, tmp_path: pathlib.Path) -> None:
        """2x the components is about 4x the characters parsed."""
        totals = []
        for depth in (100, 200):
            target = tmp_path.joinpath(f"d{depth}", *["y"] * depth)
            with self._counting_split() as lengths:
                os.makedirs(target)
            totals.append(sum(lengths))
            remove_deep(tmp_path / f"d{depth}")

        assert totals[1] > 3 * totals[0], (
            f"doubling the depth should more than double the parsing, so O(n) "
            f"cannot be the time bound: {totals} characters"
        )

    def test_makedirs_parses_in_proportion_to_the_path_length(self, tmp_path: pathlib.Path) -> None:
        """The L term, with the component count held at 100."""
        totals = []
        for length in (1, 35):
            target = tmp_path.joinpath(f"c{length}", *["y" * length] * 100)
            with self._counting_split() as lengths:
                os.makedirs(target)
            totals.append(sum(lengths))
            remove_deep(tmp_path / f"c{length}")

        assert totals[1] > 8 * totals[0], (
            f"the same number of components over a 16x longer path should parse "
            f"far more: {totals} characters"
        )

    def test_removedirs_parses_just_as_much(self, tmp_path: pathlib.Path) -> None:
        """Iteration buys space, not time: the split work is the same."""
        depth = 200
        target = tmp_path.joinpath("r", *["y"] * depth)

        # The creating call, not a second one: makedirs(exist_ok=True) over an
        # existing tree stops at the first head that exists, and splits once.
        with self._counting_split() as made:
            os.makedirs(target)
        with self._counting_split() as removed:
            os.removedirs(target)

        # Not byte-identical: makedirs stops at the first head that already
        # exists, while removedirs splits on until rmdir refuses, which is a
        # few components more. The claim is the shared bound, not equality.
        ratio = sum(removed) / sum(made)
        assert 0.9 < ratio < 1.1, (
            f"removedirs should parse about what makedirs parses: "
            f"{sum(removed)} against {sum(made)} characters"
        )


class TestPathOperationsAreStringWork:
    """The Path Operations table, and the sentence added below it."""

    PURE = ("join", "split", "dirname", "basename", "splitext", "normpath")

    def test_the_string_operations_touch_no_filesystem(self, tmp_path: pathlib.Path) -> None:
        sample = str(tmp_path / "a" / "b" / "c.txt")
        calls = {
            "join": lambda: os.path.join(sample, "x", "y"),
            "split": lambda: os.path.split(sample),
            "dirname": lambda: os.path.dirname(sample),
            "basename": lambda: os.path.basename(sample),
            "splitext": lambda: os.path.splitext(sample),
            "normpath": lambda: os.path.normpath(sample + "/../d"),
        }

        for name in self.PURE:
            with counting_syscalls() as counter:
                calls[name]()
            assert counter.total == 0, f"os.path.{name} made {counter.total} syscalls"

    def test_abspath_calls_getcwd_only_for_a_relative_path(self) -> None:
        with counting_syscalls() as relative:
            os.path.abspath("some/relative/path")
        with counting_syscalls() as absolute:
            os.path.abspath("/already/absolute/path")

        assert relative.getcwd == 1, f"expected one getcwd, got {relative.getcwd}"
        assert absolute.getcwd == 0, "an absolute path needs no getcwd"

    @POSIX_ONLY
    def test_realpath_stats_once_per_component(self, tmp_path: pathlib.Path) -> None:
        """The claim the table was missing: realpath is not string work."""
        counts = []
        for depth in (2, 4, 8):
            target = tmp_path.joinpath(f"r{depth}", *["d"] * depth)
            os.makedirs(target)
            with counting_syscalls() as counter:
                os.path.realpath(target)
            counts.append(counter.lstat)

        assert counts[0] < counts[1] < counts[2], (
            f"realpath should cost more per component: {counts} lstat calls at depths 2, 4, 8"
        )
        # Each extra component adds one lstat, so 4 more components add about 4.
        assert counts[2] - counts[0] >= 4, f"expected growth with the component count: {counts}"

    @POSIX_ONLY
    def test_realpath_resolves_a_symlink(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "real.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        assert os.path.realpath(link) == str(target)
        assert os.path.normpath(link) == str(link), "normpath does not resolve links"


class TestEfficientFileListing:
    """Performance Notes: scandir carries the file type, listdir does not."""

    ENTRIES = 55

    @staticmethod
    def _populate(root: pathlib.Path, files: int, dirs: int) -> None:
        for index in range(files):
            (root / f"f{index}.txt").write_text("x", encoding="utf-8")
        for index in range(dirs):
            (root / f"sub{index}").mkdir()

    def test_listdir_needs_a_stat_per_entry(self, tmp_path: pathlib.Path) -> None:
        self._populate(tmp_path, files=50, dirs=5)

        with counting_syscalls() as counter:
            [name for name in os.listdir(tmp_path) if os.path.isfile(tmp_path / name)]

        assert counter.stat == self.ENTRIES, (
            f"one stat per entry was expected, got {counter.stat} for {self.ENTRIES} entries"
        )

    def test_scandir_needs_none(self, tmp_path: pathlib.Path) -> None:
        """entry.is_file() answers from the directory entry itself.

        DirEntry_test_mode in Modules/posixmodule.c sets need_stat only when
        `d_type == DT_UNKNOWN` or a symlink is being followed, so this is zero
        on any filesystem that reports a type in its directory entries. A
        filesystem that reports DT_UNKNOWN would make it one stat per entry
        without the page being wrong, which is what the message says.
        """
        self._populate(tmp_path, files=50, dirs=5)

        with counting_syscalls() as counter:
            with os.scandir(tmp_path) as entries:
                [entry.name for entry in entries if entry.is_file()]

        assert counter.stat == 0, (
            f"scandir should not stat: {counter.stat} calls. If this filesystem "
            f"reports DT_UNKNOWN, is_file() must stat and the count is expected"
        )

    def test_both_listings_agree(self, tmp_path: pathlib.Path) -> None:
        self._populate(tmp_path, files=50, dirs=5)

        by_listdir = sorted(n for n in os.listdir(tmp_path) if os.path.isfile(tmp_path / n))
        with os.scandir(tmp_path) as entries:
            by_scandir = sorted(entry.name for entry in entries if entry.is_file())

        assert by_listdir == by_scandir

    def test_listdir_builds_a_list_and_scandir_does_not(self, tmp_path: pathlib.Path) -> None:
        """The O(n) against O(1) space rows for the two functions."""
        self._populate(tmp_path, files=2_000, dirs=0)

        listdir_peak = peak_bytes(lambda: os.listdir(tmp_path))

        def one_entry_at_a_time() -> None:
            with os.scandir(tmp_path) as entries:
                for _ in entries:
                    pass

        scandir_peak = peak_bytes(one_entry_at_a_time)

        assert listdir_peak > 3 * scandir_peak, (
            f"listdir holds every name at once: {listdir_peak} B against {scandir_peak} B"
        )


class TestAvoidingUnnecessaryStats:
    """Performance Notes: two stat calls against one."""

    def test_exists_then_getsize_stats_twice(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("content", encoding="utf-8")

        with counting_syscalls() as counter:
            if os.path.exists(target) and os.path.getsize(target) > 0:
                pass

        assert counter.stat == 2, f"the page calls this two stat calls, got {counter.stat}"

    def test_getsize_alone_stats_once(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("content", encoding="utf-8")

        with counting_syscalls() as counter:
            try:
                if os.path.getsize(target) > 0:
                    pass
            except FileNotFoundError:
                pass

        assert counter.stat == 1, f"the page calls this one stat call, got {counter.stat}"

    def test_the_one_stat_form_still_handles_a_missing_file(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            os.path.getsize(tmp_path / "absent.txt")


class TestSingleSyscallOperations:
    """The O(1) rows: one syscall each, whatever the directory holds."""

    def test_metadata_helpers_make_one_stat_each(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("content", encoding="utf-8")
        helpers = {
            "exists": os.path.exists,
            "isfile": os.path.isfile,
            "isdir": os.path.isdir,
            "getsize": os.path.getsize,
            "getmtime": os.path.getmtime,
            "getatime": os.path.getatime,
            "getctime": os.path.getctime,
        }

        for name, helper in helpers.items():
            with counting_syscalls() as counter:
                helper(target)
            assert counter.stat == 1, f"os.path.{name} made {counter.stat} stat calls"

    def test_a_crowded_directory_does_not_change_the_cost(self, tmp_path: pathlib.Path) -> None:
        """O(1) means the neighbours do not matter."""
        crowded = tmp_path / "crowded"
        crowded.mkdir()
        for index in range(500):
            (crowded / f"n{index}.txt").write_text("x", encoding="utf-8")
        target = crowded / "n0.txt"

        with counting_syscalls() as counter:
            os.path.getsize(target)

        assert counter.stat == 1, f"still one stat among 500 neighbours, got {counter.stat}"

    @POSIX_ONLY
    def test_lstat_does_not_follow_the_link(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "real.txt"
        target.write_text("0123456789", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        assert os.stat(link).st_size == 10, "stat follows the link"
        assert os.lstat(link).st_size != 10, "lstat describes the link itself"
        assert os.path.islink(link)

    def test_rename_and_replace_move_without_copying(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "a.txt"
        source.write_text("payload", encoding="utf-8")
        destination = tmp_path / "b.txt"

        os.rename(source, destination)

        assert destination.read_text(encoding="utf-8") == "payload"
        assert not source.exists()

        other = tmp_path / "c.txt"
        other.write_text("other", encoding="utf-8")
        os.replace(other, destination)

        assert destination.read_text(encoding="utf-8") == "other"


class TestReadlinkLength:
    """`os.readlink(path)` | O(n) | O(n) | n = length of the target."""

    @POSIX_ONLY
    def test_readlink_returns_the_target_it_was_given(self, tmp_path: pathlib.Path) -> None:
        short_target = "a"
        long_target = "b" * 200
        short_link, long_link = tmp_path / "short", tmp_path / "long"
        short_link.symlink_to(short_target)
        long_link.symlink_to(long_target)

        assert os.readlink(short_link) == short_target
        assert len(os.readlink(long_link)) == len(long_target)


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


def _is_destructive(source: str) -> bool:
    """The one block that would delete a tree if its path happened to exist."""
    return DESTRUCTIVE_MARKER in source


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block either runs or fails only for its placeholder path.

    Asserting the outcome rather than pre-classifying by content is what makes
    this catch a real defect: a NameError or a syntax error in any block is a
    failure that is not FileNotFoundError, and no allowance covers it.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        destructive = [line for line, source in blocks if _is_destructive(source)]
        assert len(destructive) == EXPECTED_DESTRUCTIVE_BLOCKS, (
            f"expected {EXPECTED_DESTRUCTIVE_BLOCKS} block to hold back, found {destructive}"
        )

    def test_blocks_run_or_fail_only_on_a_missing_path(self, tmp_path: pathlib.Path) -> None:
        unexpected: list[str] = []
        missing_path: list[int] = []
        ran = 0

        for line, source in _blocks():
            if _is_destructive(source):
                continue
            ran += 1
            result = _run(source, tmp_path)
            if result.returncode == 0:
                continue
            if "FileNotFoundError" in result.stderr:
                missing_path.append(line)
            else:
                unexpected.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not unexpected, "\n".join(unexpected)
        assert ran == EXPECTED_BLOCKS - EXPECTED_DESTRUCTIVE_BLOCKS, (
            f"ran {ran} blocks, expected {EXPECTED_BLOCKS - EXPECTED_DESTRUCTIVE_BLOCKS}"
        )
        assert len(missing_path) == EXPECTED_MISSING_PATH_BLOCKS, (
            f"expected {EXPECTED_MISSING_PATH_BLOCKS} blocks to stop on a placeholder "
            f"path, found {missing_path}"
        )

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        runnable = [source for _, source in _blocks() if not _is_destructive(source)]
        original = runnable[0]
        broken = original.replace("import os\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr


class TestDocumentedOutputs:
    """The values the Path Manipulation block states in comments."""

    def test_join_split_and_splitext(self) -> None:
        path = os.path.join("/home", "user", "documents", "file.txt")
        dirname, filename = os.path.split(path)

        assert dirname == "/home/user/documents"
        assert filename == "file.txt"

        name, ext = os.path.splitext("file.txt")
        assert name == "file"
        assert ext == ".txt"

    def test_abspath_of_a_relative_path_is_rooted_at_the_cwd(self, tmp_path: pathlib.Path) -> None:
        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            resolved = os.path.abspath("./relative/path")
        finally:
            os.chdir(original)

        assert resolved.endswith(os.path.join("relative", "path"))
        assert os.path.isabs(resolved)

    def test_environ_get_falls_back_to_the_default(self) -> None:
        assert os.environ.get("A_NAME_NOTHING_WOULD_SET", "unknown") == "unknown"
