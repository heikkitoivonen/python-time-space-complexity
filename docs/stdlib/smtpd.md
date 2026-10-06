# smtpd Module Complexity

The `smtpd` module is an SMTP server built on `asyncore` and `asynchat`. An `SMTPServer` listens
for connections and builds one `SMTPChannel` per client; the channel reads commands a line at a
time, collects a message's data until the closing `.` line, and hands the whole message to the
server's `process_message()`. Everything runs inside the `asyncore` loop, so a slow step in one
connection holds up every other.

!!! warning "Removed in Python 3.12"
    Deprecated since Python 3.6 and removed in Python 3.12 by PEP 594. The examples need Python
    3.10 or 3.11; new code should build on `asyncio`.

`n` is the bytes of one message's data, `k` is the characters of one command line, `p` is the
recipients accepted for the current message, and `s` is the server's `data_size_limit`. The bounds
count Python-level work and the bytes held; they exclude the kernel's cost for each system call,
the resolver lookups named in the rows, and the cost of your own `process_message()`. The
per-pass cost of the loop itself is on the [asyncore](asyncore.md) page.

## Complexity Reference

### SMTPServer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtpd.SMTPServer(localaddr, remoteaddr, data_size_limit=33554432, map=None, enable_SMTPUTF8=False, decode_data=False)` | O(1) | O(1) | Resolves `localaddr` with `getaddrinfo()`, binds, listens and registers itself in `map`, or in asyncore's global map. `enable_SMTPUTF8` and `decode_data` together raise `ValueError` |
| `SMTPServer.process_message(peer, mailfrom, rcpttos, data, **kwargs)` | O(1) | O(1) | Must be overridden; the default raises `NotImplementedError`. Called once per message, inside the loop. With `decode_data=False`, the default, `data` is `bytes` and `mail_options` and `rcpt_options` arrive as keyword arguments, so an override that does not accept them, with `**kwargs` or by name, raises `TypeError` and the channel closes. Return `None` to reply `250 OK`, or a reply line |
| `SMTPServer.channel_class` | O(1) | O(1) | `SMTPChannel`; set a subclass to change how connections are handled |
| `SMTPServer.handle_accepted(conn, addr)` | O(1) | O(1) | Builds one `channel_class` per accepted connection, in the server's map |

### SMTPChannel

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtpd.SMTPChannel(server, conn, addr, data_size_limit=33554432, map=None, enable_SMTPUTF8=False, decode_data=False)` | O(1) | O(1) | Built by the server for each connection. Calls `socket.getfqdn()`, a resolver lookup the whole loop waits for, and queues the `220` greeting |
| `SMTPChannel.collect_incoming_data(data)` | O(1) amortized | O(1) | Keeps each piece in `received_lines` until the terminator, and drops it once the line or the message is past its limit. In command state it also reads `max_command_size_limit`; `decode_data=True` decodes the piece first, in O(len(data)) |
| `SMTPChannel.found_terminator()` | O(k) per command, O(n) per message | O(k) per command, O(n) per message | Joins the pieces. A command line goes to its `smtp_<COMMAND>()` method, priced in its own row; a message has the leading dot removed from dot-stuffed lines and CRLF turned into LF, goes to `process_message()`, and gets its return value as the reply |
| `SMTPChannel.push(msg)` | O(len(msg)) | O(len(msg)) | Encodes a reply line as ASCII, or UTF-8 for a message sent with `SMTPUTF8`, adds CRLF and queues it |
| `SMTPChannel.smtp_HELO(arg)`, `SMTPChannel.smtp_EHLO(arg)` | O(1) | O(1) | Start a new transaction and record `seen_greeting`; a second greeting gets `503`. `EHLO` turns on `SIZE` when there is a limit, `8BITMIME` unless `decode_data`, and `SMTPUTF8` when enabled |
| `SMTPChannel.smtp_MAIL(arg)` | O(k) | O(k) | Parses the address and parameters; refuses a declared `SIZE` over `data_size_limit` with `552` |
| `SMTPChannel.smtp_RCPT(arg)` | O(k + p) | O(k + p) | Parses the address and appends it to `rcpttos`, which has no limit. It also formats the whole list for `DEBUGSTREAM`, discarded or not, so accepting p recipients costs O(p²) |
| `SMTPChannel.smtp_DATA(arg)` | O(1) | O(1) | Needs a greeting and a recipient; switches the terminator to `\r\n.\r\n` |
| `SMTPChannel.smtp_RSET(arg)` | O(1) | O(1) | Clears the sender, the recipients and `received_data`, keeping the greeting |
| `SMTPChannel.smtp_VRFY(arg)` | O(k) | O(k) | Parses the address and replies `252` without checking it |
| `SMTPChannel.smtp_NOOP(arg)`, `SMTPChannel.smtp_EXPN(arg)` | O(1) | O(1) | One fixed reply each; `EXPN` is always `502` |
| `SMTPChannel.smtp_HELP(arg)` | O(k) | O(k) | Upper-cases the argument and replies with that command's syntax, or the command list |
| `SMTPChannel.smtp_QUIT(arg)` | O(1) | O(1) | Replies `221` and closes the channel once the reply is sent |
| `SMTPChannel.smtp_server`, `SMTPChannel.conn`, `SMTPChannel.addr`, `SMTPChannel.peer`, `SMTPChannel.fqdn` | O(1) | O(1) | The server, the socket and its address, the address `getpeername()` returned, and the name `getfqdn()` returned |
| `SMTPChannel.smtp_state`, `SMTPChannel.COMMAND`, `SMTPChannel.DATA` | O(1) | O(1) | `smtp_state` is `COMMAND` (0) or, after `DATA`, `DATA` (1) |
| `SMTPChannel.seen_greeting`, `SMTPChannel.mailfrom` | O(1) | O(1) | The `HELO`/`EHLO` argument and the sender; `''` and `None` until set |
| `SMTPChannel.rcpttos` | O(1) | O(1) | The recipient list; `process_message()` receives this list itself, and the channel starts a new one for the next message |
| `SMTPChannel.received_lines` | O(1) | O(1) | The pieces of the line or message being read |
| `SMTPChannel.received_data` | O(1) | O(1) | The last message's data, the object `process_message()` received. It stays until `RSET` or the next message, so an idle channel keeps its last message |
| `SMTPChannel.data_size_limit`, `SMTPChannel.enable_SMTPUTF8` | O(1) | O(1) | Copied from the server; `None` or 0 means no limit on a message |
| `SMTPChannel.command_size_limit` | O(1) | O(1) | 512, the limit on a command line unless `command_size_limits` gives the command a larger one; a longer line gets `500 Error: line too long` |
| `SMTPChannel.command_size_limits` | O(1) | O(1) | A class-wide dict of per-command limits, shared by every channel and emptied whenever one is built. `EHLO` raises `MAIL`'s limit by 26 for `SIZE` and 10 for `SMTPUTF8` |
| `SMTPChannel.max_command_size_limit` | O(u) | O(1) | u = entries in `command_size_limits`; the largest, or 512 when it is empty |

### DebuggingServer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtpd.DebuggingServer(localaddr, remoteaddr, ...)` | O(1) | O(1) | An `SMTPServer` that prints each message instead of delivering it |
| `DebuggingServer.process_message(peer, mailfrom, rcpttos, data, **kwargs)` | O(n) | O(n) | Prints the message to standard output, with an `X-Peer` header at the first blank line; `bytes` data is printed one `repr()` per line |

