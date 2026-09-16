"""Tests to verify documented behaviour of the unittest package.

docs/stdlib/unittest.md prices the framework's own work: finding tests,
ordering them, running fixtures, comparing two values, recording an outcome and
standing in for a dependency. The test body's own cost is never part of a bound
on that page, so nothing here measures a test body. Most rows are settled by
counting or by identity rather than by a clock.

Measurement scope:

* `assertEqual` dispatch is exact-type. A `list` subclass and a plain `list`
  holding the same elements take different paths, and the difference is visible
  without timing: the list gets a line-by-line diff in its failure message and
  the subclass gets a bare `!=`. Registering a type through
  `addTypeEqualityFunc` is checked on the same instance that did not have it.
* `maxDiff` truncates after the diff exists. The truncated message states the
  diff's length in characters, so the assertion is that the reported length
  matches the untruncated message's diff - a message built without computing
  the diff could not name its size. This settles the row with no tolerance,
  where timing the two `maxDiff` values would have compared two numbers that
  are equal by design.
* `assertSequenceEqual` short-circuits on `==` and `assertSetEqual` does not.
  A `list` subclass counting its own `__eq__` is called once for the sequence
  and a `set` subclass counting its own is called zero times, because the set
  path goes straight to `difference`. Zero is the whole claim: any
  short-circuit would have to call it.
* `assertCountEqual` is linear over hashable elements and quadratic in the
  distinct values otherwise. The sharpest form is counted rather than timed: an
  element that reports its own comparisons is compared about sixteen times as
  often when the input grows fourfold, where anything linear would be four. The
  timing test beside it takes the same 4x step on *equal* inputs, which is where
  the paths diverge most, because the counting path returns early and the
  fallback does not. A third case makes every element the same value, which the
  fallback marks off as it goes, so its cost stays near linear - without it the
  quadratic row would read as a claim about length. Which path a mixed sequence
  took is settled by counting too: an element that is hashable and counts its
  own comparisons is never compared while every element hashes, and is compared
  once one element beside it cannot.
* `assertWarns` clears `__warningregistry__` on every module in `sys.modules`.
  A module object placed in `sys.modules` with a non-empty registry comes back
  empty, which is an exact observation of a scan the page prices as O(M). The
  same module is asserted untouched by `assertRaises`, so the test distinguishes
  the two context managers rather than showing that something cleared it.
* `assertRaises` clears the traceback on exit. The stored exception's
  `__traceback__` is `None`, and a local of the raising frame is checked
  separately, so the row's two halves are pinned apart.
* `assertLogs` formats every record as it arrives. A formatter counting its own
  calls runs once per record before the block exits, which distinguishes eager
  formatting from formatting on access; `assertNoLogs` is asserted to pay the
  same cost on the records it then rejects.
* Class fixtures are counted, not timed. The same three tests in two orders
  produce two and three `setUpClass` calls. A suite is built fresh for each
  order because running one twice raises, which is itself asserted.
* Discovery is observed on a temporary tree holding the same test file twice,
  once under a package and once under a plain directory. The count is 1. A
  package `__init__.py` whose name cannot match `test*.py` is asserted imported,
  so the test covers both halves of the rule rather than only the exclusion, and
  a third case puts a matching file in the start directory itself to show that
  the rule is about descending rather than about roots. Each of these names its
  package differently: discovery imports the package, and a name already in
  `sys.modules` is not imported again, so a shared name would make a later test
  pass vacuously.
* A mock's call records are read directly off each ancestor. A leaf four hops
  below the root puts one entry on all five mocks, under five different names,
  which is the whole of the per-call O(d) row; the timing test alongside it steps depth from 1 to 32
  rather than doubling it, because the per-call cost at depth 1 is small enough
  that a narrow step would not separate it from noise.
* `create_autospec` and `Mock(spec=...)` are separated by counting children
  rather than by a clock: the autospec has a child mock per method before
  anything is touched and the spec'd mock has none. A list-of-strings spec is
  the third case, and is asserted to build no children and still reject an
  unknown name. Which of the two paths a spec took is asserted through what it
  stored rather than through a clock, because the fixed cost of building a mock
  moved far more between releases than either path did, and a timing test
  comparing them does not hold at the 3.10 floor.
* Two spec'd mocks differing only in how many names their spec holds are timed
  on an attribute that both already cached, so the only work left in the loop is
  the membership test the row prices. The `assertLogs` cache claim is counted
  instead: five unrelated loggers have their level caches filled, all five are
  empty inside the block, and they are refilled inside it so that the second
  invalidation on the way out has something to clear.
* The two mock assertion families are separated by counting as well as by a
  clock. Recorded calls that report their own comparisons show the last-call
  check comparing one of them however many were made, and the scanning check
  comparing its way to the end. The clock covers what counting cannot see: the
  matcher list the scanning check rebuilds in full before it compares anything.
* `assertRaises` clearing the raising frame is asserted against a control that
  keeps the same traceback alive through a plain `try`/`except`. The control's
  local survives and the context manager's does not, so the test cannot pass on
  an ordinary drop of the exception. What it does *not* reach is pinned beside
  it: a chained exception keeps its traceback and its frames' locals.
* Buffered output is read from the streams the run replaced rather than from the
  runner's report. A failure's traceback carries the captured text into the
  report whether or not `stopTest` forwarded it, so the report cannot tell the
  two apart.
* Autospecking a class is asserted to produce a second specced mock for what
  calling it returns, which the instance form does not, so the doubled walk is
  observed through the object it leaves behind rather than through a clock: the
  ratio between one walk and two is small enough to move under load.
* `patch` building a mock is counted by substituting `MagicMock` in the
  `unittest.mock` namespace. The substitution is asserted to have been reached
  on the run that does build one, so the zero on the `new=` run is a saving
  rather than a counter that never ran.
* Cleanup ordering is asserted on interleaved sync and async registrations, so
  two separate stacks drained one after the other would fail whichever went
  first. A test registering one of each cannot tell those apart.
* `patch.dict` copies the whole dictionary. The ratio is taken over a 1,000x
  size step between two dictionaries patched with the same single key, so the
  term being measured is the dictionary's size and nothing else.
* `ThreadingMock` keeps one event per argument signature. The two runs make the
  same number of calls and differ only in whether the arguments repeat, which
  isolates the signature count from the call count; the assertion is on the
  ratio between them rather than on either one's duration. Every wait in these
  tests is bounded through the constructor, because the default blocks forever
  and a `timeout` keyword passed to `wait_until_any_call_with` would join the
  signature being waited for instead - which a test of its own pins.
* Version boundaries are asserted in both directions where a name appeared
  inside the supported range - `enterContext` at 3.11, `addDuration` and
  `collectedDurations` at 3.12, `ThreadingMock` and `loop_factory` at 3.13, and
  the `assertHasAttr`, `assertIsSubclass` and `assertStartsWith` families at
  3.14 - so the release that moves one fails here.
* Dimensions these tests do *not* vary: the element type in every timing test,
  which is a small int or a one-element list throughout; the number of keyword
  arguments in any mock call, which is zero or one; the traceback depth behind a
  recorded failure; the number of handlers already on a logger under
  `assertLogs`; and the width of a mock tree in the depth tests, which is always
  a single chain.

Claims execution cannot settle here, and why:

* That `difflib` sets the upper bound on a failed sequence comparison and that
  it is quadratic in the worst case. The bound belongs to `difflib`, which has
  its own page; a test here would pin this page's rows to another module's
  implementation, and the inputs that reach the worst case are a property of
  that algorithm rather than of `unittest`.
* The cost of an event loop per `IsolatedAsyncioTestCase` test. That one loop is
  created and closed per test *is* asserted, by identity of the running loop
  across two tests. How much it costs is platform- and selector-dependent and no
  bound on the page states it.
* `installHandler`, `removeHandler`, `registerResult` and `removeResult`. The
  handler is process-global and idempotent, and installing it would change how
  the rest of this suite responds to an interrupt. `registerResult` is exercised
  through the weak-keyed map's observable behaviour instead, without installing
  anything.
* Whether a namespace package may be a discovery root across the whole range.
  A real namespace package is discovered from in a subprocess, so the running
  version's answer is asserted either way - refused through 3.13, accepted from
  3.14 - but the page's statement is about the set of versions, which one
  interpreter cannot show. CI runs the matrix, which is where the other four are
  held to it.
* `TestProgram` exit codes. `main()` exits the process by default, and the
  conditions moved in a patch release within the supported range, so a test here
  would pin a boundary the page does not state.
"""

