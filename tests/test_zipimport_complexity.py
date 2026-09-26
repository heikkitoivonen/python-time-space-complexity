"""Tests for docs/stdlib/zipimport.md.

The page prices the module in two units: the archive's central directory,
read once per archive path into a cache shared by every importer, and one
member, read from disk each time it is asked for. The directory is settled by
counting calls to `zipimport._read_directory` and by traced allocation over
archives of different entry counts; the lookup-only rows by wrapping the
cached directory in a dictionary that counts its probes; the member rows by
counting calls to `zipimport._get_data` and `zipimport._compile_source`, which
every read and every compile goes through on every supported version.

Measurement scope:

* `zipimporter()` calls `_read_directory` once for a new archive path and not
  at all for a second importer on it, including one built with a subpath; the
  second importer's traced peak is under 20 KB over a 20,000-entry archive.
  Building the first importer over 2,000 and 20,000 one-byte members peaks
  more than 5x apart, and the cached directory holds an entry per member.
  Over ten members of 1 MB and ten of one byte, the peaks are within 2x of
  each other and under 1 MB, below one member's size, and no member is read.
* A `find_spec()` miss and `is_package()` make at most five probes of the
  directory and read no member, at 10 entries and at 10,000 alike. A
  `find_spec()` hit on a module or package reads its member once and, for a
  `.py` member, compiles it once; a namespace directory is found by lookups
  alone.
* `get_code()`, `get_filename()` and `get_source()` read the member once per
  call and repeat it on the next call; `get_code()` and `get_filename()`
  compile a `.py` member on every call and compile nothing when a `.pyc`
  written by `compileall` with `legacy=True` sits beside it, and the archive's
  bytes are unchanged afterwards. A `.pyc` under `__pycache__` is not used,
  and one whose recorded source size no longer matches the `.py` member is
  passed over for the source. `pkg/__init__.py` is chosen over `pkg.py`. `get_data()` reads once per call, and its traced
  peak exceeds 5 MB for a 5 MB member, over 20x its peak for a 10 KB one,
  while a 20,000-entry archive with a 10 KB member stays within 2x of a
  10-entry one.
* Importing through `sys.path` reads the member twice and compiles a `.py`
  member twice, once in `find_spec()` and once in `exec_module()`, and a
  `.pyc` beside it none. A module the archive lacks, looked up through
  `sys.path` with the archive first, makes between one and five probes of
  its 10,001-entry directory and reads nothing.
* `invalidate_caches()` calls `_read_directory` inside the call on 3.10-3.12
  and not on 3.13+, where the next lookup calls it once; on every version a
  member appended to the archive becomes visible after it, and
  `importlib.invalidate_caches()` reaches an importer in
  `sys.path_importer_cache`.
* `get_resource_reader()` builds its reader without opening the archive with
  `zipfile`, and each `files()` call on the reader runs
  `zipfile.ZipFile._RealGetContents` once.
* `load_module()` warns with `DeprecationWarning` and returns the executed
  module; `create_module()` returns `None`; `exec_module()` runs the body.
  `ZipImportError` subclasses `ImportError` and is raised for a file that is
  not an archive and a module the archive lacks; `archive` and `prefix` are
  asserted on a subpath.
* The Version Notes are asserted on both sides of each boundary: a directory
  with no entry of its own is found as a namespace package on 3.14+ and not
  before; a module in a 70,001-entry archive, which `zipfile` writes with a
  ZIP64 end-of-directory record, is found on 3.13+ and not before; and
  `find_loader()` and `find_module()` exist before 3.12 and not from it.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* ZIP64 archives over 4 GiB, and members with ZIP64 size or offset fields,
  are not built; the 3.13 boundary is asserted on entry count alone.
* Compiling and unmarshalling are priced at O(b). Compile cost is the
  compiler's, and pathological sources are not varied.
* Entry names are priced at O(1); name length, path depth, compression
  method and archive comments are not varied. Construction on a file that is
  not an archive is asserted to raise, and its cost is not measured.
* API coverage: the page-scoped audit reports no missing names.
  `zipimporter.get_resource_reader()` is not in the official inventory and
  is documented from the runtime. The module-level format constants
  (`END_CENTRAL_DIR_SIZE`, `STRING_END_ARCHIVE`, `MAX_COMMENT_LEN` and the
  rest), `cp437_table`, `path_sep` and `alt_path_sep` are implementation
  details outside `__all__` and are not documented.
"""

