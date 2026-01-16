# urllib Module Complexity

The `urllib` module provides utilities for working with URLs, including fetching web resources, parsing URL components, and handling URL encoding.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `urllib.parse.urlparse()` | O(n) | O(n) | n = URL length |
| `urllib.parse.urlencode()` | O(n*m) | O(n*m) | n = items, m = avg value length |
| `urllib.parse.quote()` | O(n) | O(n) | n = string length |
| `urllib.parse.unquote()` | O(n) | O(n) | n = string length |
| `urllib.request.urlopen()` | O(response) | O(response) | Depends on network/response |
| `response.read()` | O(n) | O(n) | n = response size |

## URL Parsing

### Parsing URLs

```python
from urllib.parse import urlparse

# Parse URL - O(n) where n = URL length
url = "https://user:pass@example.com:8080/path?query=1#fragment"
parsed = urlparse(url)  # O(len(url))

# Access components - O(1)
scheme   = parsed.scheme    # 'https'
netloc   = parsed.netloc    # 'user:pass@example.com:8080'
hostname = parsed.hostname  # 'example.com'
port     = parsed.port      # 8080
path     = parsed.path      # '/path'
query    = parsed.query     # 'query=1'
fragment = parsed.fragment  # 'fragment'
```

### URL Components

```python
from urllib.parse import urlparse

# Simple URL parsing - O(n)
url = "https://example.com/path?key=value"
result = urlparse(url)

# Extract parts - O(1) per access
result.scheme   # 'https'
result.netloc   # 'example.com'
result.path     # '/path'
result.query    # 'key=value'
result.fragment # ''
result.username # None
result.password # None
```

## Query String Handling

### Encoding Query Parameters

```python
from urllib.parse import urlencode, quote, quote_plus

# Encode parameters - O(n*m) where n = items, m = avg value length
params = {'name': 'Alice', 'age': '30', 'city': 'NYC'}
query_string = urlencode(params)  # O(3 * avg_length)
# Result: 'name=Alice&age=30&city=NYC'

# Use in URL - O(len(query_string))
url = f"https://example.com/search?{query_string}"
```

### Quoting and Unquoting

```python
from urllib.parse import quote, unquote, quote_plus

# Encode special characters - O(n)
text = "hello world & stuff"
encoded = quote(text)  # O(len(text))
# Result: 'hello%20world%20%26%20stuff'

# With + for spaces - O(n)
encoded = quote_plus(text)  # O(len(text))
# Result: 'hello+world+%26+stuff'

# Decode - O(n)
original = unquote(encoded)  # O(len(encoded))
# Result: 'hello world & stuff'
```

### Parsing Query Strings

```python
from urllib.parse import parse_qs, parse_qsl

# Parse query string - O(n*m)
query = "name=Alice&age=30&city=NYC&city=LA"
params = parse_qs(query)  # O(n) to parse, O(m) total keys
# Result: {'name': ['Alice'], 'age': ['30'], 'city': ['NYC', 'LA']}

# As list of tuples - O(n*m)
params_list = parse_qsl(query)  # O(n*m)
# Result: [('name', 'Alice'), ('age', '30'), ('city', 'NYC'), ('city', 'LA')]
```

## Fetching URLs

### Basic URL Fetching

```python
from urllib.request import urlopen

# Open URL and fetch content - O(response_size)
try:
    with urlopen('https://example.com') as response:  # O(network)
        content = response.read()  # O(n) - n = response size
except Exception as e:
    print(f"Error: {e}")

# Access response metadata - O(1)
status = response.status  # 200
headers = response.headers  # dict-like
```

### Reading Response Content

```python
from urllib.request import urlopen

# Fetch and read HTML - O(n)
with urlopen('https://example.com') as response:
    html = response.read()  # O(n) - n = HTML size
    text = html.decode('utf-8')  # O(n) - decoding

# Read as text (convenience) - O(n)
with urlopen('https://example.com') as response:
    text = response.read().decode('utf-8')  # O(n)
```

### Line-by-Line Reading

```python
from urllib.request import urlopen

# Stream content line-by-line - O(1) memory per line
with urlopen('https://example.com') as response:
    for line in response:  # O(1) memory, O(line_size) time per line
        process_line(line)

# Better for large responses
```

## Working with Requests

### Custom Headers

```python
from urllib.request import Request, urlopen

# Create request with headers - O(n)
headers = {
    'User-Agent': 'MyBot/1.0',
    'Accept': 'text/html'
}
req = Request('https://example.com', headers=headers)  # O(n)

# Fetch with custom request - O(response)
with urlopen(req) as response:  # O(network)
    content = response.read()  # O(n)
```

### POST Requests

```python
from urllib.request import Request, urlopen
from urllib.parse import urlencode

# Prepare POST data - O(n*m)
data = {'username': 'alice', 'password': 'secret'}
encoded_data = urlencode(data).encode('utf-8')  # O(n*m)

# Create POST request - O(n)
req = Request('https://example.com/login',
              data=encoded_data,  # POST body
              method='POST')  # O(n)

# Send request - O(response)
with urlopen(req) as response:  # O(network)
    result = response.read()  # O(n)
```

## Error Handling

### Handling HTTP Errors

