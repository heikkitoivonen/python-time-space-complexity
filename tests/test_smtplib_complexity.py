"""Tests for docs/stdlib/smtplib.md.

The page prices the client's share of each call - building the command, reading
the reply, holding the message - and counts the exchanges each call makes,
since waiting for the server is outside every bound. No test here talks
to a real mail server. `FakeServer` answers each command line in process,
behind a `FakeSocket` that offers the `sendall()` and `makefile('rb')` that
`smtplib` reads and writes through on every supported version, so every
exchange runs through the module's own code. The fake counts the replies it
sends, which is the exchange count, and counts the writes it receives while a
reply is still unread, which is pipelining. Space claims are settled by
traced allocation or by what the client retains; the one growth rate only a
stopwatch shows is timed at two sizes a hundredfold apart.

Measurement scope:

* Exchanges are counted as the replies the fake sends after its greeting.
  `SMTP(host)` makes none beyond the greeting and sends no command; the first
  `sendmail()` sends `EHLO` and the second does not; `sendmail()` to 1, 10
  and 100 recipients makes r + 3, one `RCPT` per recipient, with the message
  written in one `sendall()`; so does an accepted message with one of its
  two recipients refused. Refused transactions differ (all recipients
  refused is `MAIL`, the `RCPT`s and `RSET`) and are not counted. No command is written while a reply is unread,
  over a whole session of every command method.
* The session on the page is replayed on the fake, which offers `PLAIN`:
  `EHLO` twice around `STARTTLS`, five exchanges before `MAIL` (greeting,
  `EHLO`, `STARTTLS`, `EHLO`, `AUTH`), four for a one-recipient message, and
  `QUIT` on leaving the block.
* `sendmail()` of `bytes` peaks above the message size, and across 100,000,
  1,000,000 and 10,000,000 bytes each 10x step multiplies the peak by 5x to
  20x. The fake counts the payload without keeping it. A timing test asserts
  that 100x the message, 100,000 to 10,000,000 bytes, costs between 20x and
  1,000x, where linear gives 100x and quadratic 10,000x. The same 10x step in
  the body of `send_message()` multiplies its peak by 5x to 20x.
* A server advertising `SIZE` refuses an oversized message at `MAIL` with
  `SMTPSenderRefused` and never receives a payload. A non-ASCII `str`
  raises `UnicodeEncodeError` before `MAIL`; the same text as UTF-8 `bytes`
  arrives byte for byte.
* Refusals: one refused recipient of three is returned in the dictionary;
  all refused raises `SMTPRecipientsRefused` with the same dictionary and
  sends `RSET`, and the connection still answers `NOOP`. A `421` to the
  second `RCPT` raises `SMTPRecipientsRefused` holding only that refusal,
  sends no `DATA` and closes the socket. A `554` after the payload raises
  `SMTPDataError` and sends `RSET`.
* `send_message()` sends `RCPT` to `To`, `Cc` and `Bcc` addresses, the
  payload has no `Bcc` header, and the caller's message keeps its own. A
  non-ASCII address raises `SMTPNotSupportedError` before `MAIL` when the
  server lacks `SMTPUTF8`, and adds `SMTPUTF8` and `BODY=8BITMIME` when it
  has it. A non-ASCII body is sent, as the UTF-8 bytes it serializes to.
  With one `Resent-Date`, `MAIL` uses `Resent-From` and `RCPT` goes only to
  `Resent-To`; a second `Resent-Date` raises `ValueError`.
* `EHLO` with 1,000 and 10,000 extension lines leaves as many entries in
  `esmtp_features` and the whole reply in `ehlo_resp`. `has_extn()` ignores
  case. `helo()` after `ehlo()` sets `helo_resp` and leaves
  `esmtp_features`, `does_esmtp` and `ehlo_resp` alone. After `close()` and `connect()`
  the next `sendmail()` sends no `EHLO`. A refused `EHLO` falls back to `HELO`, and `sendmail()` then sends
  no `SIZE`; both refused raises `SMTPHeloError`.
* `starttls()` clears `esmtp_features`, `does_esmtp`, `ehlo_resp` and
  `helo_resp`, as `quit()` does, and the next `login()` sends `EHLO` again;
  without `STARTTLS` advertised it raises `SMTPNotSupportedError` and sends only
  `EHLO`. The context `starttls()` builds by default, and `SMTP_SSL.context`,
  have `verify_mode == CERT_NONE` and `check_hostname` false; a context
  passed to either is the one used. `SMTP_SSL` wraps the socket while the greeting
  is still unread, and defaults to port 465. On 3.12+ neither `SMTP_SSL()` nor
  `starttls()` takes `keyfile` or `certfile`; below 3.12 both do.
* `login()` picks `CRAM-MD5` over `PLAIN` over `LOGIN` whatever order the
  server lists them in, moves to the next when one is refused, and with a
  wrong password tries each advertised one and raises
  `SMTPAuthenticationError`. `PLAIN` is one exchange;
  `LOGIN` two, and `PLAIN` two with `initial_response_ok=False`; `CRAM-MD5`
  two, where MD5 is available. No `AUTH` raises `SMTPNotSupportedError`, no
  common mechanism `SMTPException`. `auth()` against a server that
  challenges forever raises `SMTPException` after answering five challenges
  with an initial response and six without; the page's "at most six" counts
  answered challenges, not exchanges.
* Low-level rows: `mail()`, `rcpt()`, `rset()`, `noop()`, `verify()`,
  `vrfy()`, `expn()`, `help()` and `docmd()` make one exchange each and
  `data()` two; `data()` doubles leading dots and rewrites lone `\\n` and
  `\\r` in a `str`, and leaves `bytes` line endings alone. `putcmd()` with
  CR or LF raises `ValueError` and sends nothing. `send()` writes its
  argument unchanged. A reply line of 8,192 bytes, CRLF included, is read
  and one of 8,193 raises `SMTPResponseException` with code 500.
* Connection rows: a greeting other than `220` raises `SMTPConnectError`;
  `connect('host:2525')` connects to port 2525; `SMTP()` with no host calls
  `socket.getfqdn()` once and with `local_hostname` not at all; leaving a
  `with` block sends `QUIT`, and does not raise when the server has already
  closed; `quit()` sends `QUIT` and clears the `EHLO` state; `close()` sends
  nothing; a command before `connect()` raises `SMTPServerDisconnected`;
  `set_debuglevel(1)` writes `send:` and `reply:` lines to standard error
  and level 2 prefixes each with a time. `LMTP` sends `LHLO` over a real
  Unix socket and defaults to port 2003 over TCP.
* The module functions, the port constants and the exception hierarchy and
  attributes are asserted by value.
* Every fenced Python block runs in its own subprocess. Blocks that connect
  run against `FakeServer`, installed by a prelude that replaces
  `socket.create_connection()` and `ssl.SSLContext.wrap_socket()`. A mutated
  assertion in a block is asserted to fail. The blocks' assertions about
  advertised extensions, refused recipients, the `SIZE` limit and
  authentication codes hold because the fake has those policies: `SIZE`
  and `STARTTLS` before TLS, `AUTH PLAIN LOGIN` after it, `unknown...`
  recipients refused with 550. A real server's answers differ.

Not settled here:

* Every waiting cost: round trips, DNS, the local host-name lookup the
  constructor makes, connection setup and the TLS handshake. The page counts
  exchanges instead of pricing them, and only the counts are run.
* Server behaviour: that servers commonly advertise `AUTH` only after
  `STARTTLS` is the fake's configuration, not something the client decides,
  and that `starttls()` must forget the `EHLO` answer is RFC 3207.
* The O(n) bounds on replies follow from `getreply()` reading and joining
  every line of a reply once, read from Lib/smtplib.py; only `EHLO` is
  varied in n. `ehlo()` appends each `AUTH` line to the value built so far,
  so a reply of thousands of `AUTH` lines costs more than O(n); servers
  send one or two, and that shape is not priced. `quotedata()` is two
  `re.sub()` passes and `send()` one `sendall()`, read from the source and
  checked only by value on small inputs. `quoteaddr()` parses with
  `email.utils.parseaddr()`, whose cost on deeply nested comments is not
  priced; only plain addresses are asserted.
* `send_message()` serializes the message with the email package's
  generator, whose cost depends on the MIME structure, not only on m; only
  a flat text message is measured here. `auth()` excludes the callback's
  own work and the length of its responses, which the caller controls;
  `auth()` base64-encodes each response once. `auth_cram_md5()` runs one
  HMAC-MD5 over the challenge, linear in its length, read from
  Lib/smtplib.py and asserted only by value on one challenge; the challenge
  length is not varied. Addresses, credentials and command arguments are priced at
  O(1) by the page's cost model and are not varied, nor is the number of
  `mail_options` or `rcpt_options`.
* On builds without MD5, 3.13.8+ and 3.14 leave `CRAM-MD5` out of what
  `login()` tries, and earlier releases call `hmac` with MD5 and raise
  `ValueError`, read from Lib/smtplib.py on v3.12.12, v3.13.8 and v3.14.0.
  The `CRAM-MD5` test is skipped where MD5 is unavailable, and no FIPS
  build is run.
* `login()` is asserted to raise `SMTPAuthenticationError` with code 535
  after every mechanism fails; the mechanisms all answer 535, so which
  failure's code is kept is not distinguished. Socket closure is observed as
  `smtp.sock is None`, not as a close call on the fake.
* `LMTP.sendmail()` reads one reply after the payload, where LMTP servers
  send one per recipient; the page does not price LMTP beyond the
  constructor and the fake does not model per-recipient replies.
* The page-scoped audit's classification list names `SMTP.sock`,
  `SMTP.file`, `SMTP.debuglevel`, `SMTP.default_port`, `SMTP.ehlo_msg` and
  the `winerror` attribute every exception inherits from `OSError`. They are
  implementation attributes the official documentation does not describe and
  are not on the page.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import inspect
import os
import pathlib
import re
import smtplib
import socket
import ssl
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable
from email.message import EmailMessage
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "smtplib.md"
EXPECTED_BLOCKS = 7
USERS = {"user@example.com": "app-password"}
CLIENT = "client.example.com"


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def md5_available() -> bool:
    try:
        hmac.digest(b"", b"", "md5")
    except ValueError:
        return False
    return True


# --- The fake server ------------------------------------------------------------


class FakeServer:
    """An SMTP server that answers in process, one reply per command line.

    It refuses any recipient whose address starts with `unknown`, answers
    `421` to one starting with `closing`, a `MAIL`
    whose `SIZE` exceeds `size_limit`, and a payload containing
    `X-Reject: yes`. It advertises `STARTTLS` before TLS and `AUTH` after it.
    Setting `gone` makes it stop answering, as a closed connection would.
    """

    CHALLENGE = b"<1896.697170952@mail.example.com>"

    def __init__(
        self,
        *,
        greeting: bytes = b"220 mail.example.com ESMTP fake",
        size_limit: int = 1_000_000,
        auth: str = "PLAIN LOGIN",
        extra_features: tuple[str, ...] = (),
        refuse_ehlo: bool = False,
        refuse_helo: bool = False,
        refuse_mechanisms: tuple[str, ...] = (),
        keep_data: bool = True,
    ) -> None:
        self.size_limit = size_limit
        self.auth = auth
        self.extra_features = extra_features
        self.refuse_ehlo = refuse_ehlo
        self.refuse_helo = refuse_helo
        self.refuse_mechanisms = refuse_mechanisms
        self.keep_data = keep_data
        self.commands: list[bytes] = []
        self.messages: list[bytes] = []
        self.replies = 0
        self.data_writes = 0
        self.overlapped = 0
        self.tls = False
        self.closed = False
        self.gone = False
        self.out = bytearray(greeting + b"\r\n")
        self._pending = bytearray()
        self._in_data = False
        self._auth: tuple[str, int] | None = None
        self._user = ""
        self._recipients = 0

    def verbs(self) -> list[str]:
        return [line.split(b" ", 1)[0].decode().upper() for line in self.commands]

    def reply(self, code: int, *lines: str) -> None:
        self.replies += 1
        texts = lines or ("OK",)
        for index, text in enumerate(texts):
            separator = " " if index == len(texts) - 1 else "-"
            self.out += f"{code}{separator}{text}\r\n".encode()

    def features(self) -> list[str]:
        found = [f"SIZE {self.size_limit}", "8BITMIME"]
        if not self.tls:
            found.append("STARTTLS")
        elif self.auth:
            found.append(f"AUTH {self.auth}")
        return found + list(self.extra_features)

    def receive(self, data: bytes) -> None:
        if self.gone:
            self.commands.append(bytes(data).strip())
            return
        if self.out:
            self.overlapped += 1
        if self._in_data:
            self._receive_data(data)
            return
        self._pending += data
        while not self._in_data and b"\r\n" in self._pending:
            line, _, rest = bytes(self._pending).partition(b"\r\n")
            self._pending = bytearray(rest)
            self.commands.append(line)
            self._command(line.decode("utf-8"))

    def _receive_data(self, data: bytes) -> None:
        self.data_writes += 1
        if self.keep_data:
            self.messages.append(data)
        if data.endswith(b"\r\n.\r\n"):
            self._in_data = False
            if self.keep_data and b"X-Reject: yes" in data:
                self.reply(554, "5.6.0 Message rejected")
            else:
                self.reply(250, "2.0.0 Queued")

    FIXED_REPLIES: dict[str, tuple[int, tuple[str, ...]]] = {
        "STARTTLS": (220, ("2.0.0 Ready to start TLS",)),
        "RSET": (250, ("2.0.0 OK",)),
        "NOOP": (250, ("2.0.0 OK",)),
        "VRFY": (252, ("2.5.2 Cannot VRFY user",)),
        "EXPN": (250, ("Ann <ann@example.com>", "Bob <bob@example.com>")),
        "HELP": (214, ("Commands:", "EHLO HELO MAIL RCPT DATA RSET NOOP QUIT")),
    }

    def _command(self, line: str) -> None:
        if self._auth is not None:
            self._continue_auth(line)
            return
        verb, _, args = line.partition(" ")
        verb = verb.upper()
        handler = getattr(self, f"_do_{verb.lower()}", None)
        if handler is not None:
            handler(args)
        elif verb in self.FIXED_REPLIES:
            code, texts = self.FIXED_REPLIES[verb]
            self.reply(code, *texts)
        else:
            self.reply(502, "5.5.2 Command not recognized")

    def _do_ehlo(self, args: str) -> None:
        if self.refuse_ehlo:
            self.reply(502, "5.5.1 Unrecognized command")
        else:
            self.reply(250, "mail.example.com", *self.features())

    _do_lhlo = _do_ehlo

    def _do_helo(self, args: str) -> None:
        if self.refuse_helo:
            self.reply(501, "5.5.4 Refused")
        else:
            self.reply(250, "mail.example.com")

    def _do_auth(self, args: str) -> None:
        self._start_auth(args)

    def _do_mail(self, args: str) -> None:
        self._recipients = 0
        params = dict(p.upper().split("=", 1) for p in args.split()[1:] if "=" in p)
        if int(params.get("SIZE", 0)) > self.size_limit:
            self.reply(552, "5.3.4 Message size exceeds fixed limit")
        else:
            self.reply(250, "2.1.0 Sender OK")

    def _do_rcpt(self, args: str) -> None:
        if args.lower().startswith("to:<closing"):
            self.reply(421, "4.3.2 Shutting down")
        elif args.lower().startswith("to:<unknown"):
            self.reply(550, "5.1.1 No such user")
        else:
            self._recipients += 1
            self.reply(250, "2.1.5 Recipient OK")

    def _do_data(self, args: str) -> None:
        if self._recipients:
            self._in_data = True
            self.reply(354, "End data with <CR><LF>.<CR><LF>")
        else:
            self.reply(503, "5.5.1 No valid recipients")

    def _do_quit(self, args: str) -> None:
        self.reply(221, "2.0.0 Bye")
        self.closed = True

    def _start_auth(self, args: str) -> None:
        mechanism, _, initial = args.partition(" ")
        mechanism = mechanism.upper()
        if mechanism in self.refuse_mechanisms:
            self.reply(535, "5.7.8 Authentication failed")
        elif mechanism == "PLAIN" and initial:
            self._check_plain(initial)
        elif mechanism == "PLAIN":
            self._auth = ("PLAIN", 0)
            self.reply(334, "")
        elif mechanism == "LOGIN" and initial:
            self._user = base64.b64decode(initial).decode()
            self._auth = ("LOGIN", 1)
            self.reply(334, "UGFzc3dvcmQ6")
        elif mechanism == "LOGIN":
            self._auth = ("LOGIN", 0)
            self.reply(334, "VXNlcm5hbWU6")
        elif mechanism == "CRAM-MD5":
            self._auth = ("CRAM-MD5", 0)
            self.reply(334, base64.b64encode(self.CHALLENGE).decode())
        elif mechanism == "X-LOOP":
            self._auth = ("X-LOOP", 0)
            self.reply(334, "")
        else:
            self.reply(504, "5.5.4 Unrecognized authentication type")

    def _finish_auth(self, accepted: bool) -> None:
        self._auth = None
        if accepted:
            self.reply(235, "2.7.0 Authentication successful")
        else:
            self.reply(535, "5.7.8 Authentication failed")

    def _check_plain(self, encoded: str) -> None:
        _, user, password = base64.b64decode(encoded).decode().split("\0")
        self._finish_auth(USERS.get(user) == password)

    def _continue_auth(self, line: str) -> None:
        assert self._auth is not None
        mechanism, step = self._auth
        if mechanism == "PLAIN":
            self._check_plain(line)
        elif mechanism == "LOGIN" and step == 0:
            self._user = base64.b64decode(line).decode()
            self._auth = ("LOGIN", 1)
            self.reply(334, "UGFzc3dvcmQ6")
        elif mechanism == "LOGIN":
            self._finish_auth(USERS.get(self._user) == base64.b64decode(line).decode())
        elif mechanism == "CRAM-MD5":
            user, _, digest = base64.b64decode(line).decode().partition(" ")
            key = USERS.get(user, "").encode()
            self._finish_auth(digest == hmac.HMAC(key, self.CHALLENGE, "md5").hexdigest())
        else:
            self.reply(334, "")


class FakeReader:
    """The `makefile('rb')` side: hands out what the server has written."""

    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def readline(self, limit: int = -1) -> bytes:
        out = self.server.out
        end = out.find(b"\n")
        end = len(out) if end < 0 else end + 1
        if limit >= 0:
            end = min(end, limit)
        line = bytes(out[:end])
        del out[:end]
        return line

    def close(self) -> None:
        pass


class FakeSocket:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.sends = 0

    def sendall(self, data: bytes) -> None:
        self.sends += 1
        self.server.receive(data)

    def makefile(self, mode: str = "rb") -> FakeReader:
        return FakeReader(self.server)

    def close(self) -> None:
        pass


class Network:
    """What the patched transport saw: servers made, addresses, TLS contexts."""

    def __init__(self) -> None:
        self.options: dict[str, Any] = {}
        self.servers: list[FakeServer] = []
        self.addresses: list[tuple[str, int]] = []
        self.contexts: list[ssl.SSLContext] = []
        self.greeting_unread_at_wrap: list[bool] = []

    @property
    def server(self) -> FakeServer:
        return self.servers[-1]

    def create_connection(self, address: tuple[str, int], *args: Any, **kwargs: Any) -> Any:
        self.addresses.append(address)
        server = FakeServer(**self.options)
        self.servers.append(server)
        return FakeSocket(server)

    def wrap_socket(self, context: ssl.SSLContext, sock: Any, *args: Any, **kwargs: Any) -> Any:
        self.contexts.append(context)
        self.greeting_unread_at_wrap.append(sock.server.out.startswith(b"220 mail.example"))
        sock.server.tls = True
        return sock


def install_fake_network() -> Network:
    """Route `smtplib` to fresh `FakeServer`s for the rest of the process."""
    network = Network()

    def wrap_socket(self: ssl.SSLContext, sock: Any, *args: Any, **kwargs: Any) -> Any:
        return network.wrap_socket(self, sock, *args, **kwargs)

    socket.create_connection = network.create_connection  # type: ignore[assignment]
    ssl.SSLContext.wrap_socket = wrap_socket  # type: ignore[method-assign]
    return network


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> Network:
    net = Network()

    def wrap_socket(self: ssl.SSLContext, sock: Any, *args: Any, **kwargs: Any) -> Any:
        return net.wrap_socket(self, sock, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", net.create_connection)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap_socket)
    return net


def connect(network: Network, **options: Any) -> smtplib.SMTP:
    network.options = options
    return smtplib.SMTP("smtp.example.com", 587, local_hostname=CLIENT)


# --- SMTP connections -----------------------------------------------------------


class TestConnecting:
    """`smtplib.SMTP(host, ...)` | O(n) | O(n): the greeting and nothing else.

    `EHLO` is deferred to the first command that needs it, so a constructor
    that sent it would show in the fake's command list.
    """

    def test_the_constructor_reads_the_greeting_and_sends_nothing(self, network: Network) -> None:
        smtp = connect(network)

        assert network.server.commands == []
        assert network.server.out == b"", "the greeting was not read"
        smtp.close()

    def test_ehlo_is_sent_by_the_first_send_only(self, network: Network) -> None:
        smtp = connect(network)
        smtp.sendmail("a@example.com", ["b@example.com"], b"Subject: 1\r\n\r\n")
        smtp.sendmail("a@example.com", ["b@example.com"], b"Subject: 2\r\n\r\n")

        assert network.server.verbs().count("EHLO") == 1
        assert network.server.verbs()[0] == "EHLO"
        smtp.close()

    def test_a_bad_greeting_raises_connect_error(self, network: Network) -> None:
        network.options = {"greeting": b"554 go away"}
        with pytest.raises(smtplib.SMTPConnectError) as caught:
            smtplib.SMTP("smtp.example.com", local_hostname=CLIENT)

        assert caught.value.smtp_code == 554

    def test_connect_splits_host_and_port(self, network: Network) -> None:
        smtp = smtplib.SMTP(local_hostname=CLIENT)
        assert network.addresses == [], "no host, no connection"

        code, _ = smtp.connect("smtp.example.com:2525")

        assert code == 220
        assert network.addresses == [("smtp.example.com", 2525)]
        smtp.close()

    def test_the_local_name_is_looked_up_unless_given(
        self, network: Network, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lookups: list[int] = []
        monkeypatch.setattr(socket, "getfqdn", lambda *a: lookups.append(1) or "c.example.com")

        smtplib.SMTP()
        assert lookups == [1], "SMTP() with no host still looks up the local name"
        assert network.addresses == []

        smtplib.SMTP(local_hostname=CLIENT)
        assert lookups == [1]

    def test_leaving_a_with_block_sends_quit(self, network: Network) -> None:
        with connect(network) as smtp:
            smtp.noop()

        assert network.server.verbs() == ["NOOP", "QUIT"]

    def test_leaving_a_with_block_tolerates_a_closed_server(self, network: Network) -> None:
        with connect(network) as smtp:
            network.server.gone = True

        assert network.server.verbs() == ["QUIT"]
        assert smtp.sock is None

    def test_quit_sends_quit_and_forgets_ehlo(self, network: Network) -> None:
        smtp = connect(network)
        smtp.ehlo()
        smtp.helo()
        assert smtp.esmtp_features and smtp.helo_resp is not None

        code, _ = smtp.quit()

        assert code == 221
        assert network.server.verbs()[-1] == "QUIT"
        assert smtp.esmtp_features == {} and smtp.ehlo_resp is None
        assert smtp.helo_resp is None
        assert smtp.does_esmtp is False and smtp.sock is None

    def test_close_sends_nothing(self, network: Network) -> None:
        smtp = connect(network)
        smtp.close()

        assert network.server.commands == []
        assert smtp.sock is None

    def test_a_command_before_connect_raises(self) -> None:
        smtp = smtplib.SMTP(local_hostname=CLIENT)
        with pytest.raises(smtplib.SMTPServerDisconnected):
            smtp.noop()

    def test_set_debuglevel_writes_the_conversation(
        self, network: Network, capsys: pytest.CaptureFixture[str]
    ) -> None:
        smtp = connect(network)
        smtp.set_debuglevel(1)
        smtp.noop()
        first = capsys.readouterr().err

        smtp.set_debuglevel(2)
        smtp.noop()
        second = capsys.readouterr().err
        smtp.close()

        assert "send: 'noop\\r\\n'" in first and "reply:" in first
        assert not re.match(r"\d\d:\d\d:\d\d", first)
        assert all(re.match(r"\d\d:\d\d:\d\d", line) for line in second.splitlines())


class TestNoPipelining:
    """Every command waits for its reply: the page's exchange counts rest on it.

    The fake counts writes that arrive while a reply is still unread; a
    pipelining client would make that non-zero.
    """

    def test_no_command_is_written_before_the_last_reply_is_read(self, network: Network) -> None:
        smtp = connect(network)
        smtp.starttls()
        smtp.login("user@example.com", "app-password")
        smtp.sendmail("a@example.com", [f"r{i}@example.com" for i in range(20)], b"x\r\n")
        smtp.noop()
        smtp.rset()
        smtp.verify("ann")
        smtp.expn("list")
        smtp.help()
        smtp.quit()

        assert network.server.overlapped == 0


# --- SMTP_SSL and LMTP ----------------------------------------------------------


class TestSMTPSSL:
    """`smtplib.SMTP_SSL(...)`: TLS from the first byte, port 465, and a default
    context that does not verify. The version note on `keyfile` and `certfile`
    is checked by signature on each side of 3.12."""

    def test_the_socket_is_wrapped_before_the_greeting(self, network: Network) -> None:
        smtp = smtplib.SMTP_SSL("smtp.example.com", local_hostname=CLIENT)

        assert network.addresses == [("smtp.example.com", 465)]
        assert network.contexts == [smtp.context]
        assert network.greeting_unread_at_wrap == [True]
        smtp.ehlo()
        assert smtp.has_extn("auth"), "the fake advertises AUTH only over TLS"
        smtp.close()

    def test_the_default_context_does_not_verify(self) -> None:
        smtp = smtplib.SMTP_SSL(local_hostname=CLIENT)

        assert smtp.context.verify_mode == ssl.CERT_NONE
        assert smtp.context.check_hostname is False

    def test_a_given_context_is_the_one_used(self, network: Network) -> None:
        context = ssl.create_default_context()
        smtp = smtplib.SMTP_SSL("smtp.example.com", local_hostname=CLIENT, context=context)

        assert smtp.context is context
        assert network.contexts == [context]
        smtp.close()

    def test_keyfile_and_certfile_exist_only_before_3_12(self) -> None:
        for function in (smtplib.SMTP_SSL.__init__, smtplib.SMTP.starttls):
            parameters = inspect.signature(function).parameters
            if sys.version_info >= (3, 12):
                assert "keyfile" not in parameters and "certfile" not in parameters
            else:
                assert "keyfile" in parameters and "certfile" in parameters


class TestLMTP:
    """`smtplib.LMTP(...)`: `LHLO` for `EHLO`, a Unix socket for a `/` host."""

    def test_the_default_tcp_port_is_2003(self, network: Network) -> None:
        smtplib.LMTP("lmtp.example.com", local_hostname=CLIENT).close()

        assert network.addresses == [("lmtp.example.com", 2003)]

    @pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="needs Unix sockets")
    def test_a_path_is_a_unix_socket_and_lhlo_replaces_ehlo(self) -> None:
        server = FakeServer()
        directory = tempfile.mkdtemp(prefix="lmtp")
        path = os.path.join(directory, "s")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen(1)

        def serve() -> None:
            connection, _ = listener.accept()
            with connection:
                connection.sendall(bytes(server.out))
                server.out.clear()
                while not server.closed:
                    data = connection.recv(65536)
                    if not data:
                        break
                    server.receive(data)
                    connection.sendall(bytes(server.out))
                    server.out.clear()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            with smtplib.LMTP(path, local_hostname=CLIENT) as lmtp:
                assert lmtp.sendmail("a@example.com", ["b@example.com"], b"x\r\n") == {}
        finally:
            thread.join(timeout=10)
            listener.close()
            os.unlink(path)
            os.rmdir(directory)

        assert server.verbs() == ["LHLO", "MAIL", "RCPT", "DATA", "QUIT"]


# --- Extensions and authentication ----------------------------------------------


class TestEhlo:
    """`SMTP.ehlo()` | O(n) | O(n), and the `HELO` fallback.

    Holding the reply's lines fixed at one width while their count grows
    tenfold shows the whole reply retained, in `ehlo_resp` and one
    `esmtp_features` entry per line.
    """

    @pytest.mark.parametrize("lines", [1_000, 10_000])
    def test_every_extension_line_is_kept(self, network: Network, lines: int) -> None:
        extras = tuple(f"X-FEATURE-{index} some parameters" for index in range(lines))
        smtp = connect(network, extra_features=extras)

        smtp.ehlo()

        assert len(smtp.esmtp_features) == lines + 3
        assert smtp.ehlo_resp is not None
        assert smtp.ehlo_resp.count(b"\n") == lines + 3
        smtp.close()

    def test_has_extn_ignores_case(self, network: Network) -> None:
        smtp = connect(network)
        smtp.ehlo()

        assert smtp.has_extn("STARTTLS") and smtp.has_extn("starttls")
        assert smtp.does_esmtp is True
        assert not smtp.has_extn("auth")
        smtp.close()

    def test_helo_sets_only_helo_resp(self, network: Network) -> None:
        smtp = connect(network)
        smtp.ehlo()
        features = dict(smtp.esmtp_features)
        ehlo_resp = smtp.ehlo_resp

        smtp.helo()

        assert smtp.helo_resp == b"mail.example.com"
        assert smtp.esmtp_features == features and smtp.does_esmtp is True
        assert smtp.ehlo_resp is ehlo_resp
        smtp.close()

    def test_close_and_connect_keep_the_old_answer(self, network: Network) -> None:
        smtp = connect(network)
        smtp.ehlo()
        smtp.close()
        smtp.connect("smtp.example.com", 587)

        smtp.sendmail("a@example.com", ["b@example.com"], b"x")

        assert network.server.verbs()[0] == "MAIL", "no EHLO on the new connection"
        smtp.close()

    def test_a_refused_ehlo_falls_back_to_helo_without_options(self, network: Network) -> None:
        smtp = connect(network, refuse_ehlo=True)
        smtp.sendmail("a@example.com", ["b@example.com"], b"x\r\n")

        assert network.server.verbs()[:3] == ["EHLO", "HELO", "MAIL"]
        assert b"size=" not in network.server.commands[2].lower()
        assert smtp.helo_resp == b"mail.example.com"
        smtp.close()

    def test_both_refused_raises_helo_error(self, network: Network) -> None:
        smtp = connect(network, refuse_ehlo=True, refuse_helo=True)

        with pytest.raises(smtplib.SMTPHeloError) as caught:
            smtp.login("user@example.com", "app-password")

        assert caught.value.smtp_code == 501
        smtp.close()


class TestStartTLS:
    """`SMTP.starttls(*, context=None)`: one exchange, then forget `EHLO`."""

    def test_it_clears_what_ehlo_learned_and_ehlo_is_sent_again(self, network: Network) -> None:
        smtp = connect(network)
        smtp.helo()
        smtp.ehlo()

        smtp.starttls()

        assert smtp.esmtp_features == {} and smtp.does_esmtp is False
        assert smtp.ehlo_resp is None and smtp.helo_resp is None
        smtp.login("user@example.com", "app-password")
        assert network.server.verbs() == ["HELO", "EHLO", "STARTTLS", "EHLO", "AUTH"]
        smtp.close()

    def test_the_default_context_does_not_verify(self, network: Network) -> None:
        smtp = connect(network)
        smtp.starttls()

        (context,) = network.contexts
        assert context.verify_mode == ssl.CERT_NONE and context.check_hostname is False
        smtp.close()

    def test_a_given_context_is_the_one_used(self, network: Network) -> None:
        context = ssl.create_default_context()
        smtp = connect(network)
        smtp.starttls(context=context)

        assert network.contexts == [context]
        smtp.close()

    def test_without_the_extension_it_raises(self, network: Network) -> None:
        smtp = smtplib.SMTP_SSL("smtp.example.com", local_hostname=CLIENT)

        with pytest.raises(smtplib.SMTPNotSupportedError):
            smtp.starttls()

        assert network.server.verbs() == ["EHLO"]
        smtp.close()


class TestLogin:
    """`SMTP.login()` and `SMTP.auth()`: the mechanism order, the fallback, and
    the exchanges each mechanism takes, counted on the fake."""

    @staticmethod
    def _tls(network: Network, **options: Any) -> smtplib.SMTP:
        network.options = options
        return smtplib.SMTP_SSL("smtp.example.com", local_hostname=CLIENT)

    def _auth_exchanges(self, network: Network, smtp: smtplib.SMTP, **kwargs: Any) -> int:
        smtp.ehlo()
        before = network.server.replies
        smtp.login("user@example.com", "app-password", **kwargs)
        return network.server.replies - before

    def test_plain_is_one_exchange(self, network: Network) -> None:
        smtp = self._tls(network, auth="LOGIN PLAIN")

        assert self._auth_exchanges(network, smtp) == 1
        assert network.server.commands[-1].startswith(b"AUTH PLAIN ")
        smtp.close()

    def test_plain_is_two_without_the_initial_response(self, network: Network) -> None:
        smtp = self._tls(network, auth="PLAIN")

        assert self._auth_exchanges(network, smtp, initial_response_ok=False) == 2
        smtp.close()

    def test_login_is_two_exchanges(self, network: Network) -> None:
        smtp = self._tls(network, auth="LOGIN")

        assert self._auth_exchanges(network, smtp) == 2
        smtp.close()

    @pytest.mark.skipif(not md5_available(), reason="MD5 is unavailable in this build")
    def test_cram_md5_is_preferred_and_two_exchanges(self, network: Network) -> None:
        smtp = self._tls(network, auth="LOGIN PLAIN CRAM-MD5")

        assert self._auth_exchanges(network, smtp) == 2
        assert network.server.commands[-2] == b"AUTH CRAM-MD5"
        smtp.close()

    def test_a_refused_mechanism_moves_to_the_next(self, network: Network) -> None:
        smtp = self._tls(network, auth="PLAIN LOGIN", refuse_mechanisms=("PLAIN",))

        code, _ = smtp.login("user@example.com", "app-password")

        assert code == 235
        auths = [c.split()[1] for c in network.server.commands if c.startswith(b"AUTH")]
        assert auths == [b"PLAIN", b"LOGIN"]
        smtp.close()

    def test_a_wrong_password_tries_every_advertised_mechanism(self, network: Network) -> None:
        smtp = self._tls(network, auth="LOGIN PLAIN")

        with pytest.raises(smtplib.SMTPAuthenticationError) as caught:
            smtp.login("user@example.com", "wrong")

        assert caught.value.smtp_code == 535
        auths = [c.split()[1] for c in network.server.commands if c.startswith(b"AUTH")]
        assert auths == [b"PLAIN", b"LOGIN"]
        smtp.close()

    def test_no_auth_extension_raises_not_supported(self, network: Network) -> None:
        smtp = connect(network)

        with pytest.raises(smtplib.SMTPNotSupportedError):
            smtp.login("user@example.com", "app-password")
        smtp.close()

    def test_no_common_mechanism_raises(self, network: Network) -> None:
        smtp = self._tls(network, auth="GSSAPI")

        with pytest.raises(smtplib.SMTPException, match="No suitable"):
            smtp.login("user@example.com", "app-password")
        smtp.close()

    @pytest.mark.parametrize(("initial", "answered"), [(True, 5), (False, 6)])
    def test_auth_gives_up_on_endless_challenges(
        self, network: Network, initial: bool, answered: int
    ) -> None:
        smtp = self._tls(network)
        smtp.ehlo()
        calls: list[bytes | None] = []

        def authobject(challenge: bytes | None = None) -> str:
            calls.append(challenge)
            return "x"

        with pytest.raises(smtplib.SMTPException, match="infinite loop"):
            smtp.auth("X-LOOP", authobject, initial_response_ok=initial)

        challenges = [c for c in calls if c is not None]
        assert len(challenges) == answered
        smtp.close()

    def test_the_authobjects_answer_from_user_and_password(self) -> None:
        smtp = smtplib.SMTP(local_hostname=CLIENT)
        smtp.user, smtp.password = "ann", "secret"

        assert smtp.auth_plain() == "\0ann\0secret"
        assert smtp.auth_login() == "ann"
        assert smtp.auth_cram_md5() is None, "no initial response"
        if md5_available():
            digest = hmac.HMAC(b"secret", b"challenge", hashlib.md5).hexdigest()
            assert smtp.auth_cram_md5(b"challenge") == f"ann {digest}"


# --- Mail transactions ----------------------------------------------------------


def body_of(size: int) -> bytes:
    line = b"line of text\r\n"
    return b"Subject: x\r\n\r\n" + line * (size // len(line))


class TestSendmailExchanges:
    """`SMTP.sendmail()`: `MAIL`, one `RCPT` per recipient and `DATA`, r + 3
    exchanges, with the message written in one call."""

    @pytest.mark.parametrize("recipients", [1, 10, 100])
    def test_r_plus_three_exchanges(self, network: Network, recipients: int) -> None:
        smtp = connect(network)
        smtp.ehlo()
        before = network.server.replies

        smtp.sendmail("a@example.com", [f"r{i}@example.com" for i in range(recipients)], b"x")

        assert network.server.replies - before == recipients + 3
        assert network.server.verbs().count("RCPT") == recipients
        assert network.server.data_writes == 1, "the message is written in one call"
        smtp.close()

    def test_one_refused_recipient_is_returned(self, network: Network) -> None:
        smtp = connect(network)
        smtp.ehlo()
        before = network.server.replies
        refused = smtp.sendmail(
            "a@example.com", ["ann@example.com", "unknown@example.com"], b"x\r\n"
        )

        assert refused == {"unknown@example.com": (550, b"5.1.1 No such user")}
        assert len(network.server.messages) == 1
        assert network.server.replies - before == 2 + 3, "an accepted message is still r + 3"
        smtp.close()

    def test_all_refused_raises_resets_and_stays_open(self, network: Network) -> None:
        smtp = connect(network)

        with pytest.raises(smtplib.SMTPRecipientsRefused) as caught:
            smtp.sendmail("a@example.com", ["unknown@example.com"], b"x\r\n")

        assert caught.value.recipients == {"unknown@example.com": (550, b"5.1.1 No such user")}
        assert network.server.verbs()[-1] == "RSET"
        assert smtp.noop()[0] == 250
        smtp.close()

    def test_a_421_during_rcpt_raises_even_after_an_accepted_recipient(
        self, network: Network
    ) -> None:
        smtp = connect(network)

        with pytest.raises(smtplib.SMTPRecipientsRefused) as caught:
            smtp.sendmail("a@example.com", ["ann@example.com", "closing@example.com"], b"x")

        assert caught.value.recipients == {"closing@example.com": (421, b"4.3.2 Shutting down")}
        assert "DATA" not in network.server.verbs()
        assert smtp.sock is None

    def test_a_refused_payload_raises_data_error(self, network: Network) -> None:
        smtp = connect(network)

        with pytest.raises(smtplib.SMTPDataError) as caught:
            smtp.sendmail("a@example.com", ["b@example.com"], b"X-Reject: yes\r\n\r\n")

        assert caught.value.smtp_code == 554
        assert network.server.verbs()[-1] == "RSET"
        smtp.close()

    def test_size_refuses_before_the_body_is_sent(self, network: Network) -> None:
        smtp = connect(network, size_limit=1_000)

        with pytest.raises(smtplib.SMTPSenderRefused) as caught:
            smtp.sendmail("a@example.com", ["b@example.com"], b"x" * 1_001)

        assert caught.value.smtp_code == 552
        assert caught.value.sender == "a@example.com"
        assert b"size=1001" in network.server.commands[1].lower()
        assert network.server.data_writes == 0
        assert "DATA" not in network.server.verbs()
        smtp.close()

    def test_a_non_ascii_str_raises_before_mail(self, network: Network) -> None:
        smtp = connect(network)

        with pytest.raises(UnicodeEncodeError):
            smtp.sendmail("a@example.com", ["b@example.com"], "Subject: Café\r\n\r\n")

        assert "MAIL" not in network.server.verbs()
        smtp.close()

    def test_bytes_arrive_byte_for_byte(self, network: Network) -> None:
        smtp = connect(network)
        payload = "Subject: Café\r\n\r\nbody\r\n".encode()

        smtp.sendmail("a@example.com", ["b@example.com"], payload)

        assert network.server.messages == [payload + b".\r\n"]
        smtp.close()


class TestSendmailHoldsTheMessage:
    """`SMTP.sendmail()` | O(m + n) | O(m + n): the whole message, in memory.

    The fake counts the payload without keeping it, so the peak is the
    client's. A streaming client would hold a constant; this one holds more
    than the message, and 10x the message moves the peak about 10x.
    """

    SIZES = (100_000, 1_000_000, 10_000_000)

    def _peak(self, smtp: smtplib.SMTP, message: bytes | str) -> int:
        return peak_bytes(lambda: smtp.sendmail("a@example.com", ["b@example.com"], message))

    def test_the_peak_exceeds_the_message_and_follows_it(self, network: Network) -> None:
        smtp = connect(network, size_limit=10**9, keep_data=False)
        smtp.ehlo()
        bodies = [body_of(size) for size in self.SIZES]

        peaks = [self._peak(smtp, body) for body in bodies]

        for body, peak in zip(bodies, peaks, strict=True):
            assert peak > len(body), f"{len(body)} bytes peaked at only {peak}"
        for small, large in pairwise(peaks):
            assert 5 < large / small < 20, f"10x the message moved the peak x{large / small:.1f}"
        smtp.close()

    @pytest.mark.timing
    def test_a_hundred_times_the_message_costs_about_a_hundred_times(
        self, network: Network
    ) -> None:
        smtp = connect(network, size_limit=10**9, keep_data=False)
        smtp.ehlo()
        small, large = body_of(self.SIZES[0]), body_of(self.SIZES[-1])

        small_ns = best_ns(lambda: smtp.sendmail("a@example.com", ["b@example.com"], small))
        large_ns = best_ns(lambda: smtp.sendmail("a@example.com", ["b@example.com"], large))

        ratio = large_ns / small_ns
        assert 20 < ratio < 1_000, (
            f"100x the message cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "linear gives x100 and quadratic x10,000"
        )
        smtp.close()


class TestSendMessage:
    """`SMTP.send_message()`: serialize, then `sendmail()`; `Bcc` addressed but
    not sent."""

    @staticmethod
    def _message(body: str = "Hello\n") -> EmailMessage:
        message = EmailMessage()
        message["From"] = "sender@example.com"
        message["To"] = "ann@example.com"
        message["Cc"] = "cat@example.com"
        message["Bcc"] = "hidden@example.com"
        message["Subject"] = "Hi"
        message.set_content(body)
        return message

    def test_bcc_is_a_recipient_but_not_a_header(self, network: Network) -> None:
        smtp = connect(network)
        message = self._message()

        assert smtp.send_message(message) == {}

        rcpts = [c for c in network.server.commands if c.upper().startswith(b"RCPT")]
        assert [r.lower() for r in rcpts] == [
            b"rcpt to:<ann@example.com>",
            b"rcpt to:<hidden@example.com>",
            b"rcpt to:<cat@example.com>",
        ]
        (payload,) = network.server.messages
        assert b"Bcc" not in payload and b"To: ann@example.com" in payload
        assert message["Bcc"] == "hidden@example.com", "the caller's message is unchanged"
        smtp.close()

    def test_a_non_ascii_body_is_sent_as_serialized(self, network: Network) -> None:
        smtp = connect(network)

        assert smtp.send_message(self._message("Café\n")) == {}

        (payload,) = network.server.messages
        assert "Café".encode() in payload
        smtp.close()

    def test_one_resent_block_supplies_the_recipients(self, network: Network) -> None:
        smtp = connect(network)
        message = self._message()
        message["Resent-Date"] = "Mon, 1 Jan 2024 00:00:00 +0000"
        message["Resent-From"] = "fwd@example.com"
        message["Resent-To"] = "dee@example.com"

        assert smtp.send_message(message) == {}

        commands = network.server.commands
        assert [c.lower() for c in commands if c.upper().startswith(b"RCPT")] == [
            b"rcpt to:<dee@example.com>"
        ]
        assert b"mail from:<fwd@example.com>" in commands[1].lower()

        message["Resent-Date"] = "Tue, 2 Jan 2024 00:00:00 +0000"
        with pytest.raises(ValueError, match="Resent-"):
            smtp.send_message(message)
        smtp.close()

    def test_a_non_ascii_address_needs_smtputf8(self, network: Network) -> None:
        smtp = connect(network)
        message = self._message()
        message.replace_header("To", "jörg@example.com")

        with pytest.raises(smtplib.SMTPNotSupportedError):
            smtp.send_message(message)
        assert "MAIL" not in network.server.verbs()
        smtp.close()

        smtp = connect(network, extra_features=("SMTPUTF8",))
        assert smtp.send_message(message) == {}
        mail = next(c for c in network.server.commands if c.upper().startswith(b"MAIL"))
        assert b"SMTPUTF8" in mail and b"BODY=8BITMIME" in mail
        smtp.close()

    def test_the_peak_follows_the_body(self, network: Network) -> None:
        smtp = connect(network, size_limit=10**9, keep_data=False)
        smtp.ehlo()
        small = self._message("line of text\n" * 10_000)
        large = self._message("line of text\n" * 100_000)

        small_peak = peak_bytes(lambda: smtp.send_message(small))
        large_peak = peak_bytes(lambda: smtp.send_message(large))

        assert 5 < large_peak / small_peak < 20, (
            f"10x the body moved the peak x{large_peak / small_peak:.1f}"
        )
        smtp.close()


class TestSession:
    """The page's session: `EHLO` twice, around `STARTTLS`, then `AUTH` and the
    send. With `PLAIN` offered that is five exchanges before `MAIL` and four
    for a one-recipient message."""

    def test_the_session_on_the_page(self, network: Network) -> None:
        with connect(network) as smtp:
            assert network.server.replies == 0
            smtp.starttls(context=ssl.create_default_context())
            smtp.login("user@example.com", "app-password")
            before = network.server.replies + 1  # the greeting
            message = TestSendMessage._message()
            del message["Cc"], message["Bcc"]
            assert smtp.send_message(message) == {}
            during = network.server.replies + 1 - before

        assert before == 5
        assert during == 4
        assert network.server.verbs() == [
            "EHLO", "STARTTLS", "EHLO", "AUTH", "MAIL", "RCPT", "DATA", "QUIT",
        ]  # fmt: skip


# --- Low-level commands ---------------------------------------------------------


class TestLowLevelCommands:
    """The one-exchange command methods, `data()`, `putcmd()`, `send()` and
    `getreply()`."""

    def test_each_command_method_is_one_exchange(self, network: Network) -> None:
        smtp = connect(network)
        smtp.ehlo()
        calls: list[Callable[[], Any]] = [
            lambda: smtp.mail("a@example.com"),
            lambda: smtp.rcpt("b@example.com"),
            smtp.rset,
            smtp.noop,
            lambda: smtp.verify("ann"),
            lambda: smtp.vrfy("ann"),
            lambda: smtp.expn("list"),
            smtp.help,
            lambda: smtp.docmd("NOOP"),
        ]
        for call in calls:
            before = network.server.replies
            call()
            assert network.server.replies - before == 1, call
        assert smtplib.SMTP.vrfy is smtplib.SMTP.verify
        assert smtp.help().startswith(b"Commands:")
        assert smtp.expn("list") == (250, b"Ann <ann@example.com>\nBob <bob@example.com>")
        smtp.close()

    def test_data_is_two_exchanges_and_quotes_the_message(self, network: Network) -> None:
        smtp = connect(network)
        smtp.mail("a@example.com")
        smtp.rcpt("b@example.com")
        before = network.server.replies

        code, _ = smtp.data(".first\nsecond\rthird\r\n")

        assert code == 250
        assert network.server.replies - before == 2
        assert network.server.messages == [b"..first\r\nsecond\r\nthird\r\n.\r\n"]

        smtp.mail("a@example.com")
        smtp.rcpt("b@example.com")
        smtp.data(b".first\nsecond")
        assert network.server.messages[-1] == b"..first\nsecond\r\n.\r\n"
        smtp.close()

    def test_putcmd_refuses_line_breaks(self, network: Network) -> None:
        smtp = connect(network)

        for argument in ("a\r\nRSET", "a\nb", "a\rb"):
            with pytest.raises(ValueError, match="newline"):
                smtp.putcmd("vrfy", argument)

        assert network.server.commands == []
        smtp.close()

    def test_send_writes_its_argument_unchanged(self, network: Network) -> None:
        smtp = connect(network)
        smtp.send(b"NOOP\r\n")
        smtp.send("RSET\r\n")

        assert network.server.commands == [b"NOOP", b"RSET"]
        assert smtp.getreply() == (250, b"2.0.0 OK")
        assert smtp.getreply() == (250, b"2.0.0 OK")
        smtp.close()

    def test_getreply_joins_a_multiline_reply(self, network: Network) -> None:
        smtp = connect(network)
        smtp.putcmd("expn", "list")

        assert smtp.getreply() == (250, b"Ann <ann@example.com>\nBob <bob@example.com>")
        smtp.close()

    def test_a_reply_line_over_8192_bytes_raises(self, network: Network) -> None:
        fits = b"220 " + b"x" * (8_192 - 6)
        network.options = {"greeting": fits}
        smtplib.SMTP("smtp.example.com", local_hostname=CLIENT).close()

        network.options = {"greeting": fits + b"x"}
        with pytest.raises(smtplib.SMTPResponseException) as caught:
            smtplib.SMTP("smtp.example.com", local_hostname=CLIENT)
        assert caught.value.smtp_code == 500


# --- Module functions, constants and exceptions ---------------------------------


class TestModuleFunctions:
    def test_quoteaddr_returns_the_bare_address_in_brackets(self) -> None:
        assert smtplib.quoteaddr("Ann <ann@example.com>") == "<ann@example.com>"
        assert smtplib.quoteaddr("ann@example.com") == "<ann@example.com>"

    def test_quotedata_rewrites_line_endings_and_leading_dots(self) -> None:
        assert smtplib.quotedata(".a\nb\r.c\r\n") == "..a\r\nb\r\n..c\r\n"

    def test_the_ports(self) -> None:
        assert (smtplib.SMTP_PORT, smtplib.SMTP_SSL_PORT, smtplib.LMTP_PORT) == (25, 465, 2003)


class TestExceptions:
    """The hierarchy and the attributes the page names."""

    RESPONSE = (
        smtplib.SMTPSenderRefused,
        smtplib.SMTPDataError,
        smtplib.SMTPConnectError,
        smtplib.SMTPHeloError,
        smtplib.SMTPAuthenticationError,
    )

    def test_the_hierarchy(self) -> None:
        assert issubclass(smtplib.SMTPException, OSError)
        for cls in self.RESPONSE:
            assert issubclass(cls, smtplib.SMTPResponseException)
        for cls in (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPNotSupportedError,
            smtplib.SMTPServerDisconnected,
        ):
            assert issubclass(cls, smtplib.SMTPException)
            assert not issubclass(cls, smtplib.SMTPResponseException)

    def test_the_attributes(self) -> None:
        error = smtplib.SMTPResponseException(421, b"closing")
        assert (error.smtp_code, error.smtp_error) == (421, b"closing")
        refused = smtplib.SMTPSenderRefused(552, b"too big", "a@example.com")
        assert refused.sender == "a@example.com"
        recipients = {"b@example.com": (550, b"no")}
        assert smtplib.SMTPRecipientsRefused(recipients).recipients is recipients


# --- The page's examples --------------------------------------------------------


PRELUDE = (
    "import sys\n"
    f"sys.path.insert(0, {str(pathlib.Path(__file__).parent)!r})\n"
    "import test_smtplib_complexity\n"
    "test_smtplib_complexity.install_fake_network()\n"
)


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
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


def _connects(source: str) -> bool:
    return "smtplib.SMTP" in source


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text((PRELUDE if _connects(source) else "") + source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess; the ones that connect reach a
    `FakeServer` through the prelude, and the quoting block runs without it."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert sum(not _connects(source) for _, source in blocks) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "refused['unknown@example.com']" in s)
        mutated = source.replace(
            "refused['unknown@example.com'][0] == 550",
            "refused['unknown@example.com'][0] == 250",
            1,
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
