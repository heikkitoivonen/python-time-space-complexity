"""Tests for docs/stdlib/posix.md.

The page makes two kinds of claim. Every public function on `posix` is the
same object `os` exposes, so their bounds live on the os page and are tested
in test_os_complexity.py; this file pins the identity that makes that
delegation sound. The rest of the page prices `posix.environ`, the plain dict
the C environment was copied into at startup, and says which writes reach it
and which reach the process environment. All of that is settled by
observation - identity checks, dict membership, and the C library's own
`getenv()` read through ctypes - rather than by a clock.

Measurement scope:

* The identity row is checked over every public name in `dir(posix)`: each
  one but `environ` is the identical object under the same name on `os`, and
  `environ` is a different object from `os.environ`.
* `posix.environ` being a plain dict of bytes keys and bytes values is checked
  on the live object. Its contents are checked on a child interpreter started
  with a controlled environment: every variable the child was given is in its
  dict with the same value, and nothing else is beyond what the platform's C
  library adds to every process, at two environment sizes that differ by 64x.
  That is a payload check, not a measurement of the O(b): the bound, in time
  and in space, is read from `convertenviron()` in Modules/posixmodule.c,
  which makes one dict and one bytes object per key and per value and holds
  nothing else. Interpreter startup cannot be traced or timed from inside the
  interpreter.
* Reads returning the stored object are checked by identity on a 32-byte
  value; `os.environ` reading the same key is the control that decodes a
  fresh str each time. The O(k) hashing of the key is a property of dict and
  bytes and is not measured.
* Which writes reach where is read from two places at once: `posix.environ`
  membership, and the C library's `getenv()` through ctypes, which sees the
  process environment without starting a child. A direct dict write is
  visible to `os.environ` and invisible to `getenv()`; `os.putenv()` is the
  reverse; a write through `os.environ` reaches both. `os.reload_environ()`
  on 3.14+ then makes the `putenv()` write visible in the same dict object.
  The page's example uses a child process for the same fact; the test does
  not depend on which spawn path subprocess picks, because `getenv()` reads
  the parent's own environment. The reload test restores the whole dict
  afterwards, because a reload also syncs any drift other tests left between
  the dict and the process environment.
* The bounds of the `os.environ[key] = value`, `os.putenv()` and
  `os.reload_environ()` rows are the os page's rows, restated here only to
  say which of them reach this dict; test_os_complexity.py carries their
  evidence, and records that `setenv()`'s scan of the environment is
  unsettled there.

Not settled here:

* `posix` being unavailable on Windows is the reason this module skips there,
  which no run on this project's Linux CI verifies.
* A duplicate key in the C environment keeps its first value, by
  `PyDict_SetDefaultRef` in `convertenviron()`; `os.execve()` takes a mapping
  and so cannot hand a child a duplicate, and the page does not claim it.
"""

from __future__ import annotations

import ctypes
import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

if sys.platform == "win32":  # pragma: no cover - the module is Unix only
    pytest.skip("posix is a Unix-only module", allow_module_level=True)

import posix  # noqa: E402  (after the platform guard)

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "posix.md"
EXPECTED_BLOCKS = 3


def c_getenv(key: bytes) -> bytes | None:
    """The process environment as the C library sees it, no child needed."""
    libc = ctypes.CDLL(None)
    libc.getenv.restype = ctypes.c_char_p
    libc.getenv.argtypes = [ctypes.c_char_p]
    return libc.getenv(key)


class TestFunctionsAreOsFunctions:
    """Every public function is the same object os exposes."""

    def test_every_public_name_but_environ_is_the_same_object(self) -> None:
        public = [name for name in dir(posix) if not name.startswith("_")]
        shared = [name for name in public if getattr(os, name, None) is getattr(posix, name)]

        assert set(public) - set(shared) == {"environ"}, sorted(set(public) - set(shared))
        assert len(shared) > 100, len(shared)  # the check ran over the real module, not a stub
        assert posix.open is os.open
        assert posix.environ is not os.environ


