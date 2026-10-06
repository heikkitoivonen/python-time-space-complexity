"""Tests for docs/stdlib/rlcompleter.md.

The page prices a completion as one scan on the `state == 0` call, kept and
indexed on every later state. Plain-name completion is settled by counting
the comparisons the scan makes; attribute completion by recording each
`dir()` call the class walk makes and, for the depth and attribute-count
terms, by timing ratios; laziness, reference-holding and what runs during
evaluation by observation.

Measurement scope:

* `global_matches()` is given a `str` subclass whose `__eq__` counts
  comparisons, and makes exactly one comparison per keyword, namespace name and
  `builtins` name, at 10 and 10,000 namespace names. Over 100,000 namespace
  names with no match it peaks under 20 KB of traced allocation. Its order is
  asserted as keywords, namespace, then `builtins`, with a namespace name
  hiding a builtin.
* `complete()` on a subclass that counts `global_matches()` and
  `attr_matches()` calls computes once over a whole state 0, 1, 2, ... cycle;
  clearing the namespace after state 0 leaves later states answering from the
  kept list. Whitespace-only text returns a tab, or `''` after
  `readline.insert_text('\\t')` on a recording stand-in for `readline`, without
  computing matches.
* `Completer(namespace)` keeps the same dictionary object; with no namespace,
  `namespace` is unset until the first completion and is then
  `__main__.__dict__`, a name added to `__main__` after construction is
  completed, and replacing the module's `__main__` reference between two
  completions moves the second to the new module's dictionary.
* `attr_matches()` and `get_class_members()` are observed through a recording
  `dir` placed in the module's globals: a diamond is walked as Diamond, Left,
  Base, object, Right, Base, object, and a module costs `dir()` of itself,
  `ModuleType` and `object`. A chain of classes returns as many names as the
  `dir()` of every class on it put together. Timing: `get_class_members()` on
  chains of 40, 160 and 640 classes under a 100-attribute root costs more
  than 6x per 4x of depth and more than 64x over the 16x span (linear would
  be 4x and 16x); `attr_matches()` on one object with 1,000, 4,000, 16,000 and
  64,000 attributes and no match costs under 10x per 4x step (quadratic
  would be 16x) and more than 16x over the whole 64x span.
* A property on the object being listed is asserted not called; one on the
  dotted prefix, and a recording `__getattr__` on it, run once per completion
  and not again on later states.
  A prefix that raises gives no completion. Callable matches end in `(`, or
  `()` without parameters, and attribute matches come back sorted.
* `import rlcompleter` in a child process replaces a completer set before it
  with a `Completer` bound method that completes names from `__main__`, and a
  child on a pseudo-terminal completes `math.sq` to `math.sqrt(` through
  readline with the page's Tab binding.
* Soft keywords are asserted completed on 3.11+ and not on 3.10.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `site` imports this module for the interactive interpreter is read
  from `register_readline()` in Lib/site.py, which runs as
  `sys.__interactivehook__` only at an interactive prompt.
* The 3.13+ suppression of warnings raised while computing matches is not on
  the page: it changes no bound and no documented behaviour.

* The cost of evaluating the dotted prefix, which is whatever the properties
  and `__getattr__` hooks on the way do; only that they run is asserted.
* Treating the typed text as short and each match's `getattr()` and
  `inspect.signature()` as O(1) is the page's cost model; long typed text and
  callables with many parameters are not varied.
* The O(log a) factor is read from `dir()` returning a sorted list; the
  timings assert growth well under quadratic, not the logarithm. The squared
  depth term is read from `ret = ret + get_class_members(base)` in
  Lib/rlcompleter.py, which copies the accumulated list at every level; the
  timing shows the growth, on single-inheritance chains only.
* The readline tests and the Tab-binding block need a `readline` module,
  which Windows builds lack. Their bindings are GNU readline's and libedit's;
  only libedit is available on the machines these tests were written on.
"""

