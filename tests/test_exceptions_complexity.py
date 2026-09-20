"""Tests for docs/builtins/exceptions.md.

The page prices an exception as an object that costs nothing to fill and
everything to carry: construction stores references, and the traceback grows
one entry per frame unwound. Almost all of that is settled by observation -
counting traceback entries, checking payload identity, counting the nodes a
group predicate visits, watching a weak reference die - so most of this file
needs no tolerance. Timing appears only where the cost has no observable
counterpart, and then across size steps far apart enough that the ratio
cannot be read two ways.

Measurement scope:

* Propagation is counted, not timed: `traceback.extract_tb()` returns d + 2
  entries for a raise d frames below the `try`, asserted at depths 0, 100 and
  400. A timing test backs the same term at depths 1 and 1024 with the plain
  recursive call subtracted from both, where 1024x the depth costs more than
  50x. The O(d) space term is a weak reference to a local of the frame that
  raised: it survives while the exception is held and dies after
  `with_traceback(None)` and a collection, and `except ... as name` is
  asserted to unbind the name at the end of the block. That call is timed at
  depths 1 and 5,000 *after the handler exits*, where dropping the last
  reference to a 5,000-entry traceback costs more than 100x, which is why the
  page prices it O(d) rather than O(1). Called from inside the handler the
  same measurement is flat on 3.10 and not on 3.11+, so the test takes the
  one position that holds across the supported range. A bare `raise` in a
  handler four frames deep is asserted to leave 6 entries where `raise error`
  leaves 7, which is the page's reason to prefer the bare form.
* An `except` tuple is asserted to reject a non-exception entry that sits
  *behind* a matching one, which is the whole of the "every class is checked"
  claim and needs no stopwatch. Clause order is asserted by which of two
  clauses wins for a subclass. The terms are then timed three ways: a
  2,001-class tuple with the match last costs more than 20x a 2-class one;
  a class 400 inheritance steps below `Exception` costs more than 8x one step;
  and, with the tuple held at 501 classes so only the depth moves, 400 steps
  still cost more than 8x one. That third measurement is what separates
  O(t*a) from O(t + a), which would leave it flat. All three put the matching
  class last, so they measure the worst case the page states; a match in the
  first position pays the ancestor scan once and is not measured here.
* Payload identity settles "references, not copies": `args[0] is message` for
  a one-megabyte string, the same for a 100,000-element tuple key that failed
  a lookup, and a traced peak under 1 KB for building an exception over a
  4 MB buffer - a bound on the allocation, not a claim of none.
* `bytes.decode()` is asserted to hand its exception an object that is equal
  to the input and not the input, against `str.encode()`, whose exception
  holds the original, and against `UnicodeDecodeError(...)` built directly,
  which references its buffer. The peak while a 4 MB decode fails exceeds
  4 MB; building the same exception directly stays under 1 KB. That
  asymmetry is asserted on every supported version rather than assumed. The
  decode measured fails at byte 0, so the peak is the copy of the whole
  buffer and not a scan of it.
* Every `errno` the page maps to a subclass is asserted to produce it,
  `filename` and `filename2` are asserted to stay out of `args`, and
  `winerror` is asserted present only on Windows. `characters_written` is
  asserted missing on a fresh `BlockingIOError` and settable afterwards.
  `socket.timeout` is asserted to be `TimeoutError` on every supported
  version and `asyncio.TimeoutError` only from 3.11, which is the boundary
  the page's two alias entries turn on.
* `ReferenceError` is asserted to come from a dead `weakref.proxy` and not
  from a dead `weakref.ref`, which returns `None` instead.
* `TabError` is asserted to come only from inconsistent tabs and spaces:
  uneven indentation raises `IndentationError` and is asserted *not* to be a
  `TabError`, which is the distinction a plain `IndentationError` example
  cannot make. `SyntaxError` positions are asserted on `lineno`, `offset`,
  `text` and `filename`; `end_offset` is asserted only to be at or after
  `offset`, because it moved by one between 3.10 and 3.14.
* `split()` and `subgroup()` are given a recording predicate and asserted to
  visit all five nodes of a three-leaf tree, the group itself included, in
  document order. All three - split, a matching subgroup and a subgroup that
  matches nothing - assert the exact call list, so a walk that skipped an
  interior node or visited one twice fails. A predicate that matches the root
  is asserted to visit that node alone and return the group unchanged, which
  is why the page prices the walks as O(n) worst case rather than always.
  `derive()` is asserted to drop the traceback, the `__context__`, an
  explicit `__cause__` and the notes that `split()` and `subgroup()` copy onto
  what they return; the copied note lists are asserted equal to their source's
  and not the same object, on a nested group as well as on the root. That p is
  paid per rebuilt group rather than once is timed by subtracting the unnoted
  cost from the noted one at 1 group and at 50: the 50-group note cost exceeds
  ten times the one-group note cost, where a single copy per walk would leave
  it flat. Construction is timed across
  100 and 100,000 *direct children*, where 1,000x costs more than 100x, and
  separately asserted flat when the children are two already-built subtrees
  of 10 and 100,000 leaves - which is the m term rather than n.
* `__cause__`, `__context__` and `__suppress_context__` are asserted for all
  three spellings - `from error`, no `from` at all, and `from None` - and a
  20-deep nest of raises inside handlers is asserted to leave 21 exceptions
  linked through `__context__`, which is the c term the page prices.
* `add_note()` is asserted to create `__notes__` on first call and to leave
  `args` alone; its O(1) is timed by appending to a one-note list and to one
  already holding 100,000 notes, where the second stays within 2x of the
  first. Both keep growing as they are timed, so each is an append to a list
  of at least the stated size, not exactly it.
* The hierarchy in the page's fenced tree is parsed and every parent/child
  edge checked against `__bases__`, and the tree is asserted to name every
  public exception class the running interpreter has, each exactly once. That
  is what keeps the tree from drifting as releases add classes. The set of
  classes outside `Exception` is asserted exhaustively against the
  interpreter, so `BaseExceptionGroup` joining them in 3.11 cannot be missed.
* Formatting is asserted to cost more than the display shows: a
  `RecursionError` yields over 200 `extract_tb()` entries and renders to
  fewer lines than it has frames, with the fold marker present, and
  `format_exception()` on a 2,000-frame traceback costs more than 20x one on
  a single frame. The extraction count bounds the frames present, not the
  formatter's own traversal; the timing is what prices that.
* A group with no traceback and no links is asserted to cost more to format as
  its children multiply: 1,000x the children costs more than 100x, which is the
  part of the formatting bound that neither d nor c covers. Only the width of
  a flat group is varied; nesting depth is not.
* `from None` is asserted to keep `__context__` linked while leaving the
  suppressed exception's text out of `format_exception()` output, which is
  the whole of "only the display changes". `from error` is asserted to set
  `__suppress_context__` and still display the cause, which is the
  distinction the page draws between the two links.
* Every fenced Python block runs in its own subprocess with a temporary
  working directory, and a mutated assertion in one of them is asserted to
  fail first.

Not settled here:

* Whether `except` matching is linear rather than merely growing in t and a.
  The tests bound it below at two points each; the shape between them is not
  measured, and the counts come from the source anyway.
* That `except*` costs one walk per clause. `except*` matches by subclass and
  does not consult `__instancecheck__`, so a counting class cannot record the
  walks, and the page's bound comes from the semantics rather than a count.
* That `raise new from old` is O(1) separately from the O(c) context walk the
  surrounding raise performs. The timing test below moves the context chain
  and holds everything else fixed, which prices the pair.
* The whole cost of formatting. Two dimensions are timed separately - one
  traceback's depth, and a flat group's width - and nothing combines them. A
  chain of c exceptions each carrying its own traceback, nested group depth,
  note and message lengths, and a custom `__str__` are all outside what is
  measured.
* `OSError.winerror` and the Windows `errno` values behind it. Only its
  absence is asserted on this platform; no run here reaches the attribute.
* That `MemoryError` instances are pre-allocated. Exhausting memory to
  observe it is not something a test suite should do.
* `PythonFinalizationError` being raised. It requires an operation blocked
  during interpreter shutdown; only its class and position are asserted.
* `SystemExit` and `KeyboardInterrupt` reaching the interpreter. Both are
  asserted by class relationship and by an explicit raise; nothing here
  exercises `sys.exit()` at the top level or a real interrupt.
* What issuing a warning costs. Filter matching and the once-per-location
  registry belong to the `warnings` module; only the categories' class
  relationships and one "error" filter are asserted here.
"""

