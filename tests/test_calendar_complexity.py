"""Tests for docs/stdlib/calendar.md.

The page prices the module as O(1) with default arguments because a month grid
never exceeds six weeks and a year is twelve months; only the text layout
arguments `w`, `l` and `c` grow a result. The fixed ceiling is settled by
exhausting the Gregorian cycle, the layout terms by output length and timing
tests, and the rest by observation: call counters on `setlocale()`,
`strftime()` and `formatmonthname()`, identity and type checks, and exceptions.

Measurement scope:

* Every month of the 400-year Gregorian cycle, 2000-2399, under each of the
  seven first weekdays: `monthdayscalendar()` has four to six rows of seven
  (all three lengths occur), and `itermonthdays()` yields seven times as many
  days as there are rows. `monthdays2calendar()` and `monthdatescalendar()`
  have the same shape on each month of 2024. The year grids hold twelve
  months, grouped `width` to a row for every width from 1 to 12.
* `leapdays()` equals the sum of `isleap()` over 1900-2100, 1-2025 and
  -400-400. A timing test compares a ten-year span with a billion-year one,
  both single-digit ints: the ratio stays under 3, where a loop over the range
  would give about 10^8.
* `weekday()` for years 12024, 0 and -399 matches the year congruent to it
  modulo 400 inside 1-9999. `timegm()` inverts `time.gmtime()` for timestamps from
  -10^9 to 4*10^9.
* Output length, from 100 to 10,000 in each argument: `formatmonth()`
  grows over 50x for `w` and for `l`; `formatyear()` over 50x for `w` and
  `l` and over 20x for `c`. Timing tests on `formatmonth()` give over 5x for
  100x `w` (1,000 to 100,000) and over 4x for 1,000x `l` (1,000 to
  1,000,000). `w=0, l=0` renders the same as `w=2, l=1`.
* `formatyear()` is observed to call `formatmonthname()` exactly twelve
  times for every `m` from 1 to 12, and its non-blank characters are the same
  multiset for every `m`, so `m` changes only the layout.
* `setfirstweekday()` is observed to change `monthcalendar()`,
  `weekheader()`, `month()`, `calendar()`, `prmonth()` and `prcal()`, and
  to raise `IllegalWeekdayError` for -1 and 7; `Calendar(9)` reads
  back as 2, and `setfirstweekday(-1)` on an instance as 6.
* The locale classes are observed through a counting `locale.setlocale`:
  an explicit locale makes no call at construction, and `locale=None` is
  resolved there, a query of `LC_TIME` being observed from 3.11 (3.10 reads
  the environment through `locale.getdefaultlocale()`, per Lib/calendar.py). Each `formatweekday()` and `formatmonthname()` sets `LC_TIME` to
  the calendar's locale exactly once and sets it back once, leaving it as it
  was, so a text or HTML month switches it eight times. `day_name`, `day_abbr`,
  `month_name` and `month_abbr` are observed through counting wrappers
  substituted for their per-index formatters: every index access and every
  slice element calls one again.
* `itermonthdays2()` and `monthdays2calendar()` are observed through a
  counting `calendar.weekday` to call it once per month, for the 1st, and
  their weekdays match `weekday()` for every day of 2024. The iterators are
  generators; `itermonthdates()` raises `ValueError` for
  December 9999 and, Sunday first, January of year 1, while the four
  `itermonthdays` variants complete both.
* `IllegalMonthError` is asserted from `monthrange()` and every
  month-taking `Calendar` method for months 0 and 13, on every supported
  version. The enums, the 3.12 constants, `weekday()` returning a `Day`, and
  the `January`/`February` deprecation warnings are guarded on
  `sys.version_info`, and the plain-int weekday constants on the versions
  before.
* Every fenced Python block runs in its own subprocess, so the module-level
  first weekday and the locale cannot leak between them, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Treating years as machine-size integers is a cost-model assumption: the
  fold of a year outside 1-9999 into the 400-year cycle costs O(digits) for a
  big integer, and is not varied.
* That the localized names follow a change of `LC_TIME` is read from
  Lib/calendar.py, where each name lookup calls `strftime()`. Only the C and POSIX
  locales are assumed installed, and they name days identically, so the tests
  show the per-access call rather than a changed name. The cost of
  `setlocale()` and `strftime()` depends on the C library and is priced O(1).
* The Space bounds of the text formatters are settled by the length of what
  they return; the peak allocation while building it is not traced.
* The time bounds for `w`, `l` and `c` in `formatyear()`, and for `c` in
  `calendar()` and `prcal()`, are read from Lib/calendar.py's per-cell
  `str.center()` and per-line joins; only `formatmonth()` is timed. `m` above
  12 widens the centered year title before it is stripped, and is outside the
  bounds.
* `calendar.main()` (the `python -m calendar` interface), `different_locale`,
  `format()`, `formatstring()`, `mdays` and the shared calendar `c` are not
  in the module's documented API and are left off the page.
* That the locale classes are not thread-safe follows from `LC_TIME` being
  process-wide, as the official documentation states; no concurrent run is
  attempted.
* CSS class names and caller-supplied week lists are taken at their normal
  sizes; their lengths are not varied.
"""

from __future__ import annotations

import calendar
import datetime
import enum
import inspect
import locale
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "calendar.md"
EXPECTED_BLOCKS = 11
# A locale name; typeshed accepts only a (language, encoding) tuple.
C_LOCALE: Any = "C"


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


@pytest.fixture
def restore_first_weekday() -> Iterator[None]:
    original = calendar.firstweekday()
    yield
    calendar.setfirstweekday(original)


class TestGridsHaveAFixedCeiling:
    """Every grid row is O(1): four to six weeks of seven days a month,
    twelve months a year."""

    def test_every_month_of_the_cycle_is_four_to_six_weeks(self) -> None:
        lengths: Counter[int] = Counter()
        for first in range(7):
            cal = calendar.Calendar(first)
            for year in range(2000, 2400):
                for month in range(1, 13):
                    weeks = cal.monthdayscalendar(year, month)
                    assert all(len(week) == 7 for week in weeks)
                    assert len(list(cal.itermonthdays(year, month))) == 7 * len(weeks)
                    lengths[len(weeks)] += 1

        assert set(lengths) == {4, 5, 6}, lengths

    def test_the_pair_and_date_grids_have_the_same_shape(self) -> None:
        cal = calendar.Calendar()
        for month in range(1, 13):
            shape = [len(week) for week in cal.monthdayscalendar(2024, month)]
            assert [len(week) for week in cal.monthdays2calendar(2024, month)] == shape
            assert [len(week) for week in cal.monthdatescalendar(2024, month)] == shape

    @pytest.mark.parametrize("width", range(1, 13))
    def test_year_grids_hold_twelve_months_width_to_a_row(self, width: int) -> None:
        cal = calendar.Calendar()
        for grid in (
            cal.yeardayscalendar(2024, width),
            cal.yeardays2calendar(2024, width),
            cal.yeardatescalendar(2024, width),
        ):
            expected = [min(width, 12 - start) for start in range(0, 12, width)]
            assert [len(row) for row in grid] == expected

    def test_the_module_function_is_the_shared_grid(self, restore_first_weekday: None) -> None:
        calendar.setfirstweekday(calendar.MONDAY)

        assert calendar.monthcalendar(2024, 2) == calendar.Calendar().monthdayscalendar(2024, 2)
        assert calendar.monthcalendar(2024, 2)[0] == [0, 0, 0, 1, 2, 3, 4]


