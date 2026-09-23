# urllib Module Complexity

The `urllib` package is five modules: `urllib.parse` takes URLs and query strings apart and puts
them back together, `urllib.request` opens URLs through a chain of handlers, `urllib.response` and
`urllib.error` are the objects that come back, and `urllib.robotparser` answers `robots.txt`
questions. Parsing is a single pass over the text; opening a URL returns once the headers have
arrived and leaves the body to be read.

`n` is the characters in the text an operation parses or builds - a URL, query string, path or
header value - and `b` is the bytes of a response body that are read. `f` is the fields in a query
string, `m` the headers on a request, `h` the handlers in an opener, `c` the cookies in a cookie
jar, `u` the URIs stored in a password manager, `p` the entries in a proxy mapping, `e` the
environment variables and `k` the temporary files `urlretrieve()` has left. For `robots.txt`, `s`
is the file's size, `g` its user-agent groups, each priced as naming a few agents, and `r` the rules
in the group that applies. Looking
up a header name, a user-agent name or a cache key is priced at O(1). Network and file system waits
are outside the bounds and appear as "+ round trip" where an operation makes one.

## Complexity Reference

### urllib.parse

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.parse.urlsplit(urlstring, scheme='', allow_fragments=True)` | O(n) | O(n) | Python 3.11+: splitting the same string object again is a cache hit, O(1); the cache is bounded |
| `urllib.parse.urlparse(urlstring, scheme='', allow_fragments=True)` | O(n) | O(n) | Builds a new result on every call |
| `urllib.parse.urlunsplit(parts)`, `urllib.parse.urlunparse(parts)` | O(n) | O(n) | |
| `urllib.parse.urljoin(base, url, allow_fragments=True)` | O(n) | O(n) | n = both URLs |
| `urllib.parse.urldefrag(url)` | O(n) | O(n) | |
| `urllib.parse.unwrap(url)` | O(n) | O(n) | Strips a `<URL:...>` wrapper |
| `urllib.parse.quote(string, safe='/', encoding=None, errors=None)`, `urllib.parse.quote_plus(string, safe='', encoding=None, errors=None)`, `urllib.parse.quote_from_bytes(bytes, safe='/')` | O(n) | O(n) | |
| `urllib.parse.unquote(string, encoding='utf-8', errors='replace')`, `urllib.parse.unquote_plus(string, encoding='utf-8', errors='replace')`, `urllib.parse.unquote_to_bytes(string)` | O(n) | O(n) | |
| `urllib.parse.urlencode(query, doseq=False, safe='', encoding=None, errors=None, quote_via=quote_plus)` | O(n + f) | O(n + f) | A field costs more than a character, so many short fields are slower than a few long ones; `doseq=True` makes each item of a sequence value its own field |
| `urllib.parse.parse_qsl(qs, keep_blank_values=False, strict_parsing=False, encoding='utf-8', errors='replace', max_num_fields=None, separator='&')`, `urllib.parse.parse_qs(...)` | O(n + f) | O(n + f) | `max_num_fields` raises `ValueError` before any field is built; only `separator` divides fields |

### SplitResult, ParseResult and DefragResult

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.parse.SplitResult`, `urllib.parse.ParseResult`, `urllib.parse.DefragResult`, `urllib.parse.SplitResultBytes`, `urllib.parse.ParseResultBytes`, `urllib.parse.DefragResultBytes` | O(1) | O(1) | Named tuples; indexing and the named fields are O(1) |
| `SplitResult.geturl()`, and the same method on every result type | O(n) | O(n) | Rebuilds the URL on each call |
| `SplitResult.hostname`, `SplitResult.port`, `SplitResult.username`, `SplitResult.password` | O(n) | O(n) | n = `netloc` length; worked out again on every access |
| `SplitResult.encode(encoding='ascii', errors='strict')`, `SplitResultBytes.decode(encoding='ascii', errors='strict')` | O(n) | O(n) | Converts every field |

