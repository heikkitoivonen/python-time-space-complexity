"""Tests for docs/stdlib/numbers.md.

The page prices two things: what `isinstance()` costs against the numeric
ABCs, and what each mixin method costs in calls to the abstract methods a
subclass supplies. Both are settled by counting. Probe subclasses of
`numbers.Number` count how often the ABC machinery reaches their
`__subclasshook__`, and recording subclasses of each ABC count their abstract
method calls. Only `Rational.__float__()`, the one mixin whose cost is not a
count of calls, is settled by traced allocation and a stopwatch.

Measurement scope:

* Runtime checks: a first negative check of a fresh class against `Number`
  reaches each of 1 and of 50 probe subclasses once, a repeat reaches none,
  and after an unrelated `Integral.register()` the next check reaches each
  again; a probe ABC registered on `Number` is reached the same way, which
  shows the registry walk. A class registered on a probe is found by a first
  check against `Number` that enters the probe's `__subclasscheck__` once,
  and a repeat enters it no more, which shows `Number`'s positive cache. A first positive check of a class registered on
  `Integral` reaches none of the probes, which come after `Complex` in
  `Number.__subclasses__()`, so the walk stops at the match. The traced peak
  of a first negative check against `Number` grows more than 50x when 20,000
  empty subclasses are added to the tower. `register()` bumps
  `abc.get_cache_token()` for a new class and leaves it alone for a class that
  already is a subclass. A class defining every method `Real` asks for, but
  not registered, is not a `Real`, and each ABC's `__subclasshook__` returns
  `NotImplemented`.
* The registrations: `int` (and `bool` through it) on `Integral`, `float` on
  `Real`, `complex` on `Complex`, `Decimal` on `Number` and not `Complex`;
  `Fraction` is a subclass of `Rational`. Registered classes are checked to
  receive no mixin.
* `Number` has no abstract methods, sets `__hash__ = None`, and a subclass of
  it is unhashable. Each lower ABC's abstract methods are asserted to be
  exactly those the page's rows list.
* Mixins, on recording subclasses: `bool(z)` is one `__eq__`, or one `__ne__`
  and no `__eq__` when the subclass defines `__ne__`; `z - w` is one
  `w.__neg__` and one `z.__add__`, `5 - z` one `z.__neg__` and one
  `__add__`, logged with receivers and arguments: `z - w` negates `w` and
  adds the result to `z`, `5 - z` negates `z` and adds `5` to the object the
  negation returned, which is the result.
  `Real.real` and `Real.conjugate()` are one `__pos__`,
  `Real.imag` is `0` with no call, `complex(x)` one `__float__`,
  `divmod(x, 5)` one `__floordiv__` and one `__mod__`, `divmod(5, x)` one
  `__rfloordiv__` and one `__rmod__`. `float(q)` on a `Rational` reads
  `numerator` and `denominator` once each. `operator.index(i)` and
  `float(i)` on an `Integral` are one `__int__` each, `Integral.numerator`
  one `__pos__`, `Integral.denominator` is `1` with no call.
* `Rational.__float__()`: `Fraction.__float__` is that function. On
  fractions whose numerator and denominator are random integers of 10,000,
  100,000 and 1,000,000 bits, each 10x step costs more than 4x the time,
  and less than 40x, where a constant-time conversion would give 1x and a
  quadratic one 100x; the traced peak grows more than 20x and less than 400x
  from 10,000 to 1,000,000 bits.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The L factor of the first-check bound, and the order MRO, registry,
  subclasses, are read from `_abc__abc_subclasscheck_impl` in
  Modules/_abc.c, where each step's `PyType_IsSubtype` scans the checked
  class's MRO; the tests count the registry and subclass terms, not L.
* `register()` is priced at two `issubclass()` checks, read from
  `_abc__abc_register_impl`; the tests show its effect on the token.
* Each abstract method is counted as O(1); the pages of the concrete types
  price the real ones. `float(i)` on an `Integral` is priced as one
  `__int__` plus `float()` of an int, which reads the int's top digits and
  scans its low digits only while they are zero (`_PyLong_Frexp` in
  Objects/longobject.c); only the call count is tested.
* `Rational.__float__()` is measured on terms of equal size with a finite
  quotient; a quotient that overflows or underflows, and terms of very
  different sizes, are not varied.
* Lib/numbers.py is unchanged in behaviour from 3.10 to 3.14, so the page has
  no version-bounded row.
"""

