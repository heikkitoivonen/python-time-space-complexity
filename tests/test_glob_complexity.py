"""Tests to verify documented behaviour of the glob module.

docs/stdlib/glob.md turns on one claim: the cost is the entries examined, not
the matches returned. Flat-directory and recursive memory are measured separately.

* `glob()` is O(E) in time, and the match count belongs only to the space row.
  A directory of 1,000 entries holding one `.py` costs 477-508 us; the same one
  match among 20,000 entries costs 9.4-11.2 ms. Twenty times the entries, one
  match either way, twenty times the time.
* A single-directory `iglob()` uses O(e) space. Building the iterator
  peaks at about 1.5 KB, but its *first* step peaks at 1.2-1.3 MB over 20,000
  entries: each directory is read whole into a list of names before any of its
  matches are yielded. The peak rises x17.1 on 3.10 and x19.2 on 3.14 for 20x
  the entries.

* Recursive `**/*.py` walks at depths 5 and 80 have maximum directory width
  21 and exactly one match. Both APIs peak around 11-12 KB and 140 KB on
  Python 3.10 and 3.14. Setup and pattern-cache warm-up are outside the
  measurement. Directory components keep their lengths, but full path lengths
  necessarily grow with depth, so this does not establish a growth exponent.
* Weak references to the lists returned by `_listdir` observe exactly the
  active path staying live at a deep match - eight ancestor listings out of
  thirty-three made - so retention follows the descent rather than the tree.
  This distinguishes retained listings from path-string allocation alone.

The recursive storage explanation follows `_rlistdir` in released CPython
3.10 through 3.14: suspended loops retain `names` and partial paths while
recursing. The O(e) and O(e + m) rows are scoped to one directory; no recursive
byte bound is inferred from counting directory entries as fixed-size objects.
https://github.com/python/cpython/blob/3.10/Lib/glob.py
https://github.com/python/cpython/blob/3.14/Lib/glob.py

The rest is observation. Hidden names are excluded from `*` unless
`include_hidden=True` (3.11+) or the dot is written into the pattern; `escape()`
wraps metacharacters in character classes; `glob0()` never matches a pattern
while `glob1()` lists a directory; a `**` walk descends through directory
symlinks, so one file can be reported under two paths.

`glob0()` and `glob1()` are deprecated from 3.13; the tests assert that they
warn there and stay silent before it, so the page's version note cannot drift
from the interpreter.
https://github.com/python/cpython/blob/3.13/Lib/glob.py

What `iterator.close()` releases differs by version: 3.10, 3.11, 3.13 and
3.14 drop the ancestor listings, while 3.12.3 keeps all eight even after a
`gc.collect()`. The claim above does not rest on it, so the tests assert
release during the walk instead of after it.

Not settled here:

* What a symlink loop costs. That it follows links is asserted; letting a walk
  loop is not something to leave in a test suite.
* `dir_fd`, and `root_dir` beyond one round trip.
* `glob.translate()` on 3.10 through 3.12, where it does not exist. Its row is
  version-marked and the coverage check allows it to be absent.

Axes not varied: case sensitivity (the tests run on a case-sensitive
filesystem), non-ASCII names, and bytes patterns through `magic_check_bytes`.
"""

import glob
import inspect
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
import weakref
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "glob.md"

EXPECTED_BLOCKS = 11

# Documented, but absent before 3.13. Its row must carry the version.
ADDED_IN_313 = {"translate"}


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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


def populate(folder: pathlib.Path, entries: int, match: str = "only.py") -> pathlib.Path:
    """A directory of `entries` non-matching files plus one that matches."""
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(entries):
        (folder / f"f{index}.dat").touch()
    (folder / match).touch()
    return folder


def _public_names() -> set[str]:
    return {
        name
        for name in dir(glob)
        if not name.startswith("_") and not inspect.ismodule(getattr(glob, name))
    }


