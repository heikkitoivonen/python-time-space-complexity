# http Module Complexity

The `http` package is a top-level module and four submodules over one protocol.
`http` itself holds the status and method enumerations, which are lookup
tables. `http.client` speaks HTTP to a server, `http.server` answers it, and
`http.cookies` and `http.cookiejar` carry state between the two - the first
formatting and parsing a header, the second deciding which cookies a request
may carry.

The bounds below describe local processing and memory. Connecting, sending and
receiving add a round trip that no bound here covers. Most of the rest is
linear in the bytes handled; what is worth knowing is where it is not - where
a cost follows the number of stored domains rather than the bytes, where a
peer cannot drive the work past a fixed size, and where an operation holds the
whole input in memory rather than streaming it.

## Complexity Reference

Size variables: n = bytes or characters of the text an operation reads or
writes; b = bytes of a request or response body; h = headers on one message; v
= characters in one header value; B = `blocksize`, the chunk a body is streamed
in, 8192 by default; i = `100 Continue` responses skipped before a real one; k
= entries in a directory; s = components in a request path; D = a served
directory's own path length; o = a CGI script's output; c = cookies in one
cookie string, or stored in a jar; L = the longest name in a set of them; d =
distinct domains in a jar; P = paths under the domains a lookup accepted; a =
cookies under the paths it accepted; m = cookies selected for one request; e =
levels a jar keeps after their cookies were cleared; w = the widest level a jar
walk materializes; g = blocked or allowed domains configured on a policy.

The body bounds below are in decoded body bytes, for a `bytes` or readable
body and an identity-encoded response. A chunked transfer adds its framing and
any trailer block, and an iterable body supplies chunks of its own size rather
than `blocksize` ones; neither is priced here.

Header parsing is bounded rather than linear: `http.client` rejects a header
line over 65,536 bytes, and rejects a header block once it has collected more
than 100 lines. The terminating blank line is one of them, so 99 headers is the
most that parses: 100 headers plus the terminator is 101 lines. Both h and v
are therefore capped for anything it reads. The cap is per block, not
per call: `getresponse()` skips `100 Continue` responses first, each with a
header block of its own, until a status that is not 100 arrives - a `103`, like
any other, ends the loop and becomes the response. Patch releases across the
supported branches also cap the status lines read at 100, so at most 99 interim
responses precede the final one and a peer drives a bounded multiple of one
block; where that cap is absent they are read without limit. Nothing bounds the
headers an application sends, or the body in either direction.

### HTTPStatus

An `IntEnum` in `http`, built once at import.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTTPStatus.OK`, `HTTPStatus.NOT_FOUND`, any member by name | O(1) | O(1) | Class attribute |
| `HTTPStatus(code)` | O(1) | O(1) | Indexes the value-to-member dict and returns the existing member; an unknown code raises ValueError |
| `HTTPStatus.phrase`, `HTTPStatus.description` | O(1) | O(1) | The short reason phrase and the longer sentence; both are stored on the member |
| `HTTPStatus.is_informational`, `HTTPStatus.is_success`, `HTTPStatus.is_redirection`, `HTTPStatus.is_client_error`, `HTTPStatus.is_server_error` | O(1) | O(1) | Python 3.12+; one range comparison |

### HTTPMethod

A `StrEnum` in `http`, Python 3.11+.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTTPMethod.GET`, any member by name | O(1) | O(1) | Class attribute; the member is also the method string |
| `HTTPMethod(name)` | O(1) | O(1) | As for `HTTPStatus`, over the method names |
| `HTTPMethod.description` | O(1) | O(1) | Stored on the member |

### http.client functions and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `http.client.parse_headers(fp)` | O(n) | O(n) | n = header bytes, capped at 99 headers of 65,536 bytes; reads to the blank line, which counts toward the limit, and hands the block to the `email` parser. Raises `LineTooLong` or `HTTPException` at those limits |
| `http.client.responses` | O(1) | O(1) | Status code to reason phrase; a dict lookup, not a scan |

### HTTPConnection and HTTPSConnection

