"""Tests for docs/stdlib/crypt.md.

The page prices one `crypt.crypt()` call by the method its salt names: linear
in the rounds and the word for SHA-crypt, in the rounds alone for bcrypt, in
the word alone for MD5-crypt, and constant for DES. Growth in the rounds and
the word is settled by timing three sizes a constant step apart; the rest by
observation: a counting stand-in for the C call shows `mksalt()` hashes
nothing, a raising `mksalt()` shows a string salt is passed through, equal
hashes for words that share a prefix show where a method stops reading, and a
traced peak shows the Python side's space.

`crypt` exists on Python 3.10 to 3.12 and is gone from 3.13, so every runtime
test is skipped on 3.13 and later; there, only the availability boundary and
the page's block count are checked. `Lib/crypt.py` differs between 3.10.19,
3.11.14 and 3.12.12 only in the deprecation warning 3.11 adds, which is
asserted on each side of the boundary. The C call behind it comes from the C
library, so the runtime tests are guarded to Linux, whose libxcrypt provides
all five methods and returns failure tokens; the page's examples assume it
too.

Measurement scope:

* SHA-512 and SHA-256 at 1,000, 10,000 and 100,000 rounds, word of two
  characters: each 10x step in rounds costs between 4x and 25x. At 1,000
  and at 10,000 rounds, with words of 5, 50 and 500 bytes, each 10x step
  costs between 1.5x and 25x and the whole 100x step over 3x, where a cost
  independent of the word stays near 1x. The word's share holding at 10x the
  rounds is what separates r·w from r + w.
* bcrypt at 16, 128 and 1,024 rounds: each 8x step costs between 3x and 20x.
  A 72-byte word and the same word with more appended hash alike; 71 bytes
  and 72 do not.
* MD5-crypt with words of 5, 50 and 500 bytes: each 10x step costs between
  1.5x and 25x and the whole step over 3x. `rounds` raises `ValueError`
  for MD5 and DES.
* DES: 8-byte words hash alike with anything appended; 7 bytes and 8 do not.
* Space: for each method, the traced Python peak of a warmed call, least of
  three, is the same within 64 bytes for words of 1 and 500 bytes, and under
  1 KB.
* `mksalt()` with a counting stand-in for the C call makes no calls, for
  every method, with and without `rounds`. The salts it returns at the
  default rounds have one length per method, and none is longer than 36
  characters at the largest rounds. They carry `rounds=N$` for SHA-crypt
  (none by default), `NN$` as log2 of the rounds for bcrypt (`12$` by
  default), and a `ValueError` for SHA rounds of 999 and 1,000,000,000 and
  bcrypt rounds of 8, 3,000 and 2**32.
* `crypt()` with no salt uses `methods[0]` and default rounds; with a
  `METHOD_*` value it builds a salt of that method; with a string it does not
  call `mksalt()`, and a stored hash reproduces itself. `methods` is
  SHA-512, SHA-256, bcrypt, MD5, DES in that order, and the same list on
  every access.
* A salt of `!!`, and a word of 512 bytes (256 two-byte characters), return
  a string starting with `*`; 511 ASCII bytes and 510 UTF-8 bytes hash.
  Hashing with a failure token as the salt does not return that token.
* Importing warns on 3.11 and 3.12 and not on 3.10, checked in a
  subprocess.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The module is removed from Python 3.13, so no claim on the page is checked
  on 3.13 or 3.14; the removal itself is the availability test.
* Which methods other C libraries support, and whether they raise `OSError`
  where libxcrypt returns a failure token: the module turns a NULL from
  `crypt(3)` into `OSError` (`Modules/_cryptmodule.c` at v3.12.12), and
  whether a given library returns NULL is up to it. The Windows import
  failure is in `Lib/crypt.py`, and no supported CI job runs 3.10 to 3.12
  there.
* The C library's own working memory: `Modules/_cryptmodule.c` at v3.12.12
  hands `crypt_r()` a fixed-size `struct crypt_data` on the stack, which
  tracemalloc does not see.
* MD5-crypt's fixed 1,000 rounds and the default of 5,000 SHA rounds come
  from libxcrypt and the official documentation, and are not timed; the SHA
  default is not written into the salt.
* bcrypt's cost is not varied in words shorter than 72 bytes, MD5's and
  SHA-crypt's not in words over 500 bytes, and no word is non-ASCII except
  in the 512-byte failure case. `hashlib` and `hmac`, named in the page's
  advice and Related Modules, are priced on their own pages.
"""

from __future__ import annotations

import functools
import importlib
import importlib.util
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "crypt.md"
EXPECTED_BLOCKS = 4

crypt: Any = None
if sys.version_info < (3, 13) and sys.platform == "linux":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        crypt = importlib.import_module("crypt")

