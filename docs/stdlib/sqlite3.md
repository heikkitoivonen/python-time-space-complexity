# sqlite3 Module Complexity

The `sqlite3` module is a thin binding over the SQLite C library. Almost nothing on this page is a
Python bound: what a query costs is what SQLite's query planner decides, and the module's own
contribution is compiling the SQL, converting values, and building the row objects you get back.

Four sizes run through the table. **n** is the rows in a table, **r** the rows a query returns,
**c** the columns in a row, and **p** the parameters bound to a statement.

The two things the module itself controls, and both are worth knowing:

- **Statements are cached.** A connection keeps the last 128 compiled statements (`cached_statements`),
  so re-executing the same SQL text skips the compile. Building SQL by string interpolation
  defeats that as well as inviting injection.
- **`sqlite3.Row` looks columns up by scanning.** Index access is O(1); name access is O(c),
  comparing your key against each column name in turn.

## Complexity Reference

### Connecting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.connect(database, ...)` | O(1) | O(1) | Opens the file and reads the header; `:memory:` touches no filesystem |
| `sqlite3.Connection` | O(1) | O(1) | Also a context manager, which commits or rolls back — it does not close |
| `connection.cursor()` | O(1) | O(1) | A cursor is a position, not a copy of anything |
| `connection.close()` | O(s) | O(1) | s = cached statements, finalized on the way out |
| `sqlite3.Blob` | O(1) | O(1) | Python 3.11+; incremental blob I/O without loading the value |
| `sqlite3.LEGACY_TRANSACTION_CONTROL` | O(1) | O(1) | Python 3.12+; the `autocommit` value that keeps the old implicit-transaction behaviour |
| `sqlite3.enable_shared_cache(enable)` | O(1) | O(1) | Removed in Python 3.12; deprecated by SQLite long before |

### Executing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cursor.execute(sql, parameters)` — cached statement | O(p) + query | O(1) | The compile is skipped; the query itself is SQLite's cost |
| `cursor.execute(sql, parameters)` — new statement text | O(len(sql)) + query | O(len(sql)) | Parsed and planned, then added to the connection's cache |
| `cursor.executemany(sql, seq)` | O(m·p) + m queries | O(1) | m = parameter sets; one compile, then one bind-and-step each |
| `cursor.executescript(sql)` | O(len(sql)) | O(len(sql)) | Not cached, and it commits any open transaction first |
| SELECT with an indexed or rowid predicate | O(log n + r) | O(r) if collected | The index is a B-tree |
| SELECT with no usable index | O(n) | O(r) if collected | A full table scan, whatever the result size |
| INSERT | O(log n) per B-tree | O(1) | The table's tree plus one per index, then constraints and triggers |
| UPDATE / DELETE | O(log n + r) or O(n + r) | O(1) | The lookup is the WHERE clause's; each row touched updates every index on it |
| `connection.commit()`, `connection.rollback()` | O(d) | O(1) | d = dirty pages; a commit is where the durability cost lands |
| `sqlite3.complete_statement(sql)` | O(len(sql)) | O(1) | Whether the text ends a statement; used by interactive shells |

### Fetching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cursor.fetchone()` | O(c) | O(c) | One row built from the current step |
| `cursor.fetchmany(size)` | O(size·c) | O(size·c) | Holds only the batch |
| `cursor.fetchall()` | O(r·c) | O(r·c) | Holds the whole result; the one operation here with unbounded memory |
| Iterating a cursor | O(c) per row | O(c) | The streaming form, and what `fetchall()` gives up |
| `sqlite3.Row` — `row[i]` | O(1) | O(1) | Tuple indexing |
| `sqlite3.Row` — `row['name']` | O(c) | O(1) | Case-insensitive comparison against each column name in turn |
| `sqlite3.Row.keys()` | O(c) | O(c) | Built from `cursor.description` |
| `cursor.description` | O(c) | O(c) | Seven-tuple per column, six of them always `None` |

