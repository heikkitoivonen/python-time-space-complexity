"""Tests for docs/builtins/breakpoint.md.

breakpoint() is builtin_breakpoint in Python/bltinmodule.c: it looks up
`sys.breakpointhook`, raises the `builtins.breakpoint` audit event, and calls
the hook with its own arguments. The default hook, sys_breakpointhook in
Python/sysmodule.c, reads `PYTHONBREAKPOINT` on every call, returns at once for
`0`, otherwise imports the part before the last dot (`builtins` when there is
none) and calls the attribute after it. An ImportError from the import or an
AttributeError from the lookup becomes a warning; any other exception
propagates. The routing claims are settled by observation - a recording hook,
a counting `__import__`, a patched `pdb.set_trace` - and nothing here needs a
stopwatch. The O(c + d) of entering pdb is settled on the pdb page's tests;
here only its route and its inputs are observed.

Anything that may enter pdb, install an audit hook or count imports runs in a
subprocess with an empty `HOME` and working directory, so no `.pdbrc` is read,
no session can wait for input and no tracing reaches the test process. The
in-process tests patch `sys.breakpointhook`, `pdb.set_trace` and the
environment through `monkeypatch`, which restores them.

Measurement scope:

* `breakpoint(*args, **kws)` calls a replaced hook once with exactly those
  arguments and returns its result, and still calls it when
  `PYTHONBREAKPOINT` is `0`. `sys.__breakpointhook__` is the default hook,
  and breakpoint() reaches it again once the replacement is undone.
* The `builtins.breakpoint` audit event is raised once per call, before the
  hook runs, with the hook as its only argument.
* `PYTHONBREAKPOINT=0` returns `None` and makes no `__import__` call over 100
  calls at stack depths 1 and 100, and leaves `sys.gettrace()` unset.
  `PYTHONBREAKPOINT=json.dumps` makes one `__import__` call per breakpoint();
  `os.path.join`, a two-part module path, and `int`, a builtin, return the
  callable's result. Changing `os.environ` between two calls changes the
  hook the second call uses.
* A missing module, a missing attribute and a leading dot each raise one
  `RuntimeWarning` naming the variable's value and return `None`, and so
  does a module that raises `ImportError` while importing; one that raises
  `ValueError` makes breakpoint() raise it.
* Unset and empty `PYTHONBREAKPOINT` both call `pdb.set_trace()` once with
  the keyword arguments given; a positional argument to the real
  `pdb.set_trace()` raises `TypeError`.
* Entered through breakpoint(), pdb's `where` lists 90 more frames at
  recursion depth 100 than at depth 10, and `linecache.checkcache()` runs
  once with no file name, which checks every cached file. That shows the d
  frames and c files reach `pdb.set_trace()`; that it hooks each frame, and
  what one check costs, is settled in tests/test_pdb_complexity.py and
  tests/test_bdb_complexity.py. Two breakpoint() calls
  build two `Pdb` objects before 3.14 and one from 3.14, on the
  `'monitoring'` backend.
* With `PYTHONBREAKPOINT=0`, `python -E` and `python -I` call
  `pdb.set_trace()` and a plain run does not.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* What the default hook costs once pdb has stopped - running between stops
  and building a `Pdb` - is priced on docs/stdlib/pdb.md and settled in
  tests/test_pdb_complexity.py; this file checks only that breakpoint()
  reaches those paths.
* Importing the named module the first time costs whatever that import does;
  the page leaves it out as a one-time cost, and the tests import only
  modules already loaded or cheap to load.
* The size of a dotted name is priced at O(1); names were not varied in
  length.
* The O(1) bounds of breakpoint() itself and of `PYTHONBREAKPOINT=0` follow
  from the source above: one hook lookup, one audit call, one `getenv()` and
  no loop. No allocation was measured, and the `0` path was observed to make
  no import and leave tracing off, not timed against stack depth.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import warnings
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "breakpoint.md"
EXPECTED_BLOCKS = 4


def _clean_env(home: pathlib.Path, **extra: str) -> dict[str, str]:
    """The test's environment without `PYTHONBREAKPOINT`, with `HOME` at `home`."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONBREAKPOINT"}
    env["HOME"] = str(home)
    env.update(extra)
    return env


