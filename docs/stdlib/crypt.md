# crypt Module

The `crypt` module provides Unix password hashing functionality using the crypt() system call (Unix/Linux only).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `crypt()` | O(n) | O(1) | n = work factor/iterations; intentionally slow |
| Hash password | O(n) | O(n) | Compute hash |

## Password Hashing

### Hashing Passwords

```python
import crypt

# Hash password - O(n)
password = "mypassword"
hashed = crypt.crypt(password, salt=crypt.METHOD_SHA512)

print(hashed)  # Hashed format

# Verify by re-hashing
if crypt.crypt(password, hashed) == hashed:
    print("Password correct")
```

## Related Documentation

- [hashlib Module](hashlib.md)
- [hmac Module](hmac.md)
