# socketserver Module Complexity

The `socketserver` module is the accept-and-dispatch loop behind `http.server`, `xmlrpc.server`
and `wsgiref.simple_server`. A server waits on one listening socket and, for each request, builds
an instance of your handler class; everything else is the choice of where that handler runs - in
the serving thread, in a new thread, or in a forked child. The module is pure Python, and a stream
server reads nothing from a connection itself: every byte of the request is left for the handler.

A request is the unit throughout. `t` is the handler threads a `ThreadingMixIn` server is
tracking, `c` is the child processes a `ForkingMixIn` server is tracking, `b` is the bytes of one
received datagram, at most `max_packet_size`, and `r` is the bytes a datagram handler writes as
its reply. `n` is the bytes one read or write on a handler's files moves, and `f` is the frames in
a printed traceback. Each system call - `bind`, `listen`,
`accept`, `select`, `fork`, starting a thread - is priced O(1): the bounds count calls, not kernel
time or network latency. The handler's own work is outside every bound, which is why the dispatch
rows say "plus the handler".

## Complexity Reference

### BaseServer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socketserver.BaseServer(server_address, RequestHandlerClass)` | O(1) | O(1) | Stores both; makes no socket. The base every server class below extends |
| `BaseServer.serve_forever(poll_interval=0.5)` | O(1) per wakeup, plus each request | O(1) | Wakes when a request is ready or `poll_interval` seconds pass, handles at most one request, then calls `service_actions()` unless shutting down; ignores `timeout` |
| `BaseServer.shutdown()` | O(1) | O(1) | Blocks until `serve_forever()` returns: up to one `poll_interval`, plus whatever request the loop is handling. Called from the thread running the loop, it never returns |
| `BaseServer.handle_request()` | O(1), plus the request | O(1) | Serves at most one request, waiting for at most `timeout` or the socket's own timeout, whichever is smaller; on expiry calls `handle_timeout()` instead |
| `BaseServer.service_actions()` | O(1) | O(1) | A no-op hook, called by `serve_forever()` after each wakeup |
| `BaseServer.fileno()` | O(1) | O(1) | The listening socket's descriptor, so a server can be passed to a selector |
| `BaseServer.get_request()` | O(1) | O(1) | One `accept()` on a stream server; the datagram version is under Server classes |
| `BaseServer.verify_request(request, client_address)` | O(1) | O(1) | Returns `True`; override it to refuse a request before any handler is built |
| `BaseServer.process_request(request, client_address)` | O(1), plus the handler | O(1) | `finish_request()` then `shutdown_request()`, in the serving thread; the mix-ins replace it |
| `BaseServer.finish_request(request, client_address)` | O(1), plus the handler | O(1) | Instantiates `RequestHandlerClass`, which runs the handler |
| `BaseServer.shutdown_request(request)`, `BaseServer.close_request(request)` | O(1) | O(1) | Hooks for ending a request: `TCPServer.shutdown_request()` shuts down the write side, then calls `close_request()`, which closes; a datagram server does neither |
| `BaseServer.handle_error(request, client_address)` | O(f) | O(f) | Prints the traceback to stderr; the server goes on to the next request |
| `BaseServer.handle_timeout()` | O(1) | O(1) | A no-op hook for `handle_request()` expiring |
| `BaseServer.server_bind()`, `BaseServer.server_activate()` | O(1) | O(1) | Hooks the `TCPServer` constructor calls: `bind()`, then `listen(request_queue_size)` |
| `BaseServer.server_close()` | O(1) | O(1) | A hook, also called on leaving a `with` block; `TCPServer` closes the listening socket, and the mix-ins add waiting, below |
| `BaseServer.address_family`, `BaseServer.socket_type`, `BaseServer.allow_reuse_address`, `BaseServer.request_queue_size`, `BaseServer.timeout` | O(1) | O(1) | Class attributes to override on a subclass; all but `timeout` are read during construction. `request_queue_size` is 5, the `listen()` backlog |
| `BaseServer.server_address`, `BaseServer.socket`, `BaseServer.RequestHandlerClass` | O(1) | O(1) | After binding, `server_address` is the address actually bound, so port 0 reads back as the port chosen |

