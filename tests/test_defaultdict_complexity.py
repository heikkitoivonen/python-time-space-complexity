"""Tests for docs/stdlib/defaultdict.md.

The page prices `collections.defaultdict` as a `dict` whose `dd[key]` fills
in a missing key: a hit is the inherited lookup, and a miss adds one
`default_factory` call and one insertion. Which operations are inherited is
settled by identity with the `dict` slots; which operations call the factory
by counting `__missing__` and factory calls; the linear rows by traced
allocation at two sizes; and the constant miss by one timing ratio.

Measurement scope:

* `__getitem__`, `__setitem__`, `__delitem__`, `__contains__`, `__len__`,
  `__iter__`, `__eq__`, `__ior__`, `get`, `setdefault`, `pop`, `update`,
  `keys`, `values`, `items` and `fromkeys` are asserted to be the `dict`
  attributes themselves; `__missing__`, `copy`, `__copy__`, `__or__`,
  `__ror__` and `__reduce__` are asserted to be the class's own.
* A counting factory runs once for a missing `dd[key]` and not at all for a
  present one, and the key is stored; a counting `__missing__` is called by
  `dd[key]` and by nothing among `get()`, `in`, `setdefault()` and `pop()`,
  and only `setdefault()` stores, its own default. With `default_factory` set to `None`, a miss raises
  `KeyError` carrying the key and inserts nothing.
* `dd[key] += 1` is counted on a subclass recording `__getitem__` and
  `__setitem__`: one of each on a present key. On a missing key the factory
  runs once, the read alone leaves its value stored, and the increment
  overwrites it.
* A timing test makes 5,000 misses and then deletes the 5,000 keys again, on
  mappings of 1,000 and 200,000 int keys; the larger costs under 10x the
  smaller. A miss linear in the current size would cost about 58x, since the
  smaller mapping grows to 6,000 keys during the run and the larger to
  205,000.
* Construction from a mapping, `copy()`, `dd | other` and `other | dd` with a
  two-key `other`, and `small | other` with a two-key `small`, each peak
  between 5x and 40x higher at 200,000 int keys than at 20,000, which is the
  n or m term their rows carry; quadratic growth would give 100x.
  `len(pickle.dumps(dd))` grows by between 5x and 20x over the same step.
* Behaviour is asserted directly: a non-callable first argument raises
  `TypeError`, the remaining arguments reach `dict()`, `copy()` and
  `copy.copy()` keep the factory and share the values, `|` returns a
  `defaultdict` with the `defaultdict` operand's factory on either side, the
  left one's when both are, and raises `TypeError`
  against a list of pairs, `|=` accepts one, `fromkeys()` returns a
  `defaultdict` with no factory, a pickle round trip keeps a `list` factory,
  pickling a lambda factory fails, `==` ignores the factory, and a view sees
  a key added after it was made.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The bounds of the inherited operations, `|=` and `fromkeys()` among them,
  are the `dict` page's; the tests here show the methods are `dict`'s own,
  not their cost.
* The time bounds of construction, `copy()`, `|` and `pickle.dumps()` are not
  timed. Each builds a result that the allocation and length tests show is
  linear in its size, and filling it is the time term.
* `f`, the factory's cost, is caller-supplied; the factories used are `int`,
  `list` and small counting functions.
* `__missing__` stores the factory's value with a set-default in the 3.13
  and 3.14 releases after 3.13.11 and 3.14.2 (gh-142495), and through
  `self[key] = value` before them: a subclass's `__setitem__` sees that store
  only on the older releases, and a value the factory itself stored under the
  key wins only on the newer ones. The tests assert neither.
* Pickling is priced in keys and values; what each one costs to pickle is
  the pickle page's, and only int keys and values are measured. The
  factory's own pickle is not priced: a class or module-level function is
  stored by name, but a picklable callable instance carries its state.
* Keys are ints or short strings throughout; expensive `__hash__` or
  `__eq__` implementations, and values that are expensive to compare or to
  add to, are not varied.
* A factory that stores the requested key itself is not a case the page
  prices.
* Which operand's value `|` keeps for a key both sides hold is the inherited
  `dict` update's; the `|` tests use disjoint keys.

Coverage: the official API inventory names `defaultdict` and
`default_factory`. The audit reports `copy` as needing classification; it
has a row.
"""

