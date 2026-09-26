"""Tests for docs/stdlib/sysconfig.md.

The page splits the module in two: configuration variables are loaded once and
then served from one shared dictionary, while install paths are expanded afresh
on every call from all of those variables. Both halves are settled by growing
the live configuration cache by 100,000 entries and watching what moves: a
cached read peaks under 1 KB in the grown cache, and an expansion's traced peak
grows with the cache. Identity checks settle which accessors hand back module state
rather than a copy, and call counters settle the file-reading rows.

Measurement scope:

* `get_config_vars()` returns the same dictionary on every call, and a key
  written into it is what `get_config_var()` then returns. A fresh `python -I`
  subprocess shows `import sysconfig` leaves the cache unset, and on POSIX the
  build's `_sysconfigdata` module unimported, until the first
  `get_config_var()` call.
* With 100,000 entries added to the cache, `get_config_var()` peaks under
  1 KB, and in a timing test costs under 3x what it did before the entries were
  added. `get_paths()`, `get_path()`, `get_makefile_filename()` and
  `get_config_h_filename()` peak more than 20x higher with the entries than
  without, and `get_paths()` in a timing test costs more than 5x as much; that
  is the V term. The two filename functions are skipped in a source-tree
  build, where they do not go through `get_path()`.
* `get_paths(vars=d)` is asserted to leave the caller's value for `base` in
  `d`, use it in `purelib`, and add every configuration variable to `d`.
  `get_paths(expand=False)` is the same object on two calls and allocates
  under 1 KB.
* `parse_config_h()` is handed a counting file of 100,000 lines: it calls
  `readline()` once per line plus once at end of file, and never `read()` or
  `readlines()`. A file of 100,000 comment lines peaks under 20 KB; one of
  100,000 definitions peaks over 2 MB. A dictionary passed as `vars` is the one
  returned, with the parsed names added to what it held.
* `get_path_names()` is the same tuple on two calls; `get_scheme_names()` is a
  sorted tuple containing `posix_prefix` and `nt`; `get_python_version()` is
  `MAJOR.MINOR` from `sys.version_info`; `get_default_scheme()` and
  `get_preferred_scheme('prefix')` are `'venv'` when `sys.prefix` differs from
  `sys.base_prefix` on 3.11+ and never on 3.10; `_get_preferred_schemes()`
  has the keys `prefix`, `home` and `user`. `is_python_build()` is asserted
  to call `os.path.isfile()` at most twice. `get_platform()` is asserted to
  start with `linux-` on Linux.
* With `sys.prefix` moved, `get_config_vars()` returns a new dictionary whose
  `base` is the moved one on 3.12.8+ and 3.13.1+, and the same dictionary
  before those releases.
* `get_config_var('SO')` is `None` on 3.11+ and equals `EXT_SUFFIX` on 3.10.
* Every fenced Python block runs in its own subprocess, so no block sees
  another's first-call load, and a mutated assertion in one of them is
  asserted to fail.

Not settled here:

* That the first-call load is O(V). It imports the `_sysconfigdata` module the
  build generated and copies its dictionary, read from
  Lib/sysconfig/__init__.py (Lib/sysconfig.py before 3.13); the tests observe
  only that the load is deferred to the first call.
* That Windows has far fewer configuration variables. It is read from
  `_init_non_posix()`, which sets a short fixed list plus
  `_sysconfig.config_vars()`, and is never run here. The `get_platform()`
  rows on macOS and Windows are likewise unrun.
* In a source-tree build, `get_makefile_filename()` and
  `get_config_h_filename()` join a fixed directory and are O(1). No test runs
  from a source tree.
* That a changed `sys.exec_prefix` also rebuilds the cache from 3.14 is read
  from `get_config_vars()` in Lib/sysconfig/__init__.py; only a changed
  `sys.prefix` is tested.
* Treating scheme count, path count and the length of one path as O(1) is a
  definitional choice: the scheme table is fixed at import.
* `expand_makefile_vars()` is not priced. It is absent from the official
  documentation, and deprecated on 3.14 for removal in 3.16. The
  `python -m sysconfig` command line is not priced either.
"""

