"""Tests for docs/stdlib/imaplib.md.

The page prices the client's share of each command: building the command
line, parsing the response, and holding it until the call returns. No test
here talks to a real server. `FakeServer` answers each command line in
process from a small scripted mailbox, behind a `FakeSocket` that offers the
`recv()`, `sendall()` and `makefile('rb')` that `imaplib` reads through on
every supported version, so each claim about parsing, storing and returning
responses runs through the module's own code. Space claims are settled by
traced allocation, which separates holding a response from streaming it by
orders of magnitude; state, ordering and identity claims by observation; the
growth rates that only a stopwatch shows by ratios between sizes.

Measurement scope:

* `fetch()` of 200 messages whose 50,000-byte bodies come back as literals
  peaks above the 10 MB of bodies, with the server's bytes built before
  tracing starts, and above five times the peak for 20 such messages; every
  literal is a `(header, data)` tuple. A timing test fetches 5,000, 20,000
  and 80,000 one-line `FLAGS` responses and asserts each 4x step costs under
  8x, where a linear parse gives 4x and a quadratic one 16x, and over 2x.
* `noop()` with the server pushing one `EXISTS` line per call leaves one
  more entry in `untagged_responses['EXISTS']` each time; pushed `OK` and
  `NO` lines are gone after the next command while `EXISTS` stays;
  `fetch()` returns its `FETCH` lines and leaves a pushed `EXISTS` behind; `response()` returns
  the stored list object itself and then `[None]`; `select()` starts from an
  empty store; `recent()` sends a `NOOP` only when no `RECENT` is stored.
* A `SEARCH` line of 1,000,001 bytes, CRLF included, raises `IMAP4.error`
  and one of 1,000,000 bytes is returned. The message numbers 1 to 160,000 on one line
  raise and 1 to 140,000 do not, which is what "roughly 150,000 messages"
  on the page rests on for numbers counted from 1.
* `append()` of a message with bare `\\n` line endings delivers it to the
  server with `\\r\\n` endings, and the literal handed to `sendall()` is a
  new object, not the caller's message.
* `authenticate()` calls its callback once per server challenge. A bytes
  subclass counts the suffix bytes copied while encoding replies of 10,
  100 and 1,000 48-byte chunks. Across two challenges the count is exactly
  48 * k * (k - 1), exposing quadratic copying without timing the fake
  server. The server receives the original reply on both challenges.
* `Int2AP()` returns only the letters `A` to `P`, and 16x the digits costs
  between 64x and 1,024x; it is timed on numbers of 2,000 and 32,000 hex
  digits built before timing starts.
* Connection rows are observed on the fake: the constructor leaves
  `capabilities` as a tuple of upper-case names and `PROTOCOL_VERSION`
  `'IMAP4REV1'`; leaving a `with` block sends `LOGOUT`; upper-case command
  names alias the methods; `readline()` returns one line; `read()` returns
  what it was asked for, or less at the end of the stream; `socket()` returns
  the connection's socket; `IMAP4_stream` talks to a Python script over its
  pipes; `IMAP4_SSL` is an `IMAP4` which, from 3.12, takes no `keyfile` or
  `certfile` and a keyword-only `ssl_context`.
* Session and mailbox rows are observed on the fake: `enable()` raises
  without `ENABLE` in `capabilities` and sets `utf8_enabled` after
  `UTF8=ACCEPT`; `starttls()` wraps the socket with the given context and
  asks for `CAPABILITY` again; `login_cram_md5()` answers the challenge with
  the user name and an HMAC-MD5 digest; `select(readonly=True)` sends
  `EXAMINE`; `close()` and `unselect()` return to the `AUTH` state;
  `expunge()` returns one number per removed message; `store()` returns the
  changed messages' `FETCH` lines; every other command method sends its
  command and returns `OK`.
* `print_log()` prints at most ten logged lines after twenty commands, and
  `debug = 4` writes the conversation to standard error.
* On 3.14+, `idle()` sends nothing until its block starts; iterating yields
  `('EXISTS', [b'4'])` without storing it in `untagged_responses`; `DONE` is
  sent on exit; two responses that arrive before the continuation and are
  never iterated are in `untagged_responses` after the block; `burst()`
  yields the three responses queued ahead of it and stops. With the clock
  replaced, `duration=5` two seconds into the block sets a 3-second socket
  timeout and six seconds in sets none and yields nothing.
* `select()` raises `IMAP4.readonly` when the server marks the mailbox
  `READ-ONLY`; `abort` subclasses `error` and `readonly` subclasses `abort`;
  `idle` exists exactly from 3.14.
* The module functions are asserted by value, including every
  `Time2Internaldate()` input type (int and float seconds, `struct_time`, a
  plain tuple with its DST flag and with -1, aware `datetime`, quoted
  string) and the `None` and empty-tuple results. On a host without DST the
  tuple's -1 flag never reaches the DST inference branch.
* Every fenced Python block runs in its own subprocess. Blocks that connect
  run against `FakeServer`, installed by a prelude that replaces
  `socket.create_connection()` and `ssl.SSLContext.wrap_socket()`; the
  `idle()` block is skipped below 3.14. A mutated assertion in a block is
  asserted to fail.

Not settled here:

* Every waiting cost: round trips, DNS and connection setup, the TLS
  handshake of `IMAP4_SSL` and `starttls()`, and the process start of
  `IMAP4_stream`. So is the server's own work - searching, sorting,
  threading, copying and expunging - which no client-side measurement sees.
  That `close()` expunges and `unselect()` does not is RFC 3501 and RFC 3691
  server behaviour; the client sends `CLOSE` or `UNSELECT` either way. That
  servers answer `SEARCH` on one line and that `PARTIAL` is obsolete are
  RFC 3501; that clients should restart `IDLE` every 29 minutes is RFC 2177.
  What `abort` and `readonly` ask the caller to do is the module's
  documented contract; only that `select()` raises `readonly` is run.
* The O(c + n) bounds of the commands not timed or traced here follow from
  the one path every command method takes, `_simple_command()`, read from
  Lib/imaplib.py: the command line is built from the arguments and every
  response line is parsed once and stored once. Each argument is appended
  to the line built so far, so a call with thousands of separate arguments
  costs more than O(c); only a handful of arguments is priced.
* Freeing what a call discards - the old store `select()` drops, the status
  responses the next command deletes - is the reverse of work already paid
  for and is not priced. Scanning `capabilities`, as `enable()` and `idle()`
  do, is treated as O(1): servers advertise a few dozen names. On 3.14
  `Idler` drains responses queued before the continuation with
  `list.pop(0)`; that queue is the handful a server sends while `IDLE`
  starts and its length is not varied.
* On 3.14, `readline()` also copies what remains of the last receive, at
  most `io.DEFAULT_BUFFER_SIZE` bytes, on every line; that is a per-line
  constant, not a change of bound, and is not asserted.
* How much a server pushes between commands, the widths of real `FETCH`
  responses, and `IMAP4_SSL` over a real TLS connection are not varied.
  `setannotation()` and the ACL and quota commands are only sent, since
  their response formats come from extensions the fake does not model.
* The page-scoped audit lists `imaplib.IMAP4.Idler.burst` as documented but
  unresolved: the official inventory files `Idler` under `IMAP4`, while the
  class is `imaplib.Idler` at run time. The page documents it as
  `Idler.burst()` under `### Idler`, and `TestIdler` runs it.
"""

