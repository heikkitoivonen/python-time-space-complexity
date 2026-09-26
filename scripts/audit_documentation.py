"""Audit script to identify documentation gaps for builtins and stdlib modules."""

import argparse
import ast
import builtins
import contextlib
import importlib
import importlib.util
import inspect
import io
import json
import pkgutil
import re
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import warnings
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

BUILTIN_CONSTANTS = {"False", "True", "None", "Ellipsis", "NotImplemented", "__debug__"}


def get_all_builtins() -> dict[str, list[str]]:
    """Get all built-in functions, types, and exceptions."""
    builtin_items: dict[str, list[str]] = {}

    for name in dir(builtins):
        obj = getattr(builtins, name)
        if name.startswith("_") or name in BUILTIN_CONSTANTS:
            continue

        # Categorize the builtin
        if inspect.isclass(obj):
            if issubclass(obj, BaseException):
                category = "exceptions"
            else:
                category = "types"
        elif inspect.isbuiltin(obj) or inspect.isfunction(obj):
            category = "functions"
        else:
            category = "other"

        if category not in builtin_items:
            builtin_items[category] = []
        builtin_items[category].append(name)

    # Sort each category
    for category in builtin_items:
        builtin_items[category].sort()

    return builtin_items


def get_all_stdlib_modules() -> list[str]:
    """Get list of all standard library modules.

    Uses ``sys.stdlib_module_names``, which is baked into the interpreter and
    lists exactly the standard library. Do NOT use ``pkgutil.iter_modules()``
    here: it walks ``sys.path``, so installed third-party packages and this
    repository's own ``scripts/`` modules would be counted as stdlib and the
    reported coverage would drift with whatever happens to be installed.
    """
    non_public = {
        "pydoc_data",
        "sre_compile",
        "sre_constants",
        "sre_parse",
    }

    return sorted(
        name
        for name in sys.stdlib_module_names
        if not name.startswith("_") and name not in non_public
    )


def get_documented_files(docs_dir: Path) -> dict[str, list[str]]:
    """Get list of documented files from docs directory."""
    documented: dict[str, list[str]] = {"builtins": [], "stdlib": []}

    # Check builtins
    builtins_dir = docs_dir / "builtins"
    if builtins_dir.exists():
        for md_file in builtins_dir.glob("*.md"):
            name = md_file.stem
            if name != "index":
                documented["builtins"].append(name)

    # Special handling for exceptions.md - covers all exception classes
    all_builtins = get_all_builtins()
    exception_classes = all_builtins.get("exceptions", [])
    if "exceptions" in documented["builtins"] and exception_classes:
        # Add all individual exception classes as documented
        documented["builtins"].extend(exception_classes)

    # Handle naming pattern mismatches
    # Some items have lowercase file names that should match titlecase builtins
    naming_mappings = {
        "bytearray": "bytearray_func",
        "complex": "complex_func",
        "memoryview": "memoryview_func",
        "object": "object_func",
        "type": "type_func",
        "locals": "locals_func",
        "copyright": "interpreter_info",
        "credits": "interpreter_info",
        "license": "interpreter_info",
        "exit": "exit_quit",
        "quit": "exit_quit",
        # Built-in constants with lowercase filenames
        "Ellipsis": "ellipsis",
        "False": "false",
        "None": "none",
        "NotImplemented": "notimplemented",
        "True": "true",
    }

    for builtin_name, doc_name in naming_mappings.items():
        if doc_name in documented["builtins"] and builtin_name not in documented["builtins"]:
            documented["builtins"].append(builtin_name)

    # Check stdlib
    stdlib_dir = docs_dir / "stdlib"
    if stdlib_dir.exists():
        for md_file in stdlib_dir.glob("*.md"):
            name = md_file.stem
            if name != "index":
                documented["stdlib"].append(name)

    return documented


