"""Tests for docs/stdlib/sre_constants.md.

Every row on the page is an O(1) read of a value built at import, so the
tests settle what the rows say each value is: the alias by identity and by a
fresh interpreter's warnings, the opcode lists by indexing each one with its
own members, the maps by their keys and values, and the flags and limits by
comparison with `re` and `_sre`.

Measurement scope:

* The deprecation is observed in a fresh interpreter importing the module
  twice under `warnings.simplefilter('always')`: one `DeprecationWarning`
  from the first import and none from the second on 3.11+, none on 3.10.
  Every non-dunder name of `re._constants` is asserted to be the same object
  in the alias on 3.11+.
* Every member of `OPCODES`, `ATCODES` and `CHCODES` is asserted to index
  its own list back to itself, to be an `int` and to print as its `.name`.
  `MIN_REPEAT` and `MAX_REPEAT` are asserted absent from `OPCODES` and
  present in the tree for `a*?` and `a*`, and the parse of `a*` to carry
  `MAXREPEAT` as its upper bound, by identity.
* The `OP_*`, `AT_*` and `CH_*` maps are asserted to be dicts whose keys and
  values are members of the matching list; `CH_NEGATE` (3.14+) to map each
  category to the name with `NOT_` added or removed before its last word.
* Each `SRE_FLAG_*` is asserted equal to the `re` flag of the same name;
  `SRE_FLAG_TEMPLATE` and `re.TEMPLATE` to exist exactly on 3.10 to 3.12.
  The `SRE_INFO_*` bits are asserted in the header of a compiled literal
  pattern, read with the compiler's private `_code()`. `MAGIC`, `MAXREPEAT`
  and `MAXGROUPS` are asserted equal to `_sre`'s. That `MAXGROUPS` counts
  group 0 is settled in tests/test_sre_parse_complexity.py, where a limit
  patched to 3 admits two opened groups.
* Version-bounded names are asserted by presence: `ATOMIC_GROUP` and the
  possessive repeats on 3.11+, `CALL` on 3.10 only, `CH_NEGATE` on 3.14+,
  `PatternError` on 3.13+; `error` is `re.error` everywhere.
* The single fenced Python block runs in its own subprocess, and a mutated
  assertion in it is asserted to fail.

Not settled here:

* That the 3.10 parser never produces `CALL`: Lib/sre_parse.py at v3.10.19
  has no code path that appends it; only the compiler and `getwidth()`
  mention it.
* That opcode values and `MAGIC` change between releases is read from the
  released sources (`MAGIC` is different in 3.10, 3.11, 3.12 and 3.13), not
  asserted, since one interpreter sees one release.
* The module is undocumented; which names it exposes is taken from the
  released sources of 3.10 to 3.14, not from a documented contract.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import subprocess
import sys
import textwrap
import warnings
from typing import Any

import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    sre_constants: Any = importlib.import_module("sre_constants")
    sre_parse: Any = importlib.import_module("sre_parse")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sre_constants.md"
EXPECTED_BLOCKS = 1

FLAG_NAMES = ("IGNORECASE", "LOCALE", "MULTILINE", "DOTALL", "UNICODE", "VERBOSE", "DEBUG", "ASCII")


def compiler_module() -> Any:
    """The compiler `re` uses: `re._compiler` on 3.11+, `sre_compile` on 3.10."""
    internals: Any = re
    return getattr(re, "_compiler", None) or internals.sre_compile


class TestTheModuleIsADeprecatedAlias:
    """`import sre_constants` | O(1) | Python 3.11+: warns on the first
    import only; the names are the same objects as `re._constants`'s."""

    def test_the_first_import_warns_and_the_second_does_not(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import warnings\n"
                "counts = []\n"
                "for _ in range(2):\n"
                "    with warnings.catch_warnings(record=True) as caught:\n"
                "        warnings.simplefilter('always')\n"
                "        import sre_constants\n"
                "    counts.append([w.category.__name__ for w in caught])\n"
                "print(counts)\n",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        if sys.version_info >= (3, 11):
            assert result.stdout.strip() == "[['DeprecationWarning'], []]"
        else:
            assert result.stdout.strip() == "[[], []]"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="re._constants is 3.11+")
    def test_every_name_is_the_constants_module_s_own_object(self) -> None:
        constants = importlib.import_module("re._constants")
        names = [name for name in vars(constants) if not name.startswith("__")]

        assert len(names) > 100
        for name in names:
            assert getattr(sre_constants, name) is getattr(constants, name), name