from __future__ import annotations

import base64
import collections
import hashlib
import hmac
import imaplib
import inspect
import io
import pathlib
import re
import shlex
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "imaplib.md"
EXPECTED_BLOCKS = 8
HAS_IDLE = sys.version_info >= (3, 14)


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


# --- A scripted IMAP server behind a fake socket ------------------------------------


class Message:
    def __init__(self, uid: int, body: bytes, flags: list[str] | None = None) -> None:
        self.uid = uid
        self.body = body
        self.flags = flags or []

    @property
    def header(self) -> bytes:
        return self.body.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"


def sample_message(index: int) -> bytes:
    return (
        f"From: sender{index}@example.com\r\nSubject: Message {index}\r\n\r\n"
        f"Body of message {index}.\r\n"
    ).encode()


Handler = Callable[["FakeServer", bytes, bytes, bool], None]


class FakeServer:
    """Answers one command line at a time from a small in-memory mailbox.

    The bytes it sends are queued as the objects the handlers produced, so a
    response built before tracing starts is not copied again by the server.
    """

    def __init__(self, messages: int = 3, capabilities: str = "IMAP4rev1 IDLE ENABLE") -> None:
        self.capabilities = capabilities
        self.messages = [
            Message(101 + index, sample_message(index + 1), ["\\Seen"] if index == 0 else [])
            for index in range(messages)
        ]
        self.pushes: list[bytes] = []
        self.idle_pushes: list[bytes] = []
        self.early_idle_pushes: list[bytes] = []
        self.arrivals = 0
        self.timeouts: list[float | None] = []
        self.commands: list[str] = []
        self.received: list[bytes] = []
        self.handlers: dict[bytes, Handler] = {}
        self.timeout: float | None = None
        self._out: collections.deque[bytes] = collections.deque()
        self._offset = 0
        self._inbox = bytearray()
        self._literal: int | None = None
        self._pending: tuple[bytes, bytes, bytes] | None = None
        self._idle_tag = b""
        self._auth: tuple[bytes, list[bytes]] | None = None
        self.write(b"* OK fake IMAP server ready\r\n")

    # --- transport ---------------------------------------------------------------

    def write(self, data: bytes) -> None:
        if data:
            self._out.append(data)

    def take(self, size: int) -> bytes:
        if not self._out:
            if self.timeout is not None:
                raise TimeoutError("nothing to read")
            return b""
        head = self._out[0]
        chunk = head[self._offset : self._offset + size]
        self._offset += len(chunk)
        if self._offset >= len(head):
            self._out.popleft()
            self._offset = 0
        return chunk

    def receive(self, data: bytes) -> None:
        self._inbox += data
        while self._step():
            pass

    def _step(self) -> bool:
        if self._literal is not None:
            if len(self._inbox) < self._literal + 2:
                return False
            literal = bytes(self._inbox[: self._literal])
            del self._inbox[: self._literal + 2]
            self._literal = None
            assert self._pending is not None
            tag, name, args = self._pending
            self._pending = None
            self.received.append(literal)
            self.dispatch(tag, name, args, literal)
            return True
        end = self._inbox.find(b"\r\n")
        if end < 0:
            return False
        line = bytes(self._inbox[:end])
        del self._inbox[: end + 2]
        if self._auth is not None:
            self._continue_auth(line)
            return True
        if line == b"DONE":
            self.commands.append("DONE")
            self.write(self._idle_tag + b" OK IDLE terminated\r\n")
            return True
        tag, _, rest = line.partition(b" ")
        name, _, args = rest.partition(b" ")
        name = name.upper()
        self.commands.append(name.decode())
        literal = re.search(rb" (?:UTF8 \(~)?\{(\d+)\}$", args)
        if literal:
            self._literal = int(literal.group(1))
            self._pending = (tag, name, args[: literal.start()])
            self.write(b"+ Ready for literal\r\n")
            return True
        self.dispatch(tag, name, args, None)
        return True

    # --- commands ----------------------------------------------------------------

    def dispatch(self, tag: bytes, name: bytes, args: bytes, literal: bytes | None) -> None:
        handler = self.handlers.get(name)
        if handler is not None:
            handler(self, tag, args, False)
            return
        method = getattr(self, "do_" + name.decode(), None)
        if method is None:
            self.write(tag + b" OK " + name + b" completed\r\n")
        elif literal is not None:
            method(tag, args, literal)
        else:
            method(tag, args)

    def ok(self, tag: bytes, name: str) -> None:
        self.write(tag + f" OK {name} completed\r\n".encode())

    def do_CAPABILITY(self, tag: bytes, args: bytes) -> None:
        self.write(f"* CAPABILITY {self.capabilities}\r\n".encode())
        self.ok(tag, "CAPABILITY")

    def do_LOGOUT(self, tag: bytes, args: bytes) -> None:
        self.write(b"* BYE logging out\r\n")
        self.ok(tag, "LOGOUT")

    def do_NOOP(self, tag: bytes, args: bytes) -> None:
        for line in self.pushes:
            self.write(line + b"\r\n")
        self.ok(tag, "NOOP")

    def do_ENABLE(self, tag: bytes, args: bytes) -> None:
        self.write(b"* ENABLED " + args + b"\r\n")
        self.ok(tag, "ENABLE")

    def do_SELECT(self, tag: bytes, args: bytes) -> None:
        self.write(
            b"* FLAGS (\\Answered \\Flagged \\Deleted \\Seen \\Draft)\r\n"
            + f"* {len(self.messages)} EXISTS\r\n* 0 RECENT\r\n".encode()
            + b"* OK [UIDVALIDITY 1] UIDs valid\r\n"
        )
        self.write(tag + b" OK [READ-WRITE] SELECT completed\r\n")

    def do_EXAMINE(self, tag: bytes, args: bytes) -> None:
        self.do_SELECT(tag, args)

    def do_IDLE(self, tag: bytes, args: bytes) -> None:
        self._idle_tag = tag
        for line in self.early_idle_pushes:
            self.write(line + b"\r\n")
        self.write(b"+ idling\r\n")
        for line in self.idle_pushes:
            self.write(line + b"\r\n")
        for _ in range(self.arrivals):
            uid = self.messages[-1].uid + 1 if self.messages else 101
            self.messages.append(Message(uid, sample_message(len(self.messages) + 1)))
            self.write(b"* %d EXISTS\r\n" % len(self.messages))

    def do_AUTHENTICATE(self, tag: bytes, args: bytes) -> None:
        self._auth = (tag, [])
        self.write(b"+ " + _b64(b"challenge-1") + b"\r\n")

    def _continue_auth(self, line: bytes) -> None:
        assert self._auth is not None
        tag, replies = self._auth
        replies.append(line)
        if len(replies) < 2:
            self.write(b"+ " + _b64(b"challenge-2") + b"\r\n")
            return
        self.auth_replies = [_unb64(reply) for reply in replies]
        self._auth = None
        self.ok(tag, "AUTHENTICATE")

    def _select_messages(self, message_set: bytes, by_uid: bool) -> list[tuple[int, Message]]:
        chosen: list[tuple[int, Message]] = []
        top = self.messages[-1].uid if (by_uid and self.messages) else len(self.messages)
        wanted: set[int] = set()
        for part in message_set.split(b","):
            low, _, high = part.partition(b":")
            start = top if low == b"*" else int(low)
            stop = start if not high else (top if high == b"*" else int(high))
            wanted.update(range(min(start, stop), max(start, stop) + 1))
        for seq, message in enumerate(self.messages, 1):
            if (message.uid if by_uid else seq) in wanted:
                chosen.append((seq, message))
        return chosen

    def do_SEARCH(self, tag: bytes, args: bytes, by_uid: bool = False) -> None:
        words = args.upper().split()
        found: list[int] = []
        for seq, message in enumerate(self.messages, 1):
            keep = True
            if b"UNSEEN" in words:
                keep = "\\Seen" not in message.flags
            if b"UID" in words:
                window = words[words.index(b"UID") + 1]
                keep = keep and any(
                    other is message for _, other in self._select_messages(window, True)
                )
            if keep:
                found.append(message.uid if by_uid else seq)
        self.write(b"* SEARCH" + b"".join(b" %d" % number for number in found) + b"\r\n")
        self.ok(tag, "SEARCH")

    def do_FETCH(self, tag: bytes, args: bytes, by_uid: bool = False) -> None:
        message_set, _, parts = args.partition(b" ")
        parts = parts.upper()
        for seq, message in self._select_messages(message_set, by_uid):
            items: list[bytes] = []
            if by_uid or b"UID" in parts:
                items.append(b"UID %d" % message.uid)
            if b"FLAGS" in parts:
                items.append(b"FLAGS (" + " ".join(message.flags).encode() + b")")
            if b"RFC822.SIZE" in parts:
                items.append(b"RFC822.SIZE %d" % len(message.body))
            literals: list[tuple[bytes, bytes]] = []
            if b"[HEADER]" in parts:
                literals.append((b"BODY[HEADER]", message.header))
            if re.search(rb"RFC822(?![.\w])", parts) or b"BODY[]" in parts:
                literals.append((b"RFC822", message.body))
            line = b"* %d FETCH (" % seq + b" ".join(items)
            for name, data in literals:
                line += (b" " if line[-1:] != b"(" else b"") + name + b" {%d}\r\n" % len(data)
                self.write(line)
                self.write(data)
                line = b""
            self.write(line + b")\r\n")
        self.ok(tag, "FETCH")

    def do_STORE(self, tag: bytes, args: bytes, by_uid: bool = False) -> None:
        message_set, operation, flags = args.split(b" ", 2)
        names = flags.strip(b"()").decode().split()
        for seq, message in self._select_messages(message_set, by_uid):
            if operation.upper().startswith(b"+"):
                message.flags += [name for name in names if name not in message.flags]
            elif operation.upper().startswith(b"-"):
                message.flags = [name for name in message.flags if name not in names]
            else:
                message.flags = names
            self.write(b"* %d FETCH (FLAGS (" % seq + " ".join(message.flags).encode() + b"))\r\n")
        self.ok(tag, "STORE")

    def do_EXPUNGE(self, tag: bytes, args: bytes) -> None:
        index = 0
        while index < len(self.messages):
            if "\\Deleted" in self.messages[index].flags:
                del self.messages[index]
                self.write(b"* %d EXPUNGE\r\n" % (index + 1))
            else:
                index += 1
        self.ok(tag, "EXPUNGE")

    def do_APPEND(self, tag: bytes, args: bytes, literal: bytes) -> None:
        flags = re.search(rb"\(([^)]*)\)", args)
        uid = (self.messages[-1].uid if self.messages else 100) + 1
        names = flags.group(1).decode().split() if flags else []
        self.messages.append(Message(uid, literal, names))
        self.write(tag + b" OK [APPENDUID 1 %d] APPEND completed\r\n" % uid)

    def do_LIST(self, tag: bytes, args: bytes) -> None:
        self.write(b'* LIST (\\HasNoChildren) "/" INBOX\r\n* LIST (\\HasNoChildren) "/" Sent\r\n')
        self.ok(tag, "LIST")

    def do_UID(self, tag: bytes, args: bytes) -> None:
        command, _, rest = args.partition(b" ")
        method = getattr(self, "do_" + command.upper().decode())
        method(tag, rest, by_uid=True)


