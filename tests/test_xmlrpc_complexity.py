"""Tests for docs/stdlib/xmlrpc.md.

The page prices the package a document at a time: a call marshals its whole
request, sends one HTTP POST and parses the whole response, and the server
does the same in reverse. Linearity in the document is settled by traced
allocation and by timing across three sizes; everything else - what a call
sends, how many connections it opens, which name dispatch reaches, what is
copied - is settled by observation over loopback servers or with no server
at all. No test opens a connection beyond 127.0.0.1.

Measurement scope:

* `dumps()` and `loads()` over lists of 500, 5,000 and 50,000 two-element
  arrays (documents of about 58 KB, 0.58 MB and 5.9 MB): the traced
  peak stays between 0.5 and 5 bytes per document character at every size,
  and in a timing test, with the cyclic GC off, each 10x step costs between
  3x and 50x (fastest of 7): linear predicts 10x and quadratic 100x.
* A structure of 13 lists, each holding the next one twice, marshals the
  leaf string 4,096 times; a list or a dictionary that contains itself raises
  `TypeError`. `MAXINT + 1` and `MININT - 1` raise `OverflowError`, `None`
  raises `TypeError` without `allow_none`, `<unrelated/>` raises
  `ResponseError`, and a fault document raises `Fault`.
* `ServerProxy` construction and attribute access, three levels deep, leave
  a listening loopback socket with no pending connection; a counting request
  handler sees exactly one POST per call, one POST for a `MultiCall` of 20,
  and none for building or queuing it. A recording transport receives the
  request as one `bytes` object equal to `dumps()` of the call, and a
  recording handler's `decode_request_content()` receives the whole body of
  a 100,000-character request, equal to its Content-Length, before a
  recording `loads()` in `xmlrpc.server` starts parsing it.
* Accepted connections are counted by overriding `get_request()`: 10 calls
  through one proxy are 10 connections under the default handler and one
  under an HTTP/1.1 handler, and two proxies are two connections under HTTP/1.1.
  `proxy('close')()` and leaving the `with` block drop the transport's cached
  connection.
* Dispatch: a registered function shadows the instance method of the same
  name; a `_private` name is refused with `allow_dotted_names` off and on;
  a dotted name is refused with it off, where the whole name is one
  attribute lookup; with it on, a name of 1 and of 8 segments is resolved
  with exactly 1 and 8 public attribute lookups on a counting object, by
  dispatch and by `system_methodHelp()`; an instance's `_dispatch` receives
  names, `_private` ones included, without resolving them as attributes; a later
  `register_instance()` replaces the earlier one; the decorator form returns
  the function.
* `SimpleXMLRPCDispatcher` with no socket: `system_listMethods()` is sorted,
  includes the instance's public callables, and reflects a function
  registered after an earlier call; `system_methodHelp()` returns the
  docstring and `''` for an unknown name; `system_methodSignature()` returns
  its fixed string; `system_multicall()` turns a raising call into a fault
  entry and still runs the calls after it. On the client, the `MultiCall`
  result raises `Fault` at the failed position and returns the others.
* One request at a time: two clients call a method that records how many
  calls are inside it at once. Under `SimpleXMLRPCServer` the maximum is 1;
  under a `ThreadingMixIn` server both calls meet at a two-party barrier.
* A POST outside `rpc_paths` is a `ProtocolError` with code 404 and never
  reaches `_marshaled_dispatch()`; an empty `rpc_paths` serves any path.
  A 2,000-character result arrives gzip-encoded and a 10-character one does
  not; with `accept_gzip_encoding` off, neither is compressed.
* `Binary(bytes)` keeps the same object, `Binary(bytearray)` makes a new
  one; `encode()` writes base64 and `decode()` reverses it. `DateTime()`
  holds the local time within two seconds of the call; `use_builtin_types`
  returns `bytes` and `datetime`.
* `CGIXMLRPCRequestHandler.handle_request()` is driven with a request text,
  with a request on stdin and `CONTENT_LENGTH`, and with `REQUEST_METHOD=GET`
  (a 400 page), capturing standard output.
* Documentation pages: `generate_html_documentation()` calls
  `ServerHTMLDoc.docroutine()` once per listed method and again on the next
  call; the three setters reach the page; a GET to a loopback
  `DocXMLRPCServer` returns the page while a POST still dispatches;
  `DocCGIXMLRPCRequestHandler.handle_request()` answers GET with the page.
* Every fenced Python block runs in its own subprocess, each starting its
  own loopback server where it needs one, and a mutated assertion in one of
  them is asserted to fail.

Not settled here:

* Network round trips, and every cost of a real remote peer, `SafeTransport`
  and TLS included. The bounds exclude them by definition.
* `system_listMethods()` is O(f log f) because `dir()` of the instance sorts
  every attribute and the result is `sorted()` again, on every call;
  generating the documentation page adds one pass over each docstring and
  the server documentation (Lib/xmlrpc/server.py). `system_methodHelp()`
  adds O(h) through `pydoc.getdoc()` to its O(p) lookup. The tests observe
  the sorting, the per-call rebuild and the per-method rendering, not the
  growth rate.
* `Transport.request()` retries once when a kept-alive connection turns out
  to be closed, which sends the request a second time. No test exercises a
  dropped connection.
* Linearity is measured on one shape: flat arrays of short strings and small
  ints. Deep nesting, long strings, structs with many members and non-ASCII
  text are not varied. Marshalling recurses once per nesting level, so very
  deep values reach the recursion limit; that is not priced.
* A gzip-encoded response is read whole into memory before parsing
  (`GzipDecodedResponse`); a server decodes a gzip request with a 20 MiB cap
  (`gzip_decode`). Both are read from Lib/xmlrpc/client.py and not measured.
* Excluded from the page as internals the official documentation does not
  describe: `Marshaller`, `Unmarshaller`, `ExpatParser`, `getparser`,
  `escape`, `gzip_encode`, `gzip_decode`, `GzipDecodedResponse`, `Transport`
  methods, `MultiCallIterator` (priced as the `MultiCall` result),
  `MultiPathXMLRPCServer`, `ServerHTMLDoc`, `XMLRPCDocGenerator`,
  `resolve_dotted_attribute`, `list_public_methods`, and the attributes the
  request handlers inherit from `http.server`.
"""

