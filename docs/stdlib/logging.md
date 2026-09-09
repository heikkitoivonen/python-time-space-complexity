# logging Module Complexity

The `logging` module's cost is decided by one question asked before anything else happens: is this
record going to be emitted at all? A call below the effective level returns after a cached
dictionary lookup, having built no `LogRecord` and formatted none of its arguments. A call above
it pays for the record, the walk up the logger hierarchy, every filter and formatter on the way,
and finally the handler's I/O.

The size variables: **a** is the ancestors between a logger and the root, **h** is the handlers
found along that walk, **f** is the filters attached to a logger or handler, and **k** is the
length of the formatted message.

!!! note "A suppressed call is about forty times cheaper than an emitted one"
    Not free, but close: `logger.debug(...)` under an `INFO` level is one cache lookup. Which is
    why the `%s` form matters — with `logger.debug('user %s', user)` the argument is never
    converted, while an f-string has already been built before `debug` is called.

## Complexity Reference

### Emitting a record

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logger.debug/info/warning/error/critical(msg, *args)` — suppressed | O(1) | O(1) | One lookup in the logger's level cache; no record, no formatting |
| `logger.debug/info/warning/error/critical(msg, *args)` — emitted | O(a + h + f + k) | O(k) | Record, ancestor walk, filters, then each handler's format and write |
| `logging.debug/info/warning/error/critical/log/exception/fatal/warn(...)` | O(a + h + f + k) | O(k) | The module-level functions, which call `basicConfig()` on first use if the root has no handler |
| `logger.isEnabledFor(level)` | O(1) | O(1) | Cached per logger and level; the cache is dropped whenever any level changes |
| `logging.LogRecord(...)` | O(1) | O(1) | Attribute assignment only; `getMessage()` is where `msg % args` happens |
| `logging.makeLogRecord(dict)` | O(d) | O(d) | d = keys in the dict |

### Loggers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.getLogger(name)` — known name | O(1) | O(1) | A dict lookup in the manager |
| `logging.getLogger(name)` — first time | O(d) | O(d) | d = dot-separated components; a placeholder is created for each missing ancestor |
| `logging.Logger` | O(1) | O(1) | The class itself; instances come from `getLogger()` |
| `logger.setLevel(level)` | O(L) | O(1) | L = loggers in the manager, whose level caches are all cleared |
| `logging.disable(level)` | O(L) | O(1) | The same cache-wide clear, applied globally |
| `logging.LoggerAdapter(logger, extra)` | O(1) | O(1) | Wraps a logger; `process()` runs per call |
| `logging.getLoggerClass()`, `logging.setLoggerClass(cls)` | O(1) | O(1) | The class `getLogger()` will instantiate |
| `logging.getLogRecordFactory()`, `logging.setLogRecordFactory(f)` | O(1) | O(1) | The callable that builds each record |

### Handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.Handler`, `logging.StreamHandler(stream)` | O(1) | O(1) | Construction; the write is the stream's cost |
| `logging.FileHandler(filename, ...)` | O(1) | O(1) | Opens the file eagerly unless `delay=True` |
| `logging.NullHandler()` | O(1) | O(1) | Discards the record, and exists so a library can stay silent |
| `handler.setLevel(level)` | O(1) | O(1) | Checked per record, after the logger's own level |
| `logging.getHandlerNames()`, `logging.getHandlerByName(name)` | O(1) | O(1) | Python 3.12+; the registry `dictConfig` fills in |
| `logging.shutdown()` | O(h) | O(1) | h = handlers registered; each is flushed and closed |
| `logging.lastResort` | O(1) | O(1) | The handler used when a record reaches no other |

