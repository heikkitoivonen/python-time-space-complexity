# sched Module

The `sched` module provides a general-purpose event scheduler for scheduling function calls at specific times.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enter()` / `enterabs()` | O(log n) | O(1) | n = scheduled events |
| `run()` | O(n log n) | O(n) | Process all events |
| `cancel()` | O(n) | O(1) | Remove event; O(n) linear search then heapify |

## Scheduling Events

### Basic Event Scheduling

```python
import sched
import time

scheduler = sched.scheduler(time.time, time.sleep)

def callback(name):
    print(f"Event: {name}")

# Schedule events - O(log n)
scheduler.enter(1, 1, callback, argument=('first',))
scheduler.enter(2, 1, callback, argument=('second',))
scheduler.enter(0.5, 1, callback, argument=('third',))

# Run scheduler - O(n log n)
scheduler.run()

# Output:
# Event: third
# Event: first
# Event: second
```

### Canceling Events

```python
import sched
import time

scheduler = sched.scheduler(time.time, time.sleep)

def callback(msg):
    print(f"Message: {msg}")

# Schedule - O(log n)
event = scheduler.enter(5, 1, callback, argument=('delayed',))

# Cancel - O(n) linear search in queue
scheduler.cancel(event)

# Event never fires
scheduler.run()
```

## Related Documentation

- [asyncio Module](asyncio.md)
- [threading Module](threading.md)
