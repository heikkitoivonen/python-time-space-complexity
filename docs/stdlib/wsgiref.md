# wsgiref Module Complexity

The `wsgiref` package is the reference implementation of WSGI (PEP 3333): a development server,
handlers that run an application against a set of streams, a `Headers` class, validation
middleware and a few environ helpers. Everything here is pure Python, and a handler serves one
request: the response is passed to the output stream chunk by chunk as the application produces
it, never collected first.

A request is the unit throughout. `e` is the entries in the WSGI environ, `h` is the header lines
in the message at hand (the response headers for `Headers` and `start_response`, the request
headers for `get_environ()`), `c` is the chunks the application's iterable yields and `r` is the
bytes they add up to. `p` is the characters in `PATH_INFO`, `u` is the characters in a
reconstructed URL, and `k` is a `FileWrapper` block size. Header names and values and environ
values are priced as O(1) each: the bounds count lines and entries, not their characters, except
where a row names `p`, `u`, `k` or `r`. The application's own work and memory are outside every
bound.

## Complexity Reference

### WSGIServer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wsgiref.simple_server.make_server(host, port, app, server_class=WSGIServer, handler_class=WSGIRequestHandler)` | O(1) | O(1) | Binds and listens; binding also calls `socket.getfqdn(host)`, so setup includes a resolver lookup |
| `WSGIServer(server_address, RequestHandlerClass)` | O(1) | O(1) | An `HTTPServer` with no threading mix-in: one request at a time |
| `WSGIServer.set_app(application)`, `WSGIServer.get_app()` | O(1) | O(1) | Stores or returns the callable |
| `server.handle_request()`, `server.serve_forever()` | O(e + h + c + r) per request | O(e + h) per request | One `WSGIRequestHandler` per connection, run in the serving thread |

### WSGIRequestHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `WSGIRequestHandler.handle()` | O(e + h + c + r) | O(e + h) | One request per connection, answered as HTTP/1.0; a request line over 65,536 bytes gets a 414 and the application is not called |
| `WSGIRequestHandler.get_environ()` | O(e + h) | O(e + h) | Copies the server's base environ and adds one entry per distinct request header name |
| `WSGIRequestHandler.get_stderr()` | O(1) | O(1) | Returns `sys.stderr` |

### BaseHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseHandler.run(app)` | O(e + h + c + r) | O(e + h) | Builds the environ, calls the application, then writes and flushes each chunk before taking the next |
| `BaseHandler.start_response(status, headers, exc_info=None)` | O(h) | O(1) | Wraps the header list in `Headers` and checks every pair; nothing is sent yet |
| `BaseHandler.write(data)` | O(len(data)) | O(1) | Writes and flushes; the first call also sends the status line and headers, O(h) time and space |
| `BaseHandler.setup_environ()` | O(e) | O(e) | Copies `os_environ`, then `add_cgi_vars()` adds the request's variables |
| `BaseHandler.os_environ` | O(1) | O(1) | A dict read from `os.environ` once, when `wsgiref.handlers` is imported |
| `BaseHandler.add_cgi_vars()`, `BaseHandler.get_stdin()`, `BaseHandler.get_stderr()`, `BaseHandler._write(data)`, `BaseHandler._flush()` | O(1) | O(1) | Abstract; a subclass supplies them, and `SimpleHandler`'s `_write` is O(len(data)) |
| `BaseHandler.get_scheme()` | O(1) | O(1) | `guess_scheme()` on the environ |
| `BaseHandler.sendfile()` | O(1) | O(1) | Returns `False`, so a `wsgi.file_wrapper` response is read and written in blocks |
| `BaseHandler.log_exception(exc_info)` | O(f) | O(f) | f = traceback frames printed, capped by `BaseHandler.traceback_limit` |
| `BaseHandler.error_output(environ, start_response)` | O(1) | O(1) | Starts the response with `error_status` and `error_headers` and returns `[error_body]`; `run()` calls it only if no header has gone out yet |
| `BaseHandler.wsgi_multithread`, `BaseHandler.wsgi_multiprocess`, `BaseHandler.wsgi_run_once`, `BaseHandler.wsgi_file_wrapper`, `BaseHandler.server_software`, `BaseHandler.origin_server`, `BaseHandler.http_version`, `BaseHandler.traceback_limit`, `BaseHandler.error_status`, `BaseHandler.error_headers`, `BaseHandler.error_body` | O(1) | O(1) | Class attributes; set them on a subclass or an instance |

