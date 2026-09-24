# sqlite3 Module Complexity

The `sqlite3` module is a binding over the SQLite C library. What a query costs is what SQLite's
query planner chooses; the module's own work is compiling SQL, binding parameters, converting values
and building the rows you get back. Nothing in Python holds a whole result unless you ask for all
of it.

`n` is the rows in the table a statement reads or writes, `r` the rows it returns or changes, `c`
the columns in a result row, `p` the parameters bound to a statement, `i` the indexes on a table,
`q` the characters of SQL text, `s` the compiled statements a connection holds, and `m` the size of a
whole database. `v` is the TEXT and BLOB bytes a call handles: the values it binds, fetches or
compares. Integers, floats and NULL cost O(1), and
column names are treated as O(1) strings. Custom adapters, converters, row factories and callbacks
add their own cost. Space bounds count Python objects; SQLite's own workspace - sort buffers, page
lists, its page cache - is additional. Transaction rows describe the default transaction control:
`isolation_level`, with `autocommit` (Python 3.12+) left at `LEGACY_TRANSACTION_CONTROL`.

The query rows price SQLite's work, and a Python call pays for whatever part of it runs: `execute()`
runs a query to its first row, and each fetch runs it to the next, so a fetch can scan many rows to
return one. On Python 3.10 rows are converted one step early - `execute()` converts the first row,
and each fetch converts the row after the one it returns - with the same totals.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.connect(database, timeout=5.0, detect_types=0, ..., cached_statements=128, ...)` | O(1) | O(1) | Opens the file; SQLite checks that it is a database only at the first statement. `cached_statements` defaults to 100 on Python 3.10 |
| `sqlite3.complete_statement(statement)` | O(q) | O(1) | Whether the text ends in a complete statement; nothing is compiled |
| `sqlite3.register_adapter(type, adapter, /)` | O(1) | O(1) | One entry in `sqlite3.adapters`; the adapter then runs per bound value of that type |
| `sqlite3.register_converter(typename, converter, /)` | O(1) | O(1) | One entry in `sqlite3.converters`, matched case-insensitively |
| `sqlite3.adapt(obj, proto=PrepareProtocol, /)` | O(1) + adapter | O(1) | A dict lookup, then the adapter; an optional third argument is returned when nothing adapts `obj` |
| `sqlite3.enable_callback_tracebacks(flag, /)` | O(1) | O(1) | Whether an exception inside a callback prints a traceback |
| `sqlite3.enable_shared_cache(do_enable)` | O(1) | O(1) | Removed in Python 3.12 |

### Connection

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.Connection` | O(1) | O(1) | The class `connect()` builds |
| `Connection.cursor(factory=Cursor)` | O(1) | O(1) | A cursor is a position, not a copy of anything |
| `Connection.execute(sql, parameters=(), /)`, `Connection.executemany(sql, parameters, /)`, `Connection.executescript(sql_script, /)` | As the `Cursor` method | As the `Cursor` method | Makes a cursor, calls its method, and returns the cursor |
| `Connection.commit()`, `Connection.rollback()` | O(d) | O(1) | d = pages the transaction changed; a commit is where a file database waits for the disk. Outside a transaction, a no-op |
| `with connection:` | O(1) + commit | O(1) | Commits on success, rolls back on an exception; does not close |
| `Connection.close()` | O(s) | O(1) | Finalizes the cached statements; uncommitted changes are lost, not committed |
| `Connection.in_transaction`, `Connection.total_changes` | O(1) | O(1) | |
| `Connection.isolation_level`, `Connection.autocommit` | O(1), plus a commit | O(1) | `autocommit` is Python 3.12+. Setting `isolation_level` to `None`, or `autocommit` to `True`, commits an open transaction first |
| `Connection.row_factory`, `Connection.text_factory` | O(1) | O(1) | A cursor copies `row_factory` when it is created; the factory then runs once per row, `text_factory` once per TEXT value |
| `Connection.create_function(name, narg, func, *, deterministic=False)` | O(1) | O(1) | `func` then runs once per call the SQL makes |
| `Connection.create_aggregate(name, n_arg, aggregate_class)` | O(1) | O(1) | `step()` runs once per row, `finalize()` once per group |
| `Connection.create_window_function(name, num_params, aggregate_class, /)` | O(1) | O(1) | Python 3.11+ |
| `Connection.create_collation(name, callback, /)` | O(1) | O(1) | `callback` runs once per comparison: sorting on it calls it O(r log r) times |
| `Connection.set_authorizer(authorizer_callback)` | O(s) | O(1) | Expires every compiled statement, so each compiles again on its next run; the callback is called per action while a statement compiles, not each time it runs |
| `Connection.set_progress_handler(progress_handler, n)` | O(1) | O(1) | Called periodically while a statement runs, at the given instruction interval |
| `Connection.set_trace_callback(trace_callback)` | O(1) | O(1) | Called with the SQL text of each statement SQLite runs |
| `Connection.interrupt()` | O(1) | O(1) | Aborts the running query at its next check |
| `Connection.enable_load_extension(enable, /)`, `Connection.load_extension(name, /, *, entrypoint=None)` | O(1) + the extension's setup | O(1) | Present only when Python's SQLite build allows extensions; `entrypoint` is Python 3.12+ |
| `Connection.iterdump(*, filter=None)` | O(m) | O(e + w) | A generator: e = the total length of the schema's CREATE statements, fetched up front, w = the longest statement; each row is read as its INSERT is yielded. `filter` is Python 3.13+ |
| `Connection.backup(target, *, pages=-1, progress=None, name='main', sleep=0.250)` | O(m) | O(1) | Copies `pages` pages per step and calls `progress` after each; the whole database in one step by default. The target holds the O(m) copy |
| `Connection.serialize(*, name='main')` | O(m) | O(m) | Python 3.11+; the whole database as one `bytes` object |
| `Connection.deserialize(data, /, *, name='main')` | O(m) | O(m) | Python 3.11+; copies `data` into SQLite, replacing the database |
| `Connection.blobopen(table, column, rowid, /, *, readonly=False, name='main')` | O(log n) | O(1) | Python 3.11+; finds the row by rowid and reads none of the value |
| `Connection.getlimit(category, /)`, `Connection.setlimit(category, limit, /)` | O(1) | O(1) | Python 3.11+; categories are the `SQLITE_LIMIT_*` constants |
| `Connection.getconfig(op, /)`, `Connection.setconfig(op, enable=True, /)` | O(1) | O(1) | Python 3.12+; options are the `SQLITE_DBCONFIG_*` constants |
| `Connection.Error`, `Connection.Warning`, `Connection.DatabaseError` and the other exception classes | O(1) | O(1) | The module's exception classes, reachable from a connection |

