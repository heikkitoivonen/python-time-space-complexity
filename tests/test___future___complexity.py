"""Tests for docs/stdlib/__future__.md.

The page prices a compiler directive and a fixed feature table. Every claim it
makes is settled by observation rather than timing: code-object flags and
bytecode say what the compiler did, a counting annotation expression says when
an annotation was evaluated, and identity says whether an accessor returns
what it stored.

Measurement scope:

* A future statement is a compiler flag: the module and nested code objects
  compiled with it carry the feature's `compiler_flag` in `co_flags`, and code
  compiled without it does not. Executing the statement binds the module's own
  `_Feature` object. A docstring, comments and a second future statement may
  precede it; an ordinary statement before it, or an unknown feature, raises
  `SyntaxError` from `compile()`, so no import ever runs.
* The eight mandatory features change nothing: a source using division, a
  generator, `with`, `print`, string literals, an import and an
  annotation compiles to the same bytecode, constants and names with each
  feature's flag as without it, and each has a `mandatory` release at or before
  the running interpreter. `annotations` under the same comparison changes the
  constants, which is the control.
* Defining an annotated function is O(1) with `annotations`: the module's
  bytecode for a `def` with 2 and with 2,000 annotated parameters stays within
  2x in instruction count on every supported version. Without the import,
  3.10-3.13 grow more than 100x, one evaluation per annotation, and 3.14 stays
  within 2x. The instruction count is the evidence and the definition is not
  timed: the `dis` output shows the annotations reaching the function as one
  constant tuple on 3.10-3.13 and one `__annotate__` code object on 3.14.
* A counting annotation expression runs zero times at definition and on
  `__annotations__` reads under the import, for a function and a class body,
  whose values are the source strings, and zero times when a module body runs.
  Without the import, class and module bodies are observed only on 3.10-3.13,
  where they evaluate each annotation once. Without the import it
  runs once per annotation at definition on 3.10-3.13, and on 3.14 zero times
  at definition and once per annotation on the first read. Both cases return
  the same dictionary object on a second read with no further evaluation, and
  the dictionary has one entry per annotation.
* `typing.get_type_hints()` over a function with 50 counting string
  annotations evaluates all 50 on each of two calls.
* `compile()` and `exec()` of a string inside this module, which has the
  `annotations` import, inherit its flag; `dont_inherit=True` stops that, and
  `flags=annotations.compiler_flag` turns it back on.
* `all_feature_names` has ten names including `barry_as_FLUFL`, each naming a
  `_Feature`; the two still optional are `barry_as_FLUFL` and `annotations`.
  `getOptionalRelease()` and `getMandatoryRelease()` return the `optional` and
  `mandatory` objects themselves. `annotations.mandatory` is asserted to be
  `(3, 11, 0, 'alpha', 0)` on 3.10 and `None` on 3.11+, which matches
  Lib/__future__.py at v3.10.19, v3.11.14, v3.12.12, v3.13.11 and v3.14.2.
* Every fenced Python block runs in its own subprocess, and a mutated assertion
  in one of them is asserted to fail.

Not settled here:

* The O(1) rows for reading the feature table and a `_Feature` attribute are
  attribute access on a pure-Python module and object, read from
  Lib/__future__.py; they are not measured.
* `compiler_flag` values are not asserted beyond `annotations` enabling its
  feature; the page does not state them.
* Coverage: the page-scoped audit reports no missing names. The official
  inventory's `_Feature`, `compiler_flag`, `getOptionalRelease` and
  `getMandatoryRelease` are listed as documented but unresolved, because the
  audit does not inspect a single-underscore class; the page documents them in
  its `_Feature` table and the tests above cover them. `all_feature_names`,
  `barry_as_FLUFL` and each feature's `optional`, `mandatory` and
  `compiler_flag` are runtime discoveries outside that inventory, covered by
  the same rows. The `CO_*` constants are not in `__all__` and are not on the
  page.
* Class and module bodies are observed for evaluation only; their definition
  cost is not measured, because executing a body of a annotated statements is
  O(a) whatever the import does.
"""

from __future__ import annotations
import __future__

import dis
import pathlib
import re
import subprocess
import sys
import textwrap
import typing
from types import CodeType
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "__future__.md"
EXPECTED_BLOCKS = 6

FLAG = __future__.annotations.compiler_flag
MANDATORY = (
    "nested_scopes",
    "generators",
    "division",
    "absolute_import",
    "with_statement",
    "print_function",
    "unicode_literals",
    "generator_stop",
)
FUTURE = "from __future__ import annotations\n"


class Counter:
    """An annotation expression that counts its evaluations."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> type:
        self.calls += 1
        return int


def compile_isolated(source: str, flags: int = 0) -> CodeType:
    """Compile without inheriting this module's own future flags."""
    return compile(source, "<test>", "exec", flags=flags, dont_inherit=True)


