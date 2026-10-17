"""Tests for docs/implementations/cpython.md, docs/implementations/pypy.md,
docs/implementations/jython.md and docs/implementations/ironpython.md.

Each block runs in its own CPython interpreter and working directory, apart
from the blocks that import a foreign runtime's namespace - `java` and `javax`
on Jython, `clr` and `System` on IronPython. Those exist only on that runtime,
so they are counted, so the gap stays visible, and compiled, so they are at
least valid Python. The Jython warm-up block calls `compute(1000000)` 1,001
times, a billion loop iterations as printed; the test calls `compute(1000)`
instead, asserting the substitution changed the block. The runner is checked
by unbinding `compute` in that block.

Not settled here: everything the pages say about PyPy, Jython or IronPython
themselves - JIT warm-up, speedups, GIL behaviour, interop costs. Only CPython
is installed, so the blocks show those runtimes' APIs without measuring them.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from tests.page_examples import DOCS, python_blocks, run_block

PAGES = {"cpython.md": 10, "pypy.md": 10, "jython.md": 11, "ironpython.md": 12}
FOREIGN_BLOCKS = {"cpython.md": 0, "pypy.md": 0, "jython.md": 3, "ironpython.md": 3}
FOREIGN = re.compile(r"^\s*(?:import|from)\s+(?:java|javax|clr|System)\b", re.MULTILINE)


def _page(name: str) -> pathlib.Path:
    return DOCS / "implementations" / name


def _scaled(source: str) -> str:
    return source.replace("compute(1000000)", "compute(1000)")


@pytest.mark.parametrize("name", list(PAGES))
class TestDocumentedExamples:
    def test_the_page_has_the_expected_blocks(self, name: str) -> None:
        assert len(python_blocks(_page(name))) == PAGES[name]

    def test_the_foreign_blocks_are_the_ones_importing_a_runtime(self, name: str) -> None:
        foreign = [line for line, source in python_blocks(_page(name)) if FOREIGN.search(source)]

        assert len(foreign) == FOREIGN_BLOCKS[name], foreign

    def test_every_foreign_block_compiles(self, name: str) -> None:
        for line, source in python_blocks(_page(name)):
            if FOREIGN.search(source):
                compile(source, f"{name}:{line}", "exec")

    def test_every_other_block_runs(self, name: str, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in python_blocks(_page(name)):
            if FOREIGN.search(source):
                continue
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_block(_scaled(source), workdir)
            if result.returncode != 0:
                failures.append(f"{name}:{line}\n{result.stderr.strip()}")

        assert not failures, "\n\n".join(failures)


class TestTheRunner:
    def test_only_the_jython_warm_up_block_is_scaled(self) -> None:
        scaled = [
            (name, line)
            for name in PAGES
            for line, source in python_blocks(_page(name))
            if _scaled(source) != source
        ]

        assert [name for name, _ in scaled] == ["jython.md"]

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(_page("jython.md")) if "compute(1000000)" in s)
        broken = _scaled(source).replace("def compute(n):", "def unused(n):", 1)

        assert broken != _scaled(source)
        assert run_block(broken, tmp_path).returncode != 0
