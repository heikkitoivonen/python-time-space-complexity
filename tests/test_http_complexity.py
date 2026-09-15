"""Tests to verify documented behaviour of the http package.

docs/stdlib/http.md covers four modules: the `http` enumerations, `http.client`,
`http.server`, `http.cookies` and `http.cookiejar`. Round trips are external to
every bound on the page. Nothing here opens a socket: the client is driven
through a fake socket that records what was written, and the server's handlers
are driven directly, so the counts below are exact rather than timed.

Measurement scope:

* `HTTPStatus` and `HTTPMethod` lookups return the member that already exists.
  `HTTPStatus(404) is HTTPStatus.NOT_FOUND` settles both the time and the space
  column with no tolerance: a scan could return an equal member, but only an
  index into the value map returns *that* object without building anything.
* A readable body is written in `blocksize` chunks. 100,000 bytes at the
  default 8192 produce 13 `sendall` calls, none larger than 8192, so the
  memory a send needs does not follow the body. The same bytes passed as
  `bytes` produce one call carrying all 100,000.
* Request headers are buffered: 50 `putheader` calls followed by `endheaders`
  produce exactly one `sendall`. The server side buffers the same way - 50
  `send_header` calls write nothing until `end_headers`.
* Header parsing is bounded by the module's own constants, 100 headers of
  65,536 bytes. Both limits raise rather than truncate, and the tests assert
  the exception type at each one.
* `list_directory` calls `os.path.isdir` and `os.path.islink` once per entry -
  21 entries, 21 and 21 - and returns the whole listing as one buffer. The
  counts are taken by substituting both functions in the `http.server`
  namespace, and each substitution is asserted to have been reached.
* `BaseCookie.load` parses the whole string before applying any of it. A
  trailing reserved attribute with no value leaves the cookie object *empty*,
  not holding the two valid pairs that preceded it.
* `CookieJar.add_cookie_header` asks the policy once per stored domain, then
  once per path under an accepted domain, then once per cookie under an
  accepted path. A jar of 5 domains x 3 paths x 1 cookie answers a request for
  one of those domains with 5, 3 and 1 calls, which is the (d + p) in the row;
  a flat per-cookie scan would be 15. Selection is only half the call: it ends
  by calling `clear_expired_cookies`, which walks the whole jar, so the same
  request makes 16 `is_expired` calls over those 15 cookies - 15 swept plus the
  one `return_ok` check. A separate test shows the sweep dropping an expired
  cookie from a domain the request never matched, so the c term is real work
  rather than an unused path.
* The reserved key set of a `Morsel` is fixed but not the same size on every
  supported version - nine keys through 3.13, ten from 3.14, which adds
  `partitioned`. The tests compare against the module's own set rather than a
  literal, and check the version boundary separately.
* `Morsel`'s reserved names are dict keys, not attributes: `morsel['path']`
  works and `morsel.path` raises AttributeError. Only `key`, `value` and
  `coded_value` are attributes.
* `HTTPMessage.getallmatchingheaders` returns an empty list for every name on
  every supported version. It compares bare header names against a pattern
  ending in a colon, so nothing can match; its own docstring describes
  behaviour it does not have.
* The header-count limit counts the terminating blank line, so 99 headers is
  the most that parses and a normal block of 100 is already refused. The cap
  is also per block rather than per call: `begin()` skips `100 Continue`
  responses first, each parsed under the same limits.
* `BaseCookie.load` is atomic only where the parser *refuses*. `'a=1; path'`
  discards everything, because a reserved key with no value returns; `'a=1;
  ;;;'` keeps `a`, because the pattern stops matching and the loop breaks
  after the valid pairs were gathered. Both are tested against the same valid
  prefix so the difference is the ending, not the input.
* `HTTPResponse` never assigns `url`. The constructor takes the argument and
  drops it, so `geturl()` raises AttributeError on a response built through
  `http.client`; `urllib.request` sets the attribute itself afterwards.
* `get_proxy_response_headers` parses the stored CONNECT lines on every call -
  two calls return two different objects - so it is linear in those bytes.
* `BaseCookie.output` sorts its items by name, so output order is alphabetical
  rather than insertion order. The test uses names whose insertion order
  differs from their sorted order, so a missing sort would show.
* `Morsel.setdefault` stores nothing only while the full reserved key set is
  present; after `del morsel['domain']` it stores like any dict.
* `BaseCookie.load` has a third ending beyond the two above: a name the pattern
  accepts but `Morsel.set` refuses raises `CookieError` during the *apply*
  pass, after the earlier items already landed. `'session=abc123; bad@name=2'`
  raises and leaves `session` behind.
* The jar walk (`deepvalues`) collects each level before descending, so its
  memory is the widest level it meets - with one domain and one path that is
  every cookie. Counted at 20 cookies under one path. How it collects differs
  in the middle of the range: 3.11+ copies the level's values, 3.10 builds a
  sorted list of its keys, so 3.10 also yields cookies in sorted order. The
  tests watch both accessors rather than assuming either.
* `LWPCookieJar` keeps a cookie's port and comment; `MozillaCookieJar` drops
  both. Round-tripped and compared for the port and the comment separately.
* `getresponse()` skips only `100 Continue`. A `103 Early Hints` ends the loop
  and becomes the response, so the page says `100 Continue` rather than `1xx`.
  Where `_MAXINTERIMRESPONSES` exists the cap counts the final status line too,
  so 99 interim responses reach the real one and 100 raise.
* `BaseCookie(rawdata)` loads during construction, so the constructor is not
  O(1) when given an argument; the rows split the two cases.
* `Morsel.set` validates the *name* against the reserved set and the legal
  character set, and scans the name and both value forms for control
  characters, but stores the values by reference - asserted by identity for
  the value and by the three rejections for the checks.
* The example blocks are held offline by running each one with
  `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo`
  replaced by a raising stub, rather than by grepping the source for call
  names. A mutation test connects under the same guard to show it fails.
* `DefaultCookiePolicy.blocked_domains()` returns the stored tuple itself, so
  two calls are the same object. `is_blocked` is counted through a substituted
  matcher to show it scans the configured domains.

Source evidence: Lib/http/{__init__,client,server,cookies,cookiejar}.py on the
released CPython 3.10 through 3.14 branches. In client.py, `_MAXLINE` is 65536
and `_MAXHEADERS` is 100; `send` loops `data.read(self.blocksize)` for a
readable; `_send_output` joins the buffer and sends once. In cookies.py,
`__parse_string` fills `parsed_items` and applies it only after the loop
completes. In cookiejar.py, `_cookies_for_request` iterates `self._cookies`
per domain and `_cookie_attrs` sorts by path length; `blocked_domains` returns
`self._blocked_domains` without copying. In server.py, `list_directory` calls
`os.path.isdir` and `os.path.islink` per entry and `translate_path` drops
components that are not plain names.
https://github.com/python/cpython/blob/3.10/Lib/http/client.py
https://github.com/python/cpython/blob/3.14/Lib/http/client.py
https://github.com/python/cpython/blob/3.14/Lib/http/cookiejar.py
https://github.com/python/cpython/blob/3.14/Lib/http/server.py

Not settled here:

* Anything needing a peer: `connect()`, the TLS handshake, `getresponse()`
  against a real server, keep-alive behaviour across requests, and the thread
  a `ThreadingHTTPServer` gives each connection. There is no server, and
  standing one up would test the server rather than the bound. The rows that
  name a round trip are read from the CPython source.
* `CGIHTTPRequestHandler.do_POST` forks a child process, so its cost is the
  script's. Its presence and deprecation are checked; its execution is not.
* The name lookup `HTTPServer` does when it binds, which is the network's.
* `HTTPResponse.raw` appears in the audit's unclassified list but no supported
  CPython defines it on the class; the page does not document it, and this
  test asserts the class does not have it so the omission stays deliberate.
* Whether dropping a jar's dictionary is O(1). Releasing it frees the cookies
  it held, which is work proportional to them, but that is deallocation rather
  than the operation; the rows price the dict delete.
* Chunked transfer encoding and trailer blocks. The response rows scope b to
  decoded body bytes and say so; no test drives a chunked peer.
* `revert()`'s deep copy as a mechanism. The test establishes that the old
  contents survive a refused file, which is the behaviour the row promises;
  retaining the original dictionary without copying would satisfy it too.
* `readinto`'s O(1) space as against a body-sized temporary, and a `str` body
  being encoded in one piece rather than streamed. Both are read from the
  source; the tests here show the results, not the absence of an intermediate.
* Whether `CGIHTTPRequestHandler.do_POST` forks or feeds a subprocess, which
  depends on the platform. Only its presence and deprecation are exercised.
* Whether the expiry sweep matters in wall-clock terms at a given jar size.
  The sweep's existence and its per-cookie reach are counted; how large a jar
  has to be before that dominates a request is not measured, and the page
  states which side grows rather than by how much.
* The module-level helpers in `http.cookiejar` - `domain_match`, `http2time`,
  `split_header_words`, `request_host` and the rest - are absent from that
  module's `__all__` and from the official API inventory, so the page does not
  document them. The same holds for the compiled regex objects the module
  keeps at module level.

Axes not varied: non-ASCII header values and cookie values, `blocksize` other
than the default beyond the one two-chunk check, explicit chunked transfer
encoding, directory entry counts beyond the 21 used for the stat counts, name
lengths in the directory sort (the L in its comparison term is reasoned from
the key function, not measured), path component counts beyond the six used for
the join count, and jar shapes other than the 5x3x1 and 1x1x20 used to separate
the domain term from the cookie term.
"""

