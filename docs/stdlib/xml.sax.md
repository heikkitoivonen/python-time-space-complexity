# xml.sax Module Complexity

The `xml.sax` module parses XML by calling back into your code. The parser walks the document once
and reports each start tag, text run and end tag as it reaches it, and builds no tree on the way:
what survives the document is what your handler kept, next to the parser's own working set. That
is the trade against `xml.etree.ElementTree`, which in its ordinary use builds the whole tree
before you can ask it anything.

The unit of work is the event and the unit of input is the buffer: the reader pulls its source in
fixed-size chunks and feeds them to Expat, which reports the events those chunks complete - not
always in the call that completes one, since an unfinished piece is held over. Three things the
parser holds of the document itself. The first is the piece it has to deliver whole - a whole
start tag with its attributes, an entity's replacement text - which it buffers until it is
complete. The second is the scope open around the current element: the names of the elements
enclosing it, and the namespace URIs declared on them, so a deeply nested document costs its
depth even when every tag in it is short. The third is a pool of the distinct names it has met,
so two documents of one size cost differently when one names everything differently.

`n` is the characters in the document, `e` its elements and `a` the attributes on one element.
`c` is the characters in the strings one event or call carries: a text run, a name, an attribute
value, the data handed to a `saxutils` function, or what one `XMLGenerator` call writes. `t` is
the longest piece the parser must deliver whole, `d` the characters the open scope holds - the
names of the elements open at one point, and the namespace URIs declared on them - and `v` the
characters in the distinct element and attribute names the parser has met, which in namespace
mode are the expanded ones. `u` is the characters in a namespace URI, which namespace mode writes
into every name it reports, elements and attributes alike. `p` is the namespace prefix mappings
open at one point, `f` the filters in a chain, and `r` the pairs in an `entities` mapping.

Two things sit outside the parse bounds below: the declarations of an internal DTD subset, which
a document that has one holds for the whole parse, and the source identifier, of which the parser
keeps a copy - the `prepareParser()` row prices that one. A parse bound prices the parser only:
every event also costs whatever the handler does with it, once per event.

## Complexity Reference

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.parse(source, handler, errorHandler=ErrorHandler())` | O(n), plus O(u) per name reported in namespace mode | O(t + d + v) | Builds a parser, then streams the source in chunks of just under 64 KiB; `source` may be a filename, a path, an open binary or text stream, or an `InputSource`. The second term is the URI the driver writes into each element and attribute name it reports, from one declaration in the document. The event being delivered is live on top of the space bound, which the `ContentHandler` rows price |
| `xml.sax.parseString(string, handler, errorHandler=None)` | O(n), as `parse()`, namespace term and all | O(n) for `str`, O(t + d + v) for `bytes` | A `str` is copied into an `io.StringIO`; a `bytes` object is wrapped in an `io.BytesIO`, which shares it rather than copying. A mutable buffer is copied like a `str` |
| `xml.sax.make_parser(parser_list=())` | O(m) | O(m) | m = the names in `parser_list` and the defaults, which are joined into one list before any is tried; the first import of a driver costs the module, later calls find it in `sys.modules`, and the parser object holds four default handlers |
| `xml.sax.default_parser_list` | O(1) | O(1) | The drivers `make_parser()` falls back to, `xml.sax.expatreader` alone unless `PY_SAX_PARSER` overrides it |
| `xml.sax.handler`, `xml.sax.saxutils`, `xml.sax.xmlreader` | O(1) | O(1) | `handler` and `xmlreader` are bound when `xml.sax` is; `saxutils` is not, until it is imported by you or by a parse, and it brings `urllib.request` with it - that is what opens a system identifier |

### ContentHandler

Each row prices the event: what the driver builds before the call plus what the base method does,
which is nothing except in `setDocumentLocator()`, where it stores the locator. What an override
does inside the call is yours, and it is paid once per event.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.ContentHandler()` | O(1) | O(1) | Holds one attribute, the locator the parser sets |
| `ContentHandler.setDocumentLocator(locator)` | O(1) | O(1) | Called once, before any other event |
| `ContentHandler.startDocument()`, `ContentHandler.endDocument()` | O(1) | O(1) | One call each per parse |
| `ContentHandler.startElement(name, attrs)` | O(a + c) | O(a + c) | Once per element; the attribute dictionary and the strings in it are built before the call, and `attrs` shares that dictionary rather than copying it |
| `ContentHandler.endElement(name)` | O(c) | O(c) | Once per element; the name is built for the call |
| `ContentHandler.startElementNS(name, qname, attrs)` | O(a + c) | O(a + c) | Namespace mode: the driver splits the element name and builds a name and a qname mapping per element before calling, and c counts the namespace URI carried in every name it reports |
| `ContentHandler.endElementNS(name, qname)` | O(c) | O(c) | Namespace mode; the name arrives as a `(uri, localname)` pair, built for the call |
| `ContentHandler.startPrefixMapping(prefix, uri)`, `ContentHandler.endPrefixMapping(prefix)` | O(c) | O(c) | One pair per namespace declaration; the prefix and the URI are built for the call |
| `ContentHandler.characters(content)` | O(c) | O(c) | One text run can arrive as several calls, and one call can be far larger than the read buffer when an entity's replacement text brings it; a handler that needs a run whole must join the pieces |
| `ContentHandler.ignorableWhitespace(whitespace)` | O(1) | O(1) | The Expat driver never calls it, so nothing is built for it: whitespace between elements arrives through `characters()` |
| `ContentHandler.processingInstruction(target, data)` | O(c) | O(c) | |
| `ContentHandler.skippedEntity(name)` | O(c) | O(c) | Reported for a reference the parser cannot resolve because it did not read the external subset that would declare it |

### ErrorHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.ErrorHandler()` | O(1) | O(1) | The default for `parse()` and `parseString()` |
| `ErrorHandler.error(exception)`, `ErrorHandler.fatalError(exception)` | O(1) | O(1) | Both raise the exception, which ends the parse where the fault is |
| `ErrorHandler.warning(exception)` | O(c) | O(c) | Prints the exception and returns, so it stops nothing; the Expat driver never calls it |

### DTDHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.handler.DTDHandler()` | O(1) | O(1) | |
| `DTDHandler.notationDecl(name, publicId, systemId)` | O(c) | O(c) | One call per notation declaration; its three strings are built for the call |
| `DTDHandler.unparsedEntityDecl(name, publicId, systemId, ndata)` | O(c) | O(c) | One call per unparsed entity declaration; its four strings are built for the call |

### EntityResolver

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.handler.EntityResolver()` | O(1) | O(1) | |
| `EntityResolver.resolveEntity(publicId, systemId)` | O(c) | O(c) | Returns the system identifier unchanged; reached only when `feature_external_ges` is on, and then the parser reads what it names. With the feature off an external reference is passed over |

### LexicalHandler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.handler.LexicalHandler()` | O(1) | O(1) | Python 3.10+; install it with `setProperty(property_lexical_handler, ...)` |
| `LexicalHandler.comment(content)` | O(c) | O(c) | The comment text is built for the call |
| `LexicalHandler.startDTD(name, public_id, system_id)` | O(c) | O(c) | Its three strings are built for the call |
| `LexicalHandler.endDTD()` | O(1) | O(1) | |
| `LexicalHandler.startCDATA()`, `LexicalHandler.endCDATA()` | O(1) | O(1) | Section markers only; the text inside arrives through `characters()` |

### Features and properties

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.handler.feature_namespaces` | O(1) | O(1) | Off by default; turning it on moves elements to the `*NS` callbacks, where the driver splits every name it reports |
| `xml.sax.handler.feature_namespace_prefixes`, `xml.sax.handler.feature_validation`, `xml.sax.handler.feature_external_pes` | O(1) | O(1) | Reading the name is a string attribute; the Expat driver raises `SAXNotSupportedException` when asked to turn any of them on |
| `xml.sax.handler.feature_string_interning` | O(1) | O(1) | The names reported to `startElement()` then share one string object each, so a handler that keeps the names it is given keeps one per distinct name rather than one per element; the parser keeps that dictionary as well as its own pool. It does not reach namespace mode, where the driver splits the expanded name into a fresh pair per element |
| `xml.sax.handler.feature_external_ges` | O(1) | O(1) | Off by default; on, an external entity reference is read - from the filesystem or the network - before parsing continues |
| `xml.sax.handler.all_features`, `xml.sax.handler.all_properties` | O(1) | O(1) | Module-level lists of the six feature and six property names |
| `xml.sax.handler.property_lexical_handler`, `xml.sax.handler.property_declaration_handler`, `xml.sax.handler.property_dom_node`, `xml.sax.handler.property_xml_string`, `xml.sax.handler.property_encoding`, `xml.sax.handler.property_interning_dict` | O(1) | O(1) | Property names; the Expat driver recognises the lexical handler, the interning dictionary and the XML string, and raises `SAXNotRecognizedException` for the rest |

### XMLReader

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.xmlreader.XMLReader()` | O(1) | O(1) | Installs a default content, DTD, entity and error handler |
| `XMLReader.parse(source)` | O(n), as `parse()` | O(t + d + v) | The driver's parse; the base class raises `NotImplementedError`. A document with an internal DTD subset also holds what that subset declares, for the whole parse |
| `XMLReader.setContentHandler(handler)`, `XMLReader.getContentHandler()` | O(1) | O(1) | The Expat driver accepts a new content handler during a parse |
| `XMLReader.setDTDHandler(handler)`, `XMLReader.getDTDHandler()` | O(1) | O(1) | |
| `XMLReader.setEntityResolver(resolver)`, `XMLReader.getEntityResolver()` | O(1) | O(1) | |
| `XMLReader.setErrorHandler(handler)`, `XMLReader.getErrorHandler()` | O(1) | O(1) | |
| `XMLReader.getFeature(name)`, `XMLReader.setFeature(name, state)` | O(1) | O(1) | Compared against a fixed set of names; unknown ones raise `SAXNotRecognizedException`, and setting one during a parse raises `SAXNotSupportedException` |
| `XMLReader.getProperty(name)`, `XMLReader.setProperty(name, value)` | O(1) | O(1) | Same fixed set. `property_xml_string` is the exception: it returns the input context - the buffer from the current event on - so it costs the bytes it hands back, and it answers only during a parse |
| `XMLReader.setLocale(locale)` | O(1) | O(1) | Raises `SAXNotSupportedException`: no locale support |

### IncrementalParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.xmlreader.IncrementalParser(bufsize=2**16)` | O(1) | O(1) | `make_parser()` returns one, so `feed()` is available on the parser `parse()` uses |
| `IncrementalParser.parse(source)` | O(n), as `parse()` | O(t + d + v) | Reads `bufsize` characters or bytes at a time and feeds each chunk |
| `IncrementalParser.feed(data)` | O(len(data)) amortized, with the namespace term `parse()` carries | O(t + d + v) | Events are reported for whatever the chunk completes. One call is not bounded by its own length: a held-over piece is paid for by the call that delivers it, which may be a later `feed()` or the `close()` |
| `IncrementalParser.close()` | O(t + d + v) | O(t) | Finishes the piece still pending and pays for its event, reports `endDocument`, closes the source, and releases the parser's state - the names it met and anything it left open included |
| `IncrementalParser.reset()` | O(1), or O(d + v) over a parser that read without closing | O(1) | Builds a fresh Expat parser and releases the one before it, with the names it met and the elements it left open - after a `close()` that state is already gone. The interface asks for a reset between documents; the Expat driver's `feed()` also does it for you once a parse has finished |
| `IncrementalParser.prepareParser(source)` | O(c) | O(c) | Hands the system identifier to the driver, which copies it into Expat as the base for relative references, and keeps it for the parse |

### Locator

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.xmlreader.Locator.getLineNumber()`, `xml.sax.xmlreader.Locator.getColumnNumber()` | O(1) | O(1) | Read through a weak reference to the running parser, so they answer inside a callback and raise `ReferenceError` once that parser is gone |
| `xml.sax.xmlreader.Locator.getPublicId()`, `xml.sax.xmlreader.Locator.getSystemId()` | O(1) | O(1) | Taken from the input source; the base class answers `-1` and `None` throughout |

### InputSource

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.xmlreader.InputSource(system_id=None)` | O(1) | O(1) | Holds five attributes and opens nothing |
| `InputSource.setSystemId(system_id)`, `InputSource.getSystemId()` | O(1) | O(1) | |
| `InputSource.setPublicId(public_id)`, `InputSource.getPublicId()` | O(1) | O(1) | |
| `InputSource.setEncoding(encoding)`, `InputSource.getEncoding()` | O(1) | O(1) | Ignored when a character stream is set |
| `InputSource.setByteStream(bytefile)`, `InputSource.getByteStream()` | O(1) | O(1) | The stream object itself, not a copy |
| `InputSource.setCharacterStream(charfile)`, `InputSource.getCharacterStream()` | O(1) | O(1) | Takes precedence over the byte stream |

