# ssl Module Complexity

The `ssl` module puts a TLS layer between your code and a byte stream. Almost all of it is a thin
wrapper over OpenSSL: a context holds the settings and the trust material, a connection object holds
one handshake's worth of state, and every byte that crosses the boundary is encrypted or decrypted
once. The module itself buffers nothing beyond the record it is working on.

The unit of work is the TLS record, which carries at most 16384 bytes of plaintext. That number
governs both directions: a write is cut into records, and a read delivers at most one of them. The
other cost that matters is the trust store, because a context that verifies peers has to hold - or
be able to find - the certificates it verifies against.

`n` is the bytes handed to or taken from one call, `r` is the records they occupy
(`r = ⌈n / 16384⌉`), `c` is the certificates in a chain - the one a peer presents, or the one you
load in order to present it - `t` is the certificates in a context's trust store, `k` is the bytes
in one encoded certificate, `q` is the length of a cipher list, and `p` is the bytes in an ALPN
protocol list. A public-key operation counts as
O(1): its cost is set by the key, which is fixed for a given certificate, not by anything the caller
passes. Network round trips are outside every bound on this page.

## Complexity Reference

### SSLContext

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ssl.SSLContext(protocol=None)` | O(1) | O(1) | A fresh OpenSSL context with no trust material and no certificate |
| `ssl.create_default_context(purpose=Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None)` | O(t·k) | O(t·k) | Parses the trust material it is given; with none, it falls back to the platform's default paths |
| `SSLContext.load_cert_chain(certfile, keyfile=None, password=None)` | O(c·k) | O(c·k) | Parses the leaf, every chain certificate after it in the file, and the private key |
| `SSLContext.load_verify_locations(cafile=None, capath=None, cadata=None)` | O(t·k) | O(t·k) | `cafile` and `cadata` parse every certificate now; `capath` registers a hashed directory and reads nothing until a chain needs a name from it |
| `SSLContext.load_default_certs(purpose=Purpose.SERVER_AUTH)` | O(t·k) | O(t·k) | `set_default_verify_paths()`, preceded on Windows by the system certificate stores |
| `SSLContext.set_default_verify_paths()` | O(t·k) | O(t·k) | A default bundle file is parsed; a default hashed directory is only registered |
| `SSLContext.get_ca_certs(binary_form=False)` | O(t·k) | O(t·k) | Walks the store and builds a fresh dictionary, or fresh DER bytes, per CA certificate |
| `SSLContext.cert_store_stats()` | O(t) | O(1) | Walks the store to count it; three integers out. Certificates a `capath` directory has not been asked for are not in the count |
| `SSLContext.session_stats()` | O(1) | O(1) | A fixed set of counters, whatever the cache holds |
| `SSLContext.get_ciphers()` | O(q) | O(q) | Not a stored list: a fresh dictionary per enabled cipher on every call |
| `SSLContext.set_ciphers(ciphers)` | O(q) | O(1) | OpenSSL re-evaluates the cipher string against its table. TLS 1.3 suites are not selected by it |
| `SSLContext.set_alpn_protocols(alpn_protocols)` | O(p) | O(p) | Each name is length-prefixed into one buffer |
| `SSLContext.set_npn_protocols(npn_protocols)` | O(p) | O(p) | Deprecated since 3.10, and raises `AttributeError` where OpenSSL was built without NPN |
| `SSLContext.wrap_socket(sock, server_side=False, do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=None, session=None)` | O(1), plus the handshake if `sock` is connected | O(1) | Takes over the descriptor; on an already-connected socket it goes straight into `do_handshake()` unless `do_handshake_on_connect` is false |
| `SSLContext.wrap_bio(incoming, outgoing, server_side=False, server_hostname=None, session=None)` | O(1) | O(1) | Nothing is negotiated, and no byte reaches either BIO, until `do_handshake()` |
| `SSLContext.set_servername_callback(server_name_callback)` | O(1) | O(1) | Registers a shim; the callback then runs once per server-side handshake |
| `SSLContext.sni_callback` | O(1) | O(1) | The same hook without the hostname-decoding shim |
| `SSLContext.set_psk_client_callback(callback)`, `SSLContext.set_psk_server_callback(callback, identity_hint=None)` | O(1) | O(1) | Python 3.13+; the callback runs once per handshake |
| `SSLContext.load_dh_params(path)` | O(k) | O(1) | Reads one PEM parameter file |
| `SSLContext.set_ecdh_curve(curve_name)` | O(1) | O(1) | Names a curve by string |
| `SSLContext.keylog_filename` | O(1) | O(1) | Setting it opens the file, and every later handshake appends its secrets to it |
| `SSLContext.check_hostname`, `SSLContext.verify_mode`, `SSLContext.verify_flags`, `SSLContext.options`, `SSLContext.protocol`, `SSLContext.minimum_version`, `SSLContext.maximum_version`, `SSLContext.num_tickets`, `SSLContext.post_handshake_auth`, `SSLContext.security_level`, `SSLContext.hostname_checks_common_name` | O(1) | O(1) | Settings on the context: they change what a later handshake does, not what reading them costs |

### SSLSocket

`SSLSocket` is a `socket` subclass, so everything a plain socket does is still available; the rows
below are the methods TLS changes.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SSLSocket.do_handshake(block=False)` | O(c·k) | O(c·k) | Parses and verifies the chain the peer presents, certificate by certificate; the path that verifies can be shorter than what was sent. Round trips and the key exchange are what dominate the clock |
| `SSLSocket.read(len=1024, buffer=None)`, `SSLSocket.recv(buflen=1024, flags=0)` | O(min(len, 16384)) | O(len) | Returns data from at most one application-data record, so a large `len` never yields more than 16384 bytes - but the buffer is allocated at the size you ask for and only then shrunk to what arrived. Pass `buffer` and the space is the caller's |
| `SSLSocket.recv_into(buffer, nbytes=None, flags=0)` | O(min(nbytes, 16384)) | O(1) | Decrypts into the caller's buffer instead of a new one |
| `SSLSocket.write(data)`, `SSLSocket.send(data, flags=0)` | O(n) | O(1) | Cut into r records, each with its own header and authentication tag, and each handed to the socket before the next is built. Non-zero `flags` raise `ValueError` |
| `SSLSocket.sendall(data, flags=0)` | O(n) | O(1) | Loops `send()` over a `memoryview` until the whole buffer is gone |
| `SSLSocket.sendfile(file, offset=0, count=None)` | O(n) | O(1) | The kernel's zero-copy path needs a plain socket, so a TLS socket reads and sends the file in fixed-size blocks |
| `SSLSocket.pending()` | O(1) | O(1) | Bytes already decrypted and waiting: what is left of the record the last read touched, not what the transport still holds |
| `SSLSocket.getpeercert(binary_form=False)` | O(k) | O(k) | Builds a fresh dictionary, or a fresh DER copy, on every call |
| `SSLSocket.get_verified_chain()`, `SSLSocket.get_unverified_chain()` | O(c·k) | O(c·k) | Python 3.13+; re-encodes every certificate in the chain to DER on each call |
| `SSLSocket.cipher()`, `SSLSocket.version()`, `SSLSocket.compression()`, `SSLSocket.selected_alpn_protocol()` | O(1) | O(1) | Read from the negotiated connection; `None` before the handshake |
| `SSLSocket.selected_npn_protocol()` | O(1) | O(1) | Returns `None` on every supported version; deprecated since 3.10 |
| `SSLSocket.shared_ciphers()` | O(q²) | O(q) | Server side only: the ciphers both ends have in common, found by scanning one list for each entry of the other. `None` on a client socket |
| `SSLSocket.get_channel_binding(cb_type='tls-unique')` | O(1) | O(1) | A fixed-size value; `None` before the handshake, `ValueError` for an unknown type |
| `SSLSocket.verify_client_post_handshake()` | O(1) | O(1) | Only flags the request. The certificate exchange happens on the next write, and the verification cost lands there |
| `SSLSocket.unwrap()` | O(1) | O(1) | Exchanges `close_notify` and returns *this* socket with the TLS layer dropped - the same object, reading and writing in the clear from then on |
| `SSLSocket.shutdown(how)` | O(1) | O(1) | Drops the TLS layer before shutting the socket down, so no `close_notify` is sent and the peer cannot tell a close from a truncation |
| `SSLSocket.accept()` | O(1), plus the handshake | O(1) | Accepts, then wraps the new socket with the same context and the server's `do_handshake_on_connect` |
| `SSLSocket.connect(addr)`, `SSLSocket.connect_ex(addr)` | O(1), plus the handshake | O(1) | The handshake runs here when `do_handshake_on_connect` is set |
| `SSLSocket.dup()` | O(1) | O(1) | Raises `NotImplementedError`: two file descriptors cannot share one TLS state |
| `SSLSocket.sendmsg(...)`, `SSLSocket.recvmsg(...)`, `SSLSocket.recvmsg_into(...)` | O(1) | O(1) | Raise `NotImplementedError` so nothing leaves unencrypted by accident |
| `SSLSocket.sendto(...)`, `SSLSocket.recvfrom(...)`, `SSLSocket.recvfrom_into(...)` | O(1) | O(1) | Raise `ValueError` once the socket is wrapped; they pass through while it is not |
| `SSLSocket.context`, `SSLSocket.server_side`, `SSLSocket.server_hostname`, `SSLSocket.session`, `SSLSocket.session_reused` | O(1) | O(1) | Attributes of the wrapped connection |

