# xml.dom Module Complexity

The `xml.dom` package is the W3C Document Object Model for Python: the `Node` type constants, the
DOM exception classes, and a registry of implementations. `xml.dom.minidom` is the implementation
the standard library ships, and every cost on this page is minidom's. It holds the whole document
as a tree of Python objects, each node linked to its parent and siblings, and each attribute an
`Attr` node of its own; what a parsed document costs afterwards is that tree.

`xml.dom.pulldom` reads a document as a stream of DOM events instead, a buffer at a time, and
builds only the subtrees you ask it to expand. Rows write the modules by their last name:
`minidom.parseString`, `pulldom.parse`.

`n` is the characters in a document parsed or written, counting internal entities after
expansion. `s` is the nodes in the subtree an operation walks or copies, attributes included, `h`
the height of that subtree, and `d` the depth of the node an operation starts from. `k` is the
children of the node a method is called on, `a` the attributes of one element, `c` the characters
in one text node, attribute value or string argument, and `m` the nodes a search returns. `f` is
the children of a `DocumentFragment`, `r` the nodes in a run of adjacent text nodes and `t` their
characters, `x` the entities or notations a document type declares, and `b` pulldom's buffer
size. Names, namespace URIs, feature strings and ID values are treated as short: hashing,
comparing and splitting them is O(1).

