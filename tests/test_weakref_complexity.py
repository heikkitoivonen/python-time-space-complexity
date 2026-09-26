"""Tests for docs/stdlib/weakref.md.

The page prices every weak reference, proxy, container entry and finalizer at
O(1) to make and O(w) in aggregate when the referent dies or is counted, where
w is the weak references to one referent. Sharing, per-entry references and the
order things die in are settled by identity checks, `getweakrefcount()` and
call counters, which need no tolerance. The O(w) walks and the container bounds
that are not visible to observation are settled by timing ratios chosen far
from both the claimed and the excluded shape; the iteration snapshot is settled
by traced allocation. Every test that depends on an object dying calls
`gc.collect()` itself, except the ones about whether a cycle waits for it, which
turn the collector off and say so.

Measurement scope:

* `ref(obj)` without a callback is the same object on every call, and with a
  callback a new one each call, each adding one to `getweakrefcount()`. A
  plain `ref()` costs under 3x as much with 100,000 callback references on the
  object as with 10. `int`, `str`, `tuple`, `list` and `object()` instances
  raise `TypeError`. `r()` is the referent, then `None` after the referent is
  collected; `__callback__` is the callback or `None`; `weakref.ref` is
  `weakref.ReferenceType`.
* `hash(r)` is asserted equal to the referent's hash with the referent's
  `__hash__` called once over three `hash(r)` calls; a reference whose referent
  died unhashed raises `TypeError`, and one hashed first keeps its hash. `==`
  calls the referents' `__eq__` while both live and is identity once one has
  been collected.
* `proxy(obj)` is shared the same way; attribute access, a call and `len()`
  are forwarded; a callable referent gets `CallableProxyType`; both proxy
  types are in `ProxyTypes`; a collected referent raises `ReferenceError`.
* `getweakrefcount()` over 100,000 references costs more than 50x what it
  does over 100 (linear predicts 1,000x, a stored count 1x). `getweakrefs()`
  returns a new list of every reference and proxy.
* A referent with 1,000 callback references calls each callback exactly once
  when collected, so dying is at least O(w); 10x the references costs under
  30x the time, from 10,000 to 100,000, which excludes a quadratic.
* With the collector disabled, an object outside a cycle is freed by `del`,
  an object in a cycle survives it and dies at `gc.collect()`, and a parent
  whose child holds a weak back-reference is freed by `del`.
* Each `WeakKeyDictionary`, `WeakValueDictionary`, `WeakSet`, `finalize` and
  `WeakMethod` that names an object adds one to `getweakrefcount()` on it;
  assigning the same key or value again adds nothing.
* `WeakKeyDictionary` and `WeakValueDictionary` lookups and `len()`, and
  `WeakSet` membership, cost under 3x as much at 100,000 entries as at 100.
  Entries vanish after their object is collected. A `WeakKeyDictionary` value
  that refers to its key keeps the key alive through `gc.collect()` until the
  dictionary itself is deleted; a `WeakValueDictionary` key survives
  `gc.collect()` with no other reference to it.
* `copy()` shares keys and values; `deepcopy()` copies the values of a
  `WeakKeyDictionary` and the keys of a `WeakValueDictionary` and shares the
  other side. `|` returns a new dictionary with both operands' entries.
  `keyrefs()` and `valuerefs()` return one live reference per entry.
* Iteration: on 3.14+ the traced peak of taking the first item from each
  container of 100,000 entries exceeds 1 MB; before 3.14 it stays under
  20 KB. Adding or removing an entry inside the loop raises `RuntimeError`
  before 3.14; from 3.14 it does not, and the loop visits the five entries it
  started with, for all three containers. An entry whose object is collected
  mid-loop is skipped without an error on every version.
* `WeakSet`: `s & other` with `other` at 100 items costs under 3x as much for
  `s` at 100,000 as at 100; `s | other` and `s &= other` cost more than 30x
  as much over the same step in `s`; `s.issubset(other)` with `s` at 10 costs
  more than 30x as much for `other` at 100,000 as at 100, with the members of
  `s` last in `other`; placed first, 3.12+ stops walking once all are found.
* `WeakMethod` returns an equal but new bound method per call, `None` once the
  instance is collected, and calls its callback once; a plain `ref` to a
  bound method is dead after `gc.collect()`.
* `finalize` runs once whether triggered by death or a call, returns `None`
  after that, and runs on death with no reference kept to it; one whose
  function is a bound method of its object keeps the object alive through
  `gc.collect()` until it is called. `peek()` and `detach()` return the
  documented tuple, and at interpreter exit the live ones with `atexit` set
  run newest first, in a subprocess.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That the O(1) rows stay O(1) with any number of entries other than the
  sizes timed, and the O(n) space of `copy()`, `keyrefs()` and `valuerefs()`
  beyond their length, follow from Lib/weakref.py and Lib/_weakrefset.py
  wrapping one dict or set with one reference per entry.
* Only `iter()` is measured for the iteration snapshot; `keys()`,
  `values()`, `items()` and `itervaluerefs()` copy the same dictionary in
  Lib/weakref.py.
* The O(w) space of dying is the tuple Objects/weakrefobject.c's
  `PyObject_ClearWeakRefs` builds of the callback references; only the time
  is measured. That an entry's removal on its object's death is O(1) is read
  from the removal callbacks in Lib/weakref.py and Lib/_weakrefset.py.
* The constructors, `update()`, `|=` and `|` of all three containers, and
  `-=`, `^=`, `s - other`, `s ^ other`, the comparison operators other than
  `issubset()`, and `isdisjoint()` are read from Lib/weakref.py,
  Lib/_weakrefset.py and Objects/setobject.c and asserted only by result,
  not timed. `issubset()` is varied in m only, and `&`, `|` and `&=` in n
  only.
* When CPython frees an object is interpreter behaviour, not the module's:
  the tests pin it on the interpreter they run on.
* `weakref.KeyedRef`, the reference type a `WeakValueDictionary` stores, is
  not in the documented API and is not priced on the page.
* Key and element hashing and `==` are O(1) in the cost model; callback and
  finalizer function costs are not varied.
"""

