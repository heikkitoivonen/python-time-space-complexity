"""Tests for docs/stdlib/nturl2path.md.

The page prices both functions as O(n) in the characters of their argument,
and O(n·c), c being the path components, on the releases that build a drive
path one component at a time. Lib/nturl2path.py has three implementations
across the supported range: v3.10.19, v3.11.14, v3.12.7 and v3.13.0 append
each component to a growing string when the argument has a drive letter;
v3.12.8 and v3.13.1 replace that loop with one `replace()` and one
`quote()` or `unquote()` over the whole tail; v3.14.0 rewrites
`pathname2url()` around `ntpath.splitroot()` and adds the import-time
deprecation. The bounds are read from those sources. A timing test that
holds the length fixed and varies the component count separates the two
shapes, and fails if a release moves from one to the other; the conversions
themselves and the deprecation are settled by observation.

Measurement scope:

* At a fixed 80,000 characters, an argument of 40,000 one-character
  components is timed against one of a single component. With a drive
  letter, the appending releases cost x305 to x3,074 more for the many
  components across both functions on 3.10.21, 3.11.16, 3.12.7 and 3.13.0
  (aarch64), and 3.12.14, 3.13.14 and 3.14.7 cost x1.3 to x3.9; the test
  asserts above x50 on the appending releases and below it everywhere else.
  Without a drive letter every release measured x1.4 to x15.2: splitting
  and joining 40,000 components costs more than one, but by a constant
  factor. The appending releases are chosen by `sys.version_info`: CI runs
  3.10.21 and 3.11.16 on that side and 3.12.14, 3.13.14 and 3.14.7 on the
  other.
* Traced peaks over a drive path of 7-character components, 8 with the
  separator, grow between 5x and 20x from 80,000 to 800,000 characters on
  every release, so space is linear, not quadratic, in either
  implementation.
* `pathname2url()` turns `C:\\My Files\\café.txt` into
  `///C:/My%20Files/caf%C3%A9.txt`, and `url2pathname()` turns that back.
  `url2pathname()` accepts `C|` and `C:` alike, with or without the leading
  slash, and turns `//server/share/...` into a UNC path.
* Importing warns with `DeprecationWarning` from 3.14 and not before, naming
  Python 3.19 and `urllib.request`; a call after the import does not warn.
* `urllib.request.url2pathname('///C:/x')` is `C:\\x` where `os.name` is
  `'nt'` and something else elsewhere, so it converts for the platform it
  runs on; `ntpath` joins and splits Windows paths on any platform.
* Every fenced Python block runs in its own subprocess, so each import is the
  first, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That `urllib.request` converts like nturl2path on Windows is checked for
  one drive URL, and only on CI's Windows runner; other inputs are not
  compared.
* The removal in 3.19 is what the 3.14 warning says, not something a
  supported interpreter can show.
* The release boundaries 3.12.8 and 3.13.1 come from comparing
  Lib/nturl2path.py at each 3.12 and 3.13 tag in CPython. 3.12.7 and 3.13.0
  were run on the appending side and 3.12.14 and 3.13.14 on the other; the
  patch releases between them were not.
* One ratio at one length cannot show that the appending releases grow in
  proportion to c, nor that the others are linear in n rather than merely
  independent of c. Both are read from the source: every release makes a
  fixed number of `replace()`, `split()`, `join()`, `quote()` and
  `unquote()` passes, plus the appending loop where it exists. Growth in n is not timed, because at the sizes that
  separate x4 from x16 per step, cache effects alone moved single steps to
  x6.7 on a linear release.
* Arguments of mixed component lengths, percent-escaped components and
  non-ASCII text are not timed; escaping widens the output by a constant
  factor at most. Error inputs (a second colon, a bad drive) raise on some
  releases and not others, and are not documented.
"""

from __future__ import annotations

import importlib
import ntpath
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import urllib.request
import warnings
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "nturl2path.md"
EXPECTED_BLOCKS = 3

# Releases whose drive-letter branch appends one component at a time.
APPENDS_COMPONENTS = sys.version_info[:3] < (3, 12, 8) or sys.version_info[:3] == (3, 13, 0)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    nturl2path: Any = importlib.import_module("nturl2path")


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def url_of(drive: bool, components: int, width: int) -> str:
    return ("/C:" if drive else "") + ("/" + "a" * width) * components


def path_of(drive: bool, components: int, width: int) -> str:
    return ("C:" if drive else "") + ("\\" + "a" * width) * components


SHAPES = {
    "url2pathname": (lambda: nturl2path.url2pathname, url_of),
    "pathname2url": (lambda: nturl2path.pathname2url, path_of),
}


