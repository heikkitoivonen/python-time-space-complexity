"""Tests to verify documented behaviour of the pathlib module.

Most of this is counted or measured with tracemalloc rather than timed. A
syscall is observable and a peak allocation is reproducible, so the page's
claims about how many directory reads an operation makes, and how much it
holds while it makes them, need no tolerance.

Five claims did not survive measurement:

* `Path.iterdir()` was documented O(1) space per item, "iterator uses O(1)
  space per entry". It is an iterator, but not a streaming one: every
  supported version reads the directory in full before yielding anything -
  through os.listdir up to 3.12 and a list() of os.scandir from 3.13. Taking
  only the first item from a directory of 1,600 entries peaks at roughly 8x
  what 200 entries cost, on every version (x7.11 on 3.10, x7.95 on 3.14). The
  row is O(d).
* `Path.glob()` and `Path.rglob()` carried the same O(1)-per-item space claim,
  and the same measurement refutes it: a pattern matching exactly one file
  peaks at x7.5-x7.7 more in a directory of 1,600 than in one of 200 on every
  version. Space follows the widest directory scanned, not the matches
  yielded. The glob section also defined its size variable as "matching
  entries" while the table said "entries checked"; the scan is what costs, so
  both now say entries scanned.
* `Path.rglob()` holds the directories it has found but not yet descended
  into, so depth is a term of its own: 32x the depth costs x171 on 3.10, x131
  on 3.11, x6.1 on 3.12 and x2.1 on 3.13 and 3.14. The row is O(w + d) - tight
  on the older pair, an upper bound on the newer.
* `Path.walk()` was documented O(d) space, and is the same shape as os.walk
  for the same reason - it delegates to it. 4x the siblings at a fixed depth
  costs x3.8-x3.9. The row is O(w + d), matching the os page. The row also
  carried no version marker: Path.walk() does not exist before 3.12, which is
  two of the five versions this project supports.
* `Path.is_mount()` was documented O(1), and is O(1) on four of the five
  supported versions - 6 stat calls at any depth on 3.10 and 3.11, 2 on 3.13
  and 3.14. On 3.12 it reaches an os.path.ismount that resolves the parent
  rather than lstat-ing it, so the count rises one per component: 6, 9 and 21
  at the three depths measured here. The row says O(1) and names 3.12.

Two rows became version-dependent rather than wrong:

* `Path(str)` was documented O(n) time and space. gh-101362 made PurePath
  store its arguments and parse them on first use, so from 3.12 construction
  is O(1): a 100,000-character path peaks at 100,793 B on 3.10 and 248 B on
  3.12, and the same 248 B for a 10-character one. The parse is deferred, not
  removed - the first str() pays it and caches the result.
* Joining is deferred with it. A 1,000,000-character segment costs x19.0 a
  10-character one on 3.10 and x26.9 on 3.11; from 3.12 the ratio is 1.0.
  This is the only claim here settled with a stopwatch: the peak allocation
  does not separate the two, because splitting a segment with no separator in
  it hands back the same string object either way.

Ten of the page's 25 code blocks did not run. Two could never have:
`process(match)` and `for name in files`, with neither name defined. One
raised on four of the five supported versions - `Path('large_name' *
100).exists()` is a 1,000-character basename, and before 3.14 exists()
re-raised the resulting ENAMETOOLONG rather than returning False. The other
seven reached absolute or invented placeholder paths. Every block runs now,
on 3.10 through 3.14, and the runner below holds none of them back.

Not settled by execution:

* `Path.owner()` and `Path.group()` resolve a uid and gid through the user
  database. The stat call is one syscall; what the lookup behind it costs
  depends on the NSS backend, which may be a network service. The rows price
  the syscall and name the lookup.
* `Path.lchmod()` on the subject it exists for. On Linux it succeeds on a
  regular file and raises NotImplementedError on an actual symlink, on every
  supported version, so the row cannot be exercised here as intended.
* Windows behaviour throughout, including that is_mount() is POSIX-only
  before 3.12 and that drive letters change what absolute() does. This suite
  runs on one platform at a time; the symlink tests below are POSIX-only and
  skip elsewhere.
* "O(1)" for a syscall is a choice of unit - the kernel still resolves the
  path component by component. These tests count syscalls and follow the same
  convention as the os page rather than measuring the kernel.

Axes deliberately not varied: the filesystem type (everything runs on
tmp_path), symlink density inside resolve(), and case-insensitive globbing.
"""