### Filters and formatters

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.Filter(name)` | O(1) | O(1) | Name-prefix matching; `filter()` is called per record |
| `logger.addFilter(f)`, `handler.addFilter(f)` | O(1) | O(1) | Appended; every record then pays O(f) |
| `logging.Formatter(fmt, datefmt, style)` | O(1) | O(1) | Parses the format string once |
| `formatter.format(record)` | O(k) | O(k) | k = output length; `%(asctime)s` adds a `time.localtime` and `time.strftime` and roughly doubles it |
| `logging.BufferingFormatter(linefmt)` | O(r) | O(r) | r = records formatted together |
| `logging.BASIC_FORMAT` | O(1) | O(1) | The format string `basicConfig()` defaults to |

### Configuration and levels

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.basicConfig(**kwargs)` | O(1) | O(1) | Builds one handler and formatter; does nothing if the root already has handlers and `force` is not set |
| `logging.addLevelName(level, name)` | O(1) | O(1) | Two dict entries |
| `logging.getLevelName(level)` | O(1) | O(1) | A dict lookup; an unknown level returns a string rather than raising |
| `logging.getLevelNamesMapping()` | O(v) | O(v) | Python 3.11+; v = level names, copied into a new dict |
| `logging.NOTSET`, `logging.DEBUG`, `logging.INFO`, `logging.WARNING`, `logging.WARN`, `logging.ERROR`, `logging.CRITICAL`, `logging.FATAL` | O(1) | O(1) | Integer constants; `WARN` and `FATAL` are the deprecated spellings |
| `logging.captureWarnings(True)` | O(1) | O(1) | Redirects `warnings.showwarning` once |
| `logging.raiseExceptions` | O(1) | O(1) | Whether a handler error is reported to stderr |

## The Level Check Is the Whole Story

```python
import io
import logging

stream = io.StringIO()
logger = logging.getLogger('example')
logger.addHandler(logging.StreamHandler(stream))
logger.setLevel(logging.INFO)

class Expensive:
    """Counts how many times it is converted to a string."""
    conversions = 0

    def __str__(self):
        Expensive.conversions += 1
        return 'converted'

# Below the level: O(1), and the argument is never converted
logger.debug('value is %s', Expensive())
assert Expensive.conversions == 0

# At or above it: the record is built and the argument converted once
logger.info('value is %s', Expensive())
assert Expensive.conversions == 1
assert 'value is converted' in stream.getvalue()
```

!!! warning "An f-string is formatted before `logging` sees it"
    `logger.debug(f'value is {expensive}')` converts the argument whatever the level, because the
    string is built by the caller. `logger.debug('value is %s', expensive)` hands `logging` the
    pieces and lets it decide.

## The Level Cache

`isEnabledFor()` would otherwise walk up the logger hierarchy looking for the first ancestor with
a level set. It caches the answer per level instead, and the cache is emptied whenever any level
changes — which is why `setLevel()` and `disable()` are O(loggers) rather than O(1).

```python
import logging

logger = logging.getLogger('cache.example')
logger.setLevel(logging.INFO)

logger.isEnabledFor(logging.DEBUG)
logger.isEnabledFor(logging.INFO)
assert logger._cache == {logging.DEBUG: False, logging.INFO: True}   # O(1) hits

# Any level change invalidates it, everywhere
logger.setLevel(logging.DEBUG)
assert logger._cache == {}

logger.isEnabledFor(logging.DEBUG)
logging.disable(logging.CRITICAL)
assert logger._cache == {}
logging.disable(logging.NOTSET)
```

## Getting a Logger

A name already in the manager is a dict lookup. The first request for a dotted name creates a
placeholder for each ancestor that does not exist yet, so it costs its depth — once.

```python
import logging

first = logging.getLogger('app.db.pool')   # O(d) - creates app, app.db placeholders
second = logging.getLogger('app.db.pool')  # O(1) - the same object back

assert first is second
assert first.parent is not None
assert logging.getLogger('app.db.pool').name == 'app.db.pool'

# The root is the end of every chain
assert logging.getLogger().name == 'root'
```

## Handlers and Formatters

A record walks from its logger up to the root, and every handler found along the way formats and
writes it. That is the O(a + h) part; the handler's I/O is usually what dominates.