from __future__ import annotations

import copy
import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import weakref
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "weakref.md"
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


def best_ns_with_setup(
    setup: Callable[[], Any], func: Callable[[Any], Any], repeats: int = 7
) -> float:
    """Fastest of `repeats` runs of func(setup()), timing only func."""
    best: float | None = None
    for _ in range(repeats):
        subject = setup()
        start = time.perf_counter_ns()
        func(subject)
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return float(best)


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def ignore(reference: object) -> None:
    """A callback that does nothing."""


def anything(*args: object, **kwargs: object) -> None:
    """A finalizer function that takes any arguments and does nothing."""


class Node:
    """A weakly referenceable object with identity equality."""


class Value:
    """Equal by value, counting its `__hash__` and `__eq__` calls."""

    hashes = 0
    compares = 0

    def __init__(self, key: int) -> None:
        self.key = key

    def __hash__(self) -> int:
        Value.hashes += 1
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        Value.compares += 1
        return isinstance(other, Value) and other.key == self.key


@pytest.fixture
def collector_off() -> Iterator[None]:
    """Disable the cycle collector for the test and restore it afterwards."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


class TestPlainReferencesAreShared:
    """`ref(obj, callback=None)` | O(1) | O(1): without a callback, the
    existing plain reference; with one, a new reference every call."""

    def test_a_plain_reference_is_reused(self) -> None:
        node = Node()
        first = weakref.ref(node)

        assert weakref.ref(node) is first
        assert weakref.getweakrefcount(node) == 1

    def test_a_callback_reference_is_new_every_call(self) -> None:
        node = Node()
        plain = weakref.ref(node)

        first = weakref.ref(node, ignore)
        second = weakref.ref(node, ignore)

        assert first is not second
        assert first is not plain
        assert weakref.getweakrefcount(node) == 3

    @pytest.mark.timing
    def test_making_one_does_not_depend_on_how_many_there_are(self) -> None:
        few = Node()
        many = Node()
        few_refs = [weakref.ref(few, ignore) for _ in range(10)]
        many_refs = [weakref.ref(many, ignore) for _ in range(100_000)]

        few_ns = best_ns(lambda: (weakref.ref(few), weakref.ref(few, ignore)), inner=1_000)
        many_ns = best_ns(lambda: (weakref.ref(many), weakref.ref(many, ignore)), inner=1_000)

        assert len(few_refs) == 10 and len(many_refs) == 100_000
        ratio = many_ns / few_ns
        assert ratio < 3, (
            f"ref() cost x{ratio:.2f} with 100,000 references against 10 "
            f"({few_ns:.0f}ns to {many_ns:.0f}ns); the row claims O(1)"
        )

    @pytest.mark.parametrize("value", [42, "text", (1, 2), [1, 2], object()])
    def test_some_types_cannot_be_referenced(self, value: object) -> None:
        with pytest.raises(TypeError, match="cannot create weak reference"):
            weakref.ref(value)

    def test_calling_it_returns_the_referent_until_it_is_collected(self) -> None:
        node = Node()
        reference = weakref.ref(node)

        assert reference() is node

        del node
        gc.collect()

        assert reference() is None

    def test_the_callback_attribute(self) -> None:
        node = Node()

        assert weakref.ref(node).__callback__ is None
        assert weakref.ref(node, ignore).__callback__ is ignore

    def test_ref_is_reference_type(self) -> None:
        assert weakref.ref is weakref.ReferenceType


class TestHashingAndEquality:
    """`hash(r)` caches the referent's hash; `r1 == r2` compares referents
    while both live, and identity once either is dead."""

    def test_the_referent_is_hashed_once(self) -> None:
        value = Value(7)
        reference = weakref.ref(value)
        Value.hashes = 0

        hashes = {hash(reference) for _ in range(3)}

        assert hashes == {hash(7)}
        assert Value.hashes == 1

    def test_a_reference_never_hashed_cannot_be_after_death(self) -> None:
        value = Value(7)
        reference = weakref.ref(value)

        del value
        gc.collect()

        with pytest.raises(TypeError, match="weak object has gone away"):
            hash(reference)

    def test_a_reference_hashed_before_death_keeps_its_hash(self) -> None:
        value = Value(7)
        reference = weakref.ref(value)
        before = hash(reference)

        del value
        gc.collect()

        assert hash(reference) == before

    def test_equality_follows_the_referents_then_identity(self) -> None:
        left, right = Value(1), Value(1)
        left_ref, right_ref = weakref.ref(left), weakref.ref(right)
        Value.compares = 0

        assert left_ref == right_ref
        assert Value.compares == 1

        del left
        gc.collect()

        assert left_ref != right_ref
        assert left_ref == left_ref
        assert Value.compares == 1


class Account:
    def __init__(self) -> None:
        self.balance = 10

    def deposit(self, amount: int) -> int:
        self.balance += amount
        return self.balance

    def __len__(self) -> int:
        return self.balance


class TestProxies:
    """`proxy(obj)` is shared like `ref`, forwards each operation, and raises
    `ReferenceError` once the referent is collected."""

    def test_a_plain_proxy_is_reused_and_a_callback_one_is_not(self) -> None:
        account = Account()

        assert weakref.proxy(account) is weakref.proxy(account)
        assert weakref.proxy(account, ignore) is not weakref.proxy(account, ignore)

    def test_operations_are_forwarded(self) -> None:
        account = Account()
        view: Any = weakref.proxy(account)

        assert view.deposit(5) == 15
        assert account.balance == 15
        assert len(view) == 15

    def test_the_proxy_types(self) -> None:
        plain = weakref.proxy(Account())
        callable_view = weakref.proxy(ignore)

        assert type(plain) is weakref.ProxyType
        assert type(callable_view) is weakref.CallableProxyType
        assert weakref.ProxyTypes == (weakref.ProxyType, weakref.CallableProxyType)

    def test_a_dead_proxy_raises(self) -> None:
        account = Account()
        view: Any = weakref.proxy(account)

        del account
        gc.collect()

        with pytest.raises(ReferenceError, match="no longer exists"):
            view.balance  # noqa: B018


class TestCountingWalksEveryReference:
    """`getweakrefcount(obj)` | O(w) | O(1) and `getweakrefs(obj)` | O(w) | O(w)."""

    @pytest.mark.timing
    def test_counting_grows_with_the_references(self) -> None:
        few = Node()
        many = Node()
        few_refs = [weakref.ref(few, ignore) for _ in range(100)]
        many_refs = [weakref.ref(many, ignore) for _ in range(100_000)]

        few_ns = best_ns(lambda: weakref.getweakrefcount(few), inner=100)
        many_ns = best_ns(lambda: weakref.getweakrefcount(many), inner=10)

        assert weakref.getweakrefcount(few) == len(few_refs)
        assert weakref.getweakrefcount(many) == len(many_refs)
        ratio = many_ns / few_ns
        assert ratio > 50, (
            f"1,000x the references cost only x{ratio:.1f} to count "
            f"({few_ns:.0f}ns to {many_ns:.0f}ns); a walk predicts x1000, a stored count x1"
        )

    def test_listing_returns_a_new_list_of_every_reference(self) -> None:
        node = Account()
        plain = weakref.ref(node)
        view = weakref.proxy(node)
        callbacks = [weakref.ref(node, ignore) for _ in range(3)]

        first = weakref.getweakrefs(node)
        second = weakref.getweakrefs(node)

        assert first is not second
        assert len(first) == 5
        assert {id(item) for item in first} == {id(plain), id(view), *map(id, callbacks)}

    def test_objects_without_weak_reference_support_count_zero(self) -> None:
        assert weakref.getweakrefcount(42) == 0
        assert weakref.getweakrefs(42) == []


class TestDyingClearsEveryReference:
    """The referent dying | O(w) | O(w): every reference cleared, each
    callback called once."""

    def test_every_callback_runs_once(self) -> None:
        node = Node()
        calls: list[weakref.ref[Node]] = []
        references = [weakref.ref(node, calls.append) for _ in range(1_000)]

        del node
        gc.collect()

        assert len(calls) == 1_000
        assert {id(call) for call in calls} == {id(reference) for reference in references}
        assert all(reference() is None for reference in references)

    @pytest.mark.timing
    def test_dying_is_linear_in_the_references(self) -> None:
        def die(count: int) -> float:
            def setup() -> tuple[list[Node], list[weakref.ref[Node]]]:
                node = Node()
                return [node], [weakref.ref(node, ignore) for _ in range(count)]

            return best_ns_with_setup(setup, lambda subject: subject[0].clear(), repeats=5)

        small = die(10_000)
        large = die(100_000)

        ratio = large / small
        assert 3 < ratio < 30, (
            f"10x the references cost x{ratio:.1f} to die ({small:.0f}ns to {large:.0f}ns); "
            "linear predicts x10, quadratic x100"
        )


class TestWhenObjectsDie:
    """CPython frees an object outside a cycle at once, and one inside a cycle
    at the next collection; a weak back-reference leaves no cycle."""

    def test_an_acyclic_object_dies_at_del(self, collector_off: None) -> None:
        node = Node()
        reference = weakref.ref(node)

        del node

        assert reference() is None

    def test_a_cyclic_object_waits_for_the_collector(self, collector_off: None) -> None:
        node: Any = Node()
        node.me = node
        reference = weakref.ref(node)

        del node
        assert reference() is not None

        gc.collect()
        assert reference() is None

    def test_a_weak_back_reference_leaves_no_cycle(self, collector_off: None) -> None:
        parent: Any = Node()
        child: Any = Node()
        parent.children = [child]
        child.parent = weakref.ref(parent)
        witness = weakref.ref(parent)

        del parent

        assert witness() is None
        assert child.parent() is None

    def test_a_strong_back_reference_is_a_cycle(self, collector_off: None) -> None:
        parent: Any = Node()
        child: Any = Node()
        parent.children = [child]
        child.parent = parent
        witness = weakref.ref(parent)

        del parent, child
        assert witness() is not None

        gc.collect()
        assert witness() is None


class TestEveryHolderAddsOneReference:
    """`w` counts one reference per container entry, finalizer and
    `WeakMethod` naming the object."""

    def test_each_container_adds_one(self) -> None:
        node = Node()

        keys = weakref.WeakKeyDictionary({node: 1})
        other_keys = weakref.WeakKeyDictionary({node: 2})
        values = weakref.WeakValueDictionary({"a": node})
        members = weakref.WeakSet([node])

        assert weakref.getweakrefcount(node) == 4
        assert len(keys) == len(other_keys) == len(values) == len(members) == 1

    def test_assigning_again_adds_nothing(self) -> None:
        node = Node()
        keys: weakref.WeakKeyDictionary[Node, int] = weakref.WeakKeyDictionary()
        values: weakref.WeakValueDictionary[str, Node] = weakref.WeakValueDictionary()

        for number in range(5):
            keys[node] = number
            values["a"] = node
            gc.collect()

        assert weakref.getweakrefcount(node) == 2

    def test_finalize_and_weakmethod_add_one_each(self) -> None:
        account = Account()

        finalizer = weakref.finalize(account, ignore, None)
        method = weakref.WeakMethod(account.deposit)

        assert weakref.getweakrefcount(account) == 2
        finalizer.detach()
        assert method() is not None


class TestWeakKeyDictionary:
    """`WeakKeyDictionary`: O(1) lookups and `len()`, entries that go with
    their keys, and values held strongly."""

    @pytest.mark.timing
    def test_lookups_do_not_grow_with_the_entries(self) -> None:
        small_keys = [Node() for _ in range(100)]
        large_keys = [Node() for _ in range(100_000)]
        small = weakref.WeakKeyDictionary((key, 1) for key in small_keys)
        large = weakref.WeakKeyDictionary((key, 1) for key in large_keys)
        small_probe, large_probe = small_keys[50], large_keys[50_000]

        def probe(table: weakref.WeakKeyDictionary[Node, int], key: Node) -> None:
            _ = table[key], table.get(key), key in table, len(table)

        small_ns = best_ns(lambda: probe(small, small_probe), inner=1_000)
        large_ns = best_ns(lambda: probe(large, large_probe), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"1,000x the entries cost x{ratio:.2f} per lookup ({small_ns:.0f}ns to "
            f"{large_ns:.0f}ns); the rows claim O(1)"
        )

    def test_an_entry_goes_with_its_key(self) -> None:
        keep, drop = Node(), Node()
        table = weakref.WeakKeyDictionary({keep: 1, drop: 2})

        del drop
        gc.collect()

        assert len(table) == 1
        assert list(table.items()) == [(keep, 1)]

    def test_a_value_that_refers_to_its_key_keeps_it_alive(self) -> None:
        table: weakref.WeakKeyDictionary[Node, list[Node]] = weakref.WeakKeyDictionary()
        pinned = Node()
        witness = weakref.ref(pinned)
        table[pinned] = [pinned]

        del pinned
        gc.collect()

        assert witness() is not None
        assert len(table) == 1

        del table
        gc.collect()

        assert witness() is None

    def test_the_mapping_methods(self) -> None:
        a, b, c = Node(), Node(), Node()
        table = weakref.WeakKeyDictionary({a: 1})

        assert table.setdefault(b, 2) == 2
        assert table.setdefault(b, 3) == 2
        assert table.pop(a) == 1
        assert table.pop(a, None) is None
        table[c] = 3
        del table[c]
        assert table.popitem() == (b, 2)
        assert len(table) == 0

    def test_copies(self) -> None:
        key = Node()
        value = [1, 2]
        table = weakref.WeakKeyDictionary({key: value})

        shallow = table.copy()
        also_shallow = copy.copy(table)
        deep = copy.deepcopy(table)

        assert shallow is not table and also_shallow is not table
        assert shallow[key] is value and also_shallow[key] is value
        assert list(deep.keys()) == [key]
        assert deep[key] == value and deep[key] is not value

    def test_keyrefs_and_union(self) -> None:
        a, b = Node(), Node()
        table = weakref.WeakKeyDictionary({a: 1})

        refs = table.keyrefs()
        merged = table | {b: 2}
        table |= {b: 3}

        assert [reference() for reference in refs] == [a]
        assert merged is not table and dict(merged.items()) == {a: 1, b: 2}
        assert dict(table.items()) == {a: 1, b: 3}


class TestWeakValueDictionary:
    """`WeakValueDictionary`: O(1) lookups and `len()`, and entries that go
    with their values."""

    @pytest.mark.timing
    def test_lookups_do_not_grow_with_the_entries(self) -> None:
        small_values = [Node() for _ in range(100)]
        large_values = [Node() for _ in range(100_000)]
        small = weakref.WeakValueDictionary(enumerate(small_values))
        large = weakref.WeakValueDictionary(enumerate(large_values))

        def probe(table: weakref.WeakValueDictionary[int, Node], key: int) -> None:
            _ = table[key], table.get(key), key in table, len(table)

        small_ns = best_ns(lambda: probe(small, 50), inner=1_000)
        large_ns = best_ns(lambda: probe(large, 50_000), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"1,000x the entries cost x{ratio:.2f} per lookup ({small_ns:.0f}ns to "
            f"{large_ns:.0f}ns); the rows claim O(1)"
        )

    def test_an_entry_goes_with_its_value(self) -> None:
        keep, drop = Node(), Node()
        table = weakref.WeakValueDictionary({"keep": keep, "drop": drop})

        del drop
        gc.collect()

        assert "drop" not in table
        assert table.get("drop") is None
        assert len(table) == 1

    def test_the_key_is_held_strongly(self) -> None:
        value = Node()
        key = Node()
        witness = weakref.ref(key)
        table: weakref.WeakValueDictionary[Node, Node] = weakref.WeakValueDictionary()
        table[key] = value

        del key
        gc.collect()

        assert witness() is not None
        assert list(table.values()) == [value]

    def test_the_mapping_methods(self) -> None:
        a, b, c = Node(), Node(), Node()
        table = weakref.WeakValueDictionary({"a": a})

        assert table.setdefault("b", b) is b
        assert table.setdefault("b", c) is b
        assert table.pop("a") is a
        assert table.pop("a", None) is None
        table["c"] = c
        del table["c"]
        assert table.popitem() == ("b", b)
        assert len(table) == 0

    def test_copies(self) -> None:
        key = Value(3)
        value = Node()
        table = weakref.WeakValueDictionary({key: value})

        shallow = table.copy()
        deep = copy.deepcopy(table)

        assert next(iter(shallow.keys())) is key and shallow[key] is value
        deep_key = next(iter(deep.keys()))
        assert deep_key == key and deep_key is not key
        assert deep[deep_key] is value

    def test_valuerefs_itervaluerefs_and_union(self) -> None:
        a, b = Node(), Node()
        table = weakref.WeakValueDictionary({"a": a})

        assert [reference() for reference in table.valuerefs()] == [a]
        assert [reference() for reference in table.itervaluerefs()] == [a]
        merged = table | {"b": b}
        table |= {"b": b}
        assert merged is not table
        assert dict(merged.items()) == dict(table.items()) == {"a": a, "b": b}


def _containers(objects: list[Node]) -> dict[str, Any]:
    return {
        "WeakKeyDictionary": weakref.WeakKeyDictionary((item, 1) for item in objects),
        "WeakValueDictionary": weakref.WeakValueDictionary(enumerate(objects)),
        "WeakSet": weakref.WeakSet(objects),
    }


def _add_one(container: Any, item: Node) -> None:
    if isinstance(container, weakref.WeakValueDictionary):
        container[-1] = item
    elif isinstance(container, weakref.WeakSet):
        container.add(item)
    else:
        container[item] = 1


def _remove_last(container: Any, objects: list[Node]) -> None:
    if isinstance(container, weakref.WeakValueDictionary):
        container.pop(len(objects) - 1, None)
    elif isinstance(container, weakref.WeakSet):
        container.discard(objects[-1])
    else:
        container.pop(objects[-1], None)


class TestIteration:
    """Iterating a weak container: O(n) time; O(n) space on 3.14+, which
    copies the underlying container first, and O(1) before."""

    SIZE = 100_000

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the snapshot starts in 3.14")
    def test_the_first_item_copies_the_container(self) -> None:
        objects = [Node() for _ in range(self.SIZE)]
        for name, container in _containers(objects).items():
            iterator = iter(container)

            peak = peak_bytes(lambda it=iterator: next(it))  # type: ignore[misc]

            assert peak > 1_000_000, f"{name}: the first of {self.SIZE} items peaked at {peak}"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="3.14+ copies the container")
    def test_the_first_item_copies_nothing(self) -> None:
        objects = [Node() for _ in range(self.SIZE)]
        for name, container in _containers(objects).items():
            iterator = iter(container)

            peak = peak_bytes(lambda it=iterator: next(it))  # type: ignore[misc]

            assert peak < 20_000, f"{name}: the first of {self.SIZE} items peaked at {peak}"

    def test_adding_inside_the_loop(self) -> None:
        objects = [Node() for _ in range(5)]
        extra = Node()
        for name, container in _containers(objects).items():
            visited = 0
            try:
                for _ in container:
                    visited += 1
                    _add_one(container, extra)
            except RuntimeError as error:
                assert sys.version_info < (3, 14), f"{name} raised {error} on 3.14+"
                assert "changed size during iteration" in str(error)
            else:
                assert sys.version_info >= (3, 14), f"{name} allowed an addition before 3.14"
                assert visited == 5, f"{name} visited {visited} of the 5 it started with"
            assert len(container) == 6

    def test_removing_inside_the_loop(self) -> None:
        objects = [Node() for _ in range(5)]
        for name, container in _containers(objects).items():
            visited = 0
            try:
                for _ in container:
                    visited += 1
                    _remove_last(container, objects)
            except RuntimeError as error:
                assert sys.version_info < (3, 14), f"{name} raised {error} on 3.14+"
                assert "changed size during iteration" in str(error)
            else:
                assert sys.version_info >= (3, 14), f"{name} allowed a removal before 3.14"
                assert visited == 5, f"{name} visited {visited} of the 5 it started with"
            assert len(container) == 4

    def test_an_object_dying_mid_loop_is_skipped(self) -> None:
        for name in ("WeakKeyDictionary", "WeakValueDictionary", "WeakSet"):
            objects = [Node() for _ in range(5)]
            container = _containers(objects)[name]
            iterator = iter(container)
            first = next(iterator)

            objects.clear()
            gc.collect()
            rest = list(iterator)

            assert rest == [], f"{name} visited {len(rest)} items after they were collected"
            del first
            gc.collect()
            assert len(container) == 0, f"{name} kept {len(container)} dead entries"


class TestWeakSet:
    """`WeakSet`: O(1) membership; `&` walks only `other`; `|`, `&=` and the
    comparisons are O(n + m)."""

    @staticmethod
    def _set(size: int) -> tuple[list[Node], weakref.WeakSet[Node]]:
        members = [Node() for _ in range(size)]
        return members, weakref.WeakSet(members)

    @pytest.mark.timing
    def test_membership_does_not_grow_with_the_set(self) -> None:
        small_members, small = self._set(100)
        large_members, large = self._set(100_000)
        small_probe, large_probe = small_members[50], large_members[50_000]

        small_ns = best_ns(lambda: (small_probe in small, len(small)), inner=1_000)
        large_ns = best_ns(lambda: (large_probe in large, len(large)), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 3, f"1,000x the elements cost x{ratio:.2f} per membership test"

    @pytest.mark.timing
    def test_intersection_walks_only_the_other_operand(self) -> None:
        small_members, small = self._set(100)
        large_members, large = self._set(100_000)
        small_other = small_members[:100]
        large_other = large_members[:100]

        small_ns = best_ns(lambda: small & small_other, inner=10)
        large_ns = best_ns(lambda: large & large_other, inner=10)

        assert len(large & large_other) == 100
        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"1,000x the set cost x{ratio:.2f} for & against 100 items "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); the row claims O(m)"
        )

    @pytest.mark.timing
    def test_union_and_intersection_update_walk_the_set(self) -> None:
        small_members, small = self._set(100)
        large_members, large = self._set(100_000)
        other = [Node() for _ in range(100)]

        union_small = best_ns(lambda: small | other, repeats=5)
        union_large = best_ns(lambda: large | other, repeats=5)

        def update(members: list[Node]) -> float:
            return best_ns_with_setup(
                lambda: weakref.WeakSet(members), lambda target: target.__iand__(other), 5
            )

        update_small = update(small_members)
        update_large = update(large_members)

        union_ratio = union_large / union_small
        update_ratio = update_large / update_small
        assert union_ratio > 30, f"1,000x the set cost only x{union_ratio:.1f} for |"
        assert update_ratio > 30, f"1,000x the set cost only x{update_ratio:.1f} for &="

    @pytest.mark.timing
    def test_issubset_builds_the_other_operand(self) -> None:
        members, subject = self._set(10)
        # Members last: a non-set operand is walked until all of them are found.
        small_other = [Node() for _ in range(90)] + members
        large_other = [Node() for _ in range(99_990)] + members

        small_ns = best_ns(lambda: subject.issubset(small_other), repeats=5)
        large_ns = best_ns(lambda: subject.issubset(large_other), repeats=5)

        assert subject.issubset(large_other)
        ratio = large_ns / small_ns
        assert ratio > 30, f"1,000x the other operand cost only x{ratio:.1f} for issubset"

    def test_the_set_methods(self) -> None:
        a, b, c = Node(), Node(), Node()
        subject = weakref.WeakSet([a, b])

        assert set(subject | [c]) == {a, b, c}
        assert set(subject - [a]) == {b}
        assert set(subject ^ [b, c]) == {a, c}
        assert set(subject.intersection([b, c])) == {b}
        assert not subject.isdisjoint([b])
        assert subject <= weakref.WeakSet([a, b, c]) and subject < weakref.WeakSet([a, b, c])
        assert subject >= weakref.WeakSet([a]) and subject > weakref.WeakSet([a])
        assert subject == weakref.WeakSet([b, a])
        assert subject.issubset([a, b]) and subject.issuperset([a])

        copied = subject.copy()
        subject.discard(a)
        subject.remove(b)
        assert len(subject) == 0 and len(copied) == 2
        with pytest.raises(KeyError):
            subject.remove(c)

        copied |= [c]
        copied -= [a]
        copied ^= [a]
        copied &= [a, c]
        assert set(copied) == {a, c}
        assert copied.pop() in (a, c)
        copied.clear()
        assert len(copied) == 0

    def test_an_element_goes_when_it_dies(self) -> None:
        keep, drop = Node(), Node()
        members = weakref.WeakSet([keep, drop])

        del drop
        gc.collect()

        assert list(members) == [keep]


class TestWeakMethod:
    """`WeakMethod` holds the instance and the function, and rebuilds the
    bound method on each call."""

    def test_a_plain_reference_to_a_bound_method_dies_at_once(self) -> None:
        account = Account()

        plain = weakref.ref(account.deposit)
        gc.collect()

        assert plain() is None

    def test_each_call_builds_a_new_bound_method(self) -> None:
        account = Account()
        method = weakref.WeakMethod(account.deposit)

        first, second = method(), method()

        assert first is not None and second is not None
        assert first is not second
        assert first == second == account.deposit
        assert first(1) == 11

    def test_it_dies_with_the_instance_and_calls_back_once(self) -> None:
        account = Account()
        calls: list[object] = []
        method = weakref.WeakMethod(account.deposit, calls.append)

        del account
        gc.collect()

        assert method() is None
        assert calls == [method]


EXIT_ORDER = """
import weakref

