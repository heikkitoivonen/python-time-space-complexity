"""Tests for docs/stdlib/spwd.md.

The page prices both functions by the entries in the shadow password
database: `getspnam()` reads it in order until the name matches, and
`getspall()` reads it through and keeps every entry the backends enumerate.
Neither bound can be timed here. The database is the host's, which a test
cannot grow without root, and its backend is chosen by `/etc/nsswitch.conf`.
So the bounds are read from source, and what runs is the module's interface
and its behaviour with the test process's own access on Linux 3.10 to 3.12,
the removal boundary, and the page's examples against a stand-in module. `Modules/spwdmodule.c` differs between
v3.10.19, v3.11.14 and v3.12.12 only in the import-time DeprecationWarning
added in 3.11 and a multiple-interpreters slot added in 3.12.

Measurement scope:

* From 3.13, `import spwd` raises `ModuleNotFoundError`. On Linux, importing
  it in a subprocess warns on 3.11 and 3.12 and not on 3.10.
* On Linux 3.10 to 3.12, `spwd.struct_spwd` built from nine values is a
  9-item tuple whose items at indices 0 to 8 are `sp_namp` to `sp_flag` in
  the page's order. The module's public names are `getspall`, `getspnam` and
  `struct_spwd`, the same as the stand-in's.
* On Linux 3.10 to 3.12, `getspall()` returns a list of `struct_spwd` and
  does not raise, and `getspnam()` of a name no account has raises `KeyError`
  or an `OSError`. The tests run with whatever access the process has; they
  neither need nor arrange an unprivileged one. As an unprivileged user, on
  a host whose `/etc/nsswitch.conf` reads `shadow: files systemd`, `getspall()` returned
  an empty list, `getspnam('root')` returned the entry the systemd backend
  supplies, and `getspnam()` raised `KeyError` for a missing name. That is
  observed, not asserted, as it is the host's configuration.
* Every fenced Python block runs in its own subprocess and working directory
  with a stand-in `spwd` module installed in `sys.modules`, and a mutated
  assertion in one of them is asserted to fail. The stand-in follows the
  source's interface: a positional-only `getspnam()` that raises `KeyError` for a
  missing name, and a `getspall()` that returns a new list. It shows that
  each block's own Python is sound; it says nothing about a real database.

Not settled here:

* The O(n) bounds and the in-order read: `getspnam()` is one call to the C
  library's `getspnam()`, and `getspall()` one `setspent()`, a `getspent()`
  per entry appended to a list, and one `endspent()`
  (`Modules/spwdmodule.c` at v3.12.12). That the `files` backend reads
  `/etc/shadow` line by line is the C library's; other backends set their
  own cost. The advice to read once with `getspall()` for many names, rather
  than call `getspnam()` per name, follows from those two bounds.
* Which exception an unprivileged `getspnam()` raises: the module raises
  `OSError` from `errno` when the C call fails with it set and `KeyError`
  when it is clear, and which the C library leaves is up to the backends
  configured. `getspall()` does not check `errno`, so a backend that cannot
  read the database contributes nothing instead of raising. Whether the
  examples' `root` entry exists is likewise the host's.
* The field meanings come from the official documentation and shadow(5).
  `sp_nam` and `sp_pwd`, attribute-only aliases of `sp_namp` and `sp_pwdp`
  that the module adds after the nine items, are not on the page, nor are
  the `n_fields`, `n_sequence_fields` and `n_unnamed_fields` every struct
  sequence type carries; the 3.12 audit lists them as needing
  classification.
* That `pwd` needs no privileges is priced on its own page.
* The module is not built on macOS or Windows, which lack `<shadow.h>`; that
  is a build fact, not run. A successful `getspnam()` result's fields are
  checked only through a constructed `struct_spwd`, as which entries a host
  returns, if any, is its own.
* API coverage: the audit on 3.14, where `spwd` is gone, checks no names for
  the page. Run on 3.12.14 it checks `spwd`, `getspall` and `getspnam`, and
  reports none missing.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import subprocess
import sys
import textwrap
import uuid
import warnings
from types import ModuleType

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "spwd.md"
EXPECTED_BLOCKS = 2

FIELDS = (
    "sp_namp",
    "sp_pwdp",
    "sp_lstchg",
    "sp_min",
    "sp_max",
    "sp_warn",
    "sp_inact",
    "sp_expire",
    "sp_flag",
)

HAS_SPWD = sys.platform == "linux" and sys.version_info < (3, 13)
needs_spwd = pytest.mark.skipif(
    not HAS_SPWD, reason="spwd exists on Linux before 3.13 (it needs <shadow.h>)"
)

STAND_IN = '''
"""A stand-in for the spwd module, following Modules/spwdmodule.c."""

class struct_spwd(tuple):
    _fields = (
        "sp_namp", "sp_pwdp", "sp_lstchg", "sp_min", "sp_max",
        "sp_warn", "sp_inact", "sp_expire", "sp_flag",
    )

    def __new__(cls, values):
        values = tuple(values)
        if len(values) != 9:
            raise TypeError("struct_spwd takes a 9-sequence")
        return super().__new__(cls, values)

    def __getattr__(self, name):
        try:
            return self[self._fields.index(name)]
        except ValueError:
            raise AttributeError(name) from None


_DATABASE = [
    struct_spwd(("root", "!", 19000, 0, 99999, 7, -1, -1, -1)),
    struct_spwd(("daemon", "*", 19000, 0, 99999, 7, -1, -1, -1)),
    struct_spwd(("alice", "$6$salt$hash", 19500, 0, 90, 7, 14, -1, -1)),
]


def getspnam(arg, /):
    if not isinstance(arg, str):
        raise TypeError("getspnam() argument must be str")
    for entry in _DATABASE:
        if entry.sp_namp == arg:
            return entry
    raise KeyError("getspnam(): name not found")


def getspall():
    return list(_DATABASE)
'''


def _spwd() -> ModuleType:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return importlib.import_module("spwd")


class TestAvailability:
    """`import spwd` warns on 3.11 and 3.12 and fails from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="spwd exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError) as caught:
            importlib.import_module("spwd")
        assert caught.value.name == "spwd"

    @needs_spwd
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-W", "error::DeprecationWarning", "-c", "import spwd"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if sys.version_info >= (3, 11):
            assert result.returncode != 0
            assert "'spwd' is deprecated" in result.stderr
        else:
            assert result.returncode == 0, result.stderr


