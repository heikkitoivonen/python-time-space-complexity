"""Tests for docs/stdlib/annotationlib.md.

The module exists from Python 3.14, so this file skips on older interpreters.
Its evidence is the 3.14 branch of Lib/annotationlib.py, the compiler's
generated `__annotate__` functions, which accept only the `VALUE` and
`VALUE_WITH_FAKE_GLOBALS` formats and raise `NotImplementedError` for the
rest, and the `__annotations__` descriptors on functions, classes and
modules, which call `__annotate__(VALUE)` once and keep the result.

Caching is observed with a counting call inside an annotation expression:
defining a class costs no call, the first `VALUE` access one, and every
later `VALUE` call, and every `FORWARDREF` call whose names all resolve,
none. Each `FORWARDREF` call with an unresolved name costs two: the `VALUE`
attempt that raises `NameError` partway, then the run under the substitute
namespace, whose `ForwardRef` results are new objects every time. Each
`STRING` call costs one from 3.14.1, where `call_annotate_function()` probes
the annotate function with `VALUE_WITH_FAKE_GLOBALS` under the real globals
before stringifying, which a counting call inside the annotation sees once
per `STRING` call and not at all when an earlier annotation raises; on every patch `sys.setprofile` sees the compiler's
`__annotate__` code object enter the same number of times on each `STRING`
call and not at all on a cached `VALUE` or `FORWARDREF` call. A class whose
`__annotations__` dict was assigned directly has no `__annotate__`, and its
`STRING` result holds the very string objects of that dict.

The hidden size terms are timed. Unresolved `FORWARDREF` merges the
builtins and the module's globals into a fresh dict on every call:
`get_annotations()` on a one-annotation function costs x325 for x10,000 in
`g` (11us to 3.5ms), where a bound without `g` predicts x1, and
`call_annotate_function(..., FORWARDREF)` pays it with every name resolved.
`STRING` runs under an empty namespace and does not move with `g`.
`ForwardRef.evaluate()` with a class owner copies the class namespace:
x1,100 for x10,000 in `m` (6us to 6.6ms), against x2 when `locals` is
given. `STRING` on a function with every name resolved costs x100 to x850
a cached `VALUE` call at 20 and 2,000 annotations, and x100 for x100 in `n`,
where a quadratic stringifier would cost x10,000. `type_repr()` of a tuple
costs x1,400 for x10,000 in `r`.

`get_annotate_from_class_namespace()` is counted on a dict subclass: one
lookup when `__annotate__` is present, two when it is absent, at any
namespace size. `ForwardRef.__code__` is empty before the first
`evaluate()` and the same object after the second, so the compile in `e` is
paid once per reference, and a bare name never fills it.

The `g` term's space is traced: a `FORWARDREF` call on the same
one-annotation function peaks at 14KB against 7.7MB for x10,000 in `g`.

The `e` term is timed on one subscript of 10 against 1,000 items, x91 in
source text: `STRING` costs x35, unresolved `FORWARDREF` x36 and
`ForwardRef.evaluate()` x51 with the compile, against x8,000 for a
quadratic pass. `evaluate()` on cached code is timed at 1,000 against
10,000 items, where the fixed cost of a call no longer dominates, and costs
x9 for x10; `eval_str=True`, which compiles on every call, costs x98 for
x100 in items.

Not varied: the shape of the expressions beyond that one subscript (no
nesting, attributes, operators or literals), the cost of a
call made inside an annotation, and the number of type parameters, closure
cells and wrapper layers an evaluation consults, none of which carries a
term on the page. The `l` term is timed on `ForwardRef.evaluate()` twice:
a given `locals` of 10 against 100,000 names costs x10,000 with a class
owner against x1 with no owner, and the `FORWARDREF` retry merges it again.
The copy is made when the type parameters are not `None`, which a class or
function owner's `__type_params__` tuple satisfies even when empty and a
module owner does not, or when the reference carries closure cells or extra
names; the page says only that the copy may happen, and the module-owner
and explicit-`type_params` cases are read from the source, not timed. The
copy that `eval_str=True` makes of a given `locals` for type parameters is
read from the source (a `|` merge) and not timed. The class-namespace copy of
`eval_str=True` is timed (x1,000 for x10,000 in `m`, and x2 with both
`globals` and `locals` given). The rows are about functions, classes
and modules, whose `__annotations__` descriptor is the cache; an object that
offers `__annotate__` alone has none and is not covered. The version
boundary at 3.14.1 is described above and not asserted, so the file holds on
every 3.14 patch.
"""

