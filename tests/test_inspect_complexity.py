"""Tests for docs/stdlib/inspect.md.

The page splits the module in two. Almost everything reads state the
interpreter already holds and is O(1); the parts that leave the object graph -
source text, the stack, `dis` - pay for what they reach. The O(1) rows are
settled by identity and by call counting, which need no tolerance: an accessor
that hands back an existing object is O(1) whatever its size, and a function
that never calls `linecache` never read a file. The growing rows are settled by
holding every dimension fixed but one.

Measurement scope:

* The code-flag predicates walk a chain only when there is one. Sixteen nested
  plain `functools.partial` calls leave a single partial; giving each one an
  attribute before wrapping it stops the absorption, and 64 of those leave 64
  links. Over that second shape, 256x the depth costs more than 3x.
  `unwrap()` counts its chain directly - its `stop` callback is invoked once
  per `__wrapped__` link, seven for seven.
* `getmro()` is asserted to return `cls.__mro__` itself, so no length-
  proportional work happens at any depth. `Signature.parameters` is the same
  `mappingproxy` on every access and `BoundArguments.arguments` the same
  mapping, while `BoundArguments.args` and `.kwargs` are rebuilt: the first
  pair is `is`, the second `is not` with equal contents.
* `signature()` and `getdoc()` are asserted to return a new object on each
  call, so neither is cached. `getdoc()` is then timed over docstrings of
  1,000 and 100,000 characters: 100x the length costs more than 20x.
* `getmembers()` invokes every descriptor and `getmembers_static()` invokes
  none, observed with a property that appends to a list: one call against
  zero. `getattr_static()` likewise triggers neither a property nor a
  metaclass `__getattr__`, and is timed for an attribute reachable only at
  the root of a 4-deep and a 128-deep single-inheritance chain: 32x the depth
  costs more than 5x. The metaclass term is timed separately, with the MRO
  held at 34 entries while the metaclass chain goes from 1 to 128: more than
  5x again. `classify_class_attrs()` over the first two chains, with the name
  count held at `dir(object)`, costs more than 3x; its own metaclass term is
  the same walk and is not timed separately.
* `getclasstree()` is timed on 250 and 1,000 unrelated classes, each with a
  single base so the tree stays the size of the list: 4x the input costs more
  than 8x, which excludes any linear bound. The tree's own term is observed
  separately by counting entries - a class with two bases produces five
  entries against four under `unique=True`, and a 20-class lattice of paired
  bases produces more than 20 entries per class against at most one. That
  `unique=True` only deduplicates within the list is observed by leaving the
  bases out, where it changes nothing. The base-link term is timed separately
  with the class count held at 200 and the bases per class at 1 against 64:
  64x the links costs more than 8x. `walktree()` is observed to sort the list
  it was passed, in place.
* `getclosurevars()` is settled by counting: on Python 3.12+ `dis.get_instructions`
  is replaced with a counting wrapper, and the instructions it yields equal the
  whole code object's, not the one free variable's. Before 3.12 the function
  walks `co_names` instead, so the probe asserts only that the names it could
  read are a small fraction of the instructions, and that the result agrees.
* `findsource()` is timed over three modules holding the same two-line
  function: two of 40,000 lines with the definition at either end, and one of
  400 with it at the top. Warm, top and bottom are within 2x of each other and
  top is within 2x of the small file, so the cached call tracks neither
  position nor file size, and the line list it returns is the same object on a
  second call. `getsourcelines()` over the
  40,000-line pair costs more than 3x at the top, which is the tail below the
  definition. All three modules are imported and measured once before timing.
* `stack()` and `stack(0)` are compared by counting `linecache.getlines`
  calls from a 20-frame recursion: one per frame against none at all. The
  same counter shows `getframeinfo(frame, 0)` reads nothing. What `context=0`
  does not skip is timed separately, at 1 and 4,000 statements into the
  frame's function: `getlineno()` alone costs more than 5x on every supported
  version, which is the line-table walk, and from 3.11 `getframeinfo(frame,
  0)` costs more than 5x too, which is the second walk for the column range.
  Before 3.11 that second walk does not exist and the line-table one is
  swamped by `getframeinfo()`'s own stat, so there is no pre-3.11 assertion on
  `getframeinfo()` itself.
* `cleandoc()` holds the body at 2,000 lines and moves the leading blanks from
  200 to 20,000 - under 12x the characters - and costs more than 12x, which is
  the z.L term. `signature()` holds p at 10 while the surviving `partial`
  layers go from 1 to 64 and costs more than 8x, which is the w.p one.
* `get_annotations()` holds the annotation count at one while the class's
  other members go from 10 to 5,000: before 3.14 that costs more than 20x,
  from 3.14 less than 3x, which is where the `__dict__` copy went.
  `formatargvalues()` is timed at 100 and 1,600 parameters through the proxy
  `getargvalues()` returns: 16x the parameters costs more than 20x, so the
  per-name lookup is not constant. On 3.12 the same pair is linear, which is
  why that test is guarded rather than written to hold everywhere.
* `getmodule()` is observed against `inspect.modulesbyfile` in a fresh
  interpreter: a class resolves without adding an entry, while a code object
  leaves every file-backed module that was in `sys.modules` at the time
  mapped - the set is snapshotted before the call and asserted empty of
  leftovers afterwards. The probe needs its own process because clearing that
  map does not reset the scan: a second, private map records the modules
  already walked and suppresses them. That only matches are cached is
  observed rather than timed: three calls for a code object whose filename
  belongs to no loaded module leave `modulesbyfile` without an entry for it
  every time, so there is nothing for the next call to reuse. Timing that
  against a cached hit would not settle it - on 3.10 the cached path is the
  slower of the two, because it re-normalises the path. What is timed is the
  row's O(1): resolving through `__module__` costs less than a twentieth of
  the scan. The same scan reaching `getsourcefile()` and `getframeinfo()` at
  `context=0` is read from Lib/inspect.py, not timed: the page states it as a
  qualification on those O(1) rows rather than as a bound.
* `signature()` is asserted to return a function's `__signature__` attribute
  as it stands, and `getdoc()` to return an already-clean one-line docstring
  unchanged. Neither is a cache: the first skips the build, the second still
  splits the string and finds nothing to strip. `getcallargs()` is
  asserted to bind a positional-only parameter by keyword where the call and
  `Signature.bind()` both raise. `bind()` is asserted to collect 50 arguments
  into one `*args` parameter and 50 into one `**kwargs`, which is the `a`
  term.
* `ismethoddescriptor()` is asserted against a descriptor defining `__get__`
  and `__delete__` but no `__set__`, which 3.13 and later reject and earlier
  versions accept; `isdatadescriptor()` accepts it throughout.
* The 3.11-only `co_varnames` rebuild is asserted from both directions: the
  tuple's identity across two accesses is stable everywhere but 3.11, and
  `getargs()` over a two-parameter function carrying 5 against 2,000 locals
  costs more than 4x there and under 2x elsewhere. `signature()` and
  `getfullargspec()` read the same attribute and are named in the Version
  Note. `getargs()` moves 9.5x over that pair on 3.11 and `signature()` 2.5x,
  so both are asserted, at their own thresholds and against a flat
  elsewhere.
* The version boundaries are asserted by behaviour, not by version alone:
  `getargvalues(frame).locals` supports `__setitem__` write-through on 3.13+
  and is a plain `dict` snapshot before, and a class's `findsource()` is
  timed against file size on both sides.
* The reference rows no behavioural test reaches - the `Signature` and
  `Parameter` constructors, `from_callable()`, `format()`, the annotation
  formatters, `getabsfile()`, the coroutine and async-generator state
  functions, the frame records' fields, the `CO_*` and `TPFLAGS_IS_ABSTRACT`
  flags and `BufferFlags` - are asserted against their Notes cell on a fixed
  input, not measured. Those of them that grow do so by building a result of
  the size they are priced at: `Signature(parameters)` in p, `format()` and
  the annotation formatters in the rendered length. Nothing distinguishes
  those from a worse bound here.
* Every fenced Python block runs in its own subprocess with its own working
  directory, since several write temporary modules and mutate
  `inspect.modulesbyfile`, and a mutated assertion in one of them is asserted
  to fail.

Not settled here:

* `getsourcefile()` returning `None` for a C extension module. This
  interpreter statically links every C module, so `sys.builtin_module_names`
  covers them and no `.so` exists to test against; the built-in case is
  tested in its place. The claim holds only on a build with dynamically
  loaded extension modules.
* `inspect.modulesbyfile` is documented in the `getmodule()` note rather than
  given a row. It carries no underscore but is absent from `__all__` and from
  the official API inventory, and it is named here as an intentional
  omission.
* `BufferFlags`, `CO_METHOD` and `CO_HAS_DOCSTRING` are priced as constant
  reads from the page's cost model; nothing is measured, because nothing in
  `inspect` consumes them.
* `isabstract()`'s fallback path, taken only for a class observed
  mid-construction from `__init_subclass__`. The tests cover the type-flag
  path, which is what every finished class takes.
* `Parameter.kind.description` is an attribute of the kind enum member rather
  than of `Parameter`, so the audit cannot resolve it statically. It is
  asserted on a real signature in the signature example block.
* Costs that depend on character counts rather than the page's line, name and
  parameter counts: the length of a source line, a path, a parameter name or
  an argument `repr`. The page's cost model, stated in its size-variable
  paragraph, prices an attribute read and one operation on a short string at
  O(1) and counts items rather than characters, and no test varies them. `cleandoc()`'s
  leading-blank term is priced and timed, but in lines rather than
  characters.
* Two superlinear terms are priced out of the page rather than into it,
  because reaching them takes a function nobody writes. `getfullargspec()`
  builds its `defaults` tuple by repeated concatenation: at 50, 200 and 800
  defaulted parameters it costs 41us, 197us and 1088us, growing 4.8x and 5.5x
  for each 4x, while `signature()` over the same three costs 33us, 129us and
  509us - 3.9x and 4.0x, flat. The page keeps O(w.p) for both. A `partial`
  holding many stored arguments was measured in the shape that would show it,
  a `*args` function with w = p = 1 and 50, 200 and 800 stored positional
  arguments: 6.6us, 7.6us and 12.1us, so 16x the stored arguments moved
  `signature()` by 1.8x and no term is carried for them.
* Absolute costs are not compared across functions, and no test varies
  annotation evaluation (`eval_str=True`) or non-UTF-8 source encodings.
"""

