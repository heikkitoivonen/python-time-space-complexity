# asynchat Module Complexity

The `asynchat` module frames command/response protocols over an `asyncore` channel. An
`async_chat` subclass reads from its socket, splits the input at a terminator and hands you the
pieces; on the way out it queues data and producers and sends them a chunk at a time as the
socket becomes writable. It keeps no whole message: what a message costs to hold is decided by
your `collect_incoming_data()`.

!!! warning "Removed in Python 3.12"
    Deprecated since Python 3.6 and removed in Python 3.12 by PEP 594. The examples that
    import it need Python 3.10 or 3.11; new code should use `asyncio` streams.

`n` is the bytes passed to one `push()` or still held by a `simple_producer`, `r` is the bytes
one `recv()` returns (at most `ac_in_buffer_size`), `m` is the terminators matched within those
bytes, `t` is the length of a bytes terminator, `b` is `ac_out_buffer_size`, `s` is a
`simple_producer`'s `buffer_size`, and `q` is the entries in the producer queue. The bounds count
bytes scanned and copied and exclude the cost of your own `collect_incoming_data()`,
`found_terminator()` and producer `more()` methods. A send step is priced for chunks of at most b
bytes, which is what `push()` queues; a producer chunk longer than that costs its own length.

## Complexity Reference

### async_chat

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asynchat.async_chat(sock=None, map=None)` | O(1) | O(1) | Given a socket, registers the channel in `map`, or in asyncore's global map; subclass it and override the two callbacks below |
| `async_chat.set_terminator(term)` | O(1) | O(1) | `term` is a bytes delimiter, an int byte count, or `None` to collect everything; a negative count raises `ValueError` |
| `async_chat.get_terminator()` | O(1) | O(1) | An int terminator counts down as bytes arrive and is left at 0 once it fires, which collects everything, like `None`, until you set another |
| `async_chat.collect_incoming_data(data)` | O(1) | O(1) | Must be overridden; the default raises `NotImplementedError`. Called with each piece of input as it arrives, so one message can arrive in several calls |
| `async_chat.found_terminator()` | O(1) | O(1) | Must be overridden; the default raises `NotImplementedError`. Called once per terminator matched, after the input before it has been collected |
| `async_chat.handle_read()` | O(r·(m + 1) + t²) | O(r + t) | Called by the loop for one `recv()`. Each terminator matched copies the rest of the input, so many small messages in one read cost r·m; between reads it keeps at most a partial terminator |
| `async_chat.push(data)` | O(n) | O(n) | `bytes` longer than b are copied into b-byte chunks up front, and data of at most b bytes is queued as is; sends at most one chunk now. `str` raises `TypeError` |
| `async_chat.push_with_producer(producer)` | O(b) | O(b) | Queues the producer and runs one send step; `more()` is called only once the producer reaches the head of the queue, and again only after its last chunk has gone |
| `async_chat.initiate_send()`, `async_chat.handle_write()` | O(b) | O(b) | At most one `send()` of at most b bytes per call; a producer chunk longer than b is re-sliced after every send, costing its whole length each time |
| `async_chat.close_when_done()` | O(1) | O(1) | Queues `None`; the channel closes when the queue reaches it |
| `async_chat.discard_buffers()` | O(q) | O(1) | Drops every queued chunk and producer and any partial terminator |
| `async_chat.readable()`, `async_chat.writable()` | O(1) | O(1) | Always readable; writable while the queue is not empty or the socket is not yet connected |
| `async_chat.handle_close()` | O(1) | O(1) | Closes the socket and removes the channel from its map |
| `async_chat.ac_in_buffer_size`, `async_chat.ac_out_buffer_size` | O(1) | O(1) | Class attributes, 65536 each; override them in a subclass to change r's ceiling and b |
| `async_chat.use_encoding`, `async_chat.encoding` | O(1) | O(1) | Off by default; when set, `set_terminator()` encodes a `str` terminator with `encoding` (`'latin-1'`) in O(t), and `push()` still rejects `str` |

### simple_producer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asynchat.simple_producer(data, buffer_size=512)` | O(1) | O(1) | Holds a reference to `data` |
| `simple_producer.more()` | O(n) | O(n) | Returns the first s bytes and copies the other n − s, so draining `bytes` costs O(n²/s); a `memoryview` makes each call O(1) |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asynchat.find_prefix_at_end(haystack, needle)` | O(t²) | O(t) | t = `len(needle)`; tries each proper prefix of `needle` against the end of `haystack`, longest first, and returns the length that matched, or 0 |

## Reading Framed Input

`handle_read()` takes one `recv()` and walks it for the terminator. Input goes to
`collect_incoming_data()` as it arrives, so a message split across two reads reaches you in two
pieces, and the channel itself holds nothing but a partial terminator between reads. Each
terminator matched slices the rest of the read into a new object, which is why a read carrying
many small messages costs r·m rather than r; a smaller `ac_in_buffer_size` caps r.

```python
import asynchat
import asyncore
import socket

class LineCollector(asynchat.async_chat):
    def __init__(self, sock, map):
        super().__init__(sock, map)  # O(1)
        self.set_terminator(b"\r\n")  # O(1)
        self.pieces = []
        self.lines = []

    def collect_incoming_data(self, data):
        self.pieces.append(data)

    def found_terminator(self):
        self.lines.append(b"".join(self.pieces))
        self.pieces = []

channels = {}
ours, theirs = socket.socketpair()
chat = LineCollector(ours, channels)

