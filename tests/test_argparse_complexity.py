"""Tests for docs/stdlib/argparse.md.

The page prices declaration as constant per argument, parsing as a walk over
the command line plus a visit to every declared argument, and help as linear
in the text produced. Growth in the parser's size is settled by timing ratios
over a 100x change in the declared arguments, where the documented shapes
differ by one or two orders of magnitude; per-occurrence copying, iteration
over `choices` and the rest of the command line each option examines are
settled by observation; everything else is asserted directly.

Measurement scope:

* `add_argument()` costs the same with 100 and 10,000 arguments already
  declared (asserted under 3x; measured about 1x). With `choices`, a counting
  container shows every value iterated when the argument is added, and not
  again on a successful parse of a set-like container; the traced peak grows
  between 30x and 300x from 1,000 to 100,000 choices (measured about 100x).
  Redeclaring the newest of 10,000 options under `conflict_handler='resolve'`
  costs more than 8x redeclaring it among 100 (measured 17x to 41x on
  3.10-3.14).
* Behind a `metavar`, a counting container shows the usage line iterating no
  choices, and help iterating all of them: for a plain help string before
  3.14, and from 3.14 only for one containing `%`, which is then also expanded
  when the argument is added. `nargs=REMAINDER` is asserted to accept a value
  outside `choices`.
* `parse_args([])`, `get_default()` of an unknown name and `set_defaults()`
  grow more than 20x from 100 to 10,000 declared options (measured 75x to
  170x on 3.10-3.14), which is the O(a) term; the defaults of every declared
  argument are asserted present on the namespace.
* Each string beginning with `-` that is not an exact spelling costs a scan of
  the option spellings: on a parser of 2,000 options, 200 abbreviations,
  bundled `-qr` strings or negative numbers cost more than 5x the same count
  of exact spellings, separate flags or plain numbers (measured 11x to 50x).
  200 unknown long options cost more than 4x with abbreviations allowed than
  with `allow_abbrev=False` (measured 13x to 17x).
* The n·k term: a recording subclass of `ArgumentParser._match_argument` shows
  each option handed the whole rest of the command line's pattern, so 1,000
  options ahead of 1,000 positionals are handed suffixes totalling more than a
  million characters. The time this costs is the slice that builds each
  suffix in `consume_optional` (Lib/argparse.py); the regex match itself need
  not read past the option's own values, and is not observed. On 3.12 and earlier, 8x the options (1,000 to 8,000
  `-v` flags) costs more than 25x (measured about 60x); on 3.13+ it costs
  under 25x (measured about 9x), which is the page's "far smaller sizes".
* `append` and `extend` copy their list on every occurrence: a list subclass
  default whose `__copy__` records its length sees lengths 0 to r-1 for r
  occurrences. A
  plain list goes through `items[:]` in `_copy_items` in Lib/argparse.py,
  which is read, not measured; the default list is asserted unchanged.
* A mutually exclusive group of 1,600 members costs more than 25x one of 200
  on an empty parse (measured 90x to 115x; linear would be 8x), and its traced
  peak grows more than 8x from 200 to 800 members (measured 15x; linear
  would be 4x).
* Dispatching to one of 10,000 subcommands costs under 3x dispatching to one
  of 10 (measured about 1x). The subparser's values are asserted copied onto
  the parent's namespace.
* `format_help()` over 1,600 options costs between 6x and 60x the same over
  100 (measured about 17x; quadratic would be 256x), and two calls return
  equal strings that are distinct objects. A formatter-counting
  `formatter_class` builds none during a successful parse and at least one
  for an error. Only `parse_args()` is observed; the intermixed forms rendering
  the usage line before 3.12.8 and 3.13.1 is read from those releases' source.
* `parse_args()` peaks under 30x from 10,000 to 100,000 positional strings
  (measured about 10x; quadratic space would be 100x).
* `vars(namespace)` is the namespace's `__dict__` by identity; `in`,
  equality, `Namespace(**kwargs)`, `FileType` opening at conversion,
  `BooleanOptionalAction`'s `--no-` spelling, `Action.format_usage()`,
  `register()`, `convert_arg_line_to_args()` once per argument-file line,
  `error()` and `exit()` raising `SystemExit`, and `parse_intermixed_args()`
  raising `TypeError` with subcommands are asserted by behaviour.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The assumptions of a handful of positional arguments, of spellings per
  argument and aliases per subcommand, and of few mutually exclusive groups
  are scoping choices. Many small groups also make the usage formatter's
  search for each group's first member quadratic, which is not priced.
* `parents=` copying O(a) arguments, and help formatting visiting arguments
  whose help is `SUPPRESS`, are read from Lib/argparse.py and not measured.
* The option-spelling timings hold the parser at 2,000 options and compare
  scanned strings with exact ones; the parser size is not varied there.
* With p positionals interleaved with options, each option re-tries matching
  up to p positionals, which is not priced.
* Pricing `type` conversion, actions, `choices` membership and the comparison
  of two attribute values at O(1) is a cost-model assumption; a `choices` list
  is scanned, and `namespace == other` compares values as deep as they are.
* `add_subparsers()` is O(a) from Lib/argparse.py, where building the
  subcommands' `prog` renders the usage of the parser's positionals after
  scanning its actions; it is not timed.
* `ArgumentParser()`, `add_argument_group()`, `add_mutually_exclusive_group()`,
  `add_parser()`, `register()`, the formatter classes, the exceptions and the
  constants are O(1) by reading the constructors; only `add_argument()` and
  dispatch are timed.
* The five formatter classes' methods (`add_argument`, `add_usage`,
  `format_help`, `start_section` and the rest) are undocumented formatter
  internals, reported by the audit as needing classification; the page prices
  the classes by what they render.
* A short option with its value attached (`-n5`) takes the same scan as the
  three spellings timed, and is asserted to parse but not timed. Reading an
  argument file is linear in its size by reading `_read_args_from_files`; its
  size is not varied.
* Help text with a long description or many choices is not varied apart from
  the option count; the O(h) bound is read from HelpFormatter, which wraps
  each block of text with textwrap. That bound assumes words shorter than a
  line: `textwrap` splits a longer word by slicing off one line at a time,
  copying the rest each time, and that case is not priced.
* `error()`'s O(m) term for the message and `exit()` writing its message are
  read from Lib/argparse.py; the message length is not varied.
* A `range` in `choices` answers `in` arithmetically only for `int` values,
  so the page names a set, not a `range`, as the unscanned container.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "argparse.md"
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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def parser_with_options(count: int, **kwargs: Any) -> argparse.ArgumentParser:
    """A parser declaring `count` long options, each with a help string."""
    parser = argparse.ArgumentParser(prog="tool", **kwargs)
    for index in range(count):
        parser.add_argument(f"--option{index:05d}", help=f"help text {index}")
    return parser


def exclusive_group_parser(members: int) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    for index in range(members):
        group.add_argument(f"--member{index}", action="store_true")
    return parser


class CountingChoices:
    """A choices container that counts values handed out by iteration."""

    def __init__(self, values: range) -> None:
        self.values = values
        self.iterated = 0

    def __iter__(self) -> Iterator[int]:
        for value in self.values:
            self.iterated += 1
            yield value

    def __contains__(self, value: object) -> bool:
        return value in self.values


class TestDeclaringArguments:
    """`add_argument()` | O(1), or O(c) with `choices`."""

    @pytest.mark.timing
    def test_adding_an_argument_does_not_grow_with_the_parser(self) -> None:
        def cost(existing: int) -> float:
            parser = parser_with_options(existing)
            counter = iter(range(10**9))
            return best_ns(lambda: parser.add_argument(f"--new{next(counter)}"), inner=50)

        small, large = cost(100), cost(10_000)

        assert large < small * 3, (
            f"add_argument cost {large:.0f}ns after 10,000 arguments against {small:.0f}ns "
            "after 100; the row claims O(1)"
        )

    def test_choices_are_all_rendered_when_the_argument_is_added(self) -> None:
        choices = CountingChoices(range(5_000))
        parser = argparse.ArgumentParser(exit_on_error=False)

        parser.add_argument("--pick", type=int, choices=choices)

        assert choices.iterated >= 5_000, f"add_argument iterated {choices.iterated} choices"

        before = choices.iterated
        assert parser.parse_args(["--pick", "42"]).pick == 42
        assert choices.iterated == before, "a successful parse iterated the choices"

    def test_usage_lists_every_choice(self) -> None:
        parser = argparse.ArgumentParser(prog="p")
        parser.add_argument("--pick", type=int, choices=range(20))

        usage = parser.format_usage()

        assert "{" + ",".join(str(value) for value in range(20)) + "}" in usage

    def test_choices_take_linear_space_when_the_argument_is_added(self) -> None:
        def peak(count: int) -> int:
            parser = argparse.ArgumentParser()
            return peak_bytes(lambda: parser.add_argument("--x", type=int, choices=range(count)))

        small, large = peak(1_000), peak(100_000)

        assert small * 30 < large < small * 300, (
            f"100x the choices peaked x{large / small:.1f}; quadratic predicts 10,000"
        )

    @pytest.mark.parametrize(
        ("help_text", "formatter"),
        [
            ("pick one", argparse.HelpFormatter),
            ("pick one", argparse.ArgumentDefaultsHelpFormatter),
        ],
        ids=["plain-help", "defaults-formatter"],
    )
    def test_help_expands_choices_behind_a_metavar_by_version_and_formatter(
        self, help_text: str, formatter: type[argparse.HelpFormatter]
    ) -> None:
        choices = CountingChoices(range(1_000))
        parser = argparse.ArgumentParser(prog="p", formatter_class=formatter)

        parser.add_argument("--pick", type=int, choices=choices, metavar="N", help=help_text)
        added = choices.iterated
        parser.format_usage()
        in_usage = choices.iterated - added
        parser.format_help()
        in_help = choices.iterated - added - in_usage

        expanded = sys.version_info < (3, 14) or formatter is argparse.ArgumentDefaultsHelpFormatter
        assert in_usage == 0
        assert in_help == (1_000 if expanded else 0)
        assert added == (1_000 if expanded and sys.version_info >= (3, 14) else 0)

    def test_remainder_skips_the_choices_check(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("rest", nargs=argparse.REMAINDER, choices=["allowed"])

        assert parser.parse_args(["other"]).rest == ["other"]

    @pytest.mark.timing
    def test_resolving_a_conflict_scans_the_arguments(self) -> None:
        def cost(existing: int) -> float:
            parser = parser_with_options(existing, conflict_handler="resolve")
            newest = f"--option{existing - 1:05d}"
            return best_ns(lambda: parser.add_argument(newest), inner=20)

        ratio = cost(10_000) / cost(100)

        assert ratio > 8, f"100x the arguments cost x{ratio:.1f} to redeclare the newest"


class TestEveryParseVisitsEveryArgument:
    """`parse_args()` | O(a + n + n·k + a·s): the O(a) term is paid on every call,
    and `get_default()` | O(a), `set_defaults()` | O(a + d)."""

    @pytest.mark.timing
    def test_an_empty_command_line_costs_the_parser_size(self) -> None:
        small = parser_with_options(100)
        large = parser_with_options(10_000)

        small_ns = best_ns(lambda: small.parse_args([]))
        large_ns = best_ns(lambda: large.parse_args([]))

        ratio = large_ns / small_ns
        assert ratio > 20, f"100x the declared options cost x{ratio:.1f} on an empty parse"

    @pytest.mark.timing
    def test_get_default_and_set_defaults_scan_the_arguments(self) -> None:
        small = parser_with_options(100)
        large = parser_with_options(10_000)

        get_ratio = best_ns(lambda: large.get_default("absent")) / best_ns(
            lambda: small.get_default("absent")
        )
        set_ratio = best_ns(lambda: large.set_defaults(absent=1)) / best_ns(
            lambda: small.set_defaults(absent=1)
        )

        assert get_ratio > 20, f"get_default grew x{get_ratio:.1f} for 100x the arguments"
        assert set_ratio > 20, f"set_defaults grew x{set_ratio:.1f} for 100x the arguments"

    def test_every_default_lands_on_the_namespace(self) -> None:
        parser = parser_with_options(50)

        namespace = parser.parse_args([])

        assert len(vars(namespace)) == 50
        assert all(value is None for value in vars(namespace).values())

    def test_get_default_falls_back_to_parser_level_defaults(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--level", default=1)

        parser.set_defaults(level=2, handler="run")

        assert parser.get_default("level") == 2
        assert parser.get_default("handler") == "run"
        assert parser.get_default("missing") is None


class TestOptionSpellings:
    """An exact spelling is a dict lookup; any other string starting with `-`
    adds an O(a) scan of the option spellings."""

    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        parser = parser_with_options(2_000)
        parser.add_argument("--zebra", action="store_true")
        parser.add_argument("-q", action="store_true")
        parser.add_argument("-r", action="store_true")
        parser.add_argument("numbers", nargs="*", type=int)
        return parser

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("scanned", "exact"),
        [
            (["--zeb"] * 200, ["--zebra"] * 200),
            (["-qr"] * 200, ["-q", "-r"] * 100),
            (["-1"] * 200, ["1"] * 200),
        ],
        ids=["abbreviation", "bundled-flags", "negative-number"],
    )
    def test_a_non_exact_spelling_scans_the_parser(
        self, scanned: list[str], exact: list[str]
    ) -> None:
        parser = self._parser()

        scanned_ns = best_ns(lambda: parser.parse_args(scanned))
        exact_ns = best_ns(lambda: parser.parse_args(exact))

        ratio = scanned_ns / exact_ns
        assert ratio > 5, (
            f"200 strings like {scanned[0]!r} cost x{ratio:.1f} the exact form on a "
            "2,000-option parser; a per-string O(a) scan predicts far more than 1"
        )

    def test_the_spellings_parse_as_documented(self) -> None:
        parser = self._parser()

        assert parser.parse_args(["--zeb"]).zebra is True
        bundled = parser.parse_args(["-qr"])
        assert bundled.q and bundled.r
        assert parser.parse_args(["-1", "-2"]).numbers == [-1, -2]
        assert parser.parse_args(["--option00001=v"]).option00001 == "v"

    def test_allow_abbrev_false_rejects_long_abbreviations_only(self) -> None:
        parser = argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("-x", action="store_true")
        parser.add_argument("-y", action="store_true")

        assert parser.parse_known_args(["--verb"])[1] == ["--verb"]
        both = parser.parse_args(["-xy"])
        assert both.x and both.y

    @pytest.mark.timing
    def test_allow_abbrev_false_skips_the_scan_for_unknown_long_options(self) -> None:
        unknown = ["--zzz"] * 200
        scanning = parser_with_options(2_000)
        strict = parser_with_options(2_000, allow_abbrev=False)

        ratio = best_ns(lambda: scanning.parse_known_args(unknown)) / best_ns(
            lambda: strict.parse_known_args(unknown)
        )

        assert ratio > 4, f"abbreviations cost x{ratio:.1f} on 200 unknown long options"


class TestEachOptionExaminesTheRest:
    """`parse_args()` | O(a + n + n·k + a·s): each option matches its values
    against the rest of the command line."""

    def test_each_option_is_handed_the_rest_of_the_command_line(self) -> None:
        lengths: list[int] = []

        class Recording(argparse.ArgumentParser):
            def _match_argument(self, action: Any, arg_strings_pattern: str) -> int:
                lengths.append(len(arg_strings_pattern))
                return super()._match_argument(action, arg_strings_pattern)  # type: ignore[misc]

        parser = Recording()
        parser.add_argument("-v", action="count")
        parser.add_argument("rest", nargs="*")

        parser.parse_args(["-v"] * 1_000 + ["x"] * 1_000)

        assert len(lengths) == 1_000
        assert lengths[0] == 1_999 and lengths[-1] == 1_000
        assert sum(lengths) > 1_000_000, (
            f"1,000 options were handed {sum(lengths)} pattern characters"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="the option rescan left in 3.13")
    def test_options_are_quadratic_at_small_sizes_through_3_12(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("-v", action="count")
        few, many = ["-v"] * 1_000, ["-v"] * 8_000

        ratio = best_ns(lambda: parser.parse_args(many), repeats=3) / best_ns(
            lambda: parser.parse_args(few), repeats=3
        )

        assert ratio > 25, f"8x the options cost x{ratio:.1f}; quadratic predicts 64"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the option rescan is 3.12 and earlier")
    def test_options_are_near_linear_at_the_same_sizes_from_3_13(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("-v", action="count")
        few, many = ["-v"] * 1_000, ["-v"] * 8_000

        ratio = best_ns(lambda: parser.parse_args(many), repeats=3) / best_ns(
            lambda: parser.parse_args(few), repeats=3
        )

        assert ratio < 25, f"8x the options cost x{ratio:.1f}; linear predicts 8"


class TestAppendCopiesPerOccurrence:
    """An `append` or `extend` option repeated r times costs O(r²): the list is
    copied on every occurrence."""

    @pytest.mark.parametrize("action", ["append", "extend"])
    def test_each_occurrence_copies_the_whole_list(self, action: str) -> None:
        copied: list[int] = []

        class Recorded(list):  # type: ignore[type-arg]
            def __copy__(self) -> Recorded:
                copied.append(len(self))
                return Recorded(self)

        parser = argparse.ArgumentParser()
        nargs = "+" if action == "extend" else None
        parser.add_argument("--tag", action=action, nargs=nargs, default=Recorded())

        result = parser.parse_args(["--tag", "t"] * 50)

        assert result.tag == ["t"] * 50
        assert copied == list(range(50))

    def test_the_default_list_is_never_appended_to(self) -> None:
        default: list[str] = []
        parser = argparse.ArgumentParser()
        parser.add_argument("--tag", action="append", default=default)

        result = parser.parse_args(["--tag", "a", "--tag", "b"])

        assert result.tag == ["a", "b"] and result.tag is not default
        assert default == []

    def test_one_star_option_collects_the_same_values(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--tag", action="append")
        parser.add_argument("--tags", nargs="*")

        assert (
            parser.parse_args(["--tag", "a", "--tag", "b"]).tag
            == parser.parse_args(["--tags", "a", "b"]).tags
        )


class TestMutuallyExclusiveGroups:
    """`add_mutually_exclusive_group()` | O(1), and every parse builds an
    O(g²) conflict table."""

    @pytest.mark.timing
    def test_an_empty_parse_is_quadratic_in_the_group(self) -> None:
        small = exclusive_group_parser(200)
        large = exclusive_group_parser(1_600)

        ratio = best_ns(lambda: large.parse_args([]), repeats=3) / best_ns(
            lambda: small.parse_args([])
        )

        assert ratio > 25, f"8x the members cost x{ratio:.1f}; linear predicts 8, quadratic 64"

    def test_the_conflict_table_is_quadratic_in_space(self) -> None:
        def peak(members: int) -> int:
            parser = exclusive_group_parser(members)
            parser.parse_args([])  # warm
            return peak_bytes(lambda: parser.parse_args([]))

        small, large = peak(200), peak(800)

        assert large > small * 8, f"4x the members peaked x{large / small:.1f}; linear is 4"

    def test_two_members_conflict(self) -> None:
        parser = exclusive_group_parser(3)
        parser.exit_on_error = False

        with pytest.raises(argparse.ArgumentError, match="not allowed with argument"):
            parser.parse_args(["--member0", "--member1"])


class TestSubcommands:
    """Dispatching to a subcommand | O(1); `add_parser()` | O(1)."""

    @staticmethod
    def _parser(commands: int) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        subcommands = parser.add_subparsers(dest="command")
        for index in range(commands):
            subcommands.add_parser(f"c{index}")
        return parser

    @pytest.mark.timing
    def test_dispatch_does_not_grow_with_the_subcommands(self) -> None:
        few, many = self._parser(10), self._parser(10_000)

        few_ns = best_ns(lambda: few.parse_args(["c0"]), inner=20)
        many_ns = best_ns(lambda: many.parse_args(["c0"]), inner=20)

        assert many_ns < few_ns * 3, f"10,000 subcommands cost {many_ns:.0f}ns against {few_ns:.0f}"

    def test_the_subparser_values_land_on_the_parent_namespace(self) -> None:
        parser = argparse.ArgumentParser()
        subcommands = parser.add_subparsers(dest="command")
        run = subcommands.add_parser("run", aliases=["r"])
        run.add_argument("--fast", action="store_true")
        subcommands.add_parser("stop").add_argument("--force", action="store_true")

        namespace = parser.parse_args(["r", "--fast"])

        assert namespace.command == "r" and namespace.fast is True
        assert not hasattr(namespace, "force")

    def test_intermixed_parsing_rejects_subcommands(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_subparsers()

        with pytest.raises(TypeError):
            parser.parse_intermixed_args([])


class TestParsingForms:
    """`parse_known_args()` returns the extras; the intermixed forms accept
    positionals between options."""

    def test_parse_known_args_returns_unrecognised_strings(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--keep")

        namespace, extras = parser.parse_known_args(["--keep", "1", "--other", "x"])

        assert namespace.keep == "1" and extras == ["--other", "x"]

    def test_intermixed_forms_collect_split_positionals(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--flag", action="store_true")
        parser.add_argument("files", nargs="*")

        mixed = ["a", "--flag", "b"]

        assert parser.parse_intermixed_args(mixed).files == ["a", "b"]
        namespace, extras = parser.parse_known_intermixed_args(mixed + ["--unknown"])
        assert namespace.files == ["a", "b"] and extras == ["--unknown"]
        assert parser.parse_known_args(mixed)[1] == ["b"]

    @pytest.mark.timing
    def test_parse_space_is_linear_in_the_command_line(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("rest", nargs="*")

        def peak(count: int) -> int:
            strings = ["x"] * count
            parser.parse_args(strings)  # warm
            return peak_bytes(lambda: parser.parse_args(strings))

        small, large = peak(10_000), peak(100_000)

        assert large < small * 30, f"10x the strings peaked x{large / small:.1f}; quadratic is 100"


class TestHelp:
    """`format_help()` | O(a + h), rendered on every call; a successful parse
    renders nothing."""

    @pytest.mark.timing
    def test_help_is_linear_in_the_options(self) -> None:
        small = parser_with_options(100)
        large = parser_with_options(1_600)

        ratio = best_ns(large.format_help, repeats=3) / best_ns(small.format_help)
        length_ratio = len(large.format_help()) / len(small.format_help())

        assert 12 < length_ratio < 20
        assert 6 < ratio < 60, f"16x the options cost x{ratio:.1f}; quadratic predicts 256"

    def test_help_is_not_cached(self) -> None:
        parser = parser_with_options(3)

        first, second = parser.format_help(), parser.format_help()

        assert first == second and first is not second

    def test_only_an_error_builds_a_formatter_during_parsing(self) -> None:
        built: list[int] = []

        class Counting(argparse.HelpFormatter):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                built.append(1)
                super().__init__(*args, **kwargs)

        parser = argparse.ArgumentParser(prog="p", formatter_class=Counting)
        parser.add_argument("path")
        built.clear()

        parser.parse_args(["x"])
        assert built == []

        with contextlib.redirect_stderr(io.StringIO()), pytest.raises(SystemExit) as raised:
            parser.parse_args([])
        assert raised.value.code == 2
        assert built, "the error path rendered no usage"

    def test_error_and_exit_raise_system_exit(self) -> None:
        parser = argparse.ArgumentParser(prog="p")
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as error:
            parser.error("bad input")
        assert error.value.code == 2
        assert "usage:" in stderr.getvalue() and "bad input" in stderr.getvalue()

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), pytest.raises(SystemExit) as exit:
            parser.exit(3, "bye\n")
        assert exit.value.code == 3 and stderr.getvalue() == "bye\n"

    def test_print_methods_write_to_the_given_file(self) -> None:
        parser = argparse.ArgumentParser(prog="p")
        help_out, usage_out = io.StringIO(), io.StringIO()

        parser.print_help(help_out)
        parser.print_usage(usage_out)

        assert "show this help message" in help_out.getvalue()
        assert "usage:" in usage_out.getvalue()


class TestActionsAndTypes:
    """Actions, `FileType`, `register()`, `convert_arg_line_to_args()` and
    the constants, asserted by behaviour."""

    def test_boolean_optional_action_adds_a_negative_spelling(self) -> None:
        parser = argparse.ArgumentParser()
        action = parser.add_argument("--color", action=argparse.BooleanOptionalAction)

        assert action.option_strings == ["--color", "--no-color"]
        assert parser.parse_args(["--no-color"]).color is False

    def test_action_format_usage_is_the_first_spelling(self) -> None:
        parser = argparse.ArgumentParser()

        action = parser.add_argument("-v", "--verbose", action="store_true")

        assert action.format_usage() == "-v"

    def test_file_type_opens_the_file_during_parsing(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "in.txt"
        path.write_text("data", encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parser = argparse.ArgumentParser()
            parser.add_argument("source", type=argparse.FileType("r", encoding="utf-8"))

            namespace = parser.parse_args([str(path)])

        with namespace.source as handle:
            assert handle.read() == "data"

    def test_register_names_a_custom_action(self) -> None:
        class Upper(argparse.Action):
            def __call__(
                self, parser: Any, namespace: Any, values: Any, option: Any = None
            ) -> None:
                setattr(namespace, self.dest, values.upper())

        parser = argparse.ArgumentParser()
        parser.register("action", "upper", Upper)
        parser.add_argument("--name", action="upper")

        assert parser.parse_args(["--name", "ada"]).name == "ADA"

    def test_each_argument_file_line_is_converted_in_order(self, tmp_path: pathlib.Path) -> None:
        lines: list[str] = []

        class Recording(argparse.ArgumentParser):
            def convert_arg_line_to_args(self, arg_line: str) -> list[str]:
                lines.append(arg_line)
                return super().convert_arg_line_to_args(arg_line)

        path = tmp_path / "args.txt"
        path.write_text("--level\n3\nsource\n", encoding="utf-8")
        parser = Recording(fromfile_prefix_chars="@")
        parser.add_argument("--level", type=int)
        parser.add_argument("path")

        namespace = parser.parse_args([f"@{path}"])

        assert lines == ["--level", "3", "source"]
        assert namespace.level == 3 and namespace.path == "source"

    def test_argument_type_error_becomes_an_argument_error(self) -> None:
        def positive(text: str) -> int:
            raise argparse.ArgumentTypeError(f"{text} is not positive")

        parser = argparse.ArgumentParser(exit_on_error=False)
        parser.add_argument("--count", type=positive)

        with pytest.raises(argparse.ArgumentError, match="is not positive"):
            parser.parse_args(["--count", "-1"])

    def test_the_constants_are_strings(self) -> None:
        constants = [
            argparse.SUPPRESS,
            argparse.OPTIONAL,
            argparse.ZERO_OR_MORE,
            argparse.ONE_OR_MORE,
            argparse.REMAINDER,
            argparse.PARSER,
        ]

        assert all(isinstance(value, str) for value in constants)
        assert len(set(constants)) == len(constants)


class TestNamespace:
    """`vars(namespace)` | O(1) is the live dict; `in` and `==` read it."""

    def test_vars_is_the_namespace_dict_itself(self) -> None:
        namespace = argparse.Namespace(level=1)

        attributes = vars(namespace)

        assert attributes is namespace.__dict__
        attributes["level"] = 2
        assert namespace.level == 2

    def test_membership_and_equality(self) -> None:
        namespace = argparse.Namespace(a=1, b=2)

        assert "a" in namespace and "c" not in namespace
        assert namespace == argparse.Namespace(b=2, a=1)
        assert namespace != argparse.Namespace(a=1)

    def test_parse_args_fills_a_given_namespace(self) -> None:
        namespace = argparse.Namespace(extra=True)
        parser = argparse.ArgumentParser()
        parser.add_argument("--level", type=int)

        result = parser.parse_args(["--level", "4"], namespace=namespace)

        assert result is namespace and namespace.level == 4 and namespace.extra is True


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
    """Each block runs in its own subprocess and working directory, and asserts
    its own result; none reads `sys.argv`."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(vars(args)) == 53" in s)
        mutated = source.replace("len(vars(args)) == 53", "len(vars(args)) == 52", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
