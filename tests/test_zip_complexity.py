"""Tests for docs/builtins/zip.md.

Every block on the page runs in its own interpreter and working directory. Two
blocks contrast lazy iteration with `list(zip(...))` over ranges of 10**9
items, which as printed would build a billion pairs; the test runs them with
10**4 in place of 10**9, asserting the substitution changed each one, and
every other block as the page prints it. The runner is checked by unbinding
`condition` in the iterator-efficiency block.

Not settled here: the page's table and the O(...) comments beside each
operation, and the memory the 10**9 blocks would use as printed.
"""

from __future__ import annotations

import pathlib

from tests.page_examples import DOCS, python_blocks, run_block

PAGE = DOCS / "builtins" / "zip.md"
EXPECTED_BLOCKS = 18
EXPECTED_SCALED_BLOCKS = 2


def _scaled(source: str) -> str:
    return source.replace("10**9", "10**4")


class TestDocumentedExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_the_scaled_blocks_are_the_billion_item_ones(self) -> None:
        scaled = [line for line, source in python_blocks(PAGE) if _scaled(source) != source]

        assert len(scaled) == EXPECTED_SCALED_BLOCKS, scaled

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in python_blocks(PAGE):
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_block(_scaled(source), workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert not failures, "\n\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "def condition(a, b):" in s)
        broken = source.replace("def condition(a, b):", "def unused(a, b):", 1)

        assert broken != source
        assert run_block(broken, tmp_path).returncode != 0
