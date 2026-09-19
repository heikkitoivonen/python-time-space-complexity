"""Tests for docs/stdlib/hashlib.md.

The page prices the module as a fixed-size state that absorbs each byte once:
constructing and updating are linear in the bytes passed, a digest is a copy
of the state finalized, and only the SHAKE output length and the two key
derivation functions carry a bound of their own. Linearity is settled by
timing two sizes; that the state is fixed is settled by traced allocation and
by timing a digest or copy over objects that have absorbed very different
amounts; the key derivation terms are settled by holding every other
parameter fixed while one grows.

Measurement scope:

* Every constructor in `algorithms_guaranteed` builds from the named function
  and from `new()` with equal digests, and reports the digest and block sizes
  the page lists. `sha256()` over 10,000 and 1,000,000 bytes costs between
  20x and 500x in a timing test, which excludes a constant and a quadratic
  alike, and over 10 MB peaks under 10 KB of traced allocation, the state
  being one block. `new('nope')` raises `ValueError` and a `str` raises
  `TypeError`.
* `update()` over 10,000 and 1,000,000 bytes costs between 20x and 500x in a
  timing test and peaks under 10 KB over 10 MB. Two chunked updates equal one
  call on the concatenation.
* `digest()`, `hexdigest()` and `copy()` on an object that absorbed 10 bytes
  and one that absorbed 10 MB differ by less than 3x in a timing test, where
  a cost proportional to the input would give a million; `copy()` peaks
  within 1 KB of each other on the two. A second `digest()` equals the
  first, an `update()` after it still lands, and a copy diverges from its
  original.
* `shake_128().digest()` at 32 and 1,000,000 bytes costs between 100x and
  100,000x in a timing test, and the 1,000,000-byte call peaks between 900 KB
  and 5 MB; the 32-byte output is a prefix of the longer one, `hexdigest(L)`
  is 2L characters and `digest_size` is 0.
* BLAKE2: a 64-byte key on a 1 MB message costs under 1.5x the unkeyed
  construction in a timing test, where a key absorbed per byte would double
  it; each limit raises `ValueError` one byte over; `digest_size` sets the
  output length; the class constants are the page's numbers.
* `pbkdf2_hmac('sha256')`: 1,000 and 100,000 iterations cost between 30x
  and 500x (i); `dklen` 32 against 33 between 1.5x and 4x and 32 against 320
  between 5x and 50x (c); a 1 MB password against a 2-byte one at 1,000
  iterations costs under 50x, where keying per iteration would give
  thousands, and at one iteration the same password costs under 4x across
  `dklen` 32 and 320, where keying per block would give 10x (m once); a 1 MB
  salt against 4 bytes at 1,000 iterations and one block costs under 50x (s
  per block, not per iteration), and at one iteration the same salt costs
  between 4x and 40x across `dklen` 32 and 320 (s per block). `dklen`
  defaults to the digest size, block one is unchanged by a longer `dklen`,
  and `iterations` or `dklen` of 0 raise `ValueError`.
* `scrypt()`: `n` 2**10 against 2**14 costs between 8x and 100x, `r` 1
  against 8 and `p` 1 against 8 each between 4x and 40x, all with the other
  two fixed. `n=2**16,
  r=8` raises `ValueError` under the default cap and succeeds with
  `maxmem=2**27`; `n=3` raises; `dklen` defaults to 64.
* `file_digest()` (3.11+): an 8 MB file peaks between 200 KB and 1 MB, takes
  33 `readinto()` calls, and matches `sha256()` of the bytes; after
  `seek(100)` it matches the bytes from 100. A `BytesIO` whose `bytes` the
  caller still references peaks over 8 MB on the first call and under 50 KB
  on the second; one holding the only reference, and one that was written,
  peak under 50 KB; a `BytesIO` is hashed whole after a seek. A `StringIO`
  raises `ValueError`.
* The GIL claim is a timing test on a machine with at least two CPUs in its
  affinity mask: four threads each making one `update()` of 16 MB finish in
  under 0.8x the sequential time, and four threads each making 8,000 updates
  of 1,000 bytes on a fresh object finish in more than 0.8x of it. A CPU
  quota below two cores is not detected and fails the first assertion.
* `algorithms_guaranteed` is the 14 names on the page and a subset of
  `algorithms_available`; both are sets.
* Every fenced Python block runs in its own subprocess and working
  directory, and a mutated assertion in one of them is asserted to fail. The
  two blocks that call `file_digest()` are skipped on 3.10, where it does not
  exist, and the skip count is asserted.

Not settled here:

* That `new(name)` is one name lookup over the named constructor is
  Lib/hashlib.py: `__hash_new` hands the name to `_hashlib.new()`, which
  fetches the OpenSSL digest by name, or for BLAKE2 to a constructor cache
  keyed by name. The lookup is not timed; the test shows only that both
  routes build the same object.
* That a BLAKE2 key costs one block is the BLAKE2 specification, RFC 7693
  section 3.3: the key is padded to a block and compressed first. The timing
  test bounds keyed construction under 1.5x unkeyed on 1 MB, which excludes
  rekeying per block but not a smaller cost proportional to the message.
* That the state is O(b) is read from Modules/_hashopenssl.c, where a HASH
  object holds one EVP_MD_CTX, and from the HACL* state structs behind
  Modules/blake2module.c and Modules/sha3module.c; the allocation tests bound
  it under 10 KB rather than at b.
* That `update()` releases the GIL from 2048 bytes is HASHLIB_GIL_MINSIZE in
  Modules/hashlib.h on every supported branch; the timing test observes the
  two sides of it on the pinned interpreter and is skipped on one CPU.
* The space bounds of both key derivation functions are read from OpenSSL:
  its PBKDF2 and scrypt implementations keep a copy of the password and
  salt, and scrypt's 128·r·N working set and 32 MiB default cap are
  EVP_PBE_scrypt's. tracemalloc does not see OpenSSL's allocations, so only
  the cap's rejection is observed. scrypt's password, salt and `dklen` terms
  follow from RFC 7914's two one-iteration PBKDF2 passes over 128·r·p bytes
  and are not varied; the timing tests hold them at 2, 4 and 64 bytes.
* Every growth-ratio test excludes a constant by its floor and a quadratic
  by its ceiling; a growth between the two would pass, and linearity itself
  is the algorithm's definition. The two tests that show a long password or
  salt is not absorbed per iteration bound only from above.
* Whether `usedforsecurity=False` makes MD5 or SHA-1 constructible on a
  FIPS-restricted build cannot be observed here, where both construct
  without it; the test shows only that the flag leaves the digest unchanged.
* The pure-Python `pbkdf2_hmac` fallback that 3.10 and 3.11 keep for a
  build whose OpenSSL lacks PKCS5_PBKDF2_HMAC is not reachable here.
* The measurements hold the algorithm at SHA-256 (BLAKE2b for its own rows
  and SHAKE128 for the XOF rows), the SHAKE input at 4 bytes, and the
  `hash_name` of `pbkdf2_hmac()` at 'sha256'.
"""