### SimpleHandler and the CGI handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wsgiref.handlers.SimpleHandler(stdin, stdout, stderr, environ, multithread=True, multiprocess=False)` | O(1) | O(1) | Keeps the streams and the environ; nothing is read until `run()` |
| `wsgiref.handlers.BaseCGIHandler(stdin, stdout, stderr, environ, multithread=True, multiprocess=False)` | O(1) | O(1) | `origin_server` is false: it writes a `Status:` line instead of an HTTP status line |
| `wsgiref.handlers.CGIHandler()` | O(e) | O(e) | Calls `read_environ()` on every construction; its own `os_environ` is empty |
| `wsgiref.handlers.IISCGIHandler()` | O(e + p) | O(e + p) | `CGIHandler` plus stripping the script name duplicated at the front of `PATH_INFO` |
| `wsgiref.handlers.read_environ()` | O(e) | O(e) | One entry per `os.environ` variable, with the request ones re-decoded |

### Headers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wsgiref.headers.Headers(headers=None)` | O(h) | O(1) | Checks every pair's types; wraps the list it is given without copying it, so changes show up in that list |
| `headers[name]`, `Headers.get(name, default=None)`, `name in headers` | O(h) | O(1) | Case-insensitive scan of the list; a hit stops at the first match |
| `Headers.get_all(name)` | O(h) | O(h) | Scans the whole list |
| `headers[name] = value` | O(h) | O(h) | Deletes every existing `name` by rebuilding the list, then appends |
| `del headers[name]` | O(h) | O(h) | Rebuilds the list; a missing name is not an error |
| `Headers.setdefault(name, value)` | O(h) | O(1) | A `get()` scan, then an append on a miss |
| `Headers.add_header(name, value, **params)` | O(1 + a) | O(1 + a) | a = keyword parameters; appends without looking for an existing header |
| `Headers.keys()`, `Headers.values()`, `Headers.items()` | O(h) | O(h) | New lists; `items()` is a copy of the wrapped list |
| `len(headers)` | O(1) | O(1) | Counts duplicates |
| `str(headers)`, `bytes(headers)` | O(h) | O(h) | The header block with its closing blank line |

### FileWrapper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wsgiref.util.FileWrapper(filelike, blksize=8192)` | O(1) | O(1) | Keeps the file; forwards its `close()` if it has one |
| Iterating a `FileWrapper` | O(k) per step | O(k) | One `read(blksize)` per step, stopping at the first empty read |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wsgiref.util.guess_scheme(environ)` | O(1) | O(1) | Reads `HTTPS` |
| `wsgiref.util.application_uri(environ)` | O(u) | O(u) | Quotes `SCRIPT_NAME` |
| `wsgiref.util.request_uri(environ, include_query=True)` | O(u) | O(u) | Quotes `SCRIPT_NAME` and `PATH_INFO` |
| `wsgiref.util.shift_path_info(environ)` | O(p) | O(p) | Splits and rejoins the whole remaining `PATH_INFO` on every call |
| `wsgiref.util.setup_testing_defaults(environ)` | O(1) | O(1) | Adds a fixed set of keys with `setdefault`; existing values stay |
| `wsgiref.util.is_hop_by_hop(header_name)` | O(1) | O(1) | Set lookup on the lowercased name |
| `wsgiref.simple_server.demo_app(environ, start_response)` | O(e log e) | O(e) | Sorts the whole environ and writes it into the body |
| `wsgiref.validate.validator(application)` | O(1) | O(1) | Wraps; the checks run per request |
| Calling a `validator` wrapper | O(e + h) per request, O(1) per chunk | O(e + h) | Checks every environ key and every response header, then the type of each chunk |

### wsgiref.types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wsgiref.types.StartResponse`, `wsgiref.types.WSGIEnvironment`, `wsgiref.types.WSGIApplication`, `wsgiref.types.InputStream`, `wsgiref.types.ErrorStream`, `wsgiref.types.FileWrapper` | O(1) | O(1) | Protocols and aliases for type checkers; nothing checks them at run time. Python 3.11+ |

## Serving Requests

