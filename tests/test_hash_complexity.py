"""Tests for docs/builtins/hash.md.

hash() is builtin_hash in Python/bltinmodule.c, which calls PyObject_Hash and
so the type's tp_hash. long_hash (Objects/longobject.c) folds every 30-bit
digit on each call and keeps nothing; unicode_hash and bytes_hash store the
result on the object; frozenset_hash (Objects/setobject.c) combines the hashes
stored in the set's table and stores its own; tuple_hash (Objects/tupleobject.c)
hashes every item, and from v3.14.2 stores the result in ob_hash, which
v3.11.14, v3.12.12 and v3.13.11 do not have. The set operations between two
sets look elements up with the hash stored in each table entry.

Call counts settle which hashes are recomputed and which comparisons a
collision costs; timing ratios settle the linear first hash, the O(1) kept
hash and the O(m) int hash.

Measurement scope:

* int: hashing ints of 1,000, 10,000 and 100,000 30-bit digits; each 10x step
  is asserted between x4 and x25. hash(n + modulus) == hash(n), ints that are
  multiples of sys.hash_info.modulus all hash to 0, and an integral float
  hashes like the equal int.
* str and bytes: the first hash of a fresh object of 10,000, 100,000 and
  1,000,000 characters, each 10x step between x4 and x25; hashing the same
  object again is under x3 from 1,000 to 1,000,000 characters.
* tuple: hashing a 100-item tuple calls each item's `__hash__` once; a second
  hash of the same tuple calls none on 3.14+ and 100 before. A tuple of tuples
  hashes the inner tuples' items too.
* frozenset: hashing it calls no item's `__hash__`; the first hash of a fresh
  frozenset of 10,000, 100,000 and 1,000,000 ints, each 10x step between x4
  and x25; a second hash is under x3 from 1,000 to 1,000,000 items.
* an instance's own `__hash__` is called once by each of hash(), a dict
  lookup and a set test, three in all for three operations.
* list, dict, set, bytearray and a class defining only `__eq__` raise
  TypeError; that class's `__hash__` is None.
* collisions: building a set of c instances with distinct hashes calls
  `__eq__` zero times; with one shared hash, building 200 and 2,000 calls it
  at least c(c-1)/2 times and the 10x step is over x30 (quadratic predicts
  x100, linear x10). A missing key in a dict of 1,000 colliding keys is
  compared with every one of them (1,000 to 1,100 calls). Building a set of
  1,000 and of 10,000 positive multiples of the hash modulus: the 10x step
  costs over x30.
* set operations: `&`, `|`, `-`, `^`, `<=`, `isdisjoint` and copies between
  sets and frozensets call no `__hash__`, nor does `==` between two equal-sized
  sets, nor copying a dict; `intersection(list)` calls
  it once per list item. `small & big` and `big & small` with 100 small
  elements cost under x3 as big grows from 10,000 to 1,000,000.
* PYTHONHASHSEED=1 and =2 in two subprocesses give different str and bytes
  hashes and the same int hash.
* every fenced block runs in its own subprocess; the blocks assert their own
  results.

Not settled here:

* float hashing is O(1): _Py_HashDouble's loop runs over the 53 bits of the
  mantissa, which is fixed, read from Python/pyhash.c.
* hash() of None, a bool or an instance without `__hash__` is O(1): the
  default object hash is computed from the pointer, read from Objects/object.c.
* the average-case O(1) of a dict or set lookup with distinct hashes is the
  dict and set pages' claim; this file counts only the comparisons collisions
  add.
* NaN floats hash by identity, so no float claim is made across processes.
* Not varied: the cost of an item's own hash inside a tuple (k), a `__hash__`
  whose cost grows with the instance (h), and str kinds other than ASCII.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "hash.md"
EXPECTED_BLOCKS = 9

LINEAR_LOW, LINEAR_HIGH = 4.0, 25.0
CONSTANT = 3.0


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


def first_hash_ns(build: Callable[[], object], repeats: int = 5) -> float:
    """Fastest hash() of a freshly built object, built outside the measurement."""
    best: float | None = None
    for _ in range(repeats):
        fresh = build()
        start = time.perf_counter_ns()
        hash(fresh)
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def assert_linear(label: str, times: list[float]) -> None:
    for small, large in zip(times, times[1:], strict=False):
        ratio = large / small
        assert LINEAR_LOW < ratio < LINEAR_HIGH, (
            f"{label} grew x{ratio:.2f} on a 10x step (times {times}); linear predicts x10"
        )


class Counted:
    """A key that counts its `__hash__` and `__eq__` calls."""

    hashes = 0
    comparisons = 0

    def __init__(self, value: int, fixed_hash: int | None = None) -> None:
        self.value = value
        self.fixed_hash = fixed_hash

    def __hash__(self) -> int:
        type(self).hashes += 1
        return hash(self.value) if self.fixed_hash is None else self.fixed_hash

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, Counted) and self.value == other.value

    @classmethod
    def reset(cls) -> None:
        cls.hashes = 0
        cls.comparisons = 0


class TestIntHashIsLinearInDigits:
    """`hash()` of an `int` | O(m), recomputed on every call."""

    @pytest.mark.timing
    def test_hashing_grows_with_the_digits(self) -> None:
        values = [1 << (30 * digits - 1) for digits in (1_000, 10_000, 100_000)]

        times = [best_ns(lambda value=value: hash(value), inner=5) for value in values]

        assert_linear("hash() of an int", times)

    def test_ints_are_reduced_modulo_the_hash_prime(self) -> None:
        modulus = sys.hash_info.modulus

        assert hash(modulus + 5) == hash(5)
        assert {hash(i * modulus) for i in range(1, 6)} == {0}
        assert hash(-1) == -2
        assert hash(256) == 256

    def test_an_integral_float_hashes_like_the_int(self) -> None:
        assert hash(1.0) == hash(1) == hash(True)
        assert hash(2.0**80) == hash(2**80)
        table: dict[float, str] = {1: "one"}
        assert table[1.0] == "one"


class TestStrAndBytesKeepTheirHash:
    """`hash()` of a `str` or `bytes` | O(n) first call, O(1) after."""

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", [str, bytes])
    def test_the_first_hash_is_linear(self, kind: type) -> None:
        unit: str | bytes = "q" if kind is str else b"q"

        times = [first_hash_ns(lambda size=size: unit * size) for size in (10_000, 100_000, 10**6)]

        assert_linear(f"the first hash() of a {kind.__name__}", times)

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", [str, bytes])
    def test_a_second_hash_does_not_grow(self, kind: type) -> None:
        unit: str | bytes = "q" if kind is str else b"q"
        small, large = unit * 1_000, unit * 10**6
        hash(small)
        hash(large)

        ratio = best_ns(lambda: hash(large), inner=100) / best_ns(lambda: hash(small), inner=100)

        assert ratio < CONSTANT, f"a kept hash() cost x{ratio:.2f} on 1,000x the length"


class TestTupleHashesEveryItem:
    """`hash()` of a `tuple` | O(n·k) first call; O(1) after it on 3.14+."""

    def test_each_item_is_hashed_once(self) -> None:
        data = tuple(Counted(value) for value in range(100))

        Counted.reset()
        first = hash(data)
        first_calls = Counted.hashes
        Counted.reset()
        second = hash(data)
        second_calls = Counted.hashes

        assert first == second
        assert first_calls == 100
        expected = 0 if sys.version_info >= (3, 14) else 100
        assert second_calls == expected, (
            f"the second hash() called __hash__ {second_calls} times on "
            f"{sys.version_info[:2]}, expected {expected}"
        )

    def test_nested_tuples_hash_the_inner_items(self) -> None:
        nested = tuple(tuple(Counted(10 * row + col) for col in range(10)) for row in range(10))

        Counted.reset()
        hash(nested)

        assert Counted.hashes == 100

    def test_an_unhashable_item_raises(self) -> None:
        with pytest.raises(TypeError, match="unhashable type: 'list'"):
            hash((1, [2, 3]))


class TestFrozensetCombinesStoredHashes:
    """`hash()` of a `frozenset` | O(n) first call, O(1) after; no item is hashed again."""

    def test_no_item_is_hashed(self) -> None:
        tags = frozenset(Counted(value) for value in range(100))

        Counted.reset()
        hash(tags)

        assert Counted.hashes == 0

    def test_order_does_not_change_the_hash(self) -> None:
        assert hash(frozenset(["x", "y", "z"])) == hash(frozenset(["z", "y", "x"]))

    @pytest.mark.timing
    def test_the_first_hash_is_linear(self) -> None:
        times = [
            first_hash_ns(lambda size=size: frozenset(range(size)))
            for size in (10_000, 100_000, 10**6)
        ]

        assert_linear("the first hash() of a frozenset", times)

    @pytest.mark.timing
    def test_a_second_hash_does_not_grow(self) -> None:
        small, large = frozenset(range(1_000)), frozenset(range(10**6))
        hash(small)
        hash(large)

        ratio = best_ns(lambda: hash(large), inner=100) / best_ns(lambda: hash(small), inner=100)

        assert ratio < CONSTANT, f"a kept frozenset hash() cost x{ratio:.2f} on 1,000x the items"


class TestOwnHashRunsEveryTime:
    """`hash()` of an instance with its own `__hash__` | O(h), called on every
    `hash()`, dict lookup and set test."""

    def test_hash_lookup_and_membership_each_call_it(self) -> None:
        key = Counted(7)
        table = {key: "seven"}
        members = {key}

        counts: list[int] = []
        Counted.reset()
        hash(key)
        counts.append(Counted.hashes)
        assert table[key] == "seven"
        counts.append(Counted.hashes)
        assert key in members
        counts.append(Counted.hashes)

        assert counts == [1, 2, 3]

    def test_a_tuple_of_fields_makes_equal_instances_hash_equal(self) -> None:
        class Point:
            def __init__(self, x: int, y: int) -> None:
                self.x, self.y = x, y

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)

            def __hash__(self) -> int:
                return hash((self.x, self.y))

        assert hash(Point(1, 2)) == hash(Point(1, 2))
        assert {Point(1, 2): "a"}[Point(1, 2)] == "a"

    def test_the_default_hash_is_stable_and_calls_nothing(self) -> None:
        plain = object()

        assert hash(plain) == hash(plain)
        assert type(plain).__hash__ is object.__hash__


class TestUnhashableTypesRaise:
    """`hash()` of a `list`, `dict`, `set` or `bytearray` | raises `TypeError`,
    as does a class that defines `__eq__` without `__hash__`."""

    @pytest.mark.parametrize("value", [[1], {1: 2}, {1}, bytearray(b"x")])
    def test_mutable_builtins_raise(self, value: object) -> None:
        with pytest.raises(TypeError, match="unhashable type"):
            hash(value)

    def test_defining_eq_alone_removes_the_hash(self) -> None:
        class EqOnly:
            def __eq__(self, other: object) -> bool:
                return True

        assert EqOnly.__hash__ is None
        with pytest.raises(TypeError, match="unhashable type"):
            hash(EqOnly())


class TestCollisionsCostComparisons:
    """`d[key]`, `key in d` | O(1) avg, O(c) worst; building c keys O(c²) worst.
    `__eq__` runs only when the stored hashes match."""

    @staticmethod
    def comparisons_to_build(count: int, fixed_hash: int | None) -> int:
        keys = [Counted(value, fixed_hash) for value in range(count)]
        Counted.reset()
        built = set(keys)
        assert len(built) == count
        return Counted.comparisons

    def test_distinct_hashes_never_call_eq(self) -> None:
        assert self.comparisons_to_build(2_000, None) == 0

    def test_one_shared_hash_makes_building_quadratic(self) -> None:
        small = self.comparisons_to_build(200, 42)
        large = self.comparisons_to_build(2_000, 42)

        assert small >= 200 * 199 // 2
        assert large >= 2_000 * 1_999 // 2
        assert large / small > 30, f"10x the keys cost x{large / small:.1f} comparisons"

    def test_a_missing_key_is_compared_with_every_colliding_key(self) -> None:
        table = {Counted(value, 42): value for value in range(1_000)}

        Counted.reset()
        assert Counted(-1, 42) not in table

        assert 1_000 <= Counted.comparisons <= 1_100

    @pytest.mark.timing
    def test_ints_that_share_a_hash_make_building_quadratic(self) -> None:
        modulus = sys.hash_info.modulus

        def build_ns(count: int, step: int) -> float:
            keys = [i * step for i in range(1, count + 1)]
            return best_ns(lambda: set(keys), repeats=3)

        colliding = build_ns(10_000, modulus) / build_ns(1_000, modulus)

        assert colliding > 30, f"10x the colliding ints cost x{colliding:.1f}"


class TestSetOperationsReuseStoredHashes:
    """`s1 & s2` on two sets | O(min(len(s1), len(s2))) avg; reuses the stored
    hashes, as do `|`, `-`, `^` and comparisons."""

    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda a, b: a & b, id="and"),
            pytest.param(lambda a, b: a | b, id="or"),
            pytest.param(lambda a, b: a - b, id="sub"),
            pytest.param(lambda a, b: a ^ b, id="xor"),
            pytest.param(lambda a, b: a <= b, id="le"),
            pytest.param(lambda a, b: a.isdisjoint(b), id="isdisjoint"),
            pytest.param(lambda a, b: frozenset(a) & b, id="frozenset"),
            pytest.param(lambda a, b: set(a), id="copy"),
        ],
    )
    def test_no_element_is_hashed_again(self, operation: Callable[[Any, Any], object]) -> None:
        left = {Counted(value) for value in range(100)}
        right = {Counted(value) for value in range(50, 300)}

        Counted.reset()
        operation(left, right)

        assert Counted.hashes == 0

    def test_equality_between_equal_sized_sets_hashes_nothing(self) -> None:
        left = {Counted(value) for value in range(100)}
        right = {Counted(value) for value in range(100)}

        Counted.reset()
        assert left == right

        assert Counted.hashes == 0
        assert Counted.comparisons == 100

    def test_copying_a_dict_hashes_nothing(self) -> None:
        table = {Counted(value): value for value in range(100)}

        Counted.reset()
        assert len(dict(table)) == 100

        assert Counted.hashes == 0

    def test_a_list_operand_is_hashed_item_by_item(self) -> None:
        left = {Counted(value) for value in range(100)}
        right = [Counted(value) for value in range(50, 300)]

        Counted.reset()
        assert len(left.intersection(right)) == 50

        assert Counted.hashes == 250

    @pytest.mark.timing
    @pytest.mark.parametrize("small_first", [True, False], ids=["small_and_big", "big_and_small"])
    def test_intersection_follows_the_smaller_set(self, small_first: bool) -> None:
        small = set(range(100))
        medium, huge = set(range(10_000)), set(range(10**6))

        def intersect_ns(big: set[int]) -> float:
            if small_first:
                return best_ns(lambda: small & big, inner=20)
            return best_ns(lambda: big & small, inner=20)

        ratio = intersect_ns(huge) / intersect_ns(medium)

        assert ratio < CONSTANT, f"the intersection cost x{ratio:.2f} as the big set grew 100x"


class TestHashSeed:
    """`str` and `bytes` hashes vary between processes unless `PYTHONHASHSEED`
    is set to a number; `int` hashes do not."""

    @staticmethod
    def hashes_with_seed(seed: str) -> list[str]:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "print(hash('key'), hash(b'key'), hash(10**30))",
            ],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return result.stdout.split()

    def test_only_str_and_bytes_follow_the_seed(self) -> None:
        one, two = self.hashes_with_seed("1"), self.hashes_with_seed("2")

        assert one[0] != two[0], "the str hash ignored PYTHONHASHSEED"
        assert one[1] != two[1], "the bytes hash ignored PYTHONHASHSEED"
        assert one[2] == two[2], "the int hash followed PYTHONHASHSEED"


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
        line, source = next((n, s) for n, s in _blocks() if "assert Counted.hashes == 250" in s)
        mutated = source.replace("assert Counted.hashes == 250", "assert Counted.hashes == 0", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
