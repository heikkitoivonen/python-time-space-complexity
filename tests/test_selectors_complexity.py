"""Tests for docs/stdlib/selectors.md.

The page prices registration as a dict entry keyed by descriptor and puts the
difference between the implementations in `select()`: select and poll pay for
every registration on every call, epoll pays in time only for what is ready
but allocates for every registration. Registration, lookup and the map view
are settled by observation - identity, returned keys, recorded system calls
and raised errors. The `select()` bounds are settled by timing and traced
allocation over a growing number of idle pipes with nothing ready, and the
closed-file fallback by timing against a growing number of registrations.

Measurement scope:

* `select(0)` with nothing ready, registrations growing 100x: from 20 to
  2,000 pipes for `PollSelector` and `EpollSelector`, from 4 to 400 for
  `SelectSelector` (which cannot take a descriptor at or above
  `FD_SETSIZE`). `PollSelector` time grows more than 20x, `SelectSelector`
  more than 5x, and `EpollSelector` less than 4x. `EpollSelector`'s traced
  peak grows more than 50x and `SelectSelector`'s more than 2x, while
  `PollSelector`'s stays under 1 KB at both sizes. Each call is warmed once
  first, so poll's rebuild of its array after a registration is not in the
  measurement.
* `select()` over 200 pipes with one ready returns exactly that one pair on
  every implementation this platform has, with `events` masked to what was
  registered.
* `unregister()` of a file object whose `fileno()` raises, registered last
  behind 1,000 and then 100,000 integer descriptors on a `SelectSelector`
  (which makes no system call): time grows more than 20x, while unregistering
  the same object with `fileno()` working stays under 5x the smaller time
  plus 5 us. `get_key()` and
  `modify()` on the closed object are asserted to find it.
* `modify()` changing only `data` is observed to make no call on the
  underlying poll or epoll object, and changing `events` to make exactly one.
* `get_map()` returns the same object on every call, sees registrations made
  after it was taken, iterates descriptors, and is `None` after `close()`;
  `get_key()` then raises `RuntimeError`. `close()` over 1,000 and 100,000
  integer registrations grows more than 20x in time.
* `close()` and leaving a `with` block close the epoll descriptor and leave
  the registered sockets open.
* `DefaultSelector` is `EpollSelector` on Linux. `register()` raises
  `KeyError` for a descriptor registered twice and `ValueError` for an empty
  or unknown event mask. `SelectSelector.select()` raises `ValueError` for a
  descriptor numbered 1,100, above `FD_SETSIZE` (1024 on Linux), made with
  `os.dup2` when the open-file limit allows.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `KqueueSelector` (BSD and macOS) and `DevpollSelector` (Solaris) cannot be
  built on Linux, so their rows, the O(L) up-front allocation of
  `DevpollSelector()` and the O(n) result buffer of `KqueueSelector.select()`,
  are read from Modules/selectmodule.c and Lib/selectors.py. The tests guarded
  on `hasattr(selectors, ...)` only run where the class exists.
* The Windows restriction to sockets follows from `select()` on Windows and is
  not exercised on Linux.
* Kernel work is priced as the page states: a single-descriptor system call
  as O(1), `select()` and `poll()` as O(n) and epoll's wait as O(k). Only the
  Python-visible time is measured, over idle pipes; the number ready is held
  at zero in the timing tests, and descriptor numbering and sparseness are not
  varied.
* The time `select()` spends waiting for readiness is outside every bound.
* Masking `events` by the registration is observed for ordinary readiness
  only; error and hangup events are not produced.
"""

from __future__ import annotations

import os
import pathlib
import re
import resource
import select
import selectors
import socket
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "selectors.md"
EXPECTED_BLOCKS = 7


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


class Closable:
    """A file object whose fileno() fails once it is marked closed."""

    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        if self.fd < 0:
            raise ValueError("I/O operation on closed file")
        return self.fd


