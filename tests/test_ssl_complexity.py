"""Tests for docs/stdlib/ssl.md.

The page prices a TLS connection in records and certificates: a context pays
for the trust material it parses, a handshake pays for the chain the peer
presents, and every read and write is bounded by the 16384-byte record. None
of that needs a peer on the network. A pair of `MemoryBIO` objects carries a
real handshake between two contexts in one process, and the certificates it
runs on are the fixtures at the top of this file, so every count below is
exact rather than timed.

Measurement scope:

* Trust material is settled by `cert_store_stats()`, which counts what the
  store actually holds. A bare `SSLContext` holds nothing; the same
  certificate through `cadata` puts one certificate in the store; the same
  certificate in a directory registered as `capath`, under the subject-hash
  name OpenSSL looks it up by, leaves the store at zero and `get_ca_certs()`
  empty - and then a handshake that needs that root succeeds and puts it in
  the store. Registration being lazy and the certificate being usable are
  separate claims, and a wrong hash name fails the handshake rather than
  passing quietly. Loading the same `cadata` twice still leaves one
  certificate.
* `get_ca_certs()` and `getpeercert()` build their result per call: two calls
  return equal objects that are not the same object, so the O(t·k) and O(k)
  space is real work rather than a handed-back reference. `get_ciphers()` is
  the same, asserted on the first dictionary of the list.
* `wrap_bio()` negotiates nothing: the outgoing BIO is empty and `version()`
  is `None` after it returns, and the first `do_handshake()` raises
  `SSLWantReadError` with the ClientHello - and only the ClientHello - in the
  outgoing BIO. `wrap_socket()` on a connected socket is the opposite: against
  a peer that never answers, and a one-second timeout, the wrap call itself
  raises `TimeoutError`, while `do_handshake_on_connect=False` returns a
  socket whose `version()` is `None`.
* The chain term is settled by two handshakes with the same code: a server
  sending leaf and root against a client trusting the root gives
  `get_verified_chain()` of 2, and a server sending the leaf alone against a
  client trusting the leaf with `VERIFY_X509_PARTIAL_CHAIN` gives 1. A client
  trusting neither raises `SSLCertVerificationError` carrying `verify_code`
  and `verify_message`.
* One read carries one application-data record. 40,000 bytes written in one
  call come back as 16,384 from a `read(100000)`; a `read(100)` leaves
  `pending()` at 16,284, which is the remainder of that record and not the
  23,616 bytes still in the incoming BIO. `write()` returns the full 40,000.
  `read(len, buffer)` and `recv_into(buffer)` fill the caller's buffer with
  the same 16,384 and return a count.
* The read *space* is the length asked for, not the length returned:
  `read(10_000_000)` returning 16,384 bytes has a traced peak over 9 MB, and
  the same read into a caller buffer has a traced peak under a kilobyte on
  every supported version. Returned lengths alone cannot separate those two.
* `shared_ciphers()` is an intersection, settled with three TLS 1.2 suites:
  one the server alone enables, one the client alone enables, and one both do.
  Only the shared suite is reported, so neither "what the client offered" nor
  "what the server enabled" survives, and the result equals the intersection
  of the two enabled sets. The test asserts the one-sided suites really are
  one-sided before it draws that conclusion.
* Record framing is counted in the outgoing BIO: a 1-byte write costs a fixed
  per-record overhead, and writes of 16,384, 16,385, 32,768, 32,769 and
  100,000 bytes cost that overhead once per `⌈n / 16384⌉`. The overhead is
  measured from the 1-byte write rather than written down, so its value is not
  pinned to one cipher suite. The *count* still assumes the negotiated suite
  frames each record at a fixed cost, which the AEAD suites here do and a CBC
  suite, padding to a block, would not.
* Resumption is settled by handing a finished connection's `session` to the
  next `wrap_bio()`: `session_reused` is `False` on the first connection and
  `True` on the second, and the server context's `session_stats()['hits']`
  goes from 0 to 1. On 3.13 and later the resumed connection's
  `get_verified_chain()` is empty while `getpeercert()` still matches the
  first connection's, which is the certificate exchange being skipped rather
  than repeated.
* `verify_client_post_handshake()` writes nothing: the server's outgoing BIO
  holds the same number of bytes after the call as before, so the request is
  flagged and the exchange is deferred, as the row says.
* `SSLSocket` is driven over a `socket.socketpair()`, with the server side in
  a thread that is joined before anything is asserted. `recv(100000)` returns
  16,384 of a 40,000-byte `sendall()`. The O(1) space in the write row takes
  two measurements, because a timeout alone cannot separate "streams the
  records" from "encrypts everything, then blocks": a 100 MiB `write()` to a
  peer that is not reading raises `TimeoutError` at a one-second timeout
  *and* leaves the process's resident peak *during the call* within 50 MiB of
  where it started, with the payload already resident. The peak is sampled
  from a second thread reading /proc/self/statm, which sees what a reading
  taken afterwards would miss - a buffer freed on the way out - and what
  `ru_maxrss` would miss under an earlier high-water mark. A control test
  allocates and frees 100 MiB inside the same probe and asserts it is seen,
  so the write's flat reading is not a probe that cannot see anything. `sendall()` of 40,000 bytes reaches the
  instrumented `send` exactly once, so its loop adds nothing. `sendfile()` of
  a 20,000-byte file reaches `send` three times, none of them over 8,192
  bytes, which is the fixed block the page describes; the instrumented `send`
  is asserted to have been called. `sendmsg`, `recvmsg`, `recvmsg_into` and `dup` raise
  `NotImplementedError`, and `sendto`, `recvfrom` and `recvfrom_into` raise
  `ValueError` once the socket carries TLS.
* `shutdown(SHUT_RDWR)` leaves `version()` at `None`: the TLS state is
  cleared before the socket call, which is why no `close_notify` can follow
  it. `SSLObject.unwrap()` is the opposite - it writes bytes into the outgoing
  BIO and then raises `SSLWantReadError` waiting for the peer's answer - and
  `SSLSocket.unwrap()` hands back the same object, now with `version()` of
  `None`.
* `set_npn_protocols()` raises `AttributeError` where OpenSSL has no NPN,
  asserted under the deprecation warning and skipped on a build that still
  has it.
* `MemoryBIO` is asserted on `pending` and `eof` around `write`, `read` and
  `write_eof`, including that `eof` stays `False` until the buffer is drained
  and that a write after `write_eof()` raises `SSLError`. The b term in
  `write()` is timed rather than observed, because the memmove is OpenSSL's: a
  one-byte write after a one-byte read costs more than 8x as much over a
  32,000,000-byte backlog as over a 1,000,000-byte one, and more than 8x as
  much as the same write after a full `read()` drained the same backlog. The
  same term reaches `SSLObject.write()`, whose records land in that buffer: a
  one-byte SSL write after a one-byte drain costs more than 5x as much over a
  20,000,000-byte backlog as over a 1,000,000-byte one.
* The encoding helpers round-trip a real certificate, wrap at 64 characters,
  and raise `ValueError` for a string without the header. `cert_time_to_seconds`
  is asserted on a known timestamp and on a rejected one.
* Enumeration lookups return the member that already exists: `ssl.TLSVersion`,
  `ssl.VerifyMode`, `ssl.Purpose`, `ssl.Options`, `ssl.VerifyFlags`,
  `ssl.SSLErrorNumber` and `ssl.AlertDescription` are asserted by identity, so
  nothing is built. Identity does not time the lookup; the O(1) is `enum`'s
  value map in Lib/enum.py.
* Every fenced Python block except the one that opens a connection runs in its
  own subprocess and working directory, and a mutated assertion in one of them
  is asserted to fail.

Not settled here:

* Round trips. The page puts them outside every bound, and the in-process
  handshake here has none.
* `ssl.get_server_certificate()`, which needs a server to answer.
* `ssl.enum_certificates()` and `ssl.enum_crls()` are Windows-only and absent
  on this platform, so their O(t·k) row is unverified by any run this project
  performs. `ssl.PROTOCOL_SSLv3` needs an OpenSSL built with SSLv3 and is
  absent from this build, so the constant row covering it is unverified here
  too. `SSLContext.load_default_certs()` reaches the Windows certificate
  stores only on Windows.
* Whether a public-key operation is O(1). The page says so as a cost model:
  key size is fixed per certificate and no caller argument moves it.
* The handshake's O(c) is observed as the chain length the connection reports,
  not as c signature verifications. That OpenSSL checks one signature per link
  is read from the protocol, not measured.
* `SSLContext.keylog_filename`, `set_ecdh_curve()`,
  `set_psk_client_callback()`, `set_psk_server_callback()` and the SNI
  callbacks are asserted to be accepted and to leave the context usable, not
  measured over varying input. `load_dh_params()` is not exercised at all:
  it needs a parameter file this repository does not carry.
* `SSLSocket.accept()`, `connect()` and `connect_ex()` need a listening
  socket, so their rows follow Lib/ssl.py rather than a run: each one wraps
  with the same context and runs the handshake when `do_handshake_on_connect`
  is set.
* That a missing `close_notify` leaves a peer unable to distinguish a close
  from a truncation is a property of TLS, not of this module. What is checked
  here is that `shutdown()` clears the TLS state first.
* `get_verified_chain()` and `get_unverified_chain()` do not exist before
  3.13, so the chain-length pair skips on 3.10 through 3.12 and the
  handshake's c term is unverified on those versions. The PSK callbacks skip
  there for the same reason.
* The Version Notes are asserted against the running interpreter, so the
  matrix holds the page to the boundaries it names. Where an option also needs
  a particular OpenSSL - `OP_IGNORE_UNEXPECTED_EOF` and `OP_ENABLE_KTLS` sit
  behind `#ifdef`s while `OP_LEGACY_SERVER_CONNECT` does not - the Python
  boundary and the library condition are asserted separately, so a Python new
  enough for the name is not read as a promise that the build has it.
* A build linked against an OpenSSL these runs did not use. Five interpreters
  here all link OpenSSL 3.x, so the rows that say "where the linked OpenSSL
  defines it" are unverified against a 1.1.1 build.
* Whether `load_verify_locations()` costs more for input that repeats the same
  certificate. The page prices the store it builds, and repeated input is a
  pathological shape rather than the shape a bundle has.
* Whether issuer discovery stays linear in the chain for a chain sent out of
  order. The handshake row prices parsing and verifying a well-formed chain,
  which is what a server sends.
* Only one cipher suite, one key type and one chain shape are exercised. The
  record size is a protocol constant, but the per-record overhead, the
  certificate sizes and the cipher counts are all properties of these
  fixtures.
"""

