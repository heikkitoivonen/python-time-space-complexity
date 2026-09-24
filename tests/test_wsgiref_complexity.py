"""Tests for docs/stdlib/wsgiref.md.

The page prices the package a request at a time: the handler builds an environ
of e entries, validates h response headers, and passes each of the c chunks the
application yields to the output stream before taking the next, so it never
holds the r-byte body. `Headers` is a list scanned name by name. Those claims
are settled by observation - a recording output stream, a counting header
list, a counting file, identity checks - and by traced allocation where a
space bound is the claim. The development server is exercised over loopback.

Measurement scope:

* Streaming: a recording stream and a generator application show each chunk
  written and flushed before the next is taken, one flush per chunk. A
  1,000-chunk response of one shared 10,000-byte object (10 MB in total) peaks
  under 1 MB of traced allocation through `SimpleHandler.run()`, so the body
  is not joined or copied. The handler adds `Content-Length` for a
  one-element list and `0` for an empty one, not for a two-element list or a
  generator, and keeps one the application set on a generator response.
* `start_response()` sends nothing, wraps the list it is given (a header
  added through the wrapper appears in it), and rejects a hop-by-hop header
  in last place after 1,000 others; the first `write()` sends status line and
  headers before its data, its traced peak grows more than 20x from 10 to
  10,000 headers, and a `write()` before `start_response()` raises.
* `Headers`: the wrapped list is swapped for a list subclass that counts the
  pairs its iterator yields. At 10 and 10,000 headers a missing name costs
  exactly h pairs for `get()`, `[]`, `in`, `get_all()`, `setdefault()`,
  assignment and deletion; a name in first position costs one for the three
  lookups; `add_header()` costs none. The list passed in is asserted to be the
  one mutated, `items()` a copy, and a non-str value in the last pair to be
  rejected at construction.
* `FileWrapper` over a counting file: 25,000 bytes at a 10,000-byte block are
  four `read(10000)` calls, the last returning nothing. Through
  `SimpleHandler`, whose `sendfile()` returns `False`, a wrapped file is read
  in the same blocks.
* `shift_path_info()` and `request_uri()`: traced peak grows more than 100x
  from a 10-segment `PATH_INFO` to a 10,000-segment one. `setup_testing_defaults()`
  adds the same keys to an empty environ and to one with 10,000 unrelated
  entries, and leaves existing values alone.
* Server: `WSGIServer` is an `HTTPServer` and not a `ThreadingMixIn`;
  `make_server()` calls `socket.getfqdn()` once; over loopback a request is
  answered as HTTP/1.0 with the connection closed, and a 70,000-byte request
  line gets a 414 without the application being called. `get_environ()` on a
  handler with 10 and 1,000 distinct request headers returns a copy of the
  base environ plus one `HTTP_*` entry per header; a repeated header merges
  into one comma-separated entry, and `Content-Type` and `Content-Length` go
  to `CONTENT_TYPE` and `CONTENT_LENGTH`.
* `BaseHandler`: `os_environ` does not see a variable set after import while
  `read_environ()` does; `CGIHandler` has an empty `os_environ` and reads the
  process environment on construction; `IISCGIHandler` strips a duplicated
  script name. Error output is sent when the application fails before any
  output and not after. A failure 60 calls deep logs more than two frames
  unlimited and exactly two with `traceback_limit = 2`.
* `validator()`: wrapping does not call the application; a non-str value in
  the last environ entry, a bad name in the last response header, and a
  non-bytes third chunk are each caught; a bare `bytes` return is refused.
  Unwrapped, that return gets a 500. A passing request's traced peak grows
  more than 20x from 10 to 10,000 extra environ entries at 10 headers, and
  from 10 to 10,000 response headers at 10 extra entries: `check_environ()`
  and `check_headers()` format the environ and header list into their
  assertion messages before testing the condition.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(e + h + c + r) time bounds on `run()`, `handle()`, `handle_request()`
  and `serve_forever()` are read from Lib/wsgiref/handlers.py and
  simple_server.py; the tests observe their parts (one write per chunk, one
  environ entry per header) rather than timing the whole.
* Network and resolver costs: what `socket.getfqdn()` costs depends on the
  local resolver; only that `make_server()` calls it is observed. That a slow
  application delays other clients follows from the missing `ThreadingMixIn`
  and is not raced here.
* `CGIHandler` and `IISCGIHandler` read `sys.stdin.buffer` and
  `sys.stdout.buffer`; they are constructed here, not run.
* `BaseHandler._write` and `BaseHandler._flush` are documented abstract hooks
  that the audit lists as unresolved; `SimpleHandler._write`'s O(len(data)) is
  read from source, including its retry loop on partial writes.
* `read_environ()`'s Windows branches (IIS, Apache, other servers) only run
  on Windows; no run this project performs reaches them.
* `log_exception()`'s O(f) and `demo_app()`'s O(e log e) are read from source;
  only the frame cap and the one-line-per-entry output are observed.
* `wsgiref.types` exists from 3.11; the test is skipped on 3.10.
* Header name and value lengths, environ value lengths and request bodies are
  not varied; the page prices them as O(1) or leaves them to the application.
"""