### Cursor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.Cursor` | O(1) | O(1) | Instances come from `Connection.cursor()` |
| `Cursor.execute(sql, parameters=(), /)`, SQL text in the cache | O(p + v + c) + query work | O(p + v + c) | SQLite copies the bound values; `description` is rebuilt |
| `Cursor.execute(sql, parameters=(), /)`, new SQL text | Compile + O(p + v + c) + query work | O(p + v + c), plus the compiled statement in SQLite | Compiling parses and plans the SQL; the compiled statement joins the cache |
| `Cursor.executemany(sql, seq_of_parameters, /)` | Compile + O(k·p + v) + k runs | O(p + largest set's v), plus the compiled statement in SQLite | k = parameter sets, taken from the iterable one at a time. For INSERT, UPDATE, DELETE and REPLACE; a SELECT raises `ProgrammingError` |
| `Cursor.executescript(sql_script, /)` | O(q) + each statement's work | O(q) | In the default transaction mode, commits an open transaction first. Bypasses the statement cache, so every run compiles every statement |
| `Cursor.fetchone()` | O(c + v) + query work | O(c + v) | One row, and the query advanced to the next |
| `Cursor.fetchmany(size=cursor.arraysize)` | O(b·c + v) + query work | O(b·c + v) | b = rows returned; `arraysize` defaults to 1 |
| `Cursor.fetchall()` | O(r·c + v) + query work | O(r·c + v) | Holds every remaining row |
| Iterating a `Cursor` | O(c + v) + query work per row | O(c + v) | Only the current row, unless you keep the rows |
| `Cursor.description` | O(1) | O(1) | Built by `execute()`, one seven-tuple per column; the same tuple on every access |
| `Cursor.rowcount`, `Cursor.lastrowid`, `Cursor.arraysize` | O(1) | O(1) | |
| `Cursor.connection`, `Cursor.row_factory` | O(1) | O(1) | `row_factory` starts as the connection's at creation |
| `Cursor.close()` | O(1) | O(1) | |
| `Cursor.setinputsizes(sizes, /)`, `Cursor.setoutputsize(size, column=None, /)` | O(1) | O(1) | DB-API no-ops |

### Row

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.Row(cursor, data)` | O(1) | O(1) | Keeps the value tuple and the cursor's description; set `row_factory = sqlite3.Row` to get these |
| `row[i]` | O(1) | O(1) | Tuple indexing |
| `row[name]` | O(c) | O(1) | Compares the key with each column name in turn; ASCII letters match case-insensitively |
| `row[i:j]`, `len(row)`, iterating a `Row` | O(j - i), O(1), O(c) | O(j - i), O(1), O(1) | |
| `Row.keys()` | O(c) | O(c) | A new list of the column names on every call |
| `row == other`, `hash(row)` | O(c + v) | O(1) | Compare and hash the column names and the values |

### Blob

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.Blob` | O(1) | O(1) | Python 3.11+; from `Connection.blobopen()` |
| `Blob.read(length=-1, /)` | O(k) | O(k) | k = bytes read. The first time a handle reaches offset o, by any read or write, it also walks the O(o) of pages before it; the handle remembers them |
| `Blob.write(data, /)` | O(k) | O(1) | k = bytes written; a blob cannot change length |
| `Blob.seek(offset, origin=os.SEEK_SET, /)`, `Blob.tell()` | O(1) | O(1) | |
| `len(blob)`, `blob[i]`, `blob[i] = byte` | O(1) | O(1) | |
| `blob[i:j:step]`, `blob[i:j:step] = data` | O(j - i) | O(j - i) | The whole span is read even when the step skips most of it |
| `Blob.close()` | O(1) | O(1) | Also on leaving a `with` block |

### Queries

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| SELECT by rowid, or by an index holding every column the query reads | O(log n + r) | O(r·c + v) if collected | The index is a B-tree; `EXPLAIN QUERY PLAN` says `COVERING INDEX` for the second |
| SELECT by any other indexed column | O((1 + r)·log n) | O(r·c + v) if collected | Each match is one more lookup in the table |
| SELECT with no usable index | O(n) | O(r·c + v) if collected | A scan of the whole table, whatever the result size, unless a LIMIT stops it early |
| ORDER BY a column with no usable index | O(n + r log r) | O(r·c + v) if collected | r = rows that match, before any LIMIT; SQLite sorts them in a temporary B-tree |
| INSERT | O((1 + i)·log n) | O(1) | The table's B-tree plus one per index |
| UPDATE, DELETE | The lookup's cost + O(r·(1 + i)·log n) | O(1) | The lookup is the WHERE clause's, as for a SELECT; for an UPDATE, i counts only the indexes on columns it changes, or all of them if it changes the rowid |

### Type conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.adapters`, `sqlite3.converters` | O(1) | O(1) | The two registries, as plain dicts |
| `sqlite3.PARSE_DECLTYPES`, `sqlite3.PARSE_COLNAMES` | O(1) | O(1) | `detect_types` flags. Each adds an O(c) converter lookup to `execute()`, then one converter call per non-empty value in a matched column. NULL and empty values come back as `None` without a call |
| `sqlite3.PrepareProtocol` | O(1) | O(1) | The protocol `adapt()` asks for |
| `sqlite3.Date`, `sqlite3.Time`, `sqlite3.Timestamp` | O(1) | O(1) | DB-API constructors, the `datetime` classes themselves |
| `sqlite3.DateFromTicks(ticks)`, `sqlite3.TimeFromTicks(ticks)`, `sqlite3.TimestampFromTicks(ticks)` | O(1) | O(1) | From a Unix timestamp |
| `sqlite3.Binary` | O(1) | O(1) | `memoryview` itself |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.Warning`, `sqlite3.Error` | O(1) | O(1) | The two roots |
| `Error.sqlite_errorcode`, `Error.sqlite_errorname` | O(1) | O(1) | Python 3.11+; the SQLite result code behind the exception |
| `sqlite3.InterfaceError`, `sqlite3.DatabaseError` | O(1) | O(1) | The DB-API split under `Error` |
| `sqlite3.DataError`, `sqlite3.IntegrityError`, `sqlite3.InternalError`, `sqlite3.NotSupportedError`, `sqlite3.OperationalError`, `sqlite3.ProgrammingError` | O(1) | O(1) | Under `DatabaseError` |
| `sqlite3.LEGACY_TRANSACTION_CONTROL` | O(1) | O(1) | Python 3.12+; the `autocommit` value that keeps the implicit-transaction behaviour |
| `sqlite3.sqlite_version`, `sqlite3.sqlite_version_info` | O(1) | O(1) | The SQLite library's version, not the module's |
| `sqlite3.apilevel`, `sqlite3.paramstyle`, `sqlite3.threadsafety` | O(1) | O(1) | DB-API 2.0 metadata |
| `sqlite3.version`, `sqlite3.version_info` | O(1) | O(1) | Deprecated in Python 3.12 and removed in Python 3.14 |
| `sqlite3.dbapi2` | O(1) | O(1) | The submodule everything above is re-exported from |
| Authorizer codes and `SQLITE_DONE`, 37 names: `sqlite3.SQLITE_SELECT`, `sqlite3.SQLITE_INSERT`, the other actions, `SQLITE_OK`, `SQLITE_DENY`, `SQLITE_IGNORE`, and `SQLITE_DONE` | O(1) | O(1) | The actions `Connection.set_authorizer()` is handed and the three values it may return; `SQLITE_DONE` is a statement's finished result |
| Result codes, 103 names: `sqlite3.SQLITE_BUSY`, `sqlite3.SQLITE_CONSTRAINT_UNIQUE`, and the rest | O(1) | O(1) | Python 3.11+; matched against `Error.sqlite_errorcode` |
| Limit categories, 12 names: `sqlite3.SQLITE_LIMIT_LENGTH` and the other `SQLITE_LIMIT_*` | O(1) | O(1) | Python 3.11+; for `Connection.setlimit()` and `getlimit()` |
| Configuration options, up to 16 names: `sqlite3.SQLITE_DBCONFIG_DEFENSIVE` and the other `SQLITE_DBCONFIG_*` | O(1) | O(1) | Python 3.12+; each exists only if the SQLite headers Python was built against declare it |

## Connecting and Executing

```python
import sqlite3

connection = sqlite3.connect(':memory:')   # O(1)
cursor = connection.cursor()               # O(1)

cursor.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)')
cursor.execute('INSERT INTO users VALUES (?, ?, ?)', (1, 'Alice', 30))  # O(log n)
connection.commit()

