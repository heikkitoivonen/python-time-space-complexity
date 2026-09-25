# datetime Module Complexity

The `datetime` module provides dates, times, durations and fixed-offset time zones. A `date`,
`datetime`, `time` or `timedelta` is a fixed-size record of small integers with a bounded range
(years 1 to 9999, durations under a billion days), so arithmetic, comparison, hashing, attribute
access and replacement are constant time however far apart two values are.

Only the conversions to and from strings scale. `n` is the characters in a string being parsed and
`f` is the characters in a format string, plus, in `strftime()`, the length of the zone's name for
each `%Z`. The parsing space bounds are for ASCII input that parses: a rejected string can be
echoed in the `ValueError`, which is O(n). The `strptime()` bounds assume a format in which no two
whitespace runs can meet; around a directive that can match nothing, such as `%p` in a locale with
no AM/PM names, rejecting a long run of spaces backtracks, O(n²) where two runs meet.

An aware object that needs its UTC offset calls its `tzinfo` a bounded number of times; the bounds
count each call as O(1), which it is for `timezone`. A [`zoneinfo.ZoneInfo`](zoneinfo.md) prices
its calls on its own page: up to a binary search over its recorded transitions.

## Complexity Reference

### date

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `date(year, month, day)` | O(1) | O(1) | |
| `date.today()` | O(1) | O(1) | Current local date |
| `date.fromtimestamp(timestamp)` | O(1) | O(1) | Local date of a POSIX timestamp |
| `date.fromordinal(ordinal)` | O(1) | O(1) | Day 1 is 0001-01-01 |
| `date.fromisoformat(date_string)` | O(n) | O(1) | Parsed in C with no format to compile |
| `date.fromisocalendar(year, week, day)` | O(1) | O(1) | |
| `date.strptime(date_string, format)` | O(n + f) | O(f) | Python 3.14+; the same parser as `datetime.strptime()` |
| `date.year`, `date.month`, `date.day` | O(1) | O(1) | |
| `date.min`, `date.max`, `date.resolution` | O(1) | O(1) | Class attributes; `resolution` is one day |
| `date.replace(year=..., month=..., day=...)` | O(1) | O(1) | Returns a new date |
| `date1 - date2`, `date + timedelta`, `date - timedelta` | O(1) | O(1) | |
| `date1 < date2`, `date1 == date2`, `hash(date)` | O(1) | O(1) | |
| `date.toordinal()` | O(1) | O(1) | |
| `date.weekday()`, `date.isoweekday()` | O(1) | O(1) | Monday is 0 and 1 respectively |
| `date.isocalendar()` | O(1) | O(1) | A `(year, week, weekday)` named tuple |
| `date.timetuple()` | O(1) | O(1) | A `time.struct_time` |
| `date.isoformat()`, `str(date)` | O(1) | O(1) | Fixed-width output |
| `date.ctime()` | O(1) | O(1) | Fixed-width output |
| `date.strftime(format)` | O(f) | O(f) | One pass over the format; the output is proportional to it |
| `date.__format__(format)` | O(f) | O(f) | `strftime()` for a non-empty spec, `str()` for an empty one |

### datetime

