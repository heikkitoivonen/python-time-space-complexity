"""Tests for docs/stdlib/ftplib.md.

The page prices the client's share of each call: one command line out and
one reply back on the control connection, and a stream of blocks or lines on
a data connection. No test talks to a real server. `FakeFTPServer` is an FTP
server on 127.0.0.1 in threads of this process, so every call runs through
the module's own sockets, in passive and active mode. The server renders a
listing once and sends a download from the stored bytes without copying, so
once warm it adds nothing that grows with a transfer to a traced peak. Space
claims are settled by traced allocation, command and connection claims by
what the server records, and the one growth rate only a stopwatch shows by
ratios between sizes.

Measurement scope:

* `retrbinary()` of an 8 MB file to a callback that keeps nothing peaks
  under 200 KB, and collecting the blocks peaks over 8 MB. A 1 MiB
  `blocksize` peaks between 1 MiB and 4 MiB. With `blocksize=1000` every
  block is at most 1,000 bytes and the blocks join to the file.
  `storbinary()` of an 8 MB `BytesIO` peaks under 200 KB with the server
  discarding the upload, and a recording file object shows each block read,
  sent on the data socket and passed to the callback before the next
  read.
* `retrlines()` of 10,000 and of 200,000 75-byte lines peaks under 1 MB
  for the 15 MB file and under twice the smaller file's peak; `storlines()`
  of the 15 MB file peaks under 1 MB. The cap counts the line ending: a
  download of 8,191 characters plus `\n` or `\r\n` (which the text reader
  turns into one `\n`) passes and 8,192 plus `\n` raises `ftplib.Error`;
  an upload of 8,191 bytes plus `\n` passes while 8,191 plus `\r\n` and
  8,192 plus `\n` raise. 4,096 two-byte `é` characters plus `\n` pass as a
  download and raise as an upload, so the download cap counts characters
  and the upload cap bytes. A 9,004-character reply line raises too. Downloaded lines end
  in CRLF or LF and are stripped of either; uploaded lines are sent with
  CRLF; a `StringIO` passed to `storlines()` raises `TypeError`.
* Over 20,000 names, `nlst()` and the first `next()` of `mlsd()` each peak
  above the size of their listing's text, and `dir()` to a counting callback
  peaks under a quarter of it. `mlsd()` sends nothing until the first
  `next()`, sends `OPTS MLST` for `facts` first, and no command after it.
* The server counts one data connection per `retrbinary()`, `retrlines()`,
  `storbinary()`, `storlines()`, `nlst()`, `dir()` and `mlsd()` call, and
  four for listing and fetching three files. `set_pasv(False)` sends `PORT`
  and never `PASV`, and the transfer still arrives.
* A `STAT` reply of 8,000 and of 128,000 lines is timed through
  `sendcmd()`, fastest of nine, read from an in-memory file standing in for
  the control connection so no socket or server thread is timed; every
  line is the same width. 16x the lines costs between 4x and 64x, where
  reading linearly gives 16x and copying the reply so far on every line
  256x. The multi-line reply itself is also run against the server.
* Commands are asserted by the lines the server receives and the replies
  returned: `cwd('..')` sends `CDUP`, `rename()` sends `RNFR` then `RNTO`,
  `login()` sends `PASS` only after a `3xx` to `USER` and `ACCT` only after
  one to `PASS`, `mkd()` and `pwd()` return a path with an embedded quote,
  `4xx`, `5xx` and `6xx` replies raise `error_temp`, `error_perm` and
  `error_proto`, and `voidcmd()` raises `error_reply` on a `350`.
  `ntransfercmd()` returns the size from a `150 ... (n bytes)` reply and
  `None` for a listing; a data connection closed after one `recv()` leaves a
  `226` or `426` reply for `voidresp()`, after which commands are in step.
* Leaving a `with` block sends `QUIT`, and succeeds after the server has
  closed; `quit()` raises on a `500` and leaves the socket open, while
  `close()` sends nothing and can be called twice; debug level 1 prints
  commands and replies with the password masked, and level 2 the raw lines.
* `FTP_TLS` runs with a context whose `wrap_socket()` records each socket
  and returns a stand-in for `ssl.SSLSocket`, patched in for the test:
  `login()` sends `AUTH TLS` before `USER` and wraps once, `secure=False`
  sends no `AUTH`, a listing before `prot_p()` is not wrapped, each
  retrieval after it is wrapped once, and none after `prot_c()`; `ccc()`
  sends `CCC` and leaves a plain socket. `ssl_version` is asserted on 3.10
  and 3.11 and absent from 3.12, where `keyfile`, `certfile` and a positional
  `context` raise `TypeError`.
* Every fenced Python block runs in its own subprocess and working
  directory; a prelude routes `ftp.example.com` to a `FakeFTPServer` and
  makes `ssl.SSLContext.wrap_socket()` return the socket unwrapped. A
  mutated assertion in a block is asserted to fail.

Not settled here:

* Every waiting cost: round trips, DNS lookups and connection setup, the TLS
  handshakes of `FTP_TLS` on the control connection and on each data
  connection after `prot_p()`, and the server's own work. That keeping one
  connection open beats logging in per file rests on the round trips it
  saves, which no in-process measurement sees. Real TLS is not run: the
  stand-in shows which sockets are wrapped, not what wrapping costs.
* `all_errors` without `ssl.SSLError` needs a Python built without `ssl`.
  `abort()` during a live transfer, and how a server answers `SIZE` in ASCII
  mode, are server behaviour; only `ABOR` and its `225` reply are run.
* The O(c + r) bounds of the commands not timed follow from the one path
  every command takes, `putline()` then `getresp()`, read from
  Lib/ftplib.py; `pwd()` and `mkd()` parse the `257` reply a character at a
  time. Command lengths, reply-line lengths below the cap, IPv6 (`EPSV`
  and `EPRT`) and non-UTF-8 encodings are not varied; multibyte text is
  run only at the line cap.
* Reading a multi-line reply relies on appending to a string held once;
  the timing shows it linear on each supported version, not independent of
  the allocator.
* That the first `next()` of `mlsd()` drains the listing is shown by its
  peak, by no further command, and by a `NOOP` sent between the first and
  second entries getting its own `200`, which it could not while the
  listing's final reply was unread; the data socket is not watched.
* The undocumented names are left off the page: the reply parsers
  `parse150()`, `parse227()`, `parse229()` and `parse257()`, `ftpcp()`,
  `print_line()`, `test()`, the constants `FTP_PORT`, `MAXLINE`, `CRLF`,
  `B_CRLF` and `MSG_OOB`, and the `FTP` internals the audit discovers at
  run time (`acct()`, `getline()`, `getmultiline()`, `getresp()`,
  `voidresp()`, `putline()`, `putcmd()`, `makeport()`, `makepasv()`,
  `sendport()`, `sendeprt()`, `sanitize()`, and the attributes `host`,
  `port`, `sock`, `file`, `welcome`, `debugging`, `maxline`, `passiveserver`
  and `trust_server_pasv_ipv4_address`). `ftplib.Error` is named once, as
  what the line cap raises. `FTP_TLS.login()`, `abort()` and
  `ntransfercmd()` are covered by their `FTP` rows and the `secure=False`
  note.
"""

