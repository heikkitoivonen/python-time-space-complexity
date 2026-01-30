"""Unit tests for the introspection script."""

import sys
from unittest.mock import MagicMock

from scripts.introspect import (
    build_item_list,
    find_item_index,
    format_class,
    format_item,
    format_module,
    get_builtin_items,
    get_direct_members,
    get_module_contents,
    get_stdlib_modules,
    is_public,
    main,
    should_include_member,
)


class TestIsPublic:
    """Tests for is_public function."""

    def test_public_name(self) -> None:
        assert is_public("append") is True
        assert is_public("Counter") is True
        assert is_public("my_function") is True

    def test_private_name_single_underscore(self) -> None:
        assert is_public("_private") is False
        assert is_public("_internal_method") is False

    def test_dunder_name(self) -> None:
        assert is_public("__init__") is False
        assert is_public("__len__") is False
        assert is_public("__module__") is False


class TestGetDirectMembers:
    """Tests for get_direct_members function."""

    def test_class_with_methods(self) -> None:
        class SampleClass:
            def method_a(self) -> None:
                pass

            def method_b(self) -> None:
                pass

        methods, attributes = get_direct_members(SampleClass)
        assert "method_a" in methods
        assert "method_b" in methods

    def test_class_with_attributes(self) -> None:
        class SampleClass:
            class_attr = "value"

        methods, attributes = get_direct_members(SampleClass)
        assert "class_attr" in attributes

    def test_excludes_private_members(self) -> None:
        class SampleClass:
            def _private_method(self) -> None:
                pass

            _private_attr = "secret"

        methods, attributes = get_direct_members(SampleClass)
        assert "_private_method" not in methods
        assert "_private_attr" not in attributes

    def test_excludes_dunder_members(self) -> None:
        class SampleClass:
            def __init__(self) -> None:
                pass

        methods, attributes = get_direct_members(SampleClass)
        assert "__init__" not in methods

    def test_excludes_inherited_members(self) -> None:
        class Parent:
            def parent_method(self) -> None:
                pass

        class Child(Parent):
            def child_method(self) -> None:
                pass

        methods, attributes = get_direct_members(Child)
        assert "child_method" in methods
        assert "parent_method" not in methods

    def test_returns_sorted_lists(self) -> None:
        class SampleClass:
            def zebra(self) -> None:
                pass

            def apple(self) -> None:
                pass

            def mango(self) -> None:
                pass

        methods, _ = get_direct_members(SampleClass)
        assert methods == sorted(methods)

    def test_classmethod_and_staticmethod(self) -> None:
        class SampleClass:
            @classmethod
            def class_method(cls) -> None:
                pass

            @staticmethod
            def static_method() -> None:
                pass

        methods, _ = get_direct_members(SampleClass)
        assert "class_method" in methods
        assert "static_method" in methods

    def test_property(self) -> None:
        class SampleClass:
            @property
            def my_property(self) -> str:
                return "value"

        methods, _ = get_direct_members(SampleClass)
        assert "my_property" in methods


class TestGetModuleContents:
    """Tests for get_module_contents function."""

    def test_returns_public_names(self) -> None:
        import collections

        contents = get_module_contents(collections)
        assert "Counter" in contents
        assert "deque" in contents

    def test_excludes_private_names(self) -> None:
        import collections

        contents = get_module_contents(collections)
        for name in contents:
            assert not name.startswith("_")

    def test_returns_sorted_list(self) -> None:
        import collections

        contents = get_module_contents(collections)
        assert contents == sorted(contents)


class TestGetBuiltinItems:
    """Tests for get_builtin_items function."""

    def test_returns_list_of_tuples(self) -> None:
        items = get_builtin_items()
        assert isinstance(items, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in items)

    def test_includes_common_builtins(self) -> None:
        items = get_builtin_items()
        names = [name for name, _ in items]
        assert "builtins.int" in names
        assert "builtins.str" in names
        assert "builtins.list" in names
        assert "builtins.len" in names
        assert "builtins.print" in names

    def test_excludes_private_builtins(self) -> None:
        items = get_builtin_items()
        for name, _ in items:
            # Name after "builtins." should not start with underscore
            member_name = name.split(".", 1)[1]
            assert not member_name.startswith("_")