from __future__ import annotations

import compileall
import importlib
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
import zipfile
import zipimport
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zipimport.md"
EXPECTED_BLOCKS = 4


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def build(path: pathlib.Path, members: Mapping[str, str | bytes], filler: int = 0) -> str:
    """Write an archive holding `members` plus `filler` one-byte data members."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
        for index in range(filler):
            zf.writestr(f"data/f{index}.txt", "x")
    return str(path)


class ProbeCountingDict(dict):  # type: ignore[type-arg]
    """A directory that counts how often it is probed."""

    probes = 0

    def __contains__(self, key: object) -> bool:
        self.probes += 1
        return super().__contains__(key)

    def __getitem__(self, key: Any) -> Any:
        self.probes += 1
        return super().__getitem__(key)


class Calls:
    """Counts of the module's directory reads, member reads and compiles."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.directory = 0
        self.member = 0
        self.compiled = 0
        read_directory = zipimport._read_directory  # type: ignore[attr-defined]  # noqa: SLF001
        get_data = zipimport._get_data  # type: ignore[attr-defined]  # noqa: SLF001
        compile_source = zipimport._compile_source  # type: ignore[attr-defined]  # noqa: SLF001

        def counting_read_directory(archive: str) -> ProbeCountingDict:
            self.directory += 1
            return ProbeCountingDict(read_directory(archive))

        def counting_get_data(*args: Any) -> Any:
            self.member += 1
            return get_data(*args)

        def counting_compile_source(*args: Any) -> Any:
            self.compiled += 1
            return compile_source(*args)

        monkeypatch.setattr(zipimport, "_read_directory", counting_read_directory)
        monkeypatch.setattr(zipimport, "_get_data", counting_get_data)
        monkeypatch.setattr(zipimport, "_compile_source", counting_compile_source)

    def reset(self) -> None:
        self.directory = self.member = self.compiled = 0


def directory_of(importer: zipimport.zipimporter) -> ProbeCountingDict:
    """The cached directory an importer consults."""
    cache = zipimport._zip_directory_cache  # type: ignore[attr-defined]  # noqa: SLF001
    files = cache[importer.archive]
    assert isinstance(files, ProbeCountingDict)
    return files


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[Calls]:
    cache = zipimport._zip_directory_cache  # type: ignore[attr-defined]  # noqa: SLF001
    before = set(cache)
    yield Calls(monkeypatch)
    for key in set(cache) - before:
        del cache[key]


def with_bytecode(tmp_path: pathlib.Path, name: str, legacy: bool = True) -> str:
    """An archive holding `name.py` and its `.pyc`, beside it or under `__pycache__`."""
    source = tmp_path / f"{name}.py"
    source.write_text("VALUE = 42\n", encoding="utf-8")
    assert compileall.compile_file(str(source), legacy=legacy, quiet=1)
    if legacy:
        compiled = tmp_path / f"{name}.pyc"
        arcname = f"{name}.pyc"
    else:
        compiled = next((tmp_path / "__pycache__").glob(f"{name}.*.pyc"))
        arcname = f"__pycache__/{compiled.name}"
    archive = tmp_path / f"{name}-{'legacy' if legacy else 'cache'}.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(source, f"{name}.py")
        zf.write(compiled, arcname)
    return str(archive)


