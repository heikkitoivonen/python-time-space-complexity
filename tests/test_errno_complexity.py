"""Tests for docs/stdlib/errno.md.

The page prices the module as a table built at import: constants are module
attributes, `errorcode` is one dictionary from number to name, and matching an
`OSError` is an integer compare or the subclass `OSError` picked when it was
built. Nothing on the page has a size term except iterating `errorcode`, so the
claims are settled by observation - identity, dictionary contents, the type an
`OSError` construction returns - with no timing and no tolerance.

Measurement scope:

* `errno.errorcode` is the same object on every access, and a lookup returns
  the same string object each time, so neither access copies anything.
* One name per number: `len(errorcode)` equals the number of distinct values
  among the module's `E*` and `WSA*` names, every such name's value is a key,
  and the name stored there carries the same value. Iterating `errorcode`
  yields integers. On Linux and macOS `EWOULDBLOCK` is asserted to equal
  `EAGAIN`, so the two share one entry.
* `OSError(code, strerror)` is asserted to return the subclass for each number
  mapped in Objects/exceptions.c that every supported platform defines,
  `BlockingIOError` for both `EAGAIN` and `EWOULDBLOCK` included, and plain
  `OSError` for `EIO` and `ENOSPC`. A real failed `open()` of a missing file is
  asserted to carry `ENOENT` in `.errno`, and an `OSError` built from a message
  alone to carry `None`.
* The module defines only `E*` and `WSA*` names besides `errorcode`, which is
  what the page's `dir(errno)` filter relies on.
* On Linux, `EQFULL` (a macOS code) is asserted absent; `EAGAIN` is 11 on
  Linux x86-64 and arm64 and 35 on macOS, so one name has different numbers.
  Other Linux architectures (Alpha, SPARC) number it differently and skip. On Windows the socket names take their Winsock values
  (`ECONNRESET == WSAECONNRESET`, from Modules/errnomodule.c's `#undef` of the
  CRT's values) and `OSError(errno.ECONNRESET, ...)` is still
  `ConnectionResetError`, because Objects/exceptions.c undefines the same names.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The Windows-only rows (`WSAE*` names and the Winsock values of the socket
  names) and the macOS value of `EAGAIN` skip on Linux, where this suite is
  run locally; CI runs them on their own platforms.
* That building the table happens once at import is read from
  Modules/errnomodule.c's `errno_exec`; the module has no functions, so there
  is no later work to observe.
* Which of two aliased names `errorcode` keeps is source order in
  Modules/errnomodule.c and differs by platform; the page and the tests claim
  only that one of them is kept.
"""

from __future__ import annotations

import errno
import pathlib
import platform
import re
import subprocess
import sys
import textwrap

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "errno.md"
EXPECTED_BLOCKS = 3

NAMES = [name for name in dir(errno) if name.startswith(("E", "WSA"))]

# Objects/exceptions.c's errnomap, restricted to names every supported platform defines.
SUBCLASSES = {
    "EAGAIN": BlockingIOError,
    "EALREADY": BlockingIOError,
    "EINPROGRESS": BlockingIOError,
    "EWOULDBLOCK": BlockingIOError,
    "EPIPE": BrokenPipeError,
    "ESHUTDOWN": BrokenPipeError,
    "ECHILD": ChildProcessError,
    "ECONNABORTED": ConnectionAbortedError,
    "ECONNREFUSED": ConnectionRefusedError,
    "ECONNRESET": ConnectionResetError,
    "EEXIST": FileExistsError,
    "ENOENT": FileNotFoundError,
    "EISDIR": IsADirectoryError,
    "ENOTDIR": NotADirectoryError,
    "EINTR": InterruptedError,
    "EACCES": PermissionError,
    "EPERM": PermissionError,
    "ESRCH": ProcessLookupError,
    "ETIMEDOUT": TimeoutError,
}


