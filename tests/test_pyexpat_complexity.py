"""Tests for docs/stdlib/pyexpat.md.

The page prices a parser by the data it is given and the elements it has
open, and every handler event by the arguments it builds. Space is settled by
traced allocation, which sees Expat's own buffers because pyexpat allocates
them through Python's allocator; per-event behaviour is settled by recording
what handlers receive; the few bounds that only a stopwatch separates compare
sizes ten times apart, with thresholds far from both the linear and the
quadratic outcome.

Measurement scope:

* `Parse()` fed 4,096-byte pieces peaks under 100 KB for 20,000 and for
  200,000 flat elements, while one `Parse()` of the 200,000-element document
  peaks above its 800,007 bytes. Fed the same way, 20,000 nested elements
  peak more than 10x above 20,000 flat ones, which is the d term.
  `ParseFile()` over 200,000 elements peaks under 100 KB. A parser given
  `isfinal=True` raises `ExpatError` ("parsing finished") on the next call.
* `StartElementHandler` fires for each element in document order, and one
  `Parse()` of 20,000 empty elements takes more than 5x one of 1,000.
* `StartElementHandler` receives a new dict per element, a flat list with
  `ordered_attributes`, and no DTD default with `specified_attributes`.
  `CharacterDataHandler` receives five pieces for one run split at newlines
  and an entity reference, and one with `buffer_text`; 30,000 characters
  split at newlines arrive with `buffer_text` in a few calls of no more than
  `buffer_size` (8,192 by default), and 30,000 without a newline in one
  call. With no handler assigned, the `intern` dict stays empty. That names
  are interned only while a handler's arguments are built, so an event
  without a handler builds none, is read from Modules/pyexpat.c.
* `intern`: 10,000 elements over three names leave three names in the dict
  and hand identical strings to the handler; `intern=None` hands equal but
  distinct strings; a dict passed in is the one the parser fills.
* Errors: `ExpatError` is `error`, carries the code, the 1-based line and
  the 0-based column, and matches the parser's `Error*` attributes.
  `ErrorString()` agrees with `errors.messages` for every code, and
  `errors.codes` inverts it; the `XML_ERROR_*` names are strings.
* `CurrentLineNumber` read at every event of a one-element-per-line document
  costs less than 30x at 200,000 elements what it costs at 20,000, timed,
  against 100x for a count from the start of the document at every query.
  The three `Current*` values are asserted on a three-line document. The
  text between events is held fixed; a single query after a long run of
  text scans that run, which the amortized bound absorbs.
* `GetInputContext()` returns the rest of the data being parsed: the first
  event of one 200,007-byte `Parse()` copies all of it, and the copies over
  its 50,001 events total more than 1,000 times the document, where the
  same document fed in 4,096-byte pieces keeps every copy within 4,097
  bytes. One 3.2 MB `Parse()` hands its first event exactly 1 MiB. It is
  `None` outside a handler.
* `ExternalEntityParserCreate()` from a handler costs more than 50x as much
  under a DTD of 10,000 entity declarations as under one of 10, timed.
* Reparse deferral: a 500,000-character attribute fed in 1,024-byte pieces
  costs less than 25x what a 50,000-character one does with deferral on and
  more than 40x with it off, timed; skipped where the method is missing or
  the linked Expat predates 2.6.
* The remaining rows are asserted by value: `ParserCreate()` returns an
  `XMLParserType` that cannot be instantiated directly, `SetBase()` and
  `GetBase()` round-trip, `UseForeignDTD()` and `SetParamEntityParsing()`
  succeed before parsing, the protection setters present on this build
  return `None`, `features` is a list of pairs, `EXPAT_VERSION` spells
  `version_info`, and `ElementDeclHandler` receives the `model` constants.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `Parse()`'s amortized O(c) time is measured for element count only;
  documents of long text or many attributes are not varied, and internal
  entity expansion is priced by definition. The billion-laughs and
  allocation-tracker limits are Expat's and vary with the linked version.
* `GetInputContext()` is not measured with a token longer than 1 MiB,
  within one `Parse()` or across several, where the copy exceeds 1 MiB.
* `ParseFile()`'s 2,048-byte reads and `Parse()`'s 1 MiB pieces are read
  from Modules/pyexpat.c on each supported branch; only the latter is
  observed, through `GetInputContext()`.
* Which releases have the `SetBillionLaughsAttackProtection*()` and
  `SetAllocTracker*()` methods depends on the release and the Expat it
  links, which no single interpreter here can settle; the page says to test
  with `hasattr()`. `SetReparseDeferralEnabled()`'s boundaries (3.13, 3.12.3,
  3.11.9, 3.10.14) are read from the release tags.
* The handler rows other than `StartElementHandler` and
  `CharacterDataHandler` are priced by the arguments each event converts,
  read from Modules/pyexpat.c; only `ElementDeclHandler` is exercised.
* The page-scoped audit lists the `xml.parsers.expat.xmlparser.*` members
  as unresolved because the runtime type is named `pyexpat.xmlparser` and is
  reached as `XMLParserType`; the page documents them under `### xmlparser`.
  `pyexpat.expat_CAPI`, which the audit asks to classify, is a capsule for C
  extensions such as `_elementtree` and is not documented API.
"""

