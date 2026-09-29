"""Tests for docs/stdlib/tempfile.md.

The page prices every creation by its name attempts: draw a random name, try
to create it exclusively, draw again on a collision. That loop is settled by
observation rather than timing - the name generator is replaced by a scripted
one and `os.open`, `os.mkdir` and `os.lstat` are counted - so each bound is an
exact count with no tolerance. Memory claims are settled by traced
allocation, and cleanup by counting the unlinks and rmdirs it performs.

Measurement scope:

* `mkstemp()`, `mkdtemp()`, `NamedTemporaryFile()` and `mktemp()` are given a
  name sequence whose first two names already exist: each draws three names
  and makes three `os.open`, `os.mkdir` or `os.lstat` calls in a directory
  of 1,000 other files, calling neither `os.listdir` nor `os.scandir`, and an
  uncontended call draws one name and makes one call. With `TMP_MAX` patched
  to 5 and every name taken, each raises `FileExistsError` after exactly five
  draws. A real draw is asserted to be eight characters from a 37-character
  alphabet. `TMP_MAX` is asserted to be 20 on 3.13.13+ and 3.14.4+ and
  `os.TMP_MAX` (or 10,000 where `os` has none) before that, on
  `sys.version_info`. `mkdtemp()` given a relative `dir` returns an absolute
  path on 3.12+ and a relative one before.
* `mktemp()` is asserted to create nothing, and a name it returned is shown
  to be taken by another opener before an exclusive create reaches it.
* `gettempdir()` with the cache cleared, `TMPDIR` pointing at a missing
  directory and `TEMP` at a real one makes two `os.open` calls, returns the
  second and leaves it empty; the next call, `gettempdirb()`, and an
  assignment to `tempfile.tempdir` followed by a call make none. `mkstemp()`
  with `dir=None`, the cache cleared and the same two candidates makes two
  probe opens plus one create.
* `TemporaryFile()` on Linux, where `tmp_path`'s filesystem accepts
  `O_TMPFILE`, draws no name and leaves the
  directory empty while open; with `O_TMPFILE` disabled it draws one name and
  the directory is still empty while open, because the name is unlinked at
  once. `NamedTemporaryFile()` is visible in its directory while open and gone
  after `close()`; `delete=False` keeps it; `delete_on_close=False` (3.12+)
  keeps it through `close()` and removes it at the end of the `with` block.
* Writing 8 MiB to a `NamedTemporaryFile` peaks under 256 KiB of traced
  allocation in binary mode and above 8 MiB in text mode, which encodes the
  string first; the same binary write to a `SpooledTemporaryFile` below its
  `max_size` peaks above 8 MiB and creates no file.
* `SpooledTemporaryFile` holds a write that leaves the position at exactly
  `max_size` and rolls over on the next byte; `max_size=0` holds 1 MiB
  without rolling over; `fileno()` and `truncate(size)` past `max_size`
  force rollover. `rollover()` on 8 MiB held in binary and in text mode,
  written in one call or in 8,192 calls of 1 KiB, writes all of it to the
  file, keeps the position, peaks under 1 MiB above what was already held,
  and leaves under 1 MiB traced afterwards. A second `rollover()` keeps the
  same descriptor.
* `SpooledTemporaryFile.writelines()` of 1,000 lines of 10,000 bytes with a
  20,000-byte `max_size` peaks under 1 MiB, and has rolled over before the
  fourth line is drawn, on 3.12.10+, 3.13.3+ and 3.14, and
  above the 10 MB total on 3.10, 3.11, 3.12.0-3.12.9 and 3.13.0-3.13.2.
  The two sides are guarded on `sys.version_info` and were run on 3.10.21,
  3.11.16, 3.12.7, 3.12.14, 3.13.11, 3.13.14, 3.14.2 and 3.14.7, which also
  straddle the `TMP_MAX` boundary.
* `SpooledTemporaryFile` is an `io.IOBase` with `readable()`, `seekable()`,
  `writable()` and `read1()` on 3.11+, and not on 3.10.
* `TemporaryDirectory` cleanup over trees of 10 and 1,000 files in 1 and 10
  subdirectories is counted: one `os.unlink` per file and one `os.rmdir` per
  directory, the root included. It runs when the `with` block raises, a
  second `cleanup()` does nothing, collecting the object removes the tree
  with a `ResourceWarning`, and `delete=False` (3.12+) leaves the tree
  through exit and garbage collection. A tree holding a file inside a
  read-only subdirectory defeats plain `shutil.rmtree` and is removed by
  `cleanup()`. An `OSError` from removing the root is raised by default and
  swallowed with `ignore_cleanup_errors=True`, leaving the empty root.
* Every fenced Python block runs in its own subprocess with `TMPDIR` set to
  its own working directory, which is asserted empty afterwards; a mutated
  assertion in one block is asserted to fail.

Not settled here:

* The O(d·w) space of cleanup is `shutil.rmtree`'s, measured in
  tests/test_shutil_complexity.py, not here; this file counts cleanup's calls
  and does not measure its allocation. The read-only subdirectory test is
  skipped as root, where permissions do not stop the removal it relies on.
* That `os.replace()` in the atomic-replace pattern is atomic on POSIX is the
  `os` module's contract; the block runs the rename but cannot observe a
  reader in between.
* Windows behaviour is category D. `NamedTemporaryFile` opens with
  `O_TEMPORARY` when `delete` and `delete_on_close` are both true, so the
  path cannot be reopened while the file is open, and `TemporaryFile` is
  `NamedTemporaryFile`. Those tests are guarded on `sys.platform == "win32"`
  and are skipped by every run this project performs; the POSIX tests that
  reopen a path or expect an empty directory are guarded the other way.
* `TemporaryFile()` drawing no name needs a filesystem that supports
  `O_TMPFILE`; the test uses pytest's `tmp_path`, and other filesystems take
  the fallback that the second test pins.
* The chance of a collision, and so the expected r, depends on what else is
  in the directory and on the random generator; the tests script collisions
  rather than measure their frequency. Text-mode `max_size` is compared with
  `tell()`, an opaque cookie, and only ASCII text is used.
"""

