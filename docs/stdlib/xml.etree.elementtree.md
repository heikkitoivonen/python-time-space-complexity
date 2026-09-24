# xml.etree.ElementTree Module Complexity

The `xml.etree.ElementTree` module parses XML into a tree of `Element` objects, searches it with a
small subset of XPath, and serializes it back. Parsing is one pass of Expat over the document, and
the tree is built in C as it goes; what a parsed document costs afterwards is the tree itself,
which holds every element, attribute and text run until you let it go.

`iterparse()` and `XMLPullParser` report each element as it completes, so you can discard what you
have finished with; left alone, they build the same whole tree. On the way out, `ElementTree.write()`
streams to its file, while `tostring()` holds the whole output. Rows write the module as `ET`, the
name it is conventionally imported under.

`n` is the characters in a document or in the output being written, counting internal entities
after expansion. `e` is the elements in the tree or subtree an operation walks, `b` the attributes
on those elements, and `d` the depth of that tree. `k` is the children of the element a method is
called on, `a` the attributes of one element, and `c` the characters one call carries: a chunk
passed to `feed()`, a text run, a name. `q` is the distinct tag and attribute names a serializer
meets. Attribute lookups and path predicates treat hashing and comparing a name or an attribute
value as O(1). A parsed text run can be held as its pieces until it is first read, which the
`Element.text` row prices; the other rows assume it has been read.

## Complexity Reference

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.fromstring(text, parser=None)`, `ET.XML(text, parser=None)` | O(n) | O(n) | The same function under two names; the whole tree is built before it returns |
| `ET.fromstringlist(sequence, parser=None)` | O(n) | O(n) | Feeds the fragments in order; n counts all of them |
| `ET.parse(source, parser=None)` | O(n) | O(n) | Returns an `ElementTree`; `source` is a path or an open file, read in chunks |
| `ET.XMLID(text, parser=None)` | O(n) | O(n) | Parses, then walks the tree once to map each `id` attribute to its element |
| `ET.iterparse(source, events=None, parser=None)` | O(1) to create, O(n) to exhaust | O(n) unless you remove finished elements | Reads nothing until the first `next()`, then 16 KiB at a time. Every element stays attached to the tree it builds; the iterator's `root` is set once it is exhausted, and it has `close()` on Python 3.13+ |
| `ET.ParseError` | O(1) | O(1) | A `SyntaxError` subclass raised for malformed input |
| `ParseError.code`, `ParseError.position` | O(1) | O(1) | Expat's error number and the `(line, column)` of the fault |

### XMLPullParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.XMLPullParser(events=None)` | O(1) | O(1) | Reports `"end"` events unless `events` names others: `"start"`, `"comment"`, `"pi"`, `"start-ns"`, `"end-ns"` |
| `XMLPullParser.feed(data)` | O(c) | O(c) | Queues one event per piece of markup `data` completes; a parse error is queued too, and raised by `read_events()` |
| `XMLPullParser.read_events()` | O(1) per event | O(1) | Removes events from the queue as you iterate; events you never read stay queued, and so does the tree they point into |
| `XMLPullParser.flush()` | O(c) | O(c) | c = the bytes the parser has held back; parses them now. Python 3.13+, 3.12.3+, 3.11.9+ and 3.10.14+ |
| `XMLPullParser.close()` | O(c) | O(c) | Ends the document and queues its last events; returns `None` |

### XMLParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.XMLParser(*, target=None, encoding=None)` | O(1) | O(1) | Builds a `TreeBuilder` when no target is given |
| `XMLParser.feed(data)` | O(c) | O(c) | Calls the target's methods for each piece of markup `data` completes |
| `XMLParser.close()` | O(c) | O(c) | Finishes the document and returns `target.close()`, which is the root for a `TreeBuilder` |
| `XMLParser.flush()` | O(c) | O(c) | As `XMLPullParser.flush()`, on the same versions |
| `XMLParser.entity` | O(1) | O(1) | A dict of replacement text for entities a document with a DOCTYPE uses without declaring |
| `XMLParser.target`, `XMLParser.version` | O(1) | O(1) | The target object, and the Expat version string |

