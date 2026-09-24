# imaplib Module Complexity

The `imaplib` module is a synchronous IMAP4rev1 client. Each command method builds one command
line, sends it, and reads the server's whole response before it returns, so a `fetch()` of a
thousand messages holds all thousand in memory as a list of `bytes` and `(header, literal)` tuples
when the call returns. Only `idle()` hands responses over as they arrive.

`c` is the bytes of the command line built from a call's arguments, `n` is the bytes of the
server's response to that call (every line and literal), `m` is the bytes of a message passed to
`append()`, `t` is the bytes an `authenticate()` callback returns in all, `l` is the bytes of one
line or string, and `d` is the base-16 digits of the number passed to `Int2AP()`. The bounds price
the client's own CPU work and memory for a call with a few arguments, and exclude the work of any
callback you pass. Round trips, waiting for the server, the TLS handshake, and the server's own
work (searching, sorting or expunging a mailbox) are outside every bound: O(c + n) means the
client's share is linear, not that the call returns promptly.

## Complexity Reference

### IMAP4 connections

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `imaplib.IMAP4(host='', port=IMAP4_PORT, timeout=None)` | O(n) | O(n) | Connects, reads the greeting and learns `capabilities` before returning |
| `imaplib.IMAP4_SSL(host='', port=IMAP4_SSL_PORT, *, ssl_context=None, timeout=None)` | O(n) | O(n) | As `IMAP4`, over TLS from the first byte |
| `imaplib.IMAP4_stream(command)` | O(n) | O(n) | Runs `command` through the shell and talks IMAP over its standard input and output |
| `with IMAP4(...) as imap:` | O(n) | O(n) | Leaving the block calls `logout()` |
| `IMAP4.open(host='', port=IMAP4_PORT, timeout=None)`, `IMAP4.shutdown()` | O(1) | O(1) | The constructor calls `open()` and `logout()` calls `shutdown()`; override them to change the transport |
| `IMAP4.read(size)` | O(size) | O(size) | Reads exactly `size` bytes unless the connection ends first |
| `IMAP4.readline()` | O(l) | O(l) | A line over 1,000,000 bytes raises `IMAP4.error` |
| `IMAP4.send(data)` | O(len(data)) | O(1) | |
| `IMAP4.socket()` | O(1) | O(1) | The underlying socket |

### IMAP4 session commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IMAP4.login(user, password)` | O(c + n) | O(c + n) | |
| `IMAP4.login_cram_md5(user, password)` | O(n + t²) | O(n + t) | `authenticate()` with a CRAM-MD5 callback, whose reply is the user name and a 32-character digest |
| `IMAP4.authenticate(mechanism, authobject)` | O(c + n + t²) | O(c + n + t) | `authobject` is called once per server challenge, and encoding its reply is quadratic in the reply's length |
| `IMAP4.starttls(ssl_context=None)` | O(n) | O(n) | Plus the TLS handshake; reads `capabilities` again afterwards |
| `IMAP4.capability()`, `IMAP4.namespace()`, `IMAP4.noop()`, `IMAP4.check()` | O(c + n) | O(c + n) | |
| `IMAP4.enable(capability)` | O(c + n) | O(c + n) | Raises `IMAP4.error` if `ENABLE` is not in `capabilities`; `UTF8=ACCEPT` switches the connection to UTF-8 |
| `IMAP4.proxyauth(user)` | O(c + n) | O(c + n) | |
| `IMAP4.logout()` | O(n) | O(n) | Sends `LOGOUT` and closes the connection |

### IMAP4 mailbox commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IMAP4.select(mailbox='INBOX', readonly=False)` | O(c + n) | O(c + n) | Discards every stored untagged response first; `readonly=True` sends `EXAMINE` |
| `IMAP4.close()`, `IMAP4.unselect()` | O(n) | O(n) | `close()` also expunges deleted messages on the server; `unselect()` does not |
| `IMAP4.list([directory[, pattern]])`, `IMAP4.lsub([directory[, pattern]])` | O(c + n) | O(c + n) | |
| `IMAP4.status(mailbox, names)` | O(c + n) | O(c + n) | |
| `IMAP4.create(mailbox)`, `IMAP4.delete(mailbox)`, `IMAP4.rename(oldmailbox, newmailbox)` | O(c + n) | O(c + n) | |
| `IMAP4.subscribe(mailbox)`, `IMAP4.unsubscribe(mailbox)` | O(c + n) | O(c + n) | |
| `IMAP4.expunge()` | O(n) | O(n) | One message number per removed message |

