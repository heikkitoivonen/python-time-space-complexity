# cProfile Module Complexity

The `cProfile` module is the C implementation of the `profile` interface: a `Profile` class with
the same running and reporting methods, the same `run()` and `runctx()`, and the same report
through `pstats`. While a profiler is enabled, the interpreter calls its C hooks on every call and
return event, and each one reads a timer and updates a table of per-function totals. The table
holds one entry per function, not per call, so the memory a run needs follows the program's shape
rather than its length.

`c` is the calls the profiled code makes: calls of Python functions, each resumption of a
generator, and calls of built-in functions and methods; each costs two events. `f` is the distinct
functions among them, counted by code object, so the closures one `def` makes are one function; `e`
is the distinct caller-callee pairs, and `d` the most recorded calls open at once: the deepest
nesting of calls, or from Python 3.12, where every thread is recorded, the open calls of all
threads together. `s` is the size of what every thread is running at the moment the profiler is
switched on or off: the frames on each stack and the bytecode of the functions they are in. From
Python 3.12, `enable()` and `disable()` rework each of them, and that cost is part of every row
that switches the profiler for you without being restated there. Every Time bound for a profiling
run is overhead on top of what the profiled code costs unprofiled, and lookups in the profiler's
table and each called function's bytecode size are treated as O(1).

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cProfile.run(statement, filename=None, sort=-1)` | O(c + f log f + e) | O(f + e + d) | Runs `statement` in `__main__`'s namespace, then prints the report sorted by `sort`, or writes it to `filename`; returns `None` |
| `cProfile.runctx(statement, globals, locals, filename=None, sort=-1)` | O(c + f log f + e) | O(f + e + d) | Same, in the namespaces you pass |
| `cProfile.main()`, `python -m cProfile [-o outfile] [-s sort] (-m module \| script) [args]` | O(c + f log f + e) | O(f + e + d) | The command line: profiles a script, or a module with `-m`, and prints the report sorted by `-s`, or writes it to `-o`; the script is compiled first, unprofiled |
| `cProfile.label(code)` | O(1) | O(1) | The `(filename, line, name)` key a report files a function under; a built-in gets `('~', 0, name)` |

### Profile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cProfile.Profile(timer=None, timeunit=0.0, subcalls=True, builtins=True)` | O(1) | O(1) | The default timer is a wall clock, so sleeping and waiting on I/O count. A custom `timer` is read once per event; `timeunit` is the seconds in one unit when it returns integers |
| `Profile.enable(subcalls=True, builtins=True)` | O(s) | O(1) | Starts recording into the table, adding to whatever it holds. `subcalls=False` keeps no caller records, which removes e; `builtins=False` leaves built-in calls out of c |
| `Profile.disable()` | O(s) | O(1) | Stops recording; the table is kept |
| `with cProfile.Profile() as profiler:` | O(c) | O(f + e + d) | `enable()` on entry, `disable()` on exit |
| `Profile.runcall(func, /, *args, **kwargs)` | O(c) | O(f + e + d) | Returns what `func` returns. Each call adds to the same table, so use a new `Profile` per call to keep them apart |
| `Profile.runctx(cmd, globals, locals)` | O(c) | O(f + e + d) | Runs `cmd` with `exec()`; returns the profiler |
| `Profile.run(cmd)` | O(c) | O(f + e + d) | `runctx()` in `__main__`'s namespace |
| `Profile.clear()` | O(f + e + d) | O(1) | Discards everything recorded |

### Reading the results

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Profile.getstats()` | O(f + e) | O(f + e) | One raw entry per function, each listing the functions it called |
| `Profile.snapshot_stats()` | O(f + e) | O(f + e) | Builds `.stats`, the `pstats` format: one entry per function with its callers |
| `Profile.create_stats()` | O(f + e) | O(f + e) | `disable()`, then `snapshot_stats()` |
| `Profile.print_stats(sort=-1)` | O(f log f + e) | O(f + e) | Builds a `pstats.Stats` from the profiler, which disables it, then strips directories, sorts and prints one line per function |
| `Profile.dump_stats(filename)` | O(f + e) | O(f + e) | `create_stats()`, then writes `.stats` with `marshal` for `pstats.Stats(filename)` to load |

## Where the Overhead Goes

### One Event per Call and Return

The profiler sees calls, not work. A function that adds up ten thousand numbers in a loop produces
two events, its own call and return; a loop that calls a tiny function ten thousand times produces
twenty thousand. Each event is handled in C, which is why `cProfile` costs far less per event than
`profile`, but code made of many short calls is still where it adds the most.

```python
import cProfile
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

