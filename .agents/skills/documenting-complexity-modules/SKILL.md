---
name: documenting-complexity-modules
description: Authors, expands, or reviews Python builtin and standard-library complexity pages, including API coverage, navigation, examples, translations, audit metadata, and verification. Use when adding a module/type page, materially expanding one, or reviewing an existing one for correctness - a review covers what the page omits as well as what it claims.
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
   test rationale; do not silently omit APIs. Reconcile the result with
   the shared audit gate - see *Coverage Is a Claim* below.
3. Define every size variable before using it. Avoid an ambiguous `n` when an
   operation depends on several dimensions; use terms such as input length,
   output length, fields, vertices, edges, matches, or returned items.
4. Verify implementation-specific claims against the corresponding released
   CPython branch, never `main`. Read every Python version the project
   supports - a bound can move in a middle release - but run the pinned
   interpreter unless a claim is about a particular version, in which case run
   that one for the tests asserting it; CI covers the matrix. Use official
   documentation where behavior is contractual and source where implementation
   determines the bound.

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

4. Cover all scoped operations at the altitude set by *Document the Common
   Case* below: one bound per operation, with its size variables defined.
   Distinguish best, average, amortized and worst only where they differ
   asymptotically and ordinary use can reach the difference; state eager versus
   lazy work, cache effects, output-sensitive terms, and version boundaries
   where they change the result on a version this project supports.
5. Add concise sections only where a non-obvious cost changes a practical
   choice. Exclude generic usage advice unrelated to complexity, and prefer no
   section to one that restates the table in sentences.
6. Include runnable examples that demonstrate the documented operation or a
   performance consequence. Annotate relevant operations with their complexity.
   Avoid huge allocations or slow benchmark-style examples in docs.
7. Link related operations when the comparison helps readers choose between
   different costs.

Every table row, annotation, caption, example comment, explanatory sentence,
warning, and recommendation that describes cost or behavior is a claim. Make a
claim inventory while writing; do not review only text containing `O(...)`.

## Document the Common Case

The page exists so a reader can choose between operations. Its subject is the
Big-O characteristic that governs that choice, not a full account of the CPython
code path that produced it. A row that is correct but exhaustive costs more than
it returns: it reads worse, it goes stale sooner, and every added clause is one
more claim to test.

Keep these off the page:

- **Measured constant factors.** "roughly 1,400x dearer", "some 50x", "wins by
  eight times". A ratio is a property of one machine, one input shape and one
  release. The page cannot re-run it, the reader cannot act on it, and nothing
  fails when it drifts. Where a magnitude really does drive a choice, say which
  side wins and why, not by how much; the number stays in the test that guards
  it.
- **Pathological-input costs.** An argument whose `__hash__` scans 100,000
  elements does make hashing dominate a cache hit, but pricing that into the
  cache's row teaches nothing about the cache. Document the cost the operation
  itself controls; where caller-supplied cost dominates, name it once as a
  variable (h, f, the callback) and move on.
- **Per-release micro-changes.** A version boundary earns a mention when it
  changes the bound or the recommendation on a supported version. Shifts in
  constant factors between minor releases do not, and neither does an
  implementation detail stated so precisely that the next release falsifies it.
- **Restated mechanism.** The C function reached, the struct field consulted,
  the order of two statements: that is evidence for the test file, not content
  for the page, unless the reader must do something differently because of it.

Apply one test to every note: would removing it change how someone uses the
operation? If not, cut it. An empty Notes cell beside a correct bound is a good
outcome, not an unfinished one.

A deliberately loose bound fails that test even when it is honest about being
loose. Bounding a recursive tree walk by the whole tree's metadata is true, and
tells the reader that shape does not matter - when two trees of equal entry
count differ eightfold by shape. Give the tight bound and its size variables;
"conservative" is a bound no release can ever falsify, which is the same as one
no reader can use.

## Coverage Is a Claim

Use the shared public API audit as the completeness gate for the page being
written or reviewed. Run it before the claim review and again on the final page:

```bash
uv run python scripts/audit_documentation.py --page docs/stdlib/os.md --check --include-review
```

Replace the path with the actual English page. Scope by page, including submodule
APIs assigned to it (such as `os.path` in `os.md`), rather than filtering output
by a module-name prefix. The audit uses the current interpreter's versioned
Python API inventory and deduplicates aliases across the full audit. Use that
shared inventory instead of writing another `dir(module)` completeness test.
Runtime inspection and official documentation still supplement inventory gaps.

Resolve every reported miss with substantive documentation or correct an audit
classification/matching defect with a regression test. Group related APIs when
they share a bound. Do not add token mentions to obtain a pass, silently suppress
names, or treat an inspection failure or empty inventory as zero misses.

The gate checks name coverage, not complexity correctness. Review the scoped
unresolved/unavailable and unclassified diagnostics too; record explicit names
and reasons for intentional exclusions or platform/version limitations in the
module test rationale. A successful exit does not discharge those diagnostics.
Inspect the official inventory for relevant supported-version APIs absent from
the running interpreter; run another version only when resolving a claim about
that version. One platform's successful audit does not establish all-platform
coverage.

A full review is complete only when the scoped gate passes, every remaining
coverage diagnostic is accounted for, and every documented claim has evidence.
Report API completeness and claim correctness separately. If the work is an
explicitly scoped correction, report remaining API gaps rather than describing
the whole page as reviewed. Newly documented APIs need the same claim inventory,
behavioral tests, and example verification as the existing rows.

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
2. Run `make audit` to print live coverage without writing files. Coverage tests
   compare the current interpreter with the English documentation tree; CI also
   checks the pinned newest supported Python patch. Preserve navigation targets
   for historical modules even when the current interpreter no longer has them.
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

- a passing scoped public API audit and explicit accounting for remaining
  coverage diagnostics;
- defined size variables and bounds qualified only where the qualification
  changes a decision;
- notes that survive the removal test, carrying no measured constants,
  pathological-input pricing, or restated mechanism;
- every claim mapped to evidence;
- every fenced code section tested or explicitly accounted for, with semantic
  assertions where execution alone is insufficient;
- alphabetized navigation and passing live coverage checks;
- translations updated where an equivalent page exists;
- no unrelated formatting or content changes.

If a claim remains unverified, describe the missing evidence and do not present
the page as complete.