### SSLObject

`SSLObject` is the same TLS engine reading from and writing to a pair of `MemoryBIO` objects instead
of a socket. Every method it shares with `SSLSocket` reaches the same code and costs the same; it
has no socket methods at all, so there is no `recv`, `sendall` or `sendfile`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SSLObject.read(len=1024, buffer=None)` | O(min(len, 16384)) | O(len) | One application-data record at most, and the same allocate-then-shrink as on a socket; `buffer` moves the space to the caller and returns a count |
| `SSLObject.write(data)` | O(b + n) | O(b + n) | b = bytes already waiting in the outgoing BIO. All r records land there and stay until you read them, so this side does hold the whole write - and appending after a partial drain moves the backlog first, exactly as `MemoryBIO.write()` does |
| `SSLObject.do_handshake()` | O(c·k) | O(c·k) | As on a socket, and raises `SSLWantReadError` each time it needs bytes the incoming BIO does not have yet |
| `SSLObject.unwrap()` | O(1) | O(1) | Writes `close_notify`; raises `SSLWantReadError` until the peer's arrives |
| `SSLObject.pending()`, `SSLObject.cipher()`, `SSLObject.version()`, `SSLObject.compression()`, `SSLObject.selected_alpn_protocol()`, `SSLObject.selected_npn_protocol()`, `SSLObject.get_channel_binding(cb_type='tls-unique')`, `SSLObject.verify_client_post_handshake()` | O(1) | O(1) | As on `SSLSocket` |
| `SSLObject.getpeercert(binary_form=False)` | O(k) | O(k) | A fresh dictionary or DER copy per call |
| `SSLObject.get_verified_chain()`, `SSLObject.get_unverified_chain()` | O(c·k) | O(c·k) | Python 3.13+ |
| `SSLObject.shared_ciphers()` | O(q²) | O(q) | Server side only |
| `SSLObject.context`, `SSLObject.session`, `SSLObject.session_reused`, `SSLObject.server_side`, `SSLObject.server_hostname` | O(1) | O(1) | Attributes of the wrapped connection |

### MemoryBIO

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ssl.MemoryBIO()` | O(1) | O(1) | An empty buffer |
| `MemoryBIO.write(buf)` | O(b + len(buf)) | O(b + len(buf)) | b = bytes still unread. A write after a *partial* read moves the unread remainder to the front of the buffer first, so drain with `read()` before writing again. Raises `SSLError` after `write_eof()` |
| `MemoryBIO.read(size=-1)` | O(m) | O(m) | m = `pending` when `size` is negative, otherwise min(size, `pending`). The default reads everything buffered and returns it as one `bytes` |
| `MemoryBIO.pending` | O(1) | O(1) | Bytes waiting to be read |
| `MemoryBIO.eof` | O(1) | O(1) | True only once `write_eof()` has been called *and* the buffer is drained |
| `MemoryBIO.write_eof()` | O(1) | O(1) | Marks the end so an empty read means EOF rather than "nothing yet" |

