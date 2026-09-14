"""Public API discovery, name matching, page attribution, and failure reporting."""

from enum import Enum
from pathlib import Path
from types import ModuleType

import pytest

from scripts import audit_documentation as audit


def public_manifest(names: dict[str, str]) -> dict:
    """Supply explicit public scope for synthetic audit fixtures."""
    return {
        "available": True,
        "apis": {
            name: {"kind": kind, "source": f"https://docs.python.org/3.14/library/test.html#{name}"}
            for name, kind in names.items()
        },
    }


class Parent:
    def inherited(self) -> None:
        pass


def test_main_entry_points_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("probe")
    module.__main__ = lambda: None  # type: ignore[attr-defined]
    module.__all__ = ["__main__"]  # type: ignore[attr-defined]
    assert audit.inspect_public_api(module)["items"] == []
    apis = public_manifest({"probe.__main__.run": "function"})["apis"]
    assert audit.unresolved_documented(apis, set(), {"probe"}) == []
    modules, _ = audit.audited_modules(["probe", "probe.__main__"], apis)
    assert modules == ["probe"]
    monkeypatch.setattr(
        audit, "discover_modules", lambda: (["probe"], ["probe.__main__", "idlelib"])
    )
    _, excluded = audit.audited_modules(None, apis)
    assert excluded == ["idlelib"]


class Example(Parent):
    annotated: str

    def __init__(self) -> None:
        self.field = 1

    @property
    def descriptor(self) -> int:
        raise AssertionError("Inspection must not invoke properties")

    @classmethod
    def factory(cls) -> None:
        pass

    class Nested:
        VALUE = 1

        def __init__(self) -> None:
            self.nested_field = 2


class Colour(Enum):
    RED = 1
    ALIAS = 1
    Blue = 2


def test_inventory_includes_members_and_does_not_execute_descriptors() -> None:
    module = ModuleType("probe")
    module.Example = Example  # type: ignore[attr-defined]
    module.Colour = Colour  # type: ignore[attr-defined]
    module.CONSTANT = 7  # type: ignore[attr-defined]
    module._private = 1  # type: ignore[attr-defined]
    result = audit.inspect_public_api(module)
    assert not result["errors"]
    names = {item["name"]: item["kind"] for item in result["items"]}
    assert names["probe.Example"] == "class"
    assert "probe.CONSTANT" not in names
    assert names["probe.Example.factory"] == "method"
    assert names["probe.Example.inherited"] == "method"
    assert names["probe.Example.descriptor"] == "attribute"
    assert "probe.Example.field" not in names
    assert "probe.Example.annotated" not in names
    assert "probe.Example.Nested.VALUE" not in names
    assert "probe.Colour.RED" not in names
    assert "probe.Colour.ALIAS" not in names
    assert "probe.Colour.Blue" not in names
    assert "probe.Colour" in names
    assert "probe._private" not in names
    assert "probe.Example.__init__" not in names
    assert "probe.Example.__delattr__" not in names
    assert not any(name.rsplit(".", 1)[-1].startswith("__") for name in names)
    assert "probe.Example.Nested.nested_field" not in names
    assert "probe.Example.nested_field" not in names


@pytest.mark.parametrize("module", ["builtins", "enum"])
def test_builtin_descriptors_do_not_break_inventory(module: str) -> None:
    result = audit.inspect_module_worker(module)
    assert result["errors"] == []
    names = {item["name"] for item in result["items"]}
    assert not any(
        name.count(".") >= 2 and name.rsplit(".", 1)[-1].startswith("__") for name in names
    )
    if module == "builtins":
        assert "builtins.type.mro" in names
        assert "builtins.memoryview.nbytes" in names
        assert "builtins.__import__" in names
        assert "builtins.__debug__" not in names
        assert all(f"builtins.{name}" not in names for name in audit.BUILTIN_CONSTANTS)
    else:
        assert "enum.EnumMeta.mro" in names


def test_matching_scopes_members_and_detects_removed_names() -> None:
    text = "## First\n`run/stop()`\n## Second\n`start()`\nx = Second()\nx.close()"
    assert audit.documents_name(text, "probe", "probe.First.run")
    assert audit.documents_name(text, "probe", "probe.First.stop")
    assert not audit.documents_name(text, "probe", "probe.Second.run")
    assert audit.documents_name(text, "probe", "probe.Second.close")
    changed = text.replace("run/stop", "run")
    assert changed != text
    assert not audit.documents_name(changed, "probe", "probe.First.stop")
    assert not audit.mentions("restart starting", "start")
    assert audit.documents_name("`Counter.update()`", "collections", "collections.Counter.update")


