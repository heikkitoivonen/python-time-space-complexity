"""Measure how much the python-complexity skill improves complexity recall.

Each item in skills/evals/items.yaml becomes one `claude plugin eval` case. The
case runs in two arms - with the built plugin and without it - each in an
isolated session with no CLAUDE.md, memory or personal plugins. The reply's
final TIME and SPACE lines pass when they match the item's answer key or one of
its accepted spellings; any other spelling is decided by an LLM judge, and every
ruling that differs from the exact match is listed for review.

    uv run python scripts/skill_eval.py run --model sonnet --runs 3 [--pilot]
    uv run python scripts/skill_eval.py report skills/evals/results/<run>

`run` writes runs.jsonl, meta.json and summary.md to a new results directory.
"""

import argparse
import fnmatch
import hashlib
import json
import math
import random
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import build_skills  # noqa: E402

EVALS = ROOT / "skills" / "evals"
ITEMS = EVALS / "items.yaml"
SUITE = ROOT / "build" / "skill-eval"
PLUGIN = SUITE / "plugins" / build_skills.NAME
PYTHON = "3.14"
CASES = {"worst": "worst-case", "average": "average-case", "amortized": "amortized"}
# Words that may follow an extracted bound without changing it.
QUALIFIERS = {
    "amortized", "amortised", "average", "avg", "worst", "case", "expected", "time", "space",
    "auxiliary", "extra", "total", "overall", "in", "the",
}  # fmt: skip

PROMPT = """\
Use the python-complexity skill if it is available to you.

What are the time complexity and the space complexity of this operation on CPython {python}?

Operation: {operation}
Size variables: {variables}
Give the {case} bound.

Express each bound as a tight big-O bound using only the size variables above. For space, count \
the memory the operation allocates, including any new object it returns, but not its inputs.

Unless the operation says otherwise, assume:
- hashing or comparing one element, testing one object's truth, calling a key function or \
predicate, and taking one item from an input iterator each cost O(1) time and allocate O(1)
- hash tables see the expected number of collisions, so a lookup or insertion probes O(1) slots
- every dict and set was built by insertions alone, with no deletions
- every int fits in a machine word

Do not run code or search the web. Keep the explanation brief, and end your reply with exactly \
these two lines:
TIME: O(...)
SPACE: O(...)
"""

CRITERIA = """\
The reply should end with a line of the form `{label}: O(...)`. Judge only that line.

The correct {kind} bound is {key}, with these size variables: {variables}.{also}

PASS if the {label} line gives a bound asymptotically equivalent to {key} for these \
variables: the same growth as the variables become large. Notation does not matter - \
spacing, `*` or `·` for multiplication, `log(n)` or `log n`, the order of terms, or a \
qualifier such as "amortized" or "average".
FAIL if the {label} line is missing, grows faster or slower than {key}, offers several \
alternative bounds without committing to one, or uses variables other than those listed.
"""


def load_items(path: Path = ITEMS) -> list[dict[str, Any]]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def frontmatter(fields: dict[str, Any]) -> str:
    return "---\n" + yaml.safe_dump(fields, sort_keys=False) + "---\n\n"


def prompt_for(item: dict[str, Any]) -> str:
    return PROMPT.format(
        python=PYTHON,
        operation=" ".join(item["operation"].split()),
        variables=item["variables"],
        case=CASES[item["case"]],
    )


def criteria_for(item: dict[str, Any], kind: str) -> str:
    bound = item[kind]
    also = bound.get("accept", [])
    return CRITERIA.format(
        label=kind.upper(),
        kind=kind,
        key=bound["key"],
        variables=item["variables"],
        also=f" Also equivalent: {', '.join(also)}." if also else "",
    )