from __future__ import annotations

import io
import pathlib
import pyexpat
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import xml.parsers.expat
from collections.abc import Callable
from typing import Any
from xml.parsers.expat import errors, model

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pyexpat.md"
EXPECTED_BLOCKS = 8


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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def flat(count: int) -> bytes:
    return ("<r>" + "<a/>" * count + "</r>").encode()


def nested(count: int) -> bytes:
    return ("<a>" * count + "</a>" * count).encode()


def feed(document: bytes, piece: int = 4096) -> None:
    parser = pyexpat.ParserCreate()
    parser.StartElementHandler = lambda name, attrs: None
    for offset in range(0, len(document), piece):
        parser.Parse(document[offset : offset + piece], False)
    parser.Parse(b"", True)


def parse_whole(document: bytes) -> None:
    parser = pyexpat.ParserCreate()
    parser.StartElementHandler = lambda name, attrs: None
    parser.Parse(document, True)


class TestParseHoldsThePieceAndTheOpenElements:
    """`Parse(data, isfinal)` | O(c) | O(c + d); `ParseFile(file)` | O(n) | O(d)."""

    def test_feeding_pieces_holds_a_piece_not_the_document(self) -> None:
        small, large = flat(20_000), flat(200_000)
        feed(small)

        assert peak_bytes(lambda: feed(small)) < 100_000
        assert peak_bytes(lambda: feed(large)) < 100_000

    def test_one_parse_holds_its_data(self) -> None:
        document = flat(200_000)
        parse_whole(flat(10))

        assert peak_bytes(lambda: parse_whole(document)) > len(document)

    def test_open_elements_are_held(self) -> None:
        feed(flat(10))
        shallow = peak_bytes(lambda: feed(flat(20_000)))
        deep = peak_bytes(lambda: feed(nested(20_000)))

        assert deep > 10 * shallow, f"flat {shallow} B, nested {deep} B"

    def test_parse_file_reads_in_pieces(self) -> None:
        document = flat(200_000)

        def run() -> None:
            parser = pyexpat.ParserCreate()
            parser.StartElementHandler = lambda name, attrs: None
            parser.ParseFile(io.BytesIO(document))

        run()
        assert peak_bytes(run) < 100_000

    def test_a_finished_parser_raises(self) -> None:
        parser = pyexpat.ParserCreate()
        parser.Parse("<r/>", True)

        with pytest.raises(pyexpat.ExpatError) as caught:
            parser.Parse("<r/>", True)
        assert errors.messages[caught.value.code] == "parsing finished"


