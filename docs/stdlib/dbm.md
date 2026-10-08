# dbm Module Complexity

The `dbm` module is a persistent key-value store with four interchangeable backends:
`dbm.sqlite3` (3.13+), `dbm.gnu`, `dbm.ndbm` and the pure-Python `dbm.dumb`. `dbm.open()` picks
one, and every backend hands back an object that behaves like a dictionary of `bytes` stored in
a file. What a single-key operation costs is the backend's: a B-tree lookup in SQLite, a hash
bucket in GDBM and ndbm, and a dictionary held in memory beside a data file in `dbm.dumb`.

The backends differ most in what they do to the whole database: how they count keys, whether
they can iterate, and what deleting or emptying costs. `n` is the keys stored, `v` the length of
the value read, written, replaced or deleted, `V` the total length of all values, and `d` the
changes not yet written to disk. For `dbm.gnu` and `dbm.ndbm`, `b` is the size of the file's
hash table - its buckets and, for GDBM, the directory that points to them. It grows with the keys
the file has held and is not given back when keys are deleted, so with keys that hash evenly b
is O(n) for a database that has not shrunk, and n is O(b) always. Keys are treated as short, so
hashing and comparing one is O(1). Space bounds assume `bytes`; a `str` key or value is first
encoded to UTF-8, an O(v) copy.

## Complexity Reference

### dbm

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.open(file, flag='r', mode=0o666)` | O(1) to O(n + b) | O(1) to O(n + b) | An existing file is opened by the backend `whichdb()` names; a new one, or any file with `flag='n'`, by the first available of `dbm.sqlite3`, `dbm.gnu`, `dbm.ndbm` and `dbm.dumb`. Costs that backend's `open()`: O(n) for `dbm.dumb`, O(b) for `dbm.gnu` and for `dbm.ndbm` on GDBM's emulation, O(1) for the others |
| `dbm.whichdb(filename)` | O(1) | O(1) | Checks which of each backend's files exist and reads at most 16 bytes of the main file; a Berkeley DB `.db` file is also opened with `dbm.ndbm` to confirm it |
| `dbm.error` | O(1) | O(1) | A tuple of `dbm`'s own exception class and `OSError`, so `except dbm.error` catches every backend's error |

### dbm.sqlite3

Python 3.13+. Each pair is a row in one SQLite table with a unique index on the key, so
single-key operations are indexed lookups, and every write is committed as it is made. The
object `dbm.sqlite3.open()` returns is called `sqlite3` here, as in the official documentation.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.sqlite3.open(filename, /, flag='r', mode=0o666)` | O(1) | O(1) | Opens an SQLite connection; independent of the keys already stored |
| `sqlite3[key]`, `sqlite3.get(key, default=None)`, `sqlite3.setdefault(key, default)` | O(log n + v) | O(v) | One indexed lookup; `setdefault()` also stores a missing key |
| `key in sqlite3` | O(log n + v) | O(v) | Fetches the value it does not return |
| `sqlite3[key] = value` | O(log n + v) | O(v) | Committed immediately: another connection sees it before `close()`. v includes a replaced value, whose pages are freed |
| `del sqlite3[key]` | O(log n + v) | O(1) | Frees the deleted value's pages |
| `len(sqlite3)`, `bool(sqlite3)` | O(n) | O(1) | Counts the keys on every call; nothing is cached, and `bool()` calls `len()` |
| Iterating `sqlite3` | O(n) | O(1) | Streams the keys from one query |
| `sqlite3.keys()` | O(n) | O(n) | Builds a list |
| Iterating `sqlite3.items()` or `sqlite3.values()` | O(n log n + V) | O(v) | One lookup per key on top of the key scan |
| `sqlite3.clear()` | O(n log n + V) | O(v) | One lookup and one `DELETE` per key; `flag='n'` starts an empty file instead |
| `sqlite3.close()` | O(w) | O(1) | w = pages in SQLite's write-ahead log, which the last connection to close copies into the database file |
| `dbm.sqlite3.error` | O(1) | O(1) | Subclass of `OSError` |

