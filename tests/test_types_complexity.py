"""Tests for docs/stdlib/types.md.

The page prices the module's utilities and constructors; the type names are
attribute reads. Most claims are settled by observation - identity shows what
is shared rather than copied, a counting `__eq__` or a counting mapping shows
how much work a comparison or a forwarded lookup does, and recorded events
show the order `new_class()` runs its steps in. Growth is settled by traced
allocation, which separates the shapes by orders of magnitude, and by timing
only where allocation cannot separate them.

Measurement scope:

* The type names are asserted to be `type()` of an ordinary object each, and
  the two documented aliases to be the same object. `UnionType` is asserted to
  be `typing.Union` on 3.14+ and not before, and `CapsuleType` the type of
  `_socket.CAPI` on 3.13+.
* `isinstance(obj, types.FunctionType)` is timed on an instance whose MRO has
  3,001 entries against a plain `object()`; the deep miss costs more than 5x
  (x45 on 3.14, x31 on 3.10 locally).
* `FunctionType()` is asserted to share its code, globals, defaults and
  closure by identity, and to peak under 2 KB with 20,000 closure cells; a
  timing test puts 20,000 cells over 10x one cell (x157 on 3.14).
  `MethodType` binds by identity; `ModuleType()` leaves `sys.modules` alone
  and holds the five module dunders only; `TracebackType()` links onto the
  traceback it is given; `GenericAlias()` keeps a 100,000-element argument
  tuple by identity and peaks under 1 KB.
* `SimpleNamespace(**kwargs)` peaks over 100x higher for 100,000 entries than
  for 10, and a later change to the source dict does not reach it. On 3.13+
  the positional form peaks over 1 MB for a 100,000-entry dict, so it copies
  even a dict, and `copy.replace()` leaves the original alone and peaks over
  100x higher for 100,000 entries than for 10, and for 100,000 changes than
  for 10. `vars(ns)` is
  `ns.__dict__` by identity and peaks under 1 KB over 100,000 entries.
  Equality of two 10,000-entry namespaces makes exactly 10,000 value
  comparisons and peaks under 1 KB; `repr()` calls each value's `repr()` once.
* `MappingProxyType()` peaks under 1 KB over 100,000 entries, as do its
  `keys()`, `values()`, `items()`, `iter()` and `reversed()`; the views are
  asserted live by a later insertion. Over a counting mapping, `proxy[key]`,
  `key in proxy` and `len(proxy)` make one call each. `copy()` is a `dict`
  peaking over 1 MB for 100,000 entries; `|` is a `dict` on either side, and
  its peak grows over 100x when either operand grows from 10 to 100,000
  entries. `|=` raises `TypeError`, and a list or a tuple is rejected.
  Equality with a 10,000-entry dict makes exactly 10,000 value comparisons.
* `new_class()` is observed to call `__prepare__`, the body and the
  metaclass once each, in that order, with the prepared namespace, and to
  store `__orig_bases__` only when `resolve_bases()` changed the bases. Its
  peak grows more than 20x from 10 to 10,000 namespace entries. A direct
  `type()` call with the same base is observed to pick the same metaclass
  without calling its `__prepare__`, and to reject a `list[int]` base.
  `prepare_class()` peaks under 2 KB over 100,000 bases and a timing test
  puts 100x the bases over 20x the time (x93 on 3.14); it is asserted to copy
  `kwds`, drop the metaclass from the copy, pick the most derived metaclass
  and raise on a conflict. `resolve_bases()` returns a 100,000-base tuple by
  identity yet peaks over 500 KB, and calls each `__mro_entries__` once with
  the whole tuple. Timing tests put 30,000 bases that each expand to two, and
  30,000 that each resolve to none, over 100x the time of 1,000 (x276 to x673
  locally on 3.10 and 3.14), where a linear pass would give 30x and a
  quadratic one 900x. `get_original_bases()` returns the stored
  tuple by identity on 3.12+.
* `coroutine()` returns a generator function itself with a new, flagged code
  object, a coroutine function itself with its code untouched, and wraps
  anything else. Its peak for a 10,000-statement generator function is over
  100x that for a 10-statement one on 3.11+ (327 KB against 522 bytes on
  3.14), and under 4x on 3.10, which shares the bytecode (384 bytes against
  800). `DynamicClassAttribute` is observed to answer from `fget` on an
  instance and from the metaclass's `__getattr__` on the class, and to
  return itself on the class when the getter is abstract.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(1) type-name rows are attribute reads; nothing is measured.
* `new_class()` is varied in namespace entries only, not in bases. That the
  body, the metaclass and the MRO cost what they cost in a `class` statement
  is read from Lib/types.py, which runs the same resolve, prepare, body and
  metaclass steps as `builtins.__build_class__`.
* Class keyword arguments, key hashing and key and value comparison counting
  as O(1) are cost-model assumptions; the equality tests count comparisons,
  not their cost. That `resolve_bases()` stays linear when every
  `__mro_entries__` returns exactly one base is read from Lib/types.py, where
  an equal-length slice assignment moves nothing; it is not timed.
* Average-case O(1) for namespace attribute access and proxy lookups is the
  dict's; it is not timed here. `coroutine()` is measured in space only.
* `DynamicClassAttribute.getter()`, `.setter()` and `.deleter()`,
  `FunctionType`'s `kwdefaults` argument (3.13+) and `hash(proxy)` (3.12+)
  are not on the page. Nor are the attributes and methods of the objects the
  type names describe - code, frame, generator and coroutine members - which
  the API audit lists for classification only.
"""