from __future__ import annotations

import http.client
import importlib
import io
import pathlib
import re
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import tracemalloc
from collections.abc import Callable, Iterable, Iterator
from http.server import HTTPServer
from typing import Any
from wsgiref import handlers, headers, simple_server, util, validate
from wsgiref.handlers import BaseCGIHandler, BaseHandler, CGIHandler, IISCGIHandler, SimpleHandler
from wsgiref.headers import Headers
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, demo_app, make_server
from wsgiref.util import (
    FileWrapper,
    application_uri,
    guess_scheme,
    is_hop_by_hop,
    request_uri,
    setup_testing_defaults,
    shift_path_info,
)
from wsgiref.validate import validator

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "wsgiref.md"
EXPECTED_BLOCKS = 8

StartResponse = Callable[..., Any]
Application = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def request_environ(**extra: Any) -> dict[str, Any]:
    environ: dict[str, Any] = dict(extra)
    setup_testing_defaults(environ)
    return environ


def run_app(
    app: Application, handler_class: type[SimpleHandler] = SimpleHandler, **extra: Any
) -> tuple[bytes, str]:
    """Run app through a handler over in-memory streams; return output and log."""
    out, err = io.BytesIO(), io.StringIO()
    handler_class(io.BytesIO(), out, err, request_environ(**extra)).run(app)
    return out.getvalue(), err.getvalue()


def text_app(body: Iterable[bytes]) -> Application:
    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        start_response("200 OK", [("Content-Type", "text/plain")])
        return body

    return app


class DiscardStream(io.BytesIO):
    """An output stream that keeps nothing."""

    def write(self, data: Any) -> int:
        return len(data)


def ignore_start_response(
    status: str, headers: list[tuple[str, str]], exc_info: Any = None
) -> Callable[[bytes], object]:
    """A `start_response` that accepts anything and discards the output."""
    return lambda data: None


class TestTheHandlerStreams:
    """`BaseHandler.run(app)` | O(e + h + c + r) | O(e + h): each chunk is
    written and flushed before the next is taken, and the body is never held."""

    def test_each_chunk_is_written_and_flushed_before_the_next_is_taken(self) -> None:
        events: list[str] = []

        class Recording(io.BytesIO):
            def write(self, data: Any) -> int:
                events.append(f"write {data!r}" if data.startswith(b"chunk") else "header")
                return len(data)

            def flush(self) -> None:
                events.append("flush")

        def app(environ: dict[str, Any], start_response: StartResponse) -> Iterator[bytes]:
            start_response("200 OK", [("Content-Type", "text/plain")])
            for index in range(3):
                events.append(f"take {index}")
                yield f"chunk{index}".encode()

        SimpleHandler(io.BytesIO(), Recording(), io.StringIO(), request_environ()).run(app)

        body_events = [event for event in events if event != "header"]
        assert body_events == [
            "take 0",
            "write b'chunk0'",
            "flush",
            "take 1",
            "write b'chunk1'",
            "flush",
            "take 2",
            "write b'chunk2'",
            "flush",
        ]

    def test_the_body_is_not_collected(self) -> None:
        chunk = b"x" * 10_000
        body = [chunk] * 1_000  # 10 MB of body, one object
        app = text_app(body)
        environ = request_environ()

        def serve() -> None:
            SimpleHandler(io.BytesIO(), DiscardStream(), io.StringIO(), dict(environ)).run(app)

        serve()  # warm
        peak = peak_bytes(serve)

        assert peak < 1_000_000, f"a 10 MB response peaked at {peak} bytes"

    @staticmethod
    def generated() -> Iterator[bytes]:
        yield b"a"
        yield b"b"

    def test_content_length_is_added_for_one_chunk_or_none(self) -> None:
        one, _ = run_app(text_app([b"ab"]))
        empty, _ = run_app(text_app([]))
        two, _ = run_app(text_app([b"a", b"b"]))
        lazy, _ = run_app(text_app(self.generated()))

        assert b"Content-Length: 2\r\n" in one
        assert b"Content-Length: 0\r\n" in empty
        assert b"Content-Length" not in two
        assert b"Content-Length" not in lazy
        assert lazy.startswith(b"HTTP/1.0 200 OK\r\n")
        assert lazy.endswith(b"\r\n\r\nab")

    def test_a_length_the_application_sets_is_kept(self) -> None:
        def app(environ: dict[str, Any], start_response: StartResponse) -> Iterator[bytes]:
            start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "2")])
            return self.generated()

        out, _ = run_app(app)

        assert out.count(b"Content-Length") == 1
        assert b"Content-Length: 2\r\n" in out

    def test_one_flush_per_chunk(self) -> None:
        class Counting(io.BytesIO):
            flushes = 0

            def flush(self) -> None:
                self.flushes += 1

        stream = Counting()
        app = text_app(b"x" for _ in range(100))

        SimpleHandler(io.BytesIO(), stream, io.StringIO(), request_environ()).run(app)

        assert stream.flushes == 100

    def test_returning_bytes_instead_of_a_list_is_a_500(self) -> None:
        out, log = run_app(text_app(b"hello"))  # type: ignore[arg-type]

        assert out.startswith(b"HTTP/1.0 500 Internal Server Error\r\n")
        assert BaseHandler.error_body in out
        assert "must be a bytes instance" in log


