"""Tests for docs/stdlib/pickletools.md.

The page prices every function as one walk over the pickle's bytes, opcode by
opcode, and `dis()` additionally by the indentation it writes for open MARKs.
Laziness and what `genops()` reads are settled by a reader that counts the
bytes it hands out; space by traced allocation with a sink that keeps no
output; the p·d term of `dis()` by the length of what it writes, which is a
lower bound on its work; and `optimize()` by the opcodes of its result and a
timing test.

Measurement scope:

* `genops()` over a counting reader takes nothing at construction, 2 bytes
  for the first step of a protocol 4 pickle, and exactly the pickle's bytes
  over a full iteration, stopping at the first `STOP` with a second pickle
  unread behind it; over a protocol 0 pickle it calls `readline()` once per
  newline-terminated argument and takes the same total. Draining it over a 100,000-element tuple (369 KB) peaks
  under 5 KB, and over one 10 MB `bytes` argument above 10 MB, which is the a
  term. `pos` is asserted `None` for a reader without `tell()`.
* `dis()` with a sink that keeps nothing peaks more than 5x higher over a
  100,000-element tuple than over a 10,000-element one (its emulated stack),
  and the same holds for a list of 100,000 strings against 10,000 (its memo).
  Its memo is asserted to hold `pickletools.pyunicode` placeholders rather
  than the pickled strings.
* The p·d term is the output length. Nested four-element tuples 100 and 800
  levels deep give pickles 8x apart in bytes; with the default indent the
  output grows more than 40x, and with `indentlevel=0` less than 10x. A flat
  list of 10,000 and of 100,000 ints gives output 8x to 12x apart.
* `dis()` is asserted to raise `ValueError` on a truncated pickle, an unknown
  opcode, a `POP` from an empty stack, a `GET` of an unstored memo key, and a
  5,001-digit `LONG4` integer with the digit limit set to its default of
  4,300, and to print that integer once `sys.set_int_max_str_digits(0)` lifts
  the limit; `genops()` reads the same pickle. A shared `memo` dict is
  asserted to carry an entry from one pickle to the next pickle a `Pickler`
  wrote. A pickle that stores into memo key 0 twice raises on 3.10 to 3.13 and
  disassembles on 3.14+, guarded on `sys.version_info`.
* `optimize()` is asserted to drop every `MEMOIZE` from a pickle with no
  shared object, to keep one store and one `BINGET` for an object referenced
  twice, to number the stores it keeps from 0, to keep protocol 4 framing on
  a pickle over the frame size with frame lengths other than the input's,
  to produce pickles that load to equal
  objects, and to raise `TypeError` on a file object. Time is a timing test
  over lists of 10,000, 40,000 and 160,000 strings: each 4x step costs under
  8x.
* The command line is run in a subprocess on two pickles written by one
  `Pickler`: with `-m` the second disassembles and each is headed by the
  preamble; without it the second fails; `-l 0`, `-a` and `-o` are asserted
  by the output they produce.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `dis()` does no more than O(n + p·d) work is read from
  Lib/pickletools.py: one `genops()` pass, amortized O(1) stack emulation per
  opcode (every item popped was pushed once), and one line per opcode whose
  length is the argument's `repr()` plus the indentation. The tests show the
  p·d term is reached, not that nothing larger is.
* Printing an offset is priced O(1); its width grows with log n, which the
  page's cost model leaves out, as it leaves out integer formatting under
  the digit limit. The page's digit-limit example assumes the default limit.
* Argument decoding is priced by its bytes. Protocol 0 `LONG` arguments go
  through `int()` on decimal text, which is superlinear in the digits but
  capped by the integer digit limit; that path is not measured.
* The opcode tables and readers (`opcodes`, `code2op`, `OpcodeInfo`,
  `ArgumentDescriptor`, `StackObject`, the `read_*` functions and their
  descriptor instances) are outside `__all__` and the official
  documentation. The audit lists them for classification; the page prices
  only `dis`, `genops` and `optimize`.
* Only CPython-written pickles and a few hand-built ones are measured;
  pickles with out-of-band buffers and protocol 0 text opcodes other than the
  ones above are not varied.
* The 3.12 display of `STRING` arguments with `ascii()` and the 3.14 command
  line's removal of `-t` and `-v` change output or options, not a bound, and
  are not asserted.
"""

from __future__ import annotations

import io
import pathlib
import pickle
import pickletools
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterable
from typing import IO, Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pickletools.md"
EXPECTED_BLOCKS = 7


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


def drain(items: Iterable[Any]) -> None:
    for _ in items:
        pass


def counted(reader: CountingReader) -> IO[bytes]:
    """The counting reader, typed as the binary file `genops()` accepts."""
    return cast("IO[bytes]", reader)


def names(data: bytes) -> list[str]:
    return [op.name for op, _arg, _pos in pickletools.genops(data)]


