"""Official inventory parsing, normalization, and provenance validation."""

import zlib

import pytest

from scripts.audit_documentation import load_public_manifest
from scripts.build_api_manifest import build_manifest


@pytest.mark.parametrize("minor", range(10, 15))
def test_supported_snapshots_preserve_version_boundaries(minor: int) -> None:
    version = f"3.{minor}"
    manifest = load_public_manifest(version)
    assert manifest["available"]
    assert manifest["python_version"] == version
    apis = manifest["apis"]
    assert "builtins.len" in apis
    assert "json.JSONDecoder.raw_decode" in apis
    assert ("tomllib" in apis) == (minor >= 11)
    assert ("asyncore" in apis) == (minor <= 11)
    assert ("sys.monitoring" in apis) == (minor >= 12)
    assert ("annotationlib" in apis) == (minor >= 14)
    assert all(
        entry["source"].startswith(f"https://docs.python.org/{version}/") for entry in apis.values()
    )


def inventory(body: str, version: str = "3.14") -> bytes:
    header = f"# Sphinx inventory version 2\n# Project: Python\n# Version: {version}\n# zlib\n"
    return header.encode() + zlib.compress(body.encode())


def test_inventory_normalizes_builtin_names_and_preserves_sources() -> None:
    data = inventory(
        "json py:module 0 library/json.html#module-$ -\n"
        "json.JSONDecoder.raw_decode py:method 1 library/json.html#$ -\n"
        "len py:function 1 library/functions.html#$ -\n"
        "list.append py:method 1 library/stdtypes.html#$ -\n"
        "list.__len__ py:method 1 library/stdtypes.html#$ -\n"
        "__import__ py:function 1 library/functions.html#$ -\n"
        "PyObject c:type 1 c-api/structures.html#$ -\n"
        "madeup.example py:function 1 tutorial/example.html#$ -\n"
    )
    manifest = build_manifest(data, "3.14.7", "https://docs.python.org/3.14/objects.inv")
    assert set(manifest["apis"]) == {
        "json",
        "json.JSONDecoder.raw_decode",
        "builtins.len",
        "builtins.list.append",
        "builtins.__import__",
    }
    assert (
        manifest["apis"]["builtins.len"]["source"]
        == "https://docs.python.org/3.14/library/functions.html#len"
    )
    assert manifest["documentation_version"] == "3.14.7"
    assert len(manifest["inventory_sha256"]) == 64


def test_inventory_rejects_mismatched_versions_and_empty_results() -> None:
    with pytest.raises(ValueError, match="version"):
        build_manifest(inventory(""), "3.13.1", "https://docs.python.org/3.14/objects.inv")
    with pytest.raises(ValueError, match="no recognized"):
        build_manifest(inventory(""), "3.14.7", "https://docs.python.org/3.14/objects.inv")
    with pytest.raises(ValueError, match="Sphinx"):
        build_manifest(b"garbage", "3.14.7", "https://docs.python.org/3.14/objects.inv")