from __future__ import annotations

import contextlib
import datetime
import gc
import io
import os
import pathlib
import re
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import xmlrpc.client
import xmlrpc.server
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "xmlrpc.md"
EXPECTED_BLOCKS = 10
LOOPBACK = ("127.0.0.1", 0)


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call, with the cyclic GC off."""
    best: float | None = None
    gc.collect()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            for _ in range(inner):
                func()
            elapsed = (time.perf_counter_ns() - start) / inner
            best = elapsed if best is None else min(best, elapsed)
    finally:
        gc.enable()
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


@contextlib.contextmanager
def serving(server: xmlrpc.server.SimpleXMLRPCServer) -> Iterator[str]:
    """Run `server` on a background thread and yield its URL."""
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}/"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class CountingServer(xmlrpc.server.SimpleXMLRPCServer):
    """Counts accepted connections."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("logRequests", False)
        super().__init__(*args, **kwargs)
        self.connections = 0

    def get_request(self) -> tuple[socket.socket, Any]:
        self.connections += 1
        return super().get_request()


class CountingHandler(xmlrpc.server.SimpleXMLRPCRequestHandler):
    """Counts POST requests across every instance."""

    posts = 0

    def do_POST(self) -> None:
        type(self).posts += 1
        super().do_POST()


class KeepAliveHandler(xmlrpc.server.SimpleXMLRPCRequestHandler):
    protocol_version = "HTTP/1.1"


class RecordingTransport(xmlrpc.client.Transport):
    """Records each request body and each response's Content-Encoding."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bodies: list[bytes] = []
        self.encodings: list[str | None] = []

    def request(self, host: Any, handler: Any, request_body: Any, verbose: bool = False) -> Any:
        self.bodies.append(request_body)
        return super().request(host, handler, request_body, verbose)

    def parse_response(self, response: Any) -> Any:
        self.encodings.append(response.getheader("Content-Encoding"))
        return super().parse_response(response)


def register(target: Any, function: Callable[..., Any], name: str | None = None) -> None:
    """`register_function()` without typeshed's narrow `_DispatchProtocol`."""
    target.register_function(function, name)


def flat_document(elements: int) -> tuple[list[list[Any]]]:
    return ([["abcdefgh", index] for index in range(elements)],)


