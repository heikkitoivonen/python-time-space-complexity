"""Tests for docs/stdlib/locale.md.

The page prices the module in two halves: calls that go to the C library
(settings, collation, `nl_langinfo()`, the message catalogue functions) and
number formatting written in Python over `localeconv()`. The C-library bounds
are settled by traced allocation and by timing across input sizes; the Python
half by call counters on the helpers it goes through and by conventions
substituted for `localeconv()`, which lets the grouping and decimal-point
paths run where no locale but C is installed. Every test restores the
process locale it started with.

Measurement scope:

* `setlocale(category)` is asserted to return the same name twice and to
  change nothing; a missing locale raises `locale.Error` and leaves the
  category as it was; a setting made in another thread is visible in the
  main thread. A `(language, encoding)` tuple is observed to call
  `normalize()` once and a string not at all.
* `getlocale()` is observed, through a counting `locale._setlocale`, to make
  exactly one query, and returns `(None, None)` for the C locale. With
  `LC_CTYPE` set apart from the other categories, `getlocale(LC_ALL)` raises
  `TypeError` (needs `C.UTF-8`; skipped where it is not installed).
* `normalize()` is run against a counting stand-in for `locale_alias`: a known
  name, a name with an encoding and a modifier, and an unknown name each
  make at most four lookups, and an entry added to the table is what it
  returns.
* `getpreferredencoding()` runs in subprocesses with `-X utf8=1` and
  `-X utf8=0` and a counting `setlocale`: UTF-8 mode returns UTF-8 with no
  call, `do_setlocale=False` makes none, and `do_setlocale=True` without UTF-8
  mode sets `LC_CTYPE` and restores it. `getencoding()` makes no call
  (3.11+). `getdefaultlocale()` leaves every category unchanged; it warns
  `DeprecationWarning` on 3.11 through 3.14.6 and not on 3.10 or 3.14.7
  (checked on 3.10.21, 3.11.16, 3.12, 3.13.14, 3.14.2, and 3.14.4 to 3.14.7).
* `localeconv()` returns a new dictionary on each call, with the same keys in
  the C locale and in `C.UTF-8`; in the C locale `frac_digits` is `CHAR_MAX`.
  Where `CHAR_MAX` is 127, `currency()` is asserted to raise `ValueError`
  there; where it is 255 (unsigned `char`, as on aarch64 Linux) the check in
  Lib/locale.py does not match, so that branch is skipped.
* `strcoll()` compares strings that differ in their first character: from
  1,000 to 1,000,000 characters the traced peak grows between 500x and
  5,000x, and in a timing test time grows more than 100x, where a comparison
  that stopped at the first difference would grow neither. `strxfrm()`'s peak
  grows between 500x and 5,000x over the same sizes. Its keys order as `strcoll()` does on a mixed
  list, and in the C locale an ASCII string is its own key.
* Sorting 2,000 shuffled words is counted: `key=locale.strxfrm` calls it
  exactly 2,000 times, and `cmp_to_key(locale.strcoll)` makes more than
  10,000 comparisons. What each call converts is the `strcoll()` measurement
  above; the two sorts are not timed against each other.
* `format_string()` with 100 and 10,000 `%d` conversions is timed: 100x the
  format costs between 20x and 1,000x, which excludes both a constant and a
  quadratic. `monetary=True` is observed to take `mon_decimal_point` and the
  default `decimal_point` from substituted conventions. With
  `grouping=[3, 0]` substituted, `localize(grouping=True)` on 20,000 and
  200,000 digits is timed: 10x the digits costs more than 25x, where linear
  work would give 10x; without grouping it costs under 30x.
* `atof()`, `atoi()`, `delocalize()` and `localize()` are asserted to round
  trip under substituted German-style conventions and in the C locale;
  `atof(func=Decimal)` returns a `Decimal`. `str()` is asserted to format with
  `'%.12g'`. `currency()` under substituted US conventions gives `'$1,234.50'`
  and `'-$1,234.50'`.
* `nl_langinfo()` answers every key constant with a string, gives the C
  locale's day and month names, empty `ERA` and `ALT_DIGITS`, and raises
  `ValueError` for an unknown key.
* The catalogue functions return the message unchanged under `LC_MESSAGES=C`;
  `textdomain(None)` and `bindtextdomain(domain, None)` return the current
  value without changing it; `bindtextdomain('', ...)` raises `locale.Error`.
* Every fenced Python block runs in its own subprocess, so the locale cannot
  leak between them, and a mutated assertion in one of them is asserted to
  fail.

Not settled here:

* What `setlocale()` costs to select a locale, and what the catalogue
  functions cost to look a message up, are the C library's; the first use of
  a locale or a catalogue loads data from disk. Rows marked "Varies" are that.
* Only `C`, `POSIX` and, where installed, `C.UTF-8` are exercised; other
  locales' conventions are substituted through `locale.localeconv`, which the
  Python formatting functions read. The length of `strxfrm()` keys in a
  locale with multi-level collation is not measured: the O(s) bound for them
  rests on the C library.
* That `'C'` and `'POSIX'` are always available is POSIX's guarantee; that the
  setting is process-wide and `setlocale()` not thread-safe is the Python
  documentation's, as is that `getencoding()` ignores UTF-8 mode; that
  `format()`'s `n` type follows `LC_NUMERIC` is the `string` documentation's.
* `ERA`, `ALT_DIGITS` and non-ASCII conventions, which make `nl_langinfo()` and
  `localeconv()` switch `LC_CTYPE` briefly, need a locale that has them.
* Windows: `windows_locale`, the `_locale._getdefaultlocale()` path of
  `getdefaultlocale()`, and the absence of `nl_langinfo()` and the catalogue
  functions are not run.
"""

