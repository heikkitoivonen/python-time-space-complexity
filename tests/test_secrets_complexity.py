"""Tests for docs/stdlib/secrets.md.

Every function on the page reaches `os.urandom()` through the one
`random.SystemRandom` instance the module builds, so nearly every row is
settled by recording that call: how many times it is made and how many bytes
each one asks for. The recorder replaces `random._urandom`, the name
`SystemRandom.getrandbits()` and `SystemRandom.randbytes()` look up, and each
test asserts the recorder was reached before reading it.

Measurement scope:

* The token rows are one recorded draw of exactly the bytes asked for, at
  1, 1,000 and 100,000 bytes and at no size, where the draw is
  `DEFAULT_ENTROPY` bytes. The output lengths are asserted against the byte
  count: 2n hex digits, and ceil(4n/3) URL-safe characters with no padding,
  checked at every n from 0 to 64 and at 1,000. Time is one timing test:
  1,024x the bytes of `token_hex()` costs more than 5x. The hex and Base64
  passes are not timed apart from the draw.
* `randbits(w)` is one recorded draw of ceil(w/8) bytes at widths from 1 to
  800,000 bits, with the result no wider than w.
* `randbelow(n)` is the recorded draws over 2,000 calls: every draw is
  ceil(w/8) bytes for w the bit length of n, the mean number of draws sits
  between 1.8 and 2.3 for a power of two and under 1.1 for one less than a
  power of two, and every result is in range. Width is a timing test, 1,024x
  the bits costing more than 20x, and a `tracemalloc` peak that is at least
  the bytes drawn and under ten times them. `randbelow(0)` and a negative
  bound raise before any draw.
* `choice()` is a counting sequence: one `__getitem__`, and at most two
  `__len__` calls, whether the sequence reports 10 elements or 10**18; at
  10**18 the draw is 8 bytes. The second `__len__` is the emptiness check
  made ahead of the draw from 3.11, so the count is asserted as a ceiling.
  A `range` of a billion is chosen from under a 2 KB peak.
* `SystemRandom` is asserted to be the instance every module function is
  bound to, its `random()` a 7-byte draw, its `seed()` a no-op that leaves
  the next tokens independent, and its `getstate()` a `NotImplementedError`.
* `compare_digest()` is asserted to be `hmac.compare_digest`. Its length term
  is a timing test, 1,024x the bytes costing more than 100x, and the length
  that counts is the second argument's: a 16-byte first argument against a
  1 MB second costs more than 100x the reverse. That the
  position of the first difference does not change the cost is a second
  timing test at 4 MB: a mismatch in the first byte costs at least a quarter
  of an equal comparison, where `==` on the same inputs stops thousands of
  times sooner.
* The password recipe is exercised through the page's own block: a length
  under three raises, and the mean attempts over 200 passwords is under three
  at length 12 and over eight at length 3, where about one draw in twenty
  holds all three classes.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `compare_digest()` leaks nothing through timing is a property of the
  C implementation's design, stated in the official documentation. The
  position test above shows the cost is not proportional to the match
  length; it does not show the absence of every timing channel.
"""

from __future__ import annotations

import hmac
import pathlib
import random
import re
import secrets
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "secrets.md"
EXPECTED_BLOCKS = 6