class TestHandlersFireInDocumentOrder:
    """A handler is called once per element in document order, and one
    `Parse()` takes time that grows with the element count."""

    def test_handlers_fire_in_document_order(self) -> None:
        seen: list[str] = []
        parser = pyexpat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: seen.append(name)
        parser.Parse("<root><a/><b/></root>", True)

        assert seen == ["root", "a", "b"]

    @pytest.mark.timing
    def test_parsing_scales_with_the_input(self) -> None:
        def parse(count: int) -> None:
            parser = pyexpat.ParserCreate()
            parser.StartElementHandler = lambda name, attrs: None
            parser.Parse("<root>" + "<i/>" * count + "</root>", True)

        small = best_ns(lambda: parse(1_000))
        large = best_ns(lambda: parse(20_000))

        assert large > small * 5, f"O(n) in input size: {small:.0f}ns vs {large:.0f}ns"


class TestHandlerArguments:
    """`StartElementHandler` | O(a) per element; `CharacterDataHandler` in
    pieces unless `buffer_text`; an event with no handler costs no Python
    call."""

    def test_each_element_gets_a_new_attribute_dict(self) -> None:
        received: list[Any] = []
        parser = pyexpat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: received.append(attrs)
        parser.Parse("<r><a x='1'/><a x='1'/></r>", True)

        assert received[1] == received[2] == {"x": "1"}
        assert received[1] is not received[2]

    def test_ordered_attributes_give_a_flat_list(self) -> None:
        received: list[Any] = []
        parser = pyexpat.ParserCreate()
        parser.ordered_attributes = True
        parser.StartElementHandler = lambda name, attrs: received.append(attrs)
        parser.Parse("<r b='1' a='2'/>", True)

        assert received == [["b", "1", "a", "2"]]

    def test_specified_attributes_drop_dtd_defaults(self) -> None:
        document = "<!DOCTYPE r [<!ATTLIST a x CDATA 'd'>]><r><a/></r>"

        def attributes(specified: bool) -> list[Any]:
            received: list[Any] = []
            parser = pyexpat.ParserCreate()
            parser.specified_attributes = specified
            parser.StartElementHandler = lambda name, attrs: received.append(attrs)
            parser.Parse(document, True)
            return received

        assert attributes(False) == [{}, {"x": "d"}]
        assert attributes(True) == [{}, {}]

    def test_character_data_arrives_in_pieces_unless_buffered(self) -> None:
        def pieces(buffer_text: bool) -> list[str]:
            received: list[str] = []
            parser = pyexpat.ParserCreate()
            parser.buffer_text = buffer_text
            parser.CharacterDataHandler = received.append
            parser.Parse("<r>one\ntwo &amp; three</r>", True)
            return received

        assert pieces(False) == ["one", "\n", "two ", "&", " three"]
        assert pieces(True) == ["one\ntwo & three"]

    @staticmethod
    def buffered(text: str) -> list[str]:
        received: list[str] = []
        parser = pyexpat.ParserCreate()
        assert parser.buffer_size == 8192 and parser.buffer_used == 0
        parser.buffer_text = True
        parser.CharacterDataHandler = received.append
        parser.Parse("<r>" + text + "</r>", True)
        return received

    def test_buffered_pieces_are_joined_while_they_fit(self) -> None:
        received = self.buffered("ab\n" * 10_000)

        assert "".join(received) == "ab\n" * 10_000
        assert 1 < len(received) < 10
        assert max(map(len, received)) <= 8192

    def test_a_piece_longer_than_the_buffer_arrives_alone(self) -> None:
        assert self.buffered("x" * 30_000) == ["x" * 30_000]

    def test_no_names_are_interned_without_a_handler(self) -> None:
        parser = pyexpat.ParserCreate()
        parser.Parse("<r><item/><item/></r>", True)

        assert parser.intern == {}


