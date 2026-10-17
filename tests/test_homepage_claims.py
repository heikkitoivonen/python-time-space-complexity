"""Tests for the test-suite figure on docs/index.md and its translations.

The "Why Trust This Documentation?" section gives the size of the suite as more
than a stated number of unit tests. The test collects the whole suite in a
separate pytest process, with no marker or keyword selection and with
`PYTEST_ADDOPTS` cleared, and asserts the collected count exceeds the figure,
so deleting tests below it fails. Each translated homepage must state the same
figure, in its own digit grouping: `16,000`, `16 000` or `16000`.

Collected tests include ones that skip on the running interpreter or platform.
Module-level skips are not collected, so the count varies: Windows skips the
Unix-only modules (curses, fcntl, posix, pty, readline, select, termios, tty)
at import, and older Pythons skip the modules added since. CI runs this test
on every supported Python on Linux and on the newest on macOS and Windows.

Not settled here: that every collected test validates a complexity claim -
some check site structure, translations or tooling.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

from scripts.validate_translations import LOCALES

ROOT = pathlib.Path(__file__).parent.parent
DOCS = ROOT / "docs"
SENTENCE = re.compile(r"A suite of more than ([\d,]+) unit tests validates complexity claims")
GROUPED = re.compile(r"\d{1,3}(?:[, ]\d{3})+|\d{4,}")


def _figure(text: str) -> int:
    match = SENTENCE.search(text)
    assert match, "the homepage no longer states how many tests there are"
    return int(match.group(1).replace(",", ""))


def _trust_paragraph(text: str) -> str:
    """The paragraph naming the reviewing agents, the same in every locale."""
    paragraphs = [p for p in text.split("\n\n") if "Gemini CLI" in p]
    assert len(paragraphs) == 1
    return paragraphs[0]


def test_the_suite_has_more_tests_than_the_homepage_says() -> None:
    figure = _figure((DOCS / "index.md").read_text(encoding="utf-8"))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env={k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"},
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    collected = re.search(r"^=+ (\d+) tests collected", result.stdout, re.MULTILINE)

    assert result.returncode == 0 and collected, result.stdout[-2000:] + result.stderr
    assert int(collected.group(1)) > figure


@pytest.mark.parametrize("locale", LOCALES)
def test_each_translation_states_the_same_figure(locale: str) -> None:
    figure = _figure((DOCS / "index.md").read_text(encoding="utf-8"))
    paragraph = _trust_paragraph((DOCS / locale / "index.md").read_text(encoding="utf-8"))
    numbers = [int(re.sub(r"[, ]", "", n)) for n in GROUPED.findall(paragraph)]

    assert numbers == [figure], paragraph