def disassemble(data: bytes | io.BytesIO, **kwargs: Any) -> str:
    out = io.StringIO()
    pickletools.dis(data, out=out, **kwargs)
    return out.getvalue()


def nested_tuples(depth: int) -> bytes:
    """Four-element tuples, each built between a MARK and a TUPLE."""
    value: tuple[Any, ...] = (1, 2, 3, 4)
    for _ in range(depth):
        value = (value, 1, 2, 3)
    return pickle.dumps(value, protocol=4)


class NullSink(io.StringIO):
    """A text sink that keeps nothing."""

    def write(self, s: str, /) -> int:
        return len(s)


class CountingReader:
    """A binary reader that records how many bytes it has handed out."""

    def __init__(self, data: bytes, *, tell: bool = True) -> None:
        self._stream = io.BytesIO(data)
        self.given = 0
        self.lines = 0
        if tell:
            self.tell = self._stream.tell

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        self.given += len(chunk)
        return chunk

    def readline(self) -> bytes:
        chunk = self._stream.readline()
        self.given += len(chunk)
        self.lines += 1
        return chunk


class TestGenopsIsLazy:
    """`genops(pickle)` | O(1) to build; iterating it | O(a) per opcode, O(n)
    in all | O(a).

    A counting reader separates a generator that reads one opcode per step
    from one that reads the pickle up front, and traced allocation separates
    O(a) from O(n) space.
    """

    DATA = pickle.dumps({"name": "Alice", "age": 30}, protocol=4)

    def test_building_it_reads_nothing(self) -> None:
        reader = CountingReader(self.DATA)

        pickletools.genops(counted(reader))

        assert reader.given == 0

    def test_one_step_reads_one_opcode_and_its_argument(self) -> None:
        reader = CountingReader(self.DATA)

        opcode, arg, pos = next(pickletools.genops(counted(reader)))

        assert (opcode.name, arg, pos) == ("PROTO", 4, 0)
        assert reader.given == 2

    def test_a_full_pass_reads_the_pickle_once_and_stops_at_stop(self) -> None:
        second = pickle.dumps([1, 2], protocol=4)
        reader = CountingReader(self.DATA + second)

        ops = [op.name for op, _arg, _pos in pickletools.genops(counted(reader))]

        assert ops[-1] == "STOP" and ops.count("STOP") == 1
        assert reader.given == len(self.DATA)
        assert names(second)[-1] == "STOP"

    def test_protocol_0_text_arguments_are_read_one_line_each(self) -> None:
        data = pickle.dumps([1, "text", (2, 3)], protocol=0)
        reader = CountingReader(data)

        drain(pickletools.genops(counted(reader)))

        assert reader.given == len(data)
        newline_args = [
            op
            for op, _arg, _pos in pickletools.genops(data)
            if op.arg is not None and op.arg.n == pickletools.UP_TO_NEWLINE
        ]
        assert len(newline_args) >= 4
        assert reader.lines == len(newline_args)

    def test_pos_is_none_without_tell(self) -> None:
        positions = [
            pos
            for _op, _arg, pos in pickletools.genops(counted(CountingReader(self.DATA, tell=False)))
        ]

        assert positions and all(pos is None for pos in positions)
        assert [pos for _op, _arg, pos in pickletools.genops(self.DATA)][:2] == [0, 2]

    def test_iterating_holds_one_argument_not_the_pickle(self) -> None:
        data = pickle.dumps(tuple(range(100_000)), protocol=4)
        drain(pickletools.genops(data))

        peak = peak_bytes(lambda: drain(pickletools.genops(data)))

        assert peak < 5_000, f"draining genops over {len(data)} bytes peaked at {peak}"

    def test_a_large_argument_is_held_whole(self) -> None:
        data = pickle.dumps(b"x" * 10_000_000, protocol=4)

        peak = peak_bytes(lambda: drain(pickletools.genops(data)))

        assert peak > 10_000_000, f"a 10 MB argument peaked at {peak}"


class TestDisSpace:
    """`dis()` | O(p + a) space: an emulated stack and memo of placeholders.

    A sink that keeps nothing removes the output from the measurement, so what
    remains grows with the opcodes that push or store.
    """

    @staticmethod
    def _peak(data: bytes) -> int:
        pickletools.dis(data, out=NullSink())
        return peak_bytes(lambda: pickletools.dis(data, out=NullSink()))

    def test_the_emulated_stack_grows_with_the_opcodes(self) -> None:
        small = self._peak(pickle.dumps(tuple(range(10_000)), protocol=4))
        large = self._peak(pickle.dumps(tuple(range(100_000)), protocol=4))

        assert large > 5 * small, f"10x the tuple: {small} -> {large} bytes"

    def test_the_emulated_memo_grows_with_the_stores(self) -> None:
        small = self._peak(pickle.dumps([str(i) for i in range(10_000)], protocol=4))
        large = self._peak(pickle.dumps([str(i) for i in range(100_000)], protocol=4))

        assert large > 5 * small, f"10x the stores: {small} -> {large} bytes"

    def test_the_memo_holds_placeholders_not_objects(self) -> None:
        memo: dict[int, Any] = {}

        pickletools.dis(pickle.dumps(["x" * 1_000], protocol=4), out=NullSink(), memo=memo)

        assert memo[1] is pickletools.pyunicode
        assert isinstance(memo[1], pickletools.StackObject)