class TestInterning:
    """`xmlparser.intern` | O(1) | O(q): one string per distinct name."""

    def test_repeated_names_are_one_string(self) -> None:
        names: list[str] = []
        parser = pyexpat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: names.append(name)
        parser.Parse("<root>" + "<item/><entry/>" * 5_000 + "</root>", True)

        assert len(names) == 10_001
        assert len({id(name) for name in names}) == 3
        assert parser.intern == {"root": "root", "item": "item", "entry": "entry"}

    def test_intern_none_turns_interning_off(self) -> None:
        names: list[str] = []
        parser = pyexpat.ParserCreate(intern=None)
        parser.StartElementHandler = lambda name, attrs: names.append(name)
        parser.Parse("<root><item/><item/></root>", True)

        assert parser.intern is None
        assert names[1] == names[2] and names[1] is not names[2]

    def test_a_dict_passed_in_is_the_one_filled(self) -> None:
        shared: dict[str, str] = {}
        parser = pyexpat.ParserCreate(intern=shared)
        parser.StartElementHandler = lambda name, attrs: None
        parser.Parse("<root/>", True)

        assert parser.intern is shared and shared == {"root": "root"}


class TestErrors:
    """`ExpatError` and its attributes, `ErrorString()`, `errors.codes`,
    `errors.messages`, and the parser's `Error*` attributes."""

    def test_the_exception_carries_code_line_and_column(self) -> None:
        parser = pyexpat.ParserCreate()
        with pytest.raises(pyexpat.ExpatError) as caught:
            parser.Parse("<r>\n  <a></b></r>", True)
        error = caught.value

        assert pyexpat.error is pyexpat.ExpatError is xml.parsers.expat.ExpatError
        assert (error.code, error.lineno, error.offset) == (
            parser.ErrorCode,
            parser.ErrorLineNumber,
            parser.ErrorColumnNumber,
        )
        assert (error.lineno, error.offset) == (2, 7)
        assert parser.ErrorByteIndex == 11
        assert errors.messages[error.code] == errors.XML_ERROR_TAG_MISMATCH

    def test_error_string_is_the_messages_table(self) -> None:
        assert errors.messages
        for code, message in errors.messages.items():
            assert pyexpat.ErrorString(code) == message
            assert errors.codes[message] == code
        assert len(errors.codes) == len(errors.messages)

    def test_the_constants_are_messages(self) -> None:
        names = [name for name in dir(errors) if name.startswith("XML_ERROR_")]

        assert names
        assert all(isinstance(getattr(errors, name), str) for name in names)
        assert xml.parsers.expat.errors is pyexpat.errors
        assert xml.parsers.expat.model is pyexpat.model


class TestPositions:
    """`CurrentLineNumber`, `CurrentColumnNumber` | O(1) amortized;
    `CurrentByteIndex` | O(1)."""

    def test_positions_of_each_event(self) -> None:
        positions: list[tuple[int, int, int]] = []
        parser = pyexpat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: positions.append(
            (parser.CurrentLineNumber, parser.CurrentColumnNumber, parser.CurrentByteIndex)
        )
        parser.Parse("<r>\n <a/>\n<b/></r>", True)

        assert positions == [(1, 0, 0), (2, 1, 5), (3, 0, 10)]

    @pytest.mark.timing
    def test_querying_at_every_event_stays_linear(self) -> None:
        def run(count: int) -> float:
            document = "<r>\n" + "<a/>\n" * count + "</r>"

            def parse() -> None:
                parser = pyexpat.ParserCreate()
                parser.StartElementHandler = lambda name, attrs: parser.CurrentLineNumber
                parser.Parse(document, True)

            return best_ns(parse)

        run(1_000)
        small, large = run(20_000), run(200_000)

        assert large < 30 * small, f"20,000: {small:.0f} ns, 200,000: {large:.0f} ns"