from __future__ import annotations

import builtins
import errno
import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import traceback
import tracemalloc
import warnings
import weakref
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "exceptions.md"
EXPECTED_BLOCKS = 21

# The group classes are Python 3.11 builtins. Naming them directly would not
# lint or type-check against the 3.10 floor this project supports, so the
# tests that need them reach them through `builtins`.
GROUP: Any = getattr(builtins, "ExceptionGroup", None)
BASE_GROUP: Any = getattr(builtins, "BaseExceptionGroup", None)


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def descend(depth: int) -> None:
    """Recurse `depth` frames, then raise."""
    if depth:
        return descend(depth - 1)
    raise ValueError("bottom")


def call_depth(depth: int) -> int:
    """The same recursion without the raise, for subtracting the call cost."""
    if depth:
        return call_depth(depth - 1)
    return 0


def subclass_chain(length: int) -> Any:
    """A class `length` inheritance steps below Exception."""
    cls: Any = Exception
    for index in range(length):
        cls = type(f"Chained{index}", (cls,), {})
    return cls


class TestPropagationCostsTheFrames:
    """`raise exc` | O(d) | O(d), d = frames unwound.

    Counted rather than timed: one traceback entry per frame is an exact
    number, and a weak reference either survives or does not.
    """

    def test_one_traceback_entry_per_frame_unwound(self) -> None:
        def entries(depth: int) -> int:
            try:
                descend(depth)
            except ValueError as error:
                return len(traceback.extract_tb(error.__traceback__))
            raise AssertionError("descend() returned")

        assert entries(0) == 2
        assert entries(100) == 102
        assert entries(400) == 402

    @pytest.mark.timing
    def test_propagation_time_follows_the_depth(self) -> None:
        """The one timing check on the d term; 1024x the depth, far above 50x."""
        original = sys.getrecursionlimit()
        sys.setrecursionlimit(5_000)
        try:

            def raise_through(depth: int) -> None:
                try:
                    descend(depth)
                except ValueError:
                    pass

            shallow = best_ns(lambda: raise_through(1), inner=2_000) - best_ns(
                lambda: call_depth(1), inner=2_000
            )
            deep = best_ns(lambda: raise_through(1_024), inner=20) - best_ns(
                lambda: call_depth(1_024), inner=20
            )
        finally:
            sys.setrecursionlimit(original)

        assert shallow > 0, f"propagation at depth 1 measured at {shallow:.0f}ns"
        assert deep > shallow * 50, (
            f"1024x the depth cost {deep / shallow:.1f}x: {shallow:.0f}ns to {deep:.0f}ns"
        )

    def test_a_held_exception_holds_the_frames_it_unwound(self) -> None:
        tracker: weakref.ref[Any] | None = None

        class Payload:
            pass

        def fail() -> None:
            nonlocal tracker
            payload = Payload()
            tracker = weakref.ref(payload)
            raise ValueError("boom")

        try:
            fail()
        except ValueError as error:
            held = error

        assert tracker is not None
        gc.collect()
        assert tracker() is not None, "the raising frame's local died while the exception lived"

        held.with_traceback(None)
        gc.collect()
        assert tracker() is None, "with_traceback(None) left the frame reachable"

    def test_with_traceback_returns_the_same_exception(self) -> None:
        error = ValueError("x")

        assert error.with_traceback(None) is error

    @pytest.mark.timing
    def test_dropping_the_last_traceback_reference_costs_the_frames(self) -> None:
        """The free happens inside the call, so it is O(d), not O(1).

        Measured after the handler has exited. Inside one, the thread's
        exception state still references the traceback on Python 3.10, so the
        call drops nothing and the free is deferred to the end of the block;
        from 3.11 it is the last reference either way.
        """

        def capture(depth: int) -> BaseException:
            try:
                descend(depth)
            except ValueError as error:
                return error
            raise AssertionError("descend() returned")

        def cost(depth: int) -> float:
            best: float | None = None
            for _ in range(40):
                held = capture(depth)
                start = time.perf_counter_ns()
                held.with_traceback(None)
                elapsed = float(time.perf_counter_ns() - start)
                del held
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        original = sys.getrecursionlimit()
        sys.setrecursionlimit(30_000)
        try:
            shallow = cost(1)
            deep = cost(5_000)
        finally:
            sys.setrecursionlimit(original)

        assert deep > shallow * 100, (
            f"dropping a 5,000-entry traceback cost {deep / shallow:.1f}x a 1-entry one: "
            f"{shallow:.0f}ns to {deep:.0f}ns"
        )

    def test_except_as_unbinds_the_name_at_the_end_of_the_block(self) -> None:
        try:
            raise ValueError("x")
        except ValueError as error:
            assert error.args == ("x",)

        assert "error" not in locals(), "the exception outlived its except block"

    def test_a_bare_raise_continues_the_traceback_where_raise_error_extends_it(self) -> None:
        def bare() -> None:
            try:
                descend(3)
            except ValueError:
                raise

        def explicit() -> None:
            try:
                descend(3)
            except ValueError as error:
                raise error

        def entries(func: Callable[[], None]) -> int:
            try:
                func()
            except ValueError as error:
                return len(traceback.extract_tb(error.__traceback__))
            raise AssertionError(f"{func.__name__}() returned")

        assert entries(bare) == 6
        assert entries(explicit) == 7, "`raise error` did not append a frame"


