"""Tests for docs/stdlib/ast.md.

The page's size variables: n = source length, N = nodes, h = depth, w = widest
level, s = statements, b = block nesting depth, k = direct children, f = fields.
Most of them can be settled by observation:

* every node class is a container over a fixed field list: the arguments are
  stored as attributes, a list field is kept rather than copied, and `_fields`
  and `_attributes` are the class tuples themselves. From 3.13 an omitted
  optional field comes from a class default - a fresh list per instance for a
  list field, one shared `Load()` for `ctx` - and an omitted required one
  warns; on 3.10 to 3.12 the attribute is simply absent;
* the page's grouping of the node classes is checked against the runtime class
  hierarchy: every class a row lists is a subclass of the abstract group its
  Notes name;
* recursion versus a queue is settled by depth alone. A chain of 5,000 unary
  minuses is 5,000 levels deep, past the default recursion limit; `walk()`
  yields all 10,002 nodes (each `UnaryOp` carries an `op` node) while
  `NodeVisitor.visit()`, `dump()` and `unparse()` raise `RecursionError`, on
  every supported version;
* `walk()`'s O(w) space is read off the queue itself: the function imports
  `deque` from `collections` at call time, so a subclass installed there
  records its peak length - 4,000 for 1,000 statements and 16,000 for 4,000,
  and 2 for the deep chain however long it is. In `x0 = 0 + 1` the levels run
  1, 1,000 assignments, 2,000 targets and values, then 4,000: each target's
  `Store` with each `BinOp`'s two constants and its `Add`. The queue holds
  what is left of one level plus what has been found of the next, so the peak
  lies between w and 2w, and here it lands on w;
* `unparse()`'s q term is interpolation nesting: a `FormattedValue` renders
  its expression with a fresh unparser and copies the result into the
  enclosing string. 500 then 4,000 nested `JoinedStr` levels emit x8.0 the
  characters in x27 the time, which rejects linear scaling (x8) without
  pinning an upper bound. The q copies are made one after another, so the
  space stays the output size; no test measures a peak here. On 3.10 and 3.11
  `unparse()` runs out of quote characters: four levels round-trip, the fifth
  emits text the parser rejects and the sixth raises `ValueError`. The
  measurement therefore runs from 3.12, and that boundary is pinned on every
  version;
* `unparse()`'s `s * b` term is statements, not nodes: at one block depth,
  2,000 statements of one node each and 20 statements holding 2,000 expression
  nodes between them have the same N and differ 16x in output characters.
  `unparse()` of 250 then 1,000 nested `while` blocks emits x15.7 the
  characters, s and b growing together. With the two held apart the output is
  linear in each: 1,000 then 4,000 statements 200 blocks deep emit x4.0 the
  characters, and 1,000 statements 100 then 400 blocks deep x3.9; the test
  asserts the character count, which is exact, and the growth in nodes
  separately;
* `literal_eval()` of parsed set trees with 500 then 8,000 integer keys:
  colliding keys (multiples of `sys.hash_info.modulus`) cost more than x64,
  while distinct hashes cost less than x64. Linear growth predicts x16
  and quadratic growth x256. Parsing and warm-up happen outside timing;
  the integer widths remain bounded to the same few machine words. That a
  string is parsed and a tree is not is settled by counting `parse()` calls;
* `compare()` stops at the first difference: a value in a later statement
  whose `__eq__` counts its calls is never consulted when the first
  statement already differs. `compare_attributes=True` is separated from the
  default by two structurally equal trees whose positions differ;
* `NodeVisitor` dispatches by class name, a `visit_<Class>` that does not call
  `generic_visit()` stops the descent there, and `NodeTransformer` rebuilds a
  list field in place, keeping the list object;
* the breadth-first order is asserted on the page's own example, where the
  three assignment targets come out before the names nested inside the
  expressions.

The growth tests time an operation at two sizes and assert on the ratio. The
step is 4x, so linear predicts 4x. Measured on one aarch64 machine under
CPython 3.14.7 with 1,000 then 4,000 assignment statements unless stated:

* `parse`: x4.8; a 1,000-then-4,000-term `a + a + ...` chain: x4.2; a chain
  of unary minuses: x5.2;
* `walk`: x4.3; `NodeVisitor.visit`: x4.0; `NodeTransformer.visit`: x4.0;
  `fix_missing_locations`: x4.3; `increment_lineno`: x4.3; `compare`: x4.4
  on 3.14; `literal_eval` of a 1,000-then-4,000-item list: x5.4;
* `dump` of the wide tree: x4.3 (x4.2 with `indent=2`), but of a chain 1,000
  then 16,000 deep: x137-x151 (x133-x135 on 3.10.21), the N * h shape;
  a 4,000-deep chain against a
  wide tree of the same node count costs x6.4 more; with `indent=2` the deep
  chain's output grows x16 in characters (2.0 MB to 32 MB) and the time x101,
  the N * h² shape, and x550 for 250 then 2,000 deep, which is what the test
  measures;
* `unparse`: x3.9 wide and x3.7 for the deep chain, so it is linear in both
  outside f-strings;
* `get_source_segment` of the last statement: x16-x17 on 3.11.14 and 3.14.7
  for 16x the source (1,000 then 16,000 fixed-width lines), after warm-up;
  of the first statement: x1.3 on 3.14 and x4.2 on 3.10.21, which has no
  `maxlines` cut in `_splitlines_no_ff` (added by gh-103285 in 3.12);
* `get_docstring` with 16x the statements after the docstring, `clean=False`:
  x1.0; with a 1,000-then-4,000-line docstring: x4.1 under `clean=True` and
  x1.0 under `clean=False`. Leading blank lines are checked by counting the
  entries shifted by each front pop in `cleandoc`, varying the blank-line
  count alone and then both blank and text line counts for the k * l term.

Sub-microsecond calls - `get_source_segment` of the first line, the
`get_docstring` constant-time cases - are run 200 times per sample. The deep
measurements run in a worker thread with a 256 MB stack and a raised
recursion limit, because the limit alone lets 3.10 and 3.11 overflow the C
stack on a 4,000-deep chain and take the interpreter down.

Not settled here:

* name coverage of the module's API. That is the page-scoped audit's job
  (`scripts/audit_documentation.py --page docs/stdlib/ast.md`), which reports
  no missing names. Three documented names it cannot resolve on this
  interpreter are `ast.AST._fields` and `ast.AST._field_types`, which live on
  the concrete node classes rather than the base, and
  `NodeVisitor.visit_Constant`, which 3.14 removed; the first two are asserted
  here on `ast.Name`, the third by version;
* `main()`, the command-line entry, is asserted to parse and dump a file
  through `python -m ast`; its bound is `parse` plus `dump` by construction.
  The parser is measured linear on three shapes - statement lists, binary
  chains, unary chains - which is evidence for those shapes, not a proof for
  every grammar path; the parenthesis nesting that could defeat memoization is
  capped at 200 levels by `SyntaxError`, pinned exactly below;
* the per-class position attributes the audit lists as unclassified
  (`ast.Add.lineno` and its like). They are the same four `_attributes` the
  `ast.AST` row prices, carried by the classes whose `_attributes` names them
  and by no others - `ast.Add._attributes` is empty, which is asserted - and
  no test enumerates them class by class.

Scope of the constructor bound: it covers the fields the grammar declares.
A node constructor also accepts arbitrary extra keyword attributes and sets
each one, which costs what the caller passes; that path warns from 3.13 and is
not priced here.

Not varied: node kinds, and the length of string fields. The wide trees are
assignment statements and the deep trees unary operators; the bounds do not
depend on the kind, but no test covers a tree mixing many kinds at scale, and
every `Constant` here holds a small int and every identifier is short, so the
length a long string or identifier adds to `parse`, `dump`, `unparse` and
`compare` is stated from the page's definition rather than measured.
"""

