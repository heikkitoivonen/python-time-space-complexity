"""Tests for docs/stdlib/collections.abc.md.

The page prices two things: what `isinstance()` costs against an ABC, and
what each mixin method costs in calls to the abstract methods a subclass
supplies. Both are settled by counting. Recording subclasses count their
`__getitem__`, `__setitem__`, `__delitem__`, `__iter__`, `__len__`,
`__contains__`, `add()`, `discard()`, `insert()` and `send()` calls, and a
probe subclass counts how often the ABC machinery reaches it. A stopwatch is
used only for the two quadratic `clear()` mixins, which have no counter for
the slots an iterator skips.

Measurement scope:

* Runtime checks: `_check_methods` is counted at one call for the first
  `isinstance()` against `Sized` and zero for the second. A `Mapping` subclass
  with a counting `__subclasshook__` is reached once by a first check of an
  unrelated class against `Mapping`, not at all by a repeat, and once more
  after `Set.register()` of a third class, which shows the subclass walk, the
  negative cache and its invalidation; a registered ABC with a counting hook
  is reached the same way, which shows the registry walk. The structural
  hooks are asserted on classes with and without the required methods, a
  method inherited from a base included, and `Hashable` on a class with
  `__hash__ = None`. `register()` bumps `abc.get_cache_token()` for a new
  class and leaves it alone for one that already is a subclass. `Callable`
  subscription is asserted to flatten `[int, str], float` into three
  arguments. `Buffer` recognises `bytes`, `bytearray` and `memoryview` on
  3.12+; `ByteString` warns on `isinstance()` and on subclassing from 3.12
  and not before, and its `index` is `Sequence.index`.
* `Iterator.__iter__` and `AsyncIterator.__aiter__` return the instance.
  `next()` on a `Generator` subclass is one `send(None)`, `close()` one
  `throw(GeneratorExit)`, and `RuntimeError` when `throw()` yields instead of
  raising; the same through `Coroutine.close()`; `__anext__` and `aclose()`
  on an `AsyncGenerator` subclass are one `asend(None)` and one
  `athrow(GeneratorExit)`. The eight protocol-only ABCs are asserted to define
  no public non-dunder methods.
* `Sequence`: iterating a four-item recording sequence through the mixin's
  own iterator is five `__getitem__` calls and no `__len__` call, where
  `list(seq)` would add `list()`'s own length hint; `in` stops at the match; `reversed`
  is one `__len__` and four `__getitem__`; `index()` with a stop is one
  `__getitem__` per position up to the stop, with a negative start one
  `__len__`; `count()` is five `__getitem__`. `MutableSequence`: `append()` is
  one `__len__` and one `insert()`; `extend()` is one `insert()` per value and
  `extend(self)` doubles the sequence; `pop()` one `__getitem__` and one
  `__delitem__`; `remove()` the `index()` reads plus one `__delitem__`;
  `reverse()` on four items one `__len__`, four `__getitem__` and four
  `__setitem__`; `clear()` five `__getitem__` and four `__delitem__`.
* `Set`: `<=` is two `__len__` calls and then one `other.__contains__` per
  element until the first miss, and `==` the same after two `__len__` calls
  of its own, and zero
  `__contains__` when the sizes already decide; `>=` is one `s.__contains__`
  per element of `other`; `&` one `s.__contains__` per element of `other`;
  `|` no `__contains__` at all; `-` one `other.__contains__` per element of
  `s`, and one `_from_iterable()` call first when `other` is a list; `^`
  three `_from_iterable()` calls; `isdisjoint()` stops at the first shared
  element; `_hash()` equals `hash(frozenset(s))` and hashes each element
  once; a class whose constructor takes no iterable raises `TypeError` from
  `&` until `_from_iterable()` is overridden. `MutableSet`: `remove()` is one
  `__contains__` and one `discard()`, raising `KeyError`; `pop()` one
  `__iter__` and one `discard()`; `clear()` on four elements five `__iter__`
  and four `discard()`; `|=` one `add()` per element; `&=` one
  `it.__contains__` per element of `s`; `^=` one `__contains__` per element
  of `it`; `-=` one `discard()` per element of `it`; `s ^= s` and `s -= s`
  empty `s`. A timing test puts `clear()` over a `set`-backed store of 32,000
  elements above 20x its cost on 4,000, where linear growth would give 8x.
* `Mapping`: `get()` and `in` are one `__getitem__`; `keys()`, `items()` and
  `values()` make no calls; `==` against a dict makes one `__getitem__` per
  key and peaks above 1 MB for 100,000 keys; `reversed()` raises `TypeError`.
  Views: `len()` is one `__len__`; iterating a `KeysView` is one `__iter__`
  and no `__getitem__`, an `ItemsView` or `ValuesView` one `__getitem__` per
  key; `in` on a `KeysView` is one `__contains__`, on an `ItemsView` one
  `__getitem__`, on a `ValuesView` one `__getitem__` per key until the match;
  `keys() & other` is a `set`. `MutableMapping`: `pop()` is one `__getitem__`
  and one `__delitem__`; `popitem()` one `__iter__`, one `__getitem__` and
  one `__delitem__`, removing the first key; `clear()` on three keys four
  `__iter__`; `update()` one `__setitem__` per item from a mapping, a
  `keys()` object, pairs and keywords, plus one `other[key]` per key for the
  first two; `setdefault()` one `__getitem__` and, on a miss, one
  `__setitem__`. A timing test puts `clear()` over a dict-backed store of
  32,000 keys above 20x its cost on 4,000.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* That a structural hook is linear in the MRO is read from
  `_check_methods` in Lib/_collections_abc.py, which loops over `__mro__`;
  the tests show the hook finds an inherited method and is not repeated once
  cached. The order MRO, registry, subclasses, and the negative cache's
  version check, are read from `_abc__abc_subclasscheck_impl` in
  Modules/_abc.c; the tests show each of the three sources is consulted and
  that the negative cache is dropped by an unrelated `register()`.
* `register()` is priced at two `issubclass()` checks, read from
  `_abc__abc_register_impl`; the tests show its effect on the token and that
  the second check reaches the registered class's hook, not the first check.
* Subscription is priced in type arguments by the length of `__args__`, not
  by a counter on the alias machinery.
* Each abstract method is counted as O(1); the pages of the concrete
  containers price the real ones.
* `d`, the slots a fresh iterator skips in `pop()` and `popitem()`, is read
  from Objects/dictobject.c and Objects/setobject.c; the timing tests show
  the quadratic total of `clear()`.
* Module-level names that are not in `__all__` - `bytes_iterator`,
  `dict_keys`, `mappingproxy`, `framelocalsproxy` and the other type aliases
  the module keeps for its own `register()` calls - are implementation
  details and intentionally undocumented.
"""