import contextlib
import http
import http.client
import http.cookiejar
import http.cookies
import http.server
import io
import os
import os.path
import pathlib
import re
import subprocess
import sys
import textwrap
import urllib.request
import warnings
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "http.md"

EXPECTED_BLOCKS = 6


class FakeSocket:
    """A socket that records writes and replays a canned response."""

    def __init__(self, reply: bytes = b"") -> None:
        self.sent: list[bytes] = []
        self.stream = io.BufferedReader(io.BytesIO(reply))

    def sendall(self, data: Any) -> None:
        self.sent.append(bytes(data))

    def makefile(self, *args: Any, **kwargs: Any) -> Any:
        return self.stream

    def close(self) -> None:
        pass

    def fileno(self) -> int:
        return -1


def connected(reply: bytes = b"") -> tuple[http.client.HTTPConnection, FakeSocket]:
    connection = http.client.HTTPConnection("example.com")
    sock = FakeSocket(reply)
    connection.sock = sock  # type: ignore[assignment]
    return connection, sock


def response_over(reply: bytes) -> http.client.HTTPResponse:
    response = http.client.HTTPResponse(FakeSocket(reply))  # type: ignore[arg-type]
    response.begin()
    return response


class TestHTTPStatus:
    """`HTTPStatus(code)` | O(1) | O(1) | Indexes the value-to-member dict."""

    def test_lookup_by_value_builds_nothing(self) -> None:
        """Identity settles the space column: no member is constructed."""
        assert http.HTTPStatus(404) is http.HTTPStatus.NOT_FOUND
        assert http.HTTPStatus(200) is http.HTTPStatus.OK

    def test_lookup_by_value_consults_the_value_map(self) -> None:
        """Identity alone would also hold for a scan; this watches the lookup."""
        mapping = getattr(http.HTTPStatus, "_value2member_map_")  # noqa: B009 - enum internals
        assert isinstance(mapping, dict)
        assert len(mapping) == len(list(http.HTTPStatus))

        asked: list[Any] = []

        class Watched(dict):  # type: ignore[type-arg]
            def __getitem__(self, key: Any) -> Any:
                asked.append(key)
                return super().__getitem__(key)

        setattr(http.HTTPStatus, "_value2member_map_", Watched(mapping))  # noqa: B010
        try:
            found = http.HTTPStatus(404)
        finally:
            setattr(http.HTTPStatus, "_value2member_map_", mapping)  # noqa: B010

        assert asked == [404], f"one indexed lookup, not a scan: {asked}"
        assert found is http.HTTPStatus.NOT_FOUND

    def test_lookup_by_name_is_a_class_attribute(self) -> None:
        assert http.HTTPStatus["NOT_FOUND"] is http.HTTPStatus.NOT_FOUND
        assert http.HTTPStatus.NOT_FOUND.value == 404

    def test_an_unknown_code_raises(self) -> None:
        with pytest.raises(ValueError):
            http.HTTPStatus(799)

    def test_phrase_and_description_are_different_strings(self) -> None:
        """The page's example distinguishes them; they are easy to confuse."""
        assert http.HTTPStatus.NOT_FOUND.phrase == "Not Found"
        assert http.HTTPStatus.NOT_FOUND.description == "Nothing matches the given URI"
        assert http.HTTPStatus.OK.phrase == "OK"

    def test_it_is_an_int(self) -> None:
        assert http.HTTPStatus.NOT_FOUND == 404
        assert isinstance(http.HTTPStatus.NOT_FOUND, int)

    def test_str_writes_the_code_only_from_3_11(self) -> None:
        """The page's admonition: 3.10 prints the member, 3.11+ the number."""
        printed = str(http.HTTPStatus.OK)

        if sys.version_info >= (3, 11):
            assert printed == "200"
        else:
            assert printed == "HTTPStatus.OK"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="category properties are 3.12+")
    def test_the_category_properties_are_range_checks(self) -> None:
        def flag(status: http.HTTPStatus, name: str) -> bool:
            return getattr(status, name)  # typeshed 3.12+

        assert flag(http.HTTPStatus.OK, "is_success") is True
        assert flag(http.HTTPStatus.OK, "is_client_error") is False
        assert flag(http.HTTPStatus.NOT_FOUND, "is_client_error") is True
        assert flag(http.HTTPStatus.CONTINUE, "is_informational") is True
        assert flag(http.HTTPStatus.FOUND, "is_redirection") is True
        assert flag(http.HTTPStatus.INTERNAL_SERVER_ERROR, "is_server_error") is True

    def test_the_category_properties_are_absent_before_3_12(self) -> None:
        if sys.version_info < (3, 12):
            assert not hasattr(http.HTTPStatus.OK, "is_success")


class TestHTTPMethod:
    """`HTTPMethod` | O(1) | O(1) | Python 3.11+."""

    def test_it_exists_only_from_3_11(self) -> None:
        assert hasattr(http, "HTTPMethod") == (sys.version_info >= (3, 11))

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="HTTPMethod is 3.11+")
    def test_lookup_by_value_returns_the_existing_member(self) -> None:
        method = getattr(http, "HTTPMethod")  # noqa: B009 - typeshed 3.11+

        assert method("GET") is method.GET
        assert method.GET == "GET"
        assert isinstance(getattr(method.GET, "description"), str)  # noqa: B009 - 3.11+


class TestParseHeaders:
    """`parse_headers(fp)` | O(n) | O(n) | Capped at 100 headers of 65,536 bytes."""

    def test_it_parses_to_the_blank_line(self) -> None:
        message = http.client.parse_headers(io.BytesIO(b"A: 1\r\nB: 2\r\n\r\nbody"))

        assert message["A"] == "1"
        assert message["B"] == "2"

    def test_the_blank_line_counts_toward_the_header_cap(self) -> None:
        """99 parses and 100 does not, because the terminator is counted too."""

        def block(count: int) -> io.BytesIO:
            lines = b"".join(b"X-%d: v\r\n" % index for index in range(count))
            return io.BytesIO(lines + b"\r\n")

        assert http.client.parse_headers(block(99))["X-98"] == "v"

        with pytest.raises(http.client.HTTPException, match="got more than 100 headers"):
            http.client.parse_headers(block(100))

    def test_the_line_length_is_capped(self) -> None:
        source = b"X: " + b"v" * 70_000 + b"\r\n\r\n"

        with pytest.raises(http.client.LineTooLong):
            http.client.parse_headers(io.BytesIO(source))

    def test_the_caps_are_the_documented_numbers(self) -> None:
        assert getattr(http.client, "_MAXHEADERS") == 100  # noqa: B009 - module private
        assert getattr(http.client, "_MAXLINE") == 65536  # noqa: B009 - module private

    def test_responses_is_a_mapping(self) -> None:
        """`responses` | O(1) | A dict lookup, not a scan."""
        assert isinstance(http.client.responses, dict)
        assert http.client.responses[404] == "Not Found"
        assert http.client.responses[200] == "OK"


