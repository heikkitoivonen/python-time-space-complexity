"""Tests to verify documented behaviour of the time module.

Most of docs/stdlib/time.md is constant by construction: a clock read is one
syscall, and a `struct_time` carries nine fields whatever the timestamp. There
is no size to vary, so those rows are pinned by observation - the return types,
the field count, the monotonicity - rather than by a stopwatch.

Two rows have an input that grows, and both are linear in it:

* `strftime()` follows its output. A format of 1,000 literal characters against
  one of 10,000 costs x13.8 on 3.10 and x13.0 on 3.14, where a constant-time
  operation would give x1. The slight overshoot is the output buffer being
  resized and the call retried.
* `strptime()` follows its input, once its format is cached: 10,000 characters
  against 100,000 costs x9.1 on 3.10 and x8.3 on 3.14.

`strptime()` compiles the format to a regular expression and caches it in the
private `_strptime` module, which is the only place the cache can be observed.
The cache holds six formats and the seventh call to find it over the limit
clears it entirely rather than evicting one entry - identical on 3.10, 3.11 and
3.14. A call that misses the cache costs x2.27 to x2.44 a call that hits it.

Three fixed-width claims are checked at their edges rather than at one
timestamp. `asctime()` is 24 characters only for a four-digit year: year 1 is
21 characters and year 10,000 is 25, so the row says four-digit rather than
always.

Not settled here:

* `clock_settime()` and `clock_settime_ns()` need privileges and would move the
  system clock for every process on the machine. Their row is read from the
  CPython source and the POSIX contract, not exercised.
* `sleep()`'s actual latency belongs to the scheduler. The tests assert the
  documented floor - it blocks for *at least* the requested time - and that the
  waiting costs no CPU, which is the part `time` controls.
* `tzset()` re-reads the platform's timezone database. What that costs is
  libc's, not Python's.
* Clock availability follows the platform and Python version, as listed in
  https://docs.python.org/3.14/library/time.html#clock-id-constants.
  Coverage permits only explicitly listed optional names; execution checks
  exercise the clocks available on the running interpreter.

Axes not varied: non-C locales for `strftime`/`strptime` output, non-Linux
platforms, the resolution of any clock beyond what `get_clock_info()` reports,
and timestamps before the epoch - the Windows CRT rejects those in
`gmtime`/`localtime`/`ctime`, so the fixed-width tests stay at or after it and
reach the pre-1000 and post-9999 years through `struct_time` instead.
"""

import _strptime
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import types
from collections.abc import Callable
from typing import Any, Literal

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "time.md"

EXPECTED_BLOCKS = 5

# Documented, but absent outside Unix. Each has to say so in its own row.
UNIX_ONLY = {
    "clock_gettime",
    "clock_gettime_ns",
    "clock_getres",
    "clock_settime",
    "clock_settime_ns",
    "pthread_getcpuclockid",
    "tzset",
}
CLOCK_IDS = {
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
}
OPTIONAL_NAMES = UNIX_ONLY | CLOCK_IDS | {"thread_time", "thread_time_ns"}


def require_clock(*names: str) -> None:
    """Skip execution only when a required clock API is unavailable."""
    missing = [name for name in names if not hasattr(time, name)]
    if missing:
        pytest.skip(f"clock APIs unavailable: {', '.join(missing)}")


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


