# mailcap Module

⚠️ **REMOVED IN PYTHON 3.13**: The `mailcap` module was deprecated in Python 3.11 and removed in Python 3.13.

The `mailcap` module reads mailcap files, which define how MIME types should be handled by external applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `init()` | O(n) | O(n) | n = mailcap entries |
| `getcaps()` | O(1) | O(n) | Return cached caps |
| `findmatch()` | O(1) | O(1) | Hash lookup |

## Reading Mailcap Database

### Getting MIME Handlers

```python
import mailcap

# Initialize - O(n)
caps = mailcap.getcaps()

# Find handler - O(1)
handler, copiousoutput = mailcap.findmatch(
    caps,
    'image/png',
    'view'
)
print(handler)  # e.g., 'eog %s'

# Find with fallback
match = mailcap.findmatch(caps, 'text/html', 'view')
if match[0]:
    print(f"Handler: {match[0]}")
```

## Related Documentation

- [mimetypes Module](mimetypes.md)
- [subprocess Module](subprocess.md)
