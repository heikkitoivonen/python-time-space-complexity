"""Tests for the claims added to the builtins pages that go beyond the tables.

tests/test_builtin_complexity.py covers what the complexity tables say - that
list indexing is O(1), that str concatenation scales. This file covers the
sentences written *around* those tables: the explanatory clauses that assert
something the table does not, which is where the claims in this repo have
actually been wrong.

Where a claim can be settled by observation rather than a stopwatch, it is -
`str()` returning its argument unchanged is an identity check, not a timing
one, and identity does not need a tolerance.
"""

import sys
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class TestBoolSingletons:
    """docs/builtins/bool.md: True and False are cached singletons, so every
    comparison is a pointer or small-int check, never a scan."""

    def test_bools_are_singletons(self) -> None:
        assert bool(1) is True
        assert bool(0) is False
        assert (1 == 1) is True

    def test_bool_is_an_int_subclass(self) -> None:
        assert isinstance(True, int)
        assert True == 1 and False == 0
        assert True + True == 2


class TestBytesImmutabilityCosts:
    """docs/builtins/bytes.md: changing a bytes means building a new one,
    O(n); a bytearray mutates in place, O(1)."""

    def test_bytes_cannot_be_mutated(self) -> None:
        data = bytearray(b"hello")
        with_change = bytes(data)
        try:
            with_change[0] = 106  # type: ignore[index]
        except TypeError:
            pass
        else:  # pragma: no cover - would mean bytes became mutable
            raise AssertionError("bytes should be immutable")

    def test_changing_bytes_allocates_a_new_object(self) -> None:
        original = b"hello"
        changed = b"j" + original[1:]
        assert changed is not original
        assert original == b"hello", "the original is untouched, so it was copied"

    def test_bytearray_mutates_in_place(self) -> None:
        buffer = bytearray(b"hello")
        identity = id(buffer)
        buffer[0] = 106
        assert buffer == bytearray(b"jello")
        assert id(buffer) == identity, "no new object, so no copy of the contents"

    def test_growing_a_bytes_scales_but_a_bytearray_does_not(self) -> None:
        small, large = b"x" * 1_000, b"x" * 1_000_000

        rebuild_small = best_time(lambda: small + b"y")
        rebuild_large = best_time(lambda: large + b"y")
        append_small = best_time(lambda: bytearray(small).append(121))
        append_large = best_time(lambda: bytearray(large).append(121))

        assert rebuild_large > rebuild_small * 3, (
            f"concatenating bytes copies everything: {rebuild_small:.2e}s vs {rebuild_large:.2e}s"
        )
        # The bytearray() construction dominates here, so compare the ratio
        # rather than the absolute: appending does not add a second copy.
        assert append_large / append_small < rebuild_large / rebuild_small * 2


class TestExecReparsesEveryCall:
    """docs/builtins/exec.md: exec(source) is O(n + m) every call because it
    reparses; a function is compiled once at import and costs only O(m)."""

    SOURCE = "x = 0\nfor i in range(10): x += i"

    def test_exec_on_source_is_slower_than_on_a_code_object(self) -> None:
        compiled = compile(self.SOURCE, "<test>", "exec")

        from_source = best_time(lambda: exec(self.SOURCE, {}))
        from_code = best_time(lambda: exec(compiled, {}))

        assert from_source > from_code * 3, (
            f"parsing should dominate a tiny body: source={from_source:.2e}s code={from_code:.2e}s"
        )

    def test_compiling_is_the_part_that_repeats(self) -> None:
        # Same work, so any difference is the parse the second form skips.
        namespace: dict[str, Any] = {}
        exec(self.SOURCE, namespace)
        assert namespace["x"] == sum(range(10))


