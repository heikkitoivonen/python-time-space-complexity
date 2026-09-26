"""Tests for docs/stdlib/typing.md.

The page prices hints where they are built and read: a subscription through a
bounded cache, a union's flattening, a runtime protocol check, an annotation
evaluated at definition time or on first read, and `get_type_hints()`
resolving an object's hints on every call. Almost every claim is settled by
observation - identity, a counting `__hash__`, `__eq__` or `__repr__`, a
recording wrapper around the helper an operation calls, or a probe function
called from inside an annotation - so nothing here needs a timing tolerance.
Space claims are settled by traced allocation at sizes three orders of
magnitude apart.

Measurement scope:

* Subscription caching: `List[int]` and `Dict[str, int]` are the same object
  on a repeat, `list[int]` is not, and `List[int]` is a different object from
  `list[int]`. After 1,000 other `Dict[...]` subscriptions through the same
  cache, `List[int]` is rebuilt: equal, not identical.
* `Tuple[...]` at 10 and 100 arguments: a hit through a freshly built
  argument tuple hashes each argument once. From 3.14 a tuple's hash is kept
  on the tuple, so a hit through the very same tuple object hashes none;
  written-out subscriptions build a fresh tuple each time.
* `Literal[1, 2, 1]` keeps two values and `Annotated[int, 1, 1]` both
  metadata items.
* `Union[...]` at 10 and 100 distinct arguments, and the same doubled:
  hashes stay between p and 20p and comparisons under 20p. With every
  argument hashing to one value, comparisons reach p(p-1)/2, which is why the
  page's cost model treats hashing as O(1).
* `get_args()`: an ordinary alias returns the identical tuple on two calls;
  `Callable` at 10 and 10,000 parameters and `Annotated` at 10 and 10,000
  metadata items return a fresh result whose traced peak grows more than 20x.
* `get_type_hints()`: a string annotation calling a probe is evaluated on
  each of two calls. A class with one annotation and 10 against 10,000
  methods peaks more than 20x higher, which is the a term; a function with 10
  against 1,000 annotations peaks more than 20x higher, which is k.
* Definition time: an annotation calling a probe, compiled without this
  file's `__future__` import, on a function and on a class, calls it when
  the statement runs before 3.14 and from 3.14 not until `__annotations__`
  is read; two reads call it once in all.
* Runtime protocols: on 3.10 and 3.11 a check the class has already passed
  still calls `typing._get_protocol_attrs`, which returns all 40 members.
  From 3.12 that check makes no static attribute lookup on the instance,
  while a failing check makes at least one on each call. A data protocol of
  1 and 40 members reads every member of the instance on each check, and
  `issubclass()` against it raises `TypeError`.
* `runtime_checkable()` iterates each of 1 and 40 members once from 3.12.2
  and records the non-method ones; before that it records nothing.
  `get_protocol_members()` returns the five members of a five-member
  protocol. Defining a protocol of 10,000 members peaks more than 20x higher
  than one of 10, and from 3.12 the protocol keeps all 10,000 names.
* `ForwardRef()` at 10 and 10,000 characters calls `compile` on the string
  before 3.14 and not from 3.14, where a syntax error is not raised at
  construction. `evaluate_forward_ref()` on 3.14 visits each of 1 and 100
  arguments of the resolved type once, and runs caller code in the
  expression as written.
* `assert_never()` calls `repr()` on all 1,000 elements of a list while its
  message stays under 200 characters. `no_type_check()` on a class whose
  base defines 1,000 methods reads all 1,000 from 3.11 and none on 3.10.
  `get_overloads()` returns the registered variants and `clear_overloads()`
  empties them; `overload()` registers nothing on 3.10.
* A `type` statement evaluates its value on the first `__value__` read and
  not again (3.12+). `has_default()` answers without evaluating a lazy
  default (3.13+). The `evaluate_*` attributes exist exactly from 3.14.
* The rows that carry a version are checked against the running
  interpreter: each name exists from the version its row gives and not
  before.
* Every fenced Python block runs in its own subprocess, so the
  `from __future__ import annotations` block is the first statement of its
  file, and a mutated assertion in one block is asserted to fail.

Not settled here:

* `ForwardRef()` before 3.14 is priced as a call to `compile`, not as O(s)
  in its length: the parser's cost depends on the expression's grammar as
  well as its length, which is not varied. `evaluate_forward_ref()` and
  `__value__` evaluate caller code, whose cost is the e the rows name.
* The O(1) rows for markers, aliases, `cast`, `NewType`, `final`,
  `override` and `dataclass_transform` are read from Lib/typing.py in each
  released branch (3.10.19 to 3.14.2): each returns an existing object or
  sets a fixed number of attributes.
* The log factor of `no_type_check()` is `dir()`'s sort, read from source;
  only the count of names visited is observed.
* `clear_overloads()` being O(o) follows from clearing a dictionary of
  every registered variant; it is observed to empty the registry, not timed.
* Protocol inheritance depth, hint nesting depth, `Literal` over unhashable
  values, and `get_type_hints()` over more than one level of MRO are not
  varied.
* `typing.type_check_only` is listed in the official documentation but
  exists only in stub files, so no interpreter can inspect it.
"""

