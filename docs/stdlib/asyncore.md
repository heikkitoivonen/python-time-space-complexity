# asyncore Module Complexity

⚠️ **REMOVED IN PYTHON 3.12**: The `asyncore` module was deprecated since Python 3.6 and removed in Python 3.12. Use `asyncio` instead.

The `asyncore` module provides low-level asynchronous socket operations and an event loop based on the select multiplex I/O mechanism.

## Classes & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dispatcher()` | O(1) | O(1) | Create dispatcher |
| `create_socket(family, type)` | O(1) | O(1) | Create socket |
| `connect(addr)` | O(1) | O(1) | Connect (non-blocking) |
| `handle_read()` | O(n) | O(n) | Handle incoming, n = data size |
| `handle_write()` | O(n) | O(n) | Handle outgoing |
| `loop(map)` | O(m) | O(m) | Main event loop, m = sockets |

## Creating Dispatchers

### Time Complexity: O(1)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asyncore
import socket

class Handler(asyncore.dispatcher):
    """Socket handler (DEPRECATED)."""
    
    def __init__(self):
        # Create dispatcher: O(1)
        asyncore.dispatcher.__init__(self)  # O(1)
        
        # Create socket: O(1)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)  # O(1)
        
        self.buffer = b''
    
    def handle_connect(self):
        """Connection established: O(1)."""
        print("Connected")
    
    def handle_read(self):
        """Read data: O(n)."""
        # n = data size
        data = self.recv(1024)  # O(n) to read
        if data:
            self.buffer += data  # O(n)
    
    def handle_write(self):
        """Write data: O(n)."""
        # n = buffer size
        if self.buffer:
            sent = self.send(self.buffer)  # O(n)
            self.buffer = self.buffer[sent:]
    
    def handle_close(self):
        """Connection closed: O(1)."""
        self.close()  # O(1)
```

### Space Complexity: O(1) per dispatcher

```python
# ⚠️ DEPRECATED
import asyncore

class Handler(asyncore.dispatcher):
    """Handler instance."""
    pass

# Each instance: O(1) space
handler = Handler()  # O(1)
```

## Creating Server

### Time Complexity: O(1)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asyncore
import socket

class Server(asyncore.dispatcher):
    """Server (DEPRECATED)."""
    
    def __init__(self, host, port):
        # Create dispatcher: O(1)
        asyncore.dispatcher.__init__(self)  # O(1)
        
        # Create and bind socket: O(1)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)  # O(1)
        self.bind((host, port))  # O(1)
        self.listen(5)  # O(1)
    
    def handle_accepted(self, sock, addr):
        """Accept connection: O(1)."""
        # Create handler for connection: O(1)
        Handler(sock, addr)  # O(1)
```

## Event Loop

### Time Complexity: O(m) per loop iteration

Where m = number of active connections.

```python
# ⚠️ DEPRECATED
import asyncore

# Run event loop: O(m) per iteration
# m = active connections
asyncore.loop()  # DEPRECATED!

# With timeout: O(m) per iteration
asyncore.loop(timeout=1.0)

# Map parameter: O(m) per iteration
asyncore.loop(map=custom_map)
```

### Space Complexity: O(m)

```python
# ⚠️ DEPRECATED
# Event loop tracks all connections
asyncore.loop()  # O(m) space for m connections
```

## Common Patterns

### Echo Server (DEPRECATED)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asyncore
import socket

class EchoHandler(asyncore.dispatcher):
    """Echo handler (DEPRECATED)."""
    
    def __init__(self, sock, addr):
        asyncore.dispatcher.__init__(self, sock)
        self.addr = addr
        self.buffer = b''
    
    def handle_read(self):
        """Read and echo: O(n)."""
        data = self.recv(1024)  # O(n)
        if data:
            self.buffer = data + b'\r\n'  # O(n)
    
    def handle_write(self):
        """Send echo: O(n)."""
        if self.buffer:
            sent = self.send(self.buffer)  # O(n)
            self.buffer = self.buffer[sent:]
    
    def handle_close(self):
        """Close connection: O(1)."""
        self.close()

class EchoServer(asyncore.dispatcher):
    """Echo server (DEPRECATED)."""
    
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind((host, port))
        self.listen(5)
    
    def handle_accepted(self, sock, addr):
        """Accept connection: O(1)."""
        EchoHandler(sock, addr)  # O(1)

