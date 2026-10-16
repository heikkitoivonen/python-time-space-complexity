"""Tests for the code examples in docs/versions/py314.md and docs/versions/index.md.

Each guide demonstrates the features of the release it describes, so its blocks
run only from that release: py314.md from 3.14 (`heapq.heapify_max`,
`float.from_number`, deferred annotations) and index.md from 3.15, whose first
block shows 3.15 syntax. Every block runs in its own interpreter, and the runner
is checked by undoing one fix per page. The guides' performance percentages are
not tested here; docs/versions/py315.md has its own claim tests.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PY314 = DOCS / "versions" / "py314.md"
INDEX = DOCS / "versions" / "index.md"


@pytest.mark.skipif(sys.version_info < (3, 14), reason="the 3.14 guide uses 3.14 APIs")
class TestPy314Examples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PY314)) == 9

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PY314, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_a_bare_from_number_on_a_string_would_raise(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PY314) if "float.from_number(42)" in s)
        guarded = 'try:\n    float.from_number("3.14")\nexcept TypeError:\n    pass'
        mutated = source.replace(guarded, 'float.from_number("3.14")', 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0


@pytest.mark.skipif(sys.version_info < (3, 15), reason="the overview opens with 3.15 syntax")
class TestIndexExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(INDEX)) == 6

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(INDEX, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_an_undefined_name(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(INDEX) if "match value:" in s)
        mutated = source.replace("value = 2\n", "", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
