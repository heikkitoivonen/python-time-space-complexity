"""Tests for docs/stdlib/zoneinfo.md.

`zoneinfo.ZoneInfo` is the C type from Modules/_zoneinfo.c on every supported
interpreter, and Lib/zoneinfo/_zoneinfo.py is the pure-Python reference
implementation of the same algorithm: transitions in sorted arrays, a binary
search to find the one that applies, the zone's footer rule past the last one,
and a weak-value cache by key plus a strong LRU of the eight most recently used
zones. The C type hides its arrays, so the O(log t) rows are counted on the
Python implementation, whose transition lists accept ints that count their
comparisons; cache rows are observed on the C type by identity and weak
references; load rows by traced allocation and time on synthetic TZif files
parsed from memory, so that opening a file does not dominate the parse.

Measurement scope:

* One entry per transition: the Python implementation's UTC list, both
  local-time lists and the per-transition ttinfo list each have `t` entries
  for UTC (0), Asia/Tokyo (single digits) and America/New_York (hundreds).
  The counts come from whichever database is installed (the operating
  system's, or the `tzdata` package on Windows), so the tests assert those
  relations rather than fixed numbers.
* Load space: `from_file()` on synthetic files of 1,000, 10,000 and 100,000
  transitions peaks at 88 bytes per transition for the C type and 136 for the
  Python one, every step x10; each step is asserted between x5 and x20. A real
  zone is asserted to cost more than 16 bytes per transition over UTC.
* Load time: the same three sizes cost about x10 per x10 step for both
  implementations (x10-x13 for C, x10-x20 for Python, which allocates more);
  each step is asserted between x3 and x40, against x1 for a constant parse and
  x100 for a quadratic one.
* The p term of a first load: 40 nonexistent directories prepended to
  `TZPATH` add exactly 40 `os.path.isfile` probes to `ZoneInfo.no_cache()`,
  and with the packaged database hidden a missing key costs one probe per
  entry before `ZoneInfoNotFoundError`.
* Lookups inside New York's table cost 10 comparisons for `utcoffset()`,
  `dst()` and `tzname()` each and 11 for `fromutc()`; a 100,000-transition
  synthetic zone costs 18 and 20 (asserted at most 2 * t.bit_length() + 3, where a scan
  would cost about t). A zone-to-zone `astimezone()` costs the source's
  `utcoffset()` plus the destination's `fromutc()`, within 2. Before the
  table, 1 comparison (asserted at most 2); past New York's table, whose
  footer rule has seasonal transitions, 2 for both directions; building a
  datetime with a zone, none; UTC, which has no table, none.
* The cache: a hit is the same object; of ten zones looked up and dropped,
  the last eight survive `gc.collect()`; a lookup of the oldest of eight keeps
  it alive past one more insertion (LRU, not FIFO); a zone pushed out of the
  eight survives while referenced and is collected when not; `clear_cache()`
  drops all keys or only the ones given; a pickle round trip is the cached
  object, and the pickle carries the key; a `no_cache()` zone unpickles to a
  new object; a `from_file()` zone with or without a key raises `PicklingError`.
* `available_timezones()` opens a file for every key under the system `TZPATH`
  roots outside `right/` and `posix/`, on each call, and returns a new, equal
  set. Over two temporary roots sharing
  their keys it opens a valid zone once, an invalid file once per root, nothing
  under `right/` or `posix/`, and nothing whose key the packaged list names.
* `reset_tzpath()` rejects a relative entry with `ValueError`, drops a relative
  `PYTHONTZPATH` entry with `InvalidTZPathWarning`, and leaves cached zones
  usable when the path no longer finds them. On Windows `TZPATH` is asserted
  empty and, with the packaged database hidden, a key is asserted not found.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The C type's lookups are held to O(log t) by source: `find_ttinfo()` and
  `zoneinfo_fromutc()` call the same `_bisect()` over the same arrays. Past
  the table its `fromutc()` evaluates the footer rule whatever the footer is;
  the Python implementation bisects instead when the footer is a fixed offset
  (Asia/Tokyo), which still meets the O(log t) row, so no test pins either.
* Clearing c cached zones and `reset_tzpath()` over p entries are read from
  Lib/zoneinfo/_tzpath.py and the C cache functions, not measured. Freeing an
  evicted zone is not priced.
* `available_timezones()` is observed by the files it opens, not timed in f,
  and its O(f + z) space is read from `os.walk` and the returned set.
* The strong cache exists only for `ZoneInfo` itself in the C type; a
  subclass gets the weak cache alone. Subclasses are not tested.
* Every lookup compared or counted uses `fold=0`, and ambiguous and
  nonexistent times in real zones are not sampled.
* Windows reads no Windows time zone data: the `TZPATH` assertion runs only
  there, and CI's Windows runners install `tzdata`, so the zone-loading tests
  run on it. The test that walks the system database skips on Windows, which
  has none under `TZPATH`.
* Implementation diffs between v3.10.19 and v3.14.2 touch the packaged-database
  access (`open_binary()`/`open_text()` on 3.10, `files()` from 3.11) and
  argument validation, not the search or the cache; the tests replace all
  three access functions so they run on every supported version.
"""

