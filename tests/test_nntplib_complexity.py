"""Tests for docs/stdlib/nntplib.md.

The page prices the client's share of each call - sending one command line,
reading the reply, holding what the reply returns - and counts the exchanges
each call makes, since waiting for the server is outside every bound. No test
here talks to a real NNTP server. `FakeServer` answers each command line in
process, behind a `FakeSocket` whose `makefile('rwb')` is the one file
`nntplib` reads and writes through, so every exchange runs through the
module's own code. The fake counts the replies it sends, which is the exchange
count, and the lines the client reads. Space claims are settled by traced
allocation; the growth rates only a stopwatch shows are timed at sizes far
apart. The module exists on Python 3.10, 3.11 and 3.12 only, so every test
that touches it takes the `nntplib` fixture, which skips from 3.13; run them
with one of those interpreters. Lib/nntplib.py differs between v3.10.19,
v3.11.14 and v3.12.12 only in the import-time DeprecationWarning added in
3.11: no bound moves.

Measurement scope:

* Exchanges are counted as the replies the fake sends after its greeting.
  The constructor sends `CAPABILITIES` and nothing else; with
  `readermode=True` it adds `MODE READER` and a second `CAPABILITIES` when
  `READER` is not advertised, and nothing when it is; a server answering
  `MODE READER` with 480 gets `MODE READER` alone, and the `login()` after
  it sends `MODE READER` and `CAPABILITIES` again after its own three. With
  `user` the constructor adds `AUTHINFO USER`, `AUTHINFO PASS` and
  `CAPABILITIES`. `group()`, `stat()`, `next()`, `last()`, `article()`,
  `head()`, `body()`, `list()`, `newgroups()`, `newnews()`,
  `description()`, `descriptions()`, `xhdr()`, `date()`, `help()`,
  `slave()` and `quit()` make one each; the first of `over()` and `xover()`
  on a connection makes two, the second `LIST OVERVIEW.FMT`, and every
  later call of either makes one; `post()` and `ihave()` make two.
  `getwelcome()`, `getcapabilities()`, `set_debuglevel()` and
  `decode_header()` make none.
* `over()` sends `OVER` when the server advertises it and `XOVER` when not;
  `xover()` sends `XOVER` either way.
* Multi-line replies: `list()` reads r + 2 lines for 10 and 1,000 groups, the
  status line, one per group and the terminator, and returns every group.
  `description()` reads all of a 1,000-line reply although its first line
  matches. A timing test on one connection asserts that `over()` over
  100,000 articles costs between 20x and 1,000x what it does over 1,000,
  where linear gives 100x and quadratic 10,000x. With the reply built before
  the call, so that only the client allocates, `article()`'s traced peak
  rises more than 20x from 1,000 to 100,000 lines, and with `file=` a
  discarding writer its peak at 100,000 lines is under a twentieth of the
  list's.
* `file=`: a binary file object receives the reply's lines with their line
  endings and the leading dot of a doubled-dot line removed, and the call
  returns no lines; a file name is created and written; `over(file=...)`
  and `list(file=...)` return empty lists.
* A greeting of 2,048 bytes, CRLF included, is read; one of 2,049 raises
  `NNTPDataError('line too long')`, and so does a 2,049-byte line inside an
  article.
* Return shapes: `group()` returns `int` counts; `list()` and
  `newgroups()` return `GroupInfo` of four strings; `article()`, `head()`
  and `body()` return `ArticleInfo`;
  `stat()`, `next()` and `last()` return `(response, number, message_id)`;
  `over()` returns `(number, {field: value})`; `xhdr()` returns string
  pairs; `newnews()` and `help()` return strings; `date()` returns a
  `datetime`. `getcapabilities()` returns the same dictionary each call;
  `nntp_version` is 3 for `VERSION 2 3 1`, and with
  `CAPABILITIES` refused it is 1, `nntp_implementation` is `None` and the
  capabilities are `{}`. `newgroups()` and `newnews()` raise `TypeError` for
  a date string and send nothing. `getwelcome()` returns the greeting, and
  after an accepted `MODE READER` that reply instead.
* Posting: the lines `post()` sends, from `bytes` or a `BytesIO`, have a
  leading dot doubled and every ending made CRLF, and are followed by `.`;
  `ihave()` shares that code. Posting 100,000 lines as `bytes` has a traced
  peak more than 20x that of the same article from a `BytesIO`. `ihave()`
  refused with 435 raises `NNTPTemporaryError` and sends no article line.
* Login and TLS: `login()` sends `AUTHINFO USER`, `AUTHINFO PASS` and
  `CAPABILITIES`, and no `AUTHINFO PASS` when `AUTHINFO USER` is answered
  281; without `user` and with no `~/.netrc` it sends nothing,
  and with a `~/.netrc` entry for the host it uses it. `starttls()` sends
  `STARTTLS` then `CAPABILITIES` and wraps the socket with the context it
  was given; a second call raises `ValueError` with nothing sent. `NNTP_SSL`
  wraps the socket before the greeting is read and defaults to port 563,
  `NNTP` to 119. Without a context both use one with `verify_mode ==
  CERT_NONE` and `check_hostname` false.
* `timeout=0` raises `ValueError` before connecting. A `with` block sends
  `QUIT`. `set_debuglevel(1)` prints a `*cmd*` and a `*resp*` line per command
  and no line read; level 2 prints a `*get*` line for every line of an article.
  `NNTP.debug` is `NNTP.set_debuglevel`.
* `decode_header()`: 30x the encoded words, separated by spaces, cost
  between 150x and 5,000x, where linear gives 30x, quadratic 900x and cubic
  27,000x; the same on adjacent
  words; 100x the characters of a header with no encoded word cost under
  1,000x.
* Exceptions: a 4xx reply raises `NNTPTemporaryError`, a 5xx
  `NNTPPermanentError`, an unexpected 2xx `NNTPReplyError`, a reply starting
  with 6 `NNTPProtocolError`; each carries the reply in `response` and
  subclasses `NNTPError`.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess against a
  `FakeServer`, installed by a prelude that replaces
  `socket.create_connection()`, and a mutated assertion in a block is
  asserted to fail. The blocks' assertions about groups, articles and
  descriptions hold because the fake holds them in `GROUPS`; a real server's
  answers differ.

Not settled here:

* Every waiting cost: round trips, DNS, connection setup and the TLS
  handshake. The page counts exchanges instead of pricing them, and only the
  counts are run.
* Server behaviour: that `group()` makes a group current and that a pattern
  makes the server filter `list()` and `descriptions()` are RFC 3977, and
  hold on the fake only because it implements them. That `newnews()` and
  `newgroups()` return only what is newer than the date is RFC 3977 too;
  the fake ignores the date.
* `description()` and `descriptions()` send `XGTITLE` after
  `LIST NEWSGROUPS` when the server answers it with a multi-line code other
  than 215. RFC 3977 gives that command 215 alone, and a server without it
  answers 5xx, which raises; the second exchange is not counted on the
  page.
* The O(r) bounds follow from `_getlongresp()` reading and appending each
  line once, read from Lib/nntplib.py on every supported release; only
  `over()`, `article()` and `list()` are varied in r, and the rest share
  that path and are checked by value. Lines are capped at 2,048 bytes by
  `_MAXLINE`, so line count and byte count grow together; lines near the cap
  are not varied, and neither are overview fields per line. Group names,
  message ids and article numbers are priced at O(1) by the page's cost
  model and are not varied.
* `post()` time is O(d), with d in bytes, from the one loop over the lines
  in `_post()`; only its space is measured. Outgoing lines have no length
  cap, so the space of posting from a file is one line, whatever its length;
  line length is not varied.
* `login()` without `user` parses `~/.netrc`; the parse is not timed, and
  the file's size is not varied.
* `NNTP_SSL` starts with `tls_on` false, so its `starttls()` sends
  `STARTTLS` rather than raising; the page claims the `ValueError` only for
  a second `starttls()`, and no test calls it on `NNTP_SSL`.
* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594.
* The page-scoped audit's classification list names `ArticleInfo`,
  `GroupInfo` and their fields, `NNTP.capabilities`, `NNTP.encoding`,
  `NNTP.errors` and the `response` attribute inherited by each exception.
  The two named tuples are the return types in the `list()` and `article()`
  rows, `response` is priced on `NNTPError`, `capabilities()` is what the
  constructor and `getcapabilities()` call, and `encoding` and `errors` are
  the class's fixed codec settings, not on the page. `NNTP_SSL` inherits
  `nntp_version` and `nntp_implementation`, priced on `NNTP`. A row for
  calling `capabilities()` directly, which sends `CAPABILITIES` and does not
  update what `getcapabilities()` returns, is not on the page. `NNTP_PORT` and
  `NNTP_SSL_PORT` appear in the constructor rows as 119 and 563 and are
  asserted by the default ports.
"""

