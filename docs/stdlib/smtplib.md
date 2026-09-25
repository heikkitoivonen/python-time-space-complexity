# smtplib Module Complexity

The `smtplib` module is a synchronous SMTP client. Each command method, from `ehlo()` to
`sendmail()`, sends a command and waits for the server's whole reply before sending the next; only
the low-level `putcmd()` and `send()` write without reading. Nothing is pipelined, so what a call
waits for is the number of exchanges it makes: once `EHLO` has been answered, a `sendmail()` whose
message is accepted makes r + 3, r counting refused recipients too. Nothing streams either: a message is passed, held and
written as one `str` or `bytes` object.

`m` is the bytes of the message, `r` is the recipients passed to one call, and `n` is the bytes of
the server's replies that a call reads, every line of every reply. Addresses, credentials and
command arguments are a few dozen characters and are priced at O(1). The bounds price the client's
CPU work and memory; waiting for the server, DNS, connection setup and the TLS handshake are
outside every bound, and the Notes count the exchanges instead.

## Complexity Reference

### SMTP

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtplib.SMTP(host='', port=0, local_hostname=None, timeout=..., source_address=None)` | O(n) | O(n) | With a host, connects and reads the greeting: one exchange. `EHLO` waits for the first command that needs it. Without `local_hostname`, looks up the local host's name, host or not |
| `with SMTP(...) as smtp:` | O(n) | O(n) | Leaving the block sends `QUIT` and closes; a server that has already gone is not an error |
| `SMTP.connect(host='localhost', port=0, source_address=None)` | O(n) | O(n) | Accepts `'host:port'` when `port` is 0; reads the greeting |
| `SMTP.set_debuglevel(level)` | O(1) | O(1) | 1 writes every command and reply to standard error; 2 adds timestamps |
| `SMTP.quit()` | O(n) | O(n) | Sends `QUIT`, forgets the `EHLO` answer and closes |
| `SMTP.close()` | O(1) | O(1) | Closes the socket without sending `QUIT` |

### SMTP_SSL

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtplib.SMTP_SSL(host='', port=0, local_hostname=None, *, timeout=..., source_address=None, context=None)` | O(n) | O(n) | An `SMTP` that speaks TLS from the first byte, on port 465 by default. Without `context`, the server's certificate is not verified |

### LMTP

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtplib.LMTP(host='', port=LMTP_PORT, local_hostname=None, source_address=None, timeout=...)` | O(n) | O(n) | An `SMTP` that sends `LHLO` where `SMTP` sends `EHLO`; a `host` starting with `/` is a Unix socket path |

### SMTP extensions and authentication

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SMTP.ehlo(name='')` | O(n) | O(n) | One exchange; replaces `esmtp_features` with the extensions the reply lists |
| `SMTP.helo(name='')` | O(n) | O(n) | One exchange; for servers without ESMTP |
| `SMTP.ehlo_or_helo_if_needed()` | O(n) | O(n) | Sends `EHLO`, and `HELO` if that is refused, only when neither has been answered since the object was made or last cleared by `quit()` or `starttls()`; `login()`, `starttls()`, `sendmail()` and `send_message()` call it first |
| `SMTP.has_extn(name)` | O(1) | O(1) | Case-insensitive lookup in `esmtp_features` |
| `SMTP.esmtp_features`, `SMTP.does_esmtp`, `SMTP.ehlo_resp`, `SMTP.helo_resp` | O(1) | O(1) | `EHLO` sets the first three and `HELO` the last; `starttls()` and `quit()` clear all four, `close()` does not |
| `SMTP.starttls(*, context=None)` | O(n) | O(n) | One exchange, then the TLS handshake. Clears what `EHLO` learned, so the next `login()` or send sends `EHLO` again. Without `context`, the certificate is not verified |
| `SMTP.login(user, password, *, initial_response_ok=True)` | O(n) | O(n) | Tries `CRAM-MD5`, `PLAIN` and `LOGIN` in that order, among those the server advertises, and moves on when one is refused. On a build without MD5, 3.13.8+ skips `CRAM-MD5` and earlier releases raise `ValueError` on it. With the default initial response, `PLAIN` takes one exchange and `CRAM-MD5` and `LOGIN` take two |
| `SMTP.auth(mechanism, authobject, *, initial_response_ok=True)` | O(n) | O(n) | Excluding what `authobject` does and the length of what it returns. One exchange, plus one per `334` challenge, each answered by calling `authobject`; a server that keeps challenging raises `SMTPException` after at most six answered challenges |
| `SMTP.auth_cram_md5(challenge=None)`, `SMTP.auth_plain(challenge=None)`, `SMTP.auth_login(challenge=None)` | O(n) | O(1) | The `authobject`s `login()` passes to `auth()`; each answers from `user` and `password`, and `auth_cram_md5()` hashes the challenge, which is part of a reply |

