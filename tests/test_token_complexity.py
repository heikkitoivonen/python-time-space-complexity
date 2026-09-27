"""Tests for docs/stdlib/token.md.

The page prices every operation at O(1): the constants are module-level
integers, `tok_name` and `EXACT_TOKEN_TYPES` are dictionaries built once at
import, and the three predicates are one integer comparison each. Nothing on
the page takes an input whose size could grow, so the bounds are settled by
observing what each name is - a dict, an int, a comparison - rather than by
timing, and the tests concentrate on the behavioural notes beside them.

Measurement scope:

* `tok_name` and `EXACT_TOKEN_TYPES` are asserted to be plain `dict`s, the
  same object on every access, and each entry of `tok_name` to name the
  module constant holding that value.
* Every operator string in `EXACT_TOKEN_TYPES` maps to a distinct type, and
  tokenizing it alone yields an `OP` token whose `exact_type` is the value in
  the dictionary.
* `ISTERMINAL`, `ISNONTERMINAL` and `ISEOF` are asserted on both sides of
  `NT_OFFSET` and at `ENDMARKER`; `NT_OFFSET` is 256 and `N_TOKENS` is one more
  than the largest token type in `tok_name` below `NT_OFFSET`.
* The version rows are asserted on `sys.version_info`: `EXCLAMATION` and the
  `FSTRING_*` types from 3.12, `AWAIT` and `ASYNC` up to 3.12 only, and the
  `TSTRING_*` types from 3.14. That the values are renumbered between releases
  is asserted by `token.NL`, which is 62 on 3.10 and 3.11, 65 on 3.12, 63 on
  3.13 and 66 on 3.14 (Lib/token.py on v3.10.19, v3.11.14, v3.12.12, v3.13.11
  and v3.14.2).
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That the dictionaries are built once at import is read from Lib/token.py,
  where both are module-level literals or comprehensions; the tests show only
  that repeated access returns the same object.
"""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
import sys
import textwrap
import token
import tokenize

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "token.md"
EXPECTED_BLOCKS = 2

NL_BY_VERSION = {(3, 10): 62, (3, 11): 62, (3, 12): 65, (3, 13): 63, (3, 14): 66}


class TestLookupsAreDicts:
    """`tok_name[type]` and `EXACT_TOKEN_TYPES[string]` | O(1) | O(1): both are
    dictionaries built at import, not functions that scan the constants."""

    def test_tok_name_is_a_dict_held_by_the_module(self) -> None:
        assert type(token.tok_name) is dict
        assert token.tok_name is token.tok_name

    def test_tok_name_names_the_constant_holding_each_value(self) -> None:
        for value, name in token.tok_name.items():
            assert getattr(token, name) == value

    def test_exact_token_types_is_a_dict_held_by_the_module(self) -> None:
        assert type(token.EXACT_TOKEN_TYPES) is dict
        assert token.EXACT_TOKEN_TYPES is token.EXACT_TOKEN_TYPES


class TestOperatorConstants:
    """Operator constants | one per key of `EXACT_TOKEN_TYPES`, and
    `TokenInfo.exact_type` gives the same answer as the dictionary."""

    def test_each_operator_string_has_its_own_type(self) -> None:
        values = list(token.EXACT_TOKEN_TYPES.values())

        assert len(set(values)) == len(values)
        assert all(value in token.tok_name for value in values)
        assert token.OP not in values

    def test_exact_type_agrees_with_the_dictionary(self) -> None:
        checked = 0
        for string, expected in token.EXACT_TOKEN_TYPES.items():
            # Only the first token is taken: an opening bracket alone never closes.
            first = next(tokenize.generate_tokens(io.StringIO(string + "\n").readline))

            assert first.type == token.OP, (string, token.tok_name[first.type])
            assert first.string == string
            assert first.exact_type == expected
            checked += 1

        assert checked == len(token.EXACT_TOKEN_TYPES) >= 47


class TestPredicatesAndOffsets:
    """`ISTERMINAL`, `ISNONTERMINAL`, `ISEOF` | O(1); `NT_OFFSET` is 256 and
    `N_TOKENS` is one more than the largest token type."""

    def test_nt_offset_is_256(self) -> None:
        assert token.NT_OFFSET == 256

    def test_the_predicates_split_at_nt_offset(self) -> None:
        for value in (0, token.NAME, token.OP, token.NT_OFFSET - 1):
            assert token.ISTERMINAL(value)
            assert not token.ISNONTERMINAL(value)
        for value in (token.NT_OFFSET, token.NT_OFFSET + 1):
            assert not token.ISTERMINAL(value)
            assert token.ISNONTERMINAL(value)

    def test_iseof_is_endmarker_only(self) -> None:
        assert token.ISEOF(token.ENDMARKER)
        assert not any(token.ISEOF(v) for v in token.tok_name if v != token.ENDMARKER)

    def test_n_tokens_is_one_past_the_largest_type(self) -> None:
        types = [v for v in token.tok_name if v < token.NT_OFFSET and v != token.N_TOKENS]

        assert token.N_TOKENS == max(types) + 1


class TestVersionRows:
    """The Python 3.12+, 3.13+ and 3.14+ rows, and the renumbering the page
    warns about."""

    @pytest.mark.parametrize(
        "name", ["EXCLAMATION", "FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"]
    )
    def test_added_in_312(self, name: str) -> None:
        assert hasattr(token, name) == (sys.version_info >= (3, 12))

    @pytest.mark.parametrize("name", ["AWAIT", "ASYNC"])
    def test_removed_in_313(self, name: str) -> None:
        assert hasattr(token, name) == (sys.version_info < (3, 13))

    @pytest.mark.parametrize("name", ["TSTRING_START", "TSTRING_MIDDLE", "TSTRING_END"])
    def test_added_in_314(self, name: str) -> None:
        assert hasattr(token, name) == (sys.version_info >= (3, 14))

    def test_values_are_renumbered_between_releases(self) -> None:
        assert len(set(NL_BY_VERSION.values())) > 1
        assert token.NL == NL_BY_VERSION[sys.version_info[:2]]


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "('NEWLINE', '')," in s)
        mutated = source.replace("    ('NEWLINE', ''),\n", "", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
