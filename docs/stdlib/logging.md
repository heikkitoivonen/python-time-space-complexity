# logging Module Complexity

The `logging` module routes records from loggers, through filters, to handlers that format and
write them. Its cost is decided by one question asked before anything else happens: is this record
going to be emitted at all? A call below the effective level returns after one cached dictionary
lookup, having built no `LogRecord` and formatted none of its arguments. A call at or above it pays
for the record, the walk up the logger hierarchy, every filter on the way, and one formatting and
one write per handler that accepts it.

Nothing is held beyond the record being processed, except by the handlers that buffer on purpose.
The module does keep a registry of every logger ever named and a weak reference to every handler
ever built, and `setLevel()`, `shutdown()` and `dictConfig()` are linear in one of those rather
than in anything the call names.

Records are the unit throughout. `a` is the ancestors between a logger and the root, `h` is the
handlers found on that walk, `F` is the filter calls made for one record (the originating
logger's filters, then those of each handler the record reaches) and `k` is the characters in one
handler's formatted output. `L` is the entries in the logger registry, loggers and placeholders
alike; `H` is the live handlers in the process; `d` and `ℓ` are the dotted components and the
characters of a logger name; `f` is the characters in a format string; `e` is the keys in an
`extra` mapping; `p` is the characters in a path; `t` is the frames in a traceback, chained causes included; `D` is the
frames on the call stack; `r` is the records in a buffer or queue; `E` is the entries in a log
file's directory; and `b` is a rotating handler's `backupCount`.

Emission bounds cover the standard stream handlers, constant-cost filters and ordinary `%`-style
messages from a fixed call site with no `extra`, `exc_info` or `stack_info`; those three add
the `makeRecord()`, `formatException()` and `findCaller(stack_info=True)` rows. A custom filter, formatter, `namer` or
callback adds its own cost; hashing and equality of
keys and handlers are treated as O(1); and the destination's work - a stream's write, a socket's
send, an SMTP session - counts as one operation per record. Space excludes output retained by the
destination.

!!! note "A suppressed call is cheap, not free"
    `logger.debug(...)` under an `INFO` level is one cache lookup, which is why the `%s` form
    matters: with `logger.debug('user %s', user)` the argument is never converted, while an
    f-string has already been built before `debug()` is called.

## Complexity Reference

### Logger

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.getLogger(name=None)` - known name | O(1) | O(1) | A dict lookup in the registry; no name, or `'root'`, returns the root logger |
| `logging.getLogger(name)` - first time | O((d + c)·ℓ) | O(d·ℓ) | Each missing ancestor gets a placeholder keyed by its prefix, and those prefixes are retained; c = loggers already registered below a placeholder this name replaces, each revisited to compare and repoint its parent |
| `logging.Logger(name, level=NOTSET)` | O(1) | O(1) | Direct construction bypasses the registry: no entry, no parent until one is assigned, and a level cache outside every sweep, so even its own `setLevel()` leaves cached answers stale |
| `Logger.debug(msg, *args, **kwargs)`, `Logger.info(msg, *args, **kwargs)`, `Logger.warning(msg, *args, **kwargs)`, `Logger.error(msg, *args, **kwargs)`, `Logger.critical(msg, *args, **kwargs)`, `Logger.exception(msg, *args, exc_info=True, **kwargs)`, `Logger.log(level, msg, *args, **kwargs)`, `Logger.fatal(msg, *args, **kwargs)` - suppressed | O(1) cached; O(a) on the first call per level | O(1) | One lookup in the logger's level cache; no record, no formatting, no filter |
| The same call - emitted | O(a + h + F + h·k) | O(k) auxiliary | `findCaller()`, the record, the walk up the hierarchy, every filter reached, and one formatting and one write per accepting handler; `log()` with a non-integer level raises `TypeError` when `raiseExceptions` is true and otherwise does nothing |
| `Logger.warn(msg, *args, **kwargs)` | as `warning()` | as `warning()` | Deprecated: raises a `DeprecationWarning` on every call before delegating |
| `Logger.isEnabledFor(level)` | O(1) cached; O(a) on a miss | O(1) | The answer is cached per level; a miss consults `logging.disable()`'s threshold and `getEffectiveLevel()` |
| `Logger.getEffectiveLevel()` | O(a) | O(1) | Walks toward the root until a logger with a level set; not cached |
| `Logger.setLevel(level)` | O(L) | O(1) | Clears the level cache of every registered logger, not just this one |
| `Logger.hasHandlers()` | O(a) | O(1) | Stops at the first logger with handlers, or the first with `propagate` false |
| `Logger.addHandler(hdlr)`, `Logger.removeHandler(hdlr)` | O(n) | O(1) | n = handlers already on this logger, scanned for equality; a handler is added once |
| `Logger.handle(record)` | O(F + a + h) plus handler work | O(1) | Skipped entirely when `disabled`; the logger's filters, then `callHandlers()` |
| `Logger.callHandlers(record)` | O(a + h) plus each accepting handler's `handle()` | O(1) | Walks toward the root unless `propagate` is false; a record that finds no handler anywhere goes to `logging.lastResort` |
| `Logger.makeRecord(name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None)` | O(p + e) | O(p + e) | The record, then each `extra` key checked against the record's attributes and copied in; a collision raises `KeyError` |
| `Logger.findCaller(stack_info=False, stacklevel=1)` | O(s) | O(1) | s = `stacklevel` plus logging's own frames: it stops at the first caller, so the depth of the stack below does not matter |
| `Logger.findCaller(stack_info=True, stacklevel=1)` | O(D) | O(D) | Formats every frame on the stack, reading each one's source line |
| `Logger.getChild(suffix)` | O(ℓ), then as `getLogger()` | O(ℓ) | Joins the names, even for a logger that already exists, and asks the registry |
| `Logger.getChildren()` | O(L) | O(children) | Python 3.12+; scans the whole registry for direct children |
| `Logger.name`, `Logger.level`, `Logger.parent`, `Logger.propagate`, `Logger.handlers`, `Logger.filters`, `Logger.disabled` | O(1) | O(1) | Attributes. Assigning `level` directly leaves every cached `isEnabledFor()` answer stale; `setLevel()` is what clears them |
| `logging.root`, `Logger.root`, `Logger.manager` | O(1) | O(1) | The root logger and the registry that owns every named logger |

### LogRecord

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.LogRecord(name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None)` | O(p) | O(p) | Attribute assignment: `pathname` is split for `filename` and `module`; the process id, thread name and, on 3.12+, the asyncio task name are read; `msg % args` is not done here |
| `LogRecord.getMessage()` | O(k) | O(k) | `str(msg) % args`, redone on every call; each handler's formatter calls it again |
| `logging.makeLogRecord(dict)` | O(e) | O(e) | A blank record whose `__dict__` is updated with the e keys; how a pickled record from a `SocketHandler` is rebuilt |
| `logging.getLogRecordFactory()`, `logging.setLogRecordFactory(factory)` | O(1) | O(1) | The callable that builds each record |

### Handler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.Handler(level=NOTSET)` | O(1) | O(1) | Registers a weak reference for `shutdown()` and creates an `RLock` |
| `Handler.setLevel(level)`, `Handler.setFormatter(fmt)`, `Handler.level`, `Handler.formatter` | O(1) | O(1) | A level name is resolved through one dict lookup |
| `Handler.name`, `Handler.get_name()`, `Handler.set_name(name)` | O(1) | O(1) | Assigning a name registers the handler for `getHandlerByName()`; `close()` unregisters it |
| `Handler.createLock()`, `Handler.acquire()`, `Handler.release()` | O(1) | O(1) | `emit()` runs under this lock, so threads sharing a handler serialize on it |
| `Handler.handle(record)` | O(F) plus `emit()` | O(1) | The handler's filters, then `emit()` under the lock; returns a false value when a filter rejected the record, and otherwise the record (3.12+) or `True` |
| `Handler.format(record)` | O(k) | O(k) | The handler's formatter, or the module default of `%(message)s` |
| `Handler.emit(record)` | O(1) | O(1) | Raises `NotImplementedError`; subclasses do the work |
| `Handler.flush()` | O(1) | O(1) | A no-op here; `StreamHandler` flushes its stream |
| `Handler.close()` | O(1) | O(1) | Drops the name registration; subclasses close streams and sockets |
| `Handler.handleError(record)` | O(D + t) | O(D + t) | With `logging.raiseExceptions` true, writes the traceback and the whole call stack to `sys.stderr`; with it false, nothing |
| `Handler.addFilter(filter)`, `Handler.removeFilter(filter)` | O(n) | O(1) | n = filters already on the handler, scanned for equality |
| `logging.getHandlerByName(name)` | O(1) | O(1) | Python 3.12+; a lookup in the named-handler registry |
| `logging.getHandlerNames()` | O(n) | O(n) | Python 3.12+; a fresh frozenset of the n registered names |
| `logging.lastResort` | O(1) | O(1) | A `WARNING`-level handler on `sys.stderr`, used only by a record that found no handler at all on its walk |

### StreamHandler, FileHandler and NullHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.StreamHandler(stream=None)` | O(1) | O(1) | `sys.stderr` by default; the stream is never closed by the handler |
| `StreamHandler.emit(record)` | O(k) | O(k) | Formats, writes `msg + terminator` in one `write()`, then calls `flush()`: every record is followed by a flush |
| `StreamHandler.flush()` | O(1) | O(1) | The stream's own `flush()`, under the handler lock |
| `StreamHandler.setStream(stream)` | O(1) | O(1) | Flushes the old stream and returns it, or `None` when the stream is unchanged |
| `StreamHandler.terminator` | O(1) | O(1) | The string appended to each record, `'\n'` by default |
| `logging.FileHandler(filename, mode='a', encoding=None, delay=False, errors=None)` | O(p) | O(p) | Resolves and keeps the absolute path, then opens the file unless `delay=True` |
| `FileHandler.emit(record)` | O(k) | O(k) | Opens the file on the first record when delayed, then `StreamHandler.emit()`: a `write()` and a `flush()` per record |
| `FileHandler.close()` | O(1) | O(1) | Flushes and closes the file |
| `logging.NullHandler()` | O(1) | O(1) | What a library installs so its records have somewhere to go |
| `NullHandler.handle(record)`, `NullHandler.emit(record)` | O(1) | O(1) | Both are stubs; `handle()` is overridden, so the handler's filters are never consulted |
| `NullHandler.createLock()` | O(1) | O(1) | Sets no lock at all |

### Formatter and BufferingFormatter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.Formatter(fmt=None, datefmt=None, style='%', validate=True, *, defaults=None)` | O(f) | O(f) | `validate=True` scans the format string once and raises `ValueError` for a field that does not fit the style; `'$'` compiles a `string.Template`. A `defaults` mapping is merged with the record's attributes on every `format()`, so it costs its size per record |
| `Formatter.format(record)` | O(k + t) | O(k + t) | `getMessage()`, the time if the format uses it, the fields, then the exception text and stack info if present. The exception text is formatted once per record and cached in `record.exc_text`, so a second handler pays no t |
| `Formatter.formatMessage(record)` | O(k) | O(k) | The format string applied to the record's attributes |
| `Formatter.formatTime(record, datefmt=None)` | O(1) | O(1) | A `time.localtime()` and a `time.strftime()`; fixed-size output for a fixed `datefmt` |
| `Formatter.formatException(ei)` | O(t) | O(t) | `traceback.print_exception()` into a string; each frame's source line is read through `linecache`, which reads the file the first time |
| `Formatter.formatStack(stack_info)` | O(1) | O(1) | Returns its argument; the cost was paid in `findCaller()` |
| `Formatter.usesTime()` | O(f) | O(1) | A substring search for the time field, repeated on every `format()` |
| `Formatter.converter`, `Formatter.default_time_format`, `Formatter.default_msec_format` | O(1) | O(1) | Attributes; set `converter` to `time.gmtime` for UTC timestamps |
| `logging.BufferingFormatter(linefmt=None)` | O(1) | O(1) | Stores the line formatter; no record is formatted |
| `BufferingFormatter.format(records)` | O(r + K) with amortized string growth | O(r + K) | K = total characters of the r formatted lines, concatenated one at a time between the header and footer |
| `BufferingFormatter.formatHeader(records)`, `BufferingFormatter.formatFooter(records)` | O(1) | O(1) | Return `''`; subclasses override them |
| `logging.BASIC_FORMAT` | O(1) | O(1) | The format string `basicConfig()` defaults to |

### Filter and Filterer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.Filter(name='')` | O(1) | O(1) | Stores the name and its length |
| `Filter.filter(record)` | O(ℓ) | O(1) | Compares the filter's name as a dotted prefix of the record's logger name; an empty name passes everything |
| `Filterer.addFilter(filter)`, `Filterer.removeFilter(filter)` - on a `Logger` or a `Handler` | O(n) | O(1) | n = filters already attached, scanned for equality; a filter is attached once |
| `Filterer.filter(record)` - `Logger.filter(record)`, `Handler.filter(record)` | O(F) | O(1) | Each filter in order, stopping at the first that rejects; on 3.12+ a filter may return a `LogRecord`, which replaces the record for the rest of the chain |

### LoggerAdapter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.LoggerAdapter(logger, extra=None, merge_extra=False)` | O(1) | O(1) | Wraps a logger; `merge_extra` is Python 3.13+ |
| `LoggerAdapter.process(msg, kwargs)` | O(1); O(e) with `merge_extra` | O(e) with `merge_extra` | Replaces the call's `extra` with the adapter's; `merge_extra=True` builds a merged dict instead |
| `LoggerAdapter.debug(msg, *args, **kwargs)`, `LoggerAdapter.info(msg, *args, **kwargs)`, `LoggerAdapter.warning(msg, *args, **kwargs)`, `LoggerAdapter.error(msg, *args, **kwargs)`, `LoggerAdapter.critical(msg, *args, **kwargs)`, `LoggerAdapter.exception(msg, *args, exc_info=True, **kwargs)`, `LoggerAdapter.log(level, msg, *args, **kwargs)`, `LoggerAdapter.warn(msg, *args, **kwargs)` | as `Logger`, plus `process()` | as `Logger` | The level is checked first, so a suppressed call never reaches `process()` |
| `LoggerAdapter.isEnabledFor(level)`, `LoggerAdapter.getEffectiveLevel()`, `LoggerAdapter.hasHandlers()`, `LoggerAdapter.setLevel(level)` | as `Logger` | as `Logger` | Delegated to the wrapped logger |
| `LoggerAdapter.logger`, `LoggerAdapter.extra`, `LoggerAdapter.manager`, `LoggerAdapter.name` | O(1) | O(1) | Attributes; `manager` and `name` read through to the logger |

### Module-Level Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.debug(msg, *args, **kwargs)`, `logging.info(msg, *args, **kwargs)`, `logging.warning(msg, *args, **kwargs)`, `logging.error(msg, *args, **kwargs)`, `logging.critical(msg, *args, **kwargs)`, `logging.exception(msg, *args, exc_info=True, **kwargs)`, `logging.log(level, msg, *args, **kwargs)`, `logging.fatal(msg, *args, **kwargs)`, `logging.warn(msg, *args, **kwargs)` | as the root logger's call | as the root logger's call | A root with no handlers first gets `basicConfig()`; `warn()` also raises a `DeprecationWarning` |
| `logging.disable(level=CRITICAL)` | O(L) | O(1) | Sets one threshold and clears every logger's level cache, the same as `setLevel()` |
| `logging.shutdown(handlerList=_handlerList)` | O(H) plus each handler's flush and close | O(H) auxiliary | Copies the weak references to every live handler, newest first, and flushes and closes each; from 3.12 a handler with `flushOnClose` false is closed without the flush. Registered with `atexit` |
| `logging.basicConfig(**kwargs)` | O(1) when the root has handlers and `force` is false; O(n² + m² + L) otherwise | O(n + m) | n = handlers supplied (one by default), each added with the duplicate scan; m = the root's existing handlers, each removed with a scan and closed when `force=True`; L only when `level` is given |
| `logging.getLoggerClass()`, `logging.setLoggerClass(klass)` | O(1) | O(1) | The class `getLogger()` instantiates; `setLoggerClass()` checks it subclasses `Logger` |
| `logging.captureWarnings(capture)` | O(1) | O(1) | Swaps `warnings.showwarning`; each captured warning is then rendered by `warnings.formatwarning()` and emitted through the `py.warnings` logger |
| `logging.raiseExceptions` | O(1) | O(1) | Whether `handleError()` reports to `sys.stderr` |

### Levels and Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.addLevelName(level, levelName)` | O(1) | O(1) | Two dict entries, number to name and name to number |
| `logging.getLevelName(level)` | O(1) | O(1) | A dict lookup in either direction; an unknown level returns `'Level N'` rather than raising |
| `logging.getLevelNamesMapping()` | O(v) | O(v) | Python 3.11+; v = registered names, copied into a new dict |
| `logging.NOTSET`, `logging.DEBUG`, `logging.INFO`, `logging.WARNING`, `logging.WARN`, `logging.ERROR`, `logging.CRITICAL`, `logging.FATAL` | O(1) | O(1) | Integer constants; `WARN` and `FATAL` are the deprecated spellings |
| `logging.handlers.DEFAULT_TCP_LOGGING_PORT`, `logging.handlers.DEFAULT_UDP_LOGGING_PORT`, `logging.handlers.DEFAULT_HTTP_LOGGING_PORT`, `logging.handlers.DEFAULT_SOAP_LOGGING_PORT`, `logging.handlers.SYSLOG_UDP_PORT`, `logging.handlers.SYSLOG_TCP_PORT`, `logging.config.DEFAULT_LOGGING_CONFIG_PORT` | O(1) | O(1) | Integer port numbers |

### logging.config

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.config.dictConfig(config)` | O(C + H + L log L + (n + c)·L), plus flush and close work | O(C + L + H) | C = size of the config, though h handlers or filters on one target attach through the `addHandler()` and `addFilter()` scans, O(h²). Every live handler is flushed and closed first (H); the L registered names are sorted, and each of the n configured loggers scans them for its descendants; every existing logger the config does not name is disabled unless `disable_existing_loggers` is false, except the c existing descendants of named loggers, which are reset to inherit from them, each reset an O(L) cache clear of its own. `incremental=True` skips all of that and only sets levels and `propagate`: O(C + n·L), because every level set still clears every cache |
| `logging.config.fileConfig(fname, defaults=None, disable_existing_loggers=True, encoding=None)` | O(S + H + L log L + (n + c)·L), plus flush and close work | O(S + L + H) | S = characters in the file, parsed by `configparser`; handler arguments are evaluated with `eval()`; then the same handler closing and existing-logger pass as `dictConfig()` |
| `logging.config.listen(port=DEFAULT_LOGGING_CONFIG_PORT, verify=None)` | O(1) | O(1) | Returns a thread that is not yet started; nothing is bound until `start()`. Each configuration received then runs `dictConfig()` or `fileConfig()` |
| `logging.config.stopListening()` | O(1) | O(1) | Sets a flag the server checks after each one-second poll and after any request it is serving; the socket closes then |

### BaseRotatingHandler, RotatingFileHandler and TimedRotatingFileHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.BaseRotatingHandler(filename, mode, encoding=None, delay=False, errors=None)` | O(p) | O(p) | A `FileHandler`; not meant to be instantiated directly |
| `BaseRotatingHandler.emit(record)`, `RotatingFileHandler.emit(record)`, `TimedRotatingFileHandler.emit(record)` | `shouldRollover()` + `doRollover()` when due + `FileHandler.emit()` | O(k), plus `doRollover()`'s when due | The rollover check runs on every record |
| `BaseRotatingHandler.rotation_filename(default_name)` | O(1) | O(1) | Returns the name unchanged, or whatever `namer` returns |
| `BaseRotatingHandler.rotate(source, dest)` | O(1) | O(1) | An `os.path.exists()` and an `os.rename()`, or whatever `rotator` does |
| `BaseRotatingHandler.namer`, `BaseRotatingHandler.rotator` | O(1) | O(1) | `None` by default; callables that customize the two steps above |
| `logging.handlers.RotatingFileHandler(filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False, errors=None)` | O(p) | O(p) | A `maxBytes` of 0 never rolls over |
| `RotatingFileHandler.shouldRollover(record)` | O(k) | O(k) | With `maxBytes` set, formats the record to measure it, so an emitted record is formatted twice, except the first record into an empty file from 3.12.6; before 3.12.6 it also stats the path on every record, and from 3.12.6 only when a rollover is due |
| `RotatingFileHandler.doRollover()` | O(b) | O(1) | Renames each backup up one number, an `exists()` and a `rename()` apiece, then reopens the file |
| `logging.handlers.TimedRotatingFileHandler(filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False, atTime=None, errors=None)` | O(p) | O(p) | Stats the file for its modification time and computes the first rollover |
| `TimedRotatingFileHandler.computeRollover(currentTime)` | O(1) | O(1) | Arithmetic, with a DST adjustment for local time |
| `TimedRotatingFileHandler.shouldRollover(record)` | O(1) | O(1) | A clock read and a comparison; the record is not formatted |
| `TimedRotatingFileHandler.getFilesToDelete()` | O(E + m log m) | O(E + m) | Lists the whole directory and prefix-matches every entry; m = matching backups, sorted so the oldest go first. With a `namer`, each entry is regex-searched and the namer called per candidate |
| `TimedRotatingFileHandler.doRollover()` | O(E + m log m); O(1) with `backupCount=0` | O(E + m) | A `strftime()`, a rename, `getFilesToDelete()` and one `remove()` per surplus backup, then reopens |

### WatchedFileHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.WatchedFileHandler(filename, mode='a', encoding=None, delay=False, errors=None)` | O(p) | O(p) | Opens the file and records its device and inode |
| `WatchedFileHandler.reopenIfNeeded()` | O(1) | O(1) | One `os.stat()` of the path; reopens when the device or inode changed or the file is gone |
| `WatchedFileHandler.emit(record)` | O(k) | O(k) | `reopenIfNeeded()` then `FileHandler.emit()`: a `stat()`, a `write()` and a `flush()` per record |

### SocketHandler and DatagramHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.SocketHandler(host, port)` | O(1) | O(1) | No connection until the first record; `port=None` means a Unix domain socket at `host` |
| `SocketHandler.makeSocket(timeout=1)` | name resolution, then one connection attempt per resolved address until one succeeds | O(1) | `timeout` bounds each attempt, not the name resolution before them |
| `SocketHandler.createSocket()` | O(1) between attempts | O(1) | After a failed connect, no retry before `retryStart` seconds, doubling by `retryFactor` up to `retryMax`; a record emitted meanwhile is still pickled, then dropped without a connection attempt |
| `SocketHandler.makePickle(record)` | O(k + A) | O(k + A) | A = size of the record's attribute dict, values included: the dict is copied with `msg` merged, `args` and `exc_info` cleared and `message` dropped, then pickled behind a 4-byte length; with `exc_info` the record is formatted first so `exc_text` travels |
| `SocketHandler.send(s)` | one `sendall()` | O(1) | Connects first when there is no socket |
| `SocketHandler.emit(record)` | O(k + A) plus one send | O(k + A) | `makePickle()` then `send()` |
| `SocketHandler.handleError(record)` | O(1); `Handler.handleError()` otherwise | | Closes the socket when `closeOnError` is true, so the next record reconnects |
| `SocketHandler.close()` | O(1) | O(1) | Closes the socket |
| `logging.handlers.DatagramHandler(host, port)` | O(1) | O(1) | The same pickle, over UDP |
| `DatagramHandler.makeSocket()` | O(1) | O(1) | An unconnected datagram socket |
| `DatagramHandler.send(s)` | one `sendto()` | O(1) | No delivery guarantee and no partial sends |
| `DatagramHandler.emit(record)` | O(k + A) plus one send | O(k + A) | As `SocketHandler.emit()` |

### SysLogHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.SysLogHandler(address=('localhost', SYSLOG_UDP_PORT), facility=LOG_USER, socktype=None, timeout=None)` | one `createSocket()` | O(1) | A `str` address is a Unix socket, connected now, silently if it fails; a host tuple costs a `getaddrinfo()` and, for a stream socket, a connect. `timeout` is Python 3.14+ |
| `SysLogHandler.createSocket()` | as above | O(1) | Python 3.11+; called again from `emit()` whenever there is no socket. On 3.10 the constructor does the same work inline and `emit()` reconnects only a Unix socket |
| `SysLogHandler.encodePriority(facility, priority)`, `SysLogHandler.mapPriority(levelName)` | O(1) | O(1) | Dict lookups; an unknown level name maps to `'warning'` |
| `SysLogHandler.emit(record)` | O(k) plus one send | O(k) | Formats, prefixes `ident` and the priority, encodes as UTF-8 and appends a NUL when `append_nul`; one send per record, and a failed Unix-socket send reconnects and retries once |
| `SysLogHandler.close()` | O(1) | O(1) | Closes the socket |
| `SysLogHandler.ident`, `SysLogHandler.append_nul`, `SysLogHandler.priority_names`, `SysLogHandler.facility_names`, `SysLogHandler.priority_map` | O(1) | O(1) | Attributes; the three dicts map names to the `LOG_*` integers |

### SMTPHandler, HTTPHandler and NTEventLogHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.SMTPHandler(mailhost, fromaddr, toaddrs, subject, credentials=None, secure=None, timeout=5.0)` | O(1) | O(1) | Stores the addresses; nothing is connected |
| `SMTPHandler.getSubject(record)` | O(1) | O(1) | The fixed subject; override it for a record-dependent one |
| `SMTPHandler.emit(record)` | one SMTP session | O(k) | Connects, optionally STARTTLS and login, sends and quits: a complete session for every record, on the emitting thread |
| `logging.handlers.HTTPHandler(host, url, method='GET', secure=False, credentials=None, context=None)` | O(1) | O(1) | Validates the method; nothing is connected |
| `HTTPHandler.mapLogRecord(record)` | O(1) | O(1) | Returns the record's own `__dict__`, not a copy |
| `HTTPHandler.getConnection(host, secure)` | O(1) | O(1) | An `http.client` connection object; the connect happens in the request |
| `HTTPHandler.emit(record)` | O(A + V) plus one request | O(A + V) | URL-encodes every attribute of the record (A attributes, V characters of values) into the query string or body, sends one request per record and waits for the response |
| `logging.handlers.NTEventLogHandler(appname, dllname=None, logtype='Application')` | one registry write | O(1) | Windows with pywin32: registers the event source. Elsewhere it prints a notice and every `emit()` is a no-op |
| `NTEventLogHandler.emit(record)` | O(k) plus one `ReportEvent` | O(k) | Windows only |
| `NTEventLogHandler.getMessageID(record)`, `NTEventLogHandler.getEventCategory(record)`, `NTEventLogHandler.getEventType(record)` | O(1) | O(1) | Return 1, 0 and a lookup in the level-to-type map |
| `NTEventLogHandler.close()` | O(1) | O(1) | Leaves the registry entry in place |

### BufferingHandler and MemoryHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.BufferingHandler(capacity)` | O(1) | O(1) | An empty list |
| `BufferingHandler.emit(record)` | O(1) amortized | O(1) | Appends the record, then `flush()` when `shouldFlush()` says so; records are held unformatted |
| `BufferingHandler.shouldFlush(record)` | O(1) | O(1) | True when the buffer has reached `capacity` |
| `BufferingHandler.flush()` | O(r) | O(1) | Empties the buffer and does nothing else with the records |
| `BufferingHandler.close()` | O(r) | O(1) | `flush()`, then `Handler.close()` |
| `logging.handlers.MemoryHandler(capacity, flushLevel=ERROR, target=None, flushOnClose=True)` | O(1) | O(1) | A `BufferingHandler` that forwards to `target` |
| `MemoryHandler.shouldFlush(record)` | O(1) | O(1) | True when the buffer is full or the record's level reaches `flushLevel` |
| `MemoryHandler.setTarget(target)` | O(1) | O(1) | Under the handler lock |
| `MemoryHandler.flush()` | O(r) plus the target's `handle()` per record | O(1) | Each buffered record goes to `target.handle()`, which runs the target's filters but does not check its level. Without a target the buffer is kept, so it grows without bound |
| `MemoryHandler.close()` | O(r) plus the target's `handle()` per record | O(1) | `flush()` when `flushOnClose`, then drops the target; with `flushOnClose=False` the records stay in the buffer |

### QueueHandler and QueueListener

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.handlers.QueueHandler(queue)` | O(1) | O(1) | Any object with `put_nowait()` |
| `QueueHandler.prepare(record)` | O(k + A) | O(k + A) | Formats the record on the calling thread, then returns a shallow copy whose `msg` and `message` are the formatted text and whose `args`, `exc_info`, `exc_text` and `stack_info` are `None`; anything else on the record, `extra` included, travels as it is |
| `QueueHandler.enqueue(record)` | O(1) | O(1) | `put_nowait()`; a full bounded queue raises `queue.Full` into `handleError()` and the record is dropped |
| `QueueHandler.emit(record)` | O(k + A) | O(k + A) | `enqueue(prepare(record))` |
| `QueueHandler.listener` | O(1) | O(1) | Python 3.12+; `None` unless `dictConfig()` built the listener |
| `logging.handlers.QueueListener(queue, *handlers, respect_handler_level=False)` | O(1) | O(1) | Stores the handlers; no thread yet |
| `QueueListener.start()` | O(1) | O(1) | Starts one daemon thread; from 3.13.4 a second `start()` raises `RuntimeError` |
| `QueueListener.stop()` | O(r) plus handling | O(1) | Enqueues the sentinel behind every pending record and joins, so it returns only after all r have been handled; a full bounded queue makes the sentinel's `put_nowait()` raise `queue.Full` instead. From 3.13 a second `stop()` is a no-op, and on 3.14+ the listener is a context manager |
| `QueueListener.dequeue(block)`, `QueueListener.enqueue_sentinel()` | O(1) | O(1) | `get()` and `put_nowait()` on the queue |
| `QueueListener.prepare(record)` | O(1) | O(1) | Returns the record unchanged |
| `QueueListener.handle(record)` | O(n) plus each handler's `handle()` | O(1) | n = the listener's handlers; every one of them receives the record regardless of its level unless `respect_handler_level` is true |

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
changes through `setLevel()` or `disable()`, which is why those two are O(L) rather than O(1).

```python
import logging

logger = logging.getLogger('cache.example')
logger.setLevel(logging.INFO)

assert logger.isEnabledFor(logging.DEBUG) is False   # O(a) - the first answer is computed
assert logger.isEnabledFor(logging.DEBUG) is False   # O(1) - now cached

# Any level change invalidates it, everywhere
logger.setLevel(logging.DEBUG)                        # O(L)
assert logger.isEnabledFor(logging.DEBUG) is True

logging.disable(logging.CRITICAL)                     # O(L)
assert logger.isEnabledFor(logging.ERROR) is False
logging.disable(logging.NOTSET)
assert logger.isEnabledFor(logging.ERROR) is True
```

## Getting a Logger

A name already in the registry is a dict lookup. The first request for a dotted name creates a
placeholder for each missing ancestor and retains its full prefix string, so a name of d
components costs O(d·ℓ) in time and in retained text. Creating a logger where a placeholder stood
also visits every logger registered below it to repair their parent links.

```python
import logging

first = logging.getLogger('app.db.pool')   # O((d + c)·ℓ) - two placeholders, three prefixes kept
second = logging.getLogger('app.db.pool')  # O(1) - the same object back

assert first is second
assert first.getChild('conn') is logging.getLogger('app.db.pool.conn')  # O((d + c)·ℓ) once, then O(ℓ)

# The root is the end of every chain
assert logging.getLogger().name == 'root'
assert first.parent is logging.getLogger()   # nothing named 'app' or 'app.db' exists yet

# Naming the placeholder promotes it and repoints the descendants
middle = logging.getLogger('app.db')         # O((d + c)·ℓ) for the c loggers below it
assert first.parent is middle
```

## Handlers and Formatters

A record walks the logger hierarchy and checks the handlers along the way, costing O(a + h).
Each accepting handler then formats and writes the message independently: h such handlers with
k-character output cost O(h·k), plus the filter work. A `StreamHandler` also flushes after every
record, so a file receives every record as it is written.

```python
import io
import logging

stream = io.StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))  # O(f) to validate

