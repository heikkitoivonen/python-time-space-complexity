"""Tests to verify documented behaviour of the os module.

Almost everything here is counted or observed rather than timed. Where a
documented cost is a syscall count, the syscall has to be reachable from
Python to be counted: os.stat, os.lstat, os.getcwd and os.path.split are
wrapped for the duration of a call and restored afterwards, which observes
every os.path helper because those are written in Python. It does not observe
anything posixmodule.c does internally - see TestCountingHarness, which pins
that limit so no later test is written as though the counter saw more than it
does.

The bounds that carry more than one term:

* os.walk is O(n) in time from 3.12 and O(P) in space. Timed with os.scandir
  replaced by synthetic entries and followlinks=True, so that neither scandir
  nor the os.path.islink() check makes a syscall, 4x the entries of a chain
  costs x4.37 from 3.12 - one visit per entry. Through 3.11 the same
  measurement gives x16.47: yield from forwards each result through one
  suspended frame per level, which is a factor of the depth, and a Python cost
  rather than a kernel one. On a real filesystem every version is dearer
  again, and a chain is about eight times slower than a wide tree of the same
  entry count - that part is the kernel resolving deeper paths, which this
  page counts as O(1) per call, so it belongs in the prose rather than the
  bound.
  Space is where entry count fails outright, and it changes sides at 3.12: the
  wide tree costs about ten times the chain from there (81,869 B against
  8,222 B on 3.14), where through 3.11 the chain costs about forty-seven times
  the wide tree (1,965,575 B against 41,561 B) because each suspended level
  holds its own path.
  On a real filesystem a chain's elapsed time does rise faster than its entry
  count on every version - x2.90, x3.54 and x3.76 per doubling over 100..800
  on 3.14, and x3.35, x3.98 and x4.02 on 3.11. Only the 3.11 part of that
  survives the syscalls being removed, which is what dates the rest to the
  kernel.
  Breadth alone behaves the same on every supported version: at a fixed depth,
  4x the siblings costs about 4x the peak (x3.57 on 3.11, x3.89 on 3.14).
  Depth's contribution to the peak is the part that changed - gh-89727
  replaced the recursive _walk() with an explicit stack in 3.12, so 3.10 and
  3.11 spend a generator frame per level and raise RecursionError on a tree
  2,000 deep where 3.12, 3.13 and 3.14 walk it. From 3.12 the depth term in
  the peak is the path strings, not the frames.
* os.makedirs is O(n·L) in space for n components and a path of length L. The
  frames are only half of it: each recursive frame keeps its own prefix of the
  path, so at a fixed depth of 40 the peak rises from 4,633 B to 71,134 B as
  the components grow from 1 to 80 characters. Enough *missing* components
  raise RecursionError besides - at 1,200 on both 3.11 and 3.14 - while a
  single new directory under an existing tree of any depth is one frame,
  because the recursion stops at the first head that already exists.
* os.removedirs is O(L). It is iterative, which is why it holds one prefix
  rather than all of them, but each prefix is still O(L): 799 B against 6,605 B
  for the same two component lengths. Iteration bounds how many are live at
  once, not how large they are.
* Both are O(n·L) in time as well, because the characters have to be produced
  before they can be held. Counted at os.path.split, the parsing tracks n·L
  exactly: doubling the depth multiplies it by 3.8, and at a fixed depth it
  follows the path length (x4.79 for a 5.1x path, x3.19 for a 3.23x one).
  removedirs parses the same characters as makedirs, so the two rows differ
  only in space.

os.path.realpath is bounded by neither the path it is given nor the one it
produces, but by the components it walks. Counted on inputs with no symlinks it
is one lstat per component (4, 6 and 10 calls at depths 2, 4 and 8), but a
two-component argument reaching a 12-deep target through one link costs 17, and
through a chain of eight links costs 38 - and those two resolve to the same
path, which is what rules the result out as the bound.
os.path.ismount inherits that through 3.12, where it always resolves the
parent with realpath() before comparing: 5 lstat calls for a shallow path
against 14 for one ten deep on 3.12, and 7 for the shallow case on 3.10. From
3.13 it lstats the parent directly and keeps realpath() as the fallback, which
holds it at two whatever the depth. The other filesystem entries in that table
are os.path.abspath at one getcwd for a relative path and os.path.samefile at
two stats; join, split, dirname, basename, splitext, normpath, isabs, normcase
and splitdrive make none.

Both efficiency claims in the narrative sections hold exactly: listing 55
entries costs 55 stat calls through listdir plus os.path.isfile, and none at
all through scandir plus entry.is_file(), which is shown by deleting the file
before asking - a DirEntry that answers True for an unlinked file answered
from the directory entry. That holds for a plain file; a symlink has to be
followed, and the page says so rather than claiming the loop never stats. The
"two stat calls" the page warns about are exactly two against one.

The environment rows are not O(1). A lookup encodes the key and decodes the
value, so reading a 2 MB value peaks at 2 MB and costs some 600x a short one,
and consuming os.environ.items() lists the keys before yielding any, so it
allocates per variable even when the caller keeps nothing: 1,084 B against
25,084 B for 3,000 more variables. Constructing the view itself really is
O(1) - 40 B either side of those 3,000 additions.

Code blocks: seven on the page, all of them run and all of them must exit
zero. Every path they touch is relative, so the runner's temporary working
directory is enough to make them real.

Not settled by execution:

* "O(1)" for a syscall is a choice of unit. The kernel still resolves a path
  component by component, and the page says so in its opening. These tests
  follow that convention rather than measuring the kernel, so a row reading
  O(1) for a single-syscall C function is checked for behaviour and for
  independence from the obvious size variable, not for its syscall count.
* os.getgrouplist and os.initgroups resolve through the platform's name
  service. A local file, a directory server over the network and a cache in
  front of either give three different costs for the same call, which is why
  the page states no bound and nothing here measures one.
* os.login_tty, which would take over this process's controlling terminal.
* The fork, exec, spawn, popen, system and wait families. Each one either
  replaces this process or leaves a child to reap, so they are excluded rather
  than isolated; os.register_at_fork is excluded with them because a handler
  registered here would outlive the test. os.abort and os._exit terminate the
  interpreter. Their rows are sourced from the argument vectors and
  environments they marshal, which is visible in Modules/posixmodule.c and in
  the PATH search in Lib/os.py, not from a run.
* os.sync, os.fsync and os.fdatasync block on however much dirty data exists,
  which is a property of the machine at that moment and not of the call.
* Whether os.putenv and os.unsetenv scale with the number of variables already
  in the environment. The C library's setenv() and unsetenv() do scan it, and
  at 20,000 variables both calls measure some 100x a small environment - but
  os.environ[key] = value, which reaches the same setenv(), measures flat over
  the same range. Two probes of one mechanism disagreeing is a reason to state
  the mechanism on the page and assert no ratio here.
* How os.closerange traverses its range. _Py_closerange prefers close_range(2)
  and falls back to a close() per descriptor, so a timing ratio would pin which
  branch the platform took rather than the row's bound.
* Platform-gated APIs this suite cannot reach on POSIX/Linux: os.startfile,
  os.add_dll_directory, os.get_handle_inheritable, os.set_handle_inheritable,
  os.listdrives, os.listvolumes, os.listmounts, os.path.isreserved, the
  Windows stat_result fields (st_file_attributes, st_reparse_tag), the BSD and
  macOS ones (st_flags, st_gen, st_rsize, st_creator, st_type, st_birthtime,
  st_birthtime_ns), os.chflags, os.lchflags, os.lchmod and os.plock. The
  POSIX-only tests below skip on Windows rather than assert.
"""

import os
import pathlib
import re
import shutil
import stat as stat_module
import subprocess
import sys
import textwrap
import time
import timeit
import tracemalloc
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "os.md"

