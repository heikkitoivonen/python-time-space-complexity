# socket Module Complexity

The `socket` module is a thin layer over the operating system's sockets. Nearly every method is one
system call, so what a call costs is the bytes copied between your buffers and the kernel. Waiting
for a peer, the network, a timeout or the resolver is not work this module does.

`k` is the bytes one call actually sends or receives, `b` is the `bufsize` argument to a receive
call, `c` is its `ancbufsize` argument, `v` is the buffers in a scatter/gather list, `a` is the
ancillary data bytes sent, `f` is file descriptors passed (`maxfds` for `recv_fds()`), `r` is the
address records the resolver returns, `i` is network interfaces, and `n` is the bytes in a whole
stream or file. The bounds price the CPU work and memory on the Python side of each call. Blocking,
network latency, and the lookup cost of whatever backend answers a name query (a hosts file, DNS,
NSS) are outside every bound; O(1) means constant work, not that the call returns promptly.

## Complexity Reference

### socket

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.socket(family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None)` | O(1) | O(1) | `socket.SocketType` is its C base class |
| `socket.close()`, `socket.shutdown(how)`, `socket.detach()` | O(1) | O(1) | `detach()` hands back the descriptor without closing it |
| `socket.fileno()`, `socket.dup()`, `socket.get_inheritable()`, `socket.set_inheritable(inheritable)` | O(1) | O(1) | |
| `socket.family`, `socket.type`, `socket.proto` | O(1) | O(1) | `family` and `type` come back as enum members |
| `socket.bind(address)`, `socket.listen([backlog])` | O(1) | O(1) | |
| `socket.accept()` | O(1) | O(1) | Returns a new socket and the peer address; blocks until a connection is pending |
| `socket.connect(address)`, `socket.connect_ex(address)` | O(1) | O(1) | `connect_ex()` returns the error number of a failed connection instead of raising |
| `socket.getpeername()`, `socket.getsockname()` | O(1) | O(1) | |
| `socket.setsockopt(level, optname, value)` | O(1) | O(1) | |
| `socket.getsockopt(level, optname[, buflen])` | O(1) | O(1) | With `buflen`, returns the raw option as bytes |
| `socket.makefile(mode='r', buffering=None, *, encoding=None, errors=None, newline=None)` | O(1) | O(buffering) | Allocates its buffer when built, `io.DEFAULT_BUFFER_SIZE` by default; `buffering=0` returns the unbuffered raw stream. See [Reading Lines](#reading-lines) |
| `socket.ioctl(control, option)`, `socket.share(process_id)` | O(1) | O(1) | Windows only |

### Sending

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.send(bytes[, flags])` | O(k) | O(1) | May send less than it was given; returns the count |
| `socket.sendall(bytes[, flags])` | O(k) | O(1) | Repeats `send()` until everything is gone, without copying the data; a timeout bounds the whole call |
| `socket.sendto(bytes[, flags], address)` | O(k) | O(1) | For connectionless sockets |
| `socket.sendmsg(buffers[, ancdata[, flags[, address]]])` | O(k + v + a) | O(v + a) | Gathers the buffers in one call instead of joining them first |
| `socket.sendmsg_afalg([msg, ]*, op[, iv[, assoclen[, flags]]])` | O(k + v) | O(v) | Linux `AF_ALG` sockets only |
| `socket.sendfile(file, offset=0, count=None)` | O(n) | O(1) | Uses `os.sendfile()` where it can and falls back to reading and sending fixed-size blocks |
| `socket.send_fds(sock, buffers, fds[, flags[, address]])` | O(k + v + f) | O(v + f) | Unix only; `sendmsg()` with the descriptors as ancillary data |

### Receiving

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.recv(bufsize[, flags])` | O(k) | O(b) | Allocates `bufsize` bytes before receiving, then shrinks the result to `k` |
| `socket.recvfrom(bufsize[, flags])` | O(k) | O(b) | As `recv()`, plus the sender's address |
| `socket.recv_into(buffer[, nbytes[, flags]])` | O(k) | O(1) | Fills a buffer you supply and returns the count; no data buffer is allocated |
| `socket.recvfrom_into(buffer[, nbytes[, flags]])` | O(k) | O(1) | As `recv_into()`, plus the sender's address |
| `socket.recvmsg(bufsize[, ancbufsize[, flags]])` | O(k + c) | O(b + c) | Allocates both buffers up front, like `recv()` |
| `socket.recvmsg_into(buffers[, ancbufsize[, flags]])` | O(k + v + c) | O(v + c) | Scatters into buffers you supply |
| `socket.recv_fds(sock, bufsize, maxfds[, flags])` | O(k + f) | O(b + f) | Unix only; `recvmsg()` sized for `maxfds` descriptors |

### Timeouts

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.settimeout(value)`, `socket.gettimeout()` | O(1) | O(1) | `None` blocks, `0` never blocks, a positive number raises `TimeoutError` once it runs out |
| `socket.setblocking(flag)`, `socket.getblocking()` | O(1) | O(1) | Shorthand for timeouts of `None` and `0` |
| `socket.setdefaulttimeout(timeout)`, `socket.getdefaulttimeout()` | O(1) | O(1) | Applies to sockets created afterwards, not to ones that already exist |

