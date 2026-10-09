"""Tests for docs/builtins/dir.md.

dir() is builtin_dir in Python/bltinmodule.c, which calls PyObject_Dir in
Objects/object.c. With no argument, _dir_locals takes the keys of the local
mapping and sorts them. With an argument, _dir_object looks up `__dir__` on the
type, calls it, copies the result with PySequence_List and sorts that list.
object.__dir__ (Objects/typeobject.c) copies the instance `__dict__` and calls
merge_class_dict on `__class__`, which updates from the class `__dict__` and
recurses into every entry of `__bases__` with no visited set; type.__dir__ calls
merge_class_dict on the class alone. That code is the same in behaviour in the
v3.10.19, v3.11.14, v3.12.12, v3.13.11 and v3.14.2 tags, so no version is
treated apart.

Measurement scope:

* fresh sorted list: two calls return distinct, equal lists; a `__dir__`
  returning an unsorted tuple comes back as a sorted list, and `__dir__` is
  called once per dir() call;
* sort: a `__dir__` returning 4,096 shuffled str-subclass names with a
  counting `__lt__` makes between n and 2·n·log2(n) comparisons;
* p, the per-path merge: a metaclass counting `__dict__` lookups shows the root
  of a chain of d diamonds merged 2^d times for d = 1..10, and each class of a
  single-inheritance chain of 50 merged once;
* instance names: the instance `__dict__` names appear in dir(obj) and the
  instance `__dict__` is not modified;
* dir(cls) omits metaclass attributes: `mro` is reachable on int and absent
  from dir(int), and a metaclass method is absent from dir() of its class;
* modules: dir(module) equals sorted(module.__dict__) and a module-level
  `__dir__` function replaces it;
* no argument: dir() inside a function equals its sorted local names;
* `__getattr__` attributes are reachable and not listed;
* hasattr() never calls `__dir__`, and a counting `__getattribute__` records
  exactly one lookup, of the tested name;
* vars(obj) is the instance `__dict__` itself;
* every fenced block runs in a subprocess, and the runner is mutation-tested.

Not settled here:

* O(k + p) for the dictionary copy and merges and O(n) space are source-only
  beyond the counts above: they follow from PyDict_Copy, PyDict_Update and
  PySequence_List in the files named.
* The Best Practices lists are advice resting on the rows above.
* The recursive `__bases__` walk uses C stack proportional to inheritance
  depth; the page's O(n) space counts the result and its dictionary only.
* Not varied: instances whose `__dict__` is not a dict, classes whose
  `__bases__` is overridden, and the cost of a user `__dir__()` (named D).
"""

from __future__ import annotations

import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import types
from typing import Any

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "dir.md"
EXPECTED_BLOCKS = 7


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


def _counting_metaclass(lookups: dict[str, int]) -> type:
    class Meta(type):
        def __getattribute__(cls, name: str) -> Any:
            if name == "__dict__":
                own = type.__getattribute__(cls, "__name__")
                lookups[own] = lookups.get(own, 0) + 1
            return super().__getattribute__(name)

    return Meta


class TestResultIsAFreshSortedList:
    """Rows: every form returns a new list; a custom `__dir__` result is copied
    to a list and sorted."""

    def test_each_call_builds_a_new_list(self) -> None:
        first = dir(int)
        second = dir(int)

        assert first == second
        assert first is not second

    def test_custom_dir_result_is_listed_sorted_and_called_once(self) -> None:
        calls: list[int] = []

        class Proxy:
            def __dir__(self) -> tuple[str, ...]:
                calls.append(1)
                return ("zeta", "alpha", "mid")

        assert dir(Proxy()) == ["alpha", "mid", "zeta"]
        assert len(calls) == 1

    def test_sort_comparisons_are_n_log_n(self) -> None:
        comparisons = [0]

        class Name(str):
            __slots__ = ()

            def __lt__(self, other: object) -> bool:
                comparisons[0] += 1
                return str.__lt__(self, other)  # type: ignore[operator]

        n = 4096
        names = [Name(f"n{i:05d}") for i in range(n)]
        random.Random(0).shuffle(names)

        class Many:
            def __dir__(self) -> list[Name]:
                return names

        result = dir(Many())
        made = comparisons[0]

        assert result == sorted(names)
        assert n <= made <= 2 * n * math.log2(n), made


