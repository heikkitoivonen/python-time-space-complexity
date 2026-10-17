"""Tests for docs/builtins/exec.md.

Every block on the page runs in its own interpreter and working directory. The
script-loading block opens `user_script.py`, a file the reader supplies, so
the test writes one into that block's working directory first; every other
block runs as the page prints it. The runner is checked by dropping the inner
`sum(` from the execution-time block, which leaves its source a SyntaxError.

Not settled here: the page's table and its explanatory comments - parse cost in
code length, scope size as a cost term, and the relative speed of `exec()`,
`compile()` and direct code. `tests/test_builtin_claims.py` covers the claim
that `exec()` of a string reparses it on every call.
"""

from __future__ import annotations

import pathlib

from tests.page_examples import DOCS, python_blocks, run_block

PAGE = DOCS / "builtins" / "exec.md"
EXPECTED_BLOCKS = 18
SCRIPT = "user_script.py"


class TestDocumentedExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_one_block_reads_a_script_the_reader_supplies(self) -> None:
        assert sum(SCRIPT in source for _, source in python_blocks(PAGE)) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in python_blocks(PAGE):
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            if SCRIPT in source:
                (workdir / SCRIPT).write_text("loaded = True\n", encoding="utf-8")
            result = run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert not failures, "\n\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "sum(sum(range(1000))" in s)
        broken = source.replace("sum(sum(range(1000))", "sum(range(1000))", 1)

        assert broken != source
        assert run_block(broken, tmp_path).returncode != 0