### Creating connected sockets

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.create_connection(address, timeout=..., source_address=None, *, all_errors=False)` | O(r) | O(r) | Tries each resolved address in turn and returns the first that connects; every failed attempt can wait out the timeout |
| `socket.create_server(address, *, family=AF_INET, backlog=None, reuse_port=False, dualstack_ipv6=False)` | O(1) | O(1) | Creates, binds and listens |
| `socket.socketpair([family[, type[, proto]]])` | O(1) | O(1) | Two connected sockets, with no address and no network |
| `socket.fromfd(fd, family, type, proto=0)`, `socket.dup(fd)` | O(1) | O(1) | Both duplicate the descriptor |
| `socket.fromshare(data)` | O(1) | O(1) | Windows only |
| `socket.has_dualstack_ipv6()` | O(1) | O(1) | |

### Name resolution

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.getaddrinfo(host, port, family=0, type=0, proto=0, flags=0)` | O(r) | O(r) | Returns every record as one list; pass `family` and `type` to get fewer |
| `socket.gethostbyname(hostname)` | O(1) | O(1) | IPv4 only; `getaddrinfo()` handles IPv6 too |
| `socket.gethostbyname_ex(hostname)`, `socket.gethostbyaddr(ip_address)` | O(r) | O(r) | The name, its aliases and its addresses |
| `socket.getfqdn([name])` | O(r) | O(r) | One `gethostbyaddr()`, then a scan of the aliases it returned |
| `socket.getnameinfo(sockaddr, flags)` | O(1) | O(1) | |
| `socket.getservbyname(servicename[, protocolname])`, `socket.getservbyport(port[, protocolname])`, `socket.getprotobyname(protocolname)` | O(1) | O(1) | Answered from the system's services and protocols databases |
| `socket.gethostname()`, `socket.sethostname(name)` | O(1) | O(1) | `sethostname()` needs administrator rights |
| `socket.if_nameindex()` | O(i) | O(i) | i = network interfaces |
| `socket.if_nametoindex(if_name)`, `socket.if_indextoname(if_index)` | O(1) | O(1) | |

### Address conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.inet_aton(ip_string)`, `socket.inet_ntoa(packed_ip)` | O(1) | O(1) | IPv4 text to 4 packed bytes and back |
| `socket.inet_pton(address_family, ip_string)`, `socket.inet_ntop(address_family, packed_ip)` | O(1) | O(1) | IPv4 or IPv6 |
| `socket.htonl(x)`, `socket.htons(x)`, `socket.ntohl(x)`, `socket.ntohs(x)` | O(1) | O(1) | Byte-order swaps; `htons()` and `ntohs()` raise `OverflowError` outside 16 bits |
| `socket.CMSG_LEN(length)`, `socket.CMSG_SPACE(length)` | O(1) | O(1) | Sizes for `ancbufsize` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket.AF_INET`, `socket.SOCK_STREAM`, `socket.SOL_SOCKET`, `socket.MSG_PEEK` and the other constants | O(1) | O(1) | Integer flags; which ones exist depends on the platform |
| `socket.AddressFamily`, `socket.SocketKind`, `socket.MsgFlag`, `socket.AddressInfo` | O(1) | O(1) | The enums the constants belong to |
| `socket.error` | O(1) | O(1) | An alias of `OSError` |
| `socket.timeout` | O(1) | O(1) | An alias of `TimeoutError` |
| `socket.herror`, `socket.gaierror` | O(1) | O(1) | `OSError` subclasses for address lookups; `gaierror` comes from `getaddrinfo()` and `getnameinfo()` |

## Sending Data

### send vs sendall

`send()` hands the kernel as much as it will take and returns the count, which can be less than
you gave it. `sendall()` repeats that until nothing is left. It works through the buffer you
passed rather than a copy, so sending n bytes costs O(n) time and no extra memory.

```python
import socket
import threading

left, right = socket.socketpair()  # O(1)
payload = b'x' * 4_000_000

# A non-blocking send takes what fits in the kernel buffer and reports it
left.setblocking(False)
sent = left.send(payload)  # O(k), k = bytes accepted
assert 0 < sent < len(payload)
left.setblocking(True)

received = bytearray()

