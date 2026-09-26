"""Tests for docs/stdlib/gettext.md.

The page prices the module in three places: parsing a `.mo` file, which is
linear in its bytes and happens once per file per process; searching for
files, which `translation()` repeats on every call and the module-level
`gettext()` family therefore repeats on every message; and the lookup, which
compares the message id and walks the fallback chain on a miss. Laziness,
caching and repetition are settled by counting calls and checking identity;
the size terms by traced allocation and by timing ratios.

Measurement scope:

* The module-level functions are observed through a counting
  `os.path.exists`: two calls to each of `gettext()`, `dgettext()`,
  `ngettext()`, `dngettext()`, `pgettext()`, `dpgettext()`, `npgettext()` and
  `dnpgettext()` make the same non-zero number of checks each, while a bound
  `translation(...).gettext` makes none. A counting `class_` shows a file is
  parsed once however many times `translation()` finds it. With no catalog,
  each function returns its message unchanged.
* `find()` is observed to check the four variants of `fi_FI.UTF-8` in order
  and the eight of `sr_RS.UTF-8@latin`, the most a language expands to, to stop at the first hit unless `all=True`, to stop at `C`, and to read
  `LANGUAGE` before `LANG`. Its O(d²) is a timing test over 250, 1,000 and
  4,000 distinct languages that expand to one candidate each, against a
  nonexistent directory: every 4x step costs more than 5x, where linear
  predicts 4x, and the 16x span more than 50x, where linear predicts 16x.
* `translation()` returns a new object per call sharing the parsed catalog
  and `info()` dictionary; a file rewritten after the first call is not
  reread; a different `class_` parses it again; with no file it raises
  `FileNotFoundError`, or returns a `NullTranslations` with `fallback=True`;
  two languages found are chained in the order given.
* `GNUTranslations(fp)` reads the file to its end at construction, and its
  catalog dictionary holds every message, decoded, before any lookup. Its traced peak grows more than 50x from 1,000 to 100,000
  messages, and in a timing test each 10x step in messages costs between 5x
  and 30x, which is linear and excludes quadratic's 100x. A bad magic number,
  an unknown major version and a message running past the end each raise
  `OSError`.
* A `gettext()` hit on a 1,000,000-character message id, probed with an equal
  but distinct string, costs more than 50x a 1,000-character one in a timing
  test and allocates under 1 KB, as does an `ngettext()` hit on a plural
  entry with that id. `pgettext()` and `npgettext()` on the same id allocate
  more than its length, the key they build. A miss is observed to reach every catalog in a chain of ten.
* `NullTranslations(fp)` is given an object whose `read()` raises, and a
  subclass shows `_parse()` receives `fp`. Its lookups are asserted to return
  their input, `add_fallback()` to append at the end of a chain of three,
  `info()` and `charset()` to be an empty dictionary and `None`, and
  `install()` to bind `_` and only the allowed names into `builtins`, which
  is restored afterwards.
* `bindtextdomain()` and `textdomain()` are asserted to set and return their
  value, with the module's globals restored afterwards.
* Every fenced Python block runs in its own subprocess and working directory,
  so `builtins._`, the environment and the parse cache cannot leak between
  them, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Allocation is asserted to grow with the file, not to grow linearly: the
  O(b) space bound is read from `_parse()`, which keeps the file's bytes and
  one decoded string per message.

* The O(f) space of a miss and of `add_fallback()` is one stack frame per
  catalog, read from Lib/gettext.py's recursion rather than measured.
* Treating an existence check and a plural-formula evaluation as O(1) is a
  cost-model assumption; a slow filesystem or a huge `n` is outside it.
* The `d` term of the module-level functions follows from their calling
  `translation()`, which the counting test shows; the d² term itself is timed
  on `find()` only. Plural-formula length is capped by the module at 1,000
  characters and is not varied.
* `gettext.c2py()` is outside `__all__` and the official documentation, so the
  page leaves it out; `GNUTranslations.LE_MAGIC`, `BE_MAGIC`, `CONTEXT` and
  `VERSIONS` are class constants the page does not price.
* The removals in 3.11 are a Version Notes entry. No supported interpreter
  after 3.10 has the removed names, and 3.10's deprecated forms are not
  exercised.
"""