from __future__ import annotations

import functools
import locale
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from decimal import Decimal
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "locale.md"
EXPECTED_BLOCKS = 7

LANGINFO_KEYS = [
    "CODESET",
    "D_T_FMT",
    "D_FMT",
    "T_FMT",
    "T_FMT_AMPM",
    "AM_STR",
    "PM_STR",
    "RADIXCHAR",
    "THOUSEP",
    "YESEXPR",
    "NOEXPR",
    "CRNCYSTR",
    "ERA",
    "ERA_D_T_FMT",
    "ERA_D_FMT",
    "ERA_T_FMT",
    "ALT_DIGITS",
    *(f"DAY_{i}" for i in range(1, 8)),
    *(f"ABDAY_{i}" for i in range(1, 8)),
    *(f"MON_{i}" for i in range(1, 13)),
    *(f"ABMON_{i}" for i in range(1, 13)),
]


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


def available(name: str) -> bool:
    """Whether the C library can select `name`; the current setting is kept."""
    previous = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, name)
    except locale.Error:
        return False
    finally:
        locale.setlocale(locale.LC_CTYPE, previous)
    return True


needs_c_utf8 = pytest.mark.skipif(not available("C.UTF-8"), reason="C.UTF-8 is not installed")


@pytest.fixture(autouse=True)
def _restore_locale() -> Iterator[None]:
    saved = locale.setlocale(locale.LC_ALL)
    yield
    locale.setlocale(locale.LC_ALL, saved)