from __future__ import annotations

import copy
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "defaultdict.md"
EXPECTED_BLOCKS = 5


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
    """Peak traced allocation while func runs, after one warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingFactory:
    """A default factory that records how often it is called."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return 0


class MissingCounter(defaultdict):  # type: ignore[type-arg]
    """A defaultdict that counts its `__missing__` calls."""

    misses = 0

    def __missing__(self, key: Any) -> Any:
        self.misses += 1
        return super().__missing__(key)


class OperationCounter(defaultdict):  # type: ignore[type-arg]
    """A defaultdict that counts the reads and stores made through it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gets = 0
        self.sets = 0

    def __getitem__(self, key: Any) -> Any:
        self.gets += 1
        return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self.sets += 1
        super().__setitem__(key, value)


class TestInheritedFromDict:
    """The "Inherited from dict" rows cost what they cost on a `dict` because
    they are the `dict` methods; the class defines only the rest."""

    INHERITED = (
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__contains__",
        "__len__",
        "__iter__",
        "__eq__",
        "__ior__",
        "get",
        "setdefault",
        "pop",
        "update",
        "keys",
        "values",
        "items",
    )
    OWN = ("__missing__", "copy", "__copy__", "__or__", "__ror__", "__reduce__")

    @pytest.mark.parametrize("name", INHERITED)
    def test_the_lookup_and_update_methods_are_dicts(self, name: str) -> None:
        assert getattr(defaultdict, name) is getattr(dict, name)

    def test_fromkeys_is_the_dict_class_method(self) -> None:
        assert "fromkeys" not in vars(defaultdict)
        assert defaultdict.fromkeys.__self__ is defaultdict

    @pytest.mark.parametrize("name", OWN)
    def test_the_class_defines_its_own_missing_copy_or_and_reduce(self, name: str) -> None:
        assert name in vars(defaultdict)
        assert getattr(defaultdict, name) is not getattr(dict, name, None)

    def test_equality_ignores_the_factory(self) -> None:
        assert defaultdict(list, a=1) == defaultdict(int, a=1) == {"a": 1}

    def test_views_are_live(self) -> None:
        mapping = defaultdict(int, a=1)
        keys = mapping.keys()

        mapping["b"]

        assert list(keys) == ["a", "b"]


class TestReadingAMissingKeyInsertsIt:
    """`dd[key]` missing | O(1 + f) amortized: one factory call and one stored
    entry; present | O(1): no factory call. `get()`, `in`, `setdefault()` and
    `pop()` never call `__missing__`."""

    def test_a_miss_runs_the_factory_once_and_stores_its_value(self) -> None:
        factory = CountingFactory()
        mapping = defaultdict(factory)

        assert mapping["k"] == 0

        assert factory.calls == 1
        assert dict(mapping) == {"k": 0}, "the read was also a write"

    def test_a_hit_does_not_call_the_factory(self) -> None:
        factory = CountingFactory()
        mapping = defaultdict(factory, k=5)

        assert mapping["k"] == 5

        assert factory.calls == 0

    def test_only_subscription_calls_missing(self) -> None:
        mapping = MissingCounter(list)

        assert mapping.get("a") is None
        assert "b" not in mapping
        assert mapping.setdefault("c", 7) == 7
        assert mapping.pop("d", None) is None

        assert mapping.misses == 0
        assert dict(mapping) == {"c": 7}, "only setdefault() stored, and its own default"

        mapping["e"]

        assert mapping.misses == 1
        assert mapping["e"] == []

    def test_reads_of_absent_keys_grow_the_mapping(self) -> None:
        counts: defaultdict[str, int] = defaultdict(int)
        for key in ("a", "b", "c"):
            _ = counts[key]

        assert len(counts) == 3

    def test_no_factory_raises_and_inserts_nothing(self) -> None:
        mapping: defaultdict[Any, list[int]] = defaultdict(list, present=[1])
        mapping.default_factory = None

        assert mapping["present"] == [1]
        with pytest.raises(KeyError) as raised:
            mapping[("a", "b")]
        assert raised.value.args == (("a", "b"),)
        assert ("a", "b") not in mapping

    def test_the_factory_can_be_reassigned(self) -> None:
        mapping: defaultdict[str, Any] = defaultdict(list)
        mapping.default_factory = set

        assert mapping["k"] == set()

    @pytest.mark.timing
    def test_a_miss_does_not_grow_with_the_mapping(self) -> None:
        keys = [-index - 1 for index in range(5_000)]

        def misses(size: int) -> Callable[[], None]:
            mapping: defaultdict[int, int] = defaultdict(int, dict.fromkeys(range(size), 0))

            def run() -> None:
                for key in keys:
                    mapping[key]
                for key in keys:
                    del mapping[key]

            return run

        small = best_ns(misses(1_000))
        large = best_ns(misses(200_000))
        ratio = large / small

        assert ratio < 10, (
            f"5,000 misses on 200,000 keys cost x{ratio:.2f} those on 1,000 "
            f"({small:.0f}ns to {large:.0f}ns); a miss linear in the size gives about x58"
        )


class TestIncrementIsAReadAndAStore:
    """`dd[key] += 1` | O(1 + f) amortized: a read and a store, and on a
    missing key the read stores the factory's value first."""

    def test_a_present_key_is_one_read_and_one_store(self) -> None:
        counts = OperationCounter(int)
        counts["k"] = 0
        counts.gets = counts.sets = 0

        counts["k"] += 1

        assert (counts.gets, counts.sets) == (1, 1)

    def test_a_missing_key_also_runs_the_factory(self) -> None:
        factory = CountingFactory()

        probe = OperationCounter(factory)
        probe["k"]

        assert factory.calls == 1
        assert dict(probe) == {"k": 0}, "the read alone stores the factory's value"

        counts = OperationCounter(factory)
        counts["k"] += 1

        assert factory.calls == 2
        assert counts.gets == 1
        assert dict(counts) == {"k": 1}, "and the increment stores over it"


