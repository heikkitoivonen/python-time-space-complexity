#!/usr/bin/env python3
"""Introspection script to enumerate Python builtins and stdlib for documentation coverage."""

import argparse
import builtins
import contextlib
import importlib
import io
import sys
from types import ModuleType


@contextlib.contextmanager
def suppress_stdout():
    """Suppress stdout (some modules like 'this' print on import)."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout


def get_stdlib_modules() -> list[str]:
    """Get all stdlib module names, sorted alphabetically."""
    if hasattr(sys, "stdlib_module_names"):
        return sorted(sys.stdlib_module_names)
    raise RuntimeError("Python 3.10+ required for sys.stdlib_module_names")


def is_public(name: str) -> bool:
    """Check if a name is public (no leading underscore, no dunder)."""
    if name.startswith("_"):
        return False
    return True


def get_direct_members(cls: type) -> tuple[list[str], list[str]]:
    """Get methods and attributes defined directly on a class (not inherited)."""
    methods = []
    attributes = []

    for name in cls.__dict__:
        if not is_public(name):
            continue

        obj = cls.__dict__[name]

        if callable(obj) or isinstance(obj, (classmethod, staticmethod, property)):
            methods.append(name)
        else:
            attributes.append(name)

    return sorted(methods), sorted(attributes)


def get_module_contents(module: ModuleType) -> list[str]:
    """Get public content names of a module."""
    return sorted(name for name in dir(module) if is_public(name))


def get_builtin_items() -> list[tuple[str, object]]:
    """Get all public items from builtins module."""
    items = []
    for name in dir(builtins):
        if is_public(name):
            obj = getattr(builtins, name)
            items.append((f"builtins.{name}", obj))
    return items


def should_include_member(obj: object, module_name: str) -> bool:
    """Check if a module member should be included."""
    if isinstance(obj, ModuleType):
        return False
    obj_module = getattr(obj, "__module__", None)
    if obj_module and obj_module != module_name:
        if not obj_module.startswith(module_name + "."):
            return False
    return True


def get_module_member_items(
    module: ModuleType, module_name: str, seen: set[str]
) -> list[tuple[str, object]]:
    """Get public member items from a module."""
    items = []
    for name in dir(module):
        if not is_public(name):
            continue
        try:
            obj = getattr(module, name)
        except AttributeError:
            continue
        if not should_include_member(obj, module_name):
            continue
        full_name = f"{module_name}.{name}"
        if full_name not in seen:
            items.append((full_name, obj))
            seen.add(full_name)
    return items


def build_item_list() -> list[tuple[str, object]]:
    """Build the complete list of items to enumerate."""
    items = []
    seen_names: set[str] = set()

    # Add builtins
    for item in get_builtin_items():
        items.append(item)
        seen_names.add(item[0])

    # Add stdlib modules and their members
    for module_name in get_stdlib_modules():
        if module_name == "builtins":
            continue
        try:
            with suppress_stdout():
                module = importlib.import_module(module_name)
        except Exception:
            continue

        if module_name not in seen_names:
            items.append((module_name, module))
            seen_names.add(module_name)

        items.extend(get_module_member_items(module, module_name, seen_names))

    items.sort(key=lambda x: x[0].lower())
    return items


def format_module(module: ModuleType) -> list[str]:
    """Format a module's contents."""
    lines = ["Type: module"]
    contents = get_module_contents(module)
    if contents:
        lines.append("")
        lines.append("Contents:")
        lines.extend(f"  {c}" for c in contents)
    return lines


def format_class(cls: type) -> list[str]:
    """Format a class's methods and attributes."""
    lines = ["Type: class"]
    methods, attributes = get_direct_members(cls)

    if methods:
        lines.append("")
        lines.append("Methods:")
        lines.extend(f"  {m}" for m in methods)

    if attributes:
        lines.append("")
        lines.append("Attributes:")
        lines.extend(f"  {a}" for a in attributes)

    if not methods and not attributes:
        lines.append("")
        lines.append("(no public direct members)")

    return lines


def format_item(name: str, obj: object, next_name: str | None) -> str:
    """Format an item for output."""
    lines = [f"=== {name} ==="]

    if isinstance(obj, ModuleType):
        lines.extend(format_module(obj))
    elif isinstance(obj, type):
        lines.extend(format_class(obj))
    elif callable(obj):
        lines.append("Type: function")
    else:
        lines.append(f"Type: {type(obj).__name__}")

    lines.append("")
    lines.append(f"Next: {next_name}" if next_name else "This is the last item.")

    return "\n".join(lines)


def find_item_index(items: list[tuple[str, object]], target: str) -> int | None:
    """Find the index of an item by name."""
    for i, (item_name, _) in enumerate(items):
        if item_name == target:
            return i
    return None


def handle_next(items: list[tuple[str, object]], target: str) -> None:
    """Handle --next command."""
    found_idx = find_item_index(items, target)

    if found_idx is None:
        print(f"Error: '{target}' not found in item list.")
        print("")
        print("Hint: Use --start to see the first item, or check spelling.")
        sys.exit(1)

    if found_idx + 1 >= len(items):
        print(f"'{target}' is the last item. Documentation complete!")
        sys.exit(0)

    next_idx = found_idx + 1
    name, obj = items[next_idx]
    next_name = items[next_idx + 1][0] if next_idx + 1 < len(items) else None
    print(format_item(name, obj, next_name))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Introspect Python builtins and stdlib for documentation coverage"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Output the first item")
    group.add_argument("--next", metavar="NAME", help="Output the item after NAME")
    group.add_argument("--count", action="store_true", help="Output total item count")

    args = parser.parse_args()

    items = build_item_list()

    if args.count:
        print(f"Total items: {len(items)}")
    elif args.start:
        name, obj = items[0]
        next_name = items[1][0] if len(items) > 1 else None
        print(format_item(name, obj, next_name))
    else:
        handle_next(items, args.next)


if __name__ == "__main__":
    main()