def run_script(
    source: str,
    cwd: pathlib.Path,
    *,
    flags: tuple[str, ...] = (),
    stdin: str | None = None,
    **env: str,
) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter, in `cwd`, with an empty `HOME`."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, *flags, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        env=_clean_env(cwd, **env),
        check=False,
    )


def last_json(result: subprocess.CompletedProcess[str]) -> Any:
    """The JSON a script printed on its last line, or a failure with its stderr."""
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.fixture
def default_hook(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """The default hook installed and `PYTHONBREAKPOINT` unset, all restored after.

    pytest replaces `pdb.set_trace` with its own debugger in this process, so
    a call that reached it would stop the run; it fails the test instead.
    """
    import pdb

    def refuse(*args: object, **kws: object) -> None:
        raise AssertionError("breakpoint() reached pdb.set_trace")

    monkeypatch.setattr(pdb, "set_trace", refuse)
    monkeypatch.setattr(sys, "breakpointhook", sys.__breakpointhook__)
    monkeypatch.delenv("PYTHONBREAKPOINT", raising=False)
    return monkeypatch


class Recorder:
    """A hook that records each call and returns a marker."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kws: object) -> str:
        self.calls.append((args, kws))
        return "recorded"


class TestBreakpointCallsTheHook:
    """Row: `breakpoint(*args, **kws)` | O(1) plus the hook - calls
    `sys.breakpointhook(*args, **kws)` and returns its result. A replaced hook
    is called whatever `PYTHONBREAKPOINT` says."""

    def test_arguments_and_result_pass_straight_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hook = Recorder()
        monkeypatch.setattr(sys, "breakpointhook", hook)

        result = breakpoint(1, "two", key=[3])

        assert result == "recorded"
        assert hook.calls == [((1, "two"), {"key": [3]})]

    def test_a_replaced_hook_ignores_pythonbreakpoint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hook = Recorder()
        monkeypatch.setattr(sys, "breakpointhook", hook)
        monkeypatch.setenv("PYTHONBREAKPOINT", "0")

        assert breakpoint() == "recorded"
        assert len(hook.calls) == 1

    def test_dunder_hook_is_the_default_and_restores_it(
        self, default_hook: pytest.MonkeyPatch
    ) -> None:
        default_hook.setenv("PYTHONBREAKPOINT", "int")
        assert sys.__breakpointhook__("7") == 7

        default_hook.setattr(sys, "breakpointhook", Recorder())
        assert breakpoint("7") == "recorded"
        sys.breakpointhook = sys.__breakpointhook__
        assert breakpoint("7") == 7

    def test_the_audit_event_comes_first_with_the_hook(self, tmp_path: pathlib.Path) -> None:
        result = run_script(
            """
            import json
            import sys

            order = []

            def audit(event, args):
                if event == 'builtins.breakpoint':
                    order.append(('audit', args[0] is hook, len(args)))

            def hook(*args, **kws):
                order.append(('hook', args, kws))

            sys.addaudithook(audit)
            sys.breakpointhook = hook
            breakpoint(1, k=2)
            print(json.dumps(order))
            """,
            tmp_path,
        )

        assert last_json(result) == [["audit", True, 1], ["hook", [1], {"k": 2}]]


IMPORT_COUNTER = """
import builtins
import json
import os
import sys

real_import = builtins.__import__
imports = 0

def counting_import(*args, **kws):
    global imports
    imports += 1
    return real_import(*args, **kws)

def dive(depth, calls):
    if depth > 1:
        return dive(depth - 1, calls)
    builtins.__import__ = counting_import
    try:
        return [breakpoint([1]) for _ in range(calls)]
    finally:
        builtins.__import__ = real_import
"""


class TestDisabled:
    """Row: `PYTHONBREAKPOINT=0` | O(1) - returns `None` without importing
    anything. An import per call, or tracing left on, would show the call
    doing more than returning; the same holds at depths 1 and 100."""

    @pytest.mark.parametrize("depth", [1, 100])
    def test_imports_nothing_and_traces_nothing(self, tmp_path: pathlib.Path, depth: int) -> None:
        result = run_script(
            IMPORT_COUNTER
            + f"""
results = dive({depth}, 100)
print(json.dumps([results, imports, sys.gettrace() is None, 'pdb' in sys.modules]))
""",
            tmp_path,
            PYTHONBREAKPOINT="0",
        )

        assert last_json(result) == [[None] * 100, 0, True, False]

    def test_the_counter_sees_a_named_hook_import(self, tmp_path: pathlib.Path) -> None:
        """The control: the same counter sees one import per call when
        `PYTHONBREAKPOINT` names a callable."""
        result = run_script(
            IMPORT_COUNTER + "\nprint(json.dumps([dive(1, 100)[0], imports]))\n",
            tmp_path,
            PYTHONBREAKPOINT="json.dumps",
        )

        assert last_json(result) == ["[1]", 100]

    def test_returns_none_in_process(self, default_hook: pytest.MonkeyPatch) -> None:
        default_hook.setenv("PYTHONBREAKPOINT", "0")
        assert breakpoint() is None
        assert breakpoint(1, k=2) is None


class TestNamedCallable:
    """Row: `PYTHONBREAKPOINT=module.function` | O(1) plus the function - the
    module part is imported and `function(*args, **kws)` returned; a name with
    no dot is a builtin. The variable is read on every call."""

    @pytest.mark.parametrize(
        ("name", "args", "kws", "expected"),
        [
            ("json.dumps", ([1, 2],), {}, "[1, 2]"),
            ("json.dumps", ({"a": 1},), {"sort_keys": True}, '{"a": 1}'),
            ("os.path.join", ("a", "b"), {}, os.path.join("a", "b")),
            ("int", ("42",), {}, 42),
            ("int", ("ff",), {"base": 16}, 255),
        ],
    )
    def test_returns_the_callables_result(
        self,
        default_hook: pytest.MonkeyPatch,
        name: str,
        args: tuple[object, ...],
        kws: dict[str, object],
        expected: object,
    ) -> None:
        default_hook.setenv("PYTHONBREAKPOINT", name)
        assert breakpoint(*args, **kws) == expected

    def test_a_change_to_the_environment_applies_to_the_next_call(
        self, default_hook: pytest.MonkeyPatch
    ) -> None:
        default_hook.setenv("PYTHONBREAKPOINT", "str")
        assert breakpoint(5) == "5"
        default_hook.setenv("PYTHONBREAKPOINT", "repr")
        assert breakpoint("5") == "'5'"


class TestUnimportable:
    """Row: `PYTHONBREAKPOINT` naming a missing module or attribute | O(1) -
    emits a `RuntimeWarning` and returns `None` rather than raising. The
    exception type decides it: an `ImportError` raised by the module warns,
    any other propagates."""

    @pytest.mark.parametrize(
        "name", ["no_such_module_for_breakpoint.hook", "json.no_such_attribute", ".hook"]
    )
    def test_warns_and_returns_none(self, default_hook: pytest.MonkeyPatch, name: str) -> None:
        default_hook.setenv("PYTHONBREAKPOINT", name)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = breakpoint()

        assert result is None
        assert [w.category for w in caught] == [RuntimeWarning]
        assert f'"{name}"' in str(caught[0].message)

    def test_an_import_error_raised_by_the_module_warns(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "failing_hook_module.py").write_text("raise ImportError('boom')\n")
        result = run_script(
            """
            import json
            import warnings

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                result = breakpoint()
            print(json.dumps([result, [w.category.__name__ for w in caught]]))
            """,
            tmp_path,
            PYTHONBREAKPOINT="failing_hook_module.hook",
        )

        assert last_json(result) == [None, ["RuntimeWarning"]]

    def test_an_error_raised_by_the_import_propagates(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "broken_hook_module.py").write_text("raise ValueError('boom')\n")
        result = run_script(
            """
            import json

            try:
                breakpoint()
            except ValueError as error:
                print(json.dumps(str(error)))
            """,
            tmp_path,
            PYTHONBREAKPOINT="broken_hook_module.hook",
        )

        assert last_json(result) == "boom"


class TestDefaultEntersPdb:
    """Row: `PYTHONBREAKPOINT` unset or empty | O(c + d) - calls
    `pdb.set_trace()`. A recording `set_trace` shows the route; a session
    driven through stdin shows the frames hooked and the linecache check."""

    @pytest.mark.parametrize("value", [None, ""])
    def test_unset_and_empty_call_pdb_set_trace(
        self, default_hook: pytest.MonkeyPatch, value: str | None
    ) -> None:
        import pdb

        with pytest.raises(AssertionError, match="reached pdb.set_trace"):
            breakpoint()
        if value is not None:
            default_hook.setenv("PYTHONBREAKPOINT", value)
        hook = Recorder()
        default_hook.setattr(pdb, "set_trace", hook)

        assert breakpoint(header="h") == "recorded"
        assert hook.calls == [((), {"header": "h"})]

    def test_a_positional_argument_raises_type_error(self, tmp_path: pathlib.Path) -> None:
        """The real `pdb.set_trace()` rejects the call before tracing anything.
        pytest replaces `pdb.set_trace` in its own process, so this runs in a
        fresh one."""
        result = run_script(
            """
            import json
            import sys

            try:
                breakpoint('here')
            except TypeError:
                print(json.dumps(sys.gettrace() is None))
            """,
            tmp_path,
        )

        assert last_json(result) is True

    @staticmethod
    def where_entries(depth: int, cwd: pathlib.Path) -> tuple[int, int]:
        """Frames `where` lists, and `checkcache()` calls with no file name,
        for a breakpoint() at recursion depth `depth`."""
        result = run_script(
            f"""
            import json
            import linecache
            import sys

            real_checkcache = linecache.checkcache
            checks = []

            def counting_checkcache(*args, **kws):
                checks.append(bool(args or kws))
                return real_checkcache(*args, **kws)

            def dive(n):
                if n > 1:
                    return dive(n - 1)
                linecache.checkcache = counting_checkcache
                breakpoint()
                linecache.checkcache = real_checkcache

            dive({depth})
            print()
            print(json.dumps(checks.count(False)))
            """,
            cwd,
            stdin="where\ncontinue\n",
        )
        assert result.returncode == 0, result.stderr
        entries = sum(
            1 for line in result.stdout.splitlines() if re.match(r"^[> ] \S.*\(\d+\)", line)
        )
        return entries, last_json(result)

    def test_entering_hooks_every_frame_and_checks_the_cache_once(
        self, tmp_path: pathlib.Path
    ) -> None:
        (shallow := tmp_path / "shallow").mkdir()
        (deep := tmp_path / "deep").mkdir()

        shallow_entries, shallow_checks = self.where_entries(10, shallow)
        deep_entries, deep_checks = self.where_entries(100, deep)

        assert deep_entries - shallow_entries == 90, (shallow_entries, deep_entries)
        assert shallow_checks == deep_checks == 1

    def test_pdb_instances_built_by_two_calls(self, tmp_path: pathlib.Path) -> None:
        """Before 3.14 every call builds a `Pdb`; from 3.14 the second reuses
        the first, which runs on the `'monitoring'` backend."""
        result = run_script(
            """
            import json
            import pdb

            built = []
            real_init = pdb.Pdb.__init__

            def counting_init(self, *args, **kws):
                built.append(self)
                real_init(self, *args, **kws)

            pdb.Pdb.__init__ = counting_init
            breakpoint()
            breakpoint()
            pdb.Pdb.__init__ = real_init
            print()
            print(json.dumps([len(built), getattr(built[0], 'backend', 'settrace')]))
            """,
            tmp_path,
            stdin="continue\ncontinue\n",
        )

        expected = [1, "monitoring"] if sys.version_info >= (3, 14) else [2, "settrace"]
        assert last_json(result) == expected


class TestIgnoreEnvironment:
    """Prose: `python -E` and `python -I` ignore `PYTHONBREAKPOINT`, so a
    `breakpoint()` enters pdb even when the variable is `0`. The plain run is
    the control."""

    SCRIPT = """
        import json
        import pdb

        entered = []
        pdb.set_trace = lambda **kws: entered.append(True)
        breakpoint()
        print(json.dumps(len(entered)))
        """

    @pytest.mark.parametrize(("flags", "entered"), [((), 0), (("-E",), 1), (("-I",), 1)])
    def test_flags_decide_whether_zero_is_read(
        self, tmp_path: pathlib.Path, flags: tuple[str, ...], entered: int
    ) -> None:
        result = run_script(self.SCRIPT, tmp_path, flags=flags, PYTHONBREAKPOINT="0")
        assert last_json(result) == entered


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
    return run_script(source, cwd)


class TestDocumentedExamples:
    """Each block runs in its own subprocess with closed stdin, an empty
    `HOME` and no inherited `PYTHONBREAKPOINT`, so a block that reached pdb
    would read end of input and stop rather than wait."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks():
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "breakpoint('42') == 42" in s)
        mutated = source.replace("breakpoint('42') == 42", "breakpoint('42') == 43", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