### AttributesImpl

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.xmlreader.AttributesImpl(attrs)` | O(1) | O(1) | Wraps the mapping it is given without copying it |
| `AttributesImpl.getLength()`, `len(attrs)` | O(1) | O(1) | |
| `AttributesImpl.getValue(name)`, `attrs[name]`, `AttributesImpl.get(name, alternative=None)`, `name in attrs` | O(1) | O(1) | Dictionary lookups |
| `AttributesImpl.getValueByQName(name)`, `AttributesImpl.getNameByQName(name)`, `AttributesImpl.getQNameByName(name)` | O(1) | O(1) | Without namespaces a qualified name is the name |
| `AttributesImpl.getType(name)` | O(1) | O(1) | Always `'CDATA'` |
| `AttributesImpl.getNames()`, `AttributesImpl.getQNames()`, `AttributesImpl.keys()`, `AttributesImpl.items()`, `AttributesImpl.values()` | O(a) | O(a) | Each call builds a new list, so call it once rather than per lookup |
| `AttributesImpl.copy()` | O(1) | O(1) | A new wrapper over the same mapping; to keep attributes past the callback, build a `dict` from `items()` |

### AttributesNSImpl

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.xmlreader.AttributesNSImpl(attrs, qnames)` | O(1) | O(1) | Wraps both mappings, keyed by `(uri, localname)` pairs |
| `AttributesNSImpl.getValueByQName(name)`, `AttributesNSImpl.getNameByQName(name)` | O(a) | O(1) | a string comparisons against the qualified names rather than a lookup; look up by `(uri, localname)` instead where you can |
| `AttributesNSImpl.getQNameByName(name)` | O(1) | O(1) | Dictionary lookup, the direction the mapping is keyed in |
| `AttributesNSImpl.getQNames()` | O(a) | O(a) | Builds a new list |
| `AttributesNSImpl.copy()` | O(1) | O(1) | A new wrapper over the same two mappings |

### XMLGenerator

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.saxutils.XMLGenerator(out=None, encoding='iso-8859-1', short_empty_elements=False)` | O(1) | O(1) | Wraps `out` in a text writer; `None` means `sys.stdout` |
| `XMLGenerator.startElement(name, attrs)` | O(c) | O(c) | c counts everything the tag writes: the name, and every attribute name and quoted value |
| `XMLGenerator.endElement(name)` | O(c) | O(c) | |
| `XMLGenerator.startElementNS(name, qname, attrs)` | O(c) | O(c) | Also writes the declarations opened since the last start tag, and maps each name through the prefix in scope with one lookup |
| `XMLGenerator.endElementNS(name, qname)` | O(c) | O(c) | |
| `XMLGenerator.startPrefixMapping(prefix, uri)` | O(p) | O(p) | Snapshots the prefixes in scope, so p mappings open at once cost O(p²) |
| `XMLGenerator.endPrefixMapping(prefix)` | O(p) | O(1) | Pops the snapshot and releases the map it replaces, which is the p prefixes in scope |
| `XMLGenerator.characters(content)` | O(c) | O(c) | Escapes `&`, `<` and `>` |
| `XMLGenerator.ignorableWhitespace(content)` | O(c) | O(c) | Written through unescaped |
| `XMLGenerator.processingInstruction(target, data)` | O(c) | O(c) | |
| `XMLGenerator.startDocument()` | O(1) | O(1) | Writes the XML declaration |
| `XMLGenerator.endDocument()` | O(1) | O(1) | Flushes the writer |

### XMLFilterBase

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.saxutils.XMLFilterBase(parent=None)` | O(1) | O(1) | An `XMLReader` that forwards to handlers and delegates to a parent reader |
| `XMLFilterBase.parse(source)` | `parse()`, plus O(f) per event | O(t + d + v + f) | Registers itself on the parent; each of f filters adds one call per event, and the chain is f frames deep while an event passes through it |
| Forwarding an event through a filter | O(1) | O(1) | One method call per filter per event |
| `XMLFilterBase.setParent(parent)`, `XMLFilterBase.getParent()` | O(1) | O(1) | |

### saxutils functions

