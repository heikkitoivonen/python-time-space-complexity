"""Tests for docs/builtins/globals.md.

globals() is builtin_globals in Python/bltinmodule.c: the running frame's
f_globals, returned as is. locals() is builtin_locals, which up to 3.12 is
PyEval_GetLocals: the module or class namespace itself, or for a function one
FastToLocals pass over the fast locals into the frame's one dict, which every
call refreshes and returns again. From the v3.13.0 tag (PEP 667) it is
_PyEval_GetFrameLocals: still the namespace itself at module and class scope,
but in a function a fresh dict filled by PyDict_Update from a FrameLocalsProxy,
whose keys() is one pass and whose __getitem__ (framelocalsproxy_getkeyindex in
Objects/frameobject.c) scans co_localsplusnames from the start for each key -
m lookups of O(m). `frame.f_locals` follows the same split: the frame's one
snapshot dict up to 3.12, and from 3.13 a new FrameLocalsProxy on every read,
whose item writes assign the fast local.

Observation settles every row but one:

* `globals()` is the frame's globals dict: in a module the same object as
  `sys.modules[name].__dict__`, and under exec() the mapping that was passed
  in; a key written into it is a module global, and `print` is not in it
  where `__builtins__` is;
* `locals()` at module scope is `globals()`, and in a class body it is the
  namespace, so a key written there becomes a class attribute;
* in a function the snapshot holds every bound local and no unbound one, a
  key written into it is not seen by the function, and two snapshots from the
  same call are one object up to 3.12 and two objects from 3.13;
* `frame.f_locals` is the same dict on every read up to 3.12, and from 3.13 a
  FrameLocalsProxy that differs per read, that a write through reaches the
  function's variable, and that allocates 40 bytes at 1,000 locals as at
  8,000 where `dict()` of it allocates 47,864 and 378,616 (aarch64, CPython
  3.14); up to 3.12 a write through it is not seen by the function.

Elapsed time settles the function-scope locals() row: x16 in bound locals
(1,000 to 16,000) costs x15.6 on 3.10, x22.4 on 3.11, x22.4 on 3.12, x210.5
on 3.13 and x215.9 on 3.14, where linear predicts x16 and quadratic x256. The
assignments that bind the locals are inside the timed call and are about 1%
of it on 3.13 and later; before 3.13 they are a fixed share, so the ratio
stays near linear either way.

Not varied: unbound locals as a share of the frame (the snapshot scans every
slot, bound or not, so an all-bound frame is the framing with the widest gap),
and the hash-collision worst case of the dict operations, which is dict's own
bound. `dict(frame.f_locals)` from 3.13 is the same key-by-key path as
locals() and is not timed separately; the page's O(m²) for it rests on the
locals() measurement and the source above.
"""

import operator
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "globals.md"


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[..., Any], *args: Any) -> int:
    tracemalloc.start()
    try:
        func(*args)
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def function_with_locals(count: int, tail: str) -> Callable[[], Any]:
    """A function binding `count` locals, ending in the statement `tail`."""
    namespace: dict[str, Any] = {"sys": sys}
    body = "".join(f"    v{i} = {i}\n" for i in range(count))
    exec(f"def f():\n{body}    {tail}\n", namespace)
    return namespace["f"]


class TestGlobalsRow:
    """`globals()` is the module's own dict."""

    def test_it_is_the_module_dict(self) -> None:
        assert globals() is sys.modules[__name__].__dict__

    def test_under_exec_it_is_the_mapping_passed_in(self) -> None:
        namespace: dict[str, Any] = {}
        exec("captured = globals()", namespace)
        assert namespace["captured"] is namespace

    def test_writes_reach_the_module(self) -> None:
        module = types.ModuleType("sample")
        exec("globals()['added'] = 1", module.__dict__)
        assert module.added == 1  # type: ignore[attr-defined]

    def test_builtin_names_are_not_globals(self) -> None:
        namespace: dict[str, Any] = {}
        exec(
            "has_print = 'print' in globals()\nhas_builtins = '__builtins__' in globals()",
            namespace,
        )
        assert namespace["has_print"] is False
        assert namespace["has_builtins"] is True


class TestLocalsAtModuleAndClassScope:
    """At module or class scope, locals() is the namespace itself."""

    def test_module_scope_is_globals(self) -> None:
        namespace: dict[str, Any] = {}
        exec("same = locals() is globals()", namespace)
        assert namespace["same"] is True

    def test_class_body_is_the_namespace_being_built(self) -> None:
        class Sample:
            locals()["added"] = 1

        assert Sample.added == 1  # type: ignore[attr-defined]


