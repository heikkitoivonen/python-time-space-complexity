# trace Module Complexity

The `trace` module counts which source lines run, prints them as they run, or lists the functions a
program calls. It works through `sys.settrace()`: the interpreter calls a Python-level hook on
every call event and, in the counting and printing modes, on every line of code the tracer does not
ignore. That hook is the cost. A traced program pays a Python function call per line on top of its
own work, while the counts it keeps grow with the program's distinct lines, not with how long it
runs.

`e` is the line events of traced code: lines executed, counting every repetition. `c` is the calls
of Python functions made while tracing. `L` is the distinct (file, line) pairs counted, `F` the
distinct functions called, which is what `countfuncs` records, and `P` the distinct caller-callee
pairs recorded by `countcallers`. `H` is the objects the garbage collector tracks, `S` the source
lines of the files that produced line events, and `m` and `d` the entries in `ignoremods` and
`ignoredirs`. `r` is the entries read from an `infile`, and `k` the entries in the object passed to
`update()`. Time bounds for a tracing run are overhead on top of what the traced code costs
untraced, and leave out the one-time ignore check per module that *Code in ignored modules*
prices; space bounds for a run are what the tracer and `linecache` keep once it ends. Dict lookups
and path lengths are treated as O(1).

## Complexity Reference

### Trace

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `trace.Trace(count=1, trace=1, countfuncs=0, countcallers=0, ignoremods=(), ignoredirs=(), infile=None, outfile=None, timing=False)` | O(m + d) | O(m + d) | Reads no file; `infile` is read by `results()`. `countcallers` overrides `countfuncs`, which overrides `count` and `trace`. With all four false, a run installs no hook and traces nothing |
| `Trace.run(cmd)` | By mode | By mode | `runctx()` in `__main__`'s namespace; *Tracing modes* below prices a run |
| `Trace.runctx(cmd, globals=None, locals=None)` | By mode | By mode | Installs the hook with `sys.settrace()` and `threading.settrace()`, so threads started during the run are traced too; afterwards both are set to `None`, which also removes a hook that was installed before the call |
| `Trace.runfunc(func, /, *args, **kwds)` | By mode | By mode | Traces the calling thread only, then sets `sys.settrace(None)`; returns what `func` returns |
| `Trace.results()` | O(L + F + P + r) | O(L + F + P + r) | Builds a `CoverageResults` whose `counts` is the tracer's own dict, not a copy. With `infile`, every call merges the file into that dict again, so call it once |

### Tracing modes

The first four rows price a whole run of `run()`, `runctx()` or `runfunc()`; the last two say
what code the tracer skips costs inside one.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Trace(count=True, trace=False)` | O(e + c) | O(L) | Each line event adds one to that line's count |
| `Trace(count=False, trace=True)` | O(e + c + S) | O(S) | Prints the file, line number and source of each line event; `linecache` loads, and keeps, the source of every file it prints from. With `count=True` as well, the default, the two costs add |
| `Trace(countfuncs=True)` | O(c + F·H) | O(F) | No line events at all, and no ignore check: every function called is recorded. The first time each function is seen it is named with up to three `gc.get_referrers()` scans, each O(H), then cached per tracer |
| `Trace(countcallers=True)` | O(c + F·H) | O(P) | No line events and no ignore check; the caller and callee of each call are both named, with the same first-sighting scan |
| Code in ignored modules, counting and printing modes | O(1) per call event | O(1) | No line events. Each module name is checked against `ignoremods` and `ignoredirs` once, in O(m + d), and its answer cached. `ignoremods` is matched against the file's base name, so a package module is not ignored by its dotted name; use `ignoredirs` |
| Code whose globals have no `__file__`, counting and printing modes | O(1) per call event | O(1) | Not traced: `runctx(cmd)` with no `globals` executes in an empty dict, so functions `cmd` defines produce no counts |

### CoverageResults

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `trace.CoverageResults(counts=None, calledfuncs=None, infile=None, callers=None, outfile=None)` | O(L + F + P + r) | O(L + F + P + r) | Made by `Trace.results()` rather than directly; loads and merges `infile` if given |
| `CoverageResults.update(other)` | O(k) | O(k) | Adds `other`'s line counts into this one's and takes the union of its functions and callers |
| `CoverageResults.write_results(show_missing=True, summary=False, coverdir=None, *, ignore_missing_files=False)` | O(L + S + F log F + P log P) | O(L + S + F + P) | Writes one `.cover` file per counted source file, holding every line of that file, beside the source unless `coverdir` is given. `show_missing` compiles each file to find the executable lines. Files named like `<string>` are skipped. `summary` also sorts the M files reported, adding O(M log M). `outfile`, if set, is pickled in O(L + F + P). `ignore_missing_files` is Python 3.13+ |

### Command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m trace --count [--missing] [--coverdir DIR] prog.py` | O(e + c + L + S) | O(L + S) | Runs the program under `Trace.runctx()`, then `write_results()` unless `--no-report` is given |
| `python -m trace --report --file FILE` | O(L + S + F log F + P log P) | O(L + S + F + P) | Writes the reports from a counts file saved by an earlier `--file` run, without executing anything |