class TestMatchingAnExceptClause:
    """Matching an `except` clause | O(t·a) worst case | O(1).

    The t term is settled by observation - a bad entry behind a matching one
    is still rejected - and bounded below by timing; the a term by timing an
    ancestor chain; the product by timing the depth with the width held fixed.
    """

    def test_every_class_in_the_tuple_is_checked_even_behind_a_match(self) -> None:
        with pytest.raises(TypeError, match="do not inherit from BaseException"):
            try:
                raise ValueError("bad")
            except (ValueError, "not a class"):  # type: ignore[misc]  # noqa: B030
                pass

    def test_source_order_decides_not_specificity(self) -> None:
        class AppError(Exception):
            pass

        class ValidationError(AppError):
            pass

        try:
            raise ValidationError("bad field")
        except AppError:
            first = "AppError"
        except ValidationError:  # pyright: ignore[reportUnusedExcept] - being dead is the claim
            first = "ValidationError"

        assert first == "AppError"

    def test_the_bound_name_is_the_raised_exception_not_the_matching_class(self) -> None:
        """A tuple binds what was raised, so which entry matched is not visible."""
        try:
            raise KeyError("k")
        except (LookupError, KeyError) as error:
            caught = error

        assert type(caught) is KeyError
        assert caught.args == ("k",)

    @pytest.mark.timing
    def test_a_long_tuple_costs_more_than_a_short_one(self) -> None:
        def clause_cost(width: int) -> float:
            fillers = tuple(
                type(f"Filler{width}_{index}", (Exception,), {}) for index in range(width)
            )
            classes = fillers + (ValueError,)

            def run() -> None:
                try:
                    raise ValueError("x")
                except classes:
                    pass

            return best_ns(run, inner=500)

        narrow = clause_cost(1)
        wide = clause_cost(2_000)

        assert wide > narrow * 20, (
            f"a 2,001-class clause cost {wide / narrow:.1f}x a 2-class one: "
            f"{narrow:.0f}ns to {wide:.0f}ns"
        )

    @pytest.mark.timing
    def test_a_deep_ancestor_chain_costs_more_than_a_shallow_one(self) -> None:
        def match_cost(chain: int) -> float:
            cls = subclass_chain(chain)

            def run() -> None:
                try:
                    raise cls("x")
                except Exception:
                    pass

            return best_ns(run, inner=500)

        shallow = match_cost(1)
        deep = match_cost(400)

        assert deep > shallow * 8, (
            f"400 ancestors cost {deep / shallow:.1f}x one: {shallow:.0f}ns to {deep:.0f}ns"
        )

    @pytest.mark.timing
    def test_the_two_terms_multiply(self) -> None:
        """t and a are not independent: the ancestors are rescanned per candidate.

        The tuple is held at 501 classes and only the depth of the raised
        class moves, so a sum would leave the cost nearly unchanged.
        """

        def cost(chain: int) -> float:
            cls = subclass_chain(chain)
            pad = (type(f"Pad{chain}_{index}", (Exception,), {}) for index in range(500))
            classes = tuple(pad) + (cls,)

            def run() -> None:
                try:
                    raise cls("x")
                except classes:
                    pass

            return best_ns(run, inner=200)

        shallow = cost(1)
        deep = cost(400)

        assert deep > shallow * 8, (
            f"with t fixed at 501, 400 ancestors cost {deep / shallow:.1f}x one: "
            f"{shallow:.0f}ns to {deep:.0f}ns - a sum would be flat"
        )


class TestPayloadsAreReferences:
    """`BaseException(*args)` | O(1) | O(1) for a fixed argument count.

    Identity settles the part that matters: nothing is copied, so the payload
    never enters the bound. Nothing here varies the argument count, which the
    page's cost model holds fixed and which stays at one throughout.
    """

    def test_a_message_is_referenced_not_copied(self) -> None:
        message = "x" * 1_000_000

        error = ValueError(message)

        assert error.args[0] is message
        assert error.args == (message,)

    def test_a_failed_lookup_references_the_key(self) -> None:
        key = tuple(range(100_000))

        try:
            {}[key]
        except KeyError as missing:
            assert missing.args[0] is key
        else:
            raise AssertionError("an empty dict had the key")

    @pytest.mark.serial
    def test_building_an_exception_does_not_allocate_for_its_payload(self) -> None:
        payload = bytes(4_000_000)

        peak = peak_bytes(lambda: ValueError(payload))

        assert peak < 1_000, f"ValueError() allocated {peak} bytes over a 4 MB payload"

    @pytest.mark.timing
    def test_construction_time_does_not_follow_the_message(self) -> None:
        short = "x" * 8
        long = "x" * 1_000_000

        short_ns = best_ns(lambda: ValueError(short), inner=5_000)
        long_ns = best_ns(lambda: ValueError(long), inner=5_000)

        assert long_ns < short_ns * 2, (
            f"a 125,000x longer message cost {long_ns / short_ns:.1f}x: "
            f"{short_ns:.0f}ns to {long_ns:.0f}ns"
        )


