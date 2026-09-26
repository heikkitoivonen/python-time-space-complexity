"""Tests for docs/stdlib/configparser.md.

The page prices the parser as dictionaries of sections: lookups, membership
and single-option changes are hash operations, while parsing, the post-read
walk over every held option, interpolation, and the calls that list every
section or option first are not. Space and the list-building rows are settled
by traced allocation, which separates the states by orders of magnitude; the
post-read walk and the `clear()` loops are settled by counting hook and method
calls; parsing, the value scan in `get()` and the per-reference copy in
interpolation are settled by timing ratios.

Measurement scope:

* The post-read walk is a counting `Interpolation.before_read`: reading one
  option into a parser holding 1,000 calls it 1,001 times, 100 one-option
  reads into a fresh parser call it 5,050 times, `read()` of three files calls
  it once per held option after each file, and `read_dict()` of 1,000 options
  never calls it. Parsing is timed over 1,000, 10,000 and 100,000 lines, both
  single-line options and one value continued over that many lines; 100x the
  lines must cost under 1,000x, where a quadratic parse would cost 10,000x.
* `ConfigParser.get()` on a plain value is the stored object itself, and a
  timing test holds the value at 10,000 and 10,000,000 characters: the
  interpolating parser must cost more than 20x more on the long one, and
  `RawConfigParser.get()` under 5x. The O(v·(r + 1)) term is a timing test at
  a fixed value length and reference count: 2,000 references or escapes with
  500,000 padding characters after them must cost more than 4x the same value
  with the padding before them, for both interpolation classes, since only the
  trailing padding is copied once per reference. `vars` is a traced peak that
  grows more than 100x from 10 to 100,000 entries.
* `ExtendedInterpolation` nested references are a traced peak over a
  referenced section of 10 and 100,000 options: more than 100x apart when the
  referenced value contains `$`, and under 2x apart when it is plain or when
  the same chain runs under `BasicInterpolation`. A reference chain of 10
  expands and one of 11 raises `InterpolationDepthError`, under both classes.
  Malformed syntax raises on `get()` after `read_string()`, and at once from
  `read_dict()`; `SectionProxy.clear()` on an interpolating parser stops at a
  value it cannot expand, leaving it in place.
* `options()`, `len()` and `iter()` of a `SectionProxy`, `popitem()` and the
  constructor's `defaults` are traced peaks that grow more than 100x from 10
  to 100,000 DEFAULT options or sections; `has_option()`, `has_section()`,
  `in` on a proxy and `len()` of the DEFAULT proxy stay under 2 KB with
  100,000 DEFAULT options, and iterating a parser to the end under 2 KB with
  100,000 sections. `clear()` on a parser of 200 sections is a
  subclass whose `sections()` records its result, which lists 20,100 names in
  all; `SectionProxy.clear()` on 50 options with 5 DEFAULT options records
  51 `options()` calls. `items(section)` calls `before_get` once per option,
  DEFAULT's included.
* `ConfigParser.set()` peaks under 2 KB for a 1,000,000-character value with
  nothing to expand, and over 400 KB for one of 1,000,000 characters with a
  `%%` or `$$` escape in every four, under the matching interpolation class;
  `RawConfigParser.set()` stores a non-string value unchanged, and `None` is
  accepted through a proxy of either parser with `allow_no_value=True`.
* `write()` over 200 options of 10,000 characters, into a sink that keeps only
  the last string written, peaks under five times one option against a two-million
  character file; the output, dropped comments and unexpanded references are
  asserted on the text. On 3.14, keys `a=b` and `[x]` are refused and `[x` is
  written.
* `parser.converters[name] = func` is observed to add the getter to every
  existing proxy. Identity is asserted for `parser[section]`, `defaults()` and
  `converters`. The version-specific names are asserted present or absent on
  each side of their boundary: `readfp()` and `SafeConfigParser` before 3.12,
  `LegacyInterpolation` before 3.13, `UNNAMED_SECTION` and
  `MultilineContinuationError` from 3.13, `InvalidWriteError` and
  `UnnamedSectionDisabledError` from 3.14.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(c) parse bound is measured on ordinary lines only. Lines built to make
  the option pattern backtrack are not priced, and that pattern differs
  between patch releases.
* The walk after a read also iterates every section, empty ones included,
  which is why `t` counts sections; the hook counts observe options only, and
  the section term is read from `_join_multiline_values()` in
  Lib/configparser.py.
* Option name length and `optionxform()` cost are priced at O(1); only value
  length is varied. The copy of a `vars` mapping (observed above), `str()`
  conversion of non-string values given to `defaults` or `read_dict()`, the
  `int()` or `float()` conversion in the typed getters, and the formatting of
  a value or line into an exception message are left out of the bounds.
  Converter functions are caller-supplied, and the constant per-section cost
  of binding one getter per converter is not measured.
* The `+ r` term in the expansion space bounds, one accumulator entry per
  reference, is read from `_interpolate_some()` in Lib/configparser.py; the
  per-reference copies of the remaining value dominate any measured peak.
* `ParsingError.append()` and `ParsingError.combine()` are undocumented
  helpers the page does not price; the time to build a `ParsingError` message
  over many bad lines differs between patch releases and is not varied.
* `dict_type`, `delimiters`, `comment_prefixes` and
  `inline_comment_prefixes` are left at their defaults in the timing tests.
"""

