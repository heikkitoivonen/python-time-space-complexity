---
name: python-complexity
description: Look up and apply Python builtin and standard-library time and space complexity when analyzing code, reviewing performance, or comparing operations. Includes implementation and version qualifications. Use for complexity analysis, not general Python syntax questions.
license: MIT
---

# Python Complexity

Use the bundled reference to analyze the user's Python code or operation. It is
a snapshot of the Python Complexity project, with its version, supported Python
range, source revision, and file hashes recorded in [manifest.json](manifest.json).
References are readable offline; no runtime or package installation is required.

## Find the relevant reference

Start with [the reference index](references/INDEX.md). It groups pages by builtin,
standard-library module, implementation, and Python version. Follow only the
links relevant to the question. Search within those pages for the actual method
or operation; read its table notes and the surrounding qualifications.

Use the detailed operation page rather than relying on a summary index. For a
version-dependent question, also read the relevant version page and the module's
version notes. Do not load the entire reference into context.

## Apply the evidence

- Identify the concrete types and input-size variables. Use the user's Python
  version and implementation when supplied; otherwise state any assumption that
  affects the answer. Do not transfer CPython-specific bounds to other runtimes.
- Preserve distinctions between average, amortized, and worst-case bounds. State
  what each space bound counts: auxiliary memory, returned storage, or retained
  input. If the page leaves that ambiguous, say so instead of guessing.
- Account for the complete code path: setup, repeated operations, iterator
  consumption, materialization, and the lifetime of intermediate results. Do not
  apply an iterator-creation bound to its full consumption.
- Identify user-supplied hashing, equality, comparison, key functions, or other
  callback costs when they affect the analysis. State relevant assumptions rather
  than silently treating arbitrary user code as constant cost.
- Treat the bundled pages as evidence with a defined scope, not a proof for every
  input or release. If a page is missing, contradictory, or does not cover the
  requested version, explain the gap. When source access is available and needed,
  verify against official documentation or the matching released implementation.
  Do not claim to have checked sources or run benchmarks unless you did so.
- Use asymptotic bounds to explain scaling. Do not promise a measured speedup
  from Big-O alone. Recommend a different operation only when its semantics fit
  the user's needs; preserve the user's requested scope.

## Present the result

Give time and space complexity, define the size variables, and state the
assumptions that affect the conclusion. For code, connect the individual
operations to the total bound. Cite the relevant bundled page; its canonical
website URL is also listed in its topic catalog. Distinguish the page's claim
from your derived analysis and any unresolved uncertainty.
