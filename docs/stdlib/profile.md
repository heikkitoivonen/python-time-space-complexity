# profile Module Complexity

The `profile` module is a deterministic profiler written in Python. It installs a function with
`sys.setprofile()`, and the interpreter calls that function on every call and return event, where
it reads a timer and updates a table of per-function totals. The table holds one entry per
function, not per call, so the memory a run needs follows the program's shape rather than its
length.

The unit of cost is the event. Every event is one Python-level call of the profiler's dispatcher,
which makes `profile` far slower per event than `cProfile`, which does the same bookkeeping in C
behind the same functions and report format. Use `profile` when you need to extend the profiler in
Python; measure with `cProfile`.

`c` is the calls the profiled code makes: calls of Python functions, each resumption of a
generator, and calls of built-in functions and methods; each costs two events. `f` is the distinct
functions among them, keyed by file, first line and name, `e` the distinct caller-callee pairs, and `d` the deepest nesting of calls.
`m` is the argument to `calibrate()`. Every Time bound for a profiling run is overhead on top of
what the profiled code costs unprofiled, and lookups in the profiler's table are treated as O(1).

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `profile.run(statement, filename=None, sort=-1)` | O(c + f log f + e) | O(f + e + d) | Runs `statement` in `__main__`'s namespace, then prints the report sorted by `sort`, or writes it to `filename`; returns `None` |
| `profile.runctx(statement, globals, locals, filename=None, sort=-1)` | O(c + f log f + e) | O(f + e + d) | Same, in the namespaces you pass |

### Profile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `profile.Profile(timer=None, bias=None)` | O(1) | O(1) | Calls `timer` at construction to see what it returns, then twice per event; the default, `time.process_time`, counts the process's CPU time, so sleeping and waiting on I/O do not show, but CPU used meanwhile by other threads does |
| `Profile.runcall(func, /, *args, **kwargs)` | O(c) | O(f + e + d) | Returns what `func` returns; `Profile` has no `enable()` or `disable()`, so this is how to profile one call. A second `runcall()` on the same instance fails unless `create_stats()` ran in between, and then the totals accumulate: use a new `Profile` per call to keep them apart |
| `Profile.runctx(cmd, globals, locals)` | O(c) | O(f + e + d) | Runs `cmd` with `exec()`; returns the profiler |
| `Profile.run(cmd)` | O(c) | O(f + e + d) | `runctx()` in `__main__`'s namespace |
| `Profile.create_stats()` | O(f + e) | O(f + e) | Snapshots the table into `.stats`, one entry per function with its callers |
| `Profile.print_stats(sort=-1)` | O(f log f + e) | O(f + e) | Builds a `pstats.Stats`, sorts it and prints one line per function |
| `Profile.dump_stats(filename)` | O(f + e) | O(f + e) | Writes the snapshot with `marshal`, for `pstats.Stats(filename)` to load |

### Calibration

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Profile.calibrate(m, verbose=0)` | O(m) | O(1) | Runs a fixed workload of m calls unprofiled and profiled, and returns the per-event time the profiler failed to subtract |
| `Profile.bias` | O(1) | O(1) | Subtracted from the time of every event; pass `bias=`, or set `Profile.bias` before creating profilers |

## Where the Overhead Goes

### One Dispatch per Event

The profiler sees calls, not work. A function that adds a million numbers in a loop produces two
events, its own call and return; a loop that calls a tiny function a million times produces two
million, and each is a Python-level dispatch. Code made of many short calls is where `profile`
slows down most.

```python
import profile
import pstats

def leaf():
    pass

def many_short_calls(n):
    for _ in range(n):
        leaf()

def one_long_call(n):
    total = 0
    for i in range(n):
        total += i
    return total

calls = profile.Profile()
calls.runcall(many_short_calls, 10_000)  # O(c) - 10,001 Python calls
by_name = pstats.Stats(calls).get_stats_profile().func_profiles
assert by_name['leaf'].ncalls == '10000'

loop = profile.Profile()
assert loop.runcall(one_long_call, 10_000) == 49_995_000  # O(1) - one call, whatever n is
by_name = pstats.Stats(loop).get_stats_profile().func_profiles
assert by_name['one_long_call'].ncalls == '1'
assert 'leaf' not in by_name
```

### What Counts as a Call

Built-in functions count, and so does every resumption of a generator, so iterating a Python
generator costs two events per item. A recursive function is one entry however deep it goes;
the report shows its calls as total/primitive.

```python
import profile
import pstats

def numbers(k):
    for i in range(k):
        yield i

def lengths(n):
    return [len('x') for _ in range(n)]

def depth(d):
    return 0 if d == 0 else depth(d - 1)

