# dbm Module Complexity

The `dbm` module provides interfaces to various Unix database implementations, allowing persistent key-value storage with different backend options for different performance/compatibility needs.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.open()` | O(1) to O(n) | O(1) to O(n) | Open/create database; O(1) for `dbm.sqlite3` and `dbm.ndbm`, O(n) for `dbm.dumb`, which reads its whole key index into memory, and for `dbm.gnu`, which reads its bucket directory |
| `db[key] = value` | O(1) to O(log n) | O(k) | Backend-dependent; gdbm is O(1) avg |
| `db[key]` | O(1) to O(log n) | O(v) | Backend-dependent; gdbm is O(1) avg; v = length of the value returned |
| `del db[key]` | O(1) to O(n) | O(1) to O(n) | Backend-dependent; `dbm.dumb` rewrites its whole key index on every delete |
| `key in db` | O(1) to O(log n) | O(1) | Backend-dependent |
| `db.keys()` | O(n) | O(n) | A list of every key; works on every backend |
| Iterating `db` | O(n) | O(1) | `dbm.sqlite3` and `dbm.dumb` only; `dbm.ndbm` and `dbm.gnu` databases are not iterable |
| Iterating `db.items()` or `db.values()` | O(n) plus one lookup per item | O(v) | `dbm.sqlite3`'s `items()` and `values()`, and `dbm.dumb`'s `values()`; `dbm.ndbm` and `dbm.gnu` databases have neither method |
| `db.items()` on `dbm.dumb` | O(n) plus one lookup per item | O(n + V) | V = total length of the values; builds the whole list when called, rather than returning a view |
| `db.close()` | O(n) | O(1) | Flush and close |
| `whichdb()` | O(1) | O(1) | Detect backend type |
| `error` | O(1) | O(1) | Exception type |

### dbm.sqlite3

Python 3.13+. `dbm.open()` tries this backend first when it creates a new database. Each pair is
a row in one SQLite table with a unique index on the key, so single-key operations are indexed
lookups. Here `n` is the number of keys stored and `v` the length of the value read, written,
replaced or deleted; keys are treated as short.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.sqlite3.open(filename, flag="r", mode=0o666)` | O(1) | O(1) | Opens an SQLite connection; independent of the keys already stored |
| `db[key]` | O(log n + v) | O(v) | One indexed lookup |
| `db[key] = value` | O(log n + v) | O(v) | Committed immediately: another connection sees it before `close()`; a replaced value's pages are freed too |
| `del db[key]` | O(log n + v) | O(1) | Frees the deleted value's pages |
| `key in db` | O(log n + v) | O(v) | Fetches the value to answer |
| `len(db)` | O(n) | O(1) | Counts the keys on every call; nothing is cached |
| Iterating `db` | O(n) | O(1) | Streams the keys from one query |
| `db.keys()` | O(n) | O(n) | Builds a list |
| Iterating `db.items()` or `db.values()` | O(n log n + V) | O(v) | V = total length of the values; one lookup per key on top of the key scan |
| `sqlite3.close()` (`db.close()`) | O(w) | O(1) | w = pages in SQLite's write-ahead log, which the last connection to close copies into the database file |
| `dbm.sqlite3.error` | O(1) | O(1) | Subclass of `OSError`, so `except dbm.error` catches it |

### dbm.gnu

Unix, and only where CPython was built against the GDBM library; otherwise `import dbm.gnu`
raises `ImportError`. GDBM hashes keys into buckets, so single-key operations are O(1) on
average, as in the table above. `gdbm` is the object `dbm.gnu.open()` returns, and `n` is the
number of keys stored.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.gnu.open(filename, flag="r", mode=0o666)` | O(n) | O(n) | Reads GDBM's bucket directory, which grows with the keys stored, into memory; `flag` may add `'f'` (fast: writes are not synchronized), `'s'` (synchronized) or `'u'` (no locking) |
| `dbm.gnu.open_flags` | O(1) | O(1) | The flag characters this GDBM build accepts |
| `dbm.gnu.error` | O(1) | O(1) | GDBM errors; a missing key raises `KeyError` |
| `len(gdbm)` | O(n), then O(1) | O(1) | Counted once and cached until the next store or delete |
| `gdbm.firstkey()`, `gdbm.nextkey(key)` | O(n) for a full walk | O(1) | Visits every key in hash order without building a list |
| `gdbm.keys()` | O(n) | O(n) | Builds a list |
| `gdbm.reorganize()` | O(n) | O(n) on disk | Copies the live records into a new file; deleted space is otherwise kept for reuse and never returned |
| `gdbm.sync()` | O(d) | O(1) | d = changes not yet written; needed only in fast mode |
| `gdbm.clear()` | O(n) | O(1) | Deletes key by key; 3.13+ |
| `gdbm.close()` | O(d) | O(1) | Writes pending changes and releases the file |

## DBM Variants

### Available Backends

```python
import dbm
import dbm.dumb

