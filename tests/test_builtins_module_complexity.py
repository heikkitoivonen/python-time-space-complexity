"""Tests for docs/stdlib/builtins.md.

The page prices the `builtins` module as a namespace: reading, writing and
deleting a name is one dict operation, an unqualified name falls back to it
after the module's globals, and inspecting it either hands back the live dict
or copies and sorts its names. Identity and late binding are settled by
observation, which needs no tolerance; only the claim that a lookup ignores
the size of the namespaces it searches needs a stopwatch. The per-builtin
pages under docs/builtins/ have their own tests in test_builtin_complexity.py
and test_builtin_claims.py; nothing here re-measures `len`, `getattr` or
`dir` on other objects.

Measurement scope:

* An unqualified name is looked up by a function compiled into a globals dict
  whose `__builtins__` is a custom dict. 20,000 lookups cost under 5x as much
  with 1,000,000 extra globals, and again with 1,000,000 extra builtins, as
  with 10 of each. Counting the standard names, a scan would cost over
  5,000x as much in either case. Measured on 3.10 and
  3.14, where both ratios were under 2.
* Shadowing and fall-through are observed: a module global of the same name
  is found before the built-in, and deleting it lets the built-in through; a
  closure's enclosing binding is not reached by an assignment to `builtins`,
  and code run by `exec()` with its own `__builtins__` dict is not either.
* Assigning to `builtins` reaches a function defined, and called 2,000 times
  so that 3.11+ has specialised its lookup, before the assignment; a value
  bound as a default argument at definition does not see it. Deleting a
  name raises `NameError` from a function that does not bind it, and not from
  one whose module does. The function lives in a module object created and
  run before the assignment, standing in for a module imported earlier.
* `hasattr` is `False` and `getattr` returns the default for a missing name.
* `vars(builtins)` and `builtins.__dict__` are the same object on every call;
  `dir(builtins)` is a new list each call, sorted, holding exactly the
  namespace's keys, so its length is n. Iterating `vars(builtins).items()`
  yields n pairs.
* `__builtins__` is observed in a subprocess: the module itself in `__main__`
  and `builtins.__dict__` in a Python source module that `__main__`
  imports.
* `site` is observed in two subprocesses: with `-S` none of `help`, `exit`,
  `quit`, `copyright`, `credits` and `license` is in `builtins`, without it
  all six are. `gettext.install()` is observed to add `_`.
* `mock.patch("builtins.open")` is observed to restore the original on a
  normal exit and on an exception.
* Every fenced Python block runs in its own subprocess, since two of them
  assign to `builtins`, and a mutated assertion in one of them is asserted to
  fail.

Not settled here:

* The O(n log n) time of `dir(builtins)` is read from Python/bltinmodule.c
  (`builtin_dir`, which sorts the list) and Objects/moduleobject.c
  (`module_dir`, which copies the dict's keys); the namespace cannot be grown
  far enough to time it without patching thousands of names into every
  module's builtins.
* The O(1) bounds of `builtins.name`, `getattr`, `hasattr`, `setattr` and
  `delattr` are read from Objects/moduleobject.c: the `builtins` module
  defines no `__getattr__`, so after the cached lookup on its type each is
  a fixed number of operations on its dict (a miss also looks for
  `__getattr__` there). They are not timed; the tests above observe their
  results only.
* `setattr` adding a name not already present is O(1) amortized because it is
  a dict insert, which can resize; only replacing an existing name is
  measured. Dict watchers that the experimental tier-2 optimizer installs on
  the builtins dict are not exercised: default builds do not run it.
* "Every module in the interpreter": each subinterpreter has its own
  `builtins` module, and that is read from the CPython docs, not run here.
* Name hashing and comparison are a cost-model assumption, held at short
  names; lookups through a custom `__builtins__` mapping that is not a dict
  are not varied.
"""

from __future__ import annotations

import builtins
import gettext
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import types
from collections.abc import Callable, Iterator
from typing import Any
from unittest import mock

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "builtins.md"
EXPECTED_BLOCKS = 4

PROBE = "_builtins_module_complexity_probe"
SITE_NAMES = ("help", "exit", "quit", "copyright", "credits", "license")


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


def module_from(source: str, name: str = "builtins_probe_module") -> types.ModuleType:
    """A module object whose code has already run, as an imported module's has."""
    module = types.ModuleType(name)
    exec(textwrap.dedent(source), vars(module))
    return module


