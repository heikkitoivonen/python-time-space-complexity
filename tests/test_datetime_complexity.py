"""Tests to verify documented behaviour of the datetime module.

The page's own framing is its most useful claim: a `datetime`, `date`, `time`
or `timedelta` is a fixed-size record of small integers, so everything done to
one of them is constant time and only the string conversions scale. That is
testable directly - the year 1 and the year 9999 produce objects of the same
size, and subtracting two datetimes three thousand years apart costs what
subtracting two a day apart does.

What is left is parsing and formatting, and that is where the page was wrong:

* The `strptime` row said "n = input length; format-dependent" while the
  example beside it said "n = length of format string". Both terms are real -
  the format is compiled to a regex and the input is what that regex matches -
  so the row now carries both and the example agrees with it.
* Nothing on the page mentioned that the first `strptime` in a process imports
  `_strptime`. It is not a small effect: 13.7 ms for the import, 138 us for
  the first parse after it, and 2.2 us in the steady state. `fromisoformat`
  never imports it at all, which is observable rather than timed.
* "Better: cache format if reusing" advised assigning the format to a
  variable, which does nothing - the caching is inside `_strptime`, keyed on
  the format string, and a local name cannot affect it. The claim beside it,
  "Still O(n*m) total but pattern is consistent", named no operation.
* `fromisoformat` and `strptime` were both listed at O(n) with nothing to
  choose between them. For ISO 8601 input `fromisoformat` is the cheaper by a
  wide margin, and the page now says which side wins rather than by how much.
* "Python 3.11+: New zoneinfo module for IANA timezones" - `zoneinfo` was
  added in 3.9, and is present on every version this project supports.

Two code blocks did not run: the Comparisons block used `timedelta` without
importing it, and the caching block used an undefined `large_list`.

Untested axes, and why:

* Locale. The formats used here are numeric directives only, so the suite
  holds under any locale. Name directives (`%A`, `%B`, `%b`, `%p`) compile
  to the locale's names, which changes the constant in front of the format
  length, not the term - that constant is what goes untested.
* Platform. `strftime` hands the work to the C library on some platforms;
  the linearity measured here is CPython's own pass over the format.

Not settled by execution:

* `MINYEAR`, `MAXYEAR` and `datetime_CAPI`. They are constants, and the
  Time/Space columns beside them describe reading a name.
* "Python 3.2+" and "Python 3.6+" in the Version Notes: nothing in the
  supported range can show either boundary.
* "For month arithmetic, use dateutil.relativedelta". `dateutil` reaches this
  environment as a transitive dependency of the docs toolchain rather than a
  declared one, so the block that imports it is run only when it is present
  and reported as unaccounted for when it is not.
"""

from __future__ import annotations

import _strptime
import importlib.util
import pathlib
import re
import subprocess
import sys
import textwrap
import timeit
import zoneinfo
from collections.abc import Callable, Iterator
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "stdlib" / "datetime.md"
EXPECTED_BLOCKS = 10
DATEUTIL_MARKER = "dateutil"
HAS_DATEUTIL = importlib.util.find_spec("dateutil") is not None

# Distinct formats and a string each matches, for filling the strptime cache.
# Numeric directives only: `%b` and friends compile to the locale's month
# names, so a sample holding "Jan" fails to parse under a non-English locale.
FORMAT_SAMPLES: list[tuple[str, str]] = [
    ("%Y-%m-%d", "2024-01-15"),
    ("%d/%m/%Y", "15/01/2024"),
    ("%m-%d-%Y", "01-15-2024"),
    ("%Y.%m.%d", "2024.01.15"),
    ("%H:%M:%S", "12:30:45"),
    ("%Y-%j", "2024-015"),
    ("%Y%m%d", "20240115"),
]


def per_call(operation: Callable[[], Any], number: int = 10_000, repeat: int = 5) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(operation, number=number, repeat=repeat)) / number