def run(source: str, counter: Counter) -> dict[str, Any]:
    namespace: dict[str, Any] = {"ann": counter}
    exec(compile_isolated(source), namespace)
    return namespace


def code_objects(code: CodeType) -> list[CodeType]:
    found = [code]
    for const in code.co_consts:
        if isinstance(const, CodeType):
            found.extend(code_objects(const))
    return found


def shape(code: CodeType) -> tuple[Any, ...]:
    """Bytecode, constants and names, recursively, without the flags."""
    consts = tuple(shape(c) if isinstance(c, CodeType) else c for c in code.co_consts)
    return (code.co_code, consts, code.co_names)


def definition(annotations: int, future: bool) -> str:
    params = ", ".join(f"p{index}: ann()" for index in range(annotations))
    return (FUTURE if future else "") + f"def f({params}):\n    pass\n"


def instructions(source: str) -> int:
    return len(list(dis.get_instructions(compile_isolated(source))))


class TestAFutureStatementIsACompilerFlag:
    """`from __future__ import feature` | O(1) | O(1): a flag set for the module
    at compile time, then an ordinary binding at run time."""

    def test_the_flag_is_on_every_code_object_compiled_with_it(self) -> None:
        source = FUTURE + "def f():\n    def g():\n        pass\n"

        with_it = code_objects(compile_isolated(source))
        without = code_objects(compile_isolated(source.removeprefix(FUTURE)))

        assert len(with_it) == 3
        assert all(code.co_flags & FLAG for code in with_it)
        assert not any(code.co_flags & FLAG for code in without)

    def test_running_it_binds_the_feature_object(self) -> None:
        namespace = run(FUTURE, Counter())

        assert namespace["annotations"] is __future__.annotations

    def test_a_docstring_comments_and_other_future_statements_may_precede_it(self) -> None:
        code = compile_isolated(
            '"""Doc."""\n# comment\n\nfrom __future__ import division\n' + FUTURE
        )

        assert code.co_flags & FLAG

    def test_a_statement_before_it_is_a_syntax_error(self) -> None:
        with pytest.raises(SyntaxError, match="beginning of the file"):
            compile_isolated("import sys\n" + FUTURE)

    def test_an_unknown_feature_is_a_syntax_error_at_compile_time(self) -> None:
        with pytest.raises(SyntaxError, match="spam is not defined"):
            compile_isolated("from __future__ import spam\n")


class TestMandatoryFeaturesChangeNothing:
    """The eight mandatory features are accepted and change nothing."""

    SOURCE = (
        "import os.path\n"
        "def g(x: int) -> str:\n"
        "    with x:\n"
        "        print('a', 'b')\n"
        "    yield 1 / 2\n"
    )

    @pytest.mark.parametrize("name", MANDATORY)
    def test_the_flag_leaves_the_compiled_code_unchanged(self, name: str) -> None:
        feature = getattr(__future__, name)

        with_flag = compile_isolated(self.SOURCE, feature.compiler_flag)

        assert shape(with_flag) == shape(compile_isolated(self.SOURCE))

    @pytest.mark.parametrize("name", MANDATORY)
    def test_it_is_mandatory_on_this_interpreter(self, name: str) -> None:
        mandatory = getattr(__future__, name).mandatory

        assert mandatory is not None and mandatory <= sys.version_info

    def test_annotations_under_the_same_comparison_changes_the_code(self) -> None:
        with_flag = compile_isolated(self.SOURCE, FLAG)

        assert shape(with_flag) != shape(compile_isolated(self.SOURCE))


class TestDefiningAnAnnotatedFunctionIsConstant:
    """Defining an annotated function | O(1) with the import, O(a + e) without
    on 3.10-3.13, O(1) without on 3.14+. Counted in bytecode instructions for 2
    and 2,000 annotated parameters."""

    def test_with_the_import_the_definition_does_not_grow(self) -> None:
        small = instructions(definition(2, future=True))
        large = instructions(definition(2_000, future=True))

        assert large < 2 * small, f"{small} -> {large} instructions"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="evaluation is deferred on 3.14+")
    def test_without_it_the_definition_evaluates_every_annotation(self) -> None:
        small = instructions(definition(2, future=False))
        large = instructions(definition(2_000, future=False))

        assert large > 100 * small, f"{small} -> {large} instructions"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="evaluation is eager before 3.14")
    def test_without_it_on_3_14_the_definition_does_not_grow(self) -> None:
        small = instructions(definition(2, future=False))
        large = instructions(definition(2_000, future=False))

        assert large < 2 * small, f"{small} -> {large} instructions"


