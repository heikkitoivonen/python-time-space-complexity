"""Tests for docs/stdlib/ntpath.md.

`ntpath` is pure Python and imports everywhere, but on Windows it binds C
helpers from `nt` at import, so the page prices two implementations of
several functions. Both are tested on every platform that can reach them.
The Windows side runs against the real module; the other side runs against
`_fallback()`, Lib/ntpath.py executed afresh with an empty module standing
in for `nt`, so that every `from nt import ...` fails and every Python
fallback is bound - on Linux and macOS that is simply what `ntpath` is.
Nearly everything is settled by observation: identity, call counters on the
`nt` helpers `ntpath` looks up in its own globals and on the `os` functions
genericpath looks up at call time, and a str subclass that records what
`replace()` is called on. Timing tests settle the O(L) rows, `normpath()` in
both implementations and in the fallback functions that call it, the
`normpath()` that `realpath()` starts with, and `join()` of bytes.

Measurement scope:

* Which implementation runs where: the fallback's `normpath`, `abspath`,
  `realpath` and (3.12+) `splitroot` are its own Python functions, its
  `exists`, `isdir` and `isfile` are genericpath's, and it has no
  `_getvolumepathname` or `_getfinalpathname`. On Windows `ntpath.normpath`
  is `nt._path_normpath` from 3.12 (on 3.11 a wrapper that calls it once),
  `splitroot` is `nt._path_splitroot_ex` from 3.13, and the three
  `_get*pathname` names are nt's. Ten sample paths - drive, UNC, `\\\\?\\UNC`,
  `\\\\.\\` device, drive-relative, rooted, relative, empty and `..` forms -
  give equal results from both for `normpath`, `splitdrive`, `split`,
  `splitext`, `normcase`, `isabs`, `join` and (3.12+) `splitroot`.
* The split family, `join`, `commonprefix` and `commonpath` are asserted by
  their results, including a UNC share for `splitdrive`, a rooted argument
  keeping the drive and another drive discarding it for `join`, the first
  path's case kept by `commonpath` and a mid-component stop and a case
  mismatch for `commonprefix`. `basename` and `dirname` make one `split()`
  call each. The O(L) space is a result as long as its input for `split`,
  `normcase` and `join`.
* The O(L) and O(B) time rows: `split` (both implementations), `splitext`,
  `splitdrive`, `normcase`, `join` of L/10 one-character components and
  `commonpath` of two such paths are timed at L = 3,000, 30,000 and 300,000;
  each 10x step costs under 30x, where quadratic predicts 100x (x8.6 to
  x17 on 3.14; `splitdrive` x1.8 then x5.9 on 3.10, where fixed cost
  dominates). These are str arguments. `join` was measured separately up to
  64,000 characters: with components of 1,000 characters and totals past
  400,000 its string concatenation stops growing in place on Windows and
  the steps turn superlinear, for `posixpath.join` as much as for
  `ntpath.join`. Paths that long are past what Windows opens (32,767
  characters), and are not in the test.
* `join()` of bytes: 8,000, 32,000 and 128,000 one-character arguments
  cost over 8x on the second 4x step and over 48x across both (x8.3 to x11
  then x17 to x20 on 3.14, x6.0 to x6.8 then x12.6 to x14 on 3.10 under x64
  emulation), where str arguments at the same sizes cost under 8x per step
  (x2.3 to x4.7). Bytes
  has no in-place concatenation, so `result_path = result_path + p_path`
  copies the result so far per argument; the str form of that statement
  grows in place. Argument length was not varied. The other functions
  build a result by slicing, `str.join`, or one `join()` per step that
  their row already prices, not by repeated concatenation, which is read
  from Lib/ntpath.py.
* `isabs()` is given a 10,003-character str subclass recording the length
  of every string `replace()` is called on: from 3.11 nothing is recorded,
  because it slices three characters first, and on 3.10 the whole length
  is, in both implementations. `isabs(r"\\x")` is True before 3.13 and
  False from it.
* `normcase` lower-cases and turns `/` into `\\` in both implementations;
  `ntpath` holds `_LCMapStringEx` exactly on Windows, where `_winapi`
  supplies it (the fallback has it there too, since it does not come from
  `nt`). `isreserved()` (3.13+) is asserted on a device name, a trailing
  dot and a reserved character, with no `os` call. `expandvars()` expands
  all three forms and leaves an unknown name as it is; a 16-character
  argument expands to a 30,000-character result (Windows caps a variable at
  32,767). `expanduser()` splices in a 5,009-character `USERPROFILE`,
  guesses `~other` as its sibling, and uses `HOMEDRIVE` and `HOMEPATH`
  without `USERPROFILE`.
* `normpath()`: in timing tests, 16x the length of a path of `.`
  components (5,000 to 80,000) costs `nt._path_normpath` under 80x (x16 to
  x17 on 3.14, where quadratic predicts 256x). 32x the components (1,500 to
  48,000) costs the Python fallback over 100x, both for a run of `.`
  components (x377 on 3.10, x990 to x1040 on 3.13 and 3.14) and for n names
  followed by n `..` (x145 to x340), where linear predicts 32x. The fallback
  test runs on every platform. The C helper was timed on the `.` shape only.
* `abspath()` on Windows makes one `_getfullpathname()` call and no
  `os.getcwd()`, after `normpath()` from 3.11 and before it on 3.10, and
  returns the working directory joined to the argument. The fallback makes
  one `os.getcwd()` for a relative path and none for `C:\\...`, no stat or
  lstat, and one call to its Python `normpath()` each time. `relpath()`
  makes two `abspath()` calls in both implementations and raises
  ValueError naming the mounts for two drives.
* The callers of the Python `normpath()`: in the fallback, `abspath`,
  `relpath`, `realpath` (strict or not) and `ismount` each pass the whole
  argument, `C:\\a` and 50 `\\.` components, to `normpath()`, observed by a
  wrapper that records its arguments. In timing tests 16x the components
  (1,500 to 24,000) cost the fallback's `relpath`, `realpath` and `ismount`
  over 64x (x275 to x286 on 3.14, x87 to x103 on 3.10), where linear
  predicts 16x and quadratic 256x. On Windows
  `relpath()`, `realpath()` and `realpath(strict=True)` pass the raw
  argument to `normpath()` on every version, and it is Python on 3.10
  only. `ismount()` on Windows 3.10 hands `normpath()` only the result of
  `_getfullpathname()`, with no `.` components left, and from 3.11 the raw
  argument to the C helper, so its Windows row carries no quadratic case.
* `realpath()` on Windows is counted on a 1-level and a 20-level directory
  and through a chain of five junctions: two `_getfinalpathname()` calls
  each, no `readlink()` and no `os.lstat()`. With 1, 10 and 40 missing
  trailing components it makes one more `_getfinalpathname()` and one more
  `readlink()` per component. A junction to a target over 100 characters
  longer, plus one missing component, returns the target with the
  component joined on at the same calls as a one-component miss elsewhere:
  the F term of that row. A component it cannot open is walked the same
  way: a system file held with a sharing violation (the page file, where
  the machine has one, else the test skips) costs what a missing name at
  the drive root costs, and a stub that raises ERROR_ACCESS_DENIED for the
  bottom six levels of the 20-level tree costs what six missing components
  cost. The error codes that trigger the walk are read from
  `_getfinalpathname_nonstrict()` in Lib/ntpath.py; ERROR_ACCESS_DENIED and
  ERROR_SHARING_VIOLATION are among them on every supported version, and
  3.13 adds a `_findfirstfile()` call per such step, O(1) in the model.
* The W term: chains of 2 and 20 junctions ending at a missing directory,
  with head names, missing targets and so arguments and results of equal
  length, cost one `readlink()` per link plus one for the missing end (3
  and 21), at the same `_getfinalpathname()` count; two missing components
  below the head add one step each to both. A chain of junctions to a
  directory that exists opens in two calls at 40 links; at 80 it is more
  than Windows follows (on this machine 63 open and 64 fail with
  ERROR_CANT_RESOLVE_FILENAME on 3.14; 60 open and 70 fail on every
  supported version) and `realpath()` reads all 80 links and the
  directory. That the chain stops at a loop, and that each step's string
  work and the `seen` set are the length of the path reached, is read from
  `_readlink_deep()` in Lib/ntpath.py, the same on every supported version.
* `strict=True` makes the same two calls for an existing path and raises
  FileNotFoundError after one `_getfinalpathname()` and no `readlink()` for
  ten missing components. `strict=ALLOW_MISSING` walks those ten at exactly
  the non-strict calls, and raises PermissionError where the stub refuses
  access. `ALLOW_MISSING` is genericpath's object.
* `realpath()` starts with `normpath()` of the whole argument, on every
  version and with `strict=True` too; timed on a path of `.` components, 16x the components (3,000 to
  48,000) cost over 64x on 3.10 (x139 to x197 under x64 emulation) and
  under 80x from 3.11 (x2 to x3 on 3.11 and 3.14). The per-call string
  work, and so the L + C factor, is read from Lib/ntpath.py rather than
  measured. The fallback's `realpath()` is one `abspath()` call, strict or
  not, with no stat, lstat or readlink.
* `ismount()` on Windows makes one `_getfullpathname()` and one
  `_getvolumepathname()` call for a directory and no `realpath()` call,
  which is patched to raise, and no volume query for a drive root or a
  share root, on every supported version. The fallback answers True for
  `C:\\` and `\\\\server\\share`, False for a directory under either, with
  no stat, lstat or readlink.
* `isdevdrive()` (3.12+) on Windows makes one `abspath()` and one
  `_path_isdevdrive()` call on the absolute path, and returns False when
  the query raises OSError; the fallback returns False with no `os` call.
* Predicates: on Windows from 3.12 `exists`, `isfile`, `isdir` and
  `islink` (and from 3.13 `lexists` and `isjunction`) answer without any
  `os.stat()` or `os.lstat()` call; on 3.12 `isjunction` makes one
  `os.lstat()`. The fallback's `exists`, `isdir` and `isfile` make one
  `os.stat()` each and `islink` and `lexists` one `os.lstat()`; its
  `isjunction` returns False with no `os` call from 3.13, and on 3.12
  wherever `stat_result` has no `st_reparse_tag`. `getsize`, `getmtime`,
  `getatime` and `getctime` make one `os.stat()` each, `samefile` two,
  `sameopenfile` two `os.fstat()` and `samestat` none.
* The constants are asserted by value in both implementations, and
  `supports_unicode_filenames` against the version and platform.
* Every fenced block on the page runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail. The two blocks that resolve
  against a Windows filesystem (`realpath()` and `ismount()` of real paths)
  run only on Windows and are counted as skipped elsewhere.
* The tests were run on 3.10.21, 3.11.16, 3.12.14, 3.13.15 and 3.14.7 on
  Windows 11 ARM64 (3.10 under x64 emulation); their version guards are
  read from the diffs of Lib/ntpath.py and Lib/genericpath.py between those
  tags.

Not settled here:

* That a system call counts as O(1): the page follows the os page. How long
  the kernel takes to resolve a deep path in `_getfinalpathname()`, or a
  predicate's query, is outside that model.
* The O(L) bounds of the C helpers other than `_path_normpath`
  (`_path_splitroot_ex`, `_getfullpathname`, `_getvolumepathname`) are read
  from Modules/posixmodule.c; `splitdrive` timed on 3.13 and 3.14 exercises
  `_path_splitroot_ex` but only on a drive-letter path.
* On 3.10, a path `_getfullpathname()` rejects (longer than 32,767
  characters, or containing NUL) makes `abspath()`, and so `ismount()`,
  fall back to the Python `normpath()` over the joined path, with its
  quadratic case; the page does not price that failure path.
* The fallback run on Windows is the same code as `ntpath` on Linux and
  macOS, except where it looks outside `nt`: `normcase` uses `_winapi` when
  that imports, and on 3.12 `isjunction` lstats when `stat_result` has
  `st_reparse_tag`. A Linux run of this file exercises the real module
  there; the Windows-only tests skip, so a Linux or macOS run verifies none
  of the Windows rows (the `realpath()`, `abspath()`, `ismount()` and
  `isdevdrive()` counts, the `normpath()` C timing, the predicates' C
  helpers) and the two Windows blocks.
* Bytes paths are varied only for `join()`; every other measurement uses
  str.
"""

