# cgi Module Complexity

The `cgi` module parses a CGI request - a query string, a URL-encoded body or a
`multipart/form-data` upload - into `FieldStorage` objects, and prints debugging pages for CGI
scripts. Parsing happens once, when a `FieldStorage` is built, and keeps the fields in a list:
every lookup by name then scans that list.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13. The examples that import `cgi` need
    Python 3.12 or earlier.

`n` is the bytes of the request body and `q` the bytes of the query string, which a POST parses
along with its body. `f` is the fields in the form, `u` the distinct field names, `k` the fields
sharing one name, and `s` the bytes of one part. `L` is the characters in a header line and `p`
the `;` separators in it, inside quotes or not. `e` is environment variables, and `o` the
characters a `print_*` helper writes. Comparing two field or environment variable names, parsing
one part's headers and skipping the preamble before the first boundary are priced at O(1). Space
is memory: it excludes the temporary files large parts are written to and the stream the request
is read from.

## Complexity Reference

### FieldStorage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cgi.FieldStorage(fp=None, headers=None, outerboundary=b'', environ=os.environ, keep_blank_values=0, strict_parsing=0, limit=None, encoding='utf-8', errors='replace', max_num_fields=None, separator='&')`, URL-encoded or GET | O(n + q + f) | O(n + q + f) | Reads the whole body and query string into memory and parses it when built; by default `fp` is `sys.stdin.buffer` and `environ` is `os.environ`. For a form of either kind, `max_num_fields` raises `ValueError` once it has more fields |
| `cgi.FieldStorage(...)`, `multipart/form-data` | O(n + q + f) | O(q + f) | One child `FieldStorage` per part; a part too large for a small in-memory buffer is written to a file from `make_file()`, so an upload's size does not reach memory. Assumes no part is itself URL-encoded |
| `FieldStorage[key]`, `key in form` | O(f) | O(k) | Scans every field; `in` stops at the first match. A repeated name returns a list of its k fields |
| `FieldStorage.getvalue(key, default=None)` | O(f) | O(k) | One scan, plus each match's `.value`; a list when the name repeats |
| `FieldStorage.getfirst(key, default=None)` | O(f) | O(k) | One scan that collects all k matches, plus the first match's `.value` |
| `FieldStorage.getlist(key)` | O(f) | O(k) | One scan, plus each match's `.value`; always a list |
| `FieldStorage.keys()`, `len(form)`, iterating a `FieldStorage` | O(f) | O(u) | A new list of distinct names on every call; `len()` and iteration build it too |
| `FieldStorage.value` | O(1) for a form, O(s) for a part | O(1) for a form, O(s) for a part | A form's field list; a part's contents, read again, whole, from its file on every access |
| `FieldStorage.name`, `.filename`, `.file`, `.list`, `.type`, `.type_options`, `.disposition`, `.disposition_options`, `.headers` | O(1) | O(1) | Set while parsing. `.file` streams an upload in chunks; `.list` is `None` for a single part |
| `FieldStorage.make_file()` | O(1) | O(1) | Returns an anonymous temporary file; override it in a subclass to choose where large parts go |

### MiniFieldStorage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cgi.MiniFieldStorage(name, value)` | O(1) | O(1) | One URL-encoded field; `filename`, `file`, `list` and `type` are `None` |

### Parsing functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cgi.parse(fp=None, environ=os.environ, keep_blank_values=0, strict_parsing=0, separator='&')` | O(n + q + f) | O(n + q + f) | `urllib.parse.parse_qs()` over the query string and URL-encoded body. A `multipart/form-data` body raises `AttributeError`; call `parse_multipart()` for one |
| `cgi.parse_multipart(fp, pdict, encoding='utf-8', errors='replace', separator='&')` | O(n + f·u) | O(n + f) | Builds a `FieldStorage`, then calls `getlist()` once per distinct name, so distinct names make it quadratic. `pdict['boundary']` must be bytes; file parts are read whole into the result |
| `cgi.parse_header(line)` | O(L·(p + 1)) | O(L) | Each `;` can cost a pass over the whole line, so a line made mostly of separators is quadratic |
| `cgi.maxlen` | O(1) | O(1) | `0`, no limit, by default; a POST whose Content-Length exceeds it raises `ValueError` before the body is read |

### Debugging helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cgi.test(environ=os.environ)` | O(n + q + f·u + e log e + o) | O(n + q + f + e + o) | Builds `FieldStorage()` from the process's own request, whatever `environ` is, and prints every helper below; leaves `cgi.maxlen` set to 50 |
| `cgi.print_form(form)` | O(f·u + o) | O(u + o) | Sorts the names, then looks each one up, scanning the form per name |
| `cgi.print_environ(environ=os.environ)` | O(e log e + o) | O(e + o) | Sorted by name |
| `cgi.print_exception(type=None, value=None, tb=None, limit=None)` | O(o) | O(o) | The current exception by default, as HTML |
| `cgi.print_directory()`, `cgi.print_arguments()` | O(o) | O(o) | The working directory; `sys.argv` |
| `cgi.print_environ_usage()` | O(1) | O(1) | A fixed list of CGI variable names |