class TestSendingABody:
    """`send(data)` | O(b) | O(B) for a readable | Chunked at `blocksize`."""

    def test_a_readable_is_sent_in_blocksize_chunks(self) -> None:
        connection, sock = connected()
        size = 100_000
        requested: list[Any] = []

        class WatchedBody(io.BytesIO):
            def read(self, amount: Any = -1, /) -> bytes:
                requested.append(amount)
                return super().read(amount)

        connection.send(WatchedBody(b"x" * size))

        assert connection.blocksize == 8192
        assert len(sock.sent) == -(-size // connection.blocksize) == 13
        assert max(len(chunk) for chunk in sock.sent) == connection.blocksize
        assert sum(len(chunk) for chunk in sock.sent) == size
        assert set(requested) == {connection.blocksize}, (
            f"the body must only ever be asked for one chunk: {sorted(set(requested))}"
        )

    def test_bytes_are_sent_whole(self) -> None:
        """The control: the chunking above is the readable path, not the socket."""
        connection, sock = connected()
        size = 100_000

        connection.send(b"x" * size)

        assert len(sock.sent) == 1
        assert len(sock.sent[0]) == size

    def test_bytes_reach_the_socket_without_a_copy(self) -> None:
        """O(1) space for the bytes case: the caller's object is passed through."""
        connection = http.client.HTTPConnection("example.com")
        seen: list[Any] = []

        class RecordingSocket(FakeSocket):
            def sendall(self, data: Any) -> None:
                seen.append(data)

        connection.sock = RecordingSocket()  # type: ignore[assignment]
        body = b"x" * 100_000

        connection.send(body)

        assert seen[0] is body

    def test_a_larger_blocksize_means_fewer_writes(self) -> None:
        connection, sock = connected()
        connection.blocksize = 50_000

        connection.send(io.BytesIO(b"x" * 100_000))

        assert len(sock.sent) == 2

    def test_headers_are_buffered_into_one_write(self) -> None:
        """`endheaders` | Joins the buffered lines and sends them in one write."""
        connection, sock = connected()
        connection.putrequest("GET", "/", skip_host=True, skip_accept_encoding=True)
        for index in range(50):
            connection.putheader(f"X-{index}", "v")

        assert sock.sent == [], "putheader must not reach the socket"

        connection.endheaders()

        assert len(sock.sent) == 1
        assert sock.sent[0].count(b"\r\n") == 52

    def test_request_sends_headers_then_body(self) -> None:
        connection, sock = connected()

        connection.request("POST", "/x", body=b"abc", headers={"Host": "example.com"})

        assert len(sock.sent) == 2
        assert sock.sent[0].startswith(b"POST /x HTTP/1.1\r\n")
        assert b"Content-Length: 3\r\n" in sock.sent[0]
        assert sock.sent[1] == b"abc"

    def test_class_attributes_are_what_the_page_says(self) -> None:
        assert http.client.HTTPConnection.default_port == 80
        assert http.client.HTTPSConnection.default_port == 443
        assert http.client.HTTPConnection.auto_open == 1
        assert http.client.HTTPConnection.debuglevel == 0

    def test_set_debuglevel_is_per_connection(self) -> None:
        connection, _ = connected()

        connection.set_debuglevel(1)

        assert connection.debuglevel == 1
        assert http.client.HTTPConnection.debuglevel == 0

    def test_set_tunnel_records_without_connecting(self) -> None:
        connection = http.client.HTTPConnection("proxy.example.com")

        connection.set_tunnel("target.example.com", 8443, {"X-A": "1"})

        assert getattr(connection, "_tunnel_host") == "target.example.com"  # noqa: B009
        assert getattr(connection, "_tunnel_port") == 8443  # noqa: B009
        assert connection.sock is None

    def test_sending_without_a_socket_raises(self) -> None:
        connection = http.client.HTTPConnection("example.com")
        connection.auto_open = 0

        with pytest.raises(http.client.NotConnected):
            connection.send(b"x")

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="proxy headers accessor is 3.12+")
    def test_proxy_response_headers_are_none_before_a_tunnel(self) -> None:
        connection = http.client.HTTPConnection("example.com")
        accessor = getattr(connection, "get_proxy_response_headers")  # noqa: B009 - 3.12+

        assert accessor() is None

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="proxy headers accessor is 3.12+")
    def test_proxy_response_headers_are_reparsed_on_every_call(self) -> None:
        """O(n), not O(1): the raw lines are kept and parsed afresh each time."""
        connection = http.client.HTTPConnection("example.com")
        setattr(  # noqa: B010 - what set_tunnel's CONNECT would have stored
            connection, "_raw_proxy_headers", [b"X-A: 1\r\n", b"\r\n"]
        )
        accessor = getattr(connection, "get_proxy_response_headers")  # noqa: B009 - 3.12+

        parses = 0
        real = getattr(http.client, "_parse_header_lines")  # noqa: B009 - module private

        def counting(*args: Any, **kwargs: Any) -> Any:
            nonlocal parses
            parses += 1
            return real(*args, **kwargs)

        setattr(http.client, "_parse_header_lines", counting)  # noqa: B010
        try:
            first, second = accessor(), accessor()
        finally:
            setattr(http.client, "_parse_header_lines", real)  # noqa: B010

        assert parses == 2, "one parse per call, not one cached result"
        assert first["X-A"] == "1"
        assert first is not second


class TestHTTPResponse:
    """The response rows: metadata is O(1), body reads are O(amt)."""

    REPLY = b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\nX-A: 1\r\nX-A: 2\r\n\r\nhello world"

    def test_metadata_is_parsed_before_the_body(self) -> None:
        response = response_over(self.REPLY)

        assert response.status == 200
        assert response.reason == "OK"
        assert response.version == 11
        assert response.getcode() == 200

    def test_headers_and_msg_are_the_same_object(self) -> None:
        """Both names, one parse - which is why each is O(1)."""
        response = response_over(self.REPLY)

        assert response.headers is response.msg

    def test_read_returns_the_whole_body(self) -> None:
        response = response_over(self.REPLY)

        assert response.read() == b"hello world"

    def test_read_with_an_amount_bounds_the_result(self) -> None:
        response = response_over(self.REPLY)

        assert response.read(5) == b"hello"
        assert response.read(6) == b" world"

    def test_readinto_fills_a_buffer_the_caller_owns(self) -> None:
        """O(1) space: the data lands in an existing buffer."""
        response = response_over(self.REPLY)
        buffer = bytearray(11)

        count = response.readinto(buffer)

        assert count == 11
        assert bytes(buffer) == b"hello world"

    def test_peek_does_not_consume(self) -> None:
        response = response_over(self.REPLY)

        peeked = response.peek(5)

        assert peeked.startswith(b"hello")
        assert response.read(5) == b"hello"

    def test_readline_and_read1_work_over_the_body(self) -> None:
        response = response_over(self.REPLY)

        assert response.readline() == b"hello world"
        assert response.read1(3) == b""

    def test_getheader_joins_repeats(self) -> None:
        response = response_over(self.REPLY)

        assert response.getheader("X-A") == "1, 2"
        assert response.getheader("absent", "fallback") == "fallback"

    def test_getheaders_lists_every_pair_without_copying(self) -> None:
        response = response_over(self.REPLY)
        stored = getattr(response.headers, "_headers")  # noqa: B009 - email internals

        pairs = response.getheaders()

        assert [name for name, _ in pairs].count("X-A") == 2
        assert pairs[0][1] is stored[0][1], "the values are the stored strings"

    def test_close_and_state_accessors(self) -> None:
        response = response_over(self.REPLY)

        assert response.readable() is True
        assert response.flush() is None
        response.close()
        assert response.isclosed() is True

    def test_fileno_delegates_to_the_stream(self) -> None:
        """Over a real socket that stream's descriptor is the socket's."""
        response = response_over(self.REPLY)

        with pytest.raises(io.UnsupportedOperation):
            response.fileno()

    def test_the_url_argument_is_accepted_and_discarded(self) -> None:
        """http.client never assigns it, so geturl() raises here; urllib sets it."""
        given = http.client.HTTPResponse(
            FakeSocket(self.REPLY),  # type: ignore[arg-type]
            url="https://example.com/x",
        )
        given.begin()

        assert not hasattr(given, "url")
        with pytest.raises(AttributeError):
            given.geturl()

        given.url = "https://example.com/x"  # what urllib.request does
        assert given.geturl() == "https://example.com/x"

    def test_info_returns_the_parsed_headers(self) -> None:
        response = response_over(self.REPLY)

        assert response.info() is response.headers

    def test_the_class_has_no_raw_attribute(self) -> None:
        """Recorded in the docstring: the audit lists a name CPython lacks."""
        assert not hasattr(http.client.HTTPResponse, "raw")


class TestHTTPMessage:
    """`HTTPMessage[name]` | O(h + v) | A scan of the names, not a dict lookup."""

    def message(self) -> Any:
        return http.client.parse_headers(io.BytesIO(b"A: 1\r\nB: 2\r\nA: 3\r\n\r\n"))

    def test_lookup_finds_the_first_match(self) -> None:
        assert self.message()["A"] == "1"

    def test_it_is_an_email_message(self) -> None:
        import email.message

        assert isinstance(self.message(), email.message.Message)

    def test_lookup_scans_rather_than_indexes(self) -> None:
        """A dict would not keep two headers of the same name; a list does."""
        message = self.message()

        assert message.get_all("A") == ["1", "3"]
        assert len(message.keys()) == 3

    def test_lookup_is_case_insensitive(self) -> None:
        assert self.message()["a"] == "1"

    def test_an_ascii_value_is_handed_back_not_copied(self) -> None:
        """The result is the stored string, not a copy.

        That is what the fetch rows mean by handing the value back; their O(v)
        space is the transient the policy's undecodable-byte scan makes, which
        identity here does not and cannot exclude.
        """
        message = self.message()
        stored = getattr(message, "_headers")  # noqa: B009 - email internals

        assert message["A"] is stored[0][1]
        assert message.items()[0][1] is stored[0][1]
        assert message.keys()[0] is stored[0][0]

    def test_getallmatchingheaders_never_matches(self) -> None:
        """It compares bare names against a `name:` pattern, so nothing hits."""
        message = self.message()

        assert message.getallmatchingheaders("A") == []
        assert message.getallmatchingheaders("absent") == []
        assert message.get_all("A") == ["1", "3"], "get_all is the working spelling"

    def test_defects_is_present_and_empty_for_clean_input(self) -> None:
        assert self.message().defects == []


class TestClientExceptions:
    """The exception rows: O(1), except that IncompleteRead keeps what it read."""

    def test_the_hierarchy_is_what_the_page_groups(self) -> None:
        for name in (
            "NotConnected",
            "InvalidURL",
            "UnknownProtocol",
            "UnknownTransferEncoding",
            "UnimplementedFileMode",
            "BadStatusLine",
            "LineTooLong",
            "RemoteDisconnected",
            "ImproperConnectionState",
            "CannotSendRequest",
            "CannotSendHeader",
            "ResponseNotReady",
            "IncompleteRead",
        ):
            assert issubclass(getattr(http.client, name), http.client.HTTPException), name

    def test_the_connection_state_errors_share_a_base(self) -> None:
        for name in ("CannotSendRequest", "CannotSendHeader", "ResponseNotReady"):
            assert issubclass(getattr(http.client, name), http.client.ImproperConnectionState)

    def test_incomplete_read_retains_the_partial_body(self) -> None:
        """O(r) space: catching it near a large body keeps that body alive."""
        error = http.client.IncompleteRead(b"x" * 1000, 5000)

        assert error.partial == b"x" * 1000
        assert error.expected == 5000
        assert len(error.partial) == 1000

    def test_remote_disconnected_is_also_a_connection_error(self) -> None:
        assert issubclass(http.client.RemoteDisconnected, ConnectionResetError)