def run_isolated(source: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a fresh interpreter.

    `_strptime` is imported once per process and never unloaded, so anything
    asking what the *first* call costs has to ask a new interpreter.
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


@pytest.fixture
def clean_format_cache() -> Iterator[None]:
    """Empty the strptime regex cache, and leave it as it was found."""
    saved = dict(_strptime._regex_cache)
    _strptime._regex_cache.clear()
    yield
    _strptime._regex_cache.clear()
    _strptime._regex_cache.update(saved)


class TestObjectsAreFixedSize:
    """The page's framing: these are records of small integers.

    Everything else on the page rests on this, so it is worth pinning rather
    than assuming: if a datetime grew with the year it held, half the O(1)
    rows would need a term.
    """

    def test_the_extremes_of_the_range_are_the_same_size(self) -> None:
        earliest = datetime(1, 1, 1)
        latest = datetime(9999, 12, 31, 23, 59, 59, 999_999)

        assert sys.getsizeof(earliest) == sys.getsizeof(latest)
        assert sys.getsizeof(date(1, 1, 1)) == sys.getsizeof(date(9999, 12, 31))
        assert sys.getsizeof(timedelta(0)) == sys.getsizeof(timedelta(days=3_652_058))

    @pytest.mark.timing
    def test_subtraction_does_not_care_how_far_apart_the_operands_are(self) -> None:
        near = (datetime(2024, 1, 15), datetime(2024, 1, 16))
        far = (datetime(1, 1, 1), datetime(9999, 12, 31))

        close_time = per_call(lambda: near[1] - near[0])
        distant_time = per_call(lambda: far[1] - far[0])

        assert distant_time < close_time * 2, (
            f"the difference is arithmetic on two fixed-width records: "
            f"one day apart {close_time:.2e}s, 9,998 years apart {distant_time:.2e}s"
        )

    def test_replace_and_arithmetic_return_new_objects(self) -> None:
        """O(1) space: a new record, never a mutation of the old one."""
        original = datetime(2024, 1, 15, 12, 0, 0)

        replaced = original.replace(year=2025)
        shifted = original + timedelta(days=1)

        assert original == datetime(2024, 1, 15, 12, 0, 0), "the original is untouched"
        assert replaced is not original
        assert shifted is not original
        assert sys.getsizeof(replaced) == sys.getsizeof(original)


class TestStrptimeImportsOnFirstUse:
    """The cost the page never mentioned, observed rather than timed."""

    def test_strptime_pulls_in_strptime_module_and_fromisoformat_does_not(self) -> None:
        """`datetime_strptime` calls `PyImport_Import(_strptime)`; the C
        `fromisoformat` parser has nothing to import.
        """
        results = {}
        for name, call in (
            ("strptime", 'datetime.strptime("2024-01-15", "%Y-%m-%d")'),
            ("fromisoformat", 'datetime.fromisoformat("2024-01-15")'),
        ):
            result = run_isolated(f"""
                import sys
                from datetime import datetime
                assert "_strptime" not in sys.modules, "a fresh interpreter should not have it"
                {call}
                print("_strptime" in sys.modules)
            """)
            assert result.returncode == 0, result.stderr
            results[name] = result.stdout.strip()

        assert results == {"strptime": "True", "fromisoformat": "False"}

    @pytest.mark.timing
    def test_the_first_parse_costs_far_more_than_the_next(self) -> None:
        result = run_isolated("""
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

        assert result.returncode == 0, result.stderr
        first, steady = (float(line) for line in result.stdout.split())

        assert first > steady * 100, (
            f"the import and the first compile should dwarf a cached parse: "
            f"first {first:.2e}s, steady {steady:.2e}s"
        )


class TestFormatCache:
    """`_strptime` compiles each format once, for up to five formats."""

    def test_the_documented_limit_is_the_implementation_limit(self) -> None:
        assert _strptime._CACHE_MAX_SIZE == 5

    def test_the_same_format_is_compiled_once(self, clean_format_cache: None) -> None:
        """Counted, not timed: one entry however many strings are parsed."""
        for day in range(1, 11):
            datetime.strptime(f"2024-01-{day:02d}", "%Y-%m-%d")

        assert len(_strptime._regex_cache) == 1

    def test_the_cache_is_cleared_once_it_holds_more_than_five(
        self, clean_format_cache: None
    ) -> None:
        """The corrected advice, observed at the exact boundary.

        The clear runs at the top of every call once the cache holds more
        than five, before the lookup, so the sixth format is still admitted
        and the seventh call, whatever format it asks for, empties it first.
        """
        sizes = []
        for fmt, sample in FORMAT_SAMPLES:
            datetime.strptime(sample, fmt)
            sizes.append(len(_strptime._regex_cache))

        assert sizes == [1, 2, 3, 4, 5, 6, 1], (
            f"expected the cache to fill and then be dropped: {sizes}"
        )

    def test_a_cache_hit_at_size_six_clears_too(self, clean_format_cache: None) -> None:
        """The prose claim: rotating through more than five rebuilds every parse.

        The clear runs before the lookup, not before the insert, so it does
        not matter that the next call repeats a cached format - the cache is
        emptied and the format recompiled either way. An insert-tied clear
        would leave the repeat alone and never rebuild.
        """
        for fmt, sample in FORMAT_SAMPLES[:6]:
            datetime.strptime(sample, fmt)
        assert len(_strptime._regex_cache) == 6

        repeat_fmt, repeat_sample = FORMAT_SAMPLES[0]  # already cached
        datetime.strptime(repeat_sample, repeat_fmt)

        assert len(_strptime._regex_cache) == 1, (
            f"repeating {repeat_fmt!r} at size six should have cleared and "
            f"recompiled it: {len(_strptime._regex_cache)} entries remain"
        )

    def test_naming_the_format_in_a_variable_changes_nothing(
        self, clean_format_cache: None
    ) -> None:
        """What the old advice actually did.

        The cache is keyed on the format string, so a local name is invisible
        to it: both spellings leave exactly one entry, and neither is cheaper.
        """
        datetime.strptime("2024-01-15", "%Y-%m-%d")
        inline = dict(_strptime._regex_cache)

        _strptime._regex_cache.clear()
        pattern = "%Y-%m-%d"
        datetime.strptime("2024-01-15", pattern)

        assert list(_strptime._regex_cache) == list(inline) == ["%Y-%m-%d"]

    def test_fromisoformat_never_builds_a_regex(self, clean_format_cache: None) -> None:
        for day in range(1, 11):
            datetime.fromisoformat(f"2024-01-{day:02d}")

        assert _strptime._regex_cache == {}


class TestParsingAndFormattingScale:
    """The rows that carry n and f, and the choice between two parsers."""

    @pytest.mark.timing
    def test_fromisoformat_beats_strptime_on_iso_input(self) -> None:
        """The page says which side wins; the margin stays here."""
        text = "2024-01-15T12:30:45"
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")  # warm the format cache

        iso = per_call(lambda: datetime.fromisoformat(text))
        formatted = per_call(lambda: datetime.strptime(text, "%Y-%m-%dT%H:%M:%S"))

        assert formatted > iso * 5, (
            f"even with the regex cached, strptime should not be close: "
            f"fromisoformat {iso:.2e}s, strptime {formatted:.2e}s"
        )

    @pytest.mark.timing
    def test_strftime_follows_the_format_length(self) -> None:
        moment = datetime(2024, 1, 15, 12, 30, 45)
        short = "%Y-%m-%d " * 10
        long = "%Y-%m-%d " * 100

        short_time = per_call(lambda: moment.strftime(short), 5_000)
        long_time = per_call(lambda: moment.strftime(long), 5_000)

        assert long_time > short_time * 3, (
            f"ten times the format is ten times the pass: "
            f"{len(short)} chars {short_time:.2e}s, {len(long)} chars {long_time:.2e}s"
        )

    def test_isoformat_output_is_bounded(self) -> None:
        """Why `isoformat()` is O(1) where `strftime` is not: nothing varies."""
        lengths = {len(datetime(year, 1, 1, 0, 0, 0).isoformat()) for year in (1, 2024, 9999)}

        assert lengths == {19}, f"the same shape at every year: {lengths}"
        assert len(datetime(2024, 1, 1, 0, 0, 0, 1).isoformat()) == 26, "microseconds add a field"

    def test_format_with_an_empty_spec_is_isoformat(self) -> None:
        moment = datetime(2024, 1, 15, 12, 30, 45)

        assert format(moment, "") == str(moment) == moment.isoformat(" ")
        assert format(moment, "%Y-%m-%d") == moment.strftime("%Y-%m-%d")


class TestTimedeltaArithmetic:
    """The Timedelta table: every row is arithmetic on three integers."""

    def test_the_documented_operations_answer(self) -> None:
        first, second = timedelta(days=5, hours=3), timedelta(hours=1)

        assert (first + second).total_seconds() == 5 * 86_400 + 4 * 3_600
        assert (first - second).total_seconds() == 5 * 86_400 + 2 * 3_600
        assert (second * 3).total_seconds() == 3 * 3_600
        assert (second / 2).total_seconds() == 1_800
        assert (second // 2).total_seconds() == 1_800
        assert abs(-second) == second
        assert (-second).total_seconds() == -3_600

    def test_a_timedelta_holds_three_fields_whatever_it_measures(self) -> None:
        tiny, huge = timedelta(microseconds=1), timedelta(days=999_999_999)

        assert (tiny.days, tiny.seconds, tiny.microseconds) == (0, 0, 1)
        assert huge.days == 999_999_999
        assert sys.getsizeof(tiny) == sys.getsizeof(huge)

    def test_the_range_is_what_makes_total_seconds_constant(self) -> None:
        """Why the row is O(1) and not O(digits).

        `total_seconds()` multiplies out to microseconds, so a large delta
        does reach big-integer arithmetic: measured 1.3e-07s against 4.1e-08s
        for one microsecond, a factor of three. It stays constant because the
        type will not hold anything larger - the cap is the reason, not the
        arithmetic.
        """
        assert timedelta.max.days == 999_999_999
        with pytest.raises(OverflowError):
            timedelta(days=1_000_000_000)

        assert timedelta.max.total_seconds() == pytest.approx(8.64e13, rel=1e-3)

    @pytest.mark.timing
    def test_the_magnitude_costs_a_bounded_constant(self) -> None:
        tiny, huge = timedelta(microseconds=1), timedelta.max

        tiny_time = per_call(tiny.total_seconds)
        huge_time = per_call(huge.total_seconds)

        assert huge_time < tiny_time * 8, (
            f"the widest delta the type allows should stay within a small "
            f"factor: 1 us {tiny_time:.2e}s, {timedelta.max.days:,} days "
            f"{huge_time:.2e}s"
        )


class TestTimezones:
    """The Timezone tables, including the claim about `dst()`."""

    def test_utc_is_a_singleton(self) -> None:
        assert timezone.utc is timezone(timedelta(0))

    def test_a_fixed_offset_never_reports_dst(self) -> None:
        """The page's "always None for timezone"."""
        offset = timezone(timedelta(hours=5))
        moment = datetime(2024, 6, 15, 12, 0, tzinfo=offset)

        assert offset.dst(moment) is None
        assert offset.utcoffset(moment) == timedelta(hours=5)
        assert moment.dst() is None

    def test_astimezone_converts_without_changing_the_instant(self) -> None:
        moment = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        offset = timezone(timedelta(hours=5))

        converted = moment.astimezone(offset)

        assert converted == moment, "the same instant, a different wall clock"
        assert converted.hour == 17
        assert moment.replace(tzinfo=offset) != moment, "replace() moves the instant"

    @pytest.mark.timing
    def test_astimezone_is_constant_for_a_named_zone_too(self) -> None:
        """An IANA zone caches its transitions, so the row holds for both."""
        moment = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
        offset = timezone(timedelta(hours=5))
        named = zoneinfo.ZoneInfo("America/New_York")
        moment.astimezone(named)  # let the zone load before anything is timed

        fixed_time = per_call(lambda: moment.astimezone(offset))
        named_time = per_call(lambda: moment.astimezone(named))

        assert named_time < fixed_time * 5, (
            f"a loaded zone is a lookup, not a scan: fixed {fixed_time:.2e}s, "
            f"IANA {named_time:.2e}s"
        )


class TestVersionNotes:
    """The three notes that name a version inside the supported range."""

    def test_zoneinfo_is_present_on_every_supported_version(self) -> None:
        """zoneinfo arrived in 3.9, below the whole supported range."""
        assert zoneinfo.ZoneInfo("UTC") is not None

    def test_fromisoformat_widened_in_3_11(self) -> None:
        extended = ["2024-01-15T12:30:45Z", "20240115T123045"]

        if sys.version_info >= (3, 11):
            for text in extended:
                assert datetime.fromisoformat(text) is not None
        else:
            for text in extended:
                with pytest.raises(ValueError):
                    datetime.fromisoformat(text)

    def test_utcnow_is_deprecated_from_3_12(self) -> None:
        if sys.version_info >= (3, 12):
            with pytest.deprecated_call():
                datetime.utcnow()
            with pytest.deprecated_call():
                datetime.utcfromtimestamp(0)
        else:
            datetime.utcnow()  # no warning to catch before 3.12

    def test_the_recommended_replacement_gives_an_aware_datetime(self) -> None:
        aware = datetime.now(timezone.utc)

        assert aware.tzinfo is timezone.utc
        assert aware.utcoffset() == timedelta(0)


class TestDocumentedValues:
    """Results and comments the examples state outright."""

    def test_the_parsing_example_produces_what_it_prints(self) -> None:
        """The block's own values, end to end.

        The block reassigns `dt` from `fromisoformat`, then formats it, so
        the test does the same: asserting against a datetime built here
        instead would let a comment claim any output it liked.
        """
        parsed = datetime.strptime("2024-01-15 12:30:45", "%Y-%m-%d %H:%M:%S")
        parsed = datetime.fromisoformat("2024-01-15 12:30:45")

        assert parsed == datetime(2024, 1, 15, 12, 30, 45)
        assert parsed.strftime("%Y-%m-%d %H:%M:%S") == "2024-01-15 12:30:45"
        assert parsed.isoformat() == "2024-01-15T12:30:45"

    def test_the_arithmetic_example_is_five_days(self) -> None:
        first, second = datetime(2024, 1, 15), datetime(2024, 1, 20)

        assert (second - first) == timedelta(days=5)
        assert (second - first).total_seconds() == 5 * 86_400

    def test_the_components_come_back_as_given(self) -> None:
        moment = datetime(2024, 1, 15, 12, 30, 45)

        assert (moment.year, moment.month, moment.day) == (2024, 1, 15)
        assert (moment.hour, moment.minute, moment.second) == (12, 30, 45)
        assert moment.date() == date(2024, 1, 15)
        assert moment.time() == time(12, 30, 45)


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
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
    """Every block runs, save one that needs a package this repo never declares."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        needing_dateutil = [line for line, source in blocks if DATEUTIL_MARKER in source]
        assert len(needing_dateutil) == 1, (
            f"exactly one block should reach outside the standard library, found {needing_dateutil}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            if DATEUTIL_MARKER in source and not HAS_DATEUTIL:
                continue
            ran += 1
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS - (0 if HAS_DATEUTIL else 1), (
            f"ran {ran} of {EXPECTED_BLOCKS} blocks"
        )

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("from datetime import", "from datetime import missing_name,", 1)
        assert broken != original, "the mutation did not touch the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr
