"""Tests for docs/stdlib/logging.md.

The page prices a suppressed call as one cache lookup, an emitted record as a
walk up the logger hierarchy with one formatting and one write per accepting
handler, and the module's global operations - `setLevel()`, `shutdown()`,
`dictConfig()` - as linear in the registry of loggers or the list of live
handlers rather than in their arguments. Most rows are settled by counting at
the boundary the row names: a `__str__` conversion, a formatter call, a filter
call, a stream write or flush, a `stat()`, a `rename()`, a connection attempt,
an SMTP session. Where only a stopwatch separates the growth classes, two sizes
are timed and the ratio asserted.

Measurement scope:

* A suppressed call converts a counting `__str__` argument zero times and
  builds no record through a counting record factory; an emitted call does
  each once. An f-string argument is converted before the call. In a timing
  test an emitted `info()` costs more than 5x a suppressed `debug()`.
* The level cache holds one entry per level asked; `setLevel()` and
  `disable()` empty it, assigning `level` directly does not, and a `Logger`
  built directly keeps its cached answer through its own `setLevel()`. On a chain
  of loggers whose `level` and `handlers` reads are counted through
  `__getattribute__`, `getEffectiveLevel()` and a cache miss read 90 more
  levels at depth 100 than at depth 10, a cache hit reads none, and
  `hasHandlers()` reads depth + 1 handler lists, or 6 when the sixth logger
  stops propagation.
* `log()` with a string level raises `TypeError` under `raiseExceptions`
  and emits nothing without it.
* A fresh dotted name of depth 10 and 100 leaves depth placeholders whose
  keys total depth² characters; naming a placeholder with 10 and 100
  children below it visits exactly those children; a second request is the
  same object; `getChild()` is the joined name's logger; a `Logger` built
  directly is absent from the registry. `getChildren()` yields every one of
  201 registry entries to return the 100 direct children (3.12+).
* Emission over 1 and 5 handlers, 10 and 10,000 output characters, 1 and 3
  filters per filterer, and the module-level and logger-level entry points:
  conversions and formatter calls equal the handler count, written
  characters equal handlers x (length + 1), and filter calls equal
  (handlers + 1) x filters. `addHandler()` compares a counting `__eq__`
  handler against every existing one: 45 and 4,950 comparisons for 10 and
  100 handlers, and a repeat is not added. A record with no handler on its
  walk reaches `lastResort`; a handler below the record's level still
  counts as found. A disabled logger calls no filter.
* `findCaller()` one and 400 frames deep costs under 2x in a timing test;
  with `stack_info=True` the returned text grows by at least 400 lines
  between 5 and 500 distinct frames, and `handleError()` with
  `raiseExceptions` writes at least 150 more lines to stderr 200 frames deep
  than 5. `stacklevel=2` names the caller's caller.
* `LogRecord()` converts nothing; `getMessage()` converts once per call, so
  twice over two calls. `makeRecord()` copies each `extra` key and raises
  `KeyError` for `message` and for an existing attribute. `makeLogRecord()`
  exposes every key of its dict.
* A `Formatter` rejects a fieldless format unless `validate=False`, formats
  the same record in all three styles, merges `defaults` with the record once
  per `format()` (a counting `__or__` sees 2 merges over 2 calls), reports
  `usesTime()` by the format, renders `created=0` as 1970 through
  `time.gmtime`, returns the stack text it is given, and calls
  `formatException()` once over three `format()` calls on two formatters
  because `exc_text` is cached on the record. The traceback text grows by at
  least 400 lines between exceptions raised 5 and 500 distinct frames deep.
  `%(asctime)s` costs more than 1.4x a plain format in a timing test, and
  10,000 message characters give 10,000 output characters, and
  `formatTime()` is called once per format with `%(asctime)s` and never
  without it.
  `BufferingFormatter` construction calls no formatter; formatting 1 and 100
  empty records calls the line formatter once each; one record of 100 and
  10,000 characters retains more than 20x the allocation.
* `Filter('a.b')` passes `a.b` and `a.b.c` and rejects `a.bc` and `b.a.b`;
  the empty name passes everything. The originating logger's filters run
  before the handler's and an ancestor logger's never run, every filter is
  called in order until one rejects, a suppressed record reaches none, and
  registering 10 and 100 filters on a logger or a handler makes 45 and
  4,950 equality comparisons with a repeat not added. On 3.12+ a filter's
  returned record replaces the original for the handler; before 3.12 the
  original is what the handler sees.
* `Handler()` appends a weak reference to the shutdown list; a name registers
  it for lookup and `close()` unregisters it; `handle()` returns `False` when
  a filter rejects, and otherwise the record itself from 3.12 and `True`
  before; `emit()` raises `NotImplementedError`;
  `handleError()` writes nothing when `raiseExceptions` is false. A
  `StreamHandler` flushes once per record over 5 records, `setStream()`
  flushes and returns the old stream and returns `None` for the same one,
  and `terminator` is appended as given. A `FileHandler` opens eagerly, or
  on the first record with `delay=True`, and `close()` drops the stream. A
  `NullHandler` calls none of its filters and has no lock.
* A `LoggerAdapter` replaces the call's `extra` with its own, merges them
  with the call winning under `merge_extra=True` (3.13+), never calls
  `process()` for a suppressed call, and delegates `isEnabledFor()`,
  `getEffectiveLevel()`, `hasHandlers()`, `setLevel()`, `name` and
  `manager` to its logger.
* `logging.info()` on a root with no handlers adds one `StreamHandler` and
  a second call adds none; `captureWarnings(True)` routes a warning through
  the `py.warnings` logger; `setLoggerClass()` rejects a non-`Logger` and
  `getLogger()` builds the accepted subclass; `shutdown()` over 100 and
  10,000 weakly referenced handlers flushes and closes each, newest first,
  skips the flush when `flushOnClose` is false from 3.12, and peaks more
  than 10x the allocation. `basicConfig(level=...)` clears 10 and 100 counting caches,
  `handlers=` of 10 and 100 compares 45 and 4,950 times, a root that has a
  handler makes it a no-op that consumes nothing, and `force=True` closes
  the old handlers. `getHandlerNames()` is a fresh frozenset of 10 and 100
  names (3.12+).
* `dictConfig()` on an isolated root slices the name of every one of 10 and
  1,000 registered loggers sorted after the one it configures, disables the
  ones it does not name unless `disable_existing_loggers` is false, closes
  the two live handlers on the shutdown list, registers each handler under
  its name, attaches 10 and 100 handlers to one logger with 45 and 4,950
  equality comparisons, rejects a config without `version`, resets an existing
  descendant of a configured logger to `NOTSET`, no handlers and propagation
  instead of disabling it, 10 and 100 such descendants costing 110 and
  10,100 cache clears, and with `incremental=True` slices, closes and
  disables nothing while clearing the cache of each of 10 registered loggers
  once per configured level, 3 levels giving 30 clears. `fileConfig()` from a file and from a
  stream registers its handler, sets its logger's level and disables an
  existing logger. `listen(0)` returns a thread that is not alive with no
  listener installed, and `stopListening()` with nothing listening is a
  no-op. On 3.12+ `dictConfig()` gives a `QueueHandler` a listener wired to
  the named handlers.
* `RotatingFileHandler` with `maxBytes` formats the second and later records
  twice each, the first record into an empty file once from 3.12.6 and twice
  before, and with `maxBytes=0` once; before 3.12.6 it calls
  `os.path.exists()` on the path once per record and from 3.12.6 only for
  the due rollover, twice: the regular-file check and the rename's;
  `doRollover()` with 3 and 6 existing backups
  makes 3 and 6 renames; a page-sized log rolls into exactly `backupCount`
  backups. `TimedRotatingFileHandler.shouldRollover()` formats nothing and
  is false on a fresh file; `getFilesToDelete()` calls `os.listdir()` once
  on a directory of 50 unrelated entries and 5 dated backups, returns the 3
  oldest for `backupCount=2` and none for `backupCount=10`; `doRollover()`
  leaves `backupCount` backups plus the new one. `WatchedFileHandler` stats
  the path once per record over 5 records and writes to a new file after
  the old one is renamed away.
* `SocketHandler` connects nothing at construction; with `makeSocket()`
  raising and `retryStart` at an hour, three records make one attempt, are
  pickled three times and set a retry time, and a retry time in the past
  makes the next record try again. `makePickle()`
  is a 4-byte length plus a pickle whose `args` and `exc_info` are `None`
  and which has no `message`, formats the record only when it carries
  `exc_info`, and leaves `exc_text` on the record. `DatagramHandler`
  makes an unconnected datagram socket and sends one datagram per record.
* `SysLogHandler` with a missing Unix socket path constructs without error
  and has `createSocket()` exactly from 3.11;
  `encodePriority('user', 'info')` is 14; `mapPriority()` maps an unknown
  name to `warning`; `emit()` sends `<14>` + ident + message + NUL in one
  call, and no NUL with `append_nul` false.
* `SMTPHandler.emit()` opens one SMTP session per record over two records,
  through a patched `smtplib.SMTP`; `HTTPHandler.mapLogRecord()` is the
  record's `__dict__` itself and `emit()` makes one request per record with
  the URL-encoded record as the POST body. `NTEventLogHandler` off Windows
  prints its notice, returns 1 and 0 from the two constant getters and
  emits nothing.
* `BufferingHandler` holds records unformatted and empties at capacity
  without forwarding; `MemoryHandler` forwards at capacity and at
  `flushLevel`, delivers `INFO` records to an `ERROR` target, keeps 10
  records above a capacity of 3 with no target, and after `close()` with
  `flushOnClose=False` keeps its records and drops its target.
* `QueueHandler.prepare()` formats once on the caller and returns a copy
  with `msg` set to the text, traceback and stack included, `args`,
  `exc_info`, `exc_text` and `stack_info` cleared and an `extra` attribute
  kept; a bounded queue that is full drops the record. The
  listener delivers an `INFO` record to an `ERROR` handler unless
  `respect_handler_level` is set, `stop()` returns after all 100 queued
  records are handled, a second `stop()` is a no-op (3.13+), a second
  `start()` raises (3.13.4+), and the listener is a context manager (3.14+).
* Every fenced Python block runs in its own subprocess and working
  directory, leaves no file behind, and a mutated assertion in one of them
  is asserted to fail.

Not settled here:

* Costs of the destination: a stream's write, a socket's connect and send,
  name resolution in `SysLogHandler`, an SMTP or HTTP exchange. The tests
  count the operations and never perform them.
* `NTEventLogHandler` on Windows: the registry write at construction, the
  `ReportEvent` per record and `getEventType()`'s map. No run this project
  performs reaches them.
* The L log L sort in `dictConfig()` and `fileConfig()` and the per-name
  scan being additive: the slice count shows the scan, and the sort is
  read from Lib/logging/config.py.
* `Formatter.formatTime()` as O(1) for a fixed `datefmt`, and
  `usesTime()` as a substring search of the format: read from
  Lib/logging/__init__.py.
* `BufferingFormatter.format()` as O(r + K) assumes CPython's in-place
  string concatenation keeps the repeated `+` amortized; the tests vary the
  record count at empty output and the output at one record, not both.
* `LoggerAdapter._log` appears in the official inventory and is private;
  the page does not document it.
* Lock contention between threads sharing a handler, `%`-style formatting
  with a mapping argument, custom `namer` and `rotator` callables, and the
  `ext://` and `cfg://` conversions inside `dictConfig()` are not varied.
"""

from __future__ import annotations

import io
import logging
import logging.config
import logging.handlers
import os
import pathlib
import queue
import re
import smtplib
import socket
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
import weakref
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "logging.md"
EXPECTED_BLOCKS = 15


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


def level_cache(logger: logging.Logger) -> dict[int, bool]:
    """`Logger._cache`, the only handle on the level memoization."""
    return logger._cache  # type: ignore[attr-defined]


def make_record(msg: str = "hello", level: int = logging.INFO, **extra: Any) -> logging.LogRecord:
    record = logging.LogRecord("n", level, "path", 1, msg, (), None)
    record.__dict__.update(extra)
    return record


def call_through(depth: int, func: Callable[[], Any]) -> Any:
    """Call `func` beneath `depth` distinct one-line functions.

    Recursion would not do: the traceback module folds repeated frames into
    one "[Previous line repeated N more times]" line.
    """
    namespace: dict[str, Any] = {"func": func}
    source = "def f0():\n    return func()\n" + "".join(
        f"def f{i}():\n    return f{i - 1}()\n" for i in range(1, depth + 1)
    )
    exec(source, namespace)  # noqa: S102
    return namespace[f"f{depth}"]()


class CountingFormatter(logging.Formatter):
    """Counts `format()` and `formatException()` calls."""

    def __init__(self, fmt: str = "%(message)s") -> None:
        super().__init__(fmt)
        self.formats = 0
        self.tracebacks = 0

    def format(self, record: logging.LogRecord) -> str:
        self.formats += 1
        return super().format(record)

    def formatException(self, ei: Any) -> str:
        self.tracebacks += 1
        return super().formatException(ei)


class RecordingHandler(logging.Handler):
    """Keeps every record it is asked to emit."""

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self.emitted: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.emitted.append(record)


class Converted:
    """Counts how many times it is turned into a string."""

    def __init__(self) -> None:
        self.conversions = 0

    def __str__(self) -> str:
        self.conversions += 1
        return "converted"


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


@pytest.fixture
def handler_registry(monkeypatch: pytest.MonkeyPatch) -> list[weakref.ref[logging.Handler]]:
    """A private shutdown list and name registry, so tests see only their own handlers."""
    shutdown_list: list[weakref.ref[logging.Handler]] = []
    monkeypatch.setattr(logging, "_handlerList", shutdown_list)
    monkeypatch.setattr(logging, "_handlers", weakref.WeakValueDictionary())
    return shutdown_list


@pytest.fixture
def isolated_root(
    monkeypatch: pytest.MonkeyPatch, handler_registry: list[weakref.ref[logging.Handler]]
) -> Iterator[logging.RootLogger]:
    """A private root and registry in place of the module's, torn down afterwards.

    pytest attaches its capture handlers to `logging.getLogger()` when the
    test body starts, which is this root by then, so tests clear its handlers.
    """
    root = logging.RootLogger(logging.WARNING)
    manager = logging.Manager(root)
    monkeypatch.setattr(logging, "root", root)
    monkeypatch.setattr(logging.Logger, "manager", manager)
    try:
        yield root
    finally:
        for handler in root.handlers:
            handler.close()