### urllib.request

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.urlopen(url, data=None, timeout, *, context=None)` | O(n + h) + round trip | O(n) | Returns once the final response's status and headers are in; its body is not read. A `data:` URL is decoded in full here. Handlers add their own cost, such as a cookie lookup or a redirect |
| `urllib.request.urlretrieve(url, filename=None, reporthook=None, data=None)` | O(n + h + b) + round trip | O(n) | Copies in fixed-size blocks, so memory does not grow with b. A `file:` URL with no `filename` returns the file's own path without copying |
| `urllib.request.urlcleanup()` | O(k) | O(1) | Also uninstalls an opener set by `install_opener()` |
| `urllib.request.build_opener(*handlers)` | O(h²) | O(h) | Worst case; h includes the default handlers. Each is a sorted insertion by `handler_order` |
| `urllib.request.install_opener(opener)` | O(1) | O(1) | `urlopen()` uses this opener from then on |
| `urllib.request.getproxies()` | O(e) | O(e) | Reads `*_proxy` variables; macOS and Windows fall back to the system settings when there are none |
| `urllib.request.pathname2url(path)`, `urllib.request.url2pathname(url)` | O(n) | O(n) | |

### Request

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.Request(url, data=None, headers={}, origin_req_host=None, unverifiable=False, method=None)` | O(n + m) | O(n + m) | The URL is split here, so its parts are ready before anything is sent |
| `Request.full_url`, `Request.get_full_url()` | O(1) | O(1) | O(n) when the URL has a fragment, which is rejoined on every read; assigning a new URL splits it again, O(n) |
| `Request.type`, `Request.host`, `Request.selector`, `Request.origin_req_host`, `Request.unverifiable`, `Request.method`, `Request.data` | O(1) | O(1) | Assigning new `data` drops a `Content-length` header set for the old one |
| `Request.get_method()` | O(1) | O(1) | `POST` when there is `data`, unless `method` says otherwise |
| `Request.add_header(key, val)`, `Request.add_unredirected_header(key, val)` | O(1) | O(1) | The key is stored `capitalize()`d: `User-Agent` becomes `User-agent` |
| `Request.has_header(header_name)`, `Request.get_header(header_name, default=None)`, `Request.remove_header(header_name)` | O(1) | O(1) | Exact-case lookups, so pass the `capitalize()`d name |
| `Request.header_items()` | O(m) | O(m) | A new list of both header sets |
| `Request.set_proxy(host, type)` | O(1) | O(1) | O(n) when the URL has a fragment, as for `full_url` |

### OpenerDirector

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.OpenerDirector()` | O(1) | O(1) | No handlers until they are added |
| `OpenerDirector.add_handler(handler)` | O(h) | O(1) | Keeps the handlers sorted by `handler_order` |
| `OpenerDirector.open(url, data=None, timeout)` | O(n + h) + round trip | O(n) | Every request and response processor for the scheme runs, each adding its own cost; openers are tried in order until one answers |
| `OpenerDirector.error(proto, *args)` | O(h) | O(1) | Tries the `http_error_<code>` handlers, then the defaults |

### BaseHandler and the Protocol Handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.BaseHandler`, `BaseHandler.add_parent(director)`, `BaseHandler.close()`, `BaseHandler.parent` | O(1) | O(1) | |
| `BaseHandler.default_open(req)`, `BaseHandler.unknown_open(req)`, `BaseHandler.http_error_default(req, fp, code, msg, hdrs)` | O(1) | O(1) | Hooks a subclass may define; `OpenerDirector` calls them, and what they do is the subclass's cost |
| `urllib.request.HTTPHandler`, `urllib.request.HTTPSHandler`, `urllib.request.FileHandler`, `urllib.request.DataHandler`, `urllib.request.FTPHandler`, `urllib.request.CacheFTPHandler`, `urllib.request.UnknownHandler` | O(1) | O(1) | Construction |
| `HTTPHandler.http_open(req)`, `HTTPSHandler.https_open(req)` | O(n + m) + round trip | O(n + m) | Sends the request and reads the status line and headers; the body stays unread |
| `FileHandler.file_open(req)` | O(n) + file system | O(n) | Opens a local file without reading it |
| `DataHandler.data_open(req)` | O(n) | O(n) | Decodes the whole payload before returning |
| `FTPHandler.ftp_open(req)` | O(n) + round trips | O(n) | Logs in and starts the transfer; `CacheFTPHandler` keeps logged-in connections for reuse |
| `CacheFTPHandler.setTimeout`, `CacheFTPHandler.setMaxConns` | O(1) | O(1) | How long and how many cached connections are kept |
| `UnknownHandler.unknown_open(req)` | O(1) | O(1) | Raises `URLError` for a scheme no handler serves |