class TestBuildingCopyingAndMerging:
    """Construction O(m), `copy()` O(n), `|` O(n + m), `|=` O(m) amortized, and
    `fromkeys()` O(m) with no factory."""

    SIZES = (20_000, 200_000)
    SMALL = {-1: 0, -2: 0}

    @staticmethod
    def grows(build: Callable[[int], Callable[[], Any]]) -> list[int]:
        return [peak_bytes(build(size)) for size in TestBuildingCopyingAndMerging.SIZES]

    def test_construction_grows_with_m(self) -> None:
        def build(size: int) -> Callable[[], Any]:
            source = dict.fromkeys(range(size), 0)
            return lambda: defaultdict(int, source)

        peaks = self.grows(build)

        assert peaks[0] * 5 < peaks[1] < peaks[0] * 40, f"10x the entries: {peaks}"

    def test_copy_grows_with_n(self) -> None:
        peaks = self.grows(lambda size: defaultdict(int, dict.fromkeys(range(size), 0)).copy)

        assert peaks[0] * 5 < peaks[1] < peaks[0] * 40, f"10x the keys: {peaks}"

    @pytest.mark.parametrize("side", ["left", "right"])
    def test_or_grows_with_n(self, side: str) -> None:
        def build(size: int) -> Callable[[], Any]:
            mapping = defaultdict(int, dict.fromkeys(range(size), 0))
            if side == "left":
                return lambda: mapping | self.SMALL
            return lambda: self.SMALL | mapping

        peaks = self.grows(build)

        assert peaks[0] * 5 < peaks[1] < peaks[0] * 40, f"10x the defaultdict's keys: {peaks}"

    def test_or_grows_with_m(self) -> None:
        small = defaultdict(int, self.SMALL)

        def build(size: int) -> Callable[[], Any]:
            other = dict.fromkeys(range(size), 0)
            return lambda: small | other

        peaks = self.grows(build)

        assert peaks[0] * 5 < peaks[1] < peaks[0] * 40, f"10x the other mapping's keys: {peaks}"

    def test_construction_rejects_a_non_callable_factory(self) -> None:
        with pytest.raises(TypeError, match="callable or None"):
            defaultdict(5)  # type: ignore[call-overload]

    def test_the_remaining_arguments_reach_dict(self) -> None:
        mapping = defaultdict(list, [("a", 1)], b=2)

        assert mapping == {"a": 1, "b": 2}
        assert defaultdict().default_factory is None

    @pytest.mark.parametrize("copier", [defaultdict.copy, copy.copy])
    def test_a_copy_is_shallow_and_keeps_the_factory(self, copier: Callable[[Any], Any]) -> None:
        original = defaultdict(list, {key: [key] for key in range(10)})

        copied = copier(original)

        assert type(copied) is defaultdict and copied is not original
        assert copied.default_factory is list
        assert copied == original
        assert all(copied[key] is original[key] for key in original)

    def test_or_keeps_the_factory_on_either_side(self) -> None:
        mapping = defaultdict(list, a=[1])

        left = mapping | {"b": [2]}
        right = {"b": [2]} | mapping

        for result in (left, right):
            assert type(result) is defaultdict
            assert result.default_factory is list
        assert list(left) == ["a", "b"]
        assert list(right) == ["b", "a"]
        assert mapping == {"a": [1]}, "| leaves its operands alone"

    def test_or_of_two_defaultdicts_keeps_the_left_factory(self) -> None:
        merged = defaultdict(list, a=[1]) | defaultdict(int, b=2)

        assert merged.default_factory is list
        assert merged == {"a": [1], "b": 2}

    def test_or_needs_a_dict(self) -> None:
        with pytest.raises(TypeError):
            defaultdict(list) | [("a", 1)]  # type: ignore[operator]

    def test_in_place_or_takes_pairs(self) -> None:
        mapping = defaultdict(list, a=[1])
        before = mapping

        mapping |= [("c", [3])]

        assert mapping is before
        assert list(mapping) == ["a", "c"]

    def test_fromkeys_has_no_factory(self) -> None:
        keys = defaultdict.fromkeys("xy", 0)

        assert type(keys) is defaultdict
        assert keys.default_factory is None
        assert keys == {"x": 0, "y": 0}


class TestPickling:
    """`pickle.dumps(dd)` | O(n): keys and values, and a factory that must be
    picklable itself."""

    def test_a_round_trip_keeps_a_class_factory(self) -> None:
        mapping = defaultdict(list, a=[1])

        restored = pickle.loads(pickle.dumps(mapping))

        assert restored == mapping
        assert restored.default_factory is list

    def test_a_lambda_factory_cannot_be_pickled(self) -> None:
        with pytest.raises((pickle.PicklingError, AttributeError)):
            pickle.dumps(defaultdict(lambda: 0))

    def test_the_pickle_grows_with_n(self) -> None:
        lengths = [
            len(pickle.dumps(defaultdict(int, dict.fromkeys(range(size), 0))))
            for size in (20_000, 200_000)
        ]
        ratio = lengths[1] / lengths[0]

        assert 5 < ratio < 20, f"10x the keys gave x{ratio:.2f}: {lengths}"


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
        line, source = next((n, s) for n, s in _blocks() if "len(groups) == 2" in s)
        mutated = source.replace("len(groups) == 2", "len(groups) == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
