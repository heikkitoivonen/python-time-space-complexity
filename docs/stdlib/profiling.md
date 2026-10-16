# profiling Module Complexity

The `profiling` package, new in Python 3.15, holds the standard library's two profilers.
`profiling.tracing` is the deterministic profiler `cProfile` has always been: it runs inside the
profiled process, the interpreter calls it on every call and return, and it counts every call
exactly. `profiling.sampling` is a statistical profiler that runs as a separate process and reads
the target's stack from outside at a fixed rate; the target runs no profiler code while it is
sampled, and the report is an estimate built from the samples.

So the two have different units of cost. Tracing costs per call the profiled code makes, whatever
the run's length; sampling costs per sample taken, whatever the code does between samples.

`c` is the calls the profiled code makes, `f` the distinct functions among them, `e` the distinct
caller-callee pairs, `d` the most recorded calls open at once, and `s` the frames and bytecode
every thread is running when tracing is switched on or off; [cProfile](cprofile.md) defines them
in full, and as there, the O(s) of switching is part of every row that switches the profiler for
you. `n` is the samples a sampling run takes: at most the rate (`-r`, 1 kHz by default) times the
time it runs (`-d`, or until the program exits), and fewer when samples are missed. `k` is the most
frames in one sample, summed over the threads sampled, and `u` the distinct stacks among the
samples. Every Time bound for a profiling
run is the profiler's own work, on top of what the profiled code costs unprofiled.

## Complexity Reference

### profiling

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import profiling` | O(1) | O(1) | Imports neither profiler; `profiling.__all__` names the two submodules |

### profiling.tracing

`profiling.tracing.Profile` is `cProfile.Profile`, and `run()` and `runctx()` are `cProfile`'s too,
so every bound here is the one the [cProfile](cprofile.md#complexity-reference) page gives and
explains.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `profiling.tracing.run(command, filename=None, sort=-1)` | O(c + f log f + e) | O(f + e + d) | Runs `command` in `__main__`'s namespace, then prints the report or writes it to `filename` |
| `profiling.tracing.runctx(command, globals, locals, filename=None, sort=-1)` | O(c + f log f + e) | O(f + e + d) | Same, in the namespaces you pass |
| `profiling.tracing.main()`, `python -m profiling.tracing [-o outfile] [-s sort] (-m module \| script) [args]` | O(c + f log f + e) | O(f + e + d) | The command line, the same as `python -m cProfile` |
| `profiling.tracing.label(code)` | O(1) | O(1) | The `(filename, line, name)` key a report files a function under |
| `profiling.tracing.Profile(timer=None, timeunit=0.0, subcalls=True, builtins=True)` | O(1) | O(1) | The default timer is a wall clock |
| `Profile.enable(subcalls=True, builtins=True)`, `Profile.disable()` | O(s) | O(1) | Switch recording on and off; the table is kept |
| `with Profile() as profiler:`, `Profile.runcall(func, /, *args, **kwargs)`, `Profile.runctx(cmd, globals, locals)`, `Profile.run(cmd)` | O(c) | O(f + e + d) | Each adds to the same table |
| `Profile.clear()` | O(f + e + d) | O(1) | Discards everything recorded |
| `Profile.getstats()`, `Profile.snapshot_stats()`, `Profile.create_stats()`, `Profile.dump_stats(file)` | O(f + e) | O(f + e) | One entry per function, each with its callers |
| `Profile.print_stats(sort=-1)` | O(f log f + e) | O(f + e) | Sorts and prints one line per function |

### profiling.sampling

The sampling profiler is a command-line tool. Its Time bounds are work done by the profiler's own
process; the target pays nothing per call. An output format's Space is the size of what it
produces.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m profiling.sampling run [options] script [args]`, `run -m module` | O(n·k) | Per output format, below | Starts the program in a child process and samples it from startup; `-d` stops sampling and ends the program |
| `python -m profiling.sampling attach [options] pid` | O(n·k) | Per output format, below | Samples a process that is already running, which needs permission to read its memory |
| `python -m profiling.sampling dump pid` | O(k) | O(k) | Reads the stack once and prints it like a traceback; no sampling loop |
| `python -m profiling.sampling replay [options] file` | O(n·k) | Per output format, below | Turns a `--binary` recording into any other format without profiling again |
| `-r rate`, `-d seconds` | O(1) | O(1) | Bound n: at most the rate times the duration |
| `-a`, `--all-threads` | O(1) | O(1) | Samples every thread rather than the main one, which raises k |
| `--blocking` | O(1) | O(1) | Pauses the target's threads while each sample is read, for a consistent stack; without it the target never stops |
| `--pstats` (the default), `--collapsed`, `--flamegraph`, `--heatmap`, `--jsonl`, `--live` | O(n·k) | O(u·k) | Aggregating outputs: one entry per distinct stack or source location, with a count, however many samples land on it |
| `--gecko` | O(n·k) | O(n + u·k) | A timeline for the Firefox Profiler: one entry per sample |
| `--binary [--compression {auto,zstd,none}]` | O(n·k) | O(n·k) | Every sample, written to the file as it is taken, for `replay`: its timestamp and the frames that changed since the thread's previous sample, so a repeated stack costs O(1) |
| `profiling.sampling.Collector`, `PstatsCollector`, `CollapsedStackCollector`, `HeatmapCollector`, `GeckoCollector`, `JsonlCollector`, `StringTable` | O(1) | O(1) | Reading the names; they are the classes behind the output formats, exported without documentation, and the command line is the supported interface |

