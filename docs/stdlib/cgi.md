# cgi Module

⚠️ **REMOVED IN PYTHON 3.13**: The `cgi` module was deprecated in Python 3.11 and removed in Python 3.13.

The `cgi` module provides utilities for parsing CGI (Common Gateway Interface) form data and query strings.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `parse_qs()` | O(n) | O(n) | n = query string length |
| `parse_qsl()` | O(n) | O(n) | n = query string length |
| `FieldStorage` | O(n) | O(n) | n = form data size |
| URL decoding | O(n) | O(n) | n = string length |

## Parsing Query Strings

### Query String Parsing

```python
from urllib.parse import parse_qs, parse_qsl

# Modern approach (use urllib.parse instead)
query_string = "name=John&age=30&hobbies=reading&hobbies=gaming"

# Parse as dict (values are lists) - O(n)
params = parse_qs(query_string)
print(params)  # {'name': ['John'], 'age': ['30'], 'hobbies': ['reading', 'gaming']}

# Parse as list of tuples - O(n)
params_list = parse_qsl(query_string)
print(params_list)  # [('name', 'John'), ('age', '30'), ('hobbies', 'reading'), ('hobbies', 'gaming')]
```

## Form Data Handling

### FieldStorage (Deprecated)

```python
import cgi

# Parse form data - O(n)
# In production, use Python's built-in wsgiref or modern frameworks
form = cgi.FieldStorage()

# Access form fields
if 'username' in form:
    username = form.getvalue('username')

# Access file uploads
if 'file' in form:
    fileitem = form['file']
    if fileitem.filename:
        filename = fileitem.filename
        content = fileitem.file.read()
```

## URL Encoding/Decoding

### Escape Functions

```python
import cgi
from html import escape
from urllib.parse import quote, unquote

# Escape HTML - O(n)
user_input = '<script>alert("xss")</script>'
safe = escape(user_input)
# Result: &lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;

# URL encoding - O(n)
text = "hello world & special chars!"
encoded = quote(text)
decoded = unquote(encoded)
```

## Common Patterns (Legacy)

### CGI Script Template

```python
#!/usr/bin/env python3

import cgi
import sys

def main():
    # Print HTTP header
    print("Content-Type: text/html\n")
    
    # Parse form data - O(n)
    form = cgi.FieldStorage()
    
    # Get parameters
    name = form.getvalue('name', 'Guest')
    
    # Generate response
    from html import escape
    print(f"<h1>Hello, {escape(name)}!</h1>")

if __name__ == "__main__":
    main()
```

### Error Handling

```python
import cgi
import traceback

def handle_request():
    try:
        form = cgi.FieldStorage()
        # Process form
        print("Content-Type: text/html\n")
        print("<h1>Success</h1>")
    except Exception as e:
        # Print error page
        print("Content-Type: text/html\n")
        print(f"<h1>Error</h1><pre>")
        traceback.print_exc()
        print("</pre>")

handle_request()
```

## Modern Alternatives

### Using urllib.parse

```python
from urllib.parse import parse_qs, parse_qsl, urlencode, quote, unquote

# Parse query string - O(n)
query = "name=John&age=30"
params = parse_qs(query)

# Encode parameters - O(n)
data = {'name': 'John', 'age': '30'}
encoded = urlencode(data)

# URL encoding - O(n)
text = "special chars: @ # $"
quoted = quote(text)
unquoted = unquote(quoted)
```

### Using WSGI

```python
from urllib.parse import parse_qs

def application(environ, start_response):
    # Get query string - O(n)
    query_string = environ.get('QUERY_STRING', '')
    params = parse_qs(query_string)
    
    # Process request
    response = b"Hello World"
    
    status = '200 OK'
    headers = [('Content-Type', 'text/plain')]
    start_response(status, headers)
    
    return [response]
```

### Using Modern Framework

```python
# Using Flask (recommended for CGI-like functionality)
from flask import Flask, request

app = Flask(__name__)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    name = request.args.get('name', 'Guest')
    age = request.form.get('age', 'Unknown')
    
    return f"<h1>Hello {name}, age {age}</h1>"

if __name__ == '__main__':
    app.run()
```

## Removal Notice

```python
# ❌ DON'T: Use cgi module (removed in 3.13)
import cgi
form = cgi.FieldStorage()

# ✅ DO: Use modern alternatives
# - urllib.parse for query strings
# - wsgiref for WSGI applications
# - Flask/Django for web applications
# - FastAPI for modern async applications
```

## Related Modules

- [urllib.parse Module](urllib.md) - URL parsing and encoding
- [html Module](html.md) - HTML utilities
- [urllib.request Module](urllib.md) - URL requests
- [wsgiref Module](wsgiref.md) - WSGI reference implementation
