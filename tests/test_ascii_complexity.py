"""Tests for docs/builtins/ascii.md.

ascii() is PyObject_ASCII in Objects/object.c: PyObject_Repr(x), then, unless
the result is already pure ASCII, one "backslashreplace" encode of the whole
result to bytes and one decode back to str. An ASCII-only repr is returned as
the very object `__repr__` produced. The function is identical in the v3.10.19,
v3.11.14, v3.12.12, v3.13.11 and v3.14.2 tags, so no version is treated apart.

The single pass over the whole repr is read from that source. Observation
pins what it produces, without a stopwatch:

* the result equals `repr(x).encode("ascii", "backslashreplace").decode()`
  for a list, a dict and a custom object - the whole repr escaped once, with
  each element's repr() and not its ascii();
* a counting `__repr__` is called once per call, and once per element inside
  a container;
* an ASCII-only `__repr__` result comes back as the same object, so nothing
  is copied, while a non-ASCII one comes back as a new string;
* the output is never more than ten characters per input character plus the
  two quotes, which bounds the escaping pass's allocation by O(n) / O(r).
  What `__repr__` allocates on the way is its own cost, and is not measured.

The string rows need elapsed time. A hundredfold step in length (10,000 to
1,000,000 characters) measured x102 for ASCII, x130 for U+00E9, x127 for
U+65E5 and x143 for U+1F600 on the pinned interpreter (aarch64, CPython 3.14).
The test accepts x20 to x1,000: a constant-time claim predicts x1 and a
quadratic one x10,000. Not varied: the mix of escape widths within one string,
and container nesting depth, whose cost is repr()'s and belongs to the
container's page.

The fixed 4/6/10 escape widths are pinned in tests/test_builtin_claims.py.
"""

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "ascii.md"

SMALL = 10_000
LARGE = 1_000_000


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 5) -> float:
    """The fastest of several runs of `loops` calls, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times) / loops


def escaped(text: str) -> str:
    """What one backslashreplace pass over `text` produces."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


