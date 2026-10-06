"""Tests for docs/stdlib/idlelib.md.

The page prices only IDLE's public surface: importing the package and
starting the application from the command line. There is no display here or
in CI, so nothing creates a Tk window. Startup is instead driven through the
real `idlelib.pyshell.main()` in a subprocess whose Tk root, icon images
and `PyShellFileList` are recording stand-ins, and whose Tk type is preset
so that `idlelib.macosx` does not create a root of its own on macOS, and a file load
through the real `IOBinding.loadfile()` with a recording editor window. Every
subprocess runs with `HOME` set to its own temporary directory, because
loading IDLE's configuration creates `~/.idlerc`, and without `DISPLAY` or
`WAYLAND_DISPLAY`.

Measurement scope:

* `import idlelib` in a fresh interpreter leaves `idlelib` as the only
  module whose name contains "idlelib" or "tk" in `sys.modules`, and the
  package's only public name is `testing`, which is `False`. The package
  docstring is asserted to call the other files private implementations.
* `python -m idlelib -h` exits 0 with the usage on standard output and no
  `TclError`. On Linux, `python -m idlelib` with no option exits non-zero
  with `TclError`, which is the control showing the environment has no
  display.
* Starting with 3 and with 30 file names creates the root once, then calls
  `PyShellFileList.open()` exactly once per name, in order, and under the
  default configuration opens no shell window and no empty editor, and
  destroys the root once. With `-` and a script on standard input, one
  `sys.stdin.read()` returns the whole script before the root is created,
  and the shell then runs exactly that text through `execsource()`.
* Twenty files in twenty new directories, plus a second file in the first
  of them, leave those directories at the front of `sys.path` in reverse
  order, each once. Every directory is tested for membership in a list that
  has grown by one per earlier new directory, which is the f² term; that
  cost is read from list semantics and is not timed.
* `IOBinding.loadfile()` on a 2,000-line file of 100,000 characters inserts
  the whole content with one `insert('1.0', ...)` call.
* On Linux, `python -m idlelib -` with standard input held open is still
  running after `python -m idlelib`, started alongside it the same way, has
  already failed at `Tk()`, and at least a second more; once standard input
  closes, it fails at `Tk()` too. So standard input is read to its end before
  any window is asked for.
* Lib/idlelib/__init__.py, __main__.py and idle.py, and `pyshell.main()`
  apart from message formatting and a macOS Tk version warning, are the same
  in the v3.10.19, v3.11.14, v3.12.12, v3.13.11 and v3.14.2 tags, so no
  bound on the page moves inside the supported range. The helpers `main()`
  applies to the root move within a minor version - 3.14.7 imports
  `fix_scaling` and `fix_x11_paste` from `idlelib.util` - so the stand-in
  root answers their calls rather than the helpers being replaced. The
  tests pass on 3.10.21, 3.11.16, 3.12.14, 3.13.14 and 3.14.7.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `PyShellFileList.open()` builds an `EditorWindow` whose `IOBinding`
  loads the named file is read from Lib/idlelib/filelist.py and editor.py;
  the stand-in list records the call instead of building a window. That a
  file named twice raises its existing window rather than opening a second
  is read from `FileList.open()` and is not exercised.
* That the default startup launches a second interpreter running
  `idlelib.run` and talks to it over a socket on 127.0.0.1 is read from
  Lib/idlelib/pyshell.py and the IDLE documentation; it needs a real shell
  window and is not run.
* The cost of Tk, the window system, syntax colouring, the user-code
  process, and code run by `-c` or `-r` is not priced by the page. The
  interpreter's own `sys.path` entries, which `main()` also makes absolute,
  are held at their default count and not varied.
* The display failure is Linux (X11) behaviour; on macOS and Windows Tk
  needs no `DISPLAY`, so the tests that rely on it skip there.
* The private modules - the editor, shell, colorizer, debugger and the rest
  of idlelib - are not documented, as the package docstring and PEP 434 mark
  them as implementation that can change in a bugfix release. The official
  API inventory lists no name inside `idlelib`, so the shared public API audit
  checks only that this page exists; the page's table is its name coverage.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "idlelib.md"
EXPECTED_BLOCKS = 2

try:
    import tkinter  # noqa: F401

    HAS_TK = True
except ImportError:
    HAS_TK = False

needs_tk = pytest.mark.skipif(not HAS_TK, reason="missing tkinter: this build has no tkinter")
linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="Tk needs DISPLAY only on X11"
)


def quiet_env(home: pathlib.Path) -> dict[str, str]:
    """The environment with no display and `home` as the home directory everywhere."""
    env = dict(os.environ)
    for name in ("DISPLAY", "WAYLAND_DISPLAY"):
        env.pop(name, None)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # what expanduser("~") reads on Windows
    return env


def run_python(
    args: list[str], cwd: pathlib.Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the interpreter with `args` in `cwd`, headless."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        env=quiet_env(cwd),
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def run_script(source: str, cwd: pathlib.Path, stdin: str | None = None) -> str:
    """Run `source` headless and return its standard output; fail on error."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    result = run_python([str(script)], cwd, stdin)
    assert result.returncode == 0, result.stderr
    return result.stdout


