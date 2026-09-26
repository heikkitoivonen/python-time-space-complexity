# time Module Complexity

The `time` module reads the system's clocks, sleeps, and converts between timestamps,
`struct_time` tuples and strings. It is a thin layer over the C library: a clock read is one
call into the operating system, and a conversion fills or reads one fixed-size record.

`f` is the characters in a format string and `n` is the characters in the string `strptime()`
parses. Every other operation takes a fixed-size input - a clock id, a timestamp, or a
`struct_time` - and is O(1). The C library's own work is priced O(1) too: reading a clock, and
consulting the timezone rules that `localtime()`, `mktime()` and `tzset()` rely on.

## Complexity Reference

### Clocks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.time()`, `time.time_ns()` | O(1) | O(1) | Seconds since the epoch; the system clock can be set back, so two readings can go backwards. The `_ns` form returns an int and keeps the nanoseconds a float rounds away |
| `time.monotonic()`, `time.monotonic_ns()` | O(1) | O(1) | Never goes backwards; the clock for timeouts and durations |
| `time.perf_counter()`, `time.perf_counter_ns()` | O(1) | O(1) | The highest-resolution clock for short durations; counts time spent in `sleep()` |
| `time.process_time()`, `time.process_time_ns()` | O(1) | O(1) | CPU time of the whole process; time spent in `sleep()` does not count |
| `time.thread_time()`, `time.thread_time_ns()` | O(1) | O(1) | CPU time of the calling thread only; availability is platform-dependent |
| `time.get_clock_info(name)` | O(1) | O(1) | A namespace of `implementation`, `monotonic`, `adjustable` and `resolution` |

### POSIX clocks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.clock_gettime(clk_id)`, `time.clock_gettime_ns(clk_id)` | O(1) | O(1) | Unix only; reads the clock a `CLOCK_*` id names |
| `time.clock_settime(clk_id, t)`, `time.clock_settime_ns(clk_id, t)` | O(1) | O(1) | Unix only, and needs privileges |
| `time.clock_getres(clk_id)` | O(1) | O(1) | Unix only; the clock's resolution, not the cost of reading it |
| `time.pthread_getcpuclockid(thread_id)` | O(1) | O(1) | Unix only; the id of a thread's CPU-time clock, for `clock_gettime()` |
| `time.CLOCK_REALTIME`, `time.CLOCK_MONOTONIC`, `time.CLOCK_MONOTONIC_RAW`, `time.CLOCK_BOOTTIME`, `time.CLOCK_PROCESS_CPUTIME_ID`, `time.CLOCK_THREAD_CPUTIME_ID`, `time.CLOCK_TAI`, `time.CLOCK_HIGHRES`, `time.CLOCK_PROF`, `time.CLOCK_UPTIME`, `time.CLOCK_UPTIME_RAW` | O(1) | O(1) | Integer clock ids; which of them exist is platform-dependent |
| `time.CLOCK_MONOTONIC_RAW_APPROX`, `time.CLOCK_UPTIME_RAW_APPROX` | O(1) | O(1) | Python 3.13+; platform-dependent integer clock ids |

### Sleeping

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.sleep(secs)` | O(1) | O(1) | Blocks the calling thread for at least `secs`; the wait costs no CPU time, whatever `secs` is |

### Conversions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.gmtime([secs])`, `time.localtime([secs])` | O(1) | O(1) | A timestamp to a `struct_time`, in UTC or local time; the current time when `secs` is omitted |
| `time.mktime(t)` | O(1) | O(1) | A local `struct_time` back to a timestamp |
| `time.asctime([t])`, `time.ctime([secs])` | O(1) | O(1) | 24 characters for any four-digit year |
| `time.strftime(format[, t])` | O(f) | O(f) | Output grows with the format: each directive expands to a bounded number of characters |
| `time.strptime(string[, format])` | O(n) | O(n) | Each format is compiled once, O(f), and cached; the cache is small and is cleared wholesale when full |

### struct_time

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.struct_time(sequence)` | O(1) | O(1) | Nine to eleven items; the tenth and eleventh fill `tm_zone` and `tm_gmtoff` |
| `struct_time.tm_year`, `struct_time.tm_mon`, `struct_time.tm_mday`, `struct_time.tm_hour`, `struct_time.tm_min`, `struct_time.tm_sec`, `struct_time.tm_wday`, `struct_time.tm_yday`, `struct_time.tm_isdst` | O(1) | O(1) | The nine fields that indexing and unpacking reach |
| `struct_time.tm_zone`, `struct_time.tm_gmtoff` | O(1) | O(1) | Attributes only: not part of the nine-item tuple |

### Timezone attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.timezone`, `time.altzone`, `time.daylight`, `time.tzname` | O(1) | O(1) | Module attributes, set at import and again by `tzset()` |
| `time.tzset()` | O(1) | O(1) | Unix only; re-reads `TZ` and refreshes the four attributes above |

## Reading Clocks

### Choosing a Clock

`time()` follows the system clock, which can be set back, so a duration measured with it can
come out negative. Measure durations with `monotonic()` or `perf_counter()`, and use the `_ns`
forms where the nanoseconds matter: a float timestamp near the present cannot hold them.

```python
import math
import time

now = time.time()  # O(1)
now_ns = time.time_ns()  # O(1)
assert isinstance(now_ns, int)
assert math.ulp(now) > 1e-9  # a float this large cannot resolve one nanosecond

start = time.monotonic()  # O(1)
elapsed = time.monotonic() - start
assert elapsed >= 0

info = time.get_clock_info("monotonic")  # O(1)
assert info.monotonic is True
assert info.resolution > 0
```

### CPU Time

`process_time()` and `thread_time()` count CPU time, so a thread that is blocked adds nothing
to them. `perf_counter()` counts wall-clock time, sleep included.