`HTTPSConnection` adds a TLS handshake to `connect()`; every other bound is its
parent's.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTTPConnection(host, port)` | O(n) | O(n) | n = host string length, which is validated and split from any `:port`; opens nothing |
| `HTTPConnection.connect()` | O(1) + round trip | O(1) | Name resolution and the TCP connect, plus the TLS handshake for `HTTPSConnection` |
| `HTTPConnection.request(method, url, body, headers)` | O(q + b) | O(q + B), or O(q + b) for a `str` body | q = the serialized request line and headers, method, URL, header names and values together. The space is that block plus one body chunk: a `bytes` body reaches the socket without a copy, an object with `read()` is streamed in `blocksize` chunks, and a `str` body is encoded whole first |
| `HTTPConnection.putrequest(method, url)` | O(n) | O(n) | n = method and URL length; appended to the header buffer, not sent |
| `HTTPConnection.putheader(header, *values)` | O(n) | O(n) | n = the name and all of its values; also buffered |
| `HTTPConnection.endheaders(message_body)` | O(q + b) | O(q + B) | Joins the buffered lines and sends them in one write, then the body, chunked as for `send()` |
| `HTTPConnection.send(data)` | O(b) | O(B) for a readable; O(1) for `bytes` | A file-like `data` is read and sent in `blocksize` chunks, so the memory a send needs does not grow with the body. `bytes` are passed to the socket as they are, with no copy. An iterable `data` is sent one item at a time, at whatever size it yields |
| `HTTPConnection.getresponse()` | O(i·n) | O(n) | n = one status line and header block, under the caps above; i = the `100 Continue` responses skipped first, itself capped at 99 where `_MAXINTERIMRESPONSES` exists. Returns before the body is read |
| `HTTPConnection.close()` | O(1) | O(1) | Closes the socket and any unread response |
| `HTTPConnection.set_tunnel(host, port, headers)` | O(n) | O(n) | n = the target host and the headers given; parsed and recorded here, with the round trip at `connect()` |
| `HTTPConnection.get_proxy_response_headers()` | O(n) | O(n) | Python 3.12+; n = the CONNECT response's header bytes, which it parses afresh on every call rather than caching. None when no tunnel was set |
| `HTTPConnection.set_debuglevel(level)` | O(1) | O(1) | Above 0, every send and header line is printed, which dominates the transfer |
| `HTTPConnection.blocksize` | O(1) | O(1) | The chunk size above; raising it trades memory for fewer writes |
| `HTTPConnection.default_port`, `HTTPConnection.auto_open`, `HTTPConnection.debuglevel` | O(1) | O(1) | Class attributes: 80, or 443 for `HTTPSConnection`; whether a send reconnects a closed connection; the class-wide default behind `set_debuglevel` |

### HTTPResponse

A readable stream over the connection, returned by `getresponse()`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTTPResponse.read()` | O(b) | O(b) | Reads the rest of the body into one `bytes`. b is decoded body bytes; a chunked response also reads its framing, and any trailer block after it |
| `HTTPResponse.read(amt)` | O(amt) | O(amt) | Bounds both |
| `HTTPResponse.readinto(buffer)` | O(amt) | O(1) | amt = `len(buffer)`; fills a buffer the caller already owns, allocating nothing for the data |
| `HTTPResponse.getheader(name, default)` | O(h + m·v) | O(m·v) | m = repeats of that header. Scans the stored names, lowercasing each to compare, then joins the matches with `, `; long header names add to the scan |
| `HTTPResponse.getheaders()` | O(h + n) | O(h + v) | n = header bytes; builds the list of pairs over the existing strings rather than copying them, with the same per-value scan |
| `HTTPResponse.status`, `HTTPResponse.reason`, `HTTPResponse.version`, `HTTPResponse.headers`, `HTTPResponse.msg` | O(1) | O(1) | Parsed from the status line and header block before `getresponse()` returned. `headers` and `msg` are the same `HTTPMessage` |
| `HTTPResponse.url`, `HTTPResponse.geturl()` | O(1) | O(1) | Neither is populated by `http.client`: the constructor accepts a `url` argument and discards it without assigning the attribute, so `geturl()` raises AttributeError on a response built here. `urllib.request` sets `response.url` itself afterwards, which is where the accessor works |
| `HTTPResponse.getcode()`, `HTTPResponse.info()` | O(1) | O(1) | The `urllib.response` spelling of `status` and `headers` |
| `HTTPResponse.readline(limit)`, `HTTPResponse.read1(n)` | O(limit) / O(n) | same | The buffered-reader interface over the body, each bounded by its argument |
| `HTTPResponse.peek(n)` | O(r) | O(r) | r = bytes actually returned. n is only a hint to the underlying buffered stream, which may return more or fewer, and may refill an empty buffer from the socket first. Nothing is consumed |
| `HTTPResponse.close()`, `HTTPResponse.isclosed()`, `HTTPResponse.readable()`, `HTTPResponse.flush()` | O(1) | O(1) | Closing does not drain an unread body; the connection cannot be reused until it is |
| `HTTPResponse.fileno()` | O(1) | O(1) | Delegates to the stream the connection made over the socket |
| `HTTPResponse.debuglevel` | O(1) | O(1) | As for the connection |

### HTTPMessage

The headers of a request or response. A subclass of `email.message.Message`,
so [the `email` page's bounds](email.md) apply; the caps above keep h and v
small for anything `http.client` parsed.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTTPMessage[name]`, `HTTPMessage.get(name)` | O(h + v) | O(v) | A linear scan of the names, not a dict lookup, however few headers there are; each is lowercased to compare, so long names add to it. The value handed back is the stored string itself, but the policy scans it for undecodable bytes first, and that scan is the transient O(v) |
| `HTTPMessage.get_all(name)` | O(h + m·v) | O(m + v) | m = repeats of that header, collected into a list of the stored strings, each scanned as above |
| `HTTPMessage.keys()` | O(h) | O(h) | Duplicates included |
| `HTTPMessage.items()` | O(h + n) | O(h + v) | n = header bytes: each value is scanned for undecodable bytes, then handed back as it is; the scan's transient copy is the v |
| `HTTPMessage.getallmatchingheaders(name)` | O(h) | O(h) | Builds the full list of header names and then matches each against a pattern ending in a colon, which none of them carry - so it returns an empty list for every name, having allocated that list of names first. Use `get_all()` |
| `HTTPMessage.defects`, `HTTPMessage.preamble`, `HTTPMessage.epilogue` | O(1) | O(1) | Inherited from `email`; `defects` records what the parser had to forgive |

