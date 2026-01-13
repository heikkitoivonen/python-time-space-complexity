"""Tests for documentation content and structure."""

import json
from pathlib import Path


def test_data_files_exist():
    """Test that all required data files exist."""
    data_dir = Path(__file__).parent.parent / "data"
    assert (data_dir / "builtins.json").exists(), "builtins.json not found"
    assert (data_dir / "stdlib.json").exists(), "stdlib.json not found"


def test_builtins_json_valid():
    """Test that builtins.json is valid JSON."""
    data_file = Path(__file__).parent.parent / "data" / "builtins.json"
    with open(data_file) as f:
        data = json.load(f)
    assert isinstance(data, dict), "builtins.json should contain a dict"
    assert len(data) > 0, "builtins.json should not be empty"


def test_stdlib_json_valid():
    """Test that stdlib.json is valid JSON."""
    data_file = Path(__file__).parent.parent / "data" / "stdlib.json"
    with open(data_file) as f:
        data = json.load(f)
    assert isinstance(data, dict), "stdlib.json should contain a dict"
    assert len(data) > 0, "stdlib.json should not be empty"


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
