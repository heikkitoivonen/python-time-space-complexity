"""Tests for docs/builtins/sentinel.md.

Every row on the page acts on one fixed-size object, so the claims are
settled by observation rather than timing: identity for what construction,
`repr()`, copying and pickling hand back, `sys.getsizeof` for the object not
growing with its name, a counting `__eq__` for equality, and a counting
metaclass `__hash__` for the cost of building a union.

Measurement scope:

* `sentinel(name, repr=...)` is asserted to keep `name` and `repr` as the
  same objects, and `sys.getsizeof` to be equal for a 1-character and a
  100,000-character name. A non-`str` name or `repr` raises `TypeError`.
  `__module__` is asserted to be the calling module's name: this module's,
  a `fake` module's when the call runs in an `exec()` whose globals say so,
  and the defining module's from inside a function.
* `repr(s)` and `str(s)` are asserted to be the stored string itself, with
  and without a `repr` argument. Two sentinels with one name are asserted
  distinct and unequal; `s == other` is asserted to call the other operand's
  `__eq__` exactly once and return its answer. `hash(s)` is asserted equal to
  `object.__hash__(s)`, and `bool(s)` `True`.
* `__name__` is asserted read-only and `__module__` writable; pointing
  `__module__` at a module without the name makes pickling raise
  `PicklingError`.
* `copy.copy()` and `copy.deepcopy()` are asserted to return `s` itself, and
  a pickle round trip to return it for a module-level sentinel and for a
  class-level one named by its qualified name; one that no module holds under
  its name raises `PicklingError`. The pickle is asserted to carry the module
  and the name, and, made in one interpreter, to load in a fresh one that has
  not imported the module, importing it. A pickled `object()` is asserted to
  load as a different object.
* `s | U` and `U | s` over unions of u = 10 and 1,000 classes whose
  metaclass counts `__hash__`: the count is the same for both orders, at
  least u, and exactly 100 times larger for the 100 times larger union.
  `s | s` is asserted to be `s`, and `typing.get_args(int | s)` to be
  `(int, s)`.
* Subclassing `sentinel` is asserted to raise `TypeError`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(k) pickling bound is read from Modules/_pickle.c's `save_global`,
  which writes the module and qualified name and walks the dotted name on
  load; the tests check what is written, not how its cost grows with k.
* Hashing and comparing union members is treated as O(1); a member whose
  `__hash__` is costly adds that cost u times over, and members whose hashes
  collide cost what the set's probing does. Unhashable members, which the union
  builder compares in a list instead, are not varied.
* The type is new in Python 3.15, so this file skips on earlier versions.
"""

from __future__ import annotations

import builtins
import copy
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import types
import typing
from typing import Any

import pytest

if sys.version_info < (3, 15):
    pytest.skip("version: sentinel is new in Python 3.15", allow_module_level=True)

sentinel: Any = vars(builtins)["sentinel"]

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "sentinel.md"
EXPECTED_BLOCKS = 3

MODULE_LEVEL = sentinel("MODULE_LEVEL")


class Holder:
    INNER = sentinel("Holder.INNER")


class CountingMeta(type):
    """A metaclass whose instances count every hash taken of them."""

    hashes = 0

    def __hash__(cls) -> int:
        CountingMeta.hashes += 1
        return id(cls) >> 4

    def __eq__(cls, other: object) -> bool:
        return cls is other


def union_of(size: int) -> Any:
    classes = tuple(CountingMeta(f"Member{i}", (), {}) for i in range(size))
    return typing.Union[classes]  # noqa: UP007 - a union of runtime classes


