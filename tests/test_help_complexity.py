"""Tests for docs/builtins/help.md.

`help` is a `_sitebuiltins._Helper` instance that `site.sethelper()` installs
into builtins. Its `__call__` imports `pydoc` and returns
`pydoc.help(*args, **kwds)`, where `pydoc.help` is a `pydoc.Helper` with no
streams of its own, so it reads `sys.stdin` and sends every page to
`pydoc.pager`. The page's bounds for each kind of request are the `pydoc`
page's, and `tests/test_pydoc_complexity.py` measures them; this file settles
what `help` itself adds - the forwarding, the routing of each request to the
`Helper` method the pydoc page prices, where the text goes, and the
interactive loop - by observation, with recording stand-ins for `pydoc.pager`
and the `Helper` methods in this process, and child interpreters where the
claim is about a fresh process or its standard streams. Nothing here needs a
stopwatch.

Measurement scope:

* The bare name is an instance of `_sitebuiltins._Helper`, not a function,
  and its `repr()` is the two-sentence hint. Under `-S`, `help(len)` raises
  `NameError`. In a child interpreter `pydoc` is not in `sys.modules` after
  `repr(help)` and is after `help(len)`.
* With `pydoc.help` replaced by a recorder, `help(1, 2, k=3)` passes the
  arguments through and returns the recorder's value; the real call returns
  `None`.
* With stdin on the null device and stdout a pipe, `help(len)` in a child
  interpreter writes its page to stdout, without overstrike.
* Two `help()` calls on one class call `TextDoc.docclass` once each, so
  nothing is cached between calls; `help()` of an instance renders its
  class's page, titled `<class> ... object`.
* Strings: `help('')` renders the page for `str`; `help('hello')` prints `No Python documentation found for
  'hello'`; `help('json.decoder.JSONDecoder')` calls `pydoc.locate()` with
  that name; `help('if')` and `help('NUMBERS')` call `Helper.showtopic()`
  with the string and `help('%')` calls `Helper.showsymbol('%')`; `help('keywords')`,
  `help('symbols')` and `help('topics')` call the three list methods;
  `help('modules')` calls `listmodules()` and `help('modules spam')`
  `listmodules('spam')`. In a child interpreter `help('colorsys')` imports
  `colorsys`.
* The interactive helper, fed `sys.stdin` from a pipe in a child
  interpreter: three lines ending in `q` print three `help>` prompts and
  answer the first two; `q` and `quit` stop it on every version, `exit` from
  3.13; the end of input stops it; an empty line stops it before 3.13.12 and
  3.14.3 and is skipped from those releases (3.13.11 stops, 3.13.12 and
  3.14.4 continue, observed locally).
* `__doc__` read twice is the same object for a Python function and class,
  and two equal but distinct strings for `len`, `str` and `list.append`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(D), O(x² + D), O(T)/O(z), O(N log N) and O(N + S) bounds and their
  space, including the O(F) source read and the full `repr()` counted in w: `help` reaches them through the `Helper` methods asserted above,
  and `tests/test_pydoc_complexity.py` measures those methods.
* Import cost, which the page excludes, and the first-call import of
  `pydoc` itself.
* A terminal pager such as `less`, which needs a terminal; the tests only
  see the plain pager, with stdin and stdout both non-terminals. That either
  one suffices is read from `get_pager()` in Lib/pydoc.py. `help()` at the default REPL's prompt (and its F1
  key) is not driven here.
* That a built-in's `__doc__` is linear in its length is read from
  `_PyType_GetDocFromInternalDoc()` in Objects/typeobject.c, which builds the
  string with `PyUnicode_FromString()`; lengths were not varied.
* The 3.14.3 boundary is from the backport's position on the 3.14 branch
  (first release after 3.14.2); 3.14.3 itself was not run.
"""

from __future__ import annotations

import builtins
import os
import pathlib
import pydoc
import re
import subprocess
import sys
import textwrap
import types
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "help.md"
EXPECTED_BLOCKS = 6

HINT = "Type help() for interactive help, or help(object) for help about object."


