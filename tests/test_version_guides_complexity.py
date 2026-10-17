"""Tests for the code examples in docs/versions/py310.md, docs/versions/py311.md,
docs/versions/py312.md, docs/versions/py313.md, docs/versions/py314.md and
docs/versions/index.md.

Each guide demonstrates the features of the release it describes, so a guide
whose blocks use that release's syntax or APIs runs only from it: py312.md from
3.12 (PEP 695 type parameters), py314.md from 3.14 (`heapq.heapify_max`,
`float.from_number`, deferred annotations) and index.md from 3.15, whose first
block shows 3.15 syntax. The py310.md, py311.md and py313.md blocks run on
every supported version. Where a comment states what a release changed in an
error message, a separate test runs that block on every version and asserts
the message from that release on and its absence before it. The py311.md TOML
block opens `config.toml`, a file the reader supplies, so the test writes one
into that block's working directory. Every block runs in its own interpreter,
and each page's runner is
checked by one mutation that makes a block fail; the mutated block goes
through `run_block()`, the call `failing_blocks()` makes for each block, not
through a mutated copy of the page.

Not settled here: the guides' performance percentages and speedups, and the
memory figures in py311.md. docs/versions/py315.md has its own claim tests.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PY310 = DOCS / "versions" / "py310.md"
PY311 = DOCS / "versions" / "py311.md"
PY312 = DOCS / "versions" / "py312.md"
PY313 = DOCS / "versions" / "py313.md"
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


def _failures(page: pathlib.Path, tmp_path: pathlib.Path, files: dict[str, str]) -> list[str]:
    """Run every block, first writing each named file a block mentions into its directory."""
    failures: list[str] = []
    for line, source in python_blocks(page):
        workdir = tmp_path / f"block{line}"
        workdir.mkdir()
        for name, content in files.items():
            if name in source:
                (workdir / name).write_text(content, encoding="utf-8")
        result = run_block(source, workdir)
        if result.returncode != 0:
            failures.append(f"{page.relative_to(DOCS)}:{line}\n{result.stderr.strip()}")
    return failures


def _block(page: pathlib.Path, marker: str) -> str:
    return next(source for _, source in python_blocks(page) if marker in source)


class TestPy310Examples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PY310)) == 9

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PY310, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_an_unbound_subject(self, tmp_path: pathlib.Path) -> None:
        source = _block(PY310, "case Point(x=0, y=0):")
        mutated = source.replace("value = [3, 4]\n", "", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0


class TestPy311Examples:
    CONFIG = {"config.toml": 'title = "example"\n'}

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PY311)) == 15

    def test_one_block_reads_a_config_file_the_reader_supplies(self) -> None:
        assert sum("config.toml" in source for _, source in python_blocks(PY311)) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = _failures(PY311, tmp_path, self.CONFIG)

        assert not failures, "\n\n".join(failures)

    def test_the_index_error_message_is_the_one_the_comment_gives(
        self, tmp_path: pathlib.Path
    ) -> None:
        result = run_block(_block(PY311, "x[999]"), tmp_path)

        assert result.stdout == "list index out of range\n"

    def test_left_uncaught_the_traceback_marks_the_subscript(self, tmp_path: pathlib.Path) -> None:
        source = _block(PY311, "x[999]")
        uncaught = re.sub(
            r"try:\n    x\[999\]\nexcept IndexError as error:\n    print\(error\).*\n",
            "x[999]\n",
            source,
        )
        assert uncaught != source

        result = run_block(uncaught, tmp_path)

        assert result.returncode != 0
        assert "    x[999]\n    ~^^^^^\n" in result.stderr, result.stderr

    def test_the_runner_notices_an_unbound_index(self, tmp_path: pathlib.Path) -> None:
        source = _block(PY311, "lst[i]")
        mutated = source.replace("i = 0\n", "", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0


class TestPy312Examples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PY312)) == 9

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the 3.12 guide uses 3.12 syntax")
    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PY312, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_missing_import_hint_arrives_in_3_12(self, tmp_path: pathlib.Path) -> None:
        result = run_block(_block(PY312, "json.loads"), tmp_path)
        hinted = "Did you forget to import 'json'" in result.stderr

        assert "NameError: name 'json' is not defined" in result.stderr
        assert hinted == (sys.version_info >= (3, 12)), result.stderr

    def test_the_runner_notices_an_unbound_module(self, tmp_path: pathlib.Path) -> None:
        source = _block(PY312, "json.loads")
        mutated = source.replace("import traceback\n", "", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0


class TestPy313Examples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PY313)) == 10

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PY313, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_keyword_suggestion_arrives_in_3_13(self, tmp_path: pathlib.Path) -> None:
        result = run_block(_block(PY313, "greting="), tmp_path)
        suggested = "Did you mean 'greeting'?" in result.stdout

        assert "unexpected keyword argument 'greting'" in result.stdout
        assert suggested == (sys.version_info >= (3, 13)), result.stdout

    def test_the_runner_notices_an_uncaught_error(self, tmp_path: pathlib.Path) -> None:
        source = _block(PY313, "greting=")
        mutated = source.replace("except TypeError as error:", "except ValueError as error:", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
