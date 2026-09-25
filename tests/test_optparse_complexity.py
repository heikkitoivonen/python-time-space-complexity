"""Tests for docs/stdlib/optparse.md.

The page prices `optparse` as dictionary lookups per option string, a linear
walk over the parser's options for defaults and help, and a front-of-list
removal for every consumed argument. Lookups, scans and rebuilds are settled by
counting: an `Option` subclass with a counting `__eq__` shows which operations
scan the option list, a `str` subclass with a counting `__eq__` shows the
`choice` scan, and an `Option` subclass with a counting `check_value` shows the
defaults being converted. The argument-list, abbreviation and help bounds, which
no hook can observe, are timed.

Measurement scope:

* `parse_args()` over positional arguments is timed at 2,000 and 64,000
  arguments: 32x the arguments costs more than 128x, where linear predicts
  32x and quadratic 1,024x. The same lists after `--`, and after a first
  positional with interspersed arguments disabled, cost less than 96x, so
  the remainder is copied rather than consumed. Arguments after `--` that
  look like options are asserted to come back unparsed.
* An abbreviated long option is timed against parsers of 10 and 10,000 long
  options with `values` supplied, so the defaults do not scale with the
  parser: the abbreviation costs more than 50x across that range and the
  exact spelling less than 3x. Ambiguous and unknown prefixes are asserted
  to reach `error()`, and `get_option()`/`has_option()` to reject an
  abbreviation.
* `get_default_values()` and `parse_args()` without `values` call
  `check_value` once per option with a string default, 1,000 times for
  1,000 such options; `parse_args()` given a `Values` converts no default,
  calling it once for the one command-line value, and returns that object.
* A `choice` value compares against each choice up to its match: the
  counting choices record exactly as many comparisons as the match's
  position, 1 and 1,000 for the first and last of 1,000.
* `add_option()` makes no `__eq__` comparison on a parser of 1,000 options;
  `remove_option()` of the option added after them makes 1,001 (the 1,000
  and `--help`), and a `resolve` conflict that empties that option makes the
  same scan. `add_options()` registers each option given.
* `format_help()` is timed at 200 and 3,200 options, and at one option whose
  help grows from 500 to 8,000 words: 16x the input costs less than 48x in
  both, where quadratic predicts 256x. `print_help()` is observed to make one
  `write()` whose text equals `format_help()`.
* `error()`, a bad option, a bad value and a missing value are asserted to
  raise `SystemExit(2)` with the usage on stderr; `--help` exits with status
  0 after printing the help, `--version` after printing the version.
* Declaration errors, the exception hierarchy, option groups sharing the
  parser's dictionaries, `get_option_group()`, `ensure_value()`, `append`,
  `count`, `callback`, `check_values()`, the live `largs`/`rargs`/`values`
  during a callback, `%prog` expansion, `$COLUMNS` setting the formatter
  width, `SUPPRESS_HELP`/`SUPPRESS_USAGE`, `standard_option_list` and
  `destroy()` are asserted by direct observation.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(o + h) and O(h) help bounds are read from Lib/optparse.py and Lib/textwrap.py;
  the tests show help cost is linear in option count and in help-text
  length separately, not that the two add, and neither `TitledHelpFormatter`
  nor a custom formatter is timed.
* `Values.read_module()` and `Values.read_file()`, and the per-hook
  `HelpFormatter` methods other than those the page's rows name, are left
  off the page: they are absent from the official documentation, and the
  first two cost whatever importing or executing their source costs.
* Treating option and argument strings as O(1) is a cost-model assumption;
  string lengths, callback costs, custom `check_value` costs and `nargs`
  above 2 are not varied.
"""

from __future__ import annotations

import io
import optparse
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any, NoReturn

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "optparse.md"
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


class RaisingParser(optparse.OptionParser):
    """Reports errors by raising, so a test can inspect the message."""

    def error(self, msg: str) -> NoReturn:
        raise ValueError(msg)


