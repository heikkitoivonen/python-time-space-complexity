"""Tests for docs/stdlib/zipapp.md.

The page prices three things separately: building an archive from a directory
is a copy of every byte under it plus an entry per path, copying an existing
archive is a byte copy that never parses it, and running the result compiles
every `.py` member at every start unless a `.pyc` member sits beside it. Almost
every row is settled by observation - a recording `filter`, a counting file
object, a patched `compile`, the size of the file written - rather than by a
clock.

Measurement scope:

* The `filter` row is settled by recording every path it is given. The
  recorded list is the whole tree, directories included, and it still holds a
  rejected directory's children; the archive built from it holds the file that
  was accepted under the rejected directory. The order the paths arrive in is
  asserted sorted on 3.14 only, which is the version that sorts the listing.
* Space for a directory build, stored and deflated, and for a copy is a
  `tracemalloc` peak over an eight-megabyte input, asserted at under half of
  it. That the remaining space is the member list, O(f), is read from
  `zipfile.ZipFile`, which keeps a `ZipInfo` per member until the central
  directory is written; it is not measured against f here. The time is not
  asserted by a stopwatch either: a stored archive is the input's bytes plus a
  bounded header per member, so the size of the file written shows the work is
  at least b, and the copy loop in `zipfile.ZipFile.write()` is what bounds it
  above. A copy is the same size as its source plus the shebang.
* `get_interpreter()` is settled by a `BytesIO` subclass that counts the bytes
  it hands out: nineteen for a nineteen-byte shebang line ahead of ten
  megabytes, two for an archive with no shebang.
* Copying is shown not to parse the source by copying a text file that is not
  an archive at all. The shebang replacement is asserted by bytes on both
  sides: with an interpreter the copy is the source's bytes behind a new first
  line, and without one the source's shebang is gone from the copy.
* The executable bit is asserted on both target spellings. A `str` target gets
  it on both build paths; a `pathlib.Path` target gets it from a directory
  build and not from a copy. Windows has no executable bit, so those tests are
  guarded on `sys.platform`.
* Whether a refused build opens the target is settled by the target's absence
  afterwards, for each of the four `ZipAppError` paths that exist on every
  version and the fifth that 3.14 adds.
* The self-inclusion boundary is asserted on both sides of it. Up to 3.13 a
  target created inside the source directory appears in its own member list;
  on 3.14 it does not, and an existing target inside the source raises.
* The compile at every start is a subprocess per archive that replaces
  `builtins.compile` before importing the package. Each `.py` member imported
  compiles twice, on every supported version: `zipimporter.get_filename()`
  compiles the member to learn its path while the spec is being built, and
  `get_code()` compiles it again to execute it. The same tree packed after
  `compileall.compile_dir(legacy=True)` with timestamp invalidation compiles
  nothing; editing one source after compiling makes that one member compile
  again and the other not; and the same bytecode packed under `__pycache__`
  instead of beside the source changes nothing. Running the archive as an
  application is a second driver over `runpy.run_path()`: with bytecode
  beside the sources the only member compiled is the `__main__.py` that
  `main=` generates. The inflation row is a patched `zlib.decompress` in the
  same subprocess shape: a deflated member is inflated once per compile, so
  twice, and a stored one never.
* The `python -m zipapp` row runs the page's shell block command by command
  in a subprocess, with `python` replaced by the running interpreter, against
  the same tree the Python blocks build. The three refusals are run the same
  way and asserted on stderr.

Not settled here:

* The O(f log f) that 3.14's sort adds is not separated from the O(b + f)
  around it by timing. The sorted member order on 3.14 is what is asserted.
* The shebang encoding differs by platform - UTF-8 on Windows, the filesystem
  encoding elsewhere - and the page makes no claim about it.
* The running-archive row's O(m) for reading the central directory is
  `zipimport`'s cost and is not measured here; what is measured is the compile
  and inflation count per member imported.
"""

from __future__ import annotations

import compileall
import io
import json
import os
import pathlib
import py_compile
import re
import shlex
import stat
import subprocess
import sys
import textwrap
import tracemalloc
import zipapp
import zipfile
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zipapp.md"
EXPECTED_BLOCKS = 3
LISTS_BEFORE_WRITING = sys.version_info >= (3, 14)
INTERPRETER = "/usr/bin/env python3"
NEEDS_EXEC_BIT = pytest.mark.skipif(sys.platform == "win32", reason="no executable bit")


