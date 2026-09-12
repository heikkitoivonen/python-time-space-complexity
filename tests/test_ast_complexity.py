"""Tests for docs/stdlib/ast.md.

The page's size variables: n = source length, N = nodes, h = depth, w = widest
level, k = direct children. Most of them can be settled by observation:

* recursion versus a queue is settled by depth alone. A chain of 5,000 unary
  minuses is 5,000 levels deep, past the default recursion limit; `walk()`
  yields all 10,002 nodes (each `UnaryOp` carries an `op` node) while
  `NodeVisitor.visit()`, `dump()` and `unparse()` raise `RecursionError`, on
  every supported version;
* `walk()`'s O(w) space is read off the queue itself: the function imports
  `deque` from `collections` at call time, so a subclass installed there
  records its peak length - 4,000 for 1,000 statements and 16,000 for 4,000,
  the widest level being the targets and values of every assignment, and 2
  for the deep chain however long it is. The queue holds what is left of
  one level plus what has been found of the next, so the peak is between w
  and 2w;
* `unparse()` of 250 then 1,000 nested `while` blocks emits x15.7 the
  characters in x6.0 the time: N and b grow together, so the N * b term is
  quadratic in the depth. With the two held apart the output is linear in
  each: 1,000 then 4,000 statements 200 blocks deep emit x4.0 the characters,
  and 1,000 statements 100 then 400 blocks deep x3.9; the test asserts the
  character count, which is exact, and the growth in nodes separately;
* `literal_eval()` of a set of 2,000 then 8,000 keys that all hash alike
  (multiples of `sys.hash_info.modulus`): x15.2, against x4.6 for distinct
  keys of the same width, and x34 between the two at 8,000 keys;
* `compare()` stops at the first difference: a value in a later statement
  whose `__eq__` counts its calls is never consulted when the first
  statement already differs;
* `NodeVisitor` dispatches by class name and `NodeTransformer` rebuilds a
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
* `unparse`: x3.9 wide and x3.7 for the deep chain, so it is linear in both;
* `get_source_segment` of the last statement: x16-x17 on 3.11.14 and 3.14.7
  for 16x the source (1,000 then 16,000 fixed-width lines), after warm-up;
  of the first statement: x1.3 on 3.14 and x4.2 on 3.10.21, which has no
  `maxlines` cut in `_splitlines_no_ff` (added by gh-103285 in 3.12);
* `get_docstring` with 16x the statements after the docstring, `clean=False`:
  x1.0; with a 1,000-then-4,000-line docstring: x4.1 under `clean=True` and
  x1.0 under `clean=False`; with leading blank lines, which `cleandoc` pops
  from the front of its line list one at a time: x3.4-x3.8 for 4x the blank
  lines at 4,000 text lines, and x55-x60 for 8x both (2,000 to 16,000),
  the k * l term, with parsing outside the timer.

Sub-microsecond calls - `get_source_segment` of the first line, the
`get_docstring` constant-time cases - are run 200 times per sample. The deep
measurements run in a worker thread with a 256 MB stack and a raised
recursion limit, because the limit alone lets 3.10 and 3.11 overflow the C
stack on a 4,000-deep chain and take the interpreter down.

Not measured: `main()`, the command-line entry, is asserted to parse and dump
a file through `python -m ast`; its bound is `parse` plus `dump` by
construction. The parser is measured linear on three shapes - statement
lists, binary chains, unary chains - which is evidence for those shapes, not
a proof for every grammar path; the parenthesis nesting that could defeat
memoization is capped at 200 levels by `SyntaxError`, pinned exactly below.

Not varied: node kinds, and the length of string fields. The wide trees are
assignment statements and the deep trees unary operators; the bounds do not
depend on the kind, but no test covers a tree mixing many kinds at scale, and
every `Constant` here holds a small int and every identifier is short, so the
length a long string or identifier adds to `parse`, `dump`, `unparse` and
`compare` is stated from the page's definition rather than measured.
"""

import ast
import collections
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import warnings
from collections.abc import Callable
from typing import Any, cast

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


