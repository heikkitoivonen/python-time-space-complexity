"""Tests for docs/stdlib/subprocess.md.

Lib/subprocess.py: ``Popen.__init__`` calls ``_cleanup()``, which polls every
instance in the module's ``_active`` list - the objects ``__del__`` put
there because their child had not been waited for - stores ``args`` as
given, opens a pipe per stream set to ``PIPE`` (``F_SETPIPE_SZ`` where
``pipesize`` is given and the platform has it), one ``os.devnull`` for
every stream set to ``DEVNULL``, and wraps the parent's ends in file
objects before ``_execute_child``. On POSIX that lists the arguments,
prepends ``/bin/sh -c`` under ``shell=True``, and either ``os.posix_spawn``
- for a full path without ``preexec_fn``, ``pass_fds``, ``cwd`` or the id
arguments, and only with ``close_fds=False`` before 3.14; on 3.10 to 3.12
``_posix_spawn`` substitutes ``os.environ`` for ``env=None`` and the C
call encodes it, where 3.13 passes ``environ`` through - or
``_posixsubprocess.fork_exec``: the latter encodes each ``env`` entry
with ``os.fsencode``, builds one candidate path per ``os.get_exec_path``
directory when the executable has no directory, sorts ``pass_fds`` into
the tuple the child keeps, and the child tries each candidate with
``execve`` in turn after running ``preexec_fn`` and closing every
descriptor from 3 up except the kept ones. ``communicate()`` with at most
one pipe and no timeout is a single ``read()`` or ``write()`` then
``wait()``; otherwise ``_communicate`` registers the pipes with a
selector, writes the input ``_PIPE_BUF`` bytes at a time, appends each
32 KiB read to a per-stream list kept on the instance, so a retry after
TimeoutExpired continues it, and raises ValueError for input once
``_communication_started``. ``wait(timeout)`` polls ``waitpid(WNOHANG)``
with a growing sleep and raises TimeoutExpired past the deadline;
``poll()`` is one ``waitpid(WNOHANG)``; ``send_signal`` polls first and
returns without ``os.kill`` once ``returncode`` is set; ``__exit__``
closes the three file objects and calls ``wait()``. ``run()`` is
``Popen``, ``communicate``, ``poll``, killing and waiting on
TimeoutExpired and raising CalledProcessError under ``check``;
``call()`` is ``Popen`` and ``wait``, killing on any exception;
``check_output`` is ``run(stdout=PIPE, check=True).stdout``;
``getstatusoutput`` is ``check_output(shell=True, text=True,
stderr=STDOUT)`` with one trailing newline sliced off; ``list2cmdline``
walks every character of every argument once. ``CompletedProcess``,
``CalledProcessError`` and ``TimeoutExpired`` store the objects they are
given, and the two exceptions expose ``stdout`` as a property over
``output``.

Observation settles every row that has something to observe:

* ``Popen.args`` is the list passed; str, bytes and path arguments reach
  the child's ``argv`` as given; a str command is one program name, so a
  command line with spaces raises FileNotFoundError naming the whole
  string, and under ``shell=True`` ``$0`` is the shell; a program given
  without a directory raises FileNotFoundError when no ``PATH`` directory
  holds it while the absolute path works with the same ``PATH``; an
  ``env`` mapping's ``items()`` is called once and its entries reach the
  child, ``env=None`` inherits a variable set in the parent, ``env={}``
  hides it, and a key containing ``=`` raises ValueError; a counting
  mapping installed as ``os.environ`` is never iterated by a
  ``close_fds=True`` spawn, and by a ``close_fds=False`` full-path spawn
  only on 3.10 to 3.12 where ``posix_spawn`` is in use; a pipe end made
  inheritable is closed in the child by default, open with
  ``close_fds=False`` and open under ``pass_fds`` with the default, and a
  non-inheritable one is closed even with ``close_fds=False``;
  an ``extra_groups`` generator is consumed once before the spawn, which
  then raises PermissionError without privilege; ``preexec_fn`` runs
  once, in a process whose pid is ``Popen.pid`` and not the parent's; a Popen dropped while its child runs raises
  ResourceWarning naming the pid, is polled once by each of the next two
  constructor calls and removed by a constructor call after the child
  exits;
* ``returncode`` is None until ``poll()`` reports the exit; the streams
  are None unless piped; ``universal_newlines`` reports ``text_mode``;
  on Linux ``F_GETPIPE_SZ`` reports at least the fourfold ``pipesize``
  asked for;
* ``communicate()`` delivers 1 MiB of input to a child that has already
  filled stderr with 1 MiB before reading any of it, which writing the
  input first and draining afterwards could not; 1 MiB written to stderr
  before a byte reaches stdout leaves ``stdout.read()`` alone unreturned
  after 300 ms until stderr is drained;
  a str subclass given as text input has ``encode`` called once; the
  traced peak of collecting 4 MiB is three to six times that of 1 MiB;
  a 300 ms timeout raises TimeoutExpired carrying the output the child
  had confirmed writing, with the child still running, input to the next call raises ValueError, and
  a plain next call returns the whole output from the start;
* ``wait(timeout=WAIT)`` on a finished child returns in under half of it,
  and on a blocked child raises after its 50 ms timeout with ``poll()``
  still None; ``terminate()`` and ``kill()`` leave -SIGTERM and -SIGKILL;
  ``terminate()`` returns from a child ignoring SIGTERM with it alive and
  ``os.kill`` called once, and after the exit is collected calls
  ``os.kill`` zero times; the with statement's exit leaves the pipes
  closed and ``returncode`` set, and a child that writes to its stdout
  after seeing stdin's EOF, which that exit sends last, fails;
* ``run()`` collects both streams, sends input, raises CalledProcessError
  carrying the output under ``check=True``, and on a 300 ms timeout
  raises TimeoutExpired inside five seconds of a child that would sleep
  thirty, with the pid its ``preexec_fn`` recorded gone from the process
  table; ``check_returncode()`` raises with the same ``stdout``
  and ``stderr`` objects and returns None on zero; ``call()`` returns the
  code, ``check_call()`` raises on it, and ``call(stdout=PIPE)`` of a
  child writing 1 MiB hits its timeout; ``check_output()`` returns stdout
  alone and raises with it; ``getstatusoutput()`` returns the code with
  stderr merged and exactly one newline stripped, ``getoutput()`` the
  text alone; ``list2cmdline()`` quotes spaces, empty strings and quotes;
* three streams set to ``DEVNULL`` open ``os.devnull`` once; ``STDOUT``
  puts stderr's bytes in the stdout pipe; the two exceptions subclass
  SubprocessError and their ``stdout`` reads and writes ``output``;
* ``Popen()`` accepts ``pipesize`` on every supported version and
  ``process_group``, as ``getoutput()`` accepts ``encoding``, from 3.11.

The one stopwatch test spawns ``true`` through a 15000-directory ``PATH``
against a two-directory one, and by absolute path through the long one;
it settles that the search grows with the directories, not that each costs
an exec attempt rather than a candidate path, and P is a length on the
page because the candidates copy the directory names.

Not settled by running code: s and w themselves, which are the platform's;
the O(p log p) sort of ``pass_fds``, and how the child closes the other
descriptors - one ``close_range()`` per gap between kept ones where the
kernel and libc have it, otherwise one close per descriptor - observed on
one descriptor; the count of output decodes, one by reading; Windows,
where ``CreateProcess`` replaces the spawn, ``list2cmdline`` builds the
command line, ``STARTUPINFO`` and the flags exist, the ``cmd.exe`` search
of 3.10.11, 3.11.3 and 3.12 and the 3.13 flags apply, and
``communicate()`` uses threads. Not settled either: the account
database lookups behind a ``user``, ``group`` or group name, which are the
NSS backend's. Not varied: more than one passed descriptor, argument lists
beyond four items, ``env`` beyond one entry, output beyond 4 MiB, encodings
other than UTF-8, ``bufsize``, and the ``user``, ``group``, ``umask`` and
``cwd`` arguments.
"""