cursor.execute('SELECT name FROM users WHERE id = ?', (1,))   # O(log n) - rowid
assert cursor.fetchone() == ('Alice',)
assert cursor.description[0][0] == 'name'                    # O(1)

connection.close()
```

## Statement Cache

A connection keeps up to 128 compiled statements (100 on Python 3.10), keyed by the SQL text.
Re-running the same text with new parameters skips the compile; interpolating values makes a new
text for every new value, and each new text is compiled. An authorizer makes the compiles visible, because SQLite
consults it only while compiling.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)')
connection.executemany('INSERT INTO t VALUES (?, ?)', [(i, f'n{i}') for i in range(100)])

actions = []
def authorizer(action, *details):
    actions.append(action)
    return sqlite3.SQLITE_OK

connection.set_authorizer(authorizer)   # O(s) - expires the compiled statements

# One statement text, many parameter sets - compiled once
for wanted in range(10):
    connection.execute('SELECT name FROM t WHERE id = ?', (wanted,)).fetchone()  # O(log n)
assert actions.count(sqlite3.SQLITE_SELECT) == 1

# A new text every time - compiled every time, and open to injection
for wanted in range(10):
    connection.execute(f'SELECT name FROM t WHERE id = {wanted}').fetchone()
assert actions.count(sqlite3.SQLITE_SELECT) == 11

# The cache size is a connection argument
small = sqlite3.connect(':memory:', cached_statements=8)
assert small.execute('SELECT 1').fetchone() == (1,)

connection.close()
small.close()
```

