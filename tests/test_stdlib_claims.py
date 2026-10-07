"""Tests for the claims added to the stdlib pages that go beyond the tables.

The companion to tests/test_builtin_claims.py, organised one class per
module. What is here is the explanatory half of each page - the sentences
asserting something the complexity table does not - since that is where this
repo's claims have actually been wrong.

Several are settled by observation rather than timing, which is the better
kind of test: `filecmp.dircmp` accepting a directory that does not exist
proves it reads nothing at construction, and no tolerance is involved.

docs/stdlib/array.md's claims live in tests/test_array_complexity.py,
docs/stdlib/decimal.md's in tests/test_decimal_complexity.py,
docs/stdlib/fnmatch.md's in tests/test_fnmatch_complexity.py,
docs/stdlib/multiprocessing.md's in tests/test_multiprocessing_complexity.py,
docs/stdlib/numbers.md's in tests/test_numbers_complexity.py,
docs/stdlib/secrets.md's in tests/test_secrets_complexity.py,
docs/stdlib/tempfile.md's in tests/test_tempfile_complexity.py,
docs/stdlib/smtplib.md's in tests/test_smtplib_complexity.py,
docs/stdlib/struct.md's in tests/test_struct_complexity.py and
docs/stdlib/tomllib.md's in tests/test_tomllib_complexity.py, which cover
those modules' tables as well.

Deliberately not covered, because a unit test cannot settle them:

* docs/stdlib/pwd.md - lookup cost is decided by the NSS backend, which may
  be a local file or a network directory
* docs/stdlib/cgi.md, docs/stdlib/cgitb.md - removed in Python 3.13, so a
  test would have to be skipped on any current interpreter
"""

import bisect
import contextlib
import filecmp
import pprint
import queue
import sqlite3
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import cmp_to_key
from pathlib import Path
from typing import Any

import pytest


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


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


class TestPprintSortingCost:
    """docs/stdlib/pprint.md: constructing a printer is O(1); sort_dicts adds
    O(k log k) per dict printed."""

    @pytest.mark.timing
    def test_constructing_a_printer_is_trivial(self) -> None:
        printer_time = best_time(lambda: pprint.PrettyPrinter(indent=4, width=100))
        data = {f"k{i}": i for i in range(2_000)}
        format_time = best_time(lambda: pprint.pformat(data))

        assert printer_time * 100 < format_time, (
            f"the constructor stores settings, it does no formatting: "
            f"construct={printer_time:.2e}s format={format_time:.2e}s"
        )

    @pytest.mark.timing
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

    @pytest.mark.timing
    def test_parsing_scales_with_the_input(self) -> None:
        import pyexpat

        def parse(count: int) -> None:
            parser = pyexpat.ParserCreate()
            parser.StartElementHandler = lambda name, attrs: None
            parser.Parse("<root>" + "<i/>" * count + "</root>", True)

        small = best_time(lambda: parse(1_000))
        large = best_time(lambda: parse(20_000))

        assert large > small * 5, f"O(n) in input size: {small:.2e}s vs {large:.2e}s"


class TestSqliteCommitBatching:
    """docs/stdlib/sqlite3.md: a commit is where a file database waits for the
    disk, so a commit per row pays that wait per row.

    100 inserts into a file database under tmp_path with the default
    synchronous setting: one commit per row against one commit for the batch.
    More than 10x is asserted; the dev box measured about 400x at 300 rows.
    Only the default journal mode is measured, not WAL or synchronous=OFF, and
    the ratio assumes tmp_path is on a disk-backed filesystem: on a
    memory-backed one a sync costs next to nothing.
    """

    @pytest.mark.timing
    def test_one_commit_beats_one_commit_per_row(self, tmp_path: Path) -> None:
        def run(commit_each: bool, attempt: int) -> float:
            path = tmp_path / f"{commit_each}-{attempt}.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE t (a)")
            connection.commit()
            start = time.perf_counter()
            for value in range(100):
                connection.execute("INSERT INTO t VALUES (?)", (value,))
                if commit_each:
                    connection.commit()
            connection.commit()
            elapsed = time.perf_counter() - start
            connection.close()
            return elapsed

        batched = min(run(False, attempt) for attempt in range(3))
        per_row = min(run(True, attempt) for attempt in range(3))

        assert per_row > batched * 10, (
            f"a commit per row should wait for the disk 100 times: "
            f"batched={batched:.2e}s per_row={per_row:.2e}s"
        )


