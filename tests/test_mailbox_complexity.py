"""Tests for docs/stdlib/mailbox.md.

The page prices five formats by where they keep a message. The single-file
formats (`mbox`, `MMDF`, `Babyl`) scan the file once per open and then work
from byte offsets; the directory formats (`Maildir`, `MH`) work from
filenames and go back to the directory when they need keys. Laziness, file
rewrites and directory listings are settled by direct observation - a
counting `os.listdir`, an inode, a message appended by a second writer -
which needs no tolerance. Allocation separates a file window from a copy, and
timing is used only where two costs differ by a size variable that allocation
does not expose.

Measurement scope:

* `mailbox.mbox()` is asserted not to have fixed the file's contents at
  construction: a message appended after the object exists is counted by the
  first `len()`, which a scan taken at construction could not have done. A
  scan whose result was then discarded would pass too, so this separates the
  scan from the constructor rather than proving the constructor reads nothing. A second append
  after that is not counted, so the offsets are kept. The
  scan tracks the file: 10x the file (200 against 2,000 messages of about 366
  bytes) costs between 5x and 25x, which excludes a constant scan and a
  quadratic one without separating linear from n log n. The memory still held
  after the scan grows more than 5x, which is the per-message offset pair.
* `mbox.get_file()` peaks under 10,000 bytes on a 200,000-byte message and
  changes by less than 2x against a 1,000-byte one, so it is a window;
  reading it returns the whole message. `Maildir.get_file()` and
  `MH.get_file()` are held to the same 2x across the same pair, over a fixed
  read buffer. `Babyl.get_file()` peaks above the message size on the same
  input, so it is a copy. `get_bytes()` peaks above the message size on all
  five formats.
* `mbox.__setitem__()` is asserted to grow the file by the replacement while
  the superseded copy is still there, and the next `flush()` to shrink it
  again, which is the O(m) the row prices against `remove()`'s O(1).
  `Maildir.__setitem__()` is asserted to cost a listing, which is the `e`
  term. A file view taken from an `mbox` is asserted to stop reading once
  the mailbox closes.
* The rewrite's `B` is the survivors, not the file: removing 19 of 20 equal
  messages leaves a file under a tenth of its old size. A refused flush is
  asserted to call `_create_temporary()` not at all, so the size check comes
  before the copy rather than being cleaned up after it. Two removals and a
  flush are asserted to leave a replaced file observable only at the flush,
  by collecting the inode at all four points.
* Rewrites are observed by inode. On `mbox`, `add()` then `flush()` leaves
  the file in place; `remove()` then `flush()` replaces it, and the surviving
  keys are unchanged. A mailbox whose file grew between the scan and the
  flush raises `ExternalClashError`.
* Directory listings are counted with a recording `os.listdir`. `Maildir.add()`
  lists nothing and `MH.add()` lists once. `len(maildir)` lists `cur` and
  `new` on every call; after 2.3 seconds of quiet with neither directory
  modified it lists nothing. A cached `Maildir` key is fetched with no
  listing and a missing one costs two. `MH.__contains__` and `MH.get_bytes()`
  list nothing, while `MH.get_message()` and `MH.get_sequences()` list once.
* `Message(email_message)` is a deep copy priced in headers, not payload
  bytes: 10,000x the payload (100 against 1,000,000 characters) costs under
  2x, while 100x the headers (5 against 500) costs over 5x. Constructing from
  bytes parses, so 1,000x the payload costs over 5x there. The copy's header
  list and subparts are asserted independent of the original.
* Flag storage is priced by where it lives. `MaildirMessage.set_flags()`
  leaves the header list empty and `get_flags()` is flat across 2 and 2,000
  headers (under 2x); `mboxMessage.get_flags()` grows more than 10x across
  the same pair, because it reads `Status` and `X-Status` out of the header
  list. Nothing trims those headers to the standard flag letters, so the `f`
  term is asserted directly: 5,000 characters in each of `Status` and
  `X-Status` come back as a 10,000-character string. Writing flags is the
  other way round: 1,000x the headers (10 against 10,000) moves the traced
  peak of `set_flags()` and `add_flag()` by less than 2x each on every
  supported version, while `__delitem__` on the same messages goes from 225
  bytes to over 700,000 - which is the control that makes the flat peaks mean
  something.
  Every setter is asked for a change and the change is asserted, so a setter
  that did nothing could not pass on a flat peak either. `remove_flag()` is
  the exception and is guarded on `sys.version_info`: it asks whether one of
  the two headers is there, and until 3.12 that question built a list of every
  header name, so the same pair grows more than 10x on 3.10 and 3.11 and stays
  under 2x from 3.12. `BabylMessage.update_visible()` is asserted across the
  same boundary, on 5 visible headers against 10 and 10,000 others, with a
  source header changed first so the measured call has something to refresh.
  The flag measurements run on `mboxMessage` and `MMDFMessage` alike. The 3.13 keyed `Maildir`
  flag API is guarded on `sys.version_info`
  and asserted to rename the file; neither reading nor setting the flags
  opens anything, observed through a recording `open`.
* Iterating an `MH` mailbox is asserted to list the folder once per message
  plus once for the keys, while reading the same messages with `get_bytes()`
  lists once in total - the quadratic walk the page steers away from. A
  folder padded with three non-message entries is asserted to yield only its
  three keys, which separates `e` from `n`.
* `MHMessage.get_sequences()`, `BabylMessage.get_labels()` and
  `BabylMessage.get_visible()` each return an object that is not the stored
  one, and mutating the result is asserted not to reach the message.
  `update_visible()` is asserted to add the standard headers present and to
  drop a visible header the message lost.
* `update_visible()` moves with both of its variables: 200x the message's
  other headers at 10 visible ones costs over 5x, and 4x the visible
  headers at 10 others costs over 8x, which linear growth in the visible
  set could not reach. With nothing visible at all, 200x the headers still
  costs over 5x, which is the standalone H term - the six standard headers
  are looked for either way. The visible headers sit on the message too, so
  the V measurements move H with V and do not isolate the V² term from V·H.
* `MH.set_sequences()` writes `1-3 5` for the keys 1, 2, 3 and 5, and
  `get_sequences()` expands it again and drops a key whose message was
  removed. A sequence line under 20 bytes naming 400 keys is asserted to come
  back as 400 entries, which is the `q` term standing apart from `S`. `pack()`
  renumbers to close a gap and rewrites the sequences.
* `Babyl` is asserted to store each header twice by counting a distinctive
  header name in the file it wrote, against `mbox` storing it once - and to
  store it only once when handed a `BabylMessage` - a visible set carrying a
  header of its own is asserted absent from the file. All three readers then
  raise `AssertionError` on a stored `BabylMessage` whose body holds no blank
  line, and succeed on the same message stored plain. With a blank line in the
  body the read instead succeeds and returns only what followed it - asserted
  through `get_message()`, `get_bytes()` and `get_file()`, each keeping the
  text after the blank line and losing the text before it.
* A `Maildir` holding two messages and five dotted entries in `cur` is
  asserted to have length two from 3.13, which is the second version note and
  `e` exceeding `n` on that format.
* `values()` peaks more than 10x a walk of the same 2,000-message mailbox
  that keeps neither the messages nor any result, which is the difference
  between holding one message and holding all of them. `get_string()` is asserted to round-trip to the same text as
  `get_bytes()`.
* The exceptions are raised on their documented paths: `NoSuchMailboxError`
  from `create=False`, `NotEmptyError` from `remove_folder()` on a folder
  holding mail, `ExternalClashError` from a second dot lock and from a
  resized mailbox, and `FormatError` from an unparsable sequence line. Each
  is asserted to be a `mailbox.Error`.
* Every test that asserts on traced allocation carries the `serial` marker, so
  it runs with no xdist workers: a worker's communication thread allocates
  while `tracemalloc` is active and would show up in these peaks.
* Every fenced Python block runs in its own subprocess and working directory,
  so the temporary mailboxes one block makes cannot reach another, and a
  mutated assertion in one of them is asserted to fail.

Where the bounds stop, and why:

* The scan's O(n) space is what it retains - the offset pair per message -
  measured as memory still held once the scan returns. Its peak includes a
  readline buffer that no size variable here covers, which is why those cells
  and the `.mh_sequences` ones say *retained*.
* `flush()`'s `n log n` is `sorted()`'s bound on the surviving keys. They do
  reach it already increasing, which CPython's sort walks in linear time, but
  nothing in the module promises that ordering and `B` dominates either way.
* `set_flags()` and `add_flag()` hold their `O(f)` auxiliary space on every
  supported version: they go through `replace_header()` and `add_header()`,
  which assign in place and append. The call that rebuilds the header list is
  `__delitem__`, which flag writing never reaches - `_explain_to()` does,
  during conversion. `remove_flag()` is `O(f)` only from 3.12, because it
  first asks whether one of the two headers is there, and before 3.12 that
  question built a list of every header name. `update_visible()` asks the same
  question and carries the same boundary.
* `q log q` bounds the per-sequence sorting, `Σ qᵢ log qᵢ`, from above. The
  names `get_message()` attaches are the separate L² term on that row: each
  goes through `add_sequence()`, which scans what the message already has.
  Counting those comparisons gives exactly 45 for 10 names and 780 for 40,
  the triangular numbers, and `get_message()` is asserted to attach against
  lists of length 0, 1, ... K-1, which is the same scan. A whole-call
  measurement hides it - 10x the sequences holding a key, 20 against 200,
  costs 5.2x - because the folder listing and the sequence file dominate at
  those sizes. `_dump_sequences()`'s K·L is the same shape on the write path,
  read from Lib/mailbox.py rather than counted.
* `set_sequences()`'s standalone `K` is asserted by a mapping of 50 empty
  names beside one that keeps a key. Each key list counts the length check
  that decides whether to skip it, so all 51 are observed being looked at,
  and only the one holding a key reaches the file. A line padded with 200,000
  spaces between a short name and one key is asserted to yield the same mapping
  as the compact form, which is the length the *retained* cells leave out. Each list carries its own
  counter, so a name skipped entirely cannot hide behind another checked twice.

Cost model:

* A sequence name costs O(1) to carry, compare and write, so `K` counts names
  and no bound here is in their bytes. A folder full of kilobyte-long sequence
  names is outside every `MH` bound on the page.
* A space cell marked *retained* is what the call still holds when it returns.
  Every line-oriented scan here peaks a line higher: the single-file tables of
  contents, and `.mh_sequences`, where one line may carry unbounded whitespace
  between a short name and a single key.

Not settled here:

* Contention with another operating-system process. `lock()` is exercised
  through its dot lock, which two objects in this process do contend for, but
  the `lockf` range lock is per-process and no second process is started, so
  the behaviour of `mbox.lock()` against a concurrent reader is not observed.
  Neither is what `_sync_flush()` costs: `fsync` timing is a property of the
  filesystem, not of this module.
* `Maildir.colon` on a filesystem that forbids `':'`. The separator is
  asserted to reach the filename, but no such filesystem exists on the
  platforms this suite runs on.
* Whether `ExternalClashError` from `Maildir.add()` - a name clash in `tmp` -
  can be reached without racing a second writer. It is not provoked here.
* The measurements hold message shape fixed except where a dimension is the
  subject: single-part messages with ASCII bodies, no attachments and no
  transfer encoding. Header *length*, part count, and non-ASCII payloads are
  not varied, and the deep-copy bound's `parts` term is asserted only for
  independence, not for its cost.
* `e` and `n` are separated by observation only - a padded `MH` folder, and a
  `Maildir` with dotted entries from 3.13. Nothing varies `e` against `n` at a
  scale where the two terms could be told apart by cost.
* `MMDF` and `Babyl` inherit the single-file rows from `mbox`, and only
  `get_bytes()` and the `Babyl` specifics are exercised on them directly.
  The scan, the rewrite and the clash check are measured on `mbox` alone.
* That the rewrite never *reads* the removed bytes, only that it does not
  write them. The seek-per-surviving-key loop is read from Lib/mailbox.py.
* `T` against `H`. Every measured message is single-part, so nothing varies a
  subpart's headers against the containing message's, and the two header
  counts are never told apart by cost.
* `MH` iteration is measured with an empty sequence file, so the listing
  frequency is established but the per-message sequence expansion is not.
* The `Maildir` listing counts are taken against the real clock: the
  two-listing assertions rely on staying inside the refresh window and the
  reuse test sleeps past it. Neither branch is driven by a controlled clock.
* `pop()` and `popitem()` through a configured factory. The factory row is
  exercised on `mailbox[key]` alone, so the removal pair is measured with the
  default one.
"""

