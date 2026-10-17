"""Tests for docs/builtins/setattr.md.

setattr() is builtin_setattr in Python/bltinmodule.c, which calls
PyObject_SetAttr(obj, name, value) - the call an unspecialized
`obj.name = value` makes; specialized forms such as STORE_ATTR_SLOT write
directly once the type's version tag matches.
PyObject_SetAttr (Objects/object.c) rejects a non-str name, then interns an
exact str name (PyUnicode_InternInPlace in v3.11.14, _PyUnicode_InternMortal in
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3; a str subclass is left as it is)
before calling the type's tp_setattro. For an ordinary instance that is
_PyObject_GenericSetAttrWithDict: one _PyType_Lookup on type(obj) for a data
descriptor, then a store in the instance's values or `__dict__`. _PyType_Lookup
consults a cache keyed by the type's version tag and the name object, which
takes only an exact str of at most 100 characters (MCACHE_CACHEABLE_NAME) and
walks the MRO on a miss. On a class, type_setattro interns the name, stores it
and calls PyType_Modified, which clears the version tag of the class and
recurses into each subclass that still has one; a special-method name with a
type slot then runs update_slot, which recurses into every subclass that does
not define the name itself and repeats an uncached MRO search for each one.
A slot is a member descriptor whose setter calls descr_setcheck, which
accepts type(obj) itself at once and otherwise scans its MRO for the
declaring class (PyType_IsSubtype). From the v3.13.0 tag assign_version_tag refuses
once tp_versions_used reaches MAX_VERSIONS_PER_CLASS (1,000); 3.11 and 3.12
have no such limit.

Measurement scope:

* Observation settles the hook and error rows: a counting `__setattr__` sees
  setattr() and the assignment statement, and the assignments `__init__`
  makes; a property setter runs even when the instance `__dict__` holds the
  name; a property without a setter, a missing slot and an `object()` raise
  AttributeError; a data descriptor's `__set__` runs once per call while a
  function on the class (a non-data descriptor) does not intercept the store;
  setattr() on int raises TypeError; a non-str name raises TypeError before a
  counting `__setattr__` is reached; a str subclass name is accepted.
* Interning: setattr() with a name built by "".join() stores the object
  sys.intern() returns for the same text, and the instance keeps a str
  subclass name as the subclass.
* Elapsed time on the pinned interpreter, 20,000 setattr() calls per run, a
  class 1,024 deep against one 2 deep: a literal name and a name rebuilt per
  call cost under x3 more, where getattr() with the same rebuilt names costs
  over x20; a str subclass name and a 101-character name cost over x20.
  On 3.11 to 3.15 those measured x1.0 for setattr() with rebuilt names,
  x106 to x159 for getattr() with them, and x86 to x148 for the uncached
  names. Building the rebuilt names happens outside the timed loop.
* A class assignment before each instance setattr() costs over x20 more per
  iteration at depth 1,024 than at 2, where an instance assignment costs
  under x3. After 1,100 class assignments, each followed by an instance
  setattr(), the 1,024-deep class costs over x20 what it did before on 3.13
  and later, and under x3 on 3.11 and 3.12 (measured x432 on 3.13, x385 on
  3.15, and x1.0 on 3.11 and 3.12).
* Class assignment against 20,000 subclasses that have looked up an
  attribute, against none: the first assignment of a plain name (fastest of
  3 fresh families, against fastest of 200 lone classes) costs over x50 more,
  a repeat assignment with no lookup in between (1,000 per run) under x3
  more, and every assignment of `__eq__` over x50 more. Measured on 3.11 to
  3.15: x6,250 to x10,297 for the first plain assignment, x0.98 to x1.04 for
  the repeat, and x25,381 to x41,009 for `__eq__`. Assigning `__eq__` on a
  base changes `==` on a subclass that inherits it and not on one that
  defines its own.
* Assigning `__eq__` to the root of a line of 2,000 subclasses, each deriving
  from the last, costs over x20 what it costs with 2,000 direct subclasses
  (measured about x90 to x210 on 3.11, 3.13 and 3.15; doubling the line
  measured x4, the quadratic the O(s·m) row predicts for a line).
* A slot declared on the root of a 2,048-deep chain of slotted classes:
  setattr() on an instance of the leaf costs over x8 what it costs at depth
  2 (measured x22 on 3.15 and 3.11 at that depth, x10 to x13 at 1,024), where a
  slot declared on the leaf itself, and a warmed `obj.x = value` statement
  on the inherited slot, cost under x3.
* Space: tracemalloc's traced peak for 1,000 warmed setattr() calls that
  overwrite an existing attribute, with a literal name and with names
  rebuilt beforehand, is zero.
* The instance store does not grow with the attributes already on the
  instance: overwriting one attribute on an instance holding 10 attributes
  against one holding 100,000, accepted under x3.
* Every fenced block runs in a subprocess and asserts its own results, and a
  broken assertion in one is shown to fail.

Not settled here:

* The O(k) rows price the hook at whatever it costs; no hook other than a
  counter is measured.
* Module assignment is checked for its result only: module objects use
  PyObject_GenericSetAttr with the module's `__dict__`.
* The C stack used by recursion over a class's subclasses (PyType_Modified,
  update_slot) or bases (assign_version_tag restoring a base's tag) grows
  with the depth of that hierarchy; the Space column leaves it out, and no
  test measures it.
* Not varied: multiple inheritance (the MRO here is a chain), name length
  between 1 and 100 characters (hashing is priced at O(1)), and the type
  cache's capacity, which a program touching more (class, name) pairs than it
  holds overflows.
"""