@pytest.fixture
def probe_name() -> Iterator[str]:
    """A name that is not a built-in, removed from `builtins` afterwards."""
    assert not hasattr(builtins, PROBE)
    yield PROBE
    if hasattr(builtins, PROBE):
        delattr(builtins, PROBE)


class TestLookupIgnoresNamespaceSize:
    """`Unqualified name lookup` | O(1) | O(1) | neither namespace's size
    matters.

    A lookup that scanned either namespace would cost over 5,000x more with a
    million extra names, counting the standard ones; a hash lookup costs about
    the same.
    """

    SOURCE = "def probe():\n    for _ in range(20_000):\n        len\n"

    @classmethod
    def probe_with(cls, extra_globals: int, extra_builtins: int) -> Callable[[], Any]:
        custom_builtins: dict[str, Any] = {f"b{index}": index for index in range(extra_builtins)}
        custom_builtins.update(vars(builtins))
        namespace: dict[str, Any] = {f"g{index}": index for index in range(extra_globals)}
        namespace["__builtins__"] = custom_builtins
        exec(cls.SOURCE, namespace)
        probe = namespace["probe"]
        probe()
        return probe

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("extra_globals", "extra_builtins"),
        [(1_000_000, 10), (10, 1_000_000)],
        ids=["globals", "builtins"],
    )
    def test_a_million_extra_names_cost_about_the_same(
        self, extra_globals: int, extra_builtins: int
    ) -> None:
        small_ns = best_ns(self.probe_with(10, 10))
        large_ns = best_ns(self.probe_with(extra_globals, extra_builtins))

        ratio = large_ns / small_ns
        assert ratio < 5, (
            f"20,000 lookups took {large_ns:.0f}ns with a million extra names against "
            f"{small_ns:.0f}ns with ten (x{ratio:.1f}); a scan would cost over x5,000"
        )


class TestGlobalsShadowBuiltins:
    """A module global of the same name is found first; deleting it lets the
    lookup fall through to `builtins` again."""

    def test_a_module_global_is_found_before_the_built_in(self) -> None:
        module = module_from(
            """
            def size(obj):
                return len(obj)
            """
        )
        assert module.size("abc") == 3

        module.__dict__["len"] = lambda obj: -1
        assert module.size("abc") == -1
        assert builtins.len("abc") == 3

        del module.__dict__["len"]
        assert module.size("abc") == 3


class TestAssignmentIsLateBound:
    """`setattr(builtins, name, value)` reaches every module where the name is not
    shadowed, at its next lookup; `delattr` then raises `NameError`.

    The function is called 2,000 times first, so that on 3.11+ the lookup has
    been specialised before the assignment.
    """

    def test_an_assignment_reaches_a_module_built_before_it(self, probe_name: str) -> None:
        setattr(builtins, probe_name, "before")
        module = module_from(
            f"""
            def read():
                return {probe_name}

            def read_bound(value={probe_name}):
                return value
            """
        )
        for _ in range(2_000):
            assert module.read() == "before"

        setattr(builtins, probe_name, "after")

        assert module.read() == "after"
        assert module.read_bound() == "before"

    def test_replacing_a_real_built_in_reaches_existing_code(self) -> None:
        module = module_from(
            """
            def size(obj):
                return len(obj)
            """
        )
        for _ in range(2_000):
            module.size("abc")

        original = builtins.len
        builtins.len = lambda obj: 42
        try:
            assert module.size("abc") == 42
        finally:
            builtins.len = original
        assert module.size("abc") == 3

    def test_deleting_a_name_raises_name_error_where_it_is_not_bound(self, probe_name: str) -> None:
        setattr(builtins, probe_name, 1)
        unbound = module_from(f"def read():\n    return {probe_name}\n", "unbound")
        bound = module_from(f"{probe_name} = 2\ndef read():\n    return {probe_name}\n", "bound")
        assert unbound.read() == 1

        delattr(builtins, probe_name)

        with pytest.raises(NameError, match=probe_name):
            unbound.read()
        assert bound.read() == 2

    def test_an_enclosing_binding_is_not_reached(self, probe_name: str) -> None:
        setattr(builtins, probe_name, "builtin")
        module = module_from(
            f"""
            def outer():
                {probe_name} = "enclosing"
                def inner():
                    return {probe_name}
                return inner
            """
        )
        inner = module.outer()

        setattr(builtins, probe_name, "after")
        assert inner() == "enclosing"
        delattr(builtins, probe_name)
        assert inner() == "enclosing"

    def test_exec_with_its_own_builtins_does_not_see_it(self, probe_name: str) -> None:
        namespace: dict[str, Any] = {"__builtins__": {probe_name: "own"}}
        exec(f"def read():\n    return {probe_name}\n", namespace)

        setattr(builtins, probe_name, "shared")
        assert namespace["read"]() == "own"

    def test_a_miss_is_false_or_the_default_not_an_error(self) -> None:
        assert hasattr(builtins, "len")
        assert not hasattr(builtins, PROBE)
        assert getattr(builtins, PROBE, "default") == "default"


