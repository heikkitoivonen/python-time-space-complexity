# pstats Module Complexity

The `pstats` module loads, merges, sorts and prints the statistics that `cProfile` and `profile`
collect. A `Stats` object holds the whole profile in memory: one entry per profiled function, each
carrying a dictionary of the functions that called it. Sorting builds an ordered list of those
entries, and every report copies and filters the entries in that order.

`f` is the functions in a profile, and `e` is its caller edges: the entries in all of those caller
dictionaries together. `f₂` and `e₂` are the same counts for a profile being merged in, and `c` is
the callers or callees of one printed function. Function names are priced at O(1) to hash, compare
and format. A regular-expression restriction runs its pattern once per candidate name; the
pattern's own cost is not in the bounds.

## Complexity Reference

### Stats

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pstats.Stats(*filenames_or_profiles, stream=None)` | O(f + e) | O(f + e) | For one argument. Loads the first argument and `add()`s the rest, each at `add()`'s cost; a profiler is snapshotted with its `create_stats()`. With no arguments it starts empty |
| `Stats.add(*filenames_or_profiles)` | O(f₂ + e₂ + e) per profile | O(f₂ + e₂ + e) | A filename or profiler is loaded first. A function both profiles share gets a new caller dictionary holding both sets of callers, so a merge can copy every existing edge. Drops the sort order |
| `Stats.dump_stats(filename)` | O(f + e) | O(f + e) | Writes the marshal file that `Stats(filename)` loads |
| `Stats.strip_dirs()` | O(f + e) | O(f + e) | Rebuilds every key and caller dictionary without directories. Entries that then collide are merged, each merge copying the survivor's callers, so g colliding entries with distinct callers cost O(g²). Drops the sort order |
| `Stats.sort_stats(*keys)` | O(f log f) | O(f) | Keys are strings, unambiguous prefixes of them, or `SortKey` members, not a mix; with no keys, reports go back to the unsorted order |
| `Stats.reverse_order()` | O(f) | O(1) | Reverses the sorted list in place; does nothing before `sort_stats()` |
| `Stats.print_stats(*restrictions)` | O(f) | O(f) | Copies the ordered list, then applies each restriction in turn: a string is a regex searched in every remaining name, an int keeps that many, a float in [0, 1) that fraction |
| `Stats.print_callers(*restrictions)` | O(f + Σ c log c) | O(f + c) | Selects as `print_stats()` does; each printed function's callers are sorted before printing |
| `Stats.print_callees(*restrictions)` | O(f + e + Σ c log c) first call, O(f + Σ c log c) after | O(f + e) | The first call inverts the caller graph and caches it. `strip_dirs()` clears that cache and `add()` does not, so callees printed after `add()` omit the merged calls, and a function the merge added prints with none |
| `Stats.get_stats_profile()` | O(f) | O(f) | Builds a `FunctionProfile` for every function, in sort order, into a dict keyed by bare function name, so same-named functions in different files overwrite each other |

### SortKey

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pstats.SortKey.CALLS`, `SortKey.CUMULATIVE`, `SortKey.FILENAME`, `SortKey.LINE`, `SortKey.NAME`, `SortKey.NFL`, `SortKey.PCALLS`, `SortKey.STDNAME`, `SortKey.TIME` | O(1) | O(1) | String enum members; `sort_stats()` takes them or the strings they stand for |
| `pstats.SortKey(value)` | O(1) | O(1) | Accepts the alternative spellings too: `SortKey('ncalls') is SortKey.CALLS` |

### FunctionProfile and StatsProfile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pstats.StatsProfile`, `StatsProfile.total_tt`, `StatsProfile.func_profiles` | O(1) | O(1) | What `get_stats_profile()` returns: total time and a dict of function name to `FunctionProfile` |
| `pstats.FunctionProfile`, `FunctionProfile.ncalls`, `FunctionProfile.tottime`, `FunctionProfile.percall_tottime`, `FunctionProfile.cumtime`, `FunctionProfile.percall_cumtime`, `FunctionProfile.file_name`, `FunctionProfile.line_number` | O(1) | O(1) | Dataclass fields; `ncalls` is a string, `'3/1'` for three calls of which one was primitive |

## Loading and Saving Profiles

A `Stats` object is the whole profile: loading one is linear in its functions and caller edges,
and so is writing it back out. A profiler can be handed over directly, without a file.

```python
import cProfile
import io
import os
import pstats
import tempfile

def leaf(n):
    return n * 2

def branch(n):
    total = 0
    for i in range(3):
        total += leaf(n + i)
    return total

profiler = cProfile.Profile()
profiler.runcall(branch, 10)

stats = pstats.Stats(profiler, stream=io.StringIO())  # O(f + e)
profile = stats.get_stats_profile()                    # O(f)
assert profile.func_profiles['leaf'].ncalls == '3'
assert profile.func_profiles['branch'].ncalls == '1'

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'run.prof')
    stats.dump_stats(path)                              # O(f + e)
    reloaded = pstats.Stats(path, stream=io.StringIO())  # O(f + e)

assert reloaded.get_stats_profile().func_profiles.keys() == profile.func_profiles.keys()
```

### Merging Runs

`add()` sums the counts of every function the two profiles share and unions their callers. Each
shared function gets a fresh caller dictionary, so merging a small profile into a large one can
still copy the large one's edges. An empty `Stats()` can start a merge loop.