from __future__ import annotations

import abc
import gc
import numbers
import operator
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "numbers.md"
EXPECTED_BLOCKS = 6

PROPERTIES = {"real", "imag", "numerator", "denominator"}


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


class Calls:
    """A call counter shared by the recording classes below."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def hit(self, name: str) -> None:
        self.counts[name] = self.counts.get(name, 0) + 1

    def reset(self) -> None:
        self.counts.clear()

    def __getitem__(self, name: str) -> int:
        return self.counts.get(name, 0)


def concrete(base: Any, calls: Calls, **methods: Any) -> Any:
    """A subclass of `base` whose unsupplied abstract methods record a call and
    return the instance, so a mixin's calls can be counted."""
    namespace: dict[str, Any] = {}
    for name in base.__abstractmethods__:
        if name in methods:
            continue

        def stub(self: Any, *args: Any, _name: str = name) -> Any:
            calls.hit(_name)
            return self

        namespace[name] = property(stub) if name in PROPERTIES else stub
    namespace.update(methods)
    return type(f"Recording{base.__name__}", (base,), namespace)


@pytest.fixture(autouse=True)
def _collect_local_classes() -> Iterator[None]:
    """Drop the tower subclasses a test defined, so later first checks against
    `Number` do not walk them."""
    yield
    gc.collect()


class TestRuntimeChecks:
    """`isinstance()` | O(1) on a class already checked, O(L·(1 + R + S)) the
    first time; `register()` bumps the token for a new relationship only."""

    @staticmethod
    def probes(calls: Calls, count: int) -> list[type]:
        def hook(cls: type, candidate: type) -> Any:
            calls.hit("probe")
            return NotImplemented

        return [
            type(f"Probe{index}", (numbers.Number,), {"__subclasshook__": classmethod(hook)})
            for index in range(count)
        ]

    @pytest.mark.parametrize("count", [1, 50])
    def test_a_miss_walks_every_subclass_once_and_is_cached(self, count: int) -> None:
        calls = Calls()
        probes = self.probes(calls, count)

        class Unrelated:
            pass

        assert not issubclass(Unrelated, numbers.Number)
        assert calls["probe"] == count, "the first check reaches every subclass"

        assert not isinstance(Unrelated(), numbers.Number)
        assert calls["probe"] == count, "the negative answer is cached"
        del probes

    def test_an_unrelated_register_stales_the_negative_cache(self) -> None:
        calls = Calls()
        probes = self.probes(calls, 3)

        class Unrelated:
            pass

        class Other:
            pass

        assert not issubclass(Unrelated, numbers.Number)
        assert calls["probe"] == 3

        numbers.Integral.register(Other)
        assert not issubclass(Unrelated, numbers.Number)
        assert calls["probe"] == 6, "a register() on another ABC drops Number's negative cache"

        assert not issubclass(Unrelated, numbers.Number)
        assert calls["probe"] == 6
        del probes

    def test_a_miss_consults_the_registry(self) -> None:
        calls = Calls()

        class Registered(metaclass=abc.ABCMeta):  # noqa: B024
            @classmethod
            def __subclasshook__(cls, candidate: type) -> Any:
                calls.hit("registered")
                return NotImplemented

        class Unrelated:
            pass

        numbers.Number.register(Registered)
        calls.reset()

        assert not issubclass(Unrelated, numbers.Number)
        assert calls["registered"] == 1

        assert not issubclass(Unrelated, numbers.Number)
        assert calls["registered"] == 1

    def test_a_hit_stops_at_the_match(self) -> None:
        calls = Calls()

        class Virtual:
            pass

        numbers.Integral.register(Virtual)
        probes = self.probes(calls, 5)
        subclasses = numbers.Number.__subclasses__()
        assert subclasses.index(numbers.Complex) < subclasses.index(probes[0])

        assert issubclass(Virtual, numbers.Number)
        assert calls["probe"] == 0, "the walk stopped in Complex's subtree"
        del probes

    def test_a_hit_is_cached(self) -> None:
        calls = Calls()

        class CountingMeta(abc.ABCMeta):
            def __subclasscheck__(cls, candidate: type) -> bool:
                calls.hit("entered")
                return super().__subclasscheck__(candidate)

        probe = CountingMeta("Probe", (numbers.Number,), {})

        class Virtual:
            pass

        probe.register(Virtual)
        calls.reset()

        assert issubclass(Virtual, numbers.Number)
        assert calls["entered"] == 1, "the walk entered the probe that registers it"
        assert isinstance(Virtual(), numbers.Number)
        assert calls["entered"] == 1, "Number answered from its own cache, walking nothing"
        del probe

    def test_the_first_check_allocates_with_the_tower(self) -> None:
        def first_check() -> int:
            fresh = type("Fresh", (), {})
            return peak_bytes(lambda: issubclass(fresh, numbers.Number))

        first_check()
        small = first_check()
        extra = [type(f"Extra{index}", (numbers.Number,), {}) for index in range(20_000)]
        try:
            large = first_check()
        finally:
            del extra
            gc.collect()

        assert large > small * 50, f"20,000 more subclasses: {small} to {large} bytes"

    def test_register_bumps_the_token_for_a_new_class_only(self) -> None:
        class Fresh:
            pass

        before = abc.get_cache_token()
        numbers.Real.register(Fresh)
        after = abc.get_cache_token()
        assert after != before
        assert isinstance(Fresh(), numbers.Real)

        numbers.Real.register(float)
        numbers.Real.register(Fraction)
        assert abc.get_cache_token() == after

    def test_no_abc_looks_for_methods(self) -> None:
        duck_methods = {name: (lambda self, *args: 0) for name in numbers.Real.__abstractmethods__}
        duck = type("Duck", (), duck_methods)

        assert not issubclass(duck, numbers.Real)
        for cls in (
            numbers.Number,
            numbers.Complex,
            numbers.Real,
            numbers.Rational,
            numbers.Integral,
        ):
            assert cls.__subclasshook__(duck) is NotImplemented


