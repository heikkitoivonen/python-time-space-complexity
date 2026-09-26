"""Tests for docs/stdlib/filecmp.md.

The page prices a file comparison by what it reads and a directory comparison
by what it lists, stats and reads. Every claim here is settled by observation
rather than timing: `open` is replaced in the module with a wrapper that counts
the bytes each `read()` returns, and `os.stat` and `os.listdir` are wrapped to
count calls. A count separates "reads nothing" from "reads the file" with no
tolerance, and the directory bounds follow from which calls each attribute
makes.

Measurement scope:

* `cmp()` of a file and its `shutil.copy2` copy opens neither. `cmp()` on
  two 1 MB files: with equal signatures and `shallow=True`, and
  with sizes that differ in either mode, no file is opened and exactly two
  `os.stat` calls are made. With equal sizes and different mtimes,
  `shallow=True` opens both files and reads all 2 MB when they are
  identical. With `shallow=False`, a difference in the first byte reads under
  64 KB whichever of 1 MB and 10 MB the files are, and a difference in the
  last byte reads the whole of both files. A path that is a directory
  returns `False` without an open.
* The cache: a second deep `cmp()` of an unchanged pair opens nothing;
  after `clear_cache()`, or after one file's mtime changes, the pair is read
  again. A rewrite restored to its old size and mtime returns the cached
  result. Deep comparisons of 150 distinct pairs leave at most 101 cached
  results, and the first pair is read again afterwards.
* `cmpfiles()` makes one `cmp()` per name, lists no directory, and puts a
  missing name in the third list.
* `dircmp()` over paths that do not exist succeeds and makes no `os.listdir`
  or `os.stat` call. On a pair holding 40 files and 10 subdirectories per side:
  `left_only` makes two `os.listdir` calls and no `os.stat`; `common_dirs`
  then adds exactly two `os.stat` per common name; `same_files` then adds
  exactly two per common file, and every attribute is computed once. `subdirs`
  builds one object of the caller's class per common subdirectory and lists
  none of them.
* `report()` on a tree with common subdirectories makes two `os.listdir`
  calls; `report_partial_closure()` makes two per pair at the top two levels;
  `report_full_closure()` makes two per common directory pair and none for a
  directory present on one side only. A chain 40 levels deep and a root with
  40 subdirectories, each 41 pairs, both make 82 `os.listdir` calls, so the
  bound does not depend on the tree's shape. After the full closure every
  nested object still holds its listing.
* `dircmp(shallow=False)` on 3.13+ opens both files of a same-size,
  same-mtime pair and reports them different; the default opens neither and
  reports them the same. On 3.10-3.12 the keyword raises `TypeError`.
* An `ignore` list of 50 objects with a counting `__eq__`, over a directory of
  20 names per side, is compared 50 times per listed name; an ignored
  directory is never stat'ed, and passing `ignore` drops `DEFAULT_IGNORES`.
* `python -m filecmp` is run in a subprocess on a same-size, same-mtime pair
  whose contents differ, and reports it identical; `-r` reports a nested
  difference that the plain form does not.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(e log e) sort in the listing rows is read from Lib/filecmp.py
  (`list.sort()` after `os.listdir`); only call counts are measured, and
  entry-name length is not varied.
* Bytes are counted as `read()` returns them to `filecmp`, not as the
  buffered reader fetches them from the OS; the buffer adds at most its own
  size per file, a constant.
* Filesystems with coarse mtime resolution, network filesystems and case-
  insensitive filesystems (where `os.path.normcase` matters on Windows) are
  not exercised. File permissions are not varied, since the tests may run as
  root. Trees deeper than 40 levels are not built: the closures recurse once
  per level, so a common tree near the recursion limit is outside what is
  measured.
* `demo()` is the `python -m filecmp` entry point and is covered through it.
  `dircmp.phase0` to `phase4`, `phase4_closure` and `methodmap` are the
  undocumented machinery behind the lazy attributes and are not on the page.
"""

from __future__ import annotations

import contextlib
import filecmp
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "filecmp.md"
EXPECTED_BLOCKS = 8
MB = 1_000_000


