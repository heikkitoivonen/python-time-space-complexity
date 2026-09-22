"""Tests for docs/stdlib/xml.sax.md.

The page prices the module one event at a time: a parse pulls its source in
buffer-sized chunks, reports what each chunk completes, and holds three things
of its own - the piece it has to deliver whole, the scope open around the
current element, and the names it has met. All three space terms are settled by
traced allocation, which separates the states by orders of magnitude; the
per-call bounds, the attribute lookups and the handler contracts are settled by
observation - counted reads, counted comparisons, object identity. A stopwatch
is needed for the namespace claims, for closing prefix mappings, and for what
closing a parser releases.

Measurement scope:

* `parse()` reads through a `BytesIO` subclass that records every `read()`
  request: the first is the zero-length type probe in `prepare_input_source`,
  every later one asks for the same buffer size, and the count is the document
  divided by that size plus the probe and the empty read that ends the loop.
  The peak over a 10x larger document of the same shape stays within 2x, so
  nothing accumulates.
* The token bound is a peak over one 4 MB attribute value against the same
  value at 1 MB - more than 2x apart - and against a 4 MB text run, which
  peaks below half the 1 MB attribute because the run is split. That the run
  is split is observed directly: a 2 MB run arrives as more than one
  `characters()` call, and the pieces join back to the whole. What is not
  split is observed the same way: a 200,000-character uninterrupted entity
  replacement arrives in exactly one call, three times the 64 KiB read buffer,
  while a replacement carrying markup, a reference or a line break arrives as
  the events those make.
* The depth term is a peak at a fixed document size: 350,000 bytes nested
  50,000 deep peak more than 4x above the same 350,000 bytes flat, and 100,000
  open elements peak more than 4x above 10,000. Every nested element in those
  documents is `<a>`, one character of name and one name for all of them, so
  neither the token nor the vocabulary term can account for either gap. That
  the term is characters and not elements is a third peak: 20,000 elements open
  under a 50-character name peak more than half of the 980,000 characters that
  holds above the same depth under a one-character name, and the documents
  themselves are shared buffers that the peak does not count. The namespace
  URIs declared on those open elements are the same term: 5,000 nested
  declarations of one 210-character URI peak more than half of the million
  characters they hold above 5,000 declarations of a nine-character one, and
  since it is one URI redeclared, the vocabulary cannot be what grew.
* What `close()` and `reset()` release is timed four ways: over 20,000
  distinct names each costs more than 5x what it costs over one name repeated
  20,000 times, and each with 50,000 elements left open costs more than 5x
  itself with 100 - the close over an unfinished document, through an error
  handler that returns. Feeding a second document after a `close()` with no
  `reset()` between them is observed to deliver the whole second document,
  which is the driver resetting itself.
* The vocabulary term is the same shape: 240,007 bytes of 20,000 distinct
  nine-character names peak more than 4x above the same 240,007 bytes repeating
  one of them, both of them one root over 20,000 empty children. Name length is
  held equal, so the gap is the count.
* That a `feed()` call is not bounded by its own length is observed by peaking
  every call of a parse fed in 4 KiB chunks: the first chunk peaks below a
  tenth of the 4 MB attribute value being built, and some later call - the one
  that completes it, or the `close()` that finishes it - peaks above the whole
  value, and that call is the one a watching handler sees the start tag on.
* `parseString()` peaks above the input for a `str`, which `io.StringIO`
  copies, and below half of it for the same document as `bytes`, which
  `io.BytesIO` shares; a `bytearray` of the same bytes peaks above the input
  again, so the sharing is the immutable object's. Both forms report the same
  events. Imports are warmed before every allocation measurement, because the
  first `parse()` in a process also imports the driver and `urllib.request`.
* `AttributesNSImpl.getValueByQName()` and `getNameByQName()` are counted
  against a qname mapping whose values are a `str` subclass counting `__eq__`:
  5 and 50 attributes cost one comparison per attribute, and
  `getQNameByName()` costs none. `AttributesImpl` wrapping without copying is
  observed by mutating the dictionary it was given and seeing the change
  through the wrapper and through `copy()`; the listing methods are observed to
  build a new list per call.
* `prepareParser()` handing the system identifier to the parser is a peak too:
  on an `InputSource` whose stream holds four bytes, a 500,012-character
  identifier peaks more than half of itself above a short one. That the copy
  lives as long as the parse is read from Lib/xml/sax/expatreader.py, which
  passes it to `SetBase()`; the peak shows the copy is made, not how long it
  lasts.
* `XMLGenerator.startPrefixMapping()` snapshots the prefixes in scope: 1,000
  open mappings peak more than 20x above 100, which is the quadratic the row
  claims and which a per-mapping constant could not produce. Closing them is
  the same shape and is timed: closing 1,000 costs more than 20x closing 100,
  where an O(1) pop would cost 10x, because each call releases the map it
  replaces.
* Namespace mode is settled three ways. The per-attribute mappings are
  observed: a seven-attribute element arrives with seven qualified names and
  seven keys. That the URI is materialised per name is observed by identity -
  three elements in one namespace carry three distinct URI objects, and so do
  the three attribute keys of three one-attribute elements, with interning on
  and off - and timed:
  a 2,004-character URI costs more than 2x a 14-character one over documents of
  nearly equal length, both of them 20,000 elements with no attributes.
  Namespace processing against no namespace processing is timed on the same
  20,000 elements of five prefixed attributes each and asserted above 1.5x.
  With the prefix-mapping close and the parser-release tests, those are all the
  timing tests here.
* The error path is observed: the default `ErrorHandler` raises, and the
  counting source shows the tail of a 100,000-element document was never read.
  A handler that returns instead is given the same fault twice on a short
  malformed document, once from the chunk and once from the close. Returning
  does not resume parsing, and the count of two belongs to that input rather
  than to malformed input in general. `SAXParseException` is built with a
  locator whose four values are then all changed: the system id, line and
  column keep what they were given at construction, and only `getPublicId()`
  follows the locator.
* Callback contracts are observed against the Expat driver: element-content
  whitespace arrives through `characters()` and never through
  `ignorableWhitespace()`, an entity whose declaration is in an unread
  external subset arrives through `skippedEntity()`, notation and unparsed
  entity declarations reach the `DTDHandler`, comments, CDATA markers and the
  DTD boundary reach a `LexicalHandler` installed as a property, and an
  external general entity is resolved only with `feature_external_ges` on,
  where the resolver is handed the system id and its file is read from disk.
* Interning is observed by identity: four `<item/>` tags produce one name
  object with `feature_string_interning` on and four with it off. In namespace
  mode the five URIs reported for one namespace are five distinct objects with
  the feature either way, because the driver splits the expanded name itself.
  That is the delivered strings; what the feature does inside Expat is not
  observed here.
* The reader rows are observed on both classes: the base `XMLReader` installs
  the four default handlers and recognises no feature or property, while the
  driver answers the documented names, refuses validation, namespace prefixes
  and external parameter entities, refuses any feature during a parse, hands
  back the interning dictionary it was given, returns the input context only
  while parsing, and lets the content handler be replaced mid-parse. Each of
  the five documented source forms - name, path, byte stream, character
  stream and `InputSource` - parses to the same events, and
  `prepare_input_source()` is observed to read nothing but the type probe from
  a stream it wraps. `make_parser()` leaves the driver in `sys.modules`, and a
  subprocess shows importing `saxutils` brings `urllib.request` with it.
* `XMLGenerator.startDocument()` is observed to write the declaration and
  `endDocument()` to flush its writer exactly once; a filter is observed to
  pass `setFeature()` through to its parent.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* `prepare_input_source()` opening a system identifier through
  `urllib.request`. The row prices a network round trip, and no peer is
  reachable from the suite; only the local-file and stream branches run here.
* What a handler costs per event. Every parse bound excludes it by
  construction, and the tests use handlers that record or count.
* Whether another Expat build buffers as this one does. The token bound is
  measured through the Python API against the linked library; a build with a
  different internal buffer would move the peaks, not the shape.
* The documented `Attributes` and `AttributesNS` interfaces have no runtime
  objects of their own; `AttributesImpl` and `AttributesNSImpl` are what the
  driver passes and what the page prices, so the interface names carry no
  separate tests.
* `XMLReader.setLocale()` is asserted to raise, which is the only behaviour
  the shipped drivers have; a driver that implements locales is not tested.
* That the parser holds an internal DTD subset's declarations for the length of
  the parse follows from having to expand the entities they declare; a peak
  grows with the declarations, but the declarations are also the document, so
  the measurement does not separate holding them from reading them.
* Whether a chunk that completes a large piece pays for it in that `feed()` or
  in the `close()` after it is the linked Expat's reparse-deferral behaviour.
  The test asserts only that some call pays, which holds either way.
* The pass counts behind `escape()`, `unescape()` and `quoteattr()` - three
  substitutions plus one per entity pair, plus the three whitespace pairs
  `quoteattr()` adds - are read from Lib/xml/sax/saxutils.py. The tests
  observe the order those passes produce, which is what a caller can see, not
  how many string copies it took.
* Encodings other than UTF-8 and Latin-1, and DTD-heavy input, are not varied,
  and neither is the namespace mode of the depth and vocabulary measurements,
  which are outside it except for the one that varies a redeclared URI. The
  namespace timing test holds element count and attribute count fixed and
  varies only the feature.
"""