class TestTheTower:
    """The registrations each row names, and what each ABC leaves abstract."""

    def test_the_registrations(self) -> None:
        assert issubclass(int, numbers.Integral) and issubclass(bool, numbers.Integral)
        assert issubclass(float, numbers.Real) and not issubclass(float, numbers.Rational)
        assert issubclass(complex, numbers.Complex) and not issubclass(complex, numbers.Real)
        assert issubclass(Decimal, numbers.Number) and not issubclass(Decimal, numbers.Complex)
        assert numbers.Rational in Fraction.__mro__

    def test_registered_classes_get_no_mixins(self) -> None:
        assert numbers.Integral not in int.__mro__
        assert numbers.Real not in float.__mro__
        assert numbers.Complex not in complex.__mro__
        assert numbers.Number not in Decimal.__mro__

    def test_number_is_the_unhashable_root(self) -> None:
        assert numbers.Number.__abstractmethods__ == frozenset()
        assert numbers.Number.__hash__ is None

        scalar = type("Scalar", (numbers.Number,), {})

        with pytest.raises(TypeError, match="unhashable"):
            hash(scalar())

    def test_each_abc_adds_the_abstract_methods_its_rows_list(self) -> None:
        complex_ = {
            "__complex__",
            "__add__",
            "__radd__",
            "__mul__",
            "__rmul__",
            "__truediv__",
            "__rtruediv__",
            "__pow__",
            "__rpow__",
            "__neg__",
            "__pos__",
            "__abs__",
            "__eq__",
            "real",
            "imag",
            "conjugate",
        }
        real = {
            "__float__",
            "__trunc__",
            "__floor__",
            "__ceil__",
            "__round__",
            "__floordiv__",
            "__rfloordiv__",
            "__mod__",
            "__rmod__",
            "__lt__",
            "__le__",
        }
        rational = {"numerator", "denominator"}
        integral = {
            "__int__",
            "__lshift__",
            "__rlshift__",
            "__rshift__",
            "__rrshift__",
            "__and__",
            "__rand__",
            "__xor__",
            "__rxor__",
            "__or__",
            "__ror__",
            "__invert__",
        }

        assert numbers.Complex.__abstractmethods__ == complex_
        real_mixins = {"real", "imag", "conjugate", "__complex__"}
        # Real supplies those; Rational supplies __float__;
        # Integral supplies numerator and denominator.
        assert numbers.Real.__abstractmethods__ == complex_ - real_mixins | real
        assert numbers.Rational.__abstractmethods__ == (
            numbers.Real.__abstractmethods__ - {"__float__"} | rational
        )
        assert numbers.Integral.__abstractmethods__ == (
            numbers.Rational.__abstractmethods__ - rational | integral
        )