def generate_audit_report(workspace_root: Path) -> dict[str, Any]:
    """Generate a comprehensive audit report."""
    docs_dir = workspace_root / "docs"

    # Get all available items
    builtins_by_category = get_all_builtins()
    stdlib_modules = get_all_stdlib_modules()
    documented = get_documented_files(docs_dir)

    # Flatten builtins for comparison
    all_builtins: list[str] = []
    for _category, items in builtins_by_category.items():
        all_builtins.extend(items)

    # Find gaps. Page filenames are lowercase, but module names are not always
    # (e.g. cProfile -> docs/stdlib/cprofile.md), so match case-insensitively.
    documented_builtins = {name.lower() for name in documented["builtins"]}
    documented_stdlib = {name.lower() for name in documented["stdlib"]}

    missing_builtins = [b for b in all_builtins if b.lower() not in documented_builtins]
    missing_stdlib = [s for s in stdlib_modules if s.lower() not in documented_stdlib]

    # Coverage counts items that exist upstream and have a page. The docs also
    # cover things that are not top-level module names (deque, namedtuple,
    # xml.dom, ...), so len(documented) would overcount and can exceed 100%.
    covered_builtins = len(all_builtins) - len(missing_builtins)
    covered_stdlib = len(stdlib_modules) - len(missing_stdlib)

    # Create report
    report: dict[str, Any] = {
        "builtins": {
            "total": len(all_builtins),
            "documented": covered_builtins,
            "coverage_percent": round(100 * covered_builtins / len(all_builtins), 1),
            "missing": sorted(missing_builtins),
            "by_category": builtins_by_category,
        },
        "stdlib": {
            "total": len(stdlib_modules),
            "documented": covered_stdlib,
            "coverage_percent": round(100 * covered_stdlib / len(stdlib_modules), 1),
            "missing": missing_stdlib,
        },
        "summary": {
            "total_items": len(all_builtins) + len(stdlib_modules),
            "total_documented": covered_builtins + covered_stdlib,
            "overall_coverage_percent": round(
                100
                * (covered_builtins + covered_stdlib)
                / (len(all_builtins) + len(stdlib_modules)),
                1,
            ),
        },
    }

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted report to console."""
    print("\n" + "=" * 70)
    print("DOCUMENTATION COVERAGE AUDIT — TOP-LEVEL PAGES")
    print("=" * 70)

    print("\n📦 BUILTINS")
    print(f"  Total: {report['builtins']['total']}")
    print(f"  Documented: {report['builtins']['documented']}")
    print(f"  Coverage: {report['builtins']['coverage_percent']}%")

    if report["builtins"]["missing"]:
        print(f"\n  ❌ Missing ({len(report['builtins']['missing'])}):")
        for item in report["builtins"]["missing"]:
            print(f"    - {item}")

    print("\n📚 STDLIB MODULES")
    print(f"  Total: {report['stdlib']['total']}")
    print(f"  Documented: {report['stdlib']['documented']}")
    print(f"  Coverage: {report['stdlib']['coverage_percent']}%")

    if report["stdlib"]["missing"]:
        print(f"\n  ❌ Missing ({len(report['stdlib']['missing'])}):")
        for item in report["stdlib"]["missing"]:
            print(f"    - {item}")

    print("\n📊 OVERALL")
    print(f"  Total Items: {report['summary']['total_items']}")
    print(f"  Documented: {report['summary']['total_documented']}")
    print(f"  Coverage: {report['summary']['overall_coverage_percent']}%")
    print("\n" + "=" * 70)


# These are programs, demonstrations, or test suites, not importable library APIs.
# Keep every exclusion visible in the report; never import executable entry points.
EXCLUDED_COMPONENTS = {"test", "tests", "__main__"}
# These builtin APIs remain public despite their underscore spelling.
SPECIAL_BUILTINS = {"__import__"}
EXCLUDED_PACKAGES = {"antigravity", "idlelib", "turtledemo"}
BUILTIN_PAGES = {
    "bytearray": "bytearray_func",
    "complex": "complex_func",
    "memoryview": "memoryview_func",
    "object": "object_func",
    "type": "type_func",
    "locals": "locals_func",
    "copyright": "interpreter_info",
    "credits": "interpreter_info",
    "license": "interpreter_info",
    "exit": "exit_quit",
    "quit": "exit_quit",
}
CLASS_PAGES = {
    "collections.deque": "deque",
    "collections.defaultdict": "defaultdict",
    "collections.Counter": "counter",
    "collections.OrderedDict": "ordereddict",
    "collections.namedtuple": "namedtuple",
    # A submodule whose page name is not its dotted module name.
    "concurrent.futures": "concurrent_futures",
    "xml.parsers.expat": "pyexpat",
    # Documented on the ElementTree page, not as a module of its own.
    "xml.etree.ElementInclude": "xml.etree.elementtree",
}


def is_codec_module(name: str) -> bool:
    """Individual codec implementations are outside the audit; retain alias metadata."""
    return name.startswith("encodings.") and name != "encodings.aliases"


def excluded_binding(obj: Any, kind: str) -> bool:
    """Omit constants and bindings to individual codec modules."""
    return (kind == "constant") or (isinstance(obj, ModuleType) and is_codec_module(obj.__name__))


def discover_modules() -> tuple[list[str], list[str]]:
    """Discover installed stdlib submodules without importing their parents.

    Only search package directories beneath the interpreter's stdlib directory,
    never sys.path (which includes project code and third-party packages).
    Platform-unavailable top-level modules remain in the inventory.
    """
    found = set(get_all_stdlib_modules())
    excluded: set[str] = set()
    stdlib = Path(sysconfig.get_path("stdlib"))

    def walk(directory: Path, prefix: str) -> None:
        for info in pkgutil.iter_modules([str(directory)]):
            name = prefix + info.name
            if (
                info.name in EXCLUDED_COMPONENTS
                or name.split(".")[0] in EXCLUDED_PACKAGES
                or is_codec_module(name)
            ):
                excluded.add(name)
            elif not info.name.startswith("_"):
                found.add(name)
                if info.ispkg:
                    walk(directory / info.name, name + ".")

    for name in sorted(found):
        if name in EXCLUDED_PACKAGES:
            excluded.add(name)
        elif (stdlib / name / "__init__.py").is_file():
            walk(stdlib / name, name + ".")
    return sorted(found - excluded), sorted(excluded)


@cache
def load_public_manifest(
    python_version: str | None = None, directory: Path | None = None
) -> dict[str, Any]:
    """Load only a matching minor-version snapshot; absent versions remain unclassified."""
    minor = python_version or f"{sys.version_info.major}.{sys.version_info.minor}"
    directory = directory or Path(__file__).parent / "api_manifests"
    path = directory / f"python-{minor}.json"
    if not path.is_file():
        return {
            "python_version": minor,
            "available": False,
            "apis": {},
            "notice": f"No public-API manifest for Python {minor}; classification is pending.",
        }
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("python_version") != minor:
        raise ValueError(f"Unsupported or mismatched public-API manifest: {path}")
    manifest["available"] = True
    return manifest


def resolve_loaded_object(path: str) -> Any:
    """Resolve a qualified name using loaded modules without executing descriptors."""
    parts = path.split(".")
    for length in range(len(parts), 0, -1):
        obj: Any = sys.modules.get(".".join(parts[:length]))
        if obj is not None:
            for member in parts[length:]:
                obj = inspect.getattr_static(obj, member, None)
            return obj
    return None


def attribute_hints(apis: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    """Index only explicitly documented instance attributes by class name."""
    hints: dict[str, dict[str, set[str]]] = {}
    for name, entry in apis.items():
        if entry["kind"] != "attribute" or "." not in name:
            continue
        owner, member = name.rsplit(".", 1)
        hints.setdefault(owner.rsplit(".", 1)[-1], {}).setdefault(owner, set()).add(member)
    return hints


def documented_fields(cls: type, hints: dict[str, dict[str, set[str]]]) -> set[str]:
    """Supply documented fields that appear only on instances, without constructing one."""
    # Struct-sequence fields have class descriptors when available. Inventory-only
    # fields on these types belong in unresolved diagnostics on this platform.
    if issubclass(cls, tuple) and hasattr(cls, "n_fields"):
        return set()
    names: set[str] = set()
    for base in cls.__mro__:
        for owner, members in hints.get(base.__name__, {}).items():
            if resolve_loaded_object(owner) is base:
                names.update(members)
    return names


def api_kind(name: str, obj: Any, member: bool) -> str:
    """Classify a binding without invoking it."""
    if inspect.isclass(obj):
        return "class"
    if isinstance(obj, ModuleType):
        return "module"
    if isinstance(obj, Enum) or name.removeprefix("builtins.") in BUILTIN_CONSTANTS:
        return "constant"
    if isinstance(obj, property) or inspect.isdatadescriptor(obj):
        return "attribute"
    if callable(obj) or isinstance(obj, (classmethod, staticmethod)):
        return "method" if member else "function"
    scalar = not member and type(obj) in (
        str,
        bytes,
        int,
        float,
        complex,
        bool,
        tuple,
        frozenset,
        type(None),
    )
    return "constant" if scalar or name.rsplit(".", 1)[-1].isupper() else "attribute"


def unwrap_member(obj: Any) -> Any:
    """Compare descriptors and their bound spellings without calling them."""
    if isinstance(obj, (classmethod, staticmethod)) or inspect.ismethod(obj):
        return obj.__func__
    if inspect.isbuiltin(obj) and isinstance(getattr(obj, "__self__", None), type):
        return inspect.getattr_static(obj.__self__, obj.__name__, obj)
    return obj


def definition_path(obj: Any) -> tuple[str, str] | None:
    """Return a stable importable identity only when the path resolves to this object.

    Process-local ids cannot be compared across import workers. Qualified names
    alone are also insufficient: distinct closures can share a qualified name.
    """
    obj = unwrap_member(obj)
    owner = getattr(obj, "__objclass__", None)
    module = getattr(obj, "__module__", None) or getattr(owner, "__module__", None)
    qualname = getattr(obj, "__qualname__", None)
    if not isinstance(module, str) or not isinstance(qualname, str):
        return None
    target: Any = sys.modules.get(module)
    for part in qualname.split("."):
        target = inspect.getattr_static(target, part, None)
    if unwrap_member(target) is obj:
        return module, qualname
    # Some extension types advertise an unbound name, e.g. _json.Scanner,
    # while the module exports the same type as _json.make_scanner.
    source = sys.modules.get(module)
    if source is not None:
        for name, value in sorted(vars(source).items()):
            if not name.startswith("_") and unwrap_member(value) is obj:
                return module, name
    return documented_type_path(obj) if inspect.isclass(obj) else None


@cache
def documented_type_path(cls: type) -> tuple[str, str] | None:
    """Resolve C types whose advertised name is not exported, such as method types."""
    apis = load_public_manifest()["apis"]
    module_names = {name for name, entry in apis.items() if entry["kind"] == "module"} | {
        "builtins"
    }
    for name, entry in apis.items():
        # Older Sphinx inventories index exported C types as data attributes.
        if entry["kind"] not in {"class", "attribute"} or resolve_loaded_object(name) is not cls:
            continue
        parts = name.split(".")
        for length in range(len(parts) - 1, 0, -1):
            module = ".".join(parts[:length])
            if module in module_names:
                return module, ".".join(parts[length:])
    return None


def field_owner(cls: type, member: str) -> type:
    """Find the class declaring an inherited descriptor, constant, or static field."""
    return next(
        (base for base in cls.__mro__ if member in vars(base)),
        cls,
    )


def api_record(name: str, obj: Any, kind: str, owner: type | None = None) -> dict[str, str]:
    """Attach stable identities while keeping unrelated equal-valued attributes distinct."""
    definition = definition_path(obj) if callable(obj) else None
    if isinstance(obj, ModuleType):
        definition = (obj.__name__, "")
    if definition is None and owner is not None:
        member = name.rsplit(".", 1)[-1]
        defining = field_owner(owner, member)
        owner_path = definition_path(defining)
        if owner_path is not None:
            definition = (owner_path[0], f"{owner_path[1]}.{member}")
    canonical = ".".join(part for part in definition if part) if definition else name
    return {
        "name": name,
        "kind": kind,
        "identity": canonical,
        "canonical": canonical,
        "definition": definition[1] if definition else "",
    }


@cache
def imported_data_sources(module: ModuleType) -> dict[str, tuple[ModuleType, str]]:
    """Track direct from-imports, including star exports, without merging equal values.

    Source evidence distinguishes a re-export from unrelated attributes that happen
    to contain the same small integer or interned string. Conditional and dynamic
    imports without such evidence remain separate.
    """
    try:
        tree = ast.parse(inspect.getsource(module))
    except (OSError, TypeError, SyntaxError):
        return {}
    sources: dict[str, tuple[ModuleType, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            sources.update(from_import_sources(module, node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for target in ast.walk(node):
                if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
                    sources.pop(target.id, None)
    return sources


def from_import_sources(
    module: ModuleType, node: ast.ImportFrom
) -> dict[str, tuple[ModuleType, str]]:
    """Resolve import provenance using already loaded module dictionaries."""
    path = "." * node.level + (node.module or "")
    if node.level:
        path = importlib.util.resolve_name(path, module.__package__ or module.__name__)
    source = sys.modules.get(path)
    if source is None:
        return {}
    names: list[tuple[str, str]] = []
    for alias in node.names:
        if alias.name == "*":
            exported = vars(source).get(
                "__all__", [key for key in vars(source) if not key.startswith("_")]
            )
            names.extend((key, key) for key in exported)
        else:
            names.append((alias.asname or alias.name, alias.name))
    return {
        local: (source, original)
        for local, original in names
        if local in vars(module)
        and original in vars(source)
        and vars(module)[local] is vars(source)[original]
    }


def binding_record(
    module: ModuleType, name: str, obj: Any, kind: str, owner: type | None
) -> dict[str, str]:
    """Extend object identities with proven provenance for module data exports."""
    record = api_record(name, obj, kind, owner)
    if owner is not None or kind != "attribute" or record["identity"] != name:
        return record
    member = name.rsplit(".", 1)[-1]
    source = module
    seen: set[tuple[ModuleType, str]] = set()
    while (source, member) not in seen:
        seen.add((source, member))
        origin = imported_data_sources(source).get(member)
        if origin is None:
            break
        source, member = origin
    canonical = f"{source.__name__}.{member}"
    record.update(identity=canonical, canonical=canonical, definition=member)
    return record


def singleton_members(name: str, obj: Any, enabled: bool = True) -> list[dict[str, str]]:
    """Inspect structured exported objects such as sys.flags and os.environ.

    Scalar values, ordinary containers, callables, and modules are leaves.
    Structured object members are inspected once without following object graphs.
    """
    if not enabled or isinstance(obj, ModuleType) or callable(obj):
        return []
    structured = hasattr(type(obj), "n_fields") or hasattr(type(obj), "_fields")
    if not structured and isinstance(
        obj, (str, bytes, int, float, complex, tuple, list, dict, set, frozenset, range)
    ):
        return []
    result = []
    for member in dir(obj):
        if member.startswith("_"):
            continue
        value = inspect.getattr_static(obj, member, None)
        kind = api_kind(member, value, True)
        if kind == "constant":
            continue
        # Instance data belongs to the exported object; methods belong to its class.
        owner = type(obj) if kind == "method" else None
        result.append(api_record(f"{name}.{member}", value, kind, owner))
    return result


def public_binding(module: ModuleType, name: str) -> Any:
    """Resolve a binding, including a package's lazily exported submodules."""
    try:
        return getattr(module, name)
    except AttributeError:
        if not hasattr(module, "__path__"):
            raise
        return importlib.import_module(f"{module.__name__}.{name}")