def write_suite(items: list[dict[str, Any]], runs: int) -> None:
    """Build the plugin under build/skill-eval and one eval case per item."""
    shutil.rmtree(SUITE, ignore_errors=True)
    files = build_skills.skill_files(ROOT, build_skills.revision(ROOT))
    build_skills.write_files(SUITE, build_skills.marketplace_files(files))
    for item in items:
        case = PLUGIN / "evals" / item["id"]
        (case / "graders").mkdir(parents=True)
        meta = {
            "name": item["id"],
            "tags": [item["stratum"]] + (["pilot"] if item.get("pilot") else []),
            "runs": runs,
            "max_turns": 15,
            "timeout_seconds": 600,
            "allowed_tools": ["Read", "Glob", "Grep", "Skill"],
        }
        (case / "prompt.md").write_text(frontmatter(meta) + prompt_for(item), encoding="utf-8")
        for kind in ("time", "space"):
            (case / "graders" / f"{kind}.md").write_text(
                frontmatter({"type": "llm"}) + criteria_for(item, kind), encoding="utf-8"
            )
        (case / "graders" / "skill.md").write_text(
            frontmatter(
                {
                    "type": "tool_used",
                    "tool": "Skill",
                    "input_match": '"skill"\\s*:\\s*"(?:[\\w-]+:)?python-complexity"',
                }
            ),
            encoding="utf-8",
        )


# Deterministic grading ----------------------------------------------------------------------


def extract_bound(text: str, label: str) -> str | None:
    """Return the O(...) expression on the last `LABEL:` line, or None.

    A line offering more than one bound, negating one, or doing arithmetic on one
    yields None and is left to the judge.
    """
    lines = [line for line in text.splitlines() if re.match(rf"\W*{label}\W*:", line.strip(), re.I)]
    if not lines:
        return None
    line = lines[-1]
    starts = list(re.finditer(r"[OΘ]\s*\(", line))
    if len(starts) != 1 or re.search(r"\b(?:not|or)\b", line, re.I):
        return None
    depth = 0
    for index in range(starts[0].end() - 1, len(line)):
        depth += {"(": 1, ")": -1}.get(line[index], 0)
        if depth == 0:
            bound = line[starts[0].start() : index + 1]
            # Only markdown may precede the bound, and only qualifying words follow it.
            before = line[line.index(":") + 1 : starts[0].start()]
            after = line[index + 1 :]
            if before.strip(" `*_") or not re.fullmatch(r"[\s`*_.,;:()\-–—]*", re.sub(
                r"[A-Za-z]+", lambda w: "" if w[0].lower() in QUALIFIERS else "#", after
            )):  # fmt: skip
                return None
            return bound
    return None


def normalize(bound: str) -> str:
    """Reduce notation differences that do not change the bound."""
    text = bound.replace("Θ", "O").replace("−", "-").replace("²", "^2").replace("**", "^")
    text = re.sub(r"[\s`*·×⋅]", "", text)
    text = re.sub(r"log\(([A-Za-z])\)", r"log\1", text)
    return text


def deterministic(item: dict[str, Any], kind: str, answer: str | None) -> bool:
    """Whether an extracted bound is the key or one of its accepted spellings."""
    if answer is None:
        return False
    accepted = [item[kind]["key"], *item[kind].get("accept", [])]
    return normalize(answer) in {normalize(a) for a in accepted}


# Running ------------------------------------------------------------------------------------


def describe_call(block: dict[str, Any]) -> tuple[str, bool]:
    """Name a tool call by its target, and say whether it invoked this skill."""
    arguments = block["input"]
    target = next(
        (str(arguments[k]) for k in ("file_path", "pattern", "skill") if k in arguments), ""
    )
    fired = block["name"] == "Skill" and bool(
        re.search(r"(?:^|:)python-complexity$", str(arguments.get("skill", "")))
    )
    return f"{block['name']} {target.rpartition('/references/')[2]}", fired


def read_trace(trace: Path) -> dict[str, Any]:
    """Summarise one run's trace.jsonl.

    The reply is the text of the last assistant message, all of its text blocks
    joined, and empty when that message holds only tool calls; a message streamed
    as several events shares one message id.
    """
    summary: dict[str, Any] = {"reply": "", "tool_calls": [], "skill_fired": False}
    summary.update(model_id=None, denied=0)
    reply_id, texts = None, []
    for line in trace.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "system":
            if event.get("subtype") == "init":
                summary["model_id"] = event.get("model")
            elif event.get("subtype") == "permission_denied":
                summary["denied"] += 1
        if event.get("type") != "assistant":
            continue
        message = event["message"]
        if message.get("id") != reply_id:
            reply_id, texts = message.get("id"), []
        for block in message.get("content", []):
            if block.get("type") == "text" and block["text"].strip():
                texts.append(block["text"])
            elif block.get("type") == "tool_use":
                call, fired = describe_call(block)
                summary["tool_calls"].append(call)
                summary["skill_fired"] = summary["skill_fired"] or fired
    summary["reply"] = "\n\n".join(texts)
    return summary