from __future__ import annotations

import os
import pathlib
import re
import socket
import ssl
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ssl.md"
EXPECTED_BLOCKS = 9
EXPECTED_PEER_BLOCKS = 1

RECORD = 16384
SOCKET_TIMEOUT = 30.0

# `get_verified_chain()`/`get_unverified_chain()` arrive in 3.13, TLS-PSK in 3.13.
HAS_CHAIN_METHODS = hasattr(ssl.SSLObject, "get_verified_chain")
HAS_PSK = getattr(ssl, "HAS_PSK", False)

# Throwaway EC test certificates generated for this file, valid from 2020-01-01
# to 2126-01-01 so no clock the suite runs on falls outside them. They
# authenticate nothing: the private key is public, and the root is trusted only
# by the contexts built below.
ROOT_CERT = """\
-----BEGIN CERTIFICATE-----
MIIBkjCCATigAwIBAgIUYJAgba/ETTgkgb1+QfWCqInk8qkwCgYIKoZIzj0EAwIw
JjEkMCIGA1UEAwwbc3NsLm1kIGNvbXBsZXhpdHkgdGVzdCByb290MCAXDTIwMDEw
MTAwMDAwMFoYDzIxMjYwMTAxMDAwMDAwWjAmMSQwIgYDVQQDDBtzc2wubWQgY29t
cGxleGl0eSB0ZXN0IHJvb3QwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAARHWVO/
ke7SHfqlHYs78x33J1Wd6PRG82Y1gU1WDijQM/eYtaBvoERl9cfH9rHiRZ5Y3pVA
6tjTvNAP8SAFRa/7o0IwQDAPBgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIB
BjAdBgNVHQ4EFgQUZZPngnGQDu1zzVsQ93iEp78J4vAwCgYIKoZIzj0EAwIDSAAw
RQIhANEObDt0peOhcs75eA34YmVCsO3RWDAj5vlN0cg3i+m6AiBb8D9AbP0WZbvg
0OFKCme8hz5OTJMuktTJP+Dbjklc7w==
-----END CERTIFICATE-----
"""

LEAF_CERT = """\
-----BEGIN CERTIFICATE-----
MIIByjCCAXGgAwIBAgIUC+VglDjjjt6FB3ULqEjlrfy6aP8wCgYIKoZIzj0EAwIw
JjEkMCIGA1UEAwwbc3NsLm1kIGNvbXBsZXhpdHkgdGVzdCByb290MCAXDTIwMDEw
MTAwMDAwMFoYDzIxMjYwMTAxMDAwMDAwWjAUMRIwEAYDVQQDDAlsb2NhbGhvc3Qw
WTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAATnf5jzM34NpYLR2bnW4EqGcw1WmEFe
2cKH5kGWJdypJBj2n4kSp23mrjjKV+84LEZvuXc96v6rFsDJpAbxEw0/o4GMMIGJ
MBQGA1UdEQQNMAuCCWxvY2FsaG9zdDAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQE
AwIFoDATBgNVHSUEDDAKBggrBgEFBQcDATAfBgNVHSMEGDAWgBRlk+eCcZAO7XPN
WxD3eISnvwni8DAdBgNVHQ4EFgQUQ2EqSO6q3xCNh4+r5elj2YEvxGMwCgYIKoZI
zj0EAwIDRwAwRAIgBaSQxsSljjr1mjCSZ3i0RKYvUvp2dGMpxKZdYX5AJAkCICas
1fasloCYnEIuzz4JEmpdAe5e6bli5NCY+cqvnQzJ
-----END CERTIFICATE-----
"""

