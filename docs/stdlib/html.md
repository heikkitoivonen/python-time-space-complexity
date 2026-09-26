# html Module Complexity

The `html` package escapes and unescapes text for HTML, parses HTML into callbacks with
`html.parser.HTMLParser`, and ships the named character reference tables in `html.entities`.
`escape()` and `unescape()` are linear in the string. The parser is a push parser: it
builds no tree, calls one of your methods for each tag, text run, comment or declaration, and
holds only the input it has not parsed yet, plus the text of the last start tag.

`n` is the characters of the input: the string passed to `escape()` or `unescape()`, or all the
HTML fed to one parser. `d` is the characters passed to one `feed()` call, and `b` is the
characters a parser is holding unparsed from earlier calls - typically a tag, comment, script or
character reference that was cut off at the end of a chunk. Parser bounds exclude the cost of your
handler methods; the parser makes a number of handler calls linear in its input, and whatever
they do is added on top. The entity tables have a fixed size, so a lookup in one is O(1).

## Complexity Reference

### escape and unescape

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `html.escape(s, quote=True)` | O(n) | O(n) | Replaces `&`, `<` and `>`, and with `quote` both quote characters; the output is at most six times the input |
| `html.unescape(s)` | O(n) | O(n) | HTML5 rules for named and numeric references; a string with no `&` is returned as the same object |

### HTMLParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `html.parser.HTMLParser(*, convert_charrefs=True)` | O(1) | O(1) | Holds nothing until `feed()` |
| `HTMLParser.feed(data)` | O(d + b) | O(d + b) | Parses what it can and keeps the unparsed tail; a document fed in one call costs O(n), and for one fed in chunks see *Feeding in Chunks* |
| `HTMLParser.close()` | O(b) | O(b) | Parses whatever is still held as if the input ended there; call it once at the end |
| `HTMLParser.reset()` | O(1) | O(1) | Discards anything held; the parser can take a new document |
| `HTMLParser.getpos()` | O(1) | O(1) | `(line, offset)` of the construct being handled, kept up to date as the parser consumes input |
| `HTMLParser.get_starttag_text()` | O(1) | O(1) | The source of the start tag parsed last, stored when it was parsed; `None` before the first, and a start tag cut off at the end of a chunk can reset it to `None` |
| `HTMLParser.convert_charrefs` | O(1) | O(1) | When true, text arrives in `handle_data()` with references already converted; when false, they go to `handle_entityref()` and `handle_charref()`. Inside `script`, `style` and the like, references stay as text either way |
| `HTMLParser.CDATA_CONTENT_ELEMENTS`, `HTMLParser.RCDATA_CONTENT_ELEMENTS` | O(1) | O(1) | Tag names whose content is not parsed for tags: `script`, `style` and similar arrive as raw text, and in `textarea` and `title` only references are recognised |

### HTMLParser handlers

Override these in a subclass. Each default does nothing, or in one case calls two others, so the
cost of a handler is whatever your override does.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HTMLParser.handle_starttag(tag, attrs)` | O(1) | O(1) | `tag` is lower-cased; `attrs` is a list of `(name, value)` pairs with references in values converted |
| `HTMLParser.handle_endtag(tag)` | O(1) | O(1) | Also called by the default `handle_startendtag()` |
| `HTMLParser.handle_startendtag(tag, attrs)` | O(1) | O(1) | For `<br/>`-style tags; the default calls `handle_starttag()` then `handle_endtag()` |
| `HTMLParser.handle_data(data)` | O(1) | O(1) | Text between tags; one run of text can arrive in several calls |
| `HTMLParser.handle_entityref(name)`, `HTMLParser.handle_charref(name)` | O(1) | O(1) | Only when `convert_charrefs` is false |
| `HTMLParser.handle_comment(data)` | O(1) | O(1) | The text inside `<!--` and `-->` |
| `HTMLParser.handle_decl(decl)` | O(1) | O(1) | A doctype, without `<!` and `>` |
| `HTMLParser.handle_pi(data)` | O(1) | O(1) | A processing instruction, without `<?` and `>` |
| `HTMLParser.unknown_decl(data)` | O(1) | O(1) | A `<![CDATA[...]]>` section, passed as `CDATA[...` |

### html.entities

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `html.entities.html5` | O(1) | O(1) | Every HTML5 named reference, keyed with its `;` and, where HTML5 allows it, without; what `unescape()` uses |
| `html.entities.name2codepoint` | O(1) | O(1) | The HTML 4 entity names mapped to code points |
| `html.entities.codepoint2name` | O(1) | O(1) | The reverse of `name2codepoint` |
| `html.entities.entitydefs` | O(1) | O(1) | The HTML 4 entity names mapped to their characters |

## Escaping and Unescaping

### Escaping Text for HTML

`escape()` is linear in the text and copies it once per character class it replaces. The default
also escapes both quote characters, which is what makes the result safe inside an attribute
value in quotes; `quote=False` is only for text between tags.

```python
from html import escape

text = '<script>alert("XSS")</script>'

escaped = escape(text)  # O(n)
assert escaped == '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'

assert escape("it's") == 'it&#x27;s'  # O(n) - quote=True covers both quotes
assert escape('Hello "World"', quote=False) == 'Hello "World"'  # O(n)
```

### Unescaping Character References

`unescape()` follows the HTML5 rules, including names written without their `;` and numeric
references outside the valid range. It checks for `&` first and returns the input itself when
there is none, so there is nothing to gain by checking before calling it.

```python
from html import unescape

escaped = '&lt;p&gt;Hello &amp; goodbye&lt;/p&gt;'
assert unescape(escaped) == '<p>Hello & goodbye</p>'  # O(n)

assert unescape('&copy; &nbsp; &#169; &#x00A9;') == '© \xa0 © ©'

# Names without their semicolon, as HTML5 allows for some of them
assert unescape('&amp &copy2024') == '& ©2024'

plain = 'no references here'
assert unescape(plain) is plain  # O(n) scan for '&', no copy
```

## Parsing HTML

### Feeding a Document

`feed()` scans its input once and calls a handler for each construct it finds, so a document
costs O(n) plus whatever the handlers do. Apart from the last start tag's text, nothing is kept
once it has been handed to a handler: if you want a result, the handler has to store it.

```python
from html.parser import HTMLParser

class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):  # once per start tag
        if tag == 'a':
            self.links.extend(value for name, value in attrs if name == 'href')

