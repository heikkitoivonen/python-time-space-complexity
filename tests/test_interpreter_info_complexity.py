"""Tests for docs/builtins/interpreter_info.md.

`copyright`, `credits` and `license` are `_sitebuiltins._Printer` instances
that `site.setcopyright()` installs into builtins. A printer splits its text
into lines on first use and caches them; `__repr__` joins them when there are
at most `MAXLINES` (23) and otherwise returns a fixed one-line hint. Before
3.13.12 and 3.14.3 `__call__` prints 23 lines between prompts; from those
releases, and in 3.15, it joins the lines and hands the text to
`_pyrepl.pager.get_pager()`'s pager. The rows are settled by observation and
traced allocation, with no stopwatch: printers built over temporary files
separate the first display from later ones, and stubbed `input()` and `stdout`
drive the pager.

Measurement scope:

* The three objects share the `_Printer` type, are not `str`, and are absent
  from builtins in a `python -S` subprocess, where `sys.copyright` still
  exists. `str(copyright)` equals `sys.copyright` and is 11 lines; `credits`
  fits under the 23-line limit and `sys` has no `credits`.
* The display limit is observed on printers of 23 lines (full text) and 24
  lines (the hint). A 23-line printer whose lines grow from 100 to 100,000
  characters makes `repr()` peak more than 100x higher, so a full display is
  O(n) in space.
* A printer over a 100,000-line temporary file peaks more than 50x higher on
  first display than one over a 30-line file; a second display of a 30,000-line
  one peaks under 2 KB and still returns the hint after the file is deleted, so
  the read happens once. A printer whose files cannot be read returns its
  inline fallback text.
* The real `license` is observed in a subprocess with an audit hook: the first
  `str(license)` raises one or more `open` events, the second none. Whether it
  shows the hint or the fallback pointer depends on whether a license file is
  installed, and the test accepts the one that matches.
* Before 3.13.12 and 3.14.3, `obj()` on a 50-line printer prints 23, 23 and 4
  lines and asks for input after 23 and 46 lines; answering `q` stops after one
  page. Paging a 100,000-line printer whose text is already cached peaks under
  16 KB with stdout discarded. From 3.13.12, 3.14.3 and 3.15.0, with stdout not
  a terminal, exactly the 50-line text is written without a prompt, and calling
  the cached 100,000-line printer peaks above the text's length, the joined
  copy. Both sides were run on 3.11, 3.13.11, 3.13.12, 3.14.2, 3.14.3 and
  3.15.0.
* Every fenced Python block runs in its own subprocess, and a mutated assertion
  in one of them is asserted to fail.

Not settled here:

* Which files `license` reads, and whether one is installed at all, depends on
  how the interpreter was packaged; only the hint and the fallback pointer are
  asserted, with no `LICENSE` file in the current directory.
* Time is not measured. The O(n) rows rest on the split and join over the text
  in Lib/_sitebuiltins.py, which the allocation tests observe through space
  alone.
* No pager is run against a terminal: the printer's own pager has `input()`
  stubbed, and with `_pyrepl.pager` stdout is not a terminal, so `get_pager()`
  picks its plain pager. An external pager such as `less` holds whatever it
  reads; that is outside the process and not measured.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "interpreter_info.md"
EXPECTED_BLOCKS = 8

PRINTER = type(builtins.copyright)  # pyright: ignore[reportAttributeAccessIssue]
HINT = "Type license() to see the full license text"
FALLBACK = "See https://www.python.org/psf/license/"


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak bytes traced while `func` runs."""
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def printer_over(tmp_path: pathlib.Path, name: str, lines: int, width: int = 60) -> Any:
    """A `license`-style printer that reads `lines` lines from a file it has not opened yet."""
    path = tmp_path / name
    path.write_text("\n".join("x" * width for _ in range(lines)), encoding="utf-8")
    return PRINTER("license", FALLBACK, [name], [str(tmp_path)])


