"""Tests for docs/stdlib/zoneinfo.md.

`zoneinfo.ZoneInfo` is the C type from Modules/_zoneinfo.c on every supported
interpreter, with Lib/zoneinfo/_zoneinfo.py as the reference implementation of
the same algorithm. Both keep the zone's transitions in sorted arrays and find
the one that applies with a binary search (`_bisect` in C, `bisect_right` in
Python), fall back to the zone's POSIX rule past the last transition, and share
the two-level cache: a weak-value dictionary keyed by zone name plus a strong
LRU of eight (`ZONEINFO_STRONG_CACHE_MAX_SIZE`, `_strong_cache_size`). Neither
has changed between the v3.10.0 tag and the 3.14 branch.

The C type hides its arrays, so the O(log t) rows are counted on the Python
implementation: its transition lists are replaced with ints whose comparison
operators count. Inside America/New_York's table (236 transitions in this
machine's database, 1883 to 2037) a lookup costs 10 comparisons for
`utcoffset()` and 11 for `fromutc()`, where a linear scan would cost about
236, and a zone-to-zone `astimezone()` costs the two added together. Before
the table one comparison settles it. Past the table, a zone whose footer rule
has seasonal transitions (New York) costs 2 whatever `t` is; one whose footer
is a fixed offset (Asia/Tokyo, `JST-9`, table ending in 1951) still costs 2
for `utcoffset()` but 6 for `fromutc()`, which bisects its 9 transitions
rather than short-circuit. Constructing a
datetime with a zone costs no comparison at all. The C type is held to the
same bounds by source.

The other rows are observed directly: identity for the cache hit, weak
references for the two cache lifetimes and for the touch that makes the strong
cache an LRU rather than a FIFO, `len()` of the parsed transition lists and
traced allocation for the O(t) load, and a recording `open()` for
`available_timezones()`: on this machine it opens all 506 distinct files under
/usr/share/zoneinfo on every call to return 498 zones, and over two temporary
roots that share their keys it opens a valid zone once, an invalid file once
per root, and a key the packaged list already names not at all.

Allocation is compared across transition counts on the Python implementation,
where each transition costs Python objects: 88 bytes per transition for
Asia/Tokyo's 9 and 134 for New York's 236, so the per-transition cost moves
by x1.5 for x26 in `t`, where a quadratic parse would move it by x26 too. The
C type is checked only for growing with `t` (about 74 bytes per transition).

Transition counts and the table's year range come from the operating system's
tz database, not from Python, so the tests read them from the loaded zone and
assert relations (UTC has none, Asia/Tokyo's table ends in 1951, New York's
has hundreds and spans 1990) rather than fixed numbers. The module reaches the
optional packaged database through `importlib.resources` - `files()` from
3.11, `open_text()` and `open_binary()` on 3.10 - so the tests replace those
functions: with ones raising ImportError to measure the `TZPATH` walk and the
not-found path alone, and with a fake package whose zone list names one key to
check that the list is read and that a listed key is not opened again.

The O(p) search-path term of a first load is a probe per root and is not
measured; the tests hold `TZPATH` fixed and vary `t` only.

Load time is measured on synthetic TZif files parsed from memory through
`from_file()`, because opening a real file dominates a parse of a few hundred
transitions (13us for UTC against 22us for America/New_York with the C type).
A hundredfold step from 1,000 to 100,000 transitions costs x126 with the C type
and x94 with the Python one, against x1 for a constant parse and x10,000 for a
quadratic one. The tests otherwise need a system zoneinfo database under one
of the `TZPATH` directories, as CI's Ubuntu runners have.
"""

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
import tracemalloc
import weakref
import zoneinfo
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

import pytest

_zoneinfo: Any = importlib.import_module("zoneinfo._zoneinfo")
"""The pure-Python reference implementation, whose transition lists are inspectable."""

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zoneinfo.md"

FIXED = "UTC"
FEW = "Asia/Tokyo"
MANY = "America/New_York"
ZONES = (FIXED, FEW, MANY)

