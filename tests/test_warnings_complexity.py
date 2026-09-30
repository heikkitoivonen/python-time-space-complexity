"""Tests for docs/stdlib/warnings.md.

The page prices `warn()` as a frame walk, a registry lookup and a scan of the
filter list that stops at the first match. Almost all of it is settled by
observation rather than timing: the C filter search calls `.match()` on any
filter slot that is not a plain string or None, so a counting matcher placed
in the list shows exactly which filters one warning consulted. The registries
are plain dictionaries and are read directly. Only the frame walk needs a
stopwatch.

Measurement scope:

* The filter scan: ten non-matching counting filters ahead of a matching one
  are each consulted once, and a filter after the match is not consulted.
  A repeat under `"default"`, `"module"` and `"once"` consults nothing; under
  `"ignore"` and `"always"` five warnings consult the one filter five times.
* Registries: a `"default"` warning adds its `(text, category, lineno)` key
  to the module's `__warningregistry__`; 100 distinct texts from one line
  add 100 keys and are all shown. A registry of 100 entries is emptied by the
  next warning after `simplefilter()`, `filterwarnings()`, `resetwarnings()`,
  entering `catch_warnings()` or leaving it, and is not emptied after an in-place edit of
  `warnings.filters`, under which an inserted `"error"` filter is also
  observed to be bypassed for a repeat.
* Installing a filter: f filters whose action slot counts equality
  comparisons are each compared once by `filterwarnings()`, `simplefilter()`
  and an `append=True` call, at f = 10 and f = 1,000. Deduplication,
  front insertion, `append` semantics and equality of two compiled patterns
  are asserted on the list.
* The `"all"` action (3.14+) is asserted to scan and show on every call,
  as `"always"` does.
* The frame walk: at a stack 900 frames deep under an `"ignore"` filter,
  `stacklevel=800` costs more than 10x `stacklevel=8` (a walk linear in k
  predicts about 100x in its own term; a constant one, 1x). The same calls
  measured 460 ns and 25,000 ns on the pinned 3.14. `skip_file_prefixes`
  (3.12+) is asserted to attribute a warning past two frames compiled under
  a skipped file name, and to raise the effective `stacklevel` to 2.
* `warn_explicit()`: without a registry `"default"` and `"module"` each show
  all three calls, with one they show one. A loader's `get_source()` is called once per
  call when `module_globals` is passed, including under `"ignore"`, where the
  warning is never shown. A `"once"` warning without a registry is recorded
  in `warnings.onceregistry`.
* Display: `formatwarning()` with `line` leaves `linecache` untouched; without
  it the whole 1,000-line file is cached. `showwarning()` writes one string to
  the given file.
* `catch_warnings()`: inside the block `warnings.filters` is an equal list
  but not the same object, and the original object is back afterwards;
  `action` installs one filter at the front; `record=True` returns one
  `WarningMessage` per shown warning, carrying the seven documented
  attributes. On 3.14+ with `-X context_aware_warnings=1` the global list is
  observed untouched inside the block.
* `deprecated` (3.13+): three calls of a decorated function record three
  warnings and return the original's result; a decorated class warns on
  instantiation and on subclassing; `category=None` returns the same object.
* Every fenced Python block runs in its own subprocess, the `deprecated`
  block only on 3.13+, and a mutated assertion in one of them is asserted to
  fail.

Not settled here:

* The cost of a `message` or `module` pattern is the regular expression's,
  which the caller chooses; only counting matchers and short literal
  patterns are used.
* That `linecache` keeps a whole file once loaded is read from
  Lib/linecache.py and observed as the cached line count; how long it keeps
  it (until `checkcache()` or `clearcache()`) is not varied.
* The O(1) cost of the category check treats `issubclass()` as constant;
  deep category hierarchies are not measured.
* The Python fallback in Lib/warnings.py (Lib/_py_warnings.py on 3.14) is not
  exercised; every test runs the C `_warnings` implementation CPython ships.
* Every test but one runs with context-aware warnings off, the default on
  the regular builds this project tests; free-threaded builds, where it is
  on by default, are not run. The one context-aware test starts 3.14 with
  `-X context_aware_warnings=1`.
* `warnings.defaultaction` is an undocumented module attribute and is not
  priced on the page.
"""

