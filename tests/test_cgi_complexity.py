"""Tests for docs/stdlib/cgi.md.

The page prices `FieldStorage` as one parse when it is built and a scan of the
field list on every lookup by name. The scans are settled by counting
comparisons: field names are replaced by a `str` subclass whose `__eq__`
counts, which Python calls whichever side of `==` it is on. Memory is settled
by `tracemalloc` peaks, the quadratic paths by comparison counts and by timing
at a fixed line length, and the remaining rows by observation. The module
exists on Python 3.10 to 3.12, so every test that touches it takes the `cgi`
fixture, which skips from 3.13; run them with a 3.12 interpreter.

Measurement scope:

* A URL-encoded body's traced peak while building a `FieldStorage` grows more
  than 8x from a 1 MiB body to a 16 MiB one. A multipart upload's peak at
  16 MiB is under 2x its peak at 1 MiB, for an upload of 100-byte lines and
  for one with no line breaks, and the whole upload is in the part's file;
  on 3.12.15 both peaks are under 150 KB. Building a
  multipart form of 1,000, 4,000 and 16,000 one-character fields costs under
  8x per 4x step, in a timing test, against 16x for a quadratic.
* Construction reads the whole stream: the stream is at its end afterwards.
  `FieldStorage` parses a POST's query string with its body, URL-encoded or
  multipart, and `parse()` with a URL-encoded body.
  A part of 1,000 bytes stays in memory and one of 1,001 goes to the file
  `make_file()` returns, observed through a subclass that records the call.
* `form[key]` and `getvalue()`, `getfirst()` and `getlist()` make exactly f
  comparisons, plus one for the `in` check the three methods start with when
  the name is first; `key in form` makes one comparison for the first field
  and f for the last; f is 10 and 1,000. `getfirst()` is observed to build
  the list of all 50 matches of a repeated name. `keys()` returns a new list
  on every call, and `len()` and iteration are observed to call it.
* `.value` of a form is its `.list`; of a file part, equal bytes that are a
  new object on every access, each from a `read()` of the part's file, which
  is left at offset 0.
* `parse_multipart()` over f distinct names makes at least f² name
  comparisons, at f = 100 and f = 400. A `str` boundary raises
  `AttributeError`, as does `parse()` given a multipart body.
* `parse_header()` on a line of 1,000, 4,000 and 16,000 quoted `;` costs more
  than 8x per 4x step, against 4x for a linear parse; at the largest size the
  same length with one `;` is over 100x cheaper.
* `maxlen` raises `ValueError` with no read from the stream, through both
  `FieldStorage` and `parse()`. `max_num_fields` raises `ValueError` for a
  URL-encoded and for a multipart form with one field too many.
* `print_form()` over f distinct names makes at least f² comparisons, at
  f = 30 and f = 300. The other `print_*` helpers are checked by their output;
  `test()` runs in a subprocess given a dictionary for `environ`: the form it
  prints comes from the process's own environment, the environment it prints
  from the dictionary, and it leaves `maxlen` at 50.
* Importing the module on 3.10 emits no `DeprecationWarning`, on 3.11 and
  3.12 it does, and from 3.13 it raises `ModuleNotFoundError`.
* Every fenced Python block runs in its own subprocess. On 3.12 and earlier
  all of them pass; from 3.13 the ones importing `cgi` are asserted to fail
  with `ModuleNotFoundError` and the rest to pass. A mutated assertion in one
  of them is asserted to fail.

Not settled here:

* Pricing name comparison, environment-name comparison, one part's header
  parsing and the multipart preamble at O(1) is a cost-model choice; name
  length, header size and preamble length are not varied.
* The O(o) bounds of `print_exception()`, `print_directory()` and
  `print_arguments()`, and O(1) for `print_environ_usage()`, are read from
  Lib/cgi.py: each formats what it prints once, from a fixed text for the
  last. `print_environ()`'s sort is read from source, not timed.
* That `make_file()` returns an anonymous temporary file is read from
  Lib/cgi.py; the test overrides it rather than inspecting the file system.
* A multipart part whose own type is URL-encoded goes to `read_urlencoded()`
  in Lib/cgi.py, which reads it whole into memory; the page scopes the
  multipart bounds to exclude it, and it is not measured.
* Nested multipart parts, `limit`, `outerboundary`, `strict_parsing` and
  non-UTF-8 encodings are not varied.
* `log`, `initlog`, `dolog`, `nolog`, `closelog`, `logfile`, `logfp`,
  `valid_boundary`, `FieldStorageClass`, `bufsize`, the `read_*` and
  `skip_lines` methods, `MiniFieldStorage`'s other placeholder attributes and
  the `BytesIO`, `StringIO` and `TextIOWrapper` classes Lib/cgi.py imports
  are outside the module's documentation; the page does not cover them, and
  the audit lists them under needs-classification.
"""

