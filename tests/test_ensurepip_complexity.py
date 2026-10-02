"""Tests for docs/stdlib/ensurepip.md.

The page prices `bootstrap()` as one pip install of the bundled wheels, run in
a child interpreter, and `version()` as a file-name read. Those claims are
settled by observation: the command `bootstrap()` hands to `subprocess.run`,
the wheels it has copied when it does, what it leaves in `os.environ`, the
scripts and versions real installs leave behind, and the file system calls
`version()` makes. No test here depends on a stopwatch. Every real install
goes under `tmp_path`, either through `root=` or into a new environment.

Measurement scope:

* With `subprocess.run` in `ensurepip` replaced by a recorder, `bootstrap()`
  starts exactly one process, running this interpreter with a `pip install`
  that carries `--no-index` and `--find-links` and names `pip` (and
  `setuptools` before 3.12). At the moment of the call the temporary
  directory holds the bundled wheel files, `pip-*.whl` (and `setuptools-*.whl`
  before 3.12), and nothing else; the directory is gone once `bootstrap()`
  returns. It returns `None`. `root`, `upgrade`, `user` and `verbosity=2`
  reach the command as `--root` with the given path, `--upgrade`, `--user`
  and `-vv`, and leave the process count at one.
* `altinstall=True` with `default_pip=True` raises `ValueError` with the
  recorder never called.
* `os.environ` after a recorded `bootstrap()` has no `PIP_INDEX_URL` that was
  set before it, and `PIP_CONFIG_FILE` is `os.devnull`; a child interpreter
  started afterwards sees the same.
* Real installs under `root=`, each in a child of an environment built
  without pip: the default leaves exactly the `pipX` and `pipX.Y` scripts,
  `default_pip=True` adds `pip`, and `altinstall=True` leaves only `pipX.Y`.
  One process that calls `bootstrap()` and then `bootstrap(default_pip=True)`
  gets no `pip` from the second call. A `root` that is a regular file makes
  pip fail and `bootstrap()` raise `subprocess.CalledProcessError`.
* `upgrade`: in a new environment built without pip, `bootstrap()` installs
  the bundled version; with the installed pip relabelled `1.0` (its
  dist-info directory, RECORD paths and METADATA version), a second
  `bootstrap()` leaves `1.0` installed, one with `root=` installs no script
  under the root and leaves `1.0`, and one with `upgrade=True` installs the
  bundled version again.
* `version()` equals the version in the bundled wheel's file name under
  `ensurepip/_bundled`. After one warm-up call, a second makes no
  `subprocess.run` call and succeeds with `open`, `io.open`, `os.listdir`,
  `os.scandir` and `os.stat` replaced by functions that raise, so it reads
  nothing from disk. Pointed at a directory holding `pip-99.0-py3-none-any.whl`
  (and a setuptools wheel before 3.12, which needs both), it reports `99.0`.
* `python -m ensurepip --version` prints `pip <version()>` and creates
  nothing in its working directory.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That the cost is O(p) in the bundled wheels' size is read from
  Lib/ensurepip/__init__.py, which copies the wheels and hands them to one
  `pip install`. One wheel set per interpreter exists, so p is never varied.
* `python -m ensurepip` with install options is read from `_main()` in
  Lib/ensurepip/__init__.py, which passes them to the same `_bootstrap()`; it
  is not run with options here.
* That the bundled pip changes between patch releases is read from the
  release tags: 3.14.2 bundles pip 25.3 in Lib/ensurepip/_bundled. That some
  Linux distributions remove the module or configure `--with-wheel-pkg-dir`
  is distribution packaging, not something this interpreter can show.
* The cost on a `--with-wheel-pkg-dir` build is not priced: `version()` then
  lists that directory, which is read from Lib/ensurepip/__init__.py.
"""

from __future__ import annotations

import builtins
import ensurepip
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import types
import venv
from collections.abc import Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ensurepip.md"
EXPECTED_BLOCKS = 2
BUNDLES_SETUPTOOLS = sys.version_info < (3, 12)
PACKAGES = ["setuptools", "pip"] if BUNDLES_SETUPTOOLS else ["pip"]


