"""Tests for docs/stdlib/winreg.md.

Every function in the module is one or two registry calls around a
conversion between Python objects and registry data, and PC/winreg.c
releases each buffer before it returns. The page's size terms are therefore
buffers and results, and traced allocation settles them without a
stopwatch: the conversion buffers come from PyMem_Malloc, which tracemalloc
sees. The O(1) rows are settled by behaviour, and one timing test shows
`QueryInfoKey()` does not scan the key. Everything runs under a scratch key
in HKEY_CURRENT_USER that each test creates and deletes.

Measurement scope:

* `QueryValueEx()` peaks above the value's size and grows over 50x from a
  10,000-byte `REG_BINARY` value to a 1,000,000-byte one; `SetValueEx()`
  grows over 50x over the same two sizes. Each value type's conversion is
  asserted by the Python type it returns, including `REG_DWORD_BIG_ENDIAN`
  coming back as `bytes`, and empty `REG_BINARY`, `REG_NONE` and
  `REG_DWORD_BIG_ENDIAN` data as None.
* `EnumValue()` on a one-byte value peaks under 4 KB when the key's largest
  value is 1,000 bytes and above 1,000,000 bytes when it is 1,000,000 bytes,
  while `QueryValueEx()` on the same one-byte value stays under 4 KB in both.
  That is the M term: the buffers are sized for the largest value, read from
  `RegQueryInfoKeyW` in PC/winreg.c, on every supported version. Time does
  not follow M: in a timing test 1,000x the largest value makes the same
  one-byte `EnumValue()` under 100x dearer (x3.0 on 3.14, x4.3 on 3.11 and
  x13 on 3.10, fastest of seven runs of 200 calls), because the buffer is
  allocated, not filled. Only the one-byte value was read, so n is not
  varied.
* `EnumKey()` peaks under 4 KB beside a 255-character subkey name, its
  buffer being a fixed 257 characters; an index past the end raises OSError
  with winerror 259.
* `QueryInfoKey()` costs under 3x as much on a key with 2,000 subkeys as on
  one with 10, fastest of seven runs of 200 calls, where a scan would grow
  with the 200x the subkeys.
* `ExpandEnvironmentStrings()` expanding one reference to a 30,000-character
  variable peaks above 60,000 bytes, the result's characters as UTF-16,
  where a one-character one stays under 4 KB; a 20,000-character variable
  name expanding to one character peaks above 40,000 bytes, the argument's
  characters as UTF-16; unknown names come back unchanged. Windows caps a variable at 32,767 characters and the call's
  buffers at 32K, so nothing larger can be measured.
* `QueryValue()` returns `''` for a key without a default value and the
  default of a subkey when given one; `SetValue()` creates that subkey and
  rejects any type but `REG_SZ` with TypeError.
* `OpenKeyEx()` and `OpenKey()` open the same key with the same defaults;
  `CreateKey()` on an existing key keeps its values; `DeleteKey()` removes a
  key with values and raises PermissionError (winerror 5) while it has a
  subkey; `DeleteKeyEx()` with `KEY_WOW64_64KEY` deletes; `CloseKey()`
  closes both a `PyHKEY` and a raw integer.
* `PyHKEY.Close()`, the `with` statement and `Detach()` leave `handle` at 0;
  a collected `PyHKEY` releases its kernel handle, which
  `GetHandleInformation` then rejects; `int()` and `bool()` read `handle`;
  `HKEYType` is the type `OpenKey()` returns and `error` is OSError.
* `SaveKey()` and `LoadKey()` without the backup and restore privileges
  enabled raise OSError with winerror 1314. `QueryReflectionKey()` returns a
  bool and the other two reflection calls None on a 64-bit build.
* Every fenced block on the page runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That a registry call is O(1). The page counts it that way, as the os page
  counts a syscall; the QueryInfoKey timing is the one check that a count is
  read rather than computed.
* `FlushKey()` blocking on however much is unwritten, `SaveKey()` being
  O(T) in the saved subtree and `LoadKey()` O(F) in the hive file: each is
  the registry's own I/O, and the last two need privileges a test process
  does not hold. They follow from the Win32 documentation of RegFlushKey,
  RegSaveKeyW and RegLoadKeyW.
* `ConnectRegistry()` needs a second machine running the Remote Registry
  service.
* `NotImplementedError` from the reflection calls on 32-bit Windows, which
  no supported build here runs on.
* Every test except the block count is Windows-only and skips elsewhere, so
  a run on Linux or macOS verifies none of the page's claims.
"""

from __future__ import annotations

import gc
import importlib
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "winreg.md"
EXPECTED_BLOCKS = 8

WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="winreg is Windows-only")
winreg: Any = importlib.import_module("winreg") if sys.platform == "win32" else None


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


