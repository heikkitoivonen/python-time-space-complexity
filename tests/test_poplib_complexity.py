"""Tests for docs/stdlib/poplib.md.

The page prices the client's share of each call - sending one command line,
reading the reply, holding what the reply returns - and counts the exchanges
each call makes, since waiting for the server is outside every bound. No test
here talks to a real POP3 server. `FakeServer` answers each command line in
process, behind a `FakeSocket` that offers the `sendall()` and
`makefile('rb')` that `poplib` reads and writes through on every supported
version, so every exchange runs through the module's own code. The fake counts
the replies it sends, which is the exchange count, the lines the client reads,
and the writes it receives while a reply is still unread, which is pipelining.
Space claims are settled by traced allocation; the one growth rate only a
stopwatch shows is timed at two sizes a hundredfold apart.

Measurement scope:

* Exchanges are counted as the replies the fake sends after its greeting. The
  constructor sends no command and reads the greeting; `user()`, `pass_()`,
  `apop()`, `rpop()`, `capa()`, `utf8()`, `stat()`, `list()`, `uidl()`,
  `retr()`, `top()`, `dele()`, `rset()`, `noop()` and `quit()` make one each,
  and `stls()` two, `CAPA` then `STLS`. `getwelcome()` and
  `set_debuglevel()` make none. No command is written while a reply is
  unread, over a whole session of every command method.
* Single-line replies: `stat()` and `list(which)` read one line from a
  mailbox of 10 messages and of 10,000. A greeting of 2,048 bytes, CRLF
  included, is read; one of 2,049 raises `error_proto('line too long')`, and
  so does a 2,049-byte line inside a message `retr()` is reading.
* Multi-line replies: `list()` and `uidl()` read m + 2 lines for 10 and
  1,000 messages, the status line, one per message and the terminator.
  `retr()` of a message of 1,000 and of 100,000 lines returns every line; with
  the reply built before the call, so that only the client allocates, its
  traced peak rises more than 20x across that step and exceeds the message's
  size in bytes. A timing test on one connection asserts that the 100x step
  costs between 20x and 1,000x, where linear gives 100x and quadratic
  10,000x; the fake's own linear work to produce the reply is inside it.
* Retrieved lines: a line the fake sends as `..hidden` comes back as
  `.hidden`, `octets` is the sum of each returned line's length plus two, and
  joining the lines with CRLF gives the stored message back. `top(n, 0)`
  returns what the fake sends, the headers alone, in the shape `retr()` uses.
* Authentication: `pass_()` with a wrong password raises `error_proto`
  carrying the `-ERR` reply as bytes. `apop()` sends the MD5 hex digest of the
  greeting's timestamp followed by the secret, which the fake checks, and
  against a greeting with no timestamp raises `error_proto` with nothing sent.
* TLS: `stls()` sends `CAPA` then `STLS` and wraps the socket with the
  context it was given; against a server not advertising `STLS` it raises
  after `CAPA` alone; a second call and `POP3_SSL.stls()` raise with nothing
  sent. `POP3_SSL` wraps the socket while the greeting is still unread and
  defaults to port 995, `POP3` to 110. The context both build by default has
  `verify_mode == CERT_NONE` and `check_hostname` false, and the
  `ssl.create_default_context()` the page recommends has `CERT_REQUIRED` and
  `check_hostname` true. On 3.12+
  `POP3_SSL()` takes neither `keyfile` nor `certfile` and its `timeout` is
  keyword-only; below 3.12 it takes both and `timeout` by position.
  `POP3.stls()` takes `context` alone on every supported version.
* `capa()` returns `{name: [arguments]}` and raises
  `error_proto('-ERR CAPA not supported by server')` on an `-ERR` reply.
* Connection rows: `timeout=0` raises `ValueError` before connecting;
  `POP3` has no `__enter__`; `quit()` sends `QUIT` and leaves `sock` and
  `file` as `None`; `getwelcome()` returns the same object each call.
  `set_debuglevel(1)` prints one `*cmd*` line per command and no line read;
  level 2 prints a `*get*` line for every line of a retrieved message.
* `error_proto` subclasses `Exception` and not `OSError`; a closed
  connection raises `error_proto('-ERR EOF')`, and an `OSError` from the
  socket reaches the caller unwrapped.
* Every fenced Python block runs in its own subprocess against a
  `FakeServer`, installed by a prelude that replaces
  `socket.create_connection()` and `ssl.SSLContext.wrap_socket()`, and a
  mutated assertion in a block is asserted to fail. The blocks' assertions
  about message counts, sizes, subjects, `UIDL` ids and `STLS` hold because
  the fake holds the three messages in `MAILBOX` and advertises `STLS` before
  TLS; a real server's answers differ.

Not settled here:

* Every waiting cost: round trips, DNS, connection setup and the TLS
  handshake. The page counts exchanges instead of pricing them, and only the
  counts are run.
* Server behaviour: that `dele()` only marks until `QUIT`, that `rset()`
  clears the marks, that `STAT` leaves marked messages out, that the mailbox
  is locked from `PASS` to `QUIT`, that a session ending without `QUIT`
  deletes nothing, that `TOP` does not set the seen flag and that `UIDL` ids
  persist across sessions are RFC 1939 and the official documentation, and
  hold on the fake only because it implements them.
* The O(n) bounds follow from `_getlongresp()` reading and appending each
  line once, read from Lib/poplib.py on every supported release; only
  `retr()`, `list()` and `uidl()` are varied in n. `capa()` and `top()`
  share that path and are checked by value. Line length is capped at 2,048
  bytes by `_MAXLINE`, so line count and byte count grow together; lines
  near the cap are not varied. User names, passwords and message numbers are
  priced at O(1) by the page's cost model and are not varied.
* `quit()` closes the connection only once `QUIT` is answered; a failed
  `QUIT` leaves the socket open, which the page does not price.
* `apop()` hashes the timestamp and the secret once; neither length is
  varied.
* The page-scoped audit's classification list names `POP3.close`,
  `POP3.encoding`, `POP3.timestamp` and `POP3_SSL.stls`. The first three are
  implementation attributes the official documentation does not describe
  and are not on the page; `POP3_SSL.stls` is priced in the `stls()` row.
  `POP3_PORT` and `POP3_SSL_PORT` appear in the constructor rows and are
  asserted by the default ports.
"""