### dbm.gnu

Unix, and only where CPython was built against the GDBM library; otherwise `import dbm.gnu`
raises `ImportError`. GDBM hashes keys into buckets, so single-key operations are O(1) on
average. The object `dbm.gnu.open()` returns is called `gdbm`. It is not iterable and has no
`items()` or `values()`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.gnu.open(filename, flag='r', mode=0o666, /)` | O(b) | O(b) | Reads GDBM's bucket directory into memory; `flag` may add `'f'` (fast: writes are not synchronized), `'s'` (synchronized) or `'u'` (no locking) |
| `dbm.gnu.open_flags` | O(1) | O(1) | The flag characters this GDBM build accepts |
| `dbm.gnu.error` | O(1) | O(1) | Subclass of `OSError`; a missing key raises `KeyError` |
| `gdbm[key]`, `gdbm.get(key, default=None)`, `gdbm.setdefault(key, default)` | O(1 + v) avg | O(v) | `setdefault()` also stores a missing key |
| `key in gdbm` | O(1) avg | O(1) | Checks for the key without fetching the value |
| `gdbm[key] = value` | O(1 + v) avg | O(1) | |
| `del gdbm[key]` | O(1) avg | O(1) | |
| `len(gdbm)` | O(b), then O(1) | O(1) | Counted once and cached until the next store or delete |
| `bool(gdbm)` | O(1) to O(b) | O(1) | 3.12+: stops at the first key, walking any emptied buckets ahead of it; before 3.12 it calls `len()` |
| `gdbm.firstkey()`, `gdbm.nextkey(key)` | O(b) for a full walk | O(1) | Visits every key in hash order without building a list |
| `gdbm.keys()` | O(b) | O(n) | Builds a list |
| `gdbm.reorganize()` | O(b + V) | O(n + V) on disk | Copies the live records into a new file; space freed by deletes is otherwise only reused, never returned |
| `gdbm.sync()` | O(d) | O(1) | Needed only in fast mode |
| `gdbm.clear()` | O(n·b) | O(1) | 3.13+. One delete per key, each finding the first remaining key by walking from the first bucket past the emptied ones: quadratic for a database that has not shrunk |
| `gdbm.close()` | O(d) | O(1) | Writes pending changes and releases the file |

### dbm.ndbm

Unix, and only where CPython was built against an ndbm library: Berkeley DB, GDBM's ndbm
emulation, or the system's own. `dbm.ndbm.library` names it. Keys are hashed into buckets, so
single-key operations are O(1) on average. The object `dbm.ndbm.open()` returns is called
`ndbm`. It is not iterable and has no `items()` or `values()`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.ndbm.open(filename, flag='r', mode=0o666, /)` | O(1) | O(1) | Independent of the keys already stored; built on GDBM's emulation it costs what `dbm.gnu.open()` does |
| `dbm.ndbm.library` | O(1) | O(1) | The name of the ndbm implementation this build uses |
| `dbm.ndbm.error` | O(1) | O(1) | Subclass of `OSError`; a missing key raises `KeyError` |
| `ndbm[key]`, `ndbm.get(key, default=None)`, `ndbm.setdefault(key, default=b'')` | O(1 + v) avg | O(v) | `setdefault()` also stores a missing key |
| `key in ndbm` | O(1 + v) avg | O(v) | Fetches the value it does not return |
| `ndbm[key] = value` | O(1 + v) avg | O(1) | |
| `del ndbm[key]` | O(1) avg | O(1) | |
| `len(ndbm)` | O(b), then O(1) | O(1) | Counted once and cached until the next store or delete |
| `bool(ndbm)` | O(1) to O(b) | O(1) | 3.12+: stops at the first key, walking any emptied buckets ahead of it; before 3.12 it calls `len()` |
| `ndbm.keys()` | O(b) | O(n) | Builds a list; the only way to list the keys |
| `ndbm.clear()` | O(n·b) | O(1) | 3.13+. One delete per key, each finding the first remaining key by walking from the first bucket past the emptied ones: quadratic for a database that has not shrunk |
| `ndbm.close()` | O(d) | O(1) | Writes pending changes and releases the file |

