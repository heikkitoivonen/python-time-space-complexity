"""Tests for docs/stdlib/resource.md.

The page prices every call in the module at O(1) except one: on Linux,
`getrusage(RUSAGE_SELF)` sums the counters of every thread in the process, so
it is O(t) in threads. Timing the call against a growing number of idle
threads establishes its dependence on t, with the thread-only and
children-only calls as controls that must stay flat. The linear upper bound
comes from the kernel's thread walks. Everything else - what a snapshot holds,
the units of `ru_maxrss`, when children are counted, how soft and hard limits
behave - is settled by observation. The Linux unit check allows for variation
between separately sampled memory counters.

Measurement scope:

* The fastest of seven batches of `getrusage(RUSAGE_SELF)` is measured with
  0, 49 and 499 extra idle threads. The 49-thread cost must exceed the
  baseline, and the 499-thread cost must exceed the 49-thread cost by 3x.
  This distinguishes thread-dependent work from a constant-time snapshot;
  it does not distinguish linear from quadratic growth. Raw costs include
  the fixed syscall and Python result-building costs. `RUSAGE_THREAD`,
  `RUSAGE_CHILDREN` and `getrlimit()` each stay under 3x their baseline at
  both thread counts. Linux only, where getrusage walks the thread group.
* `getrusage()` returns a new `struct_rusage` on every call, 16 items long,
  each attribute equal to the item at its documented index; the two times are
  floats and the other fourteen ints.
* `ru_maxrss` is read beside `/proc/self/status`'s VmHWM on Linux and is within
  a factor of two in either direction, which kilobytes satisfy and bytes
  (1,024x) cannot. These are separate snapshots, not an ordering guarantee;
  Linux v6.12 fs/proc/task_mmu.c's `task_mem()` explicitly allows inconsistent
  snapshots. On macOS it is over 4,000,000 in a test process, which bytes
  satisfy and kilobytes would need a 4 GB process for. It does not fall after
  a touched 64 MB buffer is freed. On Linux `ru_ixrss`, `ru_idrss`,
  `ru_isrss`, `ru_nswap`, `ru_msgsnd`, `ru_msgrcv` and `ru_nsignals` are 0.
* A child that has exited but not been reaped (held with `waitid(WNOWAIT)`)
  adds nothing to `RUSAGE_CHILDREN`; after `wait()` its CPU time is there.
* `getrlimit()` reflects a `setrlimit()` lowering the soft `RLIMIT_FSIZE` at
  once, and the soft limit goes back up to its old value under an unchanged
  hard limit. A soft limit above the hard one raises `ValueError`, as does an
  unknown resource number. In a subprocess that lowers its hard
  `RLIMIT_FSIZE` to half (1,024 if unlimited), raising it back raises
  `ValueError` without the privilege and succeeds with it: `CAP_SYS_RESOURCE`
  in `/proc/self/status`'s CapEff on Linux, effective UID 0 elsewhere.
* `prlimit()` exists on Linux and not on macOS; `prlimit(0, ...)` equals
  `getrlimit()`. `RUSAGE_THREAD` exists on Linux and not on macOS, and
  `RLIMIT_KQUEUES` (FreeBSD) is not an attribute on Linux. `resource.error`
  is `OSError`. `getpagesize()` equals `os.sysconf("SC_PAGE_SIZE")`.
* On Windows, importing `resource` raises `ModuleNotFoundError`.
* With `RLIMIT_FSIZE` at 1,024 bytes, a Python child writing byte 1,025
  gets `EFBIG`, because the interpreter ignores `SIGXFSZ` at startup
  (Modules/signalmodule.c); one that restores `SIG_DFL` dies of `SIGXFSZ`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail. The `prlimit()`
  block runs only where `prlimit()` exists.

Not settled here:

* The O(t) upper bound is sourced from Linux v6.12 kernel/sys.c's
  `getrusage()` / `accumulate_thread_rusage()` and kernel/sched/cputime.c's
  `thread_group_cputime()`: each walk adds a fixed set of counters per
  thread. https://github.com/torvalds/linux/blob/v6.12/kernel/sys.c and
  https://github.com/torvalds/linux/blob/v6.12/kernel/sched/cputime.c.
  Wall-clock ratios do not count kernel operations: cache locality and
  memory placement are uncontrolled, so no upper timing ratio is asserted.
* macOS is not timed: whether its `RUSAGE_SELF` grows with threads is not
  measured, so the page states the thread walk for Linux only. O(t) is an
  upper bound wherever the call is in fact O(1).
* `RUSAGE_CHILDREN` is not varied in the number of children reaped; that the
  kernel keeps one running total is read from Linux's kernel/sys.c.
* `setrlimit()` and `prlimit()` convert one two-item tuple and make one call
  (Modules/resource.c). Not priced by the page: on Linux, a finite
  `RLIMIT_CPU` set while the process's CPU timer is idle starts that timer,
  which reads every thread's CPU time once (kernel/time/posix-cpu-timers.c).
  That call is not timed here: a
  single-shot measurement in a fresh process with 2,000 idle threads cost
  about 5x one with none, against first-call overhead of about 100us, too
  noisy to assert; later calls are flat.
* The macOS unit check assumes a test process under 4 GB; a larger one would
  pass in kilobytes too.
* `struct_rusage.n_fields`, `n_sequence_fields` and `n_unnamed_fields` are
  the counts every struct sequence carries, not documented API, and the page
  does not price them.
* That the kernel sends `SIGXCPU` past the CPU-time soft limit is POSIX
  behaviour the page names only in its related-modules line; triggering it
  takes a second of CPU and is not run.
* That `resource` is absent on WASI follows from the official availability
  note; no WASI build is run.
"""

