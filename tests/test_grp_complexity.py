"""Tests for docs/stdlib/grp.md.

The page prices the Python side of each call: a lookup builds one entry with
its m member names, and `getgrall()` builds one for every entry the database
enumerates. The database is the machine's own, so its size cannot be varied
here; the rows are settled by observation instead - what each call returns,
that every call builds new entry objects, and that `getgrall()` returns one
entry per entry the C library enumerates.

Measurement scope:

* `getgrgid(0)` and `getgrnam()` of its name return equal `struct_group`
  entries that are not the same object, with distinct `gr_mem` lists, and two
  `getgrgid(0)` calls do the same: no entry is cached in Python. Two
  `getgrall()` calls return distinct lists sharing no entry object, with
  equal contents in any order. That nothing is cached in Python is read from
  Modules/grpmodule.c, which keeps no state but the `struct_group` type: a
  cache could also hand back copies.
* `getgrall()` returns exactly as many entries as a `setgrent()` /
  `getgrent()` / `endgrent()` walk through ctypes counts, each a
  `struct_group` whose `gr_mem` is a list of strings.
* `KeyError` for a gid and a name that `getgrall()` does not list, and
  `TypeError` for a float and a string gid, are asserted with their messages.
* `struct_group` is a tuple subclass of four items, the same values by index
  and by name, with `n_fields`, `n_sequence_fields` and `n_unnamed_fields`
  of 4, 4 and 0.
* `os.getgrouplist()` includes the group it is given, both a real primary
  group and a gid no group record lists.
* On Windows, `import grp` raises `ModuleNotFoundError`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail with `AssertionError` on the
  mutated line.

Not settled here:

* The O(m) lookup and O(g + t) enumeration bounds are read from
  Modules/grpmodule.c: `mkgrent()` decodes the name, password and each
  member once, and `getgrall()` calls it once per `getgrent()` entry. Neither
  g nor m can be varied without writing the system's group database.
* The O(1) `struct_group` rows are attribute reads on a struct sequence, and
  `user in entry.gr_mem` is a list scan; the page's dictionary built from
  `getgrall()` is an ordinary dict. None of these is measured here.
* A gid or name that `getgrall()` does not list is taken to be missing. A
  backend that answers lookups it does not enumerate could make the KeyError
  tests fail; the CI runners use the local files.
* What the backend costs - a local file, a directory server, nscd or sssd -
  is outside every bound, and which backend answers is the system's
  configuration.
* That a directory service may not enumerate every group, that `+`/`-`
  entries are NIS references, and that `gr_mem` usually omits users whose
  primary group it is all follow from the database's contents and the
  official documentation; no such database is set up here.
* Windows is the only platform without the module that CI runs. WASI,
  Android and iOS builds also omit it and are not run.
"""

from __future__ import annotations

import importlib
import os
import pathlib
import re
import subprocess
import sys
import textwrap
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "grp.md"
EXPECTED_BLOCKS = 3

UNIX = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows builds do not compile Modules/grpmodule.c"
)
grp: Any = importlib.import_module("grp") if sys.platform != "win32" else None


def _unlisted_gid() -> int:
    """A gid that no enumerated entry has."""
    taken = {entry.gr_gid for entry in grp.getgrall()}
    gid = 1_999_999_999
    while gid in taken:
        gid -= 1
    return gid


def _enumerated_by_libc() -> int:
    """Entries a setgrent/getgrent/endgrent walk returns, counted through ctypes."""
    import ctypes

    libc = ctypes.CDLL(None)
    libc.getgrent.restype = ctypes.c_void_p
    count = 0
    libc.setgrent()
    try:
        while libc.getgrent():
            count += 1
    finally:
        libc.endgrent()
    return count


