# pyexpat Module Complexity

The `pyexpat` module is the Python binding for the Expat XML parser, and `xml.parsers.expat` is
the same API under its documented name. A parser reads bytes or text and calls the handler
functions you assign as it recognises each piece of markup. It builds no tree: what it holds is
the open elements and the input it has been given but not finished with, and every higher-level
XML API in the standard library - `xml.etree.ElementTree`, `xml.sax`, `xml.dom.minidom` - is a set
of handlers over it.

`n` is the bytes of a whole document, counting internal entities after expansion, and `c` is the
characters one call carries: the data passed to one `Parse()`, one text run, one name. `d` is the
depth of open elements, `a` the attributes on one element, `q` the distinct names a parser has
interned, and `m` the size of a document's DTD, its declarations and their replacement text. Names and attribute values count as O(1)
each except where `c` measures them. Every bound excludes the handlers' own work, which is yours;
what the module adds per event is building the handler's arguments. Beyond what the rows price, a
parser keeps its DTD's declarations and its interned names until it is discarded, and holds a
token split across `Parse()` calls until the token is complete.

## Complexity Reference

### Module functions and objects

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pyexpat.ParserCreate(encoding=None, namespace_separator=None)` | O(1) | O(1) | Returns a new `xmlparser`; a parser parses one document, so make one per document |
| `pyexpat.XMLParserType` | O(1) | O(1) | The type `ParserCreate()` returns, for `isinstance()` checks; calling it raises `TypeError` |
| `pyexpat.ErrorString(errno)` | O(1) | O(1) | The message for an error number: the same text as `errors.messages[errno]` |
| `pyexpat.ExpatError`, `pyexpat.error` | O(1) | O(1) | One class under two names, raised by `Parse()` and `ParseFile()` for malformed input |
| `ExpatError.code`, `ExpatError.lineno`, `ExpatError.offset` | O(1) | O(1) | The error number, the 1-based line and the 0-based column of the fault |
| `pyexpat.features` | O(1) | O(1) | A short list of `(name, value)` pairs describing the linked Expat, built at import |
| `pyexpat.EXPAT_VERSION`, `pyexpat.version_info`, `pyexpat.native_encoding` | O(1) | O(1) | The linked Expat's version as a string and as a tuple, and the encoding Expat works in (`'UTF-8'`) |
| `pyexpat.XML_PARAM_ENTITY_PARSING_NEVER`, `pyexpat.XML_PARAM_ENTITY_PARSING_UNLESS_STANDALONE`, `pyexpat.XML_PARAM_ENTITY_PARSING_ALWAYS` | O(1) | O(1) | Integer flags for `SetParamEntityParsing()` |

### xmlparser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xmlparser.Parse(data, isfinal=False)` | O(c) amortized | O(c + d) | Amortized over the calls that feed one document, with internal entities counted after expansion: a short call can complete a long token held from earlier calls. Fed in pieces, the parser holds one piece and the open elements, not the document. After `isfinal=True` the parser is finished, and a further call raises `ExpatError` |
| `xmlparser.ParseFile(file)` | O(n) | O(d) | Reads `file` 2,048 bytes at a time until it is exhausted |
| `xmlparser.StartElementHandler` | O(a) per element | O(a) | Receives a new attribute dict per element; `ordered_attributes` makes it a flat list |
| `xmlparser.CharacterDataHandler` | O(c) per call | O(c) | A text run arrives in several calls, split at newlines and entity references, unless `buffer_text` is set |
| `xmlparser.EndElementHandler`, `xmlparser.ProcessingInstructionHandler`, `xmlparser.CommentHandler`, `xmlparser.StartCdataSectionHandler`, `xmlparser.EndCdataSectionHandler`, `xmlparser.StartNamespaceDeclHandler`, `xmlparser.EndNamespaceDeclHandler`, `xmlparser.XmlDeclHandler`, `xmlparser.StartDoctypeDeclHandler`, `xmlparser.EndDoctypeDeclHandler`, `xmlparser.ElementDeclHandler`, `xmlparser.AttlistDeclHandler`, `xmlparser.EntityDeclHandler`, `xmlparser.UnparsedEntityDeclHandler`, `xmlparser.NotationDeclHandler`, `xmlparser.NotStandaloneHandler`, `xmlparser.ExternalEntityRefHandler`, `xmlparser.SkippedEntityHandler`, `xmlparser.DefaultHandler`, `xmlparser.DefaultHandlerExpand` | O(1) to assign; O(c) per event | O(c) | Each event converts only its own arguments; an event with no handler assigned costs no Python call |
| `xmlparser.buffer_text`, `xmlparser.buffer_size`, `xmlparser.buffer_used` | O(1) | O(buffer_size) | With `buffer_text`, consecutive pieces of character data are joined into one `CharacterDataHandler` call while they fit in `buffer_size` (8,192 by default); a longer piece is delivered on its own |
| `xmlparser.ordered_attributes`, `xmlparser.specified_attributes` | O(1) | O(1) | A flat `[name, value, ...]` list instead of a dict; only the attributes the document wrote, not defaults from its DTD |
| `xmlparser.intern` | O(1) | O(q) | The dict every name given to a handler passes through, so a tag seen a thousand times is one string; it grows with the distinct names, not the elements. `ParserCreate(intern=None)` turns interning off, and passing a dict shares one between parsers |
| `xmlparser.namespace_prefixes` | O(1) | O(1) | With `namespace_separator`, names also carry their prefix |
| `xmlparser.ErrorCode`, `xmlparser.ErrorLineNumber`, `xmlparser.ErrorColumnNumber`, `xmlparser.ErrorByteIndex` | O(1) | O(1) | Where the last error occurred; `ExpatError` carries the same code, line and column |
| `xmlparser.CurrentByteIndex` | O(1) | O(1) | The byte offset of the current event |
| `xmlparser.CurrentLineNumber`, `xmlparser.CurrentColumnNumber` | O(1) amortized | O(1) | Each query counts lines in the input since the previous one, so querying at every event is still O(n) over the document |
| `xmlparser.GetInputContext()` | O(c) | O(c) | Inside a handler, a copy of the input from the current event to the end of the data Expat holds: the rest of the 1 MiB piece `Parse()` hands it at a time, plus any token held from earlier calls. `None` outside a handler |
| `xmlparser.SetBase(base)`, `xmlparser.GetBase()` | O(c) | O(c) | The base passed to the entity handlers; `None` until set |
| `xmlparser.ExternalEntityParserCreate(context[, encoding])` | O(m + c) | O(m + c) | From an `ExternalEntityRefHandler`: a parser for the entity that copies this one's DTD declarations |
| `xmlparser.SetParamEntityParsing(flag)`, `xmlparser.UseForeignDTD(flag=True)` | O(1) | O(1) | Call before parsing starts |
| `xmlparser.SetReparseDeferralEnabled(enabled)`, `xmlparser.GetReparseDeferralEnabled()` | O(1) | O(1) | Deferral, on by default with Expat 2.6+, keeps a token split across many `Parse()` calls linear; turned off, it is rescanned on every call |
| `xmlparser.SetBillionLaughsAttackProtectionActivationThreshold(threshold)`, `xmlparser.SetBillionLaughsAttackProtectionMaximumAmplification(max_factor)`, `xmlparser.SetAllocTrackerActivationThreshold(threshold)`, `xmlparser.SetAllocTrackerMaximumAmplification(max_factor)` | O(1) | O(1) | Limits on entity expansion and on memory per input byte. Present only where both the Python release and its linked Expat provide them; check with `hasattr()` |

