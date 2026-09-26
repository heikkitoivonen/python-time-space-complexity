# poplib Module Complexity

The `poplib` module is a synchronous POP3 client. Each command method sends its command and reads
the server's whole response before it returns; nothing is pipelined and nothing streams. A
command that returns lines - `list()`, `uidl()`, `retr()`, `top()` - builds the list in memory,
one `bytes` object per line, so `retr()` holds the whole message when it returns.

`n` is the bytes of the server's multi-line response to one call: one line per message for
`list()` and `uidl()`, the message for `retr()`, the headers and the requested body lines for
`top()`, the capability list for `capa()` and `stls()`. Every other response is a single line, and
a line longer than 2,048 bytes, counting its line ending, raises `error_proto`, so a single-line
reply is O(1). User names, passwords and message numbers are priced at O(1). The bounds price the
client's CPU work and memory; waiting for the server, connection setup, the TLS handshake and the
server's own work are outside every bound, and the Notes count the exchanges instead.

## Complexity Reference

### POP3

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `poplib.POP3(host, port=POP3_PORT[, timeout])` | O(1) | O(1) | Connects and reads the greeting: one exchange, no command. Port 110 by default; `timeout=0` raises `ValueError`. Not a context manager |
| `POP3.getwelcome()` | O(1) | O(1) | The greeting read at connection; no exchange |
| `POP3.set_debuglevel(level)` | O(1) | O(1) | 1 prints each command to standard output; 2 also prints every line read, a whole message for `retr()` |
| `POP3.quit()` | O(1) | O(1) | One exchange, then closes. The server deletes the marked messages and unlocks the mailbox |

### POP3_SSL

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `poplib.POP3_SSL(host, port=POP3_SSL_PORT, *, timeout=..., context=None)` | O(1) | O(1) | A `POP3` that speaks TLS from the first byte, on port 995 by default. Without `context`, the server's certificate is not verified |

### Authentication and TLS

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `POP3.user(username)`, `POP3.pass_(password)` | O(1) | O(1) | One exchange each. The server locks the mailbox from `pass_()` until `quit()` |
| `POP3.apop(user, secret)` | O(1) | O(1) | One exchange, sending an MD5 digest of the greeting's timestamp and `secret` instead of the password. Raises `error_proto` without sending anything when the greeting has no timestamp |
| `POP3.rpop(user)` | O(1) | O(1) | One exchange |
| `POP3.capa()` | O(n) | O(n) | One exchange; returns `{name: [argument, ...]}`. Raises `error_proto` when the server does not support `CAPA` |
| `POP3.stls(context=None)` | O(n) | O(n) | Calls `capa()`, then sends `STLS`: two exchanges, then the TLS handshake. Raises `error_proto` without sending `STLS` when the server does not advertise it, and at once on `POP3_SSL` or a second call. Without `context`, the certificate is not verified |
| `POP3.utf8()` | O(1) | O(1) | One exchange |

### Mailbox commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `POP3.stat()` | O(1) | O(1) | One exchange; returns `(message count, mailbox size)` |
| `POP3.list(which=None)` | O(n) | O(n) | One exchange. Without `which`, one line per message; with it, one line |
| `POP3.uidl(which=None)` | O(n) | O(n) | As `list()`, with each message's unique id in place of its size |
| `POP3.retr(which)` | O(n) | O(n) | One exchange; returns `(response, lines, octets)` with the whole message as a list of lines. A message line over 2,048 bytes raises `error_proto` |
| `POP3.top(which, howmuch)` | O(n) | O(n) | One exchange; the headers and the first `howmuch` body lines, returned as `retr()` returns a message. Optional for servers |
| `POP3.dele(which)` | O(1) | O(1) | One exchange; the server marks the message, and deletes it at `quit()` |
| `POP3.rset()` | O(1) | O(1) | One exchange; the server clears every deletion mark |
| `POP3.noop()` | O(1) | O(1) | One exchange |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `poplib.error_proto` | O(1) | O(1) | Raised for an `-ERR` reply, an over-long line, or a connection that closes while a reply is awaited. Subclasses `Exception`, not `OSError`: socket errors pass through as they are |

## Reading a Mailbox

### A Session

Connecting reads the greeting and nothing else, and each command after it waits for its reply.
`quit()` is what ends the session: `POP3` is not a context manager, so close it in a `finally`.

```python
import poplib
import ssl

context = ssl.create_default_context()  # verifies the server; the default does not

pop = poplib.POP3_SSL('pop.example.com', context=context)  # one exchange: the greeting
try:
    pop.user('user@example.com')  # O(1), one exchange
    pop.pass_('app-password')     # O(1), the mailbox is locked from here
    count, size = pop.stat()      # O(1)
    assert count == 3

    response, lines, octets = pop.retr(1)  # O(n): the whole message, as lines
    assert response.startswith(b'+OK')
    assert lines[1] == b'Subject: Hello'
finally:
    pop.quit()  # O(1), unlocks the mailbox
```

### Counting Messages

`stat()` asks for the count and gets one line back. `list()` gets one line per message, so
counting with it costs O(n), growing with the number of messages in the mailbox.

```python
import poplib

pop = poplib.POP3('pop.example.com')
pop.user('user@example.com')
pop.pass_('app-password')

count, size = pop.stat()                   # O(1): one line back
response, listings, octets = pop.list()    # O(n): one line per message
assert count == len(listings) == 3
assert listings[0] == b'1 57'              # message number and size in octets

assert pop.list(2).startswith(b'+OK 2 ')   # one message, one line: O(1)
pop.quit()
```

