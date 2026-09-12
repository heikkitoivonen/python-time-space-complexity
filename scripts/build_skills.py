"""Build offline skill and marketplace archives from the English documentation.

Documentation is copied byte for byte, retaining relative links and code fences.
Generated files live under build/ and dist/; the installable unit is a release
archive, not the source-only skills/python-complexity directory.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = "python-complexity"
REPOSITORY = "https://github.com/heikkitoivonen/python-time-space-complexity"
GROUPS = ("builtins", "stdlib", "implementations", "versions")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def revision(root: Path) -> str:
    """Identify the checkout without disguising local edits as a clean release."""
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, text=True
    ).strip()
    return sha + ("-dirty" if dirty else "")


def validate_release(root: Path, tag: str, version: str, source_revision: str) -> None:
    expected = f"{NAME}-v{version}"
    if tag != expected:
        raise ValueError(f"Release tag must match version.txt: expected {expected!r}, got {tag!r}")
    if source_revision.endswith("-dirty"):
        changed = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, text=True
        ).strip()
        raise ValueError(f"Release requires a clean checkout; changed paths:\n{changed}")
    tagged = subprocess.check_output(
        ["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"], cwd=root, text=True
    ).strip()
    if tagged != source_revision:
        raise ValueError("Release tag must point to HEAD")


def skill_files(root: Path, source_revision: str) -> dict[str, bytes]:
    source = root / "skills" / NAME
    version = (source / "version.txt").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise ValueError("Skill version must be a stable semantic version (X.Y.Z)")
    files = {
        "SKILL.md": (source / "SKILL.md").read_bytes(),
        "LICENSE.txt": (root / "LICENSE.txt").read_bytes(),
    }
    index = [
        "# Python Complexity Reference Index",
        "",
        "For a known module, open `docs/stdlib/<module>.md` relative to this index.",
        "For a builtin, open `docs/builtins/<name>.md`. Constructor pages may use",
        "a `_func` suffix; consult the builtin catalog to distinguish them.",
        "Read the operation's notes as well as its table row.",
        "",
        "Use a catalog only when you need to locate a page. Search the relevant",
        "catalog for the requested name rather than reading every page.",
        "Catalogs include canonical Website links for online citations.",
        "",
    ]
    paths = [root / "docs" / "index.md"]
    for group in GROUPS:
        index.append(f"- [{group.title()}](catalog/{group}.md)")
        catalog = [f"# {group.title()} Reference Catalog", ""]
        pages = sorted((root / "docs" / group).rglob("*.md"))
        if not pages:
            raise ValueError(f"No documentation found for {group}")
        paths.extend(pages)
        for page in pages:
            relative = page.relative_to(root / "docs").as_posix()
            title = next(
                line[2:]
                for line in page.read_text(encoding="utf-8").splitlines()
                if line.startswith("# ")
            )
            route = relative.removesuffix(".md").removesuffix("index").rstrip("/")
            catalog.append(
                f"- [{title}](../docs/{relative}) — [Website](https://pythoncomplexity.com/{route}/)"
            )
        files[f"references/catalog/{group}.md"] = ("\n".join(catalog) + "\n").encode()
    sources = {}
    for path in paths:
        content = path.read_bytes()
        files[f"references/docs/{path.relative_to(root / 'docs').as_posix()}"] = content
        sources[path.relative_to(root).as_posix()] = hashlib.sha256(content).hexdigest()
    files["references/INDEX.md"] = ("\n".join(index) + "\n").encode()
    versions = re.findall(
        r'"Programming Language :: Python :: (3\.\d+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
    )
    if not versions:
        raise ValueError("No supported Python versions in project classifiers")
    files["manifest.json"] = json_bytes(
        {
            "name": NAME,
            "version": version,
            "source_revision": source_revision,
            "repository": REPOSITORY,
            "supported_python": versions,
            "language": "en",
            "source_sha256": sources,
            "files_sha256": {
                name: hashlib.sha256(data).hexdigest() for name, data in files.items()
            },
        }
    )
    return files


def local_links(content: str) -> list[str]:
    """Extract inline and reference-definition destinations outside fenced code."""
    lines = []
    fence = ""
    for line in content.splitlines():
        stripped = line.lstrip()
        match = re.match(r"(`{3,}|~{3,})", stripped)
        if match:
            marker = match[0]
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append(line)
    text = "\n".join(lines)
    return re.findall(r"\]\(<?([^\s)>]+)", text) + re.findall(
        r"^\s*\[[^\]]+\]:\s*<?([^\s>]+)", text, re.MULTILINE
    )


def validate_skill(directory: Path) -> None:
    """Check the unpacked payload, including integrity and local file destinations."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest["files_sha256"]
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != set(expected) | {"manifest.json"}:
        raise ValueError("Skill file inventory differs from manifest")
    frontmatter = (directory / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    if metadata.get("name") != NAME or not metadata.get("description"):
        raise ValueError("Skill frontmatter needs the correct name and a description")
    for name, digest in expected.items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Content hash mismatch: {name}")
        if path.suffix != ".md":
            continue
        for target in local_links(path.read_text(encoding="utf-8")):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve()
            if not resolved.is_relative_to(directory.resolve()) or not resolved.is_file():
                raise ValueError(f"Missing or escaping local link in {name}: {target}")


def marketplace_files(files: dict[str, bytes]) -> dict[str, bytes]:
    """Wrap one portable skill for local or Git-hosted agent marketplaces."""
    version = json.loads(files["manifest.json"])["version"]
    prefix = f"plugins/{NAME}"
    result = {f"{prefix}/skills/{NAME}/{name}": data for name, data in files.items()}
    plugin = {
        "name": NAME,
        "version": version,
        "description": "Python builtin and standard-library time and space complexity reference",
        "author": {"name": "Python Complexity Project Contributors"},
        "homepage": "https://pythoncomplexity.com",
        "repository": REPOSITORY,
        "license": "MIT",
        "skills": "./skills/",
    }
    result[f"{prefix}/.claude-plugin/plugin.json"] = json_bytes(plugin)
    result[f"{prefix}/.codex-plugin/plugin.json"] = json_bytes(
        {
            **plugin,
            "interface": {
                "displayName": "Python Complexity",
                "shortDescription": "Look up Python time and space complexity",
                "longDescription": plugin["description"],
                "developerName": "Python Complexity Project Contributors",
                "category": "Productivity",
                "capabilities": [],
                "defaultPrompt": ["Analyze this Python code's time and space complexity."],
            },
        }
    )
    result[".claude-plugin/marketplace.json"] = json_bytes(
        {
            "name": NAME,
            "owner": plugin["author"],
            "plugins": [{"name": NAME, "source": f"./{prefix}", "version": version}],
        }
    )
    result[".agents/plugins/marketplace.json"] = json_bytes(
        {
            "name": NAME,
            "interface": {"displayName": "Python Complexity"},
            "plugins": [
                {
                    "name": NAME,
                    "source": {"source": "local", "path": f"./{prefix}"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                    "category": "Productivity",
                }
            ],
        }
    )
    return result


def write_files(directory: Path, files: dict[str, bytes]) -> None:
    for name, content in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def archive(path: Path, prefix: str, files: dict[str, bytes]) -> None:
    """Use fixed ZIP timestamps, permissions, and ordering for reproducible bytes."""
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for name, content in sorted(files.items()):
            info = ZipInfo(f"{prefix}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check", "package"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--release-tag", help="Require a clean checkout and matching stable tag")
    args = parser.parse_args()
    source_revision = revision(ROOT)
    files = skill_files(ROOT, source_revision)
    version = json.loads(files["manifest.json"])["version"]
    if args.release_tag:
        try:
            validate_release(ROOT, args.release_tag, version, source_revision)
        except ValueError as error:
            parser.error(str(error))
    with TemporaryDirectory(prefix="python-complexity-check-") as temporary:
        checked = Path(temporary) / NAME
        write_files(checked, files)
        validate_skill(checked)
    if args.command == "build":
        output = args.output or ROOT / "build" / "skills"
        write_files(output / NAME, files)
        validate_skill(output / NAME)
        print(f"Built {output / NAME}")
    elif args.command == "package":
        output = args.output or ROOT / "dist" / "skills"
        output.mkdir(parents=True, exist_ok=True)
        payloads = {f"{NAME}-{version}.zip": (NAME, files)}
        payloads[f"{NAME}-marketplace-{version}.zip"] = (
            f"{NAME}-marketplace",
            marketplace_files(files),
        )
        checksums = []
        for name, (prefix, payload) in payloads.items():
            path = output / name
            archive(path, prefix, payload)
            checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n")
        (output / "SHA256SUMS").write_text("".join(checksums), encoding="utf-8")
        print(f"Packaged {len(payloads)} archives in {output}")
    else:
        print(f"Skill checks passed ({len(files)} files)")


if __name__ == "__main__":
    main()
