# time Module Complexity

The `time` module provides time-related functions for wall-clock time, monotonic clocks, sleep,
and conversions between timestamps and struct_time.

Almost every operation here is constant: a clock read is one syscall or vDSO read, and a
`struct_time` has nine fields whatever the timestamp. Only `strftime()` and `strptime()` have an
input whose length can grow.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.time()`, `time.time_ns()` | O(1) | O(1) | Wall-clock seconds since the epoch; the `_ns` form returns an int of nanoseconds and keeps precision a float loses |
| `time.monotonic()`, `time.monotonic_ns()` | O(1) | O(1) | Never goes backwards, and is unaffected by changes to the system clock |
| `time.perf_counter()`, `time.perf_counter_ns()` | O(1) | O(1) | Highest resolution clock the platform offers |
| `time.process_time()`, `time.process_time_ns()` | O(1) | O(1) | CPU time of the process; time spent blocked in `sleep()` does not count |
| `time.thread_time()`, `time.thread_time_ns()` | O(1) | O(1) | CPU time of the calling thread; availability is platform-dependent |
| `time.clock_gettime(clk_id)`, `time.clock_gettime_ns(clk_id)` | O(1) | O(1) | Unix only; reads a named POSIX clock, and where it exists the named readers above are wrappers over it |
| `time.clock_settime(clk_id, t)`, `time.clock_settime_ns(clk_id, t)` | O(1) | O(1) | Unix only, and needs privileges |
| `time.clock_getres(clk_id)` | O(1) | O(1) | Unix only; the clock's tick, which is not the cost of reading it |
| `time.get_clock_info(name)` | O(1) | O(1) | Builds a four-field namespace |
| `time.pthread_getcpuclockid(thread_id)` | O(1) | O(1) | Unix only |
| `time.sleep(secs)` | O(1) | O(1) | Blocks for at least `secs`; the waiting is not work, and the call costs the same whatever `secs` is |
| `time.gmtime(secs)`, `time.localtime(secs)` | O(1) | O(1) | Timestamp to a nine-field `struct_time` |
| `time.mktime(t)` | O(1) | O(1) | A local `struct_time` back to a timestamp |
| `time.asctime(t)`, `time.ctime(secs)` | O(1) | O(1) | Fixed-width apart from the year field: 24 characters for any four-digit year |
| `time.strftime(format, t)` | O(n) | O(n) | n = output length |
| `time.strptime(string, format)` | O(n) | O(n) | n = input length; the format is compiled to a regular expression once and cached |
| `time.struct_time(seq)` | O(1) | O(1) | Nine fixed fields; indexing and attribute access are O(1) |
| `time.tzset()` | O(1) | O(1) | Unix only; re-reads `TZ` and refreshes the four attributes below |
| `time.timezone`, `time.altzone`, `time.daylight`, `time.tzname` | O(1) | O(1) | Module attributes, set at import and again by `tzset()` |
| `time.CLOCK_REALTIME`, `time.CLOCK_MONOTONIC`, `time.CLOCK_MONOTONIC_RAW`, `time.CLOCK_BOOTTIME`, `time.CLOCK_PROCESS_CPUTIME_ID`, `time.CLOCK_THREAD_CPUTIME_ID`, `time.CLOCK_TAI`, `time.CLOCK_HIGHRES`, `time.CLOCK_PROF`, `time.CLOCK_UPTIME`, `time.CLOCK_UPTIME_RAW` | O(1) | O(1) | Integer clock ids for `clock_gettime()`; which of them exist is platform-dependent |
| `time.CLOCK_MONOTONIC_RAW_APPROX`, `time.CLOCK_UPTIME_RAW_APPROX` | O(1) | O(1) | Python 3.13+; platform-dependent integer clock ids for `clock_gettime()` |

## Getting Current Time

```python
import time

# Wall-clock time (seconds since epoch)
now = time.time()  # O(1)

# The same clock without the float's rounding
now_ns = time.time_ns()  # O(1)

# Monotonic clock for measuring durations
start = time.monotonic()  # O(1)
# ... do work ...
elapsed = time.monotonic() - start  # O(1)

# Read a POSIX clock where available
if hasattr(time, "clock_gettime") and hasattr(time, "CLOCK_MONOTONIC"):
    raw = time.clock_gettime(time.CLOCK_MONOTONIC)  # O(1)
info = time.get_clock_info("monotonic")  # O(1)
print(info.monotonic, info.resolution)
```

## Sleeping

```python
import time

# Sleep for at least 0.5 seconds
time.sleep(0.5)  # O(1) time, blocks the thread

# CPU time does not advance while blocked, wall-clock time does
before = time.process_time()  # O(1)
time.sleep(0.1)
spent_on_cpu = time.process_time() - before  # close to zero
```

## Formatting and Parsing

These are the only two operations on this page whose cost follows an input size.

```python
import time

now = time.time()

# Convert to struct_time in UTC or local time
utc = time.gmtime(now)     # O(1)
local = time.localtime(now)  # O(1)

# Format time strings
stamp = time.strftime("%Y-%m-%d %H:%M:%S", local)  # O(n), n = output length

# Parse time strings
parsed = time.strptime("2026-01-30 12:34:56", "%Y-%m-%d %H:%M:%S")  # O(n), n = input length

# Fixed-width formatting does not scale with anything
line = time.asctime(local)  # O(1) - 24 characters for any four-digit year
```

`strptime()` compiles its format string to a regular expression and caches it, so a format reused
in a loop is compiled once. The cache is small and is cleared wholesale rather than one entry at a
time, so a program that rotates through many different formats recompiles more often than one that
settles on a few.

## Converting Between Timestamps and Tuples

```python
import time

local_tuple = time.localtime()  # O(1)
timestamp = time.mktime(local_tuple)  # O(1)

# struct_time is a nine-field named tuple: both access forms are O(1)
year = local_tuple.tm_year  # O(1)
also_year = local_tuple[0]  # O(1)

# Building one directly takes the same nine fields
rebuilt = time.struct_time(tuple(local_tuple))  # O(1)
```

## Timezone Attributes

```python
import time

# Set at import, and refreshed by tzset() where that exists
offset = time.timezone  # O(1) - seconds west of UTC, without DST
dst_offset = time.altzone  # O(1) - the same with DST in effect
has_dst = time.daylight  # O(1)
names = time.tzname  # O(1) - a two-string tuple

if hasattr(time, "tzset"):
    time.tzset()  # O(1) - re-reads TZ and refreshes the four above
```

## Related Documentation

- [datetime Module](datetime.md)
- [timeit Module](timeit.md)