class CountingOption(optparse.Option):
    """An option that counts the `__eq__` comparisons made against it."""

    comparisons = 0

    def __eq__(self, other: object) -> bool:
        CountingOption.comparisons += 1
        return self is other

    __hash__ = optparse.Option.__hash__


class CountingCheckOption(optparse.Option):
    """An option that counts the values it converts."""

    checks = 0

    def check_value(self, opt: str, value: Any) -> Any:
        CountingCheckOption.checks += 1
        return super().check_value(opt, value)


class CountingChoice(str):
    """A choice string that counts the comparisons made against it."""

    comparisons = 0

    def __eq__(self, other: object) -> bool:
        CountingChoice.comparisons += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


class RecordingSink:
    """A file-like object that records each write."""

    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, text: str) -> int:
        self.writes.append(text)
        return len(text)


def counting_parser(options: int) -> optparse.OptionParser:
    parser = optparse.OptionParser(option_class=CountingOption)
    for index in range(options):
        parser.add_option(f"--opt{index}")
    return parser


class TestArgumentsAreConsumedFromTheFront:
    """`parse_args()` | O(o + d + a²): each consumed argument is deleted from
    the front of the remaining list. Arguments after `--`, or after the first
    positional with interspersed arguments disabled, are copied in O(a).

    Timed over 32x the arguments, where linear predicts 32x and quadratic
    1,024x; nothing short of a timer sees the list shift.
    """

    SMALL = 2_000
    LARGE = 64_000

    @staticmethod
    def parser() -> optparse.OptionParser:
        parser = optparse.OptionParser()
        parser.add_option("-v", action="count")
        return parser

    @pytest.mark.timing
    def test_positional_arguments_cost_quadratic_time(self) -> None:
        parser = self.parser()
        small = ["-v"] + ["x"] * self.SMALL
        large = ["-v"] + ["x"] * self.LARGE

        small_ns = best_ns(lambda: parser.parse_args(small))
        large_ns = best_ns(lambda: parser.parse_args(large), repeats=3)

        ratio = large_ns / small_ns
        assert ratio > 128, (
            f"32x the arguments cost x{ratio:.1f}; linear predicts 32x, quadratic 1,024x"
        )

    @pytest.mark.timing
    def test_arguments_after_a_double_dash_are_copied(self) -> None:
        parser = self.parser()
        small = ["-v", "--"] + ["x"] * self.SMALL
        large = ["-v", "--"] + ["x"] * self.LARGE

        small_ns = best_ns(lambda: parser.parse_args(small), inner=10)
        large_ns = best_ns(lambda: parser.parse_args(large), inner=10)

        ratio = large_ns / small_ns
        assert ratio < 96, f"32x the arguments after '--' cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_arguments_after_the_first_positional_are_copied_when_not_interspersed(
        self,
    ) -> None:
        parser = self.parser()
        parser.disable_interspersed_args()
        small = ["-v"] + ["x"] * self.SMALL
        large = ["-v"] + ["x"] * self.LARGE

        small_ns = best_ns(lambda: parser.parse_args(small), inner=10)
        large_ns = best_ns(lambda: parser.parse_args(large), inner=10)

        ratio = large_ns / small_ns
        assert ratio < 96, f"32x the trailing arguments cost x{ratio:.1f}"

    def test_arguments_after_a_double_dash_are_not_parsed(self) -> None:
        options, args = self.parser().parse_args(["-v", "--", "-v", "--help", "x"])

        assert options.v == 1
        assert args == ["-v", "--help", "x"]

    def test_not_interspersed_stops_at_the_first_positional(self) -> None:
        parser = self.parser()
        parser.disable_interspersed_args()

        options, args = parser.parse_args(["-v", "run", "-v"])
        assert options.v == 1 and args == ["run", "-v"]

        parser.enable_interspersed_args()
        options, args = parser.parse_args(["-v", "run", "-v"])
        assert options.v == 2 and args == ["run"]

    def test_the_callers_list_is_not_modified(self) -> None:
        argv = ["-v", "x"]

        self.parser().parse_args(argv)

        assert argv == ["-v", "x"]

    def test_sys_argv_is_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["prog", "-v", "x"])

        options, args = self.parser().parse_args()

        assert options.v == 1 and args == ["x"]

    def test_a_short_flag_cluster_is_one_step_per_flag(self) -> None:
        parser = self.parser()
        parser.add_option("-n", type="int")

        options, args = parser.parse_args(["-vvvn5", "x"])

        assert options.v == 3 and options.n == 5 and args == ["x"]


