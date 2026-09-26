"""Tests for docs/stdlib/stat.md.

The page prices every function at O(1) with no size variable, because each
takes one fixed-width mode. That is settled by observation rather than by a
stopwatch: the C functions refuse a mode wider than `mode_t`, the pure-Python
fallback walks a table of fixed length, and every mode renders to exactly ten
characters in both. The explanatory claims - that one `os.stat()` serves every
predicate while each `os.path` predicate makes its own call, that `os.stat()`
hides a link, that a platform without a file type has a 0 constant and an
always-false predicate - are settled by counting calls and by comparing results.

Measurement scope:

* The thirteen functions are asserted to be the `_stat` builtins, more than
  half of the constants to exist on `_stat`, and `Lib/stat.py` is loaded a second time with `_stat` blocked to get the
  fallback, whose functions are asserted to be Python functions defining the
  same public names except the ones `_stat` adds per platform.
* Fixed width: the C functions raise `OverflowError` for 2**64 and for -1.
  The fallback's `filemode()` walks `_filemode_table`, asserted to hold ten
  groups. `filemode()` is asserted to return ten characters for every mode
  from 0 to 0o177777 in both implementations, and the two are asserted equal
  over the seven POSIX file types combined with all 4,096 permission values.
* The type predicates are asserted against each of the seven `S_IF*` types.
  `S_ISDOOR()`, `S_ISPORT()` and `S_ISWHT()` are asserted, on every platform,
  to recognise their own constant where it is non-zero and to answer `False`
  for every 16-bit mode where it is 0; on Linux all three constants are
  asserted to be 0.
* `os.path.isfile()`, `os.path.isdir()` and `os.path.exists()` are asserted to
  call `os.stat` once each by replacing it with a counter, and the predicates
  applied to a mode already fetched to call it zero times. A symlink is
  asserted to be a regular file through `os.stat()` and `Path.stat()` and a
  link through `os.lstat()` and `Path.lstat()`. `DirEntry.stat()` is asserted
  to return the same object on a second call.
* `S_IREAD`, `S_IWRITE`, `S_IEXEC` and `S_ENFMT` are asserted equal to the bits
  they alias. `S_IMODE()` is asserted to strip the type and keep the set-ID and
  sticky bits, and its result to round-trip through `os.chmod()`.
  `shutil.copymode()` is asserted to copy the permission bits. The `ST_*`
  indices are asserted to read the same values as the named attributes, the
  three timestamps truncated to whole seconds.
* The seven flag constants 3.13 added are asserted present from 3.13 and
  absent before it; run on 3.12 and 3.13. The seventeen `FILE_ATTRIBUTE_*` and
  the older `UF_*`/`SF_*` constants are asserted present on every platform.
* Every fenced Python block runs in its own subprocess and temporary working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That the C functions do a fixed number of bit operations is read from
  Modules/_stat.c; that the fallback's are fixed is read from Lib/stat.py.
  No timing test is made, as there is no size to vary.
* `filemode()` returns `?` for a mode with no file-type bits from the C module
  on every supported version, which is what the page states. The fallback
  returns `-` there before 3.13; the fallback is not what `stat` uses where
  `_stat` exists, and modes with an invalid type field are not compared.
* Platform-only rows, category D, skipped or unreached on Linux: `S_IFDOOR`
  and `S_IFPORT` being non-zero on Solaris and `S_IFWHT` on BSD and macOS;
  `SF_SUPPORTED` and `SF_SYNTHETIC` existing on macOS from 3.13; the
  `IO_REPARSE_TAG_*` constants existing on Windows; `st_file_attributes` and
  `st_reparse_tag` being filled in on Windows, and `st_flags` and
  `os.chflags()` on BSD and macOS. On Linux the tests assert only that these
  names and fields are absent.
* That `os.path.exists()` and its siblings each cost a system call is observed
  on Linux as one `os.stat` call each; the system calls themselves are not
  counted. On Windows from 3.12, Lib/ntpath.py binds them to `nt._path_*`
  helpers that do not call `os.stat`, so the count there is category D.
* That every name outside the platform-only set exists on every platform is
  read from Lib/stat.py, which defines its names unconditionally; the test
  compares it with the running platform's `stat` only.
"""

from __future__ import annotations

import _stat
import importlib.util
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import types
from collections.abc import Iterator

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "stat.md"
EXPECTED_BLOCKS = 6

