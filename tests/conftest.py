"""Skip policy: a skip must say what decided it.

A test with no platform-specific subject runs everywhere, so a skip is only
ever one of three things, and its reason says which:

* ``platform: ...`` - the subject does not exist or differs on this OS.
* ``version: ...`` - the subject does not exist or differs on this Python.
* ``missing <capability>: ...`` - the machine or interpreter build lacks
  something the test needs (a pseudo-terminal, an audio device, ndbm). The
  capability must be one of ``CAPABILITIES`` below.

A ``skipif`` marker settled by the platform and Python version alone -
``sys.platform``, ``os.name``, ``sys.version_info``, or an attribute every
build of that platform and version has - may give its reason as free text.
Everything decided while the test runs - ``pytest.skip()``, a module-level
skip - must carry one of the prefixes, and the hooks below fail it if it does
not. A marker that probes the machine or the build must use the ``missing``
form too, but the hooks cannot see a marker's condition, so that part of the
rule is kept by review, not enforced.

Locally any capability may be missing. CI sets
``COMPLEXITY_MISSING_CAPABILITIES`` to the capabilities its runner lacks
(space-separated, possibly empty); a ``missing`` skip for anything else then
fails, because on a machine that should have it the skip would hide the test.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest

CAPABILITIES = {
    "audio": "a wave output device",
    "bash": "a bash executable on PATH",
    "c-utf8-locale": "the C.UTF-8 locale",
    "extension-modules": "extension modules loaded from lib-dynload, not built in",
    "frozen-modules": "the standard modules the interpreter runs frozen",
    "int-digit-limit": "the int/str conversion digit limit left enabled",
    "isolated-thread-context": "threads that start with an empty context",
    "kernel-crypto": "the kernel's AF_ALG ciphers",
    "large-pipes": "permission to enlarge a pipe",
    "libintl": "the C library's gettext functions in the locale module",
    "locked-system-file": "a system file held open without sharing",
    "md5": "MD5, which a FIPS-mode OpenSSL refuses",
    "ndbm": "the dbm.ndbm backend",
    "o-tmpfile": "a filesystem that supports O_TMPFILE",
    "open-files": "a descriptor limit high enough for the test",
    "ptrace": "permission to attach to another process",
    "pty": "a working pseudo-terminal",
    "readline-append-history": "readline.append_history_file()",
    "readline-clear-history": "readline.clear_history()",
    "remote-debugging": "sys.remote_exec() enabled in the build",
    "sqlite3": "the sqlite3 module's _sqlite3 extension",
    "sqlite-serialize": "SQLite's serialize API",
    "symlinks": "permission to create symbolic links",
    "terminfo": "a terminfo entry for TERM",
    "tkinter": "the tkinter module and its Tcl/Tk libraries",
    "two-cpus": "at least two usable CPUs",
    "untraced-process": "a process tracemalloc is not already tracing",
    "unfrozen-gc": "a garbage collector with nothing frozen yet",
    "installed-interpreter": "an installed interpreter, not a source-tree build",
    "user-database": "a user database entry for the current uid",
    "unprivileged-token": "a Windows token without the restore privilege enabled",
    "uv": "the uv executable on PATH",
    "xattr": "a filesystem that supports user extended attributes",
    "zstd": "the compression.zstd module",
}

PREFIXES = ("platform: ", "version: ")

_declared = os.environ.get("COMPLEXITY_MISSING_CAPABILITIES")
ALLOWED_MISSING: frozenset[str] | None = None if _declared is None else frozenset(_declared.split())


def skip_problem(reason: str, *, from_marker: bool) -> str | None:
    """Why a skip with this reason breaks the policy, or None if it does not."""
    if reason.startswith("missing "):
        capability, colon, _ = reason[len("missing ") :].partition(": ")
        if not colon or capability not in CAPABILITIES:
            return f"unknown capability {capability!r}; add it to CAPABILITIES in conftest.py"
        if ALLOWED_MISSING is not None and capability not in ALLOWED_MISSING:
            return (
                f"this run declares {sorted(ALLOWED_MISSING)} missing, not {capability!r} "
                f"({CAPABILITIES[capability]}), so the skip would hide the test"
            )
        return None
    if from_marker or reason.startswith(PREFIXES):
        return None
    return "a skip decided at run time must start with 'platform: ', 'version: ' or 'missing '"


def _reason(longrepr: Any) -> str:
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        reason = str(longrepr[2])
        return reason.removeprefix("Skipped: ")
    return str(longrepr)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.skipped and call.excinfo is not None and not hasattr(report, "wasxfail"):
        # pytest raises a marker's skip with the item's location; a
        # pytest.skip() call carries the location of the call instead.
        from_marker = bool(getattr(call.excinfo.value, "_use_item_location", False))
        reason = _reason(report.longrepr)
        problem = skip_problem(reason, from_marker=from_marker)
        if problem is not None and from_marker and _also_skipped_by_another_marker(item, reason):
            problem = None
        if problem is not None:
            report.outcome = "failed"
            report.longrepr = f"skip policy: {problem}\n  reason: {reason}"
    return report


def _also_skipped_by_another_marker(item: pytest.Item, reason: str) -> bool:
    """Whether another true skipif marker, not a capability one, skips the test.

    pytest reports the first true marker, the one nearest the test, so a
    capability marker stacked below a platform guard is the one reported on
    the platform the guard excludes.
    """
    for mark in item.iter_markers(name="skipif"):
        condition = mark.args[0] if mark.args else mark.kwargs.get("condition")
        other = str(mark.kwargs.get("reason", ""))
        if condition is True and other != reason and not other.startswith("missing "):
            return True
    return False


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    report = yield
    if report.skipped:
        reason = _reason(report.longrepr)
        problem = skip_problem(reason, from_marker=False)
        if problem is not None:
            report.outcome = "failed"
            report.longrepr = f"skip policy: {problem}\n  reason: {reason}"
    return report