class TestShouldIncludeMember:
    """Tests for should_include_member function."""

    def test_excludes_modules(self) -> None:
        import os

        assert should_include_member(os, "collections") is False

    def test_includes_native_member(self) -> None:
        from collections import Counter

        assert should_include_member(Counter, "collections") is True

    def test_excludes_imported_member(self) -> None:
        # Create a mock object that appears to be from a different module
        mock_obj = MagicMock()
        mock_obj.__module__ = "other_module"
        assert should_include_member(mock_obj, "collections") is False

    def test_includes_submodule_member(self) -> None:
        mock_obj = MagicMock()
        mock_obj.__module__ = "collections.abc"
        assert should_include_member(mock_obj, "collections") is True


class TestGetStdlibModules:
    """Tests for get_stdlib_modules function."""

    def test_returns_sorted_list(self) -> None:
        modules = get_stdlib_modules()
        assert modules == sorted(modules)

    def test_includes_common_modules(self) -> None:
        modules = get_stdlib_modules()
        assert "collections" in modules
        assert "os" in modules
        assert "sys" in modules
        assert "json" in modules

    def test_excludes_non_public_modules(self) -> None:
        modules = get_stdlib_modules()
        non_public = ["pydoc_data", "sre_compile", "sre_constants", "sre_parse"]
        for mod in non_public:
            assert mod not in modules


class TestBuildItemList:
    """Tests for build_item_list function."""

    def test_returns_list_of_tuples(self) -> None:
        items = build_item_list()
        assert isinstance(items, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in items)

    def test_items_are_sorted(self) -> None:
        items = build_item_list()
        names = [name.lower() for name, _ in items]
        assert names == sorted(names)

    def test_includes_builtins(self) -> None:
        items = build_item_list()
        names = [name for name, _ in items]
        assert "builtins.list" in names
        assert "builtins.dict" in names

    def test_includes_stdlib_modules(self) -> None:
        items = build_item_list()
        names = [name for name, _ in items]
        assert "collections" in names
        assert "json" in names

    def test_no_duplicate_names(self) -> None:
        items = build_item_list()
        names = [name for name, _ in items]
        assert len(names) == len(set(names))

    def test_excludes_private_stdlib_modules(self) -> None:
        """Private stdlib modules (single underscore) should be excluded."""
        items = build_item_list()
        names = [name for name, _ in items]
        # These are private stdlib modules that should be filtered out
        private_modules = ["_thread", "_abc", "_collections", "_io"]
        for mod in private_modules:
            assert mod not in names, f"Private module {mod} should be excluded"

    def test_excludes_non_public_stdlib_modules(self) -> None:
        items = build_item_list()
        names = [name for name, _ in items]
        non_public = ["pydoc_data", "sre_compile", "sre_constants", "sre_parse"]
        for mod in non_public:
            assert mod not in names, f"Non-public module {mod} should be excluded"

    def test_includes_dunder_stdlib_modules(self) -> None:
        """Dunder modules like __future__ should be included."""
        items = build_item_list()
        names = [name for name, _ in items]
        assert "__future__" in names


class TestFormatModule:
    """Tests for format_module function."""

    def test_includes_type_line(self) -> None:
        import collections

        lines = format_module(collections, False)
        assert "Type: module" in lines

    def test_includes_contents_header(self) -> None:
        import collections

        lines = format_module(collections, False)
        assert "Contents:" in lines

    def test_includes_module_contents(self) -> None:
        import collections

        lines = format_module(collections, False)
        output = "\n".join(lines)
        assert "Counter" in output
        assert "deque" in output

    def test_brief_returns_empty_list(self) -> None:
        """In brief mode, format_module returns empty list (members listed separately)."""
        import collections

        lines = format_module(collections, True)
        assert lines == []


class TestFormatClass:
    """Tests for format_class function."""

    def test_includes_type_line(self) -> None:
        lines = format_class(list, False)
        assert "Type: class" in lines

    def test_includes_methods_header(self) -> None:
        lines = format_class(list, False)
        assert "Methods:" in lines

    def test_includes_class_methods(self) -> None:
        lines = format_class(list, False)
        output = "\n".join(lines)
        assert "append" in output
        assert "pop" in output

    def test_empty_class_shows_no_members_message(self) -> None:
        class EmptyClass:
            pass

        lines = format_class(EmptyClass, False)
        assert "(no public direct members)" in lines

    def test_brief_returns_empty_list(self) -> None:
        """In brief mode, format_class returns empty list (members listed separately)."""
        lines = format_class(list, True)
        assert lines == []