from __future__ import annotations

import builtins
import gc
import importlib
import importlib.resources
import io
import os
import pathlib
import pickle
import re
import struct
import subprocess
import sys
import textwrap
import time
import tracemalloc
import weakref
import zoneinfo
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zoneinfo.md"
EXPECTED_BLOCKS = 7

_zoneinfo: Any = importlib.import_module("zoneinfo._zoneinfo")
"""The pure-Python reference implementation, whose transition lists are inspectable."""

FIXED = "UTC"
FEW = "Asia/Tokyo"
MANY = "America/New_York"
ZONES = (FIXED, FEW, MANY)

INSIDE = datetime(1990, 7, 1, 12)
"""A date inside New York's transition table and past Tokyo's."""

TEN_KEYS = (
    "Asia/Tokyo", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
    "Asia/Kolkata", "Asia/Shanghai", "Australia/Sydney", "America/Chicago", "America/Denver",
)  # fmt: skip

PACKAGE_READERS = ("files", "open_text", "open_binary")
"""How zoneinfo reaches the packaged database: files() from 3.11, the other two on 3.10."""


def hide_packaged_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the optional packaged database look absent, as the module tests for it."""

    def absent(*args: Any, **kwargs: Any) -> Any:
        raise ImportError("no packaged database")

    for reader in PACKAGE_READERS:
        monkeypatch.setattr(importlib.resources, reader, absent, raising=False)


@pytest.fixture
def no_packaged_database(monkeypatch: pytest.MonkeyPatch) -> None:
    hide_packaged_database(monkeypatch)


@pytest.fixture
def restore_tzpath() -> Any:
    original = zoneinfo.TZPATH
    yield
    zoneinfo.reset_tzpath(original)


def transitions(key: str) -> int:
    """How many transitions this machine's TZif file for `key` records."""
    return len(_zoneinfo.ZoneInfo.no_cache(key)._trans_utc)


def synthetic_tzif(count: int) -> bytes:
    """A version-1 TZif file, no footer, `count` hourly transitions from 1906."""
    abbreviations = b"STD\x00DST\x00"
    header = b"TZif\x00" + b"\x00" * 15 + struct.pack(">6l", 0, 0, 0, count, 2, len(abbreviations))
    first = -2_000_000_000
    times = struct.pack(f">{count}l", *range(first, first + count * 3600, 3600))
    indices = bytes(i % 2 for i in range(count))
    ttinfos = struct.pack(">lBB", 0, 0, 0) + struct.pack(">lBB", 3600, 1, 4)
    return header + times + indices + ttinfos + abbreviations


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        best = min(best, time.perf_counter_ns() - start)
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation of one call, after a warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Counting(int):
    """An int that counts how often it is compared."""

    calls = 0

    def __lt__(self, other: int) -> bool:
        Counting.calls += 1
        return int.__lt__(self, other)

    def __gt__(self, other: int) -> bool:
        Counting.calls += 1
        return int.__gt__(self, other)

    def __le__(self, other: int) -> bool:
        Counting.calls += 1
        return int.__le__(self, other)

    def __ge__(self, other: int) -> bool:
        Counting.calls += 1
        return int.__ge__(self, other)


def counting(zone: Any) -> Any:
    """`zone` (Python implementation) with transition lists that count comparisons."""
    zone._trans_local = [[Counting(x) for x in lst] for lst in zone._trans_local]
    zone._trans_utc = [Counting(x) for x in zone._trans_utc]
    return zone