def winerror(error: OSError) -> int:
    """The Windows error code, an attribute typeshed declares only on Windows."""
    return getattr(error, "winerror")  # noqa: B009


def delete_tree(parent: Any, name: str) -> None:
    with winreg.OpenKey(parent, name) as key:
        while winreg.QueryInfoKey(key)[0]:
            delete_tree(key, winreg.EnumKey(key, 0))
    winreg.DeleteKey(parent, name)


@pytest.fixture
def scratch() -> Iterator[Any]:
    """An empty key under HKEY_CURRENT_USER, deleted with everything in it."""
    path = rf"Software\python-complexity-tests-{uuid.uuid4().hex}"
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
    try:
        yield key
    finally:
        key.Close()
        delete_tree(winreg.HKEY_CURRENT_USER, path)


@WINDOWS
class TestKeyCallsAreConstant:
    """The Keys table: one registry call each, whatever the key holds."""

    def test_openkeyex_is_openkey(self, scratch: Any) -> None:
        winreg.SetValueEx(scratch, "v", 0, winreg.REG_SZ, "x")
        winreg.CreateKey(scratch, "child").Close()
        with winreg.OpenKey(scratch, "child") as one, winreg.OpenKeyEx(scratch, "child") as two:
            assert winreg.QueryInfoKey(one)[:2] == winreg.QueryInfoKey(two)[:2]
            with pytest.raises(PermissionError):
                winreg.SetValueEx(two, "w", 0, winreg.REG_SZ, "y")  # KEY_READ by default

    def test_createkey_opens_an_existing_key(self, scratch: Any) -> None:
        with winreg.CreateKey(scratch, "child") as child:
            winreg.SetValueEx(child, "kept", 0, winreg.REG_DWORD, 7)
        with winreg.CreateKeyEx(scratch, "child", 0, winreg.KEY_READ) as again:
            assert winreg.QueryValueEx(again, "kept") == (7, winreg.REG_DWORD)

    def test_deletekey_takes_values_and_refuses_subkeys(self, scratch: Any) -> None:
        with winreg.CreateKey(scratch, "parent") as parent:
            winreg.SetValueEx(parent, "v", 0, winreg.REG_SZ, "x")
            winreg.CreateKey(parent, "child").Close()

        with pytest.raises(PermissionError) as refused:
            winreg.DeleteKey(scratch, "parent")
        assert winerror(refused.value) == 5

        winreg.DeleteKeyEx(scratch, r"parent\child", winreg.KEY_WOW64_64KEY)
        winreg.DeleteKey(scratch, "parent")
        assert winreg.QueryInfoKey(scratch)[0] == 0

    def test_closekey_accepts_a_handle_object_or_an_integer(self) -> None:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software")
        winreg.CloseKey(key)
        assert key.handle == 0

        raw = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software").Detach()
        winreg.CloseKey(raw)

    def test_flushkey_returns_once_written(self, scratch: Any) -> None:
        winreg.SetValueEx(scratch, "v", 0, winreg.REG_SZ, "x")
        assert winreg.FlushKey(scratch) is None

    @pytest.mark.timing
    def test_queryinfokey_does_not_scan_the_key(self, scratch: Any) -> None:
        """`QueryInfoKey(key)` | O(1) - the counts are read, not counted."""
        with winreg.CreateKey(scratch, "few") as few, winreg.CreateKey(scratch, "many") as many:
            for index in range(10):
                winreg.CreateKey(few, f"k{index}").Close()
            for index in range(2_000):
                winreg.CreateKey(many, f"k{index}").Close()
            assert winreg.QueryInfoKey(many)[0] == 2_000

            small = best_ns(lambda: winreg.QueryInfoKey(few), inner=200)
            large = best_ns(lambda: winreg.QueryInfoKey(many), inner=200)

        assert large / small < 3, f"200x the subkeys cost x{large / small:.2f}"