`datetime` is a subclass of `date` and inherits every row above. The rows here are the ones it
adds or answers differently.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `datetime(year, month, day, hour=0, minute=0, second=0, microsecond=0, tzinfo=None, *, fold=0)` | O(1) | O(1) | |
| `datetime.now(tz=None)`, `datetime.today()` | O(1) | O(1) | With `tz`, converts through `tz.fromutc()` |
| `datetime.utcnow()` | O(1) | O(1) | Deprecated since 3.12; returns a naive datetime |
| `datetime.fromtimestamp(timestamp, tz=None)` | O(1) | O(1) | With `tz`, converts through `tz.fromutc()` |
| `datetime.utcfromtimestamp(timestamp)` | O(1) | O(1) | Deprecated since 3.12; returns a naive datetime |
| `datetime.combine(date, time, tzinfo=time.tzinfo)` | O(1) | O(1) | |
| `datetime.fromisoformat(date_string)` | O(n) | O(1) | Parsed in C with no format to compile; cheaper than `strptime()` for ISO 8601 input |
| `datetime.strptime(date_string, format)` | O(n + f) | O(f) | Compiles the format to a regular expression and caches it; the first call in a process also imports `_strptime` |
| `datetime.hour`, `datetime.minute`, `datetime.second`, `datetime.microsecond` | O(1) | O(1) | |
| `datetime.tzinfo`, `datetime.fold` | O(1) | O(1) | |
| `datetime.min`, `datetime.max`, `datetime.resolution` | O(1) | O(1) | Class attributes; `resolution` is one microsecond |
| `datetime.date()`, `datetime.time()`, `datetime.timetz()` | O(1) | O(1) | `time()` drops the `tzinfo`, `timetz()` keeps it |
| `datetime.replace(...)` | O(1) | O(1) | Returns a new datetime; replacing `tzinfo` does not convert |
| `dt1 - dt2`, `dt + timedelta`, `dt - timedelta` | O(1) | O(1) | |
| `dt1 < dt2`, `dt1 == dt2`, `hash(dt)` | O(1) | O(1) | |
| `datetime.astimezone(tz=None)` | O(1) | O(1) | To another zone: calls `self.utcoffset()`, then `tz.fromutc()` |
| `datetime.utcoffset()`, `datetime.dst()`, `datetime.tzname()` | O(1) | O(1) | With a `tzinfo`, one call to its method of the same name; `None` without one |
| `datetime.timestamp()` | O(1) | O(1) | A naive datetime is taken as local time |
| `datetime.timetuple()`, `datetime.utctimetuple()` | O(1) | O(1) | |
| `datetime.isoformat(sep='T', timespec='auto')`, `str(dt)` | O(1) | O(1) | Bounded output: microseconds and a UTC offset add fields |
| `datetime.ctime()` | O(1) | O(1) | Fixed-width output |
| `datetime.strftime(format)` | O(f) | O(f) | One pass over the format; the output is proportional to it |
| `datetime.__format__(format)` | O(f) | O(f) | `strftime()` for a non-empty spec, `str()` for an empty one |

### time

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `time(hour=0, minute=0, second=0, microsecond=0, tzinfo=None, *, fold=0)` | O(1) | O(1) | |
| `time.fromisoformat(time_string)` | O(n) | O(1) | Parsed in C with no format to compile |
| `time.strptime(date_string, format)` | O(n + f) | O(f) | Python 3.14+; the same parser as `datetime.strptime()` |
| `time.hour`, `time.minute`, `time.second`, `time.microsecond` | O(1) | O(1) | |
| `time.tzinfo`, `time.fold` | O(1) | O(1) | |
| `time.min`, `time.max`, `time.resolution` | O(1) | O(1) | Class attributes |
| `time.replace(...)` | O(1) | O(1) | Returns a new time |
| `time1 < time2`, `time1 == time2`, `hash(time)` | O(1) | O(1) | |
| `time.utcoffset()`, `time.dst()`, `time.tzname()` | O(1) | O(1) | With a `tzinfo`, one call to its method, passed `None`; `None` without one |
| `time.isoformat(timespec='auto')`, `str(time)` | O(1) | O(1) | Bounded output: microseconds and a UTC offset add fields |
| `time.strftime(format)` | O(f) | O(f) | One pass over the format |
| `time.__format__(format)` | O(f) | O(f) | `strftime()` for a non-empty spec, `str()` for an empty one |

### timedelta

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `timedelta(days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0)` | O(1) | O(1) | Normalised to days, seconds and microseconds; `OverflowError` beyond the range |
| `timedelta.days`, `timedelta.seconds`, `timedelta.microseconds` | O(1) | O(1) | The three stored fields |
| `timedelta.min`, `timedelta.max`, `timedelta.resolution` | O(1) | O(1) | Class attributes; `max` is just under a billion days |
| `timedelta.total_seconds()` | O(1) | O(1) | |
| `td1 + td2`, `td1 - td2`, `-td`, `+td`, `abs(td)` | O(1) | O(1) | |
| `td * x`, `td / x`, `td // i`, `td1 / td2`, `td1 // td2`, `td1 % td2`, `divmod(td1, td2)` | O(1) | O(1) | `x` may be an int or a float, `i` an int; `td * x` and `td / x` round to the nearest microsecond |
| `td1 < td2`, `td1 == td2`, `hash(td)` | O(1) | O(1) | |
| `str(td)` | O(1) | O(1) | |