### Type conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.register_adapter(type, adapter)` | O(1) | O(1) | One entry in `sqlite3.adapters`; the adapter then runs per bound value |
| `sqlite3.register_converter(typename, converter)` | O(1) | O(1) | One entry in `sqlite3.converters`; the converter runs per fetched value |
| `sqlite3.adapt(obj, proto, alt)` | O(1) + adapter | O(1) | The lookup is a dict; what the adapter costs is yours |
| `sqlite3.adapters`, `sqlite3.converters` | O(1) | O(1) | The two registries, exposed as plain dicts |
| `sqlite3.PARSE_DECLTYPES`, `sqlite3.PARSE_COLNAMES` | O(1) | O(1) | `detect_types` flags; each adds a per-column lookup on every fetch |
| `sqlite3.PrepareProtocol` | O(1) | O(1) | The protocol object `adapt()` asks for |
| `sqlite3.Date`, `sqlite3.Time`, `sqlite3.Timestamp` | O(1) | O(1) | DB-API constructors, aliases of the `datetime` classes |
| `sqlite3.DateFromTicks(t)`, `sqlite3.TimeFromTicks(t)`, `sqlite3.TimestampFromTicks(t)` | O(1) | O(1) | From a Unix timestamp |
| `sqlite3.Binary` | O(1) | O(1) | An alias of `memoryview` |

### Exceptions and module metadata

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sqlite3.Warning`, `sqlite3.Error` | O(1) | O(1) | The two roots; from Python 3.11 an `Error` also carries `sqlite_errorcode` and `sqlite_errorname` |
| `sqlite3.InterfaceError`, `sqlite3.DatabaseError` | O(1) | O(1) | The DB-API split under `Error` |
| `sqlite3.DataError`, `sqlite3.IntegrityError`, `sqlite3.InternalError`, `sqlite3.NotSupportedError`, `sqlite3.OperationalError`, `sqlite3.ProgrammingError` | O(1) | O(1) | Under `DatabaseError` |
| `sqlite3.Cursor` | O(1) | O(1) | The class; instances come from `connection.cursor()` |
| `sqlite3.enable_callback_tracebacks(flag)` | O(1) | O(1) | Whether an error inside a Python callback prints a traceback |
| `sqlite3.sqlite_version`, `sqlite3.sqlite_version_info` | O(1) | O(1) | The underlying library's version, not the module's |
| `sqlite3.apilevel`, `sqlite3.paramstyle`, `sqlite3.threadsafety` | O(1) | O(1) | DB-API 2.0 metadata strings and integer |
| `sqlite3.version`, `sqlite3.version_info` | O(1) | O(1) | Deprecated in Python 3.12 and removed in Python 3.14; they described the old pysqlite package, not SQLite |
| `sqlite3.dbapi2` | O(1) | O(1) | The submodule everything above is re-exported from |

### The SQLITE_* constants

All are integers, so reading one is O(1). They come in four families. Python 3.10 has only the
first; 3.11 added the next two, and 3.12 the last.

| Family | Count | Notes |
|--------|-------|-------|
| Authorizer action codes — `SQLITE_SELECT`, `SQLITE_INSERT`, `SQLITE_CREATE_TABLE`, and the rest, plus `SQLITE_OK`, `SQLITE_DENY`, `SQLITE_IGNORE`, `SQLITE_DONE` | 37 | What `connection.set_authorizer()` is handed and what it may return |
| Result and error codes — `SQLITE_BUSY`, `SQLITE_CONSTRAINT_UNIQUE`, `SQLITE_IOERR_*`, and the rest | 103 | Python 3.11+; matched against `Error.sqlite_errorcode` |
| `SQLITE_LIMIT_*` | 12 | Python 3.11+; the categories `connection.setlimit()` and `getlimit()` take |
| `SQLITE_DBCONFIG_*` | 16 | Python 3.12+; the switches `connection.setconfig()` and `getconfig()` take |

## Connecting and Executing

```python
import sqlite3

connection = sqlite3.connect(':memory:')   # O(1), and no filesystem at all
cursor = connection.cursor()               # O(1)

cursor.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)')
cursor.execute('INSERT INTO users VALUES (?, ?, ?)', (1, 'Alice', 30))  # O(log n)
connection.commit()

cursor.execute('SELECT name FROM users WHERE id = ?', (1,))   # O(log n) - rowid
assert cursor.fetchone() == ('Alice',)

connection.close()
```

## Statements Are Cached

A connection holds the last 128 compiled statements, keyed by the SQL text. Re-running the same
text with different parameters reuses the plan; building a new string each time does not.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)')
connection.executemany('INSERT INTO t VALUES (?, ?)', [(i, f'n{i}') for i in range(100)])

# One statement text, many parameter sets - compiled once
for wanted in range(10):
    connection.execute('SELECT name FROM t WHERE id = ?', (wanted,)).fetchone()

# A new text every time - compiled every time, and open to injection
for wanted in range(10):
    connection.execute(f'SELECT name FROM t WHERE id = {wanted}').fetchone()

# The cache size is a connection argument
small = sqlite3.connect(':memory:', cached_statements=8)
assert small.execute('SELECT 1').fetchone() == (1,)

connection.close()
small.close()
```

