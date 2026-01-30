# selectors Module Complexity

The `selectors` module provides a high-level interface for multiplexed I/O, allowing monitoring of multiple sockets efficiently using system-level mechanisms (select, epoll, kqueue, IOCP).

## Classes & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `DefaultSelector()` | O(1) | O(1) | Create selector |
| `selector.register(fileobj)` | O(1) | O(1) | Register socket/file |
| `selector.unregister(fileobj)` | O(1) | O(1) | Unregister |
| `selector.select(timeout)` | O(n) or O(k) | O(k) | select: O(n) scans all fds; epoll/kqueue: O(k) for ready fds |
| `selector.modify(fileobj)` | O(1) | O(1) | Change registration |
| `selector.get_map()` | O(1) | O(n) | Get all registrations |

## Creating Selectors

### Time Complexity: O(1)

```python
import selectors

# Create selector: O(1)
# Uses best available mechanism (epoll, kqueue, select)
sel = selectors.DefaultSelector()  # O(1)

# Or specify type explicitly
sel = selectors.EpollSelector()  # O(1) on Linux
sel = selectors.KqueueSelector()  # O(1) on BSD/macOS
sel = selectors.SelectSelector()  # O(1) fallback
```

### Space Complexity: O(1)

```python
import selectors

# Selector object is small
sel = selectors.DefaultSelector()  # O(1) space
```

## Registering File Objects

### Time Complexity: O(1)

```python
import selectors
import socket

sel = selectors.DefaultSelector()

# Create socket
sock = socket.socket()

# Register socket: O(1)
# Register for read events
sel.register(sock, selectors.EVENT_READ, data=user_data)  # O(1)

# Register for write events
sel.register(sock, selectors.EVENT_WRITE)  # O(1)

# Register for both: O(1)
sel.register(sock, selectors.EVENT_READ | selectors.EVENT_WRITE)  # O(1)
```

### Space Complexity: O(1) per registration

```python
import selectors

# Each registration stores minimal info: O(1)
sel.register(sock, selectors.EVENT_READ)  # O(1) space
```

## Selecting with Timeout

### Time Complexity: O(k) for epoll/kqueue, O(n) for select

Where n = number of registered file objects, k = number of ready file objects. Note: epoll/kqueue return only ready events in O(k), while select must scan all n registered fds.

```python
import selectors
import socket

sel = selectors.DefaultSelector()

# Register sockets: O(k) for k sockets
for i in range(100):
    sock = socket.socket()
    sel.register(sock, selectors.EVENT_READ)  # O(1) per socket

# Wait for I/O: O(n) where n = registered sockets
# Returns only ready file objects: O(k) where k <= n
events = sel.select(timeout=1.0)  # O(n) for select, O(k) for epoll/kqueue

# Process events: O(k)
for key, mask in events:  # k = ready file objects
    if mask & selectors.EVENT_READ:
        data = key.fileobj.recv(4096)  # Handle read
```

### Space Complexity: O(k)

Where k = number of ready file objects.

```python
import selectors

# select() returns only ready events
events = sel.select(timeout=1.0)  # O(k) space for k ready

# Iterate ready events: O(k)
for key, mask in events:
    process(key, mask)  # O(k) total
```

## Modifying Registrations

### Time Complexity: O(1)

```python
import selectors
import socket

sel = selectors.DefaultSelector()
sock = socket.socket()

# Register: O(1)
key = sel.register(sock, selectors.EVENT_READ)  # O(1)

# Modify to watch writes instead: O(1)
sel.modify(sock, selectors.EVENT_WRITE)  # O(1)

# Modify back to read: O(1)
sel.modify(sock, selectors.EVENT_READ)  # O(1)
```

### Space Complexity: O(1)

```python
import selectors

# Modifying doesn't allocate new space
sel.modify(sock, selectors.EVENT_WRITE)  # O(1) space
```

## Unregistering

### Time Complexity: O(1)

```python
import selectors

# Unregister socket: O(1)
sel.unregister(sock)  # O(1)

# Unregister by key: O(1)
key = sel.get_map()[sock]
sel.unregister(key)  # O(1)
```

### Space Complexity: O(1)

```python
import selectors

# Cleanup is fast: O(1)
sel.unregister(sock)  # O(1)
```

## Common Patterns

### Echo Server with Multiple Clients

```python
import selectors
import socket

sel = selectors.DefaultSelector()

def accept(sock):
    """Accept new connection."""
    conn, addr = sock.accept()
    conn.setblocking(False)
    # Register for read: O(1)
    sel.register(conn, selectors.EVENT_READ, data=addr)  # O(1)

def read(conn, addr):
    """Read data from client."""
    data = conn.recv(4096)
    if data:
        # Echo back: could register for write
        sel.modify(conn, selectors.EVENT_WRITE)  # O(1) to modify
    else:
        # Close connection: O(1) to unregister
        sel.unregister(conn)  # O(1)
        conn.close()

def write(conn):
    """Write data to client."""
    # Send buffered data
    conn.sendall(buffer)
    # Switch back to read: O(1)
    sel.modify(conn, selectors.EVENT_READ)  # O(1)

def main():
    """Main event loop."""
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('localhost', 9000))
    server.listen()
    server.setblocking(False)
    
    # Register server socket for accepts: O(1)
    sel.register(server, selectors.EVENT_READ, data=None)  # O(1)
    
    while True:
        # Wait for I/O: O(k) for epoll/kqueue, O(n) for select
        events = sel.select()  # O(k) ready fds typically
        
        for key, mask in events:  # O(k) where k = ready
            if key.data is None:
                # Server socket ready
                accept(key.fileobj)  # O(1) to register
            else:
                # Client socket ready
                if mask & selectors.EVENT_READ:
                    read(key.fileobj, key.data)
                elif mask & selectors.EVENT_WRITE:
                    write(key.fileobj)
```

