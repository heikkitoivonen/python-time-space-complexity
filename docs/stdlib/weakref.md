# weakref Module Complexity

The `weakref` module refers to an object without keeping it alive. A weak reference, a proxy,
a weak container entry and a finalizer each cost O(1) to make. The rest of their cost is paid
when the referent dies: once per weak reference to it.

`w` is the weak references to one referent - plain references, proxies, callback references,
and one per weak-container entry or finalizer that names it. `n` is the entries in a weak
container, and `m` is the items in the other operand of an update, comparison or set operation.
Container bounds are average case, and every bound treats hashing and `==` on referents, keys
and elements as O(1);
callbacks and finalizer functions cost whatever they do, on top of the bounds here.

## Complexity Reference

### ref

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.ref(obj, callback=None)` | O(1) | O(1) | Without a callback, returns the object's existing plain reference if it has one; with a callback, a new reference every call. `TypeError` for objects that do not support weak references, such as `int`, `str`, `tuple` and `list` instances |
| Calling a reference, `r()` | O(1) | O(1) | The referent, or `None` once it has been freed |
| `r.__callback__` | O(1) | O(1) | The callback, or `None` |
| `hash(r)` | O(1) | O(1) | Hashes the referent on the first call and caches the result; `TypeError` if the referent died before the reference was ever hashed |
| `r1 == r2` | O(1) | O(1) | Compares the referents while both are alive, and the references by identity once either is dead |
| `weakref.ReferenceType` | O(1) | O(1) | The reference class; `weakref.ref` is the same object |

### proxy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.proxy(obj, callback=None)` | O(1) | O(1) | Shared without a callback, the same way `ref` is |
| An operation through a proxy | O(1) plus the operation | O(1) plus the operation | Forwarded to the referent; `ReferenceError` once it has been freed |
| `weakref.ProxyType`, `weakref.CallableProxyType`, `weakref.ProxyTypes` | O(1) | O(1) | The proxy types, for `isinstance`; a callable referent gets a `CallableProxyType` |

### Counting and listing references

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.getweakrefcount(obj)` | O(w) | O(1) | Walks the referent's list of weak references to count them |
| `weakref.getweakrefs(obj)` | O(w) | O(w) | A new list of every weak reference and proxy to `obj` |
| The referent dying | O(w) | O(w) | Clears every weak reference to it, then calls each reference's callback once |

### WeakMethod

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.WeakMethod(meth, callback=None)` | O(1) | O(1) | Weak references to the instance and the function, so it lives as long as both do |
| Calling a `WeakMethod` | O(1) | O(1) | A new bound method each call, or `None` once the instance or function has been freed |

### finalize

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.finalize(obj, func, /, *args, **kwargs)` | O(1) | O(1) | One registry entry, which holds `func`, `args` and `kwargs` strongly until it runs or is detached |
| Calling a `finalize` | O(1) plus `func` | O(1) | Runs `func` the first time, whether called or triggered by `obj` dying, and returns `None` after that |
| `finalize.detach()`, `finalize.peek()` | O(1) | O(1) | `(obj, func, args, kwargs)` while alive, else `None`; `detach()` also stops it running |
| `finalize.alive` | O(1) | O(1) | `False` once it has run or been detached |
| `finalize.atexit` | O(1) | O(1) | Writable; finalizers still alive at exit with it true run then, newest first |

### WeakKeyDictionary

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.WeakKeyDictionary(dict=None)` | O(m) | O(m) | m = items in `dict` |
| `d[key]`, `d.get(key, default=None)`, `key in d` | O(1) | O(1) | |
| `d[key] = value`, `d.setdefault(key, default=None)` | O(1) | O(1) | A new entry adds a callback reference to its key, so a key in several of these dictionaries has one reference per dictionary |
| `del d[key]`, `d.pop(key[, default])`, `d.popitem()` | O(1) | O(1) | |
| `len(d)` | O(1) | O(1) | |
| Iterating `d`, `d.keys()`, `d.values()`, `d.items()` | O(n) | O(n) on 3.14+, O(1) before | Python 3.14+ copies the underlying dictionary when iteration starts |
| `d.keyrefs()` | O(n) | O(n) | A list of weak references to the keys |
| `d.copy()`, `copy.copy(d)` | O(n) | O(n) | Keys and values are shared with `d` |
| `copy.deepcopy(d)` | O(n) plus copying the values | O(n) plus the copies | Values are deep-copied, keys are not |
| `d.update(other)`, `d \|= other` | O(m) | O(m) | |
| `d \| other` | O(n + m) | O(n + m) | |
| An entry's key dying | O(1) | O(1) | Its callback removes the entry |