# Auto-detect: a new database uses the first backend available
with dbm.open('mydb', 'c') as db:
    db[b'key'] = b'value'
backend = dbm.whichdb('mydb')  # O(1): reads the file's header
assert backend in ('dbm.sqlite3', 'dbm.gnu', 'dbm.ndbm', 'dbm.dumb')

# dbm.dumb - pure Python, always available
with dbm.dumb.open('portable', 'c') as db:
    db[b'key'] = b'value'
assert dbm.whichdb('portable') == 'dbm.dumb'

# dbm.gnu - only where CPython was built with GDBM
try:
    import dbm.gnu
except ImportError:
    pass
else:
    with dbm.gnu.open('gnudb', 'c') as db:
        db[b'key'] = b'value'
```

### Recommended Backends

```
Priority:
1. dbm.gnu - Fastest, most reliable (Linux/Unix)
2. dbm.ndbm - Berkeley DB (Unix systems)
3. dbm.dumb - Pure Python (slow but portable)

For new code: Use shelve + dbm.gnu
For portability: Use shelve + dbm.dumb
```

## Basic Key-Value Operations

### Store and Retrieve

```python
import dbm

# Open database - O(1)
db = dbm.open('mydata', 'c')

# Store key-value pairs - O(log n) each
db[b'name'] = b'Alice'      # Must use bytes!
db[b'age'] = b'30'
db[b'score'] = b'95.5'

# Retrieve values - O(log n)
name = db[b'name']         # b'Alice'
age = db[b'age']           # b'30'

# Check key existence - O(log n)
if b'name' in db:
    print(f"Name: {db[b'name']}")

# Close database - O(n) flush
db.close()
```

### String Encoding

```python
import dbm

db = dbm.open('strings', 'c')

# DBM requires bytes, so encode/decode
key = 'username'
value = 'john_doe'

# Store - encode to bytes - O(log n)
db[key.encode()] = value.encode()

# Retrieve - decode from bytes - O(log n)
retrieved = db[key.encode()].decode()
print(retrieved)  # 'john_doe'

db.close()
```

## Iteration and Keys

### Iterate Keys

`keys()` is the one way to list keys that every backend supports; it builds the whole list.
`for key in db`, `items()` and `values()` work on `dbm.sqlite3` and `dbm.dumb` only - a
`dbm.ndbm` or `dbm.gnu` database is not iterable, and `dbm.gnu` walks its keys without a list
through `firstkey()` and `nextkey()` instead.

```python
import dbm

with dbm.open('data', 'c') as db:
    db[b'user1'] = b'Alice'
    db[b'user2'] = b'Bob'
    db[b'user3'] = b'Charlie'

    # keys() works on every backend - O(n), builds a list
    keys = db.keys()
    assert sorted(keys) == [b'user1', b'user2', b'user3']
    names = {key: db[key] for key in keys}  # one lookup per key
    assert names[b'user2'] == b'Bob'

    assert len(db) == 3  # O(n) on dbm.sqlite3; see the tables above

# Direct iteration streams keys without a list, but only some backends allow it
with dbm.open('data', 'r') as db:
    if dbm.whichdb('data') in ('dbm.sqlite3', 'dbm.dumb'):
        assert sorted(db) == [b'user1', b'user2', b'user3']  # O(n) to iterate, then a sort
    else:
        try:
            iter(db)
        except TypeError:
            pass  # dbm.ndbm and dbm.gnu
        else:
            raise AssertionError('only dbm.sqlite3 and dbm.dumb are iterable')