import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import types
import unittest
import unittest.mock
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "unittest.md"

EXPECTED_BLOCKS = 7


def api(module: Any, name: str) -> Any:
    """A unittest name typeshed does not offer at the 3.10 floor pyright checks."""
    return getattr(module, name)


def internal(obj: Any, name: str) -> Any:
    """A private attribute a row is asserted through, such as a suite's cleanup flag."""
    return getattr(obj, name)


def timed(call: Any, repeats: int = 3) -> float:
    """The fastest of a few runs, which drops a scheduler hiccup."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        best = min(best, time.perf_counter() - start)
    return best


def failure_message(call: Any) -> str:
    case = unittest.TestCase()
    try:
        call(case)
    except AssertionError as error:
        return str(error)
    raise AssertionError("the assertion under test passed")


class TestEqualityDispatchIsExactType:
    """assertEqual picks a type-specific function only for the exact type."""

    def test_a_list_gets_the_sequence_comparison(self) -> None:
        picked = unittest.TestCase()._getAssertEqualityFunc([1], [2])

        assert picked.__name__ == "assertListEqual"

    def test_a_list_subclass_falls_back_to_plain_equality(self) -> None:
        class Derived(list):  # noqa: FURB189 - the subclass is the subject
            pass

        picked = unittest.TestCase()._getAssertEqualityFunc(Derived([1]), Derived([2]))

        assert picked.__name__ == "_baseAssertEqual"

    def test_two_different_types_fall_back_even_when_both_are_registered(self) -> None:
        picked = unittest.TestCase()._getAssertEqualityFunc([1], (1,))

        assert picked.__name__ == "_baseAssertEqual"

    def test_the_fallback_produces_no_diff_where_the_list_does(self) -> None:
        class Derived(list):  # noqa: FURB189 - the subclass is the subject
            pass

        listed = failure_message(lambda case: case.assertEqual([1, 2], [1, 3]))
        derived = failure_message(lambda case: case.assertEqual(Derived([1, 2]), Derived([1, 3])))

        assert "First differing element" in listed
        assert "First differing element" not in derived

    def test_registering_a_type_changes_that_instance_only(self) -> None:
        class Box:
            def __init__(self, value: int) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Box) and other.value == self.value

            def __hash__(self) -> int:
                return hash(self.value)

        reached: list[str] = []

        def compare(first: Box, second: Box, msg: object = None) -> None:
            reached.append("called")
            if first != second:
                raise AssertionError("boxes differ")

        registered = unittest.TestCase()
        registered.addTypeEqualityFunc(Box, compare)
        registered.assertEqual(Box(1), Box(1))

        assert reached == ["called"]
        assert unittest.TestCase()._getAssertEqualityFunc(Box(1), Box(1)).__name__ != "compare"


class TestTheDiffIsBuiltBeforeItIsTruncated:
    """maxDiff shortens the message; it does not skip the work."""

    def test_the_truncated_message_reports_the_full_diff_length(self) -> None:
        left = [str(index) for index in range(400)]
        right = [*left[:-1], "different"]

        full = unittest.TestCase()
        full.maxDiff = None
        untruncated = failure_message(lambda case: full.assertListEqual(left, right))

        short = unittest.TestCase()
        short.maxDiff = 40
        truncated = failure_message(lambda case: short.assertListEqual(left, right))

        stated = re.search(r"Diff is (\d+) characters long", truncated)
        assert stated is not None, truncated
        # Both messages are the same explanation followed by either the whole
        # diff or a note naming its length. Cutting the note off the short one
        # leaves that explanation, and what the long one adds to it is the diff.
        explanation = truncated.split("\nDiff is")[0]
        assert untruncated.startswith(explanation)
        assert int(stated.group(1)) == len(untruncated) - len(explanation)

    def test_a_multiline_string_gives_up_on_the_diff_past_its_threshold(self) -> None:
        threshold = internal(unittest.TestCase, "_diffThreshold")
        under = "a" * (threshold // 2)
        over = "a" * (threshold + 1)

        case = unittest.TestCase()
        case.maxDiff = None
        small = failure_message(lambda _: case.assertMultiLineEqual(under, under + "b"))
        large = failure_message(lambda _: case.assertMultiLineEqual(over, over + "b"))

        assert "- " in small
        # Past the threshold no diff is produced at all, so there is nothing for
        # maxDiff to shorten and no note naming a length either.
        assert "- " not in large
        assert "Diff is" not in large

    def test_a_set_failure_is_not_truncated_by_max_diff(self) -> None:
        case = unittest.TestCase()
        case.maxDiff = 10
        message = failure_message(lambda _: case.assertSetEqual(set(range(60)), set()))

        # Every other comparison would have replaced the body with a note naming
        # the diff's length; this one renders all sixty elements regardless.
        assert "Diff is" not in message
        assert "59" in message

    def test_a_membership_failure_renders_the_whole_container(self) -> None:
        message = failure_message(lambda case: case.assertIn(-1, list(range(300))))

        assert "299" in message


class TestShortCircuitsAreNotUniform:
    """A sequence compares with == first; a set never does."""

    def test_an_equal_sequence_is_compared_once(self) -> None:
        class CountingList(list):  # noqa: FURB189 - the counter is the subject
            calls = 0

            def __eq__(self, other: object) -> bool:
                type(self).calls += 1
                return list.__eq__(self, other)

            __hash__ = None  # type: ignore[assignment]

        left, right = CountingList([1, 2, 3]), CountingList([1, 2, 3])
        unittest.TestCase().assertSequenceEqual(left, right)

        assert CountingList.calls == 1

    def test_an_equal_set_is_never_compared(self) -> None:
        class CountingSet(set):
            calls = 0

            def __eq__(self, other: object) -> bool:
                type(self).calls += 1
                return set.__eq__(self, other)

            __hash__ = None  # type: ignore[assignment]

        left, right = CountingSet({1, 2, 3}), CountingSet({1, 2, 3})
        unittest.TestCase().assertSetEqual(left, right)

        assert CountingSet.calls == 0

    def test_almost_equal_returns_before_subtracting_and_its_negation_does_not(self) -> None:
        class NoSubtraction:
            def __eq__(self, other: object) -> bool:
                return other is self

            def __hash__(self) -> int:
                return 0

        value: Any = NoSubtraction()
        unittest.TestCase().assertAlmostEqual(value, value)

        with pytest.raises(TypeError):
            unittest.TestCase().assertNotAlmostEqual(value, value)


class TestCountEqualNeedsHashableElements:
    """The counting path is linear; the fallback scans pairwise even when equal.

    That scan marks off each value's duplicates, so its cost follows the distinct
    values rather than the length: mostly distinct values make it quadratic, and
    a handful repeated many times keeps it near linear.
    """

    def test_the_hashable_path_ignores_order(self) -> None:
        items = [(index, index) for index in range(50)]
        unittest.TestCase().assertCountEqual(items, list(reversed(items)))

    def test_the_unhashable_path_ignores_order_too(self) -> None:
        items = [[index] for index in range(50)]
        unittest.TestCase().assertCountEqual(items, list(reversed(items)))

    def test_equal_unhashable_input_costs_far_more_than_equal_hashable_input(self) -> None:
        case = unittest.TestCase()
        size = 700
        hashable = [(index, index) for index in range(size)]
        unhashable = [[index] for index in range(size)]

        cheap = timed(lambda: case.assertCountEqual(hashable, list(hashable)))
        dear = timed(lambda: case.assertCountEqual(unhashable, list(unhashable)))

        assert dear > cheap * 20, f"hashable {cheap:.6f}s, unhashable {dear:.6f}s"

    def test_the_fallback_is_linear_when_every_element_is_the_same_value(self) -> None:
        # The pairwise scan marks a value's duplicates as it goes, so its cost
        # follows the distinct values rather than the length. Without this the
        # quadratic row would read as a claim about n.
        case = unittest.TestCase()

        def cost(size: int) -> float:
            same = [[0]] * size
            return timed(lambda: case.assertCountEqual(same, list(same)))

        assert cost(2000) < cost(500) * 8, "one repeated value did not stay near linear"

    def test_the_fallback_makes_quadratically_many_comparisons(self) -> None:
        """Counting separates the two paths with no clock and no tolerance."""

        class Counted:
            comparisons = 0

            def __init__(self, value: int) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                type(self).comparisons += 1
                return isinstance(other, Counted) and other.value == self.value

            # No __hash__, so a container of these takes the fallback.
            __hash__ = None  # type: ignore[assignment]

        def comparisons(size: int) -> int:
            Counted.comparisons = 0
            items = [Counted(index) for index in range(size)]
            unittest.TestCase().assertCountEqual(items, list(items))
            return Counted.comparisons

        small, large = comparisons(40), comparisons(160)

        # A 4x size step costs about 16x on a pairwise scan and 4x on anything
        # linear, so 8x separates them with room on both sides.
        assert large > small * 8, f"40 elements {small}, 160 elements {large}"

    def test_the_fallback_grows_faster_than_the_counting_path(self) -> None:
        case = unittest.TestCase()

        def cost(size: int, hashable: bool) -> float:
            items = [(i, i) for i in range(size)] if hashable else [[i] for i in range(size)]
            return timed(lambda: case.assertCountEqual(items, list(items)))

        linear = cost(1200, True) / max(cost(300, True), 1e-9)
        quadratic = cost(1200, False) / max(cost(300, False), 1e-9)

        assert quadratic > 8, f"a 4x step cost {quadratic:.1f}x on the fallback"
        assert quadratic > linear * 2, f"linear {linear:.1f}x, fallback {quadratic:.1f}x"

    def test_one_unhashable_element_sends_both_arguments_down_the_fallback(self) -> None:
        class Counted:
            """Hashable and countable, so only the fallback compares it."""

            comparisons = 0

            def __init__(self, value: int) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                type(self).comparisons += 1
                return isinstance(other, Counted) and other.value == self.value

            def __hash__(self) -> int:
                return hash(self.value)

        countable = [Counted(index) for index in range(20)]
        unittest.TestCase().assertCountEqual(countable, list(countable))
        on_the_counting_path = Counted.comparisons

        # One element that cannot hash sends the whole comparison, including
        # every hashable element beside it, down the pairwise scan.
        Counted.comparisons = 0
        mixed = [*countable, [0]]
        unittest.TestCase().assertCountEqual(mixed, list(mixed))

        assert on_the_counting_path == 0
        assert Counted.comparisons > 0


class TestContextManagerAssertions:
    """assertWarns scans sys.modules; assertRaises clears frames."""

    def _planted(self) -> types.ModuleType:
        module = types.ModuleType("_unittest_page_probe")
        module.__warningregistry__ = {("noted", UserWarning, 1): True}  # type: ignore[attr-defined]
        return module

    def test_assert_warns_empties_every_module_registry(self) -> None:
        module = self._planted()
        sys.modules[module.__name__] = module
        try:
            with unittest.TestCase().assertWarns(UserWarning):
                import warnings

                warnings.warn("noted", UserWarning, stacklevel=1)
        finally:
            del sys.modules[module.__name__]

        assert module.__warningregistry__ == {}

    def test_assert_raises_leaves_every_module_registry_alone(self) -> None:
        module = self._planted()
        sys.modules[module.__name__] = module
        try:
            with unittest.TestCase().assertRaises(ValueError):
                int("not a number")
        finally:
            del sys.modules[module.__name__]

        assert module.__warningregistry__ != {}

    def test_a_chained_exceptions_traceback_is_left_alone(self) -> None:
        import gc
        import weakref

        class Tracked:
            pass

        witness: list[Any] = []

        def inner() -> None:
            local = Tracked()
            witness.append(weakref.ref(local))
            raise KeyError("documented")

        with unittest.TestCase().assertRaises(ValueError) as caught:
            try:
                inner()
            except KeyError as cause:
                raise ValueError("documented") from cause
        gc.collect()

        # Only the exception's own traceback is cleared, so the cause keeps
        # both its traceback and the locals those frames held.
        cause = caught.exception.__cause__
        assert cause is not None
        assert cause.__traceback__ is not None
        assert witness[0]() is not None

    def test_assert_raises_stores_the_exception_without_its_traceback(self) -> None:
        with unittest.TestCase().assertRaises(ValueError) as caught:
            int("not a number")

        assert caught.exception.__traceback__ is None

    def test_assert_raises_clears_the_locals_of_the_raising_frame(self) -> None:
        # The traceback is kept alive on both sides, so an ordinary drop of the
        # exception cannot be what releases the local. The control shows the
        # local surviving under a plain try/except that holds the same
        # traceback; only the context manager's frame clearing releases it.
        import gc
        import weakref

        class Tracked:
            pass

        def raiser(witness: list[Any]) -> None:
            local = Tracked()
            witness.append(weakref.ref(local))
            raise ValueError("documented")

        control: list[Any] = []
        try:
            raiser(control)
        except ValueError as error:
            control.append(error.__traceback__)
        gc.collect()

        under_test: list[Any] = []
        with unittest.TestCase().assertRaises(ValueError):
            try:
                raiser(under_test)
            except ValueError as error:
                under_test.append(error.__traceback__)
                raise
        gc.collect()

        assert control[1] is not None
        assert control[0]() is not None, "the control released it without any clearing"
        assert under_test[1] is not None
        assert under_test[0]() is None

    def test_assert_logs_formats_every_record_as_it_arrives(self) -> None:
        import logging

        formatted: list[str] = []

        class CountingFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                formatted.append(record.getMessage())
                return super().format(record)

        logger = logging.getLogger("unittest_page_probe.eager")
        with unittest.TestCase().assertLogs(logger, "INFO") as captured:
            handler = logger.handlers[0]
            handler.setFormatter(CountingFormatter("%(message)s"))
            for index in range(5):
                logger.info("record %d", index)
            inside = list(formatted)

        assert inside == [f"record {index}" for index in range(5)]
        assert len(captured.records) == 5
        assert captured.output == [f"record {index}" for index in range(5)]

    def test_assert_logs_invalidates_every_logger_level_cache(self) -> None:
        import logging

        watched = [logging.getLogger(f"unittest_page_probe.cache.{index}") for index in range(5)]
        for logger in watched:
            logger.isEnabledFor(logging.INFO)
        assert all(internal(logger, "_cache") for logger in watched)

        subject = logging.getLogger("unittest_page_probe.cache.subject")
        with unittest.TestCase().assertLogs(subject, "INFO"):
            inside = [bool(internal(logger, "_cache")) for logger in watched]
            subject.info("record")
            # Refill them so the exit invalidation has something to clear.
            for logger in watched:
                logger.isEnabledFor(logging.INFO)
            refilled = all(internal(logger, "_cache") for logger in watched)

        assert inside == [False] * 5
        assert refilled
        assert [bool(internal(logger, "_cache")) for logger in watched] == [False] * 5

    def test_assert_no_logs_carries_the_formatted_record_into_its_failure(self) -> None:
        import logging

        formatted: list[str] = []

        class CountingFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                formatted.append(record.getMessage())
                return super().format(record)

        logger = logging.getLogger("unittest_page_probe.nologs")
        inside: list[str] = []
        with pytest.raises(AssertionError) as raised:  # noqa: PT012 - the block is the subject
            with unittest.TestCase().assertNoLogs(logger, "INFO"):
                logger.handlers[0].setFormatter(CountingFormatter("%(message)s"))
                logger.info("unexpected %s", "record")
                # Formatting has already happened, before the block ends and
                # before anything decides the assertion failed.
                inside.extend(formatted)

        assert inside == ["unexpected record"]
        assert "unexpected record" in str(raised.value)


class TestCleanupsRunLastInFirstOut:
    """Cleanups unwind in reverse and survive a failing setUp."""

    def test_cleanups_unwind_in_reverse(self) -> None:
        order: list[int] = []

        class Case(unittest.TestCase):
            def test_x(self) -> None:
                for index in range(3):
                    self.addCleanup(order.append, index)

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )

        assert order == [2, 1, 0]

    def test_a_cleanup_runs_even_when_set_up_raised(self) -> None:
        order: list[str] = []

        class Case(unittest.TestCase):
            def setUp(self) -> None:
                self.addCleanup(order.append, "cleanup")
                raise RuntimeError("setUp failed")

            def tearDown(self) -> None:
                order.append("tearDown")

            def test_x(self) -> None:
                order.append("body")

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )

        assert order == ["cleanup"]

    def test_a_failing_cleanup_does_not_stop_the_others(self) -> None:
        order: list[str] = []

        def boom() -> None:
            order.append("boom")
            raise RuntimeError("cleanup failed")

        class Case(unittest.TestCase):
            def test_x(self) -> None:
                self.addCleanup(order.append, "first")
                self.addCleanup(boom)

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )

        assert order == ["boom", "first"]
        assert len(result.errors) == 1

    def test_debug_abandons_the_remaining_cleanups_where_run_does_not(self) -> None:
        under_debug: list[str] = []
        under_run: list[str] = []

        def case_for(order: list[str]) -> type[unittest.TestCase]:
            class Case(unittest.TestCase):
                def test_x(self) -> None:
                    self.addCleanup(order.append, "second")
                    self.addCleanup(lambda: (order.append("first"), 1 / 0))

            return Case

        with pytest.raises(ZeroDivisionError):
            case_for(under_debug)("test_x").debug()

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([case_for(under_run)("test_x")])
        )

        assert under_debug == ["first"]
        assert under_run == ["first", "second"]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="doModuleCleanups is exported from 3.11")
    def test_module_cleanups_all_run_and_the_first_failure_is_the_one_raised(self) -> None:
        reached: list[str] = []

        def failing(name: str) -> None:
            reached.append(name)
            raise RuntimeError(name)

        unittest.addModuleCleanup(failing, "registered first")
        unittest.addModuleCleanup(failing, "registered second")

        with pytest.raises(RuntimeError) as raised:
            api(unittest, "doModuleCleanups")()

        assert reached == ["registered second", "registered first"]
        assert str(raised.value) == "registered second"


class TestSkippingStopsBeforeSetUp:
    """A skipped test is loaded and instantiated but its fixtures never run."""

    def test_a_skipped_test_never_reaches_set_up(self) -> None:
        reached: list[str] = []

        class Case(unittest.TestCase):
            def setUp(self) -> None:
                reached.append("setUp")

            @unittest.skip("documented")
            def test_x(self) -> None:
                reached.append("body")

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )

        assert reached == []
        assert result.testsRun == 1
        assert result.skipped[0][1] == "documented"

    def test_a_skipped_class_passes_its_flag_to_a_subclass(self) -> None:
        @unittest.skip("documented")
        class Parent(unittest.TestCase):
            def test_x(self) -> None:
                raise AssertionError("ran")

        class Child(Parent):
            pass

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Child("test_x")])
        )

        assert len(result.skipped) == 1

    def test_skip_unless_decides_at_import_and_still_decides(self) -> None:
        ran: list[str] = []

        class Case(unittest.TestCase):
            @unittest.skipUnless(True, "documented")
            def test_kept(self) -> None:
                ran.append("kept")

            @unittest.skipUnless(False, "documented")
            def test_dropped(self) -> None:
                ran.append("dropped")

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_kept"), Case("test_dropped")])
        )

        # A false condition really skips, so the decorator is not an identity.
        assert ran == ["kept"]
        assert len(result.skipped) == 1

    def test_the_skip_condition_is_evaluated_once_at_import(self) -> None:
        evaluated: list[str] = []

        def condition() -> bool:
            evaluated.append("checked")
            return False

        class Case(unittest.TestCase):
            @unittest.skipUnless(condition(), "documented")
            def test_x(self) -> None:
                raise AssertionError("ran")

        assert evaluated == ["checked"]
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")] * 3)
        )

        # Three runs of a skipped test, and the condition was never consulted
        # again: it was decided when the class was defined.
        assert len(result.skipped) == 3
        assert evaluated == ["checked"]


class TestClassFixturesFollowSuiteOrder:
    """setUpClass runs per contiguous group, not per class."""

    @staticmethod
    def _classes(order: list[str]) -> tuple[type[unittest.TestCase], type[unittest.TestCase]]:
        class First(unittest.TestCase):
            @classmethod
            def setUpClass(cls) -> None:
                order.append("First.setUpClass")

            @classmethod
            def tearDownClass(cls) -> None:
                order.append("First.tearDownClass")

            def test_a(self) -> None:
                pass

            def test_b(self) -> None:
                pass

        class Second(unittest.TestCase):
            @classmethod
            def setUpClass(cls) -> None:
                order.append("Second.setUpClass")

            def test_a(self) -> None:
                pass

        return First, Second

    def test_a_grouped_suite_sets_up_each_class_once(self) -> None:
        order: list[str] = []
        first, second = self._classes(order)
        suite = unittest.TestSuite([first("test_a"), first("test_b"), second("test_a")])

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        assert order.count("First.setUpClass") == 1
        assert order.count("Second.setUpClass") == 1

    def test_an_interleaved_suite_sets_the_first_class_up_twice(self) -> None:
        order: list[str] = []
        first, second = self._classes(order)
        suite = unittest.TestSuite([first("test_a"), second("test_a"), first("test_b")])

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        assert order.count("First.setUpClass") == 2
        assert order.count("First.tearDownClass") == 2

    def test_the_loader_groups_a_class_together(self) -> None:
        order: list[str] = []
        first, _ = self._classes(order)

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestLoader().loadTestsFromTestCase(first)
        )

        assert order.count("First.setUpClass") == 1


class TestASuiteReleasesItsTestsAsItRuns:
    """The suite drops each reference, which makes it single-use."""

    @staticmethod
    def _suite() -> unittest.TestSuite:
        class Case(unittest.TestCase):
            def test_a(self) -> None:
                pass

            def test_b(self) -> None:
                pass

        return unittest.TestSuite([Case("test_a"), Case("test_b")])

    def test_the_entries_become_none_after_the_run(self) -> None:
        suite = self._suite()
        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        assert list(suite) == [None, None]

    def test_the_count_survives_the_release(self) -> None:
        suite = self._suite()
        before = suite.countTestCases()
        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        assert before == 2
        assert suite.countTestCases() == 2

    def test_running_the_same_suite_twice_raises(self) -> None:
        suite = self._suite()
        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        with pytest.raises(TypeError):
            unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

    def test_disabling_the_release_makes_the_suite_reusable(self) -> None:
        suite = self._suite()
        setattr(suite, "_cleanup", False)  # noqa: B010 - pyright has no stub for it
        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        second = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        assert second.testsRun == 2

    def test_a_nested_suite_is_counted_once_per_appearance(self) -> None:
        inner = self._suite()
        outer = unittest.TestSuite([inner, inner])

        assert outer.countTestCases() == 4

    def test_base_test_suite_runs_no_class_fixtures(self) -> None:
        order: list[str] = []

        class Case(unittest.TestCase):
            @classmethod
            def setUpClass(cls) -> None:
                order.append("setUpClass")

            def test_a(self) -> None:
                pass

        suite = unittest.suite.BaseTestSuite([Case("test_a")])
        suite.run(unittest.TestResult())

        assert order == []

    def test_base_test_suite_releases_its_tests_like_the_other_one(self) -> None:
        # Wrapping the other suite flattens its two cases into this one.
        suite = unittest.suite.BaseTestSuite(self._suite())
        assert suite.countTestCases() == 2
        suite.run(unittest.TestResult())

        # Dropping fixture handling does not bring back a second run: the
        # release happens in the shared code both classes use.
        assert list(suite) == [None, None]
        with pytest.raises(TypeError):
            suite.run(unittest.TestResult())


class TestTheLoaderScansEveryName:
    """getTestCaseNames filters dir(), so non-test attributes cost too."""

    @staticmethod
    def _built(tests: int, others: int) -> type[unittest.TestCase]:
        namespace: dict[str, Any] = {f"test_{index}": (lambda self: None) for index in range(tests)}
        namespace.update({f"helper_{index}": (lambda self: None) for index in range(others)})
        return type("Built", (unittest.TestCase,), namespace)

    def test_only_the_prefixed_names_are_returned(self) -> None:
        names = unittest.TestLoader().getTestCaseNames(self._built(5, 40))

        assert names == [f"test_{index}" for index in range(5)]

    def test_the_names_come_back_sorted(self) -> None:
        names = unittest.TestLoader().getTestCaseNames(self._built(12, 0))

        assert names == sorted(names)

    def test_a_wide_class_costs_more_to_scan_than_a_narrow_one(self) -> None:
        loader = unittest.TestLoader()
        narrow = self._built(50, 0)
        wide = self._built(50, 16000)

        cheap = timed(lambda: loader.getTestCaseNames(narrow))
        dear = timed(lambda: loader.getTestCaseNames(wide))

        assert len(loader.getTestCaseNames(wide)) == 50
        assert dear > cheap * 5, f"narrow {cheap:.6f}s, wide {dear:.6f}s"

    def test_one_case_is_built_per_matching_name(self) -> None:
        suite = unittest.TestLoader().loadTestsFromTestCase(self._built(7, 20))

        assert suite.countTestCases() == 7
        assert len({id(test) for test in suite}) == 7

    def test_a_class_with_no_matching_names_yields_an_empty_suite(self) -> None:
        class Empty(unittest.TestCase):
            pass

        assert list(unittest.TestLoader().loadTestsFromTestCase(Empty)) == []

    def test_a_class_with_no_matching_names_but_a_run_test_yields_that(self) -> None:
        class Legacy(unittest.TestCase):
            def runTest(self) -> None:
                pass

        loaded = list(unittest.TestLoader().loadTestsFromTestCase(Legacy))

        assert [internal(test, "_testMethodName") for test in loaded] == ["runTest"]

    def test_a_suite_refuses_a_class_and_a_non_callable(self) -> None:
        class Case(unittest.TestCase):
            def test_x(self) -> None:
                pass

        suite = unittest.TestSuite()
        with pytest.raises(TypeError):
            suite.addTest(Case)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            suite.addTest(42)  # type: ignore[arg-type]

    def test_an_empty_name_pattern_list_matches_nothing(self) -> None:
        loader = unittest.TestLoader()
        loader.testNamePatterns = []

        assert loader.getTestCaseNames(self._built(5, 0)) == []

    def test_an_unimportable_name_becomes_a_failing_test_with_a_traceback(self) -> None:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName("no_such_module_for_the_unittest_page.deeper.deepest")

        assert suite.countTestCases() == 1
        assert loader.errors
        # Typeshed types `errors` as exception classes; it holds message strings.
        assert "Traceback" in internal(loader, "errors")[0]


class TestDiscoveryDescendsOnlyIntoPackages:
    """Descent into a subdirectory needs a package; the start directory does not."""

    BODY = "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        pass\n"

    def test_a_plain_directory_is_skipped(self, tmp_path: pathlib.Path) -> None:
        # Each test names its package differently: discovery imports the
        # package, and a name already in sys.modules would not be imported
        # again, so a shared name would make a later test pass vacuously.
        (tmp_path / "pkg_skipped").mkdir()
        (tmp_path / "pkg_skipped" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "pkg_skipped" / "test_found.py").write_text(self.BODY, encoding="utf-8")
        (tmp_path / "plain").mkdir()
        (tmp_path / "plain" / "test_missed.py").write_text(self.BODY, encoding="utf-8")

        suite = unittest.TestLoader().discover(str(tmp_path))

        assert suite.countTestCases() == 1

    def test_a_file_directly_in_the_start_directory_is_found(self, tmp_path: pathlib.Path) -> None:
        # The start directory is read whatever it is; only going deeper needs a
        # package, which is why the rule is about descent and not about roots.
        (tmp_path / "test_at_the_root.py").write_text(self.BODY, encoding="utf-8")
        (tmp_path / "under").mkdir()
        (tmp_path / "under" / "test_one_level_down.py").write_text(self.BODY, encoding="utf-8")

        suite = unittest.TestLoader().discover(str(tmp_path))

        assert suite.countTestCases() == 1

    def test_a_package_init_is_imported_though_it_cannot_match_the_pattern(
        self, tmp_path: pathlib.Path
    ) -> None:
        marker = tmp_path / "imported.txt"
        (tmp_path / "pkg_imported").mkdir()
        (tmp_path / "pkg_imported" / "__init__.py").write_text(
            f"import pathlib\npathlib.Path({str(marker)!r}).write_text('yes')\n",
            encoding="utf-8",
        )

        unittest.TestLoader().discover(str(tmp_path), pattern="test*.py")

        assert marker.is_file()

    def test_a_file_whose_name_misses_the_pattern_is_not_imported(
        self, tmp_path: pathlib.Path
    ) -> None:
        marker = tmp_path / "imported.txt"
        (tmp_path / "pkg_unmatched").mkdir()
        (tmp_path / "pkg_unmatched" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "pkg_unmatched" / "helper.py").write_text(
            f"import pathlib\npathlib.Path({str(marker)!r}).write_text('yes')\n",
            encoding="utf-8",
        )

        unittest.TestLoader().discover(str(tmp_path), pattern="test*.py")

        assert not marker.exists()


class TestResultMemoryFollowsFailures:
    """A passing test stores only its duration; a failure stores a traceback."""

    @staticmethod
    def _run(count: int, failing: bool) -> unittest.TestResult:
        class Case(unittest.TestCase):
            def test_x(self) -> None:
                if failing:
                    raise AssertionError("documented failure")

        return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x") for _ in range(count)])
        )

    def test_a_passing_run_records_no_outcome_entries(self) -> None:
        result = self._run(20, failing=False)

        assert result.testsRun == 20
        assert (result.errors, result.failures, result.skipped) == ([], [], [])

    def test_a_failing_run_stores_one_formatted_traceback_each(self) -> None:
        result = self._run(6, failing=True)

        assert len(result.failures) == 6
        assert all("AssertionError" in text for _, text in result.failures)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="collectedDurations was added in 3.12")
    def test_durations_grow_with_a_fully_passing_run(self) -> None:
        result = self._run(20, failing=False)

        assert len(internal(result, "collectedDurations")) == 20

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="collectedDurations was added in 3.12")
    def test_a_decorated_skip_gets_no_duration_but_a_raised_one_does(self) -> None:
        class Case(unittest.TestCase):
            @unittest.skip("documented")
            def test_decorated_skip(self) -> None:
                pass

            def test_raised_skip(self) -> None:
                self.skipTest("documented")

            def test_passes(self) -> None:
                pass

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite(
                [Case("test_decorated_skip"), Case("test_raised_skip"), Case("test_passes")]
            )
        )
        timed_names = {name for name, _ in internal(result, "collectedDurations")}

        assert result.testsRun == 3
        assert len(result.skipped) == 2
        # The decorated skip returns before the timer starts; the raised one
        # does not, so two of the three tests are timed.
        assert len(timed_names) == 2
        assert not any("test_decorated_skip" in name for name in timed_names)

    def test_was_successful_ignores_skips_and_expected_failures(self) -> None:
        class Case(unittest.TestCase):
            @unittest.skip("documented")
            def test_skipped(self) -> None:
                pass

            @unittest.expectedFailure
            def test_expected(self) -> None:
                raise AssertionError("documented")

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_skipped"), Case("test_expected")])
        )

        assert result.wasSuccessful()
        assert len(result.skipped) == 1
        assert len(result.expectedFailures) == 1

    def test_failfast_stops_at_the_first_failure(self) -> None:
        run: list[str] = []

        class Case(unittest.TestCase):
            def test_a(self) -> None:
                run.append("a")
                raise AssertionError("documented")

            def test_b(self) -> None:
                run.append("b")

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0, failfast=True).run(
            unittest.TestSuite([Case("test_a"), Case("test_b")])
        )

        assert run == ["a"]
        assert result.shouldStop

    def test_buffered_output_reaches_the_stream_only_on_failure(self) -> None:
        class Case(unittest.TestCase):
            def test_quiet(self) -> None:
                print("from the passing test")

            def test_loud(self) -> None:
                print("from the failing test")
                raise AssertionError("documented")

        # The forwarding the row describes goes to the streams the run replaced,
        # not to the runner's report: a failure's traceback carries the captured
        # output into the report anyway, so reading the report proves nothing.
        real_out, real_err = io.StringIO(), io.StringIO()
        saved = (sys.stdout, sys.stderr)
        sys.stdout, sys.stderr = real_out, real_err
        try:
            unittest.TextTestRunner(stream=io.StringIO(), verbosity=0, buffer=True).run(
                unittest.TestSuite([Case("test_quiet"), Case("test_loud")])
            )
        finally:
            sys.stdout, sys.stderr = saved
        forwarded = real_out.getvalue()

        assert "from the failing test" in forwarded
        assert "from the passing test" not in forwarded

    def test_a_registered_result_is_not_kept_alive(self) -> None:
        import gc
        import weakref

        result = unittest.TestResult()
        unittest.registerResult(result)
        reference = weakref.ref(result)

        # Registration is confirmed first: without this the assertion below
        # would pass just as well if registerResult did nothing at all.
        assert unittest.removeResult(result) is True
        unittest.registerResult(result)

        del result
        gc.collect()

        assert reference() is None


class TestSubTestBuildsACasePerIteration:
    """Each subTest block is its own case, and passing ones are reported."""

    def test_a_failing_subtest_does_not_stop_the_loop(self) -> None:
        seen: list[int] = []

        class Case(unittest.TestCase):
            def test_x(self) -> None:
                for index in range(4):
                    with self.subTest(index=index):
                        seen.append(index)
                        if index == 1:
                            raise AssertionError("documented")

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )

        assert seen == [0, 1, 2, 3]
        assert len(result.failures) == 1
        assert result.testsRun == 1

    def test_the_result_is_told_about_passing_subtests_too(self) -> None:
        reported: list[object] = []

        class Recording(unittest.TestResult):
            def addSubTest(
                self, test: unittest.TestCase, subtest: unittest.TestCase, err: Any
            ) -> None:
                reported.append(err)
                super().addSubTest(test, subtest, err)

        class Case(unittest.TestCase):
            def test_x(self) -> None:
                for index in range(4):
                    with self.subTest(index=index):
                        pass

        unittest.TestSuite([Case("test_x")]).run(Recording())

        assert reported == [None] * 4

    def test_an_enclosing_subtests_parameters_survive_into_each_inner_one(self) -> None:
        class Case(unittest.TestCase):
            def test_x(self) -> None:
                with self.subTest(outer=1):
                    for inner in (2, 3):
                        with self.subTest(inner=inner):
                            raise AssertionError("documented")

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )
        described = [str(test) for test, _ in result.failures]

        # Two sibling inner blocks, and the enclosing parameter is still on
        # both: entering the second did not consume or replace it.
        assert len(described) == 2
        assert all("outer=1" in text for text in described)
        assert {"inner=2", "inner=3"} == {
            fragment
            for text in described
            for fragment in ("inner=2", "inner=3")
            if fragment in text
        }


class TestIsolatedAsyncioBuildsALoopPerTest:
    """Each async test runs on a loop of its own."""

    def test_two_tests_do_not_share_a_loop(self) -> None:
        import asyncio

        # The loops are held, not their ids: a released object's address can be
        # handed to the next one, which would make two loops look like one.
        seen: list[Any] = []

        class Case(unittest.IsolatedAsyncioTestCase):
            async def test_a(self) -> None:
                seen.append(asyncio.get_running_loop())

            async def test_b(self) -> None:
                seen.append(asyncio.get_running_loop())

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestLoader().loadTestsFromTestCase(Case)
        )

        assert len(seen) == 2
        assert seen[0] is not seen[1]
        assert all(loop.is_closed() for loop in seen)

    def test_async_cleanups_share_the_one_lifo_list(self) -> None:
        order: list[str] = []

        class Case(unittest.IsolatedAsyncioTestCase):
            async def test_x(self) -> None:
                async def later(label: str) -> None:
                    order.append(label)

                # Interleaved, so two separate stacks drained one after the
                # other could not produce this order whichever went first.
                self.addCleanup(order.append, "sync first")
                self.addAsyncCleanup(later, "async second")
                self.addCleanup(order.append, "sync third")

        unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestSuite([Case("test_x")])
        )

        assert order == ["sync third", "async second", "sync first"]

    def test_importing_unittest_does_not_import_asyncio(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", "import unittest, sys; print('asyncio' in sys.modules)"],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=True,
        )

        assert completed.stdout.strip() == "False"


class TestAMockCallReachesEveryAncestor:
    """One call appends one record to the mock and to each ancestor."""

    def test_every_ancestor_records_the_call(self) -> None:
        root = unittest.mock.Mock()
        root.service.client.session.get("/health")

        # Four ancestors stand above the leaf, and the row prices all of them.
        assert root.mock_calls == [unittest.mock.call.service.client.session.get("/health")]
        assert root.service.mock_calls == [unittest.mock.call.client.session.get("/health")]
        assert root.service.client.mock_calls == [unittest.mock.call.session.get("/health")]
        assert root.service.client.session.mock_calls == [unittest.mock.call.get("/health")]
        assert root.service.client.session.get.mock_calls == [unittest.mock.call("/health")]

    def test_the_records_are_never_trimmed(self) -> None:
        mock = unittest.mock.Mock()
        for index in range(200):
            mock(index)

        assert len(mock.call_args_list) == 200
        assert len(mock.mock_calls) == 200

    def test_reset_clears_the_records(self) -> None:
        mock = unittest.mock.Mock()
        mock.child(1)
        mock.reset_mock()

        assert mock.mock_calls == []
        assert mock.child.mock_calls == []

    def test_a_deep_call_costs_more_than_a_shallow_one(self) -> None:
        def per_call(depth: int) -> float:
            root = unittest.mock.Mock()
            node = root
            for _ in range(depth):
                node = node.link
            return timed(lambda: [node(1) for _ in range(500)])

        shallow = per_call(1)
        deep = per_call(32)

        assert deep > shallow * 5, f"depth 1 {shallow:.6f}s, depth 32 {deep:.6f}s"

    def test_a_child_is_built_once_and_cached(self) -> None:
        mock = unittest.mock.Mock()

        assert mock.child is mock.child
        assert "child" in mock._mock_children

    def test_an_attached_mock_is_wired_in_where_a_named_one_is_not(self) -> None:
        parent = unittest.mock.Mock()
        named = unittest.mock.Mock(name="named")
        parent.assigned = named
        named(1)

        assert parent.mock_calls == []

        attached = unittest.mock.Mock(name="attached")
        parent.attach_mock(attached, "attached")
        parent.attached(2)

        assert parent.mock_calls == [unittest.mock.call.attached(2)]


class TestMockAssertionsScanOrDoNot:
    """assert_called_with reads one call; assert_any_call rebuilds the list."""

    @staticmethod
    def _called(count: int) -> unittest.mock.Mock:
        mock = unittest.mock.Mock()
        for index in range(count):
            mock(index)
        return mock

    def test_assert_called_with_reads_only_the_last_call(self) -> None:
        mock = self._called(50)
        mock.assert_called_with(49)

        with pytest.raises(AssertionError):
            mock.assert_called_with(0)

    def test_assert_any_call_finds_an_earlier_one(self) -> None:
        self._called(50).assert_any_call(0)

    def test_the_last_call_check_does_not_grow_with_the_call_count(self) -> None:
        """Counted rather than timed: the recorded calls compare themselves."""

        class Counted:
            comparisons = 0

            def __init__(self, value: int) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                type(self).comparisons += 1
                return isinstance(other, Counted) and other.value == self.value

            def __hash__(self) -> int:
                return hash(self.value)

        def comparisons(count: int, scanning: bool) -> int:
            mock = unittest.mock.Mock()
            for index in range(count):
                mock(Counted(index))
            Counted.comparisons = 0
            if scanning:
                # The last recorded call, so the scan has to pass every
                # earlier one to reach it.
                mock.assert_any_call(Counted(count - 1))
            else:
                mock.assert_called_with(Counted(count - 1))
            return Counted.comparisons

        # The last-call check compares exactly one recorded call however many
        # there are. Asserting the value rather than the equality matters: two
        # zeroes would also be equal, and an assertion that compared nothing
        # would produce them.
        assert comparisons(50, scanning=False) == 1
        assert comparisons(400, scanning=False) == 1
        # The scanning check compares its way through all of them. Its list of
        # matchers is rebuilt in full either way, which is what the timing test
        # beside this one measures; this counts only the comparisons.
        assert comparisons(400, scanning=True) > comparisons(50, scanning=True) * 4

    def test_the_scanning_check_does_grow_with_the_call_count(self) -> None:
        small = self._called(500)
        large = self._called(8000)

        cheap = timed(lambda: small.assert_any_call(0))
        dear = timed(lambda: large.assert_any_call(0))

        assert dear > cheap * 5, f"500 calls {cheap:.6f}s, 8000 calls {dear:.6f}s"

    def test_assert_has_calls_wants_a_contiguous_run_without_any_order(self) -> None:
        mock = self._called(6)
        mock.assert_has_calls([unittest.mock.call(2), unittest.mock.call(3)])

        # Reversed fails because the order is wrong; 2 then 4 fails although the
        # order is right, because the run it looks for has to be contiguous.
        for wrong in (
            [unittest.mock.call(3), unittest.mock.call(2)],
            [unittest.mock.call(2), unittest.mock.call(4)],
        ):
            with pytest.raises(AssertionError):
                mock.assert_has_calls(wrong)
            mock.assert_has_calls(wrong, any_order=True)

    def test_any_matches_one_argument(self) -> None:
        mock = unittest.mock.Mock()
        mock("unpredictable", 2)
        mock.assert_called_with(unittest.mock.ANY, 2)

    def test_any_needs_the_left_side_only_against_a_refusing_operand(self) -> None:
        class Refuses:
            """Returns False rather than deferring, so reflection never runs."""

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Refuses)

            def __hash__(self) -> int:
                return 0

        # An ordinary operand defers, so either order matches.
        assert 1 == unittest.mock.ANY
        assert unittest.mock.ANY == 1

        # One that answers for itself only matches with ANY on the left.
        assert not (Refuses() == unittest.mock.ANY)
        assert unittest.mock.ANY == Refuses()

        # And that is the order the call comparison uses, which a refusing
        # argument is what shows: a string argument would match either way.
        mock = unittest.mock.Mock()
        mock(Refuses())
        mock.assert_called_with(unittest.mock.ANY)


class TestAutospecBuildsWhatSpecDescribes:
    """spec keeps names; autospec builds a mock and a signature per name."""

    class Service:
        def fetch(self, key: str, timeout: float = 1.0) -> None:
            raise NotImplementedError

        def store(self, key: str, value: str) -> None:
            raise NotImplementedError

    def test_a_spec_builds_no_children(self) -> None:
        mock = unittest.mock.Mock(spec=self.Service)

        assert mock._mock_children == {}

    def test_an_autospec_builds_a_child_per_method(self) -> None:
        mock = unittest.mock.create_autospec(self.Service, instance=True)
        children = internal(mock, "_mock_children")

        assert {"fetch", "store"} <= set(children)
        for name in ("fetch", "store"):
            child = children[name]
            # A built mock rather than a deferred placeholder, which is what
            # separates the two rows. How much each child carries with it moved
            # inside the supported range and is not something the page claims.
            assert api(unittest.mock, "_is_instance_mock")(child), name
            assert internal(child, "_spec_signature") is not None, name

    def test_only_the_autospec_checks_the_signature(self) -> None:
        loose = unittest.mock.Mock(spec=self.Service)
        loose.fetch("key", "extra", "arguments", "accepted")

        strict = unittest.mock.create_autospec(self.Service, instance=True)
        strict.fetch("key")
        with pytest.raises(TypeError):
            strict.fetch("key", "extra", "arguments", "rejected")

    def test_both_reject_a_name_the_target_does_not_have(self) -> None:
        for mock in (
            unittest.mock.Mock(spec=self.Service),
            unittest.mock.create_autospec(self.Service, instance=True),
            unittest.mock.Mock(spec=["fetch"]),
        ):
            with pytest.raises(AttributeError):
                _ = mock.absent

    def test_a_string_list_spec_builds_nothing_and_still_restricts(self) -> None:
        mock = unittest.mock.Mock(spec=["fetch"])

        assert mock._mock_children == {}
        mock.fetch("anything", "at", "all")
        with pytest.raises(AttributeError):
            _ = mock.store

    def test_a_string_list_spec_is_stored_as_given_where_an_object_is_scanned(self) -> None:
        # Timing these two apart is not stable across the supported range,
        # because the fixed cost of building a mock moved far more between
        # releases than either spec path did. What each path *stores* is the
        # claim, and it is exact: the list arrives as the name set, where the
        # object has to be listed first.
        names = ["fetch", "store"]

        assert unittest.mock.Mock(spec=names)._mock_methods == names
        assert unittest.mock.Mock(spec=self.Service)._mock_methods == dir(self.Service)

    def test_autospec_costs_more_than_spec_over_the_same_target(self) -> None:
        namespace = {f"method_{index}": (lambda self: None) for index in range(100)}
        wide = type("Wide", (), namespace)

        described = timed(lambda: unittest.mock.Mock(spec=wide))
        built = timed(lambda: unittest.mock.create_autospec(wide, instance=True))

        assert built > described * 5, f"spec {described:.6f}s, autospec {built:.6f}s"

    def test_a_spec_is_rechecked_on_every_attribute_access(self) -> None:
        narrow = unittest.mock.Mock(spec=["only"])
        wide = unittest.mock.Mock(spec=[f"filler_{index}" for index in range(4000)] + ["only"])
        narrow.only  # noqa: B018 - the first access builds the child that is then cached
        wide.only  # noqa: B018 - so both mocks reach the timing loop already warm

        cheap = timed(lambda: [narrow.only for _ in range(2000)])
        dear = timed(lambda: [wide.only for _ in range(2000)])

        assert dear > cheap * 10, f"1 name {cheap:.6f}s, 4001 names {dear:.6f}s"

    def test_autospecing_a_class_also_specs_what_calling_it_returns(self) -> None:
        namespace = {f"method_{index}": (lambda self: None) for index in range(100)}
        wide = type("Wide", (), namespace)

        from_class = unittest.mock.create_autospec(wide)
        from_instance = unittest.mock.create_autospec(wide, instance=True)

        assert callable(from_class)
        assert not callable(from_instance)
        # The second walk is visible in what it left behind: the object the
        # class mock returns when called has a child per method of its own.
        # Timing the two forms apart would be the weaker test, because the ratio
        # between one walk and two is small enough to move under load.
        returned = internal(from_class, "return_value")
        assert "method_0" in internal(returned, "_mock_children")
        # The instance form specs the same names without that second walk: what
        # its return value would be was never given a spec of its own.
        assert "method_0" in internal(from_instance, "_mock_children")
        assert "method_0" not in internal(internal(from_instance, "return_value"), "_mock_children")

    def test_sealing_refuses_a_new_attribute_and_keeps_the_old_ones(self) -> None:
        mock = unittest.mock.Mock()
        existing = mock.already_there
        unittest.mock.seal(mock)

        assert mock.already_there is existing
        with pytest.raises(AttributeError):
            _ = mock.brand_new


class TestPatchCostsFollowWhatItCopies:
    """patch.dict copies the dictionary; a decorator re-enters per call."""

    def test_patch_dict_restores_the_original(self) -> None:
        target = {"kept": 1}
        with unittest.mock.patch.dict(target, {"added": 2}):
            assert target == {"kept": 1, "added": 2}

        assert target == {"kept": 1}

    def test_patch_dict_drops_keys_the_body_added(self) -> None:
        target = {"kept": 1}
        with unittest.mock.patch.dict(target, {}):
            target["sneaked"] = 3

        assert target == {"kept": 1}

    def test_patch_dict_cost_follows_the_whole_dictionary(self) -> None:
        small = dict.fromkeys(range(100), 0)
        large = dict.fromkeys(range(100_000), 0)

        def enter(target: dict[int, int]) -> None:
            with unittest.mock.patch.dict(target, {-1: 1}):
                pass

        cheap = timed(lambda: enter(small))
        dear = timed(lambda: enter(large))

        assert dear > cheap * 20, f"100 entries {cheap:.6f}s, 100000 entries {dear:.6f}s"

    def test_a_decorator_enters_on_every_call(self) -> None:
        seen: list[Any] = []

        @unittest.mock.patch.object(TestPatchCostsFollowWhatItCopies, "MARKER", create=True)
        def decorated(mock: unittest.mock.Mock) -> None:
            seen.append(mock)

        decorated()
        decorated()

        # Both mocks are held, so this compares two live objects rather than two
        # addresses the allocator may have reused.
        assert len(seen) == 2
        assert seen[0] is not seen[1]

    def test_passing_new_skips_building_a_mock(self) -> None:
        built: list[int] = []
        real = unittest.mock.MagicMock

        class Counting(real):  # type: ignore[misc, valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                built.append(1)
                super().__init__(*args, **kwargs)

        target = types.SimpleNamespace(attr=1)
        unittest.mock.MagicMock = Counting  # type: ignore[misc]
        try:
            with unittest.mock.patch.object(target, "attr"):
                pass
            without_new = len(built)
            built.clear()
            with unittest.mock.patch.object(target, "attr", 5) as supplied:
                assert supplied == 5
                assert target.attr == 5
            with_new = len(built)
        finally:
            unittest.mock.MagicMock = real  # type: ignore[misc]

        # The substitution is asserted to have been reached before the zero is
        # believed: otherwise a counter that never ran would read as a saving.
        assert without_new > 0
        assert with_new == 0

    def test_stopall_unwinds_what_start_registered(self) -> None:
        target = types.SimpleNamespace(value=1)
        first = unittest.mock.patch.object(target, "value", 2)
        second = unittest.mock.patch.object(target, "value", 3)
        first.start()
        second.start()

        assert target.value == 3
        unittest.mock.patch.stopall()
        assert target.value == 1


class TestThreadingMockKeepsAnEventPerSignature:
    """Distinct arguments lengthen the scan every later call pays."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="ThreadingMock was added in 3.13")
    def test_distinct_arguments_cost_more_than_repeated_ones(self) -> None:
        count = 1500

        def drive(distinct: bool) -> float:
            mock = api(unittest.mock, "ThreadingMock")()
            return timed(
                lambda: [mock(index if distinct else 0) for index in range(count)], repeats=1
            )

        repeated = drive(distinct=False)
        varied = drive(distinct=True)

        assert varied > repeated * 3, f"repeated {repeated:.6f}s, distinct {varied:.6f}s"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="ThreadingMock was added in 3.13")
    def test_waiting_for_a_call_that_already_happened_does_not_block(self) -> None:
        # The timeout belongs on the constructor. `wait_until_any_call_with`
        # takes call arguments only, so a `timeout=` keyword there would become
        # part of the signature being waited for and never arrive.
        threading_mock = api(unittest.mock, "ThreadingMock")

        # An unsatisfied wait raises, so the satisfied ones below cannot be
        # read as passing because waiting stopped doing anything.
        never_called = threading_mock(timeout=0.2)
        with pytest.raises(AssertionError):
            never_called.wait_until_called()

        mock = threading_mock(timeout=5)
        mock(1)

        mock.wait_until_called()
        mock.wait_until_any_call_with(1)

        # The any-call event is never cleared, so a second wait is satisfied by
        # the same call rather than needing a new one.
        mock.wait_until_called()

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="ThreadingMock was added in 3.13")
    def test_a_wait_keyword_becomes_part_of_the_signature_waited_for(self) -> None:
        threading_mock = api(unittest.mock, "ThreadingMock")
        mock = threading_mock(timeout=0.2)
        mock(1)

        # `wait_until_any_call_with(1)` is satisfied; adding a keyword asks for a
        # call that never happened, so the wait runs out instead.
        mock.wait_until_any_call_with(1)
        with pytest.raises(AssertionError):
            mock.wait_until_any_call_with(1, timeout=5)


