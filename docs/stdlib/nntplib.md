# nntplib Module Complexity

The `nntplib` module is a synchronous NNTP client for reading and posting Usenet news. Each
command method waits for the server's whole reply before it returns. A command that returns
lines - `list()`, `over()`, `article()`, `help()` and the rest - builds the list in
memory, unless you pass `file=`, in which case the lines go to the file and the call keeps none of
them.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples need
    Python 3.10, 3.11 or 3.12.

`r` is the lines in the server's multi-line reply to one call: one per group for `list()`, one
per article for `over()` and `xhdr()`, the article for `article()`. `d` is the bytes of an article
sent by `post()` or `ihave()`, and `h` the characters and `w` the RFC 2047 encoded words of a
header given to `decode_header()`. A line longer than 2,048 bytes, counting its line ending,
raises `NNTPDataError`, so lines and bytes grow together and a single-line reply is O(1). Group names, message ids and article numbers are
priced at O(1). The bounds price the client's CPU work and memory; waiting for the server,
connection setup, the TLS handshake and the server's own work are outside every bound, and the
Notes count the exchanges instead.

## Complexity Reference

### NNTP

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nntplib.NNTP(host, port=119, user=None, password=None, readermode=None, usenetrc=False, timeout=...)` | O(r) | O(r) | Reads the greeting and sends `CAPABILITIES`; r = capability lines. `readermode=True` adds `MODE READER` and a second `CAPABILITIES` when the server does not advertise `READER`; a server that answers 480 gets them again from `login()`, after authentication. `user` or `usenetrc` adds `login()`. `timeout=0` raises `ValueError`. A `with` block sends `QUIT` on exit |
| `NNTP.getwelcome()` | O(1) | O(1) | The greeting read at connection, or the reply to an accepted `MODE READER`; no exchange |
| `NNTP.getcapabilities()` | O(1) | O(1) | The dictionary read at connection, `{name: [argument, ...]}`, not a copy; no exchange |
| `NNTP.nntp_version`, `NNTP.nntp_implementation` | O(1) | O(1) | Taken from the capabilities: the highest `VERSION`, 1 when none is advertised, and the `IMPLEMENTATION` text or `None` |
| `NNTP.set_debuglevel(level)` | O(1) | O(1) | Also spelled `NNTP.debug`. 1 prints each command and reply line; 2 also prints every line read, a whole article for `article()` |
| `NNTP.login(user=None, password=None, usenetrc=True)` | O(r) | O(r) | `AUTHINFO USER`, `AUTHINFO PASS` when asked for it, then `CAPABILITIES` again. Without `user`, parses `~/.netrc` first, at a cost that grows with that file, and sends nothing when it has no entry for the host |
| `NNTP.starttls(context=None)` | O(r) | O(r) | One exchange, the TLS handshake, then `CAPABILITIES` again. A second call raises `ValueError` with nothing sent. Without `context`, the certificate is not verified |
| `NNTP.quit()` | O(1) | O(1) | One exchange, then closes the socket |

### NNTP_SSL

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nntplib.NNTP_SSL(host, port=563, user=None, password=None, ssl_context=None, readermode=None, usenetrc=False, timeout=...)` | O(r) | O(r) | An `NNTP` that speaks TLS from the first byte, on port 563 by default. Without `ssl_context`, the certificate is not verified |

