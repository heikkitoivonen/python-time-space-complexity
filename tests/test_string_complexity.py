"""Tests for docs/stdlib/string.md.

The page prices `Template` and `Formatter` as a fresh scan of the string on
every call, `capwords()` as three linear passes, and the `string.templatelib`
types as tuples of parts. Construction and laziness claims are settled by
identity and traced allocation, which need no tolerance; the output dimension
is settled by allocation; growth classes that only a stopwatch can separate
compare sizes eight or more times apart, against a control that isolates
the variable. Allocation ratios over a 100x input are asserted between 20x
and 300x, so a quadratic peak (10,000x) fails as surely as a constant one.

Measurement scope:

* `Template()` peaks under 5 KB on a 1,000,000-character template and keeps
  the string by identity. An instance `pattern` that records its calls sees
  `sub()` run over the whole template on each of three `substitute()` and
  `safe_substitute()` calls, and a reassigned `.template` is what the next
  call scans. After one warm-up call, which is where 3.14 compiles the base
  class's pattern, substitution calls `re.compile` zero times; a subclass
  has a compiled `pattern` in its own `__dict__` as soon as its class
  statement has run.
* `substitute()` holds one placeholder while the literal text goes from
  10,000 to 100,000 to 1,000,000 characters: each 10x step costs between 3x
  and 30x in time, excluding both a constant and a quadratic scan, and the
  peak allocation grows more than 20x across the range. A value growing from
  1,000 to 100,000 characters inside a fixed three-character template grows
  the peak more than 20x, which is the v term.
* `get_identifiers()` (3.11+) holds the placeholder count while the distinct
  names go from 1 to all of them: at 1,000 and 8,000 placeholders the
  all-distinct template costs more than 20x (quadratic predicts 64x, linear
  8x), while the one-name control and the page's `dict.fromkeys()` over
  `Template.pattern.finditer()` each cost less than 20x; that alternative
  returns the same names in the same order. `is_valid()` over 100,000
  placeholders peaks under 5 KB.
* `Formatter.format()` over 1,000, 10,000 and 100,000 automatic fields costs
  between 3x and 30x per 10x step. At 1,000 fields it costs more than 3x what
  `str.format()` costs on the same string and arguments. Its peak grows more
  than 20x when a value goes from 1,000 to 100,000 characters, and when the
  format string goes from 10,000 to 1,000,000. On 3.14+ it matches
  `str.format()` for `{.real} {[0]}`; before 3.14 it raises `KeyError` there.
  A `Formatter` instance has an empty `__dict__`, and a subclass recording
  `parse()` sees the whole format string on each of three `format()` calls.
  `Formatter.parse()` on a 1,000,000-character string peaks under 5 KB and
  raises for a trailing lone brace only on the step that reaches it.
  `get_field()` on a chain of 1,000 `[0]` lookups calls `__getitem__` 1,000
  times. `vformat()` calls `check_unused_args()` exactly once, with the set
  of arguments used. `convert_field(value, None)` returns the value itself.
* `capwords()` over 2,000, 20,000 and 200,000 words costs between 3x and 30x
  per 10x step; its whitespace and separator behaviour, and the uncased
  characters where `str.title()` starts a word and it does not, are asserted
  by output.
* `templatelib.Template(*args)` (3.14+): 1,000 against 8,000 alternating
  arguments costs less than 20x, and the same counts of consecutive
  ten-character strings more than 20x (quadratic predicts 64x). `+` of a
  one-part template to one of 200 and of 20,000 interpolations peaks more
  than 20x higher for the larger, and 500 against 4,000 `+=` steps costs
  more than 20x (quadratic predicts 64x, linear 8x). `values` is a new tuple
  each access whose peak grows more than 20x over the same sizes; `strings`
  and `interpolations` are the same object on every access, and iterating a
  template of 20,000 interpolations peaks under 5 KB. A t-string literal is
  asserted to call its expressions once each and a value's `__format__`,
  `__str__` and `__repr__` never, while a field nested in the format spec is
  formatted once. `+` of two interpolation-free templates whose strings grow
  from 10,000 to 1,000,000 characters peaks 20x-300x higher.
* Every fenced Python block runs in its own subprocess. Blocks that use
  `string.templatelib` or t-string syntax run only on 3.14+, and blocks that
  call `is_valid()` or `get_identifiers()` only on 3.11+; the skipped count
  is asserted per version. A mutated assertion is asserted to fail.

Not settled here:

* Pricing a value's text by its length is a cost-model assumption; a
  `__str__` or `__format__` that does more work than it outputs is outside
  every bound on the page.
* That `Formatter.get_field()` is O(k) in the field name is read from
  Lib/string.py's loop over `_string.formatter_field_name_split()`; the test
  counts lookups, not characters.
* Placeholder names are short ASCII identifiers throughout; long names, the
  `braced` form at scale and non-default `idpattern` values are not varied.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import string
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from itertools import pairwise
from string import Formatter, Template
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "string.md"
EXPECTED_BLOCKS = 12
TEMPLATELIB_BLOCKS = 2  # blocks that need 3.14+
IDENTIFIER_BLOCKS = 1  # blocks that need 3.11+

needs_311 = pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
needs_314 = pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")


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


def _templatelib(*names: str) -> Any:
    """Names from `string.templatelib`, which exists from 3.14, typed as Any."""
    module = importlib.import_module("string.templatelib")
    values = [getattr(module, name) for name in names]
    return values[0] if len(values) == 1 else values


def assert_linear_steps(durations: list[float], label: str) -> None:
    """Each 10x step costs between 3x (not constant) and 30x (not quadratic)."""
    ratios = [later / earlier for earlier, later in pairwise(durations)]
    assert all(3 < ratio < 30 for ratio in ratios), (
        f"{label}: {durations} ns, ratios {[f'x{r:.1f}' for r in ratios]}"
    )


class TestConstants:
    """The constants are fixed module-level strings, so reading one is O(1)."""

    def test_the_classes_hold_what_their_names_say(self) -> None:
        assert string.ascii_letters == string.ascii_lowercase + string.ascii_uppercase
        assert string.ascii_lowercase == "abcdefghijklmnopqrstuvwxyz"
        assert string.digits == "0123456789"
        assert string.hexdigits == string.digits + "abcdefABCDEF"
        assert string.octdigits == "01234567"
        assert string.whitespace == " \t\n\r\x0b\x0c"
        assert len(string.punctuation) == 32
        assert all(not c.isalnum() and not c.isspace() for c in string.punctuation)

    def test_printable_is_the_four_classes_together(self) -> None:
        assert string.printable == (
            string.digits + string.ascii_letters + string.punctuation + string.whitespace
        )

    def test_reading_one_returns_the_stored_object(self) -> None:
        def read() -> str:
            return string.printable

        read()  # warm the code object before measuring

        assert read() is string.printable
        assert peak_bytes(read) == 0


class TestCapwordsIsLinear:
    """`capwords(s, sep=None)` | O(n) | O(n): split, capitalize, join."""

    def test_whitespace_collapses_without_a_separator(self) -> None:
        assert string.capwords("  hello   wORLD ") == "Hello World"

    def test_an_explicit_separator_keeps_empty_words(self) -> None:
        assert string.capwords("hello--world", sep="-") == "Hello--World"

    def test_it_differs_from_title_after_an_apostrophe(self) -> None:
        assert string.capwords("don't stop") == "Don't Stop"
        assert "don't stop".title() == "Don'T Stop"
        assert "a中b".title() == "A中B"  # an uncased letter also starts a word
        assert string.capwords("a中b") == "A中b"

    @pytest.mark.timing
    def test_ten_times_the_words_costs_about_ten_times(self) -> None:
        texts = ["hello wORLD " * (words // 2) for words in (2_000, 20_000, 200_000)]

        durations = [best_ns(lambda s=s: string.capwords(s), repeats=5) for s in texts]  # type: ignore[misc]

        assert_linear_steps(durations, "capwords")


class TestTemplateParsesNothingUntilUsed:
    """`Template(template)` | O(1) | O(1), and `Template.pattern` is compiled
    once per class, so no call after the class's first use recompiles it."""

    def test_construction_stores_the_string(self) -> None:
        text = "x" * 1_000_000 + " $a"

        peak = peak_bytes(lambda: Template(text))

        assert Template(text).template is text
        assert peak < 5_000, f"Template() allocated {peak} bytes for a 1 MB string"

    def test_a_subclass_pattern_is_compiled_with_the_class(self) -> None:
        class Percent(Template):
            delimiter = "%"

        compiled = Percent.__dict__["pattern"]
        assert isinstance(compiled, re.Pattern)
        assert "%" in compiled.pattern
        assert Percent("%who").substitute(who="Bob") == "Bob"

    def test_no_call_recompiles_the_pattern(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Percent(Template):
            delimiter = "%"

        Template("$a").substitute(a=1)  # the base class compiles lazily on 3.14

        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("re.compile was called")

        monkeypatch.setattr(re, "compile", refuse)

        assert Template("$a $$").substitute(a=1) == "1 $"
        assert Template("$a $b").safe_substitute(a=1) == "1 $b"
        assert Percent("%a").substitute(a=2) == "2"

    def test_the_class_attributes_have_their_documented_defaults(self) -> None:
        assert Template.delimiter == "$"
        assert Template.braceidpattern is None
        assert Template.pattern is Template.pattern
        assert Template.flags == re.IGNORECASE
        assert re.fullmatch(Template.idpattern, "name_1")


class TestSubstitutionScansEveryCall:
    """`substitute()` and `safe_substitute()` | O(n + v) | O(n + v)."""

    def test_every_call_runs_the_pattern_over_the_whole_template(self) -> None:
        scanned: list[str] = []

        class CountingPattern:
            def sub(self, repl: Any, text: str) -> str:
                scanned.append(text)
                return Template.pattern.sub(repl, text)

        template = Template("$a and $b")
        template.pattern = CountingPattern()  # type: ignore[assignment]

        template.substitute(a=1, b=2)
        template.safe_substitute(a=1)
        template.substitute(a=3, b=4)

        assert scanned == [template.template] * 3

    def test_the_next_call_scans_the_reassigned_template(self) -> None:
        template = Template("Hi $name")
        assert template.substitute(name="Ada") == "Hi Ada"

        template.template = "Bye $name"

        assert template.substitute(name="Ada") == "Bye Ada"

    def test_keywords_take_precedence_over_the_mapping(self) -> None:
        template = Template("$a $b")

        assert template.substitute({"a": 1, "b": 2}, b=3) == "1 3"

    def test_substitute_raises_and_safe_substitute_keeps(self) -> None:
        template = Template("$$ $a $b $")

        with pytest.raises(KeyError):
            template.substitute(a=1)
        with pytest.raises(ValueError, match="Invalid placeholder"):
            template.substitute(a=1, b=2)
        assert template.safe_substitute(a=1) == "$ 1 $b $"

    def test_the_peak_grows_with_the_template(self) -> None:
        peaks = []
        for size in (10_000, 1_000_000):
            template = Template("x" * size + " $a")
            template.substitute(a=1)
            peaks.append(peak_bytes(lambda t=template: t.substitute(a=1)))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the template: {peaks}"

    def test_the_peak_grows_with_the_values(self) -> None:
        template = Template("<$a>")
        peaks = []
        for size in (1_000, 100_000):
            value = "y" * size
            assert template.substitute(a=value) == f"<{value}>"
            peaks.append(peak_bytes(lambda v=value: template.substitute(a=v)))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the value: {peaks}"

    @pytest.mark.timing
    def test_ten_times_the_template_costs_about_ten_times(self) -> None:
        templates = [Template("x" * size + " $a") for size in (10_000, 100_000, 1_000_000)]

        durations = [best_ns(lambda t=t: t.substitute(a=1)) for t in templates]  # type: ignore[misc]

        assert_linear_steps(durations, "substitute")


@needs_311
class TestIdentifiers:
    """`is_valid()` | O(n), and `get_identifiers()` | O(n + p·u): each name is
    checked against a list of the names already found."""

    def test_is_valid(self) -> None:
        assert Template("$a ${b} $$").is_valid()  # type: ignore[attr-defined]
        assert not Template("costs $ 5").is_valid()  # type: ignore[attr-defined]

    def test_is_valid_holds_one_match_at_a_time(self) -> None:
        template = Template("$name " * 100_000)
        assert template.is_valid()  # type: ignore[attr-defined]

        peak = peak_bytes(template.is_valid)  # type: ignore[attr-defined]

        assert peak < 5_000, f"is_valid() peaked at {peak} bytes over 100,000 placeholders"

    def test_names_come_back_once_in_first_seen_order(self) -> None:
        template = Template("$user from $host; ${user} again $$")

        assert template.get_identifiers() == ["user", "host"]  # type: ignore[attr-defined]

    @staticmethod
    def names_by_dictionary(template: Template) -> list[str]:
        """The page's one-pass alternative to `get_identifiers()`."""
        return list(
            dict.fromkeys(
                match["named"] or match["braced"]
                for match in Template.pattern.finditer(template.template)
                if match["named"] or match["braced"]
            )
        )

    def test_the_dictionary_alternative_gives_the_same_names(self) -> None:
        template = Template("$b ${a} $b $$ $c ${a}")

        assert self.names_by_dictionary(template) == template.get_identifiers()  # type: ignore[attr-defined]

    @pytest.mark.timing
    def test_distinct_names_cost_quadratic_time(self) -> None:
        distinct: list[float] = []
        repeated: list[float] = []
        by_dictionary: list[float] = []
        for count in (1_000, 8_000):
            many = Template(" ".join(f"$v{index}" for index in range(count)))
            one = Template(" ".join("$v0" for _ in range(count)))
            distinct.append(best_ns(many.get_identifiers, repeats=3))  # type: ignore[attr-defined]
            repeated.append(best_ns(one.get_identifiers, repeats=3))  # type: ignore[attr-defined]
            by_dictionary.append(
                best_ns(lambda t=many: self.names_by_dictionary(t), repeats=3)  # type: ignore[misc]
            )

        distinct_ratio = distinct[1] / distinct[0]
        repeated_ratio = repeated[1] / repeated[0]
        dictionary_ratio = by_dictionary[1] / by_dictionary[0]
        assert distinct_ratio > 20, f"8x distinct names cost x{distinct_ratio:.1f}: {distinct}"
        assert repeated_ratio < 20, f"8x one repeated name cost x{repeated_ratio:.1f}: {repeated}"
        assert dictionary_ratio < 20, (
            f"8x distinct names by dictionary cost x{dictionary_ratio:.1f}: {by_dictionary}"
        )


class TestFormatter:
    """`Formatter.format()` and `vformat()` | O(n + v); `parse()` is lazy;
    the hooks are one call per field."""

    def test_it_matches_str_format(self) -> None:
        formatter = Formatter()

        for spec, args, kwargs in [
            ("{0} {1}", ("a", "b"), {}),
            ("{} {}", (1, 2), {}),
            ("{name}: {value:.2f}", (), {"name": "Price", "value": 19.99}),
            ("{0!r:>{1}}", ("x", 6), {}),
        ]:
            assert formatter.format(spec, *args, **kwargs) == spec.format(*args, **kwargs)

    def test_every_call_parses_the_whole_format_string(self) -> None:
        parsed: list[str] = []

        class Counting(Formatter):
            def parse(self, format_string: str) -> Any:
                parsed.append(format_string)
                return super().parse(format_string)

        formatter = Counting()
        for _ in range(3):
            formatter.format("{0} {1}", "a", "b")

        assert parsed == ["{0} {1}", "", ""] * 3  # the string, then each field's spec

    def test_it_holds_no_state(self) -> None:
        assert vars(Formatter()) == {}
        assert Formatter().check_unused_args({0}, (1, 2), {}) is None

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="accepted from 3.14")
    def test_unnumbered_attribute_and_index_fields_match_str_format(self) -> None:
        spec = "{.real} {[0]}"

        assert Formatter().format(spec, 3, [9]) == spec.format(3, [9]) == "3 9"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="accepted from 3.14")
    def test_unnumbered_attribute_and_index_fields_raise_before_3_14(self) -> None:
        spec = "{.real} {[0]}"

        with pytest.raises(KeyError):
            Formatter().format(spec, 3, [9])
        assert spec.format(3, [9]) == "3 9"

    def test_the_peak_grows_with_the_values(self) -> None:
        formatter = Formatter()
        peaks = []
        for size in (1_000, 100_000):
            value = "y" * size
            assert formatter.format("<{}>", value) == f"<{value}>"
            peaks.append(peak_bytes(lambda v=value: formatter.format("<{}>", v)))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the value: {peaks}"

    def test_the_peak_grows_with_the_format_string(self) -> None:
        formatter = Formatter()
        peaks = []
        for size in (10_000, 1_000_000):
            spec = "x" * size + "{}"
            formatter.format(spec, 1)
            peaks.append(peak_bytes(lambda s=spec: formatter.format(s, 1)))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the format string: {peaks}"

    def test_parse_builds_nothing_up_front(self) -> None:
        text = "x" * 1_000_000 + "{0}"

        peak = peak_bytes(lambda: Formatter().parse(text))

        assert peak < 5_000, f"parse() allocated {peak} bytes for a 1 MB string"

    def test_parse_raises_only_when_it_reaches_the_error(self) -> None:
        steps = iter(Formatter().parse("fine {0} then {"))

        assert next(steps) == ("fine ", "0", "", None)
        with pytest.raises(ValueError, match="Single '{'"):
            next(steps)

    def test_get_field_does_one_lookup_per_part(self) -> None:
        class Counting:
            calls = 0

            def __getitem__(self, index: int) -> Counting:
                Counting.calls += 1
                return self

        root = Counting()

        obj, used = Formatter().get_field("0" + "[0]" * 1_000, (root,), {})

        assert (obj, used) == (root, 0)
        assert Counting.calls == 1_000

    def test_get_value_indexes_args_or_kwargs(self) -> None:
        formatter = Formatter()

        assert formatter.get_value(1, ("a", "b"), {}) == "b"
        assert formatter.get_value("k", (), {"k": 3}) == 3

    def test_convert_field_returns_the_value_itself_without_a_conversion(self) -> None:
        value = object()
        formatter = Formatter()

        assert formatter.convert_field(value, None) is value
        assert formatter.convert_field("x", "r") == "'x'"
        assert formatter.convert_field("é", "a") == "'\\xe9'"

    def test_format_field_is_format(self) -> None:
        assert Formatter().format_field(3.14159, ".2f") == format(3.14159, ".2f")

    def test_vformat_checks_unused_args_once(self) -> None:
        calls: list[set[Any]] = []

        class Recording(Formatter):
            def check_unused_args(self, used_args: Any, args: Any, kwargs: Any) -> None:
                calls.append(set(used_args))

        Recording().vformat("{0} {x} {0}", ("a", "b"), {"x": 1, "y": 2})

        assert calls == [{0, "x"}]

    @pytest.mark.timing
    def test_ten_times_the_fields_costs_about_ten_times(self) -> None:
        formatter = Formatter()
        cases = [("{} " * count, tuple(range(count))) for count in (1_000, 10_000, 100_000)]

        durations = [
            best_ns(lambda s=s, a=a: formatter.format(s, *a), repeats=3)  # type: ignore[misc]
            for s, a in cases
        ]

        assert_linear_steps(durations, "Formatter.format")

    @pytest.mark.timing
    def test_it_is_slower_than_str_format(self) -> None:
        spec, args = "{} " * 1_000, tuple(range(1_000))
        formatter = Formatter()

        python_ns = best_ns(lambda: formatter.format(spec, *args))
        c_ns = best_ns(lambda: spec.format(*args))

        ratio = python_ns / c_ns
        assert ratio > 3, f"Formatter.format cost x{ratio:.1f} str.format on 1,000 fields"