### PureProxy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtpd.PureProxy(localaddr, remoteaddr, ...)` | O(1) | O(1) | Relays to `remoteaddr`. `enable_SMTPUTF8=True` raises `ValueError`. Pass `decode_data=True`: its `process_message()` takes no keyword arguments, so without it every message raises `TypeError` and the channel closes |
| `PureProxy.process_message(peer, mailfrom, rcpttos, data)` | O(n + p) | O(n + p) | Adds an `X-Peer` header and sends the message with a new `smtplib.SMTP` connection, one per message, with one `RCPT` per recipient; the loop waits for the whole session. Refusals and connection failures are not reported: the client still gets `250 OK` |

### MailmanProxy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtpd.MailmanProxy(localaddr, remoteaddr, ...)` | O(1) | O(1) | Python 3.10 only. A `PureProxy` that hands mailing-list addresses to a list manager; building one emits a `DeprecationWarning`, and `enable_SMTPUTF8=True` raises `ValueError` |
| `MailmanProxy.process_message(peer, mailfrom, rcpttos, data)` | O(n + p²) | O(n + p) | Takes no keyword arguments, so it needs `decode_data=True`. It imports the list manager's package, which Python does not ship; without it every message raises `ModuleNotFoundError`. With it, list recipients are removed from `rcpttos` one at a time and the rest are relayed as `PureProxy` does; the package's own work is outside the bound |

### Module constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtpd.DATA_SIZE_DEFAULT` | O(1) | O(1) | 33554432 bytes (32 MiB), the default `data_size_limit` |
| `smtpd.DEBUGSTREAM` | O(1) | O(1) | Where the module writes its trace of commands and messages; it discards them unless you assign a file such as `sys.stderr` |

## Receiving Messages

Subclass `SMTPServer` and override `process_message()`. The channel holds a message's pieces until
the closing `.` line and then hands over the whole message at once, as `bytes` with LF line
endings unless `decode_data=True`. The override runs inside the loop: while it runs, no other
connection is served.

