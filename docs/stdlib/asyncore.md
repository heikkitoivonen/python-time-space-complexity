# asyncore Module Complexity

The `asyncore` module runs an event loop over a map of channels: `dispatcher` objects, each
wrapping one non-blocking socket, whose `handle_*()` methods the loop calls when the socket is
ready. The unit of work is a pass of the loop, and passes keep no state between them: each asks
every channel whether it wants to read or write and builds the `select()` or `poll()` request from
scratch, so it costs every registered channel, idle or not.

!!! warning "Removed in Python 3.12"
    Deprecated since Python 3.6 and removed in Python 3.12 by PEP 594. The examples that
    import it need Python 3.10 or 3.11; new code should use `asyncio`.

`c` is the channels in the map a loop runs over, `r` is the bytes one `recv()` returns, `n` is the
bytes passed to one `send()`, `u` is the bytes waiting in a `dispatcher_with_send` output buffer,
and `f` is the frames in a traceback. The bounds count Python-level work and the bytes copied;
they exclude the kernel's cost for each system call and the cost of your own `handle_*()`
overrides.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncore.loop(timeout=30.0, use_poll=False, map=None, count=None)` | O(c) per pass | O(c) | Asks every channel `readable()` and `writable()` on every pass, then runs the handlers of the ready ones; stops when the map is empty, or after `count` passes if `count` is given. Without `use_poll`, a descriptor numbered 1024 or higher raises `ValueError` on Linux |
| `asyncore.close_all(map=None, ignore_all=False)` | O(c) | O(c) | Closes every channel in the map and clears it |
| `asyncore.socket_map` | O(1) | O(1) | The global map: channels registered without a `map` go into it, and `loop()` without one runs over all of them |
| `asyncore.ExitNow` | O(1) | O(1) | Raised in a handler, it propagates out of `loop()` instead of reaching the channel's `handle_error()` |

### dispatcher

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncore.dispatcher(sock=None, map=None)` | O(1) | O(1) | Given a socket, makes it non-blocking and registers the channel in `map`, or in `socket_map` |
| `dispatcher.create_socket(family=socket.AF_INET, type=socket.SOCK_STREAM)` | O(1) | O(1) | Creates a non-blocking socket and registers the channel |
| `dispatcher.connect(address)` | O(1) | O(1) | Starts a non-blocking connect; `handle_connect()` runs when it completes, at once or on a later read or write event. A host name is resolved before the call returns, blocking the loop |
| `dispatcher.bind(address)`, `dispatcher.listen(backlog)` | O(1) | O(1) | `listen()` marks the channel accepting, and an accepting channel is never polled for writing |
| `dispatcher.accept()` | O(1) | O(1) | Returns `(sock, address)`, or `None` when no connection is pending |
| `dispatcher.send(data)` | O(n) | O(1) | One `socket.send()`: returns the bytes accepted, which can be fewer than n, and 0 when the socket would block. Keeping the rest is up to you |
| `dispatcher.recv(buffer_size)` | O(r) | O(buffer_size) | One `socket.recv()`, which allocates `buffer_size` bytes before shrinking the result to r; at end of stream it calls `handle_close()` and returns `b''` |
| `dispatcher.close()` | O(1) | O(1) | Removes the channel from its map and closes the socket |
| `dispatcher.readable()`, `dispatcher.writable()` | O(1) | O(1) | Both always true: a channel that does not override `writable()` is polled for writing on every pass, so while its socket has buffer room `loop()` never waits |
| `dispatcher.handle_read()`, `dispatcher.handle_write()`, `dispatcher.handle_expt()`, `dispatcher.handle_connect()` | O(1) | O(1) | Override them; the defaults log a warning that `ignore_log_types` suppresses, so an unhandled event is dropped silently |
| `dispatcher.handle_accept()` | O(1) | O(1) | Accepts one connection and passes it to `handle_accepted()`, so a backlog of k connections takes k passes |
| `dispatcher.handle_accepted(sock, addr)` | O(1) | O(1) | Override it; the default closes the new socket |
| `dispatcher.handle_close()` | O(1) | O(1) | The default closes the channel |
| `dispatcher.handle_error()` | O(f) | O(f) | Prints a one-line summary of all f frames of the traceback and closes the channel |

