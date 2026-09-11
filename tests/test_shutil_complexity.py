"""Observe shutil allocation and traversal dimensions.

Tree tests vary width and depth independently and count retained ancestor entries.
Archive tests observe member indexes; buffer, PATH, and extended-attribute tests
measure peak allocation with input construction outside the measurement where appropriate.
Registry tests count comparisons and extension visits, and failure tests distinguish
copy aggregation from deletion callbacks. Every documentation example runs.

Filesystem syscall costs, custom callbacks, compression workspace, privileged chown,
and cross-mount move costs are source-backed exclusions, not measured bounds.
Symlink variants and non-POSIX filesystem behavior are not varied here.
"""

import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tarfile
import textwrap
import tracemalloc
import zipfile
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "shutil.md"

EXPECTED_BLOCKS = 9

# Public and documented, but deliberately outside `__all__`.
NOT_EXPORTED = {"COPY_BUFSIZE"}

# Dropped from `__all__` in 3.14, where it is also deprecated.
UNEXPORTED_IN_314 = {"ExecError"}


def copy_buffer_size() -> int:
    """`shutil.COPY_BUFSIZE`, which typeshed does not declare but every
    supported version has; it is what bounds a copy's space."""
    return shutil.COPY_BUFSIZE  # type: ignore[attr-defined]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def build_tree(base: pathlib.Path, depth: int, width: int) -> pathlib.Path:
    """A tree `depth` levels deep with `width` files at each level."""
    base.mkdir(parents=True, exist_ok=True)
    current = base
    for level in range(depth):
        current = current / f"l{level}"
        current.mkdir()
        for index in range(width):
            (current / f"f{index}").write_text("x")
    return base