class RecordedRun:
    """Stands in for `subprocess.run` inside `ensurepip`, keeping each command
    and the wheel files present when it was called."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.wheel_dirs: list[str] = []
        self.wheels: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(cmd))
        code = cmd[-1]
        match = re.search(r"'--find-links', '([^']+)'", code)
        assert match, code
        self.wheel_dirs.append(match.group(1))
        self.wheels.append(sorted(os.listdir(match.group(1))))
        return subprocess.CompletedProcess(cmd, 0)


@pytest.fixture
def saved_environ() -> Iterator[None]:
    saved = dict(os.environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch, saved_environ: None) -> RecordedRun:
    recorder = RecordedRun()
    stand_in = types.SimpleNamespace(run=recorder, CalledProcessError=subprocess.CalledProcessError)
    monkeypatch.setattr(ensurepip, "subprocess", stand_in)
    return recorder


def scripts_under(root: pathlib.Path) -> set[str]:
    """Names of the pip scripts installed anywhere under `root`."""
    return {
        path.name.removesuffix(".exe")
        for path in root.rglob("pip*")
        if path.parent.name in ("bin", "Scripts") and path.is_file()
    }


class TestBootstrapRunsOnePipInstall:
    """`bootstrap()` row: "One child interpreter runs pip with `--no-index`, so
    nothing is downloaded". The recorder shows the single command and what the
    wheel directory held when pip would have read it."""

    def test_it_starts_one_process(self, recorded: RecordedRun) -> None:
        assert ensurepip.bootstrap() is None

        assert len(recorded.commands) == 1
        assert recorded.commands[0][0] == sys.executable

    def test_the_install_is_offline_and_names_the_bundled_packages(
        self, recorded: RecordedRun
    ) -> None:
        ensurepip.bootstrap()

        code = recorded.commands[0][-1]
        assert "'install'" in code
        assert "'--no-index'" in code
        assert "'--find-links'" in code
        for package in PACKAGES:
            assert f"'{package}'" in code
        assert ("'setuptools'" in code) is BUNDLES_SETUPTOOLS

    def test_the_wheel_directory_holds_only_the_bundled_wheels(self, recorded: RecordedRun) -> None:
        ensurepip.bootstrap()

        wheels = recorded.wheels[0]
        assert len(wheels) == len(PACKAGES), wheels
        for package in PACKAGES:
            assert any(name.startswith(f"{package}-") and name.endswith(".whl") for name in wheels)
        assert not os.path.exists(recorded.wheel_dirs[0])

    def test_options_change_the_command_not_the_process_count(
        self, recorded: RecordedRun, tmp_path: pathlib.Path
    ) -> None:
        ensurepip.bootstrap(root=str(tmp_path), upgrade=True, user=True, verbosity=2)

        assert len(recorded.commands) == 1
        code = recorded.commands[0][-1]
        assert f"'--root', {str(tmp_path)!r}" in code
        for option in ("'--upgrade'", "'--user'", "'-vv'"):
            assert option in code

    def test_altinstall_with_default_pip_raises_before_anything_runs(
        self, recorded: RecordedRun
    ) -> None:
        with pytest.raises(ValueError, match="altinstall"):
            ensurepip.bootstrap(altinstall=True, default_pip=True)

        assert recorded.commands == []


class TestBootstrapChangesTheEnvironment:
    """ "deletes every `PIP_*` variable from `os.environ` and points
    `PIP_CONFIG_FILE` at the null device ... every child process started
    afterwards inherits it"."""

    def test_pip_variables_are_removed_and_the_config_file_nulled(
        self, recorded: RecordedRun
    ) -> None:
        os.environ["PIP_INDEX_URL"] = "http://127.0.0.1:9/simple"

        ensurepip.bootstrap()

        assert "PIP_INDEX_URL" not in os.environ
        assert os.environ["PIP_CONFIG_FILE"] == os.devnull

    def test_a_later_child_process_inherits_the_change(self, recorded: RecordedRun) -> None:
        os.environ["PIP_INDEX_URL"] = "http://127.0.0.1:9/simple"
        ensurepip.bootstrap()

        seen = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ.get('PIP_INDEX_URL'), os.environ['PIP_CONFIG_FILE'])",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()

        assert seen == ["None", os.devnull]