import ast
import builtins
import collections
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import timeit
import warnings
from collections.abc import Callable
from typing import Any, SupportsIndex, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ast.md"


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def ratio(small: Callable[[], Any], large: Callable[[], Any], repeats: int = 5) -> float:
    return best_time(large, repeats) / best_time(small, repeats)


def batched(func: Callable[[], Any], loops: int = 200) -> Callable[[], None]:
    def run() -> None:
        for _ in range(loops):
            func()

    return run


def statements(count: int) -> str:
    return "\n".join(f"x{i} = {i} + 1" for i in range(count))


def wide_tree(count: int) -> ast.Module:
    return ast.parse(statements(count))


POSITION: dict[str, Any] = {"lineno": 1, "col_offset": 0, "end_lineno": 1, "end_col_offset": 1}


def deep_chain(depth: int) -> ast.Expression:
    """A chain of unary minuses, built without the parser so depth is free:
    2 * depth + 2 nodes, since every UnaryOp carries an op node too. Positions
    are set here because fix_missing_locations() recurses and could not."""
    node: ast.expr = ast.Constant(value=1, **POSITION)
    for _ in range(depth):
        node = ast.UnaryOp(op=ast.USub(), operand=node, **POSITION)
    return ast.Expression(body=node)


def wrap_in_blocks(body: list[ast.stmt], depth: int) -> ast.Module:
    """Wrap statements in `while True:` blocks nested `depth` deep."""
    for _ in range(depth):
        test = ast.Constant(value=True, **POSITION)
        body = [ast.While(test=test, body=body, orelse=[], **POSITION)]
    return ast.Module(body=body, type_ignores=[])


def nested_blocks(depth: int, statements: int = 1) -> ast.Module:
    """`while True:` blocks nested `depth` deep around `statements` passes."""
    return wrap_in_blocks([ast.Pass(**POSITION) for _ in range(statements)], depth)


def flat_tree(count: int) -> ast.Module:
    """One statement per constant: 2 * count + 1 nodes, three levels deep."""
    body: list[ast.stmt] = [ast.Expr(value=ast.Constant(value=i)) for i in range(count)]
    return ast.Module(body=body, type_ignores=[])


def in_deep_stack(func: Callable[[], Any]) -> Any:
    """Run func in a thread whose stack fits a 16,000-deep recursion."""
    result: list[Any] = []
    error: list[BaseException] = []

    def run() -> None:
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(100_000)
        try:
            result.append(func())
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            error.append(exc)
        finally:
            sys.setrecursionlimit(limit)

    previous = threading.stack_size(256 * 1024 * 1024)
    try:
        worker = threading.Thread(target=run)
        worker.start()
        worker.join()
    finally:
        threading.stack_size(previous)
    if error:
        raise error[0]
    return result[0]


class TestParse:
    @pytest.mark.timing
    def test_linear_in_the_statements(self) -> None:
        """Fixed-width statements vary source length and node count by 16x.

        timeit excludes cyclic GC and restores its enabled state afterwards.
        The bounds separate linear growth (16x) from quadratic growth (256x);
        identifier length, expression shape and nesting depth stay fixed.
        """
        small, large = "x = 1 + 1\n" * 1_000, "x = 1 + 1\n" * 16_000
        ast.parse(small)
        ast.parse(large)
        small_time = min(timeit.repeat(lambda: ast.parse(small), number=1, repeat=5))
        large_time = min(timeit.repeat(lambda: ast.parse(large), number=1, repeat=5))
        growth = large_time / small_time

        assert 6 < growth < 64, f"x{growth:.1f} for 16x the source"

    @pytest.mark.timing
    def test_linear_in_a_binary_chain(self) -> None:
        small, large = " + ".join(["a"] * 1_000), " + ".join(["a"] * 4_000)

        growth = in_deep_stack(lambda: ratio(lambda: ast.parse(small), lambda: ast.parse(large)))

        assert 2.5 < growth < 8, f"x{growth:.1f} for 4x the terms"

    def test_parenthesis_nesting_is_capped_at_200(self) -> None:
        assert isinstance(ast.parse("(" * 200 + "1" + ")" * 200), ast.Module)
        with pytest.raises(SyntaxError, match="too many nested parentheses"):
            ast.parse("(" * 201 + "1" + ")" * 201)

    def test_indentation_is_capped_at_99_levels(self) -> None:
        """The page's b is at most 99 in a parsed tree because of this."""

        def nested(levels: int) -> str:
            return "".join("    " * i + "if x:\n" for i in range(levels)) + "    " * levels + "pass"

        assert isinstance(ast.parse(nested(99)), ast.Module)
        with pytest.raises(IndentationError, match="too many levels of indentation"):
            ast.parse(nested(100))

    def test_neither_cap_applies_to_a_unary_chain(self) -> None:
        """A chain that needs no parentheses and no indent clears both limits
        by an order of magnitude, and the parser's own stack stops it
        thousands of levels further out.

        Where it stops, and with which exception, moves across the supported
        range: 3.11 raises RecursionError before 5,000 levels, while 3.10 and
        3.12 to 3.14 reach 5,000 and raise MemoryError by 20,000. The test
        pins the two ends that hold on all of them.
        """
        node = ast.parse("-" * 1_000 + "1").body[0].value  # type: ignore[attr-defined]

        depth = 0
        while isinstance(node, ast.UnaryOp):
            node, depth = node.operand, depth + 1

        assert depth == 1_000
        with pytest.raises((RecursionError, MemoryError)):
            ast.parse("-" * 50_000 + "1")


