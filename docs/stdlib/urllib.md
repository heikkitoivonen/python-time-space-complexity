# urllib Module Complexity

The `urllib` package splits into five modules: `urllib.parse` for taking URLs apart and putting
them back together, `urllib.request` for fetching them, `urllib.error` for the exceptions that
raises, `urllib.response` for the file-like objects it returns, and `urllib.robotparser` for
`robots.txt`.

The tables describe local processing and memory use. Network and filesystem waits are additional;
`data:` URLs are decoded entirely in process.

## Complexity Reference

### urllib.parse

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.parse.urlsplit(url)` | O(n) | O(n) | n = URL length; cache misses. A cache hit with the same `str` object is O(1) time and space on Python 3.11+; Python 3.10 still scans the URL |
| `urllib.parse.urlparse(url)` | O(n) | O(n) | n = URL length; splits, then rebuilds a six-field result, so only the split half is memoized |
| `urllib.parse.urlunsplit(parts)`, `urllib.parse.urlunparse(parts)` | O(n) | O(n) | n = combined length of the parts |
| `urllib.parse.urljoin(base, url)` | O(n) | O(n) | n = combined length; resolving `..` walks the path segments |
| `urllib.parse.urldefrag(url)` | O(n) | O(n) | n = URL length; splits off everything after `#` |
| `urllib.parse.quote(string)`, `urllib.parse.quote_plus(string)`, `urllib.parse.quote_from_bytes(bytes)` | O(n) | O(n) | n = input length; per-character table lookup, with the table built once per `safe` set |
| `urllib.parse.unquote(string)`, `urllib.parse.unquote_plus(string)`, `urllib.parse.unquote_to_bytes(string)` | O(n) | O(n) | n = input length |
| `urllib.parse.urlencode(query)` | O(n + t) | O(n + t) | n = fields, t = total characters; the per-field work dominates unless the values are long |
| `urllib.parse.parse_qsl(qs)`, `urllib.parse.parse_qs(qs)` | O(n + t) | O(n + t) | n = fields, t = query length; `max_num_fields` caps n, and only `&` separates by default |
| `urllib.parse.SplitResult`, `urllib.parse.ParseResult`, `urllib.parse.DefragResult` | O(1) | O(1) | Named tuples; `.geturl()` is O(n) because it rebuilds the string |
| `urllib.parse.SplitResultBytes`, `urllib.parse.ParseResultBytes`, `urllib.parse.DefragResultBytes` | O(1) | O(1) | The same shapes over `bytes` |