def nested_blocks(depth: int, statements: int = 1) -> ast.Module:
    """`while True:` blocks nested `depth` deep around `statements` passes."""
    body: list[ast.stmt] = [ast.Pass(**POSITION) for _ in range(statements)]
    for _ in range(depth):
        test = ast.Constant(value=True, **POSITION)
        body = [ast.While(test=test, body=body, orelse=[], **POSITION)]
    return ast.Module(body=body, type_ignores=[])


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
        small, large = statements(1_000), statements(4_000)

        growth = ratio(lambda: ast.parse(small), lambda: ast.parse(large))

        assert 2.5 < growth < 8, f"x{growth:.1f} for 4x the source"

    @pytest.mark.timing
    def test_linear_in_a_binary_chain(self) -> None:
        small, large = " + ".join(["a"] * 1_000), " + ".join(["a"] * 4_000)

        growth = in_deep_stack(lambda: ratio(lambda: ast.parse(small), lambda: ast.parse(large)))

        assert 2.5 < growth < 8, f"x{growth:.1f} for 4x the terms"

    def test_parenthesis_nesting_is_capped_at_200(self) -> None:
        assert isinstance(ast.parse("(" * 200 + "1" + ")" * 200), ast.Module)
        with pytest.raises(SyntaxError, match="too many nested parentheses"):
            ast.parse("(" * 201 + "1" + ")" * 201)


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
        """1,000 assignments have 2,000 targets and values on one level, and
        the queue also carries the statements not yet popped: between w and
        2w, here 4,000, and four times that for four times the statements."""
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

    @pytest.mark.timing
    def test_leading_blank_lines_cost_the_line_count_each(self) -> None:
        """Time cleanup of prebuilt trees with fixed-width text lines.

        For 2,000 then 16,000 blank and text lines, linear work predicts 8x
        and k * l predicts 64x. CPython 3.11.14 measures about 55x. Parsing
        is setup; text width and indentation are not varied.
        """

        def docstring(blank: int, text: int) -> ast.Module:
            return ast.parse('"""' + "\n" * blank + "word\n" * text + '"""')

        fewer_blanks, more_blanks = docstring(1_000, 4_000), docstring(4_000, 4_000)
        small, large = docstring(2_000, 2_000), docstring(16_000, 16_000)

        blanks = ratio(
            lambda: ast.get_docstring(fewer_blanks),
            lambda: ast.get_docstring(more_blanks),
        )
        both = ratio(
            lambda: ast.get_docstring(small),
            lambda: ast.get_docstring(large),
        )

        assert 2.5 < blanks < 7, f"x{blanks:.1f} for 4x the leading blank lines"
        assert both > 24, f"x{both:.1f} for 8x both; linear would be 8, k * l 64"

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
        modulus = sys.hash_info.modulus
        assert len({hash(k * modulus) for k in range(1, 50)}) == 1

        def keys(count: int, spread: int) -> str:
            return "{" + ", ".join(str(k * modulus + k * spread) for k in range(1, count + 1)) + "}"

        colliding_small, colliding_large = keys(2_000, 0), keys(8_000, 0)
        distinct_small, distinct_large = keys(2_000, 1), keys(8_000, 1)

        colliding = ratio(
            lambda: ast.literal_eval(colliding_small), lambda: ast.literal_eval(colliding_large), 3
        )
        distinct = ratio(
            lambda: ast.literal_eval(distinct_small), lambda: ast.literal_eval(distinct_large), 3
        )

        assert colliding > 9, f"x{colliding:.1f} for 4x colliding keys; quadratic would be 16"
        assert distinct < 7, f"x{distinct:.1f} for 4x distinct keys; linear would be 4"


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

    def test_dump_show_empty_arrived_in_313(self) -> None:
        if sys.version_info >= (3, 13):
            assert "type_ignores=[]" in ast.dump(ast.parse("x = 1"), show_empty=True)
        else:
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


class TestPublicNamesAreDocumented:
    """Every non-node public name has a row or a mention; every node class
    is covered by the construction row."""

    VERSION_GATED = {"compare": (3, 14), "PyCF_OPTIMIZED_AST": (3, 13)}
    LEAKED_IMPORTS = {"contextmanager", "IntEnum", "auto", "nullcontext", "sys", "re"}
    """Names ast exposes by importing them at module level before 3.14."""

    @staticmethod
    def documented_names() -> set[str]:
        return set(re.findall(r"`(?:ast\.)?(\w+)", PAGE.read_text(encoding="utf-8")))

    def test_the_extractor_sees_the_table(self) -> None:
        assert {"parse", "walk", "NodeVisitor", "PyCF_ONLY_AST"} <= self.documented_names()

    def test_every_non_node_public_name_is_documented(self) -> None:
        public = {
            name
            for name in dir(ast)
            if not name.startswith("_")
            and not (
                isinstance(getattr(ast, name), type) and issubclass(getattr(ast, name), ast.AST)
            )
        }

        missing = public - self.documented_names() - self.LEAKED_IMPORTS

        assert not missing, f"public names without a row: {sorted(missing)}"

    def test_the_leaked_imports_are_gone_from_314(self) -> None:
        present = self.LEAKED_IMPORTS & set(dir(ast))

        assert bool(present) == (sys.version_info < (3, 14)), sorted(present)

    def test_every_documented_callable_exists(self) -> None:
        for name in (
            "parse",
            "literal_eval",
            "walk",
            "iter_child_nodes",
            "iter_fields",
            "NodeVisitor",
            "NodeTransformer",
            "dump",
            "unparse",
            "copy_location",
            "fix_missing_locations",
            "increment_lineno",
            "get_docstring",
            "get_source_segment",
            "main",
            "compare",
        ):
            since = self.VERSION_GATED.get(name)
            if since and sys.version_info < since:
                assert not hasattr(ast, name), name
            else:
                assert callable(getattr(ast, name)), name


EXPECTED_BLOCKS = 8


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

    def test_the_walk_example_prints_the_documented_order(self, tmp_path: pathlib.Path) -> None:
        source = next(source for _, source in _blocks() if "Variable:" in source)

        result = _run(source, tmp_path)

        assert (
            result.stdout.split()
            == "Variable: x Variable: y Variable: z Variable: x Variable: y".split()
        )

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("ast.parse(code)", "ast.parse(undefined_code)", 1)
        assert broken != original, "the mutation did not rewrite the call"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
