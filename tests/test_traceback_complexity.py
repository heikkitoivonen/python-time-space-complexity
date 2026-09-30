"""Tests for docs/stdlib/traceback.md.

The page prices the module in frames: `d` in one traceback or stack, `F`
the exceptions and frames across everything a formatted exception includes -
its chain and its group members. Most claims are settled by
observation - a counting frame generator shows how far a `limit` walks, a
counting `linecache.getline` shows when a source line is read, a weak
reference shows which objects keep a frame's locals alive, and the formatted
output shows what a chain, a group or a run of identical frames prints.
Growth is settled by traced allocation where it can be and by timing where
only time moves.

Measurement scope:

* `extract_tb()` over tracebacks of 30 and 900 frames: the traced peak grows
  more than 10x, and a timing test puts the time between 10x and 100x.
  `print_tb()` to a sink that keeps nothing, and `format_exception()`, each
  peak more than 50 bytes higher per extra frame, so printing holds the whole
  summary; recursion collapses their output, so that growth is the summary.
* A non-negative `limit` takes exactly that many pairs from a counting frame
  generator; a negative one takes all of them and keeps the last `n`. A timing
  test puts `extract_tb(limit=5)` under 3x from 30 to 900 frames.
  `extract_tb(limit=n)` keeps the oldest `n`, `extract_stack(limit=n)` the
  newest `n` oldest first, and `sys.tracebacklimit` is used when no `limit` is
  passed, a negative one giving no frames where `limit=-3` gives three.
* `format_exception()` on a three-link chain prints one `File` line per frame
  of all three tracebacks, and one per link with `limit=1`; `chain=False`
  prints the outer one only, and on 3.11+ still prints a group's members.
  `format_exception_only()` on a 900-frame traceback peaks under 2x its peak
  on a three-frame one; on an exception whose cause has a 900-frame traceback
  it peaks more than 50 bytes higher per extra frame than with a three-frame
  cause.
* `StackSummary.format()` on 102 and 902 frames of recursion returns seven
  strings each, one of them `[Previous line repeated k more times]` with k
  six fewer than the frames.
* `lookup_lines=False` makes no `linecache.getline` call during extraction;
  reading `.line` makes at least one and a second read makes none, and
  `lookup_lines=True` makes one per frame during extraction. A source file
  whose line was extracted is deleted and the cache cleared, and the summary
  still has the line. Extracting from a cold cache over a 100-line and a
  200,000-line source file peaks more than 20x apart, and from a warm cache
  under 2x apart.
* `capture_locals=True` calls `repr()` once per local and stores the result.
* On 3.11+, frames that run after 10 and after 20,000 generated statements:
  `extract_tb()` of a raise there costs more than 50x as much for the long
  one, and `extract_stack(limit=1)` from a generator suspended there more
  than 10x.
* A weak reference to a local of the raising function is alive while the
  exception is, dies once `clear_frames()` runs, and dies when the exception
  is dropped while a `TracebackException` of it is kept. `clear_frames()` on a
  traceback whose first frame is still executing leaves that frame's locals
  readable.
* On 3.11+, a group of 100 members formatted with `max_group_width=5` has
  100 extracted `exceptions` and prints `and 95 more exceptions`; groups
  nested 12 deep with `max_group_depth=3` are extracted all the way down and
  print the `max_group_depth` marker. `TracebackException.print()` over a
  300-link chain peaks at under a third of `list(format())` on the same
  object.
* On 3.12+, a "Did you mean" hint is asserted for an attribute and a
  `from ... import` from `format_exception_only()`, and for a name from
  `format_exception()`, which has the traceback the name search needs. The
  peak of `format_exception_only()` for a missing attribute grows more than
  20x from 1,000 to 100,000 attributes, and a timing test puts the time above
  20x; both sizes are above the cap past which no match is computed, so the
  growth is collecting and sorting the names. `format_exception()` of a
  `NameError` peaks more than 8 bytes higher per extra global from 100 to
  20,000 globals.
* The remaining rows are asserted by result: `format_tb()` equal to the
  formatted `extract_tb()`, `format_list()` and `print_list()` on tuples and
  `FrameSummary` objects, `from_list()` keeping `FrameSummary` objects by
  identity, `format_frame_summary()` returning `None` to drop a frame (3.11+),
  position fields present on traceback frames and `None` on stack frames
  (3.11+), `print_last()` raising `ValueError` without a last exception and
  printing one set by hand, the `SyntaxError` fields, `exc_type_str` and the
  `exc_type` deprecation (3.13+), and `show_group` (3.13+).
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail. The exception-group block
  needs 3.11 and the suggestion block 3.12; each is skipped below that.

Not settled here:

* O(1) per step for `walk_tb()` and `walk_stack()`, and O(1) for the traceback
  object's `tb_*` attributes, follow from Lib/traceback.py following one link
  per step; only laziness is asserted.
* The O(a log a) suggestion bound is read from Lib/traceback.py sorting the
  candidates for an attribute or a module; growth is measured, not its shape.
  Below the candidate cap, 3.12 runs a pure-Python edit distance per name and
  3.13+ a C one; the cost per name is bounded by the capped name length and
  is not varied.
* On 3.10, a traceback frame's line number is stored when the exception is
  raised and `extract_stack()` reads `f_lineno`; the location-table scan
  there is read from Objects/codeobject.c, not measured.
* The O(d) term of a suggestion is Lib/traceback.py following `tb_next` to
  the last frame for a `NameError`, and for an `AttributeError` to check
  whether the object is that frame's `self`; traceback depth is not varied
  in the suggestion tests.
* Line lengths, message lengths, note counts and statements spanning several
  lines are priced O(1) and not varied. The cost of `repr()` on captured
  locals belongs to the caller's objects.
* The page audit reports `tb_frame`, `tb_lasti`, `tb_lineno` and `tb_next`
  as unresolved: they are attributes of traceback objects, which exist only
  once something has raised. The row covers them; `tb_next`, `tb_frame` and
  `tb_lineno` are read above, `tb_lasti` is not.
* `print_last()` printing a real last exception depends on the interpreter
  recording an unhandled one; it is asserted with the attribute set by hand.
"""

