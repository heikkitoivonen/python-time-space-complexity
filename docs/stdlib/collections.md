# collections Module Complexity

The `collections` module supplies container types that specialise `dict`, `list`, `str` and
`tuple`. Five of them have their own pages, linked below, and the abstract base classes in
`collections.abc` have theirs. The rest of this page covers `ChainMap`, which searches a list
of mappings in order instead of merging them, and `UserDict`, `UserList` and `UserString`,
which hold a plain `dict`, `list` or `str` in a `data` attribute and forward each operation
to it.

## deque

See [deque](deque.md) for operations, complexity and examples.

## defaultdict

See [defaultdict](defaultdict.md) for operations, complexity and examples.

## Counter

See [Counter](counter.md) for operations, complexity and examples.

## namedtuple

See [namedtuple](namedtuple.md) for operations, complexity and examples.

## OrderedDict

See [OrderedDict](ordereddict.md) for operations, complexity and examples.

## collections.abc

See [collections.abc](collections.abc.md) for the abstract base classes and the cost of their
mixin methods. Everything `ChainMap` and the wrappers do not define themselves comes from those
mixins, and a mixin is written in terms of the wrapper's own `__getitem__`, `__iter__` and
`__setitem__`, so a subclass that overrides one of those pays for it on every step of the mixin.

## Size Variables

For `ChainMap`, `n` is the number of maps, `i` the position of the first map that holds a key
(`n` for a miss), `N` the total number of entries across all maps and `m` the entries in
`maps[0]`. For the wrappers, `n` is `len(wrapper)`, and `d` is the slots that earlier deletions
left in the dict's table. Everywhere, `k` is the size of the other operand or the number of
items supplied. Key hashing and comparison are O(1), the `ChainMap` rows assume its maps are
dicts, and an operation forwarded to `data` costs what the [dict](../builtins/dict.md),
[list](../builtins/list.md) or [str](../builtins/str.md) page says.

## Complexity Reference

### ChainMap

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `collections.ChainMap(*maps)` | O(n) | O(n) | Keeps the maps in a list; nothing is copied or merged, so a later change to any map shows through |
| `ChainMap.maps` | O(1) | O(1) | The list itself; reorder or extend it to change the search order |
| `cm[key]` | O(i) | O(1) | Tries each map in order until one has the key; a miss tries all n and raises `KeyError` |
| `key in cm` | O(i) | O(1) | The same search |
| `cm.get(key, default=None)` | O(i) | O(1) | Searches twice on a hit: once for `in`, once for the value |
| `cm[key] = value`, `del cm[key]`, `cm.pop(key)`, `cm.popitem()` | O(1) | O(1) | `maps[0]` only; deleting a key that lives in a later map raises `KeyError` |
| `cm.update(other)`, `cm \|= other` | O(k) | O(k) | Into `maps[0]` |
| `cm.setdefault(key, default=None)` | O(i) | O(1) | Returns a value found in any map; only a miss writes, and it writes to `maps[0]` |
| `cm.clear()` | O(m) | O(1) | Empties `maps[0]` and nothing else |
| `bool(cm)` | O(n) | O(1) | Stops at the first non-empty map; a chain of empty maps checks every one |
| `len(cm)` | O(n + N) | O(n + N) | Builds a set of every key to count the distinct ones, visiting every map even when it is empty |
| `cm.keys()`, `cm.items()`, `cm.values()` | O(1) | O(1) | Views over the chain; the cost is paid when they are iterated |
| Iterating `cm` or `cm.keys()` | O(n + N) | O(N) | Builds a dict of every key before yielding the first: the last map's keys, then each earlier map's new keys |
| Iterating `cm.items()` or `cm.values()`, `dict(cm)` | O(n + N·n) | O(N) | The key pass, then `cm[key]` for each key, which searches the chain again |
| `cm == other` | O(n + N·n + k) | O(N + k) | Flattens both sides into dicts and compares those |
| `cm.new_child(m=None, **kwargs)` | O(n + k) | O(n + k) | A new `ChainMap` sharing every existing map, with `m` in front; keyword arguments are written into `m` when both are given, and into a fresh dict otherwise |
| `ChainMap.parents` | O(n) | O(n) | A new `ChainMap` over `maps[1:]`; the maps are shared, the list is not |
| `cm.copy()` | O(m + n) | O(m + n) | Copies `maps[0]` and shares the rest |
| `ChainMap.fromkeys(iterable, value=None)` | O(k) | O(k) | One dict under a one-map chain |
| `cm \| other` | O(m + n + k) | O(m + n + k) | `copy()`, then `other` into the copy's first map |
| `other \| cm` | O(n + N + k) | O(N + k) | A one-map `ChainMap` holding every entry flattened: the layers are gone |