from __future__ import annotations

import abc
import copy
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
import typing
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "types.md"
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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingEq:
    """A value that counts how often it is compared for equality."""

    compared = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        CountingEq.compared += 1
        return isinstance(other, CountingEq) and other.value == self.value

    def __hash__(self) -> int:
        return hash(self.value)


class CountingMapping(Mapping[str, int]):
    """A mapping that records every protocol call made on it."""

    def __init__(self, data: dict[str, int]) -> None:
        self._data = data
        self.calls: list[str] = []

    def __getitem__(self, key: str) -> int:
        self.calls.append("getitem")
        return self._data[key]

    def __contains__(self, key: object) -> bool:
        self.calls.append("contains")
        return key in self._data

    def __len__(self) -> int:
        self.calls.append("len")
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        self.calls.append("iter")
        return iter(self._data)


def entries(count: int) -> dict[str, int]:
    return {f"k{index}": index for index in range(count)}


class TestTypeNames:
    """Type names | O(1) | O(1): each name is the type an ordinary object
    already has, and the documented aliases are the same object."""

    def test_each_name_is_the_type_of_its_object(self) -> None:
        def plain() -> None:
            pass

        def generator() -> Iterator[int]:
            yield 1

        async def coroutine_function() -> None:
            pass

        async def async_generator() -> typing.AsyncIterator[int]:
            yield 1

        class Slotted:
            __slots__ = ("field",)

            def method(self) -> None:
                pass

        coroutine = coroutine_function()
        try:
            pairs: list[tuple[Any, Any]] = [
                (plain, types.FunctionType),
                (plain.__code__, types.CodeType),
                (Slotted().method, types.MethodType),
                (generator(), types.GeneratorType),
                (coroutine, types.CoroutineType),
                (async_generator(), types.AsyncGeneratorType),
                (len, types.BuiltinFunctionType),
                ([].append, types.BuiltinMethodType),
                (object.__init__, types.WrapperDescriptorType),
                (object().__str__, types.MethodWrapperType),
                (str.join, types.MethodDescriptorType),
                (dict.__dict__["fromkeys"], types.ClassMethodDescriptorType),
                (types.FunctionType.__code__, types.GetSetDescriptorType),
                (Slotted.__dict__["field"], types.MemberDescriptorType),
                (sys, types.ModuleType),
                (sys._getframe(), types.FrameType),  # noqa: SLF001
                (None, types.NoneType),
                (..., types.EllipsisType),
                (NotImplemented, types.NotImplementedType),
                (list[int], types.GenericAlias),
                (int | str, types.UnionType),
            ]
            for obj, expected in pairs:
                assert type(obj) is expected, (obj, expected)
        finally:
            coroutine.close()

    def test_cell_and_traceback_types(self) -> None:
        value = 1

        def closure() -> int:
            return value

        assert closure.__closure__ is not None
        assert type(closure.__closure__[0]) is types.CellType
        try:
            raise ValueError
        except ValueError as error:
            assert type(error.__traceback__) is types.TracebackType

    def test_the_documented_aliases_are_one_type(self) -> None:
        assert types.LambdaType is types.FunctionType
        assert types.BuiltinMethodType is types.BuiltinFunctionType

    def test_a_c_function_is_not_a_function_type(self) -> None:
        assert callable(len)
        assert not isinstance(len, types.FunctionType)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_capsule_type(self) -> None:
        import _socket

        assert isinstance(_socket.CAPI, types.CapsuleType)  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="changed in 3.14")
    def test_union_type_is_typing_union_from_314(self) -> None:
        assert types.UnionType is typing.Union  # type: ignore[comparison-overlap]
        assert isinstance(typing.Union[int, str], types.UnionType)  # noqa: UP007

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="changed in 3.14")
    def test_union_type_is_its_own_type_before_314(self) -> None:
        assert types.UnionType is not typing.Union  # type: ignore[comparison-overlap]
        assert not isinstance(typing.Union[int, str], types.UnionType)  # noqa: UP007