logger = logging.getLogger('handlers.example')
logger.addHandler(handler)
logger.setLevel(logging.WARNING)
logger.propagate = False   # stop the walk here

logger.info('not emitted')
logger.warning('emitted')

assert stream.getvalue() == 'WARNING - emitted\n'   # O(k) to format and write

# A handler's own level is checked after the logger's
handler.setLevel(logging.ERROR)
logger.warning('below the handler')
assert stream.getvalue() == 'WARNING - emitted\n'
```

### The Cost of a Timestamp

`%(asctime)s` converts `record.created` with `time.localtime()` and renders it with
`time.strftime()` for every record. It is the one format directive that does more than read an
attribute.

```python
import logging

record = logging.LogRecord('n', logging.INFO, 'path', 1, 'hello %s', ('world',), None)

plain = logging.Formatter('%(levelname)s %(message)s')
timed = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

assert plain.usesTime() is False and timed.usesTime() is True   # O(f) each
assert plain.format(record) == 'INFO hello world'          # O(k)
assert timed.format(record).endswith('INFO hello world')   # O(k), plus the time conversion
```

### Exceptions and Stack Info

The traceback of an `exc_info` record is rendered once and cached on the record, so a second
handler appends the same text without formatting it again. `stack_info=True` is different: it
formats the entire call stack inside `findCaller()`, before any level or handler is consulted
beyond the first check, and that is O(D) in the depth of the stack at the call site.

```python
import io
import logging