### Non-blocking Socket Operations

```python
import selectors
import socket

sel = selectors.DefaultSelector()

def connect_many(hosts_ports):
    """Connect to multiple hosts simultaneously."""
    sockets = []
    
    for host, port in hosts_ports:
        sock = socket.socket()
        sock.setblocking(False)
        try:
            sock.connect((host, port))
        except BlockingIOError:
            pass  # Expected for non-blocking
        
        # Register for write (connection completion): O(1)
        sel.register(sock, selectors.EVENT_WRITE, data=(host, port))
        sockets.append(sock)
    
    # Wait for connections: O(n) for select, O(k) for epoll/kqueue
    # n = registered sockets, k = ready sockets
    while True:
        events = sel.select()  # O(n) for select, O(k) for epoll/kqueue
        
        if not events:
            break
        
        for key, mask in events:  # O(k) ready
            sock = key.fileobj
            try:
                sock.getpeername()  # Check if connected
                print(f"Connected to {key.data}")
            except OSError:
                print(f"Failed to connect to {key.data}")
            
            sel.unregister(sock)  # O(1)
            sock.close()
    
    return sockets
```

### File Object Monitoring

```python
import selectors
import sys

sel = selectors.DefaultSelector()

def read_input():
    """Read from stdin."""
    line = input()
    return line

def main():
    """Monitor multiple inputs."""
    # Register stdin: O(1)
    sel.register(sys.stdin, selectors.EVENT_READ)  # O(1)
    
    # Register other files: O(1) each
    with open('file.txt') as f:
        sel.register(f, selectors.EVENT_READ)  # O(1)
    
    # Event loop: O(n) for select, O(k) for epoll/kqueue
    while True:
        events = sel.select()  # O(n) for select, O(k) for epoll/kqueue
        
        for key, mask in events:  # O(k) ready
            if key.fileobj == sys.stdin:
                data = key.fileobj.readline()
                process_input(data)
            else:
                data = key.fileobj.read(4096)
                process_file(data)
```

## Performance Characteristics

### Selector Efficiency

```python
import selectors
import select
import socket

# selectors uses best mechanism available
# On Linux (many sockets):   epoll - O(1) per ready event, O(k) total
# On BSD/macOS:               kqueue - O(1) per ready event, O(k) total  
# Fallback:                   select - O(n) per wait where n = all registered

sel = selectors.DefaultSelector()

# For thousands of connections:
# select: becomes slow O(n) per select() - must scan all fds
# epoll/kqueue: stays fast O(k) per select() - returns only ready fds

# Registering: always O(1)
for i in range(10000):
    sel.register(socks[i], selectors.EVENT_READ)  # O(10000)

# Selecting: depends on mechanism
# epoll/kqueue: O(k) where k = ready fds (typically small)
# select: O(n) = O(10000) - must check all registered fds
events = sel.select()  # Fast with epoll/kqueue, slow with select
```

### Best Practices

```python
import selectors
import socket

sel = selectors.DefaultSelector()

# Good: Use DefaultSelector (picks best mechanism)
sel = selectors.DefaultSelector()  # O(1)

# Good: Avoid blocking operations in select loop
while True:
    events = sel.select(timeout=1.0)  # Don't block
    for key, mask in events:
        # Non-blocking operations only
        data = key.fileobj.recv(4096)  # Will not block
        process(data)

# Avoid: Blocking calls in event loop
while True:
    events = sel.select()
    for key, mask in events:
        # This might block!
        data = key.fileobj.recv(4096*1024)  # Could block

# Good: Use with asyncio or concurrent.futures for CPU work
import concurrent.futures

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

while True:
    events = sel.select()
    for key, mask in events:
        # CPU-intensive work in thread pool
        future = executor.submit(process, data)

# Good: Set non-blocking mode
sock = socket.socket()
sock.setblocking(False)  # Required for selector use
sel.register(sock, selectors.EVENT_READ)

# Avoid: Mixing blocking and non-blocking
sock.setblocking(True)  # Will block select()!
```

### Scalability

```python
import selectors

# Thousands of connections
connections = 10000

sel = selectors.DefaultSelector()

# Register all: O(n)
for i in range(connections):
    sel.register(socks[i], selectors.EVENT_READ)  # O(10000)

# Event loop: scales well with epoll/kqueue
# O(k) where k = ready events (typically small)
while True:
    # Usually only few sockets ready at once
    # If 100 ready: O(100) with epoll/kqueue vs O(10000) with select
    events = sel.select()  # Efficient with epoll/kqueue!
    
    for key, mask in events:  # Only processes ready events
        handle(key, mask)
```

## Version Notes

- **Python 3.4+**: selectors module introduced
- **Python 3.5+**: Enhanced performance
- **Python 3.10+**: Better Windows support

## Comparison with Alternatives

```python
# selectors: High-level, portable
import selectors
sel = selectors.DefaultSelector()

# select: Low-level, limited to ~1024 fds
import select
select.select(rlist, wlist, xlist, timeout)

# asyncio: Better for cooperative multitasking
import asyncio
await asyncio.wait_for(coro, timeout)

# Use selectors for:
# - Efficient handling of many connections
# - Mixing different I/O types
# - Simple non-blocking servers
```

## Related Documentation

- [asyncio Module](asyncio.md) - Modern async/await alternative
- [socket Module](socket.md) - Low-level socket operations
- [concurrent.futures Module](concurrent_futures.md) - For CPU-intensive work