def _documented_names() -> set[str]:
    """Every `glob.<name>` the Complexity Reference table mentions."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n!!! warning", start)
    return set(re.findall(r"glob\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `glob`, including the
    two undocumented survivors and the two compiled patterns."""

    def test_no_public_name_is_missing_from_the_table(self) -> None:
        missing = sorted(_public_names() - _documented_names())

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - _public_names() - ADDED_IN_313)

        assert not unknown, f"the table names attributes glob does not have: {unknown}"

    def test_translate_carries_its_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        owning = [row for row in rows if "glob.translate" in row]
        assert len(owning) == 1, f"expected one row naming translate, found {len(owning)}"
        assert "3.13" in owning[0], f"the translate row should say 3.13+: {owning[0]}"

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        public = _public_names()

        assert 7 <= len(public) <= 10, (
            f"glob has {len(public)} public names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"glob", "iglob", "escape", "has_magic"} <= documented
        thinned = documented - {"glob1"}
        assert _public_names() - thinned == {"glob1"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestCostFollowsEntriesNotMatches:
    """Single-directory `glob()` | O(E) | O(e + m).

    Both directories below hold exactly one match, so anything that scaled with
    the result would be flat here.
    """

    def test_the_match_count_is_the_same_in_both(self, tmp_path: pathlib.Path) -> None:
        small = populate(tmp_path / "small", 200)
        large = populate(tmp_path / "large", 4_000)

        assert len(glob.glob(str(small / "*.py"))) == 1
        assert len(glob.glob(str(large / "*.py"))) == 1

    @pytest.mark.timing
    def test_twenty_times_the_entries_costs_far_more_for_the_same_one_match(
        self, tmp_path: pathlib.Path
    ) -> None:
        small = populate(tmp_path / "small", 1_000)
        large = populate(tmp_path / "large", 20_000)

        small_ns = best_ns(lambda: glob.glob(str(small / "*.py")))
        large_ns = best_ns(lambda: glob.glob(str(large / "*.py")))

        ratio = large_ns / small_ns
        assert ratio > 5, (
            f"20x the entries at one match cost x{ratio:.2f} "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); a cost in matches would give x1"
        )

    def test_the_result_list_is_what_the_matches_pay_for(self, tmp_path: pathlib.Path) -> None:
        folder = tmp_path / "many"
        folder.mkdir()
        for index in range(2_000):
            (folder / f"m{index}.py").touch()

        listed = peak_bytes(lambda: glob.glob(str(folder / "*.py")))
        counted = peak_bytes(lambda: sum(1 for _ in glob.iglob(str(folder / "*.py"))))

        assert listed > counted, f"glob peaked at {listed}, iglob at {counted}"


class TestIglobIsLazyPerDirectoryNotPerEntry:
    """Single-directory `iglob()` | O(1) to build, O(E) to exhaust | O(e).

    A generator is not O(1) memory when its first step reads a whole
    directory.
    """

    def test_building_the_iterator_touches_nothing(self, tmp_path: pathlib.Path) -> None:
        folder = populate(tmp_path / "flat", 5_000)

        peak = peak_bytes(lambda: glob.iglob(str(folder / "*.py")))

        assert peak < 20_000, f"iglob() allocated {peak} bytes before its first step"

    def test_the_first_step_reads_the_whole_directory(self, tmp_path: pathlib.Path) -> None:
        folder = populate(tmp_path / "flat", 5_000)
        iterator = glob.iglob(str(folder / "*.py"))

        build_peak = peak_bytes(lambda: glob.iglob(str(folder / "*.py")))
        step_peak = peak_bytes(lambda: next(iterator))

        assert step_peak > build_peak * 10, (
            f"the first step peaked at {step_peak} against {build_peak} to build; "
            "the row says the directory is listed whole"
        )

    def test_that_peak_scales_with_the_directory(self, tmp_path: pathlib.Path) -> None:
        small = populate(tmp_path / "small", 1_000)
        large = populate(tmp_path / "large", 20_000)
        small_iter = glob.iglob(str(small / "*.py"))
        large_iter = glob.iglob(str(large / "*.py"))

        small_peak = peak_bytes(lambda: next(small_iter))
        large_peak = peak_bytes(lambda: next(large_iter))

        ratio = large_peak / small_peak
        assert ratio > 5, (
            f"20x the entries moved the first step's peak by x{ratio:.2f} "
            f"({small_peak} to {large_peak} bytes); O(1) memory would give x1"
        )

    def test_glob_is_list_of_iglob(self, tmp_path: pathlib.Path) -> None:
        folder = populate(tmp_path / "flat", 20)

        pattern = str(folder / "*")
        assert sorted(glob.glob(pattern)) == sorted(glob.iglob(pattern))


class TestHiddenNames:
    """`*`, `?` and `**` skip a leading dot unless told otherwise."""

    @pytest.fixture
    def folder(self, tmp_path: pathlib.Path) -> pathlib.Path:
        (tmp_path / "visible.py").touch()
        (tmp_path / ".hidden.py").touch()
        return tmp_path

    def test_a_star_does_not_reach_them(self, folder: pathlib.Path) -> None:
        found = glob.glob(str(folder / "*.py"))

        assert [os.path.basename(path) for path in found] == ["visible.py"]

    def test_an_explicit_dot_does(self, folder: pathlib.Path) -> None:
        found = glob.glob(str(folder / ".*.py"))

        assert [os.path.basename(path) for path in found] == [".hidden.py"]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="include_hidden is 3.11+")
    def test_include_hidden_turns_the_rule_off(self, folder: pathlib.Path) -> None:
        found = glob.glob(str(folder / "*.py"), include_hidden=True)

        assert sorted(os.path.basename(path) for path in found) == [".hidden.py", "visible.py"]


