# netrc Module

The `netrc` module parses and encapsulates the .netrc file, which contains login credentials for various hosts.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `netrc()` parse | O(n) | O(n) | n = file size |
| Lookup auth | O(n) | O(1) | n = hostname length |

## Working with Netrc Files

### Reading .netrc File

```python
import netrc

# Parse netrc - O(n)
rc = netrc.netrc()

# Get authentication - O(1)
auth = rc.authenticators('github.com')
if auth:
    login, _, password = auth
    print(f"Login: {login}")
```

### .netrc Format

```
machine github.com
login username
password secret_token

machine pypi.org
login __token__
password pypi-token-here
```

## Related Documentation

- [urllib Module](urllib.md)
- [ftplib Module](ftplib.md)
