---
name: evaluating-skill-recall
description: Writes, runs and adjudicates the python-complexity skill's recall evaluation (skills/evals/, scripts/skill_eval.py). Use when adding or changing evaluation items, rerunning after a skill release or for another model, or deciding whether a model or the answer key is right where they disagree.
---

# Evaluating Skill Recall

`make skills-recall` asks 100 single-operation questions with and without the
skill and scores the stated bounds. [skills/evaluations.md](../../../skills/evaluations.md)
describes the method and the result files; read it first. This skill covers the
judgement the scripts cannot make: what makes an item answerable, and who is
wrong when a model and a key disagree.

## Write an Item

An item is only as good as its wording. A key that is right for the page's row
can still be wrong for the question as asked, and a capable model will answer
the question as asked.

- **Name every size variable the bound may use.** `lst[i:j]` needs i and j listed
  as variables (`i = the slice start; j = the slice stop`), or models bound it by
  n. Leave out variables the key does not use: `dq[i]` asked at the costliest
  index has only n.
- **State the condition that makes the key tight.** `s.rfind(sub)` reaches
  Θ(n·m) only while Θ(n) start positions remain, which fails at m = n, so the
  item requires `len(sub) <= len(s) / 2`; `heapq.merge` needs r >= 2 inputs for
  O(r + m log r); `x in range(n)` takes its O(1) arithmetic path only for an
  exact `int` or `bool`, and searches for anything else.
- **Match the case to what can happen.** An insertion that can resize the list
  allocates O(n) in the worst case, so ask for the amortized bound.
- **Give callbacks a cost and a result size.** The prompt's cost model makes a key
  function or predicate O(1); an item whose subject is a callback, such as
  `functools.reduce(operator.add, strs)`, says what it does. A key function that
  returns large objects changes `sorted()`'s space.
- **Keep the question free of the key.** The prompt shows the operation,
  variables and case. The key and the accepted spellings go only to the judge,
  and the quoted row to neither.
- **Quote the row.** `source.row` must be text from the page, specific enough to
  include the bound; `tests/test_skill_eval.py` fails when it leaves the page.
  A row prefix with no complexity cells pins nothing.
- **Check a derived key against CPython**, in `/cpython` at the version the
  prompt asks about (`PYTHON` in the script), not only against the page. A
  page bound can be incomplete for one version: with the digit limit disabled,
  `int(str)` on 3.14 switches to a `decimal`-based algorithm above 2,000,000
  digits that the int page does not describe.
- **List only equivalent spellings in `accept`**, equivalent under the item's own
  conditions with every size variable at least 1. A difference of variables is
  not covered: the slice items allow i == j, where O(j - i) is not tight, so a
  reworded slice item should require i < j. `O(n + m)` is not `O(n)` for a
  search unless the item bounds m by n.

Run `uv run pytest tests/test_skill_eval.py` after editing `items.yaml`. A
common item needs a `usage` name present in `skills/evals/usage.json`; the test
pins the item count, so update it when the set grows on purpose.

## Run It

```bash
make skills-recall MODEL=sonnet RUNS=3   # all 100 items: 600 agent runs
make skills-recall MODEL=haiku PILOT=1   # the 20 items marked `pilot: true`
```

A full Sonnet 5.5 run with `--concurrency 6` (the script's default is 4) cost
$52 and took 33 minutes; Haiku 5.5 cost $32.

- Try a new or reworded item with
  `uv run python scripts/skill_eval.py run --case '<id>' --runs 1` before a full
  run; `PILOT=1` covers only the items already marked as pilots.
- Do not run `make check` at the same time: its timing tests flake under the
  load.
- Stop a run by the PIDs of `claude plugin eval` and `skill_eval.py` from `ps`.
  `pkill -f` with a pattern that also appears in the shell's own command line
  kills that shell.
- A stopped run leaves read-only directories under `/tmp/claude-eval-*`;
  `chmod -R u+rwx` them before deleting, and delete the partial results
  directory.

## Adjudicate the Results

Read every section of the run's `summary.md` below the summary table.

- **A model disagrees with the key.** Settle it from the CPython source before
  deciding. If the model is right, the cause is one of three: the item's
  wording admits its answer (narrow the item for the next run, and add the
  spelling to `accept` if it is equivalent); the key was derived wrongly from a
  correct page (correct the key); or the page is wrong (report the page defect;
  the key follows the corrected page). If the key is right, the miss stands.
- **Judge rulings to review.** A judge pass on a spelling outside `accept` is
  added to `accept` once it is confirmed equivalent. A judge fail on an exact
  match is already scored as a pass; the judge rejects a small share of exact
  matches.
- **Worse with the skill.** Read the reply and its `tool_calls`. A regression
  where the skill's page carries a caveat outside the item's conditions is a
  real result, not a key defect.
- After changing keys or `accept`, run
  `uv run python scripts/skill_eval.py report <results dir>` for every stored
  run. It rewrites `summary.md` without calling a model and discards judge
  verdicts given under criteria that have since changed, so on those bounds
  only listed spellings pass: check the affected items' answers for equivalent
  spellings still missing from `accept`. `meta.json` keeps the digests the run
  started with.

## Keep Runs Comparable

A change to `PROMPT`, `PYTHON` or the rendered question of any item a run
selects changes that run's `questions_sha256`, and a run under the old
questions can no longer be compared with a new one. Batch such changes, then
rerun every model you compare. A change to keys or `accept` only needs `report`.

Commit each run's results directory with the change that produced it. Its
`meta.json` records the model IDs, judge, skill digest and question and
criteria digests. Two runs are comparable when everything except the one
thing being compared agrees: the model when comparing models, the skill digest
when comparing skill releases.