def run_python(
    source: str, cwd: pathlib.Path, *flags: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter in `cwd`; stdin is `stdin`, or the null device."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, *flags, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        input=stdin,
        stdin=subprocess.DEVNULL if stdin is None else None,
        env={k: v for k, v in os.environ.items() if k not in ("PAGER", "MANPAGER")},
        check=False,
    )


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace `pydoc.pager` with a recorder and return the texts it receives."""
    received: list[str] = []

    def record(text: str, title: str = "") -> None:
        received.append(text)

    monkeypatch.setattr(pydoc, "pager", record)
    return received


class TestTheBareName:
    """Row: the bare name's `repr()` is a hint naming `help()` and
    `help(object)`. Prose: it is a callable instance, not a function, and
    `site` installs it, so it is absent under `-S`."""

    def test_an_instance_not_a_function(self) -> None:
        helper: Any = builtins.help
        assert type(helper).__name__ == "_Helper"
        assert type(helper).__module__ == "_sitebuiltins"
        assert not isinstance(helper, types.FunctionType)
        assert callable(helper)

    def test_the_hint(self) -> None:
        assert repr(builtins.help) == HINT

    def test_absent_without_site(self, tmp_path: pathlib.Path) -> None:
        result = run_python("help(len)", tmp_path, "-S")

        assert result.returncode == 1
        assert "NameError: name 'help' is not defined" in result.stderr


class TestTheCallForwardsToPydoc:
    """Intro: calling `help` imports `pydoc` the first time and hands the
    request to `pydoc.help`; it returns `None`."""

    def test_pydoc_is_imported_by_the_first_call(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import sys

            repr(help)
            print('pydoc' in sys.modules)
            help(len)
            print('pydoc' in sys.modules)
            """,
            tmp_path,
        )

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0] == "False"
        assert lines[-1] == "True"

    def test_arguments_and_result_pass_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        marker = object()

        def record(*args: Any, **kwds: Any) -> object:
            calls.append((args, kwds))
            return marker

        monkeypatch.setattr(pydoc, "help", record)

        helper: Any = builtins.help
        assert helper(1, 2, k=3) is marker
        assert calls == [((1, 2), {"k": 3})]

    def test_the_real_call_returns_none(self, pages: list[str]) -> None:
        assert builtins.help(len) is None
        assert len(pages) == 1


