# datetime Module Complexity

The `datetime` module provides classes for manipulating dates and times.

## Class Creation and Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `datetime.now()` | O(1) | O(1) | Current date/time |
| `datetime.fromtimestamp(ts)` | O(1) | O(1) | From Unix timestamp |
| `datetime.strptime(s, fmt)` | O(n) | O(1) | Parse string, n = input length; format-dependent |
| `date(year, month, day)` | O(1) | O(1) | Create date |
| `time(hour, min, sec)` | O(1) | O(1) | Create time |
| `timedelta(days, seconds, ...)` | O(1) | O(1) | Create duration |
| `dt1 - dt2` | O(1) | O(1) | Datetime arithmetic |
| `str(dt)` | O(1) | O(1) | Convert to string |
| `dt.strftime(fmt)` | O(n) | O(n) | Format string, n = format length |

## Date Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `date.year`, `date.month`, `date.day` | O(1) | O(1) | Attribute access |
| `date.weekday()` | O(1) | O(1) | Day of week (0-6) |
| `date.isoweekday()` | O(1) | O(1) | Day of week (1-7) |
| `date.isoformat()` | O(1) | O(1) | ISO 8601 string |
| `date.replace(year=...)` | O(1) | O(1) | Return new date |

## Time Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time.hour`, `time.minute`, `time.second` | O(1) | O(1) | Attribute access |
| `time.isoformat()` | O(1) | O(1) | ISO 8601 string |
| `time.replace(hour=...)` | O(1) | O(1) | Return new time |

## Timedelta Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `td.total_seconds()` | O(1) | O(1) | Total seconds |
| `td.days`, `td.seconds`, `td.microseconds` | O(1) | O(1) | Attributes |
| `td1 + td2` | O(1) | O(1) | Add durations |
| `td1 - td2` | O(1) | O(1) | Subtract durations |
| `td * n` | O(1) | O(1) | Multiply duration |

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

# Parse string - O(n) where n = length of format string
dt = datetime.strptime("2024-01-15", "%Y-%m-%d")

# Format as string - O(n)
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
from datetime import datetime

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

```python
from datetime import datetime
import time

# Simple format - faster - O(n)
start = time.time()
for _ in range(10000):
    datetime.strptime("2024-01-15", "%Y-%m-%d")
simple_time = time.time() - start

# Complex format - slower - O(n)
start = time.time()
for _ in range(10000):
    datetime.strptime("Monday, January 15, 2024 at 3:30:45 PM", "%A, %B %d, %Y at %I:%M:%S %p")
complex_time = time.time() - start
```

### Caching Parsed Dates

```python
from datetime import datetime

# Bad: parse each time - O(n) per parse
dates = []
for date_str in large_list:
    dates.append(datetime.strptime(date_str, "%Y-%m-%d"))

# Better: cache format if reusing
pattern = "%Y-%m-%d"
dates = [datetime.strptime(d, pattern) for d in large_list]
# Still O(n*m) total but pattern is consistent
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

# Add days - works fine
new_dt = dt + timedelta(days=1)

# For month arithmetic, use dateutil.relativedelta
from dateutil.relativedelta import relativedelta
new_dt = dt + relativedelta(months=1)  # 2024-02-29
```

## Version Notes

- **Python 3.2+**: timezone-aware datetimes recommended
- **Python 3.6+**: Better timezone support
- **Python 3.11+**: New zoneinfo module for IANA timezones
- **Python 3.12+**: Some deprecations in favor of zoneinfo

## Related Modules

- **[time](time.md)** - Lower-level time functions
- **[zoneinfo](zoneinfo.md)** - IANA timezone database (Python 3.9+)
- **[dateutil](dateutil.md)** - Extended datetime utilities (external)
- **[calendar](calendar.md)** - Calendar functions

## Best Practices

✅ **Do**:
- Use timezone-aware datetimes for storage/transmission
- Use UTC internally, convert to local for display
- Use `datetime.now(timezone.utc)` not `datetime.utcnow()`
- Cache parsed datetime formats in tight loops
- Use `isoformat()` for serialization

❌ **Avoid**:
- Mixing timezone-aware and naive datetimes
- String parsing in tight loops without caching
- Using `datetime.utcnow()` (deprecated)
- Manual timezone arithmetic (use libraries)
- Assuming time is monotonic (use `time.monotonic()`)