class TestRecursiveWalks:
    """`**` with `recursive=True` lists every directory below the anchor."""

    @pytest.fixture
    def tree(self, tmp_path: pathlib.Path) -> pathlib.Path:
        nested = tmp_path / "src" / "pkg"
        nested.mkdir(parents=True)
        (tmp_path / "top.py").touch()
        (nested / "deep.py").touch()
        return tmp_path

    def test_it_reaches_every_level(self, tree: pathlib.Path) -> None:
        found = glob.glob(str(tree / "**" / "*.py"), recursive=True)

        assert sorted(os.path.basename(path) for path in found) == ["deep.py", "top.py"]

    def test_without_the_flag_it_is_one_level(self, tree: pathlib.Path) -> None:
        assert glob.glob(str(tree / "**" / "*.py")) == []

    def test_it_descends_through_a_directory_symlink(self, tree: pathlib.Path) -> None:
        """Which is why the page warns about links pointing back up a tree."""
        try:
            (tree / "link").symlink_to(tree / "src", target_is_directory=True)
        except OSError:
            pytest.skip("this filesystem does not allow symlinks")

        found = glob.glob(str(tree / "**" / "deep.py"), recursive=True)

        assert len(found) == 2, f"expected the file under both paths, got {found}"

    @staticmethod
    def fixed_width_chain(root: pathlib.Path, depth: int) -> list[pathlib.Path]:
        """Twenty empty side directories and one child at every ancestor."""
        root.mkdir()
        current = root
        ancestors = []
        for _ in range(depth):
            ancestors.append(current)
            for index in range(20):
                (current / f"s{index:02}").mkdir()
            current = current / "d"
            current.mkdir()
        (current / "only.py").touch()
        return ancestors

    @pytest.mark.parametrize("api", ["glob", "iglob"])
    def test_recursive_space_grows_with_depth_at_fixed_width_and_match_count(
        self, tmp_path: pathlib.Path, api: str
    ) -> None:
        peaks = []
        for depth in (5, 80):
            root = tmp_path / f"depth{depth}"
            ancestors = self.fixed_width_chain(root, depth)
            assert len(ancestors) == depth
            assert {len(list(folder.iterdir())) for folder in ancestors} == {21}
            pattern = str(root / "**" / "*.py")
            assert glob.glob(pattern, recursive=True) == [str(ancestors[-1] / "d" / "only.py")]

            def exhaust(pattern: str = pattern) -> int:
                if api == "glob":
                    return len(glob.glob(pattern, recursive=True))
                return sum(1 for _ in glob.iglob(pattern, recursive=True))

            peaks.append(peak_bytes(exhaust))
            assert exhaust() == 1

        assert peaks[1] > peaks[0] * 4, (
            f"{api}: depth 5 -> 80 at width 21 and one match peaked at {peaks}; "
            "a largest-directory-only bound would stay flat"
        )

    def test_ancestor_listings_stay_live_until_descent_finishes(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "tree"
        ancestors = self.fixed_width_chain(root, 8)

        class Names(list[str]):
            """A directory listing that supports weak references."""

        listings: list[tuple[str, weakref.ReferenceType[Names]]] = []
        original = glob._listdir  # type: ignore[attr-defined]

        def tracked_listdir(dirname: str, *args: Any, **kwargs: Any) -> list[str]:
            names = Names(original(dirname, *args, **kwargs))
            listings.append((dirname, weakref.ref(names)))
            return names

        monkeypatch.setattr(glob, "_listdir", tracked_listdir)
        iterator: Any = glob.iglob(str(root / "**" / "*.py"), recursive=True)
        try:
            assert next(iterator) == str(ancestors[-1] / "d" / "only.py")
            live_sizes = {
                path: len(reference() or [])
                for path, reference in listings
                if reference() is not None
            }
            assert {str(path): 21 for path in ancestors}.items() <= live_sizes.items()

            # Exactly the active path is retained, and no more: each level's
            # twenty side directories were listed and released on the way down.
            # That is the release evidence, so the control does not depend on
            # what closing the iterator frees - which varies by version.
            assert set(live_sizes) == {str(path) for path in ancestors}
            assert len(listings) > 4 * len(live_sizes), (
                f"{len(listings)} listings made, {len(live_sizes)} still live at the match"
            )
        finally:
            iterator.close()

        assert listings, "the listing probe must observe the recursive walk"

    @pytest.mark.timing
    def test_a_deeper_tree_costs_its_entries(self, tmp_path: pathlib.Path) -> None:
        shallow = tmp_path / "shallow"
        deep = tmp_path / "deep"
        populate(shallow, 500)
        for level in range(10):
            populate(deep / ("sub/" * level or "."), 500)

        shallow_ns = best_ns(lambda: glob.glob(str(shallow / "**" / "*.py"), recursive=True))
        deep_ns = best_ns(lambda: glob.glob(str(deep / "**" / "*.py"), recursive=True))

        ratio = deep_ns / shallow_ns
        assert ratio > 3, (
            f"ten times the entries across a tree cost x{ratio:.2f} "
            f"({shallow_ns:.0f}ns to {deep_ns:.0f}ns)"
        )


class TestEscapingAndMagic:
    """`escape()` | O(n) | O(n) and `has_magic()` | O(n) | O(1)."""

    def test_the_documented_escape(self) -> None:
        assert glob.escape("test[1].txt") == "test[[]1].txt"

    def test_every_metacharacter_is_wrapped(self) -> None:
        escaped = glob.escape("a*b?c[d]")

        assert escaped == "a[*]b[?]c[[]d]"
        assert glob.has_magic(escaped) is True  # the classes are themselves magic

    def test_has_magic_finds_the_three_that_matter(self) -> None:
        assert glob.has_magic("a*b") is True
        assert glob.has_magic("a?b") is True
        assert glob.has_magic("a[bc]d") is True
        assert glob.has_magic("plain.txt") is False

    def test_escaping_is_what_makes_a_literal_name_findable(self, tmp_path: pathlib.Path) -> None:
        awkward = tmp_path / "data[backup].csv"
        awkward.touch()

        assert glob.glob(str(awkward)) == []
        assert glob.glob(glob.escape(str(awkward))) == [str(awkward)]

    def test_the_compiled_patterns_are_what_both_use(self) -> None:
        magic_check = glob.magic_check  # type: ignore[attr-defined]
        magic_check_bytes = glob.magic_check_bytes  # type: ignore[attr-defined]

        assert magic_check.search("a*b") is not None
        assert magic_check.search("plain") is None
        assert magic_check_bytes.search(b"a*b") is not None


class TestTheDeprecatedPair:
    """`glob0` never matches a pattern; `glob1` lists one directory.

    Both are deprecated from 3.13, which is the one thing about them a reader
    needs, so the deprecation is asserted rather than just silenced.
    """

    @pytest.fixture(autouse=True)
    def _allow_the_deprecation(self) -> Iterator[None]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            yield

    def test_glob0_checks_one_literal_name(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a.py").touch()

        assert glob.glob0(str(tmp_path), "a.py") == ["a.py"]
        assert glob.glob0(str(tmp_path), "*.py") == []
        assert glob.glob0(str(tmp_path), "missing.py") == []

    def test_glob1_lists_and_filters(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a.py").touch()
        (tmp_path / "b.dat").touch()

        assert glob.glob1(str(tmp_path), "*.py") == ["a.py"]
        assert sorted(glob.glob1(str(tmp_path), "*")) == ["a.py", "b.dat"]

    def test_glob1_keeps_the_hidden_rule(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".dot.py").touch()

        assert glob.glob1(str(tmp_path), "*.py") == []

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="deprecated from 3.13")
    def test_they_warn_from_313(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a.py").touch()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            glob.glob0(str(tmp_path), "a.py")
            glob.glob1(str(tmp_path), "*.py")

        messages = [str(entry.message) for entry in caught]
        assert len(messages) == 2, f"expected both to warn, got {messages}"
        assert all(issubclass(entry.category, DeprecationWarning) for entry in caught)
        assert all("deprecated" in message for message in messages)

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="silent before 3.13")
    def test_they_are_silent_before_313(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "a.py").touch()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            glob.glob0(str(tmp_path), "a.py")
            glob.glob1(str(tmp_path), "*.py")

        assert [entry for entry in caught if issubclass(entry.category, DeprecationWarning)] == []


@pytest.mark.skipif(not hasattr(glob, "translate"), reason="translate is 3.13+")
class TestTranslate:
    """`translate(pat)` | O(n) | O(n): the pattern as a regular expression."""

    def test_the_result_matches_what_glob_would(self) -> None:
        pattern = glob.translate("*.py")  # type: ignore[attr-defined]

        assert re.match(pattern, "script.py")
        assert re.match(pattern, "notes.txt") is None

    def test_the_leading_dot_rule_is_baked_in(self) -> None:
        strict = glob.translate("*.py")  # type: ignore[attr-defined]
        loose = glob.translate("*.py", include_hidden=True)  # type: ignore[attr-defined]

        assert re.match(strict, ".hidden.py") is None
        assert re.match(loose, ".hidden.py")


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, each in its own temporary working directory so a
    pattern cannot pick up another block's files."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import glob\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