from __future__ import annotations

import builtins
import gc
import io
import linecache
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import traceback
import tracemalloc
import types
import warnings
import weakref
from collections.abc import Callable, Iterator
from typing import Any

import pytest

# Version-dependent names, typed loosely so the 3.10 type check accepts them.
GROUP: Any = getattr(builtins, "ExceptionGroup", None)
TracebackException: Any = traceback.TracebackException

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "traceback.md"
EXPECTED_BLOCKS = 9

# Blocks that need a newer interpreter than the oldest supported one, keyed by
# a line only they contain.
MINIMUM_VERSION = {
    "group = ExceptionGroup(": (3, 11),
    "Did you mean: 'timeout'?": (3, 12),
}


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


class NullSink:
    """A file-like object that keeps nothing."""

    def write(self, text: str) -> int:
        return len(text)


def recurse(depth: int) -> None:
    if depth == 0:
        raise ValueError("bottom")
    recurse(depth - 1)


def raised(func: Callable[[], Any]) -> BaseException:
    """The exception func raises, with its traceback."""
    try:
        func()
    except BaseException as exc:  # noqa: BLE001 - the tests want every kind
        return exc
    raise AssertionError("nothing was raised")


def deep_error(frames: int) -> BaseException:
    """An exception whose traceback has exactly `frames` frames."""
    return raised(lambda: recurse(frames - 3))


def frame_count(tb: types.TracebackType | None) -> int:
    count = 0
    while tb is not None:
        count += 1
        tb = tb.tb_next
    return count


class CountingFrames:
    """Wraps a frame generator and counts the pairs taken from it."""

    def __init__(self, pairs: Iterator[tuple[Any, int]]) -> None:
        self._pairs = pairs
        self.taken = 0

    def __iter__(self) -> CountingFrames:
        return self

    def __next__(self) -> tuple[Any, int]:
        pair = next(self._pairs)
        self.taken += 1
        return pair


