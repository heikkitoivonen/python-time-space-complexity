"""Tests for docs/stdlib/netrc.md.

The page prices the module as one linear parse at construction followed by
dictionary lookups. Linearity is settled by timing at three file sizes a
decade apart, in four input shapes that exercise different parts of the lexer;
lookups by counting the dictionary operations `authenticators()` performs
against a large table; `repr()` by timing and output length; and the behaviour
rows by direct observation on files written under `tmp_path`. The `~/.netrc`
check is reached by pointing `HOME` at `tmp_path`, never at the real home
directory.

Measurement scope:

* `netrc(file)` is timed on about 10,000, 100,000 and 1,000,000 characters in
  four shapes: many one-line machine entries, one long unquoted password, one
  long double-quoted password, and many comment lines ahead of one entry. Each
  10x step must cost between 2x and 30x, where a linear parse predicts 10x and
  a quadratic one 100x. The two long-password shapes run on 3.11+ only.
* The token term is then isolated at a fixed n of 400,000 characters: one
  400,000-character password against short machine entries whose longest
  token is under ten characters. On 3.11+ the long token must cost under 2x
  the entries. On 3.10, whose shlex-based lexer copies the token on every
  character, a password of 400,000 characters must cost more than 24x one of
  50,000 (linear predicts 8x, O(n·t) 64x; x50 to x55 on 3.10.21, where 3.14.7
  takes x7.6 to x8.3).
* A `tracemalloc` peak over a 500,000-character password is over 500 KB and
  under 30 times the peak for a 50,000-character one (quadratic predicts
  100x; x3.2 on 3.14.7, x6.6 on 3.12.14 and x8.1 on 3.10.21), so the space
  follows the file and is not quadratic in it.
* `authenticators()` over 100,000 hosts is a dict subclass that counts
  `__contains__` and `__getitem__`: a hit is one of each, a miss that falls
  back to `default` two and one, and a miss without `default` two and none. It
  returns the tuple stored in `hosts`, by identity. A host listed twice keeps
  the last entry.
* `repr()` is timed on 1,000, 10,000 and 100,000 entries under the same 30x
  bound per 10x step, and its text is asserted exactly for one entry, with an
  empty account omitted and a comment dropped. A password with a space,
  quoted in the file, is written unquoted and does not parse back (3.11+).
* The `~/.netrc` check (POSIX): a 0o644 file is rejected by `netrc()` and
  accepted by path; a 0o600 file is accepted; a patched `os.getuid` that does
  not match the owner is rejected; the `anonymous` login is exempt on 3.11+.
  With no `~/.netrc`, `netrc()` raises `FileNotFoundError`.
* Version-gated on 3.11: quoted and escaped tokens, an entry without a
  password, `''` for missing fields, a `macdef` without its terminating blank
  line raising, and the comment rule: a multi-word comment on the line after an
  entry is skipped, while after a blank line a one-word comment is skipped and
  a multi-word one raises. On 3.10 the same inputs are asserted to take the
  3.10 path: an entry without a password raises, a missing account is `None`,
  the unterminated `macdef` is kept, and the comment after a blank line is
  skipped.
* `NetrcParseError` carries `msg`, `filename` and `lineno` for a syntax error.
* Every fenced Python block runs in its own subprocess with `HOME` pointed at
  a temporary directory, and a mutated assertion in one of them is asserted to
  fail.

Not settled here:

* Host-name hashing is treated as O(1); long host names are not varied.
* Non-UTF-8 files, which are parsed a second time in the locale encoding, are
  not measured; the bound is read from Lib/netrc.py, where the retry is one
  more linear pass.
* The security check on platforms without `os.getuid` (skipped since 3.13.6
  and 3.14.0), and on Windows, where it never runs, is read from Lib/netrc.py.
* `macdef` bodies are read a line at a time with `readline()`; that loop's
  cost is read from Lib/netrc.py, and files of many or long macros are not
  timed.
"""

from __future__ import annotations

import netrc
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "netrc.md"
EXPECTED_BLOCKS = 7

posix_only = pytest.mark.skipif(os.name != "posix", reason="the check runs on POSIX only")
since_311 = pytest.mark.skipif(sys.version_info < (3, 11), reason="3.11 rewrote the lexer")
before_311 = pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 parser")


def best_ns(func: Callable[[], Any], repeats: int = 3) -> float:
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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def write(directory: pathlib.Path, text: str, name: str = "credentials") -> pathlib.Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def parse(directory: pathlib.Path, text: str) -> netrc.netrc:
    return netrc.netrc(str(write(directory, text)))


def machines(chars: int) -> str:
    lines: list[str] = []
    total = 0
    index = 0
    while total < chars:
        line = f"machine h{index} login u{index} password p{index}\n"
        lines.append(line)
        total += len(line)
        index += 1
    return "".join(lines)


