"""Tests that every English page with Python examples has a page test that runs them.

A page's fenced `python` blocks are run by the page's own test module, which
counts them in a `test_the_page_has_the_expected_blocks` test and runs them
beside it. This file checks the pairing: every English page with at least one
`python` block must be named, as `docs/<path>.md`, in the opening paragraph of
the docstring of a `tests/test_*.py` module that defines that count test. The
count test makes a block added to a covered page fail until the module's
runner accounts for it; this check makes a page fail until it has such a
module at all.

Measurement scope:

* The opening paragraph alone names a module's pages, so a module that only
  cross-references a page further down its docstring does not cover it.
* A module covers its pages only when it defines the count test; naming a page
  without one covers nothing.
* Translations are left out: `scripts/validate_translations.py` holds their
  code blocks byte for byte to the English ones.

The shared runner, `tests/page_examples.run_block()`, is checked here too: a
block that reads stdin gets end-of-file rather than waiting, and a block that
outlives its timeout comes back as a failure carrying the stderr it had
written, instead of raising out of the page's loop.

Not settled here: that a module's runner executes the blocks rather than only
counting them. That is kept by review. A module whose blocks cannot run on
any interpreter or platform CI uses says so in its own docstring and compiles
them instead.
"""

from __future__ import annotations

import ast
import functools
import pathlib
import re

from scripts.validate_translations import LOCALES
from tests.page_examples import DOCS, python_blocks, run_block

TESTS = pathlib.Path(__file__).parent
COUNT_TEST = "test_the_page_has_the_expected_blocks"


@functools.cache
def pages_with_examples(docs: pathlib.Path) -> list[str]:
    """English pages with at least one fenced python block, relative to docs."""
    return sorted(
        path.relative_to(docs).as_posix()
        for path in docs.rglob("*.md")
        if path.relative_to(docs).parts[0] not in LOCALES and python_blocks(path)
    )