@UNIX
class TestLookupsReturnFreshEntries:
    """`getgrgid()` and `getgrnam()` are O(m): one query, one entry built.
    Each call builds a new entry, so equal results that are not the same
    object separate a per-call build from a Python-side cache."""

    def test_by_gid_and_by_name_agree(self) -> None:
        by_gid = grp.getgrgid(0)
        by_name = grp.getgrnam(by_gid.gr_name)

        assert isinstance(by_gid, grp.struct_group)
        assert by_gid.gr_gid == 0
        assert by_name == by_gid

    def test_every_call_builds_a_new_entry(self) -> None:
        first = grp.getgrgid(0)
        second = grp.getgrgid(0)
        by_name = grp.getgrnam(first.gr_name)

        assert first == second == by_name
        assert first is not second and first is not by_name
        assert first.gr_mem is not second.gr_mem
        assert first.gr_mem is not by_name.gr_mem

    def test_a_missing_gid_raises_key_error(self) -> None:
        gid = _unlisted_gid()
        with pytest.raises(KeyError, match="gid not found"):
            grp.getgrgid(gid)

    def test_a_missing_name_raises_key_error(self) -> None:
        names = {entry.gr_name for entry in grp.getgrall()}
        name = "no-such-group-for-grp-tests"
        assert name not in names
        with pytest.raises(KeyError, match="name not found"):
            grp.getgrnam(name)

    @pytest.mark.parametrize("gid", [0.0, "0"])
    def test_a_non_integer_gid_raises_type_error(self, gid: object) -> None:
        with pytest.raises(TypeError, match="gid should be integer"):
            grp.getgrgid(gid)


@UNIX
class TestGetgrallEnumeratesTheDatabase:
    """`getgrall()` is O(g + t): one entry, with its member list, for every
    entry the database enumerates. Counting the C library's own
    `getgrent()` walk separates one entry per database entry from a
    filtered or deduplicated result."""

    def test_one_entry_per_enumerated_record(self) -> None:
        entries = grp.getgrall()

        assert isinstance(entries, list)
        assert len(entries) == _enumerated_by_libc()
        for entry in entries:
            assert isinstance(entry, grp.struct_group)
            assert isinstance(entry.gr_mem, list)
            assert all(isinstance(member, str) for member in entry.gr_mem)

    def test_every_call_builds_a_new_list(self) -> None:
        first = grp.getgrall()
        second = grp.getgrall()

        assert first is not second
        assert {id(entry) for entry in first}.isdisjoint(id(entry) for entry in second)
        assert sorted(map(repr, first)) == sorted(map(repr, second))


@UNIX
class TestStructGroup:
    """`struct_group` is a 4-tuple with named items; reading one is O(1)."""

    def test_it_is_a_four_item_tuple_with_names(self) -> None:
        entry = grp.getgrgid(0)

        assert issubclass(grp.struct_group, tuple)
        assert len(entry) == 4
        assert entry[0] is entry.gr_name
        assert entry[1] is entry.gr_passwd
        assert entry[2] is entry.gr_gid
        assert entry[3] is entry.gr_mem
        assert isinstance(entry.gr_gid, int)

    def test_field_counts(self) -> None:
        assert grp.struct_group.n_fields == 4
        assert grp.struct_group.n_sequence_fields == 4
        assert grp.struct_group.n_unnamed_fields == 0


@UNIX
class TestGetgrouplistIncludesTheGivenGroup:
    """`os.getgrouplist()` always includes the group passed in, which is why
    it finds a primary group that `gr_mem` does not list. A gid no record
    lists separates that from a result read from the group records."""

    def test_the_primary_group_is_included(self) -> None:
        import pwd

        user = pwd.getpwuid(0)
        assert user.pw_gid in os.getgrouplist(user.pw_name, user.pw_gid)

    def test_an_unlisted_group_is_included(self) -> None:
        import pwd

        user = pwd.getpwuid(0)
        gid = _unlisted_gid()
        assert gid not in {entry.gr_gid for entry in grp.getgrall()}
        assert gid in os.getgrouplist(user.pw_name, gid)


@pytest.mark.skipif(sys.platform != "win32", reason="Unix builds compile Modules/grpmodule.c")
class TestWindowsHasNoGrp:
    """The page says `import grp` raises `ModuleNotFoundError` on Windows."""

    def test_import_fails(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("grp")


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

    @UNIX
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

    @UNIX
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "same is not root" in s)
        mutated = source.replace("same is not root", "same is root", 1)
        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"

        original = tmp_path / "original"
        original.mkdir()
        assert _run_block(source, original).returncode == 0

        broken = tmp_path / "broken"
        broken.mkdir()
        result = _run_block(mutated, broken)
        assert result.returncode != 0
        assert "same is root" in result.stderr
        assert result.stderr.rstrip().splitlines()[-1].startswith("AssertionError")