In these four rows c is the longest intermediate string, which a replacement longer than its key
makes longer than the input.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.saxutils.escape(data, entities={})` | O(c·(1 + r)) | O(c) | Three passes for `&`, `>` and `<`, then one per entity; `&` is replaced first, so the entity pairs see escaped text |
| `xml.sax.saxutils.unescape(data, entities={})` | O(c·(1 + r)) | O(c) | The inverse order: `&amp;` is replaced last |
| `xml.sax.saxutils.quoteattr(data, entities={})` | O(c·(1 + r)) | O(c + r) | `escape()` plus tab, newline and return, then one scan to choose the quote character; the mapping is copied to add those three, whether or not any pair is given |
| `xml.sax.saxutils.prepare_input_source(source, base='')` | O(1) for a stream, O(c) plus one open for a name | O(1) for a stream, O(c) for a name | Wrapping a stream is attribute work and reads nothing but a type probe; a name is normalised and joined against `base`, which costs their characters, and then opened - from the filesystem, or through `urllib.request` and its round trip when it is not a local file |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.sax.SAXException(msg, exception=None)` | O(1) | O(1) | |
| `SAXException.getMessage()`, `SAXException.getException()` | O(1) | O(1) | The stored message and wrapped exception |
| `xml.sax.SAXParseException(msg, exception, locator)` | O(1) | O(1) | Copies the system id, line and column out of the locator at construction, because the locator moves on |
| `SAXParseException.getLineNumber()`, `SAXParseException.getColumnNumber()`, `SAXParseException.getSystemId()` | O(1) | O(1) | The values cached at construction |
| `SAXParseException.getPublicId()` | O(1) | O(1) | Asked of the locator on each call, not cached |
| `str(exception)` | O(c) | O(c) | Builds `systemId:line:column: message` |
| `xml.sax.SAXNotRecognizedException(msg, exception=None)` | O(1) | O(1) | An unknown feature or property name |
| `xml.sax.SAXNotSupportedException(msg, exception=None)` | O(1) | O(1) | A known name the driver cannot honour |
| `xml.sax.SAXReaderNotAvailable(msg, exception=None)` | O(1) | O(1) | Raised by `make_parser()` when no driver can be built |

## Streaming a Document

`parse()` never holds the document. It pulls the source in fixed-size chunks and feeds each one to
Expat, so the read count follows the size of the input while the memory follows the three terms
below instead.

```python
import io
import xml.sax


class Counter(xml.sax.ContentHandler):
    def __init__(self):
        self.elements = 0

    def startElement(self, name, attrs):  # O(1) of handler work per element
        self.elements += 1


class CountingSource(io.BytesIO):
    """A byte stream that records how many times it was read."""

    reads = 0

    def read(self, size=-1):
        self.reads += 1
        return super().read(size)


document = b"<root>" + b"<item/>" * 20_000 + b"</root>"
source = CountingSource(document)
counter = Counter()

xml.sax.parse(source, counter)  # O(n), one pass

assert counter.elements == 20_001
assert 3 <= source.reads <= 6  # a handful of buffer-sized reads, not one gulp
```

### What the Parser Must Hold

Peak memory follows three things, and the document is none of them. The first is the longest piece
the parser cannot split. Text is splittable: a run arrives as however many `characters()` calls the
chunking produces. An attribute value is not, so the parser buffers it whole before it can report
the start tag. Neither is the text an entity brings in, which is why a single `characters()` call
can be far larger than the read buffer - it is the markup, the references and the line breaks
inside a replacement that split it, not the buffer.

```python
import io
import tracemalloc
import xml.sax

text_node = b"<root>" + b"y" * 2_000_000 + b"</root>"
attribute = b'<root a="' + b"z" * 2_000_000 + b'"/>'


class Pieces(xml.sax.ContentHandler):
    def __init__(self):
        self.calls = 0

    def characters(self, content):  # O(c) per call, several per run
        self.calls += 1


def peak(document):
    tracemalloc.start()
    try:
        xml.sax.parse(io.BytesIO(document), xml.sax.ContentHandler())
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


pieces = Pieces()
xml.sax.parse(io.BytesIO(text_node), pieces)
assert pieces.calls > 1  # one run, many calls: a handler that needs it whole must join them

assert peak(text_node) < 1_000_000  # O(t): the run is split, so nothing large is held
assert peak(attribute) > 2_000_000  # O(t): the value is one piece and is held whole
```

The second term is the scope, counted in the characters it holds open: the names of the enclosing
elements, and in namespace mode the URIs declared on them, one copy per declaration whether or
not two of them say the same thing. So two documents of the same size peak far apart when one of
them nests and the other does not.

```python
import io
import tracemalloc
import xml.sax

flat = b"<root>" + b"<a/>" * 87_500 + b"</root>"
deep = b"<a>" * 50_000 + b"</a>" * 50_000
assert abs(len(flat) - len(deep)) < 20  # the same bytes, a different shape


def peak(document):
    tracemalloc.start()
    try:
        xml.sax.parse(io.BytesIO(document), xml.sax.ContentHandler())
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


xml.sax.parse(io.BytesIO(b"<root/>"), xml.sax.ContentHandler())  # warm the imports

assert peak(deep) > peak(flat) * 4  # the d term: 50,000 open elements, none of them large
```

The third is the vocabulary. Names go into a pool the parser keeps for the parse, so a document
that names every element differently costs that variety, while one that repeats a handful of tags
pays for them once.

### parse() Against parseString()

`parseString()` is the same parse over a stream it builds for you, and how it builds it decides
what the call costs: a `str` is copied into an `io.StringIO`, while `bytes` are handed to an
`io.BytesIO`, which shares the caller's buffer instead of copying it.