class TestWalk:
    def test_is_breadth_first(self) -> None:
        tree = ast.parse("x = 1\ny = x + 2\nz = y * 3")

        names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]

        assert names == ["x", "y", "z", "x", "y"]

    def test_yields_every_node(self) -> None:
        assert sum(1 for _ in ast.walk(deep_chain(5_000))) == 10_002
        assert sum(1 for _ in ast.walk(flat_tree(1_000))) == 2_001

    @staticmethod
    def queue_peak(tree: ast.AST, monkeypatch: pytest.MonkeyPatch) -> int:
        peak = 0

        class Recording(collections.deque[Any]):
            def extend(self, items: Any) -> None:
                nonlocal peak
                super().extend(items)
                peak = max(peak, len(self))

        monkeypatch.setattr(collections, "deque", Recording)
        for _ in ast.walk(tree):
            pass
        return peak

    def test_the_queue_peaks_at_the_widest_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The widest level of `x0 = 0 + 1` statements is not the targets and
        values but the level below: 1,000 `Store` markers with 1,000 `Add`
        nodes and 2,000 constants. The queue holds the rest of one level plus
        what it has found of the next, so the peak is between w and 2w; here
        the level above is half as wide, so it lands on w, and four times the
        statements gives four times the peak."""
        small = self.queue_peak(wide_tree(1_000), monkeypatch)
        large = self.queue_peak(wide_tree(4_000), monkeypatch)

        assert 2_000 <= small <= 4_000
        assert large == 4 * small

    def test_a_chain_needs_a_queue_of_two(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.queue_peak(deep_chain(5_000), monkeypatch) == 2

    def test_the_recording_queue_is_the_one_walk_uses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A patch that walk() ignored would report a peak of zero."""
        assert self.queue_peak(ast.parse("x = 1"), monkeypatch) > 0

    @pytest.mark.timing
    def test_linear_in_the_nodes(self) -> None:
        small, large = wide_tree(1_000), wide_tree(4_000)

        growth = ratio(lambda: list(ast.walk(small)), lambda: list(ast.walk(large)))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the nodes"


class TestRecursiveHelpers:
    """O(h) stack: a chain past the recursion limit breaks every one of them,
    and walk() survives it."""

    DEPTH = 5_000

    @pytest.mark.parametrize(
        "helper",
        [
            pytest.param(lambda tree: ast.NodeVisitor().visit(tree), id="visit"),
            pytest.param(lambda tree: ast.NodeTransformer().visit(tree), id="transform"),
            pytest.param(ast.dump, id="dump"),
            pytest.param(ast.unparse, id="unparse"),
            pytest.param(ast.fix_missing_locations, id="fix_missing_locations"),
        ],
    )
    def test_recursion_is_the_limit(self, helper: Callable[[ast.AST], Any]) -> None:
        tree = deep_chain(self.DEPTH)

        with pytest.raises(RecursionError):
            helper(tree)
        assert sum(1 for _ in ast.walk(tree)) == 2 * self.DEPTH + 2

    def test_visitor_dispatches_by_class_name(self) -> None:
        seen: list[str] = []

        class Recorder(ast.NodeVisitor):
            def visit_Name(self, node: ast.Name) -> None:
                seen.append(f"Name:{node.id}")

            def generic_visit(self, node: ast.AST) -> None:
                seen.append(type(node).__name__)
                super().generic_visit(node)

        Recorder().visit(ast.parse("x = y"))

        assert seen == ["Module", "Assign", "Name:x", "Name:y"]

    def test_a_visit_method_that_skips_generic_visit_stops_the_descent(self) -> None:
        """The O(N) bound is the default traversal, not a floor."""
        seen: list[str] = []

        class SkipCalls(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:
                seen.append("Call")

            def visit_Name(self, node: ast.Name) -> None:
                seen.append(f"Name:{node.id}")

        SkipCalls().visit(ast.parse("f(g(x))"))

        assert seen == ["Call"]

    def test_fix_missing_locations_inherits_the_parent_position(self) -> None:
        inner = ast.Name(id="x", ctx=ast.Load())
        outer = ast.Expr(value=inner, lineno=7, col_offset=4, end_lineno=7, end_col_offset=5)
        tree = ast.Module(body=[outer], type_ignores=[])

        ast.fix_missing_locations(tree)

        assert (inner.lineno, inner.col_offset) == (7, 4)

    def test_transformer_rebuilds_a_list_field_in_place(self) -> None:
        class DropPasses(ast.NodeTransformer):
            def visit_Pass(self, node: ast.Pass) -> None:
                return None

        tree = ast.parse("pass\nx = 1\npass")
        body = tree.body

        DropPasses().visit(tree)

        assert tree.body is body
        assert [type(node).__name__ for node in body] == ["Assign"]

    def test_increment_lineno_walks_instead(self) -> None:
        tree = deep_chain(self.DEPTH)

        ast.increment_lineno(tree, 3)

        assert tree.body.lineno == 4

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "helper",
        [
            pytest.param(lambda tree: ast.NodeVisitor().visit(tree), id="visit"),
            pytest.param(lambda tree: ast.NodeTransformer().visit(tree), id="transform"),
            pytest.param(ast.fix_missing_locations, id="fix_missing_locations"),
            pytest.param(ast.increment_lineno, id="increment_lineno"),
            pytest.param(ast.unparse, id="unparse"),
        ],
    )
    def test_linear_in_the_nodes(self, helper: Callable[[ast.AST], Any]) -> None:
        small, large = wide_tree(1_000), wide_tree(4_000)

        growth = ratio(lambda: helper(small), lambda: helper(large))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the nodes"