class Counting(logging.Formatter):
    """Counts how many tracebacks it renders."""
    rendered = 0

    def formatException(self, ei):
        Counting.rendered += 1
        return super().formatException(ei)

first, second = io.StringIO(), io.StringIO()
logger = logging.getLogger('exceptions.example')
logger.propagate = False
for stream in (first, second):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(Counting('%(message)s'))
    logger.addHandler(handler)

try:
    1 / 0
except ZeroDivisionError:
    logger.exception('failed')   # O(t) once; the second handler reuses record.exc_text

assert Counting.rendered == 1
assert first.getvalue() == second.getvalue()
assert 'ZeroDivisionError' in first.getvalue()

logger.warning('where am I', stack_info=True)   # O(D): the whole stack is formatted
assert 'Stack (most recent call last):' in first.getvalue()
```

## Filters

Only the *originating* logger's filters run, then each reached handler's own filters after its
level check. A filter on an ancestor logger is never consulted for a child's record, even though
that ancestor's handlers still receive it. A rejecting filter stops that chain, so F counts the
filters actually called.

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
logger.addFilter(OnlyEven())   # O(n) to add among n filters; O(1) per record
logger.setLevel(logging.INFO)
logger.propagate = False

for index in range(4):
    logger.info('record %s', index, extra={'index': index})

assert stream.getvalue().split() == ['record', '0', 'record', '2']

# A filter on an ancestor does not see the child's record, though the
# ancestor's handlers still do
ancestor_stream = io.StringIO()
ancestor = logging.getLogger('ancestor.example')
ancestor.addHandler(logging.StreamHandler(ancestor_stream))
ancestor.addFilter(OnlyEven())          # never consulted for a child's record
ancestor.setLevel(logging.INFO)

child = logging.getLogger('ancestor.example.child')
child.info('sent up', extra={'index': 1})   # odd, so OnlyEven would have rejected it

assert 'sent up' in ancestor_stream.getvalue()

# The built-in Filter is a dotted-prefix test on the logger name
scoped = logging.Filter('ancestor.example')
assert scoped.filter(logging.makeLogRecord({'name': 'ancestor.example.child'}))   # O(ℓ)
assert not scoped.filter(logging.makeLogRecord({'name': 'ancestor.examples'}))
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

## Adapters

A `LoggerAdapter` adds the same `extra` to every call. The level check happens before
`process()`, so a suppressed call costs the adapter nothing beyond the lookup.

```python
import io
import logging

