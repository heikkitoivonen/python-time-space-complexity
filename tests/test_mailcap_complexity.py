"""Tests for docs/stdlib/mailcap.md.

The page prices `getcaps()` by the characters it parses and `findmatch()` by
the entries for one MIME type and its wildcard, with every `test` command a
shell process on top. Those are settled mostly by observation: a recording
`open()` shows which files `getcaps()` reads on each call, counting dictionary
subclasses show how many lookups and membership checks `findmatch()` makes,
a counting sort key shows how many comparisons its sort makes, and a recording
`os.system()` shows which `test` commands it runs. One timing test covers the
growth of `getcaps()` and one traced peak the space of `findmatch()`. The
module exists on Python 3.10, 3.11 and 3.12 only, so every test that touches
it takes the `mailcap` fixture, which skips from 3.13; run them with one of
those interpreters. Lib/mailcap.py differs between v3.10.19, v3.11.14 and
v3.12.12 only in the import-time DeprecationWarning added in 3.11 and in how
the read loop is spelled: no bound moves.

Measurement scope:

* `getcaps()` opens every path in `MAILCAPS` on every call, in order,
  skipping one that cannot be opened, and returns a new dictionary of new
  entry lists each time. Without `MAILCAPS` it opens `$HOME/.mailcap`,
  `/etc/mailcap`, `/usr/etc/mailcap` and `/usr/local/etc/mailcap`. Keys are
  lowercased and a type in two files gets the first file's entries, then the
  second's.
* `getcaps()` over files of 1,000, 10,000 and 100,000 one-line entries:
  each 10x step costs between 4x and 30x, which a quadratic parse would
  exceed tenfold, and the result holds one entry per line.
* `findmatch()` against a `caps` dictionary of 1 or 100,000 types makes
  the same two membership checks on it, for the exact type and its
  wildcard. Over e = 1,000 entries, each entry is asked once whether it has
  `key`. The sort over 10,000 entries that `getcaps()` built, split between
  the exact type and its wildcard, makes fewer than 2e comparisons; the same
  entries shuffled make more than e·log2(e)/2, which is the control showing
  the counter sees the sort. A traced peak over 100,000 entries none of which
  has `key` is more than 20x the peak over 1,000.
* With `os.system()` recorded: entries without a `test`, or with an empty
  one, run nothing and are taken; three
  tested entries whose tests return 1, 1 and 0 run all three in file order
  and the third is returned, and a fourth tested entry after it is not run;
  an entry without `key` is not tested; an unsafe filename runs nothing and
  returns `(None, None)` with `UnsafeMailcapInput`. A space, `;`, backslash,
  U+00A0, `$(` and `~` in a filename are each refused, and word characters,
  `@+=:,./-`, U+00A1 and `é` are accepted. `%s` in a `test` field raises
  `TypeError`, and `%t` there becomes the filename.
* `findmatch()` returns the `caps` entry object itself, with the command
  filled in; the wildcard entry wins when it comes first in the file; a
  differently-cased MIME type matches nothing. An unsafe MIME type under
  `%t`, or an unsafe parameter under `%{name}`, skips that entry with
  `UnsafeMailcapInput` and the next one is used. `UnsafeMailcapInput` is a
  `Warning` subclass.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess on 3.10 to 3.12, and a
  mutated assertion in one of them is asserted to fail. One block runs two
  real shell commands, `exit 1` and `exit 0`.

Not settled here:

* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594. The unsafe-input checks arrived in 3.10.8 and
  3.11.0 (`git tag --contains` on the change in CPython); only the newest
  3.10 patch is run.
* What a shell process costs is the operating system's and is not measured.
* The page's bounds assume a handful of files, short entries, a short
  filename and a short `plist`. `subst()` walks the field character by
  character, and each `%{name}` scans `plist`, so a long parameter list adds
  a term per substituted entry. A
  backslash-continued entry is rejoined by slicing once per continuation
  line, which is quadratic in that entry's continuation lines, and a type
  repeated across many `MAILCAPS` files has its list copied once per file;
  neither shape is measured. Entry and line length are held fixed.
* The timing window for `getcaps()` excludes quadratic growth but admits
  n log n, and the `findmatch()` peak is a lower bound on growth only; the
  linear upper bounds are read from Lib/mailcap.py.
* The sort is O(e) only for the two already-ordered runs `getcaps()`
  produces; an arbitrary `caps` mapping can cost O(e log e).
* `listmailcapfiles()`, `readmailcapfile()`, `lookup()`, `subst()`,
  `findparam()`, `lineno_sort_key()`, `parseline()`, `parsefield()`, `show()`
  and `test()` are not in `__all__` or the official API inventory, and are
  not priced. `UnsafeMailcapInput` is not in the inventory either; the page
  prices it because `findmatch()` issues it.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import math
import os
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "mailcap.md"
EXPECTED_BLOCKS = 4


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, with the collector held off."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("mailcap") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def mailcap() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: mailcap was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("mailcap")


@pytest.fixture
def system_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record os.system() commands; `exit N` returns N and anything else 0."""
    calls: list[str] = []

    def fake_system(command: str) -> int:
        calls.append(command)
        match = re.fullmatch(r"exit (\d+)", command)
        return int(match.group(1)) if match else 0

    monkeypatch.setattr(os, "system", fake_system)
    return calls