class TestFormatItem:
    """Tests for format_item function."""

    def test_includes_name_header(self) -> None:
        output = format_item(
            "builtins.list",
            list,
            "builtins.locals",
            brief=False,
            include_next=True,
        )
        assert "=== builtins.list ===" in output

    def test_includes_next_line(self) -> None:
        output = format_item(
            "builtins.list",
            list,
            "builtins.locals",
            brief=False,
            include_next=True,
        )
        assert "Next: builtins.locals" in output

    def test_last_item_message(self) -> None:
        output = format_item("builtins.list", list, None, brief=False, include_next=True)
        assert "This is the last item." in output

    def test_formats_module(self) -> None:
        import collections

        output = format_item(
            "collections",
            collections,
            "collections.Counter",
            brief=False,
            include_next=True,
        )
        assert "Type: module" in output

    def test_formats_class(self) -> None:
        output = format_item(
            "builtins.list",
            list,
            "builtins.locals",
            brief=False,
            include_next=True,
        )
        assert "Type: class" in output
        assert "Methods:" in output

    def test_formats_function(self) -> None:
        output = format_item(
            "builtins.len",
            len,
            "builtins.license",
            brief=False,
            include_next=True,
        )
        assert "Type: function" in output

    def test_formats_other_types(self) -> None:
        output = format_item(
            "builtins.True",
            True,
            "builtins.tuple",
            brief=False,
            include_next=True,
        )
        assert "Type: bool" in output

    def test_brief_formats_name_only_header(self) -> None:
        output = format_item(
            "builtins.list",
            list,
            "builtins.locals",
            brief=True,
            include_next=True,
        )
        assert output.splitlines()[0] == "builtins.list"
        assert "Type:" not in output
        assert "Next:" not in output

    def test_brief_formats_function_as_name_only(self) -> None:
        output = format_item(
            "builtins.len",
            len,
            "builtins.license",
            brief=True,
            include_next=True,
        )
        assert output.strip() == "builtins.len"
        assert "Type:" not in output


class TestFindItemIndex:
    """Tests for find_item_index function."""

    def test_finds_existing_item(self) -> None:
        items: list[tuple[str, object]] = [("a", 1), ("b", 2), ("c", 3)]
        assert find_item_index(items, "b") == 1

    def test_returns_none_for_missing_item(self) -> None:
        items: list[tuple[str, object]] = [("a", 1), ("b", 2), ("c", 3)]
        assert find_item_index(items, "z") is None

    def test_finds_first_item(self) -> None:
        items: list[tuple[str, object]] = [("a", 1), ("b", 2), ("c", 3)]
        assert find_item_index(items, "a") == 0

    def test_finds_last_item(self) -> None:
        items: list[tuple[str, object]] = [("a", 1), ("b", 2), ("c", 3)]
        assert find_item_index(items, "c") == 2


class TestIntegration:
    """Integration tests for the script."""

    def test_full_workflow(self) -> None:
        """Test the full workflow of building and navigating items."""
        items = build_item_list()

        # Should have items
        assert len(items) > 0

        # First item should be formattable
        first_name, first_obj = items[0]
        second_name = items[1][0] if len(items) > 1 else None
        output = format_item(
            first_name,
            first_obj,
            second_name,
            brief=False,
            include_next=True,
        )
        assert first_name in output

        # Should be able to find items
        idx = find_item_index(items, first_name)
        assert idx == 0

    def test_builtins_list_format(self) -> None:
        """Test that builtins.list formats correctly with expected methods."""
        output = format_item(
            "builtins.list",
            list,
            "builtins.locals",
            brief=False,
            include_next=True,
        )

        assert "=== builtins.list ===" in output
        assert "Type: class" in output
        assert "Methods:" in output
        assert "append" in output
        assert "clear" in output
        assert "copy" in output
        assert "count" in output
        assert "extend" in output
        assert "index" in output
        assert "insert" in output
        assert "pop" in output
        assert "remove" in output
        assert "reverse" in output
        assert "sort" in output
        assert "Next: builtins.locals" in output

    def test_all_brief_has_no_blank_lines(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(sys, "argv", ["introspect.py", "--all", "--brief"])
        main()
        output = capsys.readouterr().out.strip()
        lines = output.splitlines()
        assert len(lines) > 1
        assert "" not in lines
