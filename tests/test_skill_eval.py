"""Check the skill evaluation's items, answer keys and deterministic grading.

skills/evals/items.yaml holds the questions the evaluation asks and the bound
each one expects. Every answer key quotes the table row it comes from, so a page
edit that changes or moves that row fails here and the key is revisited. The
evaluation itself calls a model and is run by hand (scripts/skill_eval.py);
these tests cover only what can be checked without one.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.skill_eval import (
    CASES,
    EVALS,
    ROOT,
    criteria_for,
    deterministic,
    digest,
    extract_bound,
    load_items,
    mcnemar,
    normalize,
    prompt_for,
    read_trace,
    report,
)

ITEMS = load_items()
REQUIRED = {"id", "stratum", "operation", "variables", "case", "time", "space", "source"}


def test_items_are_well_formed() -> None:
    ids = [item["id"] for item in ITEMS]
    assert len(ids) == len(set(ids))
    assert len(ITEMS) == 100
    for item in ITEMS:
        assert REQUIRED <= item.keys() <= REQUIRED | {"usage", "pilot"}, item["id"]
        assert item["stratum"] in {"common", "tail"}
        assert item["case"] in CASES
        assert ("usage" in item) == (item["stratum"] == "common"), item["id"]
        for kind in ("time", "space"):
            assert set(item[kind]) <= {"key", "accept"}
            assert extract_bound(f"{kind.upper()}: {item[kind]['key']}", kind)


def test_pilot_covers_both_strata_equally() -> None:
    pilot = [item for item in ITEMS if item.get("pilot")]
    assert len([i for i in pilot if i["stratum"] == "common"]) == 10
    assert len([i for i in pilot if i["stratum"] == "tail"]) == 10


@pytest.mark.parametrize("item", ITEMS, ids=[item["id"] for item in ITEMS])
def test_answer_key_row_is_on_its_page(item: dict) -> None:
    page = ROOT / item["source"]["page"]
    assert item["source"]["row"] in page.read_text(encoding="utf-8")


def test_common_items_come_from_the_usage_scan() -> None:
    usage = json.loads((EVALS / "usage.json").read_text(encoding="utf-8"))
    ranked = {row["name"] for row in usage["usage"]}
    assert len(usage["packages"]) == 100
    for item in ITEMS:
        if item["stratum"] == "common":
            assert item["usage"] in ranked, item["id"]


def test_prompt_and_criteria_carry_the_question_but_not_the_key() -> None:
    item = next(i for i in ITEMS if i["id"] == "str-rfind")
    prompt = prompt_for(item)
    assert "`s.rfind(sub)`" in prompt and "n = len(s); m = len(sub)" in prompt
    assert "worst-case" in prompt and "O(n·m)" not in prompt
    assert prompt.rstrip().endswith("TIME: O(...)\nSPACE: O(...)")
    criteria = criteria_for(item, "time")
    assert "O(n·m)" in criteria and "O(n * m)" in criteria and "`TIME: O(...)`" in criteria


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Some text.\n\nTIME: O(n log n)\nSPACE: O(n)", "O(n log n)"),
        ("**TIME:** `O(min(i, n - i))` worst case", "O(min(i, n - i))"),
        ("time: O(1) amortized", "O(1)"),
        ("TIME: O(n)\nlater\nTIME: O(n·m)", "O(n·m)"),
        ("Time complexity is linear.", None),
        ("TIME: linear", None),
        ("TIME: O(n) or O(n²)", None),
        ("TIME: O(n) average, O(n²) worst", None),
        ("TIME: not O(n)", None),
        ("TIME: O(n) * log n", None),
        ("TIME: n * O(1)", None),
        ("TIME: O(n)^2", None),
        ("**TIME:** `O(n)` **amortized**", "O(n)"),
        ("TIME: O(n) (worst case, amortized).", "O(n)"),
        ("TIME: O(n) ⋅ m", None),
        ("TIME: O(n) ** m", None),
        ("TIME: O(n) per item", None),
    ],
)
def test_extract_bound(reply: str, expected: str | None) -> None:
    assert extract_bound(reply, "time") == expected


def test_normalize_ignores_notation_only() -> None:
    assert normalize("O(n · m)") == normalize("O(n*m)") == normalize("O(nm)")
    assert normalize("O(n log(n))") == normalize("O(n log n)")
    assert normalize("Θ(n²)") == normalize("O(n^2)")
    assert normalize("O(n + N)") != normalize("O(n + n)")
    assert normalize("O(n)") != normalize("O(m)")
    assert normalize("O(n**m)") == normalize("O(n^m)") != normalize("O(n*m)")


def test_deterministic_grader_uses_key_and_accepted_spellings() -> None:
    item = next(i for i in ITEMS if i["id"] == "str-rfind")
    assert deterministic(item, "time", "O(n·m)")
    assert deterministic(item, "time", "O(m n)")
    assert not deterministic(item, "time", "O(n + m)")
    assert not deterministic(item, "space", None)


def test_mcnemar_is_exact_and_symmetric() -> None:
    assert mcnemar(0, 0) == 1.0
    assert mcnemar(5, 0) == mcnemar(0, 5) == pytest.approx(2 / 32)
    assert mcnemar(3, 3) == 1.0


def test_trace_reply_joins_the_last_message_and_counts_only_this_skill(tmp_path: Path) -> None:
    events: list[dict[str, Any]] = [
        {"type": "system", "subtype": "init", "model": "claude-test-1"},
        {"type": "assistant", "message": {"id": "m1", "content": [
            {"type": "text", "text": "Looking it up."},
            {"type": "tool_use", "name": "Skill", "input": {"skill": "other-skill"}},
        ]}},
        {"type": "system", "subtype": "permission_denied"},
        {"type": "assistant", "message": {"id": "m2", "content": [
            {"type": "tool_use", "name": "Read",
             "input": {"file_path": "/x/skills/python-complexity/references/docs/a.md"}},
        ]}},
        {"type": "assistant", "message": {"id": "m3", "content": [
            {"type": "text", "text": "TIME: O(n)"},
        ]}},
        {"type": "assistant", "message": {"id": "m3", "content": [
            {"type": "text", "text": "SPACE: O(1)"},
        ]}},
    ]  # fmt: skip
    trace = tmp_path / "trace.jsonl"
    trace.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    summary = read_trace(trace)
    assert summary["reply"] == "TIME: O(n)\n\nSPACE: O(1)"
    assert summary["model_id"] == "claude-test-1"
    assert summary["denied"] == 1
    assert summary["skill_fired"] is False
    assert summary["tool_calls"] == ["Skill other-skill", "Read docs/a.md"]
    events[1]["message"]["content"][1]["input"]["skill"] = "python-complexity:python-complexity"
    trace.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    assert read_trace(trace)["skill_fired"] is True
    # A last message that only calls a tool leaves no reply, not the previous one.
    events.append({"type": "assistant", "message": {"id": "m4", "content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}},
    ]}})  # fmt: skip
    trace.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    assert read_trace(trace)["reply"] == ""


def test_report_scores_both_per_run_and_drops_stale_rulings(tmp_path: Path) -> None:
    item = next(i for i in ITEMS if i["id"] == "list-membership")
    current = {k: digest(criteria_for(item, k)) for k in ("time", "space")}

    def row(arm: str, run: int, time: str, space: str, judge: bool, sha: str) -> dict:
        return {
            "id": item["id"], "stratum": item["stratum"], "arm": arm, "run": run,
            "error": None, "reply": f"TIME: {time}\nSPACE: {space}",
            "time_judge": judge, "space_judge": judge,
            "time_criteria_sha256": sha or current["time"],
            "space_criteria_sha256": sha or current["space"],
            "skill_fired": arm == "with", "cost_usd": 0.0,
        }  # fmt: skip

    rows = [
        # Without: time and space each pass in two runs, but together only in run 2.
        row("without", 0, "O(n)", "O(n)", False, ""),
        row("without", 1, "O(1)", "O(1)", False, ""),
        row("without", 2, "O(n)", "O(1)", False, ""),
        # With: the judge's pass on a non-key spelling counts only under current criteria.
        row("with", 0, "O(len(lst))", "O(1)", True, ""),
        row("with", 1, "O(len(lst))", "O(1)", True, "stale"),
        row("with", 2, "O(n)", "O(1)", False, ""),
    ]
    meta = {
        "model": "test", "model_ids": ["claude-test-1"], "started": "now",
        "claude_version": "0", "judge_model": "test", "skill_version": "0",
        "skill_revision": "0", "items": 1, "runs_per_arm": 3, "python_asked": "3.14",
        "cost_usd": 0.0,
    }  # fmt: skip
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (tmp_path / "runs.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    report(tmp_path)
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    # Averaging time and space would give 67% without; requiring both per run gives 33%.
    assert "| all | 1 | time | 67% | 67% |" in summary
    assert "| all | 1 | space | 67% | 100% |" in summary
    assert "| all | 1 | both | 33% | 67% |" in summary
    assert "only exact matches count: list-membership" in summary