```python
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

# Handle errors
try:
    with urlopen('https://example.com/notfound') as response:
        content = response.read()
except HTTPError as e:
    print(f"HTTP Error: {e.code}")  # 404, etc.
except URLError as e:
    print(f"URL Error: {e.reason}")  # Network error
```

## Advanced URL Operations

### URL Joining

```python
from urllib.parse import urljoin

# Join base URL with relative path - O(n)
base = 'https://example.com/docs/guide/'
relative = '../api/reference.html'
full_url = urljoin(base, relative)  # O(n)
# Result: 'https://example.com/docs/api/reference.html'

# Handle absolute paths
absolute = '/other/page.html'
full_url = urljoin(base, absolute)  # O(n)
# Result: 'https://example.com/other/page.html'
```

### Splitting URLs

```python
from urllib.parse import urlsplit, urlunsplit

# Split URL into parts - O(n)
url = 'https://example.com/path?query=1#frag'
parts = urlsplit(url)  # O(n)
# (scheme, netloc, path, query, fragment)

# Reconstruct URL - O(n)
new_url = urlunsplit(parts)  # O(n)
# Result: original URL
```

## Common Patterns

### Fetch and Parse HTML

```python
from urllib.request import urlopen
from urllib.parse import urljoin

# Fetch HTML and process - O(n)
with urlopen('https://example.com') as response:
    html = response.read().decode('utf-8')  # O(n)

# Parse relative URLs in HTML - O(n*m)
import re
base = 'https://example.com/'
links = re.findall(r'href=["\']([^"\']+)["\']', html)  # O(n)

# Convert to absolute URLs - O(m * k)
absolute_links = [urljoin(base, link) for link in links]  # O(m*k)
```

### Build Query URLs

```python
from urllib.parse import urlencode, urljoin

# Build search URL - O(n*m)
base_url = 'https://api.example.com/search'
params = {
    'q': 'python programming',
    'sort': 'relevance',
    'limit': '10'
}

# Method 1: urlencode - O(n*m)
query_string = urlencode(params)  # O(n*m)
full_url = f"{base_url}?{query_string}"

# Method 2: urljoin - O(k)
from urllib.parse import urlparse
parsed = urlparse(base_url)
full_url = f"{base_url}?{query_string}"
```

### Retry Logic

```python
from urllib.request import urlopen
from urllib.error import URLError
import time

def fetch_with_retry(url, max_retries=3):
    """Fetch URL with retry - O(response) per attempt"""
    for attempt in range(max_retries):
        try:
            with urlopen(url) as response:  # O(response)
                return response.read()
        except URLError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            time.sleep(wait_time)
    
# Usage
content = fetch_with_retry('https://example.com')  # O(response)
```

## Limitations and Alternatives

### When to Use requests Library

```python
# urllib is built-in but basic
# For more features, use requests library (not built-in)

# urllib - basic, manual handling
from urllib.request import urlopen
response = urlopen('https://api.example.com/data')
data = response.read()

# requests - higher-level, more convenient
import requests  # Must install: pip install requests
response = requests.get('https://api.example.com/data')
data = response.json()  # Auto JSON parsing
```

## Performance Considerations

### Batch Fetching

```python
from urllib.request import urlopen
import concurrent.futures

# Sequential fetching - O(n * response_avg)
urls = ['https://example.com/1', 'https://example.com/2']
for url in urls:
    with urlopen(url) as response:  # O(response)
        content = response.read()

# Parallel fetching with threads - O(response_max) with overhead
def fetch(url):
    with urlopen(url) as response:
        return response.read()

with concurrent.futures.ThreadPoolExecutor() as executor:
    contents = list(executor.map(fetch, urls))  # Faster overall
```

### Caching

```python
from urllib.request import urlopen
import hashlib

cache = {}

def fetch_cached(url):
    """Fetch URL with simple caching - O(response) first time, O(1) cached"""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    
    if url_hash in cache:
        return cache[url_hash]  # O(1)
    
    with urlopen(url) as response:  # O(response)
        content = response.read()
    
    cache[url_hash] = content
    return content

# First call - O(response)
content1 = fetch_cached('https://example.com')

# Second call - O(1)
content2 = fetch_cached('https://example.com')
```

## Version Notes

- **Python 2.x**: `urllib` and `urllib2` separate modules
- **Python 3.x**: `urllib.request`, `urllib.parse`, `urllib.error` (reorganized)
- **All versions**: Basic functionality stable

## Related Modules

- **[http.client](http.md)** - Lower-level HTTP client
- **[json](json.md)** - Parse JSON responses
- **[requests](requests.md)** - Higher-level HTTP library (external)

## Best Practices

✅ **Do**:
- Use context managers (`with`) for proper cleanup
- Always specify encoding when decoding bytes
- Handle URLError and HTTPError exceptions
- Use appropriate Content-Type headers for POST
- Validate and sanitize URLs before fetching
- Use query parameters via urlencode, not string concatenation

❌ **Avoid**:
- Fetching untrusted URLs without validation
- Ignoring SSL certificate errors (security risk)
- Manual URL string construction (use urlencode)
- Fetching large files without streaming
- Ignoring timeout possibilities (use requests library for easier timeout)
- Decoding responses without checking encoding
