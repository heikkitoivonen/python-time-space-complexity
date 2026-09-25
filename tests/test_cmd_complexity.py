"""Tests for docs/stdlib/cmd.md.

The page prices `cmd` a line at a time: parsing and dispatch are linear in the
line and independent of the number of commands, while `help` and command-name
completion enumerate the class and `columnize()` is quadratic in the strings it
lays out. Nearly every row is settled by observation - a counting list, a
recording stream, a patched `get_names()` - which needs no tolerance; one
timing test separates dispatch from enumeration, and Tab completion is
observed on a pseudo-terminal.

Measurement scope:

* `columnize()` over a list subclass that counts item reads: 1,000 eight-
  character strings at width 80 read more than 40x as many items as 100 do,
  where a linear layout would read 10x; 1,000 strings wider than the display
  read more than 40x as many as 100. Twenty two-character strings that fit
  on one line read at most 3n items. The output is asserted for a list that
  wraps, one that fits, and an empty one.
* Dispatch against enumeration: a class with 10,000 `do_` methods against
  one with 10. `onecmd()` costs less than 3x as much, and `get_names()` more
  than 30x. `onecmd()` and one-topic `help` are asserted not to call
  `get_names()` at all; a `help` listing calls it once, as does each
  command-name completion at state 0 and none at later states.
* `get_names()` equals `sorted(dir(type(shell)))`. The log factor in
  O(a log a) is read from Objects/object.c, where `dir()` sorts its result,
  not measured.
* Reading a stream: with `use_rawinput` false the loop calls `readline()` on
  `stdin` once per line, each call interleaved with that line's handler, and
  never `read()`. With it true, `input()` is called and a `stdin` argument
  is never touched. Without `do_EOF`, a stream that stays exhausted is read
  well past its end: the test stops the loop after 50 reads.
* `cmdqueue` is observed to be consumed with `pop(0)`, one call per queued
  line, before `stdin` is read. That `list.pop(0)` shifts the remaining q
  items, making a replay O(q²), is the list's documented cost and is not
  re-timed here.
* Hooks: `preloop()` and `postloop()` run once per `cmdloop()`, `precmd()`
  and `postcmd()` once per line and never from `onecmd()`, the defaults
  return their argument object, and the loop stops on the first true value
  `postcmd()` returns.
* `parseline()`, `onecmd()`, `emptyline()`, `default()`, `lastcmd` (stored
  as `parseline()` returned it, and not set by a line that parses to no
  command), `?`,
  `!`, `identchars`, `do_help()` for a topic, `print_topics()`, the three
  completion helpers and the module defaults are asserted by their results.
  Attribute text is asserted to be read when printed: a handler that changes
  `prompt` changes the next prompt.
* The Tab binding: `cmdloop()` is run with `readline.parse_and_bind`
  patched, and the binding string asserted - `bind ^I rl_complete` on 3.13+
  under libedit, `tab: complete` otherwise. On a pseudo-terminal, typing
  "hell", Tab, " world" runs `do_hello('world')` where Tab completes and
  sends "hell\\t world" to `default()` under libedit before 3.13; completion
  calls `complete()` with states 0 and 1 for one match.
* Every fenced Python block runs in its own subprocess with an empty stdin, and
  a mutated assertion in one of them is asserted to fail.

Not settled here:

* The Tab behaviour under GNU readline. Every interpreter available locally
  links libedit, so the GNU branch of `test_tab_completes_a_command_name` has
  not run; per Lib/cmd.py it binds `tab: complete` on every version.
* Space bounds are read from Lib/cmd.py: `columnize()` holds the column
  widths and one row of texts, `get_names()` returns one list of a names.
  They are not measured. String lengths - names, columnized strings - are
  outside the model by the page's definition, and not varied.
* `do_help(arg)` for one topic looks up `help_<topic>`, then `do_<topic>`,
  and is O(k + t) with t the docstring's length, which since 3.13 passes
  through `inspect.cleandoc()`; read from Lib/cmd.py and not measured.
* The handler, `help_` and `complete_` methods' own costs are excluded by
  definition. Line length k is not varied: parsing is `str.strip()`, slicing
  and a scan of the command name, read from Lib/cmd.py. Treating
  `identchars` as fixed-size is a cost-model assumption; the name scan tests
  each character against that string.
"""

