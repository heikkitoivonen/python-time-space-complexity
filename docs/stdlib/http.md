# http Module

The `http` module provides HTTP client and server implementation, including status codes and HTTP message handling.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Status lookup | O(1) | O(1) | Hash-based |

## HTTP Status Codes

### Using Status Codes

```python
from http import HTTPStatus

# Access status by name - O(1)
print(HTTPStatus.OK)        # 200
print(HTTPStatus.NOT_FOUND) # 404
print(HTTPStatus.FORBIDDEN) # 403

# Access by value - O(1) lookup
response_code = 404
status = HTTPStatus(response_code)
print(status.name)          # NOT_FOUND
print(status.description)   # Not Found
```

## Related Documentation

- http.client Module
- http.server Module
- [urllib Module](urllib.md)