# Runs the real pyshell.main() with every Tk-facing call replaced. It prints
# the calls the stand-in file list and shell received, one repr per line.
MAIN_HARNESS = """
import sys

import idlelib.pyshell as pyshell
from idlelib import macosx

calls = []


class Tcl:
    def call(self, *args):
        return "1.0"  # read as the display scaling, so fonts are not adjusted


class Root:
    tk = Tcl()
    _windowingsystem = "x11"

    def bind_class(self, *args):
        return ""

    def withdraw(self):
        pass

    def wm_iconphoto(self, *args):
        pass

    def wm_iconbitmap(self, *args, **kwargs):
        pass

    def mainloop(self):
        raise AssertionError("mainloop with no window open")

    def destroy(self):
        calls.append(("destroy",))


class Interp:
    def runcommand(self, source):
        calls.append(("runcommand",))

    def execsource(self, source):
        calls.append(("execsource", source))


class Shell:
    interp = Interp()
    executing = False


class FileList:
    def __init__(self, root):
        self.inversedict = {}
        self.dict = {}
        self.pyshell = None

    def open(self, filename):
        calls.append(("open", filename))
        return object()

    def new(self):
        calls.append(("new",))

    def open_shell(self):
        calls.append(("open_shell",))
        return Shell()




class Stdin:
    def __init__(self, stream):
        self.stream = stream

    def read(self, *args):
        text = self.stream.read(*args)
        calls.append(("stdin.read", len(text)))
        return text


def tk(className):
    calls.append(("Tk",))
    return Root()


sys.stdin = Stdin(sys.stdin)
pyshell.Tk = tk
pyshell.NoDefaultRoot = lambda: None
pyshell.PhotoImage = lambda **kwargs: None
pyshell.PyShellFileList = FileList
macosx.setupApp = lambda root, flist: None
macosx._tk_type = "other"  # on macOS, isAquaTk() would otherwise create a real Tk()

sys.argv = ["idle", *ARGS]
pyshell.main()
print(repr(calls))
print(repr(sys.path))
"""


def run_main(
    args: list[str], cwd: pathlib.Path, stdin: str | None = None
) -> tuple[list[tuple], list[str]]:
    """The calls `pyshell.main()` makes on the stand-ins, and `sys.path` after it."""
    source = MAIN_HARNESS.replace("ARGS", repr(args), 1)
    assert source != MAIN_HARNESS
    output = run_script(source, cwd, stdin)
    calls, path = output.splitlines()
    return ast.literal_eval(calls), ast.literal_eval(path)


class TestImportingThePackageLoadsNothing:
    """`import idlelib` | O(1) | O(1): one flag, no submodule, not tkinter.
    Importing any IDLE module would add an `idlelib.` entry, and anything
    touching Tk would add `tkinter` or `_tkinter`."""

    def test_only_the_package_is_loaded(self, tmp_path: pathlib.Path) -> None:
        output = run_script(
            """
            import sys

            import idlelib

            print(sorted(m for m in sys.modules if "idlelib" in m or "tk" in m))
            print(sorted(n for n in vars(idlelib) if not n.startswith("_")))
            print(idlelib.testing)
            """,
            tmp_path,
        )

        assert output.splitlines() == ["['idlelib']", "['testing']", "False"]

    def test_the_package_marks_its_other_files_private(self, tmp_path: pathlib.Path) -> None:
        output = run_script("import idlelib; print(idlelib.__doc__)", tmp_path)

        assert "The other files are private implementations" in output


@needs_tk
class TestHelpNeedsNoDisplay:
    """`python -m idlelib -h` | O(1) | O(1): the usage is printed while the
    options are parsed, before `Tk()`. The Linux control shows the same
    environment cannot create a window."""

    def test_help_prints_the_usage_and_exits_cleanly(self, tmp_path: pathlib.Path) -> None:
        result = run_python(["-m", "idlelib", "-h"], tmp_path)

        assert result.returncode == 0, result.stderr
        assert "USAGE: idle" in result.stdout
        assert "TclError" not in result.stderr

    @linux_only
    def test_without_help_the_same_environment_fails_at_tk(self, tmp_path: pathlib.Path) -> None:
        result = run_python(["-m", "idlelib"], tmp_path)

        assert result.returncode != 0
        assert "TclError" in result.stderr


