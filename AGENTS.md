# AI Agent Guidelines

This file contains instructions for AI agents (like Amp, Claude, etc.) working on this repository.

## Core Rules

### Pre-Commit Verification (MANDATORY)

**Before creating ANY git commit, you MUST:**

1. Run `make check` (lint + types + tests)
   ```bash
   make check
   ```
   - All ruff linting must pass
   - All pyright type checks must pass (0 errors)
   - All pytest tests must pass (no failures; the suite grows over time, so
     check for zero failures rather than a fixed count)

2. Verify output shows:
   ```
   All checks passed!
   0 errors, 0 warnings, 0 informations
   ====== N passed ======
   ```

3. Do NOT commit if checks fail

### Example Pre-Commit Workflow

```bash
# Make changes
# ...

# Run quality checks
make lint      # Verify: All checks passed!
make format    # Fix any formatting issues
make test      # Verify: no failures

# Only then commit
git add .
git commit -m "Your message"
```

## Standard Commands

### Development
- `make dev` - Install with dev dependencies
- `make serve` - Start local server (http://localhost:8000)
- `make build` - Build static site

### Quality Assurance
- `make lint` - Check code quality (must pass before commit)
- `make format` - Format code automatically
- `make types` - Run pyright type checker (must pass before commit)
- `make check` - Run lint + types + tests (must pass before commit)
- `make test` - Run pytest (must pass before commit)

### Maintenance
- `make clean` - Remove build artifacts
- `make update` - Update dependencies
- `make help` - Show all available commands

## Project Structure

### Key Directories
- `/docs` - Documentation markdown files (site content, English)
- `/docs/<locale>` - Translations mirroring the English tree (e.g. `/docs/fi`)
- `/tests` - Python test files
- `/scripts` - Utility scripts (templates)
- `/data` - JSON data files for documentation

### Key Files
- `pyproject.toml` - Project config, dependencies, tool settings
- `Makefile` - Development commands
- `mkdocs.yml` - Documentation site config (incl. `i18n` plugin locales)
- `TRANSLATING.md` - Translation workflow and per-locale glossaries
- `ACCESSIBILITY.md` - WCAG 2.2 AA rules: colour tokens, `lang`, headings
- `PERFORMANCE.md` - critical path, vendored fonts, and what was left alone
- `SEO.md` - hreflang, canonical URLs, sitemaps, `robots.txt`
- `scripts/validate_translations.py` - Translation structure/staleness checker
- `.python-version` - Python 3.11 specification
- `uv.lock` - Dependency lock file (reproducible builds)

## Repository Skills

Reusable project workflows live in `.agents/skills/`. Agents with native Agent
Skills support should load the matching skill before starting this work:

- `documenting-complexity-modules` - Use when adding a builtin or standard-library
  module page, or materially expanding one.
- `testing-complexity-claims` - Use when adding or changing complexity claims,
  auditing claim coverage, or creating module complexity tests.
- `updating-python-support` - Use when dropping an EOL Python version, adding a
  newly released Python version, or changing the supported Python range.

`.agents/skills/` is the canonical source. Claude Code compatibility symlinks
live in `.claude/skills/`; edit the canonical skill rather than the symlink.

## Code Style & Standards

### Python Code
- Line length: 100 characters (enforced by ruff)
- No unused imports (enforced by ruff)
- Format with `make format` before commit
- All checks must pass: `make lint`

### Documentation (Markdown)
- Complexity tables required (Time, Space, Notes columns)
- Include code examples for operations
- Link to related operations
- Use admonitions for important notes:
  ```markdown
  !!! warning "Title"
      Content here
  ```

### Commit Messages
- Use imperative mood: "Add", "Fix", "Update", not "Added", "Fixed"
- Format: `Type: Brief description`
- Types: Add, Fix, Update, Refactor, Docs, Test, Chore
- Example: `Add: List complexity documentation`
- **Keep the message short.** Say what was corrected or added and stop. Do
  not narrate what the code or claim used to be, how the defect was found,
  what was measured on the way, or which approaches were rejected — the
  reader does not need it, and the evidence belongs in the test and its
  docstring, where it can be re-run. Prefer a line or a few bullets:
  ```
  Fix: Correct three os space bounds and add the module's tests

  - os.walk is O(w + d), not O(d): queued entries are a term of their own
  - os.makedirs is O(n): it recurses once per path component
  ```
  The same applies to pull request descriptions.
- **AI Agents MUST add Co-Authored-By trailer to identify the agent:**
  ```
  Add: List complexity documentation

  Co-Authored-By: Amp <amp@ampcode.com>
  ```
  Replace "Amp <amp@ampcode.com>" with the actual AI agent name (Claude,
  Copilot, etc.) and email.

## Testing Requirements

### Before Every Commit
1. Run `make lint` - all linting must pass
2. Run `make types` - all type checks must pass
3. Run `make test` - all tests must pass
4. Never commit broken code

### Test Files Location
- `tests/test_documentation.py` - Main test file
- Must test documentation structure, data files, project files

### Running Tests
```bash
make lint           # Run linting
make types          # Run type checks
make test           # Run all tests
make check          # Run lint + types + tests (recommended before commit)
```

## Dependency Management

### Adding Dependencies
```bash
# Add production dependency
uv add package-name

# Add dev dependency
uv add --dev package-name
```

### DO NOT
- Manually edit pyproject.toml dependency lists
- Manual requirements.txt edits (uv manages this)
- Forget to commit uv.lock after adding dependencies

## Common Workflows

### Adding Documentation
1. Create markdown file in `/docs`
2. Update navigation in `mkdocs.yml`
3. Run `make audit` to update `DOCUMENTATION_STATUS.md`
4. Run `make serve` to preview
5. Run `make check` to verify
6. Commit with message: `Add: Topic name documentation`

**CRITICAL:** Always update `DOCUMENTATION_STATUS.md` after adding new documentation files:
- Run `python scripts/audit_documentation.py` to regenerate the coverage report
- Update the coverage percentages and totals in DOCUMENTATION_STATUS.md
- Move documented items from "Missing" to "Documented" sections
- Never commit without updating this file - it tracks project coverage goals

### Editing an English Page That Has Translations

English is the source of truth. Every translated page records the SHA-256 of
the English file it was made from, so **any** edit to an English page - even a
typo fix or whitespace change - marks its translations stale and fails
`make check`.

When you edit `docs/<path>.md`, check for `docs/*/<path>.md`:

1. Make the English edit
2. Mirror the same change into each existing translation
3. Re-record the hashes: `uv run python scripts/validate_translations.py --update-hashes <locale>`
4. Run `make check`

If you cannot make a faithful translation, say so and leave the page stale
rather than guessing - a stale flag is recoverable, a wrong translation is not.

**Never hand-edit `source_sha`.** Use `--update-hashes`, and only after the
translation actually matches the new English text. Editing the hash without
updating the content silently marks a wrong translation as current.

### Translating

Full workflow, glossaries, and per-locale rules: `TRANSLATING.md`.
Contributor-facing summary: the i18n section of `CONTRIBUTING.md`.

Structural rules the validator enforces (`scripts/validate_translations.py`,
run as part of `make check`):

- Code blocks must match the English source **byte for byte** - do not
  translate comments, identifiers, or output inside fenced blocks
- Heading count and levels must match
- Table row counts must match
- Link targets must match

Also note:

- Headings are translated, which changes anchor slugs. Keep headings that are
  Python identifiers (`## deque`, `## Counter`) untranslated, or cross-page
  anchor links such as `collections.md#deque` will break.
- Translations live in `docs/<locale>/`, so the `docs/builtins/*.md` and
  `docs/stdlib/*.md` globs in `tests/` and `scripts/audit_documentation.py`
  do **not** see them. This is intentional - do not "fix" it.
- Missing pages fall back to English automatically. Partial translations are
  fine; never bulk-translate to fill gaps.

### Adding or Changing a Complexity Claim

Every page here is a complexity claim, so a wrong one is the worst defect
this repo can ship - and `make check` cannot see it. A page can be green,
lint-clean and confidently wrong.

Before writing a claim, decide which of three kinds it is.

**A. It says something the page's complexity table does not.** These are the
explanatory clauses - "costs no more than a str key", "one lookup",
"formatting is the more expensive of the two". Every wrong claim found so far
has been one of these. **Write a test.** Prefer observation over timing: a
counting `__eq__`, a counting `os.scandir`, an identity check, a call
counter. Those need no tolerance and cannot flake. Where only a stopwatch
will do, compare two input sizes and assert on the ratio, with a threshold
far from both the behaviour you are asserting and the one you are excluding.

Note that a claim of this kind is often a sentence with no `O(...)` in it at
all. About a third of the wrong ones were. Do not filter by notation.

**B. It restates a row of the page's own table.** A `# O(log n)` beside
`heappush`. Covered by the module's complexity test file - which needs to
exist. Add one if it does not, rather than a test per annotation.

**C. It cannot be settled by running code.** Network round trips, an NSS
backend, a module removed in a later Python, or a definitional choice such
as which unit a bound is expressed in. Say so in the test file's docstring,
next to the ones you did cover, and do not write a test that pretends
otherwise.

Claims are not the only thing that breaks. Two of the three pages spot-checked
so far shipped examples that raised on the first line - one of them a
`NameError` introduced while adding annotations to it. Run a page's code
blocks, not just its numbers.

Things worth knowing before you rely on a test:

- A test pins what it asserts, not what the prose says. Its *name* is not an
  assertion either: one here claimed a comparison its body never made.
- Measure before you correct. `Decimal.quantize()` cost tracks the digits the
  result keeps, not the operand's - the opposite of a plausible-sounding
  review comment that was accepted here without measuring.
- Vary the input before you generalise. `most_common(k)` was benchmarked on
  counts that rose in iteration order, the one shape that defeats the heap,
  and the docs told four languages that passing k never pays. On random or
  Zipf-like counts it wins by eight times.
- Run it on every version the project supports, not just the pinned one.
  Tests asserting that `prepare()` may be called once passed on 3.11 and
  failed on 3.14, which relaxed it.
- Pick the framing with the widest gap, not the one that mirrors the sentence
  most directly. Four timing tests here had to be widened after the fact,
  each because it compared the smallest pair that demonstrated the claim -
  two 70ns operations, a 2x size step, a 2us baseline. The same fact usually
  has a framing that produces a far bigger ratio.
- A mutation check that does not apply proves nothing. Assert the
  substitution changed the file: one here silently matched nothing after
  `ruff format` rewrapped the assertion, and "passed" as the original test.

Test files: `tests/test_<module>_complexity.py` for a module's table,
`tests/test_builtin_claims.py` and `tests/test_stdlib_claims.py` for kind A,
`tests/test_complexity_caveats.py` for claims that were wrong once already.

### Fixing Issues
1. Identify the problem
2. Make minimal changes
3. Run `make check` to verify
4. Commit with message: `Fix: Description of fix`

### Code Cleanup
1. Run `make format` (auto-fixes issues)
2. Verify no new issues with `make lint`
3. Run `make test` to ensure nothing broke
4. Commit with message: `Refactor: Description`

## What NOT to Do

### ❌ DO NOT
- Commit without running `make check`
- Commit if `make lint` fails
- Commit if `make types` fails
- Commit if `make test` fails
- Ignore test failures
- Manually edit lock files (use uv commands)
- Create unnecessary files in root directory
- Break existing tests without fixing them
- Edit an English page without updating its translations (see above)
- Hand-edit `source_sha` in a translation's front matter
- Translate anything inside a fenced code block
- Reformat English tables cosmetically - it marks every translation stale
- Change a colour without measuring its contrast (see ACCESSIBILITY.md)
- Re-add `extra_css`, hardcode the JS bundle's content hash, or drop
  `crossorigin` from a font preload (see PERFORMANCE.md)
- Emit a relative `hreflang` href, or add `x-default` to `extra.alternate`
  (see SEO.md)
- Dim text with `opacity` - it fails contrast and SC 1.4.1 both
- Skip a heading level (`##` straight to `####`)

### ✓ DO
- Always run quality checks before committing
- Keep commits focused and minimal
- Write clear commit messages
- **Add Co-Authored-By trailer for agent identification**
- Update documentation when changing functionality
- Test a complexity claim that goes beyond the page's table, before trusting it
- Test locally before pushing
- Review your changes before committing

## Emergency Procedures

### If Tests Fail
1. Check the error message carefully
2. Fix the issue locally
3. Run `make check` again
4. Verify all tests pass before committing

### If Code Quality Issues
1. Run `make format` (auto-fixes most issues)
2. Review remaining issues with `make lint`
3. Fix manually if needed
4. Verify with `make lint` again

### If Git History is Broken
- Do NOT use `--force` push
- Contact a human maintainer
- Preserve commit history

## Verification Checklist

Before every commit, verify:

- [ ] `make lint` passes (0 errors)
- [ ] `make types` passes (0 errors)
- [ ] `make test` passes (no failures)
- [ ] No uncommitted changes
- [ ] Commit message is clear
- [ ] Changes are focused/minimal
- [ ] Documentation updated if needed
- [ ] New complexity claims tested, or recorded as untestable (see above)
- [ ] Edited code blocks actually run, and new timing tests pass on the
      oldest and newest supported Python, not just the pinned one
- [ ] Translations updated if an English page changed
- [ ] Accessibility rules honoured if colours/headings/`lang` changed
- [ ] No test files left uncommitted

## Examples

### Example: Good Commit

```bash
# Edit documentation
vim docs/stdlib/itertools.md

# Verify changes
make serve  # View in browser

# Quality checks
make lint   # All checks passed!
make types  # 0 errors, 0 warnings, 0 informations
make test   # no failures

# Commit
git add .
git commit -m "Add: itertools module complexity documentation"
```

### Example: Bad Commit (DO NOT DO)

```bash
# Edit documentation
vim docs/stdlib/itertools.md

# Directly commit WITHOUT checking
git add .
git commit -m "updated docs"  # ❌ NO! Check first!
```

## Questions?

If you need guidance:
1. Check CONTRIBUTING.md for contribution guidelines
2. Check README.md for project overview
3. Check PERFORMANCE.md before changing how CSS, fonts or scripts are
   delivered
4. Check SEO.md before changing hreflang, canonical URLs or `robots.txt`
5. Check ACCESSIBILITY.md before changing any colour, heading level, or
   `lang` attribute

---

**Last Updated:** January 2026  
**Status:** Active guidelines - Follow these rules  
**Enforcement:** All commits checked automatically