def class_members(cls: type) -> set[str]:
    """Include inherited attributes and enum aliases, even when dir() hides them."""
    members = set(dir(cls))
    for base in cls.__mro__:
        members.update(vars(base))
    enum_members = getattr(cls, "__members__", {})
    if isinstance(enum_members, Mapping):
        members.update(enum_members)
    return members


def inspect_public_api(
    module: ModuleType, public_apis: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Enumerate public bindings, inherited class members, enums, and fields.

    Public means a non-underscore binding from dir() or __all__. Re-exported
    names are included, even when they may be implementation imports. Class dunder
    members and constants are excluded; __import__ remains included as a builtin API.
    No API functions or constructors are called; descriptors are inspected statically.
    """
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    excluded_names: list[str] = []
    apis = load_public_manifest()["apis"] if public_apis is None else public_apis
    hints = attribute_hints(apis)
    exports = set(getattr(module, "__all__", ()))

    def visit(name: str, obj: Any, ancestors: tuple[type, ...] = ()) -> None:
        kind = api_kind(name, obj, bool(ancestors))
        if "__main__" in name.split(".") or excluded_binding(obj, kind):
            excluded_names.append(name)
            return
        record: dict[str, Any] = binding_record(
            module, name, obj, kind, ancestors[-1] if ancestors else None
        )
        record["exported"] = not ancestors and name.removeprefix(module.__name__ + ".") in exports
        items.append(record)
        if not inspect.isclass(obj):
            items.extend(singleton_members(name, obj, enabled=not ancestors))
            return
        if obj in ancestors:
            return
        members = class_members(obj) | documented_fields(obj, hints)
        for member in sorted(members):
            if member.startswith("_"):
                continue
            value = inspect.getattr_static(obj, member, None)
            visit(f"{name}.{member}", value, (*ancestors, obj))

    names = set(dir(module)) | exports
    for name in sorted(names):
        if (
            name.startswith("_")
            and name not in exports
            and not (module is builtins and name in SPECIAL_BUILTINS)
        ):
            continue
        try:
            value = public_binding(module, name)
            visit(f"{module.__name__}.{name}", value)
        except Exception as exc:
            errors.append(f"{module.__name__}.{name}: {type(exc).__name__}: {exc}")
    return {"items": items, "errors": errors, "available": True, "excluded_names": excluded_names}


def load_inspection_module(name: str) -> ModuleType:
    """Include documented module objects exposed as attributes, e.g. sys.monitoring."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        module = resolve_loaded_object(name)
        if isinstance(module, ModuleType):
            return module
        raise


def inspect_module_worker(name: str) -> dict[str, Any]:
    """Import and inspect one module; the caller supplies process isolation."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                module = load_inspection_module(name)
                result = inspect_public_api(module)
                result["module_identity"] = module.__name__
                if name != module.__name__:
                    for item in result["items"]:
                        item["name"] = name + item["name"][len(module.__name__) :]
                    result["excluded_names"] = [
                        name + item[len(module.__name__) :] for item in result["excluded_names"]
                    ]
                return result
    except BaseException as exc:
        return {"items": [], "errors": [f"{name}: {type(exc).__name__}: {exc}"], "available": False}


def inspect_module(name: str) -> tuple[str, dict[str, Any]]:
    """Bound imports with a timeout, closed stdin, and a disposable working directory."""
    with tempfile.TemporaryDirectory(prefix="api-audit-") as directory:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    str(Path(__file__).resolve()),
                    "--inspect",
                    name,
                ],
                cwd=directory,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            return name, json.loads(result.stdout)
        except (subprocess.SubprocessError, ValueError) as exc:
            return name, {
                "items": [],
                "errors": [f"{name}: {type(exc).__name__}: {exc}"],
                "available": False,
            }


def documentation_page(root: Path, module: str, name: str) -> Path:
    """Use dedicated pages first, then the nearest existing package page."""
    if module == "builtins" and name == "builtins":
        return root / "docs" / "stdlib" / "builtins.md"
    if module == "builtins":
        builtin = name.split(".")[1]
        value = getattr(builtins, builtin, None)
        stem = BUILTIN_PAGES.get(builtin, builtin.lower())
        if inspect.isclass(value) and issubclass(value, BaseException):
            stem = "exceptions"
        return root / "docs" / "builtins" / f"{stem}.md"
    for qualified, stem in CLASS_PAGES.items():
        if name == qualified or name.startswith(qualified + "."):
            page = root / "docs" / "stdlib" / f"{stem}.md"
            if page.exists():
                return page
    parts = module.lower().split(".")
    for length in range(len(parts), 0, -1):
        page = root / "docs" / "stdlib" / f"{'.'.join(parts[:length])}.md"
        if page.is_file():
            return page
    return root / "docs" / "stdlib" / f"{module.lower()}.md"


def mentions(text: str, name: str) -> bool:
    """Match identifiers exactly, including slash-separated operation families."""
    return re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", text) is not None


def is_scandir_call(node: ast.AST) -> bool:
    """Recognize the qualified factory without executing documentation code."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "scandir"
    )