### TreeBuilder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.TreeBuilder(element_factory=None, *, comment_factory=None, pi_factory=None, insert_comments=False, insert_pis=False)` | O(1) | O(1) | The default target of every parse function |
| `TreeBuilder.start(tag, attrs)` | O(a) | O(a) | Creates the element and appends it to the open parent |
| `TreeBuilder.data(data)` | O(1) amortized | O(1) | Consecutive pieces are collected and joined once, when the element's `text` or `tail` is first read |
| `TreeBuilder.end(tag)` | O(1) | O(1) | Returns the element it closed |
| `TreeBuilder.comment(text)`, `TreeBuilder.pi(target, text=None)` | O(c) | O(c) | Added to the tree only with `insert_comments` or `insert_pis` |
| `TreeBuilder.close()` | O(1) | O(1) | Returns the root |
| `TreeBuilder.doctype(name, pubid, system)`, `TreeBuilder.start_ns(prefix, uri)`, `TreeBuilder.end_ns(prefix)` | O(c) | O(c) | Methods a custom target may define; `XMLParser` calls them when they exist, and the built-in `TreeBuilder` has none of them |

### Element

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.Element(tag, attrib={}, **extra)` | O(a) | O(a) | Copies `attrib`, so the dict you pass is not the element's |
| `ET.SubElement(parent, tag, attrib={}, **extra)` | O(a) amortized | O(a) | Creates the element and appends it |
| `Element.tag` | O(1) | O(1) | |
| `Element.text`, `Element.tail` | O(1), or O(c) on the first read | O(1), or O(c) on the first read | `None` when there is none; text parsed in several pieces is kept as the pieces and joined on its first read |
| `Element.attrib` | O(1) | O(1) | The element's own dict, not a copy |
| `Element.get(key, default=None)`, `Element.set(key, value)` | O(1) | O(1) | |
| `Element.keys()`, `Element.items()` | O(a) | O(a) | A new list on every call |
| `len(elem)`, `elem[index]`, `elem[index] = child` | O(1) | O(1) | The children are an array |
| `Element.append(subelement)` | O(1) amortized | O(1) | |
| `Element.extend(elements)` | O(m) amortized | O(m) | m = elements added; an iterable other than a list or tuple is copied into a list first |
| `Element.insert(index, subelement)`, `del elem[index]` | O(k) | O(1) | Shift the children after `index` |
| `Element.remove(subelement)` | O(k) | O(1) | Finds the child that is `subelement` - elements compare by identity - then shifts the rest; raises `ValueError` if it is not a child |
| `Element.clear()` | O(k + a) | O(1) | Drops the children, attributes, text and tail; the element itself stays in its parent |
| `Element.makeelement(tag, attrib)` | O(a) | O(a) | A new element of the same type, not attached to anything |
| `copy.copy(elem)` | O(k) | O(k) | The copy shares its children and its attribute dict with the original |
| `copy.deepcopy(elem)` | O(e + b) | O(e + b) | Copies every element and attribute dict of the subtree; the strings are shared |
| `Element.iter(tag=None)` | O(1) to create, O(e) to exhaust | O(d) | A lazy walk in document order that holds one entry per open level; `tag` filters, and `"*"` means every element |
| `Element.itertext()` | O(1) to create, O(e + n) to exhaust | O(d + c) | Yields the non-empty `text` and `tail` strings of the subtree in document order, joining any still in pieces as it reaches them |
| `Element.find(path, namespaces=None)` | As the path, stopping at the first match | As the path | See *Path expressions* |
| `Element.findall(path, namespaces=None)` | As the path | As the path, plus the list of matches | |
| `Element.findtext(path, default=None, namespaces=None)` | As `find()`, plus reading the match's `text` | As the path, plus that read | `""` for a match without text, `default` when nothing matches |
| `Element.iterfind(path, namespaces=None)` | As the path, spread over the iteration | As the path | Lazy |

### Path expressions

`find()`, `findall()`, `findtext()` and `iterfind()` take a path in a subset of XPath, and the path
decides the cost. Here `k` is the children of the element each step starts from and `e` the
elements beneath the element the search was called on.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tag`, `*`, `{uri}tag`, `{*}tag` | O(k) | O(1) | Direct children only: `find('item')` does not see a grandchild |
| `tag/child/...` | O(e) at most | O(1) | Each step scans the children of every element the step before it matched |
| `.//tag`, `.//*` | O(e) | O(d) | Walks the whole subtree in document order |
| `.` | O(1) | O(1) | |
| `..` | O(e) | O(e) | Maps every element under the search root to its parent, on every call |
| `[@attrib]`, `[@attrib='value']`, `[@attrib!='value']` | O(1) per candidate | O(1) | |
| `[tag]` | O(k) per candidate | O(1) | Scans the candidate's children |
| `[.='text']`, `[.!='text']`, `[tag='text']`, `[tag!='text']` | O(e + n) per candidate | O(n) | Joins all the text beneath the candidate, or beneath each matching child |
| `[position]`, `[last()]`, `[last()-1]` | O(e + k·g) | O(e) | g = distinct tags among the candidates under one parent. Builds the parent map, then scans the siblings once per parent and tag: O(e + k) when siblings share a tag, but `*[1]` over k differently tagged siblings is O(k²). Before Python 3.14.7, 3.13.15, 3.12.14, 3.11.16 and 3.10.21 the scan is once per candidate: O(e + k²) whatever the tags |

