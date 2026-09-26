"""Tests for docs/stdlib/platform.md.

The page prices the module by what each call has to ask the system for - a
system call, a file read or a subprocess - and by whether the answer is cached.
Those are settled by observation, which needs no tolerance: a recording
`subprocess.check_output` counts the commands a call runs, a recording `open`
and file object count reads, a counting dictionary counts cache fills, and
identity checks show a cached object coming back.

Measurement scope:

* `uname()` is asserted to call `os.uname()` once and run no subprocess on a
  cold cache, and to return the same object on a second call with no further
  `os.uname()`. On a result built directly, reading the five
  `os.uname()` fields runs nothing, the first `processor` access runs `uname -p`
  once and a second runs nothing; iterating, unpacking, indexing and `len()`
  each run it once on a fresh result. `system()`, `node()`, `release()`,
  `version()` and `machine()` are asserted to return the cached result's own
  field objects, and `processor()` to run `uname -p` on its first call only.
* `platform()` is driven with `uname()` replaced by an unresolved Linux result
  and by a FreeBSD one, on a Linux host with the command runner faked; the
  commands are recorded with their flags. On Linux the first call runs `uname -p` alone and
  calls `libc_ver()` once, a second returns the same string with no command,
  and a second argument pair fills its own cache entry with no command and one
  more `libc_ver()`. On FreeBSD a non-terse first call
  also runs `file`, and a terse one does not.
* `architecture()` is asserted to run `file` once per call over two calls.
* `libc_ver()` with no argument, where `os.confstr('CS_GNU_LIBC_VERSION')`
  answers, is asserted to ask `os.confstr()` for that name once and open no
  file. Given an executable of 10 and of 100
  16 KiB chunks with no libc marker, it reads 11 and 101 times. Its traced peak
  on a 1,000-chunk (16 MB) file is under twice the peak on a 10-chunk file and
  under a twentieth of the file; the peak includes the file object's buffer. A file with two `GLIBC_`
  markers 50,000 bytes apart reports the higher version in either order, with
  2.28 against 2.9 to exclude a text comparison; on 3.14+ a `musl-` marker
  reports musl.
* `freedesktop_os_release()` is pointed at a temporary file: over three calls
  it opens the file once, returns equal but distinct dictionaries, and a
  change to one does not reach the next. Files of 10 and 1,000 fields give
  dictionaries of 13 and 1,003 entries (three defaults), and a missing file
  raises `OSError`.
* The `python_*()` functions are asserted to fill the `sys.version` cache once
  across all seven of them, and `python_version()` to return the same object
  twice. `python_version_tuple()` is asserted to hold three strings.
* `invalidate_caches()` (3.14+) is asserted, with every cache filled first, to
  make the next `uname()` a new object and to empty the `platform()`,
  os-release and `sys.version` caches.
* `system_alias()` is asserted on SunOS, win32 and Linux input, with no
  command run.
* On Linux, `mac_ver()`, `win32_ver()`, `win32_edition()`, `win32_is_iot()`,
  `ios_ver()` and `android_ver()` are asserted to return their defaults with
  no command run and no file opened; `java_ver()` its defaults, with a
  `DeprecationWarning` on 3.13+. On macOS, `mac_ver()` is asserted to open
  `SystemVersion.plist` on each of two calls.
* Every fenced Python block runs in its own subprocess, so the module's caches
  start cold in each, and a mutated assertion in one of them is asserted to
  fail.

Not settled here:

* The Windows rows: that `uname()` builds its first result from
  `win32_ver()` rather than `os.uname()`, that `win32_ver()` queries WMI or
  runs `ver` on every call, and that `win32_edition()` is one registry read are
  read from Lib/platform.py; no run this project performs reaches them.
* `ios_ver()` and `android_ver()` on their own systems, and `platform()`'s
  macOS branch through `mac_ver()`, are read from Lib/platform.py. The macOS
  `mac_ver()` test runs only on macOS, which CI does not.
* `libc_ver()` without glibc scans `sys.executable`; that fallback is the same
  scan measured above with the interpreter as the file, and is not run here.
* Pricing operating-system values - `uname` fields, the plist, registry and
  WMI values - at O(1) is the page's cost model, not a measurement.
* The subprocesses' own running time is not measured; the rows count them.
* `platform()` on native macOS, FreeBSD or other Unix is not run: its generic
  branch is exercised on Linux through a replaced `uname()`.
* `libc_ver(executable)` is varied in file size only, at the default
  `chunksize`; a libc marker straddling a chunk boundary is not placed.
* The `platform()` cache key is varied in both arguments at once and in
  `terse` alone, not in `aliased` alone.
* Clearing caches in `invalidate_caches()` frees what the first calls built;
  that release is not priced.
"""

