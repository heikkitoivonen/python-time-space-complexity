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