def _collectable_functions(tree: ast.Module) -> list[str]:
    """Names pytest can collect: module-level functions and methods of `Test*` classes."""
    scopes = [tree.body] + [
        node.body
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
    ]
    return [
        node.name
        for scope in scopes
        for node in scope
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


@functools.cache
def covering_modules(tests: pathlib.Path) -> dict[str, list[str]]:
    """Each page named by a test module that counts its blocks, with the modules."""
    covered: dict[str, list[str]] = {}
    for module in sorted(tests.glob("test_*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        if COUNT_TEST not in _collectable_functions(tree):
            continue
        opening = re.split(r"\n[ \t]*\n", ast.get_docstring(tree) or "")[0]
        for page in re.findall(r"\bdocs/([\w./-]+?\.md)\b", opening):
            covered.setdefault(page, []).append(module.name)
    return covered


def uncovered_pages(docs: pathlib.Path, tests: pathlib.Path) -> list[str]:
    covered = covering_modules(tests)
    return [page for page in pages_with_examples(docs) if page not in covered]


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestEveryPageHasAnExampleTest:
    """The real tree: every English page with a python block is covered."""

    def test_every_page_with_python_blocks_has_a_page_test(self) -> None:
        missing = uncovered_pages(DOCS, TESTS)

        assert not missing, (
            "these pages have python blocks but no test module that names them in "
            f"its docstring's opening paragraph and defines {COUNT_TEST}():\n  "
            + "\n  ".join(missing)
        )

    def test_the_check_finds_the_reference_module(self) -> None:
        assert "test_csv_complexity.py" in covering_modules(TESTS)["stdlib/csv.md"]

    def test_one_module_can_cover_several_pages(self) -> None:
        covered = covering_modules(TESTS)

        assert "test_int_complexity.py" in covered["builtins/int.md"]
        assert "test_int_complexity.py" in covered["builtins/int_func.md"]

    def test_translations_are_not_pages_of_their_own(self) -> None:
        pages = pages_with_examples(DOCS)

        assert "stdlib/index.md" in pages
        assert not any(page.split("/")[0] in LOCALES for page in pages)


class TestTheCheckItself:
    """A synthetic tree, so each rule is seen to reject what it should."""

    PAGE = "# Page\n\n```python\nx = 1\n```\n"
    COUNTED = f'"""Tests for docs/stdlib/demo.md."""\n\n\ndef {COUNT_TEST}() -> None:\n    pass\n'

    def test_a_named_and_counted_page_is_covered(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        _write(tmp_path / "tests/test_demo.py", self.COUNTED)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == []

    def test_a_page_with_no_module_is_reported(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        _write(tmp_path / "tests/test_other.py", self.COUNTED.replace("demo.md", "other.md"))

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == ["stdlib/demo.md"]

    def test_a_module_without_the_count_test_covers_nothing(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        renamed = self.COUNTED.replace(COUNT_TEST, "test_something_else")
        assert renamed != self.COUNTED
        _write(tmp_path / "tests/test_demo.py", renamed)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == ["stdlib/demo.md"]

    def test_a_page_named_past_the_opening_paragraph_is_not_covered(
        self, tmp_path: pathlib.Path
    ) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        later = self.COUNTED.replace(
            "Tests for docs/stdlib/demo.md.",
            "Tests for docs/stdlib/other.md.\n\nSee docs/stdlib/demo.md.",
        )
        assert later != self.COUNTED
        _write(tmp_path / "tests/test_other.py", later)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == ["stdlib/demo.md"]

    def test_a_blank_line_of_spaces_ends_the_opening_paragraph(
        self, tmp_path: pathlib.Path
    ) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        later = self.COUNTED.replace(
            "Tests for docs/stdlib/demo.md.",
            "Tests for docs/stdlib/other.md.\n   \nSee docs/stdlib/demo.md.",
        )
        assert later != self.COUNTED
        _write(tmp_path / "tests/test_other.py", later)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == ["stdlib/demo.md"]

    def test_a_nested_count_test_is_not_collected(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        nested = self.COUNTED.replace(
            f"def {COUNT_TEST}() -> None:\n    pass\n",
            f"def helper() -> None:\n    def {COUNT_TEST}() -> None:\n        pass\n",
        )
        assert nested != self.COUNTED
        _write(tmp_path / "tests/test_demo.py", nested)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == ["stdlib/demo.md"]

    def test_a_count_test_method_is_collected(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        method = self.COUNTED.replace(
            f"def {COUNT_TEST}() -> None:\n    pass\n",
            f"class TestDocumentedExamples:\n    def {COUNT_TEST}(self) -> None:\n        pass\n",
        )
        assert method != self.COUNTED
        _write(tmp_path / "tests/test_demo.py", method)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == []

    def test_a_count_test_in_a_helper_class_is_not_collected(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", self.PAGE)
        helper = self.COUNTED.replace(
            f"def {COUNT_TEST}() -> None:\n    pass\n",
            f"class Helper:\n    def {COUNT_TEST}(self) -> None:\n        pass\n",
        )
        assert helper != self.COUNTED
        _write(tmp_path / "tests/test_demo.py", helper)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == ["stdlib/demo.md"]

    def test_a_page_without_python_blocks_needs_no_module(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / "docs/stdlib/demo.md", "# Page\n\n```bash\nls\n```\n")

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == []

    def test_a_translated_page_needs_no_module(self, tmp_path: pathlib.Path) -> None:
        _write(tmp_path / f"docs/{LOCALES[0]}/stdlib/demo.md", self.PAGE)

        assert uncovered_pages(tmp_path / "docs", tmp_path / "tests") == []


class TestTheSharedRunner:
    """`run_block()` turns a block that would block or hang into a failure."""

    def test_a_block_reading_stdin_gets_end_of_file(self, tmp_path: pathlib.Path) -> None:
        result = run_block("input()\n", tmp_path)

        assert result.returncode != 0
        assert "EOFError" in result.stderr

    def test_a_block_that_hangs_is_reported_with_its_stderr(self, tmp_path: pathlib.Path) -> None:
        source = (
            "import sys, time\nprint('started', file=sys.stderr, flush=True)\ntime.sleep(600)\n"
        )

        result = run_block(source, tmp_path, timeout=5)

        assert result.returncode != 0
        assert result.stderr.startswith("started"), result.stderr
        assert result.stderr.endswith("timed out after 5 seconds"), result.stderr
