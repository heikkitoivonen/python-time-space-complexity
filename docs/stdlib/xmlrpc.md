# xmlrpc Module Complexity

The `xmlrpc` package makes remote procedure calls over HTTP. `xmlrpc.client` marshals Python
values into an XML document and sends each call as one POST; `xmlrpc.server` parses the request,
dispatches it to a registered function, and marshals the result back. A request is marshalled
whole before it is sent, and a call returns only once the whole response has been turned into
Python objects; the server reads the whole request body before it parses any of it.

`n` is the characters in one XML-RPC document, a request or a response body; for a call it
counts both. Marshalling and parsing are both linear in it, and it grows with the values'
elements and string characters, counting a shared reference once for every place it appears.
`b` is the bytes in a `Binary` payload, `c` is the calls queued in a `MultiCall`, `f` is the
registered functions plus the attributes `dir()` finds on a registered instance, `p` is the
dotted segments in a method name, `h` is one method's docstring characters, and `t` is the
docstring characters of every listed method plus the server documentation text. Method-name
lookups are dictionary lookups and count as O(1). No bound includes the network round trip or
the work the called method itself does.

## Complexity Reference

### ServerProxy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.client.ServerProxy(uri, transport=None, encoding=None, verbose=False, allow_none=False, use_datetime=False, use_builtin_types=False, *, headers=(), context=None)` | O(1) | O(1) | Parses the URI and builds a transport; no connection is opened until the first call |
| `proxy.name`, `proxy.name.sub` | O(1) | O(1) | Builds a callable stub for the remote name; sends nothing |
| `proxy.name(*args)` | O(n) | O(n) | One HTTP POST, plus its round trip: the whole request is marshalled, and the whole response parsed, before the call returns |
| `ServerProxy.system.listMethods()`, `ServerProxy.system.methodSignature(name)`, `ServerProxy.system.methodHelp(name)` | O(n) | O(n) | Ordinary calls; `SimpleXMLRPCServer` answers them after `register_introspection_functions()`, and its side is priced under `SimpleXMLRPCDispatcher` |
| `proxy('close')()`, `with ServerProxy(...) as proxy` | O(1) | O(1) | Closes the transport's connection |
| `proxy('transport')` | O(1) | O(1) | The transport the proxy sends through |
| `xmlrpc.client.Transport`, `xmlrpc.client.SafeTransport` | O(1) | O(1) | Keep one HTTP (or HTTPS) connection and send the next call over it while the server leaves it open |

### MultiCall

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.client.MultiCall(server)` | O(1) | O(1) | Wraps a `ServerProxy` |
| `multicall.name(*args)` | O(1) | O(1) | Queues the call locally; sends nothing |
| `multicall()` | O(n) | O(n) | Sends all c queued calls as one `system.multicall` request: one round trip instead of c |
| Iterating the result, `result[i]` | O(1) per result | O(1) | A call that failed raises `Fault` when its position is reached; the results before it are still returned |

### dumps and loads

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.client.dumps(params, methodname=None, methodresponse=None, encoding=None, allow_none=False)` | O(n) | O(n) | n = the document returned; a reference cycle raises `TypeError`, and `None` needs `allow_none` |
| `xmlrpc.client.loads(data, use_datetime=False, use_builtin_types=False)` | O(n) | O(n) | Returns `(params, methodname)`; a fault document raises `Fault` |

### Binary and DateTime

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.client.Binary(data=None)` | O(1) for `bytes`, O(b) for `bytearray` | O(1) for `bytes`, O(b) for `bytearray` | A `bytes` argument is kept as it is; a `bytearray` is copied |
| `Binary.data` | O(1) | O(1) | The stored `bytes` object |
| `Binary.encode(out)` | O(b) | O(b) | Writes the base64 form to `out.write()` |
| `Binary.decode(bytes)` | O(b) | O(b) | Base64-decodes into `data` |
| `xmlrpc.client.DateTime(value=0)` | O(1) | O(1) | Stores a `YYYYMMDDTHH:MM:SS` string; the default `0` means the current local time |
| `DateTime.decode(string)`, `DateTime.encode(out)` | O(1) | O(1) | Replace or write that string |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.client.Fault(faultCode, faultString)`, `Fault.faultCode`, `Fault.faultString` | O(1) | O(1) | What a call raises when the server method raised; any exception other than `Fault` arrives as code 1 |
| `xmlrpc.client.ProtocolError`, `ProtocolError.url`, `ProtocolError.errcode`, `ProtocolError.errmsg`, `ProtocolError.headers` | O(1) | O(1) | Raised for an HTTP status other than 200 |
| `xmlrpc.client.MAXINT`, `xmlrpc.client.MININT` | O(1) | O(1) | Marshalling an `int` outside them raises `OverflowError` |
| `xmlrpc.client.Error`, `xmlrpc.client.ResponseError` | O(1) | O(1) | The base class, and what `loads()` raises for XML with no XML-RPC params, fault or method name in it |