class TestExtractingIsLinearInFrames:
    """`extract_tb` and `extract_stack` | O(d) | O(d): a record per frame,
    oldest first, with its source line read during extraction."""

    def test_extract_tb_has_one_record_per_frame_oldest_first(self) -> None:
        error = deep_error(7)

        summary = traceback.extract_tb(error.__traceback__)

        assert len(summary) == frame_count(error.__traceback__) == 7
        assert summary[0].name == "raised"
        assert [frame.name for frame in summary[2:]] == ["recurse"] * 5
        assert summary[-1].line == 'raise ValueError("bottom")'

    def test_extract_stack_is_oldest_first(self) -> None:
        def inner() -> traceback.StackSummary:
            return traceback.extract_stack()

        stack = inner()

        assert stack[-1].name == "inner"
        assert stack[-2].name == "test_extract_stack_is_oldest_first"

    def test_the_peak_grows_with_the_frames(self) -> None:
        small, large = deep_error(30), deep_error(900)
        traceback.extract_tb(large.__traceback__)  # warm linecache

        peaks = [
            peak_bytes(lambda e=e: traceback.extract_tb(e.__traceback__)) for e in (small, large)
        ]

        assert peaks[1] > peaks[0] * 10, f"30x the frames peaked at {peaks}"

    @pytest.mark.timing
    def test_the_time_grows_linearly_with_the_frames(self) -> None:
        small, large = deep_error(30), deep_error(900)
        traceback.extract_tb(large.__traceback__)

        durations = [
            best_ns(lambda e=e: traceback.extract_tb(e.__traceback__)) for e in (small, large)
        ]
        ratio = durations[1] / durations[0]

        assert 10 < ratio < 100, f"30x the frames took x{ratio:.1f} ({durations} ns)"

    def test_walk_tb_and_walk_stack_are_generators(self) -> None:
        error = deep_error(3)

        walk = traceback.walk_tb(error.__traceback__)
        assert isinstance(walk, types.GeneratorType)
        frame, lineno = next(walk)
        assert frame is error.__traceback__.tb_frame  # type: ignore[union-attr]
        assert lineno == error.__traceback__.tb_lineno  # type: ignore[union-attr]

        here = sys._getframe()  # noqa: SLF001
        stack = traceback.walk_stack(here)
        assert isinstance(stack, types.GeneratorType)
        assert next(stack)[0] is here
        assert next(stack)[0] is here.f_back