### SSLSession

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ssl.SSLSession` | O(1) | O(1) | Not constructed directly: read one off a connection and hand it back to `wrap_socket()` or `wrap_bio()` |
| `SSLSession.id` | O(1) | O(1) | The session identifier as bytes |
| `SSLSession.time`, `SSLSession.timeout`, `SSLSession.ticket_lifetime_hint` | O(1) | O(1) | When the session was established, and how long it may be reused |
| `SSLSession.has_ticket` | O(1) | O(1) | Whether the session carries a resumption ticket |

### Certificate and randomness helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ssl.DER_cert_to_PEM_cert(der_cert_bytes)` | O(k) | O(k) | Base64 plus a line break every 64 characters |
| `ssl.PEM_cert_to_DER_cert(pem_cert_string)` | O(k) | O(k) | Rejects a string without the exact header and footer |
| `ssl.cert_time_to_seconds(cert_time)` | O(1) | O(1) | A fixed-width GMT timestamp from a certificate's `notBefore` or `notAfter` |
| `ssl.get_server_certificate(addr, ssl_version=PROTOCOL_TLS_CLIENT, ca_certs=None, timeout=...)` | O(k), plus a full connection | O(k) | Builds a context, connects, handshakes, and keeps the leaf certificate only |
| `ssl.get_default_verify_paths()` | O(1) | O(1) | Two environment lookups and two stat calls |
| `ssl.RAND_bytes(num)` | O(num) | O(num) | Cryptographically strong bytes from OpenSSL |
| `ssl.RAND_add(bytes, entropy)` | O(len(bytes)) | O(1) | Mixes the buffer into OpenSSL's pool |
| `ssl.RAND_status()` | O(1) | O(1) | Whether the pool is seeded |
| `ssl.get_protocol_name(protocol_code)` | O(1) | O(1) | Dictionary lookup; `'<unknown>'` for an unrecognised code |
| `ssl.enum_certificates(store_name)`, `ssl.enum_crls(store_name)` | O(t·k) | O(t·k) | Windows only: reads a whole system store |