import gc
import inspect
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator, Mapping
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "subprocess.md"
EXPECTED_BLOCKS = 5
WAIT = 10.0
SHORT = 0.05
PY = sys.executable
MIB = 1 << 20

CLASSES: dict[str, type] = {
    "Popen": subprocess.Popen,
    "CompletedProcess": subprocess.CompletedProcess,
    "SubprocessError": subprocess.SubprocessError,
    "CalledProcessError": subprocess.CalledProcessError,
    "TimeoutExpired": subprocess.TimeoutExpired,
}
# Classes whose __init__ installs public attributes on the instance, and how
# to build one so those names count as members too.
INSTANCES: dict[str, Callable[[], object]] = {
    "Popen": lambda: _finished(),
    "CompletedProcess": lambda: subprocess.CompletedProcess(["true"], 0),
    "CalledProcessError": lambda: subprocess.CalledProcessError(1, ["false"]),
    "TimeoutExpired": lambda: subprocess.TimeoutExpired(["sleep"], 1.0),
}
# Names the module defines only on Windows, where the table's row for them
# is checked; elsewhere they are allowed to be absent.
WINDOWS_ONLY_NAMES = {
    "STARTUPINFO",
    "CREATE_NEW_CONSOLE",
    "CREATE_NEW_PROCESS_GROUP",
    "CREATE_NO_WINDOW",
    "CREATE_DEFAULT_ERROR_MODE",
    "CREATE_BREAKAWAY_FROM_JOB",
    "DETACHED_PROCESS",
    "STARTF_USESTDHANDLES",
    "STARTF_USESHOWWINDOW",
    "STARTF_FORCEONFEEDBACK",
    "STARTF_FORCEOFFFEEDBACK",
    "STD_INPUT_HANDLE",
    "STD_OUTPUT_HANDLE",
    "STD_ERROR_HANDLE",
    "SW_HIDE",
    "ABOVE_NORMAL_PRIORITY_CLASS",
    "BELOW_NORMAL_PRIORITY_CLASS",
    "HIGH_PRIORITY_CLASS",
    "IDLE_PRIORITY_CLASS",
    "NORMAL_PRIORITY_CLASS",
    "REALTIME_PRIORITY_CLASS",
}
# `Handle` wraps a Windows process handle for Popen's own use and is not in
# `__all__` or the Python documentation.
UNDOCUMENTED_NAMES = {"Handle"}
VERSION_GATED_NAMES = {
    "STARTF_FORCEONFEEDBACK": "Python 3.13+",
    "STARTF_FORCEOFFFEEDBACK": "Python 3.13+",
}