INSIDE = datetime(1990, 7, 1, 12)
"""A date inside New York's transition table and past Tokyo's."""


PACKAGE_READERS = ("files", "open_text", "open_binary")
"""How zoneinfo reaches the packaged database: files() from 3.11, the other two on 3.10."""


@pytest.fixture
def no_packaged_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the optional packaged database look absent, as the module tests for it."""

    def absent(*args: Any, **kwargs: Any) -> Any:
        raise ImportError("no packaged database")

    for reader in PACKAGE_READERS:
        monkeypatch.setattr(importlib.resources, reader, absent, raising=False)


def transitions(key: str) -> int:
    """How many transitions this machine's TZif file for `key` records."""
    return len(_zoneinfo.ZoneInfo.no_cache(key)._trans_utc)


def synthetic_tzif(count: int) -> bytes:
    """A version-1 TZif file with `count` hourly transitions between two offsets."""
    abbreviations = b"STD\x00DST\x00"
    header = b"TZif\x00" + b"\x00" * 15 + struct.pack(">6l", 0, 0, 0, count, 2, len(abbreviations))
    first = -2_000_000_000
    times = struct.pack(f">{count}l", *range(first, first + count * 3600, 3600))
    indices = bytes(i % 2 for i in range(count))
    ttinfos = struct.pack(">lBB", 0, 0, 0) + struct.pack(">lBB", 3600, 1, 4)
    return header + times + indices + ttinfos + abbreviations


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    best = float("inf")
    for _ in range(repeats):
        start = perf_counter()
        func()
        best = min(best, perf_counter() - start)
    return best


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc attributes to one call, after a warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


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


def counting_zone(key: str) -> Any:
    """The Python implementation of `key`, with transition lists that count comparisons."""
    zone = _zoneinfo.ZoneInfo.no_cache(key)
    zone._trans_local = [[Counting(x) for x in lst] for lst in zone._trans_local]
    zone._trans_utc = [Counting(x) for x in zone._trans_utc]
    return zone


def comparisons(func: Callable[[], Any]) -> int:
    Counting.calls = 0
    func()
    return Counting.calls


class TestImplementation:
    """The tests below count on the Python implementation; the C one is what users get."""

    def test_the_c_type_is_in_use(self) -> None:
        assert ZoneInfo is not _zoneinfo.ZoneInfo
        assert ZoneInfo.__module__ == "zoneinfo"

    def test_both_implementations_agree(self) -> None:
        for key in ZONES:
            c_zone, py_zone = ZoneInfo(key), _zoneinfo.ZoneInfo.no_cache(key)
            for year in (1950, 1990, 2024, 2100):
                for month in (1, 7):
                    dt = datetime(year, month, 1, 12)
                    assert c_zone.utcoffset(dt) == py_zone.utcoffset(dt), (key, dt)
                    assert c_zone.tzname(dt) == py_zone.tzname(dt), (key, dt)


