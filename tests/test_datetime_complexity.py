"""Tests for docs/stdlib/datetime.md.

The page prices every operation on a `date`, `datetime`, `time` or
`timedelta` at O(1), because each is a fixed-size record with a bounded
range, and gives only the string conversions a size variable: `n` for the
string being parsed and `f` for a format. The fixed-size framing is settled by
object sizes and a range check, the tzinfo cost model by a counting `tzinfo`,
the format cache by observing `_strptime`'s cache, and the growth of the
string conversions by traced allocation and timing ratios over 100x size
steps. Each growth ratio is bounded on both sides: above 20x, so the term is
there, and below 1,000x, so it is not quadratic.

Measurement scope:

* `sys.getsizeof` is equal for the earliest and latest `datetime` and `date`,
  and for a zero and a 3,652,058-day `timedelta`; one past `MAXYEAR` and one
  past a billion days raise `OverflowError`. Subtracting datetimes 9,998 years
  apart costs under 2x subtracting two a day apart.
* A counting `tzinfo` observes that `astimezone()` to another zone calls the
  source's `utcoffset()` and then the target's `fromutc()`, once each, and
  to its own zone returns the object with no call; that
  `utcoffset()`, `dst()` and `tzname()` on a datetime call the method of the
  same name once, and on a `time` pass `None`; that `now(tz)` and
  `fromtimestamp(ts, tz)` reach `tz.fromutc()`; and that the base
  `tzinfo.fromutc()` calls `utcoffset()` and `dst()`. The accessors
  answer `None` without a `tzinfo`.
* `strptime()`'s n term: the format `"%Y %m"`, with its regex cached, parses
  inputs whose whitespace run grows from 1,000 to 100,000 characters; time
  grows between 20x and 1,000x and the traced peak stays under 4 KB at both
  sizes.
  Its f term: a format whose whitespace run grows from 1,000 to 100,000
  characters, parsing the same 7-character input with the format cache
  emptied before each call, costs between 20x and 1,000x more; a format of
  10,000 and 100,000 literal characters, compiled with `re`'s cache purged as
  well, peaks between 5x and 50x higher.
* Whitespace runs that meet: a `LocaleTime` with its AM/PM names set empty,
  standing in for a locale that has none, compiles `"%Y %p %m"` to two
  adjacent whitespace patterns. Rejecting `"2024"` plus 500 and 5,000 spaces
  then costs more than 35x more, against less than 35x for the single run of
  `"%Y %m"`.
* A rejected input of 10,000 characters appears in full in the `ValueError`
  from `date.fromisoformat()` and from `strptime()`.
* The first `strptime()` in a fresh interpreter imports `_strptime`, which
  `fromisoformat()` never does, and costs more than 100x a later parse with
  the same format. A counting `TimeRE.compile` sees one compile for ten
  parses with one format and none for ten `fromisoformat()` calls; seven
  formats in turn leave the cache sizes 1, 2, 3, 4, 5, 6, 1, and a repeat of
  a cached format at size six is recompiled; `fromisoformat()` leaves the
  cache empty. On a 19-character ISO string with the format cached,
  `strptime()` costs more than 5x `fromisoformat()`.
* `fromisoformat()`'s n term: from 3.11, `datetime` and `time` inputs whose
  fractional-second digits grow from 1,000 to 100,000 cost between 20x and
  1,000x more, with a traced peak under 1 KB at both sizes; on every version,
  `date.fromisoformat()` rejecting 1,000 and 100,000 characters costs between
  20x and 1,000x more.
* `strftime()` over a format repeated 10 and 1,000 times costs between 20x
  and 1,000x more, and its output and traced peak grow with it. `%Z` with a
  `timezone` named by 10,000 characters formats to all of them, through
  `strftime()` and `format()`, for a `datetime` and a `time`. `isoformat()`, `str()`
  and `ctime()` produce the same length for years 1, 2024 and 9999; with
  microseconds and the widest UTC offset a datetime's ISO form is 42
  characters and a time's 31 at each of those years.
* `format()` with an empty spec equals `str()` and with a non-empty spec
  equals `strftime()`, for `date`, `datetime` and `time`.
* Row values are asserted directly: the class attributes, `timedelta`
  normalisation and rounding, `timezone`'s offset range and singleton, the
  `UTC` alias and the `datetime_CAPI` capsule. A naive `timestamp()` is
  observed as local time in a subprocess run under `TZ=EST5`.
* The version notes are asserted on each side of their boundary with
  `sys.version_info`: `fromisoformat()`'s wider grammar and `datetime.UTC` at
  3.11, the `utcnow()` and `utcfromtimestamp()` deprecation at 3.12, and
  `date.strptime()` and `time.strptime()` at 3.14. Building the regular
  expression for 5,000 and 100,000 `%%` directives costs under 60x more from
  3.12.8 and 3.13.1 and over 60x before; 3.12.7 measured about 170x and
  3.12.14 about 20x.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail with an `AssertionError` at
  that line.

Not settled here:

* A `zoneinfo.ZoneInfo` offset lookup, which the page prices on the zoneinfo
  page and not here; the bounds on this page count one `tzinfo` call as O(1).
  How many calls an aware operation makes is observed only for the operations
  listed above, and is not a stated count.
* Locale. The formats measured use numeric directives only; name directives
  (`%A`, `%B`, `%p`) compile to the locale's names, which changes a constant,
  not the term, unless a name set is empty (measured above only through a
  modified `LocaleTime`, not a real locale). A locale or `time.tzname` change
  also rebuilds `_strptime`'s tables, a constant not measured here.
* Platform. `strftime()` hands the format to the C library, so its linearity
  is measured on glibc only.
* Non-ASCII input. The page's parsing space bounds assume ASCII input:
  `fromisoformat()` copies a non-ASCII input, such as one with a non-ASCII
  date-time separator, to UTF-8, which is O(n) space on a successful parse.
* Integer arguments of unbounded size. The O(1) constructor rows assume
  machine-sized arguments; `timedelta(weeks=k, days=-7 * k)` with a
  100,000-bit `k` succeeds after big-integer arithmetic on `k`. The page
  does not price arithmetic on arguments far outside the range.
* Implementation facts read from Modules/_datetimemodule.c and
  Lib/_strptime.py rather than observed: that the types store fixed-width
  integer fields, that `fromisoformat()` is written in C, and that
  `strptime()` runs in Python. The equal object sizes and the subtraction
  timing above are consistent with the first and do not establish it.
"""