from __future__ import annotations

import builtins
import keyword
import os
import pathlib
import re
import rlcompleter
import select
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

import __main__

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "rlcompleter.md"
EXPECTED_BLOCKS = 5
SETUP_BLOCK_MARKER = "readline.set_completer(completer.complete)"

# Not in __all__ or the stubs; the page documents it as the class walk.
get_class_members: Callable[[type], list[str]] = rlcompleter.get_class_members  # type: ignore[attr-defined]

needs_readline = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows builds have no readline module"
)


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def keywords_offered() -> list[str]:
    """The keyword list `global_matches()` walks on this version."""
    if sys.version_info >= (3, 11):
        return keyword.kwlist + keyword.softkwlist
    return list(keyword.kwlist)


def all_states(completer: rlcompleter.Completer, text: str) -> list[str]:
    """What readline collects: states 0, 1, 2, ... until `None`."""
    results: list[str] = []
    while (result := completer.complete(text, len(results))) is not None:
        results.append(result)
    return results


class CountingText(str):
    """Typed text that counts the comparisons made against it."""

    comparisons = 0

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


class CountingCompleter(rlcompleter.Completer):
    """A completer that counts how often the match list is computed."""

    def __init__(self, namespace: dict[str, Any] | None = None) -> None:
        super().__init__(namespace)
        self.computed = 0
        self.calls = 0

    def complete(self, text: str, state: int) -> str | None:
        self.calls += 1
        return super().complete(text, state)

    def global_matches(self, text: str) -> list[str]:
        self.computed += 1
        return super().global_matches(text)

    def attr_matches(self, text: str) -> list[str]:
        self.computed += 1
        return super().attr_matches(text)


def chain(depth: int, root_attributes: int = 0) -> type:
    """A single-inheritance chain `depth` classes deep under a root class."""
    klass: type = type("Root", (), {f"m{index}": 1 for index in range(root_attributes)})
    for index in range(depth - 1):
        klass = type(f"Level{index}", (klass,), {})
    return klass


class Base:
    only_on_base = 1


class Left(Base):
    pass


class Right(Base):
    pass


class Diamond(Left, Right):
    pass


