"""Tests for docs/builtins/frozendict.md.

`frozendict` is new in Python 3.15, so the whole module skips on earlier
versions. The page prices it as the same hash table as `dict` with the mutating
operations taken away; the rows that differ from `dict` are the ones that hand
back an existing object, the cached hash and `|=`. Those are settled by
identity and by counting calls, which need no tolerance. The lookup rows are
held flat by a timing test over a hundredfold size step.

Measurement scope:

* `frozendict(fd)` and `fd.copy()` are asserted to return `fd` itself for an
  exact frozendict; an instance of a subclass is asserted to come back as a
  new, equal object, which is the O(n) copy.
* `hash(fd)` is a counting `__hash__` on 200 values and 200 keys, counted
  separately: the first call hashes the values 200 times and no key (the keys' hashes are stored), and a
  second call hashes nothing. A list value is asserted to build and to raise
  `TypeError` only at `hash()`. Two frozendicts with the same items in
  opposite orders are asserted equal with equal hashes.
* Equality is a counting `__eq__` on the values: 200 comparisons between
  frozendicts of 200 equal items, none when the lengths differ. A frozendict
  is asserted equal to a `dict` with the same items.
* Colliding keys (one shared hash) are a counting `__eq__`: looking up a
  missing key in a frozendict of 300 of them compares it with all 300, which
  is the O(n) worst case.
* `fd | other` is asserted to give a frozendict, `dict | fd` a dict, and a
  list operand `TypeError`. `fd |= other` is asserted to rebind the name to a
  new object and leave the original unchanged. That k such steps cost O(k^2)
  is settled by observation and allocation: every step returns a new object
  holding every item so far, and one `|=` adding a single item to 100,000
  items allocates more than 20x what it does on 1,000.
* Building from a dict of 200,000 int keys with all but 10 deleted is timed
  against building from a fresh dict of the same 10 and must cost more than
  50x (locally thousands).
* `fromkeys` is asserted to give a frozendict whose values are one object.
* `fd[key]`, `key in fd`, `fd.get()` and `len(fd)` are timed on frozendicts
  of 1,000 and 100,000 int keys and must stay under 5x apart.
* The views are asserted to wrap an equal mapping (`.mapping`) and, by a
  `tracemalloc` peak under 10 KB for all three over 100,000 items, not to
  copy it, and `reversed()` to give reverse insertion order. Assignment and
  deletion are asserted to raise `TypeError`, and `update`, `pop`,
  `setdefault`, `clear` and `popitem` to be absent.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That construction, `dict(fd)`, iteration and equality are linear rather
  than worse is read from Objects/dictobject.c (one insertion or one
  comparison per item), not timed.
* Key hashing and comparison are treated as O(1); a costly `__hash__` or
  `__eq__` is outside the bounds.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

if sys.version_info < (3, 15):
    pytest.skip("version: frozendict is new in Python 3.15", allow_module_level=True)

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "frozendict.md"
EXPECTED_BLOCKS = 4

frozendict: Any = __import__("builtins").frozendict


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1000) -> float:
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
    """A hashable value that counts its `__hash__` and `__eq__` calls."""

    hashes = 0
    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        type(self).hashes += 1
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, Counted) and self.value == other.value


class Colliding:
    """A key whose hash collides with every other instance."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return 7

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, Colliding) and self.value == other.value