class TestLoading:
    """Rows: a first load parses O(t) entries; no_cache() and from_file() always do."""

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

    def test_allocation_grows_with_the_transitions(self) -> None:
        t = transitions(MANY)
        fixed = traced_peak(lambda: ZoneInfo.no_cache(FIXED))
        many = traced_peak(lambda: ZoneInfo.no_cache(MANY))
        assert many - fixed > 16 * t, f"{many - fixed} bytes for {t} transitions"

    def test_a_synthetic_file_parses_to_its_transition_count(self) -> None:
        zone = _zoneinfo.ZoneInfo.from_file(io.BytesIO(synthetic_tzif(1_000)))
        assert len(zone._trans_utc) == 1_000
        assert ZoneInfo.from_file(io.BytesIO(synthetic_tzif(1_000))).utcoffset(
            datetime(1950, 1, 1)
        ) == timedelta(hours=1)

    @pytest.mark.timing
    @pytest.mark.parametrize("implementation", ["c", "python"])
    def test_load_time_is_linear_in_the_transitions(self, implementation: str) -> None:
        loader = ZoneInfo.from_file if implementation == "c" else _zoneinfo.ZoneInfo.from_file
        small, large = synthetic_tzif(1_000), synthetic_tzif(100_000)

        ratio = best_time(lambda: loader(io.BytesIO(large))) / best_time(
            lambda: loader(io.BytesIO(small))
        )

        assert 30 < ratio < 1_000, f"x100 in t cost x{ratio:.1f} for the {implementation} parser"

    def test_allocation_per_transition_is_flat(self) -> None:
        """Linear growth keeps bytes-per-transition steady across zones; a
        quadratic parse would multiply it by the ratio of the counts."""
        base = traced_peak(lambda: _zoneinfo.ZoneInfo.no_cache(FIXED))
        few_t, many_t = transitions(FEW), transitions(MANY)
        few = traced_peak(lambda: _zoneinfo.ZoneInfo.no_cache(FEW)) - base
        many = traced_peak(lambda: _zoneinfo.ZoneInfo.no_cache(MANY)) - base

        per_transition_growth = (many / many_t) / (few / few_t)

        assert many_t / few_t > 10, "the two zones should differ widely in t"
        assert 0.25 < per_transition_growth < 4, (
            f"bytes per transition moved x{per_transition_growth:.2f} for x{many_t / few_t:.0f} in t"
        )

    def test_no_cache_neither_reads_nor_fills_the_cache(self) -> None:
        ZoneInfo.clear_cache(only_keys=[MANY])
        fresh = ZoneInfo.no_cache(MANY)
        cached = ZoneInfo(MANY)
        assert cached is not fresh
        assert ZoneInfo(MANY) is cached
        assert ZoneInfo.no_cache(MANY) is not cached

    def test_from_file_is_uncached_keyless_and_unpicklable(self) -> None:
        path = next(
            pathlib.Path(root) / MANY
            for root in zoneinfo.TZPATH
            if (pathlib.Path(root) / MANY).exists()
        )
        with path.open("rb") as handle:
            zone = ZoneInfo.from_file(handle)
        with path.open("rb") as handle:
            named = ZoneInfo.from_file(handle, key=MANY)
        assert zone.key is None
        assert named.key == MANY
        assert zone is not ZoneInfo(MANY)
        assert named is not ZoneInfo(MANY)
        assert zone.utcoffset(datetime(2024, 7, 1)) == ZoneInfo(MANY).utcoffset(
            datetime(2024, 7, 1)
        )
        with pytest.raises(pickle.PicklingError):
            pickle.dumps(zone)

    def test_a_missing_key_raises(self) -> None:
        with pytest.raises(zoneinfo.ZoneInfoNotFoundError, match="Not/AZone"):
            ZoneInfo("Not/AZone")


class TestCache:
    """Rows: the cache hit is the same object; lifetimes are a weak map plus an LRU of eight."""

    def test_the_cache_hit_is_the_same_object(self) -> None:
        assert ZoneInfo(MANY) is ZoneInfo(MANY)
        assert pickle.loads(pickle.dumps(ZoneInfo(MANY))) is ZoneInfo(MANY)

    def test_the_eight_most_recently_used_zones_survive_without_references(self) -> None:
        ZoneInfo.clear_cache()
        keys = [
            "Asia/Tokyo", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
            "Asia/Kolkata", "Asia/Shanghai", "Australia/Sydney", "America/Chicago", "America/Denver",
        ]  # fmt: skip
        refs = [weakref.ref(ZoneInfo(key)) for key in keys]
        gc.collect()

        alive = [ref() is not None for ref in refs]

        assert alive == [False, False] + [True] * 8, alive

    def test_touching_a_zone_makes_it_recent_again(self) -> None:
        """A FIFO would evict the oldest insertion; the LRU evicts the least
        recently *used*, so a lookup rescues an old entry."""
        ZoneInfo.clear_cache()
        keys = ["Asia/Tokyo", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
                "Asia/Kolkata", "Asia/Shanghai", "Australia/Sydney"]  # fmt: skip
        refs = {key: weakref.ref(ZoneInfo(key)) for key in keys}
        ZoneInfo("Asia/Tokyo")
        ZoneInfo("America/Chicago")
        gc.collect()

        assert refs["Asia/Tokyo"]() is not None
        assert refs["Europe/Paris"]() is None

    def test_a_referenced_zone_survives_being_pushed_out_of_the_lru(self) -> None:
        ZoneInfo.clear_cache()
        held = ZoneInfo("Africa/Cairo")
        for key in ("Asia/Tokyo", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
                    "Asia/Kolkata", "Asia/Shanghai", "Australia/Sydney", "America/Chicago"):  # fmt: skip
            ZoneInfo(key)
        gc.collect()

        assert ZoneInfo("Africa/Cairo") is held

    def test_an_unreferenced_zone_pushed_out_of_the_lru_is_dropped(self) -> None:
        ZoneInfo.clear_cache()
        ref = weakref.ref(ZoneInfo("Africa/Cairo"))
        for key in ("Asia/Tokyo", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
                    "Asia/Kolkata", "Asia/Shanghai", "Australia/Sydney", "America/Chicago"):  # fmt: skip
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