from __future__ import annotations

import mailbox
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

import pytest

# A mailbox object is annotated `Any` where typeshed and the runtime disagree:
# every format but `Maildir` keys its messages by integer while `Mailbox` is
# stubbed with `str` keys, and the keyed `Maildir` flag API arrived in 3.13,
# after the 3.10 signatures this file is checked against.
PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "mailbox.md"
EXPECTED_BLOCKS = 17


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def retained_bytes(func: Callable[[], Any]) -> int:
    """Traced allocation still held when func returns."""
    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        func()
        return tracemalloc.get_traced_memory()[0] - before
    finally:
        tracemalloc.stop()


def message(subject: str = "s", body: str = "body", headers: int = 0) -> EmailMessage:
    """A single-part message with an ASCII body."""
    built = EmailMessage()
    built["Subject"] = subject
    for index in range(headers):
        built[f"X-Trace-{index}"] = "v"
    built.set_content(body)
    return built


class CountingName(str):
    """A sequence name that records the equality checks made against it."""

    calls = 0

    def __eq__(self, other: object) -> bool:
        type(self).calls += 1
        return str.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    __hash__ = str.__hash__


class CountingKeyList(list[int]):
    """A sequence's key list that records the length checks made on it."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.checks = 0

    def __len__(self) -> int:
        self.checks += 1
        return super().__len__()


class ListdirRecorder:
    """Records the directories `os.listdir` was called on."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.paths: list[Any] = []
        real = os.listdir

        def recording(path: Any = ".") -> Any:
            self.paths.append(path)
            return real(path)

        monkeypatch.setattr(os, "listdir", recording)

    def count(self) -> int:
        return len(self.paths)

    def clear(self) -> None:
        self.paths.clear()


def filled_mbox(path: pathlib.Path, count: int, body: str = "x" * 200) -> None:
    """Write `count` messages to a fresh mbox at `path` and close it."""
    box: Any = mailbox.mbox(str(path))
    for index in range(count):
        box.add(message(f"s{index}", body))
    box.close()


class TestTheScanIsLazyAndKept:
    """`mailbox.mbox(...)` | O(1) | O(1), then O(F) time and O(n) space on the
    first keyed operation.

    Laziness is settled by appending to the file after the mailbox object
    exists: a scan at construction could not have seen that message, and a
    scan repeated per call would see the next one. That separates the scan
    from the constructor; it does not establish that the constructor reads
    no bytes at all, only that it does not fix the contents.
    """

    LATE = b"From sender\nSubject: late\n\nbody\n\n"

    def test_construction_does_not_scan_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 4)

        box: Any = mailbox.mbox(str(path))
        with open(path, "ab") as appended:
            appended.write(self.LATE)

        assert len(box) == 5, "the first len() did not see a message appended after the open"
        box.close()

    def test_the_offsets_are_kept_after_the_scan(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 4)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 4
        with open(path, "ab") as appended:
            appended.write(self.LATE)

        assert len(box) == 4, "a second len() re-read the file"
        box.close()

    @pytest.mark.serial
    def test_the_scan_retains_memory_per_message(self, tmp_path: pathlib.Path) -> None:
        small, large = tmp_path / "small.mbox", tmp_path / "large.mbox"
        filled_mbox(small, 200)
        filled_mbox(large, 2_000)

        held = []
        for path in (small, large):
            box: Any = mailbox.mbox(str(path))
            held.append(retained_bytes(lambda box=box: len(box)))
            box.close()

        ratio = held[1] / held[0]
        assert ratio > 5, f"10x the messages retained only {ratio:.1f}x after the scan"

    @pytest.mark.timing
    def test_the_scan_tracks_the_file(self, tmp_path: pathlib.Path) -> None:
        """A 10x file costing 5-25x excludes a constant scan and a quadratic
        one. It does not separate linear from n log n; that the scan is one
        pass over the lines is read from Lib/mailbox.py."""
        small, large = tmp_path / "small.mbox", tmp_path / "large.mbox"
        filled_mbox(small, 200)
        filled_mbox(large, 2_000)
        assert os.path.getsize(large) > 9 * os.path.getsize(small)

        def scan(path: pathlib.Path) -> None:
            box: Any = mailbox.mbox(str(path))
            len(box)
            box.close()

        ratio = best_ns(lambda: scan(large)) / best_ns(lambda: scan(small))
        assert 5 < ratio < 25, f"10x the file cost {ratio:.1f}x"


