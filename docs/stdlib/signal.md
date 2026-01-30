# signal Module Complexity

The `signal` module provides mechanisms to handle signals from the operating system, allowing response to interrupts, termination requests, and other OS signals.

## Functions & Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `signal.signal(signum, handler)` | O(1) | O(1) | Register signal handler |
| `signal.alarm(seconds)` | O(1) | O(1) | Schedule SIGALRM; Unix only |
| `signal.pause()` | O(1) | O(1) | Wait for signal |
| `signal.set_wakeup_fd(fd)` | O(1) | O(1) | Set event loop wakeup |
| `signal.siginterrupt(signum, flag)` | O(1) | O(1) | Set signal interruption |

## Signal Handler Registration

### Time Complexity: O(1)

```python
import signal

def handler(signum, frame):
    """Signal handler function."""
    print(f"Received signal {signum}")

# Register handler: O(1)
old_handler = signal.signal(signal.SIGTERM, handler)  # O(1)

# Or register multiple
signal.signal(signal.SIGINT, handler)  # O(1)
signal.signal(signal.SIGUSR1, handler)  # O(1)

# Restore previous handler: O(1)
signal.signal(signal.SIGTERM, old_handler)  # O(1)
```

### Space Complexity: O(1)

```python
import signal

# Handler registration uses minimal memory
signal.signal(signal.SIGTERM, handler)  # O(1) space
```

## Common Signals

### Handling SIGTERM (Termination)

```python
import signal
import sys

def sigterm_handler(signum, frame):
    """Handle termination signal."""
    print("Received SIGTERM, cleaning up...")
    cleanup()
    sys.exit(0)

# Register: O(1)
signal.signal(signal.SIGTERM, sigterm_handler)  # O(1)

# Server loop
while True:
    process_request()  # Interrupted by signal
```

### Handling SIGINT (Ctrl+C)

```python
import signal
import sys

def sigint_handler(signum, frame):
    """Handle interrupt (Ctrl+C)."""
    print("\nInterrupted by user")
    cleanup()
    sys.exit(0)

# Register: O(1)
signal.signal(signal.SIGINT, sigint_handler)  # O(1)

# Default behavior is to raise KeyboardInterrupt
# Custom handler overrides this
```

### Handling SIGUSR1 (User Signal)

```python
import signal

def sigusr1_handler(signum, frame):
    """Handle user signal 1."""
    print("Received SIGUSR1, reloading configuration")
    reload_config()

# Register: O(1)
signal.signal(signal.SIGUSR1, sigusr1_handler)  # O(1)

# Can send from another process:
# kill -USR1 <pid>
```

## Alarm Signals

### Time Complexity: O(1)

```python
import signal

def timeout_handler(signum, frame):
    """Handle timeout."""
    raise TimeoutError("Operation timed out")

# Register alarm handler: O(1)
signal.signal(signal.SIGALRM, timeout_handler)  # O(1)

# Set alarm for 5 seconds: O(1)
signal.alarm(5)  # O(1)

try:
    # Long operation
    slow_operation()  # Interrupted after 5 seconds
except TimeoutError:
    print("Timed out")

# Cancel alarm: O(1)
signal.alarm(0)  # O(1) to cancel
```

### Space Complexity: O(1)

```python
import signal

# Alarm state is minimal
signal.alarm(5)  # O(1) space
signal.alarm(0)  # Cancel: O(1)
```

## Pausing for Signals

### Time Complexity: O(1) operation

```python
import signal
import os

def handler(signum, frame):
    """Signal handler."""
    print(f"Got signal {signum}")

# Register: O(1)
signal.signal(signal.SIGUSR1, handler)  # O(1)

# Pause execution: O(1) operation
# (actual time depends on when signal arrives)
signal.pause()  # O(1) to set up, waits for signal

# After signal is handled, pause() returns
print("Resumed")
```

## Wakeup File Descriptor

### Time Complexity: O(1)

```python
import signal
import selectors
import socket

# Set wakeup fd for event loop: O(1)
# Wakes up select/poll when signal arrives
sel = selectors.DefaultSelector()
read_sock, write_sock = socket.socketpair()
read_sock.setblocking(False)
write_sock.setblocking(False)
signal.set_wakeup_fd(write_sock.fileno())  # O(1)
sel.register(read_sock, selectors.EVENT_READ)

# Now signals wake up selector instead of immediate delivery
events = sel.select(timeout=1.0)  # Can be interrupted safely
```

## Common Patterns

### Graceful Shutdown Handler

```python
import signal
import sys

class Server:
    """Server with graceful shutdown."""
    
    def __init__(self):
        self.running = True
        # Register shutdown handler: O(1)
        signal.signal(signal.SIGTERM, self.handle_shutdown)  # O(1)
        signal.signal(signal.SIGINT, self.handle_shutdown)  # O(1)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        print(f"Shutting down (signal {signum})")
        self.running = False
    
    def run(self):
        """Main server loop."""
        while self.running:
            self.accept_connection()  # Can be interrupted
            self.handle_client()

server = Server()
server.run()  # Gracefully shuts down on signal
```

### Timeout Handler

