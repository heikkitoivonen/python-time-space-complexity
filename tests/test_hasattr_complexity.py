"""Tests for docs/builtins/hasattr.md.

hasattr() is builtin_hasattr_impl in Python/bltinmodule.c: one
PyObject_GetOptionalAttr (``_PyObject_LookupAttr`` up to 3.11) in
Objects/object.c, which rejects a non-str name with TypeError before any
lookup, reports a missing attribute as a NULL result rather than a raised
AttributeError for the generic, type and module getattro paths, and lets
every other exception through. The generic path is
_PyObject_GenericGetAttrWithDict: a _PyType_Lookup of the name on the type
followed by an instance-dict probe. _PyType_Lookup (Objects/typeobject.c)
consults a per-interpreter cache of 1 << MCACHE_SIZE_EXP (4,096) entries keyed
by the type's version tag and the name's hash, storing NULL results as readily
as found ones, and only on a miss walks the MRO with one dict lookup per class
(find_name_in_mro). A name is cacheable only when it is an exact str of at most
MCACHE_MAX_ATTR_SIZE (100) characters, so a str subclass forces the walk on
every call - the lever the timing tests use. Assigning to a class or a base
clears the version tag (type_modified); the next lookup assigns a fresh one.
From the v3.13.0 tag assign_version_tag refuses once tp_versions_used reaches
MAX_VERSIONS_PER_CLASS (1,000), after which nothing on that class is cached
again; 3.10 through 3.12 have no such limit.

Observation settles the hook and TypeError rows:

* a property getter runs exactly once per hasattr() call and the result is
  True; ``__getattr__`` runs once per miss and not at all on a hit, and one
  that returns a value makes every name exist;
* a KeyError from a getter and a ValueError from ``__getattr__`` both
  propagate, where an AttributeError from either becomes False;
* a counting ``__getattribute__`` sees one call for hasattr(), one for
  getattr() with a default, and two for hasattr() followed by getattr() or an
  attribute access;
* an int, bytes or None name raises TypeError before ``__getattribute__`` is
  reached, and a str subclass is accepted;
* traced allocation during one hasattr() on a 1,024-class chain is zero for a
  cached hit and miss, for a str-subclass name that walks the MRO, and for the
  first lookup after the class changed; a getter that builds a 100,000-element
  list is charged to the call (800,008 bytes), and a Python-level
  ``__getattr__`` miss allocates a few hundred bytes for its AttributeError
  (624 on 3.14).

Elapsed time settles the two lookup rows on the pinned interpreter (aarch64,
CPython 3.14). With an exact str name, a hit or a miss on a class 1,024 deep
costs the same as on one 2 deep, where the same name as a str subclass costs
x99 more at 1,024 than at 2 and a 101-character exact str x119. Assigning to the class and then looking the name
up costs x79 more per iteration at 1,024 than at 2, where assigning to the
instance instead costs x1.2. After 1,100 assignments to the class, hasattr()
on the 1,024-deep class costs x160 what it did before them on 3.14 and x215
on 3.13, and x1.0 on 3.12; 1,100 assignments to the root of its MRO give x168
on 3.14 and x1.0 on 3.12. One set(dir(obj)) against an object with 1,000 class
attributes costs x846 what three hasattr() calls do, and x100 class attributes
(100 to 10,000) cost dir() x80 where hasattr() costs x1.0.

Not varied: multiple inheritance (the MRO is a chain here; its length is what
the cache hides, whatever its shape), the type and module getattro paths
beyond a plain check that a miss on each is False, the cache's 4,096-entry
capacity (a program touching more (class, name) pairs than that between
repeats evicts its own entries), and the instance dict's hash-collision worst
case, which is dict's own bound. The Python 2 row of the page cannot be run
here: it describes hasattr() swallowing every exception, which the 3.2 change
to AttributeError-only removed.
"""

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "hasattr.md"


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
    """A str subclass: accepted by hasattr(), never cached by the type lookup."""