class TestServerClasses:
    """The server rows, including the 3.14 TLS variants."""

    def test_the_plain_servers_exist_everywhere(self) -> None:
        assert issubclass(http.server.ThreadingHTTPServer, http.server.HTTPServer)

    def test_the_tls_servers_are_3_14_plus(self) -> None:
        present = hasattr(http.server, "HTTPSServer")

        assert present == (sys.version_info >= (3, 14))
        assert hasattr(http.server, "ThreadingHTTPSServer") == present

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="HTTPSServer is 3.14+")
    def test_the_tls_servers_extend_the_plain_ones(self) -> None:
        https = getattr(http.server, "HTTPSServer")  # noqa: B009 - typeshed 3.14+
        threading_https = getattr(http.server, "ThreadingHTTPSServer")  # noqa: B009 - 3.14+

        assert issubclass(https, http.server.HTTPServer)
        assert issubclass(threading_https, https)

    def test_threading_servers_are_configured_to_thread(self) -> None:
        import socketserver

        assert issubclass(http.server.ThreadingHTTPServer, socketserver.ThreadingMixIn)
        assert http.server.ThreadingHTTPServer.daemon_threads is True

    def test_allow_reuse_address_is_set(self) -> None:
        assert http.server.HTTPServer.allow_reuse_address == 1


class HandlerHarness(http.server.SimpleHTTPRequestHandler):
    """A handler with no socket: only what the tested methods touch."""

    def __init__(self, directory: str, path: str = "/") -> None:
        self.directory = directory
        self.path = path
        self.wfile = io.BytesIO()  # type: ignore[assignment]
        self.rfile = io.BytesIO()  # type: ignore[assignment]
        self.request_version = "HTTP/1.1"
        self.client_address = ("127.0.0.1", 12345)
        self.sent: list[tuple[str, Any, Any]] = []
        self._headers_buffer: list[bytes] = []

    def send_response(self, code: Any, message: Any = None) -> None:
        self.sent.append(("response", code, message))

    def send_header(self, keyword: str, value: str) -> None:
        self.sent.append(("header", keyword, value))

    def end_headers(self) -> None:
        self.sent.append(("end", None, None))

    def log_message(self, format: str, *args: Any) -> None:
        pass


class TestDirectoryListing:
    """`list_directory(path)` | O(k·L·log k + n) | Two stats per entry."""

    def populated(self, root: pathlib.Path, files: int = 20) -> HandlerHarness:
        for index in range(files):
            (root / f"file{index:02d}.txt").write_text("x")
        (root / "sub").mkdir()
        return HandlerHarness(str(root))

    def test_it_stats_every_entry_twice(self, tmp_path: pathlib.Path) -> None:
        handler = self.populated(tmp_path)
        entries = 21
        isdir_calls = 0
        islink_calls = 0
        real_isdir, real_islink = os.path.isdir, os.path.islink

        def counting_isdir(path: Any) -> bool:
            nonlocal isdir_calls
            isdir_calls += 1
            return real_isdir(path)

        def counting_islink(path: Any) -> bool:
            nonlocal islink_calls
            islink_calls += 1
            return real_islink(path)

        server_os = getattr(http.server, "os")  # noqa: B009 - the module's own import
        server_os.path.isdir = counting_isdir
        server_os.path.islink = counting_islink
        try:
            body = handler.list_directory(str(tmp_path))
        finally:
            server_os.path.isdir = real_isdir
            server_os.path.islink = real_islink

        assert isdir_calls == entries, "the isdir substitution must have been reached"
        assert islink_calls == entries, "the islink substitution must have been reached"
        assert body is not None

    def test_the_listing_is_built_whole_before_it_is_sent(self, tmp_path: pathlib.Path) -> None:
        """O(k·L) space: the answer is one buffer, not a stream of the entries."""
        handler = self.populated(tmp_path)

        body = handler.list_directory(str(tmp_path))

        assert body is not None
        html = body.read().decode()
        assert html.count("<li><a href=") == 21
        length = next(value for kind, key, value in handler.sent if key == "Content-Length")
        assert int(length) == len(html.encode())

    def test_entries_are_sorted_case_insensitively(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "Beta.txt").write_text("x")
        (tmp_path / "alpha.txt").write_text("x")
        handler = HandlerHarness(str(tmp_path))

        body = handler.list_directory(str(tmp_path))

        assert body is not None
        html = body.read().decode()
        assert html.index("alpha.txt") < html.index("Beta.txt")

    def test_an_unreadable_directory_sends_an_error(self, tmp_path: pathlib.Path) -> None:
        handler = HandlerHarness(str(tmp_path))
        errors: list[Any] = []
        handler.send_error = lambda *args, **kwargs: errors.append(args)  # type: ignore[method-assign]

        assert handler.list_directory(str(tmp_path / "absent")) is None
        assert errors


