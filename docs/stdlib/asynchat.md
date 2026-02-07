# asynchat Module Complexity

⚠️ **REMOVED IN PYTHON 3.12**: The `asynchat` module was deprecated since Python 3.6 and removed in Python 3.12. Use `asyncio` instead.

The `asynchat` module provides asynchronous socket handlers with automatic buffering and line-based protocol support.

## Classes & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `async_chat(map)` | O(1) | O(1) | Create async chat instance |
| `set_terminator(term)` | O(1) | O(1) | Set message terminator |
| `push(data)` | O(1) | O(1) | Queue data for sending |
| `collect_incoming_data(data)` | O(n) | O(n) | Collect received data, n = size |
| `found_terminator()` | O(1) | O(1) | Callback when terminator found |

## Creating Async Chat Handlers

### Time Complexity: O(1)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asynchat
import socket

class Handler(asynchat.async_chat):
    """Chat handler (DEPRECATED)."""
    
    def __init__(self, sock, addr):
        asynchat.async_chat.__init__(self, sock)
        self.addr = addr
        
        # Set terminator: O(1)
        self.set_terminator(b'\r\n')  # O(1)
        
        self.data = []
    
    def handle_connect(self):
        """Connection established: O(1)."""
        print(f"Connected: {self.addr}")
    
    def collect_incoming_data(self, data):
        """Collect incoming data: O(n)."""
        # n = size of data
        self.data.append(data)  # O(n)
    
    def found_terminator(self):
        """Message complete: O(n)."""
        # n = total message size
        message = b''.join(self.data)  # O(n)
        self.data = []
        
        # Echo back: O(n)
        self.push(message + b'\r\n')  # O(n)
```

### Space Complexity: O(1) per instance

```python
# ⚠️ DEPRECATED
import asynchat

class Handler(asynchat.async_chat):
    """Handler instance."""
    pass

# Each instance: O(1) space
handler = Handler(sock, addr)  # O(1)
```

## Setting Terminators

### Time Complexity: O(1)

```python
# ⚠️ DEPRECATED
import asynchat

class LineHandler(asynchat.async_chat):
    """Handle line-based protocol."""
    
    def __init__(self, sock):
        asynchat.async_chat.__init__(self, sock)
        
        # Line terminator: O(1)
        self.set_terminator(b'\n')  # O(1)
        
        self.buffer = []
    
    def collect_incoming_data(self, data):
        """Collect until terminator: O(n)."""
        self.buffer.append(data)  # O(n)
```

### Space Complexity: O(1)

```python
# ⚠️ DEPRECATED
import asynchat

handler = asynchat.async_chat(sock)

# Setting terminator uses minimal space
handler.set_terminator(b'\r\n')  # O(1) space
```

## Pushing Data

### Time Complexity: O(n)

Where n = size of data.

```python
# ⚠️ DEPRECATED
import asynchat

class Handler(asynchat.async_chat):
    """Handler with push."""
    
    def send_message(self, msg):
        """Send message: O(n)."""
        # n = message size
        self.push(msg + b'\r\n')  # O(n) to queue
```

### Space Complexity: O(n)

```python
# ⚠️ DEPRECATED
# Each push adds to send buffer
handler.push(data)  # O(n) space in buffer
```

## Common Patterns

### Echo Server (DEPRECATED)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asynchat
import asyncore
import socket

class EchoHandler(asynchat.async_chat):
    """Echo handler (DEPRECATED)."""
    
    def __init__(self, sock, addr):
        asynchat.async_chat.__init__(self, sock)
        self.addr = addr
        self.set_terminator(b'\r\n')  # O(1)
        self.data = []
    
    def collect_incoming_data(self, data):
        """Collect data: O(n)."""
        self.data.append(data)  # O(n)
    
    def found_terminator(self):
        """Echo back: O(n)."""
        msg = b''.join(self.data)  # O(n)
        self.data = []
        self.push(msg + b'\r\n')  # O(n)

class EchoServer(asyncore.dispatcher):
    """Echo server (DEPRECATED)."""
    
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind((host, port))
        self.listen(5)
    
    def handle_accepted(self, sock, addr):
        """Accept connection: O(1)."""
        EchoHandler(sock, addr)  # O(1) to create

# ⚠️ DEPRECATED - Don't use
server = EchoServer('localhost', 9000)
asyncore.loop()  # DEPRECATED
```

### Protocol Handler (DEPRECATED)

```python
# ⚠️ DEPRECATED - Use asyncio instead
import asynchat

class ProtocolHandler(asynchat.async_chat):
    """Protocol handler (DEPRECATED)."""
    
    def __init__(self, sock):
        asynchat.async_chat.__init__(self, sock)
        self.set_terminator(b'\r\n')  # O(1)
        self.buffer = []
    
    def collect_incoming_data(self, data):
        """Collect: O(n)."""
        self.buffer.append(data)  # O(n)
    
    def found_terminator(self):
        """Process message: O(n)."""
        line = b''.join(self.buffer)  # O(n)
        self.buffer = []
        
        # Parse and respond: O(n)
        response = self.process_command(line)
        self.push(response + b'\r\n')  # O(n)
    
    def process_command(self, cmd):
        """Process command: O(n)."""
        # Parse command: O(n)
        parts = cmd.split(b' ')  # O(n)
        
        # Handle command
        if parts[0] == b'ECHO':
            return parts[1]
        else:
            return b'ERROR: Unknown command'
```

## Why asynchat is Deprecated

```python
# ⚠️ DEPRECATED REASONS:

# 1. asyncio is more modern and standard
import asyncio

async def handle_client(reader, writer):
    """Modern asyncio approach."""
    while True:
        data = await reader.readline()
        if not data:
            break
        writer.write(data)
        await writer.drain()

# 2. asynchat doesn't integrate with asyncio
# 3. No support for modern features
# 4. Limited error handling
# 5. Harder to debug

# MIGRATION PATH:
# asynchat -> asyncio
# asyncore -> asyncio or concurrent.futures
```

## Complexity Comparison

```python
# asynchat operations (DEPRECATED):
handler = asynchat.async_chat(sock)
handler.set_terminator(b'\n')  # O(1)
handler.push(data)  # O(n) where n = data size
handler.collect_incoming_data(chunk)  # O(n)

# asyncio equivalent (MODERN):
async def handle(reader, writer):
    data = await reader.readuntil(b'\n')  # O(n)
    writer.write(data)
    await writer.drain()  # O(n)

# asyncio: Better integration, clearer code, standard library
```

## Performance Characteristics

### Not Recommended

```python
# ⚠️ DO NOT USE asynchat
import asynchat

# Issues:
# 1. Slower than asyncio
# 2. Less maintainable
# 3. Removed in Python 3.12
# 4. Poor error handling
# 5. Difficult to test

class Handler(asynchat.async_chat):
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
            data = await reader.readuntil(b'\n')
            writer.write(data)
            await writer.drain()
    except asyncio.IncompleteReadError:
        pass
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

# asyncio.run(main())
```

## Version Notes

- **Python 2.0-2.6**: asynchat introduced
- **Python 2.7-3.5**: Widely used
- **Python 3.6+**: Deprecated (use asyncio)
- **Python 3.12+**: Removed

## Related Documentation

- [asyncio Module](asyncio.md) - **USE THIS INSTEAD**
- [asyncore Module](asyncore.md) - Also deprecated
- [socket Module](socket.md) - Low-level sockets
- [concurrent.futures Module](concurrent_futures.md) - Alternative for concurrency
