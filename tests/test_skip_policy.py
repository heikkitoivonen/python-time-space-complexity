"""Tests for the skip policy in tests/conftest.py.

The unit tests call `skip_problem()` directly. The end-to-end tests run a
throwaway test file under a copy of the conftest in a child pytest, because
what matters is that pytest's own reports are turned into failures: a run
skip, a marker skip and a module-level skip each take a different path.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

import tests.conftest as policy

CONFTEST = pathlib.Path(policy.__file__)


class TestSkipProblem:
    @pytest.fixture(autouse=True)
    def _local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(policy, "ALLOWED_MISSING", None)

    @pytest.mark.parametrize("reason", ["platform: epoll is Linux-only", "version: 3.13+"])
    def test_a_platform_or_version_skip_is_allowed_at_run_time(self, reason: str) -> None:
        assert policy.skip_problem(reason, from_marker=False) is None

    def test_an_untagged_run_time_skip_is_refused(self) -> None:
        problem = policy.skip_problem("needs a pseudo-terminal", from_marker=False)
        assert problem is not None and "must start with" in problem

    def test_a_marker_reason_is_free_text(self) -> None:
        assert policy.skip_problem("Windows-only API", from_marker=True) is None

    def test_an_unknown_capability_is_refused_even_locally(self) -> None:
        problem = policy.skip_problem("missing display: no X server", from_marker=True)
        assert problem is not None and "unknown capability 'display'" in problem

    def test_any_known_capability_may_be_missing_locally(self) -> None:
        assert policy.skip_problem("missing pty: no ptys", from_marker=False) is None

    def test_a_declared_capability_may_be_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(policy, "ALLOWED_MISSING", frozenset({"audio"}))
        assert policy.skip_problem("missing audio: no device", from_marker=True) is None

    def test_an_undeclared_capability_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(policy, "ALLOWED_MISSING", frozenset({"audio"}))
        problem = policy.skip_problem("missing pty: no ptys", from_marker=False)
        assert problem is not None and "not 'pty'" in problem

    def test_an_empty_declaration_refuses_every_capability(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(policy, "ALLOWED_MISSING", frozenset())
        assert policy.skip_problem("missing audio: no device", from_marker=True) is not None


SAMPLE = """
import pytest

@pytest.mark.skipif(True, reason="Windows-only API")
def test_marker_free_text():
    pass

@pytest.mark.skipif(True, reason="missing audio: no device")
def test_marker_capability():
    pass

def test_run_time_untagged():
    pytest.skip("needs something")

def test_run_time_platform():
    pytest.skip("platform: Linux-only")

def test_run_time_capability():
    pytest.skip("missing pty: no ptys")
"""


def run_child(tmp_path: pathlib.Path, source: str, declared: str | None) -> str:
    shutil.copy(CONFTEST, tmp_path / "conftest.py")
    (tmp_path / "test_sample.py").write_text(textwrap.dedent(source), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "COMPLEXITY_MISSING_CAPABILITIES"}
    if declared is not None:
        env["COMPLEXITY_MISSING_CAPABILITIES"] = declared
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:xdist", "-v"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return result.stdout


def outcome(output: str, name: str) -> str:
    """The verdict on the child's `-v` line for `name`."""
    for line in output.splitlines():
        if line.startswith(f"test_sample.py::{name} "):
            return line.split()[1]
    raise AssertionError(f"{name} not reported:\n{output}")


class TestThroughPytest:
    def test_locally_only_the_untagged_run_time_skip_fails(self, tmp_path: pathlib.Path) -> None:
        output = run_child(tmp_path, SAMPLE, declared=None)

        assert outcome(output, "test_run_time_untagged") == "FAILED"
        for name in (
            "test_marker_free_text",
            "test_marker_capability",
            "test_run_time_platform",
            "test_run_time_capability",
        ):
            assert outcome(output, name) == "SKIPPED", name

    def test_a_declaration_fails_the_undeclared_capabilities(self, tmp_path: pathlib.Path) -> None:
        output = run_child(tmp_path, SAMPLE, declared="audio")

        assert outcome(output, "test_marker_capability") == "SKIPPED"
        assert outcome(output, "test_run_time_capability") == "FAILED"
        assert outcome(output, "test_run_time_platform") == "SKIPPED"
        assert "not 'pty'" in output

    def test_a_module_level_skip_is_checked_too(self, tmp_path: pathlib.Path) -> None:
        untagged = run_child(
            tmp_path, 'import pytest\npytest.skip("gone", allow_module_level=True)\n', None
        )
        tagged = run_child(
            tmp_path,
            'import pytest\npytest.skip("platform: gone", allow_module_level=True)\n',
            None,
        )

        assert "1 error" in untagged and "must start with" in untagged
        assert "1 skipped" in tagged and "error" not in tagged

    def test_a_capability_marker_under_a_true_platform_guard_passes(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = """
            import pytest

            @pytest.mark.skipif(True, reason="Windows-only API")
            @pytest.mark.skipif(True, reason="missing pty: no ptys")
            def test_guarded():
                pass

            @pytest.mark.skipif(False, reason="Windows-only API")
            @pytest.mark.skipif(True, reason="missing pty: no ptys")
            def test_unguarded():
                pass
        """
        output = run_child(tmp_path, source, declared="")

        assert outcome(output, "test_guarded") == "SKIPPED"
        # A marker skips during setup, so the refused skip reports as an error.
        assert outcome(output, "test_unguarded") == "ERROR"
