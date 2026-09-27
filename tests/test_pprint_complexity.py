"""Tests for docs/stdlib/pprint.md.

The page prices pretty-printing as O(d·(D·r + s)): every level too wide for
one line is rendered whole on one line and then again item by item, so a leaf
nested under d broken levels is rendered d + 1 times, and every broken level
keeps its one-line string while its items are formatted. The one-line renderer
itself is O(D·r + s): each enclosing dict, list or tuple copies its items'
text into its own string. Render counts are
settled by a leaf whose `__repr__` counts its calls and by a key whose `__lt__`
counts comparisons, which need no tolerance; space is settled by traced peaks
at a fixed r and a growing d; one timing test confirms the render counts show
up as time.

Measurement scope:

* A list of 100 counting leaves wrapped in 0, 10 and 100 single-item lists,
  each too wide for the line: every leaf is rendered 2, 12 and 102 times, so
  d + 1 with d counting the inner list and its wrappers. With `width` wide
  enough for one line it is rendered once, and `pformat()` equals
  `saferepr()`.
* `list(range(3000))` flat and under 100 wrappers has the same r to within
  200 characters; `pformat()` of the deep one takes more than 10x as long as
  the flat one (timing).
* A 1,000,000-character string in a one-item list, and that list under 300
  more single-item lists:
  `saferepr()` of the deep one takes more than 2x as long (timing), which is
  the D term: r grows by 600 characters, and every wrapper copies the whole
  string once more.
* Two 100,000-character strings under 1 and under 100 wrappers: the traced
  peak of `pformat()` grows more than 8x, and so does `pprint()` into a sink
  that discards what it is given, so writing as it goes does not lower the
  peak; `saferepr()` of the deep one peaks under 2x the flat one.
* A 500-key dict of counting keys: `saferepr()` sorts it once, `pformat()`
  twice (the one-line attempt and the broken dict), and `pformat()` of it
  under three broken wrappers five times, by exact comparison count;
  `sort_dicts=False` and `pp()` compare no keys. A 200-item set is compared
  when `pformat(sort_dicts=False)` breaks it and not by `saferepr()`. A
  `Counter` with counting values is compared with `sort_dicts=False`, on one
  line.
* `depth=1` renders no leaf inside an elided list; a set below the depth is
  written out in full; with `width=5` the shortened line does not fit, and
  the lists below the depth are formatted in full.
* With `compact=True`, a leaf in a list broken at `width=1` is rendered three
  times rather than two, the extra attempt the page notes.
* `isrecursive()` and `isreadable()` render every leaf of a 100-leaf list
  whose first item is a cycle, and `PrettyPrinter(depth=1).isreadable()`
  renders leaves three levels down.
* A `PrettyPrinter` built with `stream=None` writes to the `sys.stdout` of its
  construction, not of the call; from 3.11 it writes nothing when that is
  `None`, and on 3.10 it raises `AttributeError`.
* A chain nested half the recursion limit deep raises `RecursionError` from
  `saferepr()` and `pformat()` and not from `repr()`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `PrettyPrinter()` is O(1) by source: the constructor validates and stores
  its arguments (Lib/pprint.py, 3.10 to 3.14) and formats nothing.
* That each sort is O(k log k) is `sorted()`'s bound; the tests count how many
  sorts happen, not the comparisons within one.
* Width, indent, `compact` and `underscore_numbers` are held at their defaults
  or at a few fixed values chosen to force or avoid line breaks; the page
  treats width and indent as constants, and long whitespace-separated strings
  wrapped by `width` are not measured.
* Only lists, dicts, sets and `Counter` are nested; tuples, deques, dataclasses
  and `SimpleNamespace` follow the same `_format` path by source and are not
  varied.
"""

from __future__ import annotations

import collections
import io
import pathlib
import pprint
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pprint.md"
EXPECTED_BLOCKS = 9


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


def wrap(obj: Any, levels: int) -> Any:
    """`obj` inside `levels` single-item lists."""
    for _ in range(levels):
        obj = [obj]
    return obj


class Leaf:
    """A leaf that counts how often it is rendered."""

    renders = 0

    def __repr__(self) -> str:
        Leaf.renders += 1
        return "L" * 20