from __future__ import annotations

import functools
import genericpath
import importlib
import importlib.util
import ntpath
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import types
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ntpath.md"
EXPECTED_BLOCKS = 5

WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="the nt helpers exist only on Windows")
nt: Any = importlib.import_module("nt") if sys.platform == "win32" else None

# The two blocks that resolve paths against a Windows filesystem. Off Windows
# `realpath()` resolves nothing and `ismount()` is lexical, so they would
# assert Windows answers the fallback does not give.
WINDOWS_BLOCKS = ("ntpath.realpath(deep)", "ntpath.ismount(absolute[:3])")


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


class Counter:
    """Wraps a callable and counts the calls that reach it."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.calls = 0
        self.first: tuple[Any, ...] | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        if self.first is None:
            self.first = args
        return self.func(*args, **kwargs)


@functools.cache
def _fallback() -> Any:
    """Lib/ntpath.py executed afresh with an empty `nt` module in place.

    Every `from nt import ...` then fails, so every Python fallback is bound:
    this is the module `ntpath` is on Linux and macOS, loaded on any platform.
    """
    saved = sys.modules.get("nt")
    sys.modules["nt"] = types.ModuleType("nt")
    try:
        spec = importlib.util.spec_from_file_location("ntpath_fallback", ntpath.__file__)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            del sys.modules["nt"]
        else:
            sys.modules["nt"] = saved
    return module


@pytest.fixture
def fallback() -> Any:
    return _fallback()


def _count_os(monkeypatch: pytest.MonkeyPatch, *names: str) -> dict[str, Counter]:
    """Count calls to the named `os` functions for the rest of the test.

    genericpath and ntpath look each one up on `os` when they call it.
    """
    counters = {name: Counter(getattr(os, name)) for name in names}
    for name, counter in counters.items():
        monkeypatch.setattr(os, name, counter)
    return counters


FILESYSTEM = ("stat", "lstat", "fstat", "readlink", "getcwd")


def _dotted(components: int) -> str:
    return "a" + "\\." * components


class TestWhereEachImplementationRuns:
    """On Windows `ntpath` binds C helpers from `nt`; elsewhere, and before
    the helper existed, the Python fallback runs."""

    def test_the_fallback_binds_python_everywhere_it_could_differ(self, fallback: Any) -> None:
        assert fallback.normpath.__module__ == "ntpath_fallback"
        assert fallback.abspath.__module__ == "ntpath_fallback"
        assert fallback.realpath.__module__ == "ntpath_fallback"
        assert fallback._getvolumepathname is None
        assert not hasattr(fallback, "_getfinalpathname")
        if sys.version_info >= (3, 12):
            assert fallback.splitroot.__module__ == "ntpath_fallback"
        for name in ("exists", "isdir", "isfile"):
            assert getattr(fallback, name) is getattr(genericpath, name), name

    @WINDOWS
    def test_on_windows_the_helpers_are_bound(self) -> None:
        assert (ntpath.normpath is getattr(nt, "_path_normpath", None)) == (
            sys.version_info >= (3, 12)
        )
        splitroot = getattr(ntpath, "splitroot", None)
        assert (splitroot is getattr(nt, "_path_splitroot_ex", False)) == (
            sys.version_info >= (3, 13)
        )
        assert getattr(ntpath, "_getfullpathname") is nt._getfullpathname  # noqa: B009
        assert getattr(ntpath, "_getfinalpathname") is nt._getfinalpathname  # noqa: B009
        assert getattr(ntpath, "_getvolumepathname") is nt._getvolumepathname  # noqa: B009

    SAMPLES = (
        r"C:\Users\me\file.txt",
        "C:/a/./b/../c//d/",
        r"\\server\share\dir\x.tar.gz",
        r"\\?\UNC\server\share\x",
        r"\\.\device\x",
        r"D:rel\..\..\x",
        r"\rooted\.\x",
        "relative/./path/../x",
        "",
        "..\\..",
    )

    @pytest.mark.parametrize("path", SAMPLES)
    def test_the_string_functions_agree(self, fallback: Any, path: str) -> None:
        """The same answers from either implementation, so the page prices
        one function with two implementations rather than two functions."""
        names = ["normpath", "splitdrive", "split", "splitext", "normcase", "isabs"]
        if sys.version_info >= (3, 12):
            names.append("splitroot")
        for name in names:
            ours, theirs = getattr(ntpath, name)(path), getattr(fallback, name)(path)
            assert ours == theirs, (name, path, ours, theirs)
        assert ntpath.join(path, "x") == fallback.join(path, "x")


class TestSplittingAndJoining:
    """The split family, `join()`, `commonprefix()` and `commonpath()` -
    O(L) or O(B), and what each returns."""

    def test_splitdrive_takes_a_drive_or_a_share(self) -> None:
        assert ntpath.splitdrive(r"C:\x\y") == ("C:", r"\x\y")
        assert ntpath.splitdrive(r"\\server\share\x") == (r"\\server\share", r"\x")
        assert ntpath.splitdrive(r"x\y") == ("", r"x\y")

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="splitroot is 3.12+")
    def test_splitroot_returns_three_parts(self) -> None:
        splitroot = getattr(ntpath, "splitroot")  # noqa: B009 - typeshed 3.12+
        assert splitroot(r"C:\x") == ("C:", "\\", "x")
        assert splitroot(r"\\server\share\x") == (r"\\server\share", "\\", "x")
        assert splitroot("C:x") == ("C:", "", "x")

    def test_split_basename_and_dirname(self) -> None:
        path = r"C:\dir\sub\file.txt"
        assert ntpath.split(path) == (r"C:\dir\sub", "file.txt")
        assert ntpath.basename(path) == "file.txt"
        assert ntpath.dirname(path) == r"C:\dir\sub"
        assert ntpath.splitext(path) == (r"C:\dir\sub\file", ".txt")

    def test_basename_and_dirname_are_one_split_each(self, monkeypatch: pytest.MonkeyPatch) -> None:
        counter = Counter(ntpath.split)
        monkeypatch.setattr(ntpath, "split", counter)
        ntpath.basename(r"C:\a\b")
        ntpath.dirname(r"C:\a\b")
        assert counter.calls == 2

    def test_join_discards_what_another_drive_or_a_root_replaces(self) -> None:
        assert ntpath.join(r"C:\a", "b", "c") == r"C:\a\b\c"
        assert ntpath.join(r"C:\a", r"D:\b") == r"D:\b"
        assert ntpath.join(r"C:\a", "D:b") == "D:b"
        assert ntpath.join(r"C:\a", r"\b") == r"C:\b"  # the root keeps the drive

    def test_results_are_as_long_as_their_input(self) -> None:
        """The O(L) space rows: a result carries the input's characters."""
        long = "C:\\" + "a" * 100_000
        head, tail = ntpath.split(long)
        assert len(head) + len(tail) == len(long)  # the root stays with the head
        assert len(ntpath.normcase(long)) == len(long)
        assert len(ntpath.join(long, long[3:])) == 2 * len(long) - 2

    def test_commonprefix_is_by_character_and_commonpath_by_component(self) -> None:
        paths = [r"C:\Proj\src\a.py", r"c:\proj\SRC\b.py", r"C:\Proj\tests\t.py"]
        assert ntpath.commonpath(paths) == r"C:\Proj"
        assert ntpath.commonprefix(paths) == ""
        assert ntpath.commonprefix([r"C:\Proj\lib", r"C:\Proj\libexec"]) == r"C:\Proj\lib"
        assert ntpath.commonpath([r"C:\Proj\lib", r"C:\Proj\libexec"]) == r"C:\Proj"