from __future__ import annotations

import gc
import os
import pathlib
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

if sys.platform != "win32":
    import resource

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "resource.md"
EXPECTED_BLOCKS = 5

UNIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="platform: resource is a Unix-only module"
)

FIELDS = (
    "ru_utime",
    "ru_stime",
    "ru_maxrss",
    "ru_ixrss",
    "ru_idrss",
    "ru_isrss",
    "ru_minflt",
    "ru_majflt",
    "ru_nswap",
    "ru_inblock",
    "ru_oublock",
    "ru_msgsnd",
    "ru_msgrcv",
    "ru_nsignals",
    "ru_nvcsw",
    "ru_nivcsw",
)
"""The struct_rusage fields in index order, from Modules/resource.c."""


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 2_000) -> float:
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


def idle_threads(count: int) -> tuple[threading.Event, list[threading.Thread]]:
    stop = threading.Event()
    threads = [threading.Thread(target=stop.wait) for _ in range(count)]
    try:
        for thread in threads:
            thread.start()
    except BaseException:
        stop.set()
        raise
    return stop, threads


@UNIX_ONLY
@pytest.mark.timing
@pytest.mark.skipif(
    sys.platform != "linux",
    reason="platform: the per-thread sum is Linux's kernel getrusage(RUSAGE_SELF)",
)
class TestRusageSelfWalksEveryThread:
    """`getrusage(RUSAGE_SELF)` | O(t); `RUSAGE_THREAD`, `RUSAGE_CHILDREN` | O(1).

    The same process is timed with 0, 49 and 499 extra idle threads.
    Growing cost distinguishes the thread walk from constant work; the
    controls read one thread or one running total and stay flat. The linear
    upper bound follows from kernel source, not a wall-clock growth ceiling.
    """

    THREADS = (49, 499)

    def _measure(self) -> dict[str, float]:
        calls: dict[str, Callable[[], Any]] = {
            "self": lambda: resource.getrusage(resource.RUSAGE_SELF),
            "thread": lambda: resource.getrusage(resource.RUSAGE_THREAD),
            "children": lambda: resource.getrusage(resource.RUSAGE_CHILDREN),
            "getrlimit": lambda: resource.getrlimit(resource.RLIMIT_NOFILE),
        }
        for call in calls.values():
            call()
        return {name: best_ns(call) for name, call in calls.items()}

    @pytest.fixture
    def costs(self) -> list[dict[str, float]]:
        measurements = [self._measure()]
        for count in self.THREADS:
            stop, threads = idle_threads(count)
            try:
                measurements.append(self._measure())
            finally:
                stop.set()
                for thread in threads:
                    thread.join()
        return measurements

    def test_rusage_self_grows_with_threads(self, costs: list[dict[str, float]]) -> None:
        alone, medium, crowded = (measurement["self"] for measurement in costs)
        assert medium > alone, f"49 extra threads must add work: {costs}"
        ratio = crowded / medium
        assert ratio > 3, (
            f"RUSAGE_SELF cost {alone:.0f}, {medium:.0f}, {crowded:.0f}ns with "
            f"0, 49, 499 extra threads; 49-to-499 growth x{ratio:.1f}; "
            "constant-time work would stay near x1"
        )

    @pytest.mark.parametrize("name", ["thread", "children", "getrlimit"])
    def test_the_controls_do_not(self, costs: list[dict[str, float]], name: str) -> None:
        alone = costs[0][name]
        for count, measurement in zip(self.THREADS, costs[1:], strict=True):
            ratio = measurement[name] / alone
            assert ratio < 3, (
                f"{name} cost {alone:.0f}ns alone and {measurement[name]:.0f}ns beside "
                f"{count} threads (x{ratio:.1f}); it should not depend on them"
            )


