"""Tests to verify documented behaviour of the struct module.

All fifteen code blocks on docs/stdlib/struct.md run. Two claims did not
survive measurement, and they contradicted each other across the page:

* "Compiling format every time / Recompile each time" - the module-level
  functions cache compiled formats, so a repeated format is parsed once
  either way. Pre-compiling saves the cache lookup, about 15%, and saves the
  parse only when formats churn past the cache.
* "pack(): O(n) for n fields (linear in data size)" conflates two terms.
  Field count dominates: '100i' and '400s' both produce 400 bytes, and the
  hundred-field version costs about five times the single-field one.

An earlier commit corrected the first claim in the complexity table and left
the same claim standing in the Optimization Tips section, which is how the
page came to argue with itself.
"""

import struct
import timeit
from collections.abc import Callable
from typing import Any

import pytest


def per_call(func: Callable[[], Any], number: int = 100_000) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(func, number=number, repeat=5)) / number


class TestFormatCaching:
    """The module caches compiled formats; pre-compiling saves the lookup."""

    def test_a_repeated_format_is_not_reparsed(self) -> None:
        """A cached call beats one that rebuilds the Struct every time.

        A long format is used so the parse is a large share of the work: at
        one field the two are within 30% and the comparison went flaky under
        full-suite load, at four hundred the gap is 2.4x.
        """
        fmt = "i" * 400
        values = tuple(range(400))
        struct.pack(fmt, *values)  # warm the cache

        cached = per_call(lambda: struct.pack(fmt, *values), number=20_000)
        rebuilt = per_call(lambda: struct.Struct(fmt).pack(*values), number=20_000)

        assert rebuilt > cached * 1.5, (
            f"if the module call re-parsed, rebuilding would cost the same: "
            f"cached {cached:.2e}s rebuilt {rebuilt:.2e}s"
        )

    def test_precompiling_saves_only_the_lookup(self) -> None:
        prepared = struct.Struct("i")

        module_time = per_call(lambda: struct.pack("i", 7))
        struct_time = per_call(lambda: prepared.pack(7))

        assert struct_time < module_time, "pre-compiling should still win"
        assert struct_time > module_time / 2, (
            f"but by the cache lookup, not a whole parse: module {module_time:.2e}s "
            f"prepared {struct_time:.2e}s"
        )

    def test_the_saving_is_real_when_formats_churn(self) -> None:
        formats = ["i" * count for count in range(2, 60)]
        values = {fmt: tuple(range(len(fmt))) for fmt in formats}
        prepared = [struct.Struct(fmt) for fmt in formats]

        def cold() -> None:
            struct._clearcache()  # type: ignore[attr-defined]
            for fmt in formats:
                struct.pack(fmt, *values[fmt])

        def warm() -> None:
            for built, fmt in zip(prepared, formats, strict=True):
                built.pack(*values[fmt])

        cold_time = per_call(cold, number=200)
        warm_time = per_call(warm, number=200)

        assert cold_time > warm_time * 2, (
            f"with the cache cleared the parse dominates: cold {cold_time:.2e}s "
            f"warm {warm_time:.2e}s"
        )


class TestFieldCountDominates:
    """The table's O(k) in fields, plus a cheaper term in bytes."""

    def test_same_bytes_more_fields_costs_more(self) -> None:
        many = struct.Struct("100i")  # 100 fields, 400 bytes
        one = struct.Struct("400s")  # 1 field, 400 bytes
        assert many.size == one.size == 400

        many_time = per_call(lambda: many.pack(*range(100)))
        one_time = per_call(lambda: one.pack(b"x" * 400))

        assert many_time > one_time * 2, (
            f"identical output size, and the field count is what costs: "
            f"100 fields {many_time:.2e}s, 1 field {one_time:.2e}s"
        )

    def test_bytes_still_count_but_less(self) -> None:
        small = struct.Struct("400s")
        large = struct.Struct("40000s")

        small_time = per_call(lambda: small.pack(b"x" * 400), number=50_000)
        large_time = per_call(lambda: large.pack(b"x" * 40_000), number=20_000)

        assert large_time > small_time, "copying more bytes is not free"
        assert large_time < small_time * 100, (
            f"but a hundred times the bytes should cost far less than a "
            f"hundred times: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_unpack_splits_the_same_way(self) -> None:
        many = struct.Struct("100i")
        one = struct.Struct("400s")
        many_data, one_data = many.pack(*range(100)), one.pack(b"x" * 400)

        many_time = per_call(lambda: many.unpack(many_data))
        one_time = per_call(lambda: one.unpack(one_data))

        assert many_time > one_time * 2, (
            f"unpack builds one tuple element per field: "
            f"100 fields {many_time:.2e}s, 1 field {one_time:.2e}s"
        )


class TestSizeAndBufferOperations:
    """calcsize() and the *_into / *_from pair."""

    def test_calcsize_matches_what_pack_produces(self) -> None:
        for fmt in ("i", "3i", "10s", "<ihb", "!IH"):
            built = struct.Struct(fmt)
            assert struct.calcsize(fmt) == built.size

    def test_pack_into_writes_without_allocating_output(self) -> None:
        buffer = bytearray(16)
        identity = id(buffer)

        struct.pack_into("4i", buffer, 0, 1, 2, 3, 4)

        assert id(buffer) == identity, "written in place, so O(1) extra space"
        assert struct.unpack_from("4i", buffer, 0) == (1, 2, 3, 4)

    def test_unpack_from_reads_at_an_offset(self) -> None:
        packed = struct.pack("2i", 7, 9) + struct.pack("2i", 11, 13)
        assert struct.unpack_from("2i", packed, 8) == (11, 13)

    def test_a_short_buffer_is_rejected_before_unpacking(self) -> None:
        with pytest.raises(struct.error, match="requires a buffer"):
            struct.unpack("i", b"AB")

    def test_an_invalid_format_is_rejected_while_parsing(self) -> None:
        with pytest.raises(struct.error):
            struct.pack("z", 42)


class TestByteOrderAffectsSizeNotCost:
    """The page documents the modifiers; native alignment changes the size."""

    def test_native_alignment_can_pad(self) -> None:
        assert struct.calcsize("@ci") >= struct.calcsize("=ci")
        assert struct.calcsize("=ci") == 5, "standard sizes, no padding"

    def test_standard_sizes_are_fixed_across_byte_orders(self) -> None:
        for prefix in ("<", ">", "!", "="):
            assert struct.calcsize(f"{prefix}i") == 4
            assert struct.calcsize(f"{prefix}q") == 8

    def test_byte_order_does_not_change_the_cost(self) -> None:
        little = struct.Struct("<100i")
        big = struct.Struct(">100i")

        little_time = per_call(lambda: little.pack(*range(100)))
        big_time = per_call(lambda: big.pack(*range(100)))

        assert max(little_time, big_time) < min(little_time, big_time) * 3, (
            f"byte swapping is not a complexity change: "
            f"little {little_time:.2e}s big {big_time:.2e}s"
        )
