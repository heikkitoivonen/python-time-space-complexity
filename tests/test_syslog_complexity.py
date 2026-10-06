"""Tests for docs/stdlib/syslog.md.

The page prices each call by the work done in the process: `syslog()` costs
its message's length, and everything else is O(1). Delivery to the system
logger is outside every bound, and no test here may deliver anything: a test
cannot read back what the logger received, and a message sent from CI would
land in the runner's real log. So every test that calls `openlog()`,
`syslog()`, `closelog()` or `setlogmask()` runs in its own subprocess under an audit hook that records the module's
`syslog.*` events and raises before the C library's `syslog()` could send.
The module raises each event before it calls the C function, so a raising
hook stops the call while still showing the arguments it was given. The
hook's rule: `syslog.syslog` is allowed through only while the log is closed
and the implicit `syslog.openlog` that must then follow is set to raise.

Measurement scope:

* `openlog()` with no arguments, after `sys.argv[0]` is set to
  `/srv/app/worker.py`, raises the event with ident `worker.py`, logoption 0
  and facility `LOG_USER`; with keyword arguments, the event carries them.
* `syslog('hi')` on a log that is not open raises `syslog.syslog` with
  priority `LOG_INFO` and then `syslog.openlog` with the default arguments.
  After a real `openlog(ident='myapp', facility=LOG_LOCAL0)` and
  `closelog()`, the next `syslog()` raises `syslog.openlog` again with the
  default ident, logoption and facility.
* `setlogmask(0)` returns `LOG_UPTO(LOG_DEBUG)` in a fresh process, and
  returns the same value twice, so 0 does not change the mask;
  `setlogmask(m)` returns the mask it replaced, and `setlogmask(0)` then
  returns `m`.
* `LOG_MASK(p)` is `1 << p` and `LOG_UPTO(p)` is the OR of `LOG_MASK(0)` to
  `LOG_MASK(p)`, for p from 0 to 7. The priority levels are 0 to 7 from
  `LOG_EMERG` to `LOG_DEBUG`, and every facility present has its low three
  bits clear.
* The message is converted in full before the C library sees it, including
  at a priority the mask excludes: `sys.getsizeof()` of a message of 1,000
  and of 100,000 copies of `'é'` grows by exactly its UTF-8 length plus one
  after a `syslog(LOG_DEBUG, ...)` stopped at the audit event, with the mask
  set to `LOG_UPTO(LOG_INFO)`. An ASCII message does not grow: its UTF-8 is
  its own storage.
* On 3.12+, a message containing a null character raises `ValueError` before
  any audit event. On 3.10 and 3.11, the event's message is the text before
  the null character.
* LOG_FTP and the five Apple facilities are absent before 3.13. From 3.13, on
  Linux (glibc) `LOG_FTP` and `LOG_AUTHPRIV` exist and the Apple facilities
  do not; on macOS all seven exist. `LOG_ODELAY`, `LOG_NOWAIT` and
  `LOG_PERROR` exist on both.
* `import logging.handlers` does not import `syslog`. On Windows,
  `import syslog` raises `ModuleNotFoundError`.
* Every fenced Python block runs in its own subprocess under the hook, with
  `syslog.syslog` wrapped to swallow the hook's stop, so its arguments are
  parsed and converted by the real function and nothing is sent; `openlog()`,
  `closelog()` and `setlogmask()` are the real ones. The events each block
  produced are asserted against what its comments say, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(n) time and space of `syslog()` beyond the conversion: the C library
  formats the header and message into one buffer and writes it to the
  logger's socket. That is `syslog(3)`, not run here, and delivery is
  outside the bound by definition.
* That the C library drops a message whose priority the mask excludes, and
  that a facility ORed into the priority overrides `openlog()`'s, are the
  POSIX contract for `syslog(3)` and `setlogmask(3)`; seeing either needs the
  logger. That 0 leaves the mask unchanged is POSIX too, and is observed.
* The O(1) bounds of `openlog()`, `closelog()`, `setlogmask()`,
  `LOG_MASK()` and `LOG_UPTO()`, and the time half of `syslog()`'s O(n),
  are read from Modules/syslogmodule.c, with every argument but the message
  counted as O(1) as the page states. None is timed.
* That `logging.handlers.SysLogHandler` talks to a syslog server from pure
  Python is the official documentation's and Lib/logging/handlers.py's (a
  socket); only that importing it does not import this module is run.
* That the module holds only the identity string, and that the mask is the
  C library's state for the whole process, are read from
  Modules/syslogmodule.c (`S_ident_o` is its only object) and setlogmask(3).
* That `syslog()` does not reopen a log that is open is read from
  Modules/syslogmodule.c (the `S_log_open` flag, v3.10.19 to v3.14.2): with
  the log open, the hook stops `syslog()` before the point where it would
  open the log.
* Module state is per process, so `closelog()`'s reset is observed only in
  the main interpreter. The 3.12+ restrictions in subinterpreters are not on
  the page and not run.
* Facility and option values beyond the low-bit check, and which of the
  platform-dependent constants other Unix systems define, follow each
  platform's `<syslog.h>`; only Linux (glibc) and macOS are run.
* API coverage: the audit on 3.14 reports no missing names for the page;
  constants are outside its inventory, and `LOG_MASK` and `LOG_UPTO`, which
  it lists as needing classification, are documented.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import re
import subprocess
import sys
import textwrap
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "syslog.md"
EXPECTED_BLOCKS = 3

UNIX = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows builds do not compile Modules/syslogmodule.c"
)
syslog: Any = importlib.import_module("syslog") if sys.platform != "win32" else None

APPLE_FACILITIES = ("LOG_NETINFO", "LOG_REMOTEAUTH", "LOG_INSTALL", "LOG_RAS", "LOG_LAUNCHD")
PRIORITIES = (
    "LOG_EMERG",
    "LOG_ALERT",
    "LOG_CRIT",
    "LOG_ERR",
    "LOG_WARNING",
    "LOG_NOTICE",
    "LOG_INFO",
    "LOG_DEBUG",
)
UNCONDITIONAL_FACILITIES = (
    "LOG_KERN",
    "LOG_USER",
    "LOG_MAIL",
    "LOG_DAEMON",
    "LOG_AUTH",
    "LOG_LPR",
    "LOG_NEWS",
    "LOG_UUCP",
    "LOG_CRON",
    "LOG_SYSLOG",
    *(f"LOG_LOCAL{i}" for i in range(8)),
)
FACILITIES = (
    *UNCONDITIONAL_FACILITIES,
    "LOG_AUTHPRIV",
    "LOG_FTP",
    *APPLE_FACILITIES,
)

# Installed ahead of every subprocess's code. It records the module's audit
# events and stops any call that could reach the C library's syslog(): a
# `syslog.syslog` event is let through only while the log is closed and
# BLOCK_OPEN makes the implicit `syslog.openlog` that follows raise.
HARNESS = """
import atexit, json, sys