@needs_spwd
class TestStructSpwd:
    """`struct_spwd` rows: a 9-item tuple whose items are also attributes,
    with indices 0 to 8 in the page's order."""

    def test_an_entry_is_a_nine_item_tuple_with_named_items(self) -> None:
        spwd = _spwd()
        values = ("name", "hash", 2, 3, 4, 5, 6, 7, 8)
        entry = spwd.struct_spwd(values)

        assert isinstance(entry, tuple)
        assert len(entry) == 9
        assert tuple(entry) == values
        for index, field in enumerate(FIELDS):
            assert getattr(entry, field) is entry[index]

    def test_the_public_names_match_the_stand_in(self) -> None:
        spwd = _spwd()
        stand_in: dict[str, object] = {}
        exec(STAND_IN, stand_in)

        names = {"getspall", "getspnam", "struct_spwd"}
        assert {name for name in dir(spwd) if not name.startswith("_")} == names
        assert {name for name in stand_in if not name.startswith("_")} == names
        assert vars(stand_in["struct_spwd"])["_fields"] == FIELDS


@needs_spwd
class TestLookupFailures:
    """`getspnam()` raises `KeyError` for a missing name, or an `OSError` such
    as `PermissionError` when a backend fails; `getspall()` returns what the
    backends enumerate rather than raising. Run with the process's own access."""

    def test_getspall_returns_a_list_of_entries_without_raising(self) -> None:
        spwd = _spwd()
        entries = spwd.getspall()

        assert isinstance(entries, list)
        assert all(isinstance(entry, spwd.struct_spwd) for entry in entries)

    def test_a_missing_name_raises_key_error_or_os_error(self) -> None:
        spwd = _spwd()
        missing = f"no-such-user-{uuid.uuid4().hex[:12]}"

        with pytest.raises((KeyError, OSError)):
            spwd.getspnam(missing)


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
    stand_in = cwd / "stand_in"
    stand_in.mkdir()
    (stand_in / "spwd.py").write_text(STAND_IN, encoding="utf-8")
    script = cwd / "block.py"
    # spwd is built into the interpreter on 3.10 to 3.12, where a module
    # first on sys.path would not shadow it, so the stand-in goes straight
    # into sys.modules.
    preamble = (
        "import importlib.util, sys\n"
        f"_spec = importlib.util.spec_from_file_location('spwd', {str(stand_in / 'spwd.py')!r})\n"
        "sys.modules['spwd'] = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(sys.modules['spwd'])\n"
    )
    script.write_text(preamble + source)
    return subprocess.run(
        [sys.executable, "-I", "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess against the stand-in, and
    asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import spwd" in source for _, source in blocks)

    def test_the_stand_in_is_the_module_the_blocks_import(self, tmp_path: pathlib.Path) -> None:
        result = _run_block(
            "import spwd, pathlib\nassert pathlib.Path(spwd.__file__).parent.name == 'stand_in'\n",
            tmp_path,
        )
        assert result.returncode == 0, result.stderr

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
        line, source = next((n, s) for n, s in _blocks() if "assert len(entry) == 9" in s)
        mutated = source.replace("assert len(entry) == 9", "assert len(entry) == 11", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