class ReadCounter:
    """Replace `open` inside filecmp, counting opens and the bytes each read returns."""

    def __init__(self) -> None:
        self.opened = 0
        self.bytes_read = 0

    def __call__(self, path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        self.opened += 1
        handle = open(path, mode, *args, **kwargs)  # noqa: SIM115
        counter = self
        read = handle.read

        def counting_read(size: int = -1) -> bytes:
            data = read(size)
            counter.bytes_read += len(data)
            return data

        handle.read = counting_read
        return handle


class CallCounter:
    """Wrap a function and count its calls."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self.func(*args, **kwargs)


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> Iterator[ReadCounter]:
    counter = ReadCounter()
    monkeypatch.setattr(filecmp, "open", counter, raising=False)
    filecmp.clear_cache()
    yield counter
    filecmp.clear_cache()


@pytest.fixture
def stats(monkeypatch: pytest.MonkeyPatch) -> CallCounter:
    counter = CallCounter(os.stat)
    monkeypatch.setattr(os, "stat", counter)
    return counter


@pytest.fixture
def listings(monkeypatch: pytest.MonkeyPatch) -> CallCounter:
    counter = CallCounter(os.listdir)
    monkeypatch.setattr(os, "listdir", counter)
    return counter


def write(path: pathlib.Path, data: bytes, mtime: int | None = None) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class TestShallowTrustsTheSignature:
    """`cmp()` | O(n) | O(1), and O(1) with no read when the signatures decide.

    Shallow mode skips the read only when type, size and mtime all match; a
    size difference skips it in both modes; anything else reads."""

    def test_a_copy2_copy_is_not_read(self, tmp_path: pathlib.Path, reads: ReadCounter) -> None:
        a = write(tmp_path / "a", b"x" * MB, mtime=1_000)
        b = tmp_path / "b"
        shutil.copy2(a, b)

        assert filecmp.cmp(a, b) is True
        assert reads.opened == 0

    def test_equal_signatures_read_nothing(
        self, tmp_path: pathlib.Path, reads: ReadCounter, stats: CallCounter
    ) -> None:
        a = write(tmp_path / "a", b"x" * MB, mtime=1_000)
        b = write(tmp_path / "b", b"y" * MB, mtime=1_000)
        stats.calls = 0

        assert filecmp.cmp(a, b) is True
        assert (reads.opened, stats.calls) == (0, 2)

    @pytest.mark.parametrize("shallow", [True, False])
    def test_different_sizes_read_nothing(
        self, tmp_path: pathlib.Path, reads: ReadCounter, shallow: bool
    ) -> None:
        a = write(tmp_path / "a", b"x" * MB)
        b = write(tmp_path / "b", b"x" * (MB + 1))

        assert filecmp.cmp(a, b, shallow=shallow) is False
        assert reads.opened == 0

    def test_shallow_reads_when_only_the_mtime_differs(
        self, tmp_path: pathlib.Path, reads: ReadCounter
    ) -> None:
        a = write(tmp_path / "a", b"x" * MB, mtime=1_000)
        b = write(tmp_path / "b", b"x" * MB, mtime=2_000)

        assert filecmp.cmp(a, b) is True
        assert reads.opened == 2
        assert reads.bytes_read == 2 * MB

    def test_shallow_equal_signature_hides_different_contents(self, tmp_path: pathlib.Path) -> None:
        a = write(tmp_path / "a", b"hello", mtime=1_000)
        b = write(tmp_path / "b", b"HELLO", mtime=1_000)

        assert filecmp.cmp(a, b, shallow=True) is True
        assert filecmp.cmp(a, b, shallow=False) is False

    def test_a_directory_is_not_equal_and_is_not_opened(
        self, tmp_path: pathlib.Path, reads: ReadCounter
    ) -> None:
        (tmp_path / "d1").mkdir()
        (tmp_path / "d2").mkdir()

        assert filecmp.cmp(tmp_path / "d1", tmp_path / "d2") is False
        assert reads.opened == 0


class TestDeepComparisonStopsAtTheFirstDifference:
    """The read ends at the first block that differs, so the cost is the
    position of the difference, and the whole file when there is none."""

    @pytest.mark.parametrize("size", [MB, 10 * MB])
    def test_an_early_difference_reads_a_constant(
        self, tmp_path: pathlib.Path, reads: ReadCounter, size: int
    ) -> None:
        a = write(tmp_path / "a", b"\0" * size)
        b = write(tmp_path / "b", b"\1" + b"\0" * (size - 1))

        assert filecmp.cmp(a, b, shallow=False) is False
        assert reads.bytes_read < 64_000, f"read {reads.bytes_read} bytes of two {size}-byte files"

    def test_a_late_difference_reads_everything(
        self, tmp_path: pathlib.Path, reads: ReadCounter
    ) -> None:
        a = write(tmp_path / "a", b"\0" * MB)
        b = write(tmp_path / "b", b"\0" * (MB - 1) + b"\1")

        assert filecmp.cmp(a, b, shallow=False) is False
        assert reads.bytes_read == 2 * MB

    def test_identical_files_are_read_to_the_end(
        self, tmp_path: pathlib.Path, reads: ReadCounter
    ) -> None:
        a = write(tmp_path / "a", b"\0" * MB)
        b = write(tmp_path / "b", b"\0" * MB)

        assert filecmp.cmp(a, b, shallow=False) is True
        assert reads.bytes_read == 2 * MB


class TestTheCache:
    """A repeated `cmp()` of an unchanged pair is O(1); `clear_cache()` and a
    signature change force a read; the cache stays bounded."""

    def test_a_repeat_reads_nothing(self, tmp_path: pathlib.Path, reads: ReadCounter) -> None:
        a = write(tmp_path / "a", b"\0" * MB)
        b = write(tmp_path / "b", b"\0" * MB)
        filecmp.cmp(a, b, shallow=False)
        opened = reads.opened

        assert filecmp.cmp(a, b, shallow=False) is True
        assert reads.opened == opened

    def test_clear_cache_forces_a_read(self, tmp_path: pathlib.Path, reads: ReadCounter) -> None:
        a = write(tmp_path / "a", b"\0" * MB)
        b = write(tmp_path / "b", b"\0" * MB)
        filecmp.cmp(a, b, shallow=False)
        opened = reads.opened

        filecmp.clear_cache()
        filecmp.cmp(a, b, shallow=False)

        assert reads.opened == opened + 2

    def test_a_new_mtime_forces_a_read(self, tmp_path: pathlib.Path, reads: ReadCounter) -> None:
        a = write(tmp_path / "a", b"\0" * MB, mtime=1_000)
        b = write(tmp_path / "b", b"\0" * MB, mtime=1_000)
        filecmp.cmp(a, b, shallow=False)
        opened = reads.opened

        os.utime(b, (2_000, 2_000))
        filecmp.cmp(a, b, shallow=False)

        assert reads.opened == opened + 2

    def test_a_rewrite_with_the_same_signature_is_not_seen(
        self, tmp_path: pathlib.Path, reads: ReadCounter
    ) -> None:
        a = write(tmp_path / "a", b"\0" * 100, mtime=1_000)
        b = write(tmp_path / "b", b"\0" * 100, mtime=1_000)
        assert filecmp.cmp(a, b, shallow=False) is True

        write(b, b"\1" * 100, mtime=1_000)

        assert filecmp.cmp(a, b, shallow=False) is True
        filecmp.clear_cache()
        assert filecmp.cmp(a, b, shallow=False) is False

    def test_the_cache_stays_bounded(self, tmp_path: pathlib.Path, reads: ReadCounter) -> None:
        sizes = []
        for index in range(150):
            a = write(tmp_path / f"a{index}", b"z")
            b = write(tmp_path / f"b{index}", b"z")
            filecmp.cmp(a, b, shallow=False)
            # The cache is private; its size is the only direct evidence of the bound.
            sizes.append(len(filecmp._cache))  # type: ignore[attr-defined]  # noqa: SLF001

        assert reads.opened == 300, "every pair must miss the cache and be read"
        assert max(sizes) <= 101, f"the cache grew to {max(sizes)} entries"

        filecmp.cmp(tmp_path / "a0", tmp_path / "b0", shallow=False)
        assert reads.opened == 302, "the first pair survived the cache being emptied"


class TestCmpfilesIsCmpInALoop:
    """`cmpfiles(a, b, common)` | O(f + s) | O(f): one `cmp()` per name, no listing."""

    def test_one_cmp_per_name_and_no_listing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, listings: CallCounter
    ) -> None:
        names = [f"n{index}" for index in range(30)]
        for name in names:
            write(tmp_path / "l" / name, b"same")
            write(tmp_path / "r" / name, b"same")
        (tmp_path / "l" / "extra").write_bytes(b"not asked for")
        counted = CallCounter(filecmp.cmp)
        monkeypatch.setattr(filecmp, "cmp", counted)
        monkeypatch.setattr(filecmp, "_cmp", _cmp_through(counted))

        match, mismatch, errors = filecmp.cmpfiles(tmp_path / "l", tmp_path / "r", names)

        assert (match, mismatch, errors) == (names, [], [])
        assert counted.calls == len(names)
        assert listings.calls == 0

    def test_the_three_lists(self, tmp_path: pathlib.Path) -> None:
        write(tmp_path / "l" / "same", b"one")
        write(tmp_path / "r" / "same", b"one")
        write(tmp_path / "l" / "changed", b"old")
        write(tmp_path / "r" / "changed", b"newer")

        result = filecmp.cmpfiles(tmp_path / "l", tmp_path / "r", ["same", "changed", "missing"])

        assert result == (["same"], ["changed"], ["missing"])


def _cmp_through(counted: CallCounter) -> Callable[..., int]:
    """`filecmp._cmp` binds `cmp` as a default argument, so patching the module
    global alone would not reach it; rebuild it around the counter."""
    original = filecmp._cmp  # type: ignore[attr-defined]  # noqa: SLF001

    def patched(a: Any, b: Any, sh: bool) -> int:
        return original(a, b, sh, cmp=counted)

    return patched


def make_pair(root: pathlib.Path, files: int, dirs: int) -> tuple[str, str]:
    """Two directories with the same `files` files and `dirs` subdirectories."""
    for side in ("l", "r"):
        for index in range(files):
            write(root / side / f"f{index:03d}", b"data")
        for index in range(dirs):
            (root / side / f"d{index:03d}").mkdir(parents=True)
    return str(root / "l"), str(root / "r")


class TestDircmpIsLazy:
    """`dircmp()` | O(1): nothing is listed or stat'ed until an attribute is
    read, each attribute pays only for the phases it needs, and each is
    computed once."""

    def test_construction_touches_nothing(self, stats: CallCounter, listings: CallCounter) -> None:
        comparison = filecmp.dircmp("/no/such/left", "/no/such/right")

        assert comparison.left == "/no/such/left"
        assert comparison.right == "/no/such/right"
        assert (stats.calls, listings.calls) == (0, 0)
        with pytest.raises(FileNotFoundError):
            _ = comparison.left_list

    def test_left_only_lists_but_does_not_stat(
        self, tmp_path: pathlib.Path, stats: CallCounter, listings: CallCounter
    ) -> None:
        left, right = make_pair(tmp_path, files=40, dirs=10)
        write(pathlib.Path(left) / "only", b"x")
        stats.calls = 0

        comparison = filecmp.dircmp(left, right)

        assert comparison.left_only == ["only"]
        assert comparison.right_only == []
        assert len(comparison.common) == 50
        assert comparison.left_list == sorted(comparison.left_list)
        assert (listings.calls, stats.calls) == (2, 0)

    def test_the_split_stats_each_common_name_twice(
        self, tmp_path: pathlib.Path, stats: CallCounter, listings: CallCounter
    ) -> None:
        left, right = make_pair(tmp_path, files=40, dirs=10)
        comparison = filecmp.dircmp(left, right)
        _ = comparison.common
        stats.calls = 0

        assert len(comparison.common_dirs) == 10
        assert len(comparison.common_files) == 40
        assert comparison.common_funny == []
        assert stats.calls == 2 * 50

    def test_same_files_adds_one_cmp_per_common_file(
        self, tmp_path: pathlib.Path, stats: CallCounter, listings: CallCounter
    ) -> None:
        left, right = make_pair(tmp_path, files=40, dirs=10)
        comparison = filecmp.dircmp(left, right)
        _ = comparison.common_files
        stats.calls = 0

        assert len(comparison.same_files) + len(comparison.diff_files) == 40
        assert comparison.funny_files == []
        assert stats.calls == 2 * 40
        assert listings.calls == 2

    def test_every_attribute_is_computed_once(
        self, tmp_path: pathlib.Path, stats: CallCounter, listings: CallCounter
    ) -> None:
        left, right = make_pair(tmp_path, files=5, dirs=2)
        comparison = filecmp.dircmp(left, right)
        names = [
            "left_list", "right_list", "common", "left_only", "right_only",
            "common_dirs", "common_files", "common_funny",
            "same_files", "diff_files", "funny_files", "subdirs",
        ]  # fmt: skip
        first = {name: getattr(comparison, name) for name in names}
        counts = (stats.calls, listings.calls)

        for name in names:
            assert getattr(comparison, name) is first[name]
        assert (stats.calls, listings.calls) == counts

    def test_subdirs_builds_children_without_listing_them(
        self, tmp_path: pathlib.Path, listings: CallCounter
    ) -> None:
        class Mine(filecmp.dircmp):  # type: ignore[type-arg]
            pass

        left, right = make_pair(tmp_path, files=0, dirs=10)
        for index in range(10):
            write(pathlib.Path(left) / f"d{index:03d}" / "inner", b"x")

        subdirs = Mine(left, right).subdirs

        assert len(subdirs) == 10
        assert all(type(child) is Mine for child in subdirs.values())
        assert listings.calls == 2
        assert all("left_list" not in vars(child) for child in subdirs.values())


def make_tree(root: pathlib.Path, shape: str, size: int) -> tuple[str, str]:
    """A common tree of `size` + 1 directory pairs, as a chain or a fan."""
    for side in ("l", "r"):
        if shape == "deep":
            path = root / side
            for _ in range(size):
                path = path / "d"
            path.mkdir(parents=True)
        else:
            for index in range(size):
                (root / side / f"d{index:03d}").mkdir(parents=True)
    return str(root / "l"), str(root / "r")


def quietly(func: Callable[[], Any]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        func()
    return buffer.getvalue()


class TestReportsVisitTheLevelsTheyName:
    """`report()` is one pair, `report_partial_closure()` adds the immediate
    common subdirectories, `report_full_closure()` the common tree: O(t log t
    + s) over the pairs visited, independent of the tree's shape."""

    def test_report_lists_one_pair(self, tmp_path: pathlib.Path, listings: CallCounter) -> None:
        left, right = make_tree(tmp_path, "deep", 5)
        comparison = filecmp.dircmp(left, right)

        output = quietly(comparison.report)

        assert listings.calls == 2
        assert "Common subdirectories : ['d']" in output
        assert "subdirs" not in vars(comparison)

    def test_partial_closure_lists_two_levels(
        self, tmp_path: pathlib.Path, listings: CallCounter
    ) -> None:
        left, right = make_tree(tmp_path, "deep", 5)

        quietly(filecmp.dircmp(left, right).report_partial_closure)

        assert listings.calls == 2 * 2

    @pytest.mark.parametrize("shape", ["deep", "wide"])
    def test_full_closure_lists_every_common_pair_once(
        self, tmp_path: pathlib.Path, listings: CallCounter, shape: str
    ) -> None:
        left, right = make_tree(tmp_path, shape, 40)

        quietly(filecmp.dircmp(left, right).report_full_closure)

        assert listings.calls == 2 * 41

    def test_a_one_sided_directory_is_not_entered(
        self, tmp_path: pathlib.Path, listings: CallCounter
    ) -> None:
        left, right = make_tree(tmp_path, "wide", 3)
        (pathlib.Path(left) / "solo" / "deep" / "deeper").mkdir(parents=True)
        comparison = filecmp.dircmp(left, right)

        output = quietly(comparison.report_full_closure)

        assert listings.calls == 2 * 4
        assert "['solo']" in output

    def test_the_full_closure_keeps_every_level(self, tmp_path: pathlib.Path) -> None:
        left, right = make_tree(tmp_path, "deep", 10)
        comparison = filecmp.dircmp(left, right)

        quietly(comparison.report_full_closure)

        level = comparison
        for _ in range(10):
            assert "left_list" in vars(level)
            level = level.subdirs["d"]
        assert "left_list" in vars(level)

    def test_full_closure_finds_a_nested_difference(self, tmp_path: pathlib.Path) -> None:
        write(tmp_path / "l" / "a" / "b" / "f", b"left")
        write(tmp_path / "r" / "a" / "b" / "f", b"right!")
        comparison = filecmp.dircmp(str(tmp_path / "l"), str(tmp_path / "r"))

        assert "Differing files : ['f']" not in quietly(comparison.report)
        assert "Differing files : ['f']" in quietly(comparison.report_full_closure)


class TestDircmpShallow:
    """`dircmp(..., *, shallow=True)`: Python 3.13+. The default never reads
    a pair whose signatures match; `shallow=False` does."""

    @staticmethod
    def same_signature_pair(root: pathlib.Path) -> tuple[str, str]:
        write(root / "l" / "f", b"hello", mtime=1_000)
        write(root / "r" / "f", b"HELLO", mtime=1_000)
        return str(root / "l"), str(root / "r")

    def test_the_default_trusts_the_signature(
        self, tmp_path: pathlib.Path, reads: ReadCounter
    ) -> None:
        left, right = self.same_signature_pair(tmp_path)

        assert filecmp.dircmp(left, right).same_files == ["f"]
        assert reads.opened == 0

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="shallow was added in 3.13")
    def test_shallow_false_reads(self, tmp_path: pathlib.Path, reads: ReadCounter) -> None:
        left, right = self.same_signature_pair(tmp_path)

        comparison = filecmp.dircmp(left, right, shallow=False)  # type: ignore[call-arg]

        assert comparison.diff_files == ["f"]
        assert reads.opened == 2

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="shallow exists from 3.13")
    def test_shallow_is_rejected_before_313(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(TypeError):
            filecmp.dircmp(str(tmp_path), str(tmp_path), shallow=False)  # type: ignore[call-arg]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="shallow was added in 3.13")
    def test_shallow_is_keyword_only(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(TypeError):
            filecmp.dircmp(str(tmp_path), str(tmp_path), None, None, False)  # type: ignore[misc]


class TestIgnoreAndHide:
    """`ignore` and `hide` are lists scanned once per listed name, and an
    ignored name is never stat'ed or entered."""

    class Counting:
        comparisons = 0

        def __eq__(self, other: object) -> bool:
            TestIgnoreAndHide.Counting.comparisons += 1
            return False

        __hash__ = object.__hash__

    def test_each_listed_name_scans_the_ignore_list(self, tmp_path: pathlib.Path) -> None:
        left, right = make_pair(tmp_path, files=20, dirs=0)
        ignore = [self.Counting() for _ in range(50)]
        TestIgnoreAndHide.Counting.comparisons = 0

        _ = filecmp.dircmp(left, right, ignore=ignore).left_list  # type: ignore[arg-type]

        assert TestIgnoreAndHide.Counting.comparisons == 20 * 2 * 50

    def test_an_ignored_directory_is_never_stat_ed(
        self, tmp_path: pathlib.Path, stats: CallCounter, listings: CallCounter
    ) -> None:
        left, right = make_pair(tmp_path, files=0, dirs=1)
        for side in (left, right):
            (pathlib.Path(side) / "build" / "deep").mkdir(parents=True)
        stats.calls = 0

        comparison = filecmp.dircmp(left, right, ignore=["build"])
        quietly(comparison.report_full_closure)

        assert comparison.common_dirs == ["d000"]
        assert stats.calls == 2
        assert listings.calls == 2 * 2

    def test_default_ignores_is_the_list_used_when_ignore_is_omitted(
        self, tmp_path: pathlib.Path
    ) -> None:
        assert filecmp.dircmp(str(tmp_path), str(tmp_path)).ignore is filecmp.DEFAULT_IGNORES
        assert ".git" in filecmp.DEFAULT_IGNORES

    def test_passing_ignore_replaces_the_defaults(self, tmp_path: pathlib.Path) -> None:
        left, right = make_pair(tmp_path, files=0, dirs=0)
        for side in (left, right):
            (pathlib.Path(side) / ".git").mkdir(parents=True)
            (pathlib.Path(side) / "build").mkdir()

        assert filecmp.dircmp(left, right).common_dirs == ["build"]
        assert filecmp.dircmp(left, right, ignore=["build"]).common_dirs == [".git"]


class TestCommandLine:
    """`python -m filecmp [-r] dir1 dir2`: `report()`, or `report_full_closure()`
    with `-r`, always shallow."""

    @staticmethod
    def run(*args: str) -> str:
        result = subprocess.run(
            [sys.executable, "-m", "filecmp", *args],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        )
        return result.stdout

    def test_it_compares_shallowly(self, tmp_path: pathlib.Path) -> None:
        write(tmp_path / "l" / "f", b"hello", mtime=1_000)
        write(tmp_path / "r" / "f", b"HELLO", mtime=1_000)

        assert "Identical files : ['f']" in self.run(str(tmp_path / "l"), str(tmp_path / "r"))

    def test_r_recurses(self, tmp_path: pathlib.Path) -> None:
        write(tmp_path / "l" / "sub" / "f", b"left")
        write(tmp_path / "r" / "sub" / "f", b"right!")
        left, right = str(tmp_path / "l"), str(tmp_path / "r")

        assert "Differing files : ['f']" not in self.run(left, right)
        assert "Differing files : ['f']" in self.run("-r", left, right)


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
    """Each block runs in its own subprocess, so the comparison cache cannot
    leak between them, and asserts its own result."""

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
        target = "assert filecmp.cmp(a, b) is True"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert filecmp.cmp(a, b) is False", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