`make_server()` gives a single-threaded server: `handle_request()` serves one connection and
returns, and `serve_forever()` does the same in a loop, so a slow application holds up every
other client. Each connection carries one request, answered as HTTP/1.0 and then closed.

```python
import http.client
import threading
from wsgiref.simple_server import WSGIRequestHandler, make_server

class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # keep stderr quiet
        pass

def application(environ, start_response):
    if environ['PATH_INFO'] == '/':
        status, body = '200 OK', b'Hello, World!'
    else:
        status, body = '404 Not Found', b'Not Found'
    start_response(status, [('Content-Type', 'text/plain')])
    return [body]  # one chunk, so the handler can add Content-Length

# O(1) plus a name lookup
with make_server('127.0.0.1', 0, application, handler_class=QuietHandler) as server:
    worker = threading.Thread(target=server.handle_request)  # serves one request
    worker.start()

    connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
    connection.request('GET', '/')
    response = connection.getresponse()
    assert response.status == 200
    assert response.read() == b'Hello, World!'
    assert response.version == 10 and response.will_close  # HTTP/1.0, one request
    assert response.getheader('Content-Length') == '13'

    worker.join()
    connection.close()
```

## Running an Application Without a Server

The handlers take any streams, so an application can be run against in-memory files. The response
is streamed: each chunk is written and flushed before the next one is taken, so the handler holds
no copy of the body. When the application does not set `Content-Length`, the handler adds it only
for a sequence of exactly one chunk or an empty body; otherwise the length is unknown and the
response ends when the connection closes.

```python
import io
from wsgiref.handlers import SimpleHandler
from wsgiref.util import setup_testing_defaults

def run(app):
    environ = {}
    setup_testing_defaults(environ)  # O(1)
    out = io.BytesIO()
    SimpleHandler(io.BytesIO(), out, io.StringIO(), environ).run(app)  # O(e + h + c + r)
    return out.getvalue()

def one_chunk(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'hello']

def generated(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    yield b'hel'
    yield b'lo'

assert b'Content-Length: 5' in run(one_chunk)
assert b'Content-Length' not in run(generated)
assert run(generated).endswith(b'\r\n\r\nhello')
```

### Chunks Cost a Write Each

Every chunk is its own `write()` and `flush()` on the output stream, which on the development
server is a send on the socket. Yielding many tiny pieces costs a call per piece; join small
pieces before yielding them.

```python
import io
from wsgiref.handlers import SimpleHandler
from wsgiref.util import setup_testing_defaults

class CountingStream(io.BytesIO):
    flushes = 0

    def flush(self):
        CountingStream.flushes += 1

def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return (b'x' for _ in range(100))  # 100 chunks

environ = {}
setup_testing_defaults(environ)
SimpleHandler(io.BytesIO(), CountingStream(), io.StringIO(), environ).run(app)
assert CountingStream.flushes == 100  # one per chunk
```

## Headers

`Headers` is a list of `(name, value)` pairs with a mapping interface on top, not a dict. Every
lookup lowercases and compares names one by one, and assignment deletes all existing copies of the
name before appending. `add_header()` only appends, which is what allows repeated headers such as
`Set-Cookie`. The list passed in is wrapped, not copied.

```python
from wsgiref.headers import Headers

pairs = [('Content-Type', 'text/plain')]
headers = Headers(pairs)  # O(h) type checks, no copy

headers['X-Request-Id'] = '42'  # O(h) - removes any old copies first
assert pairs[-1] == ('X-Request-Id', '42')  # the wrapped list changed

headers.add_header('Set-Cookie', 'a=1')  # O(1) - appends, no scan
headers.add_header('Set-Cookie', 'b=2')
assert headers.get_all('set-cookie') == ['a=1', 'b=2']  # O(h), case-insensitive
assert headers['content-type'] == 'text/plain'  # O(h) scan
assert headers['missing'] is None  # a miss returns None, not KeyError

headers.add_header('Content-Disposition', 'attachment', filename='report.csv')
assert headers['Content-Disposition'] == 'attachment; filename="report.csv"'

del headers['set-cookie']  # O(h) - rebuilds the list
assert len(headers) == 3  # O(1)
assert bytes(headers).endswith(b'\r\n\r\n')  # O(h)
```

## Serving Files