stream = io.StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(logging.Formatter('%(request)s %(message)s'))
logger = logging.getLogger('adapter.example')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

class Counting(logging.LoggerAdapter):
    processed = 0

    def process(self, msg, kwargs):
        Counting.processed += 1
        return super().process(msg, kwargs)   # O(1): the call's extra is replaced

adapter = Counting(logger, {'request': 'r-1'})
adapter.debug('suppressed')   # O(1) - process() is never reached
assert Counting.processed == 0

adapter.info('served')        # as Logger.info(), plus process()
assert Counting.processed == 1
assert stream.getvalue() == 'r-1 served\n'
```

## Writing to a File

```python
import logging
import os
import tempfile

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, 'app.log')

    handler = logging.FileHandler(path)   # O(p), and the file is opened now
    logger = logging.getLogger('file.example')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info('written')   # O(k): a write and a flush
    handler.close()

    with open(path) as opened:
        assert opened.read() == 'written\n'
```

!!! note "`delay=True` postpones the open"
    `logging.FileHandler(path, delay=True)` does not touch the filesystem until the first record
    reaches it, which matters when a configuration declares handlers that may never be used.

### Rotating Files

A `RotatingFileHandler` with `maxBytes` set has to know how long the record will be before it
decides whether to roll over, so it formats the record once to measure it and once more to write
it; only the first record into an empty file skips the measurement, from 3.12.6. A rollover
renames the b backups one number up each. A `TimedRotatingFileHandler` checks
only the clock per record, but a rollover with `backupCount` set lists the whole directory to find
the backups to delete.

```python
import logging
import logging.handlers
import os
import tempfile