from __future__ import annotations

import dis
import inspect
import linecache
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import types
from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "inspect.md"
EXPECTED_BLOCKS = 21


def best_us(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in microseconds per call."""
    func()
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best * 1e6


def chain(depth: int, **root_attrs: Any) -> type:
    """A single-inheritance chain `depth` classes deep below a root."""
    built: type = type("Root", (object,), dict(root_attrs))
    for index in range(depth):
        built = type(f"Link{index}", (built,), {})
    return built


def write_module(directory: pathlib.Path, name: str, before: int, after: int) -> types.ModuleType:
    """Import a module with `tiny()` padded by plain statements on either side."""
    import importlib.util

    path = directory / f"{name}.py"
    path.write_text(
        "pad = 1\n" * before + "def tiny():\n    return 1\n" + "pad = 1\n" * after,
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PADDING = 40_000


async def _PROBE_CORO(alpha: int) -> int:  # noqa: N802 - a constant, not a function to call
    """Never awaited; only its CO_COROUTINE flag is read."""
    return alpha


@pytest.fixture(scope="module")
def modules(tmp_path_factory: pytest.TempPathFactory) -> tuple[Any, Any, Any]:
    """The same two-line function in three files that differ only in padding.

    `at_top` and `at_bottom` hold the file size fixed and move the definition;
    `small` holds the position fixed and shrinks the file a hundredfold.
    """
    directory = tmp_path_factory.mktemp("source")
    at_top = write_module(directory, "pad_below", 0, PADDING)
    at_bottom = write_module(directory, "pad_above", PADDING, 0)
    small = write_module(directory, "pad_little", 0, PADDING // 100)
    for module in (at_top, at_bottom, small):
        inspect.getsourcelines(module.tiny)  # warm linecache before timing
    return at_top, at_bottom, small


class CountingGetlines:
    """Records which files `linecache.getlines` was asked for."""

    def __init__(self) -> None:
        self.files: list[str] = []
        self._original = linecache.getlines

    def __enter__(self) -> CountingGetlines:
        def counting(filename: str, module_globals: Any = None) -> list[str]:
            self.files.append(filename)
            return self._original(filename, module_globals)

        linecache.getlines = counting  # type: ignore[assignment]
        return self

    def __exit__(self, *_: object) -> None:
        linecache.getlines = self._original  # type: ignore[assignment]


class TestAccessorsHandBackWhatExists:
    """`getmro()` | O(1) | O(1), `Signature.parameters` | O(1) | O(1),
    `BoundArguments.arguments` | O(1) | O(1).

    Each is asserted by identity, which prices an accessor with no tolerance:
    returning an existing object cannot be linear in its size. `args` and
    `kwargs`, which the page prices at O(p), are the control - equal contents
    but a different object every time.
    """

    def test_getmro_returns_the_classes_own_tuple(self) -> None:
        deep = chain(200)

        assert inspect.getmro(deep) is deep.__mro__
        assert len(inspect.getmro(deep)) == 202

    def test_parameters_is_one_mappingproxy(self) -> None:
        def target(alpha: int, beta: str = "x", *rest: int, gamma: float = 1.0) -> None: ...

        signature = inspect.signature(target)

        assert signature.parameters is signature.parameters
        assert list(signature.parameters) == ["alpha", "beta", "rest", "gamma"]

    def test_bound_arguments_is_the_mapping_but_args_are_rebuilt(self) -> None:
        def target(alpha: int, *rest: int, gamma: int = 0) -> None: ...

        bound = inspect.signature(target).bind(1, 2, 3, gamma=4)

        assert bound.arguments is bound.arguments
        assert bound.args is not bound.args
        assert bound.args == (1, 2, 3)
        assert bound.kwargs is not bound.kwargs
        assert bound.kwargs == {"gamma": 4}


class TestNothingIsCached:
    """`signature()` and `getdoc()` build a fresh result every call.

    Identity separates a cache from a rebuild outright; the docstring timing
    then shows the rebuild is linear in what it cleans, which a cache would
    flatten.
    """

    def test_signature_is_rebuilt(self) -> None:
        def target(alpha: int, beta: int = 1) -> None: ...

        first = inspect.signature(target)
        second = inspect.signature(target)

        assert first is not second
        assert first == second

    def test_getdoc_is_rebuilt_and_is_not_the_docstring(self) -> None:
        class Documented:
            pass

        # Assigned rather than written as a literal: `ruff format` renormalises
        # docstring indentation, which is the very thing cleandoc() strips.
        Documented.__doc__ = "Summary.\n\n        Indented body.\n    "

        first = inspect.getdoc(Documented)
        assert first is not inspect.getdoc(Documented)
        assert first is not Documented.__doc__
        assert first == "Summary.\n\nIndented body."

    def test_a_clean_one_line_docstring_comes_back_unchanged(self) -> None:
        class Terse:
            pass

        Terse.__doc__ = "Nothing to strip."

        assert inspect.getdoc(Terse) is Terse.__doc__, (
            "cleandoc() built a new string although there was nothing to clean"
        )

    def test_an_explicit_signature_short_circuits_the_build(self) -> None:
        def target(alpha, beta=1):
            return alpha

        declared = inspect.Signature(
            [inspect.Parameter("gamma", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        )
        target.__signature__ = declared  # type: ignore[attr-defined]

        first = inspect.signature(target)
        assert first is declared, "__signature__ was rebuilt instead of returned"
        assert inspect.signature(target) is declared
        assert str(first) == "(gamma)"

    def test_getdoc_falls_back_through_the_mro(self) -> None:
        class Base:
            """Inherited summary."""

        class Derived(Base):
            pass

        assert Derived.__doc__ is None
        assert inspect.getdoc(Derived) == "Inherited summary."

    @pytest.mark.timing
    def test_getdoc_cost_tracks_the_docstring(self) -> None:
        class Small:
            pass

        class Large:
            pass

        Small.__doc__ = "head\n" + "    body\n" * 100
        Large.__doc__ = "head\n" + "    body\n" * 10_000
        assert len(Large.__doc__) > 90 * len(Small.__doc__)

        small = best_us(lambda: inspect.getdoc(Small), inner=20)
        large = best_us(lambda: inspect.getdoc(Large), inner=20)

        assert large > 20 * small, f"100x the docstring cost {large / small:.1f}x ({small:.2f}us)"


class TestGetmembersRunsDescriptors:
    """`getmembers()` | O(m log m + descriptor cost), `getmembers_static()` | O(m·c + m log m).

    Counting invocations separates "reads the value" from "reads the
    descriptor": a property that appends to a list runs once under
    `getmembers()` and never under `getmembers_static()`, whatever either
    costs.
    """

    @staticmethod
    def _probe() -> tuple[Any, list[str]]:
        calls: list[str] = []

        class Probe:
            @property
            def value(self) -> int:
                calls.append("value")
                return 1

        return Probe(), calls

    def test_getmembers_evaluates_every_property(self) -> None:
        probe, calls = self._probe()

        members = dict(inspect.getmembers(probe))

        assert calls == ["value"]
        assert members["value"] == 1

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="getmembers_static is Python 3.11+")
    def test_getmembers_static_evaluates_none(self) -> None:
        probe, calls = self._probe()

        getmembers_static = inspect.getmembers_static  # type: ignore[attr-defined]
        members = dict(getmembers_static(probe))

        assert calls == []
        assert isinstance(members["value"], property)

    def test_a_predicate_does_not_skip_the_getattr(self) -> None:
        probe, calls = self._probe()

        inspect.getmembers(probe, inspect.ismethod)

        assert calls == ["value"], "the predicate filtered the result, not the lookup"

    def test_results_come_back_sorted(self) -> None:
        names = [name for name, _ in inspect.getmembers(inspect)]

        assert names == sorted(names)


class TestStaticLookupWalksTheMro:
    """`getattr_static()` | O(c) | O(1).

    The descriptor-avoidance half is settled by counting; the O(c) half by
    holding the attribute's position fixed at the root of the chain and
    varying only the chain's depth.
    """

    def test_it_triggers_neither_property_nor_getattr(self) -> None:
        seen: list[str] = []

        class Meta(type):
            def __getattr__(cls, name: str) -> Any:
                seen.append(name)
                raise AttributeError(name)

        class Probe(metaclass=Meta):
            @property
            def value(self) -> int:
                seen.append("value")
                return 1

        assert isinstance(inspect.getattr_static(Probe(), "value"), property)
        assert inspect.getattr_static(Probe, "absent", "fallback") == "fallback"
        assert seen == []

        assert Probe().value == 1
        assert seen == ["value"], "the control lookup should have run the property"

    @pytest.mark.timing
    def test_cost_tracks_the_depth_of_the_chain(self) -> None:
        shallow = chain(4, target=1)
        deep = chain(128, target=1)

        near = best_us(lambda: inspect.getattr_static(shallow, "target"), inner=200)
        far = best_us(lambda: inspect.getattr_static(deep, "target"), inner=200)

        assert far > 5 * near, f"32x the depth cost {far / near:.1f}x ({near:.3f}us)"

    @pytest.mark.timing
    def test_cost_also_tracks_the_metaclass_chain(self) -> None:
        """The y term: the MRO is held at 34 while the metaclass chain grows."""

        def build(metaclass_depth: int) -> type:
            metaclass: type = type
            for index in range(metaclass_depth):
                metaclass = type(f"Meta{index}", (metaclass,), {})
            built = metaclass("Root", (object,), {"target": 1})
            for index in range(32):
                built = metaclass(f"Link{index}", (built,), {})
            return built

        plain, layered = build(1), build(128)
        assert len(plain.__mro__) == len(layered.__mro__)

        near = best_us(lambda: inspect.getattr_static(plain, "target"), inner=500)
        far = best_us(lambda: inspect.getattr_static(layered, "target"), inner=500)

        assert far > 5 * near, f"128x the metaclass depth cost {far / near:.1f}x ({near:.2f}us)"


class TestClassifyClassAttrsSearchesPerName:
    """`classify_class_attrs()` | O(m·c) | O(m).

    The name count is held at whatever `dir()` reports for an empty chain,
    which is the same for both inputs, so only `c` moves.
    """

    def test_it_reports_the_defining_class(self) -> None:
        class Base:
            def method(self) -> None: ...

        class Derived(Base):
            pass

        attributes = {entry.name: entry for entry in inspect.classify_class_attrs(Derived)}

        assert attributes["method"].defining_class is Base
        assert attributes["method"].kind == "method"
        assert attributes["method"].object is Base.__dict__["method"]

    @pytest.mark.timing
    def test_cost_tracks_the_mro(self) -> None:
        shallow = chain(4)
        deep = chain(128)
        assert len(dir(shallow)) == len(dir(deep))

        near = best_us(lambda: inspect.classify_class_attrs(shallow), inner=20)
        far = best_us(lambda: inspect.classify_class_attrs(deep), inner=20)

        assert far > 3 * near, f"32x the depth cost {far / near:.1f}x ({near:.1f}us)"


class TestGetclasstreeIsQuadratic:
    """`getclasstree()` | O(C²) | O(C).

    Four times the classes costing more than eight times the time excludes
    every linear bound, which is what the row claims and what list membership
    testing produces.
    """

    @staticmethod
    def _classes(count: int) -> list[type]:
        return [type(f"K{index}", (object,), {}) for index in range(count)]

    def test_it_nests_children_under_their_parent(self) -> None:
        class Animal:
            pass

        class Dog(Animal):
            pass

        class Cat(Animal):
            pass

        tree = inspect.getclasstree([Dog, Cat])

        assert tree[0] == (Animal, Animal.__bases__)
        children = tree[1]
        assert isinstance(children, list)
        assert [entry[0] for entry in children] == [Cat, Dog]

    def test_walktree_sorts_its_argument_in_place(self) -> None:
        class Beta:
            pass

        class Alpha:
            pass

        given = [Beta, Alpha]
        inspect.walktree(given, {}, None)

        assert given == [Alpha, Beta]

    def test_unique_false_repeats_a_class_under_every_base(self) -> None:
        class Left:
            pass

        class Right:
            pass

        class Both(Left, Right):
            pass

        def entries(tree: Any) -> int:
            return sum(entries(item) if isinstance(item, list) else 1 for item in tree)

        repeated = inspect.getclasstree([Left, Right, Both])
        once = inspect.getclasstree([Left, Right, Both], unique=True)

        assert entries(repeated) == 5, "Both should be listed under each of its two bases"
        assert entries(once) == 4, "unique=True should place Both once"

        # unique=True stops at the first base that is itself in `classes`. With the
        # bases left out there is nothing to stop at, so it changes nothing.
        assert entries(inspect.getclasstree([Both])) == 4
        assert entries(inspect.getclasstree([Both], unique=True)) == 4

    def test_a_lattice_makes_the_tree_outgrow_the_list(self) -> None:
        bases: tuple[type, ...] = (object,)
        lattice: list[type] = []
        for level in range(10):
            left = type(f"L{level}", bases, {})
            right = type(f"R{level}", bases, {})
            lattice += [left, right]
            bases = (left, right)

        def entries(tree: Any) -> int:
            return sum(entries(item) if isinstance(item, list) else 1 for item in tree)

        repeated = entries(inspect.getclasstree(lattice))
        once = entries(inspect.getclasstree(lattice, unique=True))

        assert repeated > 20 * len(lattice), (
            f"{len(lattice)} classes produced only {repeated} entries"
        )
        # Every base of every class is itself in the list here, so unique=True has a
        # stop to find: at most one entry per class, plus the external root.
        assert once <= len(lattice) + 1, f"unique=True produced {once} entries"

    @pytest.mark.timing
    def test_four_times_the_classes_costs_more_than_eight_times(self) -> None:
        small = self._classes(250)
        large = self._classes(1000)

        near = best_us(lambda: inspect.getclasstree(list(small)), inner=3)
        far = best_us(lambda: inspect.getclasstree(list(large)), inner=3)

        assert far > 8 * near, f"4x the classes cost {far / near:.1f}x ({near:.1f}us)"

    @pytest.mark.timing
    def test_more_bases_per_class_costs_more_at_a_fixed_class_count(self) -> None:
        """The e term: q is held at 200 while each class's base count grows."""

        def with_bases(count: int) -> list[type]:
            bases = tuple(type(f"B{index}", (object,), {}) for index in range(count))
            return [type(f"C{index}", bases, {}) for index in range(200)]

        one, many = with_bases(1), with_bases(64)

        near = best_us(lambda: inspect.getclasstree(list(one)), inner=3)
        far = best_us(lambda: inspect.getclasstree(list(many)), inner=3)

        assert far > 8 * near, f"64x the base links cost {far / near:.1f}x ({near:.1f}us)"


class TestClosureVarsScansTheBytecode:
    """`getclosurevars()` | O(i) | O(i).

    Counting the instructions the disassembler yields settles this outright:
    the page's claim is that the whole code object is scanned, not the one
    free variable, and the count is the code object's own length.
    """

    @staticmethod
    def _closure(statements: int) -> Any:
        source = (
            "def outer():\n"
            "    captured = 42\n"
            "    def inner():\n"
            "        total = 0\n"
            + "".join(f"        total += {n}\n" for n in range(statements))
            + "        return total + captured + len('x')\n"
            "    return inner\n"
        )
        namespace: dict[str, Any] = {}
        exec(compile(source, "<probe>", "exec"), namespace)
        return namespace["outer"]()

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the dis scan is Python 3.12+")
    def test_it_reads_the_whole_code_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inner = self._closure(200)
        total = len(list(dis.get_instructions(inner.__code__)))
        assert total > 400, "the probe body is too short to separate the two bounds"

        counted = 0
        original = dis.get_instructions

        def counting(*args: Any, **kwargs: Any) -> Any:
            nonlocal counted
            for instruction in original(*args, **kwargs):
                counted += 1
                yield instruction

        monkeypatch.setattr(dis, "get_instructions", counting)
        variables = inspect.getclosurevars(inner)

        assert counted == total, f"scanned {counted} of {total} instructions"
        assert variables.nonlocals == {"captured": 42}
        assert len(variables.nonlocals) == 1, "one free variable, the whole body scanned"
        assert variables.builtins == {"len": len}

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="co_names was replaced in 3.12")
    def test_earlier_versions_agree_without_the_dis_scan(self) -> None:
        inner = self._closure(200)
        instructions = len(list(dis.get_instructions(inner.__code__)))

        variables = inspect.getclosurevars(inner)

        assert len(inner.__code__.co_names) * 20 < instructions, (
            "the probe does not separate the names from the instructions"
        )
        assert variables.nonlocals == {"captured": 42}
        assert variables.builtins == {"len": len}