class TestASuppressedCallIsLazy:
    """`Logger.debug()` - suppressed | O(1) | O(1): no record, no formatting."""

    def test_a_suppressed_call_never_converts_its_argument(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, _ = captured
        argument = Converted()

        logger.debug("value is %s", argument)

        assert argument.conversions == 0

    def test_an_emitted_call_converts_it_once(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, stream = captured
        argument = Converted()

        logger.info("value is %s", argument)

        assert argument.conversions == 1
        assert "value is converted" in stream.getvalue()

    def test_an_fstring_is_converted_whatever_the_level(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, _ = captured
        argument = Converted()

        logger.debug(f"value is {argument}")

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
            assert logging.getLogRecordFactory() is counting_factory
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


class CountingLogger(logging.Logger):
    """A logger that counts reads of `level` and `handlers`."""

    reads: dict[str, int] = {"level": 0, "handlers": 0}

    def __getattribute__(self, name: str) -> Any:
        if name in ("level", "handlers"):
            CountingLogger.reads[name] += 1
        return super().__getattribute__(name)

    @classmethod
    def reset(cls) -> None:
        cls.reads = {"level": 0, "handlers": 0}

    @classmethod
    def chain(cls, depth: int) -> list[CountingLogger]:
        """`depth + 1` loggers, each the parent of the one before it."""
        nodes = [CountingLogger(f"chain{i}") for i in range(depth + 1)]
        for lower, upper in zip(nodes, nodes[1:], strict=False):
            lower.parent = upper
        return nodes


class TestTheLevelCache:
    """`Logger.isEnabledFor()` | O(1) cached; O(a) on a miss, and what
    invalidates it."""

    @pytest.fixture
    def logger(self) -> Iterator[logging.Logger]:
        made = logging.getLogger(f"cachetest{id(self)}")
        made.setLevel(logging.INFO)
        threshold = made.manager.disable
        yield made
        made.setLevel(logging.NOTSET)
        logging.disable(threshold)

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
        assert logger.isEnabledFor(logging.ERROR) is False

        logging.disable(logging.NOTSET)
        assert logger.isEnabledFor(logging.ERROR) is True

    def test_assigning_level_directly_leaves_the_cache_stale(self, logger: logging.Logger) -> None:
        assert logger.isEnabledFor(logging.DEBUG) is False

        logger.level = logging.DEBUG

        assert logger.isEnabledFor(logging.DEBUG) is False, "the stale answer is served"
        logger.setLevel(logging.DEBUG)
        assert logger.isEnabledFor(logging.DEBUG) is True

    def test_a_direct_logger_is_outside_every_sweep(self) -> None:
        direct = logging.Logger(f"direct{id(self)}")
        direct.setLevel(logging.INFO)
        assert direct.isEnabledFor(logging.DEBUG) is False

        threshold = direct.manager.disable
        direct.setLevel(logging.DEBUG)
        logging.disable(logging.NOTSET)
        logging.disable(threshold)

        assert level_cache(direct) == {logging.DEBUG: False}
        assert direct.isEnabledFor(logging.DEBUG) is False, "its own setLevel() misses it"
        level_cache(direct).clear()
        assert direct.isEnabledFor(logging.DEBUG) is True

    @staticmethod
    def _level_reads(depth: int, probe: Callable[[logging.Logger], Any]) -> int:
        nodes = CountingLogger.chain(depth)
        nodes[-1].setLevel(logging.WARNING)
        CountingLogger.reset()
        probe(nodes[0])
        return CountingLogger.reads["level"]

    def test_get_effective_level_reads_one_level_per_ancestor(self) -> None:
        shallow = self._level_reads(10, lambda leaf: leaf.getEffectiveLevel())
        deep = self._level_reads(100, lambda leaf: leaf.getEffectiveLevel())

        assert deep - shallow == 90, (shallow, deep)

    def test_a_cache_miss_walks_the_ancestors_and_a_hit_does_not(self) -> None:
        nodes = CountingLogger.chain(100)
        nodes[-1].setLevel(logging.WARNING)

        CountingLogger.reset()
        assert nodes[0].isEnabledFor(logging.INFO) is False
        miss = CountingLogger.reads["level"]
        CountingLogger.reset()
        assert nodes[0].isEnabledFor(logging.INFO) is False
        hit = CountingLogger.reads["level"]

        assert miss > 100 and hit == 0, (miss, hit)

    def test_has_handlers_stops_at_handlers_or_at_propagate_false(self) -> None:
        for depth in (10, 100):
            nodes = CountingLogger.chain(depth)
            nodes[-1].addHandler(logging.NullHandler())

            CountingLogger.reset()
            assert nodes[0].hasHandlers() is True
            assert CountingLogger.reads["handlers"] == depth + 1

            nodes[5].propagate = False
            CountingLogger.reset()
            assert nodes[0].hasHandlers() is False
            assert CountingLogger.reads["handlers"] == 6


class TestGetLogger:
    """`logging.getLogger()` | O(1) known; O(d·ℓ + c) the first time."""

    def test_the_same_name_gives_the_same_object(self) -> None:
        first = logging.getLogger("app.db.pool")
        second = logging.getLogger("app.db.pool")

        assert first is second
        assert first.getChild("conn") is logging.getLogger("app.db.pool.conn")

    def test_the_root_ends_every_chain(self) -> None:
        assert logging.getLogger().name == "root"
        assert logging.getLogger("root") is logging.getLogger()
        assert logging.getLogger("x.y").parent is not None

    def test_direct_construction_bypasses_the_registry(self) -> None:
        name = f"direct{id(self)}"

        made = logging.Logger(name)

        assert name not in logging.Logger.manager.loggerDict
        assert made.parent is None
        assert logging.getLogger(name) is not made

    @pytest.mark.parametrize("depth", [10, 100])
    def test_a_fresh_branch_retains_one_prefix_per_component(self, depth: int) -> None:
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
        assert made.parent is manager.root

    @pytest.mark.parametrize("count", [10, 100])
    def test_naming_a_placeholder_visits_its_descendants(self, count: int) -> None:
        manager = logging.Manager(logging.RootLogger(logging.WARNING))
        children = [manager.getLogger(f"parent.child{i}") for i in range(count)]
        placeholder: Any = manager.loggerDict["parent"]
        visits: list[logging.Logger] = []

        class Descendants(dict):  # type: ignore[type-arg]
            def keys(self) -> Any:
                for child in super().keys():
                    visits.append(child)
                    yield child

        placeholder.loggerMap = Descendants(placeholder.loggerMap)
        parent = manager.getLogger("parent")

        assert visits == children
        assert all(child.parent is parent for child in children)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="getChildren is 3.12+")
    def test_get_children_scans_the_whole_registry(self) -> None:
        manager = logging.Manager(logging.RootLogger(logging.WARNING))
        for index in range(100):
            manager.getLogger(f"a.b{index}")
            manager.getLogger(f"c{index}")
        visited = 0

        class Registry(dict):  # type: ignore[type-arg]
            def values(self) -> Any:
                nonlocal visited
                for value in super().values():
                    visited += 1
                    yield value

        manager.loggerDict = Registry(manager.loggerDict)
        parent = manager.getLogger("a")
        visited = 0

        children = parent.getChildren()  # type: ignore[attr-defined]

        assert visited == len(manager.loggerDict) == 201
        assert len(children) == 100
        assert all(child.parent is parent for child in children)

    def test_log_requires_an_integer_level(
        self, captured: tuple[logging.Logger, io.StringIO], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        logger, stream = captured

        monkeypatch.setattr(logging, "raiseExceptions", True)
        with pytest.raises(TypeError):
            logger.log("INFO", "m")  # type: ignore[arg-type]

        monkeypatch.setattr(logging, "raiseExceptions", False)
        logger.log("INFO", "m")  # type: ignore[arg-type]
        assert stream.getvalue() == ""

    def test_warn_warns_before_delegating(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, stream = captured

        with pytest.warns(DeprecationWarning):
            logger.warn("old spelling")

        assert stream.getvalue() == "old spelling\n"

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


class TestEmissionDimensions:
    """The same call - emitted | O(a + h + F + h·k): each accepting handler
    formats and writes independently, and each filterer's filters run once."""

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
        isolated_root.handlers.clear()
        isolated_root.setLevel(logging.INFO)
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


class TestHandlersOnALogger:
    """`Logger.addHandler()` | O(n), `Logger.callHandlers()` and `lastResort`."""

    @pytest.mark.parametrize("count", [10, 100])
    def test_add_handler_compares_against_every_existing_one(self, count: int) -> None:
        comparisons = 0

        class Handler(logging.NullHandler):
            __hash__ = object.__hash__

            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return self is other

        logger = logging.Logger("handlers")
        handlers = [Handler() for _ in range(count)]
        for handler in handlers:
            logger.addHandler(handler)

        assert comparisons == count * (count - 1) // 2
        logger.addHandler(handlers[0])
        assert len(logger.handlers) == count

        logger.removeHandler(handlers[0])
        assert len(logger.handlers) == count - 1
        logger.removeHandler(handlers[0])
        assert len(logger.handlers) == count - 1

    def test_a_record_with_no_handler_anywhere_goes_to_last_resort(
        self, isolated_root: logging.RootLogger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolated_root.handlers.clear()
        stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", stderr)
        logger = isolated_root.manager.getLogger("orphan")

        logger.warning("nowhere to go")

        assert stderr.getvalue() == "nowhere to go\n"

    def test_a_handler_below_the_level_still_counts_as_found(
        self, isolated_root: logging.RootLogger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolated_root.handlers.clear()
        stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", stderr)
        found = RecordingHandler(logging.ERROR)
        isolated_root.addHandler(found)
        logger = isolated_root.manager.getLogger("orphan.child")

        logger.warning("dropped")

        assert stderr.getvalue() == ""
        assert found.emitted == []

    def test_a_disabled_logger_calls_no_filter(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, stream = captured
        calls: list[int] = []
        logger.addFilter(lambda record: calls.append(1) or True)
        logger.disabled = True

        logger.info("m")
        logger.handle(make_record())

        assert calls == []
        assert stream.getvalue() == ""


class TestFindCaller:
    """`Logger.findCaller()` | O(s): flat in the stack below the caller, and
    O(D) with `stack_info=True`."""

    @staticmethod
    def _at_depth(depth: int, measure: Callable[[], float]) -> float:
        if depth:
            return TestFindCaller._at_depth(depth - 1, measure)
        return measure()

    @pytest.mark.timing
    def test_without_stack_info_it_is_flat_in_stack_depth(self) -> None:
        logger = logging.getLogger("depth.example")

        shallow = self._at_depth(1, lambda: best_ns(lambda: logger.findCaller(False, 1), inner=50))
        deep = self._at_depth(400, lambda: best_ns(lambda: logger.findCaller(False, 1), inner=50))

        ratio = deep / shallow
        assert ratio < 2, (
            f"400 frames deep cost x{ratio:.2f} one frame deep "
            f"({shallow:.0f}ns to {deep:.0f}ns); findCaller should stop at the first caller"
        )

    def test_stack_info_formats_the_whole_stack(self) -> None:
        logger = logging.Logger("stack")

        def lines() -> int:
            _, _, _, sinfo = logger.findCaller(True, 1)
            assert sinfo is not None and sinfo.startswith("Stack (most recent call last):")
            return sinfo.count("\n")

        shallow = call_through(5, lines)
        deep = call_through(500, lines)

        assert deep - shallow >= 400, (shallow, deep)

    def test_stacklevel_climbs_past_the_caller(self) -> None:
        logger = logging.Logger("stacklevel")
        handler = RecordingHandler()
        logger.addHandler(handler)

        def inner(level: int) -> str:
            logger.warning("where", stacklevel=level)
            return handler.emitted[-1].funcName

        def outer(level: int) -> str:
            return inner(level)

        assert outer(1) == "inner"
        assert outer(2) == "outer"
        handler.close()


class TestLogRecord:
    """`logging.LogRecord()` | O(p): `msg % args` is deferred to `getMessage()`."""

    def test_construction_converts_nothing_and_get_message_converts_per_call(self) -> None:
        argument = Converted()

        record = logging.LogRecord("n", logging.INFO, "dir/file.py", 1, "%s", (argument,), None)

        assert argument.conversions == 0
        assert record.filename == "file.py" and record.module == "file"
        assert record.getMessage() == "converted"
        assert record.getMessage() == "converted"
        assert argument.conversions == 2

    def test_make_record_copies_extra_and_rejects_collisions(self) -> None:
        logger = logging.Logger("extra")

        record = logger.makeRecord("n", logging.INFO, "p", 1, "m", (), None, extra={"a": 1, "b": 2})

        assert (record.a, record.b) == (1, 2)  # type: ignore[attr-defined]
        for key in ("message", "name"):
            with pytest.raises(KeyError):
                logger.makeRecord("n", logging.INFO, "p", 1, "m", (), None, extra={key: 1})

    def test_make_log_record_exposes_every_key(self) -> None:
        record = logging.makeLogRecord({"msg": "m", "levelno": logging.INFO, "custom": 1})

        assert record.getMessage() == "m"
        assert record.custom == 1  # type: ignore[attr-defined]


class TestHandlerBase:
    """`logging.Handler()` | O(1): registration, naming, `handle()` and
    `handleError()`."""

    def test_construction_registers_for_shutdown(
        self, handler_registry: list[weakref.ref[logging.Handler]]
    ) -> None:
        handler = RecordingHandler()

        assert handler_registry[-1]() is handler
        assert handler.lock is not None
        handler.acquire()
        handler.release()

    def test_a_name_registers_the_handler_and_close_unregisters_it(
        self, handler_registry: list[weakref.ref[logging.Handler]]
    ) -> None:
        handler = RecordingHandler()

        handler.name = "named"

        assert handler.get_name() == "named"
        assert logging._handlers["named"] is handler  # type: ignore[attr-defined]
        handler.set_name("renamed")
        assert "named" not in logging._handlers  # type: ignore[attr-defined]
        handler.close()
        assert "renamed" not in logging._handlers  # type: ignore[attr-defined]

    def test_handle_runs_the_filters_and_returns_the_record_or_false(self) -> None:
        handler = RecordingHandler()
        record = make_record()

        returned = handler.handle(record)
        assert returned is (record if sys.version_info >= (3, 12) else True)
        assert handler.emitted == [record]

        handler.addFilter(lambda candidate: False)
        assert handler.handle(record) is False
        assert handler.emitted == [record]

    def test_the_base_emit_is_abstract_and_format_has_a_default(self) -> None:
        handler = logging.Handler()

        assert handler.format(make_record()) == "hello"
        with pytest.raises(NotImplementedError):
            handler.emit(make_record())
        handler.close()

    @pytest.fixture
    def failing_handler(self) -> Iterator[logging.Handler]:
        class Failing(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    raise RuntimeError("write failed")
                except RuntimeError:
                    self.handleError(record)

        handler = Failing()
        yield handler
        handler.close()

    def test_handle_error_is_silent_unless_raise_exceptions(
        self, failing_handler: logging.Handler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", stderr)
        monkeypatch.setattr(logging, "raiseExceptions", False)

        failing_handler.emit(make_record())

        assert stderr.getvalue() == ""

    def test_handle_error_prints_the_whole_call_stack(
        self, failing_handler: logging.Handler, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(logging, "raiseExceptions", True)

        def lines() -> int:
            stderr = io.StringIO()
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(sys, "stderr", stderr)
                failing_handler.emit(make_record())
            text = stderr.getvalue()
            assert text.startswith("--- Logging error ---") and "Call stack:" in text
            return text.count("\n")

        shallow = call_through(5, lines)
        deep = call_through(200, lines)

        assert deep - shallow >= 150, (shallow, deep)


class TestStreamAndFileHandlers:
    """`StreamHandler.emit()` | O(k): one write and one flush per record;
    `FileHandler` opens eagerly unless delayed; `NullHandler` skips its filters."""

    class Sink:
        def __init__(self) -> None:
            self.writes: list[str] = []
            self.flushes = 0

        def write(self, text: str) -> None:
            self.writes.append(text)

        def flush(self) -> None:
            self.flushes += 1

    def test_every_record_is_written_once_and_flushed_once(self) -> None:
        sink = self.Sink()
        handler = logging.StreamHandler(sink)

        for _ in range(5):
            handler.emit(make_record())

        assert sink.writes == ["hello\n"] * 5
        assert sink.flushes == 5
        handler.close()

    def test_set_stream_flushes_the_old_stream_and_returns_it(self) -> None:
        first, second = self.Sink(), self.Sink()
        handler = logging.StreamHandler(first)

        assert handler.setStream(first) is None
        assert first.flushes == 0
        assert handler.setStream(second) is first
        assert first.flushes == 1
        handler.emit(make_record())
        assert second.writes == ["hello\n"] and first.writes == []
        handler.close()

    def test_the_terminator_is_appended_as_given(self) -> None:
        sink = self.Sink()
        handler = logging.StreamHandler(sink)
        handler.terminator = ""

        handler.emit(make_record())

        assert sink.writes == ["hello"]
        handler.close()

    def test_a_file_handler_opens_eagerly(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "eager.log"

        handler = logging.FileHandler(str(path))
        try:
            assert path.exists()
        finally:
            handler.close()
        assert handler.stream is None

    def test_delay_postpones_the_open_to_the_first_record(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "lazy.log"

        handler = logging.FileHandler(str(path), delay=True)
        try:
            assert not path.exists()
            handler.emit(make_record())
            assert path.exists()
        finally:
            handler.close()
        assert path.read_text() == "hello\n"

    def test_a_record_reaches_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "written.log"
        handler = logging.FileHandler(str(path))
        logger = logging.Logger("file.example")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

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

    def test_a_null_handler_skips_its_filters_and_has_no_lock(self) -> None:
        handler = logging.NullHandler()
        calls: list[int] = []
        handler.addFilter(lambda record: calls.append(1) or True)
        logger = logging.Logger("null.example")
        logger.addHandler(handler)

        logger.warning("nowhere")
        handler.handle(make_record())

        assert calls == []
        assert handler.lock is None


class TestFormatters:
    """`Formatter.format()` | O(k + t): the exception text is rendered once per
    record, and `%(asctime)s` is the expensive directive."""

    RECORD = logging.LogRecord("n", logging.INFO, "path", 1, "hello %s", ("world",), None)

    def test_a_plain_format_is_just_the_fields(self) -> None:
        assert self.RECORD.getMessage() == "hello world"
        assert logging.Formatter("%(levelname)s %(message)s").format(self.RECORD) == (
            "INFO hello world"
        )

    def test_validation_rejects_a_fieldless_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid format"):
            logging.Formatter("no fields here")

        assert logging.Formatter("no fields here", validate=False).format(self.RECORD) == (
            "no fields here"
        )

    def test_every_style_and_defaults(self) -> None:
        assert logging.Formatter("{levelname} {message}", style="{").format(self.RECORD) == (
            "INFO hello world"
        )
        assert logging.Formatter("$levelname $message", style="$").format(self.RECORD) == (
            "INFO hello world"
        )
        merges = 0

        class Defaults(dict):  # type: ignore[type-arg]
            def __or__(self, other: Any) -> Any:
                nonlocal merges
                merges += 1
                return dict.__or__(self, other)

        formatter = logging.Formatter("%(x)s %(message)s", defaults=Defaults(x="d"))
        assert formatter.format(self.RECORD) == "d hello world"
        assert formatter.format(self.RECORD) == "d hello world"
        assert merges == 2, "the defaults are merged with the record on every format"

    def test_uses_time_follows_the_format(self) -> None:
        assert logging.Formatter("%(message)s").usesTime() is False
        assert logging.Formatter("%(asctime)s %(message)s").usesTime() is True

    def test_format_time_uses_the_converter(self) -> None:
        formatter = logging.Formatter()
        formatter.converter = time.gmtime
        record = make_record()
        record.created = 0
        record.msecs = 0

        assert formatter.formatTime(record, "%Y") == "1970"
        assert formatter.formatTime(record) == "1970-01-01 00:00:00,000"

    def test_asctime_adds_a_timestamp(self) -> None:
        class Counting(logging.Formatter):
            conversions = 0

            def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
                Counting.conversions += 1
                return super().formatTime(record, datefmt)

        formatted = Counting("%(asctime)s %(levelname)s %(message)s").format(self.RECORD)

        assert formatted.endswith("INFO hello world")
        assert len(formatted) > len("INFO hello world")
        assert Counting.conversions == 1
        Counting("%(levelname)s %(message)s").format(self.RECORD)
        assert Counting.conversions == 1, "a format without asctime converts no time"

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

    def test_format_stack_returns_what_it_is_given(self) -> None:
        stack = "Stack (most recent call last):\n  File x"
        record = make_record()
        record.stack_info = stack

        assert logging.Formatter().formatStack(stack) is stack
        assert logging.Formatter().format(record) == "hello\n" + stack

    @staticmethod
    def _exception_record() -> logging.LogRecord:
        try:
            raise ValueError("boom")
        except ValueError:
            return logging.LogRecord("n", logging.ERROR, "p", 1, "failed", (), sys.exc_info())

    def test_the_exception_text_is_rendered_once_per_record(self) -> None:
        record = self._exception_record()
        first, second = CountingFormatter(), CountingFormatter()

        outputs = [first.format(record), first.format(record), second.format(record)]

        assert first.tracebacks == 1 and second.tracebacks == 0
        assert record.exc_text is not None and record.exc_text in outputs[0]
        assert outputs[0] == outputs[1] == outputs[2]
        assert "ValueError: boom" in outputs[2]

    def test_the_exception_text_grows_with_the_traceback(self) -> None:
        def raise_here() -> None:
            raise ValueError("bottom")

        def lines(depth: int) -> int:
            try:
                call_through(depth, raise_here)
            except ValueError:
                return logging.Formatter().formatException(sys.exc_info()).count("\n")
            raise AssertionError("the chain did not raise")

        assert lines(500) - lines(5) >= 400


class TestBufferingFormatterDimensions:
    """`BufferingFormatter.format()` | O(r + K): one line formatter call per
    record, output proportional to the text."""

    def test_construction_stores_the_line_formatter_without_using_it(self) -> None:
        class Line(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                raise AssertionError("construction must not format a record")

        line = Line("%(message)s")
        buffered = logging.BufferingFormatter(line)

        assert buffered.linefmt is line
        assert buffered.format([]) == ""
        assert buffered.formatHeader([]) == "" and buffered.formatFooter([]) == ""

    @pytest.mark.parametrize("count", [1, 100])
    def test_record_traversal_with_empty_output(self, count: int) -> None:
        line = CountingFormatter()
        records = [logging.LogRecord("n", logging.INFO, "p", 1, "", (), None) for _ in range(count)]
        formatter = logging.BufferingFormatter(line)

        assert formatter.format(records) == ""
        assert line.formats == count
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


class TestFilters:
    """`Filterer.filter()` | O(F): the originating logger's filters, then each
    reached handler's, each stopping at the first rejection."""

    def test_the_built_in_filter_is_a_dotted_prefix_test(self) -> None:
        scoped = logging.Filter("a.b")

        assert scoped.filter(make_record(name="a.b"))
        assert scoped.filter(make_record(name="a.b.c"))
        assert not scoped.filter(make_record(name="a.bc"))
        assert not scoped.filter(make_record(name="b.a.b"))
        assert logging.Filter().filter(make_record(name="anything"))

    def test_a_filter_can_drop_a_record(self, captured: tuple[logging.Logger, io.StringIO]) -> None:
        logger, stream = captured

        class OnlyEven(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                return getattr(record, "index", 0) % 2 == 0

        logger.addFilter(OnlyEven())
        for index in range(4):
            logger.info("record %s", index, extra={"index": index})

        assert stream.getvalue().split() == ["record", "0", "record", "2"]

    def test_every_filter_is_called_in_order_until_one_rejects(
        self, captured: tuple[logging.Logger, io.StringIO]
    ) -> None:
        logger, stream = captured
        calls: list[str] = []

        def recording(label: str, verdict: bool) -> Callable[[logging.LogRecord], bool]:
            def filter_(record: logging.LogRecord) -> bool:
                calls.append(label)
                return verdict

            return filter_

        rejecting = recording("second", False)
        logger.addFilter(recording("first", True))
        logger.addFilter(rejecting)
        logger.addFilter(recording("third", True))

        logger.info("m")
        assert calls == ["first", "second"]
        assert stream.getvalue() == ""

        logger.removeFilter(rejecting)
        calls.clear()
        logger.info("m")
        assert calls == ["first", "third"]
        assert stream.getvalue() == "m\n"

    def test_an_ancestor_loggers_filters_are_not_consulted(self) -> None:
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
        logger.addFilter(lambda record: calls.append(1) or True)

        logger.debug("suppressed")

        assert calls == []

    @pytest.mark.parametrize("handler_target", [False, True])
    @pytest.mark.parametrize("count", [10, 100])
    def test_registration_compares_against_every_existing_filter(
        self, handler_target: bool, count: int
    ) -> None:
        comparisons = 0

        class Filter(logging.Filter):
            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return self is other

        target = RecordingHandler() if handler_target else logging.Logger("filters")
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

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="replacement records are 3.12+")
    def test_a_returned_record_replaces_the_original(self) -> None:
        handler = RecordingHandler()
        replacement = make_record("replaced")
        handler.addFilter(lambda record: replacement)  # type: ignore[arg-type, return-value]

        assert handler.handle(make_record("original")) is replacement
        assert handler.emitted == [replacement]
        handler.close()

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="before 3.12 the record is kept")
    def test_a_returned_record_is_only_a_true_verdict(self) -> None:
        handler = RecordingHandler()
        original = make_record("original")
        handler.addFilter(lambda record: make_record("replaced"))  # type: ignore[arg-type, return-value]

        handler.handle(original)

        assert handler.emitted == [original]
        handler.close()


class TestLoggerAdapter:
    """`LoggerAdapter.process()` | O(1); O(e) with `merge_extra`, reached only
    by a call that passed the level check."""

    @pytest.fixture
    def target(self) -> Iterator[tuple[logging.Logger, RecordingHandler]]:
        logger = logging.Logger("adapter")
        handler = RecordingHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        yield logger, handler
        handler.close()

    def test_process_replaces_the_calls_extra(
        self, target: tuple[logging.Logger, RecordingHandler]
    ) -> None:
        logger, handler = target
        adapter = logging.LoggerAdapter(logger, {"request": "r-1"})

        adapter.info("served", extra={"request": "call", "other": 1})

        (record,) = handler.emitted
        assert record.request == "r-1"  # type: ignore[attr-defined]
        assert not hasattr(record, "other")

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="merge_extra is 3.13+")
    def test_merge_extra_merges_with_the_call_winning(
        self, target: tuple[logging.Logger, RecordingHandler]
    ) -> None:
        logger, handler = target
        adapter = logging.LoggerAdapter(logger, {"request": "r-1", "kept": True}, merge_extra=True)  # type: ignore[call-arg]

        adapter.info("served", extra={"request": "call"})

        (record,) = handler.emitted
        assert (record.request, record.kept) == ("call", True)  # type: ignore[attr-defined]

    def test_a_suppressed_call_never_reaches_process(
        self, target: tuple[logging.Logger, RecordingHandler]
    ) -> None:
        logger, handler = target
        processed = 0

        class Counting(logging.LoggerAdapter):  # type: ignore[type-arg]
            def process(self, msg: Any, kwargs: Any) -> Any:
                nonlocal processed
                processed += 1
                return super().process(msg, kwargs)

        adapter = Counting(logger, {"k": 1})
        adapter.debug("suppressed")
        assert processed == 0 and handler.emitted == []
        adapter.info("emitted")
        assert processed == 1 and len(handler.emitted) == 1

    def test_the_rest_delegates_to_the_logger(
        self, target: tuple[logging.Logger, RecordingHandler]
    ) -> None:
        logger, _ = target
        adapter = logging.LoggerAdapter(logger, {})

        assert adapter.isEnabledFor(logging.DEBUG) is False
        adapter.setLevel(logging.DEBUG)
        assert logger.level == logging.DEBUG
        assert adapter.getEffectiveLevel() == logging.DEBUG
        assert adapter.hasHandlers() is True
        assert adapter.name == logger.name
        assert adapter.manager is logger.manager
        with pytest.warns(DeprecationWarning):
            adapter.warn("old spelling")


class TestModuleLevelFunctions:
    """`logging.info()` and friends: the root's cost, after a `basicConfig()`
    when the root has no handlers."""

    def test_a_bare_root_is_configured_once(
        self, isolated_root: logging.RootLogger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolated_root.handlers.clear()
        stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", stderr)

        logging.warning("first")
        logging.warning("second")

        assert len(isolated_root.handlers) == 1
        assert stderr.getvalue() == "WARNING:root:first\nWARNING:root:second\n"
        with pytest.warns(DeprecationWarning):
            logging.warn("third")
        assert stderr.getvalue().endswith("WARNING:root:third\n")

    def test_capture_warnings_routes_through_the_py_warnings_logger(
        self, isolated_root: logging.RootLogger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        isolated_root.handlers.clear()
        monkeypatch.setattr(warnings, "showwarning", warnings.showwarning)
        monkeypatch.setattr(logging, "_warnings_showwarning", None)
        handler = RecordingHandler()
        logging.getLogger("py.warnings").addHandler(handler)
        logging.captureWarnings(True)
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            warnings.warn("careful", UserWarning, stacklevel=1)
        logging.captureWarnings(False)

        (record,) = handler.emitted
        assert record.name == "py.warnings" and "careful" in record.getMessage()
        handler.close()

    def test_set_logger_class_checks_the_class_and_get_logger_uses_it(
        self, isolated_root: logging.RootLogger
    ) -> None:
        class Custom(logging.Logger):
            pass

        previous = logging.getLoggerClass()
        with pytest.raises(TypeError):
            logging.setLoggerClass(dict)  # type: ignore[arg-type]
        logging.setLoggerClass(Custom)
        try:
            assert logging.getLoggerClass() is Custom
            assert isinstance(logging.getLogger("custom.example"), Custom)
        finally:
            logging.setLoggerClass(previous)

    def test_shutdown_flushes_and_closes_newest_first(self) -> None:
        events: list[tuple[str, int]] = []

        class Handler:
            def __init__(self, index: int, flush_on_close: bool = True) -> None:
                self.index = index
                self.flushOnClose = flush_on_close

            def acquire(self) -> None:
                pass

            def release(self) -> None:
                pass

            def flush(self) -> None:
                events.append(("flush", self.index))

            def close(self) -> None:
                events.append(("close", self.index))

        handlers = [Handler(0), Handler(1, flush_on_close=False), Handler(2)]
        refs = [weakref.ref(handler) for handler in handlers]

        logging.shutdown(refs)  # type: ignore[arg-type]

        expected = [
            ("flush", 2),
            ("close", 2),
            ("flush", 1),
            ("close", 1),
            ("flush", 0),
            ("close", 0),
        ]
        if sys.version_info >= (3, 12):
            expected.remove(("flush", 1))
        assert events == expected

    def test_shutdown_allocates_a_reference_snapshot(self) -> None:
        peaks = []
        for count in (100, 10_000):
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
        assert peaks[1] > peaks[0] * 10, peaks


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

    def test_add_level_name_registers_both_directions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(logging, "_levelToName", dict(logging._levelToName))  # type: ignore[attr-defined]
        monkeypatch.setattr(logging, "_nameToLevel", dict(logging._nameToLevel))  # type: ignore[attr-defined]
        logging.addLevelName(25, "NOTICE")

        assert logging.getLevelName(25) == "NOTICE"
        assert logging.getLevelName("NOTICE") == 25

    def test_an_unknown_level_answers_with_a_string(self) -> None:
        assert logging.getLevelName(99) == "Level 99"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="getLevelNamesMapping is 3.11+")
    def test_the_mapping_is_a_fresh_dict(self) -> None:
        first = logging.getLevelNamesMapping()  # type: ignore[attr-defined]
        second = logging.getLevelNamesMapping()  # type: ignore[attr-defined]

        assert first == second
        assert first is not second
        assert first["INFO"] == logging.INFO


class TestBasicConfigDimensions:
    """`logging.basicConfig()` | O(1) with handlers present; O(n² + L) otherwise."""

    @pytest.mark.parametrize("count", [10, 100])
    def test_level_clears_every_logger_cache(
        self, isolated_root: logging.RootLogger, count: int
    ) -> None:
        isolated_root.handlers.clear()
        cleared = []

        class Cache(dict):  # type: ignore[type-arg]
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

        def forbidden() -> Iterator[logging.Handler]:
            raise AssertionError("no-op configuration must not consume handlers")
            yield  # pragma: no cover

        logging.basicConfig(level=logging.DEBUG, handlers=forbidden())

        assert isolated_root.handlers == [original]
        assert isolated_root.level == logging.WARNING
        assert level_cache(isolated_root) == {logging.INFO: True}

    def test_force_closes_the_old_handlers(self, isolated_root: logging.RootLogger) -> None:
        isolated_root.handlers.clear()
        old = [RecordingHandler(), RecordingHandler()]
        closed: list[logging.Handler] = []
        for handler in old:
            handler.close = lambda handler=handler: closed.append(handler)  # type: ignore[method-assign]
            isolated_root.addHandler(handler)
        new = RecordingHandler()

        logging.basicConfig(handlers=[new], force=True)

        assert closed == old
        assert isolated_root.handlers == [new]


class TestHandlerStorage:
    """`logging.getHandlerNames()` | O(n): a fresh snapshot each call."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="named handler APIs are 3.12+")
    @pytest.mark.parametrize("count", [10, 100])
    def test_named_handler_snapshot_is_independent(
        self, count: int, handler_registry: list[weakref.ref[logging.Handler]]
    ) -> None:
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


class SlicedName(str):
    """A logger name that counts how often it is sliced."""

    slices = 0

    def __getitem__(self, key: Any) -> str:
        SlicedName.slices += 1
        return str.__getitem__(self, key)


class TestDictConfig:
    """`logging.config.dictConfig()` | O(C + H + L log L + n·L): every live
    handler closed, every registered name scanned, every unnamed logger disabled."""

    @pytest.mark.parametrize("count", [10, 1_000])
    def test_each_configured_logger_scans_the_names_sorted_after_it(
        self, isolated_root: logging.RootLogger, count: int
    ) -> None:
        isolated_root.handlers.clear()
        manager = isolated_root.manager
        existing = [manager.getLogger(SlicedName(f"zz{i}")) for i in range(count)]
        configured = manager.getLogger(SlicedName("aa"))
        SlicedName.slices = 0

        logging.config.dictConfig({"version": 1, "loggers": {"aa": {"level": "DEBUG"}}})

        assert SlicedName.slices == count
        assert configured.level == logging.DEBUG and configured.disabled is False
        assert all(logger.disabled for logger in existing)

    def test_existing_loggers_survive_when_asked(self, isolated_root: logging.RootLogger) -> None:
        isolated_root.handlers.clear()
        existing = isolated_root.manager.getLogger("legacy")

        logging.config.dictConfig(
            {"version": 1, "disable_existing_loggers": False, "loggers": {"aa": {}}}
        )

        assert existing.disabled is False

    def test_incremental_touches_only_what_it_names(
        self,
        isolated_root: logging.RootLogger,
        handler_registry: list[weakref.ref[logging.Handler]],
    ) -> None:
        isolated_root.handlers.clear()
        manager = isolated_root.manager
        existing = [manager.getLogger(SlicedName(f"zz{i}")) for i in range(10)]
        configured = [manager.getLogger(f"aa{i}") for i in range(3)]
        live = RecordingHandler()
        SlicedName.slices = 0
        cleared: list[int] = []

        class Cache(dict):  # type: ignore[type-arg]
            def clear(self) -> None:
                cleared.append(1)
                super().clear()

        for logger in existing:
            logger._cache = Cache()  # type: ignore[attr-defined]

        logging.config.dictConfig(
            {
                "version": 1,
                "incremental": True,
                "loggers": {logger.name: {"level": "INFO"} for logger in configured},
            }
        )

        assert SlicedName.slices == 0
        assert all(logger.level == logging.INFO for logger in configured)
        assert not any(logger.disabled for logger in existing)
        assert live._closed is False  # type: ignore[attr-defined]
        assert len(cleared) == 3 * len(existing), "each level set sweeps every registered cache"
        live.close()

    @pytest.mark.parametrize("count", [10, 100])
    def test_descendants_of_a_named_logger_are_reset_not_disabled(
        self, isolated_root: logging.RootLogger, count: int
    ) -> None:
        isolated_root.handlers.clear()
        manager = isolated_root.manager
        manager.getLogger("app")
        children = [manager.getLogger(f"app.child{i}") for i in range(count)]
        cleared: list[int] = []

        class Cache(dict):  # type: ignore[type-arg]
            def clear(self) -> None:
                cleared.append(1)
                super().clear()

        for child in children:
            child.setLevel(logging.DEBUG)
            child.addHandler(logging.NullHandler())
            child.propagate = False
        for child in children:
            child._cache = Cache()  # type: ignore[attr-defined]
        unrelated = manager.getLogger("other")

        logging.config.dictConfig({"version": 1, "loggers": {"app": {"level": "INFO"}}})

        assert not any(child.disabled for child in children)
        assert all(
            (child.level, child.handlers, child.propagate) == (logging.NOTSET, [], True)
            for child in children
        )
        assert unrelated.disabled is True
        assert len(cleared) == (count + 1) * count, "one sweep for the parent and one per reset"

    def test_every_live_handler_is_closed_first(
        self,
        isolated_root: logging.RootLogger,
        handler_registry: list[weakref.ref[logging.Handler]],
    ) -> None:
        isolated_root.handlers.clear()
        live = [RecordingHandler(), RecordingHandler()]
        assert [ref() for ref in handler_registry][-2:] == live

        logging.config.dictConfig({"version": 1})

        assert all(handler._closed for handler in live)  # type: ignore[attr-defined]
        assert handler_registry == []

    def test_handlers_are_registered_under_their_names(
        self,
        isolated_root: logging.RootLogger,
        handler_registry: list[weakref.ref[logging.Handler]],
    ) -> None:
        isolated_root.handlers.clear()
        stream = io.StringIO()

        logging.config.dictConfig(
            {
                "version": 1,
                "handlers": {"memory": {"class": "logging.StreamHandler", "stream": stream}},
                "loggers": {"app": {"level": "DEBUG", "handlers": ["memory"]}},
            }
        )

        handler = logging._handlers["memory"]  # type: ignore[attr-defined]
        assert isinstance(handler, logging.StreamHandler) and handler.stream is stream
        assert isolated_root.manager.getLogger("app").handlers == [handler]
        with pytest.raises(ValueError, match="version"):
            logging.config.dictConfig({})

    @pytest.mark.parametrize("count", [10, 100])
    def test_handlers_attach_to_a_logger_with_the_usual_scan(
        self,
        isolated_root: logging.RootLogger,
        handler_registry: list[weakref.ref[logging.Handler]],
        count: int,
    ) -> None:
        isolated_root.handlers.clear()
        comparisons = 0

        class Handler(logging.NullHandler):
            __hash__ = object.__hash__

            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return self is other

        logging.config.dictConfig(
            {
                "version": 1,
                "handlers": {f"h{i}": {"()": Handler} for i in range(count)},
                "loggers": {"app": {"handlers": [f"h{i}" for i in range(count)]}},
            }
        )

        assert len(isolated_root.manager.getLogger("app").handlers) == count
        assert comparisons == count * (count - 1) // 2

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="queue handler configuration is 3.12+")
    def test_a_queue_handler_gets_a_listener(
        self,
        isolated_root: logging.RootLogger,
        handler_registry: list[weakref.ref[logging.Handler]],
    ) -> None:
        isolated_root.handlers.clear()

        logging.config.dictConfig(
            {
                "version": 1,
                "handlers": {
                    "target": {"class": "logging.NullHandler"},
                    "queued": {"class": "logging.handlers.QueueHandler", "handlers": ["target"]},
                },
            }
        )

        queued = logging._handlers["queued"]  # type: ignore[attr-defined]
        assert isinstance(queued, logging.handlers.QueueHandler)
        listener = queued.listener  # type: ignore[attr-defined]
        assert isinstance(listener, logging.handlers.QueueListener)
        assert listener.handlers == (logging._handlers["target"],)  # type: ignore[attr-defined]


CONFIG_FILE = """\
[loggers]
keys=root,app

[handlers]
keys=h

[formatters]
keys=f

[logger_root]
level=WARNING
handlers=

[logger_app]
level=DEBUG
handlers=h
qualname=app

[handler_h]
class=StreamHandler
formatter=f
args=()

[formatter_f]
format=%(message)s
"""


class TestFileConfig:
    """`logging.config.fileConfig()` | O(S + H + L log L + n·L): parse the
    file, then the same passes as `dictConfig()`."""

    def test_a_file_and_a_stream_both_configure(
        self,
        isolated_root: logging.RootLogger,
        handler_registry: list[weakref.ref[logging.Handler]],
        tmp_path: pathlib.Path,
    ) -> None:
        isolated_root.handlers.clear()
        existing = isolated_root.manager.getLogger("legacy")
        path = tmp_path / "logging.ini"
        path.write_text(CONFIG_FILE, encoding="utf-8")

        logging.config.fileConfig(str(path))

        handler = logging._handlers["h"]  # type: ignore[attr-defined]
        assert isinstance(handler, logging.StreamHandler)
        app = isolated_root.manager.getLogger("app")
        assert app.level == logging.DEBUG and app.handlers == [handler]
        assert existing.disabled is True

        existing.disabled = False
        logging.config.fileConfig(io.StringIO(CONFIG_FILE), disable_existing_loggers=False)

        assert existing.disabled is False
        assert logging._handlers["h"] is not handler  # type: ignore[attr-defined]


class TestListen:
    """`logging.config.listen()` | O(1): a thread that is not yet started."""

    def test_nothing_is_bound_until_start(self) -> None:
        thread = logging.config.listen(0)

        assert not thread.is_alive()
        assert logging.config._listener is None  # type: ignore[attr-defined]
        logging.config.stopListening()
        assert logging.config._listener is None  # type: ignore[attr-defined]


def counting_path_calls(
    monkeypatch: pytest.MonkeyPatch, module: Any, name: str, path: str
) -> list[str]:
    """Count calls of `module.name` whose first argument is `path`."""
    calls: list[str] = []
    original = getattr(module, name)

    def wrapper(target: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(target, (str, bytes, os.PathLike)) and os.fspath(target) == path:
            calls.append(name)
        return original(target, *args, **kwargs)

    monkeypatch.setattr(module, name, wrapper)
    return calls


class TestRotatingFileHandler:
    """`RotatingFileHandler.shouldRollover()` | O(k): the record is formatted to
    measure it; `doRollover()` | O(b)."""

    def test_a_record_is_formatted_twice_when_max_bytes_is_set(
        self, tmp_path: pathlib.Path
    ) -> None:
        handler = logging.handlers.RotatingFileHandler(
            str(tmp_path / "a.log"), maxBytes=10_000, backupCount=1
        )
        formatter = CountingFormatter()
        handler.setFormatter(formatter)
        try:
            handler.emit(make_record())
            first = formatter.formats
            formatter.formats = 0
            handler.emit(make_record())
            handler.emit(make_record())
        finally:
            handler.close()

        assert first == (1 if sys.version_info >= (3, 12, 6) else 2), "into an empty file"
        assert formatter.formats == 4

    def test_a_record_is_formatted_once_without_max_bytes(self, tmp_path: pathlib.Path) -> None:
        handler = logging.handlers.RotatingFileHandler(str(tmp_path / "a.log"))
        formatter = CountingFormatter()
        handler.setFormatter(formatter)
        try:
            handler.emit(make_record())
            handler.emit(make_record())
        finally:
            handler.close()

        assert formatter.formats == 2

    @pytest.mark.skipif(sys.version_info >= (3, 12, 6), reason="before 3.12.6 every record stats")
    def test_before_3126_every_record_stats_the_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = str(tmp_path / "a.log")
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=10_000, backupCount=1)
        exists = counting_path_calls(monkeypatch, os.path, "exists", handler.baseFilename)
        try:
            for _ in range(5):
                handler.emit(make_record())
        finally:
            handler.close()

        assert len(exists) == 5

    @pytest.mark.skipif(
        sys.version_info < (3, 12, 6), reason="from 3.12.6 only a due rollover stats"
    )
    def test_from_3126_only_a_due_rollover_stats_the_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = str(tmp_path / "a.log")
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=10_000, backupCount=1)
        exists = counting_path_calls(monkeypatch, os.path, "exists", handler.baseFilename)
        try:
            for _ in range(5):
                handler.emit(make_record())
            assert exists == []
            handler.emit(make_record("x" * 10_000))
        finally:
            handler.close()

        assert len(exists) == 2, "the regular-file check, then rotate()'s own check"

    @pytest.mark.parametrize("backups", [3, 6])
    def test_a_rollover_renames_each_backup_up_one(
        self, tmp_path: pathlib.Path, backups: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "r.log"
        for index in range(1, backups + 1):
            (tmp_path / f"r.log.{index}").write_text(f"backup {index}")
        handler = logging.handlers.RotatingFileHandler(str(path), maxBytes=10, backupCount=backups)
        renames: list[tuple[str, str]] = []
        original = os.rename

        def counting(source: Any, dest: Any, *args: Any, **kwargs: Any) -> Any:
            renames.append((os.path.basename(source), os.path.basename(dest)))
            return original(source, dest, *args, **kwargs)

        monkeypatch.setattr(os, "rename", counting)
        try:
            handler.emit(make_record("first"))
            renames.clear()
            handler.doRollover()
        finally:
            handler.close()

        assert len(renames) == backups
        assert renames[-1] == ("r.log", "r.log.1")
        assert (tmp_path / "r.log.1").read_text() == "first\n"
        assert (tmp_path / f"r.log.{backups}").read_text() == f"backup {backups - 1}"
        assert not (tmp_path / f"r.log.{backups + 1}").exists()

    def test_a_growing_log_keeps_backup_count_files(self, tmp_path: pathlib.Path) -> None:
        handler = logging.handlers.RotatingFileHandler(
            str(tmp_path / "app.log"), maxBytes=40, backupCount=2
        )
        try:
            for _ in range(6):
                handler.emit(make_record("x" * 30))
        finally:
            handler.close()

        assert sorted(os.listdir(tmp_path)) == ["app.log", "app.log.1", "app.log.2"]


class TestTimedRotatingFileHandler:
    """`TimedRotatingFileHandler.getFilesToDelete()` | O(E + m log m): the whole
    directory is listed on a rollover with backups."""

    @pytest.fixture
    def log_dir(self, tmp_path: pathlib.Path) -> pathlib.Path:
        for index in range(50):
            (tmp_path / f"unrelated{index}.txt").write_text("")
        for day in range(1, 6):
            (tmp_path / f"t.log.2020-01-0{day}").write_text("")
        return tmp_path

    def test_the_check_formats_nothing(self, log_dir: pathlib.Path) -> None:
        handler = logging.handlers.TimedRotatingFileHandler(str(log_dir / "t.log"), when="D")
        formatter = CountingFormatter()
        handler.setFormatter(formatter)
        try:
            assert handler.shouldRollover(make_record()) is False
            assert handler.rolloverAt > time.time()
            assert handler.computeRollover(1_000) > 1_000
        finally:
            handler.close()
        assert formatter.formats == 0

    def test_the_directory_is_listed_once_and_the_oldest_surplus_returned(
        self, log_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listed: list[int] = []
        original = os.listdir

        def counting(target: Any = None) -> list[str]:
            entries = original(target)
            listed.append(len(entries))
            return entries

        monkeypatch.setattr(os, "listdir", counting)
        handler = logging.handlers.TimedRotatingFileHandler(
            str(log_dir / "t.log"), when="D", backupCount=2
        )
        try:
            surplus = handler.getFilesToDelete()
        finally:
            handler.close()

        assert listed == [56]
        assert [os.path.basename(p) for p in surplus] == [
            "t.log.2020-01-01",
            "t.log.2020-01-02",
            "t.log.2020-01-03",
        ]

        generous = logging.handlers.TimedRotatingFileHandler(
            str(log_dir / "t.log"), when="D", backupCount=10
        )
        try:
            assert generous.getFilesToDelete() == []
        finally:
            generous.close()

    def test_a_rollover_leaves_backup_count_backups_plus_the_new_one(
        self, log_dir: pathlib.Path
    ) -> None:
        handler = logging.handlers.TimedRotatingFileHandler(
            str(log_dir / "t.log"), when="D", backupCount=2
        )
        try:
            handler.emit(make_record())
            before = handler.rolloverAt
            handler.doRollover()
            assert handler.rolloverAt >= before
        finally:
            handler.close()

        backups = sorted(name for name in os.listdir(log_dir) if name.startswith("t.log."))
        assert len(backups) == 2
        assert backups[0] == "t.log.2020-01-05"
        assert (log_dir / "t.log").exists()


class TestWatchedFileHandler:
    """`WatchedFileHandler.reopenIfNeeded()` | O(1): one stat per record."""

    def test_every_record_stats_the_path_once(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = str(tmp_path / "w.log")
        handler = logging.handlers.WatchedFileHandler(path)
        stats = counting_path_calls(monkeypatch, os, "stat", handler.baseFilename)
        try:
            for _ in range(5):
                handler.emit(make_record())
        finally:
            handler.close()

        assert len(stats) == 5

    def test_a_replaced_file_is_reopened(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "w.log"
        handler = logging.handlers.WatchedFileHandler(str(path))
        try:
            handler.emit(make_record("before"))
            path.rename(tmp_path / "w.log.rotated")
            handler.emit(make_record("after"))
        finally:
            handler.close()

        assert (tmp_path / "w.log.rotated").read_text() == "before\n"
        assert path.read_text() == "after\n"


class FakeSocket:
    """Records what is sent through it."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.closed = False

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def sendto(self, data: bytes, address: Any) -> None:
        self.sent.append(data)

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def close(self) -> None:
        self.closed = True


class TestSocketHandlers:
    """`SocketHandler.createSocket()` | O(1) between attempts, and
    `makePickle()` | O(k + A)."""

    class Refusing(logging.handlers.SocketHandler):
        def __init__(self) -> None:
            super().__init__("localhost", 1)
            self.attempts = 0

        def makeSocket(self, timeout: float = 1) -> Any:
            self.attempts += 1
            raise OSError("refused")

    def test_construction_connects_nothing_and_failures_back_off(self) -> None:
        handler = self.Refusing()
        handler.retryStart = 3_600.0
        pickled = 0
        original_pickle = handler.makePickle

        def counting(record: logging.LogRecord) -> bytes:
            nonlocal pickled
            pickled += 1
            return original_pickle(record)

        handler.makePickle = counting  # type: ignore[method-assign]
        try:
            assert handler.attempts == 0 and handler.sock is None
            for _ in range(3):
                handler.emit(make_record())
            assert handler.attempts == 1
            assert pickled == 3, "a record in the back-off window is still pickled"
            assert handler.retryTime is not None
            assert handler.retryPeriod == handler.retryStart  # type: ignore[attr-defined]
            handler.retryTime = 0
            handler.emit(make_record())
            assert handler.attempts == 2
        finally:
            handler.close()

    def test_the_pickle_carries_the_text_and_none_of_the_objects(self) -> None:
        import pickle
        import struct

        handler = logging.handlers.SocketHandler("localhost", 1)
        formatter = CountingFormatter()
        handler.setFormatter(formatter)
        try:
            payload = handler.makePickle(make_record("%s", args=(Converted(),)))
            assert formatter.formats == 0
            (length,) = struct.unpack(">L", payload[:4])
            assert length == len(payload) - 4
            fields = pickle.loads(payload[4:])
            assert fields["msg"] == "converted"
            assert fields["args"] is None and fields["exc_info"] is None
            assert "message" not in fields

            try:
                raise ValueError("boom")
            except ValueError:
                record = logging.LogRecord("n", logging.ERROR, "p", 1, "m", (), sys.exc_info())
            handler.makePickle(record)
            assert formatter.formats == 1
            assert record.exc_text is not None and "ValueError: boom" in record.exc_text
        finally:
            handler.close()

    def test_a_datagram_socket_is_unconnected_and_sends_one_datagram_per_record(self) -> None:
        handler = logging.handlers.DatagramHandler("localhost", 1)
        try:
            sock = handler.makeSocket()
            assert sock.type == socket.SOCK_DGRAM
            with pytest.raises(OSError):
                sock.getpeername()
            sock.close()

            fake = FakeSocket()
            handler.makeSocket = lambda: fake  # type: ignore[method-assign]
            handler.emit(make_record())
            handler.emit(make_record())
            assert len(fake.sent) == 2
        finally:
            handler.close()
        assert fake.closed and handler.sock is None


class TestSysLogHandler:
    """`SysLogHandler.emit()` | O(k) plus one send: priority, ident, text, NUL."""

    def test_a_missing_unix_socket_does_not_raise(self, tmp_path: pathlib.Path) -> None:
        handler = logging.handlers.SysLogHandler(address=str(tmp_path / "missing.sock"))
        try:
            assert handler.unixsocket is True
            assert hasattr(handler, "createSocket") is (sys.version_info >= (3, 11))
        finally:
            handler.close()

    def test_priorities_are_lookups(self, tmp_path: pathlib.Path) -> None:
        handler = logging.handlers.SysLogHandler(address=str(tmp_path / "missing.sock"))
        try:
            assert handler.encodePriority("user", "info") == 14
            assert handler.encodePriority(1, 6) == 14
            assert handler.mapPriority("INFO") == "info"
            assert handler.mapPriority("CUSTOM") == "warning"
        finally:
            handler.close()

    def test_one_send_per_record(self, tmp_path: pathlib.Path) -> None:
        handler = logging.handlers.SysLogHandler(address=str(tmp_path / "missing.sock"))
        fake = FakeSocket()
        handler.socket = fake  # type: ignore[assignment]
        handler.ident = "app: "
        try:
            handler.emit(make_record())
            assert fake.sent == [b"<14>app: hello\x00"]
            handler.append_nul = False
            handler.emit(make_record())
            assert fake.sent[-1] == b"<14>app: hello"
        finally:
            handler.close()
        assert fake.closed


class TestSmtpAndHttpHandlers:
    """`SMTPHandler.emit()` opens one session per record; `HTTPHandler.emit()`
    makes one request per record."""

    def test_each_record_is_its_own_smtp_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sessions: list[Any] = []

        class FakeSMTP:
            def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
                self.host, self.port = host, port
                self.sent: list[Any] = []
                self.quit_called = False
                sessions.append(self)

            def send_message(self, message: Any) -> None:
                self.sent.append(message)

            def quit(self) -> None:
                self.quit_called = True

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        handler = logging.handlers.SMTPHandler("mail.example", "from@x", ["to@x"], "subject")
        try:
            assert handler.getSubject(make_record()) == "subject"
            handler.emit(make_record())
            handler.emit(make_record())
        finally:
            handler.close()

        assert len(sessions) == 2
        assert all(len(session.sent) == 1 and session.quit_called for session in sessions)
        assert sessions[0].sent[0]["Subject"] == "subject"

    def test_the_record_dict_is_sent_as_one_request(self) -> None:
        import urllib.parse

        requests: list[tuple[str, str]] = []
        bodies: list[bytes] = []

        class FakeConnection:
            def putrequest(self, method: str, url: str) -> None:
                requests.append((method, url))

            def putheader(self, *args: Any) -> None:
                pass

            def endheaders(self) -> None:
                pass

            def send(self, data: bytes) -> None:
                bodies.append(data)

            def getresponse(self) -> None:
                return None

        handler = logging.handlers.HTTPHandler("h.example", "/log", method="POST")
        record = make_record()
        assert handler.mapLogRecord(record) is record.__dict__
        handler.getConnection = lambda host, secure: FakeConnection()  # type: ignore[method-assign]
        try:
            handler.emit(record)
            handler.emit(make_record())
        finally:
            handler.close()

        assert requests == [("POST", "/log")] * 2
        assert bodies[0] == urllib.parse.urlencode(record.__dict__).encode()


class TestNTEventLogHandler:
    """`NTEventLogHandler` off Windows: a printed notice and a no-op `emit()`."""

    @pytest.mark.skipif(sys.platform == "win32", reason="the no-op path is for other platforms")
    def test_the_getters_are_constants_and_emit_does_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        handler = logging.handlers.NTEventLogHandler("app")
        try:
            assert "Win32" in capsys.readouterr().out
            assert handler.getMessageID(make_record()) == 1
            assert handler.getEventCategory(make_record()) == 0
            handler.emit(make_record())
        finally:
            handler.close()


class TestBufferingAndMemoryHandlers:
    """`MemoryHandler.flush()` | O(r) plus the target's `handle()` per record,
    and nothing without a target."""

    def test_a_buffering_handler_holds_records_unformatted_and_empties_at_capacity(
        self,
    ) -> None:
        handler = logging.handlers.BufferingHandler(3)
        formatter = CountingFormatter()
        handler.setFormatter(formatter)
        try:
            handler.emit(make_record())
            handler.emit(make_record())
            assert len(handler.buffer) == 2 and handler.shouldFlush(make_record()) is False
            handler.emit(make_record())
            assert handler.buffer == []
            handler.emit(make_record())
            assert len(handler.buffer) == 1
        finally:
            handler.close()
        assert handler.buffer == []
        assert formatter.formats == 0

    def test_a_memory_handler_flushes_at_capacity_and_at_flush_level(self) -> None:
        target = RecordingHandler(logging.ERROR)
        handler = logging.handlers.MemoryHandler(3, flushLevel=logging.ERROR, target=target)
        try:
            handler.emit(make_record("one"))
            handler.emit(make_record("two"))
            assert target.emitted == []
            handler.emit(make_record("three"))
            assert [record.msg for record in target.emitted] == ["one", "two", "three"]
            handler.emit(make_record("now", level=logging.ERROR))
            assert target.emitted[-1].msg == "now"
        finally:
            handler.close()
            target.close()

    def test_without_a_target_the_buffer_grows_without_bound(self) -> None:
        handler = logging.handlers.MemoryHandler(3)
        try:
            for _ in range(10):
                handler.emit(make_record())
            assert len(handler.buffer) == 10
        finally:
            handler.close()

    def test_close_keeps_the_records_when_told_not_to_flush(self) -> None:
        target = RecordingHandler()
        handler = logging.handlers.MemoryHandler(10, target=target, flushOnClose=False)
        handler.emit(make_record())
        handler.emit(make_record())

        handler.close()

        assert target.emitted == [] and handler.target is None
        assert len(handler.buffer) == 2
        target.close()


class TestQueueHandlerAndListener:
    """`QueueHandler.prepare()` | O(k + A) on the caller, and `QueueListener`
    delivering to every handler regardless of level."""

    def test_prepare_formats_on_the_caller_and_copies_the_record(self) -> None:
        records: queue.Queue[logging.LogRecord] = queue.Queue()
        handler = logging.handlers.QueueHandler(records)
        formatter = CountingFormatter("[%(message)s]")
        handler.setFormatter(formatter)
        argument = Converted()
        try:
            raise ValueError("boom")
        except ValueError:
            original = logging.LogRecord(
                "n", logging.ERROR, "p", 1, "%s", (argument,), sys.exc_info()
            )
        original.stack_info = "stack"
        original.request = "r-1"  # type: ignore[attr-defined]
        try:
            handler.emit(original)
        finally:
            handler.close()

        queued = records.get_nowait()
        assert queued.request == "r-1", "an extra attribute travels as it is"  # type: ignore[attr-defined]
        assert formatter.formats == 1 and argument.conversions == 1
        assert queued is not original
        assert queued.msg == queued.message
        assert queued.msg.startswith("[converted]\nTraceback") and queued.msg.endswith("\nstack")
        assert (queued.args, queued.exc_info, queued.exc_text, queued.stack_info) == (
            None,
            None,
            None,
            None,
        )
        assert original.args == (argument,) and original.exc_info is not None
        if sys.version_info >= (3, 12):
            assert handler.listener is None  # type: ignore[attr-defined]
        else:
            assert not hasattr(handler, "listener")

    def test_a_full_bounded_queue_drops_the_record(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(logging, "raiseExceptions", False)
        records: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=1)
        handler = logging.handlers.QueueHandler(records)
        try:
            handler.emit(make_record())
            handler.emit(make_record())
        finally:
            handler.close()

        assert records.qsize() == 1

    def test_the_listener_ignores_handler_levels_unless_told_to_respect_them(self) -> None:
        records: queue.Queue[logging.LogRecord] = queue.Queue()
        target = RecordingHandler(logging.ERROR)

        listener = logging.handlers.QueueListener(records, target)
        listener.start()
        records.put(make_record())
        listener.stop()
        assert len(target.emitted) == 1

        strict = logging.handlers.QueueListener(records, target, respect_handler_level=True)
        strict.start()
        records.put(make_record())
        strict.stop()
        assert len(target.emitted) == 1
        target.close()

    def test_stop_returns_after_every_queued_record_is_handled(self) -> None:
        records: queue.Queue[logging.LogRecord] = queue.Queue()
        target = RecordingHandler()
        listener = logging.handlers.QueueListener(records, target)
        for _ in range(100):
            records.put(make_record())

        listener.start()
        listener.stop()

        assert len(target.emitted) == 100
        target.close()

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the stop guard is 3.13+")
    def test_a_second_stop_is_a_noop(self) -> None:
        listener = logging.handlers.QueueListener(queue.Queue())
        listener.start()
        listener.stop()
        listener.stop()

    @pytest.mark.skipif(sys.version_info < (3, 13, 4), reason="the start guard is 3.13.4+")
    def test_a_second_start_raises(self) -> None:
        listener = logging.handlers.QueueListener(queue.Queue())
        listener.start()
        try:
            with pytest.raises(RuntimeError):
                listener.start()
        finally:
            listener.stop()

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the context manager is 3.14+")
    def test_the_listener_is_a_context_manager(self) -> None:
        records: queue.Queue[logging.LogRecord] = queue.Queue()
        target = RecordingHandler()

        with logging.handlers.QueueListener(records, target) as listener:  # type: ignore[attr-defined]
            assert listener._thread is not None  # type: ignore[attr-defined]
            records.put(make_record())

        assert listener._thread is None  # type: ignore[attr-defined]
        assert len(target.emitted) == 1
        target.close()


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
    """Each block runs in its own subprocess, because logging's configuration
    is module-global and a block that reconfigures it would reach the next one."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_no_block_writes_outside_a_temporary_directory(self) -> None:
        for line, source in _blocks():
            if "FileHandler" in source:
                assert "tempfile" in source, (
                    f"{PAGE.name}:{line} opens a FileHandler without a temporary directory"
                )

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
            assert os.listdir(workdir) == ["block.py"], (
                f"{PAGE.name}:{line} left files behind: {os.listdir(workdir)}"
            )

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "Expensive.conversions == 0" in s)
        mutated = source.replace("Expensive.conversions == 0", "Expensive.conversions == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