class TestLongOptionLookup:
    """An exact long option costs O(1) dict lookups; an abbreviation scans every
    long option string, O(L). `get_option()` and `has_option()` take exact
    strings only.

    Timed with `values` supplied so the O(o + d) defaults do not grow with
    the parser; 1,000x the long options separates O(1) from O(L).
    """

    @staticmethod
    def parser(long_options: int) -> RaisingParser:
        parser = RaisingParser(add_help_option=False)
        parser.add_option("--verbose", action="store_true")
        for index in range(long_options):
            parser.add_option(f"--opt{index:06d}", action="store_true")
        return parser

    @pytest.mark.timing
    def test_an_abbreviation_scans_the_long_options(self) -> None:
        small, large = self.parser(10), self.parser(10_000)

        def cost(parser: RaisingParser, arg: str) -> float:
            return best_ns(lambda: parser.parse_args([arg], optparse.Values()), inner=50)

        abbreviated = cost(large, "--verb") / cost(small, "--verb")
        exact = cost(large, "--verbose") / cost(small, "--verbose")

        assert abbreviated > 50, f"1,000x the long options cost an abbreviation x{abbreviated:.1f}"
        assert exact < 3, f"1,000x the long options cost an exact option x{exact:.1f}"

    def test_a_unique_prefix_resolves(self) -> None:
        options, _ = self.parser(0).parse_args(["--verb"])

        assert options.verbose is True

    def test_an_ambiguous_prefix_is_an_error(self) -> None:
        parser = self.parser(0)
        parser.add_option("--version-file")

        with pytest.raises(ValueError, match="ambiguous option: --ver"):
            parser.parse_args(["--ver"])

    def test_an_unknown_option_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="no such option: --nope"):
            self.parser(0).parse_args(["--nope"])

    def test_lookups_do_not_accept_abbreviations(self) -> None:
        parser = self.parser(0)

        assert parser.get_option("--verb") is None
        assert not parser.has_option("--verb")
        assert parser.get_option("--verbose") is not None
        assert parser.has_option("--verbose")

    def test_a_value_can_be_attached_with_an_equals_sign(self) -> None:
        parser = self.parser(0)
        parser.add_option("--file")

        options, _ = parser.parse_args(["--file=a=b"])

        assert options.file == "a=b"

    def test_a_flag_given_a_value_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="does not take a value"):
            self.parser(0).parse_args(["--verbose=1"])