class TestUnwrappingCostsTheChain:
    """`unwrap()` | O(w) | O(w), and the code-flag predicates | O(w) | O(1).

    The `stop` callback is invoked once per link, so it counts the chain
    directly rather than timing it.
    """

    @staticmethod
    def _wrapped(depth: int) -> Any:
        import functools

        def base(alpha, beta=2):  # unannotated: this file defers annotations
            return alpha + beta

        def layer(inner: Any) -> Any:
            @functools.wraps(inner)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return inner(*args, **kwargs)

            return wrapper

        current: Any = base
        for _ in range(depth):
            current = layer(current)
        return base, current

    def test_stop_is_called_once_per_link(self) -> None:
        base, wrapped = self._wrapped(7)
        seen: list[Any] = []

        result = inspect.unwrap(wrapped, stop=lambda obj: bool(seen.append(obj)))

        assert result is base
        assert len(seen) == 7

    def test_a_cycle_raises_rather_than_spinning(self) -> None:
        def one() -> None: ...
        def two() -> None: ...

        one.__wrapped__ = two  # type: ignore[attr-defined]
        two.__wrapped__ = one  # type: ignore[attr-defined]

        with pytest.raises(ValueError, match="wrapper loop"):
            inspect.unwrap(one)

    def test_partial_layers_flatten_rather_than_nest(self) -> None:
        import functools

        async def coro(alpha: int) -> int:
            return alpha

        layered: Any = coro
        for _ in range(16):
            layered = functools.partial(layered)

        assert layered.func is coro, "sixteen calls should leave one partial, not sixteen"
        assert inspect.iscoroutinefunction(layered) is True
        assert inspect.iscoroutinefunction(functools.partial(len)) is False
        coro(1).close()

    @staticmethod
    def _tagged_partials(depth: int) -> Any:
        """A real chain: giving a partial an attribute stops the next one absorbing it."""
        import functools

        layered: Any = _PROBE_CORO
        for index in range(depth):
            layered = functools.partial(layered)
            layered.tag = index
        return layered

    def test_a_tagged_partial_is_not_absorbed(self) -> None:
        chained = self._tagged_partials(64)

        depth = 0
        current: Any = chained
        while hasattr(current, "func"):
            depth += 1
            current = current.func

        assert depth == 64, f"the chain collapsed to {depth} links"
        assert current is _PROBE_CORO
        assert inspect.iscoroutinefunction(chained) is True

    @pytest.mark.timing
    def test_the_predicate_walks_a_chain_that_does_not_flatten(self) -> None:
        shallow, deep = self._tagged_partials(1), self._tagged_partials(256)

        near = best_us(lambda: inspect.iscoroutinefunction(shallow), inner=2_000)
        far = best_us(lambda: inspect.iscoroutinefunction(deep), inner=2_000)

        assert far > 3 * near, f"256x the chain cost {far / near:.1f}x ({near:.3f}us)"

    @pytest.mark.timing
    def test_signature_rebuilds_the_parameters_at_every_partial_layer(self) -> None:
        """The w.p bound: p is held at 10 while the surviving layers grow."""

        def target(a1, a2, a3, a4, a5, a6, a7, a8, a9, a10):
            return a1

        def chain(depth: int) -> Any:
            import functools

            current: Any = target
            for index in range(depth):
                current = functools.partial(current)
                current.tag = index
            return current

        shallow, deep = chain(1), chain(64)
        assert len(inspect.signature(deep).parameters) == 10, "the layers changed p"

        near = best_us(lambda: inspect.signature(shallow), inner=200)
        far = best_us(lambda: inspect.signature(deep), inner=200)

        assert far > 8 * near, f"64x the layers cost {far / near:.1f}x ({near:.1f}us)"

    def test_signature_follows_the_wrapped_chain(self) -> None:
        _, wrapped = self._wrapped(7)

        assert str(inspect.signature(wrapped)) == "(alpha, beta=2)"
        assert str(inspect.signature(wrapped, follow_wrapped=False)) == "(*args, **kwargs)"


