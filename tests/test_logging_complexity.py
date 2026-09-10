"""Evidence for docs/stdlib/logging.md.

Suppression, level caches and timestamp formatting have focused behavioral and
timing tests. Emitted calls vary handler count, message length and filter count
independently, counting formatting, written characters and filter invocations.
Fresh logger branches vary depth with fixed-length components and measure the
sum of retained prefix lengths; placeholder promotion counts descendant visits.
Handler-name snapshots and shutdown list copies have size/allocation checks.
Filter registration counts equality operations, including repeated registration.
BufferingFormatter construction stores its argument, while formatting tests
vary record count at empty output and output length at one record separately.
The O(r + K) formatting row explicitly assumes amortized string growth; repeated
concatenation is visible in released CPython 3.10 and 3.14 Lib/logging/__init__.py.
No allocator-independent worst-case concatenation time is inferred here.
basicConfig tests isolate the root and manager, count cache clears and handler
comparisons, and check the no-op path. All eight page examples run separately.

Outside these bounds: custom callbacks, exception and stack payloads, operating
system I/O costs and lock contention. No finite field-count bound captures
arbitrary filter, formatter, flush or close callbacks. Non-default format styles
and forced replacement of an existing handler set are not measured here.
"""

import io
import logging
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc
import weakref
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "logging.md"

EXPECTED_BLOCKS = 8

# Documented, but absent from the older interpreters. Each row must say so.
ADDED_AFTER_310 = {
    "getLevelNamesMapping": "3.11",
    "getHandlerByName": "3.12",
    "getHandlerNames": "3.12",
}


def best_ns(func: Callable[[], Any], repeats: int = 9, inner: int = 1) -> float:
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


def _documented_names() -> set[str]:
    """Every `logging.<name>` the Complexity Reference tables mention.

    Rows group families as `logging.debug/info/warning(...)`, so a
    slash-separated run after `logging.` names one function each.
    """
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("\n## The Level Check", start)
    names: set[str] = set()
    pattern = r"logging\.([A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*)"
    for group in re.findall(pattern, text[start:end]):
        names.update(group.split("/"))
    return names


def level_cache(logger: logging.Logger) -> dict[int, bool]:
    """`Logger._cache`, which typeshed does not declare but every supported
    version has; it is the only handle on the level memoization."""
    return logger._cache  # type: ignore[attr-defined]  # noqa: SLF001


