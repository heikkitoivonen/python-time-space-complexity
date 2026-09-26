"""Tests for docs/stdlib/contextvars.md.

The page prices a context as a persistent hash array mapped trie: a set copies
one root-to-leaf path, a copy shares the whole trie, and a lookup walks one
path. Path copying is settled by traced allocation, which rises each time the
context grows 32-fold - the trie's branching factor - yet stays under four times
its smallest value across a 1,024-fold range, which excludes both a constant and
a linear bound without a stopwatch. Copying is settled by a traced peak under
1 KB at tens of thousands of variables. Lookups and `len()` have no allocation to
observe, so they are timed over a 1,024-fold range, which excludes a linear scan
but cannot tell log n from a constant. Behaviour rows are settled by
observation.

Measurement scope:

* `ContextVar.set()` and `ContextVar.reset()` are measured in contexts of 32,
  1,024 and 32,768 variables, as the median traced peak over 15 of the
  context's own variables. Each 32-fold step raises the peak - by about 300
  bytes on 64-bit 3.10 and 3.14 - and the largest context's peak is under four
  times the smallest's, where a copy of the mapping would be 1,024 times.
* `copy_context()` and `Context.copy()` peak under 1 KB in a context of
  32,768 variables. The copy and the original are asserted to diverge in both
  directions after the copy, and a copy taken before a set keeps the value it
  replaced.
* `Context.get()`, `ctx[var]`, `var in ctx`, `len(ctx)` and `Context.run()`
  on a no-op are timed in contexts of 32 and 32,768 variables; each ratio is
  asserted under 4, against 1,024 for a scan. `ctx == other` on two contexts
  built separately with the same variables is timed at 1,024 and 32,768
  variables and asserted to grow more than 8x.
* `iter(ctx)` peaks under 1 KB at 32,768 variables. `keys()`, `values()` and
  `items()` are asserted to be one-shot iterators, and the iteration order of
  100 variables is asserted to differ from the order they were set in.
* `Context.run()` is observed to keep what the callable set, to leave the
  caller's context alone, and to raise `RuntimeError` when the context is
  already entered. `reset()` is observed to remove a key the set added, and
  to raise `RuntimeError` on a second use and `ValueError` from another
  context or for another variable.
* A context keeps every variable set in it: a function that creates and sets
  a new variable per call adds one key per call, and the key survives the
  function. `ContextVar` cannot be subclassed, so no user `__hash__` or
  `__eq__` runs in a lookup, and two variables with one name are two keys.
* `Token` as a context manager is asserted on 3.14 and its absence on earlier
  versions; `threading.Thread(context=...)` and `-X thread_inherit_context=1`
  are asserted on 3.14. A default thread is asserted to start empty when
  `sys.flags.thread_inherit_context` is unset.
* An asyncio task is observed to see the context as it was when the task was
  created, not a set the parent makes afterwards, and a task given `context=`
  to run in that context and set its variables there (3.11+).
* The inheriting thread's own set is asserted to leave the caller's value in
  place (3.14+).
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* O(log n) against O(1) for lookups, and O(n log n) against O(n) for equality.
  The trie is 32-way over a 32-bit hash, so its depth grows by one per 32-fold
  growth and never exceeds seven levels plus a collision node; no timing over
  a feasible range separates that from a constant. The bounds follow the path
  walk in Python/hamt.c (`hamt_find`, `_PyHamt_Eq`) of every supported
  release.
* `ContextVar.get()` serves a repeated read of one variable, in one thread,
  between context switches, from a per-variable cache (Python/context.c,
  `PyContextVar_Get`); free-threaded builds skip the cache. It moves only the
  constant, so the page leaves it out, and it cannot be observed from Python.
* That free-threaded builds default `thread_inherit_context` to 1 is read from
  Python/initconfig.c; no free-threaded interpreter is run here.
* The size of the stored values is not varied, and the variables in each
  measured context are set to small ints.
"""

from __future__ import annotations