### Processing Handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.HTTPErrorProcessor`, `HTTPErrorProcessor.http_response(req, response)`, `HTTPErrorProcessor.https_response(req, response)` | O(1) | O(1) | Passes a 2xx response through; any other goes to `OpenerDirector.error()`, O(h) |
| `urllib.request.HTTPDefaultErrorHandler` | O(1) | O(1) | Raises the response as `HTTPError` |
| `urllib.request.HTTPRedirectHandler`, `HTTPRedirectHandler.redirect_request(req, fp, code, msg, hdrs, newurl)` | O(n + m) | O(n + m) | Builds the follow-up `Request`: the headers carry over, but not the body, `Content-Length` or `Content-Type` |
| `HTTPRedirectHandler.http_error_301(req, fp, code, msg, hdrs)`, `HTTPRedirectHandler.http_error_302(...)`, `HTTPRedirectHandler.http_error_303(...)`, `HTTPRedirectHandler.http_error_307(...)`, `HTTPRedirectHandler.http_error_308(...)` | O(n + m + b) + round trip | O(n + m + b) | b = the redirect response's own body, read and discarded before the new request; a chain stops with `HTTPError` at the redirect to an 11th different URL, or to one URL for the 5th time |
| `urllib.request.HTTPCookieProcessor(cookiejar=None)`, `HTTPCookieProcessor.cookiejar` | O(1) | O(1) | |
| A request through `HTTPCookieProcessor` | O(c log c) | O(c) | Every domain in the jar is checked, whatever the request's host, and the matching cookies are sorted by path |
| `urllib.request.ProxyHandler(proxies=None)` | O(p) | O(p) | With no mapping it calls `getproxies()`, O(e) |

### Authentication Handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.AbstractBasicAuthHandler(password_mgr=None)`, `urllib.request.HTTPBasicAuthHandler(password_mgr=None)`, `urllib.request.ProxyBasicAuthHandler(password_mgr=None)`, `urllib.request.AbstractDigestAuthHandler(passwd=None)`, `urllib.request.HTTPDigestAuthHandler(passwd=None)`, `urllib.request.ProxyDigestAuthHandler(passwd=None)` | O(1) | O(1) | Construction |
| `AbstractBasicAuthHandler.http_error_auth_reqed(authreq, host, req, headers)`, `HTTPBasicAuthHandler.http_error_401(req, fp, code, msg, hdrs)`, `ProxyBasicAuthHandler.http_error_407(req, fp, code, msg, hdrs)` | O(u·n) + round trip | O(n) | Looks up the password and sends the request again: one extra round trip, unless `HTTPPasswordMgrWithPriorAuth` sends the credentials with the first request |
| `AbstractDigestAuthHandler.http_error_auth_reqed(auth_header, host, req, headers)`, `HTTPDigestAuthHandler.http_error_401(req, fp, code, msg, hdrs)`, `ProxyDigestAuthHandler.http_error_407(req, fp, code, msg, hdrs)` | O(u·n) + round trip | O(n) | The same extra round trip, with a fixed number of hashes |