def test_page_mapping(tmp_path: Path) -> None:
    stdlib = tmp_path / "docs" / "stdlib"
    stdlib.mkdir(parents=True)
    for name in ("collections", "counter", "xml", "xml.dom", "cprofile"):
        (stdlib / f"{name}.md").touch()
    assert (
        audit.documentation_page(tmp_path, "collections", "collections.Counter.update")
        == stdlib / "counter.md"
    )
    assert (
        audit.documentation_page(tmp_path, "xml.dom.minidom", "xml.dom.minidom.Node")
        == stdlib / "xml.dom.md"
    )
    assert (
        audit.documentation_page(tmp_path, "cProfile", "cProfile.Profile") == stdlib / "cprofile.md"
    )
    assert (
        audit.documentation_page(tmp_path, "builtins", "builtins.ValueError.args").name
        == "exceptions.md"
    )
    assert (
        audit.documentation_page(tmp_path, "builtins", "builtins.memoryview.nbytes").name
        == "memoryview_func.md"
    )


def test_report_ranks_all_defects_and_preserves_unknowns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdlib = tmp_path / "docs" / "stdlib"
    stdlib.mkdir(parents=True)
    (stdlib / "small.md").write_text("`present()`")

    def inspect(name: str) -> tuple[str, dict]:
        items = []
        errors = []
        if name == "large":
            items = [{"name": f"large.item{i}", "kind": "attribute"} for i in range(30)]
        elif name == "small":
            items = [
                {"name": "small.present", "kind": "function"},
                {"name": "small.absent", "kind": "function"},
            ]
        elif name == "unavailable":
            errors = ["unavailable: ImportError: platform"]
        return name, {"items": items, "errors": errors}

    monkeypatch.setattr(audit, "inspect_module", inspect)
    manifest = public_manifest(
        {
            "small": "module",
            "large": "module",
            "unavailable": "module",
            "small.present": "function",
            "small.absent": "function",
            **{f"large.item{i}": "attribute" for i in range(30)},
        }
    )
    report = audit.generate_api_report(tmp_path, ["small", "large", "unavailable"], manifest)
    assert [(page["file"], page["defects"]) for page in report["pages"]] == [
        ("docs/stdlib/large.md", 31),
        ("docs/stdlib/small.md", 1),
    ]
    assert report["inspection_errors"] == ["unavailable: ImportError: platform"]
    audit.print_api_report(report)
    output = capsys.readouterr().out
    assert "large.item29" in output
    assert "MISSING FILE" in output
    assert "coverage unknown" in output


def test_discovery_stays_in_stdlib_and_finds_submodules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "probe"
    package.mkdir()
    (package / "__init__.py").touch()
    (package / "child.py").touch()
    (package / "_private.py").touch()
    (package / "__main__.py").touch()
    tests = package / "tests"
    tests.mkdir()
    (tests / "__init__.py").touch()
    (tmp_path / "third_party.py").touch()
    monkeypatch.setattr(audit, "get_all_stdlib_modules", lambda: ["probe", "unavailable"])
    monkeypatch.setattr(audit.sysconfig, "get_path", lambda _: str(tmp_path))
    modules, excluded = audit.discover_modules()
    assert modules == ["probe", "probe.child", "unavailable"]
    assert excluded == ["probe.__main__", "probe.tests"]


def test_structured_singleton_members() -> None:
    result = audit.inspect_module_worker("sys")
    assert result["errors"] == []
    names = {item["name"] for item in result["items"]}
    assert "sys.flags.debug" in names
    assert "sys.float_info.max" in names
    assert "sys.implementation.cache_tag" in names


def test_import_timeout_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        assert kwargs["stdin"] == audit.subprocess.DEVNULL
        assert kwargs["timeout"] == 20
        raise audit.subprocess.TimeoutExpired("probe", 20)

    monkeypatch.setattr(audit.subprocess, "run", timeout)
    name, result = audit.inspect_module("probe")
    assert name == "probe"
    assert result["items"] == []
    assert "TimeoutExpired" in result["errors"][0]


