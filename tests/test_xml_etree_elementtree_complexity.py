"""Tests for docs/stdlib/xml.etree.elementtree.md.

The page prices parsing by the document and a parsed tree by its elements,
searches by the path they are given, and serialization by the output. Where
the work is a comparison of tags, it is counted: elements are given `str`
tags whose `__eq__` records each call, so a scan of k children and a walk of
e elements are told apart exactly. Space is settled by traced allocation,
identity and tree size; the few bounds that only a stopwatch separates
compare sizes far apart.

Measurement scope:

* Parsing: `fromstring()`'s traced peak grows more than 5x from 2,000 to
  20,000 elements, and `XML` is the same function. `parse()` reads a path and
  a binary stream to equal trees, `fromstringlist()` splits a document into
  one-character fragments, and `XMLID()` maps every `id`. `ParseError` is a
  `SyntaxError` carrying Expat's code and `(line, column)`.
* `iterparse()` reads nothing from a 400 KB stream when it is created and
  16,384 bytes by its first event. After 20,000 records, clearing each at its
  end event leaves 20,000 children on the root; removing each leaves none,
  and under 1,000 records - about one 16 KiB read - are attached at once.
  `root` is set on exhaustion, and `close()` is asserted on 3.13+.
* `XMLPullParser` queues 1,000 events until `read_events()` takes them, and
  empties the queue as it does; a parse error surfaces from `read_events()`,
  not `feed()`. `flush()` and `close()` are exercised on a split document.
  `XMLParser.entity` fills an undeclared entity in a document with a DOCTYPE
  and does not rescue one without; a custom target is observed to receive
  `doctype()`, `start_ns()` and `end_ns()`, which `TreeBuilder` lacks.
* `TreeBuilder.data()`: 100,000 one-character pieces give one joined `text`;
  the first read of it allocates the joined string and the second returns
  the same object with a traced peak under 1 KB. A timing test bounds
  100,000 pieces under 30x the cost of 10,000, against 100x for a join per
  piece.
* Element children, timed with the same child object appended repeatedly so
  the tree stays small: `insert(0)` (paired with an O(1) `del elem[-1]`) and
  `remove()` cost more than 20x at 200,000 children than at 1,000, `append()` with `del elem[-1]` less than
  3x. `remove()` removes the identical element among equal-looking ones.
* `Element()` copies `attrib`, `attrib` is the element's own dict, and
  `keys()`/`items()` build a new list per call. `copy.copy()` shares the
  children and the attribute dict; `copy.deepcopy()` shares only the strings.
  `clear()` leaves the element in its parent.
* `iter()` allocates under 1 KB to create over a 100,000-element tree; walking
  an 800-deep chain peaks more than 10x as high as walking 800 siblings.
  `itertext()` yields text and tail in document order and skips empties.
* Paths, counted: a bare tag compares each child once (k = 1,000) and never a
  grandchild, and `find()` stops at the first child; `.//tag` compares all
  1,000 descendants and `find('.//tag')` one. `..` builds a traced peak of
  more than 1 MB over 100,000 elements where the child step allocates
  nothing. `[1]` over k siblings of one parent compares tags under 10,000
  times at k = 1,000 on versions with the per-parent scan, and over 100,000
  times - k² - on those without; the boundary is asserted per patch release.
  `*[1]` over 1,000 differently tagged siblings compares over 100,000 times
  on every version: one scan per distinct tag.
  `ElementTree.find('/x')` warns with `FutureWarning`.
* Serialization: `tostring()` peaks above the 3.4 MB it returns for 100,000
  elements while `write()` to a discarding sink peaks under 100 KB. `write()`
  over 50,000 distinct tag names peaks more than 100x above 50,000 of one
  name, which is the q term, and one text run of 1,000,000 escapable
  characters peaks above 1 MB, which is the c term. A chain 100 deeper than the recursion limit
  parses and walks, and `tostring()` and `indent()` raise `RecursionError`
  on it. `write_c14n()` raises `ValueError`. `indent()` gives siblings one
  shared tail string, and indenting a 400-deep chain peaks more than 20x
  above 400 siblings, which is the d² space. `tostringlist()` over 10,000
  elements returns every written piece for `encoding="unicode"` and a few
  byte chunks otherwise, each joining to `tostring()`'s output.
* `register_namespace()`: 20,000 registered prefixes cost more than 20x what
  20 do, timed; the registry is restored afterwards. `ns0` raises.
* `canonicalize()` on 4,000 elements costs more than 10x as much nested
  4,000 deep as it does flat, timed; with `out`, a 100,000-element flat
  document peaks under 1 MB while returning a string peaks above its length.
  Attribute order and the output of the page's example are asserted.
* Every fenced Python block runs in its own subprocess, so the global
  namespace registry cannot leak between them, and a mutated assertion in
  one of them is asserted to fail.

Not settled here:

* The O(n) parse bounds are Expat's single pass; the tests measure growth in
  element count, not a document of long text or many attributes. Treating n
  as the text after internal entity expansion is a definition, and Expat's
  own amplification limits, which vary with the linked Expat version, are
  not exercised.
* The 64 KiB `parse()` read size and `flush()`'s cost in held-back bytes are
  read from Lib/xml/etree/ElementTree.py and Modules/_elementtree.c; Expat's
  reparse deferral decides what is held back, and which Expat is linked
  varies by build. `feed()`'s O(c) assumes an Expat with reparse deferral
  (2.6+): without it, one large token fed in many small pieces is reparsed
  on every piece.
* Freeing what `clear()`, `remove()` or `del` drop is the reverse of building
  it and is not priced.
* `copy.copy()`'s O(k), `clear()`, `makeelement()`, `extend()`, `keys()`/`items()`,
  `C14NWriterTarget`'s per-event bounds and the `[tag]`, `[@attrib]` and
  text predicates are read from the released sources; the tests assert their
  results, not their growth. The a log a sort term and the s term, namespace
  declarations in scope, in `canonicalize()` are not varied.
* Only the C accelerator is measured; the pure-Python `Element` is not.
* The page-scoped audit reports `TreeBuilder.doctype`, `start_ns` and
  `end_ns` as unresolved because the built-in `TreeBuilder` does not have
  them; the page documents them as hooks of a custom target, which
  `TestXMLParserAndTargets` exercises. `xml.etree.ElementInclude` belongs to
  the xml package page.
"""