def _finished() -> subprocess.Popen[bytes]:
    process = subprocess.Popen([PY, "-c", "pass"])
    process.wait(WAIT)
    return process


def _module_names() -> set[str]:
    """Public names of the module that are not the modules it imports."""
    return {
        name
        for name in dir(subprocess)
        if not name.startswith("_") and not inspect.ismodule(getattr(subprocess, name))
    }


def _table_rows() -> list[str]:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n\nA pipe holds", start)
    return [line for line in text[start:end].splitlines() if line.startswith("| `")]


def _documented() -> tuple[set[str], set[tuple[str, str]]]:
    """Module-level names and (class, member) pairs the table names.

    A backticked span is split on ``/``; a segment after the first inherits
    the class of the segment before it, so ``Popen.poll/wait`` names two
    members of Popen and ``PIPE / STDOUT`` two module names.
    """
    names: set[str] = set()
    members: set[tuple[str, str]] = set()
    for row in _table_rows():
        operation = row.split("|")[1]
        for span in re.findall(r"`([^`]+)`", operation):
            owner: str | None = None
            for segment in span.split("/"):
                segment = segment.strip().removesuffix("()").strip()
                if " " in segment:
                    segment = segment.split(" ", 1)[0]
                if "." in segment:
                    class_name, member = segment.split(".", 1)
                    owner = class_name
                    names.add(class_name)
                    members.add((class_name, member))
                elif owner is not None:
                    members.add((owner, segment))
                else:
                    names.add(segment)
    return names, members


def _public_members(owner: str) -> set[str]:
    """Public names defined on the class itself, plus any its __init__ installs."""
    members = {name for name in vars(CLASSES[owner]) if not name.startswith("_")}
    if owner in INSTANCES:
        members |= {name for name in vars(INSTANCES[owner]()) if not name.startswith("_")}
    return members


def _has_member(owner: str, member: str) -> bool:
    if hasattr(CLASSES[owner], member):
        return True
    return owner in INSTANCES and hasattr(INSTANCES[owner](), member)


def _child(code: str, **kwargs: Any) -> subprocess.Popen[Any]:
    return subprocess.Popen([PY, "-c", textwrap.dedent(code)], **kwargs)