@pytest.mark.serial
class TestFileViewsAndCopies:
    """`mbox.get_file()` | O(1) | O(1) - a window on the mailbox file - against
    `Babyl.get_file()` | O(m) | O(m), a copy.

    Traced allocation separates the two with no tolerance: a window cannot
    allocate the message, and a copy cannot avoid it.
    """

    SIZE = 200_000

    def test_an_mbox_file_view_allocates_nothing_message_sized(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "archive.mbox"
        box: Any = mailbox.mbox(str(path))
        box.add(message(body="x" * self.SIZE))
        box.close()

        box = mailbox.mbox(str(path))
        assert len(box) == 1

        peak = peak_bytes(lambda: box.get_file(0))

        assert peak < 10_000, f"mbox.get_file() allocated {peak} bytes for a {self.SIZE}-byte body"
        assert len(box.get_file(0).read()) > self.SIZE, "the view did not yield the message"
        box.close()

    def test_the_mbox_view_does_not_grow_with_the_message(self, tmp_path: pathlib.Path) -> None:
        peaks = []
        for size in (1_000, self.SIZE):
            path = tmp_path / f"archive{size}.mbox"
            box: Any = mailbox.mbox(str(path))
            box.add(message(body="x" * size))
            box.close()

            box = mailbox.mbox(str(path))
            assert len(box) == 1
            peaks.append(peak_bytes(lambda box=box: box.get_file(0)))
            box.close()

        ratio = peaks[1] / peaks[0]
        assert ratio < 2, f"200x the message changed the view's allocation by {ratio:.1f}x"

    def test_a_babyl_file_view_is_a_copy(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.babyl"
        box: Any = mailbox.Babyl(str(path))
        box.add(message(body="x" * self.SIZE))
        box.close()

        box = mailbox.Babyl(str(path))
        assert len(box) == 1

        peak = peak_bytes(lambda: box.get_file(0))

        assert peak > self.SIZE, f"Babyl.get_file() allocated only {peak} bytes"
        box.close()

    def test_directory_format_views_do_not_grow_with_the_message(
        self, tmp_path: pathlib.Path
    ) -> None:
        for name, factory in (("md", mailbox.Maildir), ("mh", mailbox.MH)):
            peaks = []
            for size in (1_000, self.SIZE):
                box: Any = factory(str(tmp_path / f"{name}{size}"))
                key = box.add(message(body="x" * size))
                peaks.append(peak_bytes(lambda box=box, key=key: box.get_file(key).close()))

            ratio = peaks[1] / peaks[0]
            assert ratio < 2, f"{name}: 200x the message changed the view by {ratio:.1f}x"
            assert peaks[1] < self.SIZE, f"{name}: the view allocated {peaks[1]} bytes"

    def test_get_bytes_allocates_the_message_on_every_format(self, tmp_path: pathlib.Path) -> None:
        body = message(body="x" * self.SIZE)

        for name, factory in (
            ("mbox", mailbox.mbox),
            ("MMDF", mailbox.MMDF),
            ("Babyl", mailbox.Babyl),
            ("Maildir", mailbox.Maildir),
            ("MH", mailbox.MH),
        ):
            box: Any = factory(str(tmp_path / name))
            key = box.add(body)
            box.close()

            box = factory(str(tmp_path / name))
            assert len(box) == 1
            peak = peak_bytes(lambda box=box, key=key: box.get_bytes(key))
            assert peak > self.SIZE, f"{name}.get_bytes() allocated only {peak} bytes"
            box.close()


class TestRemovalRewritesTheFile:
    """`mbox.remove()` | O(1), and `mbox.flush()` | O(B + n log n) after one.

    The inode separates an append that leaves the file alone from a rewrite
    that replaces it; a bound stated on `remove()` alone would miss where the
    cost lands.
    """

    def test_adding_then_flushing_leaves_the_file_in_place(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 10)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 10
        inode = os.stat(path).st_ino

        box.add(message("new"))
        box.flush()

        assert os.stat(path).st_ino == inode, "add() then flush() replaced the file"
        box.close()

    def test_removing_then_flushing_replaces_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 10)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 10
        inode = os.stat(path).st_ino

        box.remove(0)
        box.remove(1)
        box.flush()

        assert os.stat(path).st_ino != inode, "remove() then flush() did not rewrite the file"
        assert sorted(box.keys()) == list(range(2, 10))
        box.close()

    def test_the_rewrite_keeps_only_the_survivors(self, tmp_path: pathlib.Path) -> None:
        """The `B` in `O(B + n log n)`, as the rewrite's output.

        The removed bytes are not in the new file. That the copy never reads
        them is read from the seek-per-key loop in Lib/mailbox.py, not
        measured here.
        """
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 20, body="y" * 500)
        full = os.path.getsize(path)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 20
        for key in range(19):
            box.remove(key)
        box.flush()

        assert os.path.getsize(path) < full / 10, "the rewrite kept the removed messages"
        assert len(box) == 1
        box.close()

    def test_a_refused_flush_opens_no_temporary(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The size check comes first: the refusal never reaches the copy.

        Instrumenting the temporary-file helper, rather than looking for
        leftovers afterwards, is what separates "never created" from "created
        and cleaned up".
        """
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 20, body="y" * 500)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 20
        box.remove(0)
        with open(path, "ab") as appended:
            appended.write(b"From someone\nSubject: late\n\nbody\n\n")

        created: list[str] = []
        # The private helper is the only boundary where a created-then-deleted
        # temporary would still be visible.
        real_temporary = mailbox._create_temporary  # type: ignore[attr-defined]

        def recording(for_path: str) -> Any:
            created.append(for_path)
            return real_temporary(for_path)

        monkeypatch.setattr(mailbox, "_create_temporary", recording)

        with pytest.raises(mailbox.ExternalClashError):
            box.flush()

        assert created == [], f"the refused flush opened {created}"

    def test_a_replaced_file_is_observable_only_at_the_flush(self, tmp_path: pathlib.Path) -> None:
        """`remove()` only records the intent, so batching is the whole point."""
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 10)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 10
        inodes = [os.stat(path).st_ino]

        box.remove(0)
        inodes.append(os.stat(path).st_ino)
        box.remove(1)
        inodes.append(os.stat(path).st_ino)
        box.flush()
        inodes.append(os.stat(path).st_ino)

        assert inodes[0] == inodes[1] == inodes[2], "a remove() rewrote the file on its own"
        assert inodes[3] != inodes[2], "the flush did not rewrite"
        assert len(set(inodes)) == 2, (
            f"a replacement was observable at a point other than the flush: {inodes}"
        )
        box.close()

    def test_replacing_a_message_appends_it(self, tmp_path: pathlib.Path) -> None:
        """`__setitem__` is O(m) where `remove()` is O(1): it writes the new copy."""
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 4)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 4
        before = os.path.getsize(path)

        box[0] = message("replaced", "y" * 5_000)

        grew = os.path.getsize(path)
        assert grew > before + 5_000, "the replacement was not appended"
        assert box[0]["Subject"] == "replaced"

        box.flush()
        assert os.path.getsize(path) < grew, "the superseded copy survived the flush"
        assert len(box) == 4
        box.close()

    def test_a_view_stops_reading_when_the_mailbox_closes(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 1)

        box: Any = mailbox.mbox(str(path))
        assert len(box) == 1
        view = box.get_file(0)
        box.close()

        with pytest.raises(ValueError):
            view.read()

    def test_a_resized_mailbox_refuses_the_rewrite(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 2)

        box: Any = mailbox.mbox(str(path))
        box.remove(0)
        with open(path, "ab") as appended:
            appended.write(b"From someone\nSubject: third\n\nbody\n\n")

        with pytest.raises(mailbox.ExternalClashError) as raised:
            box.flush()

        assert "changed" in str(raised.value)


class TestDirectoryListings:
    """`Maildir.add()` | O(m) against `MH.add()` | O(e + n log n + m), and
    `len(maildir)` | O(e) on every call.

    A recording `os.listdir` counts the listings themselves, so the difference
    is exact rather than a ratio that a fast filesystem could blur.
    """

    def test_maildir_add_lists_nothing_and_mh_add_lists_once(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(5):
            maildir.add(message())
            mh.add(message())

        recorder = ListdirRecorder(monkeypatch)
        maildir.add(message())
        maildir_listings = recorder.count()
        recorder.clear()
        mh.add(message())
        mh_listings = recorder.count()

        assert maildir_listings == 0, "Maildir.add() listed a directory"
        assert mh_listings == 1, f"MH.add() made {mh_listings} listings, not one"

    def test_mh_keys_are_one_past_the_highest(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(3):
            mh.add(message())
        mh.remove(2)

        assert mh.add(message()) == 4
        assert sorted(mh.keys()) == [1, 3, 4]

    def test_counting_a_maildir_lists_both_directories_every_call(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        for _ in range(5):
            maildir.add(message())

        recorder = ListdirRecorder(monkeypatch)
        assert len(maildir) == 5
        first = recorder.count()
        recorder.clear()
        assert len(maildir) == 5
        second = recorder.count()

        assert first == 2, f"the first len() made {first} listings, not cur and new"
        assert second == 2, "the second len() reused a cached count"

    @pytest.mark.timing
    def test_a_quiet_unchanged_maildir_reuses_its_listing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The documented shortcut: unchanged directories and a settled clock."""
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        for _ in range(5):
            maildir.add(message())
        assert len(maildir) == 5
        time.sleep(2.3)

        recorder = ListdirRecorder(monkeypatch)
        assert len(maildir) == 5

        assert recorder.count() == 0, "a quiet, unmodified Maildir was listed again"

    def test_a_known_maildir_key_is_fetched_without_a_listing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message("kept"))
        assert key in maildir

        recorder = ListdirRecorder(monkeypatch)
        assert maildir[key]["Subject"] == "kept"
        cached = recorder.count()
        recorder.clear()
        assert maildir.get("absent") is None
        missing = recorder.count()

        assert cached == 0, "a cached key cost a listing"
        assert missing == 2, f"a missing key cost {missing} listings, not a refresh"

    def test_mh_reads_bytes_without_listing_but_labels_a_message_with_one(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        key = mh.add(message("kept"))

        recorder = ListdirRecorder(monkeypatch)
        assert 1 in mh
        contains = recorder.count()
        recorder.clear()
        mh.get_bytes(key)
        bytes_listings = recorder.count()
        recorder.clear()
        mh.get_message(key)
        message_listings = recorder.count()

        assert contains == 0, "MH.__contains__ listed the folder"
        assert bytes_listings == 0, "MH.get_bytes() listed the folder"
        assert message_listings == 1, (
            f"MH.get_message() made {message_listings} listings; the page prices one, "
            "for the sequence lookup"
        )

    def test_replacing_a_maildir_message_costs_a_listing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The `e` term in `Maildir.__setitem__`: the temporary name is not cached."""
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message("first"))
        assert len(maildir) == 1

        recorder = ListdirRecorder(monkeypatch)
        maildir[key] = message("second")

        assert recorder.count() == 2, (
            f"__setitem__ made {recorder.count()} listings; the page prices a refresh"
        )
        assert maildir[key]["Subject"] == "second"

    def test_iteration_skips_a_key_it_can_no_longer_resolve(self, tmp_path: pathlib.Path) -> None:
        """`MH.iterkeys()` is a snapshot, so a message removed mid-walk is skipped."""
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for index in range(3):
            mh.add(message(f"s{index}"))

        walk = mh.itervalues()
        first = next(walk)
        mh.remove(2)
        rest = [stored["Subject"] for stored in walk]

        assert first["Subject"] == "s0"
        assert rest == ["s2"], f"the removed key was not skipped: {rest}"

    def test_iterating_an_mh_mailbox_relists_per_message(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Why the page sends a loop to `get_bytes()`: `get_message()` labels."""
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for index in range(6):
            mh.add(message(f"s{index}"))

        recorder = ListdirRecorder(monkeypatch)
        assert len(list(mh.itervalues())) == 6
        walking = recorder.count()
        recorder.clear()
        assert len([mh.get_bytes(key) for key in mh.iterkeys()]) == 6
        reading = recorder.count()

        assert walking == 7, f"iterating made {walking} listings, not one per message plus the keys"
        assert reading == 1, f"reading the bytes made {reading} listings"

    def test_non_message_entries_do_not_become_keys(self, tmp_path: pathlib.Path) -> None:
        """`e` is entries and `n` is messages: the folder holds both."""
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(3):
            mh.add(message())
        for name in ("notes.txt", "12x", ".hidden"):
            (tmp_path / "mh" / name).touch()

        assert len(os.listdir(tmp_path / "mh")) == 7
        assert list(mh.iterkeys()) == [1, 2, 3]
        assert len(mh) == 3
        assert mh.add(message()) == 4

    @pytest.mark.skipif(
        sys.version_info < (3, 13), reason="Maildir ignores dotted entries from 3.13"
    )
    def test_dotted_entries_are_not_counted_as_messages(self, tmp_path: pathlib.Path) -> None:
        """The second version note, and `e` exceeding `n` on a Maildir."""
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        for _ in range(2):
            maildir.add(message())
        for index in range(5):
            (tmp_path / "md" / "cur" / f".editor-swap-{index}").touch()

        assert len(os.listdir(tmp_path / "md" / "cur")) == 5
        assert len(maildir) == 2
        assert len(list(maildir.iterkeys())) == 2

    def test_mh_keys_come_back_sorted(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(12):
            mh.add(message())

        assert list(mh.iterkeys()) == sorted(mh.keys())
        assert list(mh.iterkeys()) == list(range(1, 13))


class TestMessageConstruction:
    """`mailbox.Message(message=None)` | O(T + p) from a message, O(m) otherwise.

    The two bounds are separated by varying payload bytes against header
    count: a copy priced in bytes would move with the payload, and a parse
    priced in headers would not move with it.
    """

    @staticmethod
    def source(headers: int, payload: int) -> EmailMessage:
        return message(body="b" * payload, headers=headers)

    def test_the_copy_is_independent_of_the_original(self) -> None:
        original = message("hello")

        copied = mailbox.mboxMessage(original)
        copied["X-Added"] = "yes"

        assert copied["Subject"] == "hello"
        assert "X-Added" not in original, "the copy shares its header list with the original"

    def test_subparts_are_copied_too(self) -> None:
        outer = EmailMessage()
        outer["Subject"] = "outer"
        outer.set_content("first part")
        outer.add_alternative("second part")
        original_part = outer.get_payload(0)
        assert outer.is_multipart()

        copied: Any = mailbox.mboxMessage(outer)
        copied_part = copied.get_payload(0)
        copied_part["X-Added"] = "yes"

        assert copied_part is not original_part, "the copy shares a subpart with the original"
        assert "X-Added" not in original_part, "a header set on the copy reached the original"

    @pytest.mark.timing
    def test_copying_does_not_walk_the_payload(self) -> None:
        small = self.source(headers=5, payload=100)
        large = self.source(headers=5, payload=1_000_000)

        ratio = best_ns(lambda: mailbox.mboxMessage(large), inner=50) / best_ns(
            lambda: mailbox.mboxMessage(small), inner=50
        )

        assert ratio < 2, f"10,000x the payload cost {ratio:.1f}x to copy"

    @pytest.mark.timing
    def test_copying_is_priced_in_headers(self) -> None:
        few = self.source(headers=5, payload=100)
        many = self.source(headers=500, payload=100)

        ratio = best_ns(lambda: mailbox.mboxMessage(many), inner=50) / best_ns(
            lambda: mailbox.mboxMessage(few), inner=50
        )

        assert ratio > 5, f"100x the headers cost only {ratio:.1f}x to copy"

    @pytest.mark.timing
    def test_parsing_does_walk_the_payload(self) -> None:
        small = b"Subject: s\n\n" + b"b" * 100
        large = b"Subject: s\n\n" + b"b" * 100_000

        ratio = best_ns(lambda: mailbox.mboxMessage(large), inner=20) / best_ns(
            lambda: mailbox.mboxMessage(small), inner=20
        )

        assert ratio > 5, f"1,000x the payload cost only {ratio:.1f}x to parse"

    def test_an_empty_message_carries_the_format_defaults(self) -> None:
        maildir_message = mailbox.MaildirMessage()
        assert maildir_message.get_subdir() == "new"
        assert maildir_message.get_flags() == ""
        assert maildir_message.get_date() > 0

        assert mailbox.MHMessage().get_sequences() == []
        assert mailbox.BabylMessage().get_labels() == []
        assert mailbox.mboxMessage().get_from().startswith("MAILER-DAEMON ")

    def test_a_message_that_cannot_be_read_is_rejected(self) -> None:
        with pytest.raises(TypeError):
            mailbox.Message(42)  # type: ignore[arg-type]


class TestWhereFlagsLive:
    """`MaildirMessage.get_flags()` | O(f) against `mboxMessage.get_flags()` |
    O(H + f).

    Maildir keeps flags in the filename and mbox in two headers, so the
    separating observation is that one leaves the header list untouched while
    the other's cost moves with it.
    """

    def test_maildir_flags_never_touch_the_headers(self) -> None:
        maildir_message = mailbox.MaildirMessage()

        maildir_message.set_flags("SR")

        assert maildir_message.get_flags() == "RS", "set_flags() did not sort the flags"
        assert maildir_message.get_flags() is not maildir_message.get_flags(), (
            "get_flags() returned a stored string rather than a fresh slice"
        )
        assert maildir_message.get_info() == "2,RS"
        assert maildir_message.items() == [], "a Maildir flag reached the header list"

    def test_maildir_flag_edits_are_set_operations(self) -> None:
        maildir_message = mailbox.MaildirMessage()
        maildir_message.set_flags("SR")

        maildir_message.add_flag("F")
        assert set(maildir_message.get_flags()) == {"R", "S", "F"}
        maildir_message.add_flag("F")
        assert len(maildir_message.get_flags()) == 3, "add_flag() duplicated a flag"
        maildir_message.remove_flag("R")
        assert set(maildir_message.get_flags()) == {"S", "F"}
        maildir_message.remove_flag("Z")
        assert set(maildir_message.get_flags()) == {"S", "F"}

    def test_mbox_flags_are_two_headers(self) -> None:
        mbox_message = mailbox.mboxMessage()

        mbox_message.set_flags("ROD")

        assert mbox_message["Status"] == "RO"
        assert mbox_message["X-Status"] == "D"
        assert set(mbox_message.get_flags()) == {"R", "O", "D"}

    def test_mmdf_flags_behave_as_mbox_flags(self) -> None:
        mmdf_message = mailbox.MMDFMessage()
        mmdf_message.set_flags("RO")
        mmdf_message.add_flag("F")

        assert mmdf_message["Status"] == "RO"
        assert set(mmdf_message.get_flags()) == {"R", "O", "F"}
        mmdf_message.remove_flag("O")
        assert set(mmdf_message.get_flags()) == {"R", "F"}

    def test_the_from_line_is_stored_whole(self) -> None:
        mbox_message = mailbox.mboxMessage()

        mbox_message.set_from("someone@example.com")
        assert mbox_message.get_from() == "someone@example.com"

        mbox_message.set_from("someone@example.com", time.gmtime(0))
        assert mbox_message.get_from().startswith("someone@example.com ")
        assert "1970" in mbox_message.get_from()

    @pytest.mark.timing
    def test_reading_mbox_flags_costs_the_header_list(self) -> None:
        def mbox_with(headers: int) -> mailbox.mboxMessage:
            built = mailbox.mboxMessage()
            for index in range(headers):
                built[f"X-Trace-{index}"] = "v"
            built.set_flags("RO")
            return built

        few, many = mbox_with(2), mbox_with(2_000)
        ratio = best_ns(few.get_flags, inner=200)
        header_ratio = best_ns(many.get_flags, inner=200) / ratio

        assert header_ratio > 10, f"1,000x the headers cost only {header_ratio:.1f}x"

    def test_mbox_flags_are_whatever_the_headers_hold(self) -> None:
        """The `f` term: nothing trims `Status` to the standard alphabet."""
        mbox_message = mailbox.mboxMessage()
        mbox_message["Status"] = "R" * 5_000
        mbox_message["X-Status"] = "D" * 5_000

        flags = mbox_message.get_flags()

        assert len(flags) == 10_000, f"get_flags() returned {len(flags)} characters"

    @pytest.mark.serial
    @pytest.mark.parametrize(
        "factory", [mailbox.mboxMessage, mailbox.MMDFMessage], ids=["mbox", "MMDF"]
    )
    def test_writing_flags_does_not_rebuild_the_header_list(
        self, factory: Callable[[], Any]
    ) -> None:
        """The `O(f)` space on the flag setters, against the `O(H)` next door.

        `set_flags()` reaches `replace_header()`, which assigns into the header
        list, and `add_header()`, which appends. Neither rebuilds it. The
        control is `__delitem__`, the call that does rebuild, measured on the
        same messages - without it a flat peak could just mean the probe never
        touched the headers.

        `remove_flag()` is the exception, and is guarded: it asks whether one
        of the two headers is there first, and until 3.12 that question built
        a list of every header name.
        """

        def message_with(headers: int) -> Any:
            built = factory()
            for index in range(headers):
                built[f"X-Trace-{index}"] = "v"
            built.set_flags("RO")
            return built

        few, many = message_with(10), message_with(10_000)

        # Each setter is asked for a change, and the change is checked, so a
        # setter that did nothing could not pass on a flat peak.
        setting = [peak_bytes(lambda m=m: m.set_flags("AF")) for m in (few, many)]
        for built in (few, many):
            assert set(built.get_flags()) == {"A", "F"}

        adding = [peak_bytes(lambda m=m: m.add_flag("D")) for m in (few, many)]
        for built in (few, many):
            assert set(built.get_flags()) == {"A", "F", "D"}

        removing = [peak_bytes(lambda m=m: m.remove_flag("F")) for m in (few, many)]
        for built in (few, many):
            assert set(built.get_flags()) == {"A", "D"}

        deleting = [peak_bytes(lambda m=m: m.__delitem__("status")) for m in (few, many)]

        for name, peaks in (("set_flags", setting), ("add_flag", adding)):
            assert peaks[1] < 2 * peaks[0], (
                f"1,000x the headers moved {name}() from {peaks[0]} to {peaks[1]} bytes"
            )
        if sys.version_info >= (3, 12):
            assert removing[1] < 2 * removing[0], (
                f"1,000x the headers moved remove_flag() from {removing[0]} to {removing[1]} bytes"
            )
        else:
            assert removing[1] > 10 * removing[0], (
                "before 3.12 the header check listed every name, so remove_flag() should grow: "
                f"{removing[0]} to {removing[1]} bytes"
            )
        assert deleting[1] > 10 * deleting[0], (
            "the control did not grow, so the flat setter peaks prove nothing: "
            f"__delitem__ went from {deleting[0]} to {deleting[1]} bytes"
        )

    @pytest.mark.timing
    def test_reading_maildir_flags_does_not(self) -> None:
        def maildir_with(headers: int) -> mailbox.MaildirMessage:
            built = mailbox.MaildirMessage()
            for index in range(headers):
                built[f"X-Trace-{index}"] = "v"
            built.set_flags("SR")
            return built

        few, many = maildir_with(2), maildir_with(2_000)
        header_ratio = best_ns(many.get_flags, inner=200) / best_ns(few.get_flags, inner=200)

        assert header_ratio < 2, f"1,000x the headers cost {header_ratio:.1f}x"


@pytest.mark.skipif(sys.version_info < (3, 13), reason="keyed Maildir flag API added in 3.13")
class TestKeyedMaildirFlags:
    """`Maildir.get_flags(key)` and friends, Python 3.13+ | O(f) past the lookup.

    The page's claim is that these reach the filename rather than the message,
    so the test asserts the stored file was renamed and never opened.
    """

    def test_setting_flags_renames_the_file(self, tmp_path: pathlib.Path) -> None:
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message())
        before = set(os.listdir(tmp_path / "md" / "new"))

        maildir.set_flags(key, "SR")

        after = set(os.listdir(tmp_path / "md" / "new"))
        assert before != after, "set_flags() did not rename the message file"
        assert any(name.endswith("2,RS") for name in after)
        assert maildir.get_flags(key) == "RS"
        assert maildir.get_info(key) == "2,RS"

    def test_neither_reading_nor_setting_flags_opens_the_message(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message())
        maildir.set_flags(key, "S")

        opened: list[Any] = []
        real_open = open

        def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            opened.append(file)
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr("builtins.open", recording_open)
        flags = maildir.get_flags(key)
        assert flags == "S"
        after_reading = list(opened)

        maildir.set_flags(key, "SF")

        assert after_reading == [], f"get_flags() opened {after_reading}"
        assert opened == [], f"set_flags() opened {opened}"
        assert set(maildir.get_flags(key)) == {"S", "F"}

    def test_flag_edits_are_set_operations(self, tmp_path: pathlib.Path) -> None:
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message())

        maildir.add_flag(key, "F")
        assert maildir.get_flags(key) == "F"
        maildir.add_flag(key, "S")
        assert set(maildir.get_flags(key)) == {"F", "S"}
        maildir.remove_flag(key, "F")
        assert maildir.get_flags(key) == "S"

    def test_info_survives_a_round_trip(self, tmp_path: pathlib.Path) -> None:
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message())

        maildir.set_info(key, "2,FS")
        assert maildir.get_info(key) == "2,FS"
        maildir.set_info(key, "")
        assert maildir.get_info(key) == ""
        assert maildir.get_flags(key) == ""

    def test_a_non_string_is_rejected(self, tmp_path: pathlib.Path) -> None:
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message())

        with pytest.raises(TypeError):
            maildir.set_flags(key, 2)  # type: ignore[arg-type]


