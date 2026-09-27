# select Module Complexity

The `select` module exposes the operating system's I/O multiplexing calls: `select()` and
`poll()` everywhere they exist, `epoll` on Linux, `kqueue` on BSD and macOS, and `/dev/poll` on
Solaris. Each one waits until some of a set of file descriptors are ready to read or write. What
separates them is who keeps the set: `select()` and `poll()` hand the kernel every descriptor on
every call, while `epoll`, `kqueue` and `/dev/poll` keep it in the kernel and return only what is
ready.

`n` is the descriptors one `select()` call is given, counted across its three lists, or the
registrations held by a `poll`, `epoll`, `devpoll` or `kqueue` object; a kqueue registration is
an ident and filter pair, not always a descriptor. `k` is the entries one call returns. `e` is the `maxevents` result buffer of `epoll.poll()` and `kqueue.control()`.
The bounds price the work of one call, not the time it spends waiting for a descriptor to become
ready, and treat a system call that adds, changes or removes one descriptor as O(1). A
descriptor is an integer or any object with a `fileno()` method.

## Complexity Reference

### select()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.select(rlist, wlist, xlist, timeout=None)` | O(n) | O(k) | Returns three new lists holding the objects that were passed in. Any iterable is accepted, but one that is not a list or tuple is copied first, O(n) space. On Unix every descriptor must be below `FD_SETSIZE` (1024 on Linux) or it raises `ValueError`; on Windows only sockets work |

### poll

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.poll()` | O(1) | O(1) | Unix |
| `poll.register(fd, eventmask=POLLIN \| POLLPRI \| POLLOUT)` | O(1) | O(1) | Registering an fd again replaces its mask |
| `poll.modify(fd, eventmask)` | O(1) | O(1) | `FileNotFoundError` if `fd` is not registered |
| `poll.unregister(fd)` | O(1) | O(1) | `KeyError` if `fd` is not registered |
| `poll.poll(timeout=None)` | O(n) | O(k) | The kernel checks every registration; the first call after `register`, `modify` or `unregister` also rebuilds the n-entry array it passes, O(n) space. `timeout` is in milliseconds |

### epoll

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.epoll(sizehint=-1, flags=0)` | O(1) | O(1) | Linux; opens an epoll descriptor |
| `epoll.fromfd(fd)` | O(1) | O(1) | Wraps an existing epoll descriptor |
| `epoll.register(fd, eventmask=EPOLLIN \| EPOLLPRI \| EPOLLOUT)` | O(1) | O(1) | `FileExistsError` if already registered; `PermissionError` for a regular file |
| `epoll.modify(fd, eventmask)` | O(1) | O(1) | `FileNotFoundError` if not registered |
| `epoll.unregister(fd)` | O(1) | O(1) | `FileNotFoundError` if not registered |
| `epoll.poll(timeout=None, maxevents=-1)` | O(k) | O(e) | The kernel returns only ready descriptors. `maxevents=-1` means a buffer of `FD_SETSIZE - 1` (1023 on Linux), so at most that many events per call. `timeout` is in seconds |
| `epoll.close()`, leaving a `with` block | O(n) | O(1) | Releases the epoll descriptor; the registered files stay open |
| `epoll.closed`, `epoll.fileno()` | O(1) | O(1) | Once closed, `fileno()`, `poll()` and the registration methods raise `ValueError` |