## Reading a Form

A `FieldStorage` does all its parsing in the constructor. Pass the request's stream and
environment explicitly; the defaults are the process's standard input and `os.environ`, which is
what a CGI script receives.

```python
import cgi
import io

body = b"name=Alice&tag=a&tag=b"
environ = {
    'REQUEST_METHOD': 'POST',
    'CONTENT_TYPE': 'application/x-www-form-urlencoded',
    'CONTENT_LENGTH': str(len(body)),
}

form = cgi.FieldStorage(io.BytesIO(body), environ=environ)  # O(n + q + f)
assert form.getfirst('name') == 'Alice'  # O(f)
assert form.getlist('tag') == ['a', 'b']  # O(f)
assert form.getvalue('missing', 'none') == 'none'  # O(f)
names = form.keys()  # O(f)
assert sorted(names) == ['name', 'tag']

# A GET reads the query string from the environment instead
query = cgi.FieldStorage(environ={'REQUEST_METHOD': 'GET', 'QUERY_STRING': 'q=cgi'})
assert query.getvalue('q') == 'cgi'
```

### Lookups Scan the Form

`FieldStorage` is not a dictionary: `getvalue()`, `getlist()`, `form[key]` and `key in form` each
walk the field list. Looking up every name that way costs O(f·u). Walk `form.list` once instead.

```python
import cgi

pairs = '&'.join(f'field{i}=v' for i in range(1000))
form = cgi.FieldStorage(environ={'REQUEST_METHOD': 'GET', 'QUERY_STRING': pairs})

# O(f·u): every getlist() scans all f fields
slow = {name: form.getlist(name) for name in form.keys()}

# O(f): one pass over the parsed fields
fast = {}
for item in form.list:
    fast.setdefault(item.name, []).append(item.value)

assert fast == slow
```

## File Uploads

A `multipart/form-data` body becomes one child `FieldStorage` per part. A part that outgrows a
small in-memory buffer is written to the file `make_file()` returns, so an upload costs disk, not
memory. `.value` reads that file back whole on every access; copy from `.file` to stream it.

```python
import cgi
import io
import shutil

upload = b"x" * 100_000
body = (
    b'--BOUNDARY\r\n'
    b'Content-Disposition: form-data; name="title"\r\n\r\n'
    b'report\r\n'
    b'--BOUNDARY\r\n'
    b'Content-Disposition: form-data; name="data"; filename="report.bin"\r\n'
    b'Content-Type: application/octet-stream\r\n\r\n'
    + upload + b'\r\n'
    b'--BOUNDARY--\r\n'
)
environ = {
    'REQUEST_METHOD': 'POST',
    'CONTENT_TYPE': 'multipart/form-data; boundary=BOUNDARY',
    'CONTENT_LENGTH': str(len(body)),
}

form = cgi.FieldStorage(io.BytesIO(body), environ=environ)  # O(n + q + f) time, O(q + f) memory
assert form.getvalue('title') == 'report'

item = form['data']  # O(f)
assert item.filename == 'report.bin'
assert item.value == upload  # O(s): read from the file
assert item.value is not item.value  # read again on every access

target = io.BytesIO()
shutil.copyfileobj(item.file, target)  # streams in chunks
assert target.getvalue() == upload
```

### Request Limits

`cgi.maxlen` caps a POST body by its Content-Length before anything is read, and
`max_num_fields` caps the number of fields. Both raise `ValueError`.

```python
import cgi
import io

body = b"a=" + b"x" * 1000
environ = {
    'REQUEST_METHOD': 'POST',
    'CONTENT_TYPE': 'application/x-www-form-urlencoded',
    'CONTENT_LENGTH': str(len(body)),
}

cgi.maxlen = 100  # O(1)
try:
    cgi.FieldStorage(io.BytesIO(body), environ=environ)
except ValueError as error:
    assert 'Maximum content length exceeded' in str(error)
else:
    raise AssertionError('an oversized body was read')
finally:
    cgi.maxlen = 0

try:
    cgi.FieldStorage(environ={'REQUEST_METHOD': 'GET', 'QUERY_STRING': 'a=1&b=2&c=3'},
                     max_num_fields=2)
except ValueError as error:
    assert 'Max number of fields exceeded' in str(error)
else:
    raise AssertionError('a third field was accepted')
```

## Module-Level Parsing

`parse()` and `parse_multipart()` return a plain dictionary of lists, like
`urllib.parse.parse_qs()`. `parse()` handles query strings and URL-encoded bodies only.
`parse_multipart()` builds a `FieldStorage` and then calls `getlist()` once per name, so each
distinct name costs a scan of the whole form.