class TestDisOutputFollowsMarkDepth:
    """`dis()` | O(n + p·d): each line is indented `indentlevel` spaces per
    open MARK, so `indentlevel=0` drops the p·d term.

    Pickles of nested four-element tuples 100 and 800 levels deep are 8x
    apart in bytes; linear output would also be 8x apart, and output that
    carries the p·d term is 64x apart in the limit.
    """

    def test_nesting_grows_the_output_faster_than_the_pickle(self) -> None:
        shallow, deep = nested_tuples(100), nested_tuples(800)
        size_ratio = len(deep) / len(shallow)

        indented = len(disassemble(deep)) / len(disassemble(shallow))
        flat = len(disassemble(deep, indentlevel=0)) / len(disassemble(shallow, indentlevel=0))

        assert 7 < size_ratio < 9
        assert indented > 40, f"8x deeper: output grew {indented:.1f}x"
        assert flat < 10, f"8x deeper without indentation: output grew {flat:.1f}x"

    def test_a_line_is_indented_by_its_open_marks(self) -> None:
        output = disassemble(nested_tuples(50))

        assert "K    " + " " * 4 * 51 + "BININT1" in output
        assert "K    BININT1" in disassemble(nested_tuples(50), indentlevel=0)

    def test_a_flat_pickle_gives_output_linear_in_its_opcodes(self) -> None:
        small = disassemble(pickle.dumps(list(range(10_000)), protocol=4))
        large = disassemble(pickle.dumps(list(range(100_000)), protocol=4))

        assert 8 < len(large) / len(small) < 12


class TestDisChecks:
    """`dis()` raises `ValueError` on a malformed pickle and on an integer
    argument over the digit limit; a shared `memo` follows one pickler's
    entries across pickles."""

    DATA = pickle.dumps({"name": "Alice", "age": 30}, protocol=4)

    def test_the_documented_lines(self) -> None:
        lines = disassemble(self.DATA).splitlines()

        assert lines[0].split() == ["0:", "\\x80", "PROTO", "4"]
        assert lines[5].split() == ["14:", "\\x8c", "SHORT_BINUNICODE", "'name'"]
        assert lines[-1] == "highest protocol among opcodes = 4"

    def test_a_truncated_pickle_raises_after_printing_what_it_read(self) -> None:
        out = io.StringIO()

        with pytest.raises(ValueError, match="pickle exhausted before seeing STOP"):
            pickletools.dis(self.DATA[:-1], out=out)

        assert out.getvalue().splitlines()[-1].split() == [
            "37:",
            "u",
            "SETITEMS",
            "(MARK",
            "at",
            "13)",
        ]

    def test_an_unknown_opcode_raises(self) -> None:
        with pytest.raises(ValueError, match="opcode b'\\?' unknown"):
            disassemble(b"?")

    def test_a_pop_from_an_empty_stack_raises(self) -> None:
        with pytest.raises(ValueError, match="tries to pop 1 items from stack with only 0"):
            disassemble(b"0.")

    def test_an_integer_over_the_digit_limit_raises_in_dis_only(self) -> None:
        data = pickle.dumps(10**5_000, protocol=4)
        previous = sys.get_int_max_str_digits()

        assert names(data) == ["PROTO", "FRAME", "LONG4", "STOP"]
        try:
            sys.set_int_max_str_digits(sys.int_info.default_max_str_digits)
            with pytest.raises(ValueError, match="integer string conversion"):
                disassemble(data)
            sys.set_int_max_str_digits(0)
            assert "1" + "0" * 5_000 in disassemble(data)
        finally:
            sys.set_int_max_str_digits(previous)

    def test_a_shared_memo_follows_one_pickler_across_pickles(self) -> None:
        stream = io.BytesIO()
        pickler = pickle.Pickler(stream, protocol=4)
        shared = ["shared"]
        pickler.dump(shared)
        pickler.dump(shared)

        stream.seek(0)
        memo: dict[int, Any] = {}
        disassemble(stream, memo=memo)
        assert "BINGET     0" in disassemble(stream, memo=memo)

        stream.seek(0)
        disassemble(stream)
        with pytest.raises(ValueError, match="memo key 0 has never been stored into"):
            disassemble(stream)

    def test_a_memo_key_stored_twice(self) -> None:
        # BININT1 1, BINPUT 0, POP, BININT1 2, BINPUT 0, STOP
        data = b"\x80\x02K\x01q\x000K\x02q\x00."
        assert pickle.loads(data) == 2

        if sys.version_info >= (3, 14):
            assert "BINPUT     0" in disassemble(data)
        else:
            with pytest.raises(ValueError, match="memo key 0 already defined"):
                disassemble(data)


