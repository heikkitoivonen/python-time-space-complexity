"""Tests for docs/stdlib/operator.md.

The page prices each operator function as the operation it dispatches to, `f`,
and the three factories by the lookups or arguments they carry. Those claims
are settled by observation: a counting `__eq__`, `__getitem__` or
`__getattribute__` shows how many operations a call performs, identity shows
whether a target was updated in place, and traced allocation shows what a copy
costs. Timing is used twice, where the claim is about growth that no single
call exposes.

Measurement scope:

* Every name in `operator.__all__` is the same object as in `_operator`, so
  the C implementation is what runs; each double-underscore spelling is the
  same object as its plain name (`__inv__` is `inv`, `__not__` is `not_`).
* `itemgetter` performs one `__getitem__` per key, observed on a counting dict
  with three keys, returns the stored object itself for one key and a k-tuple
  for several. `attrgetter('b.c.d')` performs three `__getattribute__` calls
  and `attrgetter('b.c.d', 'b')` four. A `methodcaller` performs one lookup on
  the object and passes its kept positional and keyword arguments unchanged.
* Sorting 1,000 rows with `itemgetter`, `attrgetter` or `methodcaller` as the
  key records no Python `call` event under `sys.setprofile`; a `lambda` key
  records 1,000, and so does `attrgetter` reading a property. Run in a
  subprocess, so the profile hook cannot reach other tests.
* `countOf` makes 100 comparisons on a 100-item list whose match is at index 3;
  `indexOf` makes 4 there and 100 before raising `ValueError` when nothing
  matches; `contains` on a list stops at the match as `in` does.
* `concat` allocates more than 8 MB for a one-million-item left operand and a
  one-item right one. `iadd` and `iconcat` return the list they were given; a
  timing test appends a one-item list 1,000 times to lists of 1,000 and
  1,000,000 items and the larger costs under 10x the smaller, where a copy of
  the target would cost 1,000x. `iadd` on a one-million-item tuple returns a
  new tuple, leaves the original alone and allocates more than 8 MB.
  `ior` on a set returns the set.
* `reduce(operator.add, parts)` over 500 and 5,000 one-item lists, so p and t
  grow together: 10x the parts costs more than 30x, where linear predicts 10x
  and quadratic 100x; `reduce(operator.iconcat, parts, [])` over the same
  inputs costs under 30x.
  The start value is the list extended, and the parts are unchanged.
* `length_hint` returns `len()` for a sized object, the iterator's remaining
  count for a list iterator part-way through, and the default for a
  generator, which is not advanced.
* `is_` and `is_not` do not call `__eq__`; `and_` and `or_` are bitwise
  (`and_(2, 1) == 0`); `index` rejects a `float`; `concat` and `iconcat`
  reject a non-sequence left operand; `call` (3.11+) and `is_none` and
  `is_not_none` (3.14+) are guarded on `sys.version_info`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `f`, the operation a function dispatches to, is the operands' own cost and
  is priced on the pages for those types; only the dispatch is tested here.
* The O(k) construction bounds of `itemgetter` and `attrgetter`, and O(a) for
  `methodcaller`, follow from Modules/_operator.c storing the keys, the split
  dotted names and the arguments; name and key lengths are treated as O(1).
* The O(a) term in calling a `methodcaller` or `call` is the argument passing
  of the eventual call, read from Modules/_operator.c; argument count is not
  varied.
* The reduce folds hold every part at one item, so p and t are not varied
  apart; O(p·t) for `add` follows from each step copying the prefix, and the
  p term of `iconcat`'s O(p + t) from one call per part, empty or not.
* The list-extension timing takes the fastest of seven runs, so it supports
  the amortized bound, not a bound on each call.
* The 8 MB allocation thresholds assume 8-byte pointers, a 64-bit build.
* The Space of a getter or caller call includes whatever the dispatched
  operation allocates (`f`), which is the operand type's cost and not varied.
"""

from __future__ import annotations

import _operator
import operator
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from functools import reduce
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "operator.md"
EXPECTED_BLOCKS = 10


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


