"""Tests for docs/stdlib/abc.md.

The page prices the module at two moments: class creation, which decides the
abstract methods once, and the first `isinstance()`/`issubclass()` check of a
class against an ABC, which walks registered classes and subclasses and then
caches the answer. Both are settled by counting: a value whose
`__isabstractmethod__` counts its reads, a `__subclasshook__` that records
each ABC a check visits, and a metaclass whose `__subclasscheck__` records
each registered class a walk tests. Counts need no tolerance. One timing test
backs the instantiation row.

Measurement scope:

* Class creation reads `__isabstractmethod__` once per namespace value (30
  counting values, 30 reads) and once per abstract name a direct base
  declares (a subclass of that base with an empty body, 30 reads);
  `update_abstractmethods()` on a class with 30 local values and two bases
  declaring the same 30 names reads 90 times, once per base per name. `__abstractmethods__` is
  the same object on every access.
* Instantiating a concrete subclass reads no `__isabstractmethod__`, and
  attaching an abstract method after creation does not stop it. In a timing
  test, a concrete subclass of a base with 10,000 abstract methods
  instantiates within 3x of one whose base has a single abstract method.
  Instantiating an abstract class raises `TypeError` naming all 200 of its
  four-character abstract methods in sorted order (3.12+ quotes the names,
  3.10 and 3.11 do not); that the sort is what makes it
  O(a log a) is read from Objects/typeobject.c `object_new`.
* An uncached negative `issubclass()` calls the hook of the ABC and of each
  of 50 subclasses (51 calls); a repeat calls none; each subclass then
  answers the same query with no call, so the negative answer was cached in
  every ABC visited. After an unrelated ABC registers a class, the negative
  check makes 51 calls again, and a cached positive answer makes none;
  registering an already registered class again leaves the negative answer
  cached. A class registered directly on the ABC is answered from the
  registry and calls the hook on each of two checks; a subclass of it is
  cached after one.
  `isinstance()` is asserted to take the same cached path.
* `register()` of the k-th class into one ABC calls `__subclasscheck__` on
  the k - 1 classes already registered plus the one being added (the cycle
  test), so k registrations are O(k^2) in total. Re-registering a class that
  already is a subclass leaves the cache token unchanged; a new one advances
  it, on any ABC.
* The `__subclasshook__` row is asserted to answer `True` and `False` ahead
  of registration and inheritance: a hook returning `False` overrides both.
* The decorators are asserted to set `__isabstractmethod__`, to be enforced
  only under `ABCMeta`, and the three deprecated helpers to leave their
  members abstract. `ABC` is asserted to have `ABCMeta` as its metaclass and
  empty `__slots__`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(g) space of a first check and of `register()`: each visited ABC
  caching one weak reference is observed through the hook counts, but the
  registry snapshot taken during the walk (Modules/_abc.c,
  `subclasscheck_check_registry`) is read from source, not measured.
* Attribute lookup, a plain class's MRO test, method-name comparison and
  joining, and a caller's `__subclasshook__` are priced O(1) by the page's
  cost model; deep MROs, long names and expensive hooks are not varied.
* The per-link bound for a first check is read from the loops over the
  registry and `__subclasses__()` in Modules/_abc.c; the measured subclass
  trees have one link per class, and DAGs where a class has many ABC bases
  are not varied. Nor is the direct-base count in `b`, nor the reverse
  cycle check `register()` runs when the registered class is itself an ABC.
* Clearing a stale negative cache on the first check after a registration
  costs its entry count. Each entry was added by an earlier check, so the
  page charges it to those checks rather than to g; it is not measured.
* Assigning `__abstractmethods__`, as `update_abstractmethods()` does,
  invalidates the attribute caches of the class's existing subclasses, as
  any class attribute assignment does; that is plain-class cost and not
  priced or measured.
* The page prices only the ABC's work. What `type()` and `object()` cost
  for a plain class - MRO construction, slots, `__init__` - is outside it.
* The pure-Python fallback in Lib/_py_abc.py, used only when `_abc` is
  unavailable, follows the same algorithm and is not run.
"""

from __future__ import annotations

import abc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from abc import (
    ABC,
    ABCMeta,
    abstractmethod,
    get_cache_token,
    update_abstractmethods,
)
from collections.abc import Callable
from functools import singledispatch
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "abc.md"
EXPECTED_BLOCKS = 7


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