def per_call(obj: object, name: str, calls: int = 20_000) -> float:
    def loop() -> None:
        for _ in range(calls):
            hasattr(obj, name)

    hasattr(obj, name)  # warm the cache for the exact-str case
    return best_time(loop) / calls


class TestCachedLookupRow:
    """`hasattr(obj, name)` is O(1) once the class-level lookup is cached."""

    def test_a_hit_and_a_miss_are_plain_booleans(self) -> None:
        obj = chain(4)()
        assert hasattr(obj, "a_attr") is True
        assert hasattr(obj, "missing") is False
        assert hasattr(chain(4), "a_attr") is True and hasattr(chain(4), "missing") is False
        assert hasattr(sys, "missing") is False

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


class TestColdLookupRow:
    """The first lookup after a class changes walks the MRO; from 3.13 a class
    changed more than 1,000 times walks it on every lookup."""

    def test_assigning_to_a_class_does_not_change_the_answer(self) -> None:
        cls = chain(4)
        obj = cls()
        assert hasattr(obj, "a_attr") and not hasattr(obj, "later")
        cls.later = 1
        assert hasattr(obj, "later")
        del cls.later
        assert not hasattr(obj, "later")

    @pytest.mark.timing
    def test_the_first_lookup_after_a_change_walks_the_mro(self) -> None:
        """900 changes per class keeps every class under the 3.13 limit, and a
        fresh class per repeat keeps the count from accumulating."""

        def changing_the_class(depth: int) -> float:
            def one_run() -> float:
                cls = chain(depth)
                obj = cls()
                hasattr(obj, "a_attr")

                def loop() -> None:
                    for index in range(900):
                        cls.counter = index
                        hasattr(obj, "a_attr")

                return best_time(loop, repeats=1)

            return min(one_run() for _ in range(5))

        def changing_the_instance(depth: int) -> float:
            obj = chain(depth)()
            hasattr(obj, "a_attr")

            def loop() -> None:
                for index in range(900):
                    obj.counter = index
                    hasattr(obj, "a_attr")

            return best_time(loop)

        walked = changing_the_class(1_024) / changing_the_class(2)
        cached = changing_the_instance(1_024) / changing_the_instance(2)

        assert walked > 20, f"a lookup after each class change should cost the depth: x{walked:.1f}"
        assert cached < 3, f"a lookup after each instance change should not: x{cached:.1f}"

    @pytest.mark.timing
    @pytest.mark.parametrize("modified", ["leaf", "root"])
    def test_a_much_modified_class_stays_uncached_only_from_3_13(self, modified: str) -> None:
        cls = chain(1_024)
        target = cls if modified == "leaf" else cls.__mro__[-2]
        assert target.__name__ == {"leaf": "L1023", "root": "L0"}[modified]
        obj = cls()
        before = per_call(obj, "a_attr")

        for index in range(1_100):
            target.counter = index
            hasattr(obj, "a_attr")
        after = per_call(obj, "a_attr")

        ratio = after / before
        if sys.version_info >= (3, 13):
            assert ratio > 20, (
                f"1,100 changes should leave a 1,024-deep class uncached: x{ratio:.1f}"
            )
        else:
            assert ratio < 3, f"before 3.13 the class should be cached again: x{ratio:.1f}"