theirs.sendall(b"HELLO\r\nWOR")
asyncore.loop(timeout=1, map=channels, count=1)  # one handle_read(): O(r·(m + 1) + t²)
assert chat.lines == [b"HELLO"] and chat.pieces == [b"WOR"]

theirs.sendall(b"LD\r\n")
asyncore.loop(timeout=1, map=channels, count=1)
assert chat.lines == [b"HELLO", b"WORLD"]

chat.close()
theirs.close()
```

### Byte-Count Terminators

An int terminator fires after that many bytes and is then left at 0, which collects everything
that follows. Set a new terminator in `found_terminator()`.

```python
import asynchat
import asyncore
import socket

class Records(asynchat.async_chat):
    def __init__(self, sock, map):
        super().__init__(sock, map)
        self.set_terminator(5)  # O(1) - a byte count
        self.pieces = []
        self.records = []

    def collect_incoming_data(self, data):
        self.pieces.append(data)

    def found_terminator(self):
        self.records.append(b"".join(self.pieces))
        self.pieces = []
        assert self.get_terminator() == 0  # O(1) - spent
        self.set_terminator(5)

channels = {}
ours, theirs = socket.socketpair()
chat = Records(ours, channels)

theirs.sendall(b"abcdefghij")
asyncore.loop(timeout=1, map=channels, count=1)
assert chat.records == [b"abcde", b"fghij"]

try:
    chat.set_terminator(-1)
except ValueError as error:
    assert "positive" in str(error)
else:
    raise AssertionError("a negative byte count was accepted")

chat.close()
theirs.close()
```

## Writing Output

### Pushing Data

`push()` splits `bytes` longer than `ac_out_buffer_size` into chunks once, then tries to send the
first. Each later writable event sends at most one more, so a large push is spread over several
turns of the loop.

```python
import asynchat
import asyncore
import socket

class Sender(asynchat.async_chat):
    ac_out_buffer_size = 4096

channels = {}
ours, theirs = socket.socketpair()
chat = Sender(ours, channels)

chat.push(b"x" * 10_000)  # O(n) - three chunks, the first sent now
received = len(theirs.recv(65536))
assert received <= 4096

while received < 10_000:
    asyncore.loop(timeout=1, map=channels, count=1)  # one chunk per writable event: O(b)
    received += len(theirs.recv(65536))
assert received == 10_000

try:
    chat.push("text")
except TypeError:
    pass
else:
    raise AssertionError("push() accepted a str")

chat.close()
theirs.close()
```

### Producers

A producer is any object with a `more()` method. The channel calls it only when the producer
reaches the head of the queue, one chunk at a time. `simple_producer` slices its data on every
call, so each call copies what is left; wrapping the data in a `memoryview` makes the slices free.

```python
import asynchat
import asyncore
import socket

data = b"z" * 100_000

copying = asynchat.simple_producer(data, buffer_size=512)
assert len(copying.more()) == 512  # O(n) - the other n - s bytes are copied

viewing = asynchat.simple_producer(memoryview(data), buffer_size=512)
assert bytes(viewing.more()) == b"z" * 512  # O(1) - a view, nothing copied

channels = {}
ours, theirs = socket.socketpair()
chat = asynchat.async_chat(ours, channels)
chat.push_with_producer(asynchat.simple_producer(memoryview(b"abc" * 1000)))  # O(b)
chat.close_when_done()  # O(1) - close once the queue drains

while channels:  # one chunk per writable event, then the close
    asyncore.loop(timeout=1, map=channels, count=1)
received = b"".join(iter(lambda: theirs.recv(65536), b""))
assert received == b"abc" * 1000
theirs.close()
```

## Migrating to asyncio

`asyncio` streams do the same framing. `StreamReader.readuntil()` returns a whole message with
its delimiter, so there is no pair of callbacks to write.

```python
import asyncio

async def main():
    reader = asyncio.StreamReader()
    reader.feed_data(b"HELLO\r\nWORLD\r\n")
    reader.feed_eof()
    lines = []
    while not reader.at_eof():
        lines.append(await reader.readuntil(b"\r\n"))
    return lines

assert asyncio.run(main()) == [b"HELLO\r\n", b"WORLD\r\n"]
```

## Performance Best Practices

✅ **Do**:

- Keep the pieces `collect_incoming_data()` receives and join them in `found_terminator()`; the
  channel keeps no message for you
- `push()` bytes you already hold, which chunks them once, rather than wrapping them in a
  `simple_producer`
- Wrap large data in a `memoryview` when it must go through a `simple_producer`
- Return chunks no longer than `ac_out_buffer_size` from your own producers
- Lower `ac_in_buffer_size` for protocols that send many small messages at once; it caps r in
  r·m

❌ **Avoid**:

- A `simple_producer` over a large `bytes` object - O(n²/s) to drain
- A producer whose `more()` returns more than `ac_out_buffer_size` at once - it is re-sliced
  after every send
- `asynchat` in new code - it does not exist from Python 3.12

## Version Notes

- **Python 3.6+**: Deprecated in favour of `asyncio`
- **Python 3.10+**: Importing the module emits a `DeprecationWarning`
- **Python 3.12+**: Removed by PEP 594; `import asynchat` raises `ModuleNotFoundError`

## Related Modules

- **[asyncio](asyncio.md)** - the replacement; `StreamReader.readuntil()` reads to a delimiter
- **[asyncore](asyncore.md)** - the loop and `dispatcher` base class `async_chat` builds on, removed in 3.12 too
- **[socket](socket.md)** - the `send()` and `recv()` calls each channel makes
