"""Tests for docs/stdlib/hmac.md.

The page prices an `HMAC` as a hash state keyed once: construction costs the
key plus the message, `update()` is linear in its bytes, a digest or a copy
works on the fixed-size state alone, and `compare_digest()` walks its whole
second argument. Keying is settled by observation against the RFC 2104
construction; linearity by timing two sizes; that the state is fixed by traced
allocation and by timing a digest or copy over objects that absorbed very
different amounts; the missing early exit by timing where the inputs differ.

Measurement scope:

* Construction: a key one byte longer than the block gives the same MAC as its
  digest used as the key, and a key of exactly one block does not, for SHA-256
  (64) and SHA-512 (128); a short key gives the same MAC as itself padded with
  zero bytes. `new()` with a 10,000-byte and a 1,000,000-byte key, and with a
  10,000-byte and a 1,000,000-byte message, costs between 20x and 500x in a
  timing test. With a prebuilt 10 MB key or message, `new()` peaks under
  10 KB of traced allocation. A name and a constructor give the same digest;
  a missing `digestmod`, a `str` key and a `memoryview` key raise `TypeError`,
  and a `bytearray` key is accepted.
* `hmac.digest()` equals `new(...).digest()` for a name, a constructor and a
  long key; its key and message each cost between 20x and 500x from 10,000
  to 1,000,000 bytes, and it peaks under 10 KB over a prebuilt 10 MB message.
* `update()` over 10,000 and 1,000,000 bytes costs between 20x and 500x and
  peaks under 10 KB over 10 MB. Chunked updates equal one call on the
  concatenation, and 10 MB in 64 KiB chunks costs under 2x one call.
* `digest()`, `hexdigest()` and `copy()` on an object that absorbed 10 bytes
  and one that absorbed 10 MB differ by less than 3x in a timing test, where a
  cost proportional to the input would give a million, and each peaks under
  10 KB of traced allocation on the larger. A second `digest()` equals the first, an `update()`
  after it lands, and `hexdigest()` is `digest().hex()`. A copy diverges from
  its original and from a sibling copy, and each equals the MAC of the full
  message. Copying an object keyed with 1,000,000 bytes costs under a tenth
  of building one from the same key.
* The attributes are asserted for SHA-256, SHA-512 and MD5 by value, as are
  `hmac.digest_size`, `HMAC.blocksize` and every byte of both translation
  tables. A digest constructor without `block_size` warns with
  `RuntimeWarning` and gets a block size of 64, and its MAC equals SHA-256's.
* `compare_digest()`: from 10,000 to 10,000,000 bytes differing at the first
  byte, the cost rises between 100x and 10,000x, where `==` on the same
  inputs stays under 10x. At 10,000,000 bytes, a difference at the last byte costs between
  0.5x and 2x one at the first, where `==` costs more than 100x. A one-byte
  first argument against a 10,000,000-byte second costs more than 100x the
  reverse, and a first argument one byte short of the second costs between
  0.5x and 2x an equal comparison. It peaks under 1 KB over two 10 MB inputs.
  Its results and its `TypeError` for mixed or non-ASCII `str` are asserted,
  and a `bytearray` and a `memoryview` are accepted.
* The timing and allocation tests of `new()`, `hmac.digest()`, `update()`,
  `digest()`, `hexdigest()` and `copy()`, and the equality tests of the last
  five, run with the name `'sha256'`, which reaches OpenSSL's HMAC, and with
  the `hashlib.blake2b` constructor, which reaches the pure-Python pair of
  hash objects in Lib/hmac.py on every supported branch. The remaining tests
  use one hash each, as named in them. A SHAKE name raises rather than
  building an HMAC. `secrets.compare_digest` is asserted to be this module's
  function.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That `compare_digest()` leaks the length of its inputs but not where they
  differ is a timing side-channel property: the tests show that its cost
  follows the second argument's length and not the difference's position,
  within 2x, which is far coarser than an attack measures. The constant-time
  loops are `_tscmp` in Modules/_operator.c and, with OpenSSL, `CRYPTO_memcmp`
  in Modules/_hashopenssl.c.
* That the state is O(b) is read from Lib/hmac.py, which holds two hash
  objects, and Modules/_hashopenssl.c, which holds one `HMAC_CTX`;
  tracemalloc does not see OpenSSL's allocations, so the tests bound only
  Python-level allocation, under 10 KB rather than at b.
* That a digest is a snapshot is read from `_hmac_digest`, which copies the
  `HMAC_CTX` before `HMAC_Final`, and from `HMAC._current()`; the tests
  observe the object staying usable and the cost staying flat.
* Every growth-ratio test excludes a constant by its floor and a quadratic by
  its ceiling; a growth between the two would pass.
* The optional HACL* `_hmac` fallback that 3.14 uses for a digest name
  OpenSSL rejects, and the `_operator` comparison used by a build without
  OpenSSL, are not reached here; both loop over the input once in source.
* The measurements hold the hash at SHA-256 or BLAKE2b and do not vary the
  algorithm's own cost.
"""