class TestIsinstanceWalksTheMro:
    """`isinstance(obj, types.X)` | O(d) | O(1): an exact type match is one
    comparison; otherwise the check walks `type(obj).__mro__`."""

    @staticmethod
    def chain(depth: int) -> object:
        cls: type = object
        for index in range(depth):
            cls = type(f"C{index}", (cls,), {})
        return cls()

    @pytest.mark.timing
    def test_a_miss_costs_the_mro_length(self) -> None:
        deep = self.chain(3_000)
        shallow = object()
        assert len(type(deep).__mro__) == 3_001

        deep_ns = best_ns(lambda: isinstance(deep, types.FunctionType), inner=2_000)
        shallow_ns = best_ns(lambda: isinstance(shallow, types.FunctionType), inner=2_000)
        ratio = deep_ns / shallow_ns

        assert ratio > 5, f"3,001-entry MRO against 1: {deep_ns:.0f}ns vs {shallow_ns:.0f}ns"


class TestConstructors:
    """`FunctionType` | O(c) | O(1), and `MethodType`, `ModuleType`,
    `TracebackType`, `GenericAlias` | O(1) | O(1): each keeps references to
    what it is given rather than copying it."""

    @staticmethod
    def closure_of(cells: int) -> types.FunctionType:
        names = [f"v{index}" for index in range(cells)]
        source = (
            "def outer():\n"
            + "".join(f"    {name} = 1\n" for name in names)
            + "    def inner():\n"
            + f"        return ({', '.join(names)},)\n"
            + "    return inner\n"
        )
        namespace: dict[str, Any] = {}
        exec(source, namespace)  # noqa: S102
        inner = namespace["outer"]()
        assert len(inner.__closure__) == cells
        return inner

    def test_a_function_shares_code_globals_defaults_and_closure(self) -> None:
        inner = self.closure_of(3)
        defaults = (1, 2)

        clone = types.FunctionType(
            inner.__code__, inner.__globals__, "clone", defaults, inner.__closure__
        )

        assert clone.__code__ is inner.__code__
        assert clone.__globals__ is inner.__globals__
        assert clone.__defaults__ is defaults
        assert clone.__closure__ is inner.__closure__
        assert clone.__name__ == "clone"

    def test_a_function_allocates_nothing_for_its_closure(self) -> None:
        inner = self.closure_of(20_000)
        build = types.FunctionType
        build(inner.__code__, {}, None, None, inner.__closure__)

        peak = peak_bytes(lambda: build(inner.__code__, {}, None, None, inner.__closure__))

        assert peak < 2_000, f"a 20,000-cell function allocated {peak} bytes"

    @pytest.mark.timing
    def test_each_closure_cell_is_checked(self) -> None:
        wide = self.closure_of(20_000)
        narrow = self.closure_of(1)
        build = types.FunctionType

        wide_ns = best_ns(lambda: build(wide.__code__, {}, None, None, wide.__closure__), inner=20)
        narrow_ns = best_ns(
            lambda: build(narrow.__code__, {}, None, None, narrow.__closure__), inner=20
        )
        ratio = wide_ns / narrow_ns

        assert ratio > 10, f"20,000 cells against 1: {wide_ns:.0f}ns vs {narrow_ns:.0f}ns"

    def test_a_method_binds_without_copying(self) -> None:
        def describe(self: object) -> object:
            return self

        target = object()
        bound = types.MethodType(describe, target)

        assert bound.__func__ is describe
        assert bound.__self__ is target
        assert bound() is target

    def test_a_module_is_empty_and_unregistered(self) -> None:
        name = "_types_page_probe"
        assert name not in sys.modules

        module = types.ModuleType(name, "doc")

        assert name not in sys.modules
        assert set(vars(module)) == {"__name__", "__doc__", "__package__", "__loader__", "__spec__"}
        assert module.__doc__ == "doc"

    def test_a_traceback_links_onto_the_chain_it_is_given(self) -> None:
        try:
            raise ValueError
        except ValueError as error:
            existing = error.__traceback__
        assert existing is not None

        linked = types.TracebackType(
            existing, existing.tb_frame, existing.tb_lasti, existing.tb_lineno
        )

        assert linked.tb_next is existing

    def test_a_generic_alias_keeps_its_argument_tuple(self) -> None:
        arguments = (int,) * 100_000

        alias = types.GenericAlias(tuple, arguments)
        peak = peak_bytes(lambda: types.GenericAlias(tuple, arguments))

        assert alias.__args__ is arguments
        assert peak < 1_000, f"a 100,000-argument alias allocated {peak} bytes"


