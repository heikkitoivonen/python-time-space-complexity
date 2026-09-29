"""Tests for docs/stdlib/faulthandler.md.

The page prices each call that arms or disarms a handler at O(1) and a dump
at O(t·d), threads times frames, capped at 100 of each. Every test that
dumps, arms a timer, installs a handler or raises a signal does it in a
child interpreter, so nothing is left enabled or armed in the test process
and a fatal signal kills only the child. Dump sizes are settled by counting
the lines a child writes, which needs no tolerance; the O(1) space of a dump
by traced allocation; threads by counting the entries of /proc/self/task.

Measurement scope:

* `dump_traceback(all_threads=False)` writes exactly one `File` line per
  frame at depths of 10, 40 and 80 calls, and exactly 100 at 150 and 1,000,
  the innermost first: the outermost `<module>` frame is present below the
  cap and absent above it.
  With all threads it writes one thread header per thread for 1, 11 and 51
  threads, and 100 headers followed by a `...` line for 121. With
  `all_threads=False` and ten other threads it writes one `Stack` header and
  no thread header. A 2,000-character filename and function name each keep
  between 500 and 520 of their characters in the frame line. The traced peak of one dump stays under 2 KB at
  depths of 10 and 90, with the dump called once before each measurement.
* `enable()` is observed by sending each of the five fatal signals to a
  child: the dump names the signal and the child dies of it. Without
  `enable()`, the same child prints no dump. With `SIGFPE` ignored before
  `enable()` and `disable()`, a `SIGFPE` leaves the child running, so the
  previous handler is back. A real fault (`ctypes.string_at(0)`) dumps the
  traceback and still kills the child. `enable()` leaves `sys.gettrace()`,
  `sys.getprofile()` and the child's OS thread count as they were.
  `disable()` returns `True` then `False`. `-X faulthandler` and
  `PYTHONFAULTHANDLER=1` each make `is_enabled()` true at startup, with a
  scrubbed environment as the control. On 3.14+, a fatal dump includes the
  C stack with `c_stack` omitted or true and not with it false; `dump_c_stack()` exists
  on 3.14+ only, and under about 200 C-level calls writes at most 32 frame
  lines and a truncation marker.
* `dump_traceback_later()` adds one OS thread; arming it again leaves one;
  `cancel_dump_traceback_later()` returns the count to the baseline. A
  timer cancelled before its 0.2 s timeout writes nothing within 0.6 s. An
  expiring one writes the `Timeout (...)!` header and a header for each of
  four Python threads; `repeat=True` writes more than one dump; `exit=True`
  ends the child with status 1.
* `register()` dumps once per `SIGUSR1` delivered, three for three, and
  the child exits normally afterwards. `unregister()` returns `True` then
  `False`. Registering `SIGSEGV` raises `RuntimeError`. A Python handler
  for `SIGUSR1` is not called after `register()`, and is with
  `chain=True`. After `os.dup2()` replaces the registered descriptor, the
  dump lands in the file now behind it.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The m term on the fatal-signal row: `_Py_DumpExtensionModules()` in
  Python/pylifecycle.c walks `sys.modules` to name the non-stdlib extension
  modules. No stdlib-only interpreter has such a module to name, so the
  listing is not observed and the walk is read from source.
* O(1) time and space for `enable()`, `disable()`, `is_enabled()`,
  `register()`, `unregister()` and arming or cancelling the watchdog are
  read from Modules/faulthandler.c: five `sigaction()` calls, one alternate
  signal stack allocated once, one table of `NSIG` entries allocated on the
  first `register()`, one thread start or join, and a flag read. Nothing on
  the page's scale grows with them. `dump_c_stack()`'s O(1) is its
  32-entry `backtrace()` buffer in Python/traceback.c; only the frame
  count is observed.
* That a dump stops walking at the caps, rather than walking on without
  printing, is read from `dump_traceback()` and `_Py_DumpTracebackThreads()`
  in Python/traceback.c; the tests see only what is written.
* That a dump holds only the line in hand is shown by traced allocation,
  which sees the Python heap only, and on Linux only; on Windows the
  thread-name lookup allocates and frees one name per thread.
* `register()` and `unregister()` are absent on Windows. That is guarded on
  `sys.platform` and never runs on the Linux CI this project uses.
* Free-threaded builds, where 3.14 dumps only the current thread on a fatal
  signal while the GIL is disabled, are not run; the page scopes its bounds
  to the default build.
* The Version Notes entries for 3.3, 3.5 and 3.7 predate the supported
  range and follow the official faulthandler documentation's
  versionadded and versionchanged markers. The 3.14 entry is tested.
"""