from __future__ import annotations

import io
import math
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import xml.sax
from collections.abc import Callable
from typing import Any
from xml.sax import handler, saxutils, xmlreader
from xml.sax.handler import (
    ContentHandler,
    DTDHandler,
    EntityResolver,
    ErrorHandler,
    LexicalHandler,
    feature_external_ges,
    feature_namespaces,
    feature_string_interning,
    feature_validation,
    property_lexical_handler,
)
from xml.sax.saxutils import XMLFilterBase, XMLGenerator, escape, quoteattr, unescape
from xml.sax.xmlreader import AttributesImpl, AttributesNSImpl, InputSource

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "xml.sax.md"
EXPECTED_BLOCKS = 16


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


def warm() -> None:
    """Import the driver and urllib before anything is measured."""
    xml.sax.parse(io.BytesIO(b"<root/>"), ContentHandler())


class CountingSource(io.BytesIO):
    """A byte stream that records the size of every read request."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.sizes: list[int] = []

    def read(self, size: int | None = -1) -> bytes:
        self.sizes.append(-1 if size is None else size)
        return super().read(size)


class Recorder(ContentHandler):
    """A content handler that records the events it is given."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[Any, ...]] = []

    def startElement(self, name: str, attrs: Any) -> None:
        self.events.append(("start", name, dict(attrs.items())))

    def endElement(self, name: str) -> None:
        self.events.append(("end", name))

    def characters(self, content: str) -> None:
        self.events.append(("chars", content))

    def startDocument(self) -> None:
        self.events.append(("startDocument",))

    def endDocument(self) -> None:
        self.events.append(("endDocument",))


class CountingStr(str):
    """A string that counts the equality comparisons made against it."""

    comparisons = 0

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return str.__eq__(self, other)

    def __hash__(self) -> int:
        return str.__hash__(self)


def flat_document(elements: int) -> bytes:
    """A document of `elements` short elements, with no long token in it."""
    return b"<root>" + b"<item/>" * elements + b"</root>"


class TestParseStreamsItsSource:
    """`xml.sax.parse(source, handler)` | O(n) | O(t + d + v): the source is
    pulled in buffer-sized chunks, so the read count follows the document while
    the memory follows the longest piece, the open elements and the names the
    document uses."""

    def test_reads_are_one_buffer_each(self) -> None:
        document = flat_document(40_000)
        source = CountingSource(document)

        xml.sax.parse(source, ContentHandler())

        assert source.sizes[0] == 0, "prepare_input_source probes the stream type first"
        buffers = set(source.sizes[1:])
        assert len(buffers) == 1, f"the parser asked for {buffers}, not one buffer size"
        bufsize = buffers.pop()
        assert 32_768 <= bufsize <= 65_536, (
            f"a {bufsize}-byte buffer is not the 64 KiB the page claims"
        )
        expected = math.ceil(len(document) / bufsize) + 2
        assert len(source.sizes) == expected, (
            f"{len(source.sizes)} reads of {bufsize} bytes for {len(document)} bytes; "
            f"the probe, {expected - 2} chunks and the empty read make {expected}"
        )

    def test_the_peak_does_not_follow_the_document(self) -> None:
        warm()
        small = flat_document(100_000)
        large = flat_document(1_000_000)

        small_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(small), ContentHandler()))
        large_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(large), ContentHandler()))

        assert large_peak < small_peak * 2, (
            f"a {len(large)}-byte document peaked at {large_peak} bytes against {small_peak} "
            f"for {len(small)}; holding the document would grow with it"
        )

    def test_the_documented_source_forms_all_parse(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "doc.xml"
        path.write_bytes(b"<root><item/></root>")
        source = InputSource(str(path))

        forms: list[Any] = [
            str(path),
            path,
            io.BytesIO(path.read_bytes()),
            io.StringIO("<root><item/></root>"),
            source,
        ]
        parsed = []
        for form in forms:
            recorder = Recorder()
            xml.sax.parse(form, recorder)
            parsed.append([event[1] for event in recorder.events if event[0] == "start"])

        assert parsed == [["root", "item"]] * 5

    def test_every_element_is_reported_once(self) -> None:
        recorder = Recorder()

        xml.sax.parse(io.BytesIO(flat_document(1_000)), recorder)

        starts = [event for event in recorder.events if event[0] == "start"]
        ends = [event for event in recorder.events if event[0] == "end"]
        assert len(starts) == len(ends) == 1_001
        assert recorder.events[0] == ("startDocument",)
        assert recorder.events[1] == ("start", "root", {})
        assert recorder.events[2] == ("start", "item", {})
        assert recorder.events[3] == ("end", "item")
        assert recorder.events[-2] == ("end", "root")
        assert recorder.events[-1] == ("endDocument",)


class TestTheParserHoldsOneToken:
    """`parse()` | O(t + d + v) space, the t term: a start tag is one piece and
    is held whole, attribute values and all, while a text run is split across
    calls and is not."""

    def test_a_long_run_of_text_arrives_in_pieces(self) -> None:
        run = "y" * 2_000_000
        document = ("<root>" + run + "</root>").encode()
        pieces: list[str] = []

        class Collect(ContentHandler):
            def characters(self, content: str) -> None:
                pieces.append(content)

        xml.sax.parse(io.BytesIO(document), Collect())

        assert len(pieces) > 1, "a 2 MB run arrived in one call, so nothing bounds a call"
        assert "".join(pieces) == run

    def test_the_peak_follows_the_longest_token(self) -> None:
        warm()
        small_attribute = b'<root a="' + b"z" * 1_000_000 + b'"/>'
        large_attribute = b'<root a="' + b"z" * 4_000_000 + b'"/>'
        long_text = b"<root>" + b"y" * 4_000_000 + b"</root>"

        small_peak = peak_bytes(
            lambda: xml.sax.parse(io.BytesIO(small_attribute), ContentHandler())
        )
        large_peak = peak_bytes(
            lambda: xml.sax.parse(io.BytesIO(large_attribute), ContentHandler())
        )
        text_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(long_text), ContentHandler()))

        assert large_peak > small_peak * 2, (
            f"a 4 MB attribute value peaked at {large_peak} bytes against {small_peak} for 1 MB; "
            "a bound that ignored the token would not move"
        )
        assert text_peak < small_peak / 2, (
            f"a 4 MB text run peaked at {text_peak} bytes against {small_peak} for a 1 MB "
            "attribute value; a run that had to be held whole would be the larger of the two"
        )