class TestMockOpenServesOneHandleLazily:
    """Every open rebuilds the stream and returns the same handle."""

    def test_every_open_returns_the_same_handle(self) -> None:
        opener = unittest.mock.mock_open(read_data="one\ntwo\n")

        assert opener() is opener()

    def test_readline_and_iteration_share_a_position(self) -> None:
        opener = unittest.mock.mock_open(read_data="one\ntwo\nthree\n")
        handle = opener()
        handle.readline()
        handle.readline()

        assert list(handle) == ["three\n"]

    def test_reopening_restarts_the_stream(self) -> None:
        opener = unittest.mock.mock_open(read_data="one\ntwo\n")

        assert opener().read() == "one\ntwo\n"
        assert opener().read() == "one\ntwo\n"

    def test_sentinels_are_created_once_and_kept(self) -> None:
        assert unittest.mock.sentinel.marker is unittest.mock.sentinel.marker
        assert unittest.mock.sentinel.marker is not unittest.mock.sentinel.other

    def test_a_property_mock_records_reads_and_writes(self) -> None:
        holder = unittest.mock.PropertyMock(return_value=7)

        class Target:
            value: Any = None

        Target.value = holder
        instance = Target()

        assert instance.value == 7
        instance.value = 9

        assert holder.mock_calls == [unittest.mock.call(), unittest.mock.call(9)]

    def test_an_async_mock_counts_calls_and_awaits_separately(self) -> None:
        import asyncio

        async def drive() -> None:
            mock = unittest.mock.AsyncMock()
            coroutine = mock(1)
            assert mock.call_count == 1
            assert mock.await_count == 0
            await coroutine
            assert mock.await_count == 1
            mock.assert_awaited_once_with(1)

        asyncio.run(drive())