def counting_zone(key: str) -> Any:
    return counting(_zoneinfo.ZoneInfo.no_cache(key))


def comparisons(func: Callable[[], Any]) -> int:
    Counting.calls = 0
    func()
    return Counting.calls


class TestTheCTypeIsWhatUsersGet:
    """The counting tests run on the Python implementation; this pins that the
    C type is the one exported and that the two answer alike."""

    def test_the_c_type_is_in_use(self) -> None:
        assert ZoneInfo is not _zoneinfo.ZoneInfo
        assert ZoneInfo.__module__ == "zoneinfo"

    def test_both_implementations_agree(self) -> None:
        for key in ZONES:
            c_zone, py_zone = ZoneInfo(key), _zoneinfo.ZoneInfo.no_cache(key)
            for year in (1800, 1950, 1990, 2024, 2100):
                for month in (1, 7):
                    dt = datetime(year, month, 1, 12)
                    assert c_zone.utcoffset(dt) == py_zone.utcoffset(dt), (key, dt)
                    assert c_zone.tzname(dt) == py_zone.tzname(dt), (key, dt)
                    in_utc = dt.replace(tzinfo=timezone.utc)
                    c_local = in_utc.astimezone(c_zone).replace(tzinfo=None)
                    py_local = in_utc.astimezone(py_zone).replace(tzinfo=None)
                    assert c_local == py_local, (key, dt)


class TestLoadingParsesEachTransitionOnce:
    """Rows: a first load is O(p + t) time and O(t) space; `no_cache()` and
    `from_file()` parse every time.

    The t term is settled on synthetic files at three sizes a decade apart, by
    allocation and by time; the p term by counting search-path probes.
    """

    def test_the_zones_have_the_shapes_the_tests_assume(self) -> None:
        assert transitions(FIXED) == 0
        assert 0 < transitions(FEW) < 50
        assert transitions(MANY) > 100
        tokyo = _zoneinfo.ZoneInfo.no_cache(FEW)
        new_york = _zoneinfo.ZoneInfo.no_cache(MANY)
        inside = INSIDE.replace(tzinfo=timezone.utc).timestamp()
        assert tokyo._trans_utc[-1] < inside
        assert new_york._trans_utc[0] < inside < new_york._trans_utc[-1]

    @pytest.mark.parametrize("key", ZONES)
    def test_the_parsed_structures_hold_one_entry_per_transition(self, key: str) -> None:
        zone = _zoneinfo.ZoneInfo.no_cache(key)
        t = len(zone._trans_utc)
        assert len(zone._ttinfos) == t
        assert len(zone._trans_local[0]) == len(zone._trans_local[1]) == t

    def test_a_real_zone_allocates_with_its_transitions(self) -> None:
        t = transitions(MANY)
        fixed = peak_bytes(lambda: ZoneInfo.no_cache(FIXED))
        many = peak_bytes(lambda: ZoneInfo.no_cache(MANY))
        assert many - fixed > 16 * t, f"{many - fixed} bytes for {t} transitions"

    @pytest.mark.parametrize("implementation", ["c", "python"])
    def test_allocation_is_linear_in_the_transitions(self, implementation: str) -> None:
        loader = ZoneInfo.from_file if implementation == "c" else _zoneinfo.ZoneInfo.from_file
        sizes = (1_000, 10_000, 100_000)
        files = [synthetic_tzif(size) for size in sizes]

        peaks = [peak_bytes(lambda data=data: loader(io.BytesIO(data))) for data in files]
        steps = [peaks[i + 1] / peaks[i] for i in range(len(peaks) - 1)]

        assert all(5 < step < 20 for step in steps), (
            f"{implementation}: peaks {peaks} for {sizes} transitions"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("implementation", ["c", "python"])
    def test_load_time_is_linear_in_the_transitions(self, implementation: str) -> None:
        loader = ZoneInfo.from_file if implementation == "c" else _zoneinfo.ZoneInfo.from_file
        sizes = (1_000, 10_000, 100_000)
        files = [synthetic_tzif(size) for size in sizes]

        times = [best_ns(lambda data=data: loader(io.BytesIO(data))) for data in files]
        steps = [times[i + 1] / times[i] for i in range(len(times) - 1)]

        assert all(3 < step < 40 for step in steps), (
            f"{implementation}: x10 steps in t cost {[f'x{s:.1f}' for s in steps]}"
        )

    def test_a_synthetic_file_parses_to_its_transition_count(self) -> None:
        zone = _zoneinfo.ZoneInfo.from_file(io.BytesIO(synthetic_tzif(1_000)))
        assert len(zone._trans_utc) == 1_000
        c_zone = ZoneInfo.from_file(io.BytesIO(synthetic_tzif(1_000)))
        assert c_zone.utcoffset(datetime(1950, 1, 1)) == timedelta(hours=1)

    def test_each_search_path_entry_is_one_probe(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        restore_tzpath: None,
    ) -> None:
        probes: list[str] = []
        real_isfile = os.path.isfile

        def record(path: Any) -> bool:
            probes.append(os.fspath(path))
            return real_isfile(path)

        monkeypatch.setattr(os.path, "isfile", record)
        original = zoneinfo.TZPATH
        empty = tuple(str(tmp_path / f"empty{i}") for i in range(40))

        ZoneInfo.no_cache(MANY)
        base = len(probes)
        probes.clear()
        zoneinfo.reset_tzpath(empty + original)
        ZoneInfo.no_cache(MANY)

        assert len(probes) == base + 40, (base, len(probes))

        probes.clear()
        hide_packaged_database(monkeypatch)
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
            ZoneInfo.no_cache("Not/AZone")
        assert len(probes) == len(empty) + len(original)

    def test_no_cache_neither_reads_nor_fills_the_cache(self) -> None:
        ZoneInfo.clear_cache(only_keys=[MANY])
        fresh = ZoneInfo.no_cache(MANY)
        cached = ZoneInfo(MANY)
        assert cached is not fresh
        assert ZoneInfo(MANY) is cached
        assert ZoneInfo.no_cache(MANY) is not cached

    def test_from_file_is_uncached_keyless_and_unpicklable(self) -> None:
        data = synthetic_tzif(10)
        zone = ZoneInfo.from_file(io.BytesIO(data))
        named = ZoneInfo.from_file(io.BytesIO(data), key=MANY)
        assert zone.key is None
        assert named.key == MANY
        assert named is not ZoneInfo(MANY)
        assert ZoneInfo.from_file(io.BytesIO(data)) is not zone
        for unpicklable in (zone, named):
            with pytest.raises(pickle.PicklingError):
                pickle.dumps(unpicklable)

    def test_a_missing_key_raises(self) -> None:
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError, match="Not/AZone"):
            ZoneInfo("Not/AZone")