class TestDefaultsAreBuiltPerParse:
    """`get_default_values()` | O(o + d): it copies the defaults and converts
    each string default. `parse_args()` does the same unless `values` is
    passed. Counted by `check_value` calls, with no tolerance."""

    OPTIONS = 1_000

    def parser(self) -> optparse.OptionParser:
        parser = optparse.OptionParser(option_class=CountingCheckOption)
        for index in range(self.OPTIONS):
            parser.add_option(f"--opt{index}", type="int", default=str(index))
        return parser

    def test_get_default_values_converts_every_string_default(self) -> None:
        parser = self.parser()
        CountingCheckOption.checks = 0

        values = parser.get_default_values()

        assert CountingCheckOption.checks == self.OPTIONS
        assert values.opt999 == 999

    def test_parse_args_rebuilds_the_defaults_each_call(self) -> None:
        parser = self.parser()
        CountingCheckOption.checks = 0

        parser.parse_args([])
        parser.parse_args([])

        assert CountingCheckOption.checks == 2 * self.OPTIONS

    def test_passing_values_skips_the_defaults(self) -> None:
        parser = self.parser()
        values = optparse.Values()
        CountingCheckOption.checks = 0

        options, _ = parser.parse_args(["--opt5", "7"], values=values)

        assert CountingCheckOption.checks == 1
        assert options is values
        assert values.opt5 == 7
        assert not hasattr(values, "opt6")

    def test_set_defaults_and_set_default_reach_the_values(self) -> None:
        parser = optparse.OptionParser()
        parser.set_defaults(level="info", depth=2)
        parser.set_default("mode", "fast")

        values = parser.get_default_values()

        assert (values.level, values.depth, values.mode) == ("info", 2, "fast")

    def test_process_default_values_off_leaves_strings_alone(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option("-n", type="int", default="5")
        parser.set_process_default_values(False)

        assert parser.get_default_values().n == "5"

    def test_values_holds_one_attribute_per_default(self) -> None:
        values = optparse.Values({"a": 1, "b": None})

        assert vars(values) == {"a": 1, "b": None}
        assert values == {"a": 1, "b": None}
        assert values.ensure_value("b", []) == []
        assert values.ensure_value("a", 5) == 1


class TestChoiceScansItsChoices:
    """`check_choice()` | O(c): a `choice` value is looked up in the choices
    sequence by comparison, counted exactly with counting choice strings."""

    CHOICES = 1_000

    def test_comparisons_track_the_matchs_position(self) -> None:
        choices: list[str] = [CountingChoice(f"c{index}") for index in range(self.CHOICES)]
        parser = optparse.OptionParser()
        parser.add_option("--mode", type="choice", choices=choices)

        CountingChoice.comparisons = 0
        options, _ = parser.parse_args(["--mode", "c0"], optparse.Values())
        first = CountingChoice.comparisons

        CountingChoice.comparisons = 0
        options, _ = parser.parse_args(["--mode", "c999"], optparse.Values())
        last = CountingChoice.comparisons

        assert (first, last) == (1, self.CHOICES)
        assert options.mode == "c999"

    def test_an_invalid_choice_is_an_error(self) -> None:
        parser = RaisingParser()
        parser.add_option("--mode", choices=["fast", "safe"])

        with pytest.raises(ValueError, match="invalid choice: 'slow'"):
            parser.parse_args(["--mode", "slow"])

    def test_the_numeric_checker_converts_and_rejects(self) -> None:
        option = optparse.Option("-n", type="float")

        assert optparse.check_builtin(option, "-n", "2.5") == 2.5
        with pytest.raises(optparse.OptionValueError, match="invalid floating-point"):
            optparse.check_builtin(option, "-n", "many")


class TestAddingIsConstantRemovingScans:
    """`add_option()` | O(1): dict entries per option string, no scan of the
    option list. `remove_option()` | O(o): the option is removed from its
    container's list by comparison. Counted with a counting `__eq__`."""

    OPTIONS = 1_000

    def test_adding_makes_no_comparison(self) -> None:
        parser = counting_parser(self.OPTIONS)
        CountingOption.comparisons = 0

        parser.add_option("--last")

        assert CountingOption.comparisons == 0

    def test_removing_the_last_option_scans_the_list(self) -> None:
        parser = counting_parser(self.OPTIONS)
        parser.add_option("--last")
        CountingOption.comparisons = 0

        parser.remove_option("--last")

        # Every other option, plus the --help option added first
        assert CountingOption.comparisons == self.OPTIONS + 1
        assert not parser.has_option("--last")

    def test_a_resolved_conflict_that_empties_an_option_scans_too(self) -> None:
        parser = optparse.OptionParser(option_class=CountingOption, conflict_handler="resolve")
        for index in range(self.OPTIONS):
            parser.add_option(f"--opt{index}")
        parser.add_option("--last")
        CountingOption.comparisons = 0

        parser.add_option("--last", dest="replacement")

        assert CountingOption.comparisons == self.OPTIONS + 1
        replacement = parser.get_option("--last")
        assert replacement is not None and replacement.dest == "replacement"

    def test_removing_an_unknown_option_raises(self) -> None:
        with pytest.raises(ValueError, match="no such option"):
            optparse.OptionParser().remove_option("--nope")

    def test_add_options_and_the_constructor_register_each_option(self) -> None:
        options = [optparse.make_option(f"--o{index}") for index in range(3)]
        parser = optparse.OptionParser(option_list=options[:2])
        parser.add_options(options[2:])

        assert all(parser.get_option(f"--o{index}") is options[index] for index in range(3))

    def test_standard_option_list_is_added_to_each_parser(self) -> None:
        class Standard(optparse.OptionParser):
            standard_option_list = [optparse.make_option("--std")]

        first, second = Standard(), Standard()

        assert first.has_option("--std") and second.has_option("--std")

    def test_an_existing_option_instance_can_be_added(self) -> None:
        parser = optparse.OptionParser()
        option = optparse.Option("-x", action="store_true")

        assert parser.add_option(option) is option
        assert option.takes_value() is False
        assert option.get_opt_string() == "-x"


class TestDeclarationErrors:
    """`OptionError` and `OptionConflictError` are raised while options are
    declared; `OptParseError` is the base of every optparse exception."""

    def test_invalid_attributes_raise_at_declaration(self) -> None:
        with pytest.raises(optparse.OptionError, match="must supply a list of choices"):
            optparse.Option("--x", type="choice")
        with pytest.raises(optparse.OptionError, match="invalid action"):
            optparse.Option("--x", action="nope")

    def test_a_reused_string_is_a_conflict(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option("-x")

        with pytest.raises(optparse.OptionConflictError, match="conflicting option string"):
            parser.add_option("-x")

    def test_the_hierarchy(self) -> None:
        for name in (
            "OptionError",
            "OptionConflictError",
            "BadOptionError",
            "AmbiguousOptionError",
            "OptionValueError",
        ):
            assert issubclass(getattr(optparse, name), optparse.OptParseError)
        assert issubclass(optparse.AmbiguousOptionError, optparse.BadOptionError)
        assert issubclass(optparse.OptionConflictError, optparse.OptionError)

    def test_option_attributes_come_from_the_keyword_arguments(self) -> None:
        option = optparse.Option(
            "-n", "--num", type="int", default=3, help="h", metavar="N", dest="num"
        )

        assert (option.action, option.type, option.dest, option.default) == (
            "store",
            "int",
            "num",
            3,
        )
        assert (option.nargs, option.const, option.choices, option.help, option.metavar) == (
            1,
            None,
            None,
            "h",
            "N",
        )
        assert (option.callback, option.callback_args, option.callback_kwargs) == (
            None,
            None,
            None,
        )


class TestActions:
    """`Option.process()`/`take_action()` | O(1) per value, plus a callback's
    own cost; `append` grows one list."""

    def test_store_append_count_and_consts(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option("-I", dest="include", action="append")
        parser.add_option("-q", action="count")
        parser.add_option("--fast", dest="mode", action="store_const", const="fast")
        parser.add_option("--tag", dest="tags", action="append_const", const="t")
        parser.add_option("--off", dest="on", action="store_false")
        parser.add_option("--pair", nargs=2, type="int")

        options, _ = parser.parse_args(
            ["-I", "a", "-Ib", "-qq", "--fast", "--tag", "--tag", "--off", "--pair", "1", "2"]
        )

        assert options.include == ["a", "b"]
        assert options.q == 2
        assert options.mode == "fast"
        assert options.tags == ["t", "t"]
        assert options.on is False
        assert options.pair == (1, 2)

    def test_append_extends_one_list(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option("-I", dest="include", action="append")

        options, _ = parser.parse_args(["-Ia"])
        first = options.include
        parser.parse_args(["-Ib"], values=options)

        assert options.include is first and first == ["a", "b"]

    def test_a_callback_sees_the_live_parse_state(self) -> None:
        seen: list[tuple[Any, ...]] = []

        def callback(
            option: optparse.Option, opt: str, value: Any, parser: optparse.OptionParser
        ) -> None:
            assert parser.largs is not None and parser.rargs is not None
            seen.append((opt, value, list(parser.largs), list(parser.rargs), parser.values))

        parser = optparse.OptionParser()
        parser.add_option("--mark", action="callback", callback=callback, type="int")

        values, _ = parser.parse_args(["x", "--mark", "3", "y", "--mark", "4"])

        assert seen == [
            ("--mark", 3, ["x"], ["y", "--mark", "4"], values),
            ("--mark", 4, ["x", "y"], [], values),
        ]

    def test_process_and_convert_value(self) -> None:
        option = optparse.Option("-n", type="int")
        values = optparse.Values()

        assert option.convert_value("-n", "0x10") == 16
        assert option.check_value("-n", "7") == 7
        option.process("-n", "4", values, optparse.OptionParser())
        assert values.n == 4
        option.take_action("store", "n", "-n", 9, values, optparse.OptionParser())
        assert values.n == 9

    def test_check_values_is_called_with_the_result(self) -> None:
        class Checked(optparse.OptionParser):
            def check_values(
                self, values: optparse.Values, args: list[str]
            ) -> tuple[optparse.Values, list[str]]:
                return values, [arg.upper() for arg in args]

        assert Checked().parse_args(["a"])[1] == ["A"]
        values = optparse.Values()
        assert optparse.OptionParser().check_values(values, ["a"]) == (values, ["a"])


class TestOptionGroupsShareTheParsersDictionaries:
    """`OptionGroup` | O(1): it shares its parser's option dictionaries, so
    parsing ignores groups and an option string is unique across them."""

    def test_a_grouped_option_is_the_parsers_option(self) -> None:
        parser = optparse.OptionParser()
        group = parser.add_option_group("Debug", "debug options")
        option = group.add_option("--trace", action="store_true")

        assert parser.get_option("--trace") is option
        assert parser.get_option_group("--trace") is group
        assert parser.parse_args(["--trace"])[0].trace is True

    def test_a_parser_option_is_in_no_group(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option("-x")

        assert parser.get_option_group("-x") is None

    def test_a_string_is_unique_across_groups(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option_group("A").add_option("--x")

        with pytest.raises(optparse.OptionConflictError):
            parser.add_option_group("B").add_option("--x")

    def test_an_existing_group_can_be_added_and_retitled(self) -> None:
        parser = optparse.OptionParser()
        group = optparse.OptionGroup(parser, "Old")
        group.set_title("New")

        assert parser.add_option_group(group) is group
        assert isinstance(group, optparse.OptionContainer)
        group.add_option("--x", help="x help")
        assert "New:" in parser.format_help()

    def test_destroy_breaks_the_parser(self) -> None:
        parser = optparse.OptionParser()
        parser.add_option_group("A")

        parser.destroy()

        assert not hasattr(parser, "option_list")
        assert not hasattr(parser, "option_groups")


class TestHelpIsLinear:
    """`format_help()`/`print_help()` | O(o + h) time and space: the whole
    text is built as one string and written once.

    Timed over 16x the options and 16x the help text, where quadratic
    predicts 256x.
    """

    @staticmethod
    def parser(options: int, words: int) -> optparse.OptionParser:
        formatter = optparse.IndentedHelpFormatter(width=80)
        parser = optparse.OptionParser(prog="tool", formatter=formatter)
        for index in range(options):
            parser.add_option(f"--opt{index}", help=" ".join(["word"] * words))
        return parser

    @pytest.mark.timing
    def test_help_is_linear_in_options(self) -> None:
        small, large = self.parser(200, 5), self.parser(3_200, 5)

        ratio = best_ns(large.format_help) / best_ns(small.format_help)

        assert ratio < 48, f"16x the options cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_help_is_linear_in_help_text(self) -> None:
        small, large = self.parser(1, 500), self.parser(1, 8_000)

        ratio = best_ns(large.format_help) / best_ns(small.format_help)

        assert ratio < 48, f"16x the help text cost x{ratio:.1f}"

    def test_print_help_writes_once(self) -> None:
        parser = self.parser(50, 5)
        sink = RecordingSink()

        parser.print_help(sink)  # type: ignore[arg-type]

        assert sink.writes == [parser.format_help()]

    def test_the_pieces_format_help_joins(self) -> None:
        parser = optparse.OptionParser(
            prog="tool", description="%prog does things", epilog="See %prog.", version="%prog 1.0"
        )

        text = parser.format_help()

        assert parser.get_usage() == "Usage: tool [options]\n"
        assert parser.get_description() == "tool does things"
        assert parser.get_version() == "tool 1.0"
        assert parser.expand_prog_name("%prog!") == "tool!"
        assert parser.get_prog_name() == "tool"
        assert parser.format_option_help() in text
        assert parser.format_description(parser.formatter) in text
        assert parser.format_epilog(parser.formatter) in text
        assert "See %prog." in text

    def test_print_usage_and_version(self) -> None:
        parser = optparse.OptionParser(prog="tool", version="%prog 1.0")
        usage, version = io.StringIO(), io.StringIO()

        parser.print_usage(usage)
        parser.print_version(version)

        assert usage.getvalue() == "Usage: tool [options]\n\n"
        assert version.getvalue() == "tool 1.0\n"

    def test_prog_defaults_to_the_script_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["/usr/bin/tool.py"])

        assert optparse.OptionParser().get_prog_name() == "tool.py"

    def test_columns_sets_the_width(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COLUMNS", "50")

        assert optparse.IndentedHelpFormatter().width == 48
        assert optparse.TitledHelpFormatter(width=70).width == 70
        assert isinstance(optparse.TitledHelpFormatter(), optparse.HelpFormatter)

    def test_suppressed_help_and_usage(self) -> None:
        parser = optparse.OptionParser(usage=optparse.SUPPRESS_USAGE)
        parser.add_option("--hidden", help=optparse.SUPPRESS_HELP)

        text = parser.format_help()

        assert "--hidden" not in text
        assert "Usage" not in text

    def test_other_setters(self) -> None:
        parser = optparse.OptionParser()
        parser.set_usage("%prog FILE")
        parser.set_description("about")
        parser.set_conflict_handler("resolve")

        assert parser.usage == "%prog FILE"
        assert parser.description == "about"
        assert parser.conflict_handler == "resolve"


class TestErrorsExit:
    """`error()` prints the usage and message to stderr and raises
    `SystemExit(2)`; `parse_args()` turns every parse error into `error()`,
    and `--help`/`--version` exit with status 0."""

    @staticmethod
    def parser() -> optparse.OptionParser:
        parser = optparse.OptionParser(prog="tool", version="1.0")
        parser.add_option("-n", type="int")
        return parser

    @pytest.mark.parametrize(
        ("argv", "message"),
        [
            (["--nope"], "no such option: --nope"),
            (["-n", "x"], "option -n: invalid integer value: 'x'"),
            (["-n"], "-n option requires 1 argument"),
        ],
    )
    def test_parse_errors_exit_with_status_two(
        self, argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as caught:
            self.parser().parse_args(argv)

        assert caught.value.code == 2
        err = capsys.readouterr().err
        assert err.startswith("Usage: tool [options]")
        assert f"tool: error: {message}" in err

    def test_help_and_version_exit_with_status_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as caught:
            self.parser().parse_args(["--help"])
        assert caught.value.code == 0
        assert "--version" in capsys.readouterr().out

        with pytest.raises(SystemExit) as caught:
            self.parser().parse_args(["--version"])
        assert caught.value.code == 0
        assert capsys.readouterr().out == "1.0\n"

    def test_exit_raises_system_exit(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as caught:
            self.parser().exit(3, "bye\n")

        assert caught.value.code == 3
        assert capsys.readouterr().err == "bye\n"


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
        line, source = next((n, s) for n, s in _blocks() if "options.n == 3" in s)
        mutated = source.replace("options.n == 3", "options.n == 4", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