### UserDict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `collections.UserDict(dict=None, /, **kwargs)` | O(k) | O(k) | Fills `data` through `update()`, one `__setitem__` call per item |
| `UserDict.data` | O(1) | O(1) | The plain dict; operate on it directly to bypass the wrapper and its mixins |
| `ud[key]`, `ud[key] = value`, `del ud[key]`, `key in ud`, `len(ud)` | O(1) | O(1) | Forwarded; `ud[key]` checks membership first so that a subclass's `__missing__` can run |
| `ud.get(key, default=None)` | O(1) | O(1) | Python 3.12+: does not call `__missing__`; before 3.12 it did |
| `ud.keys()`, `ud.items()`, `ud.values()` | O(1) | O(1) | Views holding a reference to the wrapper |
| Iterating `ud` or `ud.keys()` | O(n) | O(1) | The dict's own iteration |
| Iterating `ud.items()` or `ud.values()` | O(n) | O(1) | One `ud[key]` per key |
| `ud.update(other)` | O(k) | O(1) | One `__setitem__` call per item |
| `ud \|= other` | O(k) | O(1) | One `dict.update` on `data` |
| `ud \| other` | O(n + k) | O(n + k) | Merges the two dicts, then builds a new wrapper from the result, so every item passes through `__setitem__` again |
| `ud.copy()` | O(n) | O(n) | A plain `UserDict` copies `data`; a subclass is shallow-copied, then refilled through `update()` |
| `UserDict.fromkeys(iterable, value=None)` | O(k) | O(k) | One `__setitem__` call per key |
| `ud.pop(key)`, `ud.setdefault(key, default=None)` | O(1) | O(1) | `ud[key]` and then `del ud[key]` or `ud[key] = default` |
| `ud.popitem()` | O(d) | O(1) | Removes the first key in iteration order; d is the entries deleted before it, which a fresh iterator has to skip |
| `ud.clear()` | O(n·(n + d)) | O(1) | `popitem()` until empty, each call skipping every slot the earlier ones emptied; `ud.data.clear()` is O(n) |
| `ud == other` | O(n + k) | O(n + k) | Flattens both sides into dicts and compares those, even when `other` is already a dict |

### UserList

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `collections.UserList(initlist=None)` | O(k) | O(k) | Copies a list or another `UserList`; any other iterable is consumed into a new list |
| `UserList.data` | O(1) | O(1) | The plain list |
| `ul[i]`, `ul[i] = value`, `len(ul)` | O(1) | O(1) | Forwarded |
| `ul[i:j]` | O(j - i) | O(j - i) | Returns `type(ul)`, built through its `__init__`; so do `copy()`, `+` and `*` |
| `ul.append(x)` | O(1) amortized | O(1) | Forwarded |
| `ul.insert(i, x)`, `del ul[i]`, `ul.pop(i=-1)`, `ul.remove(x)` | O(n) | O(1) | Items after `i` shift, so `pop()` from the end is O(1) |
| `ul.extend(other)`, `ul += other` | O(k) | O(k) | `+=` copies a non-list iterable into a list before extending |
| `ul + other`, `ul * k` | O(n + k), O(n·k) | O(n + k), O(n·k) | A new instance of `type(ul)`; `other` may be a list, a `UserList` or any iterable |
| `ul *= k` | O(n·k) | O(n·k) | In place |
| `x in ul`, `ul.count(x)`, `ul.index(x)`, `ul.reverse()` | O(n) | O(1) | Forwarded |
| `ul.sort(*, key=None, reverse=False)` | O(n log n) | O(n) | `list.sort` on `data` |
| `ul.clear()`, `ul.copy()` | O(n) | O(1), O(n) | `copy()` is `type(ul)(ul)` |
| Iterating `ul` or `reversed(ul)` | O(n) | O(1) | The `Sequence` mixins: one `ul[i]` call per item, and `iter()` ends on the `IndexError` from `ul[n]` |
| `ul == other`, `ul < other` | O(min(n, k)) | O(1) | Compares `data` with the other list, or with the other `UserList`'s `data` |