class Counting(logging.Formatter):
    calls = 0

    def format(self, record):
        Counting.calls += 1
        return super().format(record)

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, 'app.log')
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=40, backupCount=2)
    handler.setFormatter(Counting('%(message)s'))
    logger = logging.getLogger('rotating.example')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info('x' * 30)
    Counting.calls = 0
    logger.info('y' * 30)   # O(k) to measure, O(k) to write; the file rolled over first
    assert Counting.calls == 2

    for _ in range(3):
        logger.info('z' * 30)   # each rollover is O(b): renames .1 to .2, then app.log to .1
    handler.close()

    assert sorted(os.listdir(folder)) == ['app.log', 'app.log.1', 'app.log.2']

    timed = logging.handlers.TimedRotatingFileHandler(path, when='D', backupCount=2)
    assert timed.getFilesToDelete() == []   # O(E): lists the directory; none match the date suffix
    timed.close()
```

## Buffering in Memory

A `MemoryHandler` holds records unformatted and hands them to its target when the buffer fills
or a record reaches `flushLevel`. The target's `handle()` is called directly, so its level is not
consulted; and without a target the buffer is never emptied.

```python
import io
import logging
import logging.handlers

stream = io.StringIO()
target = logging.StreamHandler(stream)
target.setLevel(logging.ERROR)   # ignored by the flush below