### WeakValueDictionary

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.WeakValueDictionary(other=(), /, **kw)` | O(m) | O(m) | m = items in `other` and `kw` |
| `d[key]`, `d.get(key, default=None)`, `key in d` | O(1) | O(1) | |
| `d[key] = value`, `d.setdefault(key, default=None)` | O(1) | O(1) | Each entry holds its own callback reference to its value |
| `del d[key]`, `d.pop(key[, default])`, `d.popitem()` | O(1) | O(1) | |
| `len(d)` | O(1) | O(1) | |
| Iterating `d`, `d.keys()`, `d.values()`, `d.items()`, `d.itervaluerefs()` | O(n) | O(n) on 3.14+, O(1) before | Python 3.14+ copies the underlying dictionary when iteration starts |
| `d.valuerefs()` | O(n) | O(n) | A list of weak references to the values |
| `d.copy()`, `copy.copy(d)` | O(n) | O(n) | |
| `copy.deepcopy(d)` | O(n) plus copying the keys | O(n) plus the copies | Keys are deep-copied, values are not |
| `d.update(other)`, `d \|= other` | O(m) | O(m) | |
| `d \| other` | O(n + m) | O(n + m) | |
| An entry's value dying | O(1) | O(1) | Its callback removes the entry |

### WeakSet

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `weakref.WeakSet(data=None)` | O(m) | O(m) | m = items in `data` |
| `s.add(item)` | O(1) | O(1) | Each element holds its own callback reference |
| `item in s`, `s.discard(item)`, `s.remove(item)`, `s.pop()` | O(1) | O(1) | |
| `len(s)` | O(1) | O(1) | |
| Iterating `s` | O(n) | O(n) on 3.14+, O(1) before | Python 3.14+ copies the underlying set when iteration starts |
| `s.copy()` | O(n) | O(n) | |
| `s.clear()` | O(n) | O(1) | |
| `s.update(other)`, `s \|= other`, `s ^= other`, `s.symmetric_difference_update(other)` | O(m) | O(m) | |
| `s -= other`, `s.difference_update(other)` | O(m) | O(1) | |
| `s & other`, `s.intersection(other)`, `s.isdisjoint(other)` | O(m) | O(m) | Walks `other` and tests each item against `s`, so `s` may be as large as it likes |
| `s &= other`, `s.intersection_update(other)` | O(n + m) | O(m) | Drops every element of `s` not in `other` |
| `s \| other`, `s - other`, `s ^ other` and their named forms | O(n + m) | O(n + m) | A new `WeakSet` |
| `s <= other`, `s < other`, `s >= other`, `s > other`, `s == other`, `s.issubset(other)`, `s.issuperset(other)` | O(n + m) | O(m) | |
| An element dying | O(1) | O(1) | Its callback removes it |

## Weak References

### Shared and Per-Callback References

A reference without a callback is shared: asking for another returns the one the object already
has. Every callback reference is a new object, and every entry in a weak container adds one,
since each carries the callback that removes it. Those are what `w` counts.

```python
import weakref

class Node:
    pass

node = Node()

first = weakref.ref(node)   # O(1)
second = weakref.ref(node)  # O(1) - the same object again
assert first is second
assert first() is node      # O(1)

def on_death(reference):
    pass

with_callback = weakref.ref(node, on_death)  # O(1) - always a new reference
assert with_callback is not first
assert with_callback.__callback__ is on_death

registry = weakref.WeakSet()
registry.add(node)  # O(1) - one more callback reference to node
assert weakref.getweakrefcount(node) == 3  # O(w)
assert len(weakref.getweakrefs(node)) == 3  # O(w)

