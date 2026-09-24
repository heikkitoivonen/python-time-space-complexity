"""Tests for docs/stdlib/xml.dom.md.

The page prices minidom by the tree it builds and pulldom by the buffer it
reads. Child-list operations are priced by the children of one node, text
edits by the characters of one node, and searches and copies by the subtree
they walk. Space is settled by traced allocation and identity; where only a
stopwatch separates two bounds, the tests compare sizes far apart. The ID
cache and the text joining in `parse()` are observed by wrapping the method
that does the work, so the counts need no tolerance.

Measurement scope:

* Parsing: `parseString()`'s traced peak grows more than 5x from 2,000 to
  20,000 elements, and is more than twice `ElementTree.fromstring()`'s on the
  same 10,000-element document. `parse()` of a path and of a stream give the
  same tree, and `parse()` with `bufsize` builds it through `pulldom.parse()`.
* Long text: a 1,000,000-character text node reaches the builder in at least
  50 pieces from `parse()`, and from `parseString()` when it is 80-character
  lines, and the characters already joined when each piece arrives sum to
  more than 10 times the text's length; unbroken text reaches
  `parseString()` in one piece. A timing test finds 32,000,000 characters
  cost more than 20x what 4,000,000 do from a file, against 8x for linear
  work. Entity references are not varied.
* pulldom: reading 500,000 records peaks under 3x what 50,000 do; nothing is
  attached to the root, and `expandNode()` builds one record under its node
  and leaves it detached. `parseString()` queues every event of a
  1,000-record document before returning the first; `parse()` reads
  `bufsize` characters at a time, 16,364 by default, and queues only what
  one read produced. `getEvent()` returns `None` at the end and iteration
  stops before `END_DOCUMENT`, a string is
  opened as a file name, `SAX2DOM` attaches every node, `reset()` and
  `clear()` are observed, and indexing is asserted gone on 3.11+.
* Child lists, timed: `insertBefore()`, `removeChild()` and `replaceChild()`
  against the last child cost more than 20x as much among 100,000 children
  as among 1,000; `appendChild()` undone by popping the child list is their
  control, under 3x. Appending a 50,000-child fragment costs
  more than 25x a 5,000-child one, against 10x for linear work.
  `appendChild()` below a 5,000-deep chain costs under 3x what it costs at
  the root on releases with the O(1) cache clear, and more than 20x on those
  without; the boundary is asserted per patch release. Every CI interpreter
  has the fix, so the other branch runs only on an older patch release.
* `normalize()` over 10,000 adjacent 100-character text nodes costs more than
  30x what 1,000 do, and `wholeText` over 50,000 costs more than 30x what
  5,000 do, both against 10x for linear work. `appendData()` on a
  10,000,000-character node costs more than 50x what it does on 10,000.
  `splitText()`, `replaceWholeText()` and `substringData()` are asserted by
  result.
* Searching: `getElementsByTagName()` returns a new list in document order,
  allocates under 10 KB when nothing matches in a 20,000-element tree and
  over 100 KB when everything does, and costs more than 5x as much on 10x
  the tree, timed. `getElementById()` calls `Document._get_elem_info()` no
  times without DTD declarations, once per element with a non-ID attribute
  declaration, once per element on the first lookup with ID declarations, no times on a repeated lookup, and again after a mutation.
  `setIdAttribute()` at depth 5,000 costs more than 20x what it costs at the
  root, timed, and an attribute marked with `setIdAttribute()` and renamed
  with `renameNode()` stays an ID.
* Attributes: `Element.attributes` is a new object per access,
  `NamedNodeMap.item()` costs more than 50x as much among 10,000 attributes
  as among 10, timed, and `getAttribute()`/`setAttribute()`/
  `removeAttribute()` cost under 3x as much. Absent attributes, owned
  `Attr` nodes and `items()` are asserted by result.
* Cloning, importing and serializing are asserted by result.
  `writexml()` to a discarding sink peaks under 10 KB for a 10,000-element
  tree while `toxml()` peaks above the 300 KB it returns; the first
  `writexml()` over 10,000 elements built without attributes allocates over
  500 KB and the second under 10 KB. Attribute
  whitespace escaping is asserted on 3.13+, and its absence before.
* Deep trees: a chain twice the recursion limit deep parses; walking it with
  `getElementsByTagName()`, `toxml()`, `writexml()`, `cloneNode(True)`,
  `importNode(node, True)` and `normalize()` raises `RecursionError`, and
  `getElementById()` and `expandNode()` do not. A chain 0.7 times the limit
  deep is walked by `getElementsByTagName()` and not by `unlink()`.
* `documentElement` costs under 3x as much over a 100,000-child root as over
  one child, timed. `entities.getNamedItem()` costs more than 50x as much for
  the last of 10,000 declared entities as for the last of 10, timed.
* Constants, exceptions, the registry and `DOMImplementation` are asserted
  by value; the registry is restored afterwards.
* With the cycle collector disabled, an element and its attribute are freed
  when the last reference to an unlinked document goes, and not when the
  document was not unlinked; `gc.collect()` frees both.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The DOM interfaces `xml.dom.Document`, `xml.dom.Attr` and the rest are
  documented by the Python docs under `xml.dom` and implemented by minidom's
  classes; `xml.dom.Node` exists at runtime only as the holder of the node
  type constants. The audit reports the interfaces as unresolved; the page
  and these tests price minidom's. `xml.dom.minicompat`,
  `xml.dom.xmlbuilder`, `xml.dom.expatbuilder`, `xml.dom.domreg` and
  `xml.dom.NodeFilter` are undocumented internals and are not covered.
* The O(n) parse bounds are Expat's single pass; the tests measure growth in
  element count and in one text node's length, not in attributes or
  entities. Treating n as text after internal entity expansion is a
  definition.
* pulldom's bounded memory relies on the cycle collector: an element with
  attributes forms a reference cycle with them, so the plateau is where the
  collector keeps up, not a fixed allocation. The measurement ran with the
  collector enabled, on elements with one attribute each.
* The O(c + h) space of `writexml()` is read from Lib/xml/dom/minidom.py; the
  test holds the height at two. With `addindent`, each level also holds a
  longer indent string, which the page excludes and the test does not
  measure. `unlink()`'s O(a + h) is read from the same file.
* Priced from Lib/xml/dom/minidom.py and pulldom.py, and asserted only by
  result: `cloneNode()` and `importNode()` at O(s), `splitText()` at
  O(c + k), `replaceWholeText()` at O(r·k), `substringData()`, `unlink()`,
  `expandNode()`, `SAX2DOM`, `Document.appendChild()` checking its own
  children, pulldom's O(n) over a stream, `DOMImplementation.hasFeature()`,
  `renameNode()`, `getUserData()`, `setUserData()`, and the O(c) comparison
  `setAttribute()` makes before replacing a value. Name lengths are held
  short throughout.
* Timing ratios are measured on aarch64; each threshold sits at least 2x
  from the ratio of the bound it excludes.
"""