### SimpleXMLRPCServer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.server.SimpleXMLRPCServer(addr, requestHandler=SimpleXMLRPCRequestHandler, logRequests=True, allow_none=False, encoding=None, bind_and_activate=True, use_builtin_types=False)` | O(1) | O(1) | Binds and listens; serves one request at a time |
| `SimpleXMLRPCServer.register_function(function=None, name=None)` | O(1) | O(1) | One dictionary entry; also usable as a decorator |
| `SimpleXMLRPCServer.register_instance(instance, allow_dotted_names=False)` | O(1) | O(1) | Replaces any earlier instance; names are looked up on it at call time |
| `SimpleXMLRPCServer.register_introspection_functions()` | O(1) | O(1) | Adds `system.listMethods`, `system.methodSignature` and `system.methodHelp` |
| `SimpleXMLRPCServer.register_multicall_functions()` | O(1) | O(1) | Adds `system.multicall` |
| Dispatching a request | O(n) | O(n) | Reads the whole body, parses it, looks up the name, and marshals the result |
| Dispatching to the registered instance | O(p) | O(p) | Only for a name no registered function has: one `getattr` per dotted segment with `allow_dotted_names=True`, a single one without, and a segment starting with `_` is refused; an instance that defines `_dispatch` receives the name instead |

### SimpleXMLRPCDispatcher

The server side of the `system.*` methods. `SimpleXMLRPCServer` and `CGIXMLRPCRequestHandler`
both inherit them.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SimpleXMLRPCDispatcher.system_listMethods()` | O(f log f) | O(f) | Sorted names, rebuilt per call; a registered instance's `dir()` is walked each time unless it defines `_listMethods` or `_dispatch` |
| `SimpleXMLRPCDispatcher.system_methodHelp(method_name)` | O(p + h) | O(p + h) | The method's docstring, or `''` for an unknown name; p counts only when the name is resolved on the instance |
| `SimpleXMLRPCDispatcher.system_methodSignature(method_name)` | O(1) | O(1) | Always `'signatures not supported'` |
| `SimpleXMLRPCDispatcher.system_multicall(call_list)` | O(n) | O(n) | One dispatch per call; a call that raises becomes a fault entry and the rest still run |

### SimpleXMLRPCRequestHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.server.SimpleXMLRPCRequestHandler` | O(1) | O(1) | Speaks HTTP/1.0 unless `protocol_version` is overridden, so the connection closes after each response |
| `SimpleXMLRPCRequestHandler.rpc_paths` | O(1) | O(1) | Includes `'/'` and `'/RPC2'` by default; a POST to a path outside it gets a 404 without being parsed, and an empty tuple accepts every path |
| `SimpleXMLRPCRequestHandler.encode_threshold` | O(1) | O(1) | A response longer than it (1,400 bytes by default) is gzip-compressed, O(n), when the client accepts gzip, as `ServerProxy` does |

### CGIXMLRPCRequestHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.server.CGIXMLRPCRequestHandler(allow_none=False, encoding=None, use_builtin_types=False)` | O(1) | O(1) | The same dispatcher with no socket |
| `CGIXMLRPCRequestHandler.register_function(function=None, name=None)`, `CGIXMLRPCRequestHandler.register_instance(instance)`, `CGIXMLRPCRequestHandler.register_introspection_functions()`, `CGIXMLRPCRequestHandler.register_multicall_functions()` | O(1) | O(1) | As on `SimpleXMLRPCServer` |
| `CGIXMLRPCRequestHandler.handle_request(request_text=None)` | O(n) | O(n) | Reads the request from stdin when `request_text` is omitted, and writes headers and response to stdout |

