"""Tests for docs/stdlib/time.md.

Almost every row on the page is constant by construction: a clock read is one
C library call, and a `struct_time` has a fixed shape whatever the timestamp.
There is no size to vary, so those rows are settled by observation - return
types, field counts, monotonicity, which clocks advance while a thread sleeps.
Only `strftime()` and `strptime()` take an input that grows, and those are
settled by timing at three sizes spanning two orders of magnitude, with the
format cache observed directly in the private `_strptime` module.

Measurement scope:

* `strftime()` is timed on formats of 1,000, 10,000 and 100,000 repetitions
  of `%Y`, which produce four characters each: every 10x step costs more than
  4x and less than 40x, which excludes both a constant and a quadratic. Output
  length is asserted to be four times the repetitions, and bounded by a
  constant multiple of the format - at most 15 characters per format
  character - for `%c`, `%Y`, `%%` and literal text, in the C locale.
* `strptime()` is timed on inputs of 10,000, 100,000 and 1,000,000 literal
  characters plus a year, with the format already cached: every 10x step
  costs more than 4x and less than 40x. The O(f) compile is separated from the
  O(n) match by padding the format with whitespace, which compiles to one
  `\\s+` and so leaves the input fixed at seven characters: from 100 to
  100,000 format characters a cached call stays within 3x, and a call after
  clearing the cache grows more than 20x.
* The cache is observed in `_strptime._regex_cache`. A reused format is the
  same compiled object after 50 calls; the seventh distinct format leaves one
  entry rather than six, so the cache is emptied rather than evicted; seven
  formats used in rotation for 70 calls find their format missing on every
  call; and `datetime.datetime.strptime()` fills the same dictionary.
* The 3.13 `DeprecationWarning` for `%m-%d` without a year is asserted
  present on 3.13+ and absent before it, guarded on `sys.version_info`.
* `sleep()` is asserted to block for at least the requested 0.05 s, and to
  use under 10 ms of `process_time()` for sleeps of 0.05 s and 0.2 s.
  `perf_counter()` advances by at least the sleep. While a second thread
  spins until its own `thread_time()` reaches 0.2 s, the thread waiting on it
  is charged under 50 ms of `thread_time()` and `process_time()` advances by
  at least 0.2 s, so the first counts only its own thread and the second the
  whole process.
* `time_ns()` keeping precision is asserted through `math.ulp(time.time())`
  exceeding one nanosecond, which holds for any timestamp after 1970-04.
  `monotonic()` is asserted non-decreasing over 1,000 reads and reported
  monotonic and not adjustable by `get_clock_info()`.
* `struct_time` is asserted to have nine indexable items for timestamps 0,
  1e9 and 2e9, eleven named fields, `tm_zone` and `tm_gmtoff` outside the
  tuple, and to accept nine to eleven items and reject eight and twelve.
  `asctime()` and `ctime()` are 24 characters across four-digit years, 21 for
  year 1 and 25 for year 10,000.
* On Linux, every Unix-only name the page lists is asserted present, and
  every `CLOCK_*` id present is read through `clock_gettime()`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one is asserted to fail. The POSIX clock block is
  also run with every `clock_*` and `CLOCK_*` name deleted, as on a platform
  without them.

Not settled here:

* `clock_settime()` and `clock_settime_ns()` need privileges and would move
  the clock for every process on the machine; their row follows the POSIX
  contract. For the same reason nothing sets the system clock, so the claims
  that `time()` can go backwards and that `monotonic()` does not follow a
  clock change rest on the official documentation.
* Clock resolution and `sleep()`'s oversleep belong to the platform and its
  scheduler; the tests assert only the documented floor of `sleep()`.
* `tzset()`, `localtime()` and `mktime()` consult the C library's timezone
  rules, whose cost is libc's and is priced O(1) by the page's cost model.
* Windows lacks every name the page marks Unix only. That is guarded on
  `sys.platform == "win32"` and never runs here. `CLOCK_HIGHRES` (Solaris),
  `CLOCK_PROF` and `CLOCK_UPTIME` (BSD), and `CLOCK_UPTIME_RAW` and the two
  `_APPROX` ids (macOS) do not exist on Linux; their rows are read from the
  official documentation. `thread_time()` is likewise only checked where it
  exists.
* `struct_time.n_fields`, `n_sequence_fields` and `n_unnamed_fields` are
  runtime attributes absent from the official documentation, so the page does
  not list them.

Axes not varied: non-C locales for `strftime()` and `strptime()`, formats
with non-ASCII text, directives whose output is empty, timestamps before the
epoch, and any interpreter but the pinned one except for the version-gated
warning.
"""