from __future__ import annotations

import gc
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import weakref
import xml.dom
import xml.etree.ElementTree as ET
import xml.sax
from collections.abc import Callable
from typing import Any
from xml.dom import expatbuilder
from xml.dom import minidom as typed_minidom
from xml.dom import pulldom as typed_pulldom

import pytest

# typeshed marks most DOM attributes Optional, and the tests reach through them.
minidom: Any = typed_minidom
pulldom: Any = typed_pulldom

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "xml.dom.md"
EXPECTED_BLOCKS = 12

# The ID-cache fix (gh-142145) landed in these patch releases.
ID_CACHE_FIX = {10: 20, 11: 15, 12: 13, 13: 11, 14: 2}
MINOR = sys.version_info[1]
HAS_O1_CACHE_CLEAR = sys.version_info[:3] >= (3, MINOR, ID_CACHE_FIX.get(MINOR, 0))


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


def records(count: int) -> str:
    """A document of `count` records, each with one attribute and one text node."""
    body = "".join(f'<item id="i{index}">text {index}</item>' for index in range(count))
    return f"<root>{body}</root>"


def chain(depth: int) -> str:
    return "<a>" * depth + "</a>" * depth


class DiscardingSink:
    """A file-like object that keeps nothing."""

    def write(self, text: str) -> int:
        return len(text)


class TestParsingBuildsTheWholeTree:
    """`parse()` and `parseString()` | O(n) | O(n): the whole tree before they
    return, and a minidom tree is larger than an ElementTree one."""

    def test_the_peak_follows_the_document(self) -> None:
        small = records(2_000)
        large = records(20_000)
        minidom.parseString(small)  # warm

        small_peak = peak_bytes(lambda: minidom.parseString(small))
        large_peak = peak_bytes(lambda: minidom.parseString(large))

        assert large_peak > small_peak * 5, f"10x the records: {small_peak} -> {large_peak}"

    def test_a_minidom_tree_is_larger_than_an_elementtree_one(self) -> None:
        text = records(10_000)
        minidom.parseString(text)
        ET.fromstring(text)

        dom_peak = peak_bytes(lambda: minidom.parseString(text))
        et_peak = peak_bytes(lambda: ET.fromstring(text))

        assert dom_peak > et_peak * 2, f"minidom {dom_peak} bytes, ElementTree {et_peak}"

    def test_a_path_a_stream_and_a_string_give_the_same_tree(self, tmp_path: pathlib.Path) -> None:
        text = records(100)
        path = tmp_path / "doc.xml"
        path.write_text(text, encoding="utf-8")

        trees = [
            minidom.parse(str(path)),
            minidom.parse(io.BytesIO(text.encode())),
            minidom.parseString(text),
        ]

        assert len({tree.documentElement.toxml() for tree in trees}) == 1
        assert len(trees[0].getElementsByTagName("item")) == 100

    def test_bufsize_builds_through_pulldom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[Any] = []
        original = pulldom.parse

        def recording(*args: Any, **kwargs: Any) -> Any:
            calls.append(kwargs.get("bufsize"))
            return original(*args, **kwargs)

        monkeypatch.setattr(pulldom, "parse", recording)

        doc = minidom.parse(io.BytesIO(records(50).encode()), bufsize=64)

        assert calls == [64]
        assert len(doc.getElementsByTagName("item")) == 50
        minidom.parse(io.BytesIO(records(5).encode()))
        assert calls == [64], "without parser or bufsize, parse() does not use pulldom"