### Server classes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socketserver.TCPServer(server_address, RequestHandlerClass, bind_and_activate=True)` | O(1) | O(1) | Creates, binds and listens; with `bind_and_activate=False` only the socket is created |
| `socketserver.UDPServer(server_address, RequestHandlerClass, bind_and_activate=True)` | O(1) | O(1) | Binds; a datagram socket does not listen |
| `socketserver.UnixStreamServer(...)`, `socketserver.UnixDatagramServer(...)` | O(1) | O(1) | The same over `AF_UNIX`, where available; `server_close()` leaves the socket file in place |
| `TCPServer.get_request()` | O(1) | O(1) | One `accept()` |
| `UDPServer.get_request()` | O(b) | O(`max_packet_size`) | One `recvfrom(max_packet_size)`, whose buffer is the full limit before it shrinks to the datagram; the request is the datagram and the socket |
| `UDPServer.max_packet_size` | O(1) | O(1) | 8192; on POSIX the rest of a longer datagram is discarded without an error |
| `TCPServer.allow_reuse_port` | O(1) | O(1) | Python 3.11+; an IP server sets `SO_REUSEPORT` on binding |

### ThreadingMixIn and ForkingMixIn

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ThreadingMixIn.process_request(request, client_address)` | O(t) | O(t) | Starts one thread per request, first dropping finished threads from the t it tracks |
| `ThreadingMixIn.process_request_thread(request, client_address)` | O(1), plus the handler | O(1) | The thread's body: `finish_request()`, `handle_error()` on an exception, then `shutdown_request()` |
| `ThreadingMixIn.server_close()` | O(t), plus waiting | O(t) | Closes the socket, then joins every tracked thread, so it lasts as long as the slowest handler still running |
| `ThreadingMixIn.daemon_threads` | O(1) | O(1) | `False`; `True` leaves threads untracked, so `process_request()` is O(1) and `server_close()` does not wait |
| `ThreadingMixIn.block_on_close`, `ForkingMixIn.block_on_close` | O(1) | O(1) | `True`; `False` stops `server_close()` joining threads, or waiting on children that have not exited |
| `ForkingMixIn.process_request(request, client_address)` | O(1) | O(1) | One `fork()`; the parent closes its copy of the request and records the pid. POSIX only |
| `ForkingMixIn.collect_children(*, blocking=False)` | O(c) | O(c) | One `waitpid()` per tracked child; at `max_children` it first blocks until one exits |
| `ForkingMixIn.service_actions()`, `ForkingMixIn.handle_timeout()` | O(c) | O(c) | Both call `collect_children()`, so every `serve_forever()` wakeup is O(c) |
| `ForkingMixIn.server_close()` | O(c), plus waiting | O(c) | Closes the socket, then `collect_children(blocking=block_on_close)` |
| `ForkingMixIn.max_children` | O(1) | O(1) | 40 |
| `ForkingMixIn.active_children` | O(1) | O(c) | The set of pids, or `None` before the first fork |
| `ForkingMixIn.timeout` | O(1) | O(1) | 300 seconds, used by `handle_request()` |

### Predefined servers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socketserver.ThreadingTCPServer`, `socketserver.ThreadingUDPServer`, `socketserver.ThreadingUnixStreamServer`, `socketserver.ThreadingUnixDatagramServer` | O(1) | O(1) | `ThreadingMixIn` over each server class; a request costs what `ThreadingMixIn.process_request()` does |
| `socketserver.ForkingTCPServer`, `socketserver.ForkingUDPServer`, `socketserver.ForkingUnixStreamServer`, `socketserver.ForkingUnixDatagramServer` | O(1) | O(1) | `ForkingMixIn` over each; POSIX only, and the two Unix ones are Python 3.12+ |

### BaseRequestHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socketserver.BaseRequestHandler(request, client_address, server)` | O(1), plus the handler | O(1) | Constructing it is handling the request: `setup()`, `handle()`, then `finish()`, which runs even if `handle()` raises |
| `BaseRequestHandler.setup()`, `BaseRequestHandler.handle()`, `BaseRequestHandler.finish()` | O(1) | O(1) | No-ops to override |
| `BaseRequestHandler.request`, `BaseRequestHandler.client_address`, `BaseRequestHandler.server` | O(1) | O(1) | Set before `setup()`; for a datagram server `request` is `(data, socket)` |

### StreamRequestHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `StreamRequestHandler.setup()` | O(1) | O(1) | Applies `timeout` and `disable_nagle_algorithm` to the connection, then opens `rfile` and `wfile` over it |
| `StreamRequestHandler.rfile` | O(n) per read | O(n) | Buffered, so small reads do not each make a system call. `readline()` without a limit holds the whole line |
| `StreamRequestHandler.wfile` | O(n) per write | O(1) | Unbuffered by default, so each `write()` is one `sendall()` call, made before `write()` returns |
| `StreamRequestHandler.rbufsize`, `StreamRequestHandler.wbufsize` | O(1) | O(1) | -1 and 0; a positive `wbufsize` batches writes into a buffer of that size, sent when it fills and at `finish()` |
| `StreamRequestHandler.timeout`, `StreamRequestHandler.disable_nagle_algorithm` | O(1) | O(1) | `None` and `False`; read once, in `setup()` |
| `StreamRequestHandler.finish()` | O(1), plus buffered writes | O(1) | Flushes what a positive `wbufsize` still holds, then closes both files |

### DatagramRequestHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `DatagramRequestHandler.setup()` | O(1) | O(1) | Wraps the datagram already received; no system call |
| `DatagramRequestHandler.rfile` | O(n) per read | O(n) | A `BytesIO` over the whole datagram |
| `DatagramRequestHandler.wfile` | O(n) per write | O(r) | A `BytesIO` holding the whole reply until `finish()` |
| `DatagramRequestHandler.finish()` | O(r) | O(r) | Sends everything written as one datagram |

## Serving Requests

### One Request at a Time

The plain server classes run the handler in the thread that called `handle_request()` or
`serve_forever()`, so a slow handler delays every client behind it. `handle_request()` serves at
most one request, which makes it the easiest way to drive a server without threads.

```python
import socket
import socketserver

class Echo(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(1024)  # O(n), capped at 1024 bytes
        self.wfile.write(b"echo: " + line)  # O(n), sent at once

with socketserver.TCPServer(("127.0.0.1", 0), Echo) as server:  # O(1) - bind and listen
    host, port = server.server_address  # port 0 reads back as the port chosen
    assert port != 0

    client = socket.create_connection((host, port))  # waits in the listen backlog
    client.sendall(b"hello\n")
    server.handle_request()  # O(1) plus the handler, in this thread
    with client, client.makefile("rb") as reply:
        assert reply.read() == b"echo: hello\n"  # the server closed its side
```

### Serving Until Shutdown

`serve_forever()` wakes when a request is ready or every `poll_interval` seconds, whichever comes
first, and checks for a shutdown request only then. `shutdown()` sets that flag and waits for the
loop to notice, so it can block for up to one `poll_interval` plus any request in progress, and it
must come from another thread: called by the loop's own thread, it waits for itself.

```python
import socket
import socketserver
import threading

class Upper(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(self.rfile.readline(1024).upper())

server = socketserver.TCPServer(("127.0.0.1", 0), Upper)
loop = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
loop.start()

with socket.create_connection(server.server_address) as client:
    client.sendall(b"abc\n")
    with client.makefile("rb") as reply:
        assert reply.readline() == b"ABC\n"

server.shutdown()  # O(1), waits for the loop to exit
loop.join()
server.server_close()
assert not loop.is_alive()
```