from __future__ import annotations

import copy
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "xml.etree.elementtree.md"
EXPECTED_BLOCKS = 12

# The first patch of each minor release that scans a parent's children once per
# tag for a positional predicate, instead of once per candidate.
POSITIONAL_SCAN_FIXED = {(3, 10): 21, (3, 11): 16, (3, 12): 14, (3, 13): 15, (3, 14): 7}


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
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


class CountingTag(str):
    """A tag that counts every equality comparison made against it."""

    comparisons = 0

    def __eq__(self, other: object) -> bool:
        CountingTag.comparisons += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


def counted(func: Callable[[], Any]) -> int:
    """Tag comparisons made while func runs."""
    CountingTag.comparisons = 0
    func()
    return CountingTag.comparisons


def flat_tree(children: int, tag: str = "item") -> ET.Element:
    """A root with `children` children, each with its own counting tag object."""
    root = ET.Element("root")
    for _ in range(children):
        ET.SubElement(root, CountingTag(tag))
    return root


def pulled(parser: ET.XMLPullParser) -> list[tuple[str, Any]]:
    """The events `read_events()` yields, as `(event, element)` pairs."""
    return list(parser.read_events())  # type: ignore[arg-type]


def records(count: int) -> str:
    return "<log>" + "<entry><level>INFO</level></entry>" * count + "</log>"


class DiscardingSink:
    """A text sink that keeps nothing it is given."""

    def write(self, text: str) -> int:
        return len(text)