class Fixed:
    """An object whose repr is a fixed string, counting the calls."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def __repr__(self) -> str:
        self.calls += 1
        return self.text


class TestStrings:
    """The ASCII string and Unicode string rows."""

    @pytest.mark.parametrize("char", ["a", "\xe9", "日", "\U0001f600"])
    def test_time_is_linear_in_the_length(self, char: str) -> None:
        small = char * SMALL
        large = char * LARGE
        ascii(large)  # warm up

        ratio = best_time(lambda: ascii(large)) / best_time(lambda: ascii(small), loops=100)

        assert 20 < ratio < 1_000, f"x{ratio:.1f} for x{LARGE // SMALL} in length"

    @pytest.mark.parametrize("char", ["a", "\xe9", "日", "\U0001f600", "\x00"])
    def test_output_is_at_most_ten_characters_per_input_character(self, char: str) -> None:
        text = char * 1_000

        assert len(ascii(text)) <= 10 * len(text) + 2

    def test_each_non_ascii_character_gets_its_own_escape(self) -> None:
        text = "Hello, 世界"

        assert ascii(text) == "'Hello, \\u4e16\\u754c'"
        assert ascii(text) == escaped(repr(text))

    def test_the_result_is_always_ascii(self) -> None:
        text = "".join(map(chr, range(0, 0x110000, 97)))

        assert ascii(text).isascii()


class TestContainers:
    """The container row: repr(x) plus one escaping pass of O(r)."""

    def test_the_whole_repr_is_escaped_once(self) -> None:
        values: list[Any] = [
            ["caf\xe9", "日本", "\U0001f600", "plain"],
            {"cl\xe9": "valeur €"},
            ("\xd1", ["ā", {"\U0001f3b5"}]),
        ]
        for value in values:
            assert ascii(value) == escaped(repr(value))

    def test_each_element_repr_is_called_once(self) -> None:
        items = [Fixed("x\xe9"), Fixed("y"), Fixed("日")]

        result = ascii(items)

        assert result == "[x\\xe9, y, \\u65e5]"
        assert [item.calls for item in items] == [1, 1, 1]

    def test_output_is_bounded_by_the_repr_length(self) -> None:
        value = {"\U0001f600" * 50: ["\xe9" * 50, "日" * 50]}

        assert len(ascii(value)) <= 10 * len(repr(value))


class TestCustomObjects:
    """The custom-object row: `__repr__` plus O(r)."""

    def test_repr_is_called_once(self) -> None:
        obj = Fixed("<\xe9>")

        assert ascii(obj) == "<\\xe9>"
        assert obj.calls == 1

    def test_an_ascii_repr_is_returned_as_is(self) -> None:
        text = "x" * LARGE
        obj = Fixed(text)

        assert ascii(obj) is text

    def test_a_non_ascii_repr_is_escaped_into_a_new_string(self) -> None:
        text = "\xe9" * 1_000
        obj = Fixed(text)

        result = ascii(obj)

        assert result is not text
        assert result == "\\xe9" * 1_000

    def test_only_non_ascii_characters_are_escaped(self) -> None:
        """Quotes and backslashes in a custom repr pass through; no quotes are added."""
        assert ascii(Fixed("'\xe9\\")) == "'\\xe9\\"

    def test_a_non_str_repr_is_rejected(self) -> None:
        class Bad:
            def __repr__(self) -> Any:
                return 42

        with pytest.raises(TypeError):
            ascii(Bad())


class TestStatedExampleValues:
    """The results the page writes in comments."""

    def test_basic_usage(self) -> None:
        assert ascii("hello") == "'hello'"
        assert ascii("Python") == "'Python'"
        assert ascii("123") == "'123'"
        assert ascii("caf\xe9") == "'caf\\xe9'"
        assert ascii("\U0001f3b5") == "'\\U0001f3b5'"
        assert ascii("\xd1o\xf1o") == "'\\xd1o\\xf1o'"
        assert ascii("日本語") == "'\\u65e5\\u672c\\u8a9e'"

    def test_escape_sequences(self) -> None:
        assert ascii("\xe9") == "'\\xe9'"
        assert ascii("ā") == "'\\u0101'"
        assert ascii("\U0001f600") == "'\\U0001f600'"
        assert len(ascii("\xe9" * 100)) == 100 * 4 + 2

    def test_repr_escapes_control_characters_quotes_and_backslashes(self) -> None:
        assert ascii("\x7f") == "'\\x7f'"
        assert ascii("a\\b") == "'a\\\\b'"
        assert ascii("it's") == '"it\'s"'

    def test_debugging(self) -> None:
        text = "Hello\nWorld\t!"
        assert ascii(text) == "'Hello\\nWorld\\t!'"
        assert repr(text) == "'Hello\\nWorld\\t!'"
        assert str(text) is text
        assert repr("H\xe9llo") == "'H\xe9llo'"
        assert ascii("H\xe9llo") == "'H\\xe9llo'"

    def test_limited_charsets_and_paths(self) -> None:
        assert ascii("Caf\xe9: 100€") == "'Caf\\xe9: 100\\u20ac'"
        assert ascii("documento_espa\xf1a.txt") == "'documento_espa\\xf1a.txt'"
        assert ascii("/home/用户/文件.txt") == "'/home/\\u7528\\u6237/\\u6587\\u4ef6.txt'"

    def test_special_cases(self) -> None:
        assert ascii("") == "''"
        assert ascii("abc123!@#") == "'abc123!@#'"


EXPECTED_BLOCKS = 13


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        patterns = next(source for _, source in _blocks() if "make_ascii_safe" in source)
        broken = patterns.replace("def make_ascii_safe", "def renamed", 1)
        assert broken != patterns, "the mutation did not rename the function"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