### errors and model

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.parsers.expat.errors` | O(1) | O(1) | The error constants: each `errors.XML_ERROR_*` name is a message string, not a number |
| `errors.codes` | O(1) per lookup | O(1) | A dict from message to error number |
| `errors.messages` | O(1) per lookup | O(1) | A dict from error number to message, which is how `ExpatError.code` becomes text |
| `xml.parsers.expat.model` | O(1) | O(1) | Integer constants for the content-model tuples `ElementDeclHandler` receives: `model.XML_CTYPE_*` for the kind of model, `model.XML_CQUANT_*` for `?`, `*` and `+` |

## Parsing a Document

### Handlers Fire as Markup Completes

`Parse()` calls a handler for each piece of markup its data completes before it returns; with
reparse deferral, a token split across calls can wait for more data or for `isfinal=True`. Nothing is
kept for you: a handler that wants the data must store it.

```python
import pyexpat

events = []
parser = pyexpat.ParserCreate()  # O(1)
parser.StartElementHandler = lambda name, attrs: events.append(('start', name, attrs))  # O(a) per element
parser.EndElementHandler = lambda name: events.append(('end', name))

parser.Parse("<root><item id='1'/></root>", True)  # O(n)
assert events == [
    ('start', 'root', {}),
    ('start', 'item', {'id': '1'}),
    ('end', 'item'),
    ('end', 'root'),
]
```

### Feeding a Large Document in Pieces

One `Parse()` over a whole document holds the whole document while it runs. Fed in pieces, the
parser holds the current piece, the open elements and any token still incomplete, so memory follows
the piece size and the depth. `ParseFile()` does the same from a file.

```python
import io
import pyexpat