from __future__ import annotations

import linecache
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import warnings
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "warnings.md"
EXPECTED_BLOCKS = 9


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 200) -> float:
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


class CountingMatcher:
    """A filter pattern that counts how often the filter search consults it."""

    def __init__(self, matches: bool) -> None:
        self.matches = matches
        self.calls = 0

    def match(self, text: str) -> bool:
        self.calls += 1
        return self.matches


class CountingAction:
    """A filter action slot that counts the equality comparisons made against it."""

    compared = 0

    def __eq__(self, other: object) -> bool:
        CountingAction.compared += 1
        return False

    __hash__ = object.__hash__


def active_filters() -> list[Any]:
    """The module's filter list, typed as the mutable list it is."""
    return cast("list[Any]", warnings.filters)


def install(*entries: tuple[str, Any]) -> None:
    """Replace the active filters with (action, message matcher) entries, in order."""
    warnings.resetwarnings()
    active_filters().extend((action, matcher, Warning, None, 0) for action, matcher in entries)
    warnings._filters_mutated()  # type: ignore[attr-defined]  # noqa: SLF001


def emit(text: str = "probe") -> None:
    warnings.warn(text, UserWarning, stacklevel=1)


EMIT_LINE = emit.__code__.co_firstlineno + 1


def registry() -> dict[Any, Any]:
    return emit.__globals__.setdefault("__warningregistry__", {})


class TestTheFilterScanStopsAtTheFirstMatch:
    """`warn()` | O(k + f): the filters are consulted in order until one matches."""

    def test_each_filter_before_the_match_is_consulted_once(self) -> None:
        misses = [CountingMatcher(False) for _ in range(10)]
        hit = CountingMatcher(True)
        after = CountingMatcher(True)
        with warnings.catch_warnings(record=True) as caught:
            install(*[("always", m) for m in misses], ("always", hit), ("error", after))

            emit()

        assert [m.calls for m in misses] == [1] * 10
        assert hit.calls == 1
        assert after.calls == 0, "a filter after the first match was consulted"
        assert len(caught) == 1


class TestRepeatsSkipTheScan:
    """`warn()` - a repeat already in the registry | O(k): the actions that
    record what they show skip the scan on a repeat; the others scan again."""

    @pytest.mark.parametrize("action", ["default", "module", "once"])
    def test_a_recording_action_answers_a_repeat_from_the_registry(self, action: str) -> None:
        matcher = CountingMatcher(True)
        with warnings.catch_warnings(record=True) as caught:
            install((action, matcher))

            for _ in range(5):
                emit()

        assert matcher.calls == 1, f"{action}: {matcher.calls} scans for five identical warnings"
        assert len(caught) == 1

    @pytest.mark.parametrize(("action", "shown"), [("ignore", 0), ("always", 5)])
    def test_ignore_and_always_scan_on_every_call(self, action: str, shown: int) -> None:
        matcher = CountingMatcher(True)
        with warnings.catch_warnings(record=True) as caught:
            install((action, matcher))

            for _ in range(5):
                emit()

        assert matcher.calls == 5, f"{action}: {matcher.calls} scans for five warnings"
        assert len(caught) == shown

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the 'all' action added in 3.14")
    def test_all_is_always_under_another_name(self) -> None:
        matcher = CountingMatcher(True)
        with warnings.catch_warnings(record=True) as caught:
            install(("all", matcher))

            for _ in range(5):
                emit()

        assert matcher.calls == 5
        assert len(caught) == 5

    def test_the_registry_key_is_text_category_and_line(self) -> None:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("default")

            emit("keyed")

            assert registry().get(("keyed", UserWarning, EMIT_LINE)) is True


