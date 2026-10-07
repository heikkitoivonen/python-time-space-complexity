"""Tests for docs/stdlib/posixpath.md.

`posixpath` is pure Python and imports everywhere, but where the `posix`
module exists it binds C helpers for `normpath()` and `splitroot()`. Both
implementations are tested on every platform: the real module, and
`_fallback()`, Lib/posixpath.py executed afresh with an empty module standing
in for `posix`, so that every `from posix import ...` fails and every Python
fallback is bound - on Windows that is simply what `posixpath` is. Most rows
are settled by observation: identity, and call counters on the `os` functions
posixpath and genericpath look up at call time. Timing tests settle the O(L)
rows, the quadratic string work in `realpath()`, `expandvars()` on either
side of its fix, and `join()` of bytes.

Measurement scope:

* Which implementation runs where: with `posix` present, `normpath` is
  `posix._path_normpath` from 3.12 (on 3.11 a wrapper around it, on 3.10
  Python) and `splitroot` is `posix._path_splitroot_ex` from 3.13. The
  fallback's `normpath` and (3.12+) `splitroot` are its own Python
  functions. Nine sample paths - relative, absolute, two and three leading
  slashes, `.` and `..` runs, trailing slashes, empty - give equal results
  from both for `normpath`, `split`, `splitext`, `basename`, `dirname`,
  `join` and (3.12+) `splitroot`.
* String work asks nothing: `split`, `basename`, `dirname`, `splitext`,
  `splitdrive`, `splitroot`, `join`, `normpath`, `normcase`, `isabs`,
  `commonpath`, `commonprefix`, `expandvars`, and `abspath` and `relpath` of
  absolute paths make no `os.stat`, `os.lstat`, `os.fstat`, `os.readlink` or
  `os.getcwd` call. `abspath` of a relative path makes one `os.getcwd` and
  `relpath` of two relative paths two, and nothing else.
* O(1) rows: `normcase(s)` and `splitdrive(s)[1]` are `s` itself, and
  `isabs()` of a 10,000,000-character path costs under 5x what a
  10-character one does.
* O(L) rows, timed at L = 3,000, 30,000 and 300,000: each 10x step costs
  under 30x, where quadratic predicts 100x (x8 to x18 measured on 3.10,
  3.12, 3.13 and 3.14 for the functions that scan the whole path). `split`
  and `dirname` take a path of `ab/./` components; `basename` and `splitext`
  one component with no `/` or `.`, the shape that makes their reverse
  searches scan the whole path; `normpath` (both implementations) a run of
  `./` components and a run of names followed by as many `..`; `abspath`
  and `relpath` absolute paths of one-character components; `commonpath` two
  such paths; `join` of L/2 one-character str arguments. These are str
  arguments.
* `join()` of bytes: 8,000, 32,000 and 128,000 one-character arguments cost
  over 8x on the second 4x step and over 48x across both, where linear
  predicts 4x and 16x; the same sizes as str cost under 8x per step.
* `expandvars()`: the releases that run one `re.sub()` pass (3.14.1,
  3.13.10, 3.12.13, 3.11.15, 3.10.20 and later) are the ones with a
  `_varsub` module global, and on them 4,000, 16,000 and 64,000
  substitutions cost under 64x across both 4x steps, where linear predicts
  16x and quadratic 256x (x3.3 to x4.4 per step measured). On earlier
  releases the same sizes cost over 48x across both steps (x9 and x11 on
  3.12.12). A 14-character argument expands to a 30,000-character
  result.
* `expanduser()` splices in a 5,000-character `HOME` without the password
  database, calls `pwd.getpwuid()` once for `~` with `HOME` unset and
  `pwd.getpwnam()` once for `~user` with `HOME` set.
* `realpath()`: a directory 20 levels below another costs exactly 20 more
  `os.lstat()` calls and no `os.readlink()`; a chain of five symlinks costs
  five `os.readlink()` calls; ten missing trailing components cost ten more
  lstats than the existing prefix. With `strict=True` the first missing
  component raises `FileNotFoundError` after one lstat past the prefix.
  `strict=ALLOW_MISSING` returns a path with a missing tail and raises
  `NotADirectoryError` for a component below a regular file.
* `realpath()` string work: with `os.lstat` replaced by a stub reporting a
  directory, 10x the components (100, 1,000 and 10,000 of 256 characters
  each) costs over 30x per step, where linear predicts 10x and quadratic
  100x. Component width is held fixed; symlinks and filesystem costs are
  excluded from this measurement.
* `realpath()` space: a chain of 160 symlinks in a directory four
  150-character names below the temporary directory (under macOS's
  1,024-byte PATH_MAX) peaks at over 2.5x the traced allocation of a chain
  of 40 (x3.8 to x4.0 on 3.10, 3.12, 3.13 and 3.14), where R grows by about
  half; this is the j·R term.
* `ismount()`: from 3.13 two `os.lstat()` calls and no `realpath()` for a
  directory that is not a mount point; through 3.12 one `realpath()` call.
  A regular file costs one `realpath()` call on every version: through 3.12
  because its first lstat succeeds and finds no symlink, and from 3.13 because
  the lstat of `file/..` fails. A directory whose `path/..` lstat raises
  `PermissionError` (a stub) costs one `realpath()` call too. `/` is a mount
  point.
* Predicates: `exists`, `isdir`, `isfile` and the four `get*` functions make
  one `os.stat()`, `islink` and `lexists` one `os.lstat()`, `samefile` two
  `os.stat()`, `sameopenfile` two `os.fstat()`, and `samestat`, (3.12+)
  `isjunction` and (3.13+) `isdevdrive` none.
* The constants are asserted by value, `supports_unicode_filenames`
  against the platform, and the names the Version Notes list against the
  version.
* Every fenced block on the page runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail. The block that resolves
  symlinks against a real filesystem runs only where `os.name` is "posix".

Not settled here:

* That a system call counts as O(1): the page follows the os page. The
  kernel resolving a deep path in one lstat is outside that model.
* The O(L) bounds of the C helpers are read from Python/fileutils.c and
  Modules/posixmodule.c and timed only on the shapes above.
* The password database's cost for `expanduser()` depends on the NSS
  backend.
* The realpath and ismount counts need '/'-rooted paths and symlinks, so
  they run where `os.name` is "posix"; on Windows those tests skip.
* Bytes paths are varied only for `join()`; component length was not varied
  in the timing tests. `expandvars()` is timed on defined `$name`
  references only; undefined names and unterminated `${` were not varied.
"""