from __future__ import annotations

import os
import pathlib
import re
import signal
import subprocess
import sys
import textwrap

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "faulthandler.md"
EXPECTED_BLOCKS = 4
HAS_PROC_TASKS = pathlib.Path("/proc/self/task").is_dir()

# os.kill() on Windows ends the process with TerminateProcess, so no signal
# handler runs, and a real fault is a structured exception that faulthandler
# reports as "Windows fatal exception", not as a signal.
POSIX_SIGNALS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="os.kill() on Windows terminates without delivering the signal to a handler",
)

FATAL_SIGNALS = {
    "SIGSEGV": "Segmentation fault",
    "SIGFPE": "Floating",  # hyphenated as "Floating-point" on some versions only
    "SIGABRT": "Aborted",
    "SIGBUS": "Bus error",
    "SIGILL": "Illegal instruction",
}


def _no_core_dump() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_child(
    code: str,
    *args: str,
    env: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `code` in a fresh interpreter with core dumps off."""
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONFAULTHANDLER", "PYTHONDEVMODE"}
    }
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, *args, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=child_env,
        cwd=cwd,
        preexec_fn=_no_core_dump if os.name == "posix" else None,
        check=False,
    )


def child_stdout(code: str) -> str:
    result = run_child(code)
    assert result.returncode == 0, result.stderr
    return result.stdout


DUMP_AT_DEPTH = """
    import faulthandler, sys, tempfile
    sys.setrecursionlimit(5_000)

    def recurse(n, out):
        if n == 0:
            faulthandler.dump_traceback(out, all_threads=False)
        else:
            recurse(n - 1, out)

    with tempfile.TemporaryFile() as out:
        recurse({depth}, out)
        out.seek(0)
        text = out.read().decode()
    lines = [line for line in text.splitlines() if 'File "' in line]
    print(len(lines), lines[0].endswith(' in recurse'), lines[-1].endswith(' in <module>'))
"""

DUMP_WITH_THREADS = """
    import faulthandler, tempfile, threading
    release = threading.Event()
    threads = [threading.Thread(target=release.wait) for _ in range({extra})]
    for thread in threads:
        thread.start()
    with tempfile.TemporaryFile() as out:
        faulthandler.dump_traceback(out, all_threads={all_threads})
        out.seek(0)
        text = out.read().decode()
    release.set()
    for thread in threads:
        thread.join()
    print(text.count('Thread 0x') + text.count('Current thread 0x'))
    print(text.count('Stack (most recent call first)'))
    print(text.splitlines()[-1])
"""


class TestDumpIsOneLinePerFrame:
    """`dump_traceback()` | O(t·d) | O(1), with t and d capped at 100.

    Counting the lines written separates one line per frame from anything
    that grows faster, and the caps from an unbounded walk.
    """

    @pytest.mark.parametrize("depth", [10, 40, 80])
    def test_frames_below_the_cap_each_get_one_line(self, depth: int) -> None:
        lines, innermost, outermost = child_stdout(DUMP_AT_DEPTH.format(depth=depth)).split()

        # the frames: <module>, recurse() depth + 1 times
        assert int(lines) == depth + 2
        assert (innermost, outermost) == ("True", "True")

    @pytest.mark.parametrize("depth", [150, 1_000])
    def test_a_deeper_stack_keeps_the_innermost_100_frames(self, depth: int) -> None:
        lines, innermost, outermost = child_stdout(DUMP_AT_DEPTH.format(depth=depth)).split()

        assert int(lines) == 100
        assert (innermost, outermost) == ("True", "False")

    @pytest.mark.parametrize("extra", [0, 10, 50])
    def test_every_thread_gets_a_header(self, extra: int) -> None:
        headers, stacks, _ = child_stdout(
            DUMP_WITH_THREADS.format(extra=extra, all_threads=True)
        ).splitlines()

        assert int(headers) == extra + 1
        assert int(stacks) == 0

    def test_more_than_100_threads_stop_at_100(self) -> None:
        headers, _, last = child_stdout(
            DUMP_WITH_THREADS.format(extra=120, all_threads=True)
        ).splitlines()

        assert int(headers) == 100
        assert last == "..."

    def test_all_threads_false_dumps_only_the_caller(self) -> None:
        headers, stacks, _ = child_stdout(
            DUMP_WITH_THREADS.format(extra=10, all_threads=False)
        ).splitlines()

        assert int(headers) == 0
        assert int(stacks) == 1

    def test_long_names_are_cut_so_a_frame_line_is_bounded(self) -> None:
        output = child_stdout(
            """
            import faulthandler, tempfile
            name = 'f' * 2_000
            source = f'def {name}(out): faulthandler.dump_traceback(out, all_threads=False)'
            exec(compile(source, 'g' * 2_000, 'exec'))
            with tempfile.TemporaryFile() as out:
                globals()[name](out)
                out.seek(0)
                lines = out.read().decode().splitlines()
            line = next(line for line in lines if 'fffff' in line)
            print(line.count('g'), line.count('f'))
            """
        )
        gs, fs = map(int, output.split())

        # each name is cut to 500 characters; the rest of the line is short
        assert 500 <= gs < 520, f"the filename kept {gs} characters"
        assert 500 <= fs < 520, f"the function name kept {fs} characters"

    def test_a_dump_allocates_the_same_at_any_depth(self) -> None:
        output = child_stdout(
            """
            import faulthandler, tempfile, tracemalloc

            def recurse(n, out):
                if n == 0:
                    faulthandler.dump_traceback(out, all_threads=False)
                    tracemalloc.start()
                    faulthandler.dump_traceback(out, all_threads=False)
                    peak = tracemalloc.get_traced_memory()[1]
                    tracemalloc.stop()
                    return peak
                return recurse(n - 1, out)

            with tempfile.TemporaryFile() as out:
                print(recurse(10, out.fileno()), recurse(90, out.fileno()))
            """
        )
        shallow, deep = map(int, output.split())

        # 90 frames rendered as Python strings would pass 2 KB many times over
        assert deep < 2_000, f"a 90-frame dump peaked at {deep} bytes"
        assert shallow < 2_000, f"a 10-frame dump peaked at {shallow} bytes"


class TestEnablingInstallsFatalHandlers:
    """`enable()` | O(1) | O(1): installs handlers for the five fatal signals,
    and nothing runs until one arrives; `disable()` restores the previous ones.

    Each signal is sent to a child; a child without `enable()` is the control.
    """

    @POSIX_SIGNALS
    @pytest.mark.parametrize("name", sorted(FATAL_SIGNALS))
    def test_each_fatal_signal_dumps_and_kills(self, name: str) -> None:
        result = run_child(
            f"""
            import faulthandler, os, signal
            faulthandler.enable()
            os.kill(os.getpid(), signal.{name})
            """
        )

        assert f"Fatal Python error: {FATAL_SIGNALS[name]}" in result.stderr
        assert 'File "<string>"' in result.stderr
        assert result.returncode == -getattr(signal, name)

    @POSIX_SIGNALS
    def test_without_enable_there_is_no_dump(self) -> None:
        result = run_child("import os, signal; os.kill(os.getpid(), signal.SIGSEGV)")

        assert "Fatal Python error" not in result.stderr
        assert result.returncode == -signal.SIGSEGV

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows reports an access violation as a fatal exception, not SIGSEGV",
    )
    def test_a_real_fault_is_dumped_and_still_kills(self) -> None:
        result = run_child(
            """
            import ctypes, faulthandler
            faulthandler.enable()
            ctypes.string_at(0)
            """
        )

        assert "Fatal Python error: Segmentation fault" in result.stderr
        assert "in string_at" in result.stderr
        assert result.returncode == -signal.SIGSEGV

    @POSIX_SIGNALS
    def test_disable_restores_the_previous_handler(self) -> None:
        result = run_child(
            """
            import faulthandler, os, signal
            signal.signal(signal.SIGFPE, signal.SIG_IGN)
            faulthandler.enable()
            assert faulthandler.disable() is True
            assert faulthandler.disable() is False
            assert not faulthandler.is_enabled()
            os.kill(os.getpid(), signal.SIGFPE)
            print('still running')
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "still running"
        assert "Fatal Python error" not in result.stderr

    @pytest.mark.skipif(not HAS_PROC_TASKS, reason="counts threads in /proc/self/task")
    def test_enabling_adds_no_hook_and_no_thread(self) -> None:
        output = child_stdout(
            """
            import faulthandler, os, sys
            before = len(os.listdir('/proc/self/task'))
            faulthandler.enable()
            after = len(os.listdir('/proc/self/task'))
            print(faulthandler.is_enabled(), before == after,
                  sys.gettrace() is None, sys.getprofile() is None)
            """
        )

        assert output.split() == ["True", "True", "True", "True"]

    @pytest.mark.parametrize(
        ("args", "env", "expected"),
        [
            ((), {}, "False"),
            (("-X", "faulthandler"), {}, "True"),
            ((), {"PYTHONFAULTHANDLER": "1"}, "True"),
        ],
    )
    def test_startup_switches_enable_it(
        self, args: tuple[str, ...], env: dict[str, str], expected: str
    ) -> None:
        result = run_child("import faulthandler; print(faulthandler.is_enabled())", *args, env=env)

        assert result.stdout.strip() == expected, result.stderr

    @POSIX_SIGNALS
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="c_stack is Python 3.14+")
    @pytest.mark.parametrize(
        ("arguments", "shown"), [("", True), ("c_stack=True", True), ("c_stack=False", False)]
    )
    def test_c_stack_adds_the_c_stack_to_a_fatal_dump(self, arguments: str, shown: bool) -> None:
        result = run_child(
            f"""
            import faulthandler, os, signal
            faulthandler.enable({arguments})
            os.kill(os.getpid(), signal.SIGSEGV)
            """
        )

        assert "Fatal Python error: Segmentation fault" in result.stderr
        assert ("C stack trace" in result.stderr) is shown
        assert result.returncode == -signal.SIGSEGV