from __future__ import annotations

import builtins
import inspect
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
import typing
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    NamedTuple,
    NewType,
    Optional,
    Protocol,
    TypedDict,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
    runtime_checkable,
)

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "typing.md"
EXPECTED_BLOCKS = 9

# Documented, but absent from 3.10. Each row naming one must give its version.
ADDED_AFTER_310 = {
    "LiteralString": "3.11",
    "Never": "3.11",
    "NotRequired": "3.11",
    "Required": "3.11",
    "Self": "3.11",
    "TypeVarTuple": "3.11",
    "Unpack": "3.11",
    "assert_never": "3.11",
    "assert_type": "3.11",
    "clear_overloads": "3.11",
    "dataclass_transform": "3.11",
    "get_overloads": "3.11",
    "reveal_type": "3.11",
    "TypeAliasType": "3.12",
    "override": "3.12",
    "NoDefault": "3.13",
    "ReadOnly": "3.13",
    "TypeIs": "3.13",
    "get_protocol_members": "3.13",
    "is_protocol": "3.13",
    "evaluate_forward_ref": "3.14",
}


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def fresh_namespace(source: str, **names: Any) -> dict[str, Any]:
    """Run `source` without inheriting this file's `__future__` imports."""
    namespace: dict[str, Any] = dict(names)
    code = compile(textwrap.dedent(source), "<probe>", "exec", dont_inherit=True)
    exec(code, namespace)  # noqa: S102 - building the shape under test is the point
    return namespace


def protocol_of(members: int, *, data: bool = False) -> type:
    """A runtime-checkable protocol with `members` methods or data members."""
    names = [f"m{index}" for index in range(members)]
    if data:
        body: dict[str, object] = {"__annotations__": dict.fromkeys(names, int)}
    else:
        body = {"__annotations__": {}, **{name: (lambda self: None) for name in names}}
    bases: tuple[type, ...] = (Protocol,)  # type: ignore[assignment]
    return runtime_checkable(type("Wide", bases, body))


def record_static_lookups(monkeypatch: pytest.MonkeyPatch, target: object) -> list[str]:
    """From 3.12, record every static attribute lookup a protocol check makes on `target`."""
    visits: list[str] = []
    lookup_module = typing if hasattr(typing, "getattr_static") else inspect
    original = lookup_module.getattr_static  # type: ignore[attr-defined]

    def record(obj: object, name: str, *args: Any) -> Any:
        if obj is target:
            visits.append(name)
        return original(obj, name, *args)

    if hasattr(typing, "_lazy_load_getattr_static"):
        monkeypatch.setattr(typing, "_lazy_load_getattr_static", lambda: record)
    else:
        monkeypatch.setattr(lookup_module, "getattr_static", record)
    return visits