### ElementTree

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.ElementTree(element=None, file=None)` | O(1), or O(n) with `file` | O(1), or O(n) with `file` | A wrapper around one root element |
| `ElementTree.getroot()` | O(1) | O(1) | |
| `ElementTree._setroot(element)` | O(1) | O(1) | Replaces the root |
| `ElementTree.parse(source, parser=None)` | O(n) | O(n) | Replaces the root with the parsed one and returns it |
| `ElementTree.find()`, `ElementTree.findall()`, `ElementTree.findtext()`, `ElementTree.iterfind()` | As the root's | As the root's | A path starting with `/` warns with `FutureWarning` and is searched as `./` |
| `ElementTree.iter(tag=None)` | As `Element.iter()` | O(d) | |
| `ElementTree.write(file_or_filename, encoding=None, xml_declaration=None, default_namespace=None, method=None, *, short_empty_elements=True)` | O(n) | O(d + q + a + c) | Streams each piece to the file as it is produced, so it holds one element's attributes and one escaped text or value at a time; a first pass collects the names. `method` is `"xml"`, `"html"` or `"text"`; with `"text"`, elements that write nothing still cost their visit, so it is O(n + e) |
| `ElementTree.write_c14n(file)` | O(1) | O(1) | Raises `ValueError`: `"c14n"` is not an output method of `write()`. Use `canonicalize()` |

### Serialization

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.tostring(element, encoding=None, method=None, *, xml_declaration=None, default_namespace=None, short_empty_elements=True)` | O(n) | O(n) | `write()` into an in-memory buffer, so the whole output is held; `encoding="unicode"` returns a `str` |
| `ET.tostringlist(element, encoding=None, method=None, *, xml_declaration=None, default_namespace=None, short_empty_elements=True)` | O(n) | O(n) | The same output as a list instead of one object: the written pieces for `encoding="unicode"`, buffered chunks of bytes otherwise |
| `ET.dump(elem)` | O(n) | O(d + q + a + c) | Writes to `sys.stdout`; meant for debugging |
| `ET.indent(tree, space="  ", level=0)` | O(n + d²) | O(d²) | Rewrites whitespace-only `text` and `tail` in place, sharing one indentation string per level, each one level longer than the last |
| `ET.register_namespace(prefix, uri)` | O(r) | O(r) | r = registered prefixes; the registry is global, and a prefix of the form `ns<digits>` raises `ValueError` |
| `ET.canonicalize(xml_data=None, *, out=None, from_file=None, **options)` | O(n + r + (e + b)·(d + s) + b log a) | O(n + r), or O(d + s + a + c + r) with `out` | C14N 2.0, through a `C14NWriterTarget`. Every tag and attribute name is resolved by walking the open elements' namespace scopes - one step per open element and per namespace declaration in scope, s - and each element's attributes are sorted, which is the log term. `rewrite_prefixes=True` also keeps one prefix per distinct namespace URI |
| `ET.C14NWriterTarget(write, *, with_comments=False, strip_text=False, rewrite_prefixes=False, qname_aware_tags=None, qname_aware_attrs=None, exclude_attrs=None, exclude_tags=None)` | O(r) | O(r) | The parser target `canonicalize()` uses; copies the namespace registry unless `rewrite_prefixes` is set |
| `C14NWriterTarget.start(tag, attrs)` | O(c + (a + 1)·(d + s) + a log a) | O(c + a) | Writes any pending text, resolves and sorts the names, then writes the start tag |
| `C14NWriterTarget.end(tag)` | O(c + d + s) | O(c) | Writes any pending text, then the end tag |
| `C14NWriterTarget.data(data)` | O(1) amortized | O(1) | Pieces are joined and written at the next tag |
| `C14NWriterTarget.comment(text)`, `C14NWriterTarget.pi(target, data)` | O(c) | O(c) | Comments are written only with `with_comments` |
| `C14NWriterTarget.start_ns(prefix, uri)` | O(1) amortized | O(1) | |

