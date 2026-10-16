"""Tests for docs/builtins/dict.md and docs/builtins/dict_func.md.

These cover the rows and paragraphs that pin the dict page to the official
CPython time-complexity table: iteration, `|` and `|=`, `update()` iterating
its argument, and the hash table that deletion does not shrink. The lookup
rows are timed in tests/test_builtin_complexity.py.

Measurement scope:

* Deletion is observed through `sys.getsizeof()`: a dict of 200,000 int keys
  keeps its size after all but 10 are removed with `del` or with `pop()`.
* The walking operations are timed on that sparse dict against a fresh dict
  holding the same 10 keys: iteration, `items()`, `copy()`, `dict(d)`,
  `other.update(d)`, `d | {}` and `d == twin` must each cost more than 50x
  (locally they cost thousands of times more). `len()` and a lookup are held
  under 5x, so the gap is the table walk and not the dict being larger in
  memory.
* `copy()` is asserted to give a compact dict (under 1/100 of the sparse
  one's size) with the same keys in the same order. Inserting fresh keys is
  asserted to rebuild the sparse dict at its current size before 200,000
  insertions, each deleted again so that the dict keeps 10 items. The rebuild
  is sized for the items present, so it shrinks the table only when the
  insertions have not refilled it.
* `d | other` is asserted to return a new dict and leave `d` unchanged,
  `d |= other` to keep the object, and `update()` to take every item of a
  counting iterator of pairs.
* Every fenced Python block on both pages runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(n) worst case under full hash collisions is read from
  Objects/dictobject.c's probing loop; the collision test for the shared
  table code is in tests/test_frozendict_complexity.py on 3.15.
* How many insertions a sparse dict takes before it resizes depends on the
  free slots left in its table; only that it happens is asserted.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

DOCS = pathlib.Path(__file__).parent.parent / "docs" / "builtins"
PAGES = {"dict.md": 4, "dict_func.md": 22}

PEAK = 200_000
KEPT = 10


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 3) -> float:
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


def sparse_dict(method: str = "del") -> dict[int, int]:
    """A dict that held PEAK keys and now holds KEPT."""
    d = {i: i for i in range(PEAK)}
    for i in range(KEPT, PEAK):
        if method == "del":
            del d[i]
        else:
            d.pop(i)
    return d


class TestDeletingDoesNotShrinkTheTable:
    @pytest.mark.parametrize("method", ["del", "pop"])
    def test_the_table_keeps_its_size(self, method: str) -> None:
        full = sys.getsizeof({i: i for i in range(PEAK)})
        d = sparse_dict(method)
        assert len(d) == KEPT
        assert sys.getsizeof(d) == full

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "name", ["iterate", "items", "copy", "dict()", "other.update", "or", "eq"]
    )
    def test_walking_costs_the_former_size(self, name: str) -> None:
        operations: dict[str, Callable[[dict[int, int]], Any]] = {
            "iterate": list,
            "items": lambda d: list(d.items()),
            "copy": lambda d: d.copy(),
            "dict()": dict,
            "other.update": lambda d: {}.update(d),
            "or": lambda d: d | {},
            "eq": lambda d: d == {i: i for i in range(KEPT)},
        }
        op = operations[name]
        sparse, fresh = sparse_dict(), {i: i for i in range(KEPT)}
        sparse_ns = best_ns(lambda: op(sparse))
        fresh_ns = best_ns(lambda: op(fresh))
        assert sparse_ns > fresh_ns * 50, f"{name}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["len", "lookup"])
    def test_len_and_lookups_are_unaffected(self, name: str) -> None:
        operations: dict[str, Callable[[dict[int, int]], Any]] = {
            "len": len,
            "lookup": lambda d: d[KEPT - 1],
        }
        op = operations[name]
        sparse, fresh = sparse_dict(), {i: i for i in range(KEPT)}
        sparse_ns = best_ns(lambda: op(sparse), inner=10_000)
        fresh_ns = best_ns(lambda: op(fresh), inner=10_000)
        assert sparse_ns < fresh_ns * 5, f"{name}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    def test_copy_is_compact(self) -> None:
        d = sparse_dict()
        copied = d.copy()
        assert sys.getsizeof(copied) * 100 < sys.getsizeof(d)
        assert list(copied) == list(d)

    def test_insertions_eventually_resize(self) -> None:
        d = sparse_dict()
        full = sys.getsizeof(d)
        for key in range(PEAK, 2 * PEAK):
            d[key] = key
            del d[key]
            if sys.getsizeof(d) != full:
                break
        assert len(d) == KEPT
        assert sys.getsizeof(d) * 100 < full, "an insertion must eventually rebuild the table"


class CountingPairs:
    """An iterator of (key, value) pairs that counts how many were taken."""

    def __init__(self, count: int) -> None:
        self._pairs = iter([(i, i) for i in range(count)])
        self.taken = 0

    def __iter__(self) -> Iterator[tuple[int, int]]:
        return self

    def __next__(self) -> tuple[int, int]:
        pair = next(self._pairs)
        self.taken += 1
        return pair


class TestMerging:
    def test_or_builds_a_new_dict(self) -> None:
        d = {"a": 1}
        merged = d | {"b": 2}
        assert merged == {"a": 1, "b": 2} and merged is not d
        assert d == {"a": 1}

    def test_ior_updates_in_place(self) -> None:
        d = {"a": 1}
        same = d
        d |= {"b": 2}
        assert d is same and d == {"a": 1, "b": 2}

    def test_update_takes_every_item_of_an_iterable(self) -> None:
        pairs = CountingPairs(1_000)
        d: dict[int, int] = {}
        d.update(pairs)
        assert pairs.taken == 1_000 and len(d) == 1_000

    def test_iteration_follows_insertion_order(self) -> None:
        d = {"c": 1, "a": 2, "b": 3}
        assert list(d) == ["c", "a", "b"]


def _blocks(page: str) -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = (DOCS / page).read_text(encoding="utf-8").splitlines()
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
    @pytest.mark.parametrize(("page", "expected"), PAGES.items())
    def test_the_page_has_the_expected_blocks(self, page: str, expected: int) -> None:
        assert len(_blocks(page)) == expected

    @pytest.mark.parametrize("page", PAGES)
    def test_every_block_runs(self, page: str, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks(page):
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{page}:{line}\n{result.stderr.strip()}")
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = "assert sys.getsizeof(d) == full"
        line, source = next((n, s) for n, s in _blocks("dict.md") if target in s)
        mutated = source.replace(target, "assert sys.getsizeof(d) < full", 1)

        assert mutated != source, f"the mutation matched nothing in dict.md:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