try:
    weakref.ref(42)
except TypeError as error:
    assert 'cannot create weak reference' in str(error)
else:
    raise AssertionError('an int accepted a weak reference')
```

### When the Referent Dies

Dying costs O(w): every weak reference is cleared, and each one's callback runs once. When that
happens depends on the object. CPython frees an object as soon as its last strong reference goes,
unless it is part of a reference cycle, which waits for the cycle collector. The examples here
call `gc.collect()` so that they hold either way.

```python
import gc
import weakref

class Resource:
    pass

resource = Resource()
seen = []

reference = weakref.ref(resource, seen.append)  # O(1)

del resource
gc.collect()

assert reference() is None  # O(1)
assert seen == [reference]  # the callback ran once, with the dead reference
```

### Proxies

A proxy stands in for the object itself: attribute access, calls and operators are forwarded,
each at the cost of the operation behind it. Once the referent is gone, every use raises
`ReferenceError`.

```python
import gc
import weakref

class Account:
    def __init__(self):
        self.balance = 10

    def deposit(self, amount):
        self.balance += amount
        return self.balance

account = Account()
view = weakref.proxy(account)  # O(1)
assert weakref.proxy(account) is view  # shared, like ref()
assert isinstance(view, weakref.ProxyTypes)

assert view.deposit(5) == 15  # O(1) plus the method

del account
gc.collect()

try:
    view.balance
except ReferenceError as error:
    assert 'no longer exists' in str(error)
else:
    raise AssertionError('a dead proxy was used')
```

## Weak Containers

### A Cache That Does Not Keep Values Alive

A `WeakValueDictionary` looks up like a dictionary, but an entry disappears when nothing else
holds its value. The key is held strongly, the value weakly.

```python
import gc
import weakref

class Image:
    def __init__(self, name):
        self.name = name

cache = weakref.WeakValueDictionary()

logo = Image('logo.png')
cache['logo'] = logo  # O(1)
assert cache['logo'] is logo  # O(1)
assert 'logo' in cache  # O(1)
assert len(cache) == 1  # O(1)

del logo
gc.collect()

assert 'logo' not in cache
assert cache.get('logo') is None
assert len(cache) == 0
```

### Attaching Data Without Keeping Objects Alive

A `WeakKeyDictionary` is the reverse: it holds its values strongly and its keys weakly. A value
that refers back to its own key therefore keeps that key alive for as long as the dictionary
lives.

```python
import gc
import weakref

class Widget:
    pass

sizes = weakref.WeakKeyDictionary()

button = Widget()
sizes[button] = (80, 20)  # O(1)
assert sizes[button] == (80, 20)  # O(1)

del button
gc.collect()
assert len(sizes) == 0  # the entry went with its key

pinned = Widget()
sizes[pinned] = [pinned]  # the value refers to the key
del pinned
gc.collect()
assert len(sizes) == 1  # so the key never dies
```

### Iterating a Weak Container

Iteration visits the live entries, and one whose object dies in the middle of it is skipped
without an error. From Python 3.14, iterating any of the three containers first copies its
underlying dictionary or set, which costs O(n) memory at the first item; in return, the container
can be changed inside the loop, which walks the entries it started with. Before 3.14, iteration
holds O(1) extra memory, and adding or removing an entry inside the loop raises `RuntimeError`.

```python
import sys
import weakref

class Item:
    pass

items = [Item() for _ in range(3)]
live = weakref.WeakKeyDictionary((item, index) for index, item in enumerate(items))

assert sorted(live.values()) == [0, 1, 2]  # O(n)
assert len(live.keyrefs()) == 3  # O(n)

try:
    for item in live:  # O(n) memory at the first item on 3.14+
        live.pop(items[2], None)
except RuntimeError:
    assert sys.version_info < (3, 14)
else:
    assert sys.version_info >= (3, 14)
assert len(live) == 2
```

### Tracking a Group of Objects

`WeakSet` keeps membership without ownership. `&` walks only its right-hand operand, testing
each item against the set, so the set being large does not slow it down.

```python
import gc
import weakref

class Connection:
    pass