from __future__ import annotations

import builtins
import gettext
import io
import os
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "gettext.md"
EXPECTED_BLOCKS = 7

HEADER = "Content-Type: text/plain; charset=UTF-8\n"
PLURAL_HEADER = HEADER + "Plural-Forms: nplurals=2; plural=n != 1;\n"


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


def make_mo(messages: dict[str, str], header: str = HEADER, version: int = 0) -> bytes:
    """Encode {msgid: msgstr} as a little-endian GNU .mo file."""
    entries = sorted({"": header, **messages}.items())
    count = len(entries)
    tables, strings = [b"", b""], b""
    for column in (0, 1):
        for entry in entries:
            data = entry[column].encode()
            tables[column] += struct.pack("<2I", len(data), 28 + 16 * count + len(strings))
            strings += data + b"\0"
    head = struct.pack("<7I", 0x950412DE, version, count, 28, 28 + 8 * count, 0, 0)
    return head + tables[0] + tables[1] + strings


def catalog(messages: dict[str, str], header: str = HEADER) -> gettext.GNUTranslations:
    return gettext.GNUTranslations(io.BytesIO(make_mo(messages, header)))


def write_catalog(localedir: pathlib.Path, language: str, messages: dict[str, str]) -> None:
    mofile = localedir / language / "LC_MESSAGES" / "app.mo"
    mofile.parent.mkdir(parents=True, exist_ok=True)
    mofile.write_bytes(make_mo(messages))


@pytest.fixture
def module_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the module's domain and bindings, and pin the language variables."""
    monkeypatch.setattr(gettext, "_current_domain", gettext.textdomain())
    monkeypatch.setattr(gettext, "_localedirs", dict(vars(gettext)["_localedirs"]))
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGUAGE", "fi")