class TestPathTranslation:
    """`translate_path(path)` | O(n·s) | Drops components that are not names."""

    def handler(self, root: pathlib.Path) -> HandlerHarness:
        return HandlerHarness(str(root))

    def test_a_plain_path_joins_onto_the_root(self, tmp_path: pathlib.Path) -> None:
        translated = self.handler(tmp_path).translate_path("/a/b/c.txt")

        assert translated == os.path.join(str(tmp_path), "a", "b", "c.txt")

    def test_traversal_components_are_dropped(self, tmp_path: pathlib.Path) -> None:
        """A lexical check on the request text; symlinks are not its concern."""
        translated = self.handler(tmp_path).translate_path("/../../etc/passwd")

        assert translated == os.path.join(str(tmp_path), "etc", "passwd")
        assert str(tmp_path) in translated

    def test_a_symlink_inside_the_root_still_resolves_outside_it(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Why the row says the check is on the path text, not the filesystem."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("s")
        root = tmp_path / "root"
        root.mkdir()
        (root / "link").symlink_to(outside)

        translated = self.handler(root).translate_path("/link/secret.txt")

        assert translated.startswith(str(root))
        assert pathlib.Path(translated).resolve() == (outside / "secret.txt").resolve()

    def test_query_and_fragment_are_dropped(self, tmp_path: pathlib.Path) -> None:
        translated = self.handler(tmp_path).translate_path("/a.txt?x=1#f")

        assert translated == os.path.join(str(tmp_path), "a.txt")

    def test_a_trailing_slash_survives_normalisation(self, tmp_path: pathlib.Path) -> None:
        translated = self.handler(tmp_path).translate_path("/dir/")

        assert translated.endswith("/")

    def test_percent_escapes_are_decoded(self, tmp_path: pathlib.Path) -> None:
        translated = self.handler(tmp_path).translate_path("/a%20b.txt")

        assert translated.endswith("a b.txt")


class TestContentTypeGuessing:
    """`guess_type(path)` | O(n) | Split the extension off, then look it up."""

    def test_known_extensions_resolve(self, tmp_path: pathlib.Path) -> None:
        handler = HandlerHarness(str(tmp_path))

        assert handler.guess_type("x.txt").startswith("text/plain")
        assert handler.guess_type("x.png") == "image/png"

    def test_an_unknown_extension_falls_back(self, tmp_path: pathlib.Path) -> None:
        handler = HandlerHarness(str(tmp_path))

        assert handler.guess_type("x.zzz") == "application/octet-stream"

    def test_extensions_map_overrides_mimetypes(self, tmp_path: pathlib.Path) -> None:
        """The map is checked before mimetypes, so an entry in it wins."""
        handler = HandlerHarness(str(tmp_path))

        assert handler.extensions_map[".gz"] == "application/gzip"
        assert handler.guess_type("x.gz") == "application/gzip"

    def test_index_pages_is_3_12_plus(self) -> None:
        present = hasattr(http.server.SimpleHTTPRequestHandler, "index_pages")

        assert present == (sys.version_info >= (3, 12))
        if present:
            pages = getattr(http.server.SimpleHTTPRequestHandler, "index_pages")  # noqa: B009
            assert "index.html" in pages


class TestResponseHeaderBuffering:
    """`end_headers()` | Joins the buffer and writes it once."""

    def handler(self) -> Any:
        handler = http.server.BaseHTTPRequestHandler.__new__(http.server.BaseHTTPRequestHandler)
        handler.wfile = io.BytesIO()
        handler.request_version = "HTTP/1.1"
        setattr(handler, "_headers_buffer", [])  # noqa: B010 - not in typeshed
        return handler

    def test_send_header_writes_nothing_until_the_end(self) -> None:
        handler = self.handler()

        for index in range(50):
            handler.send_header(f"X-{index}", "v")

        assert handler.wfile.getvalue() == b""
        assert len(handler._headers_buffer) == 50

    def test_end_headers_flushes_in_one_write(self) -> None:
        """Counting writes, not bytes: per-header writes would pass on bytes."""
        handler = self.handler()
        writes: list[bytes] = []

        class CountingStream(io.BytesIO):
            def write(self, data: Any) -> int:
                writes.append(bytes(data))
                return len(data)

        handler.wfile = CountingStream()
        for index in range(50):
            handler.send_header(f"X-{index}", "v")
        assert writes == [], "buffering means nothing is written yet"

        handler.end_headers()

        assert len(writes) == 1, f"one flush, not one per header: {len(writes)}"
        assert writes[0].count(b"\r\n") == 51

    def test_class_attributes_are_what_the_page_says(self) -> None:
        handler_class = http.server.BaseHTTPRequestHandler

        assert handler_class.protocol_version == "HTTP/1.0"
        assert handler_class.error_content_type.startswith("text/html")
        assert "%(code)d" in handler_class.error_message_format
        assert handler_class.responses[http.HTTPStatus.NOT_FOUND][0] == "Not Found"

    def test_the_date_helpers_format_without_lookups(self) -> None:
        handler = self.handler()

        assert http.server.BaseHTTPRequestHandler.date_time_string(handler, 0).endswith("GMT")
        assert isinstance(http.server.BaseHTTPRequestHandler.log_date_time_string(handler), str)

    def test_address_string_returns_the_stored_address(self) -> None:
        """O(1): no reverse name lookup."""
        handler = self.handler()
        handler.client_address = ("192.0.2.1", 4321)

        assert http.server.BaseHTTPRequestHandler.address_string(handler) == "192.0.2.1"


class TestCGIHandler:
    """Deprecated since 3.13, removed in 3.15."""

    def test_it_is_present_on_every_supported_version(self) -> None:
        assert issubclass(http.server.CGIHTTPRequestHandler, http.server.SimpleHTTPRequestHandler)

    def test_it_has_the_documented_attributes(self) -> None:
        assert isinstance(http.server.CGIHTTPRequestHandler.cgi_directories, list)
        assert hasattr(http.server.CGIHTTPRequestHandler, "do_POST")

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="deprecated from 3.13")
    def test_constructing_it_warns_and_names_the_removal(self) -> None:
        """The warning is raised by __init__, before the handler is set up."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with contextlib.suppress(TypeError):
                http.server.CGIHTTPRequestHandler()  # type: ignore[call-arg]

        messages = [
            str(entry.message) for entry in caught if issubclass(entry.category, DeprecationWarning)
        ]

        assert messages, "constructing the handler must warn"
        assert "3.15" in messages[0]

    def test_it_does_not_warn_before_3_13(self) -> None:
        if sys.version_info >= (3, 13):
            pytest.skip("deprecated from 3.13")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with contextlib.suppress(TypeError):
                http.server.CGIHTTPRequestHandler()  # type: ignore[call-arg]

        assert not [e for e in caught if issubclass(e.category, DeprecationWarning)]


class TestCookieParsing:
    """`BaseCookie.load(rawdata)` | O(n) | Parsed whole, then applied."""

    def test_a_valid_string_loads_every_pair(self) -> None:
        cookie = http.cookies.SimpleCookie()

        cookie.load("session=abc123; user=alice")

        assert sorted(cookie.keys()) == ["session", "user"]
        assert cookie["session"].value == "abc123"

    def test_an_invalid_tail_discards_the_valid_head(self) -> None:
        """Not a partial result: nothing is applied when the parse stops."""
        cookie = http.cookies.SimpleCookie()

        cookie.load("session=abc123; user=alice; path")

        assert list(cookie.keys()) == []

    def test_a_bare_flag_is_accepted(self) -> None:
        """The control: `secure` is a flag, so the same shape does load."""
        cookie = http.cookies.SimpleCookie()

        cookie.load("session=abc123; user=alice; secure")

        assert sorted(cookie.keys()) == ["session", "user"]

    def test_loading_twice_accumulates(self) -> None:
        cookie = http.cookies.SimpleCookie()
        cookie.load("a=1")

        cookie.load("b=2")

        assert sorted(cookie.keys()) == ["a", "b"]

    def test_attributes_attach_to_the_preceding_cookie(self) -> None:
        cookie = http.cookies.SimpleCookie()

        cookie.load("a=1; Path=/x; b=2")

        assert cookie["a"]["path"] == "/x"
        assert cookie["b"]["path"] == ""

    def test_output_is_one_line_per_cookie(self) -> None:
        """`output()` | O(c·L·log c + c·v) | Sorted by name, one line each."""
        cookie = http.cookies.SimpleCookie()
        cookie.load("; ".join(f"k{index}=v{index}" for index in range(5)))

        lines = cookie.output().splitlines()

        assert len(lines) == 5
        assert all(line.startswith("Set-Cookie: ") for line in lines)

    def test_js_output_wraps_the_same_content(self) -> None:
        cookie = http.cookies.SimpleCookie()
        cookie.load("a=1")

        rendered = cookie.js_output()

        assert "<script" in rendered
        assert "document.cookie" in rendered

    def test_simple_cookie_quotes_and_unquotes(self) -> None:
        """`value_encode` / `value_decode` | O(v)."""
        cookie = http.cookies.SimpleCookie()

        value, coded = cookie.value_encode('a b"c')

        assert value == 'a b"c'
        assert coded.startswith('"') and coded.endswith('"')
        assert cookie.value_decode(coded) == (value, coded)

    def test_base_cookie_passes_the_value_through(self) -> None:
        """The control for the row: only SimpleCookie quotes."""
        base = http.cookies.BaseCookie()

        assert base.value_encode("plain") == ("plain", "plain")


class TestMorsel:
    """The Morsel rows: a fixed key set, so every accessor is O(1)."""

    def test_only_reserved_keys_are_accepted(self) -> None:
        morsel = http.cookies.Morsel()

        morsel["path"] = "/x"

        assert morsel["path"] == "/x"
        with pytest.raises(http.cookies.CookieError):
            morsel["unreserved"] = "x"

    def test_is_reserved_key_is_case_insensitive(self) -> None:
        morsel = http.cookies.Morsel()

        assert morsel.isReservedKey("path") is True
        assert morsel.isReservedKey("Path") is True
        assert morsel.isReservedKey("nope") is False

    def test_the_key_set_is_fixed(self) -> None:
        """Why the accessors do not grow with anything."""
        morsel = http.cookies.Morsel()

        reserved = getattr(http.cookies.Morsel, "_reserved")  # noqa: B009 - class private

        assert len(morsel.keys()) == len(reserved)

    def test_set_stores_both_forms_of_the_value(self) -> None:
        morsel = http.cookies.Morsel()

        morsel.set("name", "value", '"value"')

        assert morsel.key == "name"
        assert morsel.value == "value"
        assert morsel.coded_value == '"value"'

    def test_copy_is_independent(self) -> None:
        morsel = http.cookies.Morsel()
        morsel.set("name", "value", "value")
        morsel["path"] = "/a"

        duplicate = morsel.copy()
        duplicate["path"] = "/b"

        assert duplicate is not morsel
        assert isinstance(duplicate, http.cookies.Morsel)
        assert morsel["path"] == "/a"
        assert duplicate["path"] == "/b"

    def test_update_stores_and_rejects_unreserved_keys(self) -> None:
        morsel = http.cookies.Morsel()

        morsel.update({"path": "/x"})

        assert morsel["path"] == "/x"
        with pytest.raises(http.cookies.CookieError):
            morsel.update({"unreserved": "x"})

    def test_setdefault_never_stores(self) -> None:
        """Every reserved key already exists empty, so the default never lands."""
        morsel = http.cookies.Morsel()

        returned = morsel.setdefault("domain", "example.com")

        assert returned == ""
        assert morsel["domain"] == ""
        with pytest.raises(http.cookies.CookieError):
            morsel.setdefault("unreserved", "x")

    def test_output_string_lists_the_attributes_set(self) -> None:
        morsel = http.cookies.Morsel()
        morsel.set("name", "value", "value")
        morsel["path"] = "/x"
        morsel["secure"] = True

        rendered = morsel.OutputString()

        assert rendered.startswith("name=value")
        assert "Path=/x" in rendered
        assert "Secure" in rendered

    def test_the_reserved_names_are_keys_not_attributes(self) -> None:
        """`morsel.path` raises; only key, value and coded_value are attributes."""
        morsel = http.cookies.Morsel()

        assert morsel["path"] == ""
        assert not hasattr(morsel, "path")
        assert not hasattr(morsel, "expires")
        for name in ("key", "value", "coded_value"):
            assert hasattr(morsel, name), name

    def test_max_age_is_spelled_with_a_dash(self) -> None:
        reserved = getattr(http.cookies.Morsel, "_reserved")  # noqa: B009 - class private

        assert "max-age" in reserved
        assert "max_age" not in reserved

    def test_partitioned_is_3_14_plus(self) -> None:
        reserved = getattr(http.cookies.Morsel, "_reserved")  # noqa: B009 - class private
        present = "partitioned" in reserved

        assert present == (sys.version_info >= (3, 14))

    def test_the_documented_attributes_exist(self) -> None:
        morsel = http.cookies.Morsel()

        reserved = getattr(http.cookies.Morsel, "_reserved")  # noqa: B009 - class private

        for name in (
            "expires",
            "path",
            "comment",
            "domain",
            "secure",
            "httponly",
            "samesite",
            "version",
        ):
            assert name in reserved, name
            assert morsel[name] == ""


def stored_cookie(domain: str, path: str, name: str, **kwargs: Any) -> http.cookiejar.Cookie:
    fields: dict[str, Any] = {
        "version": 0,
        "name": name,
        "value": "v",
        "port": None,
        "port_specified": False,
        "domain": domain,
        "domain_specified": True,
        "domain_initial_dot": domain.startswith("."),
        "path": path,
        "path_specified": True,
        "secure": False,
        "expires": None,
        "discard": False,
        "comment": None,
        "comment_url": None,
        "rest": {},
    }
    fields.update(kwargs)
    return http.cookiejar.Cookie(**fields)


class CountingPolicy(http.cookiejar.DefaultCookiePolicy):
    """Records how often the jar asks about each level."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.domain_calls = 0
        self.path_calls = 0
        self.return_calls = 0

    def domain_return_ok(self, domain: str, request: Any) -> bool:
        self.domain_calls += 1
        return super().domain_return_ok(domain, request)

    def path_return_ok(self, path: str, request: Any) -> bool:
        self.path_calls += 1
        return super().path_return_ok(path, request)

    def return_ok(self, cookie: Any, request: Any) -> bool:
        self.return_calls += 1
        return super().return_ok(cookie, request)


