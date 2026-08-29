"""Tests for the claims added to the stdlib pages that go beyond the tables.

The companion to tests/test_builtin_claims.py, organised one class per
module. What is here is the explanatory half of each page - the sentences
asserting something the complexity table does not - since that is where this
repo's claims have actually been wrong.

Several are settled by observation rather than timing, which is the better
kind of test: `filecmp.dircmp` accepting a directory that does not exist
proves it reads nothing at construction, and no tolerance is involved.

Deliberately not covered, because a unit test cannot settle them:

* docs/stdlib/pwd.md - lookup cost is decided by the NSS backend, which may
  be a local file or a network directory
* docs/stdlib/smtplib.md - round trip counts need a real SMTP conversation
* docs/stdlib/multiprocessing.md - the IPC claims need spawned processes;
  only the chunking, which is ordinary list work, is tested here
* docs/stdlib/cgi.md, docs/stdlib/cgitb.md - removed in Python 3.13, so a
  test would have to be skipped on any current interpreter
"""

import array
import bisect
import filecmp
import fnmatch
import importlib
import io
import logging
import numbers
import posixpath
import pprint
import sqlite3
import struct
import tempfile
import time
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal, getcontext
from functools import cmp_to_key
from ipaddress import IPv4Network
from pathlib import Path
from typing import Any

import pytest
import tomllib


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class TestArrayTypeCodes:
    """docs/stdlib/array.md: the type code fixes the bytes per item, which is
    what array buys over list."""

    def test_type_code_fixes_the_item_size(self) -> None:
        assert array.array("b").itemsize == 1
        assert array.array("i").itemsize in (2, 4)
        assert array.array("d").itemsize == 8

    def test_storage_follows_item_size(self) -> None:
        import sys

        bytes_array = array.array("b", range(100))
        doubles = array.array("d", [float(i) for i in range(100)])
        assert sys.getsizeof(doubles) > sys.getsizeof(bytes_array)


class TestDecimalSpecialValues:
    """docs/stdlib/decimal.md: special values short-circuit, skipping the
    O(n) digit arithmetic."""

    def test_infinity_arithmetic_skips_the_digits(self) -> None:
        precision = getcontext().prec
        getcontext().prec = 50_000
        try:
            big = Decimal("1." + "9" * 20_000)
            infinity = Decimal("Infinity")
            digits_time = best_time(lambda: big + big)
            special_time = best_time(lambda: infinity + 5)
        finally:
            getcontext().prec = precision

        assert special_time * 3 < digits_time, (
            f"a special value has no digits to add: "
            f"digits={digits_time:.2e}s special={special_time:.2e}s"
        )

    def test_special_values_still_propagate(self) -> None:
        assert Decimal("Infinity") + 5 == Decimal("Infinity")
        assert (Decimal("NaN") + 5).is_nan()


class TestDefaultdictInsertsOnRead:
    """docs/stdlib/defaultdict.md: reading a missing key returns the default
    *and inserts it*, where dict.get() does not."""

    def test_reading_a_missing_key_inserts_it(self) -> None:
        counts: defaultdict[str, int] = defaultdict(int)
        assert counts["missing"] == 0
        assert "missing" in counts, "the read was also a write"

    def test_get_does_not_insert(self) -> None:
        plain = {"a": 1}
        assert plain.get("missing", 0) == 0
        assert "missing" not in plain

    def test_the_difference_shows_up_in_length(self) -> None:
        counts: defaultdict[str, int] = defaultdict(int)
        for key in ("a", "b", "c"):
            _ = counts[key]
        assert len(counts) == 3


