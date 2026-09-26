"""Tests for docs/stdlib/uuid.md.

A `UUID` holds one 128-bit integer, so almost every row on the page is
constant by construction and is settled by observation: which attributes are
properties, what each one returns, which source of randomness or node a
generator draws on, and how the values sort. Only two inputs grow - the
string handed to `UUID()` and the name handed to `uuid3()` and `uuid5()` -
and those are settled by timing at three sizes spanning two orders of
magnitude, with traced allocation for their space.

Measurement scope:

* `uuid3()` and `uuid5()` are timed on `str` names of 10,000, 100,000 and
  1,000,000 ASCII characters: every 10x step costs more than 4x and less than
  40x, which excludes both a constant and a quadratic. The traced peak for a
  1,000,000-character name exceeds 1,000,000 bytes, so the name is copied,
  and for a 1,000-character name it stays under 10,000. Known outputs for
  `NAMESPACE_DNS` and 'python.org' are asserted. A `bytes` name gives the
  same UUID as its `str` on 3.12+ and raises `TypeError` before 3.12,
  guarded on `sys.version_info`.
* `UUID(hex)` is timed on 32 hex digits behind 10,000, 100,000 and 1,000,000
  hyphens, which it accepts: every 10x step costs more than 4x and less than
  40x. Its space is a traced peak over `'x' * n + '-'`, which it rejects
  after copying: over 1,000,000 bytes at n = 1,000,000. A string without a
  separator to remove is not copied, so O(n) space is the bound, not every
  input's cost. Braces, hyphens and a `urn:uuid:` prefix are asserted
  optional, and a string without 32 hex digits raises `ValueError`.
* `uuid4()` is observed calling `os.urandom(16)` once through a recording
  replacement. `uuid8()` with its blocks omitted returns the same UUID twice
  after the same `random.seed()`, and with all three given returns the same
  UUID without consulting `random` (3.14+).
* `uuid1()` given a `node` succeeds with `getnode()` replaced by a function
  that raises; given only a `clock_seq` it takes its node from a replaced
  `getnode()`. `uuid6()` without a node does the same (3.14+). `getnode()`
  is observed with its private getter list replaced by one counting getter:
  one call on the first use, none on the second, the same value both times.
  With that list empty the random fallback is asserted to set bit 40, the
  multicast bit.
* Sort order: 20,000 `uuid7()` and 5,000 `uuid6()` values made in one
  process are already sorted (3.14+). With `time.time_ns()` replaced so the
  timestamp crosses a 2**32 boundary between two calls, `uuid1()` sorts the
  later value first and `uuid6()` the earlier. 1,000 `uuid4()` values are
  asserted not to be sorted.
* Every `UUID` attribute on the page is a `property` of the class, the
  instance has no `__dict__`, and `int` is stored. Text forms are 32, 36 and
  45 characters and `bytes` 16; `bytes_le` reverses the first three fields;
  `fields` matches the six single-field properties; `version` is `None` for
  a non-RFC 4122 variant; a version 7 `time` is within a second of the clock
  in milliseconds (3.14+). `is_safe` is `SafeUUID.unknown` for `uuid1()`
  given a node, `uuid3()`, `uuid4()`, `uuid5()`, a parsed string, and on
  3.14+ `uuid6()`, `uuid7()` and `uuid8()`. Equal UUIDs hash as their
  integer; `int=` and `fields=` are range-checked and `version=` overwrites
  the version and variant bits.
* The namespace constants are asserted by value, `NIL` and `MAX` by value on
  3.14+ and absent before it, the four variant strings as the values
  `UUID.variant` returns, and `SafeUUID` by its three member values.
* `python -m uuid` is run in a subprocess: on 3.12+ it prints one version 4
  UUID by default and the known `uuid5()` value for `-u uuid5 -n @dns -N
  python.org`; on 3.14+ `-C 3` prints three distinct UUIDs; before 3.12 it
  prints nothing.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The first call to `getnode()` may run `ip`, `ifconfig`, `arp`, `netstat` or
  `lanscan`, depending on the platform, or ask the platform's UUID library;
  which it does and what that costs belong to the operating system. The page
  says "may" and does not bound it. Which programs are tried per platform is
  read from `_OS_GETTERS` in Lib/uuid.py.
* Whether `uuid1()` without arguments uses the platform generator, and what
  `is_safe` that generator reports, depend on the libuuid the interpreter was
  built with (Linux and macOS) or on `UuidCreate` (Windows, where `uuid1()`
  never uses it). The tests assert only the paths that do not go through it.
* That the `python -m uuid` loop holds one UUID at a time is read from
  `main()` in Lib/uuid.py; the subprocess tests count lines, not memory.
* Reading `os.urandom()`, the clock and the platform's UUID generator is
  priced O(1) by the page's cost model.
* `uuid.main` (3.12+) is the command line's entry point. The official inventory does
  not list it, so the audit reports it for classification; the page covers it
  as the `python -m uuid` row.

Axes not varied: non-ASCII names for `uuid3()` and `uuid5()` (their UTF-8
length is m), `bytes` names in timing, strings with braces or a URN prefix in
timing, and sort order across processes or machines.
"""