@pytest.mark.parametrize("module_name", ["tkinter", "tkinter.constants", "tkinter.ttk", "other"])
def test_uppercase_constants_are_excluded(module_name: str) -> None:
    module = ModuleType(module_name)
    vars(module).update(ACTIVE="active", ALL="all", lower=[], Example=Example)
    result = audit.inspect_public_api(module)
    assert result["errors"] == []
    names = {item["name"] for item in result["items"]}
    assert f"{module_name}.ACTIVE" not in names
    assert f"{module_name}.ALL" not in names
    assert f"{module_name}.Example.Nested.VALUE" not in names
    assert f"{module_name}.lower" in names
    assert f"{module_name}.Example.inherited" in names
    control = ModuleType("other")
    vars(control)["ACTIVE"] = "active"
    assert {item["name"] for item in audit.inspect_public_api(control)["items"]} == set()


def test_encodings_keeps_registry_and_aliases_but_excludes_codec_bindings() -> None:
    module = ModuleType("encodings")
    vars(module).update(
        cp865=ModuleType("encodings.cp865"),
        utf_8=ModuleType("encodings.utf_8"),
        aliases=ModuleType("encodings.aliases"),
        sys=ModuleType("sys"),
        normalize_encoding=lambda value: value,
    )
    result = audit.inspect_public_api(module)
    assert result["errors"] == []
    assert {item["name"] for item in result["items"]} == {
        "encodings.aliases",
        "encodings.sys",
        "encodings.normalize_encoding",
    }


def test_codec_modules_are_excluded_from_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "encodings"
    package.mkdir()
    for name in ("__init__", "cp865", "utf_8", "aliases"):
        (package / f"{name}.py").touch()
    monkeypatch.setattr(audit, "get_all_stdlib_modules", lambda: ["encodings"])
    monkeypatch.setattr(audit.sysconfig, "get_path", lambda _: str(tmp_path))
    modules, excluded = audit.discover_modules()
    assert modules == ["encodings", "encodings.aliases"]
    assert excluded == ["encodings.cp865", "encodings.utf_8"]


class Override(Example):
    def inherited(self) -> None:
        pass


class Aliases(Example):
    renamed = Parent.inherited
    response_class = Example
    same_a = 1
    same_b = 1


def test_api_identities_merge_aliases_but_preserve_overrides_and_attributes() -> None:
    module = ModuleType("probe")
    vars(module).update(
        Parent=Parent,
        Example=Example,
        Again=Example,
        Aliases=Aliases,
        Override=Override,
        Colour=Colour,
        one=[],
        also_one=[],
    )
    result = audit.inspect_public_api(module)
    assert not result["errors"]
    identities = {item["name"]: item["identity"] for item in result["items"]}
    assert identities["probe.Parent.inherited"] == identities["probe.Example.inherited"]
    assert identities["probe.Aliases.renamed"] == identities["probe.Parent.inherited"]
    assert identities["probe.Override.inherited"] != identities["probe.Parent.inherited"]
    assert identities["probe.Example"] == identities["probe.Again"]
    assert identities["probe.Aliases.response_class"] == identities["probe.Example"]
    assert identities["probe.Aliases.response_class.factory"] == identities["probe.Example.factory"]
    assert identities["probe.Aliases.same_a"] != identities["probe.Aliases.same_b"]
    assert identities["probe.one"] != identities["probe.also_one"]


def test_deduplication_across_workers_and_alias_documentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdlib = tmp_path / "docs" / "stdlib"
    stdlib.mkdir(parents=True)
    (stdlib / "origin.md").write_text("")
    (stdlib / "alias.md").write_text("`Renamed.inherited()`")

    def inspect(name: str) -> tuple[str, dict]:
        module = ModuleType(name)
        if name == "origin":
            vars(module).update(Parent=Parent, Example=Example)
        elif name == "alias":
            vars(module).update(Renamed=Example)
        return name, audit.inspect_public_api(module)

    monkeypatch.setattr(audit, "inspect_module", inspect)
    manifest = public_manifest(
        {
            "origin": "module",
            "alias": "module",
            "origin.Parent": "class",
            "origin.Example": "class",
            "origin.Parent.inherited": "method",
        }
    )
    report = audit.generate_api_report(tmp_path, ["origin", "alias"], manifest)
    items = [item for page in report["pages"] for item in page["items"]]
    inherited = [item for item in items if item["identity"].endswith(".Parent.inherited")]
    assert len(inherited) == 1
    assert inherited[0]["name"] == "origin.Parent.inherited"
    assert inherited[0]["covered"]
    assert set(inherited[0]["aliases"]) == {"origin.Example.inherited", "alias.Renamed.inherited"}
    classes = [item for item in items if item["identity"].endswith(".Example")]
    assert len(classes) == 1
    assert classes[0]["name"] == "origin.Example"
    (stdlib / "alias.md").write_text("")
    manifest = public_manifest(
        {
            "origin": "module",
            "alias": "module",
            "origin.Parent": "class",
            "origin.Example": "class",
            "origin.Parent.inherited": "method",
        }
    )
    report = audit.generate_api_report(tmp_path, ["origin", "alias"], manifest)
    missing = [item for page in report["pages"] for item in page["missing"]]
    assert sum(item["identity"].endswith(".Parent.inherited") for item in missing) == 1