# ⚠️ DEPRECATED - Don't use
server = EchoServer('localhost', 9000)
asyncore.loop()  # DEPRECATED EVENT LOOP
```

### Client (DEPRECATED)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asyncore
import socket

class Client(asyncore.dispatcher):
    """Client connection (DEPRECATED)."""
    
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        # Non-blocking connect: O(1)
        self.connect((host, port))  # O(1)
        self.buffer = b'Hello\r\n'
    
    def handle_connect(self):
        """Connected: O(1)."""
        print("Connected to server")
    
    def handle_read(self):
        """Receive data: O(n)."""
        data = self.recv(1024)  # O(n)
        print(f"Received: {data}")
    
    def handle_write(self):
        """Send data: O(n)."""
        if self.buffer:
            sent = self.send(self.buffer)  # O(n)
            self.buffer = self.buffer[sent:]
    
    def handle_close(self):
        """Closed: O(1)."""
        self.close()

# ⚠️ DEPRECATED - Don't use
client = Client('localhost', 9000)
asyncore.loop()  # DEPRECATED
```

## Why asyncore is Deprecated

```python
# ⚠️ DEPRECATED REASONS:

# 1. asyncio is more modern and standard
import asyncio

async def handle_client(reader, writer):
    """Modern asyncio approach."""
    while True:
        data = await reader.read(1024)
        if not data:
            break
        writer.write(data)
        await writer.drain()

async def main():
    server = await asyncio.start_server(
        handle_client,
        '127.0.0.1', 8000
    )
    async with server:
        await server.serve_forever()

# asyncio.run(main())

# 2. asyncore is very low-level
# 3. Poor error handling
# 4. Hard to debug
# 5. Limited features
# 6. No integration with asyncio
# 7. Removed in Python 3.12
```

## Complexity Comparison

```python
# asyncore operations (DEPRECATED):
dispatcher = asyncore.dispatcher()  # O(1)
dispatcher.create_socket(...)  # O(1)
dispatcher.connect(addr)  # O(1)
dispatcher.handle_read()  # O(n)
asyncore.loop()  # O(m) per iteration

# asyncio equivalent (MODERN):
async def handle_client(reader, writer):
    data = await reader.read(1024)  # O(n)
    writer.write(data)
    await writer.drain()  # O(n)

server = await asyncio.start_server(handle_client, '127.0.0.1', 8000)
async with server:
    await server.serve_forever()

# asyncio: Better integration, clearer code, more powerful
```

## Performance Characteristics

### Not Recommended

```python
# ⚠️ DO NOT USE asyncore
import asyncore

# Issues:
# 1. Slower than asyncio (select-based)
# 2. Less maintainable
# 3. Removed in Python 3.12
# 4. Poor error handling
# 5. Hard to debug (callback-based)
# 6. Limited scalability (select() has limits)

class Handler(asyncore.dispatcher):
    """Don't use - DEPRECATED."""
    pass
```

### What to Use Instead

```python
# ✅ USE ASYNCIO
import asyncio

async def handle_client(reader, writer):
    """Modern approach."""
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        writer.close()

async def main():
    """Run server."""
    server = await asyncio.start_server(
        handle_client,
        '127.0.0.1', 8888
    )
    
    async with server:
        await server.serve_forever()

# Run with:
# asyncio.run(main())
```

## Event Loop Mechanism

```python
# asyncore event loop (DEPRECATED):
# - Uses select() or poll()
# - O(m) to check all sockets
# - Limited to ~1024 file descriptors on some systems
# - Callback-based (handle_read, handle_write, etc.)

# asyncio event loop (MODERN):
# - Uses best available: epoll/kqueue/IOCP
# - O(log m) to check ready sockets
# - Scales to thousands of connections
# - Coroutine-based (async/await)
```

## Version Notes

- **Python 2.0-2.6**: asyncore introduced
- **Python 2.7-3.5**: Widely used
- **Python 3.6+**: Deprecated (use asyncio)
- **Python 3.12+**: Removed

## Related Documentation

- [asyncio Module](asyncio.md) - **USE THIS INSTEAD**
- [asynchat Module](asynchat.md) - Also deprecated
- [selectors Module](selectors.md) - Low-level multiplexed I/O
- [socket Module](socket.md) - Low-level sockets
