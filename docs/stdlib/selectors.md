# selectors Module Complexity

The `selectors` module wraps the `select` module's primitives - `select()`, `poll()`, `epoll`,
`/dev/poll` and `kqueue` - behind one interface: register file objects with the events to watch,
then ask which of them are ready. Registration is a dict entry keyed by file descriptor, plus at
most a couple of system calls; the cost that differs between the implementations is `select()`
itself.

`n` is the file objects registered with a selector, and `k` is the `(key, events)` pairs one
`select()` call returns - one per ready file object, or two for a file kqueue reports ready for
reading and writing separately. The bounds price the work of one call, not the time it spends waiting for
a descriptor to become ready, and treat a system call that adds, changes or removes one
descriptor as O(1). A file object is an integer descriptor or anything with a `fileno()` method,
which every method that takes one calls to find its registration.

## Complexity Reference

### Selector classes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `selectors.DefaultSelector()` | O(1) | O(1) | An alias chosen at import: the first of kqueue, epoll, `/dev/poll`, poll and select that works; `EpollSelector` on Linux. Where it is `DevpollSelector`, it costs what that costs |
| `selectors.SelectSelector()` | O(1) | O(1) | Available everywhere; on Unix, descriptors must be below `FD_SETSIZE` (usually 1024) or `select()` raises `ValueError` |
| `selectors.PollSelector()` | O(1) | O(1) | Unix |
| `selectors.EpollSelector()` | O(1) | O(1) | Linux; opens an epoll descriptor |
| `selectors.KqueueSelector()` | O(1) | O(1) | BSD and macOS; opens a kqueue descriptor |
| `selectors.DevpollSelector()` | O(1) | O(L) | Solaris; L = the process's open-file limit, one slot per descriptor reserved up front |
| `EpollSelector.fileno()`, `KqueueSelector.fileno()`, `DevpollSelector.fileno()` | O(1) | O(1) | The kernel object's own descriptor |

### BaseSelector

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `selectors.BaseSelector` | O(1) | O(1) | Abstract; a subclass supplies `register`, `unregister`, `select` and `get_map`, and inherits `modify` as `unregister` plus `register` |
| `BaseSelector.register(fileobj, events, data=None)` | O(1) | O(1) | Returns the new `SelectorKey`; `KeyError` if the descriptor is already registered, `ValueError` if `events` is empty or has unknown bits |
| `BaseSelector.unregister(fileobj)` | O(1) | O(1) | O(n) once `fileobj` is closed: when `fileno()` fails, every registration is scanned for the object |
| `BaseSelector.modify(fileobj, events, data=None)` | O(1) | O(1) | Returns the updated `SelectorKey`; changing only `data` makes no system call |
| `BaseSelector.select(timeout=None)` | O(n) or O(k) | O(k) to O(n) | Returns k `(key, events)` pairs; the cost is the implementation's, below. `timeout <= 0` polls and `None` blocks |
| `BaseSelector.get_key(fileobj)` | O(1) | O(1) | `KeyError` if not registered, `RuntimeError` once the selector is closed |
| `BaseSelector.get_map()` | O(1) | O(1) | The same read-only view on every call, not a copy; `None` once closed |
| `len(mapping)`, `mapping[fileobj]`, `fileobj in mapping` | O(1) | O(1) | On the view `get_map()` returns |
| Iterating the view | O(n) | O(1) | Yields file descriptors, not file objects; `.values()` yields the keys |
| `BaseSelector.close()`, leaving a `with` block | O(n) | O(1) | Drops every registration and closes the kernel object, if there is one; the registered files stay open |

### select() by implementation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SelectSelector.select(timeout=None)` | O(n) | O(n) | Every registered descriptor is copied into the `select()` call and checked on return |
| `PollSelector.select(timeout=None)` | O(n) | O(k) | The kernel walks the whole n-entry array the selector keeps between calls; the first call after registrations change rebuilds it, resizing it to n |
| `EpollSelector.select(timeout=None)` | O(k) | O(n) | The kernel hands back only ready descriptors, but each call allocates a result buffer sized for all n |
| `KqueueSelector.select(timeout=None)` | O(k) | O(n) | As epoll |
| `DevpollSelector.select(timeout=None)` | O(k) | O(k) | Reuses the array allocated at construction |