class TestSourceCostsTheTailOfTheFile:
    """`findsource()` | O(F) first call, then O(1); `getsourcelines()` | O(t).

    The two modules hold everything fixed but the definition's position: the
    same two-line function, the same 40,000-line file. A bound in `F` predicts
    they cost the same; a bound in `t` predicts the one at the top costs far
    more, and only `getsourcelines()` does.
    """

    def test_both_return_the_same_two_lines(self, modules: tuple[Any, Any, Any]) -> None:
        at_top, at_bottom, _ = modules

        top_lines, top_start = inspect.getsourcelines(at_top.tiny)
        bottom_lines, bottom_start = inspect.getsourcelines(at_bottom.tiny)

        assert top_lines == bottom_lines == ["def tiny():\n", "    return 1\n"]
        assert top_start == 1
        assert bottom_start == PADDING + 1

    @pytest.mark.timing
    def test_findsource_is_flat_once_the_file_is_cached(
        self, modules: tuple[Any, Any, Any]
    ) -> None:
        at_top, at_bottom, small = modules

        top = best_us(lambda: inspect.findsource(at_top.tiny), inner=20)
        bottom = best_us(lambda: inspect.findsource(at_bottom.tiny), inner=20)
        little = best_us(lambda: inspect.findsource(small.tiny), inner=20)

        assert max(top, bottom) < 2 * min(top, bottom), (
            f"position changed the cached cost: {top:.1f}us vs {bottom:.1f}us"
        )
        assert top < 2 * little, f"100x the file cost {top / little:.1f}x cached ({little:.1f}us)"

    def test_the_cached_lines_are_the_same_list_every_call(
        self, modules: tuple[Any, Any, Any]
    ) -> None:
        at_top, _, _ = modules

        first, _ = inspect.findsource(at_top.tiny)
        second, _ = inspect.findsource(at_top.tiny)

        assert first is second, "findsource() rebuilt the line list instead of reusing linecache"
        assert len(first) > PADDING

    @pytest.mark.timing
    def test_getsourcelines_costs_what_follows_the_definition(
        self, modules: tuple[Any, Any, Any]
    ) -> None:
        at_top, at_bottom, _ = modules

        top = best_us(lambda: inspect.getsourcelines(at_top.tiny), inner=20)
        bottom = best_us(lambda: inspect.getsourcelines(at_bottom.tiny), inner=20)

        assert top > 3 * bottom, (
            f"40,000 lines below the definition cost {top / bottom:.1f}x ({bottom:.1f}us)"
        )

    def test_getsourcefile_does_not_go_through_linecache(
        self, modules: tuple[Any, Any, Any]
    ) -> None:
        at_top, _, _ = modules

        with CountingGetlines() as counter:
            path = inspect.getsourcefile(at_top.tiny)

        assert path is not None and path.endswith("pad_below.py")
        assert counter.files == []

    def test_a_builtin_module_has_no_file(self) -> None:
        assert "sys" in sys.builtin_module_names

        with pytest.raises(TypeError, match="built-in module"):
            inspect.getfile(sys)