def test_real_reexports_have_process_independent_identities() -> None:
    pytest.importorskip("tkinter")
    _, root = audit.inspect_module("tkinter")
    _, child = audit.inspect_module("tkinter.simpledialog")
    assert not root["errors"]
    assert not child["errors"]
    first = {item["name"]: item["identity"] for item in root["items"]}
    second = {item["name"]: item["identity"] for item in child["items"]}
    assert first["tkinter.Frame"] == second["tkinter.simpledialog.Frame"]
    assert first["tkinter.Frame.configure"] == second["tkinter.simpledialog.Button.configure"]


def test_data_reexports_share_identity_without_merging_different_bindings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    source = ModuleType("origin_data")
    target = ModuleType("alias_data")
    source_path = tmp_path / "origin_data.py"
    target_path = tmp_path / "alias_data.py"
    source_path.write_text("payload = []\nother = []\n")
    target_path.write_text("from origin_data import *\nfrom origin_data import payload as copied\n")
    vars(source).update(__file__=str(source_path), payload=[], other=[])
    vars(target).update(
        __file__=str(target_path),
        payload=vars(source)["payload"],
        copied=vars(source)["payload"],
        other=vars(source)["other"],
    )
    monkeypatch.setitem(sys.modules, source.__name__, source)
    monkeypatch.setitem(sys.modules, target.__name__, target)
    first = {item["name"]: item["identity"] for item in audit.inspect_public_api(source)["items"]}
    second = {item["name"]: item["identity"] for item in audit.inspect_public_api(target)["items"]}
    assert first["origin_data.payload"] == second["alias_data.payload"]
    assert first["origin_data.payload"] == second["alias_data.copied"]
    assert first["origin_data.payload"] != first["origin_data.other"]


def test_lowercase_math_constants_are_excluded() -> None:
    result = audit.inspect_module_worker("math")
    assert not result["errors"]
    names = {item["name"] for item in result["items"]}
    assert "math.sqrt" in names
    assert names.isdisjoint({"math.pi", "math.e", "math.tau", "math.inf", "math.nan"})
    assert all(item["kind"] != "constant" for item in result["items"])


def test_documented_json_fields_are_kept_but_constructor_internals_are_not() -> None:
    import json

    manifest = public_manifest(
        {
            "json.JSONDecodeError.msg": "attribute",
            "json.JSONDecodeError.doc": "attribute",
            "json.JSONDecodeError.pos": "attribute",
            "json.JSONDecodeError.lineno": "attribute",
            "json.JSONDecodeError.colno": "attribute",
        }
    )
    result = audit.inspect_public_api(json, manifest["apis"])
    assert not result["errors"]
    names = {item["name"] for item in result["items"]}
    assert set(manifest["apis"]) <= names
    assert "json.JSONDecoder.memo" not in names
    assert "json.JSONDecoder.scan_once" not in names


def test_json_c_scanner_aliases_share_identity() -> None:
    result = audit.inspect_module_worker("json.scanner")
    assert not result["errors"]
    identities = {item["name"]: item["identity"] for item in result["items"]}
    assert identities["json.scanner.c_make_scanner"] == identities["json.scanner.make_scanner"]


def test_unclassified_exports_do_not_increase_actionable_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = ModuleType("probe")
    vars(module).update(__all__=["promised"], promised=lambda: None, helper=lambda: None)
    manifest = public_manifest({"probe": "module"})

    def inspect(name: str) -> tuple[str, dict]:
        result = (
            audit.inspect_public_api(module, {}) if name == "probe" else {"items": [], "errors": []}
        )
        return name, result

    monkeypatch.setattr(audit, "inspect_module", inspect)
    report = audit.generate_api_report(tmp_path, ["probe"], manifest)
    assert report["missing_names"] == 1
    assert report["pages"][0]["missing"][0]["name"] == "probe"
    review = {item["name"]: item for item in report["needs_classification"]}
    assert set(review) == {"probe.promised", "probe.helper"}
    assert "__all__" in review["probe.promised"]["reason"]
    assert "Runtime discovery" in review["probe.helper"]["reason"]
    audit.print_api_report(report)
    assert "probe.helper" not in capsys.readouterr().out
    audit.print_api_report(report, include_review=True)
    output = capsys.readouterr().out
    assert "probe.helper" in output
    assert "not actionable gaps" in output