class TestTheParserHoldsTheOpenElements:
    """`parse()` | O(t + d + v) space, the d term: the parser keeps the elements
    open around the current one, so depth costs even when every tag in the
    document is short."""

    def test_depth_costs_where_the_same_size_flat_does_not(self) -> None:
        warm()
        flat = b"<root>" + b"<a/>" * 87_500 + b"</root>"
        deep = b"<a>" * 50_000 + b"</a>" * 50_000
        assert abs(len(flat) - len(deep)) < 20, "the two documents are the same size"

        flat_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(flat), ContentHandler()))
        deep_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(deep), ContentHandler()))

        assert deep_peak > flat_peak * 4, (
            f"{len(deep)} bytes nested 50,000 deep peaked at {deep_peak} against {flat_peak} for "
            f"{len(flat)} flat bytes; a bound in the document alone would not tell them apart"
        )

    def test_the_depth_term_is_counted_in_characters(self) -> None:
        warm()
        short = (b"<a>" * 20_000) + (b"</a>" * 20_000)
        long_name = b"a" * 50
        long = (b"<" + long_name + b">") * 20_000 + (b"</" + long_name + b">") * 20_000
        held = 20_000 * (len(long_name) - 1)

        short_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(short), ContentHandler()))
        long_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(long), ContentHandler()))

        assert long_peak > short_peak + held / 2, (
            f"20,000 elements open under a {len(long_name)}-character name peaked at {long_peak} "
            f"bytes against {short_peak} for a one-character name; the documents are shared "
            "buffers, so the difference is the names held open"
        )

    def test_the_open_scope_holds_a_namespace_uri_per_declaration(self) -> None:
        warm()
        depth = 5_000
        long_uri = "urn:fixed-" + "u" * 200

        def redeclaring(uri: str) -> bytes:
            opens = f'<a xmlns:p="{uri}">' * depth
            return (opens + "</a>" * depth).encode()

        short, long = redeclaring("urn:fixed"), redeclaring(long_uri)
        held = depth * (len(long_uri) - len("urn:fixed"))

        def parse(document: bytes) -> None:
            parser = xml.sax.make_parser()
            parser.setFeature(feature_namespaces, True)
            parser.setContentHandler(ContentHandler())
            parser.parse(io.BytesIO(document))

        short_peak = peak_bytes(lambda: parse(short))
        long_peak = peak_bytes(lambda: parse(long))

        assert long_peak > short_peak + held / 2, (
            f"{depth} declarations of a {len(long_uri)}-character URI peaked at {long_peak} "
            f"bytes against {short_peak} for the same count of a short one; one URI is declared "
            "over and over, so the vocabulary cannot be what grew"
        )

    def test_the_peak_grows_with_the_depth(self) -> None:
        warm()
        shallow = b"<a>" * 10_000 + b"</a>" * 10_000
        deeper = b"<a>" * 100_000 + b"</a>" * 100_000

        shallow_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(shallow), ContentHandler()))
        deeper_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(deeper), ContentHandler()))

        assert deeper_peak > shallow_peak * 4, (
            f"100,000 open elements peaked at {deeper_peak} bytes against {shallow_peak} for "
            "10,000; a constant stack would not move"
        )


class TestClosingAParserReleasesWhatItMet:
    """`IncrementalParser.close()` | O(t + d + v), and `reset()` | O(d + v) over
    a parser that read without closing: finishing releases what the parse
    accumulated - the names it met, and the elements it left open. The reset
    tests feed without closing, so it is the reset that does the releasing."""

    @staticmethod
    def _fed(distinct: int) -> Any:
        parser: Any = xml.sax.make_parser()
        parser.setContentHandler(ContentHandler())
        body = "".join(f"<n{index % distinct:05d}/>" for index in range(20_000))
        parser.feed("<r>" + body + "</r>")
        return parser

    @classmethod
    def _finish_ns(cls, distinct: int, method: str, repeats: int = 5) -> float:
        """Fastest of `repeats` calls of `method`, with the feeding left outside."""
        best: float | None = None
        for _ in range(repeats):
            parser = cls._fed(distinct)
            start = time.perf_counter_ns()
            getattr(parser, method)()
            elapsed = float(time.perf_counter_ns() - start)
            best = elapsed if best is None else min(best, elapsed)
        assert best is not None
        return best

    @pytest.mark.timing
    def test_closing_costs_the_vocabulary_it_drops(self) -> None:
        one_ns = self._finish_ns(1, "close")
        many_ns = self._finish_ns(20_000, "close")

        ratio = many_ns / one_ns
        assert ratio > 5, (
            f"closing over 20,000 distinct names cost x{ratio:.1f} of closing over one "
            f"({one_ns:.0f}ns to {many_ns:.0f}ns); a close that only finished the piece "
            "pending would not tell the two apart"
        )

    @pytest.mark.timing
    def test_closing_costs_the_elements_left_open(self) -> None:
        class Quiet(ErrorHandler):
            def fatalError(  # pyright: ignore[reportIncompatibleMethodOverride]
                self, exception: Any
            ) -> None:
                """An unfinished document is expected here."""

        def close_ns(depth: int, repeats: int = 5) -> float:
            best: float | None = None
            for _ in range(repeats):
                parser: Any = xml.sax.make_parser()
                parser.setContentHandler(ContentHandler())
                parser.setErrorHandler(Quiet())
                parser.feed("<a>" * depth)
                start = time.perf_counter_ns()
                parser.close()
                elapsed = float(time.perf_counter_ns() - start)
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        shallow_ns = close_ns(100)
        deep_ns = close_ns(50_000)

        ratio = deep_ns / shallow_ns
        assert ratio > 5, (
            f"closing with 50,000 elements open cost x{ratio:.1f} of closing with 100 "
            f"({shallow_ns:.0f}ns to {deep_ns:.0f}ns); the open stack goes with the parser"
        )

    @pytest.mark.timing
    def test_resetting_costs_the_elements_left_open(self) -> None:
        def reset_ns(depth: int, repeats: int = 5) -> float:
            best: float | None = None
            for _ in range(repeats):
                parser: Any = xml.sax.make_parser()
                parser.setContentHandler(ContentHandler())
                parser.feed("<a>" * depth)
                start = time.perf_counter_ns()
                parser.reset()
                elapsed = float(time.perf_counter_ns() - start)
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        shallow_ns = reset_ns(100)
        deep_ns = reset_ns(50_000)

        ratio = deep_ns / shallow_ns
        assert ratio > 5, (
            f"resetting with 50,000 elements open cost x{ratio:.1f} of resetting with 100 "
            f"({shallow_ns:.0f}ns to {deep_ns:.0f}ns); the open stack goes with the parser"
        )

    def test_feeding_after_a_close_resets_the_driver_itself(self) -> None:
        parser: Any = xml.sax.make_parser()
        first, second = Recorder(), Recorder()

        parser.setContentHandler(first)
        parser.feed("<first/>")
        parser.close()

        parser.setContentHandler(second)
        parser.feed("<second/>")  # no reset() in between
        parser.close()

        assert second.events == [
            ("startDocument",),
            ("start", "second", {}),
            ("end", "second"),
            ("endDocument",),
        ]

    @pytest.mark.timing
    def test_resetting_costs_the_vocabulary_it_drops(self) -> None:
        one_ns = self._finish_ns(1, "reset")
        many_ns = self._finish_ns(20_000, "reset")

        ratio = many_ns / one_ns
        assert ratio > 5, (
            f"resetting after 20,000 distinct names cost x{ratio:.1f} of resetting after one "
            f"({one_ns:.0f}ns to {many_ns:.0f}ns); building the fresh parser is the cheap half"
        )


class TestTheParserKeepsTheNamesItMeets:
    """`parse()` | O(t + d + v) space, the v term: the names a document uses go
    into a pool the parser keeps, so the variety costs where a repeat does
    not."""

    def test_a_vocabulary_costs_where_one_repeated_name_does_not(self) -> None:
        warm()
        distinct = (
            "<r>" + "".join(f"<name{index:05d}/>" for index in range(20_000)) + "</r>"
        ).encode()
        repeated = ("<r>" + "<name00000/>" * 20_000 + "</r>").encode()
        assert len(distinct) == len(repeated), "the two documents are the same size"

        distinct_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(distinct), ContentHandler()))
        repeated_peak = peak_bytes(lambda: xml.sax.parse(io.BytesIO(repeated), ContentHandler()))

        assert distinct_peak > repeated_peak * 4, (
            f"20,000 distinct names peaked at {distinct_peak} bytes against {repeated_peak} for "
            "the same bytes repeating one name; a bound without the vocabulary would match them"
        )


class TestAnEntityArrivesWhole:
    """`characters(content)` | O(c): an entity's replacement text can be
    delivered in one call far larger than the read buffer, so a call is not
    bounded by it. What splits a replacement is what is inside it - markup, a
    reference, a line break - and not the buffer."""

    def test_an_uninterrupted_replacement_longer_than_the_buffer_is_one_call(self) -> None:
        replacement = "R" * 200_000
        document = (
            f'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY big "{replacement}">]><r>&big;</r>'
        ).encode()
        sizes: list[int] = []

        class Collect(ContentHandler):
            def characters(self, content: str) -> None:
                sizes.append(len(content))

        xml.sax.parse(io.BytesIO(document), Collect())

        assert sizes == [len(replacement)], (
            f"the 200,000-character replacement arrived as {sizes}; the read buffer is 64 KiB"
        )

    def test_a_reference_inside_a_replacement_splits_the_call(self) -> None:
        document = (
            b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY mixed "left&amp;right">]><r>&mixed;</r>'
        )
        pieces: list[str] = []

        class Collect(ContentHandler):
            def characters(self, content: str) -> None:
                pieces.append(content)

        xml.sax.parse(io.BytesIO(document), Collect())

        assert pieces == ["left", "&", "right"], f"the replacement arrived as {pieces}"

    def test_a_line_break_inside_a_replacement_splits_the_call(self) -> None:
        document = (
            b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY lines "left\nright">]><r>&lines;</r>'
        )
        pieces: list[str] = []

        class Collect(ContentHandler):
            def characters(self, content: str) -> None:
                pieces.append(content)

        xml.sax.parse(io.BytesIO(document), Collect())

        assert pieces == ["left", "\n", "right"], f"the replacement arrived as {pieces}"

    def test_a_replacement_carrying_markup_arrives_as_its_events(self) -> None:
        document = (
            b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY mixed "left<child/>right">]><r>&mixed;</r>'
        )
        recorder = Recorder()

        xml.sax.parse(io.BytesIO(document), recorder)

        assert recorder.events == [
            ("startDocument",),
            ("start", "r", {}),
            ("chars", "left"),
            ("start", "child", {}),
            ("end", "child"),
            ("chars", "right"),
            ("end", "r"),
            ("endDocument",),
        ]