from __future__ import annotations

import _strptime
import datetime
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import types
import warnings
from collections.abc import Callable, Iterator
from typing import Any, Literal

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "time.md"
EXPECTED_BLOCKS = 9

UNIX_ONLY = (
    "clock_gettime",
    "clock_gettime_ns",
    "clock_getres",
    "clock_settime",
    "clock_settime_ns",
    "pthread_getcpuclockid",
    "tzset",
)
CLOCK_IDS = (
    "CLOCK_REALTIME",
    "CLOCK_MONOTONIC",
    "CLOCK_MONOTONIC_RAW",
    "CLOCK_BOOTTIME",
    "CLOCK_PROCESS_CPUTIME_ID",
    "CLOCK_THREAD_CPUTIME_ID",
    "CLOCK_TAI",
    "CLOCK_HIGHRES",
    "CLOCK_PROF",
    "CLOCK_UPTIME",
    "CLOCK_UPTIME_RAW",
    "CLOCK_MONOTONIC_RAW_APPROX",
    "CLOCK_UPTIME_RAW_APPROX",
)

ClockName = Literal["time", "monotonic", "perf_counter", "process_time", "thread_time"]
NAMED_CLOCKS: tuple[ClockName, ...] = (
    "time",
    "monotonic",
    "perf_counter",
    "process_time",
    "thread_time",
)


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


def require(*names: str) -> None:
    """Skip when the running platform lacks one of these names."""
    missing = [name for name in names if not hasattr(time, name)]
    if missing:
        pytest.skip(f"unavailable here: {', '.join(missing)}")