### dispatcher_with_send

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncore.dispatcher_with_send(sock=None, map=None)` | O(1) | O(1) | A `dispatcher` with an output buffer |
| `dispatcher_with_send.send(data)` | O(u + n) | O(u + n) | Appends to the buffer by concatenation, copying all of it, then sends up to 65,536 bytes; many small sends to a slow peer are quadratic |
| `dispatcher_with_send.handle_write()` | O(u) | O(u) | Sends up to 65,536 bytes and copies the unsent rest, so draining u bytes is O(u²) |
| `dispatcher_with_send.writable()` | O(1) | O(1) | True while the buffer holds data or the socket is not yet connected |

### file_dispatcher and file_wrapper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncore.file_dispatcher(fd, map=None)` | O(1) | O(1) | POSIX only. Takes a descriptor or an object with `fileno()`, duplicates it in a `file_wrapper`, makes it non-blocking and registers the channel |
| `asyncore.file_wrapper(fd)` | O(1) | O(1) | POSIX only. A socket-like wrapper over `os.dup(fd)`; its `recv()` and `send()` are one `os.read()` and one `os.write()`, O(r) and O(n) |

## The Event Loop

### A Pass Visits Every Channel

Every pass calls `readable()` and `writable()` on each channel in the map and passes the result to
`select()` or `poll()`, whether or not anything happened on that socket. A loop over many mostly
idle connections pays for all of them on every pass.

```python
import asyncore
import socket

class Idle(asyncore.dispatcher):
    asked = 0

    def readable(self):
        Idle.asked += 1
        return True

    def writable(self):
        return False  # without this the channel is ready on every pass

channels = {}
pairs = [socket.socketpair() for _ in range(20)]
for ours, _ in pairs:
    Idle(ours, channels)  # O(1) - registers in channels

asyncore.loop(timeout=0, map=channels, count=3)  # O(c) per pass
assert Idle.asked == 3 * 20  # every channel asked on every pass, though none was ready

asyncore.close_all(channels)  # O(c)
assert channels == {}
for _, theirs in pairs:
    theirs.close()
```

### Readiness and the Default Predicates

`readable()` and `writable()` both return true unless you override them. A socket is almost
always writable, so a channel left with the default `writable()` makes every `select()` return at
once and the loop spins, calling `handle_write()` on each pass instead of waiting for input.

The default `select()` path cannot watch a descriptor numbered 1024 or higher on Linux: the pass
raises `ValueError`. `use_poll=True` has no such limit, and costs the same O(c) per pass.

### Reading

`recv()` makes one `socket.recv()`. At end of stream it calls `handle_close()`, which by default
closes the channel and removes it from the map, so `loop()` without a `count` returns once every
channel has been closed this way.

```python
import asyncore
import socket

class Reader(asyncore.dispatcher):
    def __init__(self, sock, map):
        super().__init__(sock, map)  # O(1)
        self.received = []

    def writable(self):
        return False

    def handle_read(self):
        data = self.recv(4096)  # O(r)
        if data:
            self.received.append(data)

channels = {}
ours, theirs = socket.socketpair()
reader = Reader(ours, channels)
theirs.sendall(b"hello")
theirs.close()

asyncore.loop(timeout=1, map=channels)  # until the map is empty
assert reader.received == [b"hello"]
assert channels == {}  # recv() saw end of stream and closed the channel
```

## Sending Data

`dispatcher.send()` is one `socket.send()` and may take only part of the data; the caller keeps
the rest. `dispatcher_with_send` keeps it for you in one `bytes` buffer, which every `send()`
copies to append to and every partial send copies to drop the sent part. That is fine for short
replies and quadratic for large or many small writes; `asynchat.async_chat.push()` chunks its data
once instead.