class TestWhenAnnotationExpressionsRun:
    """With `annotations` no annotation expression runs; without it they run at
    definition on 3.10-3.13 and on the first `__annotations__` read on 3.14+.
    The first read is O(a) and cached."""

    ANNOTATIONS = 5

    def test_with_the_import_a_function_s_annotations_are_never_evaluated(self) -> None:
        counter = Counter()
        f = run(definition(self.ANNOTATIONS, future=True), counter)["f"]

        first = f.__annotations__

        assert counter.calls == 0
        assert first == {f"p{index}": "ann()" for index in range(self.ANNOTATIONS)}
        assert f.__annotations__ is first

    def test_with_the_import_class_and_module_bodies_evaluate_nothing(self) -> None:
        counter = Counter()
        namespace = run(FUTURE + "class C:\n    x: ann()\nmodule_level: ann()\n", counter)

        assert namespace["C"].__annotations__ == {"x": "ann()"}
        assert counter.calls == 0

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="evaluation is deferred on 3.14+")
    def test_without_it_the_definition_evaluates_them(self) -> None:
        counter = Counter()
        f = run(definition(self.ANNOTATIONS, future=False), counter)["f"]

        assert counter.calls == self.ANNOTATIONS
        first = f.__annotations__
        assert f.__annotations__ is first
        assert len(first) == self.ANNOTATIONS
        assert counter.calls == self.ANNOTATIONS

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="evaluation is deferred on 3.14+")
    def test_without_it_class_and_module_bodies_evaluate_them(self) -> None:
        counter = Counter()
        run("class C:\n    x: ann()\nmodule_level: ann()\n", counter)

        assert counter.calls == 2

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="evaluation is eager before 3.14")
    def test_without_it_on_3_14_the_first_read_evaluates_them_once(self) -> None:
        counter = Counter()
        f = run(definition(self.ANNOTATIONS, future=False), counter)["f"]

        assert counter.calls == 0
        first = f.__annotations__
        assert counter.calls == self.ANNOTATIONS
        assert f.__annotations__ is first
        assert len(first) == self.ANNOTATIONS
        assert counter.calls == self.ANNOTATIONS


class TestGetTypeHintsEvaluatesEveryCall:
    """`typing.get_type_hints(function)` | O(a + e) per call: nothing is cached."""

    def test_each_call_evaluates_every_annotation(self) -> None:
        counter = Counter()
        namespace = run(definition(50, future=True), counter)

        first = typing.get_type_hints(namespace["f"])
        assert counter.calls == 50
        typing.get_type_hints(namespace["f"])

        assert counter.calls == 100
        assert first == {f"p{index}": int for index in range(50)}


class TestFutureFlagsInDynamicCode:
    """`compile()` and `exec()` of a string inherit the caller's future flags;
    `dont_inherit=True` stops that and `compiler_flag` turns a feature on.
    This module imports `annotations`, so it is the caller being inherited."""

    SOURCE = "def f(x: Undefined):\n    pass\n"

    def test_compile_inherits_this_module_s_flag(self) -> None:
        assert compile(self.SOURCE, "<test>", "exec").co_flags & FLAG

    def test_exec_of_a_string_inherits_it(self) -> None:
        namespace: dict[str, Any] = {}

        exec(self.SOURCE, namespace)

        assert namespace["f"].__annotations__ == {"x": "Undefined"}

    def test_dont_inherit_stops_it(self) -> None:
        assert not compile_isolated(self.SOURCE).co_flags & FLAG

    def test_compiler_flag_turns_it_on(self) -> None:
        namespace: dict[str, Any] = {}

        exec(compile_isolated(self.SOURCE, FLAG), namespace)

        assert namespace["f"].__annotations__ == {"x": "Undefined"}


class TestTheFeatureTable:
    """`all_feature_names`, the nine feature attributes and `_Feature` members
    | O(1) | O(1): stored values, returned as they are."""

    def test_all_feature_names_lists_ten_features(self) -> None:
        names = __future__.all_feature_names

        assert len(names) == 10
        assert "barry_as_FLUFL" in names
        assert set(MANDATORY) | {"annotations", "barry_as_FLUFL"} == set(names)
        assert all(type(getattr(__future__, name)).__name__ == "_Feature" for name in names)

    def test_only_two_features_are_still_optional(self) -> None:
        optional = [
            name
            for name in __future__.all_feature_names
            if getattr(__future__, name).mandatory is None
            or getattr(__future__, name).mandatory > sys.version_info
        ]

        assert optional == ["barry_as_FLUFL", "annotations"]

    @pytest.mark.parametrize("name", __future__.all_feature_names)
    def test_the_getters_return_the_stored_objects(self, name: str) -> None:
        feature = getattr(__future__, name)

        assert feature.getOptionalRelease() is feature.optional
        assert feature.getMandatoryRelease() is feature.mandatory
        assert len(feature.optional) == 5

    def test_annotations_has_no_mandatory_release(self) -> None:
        mandatory = __future__.annotations.getMandatoryRelease()

        if sys.version_info >= (3, 11):
            assert mandatory is None
        else:
            assert mandatory == (3, 11, 0, "alpha", 0)


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
    """Each block runs in its own subprocess, so a block's future statement
    applies only to that block, and asserts its own result."""

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
        target = "assert Point.__annotations__ == {'x': 'expensive()'}"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert Point.__annotations__ == {'x': int}", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