class TestOpcodes:
    """The opcode lists are indexed by opcode value, and the opcodes are
    `int` subclasses that print as their name and are tested with `is`."""

    @pytest.mark.parametrize("table", ["OPCODES", "ATCODES", "CHCODES"])
    def test_each_list_is_indexed_by_its_members_values(self, table: str) -> None:
        codes = getattr(sre_constants, table)

        assert len(codes) > 10
        for code in codes:
            assert codes[code] is code, code
            assert int in type(code).__mro__
            assert str(code) == repr(code) == code.name
            assert getattr(sre_constants, code.name) is code

    def test_the_repeat_opcodes_appear_only_in_parse_trees(self) -> None:
        assert sre_constants.MAX_REPEAT not in sre_constants.OPCODES
        assert sre_constants.MIN_REPEAT not in sre_constants.OPCODES
        assert sre_parse.parse("a*?")[0][0] is sre_constants.MIN_REPEAT

        op, (low, high, body) = sre_parse.parse("a*")[0]
        assert op is sre_constants.MAX_REPEAT
        assert (low, high) == (0, sre_constants.MAXREPEAT) and high is sre_constants.MAXREPEAT
        assert body[0] == (sre_constants.LITERAL, ord("a"))

    def test_the_version_bounded_opcodes(self) -> None:
        for name in ("ATOMIC_GROUP", "POSSESSIVE_REPEAT", "POSSESSIVE_REPEAT_ONE"):
            assert hasattr(sre_constants, name) == (sys.version_info >= (3, 11)), name
        assert hasattr(sre_constants, "CALL") == (sys.version_info < (3, 11))


class TestOpcodeMaps:
    """The `OP_*`, `AT_*` and `CH_*` maps are dicts between members of the
    matching opcode list."""

    @pytest.mark.parametrize(
        ("name", "table"),
        [
            ("OP_IGNORE", "OPCODES"),
            ("OP_LOCALE_IGNORE", "OPCODES"),
            ("OP_UNICODE_IGNORE", "OPCODES"),
            ("AT_MULTILINE", "ATCODES"),
            ("AT_LOCALE", "ATCODES"),
            ("AT_UNICODE", "ATCODES"),
            ("CH_LOCALE", "CHCODES"),
            ("CH_UNICODE", "CHCODES"),
        ],
    )
    def test_a_map_is_a_dict_within_its_list(self, name: str, table: str) -> None:
        mapping = getattr(sre_constants, name)
        codes = getattr(sre_constants, table)

        assert isinstance(mapping, dict) and mapping
        for key, value in mapping.items():
            assert key in codes and value in codes, (key, value)

    def test_the_ignorecase_map_the_page_uses(self) -> None:
        literal = sre_constants.LITERAL
        assert sre_constants.OP_IGNORE[literal] is sre_constants.LITERAL_IGNORE

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="CH_NEGATE is 3.14+")
    def test_ch_negate_pairs_each_category_with_its_complement(self) -> None:
        negate = sre_constants.CH_NEGATE

        assert set(negate) == set(sre_constants.CHCODES)
        assert negate[sre_constants.CATEGORY_DIGIT] is sre_constants.CATEGORY_NOT_DIGIT
        for code in sre_constants.CHCODES:
            positive = code.name.replace("_NOT_", "_")
            negative = positive.replace("CATEGORY_", "CATEGORY_NOT_", 1)
            if "_LOC_" in positive or "_UNI_" in positive:
                prefix, rest = positive.rsplit("_", 1)
                negative = f"{prefix}_NOT_{rest}"
            expected = negative if code.name == positive else positive
            assert negate[code].name == expected, code.name

    def test_ch_negate_is_3_14_plus(self) -> None:
        assert hasattr(sre_constants, "CH_NEGATE") == (sys.version_info >= (3, 14))


class TestFlagsAndLimits:
    """The flags equal `re`'s; the limits and `MAGIC` equal `_sre`'s; the
    `SRE_INFO_*` bits are the compiled header's."""

    @pytest.mark.parametrize("name", FLAG_NAMES)
    def test_each_flag_equals_the_re_flag(self, name: str) -> None:
        value = getattr(sre_constants, f"SRE_FLAG_{name}")

        assert type(value) is int
        assert value == getattr(re, name)

    def test_the_template_flag_is_3_10_to_3_12(self) -> None:
        present = sys.version_info < (3, 13)
        assert hasattr(sre_constants, "SRE_FLAG_TEMPLATE") == present
        assert hasattr(re, "TEMPLATE") == present

    def test_the_info_bits_are_in_a_literal_pattern_s_header(self) -> None:
        compiler = compiler_module()
        code = compiler._code(sre_parse.parse("abc"), 0)

        assert code[0] == sre_constants.INFO
        info_flags = code[2]
        assert info_flags & sre_constants.SRE_INFO_PREFIX
        assert info_flags & sre_constants.SRE_INFO_LITERAL
        assert not info_flags & sre_constants.SRE_INFO_CHARSET

    def test_the_limits_and_magic_are_the_matcher_s(self) -> None:
        sre = importlib.import_module("_sre")

        assert sre_constants.MAGIC == sre.MAGIC
        assert sre_constants.MAXREPEAT == sre.MAXREPEAT
        assert sre_constants.MAXGROUPS == sre.MAXGROUPS


class TestExceptions:
    """`error` is `re.error`; `PatternError` is its 3.13+ name."""

    def test_error_is_re_error(self) -> None:
        assert sre_constants.error is re.error

    def test_pattern_error_is_3_13_plus(self) -> None:
        assert hasattr(sre_constants, "PatternError") == (sys.version_info >= (3, 13))
        if sys.version_info >= (3, 13):
            assert sre_constants.PatternError is sre_constants.error


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
    """The block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "op.name == 'MAX_REPEAT'" in s)
        mutated = source.replace("op.name == 'MAX_REPEAT'", "op.name == 'MIN_REPEAT'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