class TestNormalisingAndInspecting:
    """`normcase()`, `isreserved()`, `expandvars()`, `expanduser()` and the
    V and H terms."""

    def test_normcase_lowercases_and_turns_slashes(self, fallback: Any) -> None:
        assert ntpath.normcase("C:/Users/ME") == r"c:\users\me"
        # _winapi is what supplies LCMapStringEx, so the fallback has it on
        # Windows too; off Windows both use str.lower().
        assert hasattr(ntpath, "_LCMapStringEx") == (sys.platform == "win32")
        assert fallback.normcase("C:/Users/ME") == r"c:\users\me"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="isreserved is 3.13+")
    def test_isreserved_checks_every_component(self, monkeypatch: pytest.MonkeyPatch) -> None:
        isreserved = getattr(ntpath, "isreserved")  # noqa: B009 - typeshed 3.13+
        counters = _count_os(monkeypatch, *FILESYSTEM)
        assert isreserved(r"C:\NUL\x") and isreserved(r"C:\a\b.") and isreserved("a\\b<c")
        assert not isreserved(r"C:\a\b\c.txt")
        assert all(counter.calls == 0 for counter in counters.values())

    def test_expandvars_expands_three_forms_and_leaves_unknown_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NTPATH_PAGE_V", "value")
        monkeypatch.delenv("NTPATH_PAGE_UNSET", raising=False)
        assert ntpath.expandvars("%NTPATH_PAGE_V%|$NTPATH_PAGE_V|${NTPATH_PAGE_V}") == (
            "value|value|value"
        )
        assert ntpath.expandvars("%NTPATH_PAGE_UNSET%") == "%NTPATH_PAGE_UNSET%"

    def test_expandvars_output_follows_the_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The V term: a 16-character argument, a 30,000-character result."""
        monkeypatch.setenv("NTPATH_PAGE_V", "z" * 30_000)
        assert len(ntpath.expandvars("%NTPATH_PAGE_V%")) == 30_000

    def test_expanduser_splices_in_the_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The H term, and `~user` guessed as a sibling with no account lookup."""
        home = "C:\\Users\\" + "u" * 5_000
        monkeypatch.setenv("USERPROFILE", home)
        monkeypatch.setenv("USERNAME", "u" * 5_000)
        assert ntpath.expanduser(r"~\x") == home + r"\x"
        assert ntpath.expanduser(r"~other\x") == r"C:\Users\other\x"

        monkeypatch.delenv("USERPROFILE")
        monkeypatch.setenv("HOMEDRIVE", "D:")
        monkeypatch.setenv("HOMEPATH", r"\home")
        assert ntpath.expanduser("~") == r"D:\home"


