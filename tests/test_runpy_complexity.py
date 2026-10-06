"""Tests for docs/stdlib/runpy.md.

The page prices `runpy` as a loader that caches nothing: every call finds,
loads and executes the code again, compiling a script from source each time
and loading cached bytecode only where the import system supplies it. Those
claims are settled by observation - a counter the executed code appends to, a
counting `compile` and `source_to_code`, the contents of `__pycache__`, and
identity checks on the returned dictionary. The O(s) growth in the size of the
code is settled by traced allocation and a timing ratio.

Measurement scope:

* Re-execution: a module run twice through `run_module()` appends to an
  `init_globals` list twice, returns two distinct dictionaries, and is absent
  from `sys.modules` afterwards. For a dotted name, the parent package's
  `__init__` writes one line to a log over two runs and the package stays in
  `sys.modules`. A package name runs `<package>.__main__`.
* Bytecode: with `sys.dont_write_bytecode` false, `run_module()` calls
  `SourceFileLoader.source_to_code` once over two runs of an unchanged module,
  and `run_path()` on a directory does the same for its `__main__.py`, leaving
  a `__pycache__` entry. `run_path()` on a `.py` file calls `compile` (patched
  on the `runpy` module) on every one of three runs and creates no
  `__pycache__`. A directory and a zip file holding only `__main__.py` are
  run with their path at `sys.path[0]` during the run and absent from
  `sys.path` afterwards; whether zipimport compiles on every call is not
  asserted. `sys.pycache_prefix` is held at `None` for these tests.
* `sys` swapping: inside `run_module(..., alter_sys=True)` and `run_path()`
  on a `.py` file, `sys.argv[0]` is the file being run and `sys.modules[run_name]` is the
  module whose `__dict__` is the code's globals; after the call both are
  restored, a pre-existing `sys.modules` entry under `run_name` included.
  The returned dictionary is not the globals the code saw. Without
  `alter_sys`, `sys.modules` has no entry for the module during the run, and
  the returned dictionary is the globals the code saw. `init_globals`
  entries are visible to the code and in the result.
* O(s): the code is a function definition whose body is n assignment lines,
  so the source and bytecode grow with n while the globals and the executed
  top-level work stay fixed. `run_path()`'s traced peak grows by between 5x
  and 30x per 10x step over 200, 2,000 and 20,000 lines, and in a timing
  test its time grows by between 4x and 30x per 10x step over 500, 5,000
  and 50,000 lines: a constant would give about 1x and a quadratic about
  100x. `run_module()` on cached bytecode peaks between 3x and 30x higher at
  50,000 lines than at 5,000; its time is not measured.
* Every fenced Python block runs in its own subprocess and working directory,
  so `sys.argv`, `sys.path` and `sys.modules` changes cannot leak between
  them or into this process, and a mutated assertion in one of them is
  asserted to fail.

Not settled here:

* `f`, the import system's search for a module name, is priced and tested on
  docs/stdlib/importlib.md; this file does not vary `sys.path`.
* The O(i) `init_globals` update and the O(g) copy of the globals on
  `alter_sys=True` and `run_path()` are read from Lib/runpy.py
  (`run_globals.update(init_globals)`, `mod_globals.copy()` and
  `_run_code(...).copy()`); the tests show the result is a different
  dictionary, not how either cost grows. The O(p) insertion into a
  `sys.path` of p entries for a directory or zip file is not priced: it is
  a single list insert.
* That neither `run_path()` nor `alter_sys=True` is thread-safe is the
  official documentation's statement; the tests show the process-wide swap
  that causes it, not a race.
* Source encodings, `.pyc` files passed straight to `run_path()`, namespace
  packages and the `RuntimeWarning` for a module already imported under its
  own name are not exercised.
"""

from __future__ import annotations

import importlib.machinery
import pathlib
import re
import runpy
import subprocess
import sys
import textwrap
import time
import tracemalloc
import uuid
import zipfile
import zipimport
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "runpy.md"
EXPECTED_BLOCKS = 5


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def code_of_lines(lines: int) -> str:
    """Source whose size grows with `lines` while its globals and top-level work do not."""
    return "def f():\n" + "    a = 1\n" * lines + "x = 1\n"


class ModuleDir:
    """A temporary directory on `sys.path` for modules with unique names."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.prefix = f"runpy_probe_{uuid.uuid4().hex[:12]}"

    def name(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}"

    def write(self, relative: str, source: str) -> pathlib.Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        importlib.invalidate_caches()
        return path


@pytest.fixture(autouse=True)
def isolated_import_state(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Hold `sys.pycache_prefix` at None, and drop the importer cache entries
    this test's temporary paths created, so nothing outlives the test."""
    monkeypatch.setattr(sys, "pycache_prefix", None)
    yield
    root = str(tmp_path)
    for key in [key for key in sys.path_importer_cache if str(key).startswith(root)]:
        del sys.path_importer_cache[key]
    zip_cache: dict[str, Any] = vars(zipimport)["_zip_directory_cache"]
    for key in [key for key in zip_cache if key.startswith(root)]:
        del zip_cache[key]