class TestStartResponseAndWrite:
    """`start_response()` | O(h) | O(1): wraps and checks the header list,
    sends nothing; `write()` sends the headers on its first call."""

    @staticmethod
    def handler() -> tuple[SimpleHandler, io.BytesIO]:
        out = io.BytesIO()
        handler = SimpleHandler(io.BytesIO(), out, io.StringIO(), request_environ())
        handler.setup_environ()
        return handler, out

    def test_start_response_wraps_the_list_and_sends_nothing(self) -> None:
        handler, out = self.handler()
        pairs = [("Content-Type", "text/plain")]

        write = handler.start_response("200 OK", pairs)

        wrapped: Headers = handler.headers  # type: ignore[attr-defined]
        assert out.getvalue() == b""
        assert wrapped.items() == pairs
        wrapped["X-Added"] = "1"
        assert pairs[-1] == ("X-Added", "1"), "the list was copied"
        assert write == handler.write

    def test_start_response_checks_every_pair(self) -> None:
        handler, _ = self.handler()
        pairs = [(f"X-{index}", "v") for index in range(1_000)] + [("Connection", "close")]

        with pytest.raises(AssertionError, match="Hop-by-hop"):
            handler.start_response("200 OK", pairs)

    def test_the_first_write_sends_the_headers(self) -> None:
        handler, out = self.handler()
        handler.start_response("200 OK", [("Content-Type", "text/plain")])

        handler.write(b"first")
        after_first = out.getvalue()
        handler.write(b"second")

        assert after_first.startswith(b"HTTP/1.0 200 OK\r\n")
        assert after_first.endswith(b"\r\n\r\nfirst")
        assert out.getvalue() == after_first + b"second"

    def test_first_write_memory_grows_with_header_count(self) -> None:
        peaks = []
        for count in (10, 10_000):
            handler = SimpleHandler(io.BytesIO(), DiscardStream(), io.StringIO(), request_environ())
            handler.setup_environ()
            pairs = [("Content-Type", "text/plain")]
            pairs += [(f"X-{index}", "v") for index in range(count)]
            handler.start_response("200 OK", pairs)
            peaks.append(peak_bytes(lambda handler=handler: handler.write(b"x")))

        assert peaks[1] > peaks[0] * 20, f"1,000x the headers on the first write: {peaks}"

    def test_write_before_start_response_raises(self) -> None:
        handler, _ = self.handler()

        with pytest.raises(AssertionError, match="before start_response"):
            handler.write(b"x")