open_connections = weakref.WeakSet()
connections = [Connection() for _ in range(4)]
for connection in connections:
    open_connections.add(connection)  # O(1)

assert connections[0] in open_connections  # O(1)
assert len(open_connections) == 4  # O(1)

recent = connections[2:]
assert set(open_connections & recent) == set(recent)  # O(m), m = len(recent)

del connections
gc.collect()
assert set(open_connections) == set(recent)  # O(n)
```

## Bound Methods

A plain reference to a bound method dies with the bound method, which is a temporary object built
on attribute access. `WeakMethod` holds the instance and the function
instead, and builds a new bound method each time it is called.

```python
import gc
import weakref

class Button:
    def click(self):
        return 'clicked'

button = Button()

plain = weakref.ref(button.click)
gc.collect()
assert plain() is None  # the temporary bound method has gone

method = weakref.WeakMethod(button.click)  # O(1)
assert method()() == 'clicked'  # O(1) to rebuild the bound method

del button
gc.collect()
assert method() is None
```

## Finalizers

`finalize` runs a function once, when the object dies, when the finalizer is called, or at
interpreter exit, whichever comes first. The function and its arguments are held strongly, so
they must not refer to the object, or it can never die.

```python
import gc
import weakref

class TempFile:
    pass

removed = []
temp = TempFile()

finalizer = weakref.finalize(temp, removed.append, 'temp.dat')  # O(1)
assert finalizer.alive  # O(1)
assert finalizer.peek()[1:3] == (removed.append, ('temp.dat',))  # O(1)
assert finalizer.atexit is True

del temp
gc.collect()
assert removed == ['temp.dat']  # ran once, on the object's death
assert not finalizer.alive
assert finalizer() is None  # later calls do nothing

early = weakref.finalize(TempFile, removed.append, 'unused')
assert early.detach()[2] == ('unused',)  # O(1) - it will not run now
assert not early.alive
```

## Common Patterns

### Back-References Without a Cycle

A child that holds its parent strongly makes a cycle, which only the cycle collector can free.
A weak back-reference leaves no cycle, so the parent is freed as soon as the last outside
reference to it goes.

```python
import gc
import weakref

class Parent:
    def __init__(self):
        self.children = []

    def add(self, child):
        self.children.append(child)
        child.parent = weakref.ref(self)  # O(1) - no strong reference back

class Child:
    parent = None

parent = Parent()
child = Child()
parent.add(child)
assert child.parent() is parent  # O(1)

del parent
gc.collect()
assert child.parent() is None
```

## Performance Best Practices

✅ **Do**:

- Use `WeakValueDictionary` for a cache whose values should not outlive their other users; a hit is O(1)
- Use `WeakKeyDictionary` to attach data to objects you do not own, with values that do not refer back to their keys
- Use `WeakMethod` for a bound-method callback; a plain `ref` to a bound method dies with the temporary bound method
- Prefer `finalize` to a callback you manage by hand; it runs once, and runs even if you keep no reference to it
- On 3.14+, expect iterating a large weak container to copy it first

❌ **Avoid**:

- Calling `getweakrefcount()` in a loop over a heavily referenced object - each call is O(w)
- Values in a `WeakKeyDictionary` that refer to their key, or a finalizer function or arguments that refer to its object - that object never dies
- Relying on an object dying the moment its name is deleted; one in a reference cycle waits for the collector

## Version Notes

- **Python 3.14+**: Iterating a `WeakKeyDictionary`, `WeakValueDictionary` or `WeakSet` copies the underlying container first, O(n) memory, and adding or removing an entry during iteration no longer raises `RuntimeError`
- **All Python 3**: When a referent dies depends on the interpreter; CPython frees one outside a reference cycle at once, and one inside a cycle when the cycle collector runs

## Related Modules

- **[gc](gc.md)** - The cycle collector that frees objects in reference cycles, and with them their weak references
- **[functools](functools.md)** - `singledispatch` keeps its dispatch cache in a `WeakKeyDictionary`
- **[atexit](atexit.md)** - The exit hooks `finalize` registers with
- **[copy](copy.md)** - `copy.deepcopy()` of the weak dictionaries copies only the strongly held side