from __future__ import annotations

import hashlib
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "hashlib.md"
EXPECTED_BLOCKS = 11
FILE_DIGEST_BLOCKS = 2  # the blocks that need 3.11+, skipped on 3.10

GUARANTEED = {
    "md5": (16, 64),
    "sha1": (20, 64),
    "sha224": (28, 64),
    "sha256": (32, 64),
    "sha384": (48, 128),
    "sha512": (64, 128),
    "sha3_224": (28, 144),
    "sha3_256": (32, 136),
    "sha3_384": (48, 104),
    "sha3_512": (64, 72),
    "shake_128": (0, 168),
    "shake_256": (0, 136),
    "blake2b": (64, 128),
    "blake2s": (32, 64),
}

TEN_MB = b"x" * (10 * 2**20)


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


class TestConstructorsAbsorbData:
    """Constructors | O(n) | O(b): `data` is absorbed at once into a state of
    one block, and `new(name)` is one lookup on top of the named constructor."""

    @pytest.mark.parametrize("name", sorted(GUARANTEED))
    def test_every_guaranteed_name_builds_both_ways(self, name: str) -> None:
        named = getattr(hashlib, name)(b"payload")
        looked_up: Any = hashlib.new(name, b"payload")

        assert named.name == looked_up.name == name
        assert (named.digest_size, named.block_size) == GUARANTEED[name]
        if name.startswith("shake"):
            assert named.digest(32) == looked_up.digest(32)
        else:
            assert named.digest() == looked_up.digest()
            assert len(named.digest()) == named.digest_size

    def test_an_unknown_name_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported hash type"):
            hashlib.new("nope")

    def test_a_str_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="encoded"):
            hashlib.sha256("text")  # type: ignore[arg-type]

    def test_usedforsecurity_changes_nothing_about_the_digest(self) -> None:
        assert hashlib.md5(b"x", usedforsecurity=False).digest() == hashlib.md5(b"x").digest()

    def test_the_state_does_not_grow_with_the_input(self) -> None:
        peak = peak_bytes(lambda: hashlib.sha256(TEN_MB))

        assert peak < 10_000, f"sha256() over 10 MB allocated {peak} bytes"

    @pytest.mark.timing
    def test_a_hundred_times_the_data_costs_far_more(self) -> None:
        small, large = b"x" * 10_000, b"x" * 1_000_000

        small_ns = best_ns(lambda: hashlib.sha256(small), inner=5)
        large_ns = best_ns(lambda: hashlib.sha256(large), inner=5)

        ratio = large_ns / small_ns
        assert 20 < ratio < 500, f"100x the data cost x{ratio:.1f}; quadratic would be x10,000"


