"""Build an offline public-API manifest from an official Python Sphinx inventory."""

import argparse
import builtins
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path
from urllib.parse import urljoin

KINDS = {
    "py:module": "module",
    "py:class": "class",
    "py:exception": "class",
    "py:function": "function",
    "py:method": "method",
    "py:attribute": "attribute",
    "py:data": "attribute",
}


def build_manifest(data: bytes, documentation_version: str, source_url: str) -> dict:
    """Keep documented Python APIs, excluding pseudo-types and non-Python domains."""
    header = data.split(b"\n", 4)
    if len(header) != 5 or header[0] != b"# Sphinx inventory version 2":
        raise ValueError("Expected a Sphinx version 2 inventory")
    version = header[2].decode().removeprefix("# Version: ")
    minor = ".".join(documentation_version.split(".")[:2])
    if ".".join(version.split(".")[:2]) != minor:
        raise ValueError("Documentation version does not match the inventory header")
    apis = {}
    for line in zlib.decompress(header[4]).decode().splitlines():
        match = re.match(r"^(\S+) (py:\w+) -?\d+ (\S+) (.*)$", line)
        if match is None or match[2] not in KINDS:
            continue
        name, role, location = match[1], match[2], match[3]
        root = name.split(".")[0]
        if root in vars(builtins):
            normalized = "builtins." + name
        elif root in sys.stdlib_module_names or root == "builtins":
            normalized = name
        else:
            continue
        if name.rsplit(".", 1)[-1].startswith("__") and name != "__import__":
            continue
        if location.endswith("$"):
            location = location[:-1] + name
        apis[normalized] = {"kind": KINDS[role], "source": urljoin(source_url, location)}
    if not apis:
        raise ValueError("Inventory contains no recognized Python APIs")
    return {
        "schema_version": 1,
        "python_version": minor,
        "documentation_version": documentation_version,
        "source_url": source_url,
        "inventory_sha256": hashlib.sha256(data).hexdigest(),
        "apis": dict(sorted(apis.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--documentation-version", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(
        args.inventory.read_bytes(), args.documentation_version, args.source_url
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest['apis'])} documented API names to {args.output}")


if __name__ == "__main__":
    main()
