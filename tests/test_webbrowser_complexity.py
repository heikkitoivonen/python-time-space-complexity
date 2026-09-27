"""Tests for docs/stdlib/webbrowser.md.

The page prices the module in controllers tried and `PATH` probes, and says
which controllers wait for the process they start. Nothing here starts a
browser: the registry is replaced per test, so `open()` only reaches recording
controllers, and the controllers that start processes run against a fake
`subprocess.Popen` that records how it was waited on, or against a Python
child process standing in for a browser. Discovery runs in a subprocess with a
controlled environment, so it starts from an empty registry and cannot read
the machine's real browsers.

Measurement scope:

* Discovery is counted in a subprocess with `PATH` set to empty directories
  and no display, `TERM` or `BROWSER` unless a test sets one. With `TERM` set,
  the first `get()` makes the same nonzero number of `shutil.which()` calls
  with 10 directories on `PATH` as with 1,000, and `os.path.exists()` is
  called at least 50x as often with 1,000 as with 10, which is the O(p). A
  second `get()` makes no `which()` call. With none of the three set there is
  no `which()` call; three `BROWSER` entries add exactly three. With `DISPLAY`
  set there are `which()` calls, and `subprocess.check_output()` runs once on
  the first `get()` and not on the second, with `xdg-settings` as its
  program; without a display it does not run. A `BROWSER` command line set
  after the first call is not found; set before it, it is. With `TERM` set,
  a `lynx` placed on `PATH` after discovery leaves `get()` raising `Error`,
  and a fresh discovery over the same `PATH` finds it.
* `open()` is observed on recording controllers: with 10 and 1,000 failing
  controllers it calls each exactly once and returns `False`; with a
  succeeding third of five it calls the first three once and the last two
  never; a failing controller is called again on every `open()`. The module's
  and a `BaseBrowser` subclass's `open_new()` and `open_new_tab()` are
  observed to pass `new` as 1 and 2.
* `get()` returns a registered instance by identity and makes no `which()`
  call; a constructor-only registration returns a new object per call; a
  command line returns a new object per call with no `which()` call; an
  unregistered name makes one `which()` call and raises `Error`, including a
  file that exists on `PATH` under a name nothing registered; the path to an
  executable whose file name is registered returns a controller whose `name`
  is that path. An empty preference order raises `Error`.
* `register()` is observed to put a `preferred` controller first and a
  non-preferred one last, via `get()` and via `open()` order. A timing test
  holds 1,000 and then 100,000 names in the preference order: a preferred
  registration costs more than 10x as much at the larger size, where a
  constant would give about 1x and a linear insert about 100x; a
  non-preferred one costs under 3x as much.
* Controller waiting is observed on a fake `Popen`. The text-mode browsers
  discovery registers (`lynx`, `w3m`, `links`) and a command line without `&`
  call `wait()` with no timeout; a command line with `&` and `xdg-open` call
  `poll()` and never `wait()`. The remote-capable browsers discovery registers
  for `firefox`, `google-chrome`, `chromium`, `opera` and `epiphany` call
  `wait(5)`: a timeout returns `True` after one process, a failure starts a
  second process that is polled and never waited on. A real command line
  whose child sleeps 0.3 s takes at least 0.3 s to return, and its exit
  status is the result.
* `controller.name` is read from a registered controller.
* `python -m webbrowser -t URL` is run with `BROWSER` naming a recording
  script, which is observed to receive the URL once.
* Every fenced Python block runs in its own subprocess without `BROWSER`, so
  registrations and discovery cannot leak between them, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The Windows and macOS controller rows. `os.startfile` and `osascript` exist
  on those platforms only; the row follows the official documentation, which
  says the caller does not wait for the user on non-Unix platforms. No run
  this project performs verifies it.
* Real browsers. Each process-starting controller is observed on a fake
  `Popen` or a Python stand-in, so the time a real browser takes to start,
  and whether a remote call to it succeeds, are not measured.
* That `-n` and `-t` pass 1 and 2 is read from `parse_args()` in
  Lib/webbrowser.py; the command-line test observes only that the URL
  reaches the browser.
* URL length, command-line length for `get(command_line)`, the number of
  `BROWSER` entries beyond three, and the `PATH` directory count for the
  lookup `get()` makes for an unregistered name are not varied. The page
  assumes a `BROWSER` of a few entries. Each lookup is `shutil.which()`,
  whose O(p) time and space are measured on the shutil page; the O(p) space
  in the discovery and `get()` rows follows from it and is not measured
  here.
* The iOS controller, and `xdg-settings` reporting a default browser, which
  needs a desktop session. Discovery with `WAYLAND_DISPLAY` and no `DISPLAY`,
  and `BROWSER` entries naming a browser discovery already registered, are
  not exercised.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import webbrowser
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "webbrowser.md"
EXPECTED_BLOCKS = 4
URL = "https://www.example.com"


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 50) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


class Recorder(webbrowser.BaseBrowser):
    """A controller that records calls instead of starting a browser."""

    def __init__(self, name: str, succeeds: bool = True) -> None:
        super().__init__(name)
        self.succeeds = succeeds
        self.calls: list[tuple[str, int]] = []

    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        self.calls.append((url, new))
        return self.succeeds


class FakePopen:
    """Records each process start and how the caller waited on it."""

    started: list[FakePopen] = []
    exit_status: int | None = 0

    def __init__(self, args: list[str], **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.waits: list[float | None] = []
        self.polls = 0
        FakePopen.started.append(self)

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        if FakePopen.exit_status is None:
            raise subprocess.TimeoutExpired(self.args, timeout or 0)
        return FakePopen.exit_status

    def poll(self) -> int | None:
        self.polls += 1
        return None


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """An empty registry with discovery already done, restored afterwards."""
    monkeypatch.setattr(webbrowser, "_tryorder", [])
    monkeypatch.setattr(webbrowser, "_browsers", {})
    monkeypatch.setattr(webbrowser, "_os_preferred_browser", None)
    yield


@pytest.fixture
def fake_popen(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[FakePopen]]:
    FakePopen.started = []
    FakePopen.exit_status = 0
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    yield FakePopen


@pytest.fixture
def which_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    real = shutil.which

    def counting(cmd: str, *args: Any, **kwargs: Any) -> str | None:
        calls.append(cmd)
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", counting)
    return calls


def _executables(directory: pathlib.Path, names: list[str]) -> pathlib.Path:
    directory.mkdir(exist_ok=True)
    for name in names:
        path = directory / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return directory


def _discover(monkeypatch: pytest.MonkeyPatch, bin_dir: pathlib.Path, **env: str) -> None:
    """Run discovery from scratch against `bin_dir` alone."""
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "BROWSER", "TERM"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PATH", str(bin_dir))
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(webbrowser, "_tryorder", None)
    monkeypatch.setattr(webbrowser, "_browsers", {})
    monkeypatch.setattr(webbrowser, "_os_preferred_browser", None)

    def no_xdg_settings(*args: Any, **kwargs: Any) -> bytes:
        raise FileNotFoundError("xdg-settings")

    monkeypatch.setattr(subprocess, "check_output", no_xdg_settings)
    with pytest.raises(webbrowser.Error):
        webbrowser.get("no-such-browser")  # discovery runs first


DISCOVERY_PROBE = """
import json, os, os.path, shutil, subprocess, sys, webbrowser