class TestTheObjectsArePrinters:
    """'These three names are not functions and not strings', and `site` installs them."""

    def test_all_three_share_one_type_that_is_not_str(self) -> None:
        objects = [builtins.copyright, builtins.credits, builtins.license]  # pyright: ignore[reportAttributeAccessIssue]
        assert {type(obj).__name__ for obj in objects} == {"_Printer"}
        assert not any(isinstance(obj, str) for obj in objects)

    def test_python_dash_s_removes_them_and_keeps_sys_copyright(self) -> None:
        script = (
            "import builtins, sys\n"
            "print([hasattr(builtins, n) for n in ('copyright', 'credits', 'license')])\n"
            "print(bool(sys.copyright))\n"
        )
        result = subprocess.run(
            [sys.executable, "-S", "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        assert result.stdout.split("\n")[:2] == ["[False, False, False]", "True"]


class TestCopyrightAndCreditsPrintInFull:
    """Rows: `copyright` is 11 lines and `credits` a few, both under the limit."""

    def test_copyright_is_sys_copyright_in_eleven_lines(self) -> None:
        text = str(builtins.copyright)  # pyright: ignore[reportAttributeAccessIssue]
        assert text == sys.copyright
        assert len(text.split("\n")) == 11

    def test_credits_fits_under_the_limit_and_has_no_sys_twin(self) -> None:
        text = repr(builtins.credits)  # pyright: ignore[reportAttributeAccessIssue]
        assert len(text.split("\n")) <= PRINTER.MAXLINES
        assert "Thanks to CWI" in text
        assert not hasattr(sys, "credits")


class TestDisplayIsCappedAtMaxlines:
    """'`__repr__` returns the joined text only when the content fits in that many lines.'"""

    def test_twenty_three_lines_print_and_twenty_four_give_the_hint(self) -> None:
        assert PRINTER.MAXLINES == 23
        fits = "\n".join(str(i) for i in range(23))
        assert repr(PRINTER("x", fits)) == fits
        assert repr(PRINTER("x", fits + "\n23")) == "Type x() to see the full x text"

    def test_a_full_display_grows_with_the_text(self) -> None:
        def display(width: int) -> Callable[[], Any]:
            printer = PRINTER("x", "\n".join("y" * width for _ in range(23)))
            repr(printer)  # caches the lines, so only the join is measured
            return lambda: repr(printer)

        small, large = peak_bytes(display(100)), peak_bytes(display(100_000))
        assert large > 100 * small, (small, large)


class TestLicenseIsReadOnce:
    """Rows: the first `license` display reads and caches the file, later ones are O(1)."""

    def test_the_first_display_grows_with_the_file(self, tmp_path: pathlib.Path) -> None:
        small = printer_over(tmp_path, "small", 30)
        large = printer_over(tmp_path, "large", 100_000)
        small_peak, large_peak = peak_bytes(lambda: repr(small)), peak_bytes(lambda: repr(large))
        assert large_peak > 50 * small_peak, (small_peak, large_peak)

    def test_later_displays_are_cached_and_constant(self, tmp_path: pathlib.Path) -> None:
        printer = printer_over(tmp_path, "LICENSE", 30_000)
        first = repr(printer)
        (tmp_path / "LICENSE").unlink()

        later_peak = peak_bytes(lambda: repr(printer))
        assert repr(printer) == first == HINT
        assert later_peak < 2_000, later_peak

    def test_without_a_readable_file_it_falls_back_to_the_inline_text(
        self, tmp_path: pathlib.Path
    ) -> None:
        printer = PRINTER("license", FALLBACK, ["missing"], [str(tmp_path)])
        assert repr(printer) == FALLBACK

    def test_the_real_license_opens_files_on_first_display_only(self) -> None:
        script = textwrap.dedent(
            """
            import sys
            opened = []
            sys.addaudithook(lambda e, a: e == "open" and opened.append(a[0]))
            first = str(license)
            on_first = len(opened)
            second = str(license)
            print(on_first, len(opened) - on_first, first == second)
            print(first)
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        counts, shown = result.stdout.split("\n")[:2]
        on_first, on_second, same = counts.split()
        assert int(on_first) > 0
        assert (on_second, same) == ("0", "True")
        assert shown in (HINT, FALLBACK)


class Answers:
    """A stand-in for `input()` that replays `answer` and records, at each prompt, how many
    lines `out` held."""

    def __init__(self, answer: str, out: io.StringIO) -> None:
        self.answer = answer
        self.out = out
        self.lines_at_prompt: list[int] = []

    @property
    def prompts(self) -> int:
        return len(self.lines_at_prompt)

    def __call__(self, prompt: str = "") -> str:
        self.lines_at_prompt.append(self.out.getvalue().count("\n"))
        return self.answer


class Discard:
    """A stdout that keeps nothing it is given."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


@contextlib.contextmanager
def paging(monkeypatch: pytest.MonkeyPatch, answer: str) -> Iterator[tuple[Answers, io.StringIO]]:
    out = io.StringIO()
    answers = Answers(answer, out)
    monkeypatch.setattr(builtins, "input", answers)
    with contextlib.redirect_stdout(out):
        yield answers, out


# 3.13.12, 3.14.3 and 3.15.0 replaced the printer's own pager with `_pyrepl.pager`.
_VERSION = sys.version_info[:3]
USES_PAGER = _VERSION >= (3, 14, 3) or (3, 13, 12) <= _VERSION < (3, 14)
OLD_PAGER = pytest.mark.skipif(
    USES_PAGER, reason="version: 3.13.12+, 3.14.3+ and 3.15 hand the text to a pager"
)
NEW_PAGER = pytest.mark.skipif(
    not USES_PAGER, reason="version: before 3.13.12 and 3.14.3 the printer pages the text itself"
)


class TestCallingPagesTheText:
    """Row: `obj()` is O(n). Before 3.13.12 and 3.14.3 it prints the cached text 23 lines at a
    time in O(1) extra space; from those releases it joins the text and hands it to a pager,
    which is O(n) space."""

    @OLD_PAGER
    def test_fifty_lines_take_three_pages_and_two_prompts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        printer = PRINTER("x", "\n".join(str(i) for i in range(50)))
        with paging(monkeypatch, "") as (answers, out):
            printer()
        assert out.getvalue().split("\n")[:-1] == [str(i) for i in range(50)]
        assert answers.lines_at_prompt == [23, 46]

    @OLD_PAGER
    def test_q_stops_after_one_page(self, monkeypatch: pytest.MonkeyPatch) -> None:
        printer = PRINTER("x", "\n".join(str(i) for i in range(50)))
        with paging(monkeypatch, "q") as (answers, out):
            printer()
        assert out.getvalue().split("\n")[:-1] == [str(i) for i in range(23)]
        assert answers.lines_at_prompt == [23]

    @OLD_PAGER
    def test_paging_cached_text_holds_no_copy_of_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        printer = PRINTER("x", "\n".join("y" * 60 for _ in range(100_000)))
        repr(printer)
        monkeypatch.setattr(builtins, "input", lambda prompt="": "")
        with contextlib.redirect_stdout(Discard()):
            peak = peak_bytes(printer)
        assert peak < 16_000, peak

    @NEW_PAGER
    def test_the_whole_text_goes_to_the_pager_without_prompting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = "\n".join(str(i) for i in range(50))
        printer = PRINTER("x", text)
        with paging(monkeypatch, "q") as (answers, out):
            printer()
        assert out.getvalue() == text
        assert answers.prompts == 0

    @NEW_PAGER
    def test_calling_joins_the_cached_text(self) -> None:
        text = "\n".join("y" * 60 for _ in range(100_000))
        printer = PRINTER("x", text)
        with contextlib.redirect_stdout(Discard()):
            printer()  # caches the lines and imports the pager
            peak = peak_bytes(printer)
        assert peak > len(text), (peak, len(text))


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


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, with `site` loaded, and asserts its own result.
    The `license()` call is commented out on the page, so the pager is never entered."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "len(opened) == reads_on_first" in s)
        mutated = source.replace("len(opened) == reads_on_first", "len(opened) > reads_on_first")

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