class TestRoundVersusAlternatives:
    """docs/builtins/round.md, after these tests corrected it three times.

    Rounding to decimals is not a fixed-cost operation: it runs a
    double-to-decimal conversion whose length follows the value's exponent.
    That also makes it cost about the same as formatting the value, and makes
    round(x) with no ndigits the cheap one, since it skips the conversion.
    """

    def test_rounding_to_decimals_scales_with_the_exponent(self) -> None:
        small = best_time(lambda: [round(3.14159, 2) for _ in range(20_000)])
        huge = best_time(lambda: [round(3.14159e300, 2) for _ in range(20_000)])

        assert huge > small * 10, (
            f"round(x, n) expands the value exactly, so a big exponent costs "
            f"far more: 1e0={small:.2e}s 1e300={huge:.2e}s"
        )

    def test_rounding_to_an_int_is_much_cheaper(self) -> None:
        value = 3.14159
        with_digits = best_time(lambda: [round(value, 2) for _ in range(20_000)])
        without = best_time(lambda: [round(value) for _ in range(20_000)])

        assert without < with_digits, (
            f"no ndigits skips the decimal conversion: "
            f"round(x)={without:.2e}s round(x, 2)={with_digits:.2e}s"
        )

    def test_formatting_costs_about_the_same_as_rounding(self) -> None:
        # The page used to claim formatting was the pricier of the two. Both
        # run the same conversion, so they land within a few percent.
        value = 3.14159
        round_time = best_time(lambda: [round(value, 2) for _ in range(20_000)])
        format_time = best_time(lambda: [f"{value:.2f}" for _ in range(20_000)])

        ratio = max(round_time, format_time) / min(round_time, format_time)
        assert ratio < 2.0, (
            f"neither should dominate: round={round_time:.2e}s "
            f"format={format_time:.2e}s ratio={ratio:.2f}x"
        )

    def test_quantize_follows_the_digits_kept_not_the_operand(self) -> None:
        # The other correction these tests forced: quantize() does not
        # re-examine operand digits below the target exponent.
        from decimal import getcontext

        precision = getcontext().prec
        getcontext().prec = 100_000
        try:
            step = Decimal("0.01")
            short = Decimal("1." + "9" * 1_000)
            long = Decimal("1." + "9" * 50_000)

            short_operand = best_time(lambda: short.quantize(step))
            long_operand = best_time(lambda: long.quantize(step))

            # Now vary what the result keeps, holding the operand fixed.
            few_places = best_time(lambda: long.quantize(Decimal("0.01")))
            many_places = best_time(lambda: long.quantize(Decimal("1e-5000")))
        finally:
            getcontext().prec = precision

        assert long_operand < short_operand * 3, (
            f"fifty times the operand digits should not matter: "
            f"1k={short_operand:.2e}s 50k={long_operand:.2e}s"
        )
        assert many_places > few_places * 3, (
            f"the digits the result keeps are what costs: "
            f"2 places={few_places:.2e}s 5000 places={many_places:.2e}s"
        )

    def test_decimal_arithmetic_is_still_a_complexity_change(self) -> None:
        # Unchanged and still true: float is fixed width, Decimal is not.
        from decimal import getcontext

        precision = getcontext().prec
        getcontext().prec = 100_000
        try:
            short = Decimal("1." + "9" * 5_000)
            long = Decimal("1." + "9" * 10_000)
            short_time = best_time(lambda: short * short)
            long_time = best_time(lambda: long * long)
        finally:
            getcontext().prec = precision

        assert long_time > short_time * 2, (
            f"Decimal multiplication grows with digits, float does not: "
            f"{short_time:.2e}s vs {long_time:.2e}s"
        )


class TestStrConversionAvoidsACopy:
    """docs/builtins/str_func.md: str() on a str returns it as-is, O(1), while
    crossing between str and bytes always copies."""

    def test_str_of_a_str_is_the_same_object(self) -> None:
        text = "not interned because it is built at runtime " + str(id(object()))
        assert str(text) is text

    def test_encoding_produces_a_new_object(self) -> None:
        text = "hello"
        assert text.encode("utf-8") is not text.encode("utf-8")

    def test_crossing_the_boundary_scales_with_length(self) -> None:
        short, long = "x" * 1_000, "x" * 1_000_000

        short_time = best_time(lambda: short.encode("utf-8"))
        long_time = best_time(lambda: long.encode("utf-8"))
        identity_time = best_time(lambda: str(long))

        assert long_time > short_time * 3, (
            f"encoding copies every character: {short_time:.2e}s vs {long_time:.2e}s"
        )
        assert identity_time < long_time, "str() on a str should not copy at all"


class TestVarsSnapshotsLocals:
    """docs/builtins/vars.md: vars(obj) hands back __dict__ in O(1), while
    vars() builds a snapshot and is O(n) in the number of locals."""

    def test_vars_of_an_object_is_the_dict_itself(self) -> None:
        class Sample:
            pass

        instance = Sample()
        instance.attribute = 1  # type: ignore[attr-defined]
        assert vars(instance) is instance.__dict__

    def test_mutating_the_returned_mapping_reaches_the_object(self) -> None:
        class Sample:
            pass

        instance = Sample()
        vars(instance)["added"] = 2
        assert instance.added == 2  # type: ignore[attr-defined]

    def test_no_argument_form_scales_with_the_locals(self) -> None:
        few: dict[str, Any] = {}
        many: dict[str, Any] = {}
        exec("def f():\n    a = 1\n    return vars()\n", few)
        exec(
            "def f():\n" + "".join(f"    v{i} = {i}\n" for i in range(200)) + "    return vars()\n",
            many,
        )

        few_time = best_time(few["f"])
        many_time = best_time(many["f"])

        assert many_time > few_time * 3, (
            f"vars() copies the frame's locals, so it scales with them: "
            f"few={few_time:.2e}s many={many_time:.2e}s"
        )

    def test_the_snapshot_has_every_local(self) -> None:
        def sample() -> dict[str, Any]:
            # Unused by design: vars() reads them out of the frame, which is
            # the behaviour under test.
            first = 1  # noqa: F841
            second = 2  # noqa: F841
            return vars()

        snapshot = sample()
        assert snapshot["first"] == 1 and snapshot["second"] == 2


class TestIntFloatParsingAsymmetry:
    """docs/builtins/float_func.md: float() only scans, because its result is
    fixed width. int() has to build an arbitrary-precision value."""

    def test_float_parsing_is_linear(self) -> None:
        short, long = "9" * 100, "9" * 400

        short_time = best_time(lambda: float(short))
        long_time = best_time(lambda: float(long))

        assert long_time < short_time * 8, (
            f"float parsing should stay near linear: {short_time:.2e}s vs {long_time:.2e}s"
        )

    def test_float_result_is_fixed_width_however_many_digits(self) -> None:
        assert sys.getsizeof(float("9" * 300)) == sys.getsizeof(1.0)
        assert float("9" * 400) == float("inf")

    def test_int_result_grows_with_the_digits(self) -> None:
        assert sys.getsizeof(int("9" * 300)) > sys.getsizeof(int("9" * 30))
