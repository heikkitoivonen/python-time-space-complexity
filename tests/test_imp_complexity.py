"""Evidence for docs/stdlib/imp.md on Python 3.10 and 3.11.

The documented scope is the API in the official 3.11 documentation plus the
undocumented load_source, load_compiled and load_package loaders. The _imp
re-exports create_dynamic, get_frozen_object and is_frozen_package, the
re-exported SourcelessFileLoader, and the modules imp imports are outside it.
Runtime tests execute only where the module exists; availability is checked on
every supported interpreter.

Observation settles most rows. A counting os.path.isfile pins find_module at
exactly p * (2 + s) probes for a miss over 10 and 1000 directories and at zero
probes for a built-in or frozen name; a counting readline handed to
tokenize.detect_encoding pins that it consumes one line of a 6 MiB source
whose first line is code and two when the first line is a comment, and a
traced peak under 64 KiB pins that no more of the file is read into memory.
A counting FileLoader.get_data pins that
load_source, load_compiled and reload read exactly the file they load, and a
counting SourceFileLoader.source_to_code pins one compilation for a fresh
source, none while the .pyc is valid, and one again after the source changes,
when the stale .pyc is read in full before the source is.
Traced transient memory (the peak less what the loaded module retains) at
5,000 and 40,000 assignment lines (about 9x the bytes) grows between 4x and 16x for
load_source, both fresh and from its cache, and for load_compiled, which
separates linear from constant and from quadratic growth. load_package and
reload run the same SourceFileLoader path and are pinned by what they read,
not measured again. Compilation and unmarshalling are taken as linear in the
bytes they consume, the same framing as docs/stdlib/py_compile.md.
load_package is pinned by a submodule that raises if executed, and the
bytecode cache by a load with sys.dont_write_bytecode set, which writes
nothing and compiles again.

Source-only, because b and f are fixed per interpreter and cannot be varied:
is_builtin and init_builtin walk PyImport_Inittab with a string compare per
entry, and is_frozen and init_frozen walk the frozen tables the same way
(Python/import.c is_builtin and look_up_frozen on 3.11, find_frozen on 3.10).
load_dynamic's cost is dlopen and the extension's init function, which no
Python-level counter sees; the test checks only that Python reads nothing.
The deprecation and removal versions come from the official documentation
linked on the page.

Not varied: path length, the length of the first two source lines that
find_module reads for the encoding, extension modules other than the first
loadable one in lib-dynload, source that compiles to unusually large or small
bytecode, the finders reload consults, how long acquire_lock waits for a
contended lock, and the cost of the loaded module's body. The two code fences
run in a subprocess, the imp one only where the module exists.
"""

import importlib
import importlib._bootstrap_external
import importlib.machinery
import importlib.util
import io
import py_compile
import re
import subprocess
import sys
import sysconfig
import threading
import tracemalloc
import types
import warnings
from collections.abc import Callable, Iterator
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

PAGE = Path(__file__).resolve().parent.parent / "docs/stdlib/imp.md"
OUT_OF_SCOPE = {
    "create_dynamic",
    "get_frozen_object",
    "is_frozen_package",
    "SourcelessFileLoader",
    "importlib",
    "machinery",
    "os",
    "sys",
    "tokenize",
    "types",
    "util",
    "warnings",
}
SIZES = (5_000, 40_000)
MISSING = object()


def test_availability() -> None:
    assert (importlib.util.find_spec("imp") is not None) == (sys.version_info < (3, 12))


@pytest.fixture
def imp() -> Iterator[Any]:
    if sys.version_info >= (3, 12):
        pytest.skip("imp was removed in Python 3.12")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("imp")


def _documented_names() -> set[str]:
    rows = re.findall(r"^\| (`[^|]+`) \| O\(", PAGE.read_text(), re.MULTILINE)
    return {name for row in rows for name in re.findall(r"`([A-Za-z_]+)[(`]", row)}


def _write_source(path: Path, lines: int) -> int:
    path.write_text("".join(f"x{i} = {i}\n" for i in range(lines)))
    return path.stat().st_size