from __future__ import annotations

import _strptime
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time as time_module
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "datetime.md"
EXPECTED_BLOCKS = 7

# Distinct formats and a string each matches, for filling the strptime cache.
# Numeric directives only, so the samples parse under any locale.
FORMAT_SAMPLES: list[tuple[str, str]] = [
    ("%Y-%m-%d", "2024-01-15"),
    ("%d/%m/%Y", "15/01/2024"),
    ("%m-%d-%Y", "01-15-2024"),
    ("%Y.%m.%d", "2024.01.15"),
    ("%H:%M:%S", "12:30:45"),
    ("%Y-%j", "2024-015"),
    ("%Y%m%d", "20240115"),
]


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time_module.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time_module.perf_counter_ns() - start) / inner
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


def run_isolated(source: str, env: dict[str, str] | None = None) -> str:
    """Run a snippet in a fresh interpreter and return its stdout.

    `_strptime` is imported once per process and never unloaded, so anything
    asking what the first call does has to ask a new interpreter.
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def clean_format_cache() -> Iterator[None]:
    """Empty the strptime regex cache, and leave it as it was found."""
    saved = dict(_strptime._regex_cache)
    _strptime._regex_cache.clear()
    yield
    _strptime._regex_cache.clear()
    _strptime._regex_cache.update(saved)


class CountingZone(tzinfo):
    """A fixed +01:00 zone that records which of its methods were called."""

    def __init__(self, calls: list[str] | None = None) -> None:
        self.calls: list[str] = [] if calls is None else calls
        self.arguments: list[datetime | None] = []

    def utcoffset(self, dt: datetime | None) -> timedelta:
        self.calls.append("utcoffset")
        self.arguments.append(dt)
        return timedelta(hours=1)

    def dst(self, dt: datetime | None) -> timedelta:
        self.calls.append("dst")
        self.arguments.append(dt)
        return timedelta(0)

    def tzname(self, dt: datetime | None) -> str:
        self.calls.append("tzname")
        self.arguments.append(dt)
        return "CZ"


class CountingFromutcZone(CountingZone):
    """Also records `fromutc()`, and answers it without the base class."""

    def fromutc(self, dt: datetime) -> datetime:
        self.calls.append("fromutc")
        return (dt + timedelta(hours=1)).replace(tzinfo=self)


def _count_compiles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every format `_strptime` compiles from here on."""
    compiled: list[str] = []
    original = _strptime.TimeRE.compile

    def counting_compile(self: Any, format: str) -> Any:
        compiled.append(format)
        return original(self, format)

    monkeypatch.setattr(_strptime.TimeRE, "compile", counting_compile)
    return compiled


