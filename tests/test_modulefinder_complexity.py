"""Tests for docs/stdlib/modulefinder.md.

The page prices an analysis by the code it compiles and the names it looks
up: each new name is one search of the path, a name seen before is a dict
lookup, and every module found keeps its compiled code. Most of that is
settled by observation - a counting `modulefinder._find_module`, a counting
`FileFinder._fill_cache` and `FileFinder.invalidate_caches`, and identity
checks on what the finder holds - so no test here needs a tolerance. Every
analysis runs on modules written to a temporary directory, with `path`
restricted to it.

Measurement scope:

* `ModuleFinder()` keeps `sys.path` itself when `path` is omitted, and the
  given list by identity otherwise, and calls `_find_module` zero times.
* Analysis is static: a script that would write a file and exit does
  neither, an import inside a function that is never called and one inside
  `try`/`except ImportError` both reach `badmodules`, one under `if False:`
  does not, and a module named only in an `importlib.import_module()` call
  reaches neither dict.
* A script importing one found and one missing name three times each calls
  `_find_module` twice. A name in `excludes` and `sys` (a builtin) are never
  passed to it; `sys` is in `modules` with `__file__` and `__code__` `None`.
* Each lookup lists the directories it probes again: three new names over a
  five-directory path fill a directory cache 15 times, 3 x 5, where a cache
  kept for the run would fill it 5 times.
* Invalidation walks every cached path finder, and each package found adds
  one: counting `invalidate_caches()` on finders inside the temporary
  directory, 40 sibling packages (each with a submodule) cost more than 8x
  what 10 do, where invalidating a fixed set would cost 4x.
* The compiled code is kept: each source module's `Module.__code__` is a code
  object for its file, and a module of 20,000 assignments leaves a finder
  holding more than 20x the traced memory one of 100 assignments does. The
  directory listings are kept too: one small module beside 10,000 unrelated
  files leaves more than 20x the traced memory it does beside 10.
* A module star importing another has the other's `globalnames` among its
  own.
* A file with an extension-module suffix and a body that is not a valid
  extension is recorded with `__code__` `None` and never read.
* `import_hook()` raises `ImportError` for a missing name, leaves
  `badmodules` empty, and searches again when called again; with
  `fromlist=['*']` on a package it adds every module file in its directory
  and not a subpackage directory beside them.
  `load_file()` records the module under its file's stem.
* `modules` and `badmodules` are the dicts the finder fills, asserted by
  identity across an analysis.
* `any_missing_maybe()` puts a missing submodule of a package that star
  imports from a builtin in the maybe list, a name the package binds as a
  global in neither, and other missing names in the certain one, each
  sorted; `any_missing()` is their concatenation and leaves out `excludes`.
  `report()` prints modules sorted with `P` for a package, then each missing
  name with its sorted importers, the maybe name after the certain ones, and
  neither the excluded nor the global name.
* `globalnames`, `starimports` and `__path__` are asserted on a package and
  a plain module.
* `AddPackagePath()` and `ReplacePackage()` are asserted to change what a
  finder built after the call records, with the module-level dicts replaced
  for each test so no entry leaks.
* A 400-module chain of first-time imports raises `RecursionError` out of
  `run_script()` under a recursion limit of 1,000 and completes under
  20,000; a 50-module chain completes under 1,000.
* `python -m modulefinder script.py` prints the report's header and the
  modules it found.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(c) compile term and the O(e) directory-listing term are read from
  Lib/modulefinder.py (`compile()` of each source, `dis` scanning of each
  code object) and Lib/importlib/_bootstrap_external.py (`FileFinder`
  listing a directory on a cache miss); the tests count the calls, not the
  work inside them.
* The sorting terms of `any_missing()`, `any_missing_maybe()` and `report()`
  are read from Lib/modulefinder.py; their outputs are asserted sorted.
* The names star imports copy are a term of `c`; how many are copied is not
  varied. A package that tries to import one of its own globals as a
  submodule is reported certainly missing; that case is not exercised.
* The ModuleFinder methods other than those on the page - `add_module`,
  `determine_parent`, `ensure_fromlist`, `find_all_submodules`,
  `find_head_package`, `find_module`, `import_module`, `load_module`,
  `load_package`, `load_tail`, `msg`, `msgin`, `msgout`,
  `replace_paths_in_code`, `scan_code`, `scan_opcodes` - and the module's
  `test()` are the command line and the recursion's internals, absent from
  the official documentation, and are left off the page.
* Bytecode-only (`.pyc`) modules, whose bytes the page counts in `c`, zip
  archives, namespace packages, and
  `replace_paths` are not exercised. `excludes` and `replace_paths` are
  lists, scanned per lookup and per code object, and are not varied.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import io
import modulefinder
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
import types
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "modulefinder.md"
EXPECTED_BLOCKS = 5


def write_tree(root: pathlib.Path, files: dict[str, str]) -> None:
    """Write `files` (relative path to source) under `root`."""
    for relative, source in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")


def analyse(root: pathlib.Path, script: str, **kwargs: Any) -> modulefinder.ModuleFinder:
    """Run a finder restricted to `root` over `root / script`."""
    finder = modulefinder.ModuleFinder(path=[str(root)], **kwargs)
    finder.run_script(str(root / script))
    return finder


def record(finder: modulefinder.ModuleFinder, name: str) -> Any:
    """The `Module` for `name`; typeshed's stub omits its attributes."""
    return finder.modules[name]


