"""Tests for docs/stdlib/site.md.

The page prices `site` as filesystem work: each site directory it processes
is listed, each `.pth` path line naming a new path costs one existence check,
and the lookup functions build strings, the two user lookups caching theirs.
Those are settled by observation - counting `os.path.exists` calls,
`sys.path` scans, `abs_paths()` calls and `.pth` import-line runs, comparing
outputs, and identity against the cached module globals - and the listing and
file-reading space by traced allocation, which separates the sizes by orders
of magnitude. Tests that call `addsitedir()` or import in-process use a
fixture that swaps in copies of `sys.path` and `sys.path_importer_cache`
through `monkeypatch` and deletes any module the test added to
`sys.modules`; `site.main()`, the startup flags and the command line run in
subprocesses.

Measurement scope:

* `addsitedir()` without `known_paths` calls `os.path.exists` once per
  `sys.path` entry before touching the directory: 10 and 1,000 entries give
  exactly 10 and 1,000 calls for a directory with no `.pth` file, and 0 with
  a set passed. A `.pth` file of distinct existing, missing and repeated
  lines costs one call per line whose directory is not already known, and the
  count does not move when `sys.path` grows from 10 to 1,000 entries. A
  `list` subclass standing in for `sys.path` records no `__contains__` call
  and at most one iteration, so duplicates are found in the set.
* The listing: a directory of 10,000 non-`.pth` files peaks more than 100
  times higher than one of 10, with a set passed so the P term is held fixed.
* Name order: `b.pth` and `a.pth` add their directories as `a`, then `b`.
* A `.pth` line is joined to the site directory, a missing path is not
  added, an existing regular file is, a repeated path is added once, comment
  and blank lines are skipped, and an `import` line after a path line imports
  a module from the directory that line added, so it runs when it is reached.
* On 3.12.4+ a `.pth` file of 100,000 comment lines peaks more than 20 times
  higher than one of 1,000, so the file is held whole, and a file starting
  with a UTF-8 byte order mark still adds the directory on its first line.
* `site.main()` runs under `-S` in a subprocess with `site.venv` replaced by
  the identity, so `site.PREFIXES` is what the test sets on every supported
  version. Over three prefixes with one `.pth` file each and a `sys.path`
  padded to 200 entries, `os.path.exists` is called once per path line, not once per
  `sys.path` entry per directory, and the `import` line runs. `abs_paths()`
  is called once with a relative entry on `sys.path` and not at all without
  one, and once each for a duplicated and an unnormalised entry. With a
  directory holding both hooks as the whole `sys.path`, `sitecustomize` is
  imported, and `usercustomize` only once `ENABLE_USER_SITE` is true.
* In a virtual environment made with `python -m venv --without-pip`, a `.pth`
  file in the environment's site-packages whose `import` line writes a marker
  to stderr runs twice at a normal start, four times under `python -m site`,
  and not at all under `-S`. Only an environment without system site
  packages is built.
* `getsitepackages()` returns 1,000 times the paths for 1,000 prefixes as for
  one, a new list on each call, a path under a prefix that does not exist,
  and runs with
  `os.stat`, `os.listdir` and the `os.path` existence checks replaced by
  functions that raise.
* `getuserbase()` calls `os.path.expanduser` once after `USER_BASE` is
  cleared and not again, both lookups return the object in the module
  global, and neither calls `os.listdir` or `os.scandir`. A normal start has
  `USER_SITE` filled; `-S` followed by `import site` leaves both globals
  `None` until the lookups run, and `ENABLE_USER_SITE` `None` until `main()`
  runs.
* `-s` makes `ENABLE_USER_SITE` false and `python -m site --user-site` exit
  1; without it the exit status is checked against the value the same
  interpreter reports. `python -m site` prints one more line for each extra
  `PYTHONPATH` entry and reports whether `USER_BASE` and `USER_SITE` exist;
  that it prints an entry at a time, in O(1) space, is read from `_script()`.
  `-S` leaves `site` out of `sys.modules`.
* A failed import with three more directories on `sys.path` makes exactly
  three more `FileFinder.find_spec` calls.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The f log f sort and the O(P) set of known paths are read from
  `addsitedir()` and `_init_pathinfo()` in Lib/site.py; only the order the
  sort produces and the existence checks that build the set are observed.
  The r term of `main()`, one `os.path.isdir` per path `getsitepackages()`
  returns, is read from `addsitepackages()`.
* After `main()`, `ENABLE_USER_SITE` is `None` only when the real and
  effective user or group ids differ, which needs a setuid interpreter; that
  case, and the matching exit status 2, are read from
  `check_enableusersite()` and `_script()`.
* The virtual-environment tests use the POSIX layout (`bin/python`) and are
  skipped on Windows, which no run here performs.
* The fallback to the locale encoding for a `.pth` file that is not UTF-8
  cannot be told apart from UTF-8 under a UTF-8 locale, and releases before
  3.12.4 reading the file a line at a time are older than the interpreters
  the space tests run on; both are read from `addpackage()` in the released
  3.12.3 and 3.12.4 sources.
* That `site` reads `pyvenv.cfg` at startup is read from `venv()` in
  Lib/site.py; the tests replace that step.
* The first `getuserbase()` may look the home directory up through the
  password database when `HOME` is unset, which depends on the NSS backend.
* `abs_paths`, `addpackage`, `addsitepackages`, `addusersitepackages`,
  `check_enableusersite`, `enablerlcompleter`, `execsitecustomize`,
  `execusercustomize`, `gethistoryfile`, `makepath`, `register_readline`,
  `removeduppaths`, `setcopyright`, `sethelper`, `setquit`, `venv` and the
  module's `io` import are undocumented helpers the audit reports for
  classification; the page prices them only as steps of `main()` and
  `addsitedir()`.
* Path lengths are held short throughout; `makepath()` normalises each line,
  which is linear in its length, and the page prices it O(1).
"""

