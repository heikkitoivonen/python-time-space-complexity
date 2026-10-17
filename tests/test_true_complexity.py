"""Tests for docs/builtins/true.md.

Every block on the page runs, unchanged, in its own interpreter and working
directory. The short-circuit block binds `expensive_function` to a function
that raises, so its "Function not called!" comments are checked by the block
itself; the runner is checked by making the `and` operand true, which calls it.

Not settled here: the page's table and the O(1) comments beside each
operation.
"""

from __future__ import annotations

import pathlib

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PAGE = DOCS / "builtins" / "true.md"
EXPECTED_BLOCKS = 24


class TestDocumentedExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PAGE, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_call_that_should_short_circuit(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "False and expensive_function()" in s)
        mutated = source.replace("False and expensive_function()", "True and expensive_function()")

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