from __future__ import annotations

import datetime
import fnmatch
import gc
import importlib
import importlib.util
import io
import os
import pathlib
import re
import socket
import ssl
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "nntplib.md"
EXPECTED_BLOCKS = 6
USERS = {"reader": "secret"}
TRUSTED = {"local"}  # accepted at AUTHINFO USER, with no password asked
CAPABILITIES = [
    "VERSION 2",
    "READER",
    "OVER",
    "LIST ACTIVE NEWSGROUPS OVERVIEW.FMT",
    "POST",
    "IHAVE",
    "STARTTLS",
    "IMPLEMENTATION Fake NNTP 1.0",
]


def article_of(number: int, sender: str, subject: str, body: list[bytes], **extra: str) -> dict:
    headers = {
        "From": sender,
        "Subject": subject,
        "Date": "Thu, 01 Oct 2026 12:00:00 +0000",
        "Message-ID": f"<{number}@example.com>",
        **extra,
    }
    lines = [f"{name}: {value}".encode() for name, value in headers.items()]
    return {"number": number, "headers": headers, "head": lines, "body": body}


GROUPS: dict[str, dict[str, Any]] = {
    "comp.lang.c": {"description": "The C language.", "articles": []},
    "comp.lang.python": {
        "description": "The Python language.",
        "articles": [
            article_of(1, "ann@example.com", "Hello", [b"First post."]),
            article_of(
                2,
                "bob@example.com",
                "Re: Hello",
                [b".hidden dot line", b"Agreed."],
                References="<1@example.com>",
            ),
            article_of(3, "cara@example.com", "=?utf-8?q?Caf=C3=A9?=", [b"Coffee?"]),
        ],
    },
}


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, with the collector held off."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


# --- The fake server ------------------------------------------------------------


