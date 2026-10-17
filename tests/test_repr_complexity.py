"""Tests for docs/builtins/repr.md.

The page prices `repr()` by the length of what it returns, plus the elements'
own reprs for a container, a quadratic decimal conversion for an int, and a
copy of nested text at each level of nesting. Call counters settle how often
`__repr__` runs and what `logging` defers; output lengths settle the escape
expansion; the growth of the conversions and of nesting is timed.

Measurement scope:

* Floats from the subnormal minimum to the largest finite value, negatives,
  infinities and NaN are asserted to render in at most 24 characters, and
  complex numbers built from them in at most 51, so their repr does not grow
  with the value.
* `repr(int)` is timed at 1,000 and 4,000 digits: the 4x step must cost more
  than 9x (quadratic predicts 16x, linear 4x). An int of 5,001 digits raises
  `ValueError` under the default limit of 4,300 digits.
* `repr(str)` is timed at 10,000, 100,000 and 1,000,000 characters; each 10x
  step must cost more than 4x and less than 50x. A string of 10 characters
  U+E0001 renders in 102 characters, and 10 bytes of 0xFF in 43.
* `repr(list)` of 10,000, 100,000 and 1,000,000 ints is timed with the same
  bounds. A counting `__repr__` runs exactly once per list element and once
  per dict key and value, and again on a second call.
* A dict and a set of 200,000 ints with all but 10 removed must cost more than
  50x a fresh 10-item one to render.
* An object returning a prepared 1,000,000-character repr is wrapped in 1,
  20 and 400 nested lists. Each 20x depth step must cost more than 6x, while
  `L` grows by only 798 characters overall. Returning the same string by
  identity keeps leaf rendering constant; repeated copying predicts about
  20x per step, while work proportional only to `L` predicts about 1x.
  The payload length and ASCII character width are fixed. A chain of 50
  lists renders as 51 brackets each side.
* A list and a dict that contain themselves render `[...]` and `{...}`, and a
  tuple reached again through a list renders `(...)`.
* The default `object.__repr__` is matched against `<module.Name object at
  0x...>`. A `__repr__` returning a non-str raises `TypeError`. `str()`,
  `f"{x!r}"` and `"%r" % x` of a list are asserted equal to `repr()`, and
  `str()` of a list with a str element quotes it.
* `reprlib.repr()` of a 1,000,000-element list is held under 3x the cost of a
  10-element one.
* A logger at WARNING calls a counting `__repr__` zero times for
  `debug("%r", obj)` and once for `debug(f"{obj!r}")`.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* Recursion detection scans the containers currently being rendered
  (`Py_ReprEnter` in Objects/object.c, 3.11.14 through 3.15.0), O(h) per
  container; every container adds at least two characters at its depth, so
  that scan stays within the O(L·h) copying bound and is not timed apart.
* The O(1) default `object.__repr__` treats the class's module and qualified
  names as short; their length was not varied.
* The container timings use int elements; element type and the cost of a
  user `__repr__` were not varied beyond the call counts.
"""

from __future__ import annotations

import itertools
import logging
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "repr.md"
EXPECTED_BLOCKS = 6


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


class Counted:
    """An object whose `__repr__` counts its calls."""

    calls = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __repr__(self) -> str:
        type(self).calls += 1
        return f"Counted({self.value})"

    def __hash__(self) -> int:
        return self.value


class TestScalarsDoNotGrow:
    """`repr(x)` for `None`, a `bool`, a `float` or a `complex` | O(1) | O(1)."""

    def test_floats_render_in_a_bounded_length(self) -> None:
        values = [
            5e-324,
            -5e-324,
            sys.float_info.min,
            sys.float_info.max,
            -sys.float_info.max,
            1 / 3,
            -2 / 3,
            math.inf,
            -math.inf,
            math.nan,
        ]
        for value in values:
            assert len(repr(value)) <= 24, value
            assert len(repr(complex(value, -sys.float_info.max))) <= 51, value

    def test_the_singletons(self) -> None:
        assert (repr(None), repr(True), repr(False)) == ("None", "True", "False")


class TestIntConversionIsQuadratic:
    """`repr(x)` for an `int` | O(d²) | O(d) | Raises beyond the digit limit."""

    @pytest.mark.timing
    def test_four_times_the_digits_costs_far_more_than_four_times(self) -> None:
        small, large = int("7" * 1_000), int("7" * 4_000)
        small_ns = best_ns(lambda: repr(small), inner=20)
        large_ns = best_ns(lambda: repr(large), inner=5)
        assert large_ns > small_ns * 9, f"1,000 digits {small_ns:.0f}ns, 4,000 {large_ns:.0f}ns"

    def test_more_digits_than_the_limit_raise(self) -> None:
        limit = sys.get_int_max_str_digits()
        assert limit == 4300
        with pytest.raises(ValueError, match="Exceeds the limit"):
            repr(10**5000)


def _assert_linear(times: list[float]) -> None:
    for smaller, larger in itertools.pairwise(times):
        assert smaller * 4 < larger < smaller * 50, f"{times}"


class TestStringsAndBytes:
    """`repr(s)` for a `str` and `repr(b)` for `bytes` | O(n) | O(n)."""

    @pytest.mark.timing
    def test_a_string_renders_in_linear_time(self) -> None:
        times = []
        for n in (10_000, 100_000, 1_000_000):
            s = "a" * n
            times.append(best_ns(lambda s=s: repr(s)))
        _assert_linear(times)

    def test_a_character_becomes_at_most_ten(self) -> None:
        assert repr("\U000e0001" * 10) == "'" + "\\U000e0001" * 10 + "'"
        assert len(repr("\U000e0001" * 10)) == 102

    def test_a_byte_becomes_at_most_four(self) -> None:
        assert len(repr(b"\xff" * 10)) == 43
        assert max(len(repr(bytes([i]))) for i in range(256)) == 7  # b'\xff'