class TestDocumentsAreLinear:
    """`dumps` and `loads` | O(n) | O(n), n = document characters; a call
    and a server dispatch are built from them."""

    SIZES = (500, 5_000, 50_000)

    @pytest.mark.serial
    @pytest.mark.parametrize("operation", ["dumps", "loads"])
    def test_the_peak_tracks_the_document(self, operation: str) -> None:
        per_char = []
        for elements in self.SIZES:
            params = flat_document(elements)
            document = xmlrpc.client.dumps(params).encode()
            if operation == "dumps":
                peak = peak_bytes(lambda p=params: xmlrpc.client.dumps(p))  # type: ignore[misc]
            else:
                peak = peak_bytes(lambda d=document: xmlrpc.client.loads(d))  # type: ignore[misc]
            per_char.append(peak / len(document))

        assert all(0.5 < ratio < 5 for ratio in per_char), (
            f"{operation} peak per document character at {self.SIZES}: {per_char}"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("operation", ["dumps", "loads"])
    def test_each_tenfold_step_costs_about_tenfold(self, operation: str) -> None:
        durations = []
        for elements in self.SIZES:
            params = flat_document(elements)
            document = xmlrpc.client.dumps(params).encode()
            if operation == "dumps":
                durations.append(best_ns(lambda p=params: xmlrpc.client.dumps(p), repeats=7))  # type: ignore[misc]
            else:
                durations.append(best_ns(lambda d=document: xmlrpc.client.loads(d), repeats=7))  # type: ignore[misc]
        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]

        assert all(3 < ratio < 50 for ratio in ratios), (
            f"{operation}: 10x steps cost {ratios} ({durations} ns); linear predicts 10x, "
            "quadratic 100x"
        )

    def test_a_round_trip_returns_the_values_and_the_method_name(self) -> None:
        document = xmlrpc.client.dumps(({"a": [1, 2.5, "x"]}, True), "store")

        assert xmlrpc.client.loads(document) == (({"a": [1, 2.5, "x"]}, True), "store")


class TestMarshallingRepeatsSharedValues:
    """`dumps` writes a value once for every reference to it, and a cycle
    raises instead of recursing."""

    def test_a_shared_list_is_written_once_per_reference(self) -> None:
        value: list[Any] = ["leaf"]
        for _ in range(12):
            value = [value, value]

        document = xmlrpc.client.dumps((value,))

        assert document.count("<string>leaf</string>") == 2**12

    @pytest.mark.parametrize("kind", ["list", "dict"])
    def test_a_cycle_raises_type_error(self, kind: str) -> None:
        cycle: Any
        if kind == "list":
            cycle = []
            cycle.append(cycle)
        else:
            cycle = {}
            cycle["self"] = cycle

        with pytest.raises(TypeError, match="recursive"):
            xmlrpc.client.dumps((cycle,))


class TestMarshallingLimits:
    """`MAXINT`/`MININT`, `allow_none`, `ResponseError` and `Fault`."""

    def test_ints_outside_32_bits_overflow(self) -> None:
        assert xmlrpc.client.MAXINT == 2**31 - 1
        assert xmlrpc.client.MININT == -(2**31)
        xmlrpc.client.dumps((xmlrpc.client.MAXINT, xmlrpc.client.MININT))

        for value in (xmlrpc.client.MAXINT + 1, xmlrpc.client.MININT - 1):
            with pytest.raises(OverflowError):
                xmlrpc.client.dumps((value,))

    def test_none_needs_allow_none(self) -> None:
        with pytest.raises(TypeError, match="allow_none"):
            xmlrpc.client.dumps((None,))

        assert xmlrpc.client.loads(xmlrpc.client.dumps((None,), allow_none=True))[0] == (None,)

    def test_well_formed_xml_that_is_not_xmlrpc_is_a_response_error(self) -> None:
        with pytest.raises(xmlrpc.client.ResponseError):
            xmlrpc.client.loads(b"<unrelated/>")

        assert issubclass(xmlrpc.client.ResponseError, xmlrpc.client.Error)
        assert issubclass(xmlrpc.client.Fault, xmlrpc.client.Error)
        assert issubclass(xmlrpc.client.ProtocolError, xmlrpc.client.Error)

    def test_a_fault_document_raises_fault(self) -> None:
        document = xmlrpc.client.dumps(xmlrpc.client.Fault(7, "nope"))

        with pytest.raises(xmlrpc.client.Fault) as raised:
            xmlrpc.client.loads(document)

        assert (raised.value.faultCode, raised.value.faultString) == (7, "nope")