class TestUpdateIsLinearAndStateless:
    """`hash.update(data)` | O(n) | O(1): each byte is absorbed once and
    chunking changes nothing."""

    def test_chunked_updates_equal_one_call(self) -> None:
        streamed = hashlib.sha256()
        streamed.update(b"hello")
        streamed.update(b" world")

        assert streamed.digest() == hashlib.sha256(b"hello world").digest()

    def test_an_update_allocates_nothing_for_the_data(self) -> None:
        h = hashlib.sha256()

        peak = peak_bytes(lambda: h.update(TEN_MB))

        assert peak < 10_000, f"update() over 10 MB allocated {peak} bytes"

    @pytest.mark.timing
    def test_a_hundred_times_the_data_costs_far_more(self) -> None:
        small, large = b"x" * 10_000, b"x" * 1_000_000
        h = hashlib.sha256()

        small_ns = best_ns(lambda: h.update(small), inner=5)
        large_ns = best_ns(lambda: h.update(large), inner=5)

        ratio = large_ns / small_ns
        assert 20 < ratio < 500, f"100x the data cost x{ratio:.1f}; quadratic would be x10,000"


class TestDigestIsASnapshot:
    """`digest()`, `hexdigest()` | O(k) and `copy()` | O(b): the state is
    copied and the copy finalized, so nothing depends on what was absorbed."""

    def test_a_digest_does_not_consume_the_object(self) -> None:
        h = hashlib.sha256(b"hello")
        first = h.digest()

        assert h.digest() == first
        h.update(b" world")
        assert h.digest() == hashlib.sha256(b"hello world").digest()

    def test_hexdigest_is_twice_the_digest_size(self) -> None:
        h = hashlib.sha512(b"x")

        assert len(h.hexdigest()) == 2 * h.digest_size == 128
        assert bytes.fromhex(h.hexdigest()) == h.digest()

    def test_the_attributes(self) -> None:
        h = hashlib.sha256()

        assert (h.name, h.digest_size, h.block_size) == ("sha256", 32, 64)

    def test_a_copy_diverges_from_its_original(self) -> None:
        base = hashlib.sha256(b"ab")
        branch = base.copy()

        branch.update(b"c")

        assert base.digest() == hashlib.sha256(b"ab").digest()
        assert branch.digest() == hashlib.sha256(b"abc").digest()

    def test_a_copy_allocates_the_same_whatever_was_absorbed(self) -> None:
        small = hashlib.sha256(b"x" * 10)
        large = hashlib.sha256(TEN_MB)

        small_peak = peak_bytes(small.copy)
        large_peak = peak_bytes(large.copy)

        assert abs(large_peak - small_peak) < 1_000, f"copy() peaks: {small_peak} vs {large_peak}"

    @pytest.mark.timing
    @pytest.mark.parametrize("method", ["digest", "hexdigest", "copy"])
    def test_the_cost_ignores_what_was_absorbed(self, method: str) -> None:
        small = hashlib.sha256(b"x" * 10)
        large = hashlib.sha256(TEN_MB)

        small_ns = best_ns(getattr(small, method), inner=100)
        large_ns = best_ns(getattr(large, method), inner=100)

        ratio = large_ns / small_ns
        assert ratio < 3, f"{method}() after 10 MB cost x{ratio:.2f} of after 10 bytes"