LEAF_KEY = """\
-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgxgD2S67O/thY2P5N
pkR38z7aHjUPe3Xqz/u5gZ/f6tihRANCAATnf5jzM34NpYLR2bnW4EqGcw1WmEFe
2cKH5kGWJdypJBj2n4kSp23mrjjKV+84LEZvuXc96v6rFsDJpAbxEw0/
-----END PRIVATE KEY-----
"""

# OpenSSL finds a `capath` certificate by the hash of its subject name. A wrong
# name here does not pass silently: the handshake that needs the root fails.
ROOT_HASH_NAME = "3a6ebd7a.0"


@pytest.fixture(scope="module")
def chain_file(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """The leaf, its issuer and the private key: a server sending two certificates."""
    path = tmp_path_factory.mktemp("ssl") / "chain.pem"
    path.write_text(LEAF_CERT + ROOT_CERT + LEAF_KEY, encoding="ascii")
    return path


@pytest.fixture(scope="module")
def leaf_file(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """The leaf and its key alone: a server sending one certificate."""
    path = tmp_path_factory.mktemp("ssl") / "leaf.pem"
    path.write_text(LEAF_CERT + LEAF_KEY, encoding="ascii")
    return path


def server_context(certfile: pathlib.Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(certfile))
    return context


def client_context(cadata: str, partial_chain: bool = False) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=cadata)
    if partial_chain:
        context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return context


class Connection:
    """A finished handshake between two `SSLObject`s over four `MemoryBIO`s."""

    def __init__(self, client: ssl.SSLObject, server: ssl.SSLObject, bios: tuple[Any, ...]) -> None:
        self.client = client
        self.server = server
        self.client_in, self.client_out, self.server_in, self.server_out = bios

    def flush(self) -> None:
        """Move whatever each side has written into the other's incoming BIO."""
        for source, target in (
            (self.client_out, self.server_in),
            (self.server_out, self.client_in),
        ):
            data = source.read()
            if data:
                target.write(data)


def handshake(
    server_ctx: ssl.SSLContext,
    client_ctx: ssl.SSLContext,
    session: ssl.SSLSession | None = None,
    hostname: str = "localhost",
) -> Connection:
    """Drive both sides to a finished handshake with no socket and no peer."""
    bios = (ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO())
    client = client_ctx.wrap_bio(bios[0], bios[1], server_hostname=hostname, session=session)
    server = server_ctx.wrap_bio(bios[2], bios[3], server_side=True)
    connection = Connection(client, server, bios)

    for _ in range(40):
        connection.flush()
        finished = 0
        for side in (client, server):
            try:
                side.do_handshake()
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                continue
            finished += 1
        if finished == 2:
            connection.flush()
            return connection

    raise AssertionError("the handshake did not finish in 40 rounds")


def _resident_bytes() -> int:
    """This process's current resident set, from /proc/self/statm."""
    fields = pathlib.Path("/proc/self/statm").read_text().split()
    return int(fields[1]) * os.sysconf("SC_PAGE_SIZE")


class ResidentPeak:
    """Sample the resident set while a call is running.

    A reading taken after the call returns cannot see a buffer that was
    allocated and freed inside it, and `ru_maxrss` cannot see anything below
    an earlier high-water mark. Sampling from a second thread sees both -
    CPython releases the GIL around the OpenSSL call being watched.
    """

    def __init__(self, interval: float = 0.005) -> None:
        self.peak = 0
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample)

    def _sample(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, _resident_bytes())
            time.sleep(self._interval)
        self.peak = max(self.peak, _resident_bytes())

    def __enter__(self) -> ResidentPeak:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join()


@contextmanager
def tls_socketpair(
    server_ctx: ssl.SSLContext, client_ctx: ssl.SSLContext
) -> Iterator[tuple[ssl.SSLSocket, ssl.SSLSocket]]:
    """A finished handshake over a socket pair, with the server side in a thread."""
    left, right = socket.socketpair()
    left.settimeout(SOCKET_TIMEOUT)
    right.settimeout(SOCKET_TIMEOUT)
    outcome: dict[str, Any] = {}

    def serve() -> None:
        try:
            outcome["socket"] = server_ctx.wrap_socket(left, server_side=True)
        except BaseException as error:  # reported on the main thread below
            outcome["error"] = error

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        client = client_ctx.wrap_socket(right, server_hostname="localhost")
    finally:
        thread.join(SOCKET_TIMEOUT)

    assert not thread.is_alive(), "the server side did not finish its handshake"
    assert "error" not in outcome, outcome["error"]
    server = outcome["socket"]
    try:
        yield client, server
    finally:
        client.close()
        server.close()


