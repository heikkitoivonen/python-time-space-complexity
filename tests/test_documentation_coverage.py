"""Live interpreter coverage and navigation retention, including removed modules."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.audit_documentation import generate_audit_report

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("category", ["builtins", "stdlib"])
def test_live_coverage(category: str) -> None:
    report = generate_audit_report(ROOT)
    assert report[category]["missing"] == [], f"Missing {category}: {report[category]['missing']}"


def _navigation_paths(root: Path) -> set[str]:
    # BaseLoader reads navigation without resolving MkDocs' Python-name tags.
    config = yaml.load((root / "mkdocs.yml").read_text(), Loader=yaml.BaseLoader)

    def paths(node: object) -> set[str]:
        if isinstance(node, str):
            return {node} if node.endswith(".md") else set()
        if isinstance(node, dict):
            return set().union(*(paths(value) for value in node.values()))
        if isinstance(node, list):
            return set().union(*(paths(value) for value in node))
        raise AssertionError(f"Unexpected navigation entry: {node!r}")

    result = paths(config["nav"])
    assert "builtins/list.md" in result
    assert "stdlib/cgi.md" in result
    assert "versions/py310.md" in result
    return result


def _assert_navigation_targets_exist(root: Path) -> None:
    missing = sorted(
        path for path in _navigation_paths(root) if not (root / "docs" / path).is_file()
    )
    assert missing == [], f"Missing navigation targets: {missing}"


def test_navigation_targets_exist() -> None:
    _assert_navigation_targets_exist(ROOT)


def test_documented_files_match_mkdocs_nav() -> None:
    documented = {
        path.relative_to(ROOT / "docs").as_posix()
        for category in ("builtins", "stdlib")
        for path in (ROOT / "docs" / category).glob("*.md")
    }
    missing = sorted(documented - _navigation_paths(ROOT))
    assert missing == [], f"Pages absent from navigation: {missing}"


@pytest.fixture
def documentation_tree(tmp_path: Path) -> Path:
    """Copy page paths only: discovery and navigation do not inspect page contents."""
    for source in (ROOT / "docs").rglob("*.md"):
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    shutil.copyfile(ROOT / "mkdocs.yml", tmp_path / "mkdocs.yml")
    return tmp_path


@pytest.mark.parametrize(
    ("category", "filename", "item"),
    [("builtins", "len", "len"), ("stdlib", "json", "json")],
)
def test_deleted_page_is_reported(
    documentation_tree: Path, category: str, filename: str, item: str
) -> None:
    assert generate_audit_report(documentation_tree)[category]["missing"] == []
    page = documentation_tree / "docs" / category / f"{filename}.md"
    assert page.is_file()
    page.unlink()
    assert not page.exists()
    assert generate_audit_report(documentation_tree)[category]["missing"] == [item]


def test_new_interpreter_module_requires_a_page(
    documentation_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "coverage_probe_module"
    assert name not in sys.stdlib_module_names
    monkeypatch.setattr(sys, "stdlib_module_names", sys.stdlib_module_names | {name})
    assert generate_audit_report(documentation_tree)["stdlib"]["missing"] == [name]
    (documentation_tree / "docs" / "stdlib" / f"{name}.md").touch()
    assert generate_audit_report(documentation_tree)["stdlib"]["missing"] == []


@pytest.mark.parametrize("path", ["stdlib/cgi.md", "versions/py310.md"])
def test_deleted_historical_page_fails_navigation_check(
    documentation_tree: Path, path: str
) -> None:
    _assert_navigation_targets_exist(documentation_tree)
    page = documentation_tree / "docs" / path
    assert page.is_file()
    page.unlink()
    assert not page.exists()
    with pytest.raises(AssertionError, match=path):
        _assert_navigation_targets_exist(documentation_tree)


def test_audit_command_prints_without_writing_files(documentation_tree: Path) -> None:
    scripts = documentation_tree / "scripts"
    scripts.mkdir()
    script = scripts / "audit_documentation.py"
    shutil.copyfile(ROOT / "scripts" / script.name, script)
    before = set(documentation_tree.rglob("*"))
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=documentation_tree,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "DOCUMENTATION COVERAGE AUDIT" in result.stdout
    assert "BUILTINS" in result.stdout
    assert "STDLIB MODULES" in result.stdout
    assert "Coverage: 100.0%" in result.stdout
    assert set(documentation_tree.rglob("*")) == before