def _b64(data: bytes) -> bytes:
    return base64.b64encode(data)


def _unb64(data: bytes) -> bytes:
    return base64.b64decode(data)


class _Raw(io.RawIOBase):
    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        data = self.server.take(len(buffer))
        buffer[: len(data)] = data
        return len(data)


class FakeSocket:
    """The socket methods `imaplib` calls, backed by a `FakeServer`."""

    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.sent: list[bytes] = []

    def recv(self, size: int) -> bytes:
        return self.server.take(size)

    def makefile(self, mode: str) -> io.BufferedReader:
        return io.BufferedReader(_Raw(self.server))

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)
        self.server.receive(bytes(data))

    def settimeout(self, value: float | None) -> None:
        self.server.timeouts.append(value)
        self.server.timeout = value

    def gettimeout(self) -> float | None:
        return self.server.timeout

    def shutdown(self, how: int) -> None:
        pass

    def close(self) -> None:
        pass


class FakeIMAP4(imaplib.IMAP4):
    """An `IMAP4` whose connection is a `FakeServer`."""

    def __init__(self, server: FakeServer | None = None) -> None:
        self.server = server or FakeServer()
        super().__init__("imap.example.com")

    def _create_socket(self, timeout: float | None) -> Any:
        return FakeSocket(self.server)