```python
import tracemalloc
import xml.sax

text = "<root>" + "<item/>" * 100_000 + "</root>"


def peak(document):
    tracemalloc.start()
    try:
        xml.sax.parseString(document, xml.sax.ContentHandler())
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


xml.sax.parseString(b"<root/>", xml.sax.ContentHandler())  # warm the imports

assert peak(text) > len(text)  # O(n): str is copied into a text stream
assert peak(text.encode()) < len(text) // 2  # O(t): bytes are wrapped, not copied
assert peak(bytearray(text.encode())) > len(text)  # a mutable buffer is copied like a str
```

### Feeding a Parser by Hand

A parser from `make_parser()` is an `IncrementalParser`, so a document that arrives in pieces -
from a socket, a pipe, a decompressor - can be pushed in as it comes. `feed()` reports whatever
each chunk completes, `close()` finishes what is still pending, and `reset()` prepares the parser
for another document. The work over the whole parse is what `parse()` would have cost, but it is
not spread evenly: whichever call delivers a large attribute value pays for it, and a piece still
unfinished at the end is paid for by `close()`, which also releases the names the parse met.

```python
import xml.sax


class Names(xml.sax.ContentHandler):
    def __init__(self):
        self.names = []

    def startElement(self, name, attrs):
        self.names.append(name)


parser = xml.sax.make_parser()  # O(1) after the driver is imported
names = Names()
parser.setContentHandler(names)  # O(1)

chunks = ["<root><it", "em/><item", "/></root>"]
for chunk in chunks:
    parser.feed(chunk)  # O(len(chunk)) amortized; a split tag waits for the rest
parser.close()  # O(t + d + v)

assert names.names == ["root", "item", "item"]

parser.reset()  # O(1) here: close() already let the last parser's state go
parser.setContentHandler(Names())
parser.feed("<other/>")
parser.close()
```

## Reading Attributes

The `attrs` object a start tag brings is a wrapper over the parser's dictionary, so lookups by
name are dictionary lookups. The listing methods are not: each builds a new list, so take one and
reuse it rather than calling `keys()` inside a loop.

```python
import xml.sax


class Attributes(xml.sax.ContentHandler):
    def __init__(self):
        self.rows = []

    def startElement(self, name, attrs):
        if name == "item":
            value = attrs.getValue("id")  # O(1)
            assert attrs["id"] == value  # O(1), the same lookup
            assert attrs.get("missing", "?") == "?"  # O(1)
            assert attrs.getType("id") == "CDATA"  # O(1), always
            assert attrs.getLength() == len(attrs.items())  # O(a) to list
            self.rows.append(dict(attrs.items()))  # O(a), and valid after the call


rows = Attributes()
xml.sax.parseString(b'<root><item id="1" tag="x"/><item id="2" tag="y"/></root>', rows)

assert rows.rows == [{"id": "1", "tag": "x"}, {"id": "2", "tag": "y"}]
```

### Namespaces

With `feature_namespaces` on, elements arrive through `startElementNS()` as `(uri, localname)`
pairs and the driver splits every name it reports, which is per-attribute work on top of the
parse. The URI is not free either: it is materialised into every name reported from that
namespace, so a long URI declared once is paid for at every element and attribute that uses it.
Interning does not rescue this - the driver splits the expanded name itself, so each pair it
builds is a fresh URI object whatever the feature is set to. The attribute object changes with
the mode: looking up a `(uri, localname)` key stays a dictionary lookup, but `getValueByQName()`
and `getNameByQName()` scan the qualified names one by one.

```python
import io
import xml.sax
from xml.sax.handler import feature_namespaces
from xml.sax.xmlreader import AttributesNSImpl


class Namespaced(xml.sax.ContentHandler):
    def __init__(self):
        self.seen = []

    def startElementNS(self, name, qname, attrs):  # O(a + c) built before the call
        if name[1] == "item":
            self.seen.append((name, attrs.getValue(("urn:d", "id"))))  # O(1)


parser = xml.sax.make_parser()
parser.setFeature(feature_namespaces, True)  # O(1)
handler = Namespaced()
parser.setContentHandler(handler)
parser.parse(io.BytesIO(b'<r xmlns:d="urn:d"><d:item d:id="1">text</d:item></r>'))  # O(n)

assert handler.seen == [(("urn:d", "item"), "1")]

attributes = AttributesNSImpl({("urn:d", "id"): "1"}, {("urn:d", "id"): "d:id"})
assert attributes.getQNameByName(("urn:d", "id")) == "d:id"  # O(1)
assert attributes.getValueByQName("d:id") == "1"  # O(a), a scan of the qualified names
assert attributes.getNameByQName("d:id") == ("urn:d", "id")  # O(a), the same scan
```