@UNIX_ONLY
class TestStructRusage:
    """`resource.struct_rusage` | a 16-item tuple whose items are also attributes.

    And `getrusage()` keeps no state: each call is a new snapshot.
    """

    def test_each_call_is_a_new_snapshot(self) -> None:
        first = resource.getrusage(resource.RUSAGE_SELF)
        second = resource.getrusage(resource.RUSAGE_SELF)

        assert first is not second
        assert isinstance(first, resource.struct_rusage)

    def test_items_and_attributes_are_the_same_sixteen_fields(self) -> None:
        usage = resource.getrusage(resource.RUSAGE_SELF)

        assert isinstance(usage, tuple)
        assert len(usage) == len(FIELDS) == 16
        for index, name in enumerate(FIELDS):
            assert usage[index] == getattr(usage, name), name

    def test_the_times_are_floats_and_the_rest_ints(self) -> None:
        usage = resource.getrusage(resource.RUSAGE_SELF)

        assert isinstance(usage.ru_utime, float) and isinstance(usage.ru_stime, float)
        for name in FIELDS[2:]:
            assert type(getattr(usage, name)) is int, name

    @pytest.mark.skipif(
        sys.platform != "linux", reason="platform: Linux's getrusage leaves these fields unset"
    )
    def test_linux_reports_seven_fields_as_zero(self) -> None:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        unset = ("ru_ixrss", "ru_idrss", "ru_isrss", "ru_nswap", "ru_msgsnd")
        unset += ("ru_msgrcv", "ru_nsignals")

        assert {name: getattr(usage, name) for name in unset} == dict.fromkeys(unset, 0)


def _vmhwm_kb() -> int:
    status = pathlib.Path("/proc/self/status").read_text(encoding="ascii")
    match = re.search(r"^VmHWM:\s+(\d+) kB$", status, re.MULTILINE)
    assert match is not None, "no VmHWM line in /proc/self/status"
    return int(match.group(1))


@UNIX_ONLY
class TestMaxrss:
    """`struct_rusage.ru_maxrss` | a peak that never falls, in kilobytes on Linux and
    bytes on macOS.

    The unit is told apart by a factor of 1,024 against an independent reading
    of the same peak (Linux) or against any plausible process size (macOS).
    """

    @pytest.mark.skipif(sys.platform != "linux", reason="platform: VmHWM is Linux's /proc")
    def test_linux_reports_kilobytes(self) -> None:
        peak_kb = _vmhwm_kb()
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        assert peak_kb / 2 < maxrss < peak_kb * 2, (
            f"ru_maxrss {maxrss} against VmHWM {peak_kb} kB; bytes would be 1,024x VmHWM"
        )

    @pytest.mark.skipif(sys.platform != "darwin", reason="platform: macOS reports bytes")
    def test_macos_reports_bytes(self) -> None:
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        assert maxrss > 4_000_000, f"ru_maxrss {maxrss}; in bytes a test process exceeds 4 MB"

    def test_it_does_not_fall_when_memory_is_freed(self) -> None:
        buffer = bytearray(64 * 1024 * 1024)
        buffer[::4096] = b"x" * len(range(0, len(buffer), 4096))
        during = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        del buffer
        gc.collect()

        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= during


@UNIX_ONLY
@pytest.mark.skipif(
    sys.platform == "darwin" and sys.version_info < (3, 13),
    reason="version: os.waitid reaches macOS in Python 3.13",
)
class TestChildrenAreCountedOnceWaitedFor:
    """`getrusage(RUSAGE_CHILDREN)` | child processes that have exited and been waited for.

    The child is held as an unreaped zombie with `waitid(WNOWAIT)`, which
    separates "exited" from "waited for".
    """

    def test_an_unreaped_child_is_not_counted(self) -> None:
        def total() -> float:
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            return usage.ru_utime + usage.ru_stime

        before = total()
        child = subprocess.Popen([sys.executable, "-c", "sum(range(10**6))"])
        try:
            os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)
            unreaped = total()
        finally:
            returncode = child.wait()

        assert unreaped == before, "an exited, unreaped child was counted"
        assert returncode == 0
        assert total() > before, "a reaped child's CPU time was not counted"


def _may_raise_hard_limits() -> bool:
    """CAP_SYS_RESOURCE in the effective set on Linux; the superuser elsewhere."""
    if sys.platform == "linux":
        status = pathlib.Path("/proc/self/status").read_text(encoding="ascii")
        match = re.search(r"^CapEff:\s+([0-9a-f]+)$", status, re.MULTILINE)
        assert match is not None, "no CapEff line in /proc/self/status"
        return bool(int(match.group(1), 16) >> 24 & 1)
    return os.geteuid() == 0


