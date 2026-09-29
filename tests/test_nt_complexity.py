"""Tests for docs/stdlib/nt.md.

The page makes three kinds of claim. Every public function on `nt` is the
same object `os` exposes, so their bounds live on the os page and are tested
in test_os_complexity.py; this file pins the identity that makes that
delegation sound, and the one bound the os page states for a function `nt`
shares (`getcwd()`), which is the size of its result. The rest is what is
Windows's own: `nt.environ` and how it relates to `os.environ`, and the
private helpers that carry `ntpath`'s work, where a path operation costs
something other than the os page's POSIX account. Nearly all of it is
settled by observation - identity, call counters on the helpers `ntpath`
looks up in its own globals, dict membership, and child processes started
with a controlled environment. Three timing tests settle `normpath()` and
the `normpath()` that `realpath()` starts with.

Measurement scope:

* The identity row is checked over every public name in `dir(nt)`: each one
  but `environ` is the identical object under the same name on `os`, and the
  names `os` adds in Python (`walk`, `makedirs`, `fdopen`, `getenv`, `execl`,
  `spawnl`, `add_dll_directory`) are absent from `nt`. `nt.uname_result` is
  `os.uname_result`, and `nt` has no `uname`.
* `getcwd()` returns the whole working directory: from two directories
  whose paths differ by 79 characters, the results are exactly those paths.
  The time side is read from `posix_getcwd()` in Modules/posixmodule.c,
  which copies `GetCurrentDirectoryW`'s buffer into the result.
* `os.times()` returns an `nt.times_result` of five fields, and after a
  second of busy work `user` is positive while `children_user`,
  `children_system` and `elapsed` are 0. The `n_*` class attributes are
  asserted by value on both struct sequences.
* `nt.environ` is a dict of str keys and values. A child started with 4 and
  with 256 mixed-case variables holds each one in `nt.environ` under its
  original case and in `os.environ` upper-cased, with at most two variables
  beyond them (the venv launcher adds `PROCESSOR_ARCHITECTURE`). In the
  child every value in `os.environ`'s dict is, by identity, the object
  `nt.environ` holds under the original key, so building `os.environ`
  copies keys and not values: O(n). The O(b) of `nt.environ` itself is read
  from `convertenviron()` in Modules/posixmodule.c, one new str per key and
  value, and the loop that shares the values from `_createenviron()`
  (3.10-3.13) and `_create_environ_mapping()` (3.14) in Lib/os.py;
  interpreter startup cannot be timed from inside the interpreter. The
  child also shows `nt.environ` missing an upper-case spelling that
  `os.environ` finds.
* `os.environ` keeps a dict of its own, not `nt.environ`. A read through it
  returns the stored value object, by identity, for any case of the key. A
  write through it does not reach `nt.environ`, and a write into
  `nt.environ` does not reach it; a child process started afterwards sees
  the `os.environ` write, so it went through `putenv()`. A read from
  `nt.environ` returns the stored object. On 3.14+ a value set with `os.putenv()`
  appears in `os.environ` after `os.reload_environ()` and in a fresh
  `nt._create_environ()`, and not in `nt.environ`; the test restores
  `os.environ`'s dict afterwards.
* `ntpath.normpath()` is `nt._path_normpath` from 3.12 and calls it from
  3.11, where a counter on the name `ntpath` imported sees one call; 3.10
  has no `_path_normpath`. In timing tests, 16x the length of a path of `.`
  components (5,000 to 80,000) costs `nt._path_normpath` under 80x (x16 to
  x17 on 3.14, where quadratic predicts 256x). 16x the components (3,000 to
  48,000) costs the Python fallback over 64x, both for a run of `.`
  components (x280 to x520 on 3.14) and for n names followed by n `..`
  (x150 to x170), where linear predicts 16x. The fallback runs in a child
  that deletes `nt._path_normpath` before reloading `ntpath`, or directly
  off Windows, where it is what `ntpath.normpath` always is; that test runs
  on every platform. The C helper was timed on the `.` shape only.
* `ntpath.realpath()` is counted on a 1-level and a 20-level directory and
  through a chain of five junctions: two `_getfinalpathname()` calls each,
  no `readlink()` and no `os.lstat()`. With 1, 10 and 40 missing trailing
  components it makes one more `_getfinalpathname()` and one more
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
  supported version) and
  `realpath()` reads all 80 links and the directory. That the chain stops
  at a loop, and that each step's string work and the `seen` set are the
  length of the path reached, is read from `_readlink_deep()` in
  Lib/ntpath.py, the same on every supported version.
  `realpath()` passes its argument to `normpath()` first, on every version;
  timed on a path of `.` components, 16x the components (3,000 to 48,000)
  cost over 64x on 3.10 (x139 to x197 under x64 emulation) and under 80x
  from 3.11 (x2 to x3 on 3.11 and 3.14). The per-call string work, and so
  the L + C factor, is read from Lib/ntpath.py rather than measured.
* `ntpath.ismount()` on a directory makes one `_getfullpathname()` and one
  `_getvolumepathname()` call and no `realpath()` call, which is patched to
  raise, on every supported version. `ntpath.abspath()` makes one
  `_getfullpathname()` call, whose result is the working directory joined
  to the argument.
* The private helper rows: `ntpath.isdir`, `isfile`, `islink` and `exists`
  are the `nt._path_*` functions from 3.12 and absent from `nt` before;
  `isjunction`, `lexists` and `splitroot` likewise from 3.13;
  `ntpath.isdevdrive()` calls `nt._path_isdevdrive` from 3.12.
  `_findfirstfile()` returns a file's on-disk spelling for a lower-case
  query; `_getvolumepathname()` returns the drive root for a directory on
  it; `_getfinalpathname()` returns the resolved path with the `\\\\?\\`
  prefix; `_getdiskusage()` agrees with `shutil.disk_usage()`;
  `_add_dll_directory()` returns a cookie `_remove_dll_directory()` accepts;
  `_path_splitroot()` returns `(root, rest)`; `_exit` is `os._exit`;
  `_have_functions` is a list naming `MS_WINDOWS`; the `_LOAD_LIBRARY_*`
  flags are ints; `_supports_virtual_terminal()` and
  `_is_inputhook_installed()` return bools on 3.13+. The O(1) and O(L)
  bounds of these helpers are read from Modules/posixmodule.c: each is one
  or two Win32 calls, with a copy of the path or the result around it.
* Which version added each private name was found by listing `dir(nt)` on
  3.10.21, 3.11.16, 3.12.14, 3.13.15 and 3.14.7; the tests assert each name
  against `sys.version_info` and were run on each of those versions.
* Every fenced block on the page runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That a system call counts as O(1): the page follows the os page. How long
  the kernel takes to resolve a deep path in `_getfinalpathname()`, or a
  predicate's query, is outside that model.
* `nt._inputhook()` is not called: it runs whatever input hook is
  installed, and the row says so. `nt._path_splitroot()` being used by
  `importlib` is read from Lib/importlib/_bootstrap_external.py.
* The `putenv()` cost of an `os.environ` write is the os page's row, and its
  evidence is in test_os_complexity.py.
* Every test except the block count and the fallback `normpath()` timing is
  Windows-only and skips elsewhere, so a run on Linux or macOS verifies none
  of the page's other claims.
"""

