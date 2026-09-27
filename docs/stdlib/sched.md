# sched Module Complexity

The `sched` module runs callbacks at scheduled times from a single priority queue. A `scheduler`
keeps its events in a `heapq` heap ordered by time, then priority, then insertion order, and it
has no thread of its own: `run()` pops and calls events on the calling thread, and waits between
them with the `delayfunc` it was given.

`n` is the events in the queue, counting any that actions enter while `run()` is working through
it, and `d` is the events `run(blocking=False)` finds due. Event times are numbers, so comparing
two events is O(1), and `timefunc()` is taken as O(1) with each wait lasting as long as it was
asked to. The bounds cover the scheduler's own work; the actions it calls, including passing them
their arguments, and the time spent in `delayfunc` are extra.

## Complexity Reference

### scheduler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sched.scheduler(timefunc=time.monotonic, delayfunc=time.sleep)` | O(1) | O(1) | An empty queue; pass your own pair to run on simulated time |
| `scheduler.enterabs(time, priority, action, argument=(), kwargs={})` | O(log n) | O(1) | One heap push; returns the `Event`, which is the handle `cancel()` takes |
| `scheduler.enter(delay, priority, action, argument=(), kwargs={})` | O(log n) | O(1) | One `timefunc()` call, then `enterabs()` at that time plus `delay` |
| `scheduler.cancel(event)` | O(n) | O(1) | Rebuilds the whole heap, even for the next event due; raises `ValueError` if the event already ran or was cancelled |
| `scheduler.empty()` | O(1) | O(1) | |
| `scheduler.run(blocking=True)` | O(n log n) | O(1) | One heap pop per event, and `delayfunc(0)` after every action |
| `scheduler.run(blocking=False)` | O(1 + d log n) | O(1) | Runs only the due events, then returns the delay until the next one, or `None` if none is left |
| `scheduler.queue` | O(n log n) | O(n) | A new list sorted in run order on every read |
| `scheduler.timefunc`, `scheduler.delayfunc` | O(1) | O(1) | The two functions the scheduler was built with |

### Event

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Event.time`, `Event.priority`, `Event.sequence`, `Event.action`, `Event.argument`, `Event.kwargs` | O(1) | O(1) | A named tuple; events order by time, then priority, then `sequence`, so events that tie on both run in the order they were entered |

## Scheduling Events

### Relative and Absolute Times

`enter()` reads the clock once and adds the delay; `enterabs()` takes the time as given. Either
way the event goes into the heap in O(log n). The examples on this page that run the scheduler
drive it with a simulated clock, so they finish instantly: its `sleep()` advances the time
instead of waiting.

```python
import sched

class Clock:
    def __init__(self):
        self.now = 0
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds

clock = Clock()
scheduler = sched.scheduler(clock.time, clock.sleep)  # O(1)
ran = []

scheduler.enter(10, 1, ran.append, argument=('ten',))        # O(log n)
scheduler.enterabs(5, 2, ran.append, argument=('low',))      # O(log n)
scheduler.enterabs(5, 1, ran.append, argument=('high',))     # lower number runs first
scheduler.enterabs(5, 1, ran.append, argument=('entered later',))

scheduler.run()  # O(n log n)
assert ran == ['high', 'entered later', 'low', 'ten']
assert clock.now == 10
```

### Running Without Blocking

`run(blocking=False)` pops only the events that are due and returns. What it returns is
the delay until the next event, not that event's time, so it can be passed straight to whatever
wait your own loop uses.

```python
import sched

class Clock:
    def __init__(self):
        self.now = 0
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds

clock = Clock()
scheduler = sched.scheduler(clock.time, clock.sleep)
ran = []
for when in (1, 2, 10):
    scheduler.enterabs(when, 1, ran.append, argument=(when,))

clock.now = 5
assert scheduler.run(blocking=False) == 5  # O(1 + d log n): ran the two due events
assert ran == [1, 2]

clock.now = 10
assert scheduler.run(blocking=False) is None  # nothing left to wait for
assert ran == [1, 2, 10]
```

## Cancelling Events

`cancel()` finds the event with a linear scan and then rebuilds the heap, so it is O(n) wherever
the event sits, including at the front. The event is gone once it has run, and cancelling it
then raises `ValueError`.

```python
import sched

class Clock:
    def __init__(self):
        self.now = 0
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds

clock = Clock()
scheduler = sched.scheduler(clock.time, clock.sleep)
ran = []

event = scheduler.enter(5, 1, ran.append, argument=('cancelled',))  # O(log n)
scheduler.enter(6, 1, ran.append, argument=('kept',))

scheduler.cancel(event)  # O(n) - scan, then heapify
scheduler.run()
assert ran == ['kept']

try:
    scheduler.cancel(event)
except ValueError:
    pass
else:
    raise AssertionError('an event no longer queued was cancelled')
```

## Inspecting the Queue

`queue` copies the heap and pops every copied event to put them in run order, which is O(n log n)
time and O(n) memory on each read. To ask whether anything is left, `empty()` is O(1).

```python
import sched

scheduler = sched.scheduler()
first = scheduler.enterabs(2, 1, print)
second = scheduler.enterabs(1, 1, print)

upcoming = scheduler.queue  # O(n log n) - a new sorted list
assert upcoming == [second, first]
assert upcoming[0].time == 1 and upcoming[0].action is print
assert scheduler.queue is not upcoming  # rebuilt on every read

assert not scheduler.empty()  # O(1)
```

## Common Patterns

### Periodic Tasks

An action can enter its own next run. Each repetition is one O(log n) push and one O(log n) pop.

```python
import sched

class Clock:
    def __init__(self):
        self.now = 0
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds

clock = Clock()
scheduler = sched.scheduler(clock.time, clock.sleep)
ticks = []

def tick(remaining):
    ticks.append(clock.time())
    if remaining > 1:
        scheduler.enter(10, 1, tick, argument=(remaining - 1,))  # O(log n)

scheduler.enter(0, 1, tick, argument=(3,))
scheduler.run()
assert ticks == [0, 10, 20]
```

### Cancelling Many Events

Cancelling k events one at a time costs O(k·n). Where most scheduled events end up cancelled, a
flag the action checks makes each cancellation O(1); the event stays queued and costs its O(log n)
pop when its time comes.

```python
import sched

class Clock:
    def __init__(self):
        self.now = 0
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds

clock = Clock()
scheduler = sched.scheduler(clock.time, clock.sleep)
cancelled = set()
ran = []

def action(name):
    if name not in cancelled:
        ran.append(name)

for index in range(100):
    scheduler.enter(index, 1, action, argument=(index,))  # O(log n)

cancelled.update(range(0, 100, 2))  # O(1) per event, no heap rebuild
scheduler.run()
assert ran == list(range(1, 100, 2))
```

## Performance Best Practices

✅ **Do**:

- Use `empty()` to check for pending work; it is O(1) where `queue` is O(n log n)
- Keep the `Event` that `enter()` returns if you may cancel it, rather than finding it again in `queue`

❌ **Avoid**:

- Reading `queue` in a loop - every read builds and sorts a new list
- Cancelling most of a large queue one event at a time - each `cancel()` is O(n)

## Version Notes

- **All Python 3**: `run(blocking=False)` returns the delay until the next event, not its
  scheduled time

## Related Modules

- **[heapq](heapq.md)** - the heap behind the queue, and the O(log n) push and pop it pays
- **[asyncio](asyncio.md)** - `loop.call_later()` and `loop.call_at()` schedule callbacks inside an event loop
- **[threading](threading.md)** - `threading.Timer` runs one delayed call on its own thread