from __future__ import annotations

import contextlib
import ftplib
import io
import pathlib
import posixpath
import re
import socket
import ssl
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ftplib.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, the server's threads included."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


# --- An FTP server in this process ------------------------------------------------------


class FakeFTPServer:
    """An FTP server on 127.0.0.1 that runs in threads of this process and
    keeps its files in memory.

    It speaks enough of RFC 959 and RFC 3659 for every `ftplib` call on the
    page, in passive and active mode, and records what it was sent:
    `commands` holds every command line, `data_connections` counts the data
    connections opened. `replies` maps a command to a canned reply that
    replaces its handler. Listings are rendered once per directory and cached,
    and a download is sent from the stored bytes without copying them, so
    what the server allocates does not grow with a transfer once warm.
    """

    def __init__(self, files: dict[str, bytes] | None = None, dirs: tuple[str, ...] = ()) -> None:
        self.files: dict[str, bytes] = dict(files or {})
        self.dirs: set[str] = {"/", *dirs}
        for path in self.files:
            parent = posixpath.dirname(path)
            while parent not in self.dirs:
                self.dirs.add(parent)
                parent = posixpath.dirname(parent)
        self.commands: list[str] = []
        self.data_connections = 0
        self.keep_uploads = True
        self.uploaded = 0
        self.stat_lines = 0
        self.replies: dict[str, str] = {}
        self.listings: dict[tuple[str, str], bytes] = {}
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.address: tuple[str, int] = self._listener.getsockname()[:2]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=_Session(self, conn).run, daemon=True).start()

    def close(self) -> None:
        self._listener.close()

    def changed(self) -> None:
        self.listings.clear()

    def entries(self, path: str) -> list[tuple[str, int | None]]:
        """(name, size) for each entry directly under path; size is None for a directory."""
        found = [
            (posixpath.basename(d), None)
            for d in self.dirs
            if d != "/" and posixpath.dirname(d) == path
        ]
        found += [
            (posixpath.basename(f), len(data))
            for f, data in self.files.items()
            if posixpath.dirname(f) == path
        ]
        return sorted(found)

    def listing(self, verb: str, path: str) -> bytes:
        key = (verb, path)
        if key not in self.listings:
            lines = []
            for name, size in self.entries(path):
                if verb == "NLST":
                    lines.append(name)
                elif verb == "LIST":
                    mode = "drwxr-xr-x" if size is None else "-rw-r--r--"
                    lines.append(f"{mode} 1 owner group {size or 0:>10} Jan 01 00:00 {name}")
                else:
                    kind = "dir" if size is None else "file"
                    lines.append(f"type={kind};size={size or 0}; {name}")
            self.listings[key] = "".join(line + "\r\n" for line in lines).encode("utf-8")
        return self.listings[key]