### Password Managers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.HTTPPasswordMgr()`, `urllib.request.HTTPPasswordMgrWithDefaultRealm()`, `urllib.request.HTTPPasswordMgrWithPriorAuth()` | O(1) | O(1) | |
| `HTTPPasswordMgr.add_password(realm, uri, user, passwd)`, `HTTPPasswordMgrWithPriorAuth.add_password(realm, uri, user, passwd, is_authenticated=False)` | O(n) | O(n) | `uri` may be a sequence of URIs, each stored |
| `HTTPPasswordMgr.find_user_password(realm, authuri)`, `HTTPPasswordMgrWithPriorAuth.find_user_password(realm, authuri)` | O(u·n) | O(n) | Compares `authuri` with every URI stored for the realm; the default-realm managers then try the `None` realm |
| `HTTPPasswordMgrWithPriorAuth.update_authenticated(uri, is_authenticated=False)` | O(n) | O(n) | |
| `HTTPPasswordMgrWithPriorAuth.is_authenticated(authuri)` | O(u·n) | O(n) | A basic-auth handler using this manager asks it on every request |

### URLopener and FancyURLopener

Python 3.10 to 3.13 only; both classes were removed in 3.14.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.URLopener(proxies=None, **x509)`, `urllib.request.FancyURLopener(...)` | O(e) | O(e) | Construction warns `DeprecationWarning`; with no mapping it calls `getproxies()` |
| `URLopener.open(fullurl, data=None)` | O(n) + round trip | O(n) | The body is not read |
| `URLopener.retrieve(url, filename=None, reporthook=None, data=None)` | O(n + b) + round trip | O(n) | Copies in fixed-size blocks; a local file with no `filename` returns its own path |
| `URLopener.open_unknown(fullurl, data=None)` | O(n) | O(n) | Raises `OSError` |
| `URLopener.version` | O(1) | O(1) | The `User-Agent` value it sends |
| `FancyURLopener.prompt_user_passwd(host, realm)` | O(1) + user input | O(1) | Prompts on the terminal |

### addinfourl

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.response.addinfourl(fp, headers, url, code=None)` | O(1) | O(1) | Wraps an open stream; nothing is buffered |
| `addinfourl.url`, `addinfourl.status`, `addinfourl.headers`, `addinfourl.code`, `addinfourl.geturl()`, `addinfourl.getcode()`, `addinfourl.info()` | O(1) | O(1) | The last four are older spellings of the first three |
| Reading a response: `read(size=-1)`, iterating its lines | O(b) | O(b) | `read(size)` bounds both by `size`; each line is held whole, however long |
| `urllib.response.addbase`, `urllib.response.addinfo`, `urllib.response.addclosehook` | O(1) | O(1) | Undocumented bases of `addinfourl`; `addclosehook` runs one callback on close |

### URLError, HTTPError and ContentTooShortError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.error.URLError(reason)`, `URLError.reason` | O(1) | O(1) | A subclass of `OSError` |
| `urllib.error.HTTPError(url, code, msg, hdrs, fp)`, `HTTPError.code`, `HTTPError.reason`, `HTTPError.headers`, `HTTPError.url`, `HTTPError.fp` | O(1) | O(1) | Also a response: reading its body is O(b) |
| `urllib.error.ContentTooShortError(msg, content)`, `ContentTooShortError.content` | O(1) | O(1) | `urlretrieve()` raises it when fewer bytes arrive than `Content-Length` promised |

### RobotFileParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.robotparser.RobotFileParser(url='')`, `RobotFileParser.set_url(url)` | O(n) | O(n) | Nothing is fetched |
| `RobotFileParser.read()` | O(s) + round trip | O(s) | Fetches the whole file, then parses it; a 401 or 403 disallows everything, another 4xx allows everything |
| `RobotFileParser.parse(lines)` | O(s) | O(s) | On 3.13.14+ and 3.14.5+, a user-agent listed in g separate one-rule groups is merged one group at a time, O(g²); give each agent one group |
| `RobotFileParser.can_fetch(useragent, url)` | O(g + n·(r + 1)) | O(n) | `False` until `read()` or `parse()` has run. A wildcard rule is a regular-expression match rather than a prefix test |
| `RobotFileParser.crawl_delay(useragent)`, `RobotFileParser.request_rate(useragent)` | O(g) | O(1) | `None` until the file has been read, or when the group sets no value |
| `RobotFileParser.site_maps()` | O(1) | O(1) | The stored list itself, or `None` when there is none |
| `RobotFileParser.mtime()`, `RobotFileParser.modified()` | O(1) | O(1) | When the file was last read or parsed; `modified()` sets it to now |