## Indexes Decide the Query

This is the whole of the SELECT/UPDATE/DELETE rows: with a usable index the lookup is a B-tree
descent, and without one it is a scan of the table.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)')
connection.executemany(
    'INSERT INTO t VALUES (?, ?)', [(i, f'n{i}') for i in range(5000)]
)

# The integer primary key is the rowid - O(log n)
plan = connection.execute(
    'EXPLAIN QUERY PLAN SELECT * FROM t WHERE id = ?', (4999,)
).fetchone()
assert 'SEARCH' in plan[3]

# No index on name - O(n)
plan = connection.execute(
    'EXPLAIN QUERY PLAN SELECT * FROM t WHERE name = ?', ('n4999',)
).fetchone()
assert 'SCAN' in plan[3]

# One index changes the plan - O(log n)
connection.execute('CREATE INDEX idx_name ON t(name)')
plan = connection.execute(
    'EXPLAIN QUERY PLAN SELECT * FROM t WHERE name = ?', ('n4999',)
).fetchone()
assert 'SEARCH' in plan[3]

connection.close()
```

!!! warning "An index is not free to maintain"
    Every INSERT, UPDATE and DELETE has to update each index on the table. An index earns its
    place when reads outnumber writes on that column, not by default.

## Fetching Holds What You Ask For

`fetchall()` is the one operation on this page with unbounded memory. Iterating the cursor, or
`fetchmany()`, holds a row or a batch instead.

```python
import sqlite3
import tracemalloc

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)')
connection.executemany(
    'INSERT INTO t VALUES (?, ?)', [(i, 'x' * 100) for i in range(20000)]
)

tracemalloc.start()
rows = connection.execute('SELECT * FROM t').fetchall()   # O(r·c) memory
collected = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
assert len(rows) == 20000

tracemalloc.start()
counted = sum(1 for _ in connection.execute('SELECT * FROM t'))   # O(c) memory
streamed = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
assert counted == 20000

assert streamed * 100 < collected   # four orders of magnitude apart in practice

connection.close()
```

## Row Access by Name Is a Scan

`sqlite3.Row` gives you mapping-style access, and it does it by comparing your key against each
column name. On a wide row that is worth knowing.

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

# Names are matched case-insensitively
assert row['C0'] == 0

connection.close()
```

## Transactions

A commit is where durability is paid for. Doing one per row turns an O(log n) insert into an
O(log n) insert plus a disk sync.

```python
import sqlite3

connection = sqlite3.connect(':memory:')
connection.execute('CREATE TABLE t (a INTEGER)')

# One transaction around the batch
with connection:   # commits on success, rolls back on an exception
    connection.executemany('INSERT INTO t VALUES (?)', [(i,) for i in range(1000)])

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

assert Point in sqlite3.adapters or (Point, sqlite3.PrepareProtocol) in sqlite3.adapters

connection.close()
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

assert issubclass(sqlite3.IntegrityError, sqlite3.DatabaseError)
assert issubclass(sqlite3.DatabaseError, sqlite3.Error)

connection.close()
```

## Version Notes

- **Python 3.11+**: `Blob` for incremental blob I/O; `sqlite_errorcode` and `sqlite_errorname`
  on every `Error`; the 103 result-code constants and the 12 `SQLITE_LIMIT_*` categories, with
  the `setlimit`/`getlimit` methods that take them
- **Python 3.12+**: `Connection.autocommit` and `LEGACY_TRANSACTION_CONTROL`; the 16
  `SQLITE_DBCONFIG_*` switches with `setconfig`/`getconfig`; `enable_shared_cache` was removed
  and `version`/`version_info` deprecated
- **Python 3.14**: `version` and `version_info` removed

## Related Documentation

- **[json](json.md)** - the usual way to put a structure in a TEXT column
- **[datetime](datetime.md)** - what the DB-API date constructors alias
- **[contextlib](contextlib.md)** - for closing a connection, which `with` does not

## Best Practices

✅ **Do**:

- Use `?` placeholders — one compiled statement, reused, and no injection
- Index the columns you filter on, and check with `EXPLAIN QUERY PLAN` rather than assuming
- Iterate a cursor instead of `fetchall()` when the result may be large
- Wrap a batch in one transaction; `executemany()` inside one is the fast path

❌ **Avoid**:

- Interpolating values into SQL — it defeats the statement cache as well as being unsafe
- `row['name']` in a tight loop over a wide row; index access is O(1)
- Committing per row
- Indexing a column you only write