@WINDOWS
class TestValuesAreLinearInTheirSize:
    """The Values table: a read or write costs the value's bytes, in a buffer
    and then in the converted object."""

    def test_queryvalueex_space_follows_the_value(self, scratch: Any) -> None:
        winreg.SetValueEx(scratch, "small", 0, winreg.REG_BINARY, b"x" * 10_000)
        winreg.SetValueEx(scratch, "large", 0, winreg.REG_BINARY, b"x" * 1_000_000)

        small = peak_bytes(lambda: winreg.QueryValueEx(scratch, "small"))
        large = peak_bytes(lambda: winreg.QueryValueEx(scratch, "large"))

        assert large > 1_000_000
        assert large / small > 50, f"100x the value cost x{large / small:.1f} in space"

    def test_setvalueex_space_follows_the_value(self, scratch: Any) -> None:
        small_value, large_value = "x" * 5_000, "x" * 500_000
        small = peak_bytes(lambda: winreg.SetValueEx(scratch, "s", 0, winreg.REG_SZ, small_value))
        large = peak_bytes(lambda: winreg.SetValueEx(scratch, "l", 0, winreg.REG_SZ, large_value))

        assert large / small > 50, f"100x the value cost x{large / small:.1f} in space"

    @pytest.mark.parametrize(
        ("value_type", "value", "expected_type"),
        [
            ("REG_SZ", "text", str),
            ("REG_EXPAND_SZ", "%PATH%", str),
            ("REG_MULTI_SZ", ["a", "b"], list),
            ("REG_DWORD", 42, int),
            ("REG_QWORD", 2**40, int),
            ("REG_BINARY", b"\x00\x01", bytes),
            ("REG_DWORD_BIG_ENDIAN", b"\x00\x00\x00\x01", bytes),
        ],
    )
    def test_the_type_decides_the_conversion(
        self, scratch: Any, value_type: str, value: object, expected_type: type
    ) -> None:
        winreg.SetValueEx(scratch, "v", 0, getattr(winreg, value_type), value)
        read, read_type = winreg.QueryValueEx(scratch, "v")
        assert type(read) is expected_type
        assert read_type == getattr(winreg, value_type)

    @pytest.mark.parametrize("value_type", ["REG_BINARY", "REG_NONE", "REG_DWORD_BIG_ENDIAN"])
    def test_empty_bytes_data_comes_back_as_none(self, scratch: Any, value_type: str) -> None:
        winreg.SetValueEx(scratch, "v", 0, getattr(winreg, value_type), b"")
        assert winreg.QueryValueEx(scratch, "v") == (None, getattr(winreg, value_type))

    def test_queryvalue_reads_the_default_value(self, scratch: Any) -> None:
        assert winreg.QueryValue(scratch, None) == ""

        winreg.SetValue(scratch, "child", winreg.REG_SZ, "hi")
        assert winreg.QueryInfoKey(scratch)[0] == 1, "SetValue created the subkey"
        assert winreg.QueryValue(scratch, "child") == "hi"
        with winreg.OpenKey(scratch, "child") as child:
            assert winreg.QueryValueEx(child, None) == ("hi", winreg.REG_SZ)

        with pytest.raises(TypeError):
            winreg.SetValue(scratch, "child", winreg.REG_DWORD, "1")

    def test_deletevalue_removes_one_value(self, scratch: Any) -> None:
        winreg.SetValueEx(scratch, "a", 0, winreg.REG_SZ, "x")
        winreg.SetValueEx(scratch, "b", 0, winreg.REG_SZ, "y")
        winreg.DeleteValue(scratch, "a")
        assert winreg.QueryInfoKey(scratch)[1] == 1
        with pytest.raises(FileNotFoundError):
            winreg.QueryValueEx(scratch, "a")


@WINDOWS
class TestExpandEnvironmentStringsFollowsBothStrings:
    """`ExpandEnvironmentStrings(str)` | O(s + x) | O(s + x) - the argument is
    converted to UTF-16 and the result built, so either string can dominate."""

    @pytest.mark.serial
    def test_space_follows_the_expansion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(os.environ, "WINREG_TEST_SHORT", "x")
        monkeypatch.setitem(os.environ, "WINREG_TEST_LONG", "x" * 30_000)

        short = peak_bytes(lambda: winreg.ExpandEnvironmentStrings("%WINREG_TEST_SHORT%"))
        long = peak_bytes(lambda: winreg.ExpandEnvironmentStrings("%WINREG_TEST_LONG%"))

        assert short < 4_000
        assert long > 60_000, f"a 30,000-character result peaked at {long} B"

    @pytest.mark.serial
    def test_space_follows_the_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        name = "W" * 20_000
        monkeypatch.setitem(os.environ, name, "x")
        assert winreg.ExpandEnvironmentStrings(f"%{name}%") == "x"

        # A fresh str: through 3.11 the UTF-16 copy is cached on the object
        # the first call converts, so a reused argument would show nothing.
        argument = f"%{name}%"
        peak = peak_bytes(lambda: winreg.ExpandEnvironmentStrings(argument))
        assert peak > 40_000, f"a 20,002-character argument peaked at {peak} B"

    def test_unknown_names_are_left_as_written(self) -> None:
        unset = f"%WINREG_TEST_UNSET_{uuid.uuid4().hex}%"
        assert winreg.ExpandEnvironmentStrings(unset) == unset