class TestDump:
    @pytest.mark.timing
    def test_linear_in_a_wide_tree(self) -> None:
        small, large = wide_tree(1_000), wide_tree(4_000)

        growth = ratio(lambda: ast.dump(small), lambda: ast.dump(large))
        indented = ratio(lambda: ast.dump(small, indent=2), lambda: ast.dump(large, indent=2))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the nodes"
        assert 2.5 < indented < 7, f"x{indented:.1f} for 4x the nodes with indent"

    @pytest.mark.timing
    def test_superlinear_in_a_deep_chain(self) -> None:
        """Depth grows 16x with fixed node kinds and short fields.

        Linear work predicts 16x, N * h predicts 256x. After warm-up,
        1,000 then 16,000 levels measure 133-135x on CPython 3.10.21 and
        137-151x on 3.14.7. The output itself grows only about 16x; this
        distinguishes repeated copying from output size alone. Field
        lengths, branching, and indentation are not varied.
        """
        small, large = deep_chain(1_000), deep_chain(16_000)

        def measure() -> float:
            small_text, large_text = ast.dump(small), ast.dump(large)
            assert small_text.count("UnaryOp(") == 1_000
            assert large_text.count("UnaryOp(") == 16_000
            assert 15 < len(large_text) / len(small_text) < 17
            return ratio(lambda: ast.dump(small), lambda: ast.dump(large), repeats=5)

        growth = in_deep_stack(measure)

        assert growth > 48, f"x{growth:.1f} for 16x the depth; linear would be 16, N * h 256"

    @pytest.mark.timing
    def test_indent_makes_a_deep_chain_cubic(self) -> None:
        """At 8x depth, quadratic output predicts 64x and cubic work 512x.

        Warm both inputs before timing. CPython 3.14.7 measures about 550x
        from 250 to 2,000 levels after the unindented deep-chain test.
        Node kinds, field lengths, and indentation width remain fixed.
        """
        small, large = deep_chain(250), deep_chain(2_000)

        def measure() -> float:
            small_text, large_text = ast.dump(small, indent=2), ast.dump(large, indent=2)
            characters = len(large_text) / len(small_text)
            assert 48 < characters < 80, f"x{characters:.1f} characters for 8x the depth"
            return ratio(
                lambda: ast.dump(small, indent=2),
                lambda: ast.dump(large, indent=2),
                repeats=3,
            )

        growth = in_deep_stack(measure)

        assert growth > 128, f"x{growth:.1f} for 8x the depth; N * h would be 64, N * h² 512"

    def test_documented_output(self) -> None:
        text = ast.dump(ast.parse("x = 1 + 2"))

        assert text.startswith(
            "Module(body=[Assign(targets=[Name(id='x', ctx=Store())], value=BinOp("
        )


class TestUnparse:
    @pytest.mark.timing
    def test_linear_in_a_deep_chain(self) -> None:
        small, large = deep_chain(1_000), deep_chain(4_000)

        growth = in_deep_stack(
            lambda: ratio(lambda: ast.unparse(small), lambda: ast.unparse(large), repeats=3)
        )

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the depth"

    def test_nested_blocks_emit_quadratic_indentation(self) -> None:
        small, large = nested_blocks(250), nested_blocks(1_000)

        characters = in_deep_stack(lambda: len(ast.unparse(large)) / len(ast.unparse(small)))

        assert characters > 12, f"x{characters:.1f} characters for 4x the depth; linear would be 4"

    def test_output_is_linear_in_statements_and_in_depth_separately(self) -> None:
        """The N * b term: 4x the statements at one depth, then 4x the depth
        for one statement count, each grows the output about 4x."""

        def characters(depth: int, statements: int) -> int:
            return in_deep_stack(lambda: len(ast.unparse(nested_blocks(depth, statements))))

        by_statements = characters(200, 4_000) / characters(200, 1_000)
        by_depth = characters(400, 1_000) / characters(100, 1_000)

        assert 3 < by_statements < 5, f"x{by_statements:.1f} for 4x the statements"
        assert 3 < by_depth < 5, f"x{by_depth:.1f} for 4x the depth"

    def test_only_statements_pay_the_block_indent(self) -> None:
        """Equal node counts at one block depth, split differently between
        statement and expression nodes.

        2,000 `pass` statements against 20 tuple expressions of 100 elements.
        N * b is an upper bound that cannot tell the two apart; N + s * b
        predicts 2,000 indents against 20, and the output bears that out.
        Block depth and indent width are fixed. Node kinds are not: that is
        what moves the nodes from statements into expressions.
        """
        depth, width = 200, 99

        def tuple_statement() -> ast.stmt:
            elements: list[ast.expr] = [ast.Constant(value=1, **POSITION) for _ in range(width)]
            return ast.Expr(value=ast.Tuple(elts=elements, ctx=ast.Load(), **POSITION), **POSITION)

        many = nested_blocks(depth, 2_000)
        few = wrap_in_blocks([tuple_statement() for _ in range(20)], depth)

        nodes_many = sum(1 for _ in ast.walk(many))
        nodes_few = sum(1 for _ in ast.walk(few))
        characters = in_deep_stack(lambda: len(ast.unparse(many)) / len(ast.unparse(few)))

        assert 0.8 < nodes_many / nodes_few < 1.2, f"{nodes_many} against {nodes_few} nodes"
        assert characters > 8, f"x{characters:.1f} characters at equal N; N * b would be x1"

    @staticmethod
    def nested_f_string(depth: int) -> ast.Expression:
        node: ast.expr = ast.Name(id="x", ctx=ast.Load(), **POSITION)
        for _ in range(depth):
            inner = ast.FormattedValue(value=node, conversion=-1, format_spec=None, **POSITION)
            node = ast.JoinedStr(values=[inner], **POSITION)
        return ast.Expression(body=node)

    def test_nesting_f_strings_past_four_levels_needs_312(self) -> None:
        """Before 3.12 the unparser runs out of quote characters to alternate
        between: the fifth level produces text the parser will not read back,
        and the sixth raises. From 3.12 the nesting is unbounded, which is
        what lets the q measurement below run at all. The round trip is
        compared as text; the reparsed tree's structure is not."""
        four = ast.unparse(self.nested_f_string(4))

        assert ast.unparse(ast.parse(four, mode="eval")) == four
        if sys.version_info >= (3, 12):
            six = ast.unparse(self.nested_f_string(6))
            assert ast.unparse(ast.parse(six, mode="eval")) == six
        else:
            with pytest.raises(SyntaxError, match="backslash"):
                ast.parse(ast.unparse(self.nested_f_string(5)), mode="eval")
            with pytest.raises(ValueError, match="Unable to avoid backslash"):
                ast.unparse(self.nested_f_string(6))

    @pytest.mark.timing
    @pytest.mark.skipif(
        sys.version_info < (3, 12), reason="unparse cannot nest f-strings past five levels"
    )
    def test_nested_f_strings_re_render_what_is_inside_them(self) -> None:
        """8x the f-string nesting with the output growing 8x as well.

        A `FormattedValue` renders its expression with a fresh unparser and
        copies the result in, so text under q of them is copied q times. The
        assertion rejects linear scaling for this input family: linear work
        predicts x8, and CPython 3.14.7 measures x27 from 500 to 4,000 levels
        against x8 characters. It does not pin an upper bound. Only
        `JoinedStr` nesting is varied - one `Name` at the centre, no format
        specs, no conversions, no statements and no block depth. The q term
        goes unmeasured on 3.10 and 3.11, where `unparse()` cannot nest
        f-strings past four levels usefully at all.
        """

        small, large = self.nested_f_string(500), self.nested_f_string(4_000)

        def measure() -> tuple[float, float]:
            characters = len(ast.unparse(large)) / len(ast.unparse(small))
            return characters, ratio(lambda: ast.unparse(small), lambda: ast.unparse(large), 3)

        characters, growth = in_deep_stack(measure)

        assert 7 < characters < 9, f"x{characters:.1f} characters for 8x the nesting"
        assert growth > 14, f"x{growth:.1f} for 8x the nesting; linear would be 8, copying 64"

    def test_round_trips(self) -> None:
        source = "x = 1 + 2\nprint(x)"

        assert ast.unparse(ast.parse(source)) == source