## Indexes Decide the Query

With a usable index the lookup is a B-tree descent; without one it is a scan of the table.
`EXPLAIN QUERY PLAN` says which: `SEARCH` for a descent, `SCAN` for the whole table.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)')
connection.executemany(
    'INSERT INTO t VALUES (?, ?)', [(i, f'n{i}') for i in range(5000)]
)

def plan(sql, parameters=()):
    return ' '.join(row[3] for row in connection.execute('EXPLAIN QUERY PLAN ' + sql, parameters))

assert 'SEARCH' in plan('SELECT * FROM t WHERE id = ?', (4999,))       # O(log n) - rowid
assert 'SCAN' in plan('SELECT * FROM t WHERE name = ?', ('n4999',))    # O(n) - no index
assert 'TEMP B-TREE' in plan('SELECT * FROM t ORDER BY name')          # O(n log n) - a sort

connection.execute('CREATE INDEX idx_name ON t(name)')                # every insert now pays for it
assert 'SEARCH' in plan('SELECT * FROM t WHERE name = ?', ('n4999',))  # O(log n)
assert 'TEMP B-TREE' not in plan('SELECT * FROM t ORDER BY name')      # the index is in order

connection.close()
```

!!! warning "An index is not free to maintain"
    Every INSERT and DELETE updates each index on the table, and an UPDATE each index on a column
    it changes (every index, if it changes the rowid). Index the columns you filter or sort on, not every column by default.

## Fetching Rows

`fetchall()` holds every remaining row; iterating a cursor, `fetchone()` and `fetchmany()` hold
only what they return. A single TEXT or BLOB value can still be large, and a fetch can make SQLite
scan many rows to find the next match.

```python
import sqlite3
import tracemalloc

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)')
connection.executemany(
    'INSERT INTO t VALUES (?, ?)', [(i, 'x' * 100) for i in range(20000)]
)