class TestOptimize:
    """`optimize(picklestring)` | O(n) | O(n): drops each memo store no `GET`
    reads, renumbers the rest, and rebuilds protocol 4+ frames."""

    def test_unread_stores_are_dropped(self) -> None:
        data = pickle.dumps({"name": "Alice", "age": 30}, protocol=4)

        smaller = pickletools.optimize(data)

        assert "MEMOIZE" in names(data)
        assert "MEMOIZE" not in names(smaller)
        assert len(smaller) < len(data)
        assert pickle.loads(smaller) == {"name": "Alice", "age": 30}

    def test_a_read_store_is_kept_and_renumbered_from_zero(self) -> None:
        unshared = [str(i) for i in range(5)]
        shared = ["shared"]
        data = pickle.dumps([unshared, shared, shared], protocol=2)

        kept = pickletools.optimize(data)

        stores = [arg for op, arg, _pos in pickletools.genops(kept) if "PUT" in op.name]
        gets = [arg for op, arg, _pos in pickletools.genops(kept) if "GET" in op.name]
        assert stores == [0] and gets == [0]
        restored = pickle.loads(kept)
        assert restored == [unshared, shared, shared]
        assert restored[1] is restored[2]

    def test_frames_are_rebuilt(self) -> None:
        value = [str(i) * 10 for i in range(20_000)]
        data = pickle.dumps(value, protocol=4)

        optimized = pickletools.optimize(data)

        def frames(pickled: bytes) -> list[Any]:
            return [arg for op, arg, _pos in pickletools.genops(pickled) if op.name == "FRAME"]

        assert len(frames(optimized)) > 1
        assert frames(optimized) != frames(data)
        assert pickle.loads(optimized) == value

    def test_a_file_is_not_accepted(self) -> None:
        with pytest.raises(TypeError):
            pickletools.optimize(io.BytesIO(pickle.dumps(1, protocol=4)))  # type: ignore[arg-type]

    @pytest.mark.timing
    def test_time_is_linear_in_the_pickle(self) -> None:
        sizes = (10_000, 40_000, 160_000)
        pickles = [pickle.dumps([str(i) for i in range(n)], protocol=4) for n in sizes]

        times = [best_ns(lambda data=data: pickletools.optimize(data)) for data in pickles]

        for small, large in zip(times, times[1:], strict=False):
            assert large / small < 8, f"4x the pickle cost {large / small:.1f}x: {times}"


class TestCommandLine:
    """`python -m pickletools file [file ...]` | `dis()` on each file; `-m`
    shares one memo, `-l` sets the indent, `-a` annotates, `-o` writes to a
    file."""

    @staticmethod
    def _two_pickles(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        stream = io.BytesIO()
        pickler = pickle.Pickler(stream, protocol=4)
        shared = [(1, 2, 3, 4)]
        pickler.dump(shared)
        first_end = stream.tell()
        pickler.dump(shared)
        first, second = tmp_path / "first.pickle", tmp_path / "second.pickle"
        first.write_bytes(stream.getvalue()[:first_end])
        second.write_bytes(stream.getvalue()[first_end:])
        return first, second

    @staticmethod
    def _run(*args: str | pathlib.Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "pickletools", *map(str, args)],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

    def test_a_shared_memo_spans_files(self, tmp_path: pathlib.Path) -> None:
        first, second = self._two_pickles(tmp_path)

        shared = self._run("-m", first, second)
        separate = self._run(first, second)

        assert shared.returncode == 0, shared.stderr
        assert f"==> {first} <==" in shared.stdout and f"==> {second} <==" in shared.stdout
        assert "BINGET     0" in shared.stdout
        assert separate.returncode != 0
        assert "memo key 0 has never been stored into" in separate.stderr

    def test_indent_annotate_and_output_options(self, tmp_path: pathlib.Path) -> None:
        first, _second = self._two_pickles(tmp_path)
        target = tmp_path / "out.txt"

        indented = self._run(first)
        result = self._run("-l", "0", "-a", "-o", target, first)

        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        written = target.read_text(encoding="utf-8")
        assert "K        BININT1" in indented.stdout
        assert "K    BININT1" in written
        assert "Push a one-byte unsigned integer." in written


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
    """Each block runs in its own subprocess, so the integer digit limit
    cannot leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "stream.tell() == 5" in s)
        mutated = source.replace("stream.tell() == 5", "stream.tell() == 4", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