```python
import io
import logging

stream = io.StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))  # O(1) to build

logger = logging.getLogger('handlers.example')
logger.addHandler(handler)
logger.setLevel(logging.WARNING)
logger.propagate = False   # stop the walk here

logger.info('not emitted')
logger.warning('emitted')

assert stream.getvalue() == 'WARNING - emitted\n'   # O(k) to format and write
```

### The Cost of a Timestamp

`%(asctime)s` calls `time.localtime()` and `time.strftime()` for every record. It is the one
format directive that costs noticeably more than the rest.

```python
import logging

record = logging.LogRecord('n', logging.INFO, 'path', 1, 'hello %s', ('world',), None)

plain = logging.Formatter('%(levelname)s %(message)s')
timed = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

assert plain.format(record) == 'INFO hello world'          # O(k)
assert 'INFO hello world' in timed.format(record)          # O(k), plus the clock
```

## Filters

Every filter runs on every record that gets past the level check, on the logger and again on each
handler.

```python
import io
import logging

class OnlyEven(logging.Filter):
    def filter(self, record):
        return getattr(record, 'index', 0) % 2 == 0

stream = io.StringIO()
handler = logging.StreamHandler(stream)
logger = logging.getLogger('filters.example')
logger.addHandler(handler)
logger.addFilter(OnlyEven())   # O(1) to add, O(f) per record thereafter
logger.setLevel(logging.INFO)
logger.propagate = False

for index in range(4):
    logger.info('record %s', index, extra={'index': index})

assert stream.getvalue().split() == ['record', '0', 'record', '2']
```

## Levels

```python
import logging
import sys

assert logging.DEBUG < logging.INFO < logging.WARNING < logging.ERROR < logging.CRITICAL
assert logging.WARN == logging.WARNING and logging.FATAL == logging.CRITICAL

# Registering a level is two dict entries - O(1)
logging.addLevelName(25, 'NOTICE')
assert logging.getLevelName(25) == 'NOTICE'
assert logging.getLevelName('NOTICE') == 25

# An unknown level answers with a string rather than raising
assert logging.getLevelName(99) == 'Level 99'

if sys.version_info >= (3, 11):
    mapping = logging.getLevelNamesMapping()   # O(v) - a fresh dict
    assert mapping['INFO'] == logging.INFO
```

## Writing to a File

```python
import logging
import os
import tempfile

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, 'app.log')

    handler = logging.FileHandler(path)   # O(1), but the file is opened now
    logger = logging.getLogger('file.example')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info('written')
    handler.close()   # flushing is what makes it visible

    with open(path) as opened:
        assert opened.read() == 'written\n'
```

!!! note "`delay=True` postpones the open"
    `logging.FileHandler(path, delay=True)` does not touch the filesystem until the first record
    reaches it, which matters when a configuration declares handlers that may never be used.

## Version Notes

- **Python 3.11+**: `logging.getLevelNamesMapping()`
- **Python 3.12+**: `logging.getHandlerByName()` and `logging.getHandlerNames()`

## Related Modules

- **[sys](sys.md)** - `sys.stderr`, where the default handler writes
- **[time](time.md)** - what `%(asctime)s` reaches for on every record
- **[traceback](traceback.md)** - how `exc_info` becomes text

## Best Practices

✅ **Do**:

- Pass arguments, not f-strings: `logger.debug('x %s', value)` formats nothing when suppressed
- Set the level on the logger you own, and leave the root alone in a library
- Add a `NullHandler()` in a library so a record with nowhere to go stays quiet
- Reuse `getLogger(__name__)` — after the first call it is a dict lookup

❌ **Avoid**:

- `%(asctime)s` in a format you emit millions of records through
- Calling `setLevel()` in a hot path; it clears every logger's level cache
- Assuming a suppressed call is free — it is one lookup, not zero work
- Deep dotted logger names created dynamically, one per request