class Key:
    """A dict key that counts comparisons."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __lt__(self, other: Key) -> bool:
        Key.comparisons += 1
        return self.value < other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"K{self.value}"


class DiscardingSink(io.StringIO):
    """A stream that keeps nothing it is given."""

    def write(self, text: str) -> int:
        return len(text)


@pytest.fixture(autouse=True)
def _reset_counters() -> None:
    Leaf.renders = 0
    Key.comparisons = 0


def leaves(count: int = 100) -> list[Leaf]:
    return [Leaf() for _ in range(count)]


class TestNestingMultipliesRenders:
    """`pformat` | O(d·(r + s)): a leaf under d broken levels is rendered
    d + 1 times; a structure that fits is rendered once."""

    @pytest.mark.parametrize(("wrappers", "expected"), [(0, 2), (10, 12), (100, 102)])
    def test_each_broken_level_renders_its_subtree_again(
        self, wrappers: int, expected: int
    ) -> None:
        pprint.pformat(wrap(leaves(), wrappers))

        assert Leaf.renders == 100 * expected

    def test_data_that_fits_is_rendered_once(self) -> None:
        data = wrap(leaves(), 10)

        text = pprint.pformat(data, width=10**6)

        assert Leaf.renders == 100
        Leaf.renders = 0
        assert text == pprint.saferepr(data)
        assert Leaf.renders == 100

    def test_the_same_output_lines_at_any_depth(self) -> None:
        flat = list(range(1_000))

        assert pprint.pformat(wrap(flat, 20)).count("\n") == pprint.pformat(flat).count("\n")

    @pytest.mark.timing
    def test_depth_at_a_fixed_r_costs_time(self) -> None:
        flat = list(range(3_000))
        deep = wrap(flat, 100)
        assert len(pprint.saferepr(deep)) - len(pprint.saferepr(flat)) == 200

        flat_ns = best_ns(lambda: pprint.pformat(flat))
        deep_ns = best_ns(lambda: pprint.pformat(deep))

        assert deep_ns > flat_ns * 10, f"100 extra levels: {flat_ns:.0f}ns -> {deep_ns:.0f}ns"

    @pytest.mark.timing
    def test_saferepr_copies_the_text_once_per_enclosing_level(self) -> None:
        text = "x" * 1_000_000
        flat = [text]
        deep = wrap(flat, 300)
        assert len(pprint.saferepr(deep)) - len(pprint.saferepr(flat)) == 600

        flat_ns = best_ns(lambda: pprint.saferepr(flat))
        deep_ns = best_ns(lambda: pprint.saferepr(deep))

        assert deep_ns > flat_ns * 2, f"300 extra levels: {flat_ns:.0f}ns -> {deep_ns:.0f}ns"

    def test_compact_adds_an_attempt_per_broken_level(self) -> None:
        pprint.pformat([Leaf()], width=1)
        assert Leaf.renders == 2

        Leaf.renders = 0
        pprint.pformat([Leaf()], width=1, compact=True)
        assert Leaf.renders == 3


class TestBrokenLevelsHoldTheirStrings:
    """Space O(d·r) for `pformat` and `pprint`, O(r) for `saferepr`."""

    TEXT = "x" * 100_000

    def chain(self, wrappers: int) -> Any:
        return wrap([self.TEXT, self.TEXT], wrappers)

    def test_pformat_peak_grows_with_depth(self) -> None:
        shallow = peak_bytes(lambda: pprint.pformat(self.chain(1)))
        deep = peak_bytes(lambda: pprint.pformat(self.chain(100)))

        assert deep > shallow * 8, f"1 -> 100 levels at a fixed r: {shallow} -> {deep} bytes"

    def test_pprint_to_a_stream_does_not_lower_the_peak(self) -> None:
        def pprint_to_sink(wrappers: int) -> None:
            pprint.pprint(self.chain(wrappers), stream=DiscardingSink())

        shallow = peak_bytes(lambda: pprint_to_sink(1))
        deep = peak_bytes(lambda: pprint_to_sink(100))

        assert deep > shallow * 8, f"1 -> 100 levels at a fixed r: {shallow} -> {deep} bytes"

    def test_saferepr_peak_does_not(self) -> None:
        shallow = peak_bytes(lambda: pprint.saferepr(self.chain(1)))
        deep = peak_bytes(lambda: pprint.saferepr(self.chain(100)))

        assert deep < shallow * 2, f"1 -> 100 levels at a fixed r: {shallow} -> {deep} bytes"


class TestSorting:
    """s: dicts sorted with `sort_dicts=True` once per rendering, sets sorted
    when broken, `Counter` always sorted."""

    @staticmethod
    def keyed(count: int = 500) -> dict[Key, int]:
        values = list(range(count))
        random.Random(0).shuffle(values)
        return {Key(value): 0 for value in values}

    def test_saferepr_sorts_once(self) -> None:
        pprint.saferepr(self.keyed())

        assert Key.comparisons > 500

    def test_every_broken_level_sorts_again(self) -> None:
        data = self.keyed()
        pprint.saferepr(data)
        one_sort = Key.comparisons

        Key.comparisons = 0
        pprint.pformat(data)
        assert Key.comparisons == 2 * one_sort

        Key.comparisons = 0
        pprint.pformat(wrap(data, 3))
        assert Key.comparisons == 5 * one_sort

    def test_sort_dicts_false_and_pp_compare_no_keys(self) -> None:
        data = self.keyed()

        pprint.pformat(data, sort_dicts=False)
        pprint.pp(data, stream=DiscardingSink())

        assert Key.comparisons == 0

    def test_pp_keeps_insertion_order(self) -> None:
        out = io.StringIO()

        pprint.pp({"b": 1, "a": 2}, stream=out)

        assert out.getvalue() == "{'b': 1, 'a': 2}\n"

    def test_a_broken_set_is_sorted_whatever_sort_dicts_says(self) -> None:
        items = {Key(value) for value in range(200)}

        pprint.saferepr(items)
        assert Key.comparisons == 0

        pprint.pformat(items, sort_dicts=False)
        assert Key.comparisons > 0

    def test_a_counter_is_sorted_even_on_one_line(self) -> None:
        counts = collections.Counter({f"k{value}": Key(value) for value in range(50)})

        text = pprint.pformat(counts, sort_dicts=False, width=10**6)

        assert "\n" not in text
        assert Key.comparisons > 0


class TestLimitingDepth:
    """`depth` elides dicts, lists and tuples below it, so what they hold is
    never rendered; other containers are not cut."""

    def test_an_elided_list_renders_nothing(self) -> None:
        data = {"a": leaves()}

        assert pprint.pformat(data, depth=1) == "{'a': [...]}"
        assert Leaf.renders == 0

    def test_a_level_too_wide_even_when_cut_is_formatted_in_full(self) -> None:
        assert pprint.pformat([[1, 2], [3, 4]], depth=1, width=5) == "[[1,\n  2],\n [3,\n  4]]"

    def test_a_set_below_the_depth_is_not_cut(self) -> None:
        assert pprint.pformat([{1, 2}], depth=1) == "[{1, 2}]"
        assert pprint.pformat([[1, 2]], depth=1) == "[[...]]"


class TestSafeRepresentations:
    """`saferepr`, `isreadable`, `isrecursive` | O(r + s): the whole string is
    built even when the first item decides the flag."""

    def test_a_cycle_is_marked_not_followed(self) -> None:
        data: dict[str, Any] = {"a": 1}
        data["self"] = data

        assert pprint.saferepr(data).startswith("{'a': 1, 'self': <Recursion on dict with id=")
        assert repr(data) == "{'a': 1, 'self': {...}}"
        assert pprint.isrecursive(data) is True
        assert pprint.isreadable(data) is False

    def test_readability(self) -> None:
        assert pprint.isreadable({"a": [1, 2]}) is True
        assert pprint.isreadable(object()) is False

    def test_the_flags_render_every_leaf(self) -> None:
        cycle: list[Any] = []
        cycle.append(cycle)
        data = [cycle, *leaves()]

        assert pprint.isrecursive(data) is True
        assert Leaf.renders == 100
        assert pprint.isreadable(data) is False
        assert Leaf.renders == 200

    def test_printer_flags_ignore_depth(self) -> None:
        printer = pprint.PrettyPrinter(depth=1)

        assert printer.isreadable([[leaves()]]) is True
        assert Leaf.renders == 100
        assert printer.isrecursive([[leaves()]]) is False
        assert Leaf.renders == 200

    def test_printer_flags_honour_sort_dicts(self) -> None:
        data = TestSorting.keyed()

        pprint.PrettyPrinter(sort_dicts=False).isreadable(data)
        assert Key.comparisons == 0
        pprint.PrettyPrinter().isreadable(data)
        assert Key.comparisons > 0

    def test_deep_nesting_raises_where_repr_does_not(self) -> None:
        deep = wrap([], sys.getrecursionlimit() // 2)

        assert repr(deep).startswith("[[[")
        with pytest.raises(RecursionError):
            pprint.saferepr(deep)
        with pytest.raises(RecursionError):
            pprint.pformat(deep)


class TestPrettyPrinter:
    """`PrettyPrinter(...)` | O(1): it stores settings, binding `sys.stdout`
    as it is at construction."""

    def test_stdout_is_bound_at_construction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        first, second = io.StringIO(), io.StringIO()
        monkeypatch.setattr(sys, "stdout", first)
        printer = pprint.PrettyPrinter()
        monkeypatch.setattr(sys, "stdout", second)

        printer.pprint([1])

        assert first.getvalue() == "[1]\n"
        assert second.getvalue() == ""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="3.11 stopped writing to None")
    def test_nothing_is_written_when_stdout_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdout", None)

        pprint.pprint([1])
        pprint.PrettyPrinter().pprint([1])

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 still writes to None")
    def test_310_raises_when_stdout_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdout", None)

        with pytest.raises(AttributeError):
            pprint.pprint([1])

    def test_format_is_called_again_for_each_broken_level(self) -> None:
        calls: list[Any] = []

        class Recording(pprint.PrettyPrinter):
            def format(
                self, object: Any, context: dict[int, int], maxlevels: int, level: int
            ) -> tuple[str, bool, bool]:
                if isinstance(object, Leaf):
                    calls.append(object)
                return super().format(object, context, maxlevels, level)

        Recording().pformat(wrap(leaves(), 5))

        assert len(calls) == 100 * 7

    def test_settings_change_layout(self) -> None:
        compact = pprint.PrettyPrinter(width=40, compact=True).pformat(list(range(30)))

        assert compact.count("\n") == 2
        assert pprint.PrettyPrinter(underscore_numbers=True).pformat(10**9) == "1_000_000_000"
        assert pprint.PrettyPrinter(indent=4, width=5).pformat([1, 2]) == "[   1,\n    2]"


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
        line, source = next((n, s) for n, s in _blocks() if "assert calls == 0" in s)
        mutated = source.replace("assert calls == 0", "assert calls == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