@pytest.fixture
def lookups(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every name `modulefinder._find_module` is asked to search for."""
    names: list[str] = []
    original = getattr(modulefinder, "_find_module")  # noqa: B009

    def counting(name: str, path: Any = None) -> Any:
        names.append(name)
        return original(name, path)

    monkeypatch.setattr(modulefinder, "_find_module", counting)
    return names


@pytest.fixture
def fresh_package_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give AddPackagePath and ReplacePackage empty tables for one test."""
    monkeypatch.setattr(modulefinder, "packagePathMap", {})
    monkeypatch.setattr(modulefinder, "replacePackageMap", {})


class TestConstructionSearchesNothing:
    """`ModuleFinder(...)` | O(1) | O(1): `path` by reference, nothing searched."""

    def test_the_default_path_is_sys_path_itself(self, lookups: list[str]) -> None:
        finder = modulefinder.ModuleFinder()

        assert finder.path is sys.path
        assert finder.modules == {} and finder.badmodules == {}
        assert lookups == []

    def test_a_given_path_is_kept_not_copied(self) -> None:
        path = ["/nowhere"]

        assert modulefinder.ModuleFinder(path=path).path is path


class TestAnalysisIsStatic:
    """`run_script()` never executes the code it reads: every import statement in
    every code path is followed, and a run-time import is not seen."""

    def test_the_script_does_not_run(self, tmp_path: pathlib.Path) -> None:
        marker = tmp_path / "ran"
        write_tree(
            tmp_path,
            {"app.py": f"open({str(marker)!r}, 'w').close()\nraise SystemExit(3)\n"},
        )

        finder = analyse(tmp_path, "app.py")

        assert not marker.exists()
        assert "__main__" in finder.modules

    def test_every_import_statement_is_followed(self, tmp_path: pathlib.Path) -> None:
        write_tree(
            tmp_path,
            {
                "helper.py": "",
                "app.py": (
                    "import helper\n"
                    "def never_called():\n"
                    "    import lazy_dep\n"
                    "class K:\n"
                    "    def method(self):\n"
                    "        import deeper_dep\n"
                    "try:\n"
                    "    import optional_dep\n"
                    "except ImportError:\n"
                    "    pass\n"
                    "if False:\n"
                    "    import dropped\n"
                ),
            },
        )

        finder = analyse(tmp_path, "app.py")

        assert set(finder.modules) == {"__main__", "helper"}
        assert set(finder.badmodules) == {"lazy_dep", "deeper_dep", "optional_dep"}
        assert "dropped" not in finder.badmodules  # the compiler removed it

    def test_a_run_time_import_is_not_seen(self, tmp_path: pathlib.Path) -> None:
        write_tree(
            tmp_path,
            {
                "plugin.py": "",
                "app.py": "import importlib\nimportlib.import_module('plugin')\n"
                "__import__('plugin')\n",
            },
        )

        finder = analyse(tmp_path, "app.py")

        assert "plugin" not in finder.modules
        assert "plugin" not in finder.badmodules


class TestEachNewNameSearchesOnce:
    """A name already in `modules` or `badmodules` is a dict lookup; builtins
    and excluded names are never searched."""

    def test_repeated_imports_search_once(self, tmp_path: pathlib.Path, lookups: list[str]) -> None:
        write_tree(
            tmp_path,
            {"found.py": "", "app.py": "import found, absent\n" * 3},
        )

        finder = analyse(tmp_path, "app.py")

        assert sorted(lookups) == ["absent", "found"]
        assert "found" in finder.modules
        assert finder.badmodules == {"absent": {"__main__": 1}}

    def test_a_builtin_is_recorded_without_a_search(
        self, tmp_path: pathlib.Path, lookups: list[str]
    ) -> None:
        assert "sys" in sys.builtin_module_names
        write_tree(tmp_path, {"app.py": "import sys\n"})

        finder = analyse(tmp_path, "app.py")

        assert lookups == []
        assert record(finder, "sys").__file__ is None
        assert record(finder, "sys").__code__ is None

    def test_an_excluded_name_is_not_searched_or_reported(
        self, tmp_path: pathlib.Path, lookups: list[str]
    ) -> None:
        write_tree(tmp_path, {"heavy.py": "import deep\n", "app.py": "import heavy\n"})

        finder = analyse(tmp_path, "app.py", excludes=["heavy"])

        assert lookups == []
        assert "heavy" not in finder.modules
        assert "heavy" in finder.badmodules
        assert finder.any_missing() == []


class TestEveryLookupListsTheDirectoriesAgain:
    """Time O(c + u·(p + e)): the finder invalidates the import system's caches
    before each search, so each lookup re-lists what it probes, and each
    package directory searched adds a finder every later lookup invalidates."""

    def test_three_names_over_five_directories_fill_fifteen_caches(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        directories = [tmp_path / f"d{index}" for index in range(5)]
        for directory in directories:
            directory.mkdir()
        write_tree(directories[-1], {"a.py": "", "b.py": ""})
        write_tree(tmp_path, {"app.py": "import a\nimport b\nimport a\nimport missing\n"})
        watched = {str(directory) for directory in directories}
        fills: list[str] = []
        original = getattr(importlib.machinery.FileFinder, "_fill_cache")  # noqa: B009

        def counting(self: importlib.machinery.FileFinder) -> None:
            if self.path in watched:
                fills.append(self.path)
            original(self)

        monkeypatch.setattr(importlib.machinery.FileFinder, "_fill_cache", counting)

        finder = modulefinder.ModuleFinder(path=[str(d) for d in directories])
        finder.run_script(str(tmp_path / "app.py"))

        assert set(finder.modules) == {"__main__", "a", "b"}
        assert len(fills) == 15, f"3 lookups over 5 directories filled {len(fills)} caches"

    @staticmethod
    def invalidations(root: pathlib.Path, packages: int, monkeypatch: pytest.MonkeyPatch) -> int:
        files = {}
        for index in range(packages):
            files[f"p{index}/__init__.py"] = "from . import sub\n"
            files[f"p{index}/sub.py"] = ""
        files["app.py"] = "".join(f"import p{index}\n" for index in range(packages))
        write_tree(root, files)
        prefix = str(root)
        count = [0]
        original = importlib.machinery.FileFinder.invalidate_caches

        def counting(self: importlib.machinery.FileFinder) -> None:
            if self.path.startswith(prefix):
                count[0] += 1
            original(self)

        with monkeypatch.context() as patch:
            patch.setattr(importlib.machinery.FileFinder, "invalidate_caches", counting)
            finder = analyse(root, "app.py")
        assert len(finder.modules) == 2 * packages + 1
        return count[0]

    def test_invalidation_grows_with_the_packages_already_found(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "small").mkdir()
        (tmp_path / "large").mkdir()

        small = self.invalidations(tmp_path / "small", 10, monkeypatch)
        large = self.invalidations(tmp_path / "large", 40, monkeypatch)

        assert large > small * 8, (
            f"4x the packages invalidated {small} -> {large} finders; "
            "a fixed set of finders would give 4x"
        )


class TestTheFinderKeepsWhatItCompiles:
    """Space O(c + u + b): every module found keeps its compiled code."""

    def test_each_source_module_keeps_its_code(self, tmp_path: pathlib.Path) -> None:
        write_tree(
            tmp_path, {"pkg/__init__.py": "X = 1\n", "mod.py": "", "app.py": "import pkg, mod\n"}
        )

        finder = analyse(tmp_path, "app.py")

        for name, filename in [
            ("__main__", "app.py"),
            ("pkg", "pkg/__init__.py"),
            ("mod", "mod.py"),
        ]:
            code = record(finder, name).__code__
            assert isinstance(code, types.CodeType)
            assert code.co_filename == str(tmp_path / filename)

    @staticmethod
    def retained(root: pathlib.Path, assignments: int) -> int:
        body = "".join(f"name_{index} = {index}\n" for index in range(assignments))
        write_tree(root, {"big.py": body, "app.py": "import big\n"})
        tracemalloc.start()
        try:
            finder = analyse(root, "app.py")
            held = tracemalloc.get_traced_memory()[0]
        finally:
            tracemalloc.stop()
        assert len(record(finder, "big").globalnames) == assignments
        return held

    def test_retained_memory_follows_the_source(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "small").mkdir()
        (tmp_path / "large").mkdir()

        small = self.retained(tmp_path / "small", 100)
        large = self.retained(tmp_path / "large", 20_000)

        assert large > small * 20, f"200x the source left {small} -> {large} bytes held"

    @staticmethod
    def retained_with_listing(root: pathlib.Path, entries: int) -> int:
        write_tree(root, {"small.py": "", "app.py": "import small\n"})
        for index in range(entries):
            (root / f"unrelated_{index:05d}.txt").touch()
        tracemalloc.start()
        try:
            finder = analyse(root, "app.py")
            held = tracemalloc.get_traced_memory()[0]
        finally:
            tracemalloc.stop()
        assert "small" in finder.modules
        return held

    def test_retained_memory_follows_the_directories_listed(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "small").mkdir()
        (tmp_path / "large").mkdir()

        small = self.retained_with_listing(tmp_path / "small", 10)
        large = self.retained_with_listing(tmp_path / "large", 10_000)

        assert large > small * 20, f"1,000x the directory entries held {small} -> {large} bytes"

    def test_an_extension_module_is_recorded_but_not_read(self, tmp_path: pathlib.Path) -> None:
        suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
        (tmp_path / f"native{suffix}").write_bytes(b"not an extension module")
        write_tree(tmp_path, {"app.py": "import native\n"})

        finder = analyse(tmp_path, "app.py")

        native = record(finder, "native")
        assert native.__file__ == str(tmp_path / f"native{suffix}")
        assert native.__code__ is None


class TestEntryPoints:
    """`load_file()` and `import_hook()` share `run_script()`'s bounds; the
    result dicts are the finder's own."""

    def test_load_file_names_the_module_after_the_file(self, tmp_path: pathlib.Path) -> None:
        write_tree(tmp_path, {"tool.py": "import helper\n", "helper.py": ""})
        finder = modulefinder.ModuleFinder(path=[str(tmp_path)])

        finder.load_file(str(tmp_path / "tool.py"))

        assert set(finder.modules) == {"tool", "helper"}

    def test_import_hook_raises_for_a_missing_name_and_records_nothing(
        self, tmp_path: pathlib.Path, lookups: list[str]
    ) -> None:
        finder = modulefinder.ModuleFinder(path=[str(tmp_path)])

        for _ in range(2):
            with pytest.raises(ImportError):
                finder.import_hook("absent")

        assert finder.badmodules == {}
        assert lookups == ["absent", "absent"]

    def test_import_hook_star_imports_every_submodule(self, tmp_path: pathlib.Path) -> None:
        write_tree(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/one.py": "",
                "pkg/two.py": "",
                "pkg/child/__init__.py": "",
            },
        )
        finder = modulefinder.ModuleFinder(path=[str(tmp_path)])

        finder.import_hook("pkg", None, ["*"])

        # Module files directly in the directory; a subpackage directory is not one.
        assert set(finder.modules) == {"pkg", "pkg.one", "pkg.two"}

    def test_the_result_dicts_are_not_copies(self, tmp_path: pathlib.Path) -> None:
        write_tree(tmp_path, {"app.py": "import absent\n"})
        finder = modulefinder.ModuleFinder(path=[str(tmp_path)])
        modules, badmodules = finder.modules, finder.badmodules

        finder.run_script(str(tmp_path / "app.py"))

        assert finder.modules is modules and "__main__" in modules
        assert finder.badmodules is badmodules and "absent" in badmodules


class TestModuleRecords:
    """`Module.__path__`, `globalnames` and `starimports`."""

    def test_package_and_plain_module_attributes(self, tmp_path: pathlib.Path) -> None:
        write_tree(
            tmp_path,
            {
                "pkg/__init__.py": "from sys import *\nA = 1\n",
                "plain.py": "B = 2\ndef f():\n    global C\n    C = 3\n",
                "copier.py": "from plain import *\n",
                "app.py": "import pkg, plain, copier\n",
            },
        )

        finder = analyse(tmp_path, "app.py")

        pkg, plain = record(finder, "pkg"), record(finder, "plain")
        assert pkg.__path__ == [str(tmp_path / "pkg")]
        assert plain.__path__ is None
        assert "A" in pkg.globalnames
        assert pkg.starimports == {"sys": 1}
        assert {"B", "f"} <= set(plain.globalnames)
        assert plain.starimports == {}
        assert set(plain.globalnames) <= set(record(finder, "copier").globalnames)
        assert isinstance(pkg, modulefinder.Module)


class TestMissingModules:
    """`any_missing()`, `any_missing_maybe()` and `report()`."""

    FILES = {
        "pkg/__init__.py": "from sys import *\n",
        "plain/__init__.py": "DEFINED = 1\n",
        "app.py": (
            "from pkg import maybe_here\n"
            "from plain import not_here, DEFINED\n"
            "import zebra, apple\n"
            "import skipped\n"
        ),
    }

    def test_maybe_is_a_name_under_an_unresolved_star_import(self, tmp_path: pathlib.Path) -> None:
        write_tree(tmp_path, self.FILES)

        finder = analyse(tmp_path, "app.py", excludes=["skipped"])

        missing, maybe = finder.any_missing_maybe()
        assert missing == ["apple", "plain.not_here", "zebra"]
        assert maybe == ["pkg.maybe_here"]
        assert finder.any_missing() == missing + maybe
        assert "skipped" in finder.badmodules
        assert "plain.DEFINED" in finder.badmodules  # a global, so in neither list

    def test_report_lists_modules_then_missing_names_sorted(self, tmp_path: pathlib.Path) -> None:
        write_tree(tmp_path, {**self.FILES, "other.py": "import zebra\n"})
        write_tree(tmp_path, {"app.py": self.FILES["app.py"] + "import other\n"})
        finder = analyse(tmp_path, "app.py", excludes=["skipped"])
        out = io.StringIO()

        with contextlib.redirect_stdout(out):
            finder.report()

        lines = [line for line in out.getvalue().splitlines() if line]
        found = [line.split()[1] for line in lines if line[:2] in ("P ", "m ")]
        assert found == sorted(finder.modules)
        assert "P pkg" in "\n".join(lines)
        assert "? zebra imported from __main__, other" in lines
        assert "? pkg.maybe_here imported from __main__" in lines
        assert lines.index("? zebra imported from __main__, other") < lines.index(
            "? pkg.maybe_here imported from __main__"
        )
        assert not any("skipped" in line or "DEFINED" in line for line in lines)
        assert lines.index("? apple imported from __main__") < lines.index(
            "? zebra imported from __main__, other"
        )


@pytest.mark.usefixtures("fresh_package_maps")
class TestProcessWidePackageTables:
    """`AddPackagePath()` and `ReplacePackage()` write module-level tables that
    every finder built afterwards consults."""

    def test_add_package_path_extends_a_later_finder_s_search(self, tmp_path: pathlib.Path) -> None:
        write_tree(
            tmp_path,
            {"pkg/__init__.py": "", "extra/plugin.py": "", "app.py": "from pkg import plugin\n"},
        )
        assert "pkg.plugin" in analyse(tmp_path, "app.py").badmodules

        modulefinder.AddPackagePath("pkg", str(tmp_path / "extra"))
        finder = analyse(tmp_path, "app.py")

        assert "pkg.plugin" in finder.modules
        assert modulefinder.packagePathMap == {"pkg": [str(tmp_path / "extra")]}

    def test_replace_package_records_it_under_the_new_name(self, tmp_path: pathlib.Path) -> None:
        write_tree(tmp_path, {"real/__init__.py": "", "app.py": "import real\n"})

        modulefinder.ReplacePackage("real", "alias")
        finder = analyse(tmp_path, "app.py")

        assert "alias" in finder.modules
        assert "real" not in finder.modules
        assert modulefinder.replacePackageMap == {"real": "alias"}


class TestDeepChainsExhaustTheStack:
    """The search recurses once per first-time import, so a long chain raises
    `RecursionError` out of `run_script()` instead of being recorded."""

    @pytest.fixture
    def recursion_limit(self) -> Iterator[Callable[[int], None]]:
        original = sys.getrecursionlimit()
        yield sys.setrecursionlimit
        sys.setrecursionlimit(original)

    @staticmethod
    def chain(root: pathlib.Path, depth: int) -> None:
        files = {
            f"m{index}.py": f"import m{index + 1}\n" if index + 1 < depth else ""
            for index in range(depth)
        }
        files["app.py"] = "import m0\n"
        write_tree(root, files)

    def test_a_long_chain_raises(
        self, tmp_path: pathlib.Path, recursion_limit: Callable[[int], None]
    ) -> None:
        self.chain(tmp_path, 400)
        recursion_limit(1_000)

        with pytest.raises(RecursionError):
            analyse(tmp_path, "app.py")

    def test_a_short_chain_or_a_higher_limit_completes(
        self, tmp_path: pathlib.Path, recursion_limit: Callable[[int], None]
    ) -> None:
        (tmp_path / "short").mkdir()
        (tmp_path / "long").mkdir()
        self.chain(tmp_path / "short", 50)
        self.chain(tmp_path / "long", 400)

        recursion_limit(1_000)
        assert len(analyse(tmp_path / "short", "app.py").modules) == 51
        recursion_limit(20_000)
        assert len(analyse(tmp_path / "long", "app.py").modules) == 401


class TestCommandLine:
    """`python -m modulefinder script.py` prints the report."""

    def test_it_prints_the_modules_found(self, tmp_path: pathlib.Path) -> None:
        write_tree(tmp_path, {"helper.py": "", "app.py": "import helper\n"})

        result = subprocess.run(
            [sys.executable, "-m", "modulefinder", str(tmp_path / "app.py")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=True,
        )

        assert "Name" in result.stdout and "File" in result.stdout
        assert re.search(r"^m helper\s+\S*helper\.py$", result.stdout, re.MULTILINE)


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
    """Each block runs in its own subprocess, so a package table or recursion
    limit it changes cannot leak into another, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "'plugin' not in" in s)
        mutated = source.replace("'plugin' not in", "'plugin' in", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