class TestBinaryAndDateTime:
    """`Binary(data)` keeps `bytes` and copies `bytearray`; `encode`/`decode`
    are base64; `DateTime()` defaults to the current local time."""

    def test_bytes_are_kept_and_bytearrays_copied(self) -> None:
        payload = b"\x00\x01" * 1000
        mutable = bytearray(payload)

        kept = xmlrpc.client.Binary(payload)
        copied = xmlrpc.client.Binary(mutable)
        mutable[0] = 0xFF

        assert kept.data is payload
        assert copied.data == payload
        assert type(copied.data) is bytes

    def test_encode_and_decode_are_base64(self) -> None:
        out = io.StringIO()
        xmlrpc.client.Binary(b"hello").encode(out)
        decoded = xmlrpc.client.Binary()
        decoded.decode(b"aGVsbG8=\n")

        assert out.getvalue() == "<value><base64>\naGVsbG8=\n</base64></value>\n"
        assert decoded.data == b"hello"

    def test_a_default_datetime_is_now(self) -> None:
        before = time.time()
        stamp = xmlrpc.client.DateTime()
        after = time.time()

        moment = time.mktime(time.strptime(stamp.value, "%Y%m%dT%H:%M:%S"))
        assert int(before) - 2 <= moment <= after + 2

    def test_datetime_encode_and_decode_carry_the_string(self) -> None:
        stamp = xmlrpc.client.DateTime(datetime.datetime(2024, 5, 17, 12, 30))
        out = io.StringIO()
        stamp.encode(out)
        other = xmlrpc.client.DateTime()
        other.decode("20000101T00:00:00")

        assert stamp.value == "20240517T12:30:00"
        assert "20240517T12:30:00" in out.getvalue()
        assert other.value == "20000101T00:00:00"

    def test_builtin_types_replace_the_wrappers(self) -> None:
        moment = datetime.datetime(2024, 5, 17, 12, 30)
        document = xmlrpc.client.dumps((b"raw", moment))

        wrapped, _ = xmlrpc.client.loads(document)
        builtin, _ = xmlrpc.client.loads(document, use_builtin_types=True)

        assert isinstance(wrapped[0], xmlrpc.client.Binary)
        assert isinstance(wrapped[1], xmlrpc.client.DateTime)
        assert builtin == (b"raw", moment)


class TestProxyIsLazy:
    """`ServerProxy()` | O(1): no connection until the first call; attribute
    access builds a stub and sends nothing."""

    def test_construction_and_attributes_open_no_connection(self) -> None:
        with socket.create_server(LOOPBACK) as listener:
            host, port = listener.getsockname()
            proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}/")
            stub = proxy.a.b.c

            listener.settimeout(0.2)
            with pytest.raises(TimeoutError):
                listener.accept()

        assert callable(stub)
        assert isinstance(proxy("transport"), xmlrpc.client.Transport)

    def test_https_uses_the_safe_transport(self) -> None:
        proxy = xmlrpc.client.ServerProxy("https://127.0.0.1:1/")

        assert isinstance(proxy("transport"), xmlrpc.client.SafeTransport)

    def test_the_request_is_built_whole_before_it_is_sent(self) -> None:
        transport = RecordingTransport()
        with (
            CountingServer(LOOPBACK) as server,
            serving(server) as url,
            xmlrpc.client.ServerProxy(url, transport=transport) as proxy,
        ):
            register(server, len)
            assert proxy.len("abc") == 3

        assert transport.bodies == [xmlrpc.client.dumps(("abc",), "len").encode()]
        assert type(transport.bodies[0]) is bytes

    def test_the_server_reads_the_whole_body_before_parsing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[Any] = []
        original_loads = xmlrpc.client.loads  # what xmlrpc.server imported

        def recording_loads(data: Any, *args: Any, **kwargs: Any) -> Any:
            events.append("parse")
            return original_loads(data, *args, **kwargs)

        class Recording(xmlrpc.server.SimpleXMLRPCRequestHandler):
            def decode_request_content(self, data: bytes) -> bytes | None:
                events.append((len(data), int(self.headers["content-length"])))
                return super().decode_request_content(data)

        assert vars(xmlrpc.server)["loads"] is original_loads
        monkeypatch.setattr(xmlrpc.server, "loads", recording_loads)
        with CountingServer(LOOPBACK, requestHandler=Recording) as server:
            register(server, len)
            with serving(server) as url, xmlrpc.client.ServerProxy(url) as proxy:
                assert proxy.len("x" * 100_000) == 100_000

        assert len(events) == 2 and events[1] == "parse", events
        received, declared = events[0]
        assert received == declared > 100_000