class TestInspectingTheNamespace:
    """`vars(builtins)` | O(1) | O(1) | the live dict; `dir(builtins)` |
    O(n log n) | O(n) | a new sorted list; iterating the items is O(n)."""

    def test_vars_is_the_module_dict_itself(self) -> None:
        assert vars(builtins) is builtins.__dict__
        assert vars(builtins) is vars(builtins)

    def test_vars_is_live(self, probe_name: str) -> None:
        namespace = vars(builtins)
        setattr(builtins, probe_name, 1)
        assert namespace[probe_name] == 1

    def test_dir_is_a_new_sorted_list_of_every_name(self) -> None:
        first = dir(builtins)

        assert first is not dir(builtins)
        assert first == sorted(first)
        assert first == sorted(vars(builtins))

    def test_iterating_the_items_visits_each_name_once(self) -> None:
        names = [name for name, _ in vars(builtins).items()]
        assert len(names) == len(set(names)) == len(dir(builtins))


def _run(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDunderBuiltins:
    """`__builtins__` is the module in `__main__` and its dict in an imported
    module."""

    def test_it_is_the_module_in_main_and_the_dict_elsewhere(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "imported.py").write_text(
            "import builtins\nIS_DICT = __builtins__ is builtins.__dict__\n", encoding="utf-8"
        )
        (tmp_path / "main.py").write_text(
            "import builtins\nimport imported\n"
            "assert __builtins__ is builtins\n"
            "assert imported.IS_DICT\n",
            encoding="utf-8",
        )

        result = _run(["main.py"], tmp_path)

        assert result.returncode == 0, result.stderr


class TestWhatAddsNames:
    """`site` adds six names at startup and `gettext.install()` adds `_`."""

    PROBE_SITE = (
        f"import builtins\nprint(sorted(n for n in {SITE_NAMES!r} if hasattr(builtins, n)))\n"
    )

    def test_site_adds_its_names_and_dash_s_skips_them(self, tmp_path: pathlib.Path) -> None:
        with_site = _run(["-c", self.PROBE_SITE], tmp_path)
        without_site = _run(["-S", "-c", self.PROBE_SITE], tmp_path)

        assert with_site.returncode == 0 and without_site.returncode == 0
        assert with_site.stdout.strip() == repr(sorted(SITE_NAMES))
        assert without_site.stdout.strip() == "[]"

    def test_gettext_install_adds_underscore(self) -> None:
        missing = object()
        previous = builtins.__dict__.get("_", missing)
        try:
            gettext.install("builtins_module_complexity_no_such_domain")
            underscore = builtins.__dict__["_"]
            assert underscore("text") == "text"
        finally:
            if previous is missing:
                builtins.__dict__.pop("_", None)
            else:
                builtins.__dict__["_"] = previous


class TestMockPatchRestores:
    """`mock.patch("builtins.name")` makes the assignment and undoes it when the
    block exits, even on an exception."""

    def test_a_normal_exit_restores_the_original(self) -> None:
        original = builtins.open
        with mock.patch("builtins.open", mock.mock_open(read_data="x")):
            assert builtins.open is not original
        assert builtins.open is original

    def test_an_exception_restores_it_too(self) -> None:
        original = builtins.open
        with pytest.raises(RuntimeError), mock.patch("builtins.open"):
            raise RuntimeError
        assert builtins.open is original


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
    return _run([str(script)], cwd)


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so a block that assigns to
    `builtins` cannot leak into another, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if 'size("abc") == -1' in s)
        mutated = source.replace('size("abc") == -1', 'size("abc") == 3', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
