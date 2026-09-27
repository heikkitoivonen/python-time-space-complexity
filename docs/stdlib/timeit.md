# timeit Module Complexity

The `timeit` module times a small statement by running it in a loop. A `Timer` compiles the
statement and its setup into one function when it is built; each run executes the setup once,
reads the clock, runs the statement `number` times, and reads the clock again. The module's own work is
the compile and the loop: everything else is the cost of the code you hand it.

`n` is the `number` of loop iterations in one run, `r` is the `repeat` count, `k` is the loop count
`autorange()` settles on, and `c` is the characters of `stmt` and `setup` when they are strings (a
callable contributes none). `s` is the cost of one execution of the statement and `u` of one
execution of the setup; the bounds below count those as the caller's work and price the module's
own steps around them, with each clock read and each `autorange()` callback at O(1). Space is
what the module holds, not what the statement allocates.

## Complexity Reference

### Timer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `timeit.Timer(stmt='pass', setup='pass', timer=default_timer, globals=None)` | O(c) | O(c) | Compiles the strings here; runs neither |
| `Timer.timeit(number=1000000)` | O(u + n·s) | O(1) | Setup once, then the statement n times with garbage collection off |
| `Timer.repeat(repeat=5, number=1000000)` | O(r·(u + n·s)) | O(r) | r calls to `timeit()`, so the setup runs r times; returns r floats |
| `Timer.autorange(callback=None)` | O(k·s + u·log k) | O(1) | Tries 1, 2, 5, 10, 20, 50, ... loops until one run takes at least 0.2 s |
| `Timer.print_exc(file=None)` | O(c + t) | O(c + t) | t = length of the formatted traceback; shows the timed source lines |

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `timeit.timeit(stmt='pass', setup='pass', timer=default_timer, number=1000000, globals=None)` | O(c + u + n·s) | O(c) | A `Timer` and one `timeit()` call |
| `timeit.repeat(stmt='pass', setup='pass', timer=default_timer, repeat=5, number=1000000, globals=None)` | O(c + r·(u + n·s)) | O(c + r) | A `Timer` and one `repeat()` call |
| `timeit.default_timer()` | O(1) | O(1) | `time.perf_counter` |

## Timing a Statement

### Setup Runs Once per Run

The setup runs at the start of every `timeit()` call, not at construction and not per loop. The
statement shares its namespace across the n iterations of one run, so whatever it builds on the
setup's objects keeps growing until the next run's setup builds them again.

```python
import timeit

runs = []
timer = timeit.Timer(
    'x.append(1)',
    setup='x = []; runs.append(x)',
    globals={'runs': runs},
)  # O(c) - compiled here, nothing runs yet
assert runs == []

times = timer.repeat(repeat=3, number=100)  # O(r·(u + n·s))
assert len(times) == 3 and all(t >= 0 for t in times)
assert len(runs) == 3                          # setup ran once per run
assert [len(x) for x in runs] == [100, 100, 100]  # state carried across one run's loops
```

### Garbage Collection Is Off

`timeit()` disables the cyclic garbage collector for the loop and re-enables it afterwards if it
was on, so a statement whose real cost includes collection reads low. Put `gc.enable()` in the setup to
include it.

```python
import gc
import timeit

seen = []
namespace = {'seen': seen, 'gc': gc}

timeit.timeit('seen.append(gc.isenabled())', number=1, globals=namespace)
timeit.timeit('seen.append(gc.isenabled())', setup='gc.enable()', number=1, globals=namespace)

assert seen == [False, True]
assert gc.isenabled()  # back on after the run
```

### Strings or Callables

A string is compiled into the loop body, so its source length is paid once, at construction. A
callable is called once per iteration instead, which adds a function call to every loop: for a
statement cheaper than a call, the call is most of what gets measured.

```python
import timeit

calls = 0

def work():
    global calls
    calls += 1

timer = timeit.Timer(work)  # O(1) - independent of work's body
timer.timeit(number=1_000)  # O(n) calls
assert calls == 1_000

# A string statement runs inline, with no call per loop
inline = timeit.Timer('y = 1 + 1')
assert inline.timeit(number=1_000) >= 0
```

## Choosing the Loop Count

`autorange()` runs the timer with 1, 2, 5, 10, 20, 50, ... loops until one run takes at least
0.2 seconds, and returns that loop count and its time. Each step is at least double the one
before, so all the trials together execute the statement fewer than 2k times, and the setup
once per trial.

```python
import timeit

clock = 0.0

def work():
    global clock
    clock += 2 ** -12  # each execution "takes" 1/4096 s on this clock

trials = []
timer = timeit.Timer(work, timer=lambda: clock)
number, taken = timer.autorange(lambda n, t: trials.append(n))  # O(k·s + u·log k)

assert number == 1_000 and taken >= 0.2
assert trials == [1, 2, 5, 10, 20, 50, 100, 200, 500, 1_000]
assert sum(trials) < 2 * number
```

### Reporting a Failure

An exception in the timed code propagates out of `timeit()`. `print_exc()` prints its traceback
with the lines of the compiled statement.

```python
import io
import timeit

timer = timeit.Timer('1 / 0')
output = io.StringIO()
try:
    timer.timeit(number=1)
except ZeroDivisionError:
    timer.print_exc(file=output)  # O(c + t)
else:
    raise AssertionError('the timed division succeeded')

assert '1 / 0' in output.getvalue()
```

## The Command Line

`python -m timeit` builds one `Timer` from its arguments. Without `-n`, it calls `autorange()`
first and then runs `-r` repeats (5 by default) of the count it found; given a positive `-n`, it
skips the search. It prints the best per-loop time.

```python
import subprocess
import sys

result = subprocess.run(
    [sys.executable, '-m', 'timeit', '-n', '1000', '-r', '3', '-s', 'x = list(range(100))',
     'sum(x)'],
    capture_output=True, text=True, check=True,
)
assert result.stdout.startswith('1000 loops, best of 3: ')
```

## Common Patterns

### Comparing Two Implementations

Run each candidate with the same `number` and `repeat`, and compare the minimum of each: the
fastest run is the one least disturbed by the rest of the machine.

```python
import timeit

setup = 'parts = [str(i) for i in range(100)]'

joined = min(timeit.repeat("''.join(parts)", setup=setup, number=1_000, repeat=3))

concatenated = min(timeit.repeat(
    "s = ''\nfor p in parts:\n    s += p",
    setup=setup, number=1_000, repeat=3,
))  # O(c + r·(u + n·s)) each

assert joined > 0 and concatenated > 0
```

## Performance Best Practices

✅ **Do**:

- Put fixed preparation in `setup`: it runs once per run, not once per loop
- Report `min(repeat(...))` and let `autorange()` or the command line choose `number`
- Pass a string for a statement cheaper than a function call; a callable adds a call per loop
- Add `gc.enable()` to the setup when collection is part of the cost you want to see

❌ **Avoid**:

- A statement that grows what the setup built: `x.insert(0, 1)` over n loops inserts into lists
  of every length up to n, so a run is O(n²) and the per-loop time depends on `number`

## Related Modules

- **[time](time.md)** - `perf_counter`, the default timer, and the other clocks it can be swapped for
- **[cProfile](cprofile.md)** - where a whole program spends its time, rather than one statement
- **[profile](profile.md)** - the pure-Python profiler with the same interface
- **[gc](gc.md)** - the collector `timeit()` switches off while it measures