class TestJarLookup:
    """`add_cookie_header` | O(d·g + P + a + m log m + m·v + c + e) | One check per level."""

    def filled(self, policy: Any = None, sites: int = 5, paths: int = 3) -> Any:
        jar = http.cookiejar.CookieJar(policy=policy)
        for site in range(sites):
            for path in range(paths):
                jar.set_cookie(stored_cookie(f".host{site}.example.com", f"/p{path}", "n"))
        return jar

    def test_the_jar_asks_once_per_level_not_once_per_cookie(self) -> None:
        policy = CountingPolicy()
        jar = self.filled(policy)
        assert len(jar) == 15

        request = urllib.request.Request("https://host0.example.com/p0/page")
        jar.add_cookie_header(request)

        assert policy.domain_calls == 5, "one call per stored domain"
        assert policy.path_calls == 3, "only the matching domain's paths"
        assert policy.return_calls == 1, "only the matching path's cookies"
        assert request.get_header("Cookie") == "n=v"

    def test_more_cookies_under_one_path_do_not_change_the_domain_calls(self) -> None:
        """Separates the d term from the c term at a fixed domain count."""
        policy = CountingPolicy()
        jar = http.cookiejar.CookieJar(policy=policy)
        for index in range(20):
            jar.set_cookie(stored_cookie(".host0.example.com", "/", f"n{index}"))

        jar.add_cookie_header(urllib.request.Request("https://host0.example.com/page"))

        assert policy.domain_calls == 1
        assert policy.path_calls == 1
        assert policy.return_calls == 20

    def test_it_sweeps_every_cookie_for_expiry_afterwards(self) -> None:
        """The c term: selection skips domains, the expiry sweep does not."""
        jar = self.filled()
        calls = 0
        real = http.cookiejar.Cookie.is_expired

        def counting(self: Any, now: Any = None) -> bool:
            nonlocal calls
            calls += 1
            return real(self, now)

        http.cookiejar.Cookie.is_expired = counting  # type: ignore[method-assign]
        try:
            jar.add_cookie_header(urllib.request.Request("https://host0.example.com/p0/x"))
        finally:
            http.cookiejar.Cookie.is_expired = real  # type: ignore[method-assign]

        assert calls == 16, "15 stored cookies swept, plus the one return_ok check"

    def test_the_sweep_actually_drops_expired_cookies(self) -> None:
        """The control: the sweep is real work, not an unused code path."""
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".host0.example.com", "/", "keep"))
        jar.set_cookie(stored_cookie(".other.example.com", "/", "stale", expires=1))

        jar.add_cookie_header(urllib.request.Request("https://host0.example.com/"))

        assert [cookie.name for cookie in jar] == ["keep"], "an unrelated domain was swept"

    def test_selected_cookies_are_sorted_longest_path_first(self) -> None:
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".host.example.com", "/", "short"))
        jar.set_cookie(stored_cookie(".host.example.com", "/a/b/c", "long"))
        jar.set_cookie(stored_cookie(".host.example.com", "/a", "mid"))

        request = urllib.request.Request("https://host.example.com/a/b/c/page")
        jar.add_cookie_header(request)

        header = request.get_header("Cookie")
        assert header is not None
        assert [pair.split("=")[0] for pair in header.split("; ")] == ["long", "mid", "short"]

    def test_len_and_iteration_walk_the_structure(self) -> None:
        jar = self.filled()

        assert len(jar) == 15
        assert len(list(jar)) == 15


class TestJarMutation:
    """set_cookie, the clear family, and extraction."""

    def test_set_cookie_places_it_by_domain_path_and_name(self) -> None:
        jar = http.cookiejar.CookieJar()

        jar.set_cookie(stored_cookie(".x.example.com", "/p", "n"))

        assert len(jar) == 1
        stored = getattr(jar, "_cookies")  # noqa: B009 - jar internals
        assert stored[".x.example.com"]["/p"]["n"].value == "v"

    def test_a_fully_specified_clear_removes_one(self) -> None:
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".x.example.com", "/", "n1"))
        jar.set_cookie(stored_cookie(".y.example.com", "/", "n2"))

        jar.clear(".x.example.com", "/", "n1")

        assert len(jar) == 1

    def test_clearing_an_absent_cookie_raises(self) -> None:
        jar = http.cookiejar.CookieJar()

        with pytest.raises(KeyError):
            jar.clear(".absent.example.com", "/", "n")

    def test_a_bare_clear_drops_everything(self) -> None:
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".x.example.com", "/", "n"))

        jar.clear()

        assert len(jar) == 0

    def test_clear_session_cookies_walks_for_the_discard_flag(self) -> None:
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".x.example.com", "/", "keep"))
        jar.set_cookie(stored_cookie(".x.example.com", "/", "drop", discard=True))

        jar.clear_session_cookies()

        assert [cookie.name for cookie in jar] == ["keep"]

    def test_clear_expired_cookies_walks_against_the_clock(self) -> None:
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".x.example.com", "/", "keep", expires=None))
        jar.set_cookie(stored_cookie(".x.example.com", "/", "gone", expires=1))

        jar.clear_expired_cookies()

        assert [cookie.name for cookie in jar] == ["keep"]

    def test_extract_cookies_parses_and_stores(self) -> None:
        jar = http.cookiejar.CookieJar()
        request = urllib.request.Request("https://host.example.com/")
        response = http.client.parse_headers(
            io.BytesIO(b"Set-Cookie: a=1; Path=/\r\nSet-Cookie: b=2; Path=/\r\n\r\n")
        )

        jar.extract_cookies(FakeResponse(response), request)  # type: ignore[arg-type]

        assert sorted(cookie.name for cookie in jar) == ["a", "b"]

    def test_make_cookies_parses_without_storing(self) -> None:
        jar = http.cookiejar.CookieJar()
        request = urllib.request.Request("https://host.example.com/")
        response = http.client.parse_headers(io.BytesIO(b"Set-Cookie: a=1; Path=/\r\n\r\n"))

        made = jar.make_cookies(FakeResponse(response), request)  # type: ignore[arg-type]

        assert [cookie.name for cookie in made] == ["a"]
        assert len(jar) == 0

    def test_set_policy_replaces_the_policy(self) -> None:
        jar = http.cookiejar.CookieJar()
        policy = http.cookiejar.DefaultCookiePolicy()

        jar.set_policy(policy)

        assert getattr(jar, "_policy") is policy  # noqa: B009 - jar internals


class FakeResponse:
    """The two methods CookieJar asks a response for."""

    def __init__(self, message: Any) -> None:
        self._message = message

    def info(self) -> Any:
        return self._message


class TestCookieAttributes:
    """The Cookie rows: plain attributes and a dict of the rest."""

    def test_the_documented_attributes_are_set_at_construction(self) -> None:
        cookie = stored_cookie(".x.example.com", "/p", "n")

        assert cookie.name == "n"
        assert cookie.value == "v"
        assert cookie.domain == ".x.example.com"
        assert cookie.path == "/p"
        assert cookie.port is None
        assert cookie.secure is False
        assert cookie.expires is None
        assert cookie.discard is False
        assert cookie.comment is None
        assert cookie.comment_url is None
        assert cookie.version == 0
        assert cookie.port_specified is False
        assert cookie.domain_specified is True
        assert cookie.domain_initial_dot is True

    def test_rfc2109_defaults_off(self) -> None:
        assert stored_cookie(".x.example.com", "/", "n").rfc2109 is False

    def test_is_expired_compares_against_now(self) -> None:
        assert stored_cookie(".x.example.com", "/", "n", expires=1).is_expired() is True
        assert stored_cookie(".x.example.com", "/", "n").is_expired() is False

    def test_nonstandard_attributes_are_a_dict(self) -> None:
        cookie = stored_cookie(".x.example.com", "/", "n")

        assert cookie.has_nonstandard_attr("custom") is False
        cookie.set_nonstandard_attr("custom", "value")
        assert cookie.has_nonstandard_attr("custom") is True
        assert cookie.get_nonstandard_attr("custom") == "value"
        assert cookie.get_nonstandard_attr("absent", "fallback") == "fallback"