### Other functions and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ET.Comment(text=None)` | O(1) | O(1) | An element whose tag is the `Comment` function; written as `<!--text-->` |
| `ET.ProcessingInstruction(target, text=None)`, `ET.PI(target, text=None)` | O(c) | O(c) | Joins `target` and `text` into the element's text |
| `ET.QName(text_or_uri, tag=None)` | O(c) | O(c) | Builds `{uri}tag`, and compares and hashes as that string |
| `ET.iselement(element)` | O(1) | O(1) | True for any object with a `tag` attribute |
| `ET.VERSION` | O(1) | O(1) | The ElementTree API version string |

## Parsing XML

### Whole Documents

`fromstring()` and `parse()` return only once the whole tree exists, so they cost the document in
time and the tree in memory. A malformed document raises `ParseError` at the fault.

```python
import io
import xml.etree.ElementTree as ET

document = "<catalog><book id='1'>A</book><book id='2'>B</book></catalog>"

root = ET.fromstring(document)  # O(n) - the whole tree is built here
assert root.tag == 'catalog' and len(root) == 2  # O(1)

tree = ET.parse(io.BytesIO(document.encode()))  # O(n) - a path works too
assert tree.getroot()[1].get('id') == '2'  # O(1)

try:
    ET.fromstring("<catalog><book></catalog>")
except ET.ParseError as error:
    assert error.position == (1, 17)  # (line, column) of the mismatched tag
else:
    raise AssertionError('malformed XML was parsed')
```

### Streaming a Large Document

`iterparse()` hands you each element as its end tag arrives, but it still attaches every element
to the tree it is building. `clear()` empties an element and leaves it in its parent, so a loop
that only clears still holds one element per record. Removing the finished record from its parent
is what keeps the tree small: it then holds the records of one 16 KiB read, not of the file.

```python
import io
import xml.etree.ElementTree as ET

document = "<log>" + "<entry><level>INFO</level></entry>" * 1000 + "</log>"

# clear() empties each record, but the emptied elements stay in the tree
root = None
for event, elem in ET.iterparse(io.StringIO(document), events=("start", "end")):
    if root is None:
        root = elem  # the first event is the root's start
    elif event == "end" and elem.tag == "entry":
        elem.clear()  # O(k + a)
assert len(root) == 1000  # one empty element per record is still held

# Removing each finished record keeps only the records of the current read
root = None
errors = 0
for event, elem in ET.iterparse(io.StringIO(document), events=("start", "end")):
    if root is None:
        root = elem
    elif event == "end" and elem.tag == "entry":
        errors += elem.findtext("level") == "ERROR"  # O(k)
        root.remove(elem)  # O(k), k = the records of one read
assert len(root) == 0 and errors == 0
```

### Feeding a Pull Parser

`XMLPullParser` is the same machinery without a file: you feed it bytes or text as they arrive,
and it queues an event for each element they complete. Events you do not read stay queued.