class TestConstruction:
    def test_from_a_mapping_an_iterable_and_keywords(self) -> None:
        assert frozendict({"a": 1}, b=2) == {"a": 1, "b": 2}
        assert frozendict([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}
        assert frozendict() == {}

    def test_a_repeated_key_keeps_the_last_value(self) -> None:
        assert frozendict([("a", 1), ("a", 2)]) == {"a": 2}

    def test_an_exact_frozendict_is_returned_as_is(self) -> None:
        fd = frozendict(a=1)
        assert frozendict(fd) is fd
        assert fd.copy() is fd

    def test_a_subclass_instance_is_copied(self) -> None:
        class Sub(frozendict):  # type: ignore[misc, valid-type]
            pass

        sub = Sub(a=1)
        copied = sub.copy()
        assert copied is not sub and copied == sub
        assert frozendict(sub) is not sub

    def test_fromkeys_shares_one_value_object(self) -> None:
        marker = object()
        fd = frozendict.fromkeys(["x", "y"], marker)
        assert type(fd) is frozendict
        assert fd["x"] is marker and fd["y"] is marker
        assert frozendict.fromkeys("ab") == {"a": None, "b": None}

    def test_dict_of_it_is_an_independent_dict(self) -> None:
        fd = frozendict(a=1)
        mutable = dict(fd)
        mutable["b"] = 2
        assert type(mutable) is dict and fd == {"a": 1}


@pytest.mark.timing
def test_a_sparse_dict_source_costs_its_former_size() -> None:
    sparse = {i: i for i in range(200_000)}
    for i in range(10, 200_000):
        del sparse[i]
    fresh = {i: i for i in range(10)}
    sparse_ns = best_ns(lambda: frozendict(sparse), inner=3)
    fresh_ns = best_ns(lambda: frozendict(fresh), inner=3)
    assert sparse_ns > fresh_ns * 50, f"{fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"
    assert frozendict(sparse) == fresh


class TestHash:
    def test_values_are_hashed_once_and_keys_not_at_all(self) -> None:
        class Key(Counted):
            hashes = 0

        class Value(Counted):
            hashes = 0

        fd = frozendict({Key(i): Value(-i) for i in range(200)})
        Key.hashes = Value.hashes = 0
        first = hash(fd)
        assert Key.hashes == 0, "the keys' hashes are stored, not recomputed"
        assert Value.hashes == 200, "the first hash() hashes each value"
        Value.hashes = 0
        assert hash(fd) == first
        assert Key.hashes == 0 and Value.hashes == 0, "a second hash() reads the cached value"

    def test_an_unhashable_value_fails_at_hash_time(self) -> None:
        fd = frozendict(tags=["a"])
        with pytest.raises(TypeError, match="unhashable"):
            hash(fd)

    def test_order_does_not_change_the_hash(self) -> None:
        a = frozendict((i, i) for i in range(100))
        b = frozendict((i, i) for i in reversed(range(100)))
        assert list(a) != list(b)
        assert a == b and hash(a) == hash(b)


class TestEquality:
    def test_equal_lengths_compare_every_value(self) -> None:
        left = frozendict((i, Counted(i)) for i in range(200))
        right = frozendict((i, Counted(i)) for i in range(200))
        Counted.comparisons = 0
        assert left == right
        assert Counted.comparisons == 200

    def test_different_lengths_compare_nothing(self) -> None:
        left = frozendict((i, Counted(i)) for i in range(200))
        right = frozendict((i, Counted(i)) for i in range(199))
        Counted.comparisons = 0
        assert left != right
        assert Counted.comparisons == 0

    def test_equal_to_a_dict_with_the_same_items(self) -> None:
        assert frozendict(x=1, y=2) == {"y": 2, "x": 1}

    def test_colliding_keys_make_a_lookup_linear(self) -> None:
        fd = frozendict((Colliding(i), i) for i in range(300))
        Colliding.comparisons = 0
        assert Colliding(-1) not in fd
        assert Colliding.comparisons == 300


class TestMerge:
    def test_result_types(self) -> None:
        fd = frozendict(a=1)
        assert type(fd | {"b": 2}) is frozendict
        assert type({"b": 2} | fd) is dict
        with pytest.raises(TypeError):
            _ = fd | [("b", 2)]

    def test_in_place_merge_rebinds(self) -> None:
        original = frozendict(a=1)
        current = original
        current |= {"b": 2}
        assert current is not original
        assert original == {"a": 1} and current == {"a": 1, "b": 2}

    def test_each_merge_step_rebuilds_everything_so_far(self) -> None:
        current = frozendict()
        seen: list[Any] = []
        for i in range(50):
            previous = current
            current |= {i: i}
            assert current is not previous
            assert len(current) == i + 1, "step i builds an object holding i + 1 items"
            seen.append(current)
        assert len({id(item) for item in seen}) == 50

    def test_each_merge_step_allocates_the_whole_result(self) -> None:
        def allocated(size: int) -> int:
            current = frozendict((i, i) for i in range(size))
            tracemalloc.start()
            try:
                current |= {-1: -1}
                return tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()

        small, large = allocated(1_000), allocated(100_000)
        assert large > small * 20, f"{small} bytes vs {large} bytes for one added item"


class TestReadOnly:
    def test_assignment_and_deletion_raise(self) -> None:
        fd = frozendict(a=1)
        with pytest.raises(TypeError):
            fd["a"] = 2  # type: ignore[index]
        with pytest.raises(TypeError):
            del fd["a"]  # type: ignore[attr-defined]

    @pytest.mark.parametrize("name", ["update", "pop", "setdefault", "clear", "popitem"])
    def test_no_mutating_methods(self, name: str) -> None:
        assert not hasattr(frozendict, name)

    def test_views_are_views(self) -> None:
        fd = frozendict(a=1, b=2)
        for view in (fd.keys(), fd.values(), fd.items()):
            assert view.mapping == fd  # type: ignore[attr-defined]
        large = frozendict((i, i) for i in range(100_000))
        tracemalloc.start()
        try:
            views = (large.keys(), large.values(), large.items())
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert peak < 10_000, f"three views of 100,000 items allocated {peak} bytes"
        assert all(len(view) == 100_000 for view in views)
        assert list(reversed(fd)) == ["b", "a"]
        assert fd.get("missing", 0) == 0
        with pytest.raises(KeyError):
            fd["missing"]


@pytest.mark.timing
@pytest.mark.parametrize("operation", ["getitem", "contains", "get", "len"])
def test_lookups_do_not_grow_with_size(operation: str) -> None:
    def op(fd: Any, key: int) -> Callable[[], Any]:
        return {
            "getitem": lambda: fd[key],
            "contains": lambda: key in fd,
            "get": lambda: fd.get(key),
            "len": lambda: len(fd),
        }[operation]

    small = frozendict((i, i) for i in range(1_000))
    large = frozendict((i, i) for i in range(100_000))
    small_ns = best_ns(op(small, 999))
    large_ns = best_ns(op(large, 99_999))
    assert large_ns < small_ns * 5, f"{operation}: {small_ns:.0f}ns vs {large_ns:.0f}ns"


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
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks():
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert calls == 1" in s)
        mutated = source.replace("assert calls == 1", "assert calls == 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