@pytest.fixture
def recorded_dir(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Record every `dir()` call rlcompleter makes."""
    seen: list[object] = []

    def recording(obj: object) -> list[str]:
        seen.append(obj)
        return dir(obj)

    monkeypatch.setattr(rlcompleter, "dir", recording, raising=False)
    return seen


class TestCompleterHoldsTheNamespace:
    """`Completer(namespace=None)` | O(1) | O(1): a reference, not a copy;
    with no namespace, `__main__.__dict__` is read at each completion."""

    def test_the_namespace_is_the_same_object(self) -> None:
        namespace: dict[str, Any] = {"x": 1}
        assert rlcompleter.Completer(namespace).namespace is namespace  # type: ignore[attr-defined]

    def test_a_name_added_later_is_completed(self) -> None:
        namespace: dict[str, Any] = {}
        completer = rlcompleter.Completer(namespace)
        namespace["late_arrival"] = 1
        assert completer.complete("late", 0) == "late_arrival"

    def test_without_one_main_is_read_at_completion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        completer = rlcompleter.Completer()
        assert not hasattr(completer, "namespace")
        monkeypatch.setattr(__main__, "zq_added_after_construction", 1, raising=False)
        assert completer.complete("zq_added", 0) == "zq_added_after_construction"
        assert completer.namespace is __main__.__dict__  # type: ignore[attr-defined]
        other = types.ModuleType("__main__")
        other.zq_other = 1  # type: ignore[attr-defined]
        monkeypatch.setattr(rlcompleter, "__main__", other)
        assert completer.complete("zq_o", 0) == "zq_other"
        assert completer.namespace is other.__dict__  # type: ignore[attr-defined]

    def test_a_non_dict_namespace_raises(self) -> None:
        with pytest.raises(TypeError, match="dictionary"):
            rlcompleter.Completer({"a": 1}.items())  # type: ignore[arg-type]


class TestTheFirstStateDoesTheWork:
    """`complete(text, 0)` computes and keeps the list; `complete(text, state)`
    with `state > 0` | O(1) | O(1) indexes it. A recount on every state would
    make the computation count equal the call count."""

    @pytest.mark.parametrize("text", ["ap", "box.ap"])
    def test_one_computation_per_completion(self, text: str) -> None:
        box = types.SimpleNamespace(apple=1, apricot=2, apron=3)
        completer = CountingCompleter({"apple": 1, "apricot": 2, "apron": 3, "box": box})
        results = all_states(completer, text)
        assert len(results) == 3
        assert completer.calls == 4
        assert completer.computed == 1

    def test_later_states_answer_from_the_kept_list(self) -> None:
        namespace: dict[str, Any] = {"apple": 1, "apricot": 2}
        completer = rlcompleter.Completer(namespace)
        assert completer.complete("ap", 0) == "apple"
        namespace.clear()
        assert completer.complete("ap", 1) == "apricot"
        assert completer.complete("ap", 2) is None

    def test_blank_text_is_a_tab_without_readline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(rlcompleter, "_readline_available", False)
        completer = CountingCompleter({"x": 1})
        assert completer.complete("  ", 0) == "\t"
        assert completer.complete("  ", 1) is None
        assert completer.computed == 0

    def test_blank_text_inserts_a_tab_with_readline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inserted: list[str] = []
        fake = types.SimpleNamespace(insert_text=inserted.append, redisplay=lambda: None)
        monkeypatch.setattr(rlcompleter, "_readline_available", True)
        monkeypatch.setattr(rlcompleter, "readline", fake, raising=False)
        completer = CountingCompleter({"x": 1})
        assert completer.complete("", 0) == ""
        assert inserted == ["\t"]
        assert completer.computed == 0


class TestGlobalMatchesScansEachNameOnce:
    """`Completer.global_matches(text)` | O(n) | O(m): one comparison per
    keyword, namespace name and builtin, and only matches are kept."""

    @pytest.mark.parametrize("names", [10, 10_000])
    def test_one_comparison_per_name(self, names: int) -> None:
        namespace = {f"v{index}": index for index in range(names)}
        completer = rlcompleter.Completer(namespace)
        CountingText.comparisons = 0
        assert completer.global_matches(CountingText("zz")) == []
        expected = len(keywords_offered()) + names + len(builtins.__dict__)
        assert CountingText.comparisons == expected

    def test_no_matches_hold_nothing_for_the_namespace(self) -> None:
        completer = rlcompleter.Completer({f"v{index}": index for index in range(100_000)})
        completer.global_matches("zz")  # warm
        peak = peak_bytes(lambda: completer.global_matches("zz"))
        assert peak < 20_000, f"a 100,000-name scan with no match peaked at {peak} bytes"

    def test_keywords_then_namespace_then_builtins(self) -> None:
        completer = rlcompleter.Completer({"is_ready": 1})
        assert completer.global_matches("is") == ["is ", "is_ready", "isinstance(", "issubclass("]

    def test_a_namespace_name_hides_a_builtin(self) -> None:
        assert rlcompleter.Completer({"len": 5}).global_matches("len") == ["len"]

    def test_callables_get_a_parenthesis(self) -> None:
        completer = rlcompleter.Completer({"one": len, "none": lambda: None})
        assert completer.global_matches("on") == ["one("]
        assert completer.global_matches("non") == ["nonlocal ", "none()"]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="soft keywords arrive in 3.11")
    def test_soft_keywords_are_completed(self) -> None:
        assert rlcompleter.Completer({}).complete("matc", 0) == "match "

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 offers kwlist only")
    def test_soft_keywords_are_not_completed_on_3_10(self) -> None:
        assert rlcompleter.Completer({}).complete("matc", 0) is None


class TestAttributeCompletion:
    """`Completer.attr_matches(text)`: the prefix is evaluated, the last object
    is listed with `dir()` and its class walk, and its properties are not
    called."""

    class Node:
        calls: list[str]

        @property
        def child(self) -> TestAttributeCompletion.Node:
            self.calls.append("child")
            return TestAttributeCompletion.Node()

        def visit(self, other: object) -> object:
            return other

    @pytest.fixture
    def node(self) -> Any:
        self.Node.calls = []
        return self.Node()

    def test_a_property_on_the_listed_object_is_not_called(self, node: Any) -> None:
        completer = rlcompleter.Completer({"node": node})
        assert completer.complete("node.ch", 0) == "node.child"
        assert node.calls == []

    def test_a_property_on_the_prefix_runs_once_per_completion(self, node: Any) -> None:
        completer = rlcompleter.Completer({"node": node})
        assert all_states(completer, "node.child.vi") == ["node.child.visit("]
        assert node.calls == ["child"]
        all_states(completer, "node.child.vi")
        assert node.calls == ["child", "child"]

    def test_a_getattr_hook_on_the_prefix_runs_once_per_completion(self) -> None:
        looked_up: list[str] = []

        class Dynamic:
            def __getattr__(self, name: str) -> types.SimpleNamespace:
                looked_up.append(name)
                return types.SimpleNamespace(target=1)

        completer = rlcompleter.Completer({"dyn": Dynamic()})
        assert all_states(completer, "dyn.inner.tar") == ["dyn.inner.target"]
        assert looked_up == ["inner"]
        all_states(completer, "dyn.inner.tar")
        assert looked_up == ["inner", "inner"]

    def test_a_prefix_that_raises_completes_nothing(self) -> None:
        completer = rlcompleter.Completer({})
        assert completer.attr_matches("missing.attr") == []
        assert completer.complete("missing.attr", 0) is None

    def test_matches_are_sorted(self) -> None:
        box = types.SimpleNamespace(zeta=1, alpha=2, mid=3)
        completer = rlcompleter.Completer({"box": box})
        assert completer.attr_matches("box.") == ["box.alpha", "box.mid", "box.zeta"]

    def test_a_module_walks_two_classes(self, recorded_dir: list[object]) -> None:
        module = types.ModuleType("probe")
        module.value = 1  # type: ignore[attr-defined]
        rlcompleter.Completer({"probe": module}).attr_matches("probe.va")
        assert recorded_dir == [module, types.ModuleType, object]


class TestTheClassWalk:
    """`get_class_members(klass)` | O(d·a·(d + log a)) | O(d·a): `dir()` of
    every class reached through `__bases__`, once per path, repeats kept."""

    def test_a_shared_base_is_walked_once_per_path(self, recorded_dir: list[object]) -> None:
        names = get_class_members(Diamond)
        assert recorded_dir == [Diamond, Left, Base, object, Right, Base, object]
        assert names.count("only_on_base") == 5

    def test_attr_matches_walks_the_instance_and_its_classes(
        self, recorded_dir: list[object]
    ) -> None:
        instance = Diamond()
        rlcompleter.Completer({"d": instance}).attr_matches("d.only")
        assert recorded_dir == [instance, Diamond, Left, Base, object, Right, Base, object]

    def test_the_result_keeps_every_class_s_names(self) -> None:
        klass = chain(20, root_attributes=50)
        names = get_class_members(klass)
        assert len(names) == sum(len(dir(c)) for c in klass.__mro__)
        assert names.count("m0") == 20

    @pytest.mark.timing
    def test_depth_costs_its_square(self) -> None:
        depths = (40, 160, 640)
        chains = [chain(depth, root_attributes=100) for depth in depths]
        costs = [best_ns(lambda k=k: get_class_members(k)) for k in chains]
        steps = [later / earlier for earlier, later in pairwise(costs)]
        span = costs[-1] / costs[0]
        assert all(step > 6 for step in steps), f"depths {depths}: {costs} ns, steps {steps}"
        assert span > 64, f"16x the depth cost x{span:.1f}; linear would be x16"

    @pytest.mark.timing
    def test_attribute_count_costs_well_under_its_square(self) -> None:
        costs = []
        sizes = (1_000, 4_000, 16_000, 64_000)
        for size in sizes:
            box = types.SimpleNamespace(**{f"a{index}": index for index in range(size)})
            completer = rlcompleter.Completer({"box": box})
            costs.append(best_ns(lambda c=completer: c.attr_matches("box.zz")))
        steps = [later / earlier for earlier, later in pairwise(costs)]
        span = costs[-1] / costs[0]
        assert all(step < 10 for step in steps), f"sizes {sizes}: {costs} ns, steps {steps}"
        assert span > 16, f"64x the attributes cost only x{span:.1f}"


@needs_readline
class TestImportAndReadline:
    """`import rlcompleter` installs its completer; the page's setup completes
    through readline."""

    def test_import_replaces_the_completer(self) -> None:
        child = textwrap.dedent(
            """
            import sys, readline
            assert 'rlcompleter' not in sys.modules
            mine = lambda text, state: None
            readline.set_completer(mine)
            zq_main_name = 1
            import rlcompleter
            installed = readline.get_completer()
            assert installed is not mine
            assert isinstance(installed.__self__, rlcompleter.Completer)
            assert installed('zq_main', 0) == 'zq_main_name'
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", child],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    def test_tab_completes_an_attribute_on_a_terminal(self) -> None:
        setup = (
            "import math, readline, rlcompleter\n"
            "if 'libedit' in readline.__doc__:\n"
            "    readline.parse_and_bind('bind ^I rl_complete')\n"
            "else:\n"
            "    readline.parse_and_bind('tab: complete')\n"
        )
        assert _typed_line(setup, [b"math.sq\t", b"\r"]) == "'math.sqrt('"


def _typed_line(setup: str, keys: list[bytes]) -> str:
    """Read one line with `input()` on a pseudo-terminal, typing `keys`; return its repr."""
    child = "\n".join(
        [setup, "print('READY', flush=True)", "line = input('> ')", "print('RESULT', repr(line))"]
    )
    master, slave = os.openpty()
    process = subprocess.Popen(
        [sys.executable, "-c", child],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        env={**os.environ, "TERM": "xterm", "INPUTRC": os.devnull, "EDITRC": os.devnull},
    )
    os.close(slave)
    output = b""

    def read_until(pattern: bytes, seconds: float = 60) -> bool:
        nonlocal output
        deadline = time.monotonic() + seconds
        while not re.search(pattern, output) and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
        return re.search(pattern, output) is not None

    try:
        assert read_until(rb"READY"), output
        # Keys typed before readline shows its prompt meet the terminal's own
        # line editing, where Tab is only a character.
        assert read_until(rb"> "), output
        for key in keys:
            os.write(master, key)
            time.sleep(0.2)
        read_until(rb"RESULT [^\n]*\n")
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    match = re.search(r"RESULT (.*)", output.decode(errors="replace"))
    assert match, f"the child printed no result:\n{output!r}"
    return match.group(1).strip()


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
    """Each block runs in its own subprocess and asserts its own result. The
    Tab-binding block imports `readline`, so it is skipped where Windows
    builds have none."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS
        assert sum(SETUP_BLOCK_MARKER in source for _, source in _blocks()) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if sys.platform == "win32" and SETUP_BLOCK_MARKER in source:
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS - (sys.platform == "win32")
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert calls == ['child']" in s)
        mutated = source.replace("assert calls == ['child']", "assert calls == []", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