### UserString

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `collections.UserString(seq)` | O(1) | O(1) | A `str` is held as is, not copied; anything else goes through `str()` first, at that conversion's cost |
| `UserString.data` | O(1) | O(1) | The plain str |
| `us[i]`, `us[i:j]` | O(1), O(j - i) | O(1), O(j - i) | A new `type(us)` around the character or slice, never a `str` |
| Iterating `us` | O(n) | O(1) | The `Sequence` mixin: one `us[i]` per character, so every character arrives as a fresh wrapper |
| `len(us)`, `str(us)` | O(1) | O(1) | `str(us)` is `data` itself |
| `hash(us)` | O(n) | O(1) | The hash of `data` |
| `sub in us`, `us.count(sub)`, `us.find(sub)`, `us.rfind(sub)`, `us.index(sub)`, `us.rindex(sub)`, `us.startswith(prefix)`, `us.endswith(suffix)` | O(n + k) avg | O(1) | The `str` search's average case; plain `int` or `bool` results |
| `us.capitalize()`, `us.casefold()`, `us.center(width)`, `us.expandtabs()`, `us.ljust(width)`, `us.lower()`, `us.lstrip()`, `us.removeprefix(prefix)`, `us.removesuffix(suffix)`, `us.replace(old, new)`, `us.rjust(width)`, `us.rstrip()`, `us.strip()`, `us.swapcase()`, `us.title()`, `us.translate(table)`, `us.upper()`, `us.zfill(width)` | O(n + output) | O(n + output) | A new `str` wrapped in `type(us)`, as long as the output: n for the case and strip methods, `width` for the padding ones, and whatever the replacement or table produces |
| `us.split()`, `us.rsplit()`, `us.splitlines()`, `us.partition(sep)`, `us.rpartition(sep)` | O(n) | O(n) | Plain `list` or `tuple` of `str`: the wrapper type is dropped |
| `us.join(iterable)` | O(k + output) | O(k + output) | A plain `str`; k = strings joined, held in a list first unless already a sequence |
| `us.encode()` | O(n) | O(n) | Plain `bytes` |
| `us.format(*args, **kwargs)`, `us.format_map(mapping)` | O(n + output) | O(n + output) | A plain `str`; the whole template is scanned |
| `us.isalnum()`, `us.isalpha()`, `us.isdecimal()`, `us.isdigit()`, `us.isidentifier()`, `us.islower()`, `us.isnumeric()`, `us.isprintable()`, `us.isspace()`, `us.istitle()`, `us.isupper()` | O(n) | O(1) | Stop at the first character that settles the answer |
| `us.isascii()` | O(1) | O(1) | Reads a flag the `str` keeps |
| `us + other`, `other + us` | O(n + k) | O(n + k) | A new wrapper; a non-`str` operand goes through `str()` |
| `us * k`, `us % args` | O(n·k), O(n + output) | O(n·k), O(n + output) | A new wrapper |
| `us == other`, `us < other` | O(min(n, k)) | O(1) | Compares `data`; `other` may be a `str` or a `UserString` |
| `UserString.maketrans(x, y=None, z=None)` | O(k) | O(k) | `str.maketrans` itself |
| `int(us)` | O(n²) | O(n) | `int()` on `data`, so the decimal-digit limit on the [int](../builtins/int.md) page applies |
| `float(us)`, `complex(us)` | O(n) | O(n) | Conversions of `data` |