### dbm.dumb

Pure Python and always available. A `.dir` file holds the key index, which is read into a
dictionary when the database is opened and kept in memory until it is closed; a `.dat` file
holds the values. The object `dbm.dumb.open()` returns is called `dumbdbm`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.dumb.open(filename, flag='c', mode=0o666)` | O(n) | O(n) | Reads the whole key index; `flag='n'` discards it unread |
| `dbm.dumb.error` | O(1) | O(1) | `OSError` itself |
| `dumbdbm[key]`, `dumbdbm.get(key, default=None)`, `dumbdbm.setdefault(key, default)` | O(1 + v) avg | O(v) | A dictionary lookup, then one read of the data file; `setdefault()` also stores a missing key |
| `key in dumbdbm`, `len(dumbdbm)`, `bool(dumbdbm)` | O(1) avg | O(1) | Answered from the index in memory, without touching a file |
| `dumbdbm[key] = value` | O(1 + v) avg | O(1) | Writes the value, and a new key's index line; a replacement that does not fit the old value's blocks is appended, and the old blocks are never reused |
| `del dumbdbm[key]` | O(n) | O(1) | Rewrites the whole key index file |
| Iterating `dumbdbm` | O(n) | O(1) | Walks the index in memory |
| `dumbdbm.keys()` | O(n) | O(n) | Builds a list |
| `dumbdbm.items()` | O(n + V) | O(n + V) | Builds a list, reading every value |
| Iterating `dumbdbm.values()` | O(n + V) | O(v) | One data-file read per key |
| `dumbdbm.clear()` | O(n² + V) | O(v) | One read and delete per key, each delete rewriting the rest of the index; `flag='n'` starts empty instead |
| `dumbdbm.sync()` | O(n) | O(1) | Rewrites the whole key index if anything has been written |
| `dumbdbm.close()` | O(n) | O(1) | `sync()`, then releases the index |

## Choosing a Backend

Without `flag='n'`, `dbm.open()` costs one `whichdb()` check and then the chosen backend's
`open()`. An existing
file keeps the backend that wrote it; a new file, or any file opened with `flag='n'`, gets the
first one this build has.

```python
import dbm
import dbm.dumb

# A new database: the first backend available
with dbm.open('mydb', 'c') as db:              # the chosen backend's open()
    db[b'key'] = b'value'
backend = dbm.whichdb('mydb')                   # O(1): reads a file header
assert backend in ('dbm.sqlite3', 'dbm.gnu', 'dbm.ndbm', 'dbm.dumb')

# An existing file is reopened by the backend that wrote it
with dbm.dumb.open('portable', 'c') as db:     # O(n): reads the key index
    db[b'key'] = b'value'
assert dbm.whichdb('portable') == 'dbm.dumb'
with dbm.open('portable', 'r') as db:        # O(n): dbm.dumb again
    assert db[b'key'] == b'value'

# dbm.gnu exists only where CPython was built with GDBM
try:
    import dbm.gnu
except ImportError:
    pass
else:
    with dbm.gnu.open('gnudb', 'c') as db:     # O(b): reads the bucket directory
        db[b'key'] = b'value'
        assert db[b'key'] == b'value'
```

## Single-Key Operations

### Store and Retrieve

Every backend accepts `str` keys and values, stores them as UTF-8, and returns `bytes`. Other
objects need encoding first, which costs O(v) on the way in and on the way out.

```python
import dbm
import json

with dbm.open('data', 'c') as db:
    db[b'name'] = b'Alice'                       # one store
    db['city'] = 'Oslo'                          # str is stored as UTF-8
    assert db[b'city'] == b'Oslo'                # and read back as bytes
    assert b'name' in db                         # one lookup
    assert db.get(b'missing', b'?') == b'?'

    data = {'name': 'Alice', 'age': 30}
    db[b'user'] = json.dumps(data).encode()      # O(v) to encode
    assert json.loads(db[b'user']) == data       # O(v) to decode

    db[b'name'] = b'Bob'                         # a store replaces
    del db[b'name']                              # O(n) on dbm.dumb
    assert b'name' not in db