import asyncio
import functools
import pathlib
import re
import statistics
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable
from contextvars import Context, ContextVar, Token, copy_context
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "contextvars.md"
EXPECTED_BLOCKS = 7

SIZES = (32, 1_024, 32_768)


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 2_000) -> float:
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


@functools.cache
def filled(size: int) -> tuple[Context, tuple[ContextVar[int], ...]]:
    """A context holding `size` variables, each set to its index."""
    variables = tuple(ContextVar(f"v{index}") for index in range(size))
    context = Context()

    def fill() -> None:
        for index, variable in enumerate(variables):
            variable.set(index)

    context.run(fill)
    return context, variables


def sample(variables: tuple[ContextVar[int], ...], count: int = 15) -> tuple[ContextVar[int], ...]:
    return variables[:: max(1, len(variables) // count)][:count]


class TestSetCopiesOnePath:
    """`ContextVar.set(value)` and `reset(token)` | O(log n) | O(log n).

    The traced peak rises at each 32-fold growth, which a constant bound would
    not do, and stays under four times the smallest peak over 1,024-fold growth,
    where a copied mapping would grow 1,024 times.
    """

    @staticmethod
    def set_peak(size: int) -> float:
        context, variables = filled(size)

        def measure() -> float:
            peaks = []
            for variable in sample(variables):
                peaks.append(peak_bytes(lambda v=variable: v.set(1)))
            return statistics.median(peaks)

        return context.copy().run(measure)

    @staticmethod
    def reset_peak(size: int) -> float:
        context, variables = filled(size)

        def measure() -> float:
            peaks = []
            for variable in sample(variables):
                token = variable.set(2)
                peaks.append(peak_bytes(lambda v=variable, t=token: v.reset(t)))
            return statistics.median(peaks)

        return context.copy().run(measure)

    @pytest.mark.parametrize("operation", ["set", "reset"])
    def test_the_peak_grows_by_a_step_per_32_fold_growth(self, operation: str) -> None:
        measure = self.set_peak if operation == "set" else self.reset_peak
        peaks = [measure(size) for size in SIZES]

        assert peaks[0] < peaks[1] < peaks[2], f"{operation}: no growth with depth: {peaks}"
        assert peaks[2] < peaks[0] * 4, f"{operation}: 1,024x the variables peaked at {peaks}"

    def test_the_replaced_mapping_is_left_intact(self) -> None:
        variable: ContextVar[str] = ContextVar("variable")
        context = Context()
        context.run(variable.set, "before")
        snapshot = context.copy()

        token = context.run(variable.set, "after")

        assert snapshot[variable] == "before"
        assert context[variable] == "after"
        assert token.old_value == "before"


class TestReadingFallsBack:
    """`ContextVar.get([default])`: the argument, then the variable's default,
    then `LookupError`."""

    def test_the_fallback_order(self) -> None:
        bare: ContextVar[str] = ContextVar("bare")
        defaulted: ContextVar[str] = ContextVar("defaulted", default="own")

        def read() -> None:
            with pytest.raises(LookupError):
                bare.get()
            assert bare.get("argument") == "argument"
            assert defaulted.get() == "own"
            assert defaulted.get("argument") == "argument"
            defaulted.set("set")
            assert defaulted.get("argument") == "set"

        Context().run(read)

    @pytest.mark.timing
    @pytest.mark.parametrize("lookup", ["get", "subscript", "contains"])
    def test_a_lookup_does_not_scan_the_context(self, lookup: str) -> None:
        durations = []
        for size in (SIZES[0], SIZES[-1]):
            context, variables = filled(size)
            variable = variables[size // 2]
            operation: Callable[[], Any] = {
                "get": lambda c=context, v=variable: c.get(v),
                "subscript": lambda c=context, v=variable: c[v],
                "contains": lambda c=context, v=variable: v in c,
            }[lookup]
            durations.append(best_ns(operation))
        ratio = durations[1] / durations[0]

        assert ratio < 4, f"{lookup}: 1,024x the variables took {durations} ns, x{ratio:.2f}"


class TestResetRules:
    """`ContextVar.reset(token)`: only in the token's context, only once, and
    only for the token's variable; resetting to unset removes the key."""

    def test_resetting_to_unset_removes_the_key(self) -> None:
        variable: ContextVar[int] = ContextVar("variable")
        context = Context()

        token = context.run(variable.set, 1)
        assert len(context) == 1
        context.run(variable.reset, token)

        assert len(context) == 0
        assert variable not in context

    def test_a_token_is_used_once(self) -> None:
        variable: ContextVar[int] = ContextVar("variable")
        context = Context()
        token = context.run(variable.set, 1)
        context.run(variable.reset, token)

        with pytest.raises(RuntimeError, match="already been used"):
            context.run(variable.reset, token)

    def test_a_token_belongs_to_its_context(self) -> None:
        variable: ContextVar[int] = ContextVar("variable")
        token = Context().run(variable.set, 1)

        with pytest.raises(ValueError, match="different Context"):
            Context().run(variable.reset, token)

    def test_a_token_belongs_to_its_variable(self) -> None:
        first: ContextVar[int] = ContextVar("first")
        second: ContextVar[int] = ContextVar("second")
        context = Context()
        token = context.run(first.set, 1)

        with pytest.raises(ValueError, match="different ContextVar"):
            context.run(second.reset, token)


class TestToken:
    """`Token.var`, `Token.old_value`, `Token.MISSING`, and `with var.set()`
    on 3.14+."""

    def test_the_attributes(self) -> None:
        variable: ContextVar[int] = ContextVar("variable")
        context = Context()

        first = context.run(variable.set, 1)
        second = context.run(variable.set, 2)

        assert first.var is variable and second.var is variable
        assert first.old_value is Token.MISSING
        assert second.old_value == 1

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="Token.__enter__ is 3.14+")
    def test_a_token_resets_on_exit(self) -> None:
        variable: ContextVar[str] = ContextVar("variable", default="outer")

        def use() -> None:
            with variable.set("inner"):  # type: ignore[attr-defined]
                assert variable.get() == "inner"
            assert variable.get() == "outer"
            with pytest.raises(KeyError), variable.set("raised"):  # type: ignore[attr-defined]
                raise KeyError
            assert variable.get() == "outer"

        Context().run(use)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Token.__enter__ is 3.14+")
    def test_a_token_is_not_a_context_manager_before_314(self) -> None:
        assert not hasattr(Token, "__enter__")


class TestCopyIsConstant:
    """`copy_context()` and `Context.copy()` | O(1) | O(1): the copy shares
    the mapping, and the two diverge from there."""

    def test_copying_a_large_context_allocates_almost_nothing(self) -> None:
        context, _ = filled(SIZES[-1])
        context.copy()  # warm

        current = context.run(peak_bytes, copy_context)
        method = peak_bytes(context.copy)

        assert current < 1_000, f"copy_context() over {SIZES[-1]} variables peaked at {current}"
        assert method < 1_000, f"Context.copy() over {SIZES[-1]} variables peaked at {method}"

    def test_the_copies_diverge_in_both_directions(self) -> None:
        left: ContextVar[str] = ContextVar("left")
        right: ContextVar[str] = ContextVar("right")
        original = Context()
        original.run(left.set, "shared")
        copy = original.run(copy_context)

        copy.run(left.set, "copy")
        original.run(right.set, "original")

        assert original[left] == "shared" and right in original
        assert copy[left] == "copy" and right not in copy
        assert len(Context()) == 0


class TestRunDoesNotCopy:
    """`Context.run(callable, ...)` | O(1) + callable: switches, keeps what the
    callable set, and refuses a context that is already entered."""

    def test_sets_stay_in_the_context(self) -> None:
        counter: ContextVar[int] = ContextVar("counter", default=0)
        context = Context()

        def bump() -> int:
            counter.set(counter.get() + 1)
            return counter.get()

        assert context.run(bump) == 1
        assert context.run(bump) == 2
        assert counter.get() == 0

    def test_arguments_pass_through(self) -> None:
        def echo(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
            return args, kwargs

        assert Context().run(echo, 1, key=2) == ((1,), {"key": 2})

    def test_an_entered_context_cannot_be_entered_again(self) -> None:
        context = Context()

        with pytest.raises(RuntimeError, match="already entered"):
            context.run(functools.partial(context.run, int))

    @pytest.mark.timing
    def test_switching_does_not_depend_on_size(self) -> None:
        durations = []
        for size in (SIZES[0], SIZES[-1]):
            context, _ = filled(size)
            durations.append(best_ns(functools.partial(context.run, int)))
        ratio = durations[1] / durations[0]

        assert ratio < 4, f"1,024x the variables took {durations} ns, x{ratio:.2f}"


class TestLenIsStored:
    """`len(ctx)` | O(1) | O(1)."""

    def test_len_counts_variables(self) -> None:
        context, variables = filled(SIZES[0])

        assert len(context) == len(variables)

    @pytest.mark.timing
    def test_len_does_not_depend_on_size(self) -> None:
        durations = []
        for size in (SIZES[0], SIZES[-1]):
            context, _ = filled(size)
            durations.append(best_ns(functools.partial(len, context)))
        ratio = durations[1] / durations[0]

        assert ratio < 4, f"1,024x the variables took {durations} ns, x{ratio:.2f}"


class TestIterationIsLazy:
    """`iter(ctx)`, `keys()`, `values()`, `items()` | O(1) to create, O(n) to
    exhaust: one-shot iterators in hash order."""

    def test_creating_an_iterator_allocates_almost_nothing(self) -> None:
        context, _ = filled(SIZES[-1])

        for make in (context.__iter__, context.keys, context.values, context.items):
            peak = peak_bytes(make)
            assert peak < 1_000, f"{make.__name__} over {SIZES[-1]} variables peaked at {peak}"

    def test_the_iterators_are_one_shot_and_complete(self) -> None:
        context, variables = filled(SIZES[0])

        for make in (context.__iter__, context.keys, context.values, context.items):
            iterator = make()
            assert iter(iterator) is iterator
            assert len(list(iterator)) == len(variables)
            assert list(iterator) == []
        assert set(context) == set(variables)
        assert sorted(context.values()) == list(range(len(variables)))
        assert dict(context.items()) == {v: i for i, v in enumerate(variables)}

    def test_the_order_is_not_the_order_of_setting(self) -> None:
        variables = [ContextVar(f"v{index}") for index in range(100)]
        context = Context()
        for variable in variables:
            context.run(variable.set, 0)

        assert set(context) == set(variables)
        assert list(context) != variables


class TestEquality:
    """`ctx == other` | O(n log n) | O(1): compares every entry."""

    def test_equal_contents_compare_equal(self) -> None:
        variable: ContextVar[int] = ContextVar("variable")
        left, right = Context(), Context()
        left.run(variable.set, 1)
        right.run(variable.set, 1)

        assert left == right
        right.run(variable.set, 2)
        assert left != right

    @pytest.mark.timing
    def test_equality_grows_with_size(self) -> None:
        durations = []
        for size in (SIZES[1], SIZES[2]):
            context, variables = filled(size)
            twin = Context()
            twin.run(lambda vs=variables: [v.set(i) for i, v in enumerate(vs)])
            assert context == twin
            durations.append(best_ns(lambda c=context, t=twin: c == t, inner=3))
        ratio = durations[1] / durations[0]

        assert ratio > 8, f"32x the variables took {durations} ns, x{ratio:.2f}"


class TestVariablesAreKeys:
    """`ContextVar(name, *, default)`: each variable is its own key, and a
    context keeps every variable set in it."""

    def test_two_variables_with_one_name_are_two_keys(self) -> None:
        first: ContextVar[int] = ContextVar("same")
        second: ContextVar[int] = ContextVar("same")
        context = Context()
        context.run(first.set, 1)

        assert first.name == second.name == "same"
        assert first in context and second not in context

    def test_a_context_keeps_variables_created_per_call(self) -> None:
        context = Context()

        def handler() -> None:
            ContextVar("temporary").set(1)

        for _ in range(100):
            context.run(handler)

        assert len(context) == 100
        assert {variable.name for variable in context} == {"temporary"}

    def test_contextvar_cannot_be_subclassed(self) -> None:
        with pytest.raises(TypeError):
            type("Custom", (ContextVar,), {})

    def test_keys_must_be_variables(self) -> None:
        with pytest.raises(TypeError, match="ContextVar"):
            Context()["name"]  # type: ignore[index]


class TestThreadsAndTasks:
    """A thread starts in an empty context unless `thread_inherit_context` is
    set; a task runs in a copy taken when it is created."""

    def test_a_default_thread_starts_empty(self) -> None:
        if getattr(sys.flags, "thread_inherit_context", 0):
            pytest.skip("threads inherit a copy of the caller's context on this build")
        variable: ContextVar[str] = ContextVar("variable", default="unset")
        seen: list[str] = []

        def run() -> None:
            variable.set("caller")
            thread = threading.Thread(target=lambda: seen.append(variable.get()))
            thread.start()
            thread.join()

        Context().run(run)

        assert seen == ["unset"]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="Thread(context=) is 3.14+")
    def test_thread_takes_a_context(self) -> None:
        variable: ContextVar[str] = ContextVar("variable", default="unset")
        given = Context()
        given.run(variable.set, "given")
        seen: list[str] = []

        options: dict[str, Any] = {"context": given}  # the keyword is 3.14+

        thread = threading.Thread(target=lambda: seen.append(variable.get()), **options)
        thread.start()
        thread.join()

        assert seen == ["given"]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="thread_inherit_context is 3.14+")
    def test_the_inherit_flag_copies_the_caller_s_context(self) -> None:
        script = textwrap.dedent(
            """
            import sys, threading
            from contextvars import ContextVar
            variable = ContextVar('variable', default='unset')
            variable.set('caller')
            seen = []
            def target():
                seen.append(variable.get())
                variable.set('thread')
                seen.append(variable.get())
            thread = threading.Thread(target=target)
            thread.start()
            thread.join()
            assert sys.flags.thread_inherit_context == 1
            assert seen == ['caller', 'thread'], seen
            assert variable.get() == 'caller'
            """
        )
        result = subprocess.run(
            [sys.executable, "-X", "thread_inherit_context=1", "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, result.stderr

    def test_a_task_sees_the_context_as_it_was_when_created(self) -> None:
        variable: ContextVar[str] = ContextVar("variable", default="unset")

        async def main() -> str:
            variable.set("at creation")
            reader = asyncio.create_task(_read(variable))
            variable.set("after creation")
            return await reader

        assert asyncio.run(main()) == "at creation"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="create_task(context=) is 3.11+")
    def test_a_task_given_a_context_runs_in_it(self) -> None:
        variable: ContextVar[str] = ContextVar("variable", default="unset")
        given = Context()
        given.run(variable.set, "given")

        async def write() -> str:
            seen = variable.get()
            variable.set("written")
            return seen

        async def main() -> str:
            variable.set("caller")
            options: dict[str, Any] = {"context": given}  # the keyword is 3.11+
            return await asyncio.create_task(write(), **options)

        assert asyncio.run(main()) == "given"
        assert given[variable] == "written"


async def _read(variable: ContextVar[str]) -> str:
    return variable.get()


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
    """Each block runs in its own subprocess, so a variable set in one cannot
    leak into another, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert ctx.run(bump) == 2" in s)
        mutated = source.replace("assert ctx.run(bump) == 2", "assert ctx.run(bump) == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