from __future__ import annotations

import hashlib
import inspect
import pathlib
import poplib
import re
import socket
import ssl
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import deque
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "poplib.md"
EXPECTED_BLOCKS = 7
USERS = {"user@example.com": "app-password"}
TIMESTAMP = b"<1896.697170952@pop.example.com>"
MAILBOX = [
    (b"uid-1", b"From: ann@example.com\r\nSubject: Hello\r\n\r\nFirst message.\r\n"),
    (
        b"uid-2",
        b"From: bob@example.com\r\nSubject: Report\r\n\r\n"
        b".hidden dot line\r\nThe numbers are in.\r\n",
    ),
    (b"uid-3", b"From: cara@example.com\r\nSubject: Lunch\r\n\r\nNoon?\r\n"),
]


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


def message_of(lines: int, width: int = 60) -> bytes:
    """A message with a two-line header and `lines` body lines of `width` bytes."""
    body = (b"x" * width + b"\r\n") * lines
    return b"From: a@example.com\r\nSubject: Big\r\n\r\n" + body


def mailbox_of(count: int) -> list[tuple[bytes, bytes]]:
    return [(f"uid-{index}".encode(), b"Subject: s\r\n\r\nx\r\n") for index in range(count)]


# --- The fake server ------------------------------------------------------------