def table_rows() -> list[str]:
    return [line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")]


def row_naming(name: str) -> str:
    """The one table row whose Operation cell names `name`."""
    owning = [row for row in table_rows() if name in re.findall(r"time\.(\w+)", row.split("|")[1])]
    assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
    return owning[0]


class TestPlatformRows:
    """Rows for names a supported platform lacks say so in their Notes."""

    @pytest.mark.parametrize("name", UNIX_ONLY)
    def test_each_unix_only_row_says_so(self, name: str) -> None:
        assert "Unix only" in row_naming(name)

    @pytest.mark.parametrize("name", (*CLOCK_IDS, "thread_time", "thread_time_ns"))
    def test_each_optional_row_says_it_is_platform_dependent(self, name: str) -> None:
        assert "platform-dependent" in row_naming(name)

    @pytest.mark.parametrize("name", ("CLOCK_MONOTONIC_RAW_APPROX", "CLOCK_UPTIME_RAW_APPROX"))
    def test_the_approx_ids_are_marked_313(self, name: str) -> None:
        assert "Python 3.13+" in row_naming(name)
        if sys.version_info < (3, 13):
            assert not hasattr(time, name)

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux check")
    def test_linux_has_every_unix_only_name(self) -> None:
        assert [name for name in UNIX_ONLY if not hasattr(time, name)] == []

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only absence")
    def test_windows_has_none_of_them(self) -> None:
        assert [name for name in UNIX_ONLY if hasattr(time, name)] == []


class TestClocks:
    """The clock rows: O(1) reads, each with a float and an int form."""

    @pytest.mark.parametrize("name", NAMED_CLOCKS)
    def test_each_clock_has_a_float_and_an_int_form(self, name: ClockName) -> None:
        require(name, f"{name}_ns")

        assert isinstance(getattr(time, name)(), float)
        assert isinstance(getattr(time, f"{name}_ns")(), int)

    @pytest.mark.parametrize("name", NAMED_CLOCKS)
    def test_get_clock_info_describes_each_of_them(self, name: ClockName) -> None:
        require(name)
        info = time.get_clock_info(name)

        assert isinstance(info, types.SimpleNamespace)
        assert set(vars(info)) == {"implementation", "monotonic", "adjustable", "resolution"}

    def test_a_float_timestamp_cannot_hold_nanoseconds(self) -> None:
        """Why `time_ns()` exists: the float's spacing near now exceeds 1 ns."""
        assert math.ulp(time.time()) > 1e-9

    def test_monotonic_never_goes_backwards(self) -> None:
        readings = [time.monotonic() for _ in range(1000)]

        assert readings == sorted(readings)
        info = time.get_clock_info("monotonic")
        assert info.monotonic is True
        assert info.adjustable is False

    def test_perf_counter_counts_time_spent_sleeping(self) -> None:
        before = time.perf_counter()
        time.sleep(0.05)

        assert time.perf_counter() - before >= 0.05


class TestCpuClocks:
    """`process_time()` counts the whole process, `thread_time()` only the
    calling thread, and neither counts a sleep. A spinning second thread
    separates the two: it adds to the process and not to the sleeper."""

    @pytest.mark.timing
    def test_thread_time_ignores_other_threads_process_time_does_not(self) -> None:
        """The worker spins until its own `thread_time()` reaches 0.2 s, so
        the CPU it adds does not depend on how loaded the machine is."""
        require("thread_time")

        def spin() -> None:
            start = time.thread_time()
            while time.thread_time() - start < 0.2:
                pass

        worker = threading.Thread(target=spin)
        process_before = time.process_time()
        thread_before = time.thread_time()
        worker.start()
        time.sleep(0.05)
        worker.join()
        thread_spent = time.thread_time() - thread_before
        process_spent = time.process_time() - process_before

        assert thread_spent < 0.05, f"the waiting thread was charged {thread_spent:.3f}s"
        assert process_spent >= 0.2, f"the process was charged only {process_spent:.3f}s"


class TestSleepBlocksWithoutWorking:
    """`time.sleep(secs)`: blocks for at least secs, and the wait costs no CPU
    time, whatever secs is."""

    def test_it_blocks_for_at_least_the_requested_time(self) -> None:
        start = time.monotonic()
        time.sleep(0.05)

        assert time.monotonic() - start >= 0.05

    def test_the_wait_costs_no_cpu_time(self) -> None:
        spent: list[float] = []
        for secs in (0.05, 0.2):
            before = time.process_time()
            time.sleep(secs)
            spent.append(time.process_time() - before)

        assert all(cpu < 0.01 for cpu in spent), f"sleep consumed CPU: {spent}"


class TestPosixClocks:
    """The POSIX clock rows, on the platforms that have them."""

    def test_seconds_and_nanoseconds_read_the_same_clock(self) -> None:
        require("clock_gettime", "clock_gettime_ns", "CLOCK_MONOTONIC")
        before = time.clock_gettime(time.CLOCK_MONOTONIC)
        middle = time.clock_gettime_ns(time.CLOCK_MONOTONIC) / 1_000_000_000
        after = time.clock_gettime(time.CLOCK_MONOTONIC)

        assert before <= middle <= after

    def test_clock_getres_reports_a_resolution(self) -> None:
        require("clock_getres", "CLOCK_MONOTONIC")

        assert 0 < time.clock_getres(time.CLOCK_MONOTONIC) <= 1

    def test_every_clock_id_present_can_be_read(self) -> None:
        require("clock_gettime")
        present = [name for name in CLOCK_IDS if hasattr(time, name)]

        assert present, "no documented CLOCK_* id exists here"
        for name in present:
            clock_id = getattr(time, name)
            assert isinstance(clock_id, int)
            assert time.clock_gettime(clock_id) >= 0

    def test_pthread_getcpuclockid_returns_a_readable_clock(self) -> None:
        require("pthread_getcpuclockid", "clock_gettime")
        clock_id = time.pthread_getcpuclockid(threading.get_ident())

        assert isinstance(clock_id, int)
        assert time.clock_gettime(clock_id) >= 0


class TestStructTime:
    """`struct_time`: nine indexable fields plus `tm_zone` and `tm_gmtoff`,
    whatever the timestamp."""

    NINE = (
        "tm_year",
        "tm_mon",
        "tm_mday",
        "tm_hour",
        "tm_min",
        "tm_sec",
        "tm_wday",
        "tm_yday",
        "tm_isdst",
    )

    def test_nine_items_for_any_timestamp(self) -> None:
        assert {len(time.gmtime(stamp)) for stamp in (0, 10**9, 2 * 10**9)} == {9}

    def test_index_and_attribute_reach_the_same_nine_fields(self) -> None:
        parsed = time.localtime(10**9)

        assert tuple(getattr(parsed, name) for name in self.NINE) == tuple(parsed)

    def test_zone_and_offset_are_attributes_only(self) -> None:
        utc = time.gmtime(0)

        assert isinstance(utc.tm_zone, str)
        assert utc.tm_gmtoff == 0
        assert utc.tm_zone not in tuple(utc)
        assert len(utc) == time.struct_time.n_sequence_fields == 9
        assert time.struct_time.n_fields == 11

    def test_the_constructor_takes_nine_to_eleven_items(self) -> None:
        nine = tuple(time.gmtime(0))

        assert time.struct_time(nine).tm_zone is None
        assert time.struct_time((*nine, "X")).tm_zone == "X"
        assert time.struct_time((*nine, "X", 60)).tm_gmtoff == 60
        for bad in (nine[:8], (*nine, "X", 60, 0)):
            with pytest.raises(TypeError):
                time.struct_time(bad)

    def test_mktime_inverts_localtime(self) -> None:
        assert time.mktime(time.localtime(1_000_000_000)) == 1_000_000_000


class TestFixedWidthFormatting:
    """`asctime`/`ctime`: 24 characters for any four-digit year."""

    def test_twenty_four_characters_across_four_digit_years(self) -> None:
        stamps = (0, 10**9, 2 * 10**9, 1_234_567_890)

        assert {len(time.asctime(time.gmtime(stamp))) for stamp in stamps} == {24}
        assert {len(time.ctime(stamp)) for stamp in stamps} == {24}

    def test_the_year_field_is_the_part_that_is_not_fixed(self) -> None:
        widths = {}
        for year in (1, 1970, 9999, 10000):
            fields = (year, 1, 1, 0, 0, 0, 0, 1, 0)
            widths[year] = len(time.asctime(time.struct_time(fields)))

        assert widths == {1: 21, 1970: 24, 9999: 24, 10000: 25}


class TestStrftimeFollowsItsFormat:
    """`time.strftime(format[, t])` | O(f) | O(f): each directive expands to a
    bounded number of characters, so the output follows the format."""

    MOMENT = time.gmtime(0)

    @pytest.mark.parametrize("unit", ("x", "%Y", "%%", "%c"))
    def test_the_output_is_bounded_by_the_format(self, unit: str) -> None:
        small, large = unit * 10, unit * 1000
        small_out = time.strftime(small, self.MOMENT)
        large_out = time.strftime(large, self.MOMENT)

        assert len(large_out) == 100 * len(small_out)
        assert len(large_out) <= 15 * len(large)

    @pytest.mark.timing
    def test_each_tenfold_format_costs_linearly_more(self) -> None:
        times = []
        for reps in (1_000, 10_000, 100_000):
            fmt = "%Y" * reps
            assert len(time.strftime(fmt, self.MOMENT)) == 4 * reps
            times.append(best_ns(lambda fmt=fmt: time.strftime(fmt, self.MOMENT), inner=3))

        ratios = [large / small for small, large in zip(times, times[1:], strict=False)]
        assert all(4 < ratio < 40 for ratio in ratios), (
            f"10x steps cost {[f'x{r:.1f}' for r in ratios]}; "
            "linear gives about x10, constant x1, quadratic x100"
        )


class TestStrptimeFollowsItsInput:
    """`time.strptime(string[, format])` | O(n) | O(n), with the O(f) compile
    paid once per format."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Iterator[None]:
        _strptime._regex_cache.clear()
        yield
        _strptime._regex_cache.clear()

    def test_the_padding_is_parsed_rather_than_skipped(self) -> None:
        fmt = "z" * 100 + "%Y"

        assert time.strptime("z" * 100 + "2026", fmt).tm_year == 2026
        with pytest.raises(ValueError, match="does not match format"):
            time.strptime("y" * 100 + "2026", fmt)

    @pytest.mark.timing
    def test_each_tenfold_input_costs_linearly_more(self) -> None:
        times = []
        for size in (10_000, 100_000, 1_000_000):
            value, fmt = "z" * size + "2026", "z" * size + "%Y"
            time.strptime(value, fmt)  # compile outside the measurement
            times.append(best_ns(lambda v=value, f=fmt: time.strptime(v, f), inner=3))

        ratios = [large / small for small, large in zip(times, times[1:], strict=False)]
        assert all(4 < ratio < 40 for ratio in ratios), (
            f"10x steps cost {[f'x{r:.1f}' for r in ratios]}; "
            "linear gives about x10, constant x1, quadratic x100"
        )

    @pytest.mark.timing
    def test_the_format_is_paid_for_on_a_miss_and_not_on_a_hit(self) -> None:
        """Whitespace in a format compiles to one `\\s+`, so the input stays
        seven characters while the format grows a thousandfold."""
        value = "2026 01"
        hits: list[float] = []
        misses: list[float] = []
        for pad in (100, 100_000):
            fmt = "%Y" + " " * pad + "%m"
            assert time.strptime(value, fmt).tm_mon == 1

            def miss(fmt: str = fmt) -> None:
                _strptime._regex_cache.clear()
                time.strptime(value, fmt)

            hits.append(best_ns(lambda fmt=fmt: time.strptime(value, fmt), inner=20))
            misses.append(best_ns(miss, inner=3))

        assert hits[1] < hits[0] * 3, f"a cached call grew with the format: {hits}"
        assert misses[1] > misses[0] * 20, f"a miss did not follow the format: {misses}"


class TestStrptimeCache:
    """The format is compiled once and cached; the cache is small and is
    emptied all at once when full. Observed in the private `_strptime`
    module, the only place the cache is visible."""

    FORMATS = (
        ("2026-01-30", "%Y-%m-%d"),
        ("30/01/2026", "%d/%m/%Y"),
        ("20260130", "%Y%m%d"),
        ("01-30-2026", "%m-%d-%Y"),
        ("30.01.2026", "%d.%m.%Y"),
        ("2026_01_30", "%Y_%m_%d"),
        ("30~01~2026", "%d~%m~%Y"),
    )

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Iterator[None]:
        _strptime._regex_cache.clear()
        yield
        _strptime._regex_cache.clear()

    def test_reusing_a_format_compiles_nothing_new(self) -> None:
        value, fmt = self.FORMATS[0]
        time.strptime(value, fmt)
        compiled = _strptime._regex_cache[fmt]

        for _ in range(50):
            time.strptime(value, fmt)

        assert _strptime._regex_cache[fmt] is compiled
        assert len(_strptime._regex_cache) == 1

    def test_a_full_cache_is_emptied_rather_than_evicting_one(self) -> None:
        sizes = []
        for value, fmt in self.FORMATS:
            time.strptime(value, fmt)
            sizes.append(len(_strptime._regex_cache))

        assert sizes == [1, 2, 3, 4, 5, 6, 1], f"cache sizes after each format: {sizes}"

    def test_rotating_past_the_cache_misses_on_every_call(self) -> None:
        misses = 0
        for _ in range(10):
            for value, fmt in self.FORMATS:
                misses += fmt not in _strptime._regex_cache
                time.strptime(value, fmt)

        assert misses == 70

    def test_datetime_strptime_shares_the_cache(self) -> None:
        value, fmt = self.FORMATS[0]

        datetime.datetime.strptime(value, fmt)

        assert fmt in _strptime._regex_cache

    def test_a_day_without_a_year_warns_from_313(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            time.strptime("01-30", "%m-%d")

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecations) == (1 if sys.version_info >= (3, 13) else 0)


class TestTimezoneAttributes:
    """`timezone`/`altzone`/`daylight`/`tzname`: module attributes, and
    `tzset()` leaves them readable."""

    def test_the_offsets_are_whole_seconds(self) -> None:
        assert isinstance(time.timezone, int)
        assert isinstance(time.altzone, int)
        assert isinstance(time.daylight, int)

    def test_tzname_names_the_two_zones(self) -> None:
        assert isinstance(time.tzname, tuple)
        assert len(time.tzname) == 2
        assert all(isinstance(name, str) for name in time.tzname)

    def test_tzset_refreshes_the_attributes(self) -> None:
        require("tzset")
        time.tzset()

        assert isinstance(time.timezone, int)
        assert len(time.tzname) == 2


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "hours == [8, 9, 17]" in s)
        mutated = source.replace("hours == [8, 9, 17]", "hours == [8, 9, 18]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0

    def test_the_posix_block_runs_without_posix_clocks(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "clock_gettime_ns" in s)
        prelude = (
            "import time\n"
            "for name in list(vars(time)):\n"
            "    if name.startswith(('clock_', 'CLOCK_')):\n"
            "        delattr(time, name)\n"
            "assert not hasattr(time, 'clock_gettime')\n"
        )

        result = _run_block(prelude + source, tmp_path)

        assert result.returncode == 0, f"{PAGE.name}:{line}\n{result.stderr}"
