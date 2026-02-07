# telnetlib Module

⚠️ **REMOVED IN PYTHON 3.13**: The `telnetlib` module was deprecated in Python 3.11 and removed in Python 3.13.

The `telnetlib` module implements a Telnet client for communicating with Telnet servers (legacy, mostly replaced by SSH).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `connect()` | O(1) | O(1) | Network connection |
| Read/write | O(n) | O(n) | n = data size |
| Interaction | O(m) | O(m) | m = commands |

## Telnet Communication

### Basic Telnet Client

```python
import telnetlib
import time

# Connect - O(1)
tn = telnetlib.Telnet('example.com', 23)

# Read prompt - O(n)
output = tn.read_until(b'login: ')
print(output.decode())

# Send login - O(n)
tn.write(b'username\n')

# Read password prompt - O(n)
output = tn.read_until(b'Password: ')

# Send password - O(n)
tn.write(b'password\n')

# Send command - O(n)
tn.write(b'ls -la\n')

# Read response - O(n)
output = tn.read_all()
print(output.decode())

# Close - O(1)
tn.close()
```

## Related Documentation

- [socket Module](socket.md)
- [socketserver Module](socketserver.md)