def mixed():
    sum(numbers(50))  # 51 resumptions, one per item plus the last
    lengths(100)      # 100 calls of len()
    depth(99)         # 100 calls, one of them from outside

profiler = profile.Profile()
profiler.runcall(mixed)

by_name = pstats.Stats(profiler).get_stats_profile().func_profiles
assert by_name['numbers'].ncalls == '51'
assert by_name['len'].ncalls == '100'
assert by_name['depth'].ncalls == '100/1'
```

## Memory Follows Distinct Functions

The table grows by one entry the first time a function is called, and by one caller record the
first time a given caller calls it. Calling the same function more often only updates counters.

```python
import profile

def leaf():
    pass

def repeat(n):
    for _ in range(n):
        leaf()

def entries(n):
    profiler = profile.Profile()
    profiler.runcall(repeat, n)  # O(c) time, O(f + e + d) memory
    profiler.create_stats()      # O(f + e)
    return len(profiler.stats)

assert entries(10) == entries(10_000)  # 1,000x the calls, the same table
```

## One Profiler, One Thread

`sys.setprofile()` installs its function for the calling thread only, so a thread started during
the run is not profiled. And a run cannot start while any profile function is already installed,
`cProfile` included: it fails rather than nesting.

```python
import cProfile
import profile
import threading

def worker():
    return sum(range(10))

def spawn():
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

profiler = profile.Profile()
profiler.runcall(spawn)
profiler.create_stats()
names = {name for _, _, name in profiler.stats}
assert 'spawn' in names and 'worker' not in names  # the new thread ran unprofiled

outer = cProfile.Profile()
outer.enable()
try:
    profile.Profile().runcall(worker)
except (AssertionError, TypeError):
    pass
else:
    raise AssertionError('profile started under another profiler')
finally:
    outer.disable()
```

## Calibration

The dispatcher's own time between reading the timer and returning leaks into every event, so a
function making many short calls is charged for work that is the profiler's. `calibrate(m)` runs a
fixed workload of m calls with and without profiling and returns that leak per event; setting it
as `bias` subtracts it from every event. The value depends on the machine and the moment it is
measured, and a bias set too high makes some times come out negative.

```python
import profile

bias = profile.Profile().calibrate(1_000)  # O(m) - runs the workload three times
assert isinstance(bias, float)

calibrated = profile.Profile(bias=bias)  # O(1) - this profiler only
assert calibrated.runcall(sum, range(10)) == 45
```

## Common Patterns

### Profiling One Call and Reading the Top Entries

```python
import io
import profile
import pstats
import time

def leaf(x):
    return x * 2

def work(n):
    return sum(leaf(i) for i in range(n))

profiler = profile.Profile(timer=time.perf_counter)  # a fine-grained clock on every platform
assert profiler.runcall(work, 1_000) == 999_000  # O(c)

report = io.StringIO()
stats = pstats.Stats(profiler, stream=report)  # O(f + e)
stats.sort_stats('tottime').print_stats(5)    # O(f log f), five lines printed
assert 'leaf' in report.getvalue()
```

### Saving a Report and Loading It Later

```python
import os
import profile
import pstats
import tempfile

def work():
    return sorted(range(100), reverse=True)

profiler = profile.Profile()
profiler.runcall(work)

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'work.prof')
    profiler.dump_stats(path)  # O(f + e)
    loaded = pstats.Stats(path)  # O(f + e)
    assert any(name == 'work' for _, _, name in loaded.stats)
```

## Performance Best Practices

✅ **Do**:

- Measure with `cProfile`; reach for `profile` when you need to subclass or change the profiler in Python
- Profile one call with `runcall()` rather than a whole program, so c counts only the calls you care about
- Create a new `Profile` for each `runcall()` whose report should stand alone
- Calibrate once per machine and pass the result as `bias`, if you compare functions that make many short calls
- Sort the report and read the top entries; the report is one line per function, not per call

❌ **Avoid**:

- Trusting absolute times for code made of many tiny calls: each call adds two dispatches, and that overhead dominates
- Starting `profile` while `cProfile` or another profile function is active - it fails instead of nesting
- Expecting sleeps or I/O waits in the report under the default timer, which counts CPU time

## Version Notes

- **Python 3.13+**: `Profile.print_stats()` accepts a tuple of sort keys, and so does the `sort` argument of `run()` and `runctx()`

## Related Modules

- **[cProfile](cprofile.md)** - the same interface and report, with the per-event work done in C
- **[pstats](pstats.md)** - loads, sorts and prints what a profiler recorded
- **[timeit](timeit.md)** - times a snippet with no profiler in the way
- **[sys](sys.md)** - `sys.setprofile()`, the hook `profile` is built on