class TestParseStringWrapsTheInput:
    """`xml.sax.parseString(string, handler)` | O(n) for `str`, O(t + d + v) for
    `bytes`: the copy is `io.StringIO`'s, and `io.BytesIO` makes none for an
    immutable `bytes` object."""

    TEXT = "<root>" + "<item/>" * 100_000 + "</root>"

    def test_a_str_is_copied_and_bytes_are_not(self) -> None:
        warm()
        data = self.TEXT.encode()

        text_peak = peak_bytes(lambda: xml.sax.parseString(self.TEXT, ContentHandler()))
        bytes_peak = peak_bytes(lambda: xml.sax.parseString(data, ContentHandler()))

        assert text_peak > len(self.TEXT), (
            f"a {len(self.TEXT)}-character str peaked at {text_peak} bytes; "
            "a wrapped str would not pay for its own characters"
        )
        assert bytes_peak < len(data) / 2, (
            f"{len(data)} bytes peaked at {bytes_peak}; a copy would cost at least the input"
        )

        mutable = bytearray(data)
        mutable_peak = peak_bytes(lambda: xml.sax.parseString(mutable, ContentHandler()))

        assert mutable_peak > len(data), (
            f"a bytearray peaked at {mutable_peak}; only an immutable bytes object is shared"
        )

    def test_both_forms_report_the_same_events(self) -> None:
        document = b'<root a="1"><item>text</item></root>'
        from_bytes, from_text = Recorder(), Recorder()

        xml.sax.parseString(document, from_bytes)
        xml.sax.parseString(document.decode(), from_text)

        assert from_bytes.events == from_text.events