### http.client exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `http.client.HTTPException`, `http.client.NotConnected`, `http.client.InvalidURL`, `http.client.UnknownProtocol`, `http.client.UnknownTransferEncoding`, `http.client.UnimplementedFileMode`, `http.client.BadStatusLine`, `http.client.LineTooLong`, `http.client.RemoteDisconnected`, `http.client.ImproperConnectionState`, `http.client.CannotSendRequest`, `http.client.CannotSendHeader`, `http.client.ResponseNotReady` | O(1) | O(1) | Raising and constructing only |
| `http.client.IncompleteRead(partial, expected)` | O(1) | O(r) | r = bytes already read, which it keeps in `.partial`, so catching it near a large truncated body retains that body |

### HTTPServer, ThreadingHTTPServer, HTTPSServer and ThreadingHTTPSServer

`socketserver` subclasses. `HTTPSServer` and `ThreadingHTTPSServer` are Python
3.14+ and wrap each accepted connection in TLS; the threading variants give
each connection a thread rather than serving them one at a time.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTTPServer(address, handler)`, `HTTPSServer(...)`, `ThreadingHTTPServer(...)`, `ThreadingHTTPSServer(...)` | O(1) + a name lookup | O(1) | Binding resolves the host name once, for `server_name` |
| `HTTPServer.server_name`, `HTTPServer.server_port` | O(1) | O(1) | Recorded at bind time |
| Serving one request | The handler's cost | O(n) + one thread | n = the request's headers; the handler rows below give the rest. A threading server's memory grows with connections held open, not with requests served |

### BaseHTTPRequestHandler

One instance per connection. Response headers are buffered and flushed
together, so the count of writes does not grow with the count of headers.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseHTTPRequestHandler.handle()` | The sum of the requests it serves | O(1) beyond the request in flight | Loops over keep-alive requests on the connection; nothing accumulates across them |
| `BaseHTTPRequestHandler.handle_one_request()` | O(n) + the `do_*` method | O(n) + the `do_*` method | n = request line and header bytes, under the same caps as the client. It then dispatches to `do_GET` and friends and flushes, so serving a large file - or building a directory listing, and holding it - is inside this call, not after it |
| `BaseHTTPRequestHandler.send_response(code, message)`, `BaseHTTPRequestHandler.send_response_only(code, message)` | O(v) | O(v) | Buffered; `send_response` also logs and adds the Server and Date headers |
| `BaseHTTPRequestHandler.send_header(key, value)` | O(v) | O(v) | Buffered |
| `BaseHTTPRequestHandler.end_headers()`, `BaseHTTPRequestHandler.flush_headers()` | O(v·h) | O(v·h) | Joins the buffer and writes it once |
| `BaseHTTPRequestHandler.send_error(code, message, explain)` | O(v·h + e) | O(v·h + e) | e = the generated body's length, `error_message_format` filled in; suppressed for codes with no body |
| `BaseHTTPRequestHandler.handle_expect_100()` | O(1) | O(1) | Sends the interim 100 response |
| `BaseHTTPRequestHandler.log_request(code, size)`, `BaseHTTPRequestHandler.log_error(format, *args)`, `BaseHTTPRequestHandler.log_message(format, *args)` | O(n) | O(n) | n = the formatted line, which is built in memory and then written to `sys.stderr` |
| `BaseHTTPRequestHandler.version_string()`, `BaseHTTPRequestHandler.date_time_string(timestamp)`, `BaseHTTPRequestHandler.log_date_time_string()`, `BaseHTTPRequestHandler.address_string()` | O(1) | O(1) | Formatting from values already held; `address_string` returns the stored client address without a reverse lookup |
| `BaseHTTPRequestHandler.headers`, `BaseHTTPRequestHandler.path`, `BaseHTTPRequestHandler.command`, `BaseHTTPRequestHandler.requestline`, `BaseHTTPRequestHandler.request_version`, `BaseHTTPRequestHandler.client_address`, `BaseHTTPRequestHandler.server`, `BaseHTTPRequestHandler.close_connection` | O(1) | O(1) | Set while the request line was parsed |
| `BaseHTTPRequestHandler.rfile`, `BaseHTTPRequestHandler.wfile` | O(1) | O(1) | The connection's streams; `rfile` is buffered and `wfile` is not, so each write reaches the socket |
| `BaseHTTPRequestHandler.protocol_version`, `BaseHTTPRequestHandler.server_version`, `BaseHTTPRequestHandler.sys_version`, `BaseHTTPRequestHandler.error_message_format`, `BaseHTTPRequestHandler.error_content_type`, `BaseHTTPRequestHandler.responses` | O(1) | O(1) | Class attributes. `responses` maps a status to its phrase and description; setting `protocol_version` to `HTTP/1.1` requires an accurate Content-Length on every response |