### Groups

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NNTP.group(name)` | O(1) | O(1) | One exchange; returns `(response, count, first, last, name)` with the numbers as `int`; the group becomes the server's current group |
| `NNTP.list(group_pattern=None, *, file=None)` | O(r) | O(r) | One exchange; a list of `GroupInfo(group, last, first, flag)`, all four `str`. A pattern such as `'comp.lang.*'` lets the server filter, so r is the groups that match |
| `NNTP.newgroups(date, *, file=None)` | O(r) | O(r) | One exchange; `GroupInfo` for each group created since `date`, a `date` or `datetime` |
| `NNTP.description(group)` | O(r) | O(r) | One exchange; the first description in the reply, or `''`. The whole reply is read first |
| `NNTP.descriptions(group_pattern)` | O(r) | O(r) | One exchange; returns `(response, {group: description})` |

### Articles

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NNTP.stat(message_spec=None)`, `NNTP.next()`, `NNTP.last()` | O(1) | O(1) | One exchange; returns `(response, number, message_id)`, nothing of the article |
| `NNTP.article(message_spec=None, *, file=None)` | O(r) | O(r) | One exchange; returns `(response, ArticleInfo(number, message_id, lines))`, the article as `bytes` lines. With `file=`, the lines go to the file and `lines` is empty, so the call holds one line at a time |
| `NNTP.head(message_spec=None, *, file=None)`, `NNTP.body(message_spec=None, *, file=None)` | O(r) | O(r) | As `article()`, for the headers or the body alone |
| `NNTP.over(message_spec, *, file=None)` | O(r) | O(r) | One exchange, `OVER` or `XOVER` by what the server advertises; returns `(response, [(number, {field: value}), ...])`. The first `over()` or `xover()` on a connection also sends `LIST OVERVIEW.FMT`, once |
| `NNTP.xover(start, end, *, file=None)` | O(r) | O(r) | `over((start, end))` always sent as `XOVER` |
| `NNTP.xhdr(hdr, str, *, file=None)` | O(r) | O(r) | One exchange; one header for each article in `str`, as `(number, value)` string pairs |
| `NNTP.newnews(group, date, *, file=None)` | O(r) | O(r) | One exchange; the message ids posted since `date`, as strings |

### Posting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NNTP.post(data)` | O(d) | O(d) for `bytes`, one line for a file | Two exchanges, one before the article and one after. A `bytes` article is split into a list of lines first; a binary file or an iterable of lines is sent a line at a time |
| `NNTP.ihave(message_id, data)` | O(d) | O(d) for `bytes`, one line for a file | As `post()`. A server that does not want the article raises `NNTPTemporaryError` before any of it is sent |

### Other commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NNTP.date()` | O(1) | O(1) | One exchange; the server's time as a `datetime` |
| `NNTP.help(*, file=None)` | O(r) | O(r) | One exchange; the help text as a list of strings |
| `NNTP.slave()` | O(1) | O(1) | One exchange |
| `nntplib.decode_header(header_str)` | O(h + w²) | O(h) | Decodes the encoded words in a header, such as an overview's `subject`, to one `str`; no exchange |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nntplib.NNTPError` | O(1) | O(1) | Base class of the five below; `NNTPError.response` holds the reply line that caused it, or a message such as `'line too long'` |
| `nntplib.NNTPTemporaryError`, `nntplib.NNTPPermanentError` | O(1) | O(1) | A 4xx reply and a 5xx reply |
| `nntplib.NNTPReplyError` | O(1) | O(1) | A reply in the 1xx-3xx range that the command did not expect |
| `nntplib.NNTPProtocolError` | O(1) | O(1) | A reply that does not start with a digit from 1 to 5 |
| `nntplib.NNTPDataError` | O(1) | O(1) | A malformed reply, or a line longer than 2,048 bytes |

## Reading a Group

### A Session

Connecting reads the greeting and the capabilities; after that every command waits for its
reply. A `with` block sends `QUIT` when it ends.

```python
import nntplib

with nntplib.NNTP('news.example.com') as nntp:  # greeting and CAPABILITIES
    response, count, first, last, name = nntp.group('comp.lang.python')  # O(1)
    assert (count, first, last) == (3, 1, 3)

    response, info = nntp.article(first)  # O(r): the whole article, as lines
    assert info.number == 1
    assert info.message_id == '<1@example.com>'
    assert b'Subject: Hello' in info.lines
```

### The Overview Instead of the Articles

`over()` returns a few header fields for a whole range of articles in one reply, a line per
article, so listing what a group holds does not fetch any article. The first `over()` or
`xover()` on a connection asks for the overview format as well; later calls reuse it.