tracemalloc.start()
rows = connection.execute('SELECT * FROM t').fetchall()   # O(r·c + v)
collected = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
assert len(rows) == 20000

tracemalloc.start()
counted = sum(1 for _ in connection.execute('SELECT * FROM t'))   # O(c + v) per row
streamed = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
assert counted == 20000

assert streamed * 100 < collected

cursor = connection.execute('SELECT id FROM t')
cursor.arraysize = 500
assert len(cursor.fetchmany()) == 500   # O(b·c + v)

connection.close()
```

## Row Objects

`sqlite3.Row` gives mapping-style access by comparing your key with each column name in turn. On a
wide row, index access is the cheap one.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.row_factory = sqlite3.Row

columns = ', '.join(f'c{i} INTEGER' for i in range(60))
connection.execute(f'CREATE TABLE wide ({columns})')
connection.execute(
    f"INSERT INTO wide VALUES ({','.join('?' * 60)})", tuple(range(60))
)

row = connection.execute('SELECT * FROM wide').fetchone()

assert row[0] == 0            # O(1) - tuple indexing
assert row['c0'] == 0         # O(c) - found on the first comparison
assert row['c59'] == 59       # O(c) - found on the sixtieth
assert len(row.keys()) == 60  # O(c)

# ASCII names match case-insensitively
assert row['C0'] == 0

connection.close()
```

## Transactions

A commit is where a file database waits for the disk, so one commit per row pays that wait per row.
Wrap a batch in one transaction.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (a INTEGER)')

