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

## Recall Evaluation

`make skills-recall` measures how often an agent states the right time and space
bound for single operations, with the skill and without it. It runs
`scripts/skill_eval.py`, which builds the plugin under `build/skill-eval/`,
writes one `claude plugin eval` case per item, and runs every case in two arms:
with the plugin loaded and without it. Each run starts in an empty directory with
no `CLAUDE.md`, memory, personal settings or other plugins, and reads outside it
are denied, so the arm without the skill answers from the model alone. Both arms
receive the same prompt, which asks for the skill by name; the arm without it
reports that the skill is unavailable and answers anyway.

The model runs on your own credential. At `RUNS=3` the full set is 600 agent
runs plus three judge calls per bound per run; `PILOT=1` runs the 20 pilot items.

### Items

[evals/items.yaml](evals/items.yaml) holds 100 operations in two strata:

- **common** (61): taken in order from [evals/usage.json](evals/usage.json), a count
  of builtin and standard-library calls in the 100 most-downloaded PyPI packages,
  produced by `scripts/scan_pypi_usage.py`. That file pins each package's file and
  SHA-256; `--pin skills/evals/usage.json` rescans exactly those files.
- **tail** (39): operations whose bound carries a qualifier the reference documents,
  such as `x in range(n)` for a float, `getattr` with a name built at run time, or
  `dict(cm)` on a `ChainMap`.

Each item fixes the size variables, the case (worst, average or amortized), CPython
3.14, and what space counts: memory the operation allocates, including a returned
object, but not its inputs. The prompt also states a cost model: hashing, comparing,
truth-testing one object, calling a key function or predicate and taking one item
from an input iterator are O(1);
hash tables see the expected number of collisions; dicts and sets were built
without deletions; ints fit in a machine word unless the operation says otherwise.
The answer key comes from the bundled page and quotes the table row it rests on; `tests/test_skill_eval.py` fails when that row leaves
the page. Where a key is derived from a row rather than copied - a variable fixed,
a condition imposed - the item's operation states the condition.

### Grading

The reply must end with `TIME: O(...)` and `SPACE: O(...)`. A bound passes when
its line holds a single bound, with nothing but qualifying words around it, that
normalises to the key or one of the item's `accept` spellings; any other line,
including one offering several bounds or doing arithmetic on one, is
decided by an LLM judge (`--judge-model`, Sonnet by default) that votes three
times against the key. `summary.md` lists every bound the judge accepted that is
not a listed spelling, and every exact match it rejected, for review. Add an
accepted spelling to the item once one is confirmed equivalent, treating every size
variable as at least 1. The questions do not state that convention; it is the usual
reading of a bound, and stating it would change the question digest that makes
runs comparable. A run counts
toward `both` only when its time and space bounds both pass.

### Results

Each run writes `skills/evals/results/<UTC start>-<model>/`:

- `meta.json`: the model alias and the model IDs the runs reported, judge, Claude
  Code version, skill version, and digests of the skill's files, the prompt
  template, the rendered questions and the judge criteria, so two runs can be
  checked for measuring the same thing
- `runs.jsonl`: every run's final reply, extracted bounds, judge verdicts with a
  digest of the criteria each was given, tool calls, denied tool calls and cost
- `summary.md`: accuracy per stratum and bound in each arm, the per-item
  difference with a bootstrap 95% interval over items, an exact McNemar test on
  items whose majority verdict changed, the full item table, and the items that
  scored worse with the skill

`uv run python scripts/skill_eval.py report <results dir>` rewrites `summary.md`
from `runs.jsonl` against the current answer keys, extracting each bound from the
stored reply again. A corrected key re-scores an earlier run's exact matches; a judge verdict given under different criteria is
discarded rather than re-run, and `summary.md` names the items affected.

Two runs are comparable when their question and criteria digests, judge, model IDs
and skill digest all agree except the one being compared: the model IDs when
comparing models, the skill digest when comparing skill releases. The
evaluation measures recall of single operations; it does not measure analysis of
whole programs, which the prompts above cover.

Before changing an answer key because an arm disagreed with it, check the bound
against the CPython source for the version asked about. A disagreement can be a
defect in the page.
