# ftplib Module Complexity

The `ftplib` module is a synchronous FTP client. Commands travel as single lines over a control
connection, and every file transfer or directory listing opens a new data connection of its own.
Transfers stream: `retrbinary()` and `storbinary()` move one block at a time and hand each block to
your callback or socket, so memory follows the block size rather than the file. Only `nlst()` and
`mlsd()` hold a whole listing.

`b` is the bytes a transfer or listing moves over the data connection, `k` is `blocksize`, `l` is
the characters in the longest line of a line-mode transfer, `c` is the characters in the command
lines a call sends, and `r` is the characters in the server's replies to them; a transfer or
listing adds that O(c + r) to its own row. Every reply line and every line of a line-mode transfer
is read with a cap of 8,192 characters, line ending included (bytes, for `storlines()`), so `l`
never exceeds that. The
bounds price the client's own work and memory with debugging off, and exclude the work of any
callback you pass. Round trips, DNS lookups, connection setup, TLS handshakes and the server's own
work are outside every bound.

## Complexity Reference

### FTP connections

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ftplib.FTP(host='', user='', passwd='', acct='', ...)` | O(c + r) | O(c + r) | Connects when `host` is given and logs in when `user` is too; O(1) with neither |
| `FTP.connect(host='', port=0, ...)` | O(r) | O(r) | Returns the server's welcome |
| `FTP.getwelcome()` | O(1) | O(1) | The welcome `connect()` stored |
| `FTP.login(user='anonymous', passwd='', acct='')` | O(c + r) | O(c + r) | `USER`, then `PASS` and `ACCT` only when the server asks for them |
| Leaving a `with FTP(...) as ftp:` block | O(r) | O(r) | Sends `QUIT` and closes, ignoring a connection already gone |
| `FTP.set_pasv(val)` | O(1) | O(1) | Passive by default; `False` makes the server connect back to the client for each transfer |
| `FTP.set_debuglevel(level)` | O(1) | O(1) | `1` prints each command and reply to standard output, `2` every line sent and read; passwords are masked |
| `FTP.abort()` | O(r) | O(r) | Sends `ABOR` for a transfer in progress |
| `FTP.quit()` | O(r) | O(r) | Sends `QUIT`, then closes; an error reply raises before the close, so follow it with `close()` |
| `FTP.close()` | O(1) | O(1) | Closes the sockets without sending anything; safe to call twice |

### FTP commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `FTP.sendcmd(cmd)` | O(c + r) | O(c + r) | Returns the reply; a `4xx` raises `error_temp` and a `5xx` `error_perm` |
| `FTP.voidcmd(cmd)` | O(c + r) | O(c + r) | As `sendcmd()`, and raises `error_reply` unless the reply is `2xx` |
| `FTP.cwd(pathname)` | O(c + r) | O(c + r) | `'..'` sends `CDUP` |
| `FTP.pwd()`, `FTP.mkd(pathname)` | O(c + r) | O(c + r) | Return the path the server quotes in its `257` reply |
| `FTP.rmd(dirname)`, `FTP.delete(filename)` | O(c + r) | O(c + r) | |
| `FTP.rename(fromname, toname)` | O(c + r) | O(c + r) | Two commands, `RNFR` then `RNTO` |
| `FTP.size(filename)` | O(c + r) | O(c + r) | An `int` from a `213` reply |

### FTP transfers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `FTP.retrbinary(cmd, callback, blocksize=8192, rest=None)` | O(b) | O(k) | Calls `callback` with each block of at most `k` bytes as it arrives; `rest` starts the server at that offset |
| `FTP.storbinary(cmd, fp, blocksize=8192, callback=None, rest=None)` | O(b) | O(k) | Reads `fp` a block at a time and sends each block before reading the next |
| `FTP.retrlines(cmd, callback=None)` | O(b) | O(l) | Calls `callback` with each line, line ending stripped; the default prints it |
| `FTP.storlines(cmd, fp, callback=None)` | O(b) | O(l) | Reads a binary `fp` a line at a time and sends each with a CRLF ending |
| `FTP.transfercmd(cmd, rest=None)` | O(c + r) | O(c + r) | Returns the data socket; the caller reads or writes it, closes it, then calls `voidresp()` |
| `FTP.ntransfercmd(cmd, rest=None)` | O(c + r) | O(c + r) | As `transfercmd()`, returning `(socket, size)`; `size` comes from the `150` reply, or is `None` |

### FTP listings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `FTP.nlst(argument[, ...])` | O(b) | O(b) | Returns every name as one list |
| `FTP.dir(argument[, ...][, callback])` | O(b) | O(l) | Streams the `LIST` output a line at a time to `callback`, which prints by default |
| `FTP.mlsd(path='', facts=[])` | O(b) | O(b) | A generator: nothing is sent until the first `next()`, which reads the whole listing before yielding the first entry |

### FTP_TLS

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ftplib.FTP_TLS(host='', user='', passwd='', acct='', *, context=None, ...)` | O(c + r) | O(c + r) | As `FTP`; `login()` secures the control connection first unless called with `secure=False` |
| `FTP_TLS.auth()` | O(r) | O(r) | Sends `AUTH TLS` and wraps the control connection; raises `ValueError` if it is already secured |
| `FTP_TLS.prot_p()` | O(r) | O(r) | Sends `PBSZ 0` and `PROT P`; from then on every data connection is wrapped in TLS, one handshake per transfer |
| `FTP_TLS.prot_c()` | O(r) | O(r) | Data connections go back to clear text, which is the default |
| `FTP_TLS.ccc()` | O(r) | O(r) | Returns the control connection to clear text |
| `FTP_TLS.ssl_version` | O(1) | O(1) | Python 3.10 and 3.11 only |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ftplib.error_reply` | O(1) | O(1) | A reply of a kind the call did not expect |
| `ftplib.error_temp`, `ftplib.error_perm` | O(1) | O(1) | A `4xx` or a `5xx` reply |
| `ftplib.error_proto` | O(1) | O(1) | A reply that does not begin with a digit from 1 to 5 |
| `ftplib.all_errors` | O(1) | O(1) | A tuple of `ftplib.Error`, the base class of the four above, `OSError` and `EOFError`, plus `ssl.SSLError` where `ssl` is available |

## Transferring Files

### Streaming Downloads and Uploads

`retrbinary()` hands each block to its callback as it arrives and keeps nothing, so a callback that
writes to disk or updates a hash holds one block. It is the callback that decides whether the
download is held whole. `storbinary()` is the mirror image: it reads `fp` a block at a time.

```python
import ftplib
import hashlib
import io