class TestOneRequestPerCall:
    """A call is one POST; a `MultiCall` of c calls is one POST; building
    and queuing send nothing."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> None:
        CountingHandler.posts = 0

    def test_calls_and_batches(self) -> None:
        with CountingServer(LOOPBACK, requestHandler=CountingHandler) as server:
            register(server, pow)
            server.register_multicall_functions()
            with serving(server) as url, xmlrpc.client.ServerProxy(url) as proxy:
                for exponent in range(5):
                    assert proxy.pow(2, exponent) == 2**exponent
                assert CountingHandler.posts == 5

                batch = xmlrpc.client.MultiCall(proxy)
                for exponent in range(20):
                    batch.pow(2, exponent)
                assert CountingHandler.posts == 5, "queuing sent a request"

                results = batch()
                assert CountingHandler.posts == 6
                assert list(results) == [2**exponent for exponent in range(20)]  # type: ignore[arg-type]

    def test_a_failed_batched_call_raises_at_its_position(self) -> None:
        with CountingServer(LOOPBACK) as server:
            register(server, int)
            server.register_multicall_functions()
            with serving(server) as url, xmlrpc.client.ServerProxy(url) as proxy:
                batch = xmlrpc.client.MultiCall(proxy)
                for text in ("1", "two", "3"):
                    batch.int(text)
                results = batch()

        assert results[0] == 1
        with pytest.raises(xmlrpc.client.Fault, match="ValueError"):
            results[1]
        assert results[2] == 3


class TestConnectionReuse:
    """The transport reuses its connection while the server keeps it open;
    the default handler speaks HTTP/1.0 and closes it after each response."""

    @staticmethod
    def connections(handler: type[Any], proxies: int, calls: int) -> int:
        with CountingServer(LOOPBACK, requestHandler=handler) as server:
            register(server, abs)
            with serving(server) as url:
                for _ in range(proxies):
                    with xmlrpc.client.ServerProxy(url) as proxy:
                        for number in range(calls):
                            assert proxy.abs(-number) == number
            return server.connections

    def test_the_default_handler_costs_a_connection_per_call(self) -> None:
        assert xmlrpc.server.SimpleXMLRPCRequestHandler.protocol_version == "HTTP/1.0"
        assert self.connections(xmlrpc.server.SimpleXMLRPCRequestHandler, 1, 10) == 10

    def test_an_http_11_handler_keeps_one(self) -> None:
        assert self.connections(KeepAliveHandler, 1, 10) == 1

    def test_each_proxy_has_its_own_connection(self) -> None:
        assert self.connections(KeepAliveHandler, 2, 5) == 2

    def test_closing_the_proxy_drops_the_connection(self) -> None:
        with CountingServer(LOOPBACK, requestHandler=KeepAliveHandler) as server:
            register(server, abs)
            with serving(server) as url:
                proxy = xmlrpc.client.ServerProxy(url)
                transport = proxy("transport")
                proxy.abs(-1)
                assert transport._connection[1] is not None  # noqa: SLF001
                proxy("close")()
                assert transport._connection == (None, None)  # noqa: SLF001

                with xmlrpc.client.ServerProxy(url) as scoped:
                    scoped.abs(-1)
                assert scoped("transport")._connection == (None, None)  # noqa: SLF001


class TestFaultsAndPaths:
    """Server exceptions arrive as `Fault`; HTTP errors as `ProtocolError`;
    `rpc_paths` rejects other paths before parsing."""

    def test_fault_codes(self) -> None:
        def withdraw(amount: int) -> int:
            if amount > 100:
                raise xmlrpc.client.Fault(4, "insufficient funds")
            return 100 - amount

        with CountingServer(LOOPBACK) as server:
            register(server, withdraw)
            register(server, int)
            with serving(server) as url, xmlrpc.client.ServerProxy(url) as proxy:
                with pytest.raises(xmlrpc.client.Fault) as own:
                    proxy.withdraw(500)
                with pytest.raises(xmlrpc.client.Fault) as other:
                    proxy.int("x")

        assert (own.value.faultCode, own.value.faultString) == (4, "insufficient funds")
        assert other.value.faultCode == 1
        assert "ValueError" in other.value.faultString

    def test_an_unlisted_path_is_a_404_that_is_never_parsed(self) -> None:
        dispatched: list[bytes] = []

        class Recording(CountingServer):
            def _marshaled_dispatch(self, data: Any, *args: Any, **kwargs: Any) -> Any:
                dispatched.append(data)
                return super()._marshaled_dispatch(data, *args, **kwargs)

        with Recording(LOOPBACK) as server:
            register(server, abs)
            with serving(server) as url:
                with xmlrpc.client.ServerProxy(url + "elsewhere") as proxy:
                    with pytest.raises(xmlrpc.client.ProtocolError) as raised:
                        proxy.abs(-1)
                assert dispatched == []
                with xmlrpc.client.ServerProxy(url + "RPC2") as proxy:
                    assert proxy.abs(-1) == 1
                assert len(dispatched) == 1

        error = raised.value
        assert error.errcode == 404
        assert error.errmsg == "Not Found"
        assert error.url.endswith("/elsewhere")
        assert isinstance(error.headers, dict)

    def test_an_empty_rpc_paths_serves_any_path(self) -> None:
        class AnyPath(xmlrpc.server.SimpleXMLRPCRequestHandler):
            rpc_paths = ()

        with CountingServer(LOOPBACK, requestHandler=AnyPath) as server:
            register(server, abs)
            with serving(server) as url, xmlrpc.client.ServerProxy(url + "x/y") as proxy:
                assert proxy.abs(-2) == 2


class TestResponseCompression:
    """`encode_threshold`: a response over 1,400 bytes is gzip-encoded when
    the client accepts gzip, which `ServerProxy`'s transport does by default."""

    @staticmethod
    def encodings(accept_gzip: bool) -> list[str | None]:
        transport = RecordingTransport()
        transport.accept_gzip_encoding = accept_gzip
        with CountingServer(LOOPBACK) as server:
            register(server, lambda size: "x" * size, "text")
            with (
                serving(server) as url,
                xmlrpc.client.ServerProxy(url, transport=transport) as proxy,
            ):
                assert proxy.text(2_000) == "x" * 2_000
                assert proxy.text(10) == "x" * 10
        return transport.encodings

    def test_a_large_response_is_compressed(self) -> None:
        assert xmlrpc.server.SimpleXMLRPCRequestHandler.encode_threshold == 1400
        assert xmlrpc.client.Transport.accept_gzip_encoding is True
        assert self.encodings(accept_gzip=True) == ["gzip", None]

    def test_nothing_is_compressed_when_the_client_declines(self) -> None:
        assert self.encodings(accept_gzip=False) == [None, None]


