"""Tests for docs/builtins/str_func.md.

The page prices `str()` by what it hands back: an exact `str` is returned
itself, numbers other than ints convert to short fixed-size text, a container
builds the text of its elements' `repr()`, and bytes are either shown as their
`repr()` or decoded. Identity, call counters and string lengths settle most of
those without tolerance; the copy each level of nesting makes and the linear
decode are timed, and the space of nested text is a traced peak.

Measurement scope:

* `str(s)` is asserted to return `s` for an exact 1,000,000-character string
  built at run time, and a new, equal, exact `str` for an instance of a `str`
  subclass. `str()` is asserted to return the empty string.
* `len(str(f))` is asserted at most 24 for 200,000 floats drawn from random
  bit patterns (seeded), and for the extremes of the float range, signed.
* A list, tuple, dict and set of 1,000 objects that count their `__repr__()`
  and `__str__()` calls: `str()` makes exactly one `__repr__()` call per
  element (keys and values both, for the dict) and no `__str__()` call.
* Nesting: a 1,000,000-character string wrapped in 768 nested lists must
  cost more than 5x a flat list of 256 strings of 3,900 characters, whose text
  is about the same length (locally about 70x), so the cost follows depth at a
  fixed result length. The traced peak of `str()` on the string wrapped 1, 64
  and 256 deep is asserted under 4x the result's length in bytes each time
  (locally about 2.3x), where copies held at every level would need 64x and
  256x.
* `str(b)` without an encoding is asserted equal to `repr(b)` for `bytes` and
  `bytearray`. `str(b, "utf-8")` is asserted equal to `b.decode("utf-8")`,
  and is timed on UTF-8 text of 100,000, 1,000,000 and 10,000,000 bytes of
  two-byte characters: each 10x step must cost more than 4x and less than 50x
  (linear predicts 10x, quadratic 100x; the band would also admit growth near
  n^1.5, so the linear bound itself rests on the official table). A `str` argument with an encoding raises
  `TypeError`.
* A custom `__str__()` is asserted to be called exactly once per `str()`,
  `__repr__()` to supply the text when the class has no `__str__()`, and a
  `__str__()` returning an int to raise `TypeError`.
* A logger at `WARNING` makes no `__str__()` call for an `info()` message
  whose value is passed as an argument, and one call when a handler emits a
  `warning()` built the same way.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Settled elsewhere:

* The int row - O(d²), the subquadratic path from 3.12, and the
  `sys.get_int_max_str_digits()` limit covering `str()`, `repr()` and
  `format()` - is tested in tests/test_int_complexity.py.
* That `str()` of a `str` makes no copy while encoding does is also asserted
  in tests/test_builtin_claims.py.

Not settled here:

* The decode row assumes a codec that does a constant amount of work per
  byte; only UTF-8 was timed. The copy per level of nesting was timed for
  lists only; tuples, dicts and sets build their text the same way in
  Objects/tupleobject.c, Objects/dictobject.c and Objects/setobject.c.
* Element `repr()` cost was held small; an element whose `repr()` is
  expensive adds its own cost, which the row names rather than prices.
"""

from __future__ import annotations

import logging
import pathlib
import random
import re
import struct
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "str_func.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
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


class Counted:
    """An element that counts its `__repr__()` and `__str__()` calls."""

    reprs = 0
    strs = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Counted) and self.value == other.value

    def __repr__(self) -> str:
        type(self).reprs += 1
        return "r"

    def __str__(self) -> str:
        type(self).strs += 1
        return "s"


class TestAStrIsReturnedUnchanged:
    """`str(s)` on an exact `str` | O(1) | Returns `s` itself; a subclass
    instance is copied into a new exact `str`.

    Identity separates returning the argument from copying it.
    """

    def test_an_exact_str_is_the_same_object(self) -> None:
        text = "x" * 1_000_000 + str(id(object()))
        assert str(text) is text

    def test_a_subclass_instance_is_copied(self) -> None:
        class Label(str):
            pass

        label = Label("y" * 1_000)
        plain = str(label)
        assert type(plain) is str and plain == label and plain is not label

    def test_no_argument_gives_the_empty_string(self) -> None:
        assert str() == ""  # noqa: UP018 - the call itself is the subject


class TestFloatsAreShort:
    """`str(x)` for a `float` | O(1) | At most 24 characters."""

    def test_random_bit_patterns(self) -> None:
        rng = random.Random(20261016)
        longest = 0
        for _ in range(200_000):
            value = struct.unpack("d", rng.randbytes(8))[0]
            longest = max(longest, len(str(value)))
        assert longest <= 24, longest

    @pytest.mark.parametrize(
        "value",
        [sys.float_info.max, sys.float_info.min, 5e-324, -2.2250738585072014e-308, 1 / 3],
    )
    def test_extremes(self, value: float) -> None:
        assert len(str(value)) <= 24 and len(str(-value)) <= 24


