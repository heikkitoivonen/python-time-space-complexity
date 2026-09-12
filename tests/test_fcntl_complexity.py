"""Tests for docs/stdlib/fcntl.md.

Modules/fcntlmodule.c is four thin wrappers, and the page's rows are the
copies they make around the system call, which are all observable without a
stopwatch:

* `fcntl()` with a bytes-like or str argument copies it into a 1024-byte stack
  buffer and returns the buffer as a new `bytes` of the argument's length: the
  result is a distinct object of equal length at 2, 64 and 1,024 bytes (one-byte
  `bytes` objects are interned, so length 1 cannot show the copy), a str
  comes back as its UTF-8 encoding, and 1,025 bytes raise ValueError. `F_GETFL`
  is used as the command because the kernel ignores its argument, so the
  buffer comes back unchanged at any size. The same limit applies on every
  supported version (`sizeof buf` on 3.10, `FCNTL_BUFSZ` from 3.14). Before
  3.14 the argument is parsed with `s#`, which takes str and `bytes` only, so a
  `bytearray` raises TypeError there and is copied like `bytes` from 3.14.
* `ioctl()` has three shapes. An integer argument is passed by value. A
  read-only buffer, or any buffer with `mutate_flag=False`, is copied like
  `fcntl()`'s and returned as new `bytes`. A writable buffer with the default
  `mutate_flag=True` is changed in place and the integer result returned; up
  to 1024 bytes it goes through the stack buffer and back, past that the
  source hands the caller's buffer to the kernel directly. From Python the
  two mutating paths look the same, so the tests observe the one difference:
  a 1,025-byte bytearray works when mutated and raises ValueError when it is
  not. `FIONREAD` on a pipe
  holding five bytes is the request, because the count it writes is checkable,
  and `FIOCLEX` is the integer-free request, checked through the descriptor's
  inheritable flag.
* `flock()` locks the open file description: a second `open()` of the same
  file in the same process gets BlockingIOError with `LOCK_NB`, and without it
  a thread stays in the call until the holder unlocks. The waiting thread
  signals just before it calls, and the test then gives it 0.3 s to come back
  wrongly; a thread descheduled for that long passes the test rather than
  failing it, so the negative half is weaker than the positive one, which
  allows 30 s for the return after the release. Closing a third
  descriptor of the file does not release it, and a read-only descriptor can
  take an exclusive lock.
* `lockf()` is `fcntl(F_SETLK/F_SETLKW)` with a `struct flock`, so the lock is
  the process's: a second descriptor in the same process acquires it at once,
  a child process cannot, closing an unrelated descriptor of the same file in
  the holding process releases it, an exclusive lock on a read-only descriptor
  fails with EBADF, and without `LOCK_NB` a thread stays in the call until a
  child that holds the lock exits.

The table's coverage is pinned against `dir(fcntl)`: every public name the
running interpreter exposes has a row, and every name a row mentions is one
Modules/fcntlmodule.c can define, listed here by name. Which of those the
interpreter has depends on the platform and kernel headers it was built
against, so the tests do not assert any particular one exists; they do assert
that names first exposed by 3.11, 3.12, 3.13 and 3.14 are absent on older
interpreters, and that their rows say which version added them.

Both code blocks on the page run from a temporary directory. The first
replaces whatever data.txt held with 'Protected data'. Run with `fcntl.flock`
replaced by a spy that reads the file at every call, it shows the old contents
still intact when LOCK_EX is taken and the new contents in place at LOCK_UN,
and the same block with its `flush()` line removed shows an empty file at
LOCK_UN. The second block prints that the file is locked elsewhere.

Not settled by running code:

* The STREAMS `I_*` requests, `LOCK_MAND` and the mandatory-lock flags, and the
  macOS, FreeBSD, NetBSD and AIX commands: the suite runs on Linux, where the
  interpreter may not define them and the kernel does not implement them.
* `flock()`'s emulation through `fcntl()` on systems built without flock(2),
  which the page notes and Linux never takes.
* "One system call" counts the kernel as constant. What the kernel does with a
  lock table or a driver's ioctl handler is not measured.
"""