```python
import asyncore
import smtpd
import smtplib
import threading

class Collector(smtpd.SMTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # O(1) - binds and listens
        self.messages = []

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        self.messages.append((mailfrom, rcpttos, data, kwargs))  # O(1)
        return None  # 250 OK

channels = {}
server = Collector(("127.0.0.1", 0), None, map=channels)
port = server.socket.getsockname()[1]

def send():
    with smtplib.SMTP("127.0.0.1", port) as client:
        client.sendmail("a@example.org", ["b@example.org"], "Subject: hi\r\n\r\n.dot\r\n")

sender = threading.Thread(target=send)
sender.start()
while sender.is_alive():
    asyncore.loop(timeout=0.05, map=channels, count=1)  # O(n) for the message
sender.join()

mailfrom, rcpttos, data, options = server.messages[0]
assert (mailfrom, rcpttos) == ("a@example.org", ["b@example.org"])
assert data == b"Subject: hi\n\n.dot"  # bytes, LF endings, dot-stuffing undone
assert options == {"mail_options": ["SIZE=21"], "rcpt_options": []}

asyncore.close_all(channels)
```

## The Message Size Limit

`data_size_limit` bounds what one message can hold: past it the channel drops what arrives, so
memory stays near `s` however much the client sends. A client that declares the size
after `EHLO`, as `smtplib` does, is refused at `MAIL` before it sends anything. One that sends the
data anyway gets `552` at the closing `.` line, and the channel then stays in data state: what the
client sends next is read as another message, so close the connection after that reply.

```python
import asyncore
import smtpd
import socket

class Server:
    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        raise AssertionError("an oversized message was delivered")

channels = {}
ours, theirs = socket.socketpair()
channel = smtpd.SMTPChannel(Server(), ours, ("client", 0), data_size_limit=1000, map=channels)
assert theirs.recv(1024).startswith(b"220 ")

theirs.sendall(
    b"HELO me\r\nMAIL FROM:<a@x.org>\r\nRCPT TO:<b@x.org>\r\nDATA\r\n"
    + b"x" * 5_000 + b"\r\n.\r\n"
)
asyncore.loop(timeout=1, map=channels, count=1)  # O(n) time, O(s) memory
replies = theirs.recv(4096).decode().splitlines()
assert replies[-1] == "552 Error: Too much mail data"
assert channel.smtp_state == channel.DATA  # still reading message data

theirs.sendall(b"RSET\r\n")
asyncore.loop(timeout=1, map=channels, count=1)
assert channel.received_lines == [b"RSET"]  # taken as data, not as a command

asyncore.close_all(channels)
theirs.close()
```

## Relaying With PureProxy

`PureProxy` delivers each message itself, opening a new `smtplib` connection to the upstream
server and waiting for the whole session before `process_message()` returns. Every other client of
the proxy waits with it. What the upstream server answers is not passed on.

```python
import asyncore
import smtpd
import threading

class Upstream(smtpd.SMTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        self.messages.append((rcpttos, data))

upstream_map = {}
upstream = Upstream(("127.0.0.1", 0), None, map=upstream_map)
done = threading.Event()

def serve():
    while not done.is_set():
        asyncore.loop(timeout=0.05, map=upstream_map, count=1)
    asyncore.close_all(upstream_map)

thread = threading.Thread(target=serve)
thread.start()

proxy = smtpd.PureProxy(
    ("127.0.0.1", 0), upstream.socket.getsockname(), map={}, decode_data=True
)
proxy.process_message(("192.0.2.7", 2525), "a@x.org", ["b@x.org"], "Subject: hi\n\nbody")
# O(n + p), and the upstream session has finished before it returns
assert upstream.messages == [(["b@x.org"], b"Subject: hi\nX-Peer: 192.0.2.7\n\nbody")]

done.set()
thread.join()
proxy.close()
```

## Performance Best Practices

✅ **Do**:

- Accept `**kwargs` in `process_message()`, or pass `decode_data=True`; an override that refuses
  `mail_options` and `rcpt_options` closes the channel on every message
- Keep `process_message()` short, or hand the message to a thread or queue: the loop serves no one
  else while it runs
- Keep a `data_size_limit`: it is what bounds one message's memory
- Close the connection after a `552` at the end of `DATA`

❌ **Avoid**:

- `PureProxy` for any volume of mail - one blocking upstream session per message, with failures
  reported to no one
- `data_size_limit=None` or `0` with clients you do not control - a message is then held whole
- Messages with thousands of recipients - accepting p recipients costs O(p²)
- `smtpd` in new code - it does not exist from Python 3.12

## Version Notes

- **Python 3.6+**: Deprecated
- **Python 3.10+**: Importing the module emits a `DeprecationWarning`
- **Python 3.11+**: `MailmanProxy` removed
- **Python 3.12+**: Removed by PEP 594; `import smtpd` raises `ModuleNotFoundError`

## Related Modules

- **[smtplib](smtplib.md)** - the client side, and what `PureProxy` relays through
- **[asyncore](asyncore.md)** - the loop and `dispatcher` base class `SMTPServer` builds on
- **[asynchat](asynchat.md)** - the `async_chat` base class that splits a channel's input at its terminator
- **[email](email.md)** - parse the `bytes` `process_message()` receives with `email.message_from_bytes()`
- **[asyncio](asyncio.md)** - the replacement for the loop all of this runs in