class RecordingPoller:
    """Wraps a poll or epoll object and records the calls made on it."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)
        if callable(attr):

            def record(*args: Any) -> Any:
                self.calls.append(name)
                return attr(*args)

            return record
        return attr


@pytest.fixture
def pipes() -> Iterator[Callable[[int], list[tuple[int, int]]]]:
    opened: list[tuple[int, int]] = []

    def make(count: int) -> list[tuple[int, int]]:
        made = [os.pipe() for _ in range(count)]
        opened.extend(made)
        return made

    yield make
    for r, w in opened:
        os.close(r)
        os.close(w)


def poll_like_classes() -> list[type[selectors.BaseSelector]]:
    return [
        getattr(selectors, name)
        for name in ("PollSelector", "EpollSelector")
        if hasattr(selectors, name)
    ]


class TestDefaultSelector:
    """`DefaultSelector` is an alias for the best implementation that works."""

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux picks epoll")
    def test_it_is_epoll_on_linux(self) -> None:
        assert selectors.DefaultSelector is selectors.EpollSelector

    def test_every_implementation_is_a_base_selector(self) -> None:
        for name in (
            "SelectSelector",
            "PollSelector",
            "EpollSelector",
            "KqueueSelector",
            "DevpollSelector",
        ):
            cls = getattr(selectors, name, None)
            if cls is not None:
                assert issubclass(cls, selectors.BaseSelector)

    def test_base_selector_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            selectors.BaseSelector()  # type: ignore[abstract]

    def test_the_inherited_modify_is_unregister_then_register(self) -> None:
        calls: list[str] = []

        class Minimal(selectors.BaseSelector):
            def register(self, fileobj: Any, events: int, data: Any = None) -> Any:
                calls.append("register")
                return selectors.SelectorKey(fileobj, fileobj, events, data)

            def unregister(self, fileobj: Any) -> Any:
                calls.append("unregister")

            def select(self, timeout: float | None = None) -> Any:
                return []

            def get_map(self) -> Any:
                return {}

        key = Minimal().modify(5, selectors.EVENT_WRITE, "d")
        assert calls == ["unregister", "register"]
        assert key == (5, 5, selectors.EVENT_WRITE, "d")

    @pytest.mark.skipif(not hasattr(selectors, "EpollSelector"), reason="needs epoll")
    def test_close_releases_the_kernel_object_not_the_files(self) -> None:
        left, right = socket.socketpair()
        try:
            with selectors.EpollSelector() as sel:
                sel.register(left, selectors.EVENT_READ)
                epfd = sel.fileno()
                assert epfd >= 0
            with pytest.raises(OSError):
                os.fstat(epfd)
            assert sel.get_map() is None
            assert left.fileno() >= 0 and right.send(b"x") == 1
        finally:
            left.close()
            right.close()


class TestRegistration:
    """`register`, `unregister`, `modify` and `get_key` rows: one dict entry
    keyed by descriptor, and O(1) system calls."""

    def test_register_returns_the_key_get_key_returns(self) -> None:
        left, right = socket.socketpair()
        try:
            with selectors.DefaultSelector() as sel:
                key = sel.register(left, selectors.EVENT_READ, data="x")
                assert key == (left, left.fileno(), selectors.EVENT_READ, "x")
                assert sel.get_key(left) is key
                assert sel.unregister(left) is key
                with pytest.raises(KeyError):
                    sel.get_key(left)
        finally:
            left.close()
            right.close()

    def test_a_descriptor_registers_once(self) -> None:
        left, right = socket.socketpair()
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(left, selectors.EVENT_READ)
                with pytest.raises(KeyError, match="already registered"):
                    sel.register(left.fileno(), selectors.EVENT_WRITE)
        finally:
            left.close()
            right.close()

    @pytest.mark.parametrize("events", [0, 4, selectors.EVENT_READ | 8])
    def test_empty_or_unknown_events_are_rejected(self, events: int) -> None:
        left, right = socket.socketpair()
        try:
            with selectors.DefaultSelector() as sel:
                with pytest.raises(ValueError, match="Invalid events"):
                    sel.register(left, events)
                assert len(sel.get_map()) == 0
        finally:
            left.close()
            right.close()

    @pytest.mark.parametrize("cls", poll_like_classes())
    def test_changing_only_data_makes_no_system_call(
        self, cls: type[selectors.BaseSelector]
    ) -> None:
        left, right = socket.socketpair()
        try:
            with cls() as sel:
                old = sel.register(left, selectors.EVENT_READ, data="a")
                recorder = RecordingPoller(sel._selector)  # type: ignore[attr-defined]
                sel._selector = recorder  # type: ignore[attr-defined]
                try:
                    renamed = sel.modify(left, selectors.EVENT_READ, data="b")
                    assert recorder.calls == []
                    both = selectors.EVENT_READ | selectors.EVENT_WRITE
                    widened = sel.modify(left, both, data="b")
                    assert recorder.calls == ["modify"]
                finally:
                    sel._selector = recorder.inner  # type: ignore[attr-defined]
                assert old.data == "a" and renamed.data == "b"
                assert widened.events == both and renamed.events == selectors.EVENT_READ
                assert sel.get_key(left) is widened
        finally:
            left.close()
            right.close()


class TestClosedFileLookupScans:
    """`unregister()` is O(1), but O(n) once the file object is closed: when
    `fileno()` fails, every registration is scanned for the object itself."""

    @staticmethod
    def unregister_last(count: int, closed: bool) -> int:
        sel = selectors.SelectSelector()
        for fd in range(count):
            sel.register(fd, selectors.EVENT_READ)
        last = Closable(count)
        sel.register(last, selectors.EVENT_READ)
        if closed:
            last.fd = -1
        start = time.perf_counter_ns()
        key = sel.unregister(last)
        elapsed = time.perf_counter_ns() - start
        assert key.fileobj is last
        return elapsed

    def test_a_closed_file_is_still_found(self) -> None:
        with selectors.SelectSelector() as sel:
            obj = Closable(3)
            sel.register(obj, selectors.EVENT_READ, data="d")
            obj.fd = -1
            assert sel.get_key(obj).data == "d"
            assert obj in sel.get_map()
            assert sel.modify(obj, selectors.EVENT_READ, data="e").data == "e"
            assert sel.unregister(obj).fd == 3

    def test_a_closed_socket_is_still_found(self) -> None:
        left, right = socket.socketpair()
        with selectors.DefaultSelector() as sel:
            sel.register(left, selectors.EVENT_READ)
            left.close()
            right.close()
            assert left.fileno() == -1
            assert sel.unregister(left).fileobj is left
            assert len(sel.get_map()) == 0

    @pytest.mark.timing
    def test_the_closed_lookup_grows_with_registrations(self) -> None:
        small = min(self.unregister_last(1_000, True) for _ in range(5))
        large = min(self.unregister_last(100_000, True) for _ in range(5))
        assert large > 20 * small, (
            f"closed unregister: {small}ns at 1,000 and {large}ns at 100,000; "
            "a scan predicts about 100x"
        )

    @pytest.mark.timing
    def test_the_open_lookup_does_not(self) -> None:
        small = min(self.unregister_last(1_000, False) for _ in range(5))
        large = min(self.unregister_last(100_000, False) for _ in range(5))
        assert large < 5 * small + 5_000, (
            f"open unregister: {small}ns at 1,000 and {large}ns at 100,000; "
            "a dict lookup predicts no growth"
        )


class TestTheMapIsAView:
    """`get_map()` is O(1): the same read-only view on every call, not a copy;
    iterating it yields descriptors; `close()` drops it."""

    def test_the_same_live_view_every_time(self) -> None:
        left, right = socket.socketpair()
        try:
            with selectors.DefaultSelector() as sel:
                mapping = sel.get_map()
                assert sel.get_map() is mapping
                sel.register(left, selectors.EVENT_READ, data="l")
                sel.register(right, selectors.EVENT_WRITE, data="r")
                assert len(mapping) == 2
                assert mapping[left].data == "l" and right in mapping
                assert set(mapping) == {left.fileno(), right.fileno()}
                assert {key.data for key in mapping.values()} == {"l", "r"}
                with pytest.raises(TypeError):
                    mapping[left] = None  # type: ignore[index]
        finally:
            left.close()
            right.close()

    def test_close_drops_the_map(self) -> None:
        sel = selectors.SelectSelector()
        sel.register(3, selectors.EVENT_READ)
        sel.close()
        assert sel.get_map() is None
        with pytest.raises(RuntimeError, match="closed"):
            sel.get_key(3)

    @pytest.mark.timing
    def test_close_is_linear_in_registrations(self) -> None:
        def close_time(count: int) -> int:
            sel = selectors.SelectSelector()
            for fd in range(count):
                sel.register(fd, selectors.EVENT_READ)
            start = time.perf_counter_ns()
            sel.close()
            return time.perf_counter_ns() - start

        small = min(close_time(1_000) for _ in range(5))
        large = min(close_time(100_000) for _ in range(5))
        assert large > 20 * small, f"close: {small}ns at 1,000, {large}ns at 100,000"


class TestSelectReturnsReadyPairs:
    """`select()` returns k `(key, events)` pairs, events masked by what was
    registered, and the same pairs from select, poll and epoll."""

    @staticmethod
    def classes() -> list[type[selectors.BaseSelector]]:
        return [selectors.SelectSelector, *poll_like_classes()]

    def test_one_ready_among_many(self, pipes: Callable[[int], list[tuple[int, int]]]) -> None:
        made = pipes(200)
        os.write(made[57][1], b"x")
        for cls in self.classes():
            with cls() as sel:
                for r, _ in made:
                    sel.register(r, selectors.EVENT_READ, data=r)
                ready = sel.select(timeout=0)
                assert [(key.data, events) for key, events in ready] == [
                    (made[57][0], selectors.EVENT_READ)
                ], cls.__name__

    def test_events_are_masked_by_the_registration(self) -> None:
        left, right = socket.socketpair()
        try:
            right.send(b"x")  # left is now readable and writable
            for cls in self.classes():
                with cls() as sel:
                    sel.register(left, selectors.EVENT_WRITE)
                    assert [e for _, e in sel.select(0)] == [selectors.EVENT_WRITE]
                    sel.modify(left, selectors.EVENT_READ | selectors.EVENT_WRITE)
                    assert [e for _, e in sel.select(0)] == [
                        selectors.EVENT_READ | selectors.EVENT_WRITE
                    ]
        finally:
            left.close()
            right.close()

    def test_nothing_ready_is_an_empty_list(self) -> None:
        for cls in self.classes():
            with cls() as sel:
                assert sel.select(timeout=0) == []

    @pytest.mark.skipif(not hasattr(select, "select"), reason="needs select()")
    def test_select_selector_rejects_a_high_descriptor(self) -> None:
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        high = 1100
        if soft <= high:
            pytest.skip(f"open-file limit {soft} is too low to place a descriptor at {high}")
        with pytest.raises(OSError):
            os.fstat(high)  # dup2 must not replace a descriptor in use
        r, w = os.pipe()
        try:
            os.dup2(r, high)
            try:
                with selectors.SelectSelector() as sel:
                    sel.register(high, selectors.EVENT_READ)
                    with pytest.raises(ValueError, match="out of range"):
                        sel.select(0)
            finally:
                os.close(high)
        finally:
            os.close(r)
            os.close(w)


class TestSelectScaling:
    """The select-by-implementation rows: select O(n) time and space, poll
    O(n) time and O(k) space, epoll O(k) time and O(n) space. Nothing is ready,
    so k = 0 throughout and only n moves."""

    @staticmethod
    def build(
        kind: type[selectors.BaseSelector],
        count: int,
        pipes: Callable[[int], list[tuple[int, int]]],
    ) -> selectors.BaseSelector:
        sel = kind()
        for r, _ in pipes(count):
            sel.register(r, selectors.EVENT_READ)
        assert sel.select(0) == []  # warm, and poll rebuilds its array here
        return sel

    def measure(
        self,
        cls: type[selectors.BaseSelector],
        sizes: tuple[int, int],
        pipes: Callable[[int], list[tuple[int, int]]],
    ) -> tuple[list[float], list[int]]:
        times: list[float] = []
        peaks: list[int] = []
        for count in sizes:
            sel = self.build(cls, count, pipes)
            try:
                times.append(best_ns(partial(sel.select, 0), inner=20))
                peaks.append(peak_bytes(partial(sel.select, 0)))
            finally:
                sel.close()
        return times, peaks

    @pytest.mark.timing
    def test_select_selector_is_linear_in_time_and_space(
        self, pipes: Callable[[int], list[tuple[int, int]]]
    ) -> None:
        times, peaks = self.measure(selectors.SelectSelector, (4, 400), pipes)
        assert times[1] > 5 * times[0], f"select() times {times}"
        assert peaks[1] > 2 * peaks[0], f"select() peaks {peaks}"

    @pytest.mark.timing
    @pytest.mark.skipif(not hasattr(selectors, "PollSelector"), reason="needs poll")
    def test_poll_selector_is_linear_in_time_only(
        self, pipes: Callable[[int], list[tuple[int, int]]]
    ) -> None:
        times, peaks = self.measure(selectors.PollSelector, (20, 2_000), pipes)
        assert times[1] > 20 * times[0], f"poll times {times}"
        assert max(peaks) < 1_000, f"poll peaks {peaks}"

    @pytest.mark.timing
    @pytest.mark.skipif(not hasattr(selectors, "EpollSelector"), reason="needs epoll")
    def test_epoll_selector_is_linear_in_space_only(
        self, pipes: Callable[[int], list[tuple[int, int]]]
    ) -> None:
        times, peaks = self.measure(selectors.EpollSelector, (20, 2_000), pipes)
        assert times[1] < 4 * times[0], f"epoll times {times}"
        assert peaks[1] > 50 * max(peaks[0], 1), f"epoll peaks {peaks}"


class TestSelectorKey:
    """`SelectorKey` is a named tuple, so it cannot be changed in place."""

    def test_fields_and_immutability(self) -> None:
        key = selectors.SelectorKey(7, 3, selectors.EVENT_READ, None)
        assert (key.fileobj, key.fd, key.events, key.data) == (7, 3, 1, None)
        assert isinstance(key, tuple)
        with pytest.raises(AttributeError):
            key.data = "x"  # type: ignore[misc]

    def test_event_flags_are_distinct_bits(self) -> None:
        assert selectors.EVENT_READ & selectors.EVENT_WRITE == 0
        assert selectors.EVENT_READ | selectors.EVENT_WRITE == 3


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
        line, source = next((n, s) for n, s in _blocks() if "len(ready) == 1" in s)
        mutated = source.replace("len(ready) == 1", "len(ready) == 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