class CountingFlag:
    """A class attribute whose `__isabstractmethod__` counts its reads."""

    reads = 0

    def __init__(self, abstract: bool) -> None:
        self._abstract = abstract

    @property
    def __isabstractmethod__(self) -> bool:
        CountingFlag.reads += 1
        return self._abstract


class RecordingMeta(type):
    """A metaclass that records every `issubclass(x, cls)` asked of its classes."""

    calls: list[type] = []

    def __subclasscheck__(cls, subclass: type) -> bool:
        RecordingMeta.calls.append(cls)
        return type.__subclasscheck__(cls, subclass)


def hooked_abc() -> tuple[type, list[type]]:
    """A fresh ABC whose `__subclasshook__` records each class it runs for."""
    visits: list[type] = []

    class Hooked(ABC):
        @classmethod
        def __subclasshook__(cls, subclass: type) -> Any:
            visits.append(cls)
            return NotImplemented

    return Hooked, visits


class TestDecorators:
    """`@abstractmethod` and the deprecated helpers are O(1) markers; only an
    `ABCMeta` class enforces them."""

    def test_abstractmethod_sets_the_flag_and_returns_the_function(self) -> None:
        def method(self: object) -> None: ...

        marked: Any = abstractmethod(method)
        assert marked is method
        assert marked.__isabstractmethod__ is True

    def test_it_is_not_enforced_without_abcmeta(self) -> None:
        class Plain:
            @abstractmethod
            def run(self) -> None: ...

        assert Plain() is not None

    def test_wrappers_report_the_functions_flag(self) -> None:
        func: Any = abstractmethod(lambda *args: None)
        for wrapper in (property(func), classmethod(func), staticmethod(func)):
            assert wrapper.__isabstractmethod__ is True

    def test_the_deprecated_helpers_mark_members_abstract(self) -> None:
        helpers: list[Any] = [abc.abstractclassmethod, abc.abstractstaticmethod]
        namespace = {
            name: helper(lambda *args: None) for name, helper in zip("ab", helpers, strict=True)
        }
        namespace["c"] = abc.abstractproperty(lambda self: None)
        legacy: Any = ABCMeta("Legacy", (ABC,), namespace)

        assert legacy.__abstractmethods__ == frozenset({"a", "b", "c"})


class TestClassCreationScansOnce:
    """`ABCMeta(name, bases, namespace)` | O(m + b): one `__isabstractmethod__`
    read per namespace value and per abstract name of the direct bases."""

    SIZE = 30

    def _base(self) -> type:
        namespace = {f"m{i}": CountingFlag(True) for i in range(self.SIZE)}
        return ABCMeta("Base", (ABC,), namespace)

    def test_each_namespace_value_is_read_once(self) -> None:
        CountingFlag.reads = 0
        base = self._base()

        assert CountingFlag.reads == self.SIZE
        assert len(base.__abstractmethods__) == self.SIZE

    def test_each_inherited_abstract_name_is_read_once(self) -> None:
        base = self._base()
        CountingFlag.reads = 0

        sub = ABCMeta("Sub", (base,), {})

        assert CountingFlag.reads == self.SIZE
        assert sub.__abstractmethods__ == base.__abstractmethods__

    def test_update_abstractmethods_reads_the_same(self) -> None:
        """Two bases declaring the same 30 names, and 30 local values: 90 reads."""
        first, second = self._base(), self._base()
        local = {f"x{i}": CountingFlag(False) for i in range(self.SIZE)}
        sub = ABCMeta("Sub", (first, second), local)
        CountingFlag.reads = 0

        assert update_abstractmethods(sub) is sub
        assert CountingFlag.reads == 3 * self.SIZE
        assert sub.__abstractmethods__ == first.__abstractmethods__

    def test_abstractmethods_is_stored_not_recomputed(self) -> None:
        base = self._base()
        CountingFlag.reads = 0

        first = base.__abstractmethods__
        assert base.__abstractmethods__ is first
        assert CountingFlag.reads == 0