class TestSimpleNamespace:
    """`SimpleNamespace` | O(n) | O(n) to build, O(1) per attribute, and
    `vars(ns)` | O(1) | O(1): it returns the namespace's own dict."""

    def test_construction_copies_the_entries(self) -> None:
        source = {"a": 1}

        namespace = types.SimpleNamespace(**source)
        source["a"] = 2

        assert namespace.a == 1

    def test_construction_space_grows_with_the_entries(self) -> None:
        small, large = entries(10), entries(100_000)

        small_peak = peak_bytes(lambda: types.SimpleNamespace(**small))
        large_peak = peak_bytes(lambda: types.SimpleNamespace(**large))

        assert large_peak > 1_000_000, f"100,000 entries peaked at {large_peak} bytes"
        assert large_peak > small_peak * 100, (small_peak, large_peak)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_the_positional_form_copies_even_a_dict(self) -> None:
        source = entries(100_000)

        namespace = types.SimpleNamespace(source)  # type: ignore[call-arg]
        peak = peak_bytes(lambda: types.SimpleNamespace(source))  # type: ignore[call-arg]

        assert vars(namespace) is not source
        assert vars(namespace) == source
        assert peak > 1_000_000, f"a 100,000-entry dict argument peaked at {peak} bytes"
        assert types.SimpleNamespace([("a", 1)], b=2) == types.SimpleNamespace(a=1, b=2)  # type: ignore[call-arg]

    def test_vars_is_the_namespace_s_own_dict(self) -> None:
        namespace = types.SimpleNamespace(**entries(100_000))

        peak = peak_bytes(lambda: vars(namespace))

        assert vars(namespace) is namespace.__dict__
        assert peak < 1_000, f"vars() of 100,000 entries allocated {peak} bytes"
        vars(namespace)["added"] = 1
        assert namespace.added == 1

    def test_attributes_are_set_read_and_deleted(self) -> None:
        namespace = types.SimpleNamespace(a=1)

        namespace.b = 2
        del namespace.a

        assert vars(namespace) == {"b": 2}

    def test_equality_compares_each_value_and_allocates_nothing(self) -> None:
        count = 10_000
        left = types.SimpleNamespace(**{f"k{i}": CountingEq(i) for i in range(count)})
        right = types.SimpleNamespace(**{f"k{i}": CountingEq(i) for i in range(count)})
        CountingEq.compared = 0

        assert left == right
        assert CountingEq.compared == count
        assert peak_bytes(lambda: left == right) < 1_000

    def test_a_namespace_never_equals_a_dict_of_its_entries(self) -> None:
        assert types.SimpleNamespace(a=1) != {"a": 1}
        assert {"a": 1} != types.SimpleNamespace(a=1)

    def test_repr_renders_every_entry(self) -> None:
        calls: list[int] = []

        class Recorded:
            def __repr__(self) -> str:
                calls.append(1)
                return "r"

        namespace = types.SimpleNamespace(**{f"k{i}": Recorded() for i in range(1_000)})

        text = repr(namespace)

        assert len(calls) == 1_000
        assert text.startswith("namespace(k0=r, k1=r")

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_copy_replace_builds_a_new_namespace(self) -> None:
        small = types.SimpleNamespace(**entries(10))
        large = types.SimpleNamespace(**entries(100_000))
        replace = copy.replace  # type: ignore[attr-defined]

        changed = replace(large, k0=-1, extra=1)
        small_peak = peak_bytes(lambda: replace(small, k0=-1))
        large_peak = peak_bytes(lambda: replace(large, k0=-1))

        assert changed is not large and large.k0 == 0
        assert changed.k0 == -1 and changed.extra == 1
        assert large_peak > small_peak * 100, (small_peak, large_peak)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_copy_replace_space_grows_with_the_changes(self) -> None:
        base = types.SimpleNamespace(**entries(10))
        few = {f"new{i}": i for i in range(10)}
        many = {f"new{i}": i for i in range(100_000)}
        replace = copy.replace  # type: ignore[attr-defined]

        few_peak = peak_bytes(lambda: replace(base, **few))
        many_peak = peak_bytes(lambda: replace(base, **many))

        assert len(vars(replace(base, **many))) == 100_010
        assert many_peak > few_peak * 100, (few_peak, many_peak)