from __future__ import annotations

import builtins
import cmd
import io
import os
import pathlib
import re
import select
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "cmd.md"
EXPECTED_BLOCKS = 8


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


class CountingList(list[str]):
    """A list that counts reads by index."""

    reads = 0

    def __getitem__(self, index: Any) -> Any:
        self.reads += 1
        return super().__getitem__(index)


class RecordingStream:
    """A line source that records each `readline()` in a shared event log."""

    def __init__(self, lines: list[str], events: list[str]) -> None:
        self._lines = iter(lines)
        self.events = events

    def readline(self) -> str:
        line = next(self._lines, "")
        self.events.append(f"read {line.strip()!r}")
        return line

    def read(self, *args: Any) -> str:
        raise AssertionError("the loop read the whole stream")


def shell_with_commands(count: int) -> cmd.Cmd:
    """A shell whose class has `count` do_ methods named c0, c1, ..."""
    methods = {f"do_c{index}": lambda self, arg: None for index in range(count)}
    return type("Generated", (cmd.Cmd,), methods)(stdout=io.StringIO())


class TestTheLoop:
    """`Cmd.cmdloop` | O(k) per line: one `readline()` per line when
    `use_rawinput` is false, the hooks around each line, and `'EOF'` at the
    end of input."""

    def test_stdin_is_read_a_line_at_a_time(self) -> None:
        events: list[str] = []

        class Shell(cmd.Cmd):
            use_rawinput = False

            def do_run(self, arg: str) -> None:
                events.append(f"run {arg}")

            def do_EOF(self, arg: str) -> bool:
                events.append("EOF")
                return True

        stream = RecordingStream(["run 1\n", "run 2\n"], events)
        Shell(stdin=stream, stdout=io.StringIO()).cmdloop()  # type: ignore[arg-type]

        assert events == ["read 'run 1'", "run 1", "read 'run 2'", "run 2", "read ''", "EOF"]

    def test_a_prompt_is_written_before_each_read(self) -> None:
        class Shell(cmd.Cmd):
            prompt = "> "
            use_rawinput = False

            def do_EOF(self, arg: str) -> bool:
                return True

        output = io.StringIO()
        Shell(stdin=io.StringIO("x\ny\n"), stdout=output).cmdloop()

        assert output.getvalue() == "> *** Unknown syntax: x\n> *** Unknown syntax: y\n> "

    def test_raw_input_ignores_the_stdin_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        typed = iter(["hello there"])
        prompts: list[str] = []

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            return next(typed)

        monkeypatch.setattr(builtins, "input", fake_input)
        heard: list[str] = []

        class Shell(cmd.Cmd):
            def do_hello(self, arg: str) -> bool:
                heard.append(arg)
                return True

        stream = RecordingStream(["ignored\n"], [])
        Shell(completekey=None, stdin=stream).cmdloop()  # type: ignore[arg-type]

        assert heard == ["there"]
        assert prompts == [cmd.PROMPT]
        assert stream.events == []

    def test_without_do_eof_an_exhausted_stream_is_read_forever(self) -> None:
        class Exhausted:
            reads = 0

            def readline(self) -> str:
                self.reads += 1
                if self.reads > 50:
                    raise KeyboardInterrupt
                return ""

        class Shell(cmd.Cmd):
            use_rawinput = False

        stream = Exhausted()
        output = io.StringIO()

        with pytest.raises(KeyboardInterrupt):
            Shell(stdin=stream, stdout=output).cmdloop()  # type: ignore[arg-type]

        assert stream.reads == 51
        assert output.getvalue().count("*** Unknown syntax: EOF\n") == 50

    def test_hooks_run_once_per_loop_and_once_per_line(self) -> None:
        calls: list[str] = []

        class Shell(cmd.Cmd):
            use_rawinput = False

            def preloop(self) -> None:
                calls.append("preloop")

            def postloop(self) -> None:
                calls.append("postloop")

            def precmd(self, line: str) -> str:
                calls.append(f"precmd {line}")
                return line

            def postcmd(self, stop: Any, line: str) -> Any:
                calls.append(f"postcmd {line}")
                return line == "b"

            def default(self, line: str) -> None:
                calls.append(f"default {line}")

        Shell(stdin=io.StringIO("a\nb\nc\n"), stdout=io.StringIO()).cmdloop()

        assert calls == [
            "preloop",
            "precmd a",
            "default a",
            "postcmd a",
            "precmd b",
            "default b",
            "postcmd b",
            "postloop",
        ]

    def test_onecmd_runs_no_hooks(self) -> None:
        class Shell(cmd.Cmd):
            def precmd(self, line: str) -> str:
                raise AssertionError("precmd() was called")

            def postcmd(self, stop: Any, line: str) -> Any:
                raise AssertionError("postcmd() was called")

            def do_x(self, arg: str) -> str:
                return arg

        assert Shell().onecmd("x 1") == "1"

    def test_the_default_hooks_pass_their_argument_through(self) -> None:
        shell = cmd.Cmd()
        line = "some line"
        stop = object()

        assert shell.precmd(line) is line
        assert shell.postcmd(stop, line) is stop  # type: ignore[arg-type]
        assert shell.preloop() is None
        assert shell.postloop() is None

    def test_intro_is_written_first_and_prompt_is_read_each_time(self) -> None:
        class Shell(cmd.Cmd):
            prompt = "a> "
            use_rawinput = False

            def do_switch(self, arg: str) -> None:
                self.prompt = "b> "

            def do_EOF(self, arg: str) -> bool:
                return True

        output = io.StringIO()
        Shell(stdin=io.StringIO("switch\n"), stdout=output).cmdloop(intro="hi")

        assert output.getvalue() == "hi\na> b> "