### devpoll

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.devpoll()` | O(1) | O(L) | Solaris; L = the process's open-file limit, one slot per descriptor reserved up front |
| `devpoll.register(fd, eventmask=POLLIN \| POLLPRI \| POLLOUT)`, `devpoll.modify(fd, eventmask=...)`, `devpoll.unregister(fd)` | O(1) amortized | O(1) | Buffered in the reserved array, and written to `/dev/poll` at the next `poll()` or when the array fills |
| `devpoll.poll(timeout=None)` | O(k) | O(k) | Plus writing out the changes buffered since the last call. `timeout` is in milliseconds |
| `devpoll.close()` | O(n) | O(1) | Releases the `/dev/poll` descriptor |
| `devpoll.closed`, `devpoll.fileno()` | O(1) | O(1) | |

### kqueue and kevent

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.kqueue()` | O(1) | O(1) | BSD and macOS; opens a kqueue descriptor |
| `kqueue.fromfd(fd)` | O(1) | O(1) | Wraps an existing kqueue descriptor |
| `kqueue.control(changelist, maxevents, timeout=None)` | O(c + k) | O(c + e) | c = kevents in `changelist`, applied before waiting; `maxevents=0` only applies the changes |
| `kqueue.close()` | O(n + q) | O(1) | Releases the kqueue descriptor; q = open kqueue objects in the process, Python 3.12+ |
| `kqueue.closed`, `kqueue.fileno()` | O(1) | O(1) | |
| `select.kevent(ident, filter=KQ_FILTER_READ, flags=KQ_EV_ADD, fflags=0, data=0, udata=0)` | O(1) | O(1) | One change or one returned event |
| `kevent.ident`, `kevent.filter`, `kevent.flags`, `kevent.fflags`, `kevent.data`, `kevent.udata` | O(1) | O(1) | |
| Comparing two `kevent` objects | O(1) | O(1) | By their fields |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.POLLIN`, `select.POLLOUT`, `select.POLLPRI`, `select.POLLERR`, `select.POLLHUP`, `select.POLLNVAL`, and the other `POLL*` flags | O(1) | O(1) | Event bits for `poll` and `devpoll` |
| `select.EPOLLIN`, `select.EPOLLOUT`, `select.EPOLLET`, `select.EPOLLONESHOT`, `select.EPOLLEXCLUSIVE`, and the other `EPOLL*` mask bits | O(1) | O(1) | Bits of an `epoll` event mask; `EPOLLWAKEUP` is Python 3.14+ |
| `select.EPOLL_CLOEXEC` | O(1) | O(1) | The one nonzero value `epoll(flags=...)` accepts; it changes nothing, as epoll descriptors are always close-on-exec |
| `select.KQ_FILTER_*`, `select.KQ_EV_*`, `select.KQ_NOTE_*` | O(1) | O(1) | Filter, flag and note values for `kevent` |
| `select.PIPE_BUF` | O(1) | O(1) | Bytes that can be written to a pipe without blocking once it is reported writable; at least 512 |
| `select.error` | O(1) | O(1) | An alias of `OSError` |

## Waiting with select()

`select()` walks all three lists to build the descriptor sets, and walks them again on return to
pick out the ready ones, so a call costs O(n) however few are ready. The lists it returns hold
the objects you passed, not their descriptors.

```python
import select
import socket

left, right = socket.socketpair()

assert select.select([right], [], [], 0) == ([], [], [])  # O(n) - nothing to read

left.sendall(b'ping')
readable, writable, _ = select.select([right], [right], [], 1.0)  # O(n)
assert readable == [right] and readable[0] is right
assert writable == [right]
assert right.recv(4) == b'ping'

left.close()
right.close()
```

### The FD_SETSIZE Limit

On Unix, `select()` cannot watch a descriptor numbered `FD_SETSIZE` or higher, however few it is
given. A process holding more than about a thousand open files can be handed such a descriptor,
and needs `poll()` or `epoll` to watch it. The example needs an open-file limit above 1024 to
make one.

```python
import fcntl
import os
import resource
import select

soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
if soft == resource.RLIM_INFINITY or soft > 1024:
    r, w = os.pipe()
    high = fcntl.fcntl(r, fcntl.F_DUPFD, 1024)  # the lowest free descriptor from 1024 up

    try:
        select.select([high], [], [], 0)
    except ValueError as error:
        assert 'out of range' in str(error)
    else:
        raise AssertionError('a descriptor at FD_SETSIZE was accepted')

    poller = select.poll()
    poller.register(high, select.POLLIN)  # O(1) - poll has no such limit
    assert poller.poll(0) == []

    for fd in (high, r, w):
        os.close(fd)
```

## Polling with poll()

A `poll` object keeps its registrations in a dict, so changing them is O(1). The kernel still
checks every registration on every call, and the first call after a change also rebuilds the
array it hands the kernel. The timeout is in milliseconds.

```python
import select
import socket

left, right = socket.socketpair()
poller = select.poll()

poller.register(right, select.POLLIN)  # O(1)
assert poller.poll(0) == []  # O(n) - nothing ready

left.sendall(b'hello')
events = poller.poll(1000)  # O(n); the timeout is milliseconds
assert events == [(right.fileno(), select.POLLIN)]
assert right.recv(5) == b'hello'