class TestComplexMixins:
    """`bool(z)` is one `!=`; `z - w` and `w - z` are one negation and one
    addition."""

    def test_bool_is_one_eq(self) -> None:
        calls = Calls()

        def eq(self: Any, other: Any) -> bool:
            calls.hit("__eq__")
            return False

        z = concrete(numbers.Complex, calls, __eq__=eq)()
        calls.reset()

        assert bool(z) is True
        assert calls.counts == {"__eq__": 1}

    def test_bool_is_one_ne_when_the_subclass_defines_it(self) -> None:
        calls = Calls()

        def eq(self: Any, other: Any) -> bool:
            calls.hit("__eq__")
            return True

        def ne(self: Any, other: Any) -> bool:
            calls.hit("__ne__")
            return False

        z = concrete(numbers.Complex, calls, __eq__=eq, __ne__=ne)()
        calls.reset()

        assert bool(z) is False
        assert calls.counts == {"__ne__": 1}

    @staticmethod
    def logged(events: list[tuple[str, Any, Any]]) -> Any:
        """A `Complex` whose negation returns a marker and whose addition logs
        its receiver and argument."""

        def neg(self: Any) -> Any:
            events.append(("neg", self, None))
            return ("negated", self)

        def add(self: Any, other: Any) -> Any:
            events.append(("add", self, other))
            return self

        def radd(self: Any, other: Any) -> Any:
            events.append(("radd", self, other))
            return self

        return concrete(numbers.Complex, Calls(), __neg__=neg, __add__=add, __radd__=radd)

    def test_sub_adds_the_negated_right_operand_to_self(self) -> None:
        events: list[tuple[str, Any, Any]] = []
        recording = self.logged(events)
        z, w = recording(), recording()

        _ = z - w

        assert events == [("neg", w, None), ("add", z, ("negated", w))]

    def test_rsub_adds_the_left_operand_to_the_negated_self(self) -> None:
        events: list[tuple[str, Any, Any]] = []
        recording = self.logged(events)
        z = recording()

        negated: list[Any] = []

        class Negated:
            def __add__(self, other: Any) -> Any:
                events.append(("add", self, other))
                return self

        def neg(self: Any) -> Any:
            events.append(("neg", self, None))
            negated.append(Negated())
            return negated[-1]

        recording.__neg__ = neg

        result = 5 - z

        assert events == [("neg", z, None), ("add", negated[0], 5)]
        assert result is negated[0]


