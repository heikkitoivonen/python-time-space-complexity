"""Tests for docs/stdlib/symtable.md.

The page prices `symtable()` by the source it analyses, and every method after
it by the one table it is called on: `s` names and `t` direct child tables.
The child scans behind `lookup()` and `get_symbols()` are settled by
observation, by swapping a table's raw C object for a proxy that counts how
often its child list is walked and how many children each walk visits; the
caches are settled by identity. Only `symtable()` itself needs a stopwatch.

Measurement scope:

* `symtable()` over module-level statements, an assignment and a lambda per
  pair, at 200, 2,000 and 20,000 pairs: each 10x step is asserted under 30x in
  time, where linear predicts 10x and quadratic 100x. The same statements at
  3,000 pairs inside one function are asserted more than 5x dearer than at
  module level; that is the b·f term, measured at 32x to 36x on 3.10 and 3.14. The traced peak
  grows between 5x and 30x from 2,000 to 20,000 pairs (9.8x on 3.14), where
  linear predicts 10x and quadratic 100x.
* `symtable()` is observed to raise `SyntaxError` for a fault on the last of
  1,000 lines, and to register one wrapper for its filename in the factory's
  memo, rising to 1 + t only once `get_children()` is called and held.
* A module of 300 functions has t = 300 child tables, or 600 from 3.14,
  where each `def` adds an `__annotate__` table. `lookup()` walks the child
  list once, visiting all t children, on the first request for a name and
  not at all on the second, which returns the same `Symbol`. `get_symbols()`
  over its s = 301 names walks the list s times and visits s·t children on
  its first call, none on its second, whose symbols are the cached objects in
  a new list. The five
  `Function` getters walk it zero times and return the same tuple twice.
* `get_identifiers()` is a `dict_keys` view whose traced peak stays under
  1 KB over 10,000 names. `get_children()` returns a new list of the same
  wrappers while one is held; once every reference is gone, the next call
  builds a fresh wrapper with an empty lookup cache.
* `Class.get_methods()` returns the same tuple twice, and warns on each call
  from 3.14 only. The `Symbol` predicates are asserted on a module that
  exercises each of them, `get_namespaces()` is the same list on every call,
  and `get_namespace()` raises `ValueError` for none and for two tables.
* Version boundaries are asserted on either side: a list comprehension has a
  child table before 3.12 and none from 3.12; PEP 695 tables are named
  `'type parameter'` and `'TypeVar bound'` on 3.12 and `'type parameters'`
  and `'type variable'` from 3.13; `get_type()` is a `str` before 3.13 and a
  `SymbolTableType` from 3.13; a `def` and a variable annotation add an
  `__annotate__` table from 3.14 and nothing before, a function-local
  annotation included; the four 3.14 `Symbol`
  predicates exist from 3.14 only; `python -m symtable` prints tables from 3.13.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The Σ s·t term of `python -m symtable` is read from `main()` in
  Lib/symtable.py, which calls `lookup()` on every identifier of every table.
  The test asserts only that the command prints the tables.
* The b·f term is read from `analyze_child_block()` in Python/symtable.c,
  which copies the enclosing `bound`, `free` and `global` sets for every child
  block. The test varies shape at one total, not b and f separately, and does
  not nest functions more than one level deep. That `compile()` pays the same
  term follows from Python/compile.c building the same symbol table before
  code generation; it is not timed, because the rest of `compile()` is not
  linear in the module-level shape on 3.10.
* `symtable()` space is measured as a traced peak only; what the returned
  tables retain after the AST is freed is not measured.
* Treating name hashing and comparison as O(1) is a cost-model assumption.
* A name bound by many repeated definitions gives its `Symbol` one namespace
  per table, so `lookup()` space can reach O(t). The rows price the usual
  one or two; repeated definitions are asserted only at two.

Intentionally undocumented: `SymbolTableFactory` and `main` are module-level
implementation details outside `__all__` and the official documentation.
"""

from __future__ import annotations

import gc
import pathlib
import re
import subprocess
import symtable
import sys
import textwrap
import time
import tracemalloc
import warnings
import weakref
from collections.abc import Callable, Iterator
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "symtable.md"
EXPECTED_BLOCKS = 6


def best_ns(func: Callable[[], Any], repeats: int = 3) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


def build(source: str, filename: str = "<test>") -> symtable.SymbolTable:
    return symtable.symtable(source, filename, "exec")