```python
import xml.etree.ElementTree as ET

parser = ET.XMLPullParser(events=("end",))  # O(1)
parser.feed("<feed><item>1</item><it")  # O(c) - parses what is complete
parser.flush()  # O(c) - parse anything the parser held back
assert [elem.text for _, elem in parser.read_events()] == ['1']

parser.feed("em>2</item></feed>")
parser.close()
assert [elem.tag for _, elem in parser.read_events()] == ['item', 'feed']
```

## Searching a Tree

### Children and Descendants

A bare tag, or a path of bare tags, looks only at direct children: its cost is the children it
scans, not the tree. `.//` walks the whole subtree, as `iter()` does. `find()` stops at its first
match either way.

```python
import xml.etree.ElementTree as ET

root = ET.fromstring(
    "<library><shelf><book>A</book><book>B</book></shelf><book>C</book></library>"
)

assert [book.text for book in root.findall('book')] == ['C']  # O(k) - children only
assert [book.text for book in root.findall('.//book')] == ['A', 'B', 'C']  # O(e)
assert root.find('.//book').text == 'A'  # stops at the first match
assert [book.text for book in root.iter('book')] == ['A', 'B', 'C']  # O(e), lazily
assert root.findtext('shelf/book') == 'A'  # O(k) per step
assert root.find('missing') is None
```

### Parents and Positions

An element does not know its parent. A path that needs one - `..`, or a position such as `[2]` -
first maps every element under the search root to its parent, and does so again on every call.
When you need many parents, build the map once.

```python
import xml.etree.ElementTree as ET

root = ET.fromstring("<r><a><b/></a><a><c/></a></r>")

assert [parent.tag for parent in root.findall('.//b/..')] == ['a']  # O(e)
assert root.find('a[2]/c') is not None  # O(e) - positions need the parent map too

parents = {child: parent for parent in root.iter() for child in parent}  # O(e), once
assert parents[root.find('a/b')] is root[0]  # O(1) per lookup afterwards
```

### Testing a Match

`find()` returns `None` when nothing matches, and an element with no children is false. Compare
the result with `None`; testing an element's truth value warns on Python 3.12+.

```python
import warnings
import xml.etree.ElementTree as ET

root = ET.fromstring("<r><empty/></r>")
match = root.find('empty')  # O(k)

assert match is not None  # the test to use
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    assert not match  # a found element with no children is false
```

## Modifying a Tree

The children of an element are an array. Appending is amortized O(1); inserting or removing
anywhere else shifts the children after that point. `remove()` finds its argument by identity, so
it removes that element and not an equal-looking one.

```python
import xml.etree.ElementTree as ET

root = ET.Element('list')
for n in range(3):
    ET.SubElement(root, 'item', n=str(n))  # O(a) amortized - appends

first = ET.Element('item', n='first')
root.insert(0, first)  # O(k) - shifts every child
assert [child.get('n') for child in root] == ['first', '0', '1', '2']
root.remove(first)  # O(k) - found by identity, then the rest shift back
assert len(root) == 3  # O(1)

attributes = {'n': 'x'}
item = ET.Element('item', attributes)  # O(a) - copies the dict
attributes['n'] = 'changed'
assert item.get('n') == 'x'
item.attrib['n'] = 'y'  # O(1) - attrib is the element's own dict
assert item.get('n') == 'y'
```

## Serializing a Tree

### Strings and Files

`tostring()` is `write()` into an in-memory buffer, so it holds the whole output. `write()` to a
file streams: besides the file's own buffer, it holds only the open levels, the names it has
seen and the piece it is writing. `indent()` rewrites whitespace in place before either.

```python
import io
import xml.etree.ElementTree as ET

root = ET.Element('r')
ET.SubElement(root, 'item', id='1').text = 'A & B'

assert ET.tostring(root) == b'<r><item id="1">A &amp; B</item></r>'  # O(n)
assert ET.tostring(root, encoding='unicode', method='text') == 'A & B'

buffer = io.BytesIO()
ET.ElementTree(root).write(buffer, encoding='utf-8', xml_declaration=True)  # O(n), streamed
assert buffer.getvalue().startswith(b"<?xml version='1.0' encoding='utf-8'?>\n<r>")

ET.indent(root)  # O(n + d²)
assert ET.tostring(root, encoding='unicode') == '<r>\n  <item id="1">A &amp; B</item>\n</r>'
```