from __future__ import annotations

import contextlib
import gc
import html as html_module
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
import urllib.parse
import warnings
from collections.abc import Callable, Iterator
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "cgi.md"
EXPECTED_BLOCKS = 9
MIB = 1024 * 1024
REMOVED = sys.version_info >= (3, 13)


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


@pytest.fixture
def cgi() -> Iterator[Any]:
    if REMOVED:
        pytest.skip("version: cgi was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        module: Any = importlib.import_module("cgi")
    saved = module.maxlen
    yield module
    module.maxlen = saved


class CountingName(str):
    """A field name that counts the `==` comparisons it takes part in."""

    calls = 0

    def __eq__(self, other: object) -> bool:
        CountingName.calls += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


def _urlencoded_environ(body: bytes) -> dict[str, str]:
    return {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "CONTENT_LENGTH": str(len(body)),
    }


def _multipart(fields: list[tuple[str, str]], upload: bytes | None = None) -> bytes:
    parts = [
        f'--B\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields
    ]
    if upload is not None:
        parts.append(
            b'--B\r\nContent-Disposition: form-data; name="up"; filename="up.bin"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n" + upload + b"\r\n"
        )
    parts.append(b"--B--\r\n")
    return b"".join(parts)


def _multipart_environ(body: bytes) -> dict[str, str]:
    return {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "multipart/form-data; boundary=B",
        "CONTENT_LENGTH": str(len(body)),
    }


def _query_form(cgi: Any, fields: int) -> Any:
    query = "&".join(f"k{i}=v" for i in range(fields))
    return cgi.FieldStorage(environ={"REQUEST_METHOD": "GET", "QUERY_STRING": query})


def _count_names(form: Any) -> None:
    for item in form.list:
        item.name = CountingName(item.name)


class TestImport:
    """Version Notes: a warning on import from 3.11, removed in 3.13."""

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="version: warns from Python 3.11")
    def test_importing_it_on_3_10_does_not_warn(self) -> None:
        sys.modules.pop("cgi", None)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            importlib.import_module("cgi")

    @pytest.mark.skipif(
        not (3, 11) <= sys.version_info < (3, 13), reason="version: warns on 3.11 and 3.12"
    )
    def test_importing_it_warns(self) -> None:
        sys.modules.pop("cgi", None)
        with pytest.warns(DeprecationWarning, match="cgi"):
            importlib.import_module("cgi")

    @pytest.mark.skipif(not REMOVED, reason="version: present before Python 3.13")
    def test_importing_it_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("cgi")