## Choosing a Profiler

### Exact Counts From Tracing

Tracing sees every call, so its counts are exact and its cost grows with the number of calls. It is
the one to use when a call count is the question, or when a function is too short for samples to
land on it.

```python
import io
import pstats
from profiling import tracing

def leaf(x):
    return x * 2

def work(n):
    return sum(leaf(i) for i in range(n))

with tracing.Profile() as profiler:  # O(c) - two events per call
    assert work(1_000) == 999_000

stats = pstats.Stats(profiler, stream=io.StringIO())  # O(f + e)
assert stats.get_stats_profile().func_profiles['leaf'].ncalls == '1000'  # exact
```

### Estimates From Sampling

Sampling reads the stack `n` times, so its cost follows the rate and the run's length rather than
the calls. The target installs no hook of any kind; the profiler finds its stack from outside, which
is why running it needs permission to read another process's memory. The default output aggregates:
a run of a thousand samples on the same few stacks produces a few lines.

```python
import os
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as directory:
    script = os.path.join(directory, 'app.py')
    output = os.path.join(directory, 'app.txt')
    with open(script, 'w') as f:
        f.write('def spin():\n    while True:\n        pass\n\nspin()\n')

    subprocess.run(
        [sys.executable, '-m', 'profiling.sampling', 'run',
         '-d', '1', '--collapsed', '-o', output, script],
        check=True, stdout=subprocess.DEVNULL,
    )  # O(n·k) in the profiler; n is about 1,000 at the default rate

    with open(output) as f:
        lines = f.read().splitlines()  # one line per distinct stack: O(u·k)
    samples = sum(int(line.rsplit(' ', 1)[1]) for line in lines)
    assert any('spin' in line for line in lines)
    assert len(lines) < samples
```

## Version Notes

- **Python 3.15+**: Added by PEP 799. `cProfile` re-exports `profiling.tracing`, and `profile` is
  deprecated

## Related Modules

- **[cProfile](cprofile.md)** - the full account of the tracing profiler's costs
- **[profile](profile.md)** - the pure-Python tracing profiler, deprecated from Python 3.15
- **[pstats](pstats.md)** - loads, sorts and prints what either profiler recorded
- **[timeit](timeit.md)** - times a snippet with no profiler in the way