import errno
import fcntl
import os
import pathlib
import re
import select
import struct
import subprocess
import sys
import termios
import textwrap
import threading
from collections.abc import Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "fcntl.md"

EXPECTED_BLOCKS = 2

KNOWN_CONSTANTS = frozenset(
    """
    DN_ACCESS DN_ATTRIB DN_CREATE DN_DELETE DN_MODIFY DN_MULTISHOT DN_RENAME FASYNC
    FD_CLOEXEC FICLONE FICLONERANGE F_ADD_SEALS F_CLOSEM F_DUP2FD F_DUP2FD_CLOEXEC
    F_DUPFD F_DUPFD_CLOEXEC F_DUPFD_QUERY F_EXLCK F_FULLFSYNC F_GETFD F_GETFL
    F_GETLEASE F_GETLK F_GETLK64 F_GETNOSIGPIPE F_GETOWN F_GETOWN_EX F_GETPATH
    F_GETPIPE_SZ F_GETSIG F_GET_FILE_RW_HINT F_GET_RW_HINT F_GET_SEALS F_ISUNIONSTACK
    F_KINFO F_MAXFD F_NOCACHE F_NOTIFY F_OFD_GETLK F_OFD_SETLK F_OFD_SETLKW
    F_OWNER_PGRP F_OWNER_PID F_OWNER_TID F_RDAHEAD F_RDLCK F_READAHEAD
    F_SEAL_FUTURE_WRITE F_SEAL_GROW F_SEAL_SEAL F_SEAL_SHRINK F_SEAL_WRITE F_SETFD
    F_SETFL F_SETLEASE F_SETLK F_SETLK64 F_SETLKW F_SETLKW64 F_SETNOSIGPIPE F_SETOWN
    F_SETOWN_EX F_SETPIPE_SZ F_SETSIG F_SET_FILE_RW_HINT F_SET_RW_HINT F_SHLCK
    F_UNLCK F_WRLCK I_ATMARK I_CANPUT I_CKBAND I_FDINSERT I_FIND I_FLUSH I_FLUSHBAND
    I_GETBAND I_GETCLTIME I_GETSIG I_GRDOPT I_GWROPT I_LINK I_LIST I_LOOK I_NREAD
    I_PEEK I_PLINK I_POP I_PUNLINK I_PUSH I_RECVFD I_SENDFD I_SETCLTIME I_SETSIG
    I_SRDOPT I_STR I_SWROPT I_UNLINK LOCK_EX LOCK_MAND LOCK_NB LOCK_READ LOCK_RW
    LOCK_SH LOCK_UN LOCK_WRITE RWH_WRITE_LIFE_EXTREME RWH_WRITE_LIFE_LONG
    RWH_WRITE_LIFE_MEDIUM RWH_WRITE_LIFE_NONE RWH_WRITE_LIFE_NOT_SET
    RWH_WRITE_LIFE_SHORT
    """.split()
)
"""Every constant Modules/fcntlmodule.c can define on the 3.14 branch, each under an #ifdef."""

FUNCTIONS = frozenset({"fcntl", "ioctl", "flock", "lockf"})

ADDED_IN: dict[tuple[int, int], frozenset[str]] = {
    (3, 11): frozenset({"F_DUP2FD", "F_DUP2FD_CLOEXEC"}),
    (3, 12): frozenset({"FICLONE", "FICLONERANGE"}),
    (3, 13): frozenset(
        {
            "F_CLOSEM",
            "F_GETNOSIGPIPE",
            "F_GETOWN_EX",
            "F_GET_FILE_RW_HINT",
            "F_GET_RW_HINT",
            "F_ISUNIONSTACK",
            "F_KINFO",
            "F_MAXFD",
            "F_OWNER_PGRP",
            "F_OWNER_PID",
            "F_OWNER_TID",
            "F_RDAHEAD",
            "F_READAHEAD",
            "F_SEAL_FUTURE_WRITE",
            "F_SETNOSIGPIPE",
            "F_SETOWN_EX",
            "F_SET_FILE_RW_HINT",
            "F_SET_RW_HINT",
            "RWH_WRITE_LIFE_EXTREME",
            "RWH_WRITE_LIFE_LONG",
            "RWH_WRITE_LIFE_MEDIUM",
            "RWH_WRITE_LIFE_NONE",
            "RWH_WRITE_LIFE_NOT_SET",
            "RWH_WRITE_LIFE_SHORT",
        }
    ),
    (3, 14): frozenset({"F_DUPFD_QUERY"}),
}
"""Constants by the release whose Modules/fcntlmodule.c first exposes them."""

