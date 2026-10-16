"""Tests for docs/versions/py315.md, and the garbage collector note in py314.md.

The page prices what 3.15 added or changed, so most claims here are settled on
3.15 by observation: whether a module ran, whether a name still holds a proxy,
how often a value is hashed, what an object's identity is, and what a fresh
interpreter reports. Claims about how 3.15 differs from earlier releases are
checked on both sides of the boundary, so the CI matrix holds each side to it.
Allocation is measured with `tracemalloc` in a child process, away from any
test-runner threads, at ratios far from the boundary being asserted.

Measurement scope:

* Lazy imports use a module written to the test's directory that prints when
  it runs. `lazy import` and `lazy from ... import` leave it out of
  `sys.modules` and print nothing; the first attribute access runs it once and
  rebinds that one name from `types.LazyImportType` to the module, while a
  second lazily bound name stays a proxy until it is used. A recording finder
  on `sys.meta_path` is asked for the module zero times before first use and
  once at it. A missing module
  raises `ImportError` at first use, not at the import line. `lazy` inside a
  function, a class body and a `try` block is a `SyntaxError` from
  `compile()`. `__lazy_modules__` makes a plain import lazy on 3.15 and is
  ignored before it; `-X lazy_imports=all` and `PYTHON_LAZY_IMPORTS=all` make
  a plain import lazy.
* `frozendict`: a value whose `__hash__` counts calls is hashed once by the
  first `hash()` and not again by the second. A key whose `__hash__` counts
  calls is hashed once per lookup in a 10-item and a 100,000-item
  frozendict. `copy()` and `frozendict(fd)` return `fd`; `frozendict(d)` of a
  dict is a separate object unaffected by a later change to `d`. It is not a
  `dict` subclass and works as a dict key.
* `sentinel`: `copy.copy()`, `copy.deepcopy()` and a deep copy of a list
  holding one all return the same object.
* Comprehension unpacking is compared with `itertools.chain.from_iterable`
  over lists, sets and dicts. The generator form is fed by a generator that
  records each inner iterable it hands out: after the first item only the
  first has been taken, and after the third item only two.
* `take_bytes()` on a 16 MiB `bytearray` allocated at its exact size peaks
  under 4 KiB, against more than 16 MiB for `bytes(buf)`, and leaves the
  buffer empty.
* `cProfile.Profile is profiling.tracing.Profile`; importing `profile` in a
  fresh process records a `DeprecationWarning`. The six `math.integer`
  functions are the `math` objects, and `re.prefixmatch is re.match`.
* A fresh 3.15 process without `PYTHONUTF8` reports `sys.flags.utf8_mode == 1`
  and opens a file as `utf-8`; with `-X utf8=0` the flag is 0. With
  `LC_ALL=C`, `encoding="locale"` opens a file in `locale.getencoding()`, which
  on Linux is ASCII rather than UTF-8 while UTF-8 mode is on.
* Base32 and Base85: each `base64` function calls its `binascii` counterpart
  once (a counting wrapper). On 1,000,000 random bytes each encoder and
  decoder peaks under 1.25 times its output on 3.15; before 3.15
  `b85encode` peaks over 10 times its output (34 times measured on 3.11 and
  3.14).
* `Popen.wait(timeout=30)` on a child that sleeps 1 s calls `time.sleep`
  zero times on 3.15 where `subprocess` found pidfd or kqueue support and on
  Windows, and more than zero times otherwise, which includes every POSIX run
  before 3.15.
* A fresh interpreter's `gc.get_threshold()` is `(2000, 10, 10)` on 3.13,
  3.14.5 and later, and 3.15, and has a zero third threshold on 3.14.0 to
  3.14.4, the incremental collector's setting. `sys._jit.is_enabled()` is
  false without `PYTHON_JIT`, and with `PYTHON_JIT=1` equals
  `sys._jit.is_available()`, true on the uv build of 3.15.0 used locally.
* Every removed API in the page's table is absent on 3.15 and present on the
  earlier supported versions.
* Every fenced Python block runs in its own subprocess on 3.15, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That the GC revert was made for memory pressure, and that the incremental
  collector shipped in exactly 3.14.0 to 3.14.4: both are read from the 3.15
  What's New. The threshold check is a proxy for which collector runs.
* That no bound on the site depends on the JIT, and that the JIT is upgraded:
  a statement of scope and a release note, not a measurement.
* The kqueue path of `Popen.wait()` on macOS and the BSDs, and the fallback
  loop on a Linux kernel older than 5.3, run only where those exist; Windows
  is checked only for making no `time.sleep` calls.
* The time and space rows that restate a bound, such as O(1) average lookup
  or O(n) construction, are the owning pages' claims and tested there. The
  lazy-import first-use row is the cost of a normal import by definition.
* End-of-life dates come from PEP 790.
* What trimming an over-allocated buffer costs in `take_bytes()`. It is a
  `realloc` to a smaller size, which `tracemalloc` reports as a new block and
  whose cost belongs to the platform allocator: on glibc a 16 MiB buffer
  grown by 4 KiB appends took 20 us to 0.9 ms against 0.7 to 4 ms for
  `bytes(buf)`, too close under load to assert a ratio.
"""