class TestOSErrorSplitsItsState:
    """`OSError(...)` | O(1) | O(1), with the subclass chosen by errno."""

    ERRNO_SUBCLASSES = [
        (errno.ENOENT, FileNotFoundError),
        (errno.EEXIST, FileExistsError),
        (errno.EACCES, PermissionError),
        (errno.EISDIR, IsADirectoryError),
        (errno.ENOTDIR, NotADirectoryError),
        (errno.EPIPE, BrokenPipeError),
        (errno.ESRCH, ProcessLookupError),
        (errno.ECHILD, ChildProcessError),
        (errno.EINTR, InterruptedError),
        (errno.EAGAIN, BlockingIOError),
        (errno.ECONNRESET, ConnectionResetError),
        (errno.ECONNREFUSED, ConnectionRefusedError),
        (errno.ECONNABORTED, ConnectionAbortedError),
    ]

    @pytest.mark.parametrize(("number", "expected"), ERRNO_SUBCLASSES)
    def test_errno_picks_the_subclass_at_construction(
        self, number: int, expected: type[OSError]
    ) -> None:
        assert type(OSError(number, "message")) is expected

    def test_the_filenames_stay_out_of_args(self) -> None:
        error = OSError(errno.ENOENT, "No such file or directory", "missing.txt")

        assert error.errno == errno.ENOENT
        assert error.strerror == "No such file or directory"
        assert error.filename == "missing.txt"
        assert error.filename2 is None
        assert error.args == (errno.ENOENT, "No such file or directory")

    def test_the_five_argument_form_fills_filename2(self) -> None:
        error = OSError(errno.EXDEV, "Invalid cross-device link", "a.txt", None, "b.txt")

        assert error.filename == "a.txt"
        assert error.filename2 == "b.txt"

    def test_winerror_exists_only_on_windows(self) -> None:
        error = OSError(errno.ENOENT, "missing")

        assert hasattr(error, "winerror") == (sys.platform == "win32")

    def test_characters_written_is_unset_until_something_sets_it(self) -> None:
        blocked = BlockingIOError(errno.EAGAIN, "write would block")

        assert not hasattr(blocked, "characters_written")
        with pytest.raises(AttributeError):
            blocked.characters_written  # noqa: B018 - the point is that it raises

        blocked.characters_written = 512
        assert blocked.characters_written == 512

    def test_the_old_names_are_oserror_itself(self) -> None:
        assert EnvironmentError is OSError
        assert IOError is OSError
        assert issubclass(TimeoutError, OSError)
        assert issubclass(ConnectionResetError, ConnectionError)

    def test_the_timeout_aliases_landed_in_different_releases(self) -> None:
        import asyncio
        import socket

        assert socket.timeout is TimeoutError
        assert (asyncio.TimeoutError is TimeoutError) == (sys.version_info >= (3, 11))


class TestAFailedDecodeCopiesItsInput:
    """`UnicodeDecodeError` from `decode()` | O(len(object)) | O(len(object)).

    The one size-dependent bound on the page, and the only claim here that
    distinguishes a raised exception from a constructed one: built directly
    from `bytes` the exception references its buffer, raised by `decode()` it
    gets a copy. The identity assertions are what settle that. The linear
    *time* is not separated here into the scan up to the failure and the copy
    of the whole buffer; the peak test bounds the copy alone.
    """

    DATA = b"\xff" * 4_000_000

    def test_decode_hands_the_exception_a_copy(self) -> None:
        try:
            self.DATA.decode("utf-8")
        except UnicodeDecodeError as failure:
            assert failure.object == self.DATA
            assert failure.object is not self.DATA
            assert failure.encoding == "utf-8"
            assert failure.start == 0
            assert failure.end == 1
            assert failure.reason == "invalid start byte"
        else:
            raise AssertionError("invalid UTF-8 decoded")

    def test_encode_hands_the_exception_the_original(self) -> None:
        text = "\ud800" * 100_000

        try:
            text.encode("utf-8")
        except UnicodeEncodeError as failure:
            assert failure.object is text
        else:
            raise AssertionError("a lone surrogate encoded")

    @pytest.mark.serial
    def test_built_directly_it_references_its_buffer(self) -> None:
        direct = UnicodeDecodeError("utf-8", self.DATA, 0, 1, "invalid start byte")

        assert direct.object is self.DATA

        peak = peak_bytes(lambda: UnicodeDecodeError("utf-8", self.DATA, 0, 1, "reason"))

        assert peak < 1_000, f"building it directly allocated {peak} bytes over a 4 MB buffer"

    @pytest.mark.serial
    def test_the_copy_shows_up_as_space(self) -> None:
        def failing_decode() -> None:
            try:
                self.DATA.decode("utf-8")
            except UnicodeDecodeError:
                pass

        peak = peak_bytes(failing_decode)

        assert peak > len(self.DATA), (
            f"a failed 4 MB decode peaked at {peak} bytes, below one copy of the input"
        )

    def test_the_unicode_errors_sit_under_valueerror(self) -> None:
        assert issubclass(UnicodeError, ValueError)
        for cls in (UnicodeDecodeError, UnicodeEncodeError, UnicodeTranslateError):
            assert issubclass(cls, UnicodeError)