def _run(code: str, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("timeout", WAIT)
    return subprocess.run([PY, "-c", textwrap.dedent(code)], **kwargs)


def _stdout_of(process: subprocess.Popen[Any]) -> Any:
    assert process.stdout is not None
    return process.stdout


def _stderr_of(process: subprocess.Popen[Any]) -> Any:
    assert process.stderr is not None
    return process.stderr


def _stdin_of(process: subprocess.Popen[Any]) -> Any:
    assert process.stdin is not None
    return process.stdin


def _elapsed(func: Callable[[], object]) -> float:
    start = time.perf_counter()
    func()
    return time.perf_counter() - start


def traced_peak(func: Callable[[], Any]) -> int:
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


@pytest.fixture
def reaper() -> Iterator[list[subprocess.Popen[Any]]]:
    """Kills and waits for every process a test leaves running."""
    processes: list[subprocess.Popen[Any]] = []
    yield processes
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(WAIT)


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `subprocess` and of its classes."""

    def test_no_module_name_is_missing_from_the_table(self) -> None:
        missing = sorted(_module_names() - _documented()[0] - UNDOCUMENTED_NAMES)

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_no_public_member_is_missing_from_the_table(self) -> None:
        members = _documented()[1]
        missing: list[str] = []
        for owner in CLASSES:
            documented = {
                member for documented_owner, member in members if documented_owner == owner
            }
            missing.extend(
                f"{owner}.{name}" for name in sorted(_public_members(owner) - documented)
            )

        assert not missing, f"{len(missing)} members absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        names, members = _documented()
        allowed_absent = set() if sys.platform == "win32" else WINDOWS_ONLY_NAMES

        unknown_names = sorted(names - _module_names() - allowed_absent)
        unknown_members = sorted(
            f"{owner}.{member}"
            for owner, member in members
            if owner not in CLASSES or not _has_member(owner, member)
        )

        assert not unknown_names, f"the table names attributes subprocess lacks: {unknown_names}"
        assert not unknown_members, f"the table names members that do not exist: {unknown_members}"

    def test_the_windows_row_names_every_windows_only_name(self) -> None:
        names = _documented()[0]

        assert WINDOWS_ONLY_NAMES <= names
        windows_rows = [row for row in _table_rows() if "`STARTUPINFO()`" in row]
        assert len(windows_rows) == 1
        assert "Windows only" in windows_rows[0]

    def test_the_version_gated_rows_say_so(self) -> None:
        rows = _table_rows()
        for name, marker in VERSION_GATED_NAMES.items():
            owning = [row for row in rows if f"`{name}`" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert marker in owning[0], f"the {name} row should say {marker}: {owning[0]}"

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        names, members = _documented()

        assert {"Popen", "run", "check_output", "PIPE", "list2cmdline", "TimeoutExpired"} <= names
        assert {
            ("Popen", "communicate"),
            ("Popen", "text_mode"),
            ("Popen", "__exit__"),
            ("CompletedProcess", "check_returncode"),
            ("CompletedProcess", "stderr"),
            ("CalledProcessError", "output"),
            ("TimeoutExpired", "timeout"),
        } <= members
        assert _module_names() - UNDOCUMENTED_NAMES - (names - {"call"}) == {"call"}
        assert _public_members("Popen") - {
            member for owner, member in members - {("Popen", "poll")} if owner == "Popen"
        } == {"poll"}
        assert {"pid", "returncode", "pipesize"} <= _public_members("Popen")
        assert "check_returncode" in _public_members("CompletedProcess")


class TestPopenRow:
    """What Popen() encodes, searches, closes, polls and runs before the spawn."""

    def test_args_is_the_object_passed_and_each_argument_reaches_the_child(self) -> None:
        args: list[Any] = [
            PY,
            "-c",
            "import sys; print(sys.argv[1:])",
            "ä",
            b"b",
            pathlib.Path("c"),
        ]

        process = subprocess.Popen(args, stdout=subprocess.PIPE)
        output, _ = process.communicate(timeout=WAIT)

        assert process.args is args
        assert output.decode() == "['ä', 'b', 'c']\n"

    def test_a_str_command_is_one_program_name_unless_shell_is_true(self) -> None:
        with pytest.raises(FileNotFoundError) as excinfo:
            subprocess.Popen(f"{PY} -c pass")
        assert excinfo.value.filename == f"{PY} -c pass"

        result = subprocess.run("echo $0", shell=True, capture_output=True, text=True, timeout=WAIT)

        assert result.stdout.strip().endswith("sh")

    def test_a_program_without_a_directory_is_looked_up_on_path(
        self, tmp_path: pathlib.Path
    ) -> None:
        true = shutil.which("true")
        assert true is not None
        bogus = os.pathsep.join(str(tmp_path / f"no{i}") for i in range(3))

        with pytest.raises(FileNotFoundError):
            subprocess.Popen(["true"], env={"PATH": bogus})
        found = subprocess.Popen(["true"], env={"PATH": bogus + os.pathsep + os.path.dirname(true)})
        absolute = subprocess.Popen([true], env={"PATH": bogus})

        assert found.wait(WAIT) == 0
        assert absolute.wait(WAIT) == 0

    @pytest.mark.timing
    def test_the_path_search_scales_with_the_directories_listed(self) -> None:
        """Spawn `true` with 2 and 15002 PATH directories, and by absolute path
        through the long one. Measured: the search through 15000 missing
        directories is 9 to 30 times the two-directory spawn, and 8 to 10 times
        the absolute-path spawn through the same PATH; the two-directory spawn is
        the noisier of the baselines, so the absolute path is compared with the
        search it avoids. The interpreter is not the program spawned, so the spawn
        itself does not swamp the attempts. This settles that the search is O(P)
        and that a full path avoids it; that the cost is one exec attempt per
        directory, rather than the candidate list built for them, is the source's."""
        true = shutil.which("true")
        assert true is not None
        short = os.path.dirname(true) + os.pathsep + "/usr/bin"
        long = os.pathsep.join(f"/n{i}" for i in range(15000)) + os.pathsep + short

        def spawn(program: str, path: str) -> None:
            assert subprocess.Popen([program], env={"PATH": path}).wait(WAIT) == 0

        def best(program: str, path: str) -> float:
            return min(_elapsed(lambda: spawn(program, path)) for _ in range(7))

        searched_short = best("true", short)
        searched_long = best("true", long)
        absolute_long = best(true, long)

        assert searched_long / searched_short > 4, (searched_short, searched_long)
        assert searched_long / absolute_long > 4, (absolute_long, searched_long)

    def test_an_explicit_env_is_read_once_and_none_inherits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = 0

        class Env(dict[str, str]):
            def items(self) -> Any:
                nonlocal calls
                calls += 1
                return super().items()

        code = "import os; print(os.environ.get('SUBPROCESS_PAGE_PROBE'))"
        monkeypatch.setenv("SUBPROCESS_PAGE_PROBE", "inherited")

        explicit = _run(code, env=Env(SUBPROCESS_PAGE_PROBE="explicit"), text=True)
        inherited = _run(code, env=None, text=True)
        empty = _run(code, env={}, text=True)

        assert calls == 1
        assert explicit.stdout == "explicit\n"
        assert inherited.stdout == "inherited\n"
        assert empty.stdout == "None\n"
        with pytest.raises(ValueError, match="illegal environment variable name"):
            subprocess.Popen([PY, "-c", "pass"], env={"A=B": "1"})

    def test_an_inherited_environment_is_encoded_only_by_3_10_to_3_12_through_posix_spawn(
        self,
    ) -> None:
        """The posix_spawn path needs a full path and, before 3.14, close_fds=False;
        3.10 to 3.12 substitute os.environ for None there and os.posix_spawn encodes
        it, 3.13 and later hand the process environment through in C, and the fork
        path, which the default close_fds=True takes before 3.14, never reads it."""
        real = os.environ
        iterations = 0

        class Environ(Mapping[str, str]):
            def __getitem__(self, key: str) -> str:
                return real[key]

            def __iter__(self) -> Iterator[str]:
                nonlocal iterations
                iterations += 1
                return iter(real)

            def __len__(self) -> int:
                return len(real)

        # Restored by hand rather than through monkeypatch: pytest writes to
        # os.environ in its teardown, before a monkeypatch would be undone.
        cast(Any, os).environ = Environ()
        try:
            forked = subprocess.Popen([PY, "-c", "pass"], close_fds=True, env=None)
            assert forked.wait(WAIT) == 0
            assert iterations == 0
            spawned = subprocess.Popen([PY, "-c", "pass"], close_fds=False, env=None)
            assert spawned.wait(WAIT) == 0
        finally:
            cast(Any, os).environ = real

        encoded = sys.version_info < (3, 13) and cast(Any, subprocess)._USE_POSIX_SPAWN
        assert (iterations > 0) is bool(encoded), iterations

    def test_close_fds_closes_all_but_pass_fds_and_false_passes_the_inheritable(self) -> None:
        inheritable, write_end = os.pipe()
        plain, other_write_end = os.pipe()
        os.set_inheritable(inheritable, True)
        try:
            code = f"""
                import os
                for fd in ({inheritable}, {plain}):
                    try:
                        os.fstat(fd)
                        print("open")
                    except OSError:
                        print("closed")
            """
            default = _run(code, text=True).stdout.split()
            not_closing = _run(code, text=True, close_fds=False).stdout.split()
            passed = _run(code, text=True, pass_fds=(inheritable, plain)).stdout.split()
        finally:
            for fd in (inheritable, write_end, plain, other_write_end):
                os.close(fd)

        assert default == ["closed", "closed"]
        assert not_closing == ["open", "closed"]
        assert passed == ["open", "open"]

    def test_extra_groups_is_read_once_in_the_parent(self) -> None:
        """The child's setgroups() needs privilege, so an unprivileged run raises
        PermissionError from the child after the parent has listed the groups."""
        reads: list[int] = []

        def groups() -> Iterator[int]:
            for gid in os.getgroups()[:2] or [os.getgid()]:
                reads.append(gid)
                yield gid

        try:
            process = subprocess.Popen([PY, "-c", "pass"], extra_groups=groups())
        except PermissionError:
            pass
        else:
            assert process.wait(WAIT) == 0

        assert reads == (os.getgroups()[:2] or [os.getgid()])

    def test_preexec_fn_runs_once_in_the_child(self, tmp_path: pathlib.Path) -> None:
        record = tmp_path / "preexec.txt"

        def note_pid() -> None:
            with record.open("a") as file:
                file.write(f"{os.getpid()}\n")

        process = subprocess.Popen([PY, "-c", "pass"], preexec_fn=note_pid)
        process.wait(WAIT)

        pids = record.read_text().split()
        assert pids == [str(process.pid)]
        assert process.pid != os.getpid()

    def test_a_popen_dropped_unwaited_is_polled_by_later_constructors_until_it_exits(
        self,
    ) -> None:
        process = _child(
            "import sys; sys.stdin.read()", stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        pid = process.pid
        gate, exit_signal = process.stdin, process.stdout
        assert gate is not None and exit_signal is not None

        def entries() -> list[Any]:
            return [entry for entry in cast(Any, subprocess)._active if entry.pid == pid]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            del process
            gc.collect()
        messages = [str(w.message) for w in caught if issubclass(w.category, ResourceWarning)]
        assert f"subprocess {pid} is still running" in messages
        assert len(entries()) == 1
        entry = entries()[0]
        polls = 0
        original_poll = entry._internal_poll

        def counting_poll(*args: Any, **kwargs: Any) -> Any:
            nonlocal polls
            polls += 1
            return original_poll(*args, **kwargs)

        entry._internal_poll = counting_poll

        for _ in range(2):
            _finished()
        assert polls == 2
        assert len(entries()) == 1

        gate.close()
        assert exit_signal.read() == b""
        exit_signal.close()
        # The child closes stdout while shutting down, before it exits, so the
        # first constructor call after the EOF may still find it running.
        deadline = time.monotonic() + WAIT
        while entries() and time.monotonic() < deadline:
            _finished()

        assert polls >= 3
        assert entries() == []


class TestPopenAttributesRow:
    """returncode, the streams, pipesize and the text-mode aliases."""

    def test_returncode_is_none_until_the_exit_is_collected(self, reaper: list[Any]) -> None:
        process = _child("import sys; sys.stdin.read()", stdin=subprocess.PIPE)
        reaper.append(process)

        assert process.returncode is None
        assert process.poll() is None
        assert process.stdout is None and process.stderr is None
        assert isinstance(process.pid, int)
        _stdin_of(process).close()
        assert process.wait(WAIT) == 0
        assert process.returncode == 0 and process.poll() == 0

    def test_universal_newlines_reports_text_mode(self) -> None:
        binary: Any = _finished()
        text: Any = subprocess.Popen([PY, "-c", "pass"], text=True)
        text.wait(WAIT)

        assert not binary.text_mode and not binary.universal_newlines
        assert binary.encoding is None
        assert text.text_mode and text.universal_newlines
        assert text.encoding is not None
        assert binary.pipesize == -1

    def test_pipesize_sizes_the_pipes_where_the_platform_allows(self) -> None:
        fcntl = pytest.importorskip("fcntl")
        if not hasattr(fcntl, "F_GETPIPE_SZ"):
            pytest.skip("only Linux sizes pipes")

        read_end, write_end = os.pipe()
        default = fcntl.fcntl(read_end, fcntl.F_GETPIPE_SZ)
        os.close(read_end)
        os.close(write_end)
        asked = 4 * default
        try:
            sized: Any = subprocess.Popen(
                [PY, "-c", "pass"], stdout=subprocess.PIPE, pipesize=asked
            )
        except PermissionError:
            pytest.skip("this kernel does not let the user enlarge a pipe fourfold")
        sized.wait(WAIT)

        assert sized.pipesize == asked
        assert fcntl.fcntl(_stdout_of(sized).fileno(), fcntl.F_GETPIPE_SZ) >= asked
        _stdout_of(sized).close()


class TestCommunicateRow:
    """Both pipes drained together, input chunked, text converted, timeouts resumed."""

    def test_input_and_both_outputs_beyond_a_pipe_capacity_go_through(self) -> None:
        """The child fills stderr before it reads a byte of input, so writing the
        input first and draining afterwards would deadlock; only interleaving passes."""
        code = f"""
            import sys
            sys.stderr.write("e" * {MIB})
            sys.stderr.flush()
            data = sys.stdin.buffer.read()
            sys.stdout.write(str(len(data)))
        """
        process = _child(
            code, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        output, error = process.communicate(b"y" * MIB, timeout=WAIT)

        assert output == str(MIB).encode()
        assert len(error) == MIB
        assert process.returncode == 0

    def test_reading_one_stream_alone_blocks_once_the_other_pipe_is_full(
        self, reaper: list[Any]
    ) -> None:
        code = """
            import sys
            sys.stderr.write("x" * (1 << 20))
            sys.stderr.flush()
            sys.stdout.write("done")
        """
        process = _child(code, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        reaper.append(process)
        seen: list[bytes] = []
        reader = threading.Thread(
            target=lambda: seen.append(_stdout_of(process).read()), daemon=True
        )

        reader.start()
        reader.join(0.3)
        blocked = reader.is_alive()
        error = _stderr_of(process).read()
        reader.join(WAIT)

        assert blocked, "stdout.read() returned while stderr was still full"
        assert not reader.is_alive()
        assert seen == [b"done"]
        assert len(error) == MIB

    def test_text_input_is_encoded_once_and_output_decoded(self) -> None:
        encodes = 0

        class Counted(str):
            __slots__ = ()

            def encode(self, *args: Any, **kwargs: Any) -> bytes:
                nonlocal encodes
                encodes += 1
                return super().encode(*args, **kwargs)

        process: Any = _child(
            "import sys; sys.stdout.write(sys.stdin.read().upper())",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        output, _ = process.communicate(Counted("héllo"), timeout=WAIT)

        assert encodes == 1
        assert output == "HÉLLO"

    def test_space_grows_with_the_output_collected(self) -> None:
        def peak(size: int) -> int:
            process = _child(
                f"import sys; sys.stdout.write('x' * {size})",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            outputs: list[bytes] = []
            measured = traced_peak(lambda: outputs.append(process.communicate(timeout=WAIT)[0]))
            assert len(outputs[0]) == size
            return measured

        one, four = peak(MIB), peak(4 * MIB)

        assert 3 * one <= four <= 6 * one, (one, four)

    def test_a_timeout_keeps_the_output_so_far_and_the_next_call_continues(
        self, reaper: list[Any]
    ) -> None:
        code = """
            import sys
            sys.stdout.write("partial")
            sys.stdout.flush()
            sys.stderr.write("ready")
            sys.stderr.flush()
            sys.stdin.read()
            sys.stdout.write("rest")
        """
        process = _child(
            code, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        reaper.append(process)
        # Keep the child's stdin open past the first call by holding a second
        # writer, so the timeout is what ends the call; wait for the child to
        # say the partial output is in the pipe before starting the clock.
        holder = os.dup(_stdin_of(process).fileno())
        assert _stderr_of(process).read(5) == b"ready"
        try:
            with pytest.raises(subprocess.TimeoutExpired) as excinfo:
                process.communicate(b"go\n", timeout=0.3)
            assert excinfo.value.stdout == b"partial"
            assert excinfo.value.timeout == 0.3
            assert process.poll() is None
            with pytest.raises(ValueError, match="Cannot send input"):
                process.communicate(b"more")
        finally:
            os.close(holder)

        output, _ = process.communicate(timeout=WAIT)

        assert output == b"partialrest"
        assert process.returncode == 0


class TestWaitPollAndSignalRows:
    """wait(), poll(), send_signal(), terminate(), kill() and the with statement."""

    def test_wait_is_immediate_on_a_finished_child_and_bounded_by_its_timeout(
        self, reaper: list[Any]
    ) -> None:
        finished = _finished()
        blocked = _child("import sys; sys.stdin.read()", stdin=subprocess.PIPE)
        reaper.append(blocked)

        assert _elapsed(lambda: finished.wait(timeout=WAIT)) < WAIT / 2
        with pytest.raises(subprocess.TimeoutExpired) as excinfo:
            blocked.wait(timeout=SHORT)

        assert excinfo.value.timeout == SHORT
        assert blocked.poll() is None

    def test_terminate_and_kill_send_their_signals_without_waiting(
        self, reaper: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kills: list[tuple[int, int]] = []
        real_kill = os.kill
        monkeypatch.setattr(
            os, "kill", lambda pid, sig: (kills.append((pid, sig)), real_kill(pid, sig))
        )
        ignoring = _child(
            """
            import signal, sys, time
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            sys.stdout.write("ready")
            sys.stdout.flush()
            sys.stdin.read()
            """,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        reaper.append(ignoring)
        assert _stdout_of(ignoring).read(5) == b"ready"

        assert _elapsed(ignoring.terminate) < 1.0
        assert kills == [(ignoring.pid, signal.SIGTERM)]
        time.sleep(SHORT)
        assert ignoring.poll() is None
        ignoring.kill()
        assert ignoring.wait(WAIT) == -signal.SIGKILL

        terminated = _child("import sys; sys.stdin.read()", stdin=subprocess.PIPE)
        terminated.terminate()
        assert terminated.wait(WAIT) == -signal.SIGTERM

        kills.clear()
        terminated.terminate()
        terminated.send_signal(signal.SIGUSR1)
        assert kills == []
        assert terminated.returncode == -signal.SIGTERM

    def test_the_with_statement_closes_the_pipes_and_waits(self) -> None:
        with subprocess.Popen(
            [PY, "-c", "pass"], stdout=subprocess.PIPE, stdin=subprocess.PIPE
        ) as quiet:
            assert quiet.returncode is None

        assert quiet.returncode == 0
        assert _stdout_of(quiet).closed and _stdin_of(quiet).closed

        # __exit__ closes stdout before stdin, so a child that writes after
        # seeing stdin's EOF writes to a pipe already closed at the other end.
        with _child(
            "import sys; sys.stdin.read(); sys.stdout.write('late'); sys.stdout.flush()",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as late:
            pass

        assert late.returncode != 0


class TestRunAndFriendsRows:
    """run(), CompletedProcess, call(), check_call(), check_output(), getoutput()."""

    def test_run_collects_both_streams_and_sends_input(self) -> None:
        result = _run(
            "import sys; sys.stdout.write(sys.stdin.read()); sys.stderr.write('err')",
            input=b"in",
        )

        assert (result.stdout, result.stderr, result.returncode) == (b"in", b"err", 0)
        assert result.args[0] == PY
        plain = subprocess.run([PY, "-c", "pass"], timeout=WAIT)
        assert plain.stdout is None and plain.stderr is None

    def test_check_raises_with_the_output_and_check_returncode_holds_the_same_objects(
        self,
    ) -> None:
        code = "import sys; sys.stdout.write('o'); sys.stderr.write('e'); sys.exit(3)"

        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            _run(code, check=True)
        assert (excinfo.value.returncode, excinfo.value.stdout, excinfo.value.stderr) == (
            3,
            b"o",
            b"e",
        )

        result = _run(code)
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            result.check_returncode()
        assert excinfo.value.stdout is result.stdout
        assert excinfo.value.stderr is result.stderr
        assert excinfo.value.cmd is result.args
        assert subprocess.CompletedProcess(["true"], 0).check_returncode() is None

    def test_a_run_timeout_kills_and_collects_the_child(self, tmp_path: pathlib.Path) -> None:
        """The child's pid is recorded by preexec_fn, which runs before the exec,
        so it is known whether or not the child got to print anything."""
        record = tmp_path / "pid.txt"
        code = "import sys, time; sys.stdout.write('started'); sys.stdout.flush(); time.sleep(30)"

        start = time.perf_counter()
        with pytest.raises(subprocess.TimeoutExpired) as excinfo:
            _run(code, timeout=0.3, preexec_fn=lambda: record.write_text(str(os.getpid())))
        elapsed = time.perf_counter() - start

        assert elapsed < WAIT / 2
        assert excinfo.value.stdout in (None, b"", b"started")
        with pytest.raises(ProcessLookupError):
            os.kill(int(record.read_text()), 0)

    def test_call_returns_the_code_and_check_call_raises_on_it(self) -> None:
        assert subprocess.call([PY, "-c", "import sys; sys.exit(4)"], timeout=WAIT) == 4
        assert subprocess.check_call([PY, "-c", "pass"], timeout=WAIT) == 0
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            subprocess.check_call([PY, "-c", "import sys; sys.exit(4)"], timeout=WAIT)
        assert excinfo.value.returncode == 4

    def test_call_with_a_pipe_blocks_on_a_child_that_fills_it(self) -> None:
        code = f"import sys; sys.stdout.write('x' * {MIB})"

        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.call([PY, "-c", code], stdout=subprocess.PIPE, timeout=0.3)
        assert len(_run(code).stdout) == MIB

    def test_check_output_returns_stdout_alone(self) -> None:
        code = "import sys; sys.stdout.write('out'); sys.stderr.write('err')"

        assert (
            subprocess.check_output([PY, "-c", code], stderr=subprocess.DEVNULL, timeout=WAIT)
            == b"out"
        )
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            subprocess.check_output(
                [PY, "-c", code + "; sys.exit(2)"], stderr=subprocess.PIPE, timeout=WAIT
            )
        assert (excinfo.value.output, excinfo.value.stderr) == (b"out", b"err")

    def test_getstatusoutput_merges_stderr_and_strips_one_newline(self) -> None:
        status = subprocess.getstatusoutput("printf 'a\\nb\\n\\n'; echo err 1>&2; exit 7")

        assert status == (7, "a\nb\n\nerr")
        assert subprocess.getoutput("printf 'a\\n\\n'") == "a\n"
        assert subprocess.getoutput("printf 'no newline'") == "no newline"

    def test_list2cmdline_quotes_by_the_windows_rules(self) -> None:
        assert subprocess.list2cmdline(["a b", 'c"d', "", "e\\"]) == '"a b" c\\"d "" e\\'


class TestConstantAndExceptionRows:
    """PIPE, STDOUT, DEVNULL and the exception classes."""

    def test_devnull_is_opened_once_and_stdout_merges_stderr(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[Any] = []
        real_open = os.open

        def counting_open(path: Any, *args: Any, **kwargs: Any) -> int:
            if path == os.devnull:
                opened.append(path)
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(os, "open", counting_open)
        process = subprocess.Popen(
            [PY, "-c", "pass"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        process.wait(WAIT)
        assert opened == [os.devnull]

        merged = _run(
            "import sys; sys.stdout.write('out'); sys.stdout.flush(); sys.stderr.write('err')",
            capture_output=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert merged.stdout == b"outerr"
        assert merged.stderr is None

    def test_the_exceptions_subclass_subprocess_error_and_alias_stdout_to_output(self) -> None:
        called = subprocess.CalledProcessError(1, ["false"], output=b"o", stderr=b"e")
        expired = subprocess.TimeoutExpired(["sleep"], 2.0, output=b"o")

        assert isinstance(called, subprocess.SubprocessError)
        assert isinstance(expired, subprocess.SubprocessError)
        assert called.stdout is called.output
        assert expired.stdout is expired.output
        called.stdout = b"changed"
        assert called.output == b"changed"
        assert (called.returncode, called.cmd, called.stderr) == (1, ["false"], b"e")
        assert (expired.cmd, expired.timeout, expired.stderr) == (["sleep"], 2.0, None)


class TestVersionNotes:
    def test_the_parameters_arrive_on_the_versions_stated(self) -> None:
        popen = inspect.signature(subprocess.Popen).parameters
        getoutput = inspect.signature(subprocess.getoutput).parameters
        getstatusoutput = inspect.signature(subprocess.getstatusoutput).parameters
        from_3_11 = sys.version_info >= (3, 11)

        assert "pipesize" in popen
        assert ("process_group" in popen) is from_3_11
        assert ("encoding" in getoutput and "errors" in getoutput) is from_3_11
        assert ("encoding" in getstatusoutput and "errors" in getstatusoutput) is from_3_11


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


def _block_containing(marker: str) -> str:
    matches = [source for _, source in _blocks() if marker in source]
    assert len(matches) == 1, f"{len(matches)} blocks contain {marker!r}"
    return matches[0]


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [PY, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run_block(source, tmp_path)
            if result.returncode != 0 or result.stderr.strip():
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        source = _block_containing('["wc", "-w"]')
        broken = source.replace("print(error.returncode)", "print(error.exit_status)", 1)
        assert broken != source, "the mutation did not change the attribute read"

        result = _run_block(broken, tmp_path)

        assert result.returncode != 0
        assert "AttributeError" in result.stderr

    @pytest.mark.parametrize(
        ("marker", "stdout"),
        [
            ('["true"]', ["0", "'hello\\n'", "Command failed"]),
            ('["wc", "-w"]', ["3", "1"]),
            ('["cat"]', ["None", "'hello\\n'", "0"]),
            ('["sleep", "10"]', ["['sleep', '10']", "-9"]),
            ('["grep", "beta"]', ["'beta\\n'"]),
        ],
        ids=["basic", "communication", "popen", "timeouts", "chaining"],
    )
    def test_the_stated_output_is_what_the_block_produces(
        self, marker: str, stdout: list[str], tmp_path: pathlib.Path
    ) -> None:
        result = _run_block(_block_containing(marker), tmp_path)

        assert result.returncode == 0, result.stderr.strip()
        assert result.stdout.splitlines() == stdout