class TestConstructionParsesTheRequest:
    """`FieldStorage(...)` is O(n + f): it reads and parses the whole request
    when built. A URL-encoded body is held in memory, so its peak follows n;
    a multipart upload goes to a file, so its peak does not."""

    def test_construction_reads_the_whole_stream(self, cgi: Any) -> None:
        body = b"a=1&b=2"
        stream = io.BytesIO(body)
        form = cgi.FieldStorage(stream, environ=_urlencoded_environ(body))

        assert stream.tell() == len(body)
        assert [item.name for item in form.list] == ["a", "b"]

    def test_a_post_parses_its_query_string_too(self, cgi: Any) -> None:
        body = b"a=1"
        environ = {**_urlencoded_environ(body), "QUERY_STRING": "q=2"}
        form = cgi.FieldStorage(io.BytesIO(body), environ=environ)
        assert [(item.name, item.value) for item in form.list] == [("a", "1"), ("q", "2")]

        body = _multipart([("a", "1")])
        environ = {**_multipart_environ(body), "QUERY_STRING": "q=2"}
        form = cgi.FieldStorage(io.BytesIO(body), environ=environ)
        assert (form.getvalue("a"), form.getvalue("q")) == ("1", "2")

        body = b"a=1"
        environ = {**_urlencoded_environ(body), "QUERY_STRING": "q=2"}
        assert cgi.parse(io.BytesIO(body), environ=environ) == {"a": ["1"], "q": ["2"]}

    def test_a_urlencoded_body_is_held_in_memory(self, cgi: Any) -> None:
        def build(size: int) -> int:
            body = b"a=" + b"x" * size
            environ = _urlencoded_environ(body)
            return peak_bytes(lambda: cgi.FieldStorage(io.BytesIO(body), environ=environ))

        small, large = build(MIB), build(16 * MIB)
        assert large > 8 * small, (small, large)

    @pytest.mark.parametrize("line", [b"x" * 99 + b"\n", b"x" * 100], ids=["lines", "one-line"])
    def test_an_upload_does_not_reach_memory(self, cgi: Any, line: bytes) -> None:
        def build(size: int) -> int:
            upload = line * (size // len(line))
            body = _multipart([("a", "b")], upload)
            environ = _multipart_environ(body)
            forms: list[Any] = []
            peak = peak_bytes(
                lambda: forms.append(cgi.FieldStorage(io.BytesIO(body), environ=environ))
            )
            assert forms[0]["up"].file.seek(0, io.SEEK_END) == len(upload)
            return peak

        small, large = build(MIB), build(16 * MIB)
        assert large < 2 * small, (small, large)

    def test_a_large_part_goes_to_make_file(self, cgi: Any) -> None:
        calls: list[int] = []

        class Recording(cgi.FieldStorage):
            def make_file(self) -> io.BytesIO:
                calls.append(1)
                return io.BytesIO()

        for size, expected in ((1000, 0), (1001, 1)):
            calls.clear()
            body = _multipart([], b"z" * size)
            form = Recording(io.BytesIO(body), environ=_multipart_environ(body))
            assert form["up"].value == b"z" * size
            assert len(calls) == expected, size

    @pytest.mark.timing
    def test_construction_is_linear_in_the_fields(self, cgi: Any) -> None:
        def cost(fields: int) -> float:
            body = _multipart([(f"k{i}", "v") for i in range(fields)])
            environ = _multipart_environ(body)
            return best_ns(lambda: cgi.FieldStorage(io.BytesIO(body), environ=environ), 3)

        times = [cost(fields) for fields in (1000, 4000, 16000)]
        ratios = [later / earlier for earlier, later in pairwise(times)]
        assert all(ratio < 8 for ratio in ratios), (times, ratios)


class TestLookupsScanTheForm:
    """`form[key]`, `getvalue()`, `getfirst()` and `getlist()` are O(f): each
    compares the key with every field's name. `key in form` stops at the first
    match. A dictionary would make one comparison."""

    @pytest.mark.parametrize("fields", [10, 1000])
    def test_each_lookup_compares_every_field(self, cgi: Any, fields: int) -> None:
        form = _query_form(cgi, fields)
        _count_names(form)

        for lookup in (form.__getitem__, form.getvalue, form.getfirst, form.getlist):
            CountingName.calls = 0
            lookup("k0")
            expected = fields if lookup == form.__getitem__ else fields + 1
            assert CountingName.calls == expected, lookup

        CountingName.calls = 0
        assert form.getvalue("missing") is None
        assert CountingName.calls == fields

    def test_in_stops_at_the_first_match(self, cgi: Any) -> None:
        form = _query_form(cgi, 1000)
        _count_names(form)

        CountingName.calls = 0
        assert "k0" in form
        assert CountingName.calls == 1

        CountingName.calls = 0
        assert "k999" in form
        assert CountingName.calls == 1000

    def test_a_repeated_name_returns_every_match(self, cgi: Any) -> None:
        form = cgi.FieldStorage(environ={"REQUEST_METHOD": "GET", "QUERY_STRING": "a=1&b=2&a=3"})
        assert [item.value for item in form["a"]] == ["1", "3"]
        assert form.getvalue("a") == ["1", "3"]
        assert form.getfirst("a") == "1"
        assert form.getlist("b") == ["2"]

    def test_getfirst_builds_every_match_before_taking_one(self, cgi: Any) -> None:
        built: list[Any] = []

        class Recording(cgi.FieldStorage):
            def __getitem__(self, key: str) -> Any:
                found = super().__getitem__(key)
                built.append(found)
                return found

        query = "&".join(["a=1"] * 50 + ["b=2"])
        form = Recording(environ={"REQUEST_METHOD": "GET", "QUERY_STRING": query})
        assert form.getfirst("a") == "1"
        assert len(built) == 1 and len(built[0]) == 50

    def test_keys_builds_a_new_list_for_len_and_iteration(
        self, cgi: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        form = cgi.FieldStorage(environ={"REQUEST_METHOD": "GET", "QUERY_STRING": "a=1&b=2&a=3"})
        assert form.keys() is not form.keys()
        assert sorted(form.keys()) == ["a", "b"]

        calls: list[int] = []
        original = form.keys

        def counting() -> list[str]:
            calls.append(1)
            return original()

        monkeypatch.setattr(form, "keys", counting)
        assert len(form) == 2
        assert sorted(iter(form)) == ["a", "b"]
        assert len(calls) == 2


class TestValue:
    """`.value` is O(1) for a form or a small part, and O(s) for a part held
    in a file, which is read again on every access."""

    def test_a_forms_value_is_its_field_list(self, cgi: Any) -> None:
        form = _query_form(cgi, 3)
        assert form.value is form.list

    def test_a_file_part_is_read_again_on_every_access(self, cgi: Any) -> None:
        upload = b"y" * 100_000
        body = _multipart([("title", "t")], upload)
        item = cgi.FieldStorage(io.BytesIO(body), environ=_multipart_environ(body))["up"]

        reads: list[int] = []
        backing = item.file

        class CountingFile:
            def seek(self, *args: Any) -> int:
                return backing.seek(*args)

            def read(self, *args: Any) -> bytes:
                reads.append(1)
                return backing.read(*args)

        item.file = CountingFile()
        first, second = item.value, item.value
        assert first == second == upload
        assert first is not second
        assert len(reads) == 2
        assert backing.tell() == 0
        assert item.list is None
        assert item.filename == "up.bin"

    def test_a_mini_field_storage_has_no_file(self, cgi: Any) -> None:
        field = cgi.MiniFieldStorage("a", "1")
        assert (field.name, field.value) == ("a", "1")
        assert field.filename is None and field.file is None
        assert field.list is None and field.type is None


class TestModuleLevelParsing:
    """`parse()` is `parse_qs()` over the query string or URL-encoded body,
    and fails on a multipart body. `parse_multipart()` is O(n + f·u): one
    `getlist()` per distinct name, each scanning every field."""

    def test_parse_matches_parse_qs(self, cgi: Any) -> None:
        query = "a=1&a=2&b=&c=3"
        assert cgi.parse(environ={"QUERY_STRING": query}) == urllib.parse.parse_qs(query)

        body = query.encode()
        parsed = cgi.parse(io.BytesIO(body), environ=_urlencoded_environ(body))
        assert parsed == urllib.parse.parse_qs(query)

    def test_parse_cannot_read_a_multipart_body(self, cgi: Any) -> None:
        body = _multipart([("a", "1")])
        with pytest.raises(AttributeError, match="decode"):
            cgi.parse(io.BytesIO(body), environ=_multipart_environ(body))

    def test_parse_multipart_needs_a_bytes_boundary(self, cgi: Any) -> None:
        body = _multipart([("a", "1"), ("a", "2")], b"data")
        result = cgi.parse_multipart(io.BytesIO(body), {"boundary": b"B"})
        assert result == {"a": ["1", "2"], "up": [b"data"]}

        with pytest.raises(AttributeError, match="decode"):
            cgi.parse_multipart(io.BytesIO(body), {"boundary": "B"})

    @pytest.mark.parametrize("fields", [100, 400])
    def test_parse_multipart_scans_the_form_per_name(
        self, cgi: Any, monkeypatch: pytest.MonkeyPatch, fields: int
    ) -> None:
        class Counting(cgi.FieldStorage):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                if self.name is not None:
                    self.name = CountingName(self.name)

        monkeypatch.setattr(cgi, "FieldStorage", Counting)
        body = _multipart([(f"k{i}", "v") for i in range(fields)])

        CountingName.calls = 0
        result = cgi.parse_multipart(io.BytesIO(body), {"boundary": b"B"})
        assert len(result) == fields
        assert CountingName.calls >= fields * fields, CountingName.calls


class TestParseHeader:
    """`parse_header()` is O(L·(p + 1)): each `;` can cost a pass over the whole
    line. Holding the length fixed and changing only the number of `;`
    separates it from a linear parse."""

    def test_it_splits_the_value_and_parameters(self, cgi: Any) -> None:
        assert cgi.parse_header('text/html; charset="utf-8"; q=1') == (
            "text/html",
            {"charset": "utf-8", "q": "1"},
        )
        assert cgi.parse_header('form-data; name="a;b"') == ("form-data", {"name": "a;b"})

    @pytest.mark.timing
    def test_separators_make_it_quadratic(self, cgi: Any) -> None:
        def cost(separators: int) -> float:
            line = 'form-data; name="' + "a;" * separators + '"'
            return best_ns(lambda: cgi.parse_header(line), 3)

        times = [cost(separators) for separators in (1000, 4000, 16000)]
        ratios = [later / earlier for earlier, later in pairwise(times)]
        assert all(ratio > 8 for ratio in ratios), (times, ratios)

        one = 'form-data; name="' + "a" * 32000 + '"'
        assert times[-1] > 100 * best_ns(lambda: cgi.parse_header(one)), times


class TestRequestLimits:
    """`maxlen` rejects a body by its Content-Length before reading it, and
    `max_num_fields` rejects a form with too many fields."""

    class CountingStream(io.BytesIO):
        def __init__(self, data: bytes) -> None:
            super().__init__(data)
            self.reads = 0

        def read(self, size: int | None = -1) -> bytes:
            self.reads += 1
            return super().read(size)

        def readline(self, size: int | None = -1) -> bytes:
            self.reads += 1
            return super().readline(size)

    def test_maxlen_raises_before_reading(self, cgi: Any) -> None:
        body = b"a=" + b"x" * 1000
        cgi.maxlen = 100

        stream = self.CountingStream(body)
        with pytest.raises(ValueError, match="Maximum content length exceeded"):
            cgi.FieldStorage(stream, environ=_urlencoded_environ(body))
        assert stream.reads == 0

        stream = self.CountingStream(body)
        with pytest.raises(ValueError, match="Maximum content length exceeded"):
            cgi.parse(stream, environ=_urlencoded_environ(body))
        assert stream.reads == 0

    def test_maxlen_is_unlimited_by_default(self, cgi: Any) -> None:
        assert cgi.maxlen == 0

    def test_max_num_fields_raises(self, cgi: Any) -> None:
        body = b"a=1&b=2&c=3"
        with pytest.raises(ValueError, match="Max number of fields exceeded"):
            cgi.FieldStorage(io.BytesIO(body), environ=_urlencoded_environ(body), max_num_fields=2)

        body = _multipart([("a", "1"), ("b", "2"), ("c", "3")])
        with pytest.raises(ValueError, match="Max number of fields exceeded"):
            cgi.FieldStorage(io.BytesIO(body), environ=_multipart_environ(body), max_num_fields=2)
        form = cgi.FieldStorage(
            io.BytesIO(body), environ=_multipart_environ(body), max_num_fields=3
        )
        assert len(form.list) == 3


class TestDebuggingHelpers:
    """`print_form()` is O(f·u + o): it looks each sorted name up, scanning
    the form every time. The other helpers print what the page says they do."""

    @pytest.mark.parametrize("fields", [30, 300])
    def test_print_form_scans_the_form_per_name(self, cgi: Any, fields: int) -> None:
        form = _query_form(cgi, fields)
        _count_names(form)

        CountingName.calls = 0
        with contextlib.redirect_stdout(io.StringIO()):
            cgi.print_form(form)
        assert CountingName.calls >= fields * fields, CountingName.calls

    def test_the_print_helpers_write_what_they_describe(self, cgi: Any) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cgi.print_environ({"B": "2", "A": "<1>"})
            cgi.print_directory()
            cgi.print_arguments()
            cgi.print_environ_usage()
            try:
                raise KeyError("<boom>")
            except KeyError:
                cgi.print_exception()
        html = output.getvalue()

        assert html.index("<DT> A <DD> &lt;1&gt;") < html.index("<DT> B <DD> 2")
        assert html_module.escape(os.getcwd()) in html
        assert repr(sys.argv) in html
        assert "<LI>QUERY_STRING" in html
        assert "KeyError: &#x27;&lt;boom&gt;&#x27;" in html

    def test_test_parses_the_process_request_and_leaves_maxlen_at_50(self, cgi: Any) -> None:
        script = (
            "import cgi, sys\n"
            "cgi.test({'REQUEST_METHOD': 'GET', 'QUERY_STRING': 'other=y'})\n"
            "print('MAXLEN', cgi.maxlen, file=sys.__stdout__)\n"
        )
        environ = {**os.environ, "REQUEST_METHOD": "GET", "QUERY_STRING": "name=x"}
        result = subprocess.run(
            [sys.executable, "-W", "ignore::DeprecationWarning", "-c", script],
            env=environ,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "<H3>Form Contents:</H3>" in result.stdout
        assert "<DT>name:" in result.stdout
        assert "<DT>other:" not in result.stdout
        assert "<DT> QUERY_STRING <DD> other=y" in result.stdout
        assert result.stdout.rstrip().endswith("MAXLEN 50")


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


def _imports_cgi(source: str) -> bool:
    return re.search(r"^import cgi$", source, re.MULTILINE) is not None


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
    """Each block runs in its own subprocess and asserts its own result. From
    Python 3.13 a block importing `cgi` must fail on the import."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert 0 < sum(not _imports_cgi(source) for _, source in blocks) < EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if REMOVED and _imports_cgi(source):
                missing = "ModuleNotFoundError: No module named 'cgi'" in result.stderr
                if result.returncode == 0 or not missing:
                    failures.append(f"{PAGE.name}:{line} imported cgi\n{result.stderr.strip()}")
            elif result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "parse_qsl('a=1&b=2')" in s)
        mutated = source.replace("('b', '2')]", "('b', '3')]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