@pytest.fixture
def draws(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Record the size of every `os.urandom()` call the module makes."""
    sizes: list[int] = []
    original = random._urandom  # type: ignore[attr-defined]

    def recording(nbytes: int) -> bytes:
        sizes.append(nbytes)
        return original(nbytes)

    monkeypatch.setattr(random, "_urandom", recording)
    yield sizes


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def peak_bytes(func: Callable[[], Any]) -> int:
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def bytes_for(bits: int) -> int:
    return (bits + 7) // 8


class CountingSequence:
    """A sequence that counts its length and index lookups."""

    def __init__(self, length: int) -> None:
        self.length = length
        self.len_calls = 0
        self.lookups = 0

    def __len__(self) -> int:
        self.len_calls += 1
        return self.length

    def __getitem__(self, index: int) -> int:
        self.lookups += 1
        if not 0 <= index < self.length:
            raise IndexError(index)
        return index


class TestTokens:
    """`token_bytes(n)`, `token_hex(n)`, `token_urlsafe(n)` | O(n) | O(n)."""

    @pytest.mark.parametrize("nbytes", [1, 1_000, 100_000])
    def test_each_token_is_one_draw_of_the_bytes_asked_for(
        self, draws: list[int], nbytes: int
    ) -> None:
        raw = secrets.token_bytes(nbytes)
        hexed = secrets.token_hex(nbytes)
        safe = secrets.token_urlsafe(nbytes)

        assert draws == [nbytes, nbytes, nbytes]
        assert len(raw) == nbytes
        assert len(hexed) == 2 * nbytes
        assert len(safe) == -(-4 * nbytes // 3)

    def test_no_size_draws_default_entropy(self, draws: list[int]) -> None:
        assert secrets.DEFAULT_ENTROPY == 32

        raw = secrets.token_bytes()
        hexed = secrets.token_hex()
        safe = secrets.token_urlsafe()

        assert draws == [32, 32, 32]
        assert (len(raw), len(hexed), len(safe)) == (32, 64, 43)

    def test_urlsafe_length_is_four_thirds_without_padding(self) -> None:
        for nbytes in [*range(65), 1_000]:
            token = secrets.token_urlsafe(nbytes)

            assert len(token) == -(-4 * nbytes // 3), nbytes
            assert "=" not in token
            assert re.fullmatch(r"[A-Za-z0-9_-]*", token), token

    def test_hex_is_two_digits_per_byte(self) -> None:
        for nbytes in (0, 1, 7, 1_000):
            token = secrets.token_hex(nbytes)

            assert len(token) == 2 * nbytes
            assert re.fullmatch(r"[0-9a-f]*", token), token

    def test_nothing_is_shared_between_calls(self, draws: list[int]) -> None:
        first = secrets.token_bytes(32)
        second = secrets.token_bytes(32)

        assert draws == [32, 32]
        assert first != second

    @pytest.mark.timing
    def test_cost_follows_the_requested_size(self) -> None:
        small = best_time(lambda: secrets.token_hex(16))
        large = best_time(lambda: secrets.token_hex(16_384))

        assert large > small * 5, f"linear in bytes requested: {small:.2e}s vs {large:.2e}s"


class TestRandbits:
    """`randbits(w)` | O(w) | O(w) | one draw of ceil(w/8) bytes."""

    @pytest.mark.parametrize("bits", [1, 8, 9, 64, 65, 4_096, 800_000])
    def test_one_draw_of_the_bytes_that_hold_the_bits(self, draws: list[int], bits: int) -> None:
        value = secrets.randbits(bits)

        assert draws == [bytes_for(bits)]
        assert 0 <= value < 1 << bits


class TestRandbelow:
    """`randbelow(n)` | O(w) expected | O(w) | a rejection loop over w-bit draws."""

    def test_every_round_draws_the_bytes_of_the_bound(self, draws: list[int]) -> None:
        for bound in (1, 2, 3, 100, 128, 129, 2**64, 2**64 + 1, 2**4096):
            draws.clear()
            values = [secrets.randbelow(bound) for _ in range(200)]

            assert set(draws) == {bytes_for(bound.bit_length())}, bound
            assert all(0 <= value < bound for value in values), bound

    def test_a_power_of_two_costs_two_rounds_expected(self, draws: list[int]) -> None:
        for _ in range(2_000):
            secrets.randbelow(2**16)
        rounds = len(draws) / 2_000

        assert 1.8 < rounds < 2.3, f"{rounds} rounds per draw; half of each round is rejected"

    def test_one_below_a_power_of_two_costs_one_round_expected(self, draws: list[int]) -> None:
        for _ in range(2_000):
            secrets.randbelow(2**16 - 1)
        rounds = len(draws) / 2_000

        assert 1 <= rounds < 1.1, f"{rounds} rounds per draw; one in 65,536 is rejected"

    def test_a_non_positive_bound_raises_before_drawing(self, draws: list[int]) -> None:
        for bound in (0, -1):
            with pytest.raises(ValueError):
                secrets.randbelow(bound)

        assert draws == []
        assert secrets.randbelow(1) == 0

    def test_space_is_the_width_of_the_bound(self) -> None:
        drawn = bytes_for(800_000)
        bound = 2**800_000
        peak = peak_bytes(lambda: secrets.randbelow(bound))
        small = peak_bytes(lambda: secrets.randbelow(100))

        assert drawn <= peak < 10 * drawn, f"peak {peak} bytes for a {drawn}-byte draw"
        assert small < 1_000, f"peak {small} bytes for a one-byte draw"

    @pytest.mark.timing
    def test_a_wide_bound_costs_proportionally_more(self) -> None:
        narrow_bound = 2**8_192
        wide_bound = 2 ** (8_192 * 1_024)
        narrow = best_time(lambda: secrets.randbelow(narrow_bound))
        wide = best_time(lambda: secrets.randbelow(wide_bound))

        assert wide > narrow * 20, f"linear in bits: {narrow:.2e}s vs {wide:.2e}s"


class TestChoice:
    """`choice(seq)` | O(1) expected | O(1) | one length, one draw, one lookup."""

    @pytest.mark.parametrize("length", [10, 10**18])
    def test_one_length_one_draw_one_lookup(self, draws: list[int], length: int) -> None:
        population = CountingSequence(length)

        picked = secrets.choice(population)

        assert population.lookups == 1
        assert population.len_calls <= 2  # 3.11+ checks for emptiness before the draw
        assert 0 <= picked < length
        assert all(size == bytes_for(length.bit_length()) for size in draws)
        assert draws and max(draws) <= 8

    def test_choosing_from_a_huge_range_allocates_nothing(self) -> None:
        peak = peak_bytes(lambda: secrets.choice(range(10**9)))

        assert peak < 2_000, f"a materialised range would be gigabytes; peak was {peak} bytes"

    def test_a_string_yields_one_character(self) -> None:
        assert secrets.choice("hello") in set("hello")

    def test_an_empty_sequence_raises(self) -> None:
        with pytest.raises(IndexError):
            secrets.choice([])


class TestSystemRandom:
    """`SystemRandom()` | O(1) | O(1) | the instance behind every module function."""

    def test_every_function_is_bound_to_one_instance(self) -> None:
        generator = secrets.choice.__self__  # type: ignore[attr-defined]

        assert secrets.SystemRandom is random.SystemRandom
        assert isinstance(generator, random.SystemRandom)
        assert secrets.randbits.__self__ is generator  # type: ignore[attr-defined]

    def test_random_is_a_seven_byte_draw(self, draws: list[int]) -> None:
        value = secrets.SystemRandom().random()

        assert draws == [7]
        assert 0.0 <= value < 1.0

    def test_randbytes_is_the_draw_behind_token_bytes(self, draws: list[int]) -> None:
        generator = secrets.SystemRandom()

        assert len(generator.randbytes(1_000)) == 1_000
        assert draws == [1_000]

    def test_seed_does_nothing_and_state_does_not_exist(self, draws: list[int]) -> None:
        generator = secrets.SystemRandom()

        assert generator.seed(1) is None
        first = generator.randbytes(32)
        assert generator.seed(1) is None
        second = generator.randbytes(32)

        assert first != second
        assert draws == [32, 32]
        with pytest.raises(NotImplementedError):
            generator.getstate()


class TestCompareDigest:
    """`compare_digest(a, b)` | O(m) | O(1) | `hmac.compare_digest`, every byte compared."""

    def test_is_the_hmac_function(self) -> None:
        assert secrets.compare_digest is hmac.compare_digest
        token = secrets.token_hex(32)

        assert secrets.compare_digest(token, token) is True
        assert secrets.compare_digest(token, token[:-1] + "!") is False
        assert secrets.compare_digest(token.encode(), token.encode()) is True

    @pytest.mark.timing
    def test_cost_follows_the_length(self) -> None:
        small = b"x" * 1_024
        large = b"x" * (1_024 * 1_024)
        tiny = b"x" * 16
        short = best_time(lambda: secrets.compare_digest(small, small))
        long = best_time(lambda: secrets.compare_digest(large, large))
        long_second = best_time(lambda: secrets.compare_digest(tiny, large))
        short_second = best_time(lambda: secrets.compare_digest(large, tiny))

        assert long > short * 100, f"linear in bytes: {short:.2e}s vs {long:.2e}s"
        assert long_second > short_second * 100, (
            f"the second argument sets the length: {short_second:.2e}s vs {long_second:.2e}s"
        )

    @pytest.mark.timing
    def test_an_early_difference_costs_as_much_as_none(self) -> None:
        size = 4 * 1_024 * 1_024
        same = b"x" * size
        early = b"y" + same[1:]
        equal = best_time(lambda: secrets.compare_digest(same, same))
        differs = best_time(lambda: secrets.compare_digest(same, early))
        short_circuit = best_time(lambda: same == early)

        assert differs > equal / 4, f"first-byte mismatch {differs:.2e}s vs equal {equal:.2e}s"
        assert short_circuit < equal / 100, f"== {short_circuit:.2e}s vs {equal:.2e}s"


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
        [sys.executable, str(script)], cwd=cwd, capture_output=True, text=True, timeout=120
    )


class TestPasswordRecipe:
    """The page's rejection recipe: O(length) per attempt, a few attempts expected."""

    def _recipe(self) -> Callable[..., str]:
        source = next(s for _, s in _blocks() if "generate_secure_password" in s)
        namespace: dict[str, Any] = {}
        exec(source, namespace)
        return namespace["generate_secure_password"]

    def test_a_length_that_cannot_satisfy_the_rule_is_refused(self) -> None:
        recipe = self._recipe()
        for length in (0, 1, 2):
            with pytest.raises(ValueError):
                recipe(length)

    def test_attempts_fall_as_the_length_grows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        recipe = self._recipe()
        picks = 0
        original = secrets.choice

        def counting(seq: Any) -> Any:
            nonlocal picks
            picks += 1
            return original(seq)

        def attempts_at(length: int) -> float:
            nonlocal picks
            picks = 0
            passwords = [recipe(length) for _ in range(200)]
            assert all(len(password) == length for password in passwords)
            assert all(
                any(c.isupper() for c in p)
                and any(c.islower() for c in p)
                and any(c.isdigit() for c in p)
                for p in passwords
            )
            return picks / (length * 200)

        monkeypatch.setattr(secrets, "choice", counting)
        long = attempts_at(12)
        short = attempts_at(3)

        assert 1 <= long < 3, f"{long} attempts per twelve-character password"
        assert short > 8, f"{short} attempts per three-character password"
        assert short > 3 * long


class TestDocumentedExamples:
    """Each block runs in a subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(url_token) == 43" in s)
        mutated = source.replace("len(url_token) == 43", "len(url_token) == 44", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
