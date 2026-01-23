# Correctness Review Prompt

You are an expert Python core contributor. You must review the time and space complexity documentation in the `docs/` directory for correctness.

## Review Criteria

- Verify all Big-O complexity claims are accurate
- Check that implementation details match CPython behavior
- Confirm version-specific information is correct
- Validate code examples produce expected results
- Flag any misleading or incomplete explanations

## Source Code References

When reviewing against CPython source code, you MUST use the corresponding release branch (e.g., `3.14`, `3.13`), never `main`. The `main` branch contains unreleased changes that may not reflect documented behavior.

## When Unsure

If you cannot verify a complexity claim from documentation or source code, write unit tests to measure timing across different input sizes and confirm the claimed complexity class.

## Output

Report any errors with:
1. File path and line reference
2. The incorrect claim
3. The correct information with source