class TestSpaceColumn:
    """A lookup allocates nothing on any path; a hook's allocation is the call's."""

    @pytest.mark.serial
    def test_no_lookup_path_allocates(self) -> None:
        cls = chain(1_024)
        obj = cls()
        hasattr(obj, "a_attr")
        hasattr(obj, "missing")
        walked_hit, walked_miss = Name("a_attr"), Name("missing")

        assert traced_peak(lambda: hasattr(obj, "a_attr")) == 0
        assert traced_peak(lambda: hasattr(obj, "missing")) == 0
        assert traced_peak(lambda: hasattr(obj, walked_hit)) == 0
        assert traced_peak(lambda: hasattr(obj, walked_miss)) == 0
        cls.changed = 1
        assert traced_peak(lambda: hasattr(obj, "a_attr")) == 0

    def test_a_hook_allocation_is_charged_to_the_call(self) -> None:
        class Sample:
            @property
            def big(self) -> list[None]:
                return [None] * 100_000

            def __getattr__(self, name: str) -> Any:
                raise AttributeError(name)

        obj = Sample()
        assert traced_peak(lambda: hasattr(obj, "big")) >= 100_000 * 8
        assert 0 < traced_peak(lambda: hasattr(obj, "nope")) < 4_096


class TestHookRow:
    """A property getter or `__getattr__` runs inside hasattr(); only
    AttributeError becomes False."""

    def test_a_property_getter_runs_once_per_call(self) -> None:
        runs = 0

        class Sample:
            @property
            def computed(self) -> int:
                nonlocal runs
                runs += 1
                return 100

        obj = Sample()
        assert hasattr(obj, "computed") is True
        assert runs == 1
        hasattr(obj, "computed")
        assert runs == 2

    def test_getattr_runs_on_a_miss_and_not_on_a_hit(self) -> None:
        seen: list[str] = []

        class Sample:
            present = 1

            def __getattr__(self, name: str) -> Any:
                seen.append(name)
                raise AttributeError(name)

        obj = Sample()
        assert hasattr(obj, "present") is True
        assert seen == []
        assert hasattr(obj, "missing") is False
        assert seen == ["missing"]
        assert hasattr(obj, "missing") is False
        assert seen == ["missing", "missing"]

    def test_a_returning_getattr_makes_every_name_exist(self) -> None:
        class Permissive:
            def __getattr__(self, name: str) -> None:
                return None

        assert hasattr(Permissive(), "anything") is True

    def test_only_attribute_error_becomes_false(self) -> None:
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
        assert hasattr(obj, "absent") is False
        assert hasattr(obj, "quiet") is False
        with pytest.raises(KeyError):
            hasattr(obj, "broken")
        with pytest.raises(ValueError):
            hasattr(obj, "loud")


class TestLookupCounts:
    """hasattr() is one lookup; hasattr() then getattr() or an access is two."""

    def test_each_form_does_the_stated_number_of_lookups(self) -> None:
        lookups = 0

        class Counting:
            attr = 1

            def __getattribute__(self, name: str) -> Any:
                nonlocal lookups
                lookups += 1
                return object.__getattribute__(self, name)

        obj = Counting()

        lookups = 0
        hasattr(obj, "attr")
        assert lookups == 1

        lookups = 0
        getattr(obj, "attr", None)
        assert lookups == 1

        lookups = 0
        try:
            obj.attr  # noqa: B018 - the access is the lookup being counted
        except AttributeError:
            pass
        assert lookups == 1

        lookups = 0
        if hasattr(obj, "attr"):
            getattr(obj, "attr")  # noqa: B009 - the call form is the one being counted
        assert lookups == 2

        lookups = 0
        if hasattr(obj, "attr"):
            obj.attr  # noqa: B018 - the access is the lookup being counted
        assert lookups == 2


class TestTypeErrorRow:
    """A non-str name raises TypeError before any lookup happens."""

    @pytest.mark.parametrize("name", [42, b"attr", None], ids=type)
    def test_a_non_str_name_raises_before_the_lookup(self, name: object) -> None:
        lookups = 0

        class Counting:
            def __getattribute__(self, name: str) -> Any:
                nonlocal lookups
                lookups += 1
                return object.__getattribute__(self, name)

        with pytest.raises(TypeError, match="must be string"):
            hasattr(Counting(), name)  # type: ignore[arg-type]
        assert lookups == 0

    def test_a_str_subclass_is_accepted(self) -> None:
        obj = chain(2)()
        assert hasattr(obj, Name("a_attr")) is True
        assert hasattr(obj, Name("missing")) is False


