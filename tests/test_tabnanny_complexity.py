"""Tests for docs/stdlib/tabnanny.md.

The page prices `tabnanny` as a stream: `check()` feeds one file at a time
through `tokenize`, holds the current line or token and the stack of open
indents, and stops at the first problem. Streaming and early exit are settled
by counting what is taken from the input, space by traced allocation, and the
linear time bound by a timing ratio over three sizes. The directory walk,
output format and version boundaries are settled by observation on real files
in a temporary directory.

Measurement scope:

* `process_tokens()` over a stream whose third line mixes a tab with eight
  spaces, followed by 100,000 clean lines, takes three lines from `readline`.
  A counting token iterator shows it takes no token after the one it raises
  on. Given 1,000, 10,000 and 100,000 clean lines, its traced peak stays under
  100 KB and varies by under 2x; one 1,000,000-character string, on a single
  line or spread over lines inside triple quotes, peaks over 1 MB, which is
  the l term.
* A synthetic stream of 20 and then 2,000 nested INDENT tokens peaks more than
  20x higher at the greater depth, which is the d term. The indents widen with
  depth, so this measures d together with indentation width.
* In a timing test, 2,000, 20,000 and 200,000 clean lines through
  `process_tokens()` cost between 5x and 20x more at each 10x step: linear,
  where quadratic would give about 100x. The lines are 9 characters each;
  line length and multi-line tokens are not varied in time, only in space,
  and `check()`'s file opening is not in the timed call.
* `check()` on a directory of 20,000 non-`.py` files peaks more than 20x above
  one of 20, which is its listing, the e term. That the listings of the
  directories above are held while a subdirectory is walked is read from
  Lib/tabnanny.py, where `names` is a local of the recursive call.
* `check()` returns `None`, prints `path line repr(line)` for a problem and
  nothing for a clean file, prints only the path with `filename_only` set and
  several lines with `verbose` set, reports only the first of two problems in
  a file, and checks a path named `notes.txt` given directly. Over a directory
  it descends a subdirectory, skips a symlinked one and a non-`.py` file, and
  checks a `.py` symlink.
* `python -m tabnanny` on a file with a problem prints it and exits 0; with
  `-q` it prints only the path, and with `-v` it names the line.
* On 3.12+ a missing file, a syntax error and 100 levels of indentation each
  raise `SystemExit(1)` from `check()`; on 3.10 and 3.11 each returns `None`,
  and the message printed to stderr there is not asserted.
  On 3.12+ a tab followed by eight spaces is reported with the tokenizer's
  message, and `compile()` raises `TabError` for it. An indent pair that
  `compile()` accepts but that is not greater at tab size 2 is reported by
  `tabnanny`'s own "indent not greater" message on every version.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Treating one line's indentation width, and a path's length, as O(1) is a
  cost-model assumption; a directory chain h deep holds paths whose lengths
  sum to O(h^2) characters, and that is not measured.
  Comparing two indents that mix tabs and spaces tries each tab size up to the
  longest run of spaces, so a very wide mixed indent costs more than its
  length; that is not measured.
* The O(e + c) time of a directory walk is read from Lib/tabnanny.py (one
  `os.listdir()` per directory, one `check()` per matching name); only the
  listing's space is measured.
* `Whitespace`, `errprint`, `format_witnesses` and `main` are internal helpers
  outside the documented API and are not given rows. Encoding-cookie errors
  from `tokenize.open()` propagate uncaught and are not varied, nor are
  non-UTF-8 sources, symlink loops, or paths containing spaces.
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import re
import subprocess
import sys
import tabnanny
import textwrap
import time
import tokenize
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tabnanny.md"
EXPECTED_BLOCKS = 2

MIXED = "if True:\n\tpass\n        pass\n"  # a tab, then eight spaces
CLEAN = "if True:\n    pass\n"
# Consistent at tab sizes 1 and 8, so it compiles, but not nested at tab size 2.
AMBIGUOUS = "if x:\n  \tif y:\n \t  pass\n"


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


def clean_lines(count: int) -> list[str]:
    """`count` clean lines, alternating an `if` and its indented body."""
    return ["if True:\n", "    pass\n"] * (count // 2)


def run_tokens(lines: list[str]) -> None:
    tabnanny.process_tokens(tokenize.generate_tokens(iter(lines).__next__))


def check_output(path: pathlib.Path | str) -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert tabnanny.check(str(path)) is None
    return output.getvalue()


@pytest.fixture
def in_tmp_path(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Work under relative names: `check()` quotes a printed path containing a space."""
    monkeypatch.chdir(tmp_path)