def install_fake_network() -> None:
    """Route every connection in this process to a fresh `FakeServer`.

    Used as the prelude of the page's connecting examples.
    """
    import socket
    import ssl

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        server = FakeServer(messages=1_200)
        server.arrivals = 1  # one message arrives while the client idles
        return FakeSocket(server)

    def wrap_socket(self: Any, sock: Any, *args: Any, **kwargs: Any) -> Any:
        return sock

    socket.create_connection = create_connection  # type: ignore[assignment]
    ssl.SSLContext.wrap_socket = wrap_socket  # type: ignore[method-assign]


def logged_in(server: FakeServer | None = None) -> FakeIMAP4:
    imap = FakeIMAP4(server)
    imap.login("user", "password")
    imap.select("INBOX")
    return imap


def respond_with(lines: list[bytes]) -> Handler:
    """A handler that sends prebuilt untagged lines, then completes the command."""

    def handler(server: FakeServer, tag: bytes, args: bytes, by_uid: bool) -> None:
        for line in lines:
            server.write(line)
        server.write(tag + b" OK completed\r\n")

    return handler


# --- Responses are held whole --------------------------------------------------------


class TestCommandsHoldTheWholeResponse:
    """`fetch()` | O(c + n) | O(c + n): every message in the set is in memory
    when the call returns. A streaming client would peak near one message;
    this one peaks above the sum of them."""

    BODY = 50_000

    def _mailbox(self, count: int) -> FakeServer:
        server = FakeServer(messages=0)
        server.messages = [
            Message(101 + index, sample_message(index) + b"x" * self.BODY) for index in range(count)
        ]
        return server

    def test_the_peak_exceeds_every_body_together(self) -> None:
        server = self._mailbox(200)
        imap = logged_in(server)

        result: list[Any] = []
        peak = peak_bytes(lambda: result.append(imap.fetch("1:*", "(RFC822)")))

        typ, data = result[0]
        literals = [part for part in data if isinstance(part, tuple)]
        total = sum(len(body) for _, body in literals)
        assert typ == "OK" and len(literals) == 200
        assert total > 200 * self.BODY
        assert peak > total, f"fetch of {total} bytes of bodies peaked at {peak}"

    def test_ten_times_the_messages_ten_times_the_peak(self) -> None:
        small = logged_in(self._mailbox(20))
        large = logged_in(self._mailbox(200))

        peaks = [peak_bytes(partial(imap.fetch, "1:*", "(RFC822)")) for imap in (small, large)]

        assert peaks[1] > peaks[0] * 5, f"20 and 200 messages peaked at {peaks}"

    def test_literals_come_back_as_header_and_data_pairs(self) -> None:
        imap = logged_in()

        typ, data = imap.fetch("1", "(RFC822.SIZE BODY.PEEK[HEADER])")

        assert typ == "OK"
        header_line, header = data[0]  # type: ignore[misc]
        assert isinstance(header_line, bytes) and isinstance(header, bytes)
        assert header_line.startswith(b"1 (RFC822.SIZE ")
        assert header_line.endswith(b"BODY[HEADER] {%d}" % len(header))
        assert header == imap.server.messages[0].header  # type: ignore[attr-defined]
        assert data[1] == b")"

    @pytest.mark.timing
    def test_parsing_is_linear_in_the_response_lines(self) -> None:
        durations = []
        for count in (5_000, 20_000, 80_000):
            server = FakeServer()
            lines = [b"* %d FETCH (FLAGS (\\Seen))\r\n" % index for index in range(1, count + 1)]
            server.handlers[b"FETCH"] = respond_with(lines)
            imap = logged_in(server)

            def fetch(imap: FakeIMAP4 = imap, lines: list[bytes] = lines) -> None:
                imap.server.handlers[b"FETCH"] = respond_with(lines)
                assert len(imap.fetch("1:*", "(FLAGS)")[1]) == len(lines)

            durations.append(best_ns(fetch, repeats=3))

        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]
        assert all(2 < ratio < 8 for ratio in ratios), (
            f"4x the lines each step cost {[f'x{r:.1f}' for r in ratios]} ({durations} ns); "
            "linear gives x4 and quadratic x16"
        )


# --- Untagged responses --------------------------------------------------------------