class TestWhereTheSourceWentWrong:
    """`SyntaxError` and its two subclasses, priced O(1) and distinguished by
    what actually raises each one."""

    def test_syntax_error_positions(self) -> None:
        try:
            compile("if True\n    pass\n", "demo.py", "exec")
        except SyntaxError as error:
            assert isinstance(error.msg, str)
            assert error.filename == "demo.py"
            assert error.lineno == 1
            assert error.offset == 8
            assert error.text == "if True\n"
            assert error.end_lineno == 1
            assert error.end_offset is not None
            assert error.end_offset >= error.offset
        else:
            raise AssertionError("a colon-less `if` compiled")

    def test_uneven_indentation_is_not_a_taberror(self) -> None:
        with pytest.raises(IndentationError) as caught:
            compile("if True:\npass\n", "demo.py", "exec")

        assert not isinstance(caught.value, TabError)
        assert caught.value.lineno == 2

    def test_taberror_comes_from_mixing_tabs_and_spaces(self) -> None:
        with pytest.raises(TabError) as caught:
            compile("if True:\n  pass\n\tpass\n", "demo.py", "exec")

        assert caught.value.lineno == 3
        assert caught.value.text == "\tpass\n"

    def test_the_indentation_hierarchy(self) -> None:
        assert issubclass(TabError, IndentationError)
        assert issubclass(IndentationError, SyntaxError)


class TestNamesAttributesAndImports:
    """The errors that record what could not be resolved, all O(1)."""

    def test_nameerror_carries_the_identifier(self) -> None:
        try:
            undefined_name  # type: ignore[name-defined]  # noqa: B018, F821
        except NameError as error:
            assert error.name == "undefined_name"
        else:
            raise AssertionError("an unbound name resolved")

    def test_attributeerror_references_the_object_searched(self) -> None:
        class Config:
            host = "localhost"

        try:
            Config.port  # type: ignore[attr-defined]  # noqa: B018
        except AttributeError as error:
            assert error.name == "port"
            assert error.obj is Config
        else:
            raise AssertionError("a missing attribute resolved")

    def test_modulenotfounderror_carries_the_name_and_no_path(self) -> None:
        try:
            import no_such_module_here  # type: ignore[import-not-found]  # noqa: F401
        except ModuleNotFoundError as error:
            assert isinstance(error, ImportError)
            assert error.name == "no_such_module_here"
            assert error.path is None
        else:
            raise AssertionError("a missing module imported")

    def test_unboundlocalerror_inherits_name_but_leaves_it_none(self) -> None:
        def read_before_write() -> str | None:
            try:
                return count  # type: ignore[has-type]  # noqa: F821 - unbound on purpose
            except UnboundLocalError as error:
                return error.name
            count = "0"  # type: ignore[unreachable]  # noqa: F841

        assert read_before_write() is None
        assert issubclass(UnboundLocalError, NameError)


class TestReferenceError:
    """`ReferenceError` | O(1) | O(1), and which weakref spelling raises it."""

    def test_a_proxy_raises_where_a_ref_returns_none(self) -> None:
        class Target:
            pass

        target = Target()
        reference = weakref.ref(target)
        proxy = weakref.proxy(target)

        del target
        gc.collect()

        assert reference() is None
        with pytest.raises(ReferenceError):
            proxy.missing  # noqa: B018  # pyright: ignore[reportUnusedExpression] - it raises


class TestChaining:
    """`raise new from old` | O(1) | O(1); the surrounding raise is O(c)."""

    def test_from_sets_cause_and_suppresses_the_context(self) -> None:
        try:
            try:
                int("twelve")
            except ValueError as error:
                raise TypeError("not a count") from error
        except TypeError as error:
            assert isinstance(error.__cause__, ValueError)
            assert error.__cause__ is error.__context__
            assert error.__suppress_context__ is True
            # Suppression applies to the implicit context; an explicit cause
            # is displayed regardless.
            rendered = "".join(traceback.format_exception(error))
            assert "invalid literal" in rendered
            assert "direct cause" in rendered
        else:
            raise AssertionError("'twelve' parsed")

    def test_without_from_the_context_is_still_linked(self) -> None:
        try:
            try:
                int("twelve")
            except ValueError:
                raise TypeError("not a count")  # noqa: B904 - the missing `from` is the point
        except TypeError as error:
            assert isinstance(error.__context__, ValueError)
            assert error.__cause__ is None
            assert error.__suppress_context__ is False

    def test_from_none_hides_the_display_without_unlinking(self) -> None:
        try:
            try:
                int("twelve")
            except ValueError:
                raise TypeError("not a count") from None
        except TypeError as error:
            assert error.__cause__ is None
            assert isinstance(error.__context__, ValueError)
            assert error.__suppress_context__ is True
            rendered = "".join(traceback.format_exception(error))
            assert "invalid literal" not in rendered, "the suppressed context was displayed"
            assert "not a count" in rendered

    @pytest.mark.timing
    def test_raising_in_a_handler_walks_the_existing_context_chain(self) -> None:
        """The O(c) term: setting `__context__` scans the chain for a cycle."""

        def held_with_chain(depth: int) -> BaseException:
            def nest(remaining: int) -> None:
                if remaining == 0:
                    raise ValueError(0)
                try:
                    nest(remaining - 1)
                except Exception:
                    raise ValueError(remaining)  # noqa: B904 - building the chain

            try:
                nest(depth)
            except ValueError as error:
                return error
            raise AssertionError("nest() returned")

        def cost(depth: int) -> float:
            held = held_with_chain(depth)

            def run() -> None:
                try:
                    try:
                        raise held
                    except ValueError:
                        raise TypeError("new")  # noqa: B904 - the implicit context is the point
                except TypeError:
                    pass

            return best_ns(run, inner=200)

        original = sys.getrecursionlimit()
        sys.setrecursionlimit(30_000)
        try:
            short = cost(1)
            long = cost(5_000)
        finally:
            sys.setrecursionlimit(original)

        assert long > short * 10, (
            f"a 5,000-link context cost {long / short:.1f}x a 1-link one: "
            f"{short:.0f}ns to {long:.0f}ns"
        )

    def test_a_chain_keeps_every_link_alive(self) -> None:
        def nest(depth: int) -> None:
            if depth == 0:
                raise ValueError(0)
            try:
                nest(depth - 1)
            except Exception:
                raise ValueError(depth)  # noqa: B904 - an implicit context is the point

        try:
            nest(20)
        except ValueError as error:
            links = 0
            current: BaseException | None = error
            while current is not None:
                links += 1
                current = current.__context__
        else:
            raise AssertionError("nest() returned")

        assert links == 21, f"a 20-deep nest produced {links} linked exceptions"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="add_note() is Python 3.11+")