def drain():
    buffer = bytearray(65536)
    while len(received) < len(payload):
        count = right.recv_into(buffer)  # O(k), no new buffer
        received.extend(buffer[:count])

reader = threading.Thread(target=drain)
reader.start()
left.sendall(memoryview(payload)[sent:])  # O(n) time; the view does not copy
reader.join()

assert received == payload
left.close()
right.close()
```

### A Timeout Covers the Whole sendall

A timeout on a socket bounds each call. For `sendall()` that means the whole transfer: a slow
reader that keeps accepting data still makes `sendall()` raise once the total time runs out.

```python
import socket

left, right = socket.socketpair()
left.settimeout(0.2)  # O(1)

try:
    left.sendall(b'x' * 50_000_000)  # nobody reads, so the kernel buffer fills
except TimeoutError:
    pass
else:
    raise AssertionError('sendall finished with no reader')

left.close()
right.close()
```

### Scatter/Gather

`sendmsg()` sends several buffers as one message without joining them first.

```python
import socket

left, right = socket.socketpair()

header = b'LEN:0005\n'
body = b'hello'
left.sendmsg([header, body])  # O(k + v) - no concatenated copy

assert right.recv(1024) == b'LEN:0005\nhello'
left.close()
right.close()
```

## Receiving Data

### recv vs recv_into

`recv(bufsize)` allocates a `bufsize`-byte result before it knows how much will arrive, then
shrinks it to what did. A large `bufsize` is allocated in full on every call, however few bytes
come back. `recv_into()` fills a buffer you allocate once and returns the count.

```python
import socket

left, right = socket.socketpair()

left.sendall(b'hello')
data = right.recv(1024)  # O(k) time; allocates 1024 bytes, returns 5
assert data == b'hello'

buffer = bytearray(1024)
left.sendall(b'world')
count = right.recv_into(buffer)  # O(k), no new buffer
assert buffer[:count] == b'world'

# A peek leaves the data queued for the next read
left.sendall(b'again')
assert right.recv(5, socket.MSG_PEEK) == b'again'
assert right.recv(5) == b'again'

# An empty result means the peer has closed its end
left.close()
assert right.recv(1024) == b''
right.close()
```

### Reading Until the Peer Closes

A stream arrives in chunks of whatever size the kernel had ready. Collect them and join once:
`bytes +=` copies everything received so far on every chunk, which is O(n²) over the stream.

```python
import socket

left, right = socket.socketpair()
left.sendall(b'chunk-' * 1000)
left.close()

chunks = []
while True:
    chunk = right.recv(4096)  # O(k)
    if not chunk:
        break
    chunks.append(chunk)  # O(1) amortized
data = b''.join(chunks)  # O(n), once

assert data == b'chunk-' * 1000
right.close()
```

### Reading Lines

`makefile()` wraps the socket in a buffered file object. It receives up to
`io.DEFAULT_BUFFER_SIZE` bytes at a time and serves `readline()` from that buffer, so reading many
short lines takes far fewer system calls than there are lines.

```python
import socket

left, right = socket.socketpair()
left.sendall(b''.join(b'line %d\n' % index for index in range(100)))
left.close()

with right.makefile('rb') as stream:  # O(1)
    lines = stream.readlines()  # O(n)

assert len(lines) == 100 and lines[-1] == b'line 99\n'
right.close()
```

## Sending Files

`sendfile()` asks the kernel to copy from the file to the socket with `os.sendfile()`, so the data
never passes through Python. Where that is unavailable it reads and sends fixed-size blocks.
Either way memory stays O(1) in the file size; a file-like object without a real descriptor
takes the second route.

```python
import socket
import tempfile
import threading

left, right = socket.socketpair()
content = b'0123456789' * 100_000

received = bytearray()

def drain():
    buffer = bytearray(65536)
    while len(received) < len(content):
        count = right.recv_into(buffer)
        received.extend(buffer[:count])

with tempfile.TemporaryFile() as file:
    file.write(content)
    file.seek(0)
    reader = threading.Thread(target=drain)
    reader.start()
    sent = left.sendfile(file)  # O(n) time, O(1) memory
    reader.join()

assert sent == len(content) and received == content
left.close()
right.close()
```

## Connecting by Name

`create_connection()` resolves the name, then tries the records one after another until one
connects. A name with several unreachable addresses in front of a good one costs a failed
attempt for each, and each can wait out the timeout. With `all_errors=True` a total failure
raises an `ExceptionGroup` holding every attempt's error instead of only the last.

```python
import socket

server = socket.create_server(('127.0.0.1', 0))  # O(1) - port 0 picks a free port
port = server.getsockname()[1]

client = socket.create_connection(('127.0.0.1', port), timeout=5)  # O(r)
connection, address = server.accept()  # O(1)
assert address == client.getsockname()