memory = logging.handlers.MemoryHandler(capacity=3, flushLevel=logging.ERROR, target=target)
logger = logging.getLogger('memory.example')
logger.addHandler(memory)
logger.setLevel(logging.DEBUG)
logger.propagate = False

logger.info('one')
logger.info('two')
assert stream.getvalue() == ''             # O(1) each: held, not formatted
logger.info('three')                       # the buffer is full: O(r) flush to the target
assert stream.getvalue() == 'one\ntwo\nthree\n'

logger.error('now')                        # at flushLevel, so it flushes at once
assert stream.getvalue().endswith('now\n')

orphan = logging.handlers.MemoryHandler(capacity=2)   # no target
for index in range(10):
    orphan.emit(logging.makeLogRecord({'msg': str(index), 'levelno': logging.INFO}))
assert len(orphan.buffer) == 10            # nothing ever leaves an untargeted buffer
orphan.close()
memory.close()
```

## Handing Off to a Queue

`QueueHandler.prepare()` formats the record on the calling thread and enqueues a copy that
carries the text in place of `args`, `exc_info`, `exc_text` and `stack_info`; anything added
through `extra` travels as it is. The `QueueListener` thread then offers each
record to every handler it was given, ignoring the handlers' levels unless told otherwise, and
`stop()` returns only after everything already queued has been handled.

```python
import io
import logging
import logging.handlers
import queue