```

## Modifications

### Update and Delete

```python
import dbm

db = dbm.open('data', 'c')

# Store initial value - O(log n)
db[b'counter'] = b'0'

# Update - O(log n)
db[b'counter'] = b'1'
db[b'counter'] = b'2'

# Delete key - O(log n)
db[b'temp'] = b'data'
del db[b'temp']

# Conditional delete
if b'temp' in db:
    del db[b'temp']

db.close()
```

## Context Manager

### Automatic Cleanup

```python
import dbm

# Use context manager - O(1) open
with dbm.open('data', 'c') as db:
    
    # Store - O(log n)
    db[b'key'] = b'value'
    
    # Retrieve - O(log n)
    value = db[b'key']
    print(value)

# Automatically closed
```

## File Modes

### Open Modes

```python
import dbm

# 'n' - always create a new, empty database - O(1)
with dbm.open('data', 'n') as db:
    db[b'key'] = b'value'

# 'c' - read-write, create if missing (opening costs as in the dbm.open() row)
with dbm.open('data', 'c') as db:
    db[b'other'] = b'value'

# 'r' - read-only, the default
with dbm.open('data', 'r') as db:
    assert db[b'key'] == b'value'

# 'w' - read-write, fails if the database does not exist
try:
    dbm.open('newdata', 'w')
except dbm.error:
    pass
else:
    raise AssertionError("'w' should not create a database")
```

## Data Type Restrictions

### Keys and Values Are Bytes

Every backend accepts `str` keys and values and encodes them as UTF-8, and returns `bytes`. Other
objects need encoding first, which costs O(v) on the way in and on the way out.

```python
import dbm
import json

with dbm.open('data', 'c') as db:
    db['key'] = 'value'                          # str is stored as UTF-8
    assert db[b'key'] == b'value'                # and read back as bytes

    data = {'name': 'Alice', 'age': 30}
    db[b'user'] = json.dumps(data).encode()      # O(v) to encode
    assert json.loads(db[b'user']) == data       # O(v) to decode
```

## Performance Characteristics

### Backend Comparison

```python
import dbm
import dbm.dumb
import time

data = [(f'key{i}'.encode(), f'value{i}'.encode()) for i in range(1000)]

# dbm.dumb (slowest but portable)
start = time.time()
with dbm.dumb.open('dumb_test', 'n') as db:
    for key, value in data:
        db[key] = value
dumb_time = time.time() - start

# dbm.gnu (fast, if available)
try:
    import dbm.gnu
    start = time.time()
    with dbm.gnu.open('gnu_test', 'n') as db:
        for key, value in data:
            db[key] = value
    gnu_time = time.time() - start
    print(f"GNU: {gnu_time:.4f}s vs Dumb: {dumb_time:.4f}s")
except ImportError:
    print("GNU DBM not available")
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

## Common Patterns

### Simple Cache

```python
import dbm
import json
import time

class PersistentCache:
    """Simple DBM-based cache"""
    
    def __init__(self, path='cache.db'):
        self.db = dbm.open(path, 'c')
    
    # Set with TTL
    def set(self, key, value, ttl=None):
        """Store with optional expiration - O(log n)"""
        entry = {
            'value': value,
            'time': time.time(),
            'ttl': ttl
        }
        encoded_key = key.encode() if isinstance(key, str) else key
        self.db[encoded_key] = json.dumps(entry).encode()
    
    # Get with expiration check
    def get(self, key, default=None):
        """Retrieve with TTL check - O(log n)"""
        encoded_key = key.encode() if isinstance(key, str) else key
        
        if encoded_key not in self.db:
            return default
        
        entry = json.loads(self.db[encoded_key].decode())
        
        # Check expiration
        if entry['ttl'] and time.time() - entry['time'] > entry['ttl']:
            del self.db[encoded_key]
            return default
        
        return entry['value']
    
    def close(self):
        """Close database - O(n)"""
        self.db.close()

# Usage
cache = PersistentCache()
cache.set('user:1', {'name': 'Alice', 'age': 30})
user = cache.get('user:1')
print(user)
cache.close()
```