class TestInstantiation:
    """A concrete subclass instantiates in O(1) beyond `__init__`; an abstract
    one raises in O(a log a), naming every abstract method sorted."""

    def test_a_concrete_instance_reads_no_flag(self) -> None:
        class Concrete(ABC):
            plain = CountingFlag(False)

        CountingFlag.reads = 0
        Concrete()
        Concrete()

        assert CountingFlag.reads == 0

    def test_a_method_attached_later_is_not_seen(self) -> None:
        class Concrete(ABC):
            pass

        attach: Any = Concrete
        attach.late = abstractmethod(lambda self: None)

        assert Concrete() is not None
        assert update_abstractmethods(Concrete).__abstractmethods__ == frozenset({"late"})
        with pytest.raises(TypeError):
            Concrete()

    def test_the_error_names_every_abstract_method_sorted(self) -> None:
        names = [f"m{i:03d}" for i in range(200)]
        namespace = {name: abstractmethod(lambda self: None) for name in reversed(names)}
        cls = ABCMeta("Wide", (ABC,), namespace)

        with pytest.raises(TypeError) as info:
            cls()

        listed = re.findall(r"\bm\d{3}\b", str(info.value))
        assert listed == names

    @pytest.mark.timing
    def test_base_abstract_methods_do_not_cost_at_instantiation(self) -> None:
        def concrete(count: int) -> Callable[[], object]:
            names = [f"m{i}" for i in range(count)]
            base = ABCMeta("Base", (ABC,), {n: abstractmethod(lambda self: None) for n in names})
            return ABCMeta("Concrete", (base,), {n: lambda self: None for n in names})

        narrow, wide = concrete(1), concrete(10_000)
        narrow_ns = best_ns(narrow, inner=2_000)
        wide_ns = best_ns(wide, inner=2_000)

        assert wide_ns < 3 * narrow_ns, (
            f"10,000 base abstract methods: {wide_ns:.0f} ns vs {narrow_ns:.0f} ns for one"
        )


class TestChecksAreCached:
    """First check O(g), cached O(1); negative answers are dropped by any
    registration, positive ones are kept."""

    SUBCLASSES = 50

    def _tree(self) -> tuple[type, list[type], list[type]]:
        root, visits = hooked_abc()
        subclasses = [type(root)(f"S{i}", (root,), {}) for i in range(self.SUBCLASSES)]
        return root, subclasses, visits

    def test_a_negative_first_check_visits_every_subclass(self) -> None:
        root, subclasses, visits = self._tree()

        class Unrelated:
            pass

        assert not issubclass(Unrelated, root)
        assert len(visits) == self.SUBCLASSES + 1

        visits.clear()
        assert not issubclass(Unrelated, root)
        assert not isinstance(Unrelated(), root)
        assert visits == []

    def test_the_negative_answer_is_cached_in_every_abc_visited(self) -> None:
        root, subclasses, visits = self._tree()

        class Unrelated:
            pass

        issubclass(Unrelated, root)
        visits.clear()

        assert not any(issubclass(Unrelated, sub) for sub in subclasses)
        assert visits == []

    def test_any_registration_drops_negative_answers(self) -> None:
        root, _, visits = self._tree()

        class Unrelated:
            pass

        class Elsewhere(ABC):
            pass

        issubclass(Unrelated, root)
        visits.clear()
        Elsewhere.register(type("Fresh", (), {}))

        assert not issubclass(Unrelated, root)
        assert len(visits) == self.SUBCLASSES + 1

    def test_a_repeated_registration_keeps_negative_answers(self) -> None:
        root, _, visits = self._tree()

        class Unrelated:
            pass

        class Elsewhere(ABC):
            pass

        already = type("Already", (), {})
        Elsewhere.register(already)
        issubclass(Unrelated, root)
        visits.clear()
        Elsewhere.register(already)

        assert not issubclass(Unrelated, root)
        assert visits == []

    def test_a_directly_registered_class_is_answered_by_the_registry(self) -> None:
        """Not cached, so the hook runs on every check; its subclass is cached."""
        root, _, visits = self._tree()

        class Registered:
            pass

        class Derived(Registered):
            pass

        root.register(Registered)
        visits.clear()
        assert issubclass(Registered, root)
        assert issubclass(Registered, root)
        assert len(visits) == 2

        issubclass(Derived, root)
        visits.clear()
        assert issubclass(Derived, root)
        assert visits == []

    def test_positive_answers_survive_a_registration(self) -> None:
        root, subclasses, visits = self._tree()

        class Elsewhere(ABC):
            pass

        assert issubclass(subclasses[-1], root)
        assert isinstance(subclasses[-1](), root)
        visits.clear()
        Elsewhere.register(type("Fresh", (), {}))

        assert issubclass(subclasses[-1], root)
        assert isinstance(subclasses[-1](), root)
        assert visits == []