class TestClassSourceAcrossVersions:
    """Python 3.13+ reads `__firstlineno__`; earlier versions parse the AST.

    Both halves assert the same way - whether a cached `findsource()` on a
    class still grows with the file - so the boundary is established by
    behaviour on either side rather than by the version number alone.
    """

    @staticmethod
    def _class_modules(directory: pathlib.Path) -> tuple[Any, Any]:
        import importlib.util

        built = []
        for name, padding in (("small_cls", 2_000), ("large_cls", 20_000)):
            path = directory / f"{name}.py"
            path.write_text("class K:\n    pass\n" + "pad = 1\n" * padding, encoding="utf-8")
            spec = importlib.util.spec_from_file_location(name, path)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            inspect.findsource(module.K)  # warm linecache
            built.append(module)
        return built[0], built[1]

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="__firstlineno__ is Python 3.13+")
    def test_a_cached_class_lookup_is_flat(self, tmp_path: pathlib.Path) -> None:
        small, large = self._class_modules(tmp_path)

        near = best_us(lambda: inspect.findsource(small.K), inner=20)
        far = best_us(lambda: inspect.findsource(large.K), inner=20)

        assert far < 3 * near, f"10x the file cost {far / near:.1f}x ({near:.1f}us)"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="the AST parse ended in 3.13")
    def test_the_ast_parse_tracks_the_file(self, tmp_path: pathlib.Path) -> None:
        small, large = self._class_modules(tmp_path)

        near = best_us(lambda: inspect.findsource(small.K), inner=3)
        far = best_us(lambda: inspect.findsource(large.K), inner=3)

        assert far > 5 * near, f"10x the file cost {far / near:.1f}x ({near:.1f}us)"

    def test_the_line_number_is_right_either_way(self, tmp_path: pathlib.Path) -> None:
        small, _ = self._class_modules(tmp_path)

        lines, index = inspect.findsource(small.K)

        assert lines[index] == "class K:\n"
        assert inspect.getsource(small.K) == "class K:\n    pass\n"


class TestStackContextReadsSource:
    """`stack(context=1)` looks a frame's source up; `stack(0)` does not.

    Counting `linecache.getlines` separates them with no tolerance: one call
    per frame against none at all, whatever either costs.
    """

    DEPTH = 20

    @staticmethod
    def _recurse(remaining: int, then: Callable[[], Any]) -> Any:
        if remaining:
            return TestStackContextReadsSource._recurse(remaining - 1, then)
        return then()

    def test_the_default_reads_once_per_frame(self) -> None:
        with CountingGetlines() as counter:
            frames = self._recurse(self.DEPTH, lambda: inspect.stack())

        assert len(counter.files) == len(frames)
        assert frames[0].code_context is not None
        assert frames[0].index == 0

    def test_context_zero_reads_nothing(self) -> None:
        with CountingGetlines() as counter:
            frames = self._recurse(self.DEPTH, lambda: inspect.stack(0))

        assert counter.files == []
        assert frames[0].code_context is None
        assert frames[0].index is None

    def test_both_describe_the_same_frames(self) -> None:
        default = self._recurse(self.DEPTH, lambda: inspect.stack())
        lean = self._recurse(self.DEPTH, lambda: inspect.stack(0))

        assert len(default) == len(lean)
        assert [frame.function for frame in default] == [frame.function for frame in lean]
        assert default[0].function == "<lambda>"
        assert default[1].function == "_recurse"

    def test_getframeinfo_with_no_context_reads_nothing(self) -> None:
        frame = inspect.currentframe()
        assert frame is not None
        try:
            with CountingGetlines() as counter:
                info = inspect.getframeinfo(frame, 0)
        finally:
            del frame

        assert counter.files == []
        assert info.code_context is None
        assert info.function == "test_getframeinfo_with_no_context_reads_nothing"

    @staticmethod
    def _deep_function(statements: int) -> Any:
        """A function whose call to `probe` sits `statements` instructions in."""
        source = (
            "def spread(probe):\n"
            "    total = 0\n"
            + "".join(f"    total += {n}\n" for n in range(statements))
            + "    return probe()\n"
        )  # probe() is called `statements` instructions into the frame
        namespace: dict[str, Any] = {}
        exec(compile(source, "<probe>", "exec"), namespace)
        return namespace["spread"]

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="positions arrived in 3.11")
    def test_context_zero_still_walks_to_the_current_instruction(self) -> None:
        """The x term: context=0 skips the source read, not the position table."""

        def measure(statements: int) -> float:
            def probe() -> float:
                frame = sys._getframe(1)
                try:
                    return best_us(lambda f=frame: inspect.getframeinfo(f, 0), inner=300)
                finally:
                    del frame

            return self._deep_function(statements)(probe)

        measured = {"near": measure(1), "far": measure(4_000)}

        assert measured["far"] > 5 * measured["near"], (
            f"4,000 instructions in cost {measured['far'] / measured['near']:.1f}x "
            f"({measured['near']:.1f}us)"
        )

    @pytest.mark.timing
    def test_the_line_number_alone_walks_the_line_table(self) -> None:
        """The x term without the 3.11 position walk: `f_lineno` on every version."""

        def measure(statements: int) -> float:
            def probe() -> float:
                frame = sys._getframe(1)
                try:
                    return best_us(lambda f=frame: inspect.getlineno(f), inner=20_000)
                finally:
                    del frame

            return self._deep_function(statements)(probe)

        measured = {"near": measure(1), "far": measure(4_000)}

        assert measured["far"] > 5 * measured["near"], (
            f"4,000 instructions in cost {measured['far'] / measured['near']:.1f}x "
            f"({measured['near']:.3f}us)"
        )

    def test_trace_walks_the_handled_traceback(self) -> None:
        def fails() -> None:
            raise ValueError("boom")

        try:
            fails()
        except ValueError:
            frames = inspect.trace(0)
        else:
            raise AssertionError("the call did not raise")

        assert [frame.function for frame in frames][-1] == "fails"
        assert frames[0].function == "test_trace_walks_the_handled_traceback"


class TestGetmoduleUsesDunderModule:
    """`getmodule()` | O(1) | O(1), O(M) on the first code object.

    Observed against `inspect.modulesbyfile`, the map the scan fills: an
    object carrying `__module__` leaves it untouched, one without fills it
    from `sys.modules`. The probe runs in a fresh interpreter because
    emptying that map by hand does not reset the scan - `getmodule()` keeps a
    second map of the modules it has already walked, and skips them next time.
    """

    PROBE = textwrap.dedent(
        """
        import inspect, json, sys

        before = len(inspect.modulesbyfile)
        by_module = inspect.getmodule(inspect.Signature) is inspect
        after_class = len(inspect.modulesbyfile)

        # Snapshot the file-backed modules before the scan, so the assertion is
        # about what the scan had to cover rather than about a later import.
        expected = {
            inspect.getabsfile(m)
            for m in list(sys.modules.values())
            if inspect.ismodule(m) and getattr(m, "__file__", None)
        }

        code = inspect.getdoc.__code__
        by_file = inspect.getmodule(code) is inspect
        after_code = len(inspect.modulesbyfile)

        print(json.dumps({
            "before": before,
            "by_module": by_module,
            "after_class": after_class,
            "has_dunder": hasattr(code, "__module__"),
            "by_file": by_file,
            "after_code": after_code,
            "expected": len(expected),
            "unmapped": sorted(expected - set(inspect.modulesbyfile))[:5],
        }))
        """
    )

    def test_an_unresolvable_file_is_never_cached(self) -> None:
        """Only matches reach `modulesbyfile`, so a miss has nothing to reuse."""
        stranger = compile("x = 1", "/nonexistent/probe.py", "exec")
        path = inspect.getabsfile(stranger)

        for _ in range(3):
            assert inspect.getmodule(stranger) is None
            assert path not in inspect.modulesbyfile, (
                "a failed lookup was cached, which would make the next call cheap"
            )

    @pytest.mark.timing
    def test_dunder_module_is_the_only_cheap_path(self) -> None:
        """The row's O(1): it belongs to `__module__`, not to the file map."""
        stranger = compile("x = 1", "/nonexistent/probe.py", "exec")

        by_name = best_us(lambda: inspect.getmodule(inspect.Signature), inner=2_000)
        by_scan = best_us(lambda: inspect.getmodule(stranger), inner=20)

        assert by_scan > 20 * by_name, (
            f"the scan cost {by_scan / by_name:.1f}x the __module__ lookup ({by_name:.2f}us)"
        )

    def test_only_a_code_object_triggers_the_scan(self, tmp_path: pathlib.Path) -> None:
        import json

        result = _run_block(self.PROBE, tmp_path)
        assert result.returncode == 0, result.stderr
        probe = json.loads(result.stdout)

        assert probe["before"] == 0
        assert probe["by_module"] is True
        assert probe["after_class"] == 0, "resolving through __module__ scanned sys.modules"

        assert probe["has_dunder"] is False
        assert probe["by_file"] is True
        assert probe["expected"] > 1
        assert probe["unmapped"] == [], (
            f"the scan left these file-backed modules unmapped: {probe['unmapped']}"
        )