## Layering With ChainMap

### Lookups Walk the Chain

A `ChainMap` holds references, not copies. Every read tries the maps in order and stops at
the first hit, so a key in the last map costs n lookups and a miss always does. Writes go to
`maps[0]` alone, which is what makes the chain useful for scoping: a child scope shadows its
parents without touching them.

```python
from collections import ChainMap

defaults = {"timeout": 30, "retries": 3}
user = {"timeout": 60}
config = ChainMap(user, defaults)  # O(n) - two references, nothing copied

assert config["timeout"] == 60  # O(i) - found in the first map
assert config["retries"] == 3  # O(i) - found in the second
assert config.get("colour", "none") == "none"  # O(n) - a miss checks every map

config["retries"] = 5  # O(1) - into maps[0]
assert user == {"timeout": 60, "retries": 5}
assert defaults["retries"] == 3  # the parent is untouched

del config["timeout"]  # O(1) - maps[0] has it
try:
    del config["timeout"]  # now only defaults has it
except KeyError as error:
    assert "first mapping" in str(error)
else:
    raise AssertionError("a key in a later map was deleted")

# Scopes: new_child() puts a fresh map in front, parents drops the front one
scope = config.new_child()  # O(n) - shares every map
scope["timeout"] = 1
assert scope["timeout"] == 1 and config["timeout"] == 30
assert scope.parents.maps == config.maps  # O(n) - a new list over the same maps
```

### Counting and Iterating Cost Every Key

There is no shortcut for `len()`: the chain builds a set of every key to find out how many are
distinct, and iteration builds a dict of every key before yielding one. Both visit every map
and every entry, O(n + N), on a structure that otherwise holds nothing, so a chain over large
maps should not be measured or iterated in a loop. Iteration order is the last map's keys, then each earlier
map's keys that were not already seen.

```python
from collections import ChainMap

first = {"a": 1, "b": 2}
second = {"c": 3, "a": 0}
chain = ChainMap(first, second)

assert len(chain) == 3  # O(n + N) - a set of every key, counted once each
assert list(chain) == ["c", "a", "b"]  # O(n + N) - built before the first key is yielded
assert dict(chain) == {"a": 1, "b": 2, "c": 3}  # O(n + N·n) - each key searched again

# Flattening through | keeps the values the chain would return, but not the layers
flat = {"z": 26} | chain  # O(n + N + k)
assert flat.maps == [{"z": 26, "c": 3, "a": 1, "b": 2}]
```

## Wrapping With UserDict, UserList and UserString

### Hooks Run Once Per Item

The wrappers exist to be subclassed. An overridden `UserDict.__setitem__` sees construction,
`update()`, `fromkeys()` and `|`, which all go item by item through it, where subclassing
`dict` would not; `|=` and the methods forwarded to `data` bypass it. An overridden
`__getitem__` on a `UserList` or `UserString` sees every step of iteration, which goes index
by index through it rather than through the underlying object's iterator.

```python
from collections import UserDict, UserList

class Recording(UserDict):
    def __init__(self, *args, **kwargs):
        self.writes = 0
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.writes += 1
        super().__setitem__(key, value)

recorded = Recording({"a": 1, "b": 2, "c": 3})  # O(k) - one __setitem__ per item
assert recorded.writes == 3

recorded.update(d=4)  # O(k) - the mixin loop, one __setitem__ per item
assert recorded.writes == 4

merged = recorded | {"e": 5}  # O(n + k) - the merged dict is fed back through __setitem__
assert merged.writes == 5
assert recorded.writes == 4

class Indexed(UserList):
    reads = 0

    def __getitem__(self, index):
        Indexed.reads += 1
        return super().__getitem__(index)

items = Indexed([10, 20, 30])
assert list(items) == [10, 20, 30]  # O(n) - n + 1 __getitem__ calls, the last raising IndexError
assert Indexed.reads == 4
```

### Clearing a UserDict