class TestTheQueue:
    """`Cmd.cmdqueue` | O(q) per line taken: a list consumed with `pop(0)`
    before any input is read."""

    def test_queued_lines_are_taken_from_the_front_before_input(self) -> None:
        events: list[str] = []
        pops: list[tuple[Any, ...]] = []

        class Queue(list[str]):
            def pop(self, *args: Any) -> str:
                pops.append(args)
                return super().pop(*args)

        class Shell(cmd.Cmd):
            use_rawinput = False

            def default(self, line: str) -> None:
                events.append(line)

            def do_EOF(self, arg: str) -> bool:
                return True

        shell = Shell(stdin=RecordingStream(["typed\n"], events), stdout=io.StringIO())  # type: ignore[arg-type]
        shell.cmdqueue = Queue(["first", "second"])
        shell.cmdloop()

        assert pops == [(0,), (0,)]
        assert events == ["first", "second", "read 'typed'", "typed", "read ''"]

    def test_a_new_shell_has_an_empty_queue_of_its_own(self) -> None:
        one, two = cmd.Cmd(), cmd.Cmd()

        assert one.cmdqueue == [] and one.cmdqueue is not two.cmdqueue


class TestParsingAndDispatch:
    """`parseline` and `onecmd` | O(k): one lookup for `do_<command>`,
    whatever the number of commands."""

    def test_parseline_splits_the_command_from_its_arguments(self) -> None:
        shell = cmd.Cmd()

        assert shell.parseline("  add 1 2 ") == ("add", "1 2", "add 1 2")
        assert shell.parseline("add-1") == ("add", "-1", "add-1")
        assert shell.parseline("   ") == (None, None, "")
        assert shell.parseline("-x") == ("", "-x", "-x")

    def test_question_mark_is_help_and_bang_needs_do_shell(self) -> None:
        class Shell(cmd.Cmd):
            def do_shell(self, arg: str) -> None:
                pass

        assert cmd.Cmd().parseline("?add") == ("help", "add", "help add")
        assert cmd.Cmd().parseline("!ls") == (None, None, "!ls")
        assert Shell().parseline("!ls -l") == ("shell", "ls -l", "shell ls -l")

    def test_identchars_decides_where_the_name_ends(self) -> None:
        class Dashed(cmd.Cmd):
            identchars = cmd.IDENTCHARS + "-"

        assert Dashed().parseline("add-1 x") == ("add-1", "x", "add-1 x")

    def test_an_unknown_command_goes_to_default(self) -> None:
        output = io.StringIO()
        shell = cmd.Cmd(stdout=output)

        assert shell.onecmd("multiply 2 3") is None
        assert shell.onecmd("!ls") is None

        assert output.getvalue() == "*** Unknown syntax: multiply 2 3\n*** Unknown syntax: !ls\n"

    def test_the_handler_s_result_is_returned(self) -> None:
        sentinel = object()

        class Shell(cmd.Cmd):
            def do_go(self, arg: str) -> object:
                return (sentinel, arg)

        assert Shell().onecmd("go  far ") == (sentinel, "far")

    def test_dispatch_never_lists_the_commands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(self: cmd.Cmd) -> list[str]:
            raise AssertionError("get_names() was called")

        monkeypatch.setattr(cmd.Cmd, "get_names", refuse)
        shell = shell_with_commands(3)

        shell.onecmd("c1 x")
        shell.onecmd("nothing here")

    @pytest.mark.timing
    def test_dispatch_costs_the_same_with_a_thousand_times_the_commands(self) -> None:
        small, large = shell_with_commands(10), shell_with_commands(10_000)
        for shell in (small, large):
            shell.onecmd("c5 x")

        dispatch = [
            best_ns(lambda s=shell: s.onecmd("c5 x"), inner=2_000) for shell in (small, large)
        ]
        listing = [best_ns(shell.get_names, inner=5) for shell in (small, large)]

        assert dispatch[1] < dispatch[0] * 3, f"onecmd at 10 and 10,000 commands: {dispatch} ns"
        assert listing[1] > listing[0] * 30, f"get_names at 10 and 10,000 commands: {listing} ns"