class TestFrameLocalsAcrossVersions:
    """Python 3.13+ hands back a live proxy; earlier versions a snapshot dict.

    Asserted by write-through behaviour rather than by type name, so the test
    fails if a later release returns something that only looks like a proxy.
    """

    @staticmethod
    def _capture(alpha: int, beta: int = 2, *extra: int, **options: Any) -> Any:
        frame = inspect.currentframe()
        assert frame is not None
        try:
            return inspect.getargvalues(frame)
        finally:
            del frame

    def test_the_names_come_from_the_code_object(self) -> None:
        info = self._capture(1, 2, 3, flag=True)

        assert info.args == ["alpha", "beta"]
        assert info.varargs == "extra"
        assert info.keywords == "options"
        assert info.locals["alpha"] == 1
        assert info.locals["extra"] == (3,)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="PEP 667 proxy is Python 3.13+")
    def test_locals_are_a_live_proxy(self) -> None:
        def probe() -> tuple[Any, int]:
            marker = 1
            frame = inspect.currentframe()
            assert frame is not None
            try:
                local_view = inspect.getargvalues(frame).locals
                local_view["marker"] = 99
                return local_view, marker
            finally:
                del frame

        view, observed = probe()

        assert not isinstance(view, dict)
        assert observed == 99, "the write did not reach the frame"

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="the snapshot dict ended in 3.13")
    def test_locals_are_a_snapshot_dict(self) -> None:
        def probe() -> tuple[Any, int]:
            marker = 1
            frame = inspect.currentframe()
            assert frame is not None
            try:
                local_view = inspect.getargvalues(frame).locals
                local_view["marker"] = 99
                return local_view, marker
            finally:
                del frame

        view, observed = probe()

        assert isinstance(view, dict)
        assert observed == 1, "the write reached the frame after all"


class TestGeneratorStateIsFlags:
    """`getgeneratorstate()` and `getgeneratorlocals()` | O(1) | O(1)."""

    @staticmethod
    def _counter() -> Generator[int, None, None]:
        def generate() -> Generator[int, None, None]:
            total = 0
            for step in range(3):
                total += step
                yield total

        return generate()

    def test_the_four_states_in_order(self) -> None:
        seen: list[str] = []

        def generate() -> Generator[int, None, None]:
            seen.append(inspect.getgeneratorstate(running))
            yield 1

        running = generate()
        assert inspect.getgeneratorstate(running) == inspect.GEN_CREATED

        next(running)
        assert seen == [inspect.GEN_RUNNING], "the generator did not observe itself running"
        assert inspect.getgeneratorstate(running) == inspect.GEN_SUSPENDED

        running.close()
        assert inspect.getgeneratorstate(running) == inspect.GEN_CLOSED

    def test_locals_come_from_the_suspended_frame(self) -> None:
        generator = self._counter()
        assert inspect.getgeneratorlocals(generator) == {}

        next(generator)
        assert inspect.getgeneratorlocals(generator) == {"total": 0, "step": 0}

        generator.close()
        assert inspect.getgeneratorlocals(generator) == {}

    def test_a_non_generator_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="not a Python generator"):
            inspect.getgeneratorlocals(iter([1]))  # type: ignore[arg-type]


class TestPredicatesAgreeWithTheTypes:
    """The `is*()` rows | O(1) | O(1).

    A breadth check rather than a cost check: each predicate is asserted
    against something it should accept and something it should not, so a row
    priced O(1) is at least a row that answers correctly.
    """

    def test_the_concrete_type_predicates(self) -> None:
        def function() -> None: ...

        frame = inspect.currentframe()
        assert frame is not None
        try:
            assert inspect.isfunction(function) and not inspect.isfunction(len)
            assert inspect.isbuiltin(len) and not inspect.isbuiltin(function)
            assert inspect.isclass(int) and not inspect.isclass(1)
            assert inspect.ismodule(inspect) and not inspect.ismodule(int)
            assert inspect.iscode(function.__code__) and not inspect.iscode(function)
            assert inspect.isframe(frame) and not inspect.isframe(function)
            assert inspect.ismethod(self.test_the_concrete_type_predicates)
            assert not inspect.ismethod(function)
            assert inspect.isroutine(len) and inspect.isroutine(function)
            assert not inspect.isroutine(int)
        finally:
            del frame

    def test_the_descriptor_predicates(self) -> None:
        class Holder:
            __slots__ = ("slot",)

        assert inspect.ismethoddescriptor(str.upper)
        assert not inspect.ismethoddescriptor(property())
        assert inspect.isdatadescriptor(property())
        assert not inspect.isdatadescriptor(str.upper)

        class DeleteOnly:
            def __get__(self, obj: Any, owner: Any = None) -> int:
                return 1

            def __delete__(self, obj: Any) -> None: ...

        # 3.13 made the two mutually exclusive for this shape; before it, both held
        assert inspect.isdatadescriptor(DeleteOnly())
        assert inspect.ismethoddescriptor(DeleteOnly()) is (sys.version_info < (3, 13))
        assert inspect.ismemberdescriptor(Holder.slot)
        assert inspect.isgetsetdescriptor(vars(type(len))["__qualname__"])
        if sys.version_info >= (3, 11):
            ismethodwrapper = inspect.ismethodwrapper  # type: ignore[attr-defined]
            assert ismethodwrapper(object().__str__)
            assert not ismethodwrapper(len)

    def test_the_awaitable_predicates(self) -> None:
        async def coro() -> int:
            return 1

        async def agen_source() -> AsyncGenerator[int, None]:
            yield 1

        running = coro()
        agen = agen_source()
        try:
            assert inspect.iscoroutine(running) and inspect.isawaitable(running)
            assert inspect.iscoroutinefunction(coro) and not inspect.iscoroutinefunction(
                agen_source
            )
            assert inspect.isasyncgen(agen) and inspect.isasyncgenfunction(agen_source)
            assert not inspect.isawaitable(agen)
        finally:
            running.close()
            agen.aclose().close()  # type: ignore[attr-defined]

    def test_generator_and_traceback_predicates(self) -> None:
        def generate() -> Generator[int, None, None]:
            yield 1

        generator = generate()
        try:
            assert inspect.isgenerator(generator) and inspect.isgeneratorfunction(generate)
            assert not inspect.isgenerator(generate)
        finally:
            generator.close()

        try:
            raise ValueError("boom")
        except ValueError as error:
            assert inspect.istraceback(error.__traceback__)

    def test_abstract_and_package_predicates(self) -> None:
        import abc
        import xml

        class Abstract(abc.ABC):
            @abc.abstractmethod
            def required(self) -> None: ...

        assert inspect.isabstract(Abstract)
        assert not inspect.isabstract(int)
        with pytest.raises(TypeError, match="abstract"):
            Abstract()  # type: ignore[abstract]

        if sys.version_info >= (3, 14):
            assert inspect.ispackage(xml)
            assert not inspect.ispackage(inspect)
            assert not inspect.ispackage(int)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="markcoroutinefunction is Python 3.12+")
    def test_marking_a_plain_function(self) -> None:
        def returns_awaitable(alpha: int) -> int:
            return alpha

        assert inspect.iscoroutinefunction(returns_awaitable) is False
        mark = inspect.markcoroutinefunction  # type: ignore[attr-defined]
        assert mark(returns_awaitable) is returns_awaitable
        assert inspect.iscoroutinefunction(returns_awaitable) is True
        assert inspect.isfunction(returns_awaitable) is True


