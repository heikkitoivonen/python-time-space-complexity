# Public API inventory

`python-<major>.<minor>.json` is an offline snapshot of the official Python
Sphinx object inventory. Each entry records a documented name, kind, and source
link. The metadata records the documentation release and the input SHA-256.

Snapshots are included for every supported minor version: Python 3.10, 3.11,
3.12, 3.13, and 3.14. The running interpreter selects its matching snapshot;
APIs added or removed in another minor version do not enter its inventory.

To audit a specific supported version without changing the project environment:

```sh
uv run --no-project --python 3.10 python scripts/audit_documentation.py
```

Replace `3.10` with the desired minor or exact patch version. The report identifies
the interpreter and platform used; optional and platform-specific modules may
remain unavailable.
Inspection subprocesses disable site-package loading so installed packages cannot
replace standard-library modules such as `distutils` on Python 3.10 and 3.11.

The audit ranks only missing, runtime-available APIs in this inventory. It keeps
unclassified runtime discoveries in a separate report section; `__all__` is
supporting evidence for review, not automatic promotion to the actionable list.
Only explicitly documented instance attributes supplement runtime inspection.
Unavailable or unresolved documented APIs are listed separately. Constants,
class dunders, individual codecs, and the audit's program exclusions still apply.
A name mention is coverage evidence, not verification of a complexity claim.

A manifest applies to its Python minor version. If no matching snapshot exists,
the report explicitly says classification is pending and does not invent an
actionable ranking. There are no network requests during ordinary audits. The default text output lists
actionable gaps and summary counts; use `--include-review` for classification
details, or `--json` for the complete structured inventory.

To refresh a snapshot, use the matching interpreter, verify the documentation
release shown on the official site, download its inventory, then run:

```sh
curl --fail --location https://docs.python.org/3.14/objects.inv --output /tmp/python-3.14-objects.inv
uv run python scripts/build_api_manifest.py \
  --inventory /tmp/python-3.14-objects.inv \
  --documentation-version 3.14.7 \
  --source-url https://docs.python.org/3.14/objects.inv \
  --output scripts/api_manifests/python-3.14.json
```

Review the generated diff and run the focused audit tests. Do not infer a public
API solely from a runtime discovery or silently exempt a newly discovered name.
Python's object index does not capture every prose-only API contract or parameter;
those remain review work rather than presumed defects.

## Page review gate

Run the full inventory with results scoped to the English page being reviewed:

```sh
uv run python scripts/audit_documentation.py --page docs/stdlib/os.md --check --include-review
```

Page scope includes submodules assigned to that page and preserves cross-module
alias deduplication. `--check` exits with status 1 for missing APIs, an empty
scope, an unavailable manifest, or inspection errors in scope. Without `--check`,
the audit remains informational. `--json` works with both options.

A passing gate establishes name coverage only. Review the remaining unresolved
and unclassified diagnostics explicitly, including version/platform limitations;
then verify bounds and examples with the module's claim tests. Documented fields
of struct-sequence results are actionable only when their class descriptors are
available; absent platform fields remain in unresolved diagnostics.