### SimpleHTTPRequestHandler

Serves files from `directory`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SimpleHTTPRequestHandler.do_GET()` | `send_head()` + O(b) | `send_head()` | Locates the file through `send_head()`, then copies it; the body is streamed, so b does not become memory |
| `SimpleHTTPRequestHandler.do_HEAD()` | `send_head()` | `send_head()` | The same lookup with the body dropped - for a directory the listing below is still built, then discarded |
| `SimpleHTTPRequestHandler.send_head()` | O(n·s), plus the listing for a directory | O(n), plus the listing | Translates the path, stats it, and for a directory tries each name in `index_pages` before falling back to `list_directory` - so a request naming a directory carries that row's k and L, not just this row's n and s |
| `SimpleHTTPRequestHandler.translate_path(path)` | O(n·s) | O(n) | n = path length, s = its components; unquotes and normalises, then joins the surviving components one at a time, recopying the prefix each time. Components that are not plain names are dropped, which is what stops a literal `..` climbing out of the root - it does not stop a symlink inside the root pointing outside it |
| `SimpleHTTPRequestHandler.list_directory(path)` | O(k·(L·log k + D) + n) | O(k·L + n) | k = entries, L = the longest name, D = the directory's own path, n = the request path, which is unquoted and escaped into the title and heading. Names are lowercased and compared, so a shared prefix costs L per comparison, and each entry's full path is rebuilt for the two stat calls that choose its `/` or `@` mark. The whole listing is built in memory before it is sent |
| `SimpleHTTPRequestHandler.guess_type(path)` | O(n) | O(n) | n = path length: the extension is split off and lowercased before the `extensions_map` and `mimetypes` lookups, which are themselves O(1). Unknown extensions fall back to `application/octet-stream` |
| `SimpleHTTPRequestHandler.copyfile(source, outputfile)` | O(b) | O(1) | Chunked copy |
| `SimpleHTTPRequestHandler.extensions_map`, `SimpleHTTPRequestHandler.index_pages`, `SimpleHTTPRequestHandler.server_version` | O(1) | O(1) | Class attributes; `index_pages` is Python 3.12+ |

### CGIHTTPRequestHandler

Deprecated since Python 3.13 and removed in Python 3.15.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `CGIHTTPRequestHandler.do_POST()` | The script's cost | O(1), or O(b + o) without fork | Answers with an error unless the path names a CGI directory. Where the platform can fork, the child reads the body from the socket itself and the parent holds nothing; otherwise the parent reads the body and collects the script's whole output, o, before forwarding it |
| `CGIHTTPRequestHandler.cgi_directories` | O(1) | O(1) | Path prefixes treated as scripts |

### BaseCookie and SimpleCookie

A `dict` of name to `Morsel`. `SimpleCookie` is `BaseCookie` with quoted
values.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseCookie()`, `SimpleCookie()` | O(1) | O(1) | With no argument |
| `BaseCookie(rawdata)`, `SimpleCookie(rawdata)` | `load()` | `load()` | A non-empty argument is loaded during construction, at that row's cost |
| `BaseCookie.load(rawdata)` | O(n) | O(n) | n = the header's length. The string is parsed into pending items and applied only once parsing finished, so a value the *parser* refuses leaves the object untouched. Two endings do not: junk the pattern cannot match ends the parse quietly and applies what came before it, and a name `Morsel.set` rejects raises `CookieError` part way through applying |
| `BaseCookie[name]` | O(1) | O(1) | Dict lookup |
| `BaseCookie[name] = value` | O(v) | O(v) | Encodes the value through `value_encode` |
| `BaseCookie.output(attrs, header, sep)` | O(c·L·log c + c·v) | O(c·v) | c = cookies held, L = the longest name, v = one rendered cookie's length; the items are sorted by name first, so output is alphabetical rather than in insertion order |
| `BaseCookie.js_output(attrs)` | O(c·L·log c + c·v) | O(c·v) | The same sorted content, each wrapped in a script element |
| `BaseCookie.value_encode(val)`, `BaseCookie.value_decode(val)`, `SimpleCookie.value_encode(val)`, `SimpleCookie.value_decode(val)` | O(v) | O(v) | `BaseCookie` passes the value through; `SimpleCookie` quotes and unquotes it |

### Morsel