### SelectorKey and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `selectors.SelectorKey` | O(1) | O(1) | A named tuple: `modify` replaces a registration's key rather than changing it in place |
| `SelectorKey.fileobj`, `SelectorKey.fd`, `SelectorKey.events`, `SelectorKey.data` | O(1) | O(1) | What was registered, its descriptor, the event mask, and the attached object |
| `selectors.EVENT_READ`, `selectors.EVENT_WRITE` | O(1) | O(1) | Bit flags, combined with bitwise or to watch both |

## Choosing a Selector

`DefaultSelector` is not a class of its own but whichever implementation the platform supports
best, and all of them share the `BaseSelector` interface. Use it as a context manager so the
kernel object is released.

```python
import selectors

assert selectors.DefaultSelector in (
    selectors.SelectSelector,
    getattr(selectors, 'PollSelector', None),
    getattr(selectors, 'EpollSelector', None),
    getattr(selectors, 'DevpollSelector', None),
    getattr(selectors, 'KqueueSelector', None),
)

with selectors.DefaultSelector() as sel:  # O(1)
    assert isinstance(sel, selectors.BaseSelector)
    assert sel.get_map() is not None
assert sel.get_map() is None  # O(n) close on exit
```

## Registering File Objects

`register()` stores a `SelectorKey` under the file's descriptor and returns it. A descriptor can
be registered once; to watch different events on it, `modify()` the registration.

```python
import selectors
import socket

left, right = socket.socketpair()

with selectors.DefaultSelector() as sel:
    key = sel.register(left, selectors.EVENT_READ, data='left')  # O(1)
    assert key.fileobj is left and key.fd == left.fileno()
    assert sel.get_key(left) is key  # O(1)

    try:
        sel.register(left, selectors.EVENT_WRITE)
    except KeyError as error:
        assert 'already registered' in str(error)
    else:
        raise AssertionError('a descriptor was registered twice')

    try:
        sel.register(right, 0)
    except ValueError as error:
        assert 'Invalid events' in str(error)
    else:
        raise AssertionError('an empty event mask was accepted')

    both = selectors.EVENT_READ | selectors.EVENT_WRITE
    changed = sel.modify(left, both, data='left')  # O(1)
    assert changed.events == both and key.events == selectors.EVENT_READ
    renamed = sel.modify(left, both, data='renamed')  # O(1) - no system call
    assert sel.get_key(left) is renamed

    assert sel.unregister(left) is renamed  # O(1)

left.close()
right.close()
```

## What select() Returns

`select()` returns a list of `(key, events)` pairs for the ready file objects, where `events` is
the ready events masked by what was registered. Iterating the result costs O(k) whatever the
implementation. kqueue reports reading and writing as separate pairs, so a file watched for both
can appear twice.

```python
import selectors
import socket

left, right = socket.socketpair()

with selectors.DefaultSelector() as sel:
    sel.register(left, selectors.EVENT_READ, data='reader')

    assert sel.select(timeout=0) == []  # nothing to read yet

    right.send(b'ping')
    ready = sel.select(timeout=0)  # O(k) for epoll and kqueue, O(n) for poll and select
    assert len(ready) == 1
    key, events = ready[0]
    assert key.data == 'reader' and events == selectors.EVENT_READ
    assert key.fileobj.recv(4) == b'ping'

left.close()
right.close()
```

### How select() Scales

`select()` and `poll()` hand the kernel every registered descriptor on every call and check each
on return, so a call costs O(n) however few are ready. epoll, kqueue and `/dev/poll` keep the
interest set in the kernel and return only the ready descriptors, so a call costs O(k). For many
mostly idle connections that is the difference that matters, and it is why `DefaultSelector`
prefers them.

