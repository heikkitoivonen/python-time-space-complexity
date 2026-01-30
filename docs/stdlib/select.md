# select Module

The `select` module provides low-level I/O multiplexing primitives that wait for file
descriptors to become ready for reading or writing.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `select.select()` | O(n) | O(n) | n = total fds passed; scans all sets |
| `poll.register()` / `poll.unregister()` / `poll.modify()` | O(1) avg | O(1) | Per fd; Python bookkeeping + OS registration |
| `poll.poll()` | O(n) | O(k) | n = registered fds, k = ready fds |
| `epoll.register()` / `epoll.unregister()` / `epoll.modify()` | O(1) avg | O(1) | Per fd; OS-dependent |
| `epoll.poll()` | O(k) typical | O(k) | k = ready fds; OS-dependent |
| `kqueue.control()` | O(m + k) | O(k) | m = changelist length; k = ready events |

!!! warning "Platform availability"
    `poll`, `epoll`, and `kqueue` are not available on all platforms.
    Always guard with `hasattr(select, "poll")`, `hasattr(select, "epoll")`,
    or `hasattr(select, "kqueue")`.

## Waiting with select()

```python
import select
import socket

# Create a connected socket pair (cross-platform in Python 3.5+)
left, right = socket.socketpair()

# Send data so right becomes readable
left.sendall(b"ping")

# Wait for readability - O(n) where n = len(rlist) + len(wlist) + len(xlist)
rlist, wlist, xlist = select.select([right], [], [], 1.0)
if rlist:
    data = right.recv(4096)
    print(data)  # b'ping'

left.close()
right.close()
```

## Polling with poll()

```python
import select
import socket

if hasattr(select, "poll"):
    left, right = socket.socketpair()
    poller = select.poll()

    # Register for read events - O(1) average
    poller.register(right, select.POLLIN)

    left.sendall(b"hello")

    # Wait for events - O(n) for n registered fds
    events = poller.poll(1000)  # timeout in ms
    for fd, event in events:  # O(k) for k ready
        if event & select.POLLIN:
            print(right.recv(4096))  # b'hello'

    poller.unregister(right)  # O(1) average
    left.close()
    right.close()
```

## Using epoll (Linux)

```python
import select
import socket

if hasattr(select, "epoll"):
    left, right = socket.socketpair()
    ep = select.epoll()

    # Register read interest - O(1) average
    ep.register(right, select.EPOLLIN)

    left.sendall(b"event")

    # Wait for ready fds - typically O(k)
    events = ep.poll(1.0)
    for fd, event in events:
        if event & select.EPOLLIN:
            print(right.recv(4096))  # b'event'

    ep.unregister(right)  # O(1) average
    ep.close()
    left.close()
    right.close()
```

## Using kqueue (BSD/macOS)

```python
import select
import socket

if hasattr(select, "kqueue"):
    left, right = socket.socketpair()
    kq = select.kqueue()

    # Register a read event - O(1) average
    kev = select.kevent(right, filter=select.KQ_FILTER_READ, flags=select.KQ_EV_ADD)
    kq.control([kev], 0, 0)

    left.sendall(b"kq")

    # Wait for events - O(m + k) where m = changelist length
    events = kq.control([], 1, 1.0)
    if events:
        print(right.recv(4096))  # b'kq'

    kq.close()
    left.close()
    right.close()
```

## Notes and Best Practices

!!! warning "select() scalability limits"
    `select.select()` must scan all fds each call and may be limited by the
    platform's FD set size. For large numbers of connections, prefer `selectors`
    or an `epoll`/`kqueue`-based approach.

## Related Modules

- [selectors Module](selectors.md)
- [socket Module](socket.md)
- [asyncio Module](asyncio.md)