class Node:
    """An attribute chain that counts public attribute lookups."""

    lookups = 0

    def __init__(self, depth: int) -> None:
        self.depth = depth

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_"):
            Node.lookups += 1
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        if name == "child" and object.__getattribute__(self, "depth") > 0:
            return Node(object.__getattribute__(self, "depth") - 1)
        raise AttributeError(name)

    def leaf(self) -> str:
        """Return a marker."""
        return "leaf"


class TestDispatch:
    """Registered functions first, then the instance by `getattr`: O(p) for
    p dotted segments; `_` names refused; dotted names only when allowed."""

    class Service:
        def greet(self) -> str:
            return "instance"

        def version(self) -> str:
            return "1.0"

        def _internal(self) -> str:
            return "hidden"

    def dispatcher(self, allow_dotted_names: bool = False) -> xmlrpc.server.SimpleXMLRPCDispatcher:
        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        dispatcher.register_instance(self.Service(), allow_dotted_names=allow_dotted_names)
        return dispatcher

    def test_a_function_shadows_the_instance(self) -> None:
        dispatcher = self.dispatcher()
        register(dispatcher, lambda: "function", "greet")

        assert dispatcher._dispatch("greet", ()) == "function"  # noqa: SLF001
        assert dispatcher._dispatch("version", ()) == "1.0"  # noqa: SLF001

    @pytest.mark.parametrize("allow_dotted_names", [False, True])
    def test_private_names_are_refused(self, allow_dotted_names: bool) -> None:
        with pytest.raises(Exception, match="not supported"):
            self.dispatcher(allow_dotted_names)._dispatch("_internal", ())  # noqa: SLF001

    def test_an_instance_dispatch_hook_receives_every_name(self) -> None:
        received: list[tuple[str, Any]] = []

        class Hooked:
            def _dispatch(self, method: str, params: Any) -> str:
                received.append((method, params))
                return "hooked"

        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        dispatcher.register_instance(Hooked())

        assert dispatcher._dispatch("_private.name", (1,)) == "hooked"  # noqa: SLF001
        assert received == [("_private.name", (1,))]

    def test_dotted_names_need_permission(self) -> None:
        with pytest.raises(Exception, match="not supported"):
            self.dispatcher()._dispatch("greet.__self__", ())  # noqa: SLF001

        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        dispatcher.register_instance(Node(8), allow_dotted_names=False)
        Node.lookups = 0
        with pytest.raises(Exception, match="not supported"):
            dispatcher._dispatch("child.leaf", ())  # noqa: SLF001
        assert Node.lookups == 1

        Node.lookups = 0
        assert dispatcher._dispatch("leaf", ()) == "leaf"  # noqa: SLF001
        assert Node.lookups == 1

    @pytest.mark.parametrize("segments", [1, 8])
    def test_one_lookup_per_segment(self, segments: int) -> None:
        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        dispatcher.register_instance(Node(segments), allow_dotted_names=True)
        name = ".".join(["child"] * (segments - 1) + ["leaf"])
        Node.lookups = 0

        assert dispatcher._dispatch(name, ()) == "leaf"  # noqa: SLF001
        assert Node.lookups == segments

        Node.lookups = 0
        assert dispatcher.system_methodHelp(name) == "Return a marker."
        assert Node.lookups == segments

    def test_a_second_instance_replaces_the_first(self) -> None:
        dispatcher = self.dispatcher()
        dispatcher.register_instance(Node(0))

        assert dispatcher._dispatch("leaf", ()) == "leaf"  # noqa: SLF001
        with pytest.raises(Exception, match="not supported"):
            dispatcher._dispatch("version", ())  # noqa: SLF001

    def test_register_function_works_as_a_decorator(self) -> None:
        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()

        @dispatcher.register_function(name="renamed")
        def original() -> str:
            return "ok"

        assert original() == "ok"
        assert dispatcher.funcs == {"renamed": original}

    def test_the_registration_helpers_add_their_names(self) -> None:
        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()

        dispatcher.register_introspection_functions()
        dispatcher.register_multicall_functions()

        assert set(dispatcher.funcs) == {
            "system.listMethods",
            "system.methodSignature",
            "system.methodHelp",
            "system.multicall",
        }