class TestArgumentSpecs:
    """`getfullargspec()`, `getargs()`, `getcallargs()`, `formatargvalues()` | O(p)."""

    @staticmethod
    def _target(template: str, *rows: str, width: int = 80, **attrs: Any) -> str:
        return template

    def test_getfullargspec_flattens_the_signature(self) -> None:
        spec = inspect.getfullargspec(self._target)

        assert spec.args == ["template"]
        assert spec.varargs == "rows"
        assert spec.varkw == "attrs"
        assert spec.kwonlyargs == ["width"]
        assert spec.kwonlydefaults == {"width": 80}
        assert spec.defaults is None

    @staticmethod
    def _with_locals(count: int) -> Any:
        """A two-parameter function carrying `count` unrelated local variables."""
        body = "\n".join(f"    local{index} = 1" for index in range(count))
        namespace: dict[str, Any] = {}
        exec(compile(f"def g(alpha, beta):\n{body}\n    return alpha", "<p>", "exec"), namespace)
        return namespace["g"]

    @pytest.mark.timing
    def test_co_varnames_costs_the_locals_on_3_11_alone(self) -> None:
        """A boundary in the middle of the range: cached, rebuilt, cached again."""
        few, many = self._with_locals(5), self._with_locals(2_000)
        code_few, code_many = few.__code__, many.__code__

        assert (code_many.co_varnames is code_many.co_varnames) == (
            sys.version_info[:2] != (3, 11)
        ), "the tuple's identity should track the version the page names"

        near = best_us(lambda: inspect.getargs(code_few), inner=2_000)
        far = best_us(lambda: inspect.getargs(code_many), inner=2_000)

        if sys.version_info[:2] == (3, 11):
            assert far > 4 * near, f"400x the locals cost {far / near:.1f}x ({near:.2f}us)"
        else:
            assert far < 2 * near, f"400x the locals cost {far / near:.1f}x ({near:.2f}us)"

    @pytest.mark.timing
    def test_the_signature_family_shares_the_3_11_rebuild(self) -> None:
        """`signature()` reads the same attribute, so it moves on 3.11 alone."""
        few, many = self._with_locals(5), self._with_locals(2_000)
        assert len(inspect.signature(many).parameters) == 2, "the locals changed p"

        near = best_us(lambda: inspect.signature(few), inner=2_000)
        far = best_us(lambda: inspect.signature(many), inner=2_000)

        if sys.version_info[:2] == (3, 11):
            assert far > 2 * near, f"400x the locals cost {far / near:.1f}x ({near:.2f}us)"
        else:
            assert far < 1.5 * near, f"400x the locals cost {far / near:.1f}x ({near:.2f}us)"

    def test_getargs_reads_the_code_object(self) -> None:
        arguments = inspect.getargs(self._target.__code__)

        assert arguments.args == ["template", "width"]
        assert arguments.varargs == "rows"
        assert arguments.varkw == "attrs"

        with pytest.raises(TypeError, match="not a code object"):
            inspect.getargs(self._target)  # type: ignore[arg-type]

    def test_getcallargs_applies_the_binding_rules(self) -> None:
        assert inspect.getcallargs(self._target, "report", "a") == {
            "template": "report",
            "rows": ("a",),
            "width": 80,
            "attrs": {},
        }

    def test_getcallargs_does_not_see_positional_only_parameters(self) -> None:
        def positional_only(alpha, /, beta):
            return alpha

        # getfullargspec folds positional-only parameters in with the rest ...
        assert inspect.getfullargspec(positional_only).args == ["alpha", "beta"]
        bound = inspect.getcallargs(positional_only, alpha=1, beta=2)  # type: ignore[call-arg]
        assert bound == {"alpha": 1, "beta": 2}

        # ... so getcallargs binds what the call itself rejects, and bind() does not.
        # The wording moved between supported versions; the rejection did not.
        with pytest.raises(TypeError, match="positional[- ]only"):
            positional_only(alpha=1, beta=2)  # type: ignore[call-arg]
        with pytest.raises(TypeError, match="positional[- ]only"):
            inspect.signature(positional_only).bind(alpha=1, beta=2)

    def test_bind_collects_every_variadic_argument(self) -> None:
        def variadic(*rows, **attrs):
            return rows

        bound = inspect.signature(variadic).bind(*range(50), **{f"k{n}": n for n in range(50)})

        assert len(bound.args) == 50, "one *rows parameter holds all 50 arguments"
        assert len(bound.kwargs) == 50

    def test_bind_partial_tolerates_what_bind_rejects(self) -> None:
        signature = inspect.signature(self._target)

        assert signature.bind_partial().arguments == {}
        with pytest.raises(TypeError, match="template"):
            signature.bind()

    def test_apply_defaults_fills_the_rest(self) -> None:
        bound = inspect.signature(self._target).bind("report")
        assert "width" not in bound.arguments

        bound.apply_defaults()

        assert bound.arguments["width"] == 80
        assert bound.arguments["rows"] == ()

    def test_replace_leaves_the_original_alone(self) -> None:
        signature = inspect.signature(self._target)

        narrowed = signature.replace(return_annotation=int)

        assert narrowed.return_annotation is int
        assert signature.return_annotation == "str"
        assert narrowed is not signature

        parameter = signature.parameters["width"]
        assert parameter.replace(default=1).default == 1
        assert parameter.default == 80

    @staticmethod
    def _wide(parameters: int) -> Any:
        """A function of `parameters` arguments that hands its frame to a probe."""
        names = ", ".join(f"arg{index}" for index in range(parameters))
        namespace: dict[str, Any] = {}
        exec(
            compile(f"def wide({names}, probe):\n    return probe()\n", "<probe>", "exec"),
            namespace,
        )
        return namespace["wide"]

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the frame proxy is Python 3.13+")
    def test_formatargvalues_pays_per_lookup_through_the_frame_proxy(self) -> None:
        """The p.v term: each name is looked up in a proxy that scans the frame."""

        def measure(width: int) -> float:
            def probe() -> float:
                frame = sys._getframe(1)
                try:
                    info = inspect.getargvalues(frame)
                    return best_us(lambda: inspect.formatargvalues(*info), inner=100)
                finally:
                    del frame

            return self._wide(width)(*([1] * width), probe)

        measured = {"near": measure(100), "far": measure(1_600)}

        assert measured["far"] > 20 * measured["near"], (
            f"16x the parameters cost {measured['far'] / measured['near']:.1f}x "
            f"({measured['near']:.1f}us)"
        )

    def test_formatargvalues_renders_every_bound_value(self) -> None:
        def probe(alpha: int, beta: int = 2, *extra: int, **options: Any) -> str:
            frame = inspect.currentframe()
            assert frame is not None
            try:
                return inspect.formatargvalues(*inspect.getargvalues(frame))
            finally:
                del frame

        assert (
            probe(1, 2, 3, flag=True) == "(alpha=1, beta=2, *extra=(3,), **options={'flag': True})"
        )

    @staticmethod
    def _annotated(members: int) -> type:
        """A class with one annotation and `members` unrelated attributes."""
        body: dict[str, Any] = {f"member{n}": n for n in range(members)}
        body["__annotations__"] = {"only": int}
        return type("Probe", (object,), body)

    @pytest.mark.timing
    @pytest.mark.skipif(
        sys.version_info >= (3, 14), reason="3.14 reaches annotations without the copy"
    )
    def test_get_annotations_copies_a_class_dict_before_3_14(self) -> None:
        """The h term: one annotation either way, 500x the unrelated members."""
        small, large = self._annotated(10), self._annotated(5_000)
        assert len(inspect.get_annotations(large)) == 1

        near = best_us(lambda: inspect.get_annotations(small), inner=500)
        far = best_us(lambda: inspect.get_annotations(large), inner=500)

        assert far > 20 * near, f"500x the members cost {far / near:.1f}x ({near:.2f}us)"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the copy ended in 3.14")
    def test_get_annotations_ignores_the_class_dict_from_3_14(self) -> None:
        small, large = self._annotated(10), self._annotated(5_000)

        near = best_us(lambda: inspect.get_annotations(small), inner=500)
        far = best_us(lambda: inspect.get_annotations(large), inner=500)

        assert far < 3 * near, f"500x the members cost {far / near:.1f}x ({near:.2f}us)"

    def test_get_annotations_builds_a_fresh_dict(self) -> None:
        def annotated(alpha: int, beta: str) -> bool:
            return True

        first = inspect.get_annotations(annotated)
        assert first == {"alpha": "int", "beta": "str", "return": "bool"}
        assert first is not inspect.get_annotations(annotated)

        evaluated = inspect.get_annotations(annotated, eval_str=True)
        assert evaluated == {"alpha": int, "beta": str, "return": bool}

    def test_eval_str_unwinds_the_wrapper_chain(self) -> None:
        """The w term: `eval_str=True` finds the globals through `__wrapped__`."""
        import functools

        namespace: dict[str, Any] = {}
        exec(
            "from __future__ import annotations\n"
            "class Target: pass\n"
            "def inner(alpha: Target) -> Target: return alpha\n",
            namespace,
        )
        inner = namespace["inner"]

        wrapped: Any = inner
        for _ in range(8):
            wrapped = functools.wraps(wrapped)(lambda *a, **k: None)

        # The wrapper's own globals are this test module's, where Target is unknown;
        # only walking to `inner` finds the namespace the annotation names.
        assert inspect.get_annotations(wrapped, eval_str=True) == {
            "alpha": namespace["Target"],
            "return": namespace["Target"],
        }