def app_tree(root: pathlib.Path, *, with_pycache: bool = False) -> pathlib.Path:
    """A package with an entry point, and optionally a stale cache directory."""
    source = root / "app"
    (source / "pkg").mkdir(parents=True)
    (source / "pkg" / "__init__.py").write_text("def main():\n    print('hi')\n", encoding="utf-8")
    (source / "pkg" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    if with_pycache:
        (source / "pkg" / "__pycache__").mkdir()
        (source / "pkg" / "__pycache__" / "stale.pyc").write_bytes(b"")
    return source


def names_in(archive: pathlib.Path | str) -> list[str]:
    with zipfile.ZipFile(archive) as packed:
        return packed.namelist()


def is_executable(path: pathlib.Path | str) -> bool:
    return bool(os.stat(path).st_mode & stat.S_IEXEC)


class CountingFile(io.BytesIO):
    """A file object that records how many bytes it handed out."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.handed_out = 0

    def read(self, size: int | None = -1) -> bytes:
        chunk = super().read(size)
        self.handed_out += len(chunk)
        return chunk

    def readline(self, size: int | None = -1) -> bytes:
        chunk = super().readline(size)
        self.handed_out += len(chunk)
        return chunk


class TestBuildingFromADirectory:
    """The first table: every entry is a member, and the bytes stream."""

    def test_every_entry_is_a_member_directories_included(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path, with_pycache=True)
        target = tmp_path / "app.pyz"

        zipapp.create_archive(source, target, main="pkg:main")

        assert sorted(names_in(target)) == [
            "__main__.py",
            "pkg/",
            "pkg/__init__.py",
            "pkg/__pycache__/",
            "pkg/__pycache__/stale.pyc",
            "pkg/helper.py",
        ]

    def test_the_filter_sees_every_entry_and_prunes_nothing(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path, with_pycache=True)
        target = tmp_path / "app.pyz"
        offered: list[str] = []

        def reject_the_directory_only(path: pathlib.Path) -> bool:
            offered.append(path.as_posix())
            return path.name != "__pycache__"

        zipapp.create_archive(source, target, main="pkg:main", filter=reject_the_directory_only)

        assert sorted(offered) == [
            "pkg",
            "pkg/__init__.py",
            "pkg/__pycache__",
            "pkg/__pycache__/stale.pyc",
            "pkg/helper.py",
        ]
        assert "pkg/__pycache__/stale.pyc" in names_in(target)
        assert "pkg/__pycache__/" not in names_in(target)

    def test_rejecting_the_subtree_excludes_it(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path, with_pycache=True)
        target = tmp_path / "app.pyz"

        zipapp.create_archive(
            source, target, main="pkg:main", filter=lambda p: "__pycache__" not in p.parts
        )

        assert sorted(names_in(target)) == [
            "__main__.py",
            "pkg/",
            "pkg/__init__.py",
            "pkg/helper.py",
        ]

    @pytest.mark.skipif(not LISTS_BEFORE_WRITING, reason="the listing is sorted from 3.14")
    def test_the_listing_is_sorted(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "app"
        source.mkdir()
        (source / "__main__.py").write_text("", encoding="utf-8")
        for name in ("zeta", "alpha", "mid"):
            (source / name).write_text("", encoding="utf-8")
        target = tmp_path / "app.pyz"

        zipapp.create_archive(source, target)

        assert names_in(target) == ["__main__.py", "alpha", "mid", "zeta"]

    def test_a_stored_archive_is_the_bytes_plus_a_bounded_header_per_member(
        self, tmp_path: pathlib.Path
    ) -> None:
        """O(b + f) read off the file written: b bytes of contents, and under 200 per entry."""
        source = tmp_path / "app"
        source.mkdir()
        (source / "__main__.py").write_text("", encoding="utf-8")
        sizes = [0, 1, 1_000, 100_000, 1_000_000]
        for index, size in enumerate(sizes):
            (source / f"blob{index}").write_bytes(os.urandom(size))
        target = tmp_path / "app.pyz"

        zipapp.create_archive(source, target)

        entries = len(sizes) + 1
        written = target.stat().st_size
        assert sum(sizes) < written < sum(sizes) + 200 * entries, written

    @pytest.mark.parametrize("compressed", [False, True])
    def test_contents_stream_rather_than_load(
        self, tmp_path: pathlib.Path, compressed: bool
    ) -> None:
        """Space is O(f), not O(b): a build over eight megabytes peaks well under it."""
        source = tmp_path / "app"
        source.mkdir()
        (source / "__main__.py").write_text("", encoding="utf-8")
        payload = 8_000_000
        (source / "blob").write_bytes(os.urandom(payload))
        target = tmp_path / "app.pyz"

        tracemalloc.start()
        tracemalloc.reset_peak()
        try:
            zipapp.create_archive(source, target, compressed=compressed)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert peak < payload / 2, peak

    def test_compressed_members_are_deflated_and_smaller(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "app"
        source.mkdir()
        (source / "__main__.py").write_text("", encoding="utf-8")
        (source / "text").write_bytes(b"the same line again\n" * 10_000)

        zipapp.create_archive(source, tmp_path / "stored.pyz")
        zipapp.create_archive(source, tmp_path / "deflated.pyz", compressed=True)

        with zipfile.ZipFile(tmp_path / "stored.pyz") as stored:
            plain = stored.getinfo("text")
        with zipfile.ZipFile(tmp_path / "deflated.pyz") as deflated:
            squeezed = deflated.getinfo("text")
        assert plain.compress_type == zipfile.ZIP_STORED
        assert plain.compress_size == plain.file_size
        assert squeezed.compress_type == zipfile.ZIP_DEFLATED
        assert squeezed.compress_size < squeezed.file_size / 10

    def test_main_writes_a_three_line_stub(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        target = tmp_path / "app.pyz"

        zipapp.create_archive(source, target, main="pkg:main")

        with zipfile.ZipFile(target) as packed:
            stub = packed.read("__main__.py").decode("utf-8")
        assert stub.splitlines() == ["# -*- coding: utf-8 -*-", "import pkg", "pkg.main()"]

    @NEEDS_EXEC_BIT
    def test_an_interpreter_writes_the_shebang_and_sets_the_bit(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = app_tree(tmp_path)
        as_path = tmp_path / "path.pyz"
        as_str = str(tmp_path / "str.pyz")

        zipapp.create_archive(source, as_path, main="pkg:main", interpreter=INTERPRETER)
        zipapp.create_archive(source, as_str, main="pkg:main", interpreter=INTERPRETER)

        for target in (as_path, as_str):
            assert zipapp.get_interpreter(target) == INTERPRETER
            assert is_executable(target)
            with open(target, "rb") as handle:
                assert handle.read(2) == b"#!"

    @NEEDS_EXEC_BIT
    def test_no_interpreter_means_no_shebang_and_no_bit(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        target = tmp_path / "app.pyz"

        zipapp.create_archive(source, target, main="pkg:main")

        assert zipapp.get_interpreter(target) is None
        assert not is_executable(target)
        assert target.read_bytes()[:2] == b"PK"


class TestZipAppErrorLeavesNoFile:
    """Every refusal happens before the target is opened."""

    @pytest.mark.parametrize(
        ("prepare", "kwargs", "message"),
        [
            (lambda root: root / "missing", {}, "Source does not exist"),
            (lambda root: app_tree(root), {}, "no entry point"),
            (lambda root: app_tree(root), {"main": "not-an-identifier"}, "Invalid entry point"),
            (
                lambda root: _tree_with_main(root),
                {"main": "pkg:main"},
                "Cannot specify entry point",
            ),
        ],
    )
    def test_the_refusals_every_version_shares(
        self,
        tmp_path: pathlib.Path,
        prepare: Callable[[pathlib.Path], pathlib.Path],
        kwargs: dict[str, Any],
        message: str,
    ) -> None:
        source = prepare(tmp_path)
        target = tmp_path / "never.pyz"

        with pytest.raises(zipapp.ZipAppError, match=message):
            zipapp.create_archive(source, target, **kwargs)

        assert not target.exists()

    def test_it_is_a_value_error(self) -> None:
        assert issubclass(zipapp.ZipAppError, ValueError)

    def test_a_target_inside_the_source(self, tmp_path: pathlib.Path) -> None:
        """Up to 3.13 the fresh target is walked into itself; 3.14 lists first."""
        source = app_tree(tmp_path)
        target = source / "app.pyz"

        zipapp.create_archive(source, target, main="pkg:main")

        if LISTS_BEFORE_WRITING:
            assert "app.pyz" not in names_in(target)
        else:
            assert "app.pyz" in names_in(target)

    @pytest.mark.skipif(not LISTS_BEFORE_WRITING, reason="the guard exists from 3.14")
    def test_an_existing_target_inside_the_source_is_refused(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        target = source / "app.pyz"
        target.write_bytes(b"an earlier build")

        with pytest.raises(zipapp.ZipAppError, match="overwrites one of the source files"):
            zipapp.create_archive(source, target, main="pkg:main")

        assert target.read_bytes() == b"an earlier build"


def _tree_with_main(root: pathlib.Path) -> pathlib.Path:
    source = app_tree(root)
    (source / "__main__.py").write_text("", encoding="utf-8")
    return source


class TestCopyingAnArchive:
    """The second table: a byte copy behind a new first line."""

    def test_the_copy_is_the_source_behind_a_new_shebang(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        built = tmp_path / "built.pyz"
        zipapp.create_archive(source, built, main="pkg:main")
        shipped = tmp_path / "shipped.pyz"

        zipapp.create_archive(built, shipped, interpreter=INTERPRETER)

        assert shipped.read_bytes() == f"#!{INTERPRETER}\n".encode() + built.read_bytes()

    def test_copying_without_an_interpreter_drops_the_shebang(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        shipped = tmp_path / "shipped.pyz"
        zipapp.create_archive(source, shipped, main="pkg:main", interpreter=INTERPRETER)
        assert shipped.read_bytes()[:2] == b"#!"
        plain = tmp_path / "plain.pyz"

        zipapp.create_archive(shipped, plain)

        assert zipapp.get_interpreter(plain) is None
        assert plain.read_bytes() == shipped.read_bytes().split(b"\n", 1)[1]

    def test_the_source_is_not_parsed(self, tmp_path: pathlib.Path) -> None:
        not_an_archive = tmp_path / "notes.txt"
        not_an_archive.write_bytes(b"#!/old/interpreter\nnot a zip archive\n")
        copied = tmp_path / "notes.pyz"

        zipapp.create_archive(not_an_archive, copied, interpreter="/new/interpreter")

        assert copied.read_bytes() == b"#!/new/interpreter\nnot a zip archive\n"

    def test_the_copy_streams(self, tmp_path: pathlib.Path) -> None:
        """O(1) space: an eight-megabyte copy peaks well under its size."""
        payload = 8_000_000
        big = tmp_path / "big.pyz"
        big.write_bytes(b"PK" + os.urandom(payload - 2))  # never a shebang
        copied = tmp_path / "copied.pyz"

        tracemalloc.start()
        tracemalloc.reset_peak()
        try:
            zipapp.create_archive(big, copied, interpreter=INTERPRETER)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert peak < payload / 2, peak
        assert copied.stat().st_size == payload + len(f"#!{INTERPRETER}\n")

    def test_file_objects_work_on_both_sides(self, tmp_path: pathlib.Path) -> None:
        source = io.BytesIO(b"#!/old\nPKpayload")
        target = io.BytesIO()

        zipapp.create_archive(source, target, interpreter="/new")

        assert target.getvalue() == b"#!/new\nPKpayload"

    @NEEDS_EXEC_BIT
    def test_only_a_str_target_gets_the_executable_bit(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        built = tmp_path / "built.pyz"
        zipapp.create_archive(source, built, main="pkg:main")
        as_str = str(tmp_path / "str.pyz")
        as_path = tmp_path / "path.pyz"

        zipapp.create_archive(built, as_str, interpreter=INTERPRETER)
        zipapp.create_archive(built, as_path, interpreter=INTERPRETER)

        assert zipapp.get_interpreter(as_str) == INTERPRETER
        assert zipapp.get_interpreter(as_path) == INTERPRETER
        assert is_executable(as_str)
        assert not is_executable(as_path)


class TestGetInterpreter:
    """Two bytes, then one line."""

    def test_reads_the_shebang_line_and_nothing_after_it(self) -> None:
        shebang = b"#!/usr/bin/python3\n"
        archive = CountingFile(shebang + b"z" * 10_000_000)

        assert zipapp.get_interpreter(archive) == "/usr/bin/python3"
        assert archive.handed_out == len(shebang)

    def test_reads_two_bytes_when_there_is_no_shebang(self) -> None:
        archive = CountingFile(b"PK" + b"z" * 10_000_000)

        assert zipapp.get_interpreter(archive) is None
        assert archive.handed_out == 2

    def test_accepts_a_path(self, tmp_path: pathlib.Path) -> None:
        archive = tmp_path / "app.pyz"
        archive.write_bytes(b"#!/usr/bin/env python3\nPK")

        assert zipapp.get_interpreter(archive) == "/usr/bin/env python3"
        assert zipapp.get_interpreter(str(archive)) == "/usr/bin/env python3"


IMPORT_DRIVER = textwrap.dedent(
    """
    import builtins
    import json
    import os
    import sys
    import zlib

    archive = sys.argv[1]
    compiles = []
    real_compile = builtins.compile

    def counting_compile(source, filename, *args, **kwargs):
        if str(filename).startswith(archive):
            compiles.append(str(filename)[len(archive) :].replace(os.sep, "/"))
        return real_compile(source, filename, *args, **kwargs)

    inflations = []
    real_decompress = zlib.decompress

    def counting_decompress(*args, **kwargs):
        inflations.append(1)
        return real_decompress(*args, **kwargs)

    builtins.compile = counting_compile
    zlib.decompress = counting_decompress
    sys.path.insert(0, archive)
    import pkg
    import pkg.helper
    print(json.dumps([sorted(compiles), len(inflations), pkg.helper.VALUE]))
    """
)


RUN_DRIVER = textwrap.dedent(
    """
    import builtins
    import os
    import runpy
    import sys

    archive = sys.argv[1]
    compiled = set()
    real_compile = builtins.compile

    def counting_compile(source, filename, *args, **kwargs):
        if str(filename).startswith(archive):
            compiled.add(str(filename)[len(archive) :].replace(os.sep, "/"))
        return real_compile(source, filename, *args, **kwargs)

    builtins.compile = counting_compile
    runpy.run_path(archive, run_name="__main__")
    sys.stderr.write("\\n".join(sorted(compiled)))
    """
)


def compile_beside(source: pathlib.Path) -> None:
    """A timestamp-validated `.pyc` next to every `.py`, whatever the environment's default."""
    compileall.compile_dir(
        source,
        legacy=True,
        quiet=1,
        invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
    )


def compiled_when_run(archive: pathlib.Path) -> list[str]:
    """The members of the archive compiled by running it as an application."""
    result = subprocess.run(
        [sys.executable, "-c", RUN_DRIVER, str(archive)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert result.stdout == "hi\n"
    return result.stderr.splitlines()


def imports_from(archive: pathlib.Path) -> tuple[list[str], int, int]:
    """Importing `pkg` and `pkg.helper` from the archive in a fresh process.

    Returns the members compiled, one entry per compile call, the number of
    zlib inflations, and the `VALUE` the helper module ended up with.
    """
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_DRIVER, str(archive)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    compiled, inflations, value = json.loads(result.stdout)
    return compiled, inflations, value


BOTH_TWICE = ["/pkg/__init__.py", "/pkg/__init__.py", "/pkg/helper.py", "/pkg/helper.py"]


class TestRunningAnArchive:
    """The third table: sources compile at every start, bytecode does not."""

    def test_sources_compile_on_every_start(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        target = tmp_path / "app.pyz"
        zipapp.create_archive(source, target, main="pkg:main")

        before = target.read_bytes()

        first = imports_from(target)
        second = imports_from(target)

        assert first == (BOTH_TWICE, 0, 1), first
        assert second == (BOTH_TWICE, 0, 1), second
        assert target.read_bytes() == before
        assert sorted(tmp_path.iterdir()) == [source, target]

    def test_bytecode_beside_the_source_is_used_instead(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        compile_beside(source)
        target = tmp_path / "app.pyz"
        zipapp.create_archive(source, target, main="pkg:main")
        assert {"pkg/__init__.pyc", "pkg/helper.pyc"} <= set(names_in(target))

        assert imports_from(target) == ([], 0, 1)

    def test_stale_bytecode_falls_back_to_the_source(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        compile_beside(source)
        (source / "pkg" / "helper.py").write_text("VALUE = 12345\n", encoding="utf-8")
        target = tmp_path / "app.pyz"
        zipapp.create_archive(source, target, main="pkg:main")

        assert imports_from(target) == (["/pkg/helper.py", "/pkg/helper.py"], 0, 12345)

    def test_a_packed_pycache_is_ignored(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        compileall.compile_dir(source, quiet=1)
        target = tmp_path / "app.pyz"
        zipapp.create_archive(source, target, main="pkg:main")
        assert any(name.startswith("pkg/__pycache__/") for name in names_in(target))

        assert imports_from(target) == (BOTH_TWICE, 0, 1)

    def test_running_the_archive_compiles_the_generated_main_only(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = app_tree(tmp_path)
        as_source = tmp_path / "source.pyz"
        zipapp.create_archive(source, as_source, main="pkg:main")
        compile_beside(source)
        as_bytecode = tmp_path / "bytecode.pyz"
        zipapp.create_archive(source, as_bytecode, main="pkg:main")

        assert compiled_when_run(as_source) == ["/__main__.py", "/pkg/__init__.py"]
        assert compiled_when_run(as_bytecode) == ["/__main__.py"]

    def test_a_deflated_member_is_inflated_on_import(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        stored = tmp_path / "stored.pyz"
        deflated = tmp_path / "deflated.pyz"
        zipapp.create_archive(source, stored, main="pkg:main")
        zipapp.create_archive(source, deflated, main="pkg:main", compressed=True)

        assert imports_from(stored) == (BOTH_TWICE, 0, 1)
        assert imports_from(deflated) == (BOTH_TWICE, 4, 1)

    def test_the_archive_runs(self, tmp_path: pathlib.Path) -> None:
        source = app_tree(tmp_path)
        target = tmp_path / "app.pyz"
        zipapp.create_archive(source, target, main="pkg:main")

        result = subprocess.run(
            [sys.executable, str(target)], capture_output=True, text=True, check=True, timeout=60
        )

        assert result.stdout == "hi\n"


def shell_commands() -> list[list[str]]:
    """The page's bash block, one argv per command, with `python` as this interpreter."""
    text = PAGE.read_text(encoding="utf-8")
    shell = re.search(r"```bash\n(.*?)```", text, re.DOTALL)
    assert shell is not None
    commands = [
        shlex.split(line) for line in shell.group(1).splitlines() if line.startswith("python")
    ]
    assert len(commands) == 3
    return [[sys.executable, *argv[1:]] for argv in commands]


def run_cli(argv: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60)


class TestCommandLine:
    """`python -m zipapp`, with the page's shell block run command by command."""

    def test_the_shell_block_builds_copies_and_reports(self, tmp_path: pathlib.Path) -> None:
        app_tree(tmp_path)
        build, copy, info = shell_commands()

        for argv in (build, copy):
            result = run_cli(argv, tmp_path)
            assert result.returncode == 0, result.stderr
            assert result.stdout == ""
        result = run_cli(info, tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout == f"Interpreter: {INTERPRETER}\n"
        built = tmp_path / "app.pyz"
        shipped = tmp_path / "app-shipped.pyz"
        assert zipapp.get_interpreter(built) is None
        assert shipped.read_bytes() == f"#!{INTERPRETER}\n".encode() + built.read_bytes()
        if sys.platform != "win32":
            assert not is_executable(built)
            assert is_executable(shipped)

    def test_copying_onto_itself_or_with_a_new_main_is_refused(
        self, tmp_path: pathlib.Path
    ) -> None:
        app_tree(tmp_path)
        build = shell_commands()[0]
        assert run_cli(build, tmp_path).returncode == 0
        built = tmp_path / "app.pyz"
        before = built.read_bytes()
        prefix = [sys.executable, "-m", "zipapp"]

        in_place = run_cli([*prefix, "app.pyz", "-o", "app.pyz"], tmp_path)
        no_output = run_cli([*prefix, "app.pyz"], tmp_path)
        new_main = run_cli([*prefix, "app.pyz", "-m", "pkg:main", "-o", "other.pyz"], tmp_path)

        assert "In-place editing" in in_place.stderr
        assert "In-place editing" in no_output.stderr
        assert "Cannot change the main function" in new_main.stderr
        assert built.read_bytes() == before
        assert not (tmp_path / "other.pyz").exists()


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
        [sys.executable, str(script)], cwd=cwd, capture_output=True, text=True, timeout=120
    )


class TestDocumentedExamples:
    """Each block builds its own tree under a temporary directory and asserts its result."""

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
        line, source = next((n, s) for n, s in _blocks() if "sorted(seen) == offered" in s)
        mutated = source.replace("sorted(seen) == offered", "sorted(seen) != offered", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
