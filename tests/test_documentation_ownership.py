"""Package overviews link to dedicated references and retain working examples.

Only the explicitly listed pages are executed. Their examples use in-memory
collections in the subprocess's temporary working directory.
These checks cover example execution and page ownership, not every complexity
claim on the destination pages; those belong to the type-specific tests.
The collections page's own examples run in tests/test_collections_complexity.py,
and the ElementTree page's in tests/test_xml_etree_elementtree_complexity.py.
"""

import collections
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

DOCS = Path(__file__).parent.parent / "docs" / "stdlib"
DEDICATED = {
    "deque": "deque.md",
    "defaultdict": "defaultdict.md",
    "Counter": "counter.md",
    "namedtuple": "namedtuple.md",
    "OrderedDict": "ordereddict.md",
}


def test_collections_types_have_one_documentation_owner() -> None:
    """collections.md links each type with its own page from a section of its
    own, with no table there, and prices ChainMap and the User* wrappers in
    its own Complexity Reference."""
    text = (DOCS / "collections.md").read_text()
    sections = dict(re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S))
    subsections = dict(re.findall(r"^### ([^\n]+)\n(.*?)(?=^#{2,3} |\Z)", text, re.M | re.S))
    local = {"ChainMap", "UserDict", "UserList", "UserString"}
    exported = {name.lower() for name in collections.__all__}
    assert {name.lower() for name in DEDICATED.keys() | local} == exported
    for name, target in DEDICATED.items():
        section = sections[name]
        assert f"]({target})" in section
        assert "```" not in section and "|" not in section
        assert name not in subsections
        assert (DOCS / target).is_file()
    for name in local:
        assert "| Operation | Time | Space | Notes |" in subsections[name]
    assert "](collections.abc.md)" in sections["collections.abc"]
    assert (DOCS / "collections.abc.md").is_file()


@pytest.mark.parametrize(
    ("page", "targets"),
    [
        ("concurrent.md", ["concurrent_futures.md", "concurrent.interpreters.md"]),
        ("xml.md", ["xml.dom.md", "xml.sax.md", "xml.etree.elementtree.md", "pyexpat.md"]),
    ],
)
def test_package_overviews_delegate_api_details(page: str, targets: list[str]) -> None:
    text = (DOCS / page).read_text()
    assert "```" not in text and "|" not in text
    for target in targets:
        assert f"]({target})" in text
        assert (DOCS / target).is_file()


def _blocks(page: str) -> list[tuple[int, str]]:
    text = (DOCS / page).read_text()
    return [
        (text.count("\n", 0, match.start()) + 1, textwrap.dedent(match.group(1)))
        for match in re.finditer(r"^```python\n(.*?)^```", text, re.M | re.S)
    ]


def _run(source: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    ("page", "count"),
    [
        ("counter.md", 11),
        ("defaultdict.md", 11),
    ],
)
def test_owned_examples_run(page: str, count: int, tmp_path: Path) -> None:
    blocks = _blocks(page)
    assert len(blocks) == count
    for line, source in blocks:
        cwd = tmp_path / str(line)
        cwd.mkdir()
        result = _run(source, cwd)
        assert result.returncode == 0, f"{page}:{line}\n{result.stdout}\n{result.stderr}"


def test_example_runner_reports_broken_code(tmp_path: Path) -> None:
    source = _blocks("counter.md")[0][1]
    broken = source.replace("c = Counter(", "other = Counter(", 1)
    assert broken != source
    result = _run(broken, tmp_path)
    assert result.returncode != 0 and "NameError" in result.stderr