stream = io.StringIO()
target = logging.StreamHandler(stream)
target.setLevel(logging.ERROR)

records = queue.Queue()
listener = logging.handlers.QueueListener(records, target)   # O(1); no thread yet
logger = logging.getLogger('queue.example')
logger.addHandler(logging.handlers.QueueHandler(records))
logger.setLevel(logging.INFO)
logger.propagate = False

logger.info('queued %s', 1)   # O(k + A): formatted here, then a put_nowait
queued = records.get_nowait()
assert queued.msg == 'queued 1' and queued.args is None
records.put_nowait(queued)

listener.start()               # O(1)
logger.info('queued %s', 2)
listener.stop()                # O(r): joins after both records are handled

# The target's ERROR level was not consulted
assert stream.getvalue() == 'queued 1\nqueued 2\n'

strict = logging.handlers.QueueListener(records, target, respect_handler_level=True)
strict.start()
logger.info('dropped')
strict.stop()
assert stream.getvalue() == 'queued 1\nqueued 2\n'
```

## Configuring From a Dictionary

`dictConfig()` builds what the dictionary describes, but its cost also has a term the dictionary
does not mention: it closes every live handler, sorts every registered logger name and, unless
`disable_existing_loggers` is false, disables every logger the configuration does not name;
descendants of a named logger are reset to inherit from it instead. `incremental=True` skips all
of that and only adjusts levels, though each level set still clears every logger's cache.

```python
import io
import logging
import logging.config
import sys