One cookie: its value plus the reserved attributes.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Morsel()` | O(1) | O(1) | Every reserved key is created empty, so the key set is fixed and no accessor below grows with anything |
| `Morsel.set(key, val, coded_val)` | O(len(key) + v) | O(len(key)) | Checks the name against the reserved set, lowercasing it to do so, and against the legal-character set, and scans all three strings for control characters. The values are then stored by reference; the space is the lowercased name |
| `Morsel[attr] = value` | O(1) | O(1) | Only a reserved attribute; any other key raises `CookieError` |
| `Morsel.isReservedKey(K)` | O(len(K)) | O(len(K)) | Lowercases the key, then looks it up; the lookup is the O(1) part, and nothing here follows how many cookies exist |
| `Morsel.output(attrs, header)`, `Morsel.js_output(attrs)`, `Morsel.OutputString(attrs)` | O(v) | O(v) | The value plus the reserved keys that were set, of which there is a fixed number |
| `Morsel.copy()` | O(1) | O(1) | A new `Morsel` over the fixed key set, independent of the original |
| `Morsel.update(values)` | O(u) | O(u) | u = entries supplied, which are collected into a dict before any key is checked, so an invalid batch is allocated before it is refused |
| `Morsel.setdefault(key, val)` | O(1) | O(1) | Validates the key, then behaves as `dict.setdefault`. On a morsel that still has its full key set it never stores, because every reserved key already exists as an empty string; after `del morsel['domain']` it does |
| `Morsel.key`, `Morsel.value`, `Morsel.coded_value` | O(1) | O(1) | The name, the decoded value, and the value as it appears in the header |
| `Morsel.expires`, `Morsel.path`, `Morsel.comment`, `Morsel.domain`, `Morsel.secure`, `Morsel.httponly`, `Morsel.samesite`, `Morsel.version`, `Morsel.partitioned` | O(1) | O(1) | Reserved *keys*, read as `morsel['path']`: unlike `key`, `value` and `coded_value` they are not attributes, and `morsel.path` raises AttributeError. `max-age` is a key too, spelled with the dash. `partitioned` is Python 3.14+ |

### CookieJar and FileCookieJar

Cookies are stored three levels deep - domain, then path, then name - which is
what makes a lookup cheaper than a scan of the whole jar.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `CookieJar(policy)` | O(1) | O(1) | |
| `CookieJar.add_cookie_header(request)` | O(d·g + P + a + m·log m + m·v + c + e) | O(w + m·v) | d = stored domains, P = paths under the domains the policy accepted, a = cookies under the paths it accepted, m = those that survive `return_ok`, g = domains configured on the policy that each check scans. An unrelated domain costs one check rather than one per cookie, but an accepted path costs one check per cookie under it. The survivors are sorted by path length, then rendered into the header. The trailing c + e is the expiry sweep, which walks the whole jar - empty levels included - however little was selected, at the traversal cost under `len()`, the Python 3.10 sort included, and with that walk's O(w) memory |
| `CookieJar.extract_cookies(response, request)` | O(n + c·(v + g)) | O(c·v) | n = the `Set-Cookie` headers' length, c = cookies in them, each checked by the policy before it is stored |
| `CookieJar.make_cookies(response, request)` | O(n + c·v) | O(c·v) | The parsing half of `extract_cookies`, without storing |
| `CookieJar.set_cookie(cookie)` | O(1) | O(1) | Inserts at its domain, path and name |
| `CookieJar.set_cookie_if_ok(cookie, request)` | O(g) | O(1) | One `set_ok` check first, which under the default policy scans the configured blocked or allowed domains |
| `CookieJar.clear(domain, path, name)` | O(1) | O(1) | One dict delete at whichever level the arguments reach - a domain, a path under it, or one name; raises KeyError when there is nothing there, and ValueError when an inner level is given without an outer one |
| `CookieJar.clear()` | O(1) | O(1) | Drops the whole structure |
| `CookieJar.clear_session_cookies()` | As `len()` | O(w) | Walks every cookie for the discard flag, over the same traversal, so the 3.10 sort applies here too |
| `CookieJar.clear_expired_cookies()` | As `len()` | O(w) | The same walk against the clock. `add_cookie_header` calls it, so every request already pays it |
| `CookieJar.set_policy(policy)` | O(1) | O(1) | |
| `len(jar)` | O(c + e) on Python 3.11+; O((c + e)·log w) on 3.10 | O(w) | Walks the three levels and counts; the jar keeps no count. e = levels left empty by earlier `clear()` calls, which are not pruned. The walk collects each level into a list before descending, so w, the widest level it meets, is its memory - with one domain and one path that is every cookie. Python 3.11+ copies the level's values; 3.10 sorts its keys instead, which adds the log factor and fixes the order cookies come back in |
| `iter(jar)` | O(1) | O(1) | A generator; the walk above happens as it is consumed |
| `FileCookieJar(filename, delayload, policy)` | O(1) | O(1) | Opens nothing |
| `FileCookieJar.save(filename, ignore_discard, ignore_expires)` | `len()` + O(c·v) | O(w + v) or O(w + c·v) | One line per cookie, over the same traversal - so it visits retained empty levels and pays the Python 3.10 sort even when nothing is written. `MozillaCookieJar` writes each line as it goes; `LWPCookieJar` builds the whole file in memory first |
| `FileCookieJar.load(filename, ...)` | O(n + c·v) | O(c·v) | n = file size; adds to what the jar already holds |
| `FileCookieJar.revert(filename, ...)` | O(c + e + n + c'·v) | O(c + e + c'·v) | c = cookies already held, c' = cookies in the file. The jar it holds is deep-copied first - empty levels and all, which is the e in both columns - then cleared and reloaded, and the copy stays alive while the new cookies are built, so both are held at once. On failure the copy is put back, so the old contents survive a bad file; the copy is paid in full even when the file is tiny or refused |
| `FileCookieJar.filename`, `FileCookieJar.delayload` | O(1) | O(1) | |

### MozillaCookieJar and LWPCookieJar

`FileCookieJar` subclasses; the bounds above hold, the formats differ.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `MozillaCookieJar` | The `FileCookieJar` rows above | The `FileCookieJar` rows above | The `cookies.txt` format, which has no field for a cookie's comment or port: one saved with either loads back without it |
| `LWPCookieJar` | The `FileCookieJar` rows above | The `FileCookieJar` rows above | The Set-Cookie3 format, which keeps the comment and the port that `cookies.txt` drops - and, being built whole before it is written, is the O(w + c·v) side of the save row. Not everything survives: `rfc2109` comes back False whatever it was |

### Cookie

One stored cookie. Its fields are plain attributes: the constructor takes them
all, and nothing stops later assignment.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Cookie.name`, `Cookie.value`, `Cookie.domain`, `Cookie.path`, `Cookie.port`, `Cookie.secure`, `Cookie.expires`, `Cookie.discard`, `Cookie.comment`, `Cookie.comment_url`, `Cookie.version`, `Cookie.rfc2109`, `Cookie.port_specified`, `Cookie.domain_specified`, `Cookie.domain_initial_dot` | O(1) | O(1) | Read and written directly |
| `Cookie.is_expired(now)` | O(1) | O(1) | One comparison |
| `Cookie.has_nonstandard_attr(name)`, `Cookie.get_nonstandard_attr(name, default)`, `Cookie.set_nonstandard_attr(name, value)` | O(1) | O(1) | A dict of the attributes no field covers |