@pytest.fixture
def modules(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleDir]:
    """Modules importable for one test; anything imported under its prefix is
    removed from `sys.modules` afterwards."""
    monkeypatch.syspath_prepend(str(tmp_path))
    directory = ModuleDir(tmp_path)
    yield directory
    for key in [key for key in sys.modules if key.startswith(directory.prefix)]:
        del sys.modules[key]


@pytest.fixture
def counting_source_to_code(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every source compile the import system's file loader makes."""
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    compiled: list[str] = []
    original = importlib.machinery.SourceFileLoader.source_to_code

    def counting(self: Any, data: Any, path: Any, *args: Any, **kwargs: Any) -> Any:
        compiled.append(str(path))
        return original(self, data, path, *args, **kwargs)

    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "source_to_code", counting)
    return compiled


class TestRunModuleExecutesAfresh:
    """`run_module()`: the module itself is executed on every call and never
    added to `sys.modules`; only its parent packages are imported."""

    def test_each_call_executes_the_body_again(self, modules: ModuleDir) -> None:
        name = modules.name("task")
        modules.write(f"{name}.py", "calls.append(__name__)\nresult = 42\n")
        calls: list[str] = []

        first = runpy.run_module(name, {"calls": calls})
        second = runpy.run_module(name, {"calls": calls})

        assert calls == [name, name]
        assert first is not second
        assert first["result"] == second["result"] == 42
        assert name not in sys.modules

    def test_parent_packages_are_imported_once_and_kept(self, modules: ModuleDir) -> None:
        package = modules.name("pkg")
        log = modules.root / "init.log"
        modules.write(
            f"{package}/__init__.py",
            f"with open({str(log)!r}, 'a') as f:\n    f.write('init\\n')\n",
        )
        modules.write(f"{package}/task.py", "calls.append(1)\n")
        calls: list[int] = []

        runpy.run_module(f"{package}.task", {"calls": calls})
        runpy.run_module(f"{package}.task", {"calls": calls})

        assert calls == [1, 1]
        assert log.read_text().splitlines() == ["init"]
        assert package in sys.modules
        assert f"{package}.task" not in sys.modules

    def test_a_package_runs_its_main_submodule(self, modules: ModuleDir) -> None:
        package = modules.name("app")
        modules.write(f"{package}/__init__.py", "")
        modules.write(f"{package}/__main__.py", "ran = __name__\n")

        result = runpy.run_module(package)

        assert result["ran"] == f"{package}.__main__"


