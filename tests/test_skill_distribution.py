"""Verify portable skill artifacts, document fidelity, integrity, and release inputs.

These tests cover packaging, not the truth of the source complexity claims or
agent behavior. Manual agent evaluation is described in skills/evaluations.md.
"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from scripts.build_skills import (
    GROUPS,
    NAME,
    ROOT,
    archive,
    local_links,
    marketplace_files,
    skill_files,
    validate_release,
    validate_skill,
    write_files,
)


@pytest.fixture
def payload() -> dict[str, bytes]:
    return skill_files(ROOT, "a" * 40)


def test_all_english_references_are_copied_exactly(payload: dict[str, bytes]) -> None:
    sources = {ROOT / "docs" / "index.md"}
    for group in GROUPS:
        sources.update((ROOT / "docs" / group).rglob("*.md"))
    bundled = {name for name in payload if name.startswith("references/docs/")}
    expected = {f"references/docs/{p.relative_to(ROOT / 'docs').as_posix()}" for p in sources}
    assert bundled == expected
    assert len(sources) > 100
    for path in sources:
        relative = path.relative_to(ROOT / "docs").as_posix()
        assert payload[f"references/docs/{relative}"] == path.read_bytes()
        if relative != "index.md":
            group = relative.split("/")[0]
            assert f"](../docs/{relative})" in payload[f"references/catalog/{group}.md"].decode()


def test_archive_is_reproducible_and_usable_outside_checkout(
    tmp_path: Path, payload: dict[str, bytes]
) -> None:
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    archive(first, NAME, payload)
    archive(second, NAME, dict(reversed(list(payload.items()))))
    assert first.read_bytes() == second.read_bytes()
    with ZipFile(first) as zipped:
        assert zipped.testzip() is None
        assert all(name.startswith(f"{NAME}/") for name in zipped.namelist())
        zipped.extractall(tmp_path / "unrelated-project")
    installed = tmp_path / "unrelated-project" / NAME
    validate_skill(installed)
    assert (installed / "LICENSE.txt").read_bytes() == (ROOT / "LICENSE.txt").read_bytes()
    manifest = json.loads((installed / "manifest.json").read_text())
    assert manifest["source_revision"] == "a" * 40
    assert manifest["supported_python"] == ["3.10", "3.11", "3.12", "3.13", "3.14"]


@pytest.mark.parametrize("mutation", ["delete", "corrupt", "extra"])
def test_invalid_payloads_fail(tmp_path: Path, payload: dict[str, bytes], mutation: str) -> None:
    write_files(tmp_path, payload)
    target = tmp_path / "references/docs/builtins/list.md"
    if mutation == "delete":
        target.unlink()
    elif mutation == "corrupt":
        target.write_text("incorrect content")
    else:
        (tmp_path / "unintended.txt").write_text("extra content")
    with pytest.raises(ValueError, match="inventory|hash mismatch"):
        validate_skill(tmp_path)


@pytest.mark.parametrize("target", ["missing.md", "../../outside.md"])
def test_broken_and_escaping_links_fail_even_with_valid_hashes(
    tmp_path: Path, payload: dict[str, bytes], target: str
) -> None:
    payload["SKILL.md"] += f"\n[Broken]({target})\n".encode()
    manifest = json.loads(payload["manifest.json"])
    manifest["files_sha256"]["SKILL.md"] = hashlib.sha256(payload["SKILL.md"]).hexdigest()
    payload["manifest.json"] = json.dumps(manifest).encode()
    write_files(tmp_path, payload)
    with pytest.raises(ValueError, match="Missing or escaping local link"):
        validate_skill(tmp_path)


def test_link_extraction_excludes_examples_and_includes_reference_links() -> None:
    text = (
        "[Real](real.md#section)\n```python\n'[Example](missing.md)'\n```\n"
        "~~~markdown\n[Example](also-missing.md)\n~~~\n[ref]: other.md\n"
    )
    assert local_links(text) == ["real.md#section", "other.md"]


def test_marketplaces_resolve_to_identical_portable_skill(
    tmp_path: Path, payload: dict[str, bytes]
) -> None:
    files = marketplace_files(payload)
    package = tmp_path / "marketplace.zip"
    archive(package, f"{NAME}-marketplace", files)
    with ZipFile(package) as zipped:
        zipped.extractall(tmp_path)
    root = tmp_path / f"{NAME}-marketplace"
    for marketplace_path, manifest_directory in [
        (".agents/plugins/marketplace.json", ".codex-plugin"),
        (".claude-plugin/marketplace.json", ".claude-plugin"),
    ]:
        marketplace = json.loads((root / marketplace_path).read_text())
        assert len(marketplace["plugins"]) == 1
        entry = marketplace["plugins"][0]
        source = entry["source"]
        plugin = root / (source if isinstance(source, str) else source["path"])
        metadata = json.loads((plugin / manifest_directory / "plugin.json").read_text())
        assert metadata["name"] == NAME
        assert metadata["version"] == json.loads(payload["manifest.json"])["version"]
        installed = plugin / metadata["skills"] / NAME
        validate_skill(installed)
        for name, content in payload.items():
            assert (installed / name).read_bytes() == content
    assert not any("maintain" in name or ".agents/skills/" in name for name in files)


@pytest.mark.parametrize(
    ("tag", "revision", "tagged_commit", "message"),
    [
        ("python-complexity-v9.0.0", "a" * 40, "a" * 40, "matching version"),
        ("python-complexity-v1.0.0", "a" * 40 + "-dirty", "a" * 40, "clean checkout"),
        ("python-complexity-v1.0.0", "a" * 40, "b" * 40, "point to HEAD"),
    ],
)
def test_release_rejects_wrong_version_dirty_tree_and_wrong_commit(
    tag: str, revision: str, tagged_commit: str, message: str
) -> None:
    with patch("scripts.build_skills.subprocess.check_output", return_value=tagged_commit):
        with pytest.raises(ValueError, match=message):
            validate_release(ROOT, tag, "1.0.0", revision)


def test_release_accepts_exact_clean_tag() -> None:
    with patch("scripts.build_skills.subprocess.check_output", return_value="a" * 40) as git:
        validate_release(ROOT, "python-complexity-v1.0.0", "1.0.0", "a" * 40)
    assert git.call_args.args[0][-1] == "refs/tags/python-complexity-v1.0.0^{commit}"