# Every block on the page uses relative paths, so all of them run.
EXPECTED_BLOCKS = 7

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX-only behaviour")
LINUX_ONLY = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-only")
HAS_PROC_FD = pytest.mark.skipif(
    not os.path.isdir("/proc/self/fd"), reason="needs /proc/self/fd to count descriptors"
)


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
    test ends rather than left for it - before 3.12 a deep enough tree breaks
    its own cleanup as readily as it breaks os.walk.
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
    """The counter has to see real calls, and its blind spot has to be known."""

    def test_the_counter_sees_stat_calls(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f"
        target.write_text("x", encoding="utf-8")

        with counting_syscalls() as counter:
            os.stat(target)
            os.stat(target)

        assert counter.stat == 2

    def test_the_counter_is_restored_afterwards(self) -> None:
        before = os.stat
        with counting_syscalls():
            assert os.stat is not before
        assert os.stat is before

    @POSIX_ONLY
    def test_the_counter_cannot_see_inside_posixmodule(self, tmp_path: pathlib.Path) -> None:
        """DirEntry.stat() syscalls without going through os.stat.

        The entry is taken while the file exists and stat()ed after it is
        unlinked. FileNotFoundError proves a syscall happened; the counter
        recording zero proves the counter did not see it. Any test asserting
        "no syscall" about a DirEntry has to observe behaviour instead.
        """
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        with os.scandir(tmp_path) as entries:
            entry = next(iter(entries))
        os.unlink(target)

        with counting_syscalls() as counter:
            with pytest.raises(FileNotFoundError):
                entry.stat()

        assert counter.total == 0, (
            f"the wrapper is not on this path, so a zero here is not evidence: {counter.total}"
        )


# gh-89727 rewrote _walk() around an explicit stack; the commit first ships in
# v3.12.0. Both 3.10 and 3.11 still recurse.
WALK_IS_ITERATIVE = sys.version_info >= (3, 12)


class SyntheticEntry:
    """A DirEntry stand-in for walking a tree that is not on any disk."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def is_dir(self, follow_symlinks: bool = True) -> bool:
        return True

    def is_symlink(self) -> bool:
        return False


class SyntheticScandir:
    """The context-manager iterator protocol os.walk expects from os.scandir."""

    def __init__(self, entries: list[Any]) -> None:
        self._entries = iter(entries)

    def __iter__(self) -> Any:
        return self

    def __next__(self) -> Any:
        return next(self._entries)

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def close(self) -> None:
        pass


def synthetic_chain(depth: int) -> Callable[[Any], Any]:
    """An os.scandir replacement yielding a chain `depth` levels deep.

    The level is counted rather than read off the path. Deriving it from `top`
    would scan a string that grows with the depth, which is a quadratic cost
    inside the harness itself - exactly what a measurement using this is
    trying to attribute to os.walk. A top-down walk calls scandir once per
    level in order, so a counter is both exact and O(1).
    """
    state = {"level": 0}

    def scandir(top: Any) -> Any:
        state["level"] += 1
        return SyntheticScandir([SyntheticEntry("x")] if state["level"] <= depth else [])

    return scandir


def frame_depth() -> int:
    """How many Python frames are currently on the stack."""
    depth, frame = 0, sys._getframe()
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth


class TestWalkSpaceNeedsBothTerms:
    """`os.walk(path)` | O(n·L) | O(P) - entry count settles neither column.

    Breadth behaves the same on every supported version: 4x the siblings costs
    about 4x the peak on 3.11 (x3.57) and on 3.14 (x3.89).

    Depth is the term that changed. Through 3.11 _walk() recurses with
    `yield from`, so each level is a generator frame and 4x the depth costs
    5.1x; from 3.12 the walk drives an explicit stack and the same step costs
    1.75x, which is the path strings rather than the frames. Which term
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

    def test_walk_recurses_only_before_312(self, tmp_path: pathlib.Path) -> None:
        """The Version Note, measured at the depth scandir is called from.

        Exhausting the stack would settle this too, but only with a tree deep
        enough that shutil.rmtree - itself recursive - cannot clean it up
        afterwards on the recursive versions. Recording the frame depth at each
        scandir call needs 40 directories instead of 2,000: recursion makes
        that depth grow one frame per level, and the stack-based walk holds it
        flat.
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
                f"3.10 and 3.11 recurse once per level, so the spread should "
                f"track the depth: {spread}"
            )

    @pytest.mark.timing
    def test_the_traversal_itself_is_linear_in_the_entries(self) -> None:
        """Why the time column is O(n), with the filesystem taken out of it.

        os.scandir is replaced by a generator of synthetic entries, and the
        walk runs with followlinks=True, which is what takes the last syscall
        out: with the default followlinks=False os.walk calls os.path.islink()
        on each child before descending, and those lstat calls are real - 800
        of them on a chain of that depth. With both gone, what is left is
        exactly the Python the walk does: popping the stack, joining a path
        per entry, sorting entries into dirs and nondirs.

        4x the entries, from 200 to 800. From 3.12 that measures x4.37 -
        linear. Through 3.11 it measures x16.47, because `yield from` forwards
        every result through one suspended frame per level: a factor of the
        depth, with no filesystem in the picture at all.

        Walking the same chains on a real filesystem is dearer again on every
        version, because the kernel resolves a longer path on each call. This
        page counts a syscall as O(1), which is why the row says O(n) from
        3.12 and the prose beside it says the clock disagrees.
        """

        real_scandir = os.scandir
        times = []
        try:
            for depth in (200, 800):
                best = float("inf")
                for _ in range(7):
                    os.scandir = synthetic_chain(depth)  # type: ignore[assignment]
                    start = time.perf_counter()
                    drain(os.walk("/r", followlinks=True))
                    best = min(best, time.perf_counter() - start)
                times.append(best)
        finally:
            os.scandir = real_scandir  # type: ignore[assignment]

        if WALK_IS_ITERATIVE:
            assert times[1] < 8 * times[0], (
                f"from 3.12 the stack-based walk is linear in the entries: "
                f"{times[0]:.6f}s at depth 200 against {times[1]:.6f}s at 800"
            )
        else:
            assert times[1] > 8 * times[0], (
                f"through 3.11 yield from adds a frame per level, so 4x the "
                f"entries costs far more than 4x: {times[0]:.6f}s at depth 200 "
                f"against {times[1]:.6f}s at 800"
            )

    def test_walk_visits_every_entry(self, tmp_path: pathlib.Path) -> None:
        """Every entry is visited once, which is the n the row is expressed in.

        What that visit costs is settled separately, by the two tests above:
        linear from 3.12, and a factor of the depth through 3.11.
        """
        wide = make_wide(tmp_path, 20)
        (wide / "d00000" / "leaf.txt").write_text("x", encoding="utf-8")

        visited = list(os.walk(wide))

        assert len(visited) == 21, "the root plus each subdirectory"
        assert sum(len(files) for _, _, files in visited) == 1

    def test_equal_entry_counts_differ_by_shape(self, tmp_path: pathlib.Path) -> None:
        """Why the space column is O(P) and not O(n).

        600 directories either way, and the peak is the column that changes
        sides. From 3.12 the wide tree costs about ten times the chain
        (81,869 B against 8,222 B on 3.14), queueing 600 entries where the
        chain queues one. Through 3.11 the recursion inverts it: a suspended
        frame per level, each holding its own path, makes the chain cost about
        forty-seven times the wide tree (1,965,575 B against 41,561 B).

        Traced allocation, so this is Python's own memory and no syscall
        enters it. The clock is deliberately not asserted here: a chain is
        about eight times slower to walk than a wide tree of the same entry
        count, but that gap is the kernel resolving deeper paths, and under
        this page's convention a syscall is O(1) - see
        test_the_traversal_itself_is_linear_in_the_entries.

        Not varied: component length, which lengthens every path at a fixed
        shape, and file entries as against directory entries.
        """
        count = 600
        deep = make_deep(tmp_path, count)
        wide = make_wide(tmp_path, count)

        deep_peak = peak_bytes(lambda: drain(os.walk(deep)))
        wide_peak = peak_bytes(lambda: drain(os.walk(wide)))
        remove_deep(deep)

        if WALK_IS_ITERATIVE:
            assert wide_peak > 3 * deep_peak, (
                f"from 3.12 only the queue is held, so breadth costs the space: "
                f"{deep_peak} B deep against {wide_peak} B wide"
            )
        else:
            assert deep_peak > 3 * wide_peak, (
                f"through 3.11 a frame per level holds each level's path, so depth "
                f"costs the space: {deep_peak} B deep against {wide_peak} B wide"
            )

    def test_bottom_up_puts_depth_back_into_the_peak(self, tmp_path: pathlib.Path) -> None:
        """The topdown=False caveat on the page.

        A bottom-up walk cannot yield a directory until its descendants are
        done, so every ancestor's result tuple stays on the stack. On a chain
        that is the whole depth: 4x the depth costs x6.6 bottom-up (40,510 B
        to 266,938 B on 3.14) where top-down moves by x1.8 (3,406 B to
        6,222 B). Through 3.11 both directions already hold a frame per level,
        so the contrast is a 3.12-and-later one and the assertion is scoped to
        the version that changed.
        """
        shallow = make_deep(tmp_path, 100)
        nested = make_deep(tmp_path, 400)

        def walk(top: pathlib.Path, topdown: bool) -> int:
            return peak_bytes(lambda: drain(os.walk(top, topdown=topdown)))

        shallow_up, nested_up = walk(shallow, False), walk(nested, False)
        nested_down = walk(nested, True)
        remove_deep(shallow)
        remove_deep(nested)

        assert nested_up > 4 * shallow_up, (
            f"bottom-up holds every ancestor, so depth costs: {shallow_up} B at "
            f"100 against {nested_up} B at 400"
        )
        if WALK_IS_ITERATIVE:
            assert nested_up > 4 * nested_down, (
                f"and it costs far more than the top-down walk of the same tree: "
                f"{nested_down} B top-down against {nested_up} B bottom-up"
            )

    def test_pruning_dirnames_skips_the_subtree(self, tmp_path: pathlib.Path) -> None:
        """The example's claim: assigning into dirnames stops the descent."""
        skipped = tmp_path / "__pycache__"
        skipped.mkdir()
        (skipped / "inside").mkdir()
        (tmp_path / "kept").mkdir()

        visited = []
        for dirpath, dirnames, _ in os.walk(tmp_path):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            visited.append(dirpath)

        assert str(skipped) not in visited
        assert str(skipped / "inside") not in visited, "the whole subtree, not just the root"
        assert str(tmp_path / "kept") in visited


class TestFwalkHoldsADescriptorPerLevel:
    """`os.fwalk(path)` | O(n·L) | O(P), and one open directory fd per level."""

    @staticmethod
    def _open_fds() -> int:
        return len(os.listdir("/proc/self/fd"))

    @POSIX_ONLY
    @HAS_PROC_FD
    def test_open_descriptors_track_the_depth(self, tmp_path: pathlib.Path) -> None:
        peaks = []
        for depth in (4, 40):
            nested = make_deep(tmp_path, depth)
            highest = 0
            for _ in os.fwalk(nested):
                highest = max(highest, self._open_fds())
            peaks.append(highest)
            remove_deep(nested)

        assert peaks[1] - peaks[0] >= 30, (
            f"fwalk holds a descriptor per level, so 10x the depth should hold "
            f"far more at once: {peaks} open descriptors at depths 4 and 40"
        )

    @POSIX_ONLY
    def test_fwalk_closes_what_it_opened(self, tmp_path: pathlib.Path) -> None:
        nested = make_deep(tmp_path, 8)
        before = self._open_fds() if os.path.isdir("/proc/self/fd") else None

        drain(os.fwalk(nested))

        if before is not None:
            assert self._open_fds() == before, "every directory descriptor should be closed"

    @POSIX_ONLY
    def test_fwalk_visits_what_walk_visits(self, tmp_path: pathlib.Path) -> None:
        wide = make_wide(tmp_path, 5)
        (wide / "d00000" / "leaf.txt").write_text("x", encoding="utf-8")

        by_walk = sorted(top for top, _, _ in os.walk(wide))
        by_fwalk = sorted(top for top, _, _, _ in os.fwalk(wide))

        assert by_walk == by_fwalk


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

    def test_only_the_missing_components_recurse(self, tmp_path: pathlib.Path) -> None:
        """The qualification on the row: depth alone does not exhaust the stack.

        makedirs() stops recursing at the first head that already exists, so a
        single new directory under a 60-deep existing tree is one frame. The
        limit is set to 40 - far below that tree's own depth - and the call
        still succeeds, which it could not if the whole path were walked.
        """
        existing = tmp_path.joinpath(*["e"] * 60)
        os.makedirs(existing)
        original_limit = sys.getrecursionlimit()
        # Relative to where this test already stands, because how deep pytest
        # itself is varies by version. The headroom is far below 60 either way.
        headroom = frame_depth() + 25

        sys.setrecursionlimit(headroom)
        try:
            os.makedirs(existing / "leaf")
        finally:
            sys.setrecursionlimit(original_limit)

        assert (existing / "leaf").is_dir()

        # The contrast: the same headroom against components that are missing.
        sys.setrecursionlimit(headroom)
        try:
            with pytest.raises(RecursionError):
                os.makedirs(tmp_path.joinpath(*["m"] * 60))
        finally:
            sys.setrecursionlimit(original_limit)
            shutil.rmtree(tmp_path / "m", ignore_errors=True)

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

        Depth is held fixed and the components lengthened, so a bound counting
        only frames predicts no change. The frames are a fixed cost in the peak,
        so a shallower tree shows the component term more clearly: at depth 40,
        1 against 80 characters measures 4,633 B against 71,134 B (x15.4) on
        3.14, where depth 100 with 1 against 20 gives only x7.1 - and less than
        that on 3.10, whose frames are larger. Depth 40 by 81 characters also
        stays inside PATH_MAX, which 100 by 41 does not.
        """
        peaks = []
        for length in (1, 80):
            target = tmp_path.joinpath(f"c{length}", *["y" * length] * 40)
            peaks.append(peak_bytes(lambda target=target: os.makedirs(target)))
            remove_deep(tmp_path / f"c{length}")

        assert peaks[1] > 4 * peaks[0], (
            f"longer components should cost more at the same depth, so the frames "
            f"are not the whole bound: {peaks} bytes for 1 and 80 character components"
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

    def test_renames_creates_the_head_and_prunes_the_old_one(self, tmp_path: pathlib.Path) -> None:
        """`os.renames(old, new)`: makedirs, then rename, then removedirs."""
        source = tmp_path / "from" / "deep" / "f.txt"
        os.makedirs(source.parent)
        source.write_text("payload", encoding="utf-8")
        destination = tmp_path / "to" / "a" / "b" / "f.txt"

        os.renames(source, destination)

        assert destination.read_text(encoding="utf-8") == "payload"
        assert destination.parent.is_dir(), "the new head is created"
        assert not (tmp_path / "from").exists(), "the emptied old head is pruned"


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
    """The Path manipulation table and the sentence below it."""

    PURE = (
        "join",
        "split",
        "dirname",
        "basename",
        "splitext",
        "normpath",
        "isabs",
        "normcase",
        "splitdrive",
    )

    def test_the_string_operations_touch_no_filesystem(self, tmp_path: pathlib.Path) -> None:
        sample = str(tmp_path / "a" / "b" / "c.txt")
        calls = {
            "join": lambda: os.path.join(sample, "x", "y"),
            "split": lambda: os.path.split(sample),
            "dirname": lambda: os.path.dirname(sample),
            "basename": lambda: os.path.basename(sample),
            "splitext": lambda: os.path.splitext(sample),
            "normpath": lambda: os.path.normpath(sample + "/../d"),
            "isabs": lambda: os.path.isabs(sample),
            "normcase": lambda: os.path.normcase(sample),
            "splitdrive": lambda: os.path.splitdrive(sample),
        }

        for name in self.PURE:
            with counting_syscalls() as counter:
                calls[name]()
            assert counter.total == 0, f"os.path.{name} made {counter.total} syscalls"

    @POSIX_ONLY
    @pytest.mark.timing
    def test_isabs_inspects_only_the_prefix(self) -> None:
        """`os.path.isabs(path)` | O(1) - not O(L) like its neighbours.

        On POSIX the whole function is `startswith` on the argument. A peak
        measurement cannot settle that - a scan that allocates nothing would
        pass one - so the control here is an actual O(L) pass over the very
        same string: `str.replace`, which is what Windows before 3.13 does to
        the separators. isabs costs about 115ns whether the path is two
        characters or two million; the O(L) control costs some 590x that on
        the long one.

        Windows before 3.13 is therefore O(L), which this platform cannot
        exercise.
        """
        short, long = "/a", "/" + "a" * 2_000_000

        assert os.path.isabs(short) and os.path.isabs(long)
        assert not os.path.isabs("a/b")

        def fastest(call: Callable[[], Any]) -> float:
            return min(timeit.repeat(call, number=2_000, repeat=5))

        on_short = fastest(lambda: os.path.isabs(short))
        on_long = fastest(lambda: os.path.isabs(long))
        an_actual_scan = min(timeit.repeat(lambda: long.replace("/", "\\"), number=50, repeat=5))

        assert on_long < 3 * on_short, (
            f"a 1,000,000x longer path should cost the same: {on_short:.6f}s "
            f"against {on_long:.6f}s for 2,000 calls"
        )
        assert an_actual_scan / 50 > 20 * (on_long / 2_000), (
            f"the control has to be much dearer, or the comparison proves "
            f"nothing: one scan {an_actual_scan / 50:.9f}s against one isabs "
            f"{on_long / 2_000:.9f}s"
        )

    @POSIX_ONLY
    def test_normcase_and_splitdrive_are_free_on_posix(self) -> None:
        """POSIX has no case folding and no drives, so both return early."""
        sample = "/Home/User/File.TXT"

        assert os.path.normcase(sample) is sample, "POSIX normcase returns its argument"
        assert os.path.splitdrive(sample) == ("", sample)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="os.path.splitroot is 3.12+")
    def test_splitroot_separates_the_root(self) -> None:
        splitroot = getattr(os.path, "splitroot")  # noqa: B009 - absent from typeshed before 3.12

        assert splitroot("/a/b") == ("", "/", "a/b")
        assert splitroot("a/b") == ("", "", "a/b")

    def test_abspath_calls_getcwd_only_for_a_relative_path(self) -> None:
        with counting_syscalls() as relative:
            os.path.abspath("some/relative/path")
        with counting_syscalls() as absolute:
            os.path.abspath("/already/absolute/path")

        assert relative.getcwd == 1, f"expected one getcwd, got {relative.getcwd}"
        assert absolute.getcwd == 0, "an absolute path needs no getcwd"

    def test_relpath_calls_getcwd_once_per_relative_argument(self) -> None:
        """`os.path.relpath(path, start)` | O(L + S), and one getcwd each.

        Both arguments go through abspath, so the count follows how many of
        them were relative rather than whether either was.
        """
        with counting_syscalls() as neither:
            result = os.path.relpath("/a/b/c", "/a/d")
        assert result == os.path.join("..", "b", "c")
        assert neither.getcwd == 0

        with counting_syscalls() as one:
            os.path.relpath("b/c", "/d")
        with counting_syscalls() as both:
            os.path.relpath("b/c", "d")

        assert one.getcwd == 1, f"one relative argument, one getcwd: {one.getcwd}"
        assert both.getcwd == 2, f"two relative arguments, two getcwd: {both.getcwd}"

    def test_commonpath_stops_on_a_component_and_commonprefix_does_not(self) -> None:
        """The distinction the two rows draw."""
        paths = ["/usr/lib", "/usr/libexec"]

        assert os.path.commonpath(paths) == "/usr"
        assert os.path.commonprefix(paths) == "/usr/lib", "character-wise, mid-component"

    def test_expandvars_output_follows_the_substituted_value(self) -> None:
        """`os.path.expandvars(path)` | O(L + s) - s is not bounded by L."""
        os.environ["OS_PAGE_PROBE"] = "z" * 5_000
        try:
            expanded = os.path.expandvars("$OS_PAGE_PROBE")
        finally:
            del os.environ["OS_PAGE_PROBE"]

        assert len(expanded) == 5_000, "a 15-character input produced a 5,000-character result"

    def test_ismount_stops_scaling_with_the_parent_at_313(self, tmp_path: pathlib.Path) -> None:
        """`os.path.ismount(path)` | O(R) - and R disappears at 3.13.

        Through 3.12 the parent is always passed through realpath(), which
        lstats once per component of what it resolves: 5 calls for a shallow
        path against 14 for one ten deep on 3.12, and 7 against the same
        shallow case on 3.10. From 3.13 the parent is lstat'ed directly and
        realpath() is only the fallback, which holds it at two either way.
        """
        shallow = tmp_path / "sub"
        shallow.mkdir()
        deep = tmp_path.joinpath("d", *["component"] * 10)
        os.makedirs(deep)

        with counting_syscalls() as flat:
            assert os.path.ismount(shallow) is False
        with counting_syscalls() as nested:
            assert os.path.ismount(deep) is False

        if sys.version_info >= (3, 13):
            assert flat.lstat == nested.lstat == 2, (
                f"3.13 lstats the path and its parent and stops: "
                f"{flat.lstat} and {nested.lstat} lstat calls"
            )
        else:
            assert nested.lstat > flat.lstat + 5, (
                f"through 3.12 the realpath() of the parent is the bound: "
                f"{flat.lstat} against {nested.lstat} lstat calls"
            )

    def test_samefile_stats_both_arguments(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        other = tmp_path / "g.txt"
        other.write_text("x", encoding="utf-8")

        with counting_syscalls() as counter:
            same = os.path.samefile(target, target)

        assert same and counter.stat == 2
        assert not os.path.samefile(target, other)
        assert os.path.samestat(os.stat(target), os.stat(target))


class TestRealpathFollowsTheResolvedPath:
    """`os.path.realpath(path)` | O(R) | O(R), R = the path text it walks.

    The argument's own length does not bound the work. Every link resolved
    splices its target into the path still to be walked, and those components
    are lstat'ed in turn, so a two-component argument can cost more than a
    sixteen-component one that contains no links.

    Everything here counts lstat calls, which is exact. Elapsed time is not
    used: realpath rebuilds `newpath = path + sep + name` at every component,
    which is superlinear in principle, but a deeper path also makes the kernel
    resolve more components per lstat, and a stopwatch cannot separate the two
    under this page's convention that a syscall is O(1). Stubbing lstat out
    entirely leaves the Python-side work close to linear over 100..800
    components (x2.21, x2.34, x2.24), so the rebuilding never takes over at
    any depth a real path reaches.

    Not varied here: the width of each component, the encoding of the path,
    and relative link targets, which re-enter the same loop rather than a
    different one.
    """

    @POSIX_ONLY
    def test_a_link_free_path_costs_one_lstat_per_component(self, tmp_path: pathlib.Path) -> None:
        depths = (2, 4, 8)
        counts = []
        for depth in depths:
            target = tmp_path.joinpath(f"r{depth}", *["d"] * depth)
            os.makedirs(target)
            with counting_syscalls() as counter:
                os.path.realpath(target)
            counts.append(counter.lstat)

        # Exactly one per added component, not merely more: two calls per
        # component would double each step and pass a growth-only assertion.
        assert counts[1] - counts[0] == depths[1] - depths[0], (
            f"4 components should cost 2 more lstat calls than 2: {counts}"
        )
        assert counts[2] - counts[1] == depths[2] - depths[1], (
            f"8 components should cost 4 more lstat calls than 4: {counts}"
        )

    @POSIX_ONLY
    def test_a_link_costs_the_components_of_its_target(self, tmp_path: pathlib.Path) -> None:
        """The axis that the argument's length cannot predict."""
        deep = tmp_path.joinpath(*["e"] * 12)
        os.makedirs(deep)
        link = tmp_path / "L"
        link.symlink_to(deep)

        with counting_syscalls() as direct:
            os.path.realpath(tmp_path / "plain")
        with counting_syscalls() as through_link:
            os.path.realpath(link)

        assert through_link.lstat > direct.lstat + 8, (
            f"a one-component link to a 12-deep target should cost the target's "
            f"components too: {direct.lstat} against {through_link.lstat} lstat calls"
        )

    @POSIX_ONLY
    def test_a_chain_of_links_costs_more_than_one(self, tmp_path: pathlib.Path) -> None:
        """Each link in the chain re-enters the resolution."""
        deep = tmp_path.joinpath(*["e"] * 12)
        os.makedirs(deep)
        single = tmp_path / "s0"
        single.symlink_to(deep)

        previous: pathlib.Path = deep
        for index in range(8):
            link = tmp_path / f"c{index}"
            link.symlink_to(previous)
            previous = link

        with counting_syscalls() as one_link:
            os.path.realpath(single)
        with counting_syscalls() as eight_links:
            os.path.realpath(previous)

        assert os.path.realpath(single) == os.path.realpath(previous), (
            "both arguments resolve to the very same path"
        )
        assert eight_links.lstat > one_link.lstat, (
            f"and yet they cost differently, which is why the resolved path "
            f"cannot be the bound: {one_link.lstat} against "
            f"{eight_links.lstat} lstat calls"
        )

    @POSIX_ONLY
    def test_realpath_resolves_and_normpath_does_not(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "real.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        assert os.path.realpath(link) == str(target)
        assert os.path.normpath(link) == str(link), "normpath does not resolve links"

        with counting_syscalls() as counter:
            os.path.normpath(link)
        assert counter.total == 0, "normpath is the string-only alternative"


class TestFilenamesAndPathObjects:
    """The Filenames and path objects table: pass-through is O(1)."""

    def test_fspath_returns_str_and_bytes_unchanged(self) -> None:
        text = "x" * 10_000
        raw = text.encode()

        assert os.fspath(text) is text, "no copy, whatever the length"
        assert os.fspath(raw) is raw

    def test_fspath_calls_the_protocol_for_anything_else(self, tmp_path: pathlib.Path) -> None:
        calls = []

        class Path:
            def __fspath__(self) -> str:
                calls.append(1)
                return "/somewhere"

        assert os.fspath(Path()) == "/somewhere"
        assert calls == [1], "exactly one protocol call"
        assert isinstance(Path(), os.PathLike), "the ABC checks for __fspath__"
        assert isinstance(tmp_path, os.PathLike)
        assert not isinstance("plain str", os.PathLike)

    def test_fsencode_and_fsdecode_pass_their_own_type_through(self) -> None:
        text = "x" * 10_000
        raw = text.encode()

        assert os.fsdecode(text) is text, "already str: no decode, no copy"
        assert os.fsencode(raw) is raw, "already bytes: no encode, no copy"
        assert os.fsencode(text) == raw, "the converting direction is O(n)"
        assert os.fsdecode(raw) == text


class TestScandirCarriesTheType:
    """The listing sections: scandir answers from the directory entry.

    Counting os.stat cannot show this, because DirEntry stats below the Python
    level - see TestCountingHarness. The observation used instead is that an
    entry taken before the file is unlinked still answers is_file() correctly
    afterwards, which is only possible without a stat.
    """

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

    def test_is_file_answers_for_a_file_that_is_already_gone(self, tmp_path: pathlib.Path) -> None:
        """No tolerance: a stat here would have to fail.

        DirEntry_test_mode in Modules/posixmodule.c sets need_stat only when
        `d_type == DT_UNKNOWN` or a symlink is being followed. On a filesystem
        that reports DT_UNKNOWN the entry would stat, that stat would raise,
        and is_file() would return False - which is what the message says.
        """
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        with os.scandir(tmp_path) as entries:
            entry = next(iter(entries))
        os.unlink(target)

        assert entry.is_file() is True, (
            "is_file() answered from the directory entry. If this filesystem "
            "reports DT_UNKNOWN, is_file() must stat and would return False"
        )
        assert entry.is_dir() is False
        assert entry.is_symlink() is False

    @POSIX_ONLY
    def test_is_file_has_to_follow_a_symlink(self, tmp_path: pathlib.Path) -> None:
        """The caveat beside the listing example: a link is the other stat.

        is_symlink() is answered from the directory entry, so it stays True for
        a link whose target is gone. is_file() has to look at that target, and
        a broken link is how that shows: it returns False where the same probe
        on a plain file returns True.
        """
        target = tmp_path / "real.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        os.unlink(target)

        with os.scandir(tmp_path) as entries:
            entry = next(e for e in entries if e.name == "link.txt")

        assert entry.is_symlink() is True, "the type came from the directory entry"
        assert entry.is_file() is False, "is_file() followed the link and found nothing"

        # Returning False for every symlink would pass the assertion above, so
        # the control is a live link, taken from its own entry.
        good_target = tmp_path / "present.txt"
        good_target.write_text("x", encoding="utf-8")
        good_link = tmp_path / "good.txt"
        good_link.symlink_to(good_target)
        with os.scandir(tmp_path) as entries:
            good = next(e for e in entries if e.name == "good.txt")

        assert good.is_symlink() is True
        assert good.is_file() is True, "the target is what is answered about"

    @POSIX_ONLY
    def test_a_failed_stat_is_retried_where_a_successful_one_is_kept(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The caching rule on the page: successes are cached, failures are not.

        One entry throughout. While the target is missing is_file() is False;
        creating the target flips it to True, which a cached failure could not
        do. Deleting it again leaves it True, which is the cached success.
        """
        link = tmp_path / "link.txt"
        target = tmp_path / "absent.txt"
        link.symlink_to(target)
        with os.scandir(tmp_path) as entries:
            entry = next(iter(entries))

        assert entry.is_file() is False, "the target is not there yet"

        target.write_text("x", encoding="utf-8")
        assert entry.is_file() is True, "the failed stat was retried, not cached"

        os.unlink(target)
        assert entry.is_file() is True, "and this success is cached"

    def test_entry_stat_really_syscalls_and_then_caches(self, tmp_path: pathlib.Path) -> None:
        """The DirEntry.stat() row: one stat on POSIX, then free."""
        target = tmp_path / "g.txt"
        target.write_text("x", encoding="utf-8")
        with os.scandir(tmp_path) as entries:
            entry = next(iter(entries))

        first = entry.stat()
        os.unlink(target)

        assert entry.stat() is first, "the second call returns the very same object"

        with os.scandir(tmp_path) as entries:
            assert list(entries) == [], "and a fresh scandir no longer sees it"

    def test_name_path_and_inode_are_carried(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "h.txt"
        target.write_text("x", encoding="utf-8")
        with os.scandir(tmp_path) as entries:
            entry = next(iter(entries))

        assert entry.name == "h.txt"
        assert entry.path == str(target)
        assert entry.path is entry.path, "built once, then cached"
        assert entry.inode() == entry.inode() == os.stat(target).st_ino

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="DirEntry.is_junction is 3.12+")
    @POSIX_ONLY
    def test_is_junction_is_false_on_posix(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "i.txt").write_text("x", encoding="utf-8")
        with os.scandir(tmp_path) as entries:
            entry = next(iter(entries))

        is_junction = getattr(entry, "is_junction")  # noqa: B009 - typeshed 3.12+
        assert is_junction() is False

    @HAS_PROC_FD
    def test_close_releases_the_directory_handle(self, tmp_path: pathlib.Path) -> None:
        """`os.scandir.close()` - what the `with` statement calls.

        The iterator is held alive across the close, so nothing is released by
        the garbage collector on its behalf. Counting the process's open
        descriptors is what separates releasing the handle from merely marking
        the iterator exhausted.
        """

        def open_descriptors() -> int:
            return len(os.listdir("/proc/self/fd"))

        self._populate(tmp_path, files=3, dirs=0)
        before = open_descriptors()
        entries = os.scandir(tmp_path)
        next(iter(entries))
        assert open_descriptors() == before + 1, "scandir holds a directory open"

        entries.close()

        assert open_descriptors() == before, "and close() gives it back"
        assert list(entries) == [], "the iterator yields nothing further either"

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


class TestAvoidingASecondStat:
    """The narrative section: two stat calls against one."""

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

    @POSIX_ONLY
    def test_several_fields_come_from_one_stat(self, tmp_path: pathlib.Path) -> None:
        """The stat_result table: each field is an attribute read, not a syscall."""
        target = tmp_path / "f.txt"
        target.write_text("content", encoding="utf-8")

        with counting_syscalls() as counter:
            info = os.stat(target)
            fields = (
                info.st_size,
                info.st_mode,
                info.st_mtime,
                info.st_mtime_ns,
                info.st_atime,
                info.st_atime_ns,
                info.st_ctime,
                info.st_ctime_ns,
                info.st_ino,
                info.st_dev,
                info.st_nlink,
                info.st_uid,
                info.st_gid,
                info.st_blocks,
                info.st_blksize,
                info.st_rdev,
            )

        assert counter.stat == 1, f"sixteen fields, one call to os.stat, got {counter.stat}"
        assert fields[0] == 7
        assert stat_module.S_ISREG(info.st_mode)
        assert info.st_mtime_ns // 1_000_000_000 == int(info.st_mtime)

        # The counter cannot see below posixmodule, so deleting the file is
        # what shows the fields are already in hand: a field that had to ask
        # the filesystem would have nothing to ask about now.
        os.unlink(target)
        assert info.st_size == 7
        assert info.st_ino and info.st_mtime_ns


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

    @POSIX_ONLY
    def test_link_predicates_make_one_lstat_each(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "real.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        for name, helper in (("islink", os.path.islink), ("lexists", os.path.lexists)):
            with counting_syscalls() as counter:
                assert helper(link) is True
            assert counter.lstat == 1, f"os.path.{name} made {counter.lstat} lstat calls"

        os.unlink(target)
        assert os.path.lexists(link), "a broken link still exists as a link"
        assert not os.path.exists(link), "but exists() follows it and finds nothing"

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

        inode = os.stat(source).st_ino

        os.rename(source, destination)

        assert destination.read_text(encoding="utf-8") == "payload"
        assert not source.exists()
        assert os.stat(destination).st_ino == inode, (
            "the same inode under a new name, so no bytes were copied"
        )

        other = tmp_path / "c.txt"
        other.write_text("other", encoding="utf-8")
        os.replace(other, destination)

        assert destination.read_text(encoding="utf-8") == "other"

    def test_mkdir_needs_its_parent_and_rmdir_needs_it_empty(self, tmp_path: pathlib.Path) -> None:
        """The two rows that makedirs and removedirs exist to work around."""
        with pytest.raises(FileNotFoundError):
            os.mkdir(tmp_path / "absent" / "child")

        target = tmp_path / "one"
        os.mkdir(target)
        (target / "f.txt").write_text("x", encoding="utf-8")
        with pytest.raises(OSError):
            os.rmdir(target)

        os.remove(target / "f.txt")
        os.rmdir(target)
        assert not target.exists()

    def test_unlink_and_remove_do_the_same_thing(self, tmp_path: pathlib.Path) -> None:
        """Two names, one behaviour - but not one object."""
        for name, delete in (("remove", os.remove), ("unlink", os.unlink)):
            target = tmp_path / f"{name}.txt"
            target.write_text("x", encoding="utf-8")
            delete(target)
            assert not target.exists()
            with pytest.raises(FileNotFoundError):
                delete(target)

        directory = tmp_path / "dir"
        directory.mkdir()
        for delete in (os.remove, os.unlink):
            # Neither one removes a directory; that is what os.rmdir is for.
            with pytest.raises(OSError):
                delete(directory)
        assert directory.is_dir()

    @POSIX_ONLY
    def test_link_shares_the_inode_and_symlink_does_not(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "real.txt"
        target.write_text("payload", encoding="utf-8")
        hard, soft = tmp_path / "hard", tmp_path / "soft"

        os.link(target, hard)
        os.symlink(target, soft)

        assert os.stat(hard).st_ino == os.stat(target).st_ino, "no bytes copied"
        assert os.lstat(soft).st_ino != os.stat(target).st_ino
        assert os.readlink(soft) == str(target)

    @POSIX_ONLY
    def test_readlink_returns_the_target_it_was_given(self, tmp_path: pathlib.Path) -> None:
        """`os.readlink(path)` | O(t) | O(t), t = the stored target."""
        short_target = "a"
        long_target = "b" * 200
        short_link, long_link = tmp_path / "short", tmp_path / "long"
        short_link.symlink_to(short_target)
        long_link.symlink_to(long_target)

        assert os.readlink(short_link) == short_target
        assert len(os.readlink(long_link)) == len(long_target)

    @POSIX_ONLY
    def test_truncate_resizes_without_writing_the_bytes(self, tmp_path: pathlib.Path) -> None:
        """`os.truncate(path, length)` | O(1) whatever `length` is.

        Extending to 64 MB allocates no blocks, which is the observation that
        separates a constant-cost resize from one that writes zeroes.
        """
        target = tmp_path / "sparse.bin"
        target.write_bytes(b"")

        os.truncate(target, 64 * 1024 * 1024)

        info = os.stat(target)
        assert info.st_size == 64 * 1024 * 1024
        assert info.st_blocks * 512 < info.st_size // 2, (
            f"a sparse extend should allocate almost nothing: {info.st_blocks} blocks"
        )

        with open(target, "r+b") as handle:
            os.ftruncate(handle.fileno(), 0)
        assert os.stat(target).st_size == 0

    @POSIX_ONLY
    def test_chmod_and_chown_change_only_metadata(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("payload", encoding="utf-8")
        before = os.stat(target)

        os.chmod(target, 0o600)
        os.chown(target, before.st_uid, before.st_gid)

        after = os.stat(target)
        assert stat_module.S_IMODE(after.st_mode) == 0o600
        assert after.st_ino == before.st_ino
        assert target.read_text(encoding="utf-8") == "payload", "no bytes moved"

    def test_access_answers_from_the_mode(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")

        assert os.access(target, os.R_OK)
        assert not os.access(tmp_path / "absent.txt", os.R_OK)
        assert os.access(tmp_path, os.X_OK), "a directory is searchable"

    def test_utime_moves_the_timestamp_only(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("payload", encoding="utf-8")

        os.utime(target, (1_000_000, 2_000_000))

        info = os.stat(target)
        assert int(info.st_mtime) == 2_000_000
        assert info.st_size == 7


class TestDescriptorOperations:
    """The descriptor tables: byte counts where the rows carry one."""

    def test_read_allocates_and_readinto_does_not(self, tmp_path: pathlib.Path) -> None:
        """`os.read(fd, n)` is O(n) space; the buffer forms are O(1)."""
        target = tmp_path / "payload.bin"
        target.write_bytes(b"x" * 1_000_000)

        descriptor = os.open(target, os.O_RDONLY)
        try:
            small = peak_bytes(lambda: os.read(descriptor, 1_000))
            os.lseek(descriptor, 0, os.SEEK_SET)
            large = peak_bytes(lambda: os.read(descriptor, 1_000_000))
        finally:
            os.close(descriptor)

        assert large > 100 * small, (
            f"os.read allocates what it is asked for: {small} B against {large} B"
        )

    @pytest.mark.skipif(not hasattr(os, "readinto"), reason="os.readinto is 3.14+")
    def test_readinto_fills_the_callers_buffer(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "payload.bin"
        target.write_bytes(b"abcdefghij")
        buffer = bytearray(4)

        descriptor = os.open(target, os.O_RDONLY)
        try:
            readinto = getattr(os, "readinto")  # noqa: B009 - typeshed 3.14+
            count = readinto(descriptor, buffer)
        finally:
            os.close(descriptor)

        assert count == 4
        assert bytes(buffer) == b"abcd"

    @pytest.mark.skipif(not hasattr(os, "readinto"), reason="os.readinto is 3.14+")
    def test_readinto_allocates_nothing_where_read_allocates_the_lot(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The O(1) against O(n) space on the two rows.

        Same descriptor, same 4 MB: readinto peaks at 0 traced bytes because
        the buffer is the caller's and already exists, where os.read peaks at
        the 4 MB it returns.
        """
        readinto = getattr(os, "readinto")  # noqa: B009 - typeshed 3.14+
        target = tmp_path / "payload.bin"
        target.write_bytes(b"x" * 4_000_000)
        buffer = bytearray(4_000_000)

        descriptor = os.open(target, os.O_RDONLY)
        try:
            into_buffer = peak_bytes(lambda: readinto(descriptor, buffer))
            os.lseek(descriptor, 0, os.SEEK_SET)
            allocated = peak_bytes(lambda: os.read(descriptor, 4_000_000))
        finally:
            os.close(descriptor)

        assert into_buffer < 10_000, f"readinto fills a buffer that already exists: {into_buffer} B"
        assert allocated > 3_000_000, f"os.read is the control and does allocate: {allocated} B"

    @POSIX_ONLY
    def test_pread_and_pwrite_leave_the_offset_alone(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "payload.bin"
        target.write_bytes(b"0123456789")

        descriptor = os.open(target, os.O_RDWR)
        try:
            assert os.lseek(descriptor, 0, os.SEEK_CUR) == 0
            assert os.pread(descriptor, 3, 5) == b"567"
            assert os.lseek(descriptor, 0, os.SEEK_CUR) == 0, "pread did not move it"
            os.pwrite(descriptor, b"AB", 0)
            assert os.lseek(descriptor, 0, os.SEEK_CUR) == 0
        finally:
            os.close(descriptor)

        assert target.read_bytes() == b"AB23456789"

    @POSIX_ONLY
    def test_readv_and_writev_span_several_buffers(self, tmp_path: pathlib.Path) -> None:
        """n is the total across the buffers, not the count of them."""
        target = tmp_path / "vector.bin"

        descriptor = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            written = os.writev(descriptor, [b"abc", b"de", b"fgh"])
            assert written == 8
            os.lseek(descriptor, 0, os.SEEK_SET)
            first, second = bytearray(3), bytearray(5)
            assert os.readv(descriptor, [first, second]) == 8
        finally:
            os.close(descriptor)

        assert bytes(first) == b"abc"
        assert bytes(second) == b"defgh"

    @POSIX_ONLY
    def test_the_vector_forms_cost_per_buffer_as_well(self, tmp_path: pathlib.Path) -> None:
        """The k in O(n + k): empty buffers carry no bytes and still cost.

        Both calls write the same eight bytes. One passes them as three
        buffers, the other pads the list with 1,000 empty ones, so any bound
        in the byte count alone predicts no difference. The padding stays
        under SC_IOV_MAX, which is the kernel's own limit on the vector.
        """
        target = tmp_path / "vector.bin"
        payload: list[bytes] = [b"abc", b"de", b"fgh"]
        padded: list[bytes] = payload + [b""] * 1_000

        def write(buffers: list[bytes]) -> int:
            descriptor = os.open(target, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                return os.writev(descriptor, buffers)
            finally:
                os.close(descriptor)

        assert write(payload) == 8
        assert write(padded) == 8, "the same bytes, 1,000 more buffers"

        narrow = peak_bytes(lambda: write(payload))
        wide = peak_bytes(lambda: write(padded))

        assert wide > 4 * narrow, (
            f"the iovec is built per buffer, not per byte: {narrow} B against "
            f"{wide} B for the same eight bytes"
        )

    def test_dup_and_dup2_share_the_file(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.bin"
        target.write_bytes(b"0123456789")

        original = os.open(target, os.O_RDONLY)
        try:
            copy = os.dup(original)
            try:
                os.lseek(original, 5, os.SEEK_SET)
                assert os.lseek(copy, 0, os.SEEK_CUR) == 5, "one open file, two descriptors"
            finally:
                os.close(copy)

            # dup2 names the target descriptor instead of taking the lowest free
            # one, which is the whole difference between the two rows.
            spare = os.open(os.devnull, os.O_RDONLY)
            try:
                assert os.dup2(original, spare) == spare
                assert os.lseek(spare, 0, os.SEEK_CUR) == 5, "now the same open file"
            finally:
                os.close(spare)
        finally:
            os.close(original)

    def test_closerange_closes_the_descriptors_in_the_range(self) -> None:
        read_end, write_end = os.pipe()
        low, high = min(read_end, write_end), max(read_end, write_end)

        os.closerange(low, high + 1)

        for descriptor in (read_end, write_end):
            with pytest.raises(OSError):
                os.fstat(descriptor)

    def test_closerange_spans_the_range_and_stops_at_its_edges(self) -> None:
        """`os.closerange(fd_low, fd_high)` | O(k) - k is the span.

        Observed rather than timed. _Py_closerange in Python/fileutils.c
        prefers the close_range(2) syscall and falls back to a close() per
        descriptor, so how the span is traversed is the platform's business
        and a stopwatch here would be asserting which branch was taken. What
        the row promises either way is the extent: every descriptor inside the
        half-open range goes, and the neighbours on both edges stay.
        """
        descriptors = [os.open(os.devnull, os.O_RDONLY) for _ in range(6)]
        try:
            descriptors.sort()
            below, *inside, above = descriptors
            low, high = inside[0], inside[-1]

            os.closerange(low, high + 1)

            for descriptor in inside:
                with pytest.raises(OSError):
                    os.fstat(descriptor)
            assert os.fstat(below), "the descriptor below the range survives"
            assert os.fstat(above), "and so does the one above it"
        finally:
            for descriptor in descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def test_pipe_and_blocking_flags(self) -> None:
        read_end, write_end = os.pipe()
        try:
            assert os.get_blocking(read_end) is True
            os.set_blocking(read_end, False)
            assert os.get_blocking(read_end) is False

            os.set_inheritable(write_end, True)
            assert os.get_inheritable(write_end) is True

            assert os.write(write_end, b"hello") == 5
            assert os.read(read_end, 5) == b"hello"
            assert not os.isatty(read_end)
        finally:
            os.close(read_end)
            os.close(write_end)

    def test_fdopen_wraps_without_reading(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("payload", encoding="utf-8")

        descriptor = os.open(target, os.O_RDONLY)
        handle = os.fdopen(descriptor, "rb")
        try:
            # The kernel's offset, not the wrapper's: a buffered object that had
            # already filled its buffer would have moved this even while
            # reporting tell() == 0.
            assert os.lseek(descriptor, 0, os.SEEK_CUR) == 0, "nothing was read yet"
            assert handle.tell() == 0
            assert handle.read() == b"payload"
        finally:
            handle.close()

    def test_fsync_and_fdatasync_accept_the_descriptor(self, tmp_path: pathlib.Path) -> None:
        """Both are one syscall; how long the flush takes is the machine's."""
        target = tmp_path / "f.txt"

        descriptor = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, b"payload")
            os.fsync(descriptor)
            if hasattr(os, "fdatasync"):
                os.fdatasync(descriptor)
        finally:
            os.close(descriptor)

        assert target.read_bytes() == b"payload"

    @POSIX_ONLY
    def test_fchdir_fchmod_and_fchown_take_a_descriptor(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        original = os.getcwd()

        descriptor = os.open(target, os.O_RDONLY)
        try:
            os.fchmod(descriptor, 0o640)
            info = os.fstat(descriptor)
            os.fchown(descriptor, info.st_uid, info.st_gid)
        finally:
            os.close(descriptor)

        directory = os.open(tmp_path, os.O_RDONLY)
        try:
            os.fchdir(directory)
            assert os.path.samefile(os.getcwd(), tmp_path)
        finally:
            os.chdir(original)
            os.close(directory)

        assert stat_module.S_IMODE(os.stat(target).st_mode) == 0o640

    @LINUX_ONLY
    def test_the_kernel_copies_move_no_bytes_through_python(self, tmp_path: pathlib.Path) -> None:
        """The O(1) space on sendfile, copy_file_range and splice.

        os.read is the control: asked for the same 8 MB it allocates 8 MB,
        where sendfile moves it for about 1.5 KB - the descriptors and the
        int, and nothing that grows with `count`.
        """
        source = tmp_path / "src.bin"
        source.write_bytes(b"x" * 8_000_000)

        def send(count: int) -> None:
            read_fd = os.open(source, os.O_RDONLY)
            write_fd = os.open(
                tmp_path / f"dst{count}.bin", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
            )
            try:
                assert os.sendfile(write_fd, read_fd, 0, count) == count
            finally:
                os.close(read_fd)
                os.close(write_fd)

        small = peak_bytes(lambda: send(1_000))
        large = peak_bytes(lambda: send(8_000_000))

        read_fd = os.open(source, os.O_RDONLY)
        try:
            through_python = peak_bytes(lambda: os.read(read_fd, 8_000_000))
        finally:
            os.close(read_fd)

        assert large < 4 * small, (
            f"8,000x the count should not change the Python-side peak: {small} B against {large} B"
        )
        assert through_python > 100 * large, (
            f"os.read is the control and does allocate the bytes: "
            f"{large} B for sendfile against {through_python} B for read"
        )
        assert (tmp_path / "dst8000000.bin").read_bytes() == source.read_bytes()

    @LINUX_ONLY
    def test_copy_file_range_also_stays_in_the_kernel(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "src.bin"
        source.write_bytes(b"y" * 4_000_000)
        destination = tmp_path / "dst.bin"

        def copy() -> None:
            read_fd = os.open(source, os.O_RDONLY)
            write_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.copy_file_range(read_fd, write_fd, 4_000_000)
            finally:
                os.close(read_fd)
                os.close(write_fd)

        assert peak_bytes(copy) < 100_000, "4 MB moved without a 4 MB buffer"
        assert destination.read_bytes() == source.read_bytes()

    @LINUX_ONLY
    def test_the_linux_descriptor_factories(self) -> None:
        """The O(1) rows for eventfd, memfd_create, pipe2 and pidfd_open."""
        read_end, write_end = os.pipe2(os.O_CLOEXEC)
        try:
            assert os.get_inheritable(read_end) is False, "O_CLOEXEC was applied"
        finally:
            os.close(read_end)
            os.close(write_end)

        event = os.eventfd(7)
        try:
            assert os.eventfd_read(event) == 7, "the counter it was created with"
            os.eventfd_write(event, 3)
            assert os.eventfd_read(event) == 3
        finally:
            os.close(event)

        memory = os.memfd_create("os-page-probe")
        try:
            assert os.fstat(memory).st_size == 0
            os.ftruncate(memory, 4_096)
            assert os.fstat(memory).st_size == 4_096
        finally:
            os.close(memory)

        process = os.pidfd_open(os.getpid())
        try:
            assert os.fstat(process).st_mode
        finally:
            os.close(process)

    @POSIX_ONLY
    def test_openpty_returns_a_terminal_pair(self) -> None:
        """`os.openpty()` | O(1), and the pty helpers around it."""
        controller, follower = os.openpty()
        try:
            assert os.isatty(controller) and os.isatty(follower)
            assert isinstance(os.ttyname(follower), str)
            assert os.get_terminal_size(follower).columns >= 0
            assert os.device_encoding(follower) is None or isinstance(
                os.device_encoding(follower), str
            )
        finally:
            os.close(controller)
            os.close(follower)

    @POSIX_ONLY
    @pytest.mark.skipif(not hasattr(os, "posix_openpt"), reason="os.posix_openpt is 3.13+")
    def test_posix_openpt_grantpt_and_unlockpt(self) -> None:
        openpt = getattr(os, "posix_openpt")  # noqa: B009 - typeshed 3.13+
        grantpt = getattr(os, "grantpt")  # noqa: B009 - typeshed 3.13+
        unlockpt = getattr(os, "unlockpt")  # noqa: B009 - typeshed 3.13+
        ptsname = getattr(os, "ptsname")  # noqa: B009 - typeshed 3.13+

        controller = openpt(os.O_RDWR)
        try:
            grantpt(controller)
            unlockpt(controller)
            name = ptsname(controller)
        finally:
            os.close(controller)

        assert isinstance(name, str) and name

    def test_urandom_returns_what_it_was_asked_for(self) -> None:
        """`os.urandom(size)` | O(size) | O(size)."""
        assert len(os.urandom(0)) == 0
        assert len(os.urandom(4_096)) == 4_096
        assert os.urandom(32) != os.urandom(32)

    @LINUX_ONLY
    def test_getrandom_returns_what_it_was_asked_for(self) -> None:
        assert len(os.getrandom(64)) == 64


class TestProcessAndEnvironment:
    """The process tables, and the environment section's annotations."""

    def test_the_pid_functions_agree_with_the_process(self) -> None:
        pid, ppid = os.getpid(), os.getppid()

        assert pid > 0 and ppid > 0
        assert pid != ppid
        assert os.getpid() == pid, "constant for the life of the process"

    @POSIX_ONLY
    def test_the_id_functions_are_consistent(self) -> None:
        real, effective, saved = os.getresuid()
        assert real == os.getuid(), "the real uid is the first of the three"
        assert effective == os.geteuid(), "and the effective uid is the second"
        assert isinstance(saved, int)
        real_gid, effective_gid, _ = os.getresgid()
        assert real_gid == os.getgid() and effective_gid == os.getegid()
        assert os.getpgrp() > 0 and os.getpgid(0) == os.getpgrp()
        assert os.getsid(0) > 0

    @POSIX_ONLY
    def test_getgroups_returns_one_entry_per_group(self) -> None:
        """`os.getgroups()` | O(g) | O(g) - the list is the output."""
        groups = os.getgroups()

        assert isinstance(groups, list)
        assert all(isinstance(gid, int) for gid in groups)

    @POSIX_ONLY
    def test_uname_carries_five_named_fields(self) -> None:
        """The uname_result table: attribute reads on one struct sequence."""
        info = os.uname()

        assert info.sysname and info.nodename is not None
        assert info.release and info.version and info.machine
        assert tuple(info) == (
            info.sysname,
            info.nodename,
            info.release,
            info.version,
            info.machine,
        )
        assert info.sysname == info[0], "indexing and naming reach the same field"

    def test_cpu_counts_are_positive_and_independent(self) -> None:
        machine = os.cpu_count()

        assert machine is None or machine >= 1
        if hasattr(os, "process_cpu_count"):
            count = getattr(os, "process_cpu_count")  # noqa: B009 - typeshed 3.13+
            available = count()
            assert available is None or available >= 1
            if machine is not None and available is not None:
                assert available <= machine, "the affinity mask can only narrow it"

    @LINUX_ONLY
    def test_sched_affinity_and_parameters(self) -> None:
        """`os.sched_getaffinity(pid)` | O(c) - the set it builds."""
        mask = os.sched_getaffinity(0)

        assert isinstance(mask, set) and mask
        os.sched_setaffinity(0, mask)
        assert os.sched_getaffinity(0) == mask

        policy = os.sched_getscheduler(0)
        assert os.sched_get_priority_min(policy) <= os.sched_get_priority_max(policy)
        assert os.sched_getparam(0).sched_priority == os.sched_param(0).sched_priority
        os.sched_yield()

    @POSIX_ONLY
    def test_priority_and_times_are_readable(self) -> None:
        priority = os.getpriority(os.PRIO_PROCESS, 0)
        os.setpriority(os.PRIO_PROCESS, 0, priority)

        assert os.getpriority(os.PRIO_PROCESS, 0) == priority
        clock = os.times()
        assert clock.user >= 0 and clock.system >= 0
        assert len(os.getloadavg()) == 3

    def test_getcwd_output_tracks_the_path_length(self, tmp_path: pathlib.Path) -> None:
        """`os.getcwd()` | O(L) | O(L) - L is the result, which is the output."""
        original = os.getcwd()
        shallow = tmp_path / "s"
        shallow.mkdir()
        deep = tmp_path.joinpath("d", *["component"] * 20)
        os.makedirs(deep)

        try:
            os.chdir(shallow)
            short = os.getcwd()
            assert os.getcwdb() == os.fsencode(short)
            os.chdir(deep)
            long = os.getcwd()
        finally:
            os.chdir(original)

        assert len(long) > len(short) + 150, (
            f"getcwd returns the path, so its length is the bound: "
            f"{len(short)} against {len(long)} characters"
        )

    def test_umask_round_trips(self) -> None:
        original = os.umask(0o022)
        try:
            assert os.umask(0o022) == 0o022, "the call returns the previous value"
        finally:
            os.umask(original)

    def test_environ_lookup_is_a_dict_lookup(self) -> None:
        os.environ["OS_PAGE_PROBE"] = "value"
        try:
            assert os.environ["OS_PAGE_PROBE"] == "value"
            assert os.environ.get("OS_PAGE_PROBE") == "value"
            assert os.getenv("OS_PAGE_PROBE") == "value"
            assert os.environ.get("OS_PAGE_NOT_SET", "unknown") == "unknown"
            assert os.getenv("OS_PAGE_NOT_SET") is None
        finally:
            del os.environ["OS_PAGE_PROBE"]

        assert "OS_PAGE_PROBE" not in os.environ

    @POSIX_ONLY
    def test_a_lookup_costs_the_value_it_decodes(self) -> None:
        """`os.environ[key]` | O(k + v) - a dict lookup is not the whole of it.

        os._Environ encodes the key and decodes the value around the lookup,
        so a 2 MB value is returned as a 2 MB fresh str: the traced peak is
        the value's size, where a bare dict lookup would return the stored
        object and peak at nothing.

        POSIX only, because it is the decode that is being observed. Windows
        stores str and hands the same object back, which is why the row says
        so and why this would not hold there.
        """
        os.environ["OS_PAGE_SHORT"] = "x"
        os.environ["OS_PAGE_LONG"] = "x" * 2_000_000
        try:
            short_peak = peak_bytes(lambda: os.environ["OS_PAGE_SHORT"])
            long_peak = peak_bytes(lambda: os.environ["OS_PAGE_LONG"])
            assert os.environ["OS_PAGE_LONG"] is not os.environ["OS_PAGE_LONG"], (
                "each lookup decodes afresh, so it cannot be returning one object"
            )
        finally:
            del os.environ["OS_PAGE_SHORT"]
            del os.environ["OS_PAGE_LONG"]

        assert long_peak > 1_000_000, (
            f"the decode allocates the value: {short_peak} B against {long_peak} B"
        )

    def test_streaming_the_view_still_snapshots_the_keys(self) -> None:
        """The other half of the items() row: consuming it is O(m) in space too.

        Nothing is collected here - the loop discards each pair - yet the peak
        rises with the variable count, because _Environ.__iter__ lists its keys
        before yielding any. Measured 1,084 B against 25,084 B for 3,000 more
        variables.
        """

        def consume() -> None:
            for _ in os.environ.items():
                pass

        before = peak_bytes(consume)
        added = [f"OS_PAGE_STREAM_{index}" for index in range(3_000)]
        for key in added:
            os.environ[key] = "v"
        try:
            after = peak_bytes(consume)
        finally:
            for key in added:
                del os.environ[key]

        assert after > 5 * before, (
            f"iterating allocates per variable even when nothing is kept: "
            f"{before} B against {after} B"
        )

    def test_environ_items_is_a_view_not_a_copy(self) -> None:
        """`os.environ.items()` | O(1) - the O(m) is in consuming it.

        Two thousand variables added between the two measurements leave the
        peak unchanged, which no O(m) construction could do. The control is
        the same view materialised, which does grow.
        """
        before = peak_bytes(os.environ.items)
        added = [f"OS_PAGE_FILL_{index}" for index in range(2_000)]
        for key in added:
            os.environ[key] = "x" * 50
        try:
            after = peak_bytes(os.environ.items)
            materialised = peak_bytes(lambda: list(os.environ.items()))
        finally:
            for key in added:
                del os.environ[key]

        assert after <= before + 200, (
            f"items() builds a view, so 2,000 more variables change nothing: "
            f"{before} B against {after} B"
        )
        assert materialised > 100 * after, (
            f"consuming the view is the O(m): {after} B against {materialised} B"
        )

    def test_putenv_does_not_update_the_snapshot(self) -> None:
        """The note beside the putenv row."""
        os.putenv("OS_PAGE_PUTENV", "value")

        assert os.environ.get("OS_PAGE_PUTENV") is None, "os.environ is a snapshot"
        assert os.getenv("OS_PAGE_PUTENV") is None, "getenv reads that snapshot"
        os.unsetenv("OS_PAGE_PUTENV")

    @pytest.mark.skipif(not hasattr(os, "reload_environ"), reason="os.reload_environ is 3.14+")
    def test_reload_environ_rebuilds_the_snapshot(self) -> None:
        reload_environ = getattr(os, "reload_environ")  # noqa: B009 - typeshed 3.14+
        os.putenv("OS_PAGE_RELOAD", "value")
        try:
            assert os.environ.get("OS_PAGE_RELOAD") is None
            reload_environ()
            assert os.environ.get("OS_PAGE_RELOAD") == "value", "rebuilt from the real environment"
        finally:
            os.unsetenv("OS_PAGE_RELOAD")
            reload_environ()

    @POSIX_ONLY
    def test_environb_lookups_skip_the_conversion(self) -> None:
        """Why `os.environb` carries no v term where `os.environ[key]` does.

        The bytes mapping stores what it returns, so two lookups hand back the
        very same object however large the value; os.environ decodes afresh
        each time, which is the test above. The key still has to be hashed
        either way, which is the k both rows keep.

        Not varied here: the key length, which is the term this test leaves to
        the row rather than measuring.
        """
        os.environ["OS_PAGE_BYTES"] = "v" * 1_000_000
        try:
            first = os.environb[b"OS_PAGE_BYTES"]
            assert os.environb[b"OS_PAGE_BYTES"] is first, "no decode, no copy"
            assert os.getenvb(b"OS_PAGE_BYTES") is first
            assert peak_bytes(lambda: os.environb[b"OS_PAGE_BYTES"]) < 1_000, (
                "a 1 MB value costs nothing to look up as bytes"
            )
        finally:
            del os.environ["OS_PAGE_BYTES"]

    def test_get_exec_path_splits_the_path_variable(self) -> None:
        """`os.get_exec_path(env)` | O(p) - p is the length of PATH."""
        path = os.pathsep.join(["/one", "/two", "/three"])
        entries = os.get_exec_path({"PATH": path})

        assert entries == ["/one", "/two", "/three"], "one entry per separator"
        assert os.get_exec_path({"PATH": ""}) == [""]
        assert isinstance(os.get_exec_path(), list)


class TestExitStatusMacros:
    """The Waiting and exit status table: bit tests on an integer.

    No child is started. The macros take a status word, so a constructed one
    exercises the same arithmetic as a waited-for one, without leaving a
    process to reap.
    """

    @POSIX_ONLY
    def test_a_normal_exit_status(self) -> None:
        status = 3 << 8  # exited with code 3

        assert os.WIFEXITED(status)
        assert os.WEXITSTATUS(status) == 3
        assert not os.WIFSIGNALED(status)
        assert not os.WIFSTOPPED(status)
        assert os.waitstatus_to_exitcode(status) == 3

    @POSIX_ONLY
    def test_a_signalled_exit_status(self) -> None:
        import signal

        status = int(signal.SIGTERM)

        assert os.WIFSIGNALED(status)
        assert os.WTERMSIG(status) == signal.SIGTERM
        assert not os.WIFEXITED(status)
        assert not os.WCOREDUMP(status), "no core flag in this status word"
        assert os.WCOREDUMP(status | 0x80), "and the flag is the bit that sets it"
        assert os.waitstatus_to_exitcode(status) == -signal.SIGTERM

    @POSIX_ONLY
    def test_stopped_and_continued_statuses(self) -> None:
        import signal

        stopped = (int(signal.SIGSTOP) << 8) | 0x7F

        assert os.WIFSTOPPED(stopped)
        assert os.WSTOPSIG(stopped) == signal.SIGSTOP
        assert os.WIFCONTINUED(0xFFFF), "the continued status word"
        assert not os.WIFCONTINUED(3 << 8), "and a normal exit is not it"


class TestSystemConfiguration:
    """The System configuration table: lookups, not scans."""

    @POSIX_ONLY
    def test_the_name_tables_are_mappings(self) -> None:
        assert isinstance(os.sysconf_names, dict)
        assert isinstance(os.confstr_names, dict)
        assert isinstance(os.pathconf_names, dict)
        assert os.sysconf("SC_PAGESIZE") > 0
        assert os.sysconf(os.sysconf_names["SC_PAGESIZE"]) == os.sysconf("SC_PAGESIZE")

    @POSIX_ONLY
    def test_pathconf_answers_for_a_path_and_a_descriptor(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")

        by_path = os.pathconf(target, "PC_NAME_MAX")
        descriptor = os.open(target, os.O_RDONLY)
        try:
            by_fd = os.fpathconf(descriptor, "PC_NAME_MAX")
        finally:
            os.close(descriptor)

        assert by_path == by_fd > 0

    @POSIX_ONLY
    def test_confstr_returns_a_string(self) -> None:
        value = os.confstr("CS_PATH")

        assert isinstance(value, str) and value, f"CS_PATH returned {value!r}"

    def test_the_supports_sets_are_sets(self) -> None:
        """Membership, so the cost does not depend on how many functions are in them."""
        for name in (
            "supports_dir_fd",
            "supports_fd",
            "supports_follow_symlinks",
            "supports_effective_ids",
        ):
            value = getattr(os, name)
            assert isinstance(value, (set, frozenset)), f"os.{name} is {type(value).__name__}"

        # Membership is the operation, so a known member has to be found.
        assert os.stat in os.supports_fd
        assert os.stat in os.supports_follow_symlinks
        assert os.path.join not in os.supports_fd, "and a non-member has to not be"

    def test_strerror_returns_a_message(self) -> None:
        """`os.strerror(code)` | O(m) - m is the message."""
        import errno

        message = os.strerror(errno.ENOENT)

        assert isinstance(message, str) and message

    @POSIX_ONLY
    def test_device_numbers_round_trip(self) -> None:
        """major, minor and makedev are arithmetic on one integer."""
        device = os.makedev(8, 3)

        assert os.major(device) == 8
        assert os.minor(device) == 3

    @POSIX_ONLY
    def test_statvfs_carries_named_counters(self, tmp_path: pathlib.Path) -> None:
        """The statvfs_result table."""
        info = os.statvfs(tmp_path)

        assert info.f_bsize > 0 and info.f_frsize > 0
        assert info.f_blocks >= info.f_bfree >= 0
        assert info.f_bavail >= 0
        assert info.f_files >= 0 and info.f_ffree >= 0 and info.f_favail >= 0
        assert info.f_namemax > 0
        assert isinstance(info.f_flag, int) and isinstance(info.f_fsid, int)

        descriptor = os.open(tmp_path, os.O_RDONLY)
        try:
            assert os.fstatvfs(descriptor).f_bsize == info.f_bsize
        finally:
            os.close(descriptor)

    def test_terminal_size_is_a_named_pair(self) -> None:
        """The terminal_size table, built directly so no tty is needed."""
        size = os.terminal_size((80, 24))

        assert size.columns == 80
        assert size.lines == 24
        assert tuple(size) == (80, 24)

    @POSIX_ONLY
    def test_ctermid_names_the_controlling_terminal(self) -> None:
        assert isinstance(os.ctermid(), str)


@POSIX_ONLY
class TestExtendedAttributes:
    """`os.getxattr` and friends. Skipped where the filesystem refuses them."""

    @staticmethod
    def _supported(target: pathlib.Path) -> bool:
        try:
            os.setxattr(target, b"user.probe", b"1")
        except OSError:
            return False
        os.removexattr(target, b"user.probe")
        return True

    def test_value_and_name_lengths_are_the_bounds(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        if not self._supported(target):
            pytest.skip("this filesystem does not support user extended attributes")

        os.setxattr(target, b"user.short", b"a")
        os.setxattr(target, b"user.long", b"b" * 4_000)

        assert os.getxattr(target, b"user.short") == b"a"
        assert len(os.getxattr(target, b"user.long")) == 4_000
        # A filesystem may carry attributes of its own, such as security.*,
        # so the assertion is about the ones this test set.
        listed = sorted(n for n in os.listxattr(target) if n.startswith("user."))
        assert listed == ["user.long", "user.short"]

        os.removexattr(target, b"user.long")
        assert [n for n in os.listxattr(target) if n.startswith("user.")] == ["user.short"]


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while end < len(lines) and not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            assert end < len(lines), f"unterminated block at {PAGE.name}:{start}"
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


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
    """Every block runs to completion in a temporary working directory."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            work = tmp_path / f"block{line}"
            work.mkdir()
            result = _run(source, work)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS, f"ran {ran} blocks, expected {EXPECTED_BLOCKS}"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import os\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr


class TestDocumentedOutputs:
    """The values the page's examples state in comments."""

    def test_join_split_and_splitext(self) -> None:
        path = os.path.join("home", "user", "documents", "file.txt")
        dirname, filename = os.path.split(path)

        assert dirname == os.path.join("home", "user", "documents")
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

        assert resolved == str(tmp_path / "relative" / "path"), (
            "rooted at the working directory that was current, not merely absolute"
        )
        assert os.path.isabs(resolved)

    def test_environ_get_falls_back_to_the_default(self) -> None:
        assert os.environ.get("A_NAME_NOTHING_WOULD_SET", "unknown") == "unknown"