def with_conventions(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    """Make the Python formatting functions see `overrides` in `localeconv()`."""
    original = locale.localeconv

    def patched() -> dict[str, Any]:
        conventions: dict[str, Any] = dict(original())
        conventions.update(overrides)
        return conventions

    monkeypatch.setattr(locale, "localeconv", patched)


GERMAN = {
    "decimal_point": ",",
    "thousands_sep": ".",
    "grouping": [3, 0],
}
US_MONEY = {
    "currency_symbol": "$",
    "int_curr_symbol": "USD ",
    "mon_decimal_point": ".",
    "mon_thousands_sep": ",",
    "mon_grouping": [3, 0],
    "positive_sign": "",
    "negative_sign": "-",
    "frac_digits": 2,
    "int_frac_digits": 2,
    "p_cs_precedes": 1,
    "n_cs_precedes": 1,
    "p_sep_by_space": 0,
    "n_sep_by_space": 0,
    "p_sign_posn": 1,
    "n_sign_posn": 1,
}


class TestSettingsAreProcessWide:
    """`setlocale(category)` queries in O(1); `setlocale(category, locale)`
    selects through the C library for the whole process; `getlocale()` is one
    query."""

    def test_a_query_changes_nothing(self) -> None:
        first = locale.setlocale(locale.LC_NUMERIC)

        assert locale.setlocale(locale.LC_NUMERIC) == first

    def test_setting_c_reads_back_as_no_language(self) -> None:
        assert locale.setlocale(locale.LC_NUMERIC, "C") == "C"
        assert locale.getlocale(locale.LC_NUMERIC) == (None, None)

    def test_posix_is_always_there(self) -> None:
        locale.setlocale(locale.LC_NUMERIC, "POSIX")

        assert locale.localeconv()["decimal_point"] == "."

    def test_a_missing_locale_raises_and_changes_nothing(self) -> None:
        locale.setlocale(locale.LC_NUMERIC, "C")

        with pytest.raises(locale.Error, match="unsupported locale setting"):
            locale.setlocale(locale.LC_NUMERIC, "no_SUCH.locale")

        assert locale.setlocale(locale.LC_NUMERIC) == "C"
        assert issubclass(locale.Error, Exception)

    @needs_c_utf8
    def test_a_setting_made_in_another_thread_is_seen_here(self) -> None:
        locale.setlocale(locale.LC_CTYPE, "C")

        worker = threading.Thread(target=locale.setlocale, args=(locale.LC_CTYPE, "C.UTF-8"))
        worker.start()
        worker.join()

        assert locale.setlocale(locale.LC_CTYPE) == "C.UTF-8"

    def test_only_a_tuple_goes_through_normalize(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        original = locale.normalize

        def counting(name: str) -> str:
            calls.append(name)
            return original(name)

        monkeypatch.setattr(locale, "normalize", counting)

        locale.setlocale(locale.LC_NUMERIC, "C")
        assert calls == []
        assert locale.setlocale(locale.LC_NUMERIC, (None, None)) == "C"
        assert calls == ["C"]

    def test_getlocale_is_one_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        locale.setlocale(locale.LC_NUMERIC, "C")
        calls: list[tuple[Any, ...]] = []
        original = locale._setlocale  # type: ignore[attr-defined]  # noqa: SLF001

        def counting(*args: Any) -> str:
            calls.append(args)
            return original(*args)

        monkeypatch.setattr(locale, "_setlocale", counting)

        assert locale.getlocale(locale.LC_NUMERIC) == (None, None)
        assert calls == [(locale.LC_NUMERIC,)]

    @needs_c_utf8
    def test_getlocale_of_mixed_lc_all_raises(self) -> None:
        locale.setlocale(locale.LC_ALL, "C")
        locale.setlocale(locale.LC_CTYPE, "C.UTF-8")

        with pytest.raises(TypeError, match="LC_ALL is not supported"):
            locale.getlocale(locale.LC_ALL)

    def test_categories_are_integers(self) -> None:
        for name in ("LC_CTYPE", "LC_COLLATE", "LC_TIME", "LC_MONETARY", "LC_NUMERIC"):
            assert isinstance(getattr(locale, name), int)
        assert isinstance(locale.LC_MESSAGES, int)
        assert isinstance(locale.LC_ALL, int)


class CountingDict(dict[str, str]):
    """A dict that records `get()` lookups."""

    lookups = 0

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        self.lookups += 1
        return super().get(key, default)


class TestNormalizeIsAFewLookups:
    """`normalize(localename)` | O(1): at most four `locale_alias` lookups,
    and a name it does not know comes back unchanged."""

    @pytest.fixture
    def table(self, monkeypatch: pytest.MonkeyPatch) -> CountingDict:
        counting = CountingDict(locale.locale_alias)
        monkeypatch.setattr(locale, "locale_alias", counting)
        return counting

    @pytest.mark.parametrize(
        "name", ["en_US.utf8", "de_DE", "sr_RS.UTF-8@latin", "de_DE.iso885915@euro", "nonsense"]
    )
    def test_at_most_four_lookups(self, table: CountingDict, name: str) -> None:
        locale.normalize(name)

        assert 1 <= table.lookups <= 4, f"normalize({name!r}) made {table.lookups} lookups"

    def test_known_and_unknown_names(self) -> None:
        assert locale.normalize("en_US.utf8") == "en_US.UTF-8"
        assert locale.normalize("not-a-locale") == "not-a-locale"

    def test_the_table_is_what_it_reads(self, table: CountingDict) -> None:
        table["xx_yy"] = "xx_YY.UTF-8"

        assert locale.normalize("xx_YY") == "xx_YY.UTF-8"

    def test_the_tables_are_dictionaries(self) -> None:
        assert locale.locale_alias["en_us"] == "en_US.ISO8859-1"
        assert isinstance(locale.locale_encoding_alias, dict)
        assert all(isinstance(key, int) for key in locale.windows_locale)


def _encoding_probe(utf8: int, do_setlocale: bool) -> list[str]:
    """Run getpreferredencoding() in a subprocess and report its setlocale calls."""
    script = textwrap.dedent(
        f"""
        import locale
        calls = []
        original = locale.setlocale
        def counting(category, value=None):
            calls.append(repr(value))
            return original(category, value)
        locale.setlocale = counting
        before = original(locale.LC_CTYPE)
        result = locale.getpreferredencoding({do_setlocale})
        assert original(locale.LC_CTYPE) == before
        for line in [result, *calls]:
            print(line)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-X", f"utf8={utf8}", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return completed.stdout.splitlines()


class TestEncodingQueries:
    """`getencoding()` and `getpreferredencoding(False)` are O(1) queries;
    `getpreferredencoding(True)` sets `LC_CTYPE` and back unless UTF-8 mode
    answers first."""

    def test_utf8_mode_answers_without_touching_the_locale(self) -> None:
        output = _encoding_probe(utf8=1, do_setlocale=True)

        assert [line.lower() for line in output] == ["utf-8"]  # "UTF-8" on 3.10

    def test_do_setlocale_false_makes_no_call(self) -> None:
        output = _encoding_probe(utf8=0, do_setlocale=False)

        assert len(output) == 1

    def test_do_setlocale_true_sets_lc_ctype_and_restores_it(self) -> None:
        output = _encoding_probe(utf8=0, do_setlocale=True)

        # A query, the environment's locale, then the saved name put back.
        assert output[1:3] == ["None", "''"]
        assert len(output) == 4

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_getencoding_makes_no_setlocale_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: Any) -> str:
            raise AssertionError(f"setlocale{args} was called")

        monkeypatch.setattr(locale, "setlocale", refuse)
        monkeypatch.setattr(locale, "_setlocale", refuse)

        assert isinstance(locale.getencoding(), str)  # type: ignore[attr-defined]

    def test_getdefaultlocale_changes_nothing(self) -> None:
        before = locale.setlocale(locale.LC_ALL)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = locale.getdefaultlocale()

        assert len(result) == 2
        assert locale.setlocale(locale.LC_ALL) == before
        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert bool(deprecated) == ((3, 11) <= sys.version_info < (3, 14, 7))


class TestLocaleconv:
    """`localeconv()` | O(1) | a new dictionary of fixed keys per call;
    `CHAR_MAX` marks an unspecified field."""

    def test_each_call_builds_a_new_dictionary(self) -> None:
        first = locale.localeconv()
        first["decimal_point"] = "!"

        second = locale.localeconv()

        assert second is not first
        assert second["decimal_point"] == "."

    @needs_c_utf8
    def test_the_keys_do_not_depend_on_the_locale(self) -> None:
        locale.setlocale(locale.LC_ALL, "C")
        c_keys = set(locale.localeconv())
        locale.setlocale(locale.LC_ALL, "C.UTF-8")

        assert set(locale.localeconv()) == c_keys

    def test_the_c_locale_has_no_currency(self) -> None:
        locale.setlocale(locale.LC_ALL, "C")
        conventions = locale.localeconv()

        assert conventions["frac_digits"] == locale.CHAR_MAX
        assert conventions["currency_symbol"] == ""
        assert conventions["grouping"] == []

    @pytest.mark.skipif(
        locale.CHAR_MAX != 127, reason="Lib/locale.py tests frac_digits against 127"
    )
    def test_currency_refuses_the_c_locale(self) -> None:
        locale.setlocale(locale.LC_ALL, "C")

        with pytest.raises(ValueError, match="'C' locale"):
            locale.currency(1.5)


@pytest.mark.skipif(not hasattr(locale, "nl_langinfo"), reason="Unix only")
class TestNlLanginfo:
    """`nl_langinfo(option)` | O(1): one fixed key; an unknown one raises."""

    def test_every_key_constant_is_answered(self) -> None:
        for name in LANGINFO_KEYS:
            assert isinstance(locale.nl_langinfo(getattr(locale, name)), str), name

    def test_the_c_locale_names(self) -> None:
        locale.setlocale(locale.LC_ALL, "C")

        assert locale.nl_langinfo(locale.DAY_1) == "Sunday"
        assert locale.nl_langinfo(locale.ABDAY_7) == "Sat"
        assert locale.nl_langinfo(locale.MON_12) == "December"
        assert locale.nl_langinfo(locale.ABMON_1) == "Jan"
        assert locale.nl_langinfo(locale.RADIXCHAR) == "."
        assert locale.nl_langinfo(locale.ERA) == ""
        assert locale.nl_langinfo(locale.ALT_DIGITS) == ""

    def test_an_unknown_key_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported langinfo constant"):
            locale.nl_langinfo(-1)


class TestStrcollConvertsBothStringsWhole:
    """`strcoll` | O(a + b) | O(a + b): both strings are converted before the
    comparison, so a difference in the first character saves nothing."""

    @staticmethod
    def pair(length: int) -> tuple[str, str]:
        return "a" + "x" * length, "b" + "x" * length

    def test_the_peak_follows_the_length(self) -> None:
        small = self.pair(1_000)
        large = self.pair(1_000_000)

        peaks = [
            peak_bytes(lambda: locale.strcoll(*small)),
            peak_bytes(lambda: locale.strcoll(*large)),
        ]

        assert peaks[0] * 500 < peaks[1] < peaks[0] * 5_000, f"1,000x the length: peaks {peaks}"

    @pytest.mark.timing
    def test_the_time_follows_the_length(self) -> None:
        small = self.pair(1_000)
        large = self.pair(1_000_000)

        durations = [
            best_ns(lambda: locale.strcoll(*small), inner=20),
            best_ns(lambda: locale.strcoll(*large), inner=3),
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 100, f"1,000x the length cost x{ratio:.0f}: {durations} ns"

    def test_the_sign_orders_the_strings(self) -> None:
        locale.setlocale(locale.LC_COLLATE, "C")

        assert locale.strcoll("apple", "banana") < 0
        assert locale.strcoll("banana", "apple") > 0
        assert locale.strcoll("apple", "apple") == 0


class TestStrxfrmKeys:
    """`strxfrm` | O(s) | O(s): a key that orders as `strcoll()` does."""

    WORDS = ["banana", "apple", "Cherry", "apple pie", "Äpfel", "zebra", "Zebra", "ábaco"]

    def test_the_peak_follows_the_length(self) -> None:
        small = "x" * 1_000
        large = "x" * 1_000_000

        peaks = [
            peak_bytes(lambda: locale.strxfrm(small)),
            peak_bytes(lambda: locale.strxfrm(large)),
        ]

        assert peaks[0] * 500 < peaks[1] < peaks[0] * 5_000, f"1,000x the length: peaks {peaks}"

    @pytest.mark.parametrize("name", ["C", pytest.param("C.UTF-8", marks=needs_c_utf8)])
    def test_keys_order_as_strcoll_does(self, name: str) -> None:
        locale.setlocale(locale.LC_COLLATE, name)

        by_key = sorted(self.WORDS, key=locale.strxfrm)
        by_cmp = sorted(self.WORDS, key=functools.cmp_to_key(locale.strcoll))

        assert by_key == by_cmp

    def test_an_ascii_string_is_its_own_key_in_c(self) -> None:
        locale.setlocale(locale.LC_COLLATE, "C")

        assert locale.strxfrm("apple pie") == "apple pie"


class TestSortingByKeyTransformsOnce:
    """`key=locale.strxfrm` converts each string once; a `strcoll()`
    comparison function converts two strings per comparison."""

    WORDS = [f"w{index:05d}" for index in range(2_000)]

    def test_call_counts(self) -> None:
        words = self.WORDS[:]
        random.Random(1).shuffle(words)
        transforms = 0
        comparisons = 0

        def counting_strxfrm(text: str) -> str:
            nonlocal transforms
            transforms += 1
            return locale.strxfrm(text)

        def counting_strcoll(left: str, right: str) -> int:
            nonlocal comparisons
            comparisons += 1
            return locale.strcoll(left, right)

        by_key = sorted(words, key=counting_strxfrm)
        by_cmp = sorted(words, key=functools.cmp_to_key(counting_strcoll))

        assert by_key == by_cmp
        assert transforms == len(words)
        assert comparisons > len(words) * 5, f"{comparisons} strcoll() calls for {len(words)}"


class TestFormatString:
    """`format_string` | O(f + r): `%` formatting and a rewrite per numeric
    conversion; `monetary=True` takes the monetary conventions."""

    def test_the_c_locale_output(self) -> None:
        locale.setlocale(locale.LC_NUMERIC, "C")

        assert locale.format_string("%.2f of %d", (1234.5, 7), grouping=True) == "1234.50 of 7"
        assert locale.format_string("%(n)d%%", {"n": 5}) == "5%"

    def test_substituted_conventions_are_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with_conventions(monkeypatch, **GERMAN)

        assert locale.format_string("%.2f", 1234567.891, grouping=True) == "1.234.567,89"
        assert locale.format_string("%d", 1234567, grouping=True) == "1.234.567"
        assert locale.format_string("%.2f", 1234.5) == "1234,50"

    def test_monetary_takes_the_monetary_decimal_point(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with_conventions(monkeypatch, decimal_point=",", mon_decimal_point="!")

        assert locale.format_string("%.1f", 2.5) == "2,5"
        assert locale.format_string("%.1f", 2.5, monetary=True) == "2!5"

    @pytest.mark.timing
    def test_the_time_follows_the_format(self) -> None:
        def formatting(count: int) -> Callable[[], str]:
            fmt = "%d " * count
            values = tuple(range(count))
            return lambda: locale.format_string(fmt, values)

        durations = [best_ns(formatting(100), inner=5), best_ns(formatting(10_000), repeats=5)]
        ratio = durations[1] / durations[0]

        assert 20 < ratio < 1_000, f"100x the conversions cost x{ratio:.0f}: {durations} ns"

    @pytest.mark.timing
    def test_grouping_is_quadratic_in_the_digits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with_conventions(monkeypatch, **GERMAN)
        small = "1" * 20_000
        large = "1" * 200_000

        grouped = [
            best_ns(lambda: locale.localize(small, grouping=True), repeats=3),
            best_ns(lambda: locale.localize(large, grouping=True), repeats=3),
        ]
        plain = [
            best_ns(lambda: locale.localize(small), inner=20),
            best_ns(lambda: locale.localize(large), inner=20),
        ]

        assert grouped[1] / grouped[0] > 25, f"10x the digits, grouped: {grouped} ns"
        assert plain[1] / plain[0] < 30, f"10x the digits, ungrouped: {plain} ns"


class TestParsingAndSmallFormatters:
    """`atof`, `atoi`, `delocalize`, `localize` | O(s); `str` | O(1);
    `currency` | O(r)."""

    def test_german_style_round_trip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with_conventions(monkeypatch, **GERMAN)

        formatted = locale.format_string("%.2f", 1234567.5, grouping=True)
        assert formatted == "1.234.567,50"
        assert locale.delocalize(formatted) == "1234567.50"
        assert locale.atof(formatted) == 1234567.5
        assert locale.atoi("1.234") == 1234
        assert locale.localize("1234567.50", grouping=True) == formatted
        to_decimal: Any = Decimal  # typeshed types `func` as returning float
        assert locale.atof("1,5", to_decimal) == Decimal("1.5")

    def test_c_locale_round_trip(self) -> None:
        locale.setlocale(locale.LC_NUMERIC, "C")

        formatted = locale.format_string("%.2f", 1234.5, grouping=True)
        assert locale.atof(formatted) == 1234.5
        assert locale.localize("1234.50") == formatted

    def test_str_is_twelve_significant_digits(self) -> None:
        locale.setlocale(locale.LC_NUMERIC, "C")

        assert locale.str(0.1 + 0.2) == "0.3"
        assert locale.str(1 / 3) == "%.12g" % (1 / 3)

    def test_currency_with_conventions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with_conventions(monkeypatch, **US_MONEY)

        assert locale.currency(1234.5, grouping=True) == "$1,234.50"
        assert locale.currency(-1234.5, grouping=True) == "-$1,234.50"
        assert locale.currency(1234.5, symbol=False) == "1234.50"


@pytest.mark.skipif(not hasattr(locale, "gettext"), reason="needs the C library's libintl")
class TestCatalogueFunctions:
    """The C library's `gettext()` family: without a catalogue the message
    comes back; `None` only queries the domain settings."""

    def test_messages_come_back_unchanged(self) -> None:
        locale.setlocale(locale.LC_MESSAGES, "C")

        assert locale.gettext("Hello") == "Hello"
        assert locale.dgettext(None, "Hello") == "Hello"
        assert locale.dcgettext(None, "Hello", locale.LC_MESSAGES) == "Hello"

    def test_none_only_queries(self) -> None:
        domain = locale.textdomain(None)
        directory = locale.bindtextdomain(domain, None)

        assert locale.textdomain(None) == domain
        assert locale.bindtextdomain(domain, None) == directory
        codeset = locale.bind_textdomain_codeset(domain, None)
        assert codeset is None or isinstance(codeset, str)

    def test_an_empty_domain_is_refused(self) -> None:
        with pytest.raises(locale.Error, match="non-empty"):
            locale.bindtextdomain("", None)


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
    """Each block runs in its own subprocess, so a locale one block sets
    cannot reach another, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "== 'Sunday'" in s)
        mutated = source.replace("== 'Sunday'", "== 'Monday'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