class FakeServer:
    """An NNTP server that answers in process, one reply per command line.

    It serves `GROUPS`, advertises `capabilities` (`None` refuses
    `CAPABILITIES` with a 500), adds `READER` on `MODE READER` (answering
    480 before a login when `reader_needs_auth` is set), drops `STARTTLS`
    once TLS is on, and keeps a current group and article.
    Setting `prepared` to a deque of reply lines makes the next command's
    reply come from it, built before the call, so only the client allocates.
    Articles posted are kept in `posted`, as the lines sent, unless
    `keep_posted` is false.
    """

    def __init__(
        self,
        *,
        greeting: bytes = b"200 Fake NNTP service ready, posting allowed",
        capabilities: list[str] | None = CAPABILITIES,
        reader_needs_auth: bool = False,
    ) -> None:
        self.reader_needs_auth = reader_needs_auth
        self.authenticated = False
        self.capabilities = None if capabilities is None else list(capabilities)
        self.commands: list[str] = []
        self.replies = 0
        self.lines_read = 0
        self.tls = False
        self.closed = False
        self.prepared: deque[bytes] | None = None
        self.posted: list[list[bytes]] = []
        self.posted_lines = 0
        self.keep_posted = True
        self.out = bytearray(greeting + b"\r\n")
        self._pending = bytearray()
        self._receiving: str | None = None
        self._article: list[bytes] = []
        self._user = ""
        self._group: str | None = None
        self._current = 0

    def verbs(self) -> list[str]:
        return [line.split(" ", 1)[0].upper() for line in self.commands]

    def reply(self, text: str) -> None:
        self.replies += 1
        self.out += text.encode("utf-8") + b"\r\n"

    def multiline(self, text: str, lines: list[bytes]) -> None:
        self.reply(text)
        for line in lines:
            self.out += (b"." + line if line.startswith(b".") else line) + b"\r\n"
        self.out += b".\r\n"

    def receive(self, data: bytes) -> None:
        if self._receiving is not None:
            self._article_line(data)
            return
        self._pending += data
        while b"\r\n" in self._pending:
            line, _, rest = bytes(self._pending).partition(b"\r\n")
            self._pending = bytearray(rest)
            self.commands.append(line.decode("utf-8"))
            self._command(line.decode("utf-8"))

    def _article_line(self, data: bytes) -> None:
        # nntplib writes an article one line per write() call.
        if data == b".\r\n":
            if self.keep_posted:
                self.posted.append(self._article)
            self._article = []
            done = "240 Article received OK" if self._receiving == "POST" else "235 Thanks"
            self._receiving = None
            self.reply(done)
            return
        self.posted_lines += 1
        if self.keep_posted:
            self._article.append(data)

    def _command(self, line: str) -> None:
        if self.prepared:
            self.replies += 1  # the reply is already queued in `prepared`
            return
        verb, _, args = line.partition(" ")
        handler = getattr(self, f"_do_{verb.lower()}", None)
        if handler is None:
            self.reply("500 Unknown command")
        else:
            handler(args)

    # Session

    def _do_capabilities(self, args: str) -> None:
        if self.capabilities is None:
            self.reply("500 Unknown command")
            return
        names = [c for c in self.capabilities if not (self.tls and c == "STARTTLS")]
        self.multiline("101 Capability list:", [c.encode() for c in names])

    def _do_mode(self, args: str) -> None:
        if self.reader_needs_auth and not self.authenticated:
            self.reply("480 Authentication required")
            return
        if self.capabilities is not None and "READER" not in self.capabilities:
            self.capabilities.append("READER")
        self.reply("200 Reader mode, posting allowed")

    def _do_authinfo(self, args: str) -> None:
        kind, _, value = args.partition(" ")
        if kind.upper() == "USER":
            self._user = value
            if value in TRUSTED:
                self.authenticated = True
                self.reply("281 Authentication accepted")
            else:
                self.reply("381 Password required")
        elif USERS.get(self._user) == value:
            self.authenticated = True
            self.reply("281 Authentication accepted")
        else:
            self.reply("481 Authentication failed")

    def _do_starttls(self, args: str) -> None:
        self.reply("382 Continue with TLS negotiation")

    def _do_quit(self, args: str) -> None:
        self.closed = True
        self.reply("205 Connection closing")

    def _do_date(self, args: str) -> None:
        self.reply("111 20261001123456")

    def _do_help(self, args: str) -> None:
        self.multiline("100 Help text follows", [b"article [message-id|number]", b"quit"])

    def _do_slave(self, args: str) -> None:
        self.reply("202 Slave status noted")

    # Groups

    def _listing(self, names: list[str]) -> list[bytes]:
        lines = []
        for name in names:
            numbers = [a["number"] for a in GROUPS[name]["articles"]]
            last, first = (max(numbers), min(numbers)) if numbers else (0, 1)
            lines.append(f"{name} {last} {first} y".encode())
        return lines

    def _matching(self, pattern: str) -> list[str]:
        return [name for name in sorted(GROUPS) if fnmatch.fnmatchcase(name, pattern or "*")]

    def _do_list(self, args: str) -> None:
        keyword, _, pattern = args.partition(" ")
        keyword = keyword.upper()
        if keyword in {"", "ACTIVE"}:
            self.multiline("215 List of newsgroups follows", self._listing(self._matching(pattern)))
        elif keyword == "NEWSGROUPS":
            descriptions = [
                f"{name}\t{GROUPS[name]['description']}".encode()
                for name in self._matching(pattern)
            ]
            self.multiline("215 Descriptions follow", descriptions)
        elif keyword == "OVERVIEW.FMT":
            fields = [b"Subject:", b"From:", b"Date:", b"Message-ID:", b"References:"]
            self.multiline("215 Order of fields follows", [*fields, b":bytes", b":lines"])
        else:
            self.reply("501 Syntax error")

    def _do_newgroups(self, args: str) -> None:
        self.multiline("231 New newsgroups follow", self._listing(sorted(GROUPS)))

    def _do_newnews(self, args: str) -> None:
        group = args.split(" ", 1)[0]
        ids = [a["headers"]["Message-ID"].encode() for a in GROUPS[group]["articles"]]
        self.multiline("230 New articles follow", ids)

    def _do_group(self, args: str) -> None:
        if args not in GROUPS:
            self.reply("411 No such newsgroup")
            return
        self._group = args
        numbers = [a["number"] for a in GROUPS[args]["articles"]]
        first, last = (min(numbers), max(numbers)) if numbers else (1, 0)
        self._current = first if numbers else 0
        self.reply(f"211 {len(numbers)} {first} {last} {args}")

    # Articles

    def _articles(self) -> list[dict]:
        return GROUPS[self._group]["articles"] if self._group else []

    def _find(self, spec: str) -> dict | None:
        for article in self._articles():
            if spec in ("", str(article["number"]), article["headers"]["Message-ID"]):
                if spec == "" and article["number"] != self._current:
                    continue
                return article
        self.reply("423 No article with that number")
        return None

    def _send_article(self, args: str, code: int, lines: Callable[[dict], list[bytes]]) -> None:
        article = self._find(args)
        if article is not None:
            self._current = article["number"]
            message_id = article["headers"]["Message-ID"]
            self.multiline(f"{code} {article['number']} {message_id}", lines(article))

    def _do_article(self, args: str) -> None:
        self._send_article(args, 220, lambda a: [*a["head"], b"", *a["body"]])

    def _do_head(self, args: str) -> None:
        self._send_article(args, 221, lambda a: a["head"])

    def _do_body(self, args: str) -> None:
        self._send_article(args, 222, lambda a: a["body"])

    def _do_stat(self, args: str) -> None:
        article = self._find(args)
        if article is not None:
            self._current = article["number"]
            self.reply(f"223 {article['number']} {article['headers']['Message-ID']}")

    def _step(self, offset: int, failure: str) -> None:
        numbers = [a["number"] for a in self._articles()]
        if self._current + offset not in numbers:
            self.reply(failure)
            return
        self._current += offset
        self._do_stat("")

    def _do_next(self, args: str) -> None:
        self._step(1, "421 No next article")

    def _do_last(self, args: str) -> None:
        self._step(-1, "422 No previous article")

    def _range(self, spec: str) -> list[dict]:
        if spec.startswith("<"):
            return [a for a in self._articles() if a["headers"]["Message-ID"] == spec]
        if not spec:
            return [a for a in self._articles() if a["number"] == self._current]
        low, _, high = spec.partition("-")
        top = int(high) if high else sys.maxsize
        return [a for a in self._articles() if int(low) <= a["number"] <= top]

    def _overview(self, args: str) -> None:
        lines = []
        for a in self._range(args):
            h = a["headers"]
            size = sum(len(line) + 2 for line in [*a["head"], b"", *a["body"]])
            fields = [
                str(a["number"]),
                h["Subject"],
                h["From"],
                h["Date"],
                h["Message-ID"],
                h.get("References", ""),
                str(size),
                str(len(a["body"])),
            ]
            lines.append("\t".join(fields).encode())
        self.multiline("224 Overview information follows", lines)

    def _do_over(self, args: str) -> None:
        if self.capabilities is not None and "OVER" not in self.capabilities:
            self.reply("500 Unknown command")
            return
        self._overview(args)

    def _do_xover(self, args: str) -> None:
        self._overview(args)

    def _do_xhdr(self, args: str) -> None:
        header, _, spec = args.partition(" ")
        values = [
            f"{a['number']} {a['headers'].get(header.title(), '')}".encode()
            for a in self._range(spec)
        ]
        self.multiline("221 Header follows", values)

    # Posting

    def _do_post(self, args: str) -> None:
        self._receiving = "POST"
        self.reply("340 Input article; end with <CR-LF>.<CR-LF>")

    def _do_ihave(self, args: str) -> None:
        if any(args == a["headers"]["Message-ID"] for g in GROUPS.values() for a in g["articles"]):
            self.reply("435 Article not wanted")
            return
        self._receiving = "IHAVE"
        self.reply("335 Send article to be transferred")