class TestContextHoldsWhatItWasGiven:
    """`SSLContext()` is O(1) and `load_verify_locations()` is O(t·k) - but only
    for `cafile` and `cadata`. A `capath` directory is registered, not read."""

    def test_a_bare_context_holds_no_certificates(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        assert context.cert_store_stats() == {"x509": 0, "crl": 0, "x509_ca": 0}
        assert context.get_ca_certs() == []

    def test_cadata_is_parsed_now(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ROOT_CERT)

        assert context.cert_store_stats() == {"x509": 1, "crl": 0, "x509_ca": 1}
        assert len(context.get_ca_certs()) == 1

    def test_cafile_is_parsed_now(self, tmp_path: pathlib.Path) -> None:
        bundle = tmp_path / "bundle.pem"
        bundle.write_text(ROOT_CERT, encoding="ascii")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(bundle))

        assert context.cert_store_stats()["x509"] == 1

    def test_capath_reads_nothing_until_a_chain_needs_it(
        self, tmp_path: pathlib.Path, chain_file: pathlib.Path
    ) -> None:
        """Registration is O(1) and the certificate is still usable: the store
        is empty, then a handshake that needs the root puts it there. An
        implementation that ignored the directory would fail that handshake."""
        directory = tmp_path / "certs"
        directory.mkdir()
        (directory / ROOT_HASH_NAME).write_text(ROOT_CERT, encoding="ascii")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(capath=str(directory))

        assert context.cert_store_stats() == {"x509": 0, "crl": 0, "x509_ca": 0}
        assert context.get_ca_certs() == []

        connection = handshake(server_context(chain_file), context)

        assert connection.client.version() is not None
        assert context.cert_store_stats()["x509"] == 1

    def test_loading_the_same_certificate_twice_adds_nothing(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ROOT_CERT)
        context.load_verify_locations(cadata=ROOT_CERT)

        assert context.cert_store_stats()["x509"] == 1

    def test_get_ca_certs_builds_its_result(self) -> None:
        """O(t·k) space per call: equal dictionaries, never the same one twice."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ROOT_CERT)

        first, second = context.get_ca_certs(), context.get_ca_certs()

        assert first == second
        assert first[0] is not second[0]

    def test_binary_form_returns_der(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ROOT_CERT)

        (der,) = context.get_ca_certs(binary_form=True)

        assert der == ssl.PEM_cert_to_DER_cert(ROOT_CERT)


class TestCipherListIsBuiltPerCall:
    """`get_ciphers()` is O(q) in time *and* space: it builds a dictionary per
    enabled cipher rather than handing back a stored list."""

    def test_every_call_builds_new_dictionaries(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        first, second = context.get_ciphers(), context.get_ciphers()

        assert first == second
        assert first is not second
        assert first[0] is not second[0]

    def test_set_ciphers_narrows_the_list(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        before = len(context.get_ciphers())
        context.set_ciphers("AES256-SHA")

        assert 0 < len(context.get_ciphers()) < before

    def test_session_stats_is_a_fixed_shape(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        stats = context.session_stats()

        assert len(stats) == 11
        assert stats["hits"] == 0 and stats["misses"] == 0


class TestWrappingNegotiatesNothing:
    """`wrap_bio()` is O(1): no bytes move until `do_handshake()` asks for them."""

    def test_wrap_bio_writes_nothing(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()

        client = context.wrap_bio(incoming, outgoing, server_hostname="localhost")

        assert outgoing.pending == 0
        assert incoming.pending == 0
        assert client.version() is None
        assert client.cipher() is None

    def test_the_first_handshake_call_emits_the_client_hello(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        client = context.wrap_bio(incoming, outgoing, server_hostname="localhost")

        with pytest.raises(ssl.SSLWantReadError):
            client.do_handshake()

        assert 0 < outgoing.pending < RECORD
        assert client.version() is None


class TestWrapSocketHandshakesAConnectedSocket:
    """The row says `wrap_socket()` is O(1) *plus the handshake* on a connected
    socket. A peer that never answers turns that into a timeout in the wrap
    call itself, which a lazy wrapper could not produce."""

    def test_a_silent_peer_times_out_inside_wrap_socket(self) -> None:
        left, right = socket.socketpair()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        right.settimeout(1.0)
        try:
            with pytest.raises(TimeoutError):
                context.wrap_socket(right, server_hostname="localhost")
        finally:
            left.close()

    def test_deferring_the_handshake_returns_immediately(self) -> None:
        left, right = socket.socketpair()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        right.settimeout(1.0)
        try:
            wrapped = context.wrap_socket(
                right, server_hostname="localhost", do_handshake_on_connect=False
            )
            assert wrapped.version() is None
            assert wrapped.pending() == 0
            wrapped.close()
        finally:
            left.close()


class TestHandshakeFollowsTheChain:
    """The handshake's c term is the chain the peer presents, and
    `get_verified_chain()` reports it."""

    @pytest.mark.skipif(not HAS_CHAIN_METHODS, reason="chain accessors are Python 3.13+")
    def test_two_certificates_when_the_server_sends_two(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))

        assert len(connection.client.get_verified_chain()) == 2  # type: ignore[attr-defined]
        assert len(connection.client.get_unverified_chain()) == 2  # type: ignore[attr-defined]

    @pytest.mark.skipif(not HAS_CHAIN_METHODS, reason="chain accessors are Python 3.13+")
    def test_one_certificate_when_the_server_sends_one(self, leaf_file: pathlib.Path) -> None:
        connection = handshake(
            server_context(leaf_file), client_context(LEAF_CERT, partial_chain=True)
        )

        assert len(connection.client.get_verified_chain()) == 1  # type: ignore[attr-defined]

    def test_an_untrusted_chain_raises_with_the_verification_result(
        self, chain_file: pathlib.Path
    ) -> None:
        with pytest.raises(ssl.SSLCertVerificationError) as raised:
            handshake(server_context(chain_file), client_context(LEAF_CERT))

        assert raised.value.verify_code > 0
        assert raised.value.verify_message
        assert raised.value.reason == "CERTIFICATE_VERIFY_FAILED"
        assert isinstance(raised.value, ssl.SSLError)

    def test_getpeercert_builds_its_result(self, chain_file: pathlib.Path) -> None:
        """O(k) space per call rather than a reference to a parsed certificate."""
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))

        first, second = connection.client.getpeercert(), connection.client.getpeercert()

        assert first == second
        assert first is not second
        assert connection.client.getpeercert(binary_form=True) == ssl.PEM_cert_to_DER_cert(
            LEAF_CERT
        )

    def test_the_negotiated_details_read_back(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))

        version = connection.client.version()
        cipher = connection.client.cipher()
        offered = connection.server.shared_ciphers()

        assert version is not None and version.startswith("TLS")
        assert cipher is not None and cipher[1].startswith("TLS")
        assert connection.client.compression() is None
        assert connection.client.server_side is False
        assert connection.server.server_side is True
        assert connection.client.server_hostname == "localhost"
        assert connection.client.shared_ciphers() is None
        assert offered is not None and len(offered) > 0
        assert connection.client.context is not connection.server.context


class TestSharedCiphersIsAnIntersection:
    """The row says the ciphers both ends have in common. Both one-sided
    readings - what the client offered, what the server enabled - are
    plausible, and one suite each side rules them both out."""

    def test_only_the_suite_both_ends_enable_is_reported(self, chain_file: pathlib.Path) -> None:
        both = "ECDHE-ECDSA-AES256-GCM-SHA384"
        server_only = "ECDHE-ECDSA-AES128-GCM-SHA256"
        client_only = "ECDHE-ECDSA-CHACHA20-POLY1305"
        server_ctx = server_context(chain_file)
        server_ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        server_ctx.set_ciphers(f"{both}:{server_only}")
        client_ctx = client_context(ROOT_CERT)
        client_ctx.set_ciphers(f"{both}:{client_only}")

        server_enabled = {cipher["name"] for cipher in server_ctx.get_ciphers()}
        client_enabled = {cipher["name"] for cipher in client_ctx.get_ciphers()}
        assert server_only in server_enabled and server_only not in client_enabled
        assert client_only in client_enabled and client_only not in server_enabled

        connection = handshake(server_ctx, client_ctx)
        shared = connection.server.shared_ciphers()

        assert shared is not None
        names = {name for name, _version, _bits in shared}
        assert both in names
        assert server_only not in names
        assert client_only not in names
        assert names == server_enabled & client_enabled


class TestOneReadIsOneRecord:
    """`read(len)` returns at most 16384 bytes however large `len` is, and
    `pending()` is what is left of that record - not of the stream."""

    def test_a_large_read_returns_one_record(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        payload = b"x" * 40_000

        assert connection.server.write(payload) == len(payload)
        connection.flush()

        assert len(connection.client.read(100_000)) == RECORD

    def test_pending_is_the_rest_of_that_record(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        connection.server.write(b"x" * 40_000)
        connection.flush()

        assert len(connection.client.read(100)) == 100
        assert connection.client.pending() == RECORD - 100

        assert len(connection.client.read(100_000)) == RECORD - 100
        assert connection.client.pending() == 0

    @pytest.mark.serial
    def test_a_read_allocates_what_it_was_asked_for(self, chain_file: pathlib.Path) -> None:
        """Space O(len), not O(min(len, 16384)): Modules/_ssl.c allocates the
        result at the requested size and shrinks it to what arrived. Asserting
        only the returned length would miss the whole bound."""
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        connection.server.write(b"x" * 20_000)
        connection.flush()

        tracemalloc.start()
        try:
            data = connection.client.read(10_000_000)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert len(data) == RECORD
        assert peak > 9_000_000, peak

    @pytest.mark.serial
    def test_a_buffer_argument_allocates_nothing(self, chain_file: pathlib.Path) -> None:
        """The control for the row above: the same read into a caller buffer."""
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        connection.server.write(b"x" * 20_000)
        connection.flush()
        target = bytearray(10_000_000)

        tracemalloc.start()
        try:
            read = connection.client.read(len(target), target)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert read == RECORD
        # Not exactly zero on every version - a few tens of bytes of Python
        # bookkeeping - but four orders of magnitude off the request.
        assert peak < 1000, peak

    def test_a_buffer_argument_returns_a_count(self, chain_file: pathlib.Path) -> None:
        """With `buffer`, the space is the caller's and the return is a length."""
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        connection.server.write(b"x" * 40_000)
        connection.flush()
        target = bytearray(100_000)

        assert connection.client.read(len(target), target) == RECORD
        assert target[:RECORD] == b"x" * RECORD

    def test_pending_is_zero_before_anything_is_decrypted(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        connection.server.write(b"x" * 40_000)
        connection.flush()

        assert connection.client.pending() == 0
        assert connection.client_in.pending > RECORD


class TestWriteSplitsIntoRecords:
    """`write(n)` costs ⌈n / 16384⌉ records, each carrying its own framing. The
    per-record overhead is measured rather than assumed, so another cipher
    suite changes the constant without breaking the count."""

    @staticmethod
    def _encrypted_size(connection: Connection, size: int) -> int:
        connection.server_out.read()
        assert connection.server.write(b"x" * size) == size
        return len(connection.server_out.read())

    def test_record_count_follows_the_ceiling(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        overhead = self._encrypted_size(connection, 1) - 1

        assert overhead > 0

        for size in (RECORD, RECORD + 1, 2 * RECORD, 2 * RECORD + 1, 100_000):
            records = -(-size // RECORD)
            assert self._encrypted_size(connection, size) == size + overhead * records, size


class TestSessionResumption:
    """A replayed session is reused rather than renegotiated, which is what the
    page means by skipping the chain."""

    def test_a_replayed_session_is_reused(self, chain_file: pathlib.Path) -> None:
        server_ctx = server_context(chain_file)
        client_ctx = client_context(ROOT_CERT)

        first = handshake(server_ctx, client_ctx)
        assert first.client.session_reused is False
        assert server_ctx.session_stats()["hits"] == 0

        # The TLS 1.3 ticket arrives after the handshake, on the first read.
        first.server.write(b"ready")
        first.flush()
        assert first.client.read(16) == b"ready"
        session = first.client.session
        assert session is not None
        assert session.has_ticket is True
        assert isinstance(session.id, bytes)
        assert session.timeout > 0 and session.time > 0

        second = handshake(server_ctx, client_ctx, session=session)

        assert second.client.session_reused is True
        assert server_ctx.session_stats()["hits"] == 1

        if HAS_CHAIN_METHODS:
            # No certificate was exchanged, so nothing was verified; the peer
            # certificate the client still reports comes out of the session.
            assert second.client.get_verified_chain() == []  # type: ignore[attr-defined]
            assert second.client.getpeercert() == first.client.getpeercert()


class TestPostHandshakeAuthIsDeferred:
    """`verify_client_post_handshake()` is O(1): it flags the request and writes
    nothing, so the certificate exchange is not in that call."""

    def test_the_request_writes_no_bytes(self, chain_file: pathlib.Path) -> None:
        server_ctx = server_context(chain_file)
        server_ctx.verify_mode = ssl.CERT_OPTIONAL
        server_ctx.post_handshake_auth = True
        client_ctx = client_context(ROOT_CERT)
        client_ctx.post_handshake_auth = True
        connection = handshake(server_ctx, client_ctx)
        connection.server_out.read()

        connection.server.verify_client_post_handshake()

        assert connection.server_out.pending == 0


class TestSSLSocketOverSocketPair:
    """The socket wrapper reaches the same engine: one record per `recv()`, a
    looping `sendall()`, and the socket methods TLS has to refuse."""

    def test_recv_returns_one_record(self, chain_file: pathlib.Path) -> None:
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            server,
        ):
            payload = b"y" * 40_000
            sender = threading.Thread(target=server.sendall, args=(payload,))
            sender.start()
            try:
                first = client.recv(100_000)
                received = len(first)
                while received < len(payload):
                    received += len(client.recv(100_000))
            finally:
                sender.join(SOCKET_TIMEOUT)

            assert len(first) == RECORD
            assert received == len(payload)
            assert not sender.is_alive()

    @pytest.mark.skipif(not pathlib.Path("/proc/self/statm").exists(), reason="needs /proc")
    def test_a_large_write_neither_buffers_nor_completes(self, chain_file: pathlib.Path) -> None:
        """Two halves of the O(1) space row. The timeout shows backpressure:
        the call does not finish while the peer is not reading. The resident
        peak *during* the call shows the allocation: an implementation that
        encrypted the whole message and then blocked would also time out, but
        would be holding another 100 MiB while it did - even if it released
        that buffer on the way out. `tracemalloc` cannot see this: the
        allocation would be OpenSSL's, not Python's."""
        payload = b"x" * (100 * 1024 * 1024)
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            _client,
            server,
        ):
            server.settimeout(1.0)
            before = _resident_bytes()

            with ResidentPeak() as resident, pytest.raises(TimeoutError):
                server.write(payload)

        assert resident.peak - before < 50 * 1024 * 1024, (before, resident.peak)

    @pytest.mark.skipif(not pathlib.Path("/proc/self/statm").exists(), reason="needs /proc")
    def test_the_resident_probe_sees_a_transient_allocation(self) -> None:
        """The control for the row above: a probe that cannot see 100 MiB come
        and go proves nothing by not seeing it during the write."""
        before = _resident_bytes()

        with ResidentPeak() as resident:
            blob = bytearray(100 * 1024 * 1024)
            blob[:: os.sysconf("SC_PAGE_SIZE")] = b"\x01" * (
                len(blob) // os.sysconf("SC_PAGE_SIZE")
            )
            time.sleep(0.05)
            del blob

        assert resident.peak - before > 50 * 1024 * 1024, (before, resident.peak)

    def test_sendall_makes_one_send_for_a_buffer_send_takes_whole(
        self, chain_file: pathlib.Path
    ) -> None:
        """`sendall()` is a loop a blocking socket runs once, so it adds nothing."""
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            server,
        ):
            sizes = self._instrument_send(server)
            reader = threading.Thread(target=self._drain, args=(client, 40_000))
            reader.start()
            try:
                server.sendall(b"w" * 40_000)
            finally:
                reader.join(SOCKET_TIMEOUT)

            assert sizes == [40_000]
            assert not reader.is_alive()

    @staticmethod
    def _instrument_send(sock: ssl.SSLSocket) -> list[int]:
        """Record the length of every `send()` the socket makes."""
        sizes: list[int] = []
        real_send = sock.send

        def counting_send(data: Any, flags: int = 0) -> int:
            sizes.append(len(data))
            return real_send(data, flags)

        sock.send = counting_send  # type: ignore[method-assign]
        return sizes

    def test_sendfile_sends_fixed_blocks(
        self, chain_file: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        source = tmp_path / "payload.bin"
        source.write_bytes(b"z" * 20_000)
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            server,
        ):
            sizes = self._instrument_send(server)
            reader = threading.Thread(target=self._drain, args=(client, 20_000))
            reader.start()
            try:
                with source.open("rb") as handle:
                    assert server.sendfile(handle) == 20_000
            finally:
                reader.join(SOCKET_TIMEOUT)

            assert sizes, "the instrumented send was never reached"
            assert len(sizes) == 3
            assert max(sizes) <= 8192
            assert not reader.is_alive()

    @staticmethod
    def _drain(sock: ssl.SSLSocket, total: int) -> None:
        seen = 0
        while seen < total:
            chunk = sock.recv(8192)
            if not chunk:
                return
            seen += len(chunk)

    def test_message_methods_refuse(self, chain_file: pathlib.Path) -> None:
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            _server,
        ):
            for call in (
                lambda: client.sendmsg([b"x"]),  # type: ignore[arg-type]
                lambda: client.recvmsg(1),  # type: ignore[arg-type]
                lambda: client.recvmsg_into([bytearray(1)]),  # type: ignore[arg-type]
                client.dup,
            ):
                with pytest.raises(NotImplementedError):
                    call()

            for datagram in (
                lambda: client.sendto(b"x", ("127.0.0.1", 9)),
                lambda: client.recvfrom(1),
                lambda: client.recvfrom_into(bytearray(1)),
            ):
                with pytest.raises(ValueError):
                    datagram()

    def test_recv_into_fills_at_most_one_record(self, chain_file: pathlib.Path) -> None:
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            server,
        ):
            sender = threading.Thread(target=server.sendall, args=(b"q" * 40_000,))
            sender.start()
            try:
                target = bytearray(100_000)
                read = client.recv_into(target)
                drained = read
                while drained < 40_000:
                    drained += len(client.recv(100_000))
            finally:
                sender.join(SOCKET_TIMEOUT)

            assert read == RECORD
            assert target[:read] == b"q" * read
            assert not sender.is_alive()

    def test_shutdown_drops_tls_without_a_close_notify(self, chain_file: pathlib.Path) -> None:
        """`shutdown()` clears the TLS state before touching the socket, so
        there is nothing left to send `close_notify` with."""
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            _server,
        ):
            assert client.version() is not None

            client.shutdown(socket.SHUT_RDWR)

            assert client.version() is None
            assert client.pending() == 0

    def test_unwrap_drops_tls_from_the_same_socket(self, chain_file: pathlib.Path) -> None:
        """The row says *this* socket comes back, not a new one."""
        with tls_socketpair(server_context(chain_file), client_context(ROOT_CERT)) as (
            client,
            server,
        ):
            closer = threading.Thread(target=server.unwrap)
            closer.start()
            try:
                plain = client.unwrap()
            finally:
                closer.join(SOCKET_TIMEOUT)

            assert plain is client
            assert client.version() is None
            assert client.pending() == 0
            assert not closer.is_alive()