class TestOffsetLookup:
    """Rows: utcoffset/dst/tzname and fromutc are O(log t); the rule path is O(1)."""

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

    def test_past_the_table_a_seasonal_footer_costs_a_constant(self) -> None:
        zone = counting_zone(MANY)
        assert isinstance(zone._tz_after, _zoneinfo._TZStr)
        far = datetime(2100, 7, 1, 12, tzinfo=zone)
        assert comparisons(lambda: zone.utcoffset(far)) == 2
        assert comparisons(lambda: zone.tzname(far)) == 2
        assert comparisons(lambda: datetime(2100, 7, 1, tzinfo=timezone.utc).astimezone(zone)) == 2

    def test_past_the_table_a_fixed_offset_footer_still_searches_in_fromutc(self) -> None:
        zone = counting_zone(FEW)
        t = transitions(FEW)
        assert isinstance(zone._tz_after, _zoneinfo._ttinfo)
        assert comparisons(lambda: zone.utcoffset(INSIDE.replace(tzinfo=zone))) == 2

        count = comparisons(lambda: INSIDE.replace(tzinfo=timezone.utc).astimezone(zone))

        assert 3 <= count <= 2 * t.bit_length() + 3, f"{count} comparisons for t={t}"

    def test_that_search_is_logarithmic_at_a_hundred_thousand_transitions(self) -> None:
        """A synthetic footer-less zone whose table ends in 1918: fromutc() for
        1990 bisects 100,000 transitions in about 17 comparisons, where a
        linear scan would take about 100,000."""
        t = 100_000
        zone = _zoneinfo.ZoneInfo.from_file(io.BytesIO(synthetic_tzif(t)))
        assert isinstance(zone._tz_after, _zoneinfo._ttinfo)
        zone._trans_utc = [Counting(x) for x in zone._trans_utc]
        zone._trans_local = [[Counting(x) for x in lst] for lst in zone._trans_local]
        past = INSIDE.replace(tzinfo=timezone.utc)
        assert past.timestamp() > zone._trans_utc[-1]

        count = comparisons(lambda: past.astimezone(zone))

        assert 3 <= count <= 2 * t.bit_length() + 3, f"{count} comparisons for t={t}"
        assert comparisons(lambda: zone.utcoffset(INSIDE.replace(tzinfo=zone))) == 2

    def test_constructing_a_datetime_looks_nothing_up(self) -> None:
        zone = counting_zone(MANY)
        assert comparisons(lambda: datetime(1990, 7, 1, 12, tzinfo=zone)) == 0

    def test_the_rule_path_gives_the_right_answers(self) -> None:
        zone = ZoneInfo(MANY)
        assert datetime(2100, 7, 1, tzinfo=zone).tzname() == "EDT"
        assert datetime(2100, 1, 1, tzinfo=zone).tzname() == "EST"
        assert datetime(2100, 7, 1, tzinfo=zone).dst() == timedelta(hours=1)
        assert datetime(1990, 7, 1, tzinfo=zone).tzname() == "EDT"

    def test_a_fixed_offset_zone_has_no_table(self) -> None:
        zone = counting_zone(FIXED)
        assert comparisons(lambda: zone.utcoffset(datetime(2024, 1, 1, tzinfo=zone))) == 0
        assert ZoneInfo(FIXED).utcoffset(datetime(2024, 1, 1)) == timedelta(0)
        assert time(12, tzinfo=ZoneInfo(FIXED)).utcoffset() == timedelta(0)
        assert time(12, tzinfo=ZoneInfo(MANY)).utcoffset() is None

    def test_documented_conversion(self) -> None:
        est, pst = ZoneInfo("America/New_York"), ZoneInfo("America/Los_Angeles")
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=est)
        assert str(dt) == "2024-01-15 12:00:00-05:00"
        assert str(dt.astimezone(pst)) == "2024-01-15 09:00:00-08:00"
        assert dt.tzname() == "EST"