SHAPES: dict[str, Callable[[int], str]] = {
    "machines": machines,
    "long token": lambda chars: f"machine h login u password {'x' * chars}\n",
    "quoted token": lambda chars: f'machine h login u password "{"x" * chars}"\n',
    "comments": lambda chars: (
        "# a comment line of words\n" * (chars // 26) + "machine h login u password p\n"
    ),
}


TOKEN_SHAPES = ("long token", "quoted token")


class TestParsingIsLinear:
    """`netrc.netrc(file)` | O(n) | O(n): one pass, whatever the file's shape;
    on 3.10, O(n·t) for a longest token of t characters."""

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "shape",
        [
            pytest.param(shape, marks=since_311) if shape in TOKEN_SHAPES else shape
            for shape in SHAPES
        ],
    )
    def test_ten_times_the_file_costs_about_ten_times(
        self, shape: str, tmp_path: pathlib.Path
    ) -> None:
        sizes = (10_000, 100_000, 1_000_000)
        paths = [str(write(tmp_path, SHAPES[shape](size), f"f{size}")) for size in sizes]
        for path in paths:
            netrc.netrc(path)  # warm the page cache and the code objects
        durations = [best_ns(lambda p=path: netrc.netrc(p)) for path in paths]  # type: ignore[misc]
        ratios = [durations[1] / durations[0], durations[2] / durations[1]]

        assert all(2 < ratio < 30 for ratio in ratios), (
            f"{shape}: 10x steps cost x{ratios[0]:.1f} and x{ratios[1]:.1f} "
            f"({durations} ns); linear predicts x10, quadratic x100"
        )

    @staticmethod
    def token_against_entries() -> float:
        """Parse time of one 400,000-character token over that of 400,000
        characters of short entries: the same n, with t at 400,000 and under 10."""
        with tempfile.TemporaryDirectory() as directory:
            token = write(pathlib.Path(directory), SHAPES["long token"](400_000), "token")
            entries = write(pathlib.Path(directory), SHAPES["machines"](400_000), "entries")
            netrc.netrc(str(token))
            netrc.netrc(str(entries))  # warm the page cache and the code objects
            token_ns = best_ns(lambda: netrc.netrc(str(token)))
            entries_ns = best_ns(lambda: netrc.netrc(str(entries)))
        return token_ns / entries_ns

    @pytest.mark.timing
    @since_311
    def test_one_long_token_costs_what_short_ones_do(self) -> None:
        ratio = self.token_against_entries()

        assert ratio < 2, f"one long token cost x{ratio:.1f} the short entries at equal n"

    @pytest.mark.timing
    @before_311
    def test_one_long_token_is_quadratic_on_310(self, tmp_path: pathlib.Path) -> None:
        short = str(write(tmp_path, SHAPES["long token"](50_000), "short"))
        long = str(write(tmp_path, SHAPES["long token"](400_000), "long"))
        netrc.netrc(short)
        netrc.netrc(long)  # warm the page cache and the code objects

        ratio = best_ns(lambda: netrc.netrc(long)) / best_ns(lambda: netrc.netrc(short))

        assert ratio > 24, f"8x the token cost x{ratio:.1f}; linear predicts 8x, O(n·t) 64x"

    def test_every_shape_parses(self, tmp_path: pathlib.Path) -> None:
        assert len(parse(tmp_path, SHAPES["machines"](10_000)).hosts) > 250
        assert parse(tmp_path, SHAPES["long token"](1_000)).hosts["h"][2] == "x" * 1_000
        assert parse(tmp_path, SHAPES["comments"](10_000)).hosts["h"][2] == "p"

    @since_311
    def test_a_quoted_token_parses(self, tmp_path: pathlib.Path) -> None:
        assert parse(tmp_path, SHAPES["quoted token"](1_000)).hosts["h"][2] == "x" * 1_000

    def test_the_peak_follows_the_file(self, tmp_path: pathlib.Path) -> None:
        small = str(write(tmp_path, SHAPES["long token"](50_000), "small"))
        large = str(write(tmp_path, SHAPES["long token"](500_000), "large"))

        small_peak = peak_bytes(lambda: netrc.netrc(small))
        large_peak = peak_bytes(lambda: netrc.netrc(large))

        assert large_peak > 500_000, f"a 500,000-character token peaked at {large_peak}"
        assert large_peak < small_peak * 30, f"peaks {small_peak} and {large_peak}"


class CountingDict(dict[str, Any]):
    """A dict that counts membership tests and item reads."""

    contains = 0
    getitem = 0

    def __contains__(self, key: object) -> bool:
        self.contains += 1
        return super().__contains__(key)

    def __getitem__(self, key: str) -> Any:
        self.getitem += 1
        return super().__getitem__(key)