class FakeServer:
    """A POP3 server that answers in process, one reply per command line.

    It marks messages on `DELE` and removes them on `QUIT`, leaves marked
    messages out of `STAT`, `LIST` and `UIDL`, advertises `STLS` in `CAPA`
    before TLS, and answers `-ERR` to a transaction command before `PASS`.
    Setting `prepared` to a deque of reply lines makes the next command's
    reply come from it, built before the call, so only the client allocates.
    Setting `mute` stops it answering, as a closed connection would, and
    setting `gone` makes its socket raise `OSError`, as a reset one would.
    """

    def __init__(
        self,
        *,
        mailbox: list[tuple[bytes, bytes]] | None = None,
        greeting: bytes = b"+OK POP3 ready " + TIMESTAMP,
        capa: bool = True,
    ) -> None:
        self.mailbox = list(MAILBOX if mailbox is None else mailbox)
        self.capa = capa
        self.deleted: set[int] = set()
        self.commands: list[bytes] = []
        self.replies = 0
        self.lines_read = 0
        self.overlapped = 0
        self.tls = False
        self.closed = False
        self.gone = False
        self.mute = False
        self.prepared: deque[bytes] | None = None
        self.out = bytearray(greeting + b"\r\n")
        self._pending = bytearray()
        self._user = ""
        self._authenticated = False

    def verbs(self) -> list[str]:
        return [line.split(b" ", 1)[0].decode().upper() for line in self.commands]

    def ok(self, text: str = "") -> None:
        self.replies += 1
        self.out += f"+OK {text}".rstrip().encode() + b"\r\n"

    def err(self, text: str) -> None:
        self.replies += 1
        self.out += f"-ERR {text}".encode() + b"\r\n"

    def multiline(self, text: str, lines: list[bytes]) -> None:
        self.ok(text)
        for line in lines:
            self.out += (b"." + line if line.startswith(b".") else line) + b"\r\n"
        self.out += b".\r\n"

    def receive(self, data: bytes) -> None:
        if self.out:
            self.overlapped += 1
        self._pending += data
        while b"\r\n" in self._pending:
            line, _, rest = bytes(self._pending).partition(b"\r\n")
            self._pending = bytearray(rest)
            self.commands.append(line)
            self._command(line.decode("utf-8"))

    def _live(self) -> list[int]:
        return [i for i in range(1, len(self.mailbox) + 1) if i not in self.deleted]

    def _message(self, arg: str) -> int | None:
        if arg.isdigit() and int(arg) in self._live():
            return int(arg)
        self.err("no such message")
        return None

    def _command(self, line: str) -> None:
        if self.mute:
            return
        if self.prepared is not None:
            self.replies += 1  # the reply is already queued in `prepared`
            return
        verb, _, args = line.partition(" ")
        verb = verb.upper()
        if verb in {"STAT", "LIST", "UIDL", "RETR", "TOP", "DELE", "RSET"}:
            if not self._authenticated:
                self.err("not authenticated")
                return
        handler = getattr(self, f"_do_{verb.lower()}", None)
        if handler is None:
            self.err("unknown command")
        else:
            handler(args)

    def _do_user(self, args: str) -> None:
        self._user = args
        self.ok("send PASS")

    def _do_pass(self, args: str) -> None:
        if USERS.get(self._user) == args:
            self._authenticated = True
            self.ok(f"maildrop has {len(self._live())} messages")
        else:
            self.err("invalid password")

    def _do_apop(self, args: str) -> None:
        user, _, digest = args.partition(" ")
        expected = hashlib.md5(TIMESTAMP + USERS.get(user, "").encode()).hexdigest()
        if user in USERS and digest == expected:
            self._authenticated = True
            self.ok("maildrop ready")
        else:
            self.err("permission denied")

    def _do_rpop(self, args: str) -> None:
        self.ok()

    def _do_stat(self, args: str) -> None:
        live = self._live()
        self.ok(f"{len(live)} {sum(len(self.mailbox[i - 1][1]) for i in live)}")

    def _listing(self, args: str, field: Callable[[int], bytes]) -> None:
        if args:
            number = self._message(args)
            if number is not None:
                self.ok(f"{number} {field(number).decode()}")
            return
        self.multiline("listing", [str(i).encode() + b" " + field(i) for i in self._live()])

    def _do_list(self, args: str) -> None:
        self._listing(args, lambda i: str(len(self.mailbox[i - 1][1])).encode())

    def _do_uidl(self, args: str) -> None:
        self._listing(args, lambda i: self.mailbox[i - 1][0])

    def _lines(self, number: int) -> list[bytes]:
        return self.mailbox[number - 1][1].split(b"\r\n")[:-1]

    def _do_retr(self, args: str) -> None:
        number = self._message(args)
        if number is not None:
            self.multiline(f"{len(self.mailbox[number - 1][1])} octets", self._lines(number))

    def _do_top(self, args: str) -> None:
        which, _, howmuch = args.partition(" ")
        number = self._message(which)
        if number is not None:
            lines = self._lines(number)
            blank = lines.index(b"")
            self.multiline("top of message", lines[: blank + 1 + int(howmuch)])

    def _do_dele(self, args: str) -> None:
        number = self._message(args)
        if number is not None:
            self.deleted.add(number)
            self.ok(f"message {number} deleted")

    def _do_rset(self, args: str) -> None:
        self.deleted.clear()
        self.ok()

    def _do_noop(self, args: str) -> None:
        self.ok()

    def _do_utf8(self, args: str) -> None:
        self.ok("UTF8 enabled")

    def _do_capa(self, args: str) -> None:
        if not self.capa:
            self.err("unknown command")
            return
        names = [b"TOP", b"UIDL", b"USER", b"IMPLEMENTATION Fake POP3"]
        self.multiline("capability list", names if self.tls else [*names, b"STLS"])

    def _do_stls(self, args: str) -> None:
        self.ok("begin TLS negotiation")

    def _do_quit(self, args: str) -> None:
        self.mailbox = [m for i, m in enumerate(self.mailbox, 1) if i not in self.deleted]
        self.deleted.clear()
        self.closed = True
        self.ok("bye")