from __future__ import annotations

import errno
import gc
import io
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tempfile.md"
EXPECTED_BLOCKS = 9

MIB = 1 << 20


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def tmp_max_is_twenty() -> bool:
    """3.13.13+ and 3.14.4+ cap name attempts at 20."""
    version = sys.version_info[:3]
    return (3, 13, 13) <= version < (3, 14) or version >= (3, 14, 4)


def writelines_rolls_over_mid_iteration() -> bool:
    """3.12.10+, 3.13.3+ and 3.14 check `max_size` after each line."""
    version = sys.version_info[:3]
    return (3, 12, 10) <= version < (3, 13) or (3, 13, 3) <= version < (3, 14) or version >= (3, 14)


class ScriptedNames:
    """A name sequence that yields `names` in order and counts the draws."""

    def __init__(self, names: list[str]) -> None:
        self._names = iter(names)
        self.drawn = 0

    def __iter__(self) -> ScriptedNames:
        return self

    def __next__(self) -> str:
        self.drawn += 1
        return next(self._names)


class Counter:
    """Wrap a function and count its calls."""

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self.func(*args, **kwargs)


@pytest.fixture
def names(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[str]], ScriptedNames]:
    """Install a scripted name sequence in place of the module's generator."""

    def install(sequence: list[str]) -> ScriptedNames:
        scripted = ScriptedNames(sequence)
        monkeypatch.setattr(tempfile, "_get_candidate_names", lambda: scripted)
        return scripted

    return install


