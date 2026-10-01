# resource Module Complexity

The `resource` module reads and sets per-process resource limits and reports resource usage. It
is Unix only: it does not exist on Windows or WASI, and which limits and counters it offers
depends on the platform. The module keeps no state of its own: every call reads the current
value.

Almost everything here is constant time. The one size variable is `t`, the threads in the calling
process: on Linux, `getrusage(RUSAGE_SELF)` sums the counters of every thread.

## Complexity Reference

### Resource usage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `resource.getrusage(resource.RUSAGE_SELF)` | O(t) | O(1) | The whole process; Linux sums the counters of all t threads on every call |
| `resource.getrusage(resource.RUSAGE_THREAD)` | O(1) | O(1) | The calling thread only, where the platform defines it (Linux does, macOS does not) |
| `resource.getrusage(resource.RUSAGE_CHILDREN)` | O(1) | O(1) | Child processes that have exited and been waited for |
| `resource.RUSAGE_SELF`, `resource.RUSAGE_CHILDREN`, `resource.RUSAGE_BOTH`, `resource.RUSAGE_THREAD` | O(1) | O(1) | Integer `who` values; `RUSAGE_BOTH` and `RUSAGE_THREAD` exist only where the platform defines them |

### struct_rusage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `resource.struct_rusage` | O(1) | O(1) | What `getrusage()` returns: a 16-item tuple whose items are also attributes |
| `struct_rusage.ru_utime`, `struct_rusage.ru_stime` | O(1) | O(1) | User and system CPU time, as float seconds |
| `struct_rusage.ru_maxrss` | O(1) | O(1) | Peak resident set size, which never falls: kilobytes on Linux, bytes on macOS |
| `struct_rusage.ru_ixrss`, `struct_rusage.ru_idrss`, `struct_rusage.ru_isrss`, `struct_rusage.ru_minflt`, `struct_rusage.ru_majflt`, `struct_rusage.ru_nswap`, `struct_rusage.ru_inblock`, `struct_rusage.ru_oublock`, `struct_rusage.ru_msgsnd`, `struct_rusage.ru_msgrcv`, `struct_rusage.ru_nsignals`, `struct_rusage.ru_nvcsw`, `struct_rusage.ru_nivcsw` | O(1) | O(1) | Integer counters; Linux always reports `ru_ixrss`, `ru_idrss`, `ru_isrss`, `ru_nswap`, `ru_msgsnd`, `ru_msgrcv` and `ru_nsignals` as 0 |

### Resource limits

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `resource.getrlimit(resource)` | O(1) | O(1) | Returns `(soft, hard)`; an unknown resource raises `ValueError` |
| `resource.setrlimit(resource, limits)` | O(1) | O(1) | `limits` is `(soft, hard)`; a soft limit above the hard one, or raising the hard limit without privilege, raises `ValueError` |
| `resource.prlimit(pid, resource[, limits])` | O(1) | O(1) | Linux only; reads, or sets and returns the previous, limits of process `pid` (0 is the caller) |
| `resource.RLIM_INFINITY` | O(1) | O(1) | The value of an unlimited soft or hard limit |
| `resource.RLIMIT_CPU`, `resource.RLIMIT_FSIZE`, `resource.RLIMIT_NOFILE`, `resource.RLIMIT_AS` and the other `RLIMIT_*` names | O(1) | O(1) | Integer resource numbers; a name the platform lacks is not an attribute |

### Page size and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `resource.getpagesize()` | O(1) | O(1) | Bytes in one system page |
| `resource.error` | O(1) | O(1) | A deprecated alias of `OSError` |

## Measuring Usage

### Snapshots

`getrusage()` returns a new snapshot each time, so measuring a piece of work is two calls and a
subtraction. The CPU times are cumulative; `ru_maxrss` is a high-water mark, not current usage.

```python
import resource

before = resource.getrusage(resource.RUSAGE_SELF)  # O(t)
total = sum(i * i for i in range(200_000))
after = resource.getrusage(resource.RUSAGE_SELF)  # O(t)

cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
assert cpu >= 0
assert after.ru_maxrss >= before.ru_maxrss  # a peak, so it never falls

# The same snapshot is also a 16-item tuple
assert len(after) == 16 and after[0] == after.ru_utime
```

### Threads

On Linux, `RUSAGE_SELF` adds up the counters of every thread in the process on each call, so in a
process with many threads its cost grows with the thread count. `RUSAGE_THREAD` reads only the
calling thread and costs the same however many threads there are.

