"""Find and run the fenced Python blocks of a documentation page."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap

DOCS = pathlib.Path(__file__).parent.parent / "docs"


def python_blocks(page: pathlib.Path) -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based first line."""
    lines = page.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def run_block(
    source: str, cwd: pathlib.Path, timeout: float = 120
) -> subprocess.CompletedProcess[str]:
    """Run one block as a script in its own interpreter and working directory.

    A block still running after `timeout` seconds is killed and reported as a
    failure, so a hang is attributed to its page and line like any other.
    """
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    command = [sys.executable, str(script)]
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as expired:
        partial = expired.stderr or ""
        if isinstance(partial, bytes):
            partial = partial.decode(errors="replace")
        return subprocess.CompletedProcess(
            command, -1, "", f"{partial}timed out after {timeout} seconds"
        )


def failing_blocks(page: pathlib.Path, tmp_path: pathlib.Path) -> list[str]:
    """Run every block on the page; describe each one that exits non-zero."""
    failures: list[str] = []
    for line, source in python_blocks(page):
        workdir = tmp_path / f"block{line}"
        workdir.mkdir()
        result = run_block(source, workdir)
        if result.returncode != 0:
            failures.append(f"{page.relative_to(DOCS)}:{line}\n{result.stderr.strip()}")
    return failures