@pytest.fixture
def modules() -> Iterator[Callable[[str], None]]:
    saved: dict[str, Any] = {}

    def claim(name: str) -> None:
        saved.setdefault(name, sys.modules.get(name, MISSING))
        sys.modules.pop(name, None)

    yield claim
    for name, module in saved.items():
        if module is MISSING:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    loader = importlib._bootstrap_external.FileLoader  # pyright: ignore[reportAttributeAccessIssue]
    original = loader.get_data
    seen: dict[str, int] = {}

    def get_data(self: Any, path: str) -> bytes:
        data = original(self, path)
        seen[path] = seen.get(path, 0) + len(data)
        return data

    monkeypatch.setattr(loader, "get_data", get_data)
    return seen


@pytest.fixture
def compiles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    loader = importlib.machinery.SourceFileLoader
    original = loader.source_to_code
    seen: list[str] = []

    def source_to_code(self: Any, data: Any, path: str, *args: Any, **kwargs: Any) -> Any:
        seen.append(path)
        return original(self, data, path, *args, **kwargs)

    monkeypatch.setattr(loader, "source_to_code", source_to_code)
    return seen


def _transient(call: Callable[..., Any], *args: Any) -> tuple[int, Any]:
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        result = call(*args)
        retained, peak = tracemalloc.get_traced_memory()
        return peak - retained, result
    finally:
        tracemalloc.stop()


def _assert_linear(peaks: tuple[int, int], label: str) -> None:
    small, large = peaks
    assert small * 4 < large < small * 16, (label, small, large)


def test_table_covers_the_public_api(imp: Any) -> None:
    documented = _documented_names()
    assert "find_module" in documented and "IMP_HOOK" in documented
    public = {name for name in dir(imp) if not name.startswith("_")} - OUT_OF_SCOPE
    assert documented == public, (sorted(documented - public), sorted(public - documented))
    assert OUT_OF_SCOPE <= set(dir(imp))


def test_type_codes(imp: Any) -> None:
    names = re.search(r"^\| (`SEARCH_ERROR`.*?) \| O\(", PAGE.read_text(), re.MULTILINE)
    assert names is not None
    codes = [getattr(imp, name) for name in re.findall(r"`([A-Z_]+)`", names.group(1))]
    assert codes == list(range(10))


@pytest.mark.parametrize("directories", [10, 1000])
def test_find_module_probes_every_directory(
    imp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directories: int
) -> None:
    probes: list[str] = []
    original = imp.os.path.isfile

    def isfile(path: str) -> bool:
        probes.append(path)
        return original(path)

    monkeypatch.setattr(imp.os.path, "isfile", isfile)
    path = []
    for index in range(directories):
        directory = tmp_path / str(index)
        directory.mkdir()
        path.append(str(directory))
    per_directory = 2 + len(imp.get_suffixes())
    with pytest.raises(ImportError):
        imp.find_module("missing", path)
    assert len(probes) == directories * per_directory
    _write_source(tmp_path / str(directories - 1) / "found.py", 1)
    probes.clear()
    file, pathname, details = imp.find_module("found", path)
    with file:
        assert not file.closed
    assert (directories - 1) * per_directory < len(probes) <= directories * per_directory
    assert pathname == str(tmp_path / str(directories - 1) / "found.py")
    assert details == (".py", "r", imp.PY_SOURCE)