class TestLongTextNodes:
    """`parse()` and `parseString()` | O(n + Σc²): a text node arriving in
    several pieces is rebuilt once per piece. A file arrives 16 KiB per parser
    call; within a call, text broken by newlines arrives in pieces too."""

    LENGTH = 1_000_000

    @classmethod
    def pieces(
        cls, monkeypatch: pytest.MonkeyPatch, build: Callable[[bytes], Any], line: bytes = b"x"
    ) -> list[int]:
        """The length already joined when each piece of character data arrives."""
        joined: list[int] = []
        original = expatbuilder.ExpatBuilder.character_data_handler_cdata

        def recording(self: Any, data: str) -> None:
            children = self.curNode.childNodes
            joined.append(len(children[-1].data) if children else 0)
            original(self, data)

        monkeypatch.setattr(expatbuilder.ExpatBuilder, "character_data_handler_cdata", recording)
        doc = build(b"<blob>" + line * (cls.LENGTH // len(line)) + b"</blob>")
        assert len(doc.documentElement.firstChild.data) == cls.LENGTH
        assert len(doc.documentElement.childNodes) == 1
        return joined

    def test_a_file_delivers_the_text_in_many_pieces(self, monkeypatch: pytest.MonkeyPatch) -> None:
        joined = self.pieces(monkeypatch, lambda data: minidom.parse(io.BytesIO(data)))

        assert len(joined) >= 50, f"{len(joined)} pieces for {self.LENGTH} characters"
        assert sum(joined) > self.LENGTH * 10, (
            f"{sum(joined)} characters already joined across {len(joined)} pieces: "
            "each piece rebuilds the text so far"
        )

    def test_a_string_of_unbroken_text_delivers_it_in_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        joined = self.pieces(monkeypatch, minidom.parseString)

        assert joined == [0]

    def test_a_string_of_lines_delivers_it_in_many(self, monkeypatch: pytest.MonkeyPatch) -> None:
        joined = self.pieces(monkeypatch, minidom.parseString, line=b"x" * 79 + b"\n")

        assert len(joined) >= 50, f"{len(joined)} pieces for {self.LENGTH} characters"
        assert sum(joined) > self.LENGTH * 10, f"{sum(joined)} characters already joined"

    @pytest.mark.timing
    def test_the_file_cost_grows_quadratically_in_the_text(self) -> None:
        def parse(length: int) -> Callable[[], Any]:
            data = b"<blob>" + b"x" * length + b"</blob>"
            return lambda: minidom.parse(io.BytesIO(data))

        small_ns = best_ns(parse(4_000_000), repeats=3)
        large_ns = best_ns(parse(32_000_000), repeats=3)

        ratio = large_ns / small_ns
        assert ratio > 20, f"8x the text cost x{ratio:.1f}; linear work would give x8"


class CountingStream(io.BytesIO):
    """A binary stream that records the size of every read."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads: list[int] = []

    def read(self, size: int | None = -1, /) -> bytes:
        chunk = super().read(size)
        self.reads.append(len(chunk))
        return chunk


def queued(stream: Any) -> int:
    """Events the stream's handler has queued and not yet handed out."""
    count = 0
    link = stream.pulldom.firstEvent[1]  # type: ignore[attr-defined]
    while link:
        count += 1
        link = link[1]
    return count


class TestPulldomStreams:
    """`pulldom.parse()` | O(b + d) space unless nodes are expanded;
    `pulldom.parseString()` | O(n) space; `expandNode()` | O(s)."""

    def test_memory_does_not_follow_the_document(self) -> None:
        def consume(data: bytes) -> None:
            for _event, _node in pulldom.parse(io.BytesIO(data)):
                pass

        small = records(50_000).encode()
        large = records(500_000).encode()
        consume(records(100).encode())  # warm
        gc.collect()

        small_peak = peak_bytes(lambda: consume(small))
        large_peak = peak_bytes(lambda: consume(large))

        assert large_peak < small_peak * 3, (
            f"10x the records peaked at {large_peak} against {small_peak}"
        )

    def test_nothing_is_attached_unless_expanded(self) -> None:
        events = pulldom.parse(io.BytesIO(records(100).encode()))
        root = None
        expanded = []
        for event, node in events:
            if event == pulldom.START_ELEMENT and node.tagName == "root":
                root = node
            elif event == pulldom.START_ELEMENT and node.getAttribute("id") == "i7":
                events.expandNode(node)
                expanded.append(node)

        assert root is not None and not root.hasChildNodes()
        assert len(expanded) == 1
        assert expanded[0].firstChild.data == "text 7"
        assert expanded[0].parentNode is None

    def test_expand_node_builds_the_whole_subtree(self) -> None:
        data = b"<r><a><b><c>deep</c></b><b/></a><z/></r>"
        events = pulldom.parse(io.BytesIO(data))
        expanded = None
        for event, node in events:
            if event == pulldom.START_ELEMENT and node.tagName == "a":
                events.expandNode(node)
                expanded = node
                break

        assert expanded is not None
        assert expanded.toxml() == "<a><b><c>deep</c></b><b/></a>"
        event, node = next(events)
        assert (event, node.tagName) == (pulldom.START_ELEMENT, "z")

    def test_parse_string_queues_every_event_at_the_first(self) -> None:
        text = records(1_000)
        total = sum(1 for _ in pulldom.parseString(text))

        stream = pulldom.parseString(text)
        next(stream)

        assert queued(stream) == total - 1

    def test_parse_reads_a_buffer_at_a_time(self) -> None:
        data = records(1_000).encode()
        stream = CountingStream(data)
        events = pulldom.parse(stream, bufsize=1_000)

        next(events)
        assert stream.reads == [1_000]
        assert 0 < queued(events) < 200

        for _ in events:
            pass
        assert sum(stream.reads) == len(data)
        assert max(stream.reads) == 1_000

    def test_the_default_buffer(self) -> None:
        stream = CountingStream(records(2_000).encode())
        next(pulldom.parse(stream))

        assert pulldom.default_bufsize == 16_364
        assert stream.reads == [16_364]

    def test_get_event_returns_none_at_the_end(self) -> None:
        events = pulldom.parseString("<r/>")
        kinds = []
        while (event := events.getEvent()) is not None:
            kinds.append(event[0])

        # The first None ends the stream; iteration never reaches END_DOCUMENT.
        assert kinds == [pulldom.START_DOCUMENT, pulldom.START_ELEMENT, pulldom.END_ELEMENT]
        assert [kind for kind, _ in pulldom.parseString("<r/>")] == kinds

    def test_a_string_is_a_file_name(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "doc.xml"
        path.write_bytes(b"<r><a/></r>")

        events = pulldom.parse(str(path))
        names = [node.tagName for event, node in events if event == pulldom.START_ELEMENT]
        events.stream.close()  # type: ignore[attr-defined]

        assert names == ["r", "a"]

    def test_sax2dom_attaches_every_node(self) -> None:
        handler = pulldom.SAX2DOM()
        xml.sax.parseString(records(20).encode(), handler)

        document = handler.document
        assert document is not None
        assert len(document.getElementsByTagName("item")) == 20
        assert document.documentElement.lastChild.firstChild.data == "text 19"

    def test_pulldom_creates_nodes_and_queues_events(self) -> None:
        handler = pulldom.PullDOM()
        xml.sax.parseString(b"<r><a/></r>", handler)

        document = handler.document
        assert document is not None
        assert not document.documentElement.hasChildNodes()
        link = handler.firstEvent[1]
        kinds = []
        while link:
            kinds.append(link[0][0])
            link = link[1]
        assert kinds == [
            pulldom.START_DOCUMENT,
            pulldom.START_ELEMENT,
            pulldom.START_ELEMENT,
            pulldom.END_ELEMENT,
            pulldom.END_ELEMENT,
            pulldom.END_DOCUMENT,
        ]

    def test_reset_installs_a_fresh_handler_and_clear_drops_everything(self) -> None:
        events = pulldom.parseString("<r/>")
        first = events.pulldom  # type: ignore[attr-defined]

        events.reset()
        assert events.pulldom is not first  # type: ignore[attr-defined]

        events.clear()
        assert events.parser is None and events.stream is None  # type: ignore[attr-defined]
        assert not hasattr(events, "pulldom")

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="removed in 3.11")
    def test_the_stream_cannot_be_indexed(self) -> None:
        assert not hasattr(pulldom.DOMEventStream, "__getitem__")


class TestChildListOperations:
    """`appendChild()` | O(1) amortized; `insertBefore()`, `removeChild()`,
    `replaceChild()` | O(k); a fragment | O(f²)."""

    @staticmethod
    def element_with(children: int) -> tuple[Any, Any]:
        doc = minidom.Document()
        parent = doc.createElement("p")
        doc.appendChild(parent)
        for _ in range(children):
            parent.appendChild(doc.createElement("c"))
        return doc, parent

    @staticmethod
    def operation(name: str, children: int) -> Callable[[], Any]:
        doc, parent = TestChildListOperations.element_with(children)
        spare = doc.createElement("spare")

        def insert() -> None:
            parent.insertBefore(spare, parent.lastChild)
            parent.removeChild(spare)

        def remove() -> None:
            last = parent.removeChild(parent.lastChild)
            parent.appendChild(last)

        def replace() -> None:
            old = parent.replaceChild(spare, parent.lastChild)
            parent.replaceChild(old, spare)

        def append() -> None:
            parent.appendChild(spare)
            parent.childNodes.pop()
            spare.parentNode = spare.previousSibling = None
            parent.lastChild.nextSibling = None

        return {
            "insertBefore": insert,
            "removeChild": remove,
            "replaceChild": replace,
            "appendChild": append,
        }[name]

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["insertBefore", "removeChild", "replaceChild"])
    def test_scanning_operations_follow_the_children(self, name: str) -> None:
        few = best_ns(self.operation(name, 1_000), inner=20)
        many = best_ns(self.operation(name, 100_000), inner=20)

        ratio = many / few
        assert ratio > 20, f"{name}: 100x the children cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_appending_does_not(self) -> None:
        few = best_ns(self.operation("appendChild", 1_000), inner=200)
        many = best_ns(self.operation("appendChild", 100_000), inner=200)

        ratio = many / few
        assert ratio < 3, f"appendChild: 100x the children cost x{ratio:.1f}"

    def test_insert_before_and_replace_child_place_the_node(self) -> None:
        doc, parent = self.element_with(3)
        head = doc.createElement("head")
        middle = parent.childNodes[1]

        parent.insertBefore(head, parent.firstChild)
        tail = doc.createElement("tail")
        parent.insertBefore(tail, None)
        new = doc.createElement("new")
        assert parent.replaceChild(new, middle) is middle

        assert [node.tagName for node in parent.childNodes] == ["head", "c", "new", "c", "tail"]
        assert new.previousSibling is parent.childNodes[1]
        assert middle.parentNode is None

    def test_appending_a_child_moves_it_from_its_old_parent(self) -> None:
        doc, first = self.element_with(1)
        second = doc.createElement("q")
        child = first.firstChild

        second.appendChild(child)

        assert not first.hasChildNodes()
        assert child.parentNode is second

    def test_removing_a_stranger_raises_not_found(self) -> None:
        doc, parent = self.element_with(1)

        with pytest.raises(xml.dom.NotFoundErr):
            parent.removeChild(doc.createElement("stranger"))

    @pytest.mark.timing
    def test_a_fragment_costs_quadratically_in_its_children(self) -> None:
        doc = minidom.Document()

        def append_fragment(children: int) -> float:
            best = None
            for _ in range(3):
                fragment = doc.createDocumentFragment()
                for _ in range(children):
                    fragment.appendChild(doc.createTextNode("x"))
                target = doc.createElement("t")
                start = time.perf_counter_ns()
                target.appendChild(fragment)
                elapsed = time.perf_counter_ns() - start
                assert len(target.childNodes) == children
                assert not fragment.hasChildNodes()
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        small = append_fragment(5_000)
        large = append_fragment(50_000)

        ratio = large / small
        assert ratio > 25, f"10x the fragment cost x{ratio:.1f}; linear work would give x10"

    @staticmethod
    def deep_node(depth: int) -> tuple[Any, Any, Any]:
        doc = minidom.Document()
        root = doc.createElement("r")
        doc.appendChild(root)
        node = root
        for _ in range(depth):
            child = doc.createElement("c")
            node.appendChild(child)
            node = child
        return doc, root, node

    @staticmethod
    def append_and_remove(doc: Any, node: Any) -> Callable[[], Any]:
        spare = doc.createElement("spare")

        def run() -> None:
            node.appendChild(spare)
            node.removeChild(spare)

        return run

    @pytest.mark.timing
    def test_appending_below_a_deep_chain(self) -> None:
        doc, root, deep = self.deep_node(5_000)

        shallow_ns = best_ns(self.append_and_remove(doc, root), inner=20)
        deep_ns = best_ns(self.append_and_remove(doc, deep), inner=20)

        ratio = deep_ns / shallow_ns
        if HAS_O1_CACHE_CLEAR:
            assert ratio < 3, f"depth 5,000 cost x{ratio:.1f} on {sys.version_info[:3]}"
        else:
            assert ratio > 20, f"depth 5,000 cost only x{ratio:.1f} on {sys.version_info[:3]}"


class TestTextNodes:
    """`normalize()` | O(s + Σr·t); `wholeText` | O(r² + t); the edits of
    `CharacterData` | O(c)."""

    @staticmethod
    def run_of(doc: Any, count: int, piece: str) -> Any:
        element = doc.createElement("w")
        for _ in range(count):
            element.appendChild(doc.createTextNode(piece))
        return element

    @pytest.mark.timing
    def test_normalize_joins_a_run_one_piece_at_a_time(self) -> None:
        doc = minidom.Document()

        def normalize(count: int) -> float:
            best = None
            for _ in range(3):
                element = self.run_of(doc, count, "x" * 100)
                start = time.perf_counter_ns()
                element.normalize()
                elapsed = time.perf_counter_ns() - start
                assert len(element.childNodes) == 1
                assert len(element.firstChild.data) == count * 100
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        ratio = normalize(10_000) / normalize(1_000)
        assert ratio > 30, f"10x the run cost x{ratio:.1f}; linear work would give x10"

    def test_normalize_drops_empty_text_and_recurses(self) -> None:
        doc = minidom.parseString("<r><a/></r>")
        root = doc.documentElement
        inner = root.firstChild
        for element in (root, inner):
            element.appendChild(doc.createTextNode(""))
            element.appendChild(doc.createTextNode("a"))
            element.appendChild(doc.createTextNode("b"))

        root.normalize()

        assert [child.nodeType for child in root.childNodes] == [
            xml.dom.Node.ELEMENT_NODE,
            xml.dom.Node.TEXT_NODE,
        ]
        assert root.lastChild.data == "ab"
        assert [child.data for child in inner.childNodes] == ["ab"]

    @pytest.mark.timing
    def test_whole_text_is_quadratic_in_the_run(self) -> None:
        doc = minidom.Document()
        short = self.run_of(doc, 5_000, "x").lastChild
        long = self.run_of(doc, 50_000, "x").lastChild
        assert len(long.wholeText) == 50_000

        ratio = best_ns(lambda: long.wholeText, repeats=3) / best_ns(lambda: short.wholeText)
        assert ratio > 30, f"10x the run cost x{ratio:.1f}; linear work would give x10"

    def test_whole_text_gathers_both_sides_up_to_other_nodes(self) -> None:
        doc = minidom.parseString("<p>a<b/>c</p>")
        p = doc.documentElement
        middle = p.lastChild
        p.appendChild(doc.createCDATASection("d"))
        p.appendChild(doc.createTextNode("e"))

        assert middle.wholeText == "cde"
        assert p.firstChild.wholeText == "a"

    def test_replace_whole_text_removes_the_run(self) -> None:
        doc = minidom.Document()
        element = self.run_of(doc, 5, "x")
        middle = element.childNodes[2]

        assert middle.replaceWholeText("new") is middle
        assert [child.data for child in element.childNodes] == ["new"]

    @pytest.mark.timing
    def test_append_data_copies_the_string(self) -> None:
        doc = minidom.Document()
        short = doc.createTextNode("x" * 10_000)
        long = doc.createTextNode("x" * 10_000_000)

        ratio = best_ns(lambda: long.appendData("y"), inner=3) / best_ns(
            lambda: short.appendData("y"), inner=3
        )
        assert ratio > 50, f"1,000x the text cost x{ratio:.1f} per append"

    def test_the_edits(self) -> None:
        text = minidom.Document().createTextNode("hello world")

        text.insertData(5, ",")
        text.replaceData(0, 5, "HELLO")
        text.deleteData(6, 1)
        text.appendData("!")

        assert text.data == "HELLO,world!"
        assert text.length == len(text) == 12
        assert text.substringData(6, 5) == "world"
        with pytest.raises(xml.dom.IndexSizeErr):
            text.substringData(50, 1)

    def test_split_text_inserts_the_tail_as_the_next_sibling(self) -> None:
        doc = minidom.parseString("<p>one two<b/></p>")
        text = doc.documentElement.firstChild

        tail = text.splitText(3)

        assert (text.data, tail.data) == ("one", " two")
        assert text.nextSibling is tail
        assert tail.nextSibling.tagName == "b"

    def test_create_text_node_keeps_the_string(self) -> None:
        value = "".join(["some ", "text"])

        assert minidom.Document().createTextNode(value).data is value


class CountingElemInfo:
    """Count the calls `getElementById()` makes to `Document._get_elem_info`."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls = 0
        original = typed_minidom.Document._get_elem_info  # type: ignore[attr-defined]

        def counting(document: Any, element: Any) -> Any:
            self.calls += 1
            return original(document, element)

        monkeypatch.setattr(typed_minidom.Document, "_get_elem_info", counting)

    def take(self) -> int:
        calls, self.calls = self.calls, 0
        return calls


class TestSearching:
    """`getElementsByTagName()` | O(s) | O(m + d); `getElementById()` |
    O(1) cached, O(s) to search; `setIdAttribute()` | O(d)."""

    def test_a_new_list_in_document_order(self) -> None:
        doc = minidom.parseString('<a><b n="1"/><c><b n="2"/></c><b n="3"/></a>')

        first = doc.getElementsByTagName("b")

        assert [node.getAttribute("n") for node in first] == ["1", "2", "3"]
        assert doc.getElementsByTagName("b") is not first
        assert len(doc.getElementsByTagName("*")) == 5
        assert len(doc.documentElement.childNodes[1].getElementsByTagName("b")) == 1

    def test_by_namespace(self) -> None:
        doc = minidom.parseString('<r xmlns:p="urn:p"><p:a/><a/><p:b/></r>')

        assert [n.tagName for n in doc.getElementsByTagNameNS("urn:p", "*")] == ["p:a", "p:b"]
        assert [n.tagName for n in doc.getElementsByTagNameNS("*", "a")] == ["p:a", "a"]

    def test_space_follows_the_matches(self) -> None:
        doc = minidom.parseString(records(20_000))
        doc.getElementsByTagName("none")
        doc.getElementsByTagName("item")

        none_peak = peak_bytes(lambda: doc.getElementsByTagName("none"))
        all_peak = peak_bytes(lambda: doc.getElementsByTagName("item"))

        assert none_peak < 10_000, f"no matches in 20,000 elements allocated {none_peak}"
        assert all_peak > 100_000, f"20,000 matches allocated only {all_peak}"

    @pytest.mark.timing
    def test_time_follows_the_tree(self) -> None:
        small = minidom.parseString(records(2_000))
        large = minidom.parseString(records(20_000))

        ratio = best_ns(lambda: large.getElementsByTagName("none"), repeats=5) / best_ns(
            lambda: small.getElementsByTagName("none"), repeats=5
        )
        assert ratio > 5, f"10x the tree cost x{ratio:.1f}"

    def test_a_non_id_declaration_is_enough_to_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = records(1_000).replace(
            "<root>", "<!DOCTYPE root [<!ATTLIST item id CDATA #IMPLIED>]><root>", 1
        )
        doc = minidom.parseString(text)
        counter = CountingElemInfo(monkeypatch)

        assert doc.getElementById("i5") is None
        assert counter.take() == 1_001

    def test_without_declarations_there_is_no_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        doc = minidom.parseString(records(1_000))
        counter = CountingElemInfo(monkeypatch)

        assert doc.getElementById("i5") is None
        assert counter.take() == 0

    def test_with_declarations_the_first_search_walks_and_caches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = records(1_000).replace(
            "<root>", "<!DOCTYPE root [<!ATTLIST item id ID #IMPLIED>]><root>", 1
        )
        doc = minidom.parseString(text)
        counter = CountingElemInfo(monkeypatch)

        found = doc.getElementById("i0")
        assert found is not None and found.firstChild.data == "text 0"
        assert counter.take() == 1_001, "root first, then the items in reverse"

        assert doc.getElementById("i0") is found
        assert doc.getElementById("i500") is not None
        assert counter.take() == 0, "every ID passed on the way was cached"

        doc.documentElement.appendChild(doc.createElement("item"))
        assert doc.getElementById("i0") is found
        assert counter.take() > 1_000, "the mutation cleared the cache"

    def test_set_id_attribute_makes_an_id(self) -> None:
        doc = minidom.parseString('<r><a key="x"/></r>')
        element = doc.documentElement.firstChild
        assert doc.getElementById("x") is None

        element.setIdAttribute("key")

        assert element.getAttributeNode("key").isId
        assert doc.getElementById("x") is element
        with pytest.raises(xml.dom.NotFoundErr):
            element.setIdAttribute("absent")

    @pytest.mark.timing
    def test_set_id_attribute_walks_to_the_root(self) -> None:
        doc, root, deep = TestChildListOperations.deep_node(5_000)
        for element in (root, deep):
            element.setAttribute("key", "v")

        shallow_ns = best_ns(lambda: root.setIdAttribute("key"), inner=20)
        deep_ns = best_ns(lambda: deep.setIdAttribute("key"), inner=20)

        ratio = deep_ns / shallow_ns
        assert ratio > 20, f"depth 5,000 cost x{ratio:.1f}"


class TestAttributes:
    """Attribute access through the element is O(1); `NamedNodeMap.item()` is
    O(a); `Element.attributes` is a new map each time."""

    @staticmethod
    def element_with(count: int) -> Any:
        attributes = " ".join(f'a{index}="{index}"' for index in range(count))
        return minidom.parseString(f"<e {attributes}/>").documentElement

    @pytest.mark.timing
    def test_item_lists_the_names_on_every_call(self) -> None:
        few = self.element_with(10).attributes
        many = self.element_with(10_000).attributes

        ratio = best_ns(lambda: many.item(5), inner=20) / best_ns(lambda: few.item(5), inner=20)
        assert ratio > 50, f"1,000x the attributes cost x{ratio:.1f} per item()"

    @pytest.mark.timing
    def test_element_methods_do_not_follow_the_attributes(self) -> None:
        def cycle(element: Any) -> Callable[[], Any]:
            def run() -> None:
                element.setAttribute("new", "v")
                element.getAttribute("a5")
                element.removeAttribute("new")

            return run

        few = best_ns(cycle(self.element_with(10)), inner=200)
        many = best_ns(cycle(self.element_with(10_000)), inner=200)

        ratio = many / few
        assert ratio < 3, f"1,000x the attributes cost x{ratio:.1f}"

    def test_attributes_is_a_new_view_of_the_same_dicts(self) -> None:
        element = self.element_with(3)

        first = element.attributes
        assert element.attributes is not first
        assert first == element.attributes
        element.setAttribute("late", "1")
        assert first.length == len(first) == 4
        assert first.getNamedItem("late").value == "1"

    def test_map_methods(self) -> None:
        element = self.element_with(3)
        attributes = element.attributes

        assert sorted(attributes.items()) == [("a0", "0"), ("a1", "1"), ("a2", "2")]
        assert attributes["a1"].value == "1"
        assert attributes.item(3) is None
        node = element.ownerDocument.createAttribute("x")
        node.value = "9"
        assert attributes.setNamedItem(node) is None
        assert element.getAttribute("x") == "9"
        assert attributes.removeNamedItem("x") is node
        with pytest.raises(xml.dom.NotFoundErr):
            attributes.removeNamedItem("x")

    def test_absent_and_owned_attributes(self) -> None:
        element = self.element_with(1)
        other = element.ownerDocument.createElement("other")

        assert element.getAttribute("absent") == ""
        assert element.getAttributeNode("absent") is None
        assert not element.hasAttribute("absent")
        with pytest.raises(xml.dom.NotFoundErr):
            element.removeAttribute("absent")
        with pytest.raises(xml.dom.InuseAttributeErr):
            other.setAttributeNode(element.getAttributeNode("a0"))

    def test_namespaced_attributes(self) -> None:
        element = minidom.parseString('<e xmlns:p="urn:p" p:k="v"/>').documentElement

        assert element.getAttributeNS("urn:p", "k") == "v"
        assert element.hasAttributeNS("urn:p", "k")
        element.setAttributeNS("urn:p", "p:j", "w")
        assert element.getAttributeNodeNS("urn:p", "j").prefix == "p"
        element.removeAttributeNS("urn:p", "j")
        assert not element.hasAttributeNS("urn:p", "j")
        assert element.attributes.getNamedItemNS("urn:p", "k").localName == "k"

    def test_set_attribute_node_returns_what_it_replaced(self) -> None:
        element = self.element_with(1)
        old = element.getAttributeNode("a0")
        new = element.ownerDocument.createAttribute("a0")
        new.value = "new"

        assert element.setAttributeNode(new) is old
        assert element.getAttribute("a0") == "new"
        assert new.ownerElement is element
        assert element.removeAttributeNode(new) is new
        assert not element.hasAttributes()


class TestCloningAndImporting:
    """`cloneNode()` and `importNode()` | O(s) deep, O(a) shallow."""

    def test_deep_and_shallow_clones(self) -> None:
        doc = minidom.parseString('<r k="v"><a>text</a></r>')
        root = doc.documentElement

        deep = root.cloneNode(True)
        shallow = root.cloneNode(False)

        assert deep.toxml() == root.toxml()
        assert deep.firstChild is not root.firstChild
        assert shallow.getAttribute("k") == "v"
        assert not shallow.hasChildNodes()
        assert doc.cloneNode(False) is None
        assert doc.cloneNode(True).documentElement.toxml() == root.toxml()

    def test_import_node_copies_into_the_other_document(self) -> None:
        source = minidom.parseString("<r><a>text</a></r>")
        target = minidom.parseString("<t/>")
        original = source.documentElement.firstChild

        copy = target.importNode(original, True)

        assert copy.ownerDocument is target
        assert copy.parentNode is None
        assert original.parentNode is source.documentElement
        assert copy.toxml() == "<a>text</a>"
        with pytest.raises(xml.dom.NotSupportedErr):
            target.importNode(source, True)

    def test_rename_node(self) -> None:
        doc = minidom.parseString('<r k="v"><a/></r>')
        element = doc.documentElement.firstChild
        attribute = doc.documentElement.getAttributeNode("k")

        assert doc.renameNode(element, None, "b") is element
        doc.renameNode(attribute, None, "j")

        assert doc.documentElement.toxml() == '<r j="v"><b/></r>'

    def test_renaming_a_marked_id_attribute_keeps_it_an_id(self) -> None:
        doc = minidom.parseString('<r><a k="v"/></r>')
        element = doc.documentElement.firstChild
        element.setIdAttribute("k")

        doc.renameNode(element.getAttributeNode("k"), None, "key")

        assert element.getAttributeNode("key").isId
        assert doc.getElementById("v") is element


class TestSerializing:
    """`toxml()` | O(n) | O(n); `writexml()` | O(n) | O(c + d)."""

    def test_writexml_streams_and_toxml_holds_the_output(self) -> None:
        element = minidom.parseString(records(10_000)).documentElement
        element.writexml(DiscardingSink())
        output = element.toxml()

        stream_peak = peak_bytes(lambda: element.writexml(DiscardingSink()))
        string_peak = peak_bytes(element.toxml)

        assert stream_peak < 10_000, f"writexml peaked at {stream_peak} bytes"
        assert string_peak > len(output), f"toxml peaked at {string_peak} for {len(output)}"

    def test_the_first_call_gives_bare_elements_their_attribute_dicts(self) -> None:
        doc = minidom.Document()
        root = doc.createElement("r")
        for _ in range(10_000):
            root.appendChild(doc.createElement("a"))

        first = peak_bytes(lambda: root.writexml(DiscardingSink()))
        second = peak_bytes(lambda: root.writexml(DiscardingSink()))

        assert first > 500_000, f"the first call over 10,000 bare elements allocated {first}"
        assert second < 10_000, f"the second call allocated {second}"
        assert root.firstChild._attrs == {}  # type: ignore[attr-defined]

    def test_the_output(self) -> None:
        doc = minidom.parseString('<r><a x="1">text &amp; more</a></r>')

        assert doc.documentElement.toxml() == '<r><a x="1">text &amp; more</a></r>'
        assert doc.toxml() == '<?xml version="1.0" ?><r><a x="1">text &amp; more</a></r>'
        assert doc.toxml(encoding="utf-8").startswith(b'<?xml version="1.0" encoding="utf-8"?>')
        assert doc.toprettyxml(indent="  ") == (
            '<?xml version="1.0" ?>\n<r>\n  <a x="1">text &amp; more</a>\n</r>\n'
        )

    def test_a_cdata_section_holding_its_end_marker_cannot_be_written(self) -> None:
        doc = minidom.parseString("<r/>")
        doc.documentElement.appendChild(doc.createCDATASection("a]]>b"))

        with pytest.raises(ValueError, match="]]>"):
            doc.toxml()

    def test_attribute_whitespace(self) -> None:
        doc = minidom.parseString("<r/>")
        doc.documentElement.setAttribute("a", "1\n2\t3\r4")

        output = doc.documentElement.toxml()

        if sys.version_info >= (3, 13):
            assert output == '<r a="1&#10;2&#9;3&#13;4"/>'
            reparsed = minidom.parseString(output).documentElement.getAttribute("a")
            assert reparsed == "1\n2\t3\r4"
        else:
            assert output == '<r a="1\n2\t3\r4"/>'


class TestDeepTrees:
    """Walking a parsed tree recurses once per level (`unlink()` twice);
    parsing, `getElementById()` and `expandNode()` do not."""

    DEPTH = 2 * sys.getrecursionlimit()

    def test_a_deep_chain_parses_and_the_walkers_raise(self) -> None:
        doc = minidom.parseString(chain(self.DEPTH))
        other = minidom.parseString("<t/>")
        walkers: dict[str, Callable[[], Any]] = {
            "getElementsByTagName": lambda: doc.getElementsByTagName("a"),
            "toxml": doc.toxml,
            "writexml": lambda: doc.writexml(DiscardingSink()),
            "cloneNode": lambda: doc.documentElement.cloneNode(True),
            "importNode": lambda: other.importNode(doc.documentElement, True),
            "normalize": doc.normalize,
        }

        survived = []
        for name, walk in walkers.items():
            try:
                walk()
            except RecursionError:
                continue
            survived.append(name)

        assert survived == []

    def test_get_element_by_id_does_not_recurse(self) -> None:
        text = "<!DOCTYPE a [<!ATTLIST a id ID #IMPLIED>]>" + chain(self.DEPTH).replace(
            "<a></a>", '<a id="bottom"></a>', 1
        )
        doc = minidom.parseString(text)

        found = doc.getElementById("bottom")

        assert found is not None and not found.hasChildNodes()

    def test_expand_node_does_not_recurse(self) -> None:
        events = pulldom.parseString(chain(self.DEPTH))
        event, node = next(events)
        while event != pulldom.START_ELEMENT:
            event, node = next(events)

        events.expandNode(node)

        depth = 1
        while node.firstChild is not None:
            node = node.firstChild
            depth += 1
        assert depth == self.DEPTH

    def test_unlink_fails_at_a_shallower_depth(self) -> None:
        depth = sys.getrecursionlimit() * 7 // 10
        doc = minidom.parseString(chain(depth))

        assert len(doc.getElementsByTagName("a")) == depth
        with pytest.raises(RecursionError):
            doc.unlink()


class TestUnlink:
    """`unlink()` and `with node:` break the subtree's links."""

    def test_unlink_breaks_parent_and_attribute_links(self) -> None:
        doc = minidom.parseString('<r><a k="v"/></r>')
        element = doc.documentElement.firstChild
        attribute = element.getAttributeNode("k")

        doc.unlink()

        assert element.parentNode is None
        assert not element.hasAttributes(), "the element no longer holds its attributes"
        assert not attribute.hasChildNodes()
        assert doc.documentElement is None

    @pytest.mark.parametrize("unlink", [True, False])
    def test_only_an_unlinked_tree_is_freed_without_the_collector(self, unlink: bool) -> None:
        doc = minidom.parseString('<r><a k="v">text</a></r>')
        element = weakref.ref(doc.documentElement.firstChild)
        attribute = weakref.ref(doc.documentElement.firstChild.getAttributeNode("k"))
        enabled = gc.isenabled()
        gc.disable()
        try:
            if unlink:
                doc.unlink()
            del doc
            freed = element() is None and attribute() is None
        finally:
            if enabled:
                gc.enable()

        assert freed is unlink
        gc.collect()
        assert element() is None and attribute() is None

    def test_a_with_block_unlinks_on_exit(self) -> None:
        with minidom.parseString("<r><a/></r>") as doc:
            element = doc.documentElement.firstChild
            assert element.parentNode is not None

        assert element.parentNode is None


class TestNavigation:
    """Links are stored; `childNodes` is the node's own list;
    `documentElement` scans only the document's own children."""

    def test_links_and_the_live_child_list(self) -> None:
        doc = minidom.parseString("<r><a/>text<b/></r>")
        root = doc.documentElement
        children = root.childNodes

        assert root.childNodes is children
        assert (root.firstChild, root.lastChild) == (children[0], children[2])
        assert children[1].previousSibling is children[0]
        assert children[1].nextSibling is children[2]
        assert children[0].parentNode is root and root.parentNode is doc
        assert children[1].ownerDocument is doc
        root.appendChild(doc.createElement("c"))
        assert children.length == len(children) == 4
        assert children.item(3).tagName == "c" and children.item(9) is None
        assert root.hasChildNodes() and not children[0].hasChildNodes()

    def test_node_properties(self) -> None:
        doc = minidom.parseString('<p:r xmlns:p="urn:p" k="v">t<!--c--><?pi d?></p:r>')
        root = doc.documentElement
        text, comment, pi = root.childNodes

        assert (root.nodeType, root.nodeName, root.nodeValue) == (1, "p:r", None)
        assert (root.localName, root.prefix, root.namespaceURI) == ("r", "p", "urn:p")
        assert (text.nodeType, text.nodeName, text.nodeValue) == (3, "#text", "t")
        assert (comment.nodeType, comment.data) == (8, "c")
        assert (pi.nodeType, pi.target, pi.data) == (7, "pi", "d")
        assert text.attributes is None and root.attributes.length == 2
        assert root.hasAttributes() and not hasattr(text, "hasAttributes")
        assert root.isSameNode(root) and not root.isSameNode(text)
        assert root.isSupported("xml", "1.0")

    def test_user_data(self) -> None:
        node = minidom.Document().createElement("e")

        assert node.getUserData("k") is None
        assert node.setUserData("k", 1, None) is None
        assert node.setUserData("k", 2, None) == 1
        assert node.getUserData("k") == 2

    @pytest.mark.timing
    def test_document_element_does_not_search_the_tree(self) -> None:
        small = minidom.parseString("<r><a/></r>")
        large = minidom.parseString("<r>" + "<a/>" * 100_000 + "</r>")

        ratio = best_ns(lambda: large.documentElement, inner=1_000) / best_ns(
            lambda: small.documentElement, inner=1_000
        )
        assert ratio < 3, f"a 100,000-child root cost x{ratio:.1f}"

    def test_document_properties(self) -> None:
        doc = minidom.parseString("<!--prolog--><r/>")

        assert doc.documentElement.tagName == "r"
        assert doc.doctype is None
        assert doc.documentURI is None
        assert doc.strictErrorChecking is False
        assert doc.implementation is minidom.getDOMImplementation()


class TestFactories:
    """`Document.create*()` | O(1): nodes owned by the document, not yet in the tree."""

    def test_created_nodes_are_owned_and_detached(self) -> None:
        doc = minidom.parseString("<r/>")
        nodes = [
            doc.createElement("e"),
            doc.createElementNS("urn:x", "x:e"),
            doc.createTextNode("t"),
            doc.createComment("c"),
            doc.createCDATASection("d"),
            doc.createProcessingInstruction("pi", "data"),
            doc.createAttribute("a"),
            doc.createAttributeNS("urn:x", "x:a"),
            doc.createDocumentFragment(),
        ]

        assert all(node.ownerDocument is doc for node in nodes)
        assert all(node.parentNode is None for node in nodes)
        assert not doc.documentElement.hasChildNodes()
        assert nodes[1].localName == "e" and nodes[7].prefix == "x"


class TestDocumentType:
    """`DocumentType` attributes are O(1); a lookup by name in `entities` or
    `notations` is a linear scan, O(x)."""

    SUBSET = '<!ENTITY e "v"><!NOTATION n SYSTEM "urn:n">'

    def test_the_declarations(self) -> None:
        doc = minidom.parseString(f'<!DOCTYPE r PUBLIC "-//P//EN" "r.dtd" [{self.SUBSET}]><r/>')
        doctype = doc.doctype

        assert doctype is not None
        assert (doctype.name, doctype.publicId, doctype.systemId) == ("r", "-//P//EN", "r.dtd")
        assert doctype.internalSubset == self.SUBSET
        entity = doctype.entities.getNamedItem("e")
        assert entity is doctype.entities.item(0)
        assert (entity.publicId, entity.systemId, entity.notationName) == (None, None, None)
        notation = doctype.notations.getNamedItem("n")
        assert (notation.publicId, notation.systemId) == (None, "urn:n")

    @pytest.mark.timing
    def test_a_lookup_by_name_scans_the_declarations(self) -> None:
        def doctype_with(count: int) -> Any:
            entities = "".join(f'<!ENTITY e{index} "v">' for index in range(count))
            doctype = minidom.parseString(f"<!DOCTYPE r [{entities}]><r/>").doctype
            assert doctype is not None
            return doctype.entities

        few, many = doctype_with(10), doctype_with(10_000)

        ratio = best_ns(lambda: many.getNamedItem("e9999"), inner=5) / best_ns(
            lambda: few.getNamedItem("e9"), inner=5
        )
        assert ratio > 50, f"1,000x the entities cost x{ratio:.1f} per lookup"


class TestImplementationAndRegistry:
    """`getDOMImplementation()`, `registerDOMImplementation()` and the
    `DOMImplementation` methods are O(1)."""

    def test_minidom_is_the_shared_implementation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from xml.dom import domreg

        monkeypatch.delenv("PYTHON_DOM", raising=False)
        assert not domreg.registered
        implementation = xml.dom.getDOMImplementation()

        assert implementation is minidom.getDOMImplementation()
        assert xml.dom.getDOMImplementation("minidom") is implementation
        assert implementation.hasFeature("core", "2.0")
        assert not implementation.hasFeature("events", "2.0")

    def test_create_document_makes_the_root(self) -> None:
        implementation = minidom.getDOMImplementation()
        doctype = implementation.createDocumentType("r", None, "r.dtd")

        doc = implementation.createDocument(None, "r", doctype)

        assert doc.documentElement.tagName == "r"
        assert doc.doctype is doctype and doctype.ownerDocument is doc
        assert doc.toxml() == "<?xml version=\"1.0\" ?><!DOCTYPE r  SYSTEM 'r.dtd'><r/>"

    def test_register_adds_one_entry(self) -> None:
        from xml.dom import domreg

        assert "test-dom" not in domreg.registered
        sentinel: Any = object()
        try:
            xml.dom.registerDOMImplementation("test-dom", lambda: sentinel)
            assert xml.dom.getDOMImplementation("test-dom") is sentinel
        finally:
            domreg.registered.pop("test-dom", None)


class TestConstantsAndExceptions:
    """Node types 1 to 12, error codes 1 to 16, one exception class per code."""

    NODE_TYPES = [
        "ELEMENT_NODE",
        "ATTRIBUTE_NODE",
        "TEXT_NODE",
        "CDATA_SECTION_NODE",
        "ENTITY_REFERENCE_NODE",
        "ENTITY_NODE",
        "PROCESSING_INSTRUCTION_NODE",
        "COMMENT_NODE",
        "DOCUMENT_NODE",
        "DOCUMENT_TYPE_NODE",
        "DOCUMENT_FRAGMENT_NODE",
        "NOTATION_NODE",
    ]
    ERRORS = [
        ("INDEX_SIZE_ERR", "IndexSizeErr"),
        ("DOMSTRING_SIZE_ERR", "DomstringSizeErr"),
        ("HIERARCHY_REQUEST_ERR", "HierarchyRequestErr"),
        ("WRONG_DOCUMENT_ERR", "WrongDocumentErr"),
        ("INVALID_CHARACTER_ERR", "InvalidCharacterErr"),
        ("NO_DATA_ALLOWED_ERR", "NoDataAllowedErr"),
        ("NO_MODIFICATION_ALLOWED_ERR", "NoModificationAllowedErr"),
        ("NOT_FOUND_ERR", "NotFoundErr"),
        ("NOT_SUPPORTED_ERR", "NotSupportedErr"),
        ("INUSE_ATTRIBUTE_ERR", "InuseAttributeErr"),
        ("INVALID_STATE_ERR", "InvalidStateErr"),
        ("SYNTAX_ERR", "SyntaxErr"),
        ("INVALID_MODIFICATION_ERR", "InvalidModificationErr"),
        ("NAMESPACE_ERR", "NamespaceErr"),
        ("INVALID_ACCESS_ERR", "InvalidAccessErr"),
        ("VALIDATION_ERR", "ValidationErr"),
    ]

    def test_node_types(self) -> None:
        values = [getattr(xml.dom.Node, name) for name in self.NODE_TYPES]

        assert values == list(range(1, 13))
        assert minidom.Node.TEXT_NODE == xml.dom.Node.TEXT_NODE

    def test_error_codes_and_classes(self) -> None:
        for expected, (constant, name) in enumerate(self.ERRORS, start=1):
            error = getattr(xml.dom, name)
            assert getattr(xml.dom, constant) == expected
            assert error.code == expected
            assert issubclass(error, xml.dom.DOMException)
            assert error("message").code == expected

    def test_dom_exception_cannot_be_raised_directly(self) -> None:
        with pytest.raises(RuntimeError, match="instantiated directly"):
            xml.dom.DOMException()

    def test_namespaces(self) -> None:
        assert xml.dom.XML_NAMESPACE == "http://www.w3.org/XML/1998/namespace"
        assert xml.dom.XMLNS_NAMESPACE == "http://www.w3.org/2000/xmlns/"
        assert xml.dom.XHTML_NAMESPACE == "http://www.w3.org/1999/xhtml"
        assert xml.dom.EMPTY_NAMESPACE is None

    def test_pulldom_event_names(self) -> None:
        names = [
            "START_ELEMENT",
            "END_ELEMENT",
            "CHARACTERS",
            "START_DOCUMENT",
            "END_DOCUMENT",
            "COMMENT",
            "PROCESSING_INSTRUCTION",
            "IGNORABLE_WHITESPACE",
        ]

        assert [getattr(pulldom, name) for name in names] == names


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
        line, source = next((n, s) for n, s in _blocks() if "len(errors) == 333" in s)
        mutated = source.replace("len(errors) == 333", "len(errors) == 334", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