from __future__ import annotations

import os
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import uuid
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "uuid.md"
EXPECTED_BLOCKS = 6

# 100-ns intervals between the UUID epoch (1582-10-15) and the Unix epoch.
UUID_EPOCH_OFFSET = 0x01B21DD213814000
PYTHON_ORG_V3 = "6fa459ea-ee8a-3ca4-894e-db77e160355e"
PYTHON_ORG_V5 = "886313e1-3b8a-5372-9b90-0c9aee199e5d"


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


def assert_linear(durations: list[float], label: str) -> None:
    """Each 10x step costs more than 4x (not constant) and less than 40x (not quadratic)."""
    ratios = [later / earlier for earlier, later in pairwise(durations)]
    assert all(4 < ratio < 40 for ratio in ratios), (
        f"{label}: 10x steps took {[f'{d:.0f}' for d in durations]} ns, "
        f"ratios {[f'{r:.1f}' for r in ratios]}"
    )


class TestNamedUUIDsHashTheName:
    """`uuid3` and `uuid5` | O(m) | O(m): the name is encoded, appended to the
    namespace's bytes, and hashed, so both time and space follow its length."""

    SIZES = (10_000, 100_000, 1_000_000)

    def test_known_values(self) -> None:
        assert str(uuid.uuid3(uuid.NAMESPACE_DNS, "python.org")) == PYTHON_ORG_V3
        assert str(uuid.uuid5(uuid.NAMESPACE_DNS, "python.org")) == PYTHON_ORG_V5

    @pytest.mark.parametrize("generate", [uuid.uuid3, uuid.uuid5])
    def test_the_same_inputs_give_the_same_uuid(self, generate: Any) -> None:
        first = generate(uuid.NAMESPACE_URL, "https://example.com/a")

        assert first == generate(uuid.NAMESPACE_URL, "https://example.com/a")
        assert first != generate(uuid.NAMESPACE_URL, "https://example.com/b")
        assert first != generate(uuid.NAMESPACE_DNS, "https://example.com/a")

    @pytest.mark.parametrize("generate", [uuid.uuid3, uuid.uuid5])
    def test_the_name_is_copied(self, generate: Any) -> None:
        short, long = "a" * 1_000, "a" * 1_000_000

        short_peak = peak_bytes(lambda: generate(uuid.NAMESPACE_DNS, short))
        long_peak = peak_bytes(lambda: generate(uuid.NAMESPACE_DNS, long))

        assert short_peak < 10_000, f"a 1,000-character name peaked at {short_peak} bytes"
        assert long_peak > 1_000_000, f"a 1,000,000-character name peaked at {long_peak} bytes"

    @pytest.mark.timing
    @pytest.mark.parametrize("generate", [uuid.uuid3, uuid.uuid5])
    def test_time_follows_the_name(self, generate: Any) -> None:
        names = ["a" * size for size in self.SIZES]

        durations = [
            best_ns(lambda name=name: generate(uuid.NAMESPACE_DNS, name), inner=3)  # type: ignore[misc]
            for name in names
        ]

        assert_linear(durations, generate.__name__)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="bytes names from 3.12")
    @pytest.mark.parametrize("generate", [uuid.uuid3, uuid.uuid5])
    def test_a_bytes_name_matches_its_string(self, generate: Any) -> None:
        assert generate(uuid.NAMESPACE_DNS, b"python.org") == generate(
            uuid.NAMESPACE_DNS, "python.org"
        )

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="bytes names from 3.12")
    @pytest.mark.parametrize("generate", [uuid.uuid3, uuid.uuid5])
    def test_a_bytes_name_raises_before_312(self, generate: Any) -> None:
        with pytest.raises(TypeError):
            generate(uuid.NAMESPACE_DNS, b"python.org")