## Complexity Reference

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `minidom.parse(file, parser=None, bufsize=None)` | O(n + Σc²) | O(n) | The whole tree is built before it returns. Σc² sums over text nodes long enough to arrive in several pieces, each of which is rebuilt per piece; see [Long Text Nodes](#long-text-nodes). Passing `parser` or `bufsize` builds the tree through pulldom instead |
| `minidom.parseString(string, parser=None)` | O(n + Σc²) | O(n) | As `parse()`, in one parser call |
| `xml.dom.getDOMImplementation(name=None, features=())` | O(1) | O(1) | Named `'minidom'`, or unnamed with nothing registered and no `PYTHON_DOM` set: minidom's shared `DOMImplementation`. A registered name calls its factory; unnamed, with registrations, it tries each factory in turn |
| `xml.dom.registerDOMImplementation(name, factory)` | O(1) | O(1) | One dict entry |

### DOMImplementation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `DOMImplementation.createDocument(namespaceURI, qualifiedName, doctype)` | O(1) | O(1) | Creates the document and its root element |
| `DOMImplementation.createDocumentType(qualifiedName, publicId, systemId)` | O(1) | O(1) | |
| `DOMImplementation.hasFeature(feature, version)` | O(1) | O(1) | |

### Node

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Node.parentNode`, `Node.previousSibling`, `Node.nextSibling`, `Node.firstChild`, `Node.lastChild` | O(1) | O(1) | Stored links, or the ends of the child list |
| `Node.childNodes` | O(1) | O(1) | The node's own `NodeList`, not a copy; it changes as the tree does |
| `Node.nodeType`, `Node.nodeName`, `Node.nodeValue`, `Node.localName`, `Node.prefix`, `Node.namespaceURI`, `Node.ownerDocument`, `Node.attributes` | O(1) | O(1) | `attributes` is `None` except on elements |
| `Node.hasChildNodes()`, `Node.hasAttributes()` | O(1) | O(1) | minidom defines `hasAttributes()` on elements only |
| `Node.appendChild(newChild)` | O(1) amortized | O(1) | A child that already has a parent is removed from it first, at that parent's O(k). On a `Document`, O(k): it checks its own children for an existing root |
| `Node.insertBefore(newChild, refChild)` | O(k) | O(1) | Finds `refChild` by scanning the children; `refChild=None` appends. A child moved from another parent is removed from it first, as for `appendChild()` |
| `Node.removeChild(oldChild)`, `Node.replaceChild(newChild, oldChild)` | O(k) | O(1) | Both find `oldChild` by scanning the children |
| `appendChild(fragment)` | O(f²) | O(f) | Moves each child out of the `DocumentFragment` in turn, and each move shifts the ones still in it |
| `insertBefore(fragment, refChild)` | O(f·(k + f)) | O(f) | As above, and each child also scans for `refChild` |
| `Node.normalize()` | O(s + Σr·t) | O(s + t) | Joins each run of adjacent text nodes one piece at a time, so a run costs its node count times its characters; drops empty text nodes |
| `Node.cloneNode(deep)` | O(s) deep, O(a) shallow | O(s) deep, O(a) shallow | A shallow clone copies an element's attributes. `Document.cloneNode(False)` returns `None` |
| `Node.isSameNode(other)`, `Node.isSupported(feature, version)` | O(1) | O(1) | `isSameNode` is identity |
| `Node.getUserData(key)`, `Node.setUserData(key, data, handler)` | O(1) | O(1) | |
| `Node.toxml(encoding=None, standalone=None)`, `Node.toprettyxml(indent='\t', newl='\n', encoding=None, standalone=None)` | O(n) | O(n) | minidom only; the whole output is built as one string |
| `Node.writexml(writer, indent='', addindent='', newl='')` | O(n) | O(c + h) | minidom only; writes piece by piece, holding one escaped value and the recursion. Without indentation, and after the first call: that call also gives every element without attributes its two empty attribute dicts, O(s) that stays |
| `Node.unlink()`, `with node:` | O(s) | O(a + h) | minidom only; breaks the subtree's parent and attribute cycles so it can be freed without the cycle collector |

### NodeList

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NodeList.item(i)`, `nodes[i]` | O(1) | O(1) | A `list` subclass; `item()` returns `None` out of range |
| `NodeList.length`, `len(nodes)` | O(1) | O(1) | |

### Document

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Document.createElement(tagName)`, `Document.createElementNS(namespaceURI, qualifiedName)` | O(1) | O(1) | The node belongs to the document but is not in the tree until it is appended |
| `Document.createTextNode(data)`, `Document.createComment(data)`, `Document.createCDATASection(data)`, `Document.createProcessingInstruction(target, data)` | O(1) | O(1) | Keeps the string it is given |
| `Document.createAttribute(name)`, `Document.createAttributeNS(namespaceURI, qualifiedName)` | O(1) | O(1) | |
| `Document.createDocumentFragment()` | O(1) | O(1) | |
| `Document.documentElement` | O(k) | O(1) | Found among the document node's own children, not searched for in the tree |
| `Document.doctype`, `Document.documentURI`, `Document.implementation`, `Document.strictErrorChecking` | O(1) | O(1) | `doctype` is `None` without a `<!DOCTYPE>` |
| `Document.getElementsByTagName(tagName)`, `Document.getElementsByTagNameNS(namespaceURI, localName)` | O(s) | O(m + h) | A new `NodeList` of every matching descendant, in document order; `'*'` matches any name |
| `Document.getElementById(elementId)` | O(1) cached, O(s) to search | O(s) | IDs come only from a DTD's `ID` attribute declarations or `setIdAttribute()`, whatever `id` attributes the elements carry. With no DTD element or attribute declarations and no `setIdAttribute()`, it returns `None` without searching. Searches resume where the last one stopped and cache every ID they pass; adding or removing an element below the root, or changing an attribute, clears the cache |
| `Document.importNode(importedNode, deep)` | O(s) deep, O(a) shallow | O(s) deep, O(a) shallow | A copy owned by this document; the original is untouched |
| `Document.renameNode(node, namespaceURI, qualifiedName)` | O(1), O(d) for an attribute marked with `setIdAttribute()` | O(1) | Renames in place; an attribute is removed and set again, and one marked with `setIdAttribute()` is marked again |

### Element

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Element.tagName` | O(1) | O(1) | |
| `Element.getAttribute(name)`, `Element.getAttributeNS(namespaceURI, localName)` | O(1) | O(1) | `''` when the attribute is absent |
| `Element.getAttributeNode(attrname)`, `Element.getAttributeNodeNS(namespaceURI, localName)` | O(1) | O(1) | `None` when absent |
| `Element.hasAttribute(name)`, `Element.hasAttributeNS(namespaceURI, localName)` | O(1) | O(1) | |
| `Element.setAttribute(name, value)`, `Element.setAttributeNS(namespaceURI, qname, value)` | O(1), O(c) to replace a value | O(1) | Creates an `Attr` node on the first set; a later set compares the new value with the old |
| `Element.setAttributeNode(newAttr)`, `Element.setAttributeNodeNS(newAttr)` | O(1) | O(1) | Returns the node it replaced; an `Attr` owned by another element raises `InuseAttributeErr` |
| `Element.removeAttribute(name)`, `Element.removeAttributeNS(namespaceURI, localName)`, `Element.removeAttributeNode(oldAttr)` | O(1) | O(1) | An absent attribute raises `NotFoundErr` |
| `Element.setIdAttribute(name)`, `Element.setIdAttributeNS(namespaceURI, localName)`, `Element.setIdAttributeNode(idAttr)` | O(d) | O(1) | Walks up to the root first, checking for an entity reference |
| `Element.getElementsByTagName(tagName)`, `Element.getElementsByTagNameNS(namespaceURI, localName)` | O(s) | O(m + h) | As on `Document`, below this element |

### Attr

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Attr.name`, `Attr.value`, `Attr.localName`, `Attr.prefix`, `Attr.ownerElement`, `Attr.specified` | O(1) | O(1) | |
| `Attr.isId` | O(1) | O(1) | True for an attribute set with `setIdAttribute()` or declared `ID` in the DTD |

### NamedNodeMap

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Element.attributes` | O(1) | O(1) | A new `NamedNodeMap` over the element's attribute dicts on every access |
| `NamedNodeMap.length`, `len(attributes)` | O(1) | O(1) | |
| `NamedNodeMap.item(index)` | O(a) | O(a) | Lists the attribute names on every call, so a loop over `item(i)` is O(a²) |
| `NamedNodeMap.getNamedItem(name)`, `NamedNodeMap.getNamedItemNS(namespaceURI, localName)`, `attributes[name]` | O(1) | O(1) | |
| `NamedNodeMap.setNamedItem(attr)`, `NamedNodeMap.setNamedItemNS(attr)` | O(1) | O(1) | |
| `NamedNodeMap.removeNamedItem(name)`, `NamedNodeMap.removeNamedItemNS(namespaceURI, localName)` | O(1) | O(1) | |
| `attributes.items()` | O(a) | O(a) | A list of `(name, value)` pairs; `keys()` and `values()` are views, O(1) |

### Text and other character data

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `CharacterData.data`, `CharacterData.length`, `len(node)` | O(1) | O(1) | `Text`, `Comment` and `CDATASection` all hold one string |
| `CharacterData.substringData(offset, count)` | O(count) | O(count) | |
| `CharacterData.appendData(arg)`, `CharacterData.insertData(offset, arg)`, `CharacterData.deleteData(offset, count)`, `CharacterData.replaceData(offset, count, arg)` | O(c) | O(c) | Every edit builds a new string, so appending to one node in a loop is quadratic in its final length |
| `Text.splitText(offset)` | O(c + k) | O(c) | Inserts the second half as the next sibling |
| `Text.wholeText` | O(r² + t) | O(r + t) | The run on both sides of this node; the nodes before it cost quadratically |
| `Text.replaceWholeText(content)` | O(r·k) | O(1) | Removes each adjacent text node from the parent, at O(k) apiece |
| `Comment.data`, `ProcessingInstruction.target`, `ProcessingInstruction.data` | O(1) | O(1) | |
| `CDATASection` | O(1) | O(1) | A `Text` subclass; `writexml()` raises `ValueError` if the data contains `]]>` |

### DocumentType, Entity and Notation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `DocumentType.name`, `DocumentType.publicId`, `DocumentType.systemId`, `DocumentType.internalSubset` | O(1) | O(1) | `internalSubset` is the declaration text between the brackets |
| `DocumentType.entities`, `DocumentType.notations` | O(1) | O(1) | Read-only maps kept as a sequence |
| `entities.getNamedItem(name)`, `notations.getNamedItem(name)` | O(x) | O(1) | A linear scan of the declarations; `item(i)` is O(1) |
| `Entity.publicId`, `Entity.systemId`, `Entity.notationName`, `Notation.publicId`, `Notation.systemId` | O(1) | O(1) | |

### pulldom

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pulldom.parse(stream_or_string, parser=None, bufsize=None)` | O(1) to create, O(n) to exhaust | O(b + d) unless you expand nodes | A string is a file name, opened in binary mode. Reads `b` bytes at a time, `default_bufsize` unless given. The open elements and their attributes are held, and everything before the root element is queued until it arrives |
| `pulldom.parseString(string, parser=None)` | O(n) to create and to exhaust | O(n) | The whole string is one read, so the first event queues every other one |
| Iterating a `DOMEventStream`, `DOMEventStream.getEvent()` | O(n) over the stream | O(1) per event | `(event, node)` pairs; one read of b characters whenever the queue is empty. `getEvent()` returns `None` at the end |
| `DOMEventStream.expandNode(node)` | O(s) | O(s) | Consumes the events up to the node's end and builds its subtree under it; call it on a `START_ELEMENT` node. Parsing the input it reads is part of the stream's O(n) |
| `DOMEventStream.reset()` | O(1) | O(1) | Installs a fresh `PullDOM` handler on the same parser and stream |
| `DOMEventStream.clear()` | O(1) | O(1) | Drops the handler, parser and stream |
| `pulldom.PullDOM(documentFactory=None)` | O(1) | O(1) | The SAX handler behind the stream: creates each node without attaching it, and queues the event |
| `pulldom.SAX2DOM(documentFactory=None)` | O(n) over a parse | O(n) | A handler that attaches every node, so it builds the whole tree |
| `pulldom.default_bufsize` | O(1) | O(1) | 16,364 |
| `pulldom.START_ELEMENT`, `pulldom.END_ELEMENT`, `pulldom.CHARACTERS`, `pulldom.START_DOCUMENT`, `pulldom.END_DOCUMENT`, `pulldom.COMMENT`, `pulldom.PROCESSING_INSTRUCTION`, `pulldom.IGNORABLE_WHITESPACE` | O(1) | O(1) | Event names, as strings. Iterating a stream stops before `END_DOCUMENT` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Node.ELEMENT_NODE`, `Node.ATTRIBUTE_NODE`, `Node.TEXT_NODE`, `Node.CDATA_SECTION_NODE`, `Node.ENTITY_REFERENCE_NODE`, `Node.ENTITY_NODE`, `Node.PROCESSING_INSTRUCTION_NODE`, `Node.COMMENT_NODE`, `Node.DOCUMENT_NODE`, `Node.DOCUMENT_TYPE_NODE`, `Node.DOCUMENT_FRAGMENT_NODE`, `Node.NOTATION_NODE` | O(1) | O(1) | The values of `nodeType`, 1 to 12 |
| `xml.dom.XML_NAMESPACE`, `xml.dom.XMLNS_NAMESPACE`, `xml.dom.XHTML_NAMESPACE`, `xml.dom.EMPTY_NAMESPACE` | O(1) | O(1) | `EMPTY_NAMESPACE` is `None` |
| `xml.dom.DOMException` | O(1) | O(1) | Base class of the errors below; instantiating it directly raises `RuntimeError` |
| `xml.dom.DomstringSizeErr`, `xml.dom.HierarchyRequestErr`, `xml.dom.IndexSizeErr`, `xml.dom.InuseAttributeErr`, `xml.dom.InvalidAccessErr`, `xml.dom.InvalidCharacterErr`, `xml.dom.InvalidModificationErr`, `xml.dom.InvalidStateErr`, `xml.dom.NamespaceErr`, `xml.dom.NoDataAllowedErr`, `xml.dom.NoModificationAllowedErr`, `xml.dom.NotFoundErr`, `xml.dom.NotSupportedErr`, `xml.dom.SyntaxErr`, `xml.dom.ValidationErr`, `xml.dom.WrongDocumentErr` | O(1) | O(1) | Each carries its code as `code` |
| `xml.dom.INDEX_SIZE_ERR`, `xml.dom.DOMSTRING_SIZE_ERR`, `xml.dom.HIERARCHY_REQUEST_ERR`, `xml.dom.WRONG_DOCUMENT_ERR`, `xml.dom.INVALID_CHARACTER_ERR`, `xml.dom.NO_DATA_ALLOWED_ERR`, `xml.dom.NO_MODIFICATION_ALLOWED_ERR`, `xml.dom.NOT_FOUND_ERR`, `xml.dom.NOT_SUPPORTED_ERR`, `xml.dom.INUSE_ATTRIBUTE_ERR`, `xml.dom.INVALID_STATE_ERR`, `xml.dom.SYNTAX_ERR`, `xml.dom.INVALID_MODIFICATION_ERR`, `xml.dom.NAMESPACE_ERR`, `xml.dom.INVALID_ACCESS_ERR`, `xml.dom.VALIDATION_ERR` | O(1) | O(1) | The codes, 1 to 16 |

## Parsing a Document

### Whole Documents

`parseString()` and `parse()` build the whole tree before they return, so memory follows the
document. Every node is a Python object with its own links, which makes a minidom tree
considerably larger than an ElementTree one of the same document.

```python
from xml.dom import minidom

doc = minidom.parseString('<items><item>a</item><item>b</item></items>')  # O(n)

root = doc.documentElement  # O(k) over the document's own children
assert root.tagName == 'items'
assert [item.firstChild.data for item in root.childNodes] == ['a', 'b']  # O(1) per step
assert root.childNodes is root.childNodes  # the live list, not a copy
```

### Long Text Nodes

A text node that reaches the builder in several pieces is joined one piece at a time, and each
join copies everything joined so far. `parse()` hands Expat 16 KiB of a file per call, and within
a call Expat delivers text broken by newlines or entity references in pieces of about 8 KiB, from
a file or a string. Text of a few kilobytes never notices; a text node of many megabytes that
arrives in pieces costs time quadratic in its length. Unbroken text passed to `parseString()`
arrives whole. ElementTree joins a text run once.

```python
import io
from xml.dom import minidom

data = b'<blob>' + b'line\n' * 20_000 + b'</blob>'

from_file = minidom.parse(io.BytesIO(data))  # O(n + c²): one join per piece
from_bytes = minidom.parseString(data)       # O(n + c²): the same, in one call

text = from_bytes.documentElement.firstChild.data
assert text == from_file.documentElement.firstChild.data
assert len(text) == 100_000 and len(from_bytes.documentElement.childNodes) == 1
```

## Streaming With pulldom

`pulldom.parse()` reads a buffer at a time and reports each node as an event without attaching it
to its parent, the root element aside, so memory follows the buffer and the open elements rather
than the document. `expandNode()` builds the
subtree of one element when you want it whole. `pulldom.parseString()` does not stream: the whole
string is one read, and the first event queues all the rest.

```python
import io
from xml.dom import pulldom

data = b'<log>' + b''.join(b'<entry level="%d">message %d</entry>' % (i % 3, i)
                           for i in range(1000)) + b'</log>'

errors = []
events = pulldom.parse(io.BytesIO(data))  # O(1) - reads nothing yet
for event, node in events:                # O(n) over the whole stream
    if event == pulldom.START_ELEMENT and node.tagName == 'entry':
        if node.getAttribute('level') == '2':
            events.expandNode(node)       # O(s) - builds this entry only
            errors.append(node.firstChild.data)

assert len(errors) == 333
assert errors[0] == 'message 2'
```

## Finding Elements

### By Tag Name

`getElementsByTagName()` walks the whole subtree on every call and returns a new list of what it
found. Call it once and keep the result, rather than calling it inside a loop.

```python
from xml.dom import minidom

doc = minidom.parseString('<a><b/><c><b/></c></a>')

first = doc.getElementsByTagName('b')  # O(s) time, O(m + h) space
assert len(first) == 2
assert doc.getElementsByTagName('b') is not first  # a new list every call
assert len(doc.getElementsByTagName('*')) == 4
```

### By ID

`getElementById()` only knows IDs the document declares: an attribute typed `ID` in the DTD, or one
marked with `setIdAttribute()`. An attribute merely named `id` is not an ID, and without a DTD or
`setIdAttribute()` the lookup returns `None` without searching. With declarations, the first lookup walks the tree until it
finds the ID and caches every ID it passes; a repeated lookup is a dict hit until the tree changes.

```python
from xml.dom import minidom

plain = minidom.parseString('<r><a id="x"/></r>')
assert plain.getElementById('x') is None  # no ID declared: O(1), no search

typed = minidom.parseString(
    '<!DOCTYPE r [<!ATTLIST a id ID #IMPLIED>]><r><a id="x"/><a id="y"/></r>'
)
x = typed.getElementById('x')  # O(s) the first time
assert x.getAttribute('id') == 'x'
assert typed.getElementById('x') is x  # O(1) - cached

element = plain.documentElement.firstChild
element.setIdAttribute('id')  # O(d) - walks to the root
assert plain.getElementById('x') is element
```

## Changing the Tree

Children are a Python list. Appending is O(1) amortized, but `insertBefore()`, `removeChild()` and
`replaceChild()` scan the list to find the reference child, O(k) each. Attributes are dicts, so
setting and removing them is O(1).

```python
from xml.dom import minidom

doc = minidom.parseString('<list/>')
root = doc.documentElement

for i in range(3):
    item = doc.createElement('item')  # O(1)
    item.setAttribute('n', str(i))    # O(1)
    root.appendChild(item)            # O(1) amortized

first = root.firstChild
root.insertBefore(doc.createElement('head'), first)  # O(k) - finds `first` by scanning
root.removeChild(root.lastChild)                     # O(k)
assert [node.tagName for node in root.childNodes] == ['head', 'item', 'item']

first.removeAttribute('n')  # O(1)
assert not first.hasAttribute('n')
```

### Document Fragments

Appending a `DocumentFragment` moves its children across one at a time, and each move takes the
first child out of the fragment's list and shifts the rest down. That is O(f²) for f children:
append the children directly when there are many.

```python
from xml.dom import minidom

doc = minidom.parseString('<list/>')
fragment = doc.createDocumentFragment()
for i in range(100):
    fragment.appendChild(doc.createElement('item'))  # O(1) amortized

doc.documentElement.appendChild(fragment)  # O(f²)
assert len(doc.documentElement.childNodes) == 100
assert not fragment.hasChildNodes()  # the fragment is emptied
```

## Text Nodes

A text node holds one immutable string, so every `appendData()` or `insertData()` builds a new
one: accumulate the pieces in a list and set `data` once. Adjacent text nodes are what building a
tree by hand produces; `normalize()` joins them, and until then `wholeText` gathers them on every
read.

```python
from xml.dom import minidom

doc = minidom.parseString('<p/>')
p = doc.documentElement
for word in ['one ', 'two ', 'three']:
    p.appendChild(doc.createTextNode(word))  # O(1) amortized

assert len(p.childNodes) == 3
assert p.lastChild.wholeText == 'one two three'  # O(r² + t) - gathers the run

p.normalize()  # O(s + r·t) - joins the run into one node
assert len(p.childNodes) == 1 and p.firstChild.data == 'one two three'

text = p.firstChild
text.appendData('!')  # O(c) - a new string
tail = text.splitText(3)  # O(c + k)
assert (text.data, tail.data) == ('one', ' two three!')
```

## Serializing

`toxml()` and `toprettyxml()` build the whole output as one string. `writexml()` writes to any
object with a `write()` method as it goes, so the output never has to exist in memory at once.

```python
import io
from xml.dom import minidom

doc = minidom.parseString('<r><a x="1">text &amp; more</a></r>')

xml_text = doc.documentElement.toxml()  # O(n) time and space
assert xml_text == '<r><a x="1">text &amp; more</a></r>'

sink = io.StringIO()
doc.documentElement.writexml(sink)  # O(n) time, O(c + h) of its own
assert sink.getvalue() == xml_text

assert doc.toxml(encoding='utf-8').startswith(b'<?xml version="1.0" encoding="utf-8"?>')
```

## Deep Trees

Parsing is not recursive, but walking a parsed tree is: `getElementsByTagName()`, `toxml()`,
`writexml()`, `cloneNode(True)`, `importNode(node, True)` and `normalize()` call themselves once per
level, and `unlink()` twice. A tree nested deeper than the interpreter's recursion limit, 1,000 by
default, parses and then raises `RecursionError` when walked; `unlink()` fails at about half that
depth. `getElementById()` and pulldom's `expandNode()` do not recurse.

```python
import sys
from xml.dom import minidom

depth = 2 * sys.getrecursionlimit()
doc = minidom.parseString('<a>' * depth + '</a>' * depth)  # O(n) - fine at any depth

try:
    doc.getElementsByTagName('a')  # recursive: one frame per level
except RecursionError:
    pass
else:
    raise AssertionError('a tree twice the recursion limit deep was walked')
```

## Common Patterns

### Reading Attributes

`NamedNodeMap.item(i)` lists the attribute names on every call, so walk `items()` instead of
indexing in a loop.

```python
from xml.dom import minidom

element = minidom.parseString('<e a="1" b="2" c="3"/>').documentElement
attributes = element.attributes  # O(1) - a new view each access

pairs = attributes.items()  # O(a)
assert sorted(pairs) == [('a', '1'), ('b', '2'), ('c', '3')]
assert attributes.getNamedItem('b').value == '2'  # O(1)
assert attributes.item(0).name in {'a', 'b', 'c'}  # O(a) per call
```

### Freeing a Large Tree

Nodes point to their parents and attributes to their elements, so a discarded tree waits for the
cycle collector. `unlink()`, or a `with` block, breaks those links at once.

```python
from xml.dom import minidom

with minidom.parseString('<r><a x="1"/></r>') as doc:
    element = doc.documentElement.firstChild
    assert element.parentNode is doc.documentElement

# unlink() ran on leaving the block - O(s)
assert element.parentNode is None
assert doc.documentElement is None
```

## Performance Best Practices

✅ **Do**:

- Stream a large document with `pulldom.parse()` and expand only the elements you need
- Keep the list `getElementsByTagName()` returns rather than calling it again
- Declare ID attributes in the DTD or with `setIdAttribute()` if you look elements up by ID
- Build a text node's content in a list and set `data` once
- Use `writexml()` to a file for large output; `unlink()` a tree you have finished with

❌ **Avoid**:

- `pulldom.parseString()` on a large document: it queues every event at the first read
- `insertBefore()` or `removeChild()` in a loop over a wide element: each call scans the children
- Appending a `DocumentFragment` of thousands of children: it costs O(f²)
- Looping over `NamedNodeMap.item(i)`: each call is O(a)
- minidom for a document holding a text node of many megabytes, from a file or broken into lines:
  joining its pieces is quadratic; ElementTree joins it once

## Version Notes

- **Python 3.14.2+, 3.13.11+, 3.12.13+, 3.11.15+, 3.10.20+**: Adding or removing an element and
  setting or removing an attribute no longer walk to the root to clear the ID cache. Earlier
  releases add O(d) to each such call, so building a tree of depth d by `appendChild()` is O(d²)
- **Python 3.13+**: `toxml()` and `writexml()` escape tabs, carriage returns and newlines in
  attribute values, so they survive a round trip
- **Python 3.11+**: `DOMEventStream` can no longer be indexed; iterate it

## Related Modules

- **[xml.etree.ElementTree](xml.etree.elementtree.md)** - A lighter tree whose O(n) parse joins
  long text once; `iterparse()` streams too
- **[xml.sax](xml.sax.md)** - The event parser under pulldom, with no tree at all
- **[pyexpat](pyexpat.md)** - The Expat parser underneath minidom and pulldom
- **[xml](xml.md)** - Overview of the XML packages
