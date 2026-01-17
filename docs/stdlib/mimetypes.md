# Mimetypes Module

The `mimetypes` module provides support for working with MIME types, mapping filenames and URLs to MIME types.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `init()` | O(n) | O(n) | n = type database size |
| `guess_type(url)` | O(1) | O(1) | Lookup MIME type |
| `guess_extension(type)` | O(1) | O(1) | Get extension |
| `add_type(type, ext)` | O(1) | O(1) | Register mapping |
| `read(filename)` | O(n) | O(n) | n = file size |

## Common Operations

### Guessing MIME Types

```python
import mimetypes

# O(1) - guess MIME type from filename
mime_type, encoding = mimetypes.guess_type('document.pdf')
# Returns: ('application/pdf', None)

# With URL - O(1)
mime_type, encoding = mimetypes.guess_type('http://example.com/image.png')
# Returns: ('image/png', None)

# With compressed file - O(1)
mime_type, encoding = mimetypes.guess_type('archive.tar.gz')
# Returns: ('application/x-tar', 'gzip')
```

### Getting File Extensions

```python
import mimetypes

# O(1) - get extension from MIME type
ext = mimetypes.guess_extension('application/pdf')
# Returns: '.pdf'

# Get all possible extensions - O(k) where k = extension count
exts = mimetypes.guess_all_extensions('text/plain')
# Returns: ['.txt', '.asc', '.c', .h', ...]
```

## Common Use Cases

### Content-Type Header Generation

```python
import mimetypes

def get_content_type(filename):
    """Get HTTP Content-Type header - O(1)"""
    # O(1) to guess type
    mime_type, encoding = mimetypes.guess_type(filename)
    
    if mime_type is None:
        mime_type = 'application/octet-stream'
    
    # O(1) to format header
    content_type = mime_type
    if encoding:
        content_type += f'; charset={encoding}'
    
    return content_type

# Usage - O(1)
ct = get_content_type('document.pdf')  # 'application/pdf'
ct = get_content_type('data.csv')      # 'text/csv'
```

### Serving Files in Web Applications

```python
import mimetypes
from pathlib import Path

def serve_file(filepath):
    """Prepare file for serving - O(1)"""
    filepath = Path(filepath)
    
    # O(1) to guess type
    mime_type, _ = mimetypes.guess_type(str(filepath))
    
    # O(1) to get file info
    size = filepath.stat().st_size
    
    return {
        'path': filepath,
        'mime_type': mime_type or 'application/octet-stream',
        'size': size,
    }

# Usage - O(1)
info = serve_file('image.jpg')
print(f"Type: {info['mime_type']}")
```

### File Upload Validation

```python
import mimetypes

def validate_upload(filename, allowed_types):
    """Validate uploaded file type - O(1)"""
    # O(1) to guess type
    mime_type, _ = mimetypes.guess_type(filename)
    
    # O(k) to check allowed where k = allowed type count
    if mime_type in allowed_types:
        return True, mime_type
    
    return False, mime_type

# Usage - O(1)
allowed = {'image/jpeg', 'image/png', 'image/gif'}
valid, mime = validate_upload('photo.jpg', allowed)
print(f"Valid: {valid}, Type: {mime}")
```

### Custom MIME Type Registration

```python
import mimetypes

def setup_custom_types():
    """Register custom MIME types - O(k)"""
    # O(1) per registration
    mimetypes.add_type('application/x-custom', '.custom')
    mimetypes.add_type('application/json+ld', '.jsonld')
    mimetypes.add_type('application/wasm', '.wasm')
    
    # Now guess_type will recognize these - O(1)
    mime, _ = mimetypes.guess_type('script.wasm')
    # Returns: ('application/wasm', None)

# Usage - O(k)
setup_custom_types()
```

### Loading MIME Type Database

```python
import mimetypes
import os

def initialize_mimetypes(custom_files=None):
    """Initialize MIME type database - O(n)"""
    # O(1) to initialize with system defaults
    mimetypes.init()
    
    # O(m) to load custom files where m = file count
    if custom_files:
        for filepath in custom_files:
            if os.path.exists(filepath):
                # O(n) to read and parse file
                mimetypes.read(filepath)

# Usage - O(n+m)
initialize_mimetypes(['custom-types.txt'])
```

### Building MIME Type Lookup Table

```python
import mimetypes
from pathlib import Path

def build_type_cache(directory):
    """Build cache of types for directory - O(n)"""
    # O(1) to initialize cache
    type_cache = {}
    
    # O(n) where n = file count
    for filepath in Path(directory).rglob('*'):
        if filepath.is_file():
            # O(1) to guess type
            mime_type, _ = mimetypes.guess_type(str(filepath))
            
            # O(1) to cache
            ext = filepath.suffix
            if ext not in type_cache:
                type_cache[ext] = mime_type
    
    return type_cache

# Usage - O(n)
types = build_type_cache('/path/to/dir')
print(types)  # {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', ...}
```

## Performance Tips

### Cache MIME Type Lookups

```python
import mimetypes

class MimeTypeCache:
    """Cache MIME type lookups - O(1) access"""
    
    def __init__(self):
        self._cache = {}
        mimetypes.init()
    
    def get_type(self, filename):
        """O(1) cached or O(1) new lookup"""
        if filename not in self._cache:
            # O(1) lookup
            mime_type, _ = mimetypes.guess_type(filename)
            self._cache[filename] = mime_type
        
        return self._cache[filename]

# Usage - O(1) after first call
cache = MimeTypeCache()
mime = cache.get_type('document.pdf')  # O(1)
mime = cache.get_type('document.pdf')  # O(1) - cached
```

### Batch Process Files

```python
import mimetypes
from pathlib import Path

# Bad: Multiple lookups - O(n) where n = file count
for file in files:
    mime_type, _ = mimetypes.guess_type(file)

# Good: Initialize once, then lookup - O(n)
mimetypes.init()  # O(1) first call
for file in files:
    mime_type, _ = mimetypes.guess_type(file)  # O(1)
```

### Use Extension When Type Ambiguous

```python
import mimetypes

def get_accurate_type(filename):
    """Get accurate MIME type - O(1)"""
    # O(1) base lookup
    mime_type, _ = mimetypes.guess_type(filename)
    
    # If uncertain, try alternative
    if mime_type is None or 'octet-stream' in mime_type:
        # O(1) get extension and try mapping
        ext = Path(filename).suffix.lower()
        
        # Could use another method or custom mapping
        if ext == '.xyz':
            mime_type = 'application/x-xyz'
    
    return mime_type
```

## Common MIME Types

```python
# Text files
.txt       -> text/plain
.html      -> text/html
.css       -> text/css
.js        -> application/javascript
.json      -> application/json

# Images
.jpg       -> image/jpeg
.png       -> image/png
.gif       -> image/gif
.svg       -> image/svg+xml

# Documents
.pdf       -> application/pdf
.doc/.docx -> application/msword / application/vnd.openxmlformats-officedocument.wordprocessingml.document
.xls/.xlsx -> application/vnd.ms-excel / ...

# Archives
.zip       -> application/zip
.tar.gz    -> application/x-tar with gzip encoding
.rar       -> application/x-rar-compressed
```

## Version Notes

- **Python 2.6+**: Basic MIME type support
- **Python 3.x**: All features available
- **Platform-specific**: Uses system MIME type database

## Related Documentation

- [Pathlib Module](pathlib.md) - File path operations
- [Email Module](email.md) - MIME in emails
- [Html Module](html.md) - Web content handling