FUNCTIONS = (
    "S_ISDIR",
    "S_ISCHR",
    "S_ISBLK",
    "S_ISREG",
    "S_ISFIFO",
    "S_ISLNK",
    "S_ISSOCK",
    "S_ISDOOR",
    "S_ISPORT",
    "S_ISWHT",
    "S_IMODE",
    "S_IFMT",
    "filemode",
)

TYPES = {
    "S_IFSOCK": "S_ISSOCK",
    "S_IFLNK": "S_ISLNK",
    "S_IFREG": "S_ISREG",
    "S_IFBLK": "S_ISBLK",
    "S_IFDIR": "S_ISDIR",
    "S_IFCHR": "S_ISCHR",
    "S_IFIFO": "S_ISFIFO",
}

PLATFORM_ONLY = {"SF_SUPPORTED", "SF_SYNTHETIC"} | {
    "IO_REPARSE_TAG_SYMLINK",
    "IO_REPARSE_TAG_MOUNT_POINT",
    "IO_REPARSE_TAG_APPEXECLINK",
}

ADDED_IN_313 = (
    "UF_SETTABLE",
    "UF_TRACKED",
    "UF_DATAVAULT",
    "SF_SETTABLE",
    "SF_RESTRICTED",
    "SF_FIRMLINK",
    "SF_DATALESS",
)


