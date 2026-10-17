"""Tests for docs/builtins/isinstance.md.

isinstance() is object_recursive_isinstance in Objects/abstract.c. It returns
at once when type(obj) is exactly the class; an exact `type` goes to
object_isinstance, which scans type(obj).__mro__ in PyType_IsSubtype; a `|`
union is replaced by its args tuple; a tuple is walked entry by entry,
recursively, stopping at the first match; anything else calls the class's
`__instancecheck__`. ABCMeta's is _abc_instancecheck in Modules/_abc.c, which
consults a positive and a negative weak-set cache before walking the registry
and `__subclasses__()`. The function is unchanged across the v3.11.14,
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags apart from the name of an
attribute-lookup helper, so no version is treated apart.

Measurement scope:

* O(d) for a type: isinstance() against an unrelated class, on single-
  inheritance chains whose MRO holds 30 and 3,000 classes. The test accepts
  x10 to x1,000 for the hundredfold step: a constant-time claim predicts x1
  and a quadratic one x10,000;
* O(1) on an exact type: the same two chains, checked against their own
  class, differ by less than x3;
* O(k*d) and the short-circuit: a counting metaclass `__instancecheck__` on
  every candidate is called once per entry up to the first match and k
  times when nothing matches; a `|` union of the same classes makes the same
  calls;
* O(1) space: tracemalloc's peak for a negative check against a 3,000-class
  MRO and a 1,000-entry tuple is zero;
* ABC rows: a counting `__subclasshook__` inherited by an ABC and its 10
  subclasses runs 11 times on the first negative check of a class, once per
  ABC the walk visits, and not at all on the repeat; a positive answer is not recomputed after a register()
  elsewhere, a negative one is;
* the custom `__instancecheck__` row: the hook decides the answer, and it is
  not called when type(obj) is exactly the class;
* every stated example value, and every fenced block runs in a subprocess.

Not settled here:

* The d factor of a first ABC check is read from source, not measured: each
  ABC the walk visits tests the class's MRO with PyType_IsSubtype in
  _abc__abc_subclasscheck_impl, and the collections.abc hooks scan it in
  _collections_abc._check_methods.
* Nested tuples of classes are accepted and walked recursively; the page's
  k counts the classes of a flat tuple, and nesting is not priced.

* Not varied: MRO shape (every timed chain is single inheritance), the class
  matched (the timed negative case scans the whole MRO, which bounds every
  positive match), and objects whose `__class__` differs from type(obj), for
  which object_isinstance also checks `__class__`.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from abc import ABC
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "isinstance.md"
EXPECTED_BLOCKS = 17

SHALLOW = 30
DEEP = 3_000


def best_time(func: Callable[[], Any], repeats: int = 7, loops: int = 2_000) -> float:
    """The fastest of several runs of `loops` calls, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times) / loops


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc sees while `func` runs, after one warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def chain(length: int) -> type:
    """A single-inheritance class whose MRO holds `length` classes."""
    cls: type = object
    for index in range(length - 1):
        cls = type(f"Level{index}", (cls,), {})
    assert len(cls.__mro__) == length
    return cls


class Unrelated:
    pass


class CountingMeta(type):
    """A metaclass whose `__instancecheck__` records each call."""

    calls: list[str] = []

    def __instancecheck__(cls, instance: object) -> bool:
        CountingMeta.calls.append(cls.__name__)
        return type.__instancecheck__(cls, instance)


def counting_classes(count: int) -> list[type]:
    return [CountingMeta(f"K{index}", (), {}) for index in range(count)]


class TestPlainTypeScansTheMro:
    """Row: isinstance(obj, type) - O(d), O(1) when type(obj) is exactly the
    class. A negative answer scans the whole MRO, so its time grows with d;
    an exact match does not."""

    @pytest.mark.timing
    def test_a_negative_check_is_linear_in_the_mro_length(self) -> None:
        shallow = chain(SHALLOW)()
        deep = chain(DEEP)()

        ratio = best_time(lambda: isinstance(deep, Unrelated)) / best_time(
            lambda: isinstance(shallow, Unrelated)
        )

        assert 10 < ratio < 1_000, f"x{ratio:.1f} for x{DEEP // SHALLOW} in MRO length"

    @pytest.mark.timing
    def test_an_exact_type_match_ignores_the_mro_length(self) -> None:
        shallow = chain(SHALLOW)()
        deep = chain(DEEP)()

        ratio = best_time(lambda: isinstance(deep, type(deep))) / best_time(
            lambda: isinstance(shallow, type(shallow))
        )

        assert ratio < 3, f"x{ratio:.1f} for x{DEEP // SHALLOW} in MRO length"

    @pytest.mark.serial
    def test_space_is_constant(self) -> None:
        deep = chain(DEEP)()
        candidates = tuple(chain(2) for _ in range(1_000))

        assert traced_peak(lambda: isinstance(deep, Unrelated)) == 0
        assert traced_peak(lambda: isinstance(deep, candidates)) == 0