class TestInputContextCopiesTheRest:
    """`GetInputContext()` | O(c): a copy from the current event to the end of
    the data being parsed, up to the 1 MiB piece `Parse()` hands Expat."""

    @staticmethod
    def copies(document: bytes, piece: int | None) -> list[int]:
        lengths: list[int] = []
        parser = pyexpat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: lengths.append(
            len(parser.GetInputContext() or b"")
        )
        if piece is None:
            parser.Parse(document, True)
        else:
            for offset in range(0, len(document), piece):
                parser.Parse(document[offset : offset + piece], False)
            parser.Parse(b"", True)
        return lengths

    def test_one_large_parse_copies_the_rest_at_every_event(self) -> None:
        document = flat(50_000)
        lengths = self.copies(document, None)

        assert lengths[0] == len(document)
        assert sum(lengths) > 1_000 * len(document)

    def test_pieces_bound_every_copy(self) -> None:
        lengths = self.copies(flat(50_000), 4096)

        assert len(lengths) == 50_001
        assert max(lengths) <= 4097

    def test_a_copy_is_at_most_the_one_mib_piece(self) -> None:
        document = flat(800_000)
        first: list[int] = []
        parser = pyexpat.ParserCreate()

        def start(name: str, attrs: dict[str, str]) -> None:
            if not first:
                first.append(len(parser.GetInputContext() or b""))

        parser.StartElementHandler = start
        parser.Parse(document, True)

        assert len(document) > 3 * (1 << 20)
        assert first == [1 << 20]

    def test_outside_a_handler_it_is_none(self) -> None:
        parser = pyexpat.ParserCreate()
        parser.Parse("<r/>", True)

        assert parser.GetInputContext() is None


class TestExternalEntityParserCopiesTheDTD:
    """`ExternalEntityParserCreate(context[, encoding])` | O(m + c)."""

    @staticmethod
    def creation_ns(declarations: int) -> float:
        entities = "".join(f"<!ENTITY e{i} 'v'>" for i in range(declarations))
        document = f"<!DOCTYPE r [{entities}<!ENTITY ext SYSTEM 'x.xml'>]><r>&ext;</r>"
        times: list[float] = []
        parser = pyexpat.ParserCreate()
        parser.SetParamEntityParsing(pyexpat.XML_PARAM_ENTITY_PARSING_UNLESS_STANDALONE)

        def handler(context: str, base: str | None, system: str | None, public: str | None) -> int:
            for _ in range(5):
                start = time.perf_counter_ns()
                child = parser.ExternalEntityParserCreate(context)
                times.append(float(time.perf_counter_ns() - start))
                del child
            return 1

        parser.ExternalEntityRefHandler = handler
        parser.Parse(document, True)
        assert len(times) == 5
        return min(times)

    def test_the_child_parser_parses_the_entity(self) -> None:
        seen: list[str] = []
        parser = pyexpat.ParserCreate()
        parser.SetParamEntityParsing(pyexpat.XML_PARAM_ENTITY_PARSING_UNLESS_STANDALONE)

        def handler(context: str, base: str | None, system: str | None, public: str | None) -> int:
            child = parser.ExternalEntityParserCreate(context)
            child.StartElementHandler = lambda name, attrs: seen.append(name)
            child.Parse("<included/>", True)
            return 1

        parser.ExternalEntityRefHandler = handler
        parser.Parse("<!DOCTYPE r [<!ENTITY ext SYSTEM 'x.xml'>]><r>&ext;</r>", True)

        assert seen == ["included"]

    @pytest.mark.timing
    def test_creation_grows_with_the_declarations(self) -> None:
        self.creation_ns(10)
        few, many = self.creation_ns(10), self.creation_ns(10_000)

        assert many > 50 * few, f"10 declarations: {few:.0f} ns, 10,000: {many:.0f} ns"