### SMTP mail transactions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SMTP.sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())` | O(m + n) | O(m + n) | `MAIL`, one `RCPT` per recipient, `DATA` and the message: r + 3 exchanges when the message is accepted, after `EHLO` if it has not been sent. The message is written in one call. Returns the refused recipients; raises if every one is refused, or if the server closes the connection with `421` |
| `SMTP.send_message(msg, from_addr=None, to_addrs=None, mail_options=(), rcpt_options=())` | O(m + n) | O(m + n) | Plus serializing `msg`, which [email](email.md) prices. Then calls `sendmail()`. Recipients default to `To`, `Cc` and `Bcc`, or their `Resent-` forms when the message has one `Resent-Date`; the `Bcc` header is not sent |
| `SMTP.mail(sender, options=())`, `SMTP.rcpt(recip, options=())` | O(n) | O(n) | One exchange each |
| `SMTP.data(msg)` | O(m + n) | O(m + n) | Two exchanges. Doubles a leading `.` on every line, and turns every line ending in a `str` into CRLF |
| `SMTP.rset()`, `SMTP.noop()` | O(n) | O(n) | One exchange each |
| `SMTP.verify(address)`, `SMTP.expn(address)` | O(n) | O(n) | One exchange each; `SMTP.vrfy` is `verify` |
| `SMTP.help(args='')` | O(n) | O(n) | One exchange; returns the reply text alone |
| `SMTP.docmd(cmd, args='')` | O(n) | O(n) | `putcmd()`, then `getreply()` |
| `SMTP.putcmd(cmd, args='')` | O(1) | O(1) | Sends one command line; raises `ValueError` if it contains CR or LF |
| `SMTP.send(s)` | O(len(s)) | O(len(s)) | Writes `s` as is, encoding a `str` first |
| `SMTP.getreply()` | O(n) | O(n) | Reads every line of one reply and returns `(code, text)`; a line over 8,192 bytes raises `SMTPResponseException` |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtplib.quoteaddr(addrstring)` | O(a) | O(a) | a = address length; returns the bare address in angle brackets |
| `smtplib.quotedata(data)` | O(m) | O(m) | The line-ending and leading-dot rewriting `data()` does to a `str` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `smtplib.SMTP_PORT`, `smtplib.SMTP_SSL_PORT`, `smtplib.LMTP_PORT` | O(1) | O(1) | 25, 465 and 2003 |
| `smtplib.SMTPException` | O(1) | O(1) | Subclasses `OSError`; every exception below subclasses it |
| `smtplib.SMTPResponseException`, `SMTPResponseException.smtp_code`, `SMTPResponseException.smtp_error` | O(1) | O(1) | The server's reply code and text; the base of the next five |
| `smtplib.SMTPSenderRefused`, `SMTPSenderRefused.sender` | O(1) | O(1) | `MAIL` was refused, for example by a `SIZE` limit |
| `smtplib.SMTPDataError` | O(1) | O(1) | The message was refused after `DATA` |
| `smtplib.SMTPConnectError` | O(1) | O(1) | The greeting was not `220` |
| `smtplib.SMTPHeloError` | O(1) | O(1) | Both `EHLO` and `HELO` were refused |
| `smtplib.SMTPAuthenticationError` | O(1) | O(1) | Authentication was refused; from `login()`, by every mechanism it tried |
| `smtplib.SMTPRecipientsRefused`, `SMTPRecipientsRefused.recipients` | O(1) | O(1) | Every recipient was refused, or a `421` closed the connection during `RCPT`; `recipients` holds the refusals so far |
| `smtplib.SMTPNotSupportedError` | O(1) | O(1) | The server does not advertise what the call needs: `STARTTLS`, `AUTH`, or `SMTPUTF8` for a non-ASCII address |
| `smtplib.SMTPServerDisconnected` | O(1) | O(1) | The connection closed, or was never opened |

## Sending Mail

### A Session

Connecting reads the greeting and nothing else. `starttls()`, `login()` and the first send each
send `EHLO` first if it has not been answered yet, and `starttls()` forgets the answer, so the
session below sends `EHLO` twice.

```python
import smtplib
import ssl
from email.message import EmailMessage

