"""Tests for docs/stdlib/nis.md.

The page prices each call by the requests it makes to an NIS server and the
entries it brings back: one request for `match()`, one streamed transfer of
the whole map for `cat()`, several requests for `maps()`, and none for
`get_default_domain()`. None of that can be run here. The module exists on
Python 3.10 to 3.12 only in an interpreter built against the NIS client
library, which the uv-installed 3.10.21, 3.11.16 and 3.12.14 builds are not,
and every call but one needs a bound NIS domain. So the bounds are read from
`Modules/nismodule.c` at v3.12.12, and what runs is the removal boundary and
the page's examples, against a stand-in module. The file differs between
v3.10.19, v3.11.14 and v3.12.12 only in the import-time DeprecationWarning
added in 3.11 and in changes that move no bound.

Measurement scope:

* From 3.13, `import nis` raises `ModuleNotFoundError`.
* Every fenced Python block runs in its own subprocess and working directory
  with a stand-in `nis` module first on `sys.path`, and a mutated assertion in
  one of them is asserted to fail. The stand-in follows the source's
  interface: the nickname table, `str` keys and values, a new `dict` from
  `cat()`, `map` and `domain` as the keyword names, `TypeError` for a `None`
  domain, and `nis.error` for a missing key or map. It shows that each
  block's own Python is sound; it says nothing about a server.

Not settled here (source-only, `Modules/nismodule.c` at v3.12.12):

* `match()` is one `yp_match()` call and decodes one value; `cat()` is one
  `yp_all()` call, which the C library serves over a single TCP connection,
  inserting each entry into a new dict; `maps()` calls `yp_master()` for each
  nickname's map until one returns a master, then opens a TCP client to that
  master for one `YPPROC_MAPLIST` call and builds a list of the names;
  `get_default_domain()` is `yp_get_default_domain()`, which the C library
  answers from the host's domain name without a request.
* The nicknames, the `map`/`domain` keyword names, and `TypeError` for a
  `None` domain come from the `aliases` table and the `"Us|s"`, `"s|s"` and
  `"|s"` argument formats. Values are decoded with the filesystem encoding,
  so they are `str`, not the bytes the official documentation describes.
* The server's own lookup cost, and what a round trip costs, belong to the
  server and the network. The message `nis.error` carries is
  `yperr_string()`'s, which differs between C libraries, or the module's own
  when `maps()` finds no master.
* That `pwd` and `grp` reach NIS through the C library's name service is a
  property of the host's `nsswitch.conf`, not of Python.
* Windows never had the module, and it is absent from Unix builds without the
  NIS headers; both are build facts, not run.
* API coverage is provisional on the build: the audit reports `nis` as an
  import error on these interpreters, so it cannot inspect the module. The
  page prices the five names the 3.10 to 3.12 inventory lists: `cat`,
  `error`, `get_default_domain`, `maps` and `match`.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "nis.md"
EXPECTED_BLOCKS = 2

STAND_IN = '''
"""A stand-in for the nis module, following Modules/nismodule.c."""

_DOMAIN = "example.org"
_MAPS = {
    "passwd.byname": {
        "alice": "alice:x:1000:1000:Alice:/home/alice:/bin/sh",
        "bob": "bob:x:1001:1001:Bob:/home/bob:/bin/sh",
    },
    "group.byname": {"staff": "staff:x:50:alice,bob"},
}
_ALIASES = {
    "passwd": "passwd.byname",
    "group": "group.byname",
    "networks": "networks.byaddr",
    "hosts": "hosts.byname",
    "protocols": "protocols.bynumber",
    "services": "services.byname",
    "aliases": "mail.aliases",
    "ethers": "ethers.byname",
}


class error(Exception):
    pass


def _resolve(map, domain):
    if not isinstance(map, str) or not isinstance(domain, str):
        raise TypeError("map and domain must be str")
    if domain != _DOMAIN:
        raise error("Domain not bound")
    name = _ALIASES.get(map, map)
    if name not in _MAPS:
        raise error("No such map in server's domain")
    return _MAPS[name]


def get_default_domain():
    return _DOMAIN


def match(key, map, domain=_DOMAIN):
    if not isinstance(key, str):
        raise TypeError("key must be str")
    entries = _resolve(map, domain)
    if key not in entries:
        raise error("No such key in map")
    return entries[key]


def cat(map, domain=_DOMAIN):
    return dict(_resolve(map, domain))


def maps(domain=_DOMAIN):
    if not isinstance(domain, str):
        raise TypeError("domain must be str")
    if domain != _DOMAIN:
        raise error("Domain not bound")
    return list(_MAPS)
'''


class TestAvailability:
    """`import nis` fails from 3.13. Before that it depends on the build, so
    only the removal is asserted."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="nis may exist before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError) as caught:
            importlib.import_module("nis")
        assert caught.value.name == "nis"


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
    (stand_in / "nis.py").write_text(STAND_IN, encoding="utf-8")
    script = cwd / "block.py"
    script.write_text(f"import sys\nsys.path.insert(0, {str(stand_in)!r})\n{source}")
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
        assert all("import nis" in source for _, source in blocks)

    def test_the_stand_in_is_the_module_the_blocks_import(self, tmp_path: pathlib.Path) -> None:
        result = _run_block(
            "import nis, pathlib\nassert pathlib.Path(nis.__file__).parent.name == 'stand_in'\n",
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
        line, source = next((n, s) for n, s in _blocks() if "'passwd.byname' in maps" in s)
        mutated = source.replace("'passwd.byname' in maps", "'ethers.byname' in maps", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