class TestAvailableTimezones:
    """Row: opens every file under TZPATH on every call; a new set each time."""

    @staticmethod
    def recording_open(monkeypatch: pytest.MonkeyPatch) -> list[str]:
        opened: list[str] = []
        real_open = builtins.open

        def record(file: Any, *args: Any, **kwargs: Any) -> Any:
            opened.append(os.fspath(file))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", record)
        return opened

    @pytest.mark.usefixtures("no_packaged_database")
    def test_opens_every_file_under_the_system_path_on_every_call(
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

    @pytest.mark.usefixtures("no_packaged_database")
    def test_a_key_is_opened_until_it_is_known_to_be_a_zone(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two roots with the same keys: a valid zone is opened in the first
        root only, an invalid file in both, and right/ and posix/ never."""
        tzif = next(
            (pathlib.Path(root) / FIXED).read_bytes()
            for root in zoneinfo.TZPATH
            if (pathlib.Path(root) / FIXED).exists()
        )
        roots = [tmp_path / "first", tmp_path / "second"]
        for root in roots:
            (root / "Zone").mkdir(parents=True)
            (root / "Zone" / "Valid").write_bytes(tzif)
            (root / "Junk").write_bytes(b"not a zone")
            for special in ("right", "posix"):
                (root / special).mkdir()
                (root / special / "Valid").write_bytes(tzif)
        original = zoneinfo.TZPATH
        zoneinfo.reset_tzpath([str(root) for root in roots])
        try:
            opened = self.recording_open(monkeypatch)
            zones = zoneinfo.available_timezones()
        finally:
            zoneinfo.reset_tzpath(original)

        assert zones == {"Zone/Valid"}
        assert sorted(opened) == sorted(
            [str(roots[0] / "Zone" / "Valid"), str(roots[0] / "Junk"), str(roots[1] / "Junk")]
        )

    def test_the_packaged_list_is_read_and_its_keys_are_not_opened(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakePackage:
            def joinpath(self, name: str) -> "FakePackage":
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
        original = zoneinfo.TZPATH
        zoneinfo.reset_tzpath([str(tmp_path)])
        try:
            opened = self.recording_open(monkeypatch)
            zones = zoneinfo.available_timezones()
        finally:
            zoneinfo.reset_tzpath(original)

        assert zones == {"Packaged/Zone"}
        assert opened == []

    def test_the_result_is_a_set_of_loadable_keys(self) -> None:
        zones = zoneinfo.available_timezones()
        assert isinstance(zones, set)
        assert MANY in zones
        assert "posixrules" not in zones
        assert len(zones) > 300


class TestTzpath:
    """Rows: reset_tzpath validates its entries; cached zones outlive a path change."""

    def test_relative_entries_are_rejected(self) -> None:
        before = zoneinfo.TZPATH
        with pytest.raises(ValueError, match="absolute"):
            zoneinfo.reset_tzpath(["relative/path"])
        assert zoneinfo.TZPATH == before

    @pytest.mark.usefixtures("no_packaged_database")
    def test_cached_zones_survive_an_empty_path(self) -> None:
        cached = ZoneInfo(MANY)
        original = zoneinfo.TZPATH
        try:
            zoneinfo.reset_tzpath(["/nonexistent"])
            assert zoneinfo.TZPATH == ("/nonexistent",)
            assert ZoneInfo(MANY) is cached
            with pytest.raises(zoneinfo.ZoneInfoNotFoundError):
                ZoneInfo.no_cache(MANY)
        finally:
            zoneinfo.reset_tzpath(original)
        assert zoneinfo.TZPATH == original

    def test_a_relative_environment_entry_is_dropped_with_a_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = zoneinfo.TZPATH
        absolute = next(root for root in original if os.path.isabs(root))
        monkeypatch.setenv("PYTHONTZPATH", os.pathsep.join(["relative/dir", absolute]))
        try:
            with pytest.warns(zoneinfo.InvalidTZPathWarning):
                zoneinfo.reset_tzpath()
            assert zoneinfo.TZPATH == (absolute,)
        finally:
            zoneinfo.reset_tzpath(original)
        assert zoneinfo.TZPATH == original

    def test_tzpath_is_a_tuple_and_the_warning_exists(self) -> None:
        assert isinstance(zoneinfo.TZPATH, tuple)
        assert issubclass(zoneinfo.InvalidTZPathWarning, RuntimeWarning)
        assert issubclass(zoneinfo.ZoneInfoNotFoundError, KeyError)


class TestPublicNamesAreDocumented:
    """The Complexity Reference against dir(zoneinfo) and dir(ZoneInfo)."""

    @staticmethod
    def documented_names() -> set[str]:
        text = PAGE.read_text(encoding="utf-8")
        start = text.index("## Complexity Reference")
        end = text.index("## Working with Time Zones")
        names: set[str] = set()
        for line in text[start:end].splitlines():
            if not line.startswith("| `"):
                continue
            names.update(re.findall(r"`(?:ZoneInfo\.)?(\w+)", line.split("|")[1]))
        return names

    def test_the_extractor_sees_the_table(self) -> None:
        assert {"no_cache", "available_timezones", "TZPATH"} <= self.documented_names()

    def test_every_public_name_has_a_row(self) -> None:
        public = {name for name in dir(zoneinfo) if not name.startswith("_")}
        public |= {name for name in dir(ZoneInfo) if not name.startswith("_")}

        missing = public - self.documented_names()

        assert not missing, f"public names without a row: {sorted(missing)}"

    def test_every_row_names_something_that_exists(self) -> None:
        public = {name for name in dir(zoneinfo) if not name.startswith("_")}
        public |= {name for name in dir(ZoneInfo) if not name.startswith("_")}
        public |= {"ZoneInfo", "astimezone", "dt", "zone", "f", "key", "to", "only_keys", "None"}

        invented = self.documented_names() - public

        assert not invented, f"rows naming nothing that exists: {sorted(invented)}"


EXPECTED_BLOCKS = 4


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
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
    """Every block runs, under the interpreter running the tests."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_every_block_binds_the_names_it_uses(self, tmp_path: pathlib.Path) -> None:
        """A block that leans on a name from its prose rather than binding it
        compiles and then dies at run time, so NameError gets its own check."""
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_stated_values_hold(self) -> None:
        a = ZoneInfo("Europe/London")
        assert ZoneInfo("Europe/London") is a
        assert ZoneInfo.no_cache("Europe/London") is not a
        ZoneInfo.clear_cache(only_keys=["Europe/London"])
        assert ZoneInfo("Europe/London") is not a
        assert "America/New_York" in zoneinfo.available_timezones()

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        first = _blocks()[0][1]
        broken = first.replace("from zoneinfo import ZoneInfo\n", "", 1)
        assert broken != first, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