### tzinfo and timezone

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tzinfo` | O(1) | O(1) | Abstract base class; a subclass supplies the methods below |
| `tzinfo.utcoffset(dt)`, `tzinfo.dst(dt)`, `tzinfo.tzname(dt)` | O(1) | O(1) | For a subclass, whatever it implements; the base class raises `NotImplementedError` |
| `tzinfo.fromutc(dt)` | O(1) | O(1) | The default calls `dt.utcoffset()` and `dt.dst()` |
| `timezone(offset[, name])` | O(1) | O(1) | A fixed offset, strictly between -24 and +24 hours; `name` must be a string |
| `timezone.utc` | O(1) | O(1) | A singleton; `timezone(timedelta(0))` returns it |
| `timezone.min`, `timezone.max` | O(1) | O(1) | Offsets of -23:59 and +23:59 |
| `timezone.utcoffset(dt)`, `timezone.dst(dt)`, `timezone.tzname(dt)` | O(1) | O(1) | The stored offset, `None`, and the name |
| `timezone.fromutc(dt)` | O(1) | O(1) | Adds the stored offset |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `datetime.MINYEAR`, `datetime.MAXYEAR` | O(1) | O(1) | 1 and 9999 |
| `datetime.UTC` | O(1) | O(1) | Python 3.11+; the same object as `timezone.utc` |
| `datetime.datetime_CAPI` | O(1) | O(1) | Capsule holding the C API for extension modules |

## Parsing Strings

### ISO 8601 or a Format

`fromisoformat()` is a fixed parser written in C. `strptime()` runs in Python: it translates its
format into a regular expression, matches the input with it and converts each captured field, so
for ISO 8601 input `fromisoformat()` is the cheaper of the two. Both are linear in the input.
Where its format has whitespace, `strptime()` accepts a run of any length, and from Python 3.11
`fromisoformat()` accepts any number of fractional-second digits.

```python
from datetime import datetime

text = "2024-01-15T12:30:45"

parsed = datetime.fromisoformat(text)                 # O(n), no format
same = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")   # O(n + f)
assert parsed == same == datetime(2024, 1, 15, 12, 30, 45)

# strptime rejects input its format does not describe
try:
    datetime.strptime(text, "%Y-%m-%d")
except ValueError as error:
    assert "unconverted data remains" in str(error)
else:
    raise AssertionError("trailing input was accepted")
```

### The First strptime Call

The first `strptime()` in a process imports `_strptime`, a one-off cost, and each format is
compiled when it is first used. A run of parses with one format compiles it once and reuses the
result, but only a handful of compiled formats are kept, so parse a batch one format at a time
rather than cycling through many.

```python
from datetime import datetime

rows = ["2024-01-15", "2024-02-20", "2024-03-25"]

# One compile, then O(n + f) per row
parsed = [datetime.strptime(row, "%Y-%m-%d") for row in rows]
assert [d.month for d in parsed] == [1, 2, 3]

# No format and no compile - O(n) per row
assert [datetime.fromisoformat(row) for row in rows] == parsed
```

## Formatting Strings

`isoformat()` and `str()` produce output of bounded length and are O(1). `strftime()` walks its format
once and its output grows with it, so it is O(f); `format()` and f-strings route a non-empty spec
through `strftime()`.

```python
from datetime import datetime

moment = datetime(2024, 1, 15, 12, 30, 45)

assert moment.isoformat() == "2024-01-15T12:30:45"          # O(1)
assert str(moment) == "2024-01-15 12:30:45"                 # O(1)
assert moment.strftime("%d/%m/%Y") == "15/01/2024"          # O(f)
assert f"{moment:%H:%M}" == "12:30"                         # O(f), via strftime
assert f"{moment}" == str(moment)                           # empty spec, via str
```

## Arithmetic and Comparison

Every value is a handful of integers, so the distance between two of them costs nothing extra:
subtracting dates nine thousand years apart is the same work as subtracting neighbours.

```python
from datetime import date, datetime, timedelta

