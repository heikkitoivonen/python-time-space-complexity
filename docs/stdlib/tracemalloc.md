# tracemalloc Module Complexity

The `tracemalloc` module hooks Python's memory allocators. While tracing is on, every allocation
records a trace - the block's size and the traceback that allocated it - in a C table keyed by
address, and freeing the block removes it. Nothing allocated before `start()` is traced, and
`stop()` discards every trace.

The cost lands in two places: every allocation pays to capture its traceback while tracing is on,
and a snapshot copies the whole table into Python objects. `t` is the traces held, by the tracer
(one per live block allocated since tracing started) or by a snapshot; `f` is the frames stored
per traceback, at most the `nframe` passed to `start()` (1 by default); `d` is the depth of the
call stack at an allocation; `u` is the distinct tracebacks among a snapshot's traces; `r` is the
distinct tracebacks the tracer has recorded since tracing started or was last cleared, which
freeing a block does not forget; `g` is the groups a statistics call returns; and `p` is the
filters passed to `filter_traces()`. Filename hashing and matching are priced at O(1) per frame.
The bounds assume the default memory domain; each further domain a C extension tracks through the
C API adds one table to walk.

## Complexity Reference

### Tracing control

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tracemalloc.start(nframe=1)` | O(1) | O(f) | Installs the allocator hooks; a second call with a valid `nframe` while tracing changes nothing, not even the limit |
| An allocation while tracing | O(d) | O(1), O(f) for a new traceback | Walks the whole call stack to count its frames, even when `nframe` stores only one |
| A free while tracing | O(1) | O(1) | Removes the block's trace |
| `tracemalloc.stop()` | O(t + r·f) | O(1) | Unhooks the allocators and discards every trace; take a snapshot first |
| `tracemalloc.clear_traces()` | O(t + r·f) | O(1) | Discards every trace and recorded traceback but keeps tracing; current and peak both drop to 0 |
| `tracemalloc.is_tracing()` | O(1) | O(1) | |
| `tracemalloc.get_traceback_limit()` | O(1) | O(1) | The `nframe` tracing was started with |
| `tracemalloc.get_traced_memory()` | O(1) | O(1) | Two running counters, `(current, peak)`; `(0, 0)` when not tracing |
| `tracemalloc.reset_peak()` | O(1) | O(1) | Sets peak to current; does nothing when not tracing |
| `tracemalloc.get_tracemalloc_memory()` | O(1) | O(1) | Reads the tables' sizes; the overhead it reports grows as O(t + r·f) |
| `tracemalloc.get_object_traceback(obj)` | O(f) | O(f) | One lookup by address; `None` for an object allocated before `start()` |
| `tracemalloc.take_snapshot()` | O(t + u·f) | O(t + u·f) | Copies every trace, one shared tuple per distinct traceback; `RuntimeError` when not tracing |

### Snapshot

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Snapshot.statistics(key_type, cumulative=False)` | O(t·f + g log g) | O(u) | g = groups returned, largest first; O(t + u·f + g log g) on Python 3.14+ unless `cumulative=True`; `'traceback'` and `cumulative=True` take O(u·f) space |
| `Snapshot.compare_to(old_snapshot, key_type, cumulative=False)` | O(t·f + g log g) | O(u) | Groups both snapshots, so t and u count both; otherwise as `statistics()` |
| `Snapshot.filter_traces(filters)` | O(t·p) | O(t) | A new snapshot sharing the tracebacks; `all_frames=True` tests every frame, O(t·p·f) |
| `Snapshot.dump(filename)` | O(t + u·f) | O(t + u·f) | Pickles the snapshot; each shared traceback is written once |
| `Snapshot.load(filename)` | O(t + u·f) | O(t + u·f) | Static method; the loaded tracebacks are shared again |
| `Snapshot.traces` | O(1) | O(1) | A sequence of `Trace`; `len()` and indexing are O(1), iterating and `in` are O(t) |
| `Snapshot.traceback_limit` | O(1) | O(1) | The `nframe` in force when the snapshot was taken |

### Trace

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Trace.size`, `Trace.domain` | O(1) | O(1) | Bytes in the block, and the address space it was traced in |
| `Trace.traceback` | O(f) | O(f) | Builds a new `Traceback` on every access |

### Traceback

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(traceback)`, `traceback[i]` | O(1) | O(1) | Frames run oldest first; `traceback[i]` builds a `Frame` |
| `Traceback.total_nframe` | O(1) | O(1) | The stack depth at the allocation, which can exceed `len(traceback)`; set on `Trace.traceback` only, `None` elsewhere |
| `Traceback.format(limit=None, most_recent_first=False)` | O(f) | O(f) | Plus `linecache`: the first line read from a file loads that whole file |

