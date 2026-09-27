# shelve Module Complexity

The `shelve` module is a dictionary whose values persist: every value is pickled on the way in
and unpickled on the way out, and the bytes live in a `dbm` database on disk. It is a thin layer,
so almost every operation is one call to that database plus one pickle or unpickle; the shelf
keeps no values of its own unless `writeback=True` asks for a cache.

`n` is the number of keys in the shelf, `v` is the pickled length of the value an operation
stores or reads (the largest, where it handles several), `V` is the pickled length of all the
values it reads or stores, and `w` is the pickled length of everything in the writeback cache.
Pickling and unpickling are priced as linear in the pickle, and keys are short strings, so
encoding one is O(1). The bounds assume a `dbm` database underneath, as `shelve.open()` gives,
and are shelve's own work: each row names the backend calls it makes, and what one lookup, store
or delete costs belongs to the backend (see [dbm](dbm.md)). With `writeback=True`, every value
read or stored is also kept in the cache, which the Space column leaves to the `Shelf.cache` row,
and reading a cached key again costs O(1).

## Complexity Reference

### Opening a shelf

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shelve.open(filename, flag='c', protocol=None, writeback=False)` | O(1) | O(1) | Plus opening the backend `dbm.open()` picks: an existing file keeps its backend, a new one gets the first available, `dbm.sqlite3` from 3.13. `flag='n'` always creates a new, empty database with that default |
| `shelve.DbfilenameShelf(filename, flag='c', protocol=None, writeback=False)` | O(1) | O(1) | What `shelve.open()` returns |
| `shelve.Shelf(dict, protocol=None, writeback=False, keyencoding='utf-8')` | O(1) | O(1) | Wraps any mapping with bytes keys, such as a database from a chosen `dbm` backend |
| `shelve.BsdDbShelf(dict, protocol=None, writeback=False, keyencoding='utf-8')` | O(1) | O(1) | A `Shelf` over an object with cursor methods; no standard-library `dbm` backend has them |

### Shelf

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shelf[key]` | O(v) | O(v) | One backend lookup, then the value is unpickled again on every read, so a mutable value comes back as a new copy. With `writeback=True` a key already read or stored is a cache hit: O(1), the same object |
| `shelf[key] = value` | O(v) | O(v) | Pickles the value and stores it at once, with or without `writeback` |
| `del shelf[key]` | O(1) | O(1) | One backend delete |
| `key in shelf` | O(1) | O(1) | One backend lookup; nothing is unpickled |
| `Shelf.get(key, default=None)` | O(v) | O(v) | A membership test, then a read if the key is present |
| `len(shelf)` | O(1) | O(1) | One backend `len()`; `dbm.ndbm` counts its keys again after every write, O(n) |
| Iterating a shelf, `list(shelf)`, iterating `shelf.keys()` | O(n) | O(n) | The backend's whole key list is built before the first key comes back. `shelf.keys()` itself is an O(1) view |
| Iterating `shelf.items()` or `shelf.values()` | O(n + V) | O(n + v) | The key list, then one lookup and one unpickle per key |
| `shelf.pop(key[, default])`, `shelf.setdefault(key, default=None)` | O(v) | O(v) | A read and a delete, or a read that falls back to a store |
| `shelf.popitem()` | O(n + v) | O(n + v) | Builds the whole key list to find one key |
| `shelf.update(other)` | O(V) | O(v) | One store per item of `other` |
| `Shelf.clear()` | O(n² + V) | O(n + v) | One `popitem()` per key, so each removal rebuilds the key list and unpickles the value it drops |
| `DbfilenameShelf.clear()` | One backend `clear()` from Python 3.13, O(n² + V) before | O(1) from Python 3.13, O(n + v) before | The backend's `clear()` still removes keys one at a time. Before 3.13 this is `Shelf.clear()` |
| `Shelf.sync()` | O(w) | O(v) | Re-pickles and stores every cached entry, read or written, then empties the cache and calls the backend's `sync()` if it has one. O(1) without `writeback` |
| `Shelf.close()` | O(w) | O(v) | `sync()`, then the backend's `close()`; later operations raise `ValueError`. Also what leaving a `with` block does |
| `Shelf.cache` | O(1) | O(w) | With `writeback=True`, every key read or stored stays in it until it is deleted or the shelf is synced, cleared or closed; empty otherwise |

### BsdDbShelf

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BsdDbShelf.first()`, `BsdDbShelf.last()`, `BsdDbShelf.next()`, `BsdDbShelf.previous()` | O(v) | O(v) | One cursor step on the wrapped object, then an unpickled `(key, value)` pair |
| `BsdDbShelf.set_location(key)` | O(v) | O(v) | Positions the cursor at `key` and returns its pair |

## Reading and Writing

A store pickles the value and hands the bytes straight to the backend, so the shelf holds no
pending writes of its own. A read unpickles the value again every time: changing what it returns
changes nothing on disk until it is stored again.

```python
import os
import shelve
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data')

    with shelve.open(path) as shelf:        # O(1) plus the backend's open
        shelf['name'] = 'Alice'             # O(v) - pickled and stored now
        shelf['scores'] = [95, 87, 92]
        assert 'name' in shelf              # O(1) - nothing unpickled
        assert shelf.get('email', 'none') == 'none'

        scores = shelf['scores']            # O(v) - a new copy
        assert scores is not shelf['scores']
        shelf['scores'].append(100)         # changes a copy that is thrown away
        assert shelf['scores'] == [95, 87, 92]

        scores.append(100)
        shelf['scores'] = scores            # O(v) - store it again to keep it

    with shelve.open(path, flag='r') as shelf:
        assert shelf['scores'] == [95, 87, 92, 100]
        assert len(shelf) == 2              # one backend len()

    shelf.close()                           # closing twice is harmless
    try:
        shelf['name']
    except ValueError as error:
        assert 'closed shelf' in str(error)
    else:
        raise AssertionError('a closed shelf was read')