### Sharing Repeated Names

`feature_string_interning` hands Expat a dictionary to intern names through, so the name handed
to each `startElement()` call is the same object every time that tag appears. A handler that
keeps its names then keeps one per distinct name instead of one per element.

```python
import io
import xml.sax
from xml.sax.handler import feature_string_interning


class Names(xml.sax.ContentHandler):
    def __init__(self):
        self.names = []

    def startElement(self, name, attrs):
        self.names.append(name)


def parse(interning):
    parser = xml.sax.make_parser()
    parser.setFeature(feature_string_interning, interning)  # O(1)
    handler = Names()
    parser.setContentHandler(handler)
    parser.parse(io.BytesIO(b"<root>" + b"<item/>" * 4 + b"</root>"))
    return handler.names[1:]


assert len({id(name) for name in parse(True)}) == 1  # one object for four tags
assert len({id(name) for name in parse(False)}) == 4
```

## Errors Stop the Parse

The default `ErrorHandler` raises on a fatal error, so a malformed document costs the prefix that
parsed, not the file. The exception carries the position, captured when it was built.

```python
import io
import xml.sax


class CountingSource(io.BytesIO):
    reads = 0

    def read(self, size=-1):
        self.reads += 1
        return super().read(size)


broken = CountingSource(b"<root>]]>" + b"<item/>" * 100_000 + b"</root>")

try:
    xml.sax.parse(broken, xml.sax.ContentHandler())
except xml.sax.SAXParseException as error:
    assert error.getLineNumber() == 1  # O(1), cached at construction
    assert error.getColumnNumber() < 20  # O(1), where the fault is, not where the file ends
    assert "not well-formed" in error.getMessage()  # O(1)
    assert str(error).endswith(error.getMessage())  # O(c)
    assert broken.reads <= 2  # the tail was never read
else:
    raise AssertionError("a malformed document parsed")
```

A handler of your own decides otherwise, within limits. Returning instead of raising does not
repair the document: the reader keeps feeding what is left and the parser keeps reporting, so the
same fault reaches the handler again when the parser closes. Collect the exceptions rather than
counting them.

```python
import xml.sax


class Collect(xml.sax.ErrorHandler):
    def __init__(self):
        self.fatal = []

    def fatalError(self, exception):  # O(1) - returning lets the reader carry on
        self.fatal.append(exception)


collected = Collect()
xml.sax.parseString(b"<root><item></root>", xml.sax.ContentHandler(), collected)

assert all(error.getLineNumber() == 1 for error in collected.fatal)
assert all("mismatched tag" in error.getMessage() for error in collected.fatal)
assert isinstance(collected.fatal[0], xml.sax.SAXParseException)
```

## Writing XML

`XMLGenerator` is a `ContentHandler` that writes what it is told, so it doubles as the sink of a
parse. Each call costs the characters it writes; attribute values pay `quoteattr()` on top.

```python
import io
import xml.sax
from xml.sax.saxutils import XMLGenerator

output = io.StringIO()
generator = XMLGenerator(output, encoding="utf-8", short_empty_elements=True)

xml.sax.parseString(b'<root a="1&amp;2"><child/>text</root>', generator)  # O(n)

assert output.getvalue().endswith('<root a="1&amp;2"><child/>text</root>')
```

Namespace declarations are the one part that is not linear in what it writes: each open mapping
snapshots the prefixes in scope, so p mappings open at once cost O(p²).

```python
import io
from xml.sax.saxutils import XMLGenerator

output = io.StringIO()
generator = XMLGenerator(output)

for index in range(50):
    generator.startPrefixMapping(f"p{index}", f"urn:{index}")  # O(p) each

generator.startElementNS(("urn:49", "item"), None, {})  # O(1) name lookup
generator.endElementNS(("urn:49", "item"), None)

for index in reversed(range(50)):
    generator.endPrefixMapping(f"p{index}")  # O(p), the map it replaces is released

written = output.getvalue()
assert written.startswith("<p49:item ")  # the prefix in scope names the element
assert 'xmlns:p0="urn:0"' in written and 'xmlns:p49="urn:49"' in written  # all 50 declared
assert written.endswith("</p49:item>")
```

### Escaping