class TestSSLObjectShutdown:
    """`SSLObject.unwrap()` writes `close_notify` and then waits for the peer's."""

    def test_unwrap_waits_for_the_peer(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
        connection.client_out.read()

        with pytest.raises(ssl.SSLWantReadError):
            connection.client.unwrap()

        assert connection.client_out.pending > 0


class TestMemoryBIO:
    """A byte buffer with an EOF flag; `pending` and `eof` are O(1) reads."""

    def test_write_and_read_track_pending(self) -> None:
        bio = ssl.MemoryBIO()

        assert bio.pending == 0
        assert bio.eof is False
        assert bio.write(b"hello") == 5
        assert bio.pending == 5
        assert bio.read(2) == b"he"
        assert bio.pending == 3

    def test_the_default_read_takes_everything(self) -> None:
        bio = ssl.MemoryBIO()
        bio.write(b"a" * 1000)

        assert len(bio.read()) == 1000
        assert bio.pending == 0

    def test_eof_waits_for_the_buffer_to_drain(self) -> None:
        bio = ssl.MemoryBIO()
        bio.write(b"tail")
        bio.write_eof()

        assert bio.eof is False
        assert bio.read() == b"tail"
        assert bio.eof is True

    @pytest.mark.timing
    def test_a_write_after_a_partial_read_moves_the_backlog(self) -> None:
        """O(b + len(buf)): the unread remainder is shifted to the front before
        the new bytes land, so a one-byte write costs the backlog. Timed
        because no call count or allocation on the Python side can see a
        memmove inside OpenSSL."""

        def one_byte_write_after_a_partial_read(backlog: int) -> float:
            best = float("inf")
            for _ in range(5):
                bio = ssl.MemoryBIO()
                bio.write(b"x" * backlog)
                bio.read(1)
                start = time.perf_counter()
                bio.write(b"y")
                best = min(best, time.perf_counter() - start)
            return best

        small = one_byte_write_after_a_partial_read(1_000_000)
        large = one_byte_write_after_a_partial_read(32_000_000)

        assert large > small * 8, (small, large)

    @pytest.mark.timing
    def test_a_full_read_leaves_nothing_to_move(self) -> None:
        """The control, and the recommendation: drain with a bare `read()` and
        the next write has no backlog to shift."""

        def one_byte_write_after_a_full_read(backlog: int) -> float:
            best = float("inf")
            for _ in range(5):
                bio = ssl.MemoryBIO()
                bio.write(b"x" * backlog)
                bio.read()
                start = time.perf_counter()
                bio.write(b"y")
                best = min(best, time.perf_counter() - start)
            return best

        drained = one_byte_write_after_a_full_read(32_000_000)
        partial = float("inf")
        for _ in range(5):
            bio = ssl.MemoryBIO()
            bio.write(b"x" * 32_000_000)
            bio.read(1)
            start = time.perf_counter()
            bio.write(b"y")
            partial = min(partial, time.perf_counter() - start)

        assert partial > drained * 8, (drained, partial)

    @pytest.mark.timing
    def test_an_ssl_write_after_a_partial_drain_pays_the_same_backlog(
        self, chain_file: pathlib.Path
    ) -> None:
        """The b term reaches `SSLObject.write()`: its records land in the
        outgoing BIO, so a one-byte write after a partial drain moves whatever
        is still queued there."""

        def one_byte_write_over(backlog: int) -> float:
            best = float("inf")
            for _ in range(5):
                connection = handshake(server_context(chain_file), client_context(ROOT_CERT))
                connection.server_out.read()
                connection.server.write(b"x" * backlog)
                connection.server_out.read(1)
                start = time.perf_counter()
                connection.server.write(b"y")
                best = min(best, time.perf_counter() - start)
            return best

        small = one_byte_write_over(1_000_000)
        large = one_byte_write_over(20_000_000)

        assert large > small * 5, (small, large)

    def test_writing_after_eof_raises(self) -> None:
        bio = ssl.MemoryBIO()
        bio.write_eof()

        with pytest.raises(ssl.SSLError, match="write_eof"):
            bio.write(b"more")


class TestEncodingHelpers:
    """DER and PEM in each direction, linear in the certificate and nothing more."""

    def test_round_trip(self) -> None:
        der = ssl.PEM_cert_to_DER_cert(LEAF_CERT)
        pem = ssl.DER_cert_to_PEM_cert(der)

        assert pem.strip() == LEAF_CERT.strip()
        assert ssl.PEM_cert_to_DER_cert(pem) == der

    def test_body_lines_wrap_at_64(self) -> None:
        pem = ssl.DER_cert_to_PEM_cert(bytes(range(256)) * 4)
        body = pem.splitlines()[1:-1]

        assert pem.splitlines()[0] == ssl.PEM_HEADER
        assert pem.splitlines()[-1] == ssl.PEM_FOOTER
        assert max(len(line) for line in body) == 64

    def test_a_string_without_the_header_is_refused(self) -> None:
        with pytest.raises(ValueError, match="PEM"):
            ssl.PEM_cert_to_DER_cert("not a certificate")

    def test_certificate_timestamps(self) -> None:
        assert ssl.cert_time_to_seconds("Jan  5 09:34:43 2018 GMT") == 1515144883

        with pytest.raises(ValueError, match="time data"):
            ssl.cert_time_to_seconds("2018-01-05 09:34:43")


class TestConstantsAreExistingMembers:
    """These assertions establish that a lookup returns the member that already
    exists, so the space column is nothing built. They do not time the lookup:
    the O(1) comes from the value map `enum` builds once, in Lib/enum.py."""

    def test_enum_lookups_return_the_member(self) -> None:
        assert ssl.TLSVersion(772) is ssl.TLSVersion.TLSv1_3
        assert ssl.VerifyMode(2) is ssl.CERT_REQUIRED
        assert ssl.Purpose(ssl.Purpose.SERVER_AUTH.value) is ssl.Purpose.SERVER_AUTH
        assert ssl.Options(ssl.OP_NO_TICKET) is ssl.Options.OP_NO_TICKET
        assert ssl.VerifyFlags(32) is ssl.VerifyFlags.VERIFY_X509_STRICT
        assert ssl.SSLErrorNumber(ssl.SSL_ERROR_WANT_READ) is ssl.SSLErrorNumber.SSL_ERROR_WANT_READ
        assert ssl.AlertDescription(0) is ssl.AlertDescription.ALERT_DESCRIPTION_CLOSE_NOTIFY

    def test_purpose_lookups_return_the_object_identifier(self) -> None:
        assert ssl.Purpose.SERVER_AUTH.oid == "1.3.6.1.5.5.7.3.1"
        assert ssl.Purpose.SERVER_AUTH.shortname == "serverAuth"
        assert tuple(ssl.Purpose.fromnid(ssl.Purpose.CLIENT_AUTH.nid)) == tuple(
            ssl.Purpose.CLIENT_AUTH.value
        )
        assert tuple(ssl.Purpose.fromname("clientAuth")) == tuple(ssl.Purpose.CLIENT_AUTH.value)

    def test_default_verify_paths_names_its_fields(self) -> None:
        paths = ssl.get_default_verify_paths()

        assert isinstance(paths, ssl.DefaultVerifyPaths)
        assert paths.openssl_cafile_env == "SSL_CERT_FILE"
        assert paths.openssl_capath_env == "SSL_CERT_DIR"
        assert paths.cafile is None or pathlib.Path(paths.cafile).is_file()
        assert paths.capath is None or pathlib.Path(paths.capath).is_dir()
        assert isinstance(paths.openssl_cafile, str) and isinstance(paths.openssl_capath, str)

    def test_protocol_names_come_from_a_lookup(self) -> None:
        assert ssl.get_protocol_name(ssl.PROTOCOL_TLS_CLIENT) == "PROTOCOL_TLS_CLIENT"
        assert ssl.get_protocol_name(-999) == "<unknown>"

    def test_certificate_error_is_the_verification_error(self) -> None:
        assert ssl.CertificateError is ssl.SSLCertVerificationError
        assert issubclass(ssl.SSLCertVerificationError, ssl.SSLError)
        for subclass in (
            ssl.SSLZeroReturnError,
            ssl.SSLWantReadError,
            ssl.SSLWantWriteError,
            ssl.SSLSyscallError,
            ssl.SSLEOFError,
        ):
            assert issubclass(subclass, ssl.SSLError)
        assert issubclass(ssl.SSLError, OSError)

    def test_pem_markers_are_what_the_helpers_write(self) -> None:
        assert ssl.DER_cert_to_PEM_cert(b"\x00").startswith(ssl.PEM_HEADER)
        assert ssl.PEM_HEADER == "-----BEGIN CERTIFICATE-----"
        assert ssl.PEM_FOOTER == "-----END CERTIFICATE-----"

    def test_feature_flags_and_versions_are_plain_values(self) -> None:
        assert isinstance(ssl.HAS_TLSv1_3, bool) and isinstance(ssl.HAS_ALPN, bool)
        assert ssl.CHANNEL_BINDING_TYPES == ["tls-unique"]
        assert isinstance(ssl.OPENSSL_VERSION, str)
        assert len(ssl.OPENSSL_VERSION_INFO) == 5
        assert isinstance(ssl.OPENSSL_VERSION_NUMBER, int)


class TestRandomness:
    """The `RAND_*` helpers are linear in the bytes they touch."""

    def test_rand_bytes_returns_what_was_asked_for(self) -> None:
        assert len(ssl.RAND_bytes(16)) == 16
        assert len(ssl.RAND_bytes(1024)) == 1024
        assert ssl.RAND_bytes(16) != ssl.RAND_bytes(16)

    def test_rand_status_and_add(self) -> None:
        assert ssl.RAND_status() is True
        assert ssl.RAND_add(b"entropy" * 100, 0.0) is None
        assert ssl.RAND_status() is True


class TestContextSettings:
    """The settings rows: accepted, readable, and applied to a later handshake."""

    def test_a_default_context_verifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # create_default_context() honours SSLKEYLOGFILE, so the environment
        # decides keylog_filename unless it is taken out of the way.
        monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
        context = ssl.create_default_context()

        assert context.check_hostname is True
        assert context.verify_mode is ssl.CERT_REQUIRED
        assert context.protocol is ssl.PROTOCOL_TLS_CLIENT
        assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
        assert context.maximum_version is ssl.TLSVersion.MAXIMUM_SUPPORTED
        assert context.security_level >= 0
        assert context.post_handshake_auth is False
        assert context.keylog_filename is None
        assert isinstance(context.hostname_checks_common_name, bool)
        assert isinstance(context.options, ssl.Options)
        assert isinstance(context.verify_flags, ssl.VerifyFlags)

    def test_alpn_is_negotiated(self, chain_file: pathlib.Path) -> None:
        server_ctx = server_context(chain_file)
        client_ctx = client_context(ROOT_CERT)
        server_ctx.set_alpn_protocols(["h2", "http/1.1"])
        client_ctx.set_alpn_protocols(["h2", "http/1.1"])

        connection = handshake(server_ctx, client_ctx)

        assert connection.client.selected_alpn_protocol() == "h2"
        assert connection.server.selected_alpn_protocol() == "h2"

    def test_npn_selects_nothing(self, chain_file: pathlib.Path) -> None:
        """Deprecated since 3.10, and `None` on every supported version."""
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))

        with pytest.deprecated_call():
            assert connection.client.selected_npn_protocol() is None

    def test_the_sni_callback_runs_once_per_handshake(self, chain_file: pathlib.Path) -> None:
        seen: list[str | None] = []
        server_ctx = server_context(chain_file)
        server_ctx.set_servername_callback(
            lambda sslobj, name, context: seen.append(name)  # type: ignore[func-returns-value]
        )

        assert server_ctx.sni_callback is not None

        handshake(server_ctx, client_context(ROOT_CERT))

        assert seen == ["localhost"]

    @pytest.mark.skipif(ssl.HAS_NPN, reason="this OpenSSL still has NPN")
    def test_set_npn_protocols_is_gone_without_npn(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        with pytest.deprecated_call(), pytest.raises(AttributeError):
            context.set_npn_protocols(["h2"])

    def test_num_tickets_is_a_server_setting(self, chain_file: pathlib.Path) -> None:
        server_ctx = server_context(chain_file)
        server_ctx.num_tickets = 1

        assert server_ctx.num_tickets == 1
        with pytest.raises(ValueError, match="server context"):
            ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).num_tickets = 1

    def test_ecdh_curve_and_keylog_are_accepted(self, tmp_path: pathlib.Path) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.set_ecdh_curve("prime256v1")
        keylog = tmp_path / "keys.log"
        context.keylog_filename = str(keylog)

        assert context.keylog_filename == str(keylog)
        assert keylog.exists()

    @pytest.mark.skipif(not HAS_PSK, reason="TLS-PSK needs Python 3.13+ and OpenSSL support")
    def test_psk_callbacks_are_accepted(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.set_psk_client_callback(lambda hint: ("id", b"secret"))  # type: ignore[attr-defined]

        server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ctx.set_psk_server_callback(lambda identity: b"secret", "hint")  # type: ignore[attr-defined]

    def test_channel_binding(self, chain_file: pathlib.Path) -> None:
        connection = handshake(server_context(chain_file), client_context(ROOT_CERT))

        binding = connection.client.get_channel_binding("tls-unique")

        assert binding is None or isinstance(binding, bytes)
        with pytest.raises(ValueError, match="channel binding"):
            connection.client.get_channel_binding("tls-server-end-point")


class TestVersionNotes:
    """Each Version Notes bullet, asserted against the running interpreter so
    the matrix holds the page to the boundary it names."""

    def test_the_floor_is_tls_1_2_and_openssl_1_1_1(self) -> None:
        assert ssl.OPENSSL_VERSION_INFO >= (1, 1, 1)
        assert ssl.create_default_context().minimum_version is ssl.TLSVersion.TLSv1_2
        assert ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).security_level >= 0
        assert hasattr(ssl, "VERIFY_ALLOW_PROXY_CERTS")
        assert hasattr(ssl, "VERIFY_X509_PARTIAL_CHAIN")

    @pytest.mark.skipif(ssl.OPENSSL_VERSION_INFO < (3, 0), reason="the option needs OpenSSL 3.0")
    def test_the_unexpected_eof_option_is_there_on_openssl_3(self) -> None:
        assert hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF")

    def test_the_removals_land_in_3_12(self) -> None:
        gone = sys.version_info >= (3, 12)
        for name in ("wrap_socket", "match_hostname", "RAND_pseudo_bytes"):
            assert hasattr(ssl, name) is not gone, name

    def test_the_kernel_tls_and_legacy_options_arrive_in_3_12(self) -> None:
        """Both names arrive in 3.12, but only one of them depends on the
        library: Modules/_ssl.c adds `OP_LEGACY_SERVER_CONNECT` unconditionally
        and guards `OP_ENABLE_KTLS` with `#ifdef SSL_OP_ENABLE_KTLS`."""
        arrived = sys.version_info >= (3, 12)

        assert hasattr(ssl, "OP_LEGACY_SERVER_CONNECT") is arrived

        if not arrived:
            assert not hasattr(ssl, "OP_ENABLE_KTLS")
        elif ssl.OPENSSL_VERSION_INFO >= (3, 0):
            assert hasattr(ssl, "OP_ENABLE_KTLS")

    def test_chains_psk_and_strict_defaults_arrive_in_3_13(self) -> None:
        arrived = sys.version_info >= (3, 13)
        assert hasattr(ssl.SSLSocket, "get_verified_chain") is arrived
        assert hasattr(ssl.SSLSocket, "get_unverified_chain") is arrived
        assert hasattr(ssl.SSLContext, "set_psk_client_callback") is arrived
        assert hasattr(ssl.SSLContext, "set_psk_server_callback") is arrived
        assert hasattr(ssl, "HAS_PSK") is arrived

        flags = ssl.create_default_context().verify_flags
        strict = ssl.VERIFY_X509_PARTIAL_CHAIN | ssl.VERIFY_X509_STRICT
        assert bool(flags & strict == strict) is arrived

    def test_post_handshake_auth_reporting_arrives_in_3_14(self) -> None:
        assert hasattr(ssl, "HAS_PHA") is (sys.version_info >= (3, 14))


def _blocks() -> list[tuple[int, str]]:
    """Every fenced Python block on the page, with the line its fence opens on."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _needs_peer(source: str) -> bool:
    """A block that opens a connection cannot run without a server answering."""
    return "get_server_certificate(" in source


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block is either run in its own subprocess or counted as needing a peer."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_the_unrunnable_blocks_are_the_ones_that_connect(self) -> None:
        """Counted rather than skipped silently, so the gap stays visible."""
        peer = [line for line, source in _blocks() if _needs_peer(source)]

        assert len(peer) == EXPECTED_PEER_BLOCKS, (
            f"expected {EXPECTED_PEER_BLOCKS} blocks needing a peer, found {peer}"
        )

    def test_every_other_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            if _needs_peer(source):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS - EXPECTED_PEER_BLOCKS

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        line, source = next((n, s) for n, s in _blocks() if "bio.pending == 5" in s)
        mutated = source.replace("bio.pending == 5", "bio.pending == 4", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run(mutated, tmp_path).returncode != 0