REQUIRES_CRYPT = pytest.mark.skipif(
    sys.version_info >= (3, 13), reason="crypt was removed in Python 3.13"
)
REQUIRES_LIBXCRYPT = pytest.mark.skipif(
    sys.platform != "linux",
    reason="libxcrypt, Linux's crypt(3), has all five methods and failure tokens",
)
NEEDS_MODULE = [REQUIRES_CRYPT, REQUIRES_LIBXCRYPT]


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


def hash_ns(word: str, salt: str) -> float:
    return best_ns(lambda: crypt.crypt(word, salt))


def assert_linear_steps(label: str, times: list[float], step: int) -> None:
    """Each step of `step`x in size costs between a fraction of it and a
    few times it: far from both 1x (constant) and step**2 (quadratic)."""
    ratios = [later / earlier for earlier, later in pairwise(times)]
    assert all(step * 0.4 < r < step * 2.5 for r in ratios), (label, times, ratios)


class TestAvailability:
    """The page's scope: present on 3.10 to 3.12, removed from 3.13."""

    def test_the_module_exists_only_before_313(self) -> None:
        found = importlib.util.find_spec("crypt") is not None
        assert found == (sys.version_info < (3, 13))

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="crypt was removed in Python 3.13")
    @pytest.mark.skipif(sys.platform == "win32", reason="crypt refuses to import on Windows")
    def test_import_warns_from_311(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import crypt"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if sys.version_info >= (3, 11):
            assert result.returncode != 0
            assert "DeprecationWarning" in result.stderr
        else:
            assert result.returncode == 0, result.stderr


class TestMethods:
    """`crypt.methods` lists what the C library supports, strongest first, and
    `crypt()` without a salt uses the first."""

    pytestmark = NEEDS_MODULE

    def test_libxcrypt_lists_all_five_strongest_first(self) -> None:
        assert crypt.methods == [
            crypt.METHOD_SHA512,
            crypt.METHOD_SHA256,
            crypt.METHOD_BLOWFISH,
            crypt.METHOD_MD5,
            crypt.METHOD_CRYPT,
        ]
        assert crypt.methods is crypt.methods

    def test_no_salt_means_the_first_method_with_default_rounds(self) -> None:
        hashed = crypt.crypt("secret")
        assert hashed.startswith("$6$")
        assert "rounds=" not in hashed
        assert len(hashed) == crypt.METHOD_SHA512.total_size

    def test_a_method_value_builds_a_salt_of_that_method(self) -> None:
        for method in crypt.methods:
            hashed = crypt.crypt("secret", method)
            assert len(hashed) == method.total_size, method
            if method.ident:
                assert hashed.startswith(f"${method.ident}$"), method

    def test_a_string_salt_is_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stored = crypt.crypt("secret", crypt.mksalt(crypt.METHOD_SHA512, rounds=1000))

        def refuse(*args: object, **kwargs: object) -> str:
            raise AssertionError("mksalt() called for a string salt")

        monkeypatch.setattr(crypt, "mksalt", refuse)
        assert crypt.crypt("secret", stored) == stored
        assert crypt.crypt("wrong", stored) != stored


class TestMksaltHashesNothing:
    """Row: `crypt.mksalt()` is O(1) and hashes nothing; `rounds` is written
    into the salt or rejected with `ValueError`."""

    pytestmark = NEEDS_MODULE

    def test_no_hash_is_computed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, str]] = []
        monkeypatch.setattr(crypt._crypt, "crypt", lambda word, salt: calls.append((word, salt)))
        for method in crypt.methods:
            crypt.mksalt(method)
        crypt.mksalt(crypt.METHOD_SHA512, rounds=999_999_999)
        crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=1 << 31)
        assert calls == []

    def test_the_salt_length_is_bounded(self) -> None:
        for method in crypt.methods:
            assert len({len(crypt.mksalt(method)) for _ in range(50)}) == 1, method
        longest = [
            crypt.mksalt(crypt.METHOD_SHA512, rounds=999_999_999),
            crypt.mksalt(crypt.METHOD_SHA256, rounds=999_999_999),
            crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=1 << 31),
        ]
        assert max(map(len, longest)) <= 36, longest

    def test_rounds_are_written_into_the_salt(self) -> None:
        assert crypt.mksalt(crypt.METHOD_SHA512, rounds=20_000).startswith("$6$rounds=20000$")
        assert crypt.mksalt(crypt.METHOD_SHA256, rounds=1000).startswith("$5$rounds=1000$")
        assert "rounds=" not in crypt.mksalt(crypt.METHOD_SHA512)
        assert crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=1 << 8).startswith("$2b$08$")
        assert crypt.mksalt(crypt.METHOD_BLOWFISH).startswith("$2b$12$")

    @pytest.mark.parametrize(
        ("method", "rounds"),
        [
            ("METHOD_SHA512", 999),
            ("METHOD_SHA256", 1_000_000_000),
            ("METHOD_BLOWFISH", 8),
            ("METHOD_BLOWFISH", 3000),
            ("METHOD_BLOWFISH", 1 << 32),
            ("METHOD_MD5", 10_000),
            ("METHOD_CRYPT", 10_000),
        ],
    )
    def test_bad_rounds_raise(self, method: str, rounds: int) -> None:
        with pytest.raises(ValueError, match="rounds"):
            crypt.mksalt(getattr(crypt, method), rounds=rounds)