class _Probe(str):
    """A str that records the length of every string `replace()` is called on."""

    replaced: list[int] = []

    def replace(self, *args: Any, **kwargs: Any) -> str:
        _Probe.replaced.append(len(self))
        return str.replace(self, *args, **kwargs)


class TestIsabsReadsThePrefix:
    """`ntpath.isabs(path)` | O(1) from 3.11, O(L) on 3.10."""

    def test_only_3_10_rewrites_the_whole_path(self, fallback: Any) -> None:
        probe = _Probe("C:\\" + "a" * 10_000)
        for module in (ntpath, fallback):
            _Probe.replaced.clear()
            assert module.isabs(probe)
            if sys.version_info >= (3, 11):
                # Slicing a str subclass gives a plain str, so replace() on
                # the three-character prefix never reaches the probe.
                assert _Probe.replaced == []
            else:
                assert len(probe) in _Probe.replaced

    def test_a_rooted_path_without_a_drive_is_absolute_before_3_13(self) -> None:
        assert ntpath.isabs(r"\x") == (sys.version_info < (3, 13))
        assert ntpath.isabs(r"\\server\share\x")
        assert ntpath.isabs(r"C:\x") and not ntpath.isabs("C:x") and not ntpath.isabs("x")


class TestStringFunctionsAreLinear:
    """The O(L) and O(B) rows, timed: each 10x step in the input costs under
    30x, where linear predicts 10x and quadratic 100x.

    The largest input is 100,000 characters. Several of these functions copy
    the whole path, and a copy past glibc's 128 KiB mmap threshold is served
    fresh, zero-filled pages on every call, which adds page faults that are
    not the function's work: 300,000 characters measured x53 on the second
    step on 3.12."""

    @staticmethod
    def cases() -> dict[str, Callable[[int], Callable[[], Any]]]:
        def chars(func: Callable[[str], Any]) -> Callable[[int], Callable[[], Any]]:
            return lambda n: functools.partial(func, "C:\\d\\" + "a" * n)

        def parts(n: int) -> list[str]:
            return ["b"] * (n // 10)

        return {
            "split": chars(ntpath.split),
            "fallback split": chars(_fallback().split),
            "splitext": chars(ntpath.splitext),
            "splitdrive": chars(ntpath.splitdrive),
            "normcase": chars(ntpath.normcase),
            "join": lambda n: functools.partial(ntpath.join, "C:\\", *parts(n)),
            "commonpath": lambda n: functools.partial(
                ntpath.commonpath, ["C:\\" + "\\".join(parts(n)), "C:\\" + "\\".join(parts(n))]
            ),
        }

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "name",
        ["split", "fallback split", "splitext", "splitdrive", "normcase", "join", "commonpath"],
    )
    def test_ten_times_the_input_costs_about_ten_times(self, name: str) -> None:
        make = self.cases()[name]
        durations = [best_ns(make(size), repeats=5) for size in (1_000, 10_000, 100_000)]
        ratios = [durations[1] / durations[0], durations[2] / durations[1]]

        assert all(ratio < 30 for ratio in ratios), f"{name}: {durations} ns, x{ratios}"


FALLBACK_SHAPES = {
    "dots": _dotted,
    "pairs": lambda n: "a\\" * n + "..\\" * n,
}


class TestNormpath:
    """`ntpath.normpath(path)` | O(L) through `nt._path_normpath()` from 3.11;
    O(L²) as the Python fallback for a path of many `.` or `..` components."""

    @WINDOWS
    def test_it_is_the_c_helper_from_3_11(self, monkeypatch: pytest.MonkeyPatch) -> None:
        if sys.version_info >= (3, 12):
            assert ntpath.normpath is nt._path_normpath
        elif sys.version_info >= (3, 11):
            counter = Counter(nt._path_normpath)
            monkeypatch.setattr(ntpath, "_path_normpath", counter)
            assert ntpath.normpath("a/./b") == "a\\b"
            assert counter.calls == 1
        else:
            assert not hasattr(nt, "_path_normpath")
            assert ntpath.normpath.__module__ == "ntpath"

    @WINDOWS
    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="nt._path_normpath is 3.11+")
    def test_the_c_helper_is_linear(self) -> None:
        small_path, large_path = _dotted(5_000), _dotted(80_000)
        small = best_ns(lambda: nt._path_normpath(small_path), inner=20)
        large = best_ns(lambda: nt._path_normpath(large_path), inner=5)

        assert nt._path_normpath(large_path) == "a"
        assert large / small < 80, f"16x the path cost x{large / small:.1f}"

    @pytest.mark.parametrize("shape", sorted(FALLBACK_SHAPES))
    def test_the_fallback_removes_every_component(self, fallback: Any, shape: str) -> None:
        path = FALLBACK_SHAPES[shape](1_000)
        assert fallback.normpath(path) == {"dots": "a", "pairs": "."}[shape]
        assert fallback.normpath(path) == ntpath.normpath(path)

    @pytest.mark.timing
    @pytest.mark.parametrize("shape", sorted(FALLBACK_SHAPES))
    def test_the_python_fallback_is_quadratic(self, fallback: Any, shape: str) -> None:
        """32x the components: linear predicts 32x, quadratic 1,024x."""
        small_path, large_path = FALLBACK_SHAPES[shape](1_500), FALLBACK_SHAPES[shape](48_000)
        small = best_ns(lambda: fallback.normpath(small_path), repeats=7)
        large = best_ns(lambda: fallback.normpath(large_path), repeats=3)

        assert large / small > 100, f"{shape}: 32x the components cost x{large / small:.1f}"


class _Recorder:
    """Wraps `normpath` and records every argument it is given."""

    def __init__(self, func: Callable[[Any], Any]) -> None:
        self.func = func
        self.seen: list[Any] = []

    def __call__(self, path: Any) -> Any:
        self.seen.append(path)
        return self.func(path)