class TestConstantTimeGenerators:
    """`uuid1`, `uuid4`, `uuid6`, `uuid7`, `uuid8` | O(1) | O(1): each draws on
    a fixed-size source - `os.urandom()`, the clock, `random` or `getnode()`."""

    def test_uuid4_reads_sixteen_bytes_from_urandom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        requests: list[int] = []
        real_urandom = os.urandom

        def recording_urandom(size: int) -> bytes:
            requests.append(size)
            return real_urandom(size)

        monkeypatch.setattr(os, "urandom", recording_urandom)

        value = uuid.uuid4()

        assert requests == [16]
        assert value.version == 4
        assert value.variant == uuid.RFC_4122

    def test_uuid1_with_a_node_never_calls_getnode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse() -> int:
            raise AssertionError("getnode() was called")

        monkeypatch.setattr(uuid, "getnode", refuse)

        value = uuid.uuid1(node=0x0123456789AB, clock_seq=0)

        assert value.node == 0x0123456789AB
        assert value.version == 1

    def test_uuid1_without_a_node_takes_it_from_getnode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(uuid, "getnode", lambda: 0x00000000BEEF)

        assert uuid.uuid1(clock_seq=0).node == 0x00000000BEEF

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid6 from 3.14")
    def test_uuid6_without_a_node_takes_it_from_getnode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(uuid, "getnode", lambda: 0x00000000BEEF)

        value = uuid.uuid6()  # type: ignore[attr-defined]

        assert value.node == 0x00000000BEEF
        assert value.version == 6

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid7 from 3.14")
    def test_uuid7_is_version_7(self) -> None:
        assert uuid.uuid7().version == 7  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid8 from 3.14")
    def test_uuid8_fills_omitted_blocks_from_random(self) -> None:
        state = random.getstate()
        try:
            random.seed(1234)
            first = uuid.uuid8()  # type: ignore[attr-defined]
            random.seed(1234)
            second = uuid.uuid8()  # type: ignore[attr-defined]
        finally:
            random.setstate(state)

        assert first == second
        assert first.version == 8

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid8 from 3.14")
    def test_uuid8_with_every_block_given_is_deterministic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(bits: int) -> int:
            raise AssertionError("random was consulted")

        monkeypatch.setattr(random, "getrandbits", refuse)

        value = uuid.uuid8(1, 2, 3)  # type: ignore[attr-defined]

        assert value == uuid.uuid8(1, 2, 3)  # type: ignore[attr-defined]
        assert value.version == 8