class TestDirIsNotAShortcut:
    """Checking a few names through dir() costs the whole attribute list."""

    def test_dir_grows_with_the_attribute_count(self) -> None:
        narrow, wide = chain(1), chain(1)
        for index in range(1_000):
            setattr(wide, f"a{index}", index)
        assert len(dir(wide())) - len(dir(narrow())) == 1_000

    @pytest.mark.timing
    def test_three_lookups_beat_one_dir(self) -> None:
        cls = chain(1)
        for index in range(1_000):
            setattr(cls, f"a{index}", index)
        cls.x = cls.y = cls.z = 1
        obj = cls()

        def three_lookups() -> None:
            for _ in range(1_000):
                found = hasattr(obj, "x") and hasattr(obj, "y") and hasattr(obj, "z")  # noqa: F841

        def one_dir() -> None:
            for _ in range(1_000):
                present = {"x", "y", "z"} <= set(dir(obj))  # noqa: F841 - timed, not used

        ratio = best_time(one_dir) / best_time(three_lookups)
        assert ratio > 10, f"set(dir(obj)) should dwarf three hasattr() calls: x{ratio:.1f}"

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
                    set(dir(obj))

            return loop

        dir_ratio = best_time(dir_of(wide)) / best_time(dir_of(narrow))
        lookup_ratio = per_call(wide, "x") / per_call(narrow, "x")

        assert dir_ratio > 20, f"x100 attributes should cost dir() near x100: x{dir_ratio:.1f}"
        assert lookup_ratio < 3, (
            f"x100 attributes should cost hasattr() nothing: x{lookup_ratio:.1f}"
        )


EXPECTED_BLOCKS = 16


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
        source = _block_containing("hasattr(obj, 42)")
        broken = source.replace("except TypeError:", "except ValueError:", 1)
        assert broken != source, "the mutation did not change the handler"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "TypeError" in result.stderr

    @pytest.mark.parametrize(
        ("marker", "check", "stdout"),
        [
            (
                "hasattr_simulation",
                "assert hasattr_simulation(obj, 'missing') is False\n"
                "assert hasattr_simulation(Strict, 'broken') is True",
                ["False", "only AttributeError means False", "the name must be a str"],
            ),
            (
                "validate_object(FileWriter(), required)",
                "assert missing == ['flush'], missing",
                [],
            ),
            (
                "manager.get_capabilities(SimplePlugin())",
                "assert caps == ['process', 'validate'], caps",
                [],
            ),
            (
                'safe_process(minimal, "data")',
                "assert result1 == 'Processed: data' and result2 is None",
                [],
            ),
            ("config.get_port()", "assert port == 9000", []),
            (
                "process_data(buffer)",
                "assert buffer.getvalue() == 'contentCONTENT'",
                ["contentCONTENT"],
            ),
            ("Countdown(3)", "assert list(Countdown(3)) == [3, 2, 1]", ["3", "2", "1"]),
            ('print("computing")', "", ["True", "True", "computing", "True"]),
            ("Permissive", "assert result is False", ["Looking up: missing", "True"]),
            (
                "hasattr(obj, 'host'):  # lookup one",
                "assert value == 'localhost'",
                [],
            ),
        ],
        ids=[
            "simulation",
            "validation",
            "plugins",
            "safe-process",
            "port",
            "duck-typing",
            "countdown",
            "property-runs",
            "getattr-side-effect",
            "default",
        ],
    )
    def test_the_stated_output_is_what_the_block_produces(
        self, marker: str, check: str, stdout: list[str], tmp_path: pathlib.Path
    ) -> None:
        result = _run(_block_containing(marker) + "\n" + check + "\n", tmp_path)

        assert result.returncode == 0, result.stderr.strip()
        assert result.stdout.splitlines() == stdout