class TestVersionedRows:
    """Each row for a name added after 3.10 gives its version, and the version
    is the one the running interpreter agrees with."""

    def test_every_later_addition_carries_its_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        for name, version in sorted(ADDED_AFTER_310.items()):
            owning = [row for row in rows if f"typing.{name}" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert version in owning[0], f"the {name} row should say {version}+: {owning[0]}"

    def test_the_additions_match_this_interpreter(self) -> None:
        current = sys.version_info[:2]
        for name, version in ADDED_AFTER_310.items():
            introduced = tuple(int(part) for part in version.split("."))
            assert hasattr(typing, name) == (current >= introduced), f"{name} on {current}"

    def test_type_parameter_members_match_their_rows(self) -> None:
        type_var = typing.TypeVar("type_var")
        param_spec = typing.ParamSpec("param_spec")

        assert hasattr(type_var, "has_default") == (sys.version_info >= (3, 13))
        assert hasattr(param_spec, "has_default") == (sys.version_info >= (3, 13))
        for name in ("evaluate_bound", "evaluate_constraints", "evaluate_default"):
            assert hasattr(type_var, name) == (sys.version_info >= (3, 14)), name
        if sys.version_info >= (3, 12):
            alias = typing.TypeAliasType("Alias", int)  # type: ignore[attr-defined]
            assert hasattr(alias, "evaluate_value") == (sys.version_info >= (3, 14))


class TestSubscriptionIsCached:
    """`List[X]`, `Dict[K, V]` | O(1): a repeat returns the alias already
    built, the cache keeps only recent entries, and the builtin generics are
    not cached.

    `typing.List` and `list` are the two sides of this comparison, so neither
    may be rewritten into the other - see the per-file ruff ignore.
    """

    def test_the_same_parameters_give_the_same_object(self) -> None:
        assert typing.List[int] is typing.List[int]
        assert typing.Dict[str, int] is typing.Dict[str, int]
        assert typing.Dict[str, typing.List[int]] is typing.Dict[str, typing.List[int]]

    def test_different_parameters_do_not(self) -> None:
        assert typing.List[int] is not typing.List[str]

    def test_the_builtin_form_is_not_cached(self) -> None:
        assert list[int] is not list[int]
        assert list[int] == list[int]

    def test_the_two_forms_are_genuinely_different_objects(self) -> None:
        """So the contrast above is not comparing a thing with itself."""
        assert typing.List[int] is not list[int]

    def test_the_cache_keeps_only_recent_subscriptions(self) -> None:
        first = typing.List[int]
        for index in range(1_000):
            typing.Dict[str, type(f"C{index}", (), {})]  # noqa: B018 - filling the cache

        again = typing.List[int]

        assert again == first
        assert again is not first, "an alias survived 1,000 later subscriptions"


class TestVariableAritySubscriptions:
    """`Tuple[...]` and `Union[...]` | O(p): a hit still hashes the arguments,
    and a union deduplicates by hashing."""

    @pytest.mark.parametrize("count", [10, 100])
    def test_a_tuple_hit_hashes_each_argument(self, count: int) -> None:
        hashes = 0

        class Meta(type):
            def __hash__(cls) -> int:
                nonlocal hashes
                hashes += 1
                return type.__hash__(cls)

        params = tuple(Meta(f"T{i}", (), {}) for i in range(count))
        alias = typing.Tuple[params]
        hashes = 0
        assert typing.Tuple[params] is alias
        assert hashes == (0 if sys.version_info >= (3, 14) else count)
        fresh = tuple(list(params))  # noqa: C414 - force a distinct, unhashed tuple
        assert fresh == params and fresh is not params
        hashes = 0
        assert typing.Tuple[fresh] is alias
        assert hashes == count

    @pytest.mark.parametrize("count", [10, 100])
    @pytest.mark.parametrize("duplicates", [False, True])
    def test_a_union_uses_linear_hash_work(self, count: int, duplicates: bool) -> None:
        hashes = comparisons = 0

        class Meta(type):
            def __hash__(cls) -> int:
                nonlocal hashes
                hashes += 1
                return type.__hash__(cls)

            def __eq__(cls, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return cls is other

        params = tuple(Meta(f"T{i}", (), {}) for i in range(count))
        result = Union[params * (2 if duplicates else 1)]
        assert get_args(result) == params
        assert count <= hashes <= 20 * count, hashes
        assert comparisons < 20 * count, comparisons

    @pytest.mark.parametrize("count", [10, 100])
    def test_colliding_hashes_are_why_hashing_is_assumed_constant(self, count: int) -> None:
        comparisons = 0

        class Meta(type):
            def __hash__(cls) -> int:
                return 1

            def __eq__(cls, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return cls is other

        params = tuple(Meta(f"T{i}", (), {}) for i in range(count))
        assert get_args(Union[params]) == params
        assert comparisons >= count * (count - 1) // 2


class TestUnionNormalises:
    """Unions flatten and deduplicate their arguments; from 3.14 they are the
    `X | Y` object and are not cached."""

    def test_duplicates_are_dropped(self) -> None:
        assert Union[int, str, int] == Union[int, str]
        assert len(get_args(Union[int, str, int])) == 2

    def test_nested_unions_are_flattened(self) -> None:
        assert Union[int, Union[str, float]] == Union[int, str, float]
        assert len(get_args(Union[int, str | float])) == 3

    def test_optional_is_a_union_with_none(self) -> None:
        assert Optional[int] == Union[int, None]
        assert type(None) in get_args(Optional[int])

    def test_a_single_argument_collapses(self) -> None:
        assert Union[int] is int

    def test_literal_drops_duplicate_values(self) -> None:
        assert get_args(typing.Literal[1, 2, 1]) == (1, 2)
        assert get_args(typing.Annotated[int, 1, 1]) == (int, 1, 1)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="3.14 drops the union cache")
    def test_unions_are_cached_before_314(self) -> None:
        assert Union[int, str] is Union[int, str]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the change lands in 3.14")
    def test_from_314_a_union_is_the_pipe_form(self) -> None:
        assert Union[int, str] == int | str
        assert type(Union[int, str]) is type(int | str)
        assert Union[int, str] is not Union[int, str]


class TestTakingAliasesApart:
    """`get_origin` | O(1); `get_args` | O(1), O(p) for `Callable` and
    `Annotated`, which build their result on each call."""

    def test_an_ordinary_alias_hands_back_its_stored_tuple(self) -> None:
        alias = typing.Dict[str, int]

        assert get_args(alias) is get_args(alias)
        assert get_args(alias) == (str, int)
        assert get_origin(alias) is dict
        assert get_origin(int) is None
        assert get_args(int) == ()

    @pytest.mark.parametrize("kind", ["callable", "annotated"])
    def test_callable_and_annotated_rebuild_their_result(self, kind: str) -> None:
        peaks = []
        for count in (10, 10_000):
            alias = (
                typing.Callable[[int] * count, str]  # type: ignore[misc]
                if kind == "callable"
                else typing.Annotated[(int, *range(count))]
            )
            first = get_args(alias)
            peaks.append(peak_bytes(lambda alias=alias: get_args(alias)))
            second = get_args(alias)
            assert first == second and first is not second
            if kind == "callable":
                assert first[0] is not second[0]
                assert len(second[0]) == count
            else:
                assert len(second) == count + 1
        assert peaks[1] > peaks[0] * 20, peaks


class TestGetTypeHints:
    """`get_type_hints` | O(k) for a function, O(k + a) for a class: nothing
    is cached, and a class's namespaces are copied along the MRO."""

    def test_it_resolves_every_annotation(self) -> None:
        def transform(rows: typing.Dict[str, typing.List[int]], limit: int) -> typing.List[int]:
            return []

        hints = get_type_hints(transform)

        assert hints["limit"] is int
        assert hints["return"] == typing.List[int]
        assert hints["rows"] == typing.Dict[str, typing.List[int]]

    def test_a_class_merges_its_whole_mro(self) -> None:
        class Base:
            base_field: int

        class Derived(Base):
            own_field: str

        assert get_type_hints(Derived) == {"base_field": int, "own_field": str}

    def test_string_annotations_are_evaluated_on_every_call(self) -> None:
        calls: list[int] = []

        def probe() -> type:
            calls.append(1)
            return int

        namespace = fresh_namespace("def later(value: 'probe()'): pass", probe=probe)

        get_type_hints(namespace["later"])
        get_type_hints(namespace["later"])

        assert len(calls) == 2

    def test_a_class_pays_for_its_methods_not_only_its_hints(self) -> None:
        peaks = []
        for methods in (10, 10_000):
            body: dict[str, object] = {"__annotations__": {"x": int}}
            body.update({f"m{index}": (lambda self: None) for index in range(methods)})
            cls = type("Wide", (), body)
            assert get_type_hints(cls) == {"x": int}
            peaks.append(peak_bytes(lambda cls=cls: get_type_hints(cls)))

        assert peaks[1] > peaks[0] * 20, f"one hint, 1,000x the methods: {peaks}"

    def test_a_function_pays_for_its_hints(self) -> None:
        peaks = []
        for count in (10, 1_000):
            parameters = ", ".join(f"a{index}: int" for index in range(count))
            function = fresh_namespace(f"def f({parameters}): pass")["f"]
            assert len(get_type_hints(function)) == count
            peaks.append(peak_bytes(lambda function=function: get_type_hints(function)))

        assert peaks[1] > peaks[0] * 20, f"100x the annotations: {peaks}"


class TestAnnotationsAndDefinitionTime:
    """Before 3.14 an annotation is evaluated when the `def` runs; from 3.14
    on the first read of `__annotations__`, and the result is kept."""

    @pytest.mark.parametrize("source", ["def f(x: probe()): return x", "class f:\n    x: probe()"])
    def test_when_an_annotation_is_evaluated(self, source: str) -> None:
        calls: list[int] = []

        def probe() -> type:
            calls.append(1)
            return int

        namespace = fresh_namespace(source, probe=probe)
        at_definition = len(calls)
        first = namespace["f"].__annotations__
        second = namespace["f"].__annotations__

        assert at_definition == (0 if sys.version_info >= (3, 14) else 1)
        assert len(calls) == 1
        assert first == second == {"x": int}

    def test_calling_checks_nothing(self) -> None:
        def transform(rows: typing.Dict[str, typing.List[int]], limit: Optional[int]) -> int:
            return 0

        assert transform("not a dict", "not an int") == 0  # type: ignore[arg-type]

    def test_type_checking_is_false_at_runtime(self) -> None:
        assert TYPE_CHECKING is False


class TestRuntimeProtocols:
    """`isinstance()` against a runtime-checkable protocol walks its m members
    on 3.10-3.11; from 3.12 a class that has passed is answered from a cache,
    while failing checks and data members still read the instance."""

    def test_a_matching_object_passes(self) -> None:
        @runtime_checkable
        class Closeable(Protocol):
            def close(self) -> None: ...

        class Handle:
            def close(self) -> None: ...

        assert isinstance(Handle(), Closeable)
        assert not isinstance(object(), Closeable)

    def test_an_unmarked_protocol_refuses(self) -> None:
        class Unmarked(Protocol):
            def close(self) -> None: ...

        with pytest.raises(TypeError, match="runtime_checkable"):
            isinstance(object(), Unmarked)  # type: ignore[misc]

    def test_it_checks_names_and_not_signatures(self) -> None:
        @runtime_checkable
        class Closeable(Protocol):
            def close(self) -> None: ...

        class WrongSignature:
            def close(self, how: str, when: int) -> None: ...

        assert isinstance(WrongSignature(), Closeable)

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="cached from 3.12")
    def test_a_passing_check_walks_every_member_before_312(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wide = protocol_of(40)
        obj = type("Impl", (), {f"m{index}": (lambda self: None) for index in range(40)})()
        assert isinstance(obj, wide)
        walks: list[int] = []
        original = typing._get_protocol_attrs  # type: ignore[attr-defined]

        def record(cls: type) -> Any:
            attrs = original(cls)
            walks.append(len(attrs))
            return attrs

        monkeypatch.setattr(typing, "_get_protocol_attrs", record)

        assert isinstance(obj, wide)
        assert walks and all(walk == 40 for walk in walks), walks

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="walks the members before 3.12")
    def test_a_class_that_passed_is_answered_from_the_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wide = protocol_of(40)
        obj = type("Impl", (), {f"m{index}": (lambda self: None) for index in range(40)})()
        assert isinstance(obj, wide)
        visits = record_static_lookups(monkeypatch, obj)

        assert isinstance(obj, wide)
        assert visits == []

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="walks the members before 3.12")
    def test_a_failing_check_reads_the_instance_every_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wide = protocol_of(40)
        obj = object()
        assert not isinstance(obj, wide)
        visits = record_static_lookups(monkeypatch, obj)

        for calls in (1, 2):
            assert not isinstance(obj, wide)
            assert calls <= len(visits) <= 40 * calls, visits

    @pytest.mark.parametrize("count", [1, 40])
    def test_a_data_protocol_reads_every_member_each_time(
        self, count: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proto = protocol_of(count, data=True)
        names = {f"m{index}" for index in range(count)}
        obj = type("Impl", (), {})()
        for name in names:
            setattr(obj, name, 1)
        assert isinstance(obj, proto)
        visits: list[str] = []
        if sys.version_info >= (3, 12):
            visits = record_static_lookups(monkeypatch, obj)
        else:

            def record_attr(target: object, name: str) -> Any:
                if target is obj and name in names:
                    visits.append(name)
                return object.__getattribute__(target, name)

            monkeypatch.setattr(type(obj), "__getattribute__", record_attr)

        assert isinstance(obj, proto)
        assert names <= set(visits)
        assert count <= len([name for name in visits if name in names]) <= 2 * count
        with pytest.raises(TypeError):
            issubclass(type(obj), proto)


class TestDeclaringProtocols:
    """`class P(Protocol)` | O(p + m); `runtime_checkable` | O(m) from 3.12.2;
    `get_protocol_members` | O(m)."""

    def test_defining_a_protocol_pays_for_its_members(self) -> None:
        bases: tuple[type, ...] = (Protocol,)  # type: ignore[assignment]
        peaks = []
        for members in (10, 10_000):
            body = {f"m{index}": (lambda self: None) for index in range(members)}
            peaks.append(peak_bytes(lambda body=body: type("P", bases, dict(body))))
            if sys.version_info >= (3, 12):
                proto = type("P", bases, dict(body))
                assert len(proto.__protocol_attrs__) == members  # type: ignore[attr-defined]

        assert peaks[1] > peaks[0] * 20, peaks

    @pytest.mark.parametrize("count", [1, 40])
    def test_decoration_visits_each_member_from_3122(self, count: int) -> None:
        names = {f"field{i}" for i in range(count)}
        bases: tuple[type, ...] = (Protocol,)  # type: ignore[assignment]
        proto = type("Data", bases, {"__annotations__": dict.fromkeys(names, int)})
        visits: list[str] = []

        class Members(set[str]):
            def __iter__(self):  # noqa: ANN204
                for name in super().__iter__():
                    visits.append(name)
                    yield name

        if sys.version_info >= (3, 12, 2):
            proto.__protocol_attrs__ = Members(names)
        assert runtime_checkable(proto) is proto
        if sys.version_info >= (3, 12, 2):
            assert set(visits) == names and len(visits) == count
            assert proto.__non_callable_proto_members__ == names
        else:
            assert not hasattr(proto, "__non_callable_proto_members__")

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="get_protocol_members is 3.13+")
    def test_the_members_can_be_read_back(self) -> None:
        wide = protocol_of(5)

        members = typing.get_protocol_members(wide)  # type: ignore[attr-defined]

        assert members == {f"m{index}" for index in range(5)}
        assert typing.is_protocol(wide) is True  # type: ignore[attr-defined]


