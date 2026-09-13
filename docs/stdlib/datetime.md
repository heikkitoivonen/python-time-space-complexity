# datetime Module Complexity

The `datetime` module provides classes for manipulating dates and times.

Every operation on a `datetime`, `date`, `time` or `timedelta` *object* is
constant time: they are fixed-size records of small integers, so arithmetic,
comparison, attribute access and replacement have nothing to scale with. Only
the conversions to and from strings do. Throughout, `n` is the length of a
string being parsed or produced and `f` the length of a format string.

## Class Creation and Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `datetime.now()` | O(1) | O(1) | Current date/time |
| `datetime.fromtimestamp(ts)` | O(1) | O(1) | From Unix timestamp |
| `datetime.strptime(s, fmt)` | O(n + f) | O(f) | Compiles `fmt` to a regex and caches it; the first call in a process also imports `_strptime` |
| `date(year, month, day)` | O(1) | O(1) | Create date |
| `time(hour, min, sec)` | O(1) | O(1) | Create time |
| `timedelta(days, seconds, ...)` | O(1) | O(1) | Create duration |
| `dt1 - dt2` | O(1) | O(1) | Datetime arithmetic |
| `str(dt)` | O(1) | O(1) | Convert to string |
| `dt.strftime(fmt)` | O(f) | O(f) | One pass over the format |

## Date Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `date.year`, `date.month`, `date.day` | O(1) | O(1) | Attribute access |
| `date.today()` | O(1) | O(1) | Current local date |
| `date.fromisoformat(s)` | O(n) | O(1) | Parsed in C, with no format to compile; the cheaper choice when the input is ISO 8601 |
| `date.fromtimestamp(ts)` | O(1) | O(1) | From Unix timestamp |
| `date.fromordinal(n)` | O(1) | O(1) | From proleptic Gregorian ordinal |
| `date.fromisocalendar(y, w, d)` | O(1) | O(1) | From ISO year, week, day |
| `date.weekday()` | O(1) | O(1) | Day of week (0=Mon, 6=Sun) |
| `date.isoweekday()` | O(1) | O(1) | Day of week (1=Mon, 7=Sun) |
| `date.isocalendar()` | O(1) | O(1) | Returns (year, week, weekday) |
| `date.isoformat()` | O(1) | O(1) | ISO 8601 string |
| `date.strftime(fmt)` | O(f) | O(f) | One pass over the format |
| `date.ctime()` | O(1) | O(1) | C-style string |
| `date.timetuple()` | O(1) | O(1) | time.struct_time |
| `date.toordinal()` | O(1) | O(1) | Proleptic Gregorian ordinal |
| `date.replace(year=...)` | O(1) | O(1) | Return new date |
| `date.__format__(fmt)` | O(f) | O(f) | `strftime` for a non-empty spec, `isoformat()` for an empty one |

## Datetime Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `datetime.combine(date, time)` | O(1) | O(1) | Combine date and time objects |
| `datetime.fromisoformat(s)` | O(n) | O(1) | Parsed in C, with no format to compile; far cheaper than `strptime` for ISO 8601 input |
| `datetime.date()` | O(1) | O(1) | Extract date part |
| `datetime.time()` | O(1) | O(1) | Extract time part (no tzinfo) |
| `datetime.timetz()` | O(1) | O(1) | Extract time part (with tzinfo) |
| `datetime.timestamp()` | O(1) | O(1) | Return POSIX timestamp |
| `datetime.utctimetuple()` | O(1) | O(1) | UTC time.struct_time |
| `datetime.dst()` | O(1) | O(1) | Daylight saving offset |
| `datetime.tzname()` | O(1) | O(1) | Timezone name string |
| `datetime.utcoffset()` | O(1) | O(1) | UTC offset as timedelta |
| `datetime.astimezone()` | O(1) | O(1) | Convert between timezones |
| `datetime.now(tz)` | O(1) | O(1) | Current datetime in tz |
| `datetime.utcnow()` | O(1) | O(1) | Current UTC datetime |
| `datetime.utcfromtimestamp(ts)` | O(1) | O(1) | From timestamp (UTC) |
| `datetime.fromtimestamp(ts, tz)` | O(1) | O(1) | From timestamp with tz |
| `datetime.replace(...)` | O(1) | O(1) | New datetime with fields replaced |
| `datetime.timetuple()` | O(1) | O(1) | time.struct_time |
| `datetime.ctime()` | O(1) | O(1) | C-style string |
| `datetime.isoformat()` | O(1) | O(1) | ISO 8601 string |
| `datetime.__format__(fmt)` | O(f) | O(f) | `strftime` for a non-empty spec, `isoformat()` for an empty one |