class FakeReader:
    """The `makefile('rb')` side: hands out what the server has written."""

    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def readline(self, limit: int = -1) -> bytes:
        if self.server.prepared:
            self.server.lines_read += 1
            return self.server.prepared.popleft()
        out = self.server.out
        end = out.find(b"\n")
        end = len(out) if end < 0 else end + 1
        if limit >= 0:
            end = min(end, limit)
        line = bytes(out[:end])
        del out[:end]
        self.server.lines_read += 1
        return line

    def close(self) -> None:
        pass


class FakeSocket:
    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def sendall(self, data: bytes) -> None:
        if self.server.gone:
            raise ConnectionResetError("connection reset by the fake")
        self.server.receive(data)

    def makefile(self, mode: str = "rb") -> FakeReader:
        return FakeReader(self.server)

    def shutdown(self, how: int) -> None:
        pass

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
        self.greeting_unread_at_wrap.append(sock.server.out.startswith(b"+OK POP3 ready"))
        sock.server.tls = True
        return sock


def install_fake_network() -> Network:
    """Route `poplib` to fresh `FakeServer`s for the rest of the process."""
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


def connect(network: Network, **options: Any) -> poplib.POP3:
    network.options = options
    return poplib.POP3("pop.example.com")


def login(network: Network, **options: Any) -> poplib.POP3:
    pop = connect(network, **options)
    pop.user("user@example.com")
    pop.pass_("app-password")
    return pop


# --- Connections ----------------------------------------------------------------


