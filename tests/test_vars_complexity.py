"""Tests for docs/builtins/vars.md.

vars() is builtin_vars in Python/bltinmodule.c. With an argument it is one
PyObject_GetOptionalAttr(v, "__dict__"), returned untouched, and a missing
attribute becomes TypeError. An instance's or module's `__dict__` getter hands
back the object's own dict; `type.__dict__` wraps the class namespace in a new
read-only mappingproxy on every read; a class that defines `__dict__` itself
runs that descriptor. Without an argument it is locals(): the module or class
namespace itself, or a snapshot of a function frame. Up to 3.12 the snapshot
is one FastToLocals pass over the fast locals into the frame's one dict, which
every call refreshes and returns again. From the
v3.13.0 tag (PEP 667) it is _PyEval_GetFrameLocals: a fresh dict filled by
PyDict_Update from a FrameLocalsProxy, whose keys() is one pass but whose
__getitem__ (framelocalsproxy_getkeyindex in Objects/frameobject.c) scans
co_localsplusnames from the start for each key - n lookups of O(n), so the
snapshot is O(n²) in the frame's local slots.

Observation settles every table row but one:

* `vars(obj) is obj.__dict__` for an instance and a module, at 10,000
  attributes as at one; a write through the result reaches the object and an
  attribute set afterwards is visible through the earlier result;
* `vars(cls)` is a mappingproxy, a different object on each call, refusing
  item assignment with TypeError and showing a class attribute set after it
  was taken;
* a `__dict__` property runs exactly once per vars() call and its result is
  returned by identity;
* at module scope `vars() is globals()`; in a class body `vars() is locals()`
  and a key written into it becomes a class attribute;
* in a function the snapshot holds every bound local and no unbound one, a
  key written into it is not seen by the function, and two snapshots from the
  same call are one object up to 3.12 and two objects from 3.13;
* `.copy()`, `dict()` and `**` unpacking each build a new object;
* `vars(42)`, an instance whose `__slots__` omit `__dict__` and a `__dict__`
  getter that raises AttributeError all give the page's TypeError, and a
  `__dict__` slot brings the instance dict back.

Traced allocation separates the O(1) rows from the O(k) one on the pinned
interpreter (aarch64, CPython 3.14): a warm `vars(obj)` allocates nothing at
1,000 or 10,000 attributes and `vars(cls)` 40 bytes at 10,000, where
`.copy()` and `dict()` allocate 25,968 bytes at 1,000 and 207,552 at 10,000,
and `f(**vars(obj))` 80,984 and 678,952. `vars(obj)` on an instance whose
attributes still live inline (3.11 and later) materialises the dict on first
access, but inline storage holds at most SHARED_KEYS_MAX_SIZE = 30 attributes,
so that first call is bounded and the row stays O(1).

Elapsed time settles the function-scope row: x16 in bound locals (1,000 to
16,000) costs x21.1 on 3.10, x16.6 on 3.11, x22.5 on 3.12, x211.5 on 3.13 and
x211.6 on 3.14, where linear predicts x16 and quadratic x256. The assignments
that bind the locals are included in the timed call; a control function with
the same assignments and no vars() shows they are about 1% of it at 8,000.
The getattr-loop comparison is timed at three attributes, in batches of 1,000
calls, where the loop costs x111 what `vars(obj)` does.

Not varied: the cost of a user-defined `__dict__` descriptor beyond counting
its calls, unbound locals as a share of the frame (the snapshot scans every
slot, bound or not, so an all-bound frame is the framing with the widest gap),
and the hash-collision worst case of the dict operations, which is dict's own
bound. `dir()`'s sort, `json.dumps` and `dataclasses.asdict` belong to their
own pages; the dataclass block is checked only for returning the instance's
own `__dict__` where asdict() returns a new one.
"""

import functools
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "vars.md"


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Plain:
    pass


