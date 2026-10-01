"""Tests for docs/stdlib/this.md.

The page prices the module body, which takes no input: it decodes a fixed
ROT13 text with a fixed 52-entry table and prints the result, so every bound
is O(1) and what the tests settle is behaviour - when the body runs, what it
prints and where, and what the two documented attributes hold. Every import
whose printing is asserted happens in a fresh interpreter, so it is a real
first import; the in-process import used by the attribute tests is made under
`contextlib.redirect_stdout` and removed from `sys.modules` afterwards if it
was not there before.

Measurement scope:

* The first import in a fresh interpreter is observed to call `print` exactly
  once, and to write exactly `codecs.decode(this.s, 'rot13')` plus a newline
  to the process's standard output. Under `contextlib.redirect_stdout` the
  same text goes to the replacement stream and nothing reaches the real one,
  so the body writes to whatever `sys.stdout` is when it runs.
* A second `import this` in the same process calls `print` no more, writes
  nothing, and binds the object already in `sys.modules`.
  `importlib.reload(this)` returns the same object and prints the same text
  again.
* `this.s` decoded with the `rot13` codec equals the printed text without the
  trailing newline, starts with the title line and ends with the Namespaces
  aphorism. `this.d` has 52 entries, maps each ASCII letter to the letter 13
  places on in the same case, and decoding `this.s` through it character by
  character gives the codec's result.
* Every fenced Python block runs in its own fresh interpreter, so each one's
  first import is a real first import, and a mutated assertion in one of them
  is asserted to fail.

Not settled here:

* The O(1) bounds are definitional: the body reads no argument, file or
  environment, and Lib/this.py is identical in the v3.10.19, v3.11.14,
  v3.12.12, v3.13.11 and v3.14.2 tags, so the text and the work do not vary
  inside the supported range. No timing test would add to that.
* Finding and loading the module file is the import system's cost and is
  priced and tested on the importlib page.
* `this.c` and `this.i` are the loop variables left over from building `d`
  (97 and 25 after the loops); they carry no meaning and are not documented.
  The official API inventory lists no name in `this`, so the shared audit
  checks only that this page exists; its name coverage is the attributes
  table.
"""

from __future__ import annotations

import codecs
import contextlib
import importlib
import io
import pathlib
import re
import string
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from types import ModuleType

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "this.md"
EXPECTED_BLOCKS = 3
TITLE = "The Zen of Python, by Tim Peters"


def run_python(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def assert_ran(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="module")
def this() -> Iterator[ModuleType]:
    """The module, imported with its print captured."""
    was_loaded = "this" in sys.modules
    with contextlib.redirect_stdout(io.StringIO()):
        module = importlib.import_module("this")
    yield module
    if not was_loaded:
        sys.modules.pop("this", None)


class TestOnlyTheFirstImportPrints:
    """`import this`, first in a process | O(1) | O(1): one `print()` to
    `sys.stdout`; again | O(1) | O(1): a `sys.modules` hit that prints
    nothing; `importlib.reload(this)` | O(1) | O(1): prints again."""

    def test_the_first_import_prints_the_decoded_text_once(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import builtins
            import codecs
            import sys

            assert "this" not in sys.modules
            calls = []
            original = builtins.print

            def counting(*args, **kwargs):
                calls.append(args)
                return original(*args, **kwargs)

            builtins.print = counting
            import this
            first = sys.modules["this"]
            import this
            builtins.print = original

            assert len(calls) == 1, calls
            assert this is first
            sys.stderr.write(codecs.decode(this.s, "rot13"))
            """,
            tmp_path,
        )

        assert_ran(result)
        assert result.stdout == result.stderr + "\n"
        assert result.stdout.startswith(TITLE + "\n\n")

    def test_the_text_goes_to_whatever_sys_stdout_is(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import contextlib
            import io
            import sys

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                import this
            sys.stderr.write(buffer.getvalue())
            """,
            tmp_path,
        )

        assert_ran(result)
        assert result.stdout == ""
        assert result.stderr.startswith(TITLE + "\n\n")

    def test_reload_runs_the_body_and_prints_again(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            f"""
            import contextlib
            import importlib
            import io

            first, second = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(first):
                import this
            with contextlib.redirect_stdout(second):
                assert importlib.reload(this) is this
            assert first.getvalue().startswith({TITLE!r}), first.getvalue()
            assert second.getvalue() == first.getvalue(), second.getvalue()
            """,
            tmp_path,
        )

        assert_ran(result)
        assert result.stdout == ""


class TestTheAttributesHoldTheText:
    """`this.s` | O(1) | O(1): the ROT13-encoded Zen; `this.d` | O(1) | O(1):
    the 52-letter ROT13 table the body decodes it with."""

    def test_s_decodes_to_the_zen(self, this: ModuleType) -> None:
        zen = codecs.decode(this.s, "rot13")

        assert zen.startswith(TITLE + "\n\nBeautiful is better than ugly.\n")
        assert zen.splitlines()[-1] == (
            "Namespaces are one honking great idea -- let's do more of those!"
        )

    def test_d_is_the_rot13_table_for_ascii_letters(self, this: ModuleType) -> None:
        expected = {
            letter: alphabet[(index + 13) % 26]
            for alphabet in (string.ascii_uppercase, string.ascii_lowercase)
            for index, letter in enumerate(alphabet)
        }

        assert this.d == expected
        assert len(this.d) == 52

    def test_decoding_through_d_matches_the_codec(self, this: ModuleType) -> None:
        by_table = "".join(this.d.get(char, char) for char in this.s)

        assert by_table == codecs.decode(this.s, "rot13")


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


class TestDocumentedExamples:
    """Each block runs in its own fresh interpreter, so each one's first import
    is a real first import, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_python(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")
            elif result.stdout:
                failures.append(f"{PAGE.name}:{line}\nprinted {result.stdout[:80]!r}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "again.getvalue() == ''" in s)
        mutated = source.replace("again.getvalue() == ''", "again.getvalue() != ''", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert run_python(mutated, tmp_path).returncode != 0