from __future__ import annotations

import builtins
import copy
import itertools
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "versions" / "py315.md"
EXPECTED_BLOCKS = 7

ON_315 = sys.version_info >= (3, 15)
requires_315 = pytest.mark.skipif(not ON_315, reason="version: added in Python 3.15")


def run_python(
    source: str,
    cwd: pathlib.Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run source as a script in a fresh interpreter."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, *args, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=env,
        check=False,
    )


def clean_env(*drop: str) -> dict[str, str]:
    env = dict(os.environ)
    for name in drop:
        env.pop(name, None)
    return env


def write_probe(directory: pathlib.Path) -> None:
    (directory / "probe_mod.py").write_text('print("LOADED")\nx = 1\ny = 2\n', encoding="utf-8")


@requires_315
class TestLazyImportsDeferLoading:
    """`lazy import m` | O(1): binds a proxy; the module is not located or run.
    First use costs a normal import and replaces the proxy in the globals; later
    uses are ordinary lookups. A finder on `sys.meta_path` records every
    lookup, so the test sees that none happens before first use."""

    def test_lazy_import_runs_nothing_until_first_use(self, tmp_path: pathlib.Path) -> None:
        write_probe(tmp_path)
        result = run_python(
            """
            lazy import probe_mod
            import sys
            print("before", "probe_mod" in sys.modules)
            probe_mod.x
            print("after", "probe_mod" in sys.modules)
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split("\n")[:3] == ["before False", "LOADED", "after True"]

    def test_first_use_rebinds_only_that_name(self, tmp_path: pathlib.Path) -> None:
        write_probe(tmp_path)
        result = run_python(
            """
            lazy import probe_mod
            lazy from probe_mod import y
            import types
            g = globals()
            assert type(g["probe_mod"]) is types.LazyImportType
            probe_mod.x
            assert type(g["probe_mod"]) is types.ModuleType
            assert type(g["y"]) is types.LazyImportType
            assert y == 2
            assert type(g["y"]) is int
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.count("LOADED") == 1

    def test_no_finder_is_asked_until_first_use(self, tmp_path: pathlib.Path) -> None:
        write_probe(tmp_path)
        result = run_python(
            """
            import sys

            class Recorder:
                asked = []

                @classmethod
                def find_spec(cls, name, path=None, target=None):
                    cls.asked.append(name)
                    return None

            sys.meta_path.insert(0, Recorder)
            lazy import probe_mod
            print("before", Recorder.asked.count("probe_mod"))
            probe_mod.x
            print("after", Recorder.asked.count("probe_mod"))
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split("\n")[:3] == ["before 0", "LOADED", "after 1"]

    def test_a_missing_module_fails_at_first_use(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            lazy import no_such_module_for_this_test
            print("bound")
            try:
                no_such_module_for_this_test.x
            except ImportError:
                print("failed at use")
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["bound", "failed", "at", "use"]

    @pytest.mark.parametrize(
        "source",
        [
            "def f():\n    lazy import json\n",
            "class C:\n    lazy import json\n",
            "try:\n    lazy import json\nexcept ImportError:\n    pass\n",
        ],
        ids=["function", "class", "try"],
    )
    def test_lazy_outside_module_scope_is_a_syntax_error(self, source: str) -> None:
        compile("lazy import json\n", "<module>", "exec")
        with pytest.raises(SyntaxError):
            compile(source, "<test>", "exec")

    @pytest.mark.parametrize(
        ("args", "env_value"),
        [(("-X", "lazy_imports=all"), None), ((), "all")],
        ids=["-X", "PYTHON_LAZY_IMPORTS"],
    )
    def test_global_mode_makes_plain_imports_lazy(
        self, tmp_path: pathlib.Path, args: tuple[str, ...], env_value: str | None
    ) -> None:
        write_probe(tmp_path)
        env = clean_env("PYTHON_LAZY_IMPORTS")
        if env_value is not None:
            env["PYTHON_LAZY_IMPORTS"] = env_value
        result = run_python(
            """
            import probe_mod
            import sys
            print("before", "probe_mod" in sys.modules)
            probe_mod.x
            """,
            tmp_path,
            *args,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split("\n")[:2] == ["before False", "LOADED"]


class TestLazyModulesVariable:
    """`__lazy_modules__` makes plain imports lazy on 3.15; older versions
    ignore it and import eagerly. Runs on every version."""

    def test_lazy_on_315_and_eager_before(self, tmp_path: pathlib.Path) -> None:
        write_probe(tmp_path)
        result = run_python(
            """
            __lazy_modules__ = ["probe_mod"]
            import probe_mod
            import sys
            print("before", "probe_mod" in sys.modules)
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        if ON_315:
            assert result.stdout.split("\n")[:1] == ["before False"]
        else:
            assert result.stdout.split("\n")[:2] == ["LOADED", "before True"]


class CountingHash:
    """A hashable value that counts its __hash__ calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __hash__(self) -> int:
        self.calls += 1
        return 12345

    def __eq__(self, other: object) -> bool:
        return self is other


@requires_315
class TestFrozendict:
    """`hash(fd)` is O(n) once and then cached; `copy()` returns the same
    object; construction copies a dict but returns a frozendict as is; a
    lookup hashes the key once whatever the size."""

    def test_hash_is_computed_once(self) -> None:
        frozendict: Any = builtins.frozendict  # pyright: ignore[reportAttributeAccessIssue]
        value = CountingHash()
        fd = frozendict(a=value, b=1)

        first = hash(fd)
        after_first = value.calls
        second = hash(fd)

        assert after_first == 1
        assert value.calls == 1, "the second hash() recomputed the item hashes"
        assert first == second

    def test_copy_and_reconstruction_return_the_same_object(self) -> None:
        frozendict: Any = builtins.frozendict  # pyright: ignore[reportAttributeAccessIssue]
        fd = frozendict(a=1)
        assert fd.copy() is fd
        assert frozendict(fd) is fd

    def test_construction_from_a_dict_copies_it(self) -> None:
        frozendict: Any = builtins.frozendict  # pyright: ignore[reportAttributeAccessIssue]
        source = {"a": 1}
        fd = frozendict(source)
        source["b"] = 2
        assert dict(fd) == {"a": 1}

    def test_a_lookup_hashes_the_key_once_at_any_size(self) -> None:
        frozendict: Any = builtins.frozendict  # pyright: ignore[reportAttributeAccessIssue]
        for size in (10, 100_000):
            key = CountingHash()
            fd = frozendict({**{i: i for i in range(size)}, key: "found"})
            key.calls = 0
            assert fd[key] == "found"
            assert key.calls == 1, f"fd[key] hashed the key {key.calls} times at {size}"
            assert key in fd
            assert key.calls == 2, f"key in fd hashed the key again {key.calls - 1} times"

    def test_it_is_a_hashable_mapping_not_a_dict(self) -> None:
        frozendict: Any = builtins.frozendict  # pyright: ignore[reportAttributeAccessIssue]
        fd = frozendict(x=1, y=2)
        assert not isinstance(fd, dict)
        assert {fd: "v"}[frozendict(y=2, x=1)] == "v"


@requires_315
class TestSentinel:
    """Copying a sentinel returns the sentinel itself."""

    def test_copies_are_the_same_object(self) -> None:
        sentinel: Any = builtins.sentinel  # pyright: ignore[reportAttributeAccessIssue]
        missing = sentinel("MISSING")
        assert copy.copy(missing) is missing
        assert copy.deepcopy(missing) is missing
        assert copy.deepcopy([missing])[0] is missing
        assert repr(missing) == "MISSING"


@requires_315
class TestUnpackingInComprehensions:
    """The new forms give the same result as `chain.from_iterable`, and the
    generator form takes the next inner iterable only when the current one is
    exhausted."""

    LISTS = [[1, 2], [3], [], [4, 5, 6]]

    def evaluate(self, expression: str, **names: Any) -> Any:
        return eval(expression, {}, names)

    def test_list_set_and_dict_forms_match_chain(self) -> None:
        assert self.evaluate("[*it for it in its]", its=self.LISTS) == list(
            itertools.chain.from_iterable(self.LISTS)
        )
        sets = [{1, 2}, {2, 3}]
        assert self.evaluate("{*s for s in its}", its=sets) == {1, 2, 3}
        dicts = [{"a": 1}, {"b": 2}, {"a": 3}]
        assert self.evaluate("{**d for d in its}", its=dicts) == {"a": 3, "b": 2}

    def test_generator_form_takes_one_inner_iterable_at_a_time(self) -> None:
        handed_out: list[int] = []

        def outer() -> Iterator[list[int]]:
            for index, inner in enumerate(self.LISTS):
                handed_out.append(index)
                yield inner

        flat = self.evaluate("(*it for it in its)", its=outer())
        assert handed_out == []
        assert next(flat) == 1
        assert handed_out == [0]
        assert next(flat) == 2
        assert next(flat) == 3
        assert handed_out == [0, 1]
        assert list(flat) == [4, 5, 6]


TAKE_BYTES_PEAKS = """
import tracemalloc
size = 16 * 1024 * 1024
buffer = bytearray(size)
tracemalloc.start()
data = buffer.take_bytes()
take_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
assert len(data) == size and len(buffer) == 0
other = bytearray(size)
tracemalloc.start()
copied = bytes(other)
copy_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print(take_peak, copy_peak)
"""


@requires_315
class TestTakeBytesHandsOverTheBuffer:
    """`buf.take_bytes()` | O(1) | O(1): the new bytes takes over the buffer,
    against `bytes(buf)`, which copies."""

    def test_taking_the_whole_buffer_allocates_nothing(self, tmp_path: pathlib.Path) -> None:
        result = run_python(TAKE_BYTES_PEAKS, tmp_path)
        assert result.returncode == 0, result.stderr
        take_peak, copy_peak = map(int, result.stdout.split())
        assert take_peak < 4096, f"take_bytes() peaked at {take_peak} bytes"
        assert copy_peak > 16 * 1024 * 1024


@requires_315
class TestRenamedAndAliasedApis:
    """cProfile is an alias of profiling.tracing, profile is deprecated, and
    the math.integer and re.prefixmatch names are the existing objects."""

    def test_cprofile_is_profiling_tracing(self) -> None:
        import cProfile

        import profiling.tracing  # type: ignore[import-not-found]

        assert cProfile.Profile is profiling.tracing.Profile

    def test_importing_profile_warns(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import warnings
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                import profile
            print([w.category.__name__ for w in caught])
            """,
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert "DeprecationWarning" in result.stdout

    def test_math_integer_functions_are_the_math_functions(self) -> None:
        import math
        import math.integer  # type: ignore[import-not-found]

        for name in ("comb", "factorial", "gcd", "isqrt", "lcm", "perm"):
            assert getattr(math.integer, name) is getattr(math, name), name

    def test_prefixmatch_is_match(self) -> None:
        assert re.prefixmatch is re.match  # pyright: ignore[reportAttributeAccessIssue]
        pattern = re.compile("ab")
        assert pattern.prefixmatch("abc").span() == pattern.match("abc").span()  # type: ignore[union-attr]


@requires_315
class TestUtf8IsTheDefault:
    """UTF-8 mode is on by default, so open() without an encoding uses UTF-8;
    -X utf8=0 turns it off."""

    SOURCE = """
    import sys
    with open(sys.argv[0]) as handle:
        print(sys.flags.utf8_mode, handle.encoding)
    """

    def test_utf8_mode_is_on_without_any_setting(self, tmp_path: pathlib.Path) -> None:
        result = run_python(self.SOURCE, tmp_path, env=clean_env("PYTHONUTF8"))
        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["1", "utf-8"]

    def test_locale_encoding_still_follows_the_locale(self, tmp_path: pathlib.Path) -> None:
        env = clean_env("PYTHONUTF8")
        env["LC_ALL"] = "C"
        result = run_python(
            """
            import locale, sys
            with open(sys.argv[0], encoding="locale") as handle:
                print(sys.flags.utf8_mode, handle.encoding, locale.getencoding())
            """,
            tmp_path,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        mode, chosen, current = result.stdout.split()
        assert mode == "1"
        assert chosen == current
        if sys.platform == "linux":
            assert chosen.lower() != "utf-8", "glibc's C locale is ASCII"

    def test_it_can_be_turned_off(self, tmp_path: pathlib.Path) -> None:
        result = run_python(self.SOURCE, tmp_path, "-X", "utf8=0", env=clean_env("PYTHONUTF8"))
        assert result.returncode == 0, result.stderr
        assert result.stdout.split()[0] == "0"


CODEC_PEAKS = """
import base64, os, sys, tracemalloc
data = os.urandom(1_000_000)
pairs = [("b85encode", "b85decode"), ("a85encode", "a85decode"),
         ("b32encode", "b32decode"), ("b32hexencode", "b32hexdecode")]
if sys.version_info >= (3, 13):
    pairs.append(("z85encode", "z85decode"))
for encode, decode in pairs:
    encoded = getattr(base64, encode)(data)
    for name, func, arg, out_len in [(encode, getattr(base64, encode), data, len(encoded)),
                                     (decode, getattr(base64, decode), encoded, len(data))]:
        tracemalloc.start()
        func(arg)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        print(name, peak / out_len)
"""


class TestBase32AndBase85InC:
    """The Base32 and Base85 codecs call binascii, and allocate only their
    output on 3.15; before 3.15 b85encode builds far larger intermediates."""

    @requires_315
    @pytest.mark.parametrize(
        ("name", "target"),
        [
            ("b85encode", "b2a_base85"),
            ("b85decode", "a2b_base85"),
            ("a85encode", "b2a_ascii85"),
            ("a85decode", "a2b_ascii85"),
            ("b32encode", "b2a_base32"),
            ("b32decode", "a2b_base32"),
        ],
    )
    def test_base64_calls_binascii(
        self, monkeypatch: pytest.MonkeyPatch, name: str, target: str
    ) -> None:
        import base64
        import binascii

        original = getattr(binascii, target)
        calls: list[str] = []

        def counting(*args: Any, **kwargs: Any) -> Any:
            calls.append(target)
            return original(*args, **kwargs)

        monkeypatch.setattr(binascii, target, counting)
        argument = (
            b"hello world!"
            if "encode" in name
            else getattr(base64, name[:3] + "encode")(b"hello world!")
        )
        getattr(base64, name)(argument)
        assert calls == [target]

    def test_peak_allocation_by_version(self, tmp_path: pathlib.Path) -> None:
        result = run_python(CODEC_PEAKS, tmp_path)
        assert result.returncode == 0, result.stderr
        ratios = {
            name: float(ratio)
            for name, ratio in (line.split() for line in result.stdout.splitlines())
        }
        if ON_315:
            heavy = {name: ratio for name, ratio in ratios.items() if ratio >= 1.25}
            assert not heavy, f"peak over 1.25x the output: {heavy}"
        else:
            assert ratios["b85encode"] > 10, ratios


class TestPopenWaitDoesNotPoll:
    """`wait(timeout=...)` blocks on a pidfd or kqueue on 3.15 instead of a
    sleep loop; Windows waited on the process handle before 3.15 too."""

    def test_sleep_calls_by_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[float] = []
        real_sleep = time.sleep

        def counting_sleep(delay: float) -> None:
            calls.append(delay)
            real_sleep(delay)

        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.0)"])
        monkeypatch.setattr(time, "sleep", counting_sleep)
        try:
            assert process.wait(timeout=30) == 0
        finally:
            monkeypatch.undo()
            if process.poll() is None:
                process.kill()
                process.wait()

        event_driven = ON_315 and (
            getattr(subprocess, "_CAN_USE_PIDFD_OPEN", False)
            or getattr(subprocess, "_CAN_USE_KQUEUE", False)
        )
        if event_driven or sys.platform == "win32":
            assert calls == []
        else:
            assert calls, "wait(timeout=...) made no sleep calls on the polling path"


class TestGarbageCollectorAndJit:
    """3.15 and 3.14.5+ use the generational collector, as 3.13 did; 3.14.0
    to 3.14.4 ran the incremental collector. The JIT is off by default."""

    def test_default_thresholds_by_version(self, tmp_path: pathlib.Path) -> None:
        result = run_python("import gc; print(*gc.get_threshold())", tmp_path)
        assert result.returncode == 0, result.stderr
        thresholds = tuple(map(int, result.stdout.split()))
        if (3, 14, 0) <= sys.version_info[:3] < (3, 14, 5):
            assert thresholds[2] == 0, thresholds
        elif sys.version_info >= (3, 13):
            assert thresholds == (2000, 10, 10)

    @requires_315
    def test_jit_is_off_by_default(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            "import sys; print(sys._jit.is_enabled())", tmp_path, env=clean_env("PYTHON_JIT")
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False"

    @requires_315
    def test_python_jit_turns_it_on_where_built(self, tmp_path: pathlib.Path) -> None:
        env = clean_env("PYTHON_JIT")
        env["PYTHON_JIT"] = "1"
        result = run_python(
            "import sys; print(sys._jit.is_available(), sys._jit.is_enabled())", tmp_path, env=env
        )
        assert result.returncode == 0, result.stderr
        available, enabled = result.stdout.split()
        assert enabled == available


REMOVED_ATTRIBUTES = [
    ("glob", "glob", "glob0"),
    ("glob", "glob", "glob1"),
    ("http.server", "http.server", "CGIHTTPRequestHandler"),
    ("pathlib", "pathlib.PurePath", "is_reserved"),
    ("platform", "platform", "java_ver"),
    ("types", "types.CodeType", "co_lnotab"),
    ("importlib.abc", "importlib.abc.Loader", "load_module"),
    ("zipimport", "zipimport.zipimporter", "load_module"),
    ("wave", "wave.Wave_read", "getmark"),
    ("wave", "wave.Wave_write", "setmark"),
    ("wave", "wave.Wave_read", "getmarkers"),
    ("typing", "typing", "no_type_check_decorator"),
    ("ctypes", "ctypes", "SetPointerType"),
]


class TestRemovedApis:
    """Every API in the page's Removed table is gone on 3.15 and present on
    the earlier supported versions."""

    @pytest.mark.parametrize(("module", "owner", "name"), REMOVED_ATTRIBUTES)
    def test_attribute_presence_by_version(self, module: str, owner: str, name: str) -> None:
        import importlib

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            importlib.import_module(module)
            obj: Any = importlib.import_module(owner.split(".")[0])
            for part in owner.split(".")[1:]:
                obj = getattr(obj, part)
            present = hasattr(obj, name)
        assert present is not ON_315, f"{owner}.{name} present={present}"

    @pytest.mark.parametrize("module", ["sre_compile", "sre_constants", "sre_parse"])
    def test_sre_modules_by_version(self, module: str) -> None:
        import importlib

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if ON_315:
                with pytest.raises(ModuleNotFoundError):
                    importlib.import_module(module)
            else:
                importlib.import_module(module)


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
    """Each block runs in its own subprocess on 3.15 and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @requires_315
    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_python(source, workdir, env=clean_env("PYTHONUTF8"))
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    @requires_315
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "config.copy() is config" in s)
        mutated = source.replace("config.copy() is config", "config.copy() is not config", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert run_python(mutated, tmp_path).returncode != 0