existing = logging.getLogger('legacy.module')
existing.setLevel(logging.INFO)
stream = io.StringIO()

logging.config.dictConfig({          # O(C + H + L log L + (n + c)·L)
    'version': 1,
    'handlers': {'memory': {'class': 'logging.StreamHandler', 'stream': stream}},
    'loggers': {'app': {'level': 'DEBUG', 'handlers': ['memory']}},
})

assert existing.disabled is True                          # not named, so switched off
assert logging.getLogger('app').level == logging.DEBUG
if sys.version_info >= (3, 12):
    assert logging.getHandlerByName('memory') is not None   # O(1); the config named it

existing.info('lost')
assert stream.getvalue() == ''

logging.config.dictConfig({          # O(C + n·L): incremental sets the named levels, each an O(L) cache clear
    'version': 1,
    'incremental': True,
    'loggers': {'app': {'level': 'WARNING'}},
})
assert logging.getLogger('app').level == logging.WARNING
assert existing.disabled is True   # untouched, still off
```

## Common Patterns

### A Library and the Application That Uses It

A library attaches a `NullHandler` so its records have a destination and never fall through to
`lastResort`; the application decides what actually gets written.

```python
import io
import logging

# In the library: one NullHandler, and no level set
library = logging.getLogger('somelib')
library.addHandler(logging.NullHandler())   # O(1); its handle() does nothing

# In the application: configure the root once
sink = io.StringIO()
logging.basicConfig(stream=sink, level=logging.WARNING, format='%(name)s:%(message)s')  # O(n² + L)

library.debug('chatty')    # O(1) - suppressed by the root's WARNING level
library.warning('careful')  # O(a + h + F + h·k): the NullHandler, then the root's handler

assert sink.getvalue() == 'somelib:careful\n'
logging.basicConfig(level=logging.DEBUG)   # O(1): the root already has a handler, so nothing changes
assert logging.getLogger().level == logging.WARNING
```

## Performance Best Practices

✅ **Do**:

- Pass arguments, not f-strings: `logger.debug('x %s', value)` formats nothing when suppressed
- Set the level on the logger you own, and leave the root alone in a library
- Add a `NullHandler()` in a library so a record with nowhere to go stays quiet
- Reuse `getLogger(__name__)`; after the first call it is a dict lookup
- Give a `MemoryHandler` a target, or its buffer only ever grows
- Move `SMTPHandler`, `HTTPHandler` and `SocketHandler` behind a `QueueHandler`, so their per-record session or send happens on the listener's thread

❌ **Avoid**:

- `%(asctime)s` in a format you emit millions of records through
- `stack_info=True` on a hot path: it formats the whole call stack on every emitted record
- Calling `setLevel()` or `disable()` in a hot path; each clears every logger's level cache
- Assigning `logger.level` directly, which leaves the cached answers stale
- `dictConfig()` more than once at start-up: each call closes every live handler and disables every logger it does not name
- Deep dotted logger names created dynamically, one per request

## Version Notes

- **Python 3.11+**: `logging.getLevelNamesMapping()` and `SysLogHandler.createSocket()`
- **Python 3.12+**: `logging.getHandlerByName()`, `logging.getHandlerNames()` and `Logger.getChildren()`; a filter may return a `LogRecord` to replace the record; `LogRecord.taskName`; `dictConfig()` can build a `QueueHandler` with its listener
- **Python 3.12.6+**: `RotatingFileHandler` never rolls over an empty file and stats the path only when a rollover is due
- **Python 3.13+**: `LoggerAdapter(merge_extra=True)`; a second `QueueListener.stop()` is a no-op, and from 3.13.4 a second `start()` raises
- **Python 3.14+**: `QueueListener` is a context manager; `SysLogHandler(timeout=...)`
- **All Python 3**: `StreamHandler.emit()` flushes after every record

## Related Modules

- **[sys](sys.md)** - `sys.stderr`, where the default handler writes
- **[time](time.md)** - what `%(asctime)s` reaches for on every record
- **[traceback](traceback.md)** - how `exc_info` and `stack_info` become text
- **[queue](queue.md)** - the hand-off between `QueueHandler` and `QueueListener`