```

### Writeback

`writeback=True` keeps every value it reads or stores in memory, so in-place changes stick. The
price is that memory grows with every key touched, and `sync()` or `close()` re-pickles all of
them, changed or not, because the shelf cannot tell which ones were changed.

```python
import os
import shelve
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data')

    with shelve.open(path, writeback=True) as shelf:
        shelf['log'] = []                   # O(v) - stored now and cached
        shelf['log'].append('started')      # O(1) - a cache hit, the same object
        assert shelf['log'] is shelf['log']
        assert len(shelf.cache) == 1

        shelf.sync()                        # O(w) - re-pickles every cached entry
        assert shelf.cache == {}

    with shelve.open(path) as shelf:
        assert shelf['log'] == ['started']
```

## Iterating a Shelf

Iteration asks the backend for all of its keys at once. Every `dbm` backend returns them as a
list, so even taking the first key costs O(n) time and memory, and `popitem()` costs O(n + v).
`items()` and `values()` add one lookup and one unpickle per key.

```python
import os
import shelve
import tempfile

with tempfile.TemporaryDirectory() as directory:
    with shelve.open(os.path.join(directory, 'data')) as shelf:
        shelf.update({'a': [1, 2], 'b': [3], 'c': []})  # O(V) - one store each

        assert set(shelf) == {'a', 'b', 'c'}  # O(n) - one key list
        keys = shelf.keys()                  # O(1) - a view; iterating it is O(n)
        assert len(keys) == 3

        total = sum(len(value) for value in shelf.values())  # O(n + V)
        assert total == 3

        key, value = shelf.popitem()         # O(n + v) - the key list to find one key
        assert key not in shelf and len(shelf) == 2
```

## Choosing a Backend

`shelve.open()` lets `dbm.open()` choose: an existing file is opened with the backend that wrote
it unless `flag='n'` asks for a new one, and a new one gets the first available of `dbm.sqlite3`
(3.13+), `dbm.gnu`, `dbm.ndbm` and `dbm.dumb`. To choose yourself, open the database with that
backend and wrap it in `Shelf`.

```python
import dbm
import dbm.dumb
import os
import shelve
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data')

    with shelve.Shelf(dbm.dumb.open(path, 'c')) as shelf:  # O(1) - wraps it
        shelf['answer'] = 42

    assert dbm.whichdb(path) == 'dbm.dumb'
    with shelve.open(path) as shelf:        # the existing backend is kept
        assert shelf['answer'] == 42
```

## Emptying a Shelf

`clear()` removes one key at a time. On a `Shelf`, and on `shelve.open()`'s shelf before 3.13,
each removal is a `popitem()`, which rebuilds the whole key list and unpickles the value it
drops: O(n² + V) for the shelf. From 3.13 `shelve.open()`'s shelf hands the job to the backend's
`clear()` instead. Opening the file again with `flag='n'` starts from an empty database without
touching the keys at all.

```python
import os
import shelve
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data')

    with shelve.open(path) as shelf:
        shelf.update((f'key{i}', i) for i in range(100))
        shelf.clear()                       # key by key
        assert len(shelf) == 0

        shelf.update((f'key{i}', i) for i in range(100))

    with shelve.open(path, flag='n') as shelf:  # a new, empty database
        assert len(shelf) == 0
```

## Common Patterns

### A Persistent Memo

```python
import os
import shelve
import tempfile

def slow_square(x):
    return x * x

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'memo')
    computed = []

    def cached_square(shelf, x):
        key = str(x)
        if key in shelf:                    # O(1) - no unpickling to check
            return shelf[key]               # O(v)
        computed.append(x)
        shelf[key] = result = slow_square(x)  # O(v)
        return result

    with shelve.open(path) as shelf:
        assert cached_square(shelf, 12) == 144

    with shelve.open(path) as shelf:        # a later run finds it on disk
        assert cached_square(shelf, 12) == 144

    assert computed == [12]
```

## Performance Best Practices

✅ **Do**:

- Use `key in shelf` when only existence matters: it unpickles nothing, where `shelf[key]`
  unpickles the whole value
- Read a mutable value once, change it, and store it once, rather than reaching for `writeback`
- Keep `writeback=True` shelves short-lived, or `sync()` them, since every key touched stays in
  memory and is re-pickled
- Reopen a `shelve.open()` shelf with `flag='n'` to empty it, instead of calling `clear()`, which
  removes keys one at a time

❌ **Avoid**:

- `for key in shelf` or `popitem()` just to take one key - both build the whole key list
- `len(shelf)` in a loop that also writes, on a backend that counts its keys
- Mutating `shelf[key]` in place without `writeback` - the change is made to a copy and lost

## Version Notes

- **Python 3.13+**: New shelves use the `dbm.sqlite3` backend when `sqlite3` is available; before,
  the first available of `dbm.gnu`, `dbm.ndbm` and `dbm.dumb`
- **Python 3.13+**: `DbfilenameShelf.clear()` calls the backend's `clear()`; before, it removed
  keys through `popitem()` at O(n² + V)
- **All Python 3**: Reading a key returns a copy; an in-place change is lost unless it is stored
  again or the shelf uses `writeback=True`

## Related Modules

- **[dbm](dbm.md)** - The backends that store the bytes, and what each lookup, store and delete
  costs
- **[pickle](pickle.md)** - How values become bytes, which is the O(v) in every read and write
- **[sqlite3](sqlite3.md)** - Queries over the data rather than one key at a time