class TestUntaggedResponsesAccumulate:
    """A method returns the untagged responses it names and stores the rest
    until `response()` takes them or `select()` discards them."""

    def test_each_poll_adds_what_the_server_pushed(self) -> None:
        server = FakeServer()
        server.pushes = [b"* 3 EXISTS"]
        imap = logged_in(server)
        before = len(imap.untagged_responses["EXISTS"])

        for _ in range(5):
            imap.noop()

        assert len(imap.untagged_responses["EXISTS"]) == before + 5

    def test_a_command_returns_only_what_it_names(self) -> None:
        server = FakeServer()
        imap = logged_in(server)
        imap.response("EXISTS")
        pushed = [b"* 7 EXISTS\r\n", b"* 1 FETCH (FLAGS (\\Seen))\r\n"]
        server.handlers[b"FETCH"] = respond_with(pushed)

        typ, data = imap.fetch("1", "(FLAGS)")

        assert data == [b"1 (FLAGS (\\Seen))"]
        assert imap.untagged_responses["EXISTS"] == [b"7"]

    def test_status_responses_are_cleared_by_the_next_command(self) -> None:
        server = FakeServer()
        server.pushes = [b"* OK still here", b"* NO quota low", b"* 5 EXISTS"]
        imap = logged_in(server)
        imap.noop()
        assert {"OK", "NO", "EXISTS"} <= set(imap.untagged_responses)
        server.pushes = []

        imap.noop()

        assert "OK" not in imap.untagged_responses
        assert "NO" not in imap.untagged_responses
        assert imap.untagged_responses["EXISTS"][-1] == b"5"

    def test_response_hands_back_the_stored_list_and_forgets_it(self) -> None:
        imap = logged_in()
        stored = imap.untagged_responses["EXISTS"]

        typ, data = imap.response("EXISTS")

        assert (typ, data) == ("EXISTS", [b"3"])
        assert data is stored, "response() copied the stored list"
        assert "EXISTS" not in imap.untagged_responses
        assert imap.response("EXISTS") == ("EXISTS", [None])

    def test_select_starts_from_an_empty_store(self) -> None:
        server = FakeServer()
        server.pushes = [b"* 9 RECENT", b"* OK [ALERT] hello"]
        imap = logged_in(server)
        imap.noop()
        assert "ALERT" in imap.untagged_responses

        imap.select("INBOX")

        assert "ALERT" not in imap.untagged_responses
        assert imap.untagged_responses["RECENT"] == [b"0"]

    def test_recent_asks_the_server_only_when_nothing_is_stored(self) -> None:
        server = FakeServer()
        imap = logged_in(server)

        assert imap.recent() == ("OK", [b"0"])  # stored by select()
        assert "NOOP" not in server.commands

        server.pushes = [b"* 2 RECENT"]
        assert imap.recent() == ("OK", [b"2"])
        assert server.commands.count("NOOP") == 1


# --- The line limit -----------------------------------------------------------------


class TestTheLineLimit:
    """`readline()`: a line over 1,000,000 bytes raises `IMAP4.error`, and a
    `SEARCH` answer is one line."""

    @staticmethod
    def _search_answer(line: bytes) -> tuple[str, list[Any]]:
        server = FakeServer()
        server.handlers[b"SEARCH"] = respond_with([line + b"\r\n"])
        return logged_in(server).search(None, "ALL")

    def test_a_line_over_the_limit_raises(self) -> None:
        line = b"* SEARCH" + b" 1" * 499_995 + b"1"
        assert len(line) + 2 == 1_000_001

        with pytest.raises(imaplib.IMAP4.error, match="got more than 1000000 bytes"):
            self._search_answer(line)

    def test_a_line_under_it_is_returned(self) -> None:
        line = b"* SEARCH" + b" 1" * 499_995
        assert len(line) + 2 == 1_000_000

        typ, data = self._search_answer(line)

        assert typ == "OK" and len(data[0].split()) == 499_995

    def test_about_150000_numbers_from_one_reach_it(self) -> None:
        def numbers(last: int) -> bytes:
            return b"* SEARCH" + b"".join(b" %d" % number for number in range(1, last + 1))

        assert len(self._search_answer(numbers(140_000))[1][0].split()) == 140_000
        with pytest.raises(imaplib.IMAP4.error):
            self._search_answer(numbers(160_000))


# --- Commands that send more than a line ------------------------------------------


class TestAppend:
    """`append()` | O(c + m + n): every line ending becomes CRLF, a copy of
    the message, sent as one literal."""

    def test_bare_line_feeds_arrive_as_crlf(self) -> None:
        server = FakeServer()
        imap = logged_in(server)

        typ, data = imap.append("INBOX", r"(\Seen)", None, b"Subject: x\n\nline one\nline two\n")

        assert typ == "OK"
        assert server.received[-1] == b"Subject: x\r\n\r\nline one\r\nline two\r\n"
        assert server.messages[-1].flags == ["\\Seen"]

    def test_the_literal_sent_is_a_rewritten_copy(self) -> None:
        imap = logged_in()
        sock: FakeSocket = imap.socket()  # type: ignore[assignment]
        message = b"line\n" * 100_000

        imap.append("INBOX", None, None, message)

        literal = next(data for data in sock.sent if len(data) >= len(message))
        assert literal is not message
        assert literal == b"line\r\n" * 100_000