page = '''
<html>
    <a href="/page1">Link 1</a>
    <A HREF="/page2?a=1&amp;b=2">Link 2</A>
</html>
'''

parser = LinkCollector()  # O(1)
parser.feed(page)  # O(n)
parser.close()  # O(b)
assert parser.links == ['/page1', '/page2?a=1&b=2']  # tags lower-cased, references converted
```

### Feeding in Chunks

A chunk can end in the middle of a tag. The parser keeps that unparsed tail, `b` characters of it,
and parses it again together with the next chunk, so memory follows the longest construct left
open rather than the document. On the releases in *Version Notes* a construct left open across many
small chunks still costs O(n) in total; on earlier ones every call rescans the held tail, which
makes that O(n²). `close()` treats whatever is still held as the end of the
input. Always call it: until then the parser may be holding text back, and a handler may not
have run for input that has already been fed.

```python
from html.parser import HTMLParser

class Recorder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(('start', tag, attrs))

    def handle_data(self, data):
        self.events.append(('data', data))

parser = Recorder()
parser.feed('<p>one</p><a hr')  # O(d + b) - the cut-off tag is held
parser.feed('ef="/x">two')  # O(d + b)
parser.close()  # O(b)

assert parser.events == [
    ('start', 'p', []),
    ('data', 'one'),
    ('start', 'a', [('href', '/x')]),
    ('data', 'two'),
]
```

### Character References in Text

With `convert_charrefs=True`, the default, references in text are converted before
`handle_data()` sees it, so they do not split the text. With `convert_charrefs=False`
the text is split at every reference, and each reference is a separate handler call. Attribute
values are converted either way.

```python
from html.parser import HTMLParser

class Recorder(HTMLParser):
    def __init__(self, **options):
        super().__init__(**options)
        self.events = []

    def handle_data(self, data):
        self.events.append(('data', data))

    def handle_entityref(self, name):
        self.events.append(('entity', name))

    def handle_charref(self, name):
        self.events.append(('char', name))

converted = Recorder()
converted.feed('<p>Fish &amp; chips &#169;</p>')
converted.close()
assert converted.events == [('data', 'Fish & chips ©')]

raw = Recorder(convert_charrefs=False)
raw.feed('<p>Fish &amp; chips &#169;</p>')
raw.close()
assert raw.events == [
    ('data', 'Fish '), ('entity', 'amp'), ('data', ' chips '), ('char', '169'),
]
```

### Script and Style Content

Inside the elements named in `CDATA_CONTENT_ELEMENTS` the parser looks only for the matching end
tag, so a `<` in a script is text, not a tag.

```python
from html.parser import HTMLParser

class Recorder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(('start', tag))

    def handle_endtag(self, tag):
        self.events.append(('end', tag))

    def handle_data(self, data):
        self.events.append(('data', data))

parser = Recorder()
parser.feed('<script>if (a<b) { x = "<b>"; }</script>')
parser.close()

assert parser.events == [
    ('start', 'script'), ('data', 'if (a<b) { x = "<b>"; }'), ('end', 'script'),
]
assert 'script' in HTMLParser.CDATA_CONTENT_ELEMENTS
assert 'title' in HTMLParser.RCDATA_CONTENT_ELEMENTS
```

### Comments, Declarations and Positions

Every construct has its own handler, and `getpos()` and `get_starttag_text()` read values the
parser already keeps, so asking for them inside a handler costs nothing extra.

```python
from html.parser import HTMLParser