### Constants and enumerations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ssl.Purpose.SERVER_AUTH`, `ssl.Purpose.CLIENT_AUTH` | O(1) | O(1) | Existing enum members that name an extended key usage |
| `ssl.Purpose.fromnid(nid)`, `ssl.Purpose.fromname(name)` | O(1) | O(1) | One OpenSSL object lookup, returning a fresh four-field tuple |
| `Purpose.nid`, `Purpose.shortname`, `Purpose.longname`, `Purpose.oid` | O(1) | O(1) | Named tuple fields |
| `ssl.DefaultVerifyPaths` | O(1) | O(1) | The named tuple `get_default_verify_paths()` returns |
| `DefaultVerifyPaths.cafile`, `DefaultVerifyPaths.capath`, `DefaultVerifyPaths.openssl_cafile`, `DefaultVerifyPaths.openssl_capath`, `DefaultVerifyPaths.openssl_cafile_env`, `DefaultVerifyPaths.openssl_capath_env` | O(1) | O(1) | The first two are `None` unless the path exists |
| `ssl.VerifyMode`, `ssl.VerifyFlags`, `ssl.Options`, `ssl.AlertDescription`, `ssl.SSLErrorNumber` | O(1) | O(1) | Enumerations over the `CERT_*`, `VERIFY_*`, `OP_*`, `ALERT_DESCRIPTION_*` and `SSL_ERROR_*` constants; a lookup returns the member that already exists |
| `ssl.TLSVersion` | O(1) | O(1) | The protocol versions `minimum_version` and `maximum_version` take - wire versions, plus the `MINIMUM_SUPPORTED` and `MAXIMUM_SUPPORTED` sentinels - not the `PROTOCOL_*` selectors |
| `ssl.CERT_NONE`, `ssl.CERT_OPTIONAL`, `ssl.CERT_REQUIRED` | O(1) | O(1) | Values for `SSLContext.verify_mode` |
| `ssl.PROTOCOL_TLS_CLIENT`, `ssl.PROTOCOL_TLS_SERVER`, `ssl.PROTOCOL_TLS`, `ssl.PROTOCOL_SSLv23`, `ssl.PROTOCOL_TLSv1`, `ssl.PROTOCOL_TLSv1_1`, `ssl.PROTOCOL_TLSv1_2` | O(1) | O(1) | Only the first two are current; the rest are deprecated since 3.10. `ssl.PROTOCOL_SSLv3` exists only where OpenSSL was built with SSLv3 |
| `ssl.OP_ALL`, `ssl.OP_NO_TLSv1_3`, `ssl.OP_NO_TICKET`, `ssl.OP_NO_COMPRESSION`, `ssl.OP_NO_RENEGOTIATION`, `ssl.OP_CIPHER_SERVER_PREFERENCE`, `ssl.OP_SINGLE_DH_USE`, `ssl.OP_SINGLE_ECDH_USE`, `ssl.OP_ENABLE_MIDDLEBOX_COMPAT`, `ssl.OP_ENABLE_KTLS`, `ssl.OP_IGNORE_UNEXPECTED_EOF`, `ssl.OP_LEGACY_SERVER_CONNECT`, and the rest of the `OP_NO_*` family | O(1) | O(1) | Bit flags for `SSLContext.options`; they change what a handshake does, not what setting them costs. `OP_IGNORE_UNEXPECTED_EOF` arrived in 3.10 and `OP_ENABLE_KTLS` and `OP_LEGACY_SERVER_CONNECT` in 3.12. The first two also need an OpenSSL that defines them |
| `ssl.VERIFY_DEFAULT`, `ssl.VERIFY_CRL_CHECK_LEAF`, `ssl.VERIFY_CRL_CHECK_CHAIN`, `ssl.VERIFY_X509_STRICT`, `ssl.VERIFY_X509_TRUSTED_FIRST`, `ssl.VERIFY_X509_PARTIAL_CHAIN`, `ssl.VERIFY_ALLOW_PROXY_CERTS` | O(1) | O(1) | Bit flags for `SSLContext.verify_flags`. The CRL flags require revocation lists to be checked; OpenSSL does not fetch them, so load them into the store yourself |
| `ssl.HAS_ALPN`, `ssl.HAS_NPN`, `ssl.HAS_ECDH`, `ssl.HAS_SNI`, `ssl.HAS_PSK`, `ssl.HAS_PHA`, `ssl.HAS_NEVER_CHECK_COMMON_NAME`, `ssl.HAS_SSLv2`, `ssl.HAS_SSLv3`, `ssl.HAS_TLSv1`, `ssl.HAS_TLSv1_1`, `ssl.HAS_TLSv1_2`, `ssl.HAS_TLSv1_3` | O(1) | O(1) | What the linked OpenSSL supports, decided at import |
| `ssl.OPENSSL_VERSION`, `ssl.OPENSSL_VERSION_INFO`, `ssl.OPENSSL_VERSION_NUMBER` | O(1) | O(1) | The linked library's version, in three shapes |
| `ssl.CHANNEL_BINDING_TYPES` | O(1) | O(1) | The types `get_channel_binding()` accepts |
| `ssl.PEM_HEADER`, `ssl.PEM_FOOTER` | O(1) | O(1) | The lines the conversion helpers write and require |
| `ssl.SSL_ERROR_WANT_READ`, `ssl.SSL_ERROR_WANT_WRITE`, `ssl.SSL_ERROR_ZERO_RETURN`, `ssl.SSL_ERROR_EOF`, `ssl.SSL_ERROR_SSL`, `ssl.SSL_ERROR_SYSCALL`, `ssl.SSL_ERROR_WANT_CONNECT`, `ssl.SSL_ERROR_WANT_X509_LOOKUP`, `ssl.SSL_ERROR_INVALID_ERROR_CODE` | O(1) | O(1) | The codes behind the `SSLError` subclasses |
| `ssl.ALERT_DESCRIPTION_CLOSE_NOTIFY`, `ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE`, `ssl.ALERT_DESCRIPTION_BAD_CERTIFICATE`, `ssl.ALERT_DESCRIPTION_CERTIFICATE_EXPIRED`, `ssl.ALERT_DESCRIPTION_UNKNOWN_CA`, and the other `ALERT_DESCRIPTION_*` values | O(1) | O(1) | Alert codes a peer can send, for use in an SNI callback's return value |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ssl.SSLError` | O(1) | O(1) | An `OSError` subclass raised for any OpenSSL failure |
| `SSLError.library`, `SSLError.reason` | O(1) | O(1) | Short strings naming the OpenSSL submodule and error |
| `ssl.SSLCertVerificationError`, `ssl.CertificateError` | O(1) | O(1) | The same class under two names; raised when the chain does not verify |
| `SSLCertVerificationError.verify_code`, `SSLCertVerificationError.verify_message` | O(1) | O(1) | OpenSSL's numeric verification result and its text |
| `ssl.SSLWantReadError`, `ssl.SSLWantWriteError` | O(1) | O(1) | The engine needs more bytes, or room to write them: retry, do not treat as failure |
| `ssl.SSLZeroReturnError` | O(1) | O(1) | The peer closed the TLS layer cleanly |
| `ssl.SSLSyscallError`, `ssl.SSLEOFError` | O(1) | O(1) | The transport failed under the TLS layer |