### IMAP4 message commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IMAP4.search(charset, *criteria)` | O(c + n) | O(c + n) | The server answers on one line of numbers; see [The Line Limit](#the-line-limit) |
| `IMAP4.sort(sort_criteria, charset, *search_criteria)`, `IMAP4.thread(threading_algorithm, charset, *search_criteria)` | O(c + n) | O(c + n) | Server extensions; the ordering work is the server's |
| `IMAP4.fetch(message_set, message_parts)` | O(c + n) | O(c + n) | Each literal comes back as a `(header, data)` tuple; every message in the set is in memory when the call returns |
| `IMAP4.partial(message_num, message_part, start, length)` | O(c + n) | O(c + n) | Obsolete; `fetch()` with `BODY[]<start.length>` is the modern form |
| `IMAP4.store(message_set, command, flags)` | O(c + n) | O(c + n) | Returns the server's `FETCH` responses for the changed messages |
| `IMAP4.copy(message_set, new_mailbox)` | O(c + n) | O(c + n) | The copying is the server's |
| `IMAP4.append(mailbox, flags, date_time, message)` | O(c + m + n) | O(c + m + n) | Rewrites every line ending to CRLF, then sends the message as one literal |
| `IMAP4.uid(command, *args)` | O(c + n) | O(c + n) | `command` names by UID instead of sequence number; same cost as the command it wraps |
| `IMAP4.xatom(name, *args)` | O(c + n) | O(c + n) | Any extension command the server advertises |

### IMAP4 access control, quota and annotation commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IMAP4.getacl(mailbox)`, `IMAP4.setacl(mailbox, who, what)`, `IMAP4.deleteacl(mailbox, who)`, `IMAP4.myrights(mailbox)` | O(c + n) | O(c + n) | The ACL extension |
| `IMAP4.getquota(root)`, `IMAP4.getquotaroot(mailbox)`, `IMAP4.setquota(root, limits)` | O(c + n) | O(c + n) | The QUOTA extension |
| `IMAP4.getannotation(mailbox, entry, attribute)`, `IMAP4.setannotation(mailbox[, entry, attribute]+)` | O(c + n) | O(c + n) | The ANNOTATEMORE draft |

### IMAP4 responses and state

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IMAP4.response(code)` | O(1) | O(1) | Hands back the stored list for `code` itself and forgets it; `[None]` when there is none |
| `IMAP4.recent()` | O(1) or O(n) | O(1) or O(n) | Returns stored `RECENT` responses, and sends a `NOOP` only when there are none |
| `IMAP4.capabilities` | O(1) | O(1) | A tuple of the upper-case names the server advertised |
| `IMAP4.PROTOCOL_VERSION` | O(1) | O(1) | `'IMAP4REV1'` or `'IMAP4'` |
| `IMAP4.utf8_enabled` | O(1) | O(1) | `True` after `enable('UTF8=ACCEPT')` succeeds |
| `IMAP4.debug` | O(1) | O(1) | Debug level; higher levels write more of the conversation to standard error |
| `IMAP4.print_log()` | O(l) | O(l) | Prints at most the last ten logged lines to standard error; l = the longest of them |
| `IMAP4.COMMAND`, for any command in upper case | O(1) | O(1) | An alias for the lower-case method |
| `IMAP4.error`, `IMAP4.abort`, `IMAP4.readonly` | O(1) | O(1) | `abort` subclasses `error` and means reconnect; `readonly` subclasses `abort` and means the mailbox became read-only |

### Idler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IMAP4.idle(duration=None)` | O(1) | O(1) | Python 3.14+. Returns an `Idler`; nothing is sent until the `with` block starts |
| `with imap.idle() as idler:` | O(n) | O(n) | Sends `IDLE` on entry and `DONE` on exit; responses not yet yielded move to `untagged_responses` |
| Iterating an `Idler` | O(n) | O(n) | Yields each untagged response as `(type, [data])` as it arrives, so a loop that keeps none holds one at a time; stops waiting once `duration` seconds have passed since the block started |
| `Idler.burst(interval=0.1)` | O(n) | O(n) | Yields the next response and any that follow it within `interval` seconds of each other |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `imaplib.Internaldate2tuple(datestr)` | O(l) | O(1) | Local time as a `time.struct_time`, or `None` when the string holds no `INTERNALDATE` |
| `imaplib.Time2Internaldate(date_time)` | O(1) | O(1) | Accepts seconds since the epoch, a time tuple, an aware `datetime`, or a quoted string returned as is |
| `imaplib.ParseFlags(flagstr)` | O(l) | O(l) | A tuple of the flags in a `FLAGS (...)` response; empty when there is none |
| `imaplib.Int2AP(num)` | O(d²) | O(d) | Encodes a number in the letters `A`-`P`; the module uses it for its short command-tag prefix |