`UserDict` does not define `clear()`, `popitem()` or `pop()`; it inherits them from
`MutableMapping`. Its `popitem()` takes the first key a fresh iterator yields, and a dict's
iterator has to skip every slot that earlier deletions emptied, so a `popitem()` costs O(d) and
emptying the whole dict through `clear()` costs O(n·(n + d)). Clear the `data` dict directly.

```python
from collections import UserDict

wrapped = UserDict({"a": 1, "b": 2, "c": 3})

assert wrapped.popitem() == ("a", 1)  # O(d) - the first key still present
assert wrapped.popitem() == ("b", 2)

wrapped.data.clear()  # O(n) - the dict's own clear
assert len(wrapped) == 0

wrapped.update(zip("xyz", range(3)))
wrapped.clear()  # O(n·(n + d)) - popitem() until empty
assert len(wrapped) == 0
```

### Wrappers Come Back as Wrappers

The `UserString` methods that transform text, such as `upper()` and `strip()`, return a new
`type(us)`, and so do indexing and iteration, so a loop over a `UserString` allocates one
wrapper per character. Methods that return containers of text, such as `split()` and
`partition()`, return plain `str` inside a plain `list` or `tuple`, and `join()`, `format()`
and `format_map()` return a plain `str`. `UserList` slicing and arithmetic
return `type(ul)` as well, built through `__init__`, so a subclass constructor with extra
required arguments breaks slicing.

```python
from collections import UserString

source = "abc"
text = UserString(source)  # O(1) - the str is held, not copied
assert text.data is source

assert type(text.upper()) is UserString  # O(n) - a new str, wrapped
assert type(text[0]) is UserString  # O(1) - even one character is wrapped
assert all(type(char) is UserString for char in text)  # O(n) - one wrapper per character

assert type(text.split()) is list and type(text.split()[0]) is str  # O(n) - plain str inside
assert type(text.join(["x", "y"])) is str  # O(output) - plain str
assert type(text.encode()) is bytes
assert text.count("b") == 1 and text.find("z") == -1  # O(n + k) - plain int results
```

## Common Patterns

### Settings With Overrides

```python
from collections import ChainMap

defaults = {"host": "localhost", "port": 8000, "debug": False}
environment = {"port": 8080}
command_line = {"debug": True}

settings = ChainMap(command_line, environment, defaults)  # O(n) - three references

assert settings["port"] == 8080  # O(i) - the environment wins over the default
assert settings["debug"] is True  # O(i) - the command line wins over everything
assert settings["host"] == "localhost"  # O(n) - found in the last map

# Read the resolved settings once, then work from the dict
resolved = dict(settings)  # O(n + N·n) - once, not on every read
assert resolved == {"host": "localhost", "port": 8080, "debug": True}
```

## Performance Best Practices

✅ **Do**:

- Keep a `ChainMap` short: every miss, `get()` on a default and read of a key in the last map costs one lookup per map
- Flatten with `dict(chain)` once when a chain is read in a loop, so the per-map search happens once per key rather than once per read
- Clear a `UserDict` through `data.clear()`; the inherited `clear()` is quadratic in the entries and the slots deleted before them
- Reach for `ud.data`, `ul.data` or `us.data` when a hot loop does not need the subclass hooks

❌ **Avoid**:

- `len()` or iteration over a `ChainMap` in a loop - each call rebuilds a set or dict of every key
- Comparing a `UserDict` with `==` on a hot path: the mixin flattens both sides into new dicts each time
- Iterating a `UserString` character by character; every character is a new wrapper object
- A `UserList` subclass whose `__init__` needs extra arguments: slicing, `copy()`, `+` and `*` all construct through it

## Version Notes

- **Python 3.12+**: `UserDict.get()` returns the default for a missing key without calling `__missing__`; before 3.12 the inherited `Mapping.get()` went through `__getitem__` and called it
- **All Python 3**: `len()` and iteration over a `ChainMap` cost every entry in every map; nothing about the chain is cached

## Related Modules

- **[dict](../builtins/dict.md)** - what the forwarded `UserDict` operations cost
- **[list](../builtins/list.md)** - what the forwarded `UserList` operations cost
- **[str](../builtins/str.md)** - what the forwarded `UserString` operations cost