class TestAuthenticate:
    """`authenticate()` | O(c + n + t²): the callback runs once per challenge,
    and encoding its reply is quadratic in the reply's length."""

    def test_the_callback_runs_once_per_challenge(self) -> None:
        server = FakeServer()
        imap = FakeIMAP4(server)
        seen: list[bytes] = []

        def reply(challenge: bytes) -> bytes:
            seen.append(challenge)
            return b"answer %d" % len(seen)

        typ, _ = imap.authenticate("XTEST", reply)

        assert typ == "OK" and imap.state == "AUTH"
        assert seen == [b"challenge-1", b"challenge-2"]
        assert server.auth_replies == [b"answer 1", b"answer 2"]  # type: ignore[attr-defined]

    def test_cram_md5_answers_with_the_user_and_a_digest(self) -> None:
        try:
            hmac.new(b"key", b"msg", "md5")
        except ValueError:
            pytest.skip("HMAC-MD5 is not available in this build")
        server = FakeServer()
        imap = FakeIMAP4(server)

        imap.login_cram_md5("user", "secret")

        expected = [
            b"user " + hmac.new(b"secret", challenge, hashlib.md5).hexdigest().encode()
            for challenge in (b"challenge-1", b"challenge-2")
        ]
        assert server.auth_replies == expected  # type: ignore[attr-defined]
        assert "AUTHENTICATE" in server.commands

    @pytest.mark.parametrize("chunks", [10, 100, 1_000])
    def test_encoding_the_reply_copies_quadratically(self, chunks: int) -> None:
        """Count shrinking suffix copies at a fixed two server challenges.

        Each 48-byte chunk leaves a suffix shorter by 48 bytes. Their lengths
        sum to a quadratic; this observes input slicing, not elapsed time or
        the additional copies made while concatenating encoded output.
        """
        copied = 0

        class Reply(bytes):
            def __getitem__(self, key: Any) -> Any:
                nonlocal copied
                result = super().__getitem__(key)
                if isinstance(key, slice):
                    if key.start == 48 and key.stop is None:
                        copied += len(result)
                    return Reply(result)
                return result

        token = Reply(b"x" * (48 * chunks))
        server = FakeServer()
        client = FakeIMAP4(server)
        typ, _ = client.authenticate("XTEST", lambda challenge: token)

        assert typ == "OK"
        assert server.auth_replies == [bytes(token), bytes(token)]  # type: ignore[attr-defined]
        assert copied == 48 * chunks * (chunks - 1), f"{chunks=}, {copied=}"


# --- Connections ---------------------------------------------------------------------


class TestConnections:
    """Constructor, context manager, the transport methods and aliases."""

    def test_the_constructor_learns_the_capabilities(self) -> None:
        server = FakeServer(capabilities="IMAP4rev1 idle Enable")

        imap = FakeIMAP4(server)

        assert imap.capabilities == ("IMAP4REV1", "IDLE", "ENABLE")
        assert imap.PROTOCOL_VERSION == "IMAP4REV1"
        assert imap.state == "NONAUTH"
        assert server.commands == ["CAPABILITY"]

    def test_leaving_the_block_logs_out(self) -> None:
        server = FakeServer()

        with FakeIMAP4(server) as imap:
            imap.login("user", "password")

        assert server.commands[-1] == "LOGOUT"
        assert imap.state == "LOGOUT"

    def test_upper_case_names_alias_the_methods(self) -> None:
        imap = FakeIMAP4()

        assert imap.NOOP == imap.noop
        assert imap.NOOP()[0] == "OK"
        with pytest.raises(AttributeError):
            _ = imap.NOTACOMMAND

    def test_read_readline_send_and_socket(self) -> None:
        server = FakeServer()
        imap = FakeIMAP4(server)
        server.write(b"* first line\r\nabcdef")

        assert imap.readline() == b"* first line\r\n"
        assert imap.read(4) == b"abcd"
        assert imap.read(10) == b"ef"  # the stream ended first
        assert isinstance(imap.socket(), FakeSocket)
        imap.send(b"a1 NOOP\r\n")
        assert server.commands[-1] == "NOOP"

    def test_idle_exists_from_3_14(self) -> None:
        assert hasattr(imaplib.IMAP4, "idle") is HAS_IDLE

    def test_imap4_ssl_is_an_imap4(self) -> None:
        assert issubclass(imaplib.IMAP4_SSL, imaplib.IMAP4)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="keyfile was removed in 3.12")
    def test_imap4_ssl_takes_only_a_keyword_context(self) -> None:
        parameters = inspect.signature(imaplib.IMAP4_SSL).parameters
        assert parameters["ssl_context"].kind is inspect.Parameter.KEYWORD_ONLY
        assert "keyfile" not in parameters and "certfile" not in parameters

    def test_imap4_stream_talks_over_a_command_s_pipes(self, tmp_path: pathlib.Path) -> None:
        script = tmp_path / "server.py"
        script.write_text(
            textwrap.dedent(
                """
                import sys
                out = sys.stdout.buffer
                out.write(b"* OK stream ready\\r\\n"); out.flush()
                for line in sys.stdin.buffer:
                    tag, name = line.split()[:2]
                    if name == b"CAPABILITY":
                        out.write(b"* CAPABILITY IMAP4rev1\\r\\n")
                    if name == b"LOGOUT":
                        out.write(b"* BYE\\r\\n" + tag + b" OK done\\r\\n"); out.flush()
                        break
                    out.write(tag + b" OK done\\r\\n"); out.flush()
                """
            ),
            encoding="utf-8",
        )
        command = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"

        imap = imaplib.IMAP4_stream(command)

        assert imap.capabilities == ("IMAP4REV1",)
        assert imap.noop()[0] == "OK"
        assert imap.logout()[0] == "BYE"
        assert imap.process.returncode == 0  # type: ignore[attr-defined]