class TestGetnodeIsCached:
    """`getnode()`: the first call looks for a node, and later calls return it."""

    def test_the_second_call_does_not_look_again(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[None] = []

        def counting_getter() -> int:
            calls.append(None)
            return 0x0000DEADBEEF

        monkeypatch.setattr(uuid, "_node", None)
        monkeypatch.setattr(uuid, "_GETTERS", [counting_getter])

        first = uuid.getnode()
        assert len(calls) == 1
        second = uuid.getnode()

        assert len(calls) == 1
        assert first == second == 0x0000DEADBEEF

    def test_the_fallback_is_random_with_the_multicast_bit_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(uuid, "_node", None)
        monkeypatch.setattr(uuid, "_GETTERS", [])

        node = uuid.getnode()

        assert 0 <= node < 1 << 48
        assert node & (1 << 40)

    def test_the_real_node_is_48_bits_and_stable(self) -> None:
        node = uuid.getnode()

        assert 0 <= node < 1 << 48
        assert uuid.getnode() == node


class TestSortOrder:
    """UUIDs compare by their integer. `uuid6` and `uuid7` put the timestamp in
    the high bits and sort in creation order; `uuid1` puts the low 32 timestamp
    bits first and does not; `uuid4` is random."""

    @staticmethod
    def _ticks_before_wrap() -> int:
        """A clock reading, in `time_ns()` units, whose UUID timestamp has its low
        32 bits all set, so the next 100 ns tick carries into bit 32."""
        ticks = time.time_ns() // 100 + UUID_EPOCH_OFFSET
        wrap = (ticks | 0xFFFFFFFF) + 1
        return (wrap - 1 - UUID_EPOCH_OFFSET) * 100

    def _two_readings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        readings = [self._ticks_before_wrap()]
        readings.append(readings[0] + 100)
        monkeypatch.setattr(time, "time_ns", lambda: readings.pop(0))

    def test_uuid1_does_not_sort_by_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(uuid, "_last_timestamp", None)
        self._two_readings(monkeypatch)

        earlier = uuid.uuid1(node=1, clock_seq=0)
        later = uuid.uuid1(node=1, clock_seq=0)

        assert earlier.time < later.time
        assert later < earlier

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid6 from 3.14")
    def test_uuid6_sorts_by_time_across_the_same_carry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(uuid, "_last_timestamp_v6", None)
        self._two_readings(monkeypatch)

        earlier = uuid.uuid6(node=1, clock_seq=0)  # type: ignore[attr-defined]
        later = uuid.uuid6(node=1, clock_seq=0)  # type: ignore[attr-defined]

        assert earlier.time < later.time
        assert earlier < later

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid6 and uuid7 from 3.14")
    def test_uuid6_and_uuid7_sort_in_creation_order(self) -> None:
        sevens = [uuid.uuid7() for _ in range(20_000)]  # type: ignore[attr-defined]
        sixes = [uuid.uuid6() for _ in range(5_000)]  # type: ignore[attr-defined]

        assert sevens == sorted(sevens)
        assert len(set(sevens)) == len(sevens)
        assert sixes == sorted(sixes)

    def test_uuid4_is_not_in_creation_order(self) -> None:
        values = [uuid.uuid4() for _ in range(1_000)]

        assert values != sorted(values)


class TestParsingWalksTheString:
    """`UUID(hex)` | O(n) | O(n) | n = string length. Separators are removed
    before the 32-digit check, so a string of any length can be read."""

    SIZES = (10_000, 100_000, 1_000_000)
    DIGITS = "12345678123456781234567812345678"

    def test_braces_hyphens_and_urn_are_optional(self) -> None:
        expected = uuid.UUID(int=int(self.DIGITS, 16))

        assert uuid.UUID(self.DIGITS) == expected
        assert uuid.UUID("{12345678-1234-5678-1234-567812345678}") == expected
        assert uuid.UUID("urn:uuid:12345678-1234-5678-1234-567812345678") == expected

    def test_thirty_two_digits_must_remain(self) -> None:
        with pytest.raises(ValueError, match="badly formed"):
            uuid.UUID("not-a-uuid")
        with pytest.raises(ValueError, match="badly formed"):
            uuid.UUID(self.DIGITS + "0")

    def test_a_long_string_is_read_to_the_end(self) -> None:
        assert uuid.UUID("-" * 1_000_000 + self.DIGITS).hex == self.DIGITS

    def test_a_string_with_a_separator_is_copied(self) -> None:
        def reject(text: str) -> None:
            with pytest.raises(ValueError):
                uuid.UUID(text)

        short, long = "x" * 1_000 + "-", "x" * 1_000_000 + "-"

        short_peak = peak_bytes(lambda: reject(short))
        long_peak = peak_bytes(lambda: reject(long))

        assert short_peak < 20_000, f"1,001 characters peaked at {short_peak} bytes"
        assert long_peak > 1_000_000, f"1,000,001 characters peaked at {long_peak} bytes"

    @pytest.mark.timing
    def test_time_follows_the_string(self) -> None:
        texts = ["-" * size + self.DIGITS for size in self.SIZES]

        durations = [best_ns(lambda text=text: uuid.UUID(text), inner=3) for text in texts]  # type: ignore[misc]

        assert_linear(durations, "UUID(hex)")


class TestAttributesAreComputedFromTheInt:
    """Every `UUID` row other than the string constructor is O(1): the object
    stores the integer and `is_safe`, and every other attribute is a property."""

    VALUE = uuid.UUID("12345678-1234-5678-1234-567812345678")
    PROPERTIES = (
        "bytes",
        "bytes_le",
        "hex",
        "urn",
        "fields",
        "time_low",
        "time_mid",
        "time_hi_version",
        "clock_seq_hi_variant",
        "clock_seq_low",
        "node",
        "time",
        "clock_seq",
        "version",
        "variant",
    )

    def test_the_object_stores_the_int_and_nothing_else_of_size(self) -> None:
        assert not hasattr(self.VALUE, "__dict__")
        assert set(uuid.UUID.__slots__) - {"__weakref__"} == {"int", "is_safe"}
        assert self.VALUE.int is self.VALUE.int
        assert int(self.VALUE) == self.VALUE.int

    @pytest.mark.parametrize("name", PROPERTIES)
    def test_each_attribute_is_a_property(self, name: str) -> None:
        assert isinstance(vars(uuid.UUID)[name], property)

    def test_sizes_of_the_text_and_byte_forms(self) -> None:
        assert len(self.VALUE.bytes) == len(self.VALUE.bytes_le) == 16
        assert len(self.VALUE.hex) == 32
        assert len(str(self.VALUE)) == 36
        assert len(self.VALUE.urn) == 45
        assert self.VALUE.urn == "urn:uuid:" + str(self.VALUE)

    def test_bytes_le_reverses_the_first_three_fields(self) -> None:
        big = self.VALUE.bytes

        assert self.VALUE.bytes_le == big[3::-1] + big[5:3:-1] + big[7:5:-1] + big[8:]
        assert uuid.UUID(bytes_le=self.VALUE.bytes_le) == self.VALUE

    def test_fields_are_the_six_slices(self) -> None:
        value = self.VALUE

        assert value.fields == (
            value.time_low,
            value.time_mid,
            value.time_hi_version,
            value.clock_seq_hi_variant,
            value.clock_seq_low,
            value.node,
        )
        assert value.fields == (0x12345678, 0x1234, 0x5678, 0x12, 0x34, 0x567812345678)
        assert uuid.UUID(fields=value.fields) == value

    def test_version_is_none_outside_the_rfc_4122_variant(self) -> None:
        assert self.VALUE.variant == uuid.RESERVED_NCS
        assert self.VALUE.version is None
        assert uuid.uuid4().version == 4

    def test_uuid1_time_is_the_60_bit_timestamp(self) -> None:
        now = time.time_ns() // 100 + UUID_EPOCH_OFFSET

        stamped = uuid.uuid1(node=1, clock_seq=0).time

        assert abs(stamped - now) < 10_000_000  # one second in 100-ns ticks
        assert stamped < 1 << 60

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="uuid7 from 3.14")
    def test_uuid7_time_is_unix_milliseconds(self) -> None:
        now_ms = time.time_ns() // 1_000_000

        assert abs(uuid.uuid7().time - now_ms) < 1_000  # type: ignore[attr-defined]

    def test_is_safe_is_unknown_off_the_platform_path(self) -> None:
        generated = [
            uuid.uuid1(node=1, clock_seq=0),
            uuid.uuid3(uuid.NAMESPACE_DNS, "x"),
            uuid.uuid4(),
            uuid.uuid5(uuid.NAMESPACE_DNS, "x"),
            uuid.UUID(self.VALUE.hex),
        ]
        for name in ("uuid6", "uuid7", "uuid8"):  # 3.14+
            if hasattr(uuid, name):
                generated.append(getattr(uuid, name)())

        assert all(value.is_safe is uuid.SafeUUID.unknown for value in generated)

    def test_equality_and_hash_follow_the_int(self) -> None:
        twin = uuid.UUID(bytes=self.VALUE.bytes)

        assert twin == self.VALUE
        assert twin is not self.VALUE
        assert hash(twin) == hash(self.VALUE) == hash(self.VALUE.int)
        assert {self.VALUE: "found"}[twin] == "found"
        assert (uuid.UUID(int=1) < uuid.UUID(int=2)) is True

    def test_the_fixed_size_constructors_are_range_checked(self) -> None:
        with pytest.raises(ValueError):
            uuid.UUID(int=1 << 128)
        with pytest.raises(ValueError):
            uuid.UUID(fields=(1 << 32, 0, 0, 0, 0, 0))
        with pytest.raises(ValueError):
            uuid.UUID(bytes=b"\x00" * 15)

    def test_version_overwrites_the_version_and_variant_bits(self) -> None:
        value = uuid.UUID(int=(1 << 128) - 1, version=4)

        assert value.version == 4
        assert value.variant == uuid.RFC_4122