class TestEmptyLines:
    """`Cmd.emptyline` repeats `lastcmd`; `lastcmd` is the last nonempty
    line, reset by `EOF`."""

    def test_an_empty_line_repeats_the_last_command(self) -> None:
        class Counter(cmd.Cmd):
            count = 0

            def do_inc(self, arg: str) -> None:
                self.count += 1

        counter = Counter()
        counter.onecmd("inc")
        counter.onecmd("")
        counter.onecmd("   ")

        assert counter.count == 3
        assert counter.lastcmd == "inc"

    def test_with_nothing_to_repeat_it_does_nothing(self) -> None:
        output = io.StringIO()
        shell = cmd.Cmd(stdout=output)

        assert shell.lastcmd == ""
        assert shell.onecmd("") is None
        assert output.getvalue() == ""

    def test_eof_resets_lastcmd(self) -> None:
        class Shell(cmd.Cmd):
            def do_EOF(self, arg: str) -> None:
                pass

            def do_x(self, arg: str) -> None:
                pass

        shell = Shell()
        shell.onecmd("x 1")
        assert shell.lastcmd == "x 1"

        shell.onecmd("EOF")

        assert shell.lastcmd == ""

    def test_lastcmd_is_the_line_as_parsed(self) -> None:
        shell = cmd.Cmd(stdout=io.StringIO())

        shell.onecmd("  ?help  ")
        assert shell.lastcmd == "help help"

        shell.onecmd("!ls")  # no do_shell: parsed to no command, not remembered
        assert shell.lastcmd == "help help"

    def test_an_unknown_command_is_still_remembered(self) -> None:
        shell = cmd.Cmd(stdout=io.StringIO())

        shell.onecmd("nope")

        assert shell.lastcmd == "nope"