from __future__ import annotations

import hashlib
import hmac
import pathlib
import re
import secrets
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "hmac.md"
EXPECTED_BLOCKS = 8

DIGESTMODS = pytest.mark.parametrize(
    "digestmod", ["sha256", hashlib.blake2b], ids=["openssl-name", "blake2b-constructor"]
)


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return float(best)


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class TestConstructionKeysOnce:
    """`hmac.new(key, msg=None, digestmod)` | O(m + n) | O(b): a key longer than
    `b` is hashed once, a shorter one padded, and `msg` absorbed once."""

    @pytest.mark.parametrize(("name", "block"), [("sha256", 64), ("sha512", 128)])
    def test_a_key_longer_than_the_block_is_replaced_by_its_digest(
        self, name: str, block: int
    ) -> None:
        longer = b"x" * (block + 1)
        exact = b"x" * block
        hashed_longer = hashlib.new(name, longer).digest()
        hashed_exact = hashlib.new(name, exact).digest()

        assert hmac.new(longer, b"d", name).digest() == hmac.new(hashed_longer, b"d", name).digest()
        assert hmac.new(exact, b"d", name).digest() != hmac.new(hashed_exact, b"d", name).digest()

    def test_a_short_key_is_padded_with_zero_bytes(self) -> None:
        padded = b"k" + bytes(10)

        assert hmac.new(b"k", b"d", "sha256").digest() == hmac.new(padded, b"d", "sha256").digest()

    @pytest.mark.timing
    @DIGESTMODS
    def test_the_key_costs_its_length(self, digestmod: Any) -> None:
        small, large = b"k" * 10_000, b"k" * 1_000_000

        ratio = best_ns(lambda: hmac.new(large, None, digestmod)) / best_ns(
            lambda: hmac.new(small, None, digestmod)
        )

        assert 20 < ratio < 500, f"100x the key cost {ratio:.1f}x"

    @pytest.mark.timing
    @DIGESTMODS
    def test_the_message_costs_its_length(self, digestmod: Any) -> None:
        small, large = b"m" * 10_000, b"m" * 1_000_000

        ratio = best_ns(lambda: hmac.new(b"k", large, digestmod)) / best_ns(
            lambda: hmac.new(b"k", small, digestmod)
        )

        assert 20 < ratio < 500, f"100x the message cost {ratio:.1f}x"

    @DIGESTMODS
    def test_neither_a_long_key_nor_a_long_message_is_held(self, digestmod: Any) -> None:
        big = b"x" * 10_000_000

        key_peak = peak_bytes(lambda: hmac.new(big, None, digestmod))
        msg_peak = peak_bytes(lambda: hmac.new(b"k", big, digestmod))

        assert key_peak < 10_000, f"a 10 MB key allocated {key_peak} bytes"
        assert msg_peak < 10_000, f"a 10 MB message allocated {msg_peak} bytes"

    def test_a_shake_does_not_build_an_hmac(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            hmac.new(b"k", b"d", "shake_128").digest()

    def test_a_name_and_a_constructor_agree(self) -> None:
        assert (
            hmac.new(b"k", b"d", "sha256").digest() == hmac.new(b"k", b"d", hashlib.sha256).digest()
        )

    def test_digestmod_is_required(self) -> None:
        with pytest.raises(TypeError, match="digestmod"):
            hmac.new(b"k", b"d")  # pyright: ignore[reportCallIssue]

    def test_the_key_must_be_bytes_or_bytearray(self) -> None:
        expected = hmac.new(b"k", b"d", "sha256").digest()

        assert hmac.new(bytearray(b"k"), b"d", "sha256").digest() == expected
        with pytest.raises(TypeError):
            hmac.new("k", b"d", "sha256")  # pyright: ignore[reportArgumentType]
        with pytest.raises(TypeError):
            hmac.new(memoryview(b"k"), b"d", "sha256")  # pyright: ignore[reportArgumentType]


class TestOneShotDigest:
    """`hmac.digest(key, msg, digest)` | O(m + n) | O(b): the same bytes as
    `new(key, msg, digest).digest()`, with no `HMAC` object."""

    @DIGESTMODS
    def test_it_equals_the_object_route(self, digestmod: Any) -> None:
        for key in (b"k", b"k" * 1000):
            expected = hmac.new(key, b"message", digestmod).digest()
            assert hmac.digest(key, b"message", digestmod) == expected

    @pytest.mark.timing
    @DIGESTMODS
    def test_the_key_and_the_message_each_cost_their_length(self, digestmod: Any) -> None:
        small, large = b"x" * 10_000, b"x" * 1_000_000

        key_ratio = best_ns(lambda: hmac.digest(large, b"m", digestmod)) / best_ns(
            lambda: hmac.digest(small, b"m", digestmod)
        )
        msg_ratio = best_ns(lambda: hmac.digest(b"k", large, digestmod)) / best_ns(
            lambda: hmac.digest(b"k", small, digestmod)
        )

        assert 20 < key_ratio < 500, f"100x the key cost {key_ratio:.1f}x"
        assert 20 < msg_ratio < 500, f"100x the message cost {msg_ratio:.1f}x"

    @DIGESTMODS
    def test_it_holds_nothing_proportional_to_the_message(self, digestmod: Any) -> None:
        big = b"x" * 10_000_000

        peak = peak_bytes(lambda: hmac.digest(b"k", big, digestmod))

        assert peak < 10_000, f"a 10 MB message allocated {peak} bytes"


class TestUpdateAbsorbsOnce:
    """`HMAC.update(msg)` | O(n) | O(1): repeated calls equal one call on the
    concatenation."""

    @DIGESTMODS
    def test_chunks_equal_one_call(self, digestmod: Any) -> None:
        chunked = hmac.new(b"k", None, digestmod)
        for part in (b"one", b"two", b"three"):
            chunked.update(part)

        assert chunked.digest() == hmac.new(b"k", b"onetwothree", digestmod).digest()

    @pytest.mark.timing
    @DIGESTMODS
    def test_it_costs_its_length(self, digestmod: Any) -> None:
        h = hmac.new(b"k", None, digestmod)
        small, large = b"m" * 10_000, b"m" * 1_000_000

        ratio = best_ns(lambda: h.update(large)) / best_ns(lambda: h.update(small))

        assert 20 < ratio < 500, f"100x the bytes cost {ratio:.1f}x"

    @DIGESTMODS
    def test_it_holds_nothing_proportional_to_the_bytes(self, digestmod: Any) -> None:
        h = hmac.new(b"k", None, digestmod)
        big = b"x" * 10_000_000

        peak = peak_bytes(lambda: h.update(big))

        assert peak < 10_000, f"a 10 MB update allocated {peak} bytes"

    @pytest.mark.timing
    def test_chunks_cost_what_one_call_does(self) -> None:
        data = b"x" * 10_000_000
        chunks = [data[i : i + 65536] for i in range(0, len(data), 65536)]

        def chunked() -> None:
            h = hmac.new(b"k", None, "sha256")
            for chunk in chunks:
                h.update(chunk)

        ratio = best_ns(chunked) / best_ns(lambda: hmac.new(b"k", data, "sha256"))

        assert ratio < 2, f"64 KiB chunks cost {ratio:.2f}x one call"


def _small_and_large(digestmod: Any) -> tuple[hmac.HMAC, hmac.HMAC]:
    return hmac.new(b"k", b"x" * 10, digestmod), hmac.new(b"k", b"x" * 10_000_000, digestmod)


class TestDigestIsASnapshot:
    """`HMAC.digest()` and `HMAC.hexdigest()` | O(b) | O(k): the object stays
    usable, and the cost is independent of what it absorbed."""

    @DIGESTMODS
    def test_the_object_stays_usable(self, digestmod: Any) -> None:
        h = hmac.new(b"k", b"head", digestmod)

        first = h.digest()
        assert h.digest() == first
        h.update(b"tail")
        assert h.digest() == hmac.new(b"k", b"headtail", digestmod).digest()

    @DIGESTMODS
    def test_hexdigest_renders_the_same_digest(self, digestmod: Any) -> None:
        h = hmac.new(b"k", b"data", digestmod)

        assert h.hexdigest() == h.digest().hex()
        assert len(h.hexdigest()) == 2 * h.digest_size

    @pytest.mark.timing
    @DIGESTMODS
    @pytest.mark.parametrize("method", ["digest", "hexdigest"])
    def test_the_cost_ignores_what_was_absorbed(self, digestmod: Any, method: str) -> None:
        small, large = _small_and_large(digestmod)

        ratio = best_ns(getattr(large, method)) / best_ns(getattr(small, method))

        assert ratio < 3, f"{method}() after 10 MB cost {ratio:.2f}x one after 10 bytes"

    @DIGESTMODS
    @pytest.mark.parametrize("method", ["digest", "hexdigest"])
    def test_it_allocates_nothing_proportional(self, digestmod: Any, method: str) -> None:
        _, large = _small_and_large(digestmod)

        peak = peak_bytes(getattr(large, method))

        assert peak < 10_000, f"{method}() after 10 MB allocated {peak} bytes"


class TestCopyClonesTheKeyedState:
    """`HMAC.copy()` | O(b) | O(b): no rekeying, and the two objects diverge."""

    @DIGESTMODS
    def test_copies_diverge_from_the_original_and_each_other(self, digestmod: Any) -> None:
        h = hmac.new(b"k", b"header:", digestmod)
        before = h.digest()

        first, second = h.copy(), h.copy()
        first.update(b"one")
        second.update(b"two")

        assert first.digest() == hmac.new(b"k", b"header:one", digestmod).digest()
        assert second.digest() == hmac.new(b"k", b"header:two", digestmod).digest()
        assert h.digest() == before

    @pytest.mark.timing
    @DIGESTMODS
    def test_the_cost_ignores_what_was_absorbed(self, digestmod: Any) -> None:
        small, large = _small_and_large(digestmod)

        ratio = best_ns(large.copy) / best_ns(small.copy)

        assert ratio < 3, f"copy() after 10 MB cost {ratio:.2f}x one after 10 bytes"

    @DIGESTMODS
    def test_it_allocates_only_the_state(self, digestmod: Any) -> None:
        _, large = _small_and_large(digestmod)

        peak = peak_bytes(large.copy)

        assert peak < 10_000, f"copy() after 10 MB allocated {peak} bytes"

    @pytest.mark.timing
    @DIGESTMODS
    def test_copying_skips_hashing_a_long_key_again(self, digestmod: Any) -> None:
        key = b"k" * 1_000_000
        keyed = hmac.new(key, None, digestmod)

        ratio = best_ns(lambda: hmac.new(key, None, digestmod)) / best_ns(keyed.copy)

        assert ratio > 10, f"rekeying with 1 MB cost only {ratio:.1f}x a copy"


class TestAttributesAndConstants:
    """`HMAC.digest_size`, `HMAC.block_size`, `HMAC.name`, `hmac.digest_size`,
    `HMAC.blocksize`, `hmac.trans_5C`, `hmac.trans_36` | O(1) | O(1)."""

    @pytest.mark.parametrize(
        ("digestmod", "name", "digest_size", "block_size"),
        [
            ("sha256", "hmac-sha256", 32, 64),
            (hashlib.sha512, "hmac-sha512", 64, 128),
            ("md5", "hmac-md5", 16, 64),
        ],
    )
    def test_instance_attributes(
        self, digestmod: Any, name: str, digest_size: int, block_size: int
    ) -> None:
        h = hmac.new(b"k", b"d", digestmod)

        assert (h.name, h.digest_size, h.block_size) == (name, digest_size, block_size)

    def test_module_constants(self) -> None:
        assert hmac.digest_size is None
        assert hmac.HMAC.blocksize == 64  # pyright: ignore[reportAttributeAccessIssue]
        assert hmac.trans_5C == bytes(x ^ 0x5C for x in range(256))
        assert hmac.trans_36 == bytes(x ^ 0x36 for x in range(256))

    def test_blocksize_is_assumed_for_a_hash_that_reports_none(self) -> None:
        class NoBlockSize:
            digest_size = 32

            def __init__(self, data: bytes = b"") -> None:
                self._hash = hashlib.sha256(data)

            def update(self, data: bytes) -> None:
                self._hash.update(data)

            def digest(self) -> bytes:
                return self._hash.digest()

            def copy(self) -> NoBlockSize:
                clone = NoBlockSize()
                clone._hash = self._hash.copy()
                return clone

        with pytest.warns(RuntimeWarning, match="block_size"):
            h = hmac.new(b"k", b"d", NoBlockSize)  # pyright: ignore[reportArgumentType]

        assert h.block_size == 64
        assert h.digest() == hmac.new(b"k", b"d", "sha256").digest()


class TestCompareDigestHasNoEarlyExit:
    """`hmac.compare_digest(a, b)` | O(c) | O(1): walks the whole second
    argument wherever the first difference lies, and when the lengths differ."""

    def test_results(self) -> None:
        digest = hmac.digest(b"k", b"m", "sha256")

        assert hmac.compare_digest(digest, digest)
        assert not hmac.compare_digest(bytes(32), digest)
        assert not hmac.compare_digest(digest[:16], digest)
        assert hmac.compare_digest(digest.hex(), digest.hex())
        assert hmac.compare_digest(bytearray(digest), memoryview(digest))
        assert secrets.compare_digest is hmac.compare_digest

    def test_mixed_or_non_ascii_strings_raise(self) -> None:
        with pytest.raises(TypeError):
            hmac.compare_digest("ab", b"ab")  # pyright: ignore[reportCallIssue, reportArgumentType]
        with pytest.raises(TypeError, match="non-ASCII"):
            hmac.compare_digest("é", "é")

    @pytest.mark.timing
    def test_the_cost_grows_with_length_even_when_the_first_byte_differs(self) -> None:
        def pair(size: int) -> tuple[bytes, bytes]:
            return b"a" * size, b"b" + b"a" * (size - 1)

        small_a, small_b = pair(10_000)
        large_a, large_b = pair(10_000_000)

        ratio = best_ns(lambda: hmac.compare_digest(large_a, large_b)) / best_ns(
            lambda: hmac.compare_digest(small_a, small_b)
        )
        eq_ratio = best_ns(lambda: large_a == large_b) / best_ns(lambda: small_a == small_b)

        assert 100 < ratio < 10_000, f"1000x the length cost compare_digest {ratio:.1f}x"
        assert eq_ratio < 10, f"== cost {eq_ratio:.1f}x, so the control did not exit early"

    @pytest.mark.timing
    def test_the_position_of_the_difference_does_not_matter(self) -> None:
        size = 10_000_000
        base = b"a" * size
        first = b"b" + b"a" * (size - 1)
        last = b"a" * (size - 1) + b"b"

        ratio = best_ns(lambda: hmac.compare_digest(base, last)) / best_ns(
            lambda: hmac.compare_digest(base, first)
        )
        eq_ratio = best_ns(lambda: base == last) / best_ns(lambda: base == first)

        assert 0.5 < ratio < 2, f"a last-byte difference cost {ratio:.2f}x a first-byte one"
        assert eq_ratio > 100, f"== cost only {eq_ratio:.1f}x, so the control did not exit early"

    @pytest.mark.timing
    def test_the_second_argument_sets_the_cost(self) -> None:
        big = b"a" * 10_000_000

        ratio = best_ns(lambda: hmac.compare_digest(b"x", big)) / best_ns(
            lambda: hmac.compare_digest(big, b"x")
        )

        assert ratio > 100, f"a 10 MB second argument cost only {ratio:.1f}x a 10 MB first"

    @pytest.mark.timing
    def test_a_length_mismatch_still_walks_the_second_argument(self) -> None:
        big = b"a" * 10_000_000
        short = big[:-1]

        ratio = best_ns(lambda: hmac.compare_digest(short, big)) / best_ns(
            lambda: hmac.compare_digest(big, big)
        )

        assert 0.5 < ratio < 2, f"a length mismatch cost {ratio:.2f}x an equal comparison"

    def test_it_allocates_nothing_proportional(self) -> None:
        a = b"a" * 10_000_000
        b = b"a" * 9_999_999 + b"b"

        peak = peak_bytes(lambda: hmac.compare_digest(a, b))

        assert peak < 1_000, f"comparing 10 MB allocated {peak} bytes"


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
        line, source = next((n, s) for n, s in _blocks() if "h.digest() == digest  #" in s)
        mutated = source.replace(
            "assert h.digest() == digest  #", "assert h.digest() != digest  #", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