class TestShakeOutputIsLinear:
    """`shake.digest(length)` | O(L) | O(L): squeezing is linear in the bytes
    asked for, and a longer request extends a shorter one."""

    def test_the_length_is_chosen_per_call(self) -> None:
        xof = hashlib.shake_128(b"seed")

        assert xof.digest_size == 0
        assert len(xof.digest(16)) == 16
        assert xof.digest(1_000)[:16] == xof.digest(16)
        assert len(xof.hexdigest(1_000)) == 2_000
        assert bytes.fromhex(xof.hexdigest(40)) == xof.digest(40)

    def test_the_output_is_what_is_allocated(self) -> None:
        xof = hashlib.shake_128(b"seed")

        peak = peak_bytes(lambda: xof.digest(1_000_000))

        assert 900_000 < peak < 5_000_000, f"a 1,000,000-byte digest peaked at {peak} bytes"

    @pytest.mark.timing
    def test_a_long_output_costs_its_length(self) -> None:
        xof = hashlib.shake_128(b"seed")

        short_ns = best_ns(lambda: xof.digest(32), inner=10)
        long_ns = best_ns(lambda: xof.digest(1_000_000), inner=3)

        ratio = long_ns / short_ns
        assert 100 < ratio < 100_000, (
            f"31,250x the output cost x{ratio:.1f}; quadratic would be x10^9"
        )


