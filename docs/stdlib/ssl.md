# ssl Module

The `ssl` module wraps socket objects with TLS/SSL encryption, enabling secure communication for network applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wrap_socket()` | O(1) | O(1) | Wrap for TLS |
| Handshake | O(1) + crypto | O(1) | TLS handshake; asymmetric cryptography overhead |
| Send/receive | O(n) | O(n) | n = data size |

## Secure Socket Communication

### HTTPS Connection

```python
import ssl
import socket

# Create socket - O(1)
context = ssl.create_default_context()
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    # Wrap with SSL - O(1)
    with context.wrap_socket(sock, server_hostname='example.com') as ssock:
        # Connect - O(1)
        ssock.connect(('example.com', 443))
        
        # Send request - O(n)
        ssock.send(b'GET / HTTP/1.1\r\n')
        
        # Receive - O(n)
        data = ssock.recv(1024)
```

### Server with SSL

```python
import ssl
import socketserver

# Create context - O(1)
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain('server.crt', 'server.key')

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        data = self.rfile.readline()
        self.wfile.write(b"Secure response")

# Server - O(1) setup
with socketserver.TCPServer(("", 443), Handler) as server:
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
```

## Related Documentation

- [socket Module](socket.md)
- [hashlib Module](hashlib.md)
