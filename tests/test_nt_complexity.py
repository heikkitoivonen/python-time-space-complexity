"""Tests for docs/stdlib/nt.md.

The page makes three kinds of claim. Every public function on `nt` is the
same object `os` exposes, so their bounds live on the os page and are tested
in test_os_complexity.py; this file pins the identity that makes that
delegation sound, and the one bound the os page states for a function `nt`
shares (`getcwd()`), which is the size of its result. The rest is what is
Windows's own: `nt.environ` and how it relates to `os.environ`, and the
private helpers that carry `ntpath`'s work. What those helpers make each
`ntpath` function cost is the ntpath page's subject, and is tested in
test_ntpath_complexity.py. All of it is settled by observation - identity,
call counters, dict membership, and child processes started with a
controlled environment.

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
  `nt._path_normpath` is also timed, in test_ntpath_complexity.py: 16x the
  length of a path of `.` components costs it under 80x. The calls
  `ntpath.realpath()`, `abspath()` and `ismount()` make to
  `_getfinalpathname()`, `readlink()`, `_getfullpathname()` and
  `_getvolumepathname()` are counted there too.
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
* Every test except the block count is Windows-only and skips elsewhere,
  so a run on Linux or macOS verifies none of the page's claims.
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
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "nt.md"
EXPECTED_BLOCKS = 2

WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="nt is Windows-only")
nt: Any = importlib.import_module("nt") if sys.platform == "win32" else None

PYTHON_ADDS = ["walk", "makedirs", "fdopen", "getenv", "execl", "spawnl", "add_dll_directory"]


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
