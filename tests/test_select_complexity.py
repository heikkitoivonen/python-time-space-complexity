"""Tests for docs/stdlib/select.md.

The page prices each mechanism by who keeps the descriptor set: `select()`
and `poll()` hand the kernel every descriptor on every call and cost O(n),
while epoll returns only what is ready and costs O(k). Growth is settled by
timing and traced allocation over a growing number of idle descriptors with
nothing ready; errors, returned objects, masks and the epoll result cap are
settled by observation. Descriptors are `os.dup()` copies of one pipe end, so
a thousand of them cost a thousand descriptors rather than two thousand, and
a test that needs more than the open-file soft limit allows raises it for its
own duration, skipping when the hard limit is lower still.

Measurement scope:

* `select.select()` with nothing ready, from 9 to 900 descriptors: time grows
  more than 10x. Given a list, the traced peak at 900 stays under 1 KB; given
  a list iterator, it exceeds 5 KB, which is the O(n) copy. The returned
  lists are new lists holding the objects passed in. A descriptor numbered
  1024 or above raises `ValueError` ("out of range"), as does a list of 1,025
  entries ("too many").
* `poll.poll()` with nothing ready, from 20 to 2,000 registrations: time grows
  more than 20x and the steady-state traced peak stays under 1 KB at both
  sizes. The first call after 2,000 registrations peaks above 10 KB, which is
  the array rebuild, and above 100x the peak of the call after it.
* `epoll.poll()` with nothing ready, from 20 to 2,000 registrations: time
  grows less than 4x, and the traced peak is the same at both sizes to within
  1 KB. The default peak exceeds 10 KB (1,023 buffer entries) and the peak
  with `maxevents=10` is under a tenth of it. With 1,100 writable descriptors
  registered, the default returns 1,023 events and `maxevents=2000` returns
  all 1,100.
* `epoll.close()` over 400 and 40,000 registrations: time grows more than 20x.
  The registered pipe stays open afterwards.
* `epoll` raises `FileExistsError` for a second registration,
  `FileNotFoundError` for modifying or unregistering an unknown descriptor,
  `PermissionError` for a regular file, and `ValueError` from `register()`,
  `modify()`, `unregister()`, `poll()` and `fileno()` once closed; a second
  `close()` does not raise. `fromfd()` over a duplicate of an epoll
  descriptor reaches the same epoll instance. Descriptors from `epoll()` are
  not inheritable with or without `flags=EPOLL_CLOEXEC`, and any other
  nonzero `flags` raises `OSError`.
  `poll.modify()` raises `FileNotFoundError` and `poll.unregister()`
  `KeyError` for an unknown descriptor, and registering again replaces the
  mask.
* `select.error` is `OSError`. `PIPE_BUF` is at least 512, and a non-blocking
  write of `PIPE_BUF` bytes to an empty pipe that `select()` reports writable
  writes them all. `EPOLLWAKEUP` is asserted present on 3.14+.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail on that assertion. The
  `FD_SETSIZE` block does its work only where the open-file limit is above
  1024, which it is on this project's Linux runs.

Not settled here:

* `kqueue`, `kevent` and `devpoll` do not exist on Linux, so their rows - the
  O(c + k) time and O(c + e) space of `kqueue.control()`, the O(L) array of
  `devpoll()` and its amortized O(1) buffered registrations, the O(n) close
  of `devpoll` and the O(n + q) close of `kqueue`, whose q term is the
  3.12+ walk of the process's list of open kqueues - are read from
  Modules/selectmodule.c. The kernel side of each close is taken to be linear
  in the registrations, as epoll's is measured to be. The tests guarded on
  `hasattr(select, ...)` run only where the objects exist, and the kqueue
  example's body runs only there.
* The Windows rows - `select()` taking only sockets, and no `poll`, `epoll`,
  `kqueue` or `devpoll` - follow from Modules/selectmodule.c and are not
  exercised on Linux.
* Kernel work is priced as the page states: a system call that adds, changes
  or removes one descriptor as O(1), `select()` and `poll()` as O(n), and
  epoll's wait as O(k). epoll keeps its interest set in a tree; `modify()` on
  one descriptor measured about 2x slower at 100,000 registrations than at
  100, which is within what cache effects alone produce, and is not asserted.
  The kernel's `select()` also scans descriptor numbers up to the highest one
  passed; one descriptor at 1,000 against one at 3 differs by under 25%, and
  numbering is not otherwise varied.
* The time a call spends waiting for readiness is outside every bound, and
  the number ready is held at zero in the timing tests, so the k term of the
  O(k) rows is not varied.
* The `poll` array rebuild is measured after `register()` only; that
  `modify()` and `unregister()` mark the same array stale is read from
  Modules/selectmodule.c.
"""