```python
import signal

def with_timeout(func, args, timeout_secs):
    """Execute function with timeout."""
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {timeout_secs}s")
    
    # Register alarm: O(1)
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)  # O(1)
    signal.alarm(timeout_secs)  # O(1)
    
    try:
        result = func(*args)
        signal.alarm(0)  # Cancel alarm: O(1)
        return result
    finally:
        signal.alarm(0)  # Ensure cancelled: O(1)
        signal.signal(signal.SIGALRM, old_handler)  # O(1)

# Usage
def slow_task():
    import time
    time.sleep(10)

try:
    with_timeout(slow_task, (), timeout_secs=5)
except TimeoutError as e:
    print(e)
```

### Signal Counter

```python
import signal

class SignalCounter:
    """Count signals received."""
    
    def __init__(self):
        self.count = 0
        # Register: O(1)
        signal.signal(signal.SIGUSR1, self.increment)  # O(1)
    
    def increment(self, signum, frame):
        """Increment counter when signal received."""
        self.count += 1
        print(f"Received signal: count = {self.count}")

counter = SignalCounter()

# In another process:
# for i in range(5):
#     os.kill(pid, signal.SIGUSR1)

# counter.count will be 5
```

### Daemon with Signal Handling

```python
import signal
import sys
import time

class Daemon:
    """Background daemon with signal handling."""
    
    def __init__(self):
        self.shutdown_requested = False
        # Register handlers: O(1) each
        signal.signal(signal.SIGTERM, self.request_shutdown)  # O(1)
        signal.signal(signal.SIGUSR1, self.reload_config)  # O(1)
    
    def request_shutdown(self, signum, frame):
        """Request graceful shutdown."""
        print("Shutdown requested")
        self.shutdown_requested = True
    
    def reload_config(self, signum, frame):
        """Reload configuration."""
        print("Reloading configuration...")
        self.config = load_config()
    
    def run(self):
        """Main daemon loop."""
        while not self.shutdown_requested:
            self.do_work()
            time.sleep(1)
        
        self.cleanup()

daemon = Daemon()
daemon.run()
```

## Performance Characteristics

### Signal Safety

```python
import signal

def minimal_handler(signum, frame):
    """Minimal signal handler."""
    # Keep handlers short; avoid blocking I/O or locks.
    os.write(1, b"Signal received\n")

# Register handler
signal.signal(signal.SIGUSR1, minimal_handler)  # O(1)
```

### Best Practices

```python
import signal
import sys

# Good: Quick handlers that just set flags
def handler(signum, frame):
    """Minimal handler."""
    global shutdown_flag
    shutdown_flag = True  # O(1), just set flag

signal.signal(signal.SIGTERM, handler)  # O(1)

# Check flag in main loop
while not shutdown_flag:
    do_work()  # Can check flag between iterations

# Avoid: Long operations in handlers
def bad_handler(signum, frame):
    """Don't do this."""
    cleanup()  # Might deadlock!
    save_state()  # Might deadlock!
    sys.exit(0)  # Might deadlock!

# Good: Use with asyncio
import asyncio

async def async_handler():
    """Async cleanup."""
    await cleanup()
    # But signal handlers aren't async-safe

# Better: Set flag, handle in main loop
def async_aware_handler(signum, frame):
    """Signal handler for async code."""
    # Just set flag, don't call async code
    global shutdown_flag
    shutdown_flag = True  # O(1)

# In async code:
async def main():
    while not shutdown_flag:
        await asyncio.sleep(0.1)
```

### Timing Considerations

```python
import signal
import time

# Signals can arrive at any time: O(1) interrupt
def handler(signum, frame):
    """Handle signal."""
    pass

signal.signal(signal.SIGUSR1, handler)

# Critical section - should it be interrupted?
critical_lock.acquire()
critical_operation()  # Might be interrupted mid-operation!
critical_lock.release()

# Better: Use siginterrupt
signal.siginterrupt(signal.SIGUSR1, False)  # O(1)
# Now critical operations won't be interrupted

critical_lock.acquire()
critical_operation()  # Safe from interruption
critical_lock.release()

signal.siginterrupt(signal.SIGUSR1, True)  # O(1), re-enable
```

## Signal Handling Caveats

```python
import signal

# ⚠️ Only main thread can register handlers
import threading

def register_in_thread():
    """This will fail."""
    try:
        signal.signal(signal.SIGUSR1, lambda s, f: None)
    except ValueError as e:
        print(f"Error: {e}")
        # ValueError: signal only works in main thread

t = threading.Thread(target=register_in_thread)
t.start()

# ✓ Main thread only
signal.signal(signal.SIGTERM, lambda s, f: None)  # O(1)

# ⚠️ Not all signals available on all platforms
# SIGUSR1/SIGUSR2: Unix only
# SIGBREAK: Windows only

# Check available signals
print(signal.Signals)  # Enum of available signals
```

## Version Notes

- **Python 2.0+**: Basic signal handling
- **Python 3.3+**: Better Windows support
- **Python 3.x**: signal.set_wakeup_fd() available
- **Python 3.10+**: signal.Signals enum

## Related Documentation

- [asyncio Module](asyncio.md) - Signal handling with async
- [os Module](os.md) - Process management
- [threading Module](threading.md) - Note: signals only in main thread