def instance_with(count: int) -> Plain:
    obj = Plain()
    for index in range(count):
        setattr(obj, f"a{index}", index)
    vars(obj)  # materialise the dict, so the timed and traced calls are warm
    return obj


def keyword_count(**kwargs: Any) -> int:
    return len(kwargs)


class TestInstanceAndModuleRow:
    """`vars(obj)` on an instance or module is O(1): the object's own dict."""

    def test_an_instance_hands_back_its_own_dict(self) -> None:
        for count in (1, 10_000):
            obj = instance_with(count)
            assert vars(obj) is obj.__dict__
            assert len(vars(obj)) == count

    def test_a_module_hands_back_its_own_dict(self) -> None:
        module = types.ModuleType("sample")
        module.answer = 42  # type: ignore[attr-defined]
        assert vars(module) is module.__dict__
        assert vars(sys) is sys.__dict__

    def test_the_result_is_a_live_view_in_both_directions(self) -> None:
        obj = Plain()
        mapping = vars(obj)
        mapping["x"] = 1
        assert obj.x == 1  # type: ignore[attr-defined]
        obj.y = 2  # type: ignore[attr-defined]
        assert mapping["y"] == 2

        module = types.ModuleType("sample")
        vars(module)["x"] = 1
        assert module.x == 1  # type: ignore[attr-defined]

    def test_the_call_allocates_nothing_at_any_size(self) -> None:
        small, big = instance_with(1_000), instance_with(10_000)
        copy_peak = traced_peak(lambda: vars(small).copy())

        assert traced_peak(lambda: vars(small)) < copy_peak / 10
        assert traced_peak(lambda: vars(big)) < copy_peak / 10


class TestClassRow:
    """`vars(cls)` is a fresh read-only mappingproxy over the class namespace."""

    def test_a_class_gives_a_proxy_not_a_dict(self) -> None:
        assert type(vars(Plain)) is types.MappingProxyType
        assert vars(Plain) is not vars(Plain)

    def test_the_proxy_refuses_writes(self) -> None:
        with pytest.raises(TypeError):
            vars(Plain)["added"] = 1  # type: ignore[index]

    def test_the_proxy_is_a_view_of_the_class(self) -> None:
        class Sample:
            pass

        view = vars(Sample)
        Sample.later = 1  # type: ignore[attr-defined]
        assert view["later"] == 1

    def test_the_proxy_costs_nothing_per_attribute(self) -> None:
        class Wide:
            pass

        for index in range(10_000):
            setattr(Wide, f"a{index}", index)
        vars(Wide)

        copy_peak = traced_peak(lambda: dict(vars(Wide)))
        assert traced_peak(lambda: vars(Wide)) < copy_peak / 100


class TestCustomDescriptor:
    """A class that defines `__dict__` pays that descriptor's cost, once."""

    def test_the_descriptor_runs_once_and_its_result_is_returned(self) -> None:
        calls = 0
        namespace = {"n": 1}

        class Custom:
            @property
            def __dict__(self) -> dict[str, int]:  # type: ignore[override]
                nonlocal calls
                calls += 1
                return namespace

        assert vars(Custom()) is namespace
        assert calls == 1


class TestNoArgumentAtModuleAndClassScope:
    """Without an argument at module or class scope, vars() is the namespace."""

    def test_module_scope_is_globals(self) -> None:
        namespace: dict[str, Any] = {}
        exec("same = vars() is globals()", namespace)
        assert namespace["same"] is True

    def test_class_body_is_the_namespace_being_built(self) -> None:
        class Sample:
            same = vars() is locals()
            vars()["added"] = 1

        assert Sample.same is True
        assert Sample.added == 1  # type: ignore[attr-defined]