class TestNormpathCallers:
    """The rows that inherit `normpath()`'s quadratic case where it is
    Python: each passes its whole argument to `normpath()`, so it costs at
    least what `normpath()` does on it."""

    CALLERS: dict[str, Callable[[Any, str], Any]] = {
        "abspath": lambda module, path: module.abspath(path),
        "relpath": lambda module, path: module.relpath(path, "C:\\b"),
        "realpath": lambda module, path: module.realpath(path),
        "realpath strict": lambda module, path: module.realpath(path, strict=True),
        "ismount": lambda module, path: module.ismount(path),
    }

    @pytest.mark.parametrize("name", sorted(CALLERS))
    def test_the_fallback_callers_normalise_the_whole_argument(
        self, fallback: Any, monkeypatch: pytest.MonkeyPatch, name: str
    ) -> None:
        recorder = _Recorder(fallback.normpath)
        monkeypatch.setattr(fallback, "normpath", recorder)
        path = "C:\\a" + "\\." * 50

        result = self.CALLERS[name](fallback, path)

        assert path in recorder.seen, recorder.seen
        if name == "relpath":
            assert "C:\\b" in recorder.seen, recorder.seen  # `start` too
        assert result == {"relpath": r"..\a", "ismount": False}.get(name, "C:\\a")

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["relpath", "realpath", "ismount"])
    def test_the_fallback_callers_are_quadratic(self, fallback: Any, name: str) -> None:
        """16x the `.` components: linear predicts 16x, quadratic 256x."""
        call = self.CALLERS[name]
        small_path, large_path = "C:\\a" + "\\." * 1_500, "C:\\a" + "\\." * 24_000
        small = best_ns(lambda: call(fallback, small_path), repeats=7)
        large = best_ns(lambda: call(fallback, large_path), repeats=3)

        assert large / small > 64, f"{name}: 16x the components cost x{large / small:.1f}"

    @WINDOWS
    def test_on_windows_relpath_and_realpath_normalise_the_argument(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every version passes the raw argument to `normpath()`, which is
        the Python loop on 3.10 and C from 3.11 (TestNormpath)."""
        realpath: Any = ntpath.realpath  # typeshed lacks strict= on this platform
        root = realpath(tmp_path)
        path = root + "\\." * 50
        recorder = _Recorder(ntpath.normpath)
        monkeypatch.setattr(ntpath, "normpath", recorder)

        for call in (
            lambda: ntpath.relpath(path, root),
            lambda: realpath(path),
            lambda: realpath(path, strict=True),
        ):
            recorder.seen.clear()
            call()
            assert path in recorder.seen, recorder.seen
        recorder.seen.clear()
        ntpath.relpath(root, path)
        assert path in recorder.seen, "relpath() normalises `start` as well"

    @WINDOWS
    def test_on_windows_ismount_never_gives_the_python_loop_the_dots(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On 3.10 `abspath()`, and so `ismount()`, calls `_getfullpathname()`
        first and hands `normpath()` its already normalised result; from 3.11
        the raw argument goes to the C `normpath()`. Either way the quadratic
        loop never sees the `.` components."""
        recorder = _Recorder(ntpath.normpath)
        monkeypatch.setattr(ntpath, "normpath", recorder)
        path = str(tmp_path) + "\\." * 50

        assert ntpath.ismount(path) is False
        assert recorder.seen, "ismount() did not reach normpath()"
        if sys.version_info < (3, 11):
            # The 100 characters of `\.` are gone before normpath() runs.
            assert all(len(seen) == len(str(tmp_path)) for seen in recorder.seen), recorder.seen
        else:
            assert recorder.seen[0] == path


class TestJoiningBytes:
    """`ntpath.join(path, *paths)` | O(L) for str, O(n·L) for bytes: `str`
    concatenation to a local grows in place, `bytes` copies the result so
    far for every argument."""

    def test_bytes_join_like_str(self) -> None:
        assert ntpath.join(b"C:\\", b"a", b"b") == b"C:\\a\\b"
        assert ntpath.join(b"C:\\a", b"D:\\b") == b"D:\\b"

    @pytest.mark.timing
    def test_bytes_arguments_cost_quadratically_in_their_number(self) -> None:
        """8,000, 32,000 and 128,000 one-character arguments: each 4x step
        predicts 4x if linear and 16x if quadratic."""

        def steps(root: Any, part: Any) -> list[float]:
            durations = [
                best_ns(functools.partial(ntpath.join, root, *([part] * n)), repeats=3)
                for n in (8_000, 32_000, 128_000)
            ]
            return [durations[1] / durations[0], durations[2] / durations[1]]

        as_str, as_bytes = steps("C:\\", "a"), steps(b"C:\\", b"a")

        assert all(step < 8 for step in as_str), f"str: x{as_str}"
        assert as_bytes[1] > 8, f"bytes: x{as_bytes}"
        assert as_bytes[0] * as_bytes[1] > 48, f"bytes: x{as_bytes}"


class TestAbspath:
    """`ntpath.abspath(path)` | O(L + C): one `nt._getfullpathname()` on
    Windows, one `os.getcwd()` for a relative path elsewhere."""

    @WINDOWS
    def test_on_windows_it_is_one_full_path_call(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        order: list[str] = []
        full = Counter(getattr(ntpath, "_getfullpathname"))  # noqa: B009 - not in typeshed
        norm = Counter(ntpath.normpath)

        def recording_full(path: Any) -> Any:
            order.append("getfullpathname")
            return full(path)

        def recording_norm(path: Any) -> Any:
            order.append("normpath")
            return norm(path)

        monkeypatch.setattr(ntpath, "_getfullpathname", recording_full)
        monkeypatch.setattr(ntpath, "normpath", recording_norm)
        counters = _count_os(monkeypatch, "getcwd")

        result = ntpath.abspath("file.txt")

        assert result == ntpath.join(str(tmp_path), "file.txt")
        assert full.calls == 1 and counters["getcwd"].calls == 0
        if sys.version_info >= (3, 11):
            assert order == ["normpath", "getfullpathname"]
        else:
            assert order == ["getfullpathname", "normpath"]

    def test_elsewhere_it_joins_the_working_directory(
        self, fallback: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        norm = Counter(fallback.normpath)
        monkeypatch.setattr(fallback, "normpath", norm)
        counters = _count_os(monkeypatch, "getcwd", "stat", "lstat")

        relative = fallback.abspath(r"a\.\file.txt")
        after_relative = counters["getcwd"].calls
        absolute = fallback.abspath(r"C:\x\..\y")

        assert relative == norm.func(fallback.join(os.getcwd(), r"a\file.txt"))
        assert absolute == r"C:\y"
        assert after_relative == 1 and counters["getcwd"].calls == 2  # the check above adds one
        assert counters["stat"].calls == counters["lstat"].calls == 0
        assert norm.calls == 2  # the Python normpath(), once per call

    def test_relpath_takes_an_abspath_of_each(
        self, fallback: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for module in (ntpath, fallback):
            counter = Counter(module.abspath)
            monkeypatch.setattr(module, "abspath", counter)
            assert module.relpath(r"C:\Proj\src\a.py", r"C:\Proj\tests") == r"..\src\a.py"
            assert counter.calls == 2
            with pytest.raises(ValueError, match="mount"):
                module.relpath(r"D:\data", r"C:\Proj")


@pytest.fixture
def tree(tmp_path: pathlib.Path) -> Iterator[dict[str, str]]:
    """A 1-level and a 20-level directory, and five junctions chained to the
    deep one."""
    root = ntpath.realpath(tmp_path)
    shallow = ntpath.join(root, "s")
    deep = ntpath.join(root, *["d"] * 20)
    os.mkdir(shallow)
    os.makedirs(deep)
    winapi: Any = importlib.import_module("_winapi")
    target = deep
    for index in range(5):
        junction = ntpath.join(root, f"j{index}")
        winapi.CreateJunction(target, junction)
        target = junction
    yield {"shallow": shallow, "deep": deep, "junctions": target}
    for index in reversed(range(5)):
        os.rmdir(ntpath.join(root, f"j{index}"))  # removes the junction, not its target


def _junction_chain(root: str, prefix: str, links: int, end: str, *, dangling: bool) -> list[str]:
    """`links` junctions in a chain to `end`, in the order made: the first
    points at `end`, the last is the head of the chain. `end` is created if
    missing, since CreateJunction needs its target to exist, and removed
    again when `dangling`."""
    winapi: Any = importlib.import_module("_winapi")
    if not os.path.isdir(end):
        os.mkdir(end)
    made: list[str] = []
    try:
        target = end
        for index in range(links):
            junction = ntpath.join(root, f"{prefix}{index:02d}")
            winapi.CreateJunction(target, junction)
            made.append(junction)
            target = junction
    except BaseException:
        for junction in reversed(made):
            os.rmdir(junction)
        raise
    finally:
        if dangling:
            os.rmdir(end)
    return made


@WINDOWS
class TestRealpath:
    """`ntpath.realpath(path)` on Windows - two calls for a path that
    exists, then one more per missing trailing component, and one
    `readlink()` per link in a chain Windows will not resolve."""

    def _counted(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Counter]:
        counters = {
            "final": Counter(getattr(ntpath, "_getfinalpathname")),  # noqa: B009 - not in typeshed
            "readlink": Counter(getattr(ntpath, "_nt_readlink")),  # noqa: B009 - not in typeshed
            "lstat": Counter(os.lstat),
        }
        monkeypatch.setattr(ntpath, "_getfinalpathname", counters["final"])
        monkeypatch.setattr(ntpath, "_nt_readlink", counters["readlink"])
        monkeypatch.setattr(os, "lstat", counters["lstat"])
        return counters

    def _calls(
        self, monkeypatch: pytest.MonkeyPatch, path: str, **kwargs: Any
    ) -> tuple[Any, dict[str, int]]:
        """The result, or the exception raised, and the calls it took."""
        with monkeypatch.context() as patch:
            counters = self._counted(patch)
            try:
                result: Any = ntpath.realpath(path, **kwargs)
            except OSError as error:
                result = error
        return result, {name: counter.calls for name, counter in counters.items()}

    def test_an_existing_path_is_two_calls_at_any_depth(
        self, tree: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in ("shallow", "deep", "junctions"):
            result, calls = self._calls(monkeypatch, tree[name])

            assert calls == {"final": 2, "readlink": 0, "lstat": 0}, (name, calls)
            expected = tree["deep"] if name == "junctions" else tree[name]
            assert ntpath.normcase(result) == ntpath.normcase(expected)

    def test_each_missing_component_costs_a_call(
        self, tree: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counts: dict[int, dict[str, int]] = {}
        for missing in (1, 10, 40):
            path = ntpath.join(tree["shallow"], *["x"] * missing)
            result, counts[missing] = self._calls(monkeypatch, path)
            assert ntpath.normcase(result) == ntpath.normcase(path)

        assert [counts[m]["readlink"] for m in (1, 10, 40)] == [1, 10, 40]
        assert counts[10]["final"] - counts[1]["final"] == 9
        assert counts[40]["final"] - counts[10]["final"] == 30
        assert all(counts[m]["lstat"] == 0 for m in counts)

    def test_a_missing_tail_returns_the_resolved_prefix(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The F term: a short junction plus one missing component resolves
        to a result as long as the junction's target, at the same calls."""
        root = ntpath.realpath(tmp_path)
        target = ntpath.join(root, *["t" * 20] * 6)
        os.makedirs(target)
        junction = ntpath.join(root, "j")
        winapi: Any = importlib.import_module("_winapi")
        winapi.CreateJunction(target, junction)
        os.mkdir(ntpath.join(root, "s"))
        try:
            _, short_calls = self._calls(monkeypatch, ntpath.join(root, "s", "x"))
            path = ntpath.join(junction, "x")
            result, calls = self._calls(monkeypatch, path)
        finally:
            os.rmdir(junction)  # removes the junction, not its target

        assert ntpath.normcase(result) == ntpath.normcase(ntpath.join(target, "x"))
        assert len(result) - len(path) == len(target) - len(junction) > 100
        assert calls == short_calls, (calls, short_calls)  # one missing component each
        assert calls["readlink"] == 1, calls

    @staticmethod
    def _refusing(deep: str) -> tuple[str, Callable[[str], str]]:
        """A `_getfinalpathname` that raises ERROR_ACCESS_DENIED for the
        bottom six levels of the 20-level tree."""
        denied = ntpath.normcase(deep[: -len("\\d") * 5])  # levels 15 to 20 refuse
        assert denied.endswith("\\d") and ntpath.isdir(denied)
        real_final = getattr(ntpath, "_getfinalpathname")  # noqa: B009 - not in typeshed

        def refuses(path: str) -> str:
            name = ntpath.normcase(path).removeprefix("\\\\?\\")
            if name == denied or name.startswith(denied + "\\"):
                raise OSError(13, "Access is denied", path, 5)
            return real_final(path)

        return denied, refuses

    def test_a_component_it_cannot_open_is_walked_like_a_missing_one(
        self, tree: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An existing directory that refuses the open (ERROR_ACCESS_DENIED,
        stubbed at level 15 of the 20-level tree) costs a step per component
        from there down, exactly as a missing tail of the same length does."""
        deep = tree["deep"]
        _, refuses = self._refusing(deep)

        with monkeypatch.context() as patch:
            patch.setattr(ntpath, "_getfinalpathname", refuses)
            result, calls = self._calls(monkeypatch, deep)
        missing, missing_calls = self._calls(monkeypatch, ntpath.join(tree["shallow"], *["x"] * 6))

        assert ntpath.normcase(result) == ntpath.normcase(deep)
        assert calls["readlink"] == 6, calls  # the stub refused six levels
        assert calls == missing_calls, (calls, missing_calls)
        assert ntpath.normcase(missing).endswith("\\x" * 6)

    def test_a_sharing_violation_is_walked_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A real file the process cannot open: the page file or another
        system file held without sharing at the root of the system drive."""
        drive = os.environ.get("SYSTEMDRIVE", "C:") + "\\"
        refused = None
        for name in ("pagefile.sys", "swapfile.sys", "DumpStack.log.tmp"):
            candidate = ntpath.join(drive, name)
            try:
                nt._getfinalpathname(candidate)
            except OSError as error:
                if getattr(error, "winerror", None) == 32 and ntpath.lexists(candidate):
                    refused = candidate
                    break
        if refused is None:
            pytest.skip(
                "missing locked-system-file: no system file held with a sharing violation on this machine"
            )

        result, calls = self._calls(monkeypatch, refused)
        _, missing_calls = self._calls(monkeypatch, ntpath.join(drive, "nt-page-missing"))

        assert ntpath.normcase(result) == ntpath.normcase(refused)
        assert calls["readlink"] == 1, calls
        assert calls == missing_calls, (calls, missing_calls)

    def test_a_dangling_chain_is_read_one_link_at_a_time(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The W term: a chain of junctions ending at a missing target costs a
        `readlink()` per link, with the argument, the result and the missing
        tail the same length for both chains."""
        root = ntpath.realpath(tmp_path)
        counts: dict[int, dict[str, int]] = {}
        for prefix, links in (("a", 2), ("b", 20)):
            end = ntpath.join(root, f"gone{prefix}")
            made = _junction_chain(root, prefix, links, end, dangling=True)
            try:
                for tail in (0, 2):
                    path = ntpath.join(made[-1], *["x"] * tail)
                    result, calls = self._calls(monkeypatch, path)
                    assert ntpath.normcase(result) == ntpath.normcase(
                        ntpath.join(end, *["x"] * tail)
                    )
                    assert calls["lstat"] == 0, calls
                    counts[links + 100 * tail] = calls
            finally:
                for junction in reversed(made):
                    os.rmdir(junction)  # removes the junction, not its target

        # One readlink() per link, and one more for the missing end.
        assert counts[2]["readlink"] == 3 and counts[20]["readlink"] == 21, counts
        # Two missing components below the link add a step each, as a
        # missing tail does anywhere; the chain's cost is unchanged.
        assert counts[202]["readlink"] - counts[2]["readlink"] == 2, counts
        assert counts[220]["readlink"] - counts[20]["readlink"] == 2, counts
        # Only the chain's length changed: the _getfinalpathname() calls did not.
        assert counts[2]["final"] == counts[20]["final"], counts
        assert counts[202]["final"] == counts[220]["final"] == counts[2]["final"] + 2, counts

    def test_a_chain_longer_than_one_open_follows_is_read_too(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A chain of junctions to a directory that exists: 40 links open in
        two calls, 80 are more than Windows follows, and realpath() reads
        every one of them."""
        root = ntpath.realpath(tmp_path)
        end = ntpath.join(root, "exists")
        counts: dict[int, dict[str, int]] = {}
        for prefix, links in (("a", 40), ("b", 80)):
            made = _junction_chain(root, prefix, links, end, dangling=False)
            try:
                result, counts[links] = self._calls(monkeypatch, made[-1])
                assert ntpath.normcase(result) == ntpath.normcase(end)
            finally:
                for junction in reversed(made):
                    os.rmdir(junction)  # removes the junction, not its target

        assert counts[40] == {"final": 2, "readlink": 0, "lstat": 0}, counts
        assert counts[80]["readlink"] == 81, counts

    def test_strict_raises_where_the_walk_would_begin(
        self, tree: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`realpath(path, strict=True)` - no walk: one call, then the error."""
        _, existing = self._calls(monkeypatch, tree["deep"], strict=True)
        path = ntpath.join(tree["shallow"], *["x"] * 10)
        error, calls = self._calls(monkeypatch, path, strict=True)

        assert existing == {"final": 2, "readlink": 0, "lstat": 0}, existing
        assert isinstance(error, FileNotFoundError), error
        assert calls == {"final": 1, "readlink": 0, "lstat": 0}, calls

    def test_allow_missing_walks_only_a_missing_tail(
        self, tree: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        allow_missing = getattr(ntpath, "ALLOW_MISSING")  # noqa: B009 - not in typeshed
        path = ntpath.join(tree["shallow"], *["x"] * 10)
        walked, calls = self._calls(monkeypatch, path, strict=allow_missing)
        _, lenient = self._calls(monkeypatch, path)

        assert ntpath.normcase(walked) == ntpath.normcase(path)
        assert calls == lenient and calls["readlink"] == 10, (calls, lenient)

        _, refuses = self._refusing(tree["deep"])
        with monkeypatch.context() as patch:
            patch.setattr(ntpath, "_getfinalpathname", refuses)
            error, _ = self._calls(monkeypatch, tree["deep"], strict=allow_missing)
        assert isinstance(error, PermissionError), error

    def test_it_normalises_its_argument_first(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """realpath() starts with `normpath()` of the whole argument, which is
        the Python loop on 3.10 and the C helper from 3.11."""
        monkeypatch.chdir(tmp_path)
        counter = Counter(ntpath.normpath)
        monkeypatch.setattr(ntpath, "normpath", counter)
        path = _dotted(50)

        result = ntpath.realpath(path)

        assert counter.first == (path,)
        assert ntpath.normcase(result) == ntpath.normcase(
            ntpath.join(ntpath.realpath(tmp_path), "a")
        )
        if sys.version_info < (3, 11):
            assert not hasattr(nt, "_path_normpath")

    @pytest.mark.timing
    def test_on_3_10_its_normpath_is_quadratic(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """16x the `.` components: over 64x the time on 3.10, under 80x from
        3.11, where the normalisation is C and the two calls are fixed."""
        monkeypatch.chdir(tmp_path)
        small_path, large_path = _dotted(3_000), _dotted(48_000)
        small = best_ns(lambda: ntpath.realpath(small_path), repeats=15)
        large = best_ns(lambda: ntpath.realpath(large_path), repeats=3)

        ratio = large / small
        if sys.version_info < (3, 11):
            assert ratio > 64, f"16x the components cost x{ratio:.1f} on 3.10"
        else:
            assert ratio < 80, f"16x the components cost x{ratio:.1f}"


class TestRealpathElsewhere:
    """`ntpath.realpath(path)`, elsewhere | O(L + C) - it is `abspath()`."""

    def test_it_is_abspath_and_asks_the_filesystem_nothing(
        self, fallback: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counter = Counter(fallback.abspath)
        monkeypatch.setattr(fallback, "abspath", counter)
        counters = _count_os(monkeypatch, "stat", "lstat", "readlink")

        assert fallback.realpath(r"C:\a\link\..\b") == r"C:\a\b"
        assert fallback.realpath(r"C:\x", strict=True) == r"C:\x"
        assert counter.calls == 2
        assert all(c.calls == 0 for c in counters.values()), counters


class TestIsmount:
    """`ntpath.ismount(path)` | O(L + C) - one volume query on Windows,
    and lexical elsewhere."""

    @WINDOWS
    def test_ismount_is_one_volume_query(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        volume = Counter(getattr(ntpath, "_getvolumepathname"))  # noqa: B009 - not in typeshed
        full = Counter(getattr(ntpath, "_getfullpathname"))  # noqa: B009 - not in typeshed
        monkeypatch.setattr(ntpath, "_getvolumepathname", volume)
        monkeypatch.setattr(ntpath, "_getfullpathname", full)

        def no_realpath(*args: object, **kwargs: object) -> str:
            raise AssertionError("ismount() called realpath()")

        monkeypatch.setattr(ntpath, "realpath", no_realpath)

        assert ntpath.ismount(str(tmp_path)) is False
        assert (volume.calls, full.calls) == (1, 1)

        drive_root = ntpath.splitdrive(str(tmp_path))[0] + "\\"
        assert ntpath.ismount(drive_root) is True
        assert ntpath.ismount(r"\\server\share") is True
        assert volume.calls == 1, "a drive or share root is answered without the query"

    def test_elsewhere_only_the_two_roots_are_mounts(
        self, fallback: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counters = _count_os(monkeypatch, "stat", "lstat", "readlink")

        assert fallback.ismount("C:\\") and fallback.ismount(r"\\server\share")
        assert not fallback.ismount(r"C:\Windows")
        assert not fallback.ismount(r"\\server\share\dir")
        assert all(c.calls == 0 for c in counters.values()), counters


@pytest.mark.skipif(sys.version_info < (3, 12), reason="isdevdrive is 3.12+")
class TestIsdevdrive:
    """`ntpath.isdevdrive(path)` | O(L + C) on Windows, O(1) and `False`
    elsewhere."""

    @WINDOWS
    def test_on_windows_it_is_abspath_then_one_query(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isdevdrive = getattr(ntpath, "isdevdrive")  # noqa: B009 - typeshed 3.12+
        absolute = Counter(ntpath.abspath)
        query = Counter(nt._path_isdevdrive)
        monkeypatch.setattr(ntpath, "abspath", absolute)
        monkeypatch.setattr(ntpath, "_path_isdevdrive", query)

        assert isinstance(isdevdrive("relative"), bool)
        assert (absolute.calls, query.calls) == (1, 1)
        assert query.first == (ntpath.join(os.getcwd(), "relative"),)

        def fails(path: str) -> bool:
            raise OSError(21, "The device is not ready", path, 21)

        monkeypatch.setattr(ntpath, "_path_isdevdrive", fails)
        assert isdevdrive(str(tmp_path)) is False

    def test_elsewhere_it_is_false_without_the_filesystem(
        self, fallback: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counters = _count_os(monkeypatch, *FILESYSTEM)
        assert fallback.isdevdrive("C:\\") is False
        assert fallback.isdevdrive("relative") is False
        assert all(c.calls == 0 for c in counters.values()), counters


class TestPredicatesAndMetadata:
    """The O(1) rows: the C helpers on Windows, one stat or lstat each
    otherwise."""

    @WINDOWS
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the helpers are 3.12+")
    def test_on_windows_the_predicates_skip_os_stat(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        counters = _count_os(monkeypatch, "stat", "lstat")

        assert ntpath.exists(target) and ntpath.isfile(target) and ntpath.isdir(tmp_path)
        assert not ntpath.islink(target)
        if sys.version_info >= (3, 13):
            assert ntpath.lexists(target)
            assert getattr(ntpath, "isjunction")(tmp_path) is False  # noqa: B009
        assert counters["stat"].calls == counters["lstat"].calls == 0, counters

    @WINDOWS
    @pytest.mark.skipif(sys.version_info[:2] != (3, 12), reason="3.12 lstats; 3.13 has C")
    def test_on_windows_3_12_isjunction_is_one_lstat(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counters = _count_os(monkeypatch, "lstat")
        assert getattr(ntpath, "isjunction")(tmp_path) is False  # noqa: B009
        assert counters["lstat"].calls == 1

    def test_the_fallback_predicates_make_one_call_each(
        self, fallback: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        counters = _count_os(monkeypatch, "stat", "lstat")
        calls: dict[str, tuple[int, int]] = {}
        for name in ("exists", "isdir", "isfile", "islink", "lexists"):
            before = (counters["stat"].calls, counters["lstat"].calls)
            getattr(fallback, name)(target)
            calls[name] = (counters["stat"].calls - before[0], counters["lstat"].calls - before[1])

        assert calls == {
            "exists": (1, 0),
            "isdir": (1, 0),
            "isfile": (1, 0),
            "islink": (0, 1),
            "lexists": (0, 1),
        }

    @pytest.mark.skipif(
        sys.version_info < (3, 12)
        or (sys.version_info < (3, 13) and hasattr(os.stat_result, "st_reparse_tag")),
        reason="3.12+; on 3.12 the fallback lstats wherever stat_result has st_reparse_tag",
    )
    def test_isjunction_elsewhere_is_false_without_the_filesystem(
        self, fallback: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counters = _count_os(monkeypatch, *FILESYSTEM)
        assert fallback.isjunction(tmp_path) is False
        assert all(c.calls == 0 for c in counters.values()), counters

    def test_metadata_is_one_stat_each(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "f.txt"
        target.write_text("content", encoding="utf-8")
        counters = _count_os(monkeypatch, "stat", "fstat")
        for name in ("getsize", "getmtime", "getatime", "getctime"):
            before = counters["stat"].calls
            getattr(ntpath, name)(target)
            assert counters["stat"].calls - before == 1, name

        before = counters["stat"].calls
        assert ntpath.samefile(target, str(target))
        assert counters["stat"].calls - before == 2

        with open(target, "rb") as first, open(target, "rb") as second:
            assert ntpath.sameopenfile(first.fileno(), second.fileno())
        assert counters["fstat"].calls == 2

        stats = os.stat(target), os.stat(target)
        before = counters["stat"].calls
        assert ntpath.samestat(*stats)
        assert counters["stat"].calls == before


class TestConstants:
    """The constants are the same on every platform."""

    def test_the_separators_and_names(self, fallback: Any) -> None:
        for module in (ntpath, fallback):
            assert (module.sep, module.altsep, module.curdir, module.pardir) == (
                "\\",
                "/",
                ".",
                "..",
            )
            assert (module.extsep, module.pathsep, module.defpath, module.devnull) == (
                ".",
                ";",
                ".;C:\\bin",
                "nul",
            )

    def test_supports_unicode_filenames(self) -> None:
        expected = sys.version_info >= (3, 12) or sys.platform == "win32"
        assert ntpath.supports_unicode_filenames is expected

    def test_allow_missing_is_genericpath_s(self) -> None:
        allow_missing = getattr(ntpath, "ALLOW_MISSING")  # noqa: B009 - not in typeshed
        assert allow_missing is getattr(genericpath, "ALLOW_MISSING")  # noqa: B009


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
    """Each block runs in its own subprocess and working directory and
    asserts its own result. The two that resolve against a Windows
    filesystem run only on Windows."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        for marker in WINDOWS_BLOCKS:
            assert sum(marker in source for _, source in blocks) == 1, marker

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = skipped = 0
        for line, source in _blocks():
            if sys.platform != "win32" and any(marker in source for marker in WINDOWS_BLOCKS):
                skipped += 1
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran + skipped == EXPECTED_BLOCKS
        assert skipped == (0 if sys.platform == "win32" else len(WINDOWS_BLOCKS))
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if 'commonpath(paths) == r"C:\\Proj"' in s)
        mutated = source.replace('commonpath(paths) == r"C:\\Proj"', 'commonpath(paths) == "C:"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