### CookiePolicy and DefaultCookiePolicy

`CookiePolicy` is the interface `CookieJar` calls; `DefaultCookiePolicy`
implements it.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `CookiePolicy.set_ok(cookie, request)`, `CookiePolicy.return_ok(cookie, request)` | O(1) in the jar's size | O(1) | Once per candidate cookie; the checks compare that cookie's domain, path and expiry |
| `CookiePolicy.domain_return_ok(domain, request)`, `CookiePolicy.path_return_ok(path, request)` | O(1) in the jar's size | O(1) | The two filters that let selection skip a whole domain or path without looking at its cookies |
| `CookiePolicy.netscape`, `CookiePolicy.rfc2965`, `CookiePolicy.hide_cookie2` | O(1) | O(1) | Which protocols the jar handles |
| `DefaultCookiePolicy(...)` | O(g) | O(g) | Copies the blocked and allowed domain sequences into tuples |
| `DefaultCookiePolicy.is_blocked(domain)`, `DefaultCookiePolicy.is_not_allowed(domain)` | O(g) | O(1) | A scan of the configured domains, so a long list is paid on every request |
| `DefaultCookiePolicy.blocked_domains()`, `DefaultCookiePolicy.allowed_domains()` | O(1) | O(1) | Return the stored tuple itself; copy it before keeping it |
| `DefaultCookiePolicy.set_blocked_domains(domains)`, `DefaultCookiePolicy.set_allowed_domains(domains)` | O(g) | O(g) | Builds the tuple |
| `DefaultCookiePolicy.strict_domain`, `DefaultCookiePolicy.strict_rfc2965_unverifiable`, `DefaultCookiePolicy.strict_ns_unverifiable`, `DefaultCookiePolicy.strict_ns_domain`, `DefaultCookiePolicy.strict_ns_set_initial_dollar`, `DefaultCookiePolicy.strict_ns_set_path`, `DefaultCookiePolicy.rfc2109_as_netscape` | O(1) | O(1) | Flags read during the checks above |
| `DefaultCookiePolicy.DomainStrictNoDots`, `DefaultCookiePolicy.DomainStrictNonDomain`, `DefaultCookiePolicy.DomainRFC2965Match`, `DefaultCookiePolicy.DomainLiberal`, `DefaultCookiePolicy.DomainStrict` | O(1) | O(1) | The `strict_ns_domain` bit flags |

### Cookie exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `http.cookies.CookieError` | O(1) | O(1) | An attribute name that is not reserved, or a value that cannot be quoted |
| `http.cookiejar.LoadError` | O(1) | O(1) | A cookie file that does not parse |

## Status Codes Are a Table

Both enumerations are built once, at import. A member reached by name is a
class attribute, and a member reached by value is a dict lookup that returns
the member that already exists, so neither costs anything that grows with the
number of codes.

```python
from http import HTTPStatus

# By name - O(1) attribute access
assert HTTPStatus.OK.value == 200
assert HTTPStatus.NOT_FOUND.value == 404

# By value - O(1), and the member is the one that already exists
assert HTTPStatus(404) is HTTPStatus.NOT_FOUND

# phrase is the reason line; description is the sentence behind it
assert HTTPStatus.NOT_FOUND.phrase == 'Not Found'
assert HTTPStatus.NOT_FOUND.description == 'Nothing matches the given URI'

# An IntEnum, so it compares and formats as its code
assert HTTPStatus.NOT_FOUND == 404
assert f"{HTTPStatus.NOT_FOUND.value} {HTTPStatus.NOT_FOUND.phrase}" == '404 Not Found'
```

