# socketserver Module

The `socketserver` module provides classes for writing network servers, supporting both synchronous and asynchronous request handlers.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Server creation | O(1) + network latency | O(1) | Bind/listen; network setup dominates |
| Handle request | O(n) | O(n) | n = request size |
| Serve loop | Varies | Varies | Blocking accept + per-request handling |

## Creating Network Servers

### TCP Server

```python
import socketserver

class MyHandler(socketserver.StreamRequestHandler):
    def handle(self):
        """Handle client request - O(n)"""
        # Read from connection
        data = self.rfile.readline()
        print(f"Received: {data.decode()}")
        
        # Send response
        self.wfile.write(b"Echo: " + data)

# Create server - O(1)
with socketserver.TCPServer(("localhost", 8000), MyHandler) as server:
    # Serve - blocking accept + per-request handling
    server.serve_forever()
```

### Multi-threaded Server

```python
import socketserver

class MyHandler(socketserver.StreamRequestHandler):
    def handle(self):
        """Handle - O(n)"""
        data = self.rfile.readline()
        self.wfile.write(b"Response")

# Multi-threaded - O(1) setup
server = socketserver.ThreadingTCPServer(
    ("localhost", 8000),
    MyHandler
)

# Serve - blocking accept + per-request handling
server.serve_forever()
```

## Related Documentation

- [socket Module](socket.md)
- [threading Module](threading.md)