class TestLimit:
    """`limit=n` | O(n) | O(n) stops the walk; `limit=-n` | O(d) | O(n)
    walks everything and keeps the last n; `sys.tracebacklimit` is the
    default."""

    def test_a_non_negative_limit_stops_the_walk(self) -> None:
        error = deep_error(52)
        frames = CountingFrames(traceback.walk_tb(error.__traceback__))

        summary = traceback.StackSummary.extract(frames, limit=3)

        assert len(summary) == 3
        assert frames.taken == 3

    def test_a_negative_limit_walks_everything_and_keeps_the_last(self) -> None:
        error = deep_error(52)
        frames = CountingFrames(traceback.walk_tb(error.__traceback__))

        summary = traceback.StackSummary.extract(frames, limit=-3)

        assert len(summary) == 3
        assert frames.taken == 52
        assert summary[-1].line == 'raise ValueError("bottom")'

    def test_extract_tb_keeps_the_oldest_and_extract_stack_the_newest(self) -> None:
        error = deep_error(10)
        assert [f.name for f in traceback.extract_tb(error.__traceback__, limit=2)] == [
            "raised",
            "<lambda>",
        ]

        def inner() -> traceback.StackSummary:
            return traceback.extract_stack(limit=2)

        stack = inner()
        assert [f.name for f in stack] == [
            "test_extract_tb_keeps_the_oldest_and_extract_stack_the_newest",
            "inner",
        ]

    def test_sys_tracebacklimit_is_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        error = deep_error(10)
        monkeypatch.setattr(sys, "tracebacklimit", 2, raising=False)

        assert len(traceback.extract_tb(error.__traceback__)) == 2

    def test_a_negative_sys_tracebacklimit_means_no_frames(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = deep_error(10)
        monkeypatch.setattr(sys, "tracebacklimit", -3, raising=False)

        assert len(traceback.extract_tb(error.__traceback__)) == 0
        assert len(traceback.extract_tb(error.__traceback__, limit=-3)) == 3

    @pytest.mark.timing
    def test_a_positive_limit_makes_depth_irrelevant(self) -> None:
        small, large = deep_error(30), deep_error(900)

        durations = [
            best_ns(lambda e=e: traceback.extract_tb(e.__traceback__, limit=5), inner=20)
            for e in (small, large)
        ]
        ratio = durations[1] / durations[0]

        assert ratio < 3, f"30x the frames with limit=5 took x{ratio:.2f} ({durations} ns)"


class TestClearFrames:
    """`clear_frames(tb)` | O(d) | O(1): releases every frame's locals and
    skips the one still executing."""

    def test_the_traceback_keeps_locals_alive_until_cleared(self) -> None:
        refs: list[weakref.ref[Any]] = []

        class Payload:
            pass

        def fail() -> None:
            payload = Payload()
            refs.append(weakref.ref(payload))
            raise ValueError("boom")

        error = raised(fail)
        gc.collect()
        assert refs[0]() is not None

        traceback.clear_frames(error.__traceback__)

        assert refs[0]() is None

    def test_an_executing_frame_is_skipped(self) -> None:
        marker = object()
        try:
            raise ValueError("here")
        except ValueError as exc:
            traceback.clear_frames(exc.__traceback__)  # its first frame is this one

        assert marker is not None


class TestFormatting:
    """`format_*` and `print_*` | O(d) or O(F): extract, then render, with the
    whole list built before the first write."""

    def test_format_tb_is_the_formatted_summary(self) -> None:
        error = deep_error(3)

        assert traceback.format_tb(error.__traceback__) == (
            traceback.extract_tb(error.__traceback__).format()
        )

    def test_print_tb_writes_what_format_tb_returns(self) -> None:
        error = deep_error(3)
        out = io.StringIO()

        traceback.print_tb(error.__traceback__, file=out)

        assert out.getvalue() == "".join(traceback.format_tb(error.__traceback__))

    def test_print_tb_holds_the_whole_summary(self) -> None:
        small, large = deep_error(30), deep_error(900)
        traceback.print_tb(large.__traceback__, file=NullSink())

        peaks = [
            peak_bytes(lambda e=e: traceback.print_tb(e.__traceback__, file=NullSink()))
            for e in (small, large)
        ]

        # Recursion collapses the output, so what grows is the summary held.
        assert peaks[1] - peaks[0] > 870 * 50, f"printing 30x the frames peaked at {peaks}"

    def test_format_list_and_print_list_take_tuples_or_summaries(self) -> None:
        entries = [("app.py", 10, "main", "run()")]
        frame = traceback.FrameSummary("app.py", 10, "main", line="run()")
        expected = ['  File "app.py", line 10, in main\n    run()\n']
        out = io.StringIO()

        traceback.print_list(entries, file=out)

        assert traceback.format_list(entries) == expected
        assert traceback.format_list([frame]) == expected
        assert out.getvalue() == expected[0]

    def test_format_stack_and_print_stack_render_the_caller(self) -> None:
        out = io.StringIO()

        lines = traceback.format_stack()
        traceback.print_stack(file=out)

        assert "test_format_stack_and_print_stack_render_the_caller" in lines[-1]
        assert "test_format_stack_and_print_stack_render_the_caller" in out.getvalue()

    @staticmethod
    def chain_of_three() -> BaseException:
        def first() -> None:
            raise KeyError("a")

        def second() -> None:
            try:
                first()
            except KeyError as exc:
                raise ValueError("b") from exc

        def third() -> None:
            try:
                second()
            except ValueError:
                raise RuntimeError("c")  # noqa: B904 - an implicit __context__

        return raised(third)

    def test_the_whole_chain_is_formatted(self) -> None:
        error = self.chain_of_three()
        frames = 0
        link: BaseException | None = error
        while link is not None:
            frames += frame_count(link.__traceback__)
            link = link.__cause__ or link.__context__

        text = "".join(traceback.format_exception(error))

        assert text.count('  File "') == frames
        assert "direct cause" in text and "During handling" in text

    def test_limit_applies_to_each_traceback_in_the_chain(self) -> None:
        text = "".join(traceback.format_exception(self.chain_of_three(), limit=1))

        assert text.count('  File "') == 3

    def test_chain_false_formats_the_outer_exception_only(self) -> None:
        text = "".join(traceback.format_exception(self.chain_of_three(), chain=False))

        assert "KeyError" not in text and "ValueError" not in text
        assert text.endswith("RuntimeError: c\n")

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="exception groups arrive in 3.11")
    def test_chain_false_still_formats_group_members(self) -> None:
        group = GROUP("batch", [ValueError("member")])

        text = "".join(traceback.format_exception(group, chain=False))

        assert "ValueError: member" in text

    def test_print_exception_writes_what_format_exception_returns(self) -> None:
        error = self.chain_of_three()
        out = io.StringIO()

        traceback.print_exception(error, file=out)

        assert out.getvalue() == "".join(traceback.format_exception(error))

    def test_format_exc_and_print_exc_read_the_handled_exception(self) -> None:
        out = io.StringIO()
        try:
            raise ValueError("handled")
        except ValueError:
            text = traceback.format_exc()
            traceback.print_exc(file=out)

        assert text.endswith("ValueError: handled\n")
        assert out.getvalue() == text

    def test_format_exception_only_skips_the_exception_s_own_traceback(self) -> None:
        shallow, deep = deep_error(3), deep_error(900)
        traceback.format_exception(deep)  # warm linecache

        only = [peak_bytes(lambda e=e: traceback.format_exception_only(e)) for e in (shallow, deep)]
        full = [peak_bytes(lambda e=e: traceback.format_exception(e)) for e in (shallow, deep)]

        assert traceback.format_exception_only(deep) == ["ValueError: bottom\n"]
        assert only[1] < only[0] * 2, f"format_exception_only peaked at {only}"
        assert full[1] - full[0] > 897 * 50, f"format_exception peaked at {full}"

    def test_format_exception_only_still_builds_the_chain(self) -> None:
        def chained(frames: int) -> BaseException:
            cause = deep_error(frames)
            try:
                raise KeyError("outer") from cause
            except KeyError as exc:
                return exc

        errors = [chained(3), chained(900)]
        traceback.format_exception(errors[1])  # warm linecache

        peaks = [peak_bytes(lambda e=e: traceback.format_exception_only(e)) for e in errors]

        assert traceback.format_exception_only(errors[1]) == ["KeyError: 'outer'\n"]
        assert peaks[1] - peaks[0] > 897 * 50, f"a 900-frame cause peaked at {peaks}"

    def test_a_syntax_error_brings_its_source_line(self) -> None:
        error = raised(lambda: compile("x = (1,\n", "<src>", "exec"))

        lines = traceback.format_exception_only(error)
        summary = traceback.TracebackException.from_exception(error)

        assert any("x = (1," in line for line in lines)
        assert lines[-1].startswith("SyntaxError:")
        assert summary.filename == "<src>"
        assert summary.lineno is not None and summary.text is not None
        assert summary.msg and summary.offset is not None
        assert hasattr(summary, "end_lineno") and hasattr(summary, "end_offset")

    def test_print_last_needs_a_last_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("last_exc", "last_type", "last_value", "last_traceback"):
            monkeypatch.delattr(sys, name, raising=False)

        with pytest.raises(ValueError, match="no last exception"):
            traceback.print_last()

        error = deep_error(4)
        if sys.version_info >= (3, 12):
            monkeypatch.setattr(sys, "last_exc", error, raising=False)
        else:
            monkeypatch.setattr(sys, "last_type", type(error), raising=False)
            monkeypatch.setattr(sys, "last_value", error, raising=False)
            monkeypatch.setattr(sys, "last_traceback", error.__traceback__, raising=False)
        out = io.StringIO()

        traceback.print_last(file=out)

        assert out.getvalue() == "".join(traceback.format_exception(error))