class TestTupleStopsAtTheFirstMatch:
    """Rows: tuple and `|` union - O(k*d), checked in order, stopping at the
    first match."""

    def setup_method(self) -> None:
        CountingMeta.calls = []

    def test_entries_after_the_match_are_not_checked(self) -> None:
        classes = counting_classes(10)
        # An exact match never reaches __instancecheck__; use a subclass instance.
        sub = type("Sub", (classes[3],), {})()

        assert isinstance(sub, tuple(classes))
        assert CountingMeta.calls == ["K0", "K1", "K2", "K3"]

    def test_a_miss_checks_every_entry(self) -> None:
        classes = counting_classes(50)

        assert not isinstance(1, tuple(classes))
        assert len(CountingMeta.calls) == 50

    def test_a_union_is_checked_like_the_tuple(self) -> None:
        a, b, c = counting_classes(3)
        sub = type("Sub", (b,), {})()

        assert isinstance(sub, a | b | c)
        assert CountingMeta.calls == ["K0", "K1"]
        CountingMeta.calls = []
        assert not isinstance(1, a | b | c)
        assert CountingMeta.calls == ["K0", "K1", "K2"]


class TestAbcCaching:
    """ABC rows: the first check of a class walks the ABC's subclasses and
    registry, O(g*d); a repeat is a cache hit, O(1). A positive answer stays
    cached; a negative one only until any ABC registers a virtual subclass."""

    def make_abc(self) -> tuple[type, list[type]]:
        visits: list[type] = []
        # __subclasses__() holds weak references; keep the subclasses alive.
        self.subclasses: list[type] = []

        class Base(ABC):  # noqa: B024 - an ABC used only for its checks
            @classmethod
            def __subclasshook__(cls, subclass: type) -> Any:
                visits.append(cls)
                return NotImplemented

        for index in range(10):
            self.subclasses.append(type(f"Sub{index}", (Base,), {}))
        return Base, visits

    def test_a_first_negative_check_visits_every_subclass(self) -> None:
        base, visits = self.make_abc()

        assert not isinstance(Unrelated(), base)
        assert len(visits) == 11, visits

    def test_a_repeat_check_is_cached(self) -> None:
        base, visits = self.make_abc()
        assert not isinstance(Unrelated(), base)
        visits.clear()

        assert not isinstance(Unrelated(), base)
        assert visits == []

    def test_registration_elsewhere_drops_only_negative_answers(self) -> None:
        base, visits = self.make_abc()
        child = type("Child", (type("Member", (base,), {}),), {})()
        assert isinstance(child, base)
        assert not isinstance(Unrelated(), base)

        class Other(ABC):  # noqa: B024 - an ABC used only for register()
            pass

        Other.register(Unrelated)
        visits.clear()
        assert isinstance(child, base)
        assert visits == [], "a positive answer must survive the registration"
        assert not isinstance(Unrelated(), base)
        assert len(visits) > 1, "a negative answer must be recomputed"


class TestCustomInstancecheck:
    """Row: custom `__instancecheck__` - the hook decides, except that an
    object whose type is exactly the class matches without calling it."""

    def setup_method(self) -> None:
        CountingMeta.calls = []

    def test_the_hook_decides(self) -> None:
        class Everything(metaclass=CountingMeta):
            pass

        class AlwaysMeta(type):
            def __instancecheck__(cls, instance: object) -> bool:
                return True

        class Anything(metaclass=AlwaysMeta):
            pass

        assert not isinstance(1, Everything)
        assert CountingMeta.calls == ["Everything"]
        assert isinstance(1, Anything)

    def test_an_exact_type_match_skips_the_hook(self) -> None:
        (cls,) = counting_classes(1)

        assert isinstance(cls(), cls)
        assert CountingMeta.calls == []
        assert isinstance(type("Sub", (cls,), {})(), cls)
        assert CountingMeta.calls == ["K0"]


class TestStatedExampleValues:
    """The values and exceptions the page's comments give."""

    def test_mro_lengths(self) -> None:
        class Animal:
            pass

        class Dog(Animal):
            pass

        assert len(Dog.__mro__) == 3
        assert len(bool.__mro__) == 3

    def test_parameterized_generics_raise(self) -> None:
        from typing import List  # noqa: UP035 - the page's spelling

        assert List is not list  # noqa: UP006 - the subject is typing.List itself
        with pytest.raises(TypeError, match="generic"):
            isinstance([], List[int])  # noqa: UP006  # pyright: ignore[reportArgumentType]

    def test_a_list_of_classes_is_rejected(self) -> None:
        with pytest.raises(TypeError):
            isinstance(1, [int])  # type: ignore[arg-type]


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests, and pins its
    results with assert statements."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "class D(C)" in source)
        broken = block.replace("assert len(D.__mro__) == 5", "assert len(D.__mro__) == 4", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
