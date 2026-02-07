# nntplib Module

⚠️ **REMOVED IN PYTHON 3.13**: The `nntplib` module was deprecated in Python 3.11 and removed in Python 3.13.

The `nntplib` module implements NNTP (Network News Transfer Protocol) client functionality for accessing Usenet newsgroups.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `connect()` | O(1) | O(1) | Network connection |
| List groups | O(n) | O(n) | n = newsgroups |
| Get articles | O(n) | O(n) | n = articles |

## Accessing Newsgroups

### Basic NNTP Operations

```python
import nntplib

# Connect - O(1)
nntp = nntplib.NNTP('news.example.com')

# Get article - O(1)
code, num, id, lines = nntp.article('<message-id>')
print(lines)

# Group info - O(1)
code, count, first, last, name = nntp.group('comp.lang.python')
print(f"Group: {name}, Articles: {count}")

# List articles - O(n)
code, num, first, last, name = nntp.group('comp.lang.python')
code, articles = nntp.over((first, last))
for article_num, headers in articles:
    print(f"{article_num}: {headers['subject']}")

# Disconnect - O(1)
nntp.quit()
```

## Related Documentation

- [socket Module](socket.md)
- [email Module](email.md)