import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from typing import Any

import pytest

annotationlib: Any = pytest.importorskip("annotationlib")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "annotationlib.md"

Format = annotationlib.Format
ForwardRef = annotationlib.ForwardRef
get_annotations = annotationlib.get_annotations


def measure(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of several runs, with the collector held off during each."""
    best = float("inf")
    for _ in range(repeats):
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter()
            func()
            best = min(best, time.perf_counter() - start)
        finally:
            gc.enable()
    return best


def function_with(annotation: str, count: int = 1, extra_globals: int = 0) -> Any:
    """A function whose `count` parameters all carry `annotation`, defined in a
    namespace holding `extra_globals` other names."""
    namespace: dict[str, Any] = {f"name{i}": i for i in range(extra_globals)}
    params = ", ".join(f"a{i}: {annotation}" for i in range(count))
    exec(f"def fn({params}): pass", namespace)
    return namespace["fn"]


def class_with(annotation: str, namespace: dict[str, Any]) -> type:
    """A class with one annotated attribute, its body run in `namespace`."""
    exec(f"class C:\n    attr: {annotation}", namespace)
    return namespace["C"]


class Probe:
    """A call counter usable as `probe()` inside an annotation expression."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> type:
        self.calls += 1
        return int


class TestEvaluationIsDeferredThenCached:
    """The VALUE row and the section named after it."""

    def test_defining_a_class_evaluates_nothing(self) -> None:
        probe = Probe()

        class_with("probe()", {"probe": probe})

        assert probe.calls == 0

    def test_the_first_value_access_evaluates_once_and_later_calls_copy(self) -> None:
        probe = Probe()
        cls = class_with("probe()", {"probe": probe})

        first = get_annotations(cls)
        second = get_annotations(cls)

        assert probe.calls == 1
        assert first == {"attr": int}
        assert first is not second
        assert first["attr"] is second["attr"]

    def test_a_function_behaves_the_same(self) -> None:
        probe = Probe()
        fn = function_with("probe()")
        fn.__globals__["probe"] = probe

        get_annotations(fn)
        get_annotations(fn)

        assert probe.calls == 1

    def test_an_undefined_name_raises_on_the_first_access(self) -> None:
        fn = function_with("Undefined")

        with pytest.raises(NameError):
            get_annotations(fn)

    def test_eval_str_evaluates_on_every_call(self) -> None:
        probe = Probe()
        fn = function_with('"probe()"')
        fn.__globals__["probe"] = probe

        get_annotations(fn, eval_str=True)
        get_annotations(fn, eval_str=True)

        assert probe.calls == 2
        with pytest.raises(ValueError):
            get_annotations(fn, eval_str=True, format=Format.STRING)


class TestFormats:
    """The FORWARDREF and STRING rows: what each returns and what each reuses."""

    def test_forwardref_with_every_name_resolved_copies_the_cache(self) -> None:
        probe = Probe()
        fn = function_with("probe()")
        fn.__globals__["probe"] = probe
        cached = get_annotations(fn)

        result = get_annotations(fn, format=Format.FORWARDREF)

        assert probe.calls == 1
        assert result is not cached
        assert result["a0"] is cached["a0"]

    def test_forwardref_on_a_cold_object_evaluates_once_like_value(self) -> None:
        probe = Probe()
        fn = function_with("probe()")
        fn.__globals__["probe"] = probe

        first = get_annotations(fn, format=Format.FORWARDREF)
        second = get_annotations(fn)

        assert probe.calls == 1
        assert first["a0"] is second["a0"] is int

    def test_forwardref_with_an_unresolved_name_re_runs_on_every_call(self) -> None:
        probe = Probe()
        namespace: dict[str, Any] = {"probe": probe}
        exec("def fn(a0: probe(), a1: Undefined): pass", namespace)
        fn = namespace["fn"]

        first = get_annotations(fn, format=Format.FORWARDREF)
        second = get_annotations(fn, format=Format.FORWARDREF)

        assert first["a0"] is int
        assert isinstance(first["a1"], ForwardRef)
        assert first["a1"] == second["a1"]
        assert first["a1"] is not second["a1"]
        assert probe.calls == 4, "two evaluations per call: the VALUE attempt, then the re-run"

    def test_string_returns_new_strings_on_every_call(self) -> None:
        fn = function_with("list[int]")
        get_annotations(fn)

        first = get_annotations(fn, format=Format.STRING)
        second = get_annotations(fn, format=Format.STRING)

        assert first == {"a0": "list[int]"}
        assert first["a0"] is not second["a0"]

    def test_string_runs_the_annotate_code_on_every_call(self) -> None:
        """The profiler sees the compiler's `__annotate__` code object enter
        as many times on the second STRING call as on the first, and never on
        a VALUE or FORWARDREF call once the object is cached. Profiling changes
        interpreter-wide instrumentation state, so it runs in a subprocess."""
        script = textwrap.dedent("""
            import sys
            from annotationlib import Format, get_annotations

            def fn(a0: list[int]): pass

            get_annotations(fn)
            code = fn.__annotate__.__code__
            entries = []
            sys.setprofile(
                lambda frame, event, arg: entries.append(1)
                if event == "call" and frame.f_code is code
                else None
            )
            get_annotations(fn, format=Format.STRING)
            first = len(entries)
            get_annotations(fn, format=Format.STRING)
            second = len(entries) - first
            get_annotations(fn)
            get_annotations(fn, format=Format.FORWARDREF)
            sys.setprofile(None)
            print(first, second, len(entries) - first - second)
        """)

        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
        first, second, cached = map(int, result.stdout.split())

        assert first > 0
        assert second == first
        assert cached == 0

    def test_string_evaluates_a_call_under_the_real_globals_from_3_14_1(self) -> None:
        probe = Probe()
        fn = function_with("probe()")
        fn.__globals__["probe"] = probe
        get_annotations(fn)
        per_call = 1 if sys.version_info >= (3, 14, 1) else 0

        get_annotations(fn, format=Format.STRING)
        assert probe.calls == 1 + per_call
        get_annotations(fn, format=Format.STRING)
        assert probe.calls == 1 + 2 * per_call

        after_raise = Probe()
        namespace: dict[str, Any] = {"probe": after_raise}
        exec("def fn(a0: Undefined, a1: probe()): pass", namespace)
        strings = get_annotations(namespace["fn"], format=Format.STRING)
        assert strings == {"a0": "Undefined", "a1": "probe()"}
        assert after_raise.calls == 0, "the real-globals run stops at the first raise"

    def test_string_does_not_need_the_names_to_exist(self) -> None:
        fn = function_with("Undefined[int]")

        assert get_annotations(fn, format=Format.STRING) == {"a0": "Undefined[int]"}

    def test_string_works_on_a_module(self) -> None:
        module = types.ModuleType("m")
        exec("x: Undefined", module.__dict__)

        assert get_annotations(module, format=Format.STRING) == {"x": "Undefined"}
        assert isinstance(get_annotations(module, format=Format.FORWARDREF)["x"], ForwardRef)

    def test_string_without_an_annotate_function_passes_the_strings_through(self) -> None:
        cls: Any = type("Assigned", (), {"__annotations__": {"a0": "list[int]", "a1": int}})
        assert cls.__annotate__ is None

        result = get_annotations(cls, format=Format.STRING)

        assert result == {"a0": "list[int]", "a1": "int"}
        assert result["a0"] is cls.__annotations__["a0"]

    def test_the_internal_format_is_rejected(self) -> None:
        fn = function_with("int")

        with pytest.raises(ValueError):
            get_annotations(fn, format=Format.VALUE_WITH_FAKE_GLOBALS)
        with pytest.raises(ValueError):
            annotationlib.call_annotate_function(fn.__annotate__, Format.VALUE_WITH_FAKE_GLOBALS)

    def test_the_format_members_are_the_documented_ones(self) -> None:
        assert [member.name for member in Format] == [
            "VALUE",
            "VALUE_WITH_FAKE_GLOBALS",
            "FORWARDREF",
            "STRING",
        ]
        assert Format.VALUE == 1


class TestEvaluateFunctions:
    """The call_evaluate_function row, on a type alias and a type parameter."""

    @staticmethod
    def alias_and_parameter() -> tuple[Any, Any]:
        namespace: dict[str, Any] = {}
        exec("type Rows = list[Row]\nclass K[T: Bound]: pass", namespace)
        return namespace["Rows"], namespace["K"].__type_params__[0]

    def test_string_and_forwardref_return_one_value(self) -> None:
        alias, param = self.alias_and_parameter()
        call = annotationlib.call_evaluate_function

        assert call(alias.evaluate_value, Format.STRING) == "list[Row]"
        assert call(param.evaluate_bound, Format.STRING) == "Bound"
        partial = call(alias.evaluate_value, Format.FORWARDREF)
        assert str(partial) == "list[ForwardRef('Row')]"
        bound = call(param.evaluate_bound, Format.FORWARDREF)
        assert isinstance(bound, ForwardRef)
        assert bound.__forward_arg__ == "Bound"

    def test_value_raises_for_the_undefined_name(self) -> None:
        alias, _ = self.alias_and_parameter()

        with pytest.raises(NameError):
            annotationlib.call_evaluate_function(alias.evaluate_value, Format.VALUE)


class TestForwardRef:
    """The ForwardRef rows: lookup order, the cached compile, and the formats."""

    def test_a_bare_name_resolves_through_locals_globals_then_builtins(self) -> None:
        ref = ForwardRef("int")

        assert ref.evaluate(locals={"int": str}) is str
        assert ref.evaluate(globals={"int": float}) is float
        assert ref.evaluate(locals={"int": str}, globals={"int": float}) is str
        assert ref.evaluate() is int

    def test_a_class_owner_supplies_its_namespace_unless_locals_is_given(self) -> None:
        class Model:
            Id = int

        ref = ForwardRef("Id", owner=Model)

        assert ref.evaluate() is int
        assert ref.evaluate(locals={"Id": str}) is str
        with pytest.raises(NameError):
            ref.evaluate(locals={})

    def test_the_expression_is_compiled_once(self) -> None:
        ref = ForwardRef("list[int]")

        assert ref.__code__ is None
        assert ref.evaluate() == list[int]
        code = ref.__code__
        assert code is not None
        assert ref.evaluate() == list[int]
        assert ref.__code__ is code
        bare = ForwardRef("int")
        assert bare.evaluate() is int
        assert bare.__code__ is None, "a bare name is never compiled"

    def test_string_returns_the_source_and_forwardref_returns_the_reference(self) -> None:
        ref = ForwardRef("Missing[int]")

        assert ref.evaluate(format=Format.STRING) == "Missing[int]"
        with pytest.raises(NameError):
            ref.evaluate()
        retried = ref.evaluate(format=Format.FORWARDREF)
        assert isinstance(retried, ForwardRef)
        assert retried.__forward_arg__.startswith("Missing[")
        bare = ForwardRef("Missing")
        assert bare.evaluate(format=Format.FORWARDREF) is bare
        partial = ForwardRef("list[Missing]").evaluate(format=Format.FORWARDREF)
        assert str(partial) == "list[ForwardRef('Missing')]"
        failing = ForwardRef("1 / 0")
        assert failing.evaluate(format=Format.FORWARDREF) is failing


class TestLookupsAndReprs:
    """The get_annotate_from_class_namespace, annotations_to_string and type_repr rows."""

    def test_the_namespace_lookup_costs_one_or_two_lookups_at_any_size(self) -> None:
        lookups = 0

        class Counting(dict[str, Any]):
            def __getitem__(self, key: str) -> Any:
                nonlocal lookups
                lookups += 1
                return super().__getitem__(key)

            def get(self, key: str, default: Any = None) -> Any:
                nonlocal lookups
                lookups += 1
                return super().get(key, default)

        primary, fallback = function_with("int").__annotate__, function_with("str").__annotate__
        namespace = Counting({f"k{i}": i for i in range(10_000)})

        assert annotationlib.get_annotate_from_class_namespace(namespace) is None
        assert lookups == 2
        namespace["__annotate_func__"] = fallback
        assert annotationlib.get_annotate_from_class_namespace(namespace) is fallback
        assert lookups == 4
        namespace["__annotate__"] = primary
        assert annotationlib.get_annotate_from_class_namespace(namespace) is primary
        assert lookups == 5

    def test_type_repr_uses_the_qualified_name_ellipsis_or_repr(self) -> None:
        type_repr = annotationlib.type_repr

        assert type_repr(int) == "int"
        assert type_repr(ForwardRef) == "annotationlib.ForwardRef"
        assert type_repr(measure) == f"{measure.__module__}.measure"
        assert type_repr(len) == "len"
        assert type_repr(...) == "..."
        assert type_repr("x") == "'x'"
        assert type_repr((1, 2)) == "(1, 2)"
        namespace: dict[str, Any] = {"x": 1}
        exec('template = t"n={x}"', namespace)
        assert type_repr(namespace["template"]) == "t'n={x}'"

    def test_annotations_to_string_returns_a_new_dict_and_passes_strings_through(self) -> None:
        source = {"a": int, "b": "Row", "c": ...}

        result = annotationlib.annotations_to_string(source)

        assert result == {"a": "int", "b": "Row", "c": "..."}
        assert result is not source
        assert result["b"] is source["b"]


@pytest.mark.timing
class TestSizeTerms:
    """The g, m, r and n terms, each varied with the others held fixed."""

    def test_unresolved_forwardref_grows_with_the_globals(self) -> None:
        small = function_with("Undefined", extra_globals=10)
        large = function_with("Undefined", extra_globals=100_000)

        t_small = measure(lambda: get_annotations(small, format=Format.FORWARDREF))
        t_large = measure(lambda: get_annotations(large, format=Format.FORWARDREF))
        ratio = t_large / t_small

        assert 20 < ratio < 20_000, (
            f"x10,000 in g cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )

    def test_unresolved_forwardref_allocates_with_the_globals(self) -> None:
        small = function_with("Undefined", extra_globals=10)
        large = function_with("Undefined", extra_globals=100_000)
        peaks: list[int] = []
        for fn in (small, large):
            get_annotations(fn, format=Format.FORWARDREF)
            tracemalloc.start()
            try:
                get_annotations(fn, format=Format.FORWARDREF)
                peaks.append(tracemalloc.get_traced_memory()[1])
            finally:
                tracemalloc.stop()
        ratio = peaks[1] / peaks[0]

        assert 50 < ratio < 20_000, f"x10,000 in g peaked x{ratio:.1f} ({peaks})"

    def test_call_annotate_function_forwardref_pays_the_merge_with_every_name_resolved(
        self,
    ) -> None:
        small = function_with("int", extra_globals=10)
        large = function_with("int", extra_globals=100_000)
        call = annotationlib.call_annotate_function

        t_small = measure(lambda: call(small.__annotate__, Format.FORWARDREF))
        t_large = measure(lambda: call(large.__annotate__, Format.FORWARDREF))
        ratio = t_large / t_small
        t_value = measure(lambda: call(large.__annotate__, Format.VALUE))

        assert 20 < ratio < 20_000, (
            f"x10,000 in g cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )
        assert t_large / t_value > 20, f"VALUE {t_value:.2e}s, FORWARDREF {t_large:.2e}s"

    def test_string_does_not_grow_with_the_globals(self) -> None:
        small = function_with("Undefined", extra_globals=10)
        large = function_with("Undefined", extra_globals=100_000)

        t_small = measure(lambda: get_annotations(small, format=Format.STRING))
        t_large = measure(lambda: get_annotations(large, format=Format.STRING))
        ratio = t_large / t_small

        assert ratio < 5, f"x10,000 in g cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"

    def test_evaluate_with_a_class_owner_copies_its_namespace(self) -> None:
        small = type("Small", (), {f"attr{i}": i for i in range(10)})
        large = type("Large", (), {f"attr{i}": i for i in range(100_000)})
        ref_small = ForwardRef("int", owner=small)
        ref_large = ForwardRef("int", owner=large)

        t_small = measure(lambda: ref_small.evaluate())
        t_large = measure(lambda: ref_large.evaluate())
        ratio = t_large / t_small
        l_small = measure(lambda: ref_small.evaluate(locals={}))
        l_large = measure(lambda: ref_large.evaluate(locals={}))
        given = l_large / l_small

        assert 20 < ratio < 20_000, (
            f"x10,000 in m cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )
        assert given < 10, f"with locals given, x{given:.1f} ({l_small:.2e}s to {l_large:.2e}s)"

    def test_evaluate_copies_a_given_locals_with_a_class_owner_and_not_without(self) -> None:
        small = {f"name{i}": i for i in range(10)}
        large = {f"name{i}": i for i in range(100_000)}
        owned = ForwardRef("int", owner=type("Owner", (), {}))
        free = ForwardRef("int")

        o_small = measure(lambda: owned.evaluate(locals=small))
        o_large = measure(lambda: owned.evaluate(locals=large))
        f_small = measure(lambda: free.evaluate(locals=small))
        f_large = measure(lambda: free.evaluate(locals=large))
        with_owner = o_large / o_small
        without = f_large / f_small

        assert 20 < with_owner < 20_000, (
            f"x10,000 in l cost x{with_owner:.1f} ({o_small:.2e}s to {o_large:.2e}s)"
        )
        assert without < 10, f"without an owner, x{without:.1f} ({f_small:.2e}s to {f_large:.2e}s)"

    def test_evaluate_forwardref_fallback_grows_with_a_given_locals(self) -> None:
        small = {f"name{i}": i for i in range(10)}
        large = {f"name{i}": i for i in range(100_000)}
        ref = ForwardRef("Undefined[int]")

        t_small = measure(lambda: ref.evaluate(locals=small, format=Format.FORWARDREF))
        t_large = measure(lambda: ref.evaluate(locals=large, format=Format.FORWARDREF))
        ratio = t_large / t_small

        assert 20 < ratio < 20_000, (
            f"x10,000 in l cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )

    def test_evaluate_forwardref_fallback_grows_with_the_globals(self) -> None:
        small = {f"name{i}": i for i in range(10)}
        large = {f"name{i}": i for i in range(100_000)}
        ref = ForwardRef("Undefined[int]")

        t_small = measure(lambda: ref.evaluate(globals=small, format=Format.FORWARDREF))
        t_large = measure(lambda: ref.evaluate(globals=large, format=Format.FORWARDREF))
        ratio = t_large / t_small

        assert 20 < ratio < 20_000, (
            f"x10,000 in g cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )

    def test_string_costs_far_more_than_a_cached_value_call_and_is_linear_in_n(self) -> None:
        few = function_with("list[int]", count=20)
        many = function_with("list[int]", count=2_000)
        get_annotations(few)
        get_annotations(many)

        value = measure(lambda: get_annotations(many))
        string_many = measure(lambda: get_annotations(many, format=Format.STRING))
        string_few = measure(lambda: get_annotations(few, format=Format.STRING))
        against_value = string_many / value
        growth = string_many / string_few

        assert against_value > 30, f"STRING x{against_value:.0f} a cached VALUE ({value:.2e}s)"
        assert 20 < growth < 1_000, f"x100 in n cost x{growth:.1f}"

    def test_eval_str_copies_a_class_namespace_unless_both_namespaces_are_given(self) -> None:
        def class_of(size: int) -> type:
            attrs: dict[str, Any] = {f"attr{i}": i for i in range(size)}
            return type("C", (), attrs | {"__annotations__": {"a": "int"}})

        small, large = class_of(10), class_of(100_000)
        both = {"globals": {"int": int}, "locals": {}}

        t_small = measure(lambda: get_annotations(small, eval_str=True))
        t_large = measure(lambda: get_annotations(large, eval_str=True))
        ratio = t_large / t_small
        l_large = measure(lambda: get_annotations(large, eval_str=True, locals={}))
        b_small = measure(lambda: get_annotations(small, eval_str=True, **both))
        b_large = measure(lambda: get_annotations(large, eval_str=True, **both))
        given = b_large / b_small

        assert 20 < ratio < 20_000, (
            f"x10,000 in m cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )
        assert l_large / t_small > 20, f"locals alone still copies: {l_large:.2e}s"
        assert given < 10, f"with both given, x{given:.1f} ({b_small:.2e}s to {b_large:.2e}s)"

    def test_the_expression_length_term_is_linear(self) -> None:
        """One subscript with 10 or 1,000 items, x91 in the source text."""
        short = "tuple[" + ", ".join(["int"] * 10) + "]"
        long = "tuple[" + ", ".join(["int"] * 1_000) + "]"
        fn_short, fn_long = function_with(short), function_with(long)
        get_annotations(fn_short)
        get_annotations(fn_long)
        unresolved_short = function_with(short.replace("int", "Undefined"))
        unresolved_long = function_with(long.replace("int", "Undefined"))

        string = measure(lambda: get_annotations(fn_long, format=Format.STRING)) / measure(
            lambda: get_annotations(fn_short, format=Format.STRING)
        )
        forwardref = measure(
            lambda: get_annotations(unresolved_long, format=Format.FORWARDREF)
        ) / measure(lambda: get_annotations(unresolved_short, format=Format.FORWARDREF))
        compiled = measure(lambda: ForwardRef(long).evaluate()) / measure(
            lambda: ForwardRef(short).evaluate()
        )

        assert 5 < string < 2_000, f"STRING x{string:.1f} for x91 in e"
        assert 5 < forwardref < 2_000, f"unresolved FORWARDREF x{forwardref:.1f} for x91 in e"
        assert 5 < compiled < 2_000, f"evaluate() with a compile x{compiled:.1f} for x91 in e"

    def test_cached_code_and_eval_str_are_linear_in_the_expression_length(self) -> None:
        """Sizes large enough that the fixed cost of a call is noise: one
        subscript of 1,000 against 10,000 items for evaluate() on cached
        code, and 100 against 10,000 for eval_str, which compiles each time."""
        long = "tuple[" + ", ".join(["int"] * 1_000) + "]"
        longer = "tuple[" + ", ".join(["int"] * 10_000) + "]"
        short = "tuple[" + ", ".join(["int"] * 100) + "]"
        ref_long, ref_longer = ForwardRef(long), ForwardRef(longer)
        ref_long.evaluate()
        ref_longer.evaluate()
        fn_short, fn_longer = function_with(repr(short)), function_with(repr(longer))

        cached = measure(lambda: ref_longer.evaluate()) / measure(lambda: ref_long.evaluate())
        eval_str = measure(lambda: get_annotations(fn_longer, eval_str=True)) / measure(
            lambda: get_annotations(fn_short, eval_str=True)
        )

        assert 3 < cached < 40, f"evaluate() on cached code x{cached:.1f} for x10 in e"
        assert 20 < eval_str < 2_000, f"eval_str x{eval_str:.1f} for x100 in e"

    def test_type_repr_grows_with_the_result(self) -> None:
        small = tuple(range(10))
        large = tuple(range(100_000))

        t_small = measure(lambda: annotationlib.type_repr(small))
        t_large = measure(lambda: annotationlib.type_repr(large))
        ratio = t_large / t_small

        assert 100 < ratio < 20_000, (
            f"x10,000 in r cost x{ratio:.1f} ({t_small:.2e}s to {t_large:.2e}s)"
        )


class TestPublicNamesAreDocumented:
    """The Complexity Reference against the module's `__all__` and dir(ForwardRef)."""

    @staticmethod
    def documented_names() -> set[str]:
        text = PAGE.read_text(encoding="utf-8")
        start = text.index("## Complexity Reference")
        end = text.index("## Evaluation Is Deferred, Then Cached")
        names: set[str] = set()
        for line in text[start:end].splitlines():
            if not line.startswith("| `"):
                continue
            names.update(re.findall(r"`(?:Format\.|ForwardRef\.)?(\w+)", line.split("|")[1]))
        return names

    @staticmethod
    def public_names() -> set[str]:
        public = set(annotationlib.__all__)
        public |= {name for name in dir(ForwardRef) if not name.startswith("_")}
        public |= {member.name for member in Format}
        return public

    def test_the_extractor_sees_the_table(self) -> None:
        assert {"get_annotations", "evaluate", "STRING", "type_repr"} <= self.documented_names()

    def test_every_public_name_has_a_row(self) -> None:
        """The internal format has no row of its own; the Format row's note
        names it as internal, and that mention is checked here."""
        assert "`Format.VALUE_WITH_FAKE_GLOBALS` is internal" in PAGE.read_text(encoding="utf-8")

        missing = self.public_names() - self.documented_names() - {"VALUE_WITH_FAKE_GLOBALS"}

        assert not missing, f"public names without a row: {sorted(missing)}"

    def test_every_row_names_something_that_exists(self) -> None:
        invented = self.documented_names() - self.public_names() - {"format"}

        assert not invented, f"rows naming nothing that exists: {sorted(invented)}"


EXPECTED_BLOCKS = 4


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests, and its asserts hold."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_every_block_asserts_something(self) -> None:
        """The blocks carry their expected values as asserts, so running them
        checks the values and not only that nothing raised."""
        for line, source in _blocks():
            assert "assert " in source, f"{PAGE.name}:{line} asserts nothing"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        first = _blocks()[0][1]
        broken = first.replace("assert evaluations == 1\n", "assert evaluations == 2\n", 1)
        assert broken != first, "the mutation did not change the assert"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