class TestNotes:
    """`add_note()` | O(1) amortized | O(1), with `__notes__` O(p)."""

    def test_notes_do_not_exist_until_one_is_added(self) -> None:
        error: Any = ValueError("bad row")

        assert not hasattr(error, "__notes__")

        error.add_note("row 14")
        assert error.__notes__ == ["row 14"]

    def test_notes_append_in_order_and_leave_args_alone(self) -> None:
        error: Any = ValueError("bad row")

        error.add_note("row 14")
        error.add_note("file inventory.csv")

        assert error.__notes__ == ["row 14", "file inventory.csv"]
        assert error.args == ("bad row",)

    @pytest.mark.timing
    def test_adding_a_note_does_not_get_dearer_as_notes_accumulate(self) -> None:
        empty: Any = ValueError("x")
        empty.add_note("first")
        loaded: Any = ValueError("x")
        for index in range(100_000):
            loaded.add_note(f"note {index}")

        fresh_ns = best_ns(lambda: empty.add_note("n"), inner=2_000)
        loaded_ns = best_ns(lambda: loaded.add_note("n"), inner=2_000)

        assert loaded_ns < fresh_ns * 2, (
            f"appending past 100,000 notes cost {loaded_ns / fresh_ns:.1f}x: "
            f"{fresh_ns:.0f}ns to {loaded_ns:.0f}ns"
        )


@pytest.mark.skipif(sys.version_info < (3, 11), reason="exception groups are Python 3.11+")
class TestExceptionGroups:
    """Construction is O(m) in direct children; the walks are O(n) worst case.

    The walk is counted with a recording predicate, so what it visits is an
    exact call list rather than a ratio, and a predicate that matches the root
    shows where the walk stops short of n.
    """

    @staticmethod
    def _tree() -> tuple[BaseException, BaseException, Any]:
        first = ValueError("v1")
        inner = GROUP("inner", [TypeError("t"), ValueError("v2")])
        return first, inner, GROUP("outer", [first, inner])

    def test_the_children_are_held_by_reference(self) -> None:
        first, inner, group = self._tree()

        assert group.message == "outer"
        assert group.args == ("outer", [first, inner])
        assert group.exceptions == (first, inner)

    def test_split_visits_every_node_once_in_document_order(self) -> None:
        _, _, group = self._tree()
        visited: list[str] = []

        def record(exc: BaseException) -> bool:
            visited.append(type(exc).__name__)
            return isinstance(exc, ValueError)

        matched, rest = group.split(record)

        assert visited == [
            "ExceptionGroup",
            "ValueError",
            "ExceptionGroup",
            "TypeError",
            "ValueError",
        ]
        assert len(matched.exceptions) == 2
        assert isinstance(rest, GROUP)

    def test_subgroup_walks_the_same_nodes(self) -> None:
        _, _, group = self._tree()
        visited: list[str] = []

        def record(exc: BaseException) -> bool:
            visited.append(type(exc).__name__)
            return isinstance(exc, TypeError)

        result = group.subgroup(record)

        assert visited == [
            "ExceptionGroup",
            "ValueError",
            "ExceptionGroup",
            "TypeError",
            "ValueError",
        ]
        assert result is not None
        assert result.message == "outer"

    def test_a_subgroup_that_matches_nothing_still_walks_the_tree(self) -> None:
        _, _, group = self._tree()
        visited: list[str] = []

        def record(exc: BaseException) -> bool:
            visited.append(type(exc).__name__)
            return isinstance(exc, KeyError)

        assert group.subgroup(record) is None
        assert visited == [
            "ExceptionGroup",
            "ValueError",
            "ExceptionGroup",
            "TypeError",
            "ValueError",
        ]

    def test_a_node_that_matches_keeps_its_subtree_unvisited(self) -> None:
        """Why the walks are O(n) worst case rather than always O(n)."""
        _, _, group = self._tree()
        visited: list[str] = []

        def matches_anything(exc: BaseException) -> bool:
            visited.append(type(exc).__name__)
            return True

        assert group.subgroup(matches_anything) is group
        assert visited == ["ExceptionGroup"]

    @staticmethod
    def _annotated(groups: int, notes: int) -> Any:
        """A spine of `groups` nested groups, each annotated and each holding a
        matching and a non-matching leaf, so every one has to be rebuilt."""
        node: Any = GROUP("leaf", [ValueError("v"), TypeError("t")])
        for index in range(notes):
            node.add_note(f"n{index}")
        for level in range(groups - 1):
            node = GROUP(f"g{level}", [node, ValueError("v"), TypeError("t")])
            for index in range(notes):
                node.add_note(f"n{index}")
        return node

    def test_every_rebuilt_group_gets_a_copy_of_its_own_notes(self) -> None:
        """The p term, and why `derive()` is the cheap one."""
        nested: Any = self._annotated(groups=2, notes=2)

        matched, rest = nested.split(ValueError)
        sub_only = nested.subgroup(ValueError)
        derived = nested.derive([KeyError("k")])

        for rebuilt in (matched, rest, sub_only):
            assert rebuilt.__notes__ == nested.__notes__
            assert rebuilt.__notes__ is not nested.__notes__

        # and below the root, not only on it
        inner_source = nested.exceptions[0]
        inner_rebuilt = matched.exceptions[0]
        assert inner_rebuilt.__notes__ == inner_source.__notes__
        assert inner_rebuilt.__notes__ is not inner_source.__notes__

        assert not hasattr(derived, "__notes__")

    @pytest.mark.timing
    def test_notes_are_copied_once_per_group_not_once_per_walk(self) -> None:
        """p multiplies n rather than adding to it."""

        def cost(groups: int, notes: int) -> float:
            tree = self._annotated(groups, notes)
            return best_ns(lambda: tree.split(ValueError), inner=20)

        one_plain, one_annotated = cost(1, 0), cost(1, 200)
        many_plain, many_annotated = cost(50, 0), cost(50, 200)

        one_note_cost = one_annotated - one_plain
        many_note_cost = many_annotated - many_plain

        assert one_note_cost > 0 and many_note_cost > 0
        assert many_note_cost > one_note_cost * 10, (
            f"50 annotated groups paid {many_note_cost / one_note_cost:.1f}x one group's note "
            f"cost ({one_note_cost:.0f}ns to {many_note_cost:.0f}ns); a single copy per walk "
            "would leave it flat"
        )

    def test_derive_drops_what_split_copies(self) -> None:
        group: Any
        cause = RuntimeError("why")
        try:
            try:
                raise KeyError("root")
            except KeyError:
                raise GROUP("outer", [ValueError("v")]) from cause
        except BASE_GROUP as group:
            derived = group.derive([KeyError("k")])
            matched, _ = group.split(ValueError)
            sub_only = group.subgroup(ValueError)

            assert isinstance(group.__context__, KeyError)
            assert group.__cause__ is cause

            assert derived.message == "outer"
            assert derived.__traceback__ is None
            assert derived.__context__ is None
            assert derived.__cause__ is None

            for rebuilt in (matched, sub_only):
                assert rebuilt is not None
                assert rebuilt.__traceback__ is group.__traceback__
                assert rebuilt.__context__ is group.__context__
                assert rebuilt.__cause__ is cause

    def test_the_class_follows_the_leaves(self) -> None:
        assert type(BASE_GROUP("g", [ValueError("v")])) is GROUP
        assert type(BASE_GROUP("g", [KeyboardInterrupt()])) is BASE_GROUP
        with pytest.raises(TypeError):
            GROUP("g", [KeyboardInterrupt()])

    @pytest.mark.timing
    def test_construction_follows_the_direct_child_count(self) -> None:
        small = [ValueError(index) for index in range(100)]
        large = [ValueError(index) for index in range(100_000)]

        small_ns = best_ns(lambda: GROUP("g", small), inner=200)
        large_ns = best_ns(lambda: GROUP("g", large), inner=5)

        assert large_ns > small_ns * 100, (
            f"1,000x the direct children cost {large_ns / small_ns:.1f}x: "
            f"{small_ns:.0f}ns to {large_ns:.0f}ns"
        )

    @pytest.mark.timing
    def test_construction_does_not_follow_the_leaves_below_a_child(self) -> None:
        """m, not n: an already-built subtree is nested without being walked."""
        shallow = GROUP("shallow", [ValueError(index) for index in range(10)])
        deep = GROUP("deep", [ValueError(index) for index in range(100_000)])

        shallow_ns = best_ns(lambda: GROUP("g", [shallow, shallow]), inner=2_000)
        deep_ns = best_ns(lambda: GROUP("g", [deep, deep]), inner=2_000)

        assert deep_ns < shallow_ns * 2, (
            f"two 100,000-leaf children cost {deep_ns / shallow_ns:.1f}x two 10-leaf ones: "
            f"{shallow_ns:.0f}ns to {deep_ns:.0f}ns - construction would be O(n) if it walked them"
        )


