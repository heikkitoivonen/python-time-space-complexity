"""Tests for docs/builtins/getattr.md.

getattr() is builtin_getattr in Python/bltinmodule.c, unchanged from 3.11 to
3.15: with two arguments it is PyObject_GetAttr, the lookup ``obj.name``
does; with a default it is PyObject_GetOptionalAttr (``_PyObject_LookupAttr``
up to 3.12), which returns the default when the lookup reports a missing
attribute and lets every other exception through. Both reject a non-str name
with TypeError before any lookup. The generic path is
_PyObject_GenericGetAttrWithDict: a _PyType_Lookup of the name on the type
followed by an instance-dict probe. _PyType_Lookup (Objects/typeobject.c)
consults a per-interpreter cache indexed by the type's version tag and the
name object's address, whose entries match on name identity (entry->name ==
name), not on string equality. It stores NULL results as readily as found
ones, and only on a miss walks the MRO with one dict lookup per class. A name
is cacheable only when it is an exact str of at most MCACHE_MAX_ATTR_SIZE
(100) characters, so a str subclass forces the walk on every call - the lever
most timing tests use - and so does an equal but distinct str object, such as
an f-string result built per call, until sys.intern() maps it to one object.
Assigning to a class or a base clears the version tag; the next lookup assigns
a fresh one. From the v3.13.0 tag assign_version_tag refuses once
tp_versions_used reaches MAX_VERSIONS_PER_CLASS (1,000), after which nothing
on that class is cached again; 3.11 and 3.12 have no such limit.

Measurement scope:

* Observation settles the hook, default and TypeError rows: a property getter
  runs once per getattr() call; ``__getattr__`` runs once per miss and not on a
  hit; an AttributeError from a getter or ``__getattr__`` becomes the default,
  where a KeyError from a getter and a ValueError from ``__getattr__``
  propagate; the default expression runs once even when the attribute exists;
  an int, bytes or None name raises TypeError with and without a default
  before a counting ``__getattribute__`` is reached, and a str subclass is
  accepted.
* A counting ``__getattribute__`` sees one call for getattr() with or without
  a default, hit or miss, and two for hasattr() followed by getattr().
* Traced allocation during one getattr() of a stored class attribute on a
  1,024-class chain is zero for a cached hit, a cached miss with a default, a str-subclass name that walks the
  MRO, and the first lookup after the class changed; a getter that builds a
  100,000-element list is charged to the call (at least 800,000 bytes).
* Elapsed time settles the two lookup rows on the pinned interpreter. With an
  exact str name, a hit or a defaulted miss on a class 1,024 deep costs the
  same as on one 2 deep (asserted under x3), where the same names as a str
  subclass, a 101-character miss, and names rebuilt by "".join() before each
  call cost over x20 more; sys.intern() on the rebuilt names brings them back
  under x3. On 3.11 to 3.15 the rebuilt names measured x127 to x195. Building
  and interning the names happen outside the timed loop, so the cost of
  sys.intern() itself is not measured. Assigning to the class before each lookup
  costs over x20 more per iteration at 1,024 than at 2, where assigning to the
  instance costs under x3. After 1,100 assignments to the 1,024-deep class
  getattr() costs over x20 what it did before on 3.13 and later, and under x3
  on 3.11 and 3.12. dir() on an object with 10,000 class attributes costs
  over x20 what it does with 100, where getattr() costs under x3.

Not settled here: the type and module getattro paths beyond a check that a
defaulted miss on each returns the default; multiple inheritance (the MRO is a
chain here; its length is what the cache hides, whatever its shape); the
cache's capacity, which a program touching more (class, name) pairs than it
holds between repeats overflows; and the instance dict's hash-collision worst
case, which is dict's own bound. The Direct Access block's statement that
getattr() adds one builtin call to the lookup is source-only: both have the
same semantics, getattr() through PyObject_GetAttr and ``obj.name`` through
LOAD_ATTR, which specialised forms may serve without calling it; no ratio is
asserted.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "getattr.md"
EXPECTED_BLOCKS = 12


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


def chain(depth: int) -> type:
    """A class with `depth` classes of its own above object, `a_attr` on the root."""
    cls = type("L0", (), {"a_attr": 1})
    for index in range(1, depth):
        cls = type(f"L{index}", (cls,), {})
    return cls


class Name(str):
    """A str subclass: accepted by getattr(), never cached by the type lookup."""


def per_call(obj: object, name: str, calls: int = 20_000) -> float:
    def loop() -> None:
        for _ in range(calls):
            getattr(obj, name, None)

    getattr(obj, name, None)  # warm the cache for the exact-str case
    return best_time(loop) / calls


class TestCachedLookupRows:
    """`getattr(obj, name)` and `getattr(obj, name, default)` are O(1) once the
    class-level lookup is cached; a name the cache refuses walks the MRO."""

    def test_a_hit_returns_the_value_and_a_miss_raises_or_defaults(self) -> None:
        obj = chain(4)()
        sentinel = object()
        assert getattr(obj, "a_attr") == 1
        assert getattr(obj, "a_attr", sentinel) == 1
        assert getattr(obj, "missing", sentinel) is sentinel
        with pytest.raises(AttributeError, match="missing"):
            getattr(obj, "missing")
        assert getattr(chain(4), "missing", sentinel) is sentinel
        assert getattr(sys, "missing", sentinel) is sentinel

    def test_the_attribute_value_wins_over_the_default(self) -> None:
        class User:
            email = None

        assert getattr(User(), "email", "no@email.com") is None

    @pytest.mark.timing
    def test_depth_costs_nothing_when_cached_and_everything_when_not(self) -> None:
        shallow, deep = chain(2)(), chain(1_024)()

        cached_hit = per_call(deep, "a_attr") / per_call(shallow, "a_attr")
        cached_miss = per_call(deep, "missing") / per_call(shallow, "missing")
        walked_hit = per_call(deep, Name("a_attr")) / per_call(shallow, Name("a_attr"))
        walked_miss = per_call(deep, Name("missing")) / per_call(shallow, Name("missing"))
        long_miss = per_call(deep, "m" * 101) / per_call(shallow, "m" * 101)

        assert cached_hit < 3 and cached_miss < 3, (
            f"x512 classes should cost nothing cached: hit x{cached_hit:.1f}, miss x{cached_miss:.1f}"
        )
        assert walked_hit > 20 and walked_miss > 20 and long_miss > 20, (
            f"x512 classes should cost near x512 uncached: hit x{walked_hit:.1f}, "
            f"miss x{walked_miss:.1f}, 101-character miss x{long_miss:.1f}"
        )

    @pytest.mark.timing
    def test_a_name_built_per_call_misses_the_cache_until_interned(self) -> None:
        """The cache matches name objects, so equal text in a fresh object walks."""

        def rebuilt(parts: list[str], intern: bool) -> Callable[[object], float]:
            def cost(obj: object) -> float:
                names = ["".join(parts) for _ in range(20_000)]
                if intern:
                    names = [sys.intern(name) for name in names]
                assert names[0] is not names[1] or intern

                def loop() -> None:
                    for name in names:
                        getattr(obj, name, None)

                return best_time(loop)

            return cost

        shallow, deep = chain(2)(), chain(1_024)()
        for parts in (["a_", "attr"], ["mis", "sing"]):
            fresh, interned = rebuilt(parts, False), rebuilt(parts, True)
            walked = fresh(deep) / fresh(shallow)
            cached = interned(deep) / interned(shallow)
            assert walked > 20, f"x512 classes should cost a fresh name near x512: x{walked:.1f}"
            assert cached < 3, f"x512 classes should cost an interned name nothing: x{cached:.1f}"


class TestColdLookupRow:
    """The first lookup after a class changes walks the MRO; from 3.13 a class
    changed more than 1,000 times walks it on every lookup."""

    def test_assigning_to_a_class_does_not_change_the_answer(self) -> None:
        cls = chain(4)
        obj = cls()
        assert getattr(obj, "later", None) is None
        cls.later = 1
        assert getattr(obj, "later") == 1
        del cls.later
        assert getattr(obj, "later", None) is None

    def test_assigning_to_a_base_does_not_change_the_answer(self) -> None:
        cls = chain(4)
        obj, root = cls(), cls.__mro__[-2]
        assert root.__name__ == "L0"
        assert getattr(obj, "later", None) is None and getattr(obj, "a_attr") == 1
        root.later = 2
        root.a_attr = 3
        assert getattr(obj, "later") == 2 and getattr(obj, "a_attr") == 3

    @pytest.mark.timing
    def test_the_first_lookup_after_a_change_walks_the_mro(self) -> None:
        """900 changes per class keeps every class under the 3.13 limit, and a
        fresh class per repeat keeps the count from accumulating."""

        def changing_the_class(depth: int) -> float:
            def one_run() -> float:
                cls = chain(depth)
                obj = cls()
                getattr(obj, "a_attr")

                def loop() -> None:
                    for index in range(900):
                        cls.counter = index
                        getattr(obj, "a_attr")

                return best_time(loop, repeats=1)

            return min(one_run() for _ in range(5))

        def changing_the_instance(depth: int) -> float:
            obj = chain(depth)()
            getattr(obj, "a_attr")

            def loop() -> None:
                for index in range(900):
                    obj.counter = index
                    getattr(obj, "a_attr")

            return best_time(loop)

        walked = changing_the_class(1_024) / changing_the_class(2)
        cached = changing_the_instance(1_024) / changing_the_instance(2)

        assert walked > 20, f"a lookup after each class change should cost the depth: x{walked:.1f}"
        assert cached < 3, f"a lookup after each instance change should not: x{cached:.1f}"

    @pytest.mark.timing
    def test_a_much_modified_class_stays_uncached_only_from_3_13(self) -> None:
        cls = chain(1_024)
        obj = cls()
        before = per_call(obj, "a_attr")

        for index in range(1_100):
            cls.counter = index
            getattr(obj, "a_attr")
        after = per_call(obj, "a_attr")

        ratio = after / before
        if sys.version_info >= (3, 13):
            assert ratio > 20, (
                f"1,100 changes should leave a 1,024-deep class uncached: x{ratio:.1f}"
            )
        else:
            assert ratio < 3, f"before 3.13 the class should be cached again: x{ratio:.1f}"


class TestSpaceColumn:
    """Reading a stored class attribute allocates nothing, cached or walked, and
    a defaulted miss allocates nothing; a hook's allocation is the call's."""

    @pytest.mark.serial
    def test_no_lookup_path_allocates(self) -> None:
        cls = chain(1_024)
        obj = cls()
        getattr(obj, "a_attr")
        getattr(obj, "missing", None)
        walked_hit, walked_miss = Name("a_attr"), Name("missing")

        # partial, not a lambda: on 3.12+ a cold Python code object allocates
        # monitoring data on its first run once any test has called settrace().
        assert traced_peak(partial(getattr, obj, "a_attr")) == 0
        assert traced_peak(partial(getattr, obj, "missing", None)) == 0
        assert traced_peak(partial(getattr, obj, walked_hit)) == 0
        assert traced_peak(partial(getattr, obj, walked_miss, None)) == 0
        cls.changed = 1
        assert traced_peak(partial(getattr, obj, "a_attr")) == 0

    def test_a_hook_allocation_is_charged_to_the_call(self) -> None:
        class Sample:
            @property
            def big(self) -> list[None]:
                return [None] * 100_000

        obj = Sample()
        assert traced_peak(lambda: getattr(obj, "big")) >= 100_000 * 8


class TestHookRow:
    """A property getter or `__getattr__` runs inside getattr(); only
    AttributeError becomes the default."""

    def test_a_property_getter_runs_once_per_call(self) -> None:
        runs = 0

        class Sample:
            @property
            def computed(self) -> int:
                nonlocal runs
                runs += 1
                return 100

        obj = Sample()
        assert getattr(obj, "computed") == 100
        assert runs == 1
        assert getattr(obj, "computed", None) == 100
        assert runs == 2

    def test_getattr_hook_runs_on_a_miss_and_not_on_a_hit(self) -> None:
        seen: list[str] = []

        class Sample:
            present = 1

            def __getattr__(self, name: str) -> Any:
                seen.append(name)
                raise AttributeError(name)

        obj = Sample()
        assert getattr(obj, "present") == 1
        assert seen == []
        assert getattr(obj, "missing", None) is None
        assert seen == ["missing"]
        with pytest.raises(AttributeError):
            getattr(obj, "missing")
        assert seen == ["missing", "missing"]

    def test_only_attribute_error_becomes_the_default(self) -> None:
        class Sample:
            @property
            def broken(self) -> int:
                raise KeyError("not an AttributeError")

            @property
            def absent(self) -> int:
                raise AttributeError("absent")

            def __getattr__(self, name: str) -> Any:
                if name == "loud":
                    raise ValueError(name)
                raise AttributeError(name)

        obj = Sample()
        assert getattr(obj, "absent", "d") == "d"
        assert getattr(obj, "quiet", "d") == "d"
        with pytest.raises(KeyError):
            getattr(obj, "broken", "d")
        with pytest.raises(ValueError):
            getattr(obj, "loud", "d")


class TestDefaultIsEager:
    """The default expression is evaluated before the call, hit or miss."""

    def test_the_default_runs_even_when_the_attribute_exists(self) -> None:
        calls = 0

        def default() -> list[int]:
            nonlocal calls
            calls += 1
            return []

        class Cache:
            items = [1, 2, 3]

        assert getattr(Cache(), "items", default()) == [1, 2, 3]
        assert calls == 1


class TestLookupCounts:
    """getattr() is one lookup with or without a default; hasattr() then
    getattr() is two."""

    def test_each_form_does_the_stated_number_of_lookups(self) -> None:
        lookups = 0

        class Counting:
            attr = 1

            def __getattribute__(self, name: str) -> Any:
                nonlocal lookups
                lookups += 1
                return object.__getattribute__(self, name)

        obj = Counting()

        for call in (
            lambda: getattr(obj, "attr"),
            lambda: getattr(obj, "attr", None),
            lambda: getattr(obj, "missing", None),
        ):
            lookups = 0
            call()
            assert lookups == 1

        lookups = 0
        with pytest.raises(AttributeError):
            getattr(obj, "missing")
        assert lookups == 1

        lookups = 0
        if hasattr(obj, "attr"):
            getattr(obj, "attr")  # noqa: B009 - the call form is the one being counted
        assert lookups == 2


class TestTypeErrorRow:
    """A non-str name raises TypeError before any lookup, with or without a default."""

    @pytest.mark.parametrize("name", [42, b"attr", None], ids=type)
    @pytest.mark.parametrize("with_default", [False, True], ids=["no-default", "default"])
    def test_a_non_str_name_raises_before_the_lookup(
        self, name: object, with_default: bool
    ) -> None:
        lookups = 0

        class Counting:
            def __getattribute__(self, name: str) -> Any:
                nonlocal lookups
                lookups += 1
                return object.__getattribute__(self, name)

        args: tuple[object, ...] = (Counting(), name, None) if with_default else (Counting(), name)
        with pytest.raises(TypeError, match="must be string"):
            getattr(*args)  # type: ignore[call-overload]
        assert lookups == 0

    def test_a_str_subclass_is_accepted(self) -> None:
        obj = chain(2)()
        assert getattr(obj, Name("a_attr")) == 1
        assert getattr(obj, Name("missing"), None) is None


class TestDirIsNotAShortcut:
    """Listing names through dir() costs the whole attribute list."""

    @pytest.mark.timing
    def test_dir_grows_with_the_attribute_count_and_a_lookup_does_not(self) -> None:
        def with_attributes(count: int) -> object:
            cls = chain(1)
            for index in range(count):
                setattr(cls, f"a{index}", index)
            cls.x = 1
            return cls()

        narrow, wide = with_attributes(100), with_attributes(10_000)

        def dir_of(obj: object) -> Callable[[], None]:
            def loop() -> None:
                for _ in range(20):
                    dir(obj)

            return loop

        dir_ratio = best_time(dir_of(wide)) / best_time(dir_of(narrow))
        lookup_ratio = per_call(wide, "x") / per_call(narrow, "x")

        assert dir_ratio > 20, f"x100 attributes should cost dir() near x100: x{dir_ratio:.1f}"
        assert lookup_ratio < 3, (
            f"x100 attributes should cost getattr() nothing: x{lookup_ratio:.1f}"
        )


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
    """Every block runs, under the interpreter running the tests, and pins its
    own results with assertions."""

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

    @pytest.mark.parametrize(
        ("marker", "old", "new", "error"),
        [
            ("except KeyError:", "except KeyError:", "except LookupError:\n    raise", "KeyError"),
            ("expensive_default()", "calls == 1\n", "calls == 0\n", "AssertionError"),
            ("assert lookups == 2", "== 2", "== 1", "AssertionError"),
        ],
        ids=["propagates", "eager-default", "lookup-count"],
    )
    def test_the_runner_catches_a_broken_block(
        self, marker: str, old: str, new: str, error: str, tmp_path: pathlib.Path
    ) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        source = _block_containing(marker)
        broken = source.replace(old, new, 1)
        assert broken != source, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert error in result.stderr