from __future__ import annotations

import os
import pathlib
import platform
import re
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "platform.md"
EXPECTED_BLOCKS = 7
CHUNK = 16384


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every command `platform` runs, and answer it without running it."""
    ran: list[str] = []

    def fake(args: list[str], *_: Any, **kwargs: Any) -> Any:
        ran.append(" ".join(args[:2]))
        out = "x86_64\n" if args[0] == "uname" else "ELF 64-bit LSB executable\n"
        return out if kwargs.get("text") else out.encode()

    monkeypatch.setattr(subprocess, "check_output", fake)
    return ran


class RecordingFile:
    def __init__(self, inner: Any, reads: list[int]) -> None:
        self._inner = inner
        self._reads = reads

    def read(self, *args: Any) -> Any:
        self._reads.append(1)
        return self._inner.read(*args)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._inner)

    def __enter__(self) -> RecordingFile:
        return self

    def __exit__(self, *exc: object) -> None:
        self._inner.close()


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[int]]:
    """Record the files `platform` opens and the reads it makes on them."""
    paths: list[str] = []
    reads: list[int] = []

    def recording_open(path: Any, *args: Any, **kwargs: Any) -> RecordingFile:
        paths.append(str(path))
        return RecordingFile(open(path, *args, **kwargs), reads)

    monkeypatch.setattr(platform, "open", recording_open, raising=False)
    return paths, reads


def fresh_result(system: str = "Linux") -> platform.uname_result:
    return platform.uname_result(system, "host", "6.1", "#1 SMP", "x86_64")


class TestUnameIsCachedAndProcessorIsLazy:
    """`uname()` is one `os.uname()` then a cached object; `processor` alone
    runs `uname -p`, on first access or on anything that walks all six fields.
    A result built directly separates the lazy field from the cache."""

    @pytest.mark.skipif(not hasattr(os, "uname"), reason="Windows has no os.uname()")
    def test_uname_runs_no_command_and_is_cached(
        self, monkeypatch: pytest.MonkeyPatch, commands: list[str]
    ) -> None:
        calls: list[int] = []
        real_uname = os.uname
        monkeypatch.setattr(os, "uname", lambda: calls.append(1) or real_uname())
        monkeypatch.setattr(platform, "_uname_cache", None)
        first = platform.uname()

        assert commands == []
        assert calls == [1]
        assert platform.uname() is first
        assert calls == [1]

    def test_named_fields_run_nothing(self, commands: list[str]) -> None:
        result = fresh_result()
        assert (result.system, result.node, result.release, result.version, result.machine) == (
            "Linux",
            "host",
            "6.1",
            "#1 SMP",
            "x86_64",
        )
        assert commands == []

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows reads WMI, not uname -p")
    def test_processor_runs_uname_once_per_result(self, commands: list[str]) -> None:
        result = fresh_result()
        assert result.processor == "x86_64"
        assert result.processor == "x86_64"
        assert commands == ["uname -p"]

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows reads WMI, not uname -p")
    @pytest.mark.parametrize(
        "walk",
        [tuple, lambda r: r[0], len, lambda r: [*r]],
        ids=["iterate", "index", "len", "unpack"],
    )
    def test_walking_all_fields_resolves_processor(
        self, commands: list[str], walk: Callable[[platform.uname_result], object]
    ) -> None:
        walk(fresh_result())
        assert commands == ["uname -p"]

    def test_field_functions_read_the_cached_result(self, commands: list[str]) -> None:
        info = platform.uname()
        assert platform.system() is info.system
        assert platform.node() is info.node
        assert platform.release() is info.release
        assert platform.version() is info.version
        assert platform.machine() is info.machine
        assert commands == []

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows reads WMI, not uname -p")
    def test_processor_function_runs_uname_on_the_first_call_only(
        self, monkeypatch: pytest.MonkeyPatch, commands: list[str]
    ) -> None:
        monkeypatch.setattr(platform, "_uname_cache", None)
        platform.processor()
        platform.processor()
        assert commands == ["uname -p"]


class TestPlatformStringIsCachedPerArguments:
    """`platform(aliased, terse)`: cached per argument pair. The first call
    resolves `processor`; on a generic Unix a non-terse one also runs `file`
    through `architecture()`. `uname()` is replaced so the branch taken does
    not depend on the machine running the test."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows reads WMI, not uname -p")
    def test_linux_first_call_runs_uname_p_then_nothing(
        self, monkeypatch: pytest.MonkeyPatch, commands: list[str]
    ) -> None:
        result = fresh_result("Linux")
        libc_calls: list[int] = []
        real_libc_ver = platform.libc_ver
        monkeypatch.setattr(platform, "uname", lambda: result)
        monkeypatch.setattr(platform, "libc_ver", lambda: libc_calls.append(1) or real_libc_ver())
        monkeypatch.setattr(platform, "_platform_cache", {})

        first = platform.platform()
        assert commands == ["uname -p"]
        assert libc_calls == [1]
        assert platform.platform() is first
        platform.platform(aliased=True, terse=True)
        assert commands == ["uname -p"]
        assert libc_calls == [1, 1]
        assert len(platform._platform_cache) == 2  # pyright: ignore[reportAttributeAccessIssue]

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows does not run file")
    def test_generic_unix_non_terse_runs_file(
        self, monkeypatch: pytest.MonkeyPatch, commands: list[str]
    ) -> None:
        result = fresh_result("FreeBSD")
        monkeypatch.setattr(platform, "uname", lambda: result)
        monkeypatch.setattr(platform, "_platform_cache", {})

        platform.platform(terse=True)
        assert commands == ["uname -p"]
        platform.platform()
        assert commands == ["uname -p", "file -b"]
        platform.platform()
        assert commands == ["uname -p", "file -b"]