class TestSystemMethods:
    """`system_listMethods` sorted and rebuilt per call; `methodHelp` the
    docstring; `methodSignature` fixed; `multicall` runs every call."""

    def test_list_methods_is_sorted_and_rebuilt_per_call(self) -> None:
        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        dispatcher.register_instance(TestDispatch.Service())
        register(dispatcher, abs, "zeta")
        register(dispatcher, abs, "alpha")

        first = dispatcher.system_listMethods()
        register(dispatcher, abs, "middle")
        second = dispatcher.system_listMethods()

        assert first == ["alpha", "greet", "version", "zeta"]
        assert second == sorted(second) and "middle" in second

    def test_method_help_and_signature(self) -> None:
        def documented() -> None:
            """Does a thing."""

        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        register(dispatcher, documented)

        assert dispatcher.system_methodHelp("documented") == "Does a thing."
        assert dispatcher.system_methodHelp("missing") == ""
        assert dispatcher.system_methodSignature("documented") == "signatures not supported"

    def test_multicall_runs_every_call_past_a_failure(self) -> None:
        calls: list[str] = []

        def record(text: str) -> int:
            calls.append(text)
            return int(text)

        dispatcher = xmlrpc.server.SimpleXMLRPCDispatcher()
        register(dispatcher, record)

        results = dispatcher.system_multicall(
            [{"methodName": "record", "params": [text]} for text in ("1", "two", "3")]
        )

        assert calls == ["1", "two", "3"]
        assert results[0] == [1] and results[2] == [3]
        failed: Any = results[1]
        assert failed["faultCode"] == 1
        assert "ValueError" in failed["faultString"]


class TestOneRequestAtATime:
    """`SimpleXMLRPCServer` serves requests one after another;
    `ThreadingMixIn` runs them side by side."""

    @staticmethod
    def two_concurrent_calls(server: xmlrpc.server.SimpleXMLRPCServer) -> list[Any]:
        results: list[Any] = []
        with serving(server) as url:

            def call() -> None:
                with xmlrpc.client.ServerProxy(url) as proxy:
                    results.append(proxy.work())

            clients = [threading.Thread(target=call) for _ in range(2)]
            for client in clients:
                client.start()
            for client in clients:
                client.join()
        return results

    def test_the_plain_server_never_overlaps_two_calls(self) -> None:
        lock = threading.Lock()
        inside = [0]
        most = [0]

        def work() -> bool:
            with lock:
                inside[0] += 1
                most[0] = max(most[0], inside[0])
            time.sleep(0.2)
            with lock:
                inside[0] -= 1
            return True

        server = CountingServer(LOOPBACK)
        register(server, work)

        assert self.two_concurrent_calls(server) == [True, True]
        assert most[0] == 1

    def test_a_threading_server_runs_them_together(self) -> None:
        class Threaded(socketserver.ThreadingMixIn, CountingServer):
            daemon_threads = True

        barrier = threading.Barrier(2, timeout=10)

        def work() -> bool:
            barrier.wait()
            return True

        server = Threaded(LOOPBACK)
        register(server, work)

        assert self.two_concurrent_calls(server) == [True, True]


@contextlib.contextmanager
def captured_stdout() -> Iterator[io.TextIOWrapper]:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    with contextlib.redirect_stdout(stream):
        yield stream
        stream.flush()