## Setting Up a Context

A context is where the expensive, reusable work lives: trust material, the certificate you present,
the cipher list. Build one and share it between connections. Building a bare `SSLContext` costs
nothing; what costs is the trust material you then load into it.

```python
import ssl

context = ssl.create_default_context()  # O(t·k) over whatever trust material it finds
assert context.check_hostname is True
assert context.verify_mode is ssl.CERT_REQUIRED
assert context.minimum_version >= ssl.TLSVersion.TLSv1_2

bare = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # O(1) - no trust material at all
assert bare.cert_store_stats() == {'x509': 0, 'crl': 0, 'x509_ca': 0}  # O(t)
assert bare.verify_mode is ssl.CERT_REQUIRED and bare.check_hostname is True
```

### Eager and Lazy Trust Material

`load_verify_locations()` treats its three arguments differently. `cafile` and `cadata` are parsed
on the spot, so the store grows by every certificate in them. `capath` registers a directory whose
files are named after a hash of their subject, and OpenSSL opens one only when a chain asks for that
subject. For a system trust store of a few hundred certificates that is the difference between
parsing all of them and parsing the two a connection actually needs.

```python
import ssl
import tempfile

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
with tempfile.TemporaryDirectory() as directory:
    context.load_verify_locations(capath=directory)  # O(1) - the directory is registered

# Registration alone puts nothing in the store; a certificate in the directory
# is opened when a chain names its subject, not now
assert context.cert_store_stats()['x509'] == 0  # O(t)
assert context.get_ca_certs() == []             # O(t·k)
```