class TestIterators:
    """The `itermonth*` rows: lazy, padded to whole weeks, differing only in
    what they yield; `itermonthdates()` is bound by `datetime`'s range."""

    NAMES = ["itermonthdays", "itermonthdays2", "itermonthdays3", "itermonthdays4"]

    @pytest.mark.parametrize("name", [*NAMES, "itermonthdates"])
    def test_each_is_a_generator(self, name: str) -> None:
        assert inspect.isgenerator(getattr(calendar.Calendar(), name)(2024, 2))

    def test_what_each_yields_for_one_padding_day_and_one_month_day(self) -> None:
        cal = calendar.Calendar()

        assert list(cal.itermonthdays(2024, 2))[2:4] == [0, 1]
        assert list(cal.itermonthdays2(2024, 2))[2:4] == [(0, 2), (1, 3)]
        assert list(cal.itermonthdays3(2024, 2))[2:4] == [(2024, 1, 31), (2024, 2, 1)]
        assert list(cal.itermonthdays4(2024, 2))[2:4] == [(2024, 1, 31, 2), (2024, 2, 1, 3)]
        assert list(cal.itermonthdates(2024, 2))[3] == datetime.date(2024, 2, 1)

    @pytest.mark.parametrize("name", ["itermonthdays2", "monthdays2calendar"])
    def test_the_pairs_cost_one_weekday_per_month(
        self, name: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[int, int, int]] = []
        original = calendar.weekday

        def counting(year: int, month: int, day: int) -> Any:
            calls.append((year, month, day))
            return original(year, month, day)

        monkeypatch.setattr(calendar, "weekday", counting)
        result = list(getattr(calendar.Calendar(), name)(2024, 3))

        assert result
        assert calls == [(2024, 3, 1)]

    def test_the_pairs_agree_with_weekday(self) -> None:
        cal = calendar.Calendar(3)
        for month in range(1, 13):
            grid = [pair for week in cal.monthdays2calendar(2024, month) for pair in week]
            assert grid == list(cal.itermonthdays2(2024, month))
            for day, wd in grid:
                if day:
                    assert wd == calendar.weekday(2024, month, day)

    def test_iterweekdays_starts_at_firstweekday(self) -> None:
        assert list(calendar.Calendar(3).iterweekdays()) == [3, 4, 5, 6, 0, 1, 2]

    @pytest.mark.parametrize(("year", "month", "first"), [(9999, 12, 0), (1, 1, 6)])
    def test_itermonthdates_raises_beyond_datetime_s_range(
        self, year: int, month: int, first: int
    ) -> None:
        cal = calendar.Calendar(first)

        with pytest.raises(ValueError):
            list(cal.itermonthdates(year, month))
        for name in self.NAMES:
            assert len(list(getattr(cal, name)(year, month))) % 7 == 0

    def test_the_day_variants_carry_on_past_the_range(self) -> None:
        assert list(calendar.Calendar().itermonthdays3(9999, 12))[-1] == (10000, 1, 2)
        assert next(calendar.Calendar(6).itermonthdays3(1, 1)) == (0, 12, 31)


class TestArithmeticFunctions:
    """`isleap`, `leapdays`, `weekday`, `monthrange` and `timegm` are O(1);
    `leapdays` never visits its range and `weekday` folds foreign years."""

    @pytest.mark.parametrize(("start", "stop"), [(1900, 2101), (1, 2026), (-400, 401)])
    def test_leapdays_matches_counting_isleap(self, start: int, stop: int) -> None:
        assert calendar.leapdays(start, stop) == sum(map(calendar.isleap, range(start, stop)))

    @pytest.mark.timing
    def test_leapdays_costs_the_same_for_any_span(self) -> None:
        short = best_ns(lambda: calendar.leapdays(1, 11), inner=1_000)
        huge = best_ns(lambda: calendar.leapdays(1, 1_000_000_001), inner=1_000)

        ratio = huge / short
        assert ratio < 3, f"10 years took {short:.0f}ns, 10^9 took {huge:.0f}ns (x{ratio:.2f})"

    @pytest.mark.parametrize("year", [12024, 0, -399])
    def test_weekday_folds_years_outside_datetime_s_range(self, year: int) -> None:
        inside = 2000 + year % 400
        for month, day in [(1, 1), (3, 1), (12, 31)]:
            assert calendar.weekday(year, month, day) == calendar.weekday(inside, month, day)

    def test_monthrange_returns_the_first_weekday_and_the_length(self) -> None:
        assert calendar.monthrange(2024, 2) == (calendar.THURSDAY, 29)
        assert calendar.monthrange(2023, 2) == (calendar.WEDNESDAY, 28)

    @pytest.mark.parametrize("stamp", [-1_000_000_000, 0, 1_700_000_000, 4_000_000_000])
    def test_timegm_inverts_gmtime(self, stamp: int) -> None:
        assert calendar.timegm(time.gmtime(stamp)) == stamp