class FakeFile:
    """The `makefile('rwb')` side: hands out what the server has written and
    passes what the client writes to the server."""

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

    def write(self, data: bytes) -> int:
        self.server.receive(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeSocket:
    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def makefile(self, mode: str = "rwb") -> FakeFile:
        return FakeFile(self.server)

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
        self.greeting_unread_at_wrap.append(sock.server.out.startswith(b"200 "))
        sock.server.tls = True
        return sock


def install_fake_network() -> Network:
    """Route `nntplib` to fresh `FakeServer`s for the rest of the process."""
    network = Network()

    def wrap_socket(self: ssl.SSLContext, sock: Any, *args: Any, **kwargs: Any) -> Any:
        return network.wrap_socket(self, sock, *args, **kwargs)

    socket.create_connection = network.create_connection  # type: ignore[assignment]
    ssl.SSLContext.wrap_socket = wrap_socket  # type: ignore[method-assign]
    return network


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("nntplib") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def nntplib() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: nntplib was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("nntplib")


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> Network:
    net = Network()

    def wrap_socket(self: ssl.SSLContext, sock: Any, *args: Any, **kwargs: Any) -> Any:
        return net.wrap_socket(self, sock, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", net.create_connection)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap_socket)
    return net


def connect(nntplib: Any, network: Network, **options: Any) -> Any:
    network.options = options
    return nntplib.NNTP("news.example.com")


def exchanges(network: Network, call: Callable[[], Any]) -> tuple[Any, int, list[str]]:
    """Run `call` and return its result, the replies it took and its verbs."""
    server = network.server
    replies, seen = server.replies, len(server.commands)
    result = call()
    return result, server.replies - replies, server.verbs()[seen:]


def prepare(server: FakeServer, status: str, lines: list[bytes]) -> None:
    """Queue a whole reply, built before the call that reads it."""
    server.prepared = deque([status.encode() + b"\r\n", *lines, b".\r\n"])


def overview_lines(count: int) -> list[bytes]:
    return [
        f"{n}\tSubject {n}\ta@example.com\tdate\t<{n}@example.com>\t\t100\t2\r\n".encode()
        for n in range(1, count + 1)
    ]


class TestAvailability:
    """`import nntplib` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("nntplib")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="nntplib was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import nntplib"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "nntplib" in result.stderr


# --- Connections ----------------------------------------------------------------


class TestConnecting:
    """`nntplib.NNTP(host, ...)` | O(r) | O(r): the greeting and
    `CAPABILITIES`, plus `MODE READER` and `login()` when asked for;
    `getwelcome()` and `getcapabilities()` answer without an exchange."""

    def test_the_constructor_sends_capabilities_alone(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        assert network.addresses == [("news.example.com", 119)]
        assert network.server.verbs() == ["CAPABILITIES"]
        assert network.server.replies == 1
        assert nntp.getwelcome().startswith("200 ")

    def test_reader_mode_adds_two_exchanges_only_when_not_advertised(
        self, nntplib: Any, network: Network
    ) -> None:
        network.options = {"capabilities": [c for c in CAPABILITIES if c != "READER"]}
        nntplib.NNTP("news.example.com", readermode=True)
        assert network.server.verbs() == ["CAPABILITIES", "MODE", "CAPABILITIES"]

        network.options = {}
        nntplib.NNTP("news.example.com", readermode=True)
        assert network.server.verbs() == ["CAPABILITIES"]

    def test_a_480_moves_reader_mode_into_login(self, nntplib: Any, network: Network) -> None:
        network.options = {
            "capabilities": [c for c in CAPABILITIES if c != "READER"],
            "reader_needs_auth": True,
        }
        nntp = nntplib.NNTP("news.example.com", readermode=True)
        assert network.server.verbs() == ["CAPABILITIES", "MODE"]

        _, count, verbs = exchanges(network, lambda: nntp.login("reader", "secret"))
        assert (count, verbs) == (
            5,
            ["AUTHINFO", "AUTHINFO", "CAPABILITIES", "MODE", "CAPABILITIES"],
        )
        assert nntp.getwelcome() == "200 Reader mode, posting allowed"

    def test_an_accepted_mode_reader_replaces_the_welcome(
        self, nntplib: Any, network: Network
    ) -> None:
        network.options = {"capabilities": [c for c in CAPABILITIES if c != "READER"]}
        nntp = nntplib.NNTP("news.example.com", readermode=True)

        assert nntp.getwelcome() == "200 Reader mode, posting allowed"

    def test_a_user_adds_the_login(self, nntplib: Any, network: Network) -> None:
        nntplib.NNTP("news.example.com", user="reader", password="secret")

        assert network.server.verbs() == ["CAPABILITIES", "AUTHINFO", "AUTHINFO", "CAPABILITIES"]

    def test_welcome_and_capabilities_cost_no_exchange(
        self, nntplib: Any, network: Network
    ) -> None:
        nntp = connect(nntplib, network)

        (welcome, caps), count, _ = exchanges(
            network, lambda: (nntp.getwelcome(), nntp.getcapabilities())
        )
        assert count == 0
        assert welcome is nntp.getwelcome()
        assert caps is nntp.getcapabilities()
        assert caps["LIST"] == ["ACTIVE", "NEWSGROUPS", "OVERVIEW.FMT"]
        assert caps["OVER"] == []
        assert nntp.nntp_version == 2
        assert nntp.nntp_implementation == "Fake NNTP 1.0"

    def test_the_highest_version_is_taken(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network, capabilities=["VERSION 2 3 1", "READER"])

        assert nntp.nntp_version == 3

    def test_without_capabilities_the_version_is_1(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network, capabilities=None)

        assert nntp.getcapabilities() == {}
        assert nntp.nntp_version == 1
        assert nntp.nntp_implementation is None

    def test_timeout_zero_raises_before_connecting(self, nntplib: Any, network: Network) -> None:
        with pytest.raises(ValueError, match="Non-blocking"):
            nntplib.NNTP("news.example.com", timeout=0)
        assert network.servers == []

    def test_a_with_block_sends_quit(self, nntplib: Any, network: Network) -> None:
        with connect(nntplib, network):
            pass

        assert network.server.verbs()[-1] == "QUIT"
        assert network.server.closed

    def test_quit_is_one_exchange_and_closes(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        response, count, verbs = exchanges(network, nntp.quit)
        assert (count, verbs) == (1, ["QUIT"])
        assert response.startswith("205")
        assert not hasattr(nntp, "file")

    def test_debug_levels(
        self, nntplib: Any, network: Network, capsys: pytest.CaptureFixture[str]
    ) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")
        assert nntplib.NNTP.debug is nntplib.NNTP.set_debuglevel

        nntp.set_debuglevel(1)
        nntp.article(2)
        level1 = capsys.readouterr().out
        nntp.set_debuglevel(2)
        response, info = nntp.article(2)
        level2 = capsys.readouterr().out

        assert level1.count("*cmd*") == level1.count("*resp*") == 1
        assert "*get*" not in level1
        assert level2.count("*get*") == len(info.lines) + 2


class TestLogin:
    """`NNTP.login(user=None, password=None, usenetrc=True)`: `AUTHINFO USER`,
    `AUTHINFO PASS` when asked, `CAPABILITIES`; without `user`, `~/.netrc`
    or nothing."""

    def test_no_pass_is_sent_when_none_is_asked_for(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        _, count, verbs = exchanges(network, lambda: nntp.login("local", "unused"))
        assert (count, verbs) == (2, ["AUTHINFO", "CAPABILITIES"])

    def test_login_sends_user_pass_and_capabilities(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        _, count, verbs = exchanges(network, lambda: nntp.login("reader", "secret"))
        assert (count, verbs) == (3, ["AUTHINFO", "AUTHINFO", "CAPABILITIES"])

    def test_without_a_user_or_netrc_it_sends_nothing(
        self, nntplib: Any, network: Network, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        nntp = connect(nntplib, network)

        _, count, _ = exchanges(network, nntp.login)
        assert count == 0

    def test_a_netrc_entry_is_used(
        self, nntplib: Any, network: Network, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        netrc = tmp_path / ".netrc"
        netrc.write_text("machine news.example.com login reader password secret\n")
        netrc.chmod(0o600)
        monkeypatch.setenv("HOME", str(tmp_path))
        nntp = connect(nntplib, network)

        _, count, _ = exchanges(network, nntp.login)
        assert count == 3
        assert network.server.commands[-3:-1] == ["authinfo user reader", "authinfo pass secret"]


class TestTls:
    """`NNTP.starttls(context=None)` and `nntplib.NNTP_SSL(...)`: one
    exchange and `CAPABILITIES` again, or TLS from the first byte on port
    563; neither verifies the certificate without a context."""

    def test_starttls_wraps_and_rereads_the_capabilities(
        self, nntplib: Any, network: Network
    ) -> None:
        nntp = connect(nntplib, network)
        context = ssl.create_default_context()

        _, count, verbs = exchanges(network, lambda: nntp.starttls(context))
        assert (count, verbs) == (2, ["STARTTLS", "CAPABILITIES"])
        assert network.contexts == [context]
        assert "STARTTLS" not in nntp.getcapabilities()

    def test_a_second_starttls_sends_nothing(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.starttls()

        sent, replies = len(network.server.commands), network.server.replies

        with pytest.raises(ValueError, match="already"):
            nntp.starttls()
        assert (len(network.server.commands), network.server.replies) == (sent, replies)

    def test_nntp_ssl_wraps_before_the_greeting(self, nntplib: Any, network: Network) -> None:
        nntplib.NNTP_SSL("news.example.com")

        assert network.addresses == [("news.example.com", 563)]
        assert network.greeting_unread_at_wrap == [True]
        assert nntplib.NNTP_SSL_PORT == 563
        assert nntplib.NNTP_PORT == 119

    def test_the_default_context_does_not_verify(self, nntplib: Any, network: Network) -> None:
        nntplib.NNTP_SSL("news.example.com")
        connect(nntplib, network).starttls()

        for context in network.contexts:
            assert context.verify_mode == ssl.CERT_NONE
            assert not context.check_hostname
        recommended = ssl.create_default_context()
        assert recommended.verify_mode == ssl.CERT_REQUIRED
        assert recommended.check_hostname


# --- Multi-line replies ---------------------------------------------------------


class TestLongRepliesAreLists:
    """Every multi-line reply is O(r): each line is read and kept once, and a
    line over 2,048 bytes raises `NNTPDataError`."""

    @pytest.mark.parametrize("groups", [10, 1_000])
    def test_list_reads_each_line_once(self, nntplib: Any, network: Network, groups: int) -> None:
        nntp = connect(nntplib, network)
        lines = [f"group{i} 10 1 y\r\n".encode() for i in range(groups)]
        before = network.server.lines_read
        prepare(network.server, "215 List follows", lines)

        response, found = nntp.list()

        assert network.server.lines_read - before == groups + 2
        assert len(found) == groups
        assert found[0] == nntplib.GroupInfo("group0", "10", "1", "y")

    @pytest.mark.timing
    def test_over_grows_linearly(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")
        nntp.over((1, 3))  # caches the overview format
        times: list[int] = []
        for count in (1_000, 100_000):
            lines = overview_lines(count)
            elapsed: list[int] = []
            for _ in range(3):
                prepare(network.server, "224 Overview follows", lines)
                start = time.perf_counter_ns()
                response, overviews = nntp.over((1, None))
                elapsed.append(time.perf_counter_ns() - start)
                assert len(overviews) == count
            times.append(min(elapsed))

        ratio = times[1] / times[0]
        assert 20 < ratio < 1_000, f"100x the articles cost {ratio:.0f}x"

    def test_the_article_peak_follows_its_lines(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        peaks: list[int] = []
        for count in (1_000, 100_000):
            lines = [b"x" * 60 + b"\r\n"] * count
            prepare(network.server, "220 1 <1@example.com>", lines)
            peaks.append(peak_bytes(lambda: nntp.article(1)))

        assert peaks[1] > 20 * peaks[0], f"peaks {peaks} for 1,000 and 100,000 lines"

    def test_file_keeps_the_lines_out_of_memory(self, nntplib: Any, network: Network) -> None:
        class Discard:
            written = 0

            def write(self, data: bytes) -> None:
                self.written += 1

        nntp = connect(nntplib, network)
        lines = [b"x" * 60 + b"\r\n"] * 100_000
        sink = Discard()
        prepare(network.server, "220 1 <1@example.com>", lines)
        to_file = peak_bytes(lambda: nntp.article(1, file=sink))
        prepare(network.server, "220 1 <1@example.com>", lines)
        to_list = peak_bytes(lambda: nntp.article(1))

        assert sink.written == 100_000
        assert to_file * 20 < to_list, f"{to_file} bytes to a file, {to_list} to a list"

    def test_a_2048_byte_line_is_read_and_2049_raises(self, nntplib: Any, network: Network) -> None:
        greeting = b"200 " + b"x" * (2_048 - 6)
        network.options = {"greeting": greeting}
        nntp = nntplib.NNTP("news.example.com")
        server = network.server
        assert nntp.getwelcome() == greeting.decode()

        network.options = {"greeting": greeting + b"x"}
        with pytest.raises(nntplib.NNTPDataError, match="line too long"):
            nntplib.NNTP("news.example.com")

        prepare(server, "220 1 <1@example.com>", [b"y" * 2_047 + b"\r\n"])
        with pytest.raises(nntplib.NNTPDataError, match="line too long"):
            nntp.article(1)


class TestWritingToAFile:
    """With `file=`, the lines go to the file and the call returns none."""

    def test_a_file_object_gets_the_raw_lines(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")
        sink = io.BytesIO()

        response, info = nntp.body(2, file=sink)

        assert info.lines == []
        assert sink.getvalue() == b".hidden dot line\r\nAgreed.\r\n"

    def test_a_file_name_is_created(
        self, nntplib: Any, network: Network, tmp_path: pathlib.Path
    ) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")
        path = tmp_path / "article"

        nntp.article(1, file=str(path))

        assert path.read_bytes().endswith(b"\r\n\r\nFirst post.\r\n")

    def test_parsed_replies_come_back_empty(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")
        sink = io.BytesIO()

        assert nntp.over((1, 3), file=sink)[1] == []
        assert sink.getvalue().count(b"\t") == 3 * 7
        assert nntp.list(file=io.BytesIO())[1] == []


# --- Groups ---------------------------------------------------------------------


class TestGroups:
    """`group()` is one exchange returning ints; `list()`, `newgroups()`,
    `description()` and `descriptions()` are one exchange each and O(r)."""

    def test_group_returns_ints(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        result, count, _ = exchanges(network, lambda: nntp.group("comp.lang.python"))
        assert count == 1
        assert result[1:] == (3, 1, 3, "comp.lang.python")

    def test_list_returns_groupinfo_of_strings(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        (_, groups), count, _ = exchanges(network, lambda: nntp.list("comp.lang.*"))
        assert count == 1
        assert network.server.commands[-1] == "LIST ACTIVE comp.lang.*"
        assert groups == [
            nntplib.GroupInfo("comp.lang.c", "0", "1", "y"),
            nntplib.GroupInfo("comp.lang.python", "3", "1", "y"),
        ]

    def test_newgroups_takes_a_date(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        (_, groups), count, _ = exchanges(
            network, lambda: nntp.newgroups(datetime.date(2026, 1, 1))
        )
        assert count == 1
        assert network.server.commands[-1] == "NEWGROUPS 20260101 000000"
        assert all(isinstance(g, nntplib.GroupInfo) for g in groups)
        with pytest.raises(TypeError):
            exchanges(network, lambda: nntp.newgroups("20260101"))
        with pytest.raises(TypeError):
            nntp.newnews("comp.lang.python", "20260101")
        assert network.server.commands[-1] == "NEWGROUPS 20260101 000000"

    def test_description_reads_the_whole_reply(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        lines = [f"group{i}\tGroup {i}.\r\n".encode() for i in range(1_000)]
        before = network.server.lines_read
        prepare(network.server, "215 Descriptions follow", lines)

        assert nntp.description("group*") == "Group 0."
        assert network.server.lines_read - before == 1_002
        assert nntp.description("no.such.group") == ""

    def test_descriptions_returns_a_dict(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        (response, found), count, _ = exchanges(network, lambda: nntp.descriptions("comp.lang.*"))
        assert count == 1
        assert found == {
            "comp.lang.c": "The C language.",
            "comp.lang.python": "The Python language.",
        }


# --- Articles -------------------------------------------------------------------


class TestArticles:
    """`stat()`, `next()`, `last()` are one exchange returning no article;
    `article()`, `head()`, `body()`, `over()`, `xover()`, `xhdr()` and
    `newnews()` are O(r)."""

    def test_stat_next_and_last(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")

        for call, number in ((nntp.stat, 1), (nntp.next, 2), (nntp.last, 1)):
            result, count, _ = exchanges(network, call)
            assert count == 1
            assert result[1:] == (number, f"<{number}@example.com>")

    def test_article_head_and_body(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")

        (_, info), count, _ = exchanges(network, lambda: nntp.article("<2@example.com>"))
        assert count == 1
        assert isinstance(info, nntplib.ArticleInfo)
        assert (info.number, info.message_id) == (2, "<2@example.com>")
        assert info.lines[-2:] == [b".hidden dot line", b"Agreed."]
        assert nntp.head(2)[1].lines == info.lines[: info.lines.index(b"")]
        assert nntp.body(2)[1].lines == [b".hidden dot line", b"Agreed."]

    def test_over_fetches_the_format_once(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")

        (_, first), count1, verbs1 = exchanges(network, lambda: nntp.over((1, 3)))
        (_, second), count2, verbs2 = exchanges(network, lambda: nntp.over((2, None)))

        assert (count1, verbs1) == (2, ["OVER", "LIST"])
        assert (count2, verbs2) == (1, ["OVER"])
        assert network.server.commands[-1] == "OVER 2-"
        assert [n for n, _ in first] == [1, 2, 3]
        assert first[1][1]["references"] == "<1@example.com>"
        assert [n for n, _ in second] == [2, 3]

    def test_over_falls_back_to_xover(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network, capabilities=[c for c in CAPABILITIES if c != "OVER"])
        nntp.group("comp.lang.python")

        _, _, verbs = exchanges(network, lambda: nntp.over((1, 3)))
        assert verbs[0] == "XOVER"

    def test_xover_is_always_xover_and_shares_the_format(
        self, nntplib: Any, network: Network
    ) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")

        (_, found), count, verbs = exchanges(network, lambda: nntp.xover(1, 3))
        assert (count, verbs) == (2, ["XOVER", "LIST"])
        assert [n for n, _ in found] == [1, 2, 3]
        _, count, verbs = exchanges(network, lambda: nntp.over((1, 3)))
        assert (count, verbs) == (1, ["OVER"])

    def test_xhdr_and_newnews_return_strings(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        nntp.group("comp.lang.python")

        (_, pairs), count, _ = exchanges(network, lambda: nntp.xhdr("subject", "1-2"))
        assert count == 1
        assert pairs == [("1", "Hello"), ("2", "Re: Hello")]
        (_, ids), count, _ = exchanges(
            network,
            lambda: nntp.newnews("comp.lang.python", datetime.datetime(2026, 1, 1)),
        )
        assert count == 1
        assert ids == ["<1@example.com>", "<2@example.com>", "<3@example.com>"]


# --- Posting --------------------------------------------------------------------


class TestPosting:
    """`NNTP.post(data)` and `NNTP.ihave(message_id, data)` | O(d) | O(d) for
    `bytes`, one line for a file: two exchanges, a line at a time."""

    ARTICLE = b"Subject: Test\r\n\r\n.A line starting with a dot.\r\nEnd\n"

    def test_post_is_two_exchanges_and_stuffs_dots(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        for data in (self.ARTICLE, io.BytesIO(self.ARTICLE)):
            response, count, verbs = exchanges(network, lambda data=data: nntp.post(data))
            assert (count, verbs) == (2, ["POST"])
            assert response.startswith("240")
            assert network.server.posted[-1] == [
                b"Subject: Test\r\n",
                b"\r\n",
                b"..A line starting with a dot.\r\n",
                b"End\r\n",
            ]

    def test_bytes_are_split_into_a_list_first(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)
        network.server.keep_posted = False
        data = b"".join(f"line {i}\r\n".encode() for i in range(100_000))

        from_bytes = peak_bytes(lambda: nntp.post(data))
        stream = io.BytesIO(data)
        from_file = peak_bytes(lambda: nntp.post(stream))

        assert network.server.posted_lines == 200_000
        assert from_bytes > 20 * from_file, f"{from_bytes} from bytes, {from_file} from a file"

    def test_ihave_sends_nothing_when_refused(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        with pytest.raises(nntplib.NNTPTemporaryError) as caught:
            nntp.ihave("<1@example.com>", self.ARTICLE)
        assert caught.value.response.startswith("435")
        assert network.server.posted_lines == 0

        response, count, _ = exchanges(
            network, lambda: nntp.ihave("<9@example.com>", io.BytesIO(self.ARTICLE))
        )
        assert count == 2
        assert response.startswith("235")


# --- Other commands -------------------------------------------------------------


class TestOtherCommands:
    """`date()`, `help()` and `slave()` are one exchange each."""

    def test_date_help_and_slave(self, nntplib: Any, network: Network) -> None:
        nntp = connect(nntplib, network)

        (_, when), count, _ = exchanges(network, nntp.date)
        assert count == 1
        assert when == datetime.datetime(2026, 10, 1, 12, 34, 56)
        (_, text), count, _ = exchanges(network, nntp.help)
        assert count == 1
        assert text == ["article [message-id|number]", "quit"]
        response, count, _ = exchanges(network, nntp.slave)
        assert count == 1
        assert response.startswith("202")


class TestDecodeHeader:
    """`nntplib.decode_header(header_str)` | O(h + w²): linear in characters,
    quadratic in encoded words."""

    def test_it_decodes_encoded_words(self, nntplib: Any) -> None:
        assert nntplib.decode_header("=?utf-8?q?Caf=C3=A9?=") == "Café"
        assert nntplib.decode_header("Re: =?utf-8?b?Q2Fmw6k=?= time") == "Re: Café time"

    @pytest.mark.timing
    @pytest.mark.parametrize("separator", [" ", ""])
    def test_encoded_words_cost_quadratically(self, nntplib: Any, separator: str) -> None:
        headers = [separator.join(["=?utf-8?q?a?="] * w) for w in (500, 15_000)]
        times = [best_ns(lambda h=h: nntplib.decode_header(h), 3) for h in headers]

        ratio = times[1] / times[0]
        assert 150 < ratio < 5_000, (
            f"30x the encoded words cost {ratio:.0f}x; linear is 30x, quadratic 900x"
        )

    @pytest.mark.timing
    def test_plain_characters_cost_linearly(self, nntplib: Any) -> None:
        headers = ["Subject " * h for h in (10_000, 1_000_000)]
        times = [best_ns(lambda h=h: nntplib.decode_header(h), 5) for h in headers]

        ratio = times[1] / times[0]
        assert ratio < 1_000, f"100x the characters cost {ratio:.0f}x; quadratic is 10,000x"


class TestExceptions:
    """Each reply class raises its exception, which keeps the reply in
    `response`."""

    @pytest.mark.parametrize(
        ("status", "name"),
        [
            ("411 No such group", "NNTPTemporaryError"),
            ("502 Permission denied", "NNTPPermanentError"),
            ("200 Unexpected", "NNTPReplyError"),
            ("600 Nonsense", "NNTPProtocolError"),
        ],
    )
    def test_reply_classes(self, nntplib: Any, network: Network, status: str, name: str) -> None:
        nntp = connect(nntplib, network)
        network.server.prepared = deque([status.encode() + b"\r\n"])

        with pytest.raises(getattr(nntplib, name)) as caught:
            nntp.group("comp.lang.python")
        assert caught.value.response == status
        assert isinstance(caught.value, nntplib.NNTPError)

    def test_data_error_is_an_nntp_error(self, nntplib: Any) -> None:
        assert issubclass(nntplib.NNTPDataError, nntplib.NNTPError)
        assert nntplib.NNTPError().response == "No response given"


# --- The page's examples --------------------------------------------------------


PRELUDE = (
    "import sys\n"
    f"sys.path.insert(0, {str(pathlib.Path(__file__).parent)!r})\n"
    "import test_nntplib_complexity\n"
    "test_nntplib_complexity.install_fake_network()\n"
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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and reaches a `FakeServer`
    through the prelude, on the versions that still have the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("nntplib.NNTP(" in source for _, source in blocks)

    def test_every_block_runs(self, nntplib: Any, tmp_path: pathlib.Path) -> None:
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
        self, nntplib: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "(3, 1, 3)" in s)
        mutated = source.replace("(3, 1, 3)", "(3, 1, 4)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
