# telnetlib Module Complexity

The `telnetlib` module is a Telnet client: a `Telnet` object wraps one TCP socket, answers or
hands off the server's option negotiation, and offers a family of `read_*()` methods that differ in
how long they wait. Received bytes go through two queues. Each `recv()` takes at most 50 bytes
into a raw queue, which is then walked a byte at a time to strip Telnet commands; the remaining
data is appended to a cooked queue, which the read methods return from.

!!! warning "Removed in Python 3.13"
    Deprecated since Python 3.11 and removed in Python 3.13 by PEP 594. The examples need Python
    3.10, 3.11 or 3.12.

`n` is the bytes one read call takes in: what it receives during the call plus what was already
queued. `m` is the bytes passed to `write()`, `p` is the patterns passed to `expect()`, and `k` is
the characters of one line typed into `interact()`. Appending a chunk to the cooked queue builds a
new `bytes` object, so a call that keeps reading until it returns copies the queue once per 50-byte
chunk. The bounds count Python-level work and the bytes copied; they exclude the kernel's cost for
each system call, name resolution and connection set-up, and the cost of a negotiation callback.
A regular expression search is priced as linear in the text it searches.

## Complexity Reference

### Telnet

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `telnetlib.Telnet(host=None, port=0[, timeout])` | O(1) | O(1) | Unconnected without `host`; with one, calls `open()` before returning. `timeout` is the socket's timeout for every blocking call |
| `Telnet.open(host, port=0[, timeout])` | O(1) | O(1) | Connects with `socket.create_connection()`; port 0 means 23 |
| `Telnet.close()` | O(1) | O(1) | Closes the socket. A `with` block calls it on exit, and so does garbage collection |
| `Telnet.write(buffer)` | O(m) | O(1), O(m) with a 255 byte | Takes bytes; a `str` raises `TypeError`. Doubles each 255 (`IAC`) byte, copying the buffer only when it holds one, and blocks until `sendall()` has sent it all |
| `Telnet.get_socket()`, `Telnet.fileno()` | O(1) | O(1) | The socket and its descriptor; `fileno()` lets a `Telnet` be registered with `selectors` |
| `Telnet.sock` | O(1) | O(1) | The socket; `None` before `open()` and after `close()` |

### Reading

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Telnet.read_until(expected, timeout=None)` | O(n²) | O(n) | The cooked queue is rebuilt for each 50-byte chunk; the search resumes near its end, so the whole queue is not searched again. On timeout or end of file it returns what has arrived, without the match: check the result's end. `EOFError` only when the connection is closed and nothing is queued |
| `Telnet.read_all()` | O(n²) | O(n) | Blocks until the peer closes; rebuilds the cooked queue for each chunk |
| `Telnet.read_some()` | O(n) | O(n) | Returns after the first chunk that yields data, so the queue never grows; `b''` at end of file |
| `Telnet.read_very_eager()` | O(n²) | O(n) | Reads until the socket has nothing ready, rebuilding the cooked queue for each chunk. `EOFError` when the connection is closed and nothing is queued |
| `Telnet.read_eager()` | O(n) | O(n) | Stops at the first chunk that yields data; `EOFError` as for `read_very_eager()` |
| `Telnet.read_lazy()` | O(n) | O(n) | Reads nothing from the socket: processes the raw queue, at most 50 bytes, answering any negotiation in it, then returns the cooked queue |
| `Telnet.read_very_lazy()` | O(1) | O(1) | Returns the cooked queue object itself and empties it; `EOFError` when the connection is closed and both queues are empty |
| `Telnet.read_sb_data()` | O(1) | O(1) | Returns the bytes collected between `SB` and `SE` and empties the store; the callback reads them when it is called with `SE` |
| `Telnet.expect(list, timeout=None)` | O(p·n²) | O(n + p) | After each chunk, the patterns are tried in list order until one matches, each searching the whole cooked queue from the start. Patterns are bytes or compiled bytes patterns; a `str` raises `TypeError`. Returns the first pattern in list order that matches, not the earliest match, or `(-1, None, data)` on timeout |

### Negotiation and debugging

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Telnet.set_option_negotiation_callback(callback)` | O(1) | O(1) | `callback(sock, command, option)` is then called for each command received, with `option` `NOOPT` for a command without one, and `telnetlib` sends no reply of its own. Without a callback every option is refused: `DO` and `DONT` get `WONT`, `WILL` and `WONT` get `DONT` |
| `Telnet.set_debuglevel(debuglevel)` | O(1) | O(1) | Above 0, each `write()` and each received chunk prints its bytes' `repr()` to standard output |
| `Telnet.msg(msg, *args)` | O(1), O(L) when debugging | O(1), O(L) when debugging | L = the formatted message's length; it is formatted with `%` and printed only when the debug level is above 0 |