class _Session:
    """One control connection."""

    def __init__(self, server: FakeFTPServer, conn: socket.socket) -> None:
        self.server = server
        self.conn = conn
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_OOBINLINE, 1)
        self.cwd = "/"
        self.passive: socket.socket | None = None
        self.active: tuple[str, int] | None = None
        self.rest = 0
        self.rename_from: str | None = None
        self.buffer = bytearray(65536)

    def reply(self, text: str) -> None:
        self.conn.sendall(text.encode("utf-8") + b"\r\n")

    def resolve(self, arg: str) -> str:
        return posixpath.normpath(posixpath.join(self.cwd, arg)) if arg else self.cwd

    def run(self) -> None:
        reader = self.conn.makefile("rb")
        with self.conn, reader, contextlib.suppress(OSError):
            self.reply("220 Fake FTP server ready")
            for raw in reader:
                line = raw.decode("utf-8").rstrip("\r\n")
                self.server.commands.append(line)
                verb, _, arg = line.partition(" ")
                handler = getattr(self, "do_" + verb.upper(), None)
                if verb.upper() in self.server.replies:
                    self.reply(self.server.replies[verb.upper()])
                elif handler is None:
                    self.reply(f"502 {verb} not implemented")
                elif handler(arg) is False:
                    return

    # Session and replies

    def do_USER(self, arg: str) -> None:
        self.reply("331 Password required")

    def do_PASS(self, arg: str) -> None:
        self.reply("230 Logged in")

    def do_ACCT(self, arg: str) -> None:
        self.reply("230 Account accepted")

    def do_NOOP(self, arg: str) -> None:
        self.reply("200 NOOP ok")

    def do_TYPE(self, arg: str) -> None:
        self.reply(f"200 Type set to {arg}")

    def do_OPTS(self, arg: str) -> None:
        self.reply("200 OPTS ok")

    def do_QUIT(self, arg: str) -> bool:
        self.reply("221 Goodbye")
        return False

    def do_ABOR(self, arg: str) -> None:
        self.reply("225 No transfer to abort")

    def do_STAT(self, arg: str) -> None:
        body = "".join(f" line {index}\r\n" for index in range(self.server.stat_lines))
        self.conn.sendall(f"211-Status\r\n{body}211 End\r\n".encode())

    def do_SITE(self, arg: str) -> None:
        """`SITE REPLY <text>` answers with `<text>`, so a test can script any reply."""
        verb, _, text = arg.partition(" ")
        self.reply(text if verb.upper() == "REPLY" else "502 SITE command not implemented")

    def do_AUTH(self, arg: str) -> None:
        self.reply(f"234 AUTH {arg} ok")

    def do_PBSZ(self, arg: str) -> None:
        self.reply("200 PBSZ=0")

    def do_PROT(self, arg: str) -> None:
        self.reply(f"200 Protection level set to {arg}")

    def do_CCC(self, arg: str) -> None:
        self.reply("200 Clear command channel")

    # Directories and files

    def do_PWD(self, arg: str) -> None:
        quoted = self.cwd.replace('"', '""')
        self.reply(f'257 "{quoted}" is the current directory')

    def do_CWD(self, arg: str) -> None:
        path = self.resolve(arg)
        if path not in self.server.dirs:
            return self.reply(f"550 {arg}: No such directory")
        self.cwd = path
        self.reply("250 Directory changed")

    def do_CDUP(self, arg: str) -> None:
        self.cwd = posixpath.dirname(self.cwd)
        self.reply("250 Directory changed")

    def do_MKD(self, arg: str) -> None:
        path = self.resolve(arg)
        self.server.dirs.add(path)
        self.server.changed()
        quoted = path.replace('"', '""')
        self.reply(f'257 "{quoted}" created')

    def do_RMD(self, arg: str) -> None:
        path = self.resolve(arg)
        if path not in self.server.dirs or self.server.entries(path):
            return self.reply(f"550 {arg}: Cannot remove")
        self.server.dirs.discard(path)
        self.server.changed()
        self.reply("250 Directory removed")

    def do_DELE(self, arg: str) -> None:
        if self.server.files.pop(self.resolve(arg), None) is None:
            return self.reply(f"550 {arg}: No such file")
        self.server.changed()
        self.reply("250 Deleted")

    def do_RNFR(self, arg: str) -> None:
        path = self.resolve(arg)
        if path not in self.server.files:
            return self.reply(f"550 {arg}: No such file")
        self.rename_from = path
        self.reply("350 Ready for RNTO")

    def do_RNTO(self, arg: str) -> None:
        assert self.rename_from is not None
        self.server.files[self.resolve(arg)] = self.server.files.pop(self.rename_from)
        self.rename_from = None
        self.server.changed()
        self.reply("250 Renamed")

    def do_SIZE(self, arg: str) -> None:
        data = self.server.files.get(self.resolve(arg))
        if data is None:
            return self.reply(f"550 {arg}: No such file")
        self.reply(f"213 {len(data)}")

    def do_REST(self, arg: str) -> None:
        self.rest = int(arg)
        self.reply(f"350 Restarting at {arg}")

    # Data connections

    def do_PASV(self, arg: str) -> None:
        self.passive = socket.create_server(("127.0.0.1", 0))
        port = self.passive.getsockname()[1]
        self.reply(f"227 Entering Passive Mode (127,0,0,1,{port >> 8},{port & 255})")

    def do_PORT(self, arg: str) -> None:
        numbers = arg.split(",")
        self.active = (".".join(numbers[:4]), int(numbers[4]) * 256 + int(numbers[5]))
        self.reply("200 PORT command successful")

    def open_data(self) -> socket.socket:
        self.server.data_connections += 1
        if self.passive is not None:
            listener, self.passive = self.passive, None
            with listener:
                return listener.accept()[0]
        assert self.active is not None
        return socket.create_connection(self.active)

    def send_data(self, payload: bytes | memoryview, size: int | None = None) -> None:
        self.reply("150 Opening data connection" + ("" if size is None else f" ({size} bytes)"))
        try:
            with self.open_data() as data:
                data.sendall(payload)
        except OSError:
            return self.reply("426 Connection closed; transfer aborted")
        self.reply("226 Transfer complete")

    def do_RETR(self, arg: str) -> None:
        data = self.server.files.get(self.resolve(arg))
        if data is None:
            return self.reply(f"550 {arg}: No such file")
        offset, self.rest = self.rest, 0
        self.send_data(memoryview(data)[offset:], len(data) - offset)

    def do_STOR(self, arg: str) -> None:
        path = self.resolve(arg)
        offset, self.rest = self.rest, 0
        self.reply("150 Ok to send data")
        chunks: list[bytes] = []
        with self.open_data() as data:
            while count := data.recv_into(self.buffer):
                self.server.uploaded += count
                if self.server.keep_uploads:
                    chunks.append(bytes(self.buffer[:count]))
        if self.server.keep_uploads:
            kept = self.server.files.get(path, b"")[:offset]
            self.server.files[path] = kept + b"".join(chunks)
            self.server.changed()
        self.reply("226 Transfer complete")

    def listing(self, verb: str, arg: str) -> None:
        path = self.resolve(arg)
        if path not in self.server.dirs:
            return self.reply(f"550 {arg}: No such directory")
        self.send_data(self.server.listing(verb, path))

    def do_NLST(self, arg: str) -> None:
        self.listing("NLST", arg)

    def do_LIST(self, arg: str) -> None:
        self.listing("LIST", arg)

    def do_MLSD(self, arg: str) -> None:
        self.listing("MLSD", arg)


EXAMPLE_HOST = "ftp.example.com"


def example_files() -> dict[str, bytes]:
    """The files the page's examples find on `ftp.example.com`."""
    return {
        "/pub/readme.txt": b"Welcome to the example archive.\r\nFiles are in /pub.\r\n",
        "/pub/archive.bin": bytes(range(256)) * 4096,
        "/pub/notes.txt": b"one\r\ntwo\r\nthree\r\n",
    }