from __future__ import annotations

import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "setattr.md"
EXPECTED_BLOCKS = 7
CALLS = 20_000


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """The fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def chain(depth: int) -> type:
    """A class with `depth` classes of its own above object, `a_attr` on the root."""
    cls = type("L0", (), {"a_attr": 1})
    for index in range(1, depth):
        cls = type(f"L{index}", (cls,), {})
    return cls


class Name(str):
    """A str subclass: accepted by setattr(), neither interned nor cached."""


def per_name(obj: object, names: list[str], func: Callable[..., Any]) -> float:
    """Time `func` over `names` after one warm-up pass."""

    def loop() -> None:
        for name in names:
            func(obj, name)

    loop()
    return best_time(loop)


def set_one(obj: object, name: str) -> None:
    setattr(obj, name, 1)


def get_one(obj: object, name: str) -> None:
    getattr(obj, name, None)


def depth_ratio(names: list[str], func: Callable[..., Any] = set_one) -> float:
    return per_name(chain(1_024)(), names, func) / per_name(chain(2)(), names, func)


def rebuilt(parts: list[str]) -> list[str]:
    names = ["".join(parts) for _ in range(CALLS)]
    assert names[0] is not names[1]
    return names


class TestSameAsAssignment:
    """setattr() and `obj.name = value` call the same `__setattr__`."""

    def test_both_spellings_reach_setattr(self) -> None:
        calls: list[str] = []

        class Counting:
            def __setattr__(self, name: str, value: Any) -> None:
                calls.append(name)
                object.__setattr__(self, name, value)

        obj = Counting()
        setattr(obj, "a", 1)
        obj.b = 2
        assert calls == ["a", "b"]
        assert vars(obj) == {"a": 1, "b": 2}

    def test_a_module_attribute_lands_in_its_dict(self) -> None:
        module = types.ModuleType("scratch")
        setattr(module, "answer", 42)
        assert vars(module)["answer"] == 42


class TestNamesAreInterned:
    """An exact str name is interned before the store; a str subclass is not."""

    def test_a_rebuilt_name_is_stored_as_the_interned_object(self) -> None:
        name = "".join(["col", "or"])
        assert name is not sys.intern("color")

        obj = types.SimpleNamespace()
        setattr(obj, name, "red")
        (stored,) = vars(obj)
        assert stored is sys.intern("color")

    def test_a_str_subclass_name_is_kept(self) -> None:
        class Plain:
            pass

        obj = Plain()
        setattr(obj, Name("shade"), "dark")
        (stored,) = vars(obj)
        assert type(stored) is Name
        assert getattr(obj, "shade") == "dark"


class TestCachedInstanceRows:
    """`setattr(obj, name, value)` is O(1) avg whatever the depth, including
    for a name rebuilt per call; a str subclass or a name over 100 characters
    is never cached and costs O(d)."""

    @pytest.mark.timing
    def test_a_literal_name_does_not_grow_with_depth(self) -> None:
        ratio = depth_ratio(["x_val"] * CALLS)
        assert ratio < 3, f"x512 classes should cost a literal name nothing: x{ratio:.1f}"

    @pytest.mark.timing
    def test_a_rebuilt_name_does_not_grow_with_depth_unlike_getattr(self) -> None:
        names = rebuilt(["x_", "val"])
        set_ratio = depth_ratio(names)
        get_ratio = depth_ratio(names, get_one)

        assert set_ratio < 3, f"setattr() with rebuilt names should be cached: x{set_ratio:.1f}"
        assert get_ratio > 20, (
            f"getattr() with the same rebuilt names should walk the MRO: x{get_ratio:.1f}"
        )

    @pytest.mark.timing
    def test_uncacheable_names_grow_with_depth(self) -> None:
        subclass = depth_ratio([Name("x_val")] * CALLS)
        long_name = depth_ratio(["v" * 101] * CALLS)

        assert subclass > 20 and long_name > 20, (
            f"x512 classes should cost an uncacheable name near x512: "
            f"str subclass x{subclass:.1f}, 101 characters x{long_name:.1f}"
        )

    @pytest.mark.timing
    def test_the_store_does_not_grow_with_the_attributes_held(self) -> None:
        def with_attributes(count: int) -> float:
            obj = types.SimpleNamespace(**{f"a{index}": index for index in range(count)})
            return per_name(obj, ["a0"] * CALLS, set_one)

        ratio = with_attributes(100_000) / with_attributes(10)
        assert ratio < 3, f"x10,000 attributes should cost one store nothing: x{ratio:.1f}"


class TestColdLookupRow:
    """The first instance assignment after a class changes walks the MRO; from
    3.13 a class changed and looked up again more than 1,000 times walks it
    every time."""

    @pytest.mark.timing
    def test_a_class_change_makes_the_next_instance_set_walk(self) -> None:
        """900 changes per class keeps every class under the 3.13 limit, and a
        fresh class per repeat keeps the count from accumulating."""

        def changing_the_class(depth: int) -> float:
            def one_run() -> float:
                cls = chain(depth)
                obj = cls()
                obj.value = 0

                def loop() -> None:
                    for index in range(900):
                        cls.counter = index
                        obj.value = index

                return best_time(loop, repeats=1)

            return min(one_run() for _ in range(5))

        def changing_the_instance(depth: int) -> float:
            obj = chain(depth)()
            obj.value = 0

            def loop() -> None:
                for index in range(900):
                    obj.counter = index
                    obj.value = index

            return best_time(loop)

        walked = changing_the_class(1_024) / changing_the_class(2)
        cached = changing_the_instance(1_024) / changing_the_instance(2)

        assert walked > 20, f"a set after each class change should cost the depth: x{walked:.1f}"
        assert cached < 3, f"a set after each instance change should not: x{cached:.1f}"

    @pytest.mark.timing
    def test_a_much_modified_class_stays_uncached_only_from_3_13(self) -> None:
        cls = chain(1_024)
        obj = cls()
        names = ["x_val"] * CALLS
        before = per_name(obj, names, set_one)

        for index in range(1_100):
            cls.counter = index
            obj.other = index
        after = per_name(obj, names, set_one)

        ratio = after / before
        if sys.version_info >= (3, 13):
            assert ratio > 20, f"1,100 changes should leave the class uncached: x{ratio:.1f}"
        else:
            assert ratio < 3, f"before 3.13 the class should be cached again: x{ratio:.1f}"


class TestHookRows:
    """A property setter, a data descriptor's `__set__` and a custom
    `__setattr__` replace the store; a non-data descriptor does not."""

    def test_a_property_setter_wins_over_the_instance_dict(self) -> None:
        writes: list[int] = []

        class Prop:
            @property
            def value(self) -> int:
                return 0

            @value.setter
            def value(self, new: int) -> None:
                writes.append(new)

        obj = Prop()
        vars(obj)["value"] = -1
        setattr(obj, "value", 5)
        assert writes == [5]
        assert vars(obj)["value"] == -1

    def test_a_property_without_a_setter_refuses(self) -> None:
        class ReadOnly:
            @property
            def value(self) -> int:
                return 42

        with pytest.raises(AttributeError):
            setattr(ReadOnly(), "value", 1)

    def test_a_data_descriptor_runs_once_per_call(self) -> None:
        sets: list[Any] = []

        class Recorder:
            def __get__(self, obj: object, owner: type | None = None) -> None:
                return None

            def __set__(self, obj: object, value: Any) -> None:
                sets.append(value)

        class Holder:
            field = Recorder()

        obj = Holder()
        setattr(obj, "field", 1)
        setattr(obj, "field", 2)
        assert sets == [1, 2]
        assert "field" not in vars(obj)

    def test_a_method_on_the_class_does_not_intercept(self) -> None:
        class WithMethod:
            def method(self) -> str:
                return "class"

        obj = WithMethod()
        setattr(obj, "method", "instance")
        assert vars(obj) == {"method": "instance"}

    def test_setattr_runs_for_init_assignments_too(self) -> None:
        calls: list[str] = []

        class Tracked:
            def __init__(self) -> None:
                self.first = 1

            def __setattr__(self, name: str, value: Any) -> None:
                calls.append(name)
                object.__setattr__(self, name, value)

        obj = Tracked()
        setattr(obj, "second", 2)
        assert calls == ["first", "second"]


class TestSlotsAndErrors:
    """Slots store in place; without a `__dict__`, a name with no slot or other
    descriptor is refused, as are built-in types and non-str names."""

    def test_a_slot_stores_and_a_missing_slot_raises(self) -> None:
        class Point:
            __slots__ = ("x",)

        point = Point()
        setattr(point, "x", 1)
        assert point.x == 1
        assert not hasattr(point, "__dict__")
        with pytest.raises(AttributeError):
            setattr(point, "y", 2)

    def test_a_descriptor_or_a_dict_slot_accepts_other_names(self) -> None:
        class WithProperty:
            __slots__ = ("_x",)

            @property
            def x(self) -> int:
                return self._x

            @x.setter
            def x(self, value: int) -> None:
                self._x = value

        class WithDict:
            __slots__ = ("x", "__dict__")

        prop = WithProperty()
        setattr(prop, "x", 5)
        assert prop.x == 5

        open_ended = WithDict()
        setattr(open_ended, "anything", 1)
        assert vars(open_ended) == {"anything": 1}

    def test_object_has_no_dict(self) -> None:
        with pytest.raises(AttributeError):
            setattr(object(), "x", 1)

    def test_a_builtin_type_refuses(self) -> None:
        with pytest.raises(TypeError, match="immutable type"):
            setattr(int, "x", 1)

    @pytest.mark.parametrize("name", [1, b"x", None], ids=["int", "bytes", "None"])
    def test_a_non_str_name_raises_before_setattr_runs(self, name: Any) -> None:
        calls: list[Any] = []

        class Counting:
            def __setattr__(self, attr: Any, value: Any) -> None:
                calls.append(attr)

        with pytest.raises(TypeError, match="attribute name must be string"):
            setattr(Counting(), name, 1)
        assert calls == []


class TestClassRows:
    """`setattr(cls, ...)` is O(s): it invalidates each subclass whose cache is
    valid, and a special-method name also updates every inheriting subclass."""

    @staticmethod
    def _family(count: int) -> tuple[type, list[type]]:
        base = type("Base", (), {"plain": 0})
        kids = [type(f"Kid{index}", (base,), {}) for index in range(count)]
        for kid in kids:
            getattr(kid, "plain")  # gives each subclass a valid cache
        return base, kids

    @pytest.mark.timing
    def test_class_assignment_grows_with_cached_subclasses(self) -> None:
        def first(count: int, runs: int) -> float:
            """One assignment right after every subclass has cached a lookup."""
            times = []
            for _ in range(runs):
                base, _kids = self._family(count)
                times.append(best_time(partial(setattr, base, "plain", 1), repeats=1))
            return min(times)

        def per_call(count: int, name: str, value: Any, calls: int) -> float:
            base, _kids = self._family(count)
            setattr(base, name, value)

            def loop() -> None:
                for _ in range(calls):
                    setattr(base, name, value)

            return best_time(loop) / calls

        first_ratio = first(20_000, 3) / first(0, 200)
        repeat = per_call(20_000, "plain", 2, 1_000) / per_call(0, "plain", 2, 1_000)
        special = per_call(20_000, "__eq__", object.__eq__, 10) / per_call(
            0, "__eq__", object.__eq__, 1_000
        )

        assert first_ratio > 50, (
            f"20,000 cached subclasses should cost the first assignment: x{first_ratio:.1f}"
        )
        assert repeat < 3, f"subclasses already invalidated should cost nothing: x{repeat:.1f}"
        assert special > 50, f"a special method should visit every subclass: x{special:.1f}"

    @pytest.mark.timing
    def test_a_special_method_costs_more_down_a_line_than_across(self) -> None:
        def wide(count: int) -> list[type]:
            base = type("Base", (), {})
            return [base] + [type(f"Kid{index}", (base,), {}) for index in range(count)]

        def deep(count: int) -> list[type]:
            line = [type("Base", (), {})]
            for index in range(count):
                line.append(type(f"Line{index}", (line[-1],), {}))
            return line

        def cost(base: type) -> float:
            return best_time(partial(setattr, base, "__eq__", object.__eq__), repeats=3)

        # __subclasses__() holds weak references: both families stay alive here
        row, line = wide(2_000), deep(2_000)
        assert len(row[0].__subclasses__()) == 2_000
        assert len(line[-1].__mro__) == 2_002
        ratio = cost(line[0]) / cost(row[0])
        assert len(row[0].__subclasses__()) == 2_000 and line[1] in line[0].__subclasses__()
        assert ratio > 20, (
            f"2,000 subclasses in a line should cost more than in a row: x{ratio:.1f}"
        )

    def test_a_special_method_reaches_inheriting_subclasses_only(self) -> None:
        class Base:
            def __eq__(self, other: object) -> bool:
                return False

        class Child(Base):
            pass

        class Own(Base):
            def __eq__(self, other: object) -> bool:
                return False

        setattr(Base, "__eq__", lambda self, other: True)
        assert Child() == Child()
        assert not Own() == Own()


class TestInheritedSlots:
    """A slot declared on a base class costs setattr() an O(d) subtype check;
    one declared on type(obj) does not, nor does a specialized statement."""

    @staticmethod
    def _inherited(depth: int) -> Any:
        cls = type("Root", (), {"__slots__": ("x",)})
        for index in range(depth - 1):
            cls = type(f"S{index}", (cls,), {"__slots__": ()})
        return cls()

    @staticmethod
    def _own(depth: int) -> Any:
        cls = type("Root", (), {})
        for index in range(depth - 2):
            cls = type(f"P{index}", (cls,), {})
        return type("Leaf", (cls,), {"__slots__": ("x",)})()

    @staticmethod
    def _assign(obj: Any) -> float:
        def loop() -> None:
            for _ in range(CALLS):
                obj.x = 1

        loop()
        loop()
        return best_time(loop)

    @pytest.mark.timing
    def test_an_inherited_slot_grows_with_depth(self) -> None:
        shallow, deep = self._inherited(2), self._inherited(2_048)
        assert len(type(deep).__mro__) == 2_049

        inherited = per_name(deep, ["x"] * CALLS, set_one) / per_name(
            shallow, ["x"] * CALLS, set_one
        )
        own = per_name(self._own(2_048), ["x"] * CALLS, set_one) / per_name(
            self._own(2), ["x"] * CALLS, set_one
        )
        statement = self._assign(deep) / self._assign(shallow)

        assert inherited > 8, f"x1,024 depth should cost an inherited slot: x{inherited:.1f}"
        assert own < 3, f"a slot on type(obj) should not grow with depth: x{own:.1f}"
        assert statement < 3, f"a specialized assignment should skip the check: x{statement:.1f}"


@pytest.mark.serial
class TestSpaceColumn:
    """Overwriting an attribute allocates nothing, with a literal name or with
    names rebuilt beforehand: interning finds the existing object."""

    def test_overwriting_allocates_nothing(self) -> None:
        obj = types.SimpleNamespace(x_val=0)
        literal = ["x_val"] * 1_000
        fresh = ["".join(["x_", "val"]) for _ in range(1_000)]

        def run(names: list[str]) -> int:
            for name in names:
                setattr(obj, name, 1)
            remaining = iter(names)  # the list iterator is not part of the claim
            gc.collect()
            gc.disable()
            tracemalloc.start()
            try:
                for name in remaining:
                    setattr(obj, name, 1)
                return tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
                gc.enable()

        assert run(literal) == 0
        assert run(fresh) == 0


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
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if 'assert obj.changes == ["name"' in s)
        mutated = source.replace('["name", "name", "size"]', '["name", "size"]', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