class TestNoArgumentInAFunction:
    """In a function, vars() is a snapshot of the frame's locals."""

    def test_the_snapshot_has_every_bound_local_and_no_unbound_one(self) -> None:
        def sample() -> dict[str, Any]:
            # Unused by design: vars() reads them out of the frame, which is
            # the behaviour under test.
            first = 1  # noqa: F841
            second = 2  # noqa: F841
            if first == 0:
                never = 3  # noqa: F841
            return vars()

        assert sample() == {"first": 1, "second": 2}

    def test_writes_to_the_snapshot_do_not_reach_the_function(self) -> None:
        def sample() -> int:
            value = 1
            vars()["value"] = 2
            return value

        assert sample() == 1

    def test_two_snapshots_share_a_dict_only_before_3_13(self) -> None:
        def sample() -> tuple[bool, int]:
            value = 1
            before = vars()
            value = 2  # noqa: F841 - read back through the snapshots, not the name
            after = vars()
            return before is after, before["value"]

        shared, seen_through_first = sample()
        if sys.version_info >= (3, 13):
            assert not shared and seen_through_first == 1
        else:
            assert shared and seen_through_first == 2

    @pytest.mark.timing
    def test_the_snapshot_is_quadratic_from_3_13_and_linear_before(self) -> None:
        def with_locals(count: int) -> Callable[[], dict[str, Any]]:
            namespace: dict[str, Any] = {}
            body = "".join(f"    v{i} = {i}\n" for i in range(count))
            exec(f"def f():\n{body}    return vars()\n", namespace)
            return namespace["f"]

        few, many = with_locals(1_000), with_locals(16_000)
        assert len(few()) == 1_000 and len(many()) == 16_000

        ratio = best_time(many) / best_time(few)

        if sys.version_info >= (3, 13):
            assert 60 < ratio < 1000, (
                f"x16 locals should cost near x256 from 3.13, got x{ratio:.1f}"
            )
        else:
            assert 8 < ratio < 60, f"x16 locals should cost near x16 before 3.13, got x{ratio:.1f}"


class TestCopyRow:
    """Copying the result costs the attribute count; the reference does not."""

    def test_each_copying_form_builds_a_new_object(self) -> None:
        obj = instance_with(3)
        original = vars(obj)
        assert original.copy() is not original
        assert dict(original) is not original

        def capture(**kwargs: Any) -> dict[str, Any]:
            return kwargs

        assert capture(**original) is not original
        assert capture(**original) == original

    def test_copies_grow_with_the_attribute_count(self) -> None:
        small, big = instance_with(1_000), instance_with(10_000)

        forms: list[tuple[str, Callable[[Plain], Any]]] = [
            ("copy()", lambda obj: vars(obj).copy()),
            ("dict()", lambda obj: dict(vars(obj))),
            ("** unpacking", lambda obj: keyword_count(**vars(obj))),
        ]
        for label, form in forms:
            small_peak = traced_peak(functools.partial(form, small))
            big_peak = traced_peak(functools.partial(form, big))
            assert big_peak > small_peak * 4, (
                f"{label}: x10 attributes should allocate near x10: {small_peak} vs {big_peak}"
            )


class TestTypeErrorRow:
    """An argument without `__dict__` raises TypeError."""

    @pytest.mark.parametrize("value", [42, "text", [1], object()], ids=type)
    def test_builtin_instances_have_no_dict(self, value: object) -> None:
        with pytest.raises(TypeError, match="__dict__"):
            vars(value)

    def test_an_instance_whose_slots_omit_dict_has_none(self) -> None:
        class Slotted:
            __slots__ = ("x",)

        with pytest.raises(TypeError, match="__dict__"):
            vars(Slotted())

    def test_a_dict_slot_restores_it(self) -> None:
        class Slotted:
            __slots__ = ("x", "__dict__")

        obj = Slotted()
        obj.y = 1  # type: ignore[attr-defined]
        assert vars(obj) == {"y": 1} and vars(obj) is obj.__dict__

    def test_a_dict_getter_raising_attribute_error_becomes_type_error(self) -> None:
        class Hidden:
            @property
            def __dict__(self) -> dict[str, Any]:  # type: ignore[override]
                raise AttributeError("hidden")

        with pytest.raises(TypeError, match="__dict__"):
            vars(Hidden())


