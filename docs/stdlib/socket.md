# socket Module Complexity

The `socket` module provides low-level network communication interfaces for client and server applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `socket()` | O(1) | O(1) | Create socket |
| `connect()` | O(1) + network latency | O(1) | Network latency and handshake dominate |
| `send()` | O(k) | O(1) | k = data size |
| `recv()` | O(k) | O(k) | k = buffer size |

## Basic Client

```python
import socket

# Create socket - O(1)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect to server - O(n)
sock.connect(('localhost', 8000))  # O(n) - network time

# Send data - O(k)
sock.send(b'Hello')  # O(5)

# Receive data - O(k)
data = sock.recv(1024)  # O(k) - up to 1024 bytes

# Close - O(1)
sock.close()
```

## Basic Server

```python
import socket

# Create socket - O(1)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind to port - O(1)
sock.bind(('localhost', 8000))  # O(1)

# Listen for connections - O(1)
sock.listen(1)  # O(1)

# Accept connection - O(n)
client, addr = sock.accept()  # O(n) - wait for client

# Communicate - O(k)
data = client.recv(1024)  # O(k)
client.send(b'Response')  # O(8)

# Close - O(1)
client.close()
sock.close()
```

## Server Loop

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('localhost', 8000))
sock.listen(5)

# Accept multiple clients - O(n) per client
while True:
    client, addr = sock.accept()  # O(n) - wait
    
    # Handle client - O(k)
    try:
        while True:
            data = client.recv(1024)  # O(k)
            if not data:
                break
            response = process(data)  # O(f)
            client.send(response)  # O(len(response))
    finally:
        client.close()  # O(1)
```

## UDP (Connectionless)

```python
import socket

# UDP socket - O(1)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind - O(1)
sock.bind(('localhost', 8000))

# Receive from - O(k)
data, addr = sock.recvfrom(1024)  # O(k)

# Send to - O(k)
sock.sendto(b'Response', addr)  # O(k)
```

## Version Notes

- **Python 2.x**: socket available
- **Python 3.x**: Same with IPv6 improvements
- **Note**: Network I/O dominates - algorithms are secondary

## Best Practices

✅ **Do**:

- Use context managers (with statement)
- Set timeouts
- Close sockets properly
- Use asyncio for many connections

❌ **Avoid**:

- Blocking operations in GUI
- No timeout (hangs)
- Not closing sockets
- Synchronous servers for many clients
