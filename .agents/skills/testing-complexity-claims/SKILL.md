---
name: testing-complexity-claims
description: Designs and reviews tests for every complexity, behavioral, and performance claim in documentation. Use when adding or changing claims, auditing claim coverage, or creating module complexity tests.
---

# Testing Complexity Claims

Turn each documentation claim into executable evidence when execution can
settle it, and explicitly account for the claims it cannot settle.

## Inventory Before Testing

Read the page and list all claims, not only Big-O notation:

- every Time, Space, and Notes table cell;
- complexity annotations in code blocks;
- prose about operation counts, copying, caching, laziness, allocation,
  short-circuiting, implementation, or relative cost;
- version-specific behavior and API contracts;
- performance recommendations and comparisons;
- stated example output or exceptions.

Map every inventory item to one test or to an explicit untestable rationale.
Test names and docstrings are labels, not evidence: confirm each assertion
actually distinguishes the documented behavior from a plausible wrong one.

## Classify Each Claim

### A. Explanatory claim beyond the table

Write a focused test. Prefer direct observation:

- count `__eq__`, callback, comparison, iterator, filesystem, or protocol calls;
- assert identity, mutation, allocation, laziness, cache reuse, output size, or
  exception behavior;
- substitute a counting or recording object at the operation boundary;
- compare state before and after the operation.

Place broadly shared prose-claim tests in `tests/test_builtin_claims.py` or
`tests/test_stdlib_claims.py`, organized by page/module. If the module already
has a cohesive test file, keep its claims there.

### B. Restatement of the page's table

Cover it in `tests/test_<module>_complexity.py`. Test all meaningful terms and
cases in the row—not merely the happy path. For `O(k + B)`, vary `k` while
holding `B` stable and vary `B` while holding `k` stable when practical. Check
space claims with identity, mutation, output size, or allocation measurement as
appropriate.

### C. Claim execution cannot settle

Record the page and reason in the relevant test file's module docstring. Typical
examples include network round trips without a real peer, backend-dependent
costs, removed modules, and definitional or source-only facts. Cite released
CPython source or official docs in the documentation where appropriate.

Do not disguise category C as a skipped test, and never mark a wrong translation
or unverified claim current merely to make checks pass.

## Use Timing Only When Necessary

If direct observation cannot distinguish the growth class:

1. Measure before choosing sizes or thresholds.
2. Compare at least two input sizes and assert a ratio that separates the
   claimed shape from the excluded shape; avoid absolute nanosecond limits.
3. Choose inputs large enough that setup, timer resolution, and fixed overhead
   do not dominate. Move setup outside the timed operation.
4. Use repeated runs and the fastest sample where that matches local tests.
5. Pick the framing with the widest empirical gap, not the smallest example
   that happens to pass.
6. Mark the test `@pytest.mark.timing`.
7. Run it under the oldest and newest supported Python versions when the claim
   can differ by implementation version. Prefer one robust invariant over
   version branching when possible.
8. Include measured values in assertion failures so regressions are diagnosable.

Avoid microbenchmarks when a call counter, identity check, or state observation
can prove the same fact without tolerance.

## Validate Examples and Test Strength

- Execute every Python fenced block on an edited page. A generic extractor may
  compile each block with a filename containing the Markdown line number, then
  execute it in a fresh namespace. Account explicitly for examples requiring
  optional third-party packages or external services.
- Assert that the page contains the expected number of examples so an extractor
  cannot silently test nothing.
- Verify displayed output and claimed exceptions where they matter; successful
  execution alone does not validate comments.
- When using source substitution, monkeypatching, or text mutation, first assert
  the substitution matched and changed the target. A mutation that never
  applied proves nothing.
- Exercise representative input shapes. Ordered, random, duplicate-heavy,
  adversarial, shallow, and deep inputs can expose different paths.
- Keep tests deterministic and restore global state, caches, warning filters,
  import paths, decimal contexts, and garbage-collector state.

## Review Against Sources

Use a released CPython branch matching the documented version, never `main`.
Trace the operation actually reached by the test, including eager setup,
fallbacks, caches, callbacks, and output construction. Source review informs the
test but does not replace runnable evidence for claims execution can settle.

## Finish

Run the focused module and claim tests while iterating, then:

```bash
make check
```

Before declaring coverage complete, reconcile the claim inventory against the
final page line by line. Report any category C claims and their source evidence;
do not say "all claims tested" when some are only sourced or remain uncertain.