class TestParsingBuildsTheWholeTree:
    """`fromstring`, `XML`, `fromstringlist`, `parse` and `XMLID` | O(n) | O(n)."""

    DOCUMENT = "<catalog><book id='1'>A</book><book id='2'>B</book></catalog>"

    def test_xml_and_fromstring_are_one_function(self) -> None:
        assert ET.XML is ET.fromstring

    def test_the_tree_grows_with_the_document(self) -> None:
        small = records(2_000)
        large = records(20_000)
        ET.fromstring(small)

        peaks = [peak_bytes(lambda: ET.fromstring(small)), peak_bytes(lambda: ET.fromstring(large))]

        assert peaks[1] > peaks[0] * 5, f"10x the records peaked at {peaks}"

    def test_parse_reads_a_path_or_a_stream(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.xml"
        path.write_text(self.DOCUMENT)

        from_path = ET.parse(path)
        from_stream = ET.parse(io.BytesIO(self.DOCUMENT.encode()))

        assert isinstance(from_path, ET.ElementTree)
        assert ET.tostring(from_path.getroot()) == ET.tostring(from_stream.getroot())

    def test_fromstringlist_feeds_every_fragment(self) -> None:
        root = ET.fromstringlist(list(self.DOCUMENT))

        assert ET.tostring(root) == ET.tostring(ET.fromstring(self.DOCUMENT))

    def test_xmlid_maps_every_id(self) -> None:
        root, ids = ET.XMLID(self.DOCUMENT)

        assert set(ids) == {"1", "2"}
        assert ids["2"] is root[1]

    def test_a_parse_error_carries_code_and_position(self) -> None:
        with pytest.raises(ET.ParseError) as caught:
            ET.fromstring("<catalog><book></catalog>")

        assert isinstance(caught.value, SyntaxError)
        assert caught.value.position == (1, 17)
        assert caught.value.code == 7  # XML_ERROR_TAG_MISMATCH


class TestIterparseIsLazyButKeepsTheTree:
    """`iterparse` | O(1) to create, O(n) to exhaust | O(n) unless finished
    elements are removed; `clear()` leaves each element in its parent."""

    def test_creating_it_reads_nothing(self) -> None:
        source = io.BytesIO(b"<r>" + b"<a/>" * 100_000 + b"</r>")

        events = ET.iterparse(source)

        assert source.tell() == 0
        next(events)
        assert source.tell() == 16 * 1024, "the first event needs one 16 KiB read"

    def test_clearing_leaves_one_element_per_record(self) -> None:
        root = None
        for event, elem in ET.iterparse(io.StringIO(records(20_000)), events=("start", "end")):
            if root is None:
                root = elem
            elif event == "end" and elem.tag == "entry":
                elem.clear()

        assert root is not None
        assert len(root) == 20_000
        assert all(len(entry) == 0 for entry in root)

    def test_removing_each_record_holds_one_read_of_records(self) -> None:
        root = None
        seen = 0
        most = 0
        for event, elem in ET.iterparse(io.StringIO(records(20_000)), events=("start", "end")):
            if root is None:
                root = elem
            elif event == "end" and elem.tag == "entry":
                seen += elem.findtext("level") == "INFO"
                most = max(most, len(root))
                root.remove(elem)

        assert root is not None
        assert len(root) == 0
        assert seen == 20_000
        # A 16 KiB read brings about 16,384 / 34 = 482 records.
        assert 1 < most < 1_000, f"{most} records were attached at once"

    def test_root_is_set_once_exhausted(self) -> None:
        events = ET.iterparse(io.StringIO("<r><a/></r>"))

        assert events.root is None  # type: ignore[attr-defined]
        tags = [elem.tag for _, elem in events]

        assert tags == ["a", "r"]
        assert events.root.tag == "r"  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="close() added in 3.13")
    def test_close_closes_a_file_it_opened(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "data.xml"
        path.write_text("<r><a/><a/></r>")
        opened: list[Any] = []

        def recording_open(*args: Any, **kwargs: Any) -> Any:
            opened.append(open(*args, **kwargs))  # noqa: SIM115
            return opened[-1]

        monkeypatch.setattr(ET, "open", recording_open, raising=False)
        events = ET.iterparse(path)
        next(events)
        assert len(opened) == 1 and not opened[0].closed
        events.close()  # type: ignore[attr-defined]

        assert opened[0].closed
        with pytest.raises(StopIteration):
            next(events)


class TestPullParserQueuesEvents:
    """`XMLPullParser.feed` queues; `read_events` removes; errors surface from
    `read_events`; `close` returns nothing."""

    def test_events_wait_until_they_are_read(self) -> None:
        parser = ET.XMLPullParser(events=("end",))
        parser.feed("<r>" + "<a/>" * 1_000)
        parser.flush()

        first = list(parser.read_events())
        second = list(parser.read_events())

        assert len(first) == 1_000
        assert second == []

    def test_a_split_document_completes_on_close(self) -> None:
        parser = ET.XMLPullParser(events=("start", "end"))
        parser.feed("<feed><item>1</item><it")
        parser.flush()
        before = [(event, elem.tag) for event, elem in pulled(parser)]

        parser.feed("em>2</item></feed>")
        closed = parser.close()  # type: ignore[func-returns-value]
        after = [(event, elem.tag) for event, elem in pulled(parser)]

        assert before == [("start", "feed"), ("start", "item"), ("end", "item")]
        assert after == [("start", "item"), ("end", "item"), ("end", "feed")]
        assert closed is None

    def test_a_parse_error_is_raised_by_read_events(self) -> None:
        parser = ET.XMLPullParser()
        parser.feed("<r><a></r>")  # does not raise

        with pytest.raises(ET.ParseError):
            list(parser.read_events())

    def test_default_events_are_end_events(self) -> None:
        parser = ET.XMLPullParser()
        parser.feed("<r><a/></r>")
        parser.close()

        assert [event for event, _ in pulled(parser)] == ["end", "end"]


class TestXMLParserAndTargets:
    """`XMLParser` drives a target; `entity`, `target` and `version` are plain
    attributes; optional target hooks are called only when defined."""

    def test_close_returns_the_tree_builder_root(self) -> None:
        parser = ET.XMLParser()
        parser.feed("<r><a/></r>")

        root = parser.close()

        assert root.tag == "r" and len(root) == 1
        assert isinstance(parser.target, ET.TreeBuilder)
        assert parser.version.startswith("Expat ")

    def test_entity_fills_an_undeclared_entity_under_a_doctype(self) -> None:
        parser = ET.XMLParser()
        parser.entity["name"] = "value"

        parser.feed('<!DOCTYPE r SYSTEM "r.dtd"><r>&name;</r>')

        assert parser.close().text == "value"

    def test_entity_does_not_apply_without_a_doctype(self) -> None:
        parser = ET.XMLParser()
        parser.entity["name"] = "value"

        with pytest.raises(ET.ParseError, match="undefined entity"):
            parser.feed("<r>&name;</r>")
            parser.close()

    def test_optional_hooks_reach_a_target_that_defines_them(self) -> None:
        class Target:
            def __init__(self) -> None:
                self.calls: list[tuple[str, ...]] = []

            def start(self, tag: str, attrs: dict[str, str]) -> None:
                self.calls.append(("start", tag))

            def end(self, tag: str) -> None:
                self.calls.append(("end", tag))

            def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
                self.calls.append(("doctype", name, str(pubid), str(system)))

            def start_ns(self, prefix: str, uri: str) -> None:
                self.calls.append(("start_ns", prefix, uri))

            def end_ns(self, prefix: str) -> None:
                self.calls.append(("end_ns", prefix))

            def close(self) -> list[tuple[str, ...]]:
                return self.calls

        parser = ET.XMLParser(target=Target())
        parser.feed('<!DOCTYPE r SYSTEM "r.dtd"><r xmlns:p="urn:p"/>')

        assert parser.close() == [
            ("doctype", "r", "None", "r.dtd"),
            ("start_ns", "p", "urn:p"),
            ("start", "r"),
            ("end", "r"),
            ("end_ns", "p"),
        ]

    def test_the_built_in_tree_builder_has_no_optional_hooks(self) -> None:
        builder = ET.TreeBuilder()

        assert not any(hasattr(builder, name) for name in ("doctype", "start_ns", "end_ns"))


class TestTreeBuilderJoinsTextOnce:
    """`TreeBuilder.data` | O(1) amortized: pieces are joined once, on the
    first read of `text`."""

    @staticmethod
    def built(pieces: int) -> ET.Element:
        builder = ET.TreeBuilder()
        builder.start("r", {})
        for _ in range(pieces):
            builder.data("x")
        builder.end("r")
        return builder.close()

    def test_many_pieces_become_one_text(self) -> None:
        root = self.built(100_000)

        assert root.text == "x" * 100_000

    def test_the_join_happens_on_the_first_read_only(self) -> None:
        root = self.built(100_000)
        first: list[Any] = []

        first_peak = peak_bytes(lambda: first.append(root.text))
        second_peak = peak_bytes(lambda: root.text)

        assert first_peak > 100_000, f"the first read allocated {first_peak} bytes"
        assert second_peak < 1_000, f"the second read allocated {second_peak} bytes"
        assert root.text is first[0]

    def test_comments_and_pis_join_the_tree_only_when_asked(self) -> None:
        document = "<r><!--note--><?go now?></r>"
        plain = ET.fromstring(document)
        builder = ET.TreeBuilder(insert_comments=True, insert_pis=True)
        parser = ET.XMLParser(target=builder)
        parser.feed(document)
        kept = parser.close()

        assert len(plain) == 0
        assert [child.tag for child in kept] == [ET.Comment, ET.PI]
        assert kept[0].text == "note" and kept[1].text == "go now"

    @pytest.mark.timing
    def test_ten_times_the_pieces_cost_about_ten_times_as_much(self) -> None:
        small = best_ns(lambda: self.built(10_000).text, repeats=5)
        large = best_ns(lambda: self.built(100_000).text, repeats=5)

        ratio = large / small
        assert ratio < 30, f"10x the pieces cost x{ratio:.1f}; a join per piece gives x100"


class TestChildrenAreAnArray:
    """`append` | O(1) amortized; `insert` and `remove` | O(k); `remove`
    finds its argument by identity."""

    @staticmethod
    def parent_of(children: int) -> tuple[ET.Element, ET.Element]:
        filler = ET.Element("filler")
        root = ET.Element("root")
        root.extend([filler] * children)
        return root, ET.Element("moving")

    @pytest.mark.timing
    def test_inserting_at_the_front_grows_with_the_children(self) -> None:
        def cost(children: int) -> float:
            root, moving = self.parent_of(children)

            def step() -> None:
                root.insert(0, moving)
                del root[-1]  # O(1): the array keeps its length

            return best_ns(step, inner=20)

        ratio = cost(200_000) / cost(1_000)
        assert ratio > 20, f"200x the children made insert(0) x{ratio:.1f}"

    @pytest.mark.timing
    def test_removing_grows_with_the_children(self) -> None:
        def cost(children: int) -> float:
            root, moving = self.parent_of(children)

            def step() -> None:
                root.append(moving)
                root.remove(moving)

            return best_ns(step, inner=20)

        ratio = cost(200_000) / cost(1_000)
        assert ratio > 20, f"200x the children made remove() x{ratio:.1f}"

    @pytest.mark.timing
    def test_appending_does_not(self) -> None:
        def cost(children: int) -> float:
            root, moving = self.parent_of(children)

            def step() -> None:
                root.append(moving)
                del root[-1]

            return best_ns(step, inner=200)

        ratio = cost(200_000) / cost(1_000)
        assert ratio < 3, f"200x the children made append() x{ratio:.1f}"

    def test_remove_takes_the_identical_child(self) -> None:
        root = ET.Element("root")
        first = ET.SubElement(root, "item", n="1")
        second = ET.SubElement(root, "item", n="1")

        root.remove(second)

        assert list(root) == [first]
        with pytest.raises(ValueError):
            root.remove(second)

    def test_insert_and_index_deletion_shift_the_rest(self) -> None:
        root = ET.fromstring("<r><a/><b/></r>")

        root.insert(0, ET.Element("front"))
        assert [child.tag for child in root] == ["front", "a", "b"]
        del root[1]
        assert [child.tag for child in root] == ["front", "b"]

    def test_extend_accepts_an_iterator(self) -> None:
        root = ET.Element("root")

        root.extend(ET.Element(tag) for tag in "abc")

        assert [child.tag for child in root] == ["a", "b", "c"]

    def test_clear_empties_the_element_and_leaves_it_attached(self) -> None:
        root = ET.fromstring("<r><a x='1'>text<b/></a>tail</r>")
        child = root[0]

        child.clear()

        assert root[0] is child
        assert (len(child), child.attrib, child.text, child.tail) == (0, {}, None, None)


class TestAttributesAndCopies:
    """`Element()` copies `attrib`; `attrib` is the element's own dict;
    `keys()` and `items()` are new lists; `copy.copy` shares the children and
    `copy.deepcopy` copies them."""

    def test_the_constructor_copies_attrib(self) -> None:
        attributes = {"n": "1"}

        element = ET.Element("item", attributes)
        attributes["n"] = "2"

        assert element.get("n") == "1"
        assert element.attrib is not attributes

    def test_attrib_is_the_element_s_own_dict(self) -> None:
        element = ET.Element("item", n="1")

        element.attrib["n"] = "2"

        assert element.attrib is element.attrib
        assert element.get("n") == "2"

    def test_keys_and_items_are_new_lists(self) -> None:
        element = ET.Element("item", a="1", b="2")

        assert element.keys() is not element.keys()
        assert element.items() == [("a", "1"), ("b", "2")]
        assert element.get("missing", "default") == "default"

    def test_makeelement_is_unattached(self) -> None:
        root = ET.Element("root")

        made = root.makeelement("item", {"n": "1"})

        assert len(root) == 0 and made.get("n") == "1"

    def test_a_shallow_copy_shares_the_children_and_attributes(self) -> None:
        root = ET.fromstring("<r a='1'><b/></r>")

        shallow = copy.copy(root)

        assert shallow is not root and shallow[0] is root[0]
        assert shallow.attrib is root.attrib

    def test_a_deep_copy_copies_the_children_and_shares_the_strings(self) -> None:
        root = ET.fromstring("<r a='1'><b>text</b></r>")

        deep = copy.deepcopy(root)

        assert deep[0] is not root[0]
        assert deep.attrib is not root.attrib
        assert deep[0].text is root[0].text


class TestIterationIsLazy:
    """`iter` and `itertext` | O(1) to create, O(e) to exhaust | O(d)."""

    def test_creating_an_iterator_allocates_nothing_for_the_tree(self) -> None:
        root = ET.fromstring("<r>" + "<a/>" * 100_000 + "</r>")
        root.iter()

        peak = peak_bytes(root.iter)

        assert peak < 1_000, f"iter() allocated {peak} bytes over 100,000 elements"

    def test_the_walk_holds_one_entry_per_open_level(self) -> None:
        deep = ET.fromstring("<a>" * 800 + "</a>" * 800)
        flat = ET.fromstring("<a>" + "<a/>" * 799 + "</a>")

        def walk(root: ET.Element) -> Callable[[], int]:
            return lambda: sum(1 for _ in root.iter())

        walk(deep)()
        walk(flat)()
        peaks = [peak_bytes(walk(deep)), peak_bytes(walk(flat))]

        assert walk(deep)() == walk(flat)() == 800
        assert peaks[0] > peaks[1] * 10, f"deep and flat walks peaked at {peaks}"

    def test_tag_filters_and_star_means_every_element(self) -> None:
        root = ET.fromstring("<r><a/><b><a/></b></r>")

        assert [elem.tag for elem in root.iter("a")] == ["a", "a"]
        assert [elem.tag for elem in root.iter("*")] == ["r", "a", "b", "a"]

    def test_itertext_yields_text_and_tail_in_order(self) -> None:
        root = ET.fromstring("<r>one<a>two</a>three<b/><c>four</c></r>")

        assert list(root.itertext()) == ["one", "two", "three", "four"]


class TestPathCosts:
    """*Path expressions*: a bare tag scans children, `.//` walks the subtree,
    `find` stops early, `..` and positions build a parent map."""

    def test_a_bare_tag_compares_each_child_once(self) -> None:
        root = flat_tree(1_000)

        assert counted(lambda: root.findall("item")) == 1_000
        assert counted(lambda: root.find("item")) == 1

    def test_a_bare_tag_never_reaches_a_grandchild(self) -> None:
        root = ET.Element("root")
        middle = ET.SubElement(root, "middle")
        for _ in range(1_000):
            ET.SubElement(middle, CountingTag("item"))

        assert counted(lambda: root.findall("item")) == 0
        assert root.find("item") is None

    def test_descendants_walk_the_subtree_and_find_stops_early(self) -> None:
        root = flat_tree(1_000)

        assert counted(lambda: root.findall(".//item")) == 1_000
        assert counted(lambda: root.find(".//item")) == 1
        assert counted(lambda: list(root.iter("item"))) == 1_000

    def test_a_path_of_tags_scans_children_per_step(self) -> None:
        root = ET.fromstring("<r><shelf><book>A</book><book>B</book></shelf><book>C</book></r>")

        assert root.findtext("shelf/book") == "A"
        assert [book.text for book in root.findall("shelf/book")] == ["A", "B"]

    def test_parent_steps_build_a_map_of_the_subtree(self) -> None:
        root = ET.Element("root")
        first = ET.SubElement(root, "a")
        for _ in range(100_000):
            ET.SubElement(first, "b")
        root.find("a")
        root.find("a/..")

        child_peak = peak_bytes(lambda: root.find("a"))
        parent_peak = peak_bytes(lambda: root.find("a/.."))

        assert child_peak < 1_000, f"a child step allocated {child_peak} bytes"
        assert parent_peak > 1_000_000, f"a parent step allocated only {parent_peak} bytes"

    def test_positional_predicates_scan_siblings_per_parent_where_fixed(self) -> None:
        minor = sys.version_info[:2]
        fixed = sys.version_info[:3] >= (*minor, POSITIONAL_SCAN_FIXED.get(minor, 0))
        root = flat_tree(1_000)

        comparisons = counted(lambda: root.findall("item[1]"))

        assert root.findall("item[1]") == [root[0]]
        if fixed:
            assert comparisons < 10_000, f"{comparisons} comparisons for 1,000 siblings"
        else:
            assert comparisons > 100_000, f"{comparisons} comparisons for 1,000 siblings"

    def test_distinct_sibling_tags_each_need_a_scan(self) -> None:
        root = ET.Element("root")
        for index in range(1_000):
            ET.SubElement(root, CountingTag(f"t{index}"))

        comparisons = counted(lambda: root.findall("*[1]"))

        assert comparisons > 100_000, f"{comparisons} comparisons for 1,000 distinct tags"

    def test_predicates_select_what_the_page_says(self) -> None:
        root = ET.fromstring("<r><a k='1'><t>x</t></a><a k='2'><t>y</t></a><a><u/></a></r>")

        assert [a.get("k") for a in root.findall("a[@k]")] == ["1", "2"]
        assert [a.get("k") for a in root.findall("a[@k='2']")] == ["2"]
        assert [a.get("k") for a in root.findall("a[@k!='2']")] == ["1"]
        assert len(root.findall("a[u]")) == 1
        assert [a.get("k") for a in root.findall("a[t='y']")] == ["2"]
        assert root.find("a[last()]") is root[2]
        assert root.find("a[last()-1]") is root[1]

    def test_findtext_distinguishes_no_text_from_no_match(self) -> None:
        root = ET.fromstring("<r><empty/></r>")

        assert root.findtext("empty") == ""
        assert root.findtext("missing", "default") == "default"

    def test_iterfind_is_lazy(self) -> None:
        root = flat_tree(1_000)

        matches: list[Iterator[ET.Element]] = []

        assert counted(lambda: matches.append(root.iterfind(".//item"))) == 0
        assert counted(lambda: next(matches[0])) == 1

    def test_an_absolute_path_on_a_tree_warns(self) -> None:
        tree = ET.ElementTree(ET.fromstring("<r><a/></r>"))

        with pytest.warns(FutureWarning):
            found = tree.find("/a")

        root = tree.getroot()
        assert root is not None and found is root[0]


class TestElementTreeWrapper:
    """`ElementTree` holds a root; its searches are the root's."""

    def test_the_wrapper_holds_the_root(self) -> None:
        root = ET.Element("r")
        tree = ET.ElementTree(root)

        assert tree.getroot() is root
        replacement = ET.Element("s")
        tree._setroot(replacement)  # noqa: SLF001 - the documented name
        assert tree.getroot() is replacement

    def test_parse_replaces_the_root_and_returns_it(self) -> None:
        tree = ET.ElementTree(ET.Element("old"))

        root = tree.parse(io.BytesIO(b"<new><a/></new>"))

        assert tree.getroot() is root and root.tag == "new"
        assert [elem.tag for elem in tree.iter()] == ["new", "a"]
        assert [elem.tag for elem in tree.iterfind("a")] == ["a"]
        assert tree.findall("a")[0] is root[0]
        assert tree.findtext("a") == ""

    def test_a_file_argument_parses_at_construction(self) -> None:
        tree = ET.ElementTree(file=io.BytesIO(b"<r/>"))
        root = tree.getroot()

        assert root is not None and root.tag == "r"

    def test_write_c14n_raises(self) -> None:
        tree = ET.ElementTree(ET.Element("r"))

        with pytest.raises(ValueError, match="c14n"):
            tree.write_c14n(io.BytesIO())


class TestSerialization:
    """`tostring` holds the output; `write` streams it and holds O(d + q);
    serializing and `indent` recurse per level."""

    @staticmethod
    def big_tree() -> ET.Element:
        root = ET.Element("root")
        for index in range(100_000):
            ET.SubElement(root, "item", id=str(index)).text = "x" * 10
        return root

    def test_tostring_holds_the_whole_output_and_write_does_not(self) -> None:
        root = self.big_tree()
        tree = ET.ElementTree(root)
        output = ET.tostring(root)
        tree.write(DiscardingSink(), encoding="unicode")

        held = peak_bytes(lambda: ET.tostring(root))
        streamed = peak_bytes(lambda: tree.write(DiscardingSink(), encoding="unicode"))

        assert held > len(output), f"tostring peaked at {held} for {len(output)} bytes"
        assert streamed < 100_000, f"write() to a discarding sink peaked at {streamed}"

    def test_write_holds_one_entry_per_distinct_name(self) -> None:
        same = ET.Element("root")
        distinct = ET.Element("root")
        for index in range(50_000):
            ET.SubElement(same, "t")
            ET.SubElement(distinct, f"t{index}")
        for root in (same, distinct):
            ET.ElementTree(root).write(DiscardingSink(), encoding="unicode")

        peaks = [
            peak_bytes(lambda r=root: ET.ElementTree(r).write(DiscardingSink(), encoding="unicode"))  # type: ignore[misc]
            for root in (same, distinct)
        ]

        assert peaks[1] > peaks[0] * 100, f"one name and 50,000 names peaked at {peaks}"

    def test_write_holds_the_escaped_text_it_is_writing(self) -> None:
        root = ET.Element("r")
        root.text = "&" * 1_000_000
        tree = ET.ElementTree(root)
        tree.write(DiscardingSink(), encoding="unicode")

        peak = peak_bytes(lambda: tree.write(DiscardingSink(), encoding="unicode"))

        assert peak > 1_000_000, f"escaping a 1,000,000-character run peaked at {peak}"

    def test_tostringlist_is_tostring_in_pieces(self) -> None:
        root = ET.fromstring("<r>" + "<a>x</a>" * 10_000 + "</r>")

        text_pieces = ET.tostringlist(root, encoding="unicode")
        byte_chunks = ET.tostringlist(root)

        assert len(text_pieces) > 10_000
        assert "".join(text_pieces) == ET.tostring(root, encoding="unicode")
        assert 1 < len(byte_chunks) < 100
        assert b"".join(byte_chunks) == ET.tostring(root)

    def test_methods_and_encodings(self) -> None:
        root = ET.fromstring("<r><br/>text</r>")

        assert ET.tostring(root, encoding="unicode") == "<r><br />text</r>"
        assert ET.tostring(root, encoding="unicode", method="text") == "text"
        assert ET.tostring(root, encoding="unicode", method="html") == "<r><br>text</r>"

    def test_dump_writes_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        ET.dump(ET.fromstring("<r><a/></r>"))

        assert capsys.readouterr().out == "<r><a /></r>\n"

    def test_deep_trees_parse_and_walk_but_do_not_serialize(self) -> None:
        depth = sys.getrecursionlimit() + 100
        root = ET.fromstring("<a>" * depth + "</a>" * depth)

        assert sum(1 for _ in root.iter()) == depth
        with pytest.raises(RecursionError):
            ET.tostring(root)
        with pytest.raises(RecursionError):
            ET.indent(root)


class TestIndent:
    """`indent` | O(n + d²) | O(d²): one indentation string per level."""

    def test_siblings_share_one_indentation_string(self) -> None:
        root = ET.fromstring("<r><a/><b/><c><d/></c></r>")

        ET.indent(root)

        assert root[0].tail is root[1].tail
        assert ET.tostring(root, encoding="unicode") == (
            "<r>\n  <a />\n  <b />\n  <c>\n    <d />\n  </c>\n</r>"
        )

    def test_text_that_is_not_whitespace_is_kept(self) -> None:
        root = ET.fromstring("<r>keep<a/></r>")

        ET.indent(root, space="\t")

        assert root.text == "keep" and root[0].tail == "\n"

    def test_deep_chains_hold_a_string_per_level(self) -> None:
        def chain() -> ET.Element:
            return ET.fromstring("<a>" * 400 + "</a>" * 400)

        def siblings() -> ET.Element:
            return ET.fromstring("<a>" + "<a/>" * 399 + "</a>")

        ET.indent(chain())
        deep_tree, flat_tree_ = chain(), siblings()

        peaks = [
            peak_bytes(lambda: ET.indent(deep_tree)),
            peak_bytes(lambda: ET.indent(flat_tree_)),
        ]

        assert peaks[0] > peaks[1] * 20, f"400 deep and 400 wide peaked at {peaks}"


class TestNamespaceRegistry:
    """`register_namespace` | O(r) | O(r) over a global registry."""

    @pytest.fixture(autouse=True)
    def _restore_registry(self) -> Iterator[None]:
        registry = ET._namespace_map  # type: ignore[attr-defined]  # noqa: SLF001
        saved = dict(registry)
        yield
        registry.clear()
        registry.update(saved)

    def test_registered_prefixes_are_used(self) -> None:
        ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")

        title = ET.Element("{http://purl.org/dc/elements/1.1/}title")

        assert ET.tostring(title, encoding="unicode") == (
            '<dc:title xmlns:dc="http://purl.org/dc/elements/1.1/" />'
        )

    def test_generated_prefixes_are_reserved(self) -> None:
        with pytest.raises(ValueError, match="reserved"):
            ET.register_namespace("ns0", "urn:x")

    @pytest.mark.timing
    def test_registering_scans_the_registry(self) -> None:
        registry = ET._namespace_map  # type: ignore[attr-defined]  # noqa: SLF001

        def cost(prefixes: int) -> float:
            registry.update({f"urn:{index}": f"p{index}" for index in range(prefixes)})
            return best_ns(lambda: ET.register_namespace("probe", "urn:probe"), inner=5)

        small = cost(20)
        large = cost(20_000)

        assert large / small > 20, f"1,000x the prefixes cost x{large / small:.1f}"


class TestCanonicalization:
    """`canonicalize` | O(n + r + (e + b)·(d + s) + b log a) | O(n + r), or
    O(d + s + a + c + r) with `out`."""

    def test_attributes_are_sorted(self) -> None:
        assert ET.canonicalize('<r b="2"  a="1"/>') == '<r a="1" b="2"></r>'

    def test_out_streams_the_result(self) -> None:
        document = "<r>" + "<a/>" * 100_000 + "</r>"
        ET.canonicalize("<r/>")
        output = ET.canonicalize(document)

        held = peak_bytes(lambda: ET.canonicalize(document))
        streamed = peak_bytes(lambda: ET.canonicalize(document, out=DiscardingSink()))

        assert held > len(output), f"returning {len(output)} characters peaked at {held}"
        assert streamed < 1_000_000, f"streaming peaked at {streamed}"

    def test_the_writer_target_writes_what_canonicalize_returns(self) -> None:
        pieces: list[str] = []
        parser = ET.XMLParser(target=ET.C14NWriterTarget(pieces.append, with_comments=True))
        parser.feed("<r><!--c--><?p d?>t</r>")
        parser.close()

        assert "".join(pieces) == "<r><!--c--><?p d?>t</r>"

    @pytest.mark.timing
    def test_nesting_costs_more_than_the_same_elements_side_by_side(self) -> None:
        elements = 4_000
        nested = "<a>" * elements + "</a>" * elements
        flat = "<r>" + "<a></a>" * (elements - 1) + "</r>"

        nested_ns = best_ns(lambda: ET.canonicalize(nested), repeats=3)
        flat_ns = best_ns(lambda: ET.canonicalize(flat), repeats=3)

        ratio = nested_ns / flat_ns
        assert ratio > 10, f"4,000 elements nested cost x{ratio:.1f} their flat cost"


class TestOtherConstructors:
    """`Comment`, `ProcessingInstruction`, `QName`, `iselement`, `VERSION` and
    the truth value of an element."""

    def test_comment_and_pi_elements(self) -> None:
        comment = ET.Comment("note")
        instruction = ET.ProcessingInstruction("target", "data")

        assert comment.tag is ET.Comment and comment.text == "note"
        assert ET.PI is ET.ProcessingInstruction
        assert instruction.text == "target data"
        assert ET.tostring(comment) == b"<!--note-->"

    def test_qname_builds_and_compares_as_its_text(self) -> None:
        name = ET.QName("urn:x", "tag")

        assert name.text == "{urn:x}tag"
        assert name == ET.QName("{urn:x}tag")
        assert hash(name) == hash("{urn:x}tag")

    def test_iselement_checks_for_a_tag_attribute(self) -> None:
        class Tagged:
            tag = "t"

        assert ET.iselement(ET.Element("a"))
        assert ET.iselement(Tagged())
        assert not ET.iselement("a")

    def test_version_is_a_string(self) -> None:
        assert ET.VERSION == "1.3.0"

    def test_an_element_without_children_is_false(self) -> None:
        match = ET.fromstring("<r><empty/></r>").find("empty")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            truth = bool(match)

        assert match is not None and truth is False
        if sys.version_info >= (3, 12):
            assert [warning.category for warning in caught] == [DeprecationWarning]


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
    """Each block runs in its own subprocess, so the namespace registry cannot
    leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(root) == 1000" in s)
        mutated = source.replace("len(root) == 1000", "len(root) == 0", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