```python
import asyncore
import socket

data = b"x" * 10_000_000

ours, theirs = socket.socketpair()
ours.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
plain = asyncore.dispatcher(ours, {})
sent = plain.send(data)  # O(n) - one socket.send()
assert 0 < sent < len(data)  # the socket took only part of it
plain.close()
theirs.close()

channels = {}
ours, theirs = socket.socketpair()
writer = asyncore.dispatcher_with_send(ours, channels)
writer.send(b"y" * 500_000)  # O(u + n) - buffered, up to 65,536 bytes sent now
received = len(theirs.recv(1 << 20))
while writer.writable():  # O(1) - true while the buffer holds data
    asyncore.loop(timeout=1, map=channels, count=1)  # handle_write(): O(u)
    received += len(theirs.recv(1 << 20))
writer.close()
received += sum(map(len, iter(lambda: theirs.recv(1 << 20), b"")))
assert received == 500_000
theirs.close()
```

## Handling Errors

An exception raised in a handler normally reaches the channel's `handle_error()`, which by default prints
a summary of the traceback and closes the channel; the loop carries on with the other channels.
`ExitNow`, `KeyboardInterrupt` and `SystemExit` propagate out of `loop()` instead.

```python
import asyncore
import contextlib
import io
import socket

class Failing(asyncore.dispatcher):
    def writable(self):
        return False

    def handle_read(self):
        raise RuntimeError("bad input")

class Stopping(Failing):
    def handle_read(self):
        raise asyncore.ExitNow("done")

channels = {}
ours, theirs = socket.socketpair()
Failing(ours, channels)
theirs.sendall(b"x")
log = io.StringIO()
with contextlib.redirect_stdout(log):
    asyncore.loop(timeout=1, map=channels, count=1)  # handle_error(): O(f)
assert "bad input" in log.getvalue()
assert channels == {}  # the default handle_error() closed the channel
theirs.close()

ours, theirs = socket.socketpair()
Stopping(ours, channels)
theirs.sendall(b"x")
try:
    asyncore.loop(timeout=1, map=channels)
except asyncore.ExitNow as stop:
    assert str(stop) == "done"
else:
    raise AssertionError("ExitNow did not leave the loop")
assert len(channels) == 1  # the channel is still registered

asyncore.close_all(channels)
theirs.close()
```

## Migrating to asyncio

`asyncio`'s selector event loop, the default outside Windows, keeps each socket registered with
its selector between passes, and on Linux that selector is `epoll`, which reports only the ready
sockets; a pass does not visit idle connections. Streams also do the buffering and partial sends that `dispatcher_with_send` does.

```python
import asyncio
import socket

async def main():
    left, right = socket.socketpair()
    _, writer = await asyncio.open_connection(sock=left)
    reader, other = await asyncio.open_connection(sock=right)
    writer.write(b"x" * 1_000_000)  # buffered; sent as the socket allows
    writer.close()  # closes once the buffer is flushed
    data = await reader.read()  # to end of stream
    await writer.wait_closed()
    other.close()
    return len(data)

assert asyncio.run(main()) == 1_000_000
```

## Performance Best Practices

✅ **Do**:

- Override `writable()` to return true only while there is something to send or a `connect()` is
  pending; the default keeps the loop from ever waiting
- Pass each loop its own `map`, so a pass visits only that loop's channels rather than every
  channel in `socket_map`
- Pass `use_poll=True` when the process may hold descriptors numbered 1024 or higher
- Keep pending output as a list of chunks, or use `asynchat`'s `push()`, rather than
  `dispatcher_with_send` for large replies
- Raise `ExitNow` from a handler to leave the loop

❌ **Avoid**:

- Thousands of mostly idle channels in one loop - every pass costs all of them
- `dispatcher_with_send` for large or many small writes - O(u²) to drain
- Host names in `connect()` - resolution blocks every channel in the loop
- `asyncore` in new code - it does not exist from Python 3.12

## Version Notes

- **Python 3.6+**: Deprecated in favour of `asyncio`
- **Python 3.10+**: Importing the module emits a `DeprecationWarning`
- **Python 3.12+**: Removed by PEP 594; `import asyncore` raises `ModuleNotFoundError`

## Related Modules

- **[asyncio](asyncio.md)** - the replacement; its selector loop keeps sockets registered between passes
- **[asynchat](asynchat.md)** - terminator framing and chunked output on top of `dispatcher`, removed in 3.12 too
- **[selectors](selectors.md)** - persistent registration over `epoll`, `kqueue`, `poll` or `select`
- **[select](select.md)** - the `select()` and `poll()` calls each pass makes
- **[socket](socket.md)** - the `send()` and `recv()` calls each channel makes