### Documenting servers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlrpc.server.DocXMLRPCServer(addr, requestHandler=DocXMLRPCRequestHandler, ...)`, `xmlrpc.server.DocXMLRPCRequestHandler` | O(1) | O(1) | A `SimpleXMLRPCServer` that also answers GET with an HTML page |
| `xmlrpc.server.DocCGIXMLRPCRequestHandler()` | O(1) | O(1) | The CGI equivalent |
| `DocXMLRPCServer.set_server_title(server_title)`, `DocXMLRPCServer.set_server_name(server_name)`, `DocXMLRPCServer.set_server_documentation(server_documentation)` | O(1) | O(1) | Stored for the next page |
| `DocCGIXMLRPCRequestHandler.set_server_title(server_title)`, `DocCGIXMLRPCRequestHandler.set_server_name(server_name)`, `DocCGIXMLRPCRequestHandler.set_server_documentation(server_documentation)` | O(1) | O(1) | Stored for the next page |
| A GET for the documentation page | O(f log f + t) | O(f + t) | Rebuilt on every request from the method list, each method's docstring and the server documentation |

## Making Calls

### One Round Trip per Call

Attribute access on a proxy costs nothing; the call is what sends. Each call marshals its
arguments, waits for the server, and parses the complete response, so c calls are c round trips.
A `MultiCall` queues them and sends one request.

```python
import threading
from xmlrpc.client import MultiCall, ServerProxy
from xmlrpc.server import SimpleXMLRPCServer

with SimpleXMLRPCServer(('127.0.0.1', 0), logRequests=False) as server:
    server.register_function(pow)
    server.register_multicall_functions()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address

    with ServerProxy(f'http://{host}:{port}/') as proxy:  # O(1) - no connection yet
        assert proxy.pow(2, 10) == 1024  # O(n) plus one round trip

        batch = MultiCall(proxy)
        for exponent in range(5):
            batch.pow(2, exponent)  # O(1) - queued, not sent
        assert list(batch()) == [1, 2, 4, 8, 16]  # O(n), one round trip for all five

    server.shutdown()
```

### Connection Reuse

The transport keeps its connection and sends the next call over it, but only if the server left
it open. `SimpleXMLRPCRequestHandler` speaks HTTP/1.0 and closes the connection after every
response, so each call pays for a new one. A handler that sets `protocol_version` to HTTP/1.1
keeps it.

```python
import threading
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

class CountingServer(SimpleXMLRPCServer):
    connections = 0

    def get_request(self):
        CountingServer.connections += 1
        return super().get_request()

class KeepAlive(SimpleXMLRPCRequestHandler):
    protocol_version = 'HTTP/1.1'

def connections_for_ten_calls(handler):
    CountingServer.connections = 0
    with CountingServer(('127.0.0.1', 0), requestHandler=handler, logRequests=False) as server:
        server.register_function(abs)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        host, port = server.server_address
        with ServerProxy(f'http://{host}:{port}/') as proxy:
            for number in range(10):
                assert proxy.abs(-number) == number
        server.shutdown()
    return CountingServer.connections

assert connections_for_ten_calls(SimpleXMLRPCRequestHandler) == 10  # one per call
assert connections_for_ten_calls(KeepAlive) == 1  # reused
```

### Faults and Protocol Errors

An exception in the server method comes back as a `Fault`, so the call still costs its round
trip. A `Fault` the method raises itself keeps its code; anything else arrives as code 1. An HTTP
error, such as a path outside `rpc_paths`, is a `ProtocolError` instead.

```python
import threading
from xmlrpc.client import Fault, ProtocolError, ServerProxy
from xmlrpc.server import SimpleXMLRPCServer

def withdraw(amount):
    if amount > 100:
        raise Fault(4, 'insufficient funds')
    return 100 - amount

with SimpleXMLRPCServer(('127.0.0.1', 0), logRequests=False) as server:
    server.register_function(withdraw)
    server.register_function(int)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address

    with ServerProxy(f'http://{host}:{port}/') as proxy:
        assert proxy.withdraw(30) == 70
        try:
            proxy.withdraw(500)
        except Fault as fault:
            assert (fault.faultCode, fault.faultString) == (4, 'insufficient funds')
        else:
            raise AssertionError('no fault was raised')

        try:
            proxy.int('not a number')
        except Fault as fault:
            assert fault.faultCode == 1 and 'ValueError' in fault.faultString
        else:
            raise AssertionError('no fault was raised')

    with ServerProxy(f'http://{host}:{port}/elsewhere') as proxy:
        try:
            proxy.withdraw(30)
        except ProtocolError as error:
            assert error.errcode == 404
        else:
            raise AssertionError('a path outside rpc_paths was served')

    server.shutdown()
```