class TestBlake2Parameters:
    """`blake2b(...)` | O(n) | O(b): key, salt and person fold into the state
    at construction, a key costing one block; the limits are class attributes."""

    def test_the_class_constants(self) -> None:
        b, s = hashlib.blake2b, hashlib.blake2s

        assert (b.MAX_DIGEST_SIZE, b.MAX_KEY_SIZE, b.SALT_SIZE, b.PERSON_SIZE) == (64, 64, 16, 16)
        assert (s.MAX_DIGEST_SIZE, s.MAX_KEY_SIZE, s.SALT_SIZE, s.PERSON_SIZE) == (32, 32, 8, 8)

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"key": b"k" * 65}, "key length"),
            ({"salt": b"s" * 17}, "salt length"),
            ({"person": b"p" * 17}, "person length"),
            ({"digest_size": 0}, "between 1 and 64"),
            ({"digest_size": 65}, "between 1 and 64"),
        ],
    )
    def test_each_limit_raises_one_byte_over(self, kwargs: dict[str, Any], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            hashlib.blake2b(**kwargs)

    def test_the_parameters_change_the_digest(self) -> None:
        plain = hashlib.blake2b(b"m").digest()

        assert hashlib.blake2b(b"m", key=b"k").digest() != plain
        assert hashlib.blake2b(b"m", salt=b"s").digest() != plain
        assert hashlib.blake2b(b"m", person=b"p").digest() != plain

    def test_digest_size_sets_the_output_length(self) -> None:
        short = hashlib.blake2b(b"m", digest_size=16)

        assert len(short.digest()) == short.digest_size == 16
        assert short.digest() != hashlib.blake2b(b"m").digest()[:16]

    @pytest.mark.timing
    def test_a_key_costs_a_block_not_the_message(self) -> None:
        message = b"m" * 1_000_000
        key = b"k" * 64

        plain_ns = best_ns(lambda: hashlib.blake2b(message), inner=3)
        keyed_ns = best_ns(lambda: hashlib.blake2b(message, key=key), inner=3)

        ratio = keyed_ns / plain_ns
        assert ratio < 1.5, f"a 64-byte key on 1 MB cost x{ratio:.2f} of the unkeyed hash"


class TestPbkdf2:
    """`pbkdf2_hmac()` | O(m + c·(s + i)) | O(m + s + dklen): each output block absorbs
    the salt once and iterates i times; the password is keyed once."""

    PASSWORD = b"pw"
    SALT = b"salt"

    @staticmethod
    def derive(**overrides: Any) -> Callable[[], bytes]:
        kwargs: dict[str, Any] = {
            "hash_name": "sha256",
            "password": TestPbkdf2.PASSWORD,
            "salt": TestPbkdf2.SALT,
            "iterations": 1_000,
        }
        kwargs.update(overrides)
        return lambda: hashlib.pbkdf2_hmac(**kwargs)

    def test_dklen_defaults_to_the_digest_size(self) -> None:
        assert len(self.derive(hash_name="sha512", iterations=1)()) == 64
        assert len(self.derive(iterations=1, dklen=48)()) == 48

    def test_a_longer_dklen_keeps_block_one(self) -> None:
        one_block = self.derive()()
        two_blocks = self.derive(dklen=48)()

        assert len(one_block) == 32
        assert two_blocks[:32] == one_block

    def test_zero_iterations_or_zero_dklen_raise(self) -> None:
        with pytest.raises(ValueError, match="greater than 0"):
            self.derive(iterations=0)()
        with pytest.raises(ValueError, match="greater than 0"):
            self.derive(dklen=0)()

    def test_an_unknown_hash_name_raises(self) -> None:
        with pytest.raises(ValueError):
            self.derive(hash_name="nope")()

    @pytest.mark.timing
    def test_iterations_are_the_knob(self) -> None:
        few_ns = best_ns(self.derive(iterations=1_000), repeats=3)
        many_ns = best_ns(self.derive(iterations=100_000), repeats=3)

        ratio = many_ns / few_ns
        assert 30 < ratio < 500, (
            f"100x the iterations cost x{ratio:.1f}; quadratic would be x10,000"
        )

    @pytest.mark.timing
    def test_one_byte_past_the_digest_size_costs_a_whole_block(self) -> None:
        one_ns = best_ns(self.derive(iterations=10_000, dklen=32), repeats=3)
        two_ns = best_ns(self.derive(iterations=10_000, dklen=33), repeats=3)
        ten_ns = best_ns(self.derive(iterations=10_000, dklen=320), repeats=3)

        assert 1.5 < two_ns / one_ns < 4, f"dklen 33 cost x{two_ns / one_ns:.2f} of dklen 32"
        assert 5 < ten_ns / one_ns < 50, f"dklen 320 cost x{ten_ns / one_ns:.2f} of dklen 32"

    @pytest.mark.timing
    def test_the_password_is_keyed_once(self) -> None:
        big_password = b"p" * 2**20

        short_ns = best_ns(self.derive(), repeats=3)
        long_ns = best_ns(self.derive(password=big_password), repeats=3)
        one_block_ns = best_ns(self.derive(password=big_password, iterations=1), repeats=3)
        ten_blocks_ns = best_ns(
            self.derive(password=big_password, iterations=1, dklen=320), repeats=3
        )

        per_iteration = long_ns / short_ns
        per_block = ten_blocks_ns / one_block_ns
        assert per_iteration < 50, (
            f"a 1 MB password over 1,000 iterations cost x{per_iteration:.1f}"
        )
        assert per_block < 4, f"a 1 MB password over 10 blocks cost x{per_block:.2f} of over 1"

    @pytest.mark.timing
    def test_the_salt_is_absorbed_once_per_block(self) -> None:
        big_salt = b"s" * 2**20

        short_ns = best_ns(self.derive(), repeats=3)
        long_ns = best_ns(self.derive(salt=big_salt), repeats=3)
        one_block_ns = best_ns(self.derive(salt=big_salt, iterations=1, dklen=32), repeats=3)
        ten_blocks_ns = best_ns(self.derive(salt=big_salt, iterations=1, dklen=320), repeats=3)

        per_iteration = long_ns / short_ns
        per_block = ten_blocks_ns / one_block_ns
        assert per_iteration < 50, f"a 1 MB salt over 1,000 iterations cost x{per_iteration:.1f}"
        assert 4 < per_block < 40, f"a 1 MB salt over 10 blocks cost x{per_block:.1f} of over 1"


class TestScrypt:
    """`scrypt()` | O(N·r·p) | O(r·(N + p)): each parameter scales the time on
    its own, and the memory cap rejects a request before allocating."""

    PASSWORD = b"pw"
    SALT = b"salt"

    @classmethod
    def derive(cls, **overrides: Any) -> Callable[[], bytes]:
        kwargs: dict[str, Any] = {"salt": cls.SALT, "n": 2**12, "r": 8, "p": 1}
        kwargs.update(overrides)
        return lambda: hashlib.scrypt(cls.PASSWORD, **kwargs)

    def test_dklen_defaults_to_64(self) -> None:
        assert len(self.derive(n=2)()) == 64
        assert len(self.derive(n=2, dklen=16)()) == 16

    def test_the_default_cap_rejects_64_mib(self) -> None:
        with pytest.raises(ValueError, match="memory limit"):
            self.derive(n=2**16)()

    def test_raising_the_cap_admits_it(self) -> None:
        assert len(self.derive(n=2**16, maxmem=2**27)()) == 64

    def test_n_must_be_a_power_of_two(self) -> None:
        with pytest.raises(ValueError, match="power of 2"):
            self.derive(n=3)()

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("parameter", "small", "large", "floor", "ceiling"),
        [("n", 2**10, 2**14, 8, 100), ("r", 1, 8, 4, 40), ("p", 1, 8, 4, 40)],
    )
    def test_each_parameter_scales_the_time(
        self, parameter: str, small: int, large: int, floor: float, ceiling: float
    ) -> None:
        small_ns = best_ns(self.derive(**{parameter: small}), repeats=3)
        large_ns = best_ns(self.derive(**{parameter: large}), repeats=3)

        ratio = large_ns / small_ns
        assert floor < ratio < ceiling, f"{parameter} {small} to {large} cost x{ratio:.1f}"