class TestConstructionKeepsWhatItIsGiven:
    """`sentinel(name, /, *, repr=None)` | O(1) | O(1): the object holds
    `name` and `repr` themselves, so its size does not follow the name's."""

    def test_the_name_and_repr_are_kept_not_copied(self) -> None:
        name = "".join(["NA", "ME"])
        text = "".join(["<", "name", ">"])
        made = sentinel(name, repr=text)

        assert made.__name__ is name
        assert repr(made) is text

    def test_the_object_does_not_grow_with_its_name(self) -> None:
        short = sentinel("x")
        long = sentinel("x" * 100_000)

        assert sys.getsizeof(short) == sys.getsizeof(long)

    def test_the_arguments_must_be_strings(self) -> None:
        with pytest.raises(TypeError, match="must be str"):
            sentinel(1)
        with pytest.raises(TypeError, match="str or None"):
            sentinel("x", repr=1)

    def test_the_module_is_the_caller_s(self) -> None:
        assert MODULE_LEVEL.__module__ == __name__
        namespace: dict[str, Any] = {"__name__": "fake", "sentinel": sentinel}
        exec("made = sentinel('made')", namespace)
        assert namespace["made"].__module__ == "fake"

    def test_inside_a_function_it_is_the_defining_module(self) -> None:
        def make() -> Any:
            return sentinel("inner")

        assert make().__module__ == __name__


class TestReprReturnsTheStoredString:
    """`repr(s)`, `str(s)` | O(1) | O(1): the stored string comes back
    itself, so `repr()` builds no string."""

    def test_repr_is_the_name_without_a_repr_argument(self) -> None:
        name = "".join(["MIS", "SING"])
        made = sentinel(name)

        assert repr(made) is name
        assert str(made) is name

    def test_repr_is_the_repr_argument_when_given(self) -> None:
        text = "".join(["<", "missing", ">"])
        made = sentinel("MISSING", repr=text)

        assert repr(made) is text
        assert str(made) is text


class TestIdentityAndEquality:
    """`s is MISSING`, `s == other`, `hash(s)`, `bool(s)` | O(1): every
    call makes a new object, equal only to itself unless the other operand's
    `__eq__` answers."""

    def test_two_calls_make_two_sentinels(self) -> None:
        first, second = sentinel("SAME"), sentinel("SAME")

        assert first is not second
        assert first != second
        assert first == first

    def test_the_other_operand_s_eq_can_answer(self) -> None:
        calls = 0

        class Agreeable:
            def __eq__(self, other: object) -> bool:
                nonlocal calls
                calls += 1
                return True

            __hash__ = object.__hash__

        assert MODULE_LEVEL == Agreeable()
        assert calls == 1

    def test_hash_is_the_identity_hash(self) -> None:
        assert hash(MODULE_LEVEL) == object.__hash__(MODULE_LEVEL)
        assert {MODULE_LEVEL: 1}[MODULE_LEVEL] == 1

    def test_it_is_always_true(self) -> None:
        assert bool(sentinel("FALSE")) is True


class TestAttributes:
    """`s.__name__`, `s.__module__` | O(1): `__name__` is read-only and
    `__module__` can be reassigned, which changes where pickling looks."""

    def test_name_is_read_only(self) -> None:
        made = sentinel("FIXED")
        with pytest.raises(AttributeError):
            made.__name__ = "OTHER"

    def test_module_can_be_reassigned_and_pickling_follows_it(self) -> None:
        made = sentinel("MODULE_LEVEL")
        made.__module__ = "types"
        assert made.__module__ == "types"
        assert not hasattr(types, "MODULE_LEVEL")

        with pytest.raises(pickle.PicklingError):
            pickle.dumps(made)