class TestPolicyDomainLists:
    """`blocked_domains()` | O(1) | Returns the stored tuple itself."""

    def test_it_returns_the_same_object_each_time(self) -> None:
        """Identity: nothing is copied, so the caller holds the policy's tuple."""
        policy = http.cookiejar.DefaultCookiePolicy()
        policy.set_blocked_domains(["a.example.com", "b.example.com"])

        assert policy.blocked_domains() is policy.blocked_domains()

    def test_the_sequence_is_converted_to_a_tuple_once(self) -> None:
        policy = http.cookiejar.DefaultCookiePolicy()
        source = ["a.example.com"]

        policy.set_blocked_domains(source)

        assert isinstance(policy.blocked_domains(), tuple)
        assert policy.blocked_domains() is not source

    def test_allowed_domains_defaults_to_none(self) -> None:
        policy = http.cookiejar.DefaultCookiePolicy()

        assert policy.allowed_domains() is None
        assert policy.is_not_allowed("anything.example.com") is False

    def test_allowed_domains_round_trips(self) -> None:
        policy = http.cookiejar.DefaultCookiePolicy()

        policy.set_allowed_domains(["good.example.com"])

        assert policy.allowed_domains() is policy.allowed_domains()
        assert policy.is_not_allowed("good.example.com") is False
        assert policy.is_not_allowed("other.example.com") is True

    def test_is_blocked_scans_the_configured_domains(self) -> None:
        """O(g): the matcher is asked about each entry until one hits."""
        policy = http.cookiejar.DefaultCookiePolicy()
        policy.set_blocked_domains([f"site{index}.example.com" for index in range(10)])
        checked = 0
        real_match = getattr(http.cookiejar, "user_domain_match")  # noqa: B009 - not exported

        def counting_match(a: str, b: str) -> bool:
            nonlocal checked
            checked += 1
            return real_match(a, b)

        setattr(http.cookiejar, "user_domain_match", counting_match)  # noqa: B010
        try:
            assert policy.is_blocked("absent.example.net") is False
            misses = checked
            checked = 0
            assert policy.is_blocked("site0.example.com") is True
            hits = checked
        finally:
            setattr(http.cookiejar, "user_domain_match", real_match)  # noqa: B010

        assert misses == 10, "a miss compares against every configured domain"
        assert hits == 1, "a hit stops at the first match"

    def test_the_policy_flags_exist(self) -> None:
        policy = http.cookiejar.DefaultCookiePolicy()

        for name in (
            "strict_domain",
            "strict_rfc2965_unverifiable",
            "strict_ns_unverifiable",
            "strict_ns_domain",
            "strict_ns_set_initial_dollar",
            "strict_ns_set_path",
            "rfc2109_as_netscape",
        ):
            assert hasattr(policy, name), name
        assert policy.netscape is True
        assert policy.rfc2965 is False
        assert policy.hide_cookie2 is False

    def test_the_domain_strictness_flags_are_distinct_bits(self) -> None:
        values = [
            http.cookiejar.DefaultCookiePolicy.DomainStrictNoDots,
            http.cookiejar.DefaultCookiePolicy.DomainStrictNonDomain,
            http.cookiejar.DefaultCookiePolicy.DomainRFC2965Match,
        ]

        assert len(set(values)) == 3
        assert http.cookiejar.DefaultCookiePolicy.DomainLiberal == 0
        assert http.cookiejar.DefaultCookiePolicy.DomainStrict == values[0] | values[1]