class TestStackSummary:
    """`StackSummary` and `FrameSummary`: deferred and cached source lines,
    `repr()` of captured locals, and recursion collapsed in the output."""

    @pytest.fixture
    def getline_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
        calls: list[tuple[str, int]] = []
        original = linecache.getline

        def counting(filename: str, lineno: int, module_globals: Any = None) -> str:
            calls.append((filename, lineno))
            return original(filename, lineno, module_globals)

        monkeypatch.setattr(linecache, "getline", counting)
        return calls

    def test_lookup_lines_false_defers_reads(self, getline_calls: list[tuple[str, int]]) -> None:
        error = deep_error(3)

        summary = traceback.StackSummary.extract(
            traceback.walk_tb(error.__traceback__), lookup_lines=False
        )
        assert getline_calls == []

        assert summary[-1].line == 'raise ValueError("bottom")'
        reads = len(getline_calls)
        assert reads >= 1

        assert summary[-1].line == 'raise ValueError("bottom")'
        assert len(getline_calls) == reads, "a second read went back to linecache"

    def test_lookup_lines_true_reads_during_extraction(
        self, getline_calls: list[tuple[str, int]]
    ) -> None:
        error = deep_error(3)

        traceback.StackSummary.extract(traceback.walk_tb(error.__traceback__))

        assert len(getline_calls) >= frame_count(error.__traceback__)

    def test_frame_summary_reads_now_unless_given_the_line(
        self, getline_calls: list[tuple[str, int]]
    ) -> None:
        traceback.FrameSummary(__file__, 1, "module", line="given")
        assert getline_calls == []

        traceback.FrameSummary(__file__, 1, "module")
        assert getline_calls != []

    def test_an_extracted_line_survives_its_file(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "vanishing.py"
        source.write_text("def fail():\n    raise ValueError('gone')\n", encoding="utf-8")
        namespace: dict[str, Any] = {}
        exec(compile(source.read_text(), str(source), "exec"), namespace)  # noqa: S102
        error = raised(namespace["fail"])

        summary = traceback.extract_tb(error.__traceback__)
        source.unlink()
        linecache.clearcache()

        assert summary[-1].line == "raise ValueError('gone')"

    def test_capture_locals_calls_repr_once_per_local(self) -> None:
        reprs: list[int] = []

        class Counted:
            def __repr__(self) -> str:
                reprs.append(1)
                return "<counted>"

        def fail(first: Any, second: Any) -> None:
            raise ValueError("boom")

        error = raised(lambda: fail(Counted(), Counted()))
        summary = traceback.StackSummary.extract(
            traceback.walk_tb(error.__traceback__), capture_locals=True
        )

        assert summary[-1].locals == {"first": "<counted>", "second": "<counted>"}
        assert len(reprs) == 2

    def test_from_list_keeps_frame_summaries_and_wraps_tuples(self) -> None:
        frame = traceback.FrameSummary("a.py", 1, "f", line="x")

        rebuilt = traceback.StackSummary.from_list([frame, ("b.py", 2, "g", "y")])

        assert rebuilt[0] is frame
        assert isinstance(rebuilt[1], traceback.FrameSummary)
        assert rebuilt[1].line == "y"

    def test_recursion_collapses_in_the_output(self) -> None:
        outputs = []
        for frames in (102, 902):
            summary = traceback.extract_tb(deep_error(frames).__traceback__)
            assert len(summary) == frames
            outputs.append(summary.format())
            assert f"[Previous line repeated {frames - 6} more times]" in outputs[-1][-2]

        assert len(outputs[0]) == len(outputs[1]) == 7

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_format_frame_summary_returning_none_drops_the_frame(self) -> None:
        class OnlyRecurse(traceback.StackSummary):
            def format_frame_summary(self, frame_summary: Any, **kwargs: Any) -> Any:
                if frame_summary.name != "recurse":
                    return None
                return super().format_frame_summary(frame_summary, **kwargs)  # type: ignore[misc]

        error = deep_error(4)
        summary = OnlyRecurse(traceback.extract_tb(error.__traceback__))

        assert "".join(summary.format()).count('  File "') == 2

    def test_frame_summary_fields(self) -> None:
        frame = traceback.extract_tb(deep_error(3).__traceback__)[-1]

        assert frame.filename == __file__
        assert frame.name == "recurse"
        assert isinstance(frame.lineno, int)
        assert frame.locals is None

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_positions_come_from_tracebacks_not_stacks(self) -> None:
        from_traceback: Any = traceback.extract_tb(deep_error(3).__traceback__)[-1]
        from_stack: Any = traceback.extract_stack()[-1]

        assert from_traceback.colno is not None
        assert from_traceback.end_colno is not None
        assert from_traceback.end_lineno == from_traceback.lineno
        assert from_stack.colno is None and from_stack.end_colno is None
        if sys.version_info >= (3, 13):
            assert from_stack.end_lineno == from_stack.lineno
        else:
            assert from_stack.end_lineno is None


class TestSourceFiles:
    """`linecache` reads a whole file the first time a line from it is
    needed, O(s), and serves later lookups from its cache."""

    @staticmethod
    def error_from_file(directory: pathlib.Path, padding: int) -> BaseException:
        source = directory / f"padded{padding}.py"
        source.write_text(
            "def fail():\n    raise ValueError('x')\n" + "# pad\n" * padding, encoding="utf-8"
        )
        namespace: dict[str, Any] = {}
        exec(compile(source.read_text(), str(source), "exec"), namespace)  # noqa: S102
        return raised(namespace["fail"])

    def test_a_cold_read_costs_the_file_and_a_warm_one_does_not(
        self, tmp_path: pathlib.Path
    ) -> None:
        errors = [self.error_from_file(tmp_path, padding) for padding in (100, 200_000)]

        def cold(error: BaseException) -> int:
            linecache.clearcache()
            return peak_bytes(lambda: traceback.extract_tb(error.__traceback__))

        cold_peaks = [cold(error) for error in errors]
        for error in errors:
            traceback.extract_tb(error.__traceback__)  # both files cached
        warm_peaks = [peak_bytes(lambda e=e: traceback.extract_tb(e.__traceback__)) for e in errors]
        linecache.clearcache()

        assert cold_peaks[1] > cold_peaks[0] * 20, f"cold reads peaked at {cold_peaks}"
        assert warm_peaks[1] < warm_peaks[0] * 2, f"warm reads peaked at {warm_peaks}"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="position tables arrive in 3.11")