### Deep Trees

Parsing and `iter()` keep their own stack, so a deeply nested document parses and walks at any
depth. Serializing and `indent()` recurse once per level, so a tree deeper than the recursion
limit raises `RecursionError` there.

```python
import sys
import xml.etree.ElementTree as ET

depth = sys.getrecursionlimit() + 100
root = ET.fromstring('<a>' * depth + '</a>' * depth)  # O(n) - no recursion
assert sum(1 for _ in root.iter()) == depth  # O(e) - no recursion either

try:
    ET.tostring(root)
except RecursionError:
    pass
else:
    raise AssertionError('a tree deeper than the recursion limit was serialized')
```

### Namespaces and Canonical XML

Registered prefixes are used when serializing. `canonicalize()` writes the C14N 2.0 form, which
sorts attributes and resolves every name against the namespace scopes open around it, so its
cost grows with depth as well as size.

```python
import xml.etree.ElementTree as ET

ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')  # O(r)
title = ET.Element('{http://purl.org/dc/elements/1.1/}title')
assert ET.tostring(title, encoding='unicode') == (
    '<dc:title xmlns:dc="http://purl.org/dc/elements/1.1/" />'
)

assert ET.canonicalize('<r b="2"  a="1"/>') == '<r a="1" b="2"></r>'  # O(n + r + (e + b)·(d + s) + b log a)
```

## Common Patterns

### Looking Up Elements by id

```python
import xml.etree.ElementTree as ET

root, ids = ET.XMLID("<r><p id='a'>1</p><p id='b'>2</p></r>")  # O(n), plus the map

assert ids['b'].text == '2'  # O(1) per lookup, instead of a search per id
assert ids['a'] is root[0]
```

### Building a Document from Records

```python
import xml.etree.ElementTree as ET

rows = [('alice', 30), ('bob', 25)]
root = ET.Element('people')

for name, age in rows:
    ET.SubElement(root, 'person', name=name).text = str(age)  # O(a) amortized

assert ET.tostring(root, encoding='unicode') == (
    '<people><person name="alice">30</person><person name="bob">25</person></people>'
)
```

## Performance Best Practices

✅ **Do**:

- Use `iterparse()` and remove each finished element from its parent when a document is larger
  than you want in memory
- Use `.//tag` or `iter(tag)` for descendants; a bare tag scans only direct children
- Build a parent map once when you need many parents; `..` and positions build one per call
- Write large output with `ElementTree.write()` to a file rather than `tostring()`
- Compare `find()` results with `None`
- Append children rather than inserting them at the front

❌ **Avoid**:

- `elem.clear()` alone in an `iterparse()` loop - the emptied elements stay attached
- `..` and positional predicates inside a loop over many elements
- Serializing or indenting trees deeper than the recursion limit
- `canonicalize()` on deeply nested documents - every name walks the open scopes
- Testing an element's truth value

## Version Notes

- **Python 3.14.7+, 3.13.15+, 3.12.14+, 3.11.16+, 3.10.21+**: Positional predicates scan each
  parent's children once per candidate tag, O(e + k·g), rather than once per candidate, O(e + k²)
- **Python 3.13+**: `iterparse()` iterators have `close()`
- **Python 3.13+, 3.12.3+, 3.11.9+, 3.10.14+**: Added `XMLParser.flush()` and
  `XMLPullParser.flush()`
- **Python 3.12+**: Testing an element's truth value emits `DeprecationWarning`

## Related Modules

- **[xml.sax](xml.sax.md)** - Event callbacks with no tree; memory follows the open elements, not
  the document
- **[xml.dom](xml.dom.md)** - The W3C DOM interface over a whole tree
- **[pyexpat](pyexpat.md)** - The Expat parser underneath every parse function here
- **[xml](xml.md)** - Overview of the XML packages