from __future__ import annotations

import _collections_abc
import abc
import asyncio
import importlib
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Collection,
    Container,
    Coroutine,
    Generator,
    Hashable,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Reversible,
    Sequence,
    Set,
    Sized,
    ValuesView,
)
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "collections.abc.md"
EXPECTED_BLOCKS = 4

# typeshed types the ABCs as protocols without `register`, `__args__` or the
# 3.12+ `Buffer`; the module itself, untyped, is what the runtime claims are about.
abcs: Any = importlib.import_module("collections.abc")


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def best_clear_ns(build: Callable[[int], Any], size: int, repeats: int = 3) -> float:
    """Fastest `clear()` of a freshly built store, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        store = build(size)
        start = time.perf_counter_ns()
        store.clear()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


class Calls:
    """A call counter shared by the recording classes below."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def hit(self, name: str) -> None:
        self.counts[name] = self.counts.get(name, 0) + 1

    def reset(self) -> None:
        self.counts.clear()

    def __getitem__(self, name: str) -> int:
        return self.counts.get(name, 0)


class HasLen:
    def __len__(self) -> int:
        return 0


class InheritsLen(HasLen):
    pass


class DuckMapping:
    def __getitem__(self, key: str) -> int:
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0


class TestRuntimeChecks:
    """`isinstance()` | O(1) cached, O(L) with a hook, O(L·(1 + R + S)) without;
    `register()` bumps the token for a new relationship; subscription | O(a)."""

    def test_a_structural_hook_runs_once_and_is_then_cached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = Calls()
        original = _collections_abc._check_methods  # pyright: ignore[reportAttributeAccessIssue]

        def counting(cls: type, *methods: str) -> Any:
            calls.hit("check")
            return original(cls, *methods)

        monkeypatch.setattr(_collections_abc, "_check_methods", counting)

        class Fresh:
            def __len__(self) -> int:
                return 0

        assert isinstance(Fresh(), Sized)
        assert calls["check"] == 1
        assert isinstance(Fresh(), Sized)
        assert calls["check"] == 1

    def test_structural_hooks_look_for_the_named_methods(self) -> None:
        class OnlyNext:
            def __next__(self) -> int:
                raise StopIteration

        class Callable_:
            def __call__(self) -> None:
                pass

        assert isinstance(HasLen(), Sized)
        assert isinstance(InheritsLen(), Sized), "a method inherited from a base is found"
        assert not isinstance(object(), Sized)
        assert not isinstance(OnlyNext(), Iterator), "Iterator needs __iter__ and __next__"
        assert isinstance(iter([]), Iterator)
        assert isinstance(Callable_(), Callable)
        assert isinstance(DuckMapping(), Sized)
        assert isinstance(DuckMapping(), Iterable)
        assert not isinstance(DuckMapping(), Container)
        assert not isinstance(DuckMapping(), Collection)
        assert isinstance((), Hashable)
        assert not isinstance([], Hashable), "__hash__ = None is treated as absent"

    def test_mixin_abcs_are_not_structural(self) -> None:
        assert not isinstance(DuckMapping(), Mapping)
        assert not issubclass(DuckMapping, Sequence)
        assert not issubclass(DuckMapping, Set)

    def test_a_miss_walks_the_subclasses_and_is_cached_until_a_register(self) -> None:
        calls = Calls()

        class Probe(Mapping[str, int]):
            @classmethod
            def __subclasshook__(cls, candidate: type) -> Any:
                calls.hit("probe")
                return NotImplemented

        class Unrelated:
            pass

        class Other:
            pass

        assert not isinstance(Unrelated(), Mapping)
        assert calls["probe"] == 1, "the walk reaches every subclass of the ABC"

        assert not isinstance(Unrelated(), Mapping)
        assert calls["probe"] == 1, "the negative result is cached"

        abcs.Set.register(Other)
        assert not isinstance(Unrelated(), Mapping)
        assert calls["probe"] == 2, "an unrelated register() empties the negative cache"

        assert not isinstance(Unrelated(), Mapping)
        assert calls["probe"] == 2

    def test_a_miss_consults_the_registry(self) -> None:
        calls = Calls()

        class Registered(metaclass=abc.ABCMeta):  # noqa: B024
            @classmethod
            def __subclasshook__(cls, candidate: type) -> Any:
                calls.hit("registered")
                return NotImplemented

        class Local(Mapping[str, int]):
            def __getitem__(self, key: str) -> int:
                raise KeyError(key)

            def __iter__(self) -> Iterator[str]:
                return iter(())

            def __len__(self) -> int:
                return 0

        class Unrelated:
            pass

        abcs.Mapping.register.__func__(Local, Registered)
        assert calls["registered"] == 1, "register() itself asks issubclass(Local, Registered)"

        assert not isinstance(Unrelated(), Local)
        assert calls["registered"] == 2

    def test_register_bumps_the_token_for_a_new_class_only(self) -> None:
        class Fresh:
            pass

        class AlreadyOne(Mapping[str, int]):
            def __getitem__(self, key: str) -> int:
                raise KeyError(key)

            def __iter__(self) -> Iterator[str]:
                return iter(())

            def __len__(self) -> int:
                return 0

        before = abc.get_cache_token()
        abcs.Mapping.register(Fresh)
        after = abc.get_cache_token()
        assert after != before
        assert isinstance(Fresh(), Mapping)

        abcs.Mapping.register(AlreadyOne)
        assert abc.get_cache_token() == after

    def test_subscription_flattens_callable_arguments(self) -> None:
        def type_args(alias: Any) -> tuple[Any, ...]:
            return alias.__args__

        assert type_args(Callable[[int, str], float]) == (int, str, float)
        assert type_args(Callable[..., float]) == (Ellipsis, float)
        assert type_args(Iterable[int]) == (int,)
        assert type_args(Mapping[str, int]) == (str, int)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="Buffer is 3.12+")
    def test_buffer_is_structural(self) -> None:
        Buffer = abcs.Buffer

        class Exposes:
            def __buffer__(self, flags: int) -> memoryview:
                return memoryview(b"")

        for value in (b"", bytearray(), memoryview(b""), Exposes()):
            assert isinstance(value, Buffer)
        assert not isinstance("", Buffer)

    def test_bytestring_index_is_the_sequence_mixin(self) -> None:
        assert abcs.ByteString.index is Sequence.index

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="deprecated from 3.12")
    def test_bytestring_warns_from_312(self) -> None:
        with pytest.warns(DeprecationWarning, match="ByteString"):
            assert isinstance(b"", abcs.ByteString)
        with pytest.warns(DeprecationWarning, match="ByteString"):

            class Sub(abcs.ByteString):  # pyright: ignore[reportUnusedClass]
                pass

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="not deprecated before 3.12")
    def test_bytestring_is_silent_before_312(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert isinstance(b"", abcs.ByteString)


class TestIteratorAndGeneratorMixins:
    """`Iterator.__iter__` | self; `Generator.__next__` | one `send(None)`;
    `close()` | one `throw(GeneratorExit)`; the async pair likewise."""

    def test_iter_and_aiter_return_self(self) -> None:
        class Ints(Iterator[int]):
            def __next__(self) -> int:
                raise StopIteration

        class AsyncInts(AsyncIterator[int]):
            async def __anext__(self) -> int:
                raise StopAsyncIteration

        ints, async_ints = Ints(), AsyncInts()
        assert iter(ints) is ints
        assert async_ints.__aiter__() is async_ints

    @staticmethod
    def _generator(calls: Calls, stops_on_exit: bool = True) -> Generator[int, Any, None]:
        class Gen(Generator[int, Any, None]):
            def send(self, value: Any) -> int:
                calls.hit("send")
                return 42

            def throw(self, typ: Any, val: Any = None, tb: Any = None) -> int:
                calls.hit("throw")
                if stops_on_exit:
                    raise typ if val is None else val
                return 0

        return Gen()

    def test_next_is_one_send(self) -> None:
        calls = Calls()
        gen = self._generator(calls)

        assert next(gen) == 42
        assert calls.counts == {"send": 1}

    def test_close_is_one_throw(self) -> None:
        calls = Calls()
        gen = self._generator(calls)

        gen.close()
        assert calls.counts == {"throw": 1}

        with pytest.raises(RuntimeError, match="ignored GeneratorExit"):
            self._generator(calls, stops_on_exit=False).close()

    def test_coroutine_close_is_one_throw(self) -> None:
        calls = Calls()

        class Coro(Coroutine[int, Any, None]):
            def __await__(self) -> Generator[Any, None, None]:
                yield

            def send(self, value: Any) -> int:
                calls.hit("send")
                return 0

            def throw(self, typ: Any, val: Any = None, tb: Any = None) -> int:
                calls.hit("throw")
                raise typ if val is None else val

        Coro().close()  # pyright: ignore[reportAbstractUsage]
        assert calls.counts == {"throw": 1}

    def test_anext_is_one_asend_and_aclose_one_athrow(self) -> None:
        calls = Calls()

        class AsyncGen(AsyncGenerator[int, Any]):
            async def asend(self, value: Any) -> int:
                calls.hit("asend")
                return 7

            async def athrow(self, typ: Any, val: Any = None, tb: Any = None) -> int:
                calls.hit("athrow")
                raise typ if val is None else val

        async def drive() -> int:
            gen = AsyncGen()
            value = await gen.__anext__()
            await gen.aclose()
            return value

        assert asyncio.run(drive()) == 7
        assert calls.counts == {"asend": 1, "athrow": 1}

    def test_protocol_only_abcs_add_no_methods(self) -> None:
        protocols: list[Any] = [Hashable, Awaitable, Iterable, Reversible, Sized, Container]
        protocols += [Collection, Callable]
        for protocol in protocols:
            public = [name for name in vars(protocol) if not name.startswith("_")]
            assert public == [], f"{protocol.__name__} defines {public}"


class RecordingSequence(MutableSequence[int]):
    """A list-backed MutableSequence that counts the abstract calls."""

    def __init__(self, items: Iterable[int] = ()) -> None:
        self._items = list(items)
        self.calls = Calls()

    def __getitem__(self, index: Any) -> Any:
        self.calls.hit("getitem")
        return self._items[index]

    def __setitem__(self, index: Any, value: Any) -> None:
        self.calls.hit("setitem")
        self._items[index] = value

    def __delitem__(self, index: Any) -> None:
        self.calls.hit("delitem")
        del self._items[index]

    def __len__(self) -> int:
        self.calls.hit("len")
        return len(self._items)

    def insert(self, index: int, value: int) -> None:
        self.calls.hit("insert")
        self._items.insert(index, value)


class TestSequenceMixins:
    """`Sequence.__iter__` | n + 1 `__getitem__`; `__contains__` | O(i);
    `__reversed__` | `__len__` + n; `index()` | O(i); `count()` | n + 1."""

    def test_iteration_indexes_until_indexerror_without_len(self) -> None:
        seq = RecordingSequence([10, 20, 30, 40])

        # list(seq) would add list()'s own len() call; the mixin's generator has no length
        assert list(iter(seq)) == [10, 20, 30, 40]

        assert seq.calls.counts == {"getitem": 5}

    def test_contains_stops_at_the_match(self) -> None:
        seq = RecordingSequence([10, 20, 30, 40])

        assert 20 in seq
        assert seq.calls["getitem"] == 2

        seq.calls.reset()
        assert 99 not in seq
        assert seq.calls["getitem"] == 5

    def test_reversed_is_one_len_and_n_reads(self) -> None:
        seq = RecordingSequence([10, 20, 30, 40])

        assert list(reversed(seq)) == [40, 30, 20, 10]

        assert seq.calls.counts == {"len": 1, "getitem": 4}

    def test_index_reads_from_start_to_the_match_or_the_stop(self) -> None:
        seq = RecordingSequence([10, 20, 30, 40])

        assert seq.index(30) == 2
        assert seq.calls.counts == {"getitem": 3}

        seq.calls.reset()
        with pytest.raises(ValueError):
            seq.index(99, 1, 3)
        assert seq.calls.counts == {"getitem": 2}, "positions 1 and 2 only"

        seq.calls.reset()
        assert seq.index(40, -1) == 3
        assert seq.calls.counts == {"len": 1, "getitem": 1}

    def test_count_iterates_the_whole_sequence(self) -> None:
        seq = RecordingSequence([10, 20, 10, 40])

        assert seq.count(10) == 2

        assert seq.calls.counts == {"getitem": 5}


class TestMutableSequenceMixins:
    """`append()` | `__len__` + `insert()`; `extend()` | k `append()`;
    `pop()` | get + del; `remove()` | `index()` + del; `reverse()` | n gets
    and n sets; `clear()` | `pop()` until `IndexError`."""

    def test_append_is_len_and_insert(self) -> None:
        seq = RecordingSequence([1])

        seq.append(2)

        assert seq.calls.counts == {"len": 1, "insert": 1}
        assert list(seq._items) == [1, 2]

    def test_extend_appends_each_value_and_copies_itself_first(self) -> None:
        seq = RecordingSequence([1, 2])

        seq.extend([3, 4, 5])
        assert seq.calls["insert"] == 3

        seq.calls.reset()
        seq.extend(seq)
        assert seq._items == [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        assert seq.calls["insert"] == 5

        seq += [6]
        assert seq._items[-1] == 6

    def test_pop_is_one_read_and_one_delete(self) -> None:
        seq = RecordingSequence([1, 2, 3])

        assert seq.pop() == 3
        assert seq.calls.counts == {"getitem": 1, "delitem": 1}

        seq.calls.reset()
        assert seq.pop(0) == 1
        assert seq.calls.counts == {"getitem": 1, "delitem": 1}

    def test_remove_is_index_and_one_delete(self) -> None:
        seq = RecordingSequence([10, 20, 30])

        seq.remove(20)

        assert seq.calls.counts == {"getitem": 2, "delitem": 1}
        assert seq._items == [10, 30]

    def test_reverse_swaps_from_both_ends(self) -> None:
        seq = RecordingSequence([1, 2, 3, 4])

        seq.reverse()

        assert seq._items == [4, 3, 2, 1]
        assert seq.calls.counts == {"len": 1, "getitem": 4, "setitem": 4}

    def test_clear_pops_from_the_end_until_indexerror(self) -> None:
        seq = RecordingSequence([1, 2, 3, 4])

        seq.clear()

        assert seq._items == []
        assert seq.calls.counts == {"getitem": 5, "delitem": 4}


class RecordingSet(MutableSet[int]):
    """A set-backed MutableSet that counts the abstract calls and its
    constructions through `_from_iterable`."""

    constructions = 0

    def __init__(self, items: Iterable[int] = ()) -> None:
        self._items = set(items)
        self.calls = Calls()

    @classmethod
    def _from_iterable(cls, it: Iterable[Any]) -> RecordingSet:
        cls.constructions += 1
        return cls(it)

    def __contains__(self, value: object) -> bool:
        self.calls.hit("contains")
        return value in self._items

    def __iter__(self) -> Iterator[int]:
        self.calls.hit("iter")
        return iter(self._items)

    def __len__(self) -> int:
        self.calls.hit("len")
        return len(self._items)

    def add(self, value: int) -> None:
        self.calls.hit("add")
        self._items.add(value)

    def discard(self, value: int) -> None:
        self.calls.hit("discard")
        self._items.discard(value)


class HashCounting:
    """An element whose hash calls are counted."""

    def __init__(self, value: int, calls: Calls) -> None:
        self.value = value
        self.calls = calls

    def __hash__(self) -> int:
        self.calls.hit("hash")
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HashCounting) and other.value == self.value


class TestSetMixins:
    """Comparisons | one `__contains__` per element of one side; `&`, `-`,
    `^` | membership loops; `|` | none; `isdisjoint()` | stops early;
    `_hash()` | one hash per element; results built through `_from_iterable`."""

    def setup_method(self) -> None:
        RecordingSet.constructions = 0

    def test_subset_checks_sizes_then_membership_in_other(self) -> None:
        small, large = RecordingSet({1, 2}), RecordingSet({1, 2, 3, 4})

        assert small <= large
        assert small.calls["len"] == 1 and large.calls["len"] == 1
        assert large.calls["contains"] == 2 and small.calls["contains"] == 0

        small.calls.reset()
        large.calls.reset()
        assert not large <= small, "the sizes settle it"
        assert large.calls["contains"] == 0 and small.calls["contains"] == 0

        small.calls.reset()
        large.calls.reset()
        assert small != large
        assert large.calls["contains"] == 0, "unequal sizes settle == too"

        twin = RecordingSet({2, 1})
        small.calls.reset()
        assert small == twin
        assert small.calls["len"] == 2 and twin.calls["len"] == 2, "== checks, then <= checks again"
        assert twin.calls["contains"] == 2

    def test_subset_stops_at_the_first_miss(self) -> None:
        left, right = RecordingSet({1, 2, 3}), RecordingSet({7, 8, 9})

        assert not left <= right

        assert right.calls["contains"] == 1

    def test_superset_tests_membership_in_self(self) -> None:
        small, large = RecordingSet({1, 2}), RecordingSet({1, 2, 3, 4})

        assert large >= small

        assert large.calls["contains"] == 2 and small.calls["contains"] == 0

    def test_and_iterates_other_and_tests_self(self) -> None:
        evens, small = RecordingSet({0, 2, 4, 6, 8}), RecordingSet({0, 1, 2, 3})

        both = evens & small

        assert type(both) is RecordingSet and set(both) == {0, 2}
        assert evens.calls["contains"] == 4 and small.calls["contains"] == 0
        assert RecordingSet.constructions == 1

        assert set(evens & [1, 2]) == {2}, "any iterable will do"  # pyright: ignore[reportOperatorIssue]

    def test_or_tests_nothing(self) -> None:
        left, right = RecordingSet({1, 2}), RecordingSet({2, 3})

        union = left | right

        assert set(union) == {1, 2, 3}
        assert left.calls["contains"] == 0 and right.calls["contains"] == 0
        assert RecordingSet.constructions == 1

    def test_difference_tests_membership_in_other_after_converting_it(self) -> None:
        left, right = RecordingSet({1, 2, 3}), RecordingSet({2, 3, 4})

        assert set(left - right) == {1}
        assert right.calls["contains"] == 3 and left.calls["contains"] == 0
        assert RecordingSet.constructions == 1

        RecordingSet.constructions = 0
        left.calls.reset()
        assert set(left - [2, 3, 4]) == {1}  # pyright: ignore[reportOperatorIssue]
        assert RecordingSet.constructions == 2, "the list is built into a set first"
        assert left.calls["contains"] == 0

        RecordingSet.constructions = 0
        left.calls.reset()
        assert set([2, 3, 4] - left) == {4}  # pyright: ignore[reportOperatorIssue]
        assert left.calls["contains"] == 3
        assert RecordingSet.constructions == 2

    def test_symmetric_difference_builds_three_sets(self) -> None:
        left, right = RecordingSet({1, 2, 3}), RecordingSet({2, 3, 4})

        assert set(left ^ right) == {1, 4}

        assert right.calls["contains"] == 3 and left.calls["contains"] == 3
        assert RecordingSet.constructions == 3

    def test_isdisjoint_stops_at_the_first_shared_element(self) -> None:
        evens = RecordingSet({0, 2, 4})

        assert not evens.isdisjoint([1, 3, 0, 5])
        assert evens.calls["contains"] == 3

        evens.calls.reset()
        assert evens.isdisjoint([1, 3, 5])
        assert evens.calls["contains"] == 3

    def test_hash_matches_frozenset_and_hashes_each_element_once(self) -> None:
        calls = Calls()
        elements = [HashCounting(value, calls) for value in range(5)]

        class Hashed(Set[HashCounting]):
            def __init__(self, items: Iterable[HashCounting]) -> None:
                self._items = list(items)

            def __contains__(self, value: object) -> bool:
                return value in self._items

            def __iter__(self) -> Iterator[HashCounting]:
                return iter(self._items)

            def __len__(self) -> int:
                return len(self._items)

            def __hash__(self) -> int:
                return self._hash()

        hashed = Hashed(elements)
        calls.reset()

        assert hash(hashed) == hash(frozenset(elements))
        assert calls["hash"] == 10, "once for _hash() and once for frozenset()"

    def test_operators_need_a_constructor_that_takes_an_iterable(self) -> None:
        class Fixed(Set[int]):
            def __init__(self) -> None:
                self._items = {1, 2}

            def __contains__(self, value: object) -> bool:
                return value in self._items

            def __iter__(self) -> Iterator[int]:
                return iter(self._items)

            def __len__(self) -> int:
                return len(self._items)

        with pytest.raises(TypeError):
            _ = Fixed() & {1}

        class Fixed2(Fixed):
            @classmethod
            def _from_iterable(cls, it: Iterable[Any]) -> set[Any]:
                return set(it)

        assert Fixed2() & {1} == {1}


class TestMutableSetMixins:
    """`remove()` | `__contains__` + `discard()`; `pop()` | `__iter__` +
    `discard()`; `clear()` | n `pop()`, O(n·(n + d)) over a set; the in-place
    operators | one call per element of the operand."""

    SMALL = 4_000
    LARGE = 32_000

    def test_remove_checks_then_discards(self) -> None:
        store = RecordingSet({1, 2})

        store.remove(1)
        assert store.calls.counts == {"contains": 1, "discard": 1}

        with pytest.raises(KeyError):
            store.remove(9)

    def test_pop_takes_the_first_of_a_fresh_iterator(self) -> None:
        store = RecordingSet({1, 2, 3})

        popped = store.pop()

        assert popped not in store._items
        assert store.calls.counts == {"iter": 1, "discard": 1}

    def test_clear_pops_until_the_iterator_is_empty(self) -> None:
        store = RecordingSet({1, 2, 3, 4})

        store.clear()

        assert store._items == set()
        assert store.calls.counts == {"iter": 5, "discard": 4}

    @pytest.mark.timing
    def test_clear_over_a_set_grows_faster_than_the_set(self) -> None:
        small_ns = best_clear_ns(lambda size: RecordingSet(range(size)), self.SMALL)
        large_ns = best_clear_ns(lambda size: RecordingSet(range(size)), self.LARGE)

        assert large_ns > small_ns * 20, (
            f"clear() on {self.LARGE} elements took {large_ns / 1e6:.1f} ms, on {self.SMALL} "
            f"{small_ns / 1e6:.1f} ms; a linear clear would be near 8x"
        )

    def test_inplace_or_adds_each_element(self) -> None:
        store = RecordingSet({1})

        store |= [2, 3]  # pyright: ignore[reportOperatorIssue]

        assert store._items == {1, 2, 3}
        assert store.calls.counts == {"add": 2}

    def test_inplace_and_tests_self_against_the_other_and_discards(self) -> None:
        store, keep = RecordingSet({1, 2, 3, 4}), RecordingSet({2, 3})

        store &= keep

        assert store._items == {2, 3}
        assert keep.calls["contains"] == 4
        assert store.calls["discard"] == 2

    def test_inplace_xor_tests_each_element_of_the_operand(self) -> None:
        store = RecordingSet({1, 2, 3})

        store ^= RecordingSet({3, 4})

        assert store._items == {1, 2, 4}
        assert store.calls["contains"] == 2
        assert store.calls["discard"] == 1 and store.calls["add"] == 1

        store ^= store
        assert store._items == set()

    def test_inplace_sub_discards_each_element_of_the_operand(self) -> None:
        store = RecordingSet({1, 2, 3})

        store -= [2, 9]  # pyright: ignore[reportOperatorIssue]

        assert store._items == {1, 3}
        assert store.calls.counts == {"discard": 2}

        store -= store
        assert store._items == set()


class RecordingMapping(MutableMapping[str, int]):
    """A dict-backed MutableMapping that counts the abstract calls."""

    def __init__(self, items: Mapping[str, int] | None = None) -> None:
        self._data = dict(items or {})
        self.calls = Calls()

    def __getitem__(self, key: str) -> int:
        self.calls.hit("getitem")
        return self._data[key]

    def __setitem__(self, key: str, value: int) -> None:
        self.calls.hit("setitem")
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        self.calls.hit("delitem")
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        self.calls.hit("iter")
        return iter(self._data)

    def __len__(self) -> int:
        self.calls.hit("len")
        return len(self._data)


class ContainsCountingMapping(RecordingMapping):
    def __contains__(self, key: object) -> bool:
        self.calls.hit("contains")
        return key in self._data


class TestMappingMixins:
    """`get()`, `in` | one `__getitem__`; views | O(1) to make; `==` |
    flattens both sides; `reversed()` | `TypeError`."""

    def test_get_and_contains_are_one_read(self) -> None:
        store = RecordingMapping({"a": 1})

        assert store.get("a") == 1
        assert store.get("z", 0) == 0
        assert "a" in store and "z" not in store

        assert store.calls.counts == {"getitem": 4}

    def test_views_cost_nothing_to_make(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2})

        keys, items, values = store.keys(), store.items(), store.values()

        assert isinstance(keys, KeysView) and isinstance(items, ItemsView)
        assert isinstance(values, ValuesView)
        assert store.calls.counts == {}

    def test_equality_reads_every_key_and_flattens_both_sides(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2, "c": 3})

        assert store == {"a": 1, "b": 2, "c": 3}
        assert store.calls["getitem"] == 3

        big = RecordingMapping({str(index): index for index in range(100_000)})
        other = dict(big._data)
        peak = peak_bytes(lambda: big == other)
        assert peak > 1_000_000, f"Mapping == dict allocated only {peak} bytes"

    def test_reversed_raises(self) -> None:
        with pytest.raises(TypeError):
            reversed(RecordingMapping({"a": 1}))  # pyright: ignore[reportArgumentType, reportCallIssue]