## Counting Lines

A counting run keeps one integer per distinct line, so a loop that runs a million times costs a
million hook calls but still only one entry per line it covers.

```python
import trace

def total(n):
    result = 0
    for i in range(n):
        result += i
    return result

tracer = trace.Trace(count=True, trace=False)  # O(m + d)
assert tracer.runfunc(total, 1_000) == 499_500  # O(e) hook calls, e = 2,003 here

first = total.__code__.co_firstlineno
counts = {line - first: hits for (name, line), hits in tracer.counts.items()}
assert counts == {1: 1, 2: 1_001, 3: 1_000, 4: 1}  # O(L) - four lines, not 2,003 entries
```

### Writing the Report

`write_results()` costs the length of every file that has counts, not the lines that ran: each
`.cover` file repeats the whole source, with a count in front of each line that ran and, with
`show_missing`, a `>>>>>>` marker in front of each executable line that did not. Pass `coverdir`,
or the reports land beside the sources.

```python
import os
import tempfile
import trace

def calculate(x, y):
    result = x + y
    if result < 0:
        result = 0
    return result

tracer = trace.Trace(count=True, trace=False)
tracer.run('calculate(2, 3)')  # O(e + c), in __main__'s namespace
results = tracer.results()     # O(L + F + P)

with tempfile.TemporaryDirectory() as coverdir:
    results.write_results(show_missing=True, coverdir=coverdir)  # O(L + S)
    [report] = os.listdir(coverdir)
    with open(os.path.join(coverdir, report)) as f:
        lines = f.read().splitlines()

with open(__file__) as f:
    assert len(lines) == len(f.read().splitlines())  # every source line, run or not

assert any(line.startswith('>>>>>>') and 'result = 0' in line for line in lines)
assert any(line.lstrip().startswith('1:') and 'return result' in line for line in lines)
```

## Choosing a Mode

### Functions Instead of Lines

`countfuncs` and `countcallers` install no line hook, so their cost follows calls rather than
lines. The first time each function is seen it is named by scanning the garbage collector's
objects, which is O(H); later calls to it hit a per-tracer cache.

```python
import sys
import trace

def body():
    frame_hook = sys._getframe().f_trace
    for _ in range(1_000):
        pass
    return frame_hook

def main():
    return [body() for _ in range(3)]

tracer = trace.Trace(count=False, trace=False, countfuncs=True)
hooks = tracer.runfunc(main)  # O(c), plus O(H) per function seen for the first time

assert hooks == [None, None, None]  # no line hook in the traced frames
assert tracer.counts == {}
names = {name for _, _, name in tracer.results().calledfuncs}
assert {'main', 'body'} <= names
```

### Printing Every Line

`trace=True` prints every line event with its source, so the output alone is O(e), and the first
line printed from each file loads that file into `linecache`.

```python
import contextlib
import io
import trace

def repeat(n):
    for _ in range(n):
        pass

output = io.StringIO()
with contextlib.redirect_stdout(output):
    trace.Trace(count=False, trace=True).runfunc(repeat, 50)  # O(e + c + S)

printed = [line for line in output.getvalue().splitlines() if '): ' in line]
assert len(printed) == 50 + 51  # the body 50 times, the loop header 51
```

## Limiting What Gets Traced

### Ignoring the Standard Library