class TestBisectKeyListDominates:
    """docs/stdlib/bisect.md's key-list warning, checked against sorting.

    Kept here rather than in test_bisect_complexity.py because it is a claim
    about the surrounding code, not about bisect.
    """

    @pytest.mark.timing
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


class TestQueueVersusDeque:
    """docs/stdlib/queue.md: each deque append or pop is atomic on its own;
    what queue.Queue adds is waiting.

    Eight threads appending 5,000 items each never lose or duplicate one, and
    eight threads draining with popleft() hand every item to exactly one of
    them. A Queue's get() waits for an item and a bounded put() waits for
    room, each observed as a thread still blocked a tenth of a second later
    and released by the other side, where popleft() on an empty deque raises
    at once. The page's
    check-then-pop race (`if d: d.popleft()`) is shown with a worker paused
    between the two steps while another thread drains the deque.
    """

    THREADS = 8
    PER_THREAD = 5_000

    def _run(self, target: Callable[[int], None]) -> None:
        threads = [threading.Thread(target=target, args=(tag,)) for tag in range(self.THREADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def test_concurrent_appends_lose_nothing(self) -> None:
        d: deque[tuple[int, int]] = deque()

        def produce(tag: int) -> None:
            for index in range(self.PER_THREAD):
                d.append((tag, index))

        self._run(produce)

        assert len(d) == self.THREADS * self.PER_THREAD
        assert len(set(d)) == len(d), "no item was appended twice"

    def test_concurrent_pops_hand_each_item_to_one_thread(self) -> None:
        total = self.THREADS * self.PER_THREAD
        d: deque[int] = deque(range(total))
        taken: list[list[int]] = [[] for _ in range(self.THREADS)]

        def consume(tag: int) -> None:
            bucket = taken[tag]
            while True:
                try:
                    bucket.append(d.popleft())
                except IndexError:
                    return

        self._run(consume)

        assert not d
        assert sorted(item for bucket in taken for item in bucket) == list(range(total))

    def test_a_check_then_pop_can_race(self) -> None:
        d: deque[int] = deque([1])
        checked = threading.Event()
        drained = threading.Event()
        outcome: list[object] = []

        def check_then_pop() -> None:
            if d:
                checked.set()
                drained.wait(5)
                try:
                    outcome.append(d.popleft())
                except IndexError as error:
                    outcome.append(error)

        worker = threading.Thread(target=check_then_pop, daemon=True)
        worker.start()
        try:
            assert checked.wait(5)
            d.popleft()
        finally:
            drained.set()
            worker.join(5)

        assert len(outcome) == 1 and isinstance(outcome[0], IndexError)

    def test_get_and_a_bounded_put_wait_where_popleft_raises(self) -> None:
        d: deque[str] = deque()
        with pytest.raises(IndexError):
            d.popleft()

        q: queue.Queue[str] = queue.Queue(maxsize=1)
        received: list[str] = []
        entered = threading.Event()
        got = threading.Event()

        def consume() -> None:
            entered.set()
            received.append(q.get())
            got.set()

        consumer = threading.Thread(target=consume, daemon=True)
        consumer.start()
        try:
            assert entered.wait(5)
            assert not got.wait(0.1), "get() on an empty queue is still waiting"
            q.put("late")
            assert got.wait(5) and received == ["late"], "and returns once an item arrives"
        finally:
            with contextlib.suppress(queue.Full):
                q.put_nowait("late")
            consumer.join(5)

        q = queue.Queue(maxsize=1)
        q.put("full")
        entered.clear()
        stored = threading.Event()

        def produce() -> None:
            entered.set()
            q.put("no room")
            stored.set()

        producer = threading.Thread(target=produce, daemon=True)
        producer.start()
        try:
            assert entered.wait(5)
            assert not stored.wait(0.1), "put() on a full bounded queue is still waiting"
            assert q.get() == "full"
            assert stored.wait(5) and q.get() == "no room", "and stores once there is room"
        finally:
            with contextlib.suppress(queue.Empty):
                q.get_nowait()
            producer.join(5)