def install_fake_network() -> FakeFTPServer:
    """Route `ftp.example.com` to a `FakeFTPServer`, and let `FTP_TLS` wrap
    without a handshake. Used as the prelude of the page's connecting examples."""
    server = FakeFTPServer(example_files(), dirs=("/upload",))
    original = socket.create_connection

    def create_connection(address: tuple[str, int], *args: Any, **kwargs: Any) -> socket.socket:
        if address[0] == EXAMPLE_HOST:
            address = server.address
        return original(address, *args, **kwargs)

    socket.create_connection = create_connection  # type: ignore[assignment]
    ssl.SSLContext.wrap_socket = lambda self, sock, *args, **kwargs: sock  # type: ignore[method-assign]
    return server


# --- Fixtures ------------------------------------------------------------------------------


@pytest.fixture
def server() -> Iterator[FakeFTPServer]:
    fake = FakeFTPServer(example_files(), dirs=("/upload",))
    yield fake
    fake.close()


@pytest.fixture
def ftp(server: FakeFTPServer) -> Iterator[ftplib.FTP]:
    client = ftplib.FTP()
    client.connect(*server.address)
    client.login()
    yield client
    client.close()


LISTED_NAMES = 20_000


@pytest.fixture(scope="module")
def big_listing() -> Iterator[tuple[FakeFTPServer, ftplib.FTP]]:
    """A logged-in client of a server with 20,000 files in `/big`, every
    listing of it rendered and fetched once."""
    fake = FakeFTPServer({f"/big/file{index:06d}.txt": b"" for index in range(LISTED_NAMES)})
    client = ftplib.FTP()
    client.connect(*fake.address)
    client.login()
    client.nlst("/big")
    client.dir("/big", lambda line: None)
    list(client.mlsd("/big"))
    yield fake, client
    client.close()
    fake.close()


def text_file(lines: int) -> bytes:
    return b"".join(b"line %07d " % index + b"y" * 60 + b"\r\n" for index in range(lines))


# --- Transfers -----------------------------------------------------------------------------