def test_find_module_checks_tables_before_directories(
    imp: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    probes: list[str] = []
    monkeypatch.setattr(imp.os.path, "isfile", lambda path: probes.append(path) or False)
    assert imp.find_module("errno") == (None, None, ("", "", imp.C_BUILTIN))
    assert imp.find_module("__hello__") == (None, None, ("", "", imp.PY_FROZEN))
    assert probes == []


@pytest.mark.parametrize(
    ("first_line", "expected"),
    [("", [b"x0 = 0\n"]), ("# a comment\n", [b"# a comment\n", b"x0 = 0\n"])],
)
def test_find_module_reads_only_the_encoding_lines(
    imp: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_line: str,
    expected: list[bytes],
) -> None:
    source = tmp_path / "big.py"
    size = _write_source(source, 400_000)
    source.write_text(first_line + source.read_text())
    assert size > 6 * 1024 * 1024
    consumed: list[bytes] = []
    original = imp.tokenize.detect_encoding

    def detect_encoding(readline: Callable[[], bytes]) -> Any:
        def counting() -> bytes:
            line = readline()
            consumed.append(line)
            return line

        return original(counting)

    monkeypatch.setattr(imp.tokenize, "detect_encoding", detect_encoding)
    assert not tracemalloc.is_tracing()
    tracemalloc.start()
    try:
        file, _, _ = imp.find_module("big", [str(tmp_path)])
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    file.close()
    assert consumed == expected
    assert peak < 64 * 1024, (size, peak)


def test_load_source_reads_the_file_and_compiles_once(
    imp: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: Callable[[str], None],
    reads: dict[str, int],
    compiles: list[str],
) -> None:
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    fresh: list[int] = []
    cached: list[int] = []
    for lines in SIZES:
        name = f"imp_source_{lines}"
        modules(name)
        source = tmp_path / f"{name}.py"
        size = _write_source(source, lines)
        pyc = imp.cache_from_source(str(source))
        reads.clear()
        compiles.clear()
        transient, module = _transient(imp.load_source, name, str(source))
        fresh.append(transient)
        assert reads == {str(source): size}
        assert compiles == [str(source)]
        assert Path(pyc).is_file()
        assert getattr(module, f"x{lines - 1}") == lines - 1
        reads.clear()
        compiles.clear()
        transient, again = _transient(imp.load_source, name, str(source))
        cached.append(transient)
        assert reads == {pyc: Path(pyc).stat().st_size}
        assert compiles == []
        assert again is module is sys.modules[name]
    _assert_linear((fresh[0], fresh[1]), "load_source")
    _assert_linear((cached[0], cached[1]), "load_source from cache")


def test_load_source_without_bytecode_writing_compiles_every_time(
    imp: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: Callable[[str], None],
    reads: dict[str, int],
    compiles: list[str],
) -> None:
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    source = tmp_path / "imp_uncached.py"
    size = _write_source(source, 100)
    modules("imp_uncached")
    for _ in range(2):
        reads.clear()
        compiles.clear()
        imp.load_source("imp_uncached", str(source))
        assert reads == {str(source): size}
        assert compiles == [str(source)]
    assert not Path(imp.cache_from_source(str(source))).exists()


def test_load_compiled_reads_the_pyc_without_compiling(
    imp: Any,
    tmp_path: Path,
    modules: Callable[[str], None],
    reads: dict[str, int],
    compiles: list[str],
) -> None:
    peaks: list[int] = []
    for lines in SIZES:
        name = f"imp_compiled_{lines}"
        modules(name)
        source = tmp_path / f"{name}.py"
        _write_source(source, lines)
        pyc = tmp_path / f"{name}.pyc"
        py_compile.compile(str(source), cfile=str(pyc), doraise=True)
        reads.clear()
        compiles.clear()
        transient, module = _transient(imp.load_compiled, name, str(pyc))
        peaks.append(transient)
        assert reads == {str(pyc): pyc.stat().st_size}
        assert compiles == []
        assert getattr(module, f"x{lines - 1}") == lines - 1
    _assert_linear((peaks[0], peaks[1]), "load_compiled")


def test_load_package_executes_only_init(
    imp: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: Callable[[str], None],
    reads: dict[str, int],
) -> None:
    package = tmp_path / "imp_package"
    package.mkdir()
    init = package / "__init__.py"
    init.write_text("VALUE = 1\n")
    (package / "child.py").write_text("raise RuntimeError('executed')\n")
    probes: list[str] = []
    original = imp.os.path.exists
    monkeypatch.setattr(imp.os.path, "exists", lambda p: probes.append(p) or original(p))
    modules("imp_package")
    module = imp.load_package("imp_package", str(package))
    assert module.VALUE == 1 and module.__path__ == [str(package)]
    assert probes == [str(init)]
    assert set(reads) == {str(init)}
    assert "imp_package.child" not in sys.modules
    empty = tmp_path / "not_a_package"
    empty.mkdir()
    probes.clear()
    with pytest.raises(ValueError):
        imp.load_package("not_a_package", str(empty))
    suffixes = imp.machinery.SOURCE_SUFFIXES + imp.machinery.BYTECODE_SUFFIXES
    assert len(probes) == len(suffixes)


def test_load_module_dispatches_on_the_type_code(
    imp: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: Callable[[str], None],
    reads: dict[str, int],
    compiles: list[str],
) -> None:
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    source = tmp_path / "imp_dispatch.py"
    source.write_text("VALUE = 2\n")
    modules("imp_dispatch")
    with pytest.raises(ValueError):
        imp.load_module("imp_dispatch", None, str(source), (".py", "w", imp.PY_SOURCE))
    with pytest.raises(ValueError):
        imp.load_module("imp_dispatch", None, str(source), (".py", "r", imp.PY_SOURCE))
    assert reads == {}
    file, pathname, details = imp.find_module("imp_dispatch", [str(tmp_path)])
    with file:
        module = imp.load_module("imp_dispatch", file, pathname, details)
    assert module.VALUE == 2 and sys.modules["imp_dispatch"] is module
    assert compiles == [str(source)]
    pyc = imp.cache_from_source(str(source))
    reads.clear()
    compiles.clear()
    assert imp.load_source("imp_dispatch", str(source)) is module
    assert reads == {pyc: Path(pyc).stat().st_size}
    assert compiles == []
    modules("errno")
    builtin = imp.load_module("errno", None, "", ("", "", imp.C_BUILTIN))
    assert builtin.ENOENT == 2


def test_load_dynamic_reads_nothing_in_python(
    imp: Any, modules: Callable[[str], None], reads: dict[str, int]
) -> None:
    if imp.load_dynamic is None:
        pytest.skip("dynamic loading is not supported on this platform")
    dynload = Path(sysconfig.get_paths()["stdlib"]) / "lib-dynload"
    suffixes = tuple(imp.machinery.EXTENSION_SUFFIXES)
    candidates = sorted(path for path in dynload.iterdir() if path.name.endswith(suffixes))
    reads.clear()
    for path in candidates:
        name = path.name.split(".")[0]
        modules(name)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                module = imp.load_dynamic(name, str(path))
        except ImportError:
            continue
        assert isinstance(module, types.ModuleType) and sys.modules[name] is module
        assert reads == {}
        return
    pytest.skip("no loadable extension module in lib-dynload")


def test_reload_recompiles_only_changed_source(
    imp: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: Callable[[str], None],
    reads: dict[str, int],
    compiles: list[str],
) -> None:
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    source = tmp_path / "imp_reload.py"
    size = _write_source(source, 100)
    modules("imp_reload")
    module = imp.load_source("imp_reload", str(source))
    with pytest.raises(ModuleNotFoundError):
        imp.reload(module)
    monkeypatch.syspath_prepend(str(tmp_path))
    pyc = imp.cache_from_source(str(source))
    reads.clear()
    compiles.clear()
    assert imp.reload(module) is module
    assert reads == {pyc: Path(pyc).stat().st_size}
    assert compiles == []
    stale = Path(pyc).stat().st_size
    with source.open("a") as handle:
        handle.write("changed = True\n")
    reads.clear()
    compiles.clear()
    assert imp.reload(module) is module
    assert module.changed is True
    assert reads == {pyc: stale, str(source): size + len("changed = True\n")}
    assert compiles == [str(source)]


def test_new_module(imp: Any) -> None:
    module = imp.new_module("imp_new_module")
    assert type(module) is types.ModuleType
    assert module.__name__ == "imp_new_module"
    assert "imp_new_module" not in sys.modules


def test_magic_and_tag_return_existing_objects(imp: Any) -> None:
    assert imp.get_magic() is importlib.util.MAGIC_NUMBER
    assert imp.get_tag() is sys.implementation.cache_tag


def test_get_suffixes_builds_a_fresh_list(imp: Any) -> None:
    machinery = imp.machinery
    first, second = imp.get_suffixes(), imp.get_suffixes()
    assert first == second and first is not second
    expected = len(machinery.EXTENSION_SUFFIXES + machinery.SOURCE_SUFFIXES)
    assert len(first) == expected + len(machinery.BYTECODE_SUFFIXES)
    assert {code for _, _, code in first} == {imp.C_EXTENSION, imp.PY_SOURCE, imp.PY_COMPILED}


def test_cache_paths_are_string_work(imp: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    stats: list[Any] = []
    monkeypatch.setattr(imp.os, "stat", lambda *args, **kwargs: stats.append(args))
    source = "/no/such/directory/" + "deep/" * 1000 + "module.py"
    cached = imp.cache_from_source(source)
    assert cached == importlib.util.cache_from_source(source)
    assert imp.source_from_cache(cached) == source
    assert "__pycache__" in cached and imp.get_tag() in cached
    assert stats == []


def test_import_lock(imp: Any) -> None:
    assert imp.lock_held() is False
    imp.acquire_lock()
    try:
        assert imp.lock_held() is True
    finally:
        imp.release_lock()
    assert imp.lock_held() is False
    held, release, attempting, acquired = (threading.Event() for _ in range(4))

    def hold() -> None:
        imp.acquire_lock()
        held.set()
        release.wait(30)
        imp.release_lock()

    def wait() -> None:
        attempting.set()
        imp.acquire_lock()
        acquired.set()
        imp.release_lock()

    holder, waiter = threading.Thread(target=hold), threading.Thread(target=wait)
    try:
        holder.start()
        assert held.wait(30)
        assert imp.lock_held() is True
        waiter.start()
        assert attempting.wait(30)
        assert not acquired.wait(0.2)
        release.set()
        assert acquired.wait(30)
    finally:
        release.set()
        for thread in (holder, waiter):
            if thread.ident is not None:
                thread.join(30)
    assert not holder.is_alive() and not waiter.is_alive()
    assert imp.lock_held() is False


def test_null_importer(imp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checks: list[str] = []
    original = imp.os.path.isdir
    monkeypatch.setattr(imp.os.path, "isdir", lambda p: checks.append(p) or original(p))
    importer = imp.NullImporter(str(tmp_path / "missing"))
    assert checks == [str(tmp_path / "missing")]
    assert importer.find_module("anything") is None
    with pytest.raises(ImportError):
        imp.NullImporter("")
    with pytest.raises(ImportError):
        imp.NullImporter(str(tmp_path))


def test_builtin_and_frozen_tables(imp: Any, modules: Callable[[str], None]) -> None:
    assert imp.is_builtin("sys") == -1
    assert imp.is_builtin("errno") == 1
    assert imp.is_builtin("imp") == 0
    assert all(imp.is_builtin(name) for name in sys.builtin_module_names)
    assert imp.is_frozen("__hello__") is True
    assert imp.is_frozen("imp") is False
    assert imp.init_builtin("imp_no_such_builtin") is None
    modules("errno")
    errno = imp.init_builtin("errno")
    assert isinstance(errno, types.ModuleType) and errno.ENOENT == 2
    assert imp.init_frozen("imp_no_such_frozen") is None
    modules("__hello__")
    with redirect_stdout(io.StringIO()):
        hello = imp.init_frozen("__hello__")
    assert isinstance(hello, types.ModuleType) and hello.initialized is True


@pytest.mark.parametrize("index", [0, 1])
def test_examples(tmp_path: Path, index: int) -> None:
    text = PAGE.read_text()
    blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
    assert len(blocks) == 2
    if index == 0 and sys.version_info >= (3, 12):
        pytest.skip("the imp example needs Python 3.10 or 3.11")
    line = text[: text.index(blocks[index])].count("\n") + 1
    result = subprocess.run(
        [sys.executable, "-W", "ignore::DeprecationWarning", "-c", blocks[index]],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"{PAGE}:{line}: {result.stderr}"