class TestVaryingTextFillsTheRegistry:
    """Each distinct text is a new key: shown every time, one entry each."""

    def test_a_hundred_texts_add_a_hundred_entries(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("default")
            emit("warm")  # the version marker is written by the first warning
            before = len(registry())

            for index in range(100):
                emit(f"value {index}")

            assert len(registry()) - before == 100
        assert len(caught) == 101


class TestFilterChangesResetTheRegistries:
    """`warn()` - the first warning after a filter change | O(k + f + d): the
    registry is cleared lazily, and only the module functions bump the version."""

    @staticmethod
    def _fill() -> None:
        warnings.simplefilter("default")
        for index in range(100):
            emit(f"fill {index}")
        assert len(registry()) > 100

    @pytest.mark.parametrize(
        "change",
        [
            lambda: warnings.simplefilter("default"),
            lambda: warnings.filterwarnings("default", message="fill"),
            warnings.resetwarnings,
        ],
        ids=["simplefilter", "filterwarnings", "resetwarnings"],
    )
    def test_a_module_function_empties_the_registry_on_the_next_warning(
        self, change: Callable[[], None]
    ) -> None:
        with warnings.catch_warnings(record=True):
            self._fill()

            change()
            assert len(registry()) > 100, "the registry was cleared eagerly"
            emit("next")

            assert len(registry()) <= 2

    def test_entering_catch_warnings_empties_it_too(self) -> None:
        with warnings.catch_warnings(record=True):
            self._fill()
            with warnings.catch_warnings():
                emit("next")

                assert len(registry()) <= 2

    def test_leaving_catch_warnings_empties_it_too(self) -> None:
        with warnings.catch_warnings(record=True):
            with warnings.catch_warnings():
                self._fill()
            assert len(registry()) > 100
            emit("next")

            assert len(registry()) <= 2

    def test_editing_the_list_in_place_does_not(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("default")
            emit("stale")
            size = len(registry())

            active_filters().insert(0, ("error", None, Warning, None, 0))
            emit("stale")

            assert len(registry()) == size
            assert len(caught) == 1

            warnings.simplefilter("error")
            with pytest.raises(UserWarning, match="stale"):
                emit("stale")


class TestInstallingAFilterScansTheList:
    """`filterwarnings()` and `simplefilter()` | O(f): an equal filter is
    looked for across the whole list, whichever end the new one goes to."""

    @pytest.mark.parametrize("size", [10, 1_000])
    @pytest.mark.parametrize(
        "install_one",
        [
            lambda: warnings.filterwarnings("ignore", message="x"),
            lambda: warnings.simplefilter("ignore"),
            lambda: warnings.simplefilter("ignore", append=True),
        ],
        ids=["filterwarnings", "simplefilter", "append"],
    )
    def test_every_filter_is_compared_once(
        self, size: int, install_one: Callable[[], None]
    ) -> None:
        with warnings.catch_warnings():
            warnings.resetwarnings()
            active_filters().extend((CountingAction(), None, Warning, None, 0) for _ in range(size))
            CountingAction.compared = 0

            install_one()

            assert CountingAction.compared == size

    def test_a_duplicate_is_removed_and_the_new_one_goes_first(self) -> None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="old_api", category=DeprecationWarning)
            count = len(warnings.filters)
            warnings.simplefilter("error", RuntimeWarning)
            warnings.filterwarnings("ignore", message="old_api", category=DeprecationWarning)

            assert len(warnings.filters) == count + 1
            assert warnings.filters[0][0] == "ignore"
            assert isinstance(warnings.filters[0][1], re.Pattern)

    def test_two_separately_compiled_patterns_compare_equal(self) -> None:
        first = re.compile("old_api", re.I)
        re.purge()
        second = re.compile("old_api", re.I)

        assert first is not second
        assert first == second
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="old_api")
            count = len(warnings.filters)
            re.purge()
            warnings.filterwarnings("ignore", message="old_api")

            assert len(warnings.filters) == count

    def test_append_adds_at_the_end_only_when_absent(self) -> None:
        with warnings.catch_warnings():
            warnings.resetwarnings()
            warnings.simplefilter("ignore", RuntimeWarning)
            warnings.simplefilter("error", UserWarning, append=True)
            assert [f[0] for f in warnings.filters] == ["ignore", "error"]

            warnings.simplefilter("ignore", RuntimeWarning, append=True)

            assert [f[0] for f in warnings.filters] == ["ignore", "error"]

    def test_resetwarnings_empties_the_list(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.resetwarnings()
            assert warnings.filters == []

            emit("once")
            emit("once")

        assert len(caught) == 1, "with no filters the default action shows once per location"


def _at_depth(depth: int, func: Callable[[], float]) -> float:
    if depth == 0:
        return func()
    return _at_depth(depth - 1, func)


class TestTheFrameWalk:
    """`warn()` | O(k): `stacklevel` frames are walked to attribute the warning."""

    @pytest.mark.timing
    def test_a_deeper_stacklevel_costs_more(self) -> None:
        def measure(level: int) -> float:
            return best_ns(lambda: warnings.warn("deep", UserWarning, stacklevel=level))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            shallow = _at_depth(900, lambda: measure(8))
            deep = _at_depth(900, lambda: measure(800))

        ratio = deep / shallow
        assert ratio > 10, f"stacklevel 8 -> 800: {shallow:.0f}ns -> {deep:.0f}ns, x{ratio:.1f}"

    def test_stacklevel_two_names_the_caller(self) -> None:
        def old_api() -> None:
            warnings.warn("old", DeprecationWarning, stacklevel=2)

        def caller() -> None:
            old_api()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            caller()

        assert caught[0].lineno == caller.__code__.co_firstlineno + 1

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="skip_file_prefixes added in 3.12")
    def test_skip_file_prefixes_walks_past_the_named_files(self) -> None:
        namespace: dict[str, Any] = {"warnings": warnings}
        source = (
            "def inner():\n"
            "    warnings.warn('lib', UserWarning, skip_file_prefixes=('/lib/',))\n"
            "def outer():\n"
            "    inner()\n"
        )
        exec(compile(source, "/lib/module.py", "exec"), namespace)  # noqa: S102

        def user_code() -> None:
            namespace["outer"]()

        def helper() -> None:
            warnings.warn("plain", UserWarning, skip_file_prefixes=("/nowhere/",))  # type: ignore[call-overload]

        def calls_helper() -> None:
            helper()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            user_code()
            calls_helper()

        assert caught[0].filename == __file__
        assert caught[0].lineno == user_code.__code__.co_firstlineno + 1
        # A non-empty prefix tuple raises stacklevel from 1 to 2: helper's caller.
        assert caught[1].lineno == calls_helper.__code__.co_firstlineno + 1