class TestPositionTable:
    """A traceback frame's position lookup scans its code object's position
    table up to the instruction that raised, and a stack frame's `f_lineno`
    scans the line table up to the instruction being run."""

    @staticmethod
    def generated(statements: int) -> dict[str, Any]:
        padding = "    x = 1\n" * statements
        source = (
            "import traceback\n"
            "def fail():\n" + padding + "    raise ValueError('late')\n"
            "def stack():\n" + padding + "    while True:\n"
            "        yield traceback.extract_stack(limit=1)\n"
        )
        namespace: dict[str, Any] = {}
        exec(compile(source, f"<generated{statements}>", "exec"), namespace)  # noqa: S102
        return namespace

    @pytest.mark.timing
    def test_a_late_raise_in_a_long_function_costs_its_offset(self) -> None:
        errors = [raised(self.generated(size)["fail"]) for size in (10, 20_000)]

        durations = [best_ns(lambda e=e: traceback.extract_tb(e.__traceback__)) for e in errors]
        ratio = durations[1] / durations[0]

        assert ratio > 50, f"2,000x the statements before the raise cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_a_stack_frame_pays_its_offset_too(self) -> None:
        # Each generator has run its padding once; every later step extracts
        # a stack whose newest frame sits after all of it, and reading that
        # frame's f_lineno scans the line table up to there.
        generators = [self.generated(size)["stack"]() for size in (10, 20_000)]
        for generator in generators:
            assert next(generator)[0].name == "stack"

        durations = [best_ns(generator.__next__, inner=20) for generator in generators]
        ratio = durations[1] / durations[0]

        assert ratio > 10, f"extract_stack after 2,000x the statements cost x{ratio:.2f}"