def assigned_names(statement: ast.AST) -> set[str]:
    """Conservatively invalidate bindings on assignment or deletion."""
    return {
        node.id
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }


def loop_mentions_member(loop: ast.For, member: str) -> bool:
    """Find a direct member use before the loop variable is rebound."""
    if not isinstance(loop.target, ast.Name):
        return False
    for statement in loop.body:
        if loop.target.id in assigned_names(statement):
            break
        if not isinstance(statement, (ast.Expr, ast.Assign, ast.AnnAssign)):
            continue
        if any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == loop.target.id
            and node.attr == member
            for node in ast.walk(statement)
        ):
            return True
    return False


def scandir_body_mentions(statements: list[ast.stmt], iterators: set[str], member: str) -> bool:
    """Track context-managed scandir iterators within their lexical body."""
    for statement in statements:
        if isinstance(statement, ast.With):
            local = iterators | {
                item.optional_vars.id
                for item in statement.items
                if is_scandir_call(item.context_expr) and isinstance(item.optional_vars, ast.Name)
            }
            if scandir_body_mentions(statement.body, local, member):
                return True
        if isinstance(statement, ast.For):
            known = is_scandir_call(statement.iter) or (
                isinstance(statement.iter, ast.Name) and statement.iter.id in iterators
            )
            if known and loop_mentions_member(statement, member):
                return True
        iterators.difference_update(assigned_names(statement))
    return False


