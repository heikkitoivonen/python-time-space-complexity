# zoneinfo Module Complexity

The `zoneinfo` module provides IANA time zones for `datetime`, daylight saving time included. A
`ZoneInfo` is parsed once from a TZif file into sorted arrays of transition times, and is cached by
key. Every offset lookup is a binary search over those arrays, or constant time before the first
recorded transition and after the last.

`t` is the transitions recorded in a zone's TZif file (a few hundred for a zone with daylight saving
time, none for `UTC`), and `s` is the same for the zone a datetime is converted from. `p` is the
entries on the search path, `f` the files and directories under the `TZPATH` trees, `z` the zones
found there or listed by the packaged `tzdata` database, and `c` the cached zones. Checking whether
one search-path entry holds a key is one filesystem probe, and hashing a key is treated as O(1).

## Complexity Reference

### ZoneInfo

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zoneinfo.ZoneInfo(key)`, first load | O(p + t) | O(t) | Probes the search path for the file, falling back to the `tzdata` package; parses it and caches the result |
| `zoneinfo.ZoneInfo(key)`, cached | O(1) | O(1) | Returns the same object. It stays cached while referenced, and the eight most recently looked up stay alive regardless |
| `ZoneInfo.no_cache(key)` | O(p + t) | O(t) | Loads and parses every time; neither reads nor fills the cache |
| `ZoneInfo.from_file(file_obj, /, key=None)` | O(t) | O(t) | Never cached, and cannot be pickled |
| `ZoneInfo.clear_cache(*, only_keys=None)` | O(c) | O(1) | O(len(only_keys)) with `only_keys`; the next lookup of a dropped key loads it again |
| `ZoneInfo.utcoffset(dt)`, `ZoneInfo.dst(dt)`, `ZoneInfo.tzname(dt)` | O(log t) | O(1) | O(1) before the first recorded transition and after the last |
| `ZoneInfo.fromutc(dt)` | O(log t) | O(1) | O(1) before the first recorded transition and after the last; `astimezone()` calls it |
| `dt.astimezone(zone)` | O(log s + log t) | O(1) | One `utcoffset()` in the source zone, then `zone.fromutc()` |
| `ZoneInfo.key` | O(1) | O(1) | `None` for a `from_file()` zone unless a key was passed |
| Pickling a `ZoneInfo` | O(1) | O(1) | Pickled by key, without the transition data; unpickling is `ZoneInfo(key)`, or `ZoneInfo.no_cache(key)` for a zone `no_cache()` made |

### Search path

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zoneinfo.available_timezones()` | O(p + f + z) | O(f + z) | Opens each file under the `TZPATH` trees, outside `right/` and `posix/`, whose key is not already known to be a zone; nothing is cached, so every call walks again and returns a new set |
| `zoneinfo.reset_tzpath(to=None)` | O(p) | O(p) | Entries of `to` must be absolute; zones already cached stay usable |
| `zoneinfo.TZPATH` | O(1) | O(1) | The tuple of search directories |

### Exceptions and warnings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zoneinfo.ZoneInfoNotFoundError` | O(1) | O(1) | A `KeyError` subclass, raised when neither the search path nor the `tzdata` package has the key |
| `zoneinfo.InvalidTZPathWarning` | O(1) | O(1) | Warned when `PYTHONTZPATH` holds a relative entry, which is dropped |

## Loading and Caching Zones

### The Cache

A first lookup searches for the file and parses it; a later lookup of the same key returns the same
object for as long as the zone stays cached. `no_cache()` always parses and leaves the cache alone, and `clear_cache()` makes the
next lookup parse again.

```python
from zoneinfo import ZoneInfo

a = ZoneInfo("Europe/London")  # O(p + t) on first load
b = ZoneInfo("Europe/London")  # O(1) - the cached object
assert a is b

c = ZoneInfo.no_cache("Europe/London")  # O(p + t) every time
assert c is not a
assert ZoneInfo("Europe/London") is a  # no_cache() did not replace it

ZoneInfo.clear_cache(only_keys=["Europe/London"])  # O(len(only_keys))
assert ZoneInfo("Europe/London") is not a  # parsed again
```

### Cache Lifetime

The cache holds a zone weakly once it falls out of the eight most recently looked up, so a zone you
keep a reference to stays cached, and one you drop may be parsed again.