@pytest.fixture
def captured() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    """An isolated logger writing to a string, torn down afterwards."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.Logger(f"isolated{id(stream)}")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    yield logger, stream
    handler.close()


class TestEveryPublicNameIsDocumented:
    """The tables have to name every entry in `logging.__all__`."""

    def test_no_exported_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(set(logging.__all__) - _documented_names())

        assert not missing, f"{len(missing)} exported names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - set(logging.__all__) - set(ADDED_AFTER_310))

        assert not unknown, f"the tables name attributes logging does not have: {unknown}"

    def test_every_later_addition_carries_its_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        for name, version in sorted(ADDED_AFTER_310.items()):
            owning = [row for row in rows if f"logging.{name}" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert version in owning[0], f"the {name} row should say {version}+: {owning[0]}"

    def test_the_additions_list_matches_this_interpreter(self) -> None:
        current = sys.version_info[:2]
        for name, version in ADDED_AFTER_310.items():
            introduced = tuple(int(part) for part in version.split("."))
            assert hasattr(logging, name) is (current >= introduced), (
                f"{name} on {current} does not match a {version}+ marker"
            )

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        assert 40 <= len(logging.__all__) <= 48, (
            f"logging exports {len(logging.__all__)} names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"getLogger", "basicConfig", "Formatter", "info", "warning"} <= documented
        thinned = documented - {"NullHandler"}
        assert set(logging.__all__) - thinned == {"NullHandler"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestASuppressedCallIsLazy:
    """The claim the page turns on: a call below the level builds no record and
    converts none of its arguments."""

    class Counting:
        """Records how many times it is converted to a string."""

        def __init__(self) -> None:
            self.conversions = 0

        def __str__(self) -> str:
            self.conversions += 1
            return "converted"

    def test_a_suppressed_call_never_converts_its_argument(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, _ = captured
        argument = self.Counting()

        logger.debug("value is %s", argument)

        assert argument.conversions == 0

    def test_an_emitted_call_converts_it_once(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, stream = captured
        argument = self.Counting()

        logger.info("value is %s", argument)

        assert argument.conversions == 1
        assert "value is converted" in stream.getvalue()

    def test_an_fstring_is_converted_whatever_the_level(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        """Which is the whole reason the page prefers the %s form."""
        logger, _ = captured
        argument = self.Counting()

        logger.debug(f"value is {argument}")  # noqa: G004 - the eager form is the point

        assert argument.conversions == 1

    def test_the_record_is_not_built_either(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, _ = captured
        built: list[logging.LogRecord] = []
        original = logging.getLogRecordFactory()

        def counting_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = original(*args, **kwargs)
            built.append(record)
            return record

        logging.setLogRecordFactory(counting_factory)
        try:
            logger.debug("suppressed")
            assert built == []
            logger.info("emitted")
            assert len(built) == 1
        finally:
            logging.setLogRecordFactory(original)

    @pytest.mark.timing
    def test_a_suppressed_call_is_far_cheaper_than_an_emitted_one(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, _ = captured

        suppressed_ns = best_ns(lambda: logger.debug("m %s", 1), inner=200)
        emitted_ns = best_ns(lambda: logger.info("m %s", 1), inner=200)

        ratio = emitted_ns / suppressed_ns
        assert ratio > 5, (
            f"an emitted call cost x{ratio:.2f} a suppressed one "
            f"({suppressed_ns:.0f}ns to {emitted_ns:.0f}ns)"
        )


class TestTheLevelCache:
    """`isEnabledFor()` | O(1) | O(1), and what invalidates it."""

    @pytest.fixture
    def logger(self) -> Iterator[logging.Logger]:
        made = logging.getLogger(f"cachetest{id(self)}")
        made.setLevel(logging.INFO)
        yield made
        made.setLevel(logging.NOTSET)
        logging.disable(logging.NOTSET)

    def test_the_answers_are_cached_per_level(self, logger: logging.Logger) -> None:
        logger.isEnabledFor(logging.DEBUG)
        logger.isEnabledFor(logging.INFO)

        assert level_cache(logger) == {logging.DEBUG: False, logging.INFO: True}

    def test_setting_a_level_empties_it(self, logger: logging.Logger) -> None:
        logger.isEnabledFor(logging.DEBUG)
        assert level_cache(logger)

        logger.setLevel(logging.DEBUG)

        assert level_cache(logger) == {}

    def test_disable_empties_it_too(self, logger: logging.Logger) -> None:
        logger.isEnabledFor(logging.DEBUG)
        assert level_cache(logger)

        logging.disable(logging.CRITICAL)

        assert level_cache(logger) == {}

    def test_disable_suppresses_everything_below_it(self, logger: logging.Logger) -> None:
        logging.disable(logging.CRITICAL)

        assert logger.isEnabledFor(logging.ERROR) is False

        logging.disable(logging.NOTSET)
        assert logger.isEnabledFor(logging.ERROR) is True


class TestGetLogger:
    """Known-name lookup and fresh dotted-name construction."""

    def test_the_same_name_gives_the_same_object(self) -> None:
        first = logging.getLogger("app.db.pool")
        second = logging.getLogger("app.db.pool")

        assert first is second

    def test_the_ancestors_are_created_on_the_way(self) -> None:
        unique = f"created{id(self)}"
        logging.getLogger(f"{unique}.a.b.c")

        registry = logging.Logger.manager.loggerDict
        for depth in range(1, 4):
            partial = ".".join([unique, *["a", "b", "c"][: depth - 1]])
            assert partial in registry, f"{partial} should have a placeholder"

    def test_the_root_ends_every_chain(self) -> None:
        assert logging.getLogger().name == "root"
        assert logging.getLogger("x.y").parent is not None

    @pytest.mark.timing
    def test_a_known_name_is_cheaper_than_a_new_dotted_one(self) -> None:
        logging.getLogger("known.name.for.timing")
        counter = [0]

        def fresh() -> None:
            counter[0] += 1
            logging.getLogger(f"fresh{id(self)}.a.b.c.d.e{counter[0]}")

        known_ns = best_ns(lambda: logging.getLogger("known.name.for.timing"), inner=200)
        fresh_ns = best_ns(fresh, inner=1, repeats=5)

        ratio = fresh_ns / known_ns
        assert ratio > 3, (
            f"a new six-component name cost x{ratio:.2f} a known one "
            f"({known_ns:.0f}ns to {fresh_ns:.0f}ns)"
        )


class TestFormatters:
    """`formatter.format(record)` | O(k) | O(k), and what `%(asctime)s` adds."""

    RECORD = logging.LogRecord("n", logging.INFO, "path", 1, "hello %s", ("world",), None)

    def test_the_message_is_built_from_msg_and_args(self) -> None:
        assert self.RECORD.getMessage() == "hello world"

    def test_a_plain_format_is_just_the_fields(self) -> None:
        formatter = logging.Formatter("%(levelname)s %(message)s")

        assert formatter.format(self.RECORD) == "INFO hello world"

    def test_asctime_adds_a_timestamp(self) -> None:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        formatted = formatter.format(self.RECORD)

        assert formatted.endswith("INFO hello world")
        assert len(formatted) > len("INFO hello world")

    @pytest.mark.timing
    def test_asctime_costs_noticeably_more(self) -> None:
        plain = logging.Formatter("%(levelname)s %(message)s")
        timed = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        plain_ns = best_ns(lambda: plain.format(self.RECORD), inner=50)
        timed_ns = best_ns(lambda: timed.format(self.RECORD), inner=50)

        ratio = timed_ns / plain_ns
        assert ratio > 1.4, (
            f"asctime cost x{ratio:.2f} ({plain_ns:.0f}ns to {timed_ns:.0f}ns); "
            "it adds a localtime and a strftime per record"
        )

    def test_the_output_grows_with_the_message(self) -> None:
        formatter = logging.Formatter("%(message)s")
        long_record = logging.LogRecord("n", logging.INFO, "p", 1, "x" * 10_000, None, None)

        assert len(formatter.format(long_record)) == 10_000


class TestFiltersRunPerRecord:
    """`O(f)` per record that gets past the level check."""

    def test_a_filter_can_drop_a_record(self, captured: tuple[logging.Logger, io.StringIO]) -> None:
        logger, stream = captured

        class OnlyEven(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                return getattr(record, "index", 0) % 2 == 0

        logger.addFilter(OnlyEven())
        for index in range(4):
            logger.info("record %s", index, extra={"index": index})

        assert stream.getvalue().split() == ["record", "0", "record", "2"]

    def test_every_filter_is_called(self, captured: tuple[logging.Logger, io.StringIO]) -> None:
        logger, _ = captured
        calls: list[str] = []

        class Recording(logging.Filter):
            def __init__(self, label: str) -> None:
                super().__init__()
                self.label = label

            def filter(self, record: logging.LogRecord) -> bool:
                calls.append(self.label)
                return True

        logger.addFilter(Recording("first"))
        logger.addFilter(Recording("second"))

        logger.info("m")

        assert calls == ["first", "second"]

    def test_an_ancestor_loggers_filters_are_not_consulted(self) -> None:
        """Which is why F counts the originating logger, not the whole chain."""
        calls: list[str] = []

        class Recording(logging.Filter):
            def __init__(self, tag: str) -> None:
                super().__init__()
                self.tag = tag

            def filter(self, record: logging.LogRecord) -> bool:
                calls.append(self.tag)
                return True

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        parent = logging.Logger(f"ancestor{id(self)}")
        parent.addHandler(handler)
        parent.setLevel(logging.INFO)
        parent.addFilter(Recording("ancestor-logger"))
        handler.addFilter(Recording("handler"))
        child = logging.Logger(f"{parent.name}.child")
        child.parent = parent
        child.setLevel(logging.INFO)
        child.addFilter(Recording("originating-logger"))

        child.info("m")

        assert calls == ["originating-logger", "handler"], calls
        assert stream.getvalue() == "m\n", "the ancestor's handler still received it"
        handler.close()

    def test_a_suppressed_record_reaches_no_filter(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, _ = captured
        calls: list[int] = []

        class Recording(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                calls.append(1)
                return True

        logger.addFilter(Recording())

        logger.debug("suppressed")

        assert calls == []


class TestLevels:
    """The integer constants and the name registry."""

    def test_the_constants_are_ordered(self) -> None:
        assert (
            logging.NOTSET
            < logging.DEBUG
            < logging.INFO
            < logging.WARNING
            < logging.ERROR
            < logging.CRITICAL
        )

    def test_the_deprecated_spellings_are_the_same_numbers(self) -> None:
        assert logging.WARN == logging.WARNING
        assert logging.FATAL == logging.CRITICAL

    def test_add_level_name_registers_both_directions(self) -> None:
        logging.addLevelName(25, "NOTICE")

        assert logging.getLevelName(25) == "NOTICE"
        assert logging.getLevelName("NOTICE") == 25

    def test_an_unknown_level_answers_with_a_string(self) -> None:
        assert logging.getLevelName(99) == "Level 99"

    @pytest.mark.skipif(
        not hasattr(logging, "getLevelNamesMapping"), reason="getLevelNamesMapping is 3.11+"
    )
    def test_the_mapping_is_a_fresh_dict(self) -> None:
        first = logging.getLevelNamesMapping()  # type: ignore[attr-defined]
        second = logging.getLevelNamesMapping()  # type: ignore[attr-defined]

        assert first == second
        assert first is not second
        assert first["INFO"] == logging.INFO


class TestHandlers:
    """Construction is O(1); `shutdown()` is O(handlers)."""

    def test_a_null_handler_discards(self) -> None:
        logger = logging.Logger("null.example")
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("nowhere")  # must not raise

    def test_a_file_handler_opens_eagerly(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "eager.log"

        handler = logging.FileHandler(str(path))
        try:
            assert path.exists()
        finally:
            handler.close()

    def test_delay_postpones_the_open(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "lazy.log"

        handler = logging.FileHandler(str(path), delay=True)
        try:
            assert not path.exists()
        finally:
            handler.close()

    def test_a_record_reaches_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "written.log"
        handler = logging.FileHandler(str(path))
        logger = logging.Logger("file.example")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("written")
        handler.close()

        assert path.read_text() == "written\n"

    def test_a_handler_level_filters_after_the_logger(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, stream = captured
        logger.setLevel(logging.DEBUG)
        logger.handlers[0].setLevel(logging.WARNING)

        logger.info("below the handler")
        logger.warning("above it")

        assert stream.getvalue() == "above it\n"


class TestStackDepthDoesNotMatter:
    """Measured because it is easy to assume otherwise: `findCaller()` stops at
    the first frame outside the logging module, so the stack below is not
    walked."""

    @staticmethod
    def _at_depth(depth: int, measure: Callable[[], float]) -> float:
        """Reach `depth` frames, then run `measure` there.

        Stack construction is outside the timed region.
        """
        if depth:
            return TestStackDepthDoesNotMatter._at_depth(depth - 1, measure)
        return measure()

    @pytest.mark.timing
    def test_find_caller_is_flat_in_stack_depth(self) -> None:
        logger = logging.getLogger("depth.example")

        shallow = self._at_depth(1, lambda: best_ns(lambda: logger.findCaller(False, 1), inner=50))
        deep = self._at_depth(400, lambda: best_ns(lambda: logger.findCaller(False, 1), inner=50))

        ratio = deep / shallow
        assert ratio < 2, (
            f"400 frames deep cost x{ratio:.2f} one frame deep "
            f"({shallow:.0f}ns to {deep:.0f}ns); findCaller should stop at the first caller"
        )


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
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
    """Every block runs in its own process, because logging's configuration is
    module-global and a block that reconfigures it would reach the next one."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_no_block_writes_outside_a_temporary_directory(self) -> None:
        """A logging example is one careless FileHandler from littering a repo."""
        for line, source in _blocks():
            if "FileHandler" in source:
                assert "tempfile" in source, (
                    f"{PAGE.name}:{line} opens a FileHandler without a temporary directory"
                )

    def test_every_block_runs(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")
            assert os.listdir(workdir) == ["_block.py"], (
                f"{PAGE.name}:{line} left files behind: {os.listdir(workdir)}"
            )

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import logging\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr


def test_the_temporary_directory_helper_is_reachable() -> None:
    """tempfile is imported for the FileHandler example's guard above."""
    with tempfile.TemporaryDirectory() as folder:
        assert pathlib.Path(folder).is_dir()


@pytest.fixture
def isolated_root(monkeypatch: pytest.MonkeyPatch) -> Iterator[logging.RootLogger]:
    root = logging.RootLogger(logging.INFO)
    manager = logging.Manager(root)
    monkeypatch.setattr(logging, "root", root)
    monkeypatch.setattr(logging.Logger, "manager", manager)
    try:
        yield root
    finally:
        for handler in root.handlers:
            handler.close()


class TestEmissionDimensions:
    @pytest.mark.parametrize("module_call", [False, True])
    @pytest.mark.parametrize("handlers", [1, 5])
    @pytest.mark.parametrize("length", [10, 10_000])
    @pytest.mark.parametrize("filters", [1, 3])
    def test_each_handler_formats_writes_and_filters(
        self,
        isolated_root: logging.RootLogger,
        module_call: bool,
        handlers: int,
        length: int,
        filters: int,
    ) -> None:
        isolated_root.handlers.clear()  # pytest installs capture handlers at call entry
        conversions = filter_calls = written = formats = 0

        class Argument:
            def __str__(self) -> str:
                nonlocal conversions
                conversions += 1
                return "x" * length

        class Sink:
            def write(self, text: str) -> None:
                nonlocal written
                written += len(text)

            def flush(self) -> None:
                pass

        class Formatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                nonlocal formats
                formats += 1
                return super().format(record)

        class Filter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                nonlocal filter_calls
                filter_calls += 1
                return True

        for _ in range(filters):
            isolated_root.addFilter(Filter())
        for _ in range(handlers):
            handler = logging.StreamHandler(Sink())
            handler.setFormatter(Formatter("%(message)s"))
            for _ in range(filters):
                handler.addFilter(Filter())
            isolated_root.addHandler(handler)
        emit = logging.info if module_call else isolated_root.info
        emit("%s", Argument())
        assert conversions == formats == handlers
        assert written == handlers * (length + 1)
        assert filter_calls == (handlers + 1) * filters


class TestLoggerCreationDimensions:
    @pytest.mark.parametrize("depth", [10, 100])
    def test_fresh_branch_retains_quadratic_prefix_text(self, depth: int) -> None:
        manager = logging.Manager(logging.RootLogger(logging.WARNING))
        name = ".".join(["x"] * depth)
        made = manager.getLogger(name)
        expected = {".".join(["x"] * count) for count in range(1, depth + 1)}
        assert set(manager.loggerDict) == expected
        assert sum(map(len, manager.loggerDict)) == depth * depth
        assert all(
            isinstance(manager.loggerDict[prefix], logging.PlaceHolder)
            for prefix in expected - {name}
        )
        assert manager.getLogger(name) is made

    @pytest.mark.parametrize("count", [10, 100])
    def test_promoting_a_placeholder_visits_its_descendants(self, count: int) -> None:
        manager = logging.Manager(logging.RootLogger(logging.WARNING))
        children = [manager.getLogger(f"parent.child{i}") for i in range(count)]
        placeholder: Any = manager.loggerDict["parent"]
        visits = []

        class Descendants(dict):
            def keys(self):  # type: ignore[override]  # noqa: ANN202
                for child in super().keys():
                    visits.append(child)
                    yield child

        placeholder.loggerMap = Descendants(placeholder.loggerMap)
        parent = manager.getLogger("parent")
        assert visits == children
        assert all(child.parent is parent for child in children)


class TestHandlerStorage:
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="named handler APIs are 3.12+")
    @pytest.mark.parametrize("count", [10, 100])
    def test_named_handler_snapshot_is_independent(
        self, count: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(logging, "_handlers", weakref.WeakValueDictionary())
        handlers = [logging.NullHandler() for _ in range(count)]
        try:
            for index, handler in enumerate(handlers):
                handler.name = f"handler{index}"
            first = logging.getHandlerNames()  # type: ignore[attr-defined]
            second = logging.getHandlerNames()  # type: ignore[attr-defined]
            assert isinstance(first, frozenset)
            assert first == second and first is not second
            assert len(first) == count
            assert logging.getHandlerByName("handler0") is handlers[0]  # type: ignore[attr-defined]
            handlers[0].name = "renamed"
            assert "handler0" in first and "renamed" not in first
            assert "renamed" in logging.getHandlerNames()  # type: ignore[attr-defined]
        finally:
            for handler in handlers:
                handler.close()

    def test_shutdown_allocates_a_reference_snapshot(self) -> None:
        peaks = []
        for count in (10, 1_000):
            closes = flushes = 0

            class Handler:
                def acquire(self) -> None:
                    pass

                def release(self) -> None:
                    pass

                def flush(self) -> None:
                    nonlocal flushes
                    flushes += 1

                def close(self) -> None:
                    nonlocal closes
                    closes += 1

            handlers = [Handler() for _ in range(count)]
            refs = [weakref.ref(handler) for handler in handlers]
            tracemalloc.start()
            try:
                logging.shutdown(refs)  # type: ignore[arg-type]
                peaks.append(tracemalloc.get_traced_memory()[1])
            finally:
                tracemalloc.stop()
            assert closes == flushes == count
        assert peaks[1] > peaks[0] * 5, peaks


class TestFilterRegistration:
    @pytest.mark.parametrize("handler_target", [False, True])
    @pytest.mark.parametrize("count", [10, 100])
    def test_repeated_additions_check_all_existing_filters(
        self, handler_target: bool, count: int
    ) -> None:
        comparisons = 0

        class Filter(logging.Filter):
            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return self is other

        target = logging.Handler() if handler_target else logging.Logger("filters")
        try:
            for _ in range(count):
                target.addFilter(Filter())
            assert comparisons == count * (count - 1) // 2
            comparisons = 0
            added = Filter()
            target.addFilter(added)
            assert comparisons == count
            target.addFilter(added)
            assert len(target.filters) == count + 1
        finally:
            if isinstance(target, logging.Handler):
                target.close()


class TestBufferingFormatterDimensions:
    def test_construction_stores_the_line_formatter_without_using_it(self) -> None:
        class Line(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                raise AssertionError("construction must not format a record")

        line = Line("%(message)s")
        buffered = logging.BufferingFormatter(line)
        assert buffered.linefmt is line
        assert buffered.format([]) == ""

    @pytest.mark.parametrize("count", [1, 100])
    def test_record_traversal_with_empty_output(self, count: int) -> None:
        calls = 0

        class Line(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                nonlocal calls
                calls += 1
                return super().format(record)

        records = [logging.LogRecord("n", logging.INFO, "p", 1, "", (), None) for _ in range(count)]
        assert all("message" not in vars(record) for record in records)
        formatter = logging.BufferingFormatter(Line("%(message)s"))
        assert formatter.format(records) == ""
        assert calls == count
        assert all(record.message == "" for record in records)

    def test_one_record_can_allocate_arbitrary_output(self) -> None:
        retained = []
        formatter = logging.BufferingFormatter(logging.Formatter("[%(message)s]"))
        for length in (100, 10_000):
            record = logging.LogRecord("n", logging.INFO, "p", 1, "x" * length, (), None)
            tracemalloc.start()
            try:
                result = formatter.format([record])
                retained.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()
            assert result == "[" + "x" * length + "]"
        assert retained[1] > retained[0] * 20, retained


class TestBasicConfigDimensions:
    @pytest.mark.parametrize("count", [10, 100])
    def test_level_clears_every_logger_cache(
        self, isolated_root: logging.RootLogger, count: int
    ) -> None:
        isolated_root.handlers.clear()
        cleared = []

        class Cache(dict):
            def clear(self) -> None:
                cleared.append(self)
                super().clear()

        loggers = [isolated_root.manager.getLogger(f"logger{i}") for i in range(count)]
        for logger in loggers:
            logger._cache = Cache({logging.INFO: True})  # type: ignore[attr-defined]
        logging.basicConfig(level=logging.DEBUG)
        assert len(cleared) == count
        assert all(level_cache(logger) == {} for logger in loggers)
        assert isolated_root.level == logging.DEBUG

    @pytest.mark.parametrize("count", [10, 100])
    def test_supplying_handlers_has_quadratic_duplicate_checks(
        self, isolated_root: logging.RootLogger, count: int
    ) -> None:
        isolated_root.handlers.clear()
        comparisons = 0

        class Handler(logging.NullHandler):
            __hash__ = object.__hash__

            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return self is other

        handlers = [Handler() for _ in range(count)]
        logging.basicConfig(handlers=handlers)
        assert comparisons == count * (count - 1) // 2
        assert len(isolated_root.handlers) == count
        assert all(
            left is right for left, right in zip(isolated_root.handlers, handlers, strict=True)
        )

    def test_existing_handler_makes_configuration_a_noop(
        self, isolated_root: logging.RootLogger
    ) -> None:
        isolated_root.handlers.clear()
        original = logging.NullHandler()
        isolated_root.addHandler(original)
        level_cache(isolated_root)[logging.INFO] = True

        def forbidden():  # noqa: ANN202
            raise AssertionError("no-op configuration must not consume handlers")
            yield  # pragma: no cover

        logging.basicConfig(level=logging.DEBUG, handlers=forbidden())
        assert isolated_root.handlers == [original]
        assert isolated_root.level == logging.INFO
        assert level_cache(isolated_root) == {logging.INFO: True}