@needs_314
class TestTemplatelib:
    """`string.templatelib`: tuples of parts, built in O(a) when strings and
    interpolations alternate; `+` copies both operands; `values` is fresh."""

    @staticmethod
    def interpolations(count: int) -> list[Any]:
        Interpolation = _templatelib("Interpolation")

        return [Interpolation(index, "index") for index in range(count)]

    def test_a_literal_evaluates_but_formats_nothing(self) -> None:
        events: list[str] = []

        class Loud:
            def __format__(self, spec: str) -> str:
                events.append("format")
                return "loud"

            def __str__(self) -> str:
                events.append("str")
                return "loud"

            def __repr__(self) -> str:
                events.append("repr")
                return "loud"

        def make() -> Loud:
            events.append("call")
            return Loud()

        template = eval("t'a {make()!r:>{4}} b'", {"make": make})

        assert events == ["call"]
        field = template.interpolations[0]
        assert (field.expression, field.conversion, field.format_spec) == ("make()", "r", ">4")

    def test_a_field_nested_in_the_spec_is_formatted(self) -> None:
        events: list[str] = []

        class Width:
            def __format__(self, spec: str) -> str:
                events.append("width")
                return "4"

        class Value:
            def __format__(self, spec: str) -> str:
                events.append("value")
                return "v"

        template = eval("t'{value:>{width}}'", {"value": Value(), "width": Width()})

        assert events == ["width"]
        assert template.interpolations[0].format_spec == ">4"

    def test_strings_and_interpolations_are_stored(self) -> None:
        Interpolation, Template = _templatelib("Interpolation", "Template")

        value = object()
        template = Template("a", Interpolation(value, "v"), "b")

        assert template.strings is template.strings
        assert template.interpolations is template.interpolations
        assert template.interpolations[0].value is value
        assert template.values is not template.values
        assert template.values == (value,)

    def test_iteration_holds_one_part_at_a_time(self) -> None:
        Template = _templatelib("Template")
        template = Template(*self.interpolations(20_000))
        list(template)

        peak = peak_bytes(lambda: sum(1 for _ in template))

        assert peak < 5_000, f"iterating 20,000 interpolations peaked at {peak} bytes"

    def test_iteration_skips_empty_strings(self) -> None:
        Interpolation, Template = _templatelib("Interpolation", "Template")

        first, second = Interpolation(1, "a"), Interpolation(2, "b")

        assert list(Template(first, second, "!")) == [first, second, "!"]

    def test_consecutive_strings_are_joined(self) -> None:
        Interpolation, Template = _templatelib("Interpolation", "Template")

        template = Template("a", "b", Interpolation(1, "x"), "c", "d")

        assert template.strings == ("ab", "cd")

    def test_adding_a_str_raises(self) -> None:
        Template = _templatelib("Template")

        with pytest.raises(TypeError, match="can only concatenate"):
            Template("a") + "b"  # type: ignore[operator]

    def test_interpolation_stores_its_arguments(self) -> None:
        Interpolation = _templatelib("Interpolation")

        value = object()
        field = Interpolation(value)

        assert field.value is value
        assert (field.expression, field.conversion, field.format_spec) == ("", None, "")

    def test_convert(self) -> None:
        convert = _templatelib("convert")

        value = object()
        assert convert(value, None) is value
        assert convert("x", "r") == "'x'"
        assert convert(1, "s") == "1"
        assert convert("é", "a") == "'\\xe9'"

    def test_adding_copies_both_operands(self) -> None:
        Template = _templatelib("Template")

        small = Template(*self.interpolations(1))
        peaks = []
        for count in (200, 20_000):
            large = Template(*self.interpolations(count))
            combined = large + small
            assert len(combined.interpolations) == count + 1
            peaks.append(peak_bytes(lambda t=large: t + small))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the parts: {peaks}"

    def test_adding_copies_the_strings_that_meet(self) -> None:
        Template = _templatelib("Template")
        peaks = []
        for size in (10_000, 1_000_000):
            left, right = Template("x" * size), Template("y" * size)
            assert (left + right).strings == ("x" * size + "y" * size,)
            peaks.append(peak_bytes(lambda a=left, b=right: a + b))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the boundary strings: {peaks}"

    def test_values_grows_with_the_interpolations(self) -> None:
        Template = _templatelib("Template")

        peaks = []
        for count in (200, 20_000):
            template = Template(*self.interpolations(count))
            peaks.append(peak_bytes(lambda t=template: t.values))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 300, f"100x the interpolations: {peaks}"

    @pytest.mark.timing
    def test_consecutive_strings_cost_quadratic_time(self) -> None:
        Template = _templatelib("Template")

        consecutive: list[float] = []
        alternating: list[float] = []
        for count in (1_000, 8_000):
            strings = ["x" * 10] * count
            mixed = [
                part for field in self.interpolations(count // 2) for part in ("x" * 10, field)
            ]
            consecutive.append(best_ns(lambda a=strings: Template(*a), repeats=3))  # type: ignore[misc]
            alternating.append(best_ns(lambda a=mixed: Template(*a), repeats=3))  # type: ignore[misc]

        consecutive_ratio = consecutive[1] / consecutive[0]
        alternating_ratio = alternating[1] / alternating[0]
        assert consecutive_ratio > 20, f"8x strings: x{consecutive_ratio:.1f}, {consecutive}"
        assert alternating_ratio < 20, f"8x alternating: x{alternating_ratio:.1f}, {alternating}"

    @pytest.mark.timing
    def test_growing_one_template_in_a_loop_is_quadratic(self) -> None:
        Template = _templatelib("Template")

        durations = []
        for count in (500, 4_000):
            pieces = [Template(field) for field in self.interpolations(count)]

            def grow(pieces: list[Any] = pieces) -> None:
                accumulated = Template()
                for piece in pieces:
                    accumulated += piece

            durations.append(best_ns(grow, repeats=3))

        ratio = durations[1] / durations[0]
        assert ratio > 20, f"8x += steps cost x{ratio:.1f}: {durations}"


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


def _minimum_version(source: str) -> tuple[int, int]:
    if "templatelib" in source:
        return (3, 14)
    if "get_identifiers" in source or "is_valid" in source:
        return (3, 11)
    return (3, 10)


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
    """Each block runs in its own subprocess and asserts its own result;
    blocks needing a newer Python than the running one are counted as skipped."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS
        versions = [_minimum_version(source) for _, source in blocks]
        assert versions.count((3, 14)) == TEMPLATELIB_BLOCKS
        assert versions.count((3, 11)) == IDENTIFIER_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        skipped: list[int] = []
        for line, source in _blocks():
            if sys.version_info < _minimum_version(source):
                skipped.append(line)
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        expected_skips = (TEMPLATELIB_BLOCKS if sys.version_info < (3, 14) else 0) + (
            IDENTIFIER_BLOCKS if sys.version_info < (3, 11) else 0
        )
        assert len(skipped) == expected_skips, skipped
        assert ran + len(skipped) == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        needle = "assert capwords('hello--world', sep='-') == 'Hello--World'"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, needle.replace("'Hello--World'", "'Hello-World'"), 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