@pytest.fixture
def count(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Counter]:
    """Count calls to one `os` function."""

    def install(name: str) -> Counter:
        counter = Counter(getattr(os, name))
        monkeypatch.setattr(os, name, counter)
        return counter

    return install


def _create_mkstemp(directory: pathlib.Path) -> str:
    fd, path = tempfile.mkstemp(prefix="p", dir=directory)
    os.close(fd)
    return path


def _create_named(directory: pathlib.Path) -> str:
    with tempfile.NamedTemporaryFile(prefix="p", dir=directory, delete=False) as f:
        return f.name


CREATORS: dict[str, tuple[Callable[[pathlib.Path], str], str]] = {
    "mkstemp": (_create_mkstemp, "open"),
    "NamedTemporaryFile": (_create_named, "open"),
    "mkdtemp": (lambda directory: tempfile.mkdtemp(prefix="p", dir=directory), "mkdir"),
    "mktemp": (lambda directory: tempfile.mktemp(prefix="p", dir=str(directory)), "lstat"),
}


class TestNameAttemptsRetryOnCollision:
    """`mkstemp`, `mkdtemp`, `NamedTemporaryFile` and `mktemp` | O(r).

    A collision costs one more draw and one more filesystem call; nothing
    lists the directory, so what else it holds costs nothing until a name
    collides with it.
    """

    @pytest.mark.parametrize("creator", sorted(CREATORS))
    def test_each_collision_costs_one_draw_and_one_call(
        self,
        creator: str,
        tmp_path: pathlib.Path,
        names: Callable[[list[str]], ScriptedNames],
        count: Callable[[str], Counter],
    ) -> None:
        create, call = CREATORS[creator]
        for taken in ("taken1", "taken2"):
            (tmp_path / f"p{taken}").mkdir()
        for index in range(1_000):
            (tmp_path / f"other{index}").touch()
        scripted = names(["taken1", "taken2", "free"])
        counter = count(call)
        listings = count("listdir")
        scans = count("scandir")

        path = create(tmp_path)

        assert os.path.basename(path) == "pfree"
        assert listings.calls == scans.calls == 0, "the directory is never listed"
        assert scripted.drawn == 3
        assert counter.calls == 3, f"{creator}: {counter.calls} {call} calls for 3 attempts"

    @pytest.mark.parametrize("creator", sorted(CREATORS))
    def test_an_uncontended_creation_makes_one_attempt(
        self,
        creator: str,
        tmp_path: pathlib.Path,
        names: Callable[[list[str]], ScriptedNames],
        count: Callable[[str], Counter],
    ) -> None:
        create, call = CREATORS[creator]
        scripted = names(["free"])
        counter = count(call)

        create(tmp_path)

        assert (scripted.drawn, counter.calls) == (1, 1)

    @pytest.mark.parametrize("creator", sorted(CREATORS))
    def test_tmp_max_attempts_then_file_exists_error(
        self,
        creator: str,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        names: Callable[[list[str]], ScriptedNames],
    ) -> None:
        create, _ = CREATORS[creator]
        # A file, not a directory: on Windows opening a directory's name raises
        # PermissionError, which the last attempt lets escape.
        (tmp_path / "ptaken").touch()
        monkeypatch.setattr(tempfile, "TMP_MAX", 5)
        scripted = names(["taken"] * 100)

        with pytest.raises(FileExistsError):
            create(tmp_path)

        assert scripted.drawn == 5

    def test_a_real_draw_is_eight_characters(self) -> None:
        name = next(iter(tempfile._get_candidate_names()))  # type: ignore[attr-defined]  # noqa: SLF001

        assert re.fullmatch(r"[a-z0-9_]{8}", name), name

    def test_tmp_max_on_this_version(self) -> None:
        if tmp_max_is_twenty():
            assert tempfile.TMP_MAX == 20
        else:
            assert tempfile.TMP_MAX == getattr(os, "TMP_MAX", 10_000)
            assert tempfile.TMP_MAX > 20


