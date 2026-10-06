"""Tests for docs/stdlib/distutils.md.

The package exists on Python 3.10 and 3.11 only, so the in-process tests take
the `du` fixture, which skips from 3.12; run them with one of those
interpreters. The tests that run distutils in a subprocess check the version
themselves. The fixture imports the standard library's copy: an environment
can carry a site-packages `.pth` hook that substitutes another `distutils` for
the import, so the fixture imports with only the interpreter's own finders on
`sys.meta_path`, checks that the package came from the standard library
directory, and puts the previous modules back afterwards. The page's examples
run with `-S` for the same reason. Lib/distutils differs between v3.10.19 and
v3.11.14 in the removal of `command/bdist_msi.py` and in edits that move no
bound.

Almost every row is settled by observation: a recording `spawn` stands in for
the compiler, linker and archiver and counts their runs, a wrapped
`_copy_file_contents` counts the files copied, a counting `os.stat`,
`os.path.exists`, `os.path.isfile` or `os.mkdir` counts filesystem calls, a
`str` subclass counts the comparisons made against it, and identity checks
settle which objects are shared. Four bounds that are quadratic in a word,
line or argument count are covered by copied-character counts and three timings.

Measurement scope:

* `setup()` named a counting command twice and ran it once;
  `Distribution.run_command()` skips a command that has run until
  `reinitialize_command()`; `run_setup()` with `stop_after` of `"init"`,
  `"config"` and `"commandline"` runs no command; `Extension` keeps the
  `sources` list it is given. Constructing the base `Command`, calling a
  subclass's missing `run()`, and calling the base `initialize_options()` and
  `finalize_options()` raise `RuntimeError`; `get_sub_commands()` calls every
  predicate once.
* An `install` of two modules, a package header, a script and a data file
  into a temporary prefix copies files into the build tree and the prefix on
  the first run, none on a second (and leaves the script `build_scripts`
  rewrote untouched), and with `--force` exactly the files under the prefix
  again, since `--force` reaches the install commands and not `build`. That
  covers `build`, `build_py`, `build_scripts`, `install_lib`,
  `install_headers`, `install_scripts` and `install_data`. `build_py_2to3` hands 2to3 the modules a run copied and none
  on a second run.
* `build_ext` with a recording `spawn` compiles and links once, makes no run
  when the output is newer than its sources and `depends`, makes no run when
  a header outside `depends` changes, and compiles and links again when a
  header in `depends` changes. `build_clib` runs the compiler on every run and
  the archiver only while the library is older than its objects.
* `clean` removes the temporary tree and keeps `build_lib`; `clean --all`
  removes it too. `sdist` with 3 `include` lines over trees of 20 and 200
  files matches each pattern against every file: 3 x 21 and 3 x 201 regex
  searches, the tree holding MANIFEST.in as well. `bdist_dumb` installs into
  a temporary tree and hands that tree to `make_archive()`. `check` without
  `--restructuredtext` warns about missing metadata. `config` makes 1,
  2 and 3 runs for `try_compile()`, `try_link()` and `try_run()`.
* `CCompiler`: `define_macro()` makes one comparison per macro already set (10
  and 1,000) and replaces an earlier entry; the `set_*` methods store copies;
  `compile()` runs once per source on every call, with objects newer than
  every source and an older header in `depends`;
  `create_static_lib()` and `link_executable()` skip a run while the output is
  newer than every object and `force=1` links anyway; `UnixCCompiler.preprocess`
  skips a run while `output_file` is newer; `has_function()` runs the compiler
  twice; `find_library_file()` makes 4 existence checks per directory over 10
  and 100 directories and stops at the first that holds the library;
  `gen_lib_options()` looks up a library with a directory part through
  `find_library_file()`; the filename helpers make no `stat` call.
  `new_compiler()` returns the class defaults until
  `customize_compiler()`, which takes `CC` from the environment. On a
  `dry_run` compiler `spawn()`, `mkpath()` and `move_file()` do nothing and
  `execute()` still calls its function.
* `newer()` ignores a difference within one second; `newer_group()` never
  stats the sources after the first newer one. `copy_file()` of 8 MiB peaks
  under 256 KiB of traced allocation, `update=1` copies nothing for an
  up-to-date target, `link='hard'` shares the inode, and a hard link that
  fails is copied instead. `move_file()` renames
  on one filesystem and copies and deletes after `EXDEV`.
* `mkpath()` makes one `mkdir` per missing component (5), remembers what it
  made until `remove_tree()`; `create_tree()` makes one `mkpath()` per
  distinct directory, sorted; `copy_tree(update=1)` returns every name but a
  `.nfs` one, which it does not copy, and copies nothing the second time; `remove_tree()` lists the whole tree before
  its first removal and logs a failed one. `make_archive()` runs the format
  function with the working directory at `root_dir` and restores it;
  `compress="compress"` runs the external program; the tar and zip archives
  hold the tree's files.
* `util`: `convert_path()` returns its argument on POSIX; `check_environ()`
  sets `PLAT` once per process; `subst_vars()` raises `ValueError` for an
  unknown name; `byte_compile()` compiles each stale file once, nothing when
  up to date, everything with `force`, and spawns an interpreter when
  `optimize` is set unless `direct=1`. A `str` subclass preserves instrumentation
  across slices and whitespace stripping: `split_quoted()` slices a total of
  w² characters for w = 10, 100 and 1,000 one-letter words separated by spaces.
  Word width, quotes and escapes are not varied in that count.
  `wrap_text()` over 1,000 and 10,000 words at width 10,
  `TextFile.readline()` joining 1,000 and 10,000 continuation lines of 40
  characters, and `FancyGetopt.getopt()` over 1,000 and 10,000 copies of one
  long option take more than 25x the time for 10x the input: about 100x is
  quadratic, 10x linear.
* `FancyGetopt.getopt()` with 5 long arguments over 10 and 100 options calls
  `startswith` on every option once per argument; `get_option_order()` is the
  parser's own list and grows across calls; `generate_help()` calls
  `wrap_text()` once per option.
* A `str` operand of a version comparison is parsed once per comparison and
  a version operand not at all; `LooseVersion` raises `TypeError` for a number
  against letters. `distutils.log` formats its arguments only at or above the
  threshold. `find_executable()` checks the name itself and then one path per
  directory (10 and 100). `spawn()` raises `DistutilsExecError` for a non-zero
  exit. The `distutils.sysconfig` functions are `sysconfig`'s own, and
  `get_python_inc()` and `get_python_lib()` make no `stat` call. `FileList.include_pattern()` searches every file once and
  `exclude_pattern()` deletes once per file removed.
* The import warns on 3.10 and 3.11 and raises `ModuleNotFoundError` from 3.12
  without site-packages. `bdist_msi` ships in 3.10 only, and neither version
  ships `bdist_packager` or defines `sysconfig.set_python_build`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The deprecation in 3.10 and the removal in 3.12 come from PEP 632.
* `register` needs a package index, `bdist_rpm` needs `rpmbuild`, and the
  `"compress"` archive format needs the `compress` program; only the call is
  observed. `bdist_msi` needs `msilib`, which exists on Windows only, and
  `msvc9compiler` needs `winreg`; neither is imported on Linux, and CI runs
  these tests on no interpreter that has them.
* `check --restructuredtext` needs a reStructuredText parser that is not in
  the standard library.
* Source-only, from Lib/distutils on v3.11.14: `Distribution(attrs)` loops
  once over `attrs` and its `options`, and splits `keywords` and
  `platforms` on commas; `Extension` checks the type of every
  source; `create_tree()` sorts its directory set; `copy_tree()` extends each
  directory's result list with its children's, so a name is copied once per
  directory above it; `sdist` keeps one file-list entry per match until it
  sorts and deduplicates, and deletes each excluded or duplicate entry from
  that list; `TarFile.add()` sorts each directory's listing; the
  copying commands hold their list of output names plus one file
  (`build_scripts` reads the rest of a script whose `#!` line it rewrites);
  `make_tarball()` and `make_zipfile()` keep one member record per entry;
  `byte_compile()` holds one source at a time, and in a new interpreter first
  writes a script listing the files; `register` builds its request body and
  reads responses in memory; `has_function()` and `spawn()` build option and `PATH` lists.
* Not varied: path length and depth beyond the counts above, file sizes in the
  command runs, compilers other than `UnixCCompiler`, and the cost of the
  programs `spawn()` runs.
"""

