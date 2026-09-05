"""Tests to verify documented behaviour of the sys module.

Most of `sys` reads or writes one interpreter field, so most of the page is a
wall of O(1) with nothing to vary. What is worth testing is the short list of
operations that are not constant, and those are mostly observable: a frame
walk is a chain of known length, `_current_frames()` returns one entry per
thread, every audit hook fires, and a tracer is called once per event.

Four claims did not survive the check, and two of the page's code blocks did
not run at all:

* `sys.setrecursionlimit(n)` was documented O(1). Since 3.11 it writes through
  to every thread state (`Py_SetRecursionLimit` in Python/ceval.c), so it is
  O(t): flat on 3.10 at 5.0e-08s from 1 thread to 400, and 3.4e-08s to
  4.9e-07s across the same range on 3.14.
* The `sys.modules` lookup row claimed O(n) *space*. A dict lookup allocates
  nothing; the O(n) was the size of the dict, which is not what the column
  means.
* "Multiple O(n) inserts at position 0" was offered a fix - reversing the
  input and inserting at 0 anyway - labelled "O(k) amortized". Reversing
  fixes the resulting order, not the cost: k inserts at the front of an
  e-element list is O(k * e) however they are ordered.
* "sys.modules is dict-like with ~200+ entries typically" is wrong twice. It
  is a real dict, and a plain script starts with 34 entries here, not 200.
  `sys.path`'s "usually ~10-20" was 5. Both counts are gone rather than
  corrected: they are properties of one installation.

The two blocks that did not run:

* the module-lookup block ended an `if` with nothing but a comment, so it
  raised IndentationError before reaching anything it was illustrating;
* the path block used `paths` without defining it, so it raised NameError.

Fifteen rows were missing, including every operation on the page that is not
constant time: `sys._getframe`, `sys._current_frames`, `sys.intern`,
`sys.audit`, and the `sys.path` operations that the prose already priced but
the table never listed.

One version boundary turned up while testing rather than from the changelog,
and it is 3.12 alone rather than a floor. `sys.intern()` normally frees the
string with its last reference - `sys_intern_impl` calls
`_PyUnicode_InternMortal` in 3.14, and the official docs say plainly that
"interned strings are not immortal". 3.12 made them immortal, and only 3.12:
interning 500 strings of 20,000 characters and dropping every reference
retains 9.6 MB there and 0.0 MB on 3.10, 3.11, 3.13 and 3.14. It reached the
page because it changes what a caller has to do - on 3.12, interning many
distinct strings never gives the memory back.

Untested axes, and why:

* Interpreter state. Every measurement here is from one process with one
  interpreter. `_current_frames` and `setrecursionlimit` walk per-interpreter
  thread lists, so a sub-interpreter would change which threads are counted,
  not how the count is reached.
* Audit hook cost. The dispatch is counted, not timed; a hook that does real
  work adds its own cost to each of the h calls, which is the caller's.

Not settled by execution:

* Every O(1) row with no input dimension - `getrecursionlimit`, `getrefcount`,
  `exc_info`, the simple getters, the data attributes. There is nothing to
  vary, so growth cannot be measured. They are single field reads in
  Python/sysmodule.c, and the tests below assert only that each name exists
  and answers.
* `sys.exit()`'s note that the shutdown after the raise is not part of its
  cost. The raise is tested; the interpreter teardown it triggers cannot be
  measured from inside the process it tears down.
* "Python 2.6+" and "Python 3.x" in the Version Notes: nothing in the
  supported range can show an operation absent that far back.
"""

from __future__ import annotations

import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import timeit
import tracemalloc
from collections.abc import Callable, Iterator
from types import FrameType
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "stdlib" / "sys.md"
EXPECTED_BLOCKS = 11


def per_call(operation: Callable[[], Any], number: int = 1000, repeat: int = 5) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(operation, number=number, repeat=repeat)) / number