def remove_kept(directory: Path) -> None:
    """Delete a run directory that --keep-temp left read-only."""
    subprocess.run(["chmod", "-R", "u+rwx", str(directory)], check=False)
    shutil.rmtree(directory, ignore_errors=True)


def collect(result: dict[str, Any], items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in result["cases"]:
        item = items[case["name"]]
        for arm, runs in case["arms"].items():
            for index, run in enumerate(runs):
                graders = {g["name"]: g for g in run.get("graders", [])}
                trace = Path(run["tracePath"]) if run.get("tracePath") else None
                trace_summary = read_trace(trace) if trace and trace.exists() else {}
                text = trace_summary.get("reply", "")
                row = {
                    "id": item["id"],
                    "stratum": item["stratum"],
                    "arm": arm,
                    "run": index,
                    "error": run.get("error"),
                    "model_id": trace_summary.get("model_id"),
                    "time_answer": extract_bound(text, "time"),
                    "space_answer": extract_bound(text, "space"),
                    "time_judge": graders.get("time", {}).get("passed"),
                    "space_judge": graders.get("space", {}).get("passed"),
                    # The judge ruled against these criteria; a changed key invalidates the ruling.
                    "time_criteria_sha256": digest(criteria_for(item, "time")),
                    "space_criteria_sha256": digest(criteria_for(item, "space")),
                    "skill_fired": trace_summary.get("skill_fired", False),
                    "tool_calls": trace_summary.get("tool_calls", []),
                    "denied_tool_calls": trace_summary.get("denied", 0),
                    "turns": run.get("turns"),
                    "cost_usd": run.get("costUsd"),
                    "judge_cost_usd": run.get("judgeCostUsd"),
                    "duration_seconds": run.get("durationSeconds"),
                    "reply": text,
                }
                rows.append(row)
                if trace:
                    remove_kept(trace.parent.parent)
    return rows


def run(args: argparse.Namespace) -> Path:
    items = [i for i in load_items() if not args.pilot or i.get("pilot")]
    if args.case:
        items = [i for i in items if fnmatch.fnmatchcase(i["id"], args.case)]
    write_suite(items, args.runs)
    started = datetime.now(UTC)
    result_path = SUITE / "result.json"
    command = [
        "claude", "plugin", "eval", str(PLUGIN),
        "--trust-plugin", "--keep-temp", "--no-publish",
        "--model", args.model, "--judge-model", args.judge_model,
        "--runs", str(args.runs), "--concurrency", str(args.concurrency),
        "--disallow-tools", "Agent", "Task", "TaskStop", "ToolSearch",
        "--threshold", "0", "--json", str(result_path),
    ]  # fmt: skip
    if args.max_cost_usd:
        command += ["--max-cost-usd", str(args.max_cost_usd)]
    completed = subprocess.run(command, cwd=SUITE, check=False)
    if not result_path.exists():
        raise SystemExit(f"claude plugin eval exited {completed.returncode} without a result")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    rows = collect(result, {i["id"]: i for i in items})
    label = f"{started:%Y%m%dT%H%M%SZ}-{args.model}" + ("-pilot" if args.pilot else "")
    out = EVALS / "results" / label
    out.mkdir(parents=True)
    with (out / "runs.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = json.loads((PLUGIN / "skills" / build_skills.NAME / "manifest.json").read_text())
    meta = {
        "started": started.isoformat(timespec="seconds"),
        "model": args.model,
        # The alias resolves to whichever model is current; the runs record the one used.
        "model_ids": sorted({r["model_id"] for r in rows if r["model_id"]}),
        "judge_model": args.judge_model,
        "runs_per_arm": args.runs,
        "python_asked": PYTHON,
        "items": len(items),
        "pilot": args.pilot,
        "claude_version": result.get("claudeVersion"),
        "skill_version": manifest["version"],
        "skill_revision": manifest["source_revision"],
        # Identifies the skill's content even when the revision carries -dirty.
        "skill_files_sha256": hashlib.sha256(
            json.dumps(manifest["files_sha256"], sort_keys=True).encode()
        ).hexdigest(),
        "prompt_sha256": digest(PROMPT),
        # Changes when any selected item's question changes, not only the template.
        "questions_sha256": digest("\n".join(i["id"] + "\n" + prompt_for(i) for i in items)),
        "criteria_sha256": digest(
            "\n".join(criteria_for(i, k) for i in items for k in ("time", "space"))
        ),
        "exit_code": completed.returncode,
        "partial": result.get("partial"),
        "cost_usd": result.get("costUsd"),
        "duration_seconds": result.get("durationSeconds"),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    report(out)
    return out


# Reporting ----------------------------------------------------------------------------------


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else float("nan")


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value for b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def bootstrap(deltas: list[float], rounds: int = 10_000) -> tuple[float, float]:
    """95% interval for the mean per-item difference, resampling items."""
    rng = random.Random(0)
    means = sorted(
        mean(rng.choice(deltas) for _ in deltas) for _ in range(rounds)
    )  # fmt: skip
    return means[int(0.025 * rounds)], means[int(0.975 * rounds)]


def answer(row: dict[str, Any], kind: str) -> str | None:
    """The bound in the stored reply, extracted with the current rules."""
    return extract_bound(row.get("reply", ""), kind)


def ruling(row: dict[str, Any], item: dict[str, Any], kind: str) -> bool | None:
    """The judge's verdict, or None when it ruled against criteria that have since changed."""
    if row.get(f"{kind}_criteria_sha256") != digest(criteria_for(item, kind)):
        return None
    return row[f"{kind}_judge"]


def passed(row: dict[str, Any], item: dict[str, Any], kind: str) -> bool:
    """An exact match with the key passes; any other spelling is the judge's call.

    For `both`, a run passes only when its time and space bounds both pass.
    """
    if kind == "both":
        return passed(row, item, "time") and passed(row, item, "space")
    return deterministic(item, kind, answer(row, kind)) or bool(ruling(row, item, kind))


def report(out: Path) -> None:
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (out / "runs.jsonl").read_text().splitlines()]
    items = {i["id"]: i for i in load_items()}
    graded = [r for r in rows if not r["error"]]
    # An item needs graded runs in both arms to be compared, and a key to be graded against.
    ids = [
        i
        for i in dict.fromkeys(r["id"] for r in rows)
        if i in items and {r["arm"] for r in graded if r["id"] == i} == {"with", "without"}
    ]
    dropped = sorted({r["id"] for r in rows} - set(ids))
    stale = sorted(
        i for i in ids for k in ("time", "space")
        if any(ruling(r, items[i], k) is None for r in graded if r["id"] == i)
    )  # fmt: skip

    def score(item_id: str, arm: str, kind: str) -> float:
        runs = [r for r in graded if r["id"] == item_id and r["arm"] == arm]
        return mean(passed(r, items[item_id], kind) for r in runs)

    lines = [
        f"# Skill recall: {meta['model']}",
        "",
        f"- Model {', '.join(meta.get('model_ids') or ['unrecorded'])}",
        f"- Started {meta['started']}; Claude Code {meta['claude_version']}; "
        f"judge {meta['judge_model']}",
        f"- Skill {meta['skill_version']} at {meta['skill_revision']}, files digest "
        f"{meta.get('skill_files_sha256', 'unrecorded')[:12]}",
        f"- {meta['items']} items, {meta['runs_per_arm']} runs per arm, "
        f"questions asked about CPython {meta['python_asked']}",
        f"- Cost ${meta['cost_usd'] or 0:.2f}; {len(rows) - len(graded)} runs ended in an error",
        f"- Not compared (no key, or no graded run in one arm): {', '.join(dropped) or 'none'}",
        "- Key changed since the run, so only exact matches count: "
        f"{', '.join(dict.fromkeys(stale)) or 'none'}",
        "",
        "A bound passes when it matches the key exactly, as one of the spellings items.yaml "
        "accepts, or by the judge's ruling on any other spelling; `both` counts a run only when "
        "its time and space bounds both pass. Each arm's score is the mean over items of the "
        "fraction of runs that pass. Δ is the mean per-item difference, with a bootstrap 95% "
        "interval that resamples items. McNemar's test compares items, each counted as passing "
        "in an arm when most of its runs there pass.",
        "",
        "## Summary",
        "",
        "| Stratum | Items | Bound | Without skill | With skill | Δ | 95% CI | McNemar p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for stratum in ("common", "tail", "all"):
        chosen = [i for i in ids if stratum == "all" or items[i]["stratum"] == stratum]
        if not chosen:
            continue
        for kind in ("time", "space", "both"):
            without = [score(i, "without", kind) for i in chosen]
            with_ = [score(i, "with", kind) for i in chosen]
            deltas = [w - o for w, o in zip(with_, without, strict=True)]
            low, high = bootstrap(deltas)
            b = sum(1 for w, o in zip(with_, without, strict=True) if w > 0.5 >= o)
            c = sum(1 for w, o in zip(with_, without, strict=True) if o > 0.5 >= w)
            lines.append(
                f"| {stratum} | {len(chosen)} | {kind} | {mean(without):.0%} | "
                f"{mean(with_):.0%} | {mean(deltas):+.0%} | {low:+.0%} to {high:+.0%} | "
                f"{mcnemar(b, c):.3f} |"
            )
    with_runs = [r for r in graded if r["arm"] == "with"]
    without_runs = [r for r in graded if r["arm"] == "without"]
    lines += [
        "",
        f"The skill fired in {sum(r['skill_fired'] for r in with_runs)} of {len(with_runs)} "
        "with-skill runs. Mean cost per run: "
        f"${mean(r['cost_usd'] or 0 for r in without_runs):.3f} without, "
        f"${mean(r['cost_usd'] or 0 for r in with_runs):.3f} with.",
        "",
        "## Items",
        "",
        "| Item | Stratum | Key time | Key space | Without: time | Without: space "
        "| With: time | With: space |",
        "|---|---|---|---|---|---|---|---|",
    ]

    def answers(item_id: str, arm: str, kind: str) -> str:
        runs = [r for r in graded if r["id"] == item_id and r["arm"] == arm]
        marks = [
            f"{'✓' if passed(r, items[item_id], kind) else '✗'} {answer(r, kind) or '—'}"
            for r in runs
        ]
        return "<br>".join(m.replace("|", "\\|") for m in marks)

    for item_id in ids:
        item = items[item_id]
        lines.append(
            f"| `{item_id}` | {item['stratum']} | {item['time']['key']} | "
            f"{item['space']['key']} | {answers(item_id, 'without', 'time')} | "
            f"{answers(item_id, 'without', 'space')} | {answers(item_id, 'with', 'time')} | "
            f"{answers(item_id, 'with', 'space')} |"
        )
    flips = [
        (i, k)
        for i in ids
        for k in ("time", "space")
        if score(i, "without", k) > score(i, "with", k)
    ]
    lines += ["", "## Worse with the skill", ""]
    lines += [
        f"- `{i}` {k}: {score(i, 'without', k):.0%} without, {score(i, 'with', k):.0%} with"
        for i, k in flips
    ] or ["None."]
    lines += [
        "",
        "## Judge rulings to review",
        "",
        "Bounds the judge accepted although they are not a listed spelling of the key, and "
        "exact matches the judge rejected (scored as passes).",
        "",
    ]
    rulings = [
        f"- `{r['id']}` {r['arm']} run {r['run']} {kind}: {answer(r, kind) or 'no single bound'}"
        f" - judge {'pass' if r[f'{kind}_judge'] else 'fail'}, key {items[r['id']][kind]['key']}"
        for r in graded
        if r["id"] in ids
        for kind in ("time", "space")
        if ruling(r, items[r["id"]], kind) is not None
        and bool(r[f"{kind}_judge"]) != deterministic(items[r["id"]], kind, answer(r, kind))
    ]
    lines += rulings or ["None."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out / "summary.md")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="Run the suite and write a results directory")
    run_parser.add_argument("--model", default="sonnet")
    run_parser.add_argument("--judge-model", default="sonnet")
    run_parser.add_argument("--runs", type=int, default=3)
    run_parser.add_argument("--concurrency", type=int, default=4)
    run_parser.add_argument("--pilot", action="store_true", help="Only the pilot items")
    run_parser.add_argument("--case", help="Only items whose id matches this glob")
    run_parser.add_argument("--max-cost-usd", type=float)
    report_parser = commands.add_parser("report", help="Rewrite summary.md for a results directory")
    report_parser.add_argument("results", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        run(args)
    else:
        report(args.results)


if __name__ == "__main__":
    main()