def file_digest(fileobj: Any, digest: Any) -> Any:
    """`hashlib.file_digest()`, reached at run time: typeshed's 3.10 stubs lack it."""
    return hashlib.file_digest(fileobj, digest)  # type: ignore[attr-defined]


class CountingFile:
    """A binary file wrapper that counts `readinto()` calls."""

    def __init__(self, inner: io.BufferedReader) -> None:
        self._inner = inner
        self.calls = 0

    def readinto(self, buffer: bytearray) -> int | None:
        self.calls += 1
        return self._inner.readinto(buffer)

    def readable(self) -> bool:
        return True


@pytest.mark.skipif(sys.version_info < (3, 11), reason="file_digest() was added in 3.11")
class TestFileDigest:
    """`file_digest(fileobj, digest)` | O(n) | O(1): one fixed buffer from the
    current position; a `BytesIO` is hashed whole from its own buffer."""

    SIZE = 8 * 2**20

    @pytest.fixture
    def blob(self, tmp_path: pathlib.Path) -> tuple[pathlib.Path, bytes]:
        payload = os.urandom(self.SIZE)
        path = tmp_path / "blob.bin"
        path.write_bytes(payload)
        return path, payload

    def test_it_matches_the_one_shot_digest(self, blob: tuple[pathlib.Path, bytes]) -> None:
        path, payload = blob

        with path.open("rb") as f:
            by_name = file_digest(f, "sha256")
        with path.open("rb") as f:
            by_constructor = file_digest(f, hashlib.sha256)

        assert by_name.digest() == by_constructor.digest() == hashlib.sha256(payload).digest()
        assert by_name.name == "sha256"

    def test_it_reads_from_the_current_position(self, blob: tuple[pathlib.Path, bytes]) -> None:
        path, payload = blob

        with path.open("rb") as f:
            f.seek(100)
            digest = file_digest(f, "sha256")

        assert digest.digest() == hashlib.sha256(payload[100:]).digest()

    def test_a_file_goes_through_one_fixed_buffer(self, blob: tuple[pathlib.Path, bytes]) -> None:
        path, _ = blob

        with path.open("rb") as f:
            peak = peak_bytes(lambda: file_digest(f, "sha256"))
        with path.open("rb") as f:
            counting = CountingFile(f)
            file_digest(counting, "sha256")

        assert 200_000 < peak < 1_000_000, f"an 8 MB file peaked at {peak} bytes"
        assert counting.calls == self.SIZE // 2**18 + 1, f"{counting.calls} readinto() calls"

    def test_a_bytesio_is_hashed_whole_whatever_its_position(self) -> None:
        payload = os.urandom(1_000)
        buffer = io.BytesIO(payload)
        buffer.seek(100)

        assert file_digest(buffer, "sha256").digest() == hashlib.sha256(payload).digest()

    def test_a_bytesio_sharing_its_bytes_is_copied_once(self) -> None:
        payload = os.urandom(self.SIZE)
        shared = io.BytesIO(payload)  # `payload` keeps a second reference
        sole = io.BytesIO(os.urandom(self.SIZE))  # the BytesIO holds the only one
        owned = io.BytesIO()
        owned.write(payload)

        first = peak_bytes(lambda: file_digest(shared, "sha256"))
        second = peak_bytes(lambda: file_digest(shared, "sha256"))
        unshared = peak_bytes(lambda: file_digest(sole, "sha256"))
        written = peak_bytes(lambda: file_digest(owned, "sha256"))

        assert first > self.SIZE, f"the shared bytes were not copied: peak {first}"
        assert second < 50_000, f"the second call peaked at {second} bytes"
        assert unshared < 50_000, f"a sole-reference BytesIO peaked at {unshared} bytes"
        assert written < 50_000, f"a written BytesIO peaked at {written} bytes"

    def test_a_text_stream_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="binary"):
            file_digest(io.StringIO("text"), "sha256")