```python
import gc
import weakref
from zoneinfo import ZoneInfo

ZoneInfo.clear_cache()
held = ZoneInfo("Africa/Cairo")
dropped = weakref.ref(ZoneInfo("Africa/Lagos"))

for key in ["Asia/Tokyo", "Europe/Paris", "Europe/Berlin", "Europe/Rome",
            "Europe/Madrid", "Asia/Kolkata", "Asia/Shanghai", "Australia/Sydney"]:
    ZoneInfo(key)  # pushes Cairo and Lagos out of the eight most recent
gc.collect()

assert ZoneInfo("Africa/Cairo") is held  # O(1) - still cached through the reference
assert dropped() is None  # gone: the next ZoneInfo("Africa/Lagos") parses again
```

### Pickling

A `ZoneInfo` is pickled by key, without its transition data, so unpickling a zone made by
`ZoneInfo(key)` is `ZoneInfo(key)` again: a cache hit where the zone is cached, a load where it is
not, and the receiving process needs the same zone in its own database. A `from_file()` zone cannot
be pickled, even when it was given a key.

```python
import pickle
from zoneinfo import ZoneInfo

zone = ZoneInfo("America/New_York")
data = pickle.dumps(zone)  # O(1) - the key only
assert b"America/New_York" in data
assert pickle.loads(data) is zone  # O(1) - a cache hit
```

## Looking Up Offsets

### Converting Between Zones

Attaching a zone to a datetime looks nothing up. Each offset, name or conversion is at most one
binary search over the zone's transitions, and a conversion between two zones at most one in each.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

new_york = ZoneInfo("America/New_York")
los_angeles = ZoneInfo("America/Los_Angeles")

dt = datetime(2024, 1, 15, 12, 0, tzinfo=new_york)  # O(1) - no lookup yet
assert str(dt) == "2024-01-15 12:00:00-05:00"  # O(log t)
assert dt.tzname() == "EST"  # O(log t)

converted = dt.astimezone(los_angeles)  # O(log s + log t)
assert str(converted) == "2024-01-15 09:00:00-08:00"
```

### Beyond the Transition Table

A TZif file records transitions up to some year, and may end with a rule for the years after it.
A lookup past the last recorded transition evaluates that rule for the datetime's year, or takes
the last recorded offset where there is no rule; either costs the same whatever `t` is.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

zone = ZoneInfo("America/New_York")

assert datetime(1990, 7, 1, tzinfo=zone).tzname() == "EDT"  # O(log t) - a recorded transition
assert datetime(2100, 7, 1, tzinfo=zone).tzname() == "EDT"  # O(1) - the rule
assert datetime(2100, 1, 1, tzinfo=zone).tzname() == "EST"  # O(1)
```

## Listing Zones

`available_timezones()` finds zones by opening files: it walks every `TZPATH` tree and reads the
first bytes of each file it does not already know to be a zone. Nothing is cached between calls.

```python
from zoneinfo import available_timezones

zones = available_timezones()  # O(p + f + z) - opens the files under TZPATH
assert "America/New_York" in zones  # O(1) - a set
assert available_timezones() is not zones  # O(p + f + z) again
```

## Common Patterns

### Converting a Batch of Timestamps

```python
from datetime import datetime
from zoneinfo import ZoneInfo

zone = ZoneInfo("America/New_York")  # O(p + t) once
timestamps = [0, 1_700_000_000, 2_000_000_000]

local = [datetime.fromtimestamp(ts, zone) for ts in timestamps]  # O(log t) each
assert [dt.isoformat() for dt in local] == [
    "1969-12-31T19:00:00-05:00",
    "2023-11-14T17:13:20-05:00",
    "2033-05-17T23:33:20-04:00",
]
```

## Performance Best Practices

✅ **Do**:

- Look zones up by key and let the cache hold them: a cache hit is O(1)
- Keep a reference to a zone you use often, so it is not parsed again once it leaves the eight
  most recently looked up
- Call `available_timezones()` once and keep the set

❌ **Avoid**:

- `no_cache()` or `from_file()` in a loop - every call parses the file again
- `available_timezones()` per request - it opens the files under `TZPATH` every time

## Version Notes

- **Python 3.9+**: Added the module
- **All Python 3**: The default `TZPATH` is empty on Windows, and the module reads no Windows time
  zone data; without the `tzdata` package or a database named in `PYTHONTZPATH`, every key raises
  `ZoneInfoNotFoundError`

## Related Modules

- **[datetime](datetime.md)** - the `datetime` and `tzinfo` types a `ZoneInfo` is attached to
- **[time](time.md)** - the process-wide local time zone, without the IANA database