document = ("<log>" + "<entry/>" * 10_000 + "</log>").encode()

count = 0
def start(name, attrs):
    global count
    count += 1

parser = pyexpat.ParserCreate()
parser.StartElementHandler = start
for offset in range(0, len(document), 4096):
    parser.Parse(document[offset:offset + 4096], False)  # O(c) per piece
parser.Parse(b"", True)  # ends the document
assert count == 10_001

parser = pyexpat.ParserCreate()
parser.StartElementHandler = start
parser.ParseFile(io.BytesIO(document))  # O(n), 2,048 bytes at a time
assert count == 20_002
```

### Joining Character Data

A text run reaches `CharacterDataHandler` in several calls, split at newlines and entity references.
`buffer_text` joins consecutive pieces into one call, which is fewer Python calls for the same text.

```python
import pyexpat

def pieces(buffer_text):
    received = []
    parser = pyexpat.ParserCreate()
    parser.buffer_text = buffer_text  # O(1)
    parser.CharacterDataHandler = received.append  # O(c) per call
    parser.Parse("<r>one\ntwo &amp; three</r>", True)
    return received

assert pieces(False) == ['one', '\n', 'two ', '&', ' three']
assert pieces(True) == ['one\ntwo & three']
```

### Interned Names

Every tag and attribute name passes through the parser's `intern` dict, so repeated names are one
string object and the dict grows with the distinct names only.

```python
import pyexpat

names = []
parser = pyexpat.ParserCreate()
parser.StartElementHandler = lambda name, attrs: names.append(name)
parser.Parse("<r><item/><item/><item/></r>", True)

assert names[1] is names[2] is names[3]  # one string per distinct name
assert parser.intern == {'r': 'r', 'item': 'item'}  # O(q)
```

## Errors

A malformed document raises `ExpatError` at the fault. The exception carries Expat's error number
and position; `errors.messages` and `ErrorString()` turn the number into text, and
`errors.codes` turns the text back into a number.

```python
import pyexpat
from xml.parsers.expat import errors

parser = pyexpat.ParserCreate()
try:
    parser.Parse("<r>\n  <a></b></r>", True)
except pyexpat.ExpatError as error:
    assert (error.lineno, error.offset) == (2, 7)  # O(1)
    assert errors.messages[error.code] == 'mismatched tag'  # O(1)
    assert pyexpat.ErrorString(error.code) == 'mismatched tag'  # O(1)
    assert errors.codes[errors.XML_ERROR_TAG_MISMATCH] == error.code
    assert parser.ErrorLineNumber == error.lineno
else:
    raise AssertionError('a mismatched tag was parsed')

# A parser is finished once it has been given isfinal=True
parser = pyexpat.ParserCreate()
parser.Parse("<r/>", True)
try:
    parser.Parse("<r/>", True)
except pyexpat.ExpatError as error:
    assert errors.messages[error.code] == 'parsing finished'
else:
    raise AssertionError('a finished parser parsed again')
```

## Positions and Input Context

`CurrentLineNumber` and `CurrentColumnNumber` count forward from the last position asked for, so
reading them at every event costs O(n) over the document. `GetInputContext()` is different: it
copies the input from the current event to the end of the data Expat holds, which for one large
`Parse()` is up to 1 MiB, more when one token is longer. Called at every event, it copies that much
per event, far more than the document; feed the document in pieces and each copy is about a piece
and whatever token is still incomplete.

```python
import pyexpat

