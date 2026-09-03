---
name: updating-python-support
description: Updates this repository's supported Python range when an old version reaches EOL or a new final version is released. Covers package metadata, CI pins, version references, documentation, translations, tests, and lockfile verification.
---

# Updating Python Support

Change the supported Python range without erasing useful history or leaving the
site, package metadata, CI, and tests disagreeing about what is supported.

## Establish the Transition

1. Identify the version being dropped, the version being added, or both.
2. Verify against official Python sources that:
   - a dropped version has reached its official EOL date; and
   - an added version has reached its official final release date.
3. Do not add alpha, beta, or release-candidate versions. Do not drop a version
   before EOL.
4. Find the latest patch release for the new oldest and newest supported minor
   versions. CI pins exact patch releases, not minor-only versions.
5. Record the old and new inclusive support ranges before editing. Use these as
   the audit criteria throughout the change.

Prefer python.org release and lifecycle pages, the released version's official
"What's New" document, and the matching released CPython branch. Do not use
CPython `main` as evidence for a final release.

## Update Package and Tool Metadata

Edit `pyproject.toml` as one coherent source-of-support change:

- Raise `project.requires-python` when the minimum supported version changes.
- Remove the dropped `Programming Language :: Python :: 3.x` classifier.
- Add the new final version's classifier.
- Keep the classifiers continuous across the supported range.
- Raise Ruff's `target-version` when it names the dropped minimum version.

Search for other tool-specific minimum or target versions before assuming these
are the only settings. Regenerate `uv.lock` with `uv lock`; never hand-edit its
`requires-python` value or dependency markers. Review dependency resolution and
conditional markers introduced or removed by the new range.

## Update CI Boundary Versions

In `.github/workflows/deploy.yml`, keep the timing matrix on exactly the oldest
and newest supported minor lines, each pinned to its latest patch release.

- Replace the old lower boundary when support is dropped.
- Replace the old upper boundary when support is added.
- Preserve `fail-fast: false` and the patched-Python enforcement.
- Re-read nearby comments and version-specific skip logic. Update comments that
  describe the support boundaries, but retain historical examples that remain
  true.
- Confirm every pinned patch includes any security or correctness fix that the
  tests require. The latest patch should satisfy this; verify rather than infer.

## Audit Every Version Reference

Search the repository for both old boundary versions and the new version before
editing. Use exact forms broad enough to find prose, config, paths, and symbols,
for example:

```bash
rg -n '3\.10|3\.14|py310|py314|3\.10[–-]3\.14' \
  --glob '!uv.lock' --glob '!site/**' --glob '!.venv/**'
```

Adapt the numbers and search separately when a combined expression would hide
results. Inspect every match; never bulk-replace version numbers.

Update a match when it expresses the current supported set or a support
boundary, including:

- site introductions, support badges, metadata, and `docs/llms.txt`;
- English and translated landing pages;
- CI matrices, tool targets, test matrices, skip conditions, and comments that
  promise coverage of the oldest or newest supported version;
- version overview tables, EOL status, quick links, recommendations, and other
  text that claims which versions this project currently supports.

Retain a match when it is a historical or feature boundary that remains true,
including:

- "added in Python 3.x", "removed in Python 3.x", or a PEP's release;
- an algorithm or behavior that changed at a named version;
- historical version guides and factual compatibility notes;
- ordinary numeric example data such as the float `3.14`.

The search is an investigation list, not an edit list. Explain any ambiguous
match by what it means, not merely by whether it contains the old number.

## Reconcile Documentation When Dropping a Version

Do not remove documentation pages for the dropped version or for modules that
the dropped version contained. Version guides remain useful historical docs.

Re-evaluate version-gated statements in builtin and module pages. If the dropped
line was the only supported version with old behavior or without a feature,
update current tables, examples, recommendations, and tests to describe the new
supported range. Keep concise historical notes when they explain when a feature
was added or removed; do not preserve obsolete branches as though users still
need to target them.

Examples of changes to investigate:

- a table with separate behavior for the dropped minimum and all newer lines;
- a workaround needed only before a feature available throughout the new range;
- a module or API removed in one of the still-supported versions;
- a test whose skip or expected result existed only for the dropped line.

## Document a Newly Supported Version

Read the final release's official "What's New", deprecated/removed modules, and
library changes. Build an inventory of changes that affect this repository:

- new builtins, standard-library modules, classes, methods, and operations;
- removed APIs or modules;
- changed behavior, laziness, allocation, caching, or complexity;
- performance changes only when they alter an asymptotic bound or a practical
  recommendation, not merely a measured constant factor.

For each relevant item:

1. Update the owning builtin or module page and its claim tests.
2. Add a missing module page only when the new final release introduces a
   relevant module; load `documenting-complexity-modules` for that work.
3. Load `testing-complexity-claims` for every added or changed complexity or
   behavioral claim.
4. Add `docs/versions/py3xx.md` for the new final release and integrate it into
   `docs/versions/index.md`, `mkdocs.yml`, and `docs/llms.txt`.
5. Update support-range landing-page text in every existing locale. Missing
   translations of a new page may continue to fall back to English.

Do not turn "What's New" into a generic release summary. Include only changes
that help readers understand operation cost, availability, or the choice
between APIs, and verify each claim against the released interpreter and source.

## Preserve Translation and Audit Integrity

English is the source of truth. For every edited English page with an existing
translation:

1. Faithfully mirror the content change in each translation.
2. Keep fenced code byte-for-byte identical to English.
3. Preserve heading levels, table shape, and link targets.
4. Update hashes only after content matches:

   ```bash
   uv run python scripts/validate_translations.py --update-hashes <locale>
   ```

Never hand-edit `source_sha`. If a faithful translation cannot be made, leave it
explicitly stale rather than certifying incorrect content.

When adding documentation pages, run `make audit` (or
`python scripts/audit_documentation.py`) and reconcile
`DOCUMENTATION_STATUS.md` with `data/documentation_audit.json` as required by
the repository workflow.

## Verify Both Support Boundaries

Install and test the exact oldest and newest patch releases selected for CI.
Keep temporary environments outside the worktree and run sequentially so timing
tests do not compete for CPU:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/python-oldest uv run --python <oldest-patch> --frozen \
  pytest -m 'not timing'
UV_PROJECT_ENVIRONMENT=/tmp/python-oldest uv run --python <oldest-patch> --frozen \
  pytest -m timing
UV_PROJECT_ENVIRONMENT=/tmp/python-newest uv run --python <newest-patch> --frozen \
  pytest -m 'not timing'
UV_PROJECT_ENVIRONMENT=/tmp/python-newest uv run --python <newest-patch> --frozen \
  pytest -m timing
```

Run edited documentation code blocks on both boundaries when availability or
behavior differs by version. Confirm version-specific tests execute rather than
silently skip on the boundary they are meant to cover.

Finish with `make check`. Then inspect the final diff and repeat the version
searches to confirm that:

- metadata, lockfile, CI, tests, site text, and navigation agree;
- no current support statement still names the old range;
- no historical fact or documentation page was removed merely because a
  version reached EOL;
- new-version documentation is evidence-backed and scoped to relevant changes;
- translated pages are current or honestly marked stale; and
- no temporary environments or generated files remain in the worktree.