## Marshalling Without a Server

`dumps()` and `loads()` are the two halves of every call, usable on their own. Both are linear in
the document. `dumps()` writes a value out once for every place it is referenced, so a structure
that shares one list many times marshals to a document that repeats it; a reference cycle raises
`TypeError` instead of recursing forever.

```python
from xmlrpc.client import MAXINT, dumps, loads

request = dumps(({'name': 'Alice', 'tags': ['a', 'b']}, 42), 'store')  # O(n)
params, method = loads(request)  # O(n)
assert method == 'store'
assert params == ({'name': 'Alice', 'tags': ['a', 'b']}, 42)

shared = ['x' * 100]
twice = dumps(([shared, shared],))  # the shared list is written out twice
once = dumps(([shared],))
assert twice.count('x' * 100) == 2 and once.count('x' * 100) == 1

cycle = []
cycle.append(cycle)
try:
    dumps((cycle,))
except TypeError as error:
    assert 'recursive' in str(error)
else:
    raise AssertionError('a cycle was marshalled')

try:
    dumps((MAXINT + 1,))
except OverflowError:
    pass
else:
    raise AssertionError('an int past MAXINT was marshalled')

assert loads(dumps((None,), allow_none=True))[0] == (None,)
```

### Binary and DateTime

`Binary` and `DateTime` are the wrappers for base64 and ISO 8601 values. `loads()` returns them by
default; `use_builtin_types=True` returns `bytes` and `datetime` instead. `Binary(data)` keeps a
`bytes` argument as it is, and copies a `bytearray`.

```python
import datetime
import io
from xmlrpc.client import Binary, DateTime, dumps, loads

payload = b'\x00\x01' * 1000
wrapped = Binary(payload)  # O(1) - the same bytes object
assert wrapped.data is payload
assert Binary(bytearray(payload)).data is not payload  # O(b) copy

out = io.StringIO()
wrapped.encode(out)  # O(b) base64
assert out.getvalue().startswith('<value><base64>')

(value,), _ = loads(dumps((wrapped,)))  # O(n)
assert isinstance(value, Binary) and value.data == payload

(raw,), _ = loads(dumps((wrapped,)), use_builtin_types=True)
assert raw == payload

moment = datetime.datetime(2024, 5, 17, 12, 30, 0)
stamp = DateTime(moment)  # O(1)
assert stamp.value == '20240517T12:30:00'
(back,), _ = loads(dumps((stamp,)), use_builtin_types=True)
assert back == moment
```

## Serving

### Registration and Dispatch

Registering is a dictionary entry. A call's name is looked up among the registered functions
first; only a name none of them has falls through to the registered instance, where it is
resolved with `getattr` unless the instance defines its own `_dispatch`. There, a name with a
segment starting with `_` is refused, and dotted names reach nested objects only with
`allow_dotted_names=True`, which exposes whatever those objects can reach.

```python
import threading
from xmlrpc.client import Fault, ServerProxy
from xmlrpc.server import SimpleXMLRPCServer

class Service:
    def greet(self):
        return 'from the instance'

    def version(self):
        return '1.0'

    def _internal(self):
        return 'hidden'

with SimpleXMLRPCServer(('127.0.0.1', 0), logRequests=False) as server:
    @server.register_function(name='greet')  # O(1)
    def greet():
        return 'from the function'

    server.register_instance(Service())  # O(1)
    server.register_introspection_functions()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address

    with ServerProxy(f'http://{host}:{port}/') as proxy:
        assert proxy.greet() == 'from the function'  # functions come first
        assert proxy.version() == '1.0'  # O(p) getattr on the instance
        try:
            proxy._internal()
        except Fault as fault:
            assert 'not supported' in fault.faultString
        else:
            raise AssertionError('a private method was called')

        methods = proxy.system.listMethods()  # O(f log f) on the server
        assert methods == sorted(methods)
        assert {'greet', 'version', 'system.listMethods'} <= set(methods)

    server.shutdown()
```

### One Request at a Time

`SimpleXMLRPCServer` handles each request to completion before it accepts the next, so one slow
method delays every other client. Mixing in `socketserver.ThreadingMixIn` runs each request in its
own thread.