from __future__ import annotations

import errno
import gc
import importlib
import importlib.machinery
import importlib.util
import io
import os
import pathlib
import re
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import textwrap
import time
import tracemalloc
import types
import warnings
import zipfile
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "distutils.md"
EXPECTED_BLOCKS = 5
STDLIB = pathlib.Path(sysconfig.get_paths()["stdlib"])
HAS_DISTUTILS = sys.version_info < (3, 12)
# `install` passes an argument `sysconfig` deprecates; the warning is about
# distutils' own call, not about anything a test does.
pytestmark = pytest.mark.filterwarnings("ignore:check_home argument:DeprecationWarning")
OWN_FINDERS = (
    importlib.machinery.BuiltinImporter,
    importlib.machinery.FrozenImporter,
    importlib.machinery.PathFinder,
)
SUBMODULES = (
    "archive_util",
    "bcppcompiler",
    "ccompiler",
    "cmd",
    "core",
    "cygwinccompiler",
    "debug",
    "dep_util",
    "dir_util",
    "dist",
    "errors",
    "extension",
    "fancy_getopt",
    "file_util",
    "filelist",
    "log",
    "msvccompiler",
    "spawn",
    "sysconfig",
    "text_file",
    "unixccompiler",
    "util",
    "version",
    "command.bdist",
    "command.bdist_dumb",
    "command.build",
    "command.build_clib",
    "command.build_ext",
    "command.build_py",
    "command.build_scripts",
    "command.check",
    "command.clean",
    "command.config",
    "command.install",
    "command.install_data",
    "command.install_egg_info",
    "command.install_headers",
    "command.install_lib",
    "command.install_scripts",
    "command.sdist",
)


def _is_distutils(name: str) -> bool:
    return name == "distutils" or name.startswith("distutils.")


@pytest.fixture(scope="module")
def du() -> Iterator[Any]:
    """The standard library's distutils, as a namespace of its submodules."""
    if not HAS_DISTUTILS:
        pytest.skip("version: distutils was removed in Python 3.12")
    saved_modules = {name: mod for name, mod in sys.modules.items() if _is_distutils(name)}
    saved_finders = sys.meta_path[:]
    for name in saved_modules:
        del sys.modules[name]
    sys.meta_path[:] = [f for f in saved_finders if f in OWN_FINDERS]
    namespace = types.SimpleNamespace()
    try:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                package = importlib.import_module("distutils")
                for sub in SUBMODULES:
                    module = importlib.import_module(f"distutils.{sub}")
                    setattr(namespace, sub.replace("command.", "cmd_"), module)
        finally:
            sys.meta_path[:] = saved_finders
        assert pathlib.Path(str(package.__file__)).parent == STDLIB / "distutils"
        namespace.package = package
        yield namespace
    finally:
        for name in [name for name in sys.modules if _is_distutils(name)]:
            del sys.modules[name]
        sys.modules.update(saved_modules)