## Time Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.hour`, `time.minute`, `time.second` | O(1) | O(1) | Attribute access |
| `time.fromisoformat(s)` | O(n) | O(1) | Parsed in C, with no format to compile |
| `time.isoformat()` | O(1) | O(1) | ISO 8601 string |
| `time.strftime(fmt)` | O(f) | O(f) | One pass over the format |
| `time.replace(hour=...)` | O(1) | O(1) | Return new time |
| `time.dst()` | O(1) | O(1) | Daylight saving offset |
| `time.tzname()` | O(1) | O(1) | Timezone name string |
| `time.utcoffset()` | O(1) | O(1) | UTC offset as timedelta |
| `time.fold` | O(1) | O(1) | Attribute access |

## Timedelta Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `td.total_seconds()` | O(1) | O(1) | Total seconds |
| `td.days`, `td.seconds`, `td.microseconds` | O(1) | O(1) | Attributes |
| `td1 + td2` | O(1) | O(1) | Add durations |
| `td1 - td2` | O(1) | O(1) | Subtract durations |
| `td * n` | O(1) | O(1) | Multiply duration |
| `td / n` | O(1) | O(1) | Divide duration |
| `td // n` | O(1) | O(1) | Floor divide duration |
| `abs(td)` | O(1) | O(1) | Absolute duration |
| `-td` | O(1) | O(1) | Negate duration |

## Timezone Utilities

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `timezone(offset)` | O(1) | O(1) | Fixed offset tzinfo |
| `timezone.utc` | O(1) | O(1) | UTC tzinfo singleton |
| `UTC` | O(1) | O(1) | UTC tzinfo alias |
| `tzinfo` | O(1) | O(1) | Abstract base for tzinfo |

## Constants

| Name | Time | Space | Notes |
|------|------|-------|-------|
| `MINYEAR` / `MAXYEAR` | O(1) | O(1) | Supported year bounds |
| `datetime_CAPI` | O(1) | O(1) | C API capsule |

## Common Operations

### Getting Current Time

```python
from datetime import datetime, date, time

# Get current datetime - O(1)
now = datetime.now()

# Get current date - O(1)
today = date.today()

# Component access - O(1)
year = now.year
month = now.month
day = now.day
hour = now.hour
minute = now.minute
second = now.second
```

### Creating Datetime Objects

```python
from datetime import datetime, date, timedelta

# Create date - O(1)
d = date(2024, 1, 15)

# Create datetime - O(1)
dt = datetime(2024, 1, 15, 12, 30, 45)

# Create timedelta - O(1)
delta = timedelta(days=5, hours=3, minutes=30)
```

### Parsing and Formatting

```python
from datetime import datetime

# Parse string - O(n + f) for input length n and format length f
dt = datetime.strptime("2024-01-15 12:30:45", "%Y-%m-%d %H:%M:%S")

# Same result with no format to compile - O(n)
dt = datetime.fromisoformat("2024-01-15 12:30:45")

# Format as string - O(f)
formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
# "2024-01-15 12:30:45"

# ISO format - O(1)
iso_str = dt.isoformat()
# "2024-01-15T12:30:45"
```

### Arithmetic Operations

```python
from datetime import datetime, timedelta

dt1 = datetime(2024, 1, 15)
dt2 = datetime(2024, 1, 20)

# Difference - O(1)
delta = dt2 - dt1  # 5 days

# Add time - O(1)
new_dt = dt1 + timedelta(days=5)

# Subtract time - O(1)
new_dt = dt1 - timedelta(hours=2)

# Get total seconds - O(1)
total_secs = delta.total_seconds()
```

### Comparisons

```python
from datetime import datetime, timedelta

dt1 = datetime(2024, 1, 15)
dt2 = datetime(2024, 1, 20)

# Comparisons - O(1)
if dt1 < dt2:
    print("dt1 is earlier")

if dt1 == dt2:
    print("Same datetime")

# Sort datetimes - O(n log n)
dates = [dt2, dt1, dt1 + timedelta(days=1)]
sorted_dates = sorted(dates)  # O(n log n)
```