client.sendall(b'ping')
assert connection.recv(4) == b'ping'

for sock in (client, connection, server):
    sock.close()
```

### Resolving Addresses

`getaddrinfo()` builds the whole list before returning. Asking for one family and socket type
returns fewer records, and `AI_NUMERICHOST` rejects anything that is not a literal address
instead of consulting the resolver.

```python
import socket

records = socket.getaddrinfo(
    '127.0.0.1', 80, socket.AF_INET, socket.SOCK_STREAM, flags=socket.AI_NUMERICHOST
)  # O(r)
assert isinstance(records, list)
family, kind, proto, canonname, sockaddr = records[0]
assert family == socket.AF_INET and kind == socket.SOCK_STREAM
assert sockaddr == ('127.0.0.1', 80)

try:
    socket.getaddrinfo('example.invalid', 80, flags=socket.AI_NUMERICHOST)
except socket.gaierror:
    pass
else:
    raise AssertionError('a host name was accepted as a numeric address')
```

## Address Conversion

The conversion functions are pure computation on one address.

```python
import socket

packed = socket.inet_aton('192.168.0.1')  # O(1)
assert packed == b'\xc0\xa8\x00\x01'
assert socket.inet_ntoa(packed) == '192.168.0.1'

packed6 = socket.inet_pton(socket.AF_INET6, '::1')  # O(1)
assert len(packed6) == 16
assert socket.inet_ntop(socket.AF_INET6, packed6) == '::1'

assert socket.ntohs(socket.htons(8080)) == 8080  # O(1)
try:
    socket.htons(70_000)
except OverflowError:
    pass
else:
    raise AssertionError('a value over 16 bits was accepted')
```

## Passing File Descriptors

On Unix, `send_fds()` and `recv_fds()` pass open descriptors across a Unix domain socket. The
receiver gets new descriptors for the same open files.

```python
import os
import socket

left, right = socket.socketpair(socket.AF_UNIX)
read_end, write_end = os.pipe()

socket.send_fds(left, [b'fd'], [read_end])  # O(k + v + f)
data, fds, flags, address = socket.recv_fds(right, 1024, maxfds=1)  # O(k + f)
assert data == b'fd' and len(fds) == 1

os.write(write_end, b'through the pipe')
assert os.read(fds[0], 1024) == b'through the pipe'

for fd in (read_end, write_end, *fds):
    os.close(fd)
left.close()
right.close()
```

## Common Patterns

### Reading an Exact Length

Length-prefixed protocols need exactly `size` bytes. Receiving into slices of one preallocated
buffer reads them in O(size) time into that one buffer, however the stream is chunked.

```python
import socket
import struct

def recv_exactly(sock, size):
    buffer = bytearray(size)  # the only data buffer
    view = memoryview(buffer)
    filled = 0
    while filled < size:
        count = sock.recv_into(view[filled:])  # O(k)
        if not count:
            raise ConnectionError('peer closed mid-message')
        filled += count
    return buffer

left, right = socket.socketpair()
message = b'x' * 10_000
left.sendall(struct.pack('!I', len(message)) + message)

(length,) = struct.unpack('!I', recv_exactly(right, 4))
assert recv_exactly(right, length) == message
left.close()
right.close()
```

## Performance Best Practices

✅ **Do**:

- Use `sendall()`, or check what `send()` returns: `send()` can stop part way
- Reuse one buffer with `recv_into()` in a receive loop; `recv(bufsize)` allocates `bufsize` bytes on every call
- Collect received chunks in a list and join once
- Use `makefile()` for line-oriented protocols rather than receiving a byte at a time
- Use `sendfile()` for files: the kernel copies them, and memory stays O(1)
- Set a timeout; without one a call can block forever

❌ **Avoid**:

- `bytes +=` in a receive loop - O(n²) over the stream
- A very large `bufsize` passed to `recv()` just in case - it is allocated each time
- Reading a whole file into memory to send it
- Name lookups on a hot path - `getaddrinfo()` can wait on the network every time; resolve once

## Version Notes

- **Python 3.11+**: `create_connection()` accepts `all_errors=True`, raising an `ExceptionGroup`
- **Python 3.10+**: `socket.timeout` is an alias of `TimeoutError`, and `htons()`/`ntohs()`
  raise `OverflowError` for values over 16 bits

## Related Modules

- **[socketserver](socketserver.md)** - server classes that handle the accept loop
- **[selectors](selectors.md)** - wait on many sockets at once instead of blocking on one
- **[select](select.md)** - the lower-level `select`, `poll` and `epoll` calls
- **[asyncio](asyncio.md)** - streams and transports for many concurrent connections
- **[ssl](ssl.md)** - wraps a socket in TLS
- **[ipaddress](ipaddress.md)** - parse and compare addresses without touching the network
