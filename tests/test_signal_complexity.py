"""Tests for docs/stdlib/signal.md.

The page prices almost every call at O(1), and the few that build a set of
signals at O(N) for `N = signal.NSIG`. None of that can be separated by a
stopwatch on one platform, because `N` is a platform constant; what the page
says beyond the table - when a handler runs, what it coalesces, what a mask,
a wait or a wakeup fd does to delivery - is settled by observation. Every test
that installs a handler, arms a timer or changes the mask runs in a fresh
interpreter in a subprocess, so nothing leaks into the pytest process or
depends on which thread pytest runs a test in.

Measurement scope:

* Handlers run between bytecodes: a one-shot `ITIMER_VIRTUAL` timer armed for
  1 ms of CPU time fires inside a `sum()` over `islice(count(), 20_000_000)`,
  and the handler records `count(20000000)` - the counter exhausted - so it ran
  only after the C call returned. Between arming the timer and entering the
  sum the child runs a few bytecodes, microseconds of CPU against the 1 ms
  timer, which is why a CPU-time timer is used. A signal sent by `os.kill()` from a worker thread, and
  one sent by `pthread_kill()` to a worker thread, both run their handler in
  the main thread; `signal.signal()` and `set_wakeup_fd()` from a worker thread
  raise `ValueError`.
* `signal.signal()` returns `SIG_DFL` as a `Handlers` member and then the
  callable it replaced; `getsignal()` returns the same objects. A fresh
  interpreter has `default_int_handler` on `SIGINT`, which raises
  `KeyboardInterrupt`, and `SIG_IGN` on `SIGPIPE`. `raise_signal()` from the
  main thread has run the handler by the next statement.
* Coalescing: five `os.kill()` calls of `SIGUSR1` while it is blocked, then an
  unblock, give one handler call; five of `SIGRTMIN`, which the kernel queues,
  also give one on Linux. The control is five unblocked sends, which give five.
* `pthread_sigmask()` is asserted to consume every item of a generator mask
  (the m term), to return the previous mask as a set of `Signals` members,
  and to have run the handler of a pending signal it unblocks before it
  returns. With `siginterrupt(SIGALRM, False)`, a 200 ms timer that fires
  while the main thread is blocked in `os.read()` on a pipe runs its handler
  only after a worker (with `SIGALRM` blocked) has reached its write, 2 s
  after the timer was armed; with the default, the handler runs before the
  worker reaches it. The margins, 200 ms before the read and 1.8 s after
  the timer, are scheduling assumptions, not guarantees.
* `sigwait()`, `sigwaitinfo()` and `sigtimedwait()` are asserted to consume a
  blocked signal so its handler never runs, even after the unblock;
  `sigtimedwait(..., 0)` returns `None` with nothing pending, and the
  `struct_siginfo` carries the signal and the sending pid. `pause()` returns
  with the handler already run, under a repeating 10 ms timer; after a
  `SIGUSR1` handled before the call, it waits for a repeating 200 ms watchdog
  timer.
* Timers: `alarm()` takes whole seconds only (a float raises `TypeError`) and
  returns the seconds left on the previous alarm (29 or 30 of 30, allowing for
  rounding), `setitimer()` the previous `(delay, interval)`, `getitimer()` the
  current one, and 0 cancels. Each `ITIMER_*` is asserted to send the signal the page
  pairs with it. `ItimerError` is an `OSError` subclass raised for an invalid
  timer. A handler that raises ends a `time.sleep(10)` under a 200 ms timer;
  a marker set on the line before the sleep excludes expiry during setup.
* `set_wakeup_fd()` is asserted to write the signal number as one byte and
  still call the handler, to reject a blocking descriptor, and, with the
  buffer full, to drop the byte, call the handler anyway and print an
  "Exception ignored" report unless `warn_on_full_buffer=False`.
  `asyncio`'s `add_signal_handler()` is asserted to install a wakeup fd.
* `valid_signals()` and `sigpending()` return a new set on every call;
  every valid number is below `NSIG`; on Linux some are plain ints not in
  `Signals`. `strsignal()` raises `ValueError` for 0 and `NSIG`.
* `pidfd_send_signal()` is asserted to run the handler on Linux where
  `os.pidfd_open()` exists.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(N) bound on `valid_signals()`, `sigpending()` and the result of
  `pthread_sigmask()` is read from Modules/signalmodule.c, whose
  `sigset_to_set()` tests every number from 1 to `NSIG - 1`. `N` is fixed per
  platform, so no run on one platform can vary it.
* The O(1) rows are read from the same file: the calls that act are one or
  two system calls each (`sigaction`, `setitimer`, `alarm`, `raise`,
  `pthread_kill`, `pidfd_send_signal`, `fstat` and `fcntl`); `getsignal()`
  and the constants are table or attribute reads; `default_int_handler()`
  raises one exception. Nothing in them depends on an input size a test
  could vary.
* Windows: `valid_signals()` being those seven signals and the
  `CTRL_C_EVENT` and `CTRL_BREAK_EVENT` constants existing are tested under a
  `sys.platform == "win32"` guard that every run this project performs skips.
  That `signal()` accepts only `SIGABRT`, `SIGBREAK`, `SIGFPE`, `SIGILL`,
  `SIGINT`, `SIGSEGV` and `SIGTERM` there is taken from the official
  documentation and is not tested.
  `sigwaitinfo()` and `sigtimedwait()` being absent on macOS is taken from the
  official documentation and CPython's configure checks, not run.
* How long a blocking call waits depends on when a signal arrives, not on any
  input; the tests use a repeating timer or a signal already pending.
* `strsignal()` returning `None` for a number with no description, and
  `getsignal()` returning `None` for a handler not installed from Python, are
  taken from the official documentation: every valid number on Linux has a
  description, and Python records every handler it can see at startup.
* A mask set in one thread does not stop a process-directed signal reaching
  another thread; the mask-deferral tests run a single thread.
* The audit's unclassified runtime names are accounted for: `default_int_handler`
  and `struct_siginfo` with its `si_*` fields are priced on the page;
  `struct_siginfo.n_fields`, `n_sequence_fields` and `n_unnamed_fields` are
  struct-sequence metadata, and `ItimerError.winerror` is inherited from
  `OSError`.
"""

