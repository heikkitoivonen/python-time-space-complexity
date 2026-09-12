# Python Complexity Skill Evaluation

Run `make skills-eval` to build `build/skills/python-complexity/` and display
these instructions. This target prepares a manual behavioral evaluation; it
does not invoke an agent or report automated behavioral success.

Install the built skill into the agent being evaluated and start a fresh session
outside this repository. Supply only one prompt at a time, without the rubric.
Keep network access off for the first four prompts. Record the agent and model
version, skill manifest, prompt, response, referenced files, and pass/fail reasons.
Package integrity and document fidelity are tested separately by `make check`.

## Prompts

1. "Use python-complexity to analyze `def contains(items, queries): return
   [q in set(items) for q in queries]`. Assume lists of ordinary integers on
   CPython 3.14. Give time and peak space bounds with variables, and suggest an
   improvement if repeated queries justify it."
2. "Use python-complexity to compare creating `itertools.product(a, b)` with
   consuming it into a list. The inputs are lists of lengths m and n. Explain
   what memory each stage retains and cite the reference."
3. "Use python-complexity to compare bisect search and insort on a Python list.
   My key function has cost K. Explain which work determines the total cost."
4. "Use python-complexity to explain whether graphlib.TopologicalSorter.prepare
   can be called twice before sorting starts on Python 3.13 and 3.14. Cite the
   version-specific evidence rather than extrapolating from one release."
5. "Use python-complexity to give a verified worst-case bound for an operation
   implemented by a third-party extension I have not provided."
6. "How do I write a Python function with a default argument?"

## Rubric

For prompts 1–4, check the answer against the detailed bundled operation pages.
Require a relevant source, explicit size variables and cost assumptions, and
separate time and space accounting. The answer should connect its derived bound
to the concrete code, preserve version boundaries, and distinguish setup from
consumption. It must read only the relevant references and must not claim that
it ran benchmarks or consulted external sources when it did not.

Prompt 1 should account for rebuilding the set inside the loop, the empty-query
case, and the lifetime of temporary sets versus the returned list. Prompt 2
should inspect the iterator's retained input pools as well as returned storage.
Prompt 3 should distinguish locating an insertion position from performing the
insertion. Prompt 4 must establish the boundary from the module documentation.

Prompt 5 should explain what evidence is missing without inventing a bound or
claiming that the builtin/stdlib reference covers arbitrary extensions. Prompt 6
should receive a normal syntax answer without loading this complexity reference.

Do not count successful package tests as behavioral evaluation. Investigate
contradictions in source documentation separately; packaging does not certify
every source claim. Re-run affected prompts after changing skill instructions
or reference routing, and check installation in each advertised agent before
claiming end-to-end agent compatibility.