class TestCachedBytecode:
    """`run_module()` and a directory given to `run_path()` load cached
    bytecode once it is current; a `.py` file given to `run_path()` is
    compiled on every call and writes none."""

    def test_run_module_compiles_an_unchanged_module_once(
        self, modules: ModuleDir, counting_source_to_code: list[str]
    ) -> None:
        name = modules.name("cached")
        path = modules.write(f"{name}.py", "value = 1\n")

        runpy.run_module(name)
        runpy.run_module(name)

        assert counting_source_to_code == [str(path)]
        assert any((modules.root / "__pycache__").iterdir())

    def test_run_path_compiles_a_script_every_time(
        self, modules: ModuleDir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
        script = modules.write("script.py", "value = 1\n")
        compiled: list[str] = []

        def counting_compile(source: Any, filename: Any, *args: Any, **kwargs: Any) -> Any:
            compiled.append(str(filename))
            return compile(source, filename, *args, **kwargs)

        monkeypatch.setattr(runpy, "compile", counting_compile, raising=False)

        for _ in range(3):
            assert runpy.run_path(str(script))["value"] == 1

        assert compiled == [str(script)] * 3
        assert not (modules.root / "__pycache__").exists()

    def test_run_path_on_a_directory_reuses_its_pycache_from_the_front_of_sys_path(
        self, tmp_path: pathlib.Path, counting_source_to_code: list[str]
    ) -> None:
        app = tmp_path / "app"
        app.mkdir()
        main = app / "__main__.py"
        main.write_text("import sys\nvalue = 1\nfirst = sys.path[0]\n", encoding="utf-8")

        assert runpy.run_path(str(app))["first"] == str(app)
        assert runpy.run_path(str(app))["value"] == 1

        assert counting_source_to_code == [str(main)]
        assert any((app / "__pycache__").iterdir())
        assert str(app) not in sys.path

    def test_run_path_runs_a_zip_files_main_from_the_front_of_sys_path(
        self, tmp_path: pathlib.Path
    ) -> None:
        archive = tmp_path / "app.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("__main__.py", "import sys\nvalue = __name__\nfirst = sys.path[0]\n")

        result = runpy.run_path(str(archive), run_name="__main__")

        assert result["value"] == "__main__"
        assert result["first"] == str(archive)
        assert str(archive) not in sys.path


PROBE = (
    "import sys\n"
    "argv0 = sys.argv[0]\n"
    "entry = sys.modules.get(__name__)\n"
    "registered = getattr(entry, '__dict__', None) is globals()\n"
    "namespace = globals()\n"
    "seen_init = init_value\n"
)


class TestSysIsSwappedAndRestored:
    """`alter_sys=True` and `run_path()` point `sys.argv[0]` and
    `sys.modules[run_name]` at the running code, restore both, and return a
    copy of the globals; plain `run_module()` returns the namespace itself."""

    def test_alter_sys_swaps_both_and_returns_a_copy(self, modules: ModuleDir) -> None:
        name = modules.name("probe")
        path = modules.write(f"{name}.py", PROBE)
        saved_argv0 = sys.argv[0]

        result = runpy.run_module(name, {"init_value": 7}, alter_sys=True)

        assert result["argv0"] == str(path)
        assert result["registered"] is True
        assert result["namespace"] is not result
        assert result["seen_init"] == result["init_value"] == 7
        assert sys.argv[0] == saved_argv0
        assert name not in sys.modules

    def test_without_alter_sys_nothing_is_swapped_and_the_namespace_is_returned(
        self, modules: ModuleDir
    ) -> None:
        name = modules.name("plain")
        modules.write(f"{name}.py", PROBE)
        saved_argv0 = sys.argv[0]

        result = runpy.run_module(name, {"init_value": 7})

        assert result["argv0"] == saved_argv0
        assert result["entry"] is None
        assert result["namespace"] is result
        assert result["seen_init"] == 7

    def test_run_path_swaps_both_and_restores_an_existing_entry(
        self, modules: ModuleDir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script = modules.write("probe.py", PROBE)
        run_name = modules.name("existing")
        sentinel = type(sys)(run_name)
        monkeypatch.setitem(sys.modules, run_name, sentinel)
        saved_argv0 = sys.argv[0]

        result = runpy.run_path(str(script), {"init_value": 7}, run_name=run_name)

        assert result["argv0"] == str(script)
        assert result["registered"] is True
        assert result["entry"] is not sentinel
        assert result["namespace"] is not result
        assert sys.modules[run_name] is sentinel
        assert sys.argv[0] == saved_argv0

    def test_run_path_names_the_code_run_path_by_default(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "script.py"
        script.write_text("name = __name__\n", encoding="utf-8")

        assert runpy.run_path(str(script))["name"] == "<run_path>"
        assert "<run_path>" not in sys.modules


class TestCostFollowsTheCode:
    """O(s) in both functions: the code grows while the globals and the
    executed top-level work stay fixed."""

    def test_run_path_peak_grows_with_the_source(self, tmp_path: pathlib.Path) -> None:
        peaks: dict[int, int] = {}
        for lines in (200, 2_000, 20_000):
            script = tmp_path / f"script{lines}.py"
            script.write_text(code_of_lines(lines), encoding="utf-8")
            peaks[lines] = peak_bytes(lambda script=script: runpy.run_path(str(script)))

        for small, large in ((200, 2_000), (2_000, 20_000)):
            ratio = peaks[large] / peaks[small]
            assert 5 < ratio < 30, (
                f"10x the source ({small} to {large} lines) peaked x{ratio:.1f} higher; "
                f"linear predicts about 10, constant 1 and quadratic 100: {peaks}"
            )

    @pytest.mark.timing
    def test_run_path_time_grows_linearly_with_the_source(self, tmp_path: pathlib.Path) -> None:
        times: dict[int, float] = {}
        for lines in (500, 5_000, 50_000):
            script = tmp_path / f"script{lines}.py"
            script.write_text(code_of_lines(lines), encoding="utf-8")
            times[lines] = best_ns(lambda script=script: runpy.run_path(str(script)))

        for small, large in ((500, 5_000), (5_000, 50_000)):
            ratio = times[large] / times[small]
            assert 4 < ratio < 30, (
                f"10x the source ({small} to {large} lines) cost x{ratio:.1f}; "
                "linear predicts about 10, constant 1 and quadratic 100"
            )

    def test_run_module_peak_grows_with_cached_bytecode(
        self, modules: ModuleDir, counting_source_to_code: list[str]
    ) -> None:
        peaks: dict[int, int] = {}
        for lines in (5_000, 50_000):
            name = modules.name(f"big{lines}")
            modules.write(f"{name}.py", code_of_lines(lines))
            runpy.run_module(name)
            peaks[lines] = peak_bytes(lambda name=name: runpy.run_module(name))

        assert len(counting_source_to_code) == 2, "the measured runs loaded bytecode"
        ratio = peaks[50_000] / peaks[5_000]
        assert 3 < ratio < 30, f"10x the bytecode peaked x{ratio:.1f} higher: {peaks}"


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
    """Each block runs in its own subprocess, so the `sys.argv`, `sys.path`
    and `sys.modules` changes the examples make cannot reach this process, and
    asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert calls ==" in s)
        mutated = source.replace(
            "assert calls == ['runpy_demo_pkg.task', 'runpy_demo_pkg.task']",
            "assert calls == ['runpy_demo_pkg.task']",
            1,
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