class TestFileJars:
    """The FileCookieJar rows: one line per cookie, and what each format keeps."""

    def saved(self, jar_class: Any, path: pathlib.Path, **cookie_kwargs: Any) -> Any:
        jar = jar_class(str(path))
        jar.set_cookie(stored_cookie(".x.example.com", "/", "n", **cookie_kwargs))
        jar.save(ignore_discard=True, ignore_expires=True)
        return jar

    def test_a_jar_round_trips_through_a_file(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "cookies.txt"
        self.saved(http.cookiejar.MozillaCookieJar, target)

        reloaded = http.cookiejar.MozillaCookieJar(str(target))
        reloaded.load(ignore_discard=True, ignore_expires=True)

        assert [cookie.name for cookie in reloaded] == ["n"]
        assert reloaded.filename == str(target)
        assert reloaded.delayload is False

    def test_load_adds_to_what_is_already_held(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "cookies.txt"
        self.saved(http.cookiejar.MozillaCookieJar, target)
        jar = http.cookiejar.MozillaCookieJar(str(target))
        jar.set_cookie(stored_cookie(".y.example.com", "/", "other"))

        jar.load(ignore_discard=True, ignore_expires=True)

        assert sorted(cookie.name for cookie in jar) == ["n", "other"]

    def test_revert_clears_first(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "cookies.txt"
        jar = self.saved(http.cookiejar.MozillaCookieJar, target)
        jar.set_cookie(stored_cookie(".y.example.com", "/", "other"))

        jar.revert(ignore_discard=True, ignore_expires=True)

        assert [cookie.name for cookie in jar] == ["n"]

    def test_lwp_keeps_a_comment_and_mozilla_does_not(self, tmp_path: pathlib.Path) -> None:
        """The one difference between the two format rows."""
        lwp_path = tmp_path / "lwp.txt"
        moz_path = tmp_path / "moz.txt"
        self.saved(http.cookiejar.LWPCookieJar, lwp_path, comment="hello")
        self.saved(http.cookiejar.MozillaCookieJar, moz_path, comment="hello")

        lwp = http.cookiejar.LWPCookieJar(str(lwp_path))
        lwp.load(ignore_discard=True, ignore_expires=True)
        moz = http.cookiejar.MozillaCookieJar(str(moz_path))
        moz.load(ignore_discard=True, ignore_expires=True)

        assert next(iter(lwp)).comment == "hello"
        assert next(iter(moz)).comment is None

    def test_a_file_that_does_not_parse_raises_load_error(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "bad.txt"
        target.write_text("this is not a cookie file\n")
        jar = http.cookiejar.MozillaCookieJar(str(target))

        with pytest.raises(http.cookiejar.LoadError):
            jar.load()

    def test_saving_without_a_filename_raises(self) -> None:
        jar = http.cookiejar.MozillaCookieJar()

        with pytest.raises(ValueError):
            jar.save()


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
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
    """Every block runs: no example on this page needs a peer."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_no_block_reaches_the_network(self, tmp_path: pathlib.Path) -> None:
        """Enforced by breaking the socket, not by grepping for call names."""
        guard = (
            "import socket\n"
            "def _blocked(*args, **kwargs):\n"
            "    raise AssertionError('this example opened a socket')\n"
            "socket.socket.connect = _blocked\n"
            "socket.create_connection = _blocked\n"
            "socket.getaddrinfo = _blocked\n"
        )

        for line, source in _blocks():
            workdir = tmp_path / f"guard{line}"
            workdir.mkdir()
            result = _run(guard + source, workdir)
            assert result.returncode == 0, (
                f"{PAGE.name}:{line} failed under the socket guard: {result.stderr.strip()[-400:]}"
            )

    def test_the_socket_guard_catches_a_block_that_connects(self, tmp_path: pathlib.Path) -> None:
        """A guard that cannot fail would not enforce anything."""
        guard = (
            "import socket\n"
            "def _blocked(*args, **kwargs):\n"
            "    raise AssertionError('this example opened a socket')\n"
            "socket.socket.connect = _blocked\n"
            "socket.create_connection = _blocked\n"
            "socket.getaddrinfo = _blocked\n"
        )
        connecting = "import http.client\nhttp.client.HTTPConnection('example.com').connect()\n"

        result = _run(guard + connecting, tmp_path)

        assert result.returncode != 0
        assert "opened a socket" in result.stderr

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = next(source for _, source in _blocks() if "from http import" in source)
        broken = original.replace("from http import HTTPStatus", "from http import Missing", 1)
        assert broken != original, "the mutation did not reach the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr

    def test_the_runner_catches_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        """Execution alone would pass a block whose claim had been negated."""
        original = next(source for _, source in _blocks() if "assert HTTPStatus(404) is" in source)
        broken = original.replace(
            "assert HTTPStatus(404) is HTTPStatus.NOT_FOUND",
            "assert HTTPStatus(404) is not HTTPStatus.NOT_FOUND",
            1,
        )
        assert broken != original, "the mutation did not reach the assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr


class TestCodexReviewFindings:
    """Claims added while correcting the rows above, each pinned here."""

    def test_a_non_matching_tail_keeps_what_parsed(self) -> None:
        """Rejection is atomic; running out of matches is not."""
        partial = http.cookies.SimpleCookie()

        partial.load("session=abc123; ;;;")

        assert list(partial.keys()) == ["session"]

    def test_the_constructor_loads_its_argument(self) -> None:
        """Why the row splits empty construction from construction with data."""
        assert sorted(http.cookies.SimpleCookie("a=1; b=2").keys()) == ["a", "b"]
        assert list(http.cookies.SimpleCookie().keys()) == []

    def test_morsel_set_validates_the_name_and_keeps_the_value(self) -> None:
        """O(len(key) + v) time: the values are checked, then stored by reference."""
        morsel = http.cookies.Morsel()
        value = "v" * 1000

        morsel.set("name", value, value)

        assert morsel.value is value, "the value is stored, not copied"
        with pytest.raises(http.cookies.CookieError, match="reserved"):
            morsel.set("path", "v", "v")
        with pytest.raises(http.cookies.CookieError, match="Illegal"):
            morsel.set("bad name", "v", "v")
        with pytest.raises(http.cookies.CookieError, match="Control characters"):
            morsel.set("name", "bad\nvalue", "bad\nvalue")

    def test_getallmatchingheaders_builds_the_name_list_first(self) -> None:
        """O(h) space despite the empty result: keys() is materialized."""
        message = http.client.parse_headers(io.BytesIO(b"A: 1\r\nB: 2\r\n\r\n"))

        assert isinstance(message.keys(), list)
        assert len(message.keys()) == 2
        assert message.getallmatchingheaders("A") == []

    def test_the_two_endings_differ_on_the_same_prefix(self) -> None:
        """The control: identical valid prefix, opposite outcomes."""
        refused = http.cookies.SimpleCookie()
        refused.load("session=abc123; path")

        stopped = http.cookies.SimpleCookie()
        stopped.load("session=abc123; ;;;")

        assert list(refused.keys()) == [], "a reserved key with no value refuses the lot"
        assert list(stopped.keys()) == ["session"], "unmatchable junk just ends the parse"

    def test_cookie_output_is_sorted_by_name(self) -> None:
        """`output()` | O(c log c + c·v) | Sorted, not insertion order."""
        cookie = http.cookies.SimpleCookie()
        cookie.load("zeta=1; alpha=2; mid=3")

        names = [
            line.split("=")[0].removeprefix("Set-Cookie: ") for line in cookie.output().splitlines()
        ]

        assert names == ["alpha", "mid", "zeta"]
        assert list(cookie.keys()) != names, "insertion order differs, so the sort shows"

    def test_setdefault_stores_once_a_reserved_key_is_gone(self) -> None:
        """The qualification on the row: the full key set is what blocks it."""
        morsel = http.cookies.Morsel()
        del morsel["domain"]

        returned = morsel.setdefault("domain", "example.com")

        assert returned == "example.com"
        assert morsel["domain"] == "example.com"

    def test_guess_type_splits_the_path_before_it_looks_anything_up(self) -> None:
        """O(n): the extension has to be found and lowercased first."""
        handler = HandlerHarness("/tmp")

        assert handler.guess_type("x.PNG") == "image/png", "the lowercase pass runs"
        assert handler.guess_type("a/b/c/d/e.png") == "image/png"

    def test_translate_path_joins_component_by_component(self) -> None:
        """The n·s term: each join recopies the prefix built so far."""
        joins = 0
        server_os = getattr(http.server, "os")  # noqa: B009 - the module's own import
        real = server_os.path.join

        def counting(*parts: str) -> str:
            nonlocal joins
            joins += 1
            return real(*parts)

        server_os.path.join = counting
        try:
            HandlerHarness("/tmp").translate_path("/a/b/c/d/e/f")
        finally:
            server_os.path.join = real

        assert joins == 6, "one join per surviving component"

    def test_iterating_a_jar_defers_the_walk(self) -> None:
        """`iter(jar)` | O(1) | Nothing is visited before the first next().

        The walk reaches a level through `values()` on 3.11+ and through
        `keys()` on 3.10, which sorts them, so both are watched.
        """
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".x.example.com", "/", "n"))
        visited: list[int] = []

        class Watched(dict):  # type: ignore[type-arg]
            def values(self) -> Any:
                collected = list(super().values())
                visited.append(len(collected))
                return collected

            def keys(self) -> Any:
                collected = list(super().keys())
                visited.append(len(collected))
                return collected

        setattr(jar, "_cookies", Watched(getattr(jar, "_cookies")))  # noqa: B009,B010

        iterator = iter(jar)

        assert visited == [], "creating the iterator must visit nothing"
        assert next(iterator).name == "n"
        assert visited, "the walk starts on the first next()"

    def test_clearing_a_name_leaves_its_level_behind(self) -> None:
        """The e term on len(): emptied levels are not pruned."""
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(stored_cookie(".x.example.com", "/p", "n"))

        jar.clear(".x.example.com", "/p", "n")

        assert len(jar) == 0
        assert getattr(jar, "_cookies") == {".x.example.com": {"/p": {}}}  # noqa: B009

    def test_clearing_an_inner_level_without_an_outer_one_raises(self) -> None:
        jar = http.cookiejar.CookieJar()

        with pytest.raises(ValueError):
            jar.clear(path="/p", name="n")

    def test_lwp_does_not_preserve_rfc2109(self, tmp_path: pathlib.Path) -> None:
        """Why the row does not claim a full round trip."""
        target = tmp_path / "lwp.txt"
        jar = http.cookiejar.LWPCookieJar(str(target))
        cookie = stored_cookie(".x.example.com", "/", "n")
        cookie.rfc2109 = True
        jar.set_cookie(cookie)
        jar.save(ignore_discard=True, ignore_expires=True)

        back = http.cookiejar.LWPCookieJar(str(target))
        back.load(ignore_discard=True, ignore_expires=True)

        assert next(iter(back)).rfc2109 is False

    def test_revert_restores_the_old_jar_when_the_file_is_bad(self, tmp_path: pathlib.Path) -> None:
        """The deep copy earns its cost here; LoadError is an OSError."""
        target = tmp_path / "bad.txt"
        target.write_text("not a cookie file\n")
        jar = http.cookiejar.MozillaCookieJar(str(target))
        jar.set_cookie(stored_cookie(".x.example.com", "/", "keep"))

        with pytest.raises(http.cookiejar.LoadError):
            jar.revert()

        assert [cookie.name for cookie in jar] == ["keep"]
        assert issubclass(http.cookiejar.LoadError, OSError)

    def test_a_str_body_is_encoded_whole(self) -> None:
        """The O(q + b) space alternative on the request row."""
        connection, sock = connected()

        connection.request("POST", "/x", body="abc", headers={"Host": "example.com"})

        assert b"Content-Length: 3\r\n" in sock.sent[0]
        assert sock.sent[-1] == b"abc"

    def test_continue_responses_are_read_before_the_final_one(self) -> None:
        """Each skipped block is parsed under the same caps, so a call's cap is a multiple."""
        reply = (
            b"HTTP/1.1 100 Continue\r\nX-A: 1\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi"
        )

        response = response_over(reply)

        assert response.status == 200
        assert response.read() == b"hi"

    def test_only_100_is_skipped_not_every_1xx(self) -> None:
        """A 103 ends the loop and becomes the response; only 100 is interim."""
        reply = b"HTTP/1.1 103 Early Hints\r\n\r\nHTTP/1.1 200 OK\r\n\r\n"

        response = response_over(reply)

        assert response.status == 103, "103 is returned, not skipped"
        assert http.client.CONTINUE == 100

    def test_too_many_interim_responses_raise_where_the_cap_exists(self) -> None:
        """Gated on the constant, not a version: the cap arrived by backport.

        Of the pinned patches the project tests, 3.10.21, 3.11.16, 3.12.14 and
        3.14.7 have `_MAXINTERIMRESPONSES`; 3.13.14 does not. A version tuple
        would assert the wrong thing in the middle of the range.
        """
        cap = getattr(http.client, "_MAXINTERIMRESPONSES", None)  # patch-release cap
        if cap is None:
            pytest.skip("this patch release reads interim responses without a cap")
        final = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi"
        interim = b"HTTP/1.1 100 Continue\r\n\r\n"

        at_the_limit = response_over(interim * (cap - 1) + final)
        assert at_the_limit.status == 200, "99 interim responses still reach the real one"

        with pytest.raises(http.client.HTTPException, match="interim responses"):
            response_over(interim * cap + final)

    def test_cookie_application_can_fail_after_earlier_items_landed(self) -> None:
        """The third ending: the parser passes it, Morsel.set refuses it."""
        cookie = http.cookies.SimpleCookie()

        with pytest.raises(http.cookies.CookieError):
            cookie.load("session=abc123; bad@name=2")

        assert list(cookie.keys()) == ["session"]

    def test_lwp_keeps_the_port_and_mozilla_drops_it(self, tmp_path: pathlib.Path) -> None:
        """The stated difference between the two format rows."""
        results = {}
        for jar_class, name in (
            (http.cookiejar.LWPCookieJar, "lwp"),
            (http.cookiejar.MozillaCookieJar, "moz"),
        ):
            target = tmp_path / f"{name}.txt"
            jar = jar_class(str(target))
            jar.set_cookie(
                stored_cookie(".x.example.com", "/", "n", port="8080", port_specified=True)
            )
            jar.save(ignore_discard=True, ignore_expires=True)
            back = jar_class(str(target))
            back.load(ignore_discard=True, ignore_expires=True)
            results[name] = next(iter(back)).port

        assert results["lwp"] == "8080"
        assert results["moz"] is None

    def test_copyfile_streams_the_body(self, tmp_path: pathlib.Path) -> None:
        """O(b) time, O(1) space: it is asked for chunks, never the whole file."""
        source = tmp_path / "big.bin"
        source.write_bytes(b"x" * 100_000)
        handler = HandlerHarness(str(tmp_path))
        requested: list[Any] = []

        class WatchedFile(io.BytesIO):
            def read(self, amount: Any = -1, /) -> bytes:
                requested.append(amount)
                return super().read(amount)

        destination = io.BytesIO()
        handler.copyfile(WatchedFile(source.read_bytes()), destination)

        assert destination.getvalue() == b"x" * 100_000
        assert requested, "the substitution must have been reached"
        assert all(amount not in (-1, None) for amount in requested), (
            f"a whole-file read would defeat the streaming claim: {set(requested)}"
        )

    def test_the_jar_walk_materializes_each_level(self) -> None:
        """The w in the space column: a level is collected whole before descending.

        3.11+ copies the level's values; 3.10 sorts its keys instead. Either
        way the list built is as wide as the level, which is the w term.
        """
        jar = http.cookiejar.CookieJar()
        for index in range(20):
            jar.set_cookie(stored_cookie(".x.example.com", "/", f"n{index}"))
        widths: list[int] = []

        class Watched(dict):  # type: ignore[type-arg]
            def values(self) -> Any:
                collected = list(super().values())
                widths.append(len(collected))
                return collected

            def keys(self) -> Any:
                collected = list(super().keys())
                widths.append(len(collected))
                return collected

        inner = getattr(jar, "_cookies")[".x.example.com"]["/"]  # noqa: B009
        getattr(jar, "_cookies")[".x.example.com"]["/"] = Watched(inner)  # noqa: B009

        assert len(jar) == 20
        assert 20 in widths, f"the innermost level is collected whole: {widths}"