class TestCopyAndPickleReturnTheSameObject:
    """`copy.copy(s)`, `copy.deepcopy(s)` | O(1), and `pickle.dumps(s)`,
    `pickle.loads(data)` | O(k): copies are `s` itself, and a pickle is a
    reference by module and name."""

    def test_copies_are_the_object_itself(self) -> None:
        assert copy.copy(MODULE_LEVEL) is MODULE_LEVEL
        assert copy.deepcopy(MODULE_LEVEL) is MODULE_LEVEL
        assert copy.deepcopy([MODULE_LEVEL])[0] is MODULE_LEVEL

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_a_module_level_sentinel_round_trips(self, protocol: int) -> None:
        assert pickle.loads(pickle.dumps(MODULE_LEVEL, protocol)) is MODULE_LEVEL

    def test_a_class_level_sentinel_round_trips_under_its_qualified_name(self) -> None:
        assert pickle.loads(pickle.dumps(Holder.INNER)) is Holder.INNER

    def test_a_sentinel_no_module_holds_cannot_be_pickled(self) -> None:
        with pytest.raises(pickle.PicklingError, match="LOCAL"):
            pickle.dumps(sentinel("LOCAL"))

    def test_the_pickle_carries_the_module_and_name_only(self) -> None:
        data = pickle.dumps(MODULE_LEVEL)

        assert __name__.encode() in data
        assert b"MODULE_LEVEL" in data
        assert len(data) < len(__name__) + len("MODULE_LEVEL") + 32

    def test_loading_imports_the_module(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "marks.py").write_text("DONE = sentinel('DONE')\n", encoding="utf-8")
        dump = "import pickle, sys, marks\nsys.stdout.buffer.write(pickle.dumps(marks.DONE))\n"
        load = (
            "import pickle, sys\n"
            "assert 'marks' not in sys.modules\n"
            "loaded = pickle.loads(sys.stdin.buffer.read())\n"
            "assert loaded is sys.modules['marks'].DONE\n"
        )
        data = subprocess.run(
            [sys.executable, "-c", dump],
            cwd=tmp_path,
            capture_output=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        ).stdout
        result = subprocess.run(
            [sys.executable, "-c", load],
            cwd=tmp_path,
            input=data,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode()

    def test_a_pickled_object_marker_is_a_different_object(self) -> None:
        marker = object()
        assert pickle.loads(pickle.dumps(marker)) is not marker


class TestUnionHashesEachMember:
    """`s | t`, `t | s` | O(u): building the union hashes the members to
    drop duplicates. A counting metaclass shows the work follows u, the
    same in either operand order."""

    @staticmethod
    def hashes_for(size: int, *, sentinel_first: bool) -> int:
        members = union_of(size)
        mark = sentinel("MARK")
        CountingMeta.hashes = 0
        result = mark | members if sentinel_first else members | mark
        counted = CountingMeta.hashes
        assert len(typing.get_args(result)) == size + 1
        return counted

    @pytest.mark.parametrize("sentinel_first", [True, False])
    def test_the_hashes_follow_the_union_s_size(self, sentinel_first: bool) -> None:
        small = self.hashes_for(10, sentinel_first=sentinel_first)
        large = self.hashes_for(1_000, sentinel_first=sentinel_first)

        assert small >= 10
        assert large == small * 100, f"10 members took {small} hashes, 1,000 took {large}"

    def test_both_orders_cost_the_same(self) -> None:
        assert self.hashes_for(100, sentinel_first=True) == self.hashes_for(
            100, sentinel_first=False
        )

    def test_a_sentinel_or_itself_is_itself(self) -> None:
        assert (MODULE_LEVEL | MODULE_LEVEL) is MODULE_LEVEL

    def test_it_can_appear_in_an_annotation(self) -> None:
        assert typing.get_args(int | MODULE_LEVEL) == (int, MODULE_LEVEL)


class TestTheTypeIsClosed:
    """`type(s)`, `isinstance(x, sentinel)` | O(1): the type cannot be
    subclassed."""

    def test_subclassing_raises(self) -> None:
        with pytest.raises(TypeError, match="not an acceptable base type"):
            type("Special", (sentinel,), {})

    def test_the_type_and_isinstance(self) -> None:
        assert type(MODULE_LEVEL) is sentinel
        assert isinstance(MODULE_LEVEL, sentinel)
        assert not isinstance(object(), sentinel)


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
    """Each block runs in its own subprocess as a script, so a module-level
    sentinel pickles from `__main__`, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "MISSING | MISSING is MISSING" in s)
        mutated = source.replace("MISSING | MISSING is MISSING", "MISSING | MISSING is int", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
