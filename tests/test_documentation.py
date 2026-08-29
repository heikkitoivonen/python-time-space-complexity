"""Tests for documentation content and structure."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


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
    assert (project_root / "LICENSE.txt").exists()


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
    with open(audit_file, encoding="utf-8") as f:
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
        f.stem for f in (docs_dir / "builtins").glob("*.md") if f.stem != "index"
    }
    documented_stdlib = {f.stem for f in (docs_dir / "stdlib").glob("*.md") if f.stem != "index"}

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
    with open(audit_file, encoding="utf-8") as f:
        report = json.load(f)

    # Coverage should not decrease below current level
    min_coverage = 100.0  # Current: 100.0% - every builtin has a page
    current = report["builtins"]["coverage_percent"]
    assert current >= min_coverage, f"Builtin coverage dropped: {current}% < {min_coverage}%"


def test_minimum_stdlib_coverage():
    """Test that minimum stdlib coverage is maintained."""
    audit_file = Path(__file__).parent.parent / "data" / "documentation_audit.json"
    with open(audit_file, encoding="utf-8") as f:
        report = json.load(f)

    # Coverage should not decrease below current level
    min_coverage = 100.0  # Current: 100.0% - every stdlib module has a page
    current = report["stdlib"]["coverage_percent"]
    assert current >= min_coverage, f"Stdlib coverage dropped: {current}% < {min_coverage}%"


def test_mkdocs_build_valid(tmp_path):
    """Test that mkdocs configuration and markdown files are valid.

    Builds into a temporary directory rather than the default ``site/``: the
    site ships as one self-contained build per locale (scripts/build_site.py),
    so writing a combined build to ``site/`` would quietly replace a developer's
    real output with a differently-shaped one.
    """
    if not shutil.which("uv"):
        pytest.skip("uv not found")

    project_root = Path(__file__).parent.parent

    # Run mkdocs build in quiet mode to validate config and files
    result = subprocess.run(
        ["uv", "run", "mkdocs", "build", "--quiet", "-d", str(tmp_path / "site")],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"mkdocs build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_per_locale_build_valid(tmp_path):
    """Test that the per-locale build path used in production works.

    test_mkdocs_build_valid covers the combined build. This covers the shape
    the site actually ships in: one self-contained locale, with its own search
    index and no other language's pages in it.
    """
    if not shutil.which("uv"):
        pytest.skip("uv not found")

    project_root = Path(__file__).parent.parent
    out = tmp_path / "ja"

    result = subprocess.run(
        ["uv", "run", "mkdocs", "build", "--quiet", "-d", str(out)],
        cwd=project_root,
        capture_output=True,
        text=True,
        env={**os.environ, "BUILD_ONLY_LOCALE": "ja"},
    )

    assert result.returncode == 0, (
        f"per-locale build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    index = out / "search" / "search_index.json"
    assert index.exists(), "per-locale build produced no search index of its own"

    entries = json.loads(index.read_text(encoding="utf-8"))
    langs = entries["config"]["lang"]
    assert "ja" in langs, f"search index is not built for 'ja': {langs}"
    for other in ("fi", "zh"):
        assert other not in langs, f"'{other}' leaked into the 'ja' search index: {langs}"

    # The locale is served from a subdirectory, so its canonical URLs need the
    # prefix even though it was built at the root of its own tree.
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'rel="canonical"' in home, "no canonical URL emitted"
    assert "/ja/" in home, "canonical URLs are missing the locale prefix"


def test_translations_valid():
    """Test that localized pages match their English source structurally and aren't stale."""
    if not shutil.which("uv"):
        pytest.skip("uv not found")

    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        ["uv", "run", "python", "scripts/validate_translations.py"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"translation validation failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_translated_locales_configured():
    """Test that every docs/<locale>/ tree is declared in mkdocs.yml."""
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs"
    mkdocs_content = (project_root / "mkdocs.yml").read_text()

    # Locale directories are two-letter lowercase names holding markdown files.
    locale_dirs = [
        d.name
        for d in docs_dir.iterdir()
        if d.is_dir() and len(d.name) == 2 and d.name.isalpha() and d.name.islower()
    ]

    for locale in locale_dirs:
        assert f"locale: {locale}" in mkdocs_content, (
            f"docs/{locale}/ exists but 'locale: {locale}' is not configured in mkdocs.yml"
        )


def test_mkdocs_yaml_valid():
    """Test that mkdocs.yml has valid structure."""
    mkdocs_file = Path(__file__).parent.parent / "mkdocs.yml"
    content = mkdocs_file.read_text()

    # Check for required top-level keys
    assert "site_name:" in content, "mkdocs.yml missing 'site_name:'"
    assert "nav:" in content, "mkdocs.yml missing 'nav:'"
    assert "theme:" in content, "mkdocs.yml missing 'theme:'"

    # Check for tabs (YAML doesn't allow tabs for indentation)
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        if line and not line.startswith("#"):
            if "\t" in line:
                raise AssertionError(f"mkdocs.yml line {i} contains tabs instead of spaces")


def test_new_translation_is_not_reported_as_stale(tmp_path):
    """A never-recorded hash must not tell the translator to re-translate."""
    import scripts.validate_translations as validate
    source = tmp_path / "page.md"
    source.write_text("# Title\n", encoding="utf-8")

    # The elided placeholder printed in TRANSLATING.md, and no key at all.
    for recorded in ["3f8a1c...", None, "", "not-a-hash"]:
        problem = validate.hash_problem(recorded, source, "fi")
        assert problem is not None
        assert "not recorded yet" in problem, problem
        assert "STALE" not in problem
        assert "re-translate" not in problem


def test_changed_source_is_reported_as_stale(tmp_path):
    """A real recorded hash that no longer matches is genuine staleness."""
    import scripts.validate_translations as validate
    source = tmp_path / "page.md"
    source.write_text("# Title\n", encoding="utf-8")

    problem = validate.hash_problem("0" * 64, source, "fi")
    assert problem is not None and problem.startswith("STALE")

    assert validate.hash_problem(validate.sha256_of(source), source, "fi") is None


def test_update_hashes_can_record_a_first_hash():
    """--update-hashes must work from every state the error points at."""
    import scripts.validate_translations as validate
    current = "a" * 64

    # Existing key is replaced.
    assert validate.stamp_front_matter(
        "source_sha: old\ntranslated: machine", current
    ) == f"source_sha: {current}\ntranslated: machine"

    # Missing key is added rather than silently skipped.
    assert validate.stamp_front_matter("translated: machine", current) == (
        f"source_sha: {current}\ntranslated: machine"
    )
    assert validate.stamp_front_matter("", current) == f"source_sha: {current}"