def new_environment(path: pathlib.Path) -> str:
    """Build an environment without pip at `path` and return its interpreter."""
    builder = venv.EnvBuilder(symlinks=os.name != "nt")
    builder.create(path)
    return builder.ensure_directories(path).env_exe


def bootstrap_in(python: str, *calls: str) -> None:
    """Run `ensurepip.bootstrap(...)` once per entry of `calls`, in order, in
    one process of `python`."""
    code = "import ensurepip\n" + "".join(f"ensurepip.bootstrap({call})\n" for call in calls)
    subprocess.run([python, "-c", code], capture_output=True, check=True)


@pytest.fixture(scope="module")
def pip_free_python(tmp_path_factory: pytest.TempPathFactory) -> str:
    """An interpreter that cannot import pip, so an install under `root=`
    is not skipped as already satisfied."""
    python = new_environment(tmp_path_factory.mktemp("pip-free") / "env")
    probe = subprocess.run([python, "-c", "import pip"], capture_output=True, check=False)
    assert probe.returncode != 0
    return python


MAJOR_MINOR = f"pip{sys.version_info.major}.{sys.version_info.minor}"


class TestRealInstalls:
    """The script rows, and the `CalledProcessError` in the `bootstrap()` row,
    from real installs under `root=` by an interpreter without pip."""

    def test_the_default_installs_pipx_and_pipxy(
        self, pip_free_python: str, tmp_path: pathlib.Path
    ) -> None:
        bootstrap_in(pip_free_python, f"root={str(tmp_path)!r}")

        assert scripts_under(tmp_path) == {"pip3", MAJOR_MINOR}

    def test_default_pip_adds_pip(self, pip_free_python: str, tmp_path: pathlib.Path) -> None:
        bootstrap_in(pip_free_python, f"root={str(tmp_path)!r}, default_pip=True")

        assert scripts_under(tmp_path) == {"pip", "pip3", MAJOR_MINOR}

    def test_altinstall_installs_only_pipxy(
        self, pip_free_python: str, tmp_path: pathlib.Path
    ) -> None:
        bootstrap_in(pip_free_python, f"root={str(tmp_path)!r}, altinstall=True")

        assert scripts_under(tmp_path) == {MAJOR_MINOR}

    def test_default_pip_after_an_earlier_call_adds_no_pip(
        self, pip_free_python: str, tmp_path: pathlib.Path
    ) -> None:
        first, second = tmp_path / "first", tmp_path / "second"

        bootstrap_in(
            pip_free_python, f"root={str(first)!r}", f"root={str(second)!r}, default_pip=True"
        )

        assert scripts_under(second) == {"pip3", MAJOR_MINOR}

    def test_a_failing_pip_raises_called_process_error(
        self, pip_free_python: str, tmp_path: pathlib.Path
    ) -> None:
        not_a_directory = tmp_path / "file"
        not_a_directory.write_text("", encoding="utf-8")
        code = (
            "import ensurepip, subprocess\n"
            "try:\n"
            f"    ensurepip.bootstrap(root={str(not_a_directory)!r})\n"
            "except subprocess.CalledProcessError:\n"
            "    print('raised')\n"
        )

        result = subprocess.run(
            [pip_free_python, "-c", code], capture_output=True, text=True, check=True
        )

        assert result.stdout.splitlines()[-1] == "raised"