@pytest.mark.skipif(
    not hasattr(pyexpat.ParserCreate(), "SetReparseDeferralEnabled")
    or pyexpat.version_info < (2, 6, 0),
    reason="reparse deferral needs the method and Expat 2.6+",
)
class TestReparseDeferral:
    """`SetReparseDeferralEnabled()`: on, a token split across many `Parse()`
    calls stays linear; off, it is rescanned on every call."""

    @staticmethod
    def split_token_ns(size: int, deferral: bool) -> float:
        document = b"<r a='" + b"x" * size + b"'/>"

        def parse() -> None:
            parser = pyexpat.ParserCreate()
            parser.SetReparseDeferralEnabled(deferral)
            for offset in range(0, len(document), 1024):
                parser.Parse(document[offset : offset + 1024], False)
            parser.Parse(b"", True)

        return best_ns(parse, repeats=3)

    def test_deferral_is_on_by_default(self) -> None:
        parser = pyexpat.ParserCreate()

        assert parser.GetReparseDeferralEnabled() is True
        parser.SetReparseDeferralEnabled(False)
        assert parser.GetReparseDeferralEnabled() is False

    @pytest.mark.timing
    def test_deferral_keeps_a_split_token_linear(self) -> None:
        small, large = self.split_token_ns(50_000, True), self.split_token_ns(500_000, True)

        assert large < 25 * small, f"50,000: {small:.0f} ns, 500,000: {large:.0f} ns"

    @pytest.mark.timing
    def test_without_deferral_a_split_token_is_rescanned(self) -> None:
        small, large = self.split_token_ns(50_000, False), self.split_token_ns(500_000, False)

        assert large > 40 * small, f"50,000: {small:.0f} ns, 500,000: {large:.0f} ns"


class TestModuleObjects:
    """`ParserCreate`, `XMLParserType`, `features`, the version constants,
    `SetBase`/`GetBase`, the setup methods, the protection setters and the
    `model` constants."""

    def test_parsers_are_xml_parser_type(self) -> None:
        assert isinstance(pyexpat.ParserCreate(), pyexpat.XMLParserType)
        with pytest.raises(TypeError):
            pyexpat.XMLParserType()

    def test_features_and_version(self) -> None:
        assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in pyexpat.features)
        assert dict(pyexpat.features)["sizeof(XML_Char)"] == 1
        assert pyexpat.EXPAT_VERSION == "expat_{}.{}.{}".format(*pyexpat.version_info)
        assert pyexpat.native_encoding == "UTF-8"

    def test_base_round_trips(self) -> None:
        parser = pyexpat.ParserCreate()
        assert parser.GetBase() is None
        parser.SetBase("docs/main.xml")
        assert parser.GetBase() == "docs/main.xml"

    def test_setup_methods_run_before_parsing(self) -> None:
        parser = pyexpat.ParserCreate()
        assert parser.SetParamEntityParsing(pyexpat.XML_PARAM_ENTITY_PARSING_NEVER) == 1
        assert parser.UseForeignDTD() is None
        parser.Parse("<r/>", True)

        assert {
            pyexpat.XML_PARAM_ENTITY_PARSING_NEVER,
            pyexpat.XML_PARAM_ENTITY_PARSING_UNLESS_STANDALONE,
            pyexpat.XML_PARAM_ENTITY_PARSING_ALWAYS,
        } == {0, 1, 2}

    def test_protection_setters_present_here_return_none(self) -> None:
        parser = pyexpat.ParserCreate()
        calls = {
            "SetBillionLaughsAttackProtectionActivationThreshold": 8 * 1024 * 1024,
            "SetBillionLaughsAttackProtectionMaximumAmplification": 100.0,
            "SetAllocTrackerActivationThreshold": 64 * 1024 * 1024,
            "SetAllocTrackerMaximumAmplification": 100.0,
        }
        for name, value in calls.items():
            if hasattr(parser, name):
                assert getattr(parser, name)(value) is None
        parser.Parse("<r/>", True)

    def test_content_models_use_the_model_constants(self) -> None:
        declarations: dict[str, Any] = {}
        parser = pyexpat.ParserCreate()
        parser.ElementDeclHandler = lambda name, content: declarations.update({name: content})
        parser.Parse("<!DOCTYPE r [<!ELEMENT r (a+)><!ELEMENT a (#PCDATA)>]><r/>", True)

        assert declarations["r"] == (
            model.XML_CTYPE_SEQ,
            model.XML_CQUANT_NONE,
            None,
            ((model.XML_CTYPE_NAME, model.XML_CQUANT_PLUS, "a", ()),),
        )
        assert declarations["a"][0] == model.XML_CTYPE_MIXED


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "copied[0] == len(document)" in s)
        mutated = source.replace("copied[0] == len(document)", "copied[0] == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
