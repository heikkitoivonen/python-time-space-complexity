"""Tests for docs/stdlib/venv.md.

The page prices environment creation as filesystem work: a fixed handful of
directories and files, plus the interpreter executable, which is copied under
each of its names by default and linked with `symlinks=True`. Those claims are
settled by observation - the files an environment contains, their sizes and
link status, and the calls to `shutil.copyfile`, `os.unlink`/`os.remove` and
`subprocess.check_output` made while building one - so no test here depends
on a stopwatch. Every environment is built under `tmp_path`.

Measurement scope:

* The b term: `venv.create()` with its default `symlinks=False` makes
  `python`, `python3` and `python3.X` regular files the size of the resolved
  base executable, and calls `shutil.copyfile` on an interpreter-sized source
  at least once per name; `symlinks=True` makes every name a link resolving
  to the executable and never copies it. The unchanged activation templates
  are copied either way. `venv.main()` given only a directory and
  `--without-pip` links on POSIX.
* Nothing from the installation is copied: a symlinked environment built with
  `system_site_packages=True` holds fewer than 20 files, no `.py` file, and
  under 64 KB of regular-file bytes; its `site-packages` is empty and
  `pyvenv.cfg` names the base interpreter's directory as `home` and records
  the site-packages flag.
* The e term: `clear=True` over a directory holding one foreign top-level file
  and 10 or 1,000 files in a subdirectory makes between e and e + 5 calls to
  `os.unlink`/`os.remove`, and leaves none of those entries behind.
* Subprocesses: with `subprocess.check_output` replaced by a recorder, a
  default build makes none, `with_pip=True` makes one running `ensurepip`,
  `upgrade_deps=True` makes one running `pip install --upgrade` with `pip`
  (and `setuptools` before 3.12), and both together make two in that order.
* One real `with_pip=True` build runs with `HTTP_PROXY`, `HTTPS_PROXY` and
  `ALL_PROXY` pointed at a closed local port: it succeeds, pip imports in the
  environment, setuptools is installed exactly when the interpreter is older
  than 3.12, and the environment then holds more than ten times the files of
  one built without pip. A real `upgrade_deps=True` build without pip raises
  `CalledProcessError` before any network access, because `python -m pip`
  finds no pip.
* Hook order is observed by a recording subclass: `ensure_directories`,
  `create_git_ignore_file` (3.13+, with `scm_ignore_files={'git'}`),
  `create_configuration`, `setup_python`, `setup_scripts`, `install_scripts`,
  `post_setup`, `upgrade_dependencies`, each after the first receiving the
  one context object. `ensure_directories()` alone creates directories and
  the `lib64` link but no regular file, and touches no file when the tree
  already exists. `EnvBuilder()` is built with `os.makedirs`, `os.symlink`
  and `shutil.copyfile` patched to raise.
* `upgrade=True` over an existing environment calls neither `setup_scripts`
  nor `post_setup`, rewrites `pyvenv.cfg`, and leaves a file in
  `site-packages` in place.
* `install_scripts(context, path)` installs the files under `path`'s `common`
  and `os.name` subdirectories, nested ones included, skips top-level files
  and other subdirectories, and replaces `__VENV_DIR__` and
  `__VENV_PROMPT__`; a 200 KB template produces an installed file within a
  few hundred bytes of the template's size.
* `scm_ignore_files` is checked on each side of 3.13: from 3.13 the builder
  writes no `.gitignore` by default, writes one ignoring `*` for `{'git'}`,
  and `venv.main()` writes one unless given `--without-scm-ignore-files`;
  before 3.13 the keyword raises `TypeError` and `main()` writes none.
* The environment's interpreter, run by path with no activation, reports the
  environment as `sys.prefix` and the running interpreter's `sys.base_prefix`.
  Sourcing the installed `activate` script in bash puts the environment's
  `bin` directory in front of the `PATH` it was given.
* Every fenced Python block runs in its own subprocess, working directory and
  `TMPDIR`, both asserted empty afterwards, and a mutated assertion in one of
  them is asserted to fail.

Not settled here:

* `upgrade_deps=True` and `upgrade_dependencies()` contact the package index.
  The tests replace the subprocess and assert only the command; what pip then
  downloads depends on the network and on PyPI. The "+ network" term is read
  from Lib/venv/__init__.py, which runs `pip install --upgrade`.
* That `ensurepip` needs no network is read from Lib/ensurepip/__init__.py,
  which installs from bundled wheels with `--no-index`; the proxy test shows
  only that the build succeeds with every proxy variable pointing nowhere.
* Windows behaviour is kind D. On Windows the directory is `Scripts`,
  `symlinks=False` copies a launcher executable rather than the interpreter,
  and the `.bat` scripts are installed; `TestWindowsLayout` checks this and
  is skipped on every platform this project's CI runs. That `python -m venv`
  copies on Windows is read from `main()` in Lib/venv/__init__.py and not
  run. The POSIX-layout tests and the page's examples are skipped there.
* The base installation's size is not varied: one interpreter is used, and
  that creation does not grow with it follows from the environment holding
  no `.py` file and from Lib/venv/__init__.py copying nothing but the
  executable and the templates.
* That `site` reads `pyvenv.cfg` at startup, as the Related Modules entry
  says, is read from `venv()` in Lib/site.py.
* The size of p, the files pip installs, depends on the bundled pip wheel,
  which changes with each release; only its ratio to a pip-less environment
  is asserted.
* `EnvBuilder.clear_directory`, `replace_variables` and `symlink_or_copy`, the
  module `logger` and `venv.main` are undocumented helpers the audit reports
  for classification; the page does not document them, and names `main` only
  as `python -m venv`.
* Path lengths are held short throughout; placeholder replacement is linear in
  the path length and the template size together, and only the template size
  is varied.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import venv
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "venv.md"
EXPECTED_BLOCKS = 5

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX environment layout")
INTERPRETER_NAMES = ("python", "python3", f"python3.{sys.version_info[1]}")


def files_under(root: pathlib.Path) -> list[pathlib.Path]:
    """Every non-directory entry under root, links included, not followed."""
    found: list[pathlib.Path] = []
    for directory, dirnames, filenames in os.walk(root):
        found.extend(pathlib.Path(directory, name) for name in filenames)
        found.extend(
            pathlib.Path(directory, name)
            for name in dirnames
            if os.path.islink(os.path.join(directory, name))
        )
    return found


def base_executable() -> str:
    """The file an environment's interpreter is copied from or linked to."""
    return os.path.realpath(sys._base_executable)  # type: ignore[attr-defined]  # noqa: SLF001