def write_caps(path: pathlib.Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


class TestAvailability:
    """`import mailcap` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("mailcap")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="mailcap was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import mailcap"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "mailcap" in result.stderr


class TestGetcapsRereadsEveryFile:
    """`mailcap.getcaps()` | O(L) | O(L): reads the files named by `MAILCAPS`
    or the four default paths, skipping any that cannot be opened, and
    returns a new dictionary on every call. A cached result would open
    nothing the second time and return the same object."""

    def test_every_call_opens_every_listed_file(
        self, mailcap: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        first = write_caps(tmp_path / "first", "text/plain; cat %s\n")
        second = write_caps(tmp_path / "second", "image/*; display %s\n")
        missing = str(tmp_path / "missing")
        monkeypatch.setenv("MAILCAPS", os.pathsep.join([first, missing, second]))
        opened: list[str] = []

        def recording_open(path: str, *args: Any, **kwargs: Any) -> Any:
            opened.append(path)
            return open(path, *args, **kwargs)

        monkeypatch.setattr(mailcap, "open", recording_open, raising=False)
        caps = mailcap.getcaps()
        again = mailcap.getcaps()

        assert opened == [first, missing, second] * 2
        assert again == caps
        assert again is not caps
        assert again["text/plain"] is not caps["text/plain"]

    def test_without_mailcaps_it_tries_the_four_default_paths(
        self, mailcap: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        monkeypatch.delenv("MAILCAPS", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        opened: list[str] = []

        def refusing_open(path: str, *args: Any, **kwargs: Any) -> Any:
            opened.append(path)
            raise OSError(path)

        monkeypatch.setattr(mailcap, "open", refusing_open, raising=False)

        assert mailcap.getcaps() == {}
        assert opened == [
            str(tmp_path) + "/.mailcap",
            "/etc/mailcap",
            "/usr/etc/mailcap",
            "/usr/local/etc/mailcap",
        ]

    def test_keys_are_lowercased_and_later_files_append(
        self, mailcap: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        first = write_caps(tmp_path / "first", "text/plain; cat %s; copiousoutput\n")
        second = write_caps(tmp_path / "second", "Text/Plain; less %s\n")
        monkeypatch.setenv("MAILCAPS", os.pathsep.join([first, second]))

        caps = mailcap.getcaps()

        assert list(caps) == ["text/plain"]
        assert [e["view"] for e in caps["text/plain"]] == ["cat %s", "less %s"]
        assert caps["text/plain"][0]["copiousoutput"] == ""

    @pytest.mark.timing
    def test_cost_grows_linearly_with_the_file(
        self, mailcap: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        times: list[float] = []
        for lines in (1_000, 10_000, 100_000):
            path = tmp_path / f"caps{lines}"
            body = "".join(f"type{i}/sub; viewer %s; copiousoutput\n" for i in range(lines))
            monkeypatch.setenv("MAILCAPS", write_caps(path, body))
            assert len(mailcap.getcaps()) == lines
            times.append(best_ns(mailcap.getcaps, repeats=3))

        ratios = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(4 < ratio < 30 for ratio in ratios), (
            f"10x the file cost {ratios}; linear is 10x, quadratic 100x"
        )


class CountingCaps(dict[str, Any]):
    """A caps mapping that counts membership checks."""

    checks = 0

    def __contains__(self, key: object) -> bool:
        self.checks += 1
        return super().__contains__(key)


class CountingEntry(dict[str, Any]):
    """An entry that counts membership checks."""

    checks = 0

    def __contains__(self, key: object) -> bool:
        self.checks += 1
        return super().__contains__(key)


class CountingKey:
    """A sort key that counts the comparisons made on it."""

    compared = 0

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: CountingKey) -> bool:
        CountingKey.compared += 1
        return self.value < other.value


class TestFindmatchWalksOneTypesEntries:
    """`mailcap.findmatch(...)` | O(e) plus one shell process per `test` run
    | O(e): two lookups in `caps` whatever its size, one check per entry for
    the type and its wildcard, and a sort that is linear on the ordered runs
    `getcaps()` builds."""

    def test_caps_size_does_not_change_the_lookups(self, mailcap: Any) -> None:
        counts: list[int] = []
        for others in (0, 100_000):
            caps = CountingCaps({f"other{i}/x": [] for i in range(others)})
            caps["text/plain"] = [{"view": "cat %s", "lineno": 0}]
            assert mailcap.findmatch(caps, "text/plain", filename="a")[0] == "cat a"
            counts.append(caps.checks)

        assert counts == [2, 2]

    def test_each_entry_is_checked_for_the_key_once(self, mailcap: Any) -> None:
        entries = [CountingEntry(edit="vi %s", lineno=i) for i in range(1_000)]
        caps = {"text/plain": entries}

        assert mailcap.findmatch(caps, "text/plain", key="view") == (None, None)
        assert [e.checks for e in entries] == [1] * 1_000

    def test_the_sort_is_linear_on_getcaps_order(
        self, mailcap: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        e = 10_000
        body = "".join(
            ("image/*" if i % 2 else "image/png") + "; v %s; edit=x %s\n" for i in range(e)
        )
        monkeypatch.setenv("MAILCAPS", write_caps(tmp_path / "caps", body))
        caps = mailcap.getcaps()
        original = mailcap.lineno_sort_key
        monkeypatch.setattr(mailcap, "lineno_sort_key", lambda entry: CountingKey(original(entry)))

        CountingKey.compared = 0
        command, entry = mailcap.findmatch(caps, "image/png", key="edit")
        assert (command, entry) == ("x /dev/null", caps["image/png"][0])
        ordered = CountingKey.compared

        rng = random.Random(0)
        for entries in caps.values():
            rng.shuffle(entries)
        CountingKey.compared = 0
        mailcap.findmatch(caps, "image/png", key="edit")
        shuffled = CountingKey.compared

        assert ordered < 2 * e, f"{ordered} comparisons for {e} ordered entries"
        assert shuffled > e * math.log2(e) / 2, f"{shuffled} comparisons for {e} shuffled entries"

    def test_the_peak_follows_the_entries(self, mailcap: Any) -> None:
        peaks: list[int] = []
        for e in (1_000, 100_000):
            caps = {"text/plain": [{"edit": "vi %s", "lineno": i} for i in range(e)]}
            mailcap.findmatch(caps, "text/plain")
            peaks.append(peak_bytes(partial(mailcap.findmatch, caps, "text/plain")))

        assert peaks[1] > 20 * peaks[0], f"peaks {peaks} for 1,000 and 100,000 entries"


class TestFindmatchResult:
    """Returns `(command, entry)` or `(None, None)`; the first entry in file
    order with `key` wins, and `MIMEtype` is matched as given."""

    def test_it_returns_the_entry_itself(self, mailcap: Any) -> None:
        entry = {"view": "cat %s", "copiousoutput": "", "lineno": 0}
        command, found = mailcap.findmatch({"text/plain": [entry]}, "text/plain", filename="a")

        assert command == "cat a"
        assert found is entry

    def test_file_order_decides_between_exact_and_wildcard(self, mailcap: Any) -> None:
        wildcard = {"view": "display %s", "lineno": 0}
        exact = {"view": "pngview %s", "lineno": 1}
        caps = {"image/*": [wildcard], "image/png": [exact]}

        assert mailcap.findmatch(caps, "image/png", filename="a.png") == ("display a.png", wildcard)
        wildcard["lineno"] = 2
        assert mailcap.findmatch(caps, "image/png", filename="a.png") == ("pngview a.png", exact)

    def test_the_mime_type_is_not_lowercased(self, mailcap: Any) -> None:
        caps = {"text/plain": [{"view": "cat %s", "lineno": 0}]}

        assert mailcap.findmatch(caps, "Text/Plain") == (None, None)
        assert mailcap.findmatch(caps, "text/plain")[0] == "cat /dev/null"


class TestTestCommandsRunAShell:
    """One `os.system()` call per `test` field reached, stopping at the first
    entry that passes; an unsafe filename runs nothing."""

    def test_untested_entries_run_nothing(self, mailcap: Any, system_calls: list[str]) -> None:
        caps = {"text/plain": [{"view": "cat %s", "lineno": i} for i in range(10)]}

        assert mailcap.findmatch(caps, "text/plain", filename="a")[0] == "cat a"
        assert system_calls == []

    def test_tests_run_in_order_until_one_passes(
        self, mailcap: Any, system_calls: list[str]
    ) -> None:
        caps = {
            "text/html": [
                {"view": "a %s", "test": "exit 1", "lineno": 0},
                {"edit": "b %s", "test": "exit 7", "lineno": 1},
                {"view": "c %s", "test": "exit 1", "lineno": 2},
                {"view": "d %s", "test": "exit 0", "lineno": 3},
                {"view": "e %s", "test": "exit 0", "lineno": 4},
            ]
        }

        command, entry = mailcap.findmatch(caps, "text/html", filename="i.html")

        assert command == "d i.html"
        assert entry["lineno"] == 3
        assert system_calls == ["exit 1", "exit 1", "exit 0"]

    def test_an_empty_test_passes_without_a_shell(
        self, mailcap: Any, system_calls: list[str]
    ) -> None:
        caps = {"text/plain": [{"view": "cat %s", "test": "", "lineno": 0}]}

        assert mailcap.findmatch(caps, "text/plain", filename="a")[0] == "cat a"
        assert system_calls == []

    def test_an_unsafe_filename_runs_nothing(self, mailcap: Any, system_calls: list[str]) -> None:
        caps = {"text/plain": [{"view": "cat %s", "test": "exit 0", "lineno": 0}]}

        with pytest.warns(mailcap.UnsafeMailcapInput):
            result = mailcap.findmatch(caps, "text/plain", filename="x; rm -rf ~")

        assert result == (None, None)
        assert system_calls == []

    def test_percent_s_in_a_test_field_raises(self, mailcap: Any, system_calls: list[str]) -> None:
        caps = {"text/plain": [{"view": "cat %s", "test": "test -f %s", "lineno": 0}]}

        with pytest.raises(TypeError):
            mailcap.findmatch(caps, "text/plain", filename="a.txt")
        assert system_calls == []

    def test_percent_t_in_a_test_field_is_the_filename(
        self, mailcap: Any, system_calls: list[str]
    ) -> None:
        caps = {"text/plain": [{"view": "cat %s", "test": "test -f %t", "lineno": 0}]}

        assert mailcap.findmatch(caps, "text/plain", filename="a.txt")[0] == "cat a.txt"
        assert system_calls == ["test -f a.txt"]


class TestUnsafeMailcapInput:
    """`mailcap.UnsafeMailcapInput` | O(1) | O(1): a `Warning` issued when a
    filename, a MIME type under `%t` or a parameter under `%{name}` is
    refused."""

    def test_it_is_a_warning(self, mailcap: Any) -> None:
        assert issubclass(mailcap.UnsafeMailcapInput, Warning)

    @pytest.mark.parametrize("filename", ["a b", "a;b", "a\\b", "a\xa0b", "$(id)", "~/a"])
    def test_these_filenames_are_refused(self, mailcap: Any, filename: str) -> None:
        caps = {"text/plain": [{"view": "cat %s", "lineno": 0}]}

        with pytest.warns(mailcap.UnsafeMailcapInput):
            assert mailcap.findmatch(caps, "text/plain", filename=filename) == (None, None)

    def test_word_characters_punctuation_and_high_characters_are_accepted(
        self, mailcap: Any
    ) -> None:
        caps = {"text/plain": [{"view": "cat %s", "lineno": 0}]}
        filename = "a_9@+=:,./-\xa1é"

        with warnings.catch_warnings():
            warnings.simplefilter("error", mailcap.UnsafeMailcapInput)
            assert mailcap.findmatch(caps, "text/plain", filename=filename)[0] == (
                "cat " + filename
            )

    def test_an_unsafe_mime_type_skips_the_entry(self, mailcap: Any) -> None:
        caps = {
            "x/y;z": [
                {"view": "show %t", "lineno": 0},
                {"view": "show %s", "lineno": 1},
            ]
        }

        with pytest.warns(mailcap.UnsafeMailcapInput):
            command, entry = mailcap.findmatch(caps, "x/y;z", filename="a")

        assert command == "show a"
        assert entry["lineno"] == 1

    def test_an_unsafe_parameter_skips_the_entry(self, mailcap: Any) -> None:
        caps = {
            "text/plain": [
                {"view": "show %{charset}", "lineno": 0},
                {"view": "show %s", "lineno": 1},
            ]
        }

        with pytest.warns(mailcap.UnsafeMailcapInput):
            command, _ = mailcap.findmatch(
                caps, "text/plain", filename="a", plist=["charset=$(id)"]
            )
        assert command == "show a"
        safe, _ = mailcap.findmatch(caps, "text/plain", plist=["Charset=utf-8"])
        assert safe == "show utf-8"


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so `MAILCAPS` cannot leak
    between them, and asserts its own result, on the versions that still have
    the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import mailcap" in source for _, source in blocks)

    def test_every_block_runs(self, mailcap: Any, tmp_path: pathlib.Path) -> None:
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

    def test_the_runner_notices_a_broken_assertion(
        self, mailcap: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "'display a.png'" in s)
        mutated = source.replace("'display a.png'", "'pngview a.png'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
