"""Tests for docs/stdlib/email.md.

Lib/email: ``Parser.parse`` reads ``fp`` in 8192-character chunks into a
``FeedParser``, whose ``BufferedSubFile`` splits each chunk at line ends and
keeps the incomplete tail; ``readline`` pops one line and runs every
predicate on the ``_eofstack``, one boundary matcher per enclosing multipart,
against it. ``_parse_headers`` stores each header through
``policy.header_source_parse``, which joins the source lines and parses
nothing; with ``headersonly`` the body lines are joined into one string
payload. ``Message.__getitem__`` scans ``_headers`` lower-casing each name
and hands the first match to ``policy.header_fetch_parse``: ``Compat32``
runs ``_has_surrogates`` (a ``str.encode``) and returns the string, or a
``Header`` in ``unknown-8bit``; ``EmailPolicy`` returns an object that has a
``name`` and otherwise calls ``header_factory``, so a source value is parsed
on every fetch. ``__setitem__`` scans for existing headers only when
``header_max_count`` is not None, then appends what ``header_store_parse``
returns. ``get_payload`` fetches Content-Transfer-Encoding, and without
``decode`` scans the string for surrogates and returns it; ``set_payload``
stores a ``str`` and decodes ``bytes`` as ASCII with surrogateescape.
``EmailMessage._make_multipart`` partitions ``_headers`` by the ``content-``
prefix and moves the payload into a new part; ``_add_multipart`` calls the
``make_*`` method when the content type differs, builds a part and
``attach``es it. ``Generator._write`` renders each part into a fresh buffer
and copies it into the level above, and ``_handle_multipart`` buffers each
subpart once more, so a part's text passes through about 2d + 1 buffers;
``Message.walk`` is ``yield from subpart.walk()`` per subpart, one generator
frame per level; ``_handle_multipart`` generates a
boundary with ``_make_boundary(alltext)`` and stores it with
``set_boundary`` when there is none. ``_header_value_parser.get_unstructured``
and ``get_address_list`` slice the remainder of the value once per token;
``_refold_parse_tree`` does ``parts.pop(0)`` per token and, with no line
limit, ``lines[-1] += tstr`` per token; ``Header.encode`` feeds a
``_ValueFormatter`` whose ``_Accumulator.__len__`` sums its parts, once per
word, so one unbounded line costs the square of its words; ``decode_header``
concatenates consecutive same-charset words with ``bytes +=``.
``HeaderRegistry.__getitem__`` builds a class with ``type()`` per lookup.
``utils.make_msgid`` calls ``socket.getfqdn()`` when ``domain`` is None.

Observation settles most rows: header fetch and store counts through a
counting ``header_factory``; the identity of fetched strings, payloads,
attached and moved parts and content messages; the chunk sizes ``parse()``
requests; what ``HeaderParser`` leaves in the payload; the transfer encoding
``set_content()`` picks per input; the boundary ``flatten()`` stores; the
characters written through the generator's buffers at nesting depth 0 and
4 for one 100,000-character body (1.0 and 9.0 times the output); the
``set_param()`` calls ``set_type()`` makes; the exceptions each policy
raises; the defect lists; the ``getfqdn`` call count.

The stopwatch tests, on one interpreter each, best of five: parsing 50k and
200k body lines, near 4 for the linear row; the same 100k-line leaf at
nesting depth 0 and 16, 5.2 where a bound without the L·d term predicts 1;
fetching a 32,000-character Subject of 100 and 6,400 words under
``policy.default``, 18 where O(v) predicts 1; folding a parsed 2,000- and
8,000-word Subject (10.7);
``decode_header`` on 1,000 and 4,000 encoded words (12);
``Header.encode`` on 4,000 and 16,000 characters and ``as_bytes()`` on 1 MiB
and 4 MiB bodies, both near 4; ``get_payload()`` on 2 MiB and 16 MiB
(12.6, the surrogate scan); a 4,000- and 16,000-header lookup (near 4);
``walk()`` over a chain of 80 and 320 parts (11) against a flat multipart
of 80 and 320 parts (4.2); ``Message.as_string()`` on a 400- and 1,600-word
ASCII Subject, written unfolded (16), against ``as_bytes()``, folded (3.9);
under ``policy.HTTP`` a non-ASCII Subject stored parsed (18) against an
ASCII one read from source (3.5). ``Address(addr_spec=)`` shares the header parser's
slicing and is not timed on its own. None of them vary the token length, the
charset, the line length or the parameter length.

Address-list parsing is checked by counting characters in the suffix slices
between addresses. Fixed-width addresses make their total quadratic in the
address count; this observes one source of copying, not all parser work.
``TestUtils.test_getaddresses_is_linear`` separately times the utility parser.

Not settled by execution:

* the cost of the name-service lookup in ``make_msgid()``: the call is
  counted, its duration belongs to the resolver;
* the v·p of ``get_params()`` and the rows built on it: ``_parseparam``
  slices the rest of the value off once per parameter, but the copies are
  too cheap to see - 4,000 and 16,000 eight-character parameters cost 4.0x
  apart, and 6,400 ten-character parameters cost 19x what 64 of 1,000
  characters do at the same total length - so the term is read from the
  source and no test asserts it;
* that the non-ASCII refold of ``EmailPolicy.fold()`` arrived in 3.11.8 and
  3.12.2 rather than at either release boundary: the assertion is on the
  behaviour, which the pinned patch release of every version but 3.10 has;
* ``MIMEImage`` and ``MIMEAudio`` sniffing on Python 3.10 goes through
  ``imghdr`` and ``sndhdr``; the result is checked on every version, the
  module reached is not;
* that ``feed()`` costs the same however the input is chunked: the
  result is checked byte by byte against one call, the amortized cost is
  read from ``BufferedSubFile.push``, which scans each chunk once and reads
  the partial line back once when its line end arrives.

Intentionally undocumented: ``email.base64mime``, ``email.quoprimime``,
``email.feedparser`` (``BufferedSubFile``, ``NeedMoreData`` and its regular
expressions), ``email._header_value_parser``, the module-level regular
expressions the audit discovers, the ``raw_data_manager`` handler functions
(``get_text_content`` and the rest are the ``set_content()`` and
``get_content()`` rows), the per-class ``init``, ``parse`` and
``value_parser`` hooks of ``email.headerregistry``,
``email.policy.validate_header_name`` (the store row states its effect),
``email.message.decode_b`` and ``email.iterators._structure``.
"""

import io
import pathlib
import re
import socket
import subprocess
import sys
import textwrap
import timeit
import weakref
from collections.abc import Callable
from email import _header_value_parser as header_parser
from email import encoders, iterators, message_from_bytes, message_from_string, policy, utils
from email.charset import SHORTEST, Charset, add_alias, add_charset
from email.contentmanager import ContentManager
from email.errors import (
    CharsetError,
    HeaderParseError,
    HeaderWriteError,
    InvalidBase64PaddingDefect,
    MessageDefect,
    MultipartConversionError,
    MultipartInvariantViolationDefect,
    StartBoundaryNotFoundDefect,
)
from email.generator import DecodedGenerator, Generator
from email.header import Header, decode_header, make_header
from email.headerregistry import Address, Group, HeaderRegistry, UnstructuredHeader
from email.message import EmailMessage, Message, MIMEPart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.mime.text import MIMEText
from email.parser import BytesFeedParser, BytesHeaderParser, HeaderParser, Parser
from typing import Any, SupportsIndex

import pytest

PY = sys.executable
PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "email.md"
EXPECTED_BLOCKS = 3