class TestAliasesAtRuntime:
    """Unparameterized aliases work with `isinstance()`; parameterized ones
    raise `TypeError`."""

    def test_bare_aliases_check_and_parameterized_ones_raise(self) -> None:
        assert isinstance([], typing.List)
        assert isinstance({}, typing.Mapping)
        for obj, alias in (([], typing.List[int]), ({}, typing.Mapping[str, int])):
            with pytest.raises(TypeError):
                isinstance(obj, alias)  # type: ignore[arg-type]
        assert get_origin(typing.TypeGuard[int]) is typing.TypeGuard


class TestDeclaringTypes:
    """`NamedTuple`, `TypedDict` | O(k); `NewType` returns its argument;
    `TypeVar` keeps its c constraints."""

    class Point(NamedTuple):
        x: float
        y: float

    class Config(TypedDict):
        name: str
        retries: int

    def test_a_named_tuple_is_a_tuple(self) -> None:
        point = self.Point(1.0, 2.0)

        assert point.x == 1.0
        assert tuple(point) == (1.0, 2.0)

    def test_a_typed_dict_counts_inherited_fields(self) -> None:
        class Extended(self.Config):  # type: ignore[name-defined, misc]
            timeout: float

        assert is_typeddict(self.Config) is True
        assert is_typeddict(self.Point) is False
        assert set(Extended.__annotations__) == {"name", "retries", "timeout"}

    def test_new_type_returns_its_argument(self) -> None:
        UserId = NewType("UserId", int)
        value = 7

        assert UserId(value) is value
        assert UserId.__supertype__ is int  # type: ignore[attr-defined]

    def test_a_type_var_keeps_its_constraints(self) -> None:
        constrained = typing.TypeVar("constrained", int, str, bytes)

        assert constrained.__constraints__ == (int, str, bytes)

    def test_param_spec_args_and_kwargs(self) -> None:
        spec = typing.ParamSpec("spec")

        assert isinstance(spec.args, typing.ParamSpecArgs)
        assert isinstance(spec.kwargs, typing.ParamSpecKwargs)
        assert spec.args.__origin__ is spec