counts = {"which": 0, "exists": 0, "check_output": []}
real_which, real_exists, real_check = shutil.which, os.path.exists, subprocess.check_output

def which(cmd, *a, **k):
    counts["which"] += 1
    return real_which(cmd, *a, **k)

def exists(path):
    counts["exists"] += 1
    return real_exists(path)

def check_output(cmd, *a, **k):
    counts["check_output"].append(list(cmd))
    return real_check(cmd, *a, **k)

shutil.which, os.path.exists, subprocess.check_output = which, exists, check_output

result = {}
for label in ("first", "second"):
    before = {"which": counts["which"], "exists": counts["exists"],
              "check_output": len(counts["check_output"])}
    try:
        webbrowser.get()
        found = True
    except webbrowser.Error:
        found = False
    if label == "first" and len(sys.argv) > 1:
        os.environ["BROWSER"] = sys.argv[1]
    result[label] = {
        "which": counts["which"] - before["which"],
        "exists": counts["exists"] - before["exists"],
        "check_output": len(counts["check_output"]) - before["check_output"],
        "found": found,
    }
result["commands"] = counts["check_output"]
print(json.dumps(result))
"""


def _run_discovery(
    tmp_path: pathlib.Path,
    path_dirs: int,
    extra_env: dict[str, str] | None = None,
    browser_after_first: str | None = None,
) -> dict[str, Any]:
    root = pathlib.Path(tempfile.mkdtemp(dir=tmp_path))
    dirs = []
    for index in range(path_dirs):
        directory = root / f"path{index}"
        directory.mkdir()
        dirs.append(str(directory))
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DISPLAY", "WAYLAND_DISPLAY", "BROWSER", "TERM"}
    }
    env["PATH"] = os.pathsep.join(dirs)
    env.update(extra_env or {})
    argv = [sys.executable, "-c", DISCOVERY_PROBE]
    if browser_after_first is not None:
        argv.append(browser_after_first)
    result = subprocess.run(
        argv,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=True,
    )
    return json.loads(result.stdout)


class TestDiscoveryRunsOnce:
    """Browser discovery: O(p) once per process, a lookup per known name and
    per `BROWSER` entry, one `xdg-settings` run with a display, and nothing
    seen afterwards. The contrast is the same probe run twice in one process,
    and at two `PATH` lengths."""

    def test_a_second_call_looks_nothing_up(self, tmp_path: pathlib.Path) -> None:
        counts = _run_discovery(tmp_path, 3, {"TERM": "xterm"})

        assert counts["first"]["which"] > 0
        assert counts["second"]["which"] == 0
        assert counts["second"]["exists"] == 0

    def test_the_probes_follow_the_path_length(self, tmp_path: pathlib.Path) -> None:
        short = _run_discovery(tmp_path, 10, {"TERM": "xterm"})
        long = _run_discovery(tmp_path, 1_000, {"TERM": "xterm"})

        assert short["first"]["which"] == long["first"]["which"]
        ratio = long["first"]["exists"] / short["first"]["exists"]
        assert ratio >= 50, (
            f"{short['first']['exists']} probes over 10 PATH directories and "
            f"{long['first']['exists']} over 1,000: x{ratio:.1f}"
        )

    def test_each_browser_entry_adds_one_lookup(self, tmp_path: pathlib.Path) -> None:
        entries = os.pathsep.join(["no-such-a", "no-such-b", "no-such-c %s"])
        plain = _run_discovery(tmp_path, 3)
        with_entries = _run_discovery(tmp_path, 3, {"BROWSER": entries})

        assert with_entries["first"]["which"] == plain["first"]["which"] + 3

    def test_a_display_runs_xdg_settings_once(self, tmp_path: pathlib.Path) -> None:
        counts = _run_discovery(tmp_path, 3, {"DISPLAY": ":99"})

        assert counts["first"]["check_output"] == 1
        assert counts["first"]["which"] > 0
        assert counts["second"]["check_output"] == 0
        assert counts["commands"][0][0] == "xdg-settings"

    def test_no_display_and_no_terminal_look_nothing_up(self, tmp_path: pathlib.Path) -> None:
        counts = _run_discovery(tmp_path, 3)

        assert counts["first"]["check_output"] == 0
        assert counts["first"]["which"] == 0

    def test_browser_set_after_discovery_is_not_seen(self, tmp_path: pathlib.Path) -> None:
        command = shlex.join([sys.executable, "-c", "pass"]) + " %s"
        late = _run_discovery(tmp_path, 3, browser_after_first=command)
        early = _run_discovery(tmp_path, 3, {"BROWSER": command})

        assert late["first"]["found"] is False
        assert late["second"]["found"] is False
        assert early["first"]["found"] is True


@pytest.mark.usefixtures("registry")
class TestOpenWalksThePreferenceOrder:
    """`open()`: O(b), stopping at the first success, remembering nothing.
    Counting calls on recording controllers separates one attempt per
    controller from a single attempt or a retry loop."""

    def test_it_stops_at_the_first_success(self) -> None:
        controllers = [Recorder(f"r{i}", succeeds=(i == 2)) for i in range(5)]
        for controller in controllers:
            webbrowser.register(controller.name, None, controller)

        assert webbrowser.open(URL) is True
        assert [len(c.calls) for c in controllers] == [1, 1, 1, 0, 0]

    @pytest.mark.parametrize("size", [10, 1_000])
    def test_every_failing_controller_is_tried_once(self, size: int) -> None:
        controllers = [Recorder(f"r{i}", succeeds=False) for i in range(size)]
        for controller in controllers:
            webbrowser.register(controller.name, None, controller)

        assert webbrowser.open(URL) is False
        assert all(c.calls == [(URL, 0)] for c in controllers)

    def test_a_failing_controller_is_tried_on_every_call(self) -> None:
        failing = Recorder("failing", succeeds=False)
        fallback = Recorder("fallback")
        webbrowser.register("failing", None, failing)
        webbrowser.register("fallback", None, fallback)

        for _ in range(3):
            assert webbrowser.open(URL) is True
        assert len(failing.calls) == 3
        assert len(fallback.calls) == 3

    def test_a_controller_s_open_new_and_open_new_tab_pass_1_and_2(self) -> None:
        recorder = Recorder("recorder")

        assert recorder.open_new(URL) is True
        assert recorder.open_new_tab(URL) is True
        assert recorder.calls == [(URL, 1), (URL, 2)]

    def test_open_new_and_open_new_tab_ask_for_a_window_and_a_tab(self) -> None:
        recorder = Recorder("recorder")
        webbrowser.register("recorder", None, recorder)

        assert webbrowser.open_new(URL) is True
        assert webbrowser.open_new_tab(URL) is True
        assert recorder.calls == [(URL, 1), (URL, 2)]


@pytest.mark.usefixtures("registry")
class TestGetLooksUpWithoutProbing:
    """`get()`: O(1) for a registered name or a command line, a `PATH`
    lookup only for a name nothing registered. Identity and a `which()`
    counter separate returning the registered object from building one."""

    def test_a_registered_instance_comes_back_as_itself(self, which_calls: list[str]) -> None:
        recorder = Recorder("recorder")
        webbrowser.register("recorder", None, recorder)

        assert webbrowser.get("recorder") is recorder
        assert webbrowser.get("RECORDER") is recorder
        assert webbrowser.get("recorder").name == "recorder"
        assert which_calls == []

    def test_none_is_the_first_in_preference_order(self) -> None:
        first, second = Recorder("first"), Recorder("second")
        webbrowser.register("first", None, first)
        webbrowser.register("second", None, second)

        assert webbrowser.get() is first

    def test_a_constructor_is_called_on_every_get(self) -> None:
        webbrowser.register("built", lambda: Recorder("built"))

        one, two = webbrowser.get("built"), webbrowser.get("built")
        assert isinstance(one, Recorder)
        assert one is not two

    def test_a_command_line_builds_a_new_controller_each_call(self, which_calls: list[str]) -> None:
        one = webbrowser.get("some-browser %s")
        two = webbrowser.get("some-browser %s")

        assert one is not two
        assert one.name == "some-browser"
        assert which_calls == []

    def test_an_unregistered_name_is_looked_up_and_raises(self, which_calls: list[str]) -> None:
        with pytest.raises(webbrowser.Error, match="could not locate runnable browser"):
            webbrowser.get("no-such-browser")
        assert which_calls == ["no-such-browser"]

    def test_a_program_on_path_that_nothing_registered_raises(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bin_dir = _executables(tmp_path / "bin", ["some-program"])
        monkeypatch.setenv("PATH", str(bin_dir))

        with pytest.raises(webbrowser.Error):
            webbrowser.get("some-program")

    def test_a_path_to_a_registered_browser_is_found(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bin_dir = _executables(tmp_path / "bin", ["mybrowser"])
        monkeypatch.setenv("PATH", str(bin_dir))
        webbrowser.register("mybrowser", None, webbrowser.GenericBrowser("mybrowser"))
        path = str(bin_dir / "mybrowser")

        assert webbrowser.get(path).name == path

    def test_an_empty_order_raises(self) -> None:
        with pytest.raises(webbrowser.Error):
            webbrowser.get()


@pytest.mark.usefixtures("registry")
class TestRegisterAppendsOrInserts:
    """`register()`: O(1) amortized appended, O(b) with `preferred`, which
    inserts at the front of the preference order."""

    def test_preferred_goes_first_and_the_rest_go_last(self) -> None:
        first, last, front = Recorder("first"), Recorder("last"), Recorder("front")
        webbrowser.register("first", None, first)
        webbrowser.register("last", None, last)
        webbrowser.register("front", None, front, preferred=True)

        assert webbrowser.get() is front
        front.succeeds = first.succeeds = False
        assert webbrowser.open(URL) is True
        assert (len(front.calls), len(first.calls), len(last.calls)) == (1, 1, 1)

    @pytest.mark.timing
    def test_only_a_preferred_registration_grows_with_the_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        controller = Recorder("x")

        def cost(size: int, preferred: bool) -> float:
            monkeypatch.setattr(webbrowser, "_tryorder", [f"n{i}" for i in range(size)])
            return best_ns(lambda: webbrowser.register("x", None, controller, preferred=preferred))

        preferred_ratio = cost(100_000, True) / cost(1_000, True)
        appended_ratio = cost(100_000, False) / cost(1_000, False)

        assert preferred_ratio > 10, f"preferred x{preferred_ratio:.1f} for 100x the order"
        assert appended_ratio < 3, f"appended x{appended_ratio:.1f} for 100x the order"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="X11 and console discovery")
@pytest.mark.usefixtures("registry")
class TestControllersWaitOrNot:
    """The controller rows: text-mode browsers and command lines without `&`
    wait for their process, background ones do not, and remote-capable ones
    wait at most five seconds. A fake `Popen` records whether `wait()` was
    called and with what timeout."""

    @pytest.mark.parametrize("name", ["lynx", "w3m", "links"])
    def test_a_text_mode_browser_waits_without_a_timeout(
        self,
        name: str,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_popen: type[FakePopen],
    ) -> None:
        _discover(monkeypatch, _executables(tmp_path / "bin", [name]), TERM="xterm")

        assert webbrowser.get(name).open(URL) is True
        [process] = fake_popen.started
        assert process.waits == [None]

    def test_a_command_line_without_ampersand_waits(self, fake_popen: type[FakePopen]) -> None:
        fake_popen.exit_status = 3

        assert webbrowser.get("some-browser %s").open(URL) is False
        [process] = fake_popen.started
        assert process.args == ["some-browser", URL]
        assert process.waits == [None]

    def test_a_command_line_with_ampersand_does_not_wait(self, fake_popen: type[FakePopen]) -> None:
        assert webbrowser.get("some-browser %s &").open(URL) is True
        [process] = fake_popen.started
        assert process.waits == []
        assert process.polls == 1

    def test_xdg_open_does_not_wait(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_popen: type[FakePopen],
    ) -> None:
        _discover(monkeypatch, _executables(tmp_path / "bin", ["xdg-open"]), DISPLAY=":99")

        assert webbrowser.get("xdg-open").open(URL) is True
        [process] = fake_popen.started
        assert process.waits == []
        assert process.polls == 1

    @pytest.mark.parametrize("name", ["firefox", "google-chrome", "chromium", "opera", "epiphany"])
    def test_a_remote_capable_browser_waits_at_most_five_seconds(
        self,
        name: str,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_popen: type[FakePopen],
    ) -> None:
        _discover(monkeypatch, _executables(tmp_path / "bin", [name]), DISPLAY=":99")
        controller = webbrowser.get(name)

        fake_popen.exit_status = None  # still running after the timeout
        assert controller.open(URL) is True
        [process] = fake_popen.started
        assert process.waits == [5]

        fake_popen.started = []
        fake_popen.exit_status = 1  # the remote call failed
        assert controller.open(URL) is True
        remote, direct = fake_popen.started
        assert remote.waits == [5]
        assert direct.waits == []
        assert direct.polls == 1

    def test_a_browser_installed_after_discovery_is_not_seen(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bin_dir = _executables(tmp_path / "bin", [])
        _discover(monkeypatch, bin_dir, TERM="xterm")
        _executables(bin_dir, ["lynx"])

        with pytest.raises(webbrowser.Error):
            webbrowser.get()

        _discover(monkeypatch, bin_dir, TERM="xterm")
        assert webbrowser.get().name == "lynx"

    def test_a_blocking_command_line_returns_after_its_process(self) -> None:
        sleeps = shlex.join([sys.executable, "-c", "import time; time.sleep(0.3)"])
        exits_3 = shlex.join([sys.executable, "-c", "import sys; sys.exit(3)"])

        start = time.perf_counter()
        assert webbrowser.get(sleeps + " %s").open(URL) is True
        assert time.perf_counter() - start >= 0.3
        assert webbrowser.get(exits_3 + " %s").open(URL) is False


class TestCommandLineInterface:
    """`python -m webbrowser -t URL` makes one `open()` call."""

    def test_the_url_reaches_the_browser_once(self, tmp_path: pathlib.Path) -> None:
        log = tmp_path / "log.txt"
        recorder = tmp_path / "record.py"
        recorder.write_text(
            f"import sys\nwith open({str(log)!r}, 'a') as f:\n    f.write(sys.argv[1] + '\\n')\n",
            encoding="utf-8",
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"DISPLAY", "WAYLAND_DISPLAY", "TERM"}
        }
        env["PATH"] = str(tmp_path)
        env["BROWSER"] = shlex.join([sys.executable, str(recorder)]) + " %s"

        subprocess.run(
            [sys.executable, "-m", "webbrowser", "-t", URL],
            env=env,
            capture_output=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        )

        assert log.read_text(encoding="utf-8").splitlines() == [URL]


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


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "BROWSER"}
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so registrations and discovery
    cannot leak between them, and asserts its own result. The blocks that
    call `webbrowser.open()` register a recording controller first in the
    preference order, and the rest call only controllers they built, so no
    block starts a browser."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "len(failing.calls) == 2" in s)
        mutated = source.replace("len(failing.calls) == 2", "len(failing.calls) == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