poller.modify(right, select.POLLIN | select.POLLOUT)  # O(1)
assert poller.poll(0) == [(right.fileno(), select.POLLOUT)]

poller.unregister(right)  # O(1)
try:
    poller.unregister(right)
except KeyError:
    pass
else:
    raise AssertionError('an unregistered descriptor was removed twice')

left.close()
right.close()
```

## Using epoll

An `epoll` object keeps the interest set in the kernel, so a call costs O(k) in the ready
descriptors, not O(n) in the registered ones. Each call allocates a result buffer of
`maxevents` entries; the default is `FD_SETSIZE - 1`, which is also the most one call returns.
The timeout is in seconds.

```python
import select
import socket

if hasattr(select, 'epoll'):
    left, right = socket.socketpair()

    with select.epoll() as ep:  # O(1); O(n) close on exit
        ep.register(right, select.EPOLLIN)  # O(1)
        try:
            ep.register(right, select.EPOLLIN)
        except FileExistsError:
            pass
        else:
            raise AssertionError('a descriptor was registered twice')

        assert ep.poll(0) == []  # O(k) - nothing ready

        left.sendall(b'event')
        assert ep.poll(1.0) == [(right.fileno(), select.EPOLLIN)]  # O(k); seconds
        assert right.recv(5) == b'event'

        ep.unregister(right)  # O(1)
    assert ep.closed

    left.close()
    right.close()
```

### Events per Call

One `poll()` returns at most `maxevents` events, and the rest wait for the next call. The
default, `FD_SETSIZE - 1`, is 1023 on Linux; pass a larger `maxevents` when more descriptors
than that can be ready together. The buffer costs O(e) either way.

```python
import os
import select

if hasattr(select, 'epoll'):
    r, w = os.pipe()
    writers = [os.dup(w) for _ in range(5)]  # five descriptors, all writable

    with select.epoll() as ep:
        for fd in writers:
            ep.register(fd, select.EPOLLOUT)  # O(1) each
        assert len(ep.poll(0, maxevents=2)) == 2  # O(k), k capped by the buffer
        assert len(ep.poll(0)) == 5  # O(k), O(e) buffer of 1023 entries

    for fd in (r, w, *writers):
        os.close(fd)
```

## Using kqueue

`kqueue.control()` applies a list of changes and then waits for events in one system call. A
change is a `kevent`; so is each event returned. `maxevents` sizes the result buffer, and `0`
applies the changes without waiting.

```python
import select
import socket

if hasattr(select, 'kqueue'):
    left, right = socket.socketpair()
    kq = select.kqueue()

    watch = select.kevent(right, filter=select.KQ_FILTER_READ, flags=select.KQ_EV_ADD)
    assert kq.control([watch], 0, 0) == []  # O(c) - register only

    left.sendall(b'kq')
    events = kq.control(None, 4, 1.0)  # O(k), O(e) buffer
    assert [(event.ident, event.filter) for event in events] == [
        (right.fileno(), select.KQ_FILTER_READ)
    ]
    assert right.recv(2) == b'kq'

    kq.close()
    assert kq.closed
    left.close()
    right.close()
```

## Performance Best Practices

✅ **Do**:

- Use `epoll` or `kqueue` when many descriptors are registered and few are ready at once: a call
  costs what is ready, not what is registered
- Batch registrations before a `poll.poll()` call; the array is rebuilt once, on the next call
- Pass `maxevents` to `epoll.poll()` when more than 1023 descriptors can be ready together

❌ **Avoid**:

- `select()` in a process that may hold more than about a thousand open files - a descriptor at
  or above `FD_SETSIZE` raises `ValueError`
- Passing `select()` a generator or set where a list will do; it is copied before the call

## Version Notes

- **All Python 3**: `epoll.poll()` with the default `maxevents=-1` returns at most
  `FD_SETSIZE - 1` events per call
- **All Python 3**: On Windows, `select()` accepts only sockets, and `poll`, `epoll`, `kqueue` and
  `devpoll` do not exist

## Related Modules

- **[selectors](selectors.md)** - one interface over all of these, with `DefaultSelector` picking
  the best one the platform has
- **[socket](socket.md)** - the sockets these calls usually wait on
- **[asyncio](asyncio.md)** - an event loop built on `selectors`
