"""Tests to verify documented behaviour of the pathlib module.

Most of this is counted or measured with tracemalloc rather than timed. A
syscall is observable and a peak allocation is reproducible, so the page's
claims about how many directory reads an operation makes, and how much it
holds while it makes them, need no tolerance.

What the directory operations hold:

* `Path.iterdir()` is O(d) in space as well as time. It returns an iterator,
  but not a streaming one: every supported version reads the directory in full
  before yielding anything - through os.listdir up to 3.12 and a list() of
  os.scandir from 3.13. Taking only the first item from a directory of 1,600
  entries peaks at roughly 8x what 200 entries cost (x7.11 on 3.10, x7.95 on
  3.14).
* `Path.glob()` is O(w) in the widest directory it scans, for the same reason,
  and its time is in entries scanned rather than matched: a pattern matching
  exactly one file peaks at x7.5-x7.7 more in a directory of 1,600 than in one
  of 200, on every version.
* `Path.rglob()` and a `**` pattern pay a depth term as well: 32x the depth
  costs x171 on 3.10, x131 on 3.11, x6.1 on 3.12 and x2.1 on 3.13 and 3.14.
  O(w + d) bounds every version, but the term is not the same thing on each.
  Varying component length at a fixed total path length separates them: with
  1,280 characters of tail either way, 640 nested directories cost 3,628,740 B
  against 64,140 B for 20 on 3.10, while on 3.14 the same pair costs 11,962 B
  and 11,988 B - indistinguishable, because what grows there is the length of
  the paths the walk carries rather than a queue of directories behind them.
  The page states the terms and no mechanism.
* `Path.walk()` is 3.12+ and delegates to os.walk, so it carries that page's
  O(w + d): 4x the siblings at a fixed depth costs x3.8-x3.9.

Where the version matters:

* `Path(str)` is O(n) in the string before 3.12 and O(1) from it. gh-101362
  made PurePath store its arguments and parse them on first use, so a
  100,000-character path peaks at 100,793 B on 3.10 and 248 B on 3.12 - the
  same 248 B a 10-character path costs. The parse is deferred, not removed:
  the first str() pays it and caches the result.
* Joining is deferred with it. A 1,000,000-character segment costs x19.0 a
  10-character one on 3.10 and x26.9 on 3.11; from 3.12 the ratio is 1.0.
  This is the only claim here settled with a stopwatch, because the peak
  allocation does not separate the two: splitting a segment with no separator
  in it hands back the same string object either way.
* `Path.is_mount()` is O(1) on four of the five supported versions - 6 stat
  calls at any depth on 3.10 and 3.11, 2 on 3.13 and 3.14. On 3.12 it reaches
  an os.path.ismount that resolves the parent rather than lstat-ing it, so the
  count rises one per component: 6, 9 and 21 at the three depths measured here.
* `Path.iterdir()` reads the directory when it is called from 3.13, and at the
  first next() before that, so a missing directory surfaces at different
  moments.

Pure paths are the other half of the module and do no I/O at all: every
operation in the pure table runs against a path that does not exist, under the
same syscall counter, and reaches the filesystem zero times. Three of them cost
more than their API suggests:

* `PurePath.parts` rebuilds its tuple on every access from 3.12, where up to
  3.11 it was cached on the instance. Identity settles it with no stopwatch -
  `p.parts is p.parts` is False from 3.12 and True before.
* `PurePath.relative_to()` and `is_relative_to()` are O(n²) from 3.12, where
  the search walks one path's parents and rescans the other's for each
  candidate. 4x the components costs x8.2 to x9.1 there against x1.7 to x2.0
  before, and at 200 components the call is 2.2 us on 3.10 against 393 us on
  3.14.
* `PurePath.parents` is a lazy sequence, O(1) to obtain and holding nothing,
  but `list(parents)` is O(n²): each of the n parents holds up to n
  components.

Python 3.14 adds two rows worth measuring. `Path.info` caches what it stats -
four queries through one info object cost one stat call where four `Path`
predicates cost four - and the cache never expires, so a fresh `Path` is the
only way to see a changed file. `Path.copy()` streams: its peak is the same
for a 1 MB file and an 8 MB one.

pathlib's public surface is `pathlib.__all__` plus the public attributes of
PurePath and Path. `dir(pathlib)` is not the right set - the module leaks its
own imports, and on 3.14 that is a hundred-odd errno constants.
TestEveryPublicNameIsDocumented compares the tables against that surface in
both directions.

All 30 of the page's code blocks run, on 3.10 through 3.14, except the two
calling 3.14 APIs, which are counted rather than classified by outcome: any
non-zero exit is a failure, so a NameError has nowhere to hide behind an
allowance for missing paths.

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
import warnings
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pathlib.md"

EXPECTED_BLOCKS = 30
# Two blocks use APIs that arrive in 3.14 (`Path.info`, `Path.copy`). They run
# only there, and the count is asserted so the exclusion cannot quietly widen.
LATER_ONLY_MARKERS = (".info", ".copy(")
EXPECTED_LATER_ONLY_BLOCKS = 2

# Documented but absent from the older interpreters. Each must carry a version
# marker in its own row; the coverage test checks that.
ADDED_LATER = {
    "walk": "3.12",
    "is_junction": "3.12",
    "with_segments": "3.12",
    "from_uri": "3.13",
    "full_match": "3.13",
    "parser": "3.13",
    "UnsupportedOperation": "3.13",
    "copy": "3.14",
    "copy_into": "3.14",
    "move": "3.14",
    "move_into": "3.14",
    "info": "3.14",
}
# Present on the older interpreters and gone from the newer ones.
REMOVED_LATER = {"link_to": "3.12"}
CLASSES = (
    "PurePath",
    "PurePosixPath",
    "PureWindowsPath",
    "Path",
    "PosixPath",
    "WindowsPath",
    "UnsupportedOperation",
)

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


def _documented_names() -> set[str]:
    """Every attribute the Complexity Reference tables name.

    Rows group families as `PurePath.name/stem/suffix`, so a slash-separated
    run after the class name names one attribute each. The bare class names
    are matched separately, since they appear without a dot.
    """
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("## Pure Paths Never Touch the Filesystem")
    names: set[str] = set()
    for line in text[start:end].splitlines():
        if not line.startswith("| `"):
            continue
        operation = line.split("|")[1]
        for group in re.findall(
            r"(?:PurePath|Path)?\.([A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*)",
            operation,
        ):
            names.update(group.split("/"))
        for klass in CLASSES:
            if f"`{klass}`" in operation:
                names.add(klass)
    return names


def _public_names() -> set[str]:
    """What this interpreter actually offers: the classes plus their surface."""
    names = set(pathlib.__all__)
    for klass in (pathlib.PurePath, pathlib.Path):
        names |= {name for name in dir(klass) if not name.startswith("_")}
    return names


class TestEveryPublicNameIsDocumented:
    """The tables have to name every public attribute pathlib offers.

    A page is lint-clean and green whether it covers its module or a quarter
    of it, and no reader of the page can tell the difference. `pathlib.__all__`
    plus the public surface of PurePath and Path is the set that has to be
    accounted for; `dir(pathlib)` is not, because the module leaks its imports.
    """

    def test_no_public_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(_public_names() - _documented_names())

        assert not missing, f"{len(missing)} public names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        allowed = set(ADDED_LATER) | set(REMOVED_LATER)
        unknown = sorted(_documented_names() - _public_names() - allowed)

        assert not unknown, f"the tables name attributes pathlib does not have: {unknown}"

    def test_every_version_gated_row_says_which_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("| `")
        ]

        for name, version in {**ADDED_LATER, **REMOVED_LATER}.items():
            owning = [row for row in rows if re.search(rf"\b{name}\b", row)]
            assert owning, f"no row names {name}"
            assert any(version in row for row in owning), (
                f"the {name} row should name {version}: {owning[0]}"
            )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()
        public = _public_names()

        assert len(documented) >= 70, f"the extractor found only {len(documented)} names"
        assert {"parts", "suffixes", "iterdir", "PurePosixPath", "relative_to"} <= documented
        assert public - (documented - {"iterdir"}) == {"iterdir"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestPurePathsDoNoIO:
    """The pure table's defining property, and the reason it is a table apart.

    Counted rather than argued: every operation below runs against a path that
    does not exist, under the same syscall counter the filesystem tests use.
    """

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

    def test_suffixes_costs_the_final_component(
        self,
    ) -> None:
        """`PurePath.suffixes` | O(m) | O(m) | m = length of the final component."""
        few = pathlib.PurePosixPath("/a/f.tar.gz")
        many = pathlib.PurePosixPath("/a/f" + ".x" * 200)

        assert len(few.suffixes) == 2
        assert len(many.suffixes) == 200

    def test_a_pure_path_never_grows_filesystem_methods(self) -> None:
        """PurePath is the smaller surface, which is what makes the split real."""
        pure_surface = {n for n in dir(pathlib.PurePath) if not n.startswith("_")}

        assert "exists" not in pure_surface
        assert "iterdir" not in pure_surface
        assert "exists" in {n for n in dir(pathlib.Path) if not n.startswith("_")}


class TestPartsIsRebuiltPerAccess:
    """`PurePath.parts` | O(n) | O(n), rebuilt on every access from 3.12.

    Identity settles this with no stopwatch: up to 3.11 the tuple is cached on
    the instance and the same object comes back, and from 3.12 a fresh one is
    built each time.
    """

    def test_whether_the_tuple_is_cached(self) -> None:
        path = pathlib.PurePosixPath("/a/b/c/d/e/f.txt")

        first, second = path.parts, path.parts

        assert first == second
        if CONSTRUCTION_IS_DEFERRED:
            assert first is not second, "3.12 rebuilds the tuple on every access"
        else:
            assert first is second, "before 3.12 the tuple is cached on the instance"

    def test_parents_is_lazy_and_listing_it_is_not(self) -> None:
        """`PurePath.parents` | O(1) | O(1), and `list(parents)` is O(n²)."""
        deep = pathlib.PurePosixPath("/" + "/".join(f"d{i}" for i in range(400)))
        # The first touch parses the path from 3.12; measure the steady state.
        _ = deep.parents
        _ = deep.parts

        lazy_peak = peak_bytes(lambda: deep.parents)
        listed_peak = peak_bytes(lambda: list(deep.parents))

        assert len(deep.parents) == 400
        assert lazy_peak < 2_000, f"parents should hold nothing: {lazy_peak} B"
        assert listed_peak > 100 * lazy_peak, (
            f"materialising n parents of up to n components each is quadratic: "
            f"{lazy_peak} B against {listed_peak} B"
        )


class TestRelativeToGrowth:
    """`PurePath.relative_to()` | O(n²) | O(n), and O(n) before 3.12.

    The search walks the parents of one path and tests each candidate against
    the parents of the other, so the work squares from 3.12. Both versions
    peak at the O(n) result they return, so elapsed time is what separates
    them.
    """

    @staticmethod
    def _relative_ns(components: int) -> float:
        path = pathlib.PurePosixPath("/" + "/".join(f"d{i}" for i in range(components)) + "/f.txt")
        base = pathlib.PurePosixPath("/d0")
        _ = path.parts
        best = None
        for _ in range(5):
            start = time.perf_counter_ns()
            path.relative_to(base)
            elapsed = time.perf_counter_ns() - start
            best = elapsed if best is None else min(best, elapsed)
        assert best is not None
        return float(best)

    def test_relative_to_returns_the_tail(self) -> None:
        path = pathlib.PurePosixPath("/a/b/c/f.txt")

        assert path.relative_to("/a") == pathlib.PurePosixPath("b/c/f.txt")
        assert path.is_relative_to("/a")
        assert not path.is_relative_to("/z")

    @pytest.mark.timing
    def test_the_growth_squares_from_312(self) -> None:
        """x8.2 to x9.1 for 4x the components from 3.12; x1.7 to x2.0 before it.

        Linear growth would be x4 at this step and a clean square x16, so both
        thresholds sit either side of the linear point - at 50 to 200
        components the quadratic term does not dominate and a linear
        implementation passes as quadratic.

        x8 rather than x16 because the quadratic term is still arriving. The
        measured exponent rises 1.21, 1.45, 1.63 and 1.81 across n = 100, 200,
        400, 800 and 1,600 on 3.14, converging on 2, which is what the row
        claims. Before 3.12 the same sweep stays between 0.3 and 0.9.
        """
        small, large = self._relative_ns(200), self._relative_ns(800)
        ratio = large / small

        if CONSTRUCTION_IS_DEFERRED:
            assert ratio > 6, (
                f"4x the components should cost well over the 4x a linear "
                f"scan would: {small:.0f} ns against {large:.0f} ns"
            )
        else:
            assert ratio < 4, (
                f"before 3.12 the cost stays under the 4x a linear scan "
                f"would cost, let alone the 16x a square would: "
                f"{small:.0f} ns against {large:.0f} ns"
            )


class TestPureRowsWithVersionMarkers:
    """The rows whose note names a version, checked on this interpreter."""

    def test_is_reserved_warns_from_313(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pathlib.PureWindowsPath("CON").is_reserved()

        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert bool(deprecated) is (sys.version_info >= (3, 13))

    def test_purepath_as_uri_is_deprecated_in_314(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pathlib.PurePosixPath("/a/b").as_uri()

        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert bool(deprecated) is (sys.version_info >= (3, 14))

    def test_path_as_uri_is_not(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            uri = pathlib.Path("/a/b").as_uri()

        assert uri == "file:///a/b"
        assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]

    def test_as_uri_needs_an_absolute_path(self) -> None:
        with pytest.raises(ValueError):
            pathlib.Path("relative/x").as_uri()

    @POSIX_ONLY
    def test_is_junction_is_false_on_posix(self, tmp_path: pathlib.Path) -> None:
        if not hasattr(pathlib.Path, "is_junction"):
            pytest.skip("Path.is_junction() is 3.12+")

        assert tmp_path.is_junction() is False  # type: ignore[attr-defined]


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Path.info is 3.14+")
class TestPathInfoCaches:
    """`Path.info` | O(1) | O(1), caching what it stats.

    Counted rather than timed: the value of the row is that repeated queries
    cost one syscall between them, where the equivalent Path predicates cost
    one each.
    """

    def test_many_queries_cost_one_stat(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")

        info = target.info  # type: ignore[attr-defined]
        with counting_syscalls() as counter:
            info.exists()
            info.is_file()
            info.is_dir()
            info.exists()
        cached_calls = counter.stat_family

        with counting_syscalls() as counter:
            target.exists()
            target.is_file()
            target.is_dir()
            target.exists()
        plain_calls = counter.stat_family

        assert cached_calls == 1, f"info should stat once, made {cached_calls}"
        assert plain_calls == 4, f"the predicates stat each time, made {plain_calls}"

    def test_the_attribute_itself_is_cached(self, tmp_path: pathlib.Path) -> None:
        assert tmp_path.info is tmp_path.info  # type: ignore[attr-defined]

    def test_the_cache_does_not_expire(self, tmp_path: pathlib.Path) -> None:
        """Which is why the page says to build a fresh Path where it matters."""
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        info = target.info  # type: ignore[attr-defined]
        assert info.exists()

        target.unlink()

        assert info.exists(), "the cached answer survives the file"
        assert not pathlib.Path(str(target)).info.exists(), "a fresh Path stats again"  # type: ignore[attr-defined]


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Path.copy() is 3.14+")
class TestCopyStreamsAndMoveRenames:
    """`Path.copy()` | O(b) | O(1) and `Path.move()` | O(1) on one filesystem."""

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

        assert large_peak < 1.5 * small_peak, (
            f"8x the file should not move a streaming copy: {small_peak} B against {large_peak} B"
        )

    def test_copy_and_move_move_the_bytes(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "report.txt"
        source.write_text("contents", encoding="utf-8")

        source.copy(tmp_path / "backup.txt")  # type: ignore[attr-defined]
        assert (tmp_path / "backup.txt").read_text(encoding="utf-8") == "contents"
        assert source.exists()

        source.move(tmp_path / "archive.txt")  # type: ignore[attr-defined]
        assert (tmp_path / "archive.txt").read_text(encoding="utf-8") == "contents"
        assert not source.exists()

    def test_copy_into_and_move_into_take_a_directory(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "f.txt"
        source.write_text("contents", encoding="utf-8")
        destination = tmp_path / "d"
        destination.mkdir()

        source.copy_into(destination)  # type: ignore[attr-defined]
        assert (destination / "f.txt").read_text(encoding="utf-8") == "contents"

        other = tmp_path / "e"
        other.mkdir()
        source.move_into(other)  # type: ignore[attr-defined]
        assert (other / "f.txt").exists()
        assert not source.exists()


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
    """`Path.iterdir()` | O(d) | O(d).

    It returns an iterator, but the directory is read in full before the first
    item appears: os.listdir up to 3.12, and list(os.scandir(...)) from 3.13.
    Both materialise every name, so the space bound is the listing's, not one
    entry's.
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
    """`Path.glob(pattern)` | O(n) | O(w), O(w + d) with `**` - n is entries
    scanned, not matched.

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

    def test_a_recursive_pattern_pays_the_depth_term(self, tmp_path: pathlib.Path) -> None:
        """The table's O(w + d) cell for `**` patterns, at a fixed breadth of one.

        rglob() is measured the same way in the class below; this pins that the
        spelling is what matters - a glob() call with `**` in the pattern pays
        the walk's depth term, not the flat O(w) of the non-recursive patterns
        above.
        """
        shallow = make_deep(tmp_path, 20)
        nested = make_deep(tmp_path, 640)
        drain(shallow.glob("**/*.txt"))
        drain(nested.glob("**/*.txt"))

        shallow_peak = peak_bytes(lambda: drain(shallow.glob("**/*.txt")))
        nested_peak = peak_bytes(lambda: drain(nested.glob("**/*.txt")))
        remove_deep(nested)

        assert nested_peak > 1.25 * shallow_peak, (
            f"32x the depth should cost more through glob('**') too, so O(w) "
            f"alone cannot be the bound: {shallow_peak} B against {nested_peak} B"
        )


class TestRglobSpaceNeedsBothTerms:
    """`Path.rglob(pattern)` | O(n) | O(w + d).

    Width behaves the same on every supported version. Depth does not: 32x the
    depth costs x171 on 3.10 and x2.1 on 3.14, and those are not the same
    term. Held at a fixed total path length, 640 nested directories cost 57x
    what 20 do on 3.10 and nothing measurable on 3.14, where the depth term is
    the length of the paths the walk carries rather than a queue behind them.
    O(w + d) bounds both; see the module docstring.
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
        """`rglob(pattern)` is `glob('**/' + pattern)`, as the page's row says."""
        root = tmp_path / "tree"
        root.mkdir()
        (root / "a").mkdir()
        (root / "a" / "x.py").touch()
        (root / "y.py").touch()

        assert sorted(root.rglob("*.py")) == sorted(root.glob("**/" + "*.py"))