class TestLazyTypeParameterValues:
    """A `type` statement evaluates its value on the first read and keeps it;
    `has_default()` does not evaluate a lazy default."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the type statement is 3.12+")
    def test_an_alias_value_is_evaluated_once_on_first_read(self) -> None:
        calls: list[int] = []

        def probe() -> type:
            calls.append(1)
            return int

        alias = fresh_namespace("type Alias = probe()", probe=probe)["Alias"]
        before = len(calls)

        assert alias.__value__ is alias.__value__ is int
        assert (before, len(calls)) == (0, 1)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="type parameter defaults are 3.13+")
    def test_has_default_does_not_evaluate_the_default(self) -> None:
        calls: list[int] = []

        def probe() -> type:
            calls.append(1)
            return int

        function = fresh_namespace("def f[T = probe()](): pass", probe=probe)["f"]
        parameter = function.__type_params__[0]

        assert parameter.has_default() is True
        assert calls == []
        assert parameter.__default__ is int
        assert len(calls) == 1


class TestForwardReferences:
    """`ForwardRef(arg)` compiles `arg` before 3.14 and keeps the string from
    3.14; `evaluate_forward_ref` | O(e + t)."""

    @pytest.mark.parametrize("count", [10, 10_000])
    def test_construction_compiles_before_314(
        self, count: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        compiled = []
        original = builtins.compile

        def record(source: Any, *args: Any, **kwargs: Any) -> Any:
            compiled.append(source)
            return original(source, *args, **kwargs)

        monkeypatch.setattr(builtins, "compile", record)
        source = "T" * count
        ref = typing.ForwardRef(source)
        assert ref.__forward_arg__ is source
        assert compiled == ([source] if sys.version_info < (3, 14) else [])
        if sys.version_info < (3, 14):
            with pytest.raises(SyntaxError):
                typing.ForwardRef("int[")
        else:
            assert typing.ForwardRef("int[").__forward_arg__ == "int["

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="evaluate_forward_ref is 3.14+")
    @pytest.mark.parametrize("count", [1, 100])
    def test_evaluation_walks_the_resolved_type(
        self, count: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = typing._eval_type  # type: ignore[attr-defined]
        visits = 0

        def record(value: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal visits
            if value is int:
                visits += 1
            return original(value, *args, **kwargs)

        monkeypatch.setattr(typing, "_eval_type", record)
        alias = tuple[(int,) * count]
        result = typing.evaluate_forward_ref(  # type: ignore[attr-defined]
            typing.ForwardRef("Alias"),
            globals={"Alias": alias},
            # typeshed declares a heterogeneous 3-tuple here; CPython iterates
            # any tuple of type params, so the empty tuple is valid.
            type_params=(),  # pyright: ignore[reportArgumentType]
        )
        assert result == alias
        assert visits == count

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="evaluate_forward_ref is 3.14+")
    def test_evaluation_runs_the_expression_as_written(self) -> None:
        work: list[int] = []

        def resolve() -> type:
            work.extend(range(100))
            return int

        result = typing.evaluate_forward_ref(  # type: ignore[attr-defined]
            typing.ForwardRef("resolve()"),
            globals={"resolve": resolve},
            type_params=(),  # pyright: ignore[reportArgumentType]
        )

        assert result is int
        assert len(work) == 100


class TestHelpers:
    """`cast` returns its argument; `assert_never` | O(r) builds the whole
    repr; `no_type_check` visits inherited names from 3.11; the overload
    registry is per process."""

    def test_cast_returns_the_same_object_unexamined(self) -> None:
        values = [1, 2, 3]

        assert cast(typing.List[str], values) is values
        assert cast("anything at all", values) is values  # type: ignore[misc]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="assert_never is 3.11+")
    def test_assert_never_builds_the_whole_repr_before_cutting_it(self) -> None:
        reprs = 0

        class Counted:
            def __repr__(self) -> str:
                nonlocal reprs
                reprs += 1
                return "c"

        with pytest.raises(AssertionError) as caught:
            typing.assert_never([Counted() for _ in range(1_000)])  # type: ignore[arg-type]

        assert reprs == 1_000
        assert len(str(caught.value)) < 200

    def test_no_type_check_visits_inherited_names_from_311(self) -> None:
        reads: list[str] = []

        class Meta(type):
            def __getattribute__(cls, name: str) -> Any:
                if name.startswith("inherited"):
                    reads.append(name)
                return type.__getattribute__(cls, name)

        methods = {f"inherited{index}": (lambda self: None) for index in range(1_000)}
        base = Meta("Base", (), methods)

        class Child(base):  # type: ignore[valid-type, misc]
            def own(self) -> None: ...

        assert typing.no_type_check(Child) is Child
        assert Child.own.__no_type_check__ is True  # type: ignore[attr-defined]
        assert len(reads) == (1_000 if sys.version_info >= (3, 11) else 0)

    def test_overloads_are_registered_from_311(self) -> None:
        namespace = fresh_namespace(
            """
            from typing import overload

            @overload
            def f(x: int) -> int: ...
            @overload
            def f(x: str) -> str: ...
            def f(x):
                return x
            """
        )
        if sys.version_info < (3, 11):
            assert not hasattr(typing, "get_overloads")
            assert not hasattr(typing, "_overload_registry")
            return

        assert len(typing.get_overloads(namespace["f"])) == 2  # type: ignore[attr-defined]
        typing.clear_overloads()  # type: ignore[attr-defined]
        assert typing.get_overloads(namespace["f"]) == []  # type: ignore[attr-defined]


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
    """Each block runs in its own subprocess, so the `__future__` import is
    the first statement of its file, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "UserId(value) is value" in s)
        mutated = source.replace("UserId(value) is value", "UserId(value) is not value", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