class TestCompare:
    def test_arrived_in_314(self) -> None:
        assert hasattr(ast, "compare") == (sys.version_info >= (3, 14))

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="ast.compare arrived in 3.14")
    def test_equal_and_unequal(self) -> None:
        compare = getattr(ast, "compare")  # noqa: B009 - absent from typeshed before 3.14

        assert compare(ast.parse("x = 1"), ast.parse("x = 1"))
        assert not compare(ast.parse("x = 1"), ast.parse("x = 2"))

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="ast.compare arrived in 3.14")
    def test_stops_at_the_first_difference(self) -> None:
        compare = getattr(ast, "compare")  # noqa: B009 - absent from typeshed before 3.14
        calls = 0

        class Counted:
            def __eq__(self, other: object) -> bool:
                nonlocal calls
                calls += 1
                return True

            __hash__ = None  # type: ignore[assignment]

        def tree(first: int) -> ast.Module:
            body: list[ast.stmt] = [
                ast.Expr(value=ast.Constant(value=first)),
                ast.Expr(value=ast.Constant(value=cast(Any, Counted()))),
            ]
            return ast.Module(body=body, type_ignores=[])

        assert compare(tree(1), tree(1))
        assert calls == 1
        assert not compare(tree(1), tree(2))
        assert calls == 1

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="ast.compare arrived in 3.14")
    def test_compare_attributes_adds_the_positions(self) -> None:
        compare = getattr(ast, "compare")  # noqa: B009 - absent from typeshed before 3.14
        same_shape = ast.parse("x = 1"), ast.parse("\n\nx = 1")

        assert compare(*same_shape)
        assert not compare(*same_shape, compare_attributes=True)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="ast.compare arrived in 3.14")
    def test_linear_in_the_nodes(self) -> None:
        compare = getattr(ast, "compare")  # noqa: B009 - absent from typeshed before 3.14
        small, other_small = wide_tree(1_000), wide_tree(1_000)
        large, other_large = wide_tree(4_000), wide_tree(4_000)

        growth = ratio(lambda: compare(small, other_small), lambda: compare(large, other_large))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the nodes"


class TestChildren:
    def test_iter_child_nodes_includes_list_items(self) -> None:
        tree = ast.parse("x = f(1, 2)")
        call = tree.body[0].value  # type: ignore[attr-defined]

        assert [type(node).__name__ for node in ast.iter_child_nodes(call)] == [
            "Name",
            "Constant",
            "Constant",
        ]
        assert len(list(ast.iter_child_nodes(wide_tree(1_000)))) == 1_000

    def test_iter_child_nodes_yields_nothing_for_a_global(self) -> None:
        """Its names are strings, scanned but not yielded."""
        node = ast.parse("global " + ", ".join(f"n{i}" for i in range(100))).body[0]

        assert list(ast.iter_child_nodes(node)) == []
        assert len(node.names) == 100  # type: ignore[attr-defined]

    def test_iter_fields_lists_the_fields(self) -> None:
        assert [name for name, _ in ast.iter_fields(ast.parse("x = 1"))] == ["body", "type_ignores"]

    def test_copy_location_copies_four_attributes(self) -> None:
        old = ast.parse("x = 1").body[0]
        new = ast.copy_location(ast.Pass(), old)

        assert (new.lineno, new.col_offset, new.end_lineno, new.end_col_offset) == (1, 0, 1, 5)

    def test_copy_location_takes_only_what_the_source_has(self) -> None:
        """It copies rather than fills: a start position the source lacks is
        left alone, while an end position is copied even as None."""
        bare = ast.Name(id="z", ctx=ast.Load())
        target = ast.Name(id="w", ctx=ast.Load(), **POSITION)

        ast.copy_location(target, bare)

        assert (target.lineno, target.col_offset) == (POSITION["lineno"], POSITION["col_offset"])
        assert target.end_lineno is None and target.end_col_offset is None

    def test_copy_location_overwrites_what_the_source_does_have(self) -> None:
        source = ast.Name(id="z", ctx=ast.Load(), **POSITION)
        target = ast.Name(
            id="w", ctx=ast.Load(), lineno=9, col_offset=9, end_lineno=9, end_col_offset=9
        )

        ast.copy_location(target, source)

        assert (target.lineno, target.col_offset) == (POSITION["lineno"], POSITION["col_offset"])
        assert (target.end_lineno, target.end_col_offset) == (
            POSITION["end_lineno"],
            POSITION["end_col_offset"],
        )


