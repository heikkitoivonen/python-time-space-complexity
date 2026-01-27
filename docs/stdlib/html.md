# Html Module

The `html` module provides utilities for working with HTML content, including escaping and unescaping text.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `escape(text)` | O(n) | O(n) | n = string length |
| `unescape(text)` | O(n) | O(n) | n = string length |
| `html.parser.HTMLParser()` | O(1) | O(1) | Parser construction |
| `HTMLParser.feed(text)` | O(n) | O(1) | n = text length; extra space depends on handlers |

## Common Operations

### Escaping HTML

```python
from html import escape

text = '<script>alert("XSS")</script>'

# O(n) where n = string length
escaped = escape(text)
# Returns: &lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;

# With quote escaping - O(n)
escaped_with_quotes = escape(text, quote=True)
# Same result by default (quote=True)

# Without quote escaping - O(n)
no_quote = escape('Hello "World"', quote=False)
# Returns: Hello "World"
```

### Unescaping HTML

```python
from html import unescape

escaped = '&lt;p&gt;Hello &amp; goodbye&lt;/p&gt;'

# O(n) where n = string length
unescaped = unescape(escaped)
# Returns: <p>Hello & goodbye</p>

# Common entities - O(n)
entities = '&copy; &nbsp; &#169; &#x00A9;'
result = unescape(entities)
# Returns: ©  © ©
```

## Common Use Cases

### Sanitizing User Input

```python
from html import escape

def sanitize_for_html(user_input):
    """Escape user input for safe HTML display - O(n)"""
    # O(n) where n = input length
    return escape(user_input)

# Usage
user_text = '<img src=x onerror="alert(1)">'
safe = sanitize_for_html(user_text)
# &lt;img src=x onerror=&quot;alert(1)&quot;&gt;

# Safe to include in HTML
html = f'<p>{safe}</p>'
```

### Parsing HTML

```python
from html.parser import HTMLParser

class MyHTMLParser(HTMLParser):
    """Extract links from HTML - O(n)"""
    
    def __init__(self):
        super().__init__()
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        """Called for opening tags - O(1) per tag"""
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    self.links.append(value)

# Usage - O(n) where n = HTML length
parser = MyHTMLParser()
html = '''
<html>
    <a href="/page1">Link 1</a>
    <a href="/page2">Link 2</a>
</html>
'''
parser.feed(html)  # O(n)
print(parser.links)  # ['/page1', '/page2']
```

### Extracting Text from HTML

```python
from html.parser import HTMLParser
from html import unescape

class TextExtractor(HTMLParser):
    """Extract plain text from HTML - O(n)"""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_script = False
        self.in_style = False
    
    def handle_starttag(self, tag, attrs):
        """Track script/style tags - O(1)"""
        if tag in ('script', 'style'):
            self.in_script = tag == 'script'
            self.in_style = tag == 'style'
    
    def handle_endtag(self, tag):
        """O(1)"""
        if tag in ('script', 'style'):
            self.in_script = False
            self.in_style = False
    
    def handle_data(self, data):
        """Collect text - O(1) append, O(n) for data"""
        if not self.in_script and not self.in_style:
            # Strip whitespace - O(k) where k = data length
            text = data.strip()
            if text:
                self.text_parts.append(text)
    
    def get_text(self):
        """O(n) to join - n = total characters"""
        return ' '.join(self.text_parts)

# Usage - O(n) where n = HTML length
extractor = TextExtractor()
html = '''
<html>
    <head><title>Page</title></head>
    <body>
        <h1>Hello World</h1>
        <p>This is a &nbsp; test</p>
        <script>alert('hidden');</script>
    </body>
</html>
'''
extractor.feed(html)  # O(n)
text = extractor.get_text()  # O(k) where k = text length
# "Page Hello World This is a test"
```

### Building HTML Safely

```python
from html import escape

def build_html_page(title, content, links):
    """Build HTML page with escaped content - O(n)"""
    # O(n) for each escape where n = string length
    safe_title = escape(title)
    safe_content = escape(content)
    
    # O(k) to build link HTML where k = link count
    link_html = ''.join(
        f'<a href="{escape(url)}">{escape(text)}</a>'
        for url, text in links
    )
    
    # O(total) to combine
    return f'''
    <html>
        <head><title>{safe_title}</title></head>
        <body>
            <h1>{safe_title}</h1>
            <p>{safe_content}</p>
            <nav>{link_html}</nav>
        </body>
    </html>
    '''

# Usage - O(n) total where n = total characters
html = build_html_page(
    "My <Site>",
    "User input & special chars",
    [("/?search=test&q=1", "Search")]
)
```

## Performance Tips

### Batch Escaping

```python
from html import escape

# Bad: Multiple escape calls
html_parts = []
for item in items:
    html_parts.append(f'<li>{escape(item)}</li>')
result = ''.join(html_parts)  # O(n) for each item

# Good: Single escape with formatting
html_parts = [f'<li>{escape(item)}</li>' for item in items]
result = ''.join(html_parts)  # O(n) total
```

### Cache Escaped Strings

```python
from html import escape

class HtmlBuilder:
    """Cache escaped strings - O(1) lookup after escape"""
    
    def __init__(self):
        self._escaped_cache = {}
    
    def get_escaped(self, text):
        """O(n) first time, O(1) cached"""
        if text not in self._escaped_cache:
            # O(n) where n = text length
            self._escaped_cache[text] = escape(text)
        return self._escaped_cache[text]

# Usage
builder = HtmlBuilder()
escaped = builder.get_escaped("Hello & Goodbye")  # O(n)
escaped = builder.get_escaped("Hello & Goodbye")  # O(1) - cached
```

### Use unescape Sparingly

```python
from html import unescape

# Bad: Unescape every lookup
def get_title(attrs):
    for name, value in attrs:
        if name == 'title':
            return unescape(value)  # O(n)

# Good: Only unescape when needed
def get_title_safe(attrs):
    for name, value in attrs:
        if name == 'title':
            # Only unescape if it contains entities
            if '&' in value:
                return unescape(value)  # O(n)
            return value  # O(1)
```

## Version Notes

- **Python 3.x**: `html.escape`, `html.unescape`, and `html.parser` are available

## Related Documentation

- [Re Module](re.md) - Pattern matching for HTML
- [Urllib Module](urllib.md) - URL handling
- [Json Module](json.md) - Data serialization