from __future__ import annotations

import functools
import genericpath
import importlib
import importlib.util
import os
import pathlib
import posixpath
import re
import stat
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "posixpath.md"
EXPECTED_BLOCKS = 4

POSIX = pytest.mark.skipif(
    os.name != "posix",
    reason="posixpath resolves '/'-rooted paths, and Windows paths start with a drive",
)

# The block that resolves symlinks against the filesystem; see POSIX.
POSIX_BLOCKS = ("posixpath.realpath(via_link)",)

FILESYSTEM = ("stat", "lstat", "fstat", "readlink", "getcwd")

# The first release of each line whose expandvars() is one re.sub() pass.
EXPANDVARS_FIXED = {10: 20, 11: 15, 12: 13, 13: 10, 14: 1}


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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


def steps(make: Callable[[int], Callable[[], Any]], sizes: tuple[int, ...]) -> list[float]:
    """The cost ratio between each pair of consecutive sizes."""
    durations = [best_ns(make(size)) for size in sizes]
    return [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Counter:
    """Wraps a callable and counts the calls that reach it."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self.func(*args, **kwargs)


def _count_os(monkeypatch: pytest.MonkeyPatch, *names: str) -> dict[str, Counter]:
    """Count calls to the named `os` functions for the rest of the test.

    posixpath and genericpath look each one up on `os` when they call it.
    """
    counters = {name: Counter(getattr(os, name)) for name in names}
    for name, counter in counters.items():
        monkeypatch.setattr(os, name, counter)
    return counters


@functools.cache
def _fallback() -> Any:
    """Lib/posixpath.py executed afresh with an empty `posix` module in place.

    Every `from posix import ...` then fails, so every Python fallback is
    bound: this is the module `posixpath` is on Windows, loaded on any platform.
    """
    saved = sys.modules.get("posix")
    sys.modules["posix"] = types.ModuleType("posix")
    try:
        spec = importlib.util.spec_from_file_location("posixpath_fallback", posixpath.__file__)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            del sys.modules["posix"]
        else:
            sys.modules["posix"] = saved
    return module


@pytest.fixture
def fallback() -> Any:
    return _fallback()


class TestWhereEachImplementationRuns:
    """Where `posix` exists `normpath()` (3.11+) and `splitroot()` (3.13+)
    are C helpers; elsewhere the Python fallbacks run, with the same results."""

    def test_the_fallback_binds_python(self, fallback: Any) -> None:
        assert fallback.normpath.__module__ == "posixpath_fallback"
        if sys.version_info >= (3, 12):
            assert fallback.splitroot.__module__ == "posixpath_fallback"

    @pytest.mark.skipif(os.name != "posix", reason="the posix module exists only on POSIX")
    def test_with_posix_the_helpers_are_bound(self) -> None:
        posix: Any = importlib.import_module("posix")
        has_normpath = hasattr(posix, "_path_normpath")
        assert has_normpath == (sys.version_info >= (3, 11))
        assert (posixpath.normpath is getattr(posix, "_path_normpath", None)) == (
            sys.version_info >= (3, 12)
        )
        splitroot = getattr(posixpath, "splitroot", None)
        assert (splitroot is getattr(posix, "_path_splitroot_ex", False)) == (
            sys.version_info >= (3, 13)
        )

    SAMPLES = (
        "a/b/c",
        "/usr/lib/python3/",
        "//host/share/x",
        "///three/slashes",
        "a/./b/../../../c",
        "/../x/./y//",
        "file.tar.gz",
        ".bashrc",
        "",
    )

    @pytest.mark.parametrize("path", SAMPLES)
    def test_both_give_the_same_answers(self, fallback: Any, path: str) -> None:
        names = ["normpath", "split", "splitext", "basename", "dirname"]
        if sys.version_info >= (3, 12):
            names.append("splitroot")
        for name in names:
            assert getattr(fallback, name)(path) == getattr(posixpath, name)(path), name
        assert fallback.join(path, "x") == posixpath.join(path, "x")


class TestStringWorkAsksNothing:
    """The first two tables but `expanduser()` work on the string alone;
    `abspath()` and `relpath()` add a `getcwd()` per relative argument."""

    CASES: dict[str, Callable[[], Any]] = {
        "split": lambda: posixpath.split("/no/such/dir/x"),
        "basename": lambda: posixpath.basename("/no/such/dir/x"),
        "dirname": lambda: posixpath.dirname("/no/such/dir/x"),
        "splitext": lambda: posixpath.splitext("/no/such/x.txt"),
        "splitdrive": lambda: posixpath.splitdrive("/no/such"),
        "join": lambda: posixpath.join("/no", "such", "x"),
        "normpath": lambda: posixpath.normpath("/no/such/../x"),
        "normcase": lambda: posixpath.normcase("/No/Such"),
        "isabs": lambda: posixpath.isabs("/no/such"),
        "commonpath": lambda: posixpath.commonpath(["/no/such/a", "/no/such/b"]),
        "commonprefix": lambda: posixpath.commonprefix(["/no/such/a", "/no/such/b"]),
        "expandvars": lambda: posixpath.expandvars("$NO_SUCH_VARIABLE_HERE/x"),
        "abspath": lambda: posixpath.abspath("/no/such/../x"),
        "relpath": lambda: posixpath.relpath("/no/such/x", "/no/other"),
    }
    if sys.version_info >= (3, 12):
        CASES["splitroot"] = lambda: getattr(posixpath, "splitroot")("/no/such")  # noqa: B009

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_no_filesystem_call(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        counters = _count_os(monkeypatch, *FILESYSTEM)
        self.CASES[name]()
        assert {key: c.calls for key, c in counters.items()} == dict.fromkeys(FILESYSTEM, 0)

    def test_a_relative_argument_costs_one_getcwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        counters = _count_os(monkeypatch, *FILESYSTEM)
        posixpath.abspath("x/y")
        assert counters["getcwd"].calls == 1
        posixpath.relpath("x/y", "z")
        assert counters["getcwd"].calls == 3
        assert sum(c.calls for c in counters.values()) == 3


class TestConstantTimeRows:
    """`normcase()` and `splitdrive()` return the argument itself; `isabs()`
    reads a prefix."""

    def test_normcase_and_splitdrive_return_the_argument(self) -> None:
        path = "/Srv/" + "x" * 1_000
        assert posixpath.normcase(path) is path
        drive, tail = posixpath.splitdrive(path)
        assert drive == "" and tail is path

    @pytest.mark.timing
    def test_isabs_does_not_read_the_path(self) -> None:
        short, long = "/" + "x" * 10, "/" + "x" * 10_000_000
        short_ns = best_ns(lambda: posixpath.isabs(short), inner=1_000)
        long_ns = best_ns(lambda: posixpath.isabs(long), inner=1_000)
        assert long_ns < short_ns * 5, f"{short_ns:.0f}ns vs {long_ns:.0f}ns"


def _linear_cases() -> dict[str, Callable[[int], Callable[[], Any]]]:
    def components(n: int) -> str:
        return "/" + "a/" * (n // 2)

    cases: dict[str, Callable[[int], Callable[[], Any]]] = {
        "split": lambda n: functools.partial(posixpath.split, "/" + "ab/./" * (n // 5)),
        "dirname": lambda n: functools.partial(posixpath.dirname, "/" + "ab/./" * (n // 5)),
        "basename": lambda n: functools.partial(posixpath.basename, "a" * n),
        "splitext": lambda n: functools.partial(posixpath.splitext, "a" * n),
        "normpath dots": lambda n: functools.partial(posixpath.normpath, "/a" + "/." * (n // 2)),
        "normpath pairs": lambda n: functools.partial(
            posixpath.normpath, "/" + "ab/" * (n // 6) + "../" * (n // 6)
        ),
        "fallback normpath dots": lambda n: functools.partial(
            _fallback().normpath, "/a" + "/." * (n // 2)
        ),
        "fallback normpath pairs": lambda n: functools.partial(
            _fallback().normpath, "/" + "ab/" * (n // 6) + "../" * (n // 6)
        ),
        "abspath": lambda n: functools.partial(posixpath.abspath, components(n)),
        "relpath": lambda n: functools.partial(
            posixpath.relpath, components(n) + "x", components(n) + "y"
        ),
        "commonpath": lambda n: functools.partial(
            posixpath.commonpath, [components(n), components(n) + "b"]
        ),
        "join": lambda n: functools.partial(posixpath.join, "/", *(["a"] * (n // 2))),
    }
    if sys.version_info >= (3, 12):
        splitroot = getattr(posixpath, "splitroot")  # noqa: B009
        cases["splitroot"] = lambda n: functools.partial(splitroot, "//" + "a" * n)
    return cases


class TestStringFunctionsAreLinear:
    """The O(L) rows: 10x the length costs about 10x, not 100x."""

    @pytest.mark.timing
    @pytest.mark.parametrize("name", sorted(_linear_cases()))
    def test_ten_times_the_input_costs_about_ten_times(self, name: str) -> None:
        ratios = steps(_linear_cases()[name], (3_000, 30_000, 300_000))
        assert all(ratio < 30 for ratio in ratios), f"{name}: x{ratios}"


class TestJoin:
    """`join()`: an absolute argument resets; bytes is O(n·L)."""

    def test_an_absolute_argument_discards_the_prefix(self) -> None:
        assert posixpath.join("a", "/b", "c") == "/b/c"
        assert posixpath.join(b"a", b"/b", b"c") == b"/b/c"
        assert posixpath.join("a", "") == "a/"

    @pytest.mark.timing
    def test_bytes_arguments_cost_quadratically_in_their_number(self) -> None:
        sizes = (8_000, 32_000, 128_000)
        as_str = steps(lambda n: functools.partial(posixpath.join, "/", *(["a"] * n)), sizes)
        as_bytes = steps(lambda n: functools.partial(posixpath.join, b"/", *([b"a"] * n)), sizes)

        assert all(step < 8 for step in as_str), f"str: x{as_str}"
        assert as_bytes[1] > 8, f"bytes: x{as_bytes}"
        assert as_bytes[0] * as_bytes[1] > 48, f"bytes: x{as_bytes}"


def _expandvars_is_one_pass() -> bool:
    minor, micro = sys.version_info[1], sys.version_info[2]
    return minor not in EXPANDVARS_FIXED or micro >= EXPANDVARS_FIXED[minor]


class TestExpandvars:
    """`expandvars()` is O(L + V) from the listed releases and rebuilds the
    path per substitution before them."""

    def test_the_listed_releases_have_the_one_pass_version(self) -> None:
        assert ("_varsub" in vars(posixpath)) == _expandvars_is_one_pass()

    @pytest.mark.timing
    def test_substitutions_cost_what_the_release_says(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH_PAGE_X", "v")
        ratios = steps(
            lambda s: functools.partial(posixpath.expandvars, "$PATH_PAGE_X/" * s),
            (4_000, 16_000, 64_000),
        )
        if _expandvars_is_one_pass():
            assert ratios[0] * ratios[1] < 64, f"x{ratios}"
        else:
            assert ratios[0] * ratios[1] > 48, f"x{ratios}"

    def test_the_result_follows_the_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH_PAGE_X", "z" * 30_000)
        assert len(posixpath.expandvars("${PATH_PAGE_X}")) == 30_000


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no pwd module")
class TestExpanduser:
    """`~` is `HOME`; `~user`, and `~` without `HOME`, ask the password
    database."""

    @pytest.fixture
    def pwd_calls(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, Counter]:
        pwd: Any = importlib.import_module("pwd")
        entry = types.SimpleNamespace(pw_dir="/home/from-pwd")
        counters = {
            "getpwuid": Counter(lambda uid: entry),
            "getpwnam": Counter(lambda name: entry),
        }
        for name, counter in counters.items():
            monkeypatch.setattr(pwd, name, counter)
        return counters

    def test_home_is_spliced_in_without_the_database(
        self, monkeypatch: pytest.MonkeyPatch, pwd_calls: dict[str, Counter]
    ) -> None:
        home = "/h" + "x" * 4_998
        monkeypatch.setenv("HOME", home)
        assert posixpath.expanduser("~/notes") == home + "/notes"
        assert sum(c.calls for c in pwd_calls.values()) == 0

    def test_without_home_the_database_is_asked(
        self, monkeypatch: pytest.MonkeyPatch, pwd_calls: dict[str, Counter]
    ) -> None:
        monkeypatch.delenv("HOME", raising=False)
        assert posixpath.expanduser("~/notes") == "/home/from-pwd/notes"
        assert pwd_calls["getpwuid"].calls == 1

    def test_a_named_user_is_always_looked_up(
        self, monkeypatch: pytest.MonkeyPatch, pwd_calls: dict[str, Counter]
    ) -> None:
        monkeypatch.setenv("HOME", "/home/me")
        assert posixpath.expanduser("~other/notes") == "/home/from-pwd/notes"
        assert pwd_calls["getpwnam"].calls == 1


def _symlink(target: str, link: str) -> None:
    try:
        os.symlink(target, link)
    except OSError as error:
        pytest.skip(f"missing symlinks: {error}")


@POSIX
class TestRealpath:
    """One lstat per component and one readlink per symlink; a missing
    component does not end the walk unless `strict` says so."""

    def _calls(self, monkeypatch: pytest.MonkeyPatch, path: str, **kwargs: Any) -> dict[str, int]:
        counters = _count_os(monkeypatch, "lstat", "readlink")
        try:
            posixpath.realpath(path, **kwargs)
        finally:
            monkeypatch.undo()
        return {name: counter.calls for name, counter in counters.items()}

    def test_one_lstat_per_component(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        root = posixpath.realpath(str(tmp_path))
        deep = posixpath.join(root, *["d"] * 20)
        os.makedirs(deep)

        shallow_calls = self._calls(monkeypatch, root)
        deep_calls = self._calls(monkeypatch, deep)

        assert deep_calls["lstat"] - shallow_calls["lstat"] == 20
        assert deep_calls["readlink"] == shallow_calls["readlink"] == 0

    def test_one_readlink_per_symlink(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        root = posixpath.realpath(str(tmp_path))
        os.mkdir(posixpath.join(root, "end"))
        for index in range(5):
            target = f"l{index + 1}" if index < 4 else "end"
            _symlink(target, posixpath.join(root, f"l{index}"))

        start = posixpath.join(root, "l0")
        assert posixpath.realpath(start) == posixpath.join(root, "end")
        assert self._calls(monkeypatch, start)["readlink"] == 5

    def test_a_missing_tail_is_walked_to_the_end(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        root = posixpath.realpath(str(tmp_path))
        missing = posixpath.join(root, *["m"] * 10)

        assert posixpath.realpath(missing) == missing
        extra = self._calls(monkeypatch, missing)["lstat"] - self._calls(monkeypatch, root)["lstat"]
        assert extra == 10

    def test_strict_raises_at_the_first_missing_component(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        root = posixpath.realpath(str(tmp_path))
        missing = posixpath.join(root, *["m"] * 10)
        prefix_lstats = self._calls(monkeypatch, root)["lstat"]

        counters = _count_os(monkeypatch, "lstat")
        with pytest.raises(FileNotFoundError):
            posixpath.realpath(missing, strict=True)
        assert counters["lstat"].calls == prefix_lstats + 1

    @pytest.mark.skipif(
        not hasattr(posixpath, "ALLOW_MISSING"), reason="ALLOW_MISSING arrives in a patch release"
    )
    def test_allow_missing_tolerates_only_a_missing_component(self, tmp_path: pathlib.Path) -> None:
        allow_missing = getattr(posixpath, "ALLOW_MISSING")  # noqa: B009 - not in typeshed
        root = posixpath.realpath(str(tmp_path))
        missing = posixpath.join(root, "a", "b")
        assert posixpath.realpath(missing, strict=allow_missing) == missing

        regular = posixpath.join(root, "file")
        pathlib.Path(regular).write_text("x")
        with pytest.raises(NotADirectoryError):
            posixpath.realpath(posixpath.join(regular, "below"), strict=allow_missing)

    def test_space_grows_with_the_links_followed(self, tmp_path: pathlib.Path) -> None:
        root = posixpath.realpath(str(tmp_path))
        base = posixpath.join(root, *[c * 150 for c in "DEFG"])
        os.makedirs(base)

        def chain(links: int) -> str:
            directory = posixpath.join(base, f"c{links}")
            os.mkdir(directory)
            pathlib.Path(directory, "end").write_text("")
            for index in range(links):
                target = f"l{index + 1}" if index + 1 < links else "end"
                _symlink(target, posixpath.join(directory, f"l{index}"))
            start = posixpath.join(directory, "l0")
            assert posixpath.realpath(start) == posixpath.join(directory, "end")
            return start

        few, many = chain(40), chain(160)
        few_peak = peak_bytes(lambda: posixpath.realpath(few))
        many_peak = peak_bytes(lambda: posixpath.realpath(many))

        assert many_peak > few_peak * 2.5, f"{few_peak} vs {many_peak} bytes"


class TestRealpathStringWork:
    """Each component builds the resolved path so far as a new string, so a
    path of very many components is quadratic in its string work."""

    @pytest.mark.timing
    def test_ten_times_the_components_costs_far_more_than_ten_times(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        directory = os.stat_result((stat.S_IFDIR | 0o755,) + (0,) * 9)
        monkeypatch.setattr(os, "lstat", lambda path: directory)
        durations = []
        for components in (100, 1_000, 10_000):
            path = "/" + "/".join(["x" * 256] * components)
            assert posixpath.realpath(path) == path  # warm before measuring
            durations.append(best_ns(lambda path=path: posixpath.realpath(path)))

        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]
        assert all(ratio > 30 for ratio in ratios), (
            f"10x components cost {[f'x{r:.1f}' for r in ratios]} ({durations} ns); "
            "linear gives x10, quadratic x100"
        )


@POSIX
class TestIsmount:
    """From 3.13 two lstats; through 3.12 a `realpath()` of `path/..`."""

    def test_the_parent_goes_through_realpath_only_through_3_12(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        realpath = Counter(posixpath.realpath)
        monkeypatch.setattr(posixpath, "realpath", realpath)
        counters = _count_os(monkeypatch, "lstat")

        assert not posixpath.ismount(str(tmp_path))
        if sys.version_info >= (3, 13):
            assert realpath.calls == 0
            assert counters["lstat"].calls == 2
        else:
            assert realpath.calls == 1

    def test_a_regular_file_goes_through_realpath(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        regular = tmp_path / "file"
        regular.write_text("")
        realpath = Counter(posixpath.realpath)
        monkeypatch.setattr(posixpath, "realpath", realpath)

        assert not posixpath.ismount(str(regular))
        assert realpath.calls == 1

    def test_a_parent_that_cannot_be_lstated_goes_through_realpath(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        real_lstat = os.lstat

        def refusing(path: Any) -> os.stat_result:
            if os.fspath(path).endswith("/.."):
                raise PermissionError(13, "Permission denied", path)
            return real_lstat(path)

        realpath = Counter(posixpath.realpath)
        monkeypatch.setattr(posixpath, "realpath", realpath)
        monkeypatch.setattr(os, "lstat", refusing)

        assert not posixpath.ismount(str(tmp_path))
        assert realpath.calls == 1

    def test_the_root_is_a_mount_point(self) -> None:
        assert posixpath.ismount("/")


class TestPredicatesAndMetadata:
    """One stat-family call per predicate and getter, two for the
    `same*` pair, none for `samestat()` and the junction and Dev Drive stubs."""

    def test_each_call_count(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.txt"
        path.write_text("hello")
        name = str(path)
        before = os.stat(name)
        counters = _count_os(monkeypatch, "stat", "lstat", "fstat")

        def calls(func: Callable[..., Any], *args: Any) -> tuple[Any, dict[str, int]]:
            for counter in counters.values():
                counter.calls = 0
            result = func(*args)
            return result, {key: c.calls for key, c in counters.items() if c.calls}

        for func in (
            posixpath.exists,
            posixpath.isdir,
            posixpath.isfile,
            posixpath.getsize,
            posixpath.getmtime,
            posixpath.getatime,
            posixpath.getctime,
        ):
            assert calls(func, name)[1] == {"stat": 1}, func.__name__
        for func in (posixpath.islink, posixpath.lexists):
            assert calls(func, name)[1] == {"lstat": 1}, func.__name__
        assert calls(posixpath.samefile, name, name) == (True, {"stat": 2})
        with open(name) as first, open(name) as second:
            fds = first.fileno(), second.fileno()
            assert calls(posixpath.sameopenfile, *fds) == (True, {"fstat": 2})
        assert calls(posixpath.samestat, before, before) == (True, {})
        for stub in ("isjunction", "isdevdrive"):
            if hasattr(posixpath, stub):
                assert calls(getattr(posixpath, stub), name) == (False, {}), stub


class TestConstants:
    """The constants table."""

    def test_the_separators_and_names(self, fallback: Any) -> None:
        for module in (posixpath, fallback):
            assert (
                module.sep,
                module.altsep,
                module.curdir,
                module.pardir,
                module.extsep,
                module.pathsep,
                module.defpath,
                module.devnull,
            ) == ("/", None, ".", "..", ".", ":", "/bin:/usr/bin", "/dev/null")

    def test_supports_unicode_filenames(self) -> None:
        assert posixpath.supports_unicode_filenames == (sys.platform == "darwin")


class TestVersionBoundaries:
    """Version Notes: `splitroot()` and `isjunction()` 3.12+, `isdevdrive()`
    3.13+, `ALLOW_MISSING` 3.10.18, 3.11.13, 3.12.11 and 3.13.4+."""

    @pytest.mark.parametrize("name", ["splitroot", "isjunction"])
    def test_the_312_names(self, name: str) -> None:
        assert hasattr(posixpath, name) == (sys.version_info >= (3, 12))

    def test_isdevdrive_arrives_in_313(self) -> None:
        assert hasattr(posixpath, "isdevdrive") == (sys.version_info >= (3, 13))

    def test_allow_missing_arrives_in_the_listed_patches(self) -> None:
        firsts = {10: 18, 11: 13, 12: 11, 13: 4}
        minor, micro = sys.version_info[1], sys.version_info[2]
        expected = micro >= firsts[minor] if minor in firsts else True

        assert hasattr(posixpath, "ALLOW_MISSING") == expected
        if expected:
            assert getattr(posixpath, "ALLOW_MISSING") is getattr(genericpath, "ALLOW_MISSING")  # noqa: B009


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
    asserts its own result. The one that resolves symlinks runs only where
    `os.name` is "posix"."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        for marker in POSIX_BLOCKS:
            assert sum(marker in source for _, source in blocks) == 1, marker

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = skipped = 0
        for line, source in _blocks():
            if os.name != "posix" and any(marker in source for marker in POSIX_BLOCKS):
                skipped += 1
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran + skipped == EXPECTED_BLOCKS
        assert skipped == (0 if os.name == "posix" else len(POSIX_BLOCKS))
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if 'commonpath(paths) == "/srv"' in s)
        mutated = source.replace(
            'commonpath(paths) == "/srv"', 'commonpath(paths) == "/srv/app"', 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