class TestMappingViews:
    """`len(view)` | one `__len__`; iterating | `__iter__` plus, for items
    and values, one `__getitem__` per key; `in` | one call, or a scan for
    values; set operators | plain `set` results."""

    def test_len_is_the_mappings_len(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2})

        assert len(store.keys()) == 2 and len(store.items()) == 2 and len(store.values()) == 2

        assert store.calls.counts == {"len": 3}

    def test_iterating_items_and_values_reads_once_per_key(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2, "c": 3})

        # list(view) would add list()'s own len() call; the views' generators have none
        assert list(iter(store.keys())) == ["a", "b", "c"]
        assert store.calls.counts == {"iter": 1}

        store.calls.reset()
        assert list(iter(store.items())) == [("a", 1), ("b", 2), ("c", 3)]
        assert store.calls.counts == {"iter": 1, "getitem": 3}

        store.calls.reset()
        assert list(iter(store.values())) == [1, 2, 3]
        assert store.calls.counts == {"iter": 1, "getitem": 3}

    def test_membership_in_each_view(self) -> None:
        store = ContainsCountingMapping({"a": 1, "b": 2, "c": 3})

        assert "b" in store.keys()
        assert store.calls.counts == {"contains": 1}

        store.calls.reset()
        assert ("b", 2) in store.items()
        assert ("b", 3) not in store.items()
        assert store.calls.counts == {"getitem": 2}

        store.calls.reset()
        assert 2 in store.values()
        assert store.calls.counts == {"iter": 1, "getitem": 2}, "stops at the match"

        store.calls.reset()
        assert 9 not in store.values()
        assert store.calls.counts == {"iter": 1, "getitem": 3}

    def test_set_operators_build_plain_sets(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2})

        keys = store.keys() & {"a", "z"}
        items = store.items() | {("c", 3)}

        assert type(keys) is set and keys == {"a"}
        assert type(items) is set and items == {("a", 1), ("b", 2), ("c", 3)}