class TestRealMixins:
    """`real` and `conjugate()` are one `+self`, `imag` is `0`, `complex(x)`
    one `__float__`, `divmod()` one `//` and one `%`."""

    @staticmethod
    def real(calls: Calls) -> Any:
        def to_float(self: Any) -> float:
            calls.hit("__float__")
            return 1.5

        instance = concrete(numbers.Real, calls, __float__=to_float)()
        calls.reset()
        return instance

    def test_real_and_conjugate_are_one_pos(self) -> None:
        calls = Calls()
        x = self.real(calls)

        assert x.real is x
        assert calls.counts == {"__pos__": 1}
        calls.reset()
        assert x.conjugate() is x
        assert calls.counts == {"__pos__": 1}

    def test_imag_is_the_constant_zero(self) -> None:
        calls = Calls()
        x = self.real(calls)

        assert x.imag == 0
        assert calls.counts == {}

    def test_complex_is_one_float(self) -> None:
        calls = Calls()
        x = self.real(calls)

        assert complex(x) == 1.5 + 0j
        assert calls.counts == {"__float__": 1}

    def test_divmod_is_one_floordiv_and_one_mod(self) -> None:
        calls = Calls()
        x = self.real(calls)

        assert divmod(x, 5) == (x, x)
        assert calls.counts == {"__floordiv__": 1, "__mod__": 1}

    def test_rdivmod_is_one_rfloordiv_and_one_rmod(self) -> None:
        calls = Calls()
        x = self.real(calls)

        assert divmod(5, x) == (x, x)
        assert calls.counts == {"__rfloordiv__": 1, "__rmod__": 1}


class TestRationalFloat:
    """`float(q)` | O(d) | O(d): one read of each term, then an int true
    division of the whole terms; `Fraction` inherits it."""

    def test_it_reads_each_term_once(self) -> None:
        calls = Calls()

        def term(value: int, name: str) -> property:
            def read(self: Any) -> int:
                calls.hit(name)
                return value

            return property(read)

        q = concrete(
            numbers.Rational, calls, numerator=term(1, "numerator"), denominator=term(4, "den")
        )()
        calls.reset()

        assert float(q) == 0.25
        assert calls.counts == {"numerator": 1, "den": 1}

    def test_fraction_inherits_it(self) -> None:
        assert Fraction.__float__ is numbers.Rational.__float__  # pyright: ignore[reportUnknownMemberType]

    @staticmethod
    def fraction(bits: int) -> Fraction:
        rng = random.Random(bits)
        numerator = rng.getrandbits(bits) | 1 << (bits - 1)
        denominator = rng.getrandbits(bits) | 1 << (bits - 1) | 1
        return Fraction(numerator, denominator)

    def test_allocation_follows_the_digits(self) -> None:
        peaks = []
        for bits in (10_000, 1_000_000):
            q = self.fraction(bits)
            float(q)
            peaks.append(peak_bytes(lambda q=q: float(q)))  # type: ignore[misc]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 400, f"100x the bits: {peaks} bytes"

    @pytest.mark.timing
    def test_time_follows_the_digits(self) -> None:
        durations = []
        for bits in (10_000, 100_000, 1_000_000):
            q = self.fraction(bits)
            durations.append(best_ns(lambda q=q: float(q)))  # type: ignore[misc]

        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]
        assert all(4 < ratio < 40 for ratio in ratios), (
            f"10x the bits per step: {durations} ns, ratios {ratios}; linear predicts 10x, quadratic 100x"
        )


class TestIntegralMixins:
    """`operator.index(i)` and `float(i)` are one `__int__`; `numerator` is
    one `+self`; `denominator` is `1`."""

    @staticmethod
    def integral(calls: Calls) -> Any:
        def to_int(self: Any) -> int:
            calls.hit("__int__")
            return 7

        instance = concrete(numbers.Integral, calls, __int__=to_int)()
        calls.reset()
        return instance

    def test_index_and_float_are_one_int(self) -> None:
        calls = Calls()
        i = self.integral(calls)

        assert operator.index(i) == 7
        assert calls.counts == {"__int__": 1}
        assert float(i) == 7.0
        assert calls.counts == {"__int__": 2}

    def test_numerator_is_one_pos_and_denominator_is_one(self) -> None:
        calls = Calls()
        i = self.integral(calls)

        assert i.numerator is i
        assert calls.counts == {"__pos__": 1}
        calls.reset()
        assert i.denominator == 1
        assert calls.counts == {}


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
    """Each block runs in its own subprocess, so a registration in one cannot
    reach another, and asserts its own result."""

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
        target = "assert not isinstance(Decimal('1.5'), numbers.Real)"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert isinstance(Decimal('1.5'), numbers.Real)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