def _usable_cpus() -> int:
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:  # pragma: no cover - not Linux
        return os.cpu_count() or 1


@pytest.mark.timing
@pytest.mark.skipif(_usable_cpus() < 2, reason="parallel speedup needs two CPUs")
class TestUpdateReleasesTheGil:
    """`update()` from 2048 bytes runs without the GIL: large buffers hash in
    parallel across threads, small updates do not."""

    THREADS = 4

    @classmethod
    def sequential_and_parallel(cls, work: Callable[[], None]) -> tuple[float, float]:
        def sequential() -> None:
            for _ in range(cls.THREADS):
                work()

        def parallel() -> None:
            threads = [threading.Thread(target=work) for _ in range(cls.THREADS)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        return best_ns(sequential, repeats=3), best_ns(parallel, repeats=3)

    def test_large_updates_run_in_parallel(self) -> None:
        blob = b"x" * (16 * 2**20)

        def work() -> None:
            hashlib.sha256().update(blob)

        sequential_ns, parallel_ns = self.sequential_and_parallel(work)

        ratio = parallel_ns / sequential_ns
        assert ratio < 0.8, f"4 threads over 16 MB each took x{ratio:.2f} of sequential"

    def test_small_updates_do_not(self) -> None:
        chunk = b"x" * 1_000

        def work() -> None:
            h = hashlib.sha256()
            for _ in range(8_000):
                h.update(chunk)

        sequential_ns, parallel_ns = self.sequential_and_parallel(work)

        ratio = parallel_ns / sequential_ns
        assert ratio > 0.8, f"4 threads of 1,000-byte updates took x{ratio:.2f} of sequential"


class TestAlgorithmNames:
    """`algorithms_guaranteed` and `algorithms_available` are sets; the first
    is the 14 names on the page and a subset of the second."""

    def test_the_guaranteed_fourteen(self) -> None:
        assert hashlib.algorithms_guaranteed == set(GUARANTEED)

    def test_available_is_a_superset(self) -> None:
        assert isinstance(hashlib.algorithms_guaranteed, set)
        assert isinstance(hashlib.algorithms_available, set)
        assert hashlib.algorithms_guaranteed <= hashlib.algorithms_available


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
    """Each block runs in its own subprocess and working directory, so the
    files it creates cannot leak between blocks, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        skipped: list[int] = []
        for line, source in _blocks():
            if "file_digest(" in source and sys.version_info < (3, 11):
                skipped.append(line)  # file_digest() was added in 3.11
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran + len(skipped) == EXPECTED_BLOCKS
        assert len(skipped) == (FILE_DIGEST_BLOCKS if sys.version_info < (3, 11) else 0), skipped
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        needle = "assert len(first) == h.digest_size == 32"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, needle.replace("32", "33"), 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