class TestAuthenticatorsIsADictLookup:
    """`authenticators(host)` | O(1) | O(1): a lookup, then the `default`
    fallback, then `None`; it returns the stored tuple."""

    @staticmethod
    def counted(rc: netrc.netrc, host: str) -> tuple[Any, int, int]:
        table = CountingDict(rc.hosts)
        rc.hosts = table
        result = rc.authenticators(host)
        return result, table.contains, table.getitem

    @pytest.fixture
    def large(self, tmp_path: pathlib.Path) -> netrc.netrc:
        rc = parse(tmp_path, "machine example.com login alice password s3cret\n")
        rc.hosts.update({f"h{index}": ("u", "", "p") for index in range(100_000)})
        return rc

    def test_a_hit_is_one_membership_test_and_one_read(self, large: netrc.netrc) -> None:
        result, contains, getitem = self.counted(large, "example.com")

        assert result is large.hosts["example.com"]
        assert (contains, getitem) == (1, 1)

    def test_a_miss_falls_back_to_default(self, large: netrc.netrc) -> None:
        large.hosts["default"] = ("anonymous", "", "guest")

        result, contains, getitem = self.counted(large, "unknown.example")

        assert result == ("anonymous", "", "guest")
        assert (contains, getitem) == (2, 1)

    def test_a_miss_without_default_is_none(self, large: netrc.netrc) -> None:
        result, contains, getitem = self.counted(large, "unknown.example")

        assert result is None
        assert (contains, getitem) == (2, 0)

    def test_a_host_listed_twice_keeps_its_last_entry(self, tmp_path: pathlib.Path) -> None:
        rc = parse(
            tmp_path,
            "machine h login first password p\nmachine h login second password q\n",
        )

        assert rc.authenticators("h") == ("second", rc.hosts["h"][1], "q")
        assert list(rc.hosts) == ["h"]

    def test_macros_holds_each_line(self, tmp_path: pathlib.Path) -> None:
        rc = parse(tmp_path, "macdef init\ncd /pub\nbinary\n\n")

        assert rc.macros == {"init": ["cd /pub\n", "binary\n"]}


class TestReprRebuildsTheText:
    """`repr(netrc)` | O(r) | O(r): text rebuilt from `hosts` and `macros`,
    tokens unquoted."""

    def test_the_text_for_one_entry(self, tmp_path: pathlib.Path) -> None:
        rc = parse(tmp_path, "# personal\nmachine example.com login alice password s3cret\n")

        assert repr(rc) == "machine example.com\n\tlogin alice\n\tpassword s3cret\n"

    def test_an_account_and_a_macro_are_written(self, tmp_path: pathlib.Path) -> None:
        rc = parse(tmp_path, "machine h login u account a password p\nmacdef m\nline\n\n")

        assert repr(rc) == "machine h\n\tlogin u\n\taccount a\n\tpassword p\nmacdef m\nline\n\n"

    @since_311
    def test_a_token_with_whitespace_does_not_round_trip(self, tmp_path: pathlib.Path) -> None:
        rc = parse(tmp_path, 'machine h login u password "two words"\n')
        assert rc.hosts["h"][2] == "two words"

        with pytest.raises(netrc.NetrcParseError, match="bad follower token"):
            parse(tmp_path, repr(rc))

    @pytest.mark.timing
    def test_ten_times_the_entries_cost_about_ten_times(self, tmp_path: pathlib.Path) -> None:
        objects = []
        for count in (1_000, 10_000, 100_000):
            rc = parse(tmp_path, "")
            rc.hosts = {f"host{index}": ("user", "", "password") for index in range(count)}
            objects.append(rc)
        lengths = [len(repr(rc)) for rc in objects]
        durations = [best_ns(lambda r=rc: repr(r)) for rc in objects]  # type: ignore[misc]
        ratios = [durations[1] / durations[0], durations[2] / durations[1]]

        assert lengths[2] > lengths[1] * 9 > lengths[0] * 81
        assert all(2 < ratio < 30 for ratio in ratios), (
            f"10x the entries cost x{ratios[0]:.1f} and x{ratios[1]:.1f} ({durations} ns)"
        )


