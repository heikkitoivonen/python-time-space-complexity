"""Tests to verify documented behaviour of py_compile.

docs/stdlib/py_compile.md was a 42-line stub whose two code blocks both
raised FileNotFoundError, and which never mentioned what `compile()` returns
- the path it wrote, or None on a compilation error. That is the whole
success protocol.

The finding worth having is `invalidation_mode`. The default, TIMESTAMP,
records the source's mtime and size; an edit that changes neither is not
noticed, and the stale bytecode is imported. CHECKED_HASH records a hash
instead and costs about 3% more to write.

The py_compile tests previously in tests/test_compileall_complexity.py moved
here, now that the module has a file of its own.
"""

import importlib
import os
import py_compile
import shutil
import sys
import time
from collections.abc import Callable
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


def source_of(directory: Path, name: str, lines: int) -> Path:
    path = directory / name
    path.write_text(
        "\n".join(f"y{index} = {index} * 2" for index in range(lines)), encoding="utf-8"
    )
    return path


class TestCompileComplexity:
    """The table's O(n) in the source length."""

    def test_scales_with_the_source_size(self, tmp_path: Path) -> None:
        small = source_of(tmp_path, "small.py", 100)
        large = source_of(tmp_path, "large.py", 1_600)

        small_time = best_time(lambda: py_compile.compile(str(small), doraise=True))
        large_time = best_time(lambda: py_compile.compile(str(large), doraise=True))

        assert large_time > small_time * 4, (
            f"sixteen times the source: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_hashing_the_source_is_a_small_surcharge(self, tmp_path: Path) -> None:
        """The page says about 3%, so this only checks it is not a new pass."""
        module = source_of(tmp_path, "big.py", 4_000)
        modes = py_compile.PycInvalidationMode

        timestamp = best_time(
            lambda: py_compile.compile(
                str(module),
                cfile=str(tmp_path / "t.pyc"),
                invalidation_mode=modes.TIMESTAMP,
            )
        )
        hashed = best_time(
            lambda: py_compile.compile(
                str(module),
                cfile=str(tmp_path / "h.pyc"),
                invalidation_mode=modes.CHECKED_HASH,
            )
        )

        assert hashed < timestamp * 1.5, (
            f"hashing should be marginal next to compiling: "
            f"timestamp {timestamp:.2e}s hashed {hashed:.2e}s"
        )


class TestTheReturnValueIsThePath:
    """Undocumented on the page until now, and it is the success protocol."""

    def test_success_returns_the_bytecode_path(self, tmp_path: Path) -> None:
        module = source_of(tmp_path, "module.py", 2)
        written = py_compile.compile(str(module))

        assert written is not None
        assert Path(written).is_file()
        assert Path(written).suffix == ".pyc"
        assert "__pycache__" in written, "PEP 3147 layout by default"

    def test_cfile_puts_it_exactly_where_asked(self, tmp_path: Path) -> None:
        module = source_of(tmp_path, "module.py", 2)
        target = tmp_path / "explicit.pyc"

        written = py_compile.compile(str(module), cfile=str(target))

        assert written == str(target)
        assert target.is_file()

    def test_a_compilation_error_returns_none(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.py"
        broken.write_text("def (\n", encoding="utf-8")

        assert py_compile.compile(str(broken), quiet=2) is None

    def test_doraise_raises_instead(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.py"
        broken.write_text("def (\n", encoding="utf-8")

        with pytest.raises(py_compile.PyCompileError):
            py_compile.compile(str(broken), doraise=True, quiet=1)

    def test_quiet_two_overrides_doraise(self, tmp_path: Path) -> None:
        """The raise sits inside `if quiet < 2:`, so quiet=2 swallows it.

        A build step asking for doraise and quiet together gets neither the
        exception nor the message. This test exists because the first draft
        of the page's own example asked for both and demonstrated nothing.
        """
        broken = tmp_path / "broken.py"
        broken.write_text("def (\n", encoding="utf-8")

        assert py_compile.compile(str(broken), doraise=True, quiet=2) is None

    def test_a_missing_source_raises_under_every_combination(self, tmp_path: Path) -> None:
        """doraise governs compilation errors, not reading the file."""
        absent = str(tmp_path / "absent.py")

        with pytest.raises(FileNotFoundError):
            py_compile.compile(absent)
        with pytest.raises(FileNotFoundError):
            py_compile.compile(absent, doraise=True)
        with pytest.raises(FileNotFoundError):
            py_compile.compile(absent, quiet=2)


class TestInvalidationModes:
    """The default misses an edit that keeps mtime and size."""

    def _import_twice(self, tmp_path: Path, mode: Any, monkeypatch: Any) -> tuple[str, str]:
        """Compile, import, edit in place preserving mtime and size, reimport."""
        monkeypatch.syspath_prepend(str(tmp_path))
        shutil.rmtree(tmp_path / "__pycache__", ignore_errors=True)
        for name in [n for n in sys.modules if n.startswith("probe_")]:
            del sys.modules[name]

        module = tmp_path / "probe_mod.py"
        module.write_text("VALUE = 'first'\n", encoding="utf-8")
        py_compile.compile(str(module), invalidation_mode=mode)
        before = importlib.import_module("probe_mod").VALUE

        stat = module.stat()
        module.write_text("VALUE = 'secnd'\n", encoding="utf-8")  # same length
        os.utime(module, (stat.st_atime, stat.st_mtime))  # and the same mtime

        del sys.modules["probe_mod"]
        importlib.invalidate_caches()
        after = importlib.import_module("probe_mod").VALUE
        del sys.modules["probe_mod"]
        return before, after

    def test_timestamp_mode_serves_stale_bytecode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before, after = self._import_twice(
            tmp_path, py_compile.PycInvalidationMode.TIMESTAMP, monkeypatch
        )

        assert before == "first"
        assert after == "first", "an edit that preserves mtime and size is invisible to TIMESTAMP"

    def test_checked_hash_mode_notices(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before, after = self._import_twice(
            tmp_path, py_compile.PycInvalidationMode.CHECKED_HASH, monkeypatch
        )

        assert before == "first"
        assert after == "secnd", "the hash changed, so the bytecode was rebuilt"

    def test_the_modes_are_recorded_in_the_header(self, tmp_path: Path) -> None:
        """Flags in bytes 4..8 distinguish them, per PEP 552."""
        module = source_of(tmp_path, "flagged.py", 5)
        modes = py_compile.PycInvalidationMode
        flags = {}
        for mode in modes:
            target = tmp_path / f"{mode.name}.pyc"
            py_compile.compile(str(module), cfile=str(target), invalidation_mode=mode)
            flags[mode.name] = int.from_bytes(target.read_bytes()[4:8], "little")

        assert flags["TIMESTAMP"] == 0
        assert flags["UNCHECKED_HASH"] == 1
        assert flags["CHECKED_HASH"] == 3

    def test_all_three_modes_exist(self) -> None:
        names = {mode.name for mode in py_compile.PycInvalidationMode}
        assert names == {"TIMESTAMP", "CHECKED_HASH", "UNCHECKED_HASH"}
