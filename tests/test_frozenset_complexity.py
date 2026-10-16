"""Tests for docs/builtins/frozenset.md and docs/builtins/frozenset_func.md.

The rows that differ from `set` are the ones that hand back an existing
object: `copy()` and `frozenset(fs)` return `fs` itself, so they are O(1).
Identity settles them without timing.

Measurement scope:

* `fs.copy()` and `frozenset(fs)` are asserted to return `fs` for an exact
  frozenset; for an instance of a subclass both are asserted to return a new,
  equal object, which is the O(n) copy. `set(fs)` is asserted to be a new set.
* A frozenset built from a set that had all but 10 of 200,000 elements
  discarded is asserted to be under 1/100 of that set's size, so the result
  is compact even though building it walks the old table; the walk itself is
  timed in tests/test_set_complexity.py.
* That `intersection()` and `difference()` take all of a non-set operand is
  asserted for frozensets in tests/test_set_complexity.py, beside the same
  test for sets; the cached hash is in tests/test_complexity_caveats.py.
* Every fenced Python block on both pages runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

DOCS = pathlib.Path(__file__).parent.parent / "docs" / "builtins"
PAGES = {"frozenset.md": 8, "frozenset_func.md": 19}


class SubFrozenset(frozenset[int]):
    pass


class TestReturnsItself:
    def test_copy_returns_the_same_object(self) -> None:
        fs = frozenset(range(1_000))
        assert fs.copy() is fs

    def test_the_constructor_returns_the_same_object(self) -> None:
        fs = frozenset(range(1_000))
        assert frozenset(fs) is fs

    def test_a_subclass_instance_is_copied(self) -> None:
        sub = SubFrozenset(range(1_000))
        for copied in (sub.copy(), frozenset(sub)):
            assert copied is not sub and copied == sub

    def test_set_of_it_is_a_new_set(self) -> None:
        fs = frozenset(range(10))
        assert set(fs) is not fs and set(fs) == fs


def test_building_from_a_sparse_set_is_compact() -> None:
    s = set(range(200_000))
    for i in range(10, 200_000):
        s.discard(i)
    frozen = frozenset(s)
    assert frozen == s
    assert sys.getsizeof(frozen) * 100 < sys.getsizeof(s)


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
        target = "assert 'unhashable' in str(error)"
        line, source = next((n, s) for n, s in _blocks("frozenset.md") if target in s)
        mutated = source.replace(target, "assert 'hashable' not in str(error)", 1)

        assert mutated != source, f"the mutation matched nothing in frozenset.md:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