with ftplib.FTP('ftp.example.com', 'anonymous') as ftp:  # connects and logs in
    with open('archive.bin', 'wb') as f:
        ftp.retrbinary('RETR /pub/archive.bin', f.write)  # O(b) time, O(k) memory

    digest = hashlib.sha256()
    ftp.retrbinary('RETR /pub/archive.bin', digest.update)  # O(k) memory: hashed block by block

    # Collecting the blocks instead holds the whole file
    buffer = io.BytesIO()
    ftp.retrbinary('RETR /pub/archive.bin', buffer.write)  # O(b) time and memory
    assert hashlib.sha256(buffer.getvalue()).digest() == digest.digest()

    # Uploading reads the file a block at a time
    with open('archive.bin', 'rb') as f:
        ftp.storbinary('STOR /upload/archive.bin', f)  # O(b) time, O(k) memory
    assert ftp.size('/upload/archive.bin') == len(buffer.getvalue())  # O(c + r)
```

### Resuming a Download

`rest` asks the server to start at an offset, so a resumed download moves only the bytes still
missing. `transfercmd()` returns the data socket itself and leaves reading it, and collecting the
server's final reply, to you.

```python
import ftplib
import os

with ftplib.FTP('ftp.example.com', 'anonymous') as ftp:
    ftp.voidcmd('TYPE I')  # O(c + r) - binary mode, as retrbinary() sets it

    # Read the start of the file from the data connection, then stop
    with ftp.transfercmd('RETR /pub/archive.bin') as conn, open('archive.bin', 'wb') as f:
        f.write(conn.recv(65536))  # at most 64 KiB
    try:
        ftp.voidresp()  # the reply to the RETR cut short
    except ftplib.error_temp:
        pass  # 426: the server saw the data connection close

    # Resume where the file on disk ends
    with open('archive.bin', 'ab') as f:
        ftp.retrbinary('RETR /pub/archive.bin', f.write, rest=f.tell())  # O(b) - the rest only

    assert os.path.getsize('archive.bin') == ftp.size('/pub/archive.bin')
```

### Line Mode and the Line Limit

`retrlines()` and `storlines()` work a line at a time, and read each line, its ending included,
with a cap: 8,192 characters for `retrlines()` and 8,192 bytes for `storlines()`, so a line of
multibyte text reaches the upload cap sooner. A longer line raises `ftplib.Error`, the base class
of the four `error_*` exceptions, instead of growing without bound. `storlines()` needs a binary
file.

```python
import ftplib
import io

with ftplib.FTP('ftp.example.com', 'anonymous') as ftp:
    lines = []
    ftp.retrlines('RETR /pub/notes.txt', lines.append)  # O(b) time, O(l) memory
    assert lines == ['one', 'two', 'three']

    ftp.storlines('STOR /upload/more.txt', io.BytesIO(b'four\nfive\n'))  # O(b), O(l)
    uploaded = []
    ftp.retrlines('RETR /upload/more.txt', uploaded.append)
    assert uploaded == ['four', 'five']

    try:
        ftp.storlines('STOR /upload/long.txt', io.BytesIO(b'x' * 10_000 + b'\n'))
    except ftplib.Error as error:
        assert 'got more than 8192 bytes' in str(error)
        ftp.voidresp()  # the reply to the abandoned STOR
    else:
        raise AssertionError('a 10,000-character line was sent')