class TestHelp:
    """`do_help(arg)` never lists the commands; `help` alone calls
    `get_names()` once and `print_topics()` for three groups."""

    class Shell(cmd.Cmd):
        ruler = "-"

        def do_add(self, arg: str) -> None:
            """Add integers."""

        def do_quit(self, arg: str) -> bool:
            return True

        def help_syntax(self) -> None:
            self.stdout.write("Commands are words.\n")

    def test_one_topic_does_not_list_the_commands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(self: cmd.Cmd) -> list[str]:
            raise AssertionError("get_names() was called")

        monkeypatch.setattr(cmd.Cmd, "get_names", refuse)
        output = io.StringIO()
        shell = self.Shell(stdout=output)

        shell.onecmd("help add")
        shell.onecmd("help syntax")
        shell.onecmd("help quit")

        assert output.getvalue() == "Add integers.\nCommands are words.\n*** No help on quit\n"

    def test_the_listing_calls_get_names_once_and_prints_three_groups(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        names: list[None] = []
        topics: list[tuple[str, list[str]]] = []
        original_names = cmd.Cmd.get_names
        original_topics = cmd.Cmd.print_topics

        def counting_names(self: cmd.Cmd) -> list[str]:
            names.append(None)
            return original_names(self)

        def recording_topics(self: cmd.Cmd, header: str, cmds: list[str], *args: Any) -> None:
            topics.append((header, list(cmds)))
            original_topics(self, header, cmds, *args)

        monkeypatch.setattr(cmd.Cmd, "get_names", counting_names)
        monkeypatch.setattr(cmd.Cmd, "print_topics", recording_topics)
        output = io.StringIO()

        self.Shell(stdout=output).onecmd("help")

        assert len(names) == 1
        assert topics == [
            (cmd.Cmd.doc_header, ["add", "help"]),
            (cmd.Cmd.misc_header, ["syntax"]),
            (cmd.Cmd.undoc_header, ["quit"]),
        ]
        assert "Undocumented commands:\n----------------------\nquit\n" in output.getvalue()

    def test_print_topics_writes_header_ruler_and_columns(self) -> None:
        output = io.StringIO()
        shell = cmd.Cmd(stdout=output)
        shell.ruler = "~"

        shell.print_topics("Head", ["one", "two", "three"], 15, 11)
        shell.print_topics("Empty", [], 15, 80)

        assert output.getvalue() == "Head\n~~~~\none  three\ntwo\n\n"

    def test_the_header_texts_are_read_when_printed(self) -> None:
        output = io.StringIO()
        shell = self.Shell(stdout=output)
        shell.doc_leader = "LEADER"
        shell.doc_header = "DOCS"
        shell.nohelp = "none for %s"

        shell.onecmd("help")
        shell.onecmd("help missing")

        text = output.getvalue()
        assert text.startswith("LEADER\nDOCS\n----\n")
        assert text.endswith("none for missing\n")


class TestColumnizeIsQuadratic:
    """`Cmd.columnize` | O(n²) once the strings wrap onto many rows; O(n)
    when they fit on one line."""

    @staticmethod
    def reads(strings: list[str], width: int = 80) -> int:
        items = CountingList(strings)
        cmd.Cmd(stdout=io.StringIO()).columnize(items, width)
        return items.reads

    def test_ten_times_the_strings_reads_far_more_than_ten_times_the_items(self) -> None:
        small = self.reads(["x" * 8] * 100)
        large = self.reads(["x" * 8] * 1_000)

        assert large > small * 40, f"100 and 1,000 strings read {small} and {large} items"

    def test_strings_wider_than_the_display_are_quadratic_too(self) -> None:
        small = self.reads(["x" * 100] * 100)
        large = self.reads(["x" * 100] * 1_000)

        assert large > small * 40, f"100 and 1,000 wide strings read {small} and {large} items"

    def test_a_list_that_fits_on_one_line_is_linear(self) -> None:
        strings = ["ab"] * 20

        assert self.reads(strings) <= 3 * len(strings)

    def test_the_layout(self) -> None:
        output = io.StringIO()
        shell = cmd.Cmd(stdout=output)

        shell.columnize(["one", "two", "three"], displaywidth=10)
        shell.columnize(["a", "b"])
        shell.columnize([])

        assert output.getvalue() == "one  three\ntwo\na  b\n<empty>\n"

    def test_a_non_string_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="not a string"):
            cmd.Cmd(stdout=io.StringIO()).columnize(["a", 1])  # type: ignore[list-item]