def documents_direntry_member(text: str, member: str) -> bool:
    """Recognize member uses inside loops over explicitly qualified os.scandir calls."""
    for block in re.findall(r"```python[^\n]*\n(.*?)```", text, re.DOTALL):
        try:
            tree = ast.parse(textwrap.dedent(block))
        except SyntaxError:
            continue
        if scandir_body_mentions(tree.body, set(), member):
            return True
    return False


def documents_name(text: str, module: str, name: str, dedicated: bool = False) -> bool:
    """Check explicit name evidence, scoped to a class for class members.

    A mention is evidence of coverage, not proof of a complexity bound. Qualified
    references, instance aliases, and headings supply class context. Ambiguous
    unqualified mentions do not cover the same method on every class.
    """
    relative = name.removeprefix(module + ".")
    parts = relative.split(".")
    if len(parts) == 1:
        return mentions(text, parts[0])
    owner, member = parts[-2:]
    if mentions(text, ".".join(parts[-2:])) or (
        name.startswith("os.DirEntry.") and documents_direntry_member(text, member)
    ):
        return True
    aliases = re.findall(r"\b(\w+)\s*=\s*(?:[\w.]+\.)?" + re.escape(owner) + r"\s*\(", text)
    if any(mentions(text, f"{alias}.{member}") for alias in aliases):
        return True
    if dedicated:
        return mentions(text, member)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        if not heading or not mentions(heading[2], owner):
            continue
        end = index + 1
        while end < len(lines):
            following = re.match(r"^(#{1,6})\s", lines[end])
            if following and len(following[1]) <= len(heading[1]):
                break
            end += 1
        if mentions("\n".join(lines[index:end]), member):
            return True
    return False