def run_isolated(source: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a fresh interpreter.

    Audit hooks cannot be removed once installed and a tracer slows everything
    that follows, so the tests for those run out of process rather than
    leaving the suite in a changed state. So does the intern timing test: on
    3.12 an interned string is immortal, and it interns some 200 MB of them
    that would otherwise stay resident for the rest of the run.
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class ParkedThreads:
    """A context manager holding a fixed number of threads alive and idle."""

    def __init__(self, count: int) -> None:
        self.count = count
        self._release = threading.Event()
        self._running = threading.Barrier(count + 1)
        self._threads: list[threading.Thread] = []

    def _park(self) -> None:
        self._running.wait()
        self._release.wait()

    def __enter__(self) -> ParkedThreads:
        self._threads = [
            threading.Thread(target=self._park, daemon=True) for _ in range(self.count)
        ]
        for thread in self._threads:
            thread.start()
        self._running.wait()  # every thread is live before anything is measured
        return self

    def __exit__(self, *exc: object) -> None:
        self._release.set()
        for thread in self._threads:
            thread.join()


class TestExceptionState:
    """`exc_info()`, `exception()` and `exit()`."""

    def test_exc_info_reports_the_exception_being_handled(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as caught:
            exc_type, exc_value, exc_traceback = sys.exc_info()

            assert exc_type is ValueError
            assert exc_value is caught
            assert exc_traceback is caught.__traceback__

    def test_exc_info_builds_a_fresh_tuple_each_call(self) -> None:
        """O(1), but it is a construction rather than a cached read."""
        try:
            raise ValueError("boom")
        except ValueError:
            first, second = sys.exc_info(), sys.exc_info()

            assert first == second
            assert first is not second

    def test_outside_a_handler_there_is_nothing_to_report(self) -> None:
        assert sys.exc_info() == (None, None, None)

    @pytest.mark.skipif(not hasattr(sys, "exception"), reason="sys.exception() is Python 3.11+")
    def test_exception_returns_the_value_without_the_tuple(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            assert sys.exception() is sys.exc_info()[1]  # type: ignore[attr-defined]

    def test_exit_raises_rather_than_terminating(self) -> None:
        """Why the row prices the raise and not the shutdown: it is catchable."""
        with pytest.raises(SystemExit) as raised:
            sys.exit(3)

        assert raised.value.code == 3


class TestFrames:
    """`sys._getframe(d)` | O(d) | and `sys._current_frames()` | O(t) |."""

    @staticmethod
    def _nest(depth: int, action: Callable[[], Any]) -> Any:
        """Call `action` with exactly `depth` frames of `_nest` beneath it."""
        if depth <= 1:
            return action()
        return TestFrames._nest(depth - 1, action)

    @staticmethod
    def _names_up_to(target: str) -> list[str]:
        """Every frame name from here outwards, stopping at `target`."""
        names: list[str] = []
        level = 0
        while True:
            name = sys._getframe(level).f_code.co_name
            names.append(name)
            if name == target:
                return names
            level += 1

    def test_getframe_walks_one_link_per_level(self) -> None:
        """Observable rather than timed: each level is one more frame.

        `_nest` calls itself, so at depth d the chain between here and this
        test holds exactly d frames of `_nest` - which is what the walk has to
        traverse. Counting them rather than indexing them keeps the assertion
        clear of the comprehension frame 3.11 adds and 3.12 inlines away.
        """
        own_name = "test_getframe_walks_one_link_per_level"

        for depth in (5, 25):
            names = self._nest(depth, lambda: self._names_up_to(own_name))

            assert names.count("_nest") == depth, (
                f"depth {depth} should put {depth} _nest frames on the chain: {names}"
            )
            assert names[-1] == own_name

    def test_asking_past_the_bottom_of_the_stack_raises(self) -> None:
        """The walk counts links, so it can run out of them."""
        with pytest.raises(ValueError, match="call stack is not deep enough"):
            sys._getframe(1_000_000)

    @pytest.mark.timing
    def test_getframe_cost_follows_the_depth(self) -> None:
        original = sys.getrecursionlimit()
        sys.setrecursionlimit(20_000)  # the 1,000-deep nest needs headroom
        try:
            shallow = self._nest(100, lambda: per_call(lambda: sys._getframe(100), 20_000))
            deep = self._nest(1_000, lambda: per_call(lambda: sys._getframe(1_000), 20_000))
        finally:
            sys.setrecursionlimit(original)

        assert deep > shallow * 4, (
            f"ten times the depth is ten times the walk: depth 100 {shallow:.2e}s, "
            f"depth 1,000 {deep:.2e}s"
        )

    def test_current_frames_returns_one_entry_per_thread(self) -> None:
        """The O(t) row, observed directly in the size of the result."""
        alone = len(sys._current_frames())

        with ParkedThreads(12):
            crowded = len(sys._current_frames())

        assert crowded == alone + 12, (
            f"expected one frame per live thread: {alone} alone, {crowded} with 12 more"
        )


class TestRecursionLimit:
    """`getrecursionlimit()` | O(1) | and `setrecursionlimit(n)` | O(t) |."""

    @pytest.fixture(autouse=True)
    def _restore_limit(self) -> Iterator[None]:
        original = sys.getrecursionlimit()
        yield
        sys.setrecursionlimit(original)

    def test_the_limit_round_trips(self) -> None:
        sys.setrecursionlimit(2_500)

        assert sys.getrecursionlimit() == 2_500

    def test_a_limit_below_the_current_depth_is_refused(self) -> None:
        with pytest.raises(RecursionError, match="limit is too low"):
            sys.setrecursionlimit(1)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="3.10 sets one interpreter-wide value")
    def test_setting_the_limit_costs_one_pass_over_the_threads(self) -> None:
        """The corrected row. `Py_SetRecursionLimit` loops over thread states.

        On 3.10 this is flat, which is why the test does not run there: the
        loop was introduced with the per-thread limit in 3.11.
        """
        limit = sys.getrecursionlimit()
        alone = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        with ParkedThreads(300):
            crowded = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        assert crowded > alone * 3, (
            f"300 more thread states should cost more to write through: "
            f"alone {alone:.2e}s, crowded {crowded:.2e}s"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(
        sys.version_info >= (3, 11), reason="3.11 and later write through to each thread"
    )
    def test_before_3_11_the_limit_was_one_field(self) -> None:
        limit = sys.getrecursionlimit()
        alone = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        with ParkedThreads(300):
            crowded = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        assert crowded < alone * 3, (
            f"3.10 writes one interpreter field, so threads should not matter: "
            f"alone {alone:.2e}s, crowded {crowded:.2e}s"
        )


class CountingSizeof:
    """An object that records how often its `__sizeof__` is consulted."""

    calls = 0

    @classmethod
    def reset(cls) -> None:
        cls.calls = 0

    def __sizeof__(self) -> int:
        CountingSizeof.calls += 1
        return 42


class TestGetsizeof:
    """`sys.getsizeof(obj)` | O(1) | it asks the object, and asks only it."""

    def test_getsizeof_calls_dunder_sizeof_once(self) -> None:
        CountingSizeof.reset()

        size = sys.getsizeof(CountingSizeof())

        assert CountingSizeof.calls == 1
        assert size >= 42, "the pre-header is added to what __sizeof__ returned"

    def test_getsizeof_does_not_look_inside_a_container(self) -> None:
        """The page's "doesn't include referenced objects", counted.

        A hundred members whose `__sizeof__` would announce itself, and not
        one of them is asked.
        """
        CountingSizeof.reset()
        members = [CountingSizeof() for _ in range(100)]

        sys.getsizeof(members)

        assert CountingSizeof.calls == 0, "a recursive size would have called every member"

    def test_container_size_does_not_follow_its_contents(self) -> None:
        small = sys.getsizeof([b"x"])
        large = sys.getsizeof([b"x" * 1_000_000])

        assert small == large, "the list holds pointers, whatever they point at"

    # Built inside the test: a 100,000-digit int cannot be turned into a
    # pytest parameter id without tripping sys.set_int_max_str_digits.
    BUILDERS: dict[str, tuple[Callable[[], Any], Callable[[], Any]]] = {
        "list": (lambda: [0] * 100, lambda: [0] * 1_000_000),
        "dict": (lambda: dict.fromkeys(range(100)), lambda: dict.fromkeys(range(200_000))),
        "set": (lambda: set(range(100)), lambda: set(range(200_000))),
        "str": (lambda: "x" * 100, lambda: "x" * 1_000_000),
        "bytes": (lambda: b"x" * 100, lambda: b"x" * 1_000_000),
        "int": (lambda: 10**100, lambda: 10**100_000),
    }

    @pytest.mark.timing
    @pytest.mark.parametrize("name", sorted(BUILDERS))
    def test_getsizeof_is_constant_for_builtins(self, name: str) -> None:
        """Every builtin computes its size from a stored count."""
        build_small, build_large = self.BUILDERS[name]
        small, large = build_small(), build_large()

        quick = per_call(lambda: sys.getsizeof(small), 100_000)
        slow = per_call(lambda: sys.getsizeof(large), 100_000)

        assert slow < quick * 2, (
            f"{name} grew by a factor of thousands and getsizeof should not notice: "
            f"small {quick:.2e}s, large {slow:.2e}s"
        )

    def test_an_object_without_dunder_sizeof_needs_the_default(self) -> None:
        class Bare:
            __slots__ = ()
            __sizeof__ = None  # type: ignore[assignment]

        with pytest.raises(TypeError):
            sys.getsizeof(Bare())

        assert sys.getsizeof(Bare(), 99) == 99


class TestIntern:
    """`sys.intern(s)` | O(len(s)) | O(1) when already interned."""

    def test_equal_strings_intern_to_one_object(self) -> None:
        first = sys.intern("".join(["inter", "ning", "-probe"]))
        second = sys.intern("".join(["inter", "ning", "-probe"]))

        assert first is second

    def test_interning_an_interned_string_returns_it_unchanged(self) -> None:
        once = sys.intern("x" * 5_000)

        assert sys.intern(once) is once

    def test_only_exact_strings_can_be_interned(self) -> None:
        """A str subclass is refused too, which is why the row says `len(s)`
        of a real str and nothing about what a subclass might cost.
        """

        class Subclass(str):
            pass

        with pytest.raises(TypeError, match="can't intern"):
            sys.intern(Subclass("text"))

        with pytest.raises(TypeError, match="must be str"):
            sys.intern(b"bytes")  # type: ignore[arg-type]

    @pytest.mark.skipif(
        not hasattr(sys, "getunicodeinternedsize"),
        reason="sys.getunicodeinternedsize() is Python 3.12+",
    )
    def test_interning_adds_to_the_table(self) -> None:
        """Why the first intern costs O(len): it is a lookup and an insert."""
        interned_size = sys.getunicodeinternedsize  # type: ignore[attr-defined]
        before = interned_size()

        kept = sys.intern("".join(["a-string-nothing-else-would-hold", "-1"]))

        assert interned_size() == before + 1
        assert kept == "a-string-nothing-else-would-hold-1"

    @pytest.mark.skipif(
        not hasattr(sys, "getunicodeinternedsize"),
        reason="sys.getunicodeinternedsize() is Python 3.12+",
    )
    def test_an_interned_string_nobody_keeps_does_not_stay(self) -> None:
        """3.12 is the one version that keeps it, which the row has to say.

        `sys_intern_impl` calls `_PyUnicode_InternMortal`, so the table holds
        no reference of its own: discard the result and the entry goes with
        it. On 3.12 the same call left the string immortal and the count rose
        whether anyone kept it or not. This test can only see 3.12 onwards,
        since `getunicodeinternedsize()` does not exist before it - the
        retention test below covers the whole supported range.
        """
        interned_size = sys.getunicodeinternedsize  # type: ignore[attr-defined]
        before = interned_size()

        sys.intern("".join(["nothing-holds-this-string", "-2"]))

        if sys.version_info >= (3, 13):
            assert interned_size() == before, "a string nobody references is not kept interned"
        else:
            assert interned_size() == before + 1, "3.12 interning made it immortal"

    def test_only_3_12_keeps_an_interned_string_alive(self) -> None:
        """The retention, measured on every supported version.

        `getunicodeinternedsize()` arrived in 3.12, so the count test above
        cannot see 3.10 or 3.11. Traced allocation can: intern a payload,
        drop every reference to it, and see whether the memory comes back.
        """
        payload = 500 * 20_000  # bytes of ASCII, if every string is kept

        def intern_and_discard() -> None:
            """Nothing outlives this call, so its locals cannot hold them."""
            for index in range(500):
                sys.intern(str(index).rjust(20_000, "q"))

        tracemalloc.start()
        try:
            base, _ = tracemalloc.get_traced_memory()
            intern_and_discard()
            gc.collect()
            current, _ = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        retained = current - base
        if sys.version_info[:2] == (3, 12):
            assert retained > payload * 0.5, (
                f"3.12 interning is immortal, so the payload should still be held: "
                f"retained {retained:,} of {payload:,} bytes"
            )
        else:
            assert retained < payload * 0.1, (
                f"interned strings are freed with their last reference: "
                f"retained {retained:,} of {payload:,} bytes"
            )

    @pytest.mark.timing
    def test_the_first_intern_follows_the_string_length(self) -> None:
        """Run out of process: on 3.12 an interned string is immortal, and
        this test interns about 200 MB of them, which would stay resident for
        the rest of the suite. The subprocess times both lengths and prints
        one figure per line; the assertion is unchanged.
        """
        result = run_isolated(
            """
            import sys
            import timeit

            def fresh(length, count=2_000):
                strings = [str(index).rjust(length, "q") for index in range(count)]
                start = timeit.default_timer()
                for text in strings:
                    sys.intern(text)
                return (timeit.default_timer() - start) / count

            print(min(fresh(1_000) for _ in range(3)))
            print(min(fresh(100_000) for _ in range(3)))
            """
        )

        assert result.returncode == 0, result.stderr
        short, long = (float(line) for line in result.stdout.split())

        assert long > short * 10, (
            f"a hundred times the characters is hashed and compared: "
            f"1,000 chars {short:.2e}s, 100,000 chars {long:.2e}s"
        )

    @pytest.mark.timing
    def test_re_interning_does_not_follow_the_length(self) -> None:
        short, long = sys.intern("q" * 1_000), sys.intern("q" * 100_000)

        short_time = per_call(lambda: sys.intern(short), 100_000)
        long_time = per_call(lambda: sys.intern(long), 100_000)

        assert long_time < short_time * 2, (
            f"an already-interned string is recognised without being read: "
            f"1,000 chars {short_time:.2e}s, 100,000 chars {long_time:.2e}s"
        )


class TestAuditHooks:
    """`sys.audit(event, *args)` | O(h) | every hook is called."""

    def test_every_installed_hook_sees_every_event(self) -> None:
        """Run out of process: an audit hook cannot be uninstalled."""
        result = run_isolated(
            """
            import sys

            fired = []
            for index in range(8):
                sys.addaudithook(lambda event, args, i=index: fired.append((i, event)))

            sys.audit("probe.one")
            sys.audit("probe.two")
            print(sorted(i for i, event in fired if event == "probe.one"))
            print(len([1 for _, event in fired if event.startswith("probe.")]))
            """
        )

        assert result.returncode == 0, result.stderr
        hooks, total = result.stdout.strip().splitlines()
        assert hooks == str(list(range(8))), "each of the eight hooks should see the event"
        assert total == "16", "eight hooks times two events"

    def test_hooks_cannot_be_removed(self) -> None:
        assert not hasattr(sys, "removeaudithook")


class TestTracing:
    """`settrace(fn)` | O(1) | to install; the cost is one call per event."""

    def test_installing_and_reading_back_the_tracer(self) -> None:
        original = sys.gettrace()

        def tracer(frame: FrameType, event: str, arg: Any) -> Any:
            return None

        try:
            sys.settrace(tracer)
            assert sys.gettrace() is tracer
        finally:
            sys.settrace(original)

        assert sys.gettrace() is original

    def test_the_tracer_is_called_once_per_line(self) -> None:
        """Why installing is O(1) and running is not: events are per line.

        Counted rather than timed, and the two loop sizes differ by a factor
        of ten in traced lines, which is what a per-event dispatch means.
        """

        def count_line_events(iterations: int) -> int:
            events = 0

            def tracer(frame: FrameType, event: str, arg: Any) -> Any:
                nonlocal events
                if event == "line":
                    events += 1
                return tracer

            def work() -> int:
                total = 0
                for index in range(iterations):
                    total += index
                return total

            original = sys.gettrace()
            try:
                sys.settrace(tracer)
                work()
            finally:
                sys.settrace(original)
            return events

        few, many = count_line_events(10), count_line_events(100)

        assert many > few * 5, (
            f"a tracer pays per line executed, not per call: 10 iterations {few} events, "
            f"100 iterations {many}"
        )


class TestModulesAndPath:
    """The rows for `sys.modules` and `sys.path` are the rows for dict and list."""

    def test_modules_is_a_plain_dict(self) -> None:
        """What makes the lookup row true, rather than a claim of its own."""
        assert type(sys.modules) is dict
        assert sys.modules["sys"] is sys

    def test_path_is_a_plain_list(self) -> None:
        assert type(sys.path) is list

    def test_iterating_modules_visits_every_entry(self) -> None:
        assert len(list(sys.modules)) == len(sys.modules)

    def test_slice_assignment_prepends_without_replacing_the_list(self) -> None:
        """The page's fix for the repeated-insert loop, on a stand-in list."""
        path = ["/existing", "/entries"]
        identity = id(path)
        additions = ["/one", "/two", "/three"]

        path[:0] = additions

        assert id(path) == identity, "the interpreter keeps using the list it was given"
        assert path == ["/one", "/two", "/three", "/existing", "/entries"]

    @pytest.mark.timing
    def test_repeated_front_inserts_cost_more_than_one_splice(self) -> None:
        """The corrected claim: reversing the input does not make it cheaper."""
        entries, additions = 4_000, 400
        base = [f"/entry/{index}" for index in range(entries)]
        extra = [f"/new/{index}" for index in range(additions)]

        def one_at_a_time() -> None:
            path = base.copy()
            for entry in reversed(extra):
                path.insert(0, entry)

        def one_splice() -> None:
            path = base.copy()
            path[:0] = extra

        looped = per_call(one_at_a_time, 200)
        spliced = per_call(one_splice, 200)

        assert looped > spliced * 5, (
            f"k inserts shift e entries each, however they are ordered: "
            f"loop {looped:.2e}s, splice {spliced:.2e}s"
        )


class TestConstantTimeSurface:
    """The grouped rows: names that exist and answer in one field read.

    There is no size to vary here, so this is coverage rather than a growth
    measurement - it fails if the page names something the module does not
    have, or if one of them starts raising.
    """

    GETTERS = [
        "getdefaultencoding",
        "getfilesystemencoding",
        "getrecursionlimit",
        "getswitchinterval",
        "getallocatedblocks",
        "is_finalizing",
        "gettrace",
        "getprofile",
    ]

    ATTRIBUTES = [
        "platform",
        "version",
        "version_info",
        "maxsize",
        "executable",
        "argv",
        "byteorder",
        "hexversion",
    ]

    @pytest.mark.parametrize("name", GETTERS)
    def test_a_named_getter_answers(self, name: str) -> None:
        getter = getattr(sys, name)

        assert callable(getter)
        getter()

    @pytest.mark.parametrize("name", ATTRIBUTES)
    def test_a_named_attribute_is_present(self, name: str) -> None:
        assert hasattr(sys, name)

    def test_getrefcount_reports_a_live_count(self) -> None:
        target: list[int] = []
        before = sys.getrefcount(target)
        alias = target

        assert sys.getrefcount(target) == before + 1
        del alias
        assert sys.getrefcount(target) == before


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


class TestDocumentedExamples:
    """Every block on the page runs.

    They are run out of process because several of them reassign `sys.stdout`,
    mutate `sys.path` and raise the recursion limit - in-process that would
    leak into whatever ran next.
    """

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
        original = _blocks()[0][1]
        broken = original.replace("import sys\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