class TestGeneratorsAndStopIteration:
    """`StopIteration` | O(1) | O(1), and what happens when one escapes."""

    def test_stopiteration_inside_a_generator_becomes_a_runtimeerror(self) -> None:
        def leaks() -> Any:
            yield 1
            raise StopIteration("not a return")

        generator = leaks()
        assert next(generator) == 1

        try:
            next(generator)
        except RuntimeError as error:
            assert isinstance(error.__context__, StopIteration)
        else:
            raise AssertionError("StopIteration escaped the generator")

    def test_a_return_value_rides_on_stopiteration_value(self) -> None:
        def returns_total() -> Any:
            yield 1
            return 42

        totals = returns_total()
        assert next(totals) == 1

        try:
            next(totals)
        except StopIteration as stop:
            assert stop.value == 42
        else:
            raise AssertionError("the generator yielded again")

    def test_a_closed_generator_sees_generatorexit(self) -> None:
        seen = []

        def cleans_up() -> Any:
            try:
                yield 1
            except GeneratorExit:
                seen.append("closed")
                raise

        generator = cleans_up()
        next(generator)
        generator.close()

        assert seen == ["closed"]
        assert not issubclass(GeneratorExit, Exception)


class TestReadingATraceback:
    """Formatting is O(d) in frames, including the ones the display folds."""

    def test_more_frames_are_extracted_than_the_display_shows(self) -> None:
        original = sys.getrecursionlimit()
        sys.setrecursionlimit(400)
        try:

            def recurse() -> None:
                recurse()

            try:
                recurse()
            except RecursionError as error:
                frames = traceback.extract_tb(error.__traceback__)
                rendered = "".join(traceback.format_exception(error))
            else:
                raise AssertionError("recursion did not stop")
        finally:
            sys.setrecursionlimit(original)

        assert len(frames) > 200
        assert "[Previous line repeated" in rendered
        assert len(rendered.splitlines()) < len(frames)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="exception groups are Python 3.11+")
    def test_formatting_a_group_costs_more_as_its_children_multiply(self) -> None:
        """A group with nothing raised still pays for its children."""
        small: Any = GROUP("g", [ValueError(index) for index in range(10)])
        large: Any = GROUP("g", [ValueError(index) for index in range(10_000)])

        assert small.__traceback__ is None and small.__context__ is None

        small_ns = best_ns(lambda: traceback.format_exception(small), inner=5)
        large_ns = best_ns(lambda: traceback.format_exception(large), inner=2)

        assert large_ns > small_ns * 100, (
            f"1,000x the children cost {large_ns / small_ns:.1f}x: "
            f"{small_ns:.0f}ns to {large_ns:.0f}ns"
        )

    @pytest.mark.timing
    def test_formatting_time_follows_the_depth(self) -> None:
        original = sys.getrecursionlimit()
        sys.setrecursionlimit(5_000)
        try:
            captured: dict[int, BaseException] = {}
            for depth in (1, 2_000):
                try:
                    descend(depth)
                except ValueError as error:
                    captured[depth] = error
        finally:
            sys.setrecursionlimit(original)

        shallow = best_ns(lambda: traceback.format_exception(captured[1]), inner=20)
        deep = best_ns(lambda: traceback.format_exception(captured[2_000]), inner=5)

        assert deep > shallow * 20, (
            f"2,000x the depth cost {deep / shallow:.1f}x: {shallow:.0f}ns to {deep:.0f}ns"
        )

    def test_exc_info_is_empty_outside_a_handler(self) -> None:
        try:
            1 / 0  # noqa: B018  # pyright: ignore[reportUnusedExpression] - raising is the point
        except ZeroDivisionError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            assert exc_type is ZeroDivisionError
            assert exc_value is not None
            assert exc_traceback is exc_value.__traceback__
            if sys.version_info >= (3, 11):
                assert getattr(sys, "exception")() is exc_value  # noqa: B009 - 3.11+

        assert sys.exc_info() == (None, None, None)