class TestCGIHandler:
    """`CGIXMLRPCRequestHandler.handle_request(request_text=None)`: one
    request in, headers and response out on stdout."""

    @staticmethod
    def body(output: bytes) -> bytes:
        headers, _, body = output.partition(b"\n\n")
        assert b"Content-Type: text/xml" in headers
        assert f"Content-Length: {len(body)}".encode() in headers
        return body

    def test_a_given_request(self) -> None:
        handler = xmlrpc.server.CGIXMLRPCRequestHandler()
        register(handler, len)

        with captured_stdout() as out:
            handler.handle_request(xmlrpc.client.dumps(([1, 2, 3],), "len"))

        assert xmlrpc.client.loads(self.body(out.buffer.getvalue()))[0] == (3,)  # type: ignore[attr-defined]

    def test_a_request_on_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        request = xmlrpc.client.dumps(("abcd",), "len")
        monkeypatch.setattr(sys, "stdin", io.StringIO(request))
        monkeypatch.setenv("CONTENT_LENGTH", str(len(request)))
        monkeypatch.delenv("REQUEST_METHOD", raising=False)
        handler = xmlrpc.server.CGIXMLRPCRequestHandler()
        register(handler, len)

        with captured_stdout() as out:
            handler.handle_request()

        assert xmlrpc.client.loads(self.body(out.buffer.getvalue()))[0] == (4,)  # type: ignore[attr-defined]

    def test_a_get_is_a_400(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUEST_METHOD", "GET")

        with captured_stdout() as out:
            xmlrpc.server.CGIXMLRPCRequestHandler().handle_request()

        assert out.buffer.getvalue().startswith(b"Status: 400")  # type: ignore[attr-defined]

    def test_the_registration_methods_match_the_server(self) -> None:
        handler = xmlrpc.server.CGIXMLRPCRequestHandler()
        handler.register_instance(TestDispatch.Service())
        handler.register_introspection_functions()
        handler.register_multicall_functions()

        assert "greet" in handler.system_listMethods()
        assert "system.multicall" in handler.funcs


class TestDocumentationPages:
    """The page is rebuilt per request, one rendering per listed method."""

    @staticmethod
    def functions(count: int) -> list[Callable[[], None]]:
        made = []
        for index in range(count):

            def function() -> None:
                """Documented."""

            function.__name__ = f"f{index}"
            made.append(function)
        return made

    def test_each_page_renders_every_method_again(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rendered: list[str] = []
        original = xmlrpc.server.ServerHTMLDoc.docroutine

        def counting(self: Any, obj: Any, name: str, *args: Any, **kwargs: Any) -> str:
            rendered.append(name)
            return original(self, obj, name, *args, **kwargs)

        monkeypatch.setattr(xmlrpc.server.ServerHTMLDoc, "docroutine", counting)
        server = xmlrpc.server.DocXMLRPCServer(LOOPBACK, bind_and_activate=False)
        try:
            for function in self.functions(50):
                register(server, function)
            server.generate_html_documentation()
            assert rendered == sorted(f"f{index}" for index in range(50)), "not in sorted order"
            server.generate_html_documentation()
            assert rendered[50:] == rendered[:50]
        finally:
            server.server_close()

    def test_the_setters_reach_the_page(self) -> None:
        handler = xmlrpc.server.DocCGIXMLRPCRequestHandler()
        handler.set_server_title("Title here")
        handler.set_server_name("Name here")
        handler.set_server_documentation("Documentation here")

        page = handler.generate_html_documentation()

        assert "<title>Python: Title here</title>" in page
        assert "Name&nbsp;here" in page or "Name here" in page
        assert "Documentation&nbsp;here" in page or "Documentation here" in page

    def test_a_get_serves_the_page_and_a_post_still_dispatches(self) -> None:
        server = xmlrpc.server.DocXMLRPCServer(LOOPBACK, logRequests=False)
        register(server, abs)
        server.set_server_title("Loopback")
        with serving(server) as url:
            address: Any = server.server_address
            with socket.create_connection(address) as connection:
                connection.sendall(b"GET / HTTP/1.0\r\n\r\n")
                response = b""
                while chunk := connection.recv(65536):
                    response += chunk
            with xmlrpc.client.ServerProxy(url) as proxy:
                assert proxy.abs(-3) == 3

        assert response.startswith(b"HTTP/1.0 200")
        assert b"<title>Python: Loopback</title>" in response

    def test_the_cgi_handler_answers_get_with_the_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REQUEST_METHOD", "GET")
        handler = xmlrpc.server.DocCGIXMLRPCRequestHandler()
        register(handler, abs)

        with captured_stdout() as out:
            handler.handle_request()

        output = out.buffer.getvalue()  # type: ignore[attr-defined]
        assert output.startswith(b"Content-Type: text/html")
        assert b"<strong>abs</strong>" in output


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
    environment = {key: value for key, value in os.environ.items() if key != "REQUEST_METHOD"}
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=environment,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and starts its own loopback
    server where it needs one, and asserts its own result."""

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
        target = "connections_for_ten_calls(KeepAlive) == 1"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "connections_for_ten_calls(KeepAlive) == 10", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
        assert "connections_for_ten_calls(KeepAlive) == 10" in result.stderr