from __future__ import annotations

import pathlib
import re
import signal
import subprocess
import sys
import textwrap

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "signal.md"
EXPECTED_BLOCKS = 11

unix_only = pytest.mark.skipif(sys.platform == "win32", reason="Unix-only API")
linux_only = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-only")


def _run(source: str, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter, in its main thread."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def child(source: str) -> subprocess.CompletedProcess[str]:
    """Run `source` in a subprocess and require it to exit cleanly."""
    result = _run(source)
    assert result.returncode == 0, result.stderr
    return result


class TestHandlersRunBetweenBytecodes:
    """The main thread runs the Python handler at its next check: a C loop that
    runs no Python code and does not check for signals finishes first, and
    the handler runs in the main thread whichever thread received the signal."""

    @unix_only
    def test_a_long_c_call_finishes_before_the_handler_runs(self) -> None:
        child(
            """
            import itertools, signal
            counter = itertools.count()
            seen = []
            signal.signal(signal.SIGVTALRM, lambda s, f: seen.append(repr(counter)))
            signal.setitimer(signal.ITIMER_VIRTUAL, 0.001)
            sum(itertools.islice(counter, 20_000_000))
            assert seen == ["count(20000000)"], seen
            """
        )

    @unix_only
    def test_a_signal_sent_from_a_worker_is_handled_in_the_main_thread(self) -> None:
        child(
            """
            import os, signal, threading
            ran_in = []
            signal.signal(signal.SIGUSR1, lambda s, f: ran_in.append(threading.current_thread()))
            sender = threading.Thread(target=os.kill, args=(os.getpid(), signal.SIGUSR1))
            sender.start()
            sender.join()
            assert ran_in == [threading.main_thread()], ran_in
            """
        )

    @unix_only
    def test_pthread_kill_to_a_worker_still_runs_the_handler_in_the_main_thread(self) -> None:
        child(
            """
            import signal, threading, time
            ran_in = []
            signal.signal(signal.SIGUSR1, lambda s, f: ran_in.append(threading.current_thread()))
            release = threading.Event()
            worker = threading.Thread(target=release.wait)
            worker.start()
            signal.pthread_kill(worker.ident, signal.SIGUSR1)
            deadline = time.monotonic() + 30
            while not ran_in and time.monotonic() < deadline:
                time.sleep(0.001)
            release.set()
            worker.join()
            assert ran_in == [threading.main_thread()], ran_in
            """
        )

    def test_only_the_main_thread_may_install_a_handler(self) -> None:
        child(
            """
            import signal, socket, threading
            errors = []
            def attempt(call):
                try:
                    call()
                except ValueError as error:
                    errors.append(str(error))
            receiver, sender = socket.socketpair()
            sender.setblocking(False)
            calls = [
                lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
                lambda: signal.set_wakeup_fd(sender.fileno()),
            ]
            for call in calls:
                worker = threading.Thread(target=attempt, args=(call,))
                worker.start()
                worker.join()
            assert len(errors) == 2 and all("main thread" in e for e in errors), errors
            """
        )


class TestInstallingAHandler:
    """`signal()` | O(1) | returns the previous handler; `getsignal()` returns
    what `signal()` would; the defaults Python starts with."""

    @unix_only
    def test_signal_returns_what_it_replaced(self) -> None:
        child(
            """
            import signal
            def first(s, f): pass
            def second(s, f): pass
            assert signal.signal(signal.SIGUSR1, first) is signal.SIG_DFL
            assert isinstance(signal.SIG_DFL, signal.Handlers)
            assert signal.getsignal(signal.SIGUSR1) is first
            assert signal.signal(signal.SIGUSR1, second) is first
            assert signal.signal(signal.SIGUSR1, signal.SIG_IGN) is second
            assert signal.getsignal(signal.SIGUSR1) is signal.SIG_IGN
            """
        )

    def test_python_starts_with_default_int_handler_and_sigpipe_ignored(self) -> None:
        child(
            """
            import signal, sys
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
            if sys.platform != "win32":
                assert signal.getsignal(signal.SIGPIPE) is signal.SIG_IGN
            try:
                signal.default_int_handler(signal.SIGINT, None)
            except KeyboardInterrupt:
                pass
            else:
                raise AssertionError("default_int_handler returned")
            """
        )

    def test_raise_signal_has_run_the_handler_by_the_next_statement(self) -> None:
        child(
            """
            import signal
            calls = []
            signal.signal(signal.SIGINT, lambda s, f: calls.append(s))
            signal.raise_signal(signal.SIGINT)
            assert calls == [signal.SIGINT], calls
            """
        )

    def test_a_handler_must_be_callable_or_a_handlers_member(self) -> None:
        child(
            """
            import signal
            try:
                signal.signal(signal.SIGINT, 5)
            except TypeError as error:
                assert "callable" in str(error)
            else:
                raise AssertionError("an int handler was accepted")
            """
        )


@unix_only
class TestDeliveriesCoalesce:
    """Deliveries of one signal that arrive before its handler runs collapse
    into one call - even for real-time signals, which the kernel queues."""

    SOURCE = """
        import os, signal
        signum = {signum}
        calls = []
        signal.signal(signum, lambda s, f: calls.append(s))
        if {blocked}:
            signal.pthread_sigmask(signal.SIG_BLOCK, {{signum}})
        for _ in range(5):
            os.kill(os.getpid(), signum)
        if {blocked}:
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {{signum}})
        assert len(calls) == {expected}, calls
        """

    def test_five_blocked_sends_give_one_call(self) -> None:
        child(self.SOURCE.format(signum="signal.SIGUSR1", blocked=True, expected=1))

    @linux_only
    def test_five_queued_real_time_sends_give_one_call(self) -> None:
        child(self.SOURCE.format(signum="signal.SIGRTMIN", blocked=True, expected=1))

    def test_five_unblocked_sends_give_five_calls(self) -> None:
        """The control: each send is handled before the next one."""
        child(self.SOURCE.format(signum="signal.SIGUSR1", blocked=False, expected=5))


@unix_only
class TestMasks:
    """`pthread_sigmask()` | O(m + N) | O(N); blocking defers a handler,
    `siginterrupt()` does not."""

    def test_pthread_sigmask_reads_every_item_of_the_mask(self) -> None:
        child(
            """
            import signal
            taken = []
            def mask(m):
                for index in range(m):
                    taken.append(index)
                    yield signal.SIGUSR2
            signal.pthread_sigmask(signal.SIG_BLOCK, mask(1000))
            assert len(taken) == 1000, len(taken)
            previous = signal.pthread_sigmask(signal.SIG_SETMASK, [])
            assert previous == {signal.SIGUSR2}, previous
            assert all(isinstance(s, signal.Signals) for s in previous)
            """
        )

    def test_unblocking_runs_the_pending_handler_before_returning(self) -> None:
        child(
            """
            import os, signal
            calls = []
            signal.signal(signal.SIGUSR1, lambda s, f: calls.append(s))
            previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
            os.kill(os.getpid(), signal.SIGUSR1)
            assert calls == [] and signal.sigpending() == {signal.SIGUSR1}
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
            assert calls == [signal.SIGUSR1], calls
            assert signal.sigpending() == set()
            """
        )

    @pytest.mark.parametrize(("restart", "handled_after_write"), [(True, True), (False, False)])
    def test_siginterrupt_false_holds_the_handler_until_a_blocking_call_ends(
        self, restart: bool, handled_after_write: bool
    ) -> None:
        child(
            f"""
            import os, signal, threading
            read_end, write_end = os.pipe()
            written = threading.Event()
            masked = threading.Event()
            armed = threading.Event()
            def writer():
                signal.pthread_sigmask(signal.SIG_BLOCK, {{signal.SIGALRM}})
                masked.set()
                armed.wait()
                threading.Event().wait(2.0)
                written.set()
                os.write(write_end, b"x")
            seen = []
            signal.signal(signal.SIGALRM, lambda s, f: seen.append(written.is_set()))
            if {restart}:
                signal.siginterrupt(signal.SIGALRM, False)
            thread = threading.Thread(target=writer)
            thread.start()
            masked.wait()
            signal.setitimer(signal.ITIMER_REAL, 0.2)
            armed.set()
            assert os.read(read_end, 1) == b"x"
            thread.join()
            assert seen == [{handled_after_write}], seen
            """
        )


@unix_only
class TestWaiting:
    """`sigwait()`, `sigwaitinfo()`, `sigtimedwait()` consume a blocked signal;
    `pause()` returns after the handler has run."""

    def test_sigwait_consumes_the_signal(self) -> None:
        child(
            """
            import os, signal
            calls = []
            signal.signal(signal.SIGUSR1, lambda s, f: calls.append(s))
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
            os.kill(os.getpid(), signal.SIGUSR1)
            assert signal.sigwait({signal.SIGUSR1}) is signal.SIGUSR1
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})
            assert calls == [], calls
            """
        )

    @pytest.mark.skipif(not hasattr(signal, "sigtimedwait"), reason="no sigtimedwait here")
    def test_sigtimedwait_and_sigwaitinfo_return_siginfo_and_consume(self) -> None:
        child(
            """
            import os, signal
            calls = []
            signal.signal(signal.SIGUSR1, lambda s, f: calls.append(s))
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
            assert signal.sigtimedwait({signal.SIGUSR1}, 0) is None
            os.kill(os.getpid(), signal.SIGUSR1)
            info = signal.sigtimedwait({signal.SIGUSR1}, 5)
            assert isinstance(info, signal.struct_siginfo)
            assert (info.si_signo, info.si_pid) == (signal.SIGUSR1, os.getpid()), info
            os.kill(os.getpid(), signal.SIGUSR1)
            info = signal.sigwaitinfo({signal.SIGUSR1})
            assert info.si_signo == signal.SIGUSR1
            for name in ("si_code", "si_errno", "si_uid", "si_status", "si_band"):
                assert isinstance(getattr(info, name), int)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})
            assert calls == [], calls
            """
        )

    def test_pause_ignores_a_signal_handled_before_it_started(self) -> None:
        """The race the page warns about: an early signal does not end the wait,
        so only the later watchdog timer does."""
        child(
            """
            import signal
            handled = []
            signal.signal(signal.SIGUSR1, lambda s, f: handled.append("early"))
            signal.signal(signal.SIGALRM, lambda s, f: handled.append("watchdog"))
            signal.raise_signal(signal.SIGUSR1)
            signal.setitimer(signal.ITIMER_REAL, 0.2, 0.2)
            signal.pause()
            signal.setitimer(signal.ITIMER_REAL, 0)
            assert handled[:2] == ["early", "watchdog"], handled
            """
        )

    def test_pause_returns_after_the_handler_has_run(self) -> None:
        child(
            """
            import signal
            ticks = []
            signal.signal(signal.SIGALRM, lambda s, f: ticks.append(s))
            signal.setitimer(signal.ITIMER_REAL, 0.01, 0.01)
            signal.pause()
            seen = len(ticks)
            signal.setitimer(signal.ITIMER_REAL, 0)
            assert seen >= 1, seen
            """
        )


@unix_only
class TestTimers:
    """`alarm()`, `setitimer()`, `getitimer()` | O(1); each `ITIMER_*` sends
    its own signal; `ItimerError` is an `OSError`."""

    def test_alarm_returns_the_seconds_left(self) -> None:
        child(
            """
            import signal
            assert signal.alarm(30) == 0
            assert 29 <= signal.alarm(0) <= 30
            assert signal.alarm(0) == 0
            try:
                signal.alarm(0.5)
            except TypeError:
                pass
            else:
                raise AssertionError("alarm() took a fraction")
            """
        )

    def test_setitimer_returns_the_previous_timer(self) -> None:
        child(
            """
            import signal
            assert signal.setitimer(signal.ITIMER_REAL, 5, 1) == (0.0, 0.0)
            delay, interval = signal.getitimer(signal.ITIMER_REAL)
            assert 0 < delay <= 5 and interval == 1.0, (delay, interval)
            delay, interval = signal.setitimer(signal.ITIMER_REAL, 0)
            assert 0 < delay <= 5 and interval == 1.0, (delay, interval)
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
            """
        )

    @pytest.mark.parametrize(
        ("which", "signum"),
        [("ITIMER_REAL", "SIGALRM"), ("ITIMER_VIRTUAL", "SIGVTALRM"), ("ITIMER_PROF", "SIGPROF")],
    )
    def test_each_timer_sends_its_own_signal(self, which: str, signum: str) -> None:
        child(
            f"""
            import signal, time
            hits = []
            for name in ("SIGALRM", "SIGVTALRM", "SIGPROF"):
                signal.signal(getattr(signal, name), lambda s, f, n=name: hits.append(n))
            signal.setitimer(signal.{which}, 0.001)
            deadline = time.monotonic() + 30
            while not hits and time.monotonic() < deadline:
                sum(range(10_000))
            assert hits == ["{signum}"], hits
            """
        )

    def test_itimer_error_is_an_oserror(self) -> None:
        assert issubclass(signal.ItimerError, OSError)
        with pytest.raises(signal.ItimerError):
            signal.getitimer(-5)

    def test_a_raising_handler_ends_a_sleep(self) -> None:
        child(
            """
            import signal, time
            def expire(s, f):
                raise TimeoutError
            signal.signal(signal.SIGALRM, expire)
            sleeping = False
            try:
                signal.setitimer(signal.ITIMER_REAL, 0.2)
                sleeping = True
                time.sleep(10)
            except TimeoutError:
                assert sleeping, "the timer fired before the sleep started"
            else:
                raise AssertionError("the sleep ran to completion")
            """
        )


@unix_only
class TestWakeupFd:
    """`set_wakeup_fd()` | O(1): one byte per handled delivery, in addition to
    the handler; a non-blocking fd only; a full buffer drops the byte."""

    SETUP = """
        import os, signal, socket
        receiver, sender = socket.socketpair()
        receiver.setblocking(False)
        sender.setblocking(False)
        calls = []
        signal.signal(signal.SIGUSR1, lambda s, f: calls.append(s))
        """

    def test_each_delivery_writes_the_signal_number_and_calls_the_handler(self) -> None:
        child(
            self.SETUP
            + """
        assert signal.set_wakeup_fd(sender.fileno()) == -1
        signal.raise_signal(signal.SIGUSR1)
        assert receiver.recv(16) == bytes([signal.SIGUSR1])
        assert calls == [signal.SIGUSR1]
        assert signal.set_wakeup_fd(-1) == sender.fileno()
        """
        )

    def test_a_blocking_descriptor_is_rejected(self) -> None:
        child(
            """
            import os, signal
            read_end, write_end = os.pipe()
            try:
                signal.set_wakeup_fd(write_end)
            except ValueError as error:
                assert "non-blocking" in str(error)
            else:
                raise AssertionError("accepted")
            """
        )

    @pytest.mark.parametrize("warn", [True, False])
    def test_a_full_buffer_drops_the_byte_but_not_the_handler(self, warn: bool) -> None:
        result = child(
            self.SETUP
            + f"""
        try:
            while True:
                sender.send(b"x" * 4096)
        except BlockingIOError:
            pass
        signal.set_wakeup_fd(sender.fileno(), warn_on_full_buffer={warn})
        signal.raise_signal(signal.SIGUSR1)
        assert calls == [signal.SIGUSR1]
        """
        )
        reported = "Exception ignored" in result.stderr
        assert reported is warn, result.stderr

    def test_asyncio_add_signal_handler_installs_a_wakeup_fd(self) -> None:
        child(
            """
            import asyncio, signal
            async def main():
                loop = asyncio.get_running_loop()
                received = asyncio.Event()
                loop.add_signal_handler(signal.SIGUSR1, received.set)
                fd = signal.set_wakeup_fd(-1)
                signal.set_wakeup_fd(fd)
                assert fd != -1
                signal.raise_signal(signal.SIGUSR1)
                await asyncio.wait_for(received.wait(), 30)
                loop.remove_signal_handler(signal.SIGUSR1)
            asyncio.run(main())
            """
        )


class TestSetsOfSignals:
    """`valid_signals()` and `sigpending()` | O(N) | O(N): a new set of
    every matching number below `NSIG` on each call."""

    def test_valid_signals_is_a_new_set_below_nsig(self) -> None:
        first = signal.valid_signals()

        assert signal.valid_signals() is not first
        assert signal.SIGINT in first
        assert all(0 < number < signal.NSIG for number in first)

    @linux_only
    def test_numbers_without_a_name_stay_plain_ints(self) -> None:
        valid = signal.valid_signals()
        plain = [number for number in valid if not isinstance(number, signal.Signals)]

        assert plain, "every valid signal had a Signals member"
        assert all(type(number) is int for number in plain)
        assert signal.SIGRTMIN in valid and isinstance(signal.SIGRTMIN, signal.Signals)

    @unix_only
    def test_sigpending_is_a_new_set(self) -> None:
        first = signal.sigpending()

        assert isinstance(first, set)
        assert signal.sigpending() is not first

    def test_strsignal_describes_valid_numbers_only(self) -> None:
        assert isinstance(signal.strsignal(signal.SIGINT), str)
        for number in (0, signal.NSIG):
            with pytest.raises(ValueError, match="out of range"):
                signal.strsignal(number)


class TestEnumsAndConstants:
    """The enums, `SIG_DFL`/`SIG_IGN`, `NSIG`, `ITIMER_*` and `SIG_BLOCK`
    and friends are O(1) attribute reads with the documented meaning."""

    def test_the_enums_hold_their_members(self) -> None:
        assert signal.Signals(signal.SIGINT.value) is signal.SIGINT
        assert signal.SIGINT.name == "SIGINT"
        assert set(signal.Handlers) == {signal.SIG_DFL, signal.SIG_IGN}

    @unix_only
    def test_sigmasks_are_the_how_of_pthread_sigmask(self) -> None:
        assert set(signal.Sigmasks) == {signal.SIG_BLOCK, signal.SIG_UNBLOCK, signal.SIG_SETMASK}
        for name in ("SIGALRM", "SIGUSR1", "SIGVTALRM", "SIGPROF"):
            assert isinstance(getattr(signal, name), signal.Signals)
        assert len({signal.ITIMER_REAL, signal.ITIMER_VIRTUAL, signal.ITIMER_PROF}) == 3

    def test_nsig_is_above_every_signal(self) -> None:
        assert max(signal.valid_signals()) < signal.NSIG
        assert all(member < signal.NSIG for member in signal.Signals if member > 0)

    @unix_only
    def test_sigbreak_and_ctrl_events_are_windows_only(self) -> None:
        for name in ("SIGBREAK", "CTRL_C_EVENT", "CTRL_BREAK_EVENT"):
            assert not hasattr(signal, name), name


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(signal, "pidfd_send_signal"),
    reason="Linux 5.1+ only",
)
class TestPidfdSendSignal:
    """`pidfd_send_signal()` | O(1) | Linux 5.1+."""

    def test_it_delivers_to_the_process_behind_the_pidfd(self) -> None:
        child(
            """
            import os, signal
            calls = []
            signal.signal(signal.SIGUSR1, lambda s, f: calls.append(s))
            pidfd = os.pidfd_open(os.getpid())
            signal.pidfd_send_signal(pidfd, signal.SIGUSR1)
            os.close(pidfd)
            assert calls == [signal.SIGUSR1], calls
            """
        )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only API")
class TestWindows:
    """Windows `signal()` accepts seven signals, and the console events exist.
    No run this project performs reaches these."""

    def test_valid_signals_are_the_seven(self) -> None:
        names = {"SIGABRT", "SIGBREAK", "SIGFPE", "SIGILL", "SIGINT", "SIGSEGV", "SIGTERM"}

        assert {signal.Signals(number).name for number in signal.valid_signals()} == names

    def test_the_console_events_exist(self) -> None:
        assert isinstance(signal.CTRL_C_EVENT, int)  # type: ignore[attr-defined]
        assert isinstance(signal.CTRL_BREAK_EVENT, int)  # type: ignore[attr-defined]


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


@unix_only
class TestDocumentedExamples:
    """Each block runs in its own interpreter, in its main thread, so the
    handlers, timers and masks it sets cannot reach pytest or another block;
    each asserts its own result. The blocks use Unix-only APIs."""

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
        line, source = next((n, s) for n, s in _blocks() if "five sends, one call" in s)
        mutated = source.replace(
            "assert calls == [signal.SIGUSR1]  # five sends",
            "assert len(calls) == 5  # five sends",
            1,
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