BUFFER_LIMIT = 1024
"""The stack buffer a bytes-like argument is copied through, in bytes."""

INT = struct.calcsize("i")
PIPE_PAYLOAD = b"hello"

LOCK_PROBE = textwrap.dedent(
    """
    import errno
    import fcntl
    import sys

    with open(sys.argv[1], "r+") as f:
        try:
            fcntl.lockf(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            print("busy")
        else:
            print("locked")
    """
)
"""A child process that reports whether it can take the exclusive lockf() lock."""

LOCK_HOLDER = textwrap.dedent(
    """
    import fcntl
    import sys

    f = open(sys.argv[1], "r+")
    fcntl.lockf(f.fileno(), fcntl.LOCK_EX)
    print("held", flush=True)
    sys.stdin.read()
    """
)
"""A child process that holds the exclusive lockf() lock until its stdin closes."""


def _public_names() -> set[str]:
    return {name for name in dir(fcntl) if not name.startswith("_")}


def _table() -> str:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n## ", start)
    return text[start:end]


def _documented_names() -> set[str]:
    """Every `fcntl.<name>` the Complexity Reference table mentions."""
    return set(re.findall(r"`fcntl\.([A-Za-z_][A-Za-z0-9_]*)", _table()))


def _rows_naming(name: str) -> list[str]:
    return [row for row in _table().splitlines() if f"`fcntl.{name}`" in row]


def _another_process_can_lock(path: pathlib.Path) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", LOCK_PROBE, str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return result.stdout.strip() == "locked"