def _documented_names() -> set[str]:
    """Every `time.<name>` the Complexity Reference table mentions."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n## ", start)
    return set(re.findall(r"time\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `time`.

    A page is lint-clean and green whether it covers its module or a third of
    it, and no reader of the page can tell. The interpreter running the suite
    decides what `time` contains.
    """

    def test_no_public_name_is_missing_from_the_table(self) -> None:
        public = {name for name in dir(time) if not name.startswith("_")}

        missing = sorted(public - _documented_names())

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        public = {name for name in dir(time) if not name.startswith("_")}

        unknown = sorted(_documented_names() - public - OPTIONAL_NAMES)

        assert not unknown, f"the table names attributes time does not have: {unknown}"

    def test_the_platform_specific_rows_say_so(self) -> None:
        """A row for something a supported platform lacks has to warn."""
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if "| O(1) |" in line
        ]

        for name in sorted(UNIX_ONLY):
            owning = [row for row in rows if f"time.{name}(" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert "Unix only" in owning[0], f"the {name} row should say Unix only: {owning[0]}"

    def test_optional_clock_rows_have_availability_notes(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]
        for name in sorted(CLOCK_IDS | {"thread_time", "thread_time_ns"}):
            owning = [row for row in rows if name in set(re.findall(r"time\.(\w+)", row))]
            assert len(owning) == 1
            assert "platform-dependent" in owning[0]
            if name.endswith("_APPROX"):
                assert "Python 3.13+" in owning[0]

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()
        public = {name for name in dir(time) if not name.startswith("_")}

        assert {"time", "sleep", "strptime", "tzname", "CLOCK_MONOTONIC"} <= documented, (
            "the extractor missed rows that are certainly on the page"
        )
        assert public - (documented - {"monotonic"}) == {"monotonic"}, (
            "dropping one row from the extracted set should surface it as missing"
        )

    @pytest.mark.parametrize("with_posix_clocks", [False, True])
    def test_coverage_accepts_optional_api_sets(
        self, monkeypatch: pytest.MonkeyPatch, with_posix_clocks: bool
    ) -> None:
        """Exercise absent Unix APIs and optional clock ids without a host dependency."""
        for name in OPTIONAL_NAMES:
            monkeypatch.delattr(time, name, raising=False)
        if with_posix_clocks:
            for name in CLOCK_IDS:
                monkeypatch.setattr(time, name, 1, raising=False)

        self.test_no_public_name_is_missing_from_the_table()
        self.test_the_table_names_nothing_that_does_not_exist()
        self.test_the_coverage_check_would_notice_a_gap()

        monkeypatch.setattr(time, "CLOCK_UNDOCUMENTED", 1, raising=False)
        with pytest.raises(AssertionError, match="CLOCK_UNDOCUMENTED"):
            self.test_no_public_name_is_missing_from_the_table()


class TestTheClockReadersAreConstant:
    """The clock rows: one read each, and no input whose size could vary."""

    @pytest.mark.parametrize("name", NAMED_CLOCKS)
    def test_each_clock_has_a_float_and_an_int_form(self, name: ClockName) -> None:
        require_clock(name, f"{name}_ns")
        seconds = getattr(time, name)()
        nanoseconds = getattr(time, f"{name}_ns")()

        assert isinstance(seconds, float)
        assert isinstance(nanoseconds, int)

    @pytest.mark.parametrize("name", NAMED_CLOCKS)
    def test_get_clock_info_describes_each_of_them(self, name: ClockName) -> None:
        require_clock(name)
        info = time.get_clock_info(name)

        assert isinstance(info, types.SimpleNamespace)
        assert {"implementation", "monotonic", "adjustable", "resolution"} <= set(vars(info))

    def test_monotonic_never_goes_backwards(self) -> None:
        readings = [time.monotonic() for _ in range(1000)]

        assert readings == sorted(readings)
        assert time.get_clock_info("monotonic").monotonic is True

    def test_a_named_reader_that_wraps_a_posix_clock_names_which_one(self) -> None:
        """The page's wrapper claim, read off CPython's own description.

        Portable in the shape it asserts rather than in the ids it expects:
        whichever readers report a `clock_gettime(...)` implementation must
        name an id the table documents, and that id must be readable. On this
        suite's Linux all five report one; macOS reaches some of these clocks
        by another route, which is why the set is not fixed.
        """
        require_clock("clock_gettime")

        wrappers: dict[str, str] = {}
        for name in NAMED_CLOCKS:
            if not hasattr(time, name):
                continue
            match = re.fullmatch(
                r"clock_gettime\((CLOCK_\w+)\)", time.get_clock_info(name).implementation
            )
            if match:
                wrappers[name] = match.group(1)

        assert wrappers, "no named reader reported a clock_gettime implementation"
        for name, clock_id in wrappers.items():
            assert clock_id in CLOCK_IDS, f"{name} names {clock_id}, absent from the table"
            assert time.clock_gettime(getattr(time, clock_id)) >= 0

    def test_posix_seconds_and_nanoseconds_read_the_same_clock(self) -> None:
        require_clock("clock_gettime", "clock_gettime_ns", "CLOCK_MONOTONIC")
        before = time.clock_gettime(time.CLOCK_MONOTONIC)
        middle = time.clock_gettime_ns(time.CLOCK_MONOTONIC) / 1_000_000_000
        after = time.clock_gettime(time.CLOCK_MONOTONIC)

        assert before <= middle <= after

    def test_clock_getres_reports_a_tick_not_a_call_cost(self) -> None:
        require_clock("clock_getres", "CLOCK_MONOTONIC")
        resolution = time.clock_getres(time.CLOCK_MONOTONIC)

        assert isinstance(resolution, float)
        assert 0 < resolution <= 1

    def test_every_documented_clock_id_can_be_read(self) -> None:
        require_clock("clock_gettime")
        ids = sorted(CLOCK_IDS & set(dir(time)))

        for name in ids:
            clock_id = getattr(time, name)
            assert isinstance(clock_id, int)
            assert time.clock_gettime(clock_id) >= 0


class TestSleepBlocksWithoutWorking:
    """`time.sleep(secs)`: blocks for at least secs, and the waiting is not
    CPU work, so the call costs the same whatever secs is."""

    def test_it_blocks_for_at_least_the_requested_time(self) -> None:
        start = time.monotonic()
        time.sleep(0.05)

        assert time.monotonic() - start >= 0.05

    def test_the_waiting_costs_no_cpu_time(self) -> None:
        spent: list[float] = []
        for secs in (0.05, 0.2):
            before = time.process_time()
            time.sleep(secs)
            spent.append(time.process_time() - before)

        # A 4x longer sleep is 4x the wall clock and neither is CPU work.
        assert all(cpu < 0.01 for cpu in spent), f"sleep consumed CPU: {spent}"


class TestStructTimeIsFixedWidth:
    """`gmtime`/`localtime`/`mktime`/`struct_time`: nine fields, both access
    forms O(1), and the timestamp does not change the shape."""

    def test_nine_fields_for_any_timestamp(self) -> None:
        widths = {len(time.gmtime(stamp)) for stamp in (0, 10**9, 2 * 10**9)}

        assert widths == {9}

    def test_index_and_attribute_reach_the_same_field(self) -> None:
        parsed = time.gmtime(0)
        names = ("tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec")

        for index, name in enumerate(names):
            assert parsed[index] == getattr(parsed, name)

    def test_mktime_inverts_localtime(self) -> None:
        stamp = 1_000_000_000.0

        assert time.mktime(time.localtime(stamp)) == stamp

    def test_struct_time_rebuilds_from_its_own_fields(self) -> None:
        original = time.gmtime(1_000_000_000)

        rebuilt = time.struct_time(tuple(original))

        assert tuple(rebuilt) == tuple(original)
        assert rebuilt.tm_year == original.tm_year


class TestFixedWidthFormatting:
    """`asctime`/`ctime`: fixed-width apart from the year field, so 24
    characters for any four-digit year and not for years outside that."""

    def test_twenty_four_characters_across_four_digit_years(self) -> None:
        stamps = (0, 10**9, 2 * 10**9, 1_234_567_890)

        assert {len(time.asctime(time.gmtime(stamp))) for stamp in stamps} == {24}
        assert {len(time.ctime(stamp)) for stamp in stamps} == {24}

    def test_the_year_field_is_the_part_that_is_not_fixed(self) -> None:
        """Which is why the row says four-digit rather than always."""
        widths = {}
        for year in (1, 100, 1970, 9999, 10000):
            fields = (year, 1, 1, 0, 0, 0, 0, 1, 0)
            widths[year] = len(time.asctime(time.struct_time(fields)))

        assert widths[1970] == widths[9999] == 24
        assert widths[1] == 21
        assert widths[10000] == 25


class TestStrftimeFollowsItsOutput:
    """`time.strftime(format, t)` | O(n) | O(n) | n = output length."""

    @staticmethod
    def _literal(size: int) -> str:
        """A format of `size` literal characters, producing `size` of output."""
        return "x" * size

    def test_the_output_is_as_long_as_the_format_asks_for(self) -> None:
        moment = time.gmtime(0)

        for size in (10, 1000, 10000):
            assert len(time.strftime(self._literal(size), moment)) == size

    @pytest.mark.timing
    def test_ten_times_the_output_costs_far_more_than_a_constant(self) -> None:
        moment = time.gmtime(0)
        small = self._literal(1_000)
        large = self._literal(10_000)

        small_ns = best_ns(lambda: time.strftime(small, moment), inner=5)
        large_ns = best_ns(lambda: time.strftime(large, moment), inner=5)

        ratio = large_ns / small_ns
        assert ratio > 4, (
            f"10x the output cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a constant-time formatter would give x1"
        )


class TestStrptimeFollowsItsInput:
    """`time.strptime(string, format)` | O(n) | O(n) | n = input length."""

    @staticmethod
    def _padded(size: int) -> tuple[str, str]:
        """A (value, format) pair of `size` literal characters plus a year."""
        return "z" * size + "2026", "z" * size + "%Y"

    def test_the_padding_is_parsed_rather_than_skipped(self) -> None:
        value, fmt = self._padded(100)

        assert time.strptime(value, fmt).tm_year == 2026
        with pytest.raises(ValueError):
            time.strptime("y" * 100 + "2026", fmt)

    @pytest.mark.timing
    def test_ten_times_the_input_costs_far_more_than_a_constant(self) -> None:
        small_value, small_fmt = self._padded(10_000)
        large_value, large_fmt = self._padded(100_000)
        time.strptime(small_value, small_fmt)  # compile both formats first
        time.strptime(large_value, large_fmt)

        small_ns = best_ns(lambda: time.strptime(small_value, small_fmt), inner=3)
        large_ns = best_ns(lambda: time.strptime(large_value, large_fmt), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 4, (
            f"10x the input cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a constant-time parser would give x1"
        )


class TestStrptimeCachesTheCompiledFormat:
    """The format is compiled to a regex once and cached; the cache is small
    and is cleared wholesale rather than one entry at a time.

    Observed through the private `_strptime` module, which is where the cache
    lives and the only place it is visible.
    """

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
    def _clear_cache(self) -> Any:
        _strptime._regex_cache.clear()
        yield
        _strptime._regex_cache.clear()

    def test_using_a_format_puts_it_in_the_cache(self) -> None:
        value, fmt = self.FORMATS[0]

        time.strptime(value, fmt)

        assert fmt in _strptime._regex_cache

    def test_reusing_a_format_compiles_nothing_new(self) -> None:
        value, fmt = self.FORMATS[0]
        time.strptime(value, fmt)
        compiled = _strptime._regex_cache[fmt]

        for _ in range(50):
            time.strptime(value, fmt)

        assert _strptime._regex_cache[fmt] is compiled
        assert len(_strptime._regex_cache) == 1

    def test_the_seventh_format_clears_the_cache_rather_than_evicting_one(self) -> None:
        sizes = []
        for value, fmt in self.FORMATS:
            time.strptime(value, fmt)
            sizes.append(len(_strptime._regex_cache))

        assert sizes == [1, 2, 3, 4, 5, 6, 1], (
            f"expected a wholesale flush after six formats, saw {sizes}"
        )

    @pytest.mark.timing
    def test_a_missed_format_costs_more_than_a_cached_one(self) -> None:
        value, fmt = self.FORMATS[0]
        time.strptime(value, fmt)

        def cold() -> None:
            _strptime._regex_cache.clear()
            time.strptime(value, fmt)

        warm_ns = best_ns(lambda: time.strptime(value, fmt), inner=20)
        _strptime._regex_cache.clear()
        cold_ns = best_ns(cold, inner=3)

        ratio = cold_ns / warm_ns
        assert ratio > 1.5, (
            f"a cache miss cost x{ratio:.2f} ({warm_ns:.0f}ns to {cold_ns:.0f}ns); "
            "no caching at all would give x1"
        )


class TestTimezoneAttributes:
    """`timezone`/`altzone`/`daylight`/`tzname`: module attributes, so reading
    one is an attribute lookup and nothing more."""

    def test_the_offsets_are_whole_seconds(self) -> None:
        assert isinstance(time.timezone, int)
        assert isinstance(time.altzone, int)
        assert isinstance(time.daylight, int)

    def test_tzname_names_the_two_zones(self) -> None:
        assert isinstance(time.tzname, tuple)
        assert len(time.tzname) == 2
        assert all(isinstance(name, str) for name in time.tzname)

    @pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset is Unix only")
    def test_tzset_leaves_the_four_attributes_readable(self) -> None:
        time.tzset()

        assert isinstance(time.timezone, int)
        assert len(time.tzname) == 2


@pytest.mark.skipif(not hasattr(time, "pthread_getcpuclockid"), reason="Unix only")
class TestPthreadClockId:
    """`pthread_getcpuclockid(thread_id)`: one lookup, returning an id that
    `clock_gettime` accepts."""

    def test_the_id_reads_as_a_clock(self) -> None:
        import threading

        require_clock("clock_gettime")
        clock_id = time.pthread_getcpuclockid(threading.get_ident())

        assert isinstance(clock_id, int)
        assert time.clock_gettime(clock_id) >= 0


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, with nothing held back and nothing pre-classified."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import time\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr

    def test_clock_example_runs_without_posix_apis(self, tmp_path: Any) -> None:
        prelude = (
            "import time\n"
            "for name in list(vars(time)):\n"
            "    if name.startswith(('clock_', 'CLOCK_')):\n"
            "        delattr(time, name)\n"
        )
        result = _run(prelude + _blocks()[0][1], tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("True ")