class TestTheDirectoryIsReadOncePerArchive:
    """`zipimporter(archivepath)` | O(n) | O(n): the first importer reads the
    central directory, later ones reuse it, and member data is not read."""

    def test_a_second_importer_reuses_the_directory(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"lib/mod.py": ""}, filler=10)

        first = zipimport.zipimporter(archive)
        second = zipimport.zipimporter(archive)
        nested = zipimport.zipimporter(os.path.join(archive, "lib"))

        assert calls.directory == 1
        assert first.archive == second.archive == nested.archive == archive
        assert nested.prefix == "lib" + os.sep
        assert first.prefix == ""

    def test_a_second_importer_allocates_nothing_for_the_entries(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {}, filler=20_000)
        zipimport.zipimporter(archive)

        peak = peak_bytes(lambda: zipimport.zipimporter(archive))

        assert calls.directory == 1
        assert peak < 20_000, f"a second importer over 20,000 entries allocated {peak} bytes"

    def test_the_first_importer_grows_with_the_entries(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        cache = zipimport._zip_directory_cache  # type: ignore[attr-defined]  # noqa: SLF001
        peaks = []
        for entries in (2_000, 20_000):
            archive = build(tmp_path / f"n{entries}.zip", {}, filler=entries)
            peaks.append(peak_bytes(lambda a=archive: zipimport.zipimporter(a)))  # type: ignore[misc]
            assert len(cache[archive]) >= entries

        assert peaks[1] > peaks[0] * 5, f"10x the entries: {peaks}"

    def test_member_sizes_do_not_reach_the_directory_read(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        big = {f"m{index}.bin": b"\0" * 1_000_000 for index in range(10)}
        small = {f"m{index}.bin": b"\0" for index in range(10)}
        archives = [build(tmp_path / "big.zip", big), build(tmp_path / "small.zip", small)]

        peaks = [peak_bytes(lambda a=a: zipimport.zipimporter(a)) for a in archives]  # type: ignore[misc]

        assert max(peaks) < 1_000_000, f"ten 1 MB members against ten 1-byte ones: {peaks}"
        assert peaks[0] < peaks[1] * 2, f"ten 1 MB members against ten 1-byte ones: {peaks}"
        assert calls.member == 0


class TestLookupsAreNameProbes:
    """`is_package()` and a `find_spec()` miss are O(1): a few name lookups,
    whatever the archive's size, and no member is read."""

    @pytest.mark.parametrize("entries", [10, 10_000])
    def test_a_miss_and_is_package_probe_a_bounded_number_of_names(
        self, tmp_path: pathlib.Path, calls: Calls, entries: int
    ) -> None:
        archive = build(tmp_path / "a.zip", {"pkg/__init__.py": "", "mod.py": ""}, entries)
        importer = zipimport.zipimporter(archive)
        files = directory_of(importer)

        files.probes = 0
        assert importer.find_spec("missing") is None
        miss = files.probes

        files.probes = 0
        assert importer.is_package("pkg") is True
        assert importer.is_package("mod") is False
        package = files.probes

        assert miss <= 5, f"a miss probed {miss} names over {entries} entries"
        assert package <= 8, f"two is_package calls probed {package} names"
        assert calls.member == 0

    def test_a_file_that_is_not_an_archive_raises(self, tmp_path: pathlib.Path) -> None:
        plain = tmp_path / "plain.zip"
        plain.write_bytes(b"not an archive" * 100)

        with pytest.raises(zipimport.ZipImportError, match="not a Zip file"):
            zipimport.zipimporter(str(plain))

    def test_is_package_raises_for_a_module_it_does_not_hold(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        importer = zipimport.zipimporter(build(tmp_path / "a.zip", {"mod.py": ""}))

        with pytest.raises(zipimport.ZipImportError, match="can't find module"):
            importer.is_package("missing")
        assert issubclass(zipimport.ZipImportError, ImportError)

    def test_a_hit_reads_and_compiles_its_member(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"mod.py": "X = 1\n", "pkg/__init__.py": ""})
        importer = zipimport.zipimporter(archive)

        spec = importer.find_spec("mod")
        assert spec is not None and spec.loader is importer
        assert (calls.member, calls.compiled) == (1, 1)

        package = importer.find_spec("pkg")
        assert package is not None
        assert package.submodule_search_locations == [os.path.join(archive, "pkg")]
        assert (calls.member, calls.compiled) == (2, 2)

    def test_a_namespace_directory_is_found_by_lookup_alone(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = tmp_path / "a.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(zipfile.ZipInfo("ns/"), "")
            zf.writestr("ns/mod.py", "")
        importer = zipimport.zipimporter(str(archive))

        spec = importer.find_spec("ns")

        assert spec is not None and spec.loader is None
        assert spec.submodule_search_locations == [os.path.join(str(archive), "ns")]
        assert calls.member == 0


class TestMembersAreReadEveryTime:
    """`get_code`, `get_filename`, `get_source`, `get_data` | O(b) | O(b): each
    call reads its member from disk, and `get_code` and `get_filename` compile a
    `.py` member each time."""

    def test_get_code_and_get_filename_read_and_compile_on_every_call(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"mod.py": "X = 1\n"})
        before = pathlib.Path(archive).read_bytes()
        importer = zipimport.zipimporter(archive)

        importer.get_code("mod")
        importer.get_code("mod")
        assert (calls.member, calls.compiled) == (2, 2)

        assert importer.get_filename("mod") == os.path.join(archive, "mod.py")
        assert importer.get_filename("mod") == os.path.join(archive, "mod.py")
        assert (calls.member, calls.compiled) == (4, 4)
        assert pathlib.Path(archive).read_bytes() == before, "the archive was modified"

    def test_bytecode_beside_the_source_is_not_compiled(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        importer = zipimport.zipimporter(with_bytecode(tmp_path, "fast"))

        code = importer.get_code("fast")
        filename = importer.get_filename("fast")

        namespace: dict[str, Any] = {}
        exec(code, namespace)  # noqa: S102
        assert namespace["VALUE"] == 42
        assert filename.endswith("fast.pyc")
        assert calls.compiled == 0
        assert calls.member == 2

    def test_bytecode_under_pycache_is_not_used(self, tmp_path: pathlib.Path, calls: Calls) -> None:
        importer = zipimport.zipimporter(with_bytecode(tmp_path, "slow", legacy=False))

        assert importer.get_filename("slow").endswith("slow.py")
        assert calls.compiled == 1

    def test_stale_bytecode_falls_back_to_compiling_the_source(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = with_bytecode(tmp_path, "stale")
        with zipfile.ZipFile(archive) as zf:
            members = {name: zf.read(name) for name in zf.namelist()}
        members["stale.py"] = b"VALUE = 43  # a different size\n"
        importer = zipimport.zipimporter(build(tmp_path / "stale2.zip", members))

        assert importer.get_filename("stale").endswith("stale.py")
        assert calls.compiled == 1

    def test_a_package_is_tried_before_a_module_of_the_same_name(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"both.py": "", "both/__init__.py": ""})
        importer = zipimport.zipimporter(archive)

        assert importer.get_filename("both") == os.path.join(archive, "both", "__init__.py")
        assert importer.is_package("both") is True

    def test_get_source_reads_the_py_member_or_returns_none(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"mod.py": "X = 1\n", "only.pyc": b""})
        importer = zipimport.zipimporter(archive)

        assert importer.get_source("mod") == "X = 1\n"
        assert importer.get_source("mod") == "X = 1\n"
        assert importer.get_source("only") is None
        assert calls.member == 2
        with pytest.raises(zipimport.ZipImportError):
            importer.get_source("missing")

    def test_get_data_reads_on_every_call_and_raises_for_a_missing_member(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"data.txt": "payload"})
        importer = zipimport.zipimporter(archive)

        assert importer.get_data("data.txt") == b"payload"
        assert importer.get_data(os.path.join(archive, "data.txt")) == b"payload"
        assert calls.member == 2
        with pytest.raises(OSError):
            importer.get_data("missing.txt")

    def test_get_data_follows_the_member_not_the_archive(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        def probe(name: str, size: int, entries: int) -> int:
            archive = build(tmp_path / name, {"blob.bin": b"\1" * size}, filler=entries)
            importer = zipimport.zipimporter(archive)
            importer.get_data("blob.bin")
            return peak_bytes(lambda: importer.get_data("blob.bin"))

        small = probe("small.zip", 10_000, 10)
        large = probe("large.zip", 5_000_000, 10)
        crowded = probe("crowded.zip", 10_000, 20_000)

        assert large > 5_000_000, f"a 5 MB member peaked at {large} bytes"
        assert large > small * 20, f"500x the member: {small} to {large} bytes"
        assert crowded < small * 2, f"2,000x the entries: {small} to {crowded} bytes"


class TestImportingThroughSysPath:
    """Each module imported from an archive on `sys.path` is read and decoded
    twice, once by `find_spec()` and once by `exec_module()`."""

    @pytest.fixture
    def on_path(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
        added: list[str] = []

        def add(archive: str) -> None:
            monkeypatch.syspath_prepend(archive)
            added.append(archive)

        yield add
        for archive in added:
            sys.path_importer_cache.pop(archive, None)

    @pytest.mark.parametrize(("legacy", "compiles"), [(False, 2), (True, 0)])
    def test_an_import_reads_the_member_twice_and_compiles_only_source(
        self,
        tmp_path: pathlib.Path,
        calls: Calls,
        on_path: Callable[[str], None],
        legacy: bool,
        compiles: int,
    ) -> None:
        name = f"zipimport_probe_{'pyc' if legacy else 'py'}"
        if legacy:
            archive = with_bytecode(tmp_path, name)
        else:
            archive = build(tmp_path / "a.zip", {f"{name}.py": "VALUE = 42\n"})
        assert name not in sys.modules
        on_path(archive)

        try:
            module = importlib.import_module(name)
        finally:
            sys.modules.pop(name, None)

        assert module.VALUE == 42
        assert isinstance(sys.path_importer_cache[archive], zipimport.zipimporter)
        assert calls.compiled == compiles
        assert calls.member == 2

    def test_a_module_the_archive_lacks_costs_it_a_few_lookups(
        self, tmp_path: pathlib.Path, calls: Calls, on_path: Callable[[str], None]
    ) -> None:
        archive = build(tmp_path / "a.zip", {"present.py": ""}, filler=10_000)
        on_path(archive)
        importlib.util.find_spec("present")
        files = directory_of(sys.path_importer_cache[archive])  # type: ignore[arg-type]
        calls.reset()
        files.probes = 0

        assert importlib.util.find_spec("zipimport_probe_absent") is None

        assert 0 < files.probes <= 5, f"a miss probed {files.probes} names"
        assert (calls.directory, calls.member) == (0, 0)


class TestInvalidatingTheDirectory:
    """`invalidate_caches()` | O(1) on 3.13+, O(n) on 3.10-3.12: it drops the
    cached directory, and either rereads it at once or at the next lookup."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="deferred from 3.13")
    def test_the_reread_waits_for_the_next_lookup(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        importer = zipimport.zipimporter(build(tmp_path / "a.zip", {"mod.py": ""}))
        calls.reset()

        importer.invalidate_caches()
        assert calls.directory == 0

        importer.is_package("mod")
        assert calls.directory == 1

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="deferred from 3.13")
    def test_the_reread_happens_in_the_call(self, tmp_path: pathlib.Path, calls: Calls) -> None:
        importer = zipimport.zipimporter(build(tmp_path / "a.zip", {"mod.py": ""}))
        calls.reset()

        importer.invalidate_caches()
        assert calls.directory == 1

    def test_an_appended_member_appears_only_after_invalidating(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"first.py": ""})
        importer = zipimport.zipimporter(archive)
        with zipfile.ZipFile(archive, "a") as zf:
            zf.writestr("second.py", "")

        assert importer.find_spec("second") is None
        importer.invalidate_caches()
        assert importer.find_spec("second") is not None

    def test_importlib_invalidate_caches_reaches_path_importers(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"first.py": ""})
        importer = zipimport.zipimporter(archive)
        sys.path_importer_cache[archive] = importer
        try:
            with zipfile.ZipFile(archive, "a") as zf:
                zf.writestr("second.py", "")
            assert importer.find_spec("second") is None

            importlib.invalidate_caches()

            assert importer.find_spec("second") is not None
        finally:
            del sys.path_importer_cache[archive]


class TestLoaderProtocol:
    """`create_module`, `exec_module`, `load_module`, `get_resource_reader`."""

    def test_create_module_asks_for_the_default(self, tmp_path: pathlib.Path, calls: Calls) -> None:
        importer = zipimport.zipimporter(build(tmp_path / "a.zip", {"mod.py": ""}))
        spec = importer.find_spec("mod")

        assert importer.create_module(spec) is None  # type: ignore[arg-type]

    def test_exec_module_reads_the_member_again_and_runs_it(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        importer = zipimport.zipimporter(build(tmp_path / "a.zip", {"mod.py": "X = 7\n"}))
        spec = importer.find_spec("mod")
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        calls.reset()

        importer.exec_module(module)

        assert module.X == 7
        assert (calls.member, calls.compiled) == (1, 1)

    def test_load_module_warns_and_loads(self, tmp_path: pathlib.Path, calls: Calls) -> None:
        importer = zipimport.zipimporter(
            build(tmp_path / "a.zip", {"zipimport_load_probe.py": "X = 3\n"})
        )
        try:
            with pytest.warns(DeprecationWarning):
                module = importer.load_module("zipimport_load_probe")
            assert module.X == 3
            assert calls.member == 1
        finally:
            sys.modules.pop("zipimport_load_probe", None)

    def test_each_files_call_rereads_the_directory_with_zipfile(
        self, tmp_path: pathlib.Path, calls: Calls, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        archive = build(tmp_path / "a.zip", {"pkg/__init__.py": "", "pkg/data.txt": "x"})
        importer = zipimport.zipimporter(archive)
        reads = 0
        original = zipfile.ZipFile._RealGetContents  # type: ignore[attr-defined]  # noqa: SLF001

        def counting(self: zipfile.ZipFile) -> None:
            nonlocal reads
            reads += 1
            original(self)

        monkeypatch.setattr(zipfile.ZipFile, "_RealGetContents", counting)

        reader = importer.get_resource_reader("pkg")
        assert reads == 0
        assert reader is not None

        files = [reader.files() for _ in range(3)]  # type: ignore[attr-defined]

        assert reads == 3
        assert files[0].joinpath("data.txt").read_text() == "x"


class TestVersionBoundaries:
    """The Version Notes entries that can be run on this interpreter."""

    def test_find_loader_and_find_module_are_gone_from_312(self) -> None:
        present = sys.version_info < (3, 12)

        assert hasattr(zipimport.zipimporter, "find_loader") is present
        assert hasattr(zipimport.zipimporter, "find_module") is present

    def test_a_directory_without_an_entry_is_a_namespace_package_from_314(
        self, tmp_path: pathlib.Path, calls: Calls
    ) -> None:
        archive = build(tmp_path / "a.zip", {"ns/mod.py": ""})
        with zipfile.ZipFile(archive) as zf:
            assert "ns/" not in zf.namelist()

        spec = zipimport.zipimporter(archive).find_spec("ns")

        if sys.version_info >= (3, 14):
            assert spec is not None and spec.loader is None
        else:
            assert spec is None

    def test_a_zip64_archive_is_read_from_313(self, tmp_path: pathlib.Path, calls: Calls) -> None:
        archive = build(tmp_path / "wide.zip", {"mod.py": "X = 1\n"}, filler=70_000)
        with open(archive, "rb") as f:
            f.seek(-200, os.SEEK_END)
            assert b"PK\x06\x06" in f.read(), "no ZIP64 end-of-directory record"

        spec = zipimport.zipimporter(archive).find_spec("mod")

        if sys.version_info >= (3, 13):
            assert spec is not None
        else:
            assert spec is None


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
    """Each block runs in its own subprocess, so `sys.path`, `sys.modules` and
    the directory cache cannot leak between them, and asserts its own result."""

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
        target = "endswith('fast.pyc')"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "endswith('fast.py')", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