from __future__ import annotations

import fcntl
import os
import pathlib
import re
import resource
import select
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "select.md"
EXPECTED_BLOCKS = 6

needs_poll = pytest.mark.skipif(not hasattr(select, "poll"), reason="needs poll()")
needs_epoll = pytest.mark.skipif(not hasattr(select, "epoll"), reason="needs epoll")


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
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


@pytest.fixture
def pipe() -> Iterator[tuple[int, int]]:
    r, w = os.pipe()
    yield r, w
    os.close(r)
    os.close(w)


@pytest.fixture
def fd_limit() -> Iterator[Callable[[int], None]]:
    """`fd_limit(n)` raises the open-file soft limit to at least `n` for the
    test, or skips it when the hard limit does not allow that."""
    original = resource.getrlimit(resource.RLIMIT_NOFILE)

    def at_least(wanted: int) -> None:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft == resource.RLIM_INFINITY or soft >= wanted:
            return
        if hard != resource.RLIM_INFINITY and hard < wanted:
            pytest.skip(f"open-file hard limit {hard} is below {wanted}")
        resource.setrlimit(resource.RLIMIT_NOFILE, (wanted, hard))

    yield at_least
    resource.setrlimit(resource.RLIMIT_NOFILE, original)


@pytest.fixture
def dups(fd_limit: Callable[[int], None]) -> Iterator[Callable[[int, int], list[int]]]:
    """`dups(fd, count)` makes `count` copies of `fd`, closed after the test,
    with the open-file limit raised to leave room for them."""
    opened: list[int] = []

    def make(fd: int, count: int) -> list[int]:
        fd_limit(len(opened) + count + 100)
        made: list[int] = []
        for _ in range(count):
            made.append(os.dup(fd))
            opened.append(made[-1])
        return made

    yield make
    for fd in opened:
        os.close(fd)