## Timezone Class

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `timezone(offset)` | O(1) | O(1) | Create fixed offset timezone |
| `timezone.utc` | O(1) | O(1) | UTC timezone constant |
| `tz.utcoffset(dt)` | O(1) | O(1) | Return offset from UTC |
| `tz.tzname(dt)` | O(1) | O(1) | Return timezone name |
| `tz.dst(dt)` | O(1) | O(1) | Return DST offset (always None for timezone) |
| `tz.fromutc(dt)` | O(1) | O(1) | Convert UTC datetime to this timezone |

## Timezone Operations

```python
from datetime import datetime, timezone, timedelta

# UTC timezone - O(1)
utc = timezone.utc

# Create datetime with UTC - O(1)
dt_utc = datetime(2024, 1, 15, tzinfo=utc)

# Custom timezone offset - O(1)
tz = timezone(timedelta(hours=5))
dt_local = datetime(2024, 1, 15, tzinfo=tz)

# Convert between timezones - O(1)
dt_in_tz = dt_utc.astimezone(tz)

# Replace timezone - O(1)
dt_new_tz = dt_utc.replace(tzinfo=tz)
```

## Performance Notes

### Parsing Performance

`strptime` does two things the bound does not show. The first call in a
process imports `_strptime`, which is where most of that call's time goes; and
each format is compiled to a regular expression that is then cached, so a
format costs far more the first time it is seen than on any later parse.

```python
from datetime import datetime

# First call in the process: imports _strptime, then compiles the format
dt = datetime.strptime("2024-01-15", "%Y-%m-%d")  # O(n + f), plus the import

# Same format again: the compiled regex is already cached - O(n + f)
dt = datetime.strptime("2024-02-20", "%Y-%m-%d")

# No format at all, and no regex: parsed in C - O(n)
dt = datetime.fromisoformat("2024-02-20")
```

Prefer `fromisoformat()` whenever the input is ISO 8601. It is the cheaper of
the two by a wide margin, and it never builds a regex.

### Caching Parsed Dates

The format cache is cleared as soon as it holds more than five formats.
Parsing one format repeatedly compiles it once; rotating through more than
five pays the rebuild on every parse, so group the work by format rather than
interleaving it.

```python
from datetime import datetime

rows = ["2024-01-15", "2024-02-20", "2024-03-25"]

# One compile, then a cache hit per row - O(n + f) each
dates = [datetime.strptime(row, "%Y-%m-%d") for row in rows]

# Cheaper again where the input allows it - O(n) each, no compile
dates = [datetime.fromisoformat(row) for row in rows]
```

## Special Considerations

### UTC vs Local Time

```python
from datetime import datetime, timezone

# Local time (no timezone info)
local = datetime.now()  # O(1)

# UTC time
utc = datetime.utcnow()  # O(1) - deprecated in 3.12
utc = datetime.now(timezone.utc)  # O(1) - preferred

# Always use timezone-aware datetimes for serialization
```

### Date Arithmetic Limitations

```python
from datetime import datetime, timedelta

dt = datetime(2024, 1, 31)

# Careful with month/year arithmetic
# No direct "add 1 month" operation
# Must handle edge cases

# Add days - works fine, O(1)
new_dt = dt + timedelta(days=1)
```

## Version Notes

- **Python 3.2+**: timezone-aware datetimes recommended
- **Python 3.6+**: Better timezone support
- **Python 3.9+**: `zoneinfo` module added for IANA timezones
- **Python 3.11+**: `fromisoformat()` accepts most of ISO 8601, including a
  trailing `Z` and the basic format; before that it read only what
  `isoformat()` produced
- **Python 3.12+**: `datetime.utcnow()` and `datetime.utcfromtimestamp()` are
  deprecated in favour of the timezone-aware `datetime.now(timezone.utc)` and
  `datetime.fromtimestamp(ts, timezone.utc)`

## Related Modules

- **[time](time.md)** - Lower-level time functions
- **[zoneinfo](zoneinfo.md)** - IANA timezone database
- **[calendar](calendar.md)** - Calendar functions

## Best Practices

✅ **Do**:

- Use timezone-aware datetimes for storage/transmission
- Use UTC internally, convert to local for display
- Use `datetime.now(timezone.utc)` not `datetime.utcnow()`
- Group parsing work by format; prefer `fromisoformat()` for ISO 8601
- Use `isoformat()` for serialization

❌ **Avoid**:

- Mixing timezone-aware and naive datetimes
- Interleaving more than five parse formats in a tight loop
- Using `datetime.utcnow()` (deprecated)
- Manual timezone arithmetic (use libraries)
- Assuming time is monotonic (use `time.monotonic()`)