calls = cProfile.Profile()
calls.runcall(many_short_calls, 10_000)  # O(c) - 10,001 Python calls
by_name = pstats.Stats(calls).get_stats_profile().func_profiles
assert by_name['leaf'].ncalls == '10000'

loop = cProfile.Profile()
assert loop.runcall(one_long_call, 10_000) == 49_995_000  # O(1) - one call, whatever n is
by_name = pstats.Stats(loop).get_stats_profile().func_profiles
assert by_name['one_long_call'].ncalls == '1'
assert 'leaf' not in by_name
```

### What Counts as a Call

Built-in functions count, and so does every resumption of a generator, so iterating a Python
generator costs two events per item. A recursive function is one entry however deep it goes; the
report shows its calls as total/primitive. `builtins=False` leaves the built-in calls out.

```python
import cProfile
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

profiler = cProfile.Profile()
profiler.runcall(mixed)

by_name = pstats.Stats(profiler).get_stats_profile().func_profiles
assert by_name['numbers'].ncalls == '51'
assert by_name['<built-in method builtins.len>'].ncalls == '100'
assert by_name['depth'].ncalls == '100/1'

python_only = cProfile.Profile()
python_only.enable(builtins=False)  # O(s)
mixed()
python_only.disable()               # O(s)
by_name = pstats.Stats(python_only).get_stats_profile().func_profiles
assert by_name['depth'].ncalls == '100/1'
assert '<built-in method builtins.len>' not in by_name
```

## Memory Follows Distinct Functions

The table grows by one entry the first time a function is called, and by one caller record the
first time a given caller calls it. Calling the same function more often only updates counters.
`subcalls=False` keeps no caller records at all.

```python
import cProfile

def leaf():
    pass

def repeat(n):
    for _ in range(n):
        leaf()

def entries(n):
    profiler = cProfile.Profile()
    profiler.runcall(repeat, n)  # O(c) time, O(f + e + d) memory
    profiler.create_stats()      # O(f + e)
    return len(profiler.stats)

assert entries(10) == entries(10_000)  # 1,000x the calls, the same table

flat = cProfile.Profile()
flat.enable(subcalls=False)
repeat(10)
flat.disable()
flat.create_stats()
assert all(callers == {} for *_, callers in flat.stats.values())
```

## Switching the Profiler On and Off

`enable()` and `disable()` can bracket any code, as often as you like: every enabled stretch adds
to the same table, and so does every `runcall()`. `clear()` empties it. Pass `subcalls` and
`builtins` to `enable()` rather than to `Profile()`: on Python 3.14, an `enable()` without
arguments, which is what `runcall()`, `run()`, `runctx()` and a `with` block call, turns both back
on.

```python
import cProfile

def leaf():
    pass

def ncalls(profiler):
    profiler.snapshot_stats()  # O(f + e)
    return {key[2]: value[1] for key, value in profiler.stats.items()}

profiler = cProfile.Profile()
with profiler:  # enable() ... disable()
    leaf()
profiler.runcall(leaf)  # O(c) - adds to the same table
assert ncalls(profiler)['leaf'] == 2

profiler.clear()  # O(f + e + d)
assert ncalls(profiler) == {}
```

## Wall-Clock Time

The default timer is a wall clock, so a function that sleeps or waits on I/O is charged for the
wait. Pass another timer to measure something else, such as `time.process_time` for CPU time; it
is called once per event. A timer that returns integers is scaled by `timeunit`.

```python
import cProfile
import time

def nap():
    time.sleep(0.05)