class TestTheCacheReturnsTheSameObject:
    """Rows: a cache hit is O(1) and the same object; a zone stays cached while
    referenced or among the eight most recently used; pickling stores the key."""

    def test_the_cache_hit_is_the_same_object(self) -> None:
        assert ZoneInfo(MANY) is ZoneInfo(MANY)

    def test_a_pickle_is_the_key_and_unpickles_to_the_cached_zone(self) -> None:
        data = pickle.dumps(ZoneInfo(MANY))
        assert MANY.encode() in data
        assert len(data) < 200
        assert pickle.loads(data) is ZoneInfo(MANY)

    def test_a_no_cache_zone_unpickles_through_no_cache(self) -> None:
        original = ZoneInfo.no_cache(MANY)
        restored = pickle.loads(pickle.dumps(original))
        assert restored is not original
        assert restored is not ZoneInfo(MANY)
        assert restored.key == MANY

    def test_the_eight_most_recently_used_zones_survive_without_references(self) -> None:
        ZoneInfo.clear_cache()
        refs = [weakref.ref(ZoneInfo(key)) for key in TEN_KEYS]
        gc.collect()

        alive = [ref() is not None for ref in refs]

        assert alive == [False, False] + [True] * 8, alive

    def test_touching_a_zone_makes_it_recent_again(self) -> None:
        """A FIFO would evict the oldest insertion; the LRU evicts the least
        recently *used*, so a lookup rescues an old entry."""
        ZoneInfo.clear_cache()
        refs = {key: weakref.ref(ZoneInfo(key)) for key in TEN_KEYS[:8]}
        ZoneInfo(TEN_KEYS[0])
        ZoneInfo(TEN_KEYS[8])
        gc.collect()

        assert refs[TEN_KEYS[0]]() is not None
        assert refs[TEN_KEYS[1]]() is None

    def test_a_referenced_zone_survives_being_pushed_out_of_the_lru(self) -> None:
        ZoneInfo.clear_cache()
        held = ZoneInfo("Africa/Cairo")
        for key in TEN_KEYS[:9]:
            ZoneInfo(key)
        gc.collect()

        assert ZoneInfo("Africa/Cairo") is held

    def test_an_unreferenced_zone_pushed_out_of_the_lru_is_dropped(self) -> None:
        ZoneInfo.clear_cache()
        ref = weakref.ref(ZoneInfo("Africa/Cairo"))
        for key in TEN_KEYS[:9]:
            ZoneInfo(key)
        gc.collect()

        assert ref() is None

    def test_clear_cache_drops_only_the_keys_given(self) -> None:
        tokyo, many = ZoneInfo(FEW), ZoneInfo(MANY)
        ZoneInfo.clear_cache(only_keys=[FEW])
        assert ZoneInfo(FEW) is not tokyo
        assert ZoneInfo(MANY) is many

    def test_clear_cache_drops_everything_by_default(self) -> None:
        tokyo, many = ZoneInfo(FEW), ZoneInfo(MANY)
        ZoneInfo.clear_cache()
        assert ZoneInfo(FEW) is not tokyo
        assert ZoneInfo(MANY) is not many