class TestHandlerEnvironAndAttributes:
    """`setup_environ()` copies `os_environ`, read once at import;
    `CGIHandler` reads the process environment per construction; the class
    attributes reach the environ and the output."""

    def test_os_environ_is_a_snapshot_taken_at_import(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WSGIREF_TEST_LATE", "1")

        assert "WSGIREF_TEST_LATE" not in BaseHandler.os_environ
        assert handlers.read_environ()["WSGIREF_TEST_LATE"] == "1"

    def test_read_environ_has_one_entry_per_variable(self) -> None:
        import os

        assert set(handlers.read_environ()) == set(os.environ)

    def test_setup_environ_copies_it(self) -> None:
        seen: list[dict[str, Any]] = []

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            seen.append(environ)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b""]

        run_app(app)

        assert seen[0] is not BaseHandler.os_environ
        assert set(BaseHandler.os_environ) <= set(seen[0])

    def test_cgi_handler_reads_the_environment_when_built(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WSGIREF_TEST_CGI", "yes")
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO()))
        monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO()))

        handler = CGIHandler()

        assert CGIHandler.os_environ == {}
        assert handler.base_env["WSGIREF_TEST_CGI"] == "yes"  # type: ignore[attr-defined]

    def test_iis_handler_strips_the_duplicated_script_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SCRIPT_NAME", "/app")
        monkeypatch.setenv("PATH_INFO", "/app/users/42")
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO()))
        monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO()))

        handler = IISCGIHandler()

        assert handler.base_env["PATH_INFO"] == "/users/42"  # type: ignore[attr-defined]

    def test_base_cgi_handler_writes_a_status_line(self) -> None:
        out, _ = run_app(text_app([b"hi"]), handler_class=BaseCGIHandler)

        assert BaseCGIHandler.origin_server is False
        assert out.startswith(b"Status: 200 OK\r\n")

    def test_attributes_reach_the_environ_and_output(self) -> None:
        seen: dict[str, Any] = {}

        class Custom(SimpleHandler):
            wsgi_run_once = True
            server_software = "Probe/1"
            http_version = "1.1"

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            seen.update(environ)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b""]

        out = io.BytesIO()
        Custom(
            io.BytesIO(), out, io.StringIO(), request_environ(HTTPS="on"), multithread=False
        ).run(app)

        assert seen["wsgi.run_once"] is True
        assert seen["wsgi.multithread"] is False
        assert seen["wsgi.multiprocess"] is False
        assert seen["wsgi.url_scheme"] == "https"
        assert seen["wsgi.file_wrapper"] is FileWrapper
        assert out.getvalue().startswith(b"HTTP/1.1 200 OK\r\n")
        assert b"Server: Probe/1\r\n" in out.getvalue()

    def test_the_abstract_hooks_raise(self) -> None:
        handler = BaseHandler()

        for hook in (handler.get_stdin, handler.get_stderr, handler.add_cgi_vars):
            with pytest.raises(NotImplementedError):
                hook()
        with pytest.raises(NotImplementedError):
            handler._write(b"")  # noqa: SLF001
        with pytest.raises(NotImplementedError):
            handler._flush()  # noqa: SLF001

    def test_get_scheme_reads_https(self) -> None:
        handler = BaseHandler()
        handler.environ = {"HTTPS": "on"}  # type: ignore[attr-defined]

        assert handler.get_scheme() == "https"


class TestErrorHandling:
    """`error_output()` answers only while no header has gone out, and
    `traceback_limit` caps what `log_exception()` prints."""

    def test_a_failure_before_output_gets_the_error_page(self) -> None:
        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            raise ValueError("boom")

        out, log = run_app(app)

        assert out.startswith(b"HTTP/1.0 500 Internal Server Error\r\n")
        assert out.endswith(BaseHandler.error_body)
        assert b"Content-Type: text/plain" in out
        assert "ValueError: boom" in log

    def test_a_failure_after_output_gets_no_error_page(self) -> None:
        def app(environ: dict[str, Any], start_response: StartResponse) -> Iterator[bytes]:
            start_response("200 OK", [("Content-Type", "text/plain")])
            yield b"partial"
            raise ValueError("late")

        out, log = run_app(app)

        assert out.startswith(b"HTTP/1.0 200 OK\r\n")
        assert out.endswith(b"partial")
        assert BaseHandler.error_body not in out
        assert "ValueError: late" in log

    def test_error_output_returns_the_error_body(self) -> None:
        calls: list[tuple[Any, ...]] = []

        def recording(
            status: str, headers: list[tuple[str, str]], exc_info: Any = None
        ) -> Callable[[bytes], object]:
            calls.append((status, headers, exc_info))
            return lambda data: None

        body = BaseHandler().error_output({}, recording)

        assert body == [BaseHandler.error_body]
        assert calls[0][0] == BaseHandler.error_status
        assert calls[0][1] == BaseHandler.error_headers

    def test_traceback_limit_caps_the_frames_logged(self) -> None:
        def deep(depth: int) -> None:
            if depth == 0:
                raise ValueError("bottom")
            deep(depth - 1)

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            deep(60)
            return []

        class Limited(SimpleHandler):
            traceback_limit = 2

        _, full = run_app(app)
        _, limited = run_app(app, handler_class=Limited)

        assert full.count('File "') > 2
        assert limited.count('File "') == 2