import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pathlib.md"

EXPECTED_BLOCKS = 25

POSIX_ONLY = pytest.mark.skipif(os.name != "posix", reason="POSIX-only behaviour")

# gh-101362 landed in 3.12: PurePath keeps its arguments and parses them on
# first use instead of at construction.
CONSTRUCTION_IS_DEFERRED = sys.version_info >= (3, 12)
# gh-112855 landed in 3.13: iterdir() reads the directory when it is called
# rather than at the first next().
ITERDIR_IS_EAGER = sys.version_info >= (3, 13)

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


class SyscallCounter:
    """Counts the filesystem syscalls a pathlib operation makes."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = dict.fromkeys(SYSCALL_NAMES, 0)

    @property
    def stat_family(self) -> int:
        """stat and lstat together.

        Which of the two a predicate reaches moved between versions - 3.12
        asks for lstat through os.stat(follow_symlinks=False) where 3.14 calls
        os.lstat - so the count that means "one syscall" is the sum.
        """
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
    # functions as class attributes at import time. Patching os alone would
    # count nothing there, and every assertion below would read as a pass.
    accessor = getattr(pathlib, "_NormalAccessor", None)
    saved: dict[str, Any] = {}
    for name, wrapper in wrappers.items():
        setattr(os, name, wrapper)
        # Only displace an accessor attribute that *is* the os function.
        # Where 3.10 wraps one in a method of its own, that method looks the
        # name up at call time and the patched os already counts it.
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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def drain(iterator: Any) -> None:
    """Exhaust an iterator without retaining what it yields.

    A list would grow with the tree and land in the traced peak, which is a
    measurement of the collector rather than of the walk.
    """
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


def make_deep(root: pathlib.Path, depth: int) -> pathlib.Path:
    """A chain of `depth` directories with one file at the bottom."""
    deep = root / f"deep{depth}"
    deep.mkdir()
    node = deep
    for _ in range(depth):
        node = node / "d"
        node.mkdir()
    (node / "leaf.txt").touch()
    return deep


def remove_deep(root: pathlib.Path) -> None:
    """Unwind a chain from the bottom.

    shutil.rmtree recurses, so the chains built here are removed before the
    test ends rather than left for it.
    """
    node = root
    while True:
        children = [child for child in node.iterdir() if child.is_dir()]
        if not children:
            break
        node = children[0]
    for entry in node.iterdir():
        entry.unlink()
    while node != root.parent:
        node.rmdir()
        node = node.parent


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
    """The O(1) rows: `Path.exists()`, `is_file()`, `is_dir()` and the rest.

    "One stat call" is the whole content of those rows, and it is a count, so
    it is asserted as one rather than timed. stat and lstat are summed because
    which of the two a predicate reaches changed between versions without the
    count ever changing.
    """

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

    @POSIX_ONLY
    def test_owner_and_group_make_one_stat_call_each(self, tmp_path: pathlib.Path) -> None:
        """The countable half of those two rows.

        What the uid and gid are then resolved through is the user database,
        which may be a network service; that half is named on the page and
        not measured here.
        """
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

    def test_a_predicate_does_not_read_the_directory_it_lives_in(
        self, tmp_path: pathlib.Path
    ) -> None:
        """O(1) means constant in the neighbours as well as in the path."""
        crowded = make_wide(tmp_path, 400)
        target = crowded / "f000000.txt"

        with counting_syscalls() as counter:
            assert target.is_file()

        assert counter.stat_family == 1
        assert counter.listings == 0

    def test_is_mount_stats_the_parent_except_on_312(self, tmp_path: pathlib.Path) -> None:
        """`Path.is_mount()` | O(1), and O(n) in components on 3.12.

        3.10 and 3.11 use pathlib's own implementation (6 stat calls at any
        depth) and 3.13 and 3.14 reach os.path.ismount, which lstats the path
        and the parent it joins onto it (2 calls). 3.12 reaches an
        os.path.ismount that resolves the parent instead, so its count rises
        one per component - 6, 9 and 21 for the depths used here. The exact
        constants are version detail; what is asserted is the growth, which is
        what the row is about.
        """
        shallow = tmp_path / "d"
        shallow.mkdir()
        deep = tmp_path / "n"
        node = deep
        for _ in range(15):
            node = node / "x"
        node.mkdir(parents=True)

        with counting_syscalls() as counter:
            shallow.is_mount()
        shallow_calls = counter.stat_family

        with counting_syscalls() as counter:
            node.is_mount()
        deep_calls = counter.stat_family

        if sys.version_info[:2] == (3, 12):
            assert deep_calls - shallow_calls == 15, (
                f"3.12 resolves the parent, one lstat per component: "
                f"{shallow_calls} against {deep_calls}"
            )
        else:
            assert shallow_calls == deep_calls, (
                f"is_mount should not grow with depth: {shallow_calls} against {deep_calls}"
            )
            assert deep_calls <= 8, f"is_mount made {deep_calls} stat calls"


class TestModificationRowsAreOneSyscall:
    """`Path.chmod()`, `Path.unlink()`, `Path.rmdir()` | O(1) | O(1).

    The same convention as the predicates above: the row prices one syscall,
    and the count is what is asserted.
    """

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

    @POSIX_ONLY
    def test_lchmod_cannot_be_exercised_on_a_symlink_here(self, tmp_path: pathlib.Path) -> None:
        """Why the lchmod row is recorded as unsettled rather than tested."""
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "link"
        link.symlink_to(target)

        target.lchmod(0o600)

        with pytest.raises(NotImplementedError):
            link.lchmod(0o600)


class TestIterdirReadsTheWholeDirectory:
    """`Path.iterdir()` | O(d) | O(d) - the page said O(1) space per item.

    iterdir() returns an iterator, which is why the claim looked right, but
    the directory is read in full before the first item appears: os.listdir up
    to 3.12, and list(os.scandir(...)) from 3.13. Both materialise every name.
    """

    def test_the_first_item_costs_the_whole_listing(self, tmp_path: pathlib.Path) -> None:
        small = make_wide(tmp_path, 200)
        large = make_wide(tmp_path, 1600)

        def first(directory: pathlib.Path) -> None:
            next(iter(directory.iterdir()))

        small_peak = peak_bytes(lambda: first(small))
        large_peak = peak_bytes(lambda: first(large))

        assert large_peak > 3 * small_peak, (
            f"8x the entries should cost about 8x even for one item, so O(1) per "
            f"item cannot be the bound: {small_peak} B against {large_peak} B"
        )

    def test_iterdir_reads_the_directory_once(self, tmp_path: pathlib.Path) -> None:
        directory = make_wide(tmp_path, 20)

        with counting_syscalls() as counter:
            entries = list(directory.iterdir())

        assert len(entries) == 20
        assert counter.listings == 1, f"expected one directory read, got {counter.listings}"

    def test_when_the_directory_is_read(self, tmp_path: pathlib.Path) -> None:
        """The 3.13 Version Note, observed through where the error surfaces.

        Before 3.13 iterdir() is a generator function, so calling it does
        nothing and a missing directory is only reported at the first next().
        From 3.13 the scan happens in the call itself.
        """
        missing = tmp_path / "nope"

        if ITERDIR_IS_EAGER:
            with pytest.raises(FileNotFoundError):
                missing.iterdir()
        else:
            iterator = missing.iterdir()
            with pytest.raises(FileNotFoundError):
                next(iter(iterator))


class TestGlobScansEntriesNotMatches:
    """`Path.glob(pattern)` | O(n) | O(w) - n is entries scanned, not matched.

    The page's table said "entries checked" while its glob section said
    "matching entries"; only one of those can be the size variable. Holding
    the matches at exactly one and growing the haystack settles it, and
    refutes the O(1)-per-item space claim at the same time.
    """

    def test_one_match_still_costs_the_whole_directory(self, tmp_path: pathlib.Path) -> None:
        def haystack(count: int) -> pathlib.Path:
            directory = tmp_path / f"h{count}"
            directory.mkdir()
            for index in range(count):
                (directory / f"f{index:06d}.dat").touch()
            (directory / "needle.txt").touch()
            return directory

        small, large = haystack(200), haystack(1600)
        assert len(list(small.glob("*.txt"))) == 1
        assert len(list(large.glob("*.txt"))) == 1

        small_peak = peak_bytes(lambda: list(small.glob("*.txt")))
        large_peak = peak_bytes(lambda: list(large.glob("*.txt")))

        assert large_peak > 3 * small_peak, (
            f"the same single match costs 8x more in an 8x directory, so the "
            f"scan is what the bound is in: {small_peak} B against {large_peak} B"
        )

    def test_a_nested_pattern_costs_every_directory_it_opens(self, tmp_path: pathlib.Path) -> None:
        """The same claim one level down, where the matches are again fixed.

        Counted syscalls would be the sharper instrument, but not a portable
        one: 3.13 globs through a helper that captured os.scandir at import,
        so a patched os counts nothing there while 3.10 and 3.14 count every
        call. The peak needs no such knowledge and moves x6 for 8x the
        subdirectories on every supported version.
        """

        def tree(count: int) -> pathlib.Path:
            root = tmp_path / f"t{count}"
            root.mkdir()
            for index in range(count):
                sub = root / f"s{index:05d}"
                sub.mkdir()
                (sub / "note.dat").touch()
            (root / "s00000" / "only.py").touch()
            return root

        small, large = tree(50), tree(400)
        assert len(list(small.glob("*/*.py"))) == 1
        assert len(list(large.glob("*/*.py"))) == 1

        small_peak = peak_bytes(lambda: list(small.glob("*/*.py")))
        large_peak = peak_bytes(lambda: list(large.glob("*/*.py")))

        assert large_peak > 3 * small_peak, (
            f"8x the subdirectories to open, same single match: "
            f"{small_peak} B against {large_peak} B"
        )


class TestRglobSpaceNeedsBothTerms:
    """`Path.rglob(pattern)` | O(n) | O(w + d) - the page said O(1) per item.

    Width behaves the same on every supported version. Depth is the term that
    changed: the recursive selector on 3.10 and 3.11 pays x171 and x131 for
    32x the depth, where the iterative globber of 3.13 and 3.14 pays x2.1.
    Loose there, but present, and the page states the bound that holds on
    both.
    """

    def test_peak_grows_with_the_widest_directory(self, tmp_path: pathlib.Path) -> None:
        small = make_wide(tmp_path, 200)
        large = make_wide(tmp_path, 1600)

        small_peak = peak_bytes(lambda: drain(small.rglob("*.txt")))
        large_peak = peak_bytes(lambda: drain(large.rglob("*.txt")))

        assert large_peak > 3 * small_peak, f"the w term: {small_peak} B against {large_peak} B"

    def test_peak_grows_with_the_depth(self, tmp_path: pathlib.Path) -> None:
        """The d term, at a fixed breadth of one.

        32x rather than 8x: on 3.13 and 3.14 an 8x step leaves the ratio at
        x1.1, too close to any threshold that also excludes a constant. The
        first traced run of each tree costs more than the ones after it, so
        both are warmed up before they are measured.
        """
        shallow = make_deep(tmp_path, 20)
        nested = make_deep(tmp_path, 640)
        drain(shallow.rglob("*.txt"))
        drain(nested.rglob("*.txt"))

        shallow_peak = peak_bytes(lambda: drain(shallow.rglob("*.txt")))
        nested_peak = peak_bytes(lambda: drain(nested.rglob("*.txt")))
        remove_deep(nested)

        assert nested_peak > 1.25 * shallow_peak, (
            f"32x the depth should cost more, so O(w) alone cannot be the "
            f"bound: {shallow_peak} B against {nested_peak} B"
        )

    def test_rglob_is_glob_with_a_leading_double_star(self, tmp_path: pathlib.Path) -> None:
        """The page states the equivalence; it used to state it as `**/*pattern`."""
        root = tmp_path / "tree"
        root.mkdir()
        (root / "a").mkdir()
        (root / "a" / "x.py").touch()
        (root / "y.py").touch()

        assert sorted(root.rglob("*.py")) == sorted(root.glob("**/" + "*.py"))


@pytest.mark.skipif(sys.version_info < (3, 12), reason="Path.walk() is 3.12+")
class TestWalkSpaceNeedsBothTerms:
    """`Path.walk()` | O(n) | O(w + d) - the page said O(d), and no version.

    Path.walk() delegates to os.walk, so it inherits the bound the os page
    already carries: the queued entries are a term of their own, and 4x the
    siblings at a fixed depth costs about 4x.
    """

    def test_peak_grows_with_the_sibling_count(self, tmp_path: pathlib.Path) -> None:
        small = make_wide_dirs(tmp_path, 200)
        large = make_wide_dirs(tmp_path, 800)

        small_peak = peak_bytes(lambda: drain(small.walk()))  # type: ignore[attr-defined]
        large_peak = peak_bytes(lambda: drain(large.walk()))  # type: ignore[attr-defined]

        assert large_peak > 2.5 * small_peak, (
            f"4x the siblings should cost about 4x, so O(d) alone cannot be the "
            f"bound: {small_peak} B against {large_peak} B"
        )

    def test_walk_visits_every_entry(self, tmp_path: pathlib.Path) -> None:
        """O(n) time: the traversal is one visit per directory."""
        wide = make_wide_dirs(tmp_path, 20)
        (wide / "d00000" / "leaf.txt").touch()

        visited = list(wide.walk())  # type: ignore[attr-defined]

        assert len(visited) == 21, "the root plus each subdirectory"
        assert sum(len(files) for _, _, files in visited) == 1


class TestConstructionIsDeferred:
    """`Path(str)` | O(n) | O(n), and O(1) from 3.12.

    Before 3.12 the constructor splits the string immediately. From 3.12 it
    keeps the arguments and splits on first use, so the peak stops tracking
    the path's length: 100,793 B for 100,000 characters on 3.10, and the same
    248 B as a 10-character path on 3.12.
    """

    def test_the_peak_tracks_the_string_only_before_312(self) -> None:
        short = "/" + "a" * 10
        long_path = "/" + "a" * 100_000

        short_peak = peak_bytes(lambda: pathlib.PurePath(short))
        long_peak = peak_bytes(lambda: pathlib.PurePath(long_path))

        if CONSTRUCTION_IS_DEFERRED:
            assert long_peak < 2 * short_peak, (
                f"3.12 stores the string without parsing it, so a 10,000x path "
                f"should cost the same: {short_peak} B against {long_peak} B"
            )
        else:
            assert long_peak > 50 * short_peak, (
                f"before 3.12 the constructor parses, so the peak should track "
                f"the string: {short_peak} B against {long_peak} B"
            )

    def test_the_parse_is_deferred_not_removed(self) -> None:
        """The section's claim that first use pays it, and pays it once.

        Measured as allocation rather than elapsed time: the first str()
        produces the joined string, and the second hands back the object it
        cached, allocating nothing that tracks the path's length.
        """
        path = pathlib.PurePath("/" + "a" * 100_000)

        first_peak = peak_bytes(lambda: str(path))
        second_peak = peak_bytes(lambda: str(path))

        assert first_peak > 50_000, f"the first str() should build the path: {first_peak} B"
        assert second_peak < first_peak / 50, (
            f"the second str() should be cached: {first_peak} B against {second_peak} B"
        )


class TestJoinIsDeferred:
    """`path / segment` | O(n) | O(n), and deferred from 3.12 with the rest.

    This is the one claim on the page settled with a stopwatch. The peak
    allocation cannot separate the versions here: splitting a segment that
    holds no separator hands back the same string object, so neither branch
    allocates in proportion to it. Elapsed time separates them cleanly -
    x19.0 on 3.10 and x26.9 on 3.11 for a 100,000x segment, against x1.0 from
    3.12.
    """

    @staticmethod
    def _join_ns(base: pathlib.PurePath, segment: str) -> float:
        best = None
        for _ in range(9):
            start = time.perf_counter_ns()
            for _ in range(50):
                _ = base / segment
            elapsed = (time.perf_counter_ns() - start) / 50
            best = elapsed if best is None else min(best, elapsed)
        assert best is not None
        return best

    @pytest.mark.timing
    def test_the_join_scans_the_segment_only_before_312(self) -> None:
        base = pathlib.PurePath("/tmp")
        short = self._join_ns(base, "b" * 10)
        long_segment = self._join_ns(base, "b" * 1_000_000)
        ratio = long_segment / short

        if CONSTRUCTION_IS_DEFERRED:
            assert ratio < 3, (
                f"3.12 appends the segment unparsed, so a 100,000x segment should "
                f"cost the same: {short:.0f} ns against {long_segment:.0f} ns"
            )
        else:
            assert ratio > 5, (
                f"before 3.12 the join parses the segment: {short:.0f} ns against "
                f"{long_segment:.0f} ns"
            )


class TestResolveCostsOneLstatPerComponent:
    """`Path.resolve()` | O(n) | O(n) | n = path components; one lstat each."""

    def test_the_lstat_calls_track_the_component_count(self, tmp_path: pathlib.Path) -> None:
        shallow = tmp_path / "a"
        shallow.mkdir()
        deep = shallow
        for index in range(8):
            deep = deep / f"lvl{index}"
        deep.mkdir(parents=True)

        with counting_syscalls() as counter:
            shallow.resolve()
        shallow_calls = counter.stat_family

        with counting_syscalls() as counter:
            deep.resolve()
        deep_calls = counter.stat_family

        assert deep_calls - shallow_calls == 8, (
            f"eight more components should cost eight more lstat calls: "
            f"{shallow_calls} against {deep_calls}"
        )


class TestMkdirParents:
    """`Path.mkdir()` | O(1), and O(d) for d missing components with parents=True."""

    def test_each_missing_component_costs_a_call(self, tmp_path: pathlib.Path) -> None:
        with counting_syscalls() as counter:
            (tmp_path / "one").mkdir()
        plain = counter.counts["mkdir"]

        with counting_syscalls() as counter:
            (tmp_path / "a" / "b" / "c" / "d" / "e").mkdir(parents=True)
        nested = counter.counts["mkdir"]

        assert plain == 1
        assert nested >= 5, f"five missing components, {nested} mkdir calls"
        assert (tmp_path / "a" / "b" / "c" / "d" / "e").is_dir()


class TestFileIOIsLinearInSize:
    """The read_text/read_bytes and write_text/write_bytes rows."""

    def test_text_round_trips_every_character(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        payload = "x" * 100_000

        target.write_text(payload, encoding="utf-8")

        assert target.stat().st_size == len(payload)
        assert target.read_text(encoding="utf-8") == payload

    def test_bytes_round_trip(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.bin"
        payload = b"\x00\xff" * 5_000

        target.write_bytes(payload)

        assert target.read_bytes() == payload

    def test_read_holds_the_whole_file(self, tmp_path: pathlib.Path) -> None:
        """O(n) space: the content is materialised, not streamed."""
        small = tmp_path / "small.txt"
        large = tmp_path / "large.txt"
        small.write_text("x" * 10_000, encoding="utf-8")
        large.write_text("x" * 800_000, encoding="utf-8")

        small_peak = peak_bytes(lambda: small.read_text(encoding="utf-8"))
        large_peak = peak_bytes(lambda: large.read_text(encoding="utf-8"))

        assert large_peak > 10 * small_peak, (
            f"80x the file should cost about 80x: {small_peak} B against {large_peak} B"
        )

    def test_write_text_overwrites_rather_than_appends(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("a" * 1_000, encoding="utf-8")

        target.write_text("b", encoding="utf-8")

        assert target.read_text(encoding="utf-8") == "b"


class TestLinkAndRenameRows:
    """`Path.readlink()`, `Path.rename()` and `Path.replace()`."""

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
        assert link.stat().st_size == 10, "stat follows the link"
        assert link.lstat().st_size != 10, "lstat describes the link itself"

    def test_rename_and_replace_move_without_copying(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "a.txt"
        source.write_text("payload", encoding="utf-8")
        destination = tmp_path / "b.txt"

        source.rename(destination)

        assert destination.read_text(encoding="utf-8") == "payload"
        assert not source.exists()

        other = tmp_path / "c.txt"
        other.write_text("other", encoding="utf-8")
        other.replace(destination)

        assert destination.read_text(encoding="utf-8") == "other"


class TestVersionNotes:
    """Each dated entry in Version Notes, checked against this interpreter."""

    def test_the_apis_appear_when_the_page_says_they_do(self) -> None:
        added: dict[str, tuple[int, int]] = {
            "hardlink_to": (3, 10),
            "walk": (3, 12),
            "from_uri": (3, 13),
            "full_match": (3, 13),
            "copy": (3, 14),
            "copy_into": (3, 14),
            "move": (3, 14),
            "move_into": (3, 14),
            "info": (3, 14),
        }

        for name, version in added.items():
            expected = sys.version_info >= version
            assert hasattr(pathlib.Path, name) is expected, (
                f"Path.{name} should exist from {version[0]}.{version[1]}"
            )

    def test_link_to_is_gone_from_312(self) -> None:
        assert hasattr(pathlib.Path, "link_to") is (sys.version_info < (3, 12))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Path.from_uri() is 3.13+")
    def test_as_uri_and_from_uri_round_trip(self, tmp_path: pathlib.Path) -> None:
        uri = tmp_path.as_uri()

        assert uri.startswith("file://")
        assert pathlib.Path.from_uri(uri) == tmp_path  # type: ignore[attr-defined]


class TestComparisonWithOsPath:
    """The Comparison section: os.path.join always produces the joined string.

    Allocation is the observable that separates the two sides here, and it is
    the one place it does: joining a 1,000,000-character segment onto a path
    peaks in proportion to it through os.path.join on every version, while
    pathlib's `/` never allocates in proportion to the segment - before 3.12
    because splitting a separator-free segment hands back the same object,
    and from 3.12 because nothing is split at all.
    """

    def test_os_path_join_builds_the_string_every_time(self) -> None:
        short, long_segment = "b" * 10, "b" * 1_000_000

        short_peak = peak_bytes(lambda: os.path.join("data", short))
        long_peak = peak_bytes(lambda: os.path.join("data", long_segment))

        assert long_peak > 500_000, (
            f"the joined string should be built: {short_peak} B against {long_peak} B"
        )

    def test_the_pathlib_join_does_not(self) -> None:
        base = pathlib.PurePath("data")
        short, long_segment = "b" * 10, "b" * 1_000_000

        short_peak = peak_bytes(lambda: base / short)
        long_peak = peak_bytes(lambda: base / long_segment)

        assert long_peak < 10_000, (
            f"the segment should not be copied: {short_peak} B against {long_peak} B"
        )


class TestSafeDeletionPattern:
    """`shutil.rmtree(path)` | O(n) where n = total entries, in the pattern block."""

    def test_rmtree_unlinks_every_entry(self, tmp_path: pathlib.Path) -> None:
        """4x the files costs exactly 4x the unlink calls."""
        small = make_wide(tmp_path, 20)
        large = make_wide(tmp_path, 80)

        with counting_syscalls() as counter:
            shutil.rmtree(small)
        small_unlinks = counter.counts["unlink"]

        with counting_syscalls() as counter:
            shutil.rmtree(large)
        large_unlinks = counter.counts["unlink"]

        assert not small.exists()
        assert not large.exists()
        assert small_unlinks == 20, f"one unlink per file, got {small_unlinks}"
        assert large_unlinks == 80, f"one unlink per file, got {large_unlinks}"


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
    """Every block runs, in a directory of its own, with nothing held back.

    Nothing is pre-classified, which is what makes this catch a real defect:
    any non-zero exit is a failure, so a NameError has nowhere to hide behind
    an allowance for missing paths.
    """

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
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("from pathlib import Path\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