### Timeouts

`handle_request()` honours `timeout`; `serve_forever()` does not. When no request arrives in
time, `handle_request()` calls `handle_timeout()` and returns.

```python
import socketserver

class Quiet(socketserver.TCPServer):
    timeout = 0.05
    timed_out = 0

    def handle_timeout(self):
        self.timed_out += 1

with Quiet(("127.0.0.1", 0), socketserver.BaseRequestHandler) as server:
    server.handle_request()  # no client: returns after 0.05 s
    assert server.timed_out == 1
```

### Refusing and Failing Requests

`verify_request()` runs before the handler is built, so refusing there costs one accept and one
close. An `Exception` raised in a handler reaches `handle_error()`, which prints the traceback and
lets the server continue.

```python
import contextlib
import io
import socket
import socketserver

handled = []

class Record(socketserver.BaseRequestHandler):
    def handle(self):
        handled.append(self.client_address)
        raise ValueError("handler failed")

class Picky(socketserver.TCPServer):
    allowed = True

    def verify_request(self, request, client_address):
        return self.allowed

with Picky(("127.0.0.1", 0), Record) as server:
    server.allowed = False
    refused = socket.create_connection(server.server_address)
    server.handle_request()  # O(1) - the handler is never built
    assert handled == []
    assert refused.recv(1) == b""  # the connection was closed
    refused.close()

    server.allowed = True
    client = socket.create_connection(server.server_address)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        server.handle_request()  # the handler raises; handle_error prints it
    assert len(handled) == 1
    assert "ValueError: handler failed" in stderr.getvalue()
    client.close()
```

## Concurrency

### Threads

`ThreadingMixIn` starts one thread per request. By default it also keeps a reference to each
non-daemon thread so `server_close()` can join them, and each new request first scans that list
for threads that have finished: a request costs O(t) where t is the handler threads still
tracked. `daemon_threads = True` stops the tracking, and with it the wait on close.

```python
import socketserver
import threading

release = threading.Event()
started = []

class Wait(socketserver.BaseRequestHandler):
    def handle(self):
        started.append(self.client_address)
        release.wait()

class Request:
    """Stands in for an accepted connection."""
    def shutdown(self, how):
        pass
    def close(self):
        pass

server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Wait, bind_and_activate=False)
for n in range(3):
    server.process_request(Request(), ("client", n))  # O(t) - scans the tracked threads

closer = threading.Thread(target=server.server_close)  # O(t), plus waiting
closer.start()
closer.join(0.1)
assert closer.is_alive()  # still waiting for the handlers
release.set()
closer.join()
assert len(started) == 3
```

### Processes

`ForkingMixIn` forks a child per request and remembers its pid. Every `serve_forever()` wakeup
then calls `waitpid()` once per tracked child to reap the ones that have exited, so the loop
costs O(c) even when idle; at `max_children` it blocks until one exits.

```python
import os
import socket
import socketserver

if hasattr(os, "fork"):
    class Pid(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(str(os.getpid()).encode())

    with socketserver.ForkingTCPServer(("127.0.0.1", 0), Pid) as server:
        client = socket.create_connection(server.server_address)
        server.handle_request()  # O(1) - one fork; the child runs the handler
        assert len(server.active_children) == 1  # O(c) pids tracked
        with client, client.makefile("rb") as reply:
            assert int(reply.read()) != os.getpid()  # handled in the child
    # Leaving the block waited for the child: block_on_close is True
    assert not server.active_children
```

## Request Handlers

### Stream Handlers

`rfile` is buffered and `wfile` is not: each `write()` is one `sendall()`, so a handler that
writes many small pieces sends each one separately. Set `wbufsize` to batch them; the
buffer is flushed when the handler finishes. `rfile.readline()` holds a whole line, so pass a
limit when the client is not trusted.