class CountingList(list[tuple[str, str]]):
    """A header list that counts the pairs its iterator hands out."""

    yielded = 0

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for pair in super().__iter__():
            self.yielded += 1
            yield pair


class TestHeadersScanTheList:
    """`Headers` rows: lookups, assignment and deletion are O(h) scans of the
    wrapped list; `add_header()` appends without one."""

    @staticmethod
    def counted(size: int) -> tuple[Headers, CountingList]:
        wrapped = Headers([(f"X-{index}", "v") for index in range(size)])
        counting = CountingList(wrapped._headers)  # type: ignore[attr-defined]  # noqa: SLF001
        wrapped._headers = counting  # type: ignore[attr-defined]  # noqa: SLF001
        return wrapped, counting

    OPERATIONS: dict[str, Callable[[Headers], Any]] = {
        "get": lambda h: h.get("missing"),
        "getitem": lambda h: h["missing"],
        "contains": lambda h: "missing" in h,
        "get_all": lambda h: h.get_all("missing"),
        "setdefault": lambda h: h.setdefault("missing", "v"),
        "setitem": lambda h: h.__setitem__("missing", "v"),
        "delitem": lambda h: h.__delitem__("missing"),
    }

    @pytest.mark.parametrize("name", list(OPERATIONS))
    @pytest.mark.parametrize("size", [10, 10_000])
    def test_a_missing_name_scans_every_header(self, name: str, size: int) -> None:
        wrapped, counting = self.counted(size)

        self.OPERATIONS[name](wrapped)

        assert counting.yielded == size, f"{name} on {size} headers read {counting.yielded}"

    FIRST_MATCH: dict[str, Callable[[Headers], Any]] = {
        "get": lambda h: h.get("x-0"),
        "getitem": lambda h: h["x-0"],
        "contains": lambda h: "x-0" in h,
    }

    @pytest.mark.parametrize("name", list(FIRST_MATCH))
    def test_a_lookup_stops_at_the_first_match(self, name: str) -> None:
        wrapped, counting = self.counted(10_000)

        self.FIRST_MATCH[name](wrapped)

        assert counting.yielded == 1

    def test_add_header_does_not_scan(self) -> None:
        wrapped, counting = self.counted(10_000)

        wrapped.add_header("X-0", "again", charset="utf-8", inline=None)

        assert counting.yielded == 0
        assert wrapped.get_all("x-0") == ["v", 'again; charset="utf-8"; inline']

    def test_the_list_is_wrapped_not_copied(self) -> None:
        pairs = [("Content-Type", "text/plain")]
        wrapped = Headers(pairs)

        wrapped["X-Id"] = "1"
        del wrapped["content-type"]

        assert pairs == [("X-Id", "1")]
        assert wrapped.items() == pairs
        assert wrapped.items() is not pairs

    def test_assignment_replaces_every_copy(self) -> None:
        wrapped = Headers([("A", "1"), ("B", "2"), ("a", "3")])

        wrapped["A"] = "4"

        assert wrapped.items() == [("B", "2"), ("A", "4")]

    def test_views_are_new_lists(self) -> None:
        pairs = [("A", "1"), ("A", "2")]
        wrapped = Headers(pairs)

        for view in (wrapped.keys, wrapped.values, wrapped.items):
            first = view()
            assert first is not view()
            assert first is not pairs
            first.clear()
            assert len(wrapped) == 2
        assert wrapped.keys() == ["A", "A"]
        assert wrapped.values() == ["1", "2"]
        assert len(wrapped) == 2
        assert str(wrapped) == "A: 1\r\nA: 2\r\n\r\n"
        assert bytes(wrapped) == b"A: 1\r\nA: 2\r\n\r\n"

    def test_a_missing_name_is_none_and_deleting_it_is_fine(self) -> None:
        wrapped = Headers()

        assert wrapped["missing"] is None
        del wrapped["missing"]
        assert wrapped.setdefault("A", "1") == "1"
        assert wrapped.setdefault("a", "2") == "1"

    def test_construction_checks_every_pair(self) -> None:
        pairs: list[Any] = [(f"X-{index}", "v") for index in range(1_000)]
        pairs.append(("X-last", 1))

        with pytest.raises(AssertionError, match="must be"):
            Headers(pairs)

    def test_only_a_list_is_accepted(self) -> None:
        with pytest.raises(TypeError, match="list"):
            Headers((("A", "1"),))  # type: ignore[arg-type]