class TestTracebackException:
    """`TracebackException` | O(F) | O(F): the whole chain and every group
    member extracted at construction, and no frame held afterwards."""

    def test_it_holds_no_frame(self) -> None:
        refs: list[weakref.ref[Any]] = []

        class Payload:
            pass

        def fail() -> None:
            payload = Payload()
            refs.append(weakref.ref(payload))
            raise ValueError("boom")

        error: BaseException | None = raised(fail)
        summary = traceback.TracebackException.from_exception(error)  # type: ignore[arg-type]
        del error
        gc.collect()

        assert refs[0]() is None
        assert "".join(summary.format()).endswith("ValueError: boom\n")

    def test_it_captures_the_chain(self) -> None:
        error = TestFormatting.chain_of_three()

        summary = traceback.TracebackException.from_exception(error)

        assert isinstance(summary.stack, traceback.StackSummary)
        assert isinstance(summary.__context__, traceback.TracebackException)
        assert isinstance(summary.__context__.__cause__, traceback.TracebackException)
        assert summary.__suppress_context__ is False

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="notes arrive in 3.11")
    def test_it_captures_the_notes(self) -> None:
        error: Any = deep_error(3)
        error.add_note("while loading")

        summary = TracebackException.from_exception(error)

        assert summary.__notes__ == ["while loading"]
        assert "".join(summary.format()).endswith("ValueError: bottom\nwhile loading\n")

    def test_format_chain_false_is_this_exception_alone(self) -> None:
        summary = traceback.TracebackException.from_exception(TestFormatting.chain_of_three())

        assert "KeyError" not in "".join(summary.format(chain=False))
        assert "KeyError" in "".join(summary.format())

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_print_holds_one_traceback_at_a_time(self) -> None:
        def link(index: int) -> None:
            if index == 0:
                recurse(18)
            try:
                link(index - 1)
            except ValueError as exc:
                raise ValueError(f"link {index}") from exc

        summary = TracebackException.from_exception(raised(lambda: link(299)))
        list(summary.format())  # warm

        printed = peak_bytes(lambda: summary.print(file=NullSink()))
        listed = peak_bytes(lambda: list(summary.format()))

        assert printed * 3 < listed, f"print peaked at {printed}, list(format()) at {listed}"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="exception groups arrive in 3.11")
    def test_max_group_width_caps_the_output_not_the_extraction(self) -> None:
        group = GROUP("batch", [ValueError(i) for i in range(100)])

        summary = TracebackException.from_exception(group, max_group_width=5)
        text = "".join(summary.format())

        assert summary.exceptions is not None and len(summary.exceptions) == 100
        assert "and 95 more exceptions" in text

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="exception groups arrive in 3.11")
    def test_max_group_depth_caps_the_output_not_the_extraction(self) -> None:
        group: Any = ValueError("leaf")
        for level in range(12):
            group = GROUP(f"level {level}", [group])

        summary = TracebackException.from_exception(group, max_group_depth=3)
        depth = 0
        node = summary
        while node.exceptions:
            node = node.exceptions[0]
            depth += 1

        assert depth == 12
        assert "max_group_depth is 3" in "".join(summary.format())

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_show_group_formats_the_members(self) -> None:
        group = GROUP("batch", [ValueError("one"), KeyError("two")])

        plain = traceback.format_exception_only(group)
        shown = traceback.format_exception_only(group, show_group=True)  # type: ignore[call-arg]

        assert not any("ValueError" in line for line in plain)
        assert any("ValueError: one" in line for line in shown)
        assert any("KeyError: 'two'" in line for line in shown)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_exc_type_str_replaces_the_deprecated_exc_type(self) -> None:
        summary = traceback.TracebackException.from_exception(deep_error(3))

        assert summary.exc_type_str == "ValueError"  # type: ignore[attr-defined]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert summary.exc_type is ValueError
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="suggestions arrive in 3.12")
class TestSuggestions:
    """ "Did you mean" suggestion | O(a log a) | O(a): searched at
    construction over the names in scope or the object's attributes."""

    def test_an_attribute_a_name_and_an_import_get_a_hint(self) -> None:
        class Config:
            timeout = 5

        attribute = raised(lambda: Config().timeuot)  # type: ignore[attr-defined]
        name = raised(lambda: exec("lenn", {}))  # noqa: S102 - needs its traceback
        imported = raised(lambda: exec("from os import getcdw", {}))  # noqa: S102

        assert "Did you mean: 'timeout'?" in traceback.format_exception_only(attribute)[-1]
        assert "Did you mean: 'len'?" in traceback.format_exception(name)[-1]
        assert "Did you mean: 'getcwd'?" in traceback.format_exception_only(imported)[-1]

    @staticmethod
    def missing_attribute(attributes: int) -> BaseException:
        holder = types.SimpleNamespace(**{f"attribute_{i}": i for i in range(attributes)})
        return raised(lambda: holder.missing_name)

    def test_the_peak_grows_with_the_attributes(self) -> None:
        errors = [self.missing_attribute(size) for size in (1_000, 100_000)]

        peaks = [peak_bytes(lambda e=e: traceback.format_exception_only(e)) for e in errors]

        assert peaks[1] > peaks[0] * 20, f"100x the attributes peaked at {peaks}"

    def test_the_peak_grows_with_the_globals_for_a_name_error(self) -> None:
        errors = []
        for size in (100, 20_000):
            namespace = {f"name_{i}": i for i in range(size)}
            errors.append(raised(lambda ns=namespace: exec("missing_name", ns)))  # noqa: S102
        traceback.format_exception(errors[1])  # warm linecache

        peaks = [peak_bytes(lambda e=e: traceback.format_exception(e)) for e in errors]

        # At least one list slot per extra name.
        assert peaks[1] - peaks[0] > 19_900 * 8, f"200x the globals peaked at {peaks}"

    @pytest.mark.timing
    def test_the_time_grows_with_the_attributes(self) -> None:
        errors = [self.missing_attribute(size) for size in (1_000, 100_000)]

        durations = [best_ns(lambda e=e: traceback.format_exception_only(e)) for e in errors]
        ratio = durations[1] / durations[0]

        assert ratio > 20, f"100x the attributes cost x{ratio:.1f}"


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


def _too_new(source: str) -> tuple[int, int] | None:
    for marker, version in MINIMUM_VERSION.items():
        if marker in source and sys.version_info < version:
            return version
    return None


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result; the
    exception-group block needs 3.11 and the suggestion block 3.12."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        for marker in MINIMUM_VERSION:
            assert sum(marker in source for _, source in blocks) == 1, marker

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if _too_new(source):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        skipped = sum(1 for version in MINIMUM_VERSION.values() if sys.version_info < version)
        assert ran == EXPECTED_BLOCKS - skipped
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "len(summary) == 202" in s)
        mutated = source.replace("len(summary) == 202", "len(summary) == 201", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