@UNIX_ONLY
class TestLimits:
    """`getrlimit()`, `setrlimit()` | O(1); the soft limit moves freely below the hard one.

    Each check reads the limits back, so a cached value would show up as a
    stale read.
    """

    @pytest.fixture
    def fsize(self) -> Iterator[tuple[int, int]]:
        original = resource.getrlimit(resource.RLIMIT_FSIZE)
        try:
            yield original
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, original)

    def test_a_lowered_soft_limit_reads_back_and_can_be_raised_again(
        self, fsize: tuple[int, int]
    ) -> None:
        soft, hard = fsize

        resource.setrlimit(resource.RLIMIT_FSIZE, (1024, hard))
        assert resource.getrlimit(resource.RLIMIT_FSIZE) == (1024, hard)

        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
        assert resource.getrlimit(resource.RLIMIT_FSIZE) == (soft, hard)

    def test_a_soft_limit_above_the_hard_one_is_a_value_error(self, fsize: tuple[int, int]) -> None:
        with pytest.raises(ValueError, match="exceeds maximum"):
            resource.setrlimit(resource.RLIMIT_FSIZE, (2, 1))
        assert resource.getrlimit(resource.RLIMIT_FSIZE) == fsize

    def test_python_ignores_sigxfsz_so_a_write_past_the_limit_raises_efbig(self) -> None:
        script = textwrap.dedent(
            """
            import errno, resource, signal, sys, tempfile
            if sys.argv[1] == "restore":
                signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
            hard = resource.getrlimit(resource.RLIMIT_FSIZE)[1]
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024, hard))
            with tempfile.TemporaryFile(buffering=0) as handle:
                handle.write(b"x" * 1024)
                try:
                    handle.write(b"x")
                except OSError as error:
                    print(errno.errorcode[error.errno])
            """
        )

        def run(mode: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-c", script, mode], capture_output=True, text=True, check=False
            )

        python, restored = run("python"), run("restore")
        assert (python.returncode, python.stdout.strip()) == (0, "EFBIG"), python
        assert restored.returncode == -signal.SIGXFSZ, restored

    def test_an_unknown_resource_is_a_value_error(self) -> None:
        with pytest.raises(ValueError, match="invalid resource"):
            resource.getrlimit(-1)

    def test_raising_the_hard_limit_needs_privilege(self) -> None:
        script = textwrap.dedent(
            """
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
            lowered = 1024 if hard == resource.RLIM_INFINITY else hard // 2
            resource.setrlimit(resource.RLIMIT_FSIZE, (lowered, lowered))
            try:
                resource.setrlimit(resource.RLIMIT_FSIZE, (lowered, hard))
            except ValueError as error:
                print("refused:", error)
            else:
                print("raised")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )

        if _may_raise_hard_limits():
            assert result.stdout.strip() == "raised"
        else:
            assert result.stdout.strip() == "refused: not allowed to raise maximum limit"


@UNIX_ONLY
class TestPlatformNames:
    """`prlimit()`, `RUSAGE_THREAD` and the `RLIMIT_*` names exist where the
    platform defines them; `resource.error` is `OSError`."""

    @pytest.mark.skipif(sys.platform != "linux", reason="platform: prlimit(2) is Linux's")
    def test_linux_has_prlimit_and_pid_zero_is_the_caller(self) -> None:
        assert resource.prlimit(0, resource.RLIMIT_NOFILE) == resource.getrlimit(
            resource.RLIMIT_NOFILE
        )
        assert isinstance(resource.RUSAGE_THREAD, int)
        assert not hasattr(resource, "RLIMIT_KQUEUES")

    @pytest.mark.skipif(sys.platform != "darwin", reason="platform: macOS has no prlimit(2)")
    def test_macos_has_neither_prlimit_nor_rusage_thread(self) -> None:
        assert not hasattr(resource, "prlimit")
        assert not hasattr(resource, "RUSAGE_THREAD")

    def test_error_is_oserror(self) -> None:
        assert resource.error is OSError

    def test_page_size_is_the_system_page_size(self) -> None:
        assert resource.getpagesize() == os.sysconf("SC_PAGE_SIZE")


@pytest.mark.skipif(sys.platform != "win32", reason="platform: the absence is Windows'")
def test_windows_has_no_resource_module() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("resource")


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


@UNIX_ONLY
class TestDocumentedExamples:
    """Each block runs in its own subprocess, so a limit it changes cannot leak
    into the test process, and asserts its own result. The `prlimit()` block
    needs Linux and is skipped where the function does not exist."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "resource.prlimit(" in source and not hasattr(resource, "prlimit"):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        expected = EXPECTED_BLOCKS if hasattr(resource, "prlimit") else EXPECTED_BLOCKS - 1
        assert ran == expected
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "len(after) == 16" in s)
        mutated = source.replace("len(after) == 16", "len(after) == 17", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