def preferred_occurrence(item: dict[str, Any]) -> tuple[bool, bool, int, str]:
    """Prefer the defining API, then a public spelling naming its defining class."""
    name = item["name"]
    definition = item.get("definition", "")
    return (
        name != item.get("canonical", name),
        not (definition and name.endswith("." + definition)),
        name.count("."),
        name,
    )


def occurrence_covered(root: Path, item: dict[str, Any], texts: dict[Path, str]) -> bool:
    """Accept name evidence at any public alias's documentation location."""
    module, name = item["module"], item["name"]
    path = documentation_page(root, module, name)
    if not path.is_file():
        return False
    if path not in texts:
        texts[path] = path.read_text(encoding="utf-8")
    dedicated = (module == "builtins" and path.stem != "exceptions") or any(
        name.startswith(qualified + ".") and path.stem == stem
        for qualified, stem in CLASS_PAGES.items()
    )
    return (name == module and path.stem == module.lower()) or documents_name(
        texts[path], module, name, dedicated
    )


def unresolved_documented(
    apis: dict[str, Any], seen: set[str], modules: set[str]
) -> list[dict[str, str]]:
    """Keep unobserved documented APIs visible without treating them as missing docs."""
    result = []
    for name, entry in sorted(apis.items()):
        if (
            name in seen
            or "__main__" in name.split(".")
            or (entry["kind"] == "attribute" and name.rsplit(".", 1)[-1].isupper())
            or is_codec_module(name)
        ):
            continue
        if (
            name.removeprefix("builtins.") in BUILTIN_CONSTANTS
            or name.split(".")[0] in EXCLUDED_PACKAGES
        ):
            continue
        if not any(name == module or name.startswith(module + ".") for module in modules):
            continue
        result.append(
            {
                "name": name,
                "source": entry["source"],
                "reason": "Not observed on this interpreter/platform, or requires instance/runtime resolution",
            }
        )
    return result


