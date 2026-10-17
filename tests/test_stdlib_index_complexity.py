"""Tests for docs/stdlib/index.md.

Every block on the overview runs, unchanged, in its own interpreter and working
directory. The runner is checked by replacing the `defaultdict(list)` in the
collections block with a plain dict, whose missing key then raises KeyError.

Not settled here: the O(...) comments beside each call; each module's own page
and test file cover its operations.
"""

from __future__ import annotations

import pathlib

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PAGE = DOCS / "stdlib" / "index.md"
EXPECTED_BLOCKS = 3


class TestDocumentedExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PAGE, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_missing_default(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "defaultdict(list)" in s)
        mutated = source.replace("d = defaultdict(list)", "d = {}", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