## Parsing URLs

### Splitting and Joining

Every parsing function is one pass over the URL. The components of a result are plain tuple
fields, but `hostname`, `port`, `username` and `password` are worked out from `netloc` each time
they are read, so read them once in a loop.

```python
from urllib.parse import urlsplit, urlunsplit, urlparse, urljoin, urldefrag

url = 'https://user:pass@Example.com:8080/docs/page;v=1?query=1#frag'

parts = urlsplit(url)  # O(n)
assert parts.netloc == 'user:pass@Example.com:8080'  # O(1) - a tuple field
host = parts.hostname  # O(n) in netloc - worked out on each access
assert (host, parts.port) == ('example.com', 8080)
assert urlunsplit(parts) == url  # O(n)

# urlparse also separates ;params from the last path segment
assert urlparse(url).params == 'v=1'  # O(n)

base = 'https://example.com/docs/guide/'
assert urljoin(base, '../api/reference.html') == 'https://example.com/docs/api/reference.html'
assert urljoin(base, '/other') == 'https://example.com/other'  # O(n)

stripped, fragment = urldefrag(url)  # O(n)
assert fragment == 'frag' and not stripped.endswith('#frag')
```

### Splitting Is Cached

On Python 3.11+, `urlsplit()` keeps a bounded cache of recent results, and passing the same string
object again returns the cached tuple in O(1). Python 3.10 caches too, but scans the URL before it
looks. `urlparse()` builds a new result every time.

```python
from urllib.parse import urlsplit, urlparse

url = 'https://example.com/path?query=1#frag'

first = urlsplit(url)   # O(n)
second = urlsplit(url)  # O(1) on Python 3.11+
assert first is second

assert urlparse(url) is not urlparse(url)  # O(n) each time
```

## Query Strings

### Fields Cost More Than Characters

`urlencode()` and `parse_qsl()` do fixed work for every field on top of their pass over the
characters, which is why both carry f. On an untrusted query, `max_num_fields` counts the
separators and raises before any field is built.

```python
from urllib.parse import urlencode, parse_qs, parse_qsl

query = urlencode({'name': 'Alice', 'city': ['NYC', 'LA']}, doseq=True)  # O(n + f)
assert query == 'name=Alice&city=NYC&city=LA'

assert parse_qs(query) == {'name': ['Alice'], 'city': ['NYC', 'LA']}  # O(n + f)
assert parse_qsl(query)[1] == ('city', 'NYC')

# Only the separator divides fields - ';' stays inside a value
assert parse_qsl('a=1;b=2') == [('a', '1;b=2')]

try:
    parse_qsl(query, max_num_fields=2)
except ValueError as error:
    assert 'Max number of fields exceeded' in str(error)
else:
    raise AssertionError('three fields passed max_num_fields=2')
```

### Quoting

```python
from urllib.parse import quote, quote_plus, unquote, unquote_plus

text = 'hello world & stuff'

assert quote(text) == 'hello%20world%20%26%20stuff'  # O(n)
assert quote_plus(text) == 'hello+world+%26+stuff'   # O(n)
assert unquote(quote(text)) == text                  # O(n)
assert unquote_plus(quote_plus(text)) == text        # O(n)

# '/' is safe by default, so a path keeps its structure
assert quote('/a b/c') == '/a%20b/c'
```

## Opening URLs

### Opening Does Not Read the Body

`urlopen()` returns as soon as the final response's status and headers are in, for `http:`,
`https:`, `file:` and `ftp:` alike. The body is paid for when it is read, and `read(size)` or iterating the response
keeps memory to one chunk or one line. A `data:` URL is the exception: its payload is decoded in
full before `urlopen()` returns.