positions = []
parser = pyexpat.ParserCreate()
parser.StartElementHandler = lambda name, attrs: positions.append(
    (parser.CurrentLineNumber, parser.CurrentColumnNumber, parser.CurrentByteIndex)  # O(1) amortized
)
parser.Parse("<r>\n <a/>\n<b/></r>", True)
assert positions == [(1, 0, 0), (2, 1, 5), (3, 0, 10)]

document = ("<r>" + "<a/>" * 1000 + "</r>").encode()
copied = []
parser = pyexpat.ParserCreate()
parser.StartElementHandler = lambda name, attrs: copied.append(len(parser.GetInputContext()))  # O(c)
parser.Parse(document, True)
assert copied[0] == len(document)  # the first event copies all of it
assert parser.GetInputContext() is None  # outside a handler
```

## Declarations and Content Models

`ElementDeclHandler` receives each `<!ELEMENT>` declaration's content model as nested tuples of
`(type, quantifier, name, children)`, whose numbers are the `model` constants.

```python
import pyexpat
from xml.parsers.expat import model

declarations = {}
parser = pyexpat.ParserCreate()
parser.ElementDeclHandler = lambda name, content: declarations.update({name: content})
parser.Parse(
    "<!DOCTYPE r [<!ELEMENT r (a|b)*><!ELEMENT a (#PCDATA)><!ELEMENT b EMPTY>]><r/>", True
)

assert declarations['r'] == (
    model.XML_CTYPE_CHOICE,
    model.XML_CQUANT_REP,
    None,
    ((model.XML_CTYPE_NAME, model.XML_CQUANT_NONE, 'a', ()),
     (model.XML_CTYPE_NAME, model.XML_CQUANT_NONE, 'b', ())),
)
assert declarations['b'][0] == model.XML_CTYPE_EMPTY
```

## Common Patterns

### Checking What the Linked Expat Supports

The Expat a Python build links decides some of the parser's limits and methods, so check the build
rather than the Python version.

```python
import pyexpat

features = dict(pyexpat.features)  # O(1) - a short list
assert features['sizeof(XML_Char)'] == 1
assert pyexpat.EXPAT_VERSION.startswith('expat_')
assert pyexpat.version_info >= (2, 0, 0)
assert isinstance(pyexpat.ParserCreate(), pyexpat.XMLParserType)

parser = pyexpat.ParserCreate()
if hasattr(parser, 'SetAllocTrackerActivationThreshold'):
    parser.SetAllocTrackerActivationThreshold(64 * 1024 * 1024)  # O(1)
```

## Performance Best Practices

✅ **Do**:

- Feed a large document to `Parse()` in pieces, or use `ParseFile()`, so memory follows the piece
  rather than the document
- Set `buffer_text` when you only want whole text runs; it replaces many handler calls with one
- Assign only the handlers you need; an event without one costs no Python call
- Keep reparse deferral on when feeding small pieces

❌ **Avoid**:

- `GetInputContext()` in every handler of one large `Parse()` - each call copies the rest of the
  data Expat holds, up to 1 MiB or the token in progress
- Reusing a parser for a second document - it raises once it has been given `isfinal=True`
- `SetReparseDeferralEnabled(False)` for input that arrives in many small pieces - a long token is
  rescanned on every piece

## Version Notes

- **Python 3.13+, 3.12.3+, 3.11.9+, 3.10.14+**: Added `SetReparseDeferralEnabled()` and
  `GetReparseDeferralEnabled()`. Deferral itself needs Expat 2.6+; a build linking an older Expat
  rescans a split token on every `Parse()` call
- **All Python 3**: `SetBillionLaughsAttackProtection*()` and `SetAllocTracker*()` exist only where
  the Python release and its linked Expat both provide them, which varies by patch release and build

## Related Modules

- **[xml.etree.ElementTree](xml.etree.elementtree.md)** - A tree built from Expat's events
- **[xml.sax](xml.sax.md)** - The same event model behind the SAX handler interface
- **[xml.dom](xml.dom.md)** - The W3C DOM interface over a whole tree
- **[xml](xml.md)** - Overview of the XML packages