def audited_modules(
    modules: list[str] | None, public_apis: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Inspect documented modules plus discoveries, preserving explicit exclusions."""
    discovered, excluded = discover_modules() if modules is None else (modules, [])
    if modules is None:
        discovered = sorted(
            set(discovered)
            | {
                name
                for name, entry in public_apis.items()
                if entry["kind"] == "module" and name.split(".")[0] not in EXCLUDED_PACKAGES
            }
        )
    excluded = sorted(set(excluded) | {name for name in discovered if is_codec_module(name)})
    excluded = [name for name in excluded if "__main__" not in name.split(".")]
    discovered = [
        name
        for name in discovered
        if not is_codec_module(name) and "__main__" not in name.split(".")
    ]
    return discovered, excluded


def generate_api_report(
    workspace_root: Path, modules: list[str] | None = None, manifest: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the full name inventory and rank pages by absent public names."""
    manifest = load_public_manifest() if manifest is None else manifest
    public_apis = manifest["apis"]
    discovered, excluded = audited_modules(modules, public_apis)
    results: dict[str, dict[str, Any]] = {}
    pages: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for module, result in pool.map(inspect_module, sorted(set(discovered) | {"builtins"})):
            results[module] = result

    texts: dict[Path, str] = {}

    groups: dict[str, list[dict[str, Any]]] = {}
    for module, result in sorted(results.items()):
        errors.extend(result["errors"])
        items = list(result["items"])
        if (module != "builtins" or module in public_apis) and result.get(
            "available", not result["errors"]
        ):
            items.insert(
                0,
                {
                    "name": module,
                    "kind": "module",
                    "identity": result.get("module_identity", module),
                },
            )
        for item in items:
            identity = item.get("identity", item["name"])
            groups.setdefault(identity, []).append({**item, "module": module})
    review: list[dict[str, Any]] = []
    seen_names = {name for result in results.values() for name in result.get("excluded_names", [])}
    for identity, occurrences in sorted(groups.items()):
        unique = {item["name"]: item for item in occurrences}
        seen_names.update(unique)
        occurrences = sorted(unique.values(), key=preferred_occurrence)
        documented = [item for item in occurrences if item["name"] in public_apis]
        if not documented:
            primary = occurrences[0]
            review.append(
                {
                    "name": primary["name"],
                    "kind": primary["kind"],
                    "identity": identity,
                    "aliases": sorted(unique.keys() - {primary["name"]}),
                    "file": documentation_page(workspace_root, primary["module"], primary["name"])
                    .relative_to(workspace_root)
                    .as_posix(),
                    "reason": "Listed in __all__, but not in the documented API inventory"
                    if any(item.get("exported") for item in occurrences)
                    else "Runtime discovery not in the documented API inventory",
                }
            )
            continue
        primary = documented[0]
        key = (
            documentation_page(workspace_root, primary["module"], primary["name"])
            .relative_to(workspace_root)
            .as_posix()
        )
        covered = any(occurrence_covered(workspace_root, item, texts) for item in occurrences)
        if key not in pages:
            pages[key] = {
                "file": key,
                "exists": (workspace_root / key).is_file(),
                "items": [],
                "missing": [],
            }
        record = {
            "name": primary["name"],
            "kind": primary["kind"],
            "identity": identity,
            "aliases": sorted(unique.keys() - {primary["name"]}),
            "covered": covered,
            "source": public_apis[primary["name"]]["source"],
        }
        pages[key]["items"].append(record)
        if not covered:
            pages[key]["missing"].append(record)
    for page in pages.values():
        page["items"].sort(key=lambda item: item["name"])
        page["missing"].sort(key=lambda item: item["name"])
        page["defects"] = len(page["missing"])
    ranked = sorted(pages.values(), key=lambda page: (-page["defects"], page["file"]))
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "scope": "Actionable gaps are missing names from the versioned official Python API inventory, "
        "deduplicated across verified aliases and inheritance. Unclassified runtime discoveries "
        "are reported separately and do not affect rankings; __all__ supplies review evidence only. "
        "Only explicitly documented instance fields are inventoried. Coverage means a name mention, "
        "not a validated complexity claim. Constants, class dunder members, individual encodings "
        "codec modules, and listed programs are excluded. Unavailable and unresolved documented "
        "APIs are reported separately; no constructors are executed.",
        "manifest": {key: value for key, value in manifest.items() if key != "apis"},
        "needs_classification": sorted(review, key=lambda item: item["name"]),
        "unresolved_documented": unresolved_documented(public_apis, seen_names, set(results)),
        "modules_inspected": len(results),
        "excluded": excluded,
        "inspection_errors": errors,
        "total_names": sum(len(page["items"]) for page in ranked),
        "alias_paths": sum(len(item["aliases"]) for page in ranked for item in page["items"]),
        "unclassified_names": len(review),
        "missing_names": sum(page["defects"] for page in ranked),
        "pages": ranked,
    }