### Ciphers

`get_ciphers()` is not a free attribute read: it builds a throwaway connection object to ask OpenSSL
what the context would offer, then a fresh dictionary per cipher. Call it when you are auditing a
context, not inside a loop.

```python
import ssl

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
enabled = context.get_ciphers()  # O(q)
assert len(enabled) > 0
assert 'name' in enabled[0] and 'protocol' in enabled[0]

# Every call rebuilds the dictionaries rather than handing back the same ones
again = context.get_ciphers()  # O(q)
assert again[0] is not enabled[0]
assert again[0] == enabled[0]
```

## The Handshake

Wrapping is cheap; negotiating is not. `wrap_bio()` always returns without moving a byte, and so
does `wrap_socket()` on a socket that is not yet connected. On a *connected* socket, though,
`wrap_socket()` runs the whole handshake before it returns, because `do_handshake_on_connect`
defaults to true - so the cost of the handshake shows up at the wrapping call, not at the first
`send()`.

```python
import ssl

context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
client = context.wrap_bio(incoming, outgoing, server_hostname='example.com')  # O(1)
assert outgoing.pending == 0   # nothing has been negotiated yet
assert client.version() is None

try:
    client.do_handshake()  # O(c) once a peer answers
except ssl.SSLWantReadError:
    pass  # the ClientHello is out; the rest waits on the peer
else:
    raise AssertionError('the handshake completed without a peer')

assert outgoing.pending > 0  # the ClientHello is sitting in the outgoing BIO
```