### urllib.request

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.request.urlopen(url)` (HTTP(S), `file:`, FTP) | O(1) + I/O wait | O(1) | Relative to body size, with fixed request metadata; returns a stream without buffering the whole body |
| `urllib.request.urlopen(url)` (`data:`) | O(n) | O(n) | n = encoded URL length; decodes the entire payload before returning |
| `urllib.request.urlretrieve(url, filename)` | O(n) + I/O wait | O(1) streaming; O(n) for `data:` | n = response size (encoded URL length for `data:`); chunked copying adds to the scheme's opening cost |
| `urllib.request.urlcleanup()` | O(k) | O(1) | k = temporary files `urlretrieve` left behind |
| `urllib.request.Request(url, ...)` | O(n) | O(n) | n = URL and header lengths; the URL is split once here |
| `urllib.request.build_opener(*handlers)` | O(h²) worst; O(h log h) for nondecreasing priorities | O(h) | h = handlers, with a fixed number of methods per handler; sorted insertion shifts existing handlers |
| `urllib.request.install_opener(opener)` | O(1) | O(1) | Installs an already-built opener |
| `urllib.request.OpenerDirector`, `urllib.request.BaseHandler` | O(h) | O(h) | Dispatch walks the handlers registered for the scheme, in order |
| `urllib.request.HTTPHandler`, `urllib.request.HTTPSHandler`, `urllib.request.FileHandler`, `urllib.request.DataHandler`, `urllib.request.FTPHandler`, `urllib.request.CacheFTPHandler`, `urllib.request.UnknownHandler` | O(1) | O(1) | Construction only; the transfer is the network's or the filesystem's |
| `urllib.request.ProxyHandler(proxies)` | O(p) | O(p) | p = proxy entries, one bound method installed per scheme |
| `urllib.request.HTTPRedirectHandler`, `urllib.request.HTTPErrorProcessor`, `urllib.request.HTTPDefaultErrorHandler`, `urllib.request.HTTPCookieProcessor` | O(1) | O(1) | Per response; a redirect chain repeats the whole round trip |
| `urllib.request.AbstractBasicAuthHandler`, `urllib.request.HTTPBasicAuthHandler`, `urllib.request.ProxyBasicAuthHandler` | O(1) | O(1) | One extra round trip: the first request is sent unauthenticated |
| `urllib.request.AbstractDigestAuthHandler`, `urllib.request.HTTPDigestAuthHandler`, `urllib.request.ProxyDigestAuthHandler` | O(1) | O(1) | As above, plus one hash of the challenge |
| `urllib.request.HTTPPasswordMgr`, `urllib.request.HTTPPasswordMgrWithDefaultRealm`, `urllib.request.HTTPPasswordMgrWithPriorAuth` | O(u) | O(u) | u = stored URIs in the realm; a lookup compares the request path against each |
| `urllib.request.getproxies()` | O(e) | O(e) | e = environment variables, scanned for `*_proxy` |
| `urllib.request.pathname2url(path)`, `urllib.request.url2pathname(url)` | O(n) | O(n) | n = path length; quoting and unquoting |
| `urllib.request.URLopener`, `urllib.request.FancyURLopener` | O(1) | O(1) | Removed in Python 3.14; deprecated in favour of `OpenerDirector` long before that |

### urllib.error

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.error.URLError(reason)` | O(1) | O(1) | Wraps the underlying socket or protocol error |
| `urllib.error.HTTPError(url, code, msg, hdrs, fp)` | O(1) | O(1) | Also a response: it is readable, and reading the body is O(n) |
| `urllib.error.ContentTooShortError(message, content)` | O(1) | O(1) | Raised by `urlretrieve` when the download is short of `Content-Length` |

### urllib.response

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.response.addbase(fp)`, `urllib.response.addinfo(fp, headers)`, `urllib.response.addinfourl(fp, headers, url, code)` | O(1) | O(1) | Wrappers around an already-open stream; they add attributes, not buffering |
| `urllib.response.addclosehook(fp, closehook, *args)` | O(1) | O(1) | Runs one callback on close |
| `response.read()` | O(n) | O(n) | n = bytes read; `read(size)` bounds both |

### urllib.robotparser

`RobotFileParser` matches literal path prefixes: no supported version reads `*` or `$` in a rule,
so a pattern is compared as the characters it is written with. A repeated `User-agent` group does
not merge with the earlier one either — `can_fetch()` returns on the first entry that applies, and
a second group for the same agent is never consulted.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.robotparser.RobotFileParser().read()` | O(n) + round trip | O(n) | n = `robots.txt` size |
| `urllib.robotparser.RobotFileParser().parse(lines)` | O(l + t) | O(l + t) | l = lines, t = total input text; retained rules and directive values include their text, not just one record per line |
| `urllib.robotparser.RobotFileParser().can_fetch(agent, url)` | O(e·a + r·n) | O(n + a) | e = entries scanned before one applies, a = agent-name length, r = that entry's rules, n = URL length; the URL is normalized once and each rule is a prefix comparison against it |

## URL Parsing

### Parsing URLs

```python
from urllib.parse import urlparse

# Parse URL - O(n) where n = URL length
url = "https://user:pass@example.com:8080/path?query=1#fragment"
parsed = urlparse(url)  # O(len(url))

# Access components - O(1)
scheme   = parsed.scheme    # 'https'
netloc   = parsed.netloc    # 'user:pass@example.com:8080'
hostname = parsed.hostname  # 'example.com'
port     = parsed.port      # 8080
path     = parsed.path      # '/path'
query    = parsed.query     # 'query=1'
fragment = parsed.fragment  # 'fragment'
```

### Splitting Is Memoized

`urlsplit()` caches split results. On Python 3.11+, a cache hit with the same `str` object avoids
the URL scan and takes O(1) time. Python 3.10 scans before checking its cache, so a hit still takes
O(n) time. The cache is bounded; a stream of distinct URLs still needs parsing.