class TestCompletion:
    """`get_names` | O(a log a); `complete` builds every match at state 0
    and indexes it afterwards; the three helpers return their matches."""

    class Shell(cmd.Cmd):
        def do_hello(self, arg: str) -> None:
            pass

        def do_help_me(self, arg: str) -> None:
            pass

        def help_hello(self) -> None:
            pass

        def help_history(self) -> None:
            pass

        def complete_hello(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
            self.argument_calls = getattr(self, "argument_calls", 0) + 1
            return [name for name in ("world", "wide") if name.startswith(text)]

    def test_get_names_is_the_sorted_dir_of_the_class(self) -> None:
        shell = self.Shell()
        shell.do_instance_only = lambda arg: None  # type: ignore[attr-defined]

        assert shell.get_names() == sorted(dir(self.Shell))
        assert "do_instance_only" not in shell.get_names()

    def test_the_helpers_return_their_matches(self) -> None:
        shell = self.Shell()

        assert shell.completenames("hel") == ["hello", "help", "help_me"]
        assert sorted(shell.complete_help("h")) == ["hello", "help", "help_me", "history"]
        assert shell.completedefault("x", "unknown x", 8, 9) == []

    @pytest.fixture
    def line_buffer(self, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
        readline = pytest.importorskip("readline")

        def set_line(line: str) -> None:
            begin = len(line) - len(line.split(" ")[-1])
            monkeypatch.setattr(readline, "get_line_buffer", lambda: line)
            monkeypatch.setattr(readline, "get_begidx", lambda: begin)
            monkeypatch.setattr(readline, "get_endidx", lambda: len(line))

        return set_line

    def test_state_zero_lists_the_names_and_later_states_do_not(
        self, monkeypatch: pytest.MonkeyPatch, line_buffer: Callable[[str], None]
    ) -> None:
        calls: list[None] = []
        original = cmd.Cmd.get_names

        def counting(self: cmd.Cmd) -> list[str]:
            calls.append(None)
            return original(self)

        monkeypatch.setattr(cmd.Cmd, "get_names", counting)
        line_buffer("hel")
        shell = self.Shell()

        results = [shell.complete("hel", state) for state in range(4)]

        assert results == ["hello", "help", "help_me", None]
        assert len(calls) == 1

    def test_an_argument_goes_to_its_complete_method_once(
        self, monkeypatch: pytest.MonkeyPatch, line_buffer: Callable[[str], None]
    ) -> None:
        def refuse(self: cmd.Cmd) -> list[str]:
            raise AssertionError("get_names() was called")

        monkeypatch.setattr(cmd.Cmd, "get_names", refuse)
        line_buffer("hello w")
        shell = self.Shell()

        results = [shell.complete("w", state) for state in range(3)]

        assert results == ["world", "wide", None]
        assert shell.argument_calls == 1

    def test_an_argument_without_a_complete_method_gets_nothing(
        self, line_buffer: Callable[[str], None]
    ) -> None:
        line_buffer("help_me x")

        assert self.Shell().complete("x", 0) is None


class TestAttributesAndConstants:
    """`Cmd(...)` stores its arguments; the module constants are the class
    defaults."""

    def test_the_constructor_stores_its_arguments(self) -> None:
        stdin, stdout = io.StringIO(), io.StringIO()

        shell = cmd.Cmd(completekey=None, stdin=stdin, stdout=stdout)  # type: ignore[arg-type]
        default = cmd.Cmd()

        assert (shell.completekey, shell.stdin, shell.stdout) == (None, stdin, stdout)
        assert (default.completekey, default.stdin, default.stdout) == (
            "tab",
            sys.stdin,
            sys.stdout,
        )

    def test_the_module_constants_are_the_defaults(self) -> None:
        assert cmd.Cmd.prompt == cmd.PROMPT == "(Cmd) "
        assert cmd.Cmd.identchars == cmd.IDENTCHARS
        assert set(cmd.IDENTCHARS) == set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        )

    def test_the_class_defaults(self) -> None:
        assert cmd.Cmd.use_rawinput
        assert cmd.Cmd.intro is None
        assert cmd.Cmd.ruler == "="
        assert cmd.Cmd.lastcmd == ""


class TestTabBinding:
    """Version Notes: `completekey='tab'` binds Tab under libedit on 3.13+."""

    @staticmethod
    def libedit() -> bool:
        readline = pytest.importorskip("readline")
        return "libedit" in (readline.__doc__ or "")

    def test_the_binding_cmdloop_asks_for(self, monkeypatch: pytest.MonkeyPatch) -> None:
        readline = pytest.importorskip("readline")
        bindings: list[str] = []
        completers: list[Any] = []
        previous = object()
        monkeypatch.setattr(readline, "parse_and_bind", bindings.append)
        monkeypatch.setattr(readline, "set_completer", completers.append)
        monkeypatch.setattr(readline, "get_completer", lambda: previous)
        monkeypatch.setattr(builtins, "input", lambda prompt="": "EOF")

        class Shell(cmd.Cmd):
            def do_EOF(self, arg: str) -> bool:
                return True

        shell = Shell()
        shell.cmdloop()

        if self.libedit() and sys.version_info >= (3, 13):
            assert bindings == ["bind ^I rl_complete"]
        else:
            assert bindings == ["tab: complete"]
        assert completers == [shell.complete, previous]

    @pytest.mark.skipif(sys.platform == "win32", reason="needs a pseudo-terminal")
    def test_tab_completes_a_command_name(self) -> None:
        pytest.importorskip("readline")
        child = textwrap.dedent(
            """
            import cmd
            ran = []
            class Shell(cmd.Cmd):
                def complete(self, text, state):
                    result = super().complete(text, state)
                    ran.append(('complete', text, state, result))
                    return result
                def do_hello(self, arg):
                    ran.append(('hello', arg))
                    return True
                def default(self, line):
                    ran.append(('default', line))
                    return True
            print('READY', flush=True)
            Shell().cmdloop()
            print('RESULT', repr(ran), flush=True)
            """
        )
        master, slave = os.openpty()
        process = subprocess.Popen(
            [sys.executable, "-c", child],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            env={**os.environ, "TERM": "xterm", "INPUTRC": os.devnull, "EDITRC": os.devnull},
        )
        os.close(slave)
        output = b""

        def read_until(pattern: bytes, seconds: float = 60) -> None:
            nonlocal output
            deadline = time.monotonic() + seconds
            while not re.search(pattern, output) and time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        output += os.read(master, 65536)
                    except OSError:
                        return

        try:
            read_until(rb"\(Cmd\) ")
            for key in (b"hell", b"\t", b" world\r"):
                os.write(master, key)
                time.sleep(0.3)
            read_until(rb"RESULT [^\n]*\n")
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        match = re.search(r"RESULT (.*)", output.decode(errors="replace"))
        assert match, f"the child printed no result:\n{output!r}"
        result = match.group(1).strip()

        if self.libedit() and sys.version_info < (3, 13):
            assert result == repr([("default", "hell\t world")])
        else:
            assert result == repr(
                [
                    ("complete", "hell", 0, "hello"),
                    ("complete", "hell", 1, None),
                    ("hello", "world"),
                ]
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
    """Each block runs in its own subprocess with an empty stdin, and asserts
    its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "shell.total == 30" in s)
        mutated = source.replace("shell.total == 30", "shell.total == 31", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
