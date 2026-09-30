"""Tests for docs/stdlib/antigravity.md.

The page prices the module in two parts: the first import, whose cost is the
one `webbrowser.open()` call the module body makes, and `geohash()`,
whose only size-dependent work is an MD5 over `datedow`. Nothing here starts a
browser. Every import of the module happens either in a subprocess whose
environment has no `DISPLAY`, `WAYLAND_DISPLAY`, `TERM` or `BROWSER`, so that
on Linux browser discovery registers nothing, or behind a replaced
`webbrowser.open`. The in-process import used by the `geohash()` tests is
removed from `sys.modules` afterwards if it was not there before.

Measurement scope:

* The first import is observed in a fresh interpreter to call a replaced
  `webbrowser.open` exactly once, with `https://xkcd.com/353/`, and to succeed
  when that call returns `False`. A second `import` makes no further call and
  binds the object already in `sys.modules`.
* That the first import runs browser discovery unless something already has
  is counted on `webbrowser.register_standard_browsers`, wrapped in the
  subprocess: one call when the import is the first `webbrowser` use, none
  when an `open()` has already run. With the quiet environment the real
  `webbrowser.open()` finds no browser on Linux, the import succeeds, and a
  `subprocess.Popen` replaced to fail is never reached.
* That the import waits for `webbrowser.open()` is observed with a controller
  registered with `preferred=True` that sleeps 0.2 s before returning: it is
  called once with the comic's URL, and returns before the `import` statement
  does, which also shows the registration route the page recommends.
* `geohash()` is asserted to print `37.857713 -122.544543` for the xkcd 426
  example and to return `None`, and to call `hashlib.md5` once, on the
  `datedow` object itself. For that example and a southern, eastern one, the
  output is recomputed from the MD5 digest: the integer part of each
  coordinate followed by the fraction its digest half gives. A `str`
  `datedow` raises `TypeError`; a `bytearray` and a `memoryview` of the
  example's bytes print the same line as the bytes. The traced peak with a 10,000,000-byte
  `datedow` stays under 10 KB. A timing test runs it on 100,000, 1,000,000 and
  10,000,000 bytes: each 10x step costs between 4x and 30x, where a constant
  would give about 1x and a quadratic about 100x.
* Lib/antigravity.py is identical in the v3.10.19, v3.11.14, v3.12.12,
  v3.13.9 and v3.14.0 tags, so no bound on the page moves inside the
  supported range.
* Every fenced Python block runs in its own subprocess with the quiet
  environment, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(b + p) of the first import is `webbrowser.open()`'s bound: discovery's
  O(p) `PATH` probes and O(b) controllers tried are measured in
  tests/test_webbrowser_complexity.py, and only the call and the discovery it
  triggers are observed here.
* That a text-mode browser holds the import until the user quits follows from
  the synchronous call observed here and the text-mode controller's `wait()`,
  observed on the webbrowser page; no real browser is started.
* On macOS and Windows, discovery registers the system browser whatever the
  environment, so the two discovery tests, which let the real
  `webbrowser.open()` run, are limited to Linux and skip elsewhere.
* The module-level names `webbrowser` and `hashlib` are the imported modules,
  not API of this one, and are not documented. The shared public API audit
  reads `antigravity` from source, because importing it opens a browser, and
  the official API inventory lists no name inside it, so the audit checks only
  that this page exists; its name coverage is the page's two tables.
* `latitude` and `longitude` are ordinary degree values throughout; a float
  whose integer part has hundreds of digits would make `%d` formatting the
  cost, and is not measured.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import webbrowser
from collections.abc import Callable, Iterator
from itertools import pairwise
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "antigravity.md"
EXPECTED_BLOCKS = 2
COMIC = "https://xkcd.com/353/"


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


def quiet_env() -> dict[str, str]:
    """The environment without the variables that make discovery find a browser."""
    env = dict(os.environ)
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "TERM", "BROWSER"):
        env.pop(name, None)
    return env


def run_python(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter with the quiet environment."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=quiet_env(),
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def assert_ran(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="module")
def antigravity() -> Iterator[ModuleType]:
    """The module, imported behind a replaced `webbrowser.open`."""
    was_loaded = "antigravity" in sys.modules
    with mock.patch.object(webbrowser, "open", return_value=False):
        module = importlib.import_module("antigravity")
    yield module
    if not was_loaded:
        sys.modules.pop("antigravity", None)


def geohash_output(module: ModuleType, datedow: Any) -> tuple[str, Any]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = module.geohash(37.421542, -122.085589, datedow)
    return buffer.getvalue(), result


class TestTheFirstImportOpensTheComicOnce:
    """`import antigravity`, first in a process | O(b + p) | O(b + p): one
    `webbrowser.open()` call, discovery first unless it has run; again | O(1)
    | O(1): a `sys.modules` hit that does not run the body."""

    def test_the_first_import_calls_open_once_and_a_second_does_not(
        self, tmp_path: pathlib.Path
    ) -> None:
        result = run_python(
            f"""
            import sys
            import webbrowser
            from unittest import mock

            assert "antigravity" not in sys.modules
            with mock.patch.object(webbrowser, "open", return_value=False) as opened:
                import antigravity
                assert opened.call_count == 1
                first = sys.modules["antigravity"]
                import antigravity
            assert opened.call_args_list == [mock.call({COMIC!r})], opened.call_args_list
            assert antigravity is first
            """,
            tmp_path,
        )

        assert_ran(result)

    def test_the_import_runs_discovery_when_nothing_has(self, tmp_path: pathlib.Path) -> None:
        if not sys.platform.startswith("linux"):
            pytest.skip("platform: discovery registers the system browser outside Linux")
        result = run_python(
            """
            import subprocess
            import webbrowser

            def no_process(*args, **kwargs):
                raise AssertionError("a process was started")

            subprocess.Popen = no_process
            original = webbrowser.register_standard_browsers
            calls = []

            def counting():
                calls.append(1)
                return original()

            webbrowser.register_standard_browsers = counting
            import antigravity

            assert calls == [1], calls
            assert webbrowser._tryorder == [], webbrowser._tryorder
            """,
            tmp_path,
        )

        assert_ran(result)

    def test_the_import_skips_discovery_that_has_already_run(self, tmp_path: pathlib.Path) -> None:
        if not sys.platform.startswith("linux"):
            pytest.skip("platform: discovery registers the system browser outside Linux")
        result = run_python(
            """
            import subprocess
            import webbrowser

            def no_process(*args, **kwargs):
                raise AssertionError("a process was started")

            subprocess.Popen = no_process
            assert webbrowser.open("about:blank") is False
            calls = []
            webbrowser.register_standard_browsers = lambda: calls.append(1)
            import antigravity

            assert calls == [], calls
            """,
            tmp_path,
        )

        assert_ran(result)

    def test_the_import_waits_for_a_preferred_controller(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            f"""
            import webbrowser

            import time

            events = []

            class Recorder:
                name = "recorder"

                def open(self, url, new=0, autoraise=True):
                    events.append(url)
                    time.sleep(0.2)
                    events.append("returned")
                    return True

                def open_new(self, url):
                    return self.open(url, 1)

                def open_new_tab(self, url):
                    return self.open(url, 2)

            webbrowser.register("recorder", None, Recorder(), preferred=True)
            import antigravity
            events.append("imported")

            assert events == [{COMIC!r}, "returned", "imported"], events
            """,
            tmp_path,
        )

        assert_ran(result)


class TestGeohashHashesOnce:
    """`antigravity.geohash(latitude, longitude, datedow)` | O(n) | O(1): the
    MD5 over `datedow` is the only work that grows, and the coordinates are
    printed, not returned."""

    def test_the_xkcd_example(self, antigravity: ModuleType) -> None:
        output, result = geohash_output(antigravity, b"2005-05-26-10458.68")

        assert output == "37.857713 -122.544543\n"
        assert result is None

    @pytest.mark.parametrize(
        ("latitude", "longitude", "datedow"),
        [(37.421542, -122.085589, b"2005-05-26-10458.68"), (-33.9, 151.2, b"2024-01-02-37000.5")],
    )
    def test_the_digest_halves_replace_the_fractional_parts(
        self, antigravity: ModuleType, latitude: float, longitude: float, datedow: bytes
    ) -> None:
        digest = hashlib.md5(datedow, usedforsecurity=False).hexdigest()
        fractions = [f"{float.fromhex('0.' + half):f}"[1:] for half in (digest[:16], digest[16:])]
        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            antigravity.geohash(latitude, longitude, datedow)

        assert (
            buffer.getvalue() == f"{int(latitude)}{fractions[0]} {int(longitude)}{fractions[1]}\n"
        )

    @pytest.mark.parametrize("wrap", [bytearray, memoryview])
    def test_any_bytes_like_datedow_works(
        self, antigravity: ModuleType, wrap: Callable[[bytes], Any]
    ) -> None:
        output, result = geohash_output(antigravity, wrap(b"2005-05-26-10458.68"))

        assert output == "37.857713 -122.544543\n"
        assert result is None

    def test_a_str_datedow_raises(self, antigravity: ModuleType) -> None:
        with pytest.raises(TypeError):
            geohash_output(antigravity, "2005-05-26-10458.68")

    def test_it_hashes_datedow_itself_once(
        self, antigravity: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        datedow = b"2005-05-26-10458.68"
        seen: list[object] = []
        original = hashlib.md5

        def counting(data: Any, *args: Any, **kwargs: Any) -> Any:
            seen.append(data)
            return original(data, *args, **kwargs)

        monkeypatch.setattr(antigravity.hashlib, "md5", counting)

        geohash_output(antigravity, datedow)

        assert len(seen) == 1
        assert seen[0] is datedow

    def test_the_peak_does_not_follow_datedow(self, antigravity: ModuleType) -> None:
        datedow = b"x" * 10_000_000
        geohash_output(antigravity, datedow)  # warm

        peak = peak_bytes(lambda: geohash_output(antigravity, datedow))

        assert peak < 10_000, f"a 10 MB datedow peaked at {peak} bytes"

    @pytest.mark.timing
    def test_time_follows_datedow(self, antigravity: ModuleType) -> None:
        durations = []
        for size in (100_000, 1_000_000, 10_000_000):
            datedow = b"x" * size
            geohash_output(antigravity, datedow)
            durations.append(best_ns(lambda d=datedow: geohash_output(antigravity, d)))

        ratios = [later / earlier for earlier, later in pairwise(durations)]

        assert all(4 < ratio < 30 for ratio in ratios), (
            f"10x steps in datedow cost {durations} ns, ratios {ratios}; "
            "a constant gives about 1x and a quadratic about 100x"
        )


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


class TestDocumentedExamples:
    """Each block runs in its own fresh interpreter, so each one's first import
    is a real first import, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_python(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "-122.544543" in s)
        mutated = source.replace("-122.544543", "-122.544544", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert run_python(mutated, tmp_path).returncode != 0