class Counted:
    """A value whose `__eq__` calls are counted; unhashable, as a list item is."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        Counted.comparisons += 1
        return self.value == other

    __hash__ = None  # type: ignore[assignment]


class CountingDict(dict[str, int]):
    """A dict whose `__getitem__` calls are counted."""

    lookups = 0

    def __getitem__(self, key: str) -> int:
        CountingDict.lookups += 1
        return super().__getitem__(key)


class Traced:
    """An object whose attribute lookups are counted."""

    lookups = 0

    def __getattribute__(self, name: str) -> Any:
        Traced.lookups += 1
        return object.__getattribute__(self, name)


class TestTheCImplementationRuns:
    """Every function and factory is C, and the dunder spellings are aliases."""

    def test_every_public_name_comes_from_the_c_module(self) -> None:
        for name in operator.__all__:
            assert getattr(operator, name) is getattr(_operator, name), name

    def test_every_dunder_spelling_is_the_plain_function(self) -> None:
        dunders = [
            name
            for name in dir(operator)
            if name.startswith("__")
            and name.endswith("__")
            and name[2:-2]
            and callable(getattr(operator, name))
        ]
        assert "__add__" in dunders and "__getitem__" in dunders

        for name in dunders:
            base = name[2:-2]
            plain = getattr(operator, base, None) or getattr(operator, base + "_")
            assert getattr(operator, name) is plain, name

    def test_the_irregular_aliases(self) -> None:
        assert operator.__inv__ is operator.inv  # type: ignore[attr-defined]
        assert operator.__not__ is operator.not_  # type: ignore[attr-defined]
        assert operator.__and__ is operator.and_


class TestComparisonAndIdentity:
    """`is_` and `is_not` are O(1) identity checks; the rich comparisons and
    `not_` / `truth` dispatch to the operands."""

    def test_identity_calls_no_method(self) -> None:
        value = Counted(1)
        Counted.comparisons = 0

        assert operator.is_(value, value)
        assert not operator.is_not(value, value)
        assert Counted.comparisons == 0

    def test_eq_dispatches_to_the_operand(self) -> None:
        Counted.comparisons = 0

        assert operator.eq(Counted(1), 1)
        assert Counted.comparisons == 1

    def test_truth_uses_len_when_there_is_no_bool(self) -> None:
        class Sized:
            def __len__(self) -> int:
                return 0

        assert operator.truth(Sized()) is False
        assert operator.not_(Sized()) is True

    def test_bool_takes_precedence_over_len(self) -> None:
        class Both:
            def __bool__(self) -> bool:
                return True

            def __len__(self) -> int:
                raise AssertionError("__len__ was consulted")

        assert operator.truth(Both()) is True
        assert operator.not_(Both()) is False

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_is_none_and_is_not_none(self) -> None:
        assert operator.is_none(None) is True  # type: ignore[attr-defined]
        assert operator.is_none(0) is False  # type: ignore[attr-defined]
        assert operator.is_not_none(0) is True  # type: ignore[attr-defined]


class TestArithmeticAndBitwise:
    """The arithmetic rows cost the operator they name; `and_` and `or_` are
    bitwise; `index` accepts only integers."""

    def test_and_and_or_are_bitwise(self) -> None:
        assert operator.and_(2, 1) == 0
        assert operator.or_(2, 1) == 3
        assert operator.xor(3, 1) == 2

    def test_inv_and_invert_agree(self) -> None:
        assert operator.inv(5) == operator.invert(5) == ~5

    def test_index_rejects_a_float(self) -> None:
        assert operator.index(5) == 5
        with pytest.raises(TypeError):
            operator.index(5.0)  # type: ignore[arg-type]

    def test_add_on_lists_copies_both(self) -> None:
        left, right = [1, 2], [3]

        result = operator.add(left, right)

        assert result == [1, 2, 3]
        assert result is not left and left == [1, 2]


class TestInPlaceOperators:
    """A mutable target is updated and returned at amortized O(len(b)); an
    immutable one is left alone, and building the result costs O(len(a) + len(b))."""

    def test_a_list_is_extended_and_returned(self) -> None:
        items = [1, 2]

        assert operator.iadd(items, [3]) is items
        assert operator.iconcat(items, [4]) is items
        assert items == [1, 2, 3, 4]

    def test_a_tuple_is_not_changed(self) -> None:
        pair = (1, 2)

        result = operator.iadd(pair, (3,))

        assert pair == (1, 2)
        assert result == (1, 2, 3)

    def test_a_set_is_updated_in_place(self) -> None:
        tags = {"a"}

        assert operator.ior(tags, {"b"}) is tags
        assert tags == {"a", "b"}

    def test_a_tuple_target_is_copied(self) -> None:
        big = tuple(range(1_000_000))

        peak = peak_bytes(lambda: operator.iadd(big, (1,)))

        assert peak > 8_000_000, f"iadd on a 10**6-tuple allocated only {peak} bytes"

    @pytest.mark.timing
    def test_extending_a_list_does_not_cost_its_length(self) -> None:
        small = list(range(1_000))
        large = list(range(1_000_000))
        extra = [0]

        def append_many(target: list[int]) -> Callable[[], None]:
            def run() -> None:
                for _ in range(1_000):
                    operator.iadd(target, extra)
                del target[-1_000:]

            return run

        small_ns = best_ns(append_many(small))
        large_ns = best_ns(append_many(large))
        ratio = large_ns / small_ns

        assert ratio < 10, (
            f"1,000 appends to a 10**6 list cost x{ratio:.2f} those to a 10**3 list; "
            "copying the target would cost about x1000"
        )


class TestSequenceOperations:
    """`concat` copies both operands; `countOf` walks everything; `indexOf`
    stops at the first match; `length_hint` never iterates."""

    VALUES = [Counted(index) for index in range(100)]

    def test_count_of_walks_the_whole_list(self) -> None:
        Counted.comparisons = 0

        assert operator.countOf(self.VALUES, 3) == 1
        assert Counted.comparisons == 100

    def test_index_of_stops_at_the_first_match(self) -> None:
        Counted.comparisons = 0

        assert operator.indexOf(self.VALUES, 3) == 3
        assert Counted.comparisons == 4

    def test_index_of_walks_everything_before_raising(self) -> None:
        Counted.comparisons = 0

        with pytest.raises(ValueError):
            operator.indexOf(self.VALUES, -1)
        assert Counted.comparisons == 100

    def test_contains_stops_at_the_match_on_a_list(self) -> None:
        Counted.comparisons = 0

        assert operator.contains(self.VALUES, 3)
        assert Counted.comparisons == 4

    def test_both_take_any_iterable(self) -> None:
        assert operator.countOf((c for c in "banana"), "a") == 3
        assert operator.indexOf(iter("banana"), "n") == 2

    def test_concat_copies_the_left_operand(self) -> None:
        big = list(range(1_000_000))

        peak = peak_bytes(lambda: operator.concat(big, [1]))

        assert peak > 8_000_000, f"concat of a 10**6 list allocated only {peak} bytes"

    def test_concat_needs_a_sequence(self) -> None:
        with pytest.raises(TypeError):
            operator.concat({1: 2}, {3: 4})  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            operator.iconcat({1: 2}, {3: 4})

    def test_getitem_setitem_delitem_accept_slices(self) -> None:
        items = [1, 2, 3, 4]

        assert operator.getitem(items, slice(1, 3)) == [2, 3]
        operator.setitem(items, slice(0, 2), [9])
        operator.delitem(items, slice(-1, None))
        assert items == [9, 3]

    def test_length_hint_asks_and_never_iterates(self) -> None:
        class Sized:
            def __len__(self) -> int:
                return 7

        iterator = iter([1, 2, 3, 4])
        next(iterator)

        def generator() -> Any:
            yield 1

        stream = generator()

        assert operator.length_hint(Sized()) == 7
        assert operator.length_hint(iterator) == 3
        assert operator.length_hint(stream, 9) == 9
        assert next(stream) == 1, "length_hint advanced the generator"


class TestGetters:
    """`itemgetter` and `attrgetter` perform one lookup per key or dotted
    component; one key returns the value, several return a tuple."""

    def test_itemgetter_looks_up_once_per_key(self) -> None:
        record = CountingDict(a=1, b=2, c=3)
        CountingDict.lookups = 0

        assert operator.itemgetter("a", "b", "c")(record) == (1, 2, 3)
        assert CountingDict.lookups == 3

    def test_one_key_returns_the_value_itself(self) -> None:
        inner = [1, 2]

        assert operator.itemgetter(0)([inner]) is inner
        assert operator.itemgetter(*["name"])({"name": "alice"}) == "alice"

    def test_attrgetter_looks_up_each_dotted_component(self) -> None:
        obj = Traced()
        obj.b = Traced()  # type: ignore[attr-defined]
        obj.b.c = Traced()  # type: ignore[attr-defined]
        obj.b.c.d = 5  # type: ignore[attr-defined]

        Traced.lookups = 0
        assert operator.attrgetter("b.c.d")(obj) == 5
        assert Traced.lookups == 3

        middle = obj.b  # type: ignore[attr-defined]
        Traced.lookups = 0
        assert operator.attrgetter("b.c.d", "b")(obj) == (5, middle)
        assert Traced.lookups == 4


class TestMethodcallerAndCall:
    """A `methodcaller` looks the method up once per call and passes its kept
    arguments; `call` is `obj(*args, **kwargs)`."""

    def test_one_lookup_and_the_kept_arguments(self) -> None:
        received: list[tuple[Any, ...]] = []

        class Target(Traced):
            def method(self, *args: Any, **kwargs: Any) -> str:
                received.append((args, kwargs))
                return "done"

        target = Target()
        caller = operator.methodcaller("method", 1, 2, key="value")
        Traced.lookups = 0

        assert caller(target) == "done"
        assert Traced.lookups == 1
        assert received == [((1, 2), {"key": "value"})]

    def test_a_missing_method_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            operator.methodcaller("missing")(1)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_call(self) -> None:
        assert operator.call(divmod, 7, 2) == (3, 1)  # type: ignore[attr-defined]
        assert operator.call(dict, a=1) == {"a": 1}  # type: ignore[attr-defined]


PROFILE_SCRIPT = """
import operator, sys