class Spawns:
    """A recording `spawn`: keeps each command and creates its `-o` output.

    `ranlib`, which `UnixCCompiler` runs after the archiver on macOS only, is
    not recorded, so the counts are the same on every platform.
    """

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, cmd: list[str], *args: Any, **kwargs: Any) -> None:
        if os.path.basename(cmd[0]) == "ranlib":
            return
        self.commands.append(list(cmd))
        if "-o" in cmd:
            target = pathlib.Path(cmd[cmd.index("-o") + 1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()

    def __len__(self) -> int:
        return len(self.commands)


def set_mtime(path: pathlib.Path | str, seconds: int) -> None:
    os.utime(path, (seconds, seconds))


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, with the collector held off."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


def fastest(func: Callable[[], Any], repeat: int = 3) -> float:
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        best = min(best, time.perf_counter() - start)
    return best


def copy_counter(du: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Wrap the one function every distutils file copy goes through."""
    copied: list[str] = []
    original = du.file_util._copy_file_contents

    def counting(src: str, dst: str, buffer_size: int = 16 * 1024) -> None:
        copied.append(dst)
        original(src, dst, buffer_size)

    monkeypatch.setattr(du.file_util, "_copy_file_contents", counting)
    return copied


def forbid_stat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any stat, and so any existence check, fail the test."""

    def refuse(path: Any, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"stat({path!r})")

    monkeypatch.setattr(os, "stat", refuse)
    monkeypatch.setattr(os, "lstat", refuse)


def write(path: pathlib.Path, text: str = "x = 1\n") -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_python(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-S", *args],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
        env=env,
    )


class TestAvailability:
    """The package ships with 3.10 and 3.11, warns on import, and is gone from
    3.12; the rows marked as absent name modules and functions that do not
    exist."""

    def test_the_package_ships_only_before_3_12(self) -> None:
        assert (STDLIB / "distutils" / "__init__.py").is_file() == HAS_DISTUTILS

    @pytest.mark.skipif(HAS_DISTUTILS, reason="distutils exists before 3.12")
    def test_importing_it_from_3_12_raises(self) -> None:
        result = run_python("-c", "import distutils")
        assert result.returncode != 0
        assert "ModuleNotFoundError" in result.stderr

    @pytest.mark.skipif(not HAS_DISTUTILS, reason="distutils was removed in 3.12")
    def test_importing_it_warns(self) -> None:
        result = run_python("-W", "error::DeprecationWarning", "-c", "import distutils")
        assert result.returncode != 0
        assert "DeprecationWarning" in result.stderr
        assert "distutils" in result.stderr

    @pytest.mark.skipif(not HAS_DISTUTILS, reason="distutils was removed in 3.12")
    def test_bdist_msi_ships_in_3_10_only(self) -> None:
        shipped = (STDLIB / "distutils" / "command" / "bdist_msi.py").is_file()
        assert shipped == (sys.version_info < (3, 11))

    def test_documented_names_that_do_not_exist(self, du: Any) -> None:
        assert not (STDLIB / "distutils" / "command" / "bdist_packager.py").exists()
        assert not hasattr(du.sysconfig, "set_python_build")


class TestSetupRunsEachCommandOnce:
    """`setup()` | O(c) command runs; `run_setup()` stops before any command
    for `stop_after` other than "run"; `Distribution.run_command()` skips a
    command that has run."""

    @staticmethod
    def counting_command(du: Any, runs: list[str]) -> type:
        class Count(du.cmd.Command):
            user_options: list[Any] = []

            def initialize_options(self) -> None:
                pass

            def finalize_options(self) -> None:
                pass

            def run(self) -> None:
                runs.append("count")

        return Count

    def test_a_command_named_twice_runs_once(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        runs: list[str] = []
        du.core.setup(
            name="demo",
            script_name="setup.py",
            script_args=["count", "count"],
            cmdclass={"count": self.counting_command(du, runs)},
        )
        assert runs == ["count"]

    @pytest.mark.parametrize("stop_after", ["init", "config", "commandline"])
    def test_run_setup_stops_before_the_commands(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, stop_after: str
    ) -> None:
        monkeypatch.chdir(tmp_path)
        script = write(
            tmp_path / "setup.py",
            textwrap.dedent(
                """\
                from distutils.core import setup, Command

                class Boom(Command):
                    user_options = []
                    def initialize_options(self): pass
                    def finalize_options(self): pass
                    def run(self): raise AssertionError('a command ran')

                setup(name='demo', cmdclass={'boom': Boom})
                """
            ),
        )
        dist = du.core.run_setup(str(script), ["boom"], stop_after=stop_after)
        assert isinstance(dist, du.dist.Distribution)
        assert dist.get_name() == "demo"

    def test_run_command_skips_until_reinitialized(self, du: Any) -> None:
        runs: list[str] = []
        dist = du.dist.Distribution({"cmdclass": {"count": self.counting_command(du, runs)}})
        dist.run_command("count")
        dist.run_command("count")
        assert runs == ["count"]
        dist.reinitialize_command("count")
        dist.run_command("count")
        assert runs == ["count", "count"]

    def test_extension_keeps_the_sources_list(self, du: Any) -> None:
        sources = ["a.c", "b.c"]
        ext = du.core.Extension("demo", sources)
        assert ext.sources is sources
        assert du.core.Extension is du.extension.Extension
        assert du.core.Distribution is du.dist.Distribution


class TestCommandBase:
    """`Command`: the base methods are abstract, and `get_sub_commands()`
    calls each predicate in `sub_commands`."""

    def test_the_base_class_cannot_be_constructed(self, du: Any) -> None:
        assert du.core.Command is du.cmd.Command
        with pytest.raises(RuntimeError, match="abstract class"):
            du.cmd.Command(du.dist.Distribution())

    def test_a_missing_run_raises(self, du: Any) -> None:
        class NoRun(du.cmd.Command):
            def initialize_options(self) -> None:
                pass

            def finalize_options(self) -> None:
                pass

        with pytest.raises(RuntimeError, match="abstract method"):
            NoRun(du.dist.Distribution()).run()

    def test_the_base_option_methods_raise(self, du: Any) -> None:
        class Options(du.cmd.Command):
            def initialize_options(self) -> None:
                pass

            def finalize_options(self) -> None:
                pass

        command = Options(du.dist.Distribution())
        for method in (du.cmd.Command.initialize_options, du.cmd.Command.finalize_options):
            with pytest.raises(RuntimeError, match="abstract method"):
                method(command)

    def test_sub_commands_calls_every_predicate(self, du: Any) -> None:
        calls: list[str] = []

        def yes(cmd: Any) -> bool:
            calls.append("yes")
            return True

        def no(cmd: Any) -> bool:
            calls.append("no")
            return False

        class Parent(du.cmd.Command):
            sub_commands = [("a", yes), ("b", no), ("c", None)]

            def initialize_options(self) -> None:
                pass

            def finalize_options(self) -> None:
                pass

        assert Parent(du.dist.Distribution()).get_sub_commands() == ["a", "c"]
        assert calls == ["yes", "no"]


def make_project(root: pathlib.Path) -> dict[str, Any]:
    """Two modules, a package with a header, a script and a data file."""
    write(root / "alpha.py")
    write(root / "pkg" / "__init__.py")
    write(root / "pkg" / "beta.py")
    write(root / "include" / "demo.h", "#define DEMO 1\n")
    write(root / "scripts" / "tool", "#!/usr/bin/env python\nprint('tool')\n")
    write(root / "data" / "table.txt", "1 2 3\n")
    return {
        "name": "demo",
        "version": "1.0",
        "script_name": "setup.py",
        "py_modules": ["alpha"],
        "packages": ["pkg"],
        "headers": ["include/demo.h"],
        "scripts": ["scripts/tool"],
        "data_files": [("share/demo", ["data/table.txt"])],
    }


class TestCopyingCommandsSkipUpToDateFiles:
    """`build_py`, `build_scripts`, `install_lib`, `install_headers`,
    `install_scripts`, `install_data` | O(n + b): a file whose copy is at
    least as new is skipped unless `--force`."""

    def run_install(
        self, du: Any, attrs: dict[str, Any], prefix: pathlib.Path, *extra: str
    ) -> None:
        args = ["install", "--prefix", str(prefix), *extra]
        du.core.setup(script_args=args, **attrs)

    def test_a_second_install_copies_nothing(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        attrs = make_project(tmp_path)
        prefix = tmp_path / "prefix"
        copied = copy_counter(du, monkeypatch)

        self.run_install(du, attrs, prefix)
        first = list(copied)
        names = {pathlib.Path(path).name for path in first}
        assert {"alpha.py", "__init__.py", "beta.py", "demo.h", "tool", "table.txt"} <= names
        installed = {path for path in first if pathlib.Path(path).is_relative_to(prefix)}
        built = set(first) - installed
        assert installed
        assert built
        assert all("build" in pathlib.Path(path).parts for path in built)
        # build_scripts rewrites the #! line itself rather than copying the script
        script = next((tmp_path / "build").glob("scripts-*/tool"))
        rewritten = script.stat().st_mtime_ns

        copied.clear()
        self.run_install(du, attrs, prefix)
        assert copied == []
        assert script.stat().st_mtime_ns == rewritten

        self.run_install(du, attrs, prefix, "--force")
        assert set(copied) == installed  # --force reaches install_*, not build

    def test_build_py_2to3_converts_only_what_it_copied(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write(tmp_path / "alpha.py")
        write(tmp_path / "gamma.py")
        converted: list[list[str]] = []
        monkeypatch.setattr(
            du.cmd_build_py.build_py_2to3, "run_2to3", lambda self, files: converted.append(files)
        )

        for _ in range(2):
            dist = du.dist.Distribution({"py_modules": ["alpha", "gamma"]})
            dist.cmdclass["build_py"] = du.cmd_build_py.build_py_2to3
            dist.run_command("build_py")

        assert [sorted(pathlib.Path(f).name for f in files) for files in converted] == [
            ["alpha.py", "gamma.py"],
            [],
        ]


class TestBuildExtAndBuildClib:
    """`build_ext` skips an extension newer than its sources and `depends`
    and otherwise compiles every source again; `build_clib` compiles on every
    run and skips only the archiver."""

    def run(self, du: Any, command: str, attrs: dict[str, Any]) -> None:
        dist = du.dist.Distribution(attrs)
        dist.run_command(command)

    def test_build_ext_checks_sources_and_depends_only(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = write(tmp_path / "demo.c", '#include "demo.h"\n')
        header = write(tmp_path / "demo.h", "#define DEMO 1\n")
        other = write(tmp_path / "other.h", "#define OTHER 1\n")
        for path in (source, header, other):
            set_mtime(path, 1_000_000_000)
        spawns = Spawns()
        monkeypatch.setattr(du.ccompiler.CCompiler, "spawn", lambda self, cmd: spawns(cmd))

        attrs = {"ext_modules": [du.core.Extension("demo", ["demo.c"], depends=["demo.h"])]}
        self.run(du, "build_ext", attrs)
        assert len(spawns) == 2  # compile, then link

        build_ext = du.dist.Distribution(attrs).get_command_obj("build_ext")
        build_ext.ensure_finalized()
        output = build_ext.get_ext_fullpath("demo")
        assert os.path.exists(output)
        set_mtime(output, 1_100_000_000)

        spawns.commands.clear()
        self.run(du, "build_ext", attrs)
        assert len(spawns) == 0

        set_mtime(other, 1_200_000_000)
        self.run(du, "build_ext", attrs)
        assert len(spawns) == 0

        set_mtime(header, 1_200_000_000)
        self.run(du, "build_ext", attrs)
        assert len(spawns) == 2

    def test_build_clib_compiles_every_run(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write(tmp_path / "foo.c", "int foo(void) { return 0; }\n")
        write(tmp_path / "bar.c", "int bar(void) { return 0; }\n")
        spawns = Spawns()
        monkeypatch.setattr(du.ccompiler.CCompiler, "spawn", lambda self, cmd: spawns(cmd))
        attrs = {"libraries": [("foo", {"sources": ["foo.c", "bar.c"]})]}

        self.run(du, "build_clib", attrs)
        assert len(spawns) == 3  # two compiles, one archive
        archive = spawns.commands[-1]
        library = next(arg for arg in archive if arg.endswith(".a"))
        pathlib.Path(library).touch()
        set_mtime(library, 2_000_000_000)

        spawns.commands.clear()
        self.run(du, "build_clib", attrs)
        assert len(spawns) == 2
        assert all("-c" in cmd for cmd in spawns.commands)


class TestOtherCommands:
    """`clean`, `sdist`, `bdist_dumb`, `check` and `config`."""

    def test_clean_keeps_build_lib_unless_all(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        dist = du.dist.Distribution()
        build = dist.get_command_obj("build")
        build.ensure_finalized()
        write(pathlib.Path(build.build_temp) / "obj.o")
        write(pathlib.Path(build.build_lib) / "mod.py")

        dist.run_command("clean")
        assert not os.path.exists(build.build_temp)
        assert os.path.exists(build.build_lib)

        dist = du.dist.Distribution()
        dist.get_command_obj("clean").all = 1
        dist.run_command("clean")
        assert not os.path.exists(build.build_lib)

    @pytest.mark.parametrize("files", [20, 200])
    def test_sdist_matches_each_pattern_against_every_file(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, files: int
    ) -> None:
        monkeypatch.chdir(tmp_path)
        for i in range(files):
            write(tmp_path / "data" / f"f{i}.txt")
        write(tmp_path / "MANIFEST.in", "include *.txt\ninclude *.cfg\ninclude *.rst\n")
        searches = {"include": 0}
        translate = du.filelist.translate_pattern

        class Counting:
            def __init__(self, pattern: re.Pattern[str]) -> None:
                self.pattern = pattern.pattern
                self._re = pattern

            def search(self, name: str) -> Any:
                searches["include"] += 1
                return self._re.search(name)

        original_include = du.filelist.FileList.include_pattern

        def include(
            self: Any, pattern: Any, anchor: int = 1, prefix: Any = None, is_regex: int = 0
        ) -> bool:
            if self.allfiles is None:
                self.findall()
            compiled = Counting(translate(pattern, anchor, prefix, is_regex))
            return original_include(self, compiled, anchor, prefix, is_regex=1)

        in_tree = len(du.filelist.findall())
        assert in_tree == files + 1  # the data files and MANIFEST.in
        monkeypatch.setattr(du.filelist.FileList, "include_pattern", include)
        dist = du.dist.Distribution({"name": "demo", "version": "1.0", "script_name": "setup.py"})
        sdist = dist.get_command_obj("sdist")
        sdist.manifest_only = 1
        sdist.use_defaults = 0
        dist.run_command("sdist")

        assert searches["include"] == 3 * in_tree

    def test_bdist_dumb_archives_a_temporary_install(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write(tmp_path / "alpha.py")
        archived: list[list[str]] = []

        def record(
            base_name: str, format: str, root_dir: Any = None, *args: Any, **kwargs: Any
        ) -> str:
            archived.append(sorted(p.name for p in pathlib.Path(root_dir).rglob("*.py")))
            return base_name + ".tar"

        monkeypatch.setattr(du.archive_util, "make_archive", record)
        dist = du.dist.Distribution({"name": "demo", "version": "1.0", "py_modules": ["alpha"]})
        dist.script_name = "setup.py"
        dist.get_command_obj("bdist_dumb").format = "tar"
        dist.run_command("bdist_dumb")
        assert archived == [["alpha.py"]]

    def test_check_warns_about_missing_metadata(self, du: Any) -> None:
        dist = du.dist.Distribution({"name": "demo", "version": "1.0"})
        check = dist.get_command_obj("check")
        check.ensure_finalized()
        check.run()
        assert check._warnings == 2  # no url, and no author or maintainer

    def test_config_runs_the_compiler_per_try(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        spawns = Spawns()
        monkeypatch.setattr(du.ccompiler, "spawn", spawns)
        monkeypatch.setattr(du.spawn, "spawn", spawns)
        dist = du.dist.Distribution()
        config = dist.get_command_obj("config")
        config.ensure_finalized()

        counts = []
        for attempt in (config.try_compile, config.try_link, config.try_run):
            spawns.commands.clear()
            assert attempt("int main(void) { return 0; }")
            counts.append(len(spawns))
        assert counts == [1, 2, 3]


class TestCCompilerConfiguration:
    """`new_compiler()`, `define_macro()`, the `add_*` and `set_*` methods,
    `set_executables()`, `customize_compiler()` and the option helpers."""

    def test_new_compiler_has_the_class_defaults(
        self, du: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert du.ccompiler.get_default_compiler("posix", "linux") == "unix"
        assert du.ccompiler.get_default_compiler("nt", "win32") == "msvc"
        compiler = du.ccompiler.new_compiler(plat="posix")
        assert type(compiler).__name__ == "UnixCCompiler"
        assert compiler.compiler_so == ["cc"]

        monkeypatch.setenv("CC", "mycc -O0")
        du.sysconfig.customize_compiler(compiler)
        assert compiler.compiler_so[:2] == ["mycc", "-O0"]

    def test_concrete_compilers_are_ccompilers(self, du: Any) -> None:
        for module, name in [
            (du.unixccompiler, "UnixCCompiler"),
            (du.cygwinccompiler, "CygwinCCompiler"),
            (du.bcppcompiler, "BCPPCompiler"),
            (du.msvccompiler, "MSVCCompiler"),
        ]:
            assert issubclass(getattr(module, name), du.ccompiler.CCompiler)

    def test_show_compilers_prints_the_table(
        self, du: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        du.ccompiler.show_compilers()
        out = capsys.readouterr().out
        for name in ("unix", "msvc", "cygwin", "mingw32", "bcpp"):
            assert f"--compiler={name}" in out

    @pytest.mark.parametrize("macros", [10, 1_000])
    def test_define_macro_scans_the_macros(self, du: Any, macros: int) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        for i in range(macros):
            compiler.define_macro(f"M{i}", "1")

        class Name(str):
            comparisons = 0

            def __eq__(self, other: object) -> bool:
                Name.comparisons += 1
                return str.__eq__(self, other)

            __hash__ = str.__hash__

        compiler.define_macro(Name("NEW"), "1")
        assert Name.comparisons == macros

        compiler.define_macro("M0", "2")
        compiler.undefine_macro("M1")
        names = [m[0] for m in compiler.macros]
        assert names.count("M0") == 1
        assert ("M0", "2") in compiler.macros
        assert ("M1",) in compiler.macros
        assert len(compiler.macros) == macros + 1

    def test_set_methods_store_copies(self, du: Any) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        for setter, adder, attr in [
            ("set_include_dirs", "add_include_dir", "include_dirs"),
            ("set_libraries", "add_library", "libraries"),
            ("set_library_dirs", "add_library_dir", "library_dirs"),
            ("set_runtime_library_dirs", "add_runtime_library_dir", "runtime_library_dirs"),
            ("set_link_objects", "add_link_object", "objects"),
        ]:
            given = ["a", "b"]
            getattr(compiler, setter)(given)
            given.append("c")
            assert getattr(compiler, attr) == ["a", "b"]
            getattr(compiler, adder)("d")
            assert getattr(compiler, attr) == ["a", "b", "d"]
            assert given == ["a", "b", "c"]

    def test_set_executables_splits_like_a_shell(self, du: Any) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        compiler.set_executables(compiler='gcc -DNAME="a b"')
        assert compiler.compiler == ["gcc", "-DNAME=a b"]

    def test_option_helpers(self, du: Any) -> None:
        assert du.ccompiler.gen_preprocess_options([("A", "1"), ("B", None), ("C",)], ["inc"]) == [
            "-DA=1",
            "-DB",
            "-UC",
            "-Iinc",
        ]
        compiler = du.ccompiler.new_compiler(plat="posix")
        assert compiler.library_dir_option("d") == "-Ld"
        assert compiler.library_option("m") == "-lm"
        assert "d" in "".join(compiler.runtime_library_dir_option("d"))
        looked_up: list[tuple[list[str], str]] = []
        compiler.find_library_file = lambda dirs, lib, debug=0: looked_up.append((dirs, lib))
        compiler.warn = lambda msg: None
        options = du.ccompiler.gen_lib_options(compiler, ["L"], [], ["m", "sub/z"])
        assert looked_up == [(["sub"], "z")]
        assert options == ["-LL", "-lm"]


class TestCCompilerRuns:
    """`compile()` runs once per source on every call; the link and archive
    steps and `UnixCCompiler.preprocess()` skip while their output is
    newer; `has_function()` compiles and links."""

    def sources(self, root: pathlib.Path, count: int) -> list[str]:
        paths = []
        for i in range(count):
            path = write(root / f"s{i}.c", "int f(void) { return 0; }\n")
            set_mtime(path, 1_000_000_000)
            paths.append(str(path))
        return paths

    @pytest.mark.parametrize("count", [3, 30])
    def test_compile_runs_once_per_source_every_call(
        self, du: Any, tmp_path: pathlib.Path, count: int
    ) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        spawns = Spawns()
        compiler.spawn = spawns
        sources = self.sources(tmp_path, count)
        header = write(tmp_path / "old.h", "")
        set_mtime(header, 900_000_000)
        out = str(tmp_path / "build")

        objects = compiler.compile(sources, output_dir=out, depends=[str(header)])
        assert len(spawns) == count
        assert len(objects) == count
        for obj in objects:
            set_mtime(obj, 2_000_000_000)

        spawns.commands.clear()
        compiler.compile(sources, output_dir=out, depends=[str(header)])
        assert len(spawns) == count

    def test_link_and_archive_skip_while_up_to_date(self, du: Any, tmp_path: pathlib.Path) -> None:
        objects = []
        for i in range(5):
            obj = write(tmp_path / f"o{i}.o", "")
            set_mtime(obj, 1_000_000_000)
            objects.append(str(obj))

        for force in (0, 1):
            compiler = du.ccompiler.new_compiler(plat="posix", force=force)
            spawns = Spawns()
            compiler.spawn = spawns
            library = compiler.library_filename("demo", output_dir=str(tmp_path))
            program = str(tmp_path / "prog")
            for target in (library, program):
                pathlib.Path(target).touch()
                set_mtime(target, 2_000_000_000)
            compiler.create_static_lib(objects, "demo", output_dir=str(tmp_path))
            compiler.link_executable(objects, "prog", output_dir=str(tmp_path))
            assert len(spawns) == (2 if force else 0)

            for target in (library, program):
                set_mtime(target, 500_000_000)
            spawns.commands.clear()
            compiler.create_static_lib(objects, "demo", output_dir=str(tmp_path))
            compiler.link_executable(objects, "prog", output_dir=str(tmp_path))
            assert len(spawns) == 2

    def test_preprocess_skips_an_up_to_date_output(self, du: Any, tmp_path: pathlib.Path) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        compiler.set_executables(preprocessor="cpp")
        spawns = Spawns()
        compiler.spawn = spawns
        source = self.sources(tmp_path, 1)[0]
        output = write(tmp_path / "s0.i", "")
        set_mtime(output, 2_000_000_000)

        compiler.preprocess(source, output_file=str(output))
        assert len(spawns) == 0
        compiler.preprocess(source)
        assert len(spawns) == 1

    def test_has_function_compiles_and_links(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        compiler = du.ccompiler.new_compiler(plat="posix")
        spawns = Spawns()
        compiler.spawn = spawns
        assert compiler.has_function("abs")
        assert len(spawns) == 2

    @pytest.mark.parametrize("dirs", [10, 100])
    def test_find_library_file_checks_each_directory(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, dirs: int
    ) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        paths = [str(tmp_path / f"d{i}") for i in range(dirs)]
        write(tmp_path / "d5" / compiler.library_filename("demo", lib_type="shared"), "")
        checks = {"count": 0}
        exists = os.path.exists

        def counting(path: Any) -> bool:
            checks["count"] += 1
            return exists(path)

        monkeypatch.setattr(os.path, "exists", counting)
        assert compiler.find_library_file(paths, "missing") is None
        missing = checks["count"]
        checks["count"] = 0
        found = compiler.find_library_file(paths, "demo")
        monkeypatch.undo()

        assert missing == 4 * dirs
        assert found == os.path.join(paths[5], "libdemo.so")
        assert checks["count"] <= 4 * 6

    def test_filename_helpers_do_no_io(self, du: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix")
        forbid_stat(monkeypatch)
        assert compiler.object_filenames(["a/b.c", "c.cpp"], output_dir="out") == [
            os.path.join("out", "a", "b.o"),
            os.path.join("out", "c.o"),
        ]
        with pytest.raises(du.errors.UnknownFileError):
            compiler.object_filenames(["a.txt"])
        assert compiler.shared_object_filename("m") == "m.so"
        assert compiler.library_filename("m") == "libm.a"
        assert compiler.executable_filename("m") == "m"
        assert compiler.detect_language(["a.c", "b.cpp", "c.m"]) == "c++"

    def test_reporting_and_dry_run_helpers(
        self,
        du: Any,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        compiler = du.ccompiler.new_compiler(plat="posix", dry_run=1)
        compiler.debug_print("quiet")
        monkeypatch.setattr(du.debug, "DEBUG", "1")
        compiler.debug_print("loud")
        compiler.warn("careful")
        captured = capsys.readouterr()
        assert captured.out == "loud\n"
        assert captured.err == "warning: careful\n"

        calls: list[int] = []
        compiler.execute(calls.append, (1,))  # passes dry_run on as `verbose`
        assert calls == [1]
        calls.clear()
        compiler.spawn(["false"])
        compiler.mkpath(str(tmp_path / "never"))
        source = write(tmp_path / "keep.txt")
        compiler.move_file(str(source), str(tmp_path / "moved.txt"))
        assert calls == []
        assert not (tmp_path / "never").exists()
        assert source.exists()


class TestDependencyChecks:
    """`newer()` compares whole seconds; `newer_group()` stops at the first
    newer source; `newer_pairwise()` keeps the stale pairs."""

    def test_newer_ignores_a_change_within_one_second(
        self, du: Any, tmp_path: pathlib.Path
    ) -> None:
        source = write(tmp_path / "a")
        target = write(tmp_path / "b")
        os.utime(target, ns=(1_000_000_000_100_000_000, 1_000_000_000_100_000_000))
        os.utime(source, ns=(1_000_000_000_900_000_000, 1_000_000_000_900_000_000))
        assert os.stat(source).st_mtime > os.stat(target).st_mtime
        assert not du.dep_util.newer(str(source), str(target))
        assert du.dep_util.newer(str(source), str(tmp_path / "missing"))
        with pytest.raises(du.errors.DistutilsFileError):
            du.dep_util.newer(str(tmp_path / "missing"), str(target))

    def test_newer_group_stops_at_the_first_newer_source(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = write(tmp_path / "target")
        set_mtime(target, 1_000_000_000)
        sources = []
        for i in range(100):
            path = write(tmp_path / f"s{i}")
            set_mtime(path, 2_000_000_000 if i == 3 else 500_000_000)
            sources.append(str(path))
        seen: list[str] = []
        stat = os.stat

        def counting(path: Any, *args: Any, **kwargs: Any) -> Any:
            seen.append(os.fspath(path))
            return stat(path, *args, **kwargs)

        monkeypatch.setattr(os, "stat", counting)
        assert du.dep_util.newer_group(sources, str(target))
        monkeypatch.undo()

        assert set(seen) & set(sources) == set(sources[:4])

    def test_newer_pairwise(self, du: Any, tmp_path: pathlib.Path) -> None:
        old = write(tmp_path / "old")
        new = write(tmp_path / "new")
        set_mtime(old, 1_000_000_000)
        set_mtime(new, 2_000_000_000)
        result = du.dep_util.newer_pairwise([str(new), str(old)], [str(old), str(new)])
        assert result == ([str(new)], [str(old)])


class TestFileUtil:
    """`copy_file()` is O(b) time and O(1) space, O(1) with `update=1` on an
    up-to-date target or with `link`; `move_file()` renames, copying only
    across filesystems; `write_file()` adds a newline per string."""

    def test_copy_holds_one_block(self, du: Any, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "big"
        source.write_bytes(bytes(8 * 1024 * 1024))
        target = tmp_path / "copy"
        peak = peak_bytes(lambda: du.file_util.copy_file(str(source), str(target), verbose=0))
        assert target.read_bytes() == source.read_bytes()
        assert peak < 256 * 1024, peak

    def test_update_and_link_copy_nothing(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        copied = copy_counter(du, monkeypatch)
        source = write(tmp_path / "src")
        target = tmp_path / "dst"
        assert du.file_util.copy_file(str(source), str(target), update=1) == (str(target), 1)
        assert du.file_util.copy_file(str(source), str(target), update=1) == (str(target), 0)
        assert len(copied) == 1

        linked = tmp_path / "linked"
        du.file_util.copy_file(str(source), str(linked), link="hard")
        assert len(copied) == 1
        assert os.stat(linked).st_ino == os.stat(source).st_ino

        def no_link(src: Any, dst: Any) -> None:
            raise OSError(errno.EXDEV, "cross-device link")

        monkeypatch.setattr(os, "link", no_link)
        du.file_util.copy_file(str(source), str(tmp_path / "fallback"), link="hard")
        assert copied == [str(target), str(tmp_path / "fallback")]

    def test_move_file_renames_or_copies(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        copied = copy_counter(du, monkeypatch)
        source = write(tmp_path / "a")
        assert du.file_util.move_file(str(source), str(tmp_path / "b")) == str(tmp_path / "b")
        assert copied == []
        assert not source.exists()

        def cross_device(src: Any, dst: Any) -> None:
            raise OSError(errno.EXDEV, "cross-device link")

        monkeypatch.setattr(os, "rename", cross_device)
        du.file_util.move_file(str(tmp_path / "b"), str(tmp_path / "c"))
        assert len(copied) == 1
        assert not (tmp_path / "b").exists()
        assert (tmp_path / "c").read_text(encoding="utf-8") == "x = 1\n"

    def test_write_file(self, du: Any, tmp_path: pathlib.Path) -> None:
        du.file_util.write_file(str(tmp_path / "f"), ["a", "b"])
        assert (tmp_path / "f").read_text(encoding="utf-8") == "a\nb\n"


class TestDirUtil:
    """`mkpath()` is O(d) and remembers what it made; `create_tree()` makes
    one `mkpath()` per distinct directory; `copy_tree()` returns every name;
    `remove_tree()` lists before it deletes and logs failures."""

    def test_mkpath_makes_one_directory_per_missing_component(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        made: list[str] = []
        mkdir = os.mkdir

        def counting(path: Any, *args: Any, **kwargs: Any) -> None:
            made.append(os.fspath(path))
            mkdir(path, *args, **kwargs)

        monkeypatch.setattr(os, "mkdir", counting)
        target = tmp_path.joinpath("a", "b", "c", "d", "e")
        created = du.dir_util.mkpath(str(target))
        assert len(made) == 5
        assert created == made
        assert target.is_dir()

    def test_mkpath_remembers_until_remove_tree(self, du: Any, tmp_path: pathlib.Path) -> None:
        import shutil

        target = tmp_path / "x" / "y"
        assert len(du.dir_util.mkpath(str(target))) == 2
        shutil.rmtree(tmp_path / "x")
        assert du.dir_util.mkpath(str(target)) == []
        assert not target.exists()

        target.mkdir(parents=True)
        du.dir_util.remove_tree(str(tmp_path / "x"))
        assert len(du.dir_util.mkpath(str(target))) == 2
        assert target.is_dir()

    def test_create_tree_makes_each_directory_once(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(du.dir_util, "mkpath", lambda name, *a, **k: calls.append(name))
        files = [f"{d}/f{i}" for i in range(10) for d in ("c", "a", "b/x")]
        du.dir_util.create_tree(str(tmp_path), files)
        assert calls == [os.path.join(str(tmp_path), d) for d in ("a", "b/x", "c")]

    def test_copy_tree_returns_every_name(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        copied = copy_counter(du, monkeypatch)
        for name in ("a", "sub/b", "sub/deeper/c", ".nfs0001"):
            write(tmp_path / "src" / name)
        dst = tmp_path / "dst"
        first = du.dir_util.copy_tree(str(tmp_path / "src"), str(dst), update=1)
        assert len(first) == 3
        assert not (dst / ".nfs0001").exists()
        assert len(copied) == 3

        copied.clear()
        second = du.dir_util.copy_tree(str(tmp_path / "src"), str(dst), update=1)
        assert sorted(second) == sorted(first)
        assert copied == []

    def test_remove_tree_lists_before_deleting(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in ("a", "s/b", "s/t/c", "u/d"):
            write(tmp_path / "tree" / name)
        events: list[str] = []
        listdir, remove = os.listdir, os.remove

        def listing(path: Any) -> list[str]:
            events.append("list")
            return listdir(path)

        def removing(path: Any) -> None:
            events.append("remove")
            remove(path)

        monkeypatch.setattr(os, "listdir", listing)
        monkeypatch.setattr(os, "remove", removing)
        du.dir_util.remove_tree(str(tmp_path / "tree"))
        assert events == ["list"] * 4 + ["remove"] * 4
        assert not (tmp_path / "tree").exists()

    def test_remove_tree_logs_a_failure(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write(tmp_path / "tree" / "a")
        warned: list[str] = []

        def failing(path: Any) -> None:
            raise OSError("no")

        monkeypatch.setattr(os, "remove", failing)
        monkeypatch.setattr(du.log, "warn", lambda msg, *args: warned.append(msg % args))
        du.dir_util.remove_tree(str(tmp_path / "tree"))
        assert len(warned) == 2  # the file, then the directory still holding it


class TestArchives:
    """`make_tarball()` and `make_zipfile()` archive the tree; `make_archive()`
    changes the working directory to `root_dir` while it runs."""

    def test_formats(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        for name in ("a", "sub/b"):
            write(tmp_path / "tree" / name)
        for compress, suffix in [
            ("gzip", ".tar.gz"),
            ("bzip2", ".tar.bz2"),
            ("xz", ".tar.xz"),
            (None, ".tar"),
        ]:
            name = du.archive_util.make_tarball("out", "tree", compress=compress)
            assert name == "out" + suffix
            with tarfile.open(name) as tar:
                assert {"tree/a", "tree/sub/b"} <= set(tar.getnames())
        assert du.archive_util.make_zipfile("out", "tree") == "out.zip"
        with zipfile.ZipFile("out.zip") as archive:
            assert {"tree/a", "tree/sub/b"} <= set(archive.namelist())
        with pytest.raises(ValueError):
            du.archive_util.make_tarball("out", "tree", compress="rar")

    def test_compress_runs_the_external_program(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        write(tmp_path / "tree" / "a")
        commands: list[list[str]] = []
        monkeypatch.setattr(du.archive_util, "spawn", lambda cmd, **kw: commands.append(cmd))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PendingDeprecationWarning)
            name = du.archive_util.make_tarball("out", "tree", compress="compress")
        assert name == "out.tar.Z"
        assert commands == [["compress", "-f", "out.tar"]]

    def test_make_archive_changes_the_working_directory(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        seen: list[str] = []

        def record(base_name: str, base_dir: str, **kwargs: Any) -> str:
            seen.append(os.getcwd())
            return base_name + ".tar"

        monkeypatch.setitem(du.archive_util.ARCHIVE_FORMATS, "tar", (record, [], "recorder"))
        before = os.getcwd()
        du.archive_util.make_archive(str(tmp_path / "out"), "tar", root_dir=str(root))
        assert seen == [str(root)]
        assert os.getcwd() == before


class TestUtil:
    """The `distutils.util` rows."""

    @pytest.mark.skipif(os.sep != "/", reason="Windows paths are converted, not returned")
    def test_convert_path_returns_its_argument_on_posix(self, du: Any) -> None:
        path = "a/b/c"
        assert du.util.convert_path(path) is path
        assert du.util.change_root("/new", "/usr/lib") == "/new/usr/lib"
        assert du.util.change_root("/new", "rel") == "/new/rel"

    def test_check_environ_runs_once(self, du: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(du.util, "_environ_checked", 0)
        monkeypatch.delenv("PLAT", raising=False)
        du.util.check_environ()
        assert os.environ["PLAT"] == du.util.get_platform()
        monkeypatch.delenv("PLAT")
        du.util.check_environ()
        assert "PLAT" not in os.environ

    def test_subst_vars(self, du: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FROM_ENV", "env")
        assert du.util.subst_vars("$a-$FROM_ENV", {"a": 1}) == "1-env"
        with pytest.raises(ValueError, match="invalid variable"):
            du.util.subst_vars("$no_such_variable_here", {})

    def test_small_helpers(self, du: Any) -> None:
        calls: list[int] = []
        du.util.execute(calls.append, (1,), dry_run=1)
        assert calls == []
        du.util.execute(calls.append, (1,))
        assert calls == [1]
        assert du.util.strtobool("Yes") == 1
        assert du.util.strtobool("off") == 0
        assert du.util.rfc822_escape("a\nb") == "a\n        b"
        assert du.util.split_quoted(r'a "b c" d\ e') == ["a", "b c", "d e"]

    def test_byte_compile_skips_up_to_date_files(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import py_compile

        files = [str(write(tmp_path / f"m{i}.py")) for i in range(3)]
        compiled: list[str] = []
        original = py_compile.compile

        def counting(file: str, *args: Any, **kwargs: Any) -> Any:
            compiled.append(file)
            return original(file, *args, **kwargs)

        monkeypatch.setattr(py_compile, "compile", counting)
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
        du.util.byte_compile(files, direct=1, verbose=0)
        assert compiled == files
        compiled.clear()
        du.util.byte_compile(files, direct=1, verbose=0)
        assert compiled == []
        du.util.byte_compile(files, direct=1, force=1, verbose=0)
        assert compiled == files

    def test_byte_compile_with_optimize_runs_an_interpreter(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []
        monkeypatch.setattr(du.util, "spawn", lambda cmd, **kw: commands.append(cmd))
        monkeypatch.setattr(sys, "dont_write_bytecode", False)
        module = str(write(tmp_path / "m.py"))
        du.util.byte_compile([module], optimize=1, verbose=0)
        assert len(commands) == 1
        assert commands[0][0] == sys.executable

        commands.clear()
        du.util.byte_compile([module], optimize=1, direct=1, verbose=0)
        assert commands == []
        assert os.path.exists(importlib.util.cache_from_source(module, optimization=1))


def ratio(func: Callable[[int], Callable[[], Any]], small: int, large: int) -> float:
    return fastest(func(large)) / fastest(func(small))


class TestQuadraticInWords:
    """`split_quoted()` | O(L·w), `wrap_text()` | O(L + w²),
    `TextFile.readline()` joining p lines | O(L·p) and `FancyGetopt.getopt()`
    | O(o + a·o + a²). Slice lengths settle `split_quoted()`; the other
    tests require over 25x the time for 10x the words, lines or arguments,
    where a quadratic predicts 100x and a linear bound predicts 10x."""

    @pytest.mark.timing
    def test_getopt_in_the_argument_count(self, du: Any) -> None:
        def parse(a: int) -> Callable[[], Any]:
            args = ["--verbose"] * a
            return lambda: du.fancy_getopt.FancyGetopt([("verbose", "v", "")]).getopt(args)

        r = ratio(parse, 1_000, 10_000)
        assert r > 25, r

    @pytest.mark.parametrize("words", [10, 100, 1_000])
    def test_split_quoted(self, du: Any, words: int) -> None:
        """Repeated suffix slices copy w² characters for fixed-width words."""
        copied = 0

        class ObservedString(str):
            def __getitem__(self, key: Any) -> str:
                nonlocal copied
                result = super().__getitem__(key)
                if isinstance(key, slice):
                    copied += len(result)
                    return ObservedString(result)
                return result

            def strip(self, chars: str | None = None) -> ObservedString:
                return ObservedString(super().strip(chars))

            def lstrip(self, chars: str | None = None) -> ObservedString:
                return ObservedString(super().lstrip(chars))

        result = du.util.split_quoted(ObservedString("a " * words))

        assert result == ["a"] * words
        assert copied == words**2

    @pytest.mark.timing
    def test_wrap_text(self, du: Any) -> None:
        r = ratio(lambda w: lambda: du.fancy_getopt.wrap_text("ab " * w, 10), 1_000, 10_000)
        assert r > 25, r

    @pytest.mark.timing
    def test_joined_readline(self, du: Any) -> None:
        def read(p: int) -> Callable[[], Any]:
            data = ("x" * 40 + "\\\n") * p + "end\n"
            return lambda: du.text_file.TextFile(file=io.StringIO(data), join_lines=1).readline()

        r = ratio(read, 1_000, 10_000)
        assert r > 25, r


class TestTextFile:
    """`TextFile`: skips comments and blank lines, returns `None` at the
    end, unreads last in first out, and warns on stderr."""

    def test_reading(
        self, du: Any, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = write(tmp_path / "f.txt", "one # note\n\n# only a comment\ntwo\\\n  three\nfour\n")
        text = du.text_file.TextFile(str(path), join_lines=1, collapse_join=1)
        assert text.readline() == "one"
        assert text.readline() == "twothree"
        text.unreadline("b")
        text.unreadline("a")
        assert text.readline() == "a"
        assert text.readline() == "b"
        text.warn("odd")
        assert text.readlines() == ["four"]
        assert text.readline() is None
        text.close()
        assert "warning: " in capsys.readouterr().err

        text = du.text_file.TextFile(file=io.StringIO("x\n"))
        text.open(str(path))
        assert text.readline() == "one"
        text.close()


class TestFancyGetopt:
    """`FancyGetopt.getopt()` | O(o + a·o); `get_option_order()` is the
    parser's growing list; `generate_help()` wraps each option's help."""

    @pytest.mark.parametrize("options", [10, 100])
    def test_each_long_argument_scans_every_option(self, du: Any, options: int) -> None:
        class Long(str):
            calls = 0

            def startswith(self, *args: Any) -> bool:  # type: ignore[override]
                Long.calls += 1
                return str.startswith(self, *args)

        table = [(Long(f"opt{i}"), None, "help") for i in range(options)]
        parser = du.fancy_getopt.FancyGetopt(table)
        args, values = parser.getopt([f"--opt{i}" for i in range(5)])
        assert args == []
        assert values.opt4 == 1
        assert Long.calls == 5 * options

    def test_option_order_grows_across_calls(self, du: Any) -> None:
        parser = du.fancy_getopt.FancyGetopt([("verbose", "v", "be loud")])
        parser.getopt(["-v"])
        order = parser.get_option_order()
        parser.getopt(["--verbose"])
        assert parser.get_option_order() is order
        assert order == [("verbose", 1), ("verbose", 1)]

    def test_generate_help_wraps_each_option(
        self, du: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wrapped: list[str] = []
        original = du.fancy_getopt.wrap_text
        monkeypatch.setattr(
            du.fancy_getopt,
            "wrap_text",
            lambda text, width: wrapped.append(text) or original(text, width),
        )
        table = [(f"opt{i}", None, f"help {i}") for i in range(7)]
        lines = du.fancy_getopt.FancyGetopt(table).generate_help()
        assert len(wrapped) == 7
        assert lines[0] == "Option summary:"

    def test_fancy_getopt_sets_attributes(self, du: Any) -> None:
        target = types.SimpleNamespace()
        rest = du.fancy_getopt.fancy_getopt(
            [("verbose", "v", ""), ("quiet", "q", "")], {"quiet": "verbose"}, target, ["-q", "x"]
        )
        assert rest == ["x"]
        assert target.verbose == 0

    def test_wrap_text_returns_short_text_as_is(self, du: Any) -> None:
        assert du.fancy_getopt.wrap_text("short", 10) == ["short"]
        assert du.fancy_getopt.wrap_text("one two three four", 9) == ["one two", "three", "four"]


class TestVersions:
    """A `str` operand is parsed again on every comparison; `LooseVersion`
    cannot order a number against letters."""

    def test_a_string_operand_is_parsed_each_time(
        self, du: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parsed: list[str] = []
        original = du.version.LooseVersion.parse

        def counting(self: Any, vstring: str) -> None:
            parsed.append(vstring)
            original(self, vstring)

        monkeypatch.setattr(du.version.LooseVersion, "parse", counting)
        current = du.version.LooseVersion("1.9")
        other = du.version.LooseVersion("1.10")
        parsed.clear()
        for _ in range(5):
            assert current < other
        assert parsed == []
        for _ in range(5):
            assert current < "1.10"
        assert parsed == ["1.10"] * 5

    def test_parsing_and_ordering(self, du: Any) -> None:
        assert du.version.StrictVersion("1.2b1") < du.version.StrictVersion("1.2")
        assert du.version.LooseVersion("1.2") < du.version.LooseVersion("1.2b1")
        assert du.version.StrictVersion("1.2.3").version == (1, 2, 3)
        assert du.version.LooseVersion("1.2.3a").version == [1, 2, 3, "a"]
        with pytest.raises(ValueError):
            du.version.StrictVersion("1")
        with pytest.raises(TypeError):
            _ = du.version.LooseVersion("1.0a") < du.version.LooseVersion("1.0.1")


class TestLogSpawnAndSysconfig:
    """`distutils.log`, `spawn`, `find_executable` and `distutils.sysconfig`."""

    def test_log_formats_only_when_emitting(
        self, du: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import logging

        class Arg:
            calls = 0

            def __str__(self) -> str:
                Arg.calls += 1
                return "arg"

        old = du.log.set_threshold(du.log.WARN)
        try:
            du.log.info("value %s", Arg())
            assert Arg.calls == 0
            du.log.set_verbosity(1)
            du.log.info("value %s", Arg())
            assert Arg.calls == 1
            assert capsys.readouterr().out == "value arg\n"
            du.log.set_verbosity(0)
            assert du.log.set_threshold(du.log.DEBUG) == du.log.WARN
        finally:
            du.log.set_threshold(old)
        assert not isinstance(du.log._global_log, logging.Logger)

    @pytest.mark.parametrize("dirs", [10, 100])
    def test_find_executable_checks_each_directory(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, dirs: int
    ) -> None:
        checks = {"count": 0}
        isfile = os.path.isfile

        def counting(path: Any) -> bool:
            checks["count"] += 1
            return isfile(path)

        path = os.pathsep.join(str(tmp_path / f"d{i}") for i in range(dirs))
        monkeypatch.setattr(os.path, "isfile", counting)
        assert du.spawn.find_executable("no-such-program-here", path) is None
        monkeypatch.undo()
        assert checks["count"] == dirs + 1

    def test_spawn_raises_on_failure(self, du: Any) -> None:
        du.spawn.spawn([sys.executable, "-c", "pass"])
        with pytest.raises(du.errors.DistutilsExecError, match="exit code 3"):
            du.spawn.spawn([sys.executable, "-c", "raise SystemExit(3)"])

    def test_sysconfig_functions_are_shared(self, du: Any) -> None:
        for name in (
            "get_config_var",
            "get_config_vars",
            "get_config_h_filename",
            "get_makefile_filename",
        ):
            assert getattr(du.sysconfig, name) is getattr(sysconfig, name)
        assert du.sysconfig.get_config_vars() is sysconfig.get_config_vars()
        assert len(du.sysconfig.get_config_vars("prefix", "exec_prefix")) == 2
        assert du.sysconfig.PREFIX == os.path.normpath(sys.prefix)
        assert du.sysconfig.EXEC_PREFIX == os.path.normpath(sys.exec_prefix)

    def test_paths_are_not_checked_on_disk(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prefix = str(tmp_path / "does-not-exist")
        forbid_stat(monkeypatch)
        assert du.sysconfig.get_python_inc(prefix=prefix).startswith(prefix)
        assert du.sysconfig.get_python_lib(prefix=prefix).startswith(prefix)

    def test_debug_reads_the_environment_at_import(self) -> None:
        if not HAS_DISTUTILS:
            pytest.skip("version: distutils was removed in Python 3.12")
        env = dict(os.environ, DISTUTILS_DEBUG="1")
        code = "from distutils.debug import DEBUG; print(DEBUG)"
        result = run_python("-W", "ignore::DeprecationWarning", "-c", code, env=env)
        assert result.stdout.strip() == "1", result.stderr

    def test_errors_derive_from_two_bases(self, du: Any) -> None:
        for name in (
            "CompileError",
            "LinkError",
            "LibError",
            "PreprocessError",
            "UnknownFileError",
        ):
            assert issubclass(getattr(du.errors, name), du.errors.CCompilerError)
        assert issubclass(du.errors.DistutilsFileError, du.errors.DistutilsError)


class TestFileList:
    """`FileList.include_pattern()` | O(n); `exclude_pattern()` | O(n + n·x);
    `findall()` follows symbolic links."""

    def test_include_searches_each_file_once(self, du: Any) -> None:
        searched: list[str] = []

        class Counting:
            pattern = "counting"

            def search(self, name: str) -> bool:
                searched.append(name)
                return name.endswith(".py")

        files = du.filelist.FileList()
        files.set_allfiles([f"f{i}.{'py' if i % 2 else 'txt'}" for i in range(100)])
        assert files.include_pattern(Counting(), is_regex=1)
        assert len(searched) == 100
        assert len(files.files) == 50

    def test_exclude_deletes_once_per_removed_file(self, du: Any) -> None:
        deletes = {"count": 0}

        class Files(list):  # type: ignore[type-arg]
            def __delitem__(self, index: Any) -> None:
                deletes["count"] += 1
                super().__delitem__(index)

        files = du.filelist.FileList()
        files.files = Files(f"f{i}.{'py' if i % 4 else 'txt'}" for i in range(100))
        assert files.exclude_pattern("*.txt")
        assert deletes["count"] == 25
        assert len(files.files) == 75

    def test_findall_follows_symlinks(
        self, du: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write(tmp_path / "real" / "a.txt")
        try:
            os.symlink(tmp_path / "real", tmp_path / "link", target_is_directory=True)
        except OSError as error:
            pytest.skip(f"missing symlinks: {error}")
        monkeypatch.chdir(tmp_path)
        assert sorted(du.filelist.findall()) == [
            os.path.join("link", "a.txt"),
            os.path.join("real", "a.txt"),
        ]


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
        [sys.executable, "-S", "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result. The
    blocks that import distutils run on 3.10 and 3.11; the replacements block
    runs everywhere."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert sum("distutils" in source for _, source in blocks) == EXPECTED_BLOCKS - 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "distutils" in source and not HAS_DISTUTILS:
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (EXPECTED_BLOCKS if HAS_DISTUTILS else 1)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, du: Any, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert runs == []" in s)
        mutated = source.replace("assert runs == []", "assert runs == [1]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
