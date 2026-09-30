"""Whether Windows lets this process use paths past the 260-character MAX_PATH."""

import ctypes
import sys


def long_paths_enabled() -> bool:
    """What ntdll's RtlAreLongPathsEnabled() reports; always False off Windows.

    It is true when the LongPathsEnabled policy is set and the executable's
    manifest opts in, which python.org and uv builds do.
    """
    if sys.platform != "win32":
        return False
    ntdll = getattr(ctypes, "WinDLL")("ntdll")  # noqa: B009
    check = getattr(ntdll, "RtlAreLongPathsEnabled", None)
    if check is None:  # before Windows 10 1607, which has no long-path support
        return False
    check.restype = ctypes.c_ubyte
    return bool(check())