from __future__ import annotations

import importlib
import json
import ntpath
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "nt.md"
EXPECTED_BLOCKS = 4

WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="nt is Windows-only")
nt: Any = importlib.import_module("nt") if sys.platform == "win32" else None

PYTHON_ADDS = ["walk", "makedirs", "fdopen", "getenv", "execl", "spawnl", "add_dll_directory"]


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


@WINDOWS
class TestFunctionsAreOsFunctions:
    """Every public function is the same object os exposes."""

    def test_every_public_name_but_environ_is_the_same_object(self) -> None:
        public = [name for name in dir(nt) if not name.startswith("_")]
        shared = [name for name in public if getattr(os, name, None) is getattr(nt, name)]

        assert set(public) - set(shared) == {"environ"}, sorted(set(public) - set(shared))
        assert len(shared) > 90, len(shared)  # the check ran over the real module
        assert nt.environ is not os.environ

    def test_what_os_adds_in_python_is_not_in_nt(self) -> None:
        for name in PYTHON_ADDS:
            assert hasattr(os, name), name
            assert not hasattr(nt, name), name

    def test_uname_result_exists_without_uname(self) -> None:
        assert nt.uname_result is os.uname_result
        assert not hasattr(nt, "uname")
        assert (
            nt.uname_result.n_fields,
            nt.uname_result.n_sequence_fields,
            nt.uname_result.n_unnamed_fields,
        ) == (5, 5, 0)

    def test_getcwd_returns_the_whole_directory(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`nt.getcwd()` | O(C) | O(C) - the result is the working directory."""
        short = tmp_path / "s"
        long = tmp_path / ("x" * 80)
        short.mkdir()
        long.mkdir()

        monkeypatch.chdir(short)
        at_short = nt.getcwd()
        monkeypatch.chdir(long)
        at_long = nt.getcwd()

        assert nt.getcwd is os.getcwd
        assert ntpath.normcase(at_short) == ntpath.normcase(ntpath.realpath(short))
        assert ntpath.normcase(at_long) == ntpath.normcase(ntpath.realpath(long))
        assert len(at_long) - len(at_short) == 79
        assert nt.getcwdb() == os.fsencode(at_long)


@WINDOWS
class TestTimesResult:
    """`os.times()` returns an `nt.times_result`; Windows fills two fields."""

    def test_only_user_and_system_are_reported(self) -> None:
        deadline = time.process_time() + 1.0
        while time.process_time() < deadline:
            pass
        result = os.times()

        assert type(result) is nt.times_result
        assert result.user > 0
        assert result.system >= 0
        assert (result.children_user, result.children_system, result.elapsed) == (0, 0, 0)
        assert (
            nt.times_result.n_fields,
            nt.times_result.n_sequence_fields,
            nt.times_result.n_unnamed_fields,
        ) == (5, 5, 0)


ENVIRON_CHILD = textwrap.dedent(
    """
    import json, nt, os
    data = os.environ._data
    shared = [key for key, value in nt.environ.items() if data.get(key.upper()) is value]
    print(json.dumps([nt.environ, dict(os.environ), shared]))
    """
)


def _child_environments(
    variables: int,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], set[str]]:
    """Start a child with `variables` mixed-case names; return what it was
    given, its `nt.environ`, its `os.environ`, and the `nt.environ` keys whose
    value object `os.environ` holds too, by identity."""
    given = {f"Nt_Page_{index:04d}": "v" * 60 for index in range(variables)}
    given["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    report = subprocess.run(
        [sys.executable, "-c", ENVIRON_CHILD],
        env=given,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    nt_environ, os_environ, shared = json.loads(report.stdout)
    return given, nt_environ, os_environ, set(shared)


@WINDOWS
class TestEnvironIsAStartupCopy:
    """`nt.environ` is a str dict built once; `os.environ` is a second,
    upper-cased dict, and neither writes into the other."""

    def test_it_is_a_dict_of_str(self) -> None:
        assert type(nt.environ) is dict
        assert nt.environ, "an empty environment would make the type check vacuous"
        assert all(type(key) is str for key in nt.environ)
        assert all(type(value) is str for value in nt.environ.values())
        key = next(iter(nt.environ))
        assert nt.environ[key] is nt.environ[key]  # the stored object, O(1) space

    @pytest.mark.parametrize("variables", [4, 256])
    def test_a_child_holds_every_name_in_both_spellings(self, variables: int) -> None:
        given, nt_environ, os_environ, shared = _child_environments(variables)

        assert {key: nt_environ.get(key) for key in given} == given  # original case
        assert {key.upper(): os_environ.get(key.upper()) for key in given} == {
            key.upper(): value for key, value in given.items()
        }
        extras = set(nt_environ) - set(given)
        assert len(extras) <= 2, sorted(extras)
        assert "NT_PAGE_0000" not in nt_environ  # a dict lookup is case-sensitive
        assert os_environ["NT_PAGE_0000"] == "v" * 60
        # os.environ's dict holds nt.environ's value objects, not copies: only
        # the keys are new strings.
        assert set(given) <= shared, sorted(set(given) - shared)

    def test_os_environ_keeps_its_own_dict(self) -> None:
        data = getattr(os.environ, "_data")  # noqa: B009 - private, not in typeshed
        assert data is not nt.environ
        assert all(key == key.upper() for key in data)

    def test_a_read_returns_the_stored_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        value = "x" * 1_000
        monkeypatch.setitem(os.environ, "NT_PAGE_READ", value)

        assert os.environ["NT_PAGE_READ"] is value
        assert os.environ["nt_page_read"] is value

    def test_writes_do_not_cross(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert "NT_PAGE_OS" not in nt.environ and "NT_PAGE_NT" not in os.environ

        monkeypatch.setitem(os.environ, "NT_PAGE_OS", "1")
        monkeypatch.setitem(nt.environ, "NT_PAGE_NT", "1")

        assert "NT_PAGE_OS" not in nt.environ
        assert "NT_PAGE_NT" not in os.environ

        # The os.environ write went through putenv(): a child inherits it.
        child = [sys.executable, "-c", "import os; print(os.environ.get('NT_PAGE_OS'))"]
        seen = subprocess.run(child, capture_output=True, text=True, timeout=60, check=True)
        assert seen.stdout.strip() == "1"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="os.reload_environ is 3.14+")
    def test_reload_environ_leaves_nt_environ_alone(self) -> None:
        reload_environ = getattr(os, "reload_environ")  # noqa: B009 - typeshed 3.14+
        data = getattr(os.environ, "_data")  # noqa: B009
        contents = dict(data)
        before = nt.environ
        assert "NT_PAGE_PUTENV" not in os.environ
        try:
            os.putenv("NT_PAGE_PUTENV", "1")
            assert "NT_PAGE_PUTENV" not in os.environ

            fresh = nt._create_environ()
            reload_environ()

            assert fresh is not nt.environ and fresh["NT_PAGE_PUTENV"] == "1"
            assert os.environ["NT_PAGE_PUTENV"] == "1"
            assert nt.environ is before and "NT_PAGE_PUTENV" not in nt.environ
        finally:
            os.unsetenv("NT_PAGE_PUTENV")
            data.clear()
            data.update(contents)


def _dotted(components: int) -> str:
    return "a" + "\\." * components


FALLBACK_TIMING = textwrap.dedent(
    """
    import importlib, json, time
    try:
        import nt
    except ImportError:
        pass
    else:
        if hasattr(nt, "_path_normpath"):
            del nt._path_normpath
    import ntpath
    ntpath = importlib.reload(ntpath)
    assert type(ntpath.normpath).__name__ == "function"  # the Python fallback

    def best(path, repeats):
        fastest = None
        for _ in range(repeats):
            start = time.perf_counter_ns()
            ntpath.normpath(path)
            elapsed = time.perf_counter_ns() - start
            fastest = elapsed if fastest is None else min(fastest, elapsed)
        return fastest

    def dots(n):
        return "a" + "\\\\." * n

    def pairs(n):
        return "a\\\\" * n + "..\\\\" * n

    print(json.dumps({
        "dots": [best(dots(3_000), 7), best(dots(48_000), 3)],
        "pairs": [best(pairs(3_000), 7), best(pairs(48_000), 3)],
    }))
    """
)


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

    @WINDOWS
    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="nt._path_normpath is 3.11+")
    def test_the_c_helper_is_linear(self) -> None:
        small_path, large_path = _dotted(5_000), _dotted(80_000)
        small = best_ns(lambda: nt._path_normpath(small_path), inner=20)
        large = best_ns(lambda: nt._path_normpath(large_path), inner=5)

        assert nt._path_normpath(large_path) == "a"
        assert large / small < 80, f"16x the path cost x{large / small:.1f}"

    @pytest.mark.timing
    def test_the_python_fallback_is_quadratic(self) -> None:
        report = subprocess.run(
            [sys.executable, "-c", FALLBACK_TIMING],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        ratios = {
            shape: large / small for shape, (small, large) in json.loads(report.stdout).items()
        }

        assert all(ratio > 64 for ratio in ratios.values()), f"16x the path cost {ratios}"


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
    """`ntpath.realpath(path)` - two calls for a path that exists, then one
    more per missing trailing component, and one `readlink()` per link in a
    chain Windows will not resolve."""

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

    def _calls(self, monkeypatch: pytest.MonkeyPatch, path: str) -> tuple[str, dict[str, int]]:
        with monkeypatch.context() as patch:
            counters = self._counted(patch)
            result = ntpath.realpath(path)
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

    def test_a_component_it_cannot_open_is_walked_like_a_missing_one(
        self, tree: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An existing directory that refuses the open (ERROR_ACCESS_DENIED,
        stubbed at level 15 of the 20-level tree) costs a step per component
        from there down, exactly as a missing tail of the same length does."""
        deep = tree["deep"]
        denied = ntpath.normcase(deep[: -len("\\d") * 5])  # levels 15 to 20 refuse
        assert denied.endswith("\\d") and ntpath.isdir(denied)
        real_final = getattr(ntpath, "_getfinalpathname")  # noqa: B009 - not in typeshed

        def refuses(path: str) -> str:
            name = ntpath.normcase(path).removeprefix("\\\\?\\")
            if name == denied or name.startswith(denied + "\\"):
                raise OSError(13, "Access is denied", path, 5)
            return real_final(path)

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
            pytest.skip("no system file held with a sharing violation on this machine")

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


@WINDOWS
class TestIsmountAndAbspath:
    """`ntpath.ismount(path)` and `ntpath.abspath(path)` - one call to nt each
    after the string work; ismount never calls realpath()."""

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

    def test_abspath_is_one_full_path_call(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        full = Counter(getattr(ntpath, "_getfullpathname"))  # noqa: B009 - not in typeshed
        monkeypatch.setattr(ntpath, "_getfullpathname", full)

        result = ntpath.abspath("file.txt")

        assert result == ntpath.join(os.getcwd(), "file.txt")
        assert full.calls == 1


@WINDOWS
class TestPrivateHelpers:
    """The private helper rows: which ntpath function each one is, on which
    version, and what it returns."""

    def test_the_predicates_are_ntpath_from_3_12(self) -> None:
        pairs = {"isdir": "_path_isdir", "isfile": "_path_isfile"}
        pairs.update({"islink": "_path_islink", "exists": "_path_exists"})
        for public, private in pairs.items():
            if sys.version_info >= (3, 12):
                assert getattr(ntpath, public) is getattr(nt, private), public
            else:
                assert not hasattr(nt, private), private
                assert getattr(ntpath, public).__module__ in ("genericpath", "ntpath")

    def test_junction_lexists_and_splitroot_are_ntpath_from_3_13(self) -> None:
        pairs = {"isjunction": "_path_isjunction", "lexists": "_path_lexists"}
        pairs["splitroot"] = "_path_splitroot_ex"
        for public, private in pairs.items():
            if sys.version_info >= (3, 13):
                assert getattr(ntpath, public) is getattr(nt, private), public
            else:
                assert not hasattr(nt, private), private

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="isdevdrive is 3.12+")
    def test_isdevdrive_calls_the_helper(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        counter = Counter(nt._path_isdevdrive)
        monkeypatch.setattr(ntpath, "_path_isdevdrive", counter)
        assert isinstance(getattr(ntpath, "isdevdrive")(str(tmp_path)), bool)  # noqa: B009
        assert counter.calls == 1

    def test_path_helpers_return_what_the_rows_say(self, tmp_path: pathlib.Path) -> None:
        root = ntpath.realpath(tmp_path)
        target = ntpath.join(root, "MixedName.txt")
        pathlib.Path(target).write_text("x", encoding="utf-8")

        drive = ntpath.splitdrive(root)[0]
        assert nt._getvolumepathname(root) == drive + "\\"
        assert nt._getfinalpathname(target) == "\\\\?\\" + target
        assert nt._getfullpathname("x") == ntpath.join(os.getcwd(), "x")
        assert nt._path_splitroot(target) == (drive + "\\", target[len(drive) + 1 :])
        if sys.version_info >= (3, 13):
            assert nt._findfirstfile(ntpath.join(root, "mixedname.txt")) == "MixedName.txt"
        else:
            assert not hasattr(nt, "_findfirstfile")

    def test_disk_usage_and_dll_directories(self, tmp_path: pathlib.Path) -> None:
        total, free = nt._getdiskusage(str(tmp_path))
        assert total == shutil.disk_usage(tmp_path).total
        assert 0 <= free <= total

        cookie = nt._add_dll_directory(str(tmp_path))
        assert nt._remove_dll_directory(cookie) is None

    def test_the_remaining_names(self) -> None:
        assert nt._exit is os._exit
        assert isinstance(nt._have_functions, list) and "MS_WINDOWS" in nt._have_functions
        assert isinstance(nt._LOAD_LIBRARY_SEARCH_DEFAULT_DIRS, int)
        assert isinstance(nt._LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR, int)
        if sys.version_info >= (3, 13):
            assert isinstance(nt._supports_virtual_terminal(), bool)
            assert isinstance(nt._is_inputhook_installed(), bool)
            assert callable(nt._inputhook)
        else:
            assert not hasattr(nt, "_supports_virtual_terminal")
        assert hasattr(nt, "_create_environ") == (sys.version_info >= (3, 14))


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
    # The environment example asserts its name starts out unset.
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("NT_PAGE")}
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory and asserts
    its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @WINDOWS
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

    @WINDOWS
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "nt.open is os.open" in s)
        mutated = source.replace("nt.open is os.open", "nt.open is os.read", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