class TestEnvironIsAPlainDict:
    """A bytes-keyed dict built once from the C environment."""

    def test_it_is_a_dict_of_bytes(self) -> None:
        assert type(posix.environ) is dict
        assert posix.environ, "an empty environment would make the type check vacuous"
        assert all(type(key) is bytes for key in posix.environ)
        assert all(type(value) is bytes for value in posix.environ.values())

    @pytest.mark.parametrize("variables", [4, 256])
    def test_a_child_holds_exactly_the_environment_it_was_given(self, variables: int) -> None:
        """O(b) space: every key and value byte handed to execve is in the dict."""
        environment = {f"POSIX_PAGE_{index:04d}": "v" * 60 for index in range(variables)}
        environment["PATH"] = os.environ["PATH"]
        report = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json, posix; "
                "print(json.dumps({k.decode(): v.decode() for k, v in posix.environ.items()}))",
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        held = json.loads(report.stdout)

        # A platform's C library may add a variable of its own to every process
        # it starts, so the extras are bounded rather than required to be empty.
        assert {k: held.get(k) for k in environment} == environment
        extras = set(held) - set(environment)
        assert len(extras) <= 2, sorted(extras)


class TestReads:
    """A read returns the stored object; os.environ decodes a fresh one."""

    def test_a_read_returns_the_stored_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSIX_PAGE_VALUE", "x" * 32)

        assert posix.environ[b"POSIX_PAGE_VALUE"] is posix.environ[b"POSIX_PAGE_VALUE"]
        assert os.environ["POSIX_PAGE_VALUE"] is not os.environ["POSIX_PAGE_VALUE"]


class TestWhatReachesWhere:
    """The three kinds of write, and the 3.14 reload."""

    def test_a_dict_write_reaches_os_environ_but_not_the_process(self) -> None:
        key = b"POSIX_PAGE_DICT_ONLY"
        assert key not in posix.environ and c_getenv(key) is None
        try:
            posix.environ[key] = b"1"

            assert os.environ[key.decode()] == "1"  # os.environ looks in this dict
            assert c_getenv(key) is None  # the process environment is untouched
        finally:
            posix.environ.pop(key, None)

    def test_putenv_reaches_the_process_but_not_the_dict(self) -> None:
        key = b"POSIX_PAGE_PUTENV"
        assert key not in posix.environ and c_getenv(key) is None
        try:
            os.putenv(key.decode(), "1")

            assert c_getenv(key) == b"1"
            assert key not in posix.environ
        finally:
            os.unsetenv(key.decode())

    def test_an_os_environ_write_reaches_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        key = b"POSIX_PAGE_BOTH"
        assert key not in posix.environ and c_getenv(key) is None

        monkeypatch.setenv(key.decode(), "1")

        assert posix.environ[key] == b"1"
        assert c_getenv(key) == b"1"

    @pytest.mark.skipif(not hasattr(os, "reload_environ"), reason="os.reload_environ is 3.14+")
    def test_reload_environ_refreshes_the_same_dict(self) -> None:
        reload_environ = getattr(os, "reload_environ")  # noqa: B009 - typeshed 3.14+
        key = b"POSIX_PAGE_RELOAD"
        before = posix.environ
        contents = dict(before)
        assert key not in before and c_getenv(key) is None
        try:
            os.putenv(key.decode(), "1")
            assert key not in posix.environ

            reload_environ()

            assert posix.environ is before  # rebuilt in place, not replaced
            assert posix.environ[key] == b"1"
        finally:
            os.unsetenv(key.decode())
            before.clear()
            before.update(contents)


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
    # The page's examples assert their demonstration names start out unset.
    environment = {k: v for k, v in os.environ.items() if k not in ("DICT_ONLY", "PROCESS_ONLY")}
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
    )


class TestDocumentedExamples:
    """Each fenced block runs on its own and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "posix.open is os.open" in s)
        mutated = source.replace("posix.open is os.open", "posix.open is os.read", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