class TestConstantsAreModuleAttributes:
    """`errno.E*` | O(1) | O(1): a module attribute, absent where the platform
    lacks the name."""

    def test_every_name_is_an_int(self) -> None:
        assert NAMES
        assert all(type(getattr(errno, name)) is int for name in NAMES)

    def test_nothing_but_errorcode_and_the_codes_is_public(self) -> None:
        public = {name for name in dir(errno) if not name.startswith("_")}

        assert public == {"errorcode", *NAMES}

    @pytest.mark.skipif(
        sys.platform != "linux", reason="platform: Linux's errno.h has no EQFULL, a macOS code"
    )
    def test_a_name_the_platform_lacks_is_not_defined(self) -> None:
        assert not hasattr(errno, "EQFULL")
        with pytest.raises(AttributeError):
            errno.EQFULL  # noqa: B018  # pyright: ignore[reportAttributeAccessIssue]

    @pytest.mark.skipif(
        sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"},
        reason="platform: Linux's asm-generic errno table, used on x86-64 and arm64, numbers EAGAIN 11",
    )
    def test_eagain_is_11_on_generic_linux(self) -> None:
        assert errno.EAGAIN == 11

    @pytest.mark.skipif(
        sys.platform != "darwin", reason="platform: macOS's sys/errno.h numbers EAGAIN 35"
    )
    def test_eagain_is_35_on_macos(self) -> None:
        assert errno.EAGAIN == 35


class TestErrorcodeIsOneDictionary:
    """`errno.errorcode` | O(1) | O(1), `errorcode[code]` | O(1) | O(1), and
    iterating it is O(v) over numbers, one name per number."""

    def test_access_returns_the_same_dictionary(self) -> None:
        assert errno.errorcode is errno.errorcode
        assert type(errno.errorcode) is dict

    def test_a_lookup_returns_the_stored_name(self) -> None:
        assert errno.errorcode[errno.ENOENT] == "ENOENT"
        assert errno.errorcode[errno.ENOENT] is errno.errorcode[errno.ENOENT]

    def test_one_entry_per_distinct_number(self) -> None:
        values = {getattr(errno, name) for name in NAMES}

        assert set(errno.errorcode) == values
        assert len(errno.errorcode) == len(values)

    def test_the_stored_name_carries_the_number(self) -> None:
        for name in NAMES:
            code = getattr(errno, name)
            assert getattr(errno, errno.errorcode[code]) == code, name

    def test_iterating_yields_numbers(self) -> None:
        assert all(type(code) is int for code in errno.errorcode)
        assert all(type(name) is str for name in errno.errorcode.values())

    @pytest.mark.skipif(
        sys.platform not in {"linux", "darwin"},
        reason="platform: Linux and macOS define EWOULDBLOCK as EAGAIN; Winsock does not",
    )
    def test_aliases_share_one_entry(self) -> None:
        assert errno.EWOULDBLOCK == errno.EAGAIN
        assert errno.errorcode[errno.EWOULDBLOCK] in {"EWOULDBLOCK", "EAGAIN"}
        assert len(errno.errorcode) < len(NAMES)


class TestOSErrorPicksItsSubclass:
    """`OSError(code, strerror)` | O(1): the number picks the subclass, so
    catching it is the same test as comparing `.errno`."""

    @pytest.mark.parametrize("name", sorted(SUBCLASSES))
    def test_a_mapped_number_builds_its_subclass(self, name: str) -> None:
        error = OSError(getattr(errno, name), "message")

        assert type(error) is SUBCLASSES[name]
        assert error.errno == getattr(errno, name)

    @pytest.mark.parametrize("name", ["EIO", "ENOSPC"])
    def test_an_unmapped_number_stays_oserror(self, name: str) -> None:
        assert type(OSError(getattr(errno, name), "message")) is OSError

    def test_a_real_failure_carries_the_number(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError) as caught:
            (tmp_path / "missing.txt").open()

        assert caught.value.errno == errno.ENOENT

    def test_an_oserror_built_from_a_message_has_no_number(self) -> None:
        assert OSError("message").errno is None


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="platform: only Windows's errno module substitutes Winsock values for socket names",
)
class TestWindowsSocketNames:
    """`errno.WSAE*` | Windows only; the socket names take their values."""

    def test_socket_names_take_winsock_values(self) -> None:
        assert errno.ECONNRESET == errno.WSAECONNRESET  # type: ignore[attr-defined]
        assert errno.EWOULDBLOCK == errno.WSAEWOULDBLOCK  # type: ignore[attr-defined]

    def test_the_subclass_mapping_uses_the_same_values(self) -> None:
        assert type(OSError(errno.ECONNRESET, "message")) is ConnectionResetError


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
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "is FileNotFoundError" in s)
        mutated = source.replace("is FileNotFoundError", "is PermissionError", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