```python
import nntplib

nntp = nntplib.NNTP('news.example.com')
response, count, first, last, name = nntp.group('comp.lang.python')

response, overviews = nntp.over((first, last))  # O(r): one line per article
subjects = [fields['subject'] for number, fields in overviews]
assert subjects == ['Hello', 'Re: Hello', '=?utf-8?q?Caf=C3=A9?=']

assert nntplib.decode_header(subjects[2]) == 'Café'  # O(h + w²)
nntp.quit()
```

### Writing to a File

With `file=`, the reply's lines are written to the file as they arrive and the call returns none
of them, so a large article costs one line of memory instead of the whole article. `file` is a
binary file object, or a file name to create.

```python
import nntplib
import os
import tempfile

nntp = nntplib.NNTP('news.example.com')
nntp.group('comp.lang.python')

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'body')
    response, info = nntp.body(2, file=path)  # O(r) time, one line held at a time
    assert info.lines == []
    with open(path, 'rb') as f:
        assert f.read() == b'.hidden dot line\r\nAgreed.\r\n'  # line endings kept

response, info = nntp.body(2)  # the same body, held as a list
assert info.lines == [b'.hidden dot line', b'Agreed.']
nntp.quit()
```

## Listing Groups

`list()` returns one `GroupInfo` per group the server carries. A pattern makes the server send
only the groups that match. The fields stay
strings.

```python
import nntplib

nntp = nntplib.NNTP('news.example.com')

response, groups = nntp.list('comp.lang.*')  # O(r): r = matching groups
assert [g.group for g in groups] == ['comp.lang.c', 'comp.lang.python']
assert groups[1].last == '3'

response, descriptions = nntp.descriptions('comp.lang.*')
assert descriptions['comp.lang.python'] == 'The Python language.'
assert nntp.description('comp.lang.c') == 'The C language.'
nntp.quit()
```

## Posting

`post()` sends the article a line at a time, adding a dot to any line that starts with one. Passed
as `bytes`, the article is split into a list of lines first; a file opened in binary mode is read
as it is sent.

```python
import io
import nntplib

article = (b'From: ann@example.com\r\n'
           b'Newsgroups: comp.lang.python\r\n'
           b'Subject: Test\r\n'
           b'\r\n'
           b'.A line starting with a dot.\r\n')

nntp = nntplib.NNTP('news.example.com')
response = nntp.post(io.BytesIO(article))  # O(d) time, two exchanges
assert response.startswith('240')
nntp.quit()
```

## Errors

A 4xx reply raises `NNTPTemporaryError` and a 5xx reply `NNTPPermanentError`; both carry the
reply line in `response`.

```python
import nntplib

nntp = nntplib.NNTP('news.example.com')
try:
    nntp.group('no.such.group')
except nntplib.NNTPTemporaryError as error:
    assert error.response.startswith('411')
else:
    raise AssertionError('a missing group was selected')
nntp.quit()
```

## Performance Best Practices

✅ **Do**:

- Read a group's subjects with `over()`: one line per article, where `article()` returns every
  line of each one
- Pass a pattern to `list()` and `descriptions()` so the server sends only the groups you want
- Pass `file=` to `article()` or `body()` for a large article, so the lines are not held in a list
- Post from a binary file rather than `bytes`, so the article is not split into a list first
- Pass a context from `ssl.create_default_context()` to `NNTP_SSL` and `starttls()`

❌ **Avoid**:

- `list()` without a pattern against a full news server: it returns every group it carries
- `set_debuglevel(2)` around `article()`: it prints every line of every article
- Expecting `over()` to return anything when you pass `file=`: the lines go to the file and the
  list comes back empty

## Version Notes

- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import nntplib` raises `ModuleNotFoundError`

## Related Modules

- **[email](email.md)** - parses the lines `article()` returns into a message
- **[poplib](poplib.md)** - the same command-and-reply cost model, for a mailbox
- **[socket](socket.md)** - the connection underneath