context = ssl.create_default_context()  # verifies the server; the default does not

message = EmailMessage()
message['From'] = 'sender@example.com'
message['To'] = 'ann@example.com'
message['Subject'] = 'Report'
message.set_content('The numbers are in.\n')

with smtplib.SMTP('smtp.example.com', 587) as smtp:  # one exchange: the greeting
    smtp.starttls(context=context)                   # EHLO, STARTTLS and the handshake
    smtp.login('user@example.com', 'app-password')   # EHLO again, then AUTH
    refused = smtp.send_message(message)             # O(m + n): MAIL, RCPT, DATA, the message
    assert refused == {}
# leaving the block sent QUIT
```

### Recipients and Exchanges

Once `EHLO` has been answered, one `sendmail()` call is `MAIL`, one `RCPT` for each recipient,
`DATA` and the message, each waiting for its reply before the next is sent. The message crosses the network
once however many recipients it has. A recipient the server refuses is returned rather than
raised, unless every one is refused or the server closes the connection.

```python
import smtplib

body = 'Subject: Outage\r\n\r\nThe service is back.\r\n'
recipients = ['ann@example.com', 'bob@example.com', 'unknown@example.com']

with smtplib.SMTP('smtp.example.com', 587) as smtp:
    smtp.ehlo()
    refused = smtp.sendmail('ops@example.com', recipients, body)  # O(m + n), r + 3 exchanges
    assert list(refused) == ['unknown@example.com']
    assert refused['unknown@example.com'][0] == 550

    try:
        smtp.sendmail('ops@example.com', ['unknown@example.com'], body)
    except smtplib.SMTPRecipientsRefused as error:
        assert list(error.recipients) == ['unknown@example.com']
    else:
        raise AssertionError('a send with no accepted recipient succeeded')

    assert smtp.noop()[0] == 250  # the connection is still usable
```

### The Message Is Held Whole

`sendmail()` takes the message as one object and writes it in one call, so it costs O(m) memory
and cannot stream. A server that advertises `SIZE` is told the length in the `MAIL` command, and
can refuse an oversized message before any of it is sent. A `str` message must be ASCII; for
anything else pass `bytes`, or use `send_message()`, which serializes the message itself.

```python
import smtplib

with smtplib.SMTP('smtp.example.com', 587) as smtp:
    smtp.ehlo()                                  # one exchange
    assert smtp.has_extn('size')                 # O(1)
    limit = int(smtp.esmtp_features['size'])     # O(1)

    oversized = 'Subject: Big\r\n\r\n' + 'x' * limit
    try:
        smtp.sendmail('me@example.com', ['ann@example.com'], oversized)
    except smtplib.SMTPSenderRefused as error:  # refused at MAIL, before the body is sent
        assert error.smtp_code == 552
    else:
        raise AssertionError('an oversized message was accepted')

    try:
        smtp.sendmail('me@example.com', ['ann@example.com'], 'Subject: Café\r\n\r\n')
    except UnicodeEncodeError:
        pass
    else:
        raise AssertionError('a non-ASCII str was sent')

    utf8 = 'Subject: Café\r\n\r\n'.encode('utf-8')
    assert smtp.sendmail('me@example.com', ['ann@example.com'], utf8) == {}  # not re-encoded