# One transaction around the batch
with connection:   # commits on success, rolls back on an exception
    connection.executemany('INSERT INTO t VALUES (?)', ((i,) for i in range(1000)))
assert not connection.in_transaction

assert connection.execute('SELECT count(*) FROM t').fetchone()[0] == 1000

# The context manager does not close the connection
assert connection.execute('SELECT 1').fetchone() == (1,)

# A failure inside the block rolls the whole thing back
try:
    with connection:
        connection.execute('INSERT INTO t VALUES (?)', (9999,))
        raise RuntimeError('abandon')
except RuntimeError:
    pass
else:
    raise AssertionError('the block did not raise')

assert connection.execute('SELECT count(*) FROM t').fetchone()[0] == 1000

connection.close()
```

## Adapters and Converters

Each registration is one dict entry; the callables then run per value, in both directions.

```python
import sqlite3

class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

sqlite3.register_adapter(Point, lambda p: f'{p.x};{p.y}')          # O(1)
sqlite3.register_converter('point', lambda b: Point(*map(float, b.split(b';'))))

connection = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
connection.execute('CREATE TABLE places (location point)')
connection.execute('INSERT INTO places VALUES (?)', (Point(1.0, 2.0),))   # adapter runs here

restored = connection.execute('SELECT location FROM places').fetchone()[0]  # converter runs here
assert (restored.x, restored.y) == (1.0, 2.0)

assert (Point, sqlite3.PrepareProtocol) in sqlite3.adapters
assert 'POINT' in sqlite3.converters

connection.close()
```

## Callbacks

A registered function, aggregate or collation costs O(1) to register and then runs from inside
SQLite, once per call, row or comparison the query makes.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (name TEXT)')
connection.executemany('INSERT INTO t VALUES (?)', [(f'n{i}',) for i in range(1000)])

calls = []
def shout(text):
    calls.append(text)
    return text.upper()

connection.create_function('shout', 1, shout, deterministic=True)   # O(1)
connection.execute('SELECT shout(name) FROM t').fetchall()           # one call per row
assert len(calls) == 1000

comparisons = []
def by_length(left, right):
    comparisons.append(1)
    return (len(left) > len(right)) - (len(left) < len(right))

connection.create_collation('by_length', by_length)                 # O(1)
connection.execute('SELECT name FROM t ORDER BY name COLLATE by_length').fetchall()
assert len(comparisons) >= 999                                       # O(r log r) comparisons

connection.close()
```

## Incremental Blob I/O

`Connection.blobopen()` (Python 3.11+) reads and writes part of a BLOB without loading the value.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE files (data BLOB)')
connection.execute('INSERT INTO files VALUES (zeroblob(1000000))')   # no Python bytes at all

with connection.blobopen('files', 'data', 1) as blob:   # O(log n) - by rowid
    assert len(blob) == 1_000_000                       # O(1)
    assert blob[0:1_000_000:100_000] == bytes(10)       # O(j - i) - reads the whole span
    blob.seek(500_000)                                  # O(1)
    blob.write(b'hello')                                # O(k)
    blob.seek(500_000)
    assert blob.read(5) == b'hello'                     # O(k)

connection.close()
```

## Copying a Database

`backup()` and `iterdump()` both walk the whole database, and neither holds it in Python: `backup()`
copies pages into another connection, and `iterdump()` yields one SQL statement at a time.

```python
import sqlite3

source = sqlite3.connect(':memory:')
source.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)')
source.executemany('INSERT INTO t VALUES (?, ?)', [(i, 'x' * 1000) for i in range(1000)])
source.commit()

remaining = []
target = sqlite3.connect(':memory:')
source.backup(target, pages=50, progress=lambda status, left, total: remaining.append(left))  # O(m)
assert len(remaining) > 1 and remaining[-1] == 0
assert target.execute('SELECT count(*) FROM t').fetchone() == (1000,)

dump = source.iterdump()             # a generator
assert next(dump) == 'BEGIN TRANSACTION;'
assert sum(1 for _ in dump) == 1002  # O(m) - CREATE TABLE, 1000 INSERTs, COMMIT