class TestFilecmpIsLazy:
    """docs/stdlib/filecmp.md: dircmp() is O(1) because nothing is read yet;
    the stat calls happen when you touch same_files."""

    def test_construction_reads_nothing(self) -> None:
        # Constructing over directories that do not exist cannot possibly
        # have touched the filesystem.
        comparison = filecmp.dircmp("/nonexistent-left", "/nonexistent-right")
        assert comparison.left == "/nonexistent-left"

    def test_the_filesystem_is_touched_on_access(self) -> None:
        comparison = filecmp.dircmp("/nonexistent-left", "/nonexistent-right")
        with pytest.raises(OSError):
            _ = comparison.same_files

    def test_a_real_comparison_still_works(self, tmp_path: Path) -> None:
        left, right = tmp_path / "l", tmp_path / "r"
        left.mkdir()
        right.mkdir()
        (left / "same.txt").write_text("x", encoding="utf-8")
        (right / "same.txt").write_text("x", encoding="utf-8")
        assert filecmp.dircmp(str(left), str(right)).same_files == ["same.txt"]


class TestFnmatchPatternCost:
    """docs/stdlib/fnmatch.md: patterns are compiled and cached, so the
    wildcard used does not change the cost; filter() is O(k*n)."""

    def test_wildcard_choice_does_not_change_the_cost(self) -> None:
        name = "some_moderately_long_filename.txt"
        star = best_time(lambda: [fnmatch.fnmatch(name, "*.txt") for _ in range(20_000)])
        classes = best_time(lambda: [fnmatch.fnmatch(name, "[a-z]*.txt") for _ in range(20_000)])

        ratio = max(star, classes) / min(star, classes)
        assert ratio < 4.0, (
            f"both compile to a cached regex: star={star:.2e}s classes={classes:.2e}s"
        )

    def test_filter_scales_with_the_number_of_names(self) -> None:
        few = [f"file{i}.txt" for i in range(100)]
        many = [f"file{i}.txt" for i in range(10_000)]

        few_time = best_time(lambda: fnmatch.filter(few, "*.txt"))
        many_time = best_time(lambda: fnmatch.filter(many, "*.txt"))

        assert many_time > few_time * 10, (
            f"filter() is O(k) in names: {few_time:.2e}s vs {many_time:.2e}s"
        )

    def test_two_patterns_means_two_passes(self) -> None:
        names = [f"file{i}.py" for i in range(20_000)]
        one = best_time(lambda: fnmatch.filter(names, "*.py"))
        two = best_time(lambda: fnmatch.filter(names, "*.py") + fnmatch.filter(names, "*.js"))

        assert two > one * 1.5, (
            f"a second pattern is a second full pass: one={one:.2e}s two={two:.2e}s"
        )


class TestCmpToKeyCallsPerComparison:
    """docs/stdlib/functools.md: the cmp_to_key wrapper calls compare() on
    every comparison, where key= computes a key once per element."""

    def test_compare_runs_per_comparison_not_per_element(self) -> None:
        import random

        size = 200
        data = list(range(size))
        random.shuffle(data)

        comparisons = {"n": 0}
        key_calls = {"n": 0}

        def compare(left: int, right: int) -> int:
            comparisons["n"] += 1
            return (left > right) - (left < right)

        def key(value: int) -> int:
            key_calls["n"] += 1
            return value

        sorted(data, key=cmp_to_key(compare))
        sorted(data, key=key)

        assert key_calls["n"] == size, "key= is called exactly once per element"
        assert comparisons["n"] > size * 3, (
            f"compare() runs per comparison, about n log n: {comparisons['n']} calls for n={size}"
        )


class TestImportlibReloadIsShallow:
    """docs/stdlib/importlib.md: reload() re-executes one module body, not
    the transitive import graph."""

    def test_dependencies_are_not_re_executed(self, tmp_path: Path) -> None:
        import sys

        package = tmp_path / "reload_probe"
        package.mkdir()
        (package / "dep.py").write_text("RUNS = []\nRUNS.append(1)\n", encoding="utf-8")
        (package / "top.py").write_text("import dep\nVALUE = len(dep.RUNS)\n", encoding="utf-8")

        sys.path.insert(0, str(package))
        try:
            top = importlib.import_module("top")
            dep = importlib.import_module("dep")
            before = len(dep.RUNS)

            importlib.reload(top)

            assert len(dep.RUNS) == before, "the dependency's body must not re-run"
            assert top.VALUE == before
        finally:
            sys.path.remove(str(package))
            for name in ("top", "dep"):
                sys.modules.pop(name, None)


