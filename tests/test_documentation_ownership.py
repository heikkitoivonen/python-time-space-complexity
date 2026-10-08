"""Package overviews link to dedicated references instead of pricing their types.

These checks cover page ownership, not the complexity claims or examples on the
destination pages; those belong to the type-specific tests.
The collections page's own examples run in tests/test_collections_complexity.py,
the defaultdict page's in tests/test_defaultdict_complexity.py, the Counter
page's in tests/test_counter_complexity.py, and the ElementTree page's in
tests/test_xml_etree_elementtree_complexity.py."""

import collections
import re
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
    text = (DOCS / "collections.md").read_text(encoding="utf-8")
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
    text = (DOCS / page).read_text(encoding="utf-8")
    assert "```" not in text and "|" not in text
    for target in targets:
        assert f"]({target})" in text
        assert (DOCS / target).is_file()


def test_xml_parsers_expat_reexports_pyexpat() -> None:
    """xml.md sends xml.parsers.expat readers to the pyexpat page: the package
    module is a separate object whose parser API is pyexpat's own objects."""
    import pyexpat
    import xml.parsers.expat as expat

    assert "`xml.parsers.expat`, which re-exports `pyexpat`" in (DOCS / "xml.md").read_text(
        encoding="utf-8"
    )
    assert expat is not pyexpat
    for name in ("ParserCreate", "ExpatError", "XMLParserType", "ErrorString", "errors", "model"):
        assert getattr(expat, name) is getattr(pyexpat, name)