class TestLookupsBisectTheTransitions:
    """Rows: `utcoffset()`, `dst()`, `tzname()` and `fromutc()` are O(log t),
    O(1) before the first recorded transition and after the last;
    `astimezone()` is one lookup in each zone.

    Counted on the Python implementation: a binary search costs about log2 t
    comparisons where a scan costs about t, so the bound 2 log2 t + 3 excludes
    the scan by orders of magnitude at t = 100,000.
    """

    def test_lookups_inside_the_table_are_logarithmic(self) -> None:
        zone = counting_zone(MANY)
        inside = INSIDE.replace(tzinfo=zone)
        t = transitions(MANY)

        utcoffset = comparisons(lambda: zone.utcoffset(inside))
        dst = comparisons(lambda: zone.dst(inside))
        tzname = comparisons(lambda: zone.tzname(inside))

        assert 3 <= utcoffset <= 2 * t.bit_length() + 2, f"{utcoffset} comparisons for t={t}"
        assert dst == tzname == utcoffset

    def test_fromutc_is_logarithmic_too(self) -> None:
        zone = counting_zone(MANY)
        t = transitions(MANY)
        in_utc = INSIDE.replace(tzinfo=timezone.utc)

        count = comparisons(lambda: in_utc.astimezone(zone))

        assert 3 <= count <= 2 * t.bit_length() + 3, f"{count} comparisons for t={t}"

    def test_both_stay_logarithmic_at_a_hundred_thousand_transitions(self) -> None:
        t = 100_000
        zone = counting(_zoneinfo.ZoneInfo.from_file(io.BytesIO(synthetic_tzif(t))))
        inside = datetime(1910, 1, 1, 12)
        assert zone._trans_utc[0] < inside.replace(tzinfo=timezone.utc).timestamp()
        assert inside.replace(tzinfo=timezone.utc).timestamp() < zone._trans_utc[-1]

        local = comparisons(lambda: zone.utcoffset(inside.replace(tzinfo=zone)))
        from_utc = comparisons(lambda: inside.replace(tzinfo=timezone.utc).astimezone(zone))

        assert 3 <= local <= 2 * t.bit_length() + 3, f"{local} comparisons for t={t}"
        assert 3 <= from_utc <= 2 * t.bit_length() + 3, f"{from_utc} comparisons for t={t}"

    def test_a_zone_to_zone_conversion_pays_for_both_lookups(self) -> None:
        source, destination = counting_zone(MANY), counting_zone("Europe/London")
        local = INSIDE.replace(tzinfo=source)
        in_utc = INSIDE.replace(tzinfo=timezone.utc)

        source_only = comparisons(lambda: source.utcoffset(local))
        destination_only = comparisons(lambda: in_utc.astimezone(destination))
        both = comparisons(lambda: local.astimezone(destination))

        assert source_only >= 3 and destination_only >= 3
        assert abs(both - (source_only + destination_only)) <= 2, (
            both,
            source_only,
            destination_only,
        )

    def test_before_the_table_one_comparison_settles_it(self) -> None:
        zone = counting_zone(MANY)
        early = datetime(1800, 7, 1, 12, tzinfo=zone)
        assert comparisons(lambda: zone.utcoffset(early)) <= 2
        assert comparisons(lambda: datetime(1800, 7, 1, tzinfo=timezone.utc).astimezone(zone)) <= 2

    def test_past_the_table_the_footer_rule_costs_a_constant(self) -> None:
        zone = counting_zone(MANY)
        assert isinstance(zone._tz_after, _zoneinfo._TZStr)
        far = datetime(2100, 7, 1, 12, tzinfo=zone)
        assert comparisons(lambda: zone.utcoffset(far)) == 2
        assert comparisons(lambda: zone.tzname(far)) == 2
        assert comparisons(lambda: datetime(2100, 7, 1, tzinfo=timezone.utc).astimezone(zone)) == 2

    def test_constructing_a_datetime_looks_nothing_up(self) -> None:
        zone = counting_zone(MANY)
        assert comparisons(lambda: datetime(1990, 7, 1, 12, tzinfo=zone)) == 0

    def test_the_rule_path_gives_the_right_answers(self) -> None:
        zone = ZoneInfo(MANY)
        assert datetime(2100, 7, 1, tzinfo=zone).tzname() == "EDT"
        assert datetime(2100, 1, 1, tzinfo=zone).tzname() == "EST"
        assert datetime(2100, 7, 1, tzinfo=zone).dst() == timedelta(hours=1)
        assert datetime(1990, 7, 1, tzinfo=zone).tzname() == "EDT"

    def test_a_zone_without_transitions_has_no_table(self) -> None:
        zone = counting_zone(FIXED)
        assert comparisons(lambda: zone.utcoffset(datetime(2024, 1, 1, tzinfo=zone))) == 0
        assert comparisons(lambda: datetime(2024, 1, 1, tzinfo=timezone.utc).astimezone(zone)) == 0
        assert ZoneInfo(FIXED).utcoffset(datetime(2024, 1, 1)) == timedelta(0)
        assert dt_time(12, tzinfo=ZoneInfo(FIXED)).utcoffset() == timedelta(0)
        assert dt_time(12, tzinfo=ZoneInfo(MANY)).utcoffset() is None


