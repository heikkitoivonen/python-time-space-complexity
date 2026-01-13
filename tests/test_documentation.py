"""Tests for documentation content and structure."""

import json
from pathlib import Path


def test_documentation_files_exist():
    """Test that required documentation files exist."""
    docs_dir = Path(__file__).parent.parent / "docs"

    # Check main pages
    assert (docs_dir / "index.md").exists(), "index.md not found"

    # Check built-in types
    builtins_dir = docs_dir / "builtins"
    assert (builtins_dir / "index.md").exists()
    assert (builtins_dir / "list.md").exists()
    assert (builtins_dir / "dict.md").exists()

    # Check stdlib
    stdlib_dir = docs_dir / "stdlib"
    assert (stdlib_dir / "index.md").exists()
    assert (stdlib_dir / "collections.md").exists()

    # Check implementations
    impl_dir = docs_dir / "implementations"
    assert (impl_dir / "index.md").exists()
    assert (impl_dir / "cpython.md").exists()

    # Check versions
    versions_dir = docs_dir / "versions"
    assert (versions_dir / "index.md").exists()
    assert (versions_dir / "py311.md").exists()


def test_project_files_exist():
    """Test that required project files exist."""
    project_root = Path(__file__).parent.parent
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "mkdocs.yml").exists()
    assert (project_root / "Makefile").exists()
    assert (project_root / "README.md").exists()
    assert (project_root / "CONTRIBUTING.md").exists()
    assert (project_root / "LICENSE").exists()


def test_mkdocs_yml_exists():
    """Test that mkdocs.yml exists and is readable."""
    mkdocs_file = Path(__file__).parent.parent / "mkdocs.yml"
    assert mkdocs_file.exists(), "mkdocs.yml not found"
    assert mkdocs_file.is_file(), "mkdocs.yml is not a file"
    # Check it's readable and not empty
    content = mkdocs_file.read_text()
    assert len(content) > 0, "mkdocs.yml is empty"
    assert "site_name" in content, "mkdocs.yml missing site_name"
    assert "theme" in content, "mkdocs.yml missing theme"


def test_audit_report_exists():
    """Test that documentation audit report exists."""
    audit_file = Path(__file__).parent.parent / "data" / "documentation_audit.json"
    assert audit_file.exists(), f"Audit report not found at {audit_file}"


def test_audit_report_structure():
    """Test that audit report has correct structure."""
    audit_file = Path(__file__).parent.parent / "data" / "documentation_audit.json"
    with open(audit_file) as f:
        report = json.load(f)

    # Check top-level keys
    assert "builtins" in report
    assert "stdlib" in report
    assert "summary" in report

    # Check builtins structure
    assert "total" in report["builtins"]
    assert "documented" in report["builtins"]
    assert "coverage_percent" in report["builtins"]
    assert "missing" in report["builtins"]

    # Check stdlib structure
    assert "total" in report["stdlib"]
    assert "documented" in report["stdlib"]
    assert "coverage_percent" in report["stdlib"]
    assert "missing" in report["stdlib"]


def test_documented_files_match_mkdocs_nav():
    """Test that all documented files are in mkdocs.yml navigation."""
    docs_dir = Path(__file__).parent.parent / "docs"
    mkdocs_file = Path(__file__).parent.parent / "mkdocs.yml"

    # Get documented files
    documented_builtins = {
        f.stem
        for f in (docs_dir / "builtins").glob("*.md")
        if f.stem != "index"
    }
    documented_stdlib = {
        f.stem for f in (docs_dir / "stdlib").glob("*.md") if f.stem != "index"
    }

    # Read mkdocs.yml
    mkdocs_content = mkdocs_file.read_text()

    # Check that all documented files are referenced
    for builtin in documented_builtins:
        assert builtin in mkdocs_content, (
            f"Builtin '{builtin}' documented but not in mkdocs.yml nav"
        )

    for stdlib_mod in documented_stdlib:
        assert stdlib_mod in mkdocs_content, (
            f"Stdlib module '{stdlib_mod}' documented but not in mkdocs.yml nav"
        )


def test_minimum_builtin_coverage():
    """Test that minimum builtin coverage is maintained."""
    audit_file = Path(__file__).parent.parent / "data" / "documentation_audit.json"
    with open(audit_file) as f:
        report = json.load(f)

    # Coverage should not decrease below current level
    min_coverage = 5.0  # Current: 5.3%
    current = report["builtins"]["coverage_percent"]
    assert current >= min_coverage, (
        f"Builtin coverage dropped: {current}% < {min_coverage}%"
    )


def test_minimum_stdlib_coverage():
    """Test that minimum stdlib coverage is maintained."""
    audit_file = Path(__file__).parent.parent / "data" / "documentation_audit.json"
    with open(audit_file) as f:
        report = json.load(f)

    # Coverage should not decrease below current level
    min_coverage = 2.5  # Current: 3.6%
    current = report["stdlib"]["coverage_percent"]
    assert current >= min_coverage, (
        f"Stdlib coverage dropped: {current}% < {min_coverage}%"
    )