@pytest.fixture
def existence_checks(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every path `find()` checks."""
    checked: list[str] = []
    original = os.path.exists

    def counting(path: Any) -> bool:
        checked.append(str(path))
        return original(path)

    monkeypatch.setattr(os.path, "exists", counting)
    return checked


class TestModuleLevelFunctionsSearchEveryCall:
    """`gettext.gettext(message)` and its siblings | O(d² + b + f·k): each call
    runs `translation()` again. Separated from a cached lookup by counting the
    existence checks each call makes."""

    MESSAGES = {  # noqa: RUF012
        "Hello": "Hei",
        "Hello\0Hellos": "Hei\0Heit",
        "greeting\x04Hello": "Moi",
        "greeting\x04Hello\0Hellos": "Moi\0Moit",
    }
    CALLS: dict[str, Callable[[], str]] = {
        "gettext": lambda: gettext.gettext("Hello"),
        "dgettext": lambda: gettext.dgettext("app", "Hello"),
        "ngettext": lambda: gettext.ngettext("Hello", "Hellos", 1),
        "dngettext": lambda: gettext.dngettext("app", "Hello", "Hellos", 1),
        "pgettext": lambda: gettext.pgettext("greeting", "Hello"),
        "dpgettext": lambda: gettext.dpgettext("app", "greeting", "Hello"),
        "npgettext": lambda: gettext.npgettext("greeting", "Hello", "Hellos", 1),
        "dnpgettext": lambda: gettext.dnpgettext("app", "greeting", "Hello", "Hellos", 1),
    }

    @pytest.mark.parametrize("name", sorted(CALLS))
    @pytest.mark.usefixtures("module_state")
    def test_every_call_repeats_the_search(
        self, name: str, tmp_path: pathlib.Path, existence_checks: list[str]
    ) -> None:
        write_catalog(tmp_path, "fi", self.MESSAGES)
        gettext.bindtextdomain("app", str(tmp_path))
        gettext.textdomain("app")
        call = self.CALLS[name]

        call()
        first = len(existence_checks)
        result = call()

        assert result == ("Moi" if "pgettext" in name else "Hei")
        assert first > 0
        assert len(existence_checks) == 2 * first, f"{name} searched only once"

    @pytest.mark.usefixtures("module_state")
    def test_a_bound_lookup_searches_nothing(
        self, tmp_path: pathlib.Path, existence_checks: list[str]
    ) -> None:
        write_catalog(tmp_path, "fi", {"Hello": "Hei"})
        _ = gettext.translation("app", str(tmp_path)).gettext
        existence_checks.clear()

        assert _("Hello") == "Hei"
        assert existence_checks == []

    @pytest.mark.parametrize("name", sorted(CALLS))
    @pytest.mark.usefixtures("module_state")
    def test_without_a_catalog_the_message_comes_back(
        self, name: str, tmp_path: pathlib.Path
    ) -> None:
        gettext.bindtextdomain("app", str(tmp_path))
        gettext.textdomain("app")

        assert self.CALLS[name]() == "Hello"


class TestBindingsAreOneEntry:
    """`bindtextdomain` and `textdomain` | O(1): set, and return, one value."""

    @pytest.mark.usefixtures("module_state")
    def test_bindtextdomain_records_and_returns(self, tmp_path: pathlib.Path) -> None:
        assert gettext.bindtextdomain("app", str(tmp_path)) == str(tmp_path)
        assert gettext.bindtextdomain("app") == str(tmp_path)

    @pytest.mark.usefixtures("module_state")
    def test_textdomain_sets_and_returns(self) -> None:
        assert gettext.textdomain("app") == "app"
        assert gettext.textdomain() == "app"


class TestFindChecksEachCandidate:
    """`find` | O(d²) | O(d): one existence check per candidate, deduplicated
    by list scan, stopping at the first hit unless `all=True`."""

    def test_a_language_expands_into_its_variants(
        self, tmp_path: pathlib.Path, existence_checks: list[str]
    ) -> None:
        assert gettext.find("app", str(tmp_path), ["fi_FI.UTF-8"]) is None

        variants = [pathlib.Path(path).parent.parent.name for path in existence_checks]
        assert variants == ["fi_FI.UTF-8", "fi_FI", "fi.UTF-8", "fi"]

    def test_a_modifier_makes_eight(
        self, tmp_path: pathlib.Path, existence_checks: list[str]
    ) -> None:
        gettext.find("app", str(tmp_path), ["sr_RS.UTF-8@latin"])

        assert len(existence_checks) == 8

    def test_the_first_hit_stops_the_search_unless_all(
        self, tmp_path: pathlib.Path, existence_checks: list[str]
    ) -> None:
        write_catalog(tmp_path, "fi", {})
        write_catalog(tmp_path, "sv", {})

        found = gettext.find("app", str(tmp_path), ["fi", "sv"])
        checked_once = len(existence_checks)
        every = gettext.find("app", str(tmp_path), ["fi", "sv"], all=True)

        assert found is not None and pathlib.Path(found).parent.parent.name == "fi"
        assert isinstance(every, list) and len(every) == 2
        assert len(existence_checks) > 2 * checked_once

    def test_c_ends_the_search(self, tmp_path: pathlib.Path) -> None:
        write_catalog(tmp_path, "fi", {})

        assert gettext.find("app", str(tmp_path), ["C", "fi"]) is None

    def test_languages_default_to_the_environment_in_order(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_catalog(tmp_path, "fi", {})
        write_catalog(tmp_path, "sv", {})
        monkeypatch.setenv("LANGUAGE", "fi")
        monkeypatch.setenv("LANG", "sv")

        found = gettext.find("app", str(tmp_path))

        assert found is not None and pathlib.Path(found).parent.parent.name == "fi"

    @pytest.mark.timing
    def test_deduplication_is_quadratic_in_candidates(self) -> None:
        sizes = (250, 1_000, 4_000)
        durations = []
        for size in sizes:
            languages = [f"x{index}" for index in range(size)]
            durations.append(
                best_ns(lambda ls=languages: gettext.find("app", "/nonexistent", ls), repeats=3)
            )

        steps = [durations[1] / durations[0], durations[2] / durations[1]]
        span = durations[2] / durations[0]
        assert all(step > 5 for step in steps), f"4x candidates: {durations} ns, steps {steps}"
        assert span > 50, f"16x candidates cost x{span:.1f}; linear predicts x16"


class CountingTranslations(gettext.GNUTranslations):
    parses = 0

    def _parse(self, fp: Any) -> None:
        type(self).parses += 1
        super()._parse(fp)  # type: ignore[misc]


class TestTranslationCachesParsedCatalogs:
    """`translation` | O(d² + b) with b counting only files not parsed before:
    one parse per class and path for the life of the process, and a copy per
    call."""

    def test_a_file_is_parsed_once(self, tmp_path: pathlib.Path) -> None:
        write_catalog(tmp_path, "fi", {"Hello": "Hei"})

        class Counting(CountingTranslations):
            parses = 0

        results = [
            gettext.translation("app", str(tmp_path), ["fi"], class_=Counting) for _ in range(3)
        ]

        assert Counting.parses == 1
        assert len({id(result) for result in results}) == 3
        assert results[0]._catalog is results[2]._catalog  # type: ignore[attr-defined]  # noqa: SLF001
        assert results[0].info() is results[2].info()

    def test_another_class_parses_again(self, tmp_path: pathlib.Path) -> None:
        write_catalog(tmp_path, "fi", {"Hello": "Hei"})
        gettext.translation("app", str(tmp_path), ["fi"])

        class Counting(CountingTranslations):
            parses = 0

        gettext.translation("app", str(tmp_path), ["fi"], class_=Counting)

        assert Counting.parses == 1

    def test_a_rewritten_file_is_not_reread(self, tmp_path: pathlib.Path) -> None:
        write_catalog(tmp_path, "fi", {"Hello": "Hei"})
        assert gettext.translation("app", str(tmp_path), ["fi"]).gettext("Hello") == "Hei"

        write_catalog(tmp_path, "fi", {"Hello": "Moi"})

        assert gettext.translation("app", str(tmp_path), ["fi"]).gettext("Hello") == "Hei"
        with open(tmp_path / "fi" / "LC_MESSAGES" / "app.mo", "rb") as mofile:
            assert gettext.GNUTranslations(mofile).gettext("Hello") == "Moi"

    def test_no_catalog_raises_unless_fallback(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            gettext.translation("app", str(tmp_path), ["de"])

        null = gettext.translation("app", str(tmp_path), ["de"], fallback=True)

        assert type(null) is gettext.NullTranslations

    def test_every_catalog_found_is_chained_in_order(self, tmp_path: pathlib.Path) -> None:
        write_catalog(tmp_path, "fi", {"Hello": "Hei"})
        write_catalog(tmp_path, "sv", {"Hello": "Hej", "Bye": "Hej då"})

        chain = gettext.translation("app", str(tmp_path), ["fi", "sv"])

        assert chain.gettext("Hello") == "Hei"
        assert chain.gettext("Bye") == "Hej då"
        assert chain.gettext("Thanks") == "Thanks"

    def test_install_binds_underscore_through_translation(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_catalog(tmp_path, "fi", {"Hello": "Hei"})
        monkeypatch.setattr(builtins, "_", None, raising=False)
        monkeypatch.setenv("LANGUAGE", "fi")

        gettext.install("app", str(tmp_path))

        assert builtins._("Hello") == "Hei"  # type: ignore[attr-defined]


class TestParsingReadsTheWholeFile:
    """`GNUTranslations(fp)` | O(b) | O(b): every message is decoded at
    construction."""

    def test_construction_reads_to_the_end(self) -> None:
        data = make_mo({f"m{index}": f"v{index}" for index in range(100)})
        stream = io.BytesIO(data)

        gettext.GNUTranslations(stream)

        assert stream.tell() == len(data)

    def test_every_message_is_decoded_before_any_lookup(self) -> None:
        translations = catalog({f"m{index}": f"v{index}" for index in range(100)})

        entries = translations._catalog  # type: ignore[attr-defined]  # noqa: SLF001
        assert len(entries) == 101
        assert entries["m42"] == "v42"

    def test_the_peak_follows_the_file(self) -> None:
        small = make_mo({f"m{index}": f"v{index}" for index in range(1_000)})
        large = make_mo({f"m{index}": f"v{index}" for index in range(100_000)})

        peaks = [
            peak_bytes(lambda data=data: gettext.GNUTranslations(io.BytesIO(data)))
            for data in (small, large)
        ]

        assert peaks[1] > peaks[0] * 50, f"100x the messages peaked at {peaks}"

    @pytest.mark.timing
    def test_parsing_is_linear_in_the_file(self) -> None:
        files = [
            make_mo({f"m{index}": f"v{index}" for index in range(count)})
            for count in (1_000, 10_000, 100_000)
        ]
        durations = [
            best_ns(lambda data=data: gettext.GNUTranslations(io.BytesIO(data)), repeats=3)
            for data in files
        ]

        steps = [durations[1] / durations[0], durations[2] / durations[1]]
        assert all(5 < step < 30 for step in steps), (
            f"10x the messages: {durations} ns, steps {steps}; linear is x10, quadratic x100"
        )

    @pytest.mark.parametrize(
        ("data", "message"),
        [
            (b"not a catalog at all", "Bad magic number"),
            (make_mo({}, version=2 << 16), "Bad version number"),
            (make_mo({"Hello": "Hei"})[:-8], "File is corrupt"),
        ],
    )
    def test_a_malformed_file_raises(self, data: bytes, message: str) -> None:
        with pytest.raises(OSError, match=message):
            gettext.GNUTranslations(io.BytesIO(data))


class TestLookupsCostTheMessageLength:
    """`GNUTranslations.gettext` and `ngettext` | O(k) | O(1); `pgettext` and
    `npgettext` | O(k) | O(k); a miss is asked of each catalog in the chain."""

    SHORT = 1_000
    LONG = 1_000_000

    @staticmethod
    def probe(size: int) -> tuple[gettext.GNUTranslations, str]:
        translations = catalog({"a" * size: "b", "a" * size + "\0x": "c\0d"})
        message = "".join(["a"] * size)  # equal to the stored id, not the same object
        hash(message)
        return translations, message

    def test_a_hit_is_found_with_a_distinct_equal_string(self) -> None:
        translations, message = self.probe(self.SHORT)

        assert translations.gettext(message) == "b"

    def test_gettext_and_ngettext_allocate_nothing_per_character(self) -> None:
        translations, message = self.probe(self.LONG)
        translations.gettext(message)

        peaks = [
            peak_bytes(lambda: translations.gettext(message)),
            peak_bytes(lambda: translations.ngettext(message, "x", 1)),
        ]

        assert translations.ngettext(message, "x", 1) == "c", "the plural lookup missed"

        assert max(peaks) < 1_000, f"a {self.LONG}-character lookup allocated {peaks}"

    def test_pgettext_and_npgettext_build_their_key(self) -> None:
        translations, message = self.probe(self.LONG)

        peaks = [
            peak_bytes(lambda: translations.pgettext("c", message)),
            peak_bytes(lambda: translations.npgettext("c", message, "x", 1)),
        ]

        assert min(peaks) > self.LONG, f"the context lookups allocated only {peaks} bytes"

    def test_context_and_plural_keys(self) -> None:
        translations = catalog(
            {"file\0files": "tiedosto\0tiedostoa", "menu\x04Open": "Avaa"}, PLURAL_HEADER
        )

        assert translations.ngettext("file", "files", 1) == "tiedosto"
        assert translations.ngettext("file", "files", 3) == "tiedostoa"
        assert translations.pgettext("menu", "Open") == "Avaa"
        assert translations.pgettext("door", "Open") == "Open"
        assert translations.npgettext("menu", "Open", "Opens", 2) == "Opens"

    def test_a_miss_is_asked_of_every_catalog(self) -> None:
        asked: list[int] = []

        class Recording(gettext.GNUTranslations):
            def gettext(self, message: str) -> str:
                asked.append(id(self))
                return super().gettext(message)

        links = [Recording(io.BytesIO(make_mo({}))) for _ in range(10)]
        for link in links[1:]:
            links[0].add_fallback(link)

        assert links[0].gettext("Thanks") == "Thanks"
        assert asked == [id(link) for link in links]

    @pytest.mark.timing
    def test_a_hit_costs_the_message_length(self) -> None:
        short, short_message = self.probe(self.SHORT)
        long, long_message = self.probe(self.LONG)

        durations = [
            best_ns(lambda: short.gettext(short_message), inner=20),
            best_ns(lambda: long.gettext(long_message), inner=20),
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 50, f"1,000x the message id cost x{ratio:.1f} ({durations} ns)"


class TestNullTranslations:
    """`NullTranslations` holds no catalog: construction reads nothing, lookups
    return their input, and `add_fallback` appends at the end of the chain."""

    def test_construction_does_not_read(self) -> None:
        class Unreadable:
            def read(self, *args: Any) -> bytes:
                raise AssertionError("NullTranslations read its file")

        gettext.NullTranslations(Unreadable())

    def test_parse_is_the_hook_for_fp(self) -> None:
        received: list[object] = []

        class Custom(gettext.NullTranslations):
            def _parse(self, fp: Any) -> None:
                received.append(fp)

        source = io.BytesIO()
        Custom(source)
        Custom()

        assert received == [source]

    def test_lookups_return_their_input(self) -> None:
        null = gettext.NullTranslations()

        assert null.gettext("Hello") == "Hello"
        assert null.ngettext("file", "files", 1) == "file"
        assert null.ngettext("file", "files", 2) == "files"
        assert null.pgettext("menu", "Open") == "Open"
        assert null.npgettext("menu", "file", "files", 2) == "files"
        assert null.info() == {} and null.info() is null.info()
        assert null.charset() is None

    def test_a_fallback_answers_for_it(self) -> None:
        null = gettext.NullTranslations()
        null.add_fallback(catalog({"Hello": "Hei"}))

        assert null.gettext("Hello") == "Hei"

    def test_add_fallback_appends_at_the_end(self) -> None:
        first, second, third = (gettext.NullTranslations() for _ in range(3))

        first.add_fallback(second)
        first.add_fallback(third)

        assert first._fallback is second  # type: ignore[attr-defined]  # noqa: SLF001
        assert second._fallback is third  # type: ignore[attr-defined]  # noqa: SLF001

    def test_catalog_charset_and_info(self) -> None:
        translations = catalog({"Hello": "Hei"})

        assert translations.charset() == "UTF-8"
        assert translations.info() is translations.info()
        assert translations.info()["content-type"] == "text/plain; charset=UTF-8"

    def test_install_binds_underscore_and_only_allowed_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in ("_", "gettext", "ngettext", "pgettext", "npgettext", "info"):
            monkeypatch.setattr(builtins, name, None, raising=False)
        null = gettext.NullTranslations()

        null.install(names=["ngettext", "info"])

        assert builtins._ == null.gettext  # type: ignore[attr-defined]
        assert builtins.ngettext == null.ngettext  # type: ignore[attr-defined]
        assert builtins.info is None  # type: ignore[attr-defined]
        assert builtins.pgettext is None  # type: ignore[attr-defined]


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
    """Each block runs in its own subprocess, so `builtins._`, the environment
    and the parse cache cannot leak between them, and asserts its own result."""

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
        target = '.gettext("Hello") == "Hei"\n\n    # No catalog'
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, target.replace('"Hei"', '"Moi"'), 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