```

## Connections

### Extensions and STARTTLS

`EHLO` fills `esmtp_features`, and `has_extn()` is a lookup in it. `starttls()` clears it, as
RFC 3207 requires, and servers commonly advertise `AUTH` only once the connection is encrypted.

```python
import smtplib
import ssl

with smtplib.SMTP('smtp.example.com', 587) as smtp:
    smtp.ehlo()
    assert smtp.has_extn('STARTTLS') and not smtp.has_extn('AUTH')

    smtp.starttls(context=ssl.create_default_context())
    assert smtp.esmtp_features == {}  # sent again by the next command that needs it

    smtp.ehlo()
    assert smtp.has_extn('auth')  # O(1); case does not matter
```

### Authentication

`login()` picks the first of `CRAM-MD5`, `PLAIN` and `LOGIN` that the server advertises (the
table notes the exception for builds without MD5), and moves to the next when one is refused. A wrong password
is refused by all of them, so it raises `SMTPAuthenticationError` after trying each of them.

```python
import smtplib

with smtplib.SMTP_SSL('smtp.example.com') as smtp:  # TLS from the first byte
    code, _ = smtp.login('user@example.com', 'app-password')  # EHLO, then AUTH PLAIN
    assert code == 235

with smtplib.SMTP_SSL('smtp.example.com') as smtp:
    try:
        smtp.login('user@example.com', 'wrong')
    except smtplib.SMTPAuthenticationError as error:
        assert error.smtp_code == 535
    else:
        raise AssertionError('a wrong password was accepted')
```

## Quoting Helpers

`mail()`, `rcpt()` and `data()` do this rewriting themselves; the helpers expose it.

```python
import smtplib

assert smtplib.quoteaddr('Ann <ann@example.com>') == '<ann@example.com>'  # O(a)
assert smtplib.quotedata('.hidden\nline\r\n') == '..hidden\r\nline\r\n'   # O(m)
```

## Common Patterns

### One Connection for Many Messages

Personalized messages need one send each, but not one connection each: the greeting, `STARTTLS`,
its handshake and `AUTH` are paid once, and each message then costs its own r + 3 exchanges.

```python
import smtplib
import ssl
from email.message import EmailMessage

people = {'ann@example.com': 'Ann', 'bob@example.com': 'Bob'}

with smtplib.SMTP('smtp.example.com', 587) as smtp:
    smtp.starttls(context=ssl.create_default_context())
    smtp.login('user@example.com', 'app-password')

    for address, name in people.items():
        message = EmailMessage()
        message['From'] = 'news@example.com'
        message['To'] = address
        message['Subject'] = 'Your update'
        message.set_content(f'Hello {name},\n')
        assert smtp.send_message(message) == {}  # O(m + n), four exchanges
```

## Performance Best Practices

✅ **Do**:

- Keep one connection open for a batch of messages: the greeting, TLS and authentication are
  paid once
- Send one identical message to many recipients in one `sendmail()` call: one `RCPT` each, and
  the message crosses the network once
- Pass `local_hostname` when you know it, so the constructor does not look up the local host's
  name

❌ **Avoid**:

- Opening a connection per message - every one repeats the greeting, `EHLO`, TLS and `AUTH`
- Passing `sendmail()` a message too large to hold in memory: it takes one object and writes it
  in one call, and has no streaming form

## Version Notes

- **Python 3.12+**: `SMTP_SSL` and `starttls()` no longer accept `keyfile` and `certfile`; pass
  an `ssl.SSLContext` as `context`
- **All Python 3**: Without `context`, `starttls()` and `SMTP_SSL` do not verify the server's
  certificate or host name

## Related Modules

- **[email](email.md)** - building the `EmailMessage` that `send_message()` serializes
- **[ssl](ssl.md)** - the `SSLContext` that `starttls()` and `SMTP_SSL` take
- **[imaplib](imaplib.md)** - reading mail from a mailbox
- **[poplib](poplib.md)** - downloading mail from a mailbox
- **[socket](socket.md)** - the connection underneath