```

### Deleting from dbm.dumb

`dbm.dumb` keeps its key index in a dictionary and rewrites the whole index file on every
delete, while a store writes the value and, for a new key, appends one index line. Deleting
many keys one at a time is therefore quadratic; `flag='n'` replaces the database without reading
it.

```python
import dbm
import dbm.dumb

with dbm.dumb.open('dumb', 'c') as db:
    for i in range(100):
        db[b'k%d' % i] = b'v'                    # O(1 + v): appends
    del db[b'k0']                                # O(n): rewrites the index
    assert len(db) == 99                         # O(1): the index is in memory

with dbm.dumb.open('dumb', 'n') as db:           # O(1): the old index is not read
    assert len(db) == 0
```

## Whole-Database Operations

### Listing and Iterating Keys

`keys()` is the one way to list keys that every backend supports; it builds the whole list.
`for key in db`, `items()` and `values()` work on `dbm.sqlite3` and `dbm.dumb` only: a
`dbm.ndbm` or `dbm.gnu` database is not iterable, and `dbm.gnu` walks its keys without a list
through `firstkey()` and `nextkey()` instead.

```python
import dbm

with dbm.open('users', 'c') as db:
    db[b'user1'] = b'Alice'
    db[b'user2'] = b'Bob'
    db[b'user3'] = b'Charlie'

    # keys() works on every backend and builds a list - O(n), O(b) on ndbm/gnu
    keys = db.keys()
    assert sorted(keys) == [b'user1', b'user2', b'user3']
    names = {key: db[key] for key in keys}  # one lookup per key
    assert names[b'user2'] == b'Bob'

# Direct iteration streams keys without a list, but only some backends allow it
with dbm.open('users', 'r') as db:
    if dbm.whichdb('users') in ('dbm.sqlite3', 'dbm.dumb'):
        assert sorted(db) == [b'user1', b'user2', b'user3']  # O(n) to iterate, then a sort
    else:
        try:
            iter(db)
        except TypeError:
            pass  # dbm.ndbm and dbm.gnu
        else:
            raise AssertionError('only dbm.sqlite3 and dbm.dumb are iterable')
```

### Counting Keys

`dbm.dumb` answers `len()` from memory. `dbm.ndbm` and `dbm.gnu` count by walking every bucket,
and cache the count until the next write. `dbm.sqlite3` counts every key on every call, and so
does `bool()`, which it answers through `len()`.

```python
import dbm

with dbm.open('counted', 'c') as db:
    for i in range(10):
        db[b'k%d' % i] = b'v'
    assert bool(db)           # O(n) on dbm.sqlite3; O(b) on ndbm/gnu before 3.12
    assert len(db) == 10      # O(n) on dbm.sqlite3 every time; ndbm/gnu walk once, then cache
```

### Emptying a Database

`clear()` deletes key by key. On `dbm.dumb` each delete rewrites the rest of the index, and on
`dbm.ndbm` and `dbm.gnu` each one walks past the emptied buckets to find the first remaining
key. All three are quadratic in the keys, and `dbm.ndbm` and `dbm.gnu` cost more again in a file
that once held more. Opening with `flag='n'` gives an empty database without touching the old
keys.

```python
import dbm
import dbm.dumb

with dbm.dumb.open('scratch', 'c') as db:
    for i in range(50):
        db[b'k%d' % i] = b'v'
    db.clear()                                   # O(n² + V) on dbm.dumb
    assert len(db) == 0

with dbm.open('fresh', 'c') as db:
    db[b'k'] = b'v'
with dbm.open('fresh', 'n') as db:               # a new, empty database
    assert b'k' not in db and db.keys() == []
```

## The SQLite Backend

On 3.13+ a new database made by `dbm.open()` is a `dbm.sqlite3` file whenever SQLite is
available. Lookups, stores and deletes are indexed, but `len()` counts every key each time it is
called, and `key in db` reads the value it does not return.

```python
import dbm
import dbm.sqlite3

