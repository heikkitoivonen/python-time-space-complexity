"""Package overviews link to dedicated references and retain working examples.

Only the explicitly listed pages are executed. Their examples use in-memory
collections and XML files in the subprocess's temporary working directory.
The ElementTree file-reading example receives a small XML fixture.
These checks cover example execution and page ownership, not every complexity
claim on the destination pages; those belong to the type-specific tests.
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
    "DefaultDict": "defaultdict.md",
    "Counter": "counter.md",
    "NamedTuple": "namedtuple.md",
    "OrderedDict": "ordereddict.md",
}


def test_collections_types_have_one_documentation_owner() -> None:
    text = (DOCS / "collections.md").read_text()
    sections = dict(re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S))
    local = {"ChainMap", "UserDict", "UserList", "UserString"}
    exported = {name.lower() for name in collections.__all__}
    assert {name.lower() for name in DEDICATED.keys() | local} == exported
    for heading, target in DEDICATED.items():
        section = sections[heading]
        assert f"]({target})" in section
        assert "```" not in section and "|" not in section
        assert (DOCS / target).is_file()
    for heading in local:
        assert "|" in sections[heading]


@pytest.mark.parametrize(
    ("page", "targets"),
    [
        ("concurrent.md", ["concurrent_futures.md"]),
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
        ("collections.md", 1),
        ("counter.md", 11),
        ("defaultdict.md", 11),
        ("xml.etree.elementtree.md", 3),
    ],
)
def test_owned_examples_run(page: str, count: int, tmp_path: Path) -> None:
    blocks = _blocks(page)
    assert len(blocks) == count
    for line, source in blocks:
        cwd = tmp_path / str(line)
        cwd.mkdir()
        (cwd / "data.xml").write_text('<root><item id="1">A</item></root>')
        result = _run(source, cwd)
        assert result.returncode == 0, f"{page}:{line}\n{result.stdout}\n{result.stderr}"
        if page == "collections.md":
            assert result.stdout.splitlines() == ["60", "3"]
        if page == "xml.etree.elementtree.md" and "output.xml" in source:
            import xml.etree.ElementTree as ET

            root = ET.parse(cwd / "output.xml").getroot()
            assert root.attrib == {"updated": "True"}
            assert [(item.get("id"), item.text) for item in root] == [("1", "A"), ("2", "B")]


def test_example_runner_reports_broken_code(tmp_path: Path) -> None:
    source = _blocks("collections.md")[0][1]
    broken = source.replace("config = ChainMap", "other = ChainMap", 1)
    assert broken != source
    result = _run(broken, tmp_path)
    assert result.returncode != 0 and "NameError" in result.stderr