class TestMakingAParser:
    """`xml.sax.make_parser(parser_list=())` | O(m): the candidates are joined
    into one list, each is imported once, and the first that builds is
    returned."""

    def test_the_default_list_is_the_expat_driver(self) -> None:
        assert "PY_SAX_PARSER" not in os.environ, "the environment overrides the default list"
        assert xml.sax.default_parser_list == ["xml.sax.expatreader"]

    def test_the_parser_supports_incremental_parsing(self) -> None:
        parser = xml.sax.make_parser()

        assert isinstance(parser, xmlreader.IncrementalParser)
        assert isinstance(parser, xmlreader.XMLReader)

    def test_an_unimportable_driver_is_passed_over(self) -> None:
        parser = xml.sax.make_parser(["xml.sax.no_such_driver"])

        assert isinstance(parser, xmlreader.XMLReader)

    def test_the_driver_is_imported_once(self) -> None:
        xml.sax.make_parser()
        assert "xml.sax.expatreader" in sys.modules

        first = sys.modules["xml.sax.expatreader"]
        xml.sax.make_parser()
        assert sys.modules["xml.sax.expatreader"] is first

    def test_which_submodules_importing_the_package_binds(self) -> None:
        script = (
            "import sys, xml.sax;"
            "print(hasattr(xml.sax, 'handler'), hasattr(xml.sax, 'xmlreader'),"
            " hasattr(xml.sax, 'saxutils'), 'urllib.request' in sys.modules);"
            "import xml.sax.saxutils;"
            "print(hasattr(xml.sax, 'saxutils'), 'urllib.request' in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        before, after = result.stdout.split("\n")[:2]
        assert before == "True True False False", "importing xml.sax bound more than it says"
        assert after == "True True", "saxutils did not bring urllib.request with it"

    def test_no_driver_at_all_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(xml.sax, "default_parser_list", [])

        with pytest.raises(xml.sax.SAXReaderNotAvailable):
            xml.sax.make_parser(["xml.sax.no_such_driver"])


class TestFeedingAParser:
    """`IncrementalParser.feed(data)` | O(len(data)) amortized, with whatever
    namespace mode adds: a chunk reports what it completes, an unfinished piece
    waits for the rest, and the call that delivers it pays for it."""

    def test_an_event_waits_for_the_chunk_that_completes_it(self) -> None:
        parser: Any = xml.sax.make_parser()
        recorder = Recorder()
        parser.setContentHandler(recorder)

        parser.feed("<root><ite")

        assert [event[1] for event in recorder.events if event[0] == "start"] == ["root"], (
            "a tag split across chunks was reported before the chunk that finishes it"
        )

        parser.feed("m/>")
        parser.feed("</root>")
        parser.close()

        assert [event[1] for event in recorder.events if event[0] == "start"] == ["root", "item"]
        assert recorder.events[-1] == ("endDocument",)

    def test_a_call_is_not_bounded_by_the_bytes_it_is_given(self) -> None:
        warm()
        value = b"z" * 4_000_000
        document = b'<root a="' + value + b'"/>'
        chunks = [document[index : index + 4_096] for index in range(0, len(document), 4_096)]
        parser: Any = xml.sax.make_parser()

        delivered: list[int] = []
        current = 0

        class Watch(ContentHandler):
            def startElement(self, name: str, attrs: Any) -> None:
                delivered.append(current)

        parser.setContentHandler(Watch())
        peaks = []
        for index, chunk in enumerate(chunks):
            current = index
            peaks.append(peak_bytes(lambda chunk=chunk: parser.feed(chunk)))
        current = len(chunks)
        peaks.append(peak_bytes(parser.close))

        assert peaks[0] < len(value) / 10, f"the first 4 KiB chunk peaked at {peaks[0]} bytes"
        assert delivered == [len(chunks)] or delivered == [len(chunks) - 1], (
            f"the start tag was delivered on call {delivered}, neither the last feed nor the close"
        )
        assert peaks[delivered[0]] > len(value), (
            f"the call that delivered the {len(value)}-character value peaked at "
            f"{peaks[delivered[0]]} bytes, so it did not pay for the piece it completed"
        )

    def test_reset_prepares_the_parser_for_another_document(self) -> None:
        parser: Any = xml.sax.make_parser()
        first = Recorder()
        parser.setContentHandler(first)
        parser.feed("<first/>")
        parser.close()

        parser.reset()
        second = Recorder()
        parser.setContentHandler(second)
        parser.feed("<second/>")
        parser.close()

        assert [event[1] for event in second.events if event[0] == "start"] == ["second"]


class TestHandlerCallbacks:
    """The handler rows price the event: the base methods do nothing except
    `setDocumentLocator()`, which stores the locator, and which of them the
    Expat driver reaches at all is a property of the driver."""

    def test_the_base_content_handler_does_nothing_but_store_the_locator(self) -> None:
        base = ContentHandler()
        locator = xmlreader.Locator()

        assert base.setDocumentLocator(locator) is None
        assert vars(base)["_locator"] is locator, "the one base method that stores anything"

        assert base.startDocument() is None
        assert base.endDocument() is None
        assert base.startElement("a", AttributesImpl({})) is None
        assert base.endElement("a") is None
        assert base.startElementNS((None, "a"), None, AttributesNSImpl({}, {})) is None
        assert base.endElementNS((None, "a"), None) is None
        assert base.startPrefixMapping("p", "urn:p") is None
        assert base.endPrefixMapping("p") is None
        assert base.characters("text") is None
        assert base.ignorableWhitespace(" ") is None
        assert base.processingInstruction("target", "data") is None
        assert base.skippedEntity("name") is None

    def test_the_locator_is_set_before_the_first_event(self) -> None:
        seen: list[Any] = []
        positions: list[tuple[int, int]] = []

        class Located(Recorder):
            def setDocumentLocator(self, locator: Any) -> None:
                seen.append((locator, len(self.events)))

            def startElement(self, name: str, attrs: Any) -> None:
                super().startElement(name, attrs)
                locator = seen[0][0]
                positions.append((locator.getLineNumber(), locator.getColumnNumber()))

        located = Located()
        xml.sax.parseString(b"<root/>", located)

        assert len(seen) == 1
        locator, events_before = seen[0]
        assert events_before == 0, "the locator arrived after an event"
        assert positions == [(1, 0)], "the locator points at the start of the tag"
        with pytest.raises(ReferenceError):
            locator.getLineNumber()  # a weak proxy: the locator dies with its parser

    def test_element_content_whitespace_arrives_as_characters(self) -> None:
        document = (
            b'<?xml version="1.0"?>\n'
            b"<!DOCTYPE root [<!ELEMENT root (item)*><!ELEMENT item EMPTY>]>\n"
            b"<root>\n  <item/>\n</root>"
        )
        whitespace: list[str] = []
        text: list[str] = []

        class Split(ContentHandler):
            # The base parameter is named `whitespace`, which the recorder shadows here.
            def ignorableWhitespace(  # pyright: ignore[reportIncompatibleMethodOverride]
                self, whitespace_content: str
            ) -> None:
                whitespace.append(whitespace_content)

            def characters(self, content: str) -> None:
                text.append(content)

        xml.sax.parseString(document, Split())

        assert whitespace == [], "the Expat driver never installs an ignorable-whitespace handler"
        assert "".join(text).strip() == ""
        assert "".join(text) != ""

    def test_an_unresolvable_entity_is_reported_as_skipped(self) -> None:
        document = b'<?xml version="1.0"?><!DOCTYPE root SYSTEM "ext.dtd"><root>&unknown;x</root>'
        skipped: list[str] = []

        class Skips(ContentHandler):
            def skippedEntity(self, name: str) -> None:
                skipped.append(name)

        xml.sax.parseString(document, Skips())

        assert skipped == ["unknown"]

    def test_declarations_reach_the_dtd_handler(self) -> None:
        document = (
            b'<?xml version="1.0"?>\n'
            b"<!DOCTYPE root [\n"
            b'  <!ENTITY logo SYSTEM "logo.gif" NDATA gif>\n'
            b'  <!NOTATION gif SYSTEM "image/gif">\n'
            b"]>\n<root/>"
        )
        events: list[tuple[Any, ...]] = []

        class Declarations(DTDHandler):
            def notationDecl(self, name: str, publicId: Any, systemId: Any) -> None:
                events.append(("notation", name, publicId, systemId))

            def unparsedEntityDecl(
                self, name: str, publicId: Any, systemId: Any, ndata: str
            ) -> None:
                events.append(("unparsed", name, systemId, ndata))

        parser = xml.sax.make_parser()
        parser.setContentHandler(ContentHandler())
        parser.setDTDHandler(Declarations())
        parser.parse(io.BytesIO(document))

        assert ("unparsed", "logo", "logo.gif", "gif") in events
        assert ("notation", "gif", None, "image/gif") in events

    def test_lexical_events_reach_a_lexical_handler(self) -> None:
        document = (
            b'<?xml version="1.0"?>\n<!DOCTYPE root [<!ELEMENT root ANY>]>\n'
            b"<root><!-- note --><![CDATA[raw]]></root>"
        )
        events: list[tuple[Any, ...]] = []

        class Lexical(LexicalHandler):
            def comment(self, content: str) -> None:
                events.append(("comment", content))

            def startCDATA(self) -> None:
                events.append(("startCDATA",))

            def endCDATA(self) -> None:
                events.append(("endCDATA",))

            def startDTD(self, name: str, public_id: Any, system_id: Any) -> None:
                events.append(("startDTD", name))

            def endDTD(self) -> None:
                events.append(("endDTD",))

        lexical = Lexical()
        parser = xml.sax.make_parser()
        parser.setContentHandler(ContentHandler())
        parser.setProperty(property_lexical_handler, lexical)
        assert parser.getProperty(property_lexical_handler) is lexical
        parser.parse(io.BytesIO(document))

        assert events == [
            ("startDTD", "root"),
            ("endDTD",),
            ("comment", " note "),
            ("startCDATA",),
            ("endCDATA",),
        ]

    def test_external_entities_are_read_only_when_the_feature_is_on(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "part.xml").write_text("inside", encoding="utf-8")
        document = (
            b'<?xml version="1.0"?>\n'
            b'<!DOCTYPE root [<!ENTITY part SYSTEM "part.xml">]>\n'
            b"<root>&part;</root>"
        )
        asked: list[Any] = []

        class Resolver(EntityResolver):
            def resolveEntity(self, publicId: Any, systemId: Any) -> Any:
                asked.append(systemId)
                return systemId

        def parse(external: bool) -> tuple[list[str], list[Any]]:
            asked.clear()
            text: list[str] = []

            class Collect(ContentHandler):
                def characters(self, content: str) -> None:
                    text.append(content)

            parser = xml.sax.make_parser()
            parser.setFeature(feature_external_ges, external)
            parser.setContentHandler(Collect())
            parser.setEntityResolver(Resolver())
            source = InputSource(str(tmp_path / "doc.xml"))
            source.setByteStream(io.BytesIO(document))
            parser.parse(source)
            return text, list(asked)

        off_text, off_asked = parse(False)
        on_text, on_asked = parse(True)

        assert off_asked == [], "the resolver ran with external entities off"
        assert "inside" not in "".join(off_text)
        assert on_asked and on_asked[0].endswith("part.xml")
        assert "inside" in "".join(on_text)


class TestErrorsStopTheParse:
    """`ErrorHandler.fatalError(exception)` raises, so a malformed document
    costs the prefix that parsed, not the file."""

    BROKEN = b"<root>]]>" + b"<item/>" * 100_000 + b"</root>"

    def test_the_tail_is_never_read(self) -> None:
        source = CountingSource(self.BROKEN)

        with pytest.raises(xml.sax.SAXParseException) as raised:
            xml.sax.parse(source, ContentHandler())

        assert len(source.sizes) <= 2, f"{len(source.sizes)} reads for a fault in the first chunk"
        assert raised.value.getLineNumber() == 1
        column = raised.value.getColumnNumber()
        assert column is not None and column < 20
        assert "not well-formed" in raised.value.getMessage()

    def test_a_handler_that_returns_sees_the_fault_twice(self) -> None:
        collected: list[xml.sax.SAXParseException] = []

        class Collect(ErrorHandler):
            def fatalError(  # pyright: ignore[reportIncompatibleMethodOverride]
                self, exception: Any
            ) -> None:
                collected.append(exception)

        xml.sax.parseString(b"<root><item></root>", ContentHandler(), Collect())

        assert len(collected) == 2, "the chunk and the close each report the fault"
        assert {error.getMessage() for error in collected} == {"mismatched tag"}

    def test_the_base_error_handler_raises_and_warns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        base = ErrorHandler()
        exception = xml.sax.SAXException("careful")

        with pytest.raises(xml.sax.SAXException) as from_error:
            base.error(exception)
        with pytest.raises(xml.sax.SAXException) as from_fatal:
            base.fatalError(exception)

        assert from_error.value is exception and from_fatal.value is exception
        assert base.warning(exception) is None
        assert capsys.readouterr().out.strip() == "careful"

    def test_the_exception_caches_the_position_but_not_the_public_id(self) -> None:
        class MovingLocator(xmlreader.Locator):
            def __init__(self) -> None:
                self.public = "first"
                self.system = "doc.xml"
                self.line = 3
                self.column = 7

            def getColumnNumber(self) -> int:
                return self.column

            def getLineNumber(self) -> int:
                return self.line

            def getPublicId(self) -> str:
                return self.public

            def getSystemId(self) -> str:
                return self.system

        locator = MovingLocator()
        error = xml.sax.SAXParseException("bad", None, locator)
        locator.public, locator.system, locator.line, locator.column = "second", "other.xml", 99, 99

        assert error.getLineNumber() == 3 and error.getColumnNumber() == 7
        assert error.getSystemId() == "doc.xml", "the system id moved with the locator"
        assert error.getPublicId() == "second", "the public id is asked of the locator each time"
        assert str(error) == "doc.xml:3:7: bad"
        assert error.getMessage() == "bad"
        assert error.getException() is None

    def test_the_exception_hierarchy(self) -> None:
        assert issubclass(xml.sax.SAXParseException, xml.sax.SAXException)
        assert issubclass(xml.sax.SAXNotRecognizedException, xml.sax.SAXException)
        assert issubclass(xml.sax.SAXNotSupportedException, xml.sax.SAXException)
        assert issubclass(xml.sax.SAXReaderNotAvailable, xml.sax.SAXNotSupportedException)
        wrapped = ValueError("cause")
        assert xml.sax.SAXException("msg", wrapped).getException() is wrapped


class TestAttributes:
    """`AttributesImpl` | O(1) lookups, O(a) listings: the wrapper holds the
    parser's mapping rather than a copy of it."""

    def test_the_wrapper_shares_the_mapping_it_was_given(self) -> None:
        source = {"a": "1"}
        attrs = AttributesImpl(source)
        copy = attrs.copy()

        source["b"] = "2"

        assert attrs["b"] == "2", "AttributesImpl copied the mapping it was given"
        assert copy["b"] == "2", "copy() made an independent mapping"
        assert len(attrs) == attrs.getLength() == 2

    def test_lookups_are_by_name(self) -> None:
        attrs = AttributesImpl({"id": "1", "tag": "x"})

        assert attrs.getValue("id") == attrs["id"] == "1"
        assert attrs.get("missing", "?") == "?" and attrs.get("missing") is None
        assert ("id" in attrs) and ("missing" not in attrs)
        assert attrs.getType("id") == attrs.getType("missing") == "CDATA"
        assert attrs.getValueByQName("id") == "1"
        assert attrs.getNameByQName("id") == "id"
        assert attrs.getQNameByName("id") == "id"

    def test_each_listing_builds_a_new_list(self) -> None:
        attrs = AttributesImpl({"id": "1", "tag": "x"})

        for listing in (attrs.getNames, attrs.getQNames, attrs.keys, attrs.items, attrs.values):
            first, second = listing(), listing()
            assert isinstance(first, list), f"{listing.__name__}() is not a list"
            assert first == second and first is not second, (
                f"{listing.__name__}() returned the same object twice"
            )

    def test_a_qualified_name_is_found_by_scanning(self) -> None:
        for count in (5, 50):
            attrs: Any = {(None, f"n{index}"): f"v{index}" for index in range(count)}
            qnames: Any = {key: CountingStr(f"q{index}") for index, key in enumerate(attrs)}
            implementation = AttributesNSImpl(attrs, qnames)
            last = f"q{count - 1}"

            CountingStr.comparisons = 0
            value = implementation.getValueByQName(last)
            by_value = CountingStr.comparisons

            CountingStr.comparisons = 0
            name = implementation.getNameByQName(last)
            by_name = CountingStr.comparisons

            CountingStr.comparisons = 0
            qname = implementation.getQNameByName((None, f"n{count - 1}"))
            by_key = CountingStr.comparisons

            assert value == f"v{count - 1}"
            assert name == (None, f"n{count - 1}")
            assert qname == last

            assert by_value == by_name == count, (
                f"{count} attributes cost {by_value} and {by_name} comparisons"
            )
            assert by_key == 0, f"the keyed lookup compared {by_key} qualified names"

    def test_the_namespace_wrapper_shares_both_mappings(self) -> None:
        attrs: Any = {("urn:d", "id"): "1"}
        qnames: Any = {("urn:d", "id"): "d:id"}
        implementation = AttributesNSImpl(attrs, qnames)
        copy = implementation.copy()

        attrs[("urn:d", "extra")] = "2"
        qnames[("urn:d", "extra")] = "d:extra"

        assert copy.getValue(("urn:d", "extra")) == "2"
        assert copy.getQNameByName(("urn:d", "extra")) == "d:extra", "copy() copied the qnames"
        assert sorted(implementation.getQNames()) == ["d:extra", "d:id"]
        assert implementation.getQNames() is not implementation.getQNames()


class TestNamespaceMode:
    """`feature_namespaces` moves elements to the `*NS` callbacks, and the
    driver splits the element name and every attribute name before the call."""

    @staticmethod
    def _document(elements: int, attributes: int) -> bytes:
        tags = "".join(
            "<d:item " + " ".join(f'd:k{index}="{index}"' for index in range(attributes)) + "/>"
            for _ in range(elements)
        )
        return ('<r xmlns:d="urn:d">' + tags + "</r>").encode()

    def test_names_arrive_split_into_pairs(self) -> None:
        seen: list[tuple[Any, ...]] = []

        class Namespaced(ContentHandler):
            def startElementNS(self, name: Any, qname: Any, attrs: Any) -> None:
                if name[1] == "item":
                    seen.append((name, attrs.getValue(("urn:d", "k0")), attrs.getQNames()))

            def startPrefixMapping(self, prefix: Any, uri: str) -> None:
                seen.append(("prefix", prefix, uri))

        parser = xml.sax.make_parser()
        parser.setFeature(feature_namespaces, True)
        parser.setContentHandler(Namespaced())
        parser.parse(io.BytesIO(self._document(1, 1)))

        assert seen[0] == ("prefix", "d", "urn:d")
        assert seen[1] == (("urn:d", "item"), "0", ["d:k0"])

    def test_the_attribute_mappings_have_one_entry_per_attribute(self) -> None:
        seen: list[int] = []

        class Counting(ContentHandler):
            def startElementNS(self, name: Any, qname: Any, attrs: Any) -> None:
                if name[1] == "item":
                    seen.append(len(attrs.getQNames()))
                    seen.append(len(attrs.keys()))

        parser = xml.sax.make_parser()
        parser.setFeature(feature_namespaces, True)
        parser.setContentHandler(Counting())
        parser.parse(io.BytesIO(self._document(1, 7)))

        assert seen == [7, 7], "the driver builds both mappings from the element's attributes"

    def test_the_namespace_uri_is_built_into_every_name(self) -> None:
        uris: list[str] = []

        class Seen(ContentHandler):
            def startElementNS(self, name: Any, qname: Any, attrs: Any) -> None:
                if name[1] == "item":
                    uris.append(name[0])

        parser = xml.sax.make_parser()
        parser.setFeature(feature_namespaces, True)
        parser.setContentHandler(Seen())
        parser.parse(io.BytesIO(self._document(3, 0)))

        assert uris == ["urn:d"] * 3
        assert len({id(uri) for uri in uris}) == 3, "the URI is one object, not one per name"

    @pytest.mark.parametrize("interning", [False, True])
    def test_an_attribute_key_carries_its_own_copy_of_the_uri(self, interning: bool) -> None:
        document = b'<r xmlns:d="urn:a-long-uri">' + b'<d:i d:k="1"/>' * 3 + b"</r>"
        keys: list[str] = []

        class Seen(ContentHandler):
            def startElementNS(self, name: Any, qname: Any, attrs: Any) -> None:
                if name[1] == "i":
                    keys.extend(key[0] for key in attrs.keys())

        parser = xml.sax.make_parser()
        parser.setFeature(feature_namespaces, True)
        parser.setFeature(feature_string_interning, interning)
        parser.setContentHandler(Seen())
        parser.parse(io.BytesIO(document))

        assert keys == ["urn:a-long-uri"] * 3
        assert len({id(uri) for uri in keys}) == 3, (
            "the attribute keys shared one URI object; the row prices one per name reported"
        )

    @pytest.mark.timing
    def test_a_long_uri_costs_at_every_name_it_reaches(self) -> None:
        def document(uri_length: int) -> bytes:
            uri = "urn:" + "u" * uri_length
            return (f'<r xmlns:d="{uri}">' + "<d:i/>" * 20_000 + "</r>").encode()

        short, long = document(10), document(2_000)

        def parse(source: bytes) -> None:
            parser = xml.sax.make_parser()
            parser.setFeature(feature_namespaces, True)
            parser.setContentHandler(ContentHandler())
            parser.parse(io.BytesIO(source))

        short_ns = best_ns(lambda: parse(short), repeats=3)
        long_ns = best_ns(lambda: parse(long), repeats=3)

        ratio = long_ns / short_ns
        assert ratio > 2, (
            f"a 2,000-character URI cost x{ratio:.2f} against a 10-character one "
            f"({short_ns:.0f}ns to {long_ns:.0f}ns) over documents of {len(short)} and "
            f"{len(long)} bytes; the URI is materialised into every name reported"
        )

    @pytest.mark.timing
    def test_namespace_processing_costs_more_than_the_plain_parse(self) -> None:
        document = self._document(20_000, 5)

        def parse(namespaces: bool) -> None:
            parser = xml.sax.make_parser()
            parser.setFeature(feature_namespaces, namespaces)
            parser.setContentHandler(ContentHandler())
            parser.parse(io.BytesIO(document))

        plain_ns = best_ns(lambda: parse(False), repeats=3)
        namespaced_ns = best_ns(lambda: parse(True), repeats=3)

        ratio = namespaced_ns / plain_ns
        assert ratio > 1.5, (
            f"namespace processing cost x{ratio:.2f} ({plain_ns:.0f}ns to {namespaced_ns:.0f}ns) "
            "over the same 20,000 elements of five attributes each"
        )


class TestInterning:
    """`feature_string_interning` makes the name handed to each `startElement()`
    call the same object, so a handler that keeps its names keeps one per
    distinct name rather than one per element."""

    @staticmethod
    def _names(interning: bool) -> list[str]:
        names: list[str] = []

        class Names(ContentHandler):
            def startElement(self, name: str, attrs: Any) -> None:
                names.append(name)

        parser = xml.sax.make_parser()
        parser.setFeature(feature_string_interning, interning)
        assert parser.getFeature(feature_string_interning) is interning
        parser.setContentHandler(Names())
        parser.parse(io.BytesIO(flat_document(4)))
        return names[1:]

    def test_repeated_names_become_one_object(self) -> None:
        interned = self._names(True)
        separate = self._names(False)

        assert len(interned) == len(separate) == 4
        assert len({id(name) for name in interned}) == 1
        assert len({id(name) for name in separate}) == 4

    def test_the_uris_it_reports_in_namespace_mode_stay_distinct(self) -> None:
        document = b'<r xmlns:d="urn:a-long-uri">' + b"<d:i/>" * 5 + b"</r>"

        def uris(interning: bool) -> list[str]:
            seen: list[str] = []

            class Seen(ContentHandler):
                def startElementNS(self, name: Any, qname: Any, attrs: Any) -> None:
                    if name[1] == "i":
                        seen.append(name[0])

            parser = xml.sax.make_parser()
            parser.setFeature(feature_namespaces, True)
            parser.setFeature(feature_string_interning, interning)
            parser.setContentHandler(Seen())
            parser.parse(io.BytesIO(document))
            return seen

        with_interning, without = uris(True), uris(False)

        assert with_interning == without == ["urn:a-long-uri"] * 5
        assert len({id(uri) for uri in with_interning}) == 5, (
            "interning reached the URIs the driver split out of the expanded names"
        )
        assert len({id(uri) for uri in without}) == 5


class TestXMLGenerator:
    """`XMLGenerator` writes what it is told, and only its prefix mappings
    cost more than the characters they write."""

    def test_a_parse_round_trips_through_the_generator(self) -> None:
        output = io.StringIO()
        generator = XMLGenerator(output, encoding="utf-8", short_empty_elements=True)

        xml.sax.parseString(b'<root a="1&amp;2"><child/>text</root>', generator)

        assert output.getvalue().endswith('<root a="1&amp;2"><child/>text</root>')

    def test_text_is_escaped_and_whitespace_is_not(self) -> None:
        escaped, raw = io.StringIO(), io.StringIO()

        XMLGenerator(escaped, encoding="utf-8").characters("a < b")
        XMLGenerator(raw, encoding="utf-8").ignorableWhitespace("a < b")

        assert escaped.getvalue() == "a &lt; b"
        assert raw.getvalue() == "a < b"

    def test_the_document_events_write_the_declaration_and_flush(self) -> None:
        flushes = []

        class Recording(io.StringIO):
            def flush(self) -> None:
                flushes.append(self.getvalue())

        output = Recording()
        generator = XMLGenerator(output, encoding="utf-8")

        generator.startDocument()
        generator.processingInstruction("target", "data")
        generator.endDocument()

        assert output.getvalue() == '<?xml version="1.0" encoding="utf-8"?>\n<?target data?>'
        assert len(flushes) == 1, "endDocument flushes the writer once"

    def test_no_output_means_standard_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        XMLGenerator().characters("a < b")

        assert capsys.readouterr().out == "a &lt; b"

    def test_open_prefix_mappings_cost_their_own_square(self) -> None:
        def nest(mappings: int) -> None:
            generator = XMLGenerator(io.StringIO(), encoding="utf-8")
            for index in range(mappings):
                generator.startPrefixMapping(f"p{index}", f"urn:{index}")
            for index in reversed(range(mappings)):
                generator.endPrefixMapping(f"p{index}")

        nest(10)
        small_peak = peak_bytes(lambda: nest(100))
        large_peak = peak_bytes(lambda: nest(1_000))

        assert large_peak > small_peak * 20, (
            f"1,000 open mappings peaked at {large_peak} bytes against {small_peak} for 100; "
            "a per-mapping constant would give x10"
        )


class TestClosingAPrefixMappingReleasesTheMapItReplaces:
    """`XMLGenerator.endPrefixMapping(prefix)` | O(p): the pop is constant, but
    the map it drops is the p prefixes in scope, and freeing it is not."""

    @staticmethod
    def _closes_ns(mappings: int, repeats: int = 5) -> float:
        best: float | None = None
        for _ in range(repeats):
            generator = XMLGenerator(io.StringIO(), encoding="utf-8")
            for index in range(mappings):
                generator.startPrefixMapping(f"p{index}", f"urn:{index}")
            start = time.perf_counter_ns()
            for index in reversed(range(mappings)):
                generator.endPrefixMapping(f"p{index}")
            elapsed = float(time.perf_counter_ns() - start)
            best = elapsed if best is None else min(best, elapsed)
        assert best is not None
        return best

    @pytest.mark.timing
    def test_closing_them_all_is_not_linear_in_their_number(self) -> None:
        small = self._closes_ns(100)
        large = self._closes_ns(1_000)

        ratio = large / small
        assert ratio > 20, (
            f"closing 1,000 mappings cost x{ratio:.1f} of closing 100 "
            f"({small:.0f}ns to {large:.0f}ns); an O(1) pop would give x10"
        )


class TestFilterChains:
    """`XMLFilterBase` | O(1) per event per filter: a chain of f filters adds f
    calls to each event and re-parses nothing."""

    def test_each_filter_sees_each_event_once(self) -> None:
        seen: list[list[tuple[str, str]]] = []

        class Recording(XMLFilterBase):
            def __init__(self, parent: Any) -> None:
                super().__init__(parent)
                self.index = len(seen)
                seen.append([])

            def startElement(self, name: str, attrs: Any) -> None:
                seen[self.index].append(("start", name))
                super().startElement(name, attrs)

            def endElement(self, name: str) -> None:
                seen[self.index].append(("end", name))
                super().endElement(name)

        chain: Any = xml.sax.make_parser()
        for _ in range(3):
            chain = Recording(chain)
        recorder = Recorder()
        chain.setContentHandler(recorder)

        chain.parse(io.BytesIO(flat_document(50)))

        expected = [event[:2] for event in recorder.events if event[0] in {"start", "end"}]
        assert len(expected) == 102, "50 items and the root, opened and closed"
        for index, events in enumerate(seen):
            assert events == expected, f"filter {index} saw a different stream"

    def test_a_filter_delegates_configuration_to_its_parent(self) -> None:
        parent = xml.sax.make_parser()
        filtered = XMLFilterBase(parent)

        filtered.setFeature(feature_namespaces, True)

        assert filtered.getFeature(feature_namespaces) is True
        assert parent.getFeature(feature_namespaces) is True
        with pytest.raises(xml.sax.SAXNotSupportedException):
            filtered.setLocale("fi_FI")

    def test_a_filter_rewrites_the_events_it_forwards(self) -> None:
        class Upper(XMLFilterBase):
            def characters(self, content: str) -> None:
                super().characters(content.upper())

        output = io.StringIO()
        parent = xml.sax.make_parser()
        chain = Upper(parent)
        generator: Any = XMLGenerator(output, encoding="utf-8")
        chain.setContentHandler(generator)

        chain.parse(io.BytesIO(b"<root>abc</root>"))

        assert output.getvalue().endswith("<root>ABC</root>")
        assert chain.getParent() is parent
        chain.setParent(xml.sax.make_parser())
        assert chain.getParent() is not parent


class TestEscaping:
    """`escape()`, `unescape()` and `quoteattr()` | O(c·(1 + r)): one pass per
    substitution, with the ampersand at opposite ends of the two orders."""

    def test_the_three_markup_characters(self) -> None:
        assert escape("a < b & c > d") == "a &lt; b &amp; c &gt; d"
        assert unescape("a &lt; b &amp; c &gt; d") == "a < b & c > d"

    def test_the_ampersand_goes_first_and_comes_back_last(self) -> None:
        assert escape("&", {"&amp;": "[amp]"}) == "[amp]", "the pairs see escaped text"
        assert unescape("&amp;lt;") == "&lt;", "the ampersand is restored after the rest"

    def test_extra_pairs_are_applied_after_the_three(self) -> None:
        assert escape("a-b", {"-": "&#45;"}) == "a&#45;b"
        assert unescape("a&#45;b", {"&#45;": "-"}) == "a-b"

    def test_quoteattr_picks_the_quote_and_escapes_whitespace(self) -> None:
        assert quoteattr("plain") == '"plain"'
        assert quoteattr('say "hi"') == "'say \"hi\"'"
        assert quoteattr("mix \" and '") == '"mix &quot; and \'"'
        assert quoteattr("line\nbreak\ttab\rreturn") == '"line&#10;break&#9;tab&#13;return"'


class TestReaderConfiguration:
    """The `XMLReader` rows: handler slots and the feature and property names
    are O(1), and the base class recognises nothing."""

    def test_the_base_reader_installs_defaults_and_implements_nothing(self) -> None:
        reader = xmlreader.XMLReader()

        assert isinstance(reader.getContentHandler(), ContentHandler)
        assert isinstance(reader.getDTDHandler(), DTDHandler)
        assert isinstance(reader.getEntityResolver(), EntityResolver)
        assert isinstance(reader.getErrorHandler(), ErrorHandler)
        with pytest.raises(NotImplementedError):
            reader.parse(io.BytesIO(b"<root/>"))
        with pytest.raises(xml.sax.SAXNotSupportedException):
            reader.setLocale("fi_FI")
        for call in (
            lambda: reader.getFeature(feature_namespaces),
            lambda: reader.setFeature(feature_namespaces, True),
            lambda: reader.getProperty(property_lexical_handler),
            lambda: reader.setProperty(property_lexical_handler, None),
        ):
            with pytest.raises(xml.sax.SAXNotRecognizedException):
                call()

    def test_handler_slots_hold_the_object_given(self) -> None:
        reader = xml.sax.make_parser()
        content, dtd, resolver, errors = (
            ContentHandler(),
            DTDHandler(),
            EntityResolver(),
            ErrorHandler(),
        )

        reader.setContentHandler(content)
        reader.setDTDHandler(dtd)
        reader.setEntityResolver(resolver)
        reader.setErrorHandler(errors)

        assert reader.getContentHandler() is content
        assert reader.getDTDHandler() is dtd
        assert reader.getEntityResolver() is resolver
        assert reader.getErrorHandler() is errors

    def test_the_driver_recognises_a_fixed_set_of_names(self) -> None:
        parser = xml.sax.make_parser()

        assert parser.getFeature(feature_namespaces) == 0
        assert parser.getFeature(feature_external_ges) == 0
        assert parser.getFeature(feature_string_interning) is False
        with pytest.raises(xml.sax.SAXNotRecognizedException):
            parser.getFeature("http://example.invalid/feature")
        with pytest.raises(xml.sax.SAXNotSupportedException):
            parser.setFeature(feature_validation, True)
        with pytest.raises(xml.sax.SAXNotRecognizedException):
            parser.getProperty("http://example.invalid/property")
        with pytest.raises(xml.sax.SAXNotSupportedException):
            parser.setLocale("fi_FI")

    def test_the_features_the_driver_cannot_honour(self) -> None:
        for feature in (
            feature_validation,
            handler.feature_namespace_prefixes,
            handler.feature_external_pes,
        ):
            parser = xml.sax.make_parser()
            with pytest.raises(xml.sax.SAXNotSupportedException):
                parser.setFeature(feature, True)
            assert parser.getFeature(feature) == 0

    def test_the_properties_the_driver_recognises(self) -> None:
        parser = xml.sax.make_parser()
        interning: dict[str, str] = {}
        contexts: list[bytes] = []

        assert parser.getProperty(handler.property_interning_dict) is None
        parser.setProperty(handler.property_interning_dict, interning)
        assert parser.getProperty(handler.property_interning_dict) is interning
        with pytest.raises(xml.sax.SAXNotSupportedException):
            parser.getProperty(handler.property_xml_string)
        with pytest.raises(xml.sax.SAXNotSupportedException):
            parser.setProperty(handler.property_xml_string, b"")

        class Context(ContentHandler):
            def startElement(self, name: str, attrs: Any) -> None:
                context: Any = parser.getProperty(handler.property_xml_string)
                contexts.append(context)

        parser.setContentHandler(Context())
        parser.parse(io.BytesIO(b"<root><item/></root>"))

        assert contexts == [b"<root><item/></root>", b"<item/></root>"]

    def test_the_content_handler_can_be_swapped_during_a_parse(self) -> None:
        parser = xml.sax.make_parser()
        events: list[tuple[str, str]] = []

        class Second(ContentHandler):
            def startElement(self, name: str, attrs: Any) -> None:
                events.append(("second", name))

        class First(ContentHandler):
            def startElement(self, name: str, attrs: Any) -> None:
                events.append(("first", name))
                parser.setContentHandler(Second())

        parser.setContentHandler(First())
        parser.parse(io.BytesIO(b"<root><a/><b/></root>"))

        assert events == [("first", "root"), ("second", "a"), ("second", "b")]

    def test_a_feature_cannot_be_set_during_a_parse(self) -> None:
        parser = xml.sax.make_parser()
        refused: list[Exception] = []

        class Meddling(ContentHandler):
            def startElement(self, name: str, attrs: Any) -> None:
                try:
                    parser.setFeature(feature_namespaces, True)
                except xml.sax.SAXNotSupportedException as error:
                    refused.append(error)

        parser.setContentHandler(Meddling())
        parser.parse(io.BytesIO(b"<root/>"))

        assert len(refused) == 1

    def test_the_feature_and_property_lists(self) -> None:
        assert feature_namespaces in handler.all_features
        assert set(handler.all_features) == {
            handler.feature_namespaces,
            handler.feature_namespace_prefixes,
            handler.feature_string_interning,
            handler.feature_validation,
            handler.feature_external_ges,
            handler.feature_external_pes,
        }
        assert set(handler.all_properties) == {
            handler.property_lexical_handler,
            handler.property_declaration_handler,
            handler.property_dom_node,
            handler.property_xml_string,
            handler.property_encoding,
            handler.property_interning_dict,
        }

    def test_an_input_source_holds_what_it_is_given(self) -> None:
        stream = io.BytesIO(b"<root/>")
        text = io.StringIO("<root/>")
        source = InputSource("doc.xml")

        source.setPublicId("public")
        source.setEncoding("utf-8")
        source.setByteStream(stream)
        source.setCharacterStream(text)

        assert source.getSystemId() == "doc.xml"
        assert source.getPublicId() == "public"
        assert source.getEncoding() == "utf-8"
        assert source.getByteStream() is stream
        assert source.getCharacterStream() is text
        assert InputSource().getSystemId() is None

    def test_prepare_input_source_wraps_without_reading(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "doc.xml"
        path.write_bytes(b"<root/>")

        from_name = saxutils.prepare_input_source(str(path))
        assert from_name.getSystemId() == str(path)
        opened = from_name.getByteStream()
        assert opened is not None
        opened.close()

        stream = CountingSource(b"<root/>")
        from_stream = saxutils.prepare_input_source(stream)
        assert from_stream.getByteStream() is stream
        assert stream.sizes == [0], "only the type probe was read"

        text = io.StringIO("<root/>")
        from_text = saxutils.prepare_input_source(text)
        assert from_text.getCharacterStream() is text
        assert from_text.getByteStream() is None

    def test_a_system_identifier_is_copied_into_the_parser(self) -> None:
        warm()

        def parse(system_id: str) -> None:
            source = InputSource(system_id)
            source.setByteStream(io.BytesIO(b"<r/>"))
            parser = xml.sax.make_parser()
            parser.setContentHandler(ContentHandler())
            parser.parse(source)

        identifier = "file:///tmp/" + "y" * 500_000 + ".xml"

        short_peak = peak_bytes(lambda: parse("file:///tmp/x.xml"))
        long_peak = peak_bytes(lambda: parse(identifier))

        assert long_peak > short_peak + len(identifier) / 2, (
            f"a {len(identifier)}-character system identifier peaked at {long_peak} bytes "
            f"against {short_peak} for a short one; prepareParser() hands it to the parser "
            "as the base for relative references"
        )

    def test_a_locator_reports_where_the_parser_is(self) -> None:
        positions: list[tuple[int, int]] = []

        class Positioned(ContentHandler):
            def setDocumentLocator(self, locator: Any) -> None:
                self._locator = locator

            def startElement(self, name: str, attrs: Any) -> None:
                positions.append((self._locator.getLineNumber(), self._locator.getColumnNumber()))

        xml.sax.parseString(b"<root>\n<item/>\n</root>", Positioned())

        assert [line for line, _ in positions] == [1, 2]
        assert xmlreader.Locator().getLineNumber() == -1
        assert xmlreader.Locator().getColumnNumber() == -1
        assert xmlreader.Locator().getPublicId() is None
        assert xmlreader.Locator().getSystemId() is None


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
        timeout=180,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, so parser
    features and allocation measurements cannot leak between them."""

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
        line, source = next((n, s) for n, s in _blocks() if "counter.elements == 20_001" in s)
        mutated = source.replace("counter.elements == 20_001", "counter.elements == 20_000", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