!!! note "Printing a member"
    `print(HTTPStatus.OK)` writes `200` on Python 3.11+, where `IntEnum`
    inherits `int.__str__`, and `HTTPStatus.OK` on Python 3.10. Use `.value`
    or `.phrase` to get the same text on every supported version.

## Sending a Body Does Not Buffer It

`HTTPConnection.send()` and the `body` argument to `request()` accept an object
with a `read()` method as well as `bytes`. The two are not equivalent in
memory: `bytes` are handed to the socket as they are, while a readable is
drained in `blocksize` chunks, so the memory an upload needs stays fixed as the
body grows. Passing an open file streams it; calling `.read()` on that file
first does not. Headers go the other way - they are buffered until
`endheaders()` and then written once, so a request with many headers costs one
write, not one per header.

```python
import io
import http.client

class Recorder:
    # Stands in for a socket, so nothing here needs a peer
    def __init__(self):
        self.writes = []
    def sendall(self, data):
        self.writes.append(bytes(data))
    def makefile(self, *args, **kwargs):
        return io.BytesIO()
    def close(self):
        pass

conn = http.client.HTTPConnection('example.com')
conn.sock = Recorder()
assert conn.blocksize == 8192

# A readable body is drained in blocksize chunks - O(blocksize) memory
conn.send(io.BytesIO(b'x' * 100_000))
assert len(conn.sock.writes) == 13          # 100_000 / 8192, rounded up
assert max(len(w) for w in conn.sock.writes) == 8192

# The same bytes handed over directly go in one write - O(1) extra memory
conn.sock = Recorder()
conn.send(b'x' * 100_000)
assert len(conn.sock.writes) == 1

# Headers are buffered until endheaders(), then written once
conn.sock = Recorder()
conn.putrequest('GET', '/', skip_host=True, skip_accept_encoding=True)
for index in range(50):
    conn.putheader(f'X-{index}', 'v')       # O(v), buffered
assert conn.sock.writes == []
conn.endheaders()                           # O(v·h), one write
assert len(conn.sock.writes) == 1
```

## Header Parsing Is Bounded

A peer cannot make one header block cost more than a fixed amount.
`http.client` refuses a header line over 65,536 bytes, and refuses a block once
it has collected more than 100 lines. The terminating blank line counts as one,
so a normal block of 100 headers is 101 lines and is already rejected; 99 is the
most that parses.

`http.server` parses requests with the same code and the same limits, but does
not surface them the same way: it catches the failure and answers with an error
response, where `http.client` raises into the caller. And the per-block cap is
not the per-call cap - `getresponse()` skips `100 Continue` blocks first, each
parsed under the same limits. The patch releases that have
`_MAXINTERIMRESPONSES` cap the status lines read at 100, so 99 interim
responses is the most that can precede the final one.

```python
import io
import http.client

# Within the limits - O(n) in the header bytes
headers = http.client.parse_headers(io.BytesIO(b'A: 1\r\nB: 2\r\n\r\n'))
assert headers['A'] == '1'

# 99 headers plus the blank line is the most that parses
most = b''.join(b'X-%d: v\r\n' % i for i in range(99)) + b'\r\n'
assert http.client.parse_headers(io.BytesIO(most))['X-98'] == 'v'

# 100 headers plus the blank line is already over - refused, not truncated
too_many = b''.join(b'X-%d: v\r\n' % i for i in range(100)) + b'\r\n'
try:
    http.client.parse_headers(io.BytesIO(too_many))
except http.client.HTTPException as error:
    assert 'got more than 100 headers' in str(error)

# A line over 65,536 bytes - LineTooLong
long_line = b'X: ' + b'v' * 70_000 + b'\r\n\r\n'
try:
    http.client.parse_headers(io.BytesIO(long_line))
except http.client.LineTooLong:
    pass
```

Reading a header back is a scan rather than a lookup, because `HTTPMessage`
keeps the headers as the list they arrived in. With h capped that is cheap, but
it is still O(h) per access: fetch a header once and keep it rather than
reaching for it in a loop.

## Directory Listings Stat Every Entry

`SimpleHTTPRequestHandler.list_directory()` sorts the names case-insensitively
and then asks the filesystem twice about each one - whether it is a directory
and whether it is a symlink - to choose the `/` or `@` suffix. The listing is
built as one string in memory before any of it is sent. Both costs scale with
the number of entries, so a directory with many thousands of files is answered
slowly and at a memory cost the file sizes do not predict.

Serving a file is the opposite: `copyfile()` streams it, so the body's size
does not become the server's memory.

`translate_path()` drops any component that is not a plain name, so a literal
`..` in the request cannot climb out of the served directory. That is a check on
the request text, not on the filesystem: a symlink inside the directory still
resolves wherever it points.

## A Rejected Cookie Header Leaves Nothing Behind

`BaseCookie.load()` parses the whole string into pending items before it
applies any of them, so a string it *rejects* leaves the cookie object exactly
as it was rather than holding the pairs that preceded the problem.