class TestIpaddressSupernetIsBounded:
    """docs/stdlib/ipaddress.md: widening drops one prefix bit per step, so
    the loop is bounded by the address size."""

    def test_widening_terminates_within_the_prefix_length(self) -> None:
        network = IPv4Network("10.1.2.0/24")
        steps = 0
        while network.prefixlen > 0:
            network = network.supernet()
            steps += 1

        assert steps == 24, "one bit per step, from /24 to /0"
        assert steps <= 32, "and never more than the address width"

    def test_membership_does_not_scan_the_network(self) -> None:
        from ipaddress import IPv4Address

        small = IPv4Network("10.0.0.0/30")  # 4 addresses
        huge = IPv4Network("10.0.0.0/8")  # 16 million

        small_time = best_time(lambda: [IPv4Address("10.0.0.1") in small for _ in range(5_000)])
        huge_time = best_time(lambda: [IPv4Address("10.0.0.1") in huge for _ in range(5_000)])

        ratio = max(small_time, huge_time) / min(small_time, huge_time)
        assert ratio < 3.0, (
            f"membership is arithmetic on the prefix, not a scan: "
            f"/30={small_time:.2e}s /8={huge_time:.2e}s"
        )


class TestLoggingArgumentsAreBuiltEagerly:
    """docs/stdlib/logging.md: an f-string is formatted even when the record
    is filtered out."""

    def test_fstring_runs_below_the_level_threshold(self) -> None:
        formatted = {"n": 0}

        class Counted:
            def __format__(self, spec: str) -> str:
                formatted["n"] += 1
                return "value"

        logger = logging.getLogger("test_stdlib_claims.eager")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.CRITICAL)

        logger.debug(f"discarded: {Counted()}")

        assert formatted["n"] == 1, "the f-string is built before logging sees it"

    def test_percent_style_defers_the_work(self) -> None:
        formatted = {"n": 0}

        class Counted:
            def __str__(self) -> str:
                formatted["n"] += 1
                return "value"

        logger = logging.getLogger("test_stdlib_claims.lazy")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.CRITICAL)

        logger.debug("discarded: %s", Counted())

        assert formatted["n"] == 0, "%-style formatting only happens if it is emitted"


class TestMultiprocessingChunkingCopies:
    """docs/stdlib/multiprocessing.md: chunking the data holds a second copy.

    Only the chunking is tested; the pickling and IPC claims need spawned
    processes and are out of scope for a unit test.
    """

    def test_chunks_are_new_lists(self) -> None:
        data = list(range(1_000))
        chunk_size = len(data) // 4
        chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

        assert sum(len(chunk) for chunk in chunks) == len(data)
        assert all(chunk is not data for chunk in chunks)
        chunks[0][0] = -1
        assert data[0] == 0, "the chunk is a copy, so the original is untouched"