def load_fallback() -> types.ModuleType:
    """Lib/stat.py executed with `_stat` unimportable, as a fresh module."""
    spec = importlib.util.spec_from_file_location("_stat_fallback", stat.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    saved = sys.modules.get("_stat")
    sys.modules["_stat"] = None  # type: ignore[assignment]
    try:
        spec.loader.exec_module(module)
    finally:
        if saved is None:
            del sys.modules["_stat"]
        else:
            sys.modules["_stat"] = saved
    return module


def public_names(module: types.ModuleType) -> set[str]:
    return {name for name in dir(module) if not name.startswith("_")} - {"stat"}


def valid_modes() -> Iterator[int]:
    """The seven POSIX file types, each with every permission value."""
    for type_name in TYPES:
        for permissions in range(0o10000):
            yield getattr(stat, type_name) | permissions


@pytest.fixture(scope="module")
def fallback() -> types.ModuleType:
    return load_fallback()


class TestTheCModuleIsWhatRuns:
    """The page: the functions and most constants come from the C `_stat`
    module, which `Lib/stat.py` imports over its own pure-Python definitions.
    Identity separates the two: a re-export is the same object, a Python
    definition is a different type."""

    def test_every_function_is_the_c_builtin(self) -> None:
        for name in FUNCTIONS:
            assert getattr(stat, name) is getattr(_stat, name), name
            assert isinstance(getattr(stat, name), types.BuiltinFunctionType), name

    def test_most_constants_come_from_the_c_module(self) -> None:
        constants = {name for name in public_names(stat) if name not in FUNCTIONS}
        from_c = {name for name in constants if hasattr(_stat, name)}
        assert len(from_c) > len(constants) / 2, sorted(constants - from_c)

    def test_the_fallback_defines_python_functions(self, fallback: types.ModuleType) -> None:
        for name in FUNCTIONS:
            assert isinstance(getattr(fallback, name), types.FunctionType), name

    def test_the_fallback_defines_every_name_but_the_platform_ones(
        self, fallback: types.ModuleType
    ) -> None:
        assert public_names(stat) - PLATFORM_ONLY == public_names(fallback) - PLATFORM_ONLY
        assert not public_names(fallback) & PLATFORM_ONLY


class TestEveryModeIsFixedWidth:
    """Every row is O(1) with no size variable: a mode is a fixed-width
    integer. The C functions convert it to `mode_t` and reject what does not
    fit, rather than doing more work on a wider value; the fallback's
    `filemode()` walks a table of fixed length, one character per group."""

    @pytest.mark.parametrize("name", FUNCTIONS)
    def test_the_c_functions_reject_a_mode_wider_than_mode_t(self, name: str) -> None:
        with pytest.raises(OverflowError):
            getattr(stat, name)(2**64)
        with pytest.raises(OverflowError):
            getattr(stat, name)(-1)

    def test_the_fallback_table_has_ten_groups(self, fallback: types.ModuleType) -> None:
        assert len(fallback._filemode_table) == 10

    def test_filemode_is_ten_characters_for_every_mode(self, fallback: types.ModuleType) -> None:
        for implementation in (stat, fallback):
            lengths = {len(implementation.filemode(mode)) for mode in range(0o200000)}
            assert lengths == {10}, implementation.__name__

    def test_the_two_implementations_agree_on_valid_modes(self, fallback: types.ModuleType) -> None:
        mismatches = [
            mode for mode in valid_modes() if stat.filemode(mode) != fallback.filemode(mode)
        ]
        assert not mismatches, [oct(mode) for mode in mismatches[:5]]


class TestFileTypePredicates:
    """Each `S_IS*()` compares the file-type bits with one type. `S_ISDOOR()`,
    `S_ISPORT()` and `S_ISWHT()` are "always `False` on a platform without the
    type", whose `S_IF*` constant is then 0."""

    def test_each_predicate_accepts_only_its_own_type(self) -> None:
        for type_name, predicate_name in TYPES.items():
            for other in TYPES:
                mode = getattr(stat, other) | 0o644
                expected = other == type_name
                assert getattr(stat, predicate_name)(mode) is expected, (predicate_name, other)
            assert stat.S_IFMT(getattr(stat, type_name) | 0o7777) == getattr(stat, type_name)

    @pytest.mark.parametrize(
        ("constant", "predicate"),
        [("S_IFDOOR", "S_ISDOOR"), ("S_IFPORT", "S_ISPORT"), ("S_IFWHT", "S_ISWHT")],
    )
    def test_a_missing_type_is_zero_and_never_matches(self, constant: str, predicate: str) -> None:
        value = getattr(stat, constant)
        check = getattr(stat, predicate)
        if value:
            assert check(value | 0o644)
            assert not check(stat.S_IFREG | 0o644)
        else:
            assert not any(check(mode) for mode in range(0o200000))

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux has none of them")
    def test_linux_has_no_doors_ports_or_whiteouts(self) -> None:
        assert stat.S_IFDOOR == stat.S_IFPORT == stat.S_IFWHT == 0
        assert stat.S_IFMT(0o644) == stat.S_IFDOOR

    def test_filemode_marks_an_unknown_type(self) -> None:
        assert stat.filemode(0o644) == "?rw-r--r--"


class TestOneStatAnswersEveryQuestion:
    """The page: "`os.path.isfile()`, `os.path.isdir()` and `os.path.exists()`
    each make a system call of their own", while the predicates on a fetched mode make
    none. A counter substituted for `os.stat` separates the two."""

    def test_each_os_path_predicate_stats_again(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "data.txt"
        path.write_text("hello")
        calls: list[object] = []
        real = os.stat

        def counting(target: object, *args: object, **kwargs: object) -> os.stat_result:
            calls.append(target)
            return real(target, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "stat", counting)
        os.path.isfile(path)
        os.path.isdir(path)
        os.path.exists(path)
        assert len(calls) == 3

        calls.clear()
        mode = os.stat(path).st_mode
        assert stat.S_ISREG(mode) and not stat.S_ISDIR(mode)
        assert stat.filemode(mode)[0] == "-"
        assert len(calls) == 1

    def test_stat_follows_a_link_and_lstat_does_not(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("")
        link = tmp_path / "link"
        os.symlink(target, link)

        assert stat.S_ISREG(os.stat(link).st_mode)
        assert not stat.S_ISLNK(os.stat(link).st_mode)
        assert stat.S_ISLNK(os.lstat(link).st_mode)
        assert link.stat().st_mode == os.stat(link).st_mode
        assert link.lstat().st_mode == os.lstat(link).st_mode

    def test_a_dir_entry_caches_its_stat(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "file.txt").write_text("")
        with os.scandir(tmp_path) as entries:
            (entry,) = entries
            first = entry.stat(follow_symlinks=False)
            assert entry.stat(follow_symlinks=False) is first


class TestPermissionBits:
    """`S_IREAD`, `S_IWRITE` and `S_IEXEC` are the owner bits and `S_ENFMT` is
    `S_ISGID`; `S_IMODE()` keeps "the permission bits, as `os.chmod()` takes
    them", set-ID and sticky bits included."""

    def test_the_aliases(self) -> None:
        assert stat.S_IREAD == stat.S_IRUSR
        assert stat.S_IWRITE == stat.S_IWUSR
        assert stat.S_IEXEC == stat.S_IXUSR
        assert stat.S_ENFMT == stat.S_ISGID
        assert not stat.S_IEXEC & (stat.S_IXGRP | stat.S_IXOTH)

    def test_the_masks_cover_their_bits(self) -> None:
        assert stat.S_IRWXU == stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
        assert stat.S_IRWXG == stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
        assert stat.S_IRWXO == stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH

    def test_imode_strips_the_type_and_keeps_the_special_bits(self) -> None:
        mode = stat.S_IFDIR | stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX | 0o755
        assert stat.S_IMODE(mode) == 0o7755
        assert stat.filemode(stat.S_IFREG | 0o4755) == "-rwsr-xr-x"
        assert stat.filemode(stat.S_IFDIR | 0o1777) == "drwxrwxrwt"

    def test_imode_round_trips_through_chmod(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "script.py"
        path.write_text("")
        os.chmod(path, 0o640)
        os.chmod(path, stat.S_IMODE(os.stat(path).st_mode) | stat.S_IXUSR)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o740

    def test_copymode_copies_the_permission_bits(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "source"
        target = tmp_path / "target"
        source.write_text("")
        target.write_text("")
        os.chmod(source, 0o751)
        os.chmod(target, 0o600)
        shutil.copymode(source, target)
        assert stat.S_IMODE(os.stat(target).st_mode) == 0o751


class TestTupleIndices:
    """The page: "Indices into an `os.stat_result`; `st[stat.ST_MODE]` is
    `st.st_mode`"."""

    def test_each_index_reads_its_field(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.txt"
        path.write_text("hello")
        st = os.stat(path)
        assert st[stat.ST_MODE] == st.st_mode
        assert st[stat.ST_INO] == st.st_ino
        assert st[stat.ST_DEV] == st.st_dev
        assert st[stat.ST_NLINK] == st.st_nlink
        assert st[stat.ST_UID] == st.st_uid
        assert st[stat.ST_GID] == st.st_gid
        assert st[stat.ST_SIZE] == st.st_size == 5
        assert st[stat.ST_ATIME] == int(st.st_atime)
        assert st[stat.ST_MTIME] == int(st.st_mtime)
        assert st[stat.ST_CTIME] == int(st.st_ctime)


class TestPlatformConstants:
    """The flag and attribute rows: which names exist where, and from which
    version. Rows only another platform can confirm are guarded and listed in
    the module docstring."""

    def test_the_windows_and_bsd_names_exist_everywhere(self) -> None:
        attributes = [name for name in dir(stat) if name.startswith("FILE_ATTRIBUTE_")]
        assert len(attributes) == 17
        for name in (
            "UF_NODUMP",
            "UF_IMMUTABLE",
            "UF_APPEND",
            "UF_OPAQUE",
            "UF_NOUNLINK",
            "UF_COMPRESSED",
            "UF_HIDDEN",
            "SF_ARCHIVED",
            "SF_IMMUTABLE",
            "SF_APPEND",
            "SF_NOUNLINK",
            "SF_SNAPSHOT",
        ):
            assert isinstance(getattr(stat, name), int), name
        assert stat.FILE_ATTRIBUTE_HIDDEN == 2
        assert stat.UF_HIDDEN == 0x8000

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_the_313_flags_exist(self) -> None:
        for name in ADDED_IN_313:
            assert isinstance(getattr(stat, name), int), name

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="present from 3.13")
    def test_the_313_flags_are_absent_before_it(self) -> None:
        for name in ADDED_IN_313:
            assert not hasattr(stat, name), name

    @pytest.mark.skipif(
        sys.platform != "darwin" or sys.version_info < (3, 13), reason="macOS, 3.13+"
    )
    def test_macos_has_the_supported_and_synthetic_masks(self) -> None:
        for name in ("SF_SUPPORTED", "SF_SYNTHETIC"):
            assert isinstance(getattr(stat, name), int), name

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only constants")
    def test_windows_has_the_reparse_tags(self) -> None:
        for name in PLATFORM_ONLY - {"SF_SUPPORTED", "SF_SYNTHETIC"}:
            assert isinstance(getattr(stat, name), int), name

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="asserts Linux's absence")
    def test_linux_has_none_of_the_platform_names_or_fields(self) -> None:
        assert not public_names(stat) & PLATFORM_ONLY
        st = os.stat(".")
        for field in ("st_file_attributes", "st_reparse_tag", "st_flags"):
            assert not hasattr(st, field), field
        assert not hasattr(os, "chflags")


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
    """Each block runs in its own subprocess and working directory, creates
    the files it stats in a temporary directory, and asserts its own result.
    The symlink blocks need a platform where an unprivileged process may make
    links, which Linux is."""

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
        needle = "stat.S_ISLNK(os.lstat(link).st_mode)"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "stat.S_ISLNK(os.stat(link).st_mode)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