class TestValuesAreFixedSizeRecords:
    """The page's framing: fixed-size records with a bounded range.

    Every O(1) row rests on this. A record that grew with the value it held
    would give the arithmetic and comparison rows a term.
    """

    def test_the_extremes_of_the_range_are_the_same_size(self) -> None:
        assert sys.getsizeof(datetime.min) == sys.getsizeof(datetime.max)
        assert sys.getsizeof(date(1, 1, 1)) == sys.getsizeof(date(9999, 12, 31))
        assert sys.getsizeof(timedelta(0)) == sys.getsizeof(timedelta(days=3_652_058))

    def test_the_range_is_bounded(self) -> None:
        import datetime as module

        assert (module.MINYEAR, module.MAXYEAR) == (1, 9999)
        assert date.max == date(9999, 12, 31)
        with pytest.raises(OverflowError):
            _ = date.max + timedelta(days=1)
        assert timedelta.max.days == 999_999_999
        with pytest.raises(OverflowError):
            timedelta(days=1_000_000_000)

    @pytest.mark.timing
    def test_subtraction_does_not_care_how_far_apart_the_operands_are(self) -> None:
        near = (datetime(2024, 1, 15), datetime(2024, 1, 16))
        far = (datetime(1, 1, 1), datetime(9999, 12, 31))

        near_ns = best_ns(lambda: near[1] - near[0], inner=10_000)
        far_ns = best_ns(lambda: far[1] - far[0], inner=10_000)

        assert far_ns < near_ns * 2, (
            f"one day apart {near_ns:.0f}ns, 9,998 years apart {far_ns:.0f}ns"
        )

    def test_replace_and_arithmetic_return_new_objects(self) -> None:
        original = datetime(2024, 1, 15, 12, 0, 0)

        replaced = original.replace(year=2025)
        shifted = original + timedelta(days=1)

        assert original == datetime(2024, 1, 15, 12, 0, 0)
        assert replaced is not original and shifted is not original
        assert sys.getsizeof(replaced) == sys.getsizeof(original)


class TestAwareOperationsCallTheTzinfo:
    """The cost model: an aware operation calls its tzinfo a bounded number of
    times, and the rows name which method. A counting tzinfo observes the
    calls, so a row naming the wrong method fails."""

    def test_astimezone_asks_the_source_offset_then_the_target_fromutc(self) -> None:
        log: list[str] = []
        source, target = CountingZone(log), CountingFromutcZone(log)
        moment = datetime(2024, 1, 15, 12, 0, tzinfo=source)

        converted = moment.astimezone(target)

        assert log == ["utcoffset", "fromutc"], "in that order, once each, through one log"
        assert converted.tzinfo is target

    def test_astimezone_to_its_own_zone_calls_nothing(self) -> None:
        zone = CountingFromutcZone()
        moment = datetime(2024, 1, 15, 12, 0, tzinfo=zone)

        assert moment.astimezone(zone) is moment
        assert zone.calls == []

    def test_accessors_without_a_tzinfo_answer_none(self) -> None:
        for value in (datetime(2024, 1, 15), time(12, 0)):
            assert (value.utcoffset(), value.dst(), value.tzname()) == (None, None, None)

    def test_offset_accessors_call_the_method_of_the_same_name_once(self) -> None:
        for name in ("utcoffset", "dst", "tzname"):
            zone = CountingZone()
            getattr(datetime(2024, 1, 15, tzinfo=zone), name)()
            assert zone.calls == [name]

    def test_time_accessors_pass_none(self) -> None:
        zone = CountingZone()
        moment = time(12, 0, tzinfo=zone)

        assert moment.utcoffset() == timedelta(hours=1)
        assert moment.dst() == timedelta(0)
        assert moment.tzname() == "CZ"
        assert zone.calls == ["utcoffset", "dst", "tzname"]
        assert zone.arguments == [None, None, None]

    def test_now_and_fromtimestamp_convert_through_fromutc(self) -> None:
        for build in (
            lambda zone: datetime.now(zone),
            lambda zone: datetime.fromtimestamp(0, zone),
        ):
            zone = CountingFromutcZone()
            result = build(zone)
            assert "fromutc" in zone.calls
            assert result.tzinfo is zone

    def test_the_default_fromutc_asks_utcoffset_and_dst(self) -> None:
        zone = CountingZone()
        utc_wall_clock = datetime(2024, 1, 15, 12, 0, tzinfo=zone)

        local = zone.fromutc(utc_wall_clock)

        assert local.hour == 13
        assert set(zone.calls) == {"utcoffset", "dst"}

    def test_the_base_class_supplies_no_offset(self) -> None:
        with pytest.raises(NotImplementedError):
            tzinfo().utcoffset(None)