### Counter Storage

```python
import dbm

class CounterStore:
    """Count things persistently"""
    
    def __init__(self, path='counters.db'):
        self.db = dbm.open(path, 'c')
    
    # Increment counter - O(log n)
    def increment(self, counter_name):
        key = counter_name.encode()
        
        current = int(self.db.get(key, b'0'))
        self.db[key] = str(current + 1).encode()
        
        return current + 1
    
    # Get counter - O(log n)
    def get(self, counter_name):
        key = counter_name.encode()
        return int(self.db.get(key, b'0'))
    
    def close(self):
        self.db.close()

# Usage
counters = CounterStore()
counters.increment('page_views')
counters.increment('page_views')
print(counters.get('page_views'))  # 2
counters.close()
```

### Configuration Storage

```python
import dbm
import json

class DBMConfig:
    """Store configuration in DBM"""
    
    def __init__(self, path='config.db'):
        self.db = dbm.open(path, 'c')
    
    # Save config - O(log n)
    def set(self, key, value):
        encoded_key = key.encode()
        encoded_value = json.dumps(value).encode()
        self.db[encoded_key] = encoded_value
    
    # Load config - O(log n)
    def get(self, key, default=None):
        encoded_key = key.encode()
        if encoded_key in self.db:
            return json.loads(self.db[encoded_key].decode())
        return default
    
    # Get all as dict - one lookup and decode per key: keys() works on every
    # backend, items() does not
    def get_all(self):
        return {
            key.decode(): json.loads(self.db[key].decode())
            for key in self.db.keys()
        }
    
    def close(self):
        self.db.close()

# Usage
config = DBMConfig()
config.set('database.host', 'localhost')
config.set('database.port', 5432)
config.set('debug', True)

assert config.get('database.host') == 'localhost'
assert config.get_all() == {'database.host': 'localhost', 'database.port': 5432, 'debug': True}
config.close()
```

## Limitations and Alternatives

### DBM Limitations
- Keys and values are bytes (`str` is encoded as UTF-8)
- No complex queries
- Limited to key-value pairs
- Not suitable for relationships

### When to Use

```python
import dbm

# Good for: simple persistent key-value storage, caches, configuration
with dbm.open('simple_store', 'c') as db:
    db[b'setting'] = b'on'
    assert db[b'setting'] == b'on'

# For structured data or queries, use sqlite3 instead
```

## Comparison with Alternatives

### DBM vs Shelve

```python
# DBM: lower level, bytes only
import dbm
with dbm.open('raw', 'c') as db:
    db[b'key'] = b'value'

# Shelve: stores any picklable value, pickling on every store and unpickling on every load
import shelve
with shelve.open('objects') as shelf:
    shelf['key'] = {'complex': 'object'}
    assert shelf['key'] == {'complex': 'object'}
```

### DBM vs SQLite

```python
# DBM: one key, one value, lookups by key only
import dbm
with dbm.open('kv', 'c') as db:
    db[b'key'] = b'value'

# SQLite: tables, indexes and queries
import sqlite3
conn = sqlite3.connect('data.db')
conn.execute('CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value TEXT)')
conn.execute("INSERT OR REPLACE INTO data VALUES ('key', 'value')")
conn.commit()
assert conn.execute('SELECT value FROM data WHERE key = ?', ('key',)).fetchone() == ('value',)
conn.close()
```

## Best Practices

### Do's
- Use shelve instead of dbm directly
- Encode strings to bytes explicitly
- Use context managers
- Close database when done
- Use appropriate backend

### Avoid's
- Don't store complex objects directly
- Don't share between processes without synchronization
- Don't iterate over keys repeatedly
- Don't use for large datasets
- Don't call `len()` repeatedly on a `dbm.sqlite3` database - each call counts every key

## Version Notes

- **Python 3.13+**: Added `dbm.sqlite3`, which `dbm.open()` tries first when it creates a new
  database; `dbm.gnu` and `dbm.ndbm` databases gained `clear()`

## Related Documentation

- [Shelve Module](shelve.md)
- [Pickle Module](pickle.md)
- [SQLite3 Module](sqlite3.md)
- [JSON Module](json.md)