class TestSequencesAndLabelsAreCopies:
    """`MHMessage.get_sequences()`, `BabylMessage.get_labels()` and
    `BabylMessage.get_visible()` | O(L) or O(V) | a copy.

    Identity separates a copy from a view with no tolerance, and mutating the
    result proves the copy is real rather than an unmeasured alias.
    """

    def test_sequences_come_back_as_a_copy(self) -> None:
        mh_message = mailbox.MHMessage()
        mh_message.set_sequences(["unseen", "flagged"])

        taken = mh_message.get_sequences()
        taken.append("replied")

        assert mh_message.get_sequences() == ["unseen", "flagged"]
        assert mh_message.get_sequences() is not mh_message.get_sequences()

    def test_setting_sequences_copies_the_argument_in(self) -> None:
        mh_message = mailbox.MHMessage()
        supplied = ["unseen"]

        mh_message.set_sequences(supplied)
        supplied.append("flagged")

        assert mh_message.get_sequences() == ["unseen"]

    def test_attaching_sequences_rescans_what_is_already_there(self) -> None:
        """The L² term on `MH.get_message()`, counted rather than timed.

        `add_sequence()` scans the names the message already has before it
        appends, so attaching L distinct names makes 0 + 1 + ... + (L-1)
        comparisons. Counting them separates the triangular growth from the
        folder listing and sequence-file reads that hide it in a whole call.
        """
        counted = {}
        for total in (10, 40):
            CountingName.calls = 0
            mh_message = mailbox.MHMessage()
            for index in range(total):
                mh_message.add_sequence(CountingName(f"seq{index}"))
            counted[total] = CountingName.calls
            assert len(mh_message.get_sequences()) == total

        for total, comparisons in counted.items():
            expected = total * (total - 1) // 2
            assert comparisons == expected, (
                f"{total} names made {comparisons} comparisons, not the triangular {expected}"
            )

    def test_sequence_edits_are_idempotent(self) -> None:
        mh_message = mailbox.MHMessage()

        mh_message.add_sequence("unseen")
        mh_message.add_sequence("unseen")
        assert mh_message.get_sequences() == ["unseen"]

        mh_message.remove_sequence("absent")
        assert mh_message.get_sequences() == ["unseen"]
        mh_message.remove_sequence("unseen")
        assert mh_message.get_sequences() == []

        with pytest.raises(TypeError):
            mh_message.add_sequence(2)  # type: ignore[arg-type]

    def test_labels_come_back_as_a_copy(self) -> None:
        babyl_message = mailbox.BabylMessage()
        babyl_message.set_labels(["answered"])

        taken = babyl_message.get_labels()
        taken.append("deleted")

        assert babyl_message.get_labels() == ["answered"]

    def test_label_edits_are_idempotent(self) -> None:
        babyl_message = mailbox.BabylMessage()

        babyl_message.add_label("answered")
        babyl_message.add_label("answered")
        assert babyl_message.get_labels() == ["answered"]
        babyl_message.remove_label("absent")
        assert babyl_message.get_labels() == ["answered"]
        babyl_message.remove_label("answered")
        assert babyl_message.get_labels() == []

        with pytest.raises(TypeError):
            babyl_message.add_label(2)  # type: ignore[arg-type]

    def test_the_visible_set_is_a_fresh_object_each_call(self) -> None:
        babyl_message = mailbox.BabylMessage()
        babyl_message["Subject"] = "hello"
        babyl_message.update_visible()

        first, second = babyl_message.get_visible(), babyl_message.get_visible()
        first["X-Added"] = "yes"

        assert first is not second
        assert "X-Added" not in babyl_message.get_visible()

    @pytest.mark.serial
    def test_update_visible_space_follows_the_header_check(self) -> None:
        """The 3.12 boundary, on the other call here that asks `header in self`.

        Until 3.12 that question built a list of every header name, so the peak
        grew with the message even though the visible set did not. The time
        bound is unchanged either way, so only allocation separates them.
        """
        few, many = self.visible_message(5, 10), self.visible_message(5, 10_000)
        for built in (few, many):
            built.update_visible()
            built.replace_header("X-Visible-0", "changed")
            assert built.get_visible()["X-Visible-0"] == "v"

        peaks = [peak_bytes(built.update_visible) for built in (few, many)]

        for built in (few, many):
            assert built.get_visible()["X-Visible-0"] == "changed", (
                "the measured call refreshed nothing, so a flat peak proves nothing"
            )

        if sys.version_info >= (3, 12):
            assert peaks[1] < 2 * peaks[0], (
                "1,000x the other headers moved update_visible() "
                f"from {peaks[0]} to {peaks[1]} bytes"
            )
        else:
            assert peaks[1] > 10 * peaks[0], (
                "before 3.12 the header check listed every name, so it should grow: "
                f"{peaks[0]} to {peaks[1]} bytes"
            )

    @pytest.mark.timing
    def test_update_visible_scans_the_message_with_nothing_visible(self) -> None:
        """The lone H term: the six standard headers are looked for either way."""
        few, many = self.visible_message(0, 10), self.visible_message(0, 2_000)

        ratio = best_ns(many.update_visible, inner=20) / best_ns(few.update_visible, inner=20)

        assert ratio > 5, f"with nothing visible, 200x the headers cost {ratio:.1f}x"

    @pytest.mark.timing
    def test_update_visible_costs_the_message_header_list(self) -> None:
        few, many = self.visible_message(10, 10), self.visible_message(10, 2_000)

        ratio = best_ns(many.update_visible, inner=20) / best_ns(few.update_visible, inner=20)

        assert ratio > 5, f"200x the message's other headers cost only {ratio:.1f}x"

    @pytest.mark.timing
    def test_update_visible_costs_more_than_linear_in_the_visible_set(self) -> None:
        few, many = self.visible_message(100, 10), self.visible_message(400, 10)

        ratio = best_ns(many.update_visible, inner=5) / best_ns(few.update_visible, inner=5)

        assert ratio > 8, f"4x the visible headers cost {ratio:.1f}x, which reads as linear"

    @staticmethod
    def visible_message(visible: int, others: int) -> mailbox.BabylMessage:
        """A message with `visible` headers in its visible set and `others` beside them.

        The visible headers are on the message too, so each `update_visible()`
        refreshes them rather than dropping them - which is what makes the call
        repeatable, and what the V term prices.
        """
        built = mailbox.BabylMessage()
        seen = mailbox.Message()
        for index in range(visible):
            built[f"X-Visible-{index}"] = "v"
            seen[f"X-Visible-{index}"] = "v"
        built.set_visible(seen)
        for index in range(others):
            built[f"X-Other-{index}"] = "o"
        return built

    def test_update_visible_tracks_the_message(self) -> None:
        babyl_message = mailbox.BabylMessage()
        babyl_message["Subject"] = "hello"
        babyl_message["From"] = "someone@example.com"
        babyl_message["X-Ignored"] = "not standard"

        babyl_message.update_visible()

        visible = babyl_message.get_visible()
        assert visible["Subject"] == "hello"
        assert visible["From"] == "someone@example.com"
        assert "X-Ignored" not in visible, "update_visible() copied a non-standard header"

        del babyl_message["Subject"]
        babyl_message.update_visible()
        assert "Subject" not in babyl_message.get_visible()