class Thing:
    pass

things = [Thing() for _ in range(4)]
for name, thing in zip("abcd", things):
    finalizer = weakref.finalize(thing, print, name)
    if name == "c":
        finalizer.atexit = False
"""


class TestFinalize:
    """`finalize` runs once, on death, on a call or at exit, newest first."""

    def test_it_runs_once_on_death(self) -> None:
        node = Node()
        calls: list[str] = []
        finalizer = weakref.finalize(node, calls.append, "done")

        assert finalizer.alive
        assert finalizer.atexit is True

        del node
        gc.collect()

        assert calls == ["done"]
        assert not finalizer.alive
        assert finalizer() is None
        assert calls == ["done"]

    def test_calling_it_runs_it_once_and_returns_the_result(self) -> None:
        node = Node()
        finalizer = weakref.finalize(node, lambda x, y=0: x + y, 1, y=2)

        assert finalizer() == 3
        assert finalizer() is None
        assert not finalizer.alive

    def test_peek_and_detach(self) -> None:
        node = Node()
        finalizer = weakref.finalize(node, anything, "arg", key="word")

        assert finalizer.peek() == (node, anything, ("arg",), {"key": "word"})
        assert finalizer.alive
        assert finalizer.detach() == (node, anything, ("arg",), {"key": "word"})
        assert not finalizer.alive
        assert finalizer.peek() is None
        assert finalizer.detach() is None

    def test_it_runs_with_no_reference_kept_to_it(self) -> None:
        node = Node()
        calls: list[str] = []
        weakref.finalize(node, calls.append, "done")

        gc.collect()
        assert calls == []

        del node
        gc.collect()

        assert calls == ["done"]

    def test_a_function_that_refers_to_the_object_keeps_it_alive(self) -> None:
        account = Account()
        witness = weakref.ref(account)
        finalizer = weakref.finalize(account, account.deposit, 1)

        del account
        gc.collect()

        assert witness() is not None
        assert finalizer.alive
        assert finalizer() == 11
        gc.collect()
        assert witness() is None

    def test_atexit_runs_the_live_ones_newest_first(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "exit.py"
        script.write_text(EXIT_ORDER, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        )

        assert result.stdout.split() == ["d", "b", "a"]


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
        line, source = next((n, s) for n, s in _blocks() if "seen == [reference]" in s)
        mutated = source.replace("seen == [reference]", "seen == []", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