def _documented_names() -> set[str]:
    """Every `shutil.<name>` the Complexity Reference tables mention."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("\n## Copying a File", start)
    return set(re.findall(r"shutil\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The tables have to name every entry in `shutil.__all__`."""

    def test_no_exported_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(set(shutil.__all__) - _documented_names())

        assert not missing, f"{len(missing)} exported names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        allowed = set(shutil.__all__) | NOT_EXPORTED | UNEXPORTED_IN_314

        unknown = sorted(_documented_names() - allowed)

        assert not unknown, f"the tables name attributes shutil does not have: {unknown}"

    def test_the_documented_constant_is_real_but_unexported(self) -> None:
        assert NOT_EXPORTED <= _documented_names()
        for name in NOT_EXPORTED:
            assert hasattr(shutil, name)
            assert name not in shutil.__all__

    def test_exec_error_carries_its_deprecation(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        owning = [row for row in rows if "shutil.ExecError" in row]
        assert len(owning) == 1, f"expected one row naming ExecError, found {len(owning)}"
        assert "3.14" in owning[0], f"the ExecError row should name the deprecation: {owning[0]}"

    def test_exec_error_matches_this_interpreter(self) -> None:
        assert ("ExecError" in shutil.__all__) is (sys.version_info < (3, 14))

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        assert 23 <= len(shutil.__all__) <= 29, (
            f"shutil exports {len(shutil.__all__)} names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"copy", "copytree", "rmtree", "move", "which"} <= documented
        thinned = documented - {"disk_usage"}
        assert set(shutil.__all__) - thinned == {"disk_usage"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestCopyingIsBoundedByTheBuffer:
    """The copy rows' O(1) space: flat in the file size, and equal to one
    `COPY_BUFSIZE` rather than to nothing."""

    def test_the_buffer_is_one_of_the_two_documented_sizes(self) -> None:
        expected = 256 * 1024 if sys.version_info >= (3, 14) else 64 * 1024
        if os.name == "nt":
            expected = 1024 * 1024

        assert copy_buffer_size() == expected

    def test_the_peak_does_not_move_with_the_file(self, tmp_path: pathlib.Path) -> None:
        small = tmp_path / "small.bin"
        large = tmp_path / "large.bin"
        small.write_bytes(b"x" * (1 << 20))
        large.write_bytes(b"x" * (16 << 20))
        target = tmp_path / "out.bin"
        shutil.copyfile(small, target)  # warm the import machinery

        small_peak = peak_bytes(lambda: shutil.copyfile(small, target))
        large_peak = peak_bytes(lambda: shutil.copyfile(large, target))

        assert large_peak < small_peak * 2, (
            f"16x the file moved the peak from {small_peak} to {large_peak} bytes"
        )
        assert large_peak < (16 << 20) // 4, "a 16 MiB copy should not hold the file"

    def test_copyfileobj_streams_through_one_buffer(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "payload.bin"
        source.write_bytes(b"x" * (16 << 20))

        def copy_through() -> None:
            with open(source, "rb") as reader, open(os.devnull, "wb") as writer:
                shutil.copyfileobj(reader, writer)

        copy_through()
        peak = peak_bytes(copy_through)

        assert peak < (16 << 20) // 4, f"copyfileobj peaked at {peak} bytes for a 16 MiB file"


class TestWhatEachCopyCarries:
    """`copyfile` moves bytes, `copy` adds the mode, `copy2` adds the times."""

    @pytest.fixture
    def source(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "source.txt"
        path.write_text("contents")
        path.chmod(0o640)
        return path

    def test_copyfile_moves_only_the_bytes(
        self, source: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        target = tmp_path / "plain.txt"

        shutil.copyfile(source, target)

        assert target.read_text() == "contents"

    def test_copy_adds_the_mode(self, source: pathlib.Path, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "with_mode.txt"

        shutil.copy(source, target)

        assert target.stat().st_mode == source.stat().st_mode

    def test_copy2_adds_the_times(self, source: pathlib.Path, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "with_stat.txt"

        shutil.copy2(source, target)

        assert target.stat().st_mtime == source.stat().st_mtime

    def test_copymode_and_copystat_on_their_own(
        self, source: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        target = tmp_path / "bare.txt"
        target.write_text("other")
        target.chmod(0o600)

        shutil.copymode(source, target)
        assert target.stat().st_mode == source.stat().st_mode

        shutil.copystat(source, target)
        assert target.stat().st_mtime == source.stat().st_mtime
        assert target.read_text() == "other", "copystat must not touch the contents"

    def test_copying_a_file_onto_itself_is_refused(self, source: pathlib.Path) -> None:
        with pytest.raises(shutil.SameFileError):
            shutil.copyfile(source, source)


class TestTreeStorage:
    """Count live ancestor entries while varying width and depth independently."""

    @pytest.mark.parametrize("depth", [2, 20])
    @pytest.mark.parametrize("width", [2, 20])
    def test_copytree_retains_ancestor_listings(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, depth: int, width: int
    ) -> None:
        source = build_tree(tmp_path / "src", depth, width)
        original = shutil._copytree  # type: ignore[attr-defined]
        active: list[int] = []
        peak = 0

        def observe(entries: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal peak
            active.append(len(entries))
            peak = max(peak, sum(active))
            try:
                return original(entries, *args, **kwargs)
            finally:
                active.pop()

        monkeypatch.setattr(shutil, "_copytree", observe)
        shutil.copytree(source, tmp_path / "dst")
        assert peak == depth * (width + 1)
        assert not active

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="recursive rmtree before 3.12")
    @pytest.mark.parametrize("depth", [2, 20])
    @pytest.mark.parametrize("width", [2, 20])
    def test_recursive_rmtree_retains_ancestor_listings(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, depth: int, width: int
    ) -> None:
        source = build_tree(tmp_path / "src", depth, width)
        original = os.unlink
        peak = 0

        def observe(*args: Any, **kwargs: Any) -> None:
            nonlocal peak
            frame = sys._getframe(1)
            retained = 0
            while frame is not None:
                if frame.f_code.co_name in ("_rmtree_safe_fd", "_rmtree_unsafe"):
                    retained += len(frame.f_locals.get("entries", []))
                frame = frame.f_back
            peak = max(peak, retained)
            original(*args, **kwargs)

        monkeypatch.setattr(os, "unlink", observe)
        shutil.rmtree(source)
        assert peak == depth * (width + 1)
        assert not source.exists()

    @staticmethod
    def _bushy(base: pathlib.Path, siblings: int, width: int) -> pathlib.Path:
        """The same entries as a chain, reachable through a two-level path."""
        base.mkdir(parents=True)
        for index in range(siblings):
            branch = base / f"s{index:04}"
            branch.mkdir()
            for leaf in range(width):
                (branch / f"f{leaf:04}").touch()
        return base

    def test_equal_trees_of_different_shape_do_not_cost_the_same(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Why the row is O(d·e) and not the whole tree's metadata: two trees
        of identical entry count peak several-fold apart."""
        deep = build_tree(tmp_path / "deep", depth=50, width=40)
        bushy = self._bushy(tmp_path / "bushy", siblings=50, width=40)

        def entries(root: pathlib.Path) -> int:
            return sum(len(dirs) + len(files) for _, dirs, files in os.walk(root))

        assert abs(entries(deep) - entries(bushy)) <= 2, "the two shapes must hold equal entries"

        deep_peak = peak_bytes(lambda: shutil.copytree(deep, tmp_path / "cd"))
        bushy_peak = peak_bytes(lambda: shutil.copytree(bushy, tmp_path / "cb"))

        assert deep_peak > bushy_peak * 1.5, (
            f"equal entry counts peaked at {deep_peak} deep against {bushy_peak} bushy; "
            "a whole-tree bound would call these the same"
        )

    def test_rmtree_removes_everything(self, tmp_path: pathlib.Path) -> None:
        tree = build_tree(tmp_path / "doomed", depth=3, width=4)

        shutil.rmtree(tree)

        assert not tree.exists()

    def test_copytree_reproduces_the_tree(self, tmp_path: pathlib.Path) -> None:
        source = build_tree(tmp_path / "src", depth=2, width=3)

        shutil.copytree(source, tmp_path / "dst")

        original = sorted(str(p.relative_to(source)) for p in source.rglob("*"))
        copied = sorted(str(p.relative_to(tmp_path / "dst")) for p in (tmp_path / "dst").rglob("*"))
        assert original == copied


class TestIgnorePatterns:
    """`ignore_patterns()` | O(1) to build, O(patterns · e) per directory."""

    def test_it_returns_the_names_to_skip(self, tmp_path: pathlib.Path) -> None:
        ignore = shutil.ignore_patterns("*.pyc", "tmp*")

        skipped = ignore(str(tmp_path), ["a.pyc", "b.py", "tmpx", "c.txt"])

        assert sorted(skipped) == ["a.pyc", "tmpx"]

    def test_copytree_leaves_them_behind(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        for name in ("a.txt", "b.pyc", "tmp1"):
            (source / name).write_text("x")

        shutil.copytree(source, tmp_path / "dst", ignore=shutil.ignore_patterns("*.pyc", "tmp*"))

        assert os.listdir(tmp_path / "dst") == ["a.txt"]

    def test_no_patterns_skips_nothing(self, tmp_path: pathlib.Path) -> None:
        assert shutil.ignore_patterns()(str(tmp_path), ["a", "b"]) == set()


class TestMoveIsARenameWhenItCan:
    """`move()` | O(1) within one filesystem: the inode survives."""

    def test_a_file_keeps_its_inode(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "a.txt"
        source.write_text("contents")
        inode = source.stat().st_ino

        shutil.move(str(source), str(tmp_path / "b.txt"))

        assert (tmp_path / "b.txt").stat().st_ino == inode
        assert not source.exists()

    def test_a_directory_keeps_its_inode_too(self, tmp_path: pathlib.Path) -> None:
        source = build_tree(tmp_path / "src", depth=2, width=2)
        inode = source.stat().st_ino

        shutil.move(str(source), str(tmp_path / "moved"))

        assert (tmp_path / "moved").stat().st_ino == inode

    def test_moving_into_a_directory_keeps_the_basename(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "a.txt"
        source.write_text("x")
        destination = tmp_path / "into"
        destination.mkdir()

        shutil.move(str(source), str(destination))

        assert (destination / "a.txt").read_text() == "x"


class TestQuerying:
    """`disk_usage`, `which` and `get_terminal_size`: one syscall, a PATH walk,
    and one ioctl."""

    def test_disk_usage_returns_three_numbers(self) -> None:
        usage = shutil.disk_usage(".")

        assert usage.total > 0
        assert usage.used >= 0
        assert usage.free >= 0
        assert usage.used <= usage.total

    def test_which_finds_an_executable_by_absolute_path(self) -> None:
        found = shutil.which("python3")

        if found is not None:
            assert os.path.isabs(found)
            assert os.access(found, os.X_OK)

    def test_which_answers_none_for_a_missing_command(self) -> None:
        assert shutil.which("definitely-not-a-real-command-xyz") is None

    def test_an_explicit_path_replaces_the_environment(self) -> None:
        assert shutil.which("python3", path="") is None

    def test_which_caches_nothing(self, tmp_path: pathlib.Path) -> None:
        """Which is why the page says not to call it in a loop."""
        program = tmp_path / "demo"
        program.write_text("#!/bin/sh\n")
        program.chmod(0o755)

        assert shutil.which("demo", path=str(tmp_path)) == str(program)

        program.unlink()

        assert shutil.which("demo", path=str(tmp_path)) is None

    def test_get_terminal_size_answers_even_without_a_terminal(self) -> None:
        size = shutil.get_terminal_size()

        assert size.columns > 0
        assert size.lines > 0


class TestArchives:
    """`make_archive`/`unpack_archive` | O(n + E), and the two registries."""

    @pytest.fixture
    def payload(self, tmp_path: pathlib.Path) -> pathlib.Path:
        source = tmp_path / "payload"
        source.mkdir()
        (source / "a.txt").write_text("contents")
        (source / "nested").mkdir()
        (source / "nested" / "b.txt").write_text("more")
        return source

    def test_a_round_trip_through_tar(self, payload: pathlib.Path, tmp_path: pathlib.Path) -> None:
        archive = shutil.make_archive(str(tmp_path / "bundle"), "tar", str(payload))

        restored = tmp_path / "restored"
        shutil.unpack_archive(archive, str(restored))

        assert (restored / "a.txt").read_text() == "contents"
        assert (restored / "nested" / "b.txt").read_text() == "more"

    def test_the_format_lists_are_built_fresh(self) -> None:
        first = shutil.get_archive_formats()
        second = shutil.get_archive_formats()

        assert first == second
        assert first is not second
        assert {name for name, _ in first} >= {"tar", "zip", "gztar"}

    def test_unpack_formats_carry_their_extensions(self) -> None:
        formats = {name: extensions for name, extensions, _ in shutil.get_unpack_formats()}

        assert ".tar" in formats["tar"]
        assert ".zip" in formats["zip"]

    def test_registering_and_unregistering(self) -> None:
        def build(base_name: str, base_dir: str, **kwargs: Any) -> str:
            return base_name + ".demo"

        shutil.register_archive_format("demo", build, [], "A demonstration format")
        try:
            assert "demo" in [name for name, _ in shutil.get_archive_formats()]
        finally:
            shutil.unregister_archive_format("demo")

        assert "demo" not in [name for name, _ in shutil.get_archive_formats()]

    def test_the_unpack_registry_takes_the_same_treatment(self) -> None:
        def extract(filename: str, extract_dir: str, **kwargs: Any) -> None:
            return None

        shutil.register_unpack_format("demo", [".demo"], extract, [], "A demonstration format")
        try:
            assert "demo" in [name for name, _, _ in shutil.get_unpack_formats()]
        finally:
            shutil.unregister_unpack_format("demo")

        assert "demo" not in [name for name, _, _ in shutil.get_unpack_formats()]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="zstdtar arrived in 3.14")
    def test_zstdtar_joined_in_314(self) -> None:
        assert "zstdtar" in [name for name, _ in shutil.get_archive_formats()]

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="zstdtar arrived in 3.14")
    def test_zstdtar_is_absent_before_314(self) -> None:
        assert "zstdtar" not in [name for name, _ in shutil.get_archive_formats()]


class TestErrors:
    """The hierarchy, and what a tree operation collects."""

    def test_the_hierarchy(self) -> None:
        assert issubclass(shutil.SameFileError, shutil.Error)
        assert issubclass(shutil.Error, OSError)
        assert issubclass(shutil.SpecialFileError, OSError)

    def test_error_carries_the_failures_it_collected(self) -> None:
        failures = [("src", "dst", "permission denied")]

        error = shutil.Error(failures)

        assert error.args[0] == failures

    def test_a_missing_source_raises_from_os(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            shutil.copyfile(tmp_path / "absent", tmp_path / "target")

    def test_rmtree_on_a_missing_path_can_be_ignored(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            shutil.rmtree(tmp_path / "absent")

        shutil.rmtree(tmp_path / "absent", ignore_errors=True)  # must not raise


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
        timeout=180,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs in its own working directory, and none of them may
    leave anything in it — this page is the one where that matters."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_that_writes_uses_a_temporary_directory(self) -> None:
        writers = ("copyfile(", "copytree(", "make_archive(", "move(", "rmtree(")
        for line, source in _blocks():
            if any(call in source for call in writers):
                assert "tempfile" in source, (
                    f"{PAGE.name}:{line} writes without a temporary directory"
                )

    def test_every_block_runs_and_leaves_nothing_behind(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")
            leftovers = sorted(os.listdir(workdir))
            assert leftovers == ["_block.py"], f"{PAGE.name}:{line} left {leftovers}"

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import shutil\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr


@pytest.mark.parametrize("length", [1024, 1024 * 1024, -1])
def test_copyfileobj_length_controls_allocation(tmp_path: pathlib.Path, length: int) -> None:
    """Fixed 8 MiB input separates small/large buffers from a read-all request."""
    source = tmp_path / "input"
    source.write_bytes(b"x" * (8 << 20))

    def copy() -> None:
        with (
            source.open("rb", buffering=0) as reader,
            open(os.devnull, "wb", buffering=0) as writer,
        ):
            shutil.copyfileobj(reader, writer, length)

    peak = peak_bytes(copy)
    if length < 0:
        assert peak >= 8 << 20
    else:
        assert length <= peak < 3 * length + 32_000


@pytest.mark.skipif(not hasattr(os, "listxattr"), reason="extended attributes unavailable")
@pytest.mark.parametrize("dimension", ["names", "value"])
def test_copystat_attribute_allocation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, dimension: str
) -> None:
    """Name-list length and largest value size grow independently of file bytes."""
    source, target = tmp_path / "src", tmp_path / "dst"
    source.touch()
    target.touch()
    peaks = []
    for size in (10, 10_000):
        count = size if dimension == "names" else 1
        value_size = size * 100 if dimension == "value" else 1
        copied = [0]

        def names(*args: Any, count: int = count, **kwargs: Any) -> list[str]:
            return [f"user.key{i:06}" for i in range(count)]

        def value(*args: Any, value_size: int = value_size, **kwargs: Any) -> bytes:
            return b"x" * value_size

        def assign(*args: Any, copied: list[int] = copied, **kwargs: Any) -> None:
            # Count without retaining attribute names or values.
            copied[0] += 1

        monkeypatch.setattr(os, "listxattr", names)
        monkeypatch.setattr(os, "getxattr", value)
        monkeypatch.setattr(os, "setxattr", assign)
        peaks.append(peak_bytes(lambda: shutil.copystat(source, target)))
        assert copied[0] == count
    assert peaks[1] > peaks[0] * 20


@pytest.mark.skipif(os.name == "nt", reason="isolates POSIX PATH from PATHEXT")
def test_which_materializes_path_before_first_match(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def accept(*args: Any) -> bool:
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(shutil, "_access_check", accept)
    peaks = []
    for count in (100, 10_000):
        path = os.pathsep.join(f"/directory{i:06}" for i in range(count))
        calls = 0
        peaks.append(peak_bytes(lambda path=path: shutil.which("command", path=path)))
        assert calls == 1
    assert peaks[1] > peaks[0] * 20


@pytest.mark.parametrize("format_name", ["zip", "tar"])
@pytest.mark.parametrize("count", [10, 100])
def test_archives_retain_member_metadata(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, format_name: str, count: int
) -> None:
    """Observe the writer and reader member indexes with fixed empty payloads."""
    source = tmp_path / "src"
    source.mkdir()
    for index in range(count):
        (source / f"file{index:04}").touch()
    cls: Any = zipfile.ZipFile if format_name == "zip" else tarfile.TarFile
    field = "filelist" if format_name == "zip" else "members"
    original = cls.close
    sizes: list[int] = []

    def close(self: Any) -> None:
        sizes.append(len(getattr(self, field)))
        original(self)

    monkeypatch.setattr(cls, "close", close)
    archive = shutil.make_archive(str(tmp_path / "bundle"), format_name, str(source))
    assert max(sizes) >= count
    sizes.clear()
    shutil.unpack_archive(archive, str(tmp_path / "out"))
    assert max(sizes) >= count
    assert len(list((tmp_path / "out").iterdir())) == count


@pytest.mark.parametrize("unpack", [False, True])
@pytest.mark.parametrize("count", [32, 512])
def test_format_getters_sort_arbitrary_registration_order(
    monkeypatch: pytest.MonkeyPatch, unpack: bool, count: int
) -> None:
    comparisons = 0

    class Name(str):
        def __lt__(self, other: str) -> bool:
            nonlocal comparisons
            comparisons += 1
            return super().__lt__(other)

    names = [Name(f"format{i:04}") for i in range(count)]
    random.Random(42).shuffle(names)
    info: Any = ([], None, [], "description") if unpack else (None, [], "description")
    monkeypatch.setattr(
        shutil, "_UNPACK_FORMATS" if unpack else "_ARCHIVE_FORMATS", dict.fromkeys(names, info)
    )
    getter = shutil.get_unpack_formats if unpack else shutil.get_archive_formats
    result = getter()
    assert comparisons > count * 2
    assert [str(row[0]) for row in result] == sorted(str(name) for name in names)
    assert len(result) == count


@pytest.mark.parametrize("count", [10, 10_000])
def test_unpack_registration_visits_existing_extensions(
    monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    visits = 0

    class Extensions(list[str]):
        def __iter__(self) -> Any:
            nonlocal visits
            for value in super().__iter__():
                visits += 1
                yield value

    extensions = Extensions(f".ext{i:05}" for i in range(count))
    monkeypatch.setattr(shutil, "_UNPACK_FORMATS", {"existing": (extensions, None, [], "")})
    peak = peak_bytes(lambda: shutil.register_unpack_format("new", [".new"], lambda *a: None))
    assert visits == count
    if count == 10_000:
        assert peak > count * 10  # Temporary dictionary slots, with strings preallocated.


def test_copytree_aggregates_copy_failures(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    for name in ("a", "b"):
        (source / name).touch()
    calls = []

    def fail(src: Any, dst: Any) -> None:
        calls.append(src)
        raise PermissionError("denied")

    with pytest.raises(shutil.Error) as error:
        shutil.copytree(source, tmp_path / "dst", copy_function=fail)
    assert len(calls) == len(error.value.args[0]) == 2


def test_rmtree_stops_or_calls_error_handler(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    for name in ("a", "b"):
        (source / name).touch()
    calls = []
    handled = []

    def fail(*args: Any, **kwargs: Any) -> None:
        calls.append(args)
        raise PermissionError("denied")

    def handle(*args: Any) -> None:
        handled.append(args)

    with monkeypatch.context() as patch:
        patch.setattr(os, "unlink", fail)
        with pytest.raises(PermissionError):
            shutil.rmtree(source)
        assert len(calls) == 1
        calls.clear()
        options: Any = {"onexc" if sys.version_info >= (3, 12) else "onerror": handle}
        shutil.rmtree(source, **options)
        assert len(calls) == 2
        assert len(handled) == 3  # Two unlinks and removal of the still-nonempty directory.