source.close()
target.close()
```

`serialize()` (Python 3.11+) is the other way to copy: it returns the whole database as one `bytes`
object, so it costs O(m) memory in Python as well as time.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (payload TEXT)')
connection.executemany('INSERT INTO t VALUES (?)', [('x' * 1000,) for _ in range(100)])
connection.commit()

image = connection.serialize()   # O(m) time and memory
assert image.startswith(b'SQLite format 3\x00')

copy = sqlite3.connect(':memory:')
copy.deserialize(image)          # O(m) - copied into SQLite
assert copy.execute('SELECT count(*) FROM t').fetchone() == (100,)

connection.close()
copy.close()
```

## Errors

```python
import sqlite3
import sys

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY)')
connection.execute('INSERT INTO t VALUES (1)')

try:
    connection.execute('INSERT INTO t VALUES (1)')
except sqlite3.IntegrityError as error:
    # From 3.11 the result code is on the exception - O(1)
    if sys.version_info >= (3, 11):
        assert error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY
        assert error.sqlite_errorname == 'SQLITE_CONSTRAINT_PRIMARYKEY'
else:
    raise AssertionError('a duplicate primary key was inserted')

assert issubclass(sqlite3.IntegrityError, sqlite3.DatabaseError)
assert issubclass(sqlite3.DatabaseError, sqlite3.Error)
assert connection.Error is sqlite3.Error

connection.close()
```

## Common Patterns

### Bulk Loading

`executemany()` takes parameter sets from any iterable one at a time, so a generator loads a large
input without building it as a list, and one transaction around it pays for one commit.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE readings (sensor INTEGER, value REAL)')

def readings(count):
    for i in range(count):
        yield (i % 10, i * 0.5)

with connection:                                                          # one commit
    connection.executemany('INSERT INTO readings VALUES (?, ?)', readings(10000))  # O(k·p)

totals = dict(connection.execute(
    'SELECT sensor, count(*) FROM readings GROUP BY sensor'
))
assert totals == {sensor: 1000 for sensor in range(10)}

connection.close()
```

## Performance Best Practices

✅ **Do**:

- Use `?` placeholders - one compiled statement, reused from the cache, and no injection
- Index the columns you filter or sort on, and check with `EXPLAIN QUERY PLAN` rather than assuming
- Iterate a cursor instead of calling `fetchall()` when the result may be large
- Wrap a batch in one transaction; a commit per row waits for the disk once per row
- Reuse one `Blob` handle for many reads deep into a large blob

❌ **Avoid**:

- Interpolating values into SQL - every distinct text is compiled, and it is unsafe
- `row['name']` in a tight loop over a wide row; `row[i]` is O(1)
- `executescript()` for SQL you run repeatedly; it compiles every statement on every run
- Indexing a column you only write
- `serialize()` on a database larger than you want in memory; `backup()` copies without it

## Version Notes

- **Python 3.11+**: `Blob` and `Connection.blobopen()`; `serialize()` and `deserialize()`;
  `create_window_function()`; `setlimit()` and `getlimit()` with the 12 `SQLITE_LIMIT_*`
  constants; `sqlite_errorcode` and `sqlite_errorname` on errors SQLite reports, with the 103
  result-code constants; a default statement cache of 128 statements (100 on 3.10)
- **Python 3.12+**: `Connection.autocommit` and `LEGACY_TRANSACTION_CONTROL`; `setconfig()` and
  `getconfig()` with the build-dependent `SQLITE_DBCONFIG_*` constants; `enable_shared_cache()`
  removed; `version` and `version_info` deprecated
- **Python 3.13+**: `iterdump()` takes `filter`
- **Python 3.14+**: `version` and `version_info` removed

## Related Modules

- **[json](json.md)** - the usual way to put a structure in a TEXT column
- **[datetime](datetime.md)** - the classes the DB-API date constructors are
- **[contextlib](contextlib.md)** - `closing()` for a connection, which `with` does not close