class TestDocstring:
    @pytest.mark.timing
    def test_independent_of_the_statements_after_it(self) -> None:
        docstring = '"""doc"""\n'
        small, large = (
            ast.parse(docstring + statements(1_000)),
            ast.parse(docstring + statements(16_000)),
        )

        growth = ratio(
            batched(lambda: ast.get_docstring(small, clean=False)),
            batched(lambda: ast.get_docstring(large, clean=False)),
        )

        assert growth < 3, f"x{growth:.1f} for 16x the statements; a scan would be 16"

    @pytest.mark.timing
    def test_clean_is_linear_in_the_docstring(self) -> None:
        small, large = (
            ast.parse('"""' + "word\n" * 1_000 + '"""'),
            ast.parse('"""' + "word\n" * 4_000 + '"""'),
        )

        cleaned = ratio(lambda: ast.get_docstring(small), lambda: ast.get_docstring(large))
        raw = ratio(
            batched(lambda: ast.get_docstring(small, clean=False)),
            batched(lambda: ast.get_docstring(large, clean=False)),
        )

        assert 2.5 < cleaned < 7, f"clean=True x{cleaned:.1f} for 4x the lines"
        assert raw < 2.5, f"clean=False x{raw:.1f} for 4x the lines"

    def test_leading_blank_lines_cost_the_line_count_each(self) -> None:
        """Count list entries shifted while cleaning fixed-width text lines.

        A str subclass supplies a list subclass from expandtabs().split().
        Each pop performs the normal list operation and records how many
        entries it shifts. The result must match cleanup of an ordinary str.
        Text width and indentation are not varied; other cleanup work is
        not counted.
        """
        shifted: list[int] = []

        class Lines(list[str]):
            def pop(self, index: SupportsIndex = -1) -> str:
                position = index.__index__()
                if position < 0:
                    position += len(self)
                moved = len(self) - position - 1
                result = super().pop(index)
                shifted.append(moved)
                return result

        class Docstring(str):
            def expandtabs(self, tabsize: SupportsIndex = 8) -> "Docstring":
                return Docstring(super().expandtabs(tabsize))

            def split(self, sep: str | None = None, maxsplit: SupportsIndex = -1) -> list[str]:
                return Lines(super().split(sep, maxsplit))

        for blank, text in ((100, 400), (400, 400), (100, 100), (800, 800)):
            raw = "\n" * blank + "\n".join(["word"] * text)
            tree = ast.parse('"""' + raw + '"""')
            expected = ast.get_docstring(tree)
            statement = tree.body[0]
            assert isinstance(statement, ast.Expr)
            assert isinstance(statement.value, ast.Constant)
            statement.value.value = Docstring(raw)
            shifted.clear()

            assert ast.get_docstring(tree) == expected == "\n".join(["word"] * text)
            assert len(shifted) == blank
            assert sum(shifted) == blank * text + blank * (blank - 1) // 2

    def test_reads_only_the_first_statement(self) -> None:
        assert ast.get_docstring(ast.parse('"""doc"""\n"""not doc"""')) == "doc"
        assert ast.get_docstring(ast.parse('x = 1\n"""not doc"""')) is None


class TestSourceSegment:
    @pytest.mark.timing
    def test_the_last_statement_costs_the_whole_source(self) -> None:
        """Hold line width and returned segment fixed while source grows 16x.

        Warm both inputs before measuring so interpreter specialization and
        lazy regex compilation are setup costs. Linear predicts 16x and
        quadratic 256x; measured growth is 16-17x on 3.11.14 and 3.14.7.
        Line width, newline style, and multi-line segments are not varied.
        """
        small, large = "x = 1\n" * 1_000, "x = 1\n" * 16_000
        small_node, large_node = ast.parse(small).body[-1], ast.parse(large).body[-1]

        for source, node in ((small, small_node), (large, large_node)):
            assert ast.get_source_segment(source, node) == "x = 1"

        growth = ratio(
            lambda: ast.get_source_segment(small, small_node),
            lambda: ast.get_source_segment(large, large_node),
            repeats=7,
        )

        assert 6 < growth < 48, f"x{growth:.1f} for 16x the source; linear 16, quadratic 256"

    @pytest.mark.timing
    def test_the_first_statement_costs_only_its_prefix_from_312(self) -> None:
        small, large = statements(1_000), statements(4_000)
        small_node, large_node = ast.parse(small).body[0], ast.parse(large).body[0]

        growth = ratio(
            batched(lambda: ast.get_source_segment(small, small_node)),
            batched(lambda: ast.get_source_segment(large, large_node)),
        )

        if sys.version_info >= (3, 12):
            assert growth < 2.5, f"x{growth:.1f} for 4x the source after the node"
        else:
            assert growth > 2.5, f"x{growth:.1f}; the whole source is split before 3.12"

    def test_padded_pads_the_first_line_to_its_column(self) -> None:
        source = "if x:\n    y = (1 +\n         2)\n"
        node = ast.parse(source).body[0].body[0]  # type: ignore[attr-defined]

        assert ast.get_source_segment(source, node) == "y = (1 +\n         2)"
        assert ast.get_source_segment(source, node, padded=True) == "    y = (1 +\n         2)"

    def test_documented_segments(self) -> None:
        source = "\ndef first():\n    return 1\n\ndef second():\n    return 2\n"
        tree = ast.parse(source)

        segments = [ast.get_source_segment(source, node) for node in tree.body]

        assert segments == ["def first():\n    return 1", "def second():\n    return 2"]