class TestConstants:
    """Namespaces, `NIL` and `MAX`, the variant strings and `SafeUUID`: each is
    an O(1) attribute read."""

    def test_the_namespaces(self) -> None:
        assert str(uuid.NAMESPACE_DNS) == "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        assert str(uuid.NAMESPACE_URL) == "6ba7b811-9dad-11d1-80b4-00c04fd430c8"
        assert str(uuid.NAMESPACE_OID) == "6ba7b812-9dad-11d1-80b4-00c04fd430c8"
        assert str(uuid.NAMESPACE_X500) == "6ba7b814-9dad-11d1-80b4-00c04fd430c8"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="NIL and MAX from 3.14")
    def test_nil_and_max(self) -> None:
        assert uuid.NIL.int == 0  # type: ignore[attr-defined]
        assert uuid.MAX.int == (1 << 128) - 1  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="NIL and MAX from 3.14")
    def test_nil_and_max_are_absent_before_314(self) -> None:
        assert not hasattr(uuid, "NIL")
        assert not hasattr(uuid, "MAX")

    def test_the_variant_strings_are_what_variant_returns(self) -> None:
        by_top_bits = {
            0x0: uuid.RESERVED_NCS,
            0x8: uuid.RFC_4122,
            0xC: uuid.RESERVED_MICROSOFT,
            0xE: uuid.RESERVED_FUTURE,
        }
        for top, expected in by_top_bits.items():
            assert uuid.UUID(int=top << 60).variant is expected

    def test_safeuuid_members(self) -> None:
        assert [member.value for member in uuid.SafeUUID] == [0, -1, None]
        assert uuid.SafeUUID.safe.value == 0
        assert uuid.SafeUUID.unsafe.value == -1
        assert uuid.SafeUUID.unknown.value is None


def _run_cli(*args: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "uuid", *args],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=True,
    )
    return result.stdout.splitlines()


class TestCommandLine:
    """`python -m uuid` | O(k) | O(1) | Python 3.12+; one `uuid4()` by default,
    k set by `-C` on 3.14+. Only the output is asserted, not the cost."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="command line from 3.12")
    def test_the_default_is_one_uuid4(self) -> None:
        lines = _run_cli()

        assert len(lines) == 1
        assert uuid.UUID(lines[0]).version == 4

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="command line from 3.12")
    def test_uuid5_with_a_named_namespace(self) -> None:
        assert _run_cli("-u", "uuid5", "-n", "@dns", "-N", "python.org") == [PYTHON_ORG_V5]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="-C from 3.14")
    def test_count_prints_that_many(self) -> None:
        lines = _run_cli("-C", "3")

        assert len(lines) == len(set(lines)) == 3

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="command line from 3.12")
    def test_there_is_no_command_line_before_312(self) -> None:
        assert _run_cli() == []


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
        line, source = next((n, s) for n, s in _blocks() if "u.version is None" in s)
        mutated = source.replace("u.version is None", "u.version == 4", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
