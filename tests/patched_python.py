"""The CVE-2026-3276 fix releases, for tests that time Unicode normalization.

Before the fix, CPython insertion-sorted each run of combining marks, so
normalizing one run of r marks cost O(r²). The fix shipped in the patch
releases below; 3.15 and later shipped with it, so a minor absent from the map
is treated as patched. A distributor that backports the fix while keeping an
older version number is skipped rather than run -- the wrong call for coverage,
but the safe one, since the alternative fails a Python that is not actually
vulnerable.
"""

import os
import sys

import pytest

FIXED_RELEASES = {
    (3, 10): (3, 10, 21),
    (3, 11): (3, 11, 16),
    (3, 12): (3, 12, 14),
    (3, 13): (3, 13, 14),
    (3, 14): (3, 14, 6),
}


def unpatched_reason() -> str | None:
    """Why this interpreter cannot run a linear-normalization test, or None."""
    release = FIXED_RELEASES.get(sys.version_info[:2])
    if release is None or sys.version_info[:3] >= release:
        return None
    version = ".".join(str(part) for part in sys.version_info[:3])
    needed = ".".join(str(part) for part in release)
    return f"Python {version} predates the CVE-2026-3276 fix in {needed}"


def require_patched_normalization() -> None:
    """Skip on an interpreter without the fix, or fail where one is required.

    The `timing` CI job pins patched interpreters and sets
    COMPLEXITY_REQUIRE_PATCHED_PYTHON. A skip there means the pin drifted, not
    that the claim cannot be checked -- and a drifted pin is invisible if it
    stays a skip.
    """
    reason = unpatched_reason()
    if reason is None:
        return
    if os.environ.get("COMPLEXITY_REQUIRE_PATCHED_PYTHON"):
        pytest.fail(f"{reason}, but this job pins one to check the claim")
    pytest.skip(f"version: {reason}")