## Reading Responses

### Every Response Is Held Whole

A command method returns only when the server has finished answering, so its whole response is
in memory at once. Ask for what you need - a header, a size, flags - and fetch large sets in
batches rather than in one call.

```python
import imaplib

with imaplib.IMAP4_SSL('imap.example.com') as imap:  # O(n) plus the TLS handshake
    imap.login('user@example.com', 'app-password')    # O(c + n)
    typ, data = imap.select('INBOX', readonly=True)   # O(c + n)
    assert typ == 'OK'
    count = int(data[0])  # the EXISTS count

    typ, data = imap.search(None, 'ALL')  # O(n) - one line of message numbers
    numbers = data[0].split()
    assert all(number.isdigit() for number in numbers)

    # O(c + n): every requested header is in `data` when the call returns
    first = numbers[:2]
    typ, data = imap.fetch(b','.join(first), '(RFC822.SIZE BODY.PEEK[HEADER])')
    literals = [part for part in data if isinstance(part, tuple)]
    assert len(literals) == len(first)
    header_line, header = literals[0]  # (response line, literal bytes)
    assert header_line.startswith(first[0] + b' (') and header.endswith(b'\r\n\r\n')
```

### Untagged Responses Accumulate

Servers send untagged responses the command did not ask for, such as `EXISTS` when new mail
arrives. A method returns only the ones it names and keeps the rest in `untagged_responses`, so a
long-lived connection that polls with `noop()` grows until `response()` or a command naming them
collects them, or `select()` discards them. Only the status responses `OK`, `NO` and `BAD` are
cleared by the next command. `response()` hands back the stored list itself, in O(1).

```python
import imaplib

with imaplib.IMAP4_SSL('imap.example.com') as imap:
    imap.login('user@example.com', 'app-password')
    imap.select('INBOX')  # O(c + n) - forgets every stored response first

    for _ in range(3):
        imap.noop()  # O(n) - any untagged lines are stored, not returned

    typ, exists = imap.response('EXISTS')  # O(1) - takes the stored list
    assert typ == 'EXISTS' and exists[-1].isdigit()
    assert imap.response('EXISTS') == ('EXISTS', [None])  # cleared by the first call
```

### The Line Limit

Every response line is read whole, and one longer than 1,000,000 bytes raises `IMAP4.error`
instead of growing without bound. `SEARCH` answers on a single line, so a search matching
roughly 150,000 messages can hit it; split the search into UID ranges.

```python
import imaplib

with imaplib.IMAP4_SSL('imap.example.com') as imap:
    imap.login('user@example.com', 'app-password')
    imap.select('INBOX', readonly=True)

    uids = []
    # UIDs below 200,000 in four searches, each answer well under the limit
    for start in range(1, 200_001, 50_000):
        typ, data = imap.uid('SEARCH', f'UID {start}:{start + 49_999}')  # O(c + n)
        uids.extend(data[0].split())

    assert len(uids) == len(set(uids))
```

## Sending Commands

### Appending a Message

`append()` normalizes every line ending in the message to CRLF and sends the result as a single
literal.

```python
import imaplib
import time
from email.message import EmailMessage

message = EmailMessage()
message['Subject'] = 'Report'
message.set_content('Line one\nLine two\n')

with imaplib.IMAP4_SSL('imap.example.com') as imap:
    imap.login('user@example.com', 'app-password')
    typ, data = imap.append(
        'INBOX', r'(\Seen)', imaplib.Time2Internaldate(time.time()), message.as_bytes()
    )  # O(c + m + n)
    assert typ == 'OK'
```

### Changing Flags and Expunging

```python
import imaplib

with imaplib.IMAP4_SSL('imap.example.com') as imap:
    imap.login('user@example.com', 'app-password')
    imap.select('INBOX')

    typ, data = imap.store('1', '+FLAGS', r'(\Deleted)')  # O(c + n)
    assert rb'\Deleted' in data[0]
    assert r'\Deleted' in [flag.decode() for flag in imaplib.ParseFlags(data[0])]

    typ, removed = imap.expunge()  # O(n) - one number per removed message
    assert b'1' in removed
```