class TestLocalsInAFunction:
    """In a function, locals() is a snapshot rebuilt on every call."""

    def test_the_snapshot_has_every_bound_local_and_no_unbound_one(self) -> None:
        def sample() -> dict[str, Any]:
            # Unused by design: locals() reads them out of the frame, which is
            # the behaviour under test.
            first = 1  # noqa: F841
            second = 2  # noqa: F841
            if first == 0:
                never = 3  # noqa: F841
            return locals()

        assert sample() == {"first": 1, "second": 2}

    def test_writes_to_the_snapshot_do_not_reach_the_function(self) -> None:
        def sample() -> int:
            value = 1
            locals()["value"] = 2
            return value

        assert sample() == 1

    def test_two_snapshots_share_a_dict_only_before_3_13(self) -> None:
        def sample() -> tuple[bool, int]:
            value = 1
            before = locals()
            value = 2  # noqa: F841 - read back through the snapshots, not the name
            after = locals()
            return before is after, before["value"]

        shared, seen_through_first = sample()
        if sys.version_info >= (3, 13):
            assert not shared and seen_through_first == 1
        else:
            assert shared and seen_through_first == 2

    @pytest.mark.timing
    def test_the_snapshot_is_quadratic_from_3_13_and_linear_before(self) -> None:
        few = function_with_locals(1_000, "return locals()")
        many = function_with_locals(16_000, "return locals()")
        assert len(few()) == 1_000 and len(many()) == 16_000

        ratio = best_time(many) / best_time(few)

        if sys.version_info >= (3, 13):
            assert 60 < ratio < 1000, (
                f"x16 locals should cost near x256 from 3.13, got x{ratio:.1f}"
            )
        else:
            assert 8 < ratio < 60, f"x16 locals should cost near x16 before 3.13, got x{ratio:.1f}"


class TestFrameLocalsRow:
    """`frame.f_locals` is a live proxy from 3.13 and a snapshot dict before."""

    def test_writes_through_it_reach_the_function_only_from_3_13(self) -> None:
        def sample() -> int:
            value = 1
            sys._getframe().f_locals["value"] = 2
            return value

        assert sample() == (2 if sys.version_info >= (3, 13) else 1)

    def test_it_is_one_dict_before_3_13_and_a_proxy_per_read_after(self) -> None:
        frame = function_with_locals(3, "return sys._getframe()")()

        if sys.version_info >= (3, 13):
            assert type(frame.f_locals).__name__ == "FrameLocalsProxy"
            assert frame.f_locals is not frame.f_locals
        else:
            assert type(frame.f_locals) is dict
            assert frame.f_locals is frame.f_locals
        assert dict(frame.f_locals) == {f"v{i}": i for i in range(3)}

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the proxy exists from 3.13")
    def test_the_proxy_costs_nothing_per_local_where_copying_it_does(self) -> None:
        frames = [function_with_locals(m, "return sys._getframe()")() for m in (1_000, 8_000)]
        assert all(
            len(frame.f_locals) == m for frame, m in zip(frames, (1_000, 8_000), strict=True)
        )

        proxy_peaks = [traced_peak(operator.attrgetter("f_locals"), frame) for frame in frames]
        copy_peaks = [traced_peak(lambda f: dict(f.f_locals), frame) for frame in frames]

        assert proxy_peaks[0] == proxy_peaks[1], proxy_peaks
        assert copy_peaks[1] > copy_peaks[0] * 4, copy_peaks
        assert proxy_peaks[1] < copy_peaks[0] / 100, (proxy_peaks, copy_peaks)


EXPECTED_BLOCKS = 14


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
        compiles and then dies at run time, so NameError and KeyError get
        their own check."""
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr or "KeyError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        source = _block_containing("locals()['x'] = 10")
        broken = source.replace("except NameError:", "except KeyError:", 1)
        assert broken != source, "the mutation did not change the handler"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr

    @pytest.mark.parametrize(
        ("marker", "expected"),
        [
            ("print('print' in globals())", "False\nTrue\n"),
            ("my_vars = {k: v for k, v in globals().items()", "{'x': 10, 'y': 20, 'z': 30}\n"),
            ("caller_vars = get_caller_locals()", "{'x': 10, 'y': 20}\n"),
            ("print(locals() is globals())", "True\n100\n"),
            ("print('local_y' in locals())", "True\nFalse\nFalse\nTrue\n"),
            ("locals()['x'] = 10", "x not in local variables\n"),
            ("state = save_state(locals())", '{"count": 10, "name": "task", "items": [1, 2, 3]}\n'),
        ],
        ids=[
            "builtins",
            "inspecting",
            "caller-locals",
            "module-level",
            "inside-functions",
            "set-local",
            "json",
        ],
    )
    def test_the_stated_output_is_what_the_block_prints(
        self, marker: str, expected: str, tmp_path: pathlib.Path
    ) -> None:
        result = _run(_block_containing(marker), tmp_path)

        assert result.returncode == 0, result.stderr.strip()
        assert result.stdout.endswith(expected), result.stdout