```python
import resource
import threading

stop = threading.Event()
idle = [threading.Thread(target=stop.wait) for _ in range(50)]
for thread in idle:
    thread.start()

whole = resource.getrusage(resource.RUSAGE_SELF)  # O(t) - t is 51 here
if hasattr(resource, "RUSAGE_THREAD"):  # Linux, not macOS
    mine = resource.getrusage(resource.RUSAGE_THREAD)  # O(1)
    assert isinstance(mine, resource.struct_rusage)

stop.set()
for thread in idle:
    thread.join()
```

### Child Processes

`RUSAGE_CHILDREN` counts only children that have exited and been waited for. `subprocess.run()`
waits, so its child's CPU time is in the next snapshot.

```python
import resource
import subprocess
import sys

def children_cpu():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)  # O(1)
    return usage.ru_utime + usage.ru_stime

before = children_cpu()
subprocess.run([sys.executable, "-c", "sum(range(10**6))"], check=True)
assert children_cpu() > before
```

## Limits

### Soft and Hard Limits

Every resource has a soft limit, which the kernel enforces, and a hard limit, which caps the soft
one. A process may move its soft limit anywhere up to the hard limit and back, so lowering the soft
limit is the reversible way to bound something. Lowering the hard limit cannot be undone without
privilege.

```python
import errno
import resource
import tempfile

soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)  # O(1)

# Python ignores SIGXFSZ, so a write past the limit raises EFBIG instead of killing the process
resource.setrlimit(resource.RLIMIT_FSIZE, (1024, hard))  # O(1) - the soft limit only
try:
    with tempfile.TemporaryFile(buffering=0) as handle:
        handle.write(b"x" * 1024)
        try:
            handle.write(b"x")
        except OSError as error:
            assert error.errno == errno.EFBIG
        else:
            raise AssertionError("a write past the limit succeeded")
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))  # back up to the old soft limit

assert resource.getrlimit(resource.RLIMIT_FSIZE) == (soft, hard)

# A soft limit above the hard limit is rejected
try:
    resource.setrlimit(resource.RLIMIT_FSIZE, (2, 1))
except ValueError as error:
    assert "exceeds maximum" in str(error)
else:
    raise AssertionError("a soft limit above the hard limit was accepted")
```

### Another Process's Limits

On Linux, `prlimit()` reads or sets the limits of another process you own; setting returns the
limits it replaced.

```python
import resource
import subprocess
import sys

child = subprocess.Popen(
    [sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE
)
try:
    soft, hard = resource.prlimit(child.pid, resource.RLIMIT_NOFILE)  # O(1)
    assert (soft, hard) == resource.getrlimit(resource.RLIMIT_NOFILE)  # inherited

    lower = min(soft, 64)
    previous = resource.prlimit(child.pid, resource.RLIMIT_NOFILE, (lower, hard))  # O(1)
    assert previous == (soft, hard)
    assert resource.prlimit(child.pid, resource.RLIMIT_NOFILE) == (lower, hard)
finally:
    child.stdin.close()
    child.wait()
```

## Performance Best Practices

✅ **Do**:

- Take a snapshot before and after the work and subtract, rather than polling in a loop
- Use `RUSAGE_THREAD` on Linux when one thread's usage is enough; it is O(1) where `RUSAGE_SELF` is O(t)
- Lower a soft limit to bound a resource, and restore it from what `getrlimit()` returned

❌ **Avoid**:

- Calling `getrusage(RUSAGE_SELF)` in a hot loop of a process with many threads
- Lowering a hard limit unless the process should never get it back
- Comparing `ru_maxrss` between Linux and macOS without converting kilobytes and bytes

## Version Notes

- **All Python 3**: Unix only; the module does not exist on Windows or WASI
- **All Python 3**: `prlimit()` is Linux only

## Related Modules

- **[time](time.md)** - `process_time()` and `thread_time()`, CPU time that Windows reports too
- **[os](os.md)** - `os.times()` for process and child CPU times
- **[signal](signal.md)** - `SIGXCPU` and `SIGXFSZ`, sent when the CPU-time or file-size soft limit is exceeded
- **[subprocess](subprocess.md)** - running the children `RUSAGE_CHILDREN` reports on
- **[tracemalloc](tracemalloc.md)** - Python allocations by source line; `ru_maxrss` is the whole process's peak