class TestWarnExplicit:
    """`warn_explicit()` | O(f): no frame walk, the caller's registry or none,
    and `module_globals` reads the module's source on every call."""

    @pytest.mark.parametrize("action", ["default", "module"])
    def test_without_a_registry_every_call_is_shown(self, action: str) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter(action)  # type: ignore[arg-type]
            for _ in range(3):
                warnings.warn_explicit("m", UserWarning, "f.py", 2)
            shown_without = len(caught)
            owned: dict[Any, Any] = {}
            for _ in range(3):
                warnings.warn_explicit("m", UserWarning, "f.py", 2, registry=owned)

        assert shown_without == 3
        assert len(caught) == 4
        assert ("m", UserWarning, 2) in owned

    def test_a_supplied_registry_is_cleared_after_a_filter_change(self) -> None:
        owned: dict[Any, Any] = {}
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("default")
            for index in range(100):
                warnings.warn_explicit(f"m{index}", UserWarning, "f.py", 2, registry=owned)
            assert len(owned) > 100

            warnings.simplefilter("error")
            assert len(owned) > 100, "the registry was cleared eagerly"
            with pytest.raises(UserWarning):
                warnings.warn_explicit("m0", UserWarning, "f.py", 2, registry=owned)

        assert len(owned) <= 1

    def test_module_globals_fetches_the_source_on_every_call(self) -> None:
        class Loader:
            calls = 0

            def get_source(self, name: str) -> str:
                Loader.calls += 1
                return "x = 1\n" * 10

        module_globals = {"__name__": "fake_module", "__loader__": Loader()}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("ignore")
            for _ in range(3):
                warnings.warn_explicit(
                    "m", UserWarning, "fake_module.py", 2, module_globals=module_globals
                )

        assert Loader.calls == 3, "the source was not fetched per call"
        assert caught == [], "the source was read for a warning that was never shown"

    def test_once_without_a_registry_uses_onceregistry(self) -> None:
        key = ("once-only probe", UserWarning)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("once")
            warnings.warn_explicit(key[0], UserWarning, "a.py", 1)
            warnings.warn_explicit(key[0], UserWarning, "b.py", 9)

            assert warnings.onceregistry.get(key)  # type: ignore[attr-defined]
        assert len(caught) == 1