class TestTheHierarchy:
    """The page's fenced tree, checked edge by edge against `__bases__`.

    A release that adds an exception class, or moves one, fails this rather
    than quietly leaving the tree wrong.
    """

    @staticmethod
    def _tree_edges() -> list[tuple[str, str]]:
        """Every (parent, child) pair the page's tree draws."""
        text = PAGE.read_text(encoding="utf-8")
        block = re.search(r"```\n(BaseException\n.*?)```", text, re.DOTALL)
        assert block is not None, "the hierarchy tree is no longer on the page"

        edges: list[tuple[str, str]] = []
        at_depth: dict[int, str] = {}
        for line in block.group(1).splitlines():
            if not line.strip():
                continue
            name = re.sub(r"\s*\(.*\)\s*$", "", line).split()[-1]
            prefix = line[: len(line) - len(line.lstrip("│├└─ "))]
            depth = len(prefix) // 4
            at_depth[depth] = name
            if depth:
                edges.append((at_depth[depth - 1], name))
        return edges

    @staticmethod
    def _public_exception_classes() -> set[str]:
        return {
            name
            for name in dir(builtins)
            if not name.startswith("_")
            and isinstance(getattr(builtins, name), type)
            and issubclass(getattr(builtins, name), BaseException)
        }

    def test_every_drawn_edge_is_a_real_base_class(self) -> None:
        """Edges for classes a supported release does not have yet are left to
        `test_the_tree_names_every_public_exception_class_once`."""
        wrong = []
        for parent, child in self._tree_edges():
            if not hasattr(builtins, child) or not hasattr(builtins, parent):
                continue
            child_cls = getattr(builtins, child)
            parent_cls = getattr(builtins, parent)
            if parent_cls not in child_cls.__bases__:
                wrong.append(f"{child} is drawn under {parent}, bases are {child_cls.__bases__}")

        assert wrong == [], "\n".join(wrong)

    def test_the_tree_names_every_public_exception_class_once(self) -> None:
        drawn = [child for _, child in self._tree_edges()] + ["BaseException"]
        aliases = {"EnvironmentError", "IOError"}  # bound to OSError, drawn as a note

        assert len(drawn) == len(set(drawn)), "a class is drawn twice in the tree"
        # A name this release does not have is a later version's class, not a
        # drawing error; a class it does have and the tree omits is.
        assert {name for name in drawn if hasattr(builtins, name)} == (
            self._public_exception_classes() - aliases
        )

    def test_the_classes_outside_exception(self) -> None:
        outside: list[type[BaseException]] = [SystemExit, KeyboardInterrupt, GeneratorExit]
        if sys.version_info >= (3, 11):
            outside.append(BASE_GROUP)

        for cls in outside:
            assert issubclass(cls, BaseException)
            assert not issubclass(cls, Exception)

        # and that the list is exhaustive for this interpreter
        direct = {
            name
            for name in dir(builtins)
            if isinstance(getattr(builtins, name), type)
            and issubclass(getattr(builtins, name), BaseException)
            and not issubclass(getattr(builtins, name), Exception)
            and getattr(builtins, name) is not BaseException
        }
        assert direct == {cls.__name__ for cls in outside}

    def test_except_exception_lets_systemexit_through(self) -> None:
        outcome = None
        try:
            raise SystemExit(3)
        except Exception:
            outcome = "swallowed"
        except SystemExit as error:
            outcome = error.code

        assert outcome == 3

    def test_pythonfinalizationerror_is_a_runtimeerror(self) -> None:
        if sys.version_info < (3, 13):
            pytest.skip("PythonFinalizationError is Python 3.13+")

        assert issubclass(builtins.PythonFinalizationError, RuntimeError)


class TestWarningCategories:
    """`Warning` and its subclasses are exceptions that are normally reported
    rather than raised."""

    CATEGORIES = [
        UserWarning,
        DeprecationWarning,
        PendingDeprecationWarning,
        FutureWarning,
        SyntaxWarning,
        RuntimeWarning,
        ImportWarning,
        UnicodeWarning,
        BytesWarning,
        EncodingWarning,
        ResourceWarning,
    ]

    def test_every_category_is_an_exception(self) -> None:
        assert issubclass(Warning, Exception)
        for category in self.CATEGORIES:
            assert issubclass(category, Warning)

    def test_warnings_are_recorded_not_raised(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for category in self.CATEGORIES:
                warnings.warn("message", category, stacklevel=2)

        assert [type(entry.message) for entry in caught] == self.CATEGORIES

    def test_the_default_category_is_userwarning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn("check your input", stacklevel=2)

        assert type(caught[0].message) is UserWarning

    def test_an_error_filter_makes_a_category_behave_like_any_exception(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)

            with pytest.raises(DeprecationWarning) as caught:
                warnings.warn("going away", DeprecationWarning, stacklevel=2)

        assert caught.value.args == ("going away",)


class TestPageCoversTheClasses:
    """The page names every public exception class the interpreter has."""

    def test_no_class_is_missing_from_the_page(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        missing = sorted(
            name
            for name in TestTheHierarchy._public_exception_classes()
            if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text)
        )

        assert missing == []


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
    """Each block runs in its own subprocess with its own working directory,
    so a recursion limit or a created file cannot leak between them."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert entries(100) == 102" in s)
        mutated = source.replace("assert entries(100) == 102", "assert entries(100) == 103", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