def site_packages(context: Any) -> str:
    """The environment's site-packages; `context.lib_path` exists from 3.12."""
    if hasattr(context, "lib_path"):
        return context.lib_path
    if sys.platform == "win32":
        return os.path.join(context.env_dir, "Lib", "site-packages")
    version = f"python{sys.version_info[0]}.{sys.version_info[1]}"
    return os.path.join(context.env_dir, "lib", version, "site-packages")


class RecordedCalls:
    """Replaces `subprocess.check_output` and records each command."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> bytes:
        self.commands.append([str(arg) for arg in args])
        return b""


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> RecordedCalls:
    recorder = RecordedCalls()
    monkeypatch.setattr(subprocess, "check_output", recorder)
    return recorder


class TestBuildingABuilderTouchesNothing:
    """`venv.EnvBuilder(...)` | O(1) | O(1) | stores the options."""

    def test_construction_creates_no_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: Any, **kwargs: Any) -> None:
            raise AssertionError(f"filesystem call at construction: {args}")

        monkeypatch.setattr(os, "makedirs", refuse)
        monkeypatch.setattr(os, "symlink", refuse)
        monkeypatch.setattr(shutil, "copyfile", refuse)

        builder = venv.EnvBuilder(clear=True, with_pip=True, upgrade_deps=True)

        assert (builder.clear, builder.with_pip) == (True, True)


@POSIX_ONLY
class TestTheInterpreterIsCopiedOrLinked:
    """The b term: `create()` copies the executable under each name by
    default, and `symlinks=True` links each name instead, as `python -m venv`
    does on POSIX. A copy is told from a link by `islink` and by size."""

    @staticmethod
    def copies_made(
        monkeypatch: pytest.MonkeyPatch, env: pathlib.Path, **options: Any
    ) -> list[str]:
        """The `shutil.copyfile` calls whose source is an interpreter-sized file:
        the base executable, or the environment's first copy of it."""
        sources: list[str] = []
        original = shutil.copyfile

        def counting(src: Any, dst: Any, **kwargs: Any) -> Any:
            sources.append(os.path.realpath(src))
            return original(src, dst, **kwargs)

        monkeypatch.setattr(shutil, "copyfile", counting)
        venv.create(env, **options)
        monkeypatch.setattr(shutil, "copyfile", original)
        size = os.path.getsize(base_executable())
        return [source for source in sources if os.path.getsize(source) == size]

    def test_the_default_copies_the_executable_under_every_name(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = tmp_path / "env"

        sources = self.copies_made(monkeypatch, env)

        size = os.path.getsize(base_executable())
        for name in INTERPRETER_NAMES:
            path = env / "bin" / name
            assert not path.is_symlink(), f"{name} is a link"
            assert path.stat().st_size == size, f"{name} is not a full copy"
        assert len(sources) >= len(INTERPRETER_NAMES), sources

    def test_symlinks_link_every_name_and_copy_nothing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = tmp_path / "env"

        sources = self.copies_made(monkeypatch, env, symlinks=True)

        assert sources == []
        for name in INTERPRETER_NAMES:
            path = env / "bin" / name
            assert path.is_symlink(), f"{name} is not a link"
            assert os.path.realpath(path) == base_executable()

    def test_the_command_line_links_by_default(self, tmp_path: pathlib.Path) -> None:
        env = tmp_path / "env"

        venv.main([str(env), "--without-pip"])

        assert all((env / "bin" / name).is_symlink() for name in INTERPRETER_NAMES)


@POSIX_ONLY
class TestNothingFromTheInstallationIsCopied:
    """`EnvBuilder.create(env_dir)`: directories, `pyvenv.cfg`, the interpreter
    names and the activation scripts - a fixed handful, not the library."""

    def test_the_environment_is_a_handful_of_small_files(self, tmp_path: pathlib.Path) -> None:
        env = tmp_path / "env"

        venv.create(env, symlinks=True, system_site_packages=True)

        files = files_under(env)
        regular = [path for path in files if not path.is_symlink()]
        total = sum(path.stat().st_size for path in regular)
        assert len(files) < 20, [str(path.relative_to(env)) for path in files]
        assert not [path for path in files if path.suffix == ".py"]
        assert total < 64_000, f"{total} bytes of regular files"

    def test_system_site_packages_is_one_line_of_configuration(
        self, tmp_path: pathlib.Path
    ) -> None:
        env = tmp_path / "env"
        builder = venv.EnvBuilder(symlinks=True, system_site_packages=True)

        builder.create(env)

        context = builder.ensure_directories(env)
        config = (env / "pyvenv.cfg").read_text(encoding="utf-8")
        assert "include-system-site-packages = true\n" in config
        assert f"home = {context.python_dir}\n" in config
        assert os.listdir(site_packages(context)) == []


class TestClearEmptiesTheDirectory:
    """`EnvBuilder(clear=True).create(env_dir)` | O(e + b): every entry already
    there is removed, whether or not venv made it."""

    @staticmethod
    def removals(monkeypatch: pytest.MonkeyPatch, env: pathlib.Path, nested: int) -> int:
        (env / "sub").mkdir(parents=True)
        (env / "notes.txt").write_text("not venv's", encoding="utf-8")
        for index in range(nested):
            (env / "sub" / f"f{index}").touch()
        calls: list[Any] = []
        unlink, remove = os.unlink, os.remove

        def counting_unlink(*args: Any, **kwargs: Any) -> None:
            calls.append(args)
            unlink(*args, **kwargs)

        def counting_remove(*args: Any, **kwargs: Any) -> None:
            calls.append(args)
            remove(*args, **kwargs)

        monkeypatch.setattr(os, "unlink", counting_unlink)
        monkeypatch.setattr(os, "remove", counting_remove)
        venv.create(env, symlinks=True, clear=True)
        monkeypatch.setattr(os, "unlink", unlink)
        monkeypatch.setattr(os, "remove", remove)

        assert not (env / "notes.txt").exists()
        assert not (env / "sub").exists()
        assert (env / "pyvenv.cfg").exists()
        return len(calls)

    @pytest.mark.parametrize("nested", [10, 1_000])
    def test_removals_follow_the_entries_already_there(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, nested: int
    ) -> None:
        entries = nested + 1

        removed = self.removals(monkeypatch, tmp_path / "env", nested)

        assert entries <= removed <= entries + 5, f"{removed} removals for {entries} files"


class TestSubprocesses:
    """`with_pip` adds one `ensurepip` subprocess, `upgrade_deps` one
    `pip install --upgrade`; a default build starts none."""

    def test_a_default_build_starts_no_process(
        self, tmp_path: pathlib.Path, recorded: RecordedCalls
    ) -> None:
        venv.create(tmp_path / "env", symlinks=True)

        assert recorded.commands == []

    def test_with_pip_runs_ensurepip_once(
        self, tmp_path: pathlib.Path, recorded: RecordedCalls
    ) -> None:
        venv.create(tmp_path / "env", symlinks=True, with_pip=True)

        assert len(recorded.commands) == 1
        assert recorded.commands[0][1:3] == ["-m", "ensurepip"]

    def test_upgrade_deps_runs_pip_install_upgrade_once(
        self, tmp_path: pathlib.Path, recorded: RecordedCalls
    ) -> None:
        venv.create(tmp_path / "env", symlinks=True, upgrade_deps=True)

        packages = ["pip"] if sys.version_info >= (3, 12) else ["pip", "setuptools"]
        assert recorded.commands == [
            [recorded.commands[0][0], "-m", "pip", "install", "--upgrade", *packages]
        ]

    def test_both_run_ensurepip_first(
        self, tmp_path: pathlib.Path, recorded: RecordedCalls
    ) -> None:
        venv.create(tmp_path / "env", symlinks=True, with_pip=True, upgrade_deps=True)

        assert [command[2] for command in recorded.commands] == ["ensurepip", "pip"]


class TestRealPipRuns:
    """The only tests that run code in a new environment's interpreter
    beyond `sys.prefix`: one real `ensurepip`, and one `upgrade_deps` that
    fails before reaching the network because pip is absent."""

    def test_with_pip_installs_the_bundled_pip_without_a_network(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            monkeypatch.setenv(variable, "http://127.0.0.1:9")
            monkeypatch.setenv(variable.lower(), "http://127.0.0.1:9")
        monkeypatch.setenv("PIP_RETRIES", "0")
        monkeypatch.setenv("PIP_TIMEOUT", "1")
        bare, with_pip = tmp_path / "bare", tmp_path / "with_pip"
        venv.create(bare, symlinks=True)
        builder = venv.EnvBuilder(symlinks=True, with_pip=True)

        builder.create(with_pip)

        context = builder.ensure_directories(with_pip)
        installed = os.listdir(site_packages(context))
        assert any(name.startswith("pip-") for name in installed), installed
        has_setuptools = any(name.startswith("setuptools") for name in installed)
        assert has_setuptools is (sys.version_info < (3, 12)), installed
        subprocess.run([context.env_exe, "-c", "import pip"], check=True)
        ratio = len(files_under(with_pip)) / len(files_under(bare))
        assert ratio > 10, f"pip added only x{ratio:.1f} the files"

    def test_upgrade_deps_without_pip_fails(
        self, tmp_path: pathlib.Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        builder = venv.EnvBuilder(symlinks=True, upgrade_deps=True)

        with pytest.raises(subprocess.CalledProcessError):
            builder.create(tmp_path / "env")

        assert "No module named pip" in capfd.readouterr().err


class Recording(venv.EnvBuilder):
    """An `EnvBuilder` that records each hook and the context it received."""

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.calls: list[tuple[str, Any]] = []

    def ensure_directories(self, env_dir: Any) -> Any:
        context = super().ensure_directories(env_dir)
        self.calls.append(("ensure_directories", context))
        return context

    def create_git_ignore_file(self, context: Any) -> None:
        self.calls.append(("create_git_ignore_file", context))
        super().create_git_ignore_file(context)  # type: ignore[misc]

    def create_configuration(self, context: Any) -> None:
        self.calls.append(("create_configuration", context))
        super().create_configuration(context)

    def setup_python(self, context: Any) -> None:
        self.calls.append(("setup_python", context))
        super().setup_python(context)

    def setup_scripts(self, context: Any) -> None:
        self.calls.append(("setup_scripts", context))
        super().setup_scripts(context)

    def install_scripts(self, context: Any, path: Any) -> None:
        self.calls.append(("install_scripts", context))
        super().install_scripts(context, path)

    def post_setup(self, context: Any) -> None:
        self.calls.append(("post_setup", context))
        super().post_setup(context)

    def upgrade_dependencies(self, context: Any) -> None:
        self.calls.append(("upgrade_dependencies", context))

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class TestHooks:
    """The customisation hooks run in the listed order on one context;
    `upgrade=True` skips the scripts and `post_setup()`."""

    def test_the_hooks_run_in_order_on_one_context(self, tmp_path: pathlib.Path) -> None:
        options: dict[str, Any] = {"symlinks": True, "upgrade_deps": True}
        expected = [
            "ensure_directories",
            "create_configuration",
            "setup_python",
            "setup_scripts",
            "install_scripts",
            "post_setup",
            "upgrade_dependencies",
        ]
        if sys.version_info >= (3, 13):
            options["scm_ignore_files"] = {"git"}
            expected.insert(1, "create_git_ignore_file")
        builder = Recording(**options)

        builder.create(tmp_path / "env")

        assert builder.names == expected
        assert len({id(context) for _, context in builder.calls}) == 1

    def test_upgrade_skips_the_scripts_and_post_setup(self, tmp_path: pathlib.Path) -> None:
        env = tmp_path / "env"
        venv.create(env, symlinks=True)
        context = venv.EnvBuilder().ensure_directories(str(env))
        kept = pathlib.Path(site_packages(context)) / "installed.pth"
        kept.write_text("", encoding="utf-8")
        config = env / "pyvenv.cfg"
        config.write_text("stale\n", encoding="utf-8")
        builder = Recording(symlinks=True, upgrade=True)

        builder.create(env)

        assert "setup_scripts" not in builder.names
        assert "post_setup" not in builder.names
        assert "setup_python" in builder.names
        assert "home = " in config.read_text(encoding="utf-8")
        assert kept.exists()

    def test_ensure_directories_creates_no_regular_file(self, tmp_path: pathlib.Path) -> None:
        env = tmp_path / "env"

        context = venv.EnvBuilder().ensure_directories(str(env))

        assert [path for path in files_under(env) if not path.is_symlink()] == []
        assert os.path.isdir(context.bin_path)
        assert os.path.isdir(site_packages(context))
        assert context.env_dir == str(env)

    def test_ensure_directories_on_an_existing_tree_changes_nothing(
        self, tmp_path: pathlib.Path
    ) -> None:
        env = tmp_path / "env"
        venv.create(env, symlinks=True)
        before = {path: path.lstat().st_mtime_ns for path in files_under(env)}

        venv.EnvBuilder().ensure_directories(env)

        assert {path: path.lstat().st_mtime_ns for path in files_under(env)} == before

    def test_post_setup_does_nothing(self, tmp_path: pathlib.Path) -> None:
        env = tmp_path / "env"
        builder = venv.EnvBuilder()
        context = builder.ensure_directories(env)
        before = sorted(files_under(env))

        builder.post_setup(context)

        assert sorted(files_under(env)) == before


class TestInstallScripts:
    """`install_scripts(context, path)` | O(t): the templates under the
    `common` and `os.name` subdirectories, placeholders replaced."""

    @staticmethod
    def templates(root: pathlib.Path, body: str) -> pathlib.Path:
        for directory in ("common", os.name, "common/nested", "elsewhere"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / "common" / "run").write_text(body, encoding="utf-8")
        (root / "common" / "nested" / "deep").write_text("__VENV_PROMPT__", encoding="utf-8")
        (root / os.name / "platform").write_text("x", encoding="utf-8")
        (root / "elsewhere" / "skipped").write_text("x", encoding="utf-8")
        (root / "top-level").write_text("x", encoding="utf-8")
        return root

    def test_the_right_files_are_installed_with_placeholders_replaced(
        self, tmp_path: pathlib.Path
    ) -> None:
        builder = venv.EnvBuilder(prompt="demo")
        context = builder.ensure_directories(str(tmp_path / "env"))
        source = self.templates(tmp_path / "templates", "cd __VENV_DIR__\n")

        builder.install_scripts(context, str(source))

        bin_path = pathlib.Path(context.bin_path)
        installed = sorted(str(path.relative_to(bin_path)) for path in files_under(bin_path))
        assert installed == sorted(["run", os.path.join("nested", "deep"), "platform"])
        assert str(tmp_path / "env") in (bin_path / "run").read_text(encoding="utf-8")
        assert "demo" in (bin_path / "nested" / "deep").read_text(encoding="utf-8")

    def test_the_output_is_the_size_of_the_template(self, tmp_path: pathlib.Path) -> None:
        builder = venv.EnvBuilder()
        context = builder.ensure_directories(str(tmp_path / "env"))
        body = "echo __VENV_DIR__\n" + "#" * 200_000 + "\n"
        source = self.templates(tmp_path / "templates", body)

        builder.install_scripts(context, str(source))

        size = (pathlib.Path(context.bin_path) / "run").stat().st_size
        assert abs(size - len(body)) < 500, f"{size} bytes from a {len(body)}-byte template"


class TestScmIgnoreFiles:
    """`scm_ignore_files` and `create_git_ignore_file()` are Python 3.13+;
    only the command line asks for a `.gitignore` by default."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_the_builder_writes_none_by_default(self, tmp_path: pathlib.Path) -> None:
        venv.create(tmp_path / "env", symlinks=True)

        assert not (tmp_path / "env" / ".gitignore").exists()

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_git_writes_an_ignore_everything_file(self, tmp_path: pathlib.Path) -> None:
        venv.create(tmp_path / "env", symlinks=True, scm_ignore_files={"git"})  # type: ignore[call-arg]

        lines = (tmp_path / "env" / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert "*" in lines

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_the_command_line_writes_one_unless_told_not_to(self, tmp_path: pathlib.Path) -> None:
        venv.main([str(tmp_path / "default"), "--without-pip"])
        venv.main([str(tmp_path / "without"), "--without-pip", "--without-scm-ignore-files"])

        assert (tmp_path / "default" / ".gitignore").exists()
        assert not (tmp_path / "without" / ".gitignore").exists()

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="exists from 3.13")
    def test_before_313_there_is_no_such_option(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(TypeError):
            venv.EnvBuilder(scm_ignore_files={"git"})  # type: ignore[call-arg]

        venv.main([str(tmp_path / "env"), "--without-pip"])

        assert not hasattr(venv.EnvBuilder, "create_git_ignore_file")
        assert not (tmp_path / "env" / ".gitignore").exists()


class TestUsingAnEnvironmentWithoutActivating:
    """Running the environment's interpreter by path uses the environment;
    activation is a shell script that sets `PATH`."""

    def test_the_interpreter_by_path_sees_the_environment(self, tmp_path: pathlib.Path) -> None:
        env = tmp_path / "env"
        builder = venv.EnvBuilder(symlinks=True)
        builder.create(env)
        context = builder.ensure_directories(env)

        output = subprocess.run(
            [context.env_exe, "-c", "import sys; print(sys.prefix); print(sys.base_prefix)"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()

        assert os.path.realpath(output[0]) == os.path.realpath(env)
        assert output[1] == sys.base_prefix

    @POSIX_ONLY
    def test_the_activate_script_sets_path_for_this_environment(
        self, tmp_path: pathlib.Path
    ) -> None:
        env = tmp_path / "env"
        venv.create(env, symlinks=True)

        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash is needed to source the activate script")

        output = subprocess.run(
            [bash, "-c", '. "$1" && printf "%s\\n" "$PATH"', "bash", str(env / "bin" / "activate")],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PATH": "/usr/bin:/bin"},
        ).stdout

        first, _, rest = output.strip().partition(os.pathsep)
        assert os.path.realpath(first) == os.path.realpath(env / "bin")
        assert rest == "/usr/bin:/bin"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows environment layout")
class TestWindowsLayout:
    """Kind D: on Windows the scripts directory is `Scripts`, a copy installs a
    launcher rather than the interpreter, and the `.bat` scripts are added."""

    def test_copies_install_a_launcher_and_batch_scripts(self, tmp_path: pathlib.Path) -> None:
        import filecmp

        env = tmp_path / "env"
        venv.create(env)

        scripts = env / "Scripts"
        assert (scripts / "python.exe").exists()
        assert not (scripts / "python.exe").is_symlink()
        assert not filecmp.cmp(scripts / "python.exe", sys._base_executable, shallow=False)  # type: ignore[attr-defined]  # noqa: SLF001
        assert (scripts / "activate.bat").exists()
        assert (scripts / "Activate.ps1").exists()
        assert not (scripts / "activate.csh").exists()


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


def _run_block(
    source: str, cwd: pathlib.Path, tmp: pathlib.Path
) -> subprocess.CompletedProcess[str]:
    script = cwd.parent / f"{cwd.name}.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "TMPDIR": str(tmp), "TEMP": str(tmp)},
        check=False,
    )


@POSIX_ONLY
class TestDocumentedExamples:
    """Each block runs in its own subprocess with an empty working directory
    and an empty temporary directory, both of which must still be empty
    afterwards: no example leaves an environment behind. The blocks use the POSIX `bin` layout."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs_and_leaves_nothing_behind(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            tmp = tmp_path / f"tmp{line}"
            tmp.mkdir()
            result = _run_block(source, workdir, tmp)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")
            elif os.listdir(workdir) or os.listdir(tmp):
                failures.append(f"{PAGE.name}:{line} left {os.listdir(workdir) + os.listdir(tmp)}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = "assert not os.path.exists(os.path.join(env, 'notes.txt'))"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, target.replace("assert not", "assert"), 1)
        workdir = tmp_path / "mutated"
        workdir.mkdir()
        tmp = tmp_path / "mutated-tmp"
        tmp.mkdir()

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, workdir, tmp).returncode != 0