class TestSessionAndMailboxCommands:
    """The state changes and replies the rows describe, observed on the fake."""

    def test_enable_needs_the_capability(self) -> None:
        imap = FakeIMAP4(FakeServer(capabilities="IMAP4rev1"))
        imap.login("user", "password")

        with pytest.raises(imaplib.IMAP4.error, match="ENABLE"):
            imap.enable("UTF8=ACCEPT")

    def test_enable_utf8_switches_the_connection(self) -> None:
        imap = FakeIMAP4()
        imap.login("user", "password")
        assert imap.utf8_enabled is False

        imap.enable("UTF8=ACCEPT")

        assert imap.utf8_enabled is True

    def test_starttls_wraps_the_socket_and_asks_again(self) -> None:
        server = FakeServer(capabilities="IMAP4rev1 STARTTLS")
        imap = FakeIMAP4(server)
        wrapped: list[Any] = []

        class Context:
            def wrap_socket(self, sock: Any, server_hostname: str) -> Any:
                wrapped.append(server_hostname)
                return sock

        imap.starttls(ssl_context=Context())  # type: ignore[arg-type]

        assert wrapped == ["imap.example.com"]
        assert server.commands == ["CAPABILITY", "STARTTLS", "CAPABILITY"]

    def test_logout_ends_the_session(self) -> None:
        imap = FakeIMAP4()

        typ, data = imap.logout()

        assert typ == "BYE" and imap.state == "LOGOUT"

    def test_readonly_select_sends_examine(self) -> None:
        server = FakeServer()
        imap = FakeIMAP4(server)
        imap.login("user", "password")

        typ, data = imap.select("INBOX", readonly=True)

        assert (typ, data) == ("OK", [b"3"])
        assert server.commands[-1] == "EXAMINE"
        assert imap.state == "SELECTED"

    @pytest.mark.parametrize("method", ["close", "unselect"])
    def test_close_and_unselect_return_to_auth(self, method: str) -> None:
        server = FakeServer()
        imap = logged_in(server)

        getattr(imap, method)()

        assert imap.state == "AUTH"
        assert server.commands[-1] == method.upper()

    def test_store_returns_the_changed_messages(self) -> None:
        imap = logged_in()

        typ, data = imap.store("1:2", "+FLAGS", r"(\Flagged)")

        assert data == [b"1 (FLAGS (\\Seen \\Flagged))", b"2 (FLAGS (\\Flagged))"]

    def test_expunge_returns_one_number_per_removed_message(self) -> None:
        imap = logged_in()
        imap.store("1,3", "+FLAGS", r"(\Deleted)")

        typ, data = imap.expunge()

        assert data == [b"1", b"2"]  # message 3 is number 2 once 1 is gone

    def test_uid_commands_address_messages_by_uid(self) -> None:
        imap = logged_in()

        assert imap.uid("SEARCH", "ALL") == ("OK", [b"101 102 103"])
        typ, data = imap.uid("FETCH", "102", "(FLAGS)")
        assert data == [b"2 (UID 102 FLAGS ())"]

    CALLS: list[tuple[str, tuple[Any, ...], str]] = [
        ("capability", (), "CAPABILITY"),
        ("namespace", (), "NAMESPACE"),
        ("check", (), "CHECK"),
        ("proxyauth", ("other",), "PROXYAUTH"),
        ("list", (), "LIST"),
        ("lsub", (), "LSUB"),
        ("status", ("INBOX", "(MESSAGES)"), "STATUS"),
        ("create", ("Archive",), "CREATE"),
        ("delete", ("Archive",), "DELETE"),
        ("rename", ("Archive", "Old"), "RENAME"),
        ("subscribe", ("Archive",), "SUBSCRIBE"),
        ("unsubscribe", ("Archive",), "UNSUBSCRIBE"),
        ("sort", ("(DATE)", "UTF-8", "ALL"), "SORT"),
        ("thread", ("REFERENCES", "UTF-8", "ALL"), "THREAD"),
        ("partial", ("1", "RFC822", "0", "10"), "PARTIAL"),
        ("copy", ("1", "Archive"), "COPY"),
        ("xatom", ("XNOTHING",), "XNOTHING"),
        ("getacl", ("INBOX",), "GETACL"),
        ("setacl", ("INBOX", "other", "lr"), "SETACL"),
        ("deleteacl", ("INBOX", "other"), "DELETEACL"),
        ("myrights", ("INBOX",), "MYRIGHTS"),
        ("getquota", ("",), "GETQUOTA"),
        ("getquotaroot", ("INBOX",), "GETQUOTAROOT"),
        ("setquota", ("", "(STORAGE 512)"), "SETQUOTA"),
        ("getannotation", ("INBOX", '"/comment"', '"value.priv"'), "GETANNOTATION"),
        ("setannotation", ("INBOX", '"/comment"', '("value.priv" "hi")'), "SETANNOTATION"),
    ]

    @pytest.mark.parametrize(("method", "args", "command"), CALLS, ids=[c[0] for c in CALLS])
    def test_each_command_sends_its_name(
        self, method: str, args: tuple[Any, ...], command: str
    ) -> None:
        server = FakeServer()
        imap = logged_in(server)
        if method == "proxyauth":  # allowed only before a mailbox is selected
            imap.close()

        typ, _ = getattr(imap, method)(*args)

        assert typ == "OK"
        assert server.commands[-1] == command


class TestDebugging:
    """`print_log()` prints at most ten logged lines; `debug` writes the
    conversation to standard error."""

    def test_print_log_keeps_the_last_ten(self, capsys: pytest.CaptureFixture[str]) -> None:
        imap = logged_in()
        for _ in range(20):
            imap.noop()
        capsys.readouterr()

        imap.print_log()

        lines = capsys.readouterr().err.splitlines()
        assert "last 10 IMAP4 interactions" in lines[0]
        assert len(lines) == 11

    def test_debug_writes_the_conversation(self, capsys: pytest.CaptureFixture[str]) -> None:
        imap = logged_in()
        capsys.readouterr()
        imap.debug = 4

        imap.noop()

        assert "NOOP" in capsys.readouterr().err


class TestExceptions:
    def test_the_hierarchy(self) -> None:
        assert issubclass(imaplib.IMAP4.abort, imaplib.IMAP4.error)
        assert issubclass(imaplib.IMAP4.readonly, imaplib.IMAP4.abort)

    def test_a_read_only_mailbox_raises_readonly(self) -> None:
        server = FakeServer()
        server.handlers[b"SELECT"] = respond_with([b"* 3 EXISTS\r\n", b"* OK [READ-ONLY] ro\r\n"])
        imap = FakeIMAP4(server)
        imap.login("user", "password")

        with pytest.raises(imaplib.IMAP4.readonly):
            imap.select("INBOX")

    def test_a_command_in_the_wrong_state_is_an_error(self) -> None:
        imap = FakeIMAP4()

        with pytest.raises(imaplib.IMAP4.error, match="illegal in state"):
            imap.fetch("1", "(FLAGS)")


