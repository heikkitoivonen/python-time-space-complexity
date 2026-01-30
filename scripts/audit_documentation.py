"""Audit script to identify documentation gaps for builtins and stdlib modules."""

import builtins
import inspect
import json
import pkgutil
from pathlib import Path
from typing import Any


def get_all_builtins() -> dict[str, list[str]]:
    """Get all built-in functions, types, and exceptions."""
    builtin_items: dict[str, list[str]] = {}

    for name in dir(builtins):
        obj = getattr(builtins, name)
        if name.startswith("_"):
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
    """Get list of all standard library modules."""
    stdlib_modules: list[str] = []
    non_public = {
        "pydoc_data",
        "sre_compile",
        "sre_constants",
        "sre_parse",
    }

    for _importer, modname, _ispkg in pkgutil.iter_modules():
        # Filter to main stdlib modules (no underscores at start)
        if not modname.startswith("_") and modname not in non_public:
            stdlib_modules.append(modname)

    return sorted(stdlib_modules)


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

    # Find gaps
    missing_builtins = [b for b in all_builtins if b not in documented["builtins"]]
    missing_stdlib = [s for s in stdlib_modules if s not in documented["stdlib"]]

    # Create report
    report: dict[str, Any] = {
        "timestamp": None,
        "builtins": {
            "total": len(all_builtins),
            "documented": len(documented["builtins"]),
            "coverage_percent": round(
                100 * len(documented["builtins"]) / len(all_builtins), 1
            ),
            "missing": sorted(missing_builtins),
            "by_category": builtins_by_category,
        },
        "stdlib": {
            "total": len(stdlib_modules),
            "documented": len(documented["stdlib"]),
            "coverage_percent": round(
                100 * len(documented["stdlib"]) / len(stdlib_modules), 1
            ),
            "missing": missing_stdlib,
        },
        "summary": {
            "total_items": len(all_builtins) + len(stdlib_modules),
            "total_documented": len(documented["builtins"])
            + len(documented["stdlib"]),
            "overall_coverage_percent": round(
                100
                * (len(documented["builtins"]) + len(documented["stdlib"]))
                / (len(all_builtins) + len(stdlib_modules)),
                1,
            ),
        },
    }

    return report


def save_audit_report(report: dict[str, Any], workspace_root: Path) -> Path:
    """Save audit report to JSON file."""
    data_dir = workspace_root / "data"
    data_dir.mkdir(exist_ok=True)

    report_file = data_dir / "documentation_audit.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    return report_file


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted report to console."""
    print("\n" + "=" * 70)
    print("DOCUMENTATION COVERAGE AUDIT")
    print("=" * 70)

    print("\n📦 BUILTINS")
    print(f"  Total: {report['builtins']['total']}")
    print(f"  Documented: {report['builtins']['documented']}")
    print(f"  Coverage: {report['builtins']['coverage_percent']}%")

    if report["builtins"]["missing"]:
        print(f"\n  ❌ Missing ({len(report['builtins']['missing'])}):")
        for item in report["builtins"]["missing"][:20]:  # Show first 20
            print(f"    - {item}")
        if len(report["builtins"]["missing"]) > 20:
            print(
                f"    ... and {len(report['builtins']['missing']) - 20} more"
            )

    print("\n📚 STDLIB MODULES")
    print(f"  Total: {report['stdlib']['total']}")
    print(f"  Documented: {report['stdlib']['documented']}")
    print(f"  Coverage: {report['stdlib']['coverage_percent']}%")

    if report["stdlib"]["missing"]:
        print(f"\n  ❌ Missing ({len(report['stdlib']['missing'])}):")
        for item in report["stdlib"]["missing"][:20]:  # Show first 20
            print(f"    - {item}")
        if len(report["stdlib"]["missing"]) > 20:
            print(f"    ... and {len(report['stdlib']['missing']) - 20} more")

    print("\n📊 OVERALL")
    print(f"  Total Items: {report['summary']['total_items']}")
    print(f"  Documented: {report['summary']['total_documented']}")
    print(f"  Coverage: {report['summary']['overall_coverage_percent']}%")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    workspace_root = Path(__file__).parent.parent

    # Generate report
    report = generate_audit_report(workspace_root)

    # Save to JSON
    report_file = save_audit_report(report, workspace_root)
    print(f"✅ Audit report saved to: {report_file}")

    # Print to console
    print_report(report)