def test_dump_c_stack_arrives_in_3_14() -> None:
    import faulthandler

    assert hasattr(faulthandler, "dump_c_stack") is (sys.version_info >= (3, 14))


@pytest.mark.skipif(sys.version_info < (3, 14), reason="dump_c_stack is Python 3.14+")
@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows builds print <cannot get C stack on this system>"
)
class TestDumpCStackIsCapped:
    """`dump_c_stack()` | O(1) | O(1): at most 32 C frames, however deep."""

    def test_a_deep_c_stack_stops_at_32_frames(self) -> None:
        result = run_child(
            """
            import faulthandler

            def recurse(n):
                if n == 0:
                    faulthandler.dump_c_stack()
                else:
                    list(map(recurse, [n - 1]))

            recurse(200)
            """
        )
        lines = result.stderr.splitlines()

        assert result.returncode == 0, result.stderr
        assert lines[0].startswith("Current thread's C stack trace")
        assert sum(line.startswith("  Binary file") for line in lines) <= 32
        assert lines[-1] == "  <truncated rest of calls>"


@pytest.mark.skipif(not HAS_PROC_TASKS, reason="counts threads in /proc/self/task")
class TestWatchdogIsOneThread:
    """`dump_traceback_later()` | O(1) | O(1): one watchdog thread, replacing
    any armed before; each expiry dumps every thread.

    The thread is a C thread, invisible to `threading`, so it is counted in
    /proc/self/task.
    """

    def test_arming_adds_one_thread_and_cancelling_removes_it(self) -> None:
        output = child_stdout(
            """
            import faulthandler, os, time

            def tasks():
                return len(os.listdir('/proc/self/task'))

            baseline = tasks()
            faulthandler.dump_traceback_later(60)
            armed = tasks()
            faulthandler.dump_traceback_later(60)
            deadline = time.monotonic() + 10
            while tasks() != armed and time.monotonic() < deadline:
                time.sleep(0.01)
            rearmed = tasks()
            faulthandler.cancel_dump_traceback_later()
            deadline = time.monotonic() + 10
            while tasks() != baseline and time.monotonic() < deadline:
                time.sleep(0.01)
            print(armed - baseline, rearmed - baseline, tasks() - baseline)
            """
        )

        assert output.split() == ["1", "1", "0"]

    def test_a_cancelled_timer_writes_nothing(self) -> None:
        output = child_stdout(
            """
            import faulthandler, tempfile, time
            with tempfile.TemporaryFile() as log:
                faulthandler.dump_traceback_later(0.2, file=log)
                faulthandler.cancel_dump_traceback_later()
                time.sleep(0.6)
                log.seek(0)
                print(len(log.read()))
            """
        )

        assert output.strip() == "0"

    def test_an_expiry_dumps_every_thread(self) -> None:
        output = child_stdout(
            """
            import faulthandler, tempfile, threading, time
            release = threading.Event()
            threads = [threading.Thread(target=release.wait) for _ in range(3)]
            for thread in threads:
                thread.start()
            with tempfile.TemporaryFile() as log:
                faulthandler.dump_traceback_later(0.05, file=log)
                deadline = time.monotonic() + 10
                while log.tell() == 0 and time.monotonic() < deadline:
                    time.sleep(0.05)
                    log.seek(0, 2)
                faulthandler.cancel_dump_traceback_later()
                log.seek(0)
                text = log.read().decode()
            release.set()
            for thread in threads:
                thread.join()
            print(text.startswith('Timeout (0:00:00.050000)!'), text.count('hread 0x'))
            """
        )
        header, headers = output.split()

        assert header == "True"
        assert int(headers) == 4

    def test_repeat_dumps_more_than_once(self) -> None:
        output = child_stdout(
            """
            import faulthandler, tempfile, time
            with tempfile.TemporaryFile() as log:
                faulthandler.dump_traceback_later(0.05, repeat=True, file=log)
                deadline = time.monotonic() + 10
                count = 0
                while count < 2 and time.monotonic() < deadline:
                    time.sleep(0.05)
                    log.seek(0)
                    count = log.read().count(b'Timeout (')
                faulthandler.cancel_dump_traceback_later()
            print(count)
            """
        )

        assert int(output) >= 2

    def test_exit_ends_the_process_with_status_1(self) -> None:
        result = run_child(
            """
            import faulthandler, time
            faulthandler.dump_traceback_later(0.05, exit=True)
            time.sleep(30)
            """
        )

        assert result.returncode == 1
        assert result.stderr.startswith("Timeout (0:00:00.050000)!")