class TestMHSequenceFile:
    """`MH.set_sequences()` | O(K + q log q) and `MH.get_sequences()` |
    O(e + n log n + S + q log q).

    The page claims runs are stored as ranges and expanded on the way out, and
    that a key whose message is gone is dropped - all three are read off the
    file and the returned dictionary.
    """

    def test_runs_are_stored_as_ranges(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(5):
            mh.add(message())

        mh.set_sequences({"unseen": [1, 2, 3, 5]})

        written = (tmp_path / "mh" / ".mh_sequences").read_text(encoding="ASCII")
        assert "1-3 5" in written, f"the run was not collapsed: {written!r}"

    def test_ranges_expand_on_the_way_out(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(5):
            mh.add(message())
        mh.set_sequences({"unseen": [1, 2, 3, 5]})

        assert mh.get_sequences() == {"unseen": [1, 2, 3, 5]}

    def test_a_key_with_no_message_is_dropped(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(5):
            mh.add(message())
        mh.set_sequences({"unseen": [1, 2, 3, 5]})

        mh.remove(2)

        assert mh.get_sequences() == {"unseen": [1, 3, 5]}

    def test_an_empty_sequence_is_not_written(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        mh.add(message())

        mh.set_sequences({"unseen": [1], "empty": []})

        assert mh.get_sequences() == {"unseen": [1]}

    def test_a_stored_message_carries_its_sequences(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        key = mh.add(message())
        mh.set_sequences({"unseen": [key]})

        assert mh.get_message(key).get_sequences() == ["unseen"]

    def test_pack_renumbers_and_rewrites_the_sequences(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for index in range(5):
            mh.add(message(f"s{index}"))
        mh.set_sequences({"unseen": [1, 5]})
        mh.remove(2)
        mh.remove(3)

        mh.pack()

        assert sorted(mh.keys()) == [1, 2, 3]
        assert mh.get_sequences() == {"unseen": [1, 3]}
        assert mh.get_message(3)["Subject"] == "s4"

    def test_a_compact_range_names_many_keys(self, tmp_path: pathlib.Path) -> None:
        """`q` is not `S`: one short line on disk expands to 400 keys in memory."""
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        for _ in range(400):
            mh.add(message())
        mh.set_sequences({"unseen": list(range(1, 401))})

        written = (tmp_path / "mh" / ".mh_sequences").read_text(encoding="ASCII")

        assert len(written.strip()) < 20, f"the run was not collapsed: {written!r}"
        assert len(mh.get_sequences()["unseen"]) == 400

    def test_get_message_attaches_one_sequence_at_a_time(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ties the L² term to `get_message()`, not just to `add_sequence()`.

        Recording how many sequences the message already carries at each
        attachment gives 0, 1, ... K-1 - the scan lengths that sum to the
        triangular count. A `get_message()` that stopped using this path
        would record nothing.
        """
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        key = mh.add(message())
        names = [f"seq{index}" for index in range(8)]
        mh.set_sequences({name: [key] for name in names})

        already: list[int] = []
        real_add = mailbox.MHMessage.add_sequence

        def recording(self: Any, sequence: str) -> Any:
            already.append(len(self.get_sequences()))
            return real_add(self, sequence)

        monkeypatch.setattr(mailbox.MHMessage, "add_sequence", recording)
        recovered = mh.get_message(key)

        assert sorted(recovered.get_sequences()) == sorted(names)
        assert already == list(range(len(names))), (
            f"get_message() attached against lists of length {already}"
        )

    def test_set_sequences_visits_a_name_it_discards(self, tmp_path: pathlib.Path) -> None:
        """The standalone `K`: an empty sequence names no keys but is still visited.

        Each supplied key list records the length check that decides whether to
        skip it, so the 50 empty names are observed being processed rather than
        merely being absent from the result.
        """
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        key = mh.add(message())
        supplied = {f"empty{index}": CountingKeyList() for index in range(50)}
        supplied["kept"] = CountingKeyList([key])

        mh.set_sequences(supplied)

        unchecked = [name for name, keys in supplied.items() if keys.checks == 0]
        assert unchecked == [], f"{len(unchecked)} of {len(supplied)} names were never looked at"
        assert mh.get_sequences() == {"kept": [key]}
        written = (tmp_path / "mh" / ".mh_sequences").read_text(encoding="ASCII")
        assert "empty0" not in written, "a discarded name reached the file"

    def test_whitespace_on_a_line_does_not_change_the_mapping(self, tmp_path: pathlib.Path) -> None:
        """A sequence line can be padded without changing what it names.

        The parse splits on whitespace, so the line's length is free of `K` and
        `q` - it is the peak the `retained` space cells exclude, and the
        recovered mapping is identical either way.
        """
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        key = mh.add(message())
        sequences = tmp_path / "mh" / ".mh_sequences"

        sequences.write_text(f"unseen:{' ' * 200_000}{key}\n", encoding="ASCII")
        padded = mh.get_sequences()
        sequences.write_text(f"unseen: {key}\n", encoding="ASCII")

        assert padded == mh.get_sequences() == {"unseen": [key]}

    def test_an_unparsable_line_is_a_format_error(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        mh.add(message())
        (tmp_path / "mh" / ".mh_sequences").write_text("nonsense\n", encoding="ASCII")

        with pytest.raises(mailbox.FormatError):
            mh.get_sequences()


class TestBabylStoresHeadersTwice:
    """`Babyl.add()` | O(m + h): the headers are written once as received and
    once as the visible set.

    Counted by occurrences of a distinctive header name in the file, against
    `mbox` writing the same message once.
    """

    def test_the_headers_appear_twice_in_the_file(self, tmp_path: pathlib.Path) -> None:
        source = message(headers=1)

        babyl: Any = mailbox.Babyl(str(tmp_path / "archive.babyl"))
        babyl.add(source)
        babyl.close()
        box: Any = mailbox.mbox(str(tmp_path / "archive.mbox"))
        box.add(source)
        box.close()

        babyl_bytes = (tmp_path / "archive.babyl").read_bytes()
        mbox_bytes = (tmp_path / "archive.mbox").read_bytes()

        assert babyl_bytes.count(b"X-Trace-0") == 2, "Babyl did not store a second header copy"
        assert mbox_bytes.count(b"X-Trace-0") == 1

    @pytest.mark.parametrize("reader", ["get_message", "get_bytes", "get_file"])
    def test_a_stored_babyl_message_cannot_be_read_back(
        self, tmp_path: pathlib.Path, reader: str
    ) -> None:
        """The warning on the page, held to all three readers.

        `_install_message()` flattens the visible set into a buffer it never
        rewinds, so the visible section is written empty; the reader then runs
        past the message looking for the blank line that should have closed
        it. The body here holds no blank line, so the search reaches the end
        of the message and the offset arithmetic fails; a body that does hold
        one fails differently, which the next test covers. The control is the
        same message stored as a plain one, which the other branch writes
        correctly.
        """
        plain = message("hello", body="one paragraph only\n")

        readable: Any = mailbox.Babyl(str(tmp_path / "ok.babyl"))
        readable.add(plain)
        readable.close()
        broken: Any = mailbox.Babyl(str(tmp_path / "broken.babyl"))
        broken.add(mailbox.BabylMessage(plain))
        broken.close()

        readable = mailbox.Babyl(str(tmp_path / "ok.babyl"))
        assert len(readable) == 1
        assert getattr(readable, reader)(0) is not None, f"a plain message broke {reader}()"
        readable.close()

        broken = mailbox.Babyl(str(tmp_path / "broken.babyl"))
        assert len(broken) == 1
        with pytest.raises(AssertionError):
            getattr(broken, reader)(0)
        broken.close()

    def test_a_populated_visible_set_is_dropped(self, tmp_path: pathlib.Path) -> None:
        """Why the read overshoots: the second header copy is simply absent.

        The visible set carries a header of its own, so this separates "the
        visible copy was written empty" from "the visible copy repeated the
        message's headers", which is what a plain message gets.
        """
        source = mailbox.BabylMessage(message(headers=1))
        visible = mailbox.Message()
        visible["X-Visible-Only"] = "should have been written"
        source.set_visible(visible)

        broken: Any = mailbox.Babyl(str(tmp_path / "broken.babyl"))
        broken.add(source)
        broken.close()

        written = (tmp_path / "broken.babyl").read_bytes()

        assert b"X-Visible-Only" not in written, "the visible set did reach the file"
        assert written.count(b"X-Trace-0") == 1, "a BabylMessage did write a second header copy"
        assert b"*** EOOH ***" in written

    def test_a_blank_line_in_the_body_loses_everything_before_it(
        self, tmp_path: pathlib.Path
    ) -> None:
        """The silent half of the warning, and the worse one.

        The reader stops its visible-header search at the first blank line it
        meets. With nothing written between `*** EOOH ***` and the body, that
        blank line is the one inside the body - so the read succeeds and
        everything ahead of it is gone.
        """
        source = message(body="first paragraph\n\nsecond paragraph\n")

        silent: Any = mailbox.Babyl(str(tmp_path / "silent.babyl"))
        silent.add(mailbox.BabylMessage(source))
        silent.close()

        silent = mailbox.Babyl(str(tmp_path / "silent.babyl"))
        assert len(silent) == 1
        recovered = silent.get_message(0)

        assert recovered.get_payload() == "second paragraph\n", (
            "the read did not lose the first paragraph, so the page's silent case is wrong"
        )
        for name, text in (
            ("get_bytes", silent.get_bytes(0).decode("ascii")),
            ("get_file", silent.get_file(0).read().decode("ascii")),
        ):
            assert "second paragraph" in text, f"{name}() lost the whole body, not just the start"
            assert "first paragraph" not in text, f"{name}() kept the first paragraph"
        silent.close()

    def test_labels_are_unioned_across_the_mailbox(self, tmp_path: pathlib.Path) -> None:
        babyl: Any = mailbox.Babyl(str(tmp_path / "archive.babyl"))
        for labels in (["work"], ["work", "urgent"], ["unseen"]):
            stored = mailbox.BabylMessage(message())
            stored.set_labels(labels)
            babyl.add(stored)

        found = babyl.get_labels()

        assert sorted(found) == ["urgent", "work"], "a reserved label leaked into get_labels()"


class TestMailboxWideOperations:
    """The `Mailbox` rows: `values()` | O(n·m) space against iteration | O(m),
    and `get_string()` | O(m) for a parse and a render.
    """

    @pytest.mark.serial
    def test_values_holds_the_mailbox_and_iteration_holds_one(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 2_000)
        box: Any = mailbox.mbox(str(path))
        assert len(box) == 2_000

        def walk() -> int:
            """Consume every message without keeping any of them, or any result."""
            counted = 0
            for _ in box:
                counted += 1
            return counted

        walked = 0

        def measured_walk() -> None:
            nonlocal walked
            walked = walk()

        iterating = peak_bytes(measured_walk)
        held: list[Any] = []
        holding = peak_bytes(lambda: held.extend(box.values()))

        assert walked == 2_000, f"the measured walk yielded {walked} messages"
        assert len(held) == 2_000, f"the measured values() returned {len(held)}"

        assert holding > 10 * iterating, (
            f"values() peaked at {holding} bytes against {iterating} for an iteration"
        )
        box.close()

    def test_get_string_round_trips_the_stored_bytes(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        box: Any = mailbox.mbox(str(path))
        box.add(message("hello", "a body"))
        box.close()

        box = mailbox.mbox(str(path))
        assert len(box) == 1

        assert box.get_string(0) == box.get_bytes(0).decode("ascii")
        assert "hello" in box.get_string(0)
        assert box.get_string(0, from_=True).startswith("From ")
        box.close()

    def test_items_and_iteritems_agree(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 3)
        box: Any = mailbox.mbox(str(path))

        assert [key for key, _ in box.items()] == [0, 1, 2]
        assert [key for key, _ in box.iteritems()] == [0, 1, 2]
        assert [stored["Subject"] for stored in box.itervalues()] == ["s0", "s1", "s2"]
        assert len(box.values()) == 3
        box.close()

    def test_pop_and_popitem_remove_what_they_return(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 3)
        box: Any = mailbox.mbox(str(path))

        popped = box.pop(1)
        assert popped["Subject"] == "s1"
        assert 1 not in box
        assert box.pop(1) is None

        key, stored = box.popitem()
        assert key == 0 and stored["Subject"] == "s0"
        assert sorted(box.keys()) == [2]
        box.close()

    def test_popitem_on_an_empty_mailbox_raises(self, tmp_path: pathlib.Path) -> None:
        box: Any = mailbox.mbox(str(tmp_path / "empty.mbox"))

        with pytest.raises(KeyError):
            box.popitem()
        box.close()

    def test_clear_discards_every_key(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 5)
        box: Any = mailbox.mbox(str(path))

        box.clear()

        assert len(box) == 0
        box.close()
        assert os.path.getsize(path) == 0

    def test_update_reports_missing_keys_after_writing_the_rest(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 2)
        box: Any = mailbox.mbox(str(path))

        with pytest.raises(KeyError):
            box.update({99: message("nowhere"), 0: message("replaced")})

        assert box[0]["Subject"] == "replaced", "update() stopped at the missing key"
        box.close()

    def test_discard_swallows_a_missing_key_and_remove_does_not(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 1)
        box: Any = mailbox.mbox(str(path))

        box.discard(99)
        with pytest.raises(KeyError):
            box.remove(99)
        box.close()

    def test_a_factory_replaces_the_message_class(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 1)

        def read_raw(stream: Any) -> Any:
            return stream.read()

        box: Any = mailbox.mbox(str(path), factory=read_raw)
        stored = box[0]

        assert isinstance(stored, bytes)
        assert b"s0" in stored
        box.close()


class TestFoldersAndHousekeeping:
    """The folder and housekeeping rows: `list_folders()` | O(r) for `Maildir`
    and O(e) for `MH`, `add_folder()` | O(1), `remove_folder()` | O(entries in
    the folder), and `Maildir.clean()` | O(t)."""

    def test_maildir_folders_round_trip(self, tmp_path: pathlib.Path) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))

        folder = maildir.add_folder("work")
        assert maildir.list_folders() == ["work"]
        assert isinstance(maildir.get_folder("work"), mailbox.Maildir)
        with pytest.raises(mailbox.NoSuchMailboxError):
            maildir.get_folder("absent")

        folder.add(message())
        with pytest.raises(mailbox.NotEmptyError):
            maildir.remove_folder("work")

        folder.clear()
        maildir.remove_folder("work")
        assert maildir.list_folders() == []

    def test_mh_folders_round_trip(self, tmp_path: pathlib.Path) -> None:
        mh: Any = mailbox.MH(str(tmp_path / "mh"))

        folder = mh.add_folder("work")
        assert mh.list_folders() == ["work"]
        assert isinstance(mh.get_folder("work"), mailbox.MH)
        with pytest.raises(mailbox.NoSuchMailboxError):
            mh.get_folder("absent")

        folder.add(message())
        with pytest.raises(mailbox.NotEmptyError):
            mh.remove_folder("work")

        folder.clear()
        mh.remove_folder("work")
        assert mh.list_folders() == []

    def test_clean_removes_only_stale_temporaries(self, tmp_path: pathlib.Path) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        stale = tmp_path / "md" / "tmp" / "stale"
        fresh = tmp_path / "md" / "tmp" / "fresh"
        stale.touch()
        fresh.touch()
        long_ago = time.time() - 200_000
        os.utime(stale, (long_ago, long_ago))

        maildir.clean()

        assert not stale.exists(), "clean() kept a temporary older than 36 hours"
        assert fresh.exists(), "clean() removed a fresh temporary"

    def test_the_colon_reaches_the_filename(self, tmp_path: pathlib.Path) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        maildir.colon = "!"
        stored = mailbox.MaildirMessage(message())
        stored.set_flags("S")

        key = maildir.add(stored)

        names = os.listdir(tmp_path / "md" / "new")
        assert any("!2,S" in name for name in names), f"the separator did not reach {names}"
        assert maildir[key].get_flags() == "S"

    def test_next_walks_the_mailbox_once(self, tmp_path: pathlib.Path) -> None:
        maildir: Any = mailbox.Maildir(str(tmp_path / "md"))
        for index in range(3):
            maildir.add(message(f"s{index}"))

        seen = []
        while (stored := maildir.next()) is not None:
            seen.append(stored["Subject"])

        assert sorted(seen) == ["s0", "s1", "s2"]
        assert maildir.next() is None, "next() restarted after the end"

    def test_maildir_bookkeeping_calls_are_no_ops(self, tmp_path: pathlib.Path) -> None:
        maildir = mailbox.Maildir(str(tmp_path / "md"))
        key = maildir.add(message())

        maildir.lock()
        maildir.flush()
        maildir.unlock()
        maildir.close()

        assert key in mailbox.Maildir(str(tmp_path / "md"))

    def test_mh_lock_takes_the_sequences_file_not_the_messages(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The row's claim, observed at the boundary rather than by existence.

        Recreating a deleted `.mh_sequences` is 3.13 behaviour, so the test
        watches what `lock()` opens instead, which holds on every version.
        """
        mh: Any = mailbox.MH(str(tmp_path / "mh"))
        key = mh.add(message())

        opened: list[str] = []
        real_open = open

        def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            opened.append(os.path.basename(str(file)))
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr("builtins.open", recording_open)
        mh.lock()
        try:
            assert opened, "lock() opened nothing"
            assert all(name.startswith(".mh_sequences") for name in opened), (
                f"lock() opened something other than the sequences file and its dot lock: {opened}"
            )
            assert str(key) not in opened, "lock() opened the message"
        finally:
            mh.close()


class TestExceptions:
    """The `Exceptions` rows, each raised on the path the page names."""

    def test_every_error_shares_one_base(self) -> None:
        for error in (
            mailbox.NoSuchMailboxError,
            mailbox.NotEmptyError,
            mailbox.ExternalClashError,
            mailbox.FormatError,
        ):
            assert issubclass(error, mailbox.Error)
        assert issubclass(mailbox.Error, Exception)

    @pytest.mark.parametrize(
        "factory",
        [mailbox.mbox, mailbox.MMDF, mailbox.Babyl, mailbox.Maildir, mailbox.MH],
        ids=["mbox", "MMDF", "Babyl", "Maildir", "MH"],
    )
    def test_refusing_to_create(
        self, tmp_path: pathlib.Path, factory: Callable[..., mailbox.Mailbox]
    ) -> None:
        with pytest.raises(mailbox.NoSuchMailboxError):
            factory(str(tmp_path / "absent"), create=False)

    def test_a_second_dot_lock_clashes(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "archive.mbox"
        filled_mbox(path, 1)
        first: Any = mailbox.mbox(str(path))
        second: Any = mailbox.mbox(str(path))

        first.lock()
        try:
            assert (tmp_path / "archive.mbox.lock").exists()
            with pytest.raises(mailbox.ExternalClashError):
                second.lock()
        finally:
            first.unlock()
            first.close()
            second.close()

        assert not (tmp_path / "archive.mbox.lock").exists(), "unlock() left the dot lock behind"

    def test_the_abstract_base_implements_nothing(self) -> None:
        base: Any = mailbox.Mailbox("/nowhere")

        for call in (
            lambda: base.add(message()),
            lambda: base.remove(0),
            lambda: base.get_message(0),
            lambda: base.get_bytes(0),
            lambda: base.get_file(0),
            lambda: base.iterkeys(),
            lambda: base.flush(),
            lambda: base.lock(),
            lambda: base.unlock(),
            lambda: base.close(),
        ):
            with pytest.raises(NotImplementedError):
                call()


class TestConvertingBetweenFormats:
    """`Message(other_format_message)` copies and translates.

    The page claims the translation is a fixed number of flag updates on top
    of the copy, so the test pins which flags each conversion produces rather
    than timing it.
    """

    def test_maildir_flags_become_mbox_status_letters(self) -> None:
        source = mailbox.MaildirMessage(message("hello"))
        source.set_flags("RS")
        source.set_subdir("cur")

        converted = mailbox.mboxMessage(source)

        assert converted["Subject"] == "hello"
        assert set(converted.get_flags()) == {"R", "O", "A"}

    def test_maildir_flags_become_mh_sequences(self) -> None:
        source = mailbox.MaildirMessage(message())
        source.set_flags("F")

        converted = mailbox.MHMessage(source)

        assert "unseen" in converted.get_sequences()
        assert "flagged" in converted.get_sequences()

    def test_mbox_flags_become_babyl_labels(self) -> None:
        source = mailbox.mboxMessage(message())
        source.set_flags("D")

        converted = mailbox.BabylMessage(source)

        assert "deleted" in converted.get_labels()
        assert "Status" not in converted, "the mbox flag headers survived the conversion"

    def test_the_conversion_is_a_copy(self) -> None:
        source = mailbox.MaildirMessage(message("hello"))

        converted = mailbox.mboxMessage(source)
        converted["X-Added"] = "yes"

        assert "X-Added" not in source


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
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, so the
    mailboxes one block creates cannot reach another, and asserts its own
    result. Two blocks patch `os.listdir`; the subprocess is what keeps that
    from leaking into the next one."""

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
        line, source = next(
            (n, s) for n, s in _blocks() if "assert first == 2 and second == 2" in s
        )
        mutated = source.replace(
            "assert first == 2 and second == 2", "assert first == 1 and second == 1", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