class CountingFile(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads: list[int | None] = []

    def read(self, size: int | None = -1) -> bytes:
        self.reads.append(size)
        return super().read(size)


class TestFileWrapperReadsBlocks:
    """`FileWrapper` | O(k) per step: one `read(blksize)` per step, and the
    handlers' default `sendfile()` falls back to that iteration."""

    def test_one_read_per_block(self) -> None:
        source = CountingFile(b"x" * 25_000)

        blocks = list(FileWrapper(source, blksize=10_000))

        assert [len(block) for block in blocks] == [10_000, 10_000, 5_000]
        assert source.reads == [10_000] * 4

    def test_construction_reads_nothing(self) -> None:
        source = CountingFile(b"x" * 25_000)

        FileWrapper(source)

        assert source.reads == []

    def test_the_handler_iterates_a_wrapped_file(self) -> None:
        source = CountingFile(b"x" * 25_000)

        def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
            start_response("200 OK", [("Content-Type", "text/plain")])
            return environ["wsgi.file_wrapper"](source, 10_000)

        out, _ = run_app(app)

        assert BaseHandler().sendfile() is False
        assert source.reads == [10_000] * 4
        assert out.endswith(b"x" * 25_000)

    def test_close_is_forwarded_when_the_file_has_one(self) -> None:
        source = io.BytesIO(b"data")
        wrapper = FileWrapper(source)

        wrapper.close()  # type: ignore[attr-defined]

        assert source.closed
        assert not hasattr(FileWrapper(iter([])), "close")  # type: ignore[arg-type]


class TestEnvironHelpers:
    """`shift_path_info()` is O(p); `request_uri()` and `application_uri()`
    are O(u); `setup_testing_defaults()`, `guess_scheme()` and
    `is_hop_by_hop()` are O(1)."""

    @staticmethod
    def path_of(segments: int) -> str:
        return "/" + "/".join("seg" for _ in range(segments))

    def test_shift_path_info_works_on_the_whole_remaining_path(self) -> None:
        peaks = []
        for segments in (10, 10_000):
            environ = request_environ(PATH_INFO=self.path_of(segments))

            def shift(environ: dict[str, Any] = environ) -> None:
                shift_path_info(dict(environ))

            shift()
            peaks.append(peak_bytes(shift))

        assert peaks[1] > peaks[0] * 100, f"1,000x the path: {peaks}"

    def test_shift_path_info_moves_one_segment(self) -> None:
        environ = request_environ(PATH_INFO="/a/b/c")

        assert shift_path_info(environ) == "a"
        assert (environ["SCRIPT_NAME"], environ["PATH_INFO"]) == ("/a", "/b/c")
        assert shift_path_info({"PATH_INFO": ""}) is None

    def test_request_uri_is_built_from_the_whole_path(self) -> None:
        peaks = []
        for segments in (10, 10_000):
            environ = request_environ(PATH_INFO=self.path_of(segments))
            request_uri(environ)
            peaks.append(peak_bytes(lambda environ=environ: request_uri(environ)))

        assert peaks[1] > peaks[0] * 100, f"1,000x the path: {peaks}"

    def test_the_uris(self) -> None:
        environ = request_environ(SCRIPT_NAME="/app", PATH_INFO="/a b", QUERY_STRING="q=1")

        assert application_uri(environ) == "http://127.0.0.1/app"
        assert request_uri(environ) == "http://127.0.0.1/app/a%20b?q=1"
        assert request_uri(environ, include_query=False) == "http://127.0.0.1/app/a%20b"

    def test_setup_testing_defaults_adds_a_fixed_set_and_keeps_existing(self) -> None:
        empty: dict[str, Any] = {}
        crowded: dict[str, Any] = {f"X_{index}": "v" for index in range(10_000)}
        crowded["REQUEST_METHOD"] = "POST"

        setup_testing_defaults(empty)
        setup_testing_defaults(crowded)

        assert set(crowded) - {f"X_{index}" for index in range(10_000)} == set(empty)
        assert crowded["REQUEST_METHOD"] == "POST"
        assert empty["REQUEST_METHOD"] == "GET"

    def test_guess_scheme_and_hop_by_hop(self) -> None:
        assert guess_scheme({"HTTPS": "on"}) == "https"
        assert guess_scheme({}) == "http"
        assert is_hop_by_hop("Keep-Alive")
        assert not is_hop_by_hop("Content-Type")

    def test_demo_app_writes_one_sorted_line_per_entry(self) -> None:
        environ = {"B": "2", "A": "1", "C": "3"}
        body = b"".join(demo_app(environ, ignore_start_response)).decode()

        assert body.splitlines()[2:] == ["A = '1'", "B = '2'", "C = '3'"]

    def test_the_package_is_pure_python(self) -> None:
        for module in (handlers, headers, simple_server, util, validate):
            assert module.__file__ is not None and module.__file__.endswith(".py")


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


class TestTheDevelopmentServer:
    """`WSGIServer` rows: single-threaded, one HTTP/1.0 request per
    connection, a resolver lookup at bind time, and a capped request line."""

    def test_it_has_no_threading_mix_in(self) -> None:
        assert issubclass(WSGIServer, HTTPServer)
        assert not issubclass(WSGIServer, socketserver.ThreadingMixIn)

    def test_make_server_resolves_the_host_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        original = socket.getfqdn

        def counting(name: str = "") -> str:
            calls.append(name)
            return original(name)

        monkeypatch.setattr(socket, "getfqdn", counting)

        with make_server("127.0.0.1", 0, text_app([b""]), handler_class=QuietHandler) as server:
            assert server.get_app() is not None

        assert calls == ["127.0.0.1"]

    def test_set_app_and_get_app(self) -> None:
        app = text_app([b""])
        with make_server("127.0.0.1", 0, app, handler_class=QuietHandler) as server:
            assert server.get_app() is app
            server.set_app(demo_app)
            assert server.get_app() is demo_app

    def test_one_http_1_0_request_per_connection(self) -> None:
        with make_server("127.0.0.1", 0, text_app([b"hi"]), handler_class=QuietHandler) as server:
            worker = threading.Thread(target=server.handle_request)
            worker.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            try:
                connection.request("GET", "/")
                response = connection.getresponse()
                body = response.read()
            finally:
                connection.close()
                worker.join(timeout=10)

        assert body == b"hi"
        assert response.version == 10
        assert response.will_close
        assert not worker.is_alive(), "handle_request() did not return after one request"

    def test_an_oversized_request_line_is_refused(self) -> None:
        called: list[bool] = []

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            called.append(True)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b""]

        with make_server("127.0.0.1", 0, app, handler_class=QuietHandler) as server:
            worker = threading.Thread(target=server.handle_request)
            worker.start()
            with socket.create_connection(("127.0.0.1", server.server_port), timeout=10) as peer:
                peer.sendall(b"GET /" + b"a" * 70_000 + b" HTTP/1.0\r\n\r\n")
                reply = peer.recv(100)
            worker.join(timeout=10)

        assert reply.startswith(b"HTTP/1.0 414"), reply
        assert called == []

    def test_chunks_go_straight_to_the_socket(self) -> None:
        assert WSGIRequestHandler.wbufsize == 0

    BASE_ENVIRON = {"SERVER_NAME": "test", "SCRIPT_NAME": ""}

    @classmethod
    def environ_for(cls, message: http.client.HTTPMessage) -> dict[str, Any]:
        """`get_environ()` on a handler that has parsed `message` from `GET /x?y=1`."""

        class Server:
            base_environ = cls.BASE_ENVIRON

        handler = WSGIRequestHandler.__new__(WSGIRequestHandler)
        handler.server = Server()  # type: ignore[assignment]
        handler.request_version = "HTTP/1.0"
        handler.command = "GET"
        handler.path = "/x?y=1"
        handler.client_address = ("127.0.0.1", 1)
        handler.headers = message
        assert handler.get_stderr() is sys.stderr
        return handler.get_environ()

    @pytest.mark.parametrize("count", [10, 1_000])
    def test_get_environ_adds_one_entry_per_distinct_header_name(self, count: int) -> None:
        message = http.client.HTTPMessage()
        for index in range(count):
            message[f"X-Header-{index}"] = "v"

        environ = self.environ_for(message)

        http_keys = [key for key in environ if key.startswith("HTTP_")]
        assert len(http_keys) == count
        assert environ is not self.BASE_ENVIRON
        assert (environ["PATH_INFO"], environ["QUERY_STRING"]) == ("/x", "y=1")

    def test_repeats_merge_and_content_headers_have_their_own_keys(self) -> None:
        message = http.client.HTTPMessage()
        message["Accept"] = "a"
        message["Accept"] = "b"
        message["Content-Type"] = "text/plain"
        message["Content-Length"] = "3"

        environ = self.environ_for(message)

        assert environ["HTTP_ACCEPT"] == "a,b"
        assert (environ["CONTENT_TYPE"], environ["CONTENT_LENGTH"]) == ("text/plain", "3")
        assert [key for key in environ if key.startswith("HTTP_")] == ["HTTP_ACCEPT"]