### Frame

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Frame.filename`, `Frame.lineno` | O(1) | O(1) | |

### Filter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tracemalloc.Filter(inclusive, filename_pattern, lineno=None, all_frames=False, domain=None)` | O(1) | O(1) | `filename_pattern` is an `fnmatch` pattern |
| `Filter.inclusive`, `Filter.filename_pattern`, `Filter.lineno`, `Filter.all_frames`, `Filter.domain` | O(1) | O(1) | By default only the most recent frame of a trace is matched |

### DomainFilter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tracemalloc.DomainFilter(inclusive, domain)` | O(1) | O(1) | Matches `Trace.domain` and ignores frames |
| `DomainFilter.inclusive`, `DomainFilter.domain` | O(1) | O(1) | |

### Statistic

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Statistic.size`, `Statistic.count`, `Statistic.traceback` | O(1) | O(1) | Total bytes and blocks in one group |

### StatisticDiff

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `StatisticDiff.size`, `StatisticDiff.count`, `StatisticDiff.traceback` | O(1) | O(1) | The group in the newer snapshot |
| `StatisticDiff.size_diff`, `StatisticDiff.count_diff` | O(1) | O(1) | Newer minus older; the list is sorted by the absolute `size_diff` |

## Tracing Costs Every Allocation

While tracing is on, each allocation walks the whole call stack: it stores at most `nframe`
frames but counts all of them for `total_nframe`. A small `nframe` keeps traces small; it does
not make a deep call stack cheap to trace.

```python
import tracemalloc

def nested(levels):
    if levels == 0:
        return bytearray(1000)
    return nested(levels - 1)

tracemalloc.start()  # O(1) - nframe=1 stores one frame per trace
assert tracemalloc.is_tracing()
assert tracemalloc.get_traceback_limit() == 1

block = nested(20)  # O(d) - all 20+ frames are walked
assert len(tracemalloc.get_object_traceback(block)) == 1  # O(f)

snapshot = tracemalloc.take_snapshot()
deepest = max(trace.traceback.total_nframe for trace in snapshot.traces)
assert deepest > 20  # counted, though only one frame was stored

# A second start() changes nothing, not even the limit
tracemalloc.start(25)
assert tracemalloc.get_traceback_limit() == 1

tracemalloc.stop()  # O(t + r·f) - every trace is discarded
assert tracemalloc.get_object_traceback(block) is None
```

Only allocations made after `start()` are traced:

```python
import tracemalloc

before = bytearray(1000)
tracemalloc.start()
after = bytearray(1000)

assert tracemalloc.get_object_traceback(before) is None  # O(1) - no trace
assert tracemalloc.get_object_traceback(after) is not None  # O(f)

tracemalloc.stop()
```

## Measuring Current and Peak Memory

`get_traced_memory()` reads two counters that every traced allocation and free keeps up to date,
so it costs the same however many blocks are traced. It counts the traced blocks only;
`get_tracemalloc_memory()` reports what the traces themselves occupy.

```python
import tracemalloc

tracemalloc.start()

data = bytearray(1_000_000)
current, peak = tracemalloc.get_traced_memory()  # O(1)
assert current >= 1_000_000 and peak >= current

del data
current, peak = tracemalloc.get_traced_memory()
assert current < 1_000_000 <= peak  # the peak remembers the freed block

tracemalloc.reset_peak()  # O(1) - peak drops to current
assert tracemalloc.get_traced_memory()[1] < 1_000_000

assert tracemalloc.get_tracemalloc_memory() > 0  # O(1) - the tracer's own tables

tracemalloc.clear_traces()  # O(t + r·f) - tracing continues from zero
assert tracemalloc.is_tracing()

tracemalloc.stop()
assert tracemalloc.get_traced_memory() == (0, 0)
```

## Snapshots

### Taking and Grouping a Snapshot

`take_snapshot()` copies every trace into Python objects, so it is linear in the live blocks, and
it shares one frames tuple among the traces with the same traceback. `statistics()` groups those
traces and sorts the groups, largest first.

```python
import tracemalloc

tracemalloc.start()
blocks = [bytearray(1000) for _ in range(100)]
snapshot = tracemalloc.take_snapshot()  # O(t + u·f)
tracemalloc.stop()

assert snapshot.traceback_limit == 1
assert len(snapshot.traces) >= 100  # O(1)

stats = snapshot.statistics('lineno')  # O(t·f + g log g)
top = stats[0]
assert top.size >= 100_000 and top.count >= 100
assert top.traceback[0].filename == __file__

by_file = snapshot.statistics('filename')
assert len(by_file) <= len(stats)  # one group per file, not per line
```

### Comparing Snapshots to Find Growth

`compare_to()` groups both snapshots and pairs the groups, so it costs the two groupings plus a
sort by how much each group grew.

```python
import tracemalloc

tracemalloc.start()
before = tracemalloc.take_snapshot()  # O(t + u·f)

cache = [bytearray(1000) for _ in range(200)]