class TestStrptime:
    """`strptime()` is O(n + f) time and O(f) space; `date.strptime()` and
    `time.strptime()` share its parser from 3.14."""

    @pytest.mark.timing
    def test_time_follows_the_input(self) -> None:
        short = "2024" + " " * 1_000 + "01"
        long = "2024" + " " * 100_000 + "01"
        datetime.strptime(short, "%Y %m")  # compile the format first

        short_ns = best_ns(lambda: datetime.strptime(short, "%Y %m"), inner=20)
        long_ns = best_ns(lambda: datetime.strptime(long, "%Y %m"), inner=20)

        assert short_ns * 20 < long_ns < short_ns * 1_000, (
            f"100x the input cost x{long_ns / short_ns:.1f} ({short_ns:.0f}ns to {long_ns:.0f}ns)"
        )

    def test_space_does_not_follow_the_input(self) -> None:
        short = "2024" + " " * 1_000 + "01"
        long = "2024" + " " * 100_000 + "01"
        datetime.strptime(short, "%Y %m")

        short_peak = peak_bytes(lambda: datetime.strptime(short, "%Y %m"))
        long_peak = peak_bytes(lambda: datetime.strptime(long, "%Y %m"))

        assert long_peak < 4_096, f"a 100,000-character input peaked at {long_peak} bytes"
        assert short_peak < 4_096

    @pytest.mark.timing
    def test_a_compile_follows_the_format(self, clean_format_cache: None) -> None:
        short = "%Y" + " " * 1_000 + "%m"
        long = "%Y" + " " * 100_000 + "%m"

        def parse(fmt: str) -> None:
            _strptime._regex_cache.clear()
            datetime.strptime("2024 01", fmt)

        parse(short)
        parse(long)
        short_ns = best_ns(lambda: parse(short), inner=5)
        long_ns = best_ns(lambda: parse(long), inner=5)

        assert short_ns * 20 < long_ns < short_ns * 1_000, (
            f"100x the format cost x{long_ns / short_ns:.1f} "
            f"({short_ns:.0f}ns to {long_ns:.0f}ns) for the same 7-character input"
        )

    def test_a_compiled_format_follows_its_length(self, clean_format_cache: None) -> None:
        def compile_peak(length: int) -> int:
            fmt = "%Y" + "x" * length + "%m"
            text = "2024" + "x" * length + "01"

            def parse() -> None:
                _strptime._regex_cache.clear()
                re.purge()
                datetime.strptime(text, fmt)

            parse()
            return peak_bytes(parse)

        small, large = compile_peak(10_000), compile_peak(100_000)

        assert small * 5 < large < small * 50, (
            f"10x the format peaked at {large} bytes against {small}"
        )

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="date.strptime() is 3.14+")
    def test_date_and_time_strptime_use_the_same_cache(self, clean_format_cache: None) -> None:
        parse_date = date.strptime  # pyright: ignore[reportAttributeAccessIssue]
        parse_time = time.strptime  # pyright: ignore[reportAttributeAccessIssue]

        assert parse_date("2024-01-15", "%Y-%m-%d") == date(2024, 1, 15)
        assert parse_time("12:30:45", "%H:%M:%S") == time(12, 30, 45)
        assert list(_strptime._regex_cache) == ["%Y-%m-%d", "%H:%M:%S"]

    def test_rejects_trailing_input(self) -> None:
        with pytest.raises(ValueError, match="unconverted data remains"):
            datetime.strptime("2024-01-15T12:30:45", "%Y-%m-%d")

    @pytest.mark.timing
    def test_whitespace_runs_that_meet_backtrack(self) -> None:
        """A locale with no AM/PM names compiles `%p` to nothing, so the runs on
        either side of it meet; rejecting 10x the spaces costs about 100x."""
        no_am_pm = _strptime.LocaleTime()
        no_am_pm.am_pm = ["", ""]
        meeting = _strptime.TimeRE(no_am_pm).compile("%Y %p %m")
        single = _strptime.TimeRE().compile("%Y %m")

        def ratio(regex: re.Pattern[str]) -> float:
            short, long = "2024" + " " * 500 + "x", "2024" + " " * 5_000 + "x"
            assert regex.match(short) is None
            return best_ns(lambda: regex.match(long), repeats=3) / best_ns(
                lambda: regex.match(short), repeats=3
            )

        meeting_ratio, single_ratio = ratio(meeting), ratio(single)
        assert meeting_ratio > 35, f"10x the spaces cost x{meeting_ratio:.0f} for two runs"
        assert single_ratio < 35, f"10x the spaces cost x{single_ratio:.0f} for one run"


