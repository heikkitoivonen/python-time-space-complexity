---
name: documenting-complexity-modules
description: Authors or expands Python builtin and standard-library complexity pages, including API coverage, navigation, examples, translations, audit metadata, and verification. Use when adding a module/type page or materially expanding one.
---

# Documenting Complexity Modules

Produce a complete, evidence-backed page rather than filling a prose template.
Treat English documentation as the source of truth and complexity claims as
the repository's highest-risk content.

## Establish Scope and Evidence

1. Read `AGENTS.md`, `CONTRIBUTING.md`, and representative nearby pages and
   tests. Prefer recent page/test pairs such as:
   - `docs/stdlib/graphlib.md` and `tests/test_graphlib_complexity.py`
   - `docs/stdlib/struct.md` and `tests/test_struct_complexity.py`
2. Identify every public class, function, constant, and public method the page
   should cover. Use official Python documentation plus runtime inspection such
   as `dir(module)` and `dir(class)`. Filter private names, then distinguish
   callables from data attributes. Record intentional omissions in the page or
   test rationale; do not silently omit APIs.
3. Define every size variable before using it. Avoid an ambiguous `n` when an
   operation depends on several dimensions; use terms such as input length,
   output length, fields, vertices, edges, matches, or returned items.
4. Verify implementation-specific claims against the corresponding released
   CPython branch, never `main`. Check every Python version the project supports.
   Use official documentation where behavior is contractual and source where
   implementation determines the bound.

Do not trust an existing claim, a plausible review comment, or a generic
complexity rule without checking the operation's actual code path.

## Write the Page

Follow the local style of adjacent pages:

1. Title: `# <name> Module Complexity` or the established builtin equivalent.
2. Give a short performance-focused introduction.
3. Put `## Complexity Reference` first and include a table with exactly these
   semantic columns:

   ```markdown
   | Operation | Time | Space | Notes |
   |-----------|------|-------|-------|
   ```

4. Cover all scoped operations. Distinguish best, average, amortized, and worst
   cases; state eager versus lazy work, cache effects, output-sensitive terms,
   and version boundaries where they affect the result.
5. Add concise sections that explain non-obvious costs and practical performance
   choices. Exclude generic usage advice unrelated to complexity.
6. Include runnable examples that demonstrate the documented operation or a
   performance consequence. Annotate relevant operations with their complexity.
   Avoid huge allocations or slow benchmark-style examples in docs.
7. Link related operations when the comparison helps readers choose between
   different costs.

Every table row, annotation, caption, example comment, explanatory sentence,
warning, and recommendation that describes cost or behavior is a claim. Make a
claim inventory while writing; do not review only text containing `O(...)`.

## Test Every Claim

Use the `testing-complexity-claims` skill if available. Otherwise apply its core
contract directly:

- A module-specific `tests/test_<module>_complexity.py` covers the page's table.
- Explanatory claims beyond the table receive focused tests, preferably based on
  observable behavior rather than elapsed time.
- Claims that execution cannot settle are listed with the reason in a relevant
  test module's docstring; do not add a fake or permanently skipped test.
- Test or explicitly account for every fenced code block using the code-section
  rules below.
- Maintain a one-to-one claim inventory showing a test or an explicit
  untestable rationale for each claim.

Do not write documentation first and defer its evidence to later work.

## Test Every Code Section

Account for every fenced code block in the English page, not just blocks that
contain complexity annotations. Test each block when safely and meaningfully
possible; for a block that cannot be executed, record the block's location and
the concrete reason, such as required network access, interactive input,
deliberately incomplete names, destructive behavior, or an intentional
exception without an established marker. Translations do not need duplicate
execution because their code fences must be byte-for-byte identical to English.

Follow the isolation lessons from repository issue #7 when building or extending
a documentation-code runner:

- dedent each extracted block so fences nested in admonitions compile correctly;
- run each block independently in a subprocess with a hard timeout, a fresh
  namespace, closed stdin, and a temporary working directory;
- do not rely on text matching for unsafe or interactive calls: `breakpoint()`,
  `help()`, `pdb.set_trace()`, `sys.stdin.read()`, and `getpass.getpass()` are
  pitfalls alongside obvious `input()` calls;
- isolate or explicitly exclude process, thread, network, browser, system,
  signal, destructive filesystem, and indefinitely blocking examples;
- support intentional exceptions through an explicit convention rather than
  treating all raised exceptions as broken examples;
- report every failure with its Markdown file and fence line number, and restore
  captured output before emitting diagnostics;
- assert the expected block count or accounted-for locations so extraction
  cannot silently test nothing;
- mutation-test the runner with a known broken example and first assert that the
  mutation actually changed its target.

Execution proves only that a block does not crash; it does not prove that the
block demonstrates what its prose, comments, or output claims. Add semantic
assertions for results, exceptions, state changes, operation counts, and
complexity behavior wherever those claims can be tested. Retain claim-specific
unit tests even when a generic code-block runner also executes the example.

## Integrate the Page

1. Add the English page to the appropriate alphabetized navigation section in
   `mkdocs.yml`.
2. Run `python scripts/audit_documentation.py` (or `make audit`) to regenerate
   `data/documentation_audit.json`. Then update `DOCUMENTATION_STATUS.md` from
   that report: adjust totals and percentages and move the module from missing
   to documented. Confirm all values agree with the generated JSON.
3. Look for existing translations at the equivalent `docs/<locale>/...` path.
   If they exist, faithfully mirror the English change and run:

   ```bash
   uv run python scripts/validate_translations.py --update-hashes <locale>
   ```

   Never hand-edit `source_sha`. Keep fenced code byte-for-byte identical to
   English, and preserve heading levels, table shape, links, and complexity
   notation. Missing translations may continue to fall back to English.

## Verify

Run the narrowest useful checks while iterating, then finish with:

```bash
make check
```

Also inspect the final diff for:

- complete public API coverage or explained omissions;
- defined size variables and qualified bounds;
- every claim mapped to evidence;
- every fenced code section tested or explicitly accounted for, with semantic
  assertions where execution alone is insufficient;
- alphabetized navigation and correct audit changes;
- translations updated where an equivalent page exists;
- no unrelated formatting or content changes.

If a claim remains unverified, describe the missing evidence and do not present
the page as complete.