```python
import socketserver
import threading
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer

class ThreadedServer(socketserver.ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True

both_inside = threading.Barrier(2, timeout=10)

def rendezvous():
    both_inside.wait()  # returns only when two calls are running at once
    return True

with ThreadedServer(('127.0.0.1', 0), logRequests=False) as server:
    server.register_function(rendezvous)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address

    results = []

    def call():
        with ServerProxy(f'http://{host}:{port}/') as proxy:
            results.append(proxy.rendezvous())

    clients = [threading.Thread(target=call) for _ in range(2)]
    for client in clients:
        client.start()
    for client in clients:
        client.join()
    assert results == [True, True]

    server.shutdown()
```

### Handling a Request Through CGI

`CGIXMLRPCRequestHandler` is the same dispatcher without a socket: `handle_request()` parses one
request and writes the HTTP headers and response to standard output.

```python
import contextlib
import io
import sys
from xmlrpc.client import dumps, loads
from xmlrpc.server import CGIXMLRPCRequestHandler

handler = CGIXMLRPCRequestHandler()
handler.register_function(len)  # O(1)

stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
with contextlib.redirect_stdout(stdout):
    handler.handle_request(dumps(([1, 2, 3],), 'len'))  # O(n)
    sys.stdout.flush()

output = stdout.buffer.getvalue()
headers, _, body = output.partition(b'\n\n')
assert b'Content-Type: text/xml' in headers
assert loads(body)[0] == (3,)
```

### Documentation Pages

`DocXMLRPCServer` answers GET with an HTML page built from the registered methods. The page is
rebuilt on every request: the methods are listed and sorted, and each docstring is rendered.

```python
import threading
import urllib.request
from xmlrpc.server import DocXMLRPCServer

def add(a, b):
    """Addition."""
    return a + b

with DocXMLRPCServer(('127.0.0.1', 0), logRequests=False) as server:
    server.register_function(add)
    server.set_server_title('Calculator')  # O(1)
    server.set_server_name('Calculator service')
    server.set_server_documentation('Arithmetic over XML-RPC.')
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address

    with urllib.request.urlopen(f'http://{host}:{port}/') as response:  # O(f log f + t)
        page = response.read().decode('utf-8')
    assert '<title>Python: Calculator</title>' in page
    assert 'Addition.' in page

    server.shutdown()
```

## Common Patterns

### Batching Many Small Calls

A `MultiCall` turns c round trips into one. A call that fails does not stop the batch: its
`Fault` is raised when the result is reached, and the results around it are still there.

```python
import threading
from xmlrpc.client import Fault, MultiCall, ServerProxy
from xmlrpc.server import SimpleXMLRPCServer

with SimpleXMLRPCServer(('127.0.0.1', 0), logRequests=False) as server:
    server.register_function(int)
    server.register_multicall_functions()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address

    with ServerProxy(f'http://{host}:{port}/') as proxy:
        batch = MultiCall(proxy)
        for text in ['1', 'two', '3']:
            batch.int(text)  # O(1) each
        results = batch()  # O(n), one round trip

        assert results[0] == 1  # O(1)
        try:
            results[1]
        except Fault as fault:
            assert 'ValueError' in fault.faultString
        else:
            raise AssertionError('the failed call returned a value')
        assert results[2] == 3

    server.shutdown()
```

## Performance Best Practices

✅ **Do**:

- Batch independent calls with `MultiCall`: c calls become one round trip
- Keep one `ServerProxy` per server and reuse it; a new proxy starts a new connection
- Set `protocol_version = 'HTTP/1.1'` on the request handler when clients make many calls, so
  they can reuse the connection
- Mix in `socketserver.ThreadingMixIn` when a method can be slow, so it does not hold up other
  clients

❌ **Avoid**:

- A loop of small remote calls where one `MultiCall`, or one call taking a list, would do
- Very large arguments or results: the request is built whole in memory, and the whole result is
  materialized before the call returns
- Sharing one large object many times inside an argument; it is marshalled once per reference
- `allow_dotted_names=True` on anything reachable from an untrusted network

## Version Notes

- **All Python 3**: `SimpleXMLRPCRequestHandler` speaks HTTP/1.0, so every call opens a new
  connection unless the handler sets `protocol_version = 'HTTP/1.1'`

## Related Modules

- **[http](http.md)** - `http.client` and `http.server`, which carry every call
- **[socketserver](socketserver.md)** - `ThreadingMixIn` and the serving loop `SimpleXMLRPCServer`
  inherits
- **[json](json.md)** - the other common text format for structured data
- **[xml](xml.md)** - the XML packages; `xmlrpc` parses with `xml.parsers.expat`