def test_missing_manifest_is_explicit_and_never_promotes_discoveries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = audit.load_public_manifest("9.9", tmp_path)
    assert not manifest["available"]
    assert "classification is pending" in manifest["notice"]
    monkeypatch.setattr(audit, "inspect_module", lambda name: (name, {"items": [], "errors": []}))
    report = audit.generate_api_report(tmp_path, ["probe"], manifest)
    assert report["missing_names"] == 0
    assert report["unclassified_names"] == 1
    assert report["pages"] == []


def test_mismatched_manifest_is_rejected(tmp_path: Path) -> None:
    import json

    (tmp_path / "python-3.14.json").write_text(
        json.dumps({"schema_version": 1, "python_version": "3.13"})
    )
    with pytest.raises(ValueError, match="mismatched"):
        audit.load_public_manifest("3.14", tmp_path)


def test_official_json_inventory_limits_the_actionable_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = audit.load_public_manifest()
    assert manifest["available"]
    modules = ["json", "json.decoder", "json.encoder", "json.scanner", "json.tool"]
    results = {name: audit.inspect_module_worker(name) for name in modules}
    results["builtins"] = {"items": [], "errors": [], "available": False}
    monkeypatch.setattr(audit, "inspect_module", lambda name: (name, results[name]))
    report = audit.generate_api_report(tmp_path, modules, manifest)
    expected = {name for name in manifest["apis"] if name == "json" or name.startswith("json.")}
    actionable = {item["name"] for page in report["pages"] for item in page["missing"]}
    assert len(expected) == 19
    assert actionable == expected
    assert "json.JSONDecoder.raw_decode" in actionable
    assert "json.JSONEncoder.iterencode" in actionable
    assert "json.tool" in actionable
    assert "json.detect_encoding" not in actionable
    review = {item["name"]: item for item in report["needs_classification"]}
    scanner_groups = [
        item
        for item in review.values()
        if "json.scanner.c_make_scanner" in {item["name"], *item["aliases"]}
    ]
    assert len(scanner_groups) == 1
    assert "json.scanner.make_scanner" in {scanner_groups[0]["name"], *scanner_groups[0]["aliases"]}


def test_module_alias_uses_documented_spelling_and_shared_identity() -> None:
    import os

    alias = audit.inspect_module_worker("os.path")
    original = audit.inspect_module_worker(os.path.__name__)
    assert not alias["errors"]
    assert alias["module_identity"] == original["module_identity"]
    aliases = {item["name"]: item["identity"] for item in alias["items"]}
    originals = {item["name"]: item["identity"] for item in original["items"]}
    assert aliases["os.path.join"] == originals[f"{os.path.__name__}.join"]


def test_documented_module_attribute_can_be_inspected() -> None:
    import sys

    if not hasattr(sys, "monitoring"):
        pytest.skip("sys.monitoring is available from Python 3.12")
    result = audit.inspect_module_worker("sys.monitoring")
    assert result["available"]
    assert not result["errors"]
    assert "sys.monitoring.get_events" in {item["name"] for item in result["items"]}


def test_documented_c_type_aliases_share_identity() -> None:
    first = audit.inspect_module_worker("contextlib")
    second = audit.inspect_module_worker("types")
    assert not first["errors"]
    assert not second["errors"]
    context = {item["name"]: item["identity"] for item in first["items"]}
    types = {item["name"]: item["identity"] for item in second["items"]}
    assert context["contextlib.MethodType"] == types["types.MethodType"]


def test_inspection_uses_stdlib_distutils() -> None:
    import sys

    if sys.version_info >= (3, 12):
        pytest.skip("distutils is removed from the standard library in Python 3.12")
    _, result = audit.inspect_module("distutils.bcppcompiler")
    assert result["available"]
    assert not result["errors"]
    assert "distutils.bcppcompiler.BCPPCompiler" in {item["name"] for item in result["items"]}