```python
import cgi
import io

params = cgi.parse(environ={'QUERY_STRING': 'a=1&a=2&b='}, keep_blank_values=True)  # O(q + f)
assert params == {'a': ['1', '2'], 'b': ['']}

body = (
    b'--B\r\nContent-Disposition: form-data; name="a"\r\n\r\n1\r\n'
    b'--B\r\nContent-Disposition: form-data; name="b"\r\n\r\n2\r\n'
    b'--B--\r\n'
)
fields = cgi.parse_multipart(io.BytesIO(body), {'boundary': b'B'})  # O(n + f·u)
assert fields == {'a': ['1'], 'b': ['2']}

# parse() cannot read a multipart body
environ = {
    'REQUEST_METHOD': 'POST',
    'CONTENT_TYPE': 'multipart/form-data; boundary=B',
    'CONTENT_LENGTH': str(len(body)),
}
try:
    cgi.parse(io.BytesIO(body), environ=environ)
except AttributeError as error:
    assert 'decode' in str(error)
else:
    raise AssertionError('parse() read a multipart body')
```

### Parsing Headers

`parse_header()` splits a `Content-Type` or `Content-Disposition` value into the main value and a
dictionary of parameters. Each `;` can cost a pass over the whole line, which is harmless for a
real header and quadratic for one built from separators.

```python
import cgi

value, params = cgi.parse_header('text/html; charset="utf-8"; q=1')  # O(L·(p + 1))
assert value == 'text/html'
assert params == {'charset': 'utf-8', 'q': '1'}
```

## Debugging Helpers

The `print_*` functions write HTML to standard output. `print_form()` sorts the names and looks
each one up, so it inherits the O(f·u) cost of name lookups.

```python
import cgi
import contextlib
import io

form = cgi.FieldStorage(environ={'REQUEST_METHOD': 'GET', 'QUERY_STRING': 'b=2&a=1'})

output = io.StringIO()
with contextlib.redirect_stdout(output):
    cgi.print_form(form)  # O(f·u + o)
    cgi.print_environ({'PATH': '/bin'})  # O(e log e + o)

html = output.getvalue()
assert html.index('<DT>a:') < html.index('<DT>b:')
assert '<DT> PATH <DD> /bin' in html
```

## Migrating Off cgi

The module's own documentation names the replacements: `urllib.parse.parse_qs()` and
`parse_qsl()` for query strings and URL-encoded bodies, and the `email` package for header
parameters and multipart bodies. These run on every Python version.

```python
from email.message import EmailMessage
from urllib.parse import parse_qs, parse_qsl

# cgi.parse() and FieldStorage's URL-encoded path
assert parse_qs('a=1&a=2&b=3') == {'a': ['1', '2'], 'b': ['3']}  # O(q + f)
assert parse_qsl('a=1&b=2') == [('a', '1'), ('b', '2')]  # O(q + f)

# cgi.parse_header()
message = EmailMessage()
message['Content-Type'] = 'text/html; charset="utf-8"'
assert message.get_content_type() == 'text/html'
assert message['Content-Type'].params['charset'] == 'utf-8'
```

## Common Patterns

### A CGI Handler

```python
import cgi
import html
import io

def handle(stdin, environ):
    form = cgi.FieldStorage(stdin, environ=environ)  # O(n + q + f)
    name = form.getfirst('name', 'Guest')  # O(f)
    return 'Content-Type: text/html\n\n<h1>Hello, ' + html.escape(name) + '!</h1>'

page = handle(io.BytesIO(), {'REQUEST_METHOD': 'GET', 'QUERY_STRING': 'name=<Bob>'})
assert page.endswith('<h1>Hello, &lt;Bob&gt;!</h1>')
```

## Performance Best Practices

✅ **Do**:

- Walk `form.list` once when you need every field, rather than looking each name up
- Copy an upload from `.file` in chunks; `.value` reads the whole part into memory every time
- Set `cgi.maxlen`, so an oversized body is rejected before it is read, and `max_num_fields` to cap the fields a request can create
- Move to `urllib.parse` and `email` before Python 3.13

❌ **Avoid**:

- `getvalue()` or `form[key]` in a loop over many names - each call scans the whole form
- `parse_multipart()` on a form with many distinct names - it is quadratic in them
- `parse()` on a `multipart/form-data` body - it raises `AttributeError`
- Calling `cgi.test()` in a process that parses more requests - it leaves `cgi.maxlen` at 50

## Version Notes

- **Python 3.11+**: Importing `cgi` emits `DeprecationWarning`
- **Python 3.13+**: Removed; `import cgi` raises `ModuleNotFoundError`

## Related Modules

- **[urllib](urllib.md)** - `parse_qs()` and `parse_qsl()` replace `cgi.parse()`
- **[email](email.md)** - `EmailMessage` replaces `cgi.parse_header()`
- **[cgitb](cgitb.md)** - Traceback pages for CGI scripts, removed alongside `cgi`
- **[wsgiref](wsgiref.md)** - Runs WSGI applications, including under CGI
- **[tempfile](tempfile.md)** - Where `make_file()` puts large parts