first = datetime(2024, 1, 15)
second = datetime(2024, 1, 20)

delta = second - first                          # O(1)
assert delta == timedelta(days=5)
assert delta.total_seconds() == 432_000         # O(1)
assert first + timedelta(days=5) == second      # O(1)
assert first < second                           # O(1)

span = date(9999, 12, 31) - date(1, 1, 1)       # O(1) - the distance is not a factor
assert span.days == 3_652_058

# Past the supported range is an error, not a bigger object
try:
    date(9999, 12, 31) + timedelta(days=1)
except OverflowError as error:
    assert "out of range" in str(error)
else:
    raise AssertionError("a date past MAXYEAR was built")
```

## Time Zones

`timezone` is a fixed offset, so arithmetic, comparison and conversion on a datetime that uses one
stay O(1). `astimezone()` converts, keeping the instant; `replace(tzinfo=...)` relabels, keeping
the wall-clock time.

```python
from datetime import datetime, timedelta, timezone

utc_moment = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
plus_five = timezone(timedelta(hours=5))                # O(1)

converted = utc_moment.astimezone(plus_five)            # O(1) - one fromutc() call
assert converted.hour == 17
assert converted == utc_moment                          # the same instant

relabelled = utc_moment.replace(tzinfo=plus_five)       # O(1) - no conversion
assert relabelled.hour == 12
assert relabelled != utc_moment                         # a different instant

assert plus_five.dst(converted) is None                 # a fixed offset has no DST
assert timezone(timedelta(0)) is timezone.utc           # the singleton
```

## Common Patterns

### Grouping Timestamps by Day

```python
from collections import Counter
from datetime import datetime

log = [
    "2024-01-15T08:15:00",
    "2024-01-15T17:40:00",
    "2024-01-16T09:05:00",
]

per_day = Counter(datetime.fromisoformat(line).date() for line in log)  # O(n) per line
assert per_day[datetime(2024, 1, 15).date()] == 2
assert len(per_day) == 2
```

### Storing Aware Timestamps

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)            # O(1), aware
stored = now.isoformat()                    # O(1)
restored = datetime.fromisoformat(stored)   # O(n)

assert restored == now
assert restored.utcoffset() is not None
```

## Performance Best Practices

✅ **Do**:

- Parse ISO 8601 with `fromisoformat()`: it needs no format and no compiled regex
- Parse a batch with one format at a time, so `strptime()` compiles it once
- Serialize with `isoformat()` and read back with `fromisoformat()`: O(1) out, O(n) in, no format either way
- Use `datetime.now(timezone.utc)` for the current UTC time; it is O(1) like `utcnow()`, and aware

❌ **Avoid**:

- `strptime()` with a hand-written ISO format, when `fromisoformat()` reads the same input for less
- `datetime.utcnow()` and `datetime.utcfromtimestamp()`, deprecated since 3.12
- `replace(tzinfo=...)` to convert between zones - it relabels without converting; use `astimezone()`

## Version Notes

- **Python 3.11+**: `fromisoformat()` accepts most of ISO 8601, including a trailing `Z`, the
  basic format and any number of fractional-second digits; before that it read only what
  `isoformat()` produced
- **Python 3.11+**: Added `datetime.UTC`
- **Python 3.12+**: `datetime.utcnow()` and `datetime.utcfromtimestamp()` are deprecated in
  favour of `datetime.now(timezone.utc)` and `datetime.fromtimestamp(timestamp, timezone.utc)`
- **Python 3.12.8+ and 3.13.1+**: compiling a `strptime()` format is O(f); earlier releases
  build its regular expression in O(f·d) for a format of d ≥ 1 directives
- **Python 3.14+**: Added `date.strptime()` and `time.strptime()`

## Related Modules

- **[time](time.md)** - POSIX timestamps, `struct_time` and monotonic clocks
- **[zoneinfo](zoneinfo.md)** - IANA time zones, whose offset lookups search the recorded transitions
- **[calendar](calendar.md)** - Month and year layouts built on `date`