class TestConnecting:
    """`poplib.POP3(host, ...)` | O(1) | O(1): the greeting and nothing else;
    `getwelcome()` returns it without an exchange; `quit()` is one exchange
    and closes; the class is not a context manager."""

    def test_the_constructor_reads_the_greeting_and_sends_nothing(self, network: Network) -> None:
        pop = connect(network)

        assert network.addresses == [("pop.example.com", 110)]
        assert network.server.commands == []
        assert network.server.out == b"", "the greeting was not read"
        assert pop.getwelcome() == b"+OK POP3 ready " + TIMESTAMP
        assert pop.getwelcome() is pop.getwelcome()

    def test_a_zero_timeout_raises_before_connecting(self, network: Network) -> None:
        with pytest.raises(ValueError, match="Non-blocking"):
            poplib.POP3("pop.example.com", timeout=0)

        assert network.addresses == []

    def test_it_is_not_a_context_manager(self) -> None:
        assert not hasattr(poplib.POP3, "__enter__")
        assert not hasattr(poplib.POP3, "__exit__")

    def test_quit_sends_quit_and_closes(self, network: Network) -> None:
        pop = login(network)

        response = pop.quit()

        assert response.startswith(b"+OK")
        assert network.server.verbs()[-1] == "QUIT"
        assert pop.sock is None and pop.file is None

    def test_set_debuglevel_prints_commands_then_lines(
        self, network: Network, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pop = login(network, mailbox=[(b"u", message_of(50))])
        capsys.readouterr()

        pop.set_debuglevel(1)
        pop.retr(1)
        first = capsys.readouterr().out

        pop.set_debuglevel(2)
        pop.retr(1)
        second = capsys.readouterr().out

        assert first.count("*cmd*") == 1
        assert "*get*" not in first
        assert second.count("*get*") >= 50 + 3 + 2, "level 2 prints every line read"


class TestOneExchangePerCommand:
    """Every command row is one exchange except `stls()`, which is two; the
    exchange count rests on the client never writing ahead of a reply."""

    CALLS: list[tuple[str, Callable[[poplib.POP3], Any]]] = [
        ("NOOP", lambda p: p.noop()),
        ("STAT", lambda p: p.stat()),
        ("LIST", lambda p: p.list()),
        ("LIST", lambda p: p.list(1)),
        ("UIDL", lambda p: p.uidl()),
        ("UIDL", lambda p: p.uidl(1)),
        ("RETR", lambda p: p.retr(1)),
        ("TOP", lambda p: p.top(1, 0)),
        ("DELE", lambda p: p.dele(1)),
        ("RSET", lambda p: p.rset()),
        ("CAPA", lambda p: p.capa()),
        ("UTF8", lambda p: p.utf8()),
        ("RPOP", lambda p: p.rpop("user")),
        ("QUIT", lambda p: p.quit()),
    ]

    @pytest.mark.parametrize(
        ("verb", "call"), CALLS, ids=[f"{v}{i}" for i, (v, _) in enumerate(CALLS)]
    )
    def test_each_command_is_one_exchange(
        self, network: Network, verb: str, call: Callable[[poplib.POP3], Any]
    ) -> None:
        pop = login(network)
        before = network.server.replies

        call(pop)

        assert network.server.replies - before == 1
        assert network.server.verbs()[-1] == verb

    def test_user_and_pass_are_one_exchange_each(self, network: Network) -> None:
        pop = connect(network)

        pop.user("user@example.com")
        assert network.server.replies == 1
        pop.pass_("app-password")
        assert network.server.replies == 2
        assert network.server.verbs() == ["USER", "PASS"]

    def test_the_local_calls_make_no_exchange(self, network: Network) -> None:
        pop = connect(network)

        pop.getwelcome()
        pop.set_debuglevel(0)

        assert network.server.replies == 0

    def test_stls_is_two_exchanges(self, network: Network) -> None:
        pop = connect(network)

        pop.stls()

        assert network.server.verbs() == ["CAPA", "STLS"]
        assert network.server.replies == 2

    def test_nothing_is_written_before_the_last_reply_is_read(self, network: Network) -> None:
        pop = connect(network)
        pop.stls()
        pop.user("user@example.com")
        pop.pass_("app-password")
        for _, call in self.CALLS:
            call(pop)

        assert network.server.overlapped == 0


# --- Reply sizes ----------------------------------------------------------------


class TestSingleLineRepliesAreBounded:
    """Single-line replies are O(1): one line, and no line may exceed 2,048
    bytes. `stat()` and `list(which)` read one line whatever the mailbox holds."""

    @pytest.mark.parametrize("count", [10, 10_000])
    def test_stat_and_list_of_one_read_one_line(self, network: Network, count: int) -> None:
        pop = login(network, mailbox=mailbox_of(count))

        before = network.server.lines_read
        assert pop.stat() == (count, count * 17)
        assert network.server.lines_read - before == 1

        before = network.server.lines_read
        response = pop.list(count)
        assert isinstance(response, bytes) and response.startswith(f"+OK {count} ".encode())
        assert network.server.lines_read - before == 1

    def test_a_line_of_2048_bytes_is_read(self, network: Network) -> None:
        greeting = b"+OK " + b"x" * (2048 - 6)

        pop = connect(network, greeting=greeting)

        assert pop.getwelcome() == greeting

    def test_a_line_of_2049_bytes_raises(self, network: Network) -> None:
        with pytest.raises(poplib.error_proto, match="line too long"):
            connect(network, greeting=b"+OK " + b"x" * (2049 - 6))

    def test_a_message_line_over_the_limit_raises_mid_retrieval(self, network: Network) -> None:
        message = b"Subject: wide\r\n\r\n" + b"x" * 2047 + b"\r\n"
        pop = login(network, mailbox=[(b"u", message)])

        with pytest.raises(poplib.error_proto, match="line too long"):
            pop.retr(1)


class TestMultiLineRepliesAreLinear:
    """`list()`, `uidl()` and `retr()` | O(n) | O(n): one line read and kept
    per line of the reply, so the whole reply is in memory on return."""

    @pytest.mark.parametrize("count", [10, 1_000])
    @pytest.mark.parametrize("method", ["list", "uidl"])
    def test_listings_read_one_line_per_message(
        self, network: Network, count: int, method: str
    ) -> None:
        pop = login(network, mailbox=mailbox_of(count))
        before = network.server.lines_read

        _, listings, _ = getattr(pop, method)()

        assert len(listings) == count
        assert network.server.lines_read - before == count + 2

    @pytest.mark.parametrize("lines", [1_000, 100_000])
    def test_retr_returns_every_line(self, network: Network, lines: int) -> None:
        pop = login(network, mailbox=[(b"u", message_of(lines))])
        before = network.server.lines_read

        _, got, _ = pop.retr(1)

        assert len(got) == lines + 3
        assert network.server.lines_read - before == lines + 3 + 2

    @staticmethod
    def reply_lines(message: bytes) -> deque[bytes]:
        """The RETR reply for `message`, one line per item.

        Lines are not dot-stuffed and bypass `readline()`'s limit, so the
        message must hold short lines with no leading dot.
        """
        lines = [line + b"\r\n" for line in message.split(b"\r\n")[:-1]]
        return deque([b"+OK\r\n", *lines, b".\r\n"])

    def test_retr_holds_the_whole_message(self, network: Network) -> None:
        peaks = []
        for lines in (1_000, 100_000):
            message = message_of(lines)
            pop = login(network)
            network.server.prepared = self.reply_lines(message)
            got: list[Any] = []
            peaks.append(peak_bytes(lambda p=pop, g=got: g.append(p.retr(1))))  # type: ignore[misc]
            assert not network.server.prepared, "the client did not read the whole reply"
            assert len(got[0][1]) == lines + 3
            network.server.prepared = None

        assert peaks[1] > peaks[0] * 20, f"100x the message: peaks {peaks}"
        assert peaks[1] > len(message_of(100_000)), f"peak {peaks[1]} under the message size"

    @pytest.mark.timing
    def test_retr_time_grows_linearly(self, network: Network) -> None:
        durations = []
        for lines in (1_000, 100_000):
            pop = login(network, mailbox=[(b"u", message_of(lines))])
            pop.retr(1)
            durations.append(best_ns(partial(pop.retr, 1)))

        ratio = durations[1] / durations[0]
        assert 20 < ratio < 1_000, f"100x the message cost x{ratio:.1f}: {durations} ns"


class TestRetrievedLines:
    """Lines come back without their endings and with a doubled leading dot
    undone; `octets` counts them with their endings; `top(n, 0)` returns the
    headers in the same shape."""

    def test_a_doubled_leading_dot_is_undone(self, network: Network) -> None:
        pop = login(network)
        assert b"..hidden dot line\r\n" not in MAILBOX[1][1]

        _, lines, _ = pop.retr(2)

        assert b".hidden dot line" in lines

    def test_octets_count_the_lines_with_their_endings(self, network: Network) -> None:
        pop = login(network)

        for number, (_, stored) in enumerate(MAILBOX, 1):
            _, lines, octets = pop.retr(number)
            assert octets == sum(len(line) + 2 for line in lines) == len(stored)
            assert b"\r\n".join(lines) + b"\r\n" == stored

    def test_top_zero_returns_the_headers(self, network: Network) -> None:
        pop = login(network)

        _, lines, octets = pop.top(1, 0)

        assert lines == [b"From: ann@example.com", b"Subject: Hello", b""]
        assert octets == sum(len(line) + 2 for line in lines)


# --- Authentication and TLS -----------------------------------------------------


class TestAuthentication:
    """`user()`, `pass_()`, `apop()`: one exchange each, or none when `apop()`
    has no timestamp to hash."""

    def test_a_wrong_password_raises_with_the_reply(self, network: Network) -> None:
        pop = connect(network)
        pop.user("user@example.com")

        with pytest.raises(poplib.error_proto) as caught:
            pop.pass_("wrong")

        assert caught.value.args[0] == b"-ERR invalid password"

    def test_apop_sends_the_digest_of_timestamp_and_secret(self, network: Network) -> None:
        pop = connect(network)

        pop.apop("user@example.com", "app-password")

        digest = hashlib.md5(TIMESTAMP + b"app-password").hexdigest()
        assert network.server.commands == [f"APOP user@example.com {digest}".encode()]
        assert pop.stat()[0] == 3

    def test_apop_without_a_timestamp_sends_nothing(self, network: Network) -> None:
        pop = connect(network, greeting=b"+OK POP3 ready")

        with pytest.raises(poplib.error_proto, match="APOP not supported"):
            pop.apop("user@example.com", "app-password")

        assert network.server.commands == []


class TestCapaAndStls:
    """`capa()` | O(n) | O(n); `stls()` is `CAPA`, `STLS` and the handshake,
    and refuses without sending `STLS` where it cannot go on."""

    def test_capa_returns_names_and_arguments(self, network: Network) -> None:
        pop = connect(network)

        caps = pop.capa()

        assert caps["IMPLEMENTATION"] == ["Fake", "POP3"]
        assert caps["TOP"] == [] and "STLS" in caps

    def test_capa_refused_raises(self, network: Network) -> None:
        pop = connect(network, capa=False)

        with pytest.raises(poplib.error_proto, match="CAPA not supported"):
            pop.capa()

    def test_stls_wraps_with_the_given_context(self, network: Network) -> None:
        pop = connect(network)
        context = ssl.create_default_context()

        pop.stls(context=context)

        assert network.contexts == [context]
        assert "STLS" not in pop.capa(), "the fake stops advertising STLS over TLS"

    def test_stls_not_advertised_stops_after_capa(self, network: Network) -> None:
        pop = connect(network)
        network.server.tls = True  # the fake then leaves STLS out of CAPA

        with pytest.raises(poplib.error_proto, match="STLS not supported"):
            pop.stls()

        assert network.server.verbs() == ["CAPA"]

    def test_a_second_stls_sends_nothing(self, network: Network) -> None:
        pop = connect(network)
        pop.stls()
        sent = len(network.server.commands)

        with pytest.raises(poplib.error_proto, match="already established"):
            pop.stls()

        assert len(network.server.commands) == sent

    def test_pop3_ssl_stls_sends_nothing(self, network: Network) -> None:
        pop = poplib.POP3_SSL("pop.example.com")

        with pytest.raises(poplib.error_proto, match="already established"):
            pop.stls()

        assert network.server.commands == []

    def test_pop3_ssl_wraps_before_the_greeting(self, network: Network) -> None:
        context = ssl.create_default_context()

        pop = poplib.POP3_SSL("pop.example.com", context=context)

        assert network.addresses == [("pop.example.com", 995)]
        assert network.contexts == [context]
        assert pop.context is context  # type: ignore[attr-defined]
        assert network.greeting_unread_at_wrap == [True]

    def test_the_default_contexts_do_not_verify(self, network: Network) -> None:
        pop = poplib.POP3_SSL("pop.example.com")
        plain = connect(network)
        plain.stls()

        for context in (pop.context, network.contexts[-1]):  # type: ignore[attr-defined]
            assert context.verify_mode == ssl.CERT_NONE
            assert context.check_hostname is False

    def test_the_recommended_context_verifies(self) -> None:
        context = ssl.create_default_context()

        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    def test_keyfile_and_certfile_exist_only_before_3_12(self) -> None:
        parameters = inspect.signature(poplib.POP3_SSL.__init__).parameters
        if sys.version_info >= (3, 12):
            assert "keyfile" not in parameters and "certfile" not in parameters
            assert parameters["timeout"].kind is inspect.Parameter.KEYWORD_ONLY
        else:
            assert "keyfile" in parameters and "certfile" in parameters
            assert parameters["timeout"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert list(inspect.signature(poplib.POP3.stls).parameters) == ["self", "context"]


# --- Mailbox commands and errors ------------------------------------------------


class TestDeletionAndErrors:
    """`dele()` and `rset()` are one exchange each; what the server does with
    the marks is the fake's RFC 1939 policy. `error_proto` is not an
    `OSError`, and socket errors are not wrapped in it."""

    def test_dele_rset_and_quit(self, network: Network) -> None:
        pop = login(network)

        pop.dele(1)
        assert pop.stat()[0] == 2
        pop.rset()
        assert pop.stat()[0] == 3
        pop.dele(1)
        pop.quit()

        assert network.server.verbs()[-4:] == ["RSET", "STAT", "DELE", "QUIT"]
        assert [uid for uid, _ in network.server.mailbox] == [b"uid-2", b"uid-3"]

    def test_an_err_reply_raises_with_its_bytes(self, network: Network) -> None:
        pop = login(network)

        with pytest.raises(poplib.error_proto) as caught:
            pop.retr(99)

        assert caught.value.args[0] == b"-ERR no such message"

    def test_error_proto_is_not_an_os_error(self) -> None:
        assert issubclass(poplib.error_proto, Exception)
        assert not issubclass(poplib.error_proto, OSError)

    def test_a_closed_connection_raises_eof(self, network: Network) -> None:
        pop = connect(network)
        network.server.mute = True

        with pytest.raises(poplib.error_proto, match="-ERR EOF"):
            pop.noop()

    def test_a_socket_error_passes_through(self, network: Network) -> None:
        pop = connect(network)
        network.server.gone = True

        with pytest.raises(ConnectionResetError):
            pop.noop()


# --- The page's examples --------------------------------------------------------


PRELUDE = (
    "import sys\n"
    f"sys.path.insert(0, {str(pathlib.Path(__file__).parent)!r})\n"
    "import test_poplib_complexity\n"
    "test_poplib_complexity.install_fake_network()\n"
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


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(PRELUDE + source, encoding="utf-8")
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
    """Each block runs in its own subprocess and reaches a `FakeServer`
    through the prelude; every block on the page connects."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("poplib.POP3" in source for _, source in blocks)

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
        line, source = next((n, s) for n, s in _blocks() if "count == len(listings) == 3" in s)
        mutated = source.replace("count == len(listings) == 3", "count == len(listings) == 4", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