from __future__ import annotations

import importlib.machinery
import json
import os
import pathlib
import re
import site
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "site.md"
EXPECTED_BLOCKS = 4


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingExists:
    """Stand-in for `os.path.exists` that counts its calls."""

    def __init__(self) -> None:
        self.calls = 0
        self._real = os.path.exists

    def __call__(self, path: Any) -> bool:
        self.calls += 1
        return self._real(path)


class CountingList(list[str]):
    """A `sys.path` stand-in that records membership tests and iterations."""

    contains = 0
    iterations = 0

    def __contains__(self, item: object) -> bool:
        type(self).contains += 1
        return super().__contains__(item)

    def __iter__(self) -> Iterator[str]:
        type(self).iterations += 1
        return super().__iter__()


@pytest.fixture
def isolated_path(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Give the test its own `sys.path`, importer cache and module table entries."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "path_importer_cache", dict(sys.path_importer_cache))
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        del sys.modules[name]


def padded_path(tmp_path: pathlib.Path, entries: int) -> list[str]:
    """`entries` distinct absolute paths; only the first exists."""
    return [str(tmp_path)] + [str(tmp_path / f"absent{index}") for index in range(entries - 1)]


def write_pth(directory: pathlib.Path, name: str, lines: list[str]) -> None:
    (directory / name).write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def run_python(
    *args: str, env: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=env,
        check=check,
    )


def clean_env(**extra: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONUSERBASE", "PYTHONSTARTUP"}
    }
    env.update(extra)
    return env


@pytest.mark.usefixtures("isolated_path")
class TestAddsitedirChecksThePathOnce:
    """`addsitedir` | O(P + e + f log f + L): every `sys.path` entry is checked
    for existence first unless `known_paths` is given, and each `.pth` line
    naming a path not already known costs one check; known paths are found
    by a set rather than a scan."""

    @pytest.mark.parametrize("entries", [10, 1_000])
    def test_without_known_paths_every_entry_is_checked(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, entries: int
    ) -> None:
        sitedir = tmp_path / "site"
        sitedir.mkdir()
        sys.path[:] = padded_path(tmp_path, entries)
        exists = CountingExists()
        monkeypatch.setattr(os.path, "exists", exists)

        site.addsitedir(str(sitedir))

        assert exists.calls == entries

    def test_with_known_paths_no_entry_is_checked(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sitedir = tmp_path / "site"
        sitedir.mkdir()
        sys.path[:] = padded_path(tmp_path, 1_000)
        exists = CountingExists()
        monkeypatch.setattr(os.path, "exists", exists)

        known: set[str] = set()
        assert site.addsitedir(str(sitedir), known) is known

        assert exists.calls == 0

    @pytest.mark.parametrize("entries", [10, 1_000])
    def test_one_check_per_line_whatever_the_length_of_sys_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, entries: int
    ) -> None:
        sitedir = tmp_path / "site"
        sitedir.mkdir()
        for name in ("one", "two", "three"):
            (sitedir / name).mkdir()
        write_pth(sitedir, "x.pth", ["one", "two", "three", "missing", "one", "two"])
        sys.path[:] = padded_path(tmp_path, entries)
        exists = CountingExists()
        monkeypatch.setattr(os.path, "exists", exists)

        site.addsitedir(str(sitedir), set())

        # three new directories and one missing one; the two repeats are known
        assert exists.calls == 4

    def test_duplicates_are_found_without_scanning_sys_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sitedir = tmp_path / "site"
        sitedir.mkdir()
        (sitedir / "one").mkdir()
        write_pth(sitedir, "x.pth", ["one"] * 50)
        counting = CountingList(padded_path(tmp_path, 100))
        monkeypatch.setattr(sys, "path", counting)
        monkeypatch.setattr(CountingList, "contains", 0)
        monkeypatch.setattr(CountingList, "iterations", 0)

        site.addsitedir(str(sitedir))

        assert CountingList.contains == 0
        assert CountingList.iterations <= 1, "sys.path was walked more than once"
        assert counting[-1] == str(sitedir / "one")
        assert counting.count(str(sitedir / "one")) == 1


@pytest.mark.usefixtures("isolated_path")
class TestPthLines:
    """A path line is joined to the site directory and added only if it
    exists and is new; an `import` line runs as it is read."""

    def test_lines_are_joined_filtered_and_deduplicated(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "plugins").mkdir()
        (tmp_path / "archive.zip").write_bytes(b"")
        lines = ["# a comment", "", "plugins", "missing", "plugins", "archive.zip"]
        write_pth(tmp_path, "x.pth", lines)
        before = len(sys.path)

        site.addsitedir(str(tmp_path))

        # an existing file is added too: the check is for existence, not a directory
        added = [str(tmp_path), str(tmp_path / "plugins"), str(tmp_path / "archive.zip")]
        assert sys.path[before:] == added

    def test_an_import_line_sees_the_lines_above_it(self, tmp_path: pathlib.Path) -> None:
        marker = tmp_path / "plugins" / "site_page_marker.py"
        marker.parent.mkdir()
        marker.write_text("", encoding="utf-8")
        write_pth(tmp_path, "x.pth", ["plugins", "import site_page_marker"])
        assert "site_page_marker" not in sys.modules

        site.addsitedir(str(tmp_path))

        assert sys.modules["site_page_marker"].__file__ == str(marker)

    def test_pth_files_are_processed_in_name_order(self, tmp_path: pathlib.Path) -> None:
        for name in ("b", "a"):
            (tmp_path / name).mkdir()
            write_pth(tmp_path, f"{name}.pth", [name])
        before = len(sys.path)

        site.addsitedir(str(tmp_path))

        assert sys.path[before + 1 :] == [str(tmp_path / "a"), str(tmp_path / "b")]

    @pytest.mark.skipif(sys.version_info < (3, 12, 4), reason="UTF-8 decoding arrived in 3.12.4")
    def test_a_byte_order_mark_is_accepted(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "plugins").mkdir()
        (tmp_path / "x.pth").write_bytes(b"\xef\xbb\xbfplugins\n")

        site.addsitedir(str(tmp_path))

        assert str(tmp_path / "plugins") in sys.path


@pytest.mark.usefixtures("isolated_path")
class TestAddsitedirSpace:
    """`addsitedir` | O(P + e + A + c) space: the whole listing is held, and
    from 3.12.4 the whole `.pth` file. The A term is the entries appended to
    `sys.path`, asserted in `TestPthLines`."""

    def test_the_whole_directory_is_listed(self, tmp_path: pathlib.Path) -> None:
        peaks = []
        for count in (10, 10_000):
            sitedir = tmp_path / f"site{count}"
            sitedir.mkdir()
            for index in range(count):
                (sitedir / f"package{index:05d}.txt").touch()
            site.addsitedir(str(sitedir), set())  # warm
            peaks.append(peak_bytes(lambda d=sitedir: site.addsitedir(str(d), set())))  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 100, f"10 and 10,000 entries without a .pth file: {peaks}"

    @pytest.mark.skipif(sys.version_info < (3, 12, 4), reason="read whole from 3.12.4")
    def test_a_pth_file_is_read_whole(self, tmp_path: pathlib.Path) -> None:
        peaks = []
        for lines in (1_000, 100_000):
            sitedir = tmp_path / f"site{lines}"
            sitedir.mkdir()
            write_pth(sitedir, "x.pth", ["# a comment line"] * lines)
            site.addsitedir(str(sitedir), set())  # warm
            peaks.append(peak_bytes(lambda d=sitedir: site.addsitedir(str(d), set())))  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 20, f"1,000 and 100,000 comment lines: {peaks}"


MAIN_SCRIPT = """
import json, os, site, sys
calls = {"exists": 0, "abs_paths": 0}
real_exists, real_abs_paths = os.path.exists, site.abs_paths
def exists(path):
    calls["exists"] += 1
    return real_exists(path)
def abs_paths():
    calls["abs_paths"] += 1
    real_abs_paths()
site.venv = lambda known_paths: known_paths
site.abs_paths = abs_paths
site.PREFIXES = json.loads(sys.argv[1])
site.ENABLE_USER_SITE = json.loads(sys.argv[2])
sys.path[:] = json.loads(sys.argv[3])
os.path.exists = exists
site.main()
os.path.exists = real_exists
print(json.dumps({
    "calls": calls,
    "path": sys.path,
    "modules": [name for name in ("site_page_marker", "sitecustomize", "usercustomize")
                if name in sys.modules],
}))
"""


class TestMainSharesOneSetOfKnownPaths:
    """`site.main()` | O(P + M + r + e + f log f + L): one `addsitedir()` per
    site directory, sharing the known paths, and O(M) only for a relative,
    duplicated or unnormalised `sys.path` entry."""

    @staticmethod
    def prefix(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
        """A prefix whose site-packages holds `plugin<name>` and a `.pth` naming it."""
        prefix = tmp_path / name
        sitedir = pathlib.Path(site.getsitepackages([str(prefix)])[0])
        sitedir.mkdir(parents=True)
        (sitedir / f"plugin{name}").mkdir()
        write_pth(sitedir, f"{name}.pth", [f"plugin{name}"])
        return prefix

    def run_main(
        self,
        prefixes: list[pathlib.Path],
        path: list[str],
        enable_user_site: bool = False,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = run_python(
            "-S",
            "-c",
            MAIN_SCRIPT,
            json.dumps([str(prefix) for prefix in prefixes]),
            json.dumps(enable_user_site),
            json.dumps(path),
            env=env or clean_env(),
        )
        return json.loads(result.stdout)

    def test_sys_path_is_not_rechecked_per_directory(self, tmp_path: pathlib.Path) -> None:
        prefixes = [self.prefix(tmp_path, name) for name in ("a", "b", "c")]
        padding = padded_path(tmp_path / "padding", 200)

        report = self.run_main(prefixes, padding)

        # one existence check per .pth path line, none for the 200 entries
        assert report["calls"]["exists"] == 3, report["calls"]
        added = [pathlib.Path(entry).name for entry in report["path"][len(padding) :]]
        assert added == ["site-packages", "plugina"] + ["site-packages", "pluginb"] + [
            "site-packages",
            "pluginc",
        ]

    def test_pth_import_lines_run_at_startup(self, tmp_path: pathlib.Path) -> None:
        prefix = self.prefix(tmp_path, "a")
        sitedir = pathlib.Path(site.getsitepackages([str(prefix)])[0])
        (sitedir / "plugina" / "site_page_marker.py").write_text("", encoding="utf-8")
        write_pth(sitedir, "z.pth", ["import site_page_marker"])

        report = self.run_main([prefix], [str(tmp_path)])

        assert "site_page_marker" in report["modules"]

    def test_modules_are_revisited_only_when_an_entry_is_rewritten(
        self, tmp_path: pathlib.Path
    ) -> None:
        clean = self.run_main([], [str(tmp_path)])
        relative = self.run_main([], [str(tmp_path), "relative"])
        duplicate = self.run_main([], [str(tmp_path), str(tmp_path)])
        unnormalised = self.run_main([], [str(tmp_path / "x" / "..")])

        assert clean["calls"]["abs_paths"] == 0
        assert relative["calls"]["abs_paths"] == 1
        assert relative["path"][1] == os.path.abspath("relative")
        assert duplicate["calls"]["abs_paths"] == 1
        assert duplicate["path"] == [str(tmp_path)]
        assert unnormalised["calls"]["abs_paths"] == 1
        assert unnormalised["path"] == [str(tmp_path)]

    def test_customize_modules_are_imported(self, tmp_path: pathlib.Path) -> None:
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        for name in ("sitecustomize", "usercustomize"):
            (hooks / f"{name}.py").write_text("", encoding="utf-8")
        env = clean_env(PYTHONUSERBASE=str(tmp_path / "userbase"))

        disabled = self.run_main([], [str(hooks)], enable_user_site=False, env=env)
        enabled = self.run_main([], [str(hooks)], enable_user_site=True, env=env)

        assert disabled["modules"] == ["sitecustomize"]
        assert enabled["modules"] == ["sitecustomize", "usercustomize"]


class TestLookupsBuildAndCache:
    """`getsitepackages` | O(r); `getuserbase` and `getusersitepackages` | O(1),
    computed once and kept in the module globals."""

    def test_one_or_two_paths_per_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(site, "PREFIXES", ["/prefix0"])
        one = len(site.getsitepackages())
        monkeypatch.setattr(site, "PREFIXES", [f"/prefix{index}" for index in range(1_000)])

        assert len(site.getsitepackages()) == 1_000 * one

    def test_no_path_is_checked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("getsitepackages touched the filesystem")

        monkeypatch.setattr(site, "PREFIXES", ["/nonexistent/prefix"])
        for name in ("exists", "isdir", "isfile", "lexists"):
            monkeypatch.setattr(os.path, name, refuse)
        monkeypatch.setattr(os, "stat", refuse)
        monkeypatch.setattr(os, "lstat", refuse)
        monkeypatch.setattr(os, "listdir", refuse)

        paths = site.getsitepackages()

        assert paths and all(path.startswith("/nonexistent/prefix") for path in paths)
        assert site.getsitepackages() is not paths

    def test_the_user_base_is_computed_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("a lookup listed a directory")

        calls = []
        real = os.path.expanduser

        def expanduser(path: str) -> str:
            calls.append(path)
            return real(path)

        monkeypatch.delenv("PYTHONUSERBASE", raising=False)
        monkeypatch.setattr(site, "USER_BASE", None)
        monkeypatch.setattr(site, "USER_SITE", None)
        monkeypatch.setattr(os.path, "expanduser", expanduser)
        for name in ("listdir", "scandir"):
            monkeypatch.setattr(os, name, refuse)

        first = site.getuserbase()
        assert len(calls) == 1
        assert site.getuserbase() is first is site.USER_BASE
        assert site.getusersitepackages() is site.USER_SITE
        assert site.getusersitepackages() is site.USER_SITE
        assert len(calls) == 1

    def test_startup_fills_the_globals_and_minus_s_does_not(self) -> None:
        script = "import site; print(site.USER_BASE is None, site.USER_SITE is None)"
        fill = "; site.getusersitepackages(); print(site.USER_BASE is None, site.USER_SITE is None)"

        unset = "; print(site.ENABLE_USER_SITE)"

        normal = run_python("-c", script, env=clean_env()).stdout.split()
        bare = run_python("-S", "-c", script + unset + fill, env=clean_env()).stdout.split()

        assert normal == ["False", "False"]
        assert bare == ["True", "True", "None", "False", "False"]


class TestStartupAndCommandLine:
    """`-S` skips `site`; `-s` turns the user site off; `python -m site` is
    O(P) and its `--user-site` exit status follows `ENABLE_USER_SITE`."""

    def test_minus_capital_s_skips_the_module(self) -> None:
        script = "import sys; print('site' in sys.modules, sys.flags.no_site)"

        assert run_python("-S", "-c", script, env=clean_env()).stdout.split() == ["False", "1"]

    def test_minus_s_disables_the_user_site(self) -> None:
        script = "import site; print(site.ENABLE_USER_SITE)"

        assert run_python("-s", "-c", script, env=clean_env()).stdout.strip() == "False"
        result = run_python("-s", "-m", "site", "--user-site", env=clean_env(), check=False)
        assert result.returncode == 1

    def test_the_exit_status_follows_enable_user_site(self) -> None:
        value = run_python("-c", "import site; print(site.ENABLE_USER_SITE)", env=clean_env())
        expected = {"True": 0, "False": 1, "None": 2}[value.stdout.strip()]

        for flag in ("--user-base", "--user-site"):
            result = run_python("-m", "site", flag, env=clean_env(), check=False)
            assert result.returncode == expected, (flag, result.stdout, result.stderr)

    def test_the_report_grows_with_sys_path(self, tmp_path: pathlib.Path) -> None:
        extra = [str(tmp_path / f"entry{index}") for index in range(50)]

        short = run_python("-m", "site", env=clean_env()).stdout
        long = run_python("-m", "site", env=clean_env(PYTHONPATH=os.pathsep.join(extra))).stdout

        assert len(long.splitlines()) == len(short.splitlines()) + 50
        assert re.search(r"^USER_BASE: .*\((exists|doesn't exist)\)$", short, re.M)
        assert re.search(r"^USER_SITE: .*\((exists|doesn't exist)\)$", short, re.M)


PTH_MARKER = "site-page-pth-run"


def run_in(python: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python), *args],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=clean_env(),
        check=True,
    )


@pytest.fixture(scope="module")
def venv_python(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """A pip-less virtual environment whose site-packages holds a `.pth` file
    with an `import` line that writes `PTH_MARKER` to stderr."""
    env = tmp_path_factory.mktemp("venv") / "env"
    run_python("-m", "venv", "--without-pip", str(env), env=clean_env())
    python = env / "bin" / "python"
    purelib = run_in(python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))")
    line = f"import sys; sys.stderr.write('{PTH_MARKER}\\n')"
    write_pth(pathlib.Path(purelib.stdout.strip()), "site_page_count.pth", [line])
    return python


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX virtual-environment layout")
class TestVirtualEnvironmentSitePackagesRunsTwice:
    """In a virtual environment `main()` processes the environment's own
    site-packages twice, and `python -m site` runs `main()` again."""

    @staticmethod
    def runs(python: pathlib.Path, *args: str) -> int:
        return run_in(python, *args).stderr.splitlines().count(PTH_MARKER)

    def test_a_normal_start_runs_the_import_line_twice(self, venv_python: pathlib.Path) -> None:
        assert self.runs(venv_python, "-c", "pass") == 2

    def test_python_m_site_runs_it_twice_more(self, venv_python: pathlib.Path) -> None:
        assert self.runs(venv_python, "-m", "site") == 4

    def test_minus_capital_s_never_runs_it(self, venv_python: pathlib.Path) -> None:
        assert self.runs(venv_python, "-S", "-c", "pass") == 0


@pytest.mark.usefixtures("isolated_path")
class TestEachAddedDirectoryIsSearched:
    """Each directory `site` adds is one more entry an import miss searches."""

    def test_a_miss_asks_one_more_finder_per_directory(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = []
        real = importlib.machinery.FileFinder.find_spec

        def find_spec(self: Any, fullname: str, target: Any = None) -> Any:
            if fullname == "site_page_no_such_module":
                calls.append(fullname)
            return real(self, fullname, target)

        monkeypatch.setattr(importlib.machinery.FileFinder, "find_spec", find_spec)

        def misses() -> int:
            calls.clear()
            with pytest.raises(ModuleNotFoundError):
                __import__("site_page_no_such_module")
            return len(calls)

        base = misses()
        for index in range(3):
            directory = tmp_path / f"extra{index}"
            directory.mkdir()
            sys.path.append(str(directory))

        assert misses() == base + 3


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
    """Each block runs in its own subprocess, so the `sys.path` and module
    changes it makes cannot leak, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "== ['a', 'b']" in s)
        mutated = source.replace("== ['a', 'b']", "== ['b', 'a']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