class TestBinaryTransfersHoldOneBlock:
    """`retrbinary` and `storbinary` | O(b) | O(k): each block is handed on
    before the next is read, so the peak follows `blocksize`, not the file."""

    SIZE = 8_000_000

    @pytest.fixture
    def big(self) -> Iterator[tuple[FakeFTPServer, ftplib.FTP]]:
        fake = FakeFTPServer({"/big.bin": b"x" * self.SIZE})
        client = ftplib.FTP()
        client.connect(*fake.address)
        client.login()
        yield fake, client
        client.close()
        fake.close()

    def test_a_download_passed_on_peaks_at_a_block(
        self, big: tuple[FakeFTPServer, ftplib.FTP]
    ) -> None:
        _, client = big
        client.retrbinary("RETR /big.bin", lambda block: None)  # warm

        peak = peak_bytes(lambda: client.retrbinary("RETR /big.bin", lambda block: None))

        assert peak < 200_000, f"an 8 MB download passed on block by block peaked at {peak}"

    def test_a_download_collected_holds_the_file(
        self, big: tuple[FakeFTPServer, ftplib.FTP]
    ) -> None:
        _, client = big
        blocks: list[bytes] = []

        peak = peak_bytes(lambda: client.retrbinary("RETR /big.bin", blocks.append))

        assert sum(map(len, blocks)) == self.SIZE
        assert peak > self.SIZE, f"collecting an 8 MB download peaked at only {peak}"

    def test_the_peak_follows_blocksize(self, big: tuple[FakeFTPServer, ftplib.FTP]) -> None:
        _, client = big
        client.retrbinary("RETR /big.bin", lambda block: None, blocksize=1 << 20)

        peak = peak_bytes(
            lambda: client.retrbinary("RETR /big.bin", lambda block: None, blocksize=1 << 20)
        )

        assert 1 << 20 < peak < 4 << 20, f"a 1 MiB blocksize peaked at {peak}"

    def test_blocks_are_at_most_blocksize_and_arrive_whole(self, ftp: ftplib.FTP) -> None:
        blocks: list[bytes] = []

        ftp.retrbinary("RETR /pub/archive.bin", blocks.append, blocksize=1000)

        assert b"".join(blocks) == example_files()["/pub/archive.bin"]
        assert max(map(len, blocks)) <= 1000
        assert len(blocks) >= len(example_files()["/pub/archive.bin"]) // 1000

    def test_an_upload_peaks_at_a_block(self, big: tuple[FakeFTPServer, ftplib.FTP]) -> None:
        fake, client = big
        fake.keep_uploads = False
        source = io.BytesIO(b"x" * self.SIZE)
        client.storbinary("STOR /sink", source)  # warm
        source.seek(0)
        fake.uploaded = 0

        peak = peak_bytes(lambda: client.storbinary("STOR /sink", source))

        assert fake.uploaded == self.SIZE
        assert peak < 200_000, f"an 8 MB upload from a file object peaked at {peak}"

    def test_an_upload_reads_and_sends_a_block_at_a_time(
        self, ftp: ftplib.FTP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []
        source = io.BytesIO(b"x" * 25_000)

        class RecordingFile:
            def read(self, size: int) -> bytes:
                events.append(f"read {size}")
                return source.read(size)

        class RecordingSocket:
            def __init__(self, sock: socket.socket) -> None:
                self.sock = sock

            def sendall(self, data: bytes) -> None:
                events.append(f"send {len(data)}")
                self.sock.sendall(data)

            def __enter__(self) -> RecordingSocket:
                return self

            def __exit__(self, *args: object) -> None:
                self.sock.close()

        transfercmd = ftp.transfercmd
        monkeypatch.setattr(ftp, "transfercmd", lambda *a: RecordingSocket(transfercmd(*a)))

        ftp.storbinary(
            "STOR /upload/x.bin",
            RecordingFile(),  # type: ignore[arg-type]
            blocksize=10_000,
            callback=lambda block: events.append(f"callback {len(block)}"),
        )

        assert events == [
            "read 10000",
            "send 10000",
            "callback 10000",
            "read 10000",
            "send 10000",
            "callback 10000",
            "read 10000",
            "send 5000",
            "callback 5000",
            "read 10000",
        ]

    def test_rest_moves_only_the_missing_bytes(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        data = example_files()["/pub/archive.bin"]
        blocks: list[bytes] = []

        ftp.retrbinary("RETR /pub/archive.bin", blocks.append, rest=1_000_000)

        assert b"".join(blocks) == data[1_000_000:]
        assert "REST 1000000" in server.commands


class TestLineModeHoldsOneLine:
    """`retrlines`, `storlines` and `dir` | O(b) | O(l): one line at a time,
    each read with a cap of 8,192 - characters, line ending included, for a
    download, and bytes for an upload."""

    def test_the_peak_does_not_follow_the_file(self) -> None:
        fake = FakeFTPServer({"/small.txt": text_file(10_000), "/large.txt": text_file(200_000)})
        client = ftplib.FTP()
        client.connect(*fake.address)
        client.login()
        peaks = []
        for name in ("/small.txt", "/large.txt"):
            client.retrlines(f"RETR {name}", lambda line: None)  # warm
            peaks.append(
                peak_bytes(lambda n=name: client.retrlines(f"RETR {n}", lambda line: None))
            )
        client.close()
        fake.close()

        assert peaks[1] < 1_000_000, f"a 15 MB line-mode download peaked at {peaks[1]}"
        assert peaks[1] < peaks[0] * 2, f"20x the lines moved the peak from {peaks}"

    def test_an_upload_peaks_at_a_line(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        server.keep_uploads = False
        source = io.BytesIO(text_file(200_000))
        ftp.storlines("STOR /sink", source)  # warm
        source.seek(0)
        server.uploaded = 0

        peak = peak_bytes(lambda: ftp.storlines("STOR /sink", source))

        assert server.uploaded == len(source.getvalue())
        assert peak < 1_000_000, f"a 15 MB line-mode upload peaked at {peak}"

    def test_line_endings_are_stripped_and_the_default_prints(
        self, server: FakeFTPServer, ftp: ftplib.FTP, capsys: pytest.CaptureFixture[str]
    ) -> None:
        server.files["/mixed.txt"] = b"a\r\nb\nc\r\n"
        lines: list[str] = []

        ftp.retrlines("RETR /mixed.txt", lines.append)
        ftp.retrlines("RETR /mixed.txt")

        assert lines == ["a", "b", "c"]
        assert capsys.readouterr().out == "a\nb\nc\n"

    def test_storlines_needs_a_binary_file(self, ftp: ftplib.FTP) -> None:
        with pytest.raises(TypeError):
            ftp.storlines("STOR /upload/text.txt", io.StringIO("a\n"))  # type: ignore[arg-type]

    def test_storlines_sends_crlf_endings(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        ftp.storlines("STOR /upload/lines.txt", io.BytesIO(b"a\nb\r\nc"))

        assert server.files["/upload/lines.txt"] == b"a\r\nb\r\nc\r\n"

    @pytest.mark.parametrize(
        ("line", "raises"),
        [
            (b"x" * 8_191 + b"\n", False),
            (b"x" * 8_191 + b"\r\n", False),
            (b"x" * 8_192 + b"\n", True),
            ("\u00e9".encode() * 4_096 + b"\n", False),
        ],
    )
    def test_a_downloaded_line_over_the_cap_raises(
        self, server: FakeFTPServer, ftp: ftplib.FTP, line: bytes, raises: bool
    ) -> None:
        server.files["/long.txt"] = line
        lines: list[str] = []

        if raises:
            with pytest.raises(ftplib.Error, match="got more than 8192 bytes"):
                ftp.retrlines("RETR /long.txt", lines.append)
        else:
            ftp.retrlines("RETR /long.txt", lines.append)
            assert lines == [line.decode().rstrip("\r\n")]

    @pytest.mark.parametrize(
        ("line", "raises"),
        [
            (b"x" * 8_191 + b"\n", False),
            (b"x" * 8_191 + b"\r\n", True),
            (b"x" * 8_192 + b"\n", True),
            ("\u00e9".encode() * 4_096 + b"\n", True),
        ],
    )
    def test_an_uploaded_line_over_the_cap_raises(
        self, server: FakeFTPServer, ftp: ftplib.FTP, line: bytes, raises: bool
    ) -> None:
        source = io.BytesIO(line)

        if raises:
            with pytest.raises(ftplib.Error, match="got more than 8192 bytes"):
                ftp.storlines("STOR /upload/long.txt", source)
            assert ftp.voidresp().startswith("226")
            assert server.files["/upload/long.txt"] == b""
        else:
            ftp.storlines("STOR /upload/long.txt", source)
            assert server.files["/upload/long.txt"] == line.rstrip(b"\r\n") + b"\r\n"

    def test_a_reply_line_over_the_cap_raises(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        server.replies["NOOP"] = "200 " + "x" * 9_000

        with pytest.raises(ftplib.Error, match="got more than 8192 bytes"):
            ftp.sendcmd("NOOP")

    def test_the_cap_is_the_base_of_the_error_classes(self) -> None:
        for error in (ftplib.error_reply, ftplib.error_temp, ftplib.error_perm, ftplib.error_proto):
            assert issubclass(error, ftplib.Error)


class TestTransferCommands:
    """`transfercmd` and `ntransfercmd` | O(c + r): the data socket is handed
    back, and the caller collects the final reply."""

    def test_transfercmd_returns_the_data_socket(self, ftp: ftplib.FTP) -> None:
        ftp.voidcmd("TYPE I")
        with ftp.transfercmd("RETR /pub/notes.txt") as conn:
            received = b""
            while chunk := conn.recv(1024):
                received += chunk

        assert received == example_files()["/pub/notes.txt"]
        assert ftp.voidresp().startswith("226")

    def test_binary_and_line_transfers_set_the_type(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        sent = len(server.commands)
        ftp.retrbinary("RETR /pub/notes.txt", lambda block: None)
        ftp.retrlines("RETR /pub/notes.txt", lambda line: None)

        assert server.commands[sent:] == [
            "TYPE I",
            "PASV",
            "RETR /pub/notes.txt",
            "TYPE A",
            "PASV",
            "RETR /pub/notes.txt",
        ]

    def test_ntransfercmd_reports_the_size_in_a_150_reply(self, ftp: ftplib.FTP) -> None:
        conn, size = ftp.ntransfercmd("RETR /pub/notes.txt")
        conn.close()
        ftp.voidresp()
        listing, no_size = ftp.ntransfercmd("NLST /pub")
        listing.close()
        ftp.voidresp()

        assert size == len(example_files()["/pub/notes.txt"])
        assert no_size is None

    def test_a_transfer_cut_short_leaves_a_reply_to_collect(self, ftp: ftplib.FTP) -> None:
        ftp.voidcmd("TYPE I")
        with ftp.transfercmd("RETR /pub/archive.bin") as conn:
            assert conn.recv(65536)

        reply = ""
        try:
            reply = ftp.voidresp()
        except ftplib.error_temp as error:
            reply = str(error)
        assert reply[:3] in {"226", "426"}
        assert ftp.sendcmd("NOOP").startswith("200"), "the control connection is back in step"


# --- Listings ------------------------------------------------------------------------------


class TestListings:
    """`nlst` | O(b) | O(b), `dir` | O(b) | O(l), `mlsd` | O(b) | O(b): what
    each holds, measured over 20,000 names."""

    NAMES = LISTED_NAMES

    @pytest.fixture
    def big(
        self, big_listing: tuple[FakeFTPServer, ftplib.FTP]
    ) -> tuple[FakeFTPServer, ftplib.FTP]:
        return big_listing

    def test_nlst_holds_every_name(self, big: tuple[FakeFTPServer, ftplib.FTP]) -> None:
        fake, client = big
        names: list[str] = []

        peak = peak_bytes(lambda: names.extend(client.nlst("/big")))

        assert len(names) == self.NAMES
        assert peak > len(fake.listing("NLST", "/big")), f"nlst peaked at {peak}"

    def test_dir_passes_each_line_on(self, big: tuple[FakeFTPServer, ftplib.FTP]) -> None:
        fake, client = big
        count = 0

        def count_line(line: str) -> None:
            nonlocal count
            count += 1

        peak = peak_bytes(lambda: client.dir("/big", count_line))

        assert count == self.NAMES
        assert peak < len(fake.listing("LIST", "/big")) / 4, f"dir peaked at {peak}"

    def test_dir_prints_by_default(
        self, ftp: ftplib.FTP, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert ftp.dir("/pub") is None

        assert capsys.readouterr().out.count("\n") == 3

    def test_mlsd_sends_nothing_until_the_first_next(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        sent = len(server.commands)

        entries = ftp.mlsd("/pub", facts=["type", "size"])
        assert len(server.commands) == sent

        name, facts = next(entries)
        assert server.commands[sent] == "OPTS MLST type;size;"
        assert "MLSD /pub" in server.commands[sent:]
        assert (name, facts) == ("archive.bin", {"type": "file", "size": "1048576"})

    def test_mlsd_reads_the_whole_listing_on_the_first_next(
        self, big: tuple[FakeFTPServer, ftplib.FTP]
    ) -> None:
        fake, client = big
        entries = client.mlsd("/big")

        peak = peak_bytes(lambda: next(entries))
        commands = len(fake.commands)
        rest = list(entries)

        assert len(rest) == self.NAMES - 1
        assert len(fake.commands) == commands, "the other entries needed no command"
        assert peak > len(fake.listing("MLSD", "/big")), f"the first next() peaked at {peak}"

    def test_the_first_next_finishes_the_transfer(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        """If the listing were still being read, the next command's reply
        would be the listing's `226`, not the `200` for `NOOP`."""
        entries = ftp.mlsd("/pub")
        next(entries)

        assert ftp.sendcmd("NOOP").startswith("200")
        assert len(list(entries)) == 2


class TestEachTransferOpensADataConnection:
    """Every transfer and listing opens a data connection of its own, so
    mirroring n files costs n + 1."""

    def test_one_data_connection_per_call(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        calls: list[Callable[[], Any]] = [
            lambda: ftp.retrbinary("RETR /pub/notes.txt", lambda block: None),
            lambda: ftp.retrlines("RETR /pub/notes.txt", lambda line: None),
            lambda: ftp.storbinary("STOR /upload/a", io.BytesIO(b"a")),
            lambda: ftp.storlines("STOR /upload/b", io.BytesIO(b"b\n")),
            lambda: ftp.nlst("/pub"),
            lambda: ftp.dir("/pub", lambda line: None),
            lambda: list(ftp.mlsd("/pub")),
        ]
        for count, call in enumerate(calls, start=1):
            call()
            assert server.data_connections == count

    def test_mirroring_n_files_opens_n_plus_one(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        ftp.cwd("/pub")
        names = ftp.nlst()
        for name in names:
            ftp.retrbinary(f"RETR {name}", lambda block: None)

        assert server.data_connections == len(names) + 1 == 4

    def test_active_mode_has_the_server_connect_back(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        ftp.set_pasv(False)
        lines: list[str] = []

        ftp.retrlines("RETR /pub/notes.txt", lines.append)

        assert lines == ["one", "two", "three"]
        assert any(command.startswith("PORT ") for command in server.commands)
        assert not any(command == "PASV" for command in server.commands)


# --- Commands ------------------------------------------------------------------------------


class TestCommandsAndReplies:
    """Each command is one line out and one reply back: O(c + r)."""

    def test_sendcmd_returns_the_reply(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        server.replies["SITE"] = "350 Need more"

        assert ftp.sendcmd("SITE X") == "350 Need more"

    @pytest.mark.parametrize(
        ("reply", "error"),
        [
            ("450 Busy", ftplib.error_temp),
            ("550 Denied", ftplib.error_perm),
            ("600 Unknown", ftplib.error_proto),
        ],
    )
    def test_error_replies_raise(
        self, server: FakeFTPServer, ftp: ftplib.FTP, reply: str, error: type[Exception]
    ) -> None:
        server.replies["SITE"] = reply

        with pytest.raises(error, match=reply):
            ftp.sendcmd("SITE X")

    def test_voidcmd_raises_on_anything_but_2xx(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        server.replies["SITE"] = "350 Need more"

        with pytest.raises(ftplib.error_reply, match="350"):
            ftp.voidcmd("SITE X")
        assert ftp.voidcmd("NOOP").startswith("200")

    def test_a_multiline_reply_comes_back_whole(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        server.stat_lines = 3

        assert ftp.sendcmd("STAT") == "211-Status\n line 0\n line 1\n line 2\n211 End"

    @pytest.mark.timing
    def test_a_multiline_reply_is_read_in_linear_time(self) -> None:
        """Each reply line is appended to the text read so far; 16x the lines
        costs 16x if that is linear and 256x if it copies the whole each time.
        The reply is read from an in-memory file, so only the client is timed."""

        class NullSocket:
            def sendall(self, data: bytes) -> None:
                pass

        def reply_of(lines: int) -> str:
            body = "".join(f" line {index:07d}\r\n" for index in range(lines))
            return f"211-Status\r\n{body}211 End\r\n"

        client = ftplib.FTP()
        client.sock = NullSocket()  # type: ignore[assignment]
        durations = []
        for lines in (8_000, 128_000):
            reply = reply_of(lines)

            def read_reply(text: str = reply) -> str:
                client.file = io.StringIO(text)
                return client.sendcmd("STAT")

            assert read_reply().count("\n") == lines + 1
            durations.append(best_ns(read_reply, repeats=9))
        client.sock = None

        ratio = durations[1] / durations[0]
        assert 4 < ratio < 64, f"16x the lines cost x{ratio:.1f}: {durations} ns"

    def test_directory_commands(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        assert ftp.mkd('/upload/a"b') == '/upload/a"b'
        ftp.cwd('/upload/a"b')
        assert ftp.pwd() == '/upload/a"b'

        sent = len(server.commands)
        ftp.cwd("..")
        assert server.commands[sent:] == ["CDUP"]
        assert ftp.pwd() == "/upload"

        assert ftp.rmd('a"b').startswith("250")
        assert '/upload/a"b' not in server.dirs

    def test_file_commands(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        assert ftp.size("/pub/notes.txt") == len(example_files()["/pub/notes.txt"])

        sent = len(server.commands)
        ftp.rename("/pub/notes.txt", "/pub/moved.txt")
        assert server.commands[sent:] == ["RNFR /pub/notes.txt", "RNTO /pub/moved.txt"]

        assert ftp.delete("/pub/moved.txt").startswith("250")
        assert "/pub/moved.txt" not in server.files
        with pytest.raises(ftplib.error_perm, match="550"):
            ftp.delete("/pub/moved.txt")


class TestConnections:
    """Connecting, logging in, leaving and closing."""

    def test_ftp_without_a_host_does_not_connect(self) -> None:
        client = ftplib.FTP()

        assert client.sock is None

    def test_ftp_with_host_and_user_connects_and_logs_in(
        self, server: FakeFTPServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = socket.create_connection

        def to_fake(address: tuple[str, int], *args: Any, **kwargs: Any) -> socket.socket:
            return original(server.address if address[0] == "example" else address, *args, **kwargs)

        monkeypatch.setattr(socket, "create_connection", to_fake)

        with ftplib.FTP("example") as connected:
            assert connected.getwelcome() == "220 Fake FTP server ready"
            assert server.commands == []
        server.commands.clear()
        with ftplib.FTP("example", "alice", "secret"):
            assert server.commands == ["USER alice", "PASS secret"]

    def test_connect_returns_the_welcome_getwelcome_keeps(self, server: FakeFTPServer) -> None:
        client = ftplib.FTP()

        welcome = client.connect(*server.address)

        assert welcome == "220 Fake FTP server ready"
        assert client.getwelcome() is welcome
        client.close()

    def test_login_sends_pass_and_acct_only_when_asked(
        self, server: FakeFTPServer, ftp: ftplib.FTP
    ) -> None:
        assert server.commands == ["USER anonymous", "PASS anonymous@"]

        server.replies["PASS"] = "332 Need account"
        ftp.login("bob", "pw", "acct")
        assert server.commands[2:] == ["USER bob", "PASS pw", "ACCT acct"]

        server.replies["USER"] = "230 No password needed"
        ftp.login("dave", "pw", "acct")
        assert server.commands[5:] == ["USER dave"]

    def test_leaving_a_with_block_quits(self, server: FakeFTPServer) -> None:
        with ftplib.FTP() as client:
            client.connect(*server.address)

        assert server.commands == ["QUIT"]
        assert client.sock is None

    def test_leaving_ignores_a_connection_already_gone(self, server: FakeFTPServer) -> None:
        with ftplib.FTP() as client:
            client.connect(*server.address)
            client.sendcmd("QUIT")  # the server closes its end

        assert client.sock is None

    def test_quit_raises_on_an_error_close_does_not(self, server: FakeFTPServer) -> None:
        server.replies["QUIT"] = "500 No"
        client = ftplib.FTP()
        client.connect(*server.address)

        with pytest.raises(ftplib.error_perm):
            client.quit()
        assert client.sock is not None, "quit() closed despite the error"
        sent = len(server.commands)
        client.close()
        client.close()

        assert client.sock is None
        assert len(server.commands) == sent

    def test_abort_sends_abor(self, server: FakeFTPServer, ftp: ftplib.FTP) -> None:
        assert ftp.abort().startswith("225")
        assert server.commands[-1] == "ABOR"

    def test_debug_levels(self, ftp: ftplib.FTP, capsys: pytest.CaptureFixture[str]) -> None:
        ftp.set_debuglevel(1)
        ftp.login("carol", "hunter2")
        first = capsys.readouterr().out
        ftp.set_debuglevel(2)
        ftp.sendcmd("NOOP")
        second = capsys.readouterr().out

        assert "*cmd* 'USER carol'" in first and "*resp*" in first
        assert "hunter2" not in first and "'PASS *******'" in first
        assert "*put*" not in first and "*get*" not in first
        assert "*put* 'NOOP\\r\\n'" in second and "*get*" in second


# --- FTP_TLS -------------------------------------------------------------------------------


class FakeTLSSocket:
    """Stands in for `ssl.SSLSocket` so `FTP_TLS` can run without a handshake."""

    def __init__(self, sock: socket.socket) -> None:
        self.plain = sock

    def __getattr__(self, name: str) -> Any:
        return getattr(self.plain, name)

    def __enter__(self) -> FakeTLSSocket:
        return self

    def __exit__(self, *args: object) -> None:
        self.plain.close()

    def unwrap(self) -> socket.socket:
        return self.plain


class FakeContext:
    """Records each socket it is asked to wrap."""

    protocol = ssl.PROTOCOL_TLS_CLIENT

    def __init__(self) -> None:
        self.wrapped: list[socket.socket] = []

    def wrap_socket(self, sock: socket.socket, server_hostname: str | None = None) -> Any:
        self.wrapped.append(sock)
        return FakeTLSSocket(sock)


class TestFTPTLS:
    """`FTP_TLS` secures the control connection at login and the data
    connections only after `prot_p()`, one wrap per transfer."""

    @pytest.fixture
    def tls(
        self, server: FakeFTPServer, monkeypatch: pytest.MonkeyPatch
    ) -> Iterator[tuple[ftplib.FTP_TLS, FakeContext]]:
        monkeypatch.setattr(ssl, "SSLSocket", FakeTLSSocket)
        context = FakeContext()
        client = ftplib.FTP_TLS(context=context)  # type: ignore[arg-type]
        client.connect(*server.address)
        yield client, context
        client.close()

    def test_login_secures_the_control_connection_first(
        self, server: FakeFTPServer, tls: tuple[ftplib.FTP_TLS, FakeContext]
    ) -> None:
        client, context = tls

        client.login()

        assert server.commands == ["AUTH TLS", "USER anonymous", "PASS anonymous@"]
        assert isinstance(client.sock, FakeTLSSocket)
        assert len(context.wrapped) == 1
        with pytest.raises(ValueError, match="Already using TLS"):
            client.auth()

    def test_login_with_secure_false_stays_clear(
        self, server: FakeFTPServer, tls: tuple[ftplib.FTP_TLS, FakeContext]
    ) -> None:
        client, context = tls

        client.login(secure=False)

        assert server.commands == ["USER anonymous", "PASS anonymous@"]
        assert context.wrapped == []

    def test_data_connections_are_wrapped_only_after_prot_p(
        self, server: FakeFTPServer, tls: tuple[ftplib.FTP_TLS, FakeContext]
    ) -> None:
        client, context = tls
        client.login()

        client.nlst("/pub")
        assert len(context.wrapped) == 1, "a data connection was wrapped before prot_p()"

        client.prot_p()
        assert server.commands[-2:] == ["PBSZ 0", "PROT P"]
        for expected in (2, 3, 4):
            client.retrbinary("RETR /pub/notes.txt", lambda block: None)
            assert len(context.wrapped) == expected

        client.prot_c()
        assert server.commands[-1] == "PROT C"
        client.nlst("/pub")
        assert len(context.wrapped) == 4

    def test_ccc_returns_the_control_connection_to_clear_text(
        self, server: FakeFTPServer, tls: tuple[ftplib.FTP_TLS, FakeContext]
    ) -> None:
        client, _ = tls
        client.login()

        assert client.ccc().startswith("200")

        assert server.commands[-1] == "CCC"
        assert isinstance(client.sock, socket.socket)
        with pytest.raises(ValueError, match="not using TLS"):
            client.ccc()

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="removed in 3.12")
    def test_ssl_version_exists_before_312(self) -> None:
        assert ftplib.FTP_TLS.ssl_version == ssl.PROTOCOL_TLS_CLIENT  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="removed in 3.12")
    def test_312_drops_ssl_version_keyfile_and_certfile(self) -> None:
        assert not hasattr(ftplib.FTP_TLS, "ssl_version")
        with pytest.raises(TypeError):
            ftplib.FTP_TLS(keyfile="key.pem")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            ftplib.FTP_TLS(certfile="cert.pem")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            ftplib.FTP_TLS("", "", "", "", FakeContext())  # type: ignore[misc]


class TestExceptions:
    """The four reply errors and `all_errors`."""

    def test_all_errors(self) -> None:
        assert ftplib.all_errors == (ftplib.Error, OSError, EOFError, ssl.SSLError)
        for error in (ftplib.error_reply, ftplib.error_temp, ftplib.error_perm, ftplib.error_proto):
            assert issubclass(error, ftplib.all_errors)


# --- The page's examples -------------------------------------------------------------------


PRELUDE = (
    "import sys\n"
    f"sys.path.insert(0, {str(pathlib.Path(__file__).parent)!r})\n"
    "import test_ftplib_complexity\n"
    "test_ftplib_complexity.install_fake_network()\n"
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
    prelude = PRELUDE if EXAMPLE_HOST in source else ""
    script.write_text(prelude + source, encoding="utf-8")
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
    """Each block runs in its own subprocess and working directory; the ones
    that connect reach a `FakeFTPServer` through the prelude."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

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
        line, source = next((n, s) for n, s in _blocks() if "lines == ['one', 'two'" in s)
        mutated = source.replace("lines == ['one', 'two', 'three']", "lines == ['one']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
