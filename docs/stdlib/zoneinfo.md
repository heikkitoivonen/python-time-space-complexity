# zoneinfo Module Complexity

The `zoneinfo` module provides IANA time zone support for `datetime`,
including daylight saving time. A `ZoneInfo` object is parsed once from a
TZif file and cached. A lookup inside its recorded transitions is a binary
search; one before the first is constant, and so is one after the last when
the zone's footer rule has seasonal transitions to evaluate.

## Complexity Reference

Let `t` be the number of transitions in a zone's TZif file (a few hundred for
a zone with daylight saving time, none for `UTC`), `s` the same for the zone a
datetime is converted from, `f` the number of files and directories under the
`TZPATH` trees, `z` the number of zones found there or listed by the packaged
database, `c` the number of cached zones, and `p` the number of search-path
entries.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ZoneInfo(key)`, first load | O(p + t) | O(t) | Probes the search path for the file, then reads and parses it, one entry per transition, and caches the instance |
| `ZoneInfo(key)`, cached | O(1) | O(1) | Returns the same object. It lives while referenced, and the eight most recently used zones stay alive regardless |
| `ZoneInfo.no_cache(key)` | O(p + t) | O(t) | Probes and parses every time; neither reads nor fills the cache |
| `ZoneInfo.from_file(f, key=None)` | O(t) | O(t) | Never cached; the result cannot be pickled |
| `ZoneInfo.clear_cache(only_keys=None)` | O(c) | O(1) | Drops every cached zone, or O(len(only_keys)) for the keys given; the next load parses again |
| `utcoffset(dt)`, `dst(dt)`, `tzname(dt)` | O(log t) | O(1) | Binary search over the transitions in local time. O(1) before the first transition and after the last, where the zone's footer rule is evaluated for the year of `dt` |
| `fromutc(dt)` | O(log t) | O(1) | The same search over the UTC transitions, plus the fold check. O(1) before the first transition, and after the last only when the footer rule has seasonal transitions; a fixed-offset footer still searches |
| `dt.astimezone(zone)` | O(log s + log t) | O(1) | The source zone's `utcoffset()`, then `zone.fromutc()` |
| `key` | O(1) | O(1) | `None` for a `from_file()` zone unless one was passed |
| `available_timezones()` | O(p + f + z) | O(z + f) | Reads the packaged zone list if one is installed, then walks the `TZPATH` trees, skipping `right` and `posix`, and opens each file whose key is not yet a known zone to check for the TZif magic; the walk's listings are the `f` term. Nothing is cached: every call walks again and returns a new set |
| `reset_tzpath(to=None)` | O(p) | O(p) | `to`'s entries, or with `None` those of `PYTHONTZPATH` or the build's default. An entry of `to` must be absolute, `ValueError` otherwise; a relative `PYTHONTZPATH` entry is dropped with `InvalidTZPathWarning`. Zones already cached stay usable |
| `TZPATH` | O(1) | — | The tuple of search directories |
| `ZoneInfoNotFoundError`, `InvalidTZPathWarning` | — | — | Raised when no file matches `key`; warned when `PYTHONTZPATH` holds a relative entry |

## Working with Time Zones

### Using Timezones

```python
from zoneinfo import ZoneInfo
from datetime import datetime

# Create timezone - O(p + t) on first load, O(1) from the cache afterwards
est = ZoneInfo("America/New_York")
pst = ZoneInfo("America/Los_Angeles")

# Create datetime with timezone - O(1)
dt = datetime(2024, 1, 15, 12, 0, tzinfo=est)
print(dt)  # 2024-01-15 12:00:00-05:00

# Convert timezone - O(log s + log t), one lookup in each zone
dt_pst = dt.astimezone(pst)
print(dt_pst)  # 2024-01-15 09:00:00-08:00

# Get timezone name - O(log t)
print(dt.tzname())  # EST
```

### The Cache

```python
from zoneinfo import ZoneInfo

# O(1) - the second call returns the very same object
a = ZoneInfo("Europe/London")
b = ZoneInfo("Europe/London")
a is b  # True

# O(p + t) - a fresh probe and parse that leaves the cache alone
c = ZoneInfo.no_cache("Europe/London")
c is a  # False

# O(1) - one key to drop; the next lookup parses again
ZoneInfo.clear_cache(only_keys=["Europe/London"])
ZoneInfo("Europe/London") is a  # False
```

### Beyond the Transition Table

```python
from zoneinfo import ZoneInfo
from datetime import datetime

zone = ZoneInfo("America/New_York")

# O(log t) - inside the table of recorded transitions
datetime(1990, 7, 1, tzinfo=zone).tzname()  # 'EDT'

# O(1) - after the last recorded transition the footer rule decides
datetime(2100, 7, 1, tzinfo=zone).tzname()  # 'EDT'
datetime(2100, 1, 1, tzinfo=zone).tzname()  # 'EST'
```

### Listing Zones

```python
from zoneinfo import available_timezones

# O(p + f + z) - walks the search path, opening files as it goes; call it once and keep the set
zones = available_timezones()
"America/New_York" in zones  # True
```

## Best Practices

✅ **Do**:

- Look zones up by key and let the cache hold them
- Call `available_timezones()` once and keep the set
- Keep a reference to a zone you use often, so it survives beyond the eight
  the cache holds on its own

❌ **Avoid**:

- `no_cache()` or `from_file()` in a loop - every call parses the file again
- Calling `available_timezones()` per request - it walks the search path every time

## Related Documentation

- [datetime Module](datetime.md)