class Row:
    def __init__(self, value):
        self.value = value

    @property
    def computed(self):
        return self.value

calls = 0

def profile(frame, event, arg):
    global calls
    if event == "call":
        calls += 1

def count(items, key):
    global calls
    calls = 0
    sys.setprofile(profile)
    try:
        sorted(items, key=key)
    finally:
        sys.setprofile(None)
    return calls

values = range(1_000)
print(count([(value,) for value in values], operator.itemgetter(0)))
print(count([Row(value) for value in values], operator.attrgetter("value")))
print(count([str(value) for value in values], operator.methodcaller("casefold")))
print(count([Row(value) for value in values], lambda row: row.value))
print(count([Row(value) for value in values], operator.attrgetter("computed")))
"""


class TestKeyFunctionsRunWithoutAFrame:
    """A C key callable starts no Python frame per element; a `lambda` starts
    one per element. The sort's bound is the same either way."""

    def test_c_getters_record_no_python_calls(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "profile.py"
        script.write_text(PROFILE_SCRIPT, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        item, attr, method, lam, prop = (int(line) for line in result.stdout.split())

        assert (item, attr, method) == (0, 0, 0)
        assert lam == 1_000
        assert prop == 1_000, "a property runs Python code whoever looks it up"


class TestFoldingWithReduce:
    """`reduce(operator.add, parts)` is O(p·t) for p parts totalling t items;
    `reduce(operator.iconcat, parts, [])` is O(p + t). One-item parts make p = t."""

    def test_iconcat_extends_the_start_value(self) -> None:
        parts = [[1, 2], [3], [4, 5]]
        start: list[int] = []

        result = reduce(operator.iconcat, parts, start)

        assert result is start
        assert result == [1, 2, 3, 4, 5]
        assert parts == [[1, 2], [3], [4, 5]]

    def test_without_a_start_value_the_first_part_is_extended(self) -> None:
        parts = [[1, 2], [3]]

        result = reduce(operator.iconcat, parts)

        assert result is parts[0]
        assert parts[0] == [1, 2, 3]

    @staticmethod
    def _ratio(fold: Callable[[list[list[int]]], Any]) -> float:
        small = [[index] for index in range(500)]
        large = [[index] for index in range(5_000)]
        return best_ns(lambda: fold(large), repeats=5) / best_ns(lambda: fold(small), repeats=5)

    @pytest.mark.timing
    def test_add_is_quadratic(self) -> None:
        ratio = self._ratio(lambda parts: reduce(operator.add, parts))

        assert ratio > 30, f"10x the parts cost x{ratio:.1f}; quadratic predicts x100"

    @pytest.mark.timing
    def test_iconcat_is_linear(self) -> None:
        ratio = self._ratio(lambda parts: reduce(operator.iconcat, parts, []))

        assert ratio < 30, f"10x the parts cost x{ratio:.1f}; linear predicts x10"


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
        line, source = next((n, s) for n, s in _blocks() if "countOf(values, 1) == 2" in s)
        mutated = source.replace("countOf(values, 1) == 2", "countOf(values, 1) == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