@pytest.mark.skipif(not hasattr(signal, "SIGUSR1"), reason="needs SIGUSR1")
class TestUserSignalsDumpAndCarryOn:
    """`register()` | O(1) | O(1): each delivery dumps, and the process
    carries on; without `chain=True` the dump replaces the previous handler."""

    def test_each_signal_dumps_once_and_the_process_continues(self) -> None:
        result = run_child(
            """
            import faulthandler, os, signal, tempfile
            with tempfile.TemporaryFile() as log:
                faulthandler.register(signal.SIGUSR1, file=log, all_threads=False)
                for _ in range(3):
                    os.kill(os.getpid(), signal.SIGUSR1)
                print(faulthandler.unregister(signal.SIGUSR1))
                print(faulthandler.unregister(signal.SIGUSR1))
                log.seek(0)
                print(log.read().count(b'Stack (most recent call first)'))
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["True", "False", "3"]

    def test_a_fatal_signal_cannot_be_registered(self) -> None:
        result = run_child(
            """
            import faulthandler, signal
            try:
                faulthandler.register(signal.SIGSEGV)
            except RuntimeError as error:
                print('use enable() instead' in str(error))
            """
        )

        assert result.stdout.strip() == "True", result.stderr

    @pytest.mark.parametrize(("chain", "called"), [("False", "False"), ("True", "True")])
    def test_the_previous_handler_runs_only_with_chain(self, chain: str, called: str) -> None:
        result = run_child(
            f"""
            import faulthandler, os, signal, tempfile
            calls = []
            signal.signal(signal.SIGUSR1, lambda *args: calls.append(1))
            with tempfile.TemporaryFile() as log:
                faulthandler.register(signal.SIGUSR1, file=log, chain={chain})
                os.kill(os.getpid(), signal.SIGUSR1)
                for _ in range(100):
                    pass
                faulthandler.unregister(signal.SIGUSR1)
                log.seek(0)
                print(bool(log.read()), bool(calls))
            """
        )

        assert result.stdout.split() == ["True", called], result.stderr

    def test_the_dump_follows_the_descriptor(self) -> None:
        result = run_child(
            """
            import faulthandler, os, signal, tempfile
            with tempfile.TemporaryFile() as first, tempfile.TemporaryFile() as second:
                faulthandler.register(signal.SIGUSR1, file=first, all_threads=False)
                os.dup2(second.fileno(), first.fileno())
                os.kill(os.getpid(), signal.SIGUSR1)
                faulthandler.unregister(signal.SIGUSR1)
                second.seek(0)
                print(second.read().startswith(b'Stack'))
            """
        )

        assert result.stdout.strip() == "True", result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only absence")
def test_register_is_absent_on_windows() -> None:
    import faulthandler

    assert not hasattr(faulthandler, "register")
    assert not hasattr(faulthandler, "unregister")


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
        preexec_fn=_no_core_dump if os.name == "posix" else None,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so no handler, timer or signal
    registration reaches the test process, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        skipped: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            if sys.platform == "win32" and "faulthandler.register(" in source:
                skipped.append(f"{PAGE.name}:{line}: register() is not available on Windows")
                continue
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "deep == 100" in s)
        mutated = source.replace("deep == 100", "deep == 99", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