class TestValidatorChecksEachRequest:
    """`validator(app)` is O(1) to build; each call checks every environ key
    and every response header, then the type of each chunk."""

    def test_wrapping_does_not_call_the_application(self) -> None:
        calls: list[bool] = []

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            calls.append(True)
            return [b""]

        validator(app)

        assert calls == []

    def test_every_environ_key_is_checked(self) -> None:
        environ = request_environ(QUERY_STRING="")
        environ.update({f"X_{index}": "v" for index in range(1_000)})
        environ["X_LAST"] = 1

        with pytest.raises(AssertionError, match="X_LAST"):
            validator(text_app([b""]))(environ, ignore_start_response)

    def test_every_response_header_is_checked(self) -> None:
        pairs = [("Content-Type", "text/plain")]
        pairs += [(f"X-{index}", "v") for index in range(1_000)]
        pairs.append(("Bad Name", "v"))

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            start_response("200 OK", pairs)
            return [b""]

        with pytest.raises(AssertionError, match="Bad Name"):
            validator(app)(request_environ(QUERY_STRING=""), ignore_start_response)

    def test_each_chunk_is_checked_as_it_is_taken(self) -> None:
        body: list[Any] = [b"a", b"b", "c"]
        result = validator(text_app(body))(request_environ(QUERY_STRING=""), ignore_start_response)
        iterator = iter(result)

        assert next(iterator) == b"a"
        assert next(iterator) == b"b"
        with pytest.raises(AssertionError, match="non-bytestring"):
            next(iterator)
        result.close()  # type: ignore[attr-defined]

    def test_a_bare_bytes_return_is_refused(self) -> None:
        app = text_app(b"hello")  # type: ignore[arg-type]

        with pytest.raises(AssertionError, match="single-item list"):
            validator(app)(request_environ(QUERY_STRING=""), ignore_start_response)

    @staticmethod
    def validated_call(entries: int, headers: int) -> Callable[[], None]:
        """One warmed validated request with extra environ entries and headers."""
        environ = request_environ(QUERY_STRING="")
        environ.update({f"X_{index}": "v" for index in range(entries)})
        pairs = [("Content-Type", "text/plain")]
        pairs += [(f"X-{index}", "v") for index in range(headers)]

        def app(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
            start_response("200 OK", pairs)
            return [b""]

        checked = validator(app)

        def call() -> None:
            result = checked(environ, ignore_start_response)
            result.close()  # type: ignore[attr-defined]

        call()
        return call

    def test_memory_grows_with_the_environ(self) -> None:
        peaks = [peak_bytes(self.validated_call(entries, 10)) for entries in (10, 10_000)]

        assert peaks[1] > peaks[0] * 20, f"1,000x the environ entries: {peaks}"

    def test_memory_grows_with_the_response_headers(self) -> None:
        peaks = [peak_bytes(self.validated_call(10, headers)) for headers in (10, 10_000)]

        assert peaks[1] > peaks[0] * 20, f"1,000x the response headers: {peaks}"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="wsgiref.types is 3.11+")
class TestTypesAreStatic:
    """`wsgiref.types` holds protocols and aliases for type checkers only."""

    def test_the_names_exist_and_are_not_runtime_checkable(self) -> None:
        types = importlib.import_module("wsgiref.types")
        for name in (
            "StartResponse",
            "WSGIEnvironment",
            "WSGIApplication",
            "InputStream",
            "ErrorStream",
            "FileWrapper",
        ):
            assert hasattr(types, name)

        with pytest.raises(TypeError):
            isinstance(io.BytesIO(), types.InputStream)


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
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, and asserts its own result. The
    server example binds to 127.0.0.1 on a free port and serves one request."""

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
        line, source = next((n, s) for n, s in _blocks() if "flushes == 100" in s)
        mutated = source.replace("flushes == 100", "flushes == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