class TestWhereTheOutputGoes:
    """Prose: when standard input or output is not a terminal, the page goes
    to `sys.stdout` through the plain pager."""

    def test_not_a_terminal_writes_plain_text_to_stdout(self, tmp_path: pathlib.Path) -> None:
        result = run_python("help(len)", tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("Help on built-in function len in module builtins:")
        assert "\b" not in result.stdout


class Base:
    def method(self) -> None:
        """Do something."""


class Child(Base):
    pass


class TestObjects:
    """Row: `help(object)` renders the object's documentation, and an
    instance is documented through its class. Intro: nothing is cached, so
    every call renders again."""

    def test_every_call_renders_the_class_again(
        self, pages: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        documented: list[object] = []
        original = pydoc.TextDoc.docclass

        def counting(self: pydoc.TextDoc, object: type, *args: Any, **kwds: Any) -> str:
            documented.append(object)
            return original(self, object, *args, **kwds)

        monkeypatch.setattr(pydoc.TextDoc, "docclass", counting)

        builtins.help(Child)
        builtins.help(Child)

        assert documented.count(Child) == 2
        assert all("Methods inherited from" in page for page in pages)

    def test_an_instance_gets_its_class_page(self, pages: list[str]) -> None:
        builtins.help(Child())

        assert pages[0].startswith(f"Help on Child in module {__name__} object:")
        assert "Methods inherited from" in pages[0]


class TestStringsAreNames:
    """Rows: a string is a name to look up; keywords, symbols and topics show
    their text; the three list requests and `'modules'` list. Each is
    checked to reach the `Helper` method or `pydoc` function the pydoc page
    prices."""

    def test_a_name_nothing_has(self, capsys: pytest.CaptureFixture[str], pages: list[str]) -> None:
        builtins.help("hello")

        assert "No Python documentation found for 'hello'" in capsys.readouterr().out
        assert pages == []

    def test_the_empty_string_documents_str(self, pages: list[str]) -> None:
        builtins.help("")

        assert pages[0].startswith("Help on class str in module builtins:")

    def test_a_dotted_name_is_located(
        self, pages: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        located: list[str] = []
        original = pydoc.locate

        def counting(path: str, forceload: bool = False) -> object:
            located.append(path)
            return original(path, forceload)

        monkeypatch.setattr(pydoc, "locate", counting)

        builtins.help("json.decoder.JSONDecoder")

        assert located == ["json.decoder.JSONDecoder"]
        assert pages[0].startswith("Help on class JSONDecoder in json.decoder:")

    def test_a_module_name_is_imported(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import sys

            print('colorsys' in sys.modules)
            help('colorsys')
            print('colorsys' in sys.modules)
            """,
            tmp_path,
        )

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0] == "False"
        assert lines[-1] == "True"

    @pytest.mark.parametrize(
        ("request_", "method", "args"),
        [
            ("if", "showtopic", ("if",)),
            ("NUMBERS", "showtopic", ("NUMBERS",)),
            ("%", "showsymbol", ("%",)),
            ("keywords", "listkeywords", ()),
            ("symbols", "listsymbols", ()),
            ("topics", "listtopics", ()),
            ("modules", "listmodules", ()),
            ("modules spam", "listmodules", ("spam",)),
        ],
    )
    def test_requests_reach_the_priced_method(
        self, request_: str, method: str, args: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, tuple[Any, ...]]] = []

        def make(name: str) -> Any:
            def record(self: pydoc.Helper, *a: Any, **k: Any) -> None:
                calls.append((name, a))

            return record

        for name in (
            "showtopic",
            "showsymbol",
            "listkeywords",
            "listsymbols",
            "listtopics",
            "listmodules",
        ):
            monkeypatch.setattr(pydoc.Helper, name, make(name))

        builtins.help(request_)

        assert calls == [(method, args)]


def interact(stdin: str, cwd: pathlib.Path) -> str:
    """Run `help()` in a child interpreter reading `stdin`; return its stdout."""
    result = run_python("help()\nprint('returned')", cwd, stdin=stdin)
    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith("returned\n"), result.stdout
    return result.stdout


LEN = "Help on built-in function len in module builtins"


class TestTheInteractiveHelper:
    """Row: `help()` reads one request per line from `sys.stdin`. Prose: it
    stops at `q`, `quit` or `exit` (Version Notes: `exit` from 3.13), or the
    end of input; an empty line stops it before 3.13.12 and 3.14.3 and returns
    to the prompt from those releases."""

    def test_one_request_per_line(self, tmp_path: pathlib.Path) -> None:
        output = interact("len\nkeywords\nq\n", tmp_path)

        assert output.count("\nhelp> ") == 3
        assert LEN in output
        assert "nonlocal" in output

    @pytest.mark.parametrize("word", ["q", "quit", "exit"])
    def test_a_quit_word_stops_it(self, word: str, tmp_path: pathlib.Path) -> None:
        output = interact(f"{word}\nlen\n", tmp_path)

        stops = word != "exit" or sys.version_info >= (3, 13)
        assert (LEN not in output) == stops, output

    def test_the_end_of_input_stops_it(self, tmp_path: pathlib.Path) -> None:
        output = interact("len\n", tmp_path)

        assert LEN in output
        assert "You are now leaving help" in output

    def test_an_empty_line(self, tmp_path: pathlib.Path) -> None:
        output = interact("\nlen\nq\n", tmp_path)

        continues = sys.version_info >= (3, 14, 3) or (3, 13, 12) <= sys.version_info < (3, 14)
        assert (LEN in output) == continues, output


class TestReadingTheDocstring:
    """Prose: `__doc__` of a function or class written in Python returns the
    string it stores; a built-in one builds a new string on each read."""

    def test_python_functions_and_classes_return_the_stored_string(self) -> None:
        assert Base.method.__doc__ is not None
        assert Base.method.__doc__ is Base.method.__doc__
        assert TestReadingTheDocstring.__doc__ is TestReadingTheDocstring.__doc__

    def test_builtin_functions_and_types_build_a_new_string(self) -> None:
        for documented in (len, str, list.append):
            first, second = documented.__doc__, documented.__doc__
            assert first is not None
            assert first == second
            assert first is not second


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
    """Each block runs in its own subprocess and working directory with stdin
    on the null device, and must exit 0 without writing to stdout: every page
    `help()` produces is captured inside the block."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks():
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_python(source, workdir)
            if result.returncode != 0 or result.stdout != "":
                failures.append(
                    f"{PAGE.name}:{line} exited {result.returncode}\n"
                    f"stdout: {result.stdout[:500]}\nstderr: {result.stderr.strip()}"
                )

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== 3  # one prompt" in s)
        mutated = source.replace("== 3  # one prompt", "== 4  # one prompt", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = run_python(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