class TestTheHomeNetrcCheck:
    """`netrc.netrc()` on POSIX checks the owner and mode of `~/.netrc`; a
    file passed by path is not checked. `HOME` points at `tmp_path`."""

    ENTRY = "machine example.com login alice password s3cret\n"

    @pytest.fixture
    def home(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))  # what `~` reads on Windows
        assert os.path.expanduser("~") == str(tmp_path)
        return tmp_path

    @posix_only
    def test_a_group_readable_file_is_rejected(self, home: pathlib.Path) -> None:
        path = write(home, self.ENTRY, ".netrc")
        path.chmod(0o644)

        with pytest.raises(netrc.NetrcParseError, match="too permissive"):
            netrc.netrc()
        assert netrc.netrc(str(path)).authenticators("example.com") is not None

    def test_a_missing_file_raises_file_not_found(self, home: pathlib.Path) -> None:
        assert not (home / ".netrc").exists()

        with pytest.raises(FileNotFoundError):
            netrc.netrc()

    @posix_only
    def test_an_owner_only_file_is_accepted(self, home: pathlib.Path) -> None:
        write(home, self.ENTRY, ".netrc").chmod(0o600)

        assert netrc.netrc().authenticators("example.com")[0] == "alice"  # type: ignore[index]

    @posix_only
    def test_another_owner_is_rejected(
        self, home: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write(home, self.ENTRY, ".netrc").chmod(0o600)
        real_uid = os.getuid()
        monkeypatch.setattr(os, "getuid", lambda: real_uid + 12_345)

        with pytest.raises(netrc.NetrcParseError, match="does not match"):
            netrc.netrc()

    @posix_only
    @since_311
    def test_the_anonymous_login_is_exempt(self, home: pathlib.Path) -> None:
        write(home, "machine h login anonymous password guest\n", ".netrc").chmod(0o644)

        assert netrc.netrc().hosts == {"h": ("anonymous", "", "guest")}


class TestVersionedSyntax:
    """The 3.11 lexer: quoting, optional passwords, `''` fields, terminated
    macros and the comment rule; the same inputs on the 3.10 parser."""

    @since_311
    def test_quotes_and_escapes_join_words(self, tmp_path: pathlib.Path) -> None:
        assert parse(tmp_path, 'machine h login u password "a b"\n').hosts["h"][2] == "a b"
        assert parse(tmp_path, "machine h login u password a\\ b\n").hosts["h"][2] == "a b"

    @since_311
    def test_an_entry_needs_no_password(self, tmp_path: pathlib.Path) -> None:
        assert parse(tmp_path, "machine h login u\n").hosts == {"h": ("u", "", "")}

    @since_311
    def test_an_unterminated_macro_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(netrc.NetrcParseError, match="null line"):
            parse(tmp_path, "macdef m\nline\n")

    @since_311
    def test_a_comment_after_an_entry_line_is_skipped(self, tmp_path: pathlib.Path) -> None:
        rc = parse(
            tmp_path,
            "machine a login u password p\n# the work account\nmachine b login v password q\n",
        )

        assert sorted(rc.hosts) == ["a", "b"]

    @since_311
    def test_after_a_blank_line_only_the_first_word_is_skipped(
        self, tmp_path: pathlib.Path
    ) -> None:
        entry = "machine a login u password p\n\n"

        assert parse(tmp_path, entry + "#work\n").hosts == {"a": ("u", "", "p")}
        with pytest.raises(netrc.NetrcParseError, match="bad follower token 'the'"):
            parse(tmp_path, entry + "# the work account\n")

    @before_311
    def test_the_310_parser(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(netrc.NetrcParseError, match="malformed"):
            parse(tmp_path, "machine h login u\n")
        assert parse(tmp_path, "machine h login u password p\n").hosts == {"h": ("u", None, "p")}
        assert parse(tmp_path, "macdef m\nline\n").macros == {"m": ["line\n"]}
        rc = parse(tmp_path, "machine a login u password p\n\n# the work account\n")
        assert rc.hosts == {"a": ("u", None, "p")}


class TestNetrcParseError:
    """`NetrcParseError` | O(1): `msg`, `filename` and `lineno` locate a
    syntax error, and parsing stops there."""

    def test_it_carries_the_location(self, tmp_path: pathlib.Path) -> None:
        path = write(tmp_path, "machine a login u password p\nhost b\nmachine c\n")

        with pytest.raises(netrc.NetrcParseError) as caught:
            netrc.netrc(str(path))

        assert caught.value.filename == str(path)
        assert caught.value.lineno == 2
        assert "bad follower token 'host'" in caught.value.msg
        assert str(path) in str(caught.value)


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
    home = cwd / "home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
        env={**os.environ, "HOME": str(home)},
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess with `HOME` pointed at an empty
    directory, so no block can read the real `~/.netrc`, and asserts its own
    result."""

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
            leftovers = sorted(p.name for p in workdir.iterdir()) + sorted(
                p.name for p in (workdir / "home").iterdir()
            )
            if leftovers != ["block.py", "home"]:
                failures.append(f"{PAGE.name}:{line} left {leftovers} behind")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "error.lineno == 2" in s)
        mutated = source.replace("error.lineno == 2", "error.lineno == 3", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