```python
import pathlib
import tempfile
from urllib.request import urlopen, pathname2url

with tempfile.TemporaryDirectory() as folder:
    path = pathlib.Path(folder) / 'page.txt'
    path.write_text('first line\nsecond line\n')
    url = 'file:' + pathname2url(str(path))  # O(n)

    with urlopen(url) as response:  # O(n + h) - the file is opened, not read
        assert response.headers['Content-Length'] == '23'
        assert response.read(5) == b'first'  # O(size)

    with urlopen(url) as response:
        lines = [line for line in response]  # O(b) time, one line at a time
    assert lines == [b'first line\n', b'second line\n']

# data: URLs are decoded before urlopen returns - O(n) time and space
with urlopen('data:,hello%20world') as response:
    assert response.read() == b'hello world'
```

### Building a Request

A `Request` splits its URL when it is built, so the parts are available before anything is sent.
Header names are stored `capitalize()`d, and the lookups are exact.

```python
from urllib.parse import urlencode
from urllib.request import Request

body = urlencode({'username': 'alice'}).encode()  # O(n + f)
request = Request(
    'https://example.com/login?next=/home',
    data=body,
    headers={'User-Agent': 'MyBot/1.0'},
)  # O(n + m)

assert (request.type, request.host) == ('https', 'example.com')  # O(1)
assert request.selector == '/login?next=/home'
assert request.get_method() == 'POST'  # data makes it a POST

assert request.has_header('User-agent')      # O(1)
assert not request.has_header('User-Agent')  # stored capitalize()d
assert request.header_items() == [('User-agent', 'MyBot/1.0')]  # O(m)
```

### Handlers Run on Every Request

An opener is a list of handlers. Each request passes through every processor registered for its
scheme, and openers are tried until one answers. A cookie processor checks every domain in its jar,
and a redirect or an authentication challenge repeats the round trip. `HTTPPasswordMgrWithPriorAuth`
saves that repeat by sending basic credentials with the first request.

```python
from urllib.request import (
    HTTPBasicAuthHandler,
    HTTPCookieProcessor,
    HTTPPasswordMgrWithPriorAuth,
    Request,
    build_opener,
)

manager = HTTPPasswordMgrWithPriorAuth()
manager.add_password(None, 'https://example.com/', 'alice', 'secret', is_authenticated=True)
auth = HTTPBasicAuthHandler(manager)

opener = build_opener(auth, HTTPCookieProcessor())  # O(h²) worst case, once
assert auth in opener.handlers

# The credentials go out with the request itself, so a 401 never has to be answered
request = auth.http_request(Request('https://example.com/private'))  # O(u·n)
assert request.get_header('Authorization') == 'Basic YWxpY2U6c2VjcmV0'
```

## Errors

`HTTPError` is raised for a non-2xx response that no handler resolves, and it is also that response: its status, headers
and body are all there, and reading the body costs O(b) like any other.

```python
import email.message
import io
from urllib.error import HTTPError, URLError

error = HTTPError(
    'https://example.com/missing', 404, 'Not Found', email.message.Message(),
    io.BytesIO(b'no such page'),
)

try:
    raise error
except HTTPError as caught:  # before URLError: it is the subclass
    assert (caught.code, caught.reason) == (404, 'Not Found')  # O(1)
    assert caught.read() == b'no such page'  # O(b)
except URLError:
    raise AssertionError('HTTPError was not caught first')
else:
    raise AssertionError('nothing was raised')

assert issubclass(HTTPError, URLError) and issubclass(URLError, OSError)
```

## Downloading to a File

`urlretrieve()` copies the body in fixed-size blocks, so memory stays flat however large the
download is. With no `filename` it writes a temporary file that stays until `urlcleanup()`, except
for a `file:` URL, which gets its own path back without a copy.

```python
import os
import pathlib
import tempfile
from urllib.request import urlretrieve, urlcleanup, pathname2url

with tempfile.TemporaryDirectory() as folder:
    source = pathlib.Path(folder) / 'source.txt'
    source.write_text('body')
    url = 'file:' + pathname2url(str(source))

    copy = pathlib.Path(folder) / 'copy.txt'
    filename, headers = urlretrieve(url, str(copy))  # O(n + h + b), O(n) memory
    assert copy.read_text() == 'body'

    local, headers = urlretrieve(url)  # no filename: no copy is made
    assert os.path.samefile(local, source)

temporary, headers = urlretrieve('data:,body')  # a temporary file
assert os.path.exists(temporary)
urlcleanup()  # O(k)
assert not os.path.exists(temporary)
```