with dbm.open("default", "c") as db:            # O(1)
    db[b"key"] = b"value"                       # O(log n + v)
assert dbm.whichdb("default") == "dbm.sqlite3"

with dbm.sqlite3.open("store.sqlite", "c") as db:   # O(1)
    db[b"alpha"] = b"1"                         # O(log n + v)
    db["beta"] = "2"                            # str keys and values are stored as UTF-8
    assert db[b"beta"] == b"2"                  # O(log n + v)
    assert b"alpha" in db                       # O(log n + v): fetches the value
    assert len(db) == 2                         # O(n): counted on every call
    assert sorted(db) == [b"alpha", b"beta"]    # O(n) to stream the keys, then a sort

try:
    dbm.sqlite3.open("missing.sqlite")          # flag "r" needs an existing file
except dbm.error as error:
    assert isinstance(error, dbm.sqlite3.error)
else:
    raise AssertionError("opening a missing database read-only should fail")
```

## File Modes

```python
import dbm

# 'n' - always create a new, empty database
with dbm.open('modes', 'n') as db:
    db[b'key'] = b'value'

# 'c' - read-write, create if missing
with dbm.open('modes', 'c') as db:
    db[b'other'] = b'value'

# 'r' - read-only, the default
with dbm.open('modes', 'r') as db:
    assert db[b'key'] == b'value'

# 'w' - read-write, fails if the database does not exist
try:
    dbm.open('newdata', 'w')
except dbm.error:
    pass
else:
    raise AssertionError("'w' should not create a database")
```

## Common Patterns

### Counter Storage

```python
import dbm

def increment(db, name):
    key = name.encode()
    count = int(db.get(key, b'0')) + 1           # one lookup
    db[key] = str(count).encode()                # one store
    return count

with dbm.open('counters', 'c') as db:
    increment(db, 'page_views')
    assert increment(db, 'page_views') == 2
    assert int(db[b'page_views']) == 2
```

### Loading Everything Once

Reading a whole database costs one key listing and one lookup per key, whatever the backend.
`keys()` is the portable way to start it.

```python
import dbm
import json

with dbm.open('config', 'c') as db:
    db[b'database.host'] = json.dumps('localhost').encode()
    db[b'database.port'] = json.dumps(5432).encode()
    db[b'debug'] = json.dumps(True).encode()

with dbm.open('config', 'r') as db:
    config = {key.decode(): json.loads(db[key]) for key in db.keys()}  # one lookup per key

assert config == {'database.host': 'localhost', 'database.port': 5432, 'debug': True}
```

## Performance Best Practices

✅ **Do**:

- Use `with dbm.open(...)` so `close()` writes pending changes and releases the file
- Keep a count yourself if a `dbm.sqlite3` program needs it often; each `len()` counts every key
- Open with `flag='n'` to start over, rather than calling `clear()`
- Use `shelve` when the values are Python objects rather than bytes; it pickles on each store

❌ **Avoid**:

- `if db:` or `len(db)` in a loop over a `dbm.sqlite3` database - each is O(n)
- Deleting many keys from a `dbm.dumb` database - each delete rewrites its whole index
- `clear()` on `dbm.dumb`, `dbm.ndbm` or `dbm.gnu` - quadratic in the keys stored, or worse
- Opening a large `dbm.dumb` database for a single lookup - opening reads every key

## Version Notes

- **Python 3.12+**: `bool()` on a `dbm.gnu` or `dbm.ndbm` database no longer counts every key
- **Python 3.13+**: Added `dbm.sqlite3`, which `dbm.open()` tries first when it creates a new
  database; `dbm.gnu` and `dbm.ndbm` databases gained `clear()`

## Related Modules

- **[shelve](shelve.md)** - a `dbm` database whose values are pickled Python objects
- **[sqlite3](sqlite3.md)** - tables, indexes and queries when one key and one value is not enough
- **[pickle](pickle.md)** - what `shelve` uses to turn objects into the bytes `dbm` stores
- **[json](json.md)** - a portable encoding for values stored as bytes