class TestRegistration:
    """`ABCMeta.register(subclass)` | O(g): it starts with a first
    `issubclass()` check, which walks the registry built so far."""

    def test_each_registration_walks_the_registry_so_far(self) -> None:
        class Target(ABC):
            pass

        classes = [RecordingMeta(f"R{i}", (), {}) for i in range(40)]
        per_call: list[int] = []
        for cls in classes:
            RecordingMeta.calls.clear()
            Target.register(cls)
            per_call.append(len(RecordingMeta.calls))

        # k - 1 registered classes tested, plus the cycle test on the new one
        assert per_call == list(range(1, 41))

    def test_register_returns_the_class_and_checks_no_methods(self) -> None:
        class Drawable(ABC):
            @abstractmethod
            def draw(self) -> None: ...

        class Blank:
            pass

        assert Drawable.register(Blank) is Blank
        assert issubclass(Blank, Drawable)
        assert Drawable not in Blank.__mro__
        assert Blank() is not None

    def test_the_token_moves_only_for_a_new_virtual_subclass(self) -> None:
        class Interface(ABC):
            pass

        class Derived(Interface):
            pass

        class Newcomer:
            pass

        token = get_cache_token()
        Interface.register(Derived)
        assert get_cache_token() == token

        Interface.register(Newcomer)
        moved = get_cache_token()
        assert moved != token

        Interface.register(Newcomer)
        assert get_cache_token() == moved

    def test_the_token_never_decreases(self) -> None:
        class InterfaceA(ABC):
            pass

        class InterfaceB(ABC):
            pass

        # The token is documented as an opaque object; CPython's is an int.
        readings: list[int] = [get_cache_token()]  # type: ignore[list-item]
        InterfaceA.register(type("First", (), {}))
        readings.append(get_cache_token())  # type: ignore[arg-type]
        InterfaceB.register(type("Second", (), {}))
        readings.append(get_cache_token())  # type: ignore[arg-type]

        assert readings == sorted(readings)
        assert len(set(readings)) == 3


class TestSubclassHook:
    """`__subclasshook__` answers an uncached check before registration and
    inheritance are consulted."""

    def test_false_overrides_inheritance_and_registration(self) -> None:
        class Gate(ABC):
            @classmethod
            def __subclasshook__(cls, subclass: type) -> Any:
                return False

        class Child(Gate):
            pass

        class Registered:
            pass

        Gate.register(Registered)

        assert not issubclass(Child, Gate)
        assert not issubclass(Registered, Gate)

    def test_true_admits_an_unrelated_class(self) -> None:
        class Anything(ABC):
            @classmethod
            def __subclasshook__(cls, subclass: type) -> Any:
                return True

        assert issubclass(int, Anything)


class TestAbcClassAndRelatedModules:
    def test_abc_is_a_plain_abcmeta_base(self) -> None:
        assert type(ABC) is ABCMeta
        assert ABC.__slots__ == ()

    def test_update_abstractmethods_leaves_a_plain_class_alone(self) -> None:
        class Plain:
            pass

        assert update_abstractmethods(Plain) is Plain
        assert not hasattr(Plain, "__abstractmethods__")

    def test_singledispatch_dispatches_on_a_virtual_subclass(self) -> None:
        class Drawable(ABC):
            pass

        class Circle:
            pass

        @singledispatch
        def describe(obj: object) -> str:
            return "object"

        describe.register(Drawable, lambda obj: "drawable")

        assert describe(Circle()) == "object"
        Drawable.register(Circle)
        assert describe(Circle()) == "drawable"


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
    """Each block runs in its own subprocess, so registrations and the cache
    token cannot leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(visits) == 11" in s)
        mutated = source.replace("len(visits) == 11", "len(visits) == 10", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