def pairs(count: int, indent: str = "") -> str:
    return "".join(f"{indent}x{i} = 1\n{indent}g{i} = lambda: 0\n" for i in range(count))


def at_module(count: int) -> str:
    return pairs(count)


def in_function(count: int) -> str:
    return "def outer():\n" + pairs(count, "    ")


class CountingRaw:
    """Stands in for a table's C object and counts walks of its child list."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw
        self.walks = 0
        self.visited = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    @property
    def children(self) -> Iterator[Any]:
        self.walks += 1
        for child in self._raw.children:
            self.visited += 1
            yield child


def counted(table: symtable.SymbolTable) -> CountingRaw:
    raw = CountingRaw(table._table)  # type: ignore[attr-defined]  # noqa: SLF001
    table._table = raw  # type: ignore[attr-defined]  # noqa: SLF001
    return raw


def memo_entries(filename: str) -> int:
    memo = symtable._newSymbolTable._SymbolTableFactory__memo  # type: ignore[attr-defined]  # noqa: SLF001
    return sum(1 for _, name in list(memo.keys()) if name == filename)


def functions(count: int) -> str:
    return "".join(f"def f{i}(): pass\n" for i in range(count)) + "total = 0\n"


class TestBuildingAnalysesTheWholeSource:
    """`symtable()` | O(n + b·f) | O(n); only the top table is wrapped."""

    def test_a_fault_on_the_last_line_raises_at_the_call(self) -> None:
        source = at_module(500) + "def (:\n"

        with pytest.raises(SyntaxError):
            build(source)

    def test_only_the_top_table_is_wrapped(self) -> None:
        name = "<only-the-top>"
        table = build(functions(50), name)

        assert memo_entries(name) == 1
        children = table.get_children()
        assert len(children) >= 50
        assert memo_entries(name) == 1 + len(children)

    def test_the_peak_follows_the_source(self) -> None:
        small, large = at_module(2_000), at_module(20_000)

        peaks = [peak_bytes(lambda: build(small)), peak_bytes(lambda: build(large))]

        assert peaks[0] * 5 < peaks[1] < peaks[0] * 30, f"10x the source peaked at {peaks}"

    @pytest.mark.timing
    def test_module_level_code_is_linear(self) -> None:
        sources = [at_module(count) for count in (200, 2_000, 20_000)]
        for source in sources:
            build(source)

        durations = [best_ns(lambda s=source: build(s)) for source in sources]
        ratios = [later / earlier for earlier, later in pairwise(durations)]

        assert all(ratio < 30 for ratio in ratios), (
            f"10x steps cost {[f'x{r:.1f}' for r in ratios]} ({durations} ns); "
            "linear predicts x10, quadratic x100"
        )

    @pytest.mark.timing
    def test_the_same_statements_in_a_function_cost_their_product(self) -> None:
        flat, nested = at_module(3_000), in_function(3_000)
        build(flat)
        build(nested)

        ratio = best_ns(lambda: build(nested)) / best_ns(lambda: build(flat))

        assert ratio > 5, (
            f"3,000 locals and lambdas in one function cost x{ratio:.1f} the same "
            "statements at module level; O(n) alone predicts about x1"
        )


class TestLookupScansTheChildren:
    """`lookup()` | O(t) first time, O(1) after; `get_symbols()` | O(s·t) first
    time, O(s) after; the `Function` getters scan no children."""

    SOURCE = functions(300)

    def test_the_first_lookup_walks_every_child_once(self) -> None:
        table = build(self.SOURCE)
        children = len(table.get_children())
        raw = counted(table)

        first = table.lookup("total")

        assert children == (600 if sys.version_info >= (3, 14) else 300)
        assert (raw.walks, raw.visited) == (1, children)
        assert table.lookup("total") is first
        assert (raw.walks, raw.visited) == (1, children)

    def test_a_name_the_table_lacks_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            build(self.SOURCE).lookup("missing")

    def test_get_symbols_is_one_lookup_per_name(self) -> None:
        table = build(self.SOURCE)
        names = len(list(table.get_identifiers()))
        children = len(table.get_children())
        raw = counted(table)

        first = table.get_symbols()

        assert names == 301
        assert (raw.walks, raw.visited) == (names, names * children)
        second = table.get_symbols()
        assert (raw.walks, raw.visited) == (names, names * children)
        assert second is not first
        assert all(a is b for a, b in zip(first, second, strict=True))

    def test_function_getters_scan_nothing_and_cache_their_tuple(self) -> None:
        source = "def f(a, b):\n    global g\n    c = a\n    def h():\n        return b\n"
        table = build(source)
        function = table.lookup("f").get_namespace()
        assert isinstance(function, symtable.Function)
        raw = counted(function)
        getters = [
            function.get_parameters,
            function.get_locals,
            function.get_globals,
            function.get_nonlocals,
            function.get_frees,
        ]

        for getter in getters:
            assert getter() is getter()

        assert raw.walks == 0
        assert function.get_parameters() == ("a", "b")
        assert function.get_globals() == ("g",)

    def test_get_identifiers_is_a_view_not_a_copy(self) -> None:
        table = build("".join(f"x{i} = 1\n" for i in range(10_000)))
        table.get_identifiers()

        peak = peak_bytes(table.get_identifiers)

        assert type(table.get_identifiers()).__name__ == "dict_keys"
        assert len(table.get_identifiers()) == 10_000
        assert peak < 1_000, f"get_identifiers() allocated {peak} bytes over 10,000 names"


class TestChildTablesKeepTheirCachesWhileHeld:
    """`get_children()` | O(t) | O(t): a new list each time, the same wrapper
    only while something holds it."""

    SOURCE = "def f():\n    x = 1\n"

    @staticmethod
    def child(table: symtable.SymbolTable) -> symtable.SymbolTable:
        return next(c for c in table.get_children() if c.get_name() == "f")

    def test_a_new_list_of_the_same_wrappers(self) -> None:
        table = build(self.SOURCE)

        first, second = table.get_children(), table.get_children()

        assert first is not second
        assert all(a is b for a, b in zip(first, second, strict=True))

    def test_a_dropped_child_comes_back_without_its_cache(self) -> None:
        table = build(self.SOURCE)
        f = self.child(table)
        f.lookup("x")
        assert f._symbols  # type: ignore[attr-defined]  # noqa: SLF001
        alive = weakref.ref(f)

        del f
        gc.collect()

        assert alive() is None
        assert not self.child(table)._symbols  # type: ignore[attr-defined]  # noqa: SLF001


class TestClassAndSymbol:
    """`Class.get_methods()` caches and, from 3.14, warns; the `Symbol` rows
    are flag tests on one integer."""

    SOURCE = textwrap.dedent(
        """
        import os
        from sys import argv
        counter: int = 0
        def outer(step):
            total = 0
            def inner():
                nonlocal total
                global counter
                total += step
                counter += 1
            return inner
        class C:
            def m(self):
                pass
        def twice(): pass
        def twice(): pass
        """
    )

    def test_get_methods_caches_and_warns_from_314(self) -> None:
        cls = build(self.SOURCE).lookup("C").get_namespace()
        assert isinstance(cls, symtable.Class)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            first = cls.get_methods()
            second = cls.get_methods()

        assert first == ("m",)
        assert second is first
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecations) == (2 if sys.version_info >= (3, 14) else 0)

    def test_the_predicates(self) -> None:
        table = build(self.SOURCE)
        outer = table.lookup("outer").get_namespace()
        inner = outer.lookup("inner").get_namespace()

        assert table.lookup("os").is_imported() and table.lookup("argv").is_imported()
        assert table.lookup("counter").is_annotated()
        assert table.lookup("counter").is_assigned() and table.lookup("counter").is_global()
        assert table.lookup("counter").is_local()
        assert outer.lookup("step").is_parameter() and inner.lookup("step").is_referenced()
        assert not outer.lookup("step").is_referenced()
        assert inner.lookup("counter").is_declared_global()
        assert inner.lookup("total").is_nonlocal() and inner.lookup("total").is_free()
        assert not outer.lookup("total").is_free()
        assert inner.is_nested() and not outer.is_nested()
        assert outer.is_optimized() and not table.is_optimized()
        assert table.get_name() == "top" and table.get_lineno() == 0
        assert isinstance(table.get_id(), int)

    def test_namespaces(self) -> None:
        table = build(self.SOURCE)
        outer = table.lookup("outer")

        assert outer.is_namespace()
        assert outer.get_namespaces() is outer.get_namespaces()
        assert outer.get_namespace().get_name() == "outer"
        with pytest.raises(ValueError):
            table.lookup("os").get_namespace()
        assert len(table.lookup("twice").get_namespaces()) == 2
        with pytest.raises(ValueError):
            table.lookup("twice").get_namespace()

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_the_predicates_added_in_314(self) -> None:
        generic = build("def f[T]():\n    return [x for x in T]\n")
        scope = next(t for t in generic.get_children() if t.get_name() == "f")
        function = next(t for t in scope.get_children() if t.get_type() == "function")
        closure = build(
            "def outer():\n    y = 1\n    class C:\n        y = 2\n"
            "        def m(self):\n            return y\n"
        )
        cls = closure.lookup("outer").get_namespace().lookup("C").get_namespace()

        assert scope.lookup("T").is_type_parameter()  # type: ignore[attr-defined]
        assert not function.lookup("T").is_type_parameter()  # type: ignore[attr-defined]
        assert function.lookup("x").is_comp_iter()  # type: ignore[attr-defined]
        assert not function.lookup("x").is_comp_cell()  # type: ignore[attr-defined]
        captured = build("def g():\n    return [lambda: y for y in range(3)]\n")
        g = captured.lookup("g").get_namespace()
        assert g.lookup("y").is_comp_cell()  # type: ignore[attr-defined]
        assert cls.lookup("y").is_free_class()  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="added in 3.14")
    def test_the_314_predicates_are_absent_before(self) -> None:
        for name in ("is_type_parameter", "is_free_class", "is_comp_iter", "is_comp_cell"):
            assert not hasattr(symtable.Symbol, name)


def walk(table: symtable.SymbolTable) -> list[tuple[str, str]]:
    found = [(table.get_name(), str(table.get_type()))]
    for child in table.get_children():
        found.extend(walk(child))
    return found


class TestVersionBoundaries:
    """The Version Notes, asserted on either side of each boundary."""

    def test_list_comprehensions_are_inlined_from_312(self) -> None:
        names = [name for name, _ in walk(build("def f(y):\n    return [x for x in y]\n"))]

        assert ("listcomp" in names) == (sys.version_info < (3, 12))

    def test_generator_expressions_keep_a_table(self) -> None:
        names = [name for name, _ in walk(build("g = (x for x in y)\n"))]

        assert "genexpr" in names

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 695 syntax is 3.12+")
    def test_pep_695_table_kinds(self) -> None:
        kinds = {kind for _, kind in walk(build("type A[U] = list[U]\ndef g[V: int](): pass\n"))}

        if sys.version_info >= (3, 13):
            assert {"type parameters", "type alias", "type variable"} <= kinds
        else:
            assert {"type parameter", "type alias", "TypeVar bound"} <= kinds

    def test_get_type_is_a_string_or_an_equal_enum_member(self) -> None:
        kind = build("x = 1\n").get_type()

        assert kind == "module"
        if sys.version_info >= (3, 13):
            assert kind is symtable.SymbolTableType.MODULE  # type: ignore[attr-defined]
            assert [m.value for m in symtable.SymbolTableType] == [  # type: ignore[attr-defined]
                "module",
                "function",
                "class",
                "annotation",
                "type alias",
                "type parameters",
                "type variable",
            ]
        else:
            assert type(kind) is str
            assert not hasattr(symtable, "SymbolTableType")

    def test_annotate_tables_from_314(self) -> None:
        with_def = walk(build("def f(): pass\n"))
        annotated_class = walk(build("class C:\n    x: int\n"))
        local_annotation = build("def f():\n    x: int = 1\n").lookup("f").get_namespace()
        plain = walk(build("x = 1\nclass D: pass\n"))

        expected = sys.version_info >= (3, 14)
        assert (("__annotate__", "annotation") in with_def) == expected
        assert (("__annotate__", "annotation") in annotated_class) == expected
        inside = [(c.get_name(), str(c.get_type())) for c in local_annotation.get_children()]
        assert inside == ([("__annotate__", "annotation")] if expected else [])
        assert all(name != "__annotate__" for name, _ in plain)

    def test_the_command_line(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "sample.py"
        script.write_text("def f(a):\n    return a\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "symtable", str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        if sys.version_info >= (3, 13):
            assert result.returncode == 0, result.stderr
            assert "symbol table for function 'f'" in result.stdout
            assert "local symbol 'a'" in result.stdout
        else:
            assert "symbol table for" not in result.stdout


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
        line, source = next((n, s) for n, s in _blocks() if "== ('step',)" in s)
        mutated = source.replace("== ('step',)", "== ('total',)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