```

## Listing Directories

The three listing calls cost the same O(b) to run and differ in what they hold. `dir()` passes each
line on and keeps none. `nlst()` returns every name in one list. `mlsd()` is a generator, but that
buys nothing in memory: its first `next()` reads the whole listing before yielding the first entry.

```python
import ftplib

with ftplib.FTP('ftp.example.com', 'anonymous') as ftp:
    names = ftp.nlst('/pub')  # O(b) time and memory - the whole listing
    assert names == ['archive.bin', 'notes.txt', 'readme.txt']

    long_form = []
    ftp.dir('/pub', long_form.append)  # O(b) time, O(l) memory beyond what the callback keeps
    assert len(long_form) == 3

    entries = ftp.mlsd('/pub', facts=['type', 'size'])  # O(1) - nothing is sent yet
    name, facts = next(entries)  # O(b) - the whole listing is read here
    assert name == 'archive.bin' and facts['size'] == '1048576'
    assert {name: facts['type'] for name, facts in entries} == {
        'notes.txt': 'file',
        'readme.txt': 'file',
    }
```

## Commands and Replies

Each command is one line out and one reply back, so its client-side cost is the length of the two.
A `4xx` or `5xx` reply raises rather than returning, and `voidcmd()` also raises on anything other
than `2xx`.

```python
import ftplib

with ftplib.FTP('ftp.example.com', 'anonymous') as ftp:
    assert ftp.getwelcome().startswith('220')  # O(1) - read by connect()

    assert ftp.mkd('/upload/reports') == '/upload/reports'  # O(c + r)
    ftp.cwd('/upload/reports')  # O(c + r)
    assert ftp.pwd() == '/upload/reports'
    ftp.cwd('..')  # sends CDUP
    assert ftp.pwd() == '/upload'
    assert ftp.rmd('reports').startswith('250')

    assert ftp.sendcmd('NOOP').startswith('200')  # O(c + r) - returns the reply

    try:
        ftp.cwd('/missing')
    except ftplib.error_perm as error:  # a 5xx reply
        assert str(error).startswith('550')
    else:
        raise AssertionError('a missing directory was entered')
```

## Secure Connections

`FTP_TLS` secures the control connection when you log in, but data connections stay in clear text
until `prot_p()`. After it, every transfer and listing pays a TLS handshake for its own data
connection.

```python
import ftplib
import ssl

context = ssl.create_default_context()
with ftplib.FTP_TLS('ftp.example.com', context=context) as ftps:
    ftps.login('anonymous')  # AUTH TLS first, then USER and PASS
    ftps.prot_p()  # O(r) - data connections are encrypted from here on
    assert 'readme.txt' in ftps.nlst('/pub')  # O(b), plus a handshake for this listing
```

## Common Patterns

### Mirroring a Directory

Every file is a transfer of its own, so a directory of n files costs n + 1 data connections: one for
the listing and one per file. Keep the control connection open across them rather than logging in
again for each.

```python
import ftplib
import pathlib

target = pathlib.Path('mirror')
target.mkdir()

with ftplib.FTP('ftp.example.com', 'anonymous') as ftp:
    ftp.cwd('/pub')
    for name in ftp.nlst():  # one data connection for the listing
        with open(target / name, 'wb') as f:
            ftp.retrbinary(f'RETR {name}', f.write)  # and one per file

assert sorted(path.name for path in target.iterdir()) == ['archive.bin', 'notes.txt', 'readme.txt']
```

## Performance Best Practices

✅ **Do**:

- Give `retrbinary()` a callback that writes or hashes each block, so memory stays at one block
- Pass a file object to `storbinary()` rather than reading it into memory first
- Resume an interrupted download with `rest`, which moves only the missing bytes
- Use `dir()` with a callback to scan a large directory; it holds one line at a time
- Reuse one logged-in connection for many transfers

❌ **Avoid**:

- Collecting a large download in a `BytesIO` or a list, which costs O(b) memory
- Treating `mlsd()` as lazy: it holds the whole listing once iteration starts
- Relying on `FTP_TLS` alone to protect file contents; call `prot_p()` after logging in

## Version Notes

- **Python 3.12+**: `FTP_TLS` no longer takes `keyfile` or `certfile`, `context` is keyword-only,
  and `FTP_TLS.ssl_version` is gone; pass an `ssl.SSLContext` as `context`

## Related Modules

- **[socket](socket.md)** - the connections every command and transfer runs over
- **[ssl](ssl.md)** - the `SSLContext` that `FTP_TLS` takes
- **[shutil](shutil.md)** - `copyfileobj()` for moving the downloaded file on locally
- **[netrc](netrc.md)** - reading FTP login details from a `.netrc` file