class TestDisplayReadsTheSourceFile:
    """`formatwarning()` and `showwarning()` | O(b) for the first warning from
    a file: `linecache` loads and keeps the whole file."""

    @pytest.fixture
    def source(self, tmp_path: pathlib.Path) -> Iterator[str]:
        path = tmp_path / "module.py"
        path.write_text("pass\n" * 1_000, encoding="utf-8")
        linecache.checkcache(str(path))
        yield str(path)
        linecache.checkcache(str(path))
        linecache.cache.pop(str(path), None)

    def test_passing_line_skips_the_file(self, source: str) -> None:
        text = warnings.formatwarning("m", UserWarning, source, 5, line="given")

        assert source not in linecache.cache
        assert text.endswith("UserWarning: m\n  given\n")

    def test_omitting_line_caches_the_whole_file(self, source: str) -> None:
        text = warnings.formatwarning("m", UserWarning, source, 5)

        entry = cast("tuple[Any, Any, list[str], Any]", linecache.cache[source])
        assert len(entry[2]) == 1_000
        assert text.endswith("  pass\n")

    def test_showwarning_writes_one_string(self, source: str, tmp_path: pathlib.Path) -> None:
        # pytest redirects the display step while a test runs, so this runs in a fresh process.
        script = textwrap.dedent(
            f"""
            import warnings
            writes = []

            class Sink:
                def write(self, text):
                    writes.append(text)

            warnings.showwarning("m", UserWarning, {source!r}, 5, file=Sink(), line="given")
            assert writes == [{source!r} + ":5: UserWarning: m\\n  given\\n"], writes
            """
        )

        result = _run_block(script, tmp_path)

        assert result.returncode == 0, result.stderr