after = tracemalloc.take_snapshot()
tracemalloc.stop()

diffs = after.compare_to(before, 'lineno')  # O(t·f + g log g)
growth = diffs[0]
assert growth.size_diff >= 200_000 and growth.count_diff >= 200
assert growth.traceback[0].filename == __file__
assert abs(diffs[0].size_diff) >= abs(diffs[-1].size_diff)
```

### Filtering Traces

A filter tests the most recent frame of each trace, or every frame with `all_frames=True`. The
result is a new snapshot, so filtering costs a pass over the traces and a list of the survivors.

```python
import tracemalloc

tracemalloc.start()
blocks = [bytearray(1000) for _ in range(50)]
snapshot = tracemalloc.take_snapshot()
tracemalloc.stop()

mine = snapshot.filter_traces([tracemalloc.Filter(True, __file__)])  # O(t·p)
assert len(mine.traces) >= 50
assert all(trace.traceback[0].filename == __file__ for trace in mine.traces)

others = snapshot.filter_traces([tracemalloc.Filter(False, __file__)])
assert len(mine.traces) + len(others.traces) == len(snapshot.traces)

# DomainFilter matches the address space, not the frames
python_heap = snapshot.filter_traces([tracemalloc.DomainFilter(True, 0)])
assert len(python_heap.traces) == len(snapshot.traces)
```

### Saving a Snapshot

`dump()` pickles the snapshot. Traces that share a traceback share one frames tuple, and the
pickle writes it once, so the file follows the same O(t + u·f) as the snapshot.

```python
import os
import tempfile
import tracemalloc

tracemalloc.start()
blocks = [bytearray(1000) for _ in range(50)]
snapshot = tracemalloc.take_snapshot()
tracemalloc.stop()

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'snapshot.pickle')
    snapshot.dump(path)  # O(t + u·f)
    loaded = tracemalloc.Snapshot.load(path)  # O(t + u·f)

assert len(loaded.traces) == len(snapshot.traces)
assert loaded.statistics('lineno') == snapshot.statistics('lineno')
```

## Common Patterns

### Checking a Function for Growth

```python
import tracemalloc

retained = []

def leaky():
    retained.append(bytearray(10_000))

tracemalloc.start()
try:
    leaky()  # warm up anything allocated once
    before = tracemalloc.take_snapshot()
    for _ in range(20):
        leaky()
    after = tracemalloc.take_snapshot()
finally:
    tracemalloc.stop()

mine = [tracemalloc.Filter(True, __file__)]
growth = after.filter_traces(mine).compare_to(before.filter_traces(mine), 'lineno')
assert growth[0].size_diff >= 200_000  # twenty 10 KB blocks
assert growth[0].traceback[0].filename == __file__
```

### Formatting a Traceback

```python
import tracemalloc

def build():
    return bytearray(1000)

tracemalloc.start(5)  # store up to 5 frames
block = build()
traceback = tracemalloc.get_object_traceback(block)
tracemalloc.stop()

assert 1 < len(traceback) <= 5
assert traceback[-1].filename == __file__  # the most recent frame is last

lines = traceback.format()  # O(f), plus reading the source through linecache
assert any('bytearray(1000)' in line for line in lines)
assert traceback.format(most_recent_first=True)[0] == lines[-2]
```

## Performance Best Practices

✅ **Do**:

- Take a snapshot before `stop()`; stopping discards every trace
- Keep `nframe` as small as the question allows: snapshots, grouping and dumps all scale with f
- Group by `'lineno'` or `'filename'` first, and reach for `'traceback'` or `cumulative=True`
  only when one line does not explain the growth
- Start tracing at interpreter startup with `-X tracemalloc=N` or `PYTHONTRACEMALLOC=N` to trace
  imports as well

❌ **Avoid**:

- Leaving tracing on in production: every allocation pays O(d) to walk the stack, and every
  distinct traceback stays recorded until `clear_traces()` or `stop()`, even after its blocks are
  freed
- Expecting `nframe=1` to make deep call stacks cheap to trace; it limits what is stored, not
  what is walked
- `cumulative=True` on a large snapshot with a high `nframe` - it visits all t·f frames

## Version Notes

- **Python 3.14+**: Tuple hashes are cached, so `statistics()` and `compare_to()` without
  `cumulative=True` hash each distinct traceback once: O(t + u·f + g log g)
- **All Python 3**: Only allocations made after `start()` are traced

## Related Modules

- **[gc](gc.md)** - Find what still references an object that tracemalloc shows growing
- **[sys](sys.md)** - `sys.getsizeof()` for one object, without tracing every allocation
- **[linecache](linecache.md)** - What `Traceback.format()` reads source lines through
- **[pickle](pickle.md)** - What `Snapshot.dump()` and `Snapshot.load()` use
- **[cProfile](cprofile.md)** - Profile time rather than memory