profiler = cProfile.Profile()
profiler.runcall(nap)
profiler.create_stats()
cumulative = {key[2]: value[3] for key, value in profiler.stats.items()}
assert cumulative['nap'] >= 0.04  # the sleep is in the wall-clock time

ticks = 0

def counter():  # one tick per read
    global ticks
    ticks += 1
    return ticks

def leaf():
    pass

def many(n):
    for _ in range(n):
        leaf()

profiler = cProfile.Profile(counter, timeunit=0.001)  # O(1)
profiler.enable(builtins=False)
many(100)
profiler.disable()
profiler.create_stats()
inline = {key[2]: value[2] for key, value in profiler.stats.items()}
assert abs(inline['leaf'] - 100 * 0.001) < 1e-9  # one read on entry, one on return
```

## Common Patterns

### Profiling a Block and Reading the Top Entries

```python
import cProfile
import io
import pstats

def leaf(x):
    return x * 2

def work(n):
    return sum(leaf(i) for i in range(n))

with cProfile.Profile() as profiler:  # O(c)
    assert work(1_000) == 999_000

report = io.StringIO()
stats = pstats.Stats(profiler, stream=report)  # O(f + e)
stats.sort_stats('tottime').print_stats(5)    # O(f log f), five lines printed
assert stats.get_stats_profile().func_profiles['leaf'].ncalls == '1000'
```

### Saving a Report and Loading It Later

```python
import cProfile
import os
import pstats
import tempfile

def work():
    return sorted(range(100), reverse=True)

profiler = cProfile.Profile()
profiler.runcall(work)

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'work.prof')
    profiler.dump_stats(path)  # O(f + e)
    loaded = pstats.Stats(path)  # O(f + e)
    assert any(name == 'work' for _, _, name in loaded.stats)
```

### Profiling a Script From the Command Line

```python
import os
import pstats
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as directory:
    script = os.path.join(directory, 'app.py')
    output = os.path.join(directory, 'app.prof')
    with open(script, 'w') as f:
        f.write('def leaf():\n    pass\n\nfor _ in range(10):\n    leaf()\n')

    subprocess.run(
        [sys.executable, '-m', 'cProfile', '-o', output, script],
        check=True,
    )  # O(c + f + e) - written to the file, nothing printed

    by_name = pstats.Stats(output).get_stats_profile().func_profiles
    assert by_name['leaf'].ncalls == '10'
```

## Performance Best Practices

✅ **Do**:

- Measure with `cProfile` rather than `profile`; the per-event work is done in C
- Profile one call or one block with `runcall()` or `with`, so c counts only the calls you care about
- Create a new `Profile` for each run whose report should stand alone, or `clear()` the old one
- Pass `subcalls=False` or `builtins=False` to `enable()` when you do not need callers or built-ins
- Sort the report and read the top entries; the report is one line per function, not per call

❌ **Avoid**:

- Trusting absolute times for code made of many tiny calls: each call adds two events, and that overhead dominates
- Reading CPU cost from the default timer: it is a wall clock, so sleeps and I/O waits are in the times
- Passing `subcalls` or `builtins` only to `Profile()` on Python 3.14, where `runcall()` and `with` turn them back on

## Version Notes

- **Python 3.12+**: Events come from `sys.monitoring`. Calls made in every thread are recorded while a profiler is enabled, enabling a second one raises `ValueError` instead of silently taking over from the first, and `enable()` and `disable()` rework what every thread is running (the s term)
- **Python 3.13+**: `Profile.print_stats()` accepts a tuple of sort keys, and so does the `sort` argument of `run()` and `runctx()`
- **Python 3.14+**: `enable()` with no arguments turns `subcalls` and `builtins` back on, discarding what was passed to `Profile()`

## Related Modules

- **[profile](profile.md)** - the same interface in pure Python, for extending the profiler
- **[pstats](pstats.md)** - loads, sorts and prints what a profiler recorded
- **[timeit](timeit.md)** - times a snippet with no profiler in the way
- **[sys](sys.md)** - `sys.monitoring`, the event source `cProfile` uses from Python 3.12