class TestFirstWeekday:
    """The module functions share one calendar that `setfirstweekday()`
    changes; an instance reads its own setting modulo 7, unchecked."""

    def test_setfirstweekday_changes_every_shared_layout(
        self, restore_first_weekday: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calendar.setfirstweekday(calendar.SUNDAY)

        assert calendar.firstweekday() == calendar.SUNDAY
        assert calendar.monthcalendar(2024, 9)[0][0] == 1
        assert calendar.weekheader(2).startswith("Su")
        assert calendar.month(2024, 9).splitlines()[1].startswith("Su")
        assert calendar.calendar(2024).splitlines()[3].startswith("Su")
        calendar.prmonth(2024, 9)
        assert capsys.readouterr().out.splitlines()[1].startswith("Su")
        calendar.prcal(2024)
        assert capsys.readouterr().out.splitlines()[3].startswith("Su")

    @pytest.mark.parametrize("bad", [-1, 7])
    def test_setfirstweekday_rejects_out_of_range(
        self, bad: int, restore_first_weekday: None
    ) -> None:
        with pytest.raises(calendar.IllegalWeekdayError) as caught:
            calendar.setfirstweekday(bad)

        assert caught.value.weekday == bad
        assert isinstance(caught.value, ValueError)

    def test_an_instance_reads_its_setting_modulo_seven(self) -> None:
        cal = calendar.Calendar(9)

        assert cal.firstweekday == cal.getfirstweekday() == 2
        cal.setfirstweekday(-1)
        assert cal.firstweekday == 6
        cal.firstweekday = 0
        assert list(cal.iterweekdays())[0] == 0


class TestTextLayoutGrows:
    """`TextCalendar` rows: O(w) per cell and week, O(w + l) per month and
    O(w + c + l) per year; `m` changes the layout, not the number of months
    formatted."""

    text = calendar.TextCalendar()

    def test_the_cell_level_formatters_are_width_wide(self) -> None:
        assert self.text.formatday(5, 0, 6) == "   5  "
        assert self.text.formatday(0, 0, 4) == "    "
        # typeshed types the week argument as int; it is a list of (day, weekday) pairs.
        week: Any = calendar.Calendar().monthdays2calendar(2024, 2)[1]
        assert len(self.text.formatweek(week, 5)) == 7 * 5 + 6
        assert calendar.week(week, 5) == self.text.formatweek(week, 5)
        assert len(calendar.weekheader(4)) == 7 * 4 + 6
        assert len(self.text.formatmonthname(2024, 2, 40)) == 40

    def test_formatweekday_uses_the_full_name_from_width_nine(self) -> None:
        assert self.text.formatweekday(2, 9) == "Wednesday"
        assert self.text.formatweekday(2, 8) == "  Wed   "
        assert self.text.formatweekday(2, 2) == "We"
        assert self.text.formatweekheader(3).split() == list(calendar.day_abbr)

    def test_widths_below_the_minimum_are_raised(self) -> None:
        assert self.text.formatmonth(2024, 2, 0, 0) == self.text.formatmonth(2024, 2, 2, 1)

    @pytest.mark.parametrize("argument", ["w", "l"])
    def test_formatmonth_output_follows_w_and_l(self, argument: str) -> None:
        small = self.text.formatmonth(2024, 2, **{argument: 100})
        large = self.text.formatmonth(2024, 2, **{argument: 10_000})

        assert len(large) > 50 * len(small), (argument, len(small), len(large))

    @pytest.mark.parametrize(("argument", "factor"), [("w", 50), ("c", 20), ("l", 50)])
    def test_formatyear_output_follows_w_c_and_l(self, argument: str, factor: int) -> None:
        small = self.text.formatyear(2024, **{argument: 100})
        large = self.text.formatyear(2024, **{argument: 10_000})

        assert len(large) > factor * len(small), (argument, len(small), len(large))

    @pytest.mark.parametrize("m", range(1, 13))
    def test_m_formats_every_month_once(self, m: int) -> None:
        names: list[int] = []

        class Counting(calendar.TextCalendar):
            def formatmonthname(self, *args: Any, **kwargs: Any) -> str:
                names.append(args[1])
                return super().formatmonthname(*args, **kwargs)

        rendered = Counting().formatyear(2024, m=m)

        assert names == list(range(1, 13))
        default = self.text.formatyear(2024)
        assert Counter(rendered.replace(" ", "").replace("\n", "")) == Counter(
            default.replace(" ", "").replace("\n", "")
        )

    @pytest.mark.timing
    def test_formatmonth_time_follows_w(self) -> None:
        durations = [
            best_ns(lambda w=w: self.text.formatmonth(2024, 2, w=w), inner=3)  # type: ignore[misc]
            for w in (1_000, 100_000)
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 5, f"100x w: {durations} ns, x{ratio:.2f}"

    @pytest.mark.timing
    def test_formatmonth_time_follows_l(self) -> None:
        durations = [
            best_ns(lambda l=l: self.text.formatmonth(2024, 2, l=l), inner=3)  # type: ignore[misc]  # noqa: E741
            for l in (1_000, 1_000_000)  # noqa: E741
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 4, f"1,000x l: {durations} ns, x{ratio:.2f}"


class TestPrintingFunctions:
    """The `pr*` rows print exactly what their `format*` counterparts return."""

    def test_each_prints_its_formatter(
        self, restore_first_weekday: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calendar.setfirstweekday(calendar.MONDAY)
        text = calendar.TextCalendar()
        week: Any = text.monthdays2calendar(2024, 2)[0]
        cases: list[tuple[Callable[[], None], str]] = [
            (lambda: calendar.prweek(week, 3), calendar.week(week, 3)),
            (lambda: calendar.prmonth(2024, 2), calendar.month(2024, 2)),
            (lambda: calendar.prcal(2024), calendar.calendar(2024)),
            (lambda: text.prweek(week, 3), text.formatweek(week, 3)),
            (lambda: text.prmonth(2024, 2), text.formatmonth(2024, 2)),
            (lambda: text.pryear(2024), text.formatyear(2024)),
        ]
        for printer, expected in cases:
            printer()
            assert capsys.readouterr().out == expected

    def test_the_module_functions_are_the_default_text_calendar(
        self, restore_first_weekday: None
    ) -> None:
        calendar.setfirstweekday(calendar.MONDAY)
        text = calendar.TextCalendar()

        assert calendar.month(2024, 2) == text.formatmonth(2024, 2)
        assert calendar.calendar(2024) == text.formatyear(2024)
        assert calendar.weekheader(2) == text.formatweekheader(2)


class TestHTMLCalendar:
    """`HTMLCalendar` writes a fixed set of elements; the CSS class names are
    read as each one is written."""

    html = calendar.HTMLCalendar()

    def test_the_element_formatters(self) -> None:
        assert self.html.formatday(0, 0) == '<td class="noday">&nbsp;</td>'
        assert self.html.formatday(5, 4) == '<td class="fri">5</td>'
        week: Any = self.html.monthdays2calendar(2024, 2)[0]
        assert self.html.formatweek(week).count("<td") == 7
        assert self.html.formatweekday(0) == '<th class="mon">Mon</th>'
        assert self.html.formatweekheader().count("<th") == 7
        assert "February 2024" in self.html.formatmonthname(2024, 2)
        assert "2024" not in self.html.formatmonthname(2024, 2, withyear=False)

    @pytest.mark.parametrize("width", [1, 3, 5, 12])
    def test_formatyear_has_twelve_month_tables_width_to_a_row(self, width: int) -> None:
        year = self.html.formatyear(2024, width)

        assert year.count('class="month"') == 2 * 12  # each table and its heading row
        assert year.count("<tr><td>") == -(-12 // width)

    def test_formatyearpage_returns_encoded_bytes(self) -> None:
        page = self.html.formatyearpage(2024, encoding="ascii")

        assert isinstance(page, bytes)
        assert b'encoding="ascii"' in page
        assert b'href="calendar.css"' in page
        assert b"<link" not in self.html.formatyearpage(2024, css=None)

    def test_css_class_attributes_can_be_overridden_on_an_instance(self) -> None:
        styled: Any = calendar.HTMLCalendar()  # typeshed declares these ClassVar
        styled.cssclass_noday = "empty"
        styled.cssclasses = ["d0", "d1", "d2", "d3", "d4", "d5", "d6"]
        styled.cssclasses_weekday_head = ["h0", "h1", "h2", "h3", "h4", "h5", "h6"]
        styled.cssclass_month = "m"
        styled.cssclass_month_head = "mh"
        styled.cssclass_year = "y"
        styled.cssclass_year_head = "yh"

        year = styled.formatyear(2024)

        for fragment in ['class="empty"', 'class="d3"', 'class="h0"', 'class="m"', 'class="mh"']:
            assert fragment in year
        assert year.startswith('<table border="0" cellpadding="0" cellspacing="0" class="y">')
        assert 'class="yh"' in year
        assert 'class="empty"' not in self.html.formatyear(2024)


class TestLocaleCalendarsSwitchLCTime:
    """The locale classes set `LC_TIME` to their locale once per name
    formatted and restore it; `locale=None` is resolved at construction."""

    @pytest.fixture
    def setlocale_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
        calls: list[tuple[Any, ...]] = []
        original = locale.setlocale

        def counting(*args: Any) -> str:
            calls.append(args)
            return original(*args)

        monkeypatch.setattr(locale, "setlocale", counting)
        return calls

    @staticmethod
    def sets(calls: list[tuple[Any, ...]]) -> list[Any]:
        """The values `LC_TIME` was set to, in order, leaving out queries."""
        return [args[1] for args in calls if len(args) == 2 and args[1] is not None]

    @pytest.mark.parametrize("cls", [calendar.LocaleTextCalendar, calendar.LocaleHTMLCalendar])
    def test_an_explicit_locale_costs_nothing_to_construct(
        self, cls: type, setlocale_calls: list[tuple[Any, ...]]
    ) -> None:
        cls(locale=C_LOCALE)

        assert setlocale_calls == []

    @pytest.mark.parametrize("cls", [calendar.LocaleTextCalendar, calendar.LocaleHTMLCalendar])
    def test_the_default_locale_is_read_at_construction(
        self, cls: type, setlocale_calls: list[tuple[Any, ...]]
    ) -> None:
        cal = cls()

        assert cal.locale is not None
        if sys.version_info >= (3, 11):
            # 3.10 reads the environment through locale.getdefaultlocale() instead.
            assert (locale.LC_TIME, None) in setlocale_calls

    def test_each_name_switches_once_and_restores(
        self, setlocale_calls: list[tuple[Any, ...]]
    ) -> None:
        before = locale.setlocale(locale.LC_TIME)
        text = calendar.LocaleTextCalendar(locale=C_LOCALE)
        html = calendar.LocaleHTMLCalendar(locale=C_LOCALE)
        cases: list[tuple[Callable[[], Any], int]] = [
            (lambda: text.formatweekday(0, 9), 1),
            (lambda: text.formatmonthname(2024, 2, 20), 1),
            (lambda: html.formatweekday(0), 1),
            (lambda: html.formatmonthname(2024, 2), 1),
            (lambda: text.formatmonth(2024, 2), 8),
            (lambda: html.formatmonth(2024, 2), 8),
        ]
        for call, names in cases:
            setlocale_calls.clear()
            call()
            sets = self.sets(setlocale_calls)
            assert sets[0::2] == ["C"] * names
            assert len(sets) == 2 * names  # each switch is undone
            assert locale.setlocale(locale.LC_TIME) == before

    def test_the_names_are_those_of_the_locale(self) -> None:
        text = calendar.LocaleTextCalendar(locale=C_LOCALE)

        assert text.formatmonthname(2024, 2, 20).strip() == "February 2024"
        assert text.formatweekday(0, 9) == "  Monday "


class TestNamesAreFormattedPerAccess:
    """`day_name`, `day_abbr`, `month_name`, `month_abbr`: each index runs
    the formatter again; nothing is stored."""

    @pytest.mark.parametrize(
        ("sequence", "holder", "table", "index"),
        [
            (calendar.day_name, "_localized_day", "_days", 0),
            (calendar.day_abbr, "_localized_day", "_days", 4),
            (calendar.month_name, "_localized_month", "_months", 1),
            (calendar.month_abbr, "_localized_month", "_months", 12),
        ],
    )
    def test_every_access_calls_the_formatter(
        self, sequence: Any, holder: str, table: str, index: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The per-index formatters are private; substituting counting wrappers
        # is where the per-access call shows.
        cls = getattr(calendar, holder)
        calls: list[int] = []

        def wrap(position: int, formatter: Callable[[str], str]) -> Callable[[str], str]:
            def counted(spec: str) -> str:
                calls.append(position)
                return formatter(spec)

            return counted

        wrapped = [wrap(position, f) for position, f in enumerate(getattr(cls, table))]
        monkeypatch.setattr(cls, table, wrapped)

        first = sequence[index]
        second = sequence[index]
        assert first == second
        assert calls == [index, index]
        calls.clear()
        assert len(sequence[:3]) == 3
        assert calls == [0, 1, 2]

    def test_the_sequences(self) -> None:
        assert len(calendar.day_name) == len(calendar.day_abbr) == 7
        assert len(calendar.month_name) == len(calendar.month_abbr) == 13
        assert calendar.month_name[0] == calendar.month_abbr[0] == ""
        assert list(calendar.day_name)[6] == "Sunday"
        assert list(calendar.month_abbr)[12] == "Dec"


DAY_NAMES = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
MONTH_NAMES = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
]


class TestConstants:
    """The weekday constants everywhere; `Day`, `Month` and the month
    constants from 3.12."""

    def test_weekday_constants_are_zero_to_six(self) -> None:
        assert [getattr(calendar, name) for name in DAY_NAMES] == list(range(7))

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="Day members from 3.12")
    def test_weekday_constants_are_plain_ints_before_312(self) -> None:
        assert all(type(getattr(calendar, name)) is int for name in DAY_NAMES)
        assert type(calendar.weekday(2024, 1, 1)) is int
        assert not hasattr(calendar, "Month")

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_the_enums_and_month_constants(self) -> None:
        day = calendar.Day  # type: ignore[attr-defined]
        month = calendar.Month  # type: ignore[attr-defined]

        assert all(getattr(calendar, name) is day[name] for name in DAY_NAMES)
        assert [getattr(calendar, name) for name in MONTH_NAMES] == list(range(1, 13))
        assert all(getattr(calendar, name) is month[name] for name in MONTH_NAMES)
        assert type(calendar.weekday(2024, 1, 1)) is day
        assert issubclass(day, enum.IntEnum) and issubclass(month, enum.IntEnum)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="deprecated in 3.12")
    def test_january_and_february_are_deprecated(self) -> None:
        with pytest.warns(DeprecationWarning, match="JANUARY"):
            assert calendar.January == 1  # type: ignore[attr-defined]
        with pytest.warns(DeprecationWarning, match="FEBRUARY"):
            assert calendar.February == 2  # type: ignore[attr-defined]


class TestIllegalMonths:
    """`IllegalMonthError` is a `ValueError` raised by `monthrange()` and the
    `Calendar` methods for a month outside 1-12."""

    METHODS = [
        "itermonthdays",
        "itermonthdays2",
        "itermonthdays3",
        "itermonthdays4",
        "itermonthdates",
        "monthdayscalendar",
        "monthdays2calendar",
        "monthdatescalendar",
    ]

    @pytest.mark.parametrize("bad", [0, 13])
    def test_monthrange_raises_it(self, bad: int) -> None:
        with pytest.raises(calendar.IllegalMonthError) as caught:
            calendar.monthrange(2024, bad)

        assert caught.value.month == bad
        assert isinstance(caught.value, ValueError)
        assert f"bad month number {bad}" in str(caught.value)

    @pytest.mark.parametrize("bad", [0, 13])
    @pytest.mark.parametrize("name", METHODS)
    def test_every_calendar_method_raises_it(self, name: str, bad: int) -> None:
        with pytest.raises(calendar.IllegalMonthError):
            list(getattr(calendar.Calendar(), name)(2024, bad))


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
    """Each block runs in its own subprocess, so the module-level first
    weekday and the locale cannot leak between them, and asserts its own
    result."""

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
        needle = "assert by_loop == by_formula == 49"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "assert by_loop == by_formula == 48", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