### Interactive sessions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Telnet.interact()` | O(k) per line, O(n) per read | O(k + n) | On Windows it runs `mt_interact()`. Elsewhere it sends each line of standard input and prints what arrives, decoded as ASCII, so a non-ASCII byte raises `UnicodeDecodeError`, and returns at the end of standard input or when the peer closes |
| `Telnet.mt_interact()` | O(k) per line | O(k) | Prints what arrives from a second thread running `Telnet.listener()`, which keeps polling the socket with a zero timeout, never waiting for data, until the peer closes, even after `mt_interact()` returns at the end of standard input |

### Module constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `telnetlib.TELNET_PORT` | O(1) | O(1) | 23, the port `open()` uses for port 0 |
| `telnetlib.DEBUGLEVEL` | O(1) | O(1) | 0, the debug level a new instance starts with |
| `telnetlib.IAC`, `telnetlib.DO`, `telnetlib.DONT`, `telnetlib.WILL`, `telnetlib.WONT`, `telnetlib.SB`, `telnetlib.SE`, `telnetlib.NOP`, `telnetlib.DM`, `telnetlib.BRK`, `telnetlib.IP`, `telnetlib.AO`, `telnetlib.AYT`, `telnetlib.EC`, `telnetlib.EL`, `telnetlib.GA` | O(1) | O(1) | Command codes, each a one-byte `bytes`; `IAC` is `b'\xff'` |
| `telnetlib.ECHO`, `telnetlib.SGA`, `telnetlib.TTYPE`, `telnetlib.NAWS`, `telnetlib.LINEMODE`, `telnetlib.NOOPT`, ... | O(1) | O(1) | Option codes, each a one-byte `bytes`. `NOOPT` is `b'\x00'` |

## Reading Up to a Prompt

`read_until()` returns as soon as the expected bytes arrive. When the timeout runs out first it
does not raise: it returns whatever has arrived, so test the result before acting on it.

```python
import socket
import telnetlib

server = socket.create_server(("127.0.0.1", 0))
tn = telnetlib.Telnet("127.0.0.1", server.getsockname()[1], timeout=5)  # O(1)
peer, _ = server.accept()

peer.sendall(b"Welcome\r\nlogin: ")
assert tn.read_until(b"login: ", timeout=5) == b"Welcome\r\nlogin: "  # O(n²)
tn.write(b"guido\r\n")  # O(m)
assert peer.recv(100) == b"guido\r\n"

peer.sendall(b"Password")  # the prompt never completes
partial = tn.read_until(b"Password: ", timeout=0.5)
assert partial == b"Password"  # no exception: the match is simply missing
assert not partial.endswith(b"Password: ")

peer.close()
tn.close()
server.close()
```

## Reading Large Output

`read_all()`, `read_until()`, `read_very_eager()` and `expect()` keep reading until they return,
and each 50-byte chunk rebuilds the cooked queue, so n bytes cost O(n²). `read_some()` returns
after the first chunk that yields data, so the queue never grows: call it in a loop and join the
pieces for O(n) in total.

```python
import socket
import telnetlib

server = socket.create_server(("127.0.0.1", 0))
tn = telnetlib.Telnet("127.0.0.1", server.getsockname()[1], timeout=5)
peer, _ = server.accept()

payload = b"x" * 20_000
peer.sendall(payload)
peer.close()

chunks = []
while chunk := tn.read_some():  # O(1) per call: one chunk of at most 50 bytes
    chunks.append(chunk)
data = b"".join(chunks)  # O(n) in total; read_all() would be O(n²)
assert data == payload
assert max(len(chunk) for chunk in chunks) <= 50

tn.close()
server.close()
```

## Matching With expect()

`expect()` takes a list of byte patterns and, after each chunk, tries them in order until one
matches, each searching the whole cooked queue from the start, so the cost grows with both the
patterns and the square of the bytes read.
For a fixed string, `read_until()` resumes its search near the end of the queue instead of starting
again from the front. When more than one pattern matches, the first in the list wins, wherever its
match is.