class TestMkdtempPath:
    """`mkdtemp()` returns an absolute path from 3.12, even for a relative `dir`."""

    def test_a_relative_dir(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "rel").mkdir()

        path = tempfile.mkdtemp(dir="rel")

        assert os.path.isabs(path) is (sys.version_info >= (3, 12))
        assert os.path.samefile(os.path.dirname(path), tmp_path / "rel")


class TestMktempCreatesNothing:
    """`mktemp` | O(r) | deprecated: it checks a name and returns it, and the
    name can be taken before the caller creates it."""

    def test_nothing_is_created(self, tmp_path: pathlib.Path) -> None:
        name = tempfile.mktemp(dir=str(tmp_path))

        assert os.path.dirname(name) == str(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_another_opener_can_take_the_name(self, tmp_path: pathlib.Path) -> None:
        name = tempfile.mktemp(dir=str(tmp_path))
        pathlib.Path(name).touch()

        with pytest.raises(FileExistsError):
            os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY)


class TestGettempdirProbesOnceThenCaches:
    """`gettempdir()` | O(c) first call, then O(1): each candidate costs one
    probe file, and the winner is cached in `tempfile.tempdir`."""

    @pytest.fixture
    def candidates(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> Iterator[pathlib.Path]:
        good = tmp_path / "good"
        good.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", None)
        monkeypatch.setenv("TMPDIR", str(tmp_path / "missing"))
        monkeypatch.setenv("TEMP", str(good))
        monkeypatch.delenv("TMP", raising=False)
        yield good

    def test_the_first_call_probes_each_candidate_in_turn(
        self, candidates: pathlib.Path, count: Callable[[str], Counter]
    ) -> None:
        opens = count("open")

        found = tempfile.gettempdir()

        assert found == str(candidates)
        assert opens.calls == 2, "one failed probe in the missing directory, one success"
        assert list(candidates.iterdir()) == [], "the probe file is removed"
        assert tempfile.tempdir == found

    def test_later_calls_read_the_cache(
        self, candidates: pathlib.Path, count: Callable[[str], Counter]
    ) -> None:
        first = tempfile.gettempdir()
        opens = count("open")

        assert tempfile.gettempdir() == first
        assert tempfile.gettempdirb() == os.fsencode(first)
        assert opens.calls == 0

    def test_assigning_tempdir_skips_the_probe(
        self,
        candidates: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        count: Callable[[str], Counter],
    ) -> None:
        monkeypatch.setattr(tempfile, "tempdir", str(candidates))
        opens = count("open")

        assert tempfile.gettempdir() == str(candidates)
        assert opens.calls == 0

    def test_a_creation_with_dir_none_pays_the_first_probe(
        self, candidates: pathlib.Path, count: Callable[[str], Counter]
    ) -> None:
        opens = count("open")

        fd, path = tempfile.mkstemp()
        os.close(fd)

        assert os.path.dirname(path) == str(candidates)
        assert opens.calls == 3, "two probes plus one create"
        os.unlink(path)

    def test_the_prefixes(self) -> None:
        assert tempfile.gettempprefix() == "tmp"
        assert tempfile.gettempprefixb() == b"tmp"


class TestTemporaryFileNeedsNoName:
    """`TemporaryFile` | O(r) | O(1): on Linux with `O_TMPFILE` no name is
    drawn; elsewhere on POSIX the name is unlinked as soon as it exists."""

    @pytest.mark.skipif(
        sys.platform != "linux" or not hasattr(os, "O_TMPFILE"), reason="O_TMPFILE is Linux-only"
    )
    def test_o_tmpfile_draws_no_name(
        self, tmp_path: pathlib.Path, names: Callable[[list[str]], ScriptedNames]
    ) -> None:
        if sys.platform != "linux":
            pytest.skip("O_TMPFILE is Linux-only")
        try:
            os.close(os.open(tmp_path, os.O_RDWR | os.O_TMPFILE))
        except OSError:
            pytest.skip("this filesystem does not support O_TMPFILE")
        scripted = names(["unused"])

        with tempfile.TemporaryFile(dir=tmp_path) as f:
            f.write(b"data")
            assert list(tmp_path.iterdir()) == []

        assert scripted.drawn == 0

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX unlinks the name at once")
    def test_the_fallback_draws_one_name_and_unlinks_it(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        names: Callable[[list[str]], ScriptedNames],
    ) -> None:
        monkeypatch.setattr(tempfile, "_O_TMPFILE_WORKS", False, raising=False)
        scripted = names(["one"])

        with tempfile.TemporaryFile(dir=tmp_path) as f:
            f.write(b"data")
            f.seek(0)
            assert f.read() == b"data"
            assert list(tmp_path.iterdir()) == []

        assert scripted.drawn == 1

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only aliasing")
    def test_on_windows_it_is_named_temporary_file(self) -> None:
        assert tempfile.TemporaryFile is tempfile.NamedTemporaryFile


class TestNamedTemporaryFileLivesOnDisk:
    """`NamedTemporaryFile` | O(r) | O(1): the data goes to disk, the path is
    visible while it is open, and `delete`/`delete_on_close` decide when it
    is removed."""

    def test_writing_holds_the_buffer_not_the_data(self, tmp_path: pathlib.Path) -> None:
        data = b"x" * (8 * MIB)
        with tempfile.NamedTemporaryFile(dir=tmp_path) as f:
            peak = peak_bytes(lambda: f.write(data))
            f.flush()
            assert os.path.getsize(f.name) == len(data)

        assert peak < 256 * 1024, f"an 8 MiB write peaked at {peak} bytes"

    def test_a_text_write_holds_the_encoded_string(self, tmp_path: pathlib.Path) -> None:
        data = "x" * (8 * MIB)
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", dir=tmp_path) as f:
            peak = peak_bytes(lambda: f.write(data))
            f.flush()
            assert os.path.getsize(f.name) == len(data)

        assert peak > 8 * MIB, f"an 8 MiB text write peaked at only {peak} bytes"

    def test_the_path_is_visible_while_open_and_gone_after_close(
        self, tmp_path: pathlib.Path
    ) -> None:
        f = tempfile.NamedTemporaryFile(dir=tmp_path)
        assert [p.name for p in tmp_path.iterdir()] == [os.path.basename(f.name)]
        assert f.file is not f

        f.close()

        assert list(tmp_path.iterdir()) == []

    def test_delete_false_keeps_it(self, tmp_path: pathlib.Path) -> None:
        with tempfile.NamedTemporaryFile(dir=tmp_path, delete=False) as f:
            pass

        assert os.path.exists(f.name)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="delete_on_close is 3.12+")
    def test_delete_on_close_false_keeps_it_until_the_block_ends(
        self, tmp_path: pathlib.Path
    ) -> None:
        with tempfile.NamedTemporaryFile(dir=tmp_path, delete_on_close=False) as f:  # type: ignore[call-overload]
            f.close()
            assert os.path.exists(f.name)

        assert not os.path.exists(f.name)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX allows a second opener")
    def test_on_posix_the_path_can_be_reopened_while_open(self, tmp_path: pathlib.Path) -> None:
        with tempfile.NamedTemporaryFile(dir=tmp_path) as f:
            f.write(b"shared")
            f.flush()
            with open(f.name, "rb") as reader:
                assert reader.read() == b"shared"

    @pytest.mark.skipif(sys.platform != "win32", reason="O_TEMPORARY is Windows-only")
    def test_on_windows_o_temporary_blocks_a_second_opener(self, tmp_path: pathlib.Path) -> None:
        with tempfile.NamedTemporaryFile(dir=tmp_path) as f, pytest.raises(PermissionError):
            open(f.name, "rb").close()  # noqa: SIM115