class TestCatchWarnings:
    """`catch_warnings()` | O(f) on entry: a copy, restored on exit."""

    def test_entering_copies_the_list_and_leaving_restores_it(self) -> None:
        before = warnings.filters
        with warnings.catch_warnings():
            assert warnings.filters == before
            assert warnings.filters is not before
            warnings.simplefilter("ignore")
            assert warnings.filters != before
        assert warnings.filters is before

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="action added in 3.11")
    def test_action_installs_one_filter_on_entry(self) -> None:
        with warnings.catch_warnings():
            warnings.resetwarnings()
            with warnings.catch_warnings(action="error", category=RuntimeWarning):  # type: ignore[call-overload]
                assert len(warnings.filters) == 1
                assert warnings.filters[0][0] == "error"
                assert warnings.filters[0][2] is RuntimeWarning

    def test_record_keeps_one_message_per_shown_warning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for _ in range(3):
                emit("recorded")

        assert len(caught) == 3
        message = caught[0]
        assert isinstance(message, warnings.WarningMessage)  # type: ignore[attr-defined]
        for name in ("message", "category", "filename", "lineno", "file", "line", "source"):
            assert hasattr(message, name)
        assert message.category is UserWarning
        assert message.lineno == EMIT_LINE

    def test_construction_saves_nothing(self) -> None:
        before = warnings.filters
        manager = warnings.catch_warnings()

        assert warnings.filters is before
        assert not hasattr(manager, "_filters")  # the saved list is taken on entry

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="context-aware warnings added in 3.14")
    def test_context_aware_mode_leaves_the_global_list_alone(self, tmp_path: pathlib.Path) -> None:
        script = textwrap.dedent(
            """
            import sys, warnings
            assert sys.flags.context_aware_warnings
            before = warnings.filters
            count = len(before)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                assert warnings.filters is before and len(before) == count
                warnings.warn("a")
                warnings.warn("a")
            assert len(caught) == 2
            """
        )
        result = subprocess.run(
            [sys.executable, "-X", "context_aware_warnings=1", "-c", script],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        assert result.returncode == 0, result.stderr


@pytest.mark.skipif(sys.version_info < (3, 13), reason="warnings.deprecated added in 3.13")
class TestDeprecated:
    """`deprecated` | O(1) to decorate; each use is one `warn()`."""

    def test_each_call_warns_once_and_runs_the_original(self) -> None:
        @warnings.deprecated("use add()")  # type: ignore[attr-defined]
        def plus(a: int, b: int) -> int:
            return a + b

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            results = [plus(1, 2) for _ in range(3)]

        assert results == [3, 3, 3]
        assert [w.category for w in caught] == [DeprecationWarning] * 3
        assert plus.__deprecated__ == "use add()"  # type: ignore[attr-defined]

    def test_a_class_warns_on_instantiation_and_subclassing(self) -> None:
        @warnings.deprecated("old class")  # type: ignore[attr-defined]
        class Old:
            pass

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Old()

            class Child(Old):
                pass

        assert [str(w.message) for w in caught] == ["old class", "old class"]

    def test_category_none_returns_the_object_itself(self) -> None:
        def quiet() -> int:
            return 1

        decorated = warnings.deprecated("gone", category=None)(quiet)  # type: ignore[attr-defined]

        assert decorated is quiet
        assert quiet.__deprecated__ == "gone"  # type: ignore[attr-defined]


class TestCategories:
    """The categories are built-in classes; a filter matches subclasses too."""

    CATEGORIES = [
        UserWarning,
        DeprecationWarning,
        PendingDeprecationWarning,
        SyntaxWarning,
        RuntimeWarning,
        FutureWarning,
        ImportWarning,
        UnicodeWarning,
        BytesWarning,
        ResourceWarning,
        EncodingWarning,
    ]

    def test_every_category_derives_from_warning(self) -> None:
        assert all(issubclass(category, Warning) for category in self.CATEGORIES)

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_an_error_filter_on_warning_raises_every_category(self, category: type) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Warning)
            with pytest.raises(category):
                warnings.warn("x", category, stacklevel=1)

    def test_warn_defaults_to_userwarning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn("plain", stacklevel=1)

        assert caught[0].category is UserWarning


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


def _needs_313(source: str) -> bool:
    return "warnings.deprecated" in source


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so filters and registries cannot
    leak between them, and asserts its own result. The `deprecated` block
    needs 3.13 and is skipped on older interpreters."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS
        assert sum(_needs_313(source) for _, source in blocks) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if _needs_313(source) and sys.version_info < (3, 13):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS - (sys.version_info < (3, 13))
        assert not failures, "\n\n".join(failures)

    def test_every_block_asserts_something(self) -> None:
        for line, source in _blocks():
            assert "assert" in source, f"{PAGE.name}:{line} runs but claims nothing"

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert len(caught) == 3" in s)
        mutated = source.replace("assert len(caught) == 3", "assert len(caught) == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "assert len(caught) == 1" in result.stderr
        assert "AssertionError" in result.stderr