`FileWrapper` turns a file into an iterable of `blksize` reads. The reference handlers have no
platform file-transmission path (`sendfile()` returns `False`), so a wrapped file is read and
written a block at a time: memory stays at one block, and a larger block means fewer writes.

```python
import io
from wsgiref.util import FileWrapper

source = io.BytesIO(b'x' * 25_000)
blocks = list(FileWrapper(source, blksize=10_000))  # O(k) per block
assert [len(block) for block in blocks] == [10_000, 10_000, 5_000]

wrapper = FileWrapper(io.BytesIO(b'data'))
wrapper.close()  # forwarded to the file
```

## Dispatching on the Path

`shift_path_info()` moves one segment from `PATH_INFO` to `SCRIPT_NAME`, but it splits and rejoins
the whole remaining path to do so. Walking a path one segment at a time therefore re-splits what
remains on every call; split `PATH_INFO` once when an application needs every segment.

```python
from wsgiref.util import request_uri, setup_testing_defaults, shift_path_info

environ = {'PATH_INFO': '/users/42/profile', 'QUERY_STRING': 'tab=posts'}
setup_testing_defaults(environ)

assert shift_path_info(environ) == 'users'  # O(p)
assert environ['SCRIPT_NAME'] == '/users'
assert environ['PATH_INFO'] == '/42/profile'

# O(u) - rebuilt from the environ, quoted
assert request_uri(environ) == 'http://127.0.0.1/users/42/profile?tab=posts'

# All the segments at once - one O(p) split instead of one per segment
segments = [part for part in environ['PATH_INFO'].split('/') if part]
assert segments == ['42', 'profile']
```

## Validating an Application

`validator()` wraps an application in checks for the WSGI rules. The checks cost O(e + h) time and
memory per request and a type check per chunk, so it belongs in tests and development rather than in front
of production traffic. It catches the classic mistake of returning a `bytes` object instead of a
list of them; unwrapped, the handler iterates the bytes as integers and answers 500.

```python
import io
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

def broken(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return b'hello'  # should be [b'hello']

environ = {'QUERY_STRING': ''}
setup_testing_defaults(environ)
checked = validator(broken)  # O(1)

try:
    checked(environ, lambda status, headers, exc_info=None: None)
except AssertionError as error:
    assert 'single-item list' in str(error)
else:
    raise AssertionError('returning bytes was accepted')
```

## Common Patterns

### Testing an Application Directly

A WSGI application is a callable, so a test can call it with a filled-in environ and a
`start_response` that records its arguments: no server, no socket.

```python
from wsgiref.util import setup_testing_defaults

def application(environ, start_response):
    name = environ['QUERY_STRING'].partition('=')[2] or 'world'
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [f'Hello, {name}!'.encode()]

captured = {}

def start_response(status, headers, exc_info=None):
    captured['status'] = status
    return lambda data: None

environ = {'QUERY_STRING': 'name=Ada'}
setup_testing_defaults(environ)  # O(1) - fills only what is missing

body = b''.join(application(environ, start_response))  # O(r)
assert captured['status'] == '200 OK'
assert body == b'Hello, Ada!'
```

## Performance Best Practices

✅ **Do**:

- Return a one-element list when the whole body is at hand: the handler can then send
  `Content-Length`
- Yield large chunks from a generator when the body is big, so memory stays at one chunk
- Use `add_header()` for headers that repeat; it appends without the O(h) scan that assignment does
- Test applications by calling them with `setup_testing_defaults()`; no server is needed
- Keep `validator()` to tests and development

❌ **Avoid**:

- The development server in production: one thread, one request per connection, HTTP/1.0
- Yielding many tiny chunks: each one is a write and a flush
- Returning `bytes` or `str` instead of an iterable of `bytes`
- Calling `shift_path_info()` once per segment on a deep path when a single split would do

## Version Notes

- **Python 3.11+**: Added `wsgiref.types`
- **All Python 3**: `simple_server` is single-threaded, answers HTTP/1.0 and closes each
  connection after one request

## Related Modules

- **[http.server](http.md)** - the `HTTPServer` and request handler `wsgiref.simple_server` builds on
- **[socketserver](socketserver.md)** - `ThreadingMixIn`, which `WSGIServer` does not use
- **[urllib](urllib.md)** - `urllib.parse.quote`, which `request_uri()` uses