```python
import socket
import telnetlib

server = socket.create_server(("127.0.0.1", 0))
tn = telnetlib.Telnet("127.0.0.1", server.getsockname()[1], timeout=5)
peer, _ = server.accept()

peer.sendall(b"error 42\r\n$ ")
index, match, text = tn.expect([rb"\$ $", rb"error (\d+)"], timeout=5)  # O(p·n²)
assert index == 0  # first in the list, though "error 42" comes earlier
assert text == b"error 42\r\n$ "

try:
    tn.expect(["login: "], timeout=0)  # a str pattern cannot search bytes
except TypeError as exc:
    assert "string pattern on a bytes-like object" in str(exc)
else:
    raise AssertionError("a str pattern was accepted")

peer.close()
tn.close()
server.close()
```

## Option Negotiation

Without a callback, `telnetlib` refuses every option the server proposes, one reply per request,
while reading. A callback takes over completely: it is called for every command, including `SB`
and `SE` around subnegotiation data, and nothing is sent unless it sends it.

```python
import socket
import telnetlib
from telnetlib import DO, DONT, ECHO, IAC, SB, SE, SGA, TTYPE, WILL, WONT

server = socket.create_server(("127.0.0.1", 0))
port = server.getsockname()[1]

tn = telnetlib.Telnet("127.0.0.1", port, timeout=5)
peer, _ = server.accept()
peer.sendall(IAC + DO + ECHO + IAC + WILL + SGA + b"ok")
assert tn.read_until(b"ok", timeout=5) == b"ok"  # the commands are not data
replies = b""
while len(replies) < 6:
    replies += peer.recv(100)
assert replies == IAC + WONT + ECHO + IAC + DONT + SGA  # both refused
peer.close()
tn.close()

seen = []

def negotiate(sock, command, option):
    if command == SE:
        seen.append(("SE", tn.read_sb_data()))  # O(1)
    else:
        seen.append((command, option))

tn = telnetlib.Telnet("127.0.0.1", port, timeout=5)
tn.set_option_negotiation_callback(negotiate)  # O(1)
peer, _ = server.accept()
peer.sendall(IAC + DO + ECHO + IAC + SB + TTYPE + b"\x01" + IAC + SE + b"ok")
assert tn.read_until(b"ok", timeout=5) == b"ok"
assert seen == [(DO, ECHO), (SB, telnetlib.NOOPT), ("SE", TTYPE + b"\x01")]
peer.settimeout(0.5)
try:
    peer.recv(100)
except TimeoutError:
    pass  # the callback sent nothing, so nothing was sent
else:
    raise AssertionError("telnetlib replied on the callback's behalf")

peer.close()
tn.close()
server.close()
```

## Bytes the Client Rewrites

The cooked queue is not a copy of what the server sent. A doubled 255 byte becomes one, Telnet
commands are removed, and NUL and `\x11` bytes are dropped, so binary data
does not survive the trip. `write()` doubles each 255 byte on the way out.

```python
import socket
import telnetlib

server = socket.create_server(("127.0.0.1", 0))
tn = telnetlib.Telnet("127.0.0.1", server.getsockname()[1], timeout=5)
peer, _ = server.accept()

peer.sendall(b"a\x00b\x11c\xff\xffd!")
assert tn.read_until(b"!", timeout=5) == b"abc\xffd!"  # NUL and \x11 are gone

tn.write(b"\xff")  # O(m)
assert peer.recv(100) == b"\xff\xff"

peer.close()
tn.close()
server.close()
```

## Performance Best Practices

✅ **Do**:

- Read large output with a `read_some()` loop and join the pieces - O(n) where `read_all()` is
  O(n²)
- Give `read_until()` and `expect()` a timeout, and check that `read_until()`'s result ends with
  the match and that `expect()`'s index is not -1
- Use `read_until()` for a fixed prompt - it does not search the whole queue again - and keep the
  `expect()` list short
- Set a negotiation callback when the server needs an option accepted
- Use `with Telnet(...) as tn:` so the socket is closed

❌ **Avoid**:

- `read_all()`, `read_until()`, `read_very_eager()` or `expect()` for large output - each 50-byte
  chunk copies everything read so far
- `str` patterns in `expect()` - they raise `TypeError`
- `mt_interact()` in a process that goes on to other work - its listener thread keeps polling
  with a zero timeout until the connection closes
- `telnetlib` in new code - it does not exist from Python 3.13

## Version Notes

- **Python 3.11+**: Deprecated; importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import telnetlib` raises `ModuleNotFoundError`

## Related Modules

- **[socket](socket.md)** - the connection `Telnet` wraps
- **[selectors](selectors.md)** - wait on several connections; a `Telnet` can be registered directly
- **[re](re.md)** - the patterns `expect()` takes, which must be bytes patterns
- **[asyncio](asyncio.md)** - streams for a client that serves many connections at once