class TestBasesAreWalkedPerPath:
    """Prose: the default `__dir__` follows `__bases__`, not the MRO, merging a
    class once per inheritance path. A metaclass counts `__dict__` reads per
    class; an MRO walk would read each once."""

    def test_diamond_chain_merges_the_root_two_to_the_d_times(self) -> None:
        for depth in range(1, 11):
            lookups: dict[str, int] = {}
            meta = _counting_metaclass(lookups)
            cls = meta("Top", (), {"a": 1})
            for i in range(depth):
                left = meta(f"L{i}", (cls,), {})
                right = meta(f"R{i}", (cls,), {})
                cls = meta(f"J{i}", (left, right), {})
            assert len(cls.__mro__) == 3 * depth + 2
            lookups.clear()

            dir(cls())

            assert lookups["Top"] == 2**depth, (depth, lookups["Top"])

    def test_single_inheritance_merges_each_class_once(self) -> None:
        lookups: dict[str, int] = {}
        meta = _counting_metaclass(lookups)
        cls = meta("C0", (), {})
        for i in range(1, 50):
            cls = meta(f"C{i}", (cls,), {})
        lookups.clear()

        dir(cls())

        assert lookups == {f"C{i}": 1 for i in range(50)}


class TestWhatTheDefaultLists:
    """Rows: dir(obj) includes the instance `__dict__` (copied, not modified);
    dir(cls) omits metaclass attributes; `__getattr__` names are not listed."""

    def test_instance_names_are_listed_and_dict_untouched(self) -> None:
        class Base:
            shared = 1

        obj = Base()
        obj.own = 2  # type: ignore[attr-defined]
        before = dict(vars(obj))

        names = dir(obj)

        assert "own" in names and "shared" in names
        assert vars(obj) == before

    def test_class_dir_omits_metaclass_attributes(self) -> None:
        class Meta(type):
            def meta_method(cls) -> None:
                pass

        class WithMeta(metaclass=Meta):
            pass

        assert hasattr(WithMeta, "meta_method")
        assert "meta_method" not in dir(WithMeta)
        assert hasattr(int, "mro") and "mro" not in dir(int)

    def test_getattr_names_are_not_listed(self) -> None:
        class Lazy:
            def __getattr__(self, name: str) -> str:
                return name.upper()

        obj = Lazy()

        assert obj.anything == "ANYTHING"
        assert "anything" not in dir(obj)


class TestModulesAndLocals:
    """Rows: dir(module) and dir() with no argument sort a namespace's keys."""

    def test_module_dir_is_its_sorted_globals(self) -> None:
        assert dir(math) == sorted(math.__dict__)

    def test_module_level_dir_function_replaces_globals(self) -> None:
        module = types.ModuleType("custom")
        module.hidden = 1  # type: ignore[attr-defined]
        module.__dir__ = lambda: ["b", "a"]  # type: ignore[method-assign]

        assert dir(module) == ["a", "b"]

    def test_no_argument_lists_sorted_locals(self) -> None:
        def scope() -> list[str]:
            zed = 1
            alpha = 2
            del zed, alpha
            beta = 3
            return [str(beta), *dir()]

        assert scope() == ["3", "beta"]


class TestCheaperAlternatives:
    """Common Patterns: hasattr() does one lookup and never builds the dir()
    list; vars(obj) is the instance `__dict__` with no copy."""

    def test_hasattr_never_calls_dir(self) -> None:
        calls: list[int] = []

        class Config:
            debug = False

            def __dir__(self) -> list[str]:
                calls.append(1)
                return ["debug"]

        assert hasattr(Config(), "debug")
        assert calls == []

    def test_hasattr_makes_one_lookup(self) -> None:
        lookups: list[str] = []

        class Config:
            debug = False

            def __getattribute__(self, name: str) -> Any:
                lookups.append(name)
                return super().__getattribute__(name)

        cfg = Config()

        assert hasattr(cfg, "debug")
        assert lookups == ["debug"]

    def test_vars_is_the_instance_dict(self) -> None:
        class Point:
            def __init__(self) -> None:
                self.x = 1

        p = Point()

        assert vars(p) is p.__dict__


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

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "class Proxy:" in source)
        broken = block.replace('["alpha", "zeta"]', '["zeta", "alpha"]', 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
