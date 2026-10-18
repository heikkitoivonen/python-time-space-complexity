"""Count builtin and standard-library usage in the most-downloaded PyPI packages.

The skill evaluation draws its common items from this ranking. One wheel (or
sdist) per package is downloaded and its .py files are parsed with ast; nothing
downloaded is imported or executed.

    uv run python -I scripts/scan_pypi_usage.py --cache /tmp/pypi --out skills/evals/usage.json
    uv run python -I scripts/scan_pypi_usage.py --cache /tmp/pypi --pin skills/evals/usage.json \\
        --out /tmp/usage.json

With --pin, the exact files recorded in an earlier output are scanned again and
their SHA-256 digests checked. Otherwise the top packages are read from
hugovk/top-pypi-packages and the newest release of each is used.

Counts are by name: a method call such as `x.append()` is counted as `method:append`
whatever `x` is, because the receiver's type is not known statically. Builtins
are counted unless the module binds the name anywhere, by assignment, argument,
definition or import. Stdlib calls are resolved through the module's imports,
read once per module: an import inside a function applies to the whole module,
and rebinding an imported module name later is not tracked. `op:in` counts
`in`/`not in` comparisons and `op:subscript-index` / `op:subscript-slice` count
subscripts.
"""

import argparse
import ast
import builtins
import hashlib
import io
import json
import sys
import tarfile
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

TOP = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
BUILTINS = {n for n in dir(builtins) if not n.startswith("_")}
STDLIB = set(sys.stdlib_module_names)
METHODS = {
    name
    for kind in (list, dict, str, set, bytes)
    for name in dir(kind)
    if not name.startswith("_") and name not in dir(object)
}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as response:
        return response.read()


def pick_file(release: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer a pure-Python wheel, then a Linux wheel, any wheel, and finally the sdist."""
    files = release["urls"]
    wheels = [f for f in files if f["packagetype"] == "bdist_wheel"]
    for marker in ("py3-none-any", "manylinux", "linux"):
        for wheel in wheels:
            if marker in wheel["filename"]:
                return wheel
    return next(iter(wheels), None) or next((f for f in files if f["packagetype"] == "sdist"), None)


def sources(blob: bytes, filename: str) -> Iterator[bytes]:
    if filename.endswith((".whl", ".zip")):
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for name in archive.namelist():
                if name.endswith(".py"):
                    yield archive.read(name)
    else:
        with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
            for member in archive.getmembers():
                if member.isfile() and member.name.endswith(".py"):
                    handle = archive.extractfile(member)
                    if handle is not None:
                        yield handle.read()


class Usage(ast.NodeVisitor):
    def __init__(self, tree: ast.Module, counts: Counter[str]) -> None:
        self.counts = counts
        self.modules: dict[str, str] = {}  # local alias -> stdlib module
        self.names: dict[str, str] = {}  # local name -> module.attr
        bound: set[str] = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                bound.add(n.id)
            elif isinstance(n, ast.arg):
                bound.add(n.arg)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                bound.update((a.asname or a.name).split(".")[0] for a in n.names)
        self.rebound = BUILTINS & bound

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in STDLIB:
                self.modules[alias.asname or top] = alias.name if alias.asname else top

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module and node.module.split(".")[0] in STDLIB:
            for alias in node.names:
                self.names[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def dotted(self, node: ast.expr) -> str | None:
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            if node.id in self.modules:
                return ".".join([self.modules[node.id], *reversed(parts)])
            if node.id in self.names:
                return ".".join([self.names[node.id], *reversed(parts)])
        return None

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in self.names:
                self.counts[f"stdlib:{self.names[func.id]}"] += 1
            elif func.id in BUILTINS and func.id not in self.rebound:
                self.counts[f"builtin:{func.id}"] += 1
        elif isinstance(func, ast.Attribute):
            path = self.dotted(func)
            if path:
                self.counts[f"stdlib:{path}"] += 1
            elif func.attr in METHODS:
                self.counts[f"method:{func.attr}"] += 1
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            if isinstance(op, (ast.In, ast.NotIn)):
                self.counts["op:in"] += 1
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        kind = "slice" if isinstance(node.slice, ast.Slice) else "index"
        self.counts[f"op:subscript-{kind}"] += 1
        self.generic_visit(node)


def scan(blob: bytes, filename: str) -> tuple[Counter[str], int]:
    counts: Counter[str] = Counter()
    parsed = 0
    for source in sources(blob, filename):
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        parsed += 1
        Usage(tree, counts).visit(tree)
    return counts, parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--count", type=int, default=100, help="Packages to scan")
    parser.add_argument("--min-packages", type=int, default=5, help="Omit rarer names")
    parser.add_argument("--cache", type=Path, required=True, help="Download directory")
    parser.add_argument("--pin", type=Path, help="Rescan the files in an earlier output")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    wanted: dict[str, tuple[str, str, str] | None]
    if args.pin:
        earlier = json.loads(args.pin.read_text(encoding="utf-8"))
        ranking = earlier["ranking"]
        wanted = {
            name: (p["version"], p["file"], p["sha256"]) for name, p in earlier["packages"].items()
        }
    else:
        top = json.loads(fetch(TOP))
        ranking = {"source": TOP, "last_update": top["last_update"]}
        wanted = {row["project"]: None for row in top["rows"][: args.count]}
    total: Counter[str] = Counter()
    present: Counter[str] = Counter()
    packages: dict[str, dict[str, Any]] = {}
    files = 0
    for name, pin in wanted.items():
        url = f"https://pypi.org/pypi/{name}/json" if pin is None else (
            f"https://pypi.org/pypi/{name}/{pin[0]}/json"
        )  # fmt: skip
        release = json.loads(fetch(url))
        chosen = (
            pick_file(release)
            if pin is None
            else next(f for f in release["urls"] if f["filename"] == pin[1])
        )
        if chosen is None:
            print(f"{name}: no files", file=sys.stderr)
            continue
        target = args.cache / chosen["filename"]
        if not target.exists():
            target.write_bytes(fetch(chosen["url"]))
        blob = target.read_bytes()
        expected = chosen["digests"]["sha256"] if pin is None else pin[2]
        if hashlib.sha256(blob).hexdigest() != expected:
            raise SystemExit(f"{chosen['filename']}: SHA-256 mismatch")
        counts, parsed = scan(blob, chosen["filename"])
        files += parsed
        total.update(counts)
        present.update(counts.keys())
        packages[name] = {
            "version": release["info"]["version"],
            "file": chosen["filename"],
            "sha256": expected,
        }
        print(f"{name} {packages[name]['version']}: {counts.total()} uses", file=sys.stderr)
    usage = [
        {"name": key, "packages": present[key], "uses": total[key]}
        for key in sorted(total, key=lambda k: (-present[k], -total[k], k))
        if present[key] >= args.min_packages
    ]
    output = {
        "ranking": ranking,
        "min_packages": args.min_packages,
        "python": sys.version.split()[0],
        "files_parsed": files,
        "packages": packages,
        "usage": usage,
    }
    args.out.write_text(json.dumps(output, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
