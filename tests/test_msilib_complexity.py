"""Tests for docs/stdlib/msilib.md.

msilib existed only on Windows, and only before Python 3.13. CI runs Windows
only on the newest supported Python, so no interpreter this project tests on
can import it, and the page's blocks are compiled rather than run: the count
and the compile keep them valid Python and keep a new block from going
unnoticed.

Not settled here: every row and comment on the page. They price calls into
the Windows Installer API, which needs Windows and Python 3.12 or older, plus
an existing `package.msi` the blocks open.
"""

from __future__ import annotations

from tests.page_examples import DOCS, python_blocks

PAGE = DOCS / "stdlib" / "msilib.md"
EXPECTED_BLOCKS = 3


class TestDocumentedExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_every_block_compiles(self) -> None:
        for line, source in python_blocks(PAGE):
            compile(source, f"{PAGE.name}:{line}", "exec")

    def test_every_block_imports_msilib(self) -> None:
        assert all("import msilib" in source for _, source in python_blocks(PAGE))