```python
from xml.sax.saxutils import escape, quoteattr, unescape

assert escape("a < b & c") == "a &lt; b &amp; c"  # O(c), three passes
assert unescape("a &lt; b &amp; c") == "a < b & c"  # O(c)

# `&` goes first, so the extra pairs see escaped text
assert escape("&", {"&amp;": "[amp]"}) == "[amp]"  # O(c * (1 + r))

# quoteattr picks the quote character and escapes the whitespace entities
assert quoteattr('say "hi"') == '\'say "hi"\''  # O(c)
assert quoteattr("line\nbreak") == '"line&#10;break"'
```

### Filter Chains

`XMLFilterBase` sits between a reader and the handlers, so a chain of f filters adds f calls per
event - linear in the chain, and nothing is re-parsed.

```python
import io
import xml.sax
from xml.sax.saxutils import XMLFilterBase, XMLGenerator


class Upper(XMLFilterBase):
    def characters(self, content):  # O(c), then one forwarding call per filter
        super().characters(content.upper())


output = io.StringIO()
chain = Upper(Upper(xml.sax.make_parser()))
chain.setContentHandler(XMLGenerator(output, encoding="utf-8"))
chain.parse(io.BytesIO(b"<root>abc</root>"))  # the parse, plus one call per filter per event

assert output.getvalue().endswith("<root>ABC</root>")
assert isinstance(chain.getParent(), XMLFilterBase)  # O(1)
```

## Common Patterns

### Aggregating Without a Tree

The point of SAX is that the handler decides what to keep, and an aggregate is smaller than the
document it came from. Keeping a count per tag costs the distinct tags, whatever the document
weighs.

```python
import io
import xml.sax
from collections import Counter


class TagCounts(xml.sax.ContentHandler):
    def __init__(self):
        self.counts = Counter()

    def startElement(self, name, attrs):
        self.counts[name] += 1  # O(1) amortized


document = b"<log>" + b"<entry level='warn'/><entry level='info'/>" * 5_000 + b"</log>"
counts = TagCounts()

xml.sax.parse(io.BytesIO(document), counts)  # O(n) time, O(distinct tags) in the handler

assert counts.counts == {"entry": 10_000, "log": 1}
```

### Collecting Text Safely

A run of text can arrive in pieces, so collect the pieces and join once per element rather than
concatenating on every call. One flag holds for one level: a title inside a title would need a
stack of them.

```python
import io
import xml.sax


class Titles(xml.sax.ContentHandler):
    def __init__(self):
        self.titles = []
        self._pieces = None

    def startElement(self, name, attrs):
        if name == "title":
            self._pieces = []

    def characters(self, content):
        if self._pieces is not None:
            self._pieces.append(content)  # O(c) per call

    def endElement(self, name):
        if name == "title":
            self.titles.append("".join(self._pieces))  # O(c) once per element
            self._pieces = None


titles = Titles()
document = b"<doc><title>One</title><title>T<em>w</em>o</title></doc>"
xml.sax.parse(io.BytesIO(document), titles)

assert titles.titles == ["One", "Two"]  # a title containing markup joins from its pieces
```

## Performance Best Practices

✅ **Do**:

- Stream from a file or a stream; `parse()` holds a buffer, the open elements and the names it has
  met, not the document
- Pass `bytes` to `parseString()`, which wraps them, rather than `str`, which is copied
- Join the pieces `characters()` hands you once per element instead of concatenating per call
- Look attributes up by name or by `(uri, localname)`, and list them once if you need them all
- Turn on `feature_string_interning` when a handler keeps the names it is given and the document
  repeats a small vocabulary

❌ **Avoid**:

- Building a list of every element in the handler - that is the tree you came here to skip
- `getValueByQName()` in namespace mode, which scans the attributes of the element
- Long namespace URIs on a document parsed in namespace mode: every name reported carries one, and
  interning does not collapse them
- Holding many `XMLGenerator` prefix mappings open at once: each one snapshots the others, so the
  cost is quadratic in how many are open, not in how many you declare
- Turning on `feature_external_ges` for untrusted input, which lets a document name what to read

## Version Notes

- **Python 3.10+**: `xml.sax.handler.LexicalHandler` reports comments, CDATA sections and the DTD
- **Python 3.7.1+**: external general entities are not resolved by default, so a document cannot
  make the parser fetch what it names unless `feature_external_ges` is turned on. A URL handed
  in as the source itself is still fetched, through `urllib.request`

## Related Modules

- **[xml](xml.md)** - the package overview and the other XML interfaces
- **[xml.etree.ElementTree](xml.etree.elementtree.md)** - builds the tree SAX avoids;
  `iterparse()` is the middle ground
- **[xml.dom](xml.dom.md)** - the full document object model, the most memory per document
- **[pyexpat](pyexpat.md)** - the parser underneath, with no SAX layer in front of it