class TestConversions:
    """The Notes cells: a colon or a pipe after the drive, `%XX` decoding, a
    `///C:/...` URL with escapes, and a UNC path for a server authority."""

    def test_pathname2url_escapes_and_adds_an_empty_authority(self) -> None:
        url = nturl2path.pathname2url("C:\\My Files\\café.txt")
        assert url == "///C:/My%20Files/caf%C3%A9.txt"

    def test_url2pathname_decodes_it_back(self) -> None:
        path = nturl2path.url2pathname("///C:/My%20Files/caf%C3%A9.txt")
        assert path == "C:\\My Files\\café.txt"

    @pytest.mark.parametrize("url", ["/C|/a/b", "/C:/a/b", "C|/a/b", "C:/a/b", "///C|/a/b"])
    def test_a_pipe_or_a_colon_marks_the_drive(self, url: str) -> None:
        assert nturl2path.url2pathname(url) == "C:\\a\\b"

    def test_a_server_authority_becomes_a_unc_path(self) -> None:
        path = nturl2path.url2pathname("//server/share/file.txt")
        assert path == "\\\\server\\share\\file.txt"


class TestComponentCount:
    """`O(n)`, and `O(n·c)` on 3.10, 3.11, 3.12.0-3.12.7 and 3.13.0 with a
    drive letter. The length is held at 80,000 characters while the component
    count goes from 1 to 40,000, so only the c term can move the cost: the
    appending releases pay x305 or more, the others under x16."""

    LENGTH = 80_000

    @pytest.mark.timing
    @pytest.mark.parametrize("drive", [True, False], ids=["drive", "no-drive"])
    @pytest.mark.parametrize("name", list(SHAPES))
    def test_many_components_cost_more_only_where_components_are_appended(
        self, name: str, drive: bool
    ) -> None:
        get, build = SHAPES[name]
        convert = get()
        many = build(drive, self.LENGTH // 2, 1)
        one = build(drive, 1, self.LENGTH - 1)
        assert abs(len(many) - len(one)) <= 3

        many_ns = best_ns(lambda: convert(many), repeats=5)
        one_ns = best_ns(lambda: convert(one), repeats=5)
        ratio = many_ns / one_ns

        if drive and APPENDS_COMPONENTS:
            assert ratio > 50, (
                f"{name}: 40,000 components cost x{ratio:.1f} of one at equal length "
                f"({one_ns:.0f}ns to {many_ns:.0f}ns); O(n·c) predicts hundreds"
            )
        else:
            assert ratio < 50, (
                f"{name}: 40,000 components cost x{ratio:.1f} of one at equal length "
                f"({one_ns:.0f}ns to {many_ns:.0f}ns); O(n) predicts a small constant"
            )


class TestSpaceIsLinear:
    """The Space column: O(n) on every release. Ten times the length raises
    the traced peak about ten times, where a quadratic would give a hundred."""

    @pytest.mark.parametrize("name", list(SHAPES))
    def test_the_peak_tracks_the_length(self, name: str) -> None:
        get, build = SHAPES[name]
        convert = get()
        small, large = build(True, 10_000, 7), build(True, 100_000, 7)
        convert(small)

        ratio = peak_bytes(lambda: convert(large)) / peak_bytes(lambda: convert(small))
        assert 5 < ratio < 20, f"{name}: 10x the length raised the peak x{ratio:.1f}"


class TestDeprecation:
    """The warning box and Version Notes: importing warns from 3.14, naming
    3.19 and `urllib.request`; calling does not warn."""

    def test_importing_it_warns_from_3_14(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import nturl2path"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 14)), result.stderr
        if sys.version_info >= (3, 14):
            assert "DeprecationWarning" in result.stderr
            assert "3.19" in result.stderr
            assert "urllib.request" in result.stderr

    def test_calling_it_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            nturl2path.url2pathname("/C:/x")
            nturl2path.pathname2url("C:\\x")


class TestRelatedModules:
    """The warning box and Related Modules: `urllib.request` converts for the
    platform it runs on, and `ntpath` handles Windows paths anywhere."""

    def test_urllib_request_converts_drive_urls_only_on_windows(self) -> None:
        converted = urllib.request.url2pathname("///C:/x")
        assert (converted == "C:\\x") == (os.name == "nt"), converted

    def test_ntpath_handles_windows_paths_here(self) -> None:
        assert ntpath.join("C:\\a", "b") == "C:\\a\\b"
        assert ntpath.split("C:\\a\\b") == ("C:\\a", "b")


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
    """Each block runs in its own subprocess, so its import of the module is
    the first and the deprecation block sees the warning, and asserts its own
    result."""

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
        line, source = next((n, s) for n, s in _blocks() if "caf%C3%A9.txt'" in s)
        mutated = source.replace("caf%C3%A9.txt'", "cafe.txt'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