from __future__ import annotations

import configparser
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "configparser.md"
EXPECTED_BLOCKS = 10


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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
    """Peak traced allocation while func runs, after one untraced warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingReads(configparser.Interpolation):
    """An interpolation that counts `before_read` and `before_get` calls."""

    def __init__(self) -> None:
        self.reads = 0
        self.gets = 0

    def before_read(self, parser: Any, section: Any, option: str, value: Any) -> Any:
        self.reads += 1
        return value

    def before_get(self, parser: Any, section: Any, option: str, value: Any, defaults: Any) -> Any:
        self.gets += 1
        return value


class LastLineSink:
    """A file-like object that keeps only the last string written."""

    last: str = ""

    def write(self, text: str) -> int:
        self.last = text
        return len(text)


def parser_with_sections(count: int, cls: type[Any] = configparser.RawConfigParser) -> Any:
    """A parser of `cls` holding `count` empty sections."""
    parser = cls()
    for index in range(count):
        parser.add_section(f"s{index}")
    return parser


class TestEveryReadVisitsTheWholeParser:
    """`read_file()`, `read_string()` | O(c + t): after parsing, every held
    option is visited; `read_dict()` | O(c) visits none of them."""

    def test_one_small_read_visits_every_held_option(self) -> None:
        hook = CountingReads()
        parser = configparser.ConfigParser(interpolation=hook)
        parser.read_dict({f"s{i}": {f"k{j}": "v" for j in range(10)} for i in range(100)})

        parser.read_string("[new]\na = 1\n")

        assert hook.reads == 1_001

    def test_many_small_reads_are_quadratic_in_calls(self) -> None:
        hook = CountingReads()
        parser = configparser.ConfigParser(interpolation=hook)

        for index in range(100):
            parser.read_string(f"[s{index}]\nk = v\n")

        assert hook.reads == 100 * 101 // 2

    def test_read_dict_does_not_walk(self) -> None:
        hook = CountingReads()
        parser = configparser.ConfigParser(interpolation=hook)

        parser.read_dict({f"s{i}": {f"k{j}": "v" for j in range(10)} for i in range(100)})

        assert hook.reads == 0
        assert len(parser.sections()) == 100

    def test_read_walks_once_per_file(self, tmp_path: pathlib.Path) -> None:
        hook = CountingReads()
        parser = configparser.ConfigParser(interpolation=hook)
        names = []
        for index in range(3):
            path = tmp_path / f"f{index}.ini"
            path.write_text(f"[s{index}]\na = 1\nb = 2\n", encoding="utf-8")
            names.append(path)

        loaded = parser.read([*names, tmp_path / "absent.ini"], encoding="utf-8")

        assert loaded == [str(name) for name in names]
        assert hook.reads == 2 + 4 + 6

    def test_continuation_lines_are_joined(self) -> None:
        parser = configparser.ConfigParser()

        parser.read_string("[s]\nk = first\n  second\n  third\n")

        assert parser["s"]["k"] == "first\nsecond\nthird"

    @pytest.mark.timing
    @pytest.mark.parametrize("shape", ["options", "continuation"])
    def test_parsing_is_linear_in_lines(self, shape: str) -> None:
        durations = []
        for lines in (1_000, 10_000, 100_000):
            if shape == "options":
                text = "[s]\n" + "".join(f"k{i} = value{i}\n" for i in range(lines))
            else:
                text = "[s]\nk = start\n" + "".join(f"  line{i}\n" for i in range(lines))
            durations.append(
                best_ns(lambda t=text: configparser.ConfigParser().read_string(t), repeats=3)
            )

        ratio = durations[2] / durations[0]
        assert durations[0] < durations[1] < durations[2], f"cost did not grow: {durations} ns"
        assert ratio < 1_000, (
            f"100x the lines cost x{ratio:.0f}; a quadratic parse would cost x10,000 "
            f"({durations} ns)"
        )


class TestParsingErrors:
    """Bad lines are collected and raised together after the parse; strict
    duplicates and a missing header raise at once."""

    def test_bad_lines_are_collected_and_good_ones_kept(self) -> None:
        parser = configparser.ConfigParser()

        with pytest.raises(configparser.ParsingError) as caught:
            parser.read_string("[s]\na = 1\nbad line\nb = 2\nworse\nc = 3\n")

        assert [lineno for lineno, _ in caught.value.errors] == [3, 5]
        assert dict(parser["s"]) == {"a": "1", "b": "2", "c": "3"}

    def test_a_duplicate_option_raises_at_its_line(self) -> None:
        parser = configparser.ConfigParser()

        with pytest.raises(configparser.DuplicateOptionError) as caught:
            parser.read_string("[s]\np = 1\np = 2\n[later]\n")

        assert caught.value.lineno == 3
        assert not parser.has_section("later")

    def test_a_duplicate_section_raises_in_one_source(self) -> None:
        with pytest.raises(configparser.DuplicateSectionError):
            configparser.ConfigParser().read_string("[s]\n[s]\n")

    def test_a_non_strict_parser_keeps_the_last(self) -> None:
        parser = configparser.ConfigParser(strict=False)

        parser.read_string("[s]\np = 1\np = 2\n")

        assert parser["s"]["p"] == "2"

    def test_an_option_before_any_header_raises(self) -> None:
        with pytest.raises(configparser.MissingSectionHeaderError):
            configparser.ConfigParser().read_string("# comment\n\na = 1\n")

    def test_every_exception_derives_from_error(self) -> None:
        names = [
            "NoSectionError",
            "NoOptionError",
            "DuplicateSectionError",
            "DuplicateOptionError",
            "ParsingError",
            "MissingSectionHeaderError",
            "InterpolationError",
            "InterpolationMissingOptionError",
            "InterpolationSyntaxError",
            "InterpolationDepthError",
        ]
        for name in names:
            assert issubclass(getattr(configparser, name), configparser.Error), name

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_a_continued_valueless_option_raises(self) -> None:
        parser = configparser.ConfigParser(allow_no_value=True)

        with pytest.raises(configparser.MultilineContinuationError):  # type: ignore[attr-defined]
            parser.read_string("[s]\nflag\n  indented\n")


class TestLookups:
    """`get()` | O(v·(r + 1) + w); raw or `RawConfigParser` | O(1); the
    membership tests are O(1) and the list-building calls are not."""

    DEFAULTS = {f"d{i}": "x" for i in range(100_000)}

    def test_a_plain_value_comes_back_uncopied(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_dict({"s": {"a": "x" * 1_000}})

        assert parser.get("s", "a") is parser.get("s", "a", raw=True)

    @pytest.mark.timing
    def test_the_interpolating_get_scans_the_value(self) -> None:
        durations: dict[str, list[float]] = {}
        for cls in (configparser.ConfigParser, configparser.RawConfigParser):
            durations[cls.__name__] = []
            for length in (10_000, 10_000_000):
                parser = cls()
                parser.read_dict({"s": {"a": "x" * length}})
                durations[cls.__name__].append(
                    best_ns(lambda p=parser: p.get("s", "a"), repeats=7, inner=20)
                )

        scanned = durations["ConfigParser"][1] / durations["ConfigParser"][0]
        raw = durations["RawConfigParser"][1] / durations["RawConfigParser"][0]
        assert scanned > 20, f"1,000x the value cost x{scanned:.1f}: {durations}"
        assert raw < 5, f"RawConfigParser.get() grew x{raw:.1f} with the value: {durations}"

    def test_vars_are_copied_on_every_call(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_dict({"s": {"a": "1"}})
        peaks = []
        for size in (10, 100_000):
            extra = {f"v{i}": "x" for i in range(size)}
            peaks.append(peak_bytes(lambda e=extra: parser.get("s", "a", vars=e)))

        assert peaks[1] > peaks[0] * 100, f"vars of 10 and 100,000 entries peaked at {peaks}"

    def test_fallbacks_cover_a_missing_section_and_option(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[s]\na = 1\n")

        assert parser.get("missing", "a", fallback="f") == "f"
        assert parser.get("s", "missing", fallback=None) is None
        assert parser.getint("missing", "a", fallback=4) == 4
        with pytest.raises(configparser.NoSectionError):
            parser.get("missing", "a")
        with pytest.raises(configparser.NoOptionError):
            parser.get("s", "missing")

    def test_typed_getters_convert(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[s]\ni = 42\nf = 1.5\nb = YES\n")

        assert parser.getint("s", "i") == 42
        assert parser.getfloat("s", "f") == 1.5
        assert parser.getboolean("s", "b") is True
        assert set(parser.BOOLEAN_STATES) == {"1", "yes", "true", "on", "0", "no", "false", "off"}

    def test_membership_tests_do_not_build_lists(self) -> None:
        parser = configparser.ConfigParser(defaults=self.DEFAULTS)
        parser.read_dict({"s": {"a": "1"}})

        peaks = [
            peak_bytes(lambda: parser.has_option("s", "d5")),
            peak_bytes(lambda: parser.has_section("s")),
            peak_bytes(lambda: "d5" in parser["s"]),
            peak_bytes(lambda: len(parser["DEFAULT"])),
        ]

        assert max(peaks) < 2_000, f"O(1) lookups over 100,000 defaults peaked at {peaks}"
        assert parser.has_option("s", "d5") and not parser.has_section("DEFAULT")
        assert not parser.has_option("missing", "a")

    @pytest.mark.parametrize("operation", ["options", "len(proxy)", "iter(proxy)"])
    def test_option_lists_grow_with_default(self, operation: str) -> None:
        peaks = []
        for size in (10, 100_000):
            parser = configparser.ConfigParser(defaults={f"d{i}": "x" for i in range(size)})
            parser.read_dict({"s": {"a": "1"}})
            proxy = parser["s"]
            call: Callable[[], Any] = {
                "options": lambda p=parser: p.options("s"),
                "len(proxy)": lambda x=proxy: len(x),
                "iter(proxy)": lambda x=proxy: iter(x),
            }[operation]
            peaks.append(peak_bytes(call))

        assert peaks[1] > peaks[0] * 100, f"{operation} over 10 and 100,000 defaults: {peaks}"

    def test_options_lists_the_section_then_default(self) -> None:
        parser = configparser.ConfigParser(defaults={"z": "1", "a": "2"})
        parser.read_string("[s]\nm = 3\na = 4\n")

        assert parser.options("s") == ["m", "a", "z"]
        assert parser.sections() == ["s"]
        assert parser.sections() is not parser.sections()

    def test_items_expands_every_option_including_default(self) -> None:
        hook = CountingReads()
        parser = configparser.ConfigParser(defaults={"d1": "x", "d2": "y"}, interpolation=hook)
        parser.read_dict({"s": {f"k{i}": "v" for i in range(5)}})

        pairs = parser.items("s")

        assert hook.gets == 7
        assert len(pairs) == 7

    def test_items_without_a_section_is_a_view_of_proxies(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[a]\n[b]\n")

        view = parser.items()

        assert [name for name, _ in view] == ["DEFAULT", "a", "b"]
        assert all(proxy is parser[name] for name, proxy in view)

    def test_defaults_is_the_dictionary_itself(self) -> None:
        parser = configparser.ConfigParser(defaults={"a": "1"})
        defaults: dict[str, str] = parser.defaults()  # type: ignore[assignment]

        assert parser.defaults() is defaults
        defaults["b"] = "2"
        assert parser.get("DEFAULT", "b") == "2"


class TestConstructionAndSetting:
    """Constructors | O(d); `ConfigParser.set()` | O(v), scanning without
    copying a value that has no `%`; `RawConfigParser.set()` | O(1)."""

    def test_defaults_are_strings_only_on_config_parser(self) -> None:
        numeric: Any = {"n": 1}

        assert configparser.ConfigParser(defaults=numeric).defaults() == {"n": "1"}
        assert configparser.RawConfigParser(defaults=numeric).defaults() == {"n": 1}

    def test_construction_grows_with_defaults(self) -> None:
        peaks = []
        for size in (10, 100_000):
            defaults = {f"d{i}": "x" for i in range(size)}
            peaks.append(peak_bytes(lambda d=defaults: configparser.ConfigParser(defaults=d)))

        assert peaks[1] > peaks[0] * 100, f"10 and 100,000 defaults peaked at {peaks}"

    @pytest.mark.parametrize(
        ("interpolation", "escape"),
        [(configparser.BasicInterpolation, "%%"), (configparser.ExtendedInterpolation, "$$")],
    )
    def test_set_scans_a_plain_value_without_copying(
        self, interpolation: type[configparser.Interpolation], escape: str
    ) -> None:
        parser = configparser.ConfigParser(interpolation=interpolation())
        parser.add_section("s")
        plain = "x" * 1_000_000
        escaped = ("ab" + escape) * 250_000

        plain_peak = peak_bytes(lambda: parser.set("s", "a", plain))
        escaped_peak = peak_bytes(lambda: parser.set("s", "a", escaped))

        assert plain_peak < 2_000, f"a plain 1 MB value peaked at {plain_peak}"
        assert escaped_peak > 400_000, f"an escaped 1 MB value peaked at {escaped_peak}"

    def test_config_parser_set_checks_type_and_syntax(self) -> None:
        parser = configparser.ConfigParser()
        parser.add_section("s")

        with pytest.raises(TypeError):
            parser.set("s", "a", 1)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="interpolation syntax"):
            parser.set("s", "a", "100%")

    def test_raw_set_stores_any_value(self) -> None:
        parser = configparser.RawConfigParser()
        parser.add_section("s")
        value = object()

        parser.set("s", "a", value)  # type: ignore[arg-type]

        assert parser.get("s", "a") is value

    def test_add_and_remove(self) -> None:
        parser = configparser.ConfigParser()
        parser.add_section("s")
        parser.set("s", "a", "1")

        with pytest.raises(configparser.DuplicateSectionError):
            parser.add_section("s")
        with pytest.raises(ValueError):
            parser.add_section("DEFAULT")
        assert parser.remove_option("s", "a") is True
        assert parser.remove_option("s", "a") is False
        with pytest.raises(configparser.NoSectionError):
            parser.remove_option("missing", "a")
        assert parser.remove_section("s") is True
        assert parser.remove_section("s") is False


class TestPopitemAndClear:
    """`popitem()` | O(s) lists every section; `clear()` | O(s²) calls it once
    per section; `SectionProxy.clear()` | O(o·(o + d))."""

    def test_popitem_lists_every_section(self) -> None:
        peaks = []
        for count in (10, 100_000):
            parser = parser_with_sections(count)
            peaks.append(peak_bytes(parser.popitem))

        assert peaks[1] > peaks[0] * 100, f"popitem over 10 and 100,000 sections: {peaks}"

    def test_clear_lists_the_remaining_sections_once_per_section(self) -> None:
        listed: list[int] = []

        class Recording(configparser.RawConfigParser):
            def sections(self) -> list[str]:
                names = super().sections()
                listed.append(len(names))
                return names

        parser = parser_with_sections(200, Recording)
        parser.set("DEFAULT", "kept", "yes")

        parser.clear()

        assert sum(listed) == 200 * 201 // 2
        assert parser.sections() == []
        assert parser.defaults() == {"kept": "yes"}

    def test_popitem_never_removes_default(self) -> None:
        parser = configparser.ConfigParser(defaults={"a": "1"})

        with pytest.raises(KeyError):
            parser.popitem()

    def test_proxy_clear_builds_one_option_list_per_removal(self) -> None:
        calls: list[int] = []

        class Recording(configparser.RawConfigParser):
            def options(self, section: str) -> list[str]:
                names = super().options(section)
                calls.append(len(names))
                return names

        parser = Recording(defaults={f"d{i}": "x" for i in range(5)})
        parser.read_dict({"s": {f"k{i}": "v" for i in range(50)}})

        parser["s"].clear()

        assert len(calls) == 51
        assert calls[0] == 55
        assert parser.options("s") == [f"d{i}" for i in range(5)]


class TestMappingAccess:
    """`parser[section]` is the stored proxy; `len()` and iteration of a
    parser are O(1) and lazy; proxy item access goes through the parser."""

    def test_the_proxy_is_built_once(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[s]\na = 1\n")

        assert parser["s"] is parser["s"]
        assert parser["s"].name == "s"
        assert parser["s"].parser is parser
        with pytest.raises(KeyError):
            parser["missing"]

    def test_default_section_can_be_renamed(self) -> None:
        parser = configparser.ConfigParser(default_section="common")
        parser.read_string("[common]\na = 1\n[s]\n")

        assert configparser.DEFAULTSECT == "DEFAULT"
        assert parser["s"]["a"] == "1"
        assert parser.sections() == ["s"]

    def test_parser_length_and_iteration_include_default(self) -> None:
        parser = parser_with_sections(3)

        assert len(parser) == 4
        assert list(parser) == ["DEFAULT", "s0", "s1", "s2"]
        assert "DEFAULT" in parser and "s1" in parser and "missing" not in parser

    def test_iterating_a_parser_is_lazy(self) -> None:
        parser = parser_with_sections(100_000)

        seen = [0]

        def walk() -> None:
            seen[0] = 0
            for _ in parser:
                seen[0] += 1

        peak = peak_bytes(walk)

        assert seen[0] == 100_001
        assert peak < 2_000, f"iterating 100,000 sections peaked at {peak}"

    def test_assigning_a_section_replaces_its_options(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[s]\nold = 1\n")

        parser["s"] = {"new": "2"}

        assert dict(parser["s"]) == {"new": "2"}
        with pytest.raises(ValueError):
            del parser["DEFAULT"]
        del parser["s"]
        assert "s" not in parser

    def test_proxy_access(self) -> None:
        parser = configparser.RawConfigParser(defaults={"shared": "d"})
        parser.read_string("[s]\na = 1\n")
        proxy = parser["s"]

        assert proxy["a"] == "1"
        assert proxy.get("missing") is None
        assert proxy.getint("a") == 1
        with pytest.raises(KeyError):
            proxy["missing"]
        with pytest.raises(KeyError):
            del proxy["shared"]
        with pytest.raises(TypeError):
            proxy["b"] = 2  # type: ignore[assignment]
        del proxy["a"]
        assert "a" not in proxy

    def test_none_is_allowed_only_with_allow_no_value(self) -> None:
        for cls in (configparser.ConfigParser, configparser.RawConfigParser):
            parser = cls(allow_no_value=True)
            parser.add_section("s")

            parser["s"]["flag"] = None  # type: ignore[assignment]

            assert parser.get("s", "flag") is None

            strict = cls()
            strict.add_section("s")
            with pytest.raises(TypeError):
                strict["s"]["flag"] = None  # type: ignore[assignment]


class TestInterpolation:
    """Expansion | O(v·(r + 1) + w): each reference or escape copies the rest
    of the value. `ExtendedInterpolation` adds O(o + d) per nested reference."""

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("interpolation", "token"),
        [
            (configparser.BasicInterpolation, "%(x)s"),
            (configparser.BasicInterpolation, "%%"),
            (configparser.ExtendedInterpolation, "${x}"),
            (configparser.ExtendedInterpolation, "$$"),
        ],
    )
    def test_each_reference_copies_the_rest(
        self, interpolation: type[configparser.Interpolation], token: str
    ) -> None:
        padding = "a" * 500_000
        durations = []
        for value in (padding + token * 2_000, token * 2_000 + padding):
            parser = configparser.ConfigParser(interpolation=interpolation())
            parser.read_dict({"s": {"x": "y", "v": value}})
            durations.append(best_ns(lambda p=parser: p.get("s", "v"), repeats=3))

        ratio = durations[1] / durations[0]
        assert ratio > 4, (
            f"trailing padding cost x{ratio:.1f} over leading padding at the same length and "
            f"reference count ({durations} ns); an O(v + r) expansion would give x1"
        )

    @pytest.mark.parametrize(
        ("interpolation", "chain", "copies"),
        [
            (configparser.ExtendedInterpolation, ("${b}", "${c}"), True),
            (configparser.ExtendedInterpolation, ("${b}", "end"), False),
            (configparser.BasicInterpolation, ("%(b)s", "%(c)s"), False),
        ],
    )
    def test_only_extended_nesting_copies_the_section(
        self,
        interpolation: type[configparser.Interpolation],
        chain: tuple[str, str],
        copies: bool,
    ) -> None:
        peaks = []
        for size in (10, 100_000):
            options = {f"k{i}": "z" for i in range(size)}
            options.update(v=chain[0], b=chain[1], c="end")
            parser = configparser.ConfigParser(interpolation=interpolation())
            parser.read_dict({"s": options})
            assert parser.get("s", "v") == "end"
            peaks.append(peak_bytes(lambda p=parser: p.get("s", "v")))

        if copies:
            assert peaks[1] > peaks[0] * 100, f"{chain} over 10 and 100,000 options: {peaks}"
        else:
            assert peaks[1] < peaks[0] * 2, f"{chain} over 10 and 100,000 options: {peaks}"

    def test_cross_section_references(self) -> None:
        parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        parser.read_string(
            "[common]\nroot = /srv\nlogs = ${root}/logs\n[app]\nf = ${common:logs}\n"
        )

        assert parser["app"]["f"] == "/srv/logs"

    @pytest.mark.parametrize(
        ("interpolation", "template"),
        [
            (configparser.BasicInterpolation, "%(k{})s"),
            (configparser.ExtendedInterpolation, "${{k{}}}"),
        ],
    )
    def test_depth_limit(
        self, interpolation: type[configparser.Interpolation], template: str
    ) -> None:
        assert configparser.MAX_INTERPOLATION_DEPTH == 10
        for length, raises in ((10, False), (11, True)):
            options = {f"k{i}": template.format(i + 1) for i in range(length)}
            options[f"k{length}"] = "end"
            parser = configparser.ConfigParser(interpolation=interpolation())
            parser.read_dict({"s": options})
            if raises:
                with pytest.raises(configparser.InterpolationDepthError):
                    parser.get("s", "k0")
            else:
                assert parser.get("s", "k0") == "end"

    def test_errors_surface_on_get_not_read(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[s]\nbad = 100%\nmissing = %(nope)s\n")

        with pytest.raises(configparser.InterpolationSyntaxError):
            parser.get("s", "bad")
        with pytest.raises(configparser.InterpolationMissingOptionError):
            parser.get("s", "missing")
        assert parser.get("s", "bad", raw=True) == "100%"

    def test_set_and_read_dict_check_syntax_at_once(self) -> None:
        with pytest.raises(ValueError, match="interpolation syntax"):
            configparser.ConfigParser().read_dict({"s": {"bad": "100%"}})

    def test_proxy_clear_expands_what_it_removes(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_string("[s]\nbad = 100%\n")

        with pytest.raises(configparser.InterpolationSyntaxError):
            parser["s"].clear()
        assert parser.options("s") == ["bad"]

    def test_raw_parser_does_not_expand(self) -> None:
        parser = configparser.RawConfigParser()
        parser.read_string("[s]\na = %(b)s\n")

        assert parser.get("s", "a") == "%(b)s"

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="removed in 3.13")
    def test_legacy_interpolation_exists_before_313(self) -> None:
        assert hasattr(configparser, "LegacyInterpolation")

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="removed in 3.13")
    def test_legacy_interpolation_is_gone_from_313(self) -> None:
        assert not hasattr(configparser, "LegacyInterpolation")


class TestWritingHoldsOneLine:
    """`write()` | O(c) | O(v): one option formatted and written at a time,
    stored values unexpanded, comments dropped."""

    def test_the_peak_is_one_line_not_the_file(self) -> None:
        parser = configparser.ConfigParser()
        parser.read_dict({"s": {f"k{i}": "v" * 10_000 for i in range(200)}})
        sink = LastLineSink()

        peak = peak_bytes(lambda: parser.write(sink))  # type: ignore[arg-type]

        widest = len("k0 = " + "v" * 10_000)
        assert peak < widest * 5, f"write peaked at {peak} for a {widest}-char option line"

    def test_output(self) -> None:
        parser = configparser.ConfigParser(defaults={"d": "1"})
        parser.read_string("# gone\n[s]\nurl = %(d)s/x\n")
        buffer = io.StringIO()

        parser.write(buffer)

        assert buffer.getvalue() == "[DEFAULT]\nd = 1\n\n[s]\nurl = %(d)s/x\n\n"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_a_key_that_would_not_read_back_is_refused(self) -> None:
        parser = configparser.RawConfigParser()
        parser.add_section("s")
        parser.set("s", "a=b", "1")

        with pytest.raises(configparser.InvalidWriteError):  # type: ignore[attr-defined]
            parser.write(io.StringIO())

        parser.remove_option("s", "a=b")
        parser.set("s", "[x]", "1")
        with pytest.raises(configparser.InvalidWriteError):  # type: ignore[attr-defined]
            parser.write(io.StringIO())

        parser.remove_option("s", "[x]")
        parser.set("s", "[x", "1")
        parser.write(io.StringIO())


class TestConvertersAndCustomization:
    """`converters[name] = func` | O(s) reaches every existing proxy;
    `optionxform`, `BOOLEAN_STATES` and `SECTCRE` are replaceable."""

    def test_a_new_converter_reaches_every_existing_proxy(self) -> None:
        parser = parser_with_sections(50, configparser.ConfigParser)
        for name in parser.sections():
            parser.set(name, "v", "a,b")

        parser.converters["list"] = lambda value: value.split(",")

        assert parser.converters is parser.converters
        assert all(parser[name].getlist("v") == ["a", "b"] for name in parser.sections())
        assert parser.getlist("s0", "v") == ["a", "b"]  # type: ignore[attr-defined]

    def test_optionxform_keeps_case_when_replaced(self) -> None:
        parser = configparser.ConfigParser()
        parser.optionxform = str  # type: ignore[assignment,method-assign]
        parser.read_string("[s]\nKey = 1\n")

        assert parser.options("s") == ["Key"]
        assert configparser.ConfigParser().optionxform("Key") == "key"

    def test_boolean_states_and_sectcre_are_replaceable(self) -> None:
        class Custom(configparser.ConfigParser):
            BOOLEAN_STATES = {"sure": True, "nope": False}  # noqa: RUF012
            SECTCRE = re.compile(r"<(?P<header>[^>]+)>")

        parser = Custom()
        parser.read_string("<s>\nflag = Sure\n")

        parser.set("s", "other", "yes")

        assert parser.sections() == ["s"]
        assert parser.getboolean("s", "flag") is True
        with pytest.raises(ValueError, match="Not a boolean"):
            parser.getboolean("s", "other")


class TestVersionedNames:
    """The names that exist only on part of the supported range."""

    def test_readfp_and_safeconfigparser_end_at_312(self) -> None:
        present = sys.version_info < (3, 12)
        assert hasattr(configparser.ConfigParser, "readfp") is present
        assert hasattr(configparser, "SafeConfigParser") is present

    def test_unnamed_section_arrives_in_313(self) -> None:
        present = sys.version_info >= (3, 13)
        assert hasattr(configparser, "UNNAMED_SECTION") is present
        assert hasattr(configparser, "MultilineContinuationError") is present

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_unnamed_section_holds_leading_options(self) -> None:
        parser = configparser.ConfigParser(allow_unnamed_section=True)  # type: ignore[call-arg]
        parser.read_string("a = 1\n[s]\nb = 2\n")

        unnamed = configparser.UNNAMED_SECTION  # type: ignore[attr-defined]
        assert parser.get(unnamed, "a") == "1"
        assert parser.sections() == [unnamed, "s"]

    def test_write_and_unnamed_errors_arrive_in_314(self) -> None:
        present = sys.version_info >= (3, 14)
        assert hasattr(configparser, "InvalidWriteError") is present
        assert hasattr(configparser, "UnnamedSectionDisabledError") is present

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_unnamed_section_needs_the_flag(self) -> None:
        with pytest.raises(configparser.UnnamedSectionDisabledError):  # type: ignore[attr-defined]
            configparser.ConfigParser().add_section(
                configparser.UNNAMED_SECTION  # type: ignore[attr-defined]
            )


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
    """Each block runs in its own subprocess and working directory, and
    asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "hook.reads == 101" in s)
        mutated = source.replace("hook.reads == 101", "hook.reads == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