class TestNumbersAbcCaching:
    """docs/stdlib/numbers.md: isinstance() against an ABC caches per
    (class, ABC) pair, so the first check on a type costs more."""

    def test_first_check_on_a_class_costs_more_than_the_rest(self) -> None:
        firsts: list[float] = []
        laters: list[float] = []
        for index in range(200):
            fresh = type(f"Probe{index}", (), {})
            instance = fresh()

            start = time.perf_counter()
            isinstance(instance, numbers.Number)
            firsts.append(time.perf_counter() - start)

            start = time.perf_counter()
            isinstance(instance, numbers.Number)
            laters.append(time.perf_counter() - start)

        first = sorted(firsts)[len(firsts) // 2]
        later = sorted(laters)[len(laters) // 2]
        assert first > later * 2, (
            f"the negative result should be cached after the first check: "
            f"first={first:.2e}s later={later:.2e}s"
        )

    def test_the_answer_is_the_same_either_way(self) -> None:
        assert isinstance(42, numbers.Integral)
        assert isinstance(3.5, numbers.Real)
        assert not isinstance("42", numbers.Number)


class TestPosixpathIsPureStringWork:
    """docs/stdlib/posixpath.md: join and normpath are string operations with
    no filesystem access."""

    def test_paths_that_do_not_exist_are_handled_fine(self) -> None:
        assert posixpath.join("/nowhere", "a", "b") == "/nowhere/a/b"
        assert posixpath.normpath("/nowhere/../a//b") == "/a/b"

    def test_cost_follows_the_string_length(self) -> None:
        short = "/".join(["seg"] * 10)
        long = "/".join(["seg"] * 5_000)

        short_time = best_time(lambda: posixpath.normpath(short))
        long_time = best_time(lambda: posixpath.normpath(long))

        assert long_time > short_time * 10, (
            f"normpath is linear in the path: {short_time:.2e}s vs {long_time:.2e}s"
        )


class TestPprintSortingCost:
    """docs/stdlib/pprint.md: constructing a printer is O(1); sort_dicts adds
    O(k log k) per dict printed."""

    def test_constructing_a_printer_is_trivial(self) -> None:
        printer_time = best_time(lambda: pprint.PrettyPrinter(indent=4, width=100))
        data = {f"k{i}": i for i in range(2_000)}
        format_time = best_time(lambda: pprint.pformat(data))

        assert printer_time * 100 < format_time, (
            f"the constructor stores settings, it does no formatting: "
            f"construct={printer_time:.2e}s format={format_time:.2e}s"
        )

    def test_sorting_keys_costs_extra(self) -> None:
        data = {f"key{i:05d}": i for i in range(3_000)}

        sorted_time = best_time(lambda: pprint.pformat(data, sort_dicts=True))
        unsorted_time = best_time(lambda: pprint.pformat(data, sort_dicts=False))

        assert sorted_time > unsorted_time, (
            f"sort_dicts adds a sort per dict: sorted={sorted_time:.2e}s "
            f"unsorted={unsorted_time:.2e}s"
        )


class TestPyexpatStreams:
    """docs/stdlib/pyexpat.md: handlers fire as elements close, so no
    document tree is built."""

    def test_handlers_fire_during_parsing(self) -> None:
        import pyexpat

        seen: list[str] = []
        parser = pyexpat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: seen.append(name)
        parser.Parse("<root><a/><b/></root>", True)

        assert seen == ["root", "a", "b"]

    def test_parsing_scales_with_the_input(self) -> None:
        import pyexpat

        def parse(count: int) -> None:
            parser = pyexpat.ParserCreate()
            parser.StartElementHandler = lambda name, attrs: None
            parser.Parse("<root>" + "<i/>" * count + "</root>", True)

        small = best_time(lambda: parse(1_000))
        large = best_time(lambda: parse(20_000))

        assert large > small * 5, f"O(n) in input size: {small:.2e}s vs {large:.2e}s"


class TestSecretsLengthIsTheOnlyLever:
    """docs/stdlib/secrets.md: token generation is linear in the bytes asked
    for, and that is the only thing that moves the cost."""

    def test_cost_follows_the_requested_size(self) -> None:
        import secrets

        small = best_time(lambda: secrets.token_hex(16))
        large = best_time(lambda: secrets.token_hex(16_384))

        assert large > small * 5, f"linear in bytes requested: {small:.2e}s vs {large:.2e}s"

    def test_output_length_is_what_was_asked_for(self) -> None:
        import secrets

        assert len(secrets.token_bytes(32)) == 32
        assert len(secrets.token_hex(32)) == 64


class TestSqliteCommitBatching:
    """docs/stdlib/sqlite3.md: the durability cost is paid per transaction,
    which is why batching beats committing each insert."""

    def test_one_commit_beats_one_commit_per_row(self) -> None:
        def run(commit_each: bool) -> float:
            connection = sqlite3.connect(":memory:")
            connection.execute("CREATE TABLE t (a)")
            start = time.perf_counter()
            for value in range(2_000):
                connection.execute("INSERT INTO t VALUES (?)", (value,))
                if commit_each:
                    connection.commit()
            if not commit_each:
                connection.commit()
            elapsed = time.perf_counter() - start
            connection.close()
            return elapsed

        batched = min(run(False) for _ in range(3))
        per_row = min(run(True) for _ in range(3))

        assert per_row > batched, (
            f"a commit per row pays the transaction cost 2000 times: "
            f"batched={batched:.2e}s per_row={per_row:.2e}s"
        )


class TestStructFormatCaching:
    """docs/stdlib/struct.md, as corrected by this test.

    The page claimed pre-compiling a Struct saves parsing the format "on
    every call". It does not: the module-level functions cache compiled
    formats, so a repeated format is parsed once anyway. Pre-compiling saves
    the cache lookup, and saves the parse only when the cache misses.
    """

    FORMAT = "iiii"

    def test_precompiled_saves_only_the_cache_lookup(self) -> None:
        compiled = struct.Struct(self.FORMAT)
        data = compiled.pack(1, 2, 3, 4)

        module_time = best_time(lambda: [struct.unpack(self.FORMAT, data) for _ in range(20_000)])
        struct_time = best_time(lambda: [compiled.unpack(data) for _ in range(20_000)])

        assert struct_time < module_time, "pre-compiling should still win"
        assert struct_time > module_time / 3, (
            f"but only by the cache lookup, not by a whole parse: "
            f"module={module_time:.2e}s struct={struct_time:.2e}s"
        )

    def test_the_parse_is_only_re_paid_on_a_cache_miss(self) -> None:
        formats = ["i" * n for n in range(2, 60)]
        payloads = {f: struct.pack(f, *range(len(f))) for f in formats}
        compiled = [struct.Struct(f) for f in formats]

        def cold() -> None:
            struct._clearcache()  # type: ignore[attr-defined]
            for fmt in formats:
                struct.unpack(fmt, payloads[fmt])

        def warm() -> None:
            for fmt, prepared in zip(formats, compiled, strict=True):
                prepared.unpack(payloads[fmt])

        cold_time = best_time(cold)
        warm_time = best_time(warm)

        assert cold_time > warm_time * 2, (
            f"with the cache cleared the parse dominates: "
            f"cold={cold_time:.2e}s warm={warm_time:.2e}s"
        )

    def test_a_short_read_fails_before_unpacking(self) -> None:
        with pytest.raises(struct.error):
            struct.unpack("i", b"AB")


class TestTempfileCachesTheDirectory:
    """docs/stdlib/tempfile.md: gettempdir() is O(1) after the first call,
    because it caches the search it had to do."""

    def test_the_first_lookup_is_the_expensive_one(self) -> None:
        saved = tempfile.tempdir
        try:
            tempfile.tempdir = None
            start = time.perf_counter()
            tempfile.gettempdir()
            first = time.perf_counter() - start

            start = time.perf_counter()
            tempfile.gettempdir()
            cached = time.perf_counter() - start
        finally:
            tempfile.tempdir = saved

        assert first > cached * 5, (
            f"the search result is cached: first={first:.2e}s cached={cached:.2e}s"
        )

    def test_temporary_directory_cleans_up_every_file(self, tmp_path: Path) -> None:
        with tempfile.TemporaryDirectory(dir=str(tmp_path)) as name:
            directory = Path(name)
            for index in range(10):
                (directory / f"chunk{index}").write_text("x", encoding="utf-8")
            assert len(list(directory.iterdir())) == 10
        assert not directory.exists(), "cleanup is O(k) in the files created"


class TestTomllibNestingIsNotFree:
    """docs/stdlib/tomllib.md, as corrected by this test.

    The page claimed nesting costs no more per character than a flat key.
    Each table header creates and installs a dict, so the same number of keys
    spread over tables costs about twice as much.
    """

    KEYS = 2_000

    def test_tables_cost_more_than_flat_keys(self) -> None:
        flat = "\n".join(f"k{i} = {i}" for i in range(self.KEYS))
        nested = "\n".join(f"[t{i}]\nk = {i}" for i in range(self.KEYS))

        flat_time = best_time(lambda: tomllib.loads(flat))
        nested_time = best_time(lambda: tomllib.loads(nested))

        assert nested_time > flat_time * 1.3, (
            f"a table per key is not free: flat={flat_time:.2e}s nested={nested_time:.2e}s"
        )

    def test_parsing_scales_with_the_text(self) -> None:
        small = "\n".join(f"k{i} = {i}" for i in range(500))
        large = "\n".join(f"k{i} = {i}" for i in range(5_000))

        small_time = best_time(lambda: tomllib.loads(small))
        large_time = best_time(lambda: tomllib.loads(large))

        assert large_time > small_time * 5, (
            f"O(n) in the text: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestUnicodeDataLookupsAreTableReads:
    """docs/stdlib/unicodedata.md: the per-character properties are O(1)
    table reads, and an ASCII string answers is_normalized from a flag."""

    def test_property_lookups_do_not_depend_on_the_code_point(self) -> None:
        low = best_time(lambda: [unicodedata.category("a") for _ in range(20_000)])
        high = best_time(lambda: [unicodedata.category("\U0001f600") for _ in range(20_000)])

        ratio = max(low, high) / min(low, high)
        assert ratio < 3.0, f"both are table reads: ascii={low:.2e}s astral={high:.2e}s"

    def test_ascii_is_normalized_answers_from_a_flag(self) -> None:
        ascii_text = "a" * 200_000
        accented = "é" * 200_000

        ascii_time = best_time(lambda: unicodedata.is_normalized("NFC", ascii_text))
        accented_time = best_time(lambda: unicodedata.is_normalized("NFC", accented))

        assert accented_time > ascii_time * 10, (
            f"ASCII short-circuits, other text is scanned: "
            f"ascii={ascii_time:.2e}s accented={accented_time:.2e}s"
        )

    def test_normalization_still_agrees_with_the_check(self) -> None:
        decomposed = "café"
        assert not unicodedata.is_normalized("NFC", decomposed)
        assert unicodedata.is_normalized("NFC", unicodedata.normalize("NFC", decomposed))

    def test_an_already_normalized_string_is_returned_unchanged(self) -> None:
        # The page claimed normalize() allocates a new string. It does not
        # when there is nothing to do - the O(n) space is the worst case.
        ascii_text = "cafe"
        composed = unicodedata.normalize("NFC", "cafe\u0301")

        assert unicodedata.normalize("NFC", ascii_text) is ascii_text
        assert unicodedata.normalize("NFC", composed) is composed

    def test_a_string_needing_work_does_allocate(self) -> None:
        decomposed = "cafe\u0301"
        result = unicodedata.normalize("NFC", decomposed)

        assert result is not decomposed
        assert result != decomposed


class TestIoStringBuilding:
    """docs/stdlib/io.md: StringIO accumulation is linear."""

    def test_stringio_accumulation_is_linear(self) -> None:
        def build(rows: int) -> str:
            buffer = io.StringIO()
            for index in range(rows):
                buffer.write(f"row {index}\n")
            return buffer.getvalue()

        small = best_time(lambda: build(2_000))
        large = best_time(lambda: build(20_000))

        assert large < small * 30, (
            f"writes are amortized, so ten times the rows should be about ten "
            f"times the work: {small:.2e}s vs {large:.2e}s"
        )


class TestBisectKeyListDominates:
    """docs/stdlib/bisect.md's key-list warning, checked against sorting.

    Kept here rather than in test_bisect_complexity.py because it is a claim
    about the surrounding code, not about bisect.
    """

    def test_sorting_once_beats_rebuilding_keys_per_search(self) -> None:
        size = 50_000
        data = [(str(i), i) for i in range(size)]
        keys = [item[1] for item in data]

        rebuild = best_time(lambda: [item[1] for item in data], repeats=3)
        search = best_time(lambda: bisect.bisect_left(keys, size // 2))

        assert rebuild > search * 100, (
            f"the O(n) rebuild dwarfs the O(log n) search it precedes: "
            f"rebuild={rebuild:.2e}s search={search:.2e}s"
        )