from __future__ import annotations

import io
import os
import pathlib
import re
import subprocess
import sys
import sysconfig
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sysconfig.md"
EXPECTED_BLOCKS = 7
EXTRA_VARS = 100_000


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


@pytest.fixture
def grow_cache() -> Iterator[Callable[[], None]]:
    """Add EXTRA_VARS entries to the live configuration cache, and remove them afterwards."""
    config = sysconfig.get_config_vars()
    names = [f"ZZ_TEST_{index}" for index in range(EXTRA_VARS)]
    assert not config.keys() & set(names[:10]), "the test's names are already in the cache"

    def grow() -> None:
        config.update(dict.fromkeys(names, "x"))

    yield grow
    for name in names:
        config.pop(name, None)


class TestConfigVarsAreOneSharedCache:
    """`get_config_vars()` | O(1) | O(1) | the module's cache itself, and
    `get_config_var(name)` | O(1) | O(1) | one dict lookup.

    The cache is grown by 100,000 entries: a copy or a scan would move with it,
    and a lookup does not.
    """

    def test_every_call_returns_the_same_dictionary(self) -> None:
        assert sysconfig.get_config_vars() is sysconfig.get_config_vars()

    def test_a_change_to_it_is_what_get_config_var_returns(self) -> None:
        config = sysconfig.get_config_vars()
        assert "ZZ_TEST_SHARED" not in config
        try:
            config["ZZ_TEST_SHARED"] = "changed"
            assert sysconfig.get_config_var("ZZ_TEST_SHARED") == "changed"
        finally:
            del config["ZZ_TEST_SHARED"]

    def test_a_changed_prefix_rebuilds_the_cache_on_3_12_8_and_3_13_1(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        version = sys.version_info[:3]
        rebuilds = version >= (3, 13, 1) or (3, 12, 8) <= version < (3, 13)
        moved = os.path.join(sys.prefix, "moved")
        config = sysconfig.get_config_vars()

        monkeypatch.setattr(sys, "prefix", moved)
        after = sysconfig.get_config_vars()

        assert (after is not config) is rebuilds
        assert (after["base"] == moved) is rebuilds

    def test_unknown_names_read_as_none(self) -> None:
        assert sysconfig.get_config_var("NO_SUCH_VARIABLE") is None
        assert sysconfig.get_config_vars("py_version_short", "NO_SUCH_VARIABLE") == [
            sysconfig.get_python_version(),
            None,
        ]

    def test_a_lookup_peaks_under_1kb_in_a_grown_cache(
        self, grow_cache: Callable[[], None]
    ) -> None:
        grow_cache()
        sysconfig.get_config_var("prefix")  # warm

        peak = peak_bytes(lambda: sysconfig.get_config_var("prefix"))

        assert peak < 1_000, f"get_config_var allocated {peak} bytes over a grown cache"

    @pytest.mark.timing
    def test_a_lookup_does_not_slow_as_the_cache_grows(
        self, grow_cache: Callable[[], None]
    ) -> None:
        def lookup() -> Any:
            return sysconfig.get_config_var("prefix")

        before = best_ns(lookup, inner=1_000)
        grow_cache()
        after = best_ns(lookup, inner=1_000)

        ratio = after / before
        assert ratio < 3, (
            f"{EXTRA_VARS} more variables took get_config_var from {before:.0f}ns to "
            f"{after:.0f}ns, x{ratio:.2f}; a scan would scale with the cache"
        )

    def test_the_cache_is_loaded_on_first_use(self) -> None:
        name = "_sysconfigdata" if os.name == "posix" else ""
        script = textwrap.dedent(
            f"""
            import sys
            import sysconfig

            assert sysconfig._CONFIG_VARS is None
            loaded = [m for m in sys.modules if {name!r} and m.startswith({name!r})]
            assert not loaded, loaded

            sysconfig.get_config_var('prefix')

            assert sysconfig._CONFIG_VARS is not None
            if {name!r}:
                assert any(m.startswith({name!r}) for m in sys.modules)
            """
        )

        result = subprocess.run(
            [sys.executable, "-I", "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        assert result.returncode == 0, result.stderr


def _expansions() -> dict[str, Callable[[], Any]]:
    return {
        "get_paths": sysconfig.get_paths,
        "get_path": lambda: sysconfig.get_path("purelib"),
        "get_makefile_filename": sysconfig.get_makefile_filename,
        "get_config_h_filename": sysconfig.get_config_h_filename,
    }


class TestPathsAreExpandedFromEveryVariable:
    """`get_paths()`, `get_path(name)`, `get_makefile_filename()` and
    `get_config_h_filename()` | O(V) | O(V): nothing is cached, and each call
    merges every configuration variable into its substitution dictionary."""

    @pytest.mark.parametrize("name", list(_expansions()))
    def test_the_peak_grows_with_the_cache(self, name: str, grow_cache: Callable[[], None]) -> None:
        if name.endswith("filename") and sysconfig.is_python_build():
            pytest.skip("a source-tree build does not resolve these through get_path()")
        operation = _expansions()[name]
        operation()
        small = peak_bytes(operation)

        grow_cache()
        operation()
        large = peak_bytes(operation)

        assert large > small * 20, (
            f"{name} peaked at {small} bytes, then {large} with {EXTRA_VARS} more variables"
        )

    @pytest.mark.timing
    def test_get_paths_slows_as_the_cache_grows(self, grow_cache: Callable[[], None]) -> None:
        before = best_ns(sysconfig.get_paths, inner=5)
        grow_cache()
        after = best_ns(sysconfig.get_paths, inner=5)

        ratio = after / before
        assert ratio > 5, (
            f"{EXTRA_VARS} more variables took get_paths from {before:.0f}ns to "
            f"{after:.0f}ns, x{ratio:.2f}; a cached result would stay flat"
        )

    def test_get_path_is_one_entry_of_get_paths(self) -> None:
        paths = sysconfig.get_paths()

        assert set(sysconfig.get_path_names()) <= set(paths)
        assert paths["purelib"] == sysconfig.get_path("purelib")

    def test_a_vars_dict_is_filled_in_place(self) -> None:
        overrides = {"base": "/opt/app"}

        paths = sysconfig.get_paths(vars=overrides)

        assert paths["purelib"].startswith(os.path.normpath("/opt/app"))
        assert overrides["base"] == "/opt/app"
        assert overrides.keys() >= sysconfig.get_config_vars().keys()

    def test_unexpanded_templates_are_the_scheme_itself(self) -> None:
        first = sysconfig.get_paths(expand=False)

        peak = peak_bytes(lambda: sysconfig.get_paths(expand=False))

        assert sysconfig.get_paths(expand=False) is first
        assert "{base}" in first["purelib"]
        assert peak < 1_000, f"get_paths(expand=False) allocated {peak} bytes"


class CountingFile:
    """A text file that records which reading methods were called."""

    def __init__(self, text: str) -> None:
        self._file = io.StringIO(text)
        self.lines_read = 0

    def readline(self) -> str:
        self.lines_read += 1
        return self._file.readline()

    def read(self, *args: Any) -> str:
        raise AssertionError("parse_config_h read the whole file")

    def readlines(self, *args: Any) -> list[str]:
        raise AssertionError("parse_config_h read every line at once")


class TestParseConfigHReadsALineAtATime:
    """`parse_config_h(fp, vars=None)` | O(L) | O(D): one `readline()` per
    line, and only the definitions are kept."""

    LINES = 100_000

    def test_it_reads_one_line_per_call(self) -> None:
        source = CountingFile("/* nothing to see */\n" * self.LINES)

        assert sysconfig.parse_config_h(source) == {}  # type: ignore[arg-type]
        assert source.lines_read == self.LINES + 1

    def test_comment_lines_peak_small_and_definitions_large(self) -> None:
        comments = "/* nothing to see here at all */\n" * self.LINES
        definitions = "".join(f"#define NAME_{index} {index}\n" for index in range(self.LINES))

        # The files are built outside the measurement; parsing them is what is measured.
        comment_file, definition_file = io.StringIO(comments), io.StringIO(definitions)

        comment_peak = peak_bytes(lambda: sysconfig.parse_config_h(comment_file))
        definition_peak = peak_bytes(lambda: sysconfig.parse_config_h(definition_file))

        assert comment_peak < 20_000, f"{self.LINES} comment lines peaked at {comment_peak}"
        assert definition_peak > 2_000_000, (
            f"{self.LINES} definitions peaked at only {definition_peak}"
        )

    def test_it_parses_defines_undefs_and_strings(self) -> None:
        header = '#define HAVE_FORK 1\n#define PY_NAME "python"\n/* #undef HAVE_NOTHING */\n'

        values = sysconfig.parse_config_h(io.StringIO(header))

        assert values == {"HAVE_FORK": 1, "PY_NAME": '"python"', "HAVE_NOTHING": 0}

    def test_a_vars_dict_is_filled_and_returned(self) -> None:
        existing = {"KEPT": 1}

        result = sysconfig.parse_config_h(io.StringIO("#define ADDED 2\n"), existing)

        assert result is existing
        assert existing == {"KEPT": 1, "ADDED": 2}


class TestSchemesAndConstants:
    """The scheme table is fixed at import, so the scheme and path-name rows
    are O(1); the version, platform and build rows read what is already known."""

    def test_get_path_names_is_the_same_tuple(self) -> None:
        names = sysconfig.get_path_names()

        assert isinstance(names, tuple)
        assert sysconfig.get_path_names() is names
        assert {"stdlib", "purelib", "platlib", "scripts", "data"} <= set(names)

    def test_get_scheme_names_is_a_sorted_tuple(self) -> None:
        names = sysconfig.get_scheme_names()

        assert isinstance(names, tuple)
        assert list(names) == sorted(names)
        assert {"posix_prefix", "nt"} <= set(names)

    def test_preferred_schemes_cover_the_three_layouts(self) -> None:
        names = set(sysconfig.get_scheme_names())

        assert set(sysconfig._get_preferred_schemes()) == {"prefix", "home", "user"}  # noqa: SLF001
        assert sysconfig.get_preferred_scheme("home") in names
        assert sysconfig.get_default_scheme() in names

    @pytest.mark.parametrize("in_venv", [True, False])
    def test_the_default_scheme_is_venv_only_inside_one_on_311(
        self, in_venv: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prefix = sys.base_prefix + ("-venv" if in_venv else "")
        monkeypatch.setattr(sys, "prefix", prefix)

        expected_venv = in_venv and sys.version_info >= (3, 11)

        assert (sysconfig.get_default_scheme() == "venv") is expected_venv
        assert (sysconfig.get_preferred_scheme("prefix") == "venv") is expected_venv

    def test_get_python_version_is_major_dot_minor(self) -> None:
        expected = f"{sys.version_info[0]}.{sys.version_info[1]}"

        assert sysconfig.get_python_version() == expected

    @pytest.mark.skipif(sys.platform != "linux", reason="asserts the Linux platform tag")
    def test_get_platform_on_linux(self) -> None:
        assert sysconfig.get_platform().startswith("linux-")

    def test_is_python_build_checks_at_most_two_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        original = os.path.isfile

        def counting_isfile(path: Any) -> bool:
            calls.append(os.fspath(path))
            return original(path)

        monkeypatch.setattr(os.path, "isfile", counting_isfile)

        result = sysconfig.is_python_build()

        assert isinstance(result, bool)
        assert 1 <= len(calls) <= 2, calls


class TestTheSoVariable:
    """Version Notes: `get_config_var('SO')` is `None` on 3.11+."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="SO exists on 3.10")
    def test_so_is_gone(self) -> None:
        assert sysconfig.get_config_var("SO") is None
        assert sysconfig.get_config_var("EXT_SUFFIX")

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="SO is gone from 3.11")
    def test_so_is_ext_suffix_on_310(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            so = sysconfig.get_config_var("SO")

        assert so == sysconfig.get_config_var("EXT_SUFFIX")


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
    """Each block runs in its own subprocess, so each pays its own first-call
    load and none sees another's cache, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "get_config_vars() is config" in s)
        mutated = source.replace(
            "get_config_vars() is config", "get_config_vars() is not config", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