class TestMutableMappingMixins:
    """`pop()` | get + del; `popitem()` | `__iter__` + get + del; `clear()` |
    n `popitem()`, O(n·(n + d)) over a dict; `update()` | one `__setitem__` per
    item; `setdefault()` | get, then set on a miss."""

    SMALL = 4_000
    LARGE = 32_000

    def test_pop_is_one_read_and_one_delete(self) -> None:
        store = RecordingMapping({"a": 1})

        assert store.pop("a") == 1
        assert store.calls.counts == {"getitem": 1, "delitem": 1}

        store.calls.reset()
        assert store.pop("z", 0) == 0
        assert store.calls.counts == {"getitem": 1}
        with pytest.raises(KeyError):
            store.pop("z")

    def test_popitem_takes_the_first_key_of_a_fresh_iterator(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2})

        assert store.popitem() == ("a", 1)

        assert store.calls.counts == {"iter": 1, "getitem": 1, "delitem": 1}

    def test_clear_starts_one_iterator_per_key_plus_one(self) -> None:
        store = RecordingMapping({"a": 1, "b": 2, "c": 3})

        store.clear()

        assert store._data == {}
        assert store.calls.counts == {"iter": 4, "getitem": 3, "delitem": 3}

    @pytest.mark.timing
    def test_clear_over_a_dict_grows_faster_than_the_dict(self) -> None:
        def build(size: int) -> RecordingMapping:
            return RecordingMapping({str(index): index for index in range(size)})

        small_ns = best_clear_ns(build, self.SMALL)
        large_ns = best_clear_ns(build, self.LARGE)

        assert large_ns > small_ns * 20, (
            f"clear() on {self.LARGE} keys took {large_ns / 1e6:.1f} ms, on {self.SMALL} "
            f"{small_ns / 1e6:.1f} ms; a linear clear would be near 8x"
        )

    def test_update_writes_once_per_item_from_every_source(self) -> None:
        store = RecordingMapping()
        other = RecordingMapping({"a": 1, "b": 2})

        store.update(other)
        assert store.calls.counts == {"setitem": 2}
        assert other.calls.counts == {"iter": 1, "getitem": 2}

        class HasKeys:
            def keys(self) -> list[str]:
                return ["c", "d"]

            def __getitem__(self, key: str) -> int:
                return 0

        store.calls.reset()
        store.update(HasKeys())  # pyright: ignore[reportArgumentType, reportCallIssue]
        assert store.calls.counts == {"setitem": 2}

        store.calls.reset()
        store.update([("e", 5)], f=6)
        assert store.calls.counts == {"setitem": 2}
        assert store._data == {"a": 1, "b": 2, "c": 0, "d": 0, "e": 5, "f": 6}

    def test_setdefault_reads_then_writes_on_a_miss(self) -> None:
        store = RecordingMapping({"a": 1})

        assert store.setdefault("a", 9) == 1
        assert store.calls.counts == {"getitem": 1}

        store.calls.reset()
        assert store.setdefault("b", 9) == 9
        assert store.calls.counts == {"getitem": 1, "setitem": 1}


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
    """Each block runs in its own subprocess, so the ABC caches and registries
    it touches cannot leak between blocks, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert seq.reads == 5" in s)
        mutated = source.replace("assert seq.reads == 5", "assert seq.reads == 6", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
