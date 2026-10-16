"""Tests for the code examples in docs/builtins/len.md.

The page's complexity claims are kind B rows that tests/test_builtin_complexity.py
and the range and str test files already cover. This file runs every fenced
Python block on the page in its own interpreter, so an example that uses a name
it never defines fails here, and checks the runner by deleting one setup line.
"""

from __future__ import annotations

import pathlib

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PAGE = DOCS / "builtins" / "len.md"


class TestDocumentedExamples:
    """Each block runs in its own interpreter and defines every name it uses."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == 10

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PAGE, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_an_undefined_name(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "len(list1) > len(list2)" in s)
        mutated = source.replace("list1, list2 = [1, 2, 3], [4, 5]\n", "", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