```python
from urllib.parse import urlsplit, urlparse

url = "https://example.com/path?query=1#frag"

first = urlsplit(url)   # O(n)
second = urlsplit(url)  # O(1) on Python 3.11+; O(n) on 3.10
assert first is second

# urlparse builds a fresh six-field result even when urlsplit has a cache hit
assert urlparse(url) is not urlparse(url)

# Reconstruct - O(n)
from urllib.parse import urlunsplit
assert urlunsplit(first) == url
```

## Query String Handling

### Encoding Query Parameters

Both `urlencode()` and `parse_qsl()` charge per field, not per character: a thousand short fields
cost far more than ten long ones carrying the same number of characters.

```python
from urllib.parse import urlencode

# Encode parameters - O(n + t), n = fields, t = total characters
params = {'name': 'Alice', 'age': '30', 'city': 'NYC'}
query_string = urlencode(params)
assert query_string == 'name=Alice&age=30&city=NYC'

# Repeated keys need doseq, or the list is encoded as its repr
multi = urlencode({'city': ['NYC', 'LA']}, doseq=True)  # O(n + t)
assert multi == 'city=NYC&city=LA'

# Use in URL - O(len(query_string))
url = f"https://example.com/search?{query_string}"
```

### Quoting and Unquoting

```python
from urllib.parse import quote, unquote, quote_plus

# Encode special characters - O(n)
text = "hello world & stuff"
encoded = quote(text)  # O(len(text))
assert encoded == 'hello%20world%20%26%20stuff'

# With + for spaces - O(n)
plus = quote_plus(text)  # O(len(text))
assert plus == 'hello+world+%26+stuff'

# Decode - O(n)
assert unquote(encoded) == text
```

### Parsing Query Strings

```python
from urllib.parse import parse_qs, parse_qsl

# Parse query string - O(n + t), n = fields, t = query length
query = "name=Alice&age=30&city=NYC&city=LA"
params = parse_qs(query)
assert params == {'name': ['Alice'], 'age': ['30'], 'city': ['NYC', 'LA']}

# As list of tuples - the same walk without the grouping
assert parse_qsl(query)[0] == ('name', 'Alice')

# Only '&' separates by default, so ';' stays inside the value
assert parse_qsl("a=1;b=2") == [('a', '1;b=2')]

# max_num_fields bounds n before the work is done
try:
    parse_qsl(query, max_num_fields=2)
except ValueError as error:
    assert 'Max number of fields exceeded' in str(error)
```

## Fetching URLs

### Basic URL Fetching

For HTTP(S), `urlopen()` returns after reading the response headers, without buffering the whole
body. With request metadata fixed, opening uses O(1) space relative to body size, while reading the
whole body uses O(n). The `file:` and FTP handlers also return streams. A `data:` URL instead
decodes its entire payload before returning, taking O(n) time and space in the encoded URL length.

```python
from urllib.request import urlopen

# Open URL - returns after the headers, not the body
try:
    with urlopen('https://example.com') as response:  # O(1) plus the round trip
        # Metadata is available before any of the body is read - O(1)
        status = response.status  # 200
        headers = response.headers  # dict-like

        content = response.read()  # O(n) - n = response size
except Exception as e:
    print(f"Error: {e}")
```

### Reading Response Content

```python
from urllib.request import urlopen

# Fetch and read HTML - O(n)
with urlopen('https://example.com') as response:
    html = response.read()  # O(n) - n = HTML size
    text = html.decode('utf-8')  # O(n) - decoding
```

### Line-by-Line Reading

```python
from urllib.request import urlopen

def process_line(line):
    return line.strip()

# Stream content line-by-line - O(1) memory per line
with urlopen('https://example.com') as response:
    for line in response:  # O(1) memory, O(line_size) time per line
        process_line(line)
```

## Working with Requests

### Custom Headers

```python
from urllib.request import Request, urlopen

# Create request with headers - O(n), and the URL is split here
headers = {
    'User-Agent': 'MyBot/1.0',
    'Accept': 'text/html'
}
req = Request('https://example.com', headers=headers)  # O(n)

# Fetch with custom request
with urlopen(req) as response:  # O(1) plus the round trip
    content = response.read()  # O(n)
```

### POST Requests

```python
from urllib.request import Request, urlopen
from urllib.parse import urlencode

# Prepare POST data - O(n + t)
data = {'username': 'alice', 'password': 'secret'}
encoded_data = urlencode(data).encode('utf-8')  # O(n + t)

# Create POST request - O(n)
req = Request('https://example.com/login',
              data=encoded_data,  # POST body
              method='POST')  # O(n)

# Send request
with urlopen(req) as response:  # O(1) plus the round trip
    result = response.read()  # O(n)
```