def per_call(func: Callable[[], Any], number: int = 1, repeat: int = 5) -> float:
    """Seconds per call, best of several runs."""
    return min(timeit.repeat(func, number=number, repeat=repeat)) / number


class CountingFactory:
    """A header_factory that counts, and names, the parses EmailPolicy asks for."""

    def __init__(self) -> None:
        self.parses = 0
        self.names: list[str] = []
        self.registry = HeaderRegistry()

    def __call__(self, name: str, value: str) -> Any:
        self.parses += 1
        self.names.append(name.lower())
        return self.registry(name, value)

    def __getitem__(self, name: str) -> Any:
        return self.registry[name]


def parse_header(name: str, value: str) -> Any:
    """A header object of the registered class, typed loosely for its properties."""
    return HeaderRegistry()(name, value)


def counting_policy() -> tuple[CountingFactory, Any]:
    factory = CountingFactory()
    return factory, policy.default.clone(header_factory=factory)


def headers_source(count: int, last: str = "Last: z\n") -> str:
    return "".join(f"X-H{i}: v\n" for i in range(count)) + last + "\nbody\n"


def nested_source(depth: int, lines: int) -> bytes:
    """A text leaf of the given line count wrapped in `depth` multiparts."""
    part: EmailMessage = EmailMessage()
    part.set_content("line of text\n" * lines)
    for _ in range(depth):
        outer = EmailMessage()
        outer.make_mixed()
        outer.attach(part)
        part = outer
    return part.as_bytes()


class TestParsing:
    """Parsing stores header text and reads to the end; depth adds per-line work."""

    def test_headers_are_stored_unparsed_whatever_the_policy(self) -> None:
        factory, counting = counting_policy()

        message = message_from_string("Subject: a b\nTo: x@y.z\n\nbody\n", policy=counting)

        assert factory.parses == 0
        assert isinstance(message.raw_items().__next__()[1], str)
        legacy = message_from_string("Subject: a b\n\nbody\n")
        assert isinstance(legacy.raw_items().__next__()[1], str)

    def test_the_parser_reads_a_multipart_boundary_through_get_param(self) -> None:
        class Counting(Message):
            params: list[str] = []

            def get_param(self, param: str, *args: Any, **kwargs: Any) -> Any:
                Counting.params.append(param)
                return super().get_param(param, *args, **kwargs)

        source = "Content-Type: multipart/mixed; boundary=B\n\n--B\n\nx\n--B--\n"
        Parser(_class=Counting).parsestr(source)
        assert "boundary" in Counting.params

        Counting.params = []
        Parser(_class=Counting).parsestr("Subject: s\n\nx\n")
        assert Counting.params == []

    def test_the_parser_interprets_content_type_and_a_multipart_cte_only(self) -> None:
        factory, counting = counting_policy()
        source = (
            "Subject: a b\nTo: x@y.z\nContent-Transfer-Encoding: 8bit\n"
            "Content-Type: multipart/mixed; boundary=B\n\n"
            "--B\nSubject: inner\nContent-Transfer-Encoding: 7bit\n"
            "Content-Type: text/plain\n\nx\n--B--\n"
        )

        message = message_from_string(source, policy=counting)

        assert set(factory.names) == {"content-type", "content-transfer-encoding"}
        assert factory.names.count("content-transfer-encoding") == 1
        assert all(isinstance(value, str) for _, value in message.raw_items())
        during_parse = factory.parses
        message["Subject"]
        assert factory.parses == during_parse + 1

    def test_bytes_that_do_not_decode_survive_the_round_trip(self) -> None:
        message = message_from_bytes(b"Subject: s\n\n\xff\xfe raw\n")

        assert message.get_payload(decode=True) == b"\xff\xfe raw\n"
        assert message.get_payload() == "\ufffd\ufffd raw\n"
        latin = message_from_bytes(b"Content-Type: text/plain; x=1; charset=latin-1\n\n\xe9\n")
        assert latin.get_payload() == "\xe9\n"

    def test_a_file_is_read_to_its_end_in_8k_chunks(self) -> None:
        class Recording(io.StringIO):
            sizes: list[int] = []

            def read(self, size: int | None = -1) -> str:
                self.sizes.append(size if size is not None else -1)
                return super().read(size)

        source = "Subject: s\n\n" + "x" * 30_000
        fp = Recording(source)

        Parser().parse(fp)

        assert fp.sizes == [8192] * 5
        assert fp.tell() == len(source)

    def test_header_parser_reads_the_body_and_does_not_split_it(self) -> None:
        body = "--B\nContent-Type: text/plain\n\nfirst part\n--B--\n"
        source = "Content-Type: multipart/mixed; boundary=B\nSubject: s\n\n" + body

        message = HeaderParser().parsestr(source)

        assert message.is_multipart() is False
        assert message.get_payload() == body
        fp = io.BytesIO(source.encode())
        BytesHeaderParser().parse(fp)
        assert fp.tell() == len(source)

    def test_feed_parser_result_does_not_depend_on_chunking(self) -> None:
        source = nested_source(2, 5)
        whole = BytesFeedParser(policy=policy.default)
        whole.feed(source)
        by_byte = BytesFeedParser(policy=policy.default)
        for byte in source:
            by_byte.feed(bytes([byte]))

        first, second = whole.close(), by_byte.close()

        assert first.as_bytes() == second.as_bytes() == source
        assert [p.get_content_type() for p in second.walk()] == [
            "multipart/mixed",
            "multipart/mixed",
            "text/plain",
        ]

    def test_feeding_only_the_headers_leaves_no_body(self) -> None:
        parser = BytesFeedParser(policy=policy.default)
        for line in b"Subject: Hello\nTo: a@b.c\n\nbody\n".splitlines(keepends=True):
            parser.feed(line)
            if line == b"\n":
                break

        message = parser.close()

        assert message["Subject"] == "Hello"
        assert message.get_payload() == ""

    def test_close_records_a_multipart_root_with_no_parts(self) -> None:
        source = "Content-Type: multipart/mixed; boundary=B\n\nno boundary here\n"

        message = message_from_string(source)

        assert [type(d) for d in message.defects] == [
            StartBoundaryNotFoundDefect,
            MultipartInvariantViolationDefect,
        ]
        assert message.is_multipart() is False

    @pytest.mark.timing
    def test_parsing_is_linear_in_the_lines(self) -> None:
        small = ("Subject: s\n\n" + "line of text\n" * 50_000).encode()
        large = ("Subject: s\n\n" + "line of text\n" * 200_000).encode()

        small_time = per_call(lambda: message_from_bytes(small))
        large_time = per_call(lambda: message_from_bytes(large))

        ratio = large_time / small_time
        assert ratio < 7, f"4x the lines cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_nesting_depth_multiplies_the_per_line_cost(self) -> None:
        """The same 100k-line leaf, parsed at depth 0 and inside 16 multiparts.

        The sources differ by under 1% in length, so a bound in n alone
        predicts a ratio near 1; each enclosing multipart adds one boundary
        match per body line.
        """
        flat = nested_source(0, 100_000)
        deep = nested_source(16, 100_000)
        assert len(deep) < len(flat) * 1.01

        flat_time = per_call(lambda: message_from_bytes(flat))
        deep_time = per_call(lambda: message_from_bytes(deep))

        ratio = deep_time / flat_time
        assert ratio > 2.5, f"16 enclosing multiparts cost x{ratio:.1f}"