class TestMappingProxyIsAView:
    """`MappingProxyType(mapping)` | O(1) | O(1): no copy, later changes show
    through; lookups are forwarded, and only `copy()` and `|` build a dict."""

    def test_construction_copies_nothing(self) -> None:
        data = entries(100_000)

        peak = peak_bytes(lambda: types.MappingProxyType(data))

        assert peak < 1_000, f"wrapping 100,000 entries allocated {peak} bytes"

    def test_later_changes_show_through(self) -> None:
        data = {"a": 1}
        proxy = types.MappingProxyType(data)

        data["b"] = 2

        assert proxy["b"] == 2
        assert len(proxy) == 2
        assert list(reversed(proxy)) == ["b", "a"]

    def test_a_list_or_tuple_is_rejected(self) -> None:
        for bad in ([("a", 1)], (("a", 1),)):
            with pytest.raises(TypeError, match="must be a mapping"):
                types.MappingProxyType(bad)  # type: ignore[arg-type]

    def test_each_lookup_is_one_call_on_the_mapping(self) -> None:
        mapping = CountingMapping({"a": 1})
        proxy = types.MappingProxyType(mapping)

        assert proxy["a"] == 1
        assert "a" in proxy
        assert len(proxy) == 1

        assert mapping.calls == ["getitem", "contains", "len"]

    def test_get_does_not_raise(self) -> None:
        proxy = types.MappingProxyType({"a": 1})

        assert proxy.get("a") == 1
        assert proxy.get("z") is None
        assert proxy.get("z", 0) == 0

    def test_views_are_the_mapping_s_own(self) -> None:
        data = entries(100_000)
        proxy = types.MappingProxyType(data)

        keys = proxy.keys()
        values, items = proxy.values(), proxy.items()
        peaks = [peak_bytes(method) for method in (proxy.keys, proxy.values, proxy.items)]
        data["added"] = -1

        assert "added" in keys and -1 in values and ("added", -1) in items
        assert type(keys) is type(data.keys())
        assert max(peaks) < 1_000, f"views of 100,000 entries allocated {peaks} bytes"

    def test_iteration_holds_no_copy(self) -> None:
        data = entries(100_000)
        proxy = types.MappingProxyType(data)

        peaks = [peak_bytes(lambda: iter(proxy)), peak_bytes(lambda: reversed(proxy))]

        assert max(peaks) < 1_000, peaks
        assert sum(1 for _ in proxy) == len(data)

    def test_copy_is_a_writable_dict(self) -> None:
        data = entries(100_000)
        proxy = types.MappingProxyType(data)

        snapshot = proxy.copy()
        peak = peak_bytes(proxy.copy)
        snapshot["added"] = 1

        assert type(snapshot) is dict
        assert "added" not in proxy
        assert peak > 1_000_000, f"copying 100,000 entries peaked at {peak} bytes"

    def test_union_builds_a_new_dict_on_either_side(self) -> None:
        proxy = types.MappingProxyType({"a": 1})

        assert type(proxy | {"b": 2}) is dict
        assert type({"b": 2} | proxy) is dict
        assert proxy | {"a": 2} == {"a": 2}
        assert "b" not in proxy

    def test_in_place_union_raises(self) -> None:
        proxy = types.MappingProxyType({"a": 1})

        with pytest.raises(TypeError, match="use '\\|' instead"):
            proxy |= {"b": 2}  # type: ignore[misc]

    def test_union_space_grows_with_both_operands(self) -> None:
        small, large = entries(10), entries(100_000)
        small_proxy, large_proxy = types.MappingProxyType(small), types.MappingProxyType(large)

        peaks = {
            "small|small": peak_bytes(lambda: small_proxy | small),
            "large|small": peak_bytes(lambda: large_proxy | small),
            "small|large": peak_bytes(lambda: small_proxy | large),
        }

        assert peaks["large|small"] > peaks["small|small"] * 100, peaks
        assert peaks["small|large"] > peaks["small|small"] * 100, peaks

    def test_equality_is_the_mapping_s_and_allocates_nothing(self) -> None:
        count = 10_000
        left = types.MappingProxyType({f"k{i}": CountingEq(i) for i in range(count)})
        right = {f"k{i}": CountingEq(i) for i in range(count)}
        CountingEq.compared = 0

        assert left == right
        assert CountingEq.compared == count
        assert peak_bytes(lambda: left == right) < 1_000