## Error Handling

### Handling HTTP Errors

`HTTPError` is a response as well as an exception, so its body is readable and reading it costs
the same O(n) as reading a successful one.

```python
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

try:
    with urlopen('https://example.com/notfound') as response:
        content = response.read()
except HTTPError as e:
    print(f"HTTP Error: {e.code}")  # 404, etc.
    body = e.read()  # O(n) - the error page, if the server sent one
except URLError as e:
    print(f"URL Error: {e.reason}")  # Network error
```

## Advanced URL Operations

### URL Joining

```python
from urllib.parse import urljoin

# Join base URL with relative path - O(n)
base = 'https://example.com/docs/guide/'
relative = '../api/reference.html'
assert urljoin(base, relative) == 'https://example.com/docs/api/reference.html'

# An absolute path replaces the whole path
assert urljoin(base, '/other/page.html') == 'https://example.com/other/page.html'

# An absolute URL replaces everything
assert urljoin(base, 'https://other.example/x') == 'https://other.example/x'
```

### Splitting URLs

```python
from urllib.parse import urlsplit, urlunsplit, urldefrag

# Split URL into parts - O(n)
url = 'https://example.com/path?query=1#frag'
parts = urlsplit(url)  # O(n)
assert tuple(parts) == ('https', 'example.com', '/path', 'query=1', 'frag')

# Reconstruct URL - O(n)
assert urlunsplit(parts) == url

# Drop just the fragment - O(n)
stripped, fragment = urldefrag(url)
assert (stripped, fragment) == ('https://example.com/path?query=1', 'frag')
```

## Local and Data URLs

Not every scheme goes over the network. `file:` and `data:` URLs are served by handlers that are
already installed, which makes them the cheapest way to see what `urlopen()` does.

```python
import tempfile, pathlib
from urllib.request import urlopen, pathname2url

# data: URLs are decoded before opening returns - O(n) time and space
with urlopen('data:,hello%20world') as response:
    assert response.read() == b'hello world'

# file: URLs open the file without reading it - O(1) until you read
with tempfile.TemporaryDirectory() as folder:
    path = pathlib.Path(folder) / 'page.txt'
    path.write_text('body')
    with urlopen('file:' + pathname2url(str(path))) as response:  # O(1)
        assert response.read() == b'body'  # O(n)
```

## Performance Considerations

### Batch Fetching

```python
from urllib.request import urlopen
import concurrent.futures

# Sequential fetching - one round trip after another
urls = ['https://example.com/1', 'https://example.com/2']
for url in urls:
    with urlopen(url) as response:
        content = response.read()  # O(n)

# Parallel fetching with threads - the round trips overlap
def fetch(url):
    with urlopen(url) as response:
        return response.read()

with concurrent.futures.ThreadPoolExecutor() as executor:
    contents = list(executor.map(fetch, urls))
```

### Caching

```python
from urllib.request import urlopen

cache = {}

def fetch_cached(url):
    """Fetch URL with simple caching - O(n) first time, O(1) cached"""
    if url in cache:
        return cache[url]  # O(1)

    with urlopen(url) as response:
        cache[url] = response.read()  # O(n)
    return cache[url]

content1 = fetch_cached('https://example.com')  # O(n)
content2 = fetch_cached('https://example.com')  # O(1)
```

## Related Modules

- **[http.client](http.md)** - Lower-level HTTP client
- **[json](json.md)** - Parse JSON responses

## Best Practices

✅ **Do**:

- Use context managers (`with`) for proper cleanup
- Always specify encoding when decoding bytes
- Handle URLError and HTTPError exceptions
- Use appropriate Content-Type headers for POST
- Validate and sanitize URLs before fetching
- Use query parameters via urlencode, not string concatenation
- Bound untrusted query strings with `max_num_fields`

❌ **Avoid**:

- Fetching untrusted URLs without validation
- Ignoring SSL certificate errors (security risk)
- Manual URL string construction (use urlencode)
- Reading a large response whole when you can stream it
- Building a query out of many tiny fields when a few larger ones will do
- Decoding responses without checking encoding