@pytest.fixture
def locked_file(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "locked.txt"
    path.write_bytes(b"")
    return path


@pytest.fixture
def pipe_holding_bytes() -> Iterator[int]:
    """The read end of a pipe with PIPE_PAYLOAD waiting in it."""
    read_end, write_end = os.pipe()
    try:
        os.write(write_end, PIPE_PAYLOAD)
        yield read_end
    finally:
        os.close(read_end)
        os.close(write_end)


def _wait_in_thread(call: Any) -> tuple[threading.Thread, threading.Event, threading.Event]:
    """Run `call` in a thread; one event is set just before it, the other once it returns."""
    started = threading.Event()
    done = threading.Event()

    def run() -> None:
        started.set()
        call()
        done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, started, done


WAIT_GRACE = 0.3
"""How long a waiter that should be blocked is given to come back wrongly."""

WAIT_LIMIT = 30
"""How long a waiter that should be released is given to come back."""


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `fcntl`.

    Every constant the module defines is under an #ifdef, so which ones the
    running interpreter has is a property of the platform it was built on.
    The table must cover whatever this one has, and may only name attributes
    some build can have.
    """

    def test_no_public_name_is_missing_from_the_table(self) -> None:
        missing = sorted(_public_names() - _documented_names())

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_the_table_names_nothing_the_module_cannot_define(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - FUNCTIONS - KNOWN_CONSTANTS)

        assert not unknown, f"the table names attributes fcntl cannot have: {unknown}"

    def test_the_known_constants_are_the_module_sources_list(self) -> None:
        """Nothing the interpreter has may be missing from the allowlist either."""
        constants = _public_names() - FUNCTIONS

        assert constants <= KNOWN_CONSTANTS, sorted(constants - KNOWN_CONSTANTS)
        assert FUNCTIONS <= _public_names()

    @pytest.mark.parametrize("version", sorted(ADDED_IN))
    def test_names_added_later_are_absent_before_their_release(
        self, version: tuple[int, int]
    ) -> None:
        if sys.version_info >= version:
            pytest.skip(f"{sys.version_info[:2]} may define these")

        present = sorted(ADDED_IN[version] & _public_names())

        assert not present, f"{version} names present on {sys.version_info[:2]}: {present}"

    @pytest.mark.parametrize("version", sorted(ADDED_IN))
    def test_rows_for_later_names_say_which_release_added_them(
        self, version: tuple[int, int]
    ) -> None:
        marker = f"Python {version[0]}.{version[1]}+"
        for name in sorted(ADDED_IN[version]):
            rows = _rows_naming(name)
            assert len(rows) == 1, f"expected one row naming {name}, found {len(rows)}"
            assert marker in rows[0], f"the {name} row should say {marker}: {rows[0]}"

    def test_names_present_on_every_supported_version_are_not_marked(self) -> None:
        later = frozenset().union(*ADDED_IN.values())
        for name in sorted(KNOWN_CONSTANTS - later):
            rows = _rows_naming(name)
            assert len(rows) == 1, f"expected one row naming {name}, found {len(rows)}"
            assert "Python 3." not in rows[0], f"the {name} row carries a version: {rows[0]}"

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert FUNCTIONS | {"LOCK_EX", "F_GETFL", "I_PUSH"} <= documented, (
            "the extractor missed rows that are certainly on the page"
        )
        assert _public_names() - (documented - {"flock"}) == {"flock"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestFcntl:
    """A bytes-like argument is copied in and copied out; an integer is not."""

    def test_an_integer_argument_returns_the_calls_integer(self, tmp_path: pathlib.Path) -> None:
        with open(tmp_path / "f", "w") as f:
            flags = fcntl.fcntl(f.fileno(), fcntl.F_GETFL)

        assert isinstance(flags, int)
        assert flags & os.O_ACCMODE == os.O_WRONLY

    @pytest.mark.parametrize("length", [2, 64, BUFFER_LIMIT])
    def test_a_bytes_argument_comes_back_as_new_bytes_of_its_length(
        self, tmp_path: pathlib.Path, length: int
    ) -> None:
        arg = bytes(range(256)) * (length // 256) + bytes(range(length % 256))
        assert len(arg) == length
        with open(tmp_path / "f", "w") as f:
            result = fcntl.fcntl(f.fileno(), fcntl.F_GETFL, arg)

        assert type(result) is bytes
        assert result == arg, "F_GETFL ignores its argument, so the copy is unchanged"
        assert result is not arg, "the result is a copy, not the argument handed back"

    def test_a_str_argument_is_copied_as_its_utf8_encoding(self, tmp_path: pathlib.Path) -> None:
        with open(tmp_path / "f", "w") as f:
            result = fcntl.fcntl(f.fileno(), fcntl.F_GETFL, "héllo")

        assert result == "héllo".encode()

    def test_a_bytearray_is_accepted_only_from_314(self, tmp_path: pathlib.Path) -> None:
        with open(tmp_path / "f", "w") as f:
            if sys.version_info >= (3, 14):
                assert fcntl.fcntl(f.fileno(), fcntl.F_GETFL, bytearray(b"ab")) == b"ab"
            else:
                with pytest.raises(TypeError):
                    fcntl.fcntl(f.fileno(), fcntl.F_GETFL, bytearray(b"ab"))

    def test_one_byte_past_the_limit_raises(self, tmp_path: pathlib.Path) -> None:
        with open(tmp_path / "f", "w") as f:
            with pytest.raises(ValueError):
                fcntl.fcntl(f.fileno(), fcntl.F_GETFL, bytes(BUFFER_LIMIT + 1))


class TestIoctl:
    """Three shapes: by value, copied in and out, or the caller's buffer in place."""

    def test_an_integer_free_request_returns_the_calls_integer(
        self, tmp_path: pathlib.Path
    ) -> None:
        with open(tmp_path / "f", "w") as f:
            fd = f.fileno()
            os.set_inheritable(fd, True)

            result = fcntl.ioctl(fd, termios.FIOCLEX)

            assert result == 0
            assert os.get_inheritable(fd) is False

    def test_a_read_only_buffer_comes_back_as_new_bytes(self, pipe_holding_bytes: int) -> None:
        arg = bytes(INT)

        result = fcntl.ioctl(pipe_holding_bytes, termios.FIONREAD, arg)

        assert type(result) is bytes
        assert result is not arg
        assert struct.unpack("i", result) == (len(PIPE_PAYLOAD),)
        assert arg == bytes(INT), "the argument itself is untouched"

    def test_a_writable_buffer_is_changed_in_place(self, pipe_holding_bytes: int) -> None:
        buffer = bytearray(INT)

        result = fcntl.ioctl(pipe_holding_bytes, termios.FIONREAD, buffer)

        assert result == 0
        assert struct.unpack("i", buffer) == (len(PIPE_PAYLOAD),)

    def test_mutate_flag_false_copies_a_writable_buffer_instead(
        self, pipe_holding_bytes: int
    ) -> None:
        buffer = bytearray(INT)

        result = fcntl.ioctl(pipe_holding_bytes, termios.FIONREAD, buffer, False)

        assert type(result) is bytes
        assert struct.unpack("i", result) == (len(PIPE_PAYLOAD),)
        assert buffer == bytearray(INT), "the caller's buffer is left alone"

    def test_a_writable_buffer_past_the_limit_is_still_accepted(
        self, pipe_holding_bytes: int
    ) -> None:
        """The cap belongs to the copy, and the source makes none for this shape."""
        buffer = bytearray(BUFFER_LIMIT + 1)

        result = fcntl.ioctl(pipe_holding_bytes, termios.FIONREAD, buffer)

        assert result == 0
        assert struct.unpack("i", buffer[:INT]) == (len(PIPE_PAYLOAD),)

    def test_the_copying_paths_stop_at_the_limit(self, pipe_holding_bytes: int) -> None:
        with pytest.raises(ValueError):
            fcntl.ioctl(pipe_holding_bytes, termios.FIONREAD, bytes(BUFFER_LIMIT + 1))
        with pytest.raises(ValueError):
            fcntl.ioctl(pipe_holding_bytes, termios.FIONREAD, bytearray(BUFFER_LIMIT + 1), False)


class TestFlock:
    """The lock belongs to the open file description."""

    def test_a_second_open_of_the_file_contends_in_the_same_process(
        self, locked_file: pathlib.Path
    ) -> None:
        with open(locked_file) as holder, open(locked_file) as other:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)

            with pytest.raises(BlockingIOError):
                fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
            fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_without_lock_nb_the_call_waits_for_the_release(
        self, locked_file: pathlib.Path
    ) -> None:
        with open(locked_file) as holder, open(locked_file) as other:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
            thread, started, done = _wait_in_thread(
                lambda: fcntl.flock(other.fileno(), fcntl.LOCK_EX)
            )
            try:
                assert started.wait(WAIT_LIMIT)
                assert not done.wait(WAIT_GRACE), "the waiter returned while the lock was held"

                fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
                assert done.wait(WAIT_LIMIT), "the waiter did not return after the release"
            finally:
                fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
                thread.join(WAIT_LIMIT)

    def test_closing_another_descriptor_does_not_release_it(
        self, locked_file: pathlib.Path
    ) -> None:
        with open(locked_file) as holder, open(locked_file) as other:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
            open(locked_file).close()

            with pytest.raises(BlockingIOError):
                fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_an_exclusive_lock_does_not_need_write_access(self, locked_file: pathlib.Path) -> None:
        with open(locked_file) as read_only:
            fcntl.flock(read_only.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


class TestLockf:
    """The lock belongs to the process."""

    def test_a_second_descriptor_in_the_same_process_never_contends(
        self, locked_file: pathlib.Path
    ) -> None:
        with open(locked_file, "r+") as holder, open(locked_file, "r+") as other:
            fcntl.lockf(holder.fileno(), fcntl.LOCK_EX)

            fcntl.lockf(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_another_process_does(self, locked_file: pathlib.Path) -> None:
        assert _another_process_can_lock(locked_file)

        with open(locked_file, "r+") as holder:
            fcntl.lockf(holder.fileno(), fcntl.LOCK_EX)

            assert not _another_process_can_lock(locked_file)

        assert _another_process_can_lock(locked_file)

    def test_closing_any_descriptor_of_the_file_releases_it(
        self, locked_file: pathlib.Path
    ) -> None:
        with open(locked_file, "r+") as holder:
            fcntl.lockf(holder.fileno(), fcntl.LOCK_EX)
            assert not _another_process_can_lock(locked_file)

            open(locked_file).close()

            assert _another_process_can_lock(locked_file), (
                "closing an unrelated descriptor dropped the process's lock"
            )

    def test_an_exclusive_lock_needs_write_access(self, locked_file: pathlib.Path) -> None:
        with open(locked_file) as read_only:
            with pytest.raises(OSError) as excinfo:
                fcntl.lockf(read_only.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        assert excinfo.value.errno == errno.EBADF

    def test_without_lock_nb_the_call_waits_for_the_holder(self, locked_file: pathlib.Path) -> None:
        with subprocess.Popen(
            [sys.executable, "-c", LOCK_HOLDER, str(locked_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        ) as holder:
            assert holder.stdin is not None and holder.stdout is not None
            thread: threading.Thread | None = None
            try:
                readable, _, _ = select.select([holder.stdout], [], [], WAIT_LIMIT)
                assert readable, "the child did not report holding the lock"
                assert holder.stdout.readline().strip() == "held"
                with open(locked_file, "r+") as waiter:
                    thread, started, done = _wait_in_thread(
                        lambda: fcntl.lockf(waiter.fileno(), fcntl.LOCK_EX)
                    )
                    assert started.wait(WAIT_LIMIT)
                    assert not done.wait(WAIT_GRACE), "the waiter returned while the child held"

                    holder.stdin.close()
                    assert holder.wait(timeout=WAIT_LIMIT) == 0
                    assert done.wait(WAIT_LIMIT), "the waiter did not return after the child exited"
                    thread.join(WAIT_LIMIT)
            finally:
                if holder.poll() is None:
                    holder.kill()
                    holder.wait()
                if thread is not None:
                    thread.join(WAIT_LIMIT)


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


def _seen_at_each_flock(
    source: str, cwd: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[int, str]]:
    """Run a block in-process, reading data.txt through a fresh descriptor at each flock()."""
    seen: list[tuple[int, str]] = []
    real_flock = fcntl.flock

    def spy(fd: int, operation: int) -> None:
        seen.append((operation, (cwd / "data.txt").read_text()))
        real_flock(fd, operation)

    with monkeypatch.context() as patch:
        patch.setattr(fcntl, "flock", spy)
        patch.chdir(cwd)
        exec(compile(source, "<block>", "exec"), {"__name__": "__main__"})
    return seen


class TestDocumentedExamples:
    """Both blocks run from a temporary directory and do what their prose says."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_the_locking_block_replaces_the_data(self, tmp_path: pathlib.Path) -> None:
        line, source = _blocks()[0]
        (tmp_path / "data.txt").write_text("old contents")

        result = _run(source, tmp_path)

        assert result.returncode == 0, f"{PAGE.name}:{line} raised: {result.stderr.strip()}"
        assert (tmp_path / "data.txt").read_text() == "Protected data"

    def test_the_non_blocking_block_finds_the_file_locked(self, tmp_path: pathlib.Path) -> None:
        line, source = _blocks()[1]

        result = _run(source, tmp_path)

        assert result.returncode == 0, f"{PAGE.name}:{line} raised: {result.stderr.strip()}"
        assert result.stdout.strip() == "File is locked elsewhere"

    def test_the_locking_block_changes_the_file_only_while_it_holds_the_lock(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Opening without truncation keeps the old data until LOCK_EX; `flush()` lands the new
        data before LOCK_UN."""
        _, source = _blocks()[0]
        without_flush = source.replace("        f.flush()\n", "", 1)
        assert without_flush != source, "the mutation did not remove the flush"

        (tmp_path / "data.txt").write_text("old contents")
        assert _seen_at_each_flock(source, tmp_path, monkeypatch) == [
            (fcntl.LOCK_EX, "old contents"),
            (fcntl.LOCK_UN, "Protected data"),
        ]

        (tmp_path / "data.txt").write_text("old contents")
        assert _seen_at_each_flock(without_flush, tmp_path, monkeypatch) == [
            (fcntl.LOCK_EX, "old contents"),
            (fcntl.LOCK_UN, ""),
        ]

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        _, original = _blocks()[0]
        broken = original.replace("import fcntl\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