## robots.txt

`parse()` is one pass over the file. A lookup finds the group for the agent, O(g), then checks the
URL against that group's rules. Nothing is allowed until the file has been read or parsed.

```python
from urllib.robotparser import RobotFileParser

robots = RobotFileParser('https://example.com/robots.txt')  # O(n) - nothing is fetched
assert robots.can_fetch('mybot', 'https://example.com/') is False  # not read yet

robots.parse([
    'User-agent: mybot',
    'Crawl-delay: 5',
    'Disallow: /private',
    '',
    'User-agent: *',
    'Disallow: /',
    'Sitemap: https://example.com/sitemap.xml',
])  # O(s)

assert robots.can_fetch('mybot', 'https://example.com/public/page')  # O(g + n·(r + 1))
assert not robots.can_fetch('mybot', 'https://example.com/private/page')
assert not robots.can_fetch('otherbot', 'https://example.com/public/page')
assert robots.crawl_delay('mybot') == 5  # O(g)
assert robots.site_maps() == ['https://example.com/sitemap.xml']  # O(1)
```

## Common Patterns

### Changing One Query Parameter

```python
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

url = 'https://example.com/search?q=python&page=1'

parts = urlsplit(url)                  # O(n)
params = dict(parse_qsl(parts.query))  # O(n + f)
params['page'] = '2'
rebuilt = urlunsplit(parts._replace(query=urlencode(params)))  # O(n + f)

assert rebuilt == 'https://example.com/search?q=python&page=2'
```

## Performance Best Practices

✅ **Do**:

- Read a large response with `read(size)` or `shutil.copyfileobj()`, so memory follows the chunk
  rather than the body
- Pass `max_num_fields` to `parse_qs()` and `parse_qsl()` on an untrusted query
- Build an opener once and install or reuse it, rather than per request
- Use `HTTPPasswordMgrWithPriorAuth` with `is_authenticated=True` when the server always asks for
  basic credentials, to save a round trip per request
- Read `hostname` and `port` once outside a loop; each access re-parses `netloc`

❌ **Avoid**:

- `response.read()` on a download of unknown size
- Iterating the lines of a response that may have no line breaks: each line is held whole
- A cookie jar that only grows: every request checks every domain in it
- A `data:` URL for a large payload - it is decoded in full before `urlopen()` returns
- Repeating a user-agent across many groups in `robots.txt` - merging them is quadratic on the
  releases that merge

## Version Notes

- **Python 3.11+**: A repeated `urlsplit()` of the same string is a cache hit, O(1); 3.10 caches
  the result too but scans the URL first
- **Python 3.11+**: `HTTPRedirectHandler` follows 308 redirects
- **Python 3.13+**: `urlopen()` no longer takes `cafile`, `capath` or `cadefault`; pass an
  `ssl.SSLContext` as `context`
- **Python 3.14+**: `URLopener` and `FancyURLopener` are removed
- **Python 3.13.14+ and 3.14.5+**: `RobotFileParser` follows RFC 9309: `*` and a trailing `$` in
  rules, the longest matching rule wins with `Allow` taking ties, and groups naming the same agent
  are merged. Earlier releases, and 3.10 to 3.12, match literal prefixes and use the first group
  and the first rule that apply

## Related Modules

- **[http](http.md)** - `http.client` is the connection `HTTPHandler` sends through, and
  `http.cookiejar` the jar `HTTPCookieProcessor` checks on every request
- **[ssl](ssl.md)** - the `context` that `urlopen()` and `HTTPSHandler` take
- **[re](re.md)** - the matching cost of a wildcard `robots.txt` rule
- **[tempfile](tempfile.md)** - where `urlretrieve()` puts a download with no `filename`