class TestVersionBoundaries:
    """Names that appeared inside the supported range, asserted both ways."""

    def test_the_module_scoped_names_arrived_in_311(self) -> None:
        recent = sys.version_info >= (3, 11)
        assert hasattr(unittest.TestCase, "enterContext") is recent
        assert hasattr(unittest.TestCase, "enterClassContext") is recent
        assert hasattr(unittest, "enterModuleContext") is recent
        assert hasattr(unittest, "doModuleCleanups") is recent
        # addModuleCleanup predates them, so the boundary is the export of the
        # names beside it rather than module cleanups as a feature.
        assert hasattr(unittest, "addModuleCleanup")

    def test_durations_arrived_in_312(self) -> None:
        assert hasattr(unittest.TestResult, "addDuration") is (sys.version_info >= (3, 12))
        assert hasattr(unittest.TestResult(), "collectedDurations") is (sys.version_info >= (3, 12))

    def test_threading_mock_and_loop_factory_arrived_in_313(self) -> None:
        assert hasattr(unittest.mock, "ThreadingMock") is (sys.version_info >= (3, 13))
        assert hasattr(unittest.IsolatedAsyncioTestCase, "loop_factory") is (
            sys.version_info >= (3, 13)
        )

    def test_the_newest_assertion_families_arrived_in_314(self) -> None:
        recent = sys.version_info >= (3, 14)
        for name in (
            "assertHasAttr",
            "assertNotHasAttr",
            "assertIsSubclass",
            "assertNotIsSubclass",
            "assertStartsWith",
            "assertEndsWith",
            "assertNotStartsWith",
            "assertNotEndsWith",
        ):
            assert hasattr(unittest.TestCase, name) is recent, name

    def test_namespace_package_discovery_matches_this_version(self, tmp_path: pathlib.Path) -> None:
        # Driven through a real namespace package rather than through the
        # private parameter that implements it, and in a subprocess because it
        # puts a directory on sys.path and imports from it.
        supported = sys.version_info >= (3, 14)
        (tmp_path / "namespace_probe").mkdir()
        (tmp_path / "namespace_probe" / "test_inside.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n        pass\n",
            encoding="utf-8",
        )
        source = textwrap.dedent("""
            import sys, unittest
            sys.path.insert(0, sys.argv[1])
            try:
                print(unittest.TestLoader().discover("namespace_probe").countTestCases())
            except TypeError:
                print("refused")
        """)
        completed = subprocess.run(
            [sys.executable, "-c", source, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=True,
        )
        printed = completed.stdout.strip()

        assert printed in {"1", "refused"}, completed.stderr
        assert (printed == "1") is supported


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
    """Every block runs in its own process; what each one shows is checked here.

    A block's exit status only proves it did not raise. The blocks whose point is
    a number - the fixture order, the discovery count - have that number asserted
    below, and the one that drives a runner asserts `wasSuccessful()` itself,
    because a failing test inside a `TextTestRunner` does not fail the process.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        source = _blocks()[0][1]
        mutated = source.replace("import unittest", "import unittest_not_a_module", 1)

        assert mutated != source, "the mutation matched nothing"
        assert _run(mutated, tmp_path).returncode != 0

    def test_the_fixture_order_block_shows_the_extra_set_up(self, tmp_path: pathlib.Path) -> None:
        line, source = next((line, text) for line, text in _blocks() if "setUpClass" in text)
        result = _run(source, tmp_path)
        printed = result.stdout.strip().splitlines()

        assert result.returncode == 0, f"{PAGE.name}:{line}\n{result.stderr}"
        assert printed[0].count("setUpClass") == 2
        assert printed[1].count("setUpClass") == 3

    def test_the_discovery_block_finds_two_of_its_three_test_files(
        self, tmp_path: pathlib.Path
    ) -> None:
        line, source = next(
            (line, text) for line, text in _blocks() if "TemporaryDirectory" in text
        )
        result = _run(source, tmp_path)

        assert result.returncode == 0, f"{PAGE.name}:{line}\n{result.stderr}"
        assert result.stdout.strip() == "2"