# --- IDLE ----------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_IDLE, reason="IMAP4.idle() is Python 3.14+")
class TestIdler:
    """`idle()` | O(1): nothing is sent until the block starts; iterating
    yields each response as it arrives, instead of storing it."""

    def _idling(self, pushes: list[bytes]) -> tuple[FakeServer, FakeIMAP4]:
        server = FakeServer()
        server.idle_pushes = pushes
        return server, logged_in(server)

    def test_building_the_idler_sends_nothing(self) -> None:
        server, imap = self._idling([])
        sent = list(server.commands)

        imap.idle(duration=1)  # type: ignore[attr-defined]

        assert server.commands == sent

    def test_responses_are_yielded_not_stored(self) -> None:
        server, imap = self._idling([b"* 4 EXISTS"])
        imap.response("EXISTS")

        with imap.idle(duration=5) as idler:  # type: ignore[attr-defined]
            assert server.commands[-1] == "IDLE"
            responses = list(idler)  # ends when the socket times out
            assert "EXISTS" not in imap.untagged_responses

        assert responses == [("EXISTS", [b"4"])]
        assert server.commands[-1] == "DONE"
        assert imap.state == "SELECTED"

    def test_responses_left_unread_are_stored_on_exit(self) -> None:
        server = FakeServer()
        server.early_idle_pushes = [b"* 8 EXISTS", b"* 2 RECENT"]
        imap = logged_in(server)
        imap.response("EXISTS")
        imap.response("RECENT")

        with imap.idle():  # type: ignore[attr-defined]
            assert "EXISTS" not in imap.untagged_responses

        assert imap.untagged_responses["EXISTS"] == [b"8"]
        assert imap.untagged_responses["RECENT"] == [b"2"]

    def test_duration_counts_from_the_start_of_the_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        server, imap = self._idling([])
        clock = [100.0]
        monkeypatch.setattr(time, "monotonic", lambda: clock[0])

        with imap.idle(duration=5) as idler:  # type: ignore[attr-defined]
            clock[0] = 102.0
            server.timeouts.clear()
            assert list(idler) == []  # waits at most the 3 seconds left
            assert [t for t in server.timeouts if t] == [3.0]

            clock[0] = 106.0
            server.timeouts.clear()
            assert list(idler) == []  # past the deadline: no wait at all
            assert [t for t in server.timeouts if t] == []

    def test_burst_yields_what_is_queued_and_stops(self) -> None:
        pushes = [b"* 4 EXISTS", b"* 1 RECENT", b"* 2 FETCH (FLAGS (\\Seen))"]
        server, imap = self._idling(pushes)

        with imap.idle() as idler:  # type: ignore[attr-defined]
            batch = list(idler.burst(interval=0.01))

        assert [typ for typ, _ in batch] == ["EXISTS", "RECENT", "FETCH"]


# --- Module functions ---------------------------------------------------------------


class TestModuleFunctions:
    """`Internaldate2tuple`, `Time2Internaldate`, `ParseFlags` and `Int2AP`."""

    STAMP = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def test_parse_flags(self) -> None:
        assert imaplib.ParseFlags(rb"1 (FLAGS (\Seen \Answered) UID 7)") == (
            rb"\Seen",
            rb"\Answered",
        )
        assert imaplib.ParseFlags(b"1 (UID 7)") == ()

    def test_internaldate_to_local_time(self) -> None:
        parsed = imaplib.Internaldate2tuple(b'1 (INTERNALDATE "02-Jan-2024 03:04:05 +0000")')

        assert isinstance(parsed, time.struct_time)
        assert time.mktime(parsed) == self.STAMP.timestamp()
        assert imaplib.Internaldate2tuple(b"1 (UID 7)") is None

    def test_every_accepted_input_to_time2internaldate(self) -> None:
        expected = '"02-Jan-2024 03:04:05 +0000"'
        seconds = self.STAMP.timestamp()
        local = imaplib.Time2Internaldate(seconds)

        assert imaplib.Time2Internaldate(self.STAMP) == expected
        assert imaplib.Internaldate2tuple(b"INTERNALDATE " + local.encode()) == time.localtime(
            seconds
        )
        assert imaplib.Time2Internaldate(time.localtime(seconds)) == local
        assert imaplib.Time2Internaldate(int(seconds)) == local
        plain = tuple(time.localtime(seconds))
        assert imaplib.Time2Internaldate(plain) == local  # type: ignore[arg-type]
        assert imaplib.Time2Internaldate((*plain[:8], -1)) == local  # type: ignore[arg-type]
        assert imaplib.Time2Internaldate(expected) is expected
        shifted = self.STAMP.astimezone(timezone(timedelta(hours=2)))
        assert imaplib.Time2Internaldate(shifted) == '"02-Jan-2024 05:04:05 +0200"'
        with pytest.raises(ValueError):
            imaplib.Time2Internaldate(datetime(2024, 1, 2))

    def test_int2ap_uses_sixteen_letters(self) -> None:
        assert imaplib.Int2AP(0x1F) == b"BP"
        assert set(imaplib.Int2AP(16**50 - 1)) == {ord("P")}
        assert len(imaplib.Int2AP(16**50)) == 51

    @pytest.mark.timing
    def test_int2ap_is_quadratic_in_digits(self) -> None:
        small_number, large_number = 16**2_000 - 1, 16**32_000 - 1
        small = best_ns(partial(imaplib.Int2AP, small_number))
        large = best_ns(partial(imaplib.Int2AP, large_number))

        assert 64 < large / small < 1024, (
            f"16x the digits cost x{large / small:.1f}; linear gives x16, quadratic x256 "
            "and cubic x4096"
        )


# --- The page's examples --------------------------------------------------------------


PRELUDE = (
    "import sys\n"
    f"sys.path.insert(0, {str(pathlib.Path(__file__).parent)!r})\n"
    "import test_imaplib_complexity\n"
    "test_imaplib_complexity.install_fake_network()\n"
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
    return "IMAP4_SSL(" in source


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
    `FakeServer` through the prelude, and the `idle()` block needs 3.14."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if ".idle(" in source and not HAS_IDLE:
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS - (0 if HAS_IDLE else 1)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "cleared by the first call" in s)
        mutated = source.replace("('EXISTS', [None])", "('EXISTS', [b'3'])", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