class TestExampleClaims:
    """Claims the page's examples make beyond the table."""

    def test_dict_comparison_visits_every_attribute(self) -> None:
        compared = 0

        class Counting:
            def __eq__(self, other: object) -> bool:
                nonlocal compared
                compared += 1
                return isinstance(other, Counting)

        first, second = Plain(), Plain()
        for index in range(50):
            setattr(first, f"a{index}", Counting())
            setattr(second, f"a{index}", Counting())

        assert vars(first) == vars(second)
        assert compared == 50

    @pytest.mark.timing
    def test_the_getattr_loop_is_far_slower_than_vars(self) -> None:
        obj = Plain()
        obj.x, obj.y, obj.z = 1, 2, 3  # type: ignore[attr-defined]

        def loop() -> dict[str, Any]:
            attrs: dict[str, Any] = {}
            for name in dir(obj):
                try:
                    attrs[name] = getattr(obj, name)
                except AttributeError:
                    pass
            return attrs

        def many_loops() -> None:
            for _ in range(1_000):
                loop()

        def many_vars() -> None:
            for _ in range(1_000):
                vars(obj)

        ratio = best_time(many_loops) / best_time(many_vars)
        assert ratio > 10, f"the dir()/getattr loop should dwarf vars(): x{ratio:.1f}"


EXPECTED_BLOCKS = 24


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


def _block_containing(marker: str) -> str:
    matches = [source for _, source in _blocks() if marker in source]
    assert len(matches) == 1, f"{len(matches)} blocks contain {marker!r}"
    return matches[0]


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
    """Every block runs, under the interpreter running the tests."""

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

    def test_every_block_binds_the_names_it_uses(self, tmp_path: pathlib.Path) -> None:
        """A block that leans on a name from its prose rather than binding it
        compiles and then dies at run time, so NameError gets its own check."""
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        source = _block_containing("vars(42)")
        broken = source.replace("except TypeError:", "except ValueError:", 1)
        assert broken != source, "the mutation did not change the handler"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "TypeError" in result.stderr

    @pytest.mark.parametrize(
        ("marker", "check"),
        [
            (
                "merge_objects(obj1, obj2)",
                "assert merged == {'host': 'localhost', 'port': 8000}, merged",
            ),
            (
                "p2 = p1.copy()",
                "assert vars(p2) == {'x': 2, 'y': 4, 'z': 6} and vars(p2) is not vars(p1)",
            ),
            (
                "all_attrs = dir(obj)",
                "assert all_attrs == sorted(all_attrs)\n"
                "assert all_attrs[-2:] == ['class_attr', 'instance_attr']\n"
                "assert inst_attrs == {'instance_attr': 20}",
            ),
            (
                "person_dict = vars(person)",
                "from dataclasses import asdict\n"
                "assert person_dict is person.__dict__\n"
                "assert asdict(person) == person_dict and asdict(person) is not person_dict",
            ),
            (
                "slot_dict = obj.to_dict()",
                "assert slot_dict == {'x': 1, 'y': 2, 'z': 3}",
            ),
            (
                "attrs_copy = vars(obj).copy()",
                "assert obj.x == 1 and not hasattr(obj, 'y')",
            ),
            (
                "state = vars(config)",
                "assert state == {'host': 'localhost', 'port': 8000, 'debug': True}",
            ),
        ],
        ids=["merge", "point-copy", "dir", "dataclass", "slots", "copy-vs-reference", "config"],
    )
    def test_the_stated_output_is_what_the_block_produces(
        self, marker: str, check: str, tmp_path: pathlib.Path
    ) -> None:
        result = _run(_block_containing(marker) + "\n" + check + "\n", tmp_path)

        assert result.returncode == 0, result.stderr.strip()