### Chain Verification

A peer sends a chain, and verification works along it until it reaches something the trust store
holds. The cost of a handshake therefore carries a c term, and `get_verified_chain()` costs c
certificates' worth of DER every time it is called - it re-encodes them rather than returning what
it built during the handshake.

## Reading and Writing Through TLS

### Records and Reads

`read()` and `recv()` return data from at most one application-data record, whatever length you ask
for. Asking for 100000 bytes does not save you a call: you get at most 16384 back, and `pending()`
tells you what is left of the record you just touched - not what the transport is still holding.

Asking for more is not free either. Without a `buffer` argument the result object is allocated at
the length you asked for and only then shrunk to what arrived, so `read(10_000_000)` allocates ten
megabytes to hand you 16384 bytes. Read in record-sized pieces, or pass a buffer and reuse it.

Write is the mirror image. `write()` accepts the whole buffer and returns its full length, cutting
it into `⌈n / 16384⌉` records on the way out, each with its own header and authentication tag. One
large write therefore carries the same application bytes in fewer records - and so in fewer bytes
on the wire - than the same payload written in small pieces, each of which pays for a record of its
own.

On a socket, each record goes out as it is built, so the encrypted copy never exists whole - a
write larger than the peer is reading blocks rather than buffering. Over a `MemoryBIO` there is
nowhere for it to go, so the whole encrypted write waits in the outgoing buffer until you take it.
`sendall()` is the loop `send()` would need around a partial write; it adds nothing to either
bound.

## In-Memory TLS with MemoryBIO

`MemoryBIO` is a plain byte buffer with an EOF flag, and `wrap_bio()` is how you drive TLS over a
transport the module does not own - an asyncio protocol, a tunnel, a test.

Drain a BIO with a bare `read()` rather than in pieces. A write that follows a partial read has to
move whatever is still unread to the front of the buffer first, which turns a one-byte write into
work proportional to the backlog.

```python
import ssl

bio = ssl.MemoryBIO()          # O(1)
assert bio.pending == 0 and bio.eof is False

bio.write(b'hello')            # O(n)
assert bio.pending == 5

assert bio.read(2) == b'he'    # O(min(size, pending))
assert bio.pending == 3

bio.write_eof()                # O(1)
assert bio.eof is False        # not until the buffer is drained
assert bio.read() == b'llo'    # O(pending) - the default reads everything
assert bio.eof is True

try:
    bio.write(b'more')
except ssl.SSLError as error:
    assert 'write_eof' in str(error)
else:
    raise AssertionError('a write after write_eof was accepted')
```

## Session Resumption

A resumed handshake skips the certificate exchange, so the c term and the signature checks go with
it: `get_verified_chain()` comes back empty on the resumed connection, while `getpeercert()` still
answers out of the session the client replayed. Keep the `session` from a finished connection and
hand it to the next `wrap_socket()` or `wrap_bio()` against the same server; `session_reused` says
whether the server took it.

## Certificate Encoding Helpers

`DER_cert_to_PEM_cert()` and `PEM_cert_to_DER_cert()` are base64 in each direction, linear in the
certificate and nothing more - no parsing, no validation of the contents.

```python
import ssl

der = bytes(range(256)) * 2                 # stands in for a certificate body
pem = ssl.DER_cert_to_PEM_cert(der)         # O(k)
assert pem.startswith(ssl.PEM_HEADER)
assert pem.strip().endswith(ssl.PEM_FOOTER)
assert max(len(line) for line in pem.splitlines()[1:-1]) == 64

assert ssl.PEM_cert_to_DER_cert(pem) == der  # O(k)

try:
    ssl.PEM_cert_to_DER_cert('not a certificate')
except ValueError as error:
    assert 'PEM' in str(error)
else:
    raise AssertionError('a string without the header was decoded')
```

Certificate timestamps come out of `getpeercert()` as strings, and `cert_time_to_seconds()` turns
one into an epoch value in constant time.