class TestContainersRenderEachElementOnce:
    """`repr(x)` for a list, tuple, dict or set | O(L) plus the elements' reprs."""

    def test_a_list_calls_each_elements_repr_once(self) -> None:
        items = [Counted(i) for i in range(100)]
        Counted.calls = 0
        repr(items)
        assert Counted.calls == 100
        repr(items)
        assert Counted.calls == 200, "nothing is cached between calls"

    def test_a_dict_calls_each_key_and_value_once(self) -> None:
        d = {Counted(i): Counted(-i) for i in range(100)}
        Counted.calls = 0
        repr(d)
        assert Counted.calls == 200

    @pytest.mark.timing
    def test_a_list_renders_in_linear_time(self) -> None:
        times = []
        for n in (10_000, 100_000, 1_000_000):
            lst = list(range(2_000, 2_000 + n))
            times.append(best_ns(lambda lst=lst: repr(lst), repeats=5))
        _assert_linear(times)


class TestASparseHashTableCostsItsFormerSize:
    """`repr(x)` for a dict or set walks its hash table."""

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["dict", "set"])
    def test_removed_items_still_cost(self, kind: str) -> None:
        if kind == "dict":
            sparse: Any = dict.fromkeys(range(200_000), 0)
            for key in range(10, 200_000):
                del sparse[key]
            fresh: Any = dict.fromkeys(range(10), 0)
        else:
            sparse = set(range(200_000))
            for item in range(10, 200_000):
                sparse.discard(item)
            fresh = set(range(10))
        assert repr(sparse) == repr(fresh)
        sparse_ns = best_ns(lambda: repr(sparse))
        fresh_ns = best_ns(lambda: repr(fresh), inner=100)
        assert sparse_ns > fresh_ns * 50, f"fresh {fresh_ns:.0f}ns, sparse {sparse_ns:.0f}ns"


def _wrap(item: Any, depth: int) -> list[Any]:
    wrapped: list[Any] = [item]
    for _ in range(depth - 1):
        wrapped = [wrapped]
    return wrapped


class TestNestedTextIsCopiedOncePerLevel:
    """Containers nested h levels deep | O(L·h) at most | Each level copies its text.

    Prepared text at depths 1, 20 and 400 leaves `L` almost unchanged, so a
    bound in `L` alone predicts equal cost. The leaf returns its text without
    scanning or escaping it, isolating the containers' copying cost.
    """

    @pytest.mark.timing
    def test_depth_multiplies_the_cost_of_the_same_text(self) -> None:
        text = "a" * 1_000_000

        class PreparedRepr:
            def __repr__(self) -> str:
                return text

        leaf = PreparedRepr()
        assert repr(leaf) is text
        depths = (1, 20, 400)
        times = []
        for depth in depths:
            nested = _wrap(leaf, depth)
            assert repr(nested) == "[" * depth + text + "]" * depth
            times.append(best_ns(lambda nested=nested: repr(nested), inner=3))

        for smaller, larger in itertools.pairwise(times):
            assert larger > smaller * 6, f"depths {depths}: {times} ns"

    def test_a_chain_renders_its_brackets(self) -> None:
        assert repr(_wrap([], 50)) == "[" * 51 + "]" * 51

    def test_self_references_are_not_rendered_again(self) -> None:
        lst: list[Any] = [1]
        lst.append(lst)
        assert repr(lst) == "[1, [...]]"
        d: dict[str, Any] = {}
        d["self"] = d
        assert repr(d) == "{'self': {...}}"
        inner: list[Any] = []
        t = (inner,)
        inner.append(t)
        assert repr(t) == "([(...)],)"


class _Plain:
    pass


class TestUserDefinedObjects:
    """The default `object.__repr__` is O(1); a `__repr__` must return a str."""

    def test_the_default_repr(self) -> None:
        assert re.fullmatch(
            rf"<{re.escape(__name__)}\._Plain object at 0x[0-9a-fA-F]+>", repr(_Plain())
        )

    def test_a_non_str_result_raises(self) -> None:
        class Bad:
            def __repr__(self) -> str:
                return 42  # type: ignore[return-value]

        with pytest.raises(TypeError):
            repr(Bad())

    def test_str_and_the_r_conversions_match_repr(self) -> None:
        items = ["a", 1, (2,)]
        assert str(items) == f"{items!r}" == "%r" % (items,) == repr(items)  # noqa: UP031 - the subject
        assert str(items) == "['a', 1, (2,)]"


class TestTruncating:
    """`reprlib.repr()` reads only the first few elements of a list."""

    @pytest.mark.timing
    def test_reprlib_does_not_grow_with_the_list(self) -> None:
        import reprlib

        small, large = list(range(10)), list(range(1_000_000))
        small_ns = best_ns(lambda: reprlib.repr(small), inner=100)
        large_ns = best_ns(lambda: reprlib.repr(large), inner=100)
        assert large_ns < small_ns * 3, f"10 items {small_ns:.0f}ns, 1,000,000 {large_ns:.0f}ns"


class TestLoggingDefersRepr:
    """`%r` with the object defers `repr()` to an emitted record; an f-string does not."""

    def test_only_the_f_string_renders(self) -> None:
        log = logging.getLogger("test-repr-deferral")
        log.setLevel(logging.WARNING)
        obj = Counted(1)
        Counted.calls = 0
        log.debug("state: %r", obj)
        assert Counted.calls == 0
        log.debug(f"state: {obj!r}")
        assert Counted.calls == 1


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
        target = 'assert repr(lst) == "[1, 2, [...]]"'
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, 'assert repr(lst) == "[1, 2, [1, 2]]"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