def print_api_report(report: dict[str, Any], include_review: bool = False) -> None:
    """Print every missing name, ranked by defects per file, without truncation."""
    print(f"\nPUBLIC API AUDIT — Python {report['python']} ({report['platform']})")
    print(report["scope"])
    print(
        f"Inspected modules: {report['modules_inspected']}; unique APIs: {report['total_names']}; "
        f"missing APIs: {report['missing_names']}; aliases combined: {report['alias_paths']}"
    )
    print(f"Needs classification (not ranked): {report['unclassified_names']}")
    print(f"Documented but unresolved (not ranked): {len(report['unresolved_documented'])}")
    if report["manifest"].get("notice"):
        print(report["manifest"]["notice"])
    print("\nFILES ORDERED BY MOST ACTIONABLE GAPS")
    for page in report["pages"]:
        if not page["defects"]:
            continue
        status = "missing parts" if page["exists"] else "MISSING FILE"
        print(f"\n{page['defects']:5d}  {page['file']} ({status})")
        for item in page["missing"]:
            print(f"  - {item['name']} [{item['kind']}]")
    if include_review:
        print_classification_report(report)
    else:
        print("\nClassification details are available in --json or with --include-review.")
    print("\nINSPECTION ERRORS (coverage unknown)")
    for error in report["inspection_errors"]:
        print(f"  - {error}")
    print("\nEXCLUDED MODULES / PACKAGES")
    for name in report["excluded"]:
        print(f"  - {name}")


def print_classification_report(report: dict[str, Any]) -> None:
    """Keep uncertain runtime discoveries and unresolved documentation out of the ranking."""
    print(f"\nAPI CLASSIFICATION REVIEW — Python {report['python']} ({report['platform']})")
    print("\nNEEDS CLASSIFICATION (not actionable gaps)")
    for item in report["needs_classification"]:
        print(f"  - {item['name']} [{item['kind']}] — {item['reason']}")
    print("\nDOCUMENTED BUT UNRESOLVED (not actionable gaps)")
    for item in report["unresolved_documented"]:
        print(f"  - {item['name']} — {item['reason']}")


def page_api_report(root: Path, report: dict[str, Any], page: str) -> dict[str, Any]:
    """Scope a complete audit to a page, retaining uncertainty and alias deduplication."""
    selected = dict(report)
    modules = {
        name for name, entry in load_public_manifest()["apis"].items() if entry["kind"] == "module"
    }

    def target_page(name: str) -> str:
        prefixes = [prefix for prefix in modules if name == prefix or name.startswith(prefix + ".")]
        module = max(prefixes, key=len) if prefixes else name.split(".")[0]
        return documentation_page(root, module, name).relative_to(root).as_posix()

    selected["inspection_errors"] = [
        error
        for error in report["inspection_errors"]
        if target_page(error.split(":", 1)[0]) == page
    ]
    selected["pages"] = [item for item in report["pages"] if item["file"] == page]
    for key in ("needs_classification", "unresolved_documented"):
        selected[key] = []
        for item in report[key]:
            if item.get("file", target_page(item["name"])) == page:
                selected[key].append(item)
    selected["total_names"] = sum(len(item["items"]) for item in selected["pages"])
    selected["missing_names"] = sum(item["defects"] for item in selected["pages"])
    selected["alias_paths"] = sum(
        len(item["aliases"]) for p in selected["pages"] for item in p["items"]
    )
    selected["unclassified_names"] = len(selected["needs_classification"])
    return selected


def api_gate_passes(report: dict[str, Any]) -> bool:
    """Zero misses is meaningful only with an inventory and successful inspection."""
    return bool(
        report["manifest"].get("available")
        and report["total_names"]
        and not report["missing_names"]
        and not report["inspection_errors"]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", help=argparse.SUPPRESS)
    parser.add_argument("--pages-only", action="store_true", help="Only check top-level page files")
    parser.add_argument(
        "--include-review", action="store_true", help="Also list unclassified and unresolved APIs"
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the complete machine-readable inventory"
    )
    parser.add_argument("--page", help="Scope API results to a repository-relative Markdown page")
    parser.add_argument(
        "--check", action="store_true", help="Fail on API misses or unknown coverage"
    )
    args = parser.parse_args()
    if args.pages_only and (args.page or args.check):
        parser.error("--page and --check require the public API audit")
    if args.inspect:
        print(json.dumps(inspect_module_worker(args.inspect)))
        return
    root = Path(__file__).resolve().parent.parent
    report = generate_audit_report(root)
    if not args.pages_only:
        report["api"] = generate_api_report(root)
        if args.page:
            page = Path(args.page)
            if page.is_absolute() or ".." in page.parts or page.suffix != ".md":
                parser.error("--page must be a repository-relative Markdown path")
            report["api"] = page_api_report(root, report["api"], page.as_posix())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
        if "api" in report:
            print_api_report(report["api"], include_review=args.include_review)
    if args.check:
        passed = api_gate_passes(report["api"])
        if not args.json:
            print(
                "API gate: PASS" if passed else "API gate: FAIL (misses or unknown/empty coverage)"
            )
        raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