@WINDOWS
class TestEnumerationIsOneCallPerEntry:
    """The Enumeration table."""

    @pytest.mark.serial
    def test_enumvalue_is_sized_for_the_largest_value(self, scratch: Any) -> None:
        """`EnumValue(key, index)` | O(n) | O(M) - the buffers fit the largest value,
        not the one returned, where `QueryValueEx()` fits the one it reads."""

        def peaks(largest: int) -> tuple[int, int]:
            winreg.SetValueEx(scratch, "large", 0, winreg.REG_BINARY, b"y" * largest)
            index = [winreg.EnumValue(scratch, i)[0] for i in range(2)].index("small")
            assert winreg.EnumValue(scratch, index)[1] == b"x"
            enum = peak_bytes(lambda: winreg.EnumValue(scratch, index))
            query = peak_bytes(lambda: winreg.QueryValueEx(scratch, "small"))
            return enum, query

        winreg.SetValueEx(scratch, "small", 0, winreg.REG_BINARY, b"x")
        enum_beside_small, query_beside_small = peaks(1_000)
        enum_beside_large, query_beside_large = peaks(1_000_000)

        assert enum_beside_small < 4_000
        assert enum_beside_large > 1_000_000, f"peaked at {enum_beside_large} B"
        assert query_beside_small < 4_000 and query_beside_large < 4_000

    @pytest.mark.timing
    def test_enumvalue_time_does_not_follow_the_largest_value(self, scratch: Any) -> None:
        """`EnumValue(key, index)` | O(n) time - the M-sized buffer is allocated,
        not filled, so 1,000x the largest value stays far from 1,000x the time."""
        winreg.SetValueEx(scratch, "small", 0, winreg.REG_BINARY, b"x")

        def cost(largest: int) -> float:
            winreg.SetValueEx(scratch, "large", 0, winreg.REG_BINARY, b"y" * largest)
            index = [winreg.EnumValue(scratch, i)[0] for i in range(2)].index("small")
            return best_ns(lambda: winreg.EnumValue(scratch, index), inner=200)

        beside_small, beside_large = cost(1_000), cost(1_000_000)

        assert beside_large / beside_small < 100, f"x{beside_large / beside_small:.1f}"

    @pytest.mark.serial
    def test_enumkey_uses_a_fixed_buffer(self, scratch: Any) -> None:
        winreg.CreateKey(scratch, "k" * 255).Close()
        peak = peak_bytes(lambda: winreg.EnumKey(scratch, 0))
        assert winreg.EnumKey(scratch, 0) == "k" * 255
        assert peak < 4_000

    def test_an_index_past_the_end_raises(self, scratch: Any) -> None:
        winreg.CreateKey(scratch, "only").Close()
        with pytest.raises(OSError) as past:
            winreg.EnumKey(scratch, 1)
        assert winerror(past.value) == 259
        with pytest.raises(OSError):
            winreg.EnumValue(scratch, 0)


@WINDOWS
class TestHiveFilesAndReflection:
    """The hive rows need privileges a test process does not hold; reflection
    is observable on a 64-bit build."""

    def test_savekey_and_loadkey_need_privileges(
        self, scratch: Any, tmp_path: pathlib.Path
    ) -> None:
        with pytest.raises(OSError) as save:
            winreg.SaveKey(scratch, str(tmp_path / "hive"))
        assert winerror(save.value) == 1314

        with pytest.raises(OSError) as load:
            winreg.LoadKey(winreg.HKEY_USERS, "python-complexity", str(tmp_path / "hive"))
        assert winerror(load.value) == 1314

    def test_reflection_calls_answer(self, scratch: Any) -> None:
        assert isinstance(winreg.QueryReflectionKey(scratch), bool)
        assert winreg.DisableReflectionKey(scratch) is None
        assert winreg.EnableReflectionKey(scratch) is None


@WINDOWS
class TestPyHKEY:
    """The PyHKEY table: the object owns one handle until closed or detached."""

    def test_close_detach_and_with_clear_the_handle(self) -> None:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software")
        assert isinstance(key, winreg.HKEYType)
        assert key and int(key) == key.handle != 0
        key.Close()
        assert not key and key.handle == 0

        detached = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software")
        raw = detached.Detach()
        assert raw != 0 and detached.handle == 0
        winreg.CloseKey(raw)

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software") as scoped:
            assert scoped.handle != 0
        assert scoped.handle == 0

    def test_collection_closes_the_handle(self) -> None:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        flags = ctypes.c_ulong()

        def is_open(handle: int) -> bool:
            return bool(kernel32.GetHandleInformation(ctypes.c_void_p(handle), ctypes.byref(flags)))

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software")
        raw = key.handle
        assert is_open(raw)
        del key
        gc.collect()
        assert not is_open(raw)

    def test_error_is_oserror(self) -> None:
        assert winreg.error is OSError


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
    """Each block runs in its own subprocess and asserts its own result. Every
    block creates its keys under HKEY_CURRENT_USER and deletes them."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @WINDOWS
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

    @WINDOWS
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if '== r"C:\\Data\\logs"' in s)
        mutated = source.replace('== r"C:\\Data\\logs"', '== r"C:\\Data\\log"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
