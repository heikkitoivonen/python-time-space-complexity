"""Tests for docs/builtins/locals_func.md.

locals() is builtin_locals in Python/bltinmodule.c. Up to 3.12 it is
PyEval_GetLocals: the module or class namespace itself, or for a function one
FastToLocals pass over the frame's slots into the frame's one dict, which
every call refreshes and returns again. From the v3.13.0 tag (PEP 667) it is
_PyEval_GetFrameLocals: still the namespace itself at module and class scope,
but in a function a fresh dict filled by PyDict_Update from a
FrameLocalsProxy, whose keys() is one pass over the slots and whose
__getitem__ (framelocalsproxy_getkeyindex in Objects/frameobject.c) scans
co_localsplusnames from the start for each key. The page's m counts those
slots: locals, cells and free variables.

Measurement scope:

* At module scope locals() is globals(); in a class body a key written into
  it becomes a class attribute; under exec() and eval() with a separate locals
  mapping it is that mapping, and a write into it lands there.
* In a function the snapshot holds every bound local and every free variable
  the function reads, and no local that is still unbound; a key written into
  it is not seen by the function. Two calls in one frame return one dict up to
  3.12, whose first result shows the later value, and two dicts from 3.13.
* Elapsed time settles the function-scope row: a function binding 1,000 locals
  against one binding 16,000, with the assignments inside the timed call. x16
  in m predicts x16 if linear and x256 if quadratic; the test asserts over
  x60 from 3.13 and under x60 before. On aarch64 a x4 step cost x14.0 and
  x16.7 on 3.15.0, x12.9 and x15.8 on 3.13.16, and x5.3 and x4.1 on 3.11.17,
  where the assignments are a fixed share of the call.
* The snapshot's O(m) space is a traced allocation peak over one call, after
  a warm-up call, at 1,000 and 16,000 locals: x16.0 on 3.11.17 and 3.12.15,
  x15.8 on 3.13.16 and 3.15.0, against x16 if linear and x256 if quadratic;
  the test asserts between x8 and x32.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Unbound slots as a share of the frame, and where in the frame the bound
  names sit, are not varied: from 3.13 each key's scan stops at its own slot,
  so an all-bound frame is the framing with the widest gap, and the page's
  O(m²) is the bound for a frame of m slots rather than a measured cost for
  every layout.
* The O(1) average lookup in the result is dict's own bound, including its
  hash-collision worst case, and is not measured here.
* locals() inside a comprehension, which 3.12 inlined into the enclosing
  function (PEP 709), is not separately tested; it is the enclosing
  function's frame.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "locals_func.md"
EXPECTED_BLOCKS = 5


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
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


def function_with_locals(count: int) -> Callable[[], dict[str, Any]]:
    """A function binding `count` locals and returning locals()."""
    namespace: dict[str, Any] = {}
    body = "".join(f"    v{i} = {i}\n" for i in range(count))
    exec(f"def f():\n{body}    return locals()\n", namespace)
    return namespace["f"]


class TestModuleAndClassScopeIsTheNamespace:
    """`locals()` at module or class scope: O(1), the namespace itself, or the
    locals mapping passed to `exec()`; writes reach it."""

    def test_module_scope_is_globals(self) -> None:
        namespace: dict[str, Any] = {}
        exec("same = locals() is globals()", namespace)
        assert namespace["same"] is True

    def test_a_write_in_a_class_body_becomes_an_attribute(self) -> None:
        class Sample:
            locals()["added"] = 1

        assert Sample.added == 1  # type: ignore[attr-defined]

    def test_under_exec_it_is_the_mapping_passed_in(self) -> None:
        local_namespace: dict[str, Any] = {}
        exec("captured = locals()\nlocals()['added'] = 1", {}, local_namespace)
        assert local_namespace["captured"] is local_namespace
        assert local_namespace["added"] == 1

    def test_under_eval_it_is_the_mapping_passed_in(self) -> None:
        local_namespace: dict[str, Any] = {}
        assert eval("locals()", {}, local_namespace) is local_namespace


class TestFunctionScopeIsASnapshot:
    """`locals()` in a function: a snapshot of the bound names, free variables
    included; writes do not reach the function."""

    def test_it_holds_bound_and_free_names_and_no_unbound_one(self) -> None:
        def outer() -> dict[str, Any]:
            free = "outer"

            def inner() -> dict[str, Any]:
                bound = "inner"  # noqa: F841 - read back through the snapshot
                if free == "":
                    never = 1  # noqa: F841 - unbound when the snapshot is taken
                return locals()

            return inner()

        assert outer() == {"bound": "inner", "free": "outer"}

    def test_writes_do_not_reach_the_function(self) -> None:
        def sample() -> tuple[int, int]:
            value = 1
            snapshot = locals()
            snapshot["value"] = 2
            return value, snapshot["value"]

        assert sample() == (1, 2)

    def test_two_calls_share_one_dict_only_before_3_13(self) -> None:
        def sample() -> tuple[bool, int, int]:
            value = 1
            first = locals()
            value = 2  # noqa: F841 - read back through the snapshots, not the name
            second = locals()
            return first is second, first["value"], second["value"]

        shared, seen_through_first, seen_through_second = sample()
        assert seen_through_second == 2
        if sys.version_info >= (3, 13):
            assert not shared and seen_through_first == 1
        else:
            assert shared and seen_through_first == 2

    @pytest.mark.timing
    def test_the_snapshot_is_quadratic_from_3_13_and_linear_before(self) -> None:
        few = function_with_locals(1_000)
        many = function_with_locals(16_000)
        assert len(few()) == 1_000 and len(many()) == 16_000

        ratio = best_ns(many) / best_ns(few)

        if sys.version_info >= (3, 13):
            assert ratio > 60, f"x16 locals should cost near x256 from 3.13, got x{ratio:.1f}"
        else:
            assert ratio < 60, f"x16 locals should cost near x16 before 3.13, got x{ratio:.1f}"

    def test_the_snapshot_allocates_in_proportion_to_m(self) -> None:
        few = function_with_locals(1_000)
        many = function_with_locals(16_000)
        assert len(few()) == 1_000 and len(many()) == 16_000

        peaks = [peak_bytes(few), peak_bytes(many)]

        assert 8 < peaks[1] / peaks[0] < 32, f"x16 locals should allocate near x16, got {peaks}"


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
        target = "assert modify_attempt() == (10, 20)"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert modify_attempt() == (20, 20)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
