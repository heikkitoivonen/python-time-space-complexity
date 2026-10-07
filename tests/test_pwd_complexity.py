"""Tests for docs/stdlib/pwd.md.

The page prices the Python side of each call: a lookup builds one entry of
seven fields, and `getpwall()` builds one for every entry the database
enumerates. The database is the machine's own, so its size cannot be varied
here; the rows are settled by observation instead - what each call returns,
that every call builds new entry objects, and that `getpwall()` returns one
entry per entry the C library enumerates.

Measurement scope:

* `getpwuid(0)` and `getpwnam()` of its name return equal `struct_passwd`
  entries that are not the same object, and two `getpwuid(0)` calls and two
  `getpwnam()` calls do the same. Two `getpwall()` calls return distinct
  lists sharing no entry object, with equal contents in any order. That
  nothing is cached in Python is read from Modules/pwdmodule.c, which keeps
  no state but the `struct_passwd` type: a cache could also hand back copies.
* `getpwall()` returns exactly as many entries as a `setpwent()` /
  `getpwent()` / `endpwent()` walk through ctypes counts, each a
  `struct_passwd`.
* `KeyError` for a uid and a name that `getpwall()` does not list and for
  the uid `2**32`, beyond a 32-bit `uid_t`; `TypeError` for a float and a
  string uid and for a bytes name. Each is asserted with its message.
* `struct_passwd` is a tuple subclass of seven items, the same values by
  index and by name, with integer `pw_uid` and `pw_gid`, and `n_fields`,
  `n_sequence_fields` and `n_unnamed_fields` of 7, 7 and 0.
* `os.path.expanduser('~name')` is observed to call `pwd.getpwnam()` once per
  call, with the name, through a counting wrapper, and to return its
  `pw_dir`.
* On Windows, `import pwd` raises `ModuleNotFoundError`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail with `AssertionError` on the
  mutated line.

Not settled here:

* The O(1) lookup and O(u) enumeration bounds are read from
  Modules/pwdmodule.c: `mkpwent()` decodes a fixed seven fields, and
  `getpwall()` calls it once per `getpwent()` entry. u cannot be varied
  without writing the system's user database, and the characters in each
  field are not priced.
* The O(1) `struct_passwd` rows are attribute reads on a struct sequence; the
  page's dictionary built from `getpwall()` is an ordinary dict. Neither is
  measured here.
* A uid or name that `getpwall()` does not list is taken to be missing. A
  backend that answers lookups it does not enumerate could make the KeyError
  tests fail; the CI runners use the local files.
* What the backend costs - a local file, a directory server, nscd or sssd -
  is outside every bound, and which backend answers is the system's
  configuration. That a directory service may not enumerate every user
  follows from its configuration and the official documentation; no such
  service is set up here.
* Windows is the only platform without the module that CI runs. WASI builds
  also omit it and are not run.
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pwd.md"
EXPECTED_BLOCKS = 2

UNIX = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows builds do not compile Modules/pwdmodule.c"
)
pwd: Any = importlib.import_module("pwd") if sys.platform != "win32" else None


def _unlisted_uid() -> int:
    """A uid that no enumerated entry has."""
    taken = {entry.pw_uid for entry in pwd.getpwall()}
    uid = 1_999_999_999
    while uid in taken:
        uid -= 1
    return uid


def _enumerated_by_libc() -> int:
    """Entries a setpwent/getpwent/endpwent walk returns, counted through ctypes."""
    import ctypes

    libc = ctypes.CDLL(None)
    libc.getpwent.restype = ctypes.c_void_p
    count = 0
    libc.setpwent()
    try:
        while libc.getpwent():
            count += 1
    finally:
        libc.endpwent()
    return count


@UNIX
class TestLookupsReturnFreshEntries:
    """`getpwuid()` and `getpwnam()` are O(1): one query, one seven-field
    entry built. Equal results that are not the same object show each call
    returns a fresh entry; that nothing is cached is read from the source."""

    def test_by_uid_and_by_name_agree(self) -> None:
        by_uid = pwd.getpwuid(0)
        by_name = pwd.getpwnam(by_uid.pw_name)

        assert isinstance(by_uid, pwd.struct_passwd)
        assert by_uid.pw_uid == 0
        assert by_name == by_uid

    def test_every_call_builds_a_new_entry(self) -> None:
        first = pwd.getpwuid(0)
        second = pwd.getpwuid(0)
        by_name = pwd.getpwnam(first.pw_name)
        again_by_name = pwd.getpwnam(first.pw_name)

        assert first == second == by_name == again_by_name
        assert first is not second and first is not by_name
        assert by_name is not again_by_name

    def test_a_missing_uid_raises_key_error(self) -> None:
        uid = _unlisted_uid()
        with pytest.raises(KeyError, match="uid not found"):
            pwd.getpwuid(uid)

    def test_a_missing_name_raises_key_error(self) -> None:
        names = {entry.pw_name for entry in pwd.getpwall()}
        name = "no-such-user-for-pwd-tests"
        assert name not in names
        with pytest.raises(KeyError, match="name not found"):
            pwd.getpwnam(name)

    def test_a_uid_beyond_uid_t_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="uid not found"):
            pwd.getpwuid(2**32)

    @pytest.mark.parametrize("uid", [0.0, "0"])
    def test_a_non_integer_uid_raises_type_error(self, uid: object) -> None:
        with pytest.raises(TypeError, match="uid should be integer"):
            pwd.getpwuid(uid)

    def test_a_bytes_name_raises_type_error(self) -> None:
        name = pwd.getpwuid(0).pw_name.encode()
        with pytest.raises(TypeError, match="must be str, not bytes"):
            pwd.getpwnam(name)


@UNIX
class TestGetpwallEnumeratesTheDatabase:
    """`getpwall()` is O(u): one entry for every entry the database
    enumerates. Counting the C library's own `getpwent()` walk separates one
    entry per database entry from a filtered or deduplicated result."""

    def test_one_entry_per_enumerated_record(self) -> None:
        entries = pwd.getpwall()

        assert isinstance(entries, list)
        assert len(entries) == _enumerated_by_libc()
        assert all(isinstance(entry, pwd.struct_passwd) for entry in entries)

    def test_every_call_builds_a_new_list(self) -> None:
        first = pwd.getpwall()
        second = pwd.getpwall()

        assert first is not second
        assert {id(entry) for entry in first}.isdisjoint(id(entry) for entry in second)
        assert sorted(map(repr, first)) == sorted(map(repr, second))


@UNIX
class TestStructPasswd:
    """`struct_passwd` is a 7-tuple with named items; reading one is O(1)."""

    def test_it_is_a_seven_item_tuple_with_names(self) -> None:
        entry = pwd.getpwuid(0)
        names = ["pw_name", "pw_passwd", "pw_uid", "pw_gid", "pw_gecos", "pw_dir", "pw_shell"]

        assert issubclass(pwd.struct_passwd, tuple)
        assert len(entry) == 7
        for index, name in enumerate(names):
            assert entry[index] is getattr(entry, name)
        assert isinstance(entry.pw_uid, int) and isinstance(entry.pw_gid, int)

    def test_field_counts(self) -> None:
        assert pwd.struct_passwd.n_fields == 7
        assert pwd.struct_passwd.n_sequence_fields == 7
        assert pwd.struct_passwd.n_unnamed_fields == 0


@UNIX
class TestExpanduserAsksPwdEveryCall:
    """The page says `os.path.expanduser('~name')` asks `getpwnam()` on
    every call. A counting wrapper separates a call per expansion from a
    cached home directory."""

    def test_each_expansion_is_one_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real = pwd.getpwnam
        calls: list[str] = []

        def counting(name: str) -> Any:
            calls.append(name)
            return real(name)

        monkeypatch.setattr(pwd, "getpwnam", counting)
        name = pwd.getpwuid(0).pw_name
        home = real(name).pw_dir

        for _ in range(3):
            assert os.path.expanduser(f"~{name}") == home
        assert calls == [name] * 3


@pytest.mark.skipif(sys.platform != "win32", reason="Unix builds compile Modules/pwdmodule.c")
class TestWindowsHasNoPwd:
    """The page says `import pwd` raises `ModuleNotFoundError` on Windows."""

    def test_import_fails(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("pwd")


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