class TestUpgrade:
    """`bootstrap(upgrade=True)` row: "Without it, a pip the running
    interpreter already has, of any version, satisfies the request, even with
    `root`, and no pip is installed". An older pip is simulated by relabelling
    the installed one."""

    @staticmethod
    def installed_version(python: str) -> str:
        return subprocess.run(
            [python, "-c", "from importlib import metadata; print(metadata.version('pip'))"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    @staticmethod
    def pretend_installed_is_older(site: pathlib.Path, bundled: str) -> None:
        """Relabel the installed pip as 1.0: its dist-info directory, the
        paths its RECORD lists, and the version in its METADATA."""
        old = site / f"pip-{bundled}.dist-info"
        new = old.rename(site / "pip-1.0.dist-info")
        for name, before, after in (
            ("METADATA", f"Version: {bundled}\n", "Version: 1.0\n"),
            ("RECORD", old.name, new.name),
        ):
            text = (new / name).read_text(encoding="utf-8")
            rewritten = text.replace(before, after)
            assert rewritten != text, name
            (new / name).write_text(rewritten, encoding="utf-8")

    def test_an_older_pip_is_replaced_only_with_upgrade(self, tmp_path: pathlib.Path) -> None:
        python = new_environment(tmp_path / "env")
        bundled = ensurepip.version()

        bootstrap_in(python, "")
        assert self.installed_version(python) == bundled

        site = pathlib.Path(
            subprocess.run(
                [python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        self.pretend_installed_is_older(site, bundled)
        assert self.installed_version(python) == "1.0"

        bootstrap_in(python, "")
        assert self.installed_version(python) == "1.0"

        root = tmp_path / "root"
        bootstrap_in(python, f"root={str(root)!r}")
        assert scripts_under(root) == set()
        assert self.installed_version(python) == "1.0"

        bootstrap_in(python, "upgrade=True")
        assert self.installed_version(python) == bundled


class TestVersionRunsNothing:
    """`version()` row: "The bundled pip's version string; nothing is run or
    installed"."""

    def test_it_matches_the_bundled_wheel(self) -> None:
        bundled = pathlib.Path(ensurepip.__file__).parent / "_bundled"
        (wheel,) = bundled.glob("pip-*.whl")

        assert wheel.name == f"pip-{ensurepip.version()}-py3-none-any.whl"

    def test_it_runs_nothing_and_reads_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        expected = ensurepip.version()

        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError(f"version() touched the disk or ran something: {args!r}")

        for module, name in (
            (subprocess, "run"),
            (builtins, "open"),
            (io, "open"),
            (os, "listdir"),
            (os, "scandir"),
            (os, "stat"),
        ):
            monkeypatch.setattr(module, name, refuse)
        try:
            result = ensurepip.version()
        finally:
            monkeypatch.undo()

        assert result == expected

    def test_a_wheel_package_directory_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "pip-99.0-py3-none-any.whl").write_bytes(b"")
        (tmp_path / "setuptools-99.0-py3-none-any.whl").write_bytes(b"")
        if sys.version_info >= (3, 13):
            monkeypatch.setattr(ensurepip, "_WHEEL_PKG_DIR", tmp_path)
        else:
            monkeypatch.setattr(ensurepip, "_WHEEL_PKG_DIR", str(tmp_path))
            monkeypatch.setattr(ensurepip, "_PACKAGES", None)

        assert ensurepip.version() == "99.0"


class TestCommandLine:
    """`python -m ensurepip --version` row: "Prints the bundled pip's version
    and installs nothing". Observed as the printed version and an empty
    working directory."""

    def test_version_prints_and_creates_nothing(self, tmp_path: pathlib.Path) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ensurepip", "--version"],
            capture_output=True,
            text=True,
            check=True,
            cwd=tmp_path,
        )

        assert result.stdout.strip() == f"pip {ensurepip.version()}"
        assert list(tmp_path.iterdir()) == []


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
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, so the
    environment `bootstrap()` changes cannot leak, and asserts its own
    result. The install block installs into a new environment built without
    pip, in a temporary directory."""

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
        line, source = next((n, s) for n, s in _blocks() if "f'pip {bundled}'" in s)
        mutated = source.replace("f'pip {bundled}'", "f'pip {bundled}x'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