## Waiting for New Mail

`idle()` (Python 3.14+) keeps one command open and yields untagged responses as the server pushes
them, one at a time; only those still unread when the block ends are stored. `duration` stops the
waiting that many seconds after the block starts. RFC 2177 has clients restart `IDLE` at least
every 29 minutes, so a long-running watcher loops around the block.

```python
import imaplib

with imaplib.IMAP4_SSL('imap.example.com') as imap:
    imap.login('user@example.com', 'app-password')
    imap.select('INBOX')

    new_mail = False
    with imap.idle(duration=5) as idler:  # O(1) to build; entering sends IDLE
        for typ, data in idler:           # O(n) over the responses yielded
            if typ == 'EXISTS':
                new_mail = True
                break                     # leaving the block sends DONE

    assert imap.state == 'SELECTED'  # back to normal commands
    if new_mail:
        typ, data = imap.search(None, 'UNSEEN')
```

## Parsing Helpers

The module-level helpers convert single values and never touch a connection.

```python
import imaplib
import time
from datetime import datetime, timezone

# O(l) - the flags of a FLAGS response, as a tuple of bytes
flags = imaplib.ParseFlags(rb'1 (FLAGS (\Seen \Answered) UID 17)')
assert flags == (rb'\Seen', rb'\Answered')
assert imaplib.ParseFlags(b'1 (UID 17)') == ()

# O(1) - an aware datetime to the quoted IMAP date form
stamp = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
assert imaplib.Time2Internaldate(stamp) == '"02-Jan-2024 03:04:05 +0000"'

# O(l) - back to local time from a FETCH line
parsed = imaplib.Internaldate2tuple(b'1 (INTERNALDATE "02-Jan-2024 03:04:05 +0000")')
assert time.mktime(parsed) == stamp.timestamp()
assert imaplib.Internaldate2tuple(b'1 (UID 17)') is None
```

## Common Patterns

### Fetching in Batches

Fetching a slice at a time keeps each response to one batch, whatever the mailbox holds.

```python
import imaplib
import re

BATCH = 500

with imaplib.IMAP4_SSL('imap.example.com') as imap:
    imap.login('user@example.com', 'app-password')
    imap.select('INBOX', readonly=True)
    typ, data = imap.uid('SEARCH', 'ALL')
    uids = data[0].split()

    sizes = {}
    for start in range(0, len(uids), BATCH):
        batch = b','.join(uids[start:start + BATCH])
        typ, data = imap.uid('FETCH', batch, '(RFC822.SIZE)')  # O(c + n) per batch
        for line in data:  # b'1 (UID 17 RFC822.SIZE 2048)'
            uid = re.search(rb'UID (\d+)', line).group(1)
            sizes[uid] = int(re.search(rb'RFC822.SIZE (\d+)', line).group(1))

    assert len(sizes) <= len(uids)  # a message expunged meanwhile is missing
```

## Performance Best Practices

✅ **Do**:

- Fetch only the parts you need (`BODY.PEEK[HEADER]`, `RFC822.SIZE`, `FLAGS`); the response is
  held whole
- Fetch large message sets in batches, so each response holds one batch rather than the mailbox
- Collect untagged responses with `response()` on a long-lived connection, or they accumulate
- Split very large searches into UID ranges to stay under the 1,000,000-byte line limit
- Use `idle()` on Python 3.14+ instead of polling with `noop()`

❌ **Avoid**:

- `fetch('1:*', '(RFC822)')` on a large mailbox - every message is in memory before the call
  returns
- Polling a long-lived connection with `noop()` and never calling `response()` - the untagged
  responses it stores stay until `select()`

## Version Notes

- **Python 3.12+**: `IMAP4_SSL` no longer accepts `keyfile` and `certfile`; pass an
  `ssl_context`, which is keyword-only
- **Python 3.14+**: Added `IMAP4.idle()`

## Related Modules

- **[poplib](poplib.md)** - the simpler POP3 client
- **[smtplib](smtplib.md)** - sending mail
- **[email](email.md)** - parsing the message bytes `fetch()` returns
- **[mailbox](mailbox.md)** - local mailbox files, with no server round trips
- **[ssl](ssl.md)** - the contexts `IMAP4_SSL` and `starttls()` take