class TestSelectWalksEveryDescriptor:
    """`select.select()` | O(n) | O(k): every descriptor passed is converted
    and checked on each call; lists and tuples are used in place, any other
    iterable is copied first."""

    @staticmethod
    def low(fds: list[int]) -> list[int]:
        if max(fds) >= 1024:
            pytest.skip("the process already holds too many descriptors for select()")
        return fds

    @pytest.mark.timing
    def test_time_grows_with_descriptors_passed(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = self.low(dups(pipe[0], 900))
        times = []
        for count in (9, 900):
            call = partial(select.select, fds[:count], [], [], 0)
            assert call() == ([], [], [])
            times.append(best_ns(call, inner=20))

        assert times[1] > 10 * times[0], f"select() over 9 and 900 descriptors: {times} ns"

    def test_a_list_is_not_copied(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = self.low(dups(pipe[0], 900))
        call = partial(select.select, fds, [], [], 0)
        call()

        peak = peak_bytes(call)

        assert peak < 1_000, f"select() over a 900-entry list peaked at {peak} bytes"

    def test_any_other_iterable_is(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = self.low(dups(pipe[0], 900))
        select.select(iter(fds), [], [], 0)

        peak = peak_bytes(lambda: select.select(iter(fds), [], [], 0))

        assert peak > 5_000, f"select() over a 900-entry iterator peaked at {peak} bytes"

    def test_it_returns_new_lists_of_the_objects_passed(self, pipe: tuple[int, int]) -> None:
        r, w = pipe

        class Wrapped:
            def fileno(self) -> int:
                return r

        wrapped = Wrapped()
        rlist: list[Any] = [wrapped]
        os.write(w, b"x")

        readable, writable, exceptional = select.select(rlist, [], [], 0)

        assert readable == [wrapped] and readable[0] is wrapped
        assert readable is not rlist
        assert writable == [] and exceptional == []

    def test_a_descriptor_at_fd_setsize_is_rejected(
        self, pipe: tuple[int, int], fd_limit: Callable[[int], None]
    ) -> None:
        fd_limit(2_048)
        high = fcntl.fcntl(pipe[0], fcntl.F_DUPFD, 1024)  # never replaces an open descriptor
        try:
            with pytest.raises(ValueError, match="out of range"):
                select.select([high], [], [], 0)
        finally:
            os.close(high)

    def test_more_than_fd_setsize_entries_are_rejected(self, pipe: tuple[int, int]) -> None:
        with pytest.raises(ValueError, match="too many"):
            select.select([pipe[0]] * 1025, [], [], 0)


@needs_poll
class TestPollChecksEveryRegistration:
    """`poll.poll()` | O(n) | O(k), with an O(n) array rebuild on the first
    call after the registrations change; registration itself is O(1)."""

    @staticmethod
    def poller(fds: list[int]) -> Any:
        poller = select.poll()
        for fd in fds:
            poller.register(fd, select.POLLIN)
        return poller

    @pytest.mark.timing
    def test_time_grows_with_registrations(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = dups(pipe[0], 2_000)
        times = []
        for count in (20, 2_000):
            call = partial(self.poller(fds[:count]).poll, 0)
            assert call() == []
            times.append(best_ns(call, inner=20))

        assert times[1] > 20 * times[0], f"poll() over 20 and 2,000 registrations: {times} ns"

    def test_a_steady_call_allocates_nothing_per_registration(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = dups(pipe[0], 2_000)
        peaks = []
        for count in (20, 2_000):
            call = partial(self.poller(fds[:count]).poll, 0)
            call()
            peaks.append(peak_bytes(call))

        assert max(peaks) < 1_000, f"steady poll() peaks {peaks}"

    def test_the_first_call_after_a_change_rebuilds_the_array_once(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        poller = self.poller(dups(pipe[0], 2_000))

        first = peak_bytes(partial(poller.poll, 0))
        second = peak_bytes(partial(poller.poll, 0))

        assert first > 10_000, f"the first poll() over 2,000 registrations peaked at {first}"
        assert first > 100 * max(second, 1), f"first {first}, second {second}"

    def test_registering_again_replaces_the_mask(self, pipe: tuple[int, int]) -> None:
        r, w = pipe
        poller = select.poll()
        os.write(w, b"x")

        poller.register(r, select.POLLIN)
        assert poller.poll(0) == [(r, select.POLLIN)]
        poller.register(r, select.POLLOUT)
        assert poller.poll(0) == []

    def test_modify_and_unregister_need_a_registration(self, pipe: tuple[int, int]) -> None:
        poller = select.poll()

        with pytest.raises(FileNotFoundError):
            poller.modify(pipe[0], select.POLLIN)
        with pytest.raises(KeyError):
            poller.unregister(pipe[0])


@needs_epoll
class TestEpollReturnsOnlyWhatIsReady:
    """`epoll.poll()` | O(k) | O(e): the kernel returns ready descriptors
    only, into a `maxevents` buffer that defaults to FD_SETSIZE - 1."""

    @staticmethod
    def epoll_over(fds: list[int], mask: int | None = None) -> Any:
        ep = select.epoll()
        for fd in fds:
            ep.register(fd, select.EPOLLIN if mask is None else mask)
        return ep

    @pytest.mark.timing
    def test_time_does_not_grow_with_idle_registrations(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = dups(pipe[0], 2_000)
        times = []
        for count in (20, 2_000):
            with self.epoll_over(fds[:count]) as ep:
                call = partial(ep.poll, 0)
                assert call() == []
                times.append(best_ns(call, inner=20))

        assert times[1] < 4 * times[0], f"epoll.poll() over 20 and 2,000 registrations: {times}"

    def test_the_buffer_follows_maxevents_not_registrations(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = dups(pipe[0], 2_000)
        peaks = []
        for count in (20, 2_000):
            with self.epoll_over(fds[:count]) as ep:
                ep.poll(0)
                peaks.append(peak_bytes(partial(ep.poll, 0)))
                small = peak_bytes(partial(ep.poll, 0, 10))

        assert abs(peaks[1] - peaks[0]) < 1_000, f"default epoll.poll() peaks {peaks}"
        assert peaks[0] > 10_000, f"a 1,023-entry buffer peaked at {peaks[0]}"
        assert small < peaks[0] / 10, f"maxevents=10 peaked at {small} against {peaks[0]}"

    def test_the_default_returns_at_most_1023_events(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        writers = dups(pipe[1], 1_100)
        with self.epoll_over(writers, select.EPOLLOUT) as ep:
            assert len(ep.poll(0)) == 1023
            assert len(ep.poll(0, maxevents=2000)) == 1100
            with pytest.raises(ValueError, match="maxevents"):
                ep.poll(0, maxevents=0)

    def test_registration_errors(self, pipe: tuple[int, int], tmp_path: pathlib.Path) -> None:
        r, _ = pipe
        regular = tmp_path / "file"
        regular.write_bytes(b"")
        with select.epoll() as ep, open(regular, "rb") as handle:
            with pytest.raises(FileNotFoundError):
                ep.modify(r, select.EPOLLIN)
            with pytest.raises(FileNotFoundError):
                ep.unregister(r)
            ep.register(r, select.EPOLLIN)
            with pytest.raises(FileExistsError):
                ep.register(r, select.EPOLLIN)
            with pytest.raises(PermissionError):
                ep.register(handle, select.EPOLLIN)

    def test_a_closed_object_refuses_io_and_registration(self, pipe: tuple[int, int]) -> None:
        r, _ = pipe
        ep = select.epoll()
        ep.register(r, select.EPOLLIN)
        ep.close()
        ep.close()

        assert ep.closed
        for call in (
            partial(ep.register, r),
            partial(ep.modify, r, select.EPOLLIN),
            partial(ep.unregister, r),
            partial(ep.poll, 0),
            ep.fileno,
        ):
            with pytest.raises(ValueError, match="closed"):
                call()
        assert os.fstat(r) is not None, "closing the epoll object closed a registered file"

    def test_fromfd_wraps_an_existing_epoll_descriptor(self, pipe: tuple[int, int]) -> None:
        r, w = pipe
        os.write(w, b"x")
        with select.epoll() as ep:
            # A duplicate, so each object closes a descriptor of its own.
            with select.epoll.fromfd(os.dup(ep.fileno())) as wrapped:
                assert wrapped.fileno() != ep.fileno()
                wrapped.register(r, select.EPOLLIN)
                assert ep.poll(0) == [(r, select.EPOLLIN)], "not the same epoll instance"

    def test_epoll_descriptors_are_close_on_exec_whatever_the_flags(self) -> None:
        with select.epoll() as plain, select.epoll(flags=select.EPOLL_CLOEXEC) as flagged:
            assert not os.get_inheritable(plain.fileno())
            assert not os.get_inheritable(flagged.fileno())
        with pytest.raises(OSError):
            select.epoll(flags=select.EPOLL_CLOEXEC + 1)

    @pytest.mark.timing
    def test_close_is_linear_in_registrations(
        self, pipe: tuple[int, int], dups: Callable[[int, int], list[int]]
    ) -> None:
        fds = dups(pipe[0], 40_000)

        def close_time(count: int) -> int:
            ep = self.epoll_over(fds[:count])
            start = time.perf_counter_ns()
            ep.close()
            return time.perf_counter_ns() - start

        small = min(close_time(400) for _ in range(5))
        large = min(close_time(40_000) for _ in range(3))
        assert large > 20 * small, f"epoll.close(): {small}ns at 400, {large}ns at 40,000"


class TestConstantsAndAliases:
    """The constants and `select.error` rows."""

    def test_error_is_oserror(self) -> None:
        assert select.error is OSError

    def test_pipe_buf_bytes_fit_a_writable_pipe(self, pipe: tuple[int, int]) -> None:
        r, w = pipe
        assert select.PIPE_BUF >= 512
        os.set_blocking(w, False)

        assert select.select([], [w], [], 0)[1] == [w]
        assert os.write(w, b"x" * select.PIPE_BUF) == select.PIPE_BUF

    @needs_poll
    def test_poll_flags_are_distinct_bits(self) -> None:
        flags = [select.POLLIN, select.POLLPRI, select.POLLOUT, select.POLLERR, select.POLLHUP]
        assert all(flag and flag & (flag - 1) == 0 for flag in flags)
        assert len(set(flags)) == len(flags)

    @needs_epoll
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_epollwakeup_arrives_in_314(self) -> None:
        assert hasattr(select, "EPOLLWAKEUP")


@pytest.mark.skipif(not hasattr(select, "kqueue"), reason="BSD and macOS only")
class TestKqueue:
    """`kqueue.control()` applies the changelist, then returns at most
    `maxevents` events; `maxevents=0` only applies the changes."""

    def test_control_applies_then_returns_at_most_maxevents(self) -> None:
        # The stubs this project type-checks against are Linux's, which lack kqueue.
        bsd: Any = select
        kqueue, kevent = bsd.kqueue, bsd.kevent
        read_filter, add = bsd.KQ_FILTER_READ, bsd.KQ_EV_ADD
        pipes = [os.pipe() for _ in range(3)]
        kq = kqueue()
        try:
            changes = [kevent(r, filter=read_filter, flags=add) for r, _ in pipes]
            assert kq.control(changes, 0, 0) == []
            for _, w in pipes:
                os.write(w, b"x")
            assert len(kq.control(None, 2, 0)) == 2
            assert len(kq.control(None, 10, 0)) == 3
        finally:
            kq.close()
            for r, w in pipes:
                os.close(r)
                os.close(w)
        assert kq.closed


@pytest.mark.skipif(not hasattr(select, "devpoll"), reason="Solaris only")
class TestDevpoll:
    """A `devpoll` registration takes effect by the next `poll()`. That it is
    buffered until then is read from Modules/selectmodule.c, not observed."""

    def test_a_buffered_registration_is_seen_by_the_next_poll(self, pipe: tuple[int, int]) -> None:
        r, w = pipe
        solaris: Any = select  # absent from the Linux stubs, as kqueue is
        devpoll = solaris.devpoll
        dp = devpoll()
        try:
            dp.register(r, select.POLLIN)
            os.write(w, b"x")
            assert dp.poll(0) == [(r, select.POLLIN)]
        finally:
            dp.close()
        assert dp.closed


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
    """Each block runs in its own subprocess on local socket pairs and pipes,
    so no network is touched and no descriptor leaks between them."""

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
        line, source = next((n, s) for n, s in _blocks() if "writable == [right]" in s)
        mutated = source.replace("writable == [right]", "writable == []", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "assert writable == []" in result.stderr and "AssertionError" in result.stderr
