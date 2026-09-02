---
name: testing-complexity-claims
description: Designs and reviews tests for every complexity, behavioral, and performance claim in documentation. Use when adding or changing claims, auditing claim coverage, or creating module complexity tests.
---

# Testing Complexity Claims

Turn each documentation claim into executable evidence when execution can
settle it, and explicitly account for the claims it cannot settle.

## Choose a Durable Level of Abstraction

Concentrate reviews and tests on Big-O characteristics that matter to a
reader's choice: the growth class, its size variables, meaningful best/average/
worst distinctions, output size, callback cost, and bounded versus unbounded
behavior. A finding should normally change one of those conclusions.

Do not turn constant factors, benchmark ratios, incidental CPython steps, rare
custom-protocol behavior, or minor wording in test comments into review
findings unless they make the documented complexity materially misleading.
Respect explicitly scoped bounds such as "after first access", "cache hit",
"auxiliary space", or "excluding callback cost". Do not flag omitted
out-of-scope work unless the page presents the bound as total or the omission
materially changes a reader's decision.
Use CPython source to establish the durable bound, not to reproduce a release's
implementation in prose or tests. When caller-defined work can dominate, name
it once as a variable such as callback cost or key cost rather than cataloguing
pathological implementations.

Inventories remain exhaustive so false claims are not silently blessed, but
report and fix them at the highest useful level. Prefer one stable growth-class
test over several microbenchmarks that pin mechanisms or constants likely to
change between releases.

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

## Corrections Are New Claims

A fix does not only remove a wrong claim, it writes a replacement — and that
replacement arrives with none of the scrutiny the original just received.
Inventory and classify it before publishing it, exactly as you did the text it
replaces. Over a sustained review cycle most surviving defects are found in
prose written by earlier fixes rather than in the original page.

The measurement that motivated the fix usually covers one sentence. The
explanation written around it goes in untested, and that is where corrections
go wrong:

- naming a mechanism the measurement did not observe ("sorts the input for a
  deterministic order", where the sorted path was measured and the fallback is
  not ordered at all);
- asserting a lifetime or invariant in passing ("the cached entry lives as long
  as its key does", where an unrelated call clears the cache);
- restating a bound for a path that was not measured, such as an
  immediate-failure cost presented as the cost of every failure;
- naming one end of a range as though it were the whole, such as a worst case
  with no best case, or the reverse.

Apply one rule to every sentence of a correction: if it claims something about
cost, ordering, lifetime, allocation, or call counts, and no test distinguishes
it from its negation, either test it or cut it. Prefer cutting to hedging, and a
shorter true row to a longer one carrying a fresh untested clause.

When a correction rests on a single measured input, record in the test docstring
which dimensions were *not* varied — element cost, operand width, input order,
arity, callback cost. A named untested axis can be checked later; an implied one
reads as covered.

## Keep Measurements in the Test

Settling a claim generates prose: the ratio you just measured, the code path you
just read, a caveat about the one input shape you used. Almost none of it
belongs on the page. The page carries the Big-O characteristic and the size
variables it is expressed in; the numbers, the mechanism and the untested axes
go in the test and its docstring, where they can be re-run and where the next
CPython release fails them loudly instead of leaving a stale sentence behind.

So "either test it or cut it" has a third outcome, and it is often the right
one: keep the test, drop the sentence. A fact that needed a stopwatch to settle
is usually a fact the page should state qualitatively — which side wins and
why, not by how much — or not at all. Trimming a claim discharges it; a claim
that is gone needs no test, and the inventory shrinks with the page.

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
8. Include measured values in assertion failures so regressions are
   diagnosable. Those values stay in the test; never quote them on the page.

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