### Retrieved Lines

`retr()` and `top()` return the message as a list of lines with their line endings removed and
any leading dot the server doubled taken off again; `octets` counts what the lines held with their
line endings. Joining the lines with `b'\r\n'` and ending with one more gives the message back
for the `email` parser.

```python
import poplib
from email.parser import BytesParser

pop = poplib.POP3('pop.example.com')
pop.user('user@example.com')
pop.pass_('app-password')

response, lines, octets = pop.retr(2)  # O(n)
assert b'.hidden dot line' in lines   # sent as '..hidden dot line'
raw = b'\r\n'.join(lines) + b'\r\n'
assert len(raw) == octets

message = BytesParser().parsebytes(raw)
assert message['Subject'] == 'Report'
assert message.get_payload() == '.hidden dot line\r\nThe numbers are in.\r\n'
pop.quit()
```

## Headers Without Bodies

`top(which, 0)` returns a message's headers alone, so a scan of what is in the mailbox reads each
message's headers instead of its body. Unlike `retr()`, it does not mark the message
seen. `TOP` is optional in POP3, and not every server implements it faithfully.

```python
import poplib

pop = poplib.POP3('pop.example.com')
pop.user('user@example.com')
pop.pass_('app-password')

subjects = []
for number in range(1, pop.stat()[0] + 1):
    response, lines, octets = pop.top(number, 0)  # O(n): headers only
    subjects += [line[9:] for line in lines if line.startswith(b'Subject: ')]

assert subjects == [b'Hello', b'Report', b'Lunch']
pop.quit()
```

## Deleting Messages

`dele()` only marks a message. The server deletes the marked messages when `quit()` ends the
session, and `rset()` clears the marks before then. A connection that ends without `QUIT` should
delete nothing, but POP3 servers vary.

```python
import poplib

pop = poplib.POP3('pop.example.com')
pop.user('user@example.com')
pop.pass_('app-password')

pop.dele(1)                    # O(1): marked, not yet deleted
assert pop.stat()[0] == 2      # marked messages are hidden from the session
pop.rset()                     # O(1): every mark cleared
assert pop.stat()[0] == 3

try:
    pop.retr(99)
except poplib.error_proto as error:
    assert error.args[0].startswith(b'-ERR')
else:
    raise AssertionError('a missing message was retrieved')
pop.quit()
```

## Upgrading with STLS

`stls()` calls `capa()` first and refuses to go on if `STLS` is not advertised, so it is two
exchanges before the handshake. Upgrade before `user()` and `pass_()`, or the password crosses the
network in clear text.

```python
import poplib
import ssl

pop = poplib.POP3('pop.example.com')             # port 110, clear text
assert 'STLS' in pop.capa()                      # O(n), one exchange
pop.stls(context=ssl.create_default_context())  # CAPA, STLS and the handshake
pop.user('user@example.com')
pop.pass_('app-password')

try:
    pop.stls()
except poplib.error_proto as error:
    assert 'already established' in str(error)
else:
    raise AssertionError('a second STLS was sent')
pop.quit()
```

## Common Patterns

### Downloading Only New Messages

A message's number can change from one session to the next; its `UIDL` id does not. One `uidl()`
call lists every id, so a client that remembers which ids it has seen retrieves only the rest.

```python
import poplib

seen = {b'uid-1'}

pop = poplib.POP3('pop.example.com')
pop.user('user@example.com')
pop.pass_('app-password')

response, listings, octets = pop.uidl()  # O(n): one line per message
fresh = []
for listing in listings:
    number, uid = listing.split()
    if uid not in seen:
        fresh.append(pop.retr(int(number))[1])  # O(n) for each new message
        seen.add(uid)

assert len(fresh) == 2
assert seen == {b'uid-1', b'uid-2', b'uid-3'}
pop.quit()
```

## Performance Best Practices

✅ **Do**:

- Count messages with `stat()`: one line back, where `list()` returns one per message
- Scan headers with `top(which, 0)` where the server supports it, rather than `retr()` on every
  message
- Track `uidl()` ids between sessions and retrieve only the messages you have not seen
- Call `quit()` in a `finally`: without it the server applies no deletions, and keeps the mailbox
  locked until it notices the connection is gone
- Pass a `context` from `ssl.create_default_context()` to `POP3_SSL` and `stls()`

❌ **Avoid**:

- `retr()` on a message too large to hold in memory: it returns the whole message, and has no
  streaming form
- `set_debuglevel(2)` around `retr()`: it prints every line of every message
- Sending the password over plain `POP3` without `stls()`

## Version Notes

- **Python 3.12+**: `POP3_SSL` no longer accepts `keyfile` and `certfile`, and takes `timeout` by
  keyword only; pass an `ssl.SSLContext` as `context`
- **All Python 3**: Without `context`, `POP3_SSL` and `stls()` do not verify the server's
  certificate or host name

## Related Modules

- **[imaplib](imaplib.md)** - mailboxes kept on the server, with search and partial fetches
- **[email](email.md)** - parsing the lines `retr()` returns into a message
- **[smtplib](smtplib.md)** - sending mail
- **[ssl](ssl.md)** - the `SSLContext` that `POP3_SSL` and `stls()` take
- **[socket](socket.md)** - the connection underneath