class CountingReadline:
    """A `readline` that records how many lines have been taken from it."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = iter(lines)
        self.taken = 0

    def __call__(self) -> str:
        self.taken += 1
        return next(self._lines, "")


class TestProcessTokensStopsAtTheFirstProblem:
    """`process_tokens(tokens)` | O(t) | raises `NannyNag` at the first
    problem and takes no more."""

    def test_it_reads_only_up_to_the_offending_line(self) -> None:
        lines: list[str] = [*MIXED.splitlines(keepends=True), *["x = 1\n"] * 100_000]
        readline = CountingReadline(lines)

        with pytest.raises(tabnanny.NannyNag) as caught:
            tabnanny.process_tokens(tokenize.generate_tokens(readline))

        assert caught.value.get_lineno() == 3
        assert readline.taken == 3, f"took {readline.taken} lines to find a problem on line 3"

    def test_it_takes_no_token_after_the_one_it_raises_on(self) -> None:
        tokens = list(tokenize.generate_tokens(io.StringIO(AMBIGUOUS + "x = 1\n" * 100).readline))
        taken: list[tokenize.TokenInfo] = []

        def counting() -> Iterator[tokenize.TokenInfo]:
            for token in tokens:
                taken.append(token)
                yield token

        with pytest.raises(tabnanny.NannyNag, match="indent not greater"):
            tabnanny.process_tokens(counting())

        assert taken[-1].type == tokenize.INDENT
        assert taken[-1].start[0] == 3


class TestNannyNag:
    """`NannyNag` carries the line number, message and line it was built with."""

    def test_the_accessors_return_what_was_stored(self) -> None:
        nag = tabnanny.NannyNag(7, "message", "line\n")

        assert (nag.get_lineno(), nag.get_msg(), nag.get_line()) == (7, "message", "line\n")
        assert isinstance(nag, Exception)


class TestSpaceFollowsTheLineAndTheDepth:
    """`check()` | O(d + l) space: neither the file's length nor its line
    count, but the longest line or token and the open indents."""

    def test_line_count_does_not_raise_the_peak(self) -> None:
        run_tokens(clean_lines(1_000))  # compile the tokenizer's patterns outside the measurement
        peaks = []
        for count in (1_000, 10_000, 100_000):
            lines = clean_lines(count)
            peaks.append(peak_bytes(lambda lines=lines: run_tokens(lines)))

        assert max(peaks) < 100_000, f"clean lines peaked at {peaks}"
        assert max(peaks) < min(peaks) * 2, f"100x the lines moved the peak: {peaks}"

    @pytest.mark.parametrize("shape", ["one line", "triple-quoted"])
    def test_the_longest_token_is_held_whole(self, shape: str) -> None:
        size = 1_000_000
        if shape == "one line":
            lines = ["x = '" + "a" * size + "'\n"]
        else:
            lines = ['x = """\n', *["a" * 9 + "\n"] * (size // 10), '"""\n']

        peak = peak_bytes(lambda: run_tokens(lines))

        assert peak > size, f"a {size}-character {shape} token peaked at {peak} bytes"

    @staticmethod
    def nested(depth: int) -> list[tokenize.TokenInfo]:
        tokens = []
        for level in range(1, depth + 1):
            line = " " * level + "x\n"
            tokens.append(
                tokenize.TokenInfo(tokenize.INDENT, " " * level, (level, 0), (level, level), line)
            )
        return tokens

    def test_open_indents_are_held(self) -> None:
        peaks = []
        for depth in (20, 2_000):
            tokens = self.nested(depth)
            peaks.append(peak_bytes(lambda tokens=tokens: tabnanny.process_tokens(iter(tokens))))

        assert peaks[1] > peaks[0] * 20, f"100x the depth: {peaks}"


class TestTimeIsLinearInTheSource:
    """`check()` | O(c), timed through `process_tokens()`: each 10x step in
    clean lines of fixed length costs about 10x."""

    @pytest.mark.timing
    def test_ten_times_the_lines_costs_about_ten_times(self) -> None:
        durations = []
        for count in (2_000, 20_000, 200_000):
            lines = clean_lines(count)
            durations.append(best_ns(lambda lines=lines: run_tokens(lines)))

        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]
        assert all(5 < ratio < 20 for ratio in ratios), (
            f"10x steps cost {[f'x{ratio:.1f}' for ratio in ratios]} ({durations} ns); "
            "linear gives about x10, quadratic about x100"
        )


class TestCheckReportsOnStdout:
    """`check(file)` prints the first problem in each file and returns `None`."""

    pytestmark = pytest.mark.usefixtures("in_tmp_path")

    @pytest.fixture(autouse=True)
    def _restore_switches(self) -> Iterator[None]:
        saved = tabnanny.verbose, tabnanny.filename_only
        yield
        tabnanny.verbose, tabnanny.filename_only = saved

    def test_a_problem_prints_the_path_line_and_text(self) -> None:
        path = pathlib.Path("mixed.py")
        path.write_text(MIXED)

        output = check_output(path)

        assert output.startswith(f"{path} 3 ")
        assert output.count("\n") == 1
        assert "pass" in output

    def test_a_clean_file_prints_nothing(self) -> None:
        path = pathlib.Path("clean.py")
        path.write_text(CLEAN)

        assert check_output(path) == ""

    def test_only_the_first_problem_is_reported(self) -> None:
        path = pathlib.Path("twice.py")
        path.write_text(MIXED + MIXED.replace("True", "False"))

        output = check_output(path)

        assert output.count("\n") == 1
        assert f"{path} 3 " in output

    def test_filename_only_prints_just_the_path(self) -> None:
        path = pathlib.Path("mixed.py")
        path.write_text(MIXED)
        tabnanny.filename_only = 1

        assert check_output(path) == f"{path}\n"

    def test_verbose_explains_the_problem(self) -> None:
        path = pathlib.Path("mixed.py")
        path.write_text(MIXED)
        tabnanny.verbose = 1

        output = check_output(path)

        assert "Line 3" in output
        assert output.count("\n") == 3

    def test_a_path_given_directly_is_checked_whatever_its_suffix(self) -> None:
        path = pathlib.Path("notes.txt")
        path.write_text(MIXED)

        assert check_output(path).startswith(f"{path} 3 ")


class TestTheDirectoryWalk:
    """`check()` on a directory | O(e + c) | O(e + d + l): descends real
    subdirectories and checks `.py` names, holding each listing."""

    pytestmark = pytest.mark.usefixtures("in_tmp_path")

    def test_what_the_walk_visits(self) -> None:
        root = pathlib.Path("tree")
        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "nested.py").write_text(MIXED)
        (root / "real").mkdir()
        (root / "real" / "linked.py").write_text(MIXED)
        (root / "link").symlink_to("real")
        (root / "alias.py").symlink_to(pathlib.Path("pkg") / "nested.py")
        (root / "notes.txt").write_text(MIXED)

        reported = {line.split(" ")[0] for line in check_output(root).splitlines()}

        expected = {
            str(root / "pkg" / "nested.py"),
            str(root / "real" / "linked.py"),
            str(root / "alias.py"),
        }
        assert reported == expected

    def test_the_listing_is_held(self) -> None:
        peaks = []
        for count in (20, 20_000):
            root = pathlib.Path(str(count))
            root.mkdir()
            for index in range(count):
                (root / f"entry{index:05d}.txt").touch()
            peaks.append(peak_bytes(lambda root=root: check_output(root)))

        assert peaks[1] > peaks[0] * 20, f"1,000x the entries: {peaks}"


def _write_deep(path: pathlib.Path, depth: int) -> None:
    body = "".join("    " * level + "if x:\n" for level in range(depth))
    path.write_text(body + "    " * depth + "pass\n")


class TestErrorsEndTheCheck:
    """Version Notes: from 3.12 an unreadable or untokenizable file raises
    `SystemExit(1)` from `check()`; before, `check()` returns `None`."""

    @pytest.fixture(params=["missing", "syntax", "too deep"])
    def broken(self, request: pytest.FixtureRequest, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "broken.py"
        if request.param == "syntax":
            path.write_text("def f(:\n    pass\n")
        elif request.param == "too deep":
            _write_deep(path, 100)
        return path

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="exits from 3.12")
    def test_it_exits_from_312(self, broken: pathlib.Path) -> None:
        with (
            contextlib.redirect_stderr(io.StringIO()) as errors,
            pytest.raises(SystemExit) as caught,
        ):
            tabnanny.check(str(broken))

        assert caught.value.code == 1
        assert "broken.py" in errors.getvalue()

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="returns before 3.12")
    def test_it_returns_before_312(self, broken: pathlib.Path) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            assert tabnanny.check(str(broken)) is None

    def test_one_level_less_is_clean(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "deep.py"
        _write_deep(path, 99)

        assert check_output(path) == ""


class TestWhatTabnannyCatches:
    """Version Notes: from 3.12 a tab mix that raises `TabError` is reported
    with the tokenizer's message; a mix that compiles but changes meaning at
    another tab size is reported by tabnanny's own check on every version."""

    @staticmethod
    def nag(source: str) -> tabnanny.NannyNag:
        with pytest.raises(tabnanny.NannyNag) as caught:
            tabnanny.process_tokens(tokenize.generate_tokens(io.StringIO(source).readline))
        return caught.value

    def test_a_tab_error_is_caught(self) -> None:
        with pytest.raises(TabError):
            compile(MIXED, "<mixed>", "exec")

        message = self.nag(MIXED).get_msg()

        if sys.version_info >= (3, 12):
            assert message == "inconsistent use of tabs and spaces in indentation"
        else:
            assert message.startswith("indent not equal")

    def test_indentation_that_compiles_is_still_caught(self) -> None:
        compile(AMBIGUOUS, "<ambiguous>", "exec")

        nag = self.nag(AMBIGUOUS)

        assert nag.get_lineno() == 3
        assert nag.get_msg() == "indent not greater e.g. at tab size 2"


class TestCommandLine:
    """`python -m tabnanny` prints problems and exits 0; `-q` prints paths
    only and `-v` explains each problem."""

    pytestmark = pytest.mark.usefixtures("in_tmp_path")

    @staticmethod
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tabnanny", *args],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

    def test_a_problem_still_exits_zero(self) -> None:
        path = pathlib.Path("mixed.py")
        path.write_text(MIXED)

        result = self.run(str(path))

        assert result.returncode == 0
        assert result.stdout.startswith(f"{path} 3 ")

    def test_q_prints_only_the_path(self) -> None:
        path = pathlib.Path("mixed.py")
        path.write_text(MIXED)

        assert self.run("-q", str(path)).stdout == f"{path}\n"

    def test_v_explains_the_problem(self) -> None:
        path = pathlib.Path("mixed.py")
        path.write_text(MIXED)

        assert "Line 3" in self.run("-v", str(path)).stdout


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
    """Each block runs in its own subprocess and working directory, and
    asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "lines.tell() < 100" in s)
        mutated = source.replace("lines.tell() < 100", "lines.tell() > 100", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