class TestHeaderAccess:
    """Fetches go through the policy; stores append; lookups scan."""

    def test_default_policy_parses_on_every_fetch(self) -> None:
        factory, counting = counting_policy()
        message = message_from_string("Subject: a b\nTo: x@y.z\n\nbody\n", policy=counting)

        first, second = message["Subject"], message["Subject"]

        assert factory.parses == 2
        assert first is not second
        message.items()
        assert factory.parses == 4
        message.get_all("To")
        assert factory.parses == 5
        message.get("Missing")
        assert factory.parses == 5

    def test_a_stored_header_object_is_returned_as_it_is(self) -> None:
        factory, counting = counting_policy()
        message = EmailMessage(policy=counting)

        message["Subject"] = "a b"

        assert factory.parses == 1
        assert message["Subject"] is message["Subject"]
        assert factory.parses == 1

    def test_compat32_returns_the_stored_string_itself(self) -> None:
        message = message_from_string("Subject: a b\n\nbody\n")

        assert type(message["Subject"]) is str
        assert message["Subject"] is message["Subject"]
        raw = message_from_bytes(b"Subject: \xff\n\nbody\n")
        assert isinstance(raw["Subject"], Header)
        assert str(raw["Subject"].encode()).startswith("=?unknown-8bit?")

    def test_lookup_is_the_first_case_insensitive_match(self) -> None:
        message = message_from_string("A: 1\na: 2\n\nb\n")

        assert message["a"] == "1"
        assert message.get_all("A") == ["1", "2"]
        assert message.get_all("Z") is None
        assert "A" in message and "z" not in message
        assert len(message) == 2
        assert message.keys() == ["A", "a"]

    def test_setitem_appends_and_never_replaces(self) -> None:
        legacy = Message()
        legacy["Subject"] = "1"
        legacy["Subject"] = "2"
        assert legacy.get_all("Subject") == ["1", "2"]

        modern = EmailMessage()
        modern["Subject"] = "1"
        with pytest.raises(ValueError, match="at most 1"):
            modern["Subject"] = "2"
        modern["X-Custom"] = "1"
        modern["X-Custom"] = "2"
        assert modern.get_all("X-Custom") == ["1", "2"]

    def test_header_names_are_validated_from_3_14(self) -> None:
        for message in (Message(), EmailMessage()):
            if sys.version_info >= (3, 14):
                with pytest.raises(ValueError, match="invalid characters"):
                    message["Bad Name"] = "x"
            else:
                message["Bad Name"] = "x"
                assert message["Bad Name"] == "x"

    def test_del_removes_every_match_and_tolerates_absence(self) -> None:
        message = message_from_string("A: 1\na: 2\nB: 3\n\nb\n")

        del message["A"]
        del message["A"]

        assert message.keys() == ["B"]

    def test_replace_header_keeps_the_position(self) -> None:
        message = message_from_string("A: 1\nB: 2\nA: 3\n\nb\n")

        message.replace_header("a", "9")

        assert message.items() == [("A", "9"), ("B", "2"), ("A", "3")]
        with pytest.raises(KeyError):
            message.replace_header("Q", "1")

    def test_add_header_formats_and_encodes_parameters(self) -> None:
        message = Message()

        message.add_header(
            "Content-Disposition", "attachment", filename=("utf-8", "", "é.txt"), size="3"
        )

        assert message["Content-Disposition"] == (
            "attachment; filename*=utf-8''%C3%A9.txt; size=\"3\""
        )
        assert message.get_filename() == "é.txt"

    def test_raw_items_and_set_raw_bypass_the_policy(self) -> None:
        factory, counting = counting_policy()
        message = EmailMessage(policy=counting)
        message["Subject"] = "x"

        message.set_raw("X-Raw", "left alone")

        assert factory.parses == 1
        assert [type(v) for _, v in message.raw_items()] == [
            type(message["Subject"]),
            str,
        ]

    @pytest.mark.timing
    def test_lookup_scans_the_header_list(self) -> None:
        small = message_from_string(headers_source(4_000))
        large = message_from_string(headers_source(16_000))

        small_time = per_call(lambda: small["Last"], number=50)
        large_time = per_call(lambda: large["Last"], number=50)

        ratio = large_time / small_time
        assert ratio > 2.5, f"4x the headers cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_parse_cost_grows_with_tokens_at_a_fixed_length(self) -> None:
        """Two 32,000-character Subjects: 100 words and 6,400 words.

        A bound in v alone predicts the same cost; the parser slices the
        remainder once per token.
        """

        def subject(words: int) -> Any:
            word = "x" * (32_000 // words - 1)
            value = " ".join([word] * words)
            return message_from_string(f"Subject: {value}\n\nb\n", policy=policy.default)

        few, many = subject(100), subject(6_400)
        assert abs(len(few.raw_items().__next__()[1]) - len(many.raw_items().__next__()[1])) < 100

        few_time = per_call(lambda: few["Subject"])
        many_time = per_call(lambda: many["Subject"])

        ratio = many_time / few_time
        assert ratio > 6, f"64x the words at one length cost x{ratio:.1f}"

    def test_address_header_copies_quadratic_suffix_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Count actual separator slices through the public header-fetch path.

        Only the remainder returned by get_address is instrumented. Slicing
        returns an ordinary str, so parsing inside each address is unchanged.
        Address width is fixed; display names, groups and defects are not varied.
        """
        copied: list[int] = []
        original = header_parser.get_address

        class Remainder(str):
            def __getitem__(self, key: SupportsIndex | slice) -> str:
                result = super().__getitem__(key)
                if isinstance(key, slice):
                    copied.append(len(result))
                return result

        def get_address(value: str) -> Any:
            address, remainder = original(value)
            return address, Remainder(remainder)

        monkeypatch.setattr(header_parser, "get_address", get_address)
        totals: list[int] = []
        width = len("user0000@example.com")
        for count in (100, 400):
            addresses = [f"user{i:04d}@example.com" for i in range(count)]
            message = message_from_string(
                f"To: {','.join(addresses)}\n\nb\n", policy=policy.default
            )
            copied.clear()

            header = message["To"]

            assert [address.addr_spec for address in header.addresses] == addresses
            assert not header.defects
            assert len(copied) == count - 1
            expected = (width + 1) * count * (count - 1) // 2 - (count - 1)
            assert sum(copied) == expected
            totals.append(sum(copied))

        assert 15 < totals[1] / totals[0] < 17, totals


class TestPayload:
    """Payload accessors return what is stored; decoding allocates."""

    def test_get_payload_returns_the_stored_string(self) -> None:
        message = Message()
        text = "hello"

        message.set_payload(text)

        assert message.get_payload() is text
        assert message.get_payload(decode=True) == b"hello"
        assert message.get_payload(decode=True) is not text

    def test_get_payload_fetches_the_transfer_encoding_but_not_for_a_subpart(self) -> None:
        factory, counting = counting_policy()
        single = message_from_string("Content-Transfer-Encoding: 7bit\n\nx\n", policy=counting)
        multi = message_from_string(
            "Content-Transfer-Encoding: 7bit\nContent-Type: multipart/mixed; boundary=B\n\n"
            "--B\n\nx\n--B--\n",
            policy=counting,
        )
        factory.parses = 0  # the multipart parse read its Content-Type

        single.get_payload()
        assert factory.parses == 1
        parts = multi.get_payload()
        assert multi.get_payload(0) is parts[0]
        assert factory.parses == 1

    def test_decode_handles_encodings_and_reports_bad_base64(self) -> None:
        message = message_from_string("Content-Transfer-Encoding: base64\n\nYWJj\n")
        assert message.get_payload(decode=True) == b"abc"

        broken = message_from_string("Content-Transfer-Encoding: base64\n\nYWJ\n")
        assert broken.get_payload(decode=True) == b"ab"
        assert [type(d) for d in broken.defects] == [InvalidBase64PaddingDefect]

        multipart = EmailMessage()
        multipart.make_mixed()
        assert multipart.get_payload(decode=True) is None

    def test_set_payload_bytes_become_a_surrogate_escaped_string(self) -> None:
        message = Message()

        message.set_payload(b"a\xffb")

        assert message.get_payload(decode=True) == b"a\xffb"
        assert message.get_payload() == "a\ufffdb"

    def test_set_charset_encodes_utf8_and_leaves_ascii(self) -> None:
        utf8 = Message()
        utf8.set_payload("hé", charset="utf-8")
        assert utf8["Content-Transfer-Encoding"] == "base64"
        assert utf8.get_payload() == "aMOp\n"
        assert utf8.get_charset() == Charset("utf-8")

        ascii_ = Message()
        ascii_.set_payload("hi", charset="us-ascii")
        assert ascii_["Content-Transfer-Encoding"] == "7bit"
        assert ascii_.get_payload() == "hi"
        assert ascii_["MIME-Version"] == "1.0"

        ascii_.set_charset(None)
        assert ascii_.get_param("charset") is None

    def test_attach_appends_by_reference_and_leaves_the_type_alone(self) -> None:
        message = Message()
        part = Message()

        message.attach(part)

        parts: Any = message.get_payload()
        assert parts[0] is part
        assert message.get_content_type() == "text/plain"
        assert message.is_multipart() is True
        text = Message()
        text.set_payload("body")
        with pytest.raises(TypeError):
            text.attach(part)

    def test_is_multipart_follows_the_payload_not_the_header(self) -> None:
        message = Message()
        message.set_payload([])
        assert message.is_multipart() is True

        typed = message_from_string("Content-Type: multipart/mixed; boundary=B\n\nno parts\n")
        assert typed.is_multipart() is False

    def test_walk_is_lazy_and_depth_first(self) -> None:
        message = message_from_bytes(nested_source(2, 1))

        walker = message.walk()

        assert next(walker) is message
        assert [p.get_content_type() for p in walker] == ["multipart/mixed", "text/plain"]

    def test_set_type_rebuilds_the_header_once_per_parameter(self) -> None:
        class Counting(Message):
            calls = 0

            def set_param(self, *args: Any, **kwargs: Any) -> None:
                Counting.calls += 1
                super().set_param(*args, **kwargs)

        message = Counting()
        message["Content-Type"] = "text/plain; a=1; b=2; c=3"

        message.set_type("text/html")

        assert Counting.calls == 3
        assert message["Content-Type"] == 'text/html; a="1"; b="2"; c="3"'

    @pytest.mark.timing
    def test_walk_passes_each_part_through_one_generator_per_level(self) -> None:
        """A chain of k parts against a flat multipart of k parts."""

        def chain(count: int) -> EmailMessage:
            part = EmailMessage()
            part.set_content("x")
            for _ in range(count):
                outer = EmailMessage()
                outer.make_mixed()
                outer.attach(part)
                part = outer
            return part

        def flat(count: int) -> EmailMessage:
            message = EmailMessage()
            message.make_mixed()
            for _ in range(count):
                part = EmailMessage()
                part.set_content("x")
                message.attach(part)
            return message

        chain_small, chain_large = chain(80), chain(320)
        flat_small, flat_large = flat(80), flat(320)

        chain_ratio = per_call(lambda: list(chain_large.walk())) / per_call(
            lambda: list(chain_small.walk())
        )
        flat_ratio = per_call(lambda: list(flat_large.walk())) / per_call(
            lambda: list(flat_small.walk())
        )

        assert chain_ratio > 7, f"chain: 4x the parts cost x{chain_ratio:.1f}"
        assert flat_ratio < 6, f"flat: 4x the parts cost x{flat_ratio:.1f}"

    def test_content_type_fallbacks(self) -> None:
        message = Message()
        assert message.get_content_type() == "text/plain"
        message.set_default_type("message/rfc822")
        assert message.get_content_type() == "message/rfc822"
        message["Content-Type"] = "noslash"
        assert message.get_content_type() == "text/plain"

        named = message_from_string('Content-Type: text/plain; name="n.txt"\n\nb\n')
        assert named.get_filename() == "n.txt"
        assert named.get_params() == [("text/plain", ""), ("name", "n.txt")]
        assert Message().get_charsets("none") == ["none"]

    def test_set_boundary_needs_a_content_type(self) -> None:
        with pytest.raises(HeaderParseError):
            Message().set_boundary("x")
        message = message_from_string("Content-Type: multipart/mixed; boundary=B\n\nb\n")
        message.set_boundary("C")
        assert message.get_boundary() == "C"
        assert message["Content-Type"] == 'multipart/mixed; boundary="C"'

    @pytest.mark.timing
    def test_get_payload_scans_the_text(self) -> None:
        small, large = Message(), Message()
        small.set_payload("y" * (2 << 20))
        large.set_payload("y" * (16 << 20))

        small_time = per_call(lambda: small.get_payload(), number=20)
        large_time = per_call(lambda: large.get_payload(), number=20)

        ratio = large_time / small_time
        assert ratio > 3, f"8x the text cost x{ratio:.1f}"


class TestEmailMessage:
    """Content helpers move parts by reference and pick encodings."""

    def test_set_content_picks_the_transfer_encoding(self) -> None:
        cases = {
            "hi\n": "7bit",
            "héllo\n": "8bit",
            "x" * 200: "quoted-printable",
            "é" * 200: "base64",
        }
        for text, expected in cases.items():
            message = EmailMessage()
            message.set_content(text)
            assert message["Content-Transfer-Encoding"] == expected, text[:5]
            assert message.get_content() == text.rstrip("\n") + "\n"

        class Counting(EmailMessage):
            calls = 0

            def set_param(self, *args: Any, **kwargs: Any) -> None:
                Counting.calls += 1
                super().set_param(*args, **kwargs)

        with_params = Counting()
        with_params.set_content("x", params={"a": "1", "b": "2"}, headers=["X-One: 1", "X-Two: 2"])
        assert Counting.calls == 3
        assert with_params["Content-Type"] == 'text/plain; charset="utf-8"; a="1"; b="2"'
        assert with_params["X-One"] == "1" and with_params["X-Two"] == "2"

        Counting.calls = 0
        wrapping = Counting()
        wrapping.set_content(EmailMessage(), params={"a": "1"}, headers=["X-One: 1"])
        assert Counting.calls == 1
        assert wrapping["Content-Type"] == 'message/rfc822; a="1"'
        assert wrapping["X-One"] == "1"

        seven_bit = EmailMessage(policy=policy.default.clone(cte_type="7bit"))
        seven_bit.set_content("héllo\n")
        assert seven_bit["Content-Transfer-Encoding"] == "quoted-printable"

        binary = EmailMessage()
        binary.set_content(b"\x00" * 200, maintype="application", subtype="octet-stream")
        assert binary["Content-Transfer-Encoding"] == "base64"
        encoded: Any = binary.get_payload()
        assert max(len(line) for line in encoded.splitlines()) <= 78
        assert binary.get_content() == b"\x00" * 200

    def test_set_content_replaces_content_headers_and_keeps_the_rest(self) -> None:
        message = EmailMessage()
        message["Subject"] = "kept"
        message.set_content("one", disposition="attachment", filename="a.txt")

        message.set_content("two")

        assert message["Subject"] == "kept"
        assert message["Content-Disposition"] is None
        assert message["MIME-Version"] == "1.0"
        assert message.get_content_type() == "text/plain"
        part = MIMEPart()
        part.set_content("x")
        assert part["MIME-Version"] is None

    def test_a_message_payload_is_stored_by_reference(self) -> None:
        outer, inner = EmailMessage(), EmailMessage()
        inner.set_content("inner")

        outer.set_content(inner)

        assert outer.get_payload(0) is inner
        assert outer.get_content() is inner
        assert outer.get_content_type() == "message/rfc822"
        other = message_from_string(
            "Content-Type: message/partial\n\nSubject: inner\n\nbody\n", policy=policy.default
        )
        assert other.get_content() == b"Subject: inner\n\nbody\n"

    def test_get_content_needs_a_handler(self) -> None:
        with pytest.raises(KeyError):
            ContentManager().get_content(EmailMessage())
        multipart = EmailMessage()
        multipart.make_mixed()
        with pytest.raises(TypeError):
            multipart.set_content("x")

    def test_make_mixed_moves_content_by_reference(self) -> None:
        message = EmailMessage()
        message["Subject"] = "s"
        message.set_content("text")
        payload = message.get_payload()

        message.make_mixed()

        assert message.get_content_type() == "multipart/mixed"
        assert message["Subject"] == "s"
        first: Any = message.get_payload(0)
        assert first.get_payload() is payload
        assert first["Subject"] is None
        with pytest.raises(ValueError):
            message.make_mixed()
        with pytest.raises(ValueError):
            message.make_alternative()
        nested = EmailMessage()
        nested.make_alternative()
        nested.make_mixed()
        assert [p.get_content_type() for p in nested.walk()] == [
            "multipart/mixed",
            "multipart/alternative",
        ]

    def test_add_attachment_converts_once_and_attaches_by_reference(self) -> None:
        message = EmailMessage()
        message.set_content("body")
        text = message.get_payload()

        message.add_attachment(b"z", maintype="application", subtype="pdf", filename="f.pdf")
        message.add_attachment(b"y", maintype="application", subtype="pdf", filename="g.pdf")

        body: Any = message.get_body()
        assert body.get_payload() is text
        parts: Any = message.get_payload()
        assert body is parts[0]
        assert len(parts) == 3
        assert list(message.iter_attachments()) == parts[1:]
        assert parts[1]["Content-Disposition"] == 'attachment; filename="f.pdf"'
        assert list(message.iter_parts()) == parts
        assert list(EmailMessage().iter_parts()) == []
        assert parts[1].is_attachment() and not parts[0].is_attachment()

    def test_clear_and_clear_content(self) -> None:
        message = EmailMessage()
        message["Subject"] = "s"
        message.set_content("x")

        message.clear_content()
        assert message.keys() == ["Subject", "MIME-Version"]
        assert message.get_payload() is None

        message.set_content("body")
        message.add_attachment(b"z", maintype="application", subtype="pdf", filename="f")
        attachment = weakref.ref(message.get_payload(1))
        message.clear_content()
        assert attachment() is None

        message.add_attachment(b"z", maintype="application", subtype="pdf", filename="f")
        part = weakref.ref(message.get_payload(0))
        subject = weakref.ref(message["Subject"])
        message.clear()
        assert message.keys() == []
        assert part() is None and subject() is None

    def test_str_writes_utf8_headers_as_they_are(self) -> None:
        message = EmailMessage()
        message["Subject"] = "héllo"

        assert "Subject: héllo" in str(message)
        assert "=?utf-8?" in message.as_string()


class TestGenerator:
    """Flattening folds headers, verifies them and stores a boundary."""

    def test_flatten_generates_and_stores_a_boundary(self) -> None:
        message = EmailMessage()
        message.make_mixed()
        part = EmailMessage()
        part.set_content("x")
        message.attach(part)
        assert message.get_boundary() is None

        output = message.as_bytes()

        boundary = message.get_boundary()
        assert boundary is not None
        assert output.count(b"--" + boundary.encode()) == 2

    def test_flatten_reads_each_multipart_boundary_through_get_param(self) -> None:
        class Counting(Message):
            params: list[str] = []

            def get_param(self, param: str, *args: Any, **kwargs: Any) -> Any:
                Counting.params.append(param)
                return super().get_param(param, *args, **kwargs)

        source = "Content-Type: multipart/mixed; boundary=B\n\n--B\n\nx\n--B--\n"
        message = Parser(_class=Counting).parsestr(source)
        Counting.params = []

        message.as_string()

        assert Counting.params.count("boundary") == 1
        Counting.params = []
        Parser(_class=Counting).parsestr("Subject: s\n\nx\n").as_string()
        assert Counting.params == []

    def test_a_line_break_in_a_header_raises_on_output(self) -> None:
        message = Message()
        message["X"] = "a\nb"

        with pytest.raises(HeaderWriteError):
            message.as_string()

    def test_mangle_from_follows_the_policy_but_as_string_turns_it_off(self) -> None:
        message = Message()
        message.set_payload("From here\n")

        output = io.StringIO()
        Generator(output).flatten(message)

        assert output.getvalue() == "\n>From here\n"
        assert message.as_string() == "\nFrom here\n"

    def test_as_string_leaves_headers_unfolded_and_as_bytes_folds(self) -> None:
        message = Message()
        message["Subject"] = " ".join(["word"] * 40)

        assert len(message.as_string().splitlines()) == 2
        assert len(message.as_bytes().splitlines()) == 4
        modern = EmailMessage()
        modern["Subject"] = " ".join(["word"] * 40)
        assert len(modern.as_string().splitlines()) == 4

    def test_a_source_header_that_fits_is_written_verbatim(self) -> None:
        source = "Subject: two  spaces   kept\nX-Long: " + " ".join(["word"] * 40) + "\n\nb\n"
        message = message_from_string(source, policy=policy.default)

        lines = message.as_string().splitlines()

        assert lines[0] == "Subject: two  spaces   kept"
        assert lines[1].startswith("X-Long:") and len(lines[1]) <= 78
        assert lines[2].startswith(" ")

    def test_each_enclosing_multipart_copies_the_text_again(self) -> None:
        """Characters written through the generator's buffers, per depth.

        The output barely changes with depth; the buffered characters grow
        with it because every level renders its subtree into a buffer and
        copies that into the level above.
        """

        class Counting(io.StringIO):
            total = 0

            def write(self, s: str) -> int:
                Counting.total += len(s)
                return super().write(s)

        class CountingGenerator(Generator):
            def _new_buffer(self) -> io.StringIO:  # type: ignore[override]
                return Counting()

        def buffered(depth: int) -> tuple[int, int]:
            message = message_from_bytes(nested_source(depth, 1))
            leaf: Any = message
            while leaf.is_multipart():
                leaf = leaf.get_payload(0)
            leaf.set_payload("x" * 100_000)
            Counting.total = 0
            output = io.StringIO()
            CountingGenerator(output).flatten(message)
            return Counting.total, len(output.getvalue())

        flat_total, flat_output = buffered(0)
        deep_total, deep_output = buffered(4)

        assert flat_total < flat_output * 1.1
        assert deep_output < flat_output * 1.1
        assert deep_total > flat_total * 5, f"{deep_total} vs {flat_total} at depth 4"

    def test_a_folded_header_passes_verification_and_as_bytes_checks_too(self) -> None:
        message = Message()
        message["Subject"] = " ".join(["word"] * 40)
        assert len(message.as_bytes().splitlines()) == 4

        message["X"] = "a\nb"
        with pytest.raises(HeaderWriteError):
            message.as_bytes()

    def test_decoded_generator_writes_text_and_fmt_lines(self) -> None:
        message = EmailMessage()
        message.set_content("text body")
        message.add_attachment(b"z", maintype="application", subtype="pdf", filename="f.pdf")
        message.add_attachment(
            b"y", maintype="application", subtype="pdf", params={"name": "n.pdf"}
        )
        unnamed: Any = message.get_payload(2)
        del unnamed["Content-Disposition"]
        output = io.StringIO()

        DecodedGenerator(output).flatten(message)

        text = output.getvalue()
        assert "text body\n" in text
        assert "[Non-text (application/pdf) part of message omitted, filename f.pdf]\n" in text
        assert text.endswith(
            "[Non-text (application/pdf) part of message omitted, filename n.pdf]\n"
        )
        assert "--" not in text.split("\n\n", 1)[1]

    @pytest.mark.timing
    def test_flatten_is_linear_in_the_body(self) -> None:
        small, large = EmailMessage(), EmailMessage()
        small.set_content("y" * (1 << 20))
        large.set_content("y" * (4 << 20))

        small_time = per_call(lambda: small.as_bytes())
        large_time = per_call(lambda: large.as_bytes())

        ratio = large_time / small_time
        assert ratio < 7, f"4x the body cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_an_unfolded_header_costs_quadratic_and_a_folded_one_linear(self) -> None:
        """Message.as_string() writes headers unfolded; as_bytes() folds them."""
        small, large = Message(), Message()
        small["Subject"] = " ".join(["word"] * 400)
        large["Subject"] = " ".join(["word"] * 1_600)

        unfolded = per_call(lambda: large.as_string()) / per_call(lambda: small.as_string())
        folded = per_call(lambda: large.as_bytes()) / per_call(lambda: small.as_bytes())

        assert unfolded > 8, f"unfolded: 4x the words cost x{unfolded:.1f}"
        assert folded < 6, f"folded: 4x the words cost x{folded:.1f}"

    @pytest.mark.timing
    def test_without_a_line_limit_a_source_header_is_linear(self) -> None:
        """policy.HTTP: a non-ASCII header stored parsed against an ASCII one from source.

        The ASCII value stored parsed is not the contrast: with no line limit
        it folds in one piece, near 3.5x for 4x the words.
        """

        def stored(words: int) -> EmailMessage:
            message = EmailMessage(policy=policy.HTTP)
            message["Subject"] = " ".join(["wörd"] * words)
            return message

        def parsed(words: int) -> Any:
            source = "Subject: " + " ".join(["word"] * words) + "\n\nb\n"
            return message_from_string(source, policy=policy.HTTP)

        stored_small, stored_large = stored(400), stored(1_600)
        source_small, source_large = parsed(400), parsed(1_600)

        stored_ratio = per_call(lambda: stored_large.as_string()) / per_call(
            lambda: stored_small.as_string()
        )
        source_ratio = per_call(lambda: source_large.as_string()) / per_call(
            lambda: source_small.as_string()
        )

        assert stored_ratio > 8, f"stored parsed: 4x the words cost x{stored_ratio:.1f}"
        assert source_ratio < 6, f"from source: 4x the words cost x{source_ratio:.1f}"

    @pytest.mark.timing
    def test_folding_a_parsed_header_grows_faster_than_its_tokens(self) -> None:
        small = policy.default.header_factory("Subject", " ".join(["word"] * 2_000))
        large = policy.default.header_factory("Subject", " ".join(["word"] * 8_000))

        small_time = per_call(lambda: small.fold(policy=policy.default))
        large_time = per_call(lambda: large.fold(policy=policy.default))

        ratio = large_time / small_time
        assert ratio > 6, f"4x the words cost x{ratio:.1f} to fold"


class TestPolicy:
    """Policies are immutable values that decide parsing and defects."""

    def test_policies_are_immutable_and_cloned(self) -> None:
        abstract: Any = policy.Policy
        with pytest.raises(TypeError):
            abstract()
        assert policy.Compat32().linesep == policy.EmailPolicy().linesep == "\n"
        with pytest.raises(AttributeError):
            policy.default.linesep = "x"  # type: ignore[misc]
        unknown: dict[str, Any] = {"nope": 1}
        with pytest.raises(TypeError):
            policy.default.clone(**unknown)

        clone = policy.default.clone(linesep="\r\n")

        assert clone is not policy.default
        assert clone.header_factory is policy.default.header_factory
        assert (policy.compat32 + policy.SMTP).linesep == "\r\n"

    def test_module_policies(self) -> None:
        assert policy.strict.raise_on_defect and not policy.default.raise_on_defect
        assert policy.SMTP.linesep == policy.HTTP.linesep == policy.SMTPUTF8.linesep == "\r\n"
        assert policy.HTTP.max_line_length is None
        assert policy.SMTPUTF8.utf8 and not policy.SMTP.utf8
        assert policy.compat32.mangle_from_ and not policy.default.mangle_from_
        assert policy.compat32.verify_generated_headers and policy.default.verify_generated_headers
        assert EmailMessage().policy is policy.default
        assert Message().policy is policy.compat32
        assert policy.default.content_manager is policy.default.content_manager

    def test_strict_raises_the_defect_default_records_it(self) -> None:
        source = "Content-Type: multipart/mixed; boundary=B\n\nno boundary here\n"

        with pytest.raises(StartBoundaryNotFoundDefect) as info:
            message_from_string(source, policy=policy.strict)

        assert isinstance(info.value, ValueError)
        recorded = message_from_string(source, policy=policy.default)
        assert type(recorded.defects[0]) is StartBoundaryNotFoundDefect
        header = message_from_string("To: bad@@x\n\nb\n", policy=policy.strict)["To"]
        assert header.defects and header.addresses[0].domain == ""
        target = Message()
        policy.strict.register_defect(target, StartBoundaryNotFoundDefect())
        assert len(target.defects) == 1
        with pytest.raises(StartBoundaryNotFoundDefect):
            policy.strict.handle_defect(target, StartBoundaryNotFoundDefect())

    def test_header_source_parse_joins_without_parsing(self) -> None:
        lines = ["Subject: a\n", " b\n"]

        assert policy.compat32.header_source_parse(lines) == ("Subject", "a\n b")
        assert policy.default.header_source_parse(lines) == ("Subject", "a\n b")

    def test_header_store_parse(self) -> None:
        assert policy.compat32.header_store_parse("X", "a b") == ("X", "a b")
        with pytest.raises(ValueError):
            policy.default.header_store_parse("X", "a\nb")

        stored = policy.default.header_factory("X", "a b")
        assert policy.default.header_store_parse("x", stored)[1] is stored
        assert policy.default.header_max_count("Subject") == 1
        assert policy.default.header_max_count("X-Custom") is None
        assert policy.compat32.header_max_count("Subject") is None

    def test_header_fetch_parse(self) -> None:
        value = "a b"
        assert policy.compat32.header_fetch_parse("X", value) is value
        raw = b"a \xff".decode("ascii", "surrogateescape")
        assert isinstance(policy.compat32.header_fetch_parse("X", raw), Header)

        parsed = policy.default.header_fetch_parse("Subject", "a\n b")
        assert parsed == "a b"
        assert policy.default.header_fetch_parse("Subject", parsed) is parsed

    def test_fold_binary_encodes_the_folded_text(self) -> None:
        assert policy.SMTPUTF8.fold_binary("Subject", "hé") == "Subject: hé\r\n".encode()
        assert policy.compat32.fold("Subject", "plain") == "Subject: plain\n"
        assert policy.default.fold("Subject", "plain") == "Subject: plain\n"

    def test_a_short_non_ascii_source_value_is_refolded_except_on_3_10(self) -> None:
        """Python 3.10 writes it out as it is, which is O(v) rather than O(v·t)."""
        folded = policy.default.fold("Subject", "hé")

        if sys.version_info >= (3, 11):
            assert folded == "Subject: =?utf-8?q?h=C3=A9?=\n"
        else:
            assert folded == "Subject: hé\n"
        assert policy.SMTPUTF8.fold("Subject", "hé") == "Subject: hé\r\n"


class TestHeaderRegistry:
    """Header objects parse once and precompute their properties."""

    def test_lookup_builds_a_new_class_each_time(self) -> None:
        registry = HeaderRegistry()

        first, second = registry["subject"], registry["subject"]

        assert first is not second
        assert first.__name__ == second.__name__ == "_UniqueUnstructuredHeader"
        plain: Any = UnstructuredHeader
        registry.map_to_type("x-mine", plain)
        assert registry["x-mine"].__name__ == "_UnstructuredHeader"

    def test_call_parses_and_records_defects(self) -> None:
        header = parse_header("To", "A <a@b.c>, bad@@x")

        assert str in type(header).__mro__
        assert vars(header)["_addresses"] is None
        assert header.addresses[0].addr_spec == "a@b.c"
        assert header.addresses is header.addresses
        assert header.defects
        assert header.defects is not header.defects
        assert header.defects[0] is header.defects[0]
        assert header.max_count == 1
        assert parse_header("X-Custom", "x").max_count is None
        assert parse_header("Date", "garbage").datetime is None

    def test_single_and_unique_headers(self) -> None:
        assert parse_header("Subject", "s").max_count == 1
        sender = parse_header("Sender", "a@b.c, d@e.f")
        with pytest.raises(ValueError):
            sender.address  # noqa: B018

        content = parse_header("Content-Type", 'text/plain; charset="utf-8"')
        assert (content.maintype, content.subtype, content.params["charset"]) == (
            "text",
            "plain",
            "utf-8",
        )

    def test_address_validation(self) -> None:
        with pytest.raises(ValueError):
            Address(display_name="x\n")
        with pytest.raises(TypeError):
            Address(username="a", addr_spec="a@b.c")
        with pytest.raises(ValueError):
            Address(addr_spec="a@b.c extra")

        address = Address("A B", addr_spec='"a b"@c.d')
        assert address.username == "a b"
        assert address.addr_spec == '"a b"@c.d'
        assert str(address) == 'A B <"a b"@c.d>'
        assert Address(username="a b", domain="c.d").addr_spec == '"a b"@c.d'

    def test_group_copies_its_addresses(self) -> None:
        addresses = [Address(addr_spec="a@b.c")]
        group = Group("g", addresses)

        addresses.append(Address(addr_spec="z@z.z"))

        assert len(group.addresses) == 1
        assert str(group) == "g: a@b.c;"


class TestHeaderModule:
    """email.header: chunks, folding and decoding."""

    def test_append_falls_back_to_utf8_only_from_ascii(self) -> None:
        assert Header("hé", "us-ascii").encode() == "=?utf-8?b?aMOp?="
        with pytest.raises(UnicodeEncodeError):
            Header("ж", "iso-8859-1")
        header = Header("a")
        header.append("b")
        assert str(header) == "a b"
        assert header.encode() == "a b"

    def test_encode_rejects_an_embedded_header(self) -> None:
        with pytest.raises(HeaderParseError):
            Header("a\nb: c").encode()

    def test_decode_header_and_make_header(self) -> None:
        assert decode_header("plain") == [("plain", None)]
        decoded = decode_header("=?utf-8?b?aMOp?= =?utf-8?b?aMOp?= plain")
        assert decoded == [(b"h\xc3\xa9h\xc3\xa9", "utf-8"), (b" plain", None)]
        assert str(make_header(decoded)) == "héhé plain"

    @pytest.mark.timing
    def test_decode_header_grows_faster_than_its_encoded_words(self) -> None:
        def words(count: int) -> str:
            return " ".join(["=?utf-8?b?aMOpbGxv?="] * count)

        small, large = words(1_000), words(4_000)

        small_time = per_call(lambda: decode_header(small))
        large_time = per_call(lambda: decode_header(large))

        ratio = large_time / small_time
        assert ratio > 6, f"4x the encoded words cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_header_encode_is_linear(self) -> None:
        small = Header(" ".join(["wörd"] * 800), header_name="Subject")
        large = Header(" ".join(["wörd"] * 3_200), header_name="Subject")

        small_time = per_call(lambda: small.encode())
        large_time = per_call(lambda: large.encode())

        ratio = large_time / small_time
        assert ratio < 7, f"4x the text cost x{ratio:.1f}"


class TestCharset:
    """Charset resolves names once and encodes on request."""

    def test_constructor(self) -> None:
        assert Charset("latin-1").input_charset == "iso-8859-1"
        assert Charset("utf-8") == Charset("UTF-8")
        with pytest.raises(CharsetError):
            Charset("é")
        unknown = Charset("no-such-codec")
        assert unknown.body_encoding == Charset("utf-8").body_encoding
        with pytest.raises(LookupError):
            unknown.body_encode("x")

    def test_body_and_header_encoding(self) -> None:
        assert Charset("utf-8").body_encode("hé") == "aMOp\n"
        text = "plain"
        result = Charset("us-ascii").body_encode(text)
        assert result == text and result is not text
        assert Charset("utf-8").header_encode("hé") == "=?utf-8?b?aMOp?="
        assert Charset("iso-8859-1").header_encode("hé") == "=?iso-8859-1?q?h=E9?="
        assert Charset("utf-8").header_encode_lines("hé hé", iter([20, 20])) == [
            "=?utf-8?b?aMOpIGg=?=",
            "=?utf-8?b?w6k=?=",
        ]
        assert Charset("us-ascii").get_body_encoding() is encoders.encode_7or8bit
        assert Charset("utf-8").get_body_encoding() == "base64"

    def test_module_tables(self) -> None:
        add_alias("x-test-alias", "utf-8")
        assert Charset("x-test-alias").output_charset == "utf-8"
        with pytest.raises(ValueError):
            add_charset("x-test-charset", body_enc=SHORTEST)


class TestEncoders:
    """Encoders rewrite the payload and its transfer-encoding header."""

    def test_encode_base64_rewrites_and_stacks(self) -> None:
        message = Message()
        message.set_payload("abc")

        encoders.encode_base64(message)
        assert message.get_payload() == "YWJj\n"
        assert message["Content-Transfer-Encoding"] == "base64"

        encoders.encode_base64(message)
        assert message.get_payload() == "YWJj\n"

    def test_encode_7or8bit_sets_the_header_only(self) -> None:
        message = Message()
        message.set_payload("abc")
        encoders.encode_7or8bit(message)
        assert message.get_payload() == "abc"
        assert message["Content-Transfer-Encoding"] == "7bit"

        raw = Message()
        raw.set_payload(b"\xff")
        encoders.encode_7or8bit(raw)
        assert raw["Content-Transfer-Encoding"] == "8bit"

        untouched = Message()
        untouched.set_payload("abc")
        encoders.encode_noop(untouched)
        assert untouched.items() == []


class TestIterators:
    """Both iterators are generators over walk()."""

    def test_body_line_iterator(self) -> None:
        message = EmailMessage()
        message.set_content("one\ntwo")
        message.add_attachment(b"z", maintype="application", subtype="pdf", filename="f")

        lines = iterators.body_line_iterator(message)

        assert next(lines) == "one\n"
        assert list(lines) == ["two\n", "eg==\n"]
        assert list(iterators.body_line_iterator(message, decode=True)) == []

    def test_typed_subpart_iterator(self) -> None:
        message = EmailMessage()
        message.set_content("t")
        message.add_alternative("<p>h</p>", subtype="html")
        message.add_attachment(b"z", maintype="application", subtype="pdf", filename="f")

        parts = iterators.typed_subpart_iterator(message, "text")

        assert next(parts).get_content_type() == "text/plain"
        assert [p.get_content_type() for p in parts] == ["text/html"]
        assert [
            p.get_content_type() for p in iterators.typed_subpart_iterator(message, "text", "html")
        ] == ["text/html"]


class TestMime:
    """The MIME constructors set headers and attach by reference."""

    def test_mime_text_charset_choice(self) -> None:
        ascii_ = MIMEText("hi")
        assert (ascii_["Content-Transfer-Encoding"], ascii_.get_payload()) == ("7bit", "hi")
        assert ascii_.get_param("charset") == "us-ascii"
        assert ascii_.policy is policy.compat32

        utf8 = MIMEText("hé")
        assert (utf8["Content-Transfer-Encoding"], utf8.get_payload()) == ("base64", "aMOp\n")
        assert utf8.get_param("charset") == "utf-8"

    def test_mime_multipart_and_message_attach_by_reference(self) -> None:
        part = MIMEText("x")
        multipart = MIMEMultipart(_subparts=[part], boundary="BB")
        assert multipart.get_payload(0) is part
        assert multipart.get_boundary() == "BB"
        assert multipart["MIME-Version"] == "1.0"

        inner = Message()
        wrapped = MIMEMessage(inner)
        assert wrapped.get_payload(0) is inner
        assert wrapped.get_content_type() == "message/rfc822"
        with pytest.raises(TypeError):
            MIMEMessage("not a message")  # type: ignore[arg-type]
        with pytest.raises(MultipartConversionError):
            MIMENonMultipart("text", "plain").attach(part)

    def test_binary_types_run_the_encoder_once_and_sniff(self) -> None:
        calls: list[Message] = []

        def encoder(message: Message) -> None:
            calls.append(message)

        application = MIMEApplication(b"data", _encoder=encoder, name="d.bin")
        assert calls == [application]
        assert application.get_payload() == "data"
        assert application.get_param("name") == "d.bin"

        assert MIMEApplication(b"data").get_content_type() == "application/octet-stream"
        with pytest.raises(TypeError):
            MIMEApplication(b"data", None)  # type: ignore[arg-type]
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
        assert MIMEImage(png).get_content_type() == "image/png"
        assert MIMEImage(png)["Content-Transfer-Encoding"] == "base64"
        with pytest.raises(TypeError):
            MIMEImage(b"nope")


class TestUtils:
    """Address, date and parameter helpers."""

    def test_make_msgid_looks_the_host_up_only_without_a_domain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        monkeypatch.setattr(socket, "getfqdn", lambda *args: calls.append("x") or "host.example")

        with_lookup = utils.make_msgid()
        without = utils.make_msgid(domain="given.example")

        assert calls == ["x"]
        assert with_lookup.endswith("@host.example>")
        assert without.endswith("@given.example>")

    def test_dates(self) -> None:
        assert utils.parsedate("bad") is None
        assert utils.parsedate_tz("bad") is None
        with pytest.raises(ValueError):
            utils.parsedate_to_datetime("bad")
        stamp = utils.parsedate_to_datetime("Mon, 1 Jan 2024 10:00:00 +0100")
        assert utils.format_datetime(stamp) == "Mon, 01 Jan 2024 10:00:00 +0100"
        with_zone = utils.parsedate_tz("Mon, 1 Jan 2024 10:00:00 +0100")
        assert with_zone is not None
        assert utils.mktime_tz(with_zone) == int(stamp.timestamp())
        params = list(__import__("inspect").signature(utils.localtime).parameters)
        assert params == (["dt"] if sys.version_info >= (3, 14) else ["dt", "isdst"])

    def test_addresses(self) -> None:
        assert utils.parseaddr("Ann <ann@example.com>") == ("Ann", "ann@example.com")
        assert utils.parseaddr("garbage <<") == ("garbage", "")
        assert utils.getaddresses(["a@b.c, D <d@e.f>"]) == [("", "a@b.c"), ("D", "d@e.f")]
        assert utils.formataddr(("Hé", "a@b.c")) == "=?utf-8?b?SMOp?= <a@b.c>"
        assert utils.formataddr(("A, B", "a@b.c")) == '"A, B" <a@b.c>'

    def test_rfc2231_helpers(self) -> None:
        assert utils.decode_params([("", ""), ("t*1*", "b"), ("t*0*", "a"), ("x", "y")]) == [
            ("", ""),
            ("x", '"y"'),
            ("t", (None, None, '"ab"')),
        ]
        assert utils.encode_rfc2231("é.txt", "utf-8") == "utf-8''%C3%A9.txt"
        assert utils.decode_rfc2231("utf-8''%C3%A9.txt") == ["utf-8", "", "%C3%A9.txt"]
        assert utils.collapse_rfc2231_value(("utf-8", "", "\xc3\xa9.txt")) == "é.txt"
        assert utils.quote('a"b') == 'a\\"b' and utils.unquote('"a"') == "a"

    @pytest.mark.timing
    def test_getaddresses_is_linear(self) -> None:
        small = ", ".join(f"user{i}@example.com" for i in range(1_000))
        large = ", ".join(f"user{i}@example.com" for i in range(4_000))

        small_time = per_call(lambda: utils.getaddresses([small]))
        large_time = per_call(lambda: utils.getaddresses([large]))

        ratio = large_time / small_time
        assert ratio < 7, f"4x the addresses cost x{ratio:.1f}"


class TestErrors:
    """Defects are ValueErrors; the exceptions form one tree."""

    def test_hierarchy(self) -> None:
        assert issubclass(MessageDefect, ValueError)
        assert issubclass(StartBoundaryNotFoundDefect, MessageDefect)
        assert issubclass(HeaderParseError, MessageDefect.__mro__[0]) is False
        from email.errors import BoundaryError, MessageError, MessageParseError

        assert issubclass(HeaderParseError, MessageParseError)
        assert issubclass(BoundaryError, MessageParseError)
        assert issubclass(MessageParseError, MessageError)
        assert issubclass(MultipartConversionError, MessageError)


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


def _outputs() -> list[str]:
    """The plain fenced blocks that follow each python block."""
    text = PAGE.read_text(encoding="utf-8")
    return [match.strip() for match in re.findall(r"Output:\n\n```\n(.*?)```", text, re.S)]


def _block_containing(marker: str) -> str:
    matches = [source for _, source in _blocks() if marker in source]
    assert len(matches) == 1, f"{len(matches)} blocks contain {marker!r}"
    return matches[0]


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [PY, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs and prints the output the page shows."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS
        assert len(_outputs()) == EXPECTED_BLOCKS

    def test_every_block_prints_its_stated_output(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for (line, source), expected in zip(_blocks(), _outputs(), strict=True):
            result = _run_block(source, tmp_path)
            if result.returncode != 0 or result.stderr.strip():
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")
            elif result.stdout.strip() != expected:
                failures.append(f"{PAGE.name}:{line}: printed {result.stdout!r}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        source = _block_containing("iter_attachments")
        broken = source.replace("message.get_body().get_payload()", "message.get_bdy()", 1)
        assert broken != source, "the mutation did not change the method called"

        result = _run_block(broken, tmp_path)

        assert result.returncode != 0
        assert "AttributeError" in result.stderr