class TestArchitectureIsNotCached:
    """`architecture()`: not cached; every call runs `file -b`."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows does not run file")
    def test_every_call_runs_file(self, commands: list[str]) -> None:
        assert platform.architecture() == ("64bit", "ELF")
        platform.architecture()
        assert commands == ["file -b", "file -b"]


class TestLibcVer:
    """`libc_ver()`: one `os.confstr()` with glibc; given an executable, O(b)
    reads of `chunksize` each and O(chunksize) memory, on every call."""

    def test_default_reads_no_file_with_glibc(
        self, monkeypatch: pytest.MonkeyPatch, opened: tuple[list[str], list[int]]
    ) -> None:
        try:
            answer = os.confstr("CS_GNU_LIBC_VERSION")
        except (AttributeError, ValueError, OSError):
            answer = None
        if not answer:
            pytest.skip("not a glibc system")
        paths, _ = opened
        asked: list[str] = []
        real_confstr = os.confstr
        monkeypatch.setattr(os, "confstr", lambda name: asked.append(name) or real_confstr(name))

        assert platform.libc_ver() == tuple(answer.split(maxsplit=1))
        assert asked == ["CS_GNU_LIBC_VERSION"]
        assert paths == []

    @pytest.mark.parametrize(("chunks", "expected_reads"), [(10, 11), (100, 101)])
    def test_the_whole_file_is_read_in_chunks(
        self,
        tmp_path: pathlib.Path,
        opened: tuple[list[str], list[int]],
        chunks: int,
        expected_reads: int,
    ) -> None:
        binary = tmp_path / "binary"
        binary.write_bytes(b"\0" * (chunks * CHUNK))
        _, reads = opened

        assert platform.libc_ver(str(binary)) == ("", "")
        assert len(reads) == expected_reads
        platform.libc_ver(str(binary))
        assert len(reads) == 2 * expected_reads

    def test_memory_follows_the_chunk_not_the_file(self, tmp_path: pathlib.Path) -> None:
        peaks: dict[int, int] = {}
        for chunks in (10, 1_000):
            binary = tmp_path / f"binary{chunks}"
            binary.write_bytes(b"\0" * (chunks * CHUNK))
            platform.libc_ver(str(binary))  # warm the regex cache
            peaks[chunks] = peak_bytes(partial(platform.libc_ver, str(binary)))

        assert peaks[1_000] < 2 * peaks[10], f"peaks {peaks} for 10 and 1,000 chunks"
        assert peaks[1_000] < 1_000 * CHUNK // 20, f"peak {peaks[1_000]} over a 16 MB file"

    @pytest.mark.parametrize(
        "markers",
        [(b"GLIBC_2.17", b"GLIBC_2.28"), (b"GLIBC_2.28", b"GLIBC_2.9")],
        ids=["ascending", "descending"],
    )
    def test_the_highest_version_wins(
        self, tmp_path: pathlib.Path, markers: tuple[bytes, bytes]
    ) -> None:
        binary = tmp_path / "binary"
        binary.write_bytes(
            b"\0" * 50_000 + markers[0] + b"\0" + b"\0" * 50_000 + markers[1] + b"\0"
        )
        assert platform.libc_ver(str(binary)) == ("glibc", "2.28")

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="musl is recognised from 3.14")
    def test_musl_is_recognised(self, tmp_path: pathlib.Path) -> None:
        binary = tmp_path / "binary"
        binary.write_bytes(b"\0" * 50_000 + b"musl-1.2.4\0")
        assert platform.libc_ver(str(binary)) == ("musl", "1.2.4")


class TestOsReleaseIsReadOnceAndCopied:
    """`freedesktop_os_release()`: O(f); read once, then a fresh copy of the
    cached dictionary per call; `OSError` when no candidate exists."""

    @pytest.fixture
    def release_file(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
        path = tmp_path / "os-release"
        monkeypatch.setattr(platform, "_os_release_candidates", (str(path),))
        monkeypatch.setattr(platform, "_os_release_cache", None)
        return path

    def test_read_once_copied_each_call(
        self, release_file: pathlib.Path, opened: tuple[list[str], list[int]]
    ) -> None:
        release_file.write_text('NAME="Example"\nID=example\n', encoding="utf-8")
        paths, _ = opened

        first = platform.freedesktop_os_release()
        second = platform.freedesktop_os_release()
        first["ID"] = "changed"
        third = platform.freedesktop_os_release()

        assert paths == [str(release_file)]
        assert second == {"NAME": "Example", "ID": "example", "PRETTY_NAME": "Linux"}
        assert second is not first and third is not second
        assert third["ID"] == "example"

    @pytest.mark.parametrize("fields", [10, 1_000])
    def test_result_grows_with_the_file(self, release_file: pathlib.Path, fields: int) -> None:
        release_file.write_text(
            "".join(f"KEY_{i}=value{i}\n" for i in range(fields)), encoding="utf-8"
        )
        assert len(platform.freedesktop_os_release()) == fields + 3

    def test_missing_file_raises(self, release_file: pathlib.Path) -> None:
        with pytest.raises(OSError, match="Unable to read files"):
            platform.freedesktop_os_release()


class CountingDict(dict[Any, Any]):
    def __init__(self) -> None:
        super().__init__()
        self.fills = 0

    def __setitem__(self, key: Any, value: Any) -> None:
        self.fills += 1
        super().__setitem__(key, value)


class TestPythonBuildInfoIsParsedOnce:
    """The `python_*()` functions parse `sys.version` once and read a cache;
    `python_version_tuple()` holds strings."""

    def test_one_parse_serves_every_function(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cache = CountingDict()
        monkeypatch.setattr(platform, "_sys_version_cache", cache)

        for _ in range(3):
            platform.python_implementation()
            platform.python_version()
            platform.python_version_tuple()
            platform.python_branch()
            platform.python_revision()
            platform.python_build()
            platform.python_compiler()

        assert cache.fills == 1
        assert platform.python_version() is platform.python_version()

    def test_version_tuple_holds_strings(self) -> None:
        parts = platform.python_version_tuple()
        assert len(parts) == 3
        assert all(isinstance(part, str) for part in parts)
        assert (int(parts[0]), int(parts[1])) == sys.version_info[:2]
        assert ["3", "10"] < ["3", "9"]


@pytest.mark.skipif(sys.version_info < (3, 14), reason="invalidate_caches() is 3.14+")
class TestInvalidateCaches:
    """`invalidate_caches()`: drops the cached `uname()`, `platform()`,
    os-release and `sys.version` results."""

    def test_every_cache_is_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(platform, "_os_release_cache", {"ID": "seeded"})
        before = platform.uname()
        platform.platform()
        platform.python_version()

        platform.invalidate_caches()  # pyright: ignore[reportAttributeAccessIssue]

        assert platform._platform_cache == {}  # pyright: ignore[reportAttributeAccessIssue]
        assert platform._sys_version_cache == {}  # pyright: ignore[reportAttributeAccessIssue]
        assert platform._os_release_cache is None  # pyright: ignore[reportAttributeAccessIssue]
        assert platform.uname() is not before


class TestSystemAlias:
    """`system_alias()`: rewrites its arguments and queries nothing."""

    def test_rewrites_without_querying(
        self, commands: list[str], opened: tuple[list[str], list[int]]
    ) -> None:
        assert platform.system_alias("SunOS", "5.8", "Generic") == ("Solaris", "2.8", "Generic")
        assert platform.system_alias("win32", "10", "x") == ("Windows", "10", "x")
        assert platform.system_alias("Linux", "6.1", "#1") == ("Linux", "6.1", "#1")
        assert commands == []
        assert opened[0] == []


class TestOtherOperatingSystems:
    """The per-system version queries return their defaults elsewhere, having
    run nothing; `mac_ver()` reads its plist on every call on macOS."""

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="asserts Linux defaults")
    def test_defaults_on_linux(
        self, commands: list[str], opened: tuple[list[str], list[int]]
    ) -> None:
        assert platform.mac_ver() == ("", ("", "", ""), "")
        assert platform.win32_ver() == ("", "", "", "")
        assert platform.win32_edition() is None
        assert platform.win32_is_iot() is False
        if sys.version_info >= (3, 13):
            ios = platform.ios_ver()  # pyright: ignore[reportAttributeAccessIssue]
            android = platform.android_ver()  # pyright: ignore[reportAttributeAccessIssue]
            assert ios == ("", "", "", False)
            assert android == ("", 0, "", "", "", False)
        assert commands == []
        assert opened[0] == []

    def test_java_ver_returns_defaults(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert platform.java_ver() == ("", "", ("", "", ""), ("", "", ""))
        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecated) == (1 if sys.version_info >= (3, 13) else 0)

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only plist")
    def test_mac_ver_reads_the_plist_every_call(self, opened: tuple[list[str], list[int]]) -> None:
        platform.mac_ver()
        platform.mac_ver()
        assert opened[0] == ["/System/Library/CoreServices/SystemVersion.plist"] * 2


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
    """Each block runs in its own subprocess, so the module's caches start
    cold in each, and asserts its own result."""

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
            (n, s) for n, s in _blocks() if "assert 'processor' not in vars(info)" in s
        )
        mutated = source.replace(
            "assert 'processor' not in vars(info)", "assert 'processor' in vars(info)", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