@pytest.mark.parametrize(
    ("source", "covered"),
    [
        (
            'with os.scandir(".") as entries:\n    for entry in entries:\n        print(entry.is_file())',
            True,
        ),
        ('for entry in os.scandir("."):\n    print(entry.name)', True),
        ("for entry in other_entries:\n    print(entry.name)", False),
        ('for entry in os.scandir("."):\n    entry = other\n    print(entry.name)', False),
        (
            'with os.scandir(".") as entries:\n    pass\nfor entry in entries:\n    print(entry.name)',
            False,
        ),
        (
            'with os.scandir(".") as entries:\n    entries = other\n    for entry in entries:\n        print(entry.name)',
            False,
        ),
    ],
)
def test_scandir_examples_identify_only_bound_direntry_members(source: str, covered: bool) -> None:
    text = f"```python\n{source}\n```"
    member = "is_file" if "is_file" in source else "name"
    assert audit.documents_name(text, "os", f"os.DirEntry.{member}") is covered
    assert not audit.documents_name(text, "os", "os.DirEntry.inode")
    assert not audit.documents_name(text, "probe", f"probe.Other.{member}")


def test_absent_struct_sequence_fields_remain_unresolved() -> None:
    import os

    manifest = public_manifest(
        {"os.stat_result.st_mode": "attribute", "os.stat_result.unavailable_field": "attribute"}
    )
    result = audit.inspect_public_api(os, manifest["apis"])
    names = {item["name"] for item in result["items"]}
    assert "os.stat_result.st_mode" in names
    assert "os.stat_result.unavailable_field" not in names
    unresolved = audit.unresolved_documented(manifest["apis"], names, {"os"})
    assert [item["name"] for item in unresolved] == ["os.stat_result.unavailable_field"]


def test_page_gate_includes_submodules_and_preserves_review_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs" / "stdlib"
    docs.mkdir(parents=True)
    page = docs / "probe.md"
    page.write_text("probe probe.child present")
    manifest = public_manifest(
        {
            "probe": "module",
            "probe.child": "module",
            "probe.child.present": "function",
            "probe.child.absent": "function",
            "probe.child.unavailable": "function",
            "other": "module",
        }
    )
    monkeypatch.setattr(audit, "load_public_manifest", lambda: manifest)

    def inspect(name: str) -> tuple[str, dict]:
        if name == "other":
            return name, {"items": [], "errors": ["other: ImportError: unavailable"]}
        names = ["present", "absent", "unclassified"] if name == "probe.child" else []
        return name, {
            "items": [{"name": f"{name}.{member}", "kind": "function"} for member in names],
            "errors": [],
        }

    monkeypatch.setattr(audit, "inspect_module", inspect)

    def scoped() -> dict:
        report = audit.generate_api_report(tmp_path, ["probe", "probe.child", "other"], manifest)
        return audit.page_api_report(tmp_path, report, "docs/stdlib/probe.md")

    report = scoped()
    assert report["missing_names"] == 1
    assert not audit.api_gate_passes(report)
    assert not report["inspection_errors"]
    assert [item["name"] for item in report["unresolved_documented"]] == ["probe.child.unavailable"]
    assert [item["name"] for item in report["needs_classification"]] == ["probe.child.unclassified"]
    page.write_text(page.read_text() + " absent")
    report = scoped()
    assert audit.api_gate_passes(report)
    assert report["unresolved_documented"]  # Passing name coverage still needs human review.
    assert not audit.api_gate_passes(audit.page_api_report(tmp_path, report, "docs/stdlib/typo.md"))
    report["inspection_errors"] = ["probe.child: TimeoutExpired"]
    assert not audit.api_gate_passes(report)
    report["inspection_errors"] = []
    report["manifest"] = {"available": False}
    assert not audit.api_gate_passes(report)


@pytest.mark.parametrize(("missing", "expected"), [(0, 0), (1, 1)])
def test_check_exit_status_and_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], missing: int, expected: int
) -> None:
    import json
    import sys

    monkeypatch.setattr(sys, "argv", ["audit", "--check", "--json"])
    monkeypatch.setattr(audit, "generate_audit_report", lambda root: {})
    monkeypatch.setattr(
        audit,
        "generate_api_report",
        lambda root: {
            "manifest": {"available": True},
            "total_names": 1,
            "missing_names": missing,
            "inspection_errors": [],
        },
    )
    with pytest.raises(SystemExit) as exc:
        audit.main()
    assert exc.value.code == expected
    assert json.loads(capsys.readouterr().out)["api"]["missing_names"] == missing