```python
import os
import selectors

pipes = [os.pipe() for _ in range(200)]
os.write(pipes[-1][1], b'x')  # one of 200 is ready

candidates = [selectors.SelectSelector]
for name in ('PollSelector', 'EpollSelector', 'KqueueSelector', 'DevpollSelector'):
    if hasattr(selectors, name):
        candidates.append(getattr(selectors, name))

for cls in candidates:
    with cls() as sel:
        for r, _ in pipes:
            sel.register(r, selectors.EVENT_READ)  # O(1) each
        ready = sel.select(timeout=0)  # O(n) for select/poll, O(k) for the rest
        assert [key.fd for key, _ in ready] == [pipes[-1][0]]

for r, w in pipes:
    os.close(r)
    os.close(w)
```

The kernel-side selectors are not free of n: epoll and kqueue allocate a result buffer sized for
every registration on each call, so their `select()` is O(k) in time and O(n) in memory.

## Unregistering Before Closing

Registrations are found by descriptor. Once a file is closed, its `fileno()` fails, and
`unregister()`, `modify()` and `get_key()` fall back to scanning every registration for the object
itself - O(n) per call. Unregister first.

```python
import selectors
import socket

with selectors.DefaultSelector() as sel:
    left, right = socket.socketpair()
    sel.register(left, selectors.EVENT_READ)

    sel.unregister(left)  # O(1) - fileno() still works
    left.close()

    sel.register(right, selectors.EVENT_READ)
    right.close()
    assert right.fileno() == -1
    sel.unregister(right)  # O(n) - found by scanning every registration
    assert len(sel.get_map()) == 0
```

## The Registration Map

`get_map()` returns a live, read-only view of the registrations, not a snapshot, so holding it
costs nothing and it always reflects the current state. Lookups take a file object; iteration
yields descriptors.

```python
import selectors
import socket

left, right = socket.socketpair()

with selectors.DefaultSelector() as sel:
    mapping = sel.get_map()  # O(1)
    assert sel.get_map() is mapping

    sel.register(left, selectors.EVENT_READ, data='left')
    sel.register(right, selectors.EVENT_WRITE, data='right')
    assert len(mapping) == 2  # O(1) - the view sees the new entries
    assert mapping[left].data == 'left' and right in mapping  # O(1)
    assert set(mapping) == {left.fileno(), right.fileno()}  # O(n)
    assert {key.data for key in mapping.values()} == {'left', 'right'}  # O(n)

sel.close()
assert sel.get_map() is None
try:
    sel.get_key(left)
except RuntimeError as error:
    assert 'closed' in str(error)
else:
    raise AssertionError('a closed selector answered')

left.close()
right.close()
```

## Common Patterns

### Dispatching on Attached Data

Attaching a callback as `data` means each ready event carries its own handler, so the loop does
O(k) work on top of whatever `select()` costs.

```python
import selectors
import socket

received = []

def on_readable(conn):
    received.append(conn.recv(1024))

pairs = [socket.socketpair() for _ in range(3)]

with selectors.DefaultSelector() as sel:
    for left, _ in pairs:
        left.setblocking(False)
        sel.register(left, selectors.EVENT_READ, data=on_readable)  # O(1)

    pairs[0][1].send(b'a')
    pairs[2][1].send(b'c')

    for key, events in sel.select(timeout=0):  # k = 2 ready
        key.data(key.fileobj)  # O(1) dispatch per ready file

    for left, right in pairs:
        sel.unregister(left)  # O(1) - before closing
        left.close()
        right.close()

assert sorted(received) == [b'a', b'c']
```

## Performance Best Practices

✅ **Do**:

- Use `DefaultSelector`; on Linux, BSD and macOS it is the O(k) implementation
- `unregister()` a file before closing it, so the lookup stays O(1)
- Keep per-connection state in `data`, so a ready event needs no second lookup
- Close the selector, or use it in a `with` block, to release the kernel object

❌ **Avoid**:

- `SelectSelector` or `PollSelector` for many mostly idle connections - every call is O(n)
- `SelectSelector` on Unix for descriptors at or above `FD_SETSIZE`; `select()` raises `ValueError`

## Version Notes

- **All Python 3**: On Windows only sockets can be watched, because `select()` there accepts
  nothing else

## Related Modules

- **[select](select.md)** - the primitives each selector wraps
- **[asyncio](asyncio.md)** - an event loop built on a selector
- **[socket](socket.md)** - the file objects most often registered
- **[socketserver](socketserver.md)** - servers that wait on a selector between requests