class TestTheFirstStrptimeCall:
    """The first call imports `_strptime` and compiles its format; a run of
    parses with one format reuses the compiled pattern; only a handful are
    kept."""

    def test_strptime_imports_its_module_and_fromisoformat_does_not(self) -> None:
        results = {}
        for name, call in (
            ("strptime", 'datetime.strptime("2024-01-15", "%Y-%m-%d")'),
            ("fromisoformat", 'datetime.fromisoformat("2024-01-15")'),
        ):
            results[name] = run_isolated(f"""
                import sys
                from datetime import datetime
                assert "_strptime" not in sys.modules
                {call}
                print("_strptime" in sys.modules)
            """).strip()

        assert results == {"strptime": "True", "fromisoformat": "False"}

    @pytest.mark.timing
    def test_the_first_parse_costs_far_more_than_the_next(self) -> None:
        output = run_isolated("""
            import time
            from datetime import datetime

            start = time.perf_counter()
            datetime.strptime("2024-01-15", "%Y-%m-%d")
            first = time.perf_counter() - start

            start = time.perf_counter()
            for _ in range(200):
                datetime.strptime("2024-01-15", "%Y-%m-%d")
            steady = (time.perf_counter() - start) / 200

            print(first)
            print(steady)
        """)
        first, steady = (float(line) for line in output.split())

        assert first > steady * 100, f"first {first:.2e}s, steady {steady:.2e}s"

    def test_one_format_is_compiled_once(
        self, clean_format_cache: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        compiled = _count_compiles(monkeypatch)

        for day in range(1, 11):
            datetime.strptime(f"2024-01-{day:02d}", "%Y-%m-%d")

        assert compiled == ["%Y-%m-%d"], f"ten parses compiled {compiled}"
        assert list(_strptime._regex_cache) == ["%Y-%m-%d"]

    def test_only_a_handful_of_formats_are_kept(self, clean_format_cache: None) -> None:
        sizes = []
        for fmt, sample in FORMAT_SAMPLES:
            datetime.strptime(sample, fmt)
            sizes.append(len(_strptime._regex_cache))

        assert sizes == [1, 2, 3, 4, 5, 6, 1], f"the cache sizes were {sizes}"

    def test_cycling_past_the_limit_recompiles_a_cached_format(
        self, clean_format_cache: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clear runs before the lookup, so a format that was cached is
        compiled again once the cache is full."""
        for fmt, sample in FORMAT_SAMPLES[:6]:
            datetime.strptime(sample, fmt)
        compiled = _count_compiles(monkeypatch)
        repeat_format, repeat_sample = FORMAT_SAMPLES[0]
        datetime.strptime(repeat_sample, repeat_format)

        assert compiled == [repeat_format]
        assert list(_strptime._regex_cache) == [repeat_format]

    def test_fromisoformat_never_compiles_a_format(
        self, clean_format_cache: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        compiled = _count_compiles(monkeypatch)

        for day in range(1, 11):
            datetime.fromisoformat(f"2024-01-{day:02d}")

        assert compiled == []
        assert _strptime._regex_cache == {}

    @pytest.mark.timing
    def test_fromisoformat_beats_strptime_on_iso_input(self) -> None:
        text = "2024-01-15T12:30:45"
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")

        iso_ns = best_ns(lambda: datetime.fromisoformat(text), inner=5_000)
        strptime_ns = best_ns(lambda: datetime.strptime(text, "%Y-%m-%dT%H:%M:%S"), inner=5_000)

        assert strptime_ns > iso_ns * 5, (
            f"with the regex cached: fromisoformat {iso_ns:.0f}ns, strptime {strptime_ns:.0f}ns"
        )


class TestFromisoformat:
    """O(n) time and O(1) space, parsed in C."""

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="3.10 rejects extra digits")
    def test_time_follows_the_fractional_digits(self) -> None:
        for parse, prefix in (
            (datetime.fromisoformat, "2024-01-15T12:30:45."),
            (time.fromisoformat, "12:30:45."),
        ):
            short = partial(parse, prefix + "1" * 1_000)
            long = partial(parse, prefix + "1" * 100_000)
            short_ns = best_ns(short, inner=50)
            long_ns = best_ns(long, inner=50)

            assert short_ns * 20 < long_ns < short_ns * 1_000, (
                f"{parse.__qualname__}: 100x the digits cost x{long_ns / short_ns:.1f}"
            )

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="3.10 rejects extra digits")
    def test_space_does_not_follow_the_fractional_digits(self) -> None:
        for parse, prefix in (
            (datetime.fromisoformat, "2024-01-15T12:30:45."),
            (time.fromisoformat, "12:30:45."),
        ):
            peaks = []
            for digits in (1_000, 100_000):
                text = prefix + "1" * digits
                assert parse(text).microsecond == 111_111
                peaks.append(peak_bytes(partial(parse, text)))

            assert max(peaks) < 1_024, f"{parse.__qualname__} peaked at {peaks} bytes"

    @pytest.mark.timing
    def test_date_rejection_follows_the_input(self) -> None:
        def reject(text: str) -> None:
            with pytest.raises(ValueError):
                date.fromisoformat(text)

        short, long = "x" * 1_000, "x" * 100_000
        short_ns = best_ns(lambda: reject(short), inner=50)
        long_ns = best_ns(lambda: reject(long), inner=50)

        assert short_ns * 20 < long_ns < short_ns * 1_000, (
            f"100x the input cost x{long_ns / short_ns:.1f}"
        )

    def test_a_rejected_input_is_echoed_in_the_error(self) -> None:
        tail = "x" * 10_000
        with pytest.raises(ValueError) as fromiso:
            date.fromisoformat(tail)
        with pytest.raises(ValueError) as strp:
            datetime.strptime("2024-01-15" + tail, "%Y-%m-%d")

        assert tail in str(fromiso.value)
        assert tail in str(strp.value)


class TestFormatting:
    """`strftime()` and `__format__()` are O(f); the ISO forms are fixed-width."""

    @pytest.mark.timing
    def test_strftime_follows_the_format(self) -> None:
        moment = datetime(2024, 1, 15, 12, 30, 45)
        short, long = "%Y-%m-%d " * 10, "%Y-%m-%d " * 1_000

        short_ns = best_ns(lambda: moment.strftime(short), inner=100)
        long_ns = best_ns(lambda: moment.strftime(long), inner=100)

        assert short_ns * 20 < long_ns < short_ns * 1_000, (
            f"100x the format cost x{long_ns / short_ns:.1f}"
        )

    def test_strftime_output_and_peak_follow_the_format(self) -> None:
        moment = datetime(2024, 1, 15, 12, 30, 45)
        short, long = "%Y-%m-%d " * 100, "%Y-%m-%d " * 10_000

        assert len(moment.strftime(long)) == 100 * len(moment.strftime(short))
        short_peak = peak_bytes(lambda: moment.strftime(short))
        long_peak = peak_bytes(lambda: moment.strftime(long))

        assert short_peak * 20 < long_peak < short_peak * 1_000, (
            f"peaks {short_peak} and {long_peak} bytes"
        )

    def test_iso_and_ctime_forms_are_fixed_width(self) -> None:
        for render in (datetime.isoformat, str, datetime.ctime):
            lengths = {len(render(datetime(year, 1, 1))) for year in (1, 2024, 9999)}
            assert len(lengths) == 1, f"{render.__name__} lengths {lengths}"
        for render in (date.isoformat, str, date.ctime):
            lengths = {len(render(date(year, 1, 1))) for year in (1, 2024, 9999)}
            assert len(lengths) == 1, f"{render.__name__} lengths {lengths}"

    def test_iso_forms_with_every_optional_field_are_still_bounded(self) -> None:
        """Microseconds and the widest UTC offset are the fields that lengthen
        the output; with both present, the length is still the same at every
        year."""
        widest = timezone(-timedelta(hours=23, minutes=59, seconds=59, microseconds=999_999))
        for year in (1, 2024, 9999):
            moment = datetime(year, 12, 31, 23, 59, 59, 999_999, tzinfo=widest)
            assert len(moment.isoformat()) == len(str(moment)) == 42
            assert len(moment.timetz().isoformat()) == 31

    def test_an_empty_spec_is_str_and_any_other_is_strftime(self) -> None:
        for value in (date(2024, 1, 15), datetime(2024, 1, 15, 12, 30), time(12, 30)):
            assert format(value, "") == str(value)
            assert format(value, "%H:%M %d") == value.strftime("%H:%M %d")

    def test_a_zone_name_counts_toward_the_format(self) -> None:
        name = "z" * 10_000
        zone = timezone(timedelta(0), name)
        for value in (datetime(2024, 1, 15, tzinfo=zone), time(12, tzinfo=zone)):
            assert value.strftime("%Z") == name
            assert format(value, "%Z") == name


class TestRowValues:
    """Values the Notes cells state outright."""

    def test_class_attributes(self) -> None:
        assert date.resolution == timedelta(days=1)
        assert datetime.resolution == timedelta(microseconds=1)
        assert time.resolution == timedelta(microseconds=1)
        assert (time.min, time.max) == (time(0), time(23, 59, 59, 999_999))
        assert timedelta.max == timedelta(days=999_999_999, microseconds=86_400_000_000 - 1)
        assert timedelta.min == -timedelta(days=999_999_999)

    def test_ordinal_day_one(self) -> None:
        assert date.fromordinal(1) == date(1, 1, 1)
        assert date(2024, 1, 15).toordinal() == 738_900

    def test_weekday_numbering(self) -> None:
        monday = date(2024, 1, 15)

        assert (monday.weekday(), monday.isoweekday()) == (0, 1)
        assert monday.isocalendar().week == 3

    def test_time_drops_the_tzinfo_and_timetz_keeps_it(self) -> None:
        moment = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        assert moment.time().tzinfo is None
        assert moment.timetz().tzinfo is timezone.utc

    def test_replace_tzinfo_does_not_convert(self) -> None:
        moment = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        offset = timezone(timedelta(hours=5))

        assert moment.replace(tzinfo=offset).hour == 12
        assert moment.astimezone(offset).hour == 17

    def test_a_naive_timestamp_is_local_time(self) -> None:
        env = dict(os.environ, TZ="EST5")
        output = run_isolated(
            """
            from datetime import datetime
            print(datetime(1970, 1, 1).timestamp())
            """,
            env,
        )

        assert float(output) == 5 * 3_600

    def test_timedelta_normalises_and_rounds(self) -> None:
        delta = timedelta(hours=25, milliseconds=1)
        three = timedelta(microseconds=3)

        assert (delta.days, delta.seconds, delta.microseconds) == (1, 3_600, 1_000)
        assert three * 0.5 == timedelta(microseconds=2), "half to even"
        assert three / 2 == timedelta(microseconds=2)
        assert three // 2 == timedelta(microseconds=1)
        assert timedelta(hours=3) / timedelta(hours=2) == 1.5
        assert timedelta(hours=3) // timedelta(hours=2) == 1
        assert timedelta(hours=3) % timedelta(hours=2) == timedelta(hours=1)
        assert divmod(timedelta(hours=3), timedelta(hours=2)) == (1, timedelta(hours=1))
        assert abs(-three) == +three == three
        assert str(timedelta(days=1, seconds=1)) == "1 day, 0:00:01"

    def test_timezone_offsets_are_strictly_inside_a_day(self) -> None:
        for hours in (24, -24):
            with pytest.raises(ValueError):
                timezone(timedelta(hours=hours))
        assert timezone.max.utcoffset(None) == timedelta(hours=23, minutes=59)
        assert timezone.min.utcoffset(None) == -timedelta(hours=23, minutes=59)

    def test_timezone_methods(self) -> None:
        plus_five = timezone(timedelta(hours=5), "PLUS5")
        utc_wall_clock = datetime(2024, 1, 15, 12, 0, tzinfo=plus_five)

        assert plus_five.utcoffset(None) == timedelta(hours=5)
        assert plus_five.dst(None) is None
        assert plus_five.tzname(None) == "PLUS5"
        assert plus_five.fromutc(utc_wall_clock).hour == 17
        assert timezone(timedelta(0)) is timezone.utc

    def test_constants(self) -> None:
        import datetime as module

        assert type(module.datetime_CAPI).__name__ == "PyCapsule"
        if sys.version_info >= (3, 11):
            assert module.UTC is timezone.utc
        else:
            assert not hasattr(module, "UTC")


class TestVersionNotes:
    """Each note, asserted on both sides of its boundary."""

    def test_fromisoformat_widened_in_3_11(self) -> None:
        extended = ["2024-01-15T12:30:45Z", "20240115T123045", "12:30:45.1234567"]
        parsers = [datetime.fromisoformat, datetime.fromisoformat, time.fromisoformat]

        for parse, text in zip(parsers, extended, strict=True):
            if sys.version_info >= (3, 11):
                assert parse(text) is not None
            else:
                with pytest.raises(ValueError):
                    parse(text)

    def test_utcnow_and_utcfromtimestamp_are_deprecated_from_3_12(self) -> None:
        if sys.version_info >= (3, 12):
            with pytest.deprecated_call():
                naive = datetime.utcnow()
            with pytest.deprecated_call():
                datetime.utcfromtimestamp(0)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                naive = datetime.utcnow()
                datetime.utcfromtimestamp(0)
        assert naive.tzinfo is None

    @pytest.mark.timing
    def test_compiling_a_format_turned_linear_in_3_12_8_and_3_13_1(self) -> None:
        """20x the directives costs about 20x from 3.12.8 and 3.13.1, and about
        150x before."""
        builder = _strptime.TimeRE()
        few, many = "%%" * 5_000, "%%" * 100_000
        few_ns = best_ns(lambda: builder.pattern(few), repeats=3)
        many_ns = best_ns(lambda: builder.pattern(many), repeats=3)
        ratio = many_ns / few_ns

        linear = sys.version_info >= (3, 13, 1) or (3, 12, 8) <= sys.version_info < (3, 13)
        if linear:
            assert ratio < 60, f"20x the directives cost x{ratio:.0f}"
        else:
            assert ratio > 60, f"20x the directives cost x{ratio:.0f}"

    def test_date_and_time_strptime_arrive_in_3_14(self) -> None:
        present = sys.version_info >= (3, 14)

        assert hasattr(date, "strptime") is present
        assert ("strptime" in vars(time)) is present


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
        [sys.executable, "-W", "error", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, with warnings as errors so a
    deprecated call fails, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "converted.hour == 17" in s)
        mutated = source.replace("converted.hour == 17", "converted.hour == 12", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
        assert "converted.hour == 12" in result.stderr, "it failed at the mutated line"