class TestDynamicClassCreation:
    """`new_class` | O(b + n), `prepare_class` | O(b) | O(1), `resolve_bases` |
    O(b) | O(b), and `get_original_bases` | O(1) | O(1)."""

    def test_new_class_runs_the_body_once_on_the_prepared_namespace(self) -> None:
        events: list[str] = []

        class Recorder(dict[str, Any]):
            pass

        class Meta(type):
            @classmethod
            def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwds: Any) -> Recorder:
                events.append(f"prepare {sorted(kwds)}")
                return Recorder()

            def __new__(
                mcs, name: str, bases: tuple[type, ...], ns: dict[str, Any], **kwds: Any
            ) -> Meta:
                assert type(ns) is Recorder
                events.append("new")
                return super().__new__(mcs, name, bases, dict(ns))

            def __init__(cls, *args: Any, **kwds: Any) -> None:
                super().__init__(*args)

        def body(ns: dict[str, Any]) -> None:
            assert type(ns) is Recorder
            events.append("body")
            ns["x"] = 1

        created = types.new_class("Built", (), {"metaclass": Meta, "flag": True}, body)

        assert events == ["prepare ['flag']", "body", "new"]
        assert created.x == 1  # type: ignore[attr-defined]

    def test_new_class_resolves_aliases_and_keeps_the_originals(self) -> None:
        resolved = types.new_class("Scores", (list[int],))
        plain = types.new_class("Plain", (int,))

        assert resolved.__bases__ == (list,)
        assert resolved.__dict__["__orig_bases__"] == (list[int],)
        assert "__orig_bases__" not in plain.__dict__

    def test_type_rejects_an_alias_base(self) -> None:
        with pytest.raises(TypeError, match="new_class"):
            type("Scores", (list[int],), {})

    def test_type_skips_prepare_where_new_class_calls_it(self) -> None:
        prepared: list[str] = []

        class Meta(type):
            @classmethod
            def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwds: Any) -> dict[str, Any]:
                prepared.append(name)
                return {}

        base = Meta("Base", (), {})
        prepared.clear()

        direct = type("Direct", (base,), {})
        built = types.new_class("Built", (base,))

        assert type(direct) is Meta and type(built) is Meta
        assert prepared == ["Built"]

    def test_new_class_space_grows_with_the_namespace(self) -> None:
        def build(size: int) -> Callable[[], type]:
            names = [f"a{index}" for index in range(size)]
            return lambda: types.new_class(
                "Wide", (), None, lambda ns: ns.update(dict.fromkeys(names))
            )

        small, large = build(10), build(10_000)
        small()  # warm
        large()

        peaks = [peak_bytes(small), peak_bytes(large)]

        assert peaks[1] > peaks[0] * 20, f"10 against 10,000 namespace entries: {peaks}"

    def test_prepare_class_copies_kwds_and_pops_the_metaclass(self) -> None:
        kwds = {"metaclass": type, "flag": True}

        meta, namespace, rest = types.prepare_class("X", (), kwds)

        assert meta is type and namespace == {}
        assert rest == {"flag": True}
        assert kwds == {"metaclass": type, "flag": True}

    def test_prepare_class_picks_the_most_derived_metaclass(self) -> None:
        class Meta(type):
            pass

        class Base(metaclass=Meta):
            pass

        class Other(type):
            pass

        class Unrelated(metaclass=Other):
            pass

        assert types.prepare_class("X", (Base,))[0] is Meta
        assert types.prepare_class("X", (Base,), {"metaclass": type})[0] is Meta
        with pytest.raises(TypeError, match="metaclass conflict"):
            types.prepare_class("X", (Base, Unrelated))

    def test_prepare_class_allocates_nothing_per_base(self) -> None:
        bases = (object,) * 100_000
        types.prepare_class("X", bases)

        peak = peak_bytes(lambda: types.prepare_class("X", bases))

        assert peak < 2_000, f"100,000 bases allocated {peak} bytes"

    @pytest.mark.timing
    def test_prepare_class_visits_each_base(self) -> None:
        few, many = (object,) * 1_000, (object,) * 100_000

        few_ns = best_ns(lambda: types.prepare_class("X", few), inner=3)
        many_ns = best_ns(lambda: types.prepare_class("X", many), inner=3)
        ratio = many_ns / few_ns

        assert ratio > 20, f"100x the bases cost x{ratio:.1f} ({few_ns:.0f}ns to {many_ns:.0f}ns)"

    def test_resolve_bases_returns_the_same_tuple_when_nothing_changes(self) -> None:
        bases = (int,) * 100_000

        peak = peak_bytes(lambda: types.resolve_bases(bases))

        assert types.resolve_bases(bases) is bases
        assert peak > 500_000, f"100,000 bases peaked at {peak} bytes; the row claims O(b)"

    def test_resolve_bases_calls_each_mro_entries_once_with_all_bases(self) -> None:
        seen: list[tuple[object, ...]] = []

        class Entry:
            def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[type, ...]:
                seen.append(bases)
                return (int, str)

        first, second = Entry(), Entry()
        bases = (first, float, second)

        assert types.resolve_bases(bases) == (int, str, float, int, str)
        assert seen == [bases, bases]

    @pytest.mark.timing
    @pytest.mark.parametrize("replacement", [(int, str), ()], ids=["two", "none"])
    def test_each_base_not_replaced_by_one_costs_another_pass(
        self, replacement: tuple[type, ...]
    ) -> None:
        class Entry:
            def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[type, ...]:
                return replacement

        few = tuple(Entry() for _ in range(1_000))
        many = tuple(Entry() for _ in range(30_000))

        assert len(types.resolve_bases(many)) == 30_000 * len(replacement)
        few_ns = best_ns(lambda: types.resolve_bases(few), repeats=3)
        many_ns = best_ns(lambda: types.resolve_bases(many), repeats=3)
        ratio = many_ns / few_ns

        assert ratio > 100, f"30x the replaced bases cost x{ratio:.0f}; linear would be x30"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_get_original_bases_returns_the_stored_tuple(self) -> None:
        resolved = types.new_class("Scores", (list[int],))
        get_original_bases = types.get_original_bases  # type: ignore[attr-defined]

        assert get_original_bases(resolved) is resolved.__dict__["__orig_bases__"]
        assert get_original_bases(int) is int.__bases__
        with pytest.raises(TypeError, match="Expected an instance of type"):
            get_original_bases(1)