@pytest.mark.skipif(sys.version_info < (3, 12), reason="Path.walk() is 3.12+")
class TestWalkSpaceNeedsBothTerms:
    """`Path.walk()` | O(n) | O(w + d), and 3.12+.

    It delegates to os.walk, so it carries the bound the os page already
    does: the queued entries are a term of their own, and 4x the siblings at
    a fixed depth costs about 4x.
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


def _needs_314(source: str) -> bool:
    """Blocks calling `Path.info` or `Path.copy`, which arrive in 3.14."""
    return any(marker in source for marker in LATER_ONLY_MARKERS)


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
    """Every block runs, in a directory of its own.

    Nothing is pre-classified by outcome, which is what gives the check teeth:
    any non-zero exit is a failure, so a NameError has nowhere to hide behind
    an allowance for missing paths. The only blocks held back are the two that
    call 3.14 APIs, and they are counted so the exclusion cannot widen.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        later = [line for line, source in blocks if _needs_314(source)]
        assert len(later) == EXPECTED_LATER_ONLY_BLOCKS, (
            f"expected {EXPECTED_LATER_ONLY_BLOCKS} blocks using 3.14 APIs, found {later}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            if _needs_314(source) and sys.version_info < (3, 14):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        expected = EXPECTED_BLOCKS
        if sys.version_info < (3, 14):
            expected -= EXPECTED_LATER_ONLY_BLOCKS
        assert ran == expected, f"ran {ran} blocks, expected {expected}"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("from pathlib import Path\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