class TestSourceHelpers:
    """`getblock()`, `indentsize()`, `getcomments()`, `getmodulename()` | small and local."""

    def test_getblock_stops_at_the_block(self) -> None:
        lines = ["def one():\n", "    return 1\n", "def two():\n", "    return 2\n"]

        assert inspect.getblock(lines) == ["def one():\n", "    return 1\n"]

    def test_indentsize_expands_tabs(self) -> None:
        assert inspect.indentsize("    x") == 4
        assert inspect.indentsize("\tx") == 8
        assert inspect.indentsize("x") == 0

    def test_getmodulename_matches_import_suffixes(self) -> None:
        assert inspect.getmodulename("/tmp/thing.py") == "thing"
        assert inspect.getmodulename("/tmp/thing.txt") is None

    def test_getcomments_reads_the_block_above(self, tmp_path: pathlib.Path) -> None:
        import importlib.util

        path = tmp_path / "commented.py"
        path.write_text("# first\n# second\ndef target():\n    return 1\n", encoding="utf-8")
        spec = importlib.util.spec_from_file_location("commented", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["commented"] = module
        spec.loader.exec_module(module)

        assert inspect.getcomments(module.target) == "# first\n# second\n"

    @pytest.mark.timing
    def test_cleandoc_pays_extra_for_leading_blank_lines(self) -> None:
        """The z.L term: the same character count, moved to the front as blanks."""
        body = "text\n" * 2_000
        few = "\n" * 200 + body
        many = "\n" * 20_000 + body

        near = best_us(lambda: inspect.cleandoc(few), inner=20)
        far = best_us(lambda: inspect.cleandoc(many), inner=20)

        assert len(many) < 12 * len(few), "the two inputs differ by more than the blanks"
        assert far > 12 * near, f"100x the leading blanks cost {far / near:.1f}x ({near:.1f}us)"

    def test_cleandoc_removes_the_common_margin(self) -> None:
        assert inspect.cleandoc("a\n    b\n      c\n") == "a\nb\n  c"
        assert inspect.cleandoc("\n\n  only\n\n") == "only"


class TestRemainingReferenceRows:
    """The reference rows the behavioural classes above do not reach.

    Each asserts what its Notes cell says on a fixed input, so a row is at
    least a row whose contract holds. These are behavioural checks, not
    measurements: where the row grows - `Signature(parameters)` in p, the
    annotation formatters in the rendered length - the growth is the ordinary
    "builds a result of that size" kind, stated in the module docstring rather
    than timed.
    """

    def test_signature_can_be_built_and_validated_by_hand(self) -> None:
        parameters = [
            inspect.Parameter("alpha", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("beta", inspect.Parameter.KEYWORD_ONLY, default=2),
        ]
        signature = inspect.Signature(parameters, return_annotation=int)

        assert str(signature) == "(alpha, *, beta=2) -> int"
        assert signature.parameters["beta"].default == 2
        assert signature.parameters["alpha"].annotation is inspect.Parameter.empty
        assert inspect.Parameter.empty is inspect.Signature.empty

        with pytest.raises(ValueError, match="wrong parameter order"):
            inspect.Signature(list(reversed(parameters)))

    def test_from_callable_agrees_with_signature(self) -> None:
        def target(alpha, beta=1):
            return alpha

        assert inspect.Signature.from_callable(target) == inspect.signature(target)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Signature.format is Python 3.13+")
    def test_format_renders_the_signature(self) -> None:
        def target(alpha, beta=1):
            return alpha

        signature = inspect.signature(target)
        rendered = signature.format()  # type: ignore[attr-defined]

        assert rendered == str(signature) == "(alpha, beta=1)"

        # quote_annotation_strings arrived a release after format() itself
        if sys.version_info >= (3, 14):
            assert signature.format(quote_annotation_strings=False) == rendered  # type: ignore[attr-defined]
        else:
            with pytest.raises(TypeError):
                signature.format(quote_annotation_strings=False)  # type: ignore[attr-defined,call-arg]

    def test_parameter_kinds_carry_a_description(self) -> None:
        def target(only_positional, /, either, *rest, keyword_only, **options):
            return either

        kinds = {name: p.kind for name, p in inspect.signature(target).parameters.items()}

        assert kinds["only_positional"].description == "positional-only"
        assert kinds["either"].description == "positional or keyword"
        assert kinds["rest"].description == "variadic positional"
        assert kinds["keyword_only"].description == "keyword-only"
        assert kinds["options"].description == "variadic keyword"

    def test_annotation_formatters(self) -> None:
        assert inspect.formatannotation(int) == "int"
        assert inspect.formatannotation(inspect.Signature) == "inspect.Signature"
        assert inspect.formatannotation(inspect.Signature, "inspect") == "Signature"

        relative = inspect.formatannotationrelativeto(inspect.getdoc)
        assert relative(inspect.Signature) == "Signature"
        assert relative(int) == "int"

    def test_getabsfile_normalises_the_path(self) -> None:
        import os

        absolute = inspect.getabsfile(inspect)

        assert os.path.isabs(absolute)
        assert absolute == os.path.normcase(os.path.abspath(inspect.__file__))

    def test_coroutine_state_and_locals(self) -> None:
        async def work() -> int:
            marker = 1
            return marker

        coroutine = work()
        try:
            assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CREATED
            assert inspect.getcoroutinelocals(coroutine) == {}
        finally:
            coroutine.close()
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="getasyncgenstate is Python 3.12+")
    def test_async_generator_state_and_locals(self) -> None:
        async def source() -> AsyncGenerator[int, None]:
            yield 1

        agen = source()
        try:
            getstate = inspect.getasyncgenstate  # type: ignore[attr-defined]
            getlocals = inspect.getasyncgenlocals  # type: ignore[attr-defined]
            assert getstate(agen) == inspect.AGEN_CREATED  # type: ignore[attr-defined]
            assert getlocals(agen) == {}
        finally:
            agen.aclose().close()  # type: ignore[attr-defined]

    def test_frame_records_carry_the_same_fields(self) -> None:
        frame = inspect.currentframe()
        assert frame is not None
        try:
            outer = inspect.getouterframes(frame, 1)
            info = inspect.getframeinfo(frame, 1)
        finally:
            del frame

        assert outer[0].function == info.function == "test_frame_records_carry_the_same_fields"
        assert outer[0].filename == info.filename == __file__
        assert outer[0].lineno > 0 and info.lineno > 0
        assert info.code_context is not None and len(info.code_context) == 1
        assert info.index == 0
        assert outer[0].frame.f_code.co_name == info.function

        if sys.version_info >= (3, 11):
            assert info.positions is not None
            assert info.positions.lineno is not None

    def test_getinnerframes_walks_the_traceback(self) -> None:
        def fails() -> None:
            raise ValueError("boom")

        try:
            fails()
        except ValueError as error:
            traceback = error.__traceback__
        else:
            raise AssertionError("the call did not raise")

        assert traceback is not None
        inner = inspect.getinnerframes(traceback, 0)

        assert [record.function for record in inner][-1] == "fails"
        assert inner[0].code_context is None

    def test_the_code_flags_match_the_code_objects(self) -> None:
        def generate() -> Generator[int, None, None]:
            yield 1

        async def coroutine() -> int:
            return 1

        async def asyncgen() -> AsyncGenerator[int, None]:
            yield 1

        def varied(*args: int, **kwargs: int) -> None: ...

        assert generate.__code__.co_flags & inspect.CO_GENERATOR
        assert coroutine.__code__.co_flags & inspect.CO_COROUTINE
        assert asyncgen.__code__.co_flags & inspect.CO_ASYNC_GENERATOR
        assert varied.__code__.co_flags & inspect.CO_VARARGS
        assert varied.__code__.co_flags & inspect.CO_VARKEYWORDS
        assert not varied.__code__.co_flags & inspect.CO_GENERATOR
        assert not generate.__code__.co_flags & inspect.CO_VARARGS
        assert generate.__code__.co_flags & inspect.CO_OPTIMIZED
        assert generate.__code__.co_flags & inspect.CO_NEWLOCALS

        coroutine().close()

    def test_the_abstract_type_flag(self) -> None:
        import abc

        class Abstract(abc.ABC):
            @abc.abstractmethod
            def required(self) -> None: ...

        assert Abstract.__flags__ & inspect.TPFLAGS_IS_ABSTRACT
        assert not int.__flags__ & inspect.TPFLAGS_IS_ABSTRACT

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="BufferFlags is Python 3.12+")
    def test_buffer_flags_are_an_int_flag(self) -> None:
        flags = inspect.BufferFlags  # type: ignore[attr-defined]

        assert int(flags.SIMPLE) == 0
        assert flags.WRITABLE in (flags.WRITABLE | flags.FORMAT)


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
    """Each block runs in its own subprocess and working directory, so the
    temporary modules several of them write, and the `modulesbyfile` cache one
    of them fills, cannot leak between them."""

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
        line, source = next((n, s) for n, s in _blocks() if "mro is Leaf.__mro__" in s)
        mutated = source.replace("mro is Leaf.__mro__", "mro is not Leaf.__mro__", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