@pytest.mark.timing
class TestCostByMethod:
    """Rows under Cost by method: SHA-crypt O(r·w), bcrypt O(r), MD5-crypt
    O(w). Three sizes a constant step apart, each step checked against both
    constant and quadratic growth."""

    pytestmark = NEEDS_MODULE

    @pytest.mark.parametrize("method", ["METHOD_SHA512", "METHOD_SHA256"])
    def test_sha_crypt_is_linear_in_rounds(self, method: str) -> None:
        m = getattr(crypt, method)
        times = [hash_ns("pw", crypt.mksalt(m, rounds=r)) for r in (1_000, 10_000, 100_000)]
        assert_linear_steps(method, times, 10)

    @pytest.mark.parametrize(
        ("method", "rounds"),
        [
            ("METHOD_SHA512", 1_000),
            ("METHOD_SHA512", 10_000),
            ("METHOD_SHA256", 1_000),
            ("METHOD_SHA256", 10_000),
            ("METHOD_MD5", None),
        ],
    )
    def test_cost_is_linear_in_the_word(self, method: str, rounds: int | None) -> None:
        salt = crypt.mksalt(getattr(crypt, method), rounds=rounds)
        times = [hash_ns("x" * w, salt) for w in (5, 50, 500)]
        ratios = [later / earlier for earlier, later in pairwise(times)]
        assert all(1.5 < r < 25 for r in ratios), (method, rounds, times, ratios)
        assert times[2] / times[0] > 3, (method, rounds, times)

    def test_bcrypt_is_linear_in_rounds(self) -> None:
        times = [
            hash_ns("pw", crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=r)) for r in (16, 128, 1024)
        ]
        assert_linear_steps("bcrypt", times, 8)


class TestTruncatingMethods:
    """DES reads 8 bytes of the word and bcrypt 72."""

    pytestmark = NEEDS_MODULE

    def test_des_reads_eight_bytes(self) -> None:
        salt = crypt.mksalt(crypt.METHOD_CRYPT)
        assert crypt.crypt("password", salt) == crypt.crypt("password-and-more", salt)
        assert crypt.crypt("passwor", salt) != crypt.crypt("passwork", salt)

    def test_bcrypt_reads_72_bytes(self) -> None:
        salt = crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=16)
        assert crypt.crypt("x" * 72, salt) == crypt.crypt("x" * 72 + "ignored", salt)
        assert crypt.crypt("x" * 71, salt) != crypt.crypt("x" * 71 + "y", salt)


class TestSpaceIsConstant:
    """Every Space cell is O(1): the result's length is bounded by the method,
    and nothing on the Python side follows the word."""

    pytestmark = NEEDS_MODULE

    def test_the_peak_does_not_follow_the_word(self) -> None:
        for method in crypt.methods:
            salt = crypt.mksalt(method, rounds=1000 if method.ident in ("5", "6") else None)
            peaks = []
            for word in ("x", "x" * 500):
                call = functools.partial(crypt.crypt, word, salt)
                call()
                peaks.append(min(peak_bytes(call) for _ in range(3)))
            assert abs(peaks[1] - peaks[0]) < 64, (method, peaks)
            assert max(peaks) < 1024, (method, peaks)


class TestFailures:
    """libxcrypt returns a failure string starting with `*` for an unusable
    salt or a word of 512 bytes or more."""

    pytestmark = NEEDS_MODULE

    def test_an_unusable_salt_returns_a_failure_token(self) -> None:
        token = crypt.crypt("secret", "!!")
        assert token.startswith("*")
        assert crypt.crypt("secret", token) != token

    def test_the_word_limit_is_512_bytes(self) -> None:
        salt = crypt.mksalt(crypt.METHOD_SHA512, rounds=1000)
        assert crypt.crypt("x" * 511, salt).startswith("$6$")
        assert crypt.crypt("x" * 512, salt).startswith("*")
        assert crypt.crypt("é" * 255, salt).startswith("$6$")
        assert crypt.crypt("é" * 256, salt).startswith("*")


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result, on
    the versions that still have the module and a C library with all five
    methods."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @REQUIRES_CRYPT
    @REQUIRES_LIBXCRYPT
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

    @REQUIRES_CRYPT
    @REQUIRES_LIBXCRYPT
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "'$2b$08$'" in s)
        mutated = source.replace("'$2b$08$'", "'$2b$09$'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