```python
import time

cpu_before = time.process_time()  # O(1)
wall_before = time.perf_counter()  # O(1)
time.sleep(0.05)  # O(1) - the thread waits, it does not work
cpu_spent = time.process_time() - cpu_before
wall_spent = time.perf_counter() - wall_before

assert wall_spent >= 0.05
assert cpu_spent < wall_spent
```

### POSIX Clocks

On Unix, `clock_gettime()` reads a clock by id. Which ids exist depends on the platform, so
check before reaching for one.

```python
import time

if hasattr(time, "clock_gettime") and hasattr(time, "CLOCK_MONOTONIC"):
    seconds = time.clock_gettime(time.CLOCK_MONOTONIC)  # O(1)
    nanoseconds = time.clock_gettime_ns(time.CLOCK_MONOTONIC)  # O(1)
    assert isinstance(seconds, float) and isinstance(nanoseconds, int)
    assert 0 < time.clock_getres(time.CLOCK_MONOTONIC) <= 1  # O(1)
```

## Converting Timestamps

A `struct_time` has a fixed shape whatever the timestamp, so converting either way is O(1).
Its nine fields are reachable by index and by name; `tm_zone` and `tm_gmtoff` only by name.

```python
import time

utc = time.gmtime(0)  # O(1)
assert (utc.tm_year, utc.tm_mon, utc.tm_mday) == (1970, 1, 1)
assert utc[0] == utc.tm_year  # O(1) either way
assert len(utc) == 9
assert utc.tm_gmtoff == 0 and utc.tm_zone not in utc  # O(1) - by name only

local = time.localtime(1_000_000_000)  # O(1)
assert time.mktime(local) == 1_000_000_000  # O(1)

rebuilt = time.struct_time(tuple(utc))  # O(1)
assert rebuilt == utc
```

## Formatting and Parsing

These are the only operations on this page whose cost follows an input: `strftime()` the format
it is given, and `strptime()` the string it parses. `asctime()` and `ctime()` have a fixed
layout instead.

```python
import time

moment = time.gmtime(0)

stamp = time.strftime("%Y-%m-%d %H:%M:%S", moment)  # O(f)
assert stamp == "1970-01-01 00:00:00"

parsed = time.strptime("2026-01-30 12:34:56", "%Y-%m-%d %H:%M:%S")  # O(n)
assert (parsed.tm_year, parsed.tm_hour) == (2026, 12)

assert time.asctime(moment) == "Thu Jan  1 00:00:00 1970"  # O(1)
```

### The strptime Format Cache

`strptime()` compiles its format to a regular expression and caches it, so a format reused in a
loop is compiled once and each later call is only the O(n) match. The cache holds a few formats
and is emptied all at once when it is full, so a program rotating through more formats than
that compiles on almost every call. `datetime.strptime()` shares the same cache.

```python
import time

lines = ["2026-01-30 08:00", "2026-01-30 09:15", "2026-01-31 17:45"]
fmt = "%Y-%m-%d %H:%M"

hours = [time.strptime(line, fmt).tm_hour for line in lines]  # O(f) once, then O(n) each
assert hours == [8, 9, 17]

try:
    time.strptime("2026-01-30", fmt)
except ValueError as error:
    assert "does not match format" in str(error)
else:
    raise AssertionError("a string missing its time parsed")
```

## Timezone Attributes

```python
import time

offset = time.timezone  # O(1) - seconds west of UTC, outside DST
dst_offset = time.altzone  # O(1) - the same with DST in effect
has_dst = time.daylight  # O(1)
standard, summer = time.tzname  # O(1) - a two-string tuple
assert isinstance(offset, int) and isinstance(dst_offset, int)

if hasattr(time, "tzset"):
    time.tzset()  # O(1) - re-reads TZ and refreshes the four above
    assert len(time.tzname) == 2
```

## Common Patterns

### Timing a Block of Code

```python
import time

start = time.perf_counter_ns()  # O(1)
total = sum(range(100_000))
elapsed_ns = time.perf_counter_ns() - start  # O(1)

assert total == 4_999_950_000
assert elapsed_ns >= 0
```

### Waiting With a Deadline

```python
import time

deadline = time.monotonic() + 0.05  # O(1) - unaffected if the system clock is set
polls = 0
while time.monotonic() < deadline:
    polls += 1
    time.sleep(0.01)  # O(1) CPU per wait

assert polls >= 1
assert time.monotonic() >= deadline
```

## Performance Best Practices

✅ **Do**:

- Measure durations and deadlines with `monotonic()` or `perf_counter()`, which never go backwards
- Use `process_time()` or `thread_time()` to separate CPU work from time spent waiting
- Reuse one `strptime()` format across a loop, so it is compiled once
- Use the `_ns` clock forms when nanoseconds matter

❌ **Avoid**:

- Timing with `time()` - a clock adjustment can make the result wrong or negative
- Rotating through many `strptime()` formats - past the cache's size, most calls recompile
- A busy loop polling a clock where `sleep()` would wait without spending CPU

## Version Notes

- **Python 3.13+**: `strptime()` issues a `DeprecationWarning` for a format with a day of the
  month but no year
- **All Python 3**: `time()` follows the system clock and can go backwards when it is set

## Related Modules

- **[datetime](datetime.md)** - date and time objects with arithmetic; `datetime.strptime()` shares the format cache
- **[zoneinfo](zoneinfo.md)** - IANA timezones for `datetime`, beyond the process-wide `TZ`
- **[calendar](calendar.md)** - `calendar.timegm()`, the inverse of `time.gmtime()`
- **[timeit](timeit.md)** - repeated timing of small snippets, built on `perf_counter()`