class TestSpooledTemporaryFileRollsOver:
    """`SpooledTemporaryFile`: writes are held in memory until the position
    passes `max_size`; `rollover()` then copies the n held bytes to a real
    file once, O(r + n), and frees them."""

    def test_below_max_size_the_data_is_in_memory(self, tmp_path: pathlib.Path) -> None:
        data = b"x" * (8 * MIB)
        with tempfile.SpooledTemporaryFile(max_size=16 * MIB, dir=str(tmp_path)) as spool:
            peak = peak_bytes(lambda: spool.write(data))

            assert spool.name is None
            assert list(tmp_path.iterdir()) == []

        assert peak > 8 * MIB, f"an in-memory 8 MiB write peaked at only {peak} bytes"

    def test_the_position_must_pass_max_size(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(max_size=1_000, dir=str(tmp_path)) as spool:
            spool.write(b"x" * 1_000)
            assert spool.name is None

            spool.write(b"y")

            assert spool.name is not None
            spool.seek(0)
            assert spool.read() == b"x" * 1_000 + b"y"

    def test_max_size_zero_never_rolls_over_on_its_own(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(dir=str(tmp_path)) as spool:
            spool.write(b"x" * MIB)

            assert spool.name is None

    def test_fileno_forces_rollover(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(dir=str(tmp_path)) as spool:
            spool.write(b"x" * 1_000)

            fd = spool.fileno()

            assert os.fstat(fd).st_size == 1_000
            assert spool.name is not None

    def test_truncate_past_max_size_forces_rollover(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(max_size=100, dir=str(tmp_path)) as spool:
            spool.write(b"x" * 10)
            spool.truncate(5)
            assert spool.name is None

            spool.truncate(200)

            assert spool.name is not None

    @pytest.mark.parametrize("mode", ["w+b", "w+"])
    @pytest.mark.parametrize("writes", [1, 8_192])
    def test_rollover_keeps_the_data_and_frees_the_buffer(
        self, mode: str, writes: int, tmp_path: pathlib.Path
    ) -> None:
        payload: Any = b"x" * (8 * MIB) if "b" in mode else "x" * (8 * MIB)
        size = len(payload) // writes
        chunks = [payload[start : start + size] for start in range(0, len(payload), size)]
        tracemalloc.start()
        try:
            spool = tempfile.SpooledTemporaryFile(max_size=16 * MIB, mode=mode, dir=str(tmp_path))
            for chunk in chunks:
                spool.write(chunk)
            spool.seek(1_000)
            held = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()

            spool.rollover()

            after, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        with spool:
            assert spool.tell() == 1_000
            spool.flush()
            assert os.fstat(spool.fileno()).st_size == 8 * MIB
            spool.seek(0)
            assert spool.read() == payload
        assert held > 8 * MIB
        assert peak - held < MIB, f"rollover peaked {peak - held} bytes above the {held} held"
        assert after < MIB, f"{after} bytes still traced after rollover"

    def test_a_second_rollover_does_nothing(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(dir=str(tmp_path)) as spool:
            spool.write(b"x")
            spool.rollover()
            first = spool.fileno()

            spool.rollover()

            assert spool.fileno() == first

    @pytest.mark.skipif(
        not writelines_rolls_over_mid_iteration(), reason="3.12.10+, 3.13.3+ and 3.14"
    )
    def test_writelines_rolls_over_mid_iteration(self, tmp_path: pathlib.Path) -> None:
        peak, size, rolled_by_fourth_line = self._writelines(tmp_path)

        assert size == 10_000_000
        assert peak < MIB, f"writelines of 10 MB peaked at {peak} bytes"
        assert rolled_by_fourth_line, "the third line crossed max_size but did not roll over"

    @pytest.mark.skipif(writelines_rolls_over_mid_iteration(), reason="before 3.12.10 and 3.13.3")
    def test_older_writelines_holds_the_whole_iterable(self, tmp_path: pathlib.Path) -> None:
        peak, size, _ = self._writelines(tmp_path)

        assert size == 10_000_000
        assert peak > 10_000_000, f"writelines of 10 MB peaked at only {peak} bytes"

    @staticmethod
    def _writelines(tmp_path: pathlib.Path) -> tuple[int, int, bool]:
        line = b"y" * 10_000
        rolled: list[bool] = []
        with tempfile.SpooledTemporaryFile(max_size=20_000, dir=str(tmp_path)) as spool:

            def lines() -> Iterator[bytes]:
                for index in range(1_000):
                    if index == 3:
                        rolled.append(spool.name is not None)
                    yield line

            peak = peak_bytes(lambda: spool.writelines(lines()))
            spool.flush()
            return peak, os.fstat(spool.fileno()).st_size, rolled == [True]

    def test_reads_are_passed_through(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(max_size=100, mode="w+", dir=str(tmp_path)) as spool:
            spool.write("a\nb\n")
            spool.seek(0)
            assert spool.readline() == "a\n"
            assert spool.readlines() == ["b\n"]
            spool.seek(0)
            assert list(spool) == ["a\n", "b\n"]
            assert spool.mode == "w+"
            assert spool.encoding

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="full io interface is 3.11+")
    def test_it_is_a_full_io_object(self, tmp_path: pathlib.Path) -> None:
        with tempfile.SpooledTemporaryFile(dir=str(tmp_path)) as spooled:
            spooled.write(b"abc")
            spooled.seek(0)
            spool: Any = spooled  # typeshed does not declare read1() or readinto() on it

            assert isinstance(spooled, io.IOBase)
            assert spool.readable() and spool.seekable() and spool.writable()
            assert spool.read1(2) == b"ab"
            buffer = bytearray(1)
            assert spool.readinto(buffer) == 1 and buffer == b"c"

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 only")
    def test_before_311_it_is_not_an_io_object(self) -> None:
        with tempfile.SpooledTemporaryFile() as spool:
            assert not isinstance(spool, io.IOBase)
            assert not hasattr(spool, "read1")


def build_tree(root: pathlib.Path, files: int, subdirectories: int) -> None:
    """`files` files spread over `subdirectories` nested directories."""
    directories = [root]
    for index in range(subdirectories):
        directories.append(directories[-1] / f"d{index}")
        directories[-1].mkdir()
    for index in range(files):
        (directories[index % len(directories)] / f"f{index}").touch()


class TestTemporaryDirectoryCleanupWalksTheTree:
    """`TemporaryDirectory.cleanup()` | O(m): one removal per entry, whatever
    the tree's shape; errors are handled as the row says."""

    @pytest.mark.parametrize(("files", "subdirectories"), [(10, 1), (1_000, 10)])
    def test_one_removal_per_entry(
        self,
        files: int,
        subdirectories: int,
        tmp_path: pathlib.Path,
        count: Callable[[str], Counter],
    ) -> None:
        with tempfile.TemporaryDirectory(dir=tmp_path) as name:
            build_tree(pathlib.Path(name), files, subdirectories)
            unlinks = count("unlink")
            rmdirs = count("rmdir")

        assert not os.path.exists(name)
        assert unlinks.calls == files
        assert rmdirs.calls == subdirectories + 1

    def test_cleanup_runs_when_the_block_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(RuntimeError), tempfile.TemporaryDirectory(dir=tmp_path) as name:
            (pathlib.Path(name) / "partial").touch()
            raise RuntimeError

        assert list(tmp_path.iterdir()) == []

    def test_a_second_cleanup_does_nothing(
        self, tmp_path: pathlib.Path, count: Callable[[str], Counter]
    ) -> None:
        directory = tempfile.TemporaryDirectory(dir=tmp_path)
        directory.cleanup()
        rmdirs = count("rmdir")

        directory.cleanup()

        assert rmdirs.calls == 0

    def test_collection_cleans_up_with_a_warning(self, tmp_path: pathlib.Path) -> None:
        directory = tempfile.TemporaryDirectory(dir=tmp_path)
        (pathlib.Path(directory.name) / "file").touch()

        with pytest.warns(ResourceWarning, match="Implicitly cleaning up"):
            del directory
            gc.collect()

        assert list(tmp_path.iterdir()) == []

    def test_with_binds_the_name(self, tmp_path: pathlib.Path) -> None:
        directory = tempfile.TemporaryDirectory(dir=tmp_path)
        with directory as name:
            assert name == directory.name
            assert isinstance(name, str)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="delete is 3.12+")
    def test_delete_false_leaves_the_tree(self, tmp_path: pathlib.Path) -> None:
        directory = tempfile.TemporaryDirectory(dir=tmp_path, delete=False)  # type: ignore[call-arg]
        with directory as name:
            (pathlib.Path(name) / "kept").touch()
        del directory
        gc.collect()

        assert (pathlib.Path(name) / "kept").exists()
        shutil.rmtree(name)

    @pytest.mark.skipif(
        sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX permissions, not root"
    )
    def test_a_read_only_subdirectory_is_handled(self, tmp_path: pathlib.Path) -> None:
        def locked_tree(root: pathlib.Path) -> None:
            (root / "locked").mkdir()
            (root / "locked" / "file").touch()
            (root / "locked").chmod(stat.S_IRUSR | stat.S_IXUSR)

        plain = tmp_path / "plain"
        plain.mkdir()
        locked_tree(plain)
        with pytest.raises(PermissionError):
            shutil.rmtree(plain)
        (plain / "locked").chmod(stat.S_IRWXU)

        with tempfile.TemporaryDirectory(dir=tmp_path) as name:
            locked_tree(pathlib.Path(name))

        assert not os.path.exists(name)

    @pytest.mark.parametrize("ignore", [False, True])
    def test_ignore_cleanup_errors(
        self, ignore: bool, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        directory = tempfile.TemporaryDirectory(dir=tmp_path, ignore_cleanup_errors=ignore)
        (pathlib.Path(directory.name) / "file").touch()
        real_rmdir = os.rmdir

        def busy_root(path: Any, *args: Any, **kwargs: Any) -> None:
            if os.fspath(path) == directory.name:
                raise OSError(errno.EBUSY, "busy", path)
            real_rmdir(path, *args, **kwargs)

        monkeypatch.setattr(os, "rmdir", busy_root)

        if ignore:
            directory.cleanup()
        else:
            with pytest.raises(OSError, match="busy"):
                directory.cleanup()

        assert os.listdir(directory.name) == []
        monkeypatch.undo()
        os.rmdir(directory.name)


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
        env={**os.environ, "TMPDIR": str(cwd)},
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _needs_312(source: str) -> bool:
    """The block using the 3.12 arguments `delete_on_close` and `delete`."""
    return "delete_on_close" in source


class TestDocumentedExamples:
    """Each block runs in its own subprocess with `TMPDIR` pointing at its own
    working directory, which must hold nothing but the script afterwards.
    The block using the 3.12 arguments is skipped on earlier versions."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS
        assert sum(_needs_312(source) for _, source in _blocks()) == 1

    def test_every_block_runs_and_leaves_nothing_behind(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if _needs_312(source) and sys.version_info < (3, 12):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")
            leftovers = sorted(os.listdir(workdir))
            if leftovers != ["block.py"]:
                failures.append(f"{PAGE.name}:{line} left {leftovers}")

        assert ran == EXPECTED_BLOCKS - (sys.version_info < (3, 12))
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert spool.name is None" in s)
        mutated = source.replace("assert spool.name is None", "assert spool.name is not None", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