@needs_tk
class TestStartupOpensOneWindowPerFile:
    """`python -m idlelib [options] [file ...]` | O(f² + s) | O(f + s): one
    editor window per file named, each file read whole, and each new
    directory added to a `sys.path` that grows per file. The window count is
    the stand-in file list's `open()` calls; the read is `loadfile()`'s one
    insert of the whole text; the growth is `sys.path` after `main()`."""

    @pytest.mark.parametrize("count", [3, 30])
    def test_each_file_named_is_opened_once_in_order(
        self, tmp_path: pathlib.Path, count: int
    ) -> None:
        names = [f"file{index}.py" for index in range(count)]

        calls, _ = run_main(names, tmp_path)

        assert calls == [("Tk",), *(("open", name) for name in names), ("destroy",)]

    def test_each_new_directory_joins_the_front_of_sys_path_once(
        self, tmp_path: pathlib.Path
    ) -> None:
        # Each directory is a membership test over sys.path, which grows by one
        # per new directory: the f-squared term of the startup row.
        names = [str(tmp_path / f"dir{index}" / "file.py") for index in range(20)]
        names.append(str(tmp_path / "dir0" / "other.py"))
        directories = [str(tmp_path / f"dir{index}") for index in range(20)]

        _, path = run_main(names, tmp_path)

        assert path[:20] == directories[::-1]
        assert path.count(directories[0]) == 1

    def test_loadfile_inserts_the_whole_file_at_once(self, tmp_path: pathlib.Path) -> None:
        output = run_script(
            """
            from idlelib.iomenu import IOBinding

            path = "big.py"
            content = "".join(f"x = {index:045d}\\n" for index in range(2_000))
            assert len(content) == 100_000
            with open(path, "w", encoding="utf-8", newline="\\n") as file:
                file.write(content)

            inserts = []

            class Text:
                def bind(self, *args):
                    return "id"

                def delete(self, *args):
                    pass

                def insert(self, index, chars):
                    inserts.append((index, chars))

                def mark_set(self, *args):
                    pass

                def yview(self, *args):
                    pass

            class EditorWindow:
                text = Text()
                flist = None

                def set_saved(self, flag):
                    pass

                def reset_undo(self):
                    pass

            assert IOBinding(EditorWindow()).loadfile(path) is True
            assert inserts == [("1.0", content)], [(i, len(c)) for i, c in inserts]
            print("ok")
            """,
            tmp_path,
        )

        assert output == "ok\n"


@needs_tk
class TestStandardInputIsReadFirst:
    """`python -m idlelib -` | O(i) | O(i): standard input is read to its end
    before any window is asked for, then run in the shell."""

    def test_the_input_is_run_in_the_shell(self, tmp_path: pathlib.Path) -> None:
        script = "print('from stdin')\n" * 50

        calls, _ = run_main(["-"], tmp_path, stdin=script)

        assert calls == [
            ("stdin.read", len(script)),
            ("Tk",),
            ("open_shell",),
            ("runcommand",),
            ("execsource", script),
            ("destroy",),
        ]

    @linux_only
    def test_no_window_is_asked_for_until_the_input_ends(self, tmp_path: pathlib.Path) -> None:
        def start(*args: str) -> subprocess.Popen[str]:
            # Each gets its own home: both would otherwise race to create ~/.idlerc
            home = tmp_path / ("reader" if args else "control")
            home.mkdir()
            return subprocess.Popen(
                [sys.executable, "-m", "idlelib", *args],
                cwd=home,
                env=quiet_env(home),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        reader = start("-")
        control = start()
        try:
            began = time.monotonic()
            _, control_err = control.communicate(timeout=120)
            elapsed = time.monotonic() - began
            assert "TclError" in control_err, control_err
            assert reader.stdin is not None
            reader.stdin.write("print('from stdin')\n")
            reader.stdin.flush()
            time.sleep(max(1.0, elapsed))

            assert reader.poll() is None, "`-` stopped before its input ended"

            _, reader_err = reader.communicate(timeout=120)
            assert reader.returncode != 0
            assert "TclError" in reader_err, reader_err
        finally:
            for process in (reader, control):
                if process.poll() is None:
                    process.kill()
                    process.communicate()


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
    return run_python([str(script)], cwd)


@needs_tk
class TestDocumentedExamples:
    """Each block runs in its own headless subprocess with its own home
    directory, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "'USAGE: idle'" in s)
        mutated = source.replace("'USAGE: idle'", "'USAGE: idle3'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