EVENTS = []
BLOCK_OPEN = False
_open = False


class Blocked(Exception):
    pass


def _hook(event, args):
    global _open
    if not event.startswith('syslog.'):
        return
    EVENTS.append([event, list(args)])
    if event == 'syslog.openlog':
        if BLOCK_OPEN:
            raise Blocked
        _open = True
    elif event == 'syslog.closelog':
        _open = False
    elif event == 'syslog.syslog' and (_open or not BLOCK_OPEN):
        raise Blocked


sys.addaudithook(_hook)
atexit.register(lambda: sys.__stdout__.write('\\nEVENTS=' + json.dumps(EVENTS) + '\\n'))
"""

# Added for the page's blocks: they call syslog.syslog() as an application
# would, so the hook's stop is swallowed after the real argument handling.
SWALLOW = """
import syslog

_real_syslog = syslog.syslog


def _syslog(*args):
    try:
        _real_syslog(*args)
    except Blocked:
        return
    raise AssertionError('syslog() was not stopped by the audit hook')


syslog.syslog = _syslog
"""


def _run(code: str, prelude: str = "") -> tuple[subprocess.CompletedProcess[str], list[Any]]:
    """Run code under the harness; return the process and its recorded events."""
    script = HARNESS + prelude + textwrap.dedent(code)
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    match = re.search(r"^EVENTS=(.*)$", result.stdout, re.MULTILINE)
    events = json.loads(match.group(1)) if match else []
    return result, events


def _check(code: str) -> list[Any]:
    result, events = _run(code)
    assert result.returncode == 0, result.stderr
    return events


class TestAvailability:
    """The module is Unix-only, and `logging.handlers.SysLogHandler` does
    without it."""

    @pytest.mark.skipif(
        sys.platform != "win32", reason="only Windows builds omit Modules/syslogmodule.c"
    )
    def test_importing_it_on_windows_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("syslog")

    def test_logging_handlers_does_not_import_it(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys, logging.handlers\n"
                "assert hasattr(logging.handlers, 'SysLogHandler')\n"
                "assert 'syslog' not in sys.modules\n",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert result.returncode == 0, result.stderr


@UNIX
class TestHarness:
    """The guard every other test relies on: a `syslog()` call is stopped
    before the C library whether or not the log is open."""

    def test_a_call_on_an_open_log_is_stopped(self) -> None:
        events = _check(
            """
            import syslog
            syslog.openlog(ident='harness-test')
            try:
                syslog.syslog('never sent')
            except Blocked:
                pass
            else:
                raise AssertionError('reached the C library')
            """
        )
        assert [event for event, _ in events] == ["syslog.openlog", "syslog.syslog"]

    def test_a_call_that_would_open_the_log_is_stopped(self) -> None:
        events = _check(
            """
            import syslog
            try:
                syslog.syslog('never sent')
            except Blocked:
                pass
            else:
                raise AssertionError('reached the C library')
            """
        )
        assert [event for event, _ in events] == ["syslog.syslog"]


@UNIX
class TestOpenlog:
    """`openlog()` row: sets the identity, options and default facility;
    `ident` defaults to `sys.argv[0]` without its directory and `facility` to
    `LOG_USER`."""

    def test_the_default_ident_is_argv0_without_its_directory(self) -> None:
        events = _check(
            """
            import syslog
            sys.argv[0] = '/srv/app/worker.py'
            BLOCK_OPEN = True
            try:
                syslog.openlog()
            except Blocked:
                pass
            """
        )
        assert events == [["syslog.openlog", ["worker.py", 0, syslog.LOG_USER]]]

    def test_keyword_arguments_are_passed_through(self) -> None:
        events = _check(
            """
            import syslog
            BLOCK_OPEN = True
            try:
                syslog.openlog(
                    ident='myapp', logoption=syslog.LOG_PID, facility=syslog.LOG_LOCAL0
                )
            except Blocked:
                pass
            """
        )
        assert events == [["syslog.openlog", ["myapp", syslog.LOG_PID, syslog.LOG_LOCAL0]]]


@UNIX
class TestSyslogOpensTheLog:
    """`syslog()` and `closelog()` rows: `priority` defaults to `LOG_INFO`;
    a log that is not open is opened as `openlog()` with no arguments, which
    is also what the first call after `closelog()` does, dropping the
    identity and facility set before it."""

    def test_the_first_call_opens_the_log_with_the_defaults(self) -> None:
        events = _check(
            """
            import syslog
            sys.argv[0] = '/srv/app/job'
            BLOCK_OPEN = True
            try:
                syslog.syslog('hi')
            except Blocked:
                pass
            """
        )
        assert events == [
            ["syslog.syslog", [syslog.LOG_INFO, "hi"]],
            ["syslog.openlog", ["job", 0, syslog.LOG_USER]],
        ]

    def test_closelog_makes_the_next_call_open_it_with_the_defaults(self) -> None:
        events = _check(
            """
            import syslog
            sys.argv[0] = '/srv/app/job'
            syslog.openlog(ident='myapp', facility=syslog.LOG_LOCAL0)
            syslog.closelog()
            BLOCK_OPEN = True
            try:
                syslog.syslog(syslog.LOG_ERR, 'after close')
            except Blocked:
                pass
            """
        )
        assert events == [
            ["syslog.openlog", ["myapp", 0, syslog.LOG_LOCAL0]],
            ["syslog.closelog", []],
            ["syslog.syslog", [syslog.LOG_ERR, "after close"]],
            ["syslog.openlog", ["job", 0, syslog.LOG_USER]],
        ]


@UNIX
class TestSetlogmask:
    """`setlogmask()` row: returns the previous mask, and 0 leaves the mask
    unchanged, so `setlogmask(0)` reads it. By default every priority
    passes."""

    def test_zero_reads_the_mask_and_a_mask_returns_the_old_one(self) -> None:
        _check(
            """
            import syslog
            everything = syslog.LOG_UPTO(syslog.LOG_DEBUG)
            assert syslog.setlogmask(0) == everything
            assert syslog.setlogmask(0) == everything

            warnings_up = syslog.LOG_UPTO(syslog.LOG_WARNING)
            assert syslog.setlogmask(warnings_up) == everything
            assert syslog.setlogmask(0) == warnings_up
            assert syslog.setlogmask(0) == warnings_up
            assert syslog.setlogmask(everything) == warnings_up
            """
        )


@UNIX
class TestMaskHelpers:
    """`LOG_MASK()` and `LOG_UPTO()` rows, and the priority-level row: levels
    0 to 7, most severe first."""

    def test_the_priority_levels_are_zero_to_seven_most_severe_first(self) -> None:
        assert [getattr(syslog, name) for name in PRIORITIES] == list(range(8))

    def test_log_mask_is_one_bit_per_priority(self) -> None:
        for pri in range(8):
            assert syslog.LOG_MASK(pri) == 1 << pri

    def test_log_upto_covers_every_priority_up_to_and_including_pri(self) -> None:
        for pri in range(8):
            expected = 0
            for more_severe in range(pri + 1):
                expected |= syslog.LOG_MASK(more_severe)
            assert syslog.LOG_UPTO(pri) == expected


@UNIX
class TestConstants:
    """Facility rows: their bits do not overlap the priority levels', and the
    platform-dependent ones exist where `<syslog.h>` defines them, the six
    from 3.13."""

    def test_the_unconditional_constants_exist(self) -> None:
        for name in (*UNCONDITIONAL_FACILITIES, "LOG_PID", "LOG_CONS", "LOG_NDELAY"):
            assert isinstance(getattr(syslog, name), int), name

    def test_facilities_leave_the_priority_bits_clear(self) -> None:
        present = [name for name in FACILITIES if hasattr(syslog, name)]
        assert set(UNCONDITIONAL_FACILITIES) <= set(present)
        for name in present:
            assert getattr(syslog, name) & 0x07 == 0, name

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="the six were added in 3.13")
    def test_the_3_13_facilities_are_absent_before_it(self) -> None:
        for name in ("LOG_FTP", *APPLE_FACILITIES):
            assert not hasattr(syslog, name), name

    @pytest.mark.skipif(
        sys.platform != "linux" or sys.version_info < (3, 13),
        reason="glibc's <syslog.h> defines LOG_FTP and none of the Apple facilities; "
        "the module exports LOG_FTP from 3.13",
    )
    def test_linux_has_log_ftp_and_not_the_apple_facilities(self) -> None:
        assert isinstance(syslog.LOG_FTP, int)
        assert isinstance(syslog.LOG_AUTHPRIV, int)
        for name in APPLE_FACILITIES:
            assert not hasattr(syslog, name), name

    @pytest.mark.skipif(
        sys.platform != "darwin" or sys.version_info < (3, 13),
        reason="macOS's <syslog.h> defines the Apple facilities; the module exports them from 3.13",
    )
    def test_macos_has_every_facility(self) -> None:
        for name in ("LOG_AUTHPRIV", "LOG_FTP", *APPLE_FACILITIES):
            assert isinstance(getattr(syslog, name), int), name

    @pytest.mark.skipif(
        sys.platform not in ("linux", "darwin"),
        reason="glibc's and macOS's <syslog.h> both define the three options",
    )
    def test_the_optional_options_exist_on_linux_and_macos(self) -> None:
        for name in ("LOG_ODELAY", "LOG_NOWAIT", "LOG_PERROR"):
            assert isinstance(getattr(syslog, name), int), name


@UNIX
class TestMessageConversion:
    """`syslog()` row and the mask notes: the whole message is converted
    before the C library sees it, whatever the mask, so the call is O(n) in
    the message even when the message is then filtered."""

    def test_a_filtered_message_is_still_converted_in_full(self) -> None:
        events = _check(
            """
            import syslog
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
            growth = []
            for n in (1_000, 100_000):
                message = 'é' * n
                before = sys.getsizeof(message)
                try:
                    syslog.syslog(syslog.LOG_DEBUG, message)
                except Blocked:
                    pass
                growth.append(sys.getsizeof(message) - before)
            assert growth == [2 * 1_000 + 1, 2 * 100_000 + 1], growth

            ascii_message = 'a' * 100_000
            before = sys.getsizeof(ascii_message)
            try:
                syslog.syslog(syslog.LOG_DEBUG, ascii_message)
            except Blocked:
                pass
            assert sys.getsizeof(ascii_message) == before
            """
        )
        sent = [args for event, args in events if event == "syslog.syslog"]
        assert [len(message) for _, message in sent] == [1_000, 100_000, 100_000]


@UNIX
class TestNullCharacter:
    """Version note: on 3.12+ a message containing a null character raises
    `ValueError`; earlier versions pass on the text before it."""

    def test_a_null_character_in_the_message(self) -> None:
        result, events = _run(
            """
            import syslog
            try:
                syslog.syslog('before\\0after')
            except Blocked:
                print('PASSED_ON')
            except ValueError as error:
                assert 'null character' in str(error)
                print('REJECTED')
            """
        )
        assert result.returncode == 0, result.stderr
        if sys.version_info >= (3, 12):
            assert "REJECTED" in result.stdout
            assert events == []
        else:
            assert "PASSED_ON" in result.stdout
            assert events == [["syslog.syslog", [syslog.LOG_INFO, "before"]]]


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
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


def _run_block(source: str) -> tuple[subprocess.CompletedProcess[str], list[Any]]:
    return _run(source, prelude=SWALLOW)


def _block(marker: str) -> tuple[int, str]:
    return next((line, source) for line, source in _blocks() if marker in source)


@UNIX
class TestDocumentedExamples:
    """Each block runs in its own subprocess under the harness, asserts its
    own result, and produces the events its comments describe."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import syslog" in source for _, source in blocks)

    def test_every_block_runs(self) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            result, _ = _run_block(source)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_sending_messages_opens_sends_and_closes(self) -> None:
        _, source = _block("'Started up'")
        result, events = _run_block(source)

        assert result.returncode == 0, result.stderr
        assert events == [
            ["syslog.openlog", ["myapp", syslog.LOG_PID, syslog.LOG_LOCAL0]],
            ["syslog.syslog", [syslog.LOG_INFO, "Started up"]],
            ["syslog.syslog", [syslog.LOG_ERR, "Something went wrong"]],
            ["syslog.syslog", [syslog.LOG_WARNING | syslog.LOG_AUTH, "Login failed"]],
            ["syslog.closelog", []],
        ]

    def test_priority_masks_still_hands_over_the_filtered_message(self) -> None:
        _, source = _block("'Filtered'")
        result, events = _run_block(source)

        assert result.returncode == 0, result.stderr
        sent = [args for event, args in events if event == "syslog.syslog"]
        assert sent == [[syslog.LOG_INFO, "Filtered"], [syslog.LOG_ERR, "Sent"]]

    def test_skipping_expensive_messages_sends_only_the_unfiltered_one(self) -> None:
        _, source = _block("def log_debug")
        result, events = _run_block(source)

        assert result.returncode == 0, result.stderr
        sent = [args for event, args in events if event == "syslog.syslog"]
        expected = "state: " + ", ".join(map(str, range(10_000)))
        assert sent == [[syslog.LOG_DEBUG, expected]]

    def test_the_runner_notices_a_broken_assertion(self) -> None:
        line, source = _block("assert built == [True]")
        mutated = source.replace("assert built == [True]", "assert built == []", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result, _ = _run_block(mutated)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