That is not the same as all-or-nothing, and two endings break it. When the
pattern simply stops matching, parsing ends quietly and everything gathered so
far is applied, so trailing junk leaves a partly filled object. And a name that
survives the parser but that `Morsel.set` refuses raises `CookieError` while the
items are being applied, after the earlier ones already landed. Check what you
got rather than assuming the whole string arrived.

```python
from http.cookies import SimpleCookie

good = SimpleCookie()
good.load('session=abc123; user=alice')  # O(n)
assert sorted(good.keys()) == ['session', 'user']

# 'path' is a reserved key and needs a value, so the whole string is rejected
rejected = SimpleCookie()
rejected.load('session=abc123; user=alice; path')
assert list(rejected.keys()) == []  # not ['session', 'user']

# Junk the pattern cannot match just ends the parse - what came before is kept
partial = SimpleCookie()
partial.load('session=abc123; ;;;')
assert list(partial.keys()) == ['session']

# A name the parser passes but Morsel refuses raises part way through applying
from http.cookies import CookieError
half = SimpleCookie()
try:
    half.load('session=abc123; bad@name=2')
except CookieError:
    pass
assert list(half.keys()) == ['session']

# Output is one Set-Cookie line per cookie - O(c·v)
good['session']['path'] = '/'
assert good['session'].output() == 'Set-Cookie: session=abc123; Path=/'
```

## A Jar Lookup Skips Domains, the Expiry Sweep Does Not

`CookieJar` stores cookies by domain, then path, then name, and
`add_cookie_header()` asks the policy about each level in turn. A domain the
policy rejects costs one call however many cookies it holds, and a path it
rejects costs one call however many names are under it. What that buys is
skipping *rejected* subtrees: growth under a domain the request does not match
is free, growth under one it does still costs a check per cookie.

```python
import http.cookiejar
import urllib.request

jar = http.cookiejar.CookieJar()

def cookie(domain, path, name, expires=None):
    return http.cookiejar.Cookie(
        0, name, 'v', None, False, domain, True, domain.startswith('.'),
        path, True, False, expires, False, None, None, {})

for site in range(5):
    for path in range(3):
        jar.set_cookie(cookie(f'.host{site}.example.com', f'/p{path}', 'n'))
assert len(jar) == 15  # O(c + e) - a walk, not a stored count

# Only the matching domain's paths and cookies are examined for selection
request = urllib.request.Request('https://host0.example.com/p0/page')
jar.add_cookie_header(request)  # O(d·g + P + a + m log m + m·v + c + e)
assert request.get_header('Cookie') == 'n=v'

# The c term: the call also sweeps the whole jar, unrelated domains included
jar.set_cookie(cookie('.elsewhere.example.net', '/', 'stale', expires=1))
assert 'stale' in [c.name for c in jar]
jar.add_cookie_header(urllib.request.Request('https://host0.example.com/p0/page'))
assert 'stale' not in [c.name for c in jar]
```

Selection is only half the call. `add_cookie_header()` finishes by calling
`clear_expired_cookies()`, which walks every cookie in the jar, so the call
carries a term in c whatever the policy skipped - on top of sorting and
rendering the ones it selected. Cookies kept for other sites stay cheap to skip;
they do not stay free.

Two things on the policy are worth knowing before a jar gets large.
`is_blocked()` scans the configured domains on every check, so a long block
list is paid per request. And `blocked_domains()` hands back the stored tuple
itself rather than a copy - cheap, but it means the value you keep is the
policy's own.

```python
from http.cookiejar import DefaultCookiePolicy

policy = DefaultCookiePolicy()
policy.set_blocked_domains(['ads.example.com', 'tracker.example.net'])

# O(1): the stored tuple, not a copy
assert policy.blocked_domains() is policy.blocked_domains()
assert policy.is_blocked('ads.example.com') is True   # O(g) scan
assert policy.allowed_domains() is None               # nothing restricted
```

## Version Notes

- **Python 3.11+**: `HTTPMethod` exists, and `IntEnum.__str__` is `int.__str__`, so `print(HTTPStatus.OK)` writes `200` rather than `HTTPStatus.OK`
- **Python 3.12+**: `HTTPStatus.is_success` and its four siblings; `HTTPConnection.get_proxy_response_headers()`; `SimpleHTTPRequestHandler.index_pages`
- **Python 3.13+**: `CGIHTTPRequestHandler` is deprecated; it is removed in Python 3.15
- **Python 3.14+**: `HTTPSServer` and `ThreadingHTTPSServer`; `Morsel.partitioned`

## Related Documentation

- [urllib Module](urllib.md) - The opener layer built on `http.client`
- [email Module](email.md) - `HTTPMessage` is an `email` message, and its header bounds apply
- [socketserver Module](socketserver.md) - What `HTTPServer` inherits its accept loop from
- [ssl Module](ssl.md) - The handshake `HTTPSConnection` and `HTTPSServer` add
- [mimetypes Module](mimetypes.md) - Behind `guess_type()`
- [json Module](json.md) - Parsing a response body