```python
import socket
import socketserver

class Pieces(socketserver.StreamRequestHandler):
    wbufsize = 65536  # buffer writes; finish() flushes them

    def handle(self):
        request = self.rfile.readline(64)  # O(n), n <= 64
        assert request == b"x" * 64  # the rest of the line is left unread
        for n in range(1000):
            self.wfile.write(b"%d\n" % n)  # O(n) each, no system call

with socketserver.TCPServer(("127.0.0.1", 0), Pieces) as server:
    client = socket.create_connection(server.server_address)
    client.sendall(b"x" * 100 + b"\n")
    server.handle_request()
    with client, client.makefile("rb") as reply:
        assert reply.read().splitlines()[-1] == b"999"
```

### Datagram Handlers

A datagram server receives at most `max_packet_size` bytes per request; on POSIX the rest is
dropped without an error. `DatagramRequestHandler` holds the whole datagram in `rfile` and
collects the reply in `wfile`, sending it as a single datagram when the handler finishes.

```python
import socket
import socketserver

class Size(socketserver.DatagramRequestHandler):
    def handle(self):
        data = self.rfile.read()  # O(b) - the whole datagram
        self.wfile.write(b"%d" % len(data))  # O(n) - held until finish()
        self.wfile.write(b" bytes")

with socketserver.UDPServer(("127.0.0.1", 0), Size) as server:
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"x" * 10000, server.server_address)
    server.handle_request()  # O(b) - one recvfrom
    reply, _ = client.recvfrom(1024)
    assert reply == b"8192 bytes"  # max_packet_size, not 10000; one datagram back
    client.close()
```

## Common Patterns

### A Threaded Server in the Background

```python
import socket
import socketserver
import threading

class Echo(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:  # O(n) per line
            self.wfile.write(line)

class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True  # untracked: process_request is O(1)

with Server(("127.0.0.1", 0), Echo) as server:
    loop = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
    loop.start()

    clients = [socket.create_connection(server.server_address) for _ in range(3)]
    for n, client in enumerate(clients):  # all three connected at once
        client.sendall(b"%d\n" % n)
    for n, client in enumerate(clients):
        with client, client.makefile("rb") as reply:
            assert reply.readline() == b"%d\n" % n

    server.shutdown()
    loop.join()
```

## Performance Best Practices

✅ **Do**:

- Use a threading or forking server when a handler can block; the plain classes serve one client
  at a time
- Set `daemon_threads = True` on a busy threading server that need not wait for handlers on
  close, so each request stops paying O(t)
- Pass a limit to `rfile.readline()` so one client cannot make the handler hold an unbounded line
- Set `wbufsize` when a handler writes many small pieces, so they are not one `sendall()` each
- Refuse unwanted clients in `verify_request()`, before a handler, thread or child is created

❌ **Avoid**:

- Calling `shutdown()` from a handler of a single-threaded server, or from the thread running
  `serve_forever()` - it waits for itself
- A long `poll_interval` when a prompt `shutdown()` matters - a longer interval can delay it
- Relying on `timeout` with `serve_forever()` - only `handle_request()` honours it
- Datagrams larger than `max_packet_size` - on POSIX the excess is dropped without an error

## Version Notes

- **Python 3.11+**: Added `allow_reuse_port`
- **Python 3.12+**: Added `ForkingUnixStreamServer` and `ForkingUnixDatagramServer`
- **All Python 3**: `ForkingMixIn` and the `Forking*` servers exist only where `os.fork` does, and
  the `Unix*` servers only where `AF_UNIX` does

## Related Modules

- **[socket](socket.md)** - the calls each server makes
- **[selectors](selectors.md)** - many clients served from one thread, without a thread each
- **[threading](threading.md)** - the threads `ThreadingMixIn` starts
- **[http](http.md)** - `http.server`, built on `TCPServer` and `ThreadingMixIn`
- **[wsgiref](wsgiref.md)** - a WSGI server built on these classes
- **[asyncio](asyncio.md)** - many connections in one thread, with coroutines for handlers