class TestCoroutineAdapters:
    """`coroutine(gen_func)` | O(k) | O(k): the same function comes back with a
    flagged copy of its code; `DynamicClassAttribute` | O(1) | O(1)."""

    @staticmethod
    def generator_function(statements: int) -> types.FunctionType:
        source = (
            "def generate():\n"
            + "".join(f"    x{index} = {index}\n" for index in range(statements))
            + "    yield 1\n"
        )
        namespace: dict[str, Any] = {}
        exec(source, namespace)  # noqa: S102
        return namespace["generate"]

    def test_a_generator_function_comes_back_itself_with_new_code(self) -> None:
        function = self.generator_function(3)
        original = function.__code__

        marked = types.coroutine(function)

        assert marked is function
        assert function.__code__ is not original
        assert function.__code__.co_flags & 0x100  # CO_ITERABLE_COROUTINE

    def test_a_coroutine_function_comes_back_unchanged(self) -> None:
        async def native() -> None:
            pass

        code = native.__code__

        assert types.coroutine(native) is native
        assert native.__code__ is code

    def test_any_other_callable_is_wrapped(self) -> None:
        def factory() -> Iterator[int]:
            return iter([])

        wrapped = types.coroutine(factory)

        assert wrapped is not factory
        assert wrapped.__wrapped__ is factory  # type: ignore[attr-defined]

    def test_the_space_follows_the_code_size(self) -> None:
        def peak_for(statements: int) -> int:
            functions = iter([self.generator_function(statements) for _ in range(3)])
            types.coroutine(next(functions))  # warm
            return peak_bytes(lambda: types.coroutine(next(functions)))

        small, large = peak_for(10), peak_for(10_000)

        if sys.version_info >= (3, 11):
            assert large > small * 100, f"10 against 10,000 statements: {small}, {large}"
        else:
            assert large < small * 4, f"3.10 shares the bytecode: {small}, {large}"

    def test_dynamic_class_attribute_routes_class_access(self) -> None:
        class Meta(type):
            def __getattr__(cls, name: str) -> str:
                return f"class {name}"

        class Holder(metaclass=Meta):
            @types.DynamicClassAttribute
            def value(self) -> str:
                return "instance"

        assert Holder().value == "instance"
        assert Holder.value == "class value"  # type: ignore[attr-defined]

    def test_an_abstract_getter_returns_the_descriptor_on_the_class(self) -> None:
        @abc.abstractmethod
        def value(self: object) -> str:
            return "instance"

        descriptor = types.DynamicClassAttribute(value)

        class Holder:
            attribute = descriptor

        assert Holder.attribute is descriptor


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
        line, source = next((n, s) for n, s in _blocks() if "assert ns.port == 8080" in s)
        mutated = source.replace("assert ns.port == 8080", "assert ns.port == 9090", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