```python
import ssl

assert ssl.cert_time_to_seconds('Jan  5 09:34:43 2018 GMT') == 1515144883  # O(1)

try:
    ssl.cert_time_to_seconds('2018-01-05 09:34:43')
except ValueError as error:
    assert 'time data' in str(error)
else:
    raise AssertionError('a non-certificate timestamp was parsed')
```

## Common Patterns

### One Context, Many Connections

```python
import ssl

context = ssl.create_default_context()  # O(t·k) once
context.set_alpn_protocols(['h2', 'http/1.1'])  # O(p)

# Every connection reuses the parsed trust store; wrapping itself is O(1)
for _ in range(3):
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    connection = context.wrap_bio(incoming, outgoing, server_hostname='example.com')
    assert connection.context is context
    assert connection.session_reused is False
```

### Fetching a Server's Certificate

```python
import ssl

# Connects, handshakes, and returns the leaf certificate as PEM - a full round trip
pem = ssl.get_server_certificate(('www.python.org', 443))  # O(k) plus the connection
der = ssl.PEM_cert_to_DER_cert(pem)                        # O(k)
assert len(der) > 0
```

## Performance Best Practices

✅ **Do**:

- Build one `SSLContext` and reuse it: the trust store is parsed once, and wrapping is O(1)
- Keep and replay a `session` when you reconnect to the same server, to skip the chain verification
- Point a large trust store at a `capath` directory rather than a bundle file: the directory is
  read on demand, the file is parsed in full
- Read in blocks of 16384 or less, or into a reused buffer: a bare `read(n)` allocates n bytes
  whatever it returns
- Hand `write()` the whole buffer and let it cut the records

❌ **Avoid**:

- Calling `create_default_context()` per connection - that is the O(t·k) parse, repeated
- Calling `get_ciphers()`, `get_ca_certs()` or `get_verified_chain()` in a loop: each one rebuilds
  its result from scratch
- Many small `write()` calls, which pay a record's header and tag for a handful of bytes
- Leaving `keylog_filename` set outside debugging - every handshake appends its secrets to the file
- `shutdown()` where `unwrap()` is meant: it leaves the peer unable to tell a close from a
  truncation

## Version Notes

- **Python 3.10+**: The module requires OpenSSL 1.1.1 or newer and defaults to TLS 1.2 as the
  minimum version. Reads and writes go through `SSL_read_ex`/`SSL_write_ex`, so a single call can
  carry more than 2 GB. `ssl.wrap_socket()`, `match_hostname()`, NPN and the version-specific
  `PROTOCOL_*` constants are deprecated; `VERIFY_X509_PARTIAL_CHAIN`, `VERIFY_ALLOW_PROXY_CERTS`,
  `OP_IGNORE_UNEXPECTED_EOF` and `SSLContext.security_level` are new
- **Python 3.12+**: `ssl.wrap_socket()`, `ssl.match_hostname()` and `ssl.RAND_pseudo_bytes()` are
  gone; `OP_LEGACY_SERVER_CONNECT` and `OP_ENABLE_KTLS` are new
- **Python 3.13+**: `get_verified_chain()` and `get_unverified_chain()` are added, TLS-PSK arrives
  with `set_psk_client_callback()` and `set_psk_server_callback()`, and `create_default_context()`
  sets `VERIFY_X509_PARTIAL_CHAIN` and `VERIFY_X509_STRICT`
- **Python 3.14+**: `HAS_PHA` reports whether post-handshake client authentication is available
- **All Python 3**: `SSLContext.wrap_socket()` on an already-connected socket performs the
  handshake before it returns, unless `do_handshake_on_connect=False` defers it

## Related Modules

- **[socket](socket.md)** - the transport underneath; `SSLSocket` is a subclass of it
- **[hashlib](hashlib.md)** - digests and key derivation, without a connection
- **[secrets](secrets.md)** - token generation; prefer it to `RAND_bytes()` in application code
- **[http](http.md)** - `http.client.HTTPSConnection` takes an `SSLContext` directly
- **[asyncio](asyncio.md)** - drives TLS through `MemoryBIO` and `SSLObject`