```python
import cProfile
import io
import pstats

def work():
    return sum(range(100))

combined = pstats.Stats(stream=io.StringIO())  # O(1) - empty
for _ in range(3):
    profiler = cProfile.Profile()
    profiler.runcall(work)
    combined.add(profiler)  # O(f₂ + e₂ + e)

assert combined.get_stats_profile().func_profiles['work'].ncalls == '3'
```

## Sorting

`sort_stats()` builds a list of every entry and sorts it: O(f log f) whichever keys you pass, and
later keys only break ties. `add()` and `strip_dirs()` both discard the order, so sort last.

```python
import cProfile
import io
import pstats

def leaf(n):
    return n * 2

def branch(n):
    total = 0
    for i in range(3):
        total += leaf(n + i)
    return total

profiler = cProfile.Profile()
profiler.runcall(branch, 10)
stats = pstats.Stats(profiler, stream=io.StringIO())

stats.sort_stats(pstats.SortKey.CALLS, pstats.SortKey.NAME)  # O(f log f)
order = list(stats.get_stats_profile().func_profiles)
assert order[0] == 'leaf'  # three calls, the most

stats.reverse_order()  # O(f)
assert list(stats.get_stats_profile().func_profiles) == order[::-1]

# Strings and their unambiguous prefixes work too, but not mixed with SortKey
stats.sort_stats('ncalls', 'name')  # O(f log f)
assert list(stats.get_stats_profile().func_profiles) == order
try:
    stats.sort_stats('calls', pstats.SortKey.NAME)
except TypeError as error:
    assert 'mixed' in str(error)
else:
    raise AssertionError('a string and a SortKey were mixed')

stats.strip_dirs()  # O(f + e) - and the order is gone
stats.sort_stats(pstats.SortKey.CALLS)  # sort again after it
```

## Restricting Reports

Every print method copies the ordered list and filters it, so even `print_stats(1)` is O(f).
Restrictions apply left to right, each to what the previous one kept: a regex placed after a count
is searched in only the entries the count kept.

```python
import cProfile
import io
import pstats

def leaf(n):
    return n * 2

def branch(n):
    total = 0
    for i in range(3):
        total += leaf(n + i)
    return total

profiler = cProfile.Profile()
profiler.runcall(branch, 10)
stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream).sort_stats('calls')

stats.print_stats(1, r'\(branch\)')  # O(f) - the top entry, then the regex on it
assert '(branch)' not in stream.getvalue()  # the top entry is leaf

stream.seek(0)
stream.truncate()
stats.print_stats(r'\(branch\)', 1)  # O(f) - the regex over all f, then one match
assert '(branch)' in stream.getvalue()
```

## Walking the Call Graph

`print_callers()` reads the caller dictionaries each entry already holds. `print_callees()` needs
the reverse direction, which it builds for the whole profile on its first call and keeps.
`strip_dirs()` clears it; `add()` does not, so call `print_callees()` only after the last merge.

```python
import cProfile
import io
import pstats

def leaf(n):
    return n * 2

def branch(n):
    total = 0
    for i in range(3):
        total += leaf(n + i)
    return total

profiler = cProfile.Profile()
profiler.runcall(branch, 10)
stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream).strip_dirs()

stats.print_callers('leaf')  # O(f + c log c) - callers are stored per entry
callers = stream.getvalue()
assert 'was called by' in callers and '(branch)' in callers

stream.seek(0)
stream.truncate()
stats.print_callees('branch')  # O(f + e) the first time - inverts the graph
assert 'called...' in stream.getvalue() and '(leaf)' in stream.getvalue()
```

## Common Patterns

### Profile, Trim and Report

Every method in the `Stats` table except `get_stats_profile()` and `dump_stats()` returns the
`Stats` object, so a report is one chain. Stripping directories before sorting keeps the order the report needs.

```python
import cProfile
import io
import pstats

def parse(text):
    return text.split(',')

def run():
    rows = []
    for _ in range(50):
        rows.append(parse('a,b,c'))
    return rows

profiler = cProfile.Profile()
profiler.runcall(run)

stream = io.StringIO()
(pstats.Stats(profiler, stream=stream)
    .strip_dirs()                          # O(f + e)
    .sort_stats(pstats.SortKey.CUMULATIVE)  # O(f log f)
    .print_stats(10))                      # O(f)

report = stream.getvalue()
assert 'Ordered by: cumulative time' in report
assert '(parse)' in report
```

## Performance Best Practices

✅ **Do**:

- Call `strip_dirs()` and `add()` before `sort_stats()`: both drop the order, and sorting is the
  O(f log f) step
- Put a count before a regex in a print restriction when the top entries are all you want: the
  regex then searches only those
- Merge every run before the first `print_callees()`, which caches the callee map `add()` does not
  refresh
- Hand a profiler straight to `Stats()` instead of round-tripping it through `dump_stats()`

❌ **Avoid**:

- Looking a function up in `get_stats_profile()` by name when several files define it: only one of
  them survives
- `strip_dirs()` when files in different directories share names, lines and functions: their
  entries merge, and g such collisions with distinct callers cost O(g²)
- Re-sorting inside a loop that prints: sort once, then print with different restrictions

## Version Notes

- **Python 3.11+**: `SortKey` is a `StrEnum`, so `str(SortKey.TIME)` is `'time'`; on 3.10 it is
  `'SortKey.TIME'`

## Related Modules

- **[cProfile](cprofile.md)** - the C profiler whose output `Stats` usually reads
- **[profile](profile.md)** - the pure-Python profiler with the same output format
- **[marshal](marshal.md)** - the file format `dump_stats()` writes and `Stats(filename)` reads
- **[timeit](timeit.md)** - timing one snippet, when a whole profile is more than you need