An ignored module still costs a call event, but it produces no line events, so the run pays for
your lines only. `ignoremods` compares module base names (`decoder`, not `json.decoder`), so
directories are the reliable way to exclude a package.

```python
import json
import os
import trace

package = os.path.dirname(json.__file__)

traced = trace.Trace(count=True, trace=False)
traced.runfunc(json.loads, '[1, 2]')
assert any(name.startswith(package) for name, _ in traced.counts)

by_name = trace.Trace(count=True, trace=False, ignoremods=['json'])
by_name.runfunc(json.loads, '[1, 2]')
assert any(name.startswith(package) for name, _ in by_name.counts)  # still traced

by_dir = trace.Trace(count=True, trace=False, ignoredirs=[package])  # O(m + d)
by_dir.runfunc(json.loads, '[1, 2]')
assert by_dir.counts == {}
```

### Threads

`runctx()` and `run()` also install the hook for threads started during the run; `runfunc()`
does not. Both leave `sys.gettrace()` as `None`, not as whatever it was before.

```python
import sys
import threading
import trace

def worker():
    return 1

def spawn():
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

worker_line = (__file__, worker.__code__.co_firstlineno + 1)

by_func = trace.Trace(count=True, trace=False)
by_func.runfunc(spawn)
assert worker_line not in by_func.counts

by_ctx = trace.Trace(count=True, trace=False)
by_ctx.runctx('spawn()', globals())
assert by_ctx.counts[worker_line] == 1

assert sys.gettrace() is None
```

## Accumulating Across Runs

`outfile` pickles the counts when `write_results()` runs, and a later tracer's `infile` merges
them back in, which is how the command line's `--file` adds runs together.

```python
import os
import tempfile
import trace

def step():
    return 1

with tempfile.TemporaryDirectory() as workdir:
    counts_file = os.path.join(workdir, 'counts')
    for _ in range(2):
        tracer = trace.Trace(count=True, trace=False, infile=counts_file, outfile=counts_file)
        tracer.runfunc(step)
        results = tracer.results()  # O(L + F + P + r), merges the saved counts once
        results.write_results(show_missing=False, coverdir=workdir)  # pickles O(L + F + P)

line = step.__code__.co_firstlineno + 1
assert results.counts[(__file__, line)] == 2
```

### From the Command Line

```python
import os
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as workdir:
    program = os.path.join(workdir, 'prog.py')
    with open(program, 'w') as f:
        f.write('total = 0\nfor i in range(10):\n    total += i\n')

    coverdir = os.path.join(workdir, 'cover')
    subprocess.run(
        [sys.executable, '-m', 'trace', '--count', '--missing',
         '--coverdir', coverdir, program],
        check=True, capture_output=True,
    )  # O(e + c + L + S)

    with open(os.path.join(coverdir, 'prog.cover')) as f:
        report = f.read().splitlines()

assert report[1].split(':')[0].strip() == '11'  # the loop header ran 11 times
assert report[2].split(':')[0].strip() == '10'
```

## Performance Best Practices

✅ **Do**:

- Pass `ignoredirs` for the standard library and site-packages when counting or printing lines,
  so the run pays line events only for your own code
- Use `countfuncs` or `countcallers` when you need which functions ran, not which lines: they
  install no line hook
- Pass `coverdir` to `write_results()`, and `show_missing=False` when the unexecuted-line markers
  are not needed, which skips compiling every file
- Call `results()` once per tracer

❌ **Avoid**:

- Tracing a long-running loop line by line when a function list would answer the question - every
  line event is a Python-level call
- `ignoremods` with a dotted package name - it matches base names only

## Version Notes

- **Python 3.13+**: `write_results()` takes `ignore_missing_files`; without it, counts for a
  file that no longer exists raise `FileNotFoundError`

## Related Modules

- **[sys](sys.md)** - `sys.settrace()`, the hook every tracer installs
- **[cProfile](cprofile.md)** - per-function time with a C hook, when lines are not needed
- **[profile](profile.md)** - the same per-function report with a Python hook
- **[dis](dis.md)** - the line table `show_missing` reads to find executable lines
- **[linecache](linecache.md)** - the source cache the trace mode and the reports read
- **[gc](gc.md)** - `get_referrers()`, which names each function the first time it is seen
