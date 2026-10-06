"""Tests for docs/stdlib/smtpd.md.

The page prices the server by the bytes a channel holds and copies: a command
line is joined and dispatched once, a message is collected in pieces and
joined, unstuffed and handed over once, and `data_size_limit` caps what one
message can hold. The module exists on Python 3.10 and 3.11 only, so every
runtime test takes the `smtpd` fixture, which skips from 3.12; availability
itself is asserted on every version. CI runs only the timing tests on 3.10
and 3.11, so the rest are run by hand on one of those versions. Lib/smtpd.py
differs between v3.10.19 and v3.11.14 only in `MailmanProxy`, which 3.11
removes, and in how the import-time DeprecationWarning is raised; the
interpreters run here, 3.10.21 and 3.11.16, carry the same file as those tags.
Channels are built on `socket.socketpair()` with a private map, so a test
chooses exactly what arrives; the end-to-end tests run a real `smtplib`
client, or a real upstream server, in a thread on 127.0.0.1.

Measurement scope:

* `found_terminator()` on a message of 1, 4 and 16 MB, already collected in
  65,536-byte pieces of 78-character CRLF lines, costs between 2x and 8x per
  4x step, where linear gives 4x and quadratic 16x. Its traced peak exceeds
  the message size. A command line is checked by its replies only.
* The limit: 16 pieces of 65,536 bytes collected in data state through
  `collect_incoming_data()`, with `data_size_limit` of
  100,000, leaves at most 100,000 + 65,536 bytes in `received_lines`, and
  `num_bytes` stops with them; the closing line gets `552`, nothing is
  delivered, `smtp_state` stays `DATA`, and a following `RSET` line is
  collected as data. With a limit of `None` or 0 the same input is all
  kept. A `NOOP` line of 605 characters gets `500 Error: line too long`. A
  `MAIL` that declares a `SIZE` over the limit gets `552` before any data,
  and `smtplib` declares it after `EHLO`.
* Delivery: through a real server and `smtplib`, `process_message()` gets
  `bytes` with LF endings and dot-stuffing undone, and `mail_options` and
  `rcpt_options` as keyword arguments; with `decode_data=True` a `str` and no
  keyword arguments. An override without `**kwargs` raises `TypeError` in the
  channel, whose own error handler closes it. `rcpttos` is the channel's own list, replaced by a
  new one after the message; `received_data` is the object delivered, kept
  after the reply and through a `NOOP`, and cleared by `RSET`. A returned
  string is the reply; `None` is `250 OK`.
* `socket.getfqdn()` is counted: once per channel built, and not by
  `SMTPServer()`, which calls `socket.getaddrinfo()` once. `handle_accepted()`
  registers one `channel_class` instance in the server's map.
* Commands: replies are read for a second greeting (`503`), `EHLO`'s
  extensions with and without a limit, `decode_data` and `SMTPUTF8`, `VRFY`
  (`252`), `EXPN` (`502`), `NOOP`, `HELP`, `DATA` without a recipient
  (`503`), `RSET`, which clears the sender and recipients and keeps the
  greeting, and `QUIT`, after which the channel leaves its map once the
  reply is sent. 1,000 `RCPT` commands are all accepted, and with
  `DEBUGSTREAM` replaced by a sink that records what it is given, the
  1,000th `RCPT` writes more than 13,000 characters, the whole list's
  `repr()`, and over 50x what the 10th writes: each one formats the whole list so far, which
  `print()` does before the default `Devnull` discards it. `push()` encodes
  UTF-8 only after `MAIL ... SMTPUTF8`; before that a non-ASCII reply
  raises `UnicodeEncodeError`.
* `command_size_limits` is one object across channels; `EHLO` with a limit
  and `SMTPUTF8` sets `MAIL`'s entry to 512 + 26 + 10, an unknown command
  word after `EHLO` adds an entry, and building another channel empties it;
  `max_command_size_limit` is then 512. A 518-character `MAIL` line gets
  `500` after `HELO` and `250` after `EHLO`.
* `PureProxy`: with an upstream server in a thread, `process_message()`
  returns after the upstream has the message and the `QUIT` that ends the
  session, which carries an `X-Peer`
  header after the headers; two messages open two upstream connections, and
  three recipients make three `RCPT` commands. A client sending through the
  proxy gets `250 OK` when the upstream port is closed and when the upstream
  rejects the data. `process_message()` called with the keyword arguments a
  channel passes raises `TypeError`; `enable_SMTPUTF8=True` raises
  `ValueError`.
* `DebuggingServer.process_message()` prints each line of `bytes` data as its
  `repr()`, with the `X-Peer` header before the first blank line, and none
  when there is no blank line.
* `MailmanProxy`, on 3.10 only: building one warns, `enable_SMTPUTF8=True`
  raises `ValueError`, and `process_message()` raises `TypeError` given the
  keyword arguments and otherwise `ModuleNotFoundError`, since this
  project's environment does not install the package it imports. On 3.11
  the name is gone.
* The constants: `DATA_SIZE_DEFAULT` is 33554432 and the default for both
  classes, `COMMAND` and `DATA` are 0 and 1, `command_size_limit` is 512, and
  `DEBUGSTREAM` is a `Devnull` until a stream is assigned, which then gets
  the channel's trace.
* The import warns on 3.10 and 3.11 and raises `ModuleNotFoundError` from 3.12.
* Every fenced Python block runs in its own subprocess on 3.10 and 3.11, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* `found_terminator()` is timed for a message only, with one line length; a
  message with many dot-stuffed lines and `decode_data=True` follow the same
  split, slice and join in Lib/smtpd.py and are not timed. The O(k) of a
  command line and of `MAIL`, `RCPT`, `VRFY` and `HELP`, which parse or
  upper-case the argument, is read from source: the line is at most 512
  characters before `EHLO`.
* The O(u) of `max_command_size_limit` is `max()` over the dict's values; the
  growth of the dict is observed, the cost is not timed.
* `PureProxy.process_message()`'s O(n + p) is its split and join of the
  message plus `smtplib.SMTP.sendmail()`; the network round trips and the
  upstream server's work are outside the bound. `DebuggingServer`'s O(n) is
  read from source.
* `MailmanProxy.process_message()` imports a package Python does not ship;
  the O(n + p²) with it installed is read from Lib/smtpd.py at v3.10.19,
  where each list recipient is removed from `rcpttos` with `list.remove()`,
  and excludes the work of the package's own functions.
* The resolver lookups `getaddrinfo()` and `getfqdn()` make, and the kernel's
  cost for each socket call, are outside every bound. The examples rely on a
  small send over a Linux `AF_UNIX` socket pair being read back in one
  `recv()`; they have been run on Linux only.
* The deprecation in 3.6 and the removal in 3.12 come from the 3.11
  documentation and PEP 594; that the import warning starts at 3.10 is read
  from Lib/smtpd.py at v3.9.0 and v3.10.0, since 3.9 is not supported, and
  `MailmanProxy`'s removal in 3.11 from v3.11.0.
* The page-scoped audit, run on 3.10 and 3.11, reports no missing names. Its
  classification list holds the channel methods and limits the page prices,
  and these, which the page leaves out: the command-line entry point
  (`usage()`, `parseargs()`, `Options` and its attributes), the `Devnull`
  stream behind `DEBUGSTREAM`, and `get_addr_spec` and `get_angle_addr`,
  imported from `email._header_value_parser`. The `__server`-style
  properties that warn and forward to the public attributes are private
  names and are not on the page either.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import inspect
import io
import pathlib
import re
import smtplib
import socket
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "smtpd.md"
EXPECTED_BLOCKS = 3
PIECE = 65536


def best_ns_with_setup(
    setup: Callable[[], Any], func: Callable[[Any], Any], repeats: int = 5
) -> float:
    """Fastest of `repeats` runs of func(setup()), timing func alone."""
    best: float | None = None
    for _ in range(repeats):
        subject = setup()
        start = time.perf_counter_ns()
        func(subject)
        elapsed = float(time.perf_counter_ns() - start)
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


def test_the_module_exists_only_before_3_12() -> None:
    assert (importlib.util.find_spec("smtpd") is not None) == (sys.version_info < (3, 12))


def loop(channels: dict[int, Any], timeout: float = 1, count: int = 1) -> None:
    """One `asyncore.loop()` call; asyncore is imported once smtpd has been."""
    sys.modules["asyncore"].loop(timeout=timeout, map=channels, count=count)


def close_all(channels: dict[int, Any]) -> None:
    sys.modules["asyncore"].close_all(channels)


@pytest.fixture
def smtpd() -> Iterator[Any]:
    if sys.version_info >= (3, 12):
        pytest.skip("version: smtpd was removed in Python 3.12")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("smtpd")


class Recorder:
    """A server object for a bare channel: records every delivery."""

    def __init__(self, reply: str | None = None) -> None:
        self.reply = reply
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def process_message(self, *args: Any, **kwargs: Any) -> str | None:
        self.calls.append((args, kwargs))
        return self.reply


class Session:
    """One channel on a socket pair, driven a read at a time."""

    def __init__(self, smtpd: Any, server: Any | None = None, **kwargs: Any) -> None:
        self.map: dict[int, Any] = {}
        self.server = Recorder() if server is None else server
        ours, self.peer = socket.socketpair()
        self.peer.setblocking(False)
        self.channel = smtpd.SMTPChannel(self.server, ours, ("client", 0), map=self.map, **kwargs)
        greeting = self.replies()
        assert greeting[0].startswith("220 "), greeting

    def replies(self) -> list[str]:
        received = b""
        while True:
            try:
                chunk = self.peer.recv(PIECE)
            except BlockingIOError:
                break
            if not chunk:
                break
            received += chunk
        return received.decode("utf-8").splitlines()

    def send(self, data: bytes) -> list[str]:
        self.peer.sendall(data)
        loop(self.map)
        return self.replies()

    def start_data(self, greeting: bytes = b"HELO me") -> None:
        replies = self.send(greeting + b"\r\nMAIL FROM:<a@x.org>\r\nRCPT TO:<b@x.org>\r\nDATA\r\n")
        assert replies[-1].startswith("354 "), replies

    def close(self) -> None:
        close_all(self.map)
        self.peer.close()


@pytest.fixture
def session(smtpd: Any) -> Iterator[Callable[..., Session]]:
    opened: list[Session] = []

    def make(server: Any | None = None, **kwargs: Any) -> Session:
        built = Session(smtpd, server, **kwargs)
        opened.append(built)
        return built

    yield make
    for each in opened:
        each.close()


@contextlib.contextmanager
def serving(channels: dict[int, Any]) -> Iterator[None]:
    """Run an asyncore loop over `channels` in a thread until the block ends."""
    done = threading.Event()

    def run() -> None:
        while not done.is_set():
            loop(channels, timeout=0.02)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        close_all(channels)


def send_through(channels: dict[int, Any], port: int, sender: Callable[[smtplib.SMTP], Any]) -> Any:
    """Run `sender` with a client connected to `port` while this thread serves."""
    outcome: dict[str, Any] = {}

    def client() -> None:
        try:
            with smtplib.SMTP("127.0.0.1", port, "client.test", timeout=30) as connection:
                outcome["value"] = sender(connection)
        except Exception as error:  # re-raised in the test thread
            outcome["error"] = error

    thread = threading.Thread(target=client)
    thread.start()
    while thread.is_alive():
        loop(channels, timeout=0.02)
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def collector(smtpd: Any) -> type:
    class Collector(smtpd.SMTPServer):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.messages: list[tuple[Any, ...]] = []

        def process_message(self, *args: Any, **kwargs: Any) -> None:
            self.messages.append((*args, kwargs))

    return Collector


class TestAvailability:
    """`import smtpd` works on 3.10 and 3.11, warning on both, and fails from
    3.12."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the module exists before 3.12")
    def test_importing_it_from_3_12_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("smtpd")

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="smtpd was removed in 3.12")
    def test_importing_it_warns(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import smtpd"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert result.returncode != 0
        assert "DeprecationWarning" in result.stderr


class TestMessageCostIsLinear:
    """`found_terminator()` is O(n) per message: it joins the pieces, splits
    the lines, undoes dot-stuffing and joins them again. A copy per line
    against the rest of the message would be quadratic."""

    @staticmethod
    def pieces(size: int) -> list[bytes]:
        line = b"x" * 76 + b"\r\n"
        data = line * (size // len(line))
        return [data[i : i + PIECE] for i in range(0, len(data), PIECE)]

    @staticmethod
    def ready(session: Session, pieces: list[bytes]) -> Any:
        channel = session.channel
        channel.smtp_state = channel.DATA
        channel.mailfrom = "a@x.org"
        channel.rcpttos = ["b@x.org"]
        channel.mail_options = channel.rcpt_options = []
        channel.received_lines = list(pieces)
        channel.num_bytes = 0
        return channel

    @pytest.mark.timing
    def test_four_times_the_message_costs_about_four_times(
        self, session: Callable[..., Session]
    ) -> None:
        bare = session(data_size_limit=None)
        bare.channel.push = lambda msg: None
        times = []
        for size in (1 << 20, 4 << 20, 16 << 20):
            pieces = self.pieces(size)
            times.append(
                best_ns_with_setup(
                    lambda p=pieces: self.ready(bare, p), lambda c: c.found_terminator()
                )
            )
        ratios = [times[1] / times[0], times[2] / times[1]]
        assert all(2 < ratio < 8 for ratio in ratios), (times, ratios)

    def test_the_peak_exceeds_the_message(self, session: Callable[..., Session]) -> None:
        bare = session(data_size_limit=None)
        bare.channel.push = lambda msg: None
        size = 4 << 20
        channel = self.ready(bare, self.pieces(size))
        assert peak_bytes(channel.found_terminator) > size


class TestTheSizeLimit:
    """Past `data_size_limit` a piece is dropped, so a message holds O(s); the closing line gets `552` and the channel stays in data
    state. A command line has its own limit."""

    def test_pieces_past_the_limit_are_dropped(self, session: Callable[..., Session]) -> None:
        limited = session(data_size_limit=100_000)
        limited.start_data()
        channel = limited.channel
        for _ in range(16):
            channel.collect_incoming_data(b"x" * PIECE)

        held = sum(len(piece) for piece in channel.received_lines)
        assert 100_000 < held <= 100_000 + PIECE
        assert channel.num_bytes == held

    @pytest.mark.parametrize("limit", [None, 0])
    def test_without_a_limit_every_piece_is_kept(
        self, session: Callable[..., Session], limit: int | None
    ) -> None:
        unlimited = session(data_size_limit=limit)
        unlimited.start_data()
        count = 16
        for _ in range(count):
            unlimited.channel.collect_incoming_data(b"x" * PIECE)
        assert sum(len(piece) for piece in unlimited.channel.received_lines) == count * PIECE

    def test_an_oversized_message_is_refused_and_the_channel_stays_in_data(
        self, session: Callable[..., Session]
    ) -> None:
        limited = session(data_size_limit=1_000)
        limited.start_data()
        replies = limited.send(b"x" * 5_000 + b"\r\n.\r\n")
        channel = limited.channel

        assert replies == ["552 Error: Too much mail data"]
        assert limited.server.calls == []
        assert channel.smtp_state == channel.DATA
        assert limited.send(b"RSET\r\n") == []
        assert channel.received_lines == [b"RSET"]

    def test_a_declared_size_over_the_limit_is_refused_at_mail(
        self, session: Callable[..., Session]
    ) -> None:
        limited = session(data_size_limit=1_000)
        assert limited.send(b"EHLO me\r\n")[-1] == "250 HELP"
        replies = limited.send(b"MAIL FROM:<a@x.org> SIZE=5000\r\n")
        assert replies == ["552 Error: message size exceeds fixed maximum message size"]
        assert limited.channel.mailfrom is None

    def test_smtplib_declares_the_size(self, smtpd: Any) -> None:
        channels: dict[int, Any] = {}
        server = collector(smtpd)(("127.0.0.1", 0), None, data_size_limit=1_000, map=channels)
        port = server.socket.getsockname()[1]
        try:
            with pytest.raises(smtplib.SMTPSenderRefused) as raised:
                send_through(
                    channels, port, lambda c: c.sendmail("a@x.org", ["b@x.org"], "x" * 5_000)
                )
            assert raised.value.smtp_code == 552
            assert server.messages == []
        finally:
            close_all(channels)

    def test_a_long_command_line_is_refused(self, session: Callable[..., Session]) -> None:
        bare = session()
        assert bare.send(b"NOOP " + b"x" * 600 + b"\r\n") == ["500 Error: line too long"]


class TestDelivery:
    """`process_message()` gets the whole message once, as `bytes` with LF
    endings and the keyword arguments unless `decode_data=True`; the
    channel's `rcpttos` and `received_data` are the objects it receives."""

    def test_bytes_with_keyword_arguments_by_default(self, smtpd: Any) -> None:
        channels: dict[int, Any] = {}
        server = collector(smtpd)(("127.0.0.1", 0), None, map=channels)
        port = server.socket.getsockname()[1]
        message = "Subject: hi\r\n\r\n.dot\r\nbody\r\n"
        try:
            send_through(channels, port, lambda c: c.sendmail("a@x.org", ["b@x.org"], message))
        finally:
            close_all(channels)

        [(peer, mailfrom, rcpttos, data, kwargs)] = server.messages
        assert (peer[0], mailfrom, rcpttos) == ("127.0.0.1", "a@x.org", ["b@x.org"])
        assert data == b"Subject: hi\n\n.dot\nbody"
        assert kwargs == {"mail_options": [f"SIZE={len(message)}"], "rcpt_options": []}

    def test_str_without_keyword_arguments_with_decode_data(self, smtpd: Any) -> None:
        channels: dict[int, Any] = {}
        server = collector(smtpd)(("127.0.0.1", 0), None, map=channels, decode_data=True)
        port = server.socket.getsockname()[1]
        try:
            send_through(channels, port, lambda c: c.sendmail("a@x.org", ["b@x.org"], "hi\r\n"))
        finally:
            close_all(channels)

        [(_, _, _, data, kwargs)] = server.messages
        assert data == "hi"
        assert kwargs == {}

    def test_an_override_that_refuses_the_keywords_closes_the_channel(
        self, smtpd: Any, session: Callable[..., Session]
    ) -> None:
        class Narrow:
            def process_message(self, peer: Any, mailfrom: Any, rcpttos: Any, data: Any) -> None:
                raise AssertionError("reached")

        errors: list[type[BaseException] | None] = []
        narrow = session(Narrow())
        channel = narrow.channel

        handle_error = channel.handle_error

        def record() -> None:
            errors.append(sys.exc_info()[0])
            handle_error()

        channel.handle_error = record
        narrow.start_data()
        narrow.send(b"hi\r\n.\r\n")
        assert errors == [TypeError]
        assert narrow.map == {}

    def test_rcpttos_is_handed_over_and_replaced(self, session: Callable[..., Session]) -> None:
        bare = session()
        bare.start_data()
        before = bare.channel.rcpttos
        assert bare.send(b"hi\r\n.\r\n") == ["250 OK"]
        [(args, _)] = bare.server.calls
        assert args[2] is before
        assert bare.channel.rcpttos == [] and bare.channel.rcpttos is not before

    def test_received_data_is_kept_until_rset(self, session: Callable[..., Session]) -> None:
        bare = session()
        bare.start_data()
        bare.send(b"hi\r\n.\r\n")
        [(args, _)] = bare.server.calls
        assert bare.channel.received_data is args[3]
        assert bare.send(b"NOOP\r\n") == ["250 OK"]
        assert bare.channel.received_data is args[3]
        assert bare.send(b"RSET\r\n") == ["250 OK"]
        assert bare.channel.received_data == ""

    def test_a_returned_string_is_the_reply(self, session: Callable[..., Session]) -> None:
        refusing = session(Recorder(reply="554 no thanks"))
        refusing.start_data()
        assert refusing.send(b"hi\r\n.\r\n") == ["554 no thanks"]


class TestConnections:
    """Each channel costs one `getfqdn()` lookup; the server resolves its own
    address once and builds one `channel_class` per connection."""

    def test_getfqdn_once_per_channel_and_not_for_the_server(
        self, smtpd: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        looked_up: list[tuple[Any, ...]] = []
        resolved: list[tuple[Any, ...]] = []
        real_getaddrinfo = socket.getaddrinfo

        def getfqdn(*args: Any) -> str:
            looked_up.append(args)
            return "mail.test"

        def getaddrinfo(*args: Any, **kwargs: Any) -> Any:
            resolved.append(args)
            return real_getaddrinfo(*args, **kwargs)

        monkeypatch.setattr(socket, "getfqdn", getfqdn)
        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
        channels: dict[int, Any] = {}
        server = collector(smtpd)(("127.0.0.1", 0), None, map=channels)
        assert looked_up == [] and len(resolved) == 1
        port = server.socket.getsockname()[1]
        try:
            for _ in range(3):
                send_through(channels, port, lambda c: c.noop())
        finally:
            close_all(channels)
        assert len(looked_up) == 3

    def test_handle_accepted_builds_one_channel_class_in_the_map(self, smtpd: Any) -> None:
        class Channel(smtpd.SMTPChannel):
            pass

        class Server(collector(smtpd)):
            channel_class = Channel

        channels: dict[int, Any] = {}
        server = Server(("127.0.0.1", 0), None, map=channels)
        ours, theirs = socket.socketpair()
        try:
            server.handle_accepted(ours, ("client", 0))
            built = [each for each in channels.values() if each is not server]
            assert len(built) == 1 and type(built[0]) is Channel
            assert built[0].smtp_server is server and built[0].conn is ours
        finally:
            close_all(channels)
            theirs.close()

    def test_utf8_and_decode_data_together_raise(self, smtpd: Any) -> None:
        with pytest.raises(ValueError, match="cannot"):
            smtpd.SMTPServer(("127.0.0.1", 0), None, map={}, enable_SMTPUTF8=True, decode_data=True)


class TestCommands:
    """The replies to each command are what the page's rows say."""

    def test_a_second_greeting_is_refused(self, session: Callable[..., Session]) -> None:
        bare = session()
        assert bare.send(b"HELO me\r\n")[0].startswith("250 ")
        assert bare.channel.seen_greeting == "me"
        assert bare.send(b"EHLO me\r\n") == ["503 Duplicate HELO/EHLO"]

    @pytest.mark.parametrize(
        ("options", "expected"),
        [
            ({}, ["250-SIZE 33554432", "250-8BITMIME", "250 HELP"]),
            ({"data_size_limit": None}, ["250-8BITMIME", "250 HELP"]),
            ({"decode_data": True}, ["250-SIZE 33554432", "250 HELP"]),
            (
                {"enable_SMTPUTF8": True},
                ["250-SIZE 33554432", "250-8BITMIME", "250-SMTPUTF8", "250 HELP"],
            ),
        ],
    )
    def test_ehlo_extensions(
        self, session: Callable[..., Session], options: dict[str, Any], expected: list[str]
    ) -> None:
        bare = session(**options)
        assert bare.send(b"EHLO me\r\n")[1:] == expected

    @pytest.mark.parametrize(
        ("command", "reply"),
        [
            (
                b"VRFY <b@x.org>",
                "252 Cannot VRFY user, but will accept message and attempt delivery",
            ),
            (b"EXPN list", "502 EXPN not implemented"),
            (b"NOOP", "250 OK"),
            (b"HELP", "250 Supported commands: EHLO HELO MAIL RCPT DATA RSET NOOP QUIT VRFY"),
        ],
    )
    def test_fixed_replies(
        self, session: Callable[..., Session], command: bytes, reply: str
    ) -> None:
        assert session().send(command + b"\r\n") == [reply]

    def test_rset_clears_the_transaction_and_keeps_the_greeting(
        self, session: Callable[..., Session]
    ) -> None:
        bare = session()
        bare.send(b"HELO me\r\nMAIL FROM:<a@x.org>\r\nRCPT TO:<b@x.org>\r\n")
        assert bare.send(b"RSET\r\n") == ["250 OK"]
        channel = bare.channel
        assert (channel.mailfrom, channel.rcpttos, channel.seen_greeting) == (None, [], "me")

    def test_data_needs_a_recipient(self, session: Callable[..., Session]) -> None:
        bare = session()
        bare.send(b"HELO me\r\nMAIL FROM:<a@x.org>\r\n")
        assert bare.send(b"DATA\r\n") == ["503 Error: need RCPT command"]
        assert bare.channel.smtp_state == bare.channel.COMMAND

    def test_quit_closes_once_the_reply_is_sent(self, session: Callable[..., Session]) -> None:
        bare = session()
        assert bare.send(b"QUIT\r\n") == ["221 Bye"]
        loop(bare.map)
        assert bare.map == {}

    def test_recipients_have_no_limit(self, session: Callable[..., Session]) -> None:
        bare = session()
        bare.send(b"HELO me\r\nMAIL FROM:<a@x.org>\r\n")
        for start in range(0, 1_000, 100):
            batch = b"".join(b"RCPT TO:<r%d@x.org>\r\n" % i for i in range(start, start + 100))
            assert bare.send(batch) == ["250 OK"] * 100
        assert len(bare.channel.rcpttos) == 1_000

    def test_each_rcpt_formats_every_recipient_so_far(
        self, smtpd: Any, session: Callable[..., Session], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bare = session()
        bare.send(b"HELO me\r\nMAIL FROM:<a@x.org>\r\n")
        trace: list[str] = []

        class Sink:
            def write(self, text: str) -> None:
                trace.append(text)

        monkeypatch.setattr(smtpd, "DEBUGSTREAM", Sink())
        written: list[int] = []
        for i in range(1, 1_001):
            trace.clear()
            bare.channel.smtp_RCPT(f"TO:<r{i:04d}@x.org>")
            written.append(sum(len(text) for text in trace))
        bare.replies()
        assert len(bare.channel.rcpttos) == 1_000
        assert str(bare.channel.rcpttos) in "".join(trace)
        assert written[-1] > 1_000 * len("'r0000@x.org'")
        assert written[-1] > 50 * written[9]

    def test_push_encodes_utf8_only_for_an_smtputf8_message(
        self, session: Callable[..., Session]
    ) -> None:
        bare = session(enable_SMTPUTF8=True)
        bare.send(b"EHLO me\r\n")
        with pytest.raises(UnicodeEncodeError):
            bare.channel.push("250 café")
        assert bare.send(b"MAIL FROM:<a@x.org> SMTPUTF8\r\n") == ["250 OK"]
        bare.channel.push("250 café")
        assert bare.replies() == ["250 café"]


class TestCommandSizeLimits:
    """`command_size_limits` is one dict for every channel: `EHLO` raises
    `MAIL`'s entry, each new command word after `EHLO` adds one, and every
    new channel empties it."""

    def test_shared_raised_grown_and_emptied(self, session: Callable[..., Session]) -> None:
        first = session(enable_SMTPUTF8=True)
        limits = first.channel.command_size_limits
        first.send(b"EHLO me\r\n")
        assert limits["MAIL"] == 512 + 26 + 10
        first.send(b"FROB1\r\nFROB2\r\n")
        assert {"FROB1", "FROB2"} <= set(limits)
        assert first.channel.max_command_size_limit == 548

        second = session()
        assert second.channel.command_size_limits is limits
        assert len(limits) == 0
        assert first.channel.max_command_size_limit == 512

    def test_ehlo_lets_a_longer_mail_line_through(self, session: Callable[..., Session]) -> None:
        line = b"MAIL FROM:<" + b"a" * 500 + b"@x.org>\r\n"
        plain = session()
        plain.send(b"HELO me\r\n")
        assert plain.send(line) == ["500 Error: line too long"]

        extended = session()
        extended.send(b"EHLO me\r\n")
        assert extended.send(line) == ["250 OK"]


class TestPureProxy:
    """`PureProxy` relays each message with its own `smtplib` session, inside
    `process_message()`, and replies `250 OK` whatever the upstream said."""

    @pytest.fixture(autouse=True)
    def _relay_timeout(self) -> Iterator[None]:
        """The proxy's own `smtplib.SMTP()` takes the default socket timeout."""
        previous = socket.getdefaulttimeout()
        socket.setdefaulttimeout(30)
        yield
        socket.setdefaulttimeout(previous)

    @staticmethod
    def upstream(smtpd: Any, reply: str | None = None) -> tuple[Any, dict[int, Any], list[str]]:
        commands: list[str] = []

        class Counting(smtpd.SMTPChannel):
            def smtp_RCPT(self, arg: str) -> None:
                commands.append("RCPT")
                super().smtp_RCPT(arg)

            def smtp_QUIT(self, arg: str) -> None:
                commands.append("QUIT")
                super().smtp_QUIT(arg)

        class Upstream(collector(smtpd)):
            channel_class = Counting
            accepted = 0

            def handle_accepted(self, conn: Any, addr: Any) -> None:
                type(self).accepted += 1
                super().handle_accepted(conn, addr)

            def process_message(self, *args: Any, **kwargs: Any) -> str | None:
                super().process_message(*args, **kwargs)
                return reply

        channels: dict[int, Any] = {}
        return Upstream(("127.0.0.1", 0), None, map=channels), channels, commands

    def test_the_session_has_finished_when_it_returns(self, smtpd: Any) -> None:
        upstream, channels, commands = self.upstream(smtpd)
        with serving(channels):
            proxy = smtpd.PureProxy(
                ("127.0.0.1", 0), upstream.socket.getsockname(), map={}, decode_data=True
            )
            try:
                for sent in (1, 2):
                    proxy.process_message(
                        ("192.0.2.7", 1),
                        "a@x.org",
                        ["b@x.org", "c@x.org", "d@x.org"],
                        "Subject: hi\n\nbody",
                    )
                    assert len(upstream.messages) == sent
                    assert commands.count("QUIT") == sent
            finally:
                proxy.close()

        assert len(upstream.messages) == 2
        assert upstream.messages[0][3] == b"Subject: hi\nX-Peer: 192.0.2.7\n\nbody"
        assert type(upstream).accepted == 2
        assert commands.count("RCPT") == 6

    @pytest.mark.parametrize("failure", ["closed port", "rejected data"])
    def test_the_client_gets_250_whatever_happens_upstream(self, smtpd: Any, failure: str) -> None:
        upstream_channels: dict[int, Any] = {}
        if failure == "closed port":
            probe = socket.socket()
            probe.bind(("127.0.0.1", 0))
            remote = probe.getsockname()
            probe.close()
        else:
            upstream, upstream_channels, _ = self.upstream(smtpd, reply="554 rejected")
            remote = upstream.socket.getsockname()

        channels: dict[int, Any] = {}
        proxy = smtpd.PureProxy(("127.0.0.1", 0), remote, map=channels, decode_data=True)
        port = proxy.socket.getsockname()[1]
        with serving(upstream_channels):
            try:
                refused = send_through(
                    channels, port, lambda c: c.sendmail("a@x.org", ["b@x.org"], "hi")
                )
            finally:
                close_all(channels)
        assert refused == {}

    def test_keyword_arguments_raise_type_error(self, smtpd: Any) -> None:
        proxy = smtpd.PureProxy(("127.0.0.1", 0), ("127.0.0.1", 9), map={})
        try:
            with pytest.raises(TypeError):
                proxy.process_message(
                    ("192.0.2.7", 1),
                    "a@x.org",
                    ["b@x.org"],
                    b"hi",
                    mail_options=[],
                    rcpt_options=[],
                )
        finally:
            proxy.close()

    def test_smtputf8_raises(self, smtpd: Any) -> None:
        with pytest.raises(ValueError, match="SMTPUTF8"):
            smtpd.PureProxy(("127.0.0.1", 0), ("127.0.0.1", 9), map={}, enable_SMTPUTF8=True)


class TestDebuggingServer:
    def test_it_prints_each_line_with_x_peer_after_the_headers(self, smtpd: Any) -> None:
        server = smtpd.DebuggingServer(("127.0.0.1", 0), None, map={})
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                server.process_message(
                    ("192.0.2.7", 1),
                    "a@x.org",
                    ["b@x.org"],
                    b"Subject: hi\n\nbody",
                    mail_options=[],
                    rcpt_options=[],
                )
        finally:
            server.close()
        lines = out.getvalue().splitlines()
        assert lines[1:-1] == ["b'Subject: hi'", "b'X-Peer: 192.0.2.7'", "b''", "b'body'"]

    def test_without_a_blank_line_there_is_no_x_peer(self, smtpd: Any) -> None:
        server = smtpd.DebuggingServer(("127.0.0.1", 0), None, map={})
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                server.process_message(("192.0.2.7", 1), "a@x.org", ["b@x.org"], "hi\nthere")
        finally:
            server.close()
        assert out.getvalue().splitlines()[1:-1] == ["hi", "there"]


class TestMailmanProxy:
    """`MailmanProxy` exists on 3.10 only, takes no keyword arguments in
    `process_message()`, and imports a package Python does not ship."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="MailmanProxy exists on 3.10")
    def test_it_is_gone_from_3_11(self, smtpd: Any) -> None:
        assert not hasattr(smtpd, "MailmanProxy")

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="MailmanProxy was removed in 3.11")
    def test_it_warns_refuses_utf8_and_needs_its_package(self, smtpd: Any) -> None:
        assert issubclass(smtpd.MailmanProxy, smtpd.PureProxy)
        with pytest.warns(DeprecationWarning, match="MailmanProxy"):
            proxy = smtpd.MailmanProxy(("127.0.0.1", 0), ("127.0.0.1", 9), map={}, decode_data=True)
        peer = ("192.0.2.7", 1)
        try:
            with pytest.raises(TypeError):
                proxy.process_message(peer, "a", ["b"], b"hi", mail_options=[], rcpt_options=[])
            with pytest.raises(ModuleNotFoundError):
                proxy.process_message(peer, "a@x.org", ["b@x.org"], "hi")
        finally:
            proxy.close()
        with pytest.warns(DeprecationWarning), pytest.raises(ValueError, match="SMTPUTF8"):
            smtpd.MailmanProxy(("127.0.0.1", 0), ("127.0.0.1", 9), map={}, enable_SMTPUTF8=True)


class TestConstants:
    def test_the_values(self, smtpd: Any) -> None:
        assert smtpd.DATA_SIZE_DEFAULT == 33554432
        assert smtpd.SMTPChannel.COMMAND == 0 and smtpd.SMTPChannel.DATA == 1
        assert smtpd.SMTPChannel.command_size_limit == 512

    def test_data_size_default_is_both_defaults(self, smtpd: Any) -> None:
        for cls in (smtpd.SMTPServer, smtpd.SMTPChannel):
            default = inspect.signature(cls).parameters["data_size_limit"].default
            assert default == smtpd.DATA_SIZE_DEFAULT

    def test_debugstream_receives_the_trace(
        self, smtpd: Any, session: Callable[..., Session], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert isinstance(smtpd.DEBUGSTREAM, smtpd.Devnull)
        trace = io.StringIO()
        monkeypatch.setattr(smtpd, "DEBUGSTREAM", trace)
        session().send(b"NOOP\r\n")
        assert "NOOP" in trace.getvalue()


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
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory on the
    versions that still have the module, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import smtpd" in source for _, source in blocks)

    def test_every_block_runs(self, smtpd: Any, tmp_path: pathlib.Path) -> None:
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

    def test_the_runner_notices_a_broken_assertion(
        self, smtpd: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "Too much mail data" in s)
        mutated = source.replace('== "552 Error: Too much mail data"', '== "250 OK"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