class TestContainersUseRepr:
    """`str(c)` for a container calls `repr()`, not `str()`, on each element,
    once each."""

    @pytest.mark.parametrize("kind", ["list", "tuple", "dict", "set"])
    def test_each_element_is_reprd_once(self, kind: str) -> None:
        items = [Counted(i) for i in range(1_000)]
        containers: dict[str, Any] = {
            "list": items,
            "tuple": tuple(items),
            "dict": dict(zip(items, [Counted(-1 - i) for i in range(1_000)], strict=True)),
            "set": set(items),
        }
        container = containers[kind]
        expected = 2_000 if kind == "dict" else 1_000
        Counted.reprs = Counted.strs = 0
        str(container)
        assert (Counted.reprs, Counted.strs) == (expected, 0)


def _nested(leaf: object, depth: int) -> object:
    for _ in range(depth):
        leaf = [leaf]
    return leaf


class TestNestingCopiesInnerText:
    """`str(c)` | O(L × h) time, O(L) space: each level of nesting copies the
    text of the levels inside it once more, and the text held at once stays
    within a constant multiple of the result's length.

    A deep chain and a flat list with text of about the same length separate
    a cost in the result's length from one in its depth.
    """

    LEAF = "a" * 1_000_000

    @pytest.mark.timing
    def test_depth_costs_more_than_breadth(self) -> None:
        deep = _nested(self.LEAF, 768)
        flat = ["a" * 3_900] * 256
        assert abs(len(str(deep)) - len(str(flat))) < 5_000
        deep_ns = best_ns(lambda: str(deep), repeats=5)
        flat_ns = best_ns(lambda: str(flat))
        assert deep_ns > flat_ns * 5, f"deep {deep_ns:.0f}ns, flat {flat_ns:.0f}ns"

    @pytest.mark.parametrize("depth", [1, 64, 256])
    def test_space_follows_the_result_not_the_depth(self, depth: int) -> None:
        value = _nested(self.LEAF, depth)
        result_length = len(str(value))
        peak = peak_bytes(lambda: str(value))
        assert peak < result_length * 4, f"depth {depth}: peak {peak}, length {result_length}"


class TestBytes:
    """`str(b)` is the `repr()`; `str(b, encoding)` decodes in O(n)."""

    @pytest.mark.parametrize("data", [b"caf\xc3\xa9", bytearray(b"caf\xc3\xa9")])
    def test_no_encoding_gives_the_repr(self, data: bytes | bytearray) -> None:
        assert str(data) == repr(data)

    def test_an_encoding_decodes(self) -> None:
        data = "café".encode()
        assert str(data, "utf-8") == data.decode("utf-8") == "café"

    def test_a_str_cannot_be_decoded(self) -> None:
        with pytest.raises(TypeError):
            str("café", "utf-8")  # pyright: ignore[reportArgumentType]

    @pytest.mark.timing
    def test_decoding_is_linear(self) -> None:
        sizes = [100_000, 1_000_000, 10_000_000]
        payloads = [("é" * (size // 2)).encode() for size in sizes]
        times = [best_ns(lambda p=p: str(p, "utf-8")) for p in payloads]
        for small, large in zip(times, times[1:], strict=False):
            assert 4 < large / small < 50, f"times {times}"


class TestCustomStr:
    """`str(obj)` costs one `__str__()` call; `__repr__()` is the fallback,
    and a non-`str` result raises `TypeError`."""

    def test_str_is_called_once(self) -> None:
        Counted.strs = 0
        assert str(Counted(1)) == "s"
        assert Counted.strs == 1

    def test_repr_is_the_fallback(self) -> None:
        class OnlyRepr:
            def __repr__(self) -> str:
                return "only"

        assert str(OnlyRepr()) == "only"

    def test_a_non_str_result_raises(self) -> None:
        class Broken:
            def __str__(self) -> Any:
                return 42

        with pytest.raises(TypeError):
            str(Broken())


class FormattingHandler(logging.Handler):
    """A handler that formats each record it emits and keeps the text."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


class TestLoggingDefersConversion:
    """Passing a value as a logging argument defers `str()` until a handler
    emits the record."""

    def test_a_disabled_message_converts_nothing_and_an_emitted_one_converts_once(
        self,
    ) -> None:
        logger = logging.getLogger("test_str_func_complexity")
        level, propagate = logger.level, logger.propagate
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        handler = FormattingHandler()
        logger.addHandler(handler)
        try:
            Counted.strs = 0
            logger.info("value: %s", Counted(1))
            assert Counted.strs == 0
            logger.warning("value: %s", Counted(1))
            assert Counted.strs == 1
            assert handler.messages == ["value: s"]
        finally:
            logger.removeHandler(handler)
            logger.setLevel(level)
            logger.propagate = propagate


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        target = "assert str(text) is text"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert str(text) is not text", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