class TestAvailableTimezonesOpensFiles:
    """Row: `available_timezones()` is O(p + f + z): it opens each file under
    `TZPATH` whose key is not already known, on every call, and returns a new set."""

    @staticmethod
    def recording_open(monkeypatch: pytest.MonkeyPatch) -> list[str]:
        opened: list[str] = []
        real_open = builtins.open

        def record(file: Any, *args: Any, **kwargs: Any) -> Any:
            opened.append(os.fspath(file))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", record)
        return opened

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Windows has no time zone database under TZPATH"
    )
    @pytest.mark.usefixtures("no_packaged_database")
    def test_opens_a_file_for_every_key_under_the_system_path_on_every_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        roots = [root for root in zoneinfo.TZPATH if os.path.isdir(root)]
        assert roots, "no zoneinfo database on TZPATH"
        keys: set[str] = set()
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                if dirpath == root:
                    dirnames[:] = [d for d in dirnames if d not in ("right", "posix")]
                keys.update(os.path.relpath(os.path.join(dirpath, f), root) for f in filenames)

        opened = self.recording_open(monkeypatch)
        first = zoneinfo.available_timezones()
        first_opens = list(opened)
        opened.clear()
        second = zoneinfo.available_timezones()

        opened_keys = {
            os.path.relpath(path, root)
            for path in first_opens
            for root in roots
            if path.startswith(root + os.sep)
        }
        assert keys <= opened_keys, sorted(keys - opened_keys)[:5]
        assert opened == first_opens
        assert first == second
        assert first is not second

    @pytest.mark.usefixtures("no_packaged_database", "restore_tzpath")
    def test_a_key_is_opened_until_it_is_known_to_be_a_zone(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two roots with the same keys: a valid zone is opened in the first
        root only, an invalid file in both, and right/ and posix/ never."""
        tzif = synthetic_tzif(1)
        roots = [tmp_path / "first", tmp_path / "second"]
        for root in roots:
            (root / "Zone").mkdir(parents=True)
            (root / "Zone" / "Valid").write_bytes(tzif)
            (root / "Junk").write_bytes(b"not a zone")
            for special in ("right", "posix"):
                (root / special).mkdir()
                (root / special / "Valid").write_bytes(tzif)
        zoneinfo.reset_tzpath([str(root) for root in roots])
        opened = self.recording_open(monkeypatch)

        zones = zoneinfo.available_timezones()

        assert zones == {"Zone/Valid"}
        assert sorted(opened) == sorted(
            [str(roots[0] / "Zone" / "Valid"), str(roots[0] / "Junk"), str(roots[1] / "Junk")]
        )

    @pytest.mark.usefixtures("restore_tzpath")
    def test_the_packaged_list_is_read_and_its_keys_are_not_opened(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakePackage:
            def joinpath(self, name: str) -> FakePackage:
                assert name == "zones"
                return self

            def open(self, *args: Any, **kwargs: Any) -> io.StringIO:
                return io.StringIO("Packaged/Zone\n\n")

        monkeypatch.setattr(importlib.resources, "files", lambda package: FakePackage())
        monkeypatch.setattr(
            importlib.resources,
            "open_text",
            lambda *args, **kwargs: FakePackage().open(),
            raising=False,
        )
        (tmp_path / "Packaged").mkdir()
        (tmp_path / "Packaged" / "Zone").write_bytes(b"would be opened if unknown")
        zoneinfo.reset_tzpath([str(tmp_path)])
        opened = self.recording_open(monkeypatch)

        zones = zoneinfo.available_timezones()

        assert zones == {"Packaged/Zone"}
        assert opened == []

    def test_the_result_is_a_set_of_zone_keys(self) -> None:
        zones = zoneinfo.available_timezones()
        assert isinstance(zones, set)
        assert MANY in zones
        assert "posixrules" not in zones
        assert len(zones) > 300


class TestSearchPath:
    """Rows: `reset_tzpath()` takes absolute entries only; cached zones outlive
    a path change; the exception and warning are the documented types."""

    def test_relative_entries_are_rejected(self) -> None:
        before = zoneinfo.TZPATH
        with pytest.raises(ValueError, match="absolute"):
            zoneinfo.reset_tzpath(["relative/path"])
        assert zoneinfo.TZPATH == before

    @pytest.mark.usefixtures("restore_tzpath")
    def test_cached_zones_survive_an_empty_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cached = ZoneInfo(MANY)
        hide_packaged_database(monkeypatch)
        empty = str(tmp_path / "nonexistent")

        zoneinfo.reset_tzpath([empty])

        assert zoneinfo.TZPATH == (empty,)
        assert ZoneInfo(MANY) is cached
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
            ZoneInfo.no_cache(MANY)

    @pytest.mark.usefixtures("restore_tzpath")
    def test_a_relative_environment_entry_is_dropped_with_a_warning(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        absolute = str(tmp_path)
        monkeypatch.setenv("PYTHONTZPATH", os.pathsep.join(["relative/dir", absolute]))

        with pytest.warns(zoneinfo.InvalidTZPathWarning):
            zoneinfo.reset_tzpath()

        assert zoneinfo.TZPATH == (absolute,)

    def test_the_types_are_what_the_rows_say(self) -> None:
        assert isinstance(zoneinfo.TZPATH, tuple)
        assert issubclass(zoneinfo.InvalidTZPathWarning, RuntimeWarning)
        assert issubclass(zoneinfo.ZoneInfoNotFoundError, KeyError)

    @pytest.mark.skipif(
        sys.platform != "win32", reason="only a Windows build sets no default TZPATH"
    )
    @pytest.mark.usefixtures("no_packaged_database", "restore_tzpath")
    def test_windows_needs_the_tzdata_package(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYTHONTZPATH", raising=False)
        zoneinfo.reset_tzpath()

        assert zoneinfo.TZPATH == ()
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
            ZoneInfo.no_cache(MANY)


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so the zone cache and `TZPATH`
    cannot leak between them, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert dropped() is None" in s)
        mutated = source.replace("assert dropped() is None", "assert dropped() is not None", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(source, tmp_path).returncode == 0
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr, result.stderr