class Recorder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(('start', tag, self.getpos(), self.get_starttag_text()))  # O(1)

    def handle_endtag(self, tag):
        self.events.append(('end', tag))

    def handle_comment(self, data):
        self.events.append(('comment', data))

    def handle_decl(self, decl):
        self.events.append(('decl', decl))

    def handle_pi(self, data):
        self.events.append(('pi', data))

    def unknown_decl(self, data):
        self.events.append(('unknown', data))

parser = Recorder()
parser.feed('<!DOCTYPE html>\n<?xml-stylesheet href="s.css"?>\n<!-- note -->\n')
parser.feed('<IMG SRC="a.png"/><![CDATA[raw]]>')
parser.close()

assert parser.events == [
    ('decl', 'DOCTYPE html'),
    ('pi', 'xml-stylesheet href="s.css"?'),
    ('comment', ' note '),
    ('start', 'img', (4, 0), '<IMG SRC="a.png"/>'),  # handle_startendtag's default
    ('end', 'img'),
    ('unknown', 'CDATA[raw'),
]

parser.reset()  # O(1) - ready for another document
assert parser.getpos() == (1, 0)
```

## Entity Tables

`html.entities` is data. The tables are dictionaries built once at import, so every lookup is a
dict lookup. `html5` is the complete HTML5 list; the other three cover only the HTML 4 names.

```python
from html.entities import codepoint2name, entitydefs, html5, name2codepoint

assert html5['amp;'] == '&'  # O(1)
assert html5['amp'] == '&'  # this name is also valid without its semicolon
assert html5['NotEqualTilde;'] == '≂̸'  # some names map to two characters
assert 'NotEqualTilde;' not in entitydefs  # HTML5-only names are not in the HTML 4 tables

assert name2codepoint['copy'] == 0xA9  # O(1)
assert codepoint2name[0xA9] == 'copy'  # O(1)
assert entitydefs['copy'] == '©'  # O(1)
```

## Common Patterns

### Extracting Text

```python
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(' '.join(data.split()))  # O(length of the text)

    def text(self):
        return ' '.join(self.parts)  # O(length of the kept text)

extractor = TextExtractor()
extractor.feed('''
<html>
    <head><title>Page</title></head>
    <body>
        <h1>Hello World</h1>
        <p>This is a &amp; test</p>
        <script>alert('hidden');</script>
    </body>
</html>
''')  # O(n)
extractor.close()
assert extractor.text() == 'Page Hello World This is a & test'
```

### Building HTML Safely

Escape each piece of untrusted text once, where it is inserted. Every `escape()` is linear in its
own argument, so building the page is linear in everything that goes into it. Escaping keeps a
URL from breaking out of its attribute, but does not check its scheme; a `javascript:` URL comes
through unchanged.

```python
from html import escape

def build_page(title, links):
    items = ''.join(
        f'<li><a href="{escape(url)}">{escape(label)}</a></li>'  # O(length of each piece)
        for url, label in links
    )
    return f'<title>{escape(title)}</title><ul>{items}</ul>'

page = build_page('My <Site>', [('/?q=1&r="2"', 'Search & find')])
assert page == (
    '<title>My &lt;Site&gt;</title>'
    '<ul><li><a href="/?q=1&amp;r=&quot;2&quot;">Search &amp; find</a></li></ul>'
)
```

## Performance Best Practices

✅ **Do**:

- Call `unescape()` unconditionally; it already returns a string with no `&` untouched
- Feed a parser chunks as they arrive; it holds only the construct left open, not the document
- Call `close()` after the last `feed()`, so held text is parsed as the end of the input
- Store what you need inside the handlers: the parser keeps nothing it has handled but the last
  start tag

❌ **Avoid**:

- Reading a whole file into one string just to feed it; the parser does not need it all at once
- `convert_charrefs=False` unless you need the references themselves; it splits text into more
  handler calls

## Version Notes

- **Python 3.10.21, 3.11.16, 3.12.14, 3.13.15, 3.14.7+**: When `feed()` cannot parse anything
  new, it waits for the held text to double before scanning it again, so feeding a construct that
  stays open across many small chunks is O(n) in total. Earlier releases rescan it on every call,
  which is O(n²) for that pattern.
- **All Python 3**: `escape()` escapes quotes by default; pass `quote=False` only for text
  between tags

## Related Modules

- **[xml](xml.md)** - Tree and event parsers for well-formed XML
- **[urllib](urllib.md)** - Quoting URL components, which `escape()` does not do
- **[re](re.md)** - Pattern matching, for text rather than markup