class TestLiteralEval:
    @pytest.mark.timing
    def test_linear_in_the_literal(self) -> None:
        small = "[" + ", ".join(map(str, range(1_000))) + "]"
        large = "[" + ", ".join(map(str, range(4_000))) + "]"

        growth = ratio(lambda: ast.literal_eval(small), lambda: ast.literal_eval(large))

        assert 2.5 < growth < 8, f"x{growth:.1f} for 4x the items"

    def test_documented_values(self) -> None:
        assert ast.literal_eval("{'name': 'Alice', 'age': 30}") == {"name": "Alice", "age": 30}
        assert ast.literal_eval("[1, 2, 3, 4, 5]") == [1, 2, 3, 4, 5]
        with pytest.raises(ValueError):
            ast.literal_eval("__import__('os').system('rm -rf /')")

    def test_a_string_is_parsed_and_a_tree_is_not(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """literal_eval() calls the module-level parse(), so counting it
        separates the O(n) parse from the rebuild."""
        calls = 0
        real = ast.parse

        def counted(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return real(*args, **kwargs)

        tree = ast.parse("[1, 2]", mode="eval")
        monkeypatch.setattr(ast, "parse", counted)

        assert ast.literal_eval("[1, 2]") == [1, 2]
        assert calls == 1
        assert ast.literal_eval(tree) == [1, 2]
        assert calls == 1

    def test_accepted_and_rejected_forms(self) -> None:
        assert ast.literal_eval("set()") == set()
        assert ast.literal_eval("{1, 2}") == {1, 2}
        assert ast.literal_eval("-1") == -1
        assert ast.literal_eval("1 + 2j") == 1 + 2j
        for expression in ("x", "f(1)", "1 + 2", "2j + 1"):
            with pytest.raises(ValueError):
                ast.literal_eval(expression)
        with pytest.raises(SyntaxError):
            ast.literal_eval("1 +")
        with pytest.raises(TypeError):
            ast.literal_eval("{[]: 1}")

    @pytest.mark.timing
    def test_colliding_keys_make_a_set_quadratic(self) -> None:
        """Isolate set reconstruction with parsed trees and a 16x size step.

        Linear and quadratic growth are separated by the x64 threshold.
        CPython 3.14.7 measures x15.5 for distinct hashes and x283 for
        collisions. Parsing is covered separately; only integer keys and
        flat sets are varied here.
        """
        modulus = sys.hash_info.modulus

        def keys(count: int, spread: int) -> ast.Expression:
            values = [k * modulus + k * spread for k in range(1, count + 1)]
            assert len({hash(value) for value in values}) == (count if spread else 1)
            source = "{" + ", ".join(map(str, values)) + "}"
            tree = ast.parse(source, mode="eval")
            assert ast.literal_eval(tree) == set(values)
            return tree

        colliding_small, colliding_large = keys(500, 0), keys(8_000, 0)
        distinct_small, distinct_large = keys(500, 1), keys(8_000, 1)

        colliding = ratio(
            lambda: ast.literal_eval(colliding_small), lambda: ast.literal_eval(colliding_large), 3
        )
        distinct = ratio(
            lambda: ast.literal_eval(distinct_small), lambda: ast.literal_eval(distinct_large), 3
        )

        assert colliding > 64, f"x{colliding:.1f} for 16x colliding keys; quadratic would be 256"
        assert distinct < 64, f"x{distinct:.1f} for 16x distinct keys; linear would be 16"


class TestMain:
    def test_parses_and_dumps_a_file(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "sample.py"
        script.write_text("x = 1 + 2\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "ast", str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        assert "Assign(" in result.stdout
        assert "BinOp(" in result.stdout
        assert any(line.startswith("   ") for line in result.stdout.splitlines()), "not indented"


class TestVersionNotes:
    @pytest.mark.parametrize(
        ("name", "since"),
        [
            ("TryStar", (3, 11)),
            ("TypeAlias", (3, 12)),
            ("TypeVar", (3, 12)),
            ("ParamSpec", (3, 12)),
            ("TypeVarTuple", (3, 12)),
            ("type_param", (3, 12)),
            ("PyCF_OPTIMIZED_AST", (3, 13)),
            ("compare", (3, 14)),
            ("TemplateStr", (3, 14)),
            ("Interpolation", (3, 14)),
        ],
    )
    def test_added(self, name: str, since: tuple[int, int]) -> None:
        assert hasattr(ast, name) == (sys.version_info >= since)

    @pytest.mark.parametrize("name", ["Num", "Str", "Bytes", "NameConstant", "Ellipsis"])
    def test_removed_in_314(self, name: str) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            present = hasattr(ast, name)

        assert present == (sys.version_info < (3, 14))

    def test_visit_constant_shim_went_with_the_deprecated_nodes(self) -> None:
        """NodeVisitor carried a visit_Constant that forwarded to visit_Num and
        its siblings; 3.14 removed the nodes and the shim together."""
        assert hasattr(ast.NodeVisitor, "visit_Constant") == (sys.version_info < (3, 14))

    def test_dump_show_empty_arrived_in_313(self) -> None:
        """The default changed with the argument: an empty list field is
        printed before 3.13 and omitted from it."""
        default = ast.dump(ast.parse("x = 1"))

        if sys.version_info >= (3, 13):
            assert "type_ignores=[]" not in default
            assert "type_ignores=[]" in ast.dump(ast.parse("x = 1"), show_empty=True)
        else:
            assert "type_ignores=[]" in default
            with pytest.raises(TypeError):
                ast.dump(ast.parse("x = 1"), show_empty=True)  # type: ignore[call-arg]

    def test_parse_optimize_folds_constants_on_313_only(self) -> None:
        if sys.version_info < (3, 13):
            with pytest.raises(TypeError):
                ast.parse("1 + 2", optimize=1)  # type: ignore[call-arg]
            return

        folded = ast.parse("1 + 2", optimize=1).body[0].value  # type: ignore[attr-defined]
        debug = ast.parse("__debug__", optimize=1).body[0].value  # type: ignore[attr-defined]

        assert isinstance(folded, ast.Constant) == (sys.version_info < (3, 14))
        assert isinstance(debug, ast.Constant) and debug.value is False


class TestNodeObjects:
    """The AST rows: fields are stored, not copied, and the class tuples are
    shared. A constructor that copied its list would break `is`."""

    def test_construction_stores_the_arguments(self) -> None:
        node = ast.Name(id="x", ctx=ast.Load())

        assert node.id == "x"
        assert isinstance(node.ctx, ast.Load)

    def test_a_list_field_is_kept_not_copied(self) -> None:
        body: list[ast.stmt] = [ast.Pass(**POSITION)]

        module = ast.Module(body=body, type_ignores=[])

        assert module.body is body

    def test_fields_and_attributes_are_the_class_tuples(self) -> None:
        node = ast.Name(id="x", ctx=ast.Load())

        assert node._fields is ast.Name._fields
        assert node._attributes is ast.Name._attributes
        assert ast.Name._fields == ("id", "ctx")
        assert ast.Name._attributes == ("lineno", "col_offset", "end_lineno", "end_col_offset")
        assert ast.Module._attributes == ()
        assert ast.AST._fields == ()

    def test_positions_are_attributes_not_fields(self) -> None:
        """The page prices them separately because they are not in _fields."""
        assert "lineno" not in ast.Name._fields
        assert set(ast.Name._attributes) == {
            "lineno",
            "col_offset",
            "end_lineno",
            "end_col_offset",
        }
        assert not hasattr(ast.Name(id="x", ctx=ast.Load()), "lineno")

    def test_an_operator_class_carries_no_positions(self) -> None:
        """The position row applies to the classes whose _attributes names
        them; fix_missing_locations() leaves the others alone."""
        operator = ast.Add()
        name = ast.Name(id="x", ctx=ast.Load())
        total = ast.BinOp(left=name, op=operator, right=ast.Constant(value=1, kind=None))
        tree = ast.Module(body=[ast.Expr(value=total)], type_ignores=[])

        ast.fix_missing_locations(tree)

        assert total.op is operator
        assert ast.Add._attributes == ()
        assert not hasattr(operator, "lineno")
        assert name.lineno == 1

    def test_type_comments_are_collected_only_on_request(self) -> None:
        source = "x = 1  # type: int\n"

        plain = ast.parse(source).body[0]
        annotated = ast.parse(source, type_comments=True).body[0]

        assert plain.type_comment is None  # type: ignore[attr-defined]
        assert annotated.type_comment == "int"  # type: ignore[attr-defined]

    def test_field_defaults_arrived_in_313(self) -> None:
        """Before 3.13 an omitted field leaves no attribute at all."""
        if sys.version_info < (3, 13):
            with pytest.raises(AttributeError):
                ast.Name(id="x").ctx  # noqa: B018 - the access is the assertion
            with pytest.raises(AttributeError):
                ast.Module().body  # type: ignore[call-arg] # noqa: B018 - it is the assertion
            assert not hasattr(ast.Name, "_field_types")
            return

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            first, second = ast.Module(), ast.Module()  # type: ignore[call-arg]

        assert first.body == [] and first.body is not second.body
        assert ast.Name(id="x").ctx is ast.Name(id="y").ctx
        assert ast.Name._field_types == {"id": str, "ctx": ast.expr_context}

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="constructors warn from 3.13")
    def test_omitting_a_required_field_warns_from_313(self) -> None:
        with pytest.warns(DeprecationWarning, match="missing 1 required positional argument"):
            ast.Name()  # type: ignore[call-arg]

    def test_index_returns_its_value_and_extslice_copies_its_dims(self) -> None:
        """The two deprecated classes that are not plain constructors."""
        value = ast.Constant(value=1, **POSITION)
        dims = [ast.Constant(value=i, **POSITION) for i in range(5)]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            index = ast.Index(value)  # type: ignore[attr-defined]
            extended = ast.ExtSlice(dims)  # type: ignore[attr-defined]

        assert index is value
        assert isinstance(extended, ast.Tuple)
        assert extended.elts == dims and extended.elts is not dims


class TestNodeClassGroups:
    """The Node classes table groups the grammar; each row's Notes name the
    abstract base its classes belong to."""

    @staticmethod
    def rows(section: str | None = None) -> list[tuple[list[str], list[str]]]:
        """Operation-cell class names and Notes-cell group names, per row."""
        if section is None:
            text = PAGE.read_text(encoding="utf-8")
            section = text[text.index("### Node classes") : text.index("### Traversal")]
        found: list[tuple[list[str], list[str]]] = []
        for line in section.splitlines():
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) != 6 or cells[1].startswith(("Operation", "---")):
                continue
            names = re.findall(r"`ast\.(\w+)", cells[1])
            groups = re.findall(r"`ast\.([a-z]\w*)", cells[4])
            found.append((names, groups))
        return found

    def test_the_table_was_found(self) -> None:
        rows = self.rows()

        assert len(rows) >= 8
        assert sum(len(names) for names, _ in rows) >= 90

    def test_every_listed_class_belongs_to_its_group(self) -> None:
        """`issubclass` alone would pass for a row that listed its own group,
        so each name has to be a *proper* subclass of one of them."""
        checked = 0
        for names, groups in self.rows():
            bases = tuple(
                getattr(ast, group)
                for group in groups
                if isinstance(getattr(ast, group, None), type)
            )
            if not names or not bases:
                continue
            for name in names:
                node = getattr(ast, name, None)
                if node is None:  # added in a later version than this one
                    continue
                assert node not in bases, f"{name} is a group, not one of its classes"
                assert issubclass(node, bases), f"{name} is not one of {groups}"
                checked += 1

        assert checked >= 80, f"only {checked} classes were checked"

    def test_the_extractor_would_catch_a_group_in_a_concrete_row(self) -> None:
        """The check above is only worth running if `rows()` itself reports a
        group name planted among a row's classes."""
        names, groups = next((n, g) for n, g in self.rows() if g)
        planted = (
            "| `ast."
            + "`, `ast.".join([*names, groups[0]])
            + "` | O(1) | O(1) | The `ast."
            + groups[0]
            + "` classes |"
        )

        extracted, extracted_groups = self.rows(planted)[0]

        assert extracted_groups == [groups[0]]
        assert groups[0] in extracted

    def test_the_abstract_row_lists_every_group_the_others_name(self) -> None:
        rows = self.rows()
        named = {group for _, groups in rows for group in groups}
        abstract = next(names for names, groups in rows if not groups and "mod" in names)

        assert named <= set(abstract), f"not listed as abstract: {sorted(named - set(abstract))}"
        for name in abstract:  # type_param and its like arrive in a later version
            group = getattr(ast, name, None)
            assert group is None or issubclass(group, ast.AST), name


class TestCompileFlags:
    """The flags are integers the module hands to compile(); each one selects
    what compile() does, and none of them is a cost."""

    CO_COROUTINE = 0x80

    def test_parse_hands_the_only_ast_flag_to_compile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Equal output would not show delegation, so the builtin is recorded."""
        seen: list[int] = []
        real = builtins.compile

        def recorded(
            source: Any, filename: Any, mode: Any, flags: int = 0, *args: Any, **kwargs: Any
        ) -> Any:
            seen.append(flags)
            return real(source, filename, mode, flags, *args, **kwargs)

        monkeypatch.setattr(builtins, "compile", recorded)
        tree = ast.parse("x = 1 + 2")

        assert len(seen) == 1
        assert seen[0] & ast.PyCF_ONLY_AST
        assert isinstance(tree, ast.Module)

    def test_the_flags_are_integers_and_two_of_them_change_what_compile_returns(self) -> None:
        """`PyCF_OPTIMIZED_AST` is only checked for its type here; what it does
        is asserted in TestVersionNotes through `parse(optimize=)`."""
        flags = [ast.PyCF_ONLY_AST, ast.PyCF_TYPE_COMMENTS, ast.PyCF_ALLOW_TOP_LEVEL_AWAIT]
        if sys.version_info >= (3, 13):
            flags.append(ast.PyCF_OPTIMIZED_AST)

        assert all(isinstance(flag, int) for flag in flags)

        commented = compile(
            "x = 1  # type: int", "<s>", "exec", ast.PyCF_ONLY_AST | ast.PyCF_TYPE_COMMENTS
        )
        assert commented.body[0].type_comment == "int"

        # The parser accepts top-level await on its own; the flag is what lets
        # the compiler turn the tree into code.
        tree = compile("await f()", "<s>", "exec", ast.PyCF_ONLY_AST)
        assert isinstance(tree, ast.Module)
        assert isinstance(tree.body[0], ast.Expr)
        assert isinstance(tree.body[0].value, ast.Await)
        top_level = compile(tree, "<s>", "exec", ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        assert top_level.co_flags & self.CO_COROUTINE
        with pytest.raises(SyntaxError):
            compile(tree, "<s>", "exec")


EXPECTED_BLOCKS = 12


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
    """Every python block runs, under the interpreter running the tests."""

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

    def test_the_runner_catches_a_flipped_assertion(self, tmp_path: pathlib.Path) -> None:
        """The blocks assert their own results, so the runner has to fail when
        one of those assertions is made false."""
        line, original = next(
            (line, source) for line, source in _blocks() if '"x", "y", "z", "x", "y"' in source
        )
        broken = original.replace('"x", "y", "z", "x", "y"', '"x", "y", "z"', 1)
        assert broken != original, f"the mutation did not rewrite {PAGE.name}:{line}"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("ast.parse(code)", "ast.parse(undefined_code)", 1)
        assert broken != original, "the mutation did not rewrite the call"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
