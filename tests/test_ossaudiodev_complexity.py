"""Tests for docs/stdlib/ossaudiodev.md.

The page prices the bytes `read()`, `write()` and `writeall()` move and
counts every other call as a fixed number of system calls; waiting for the
device is outside every bound. The module exists on Python 3.10 to 3.12, and
the uv-installed 3.10.21, 3.11.16 and 3.12.14 builds have it, but this machine
has no OSS device, and `open()` raises unless its file answers the
`SNDCTL_DSP_GETFMTS` ioctl. So an audio device object cannot be made here,
and everything about one is read from `Modules/ossaudiodev.c`. A mixer can be
opened on `/dev/null`, because `openmixer()` makes no ioctl, and everything
the module checks before it reaches the device is run against the real module
through that. Tests touching the real module take the `ossaudiodev` fixture,
which skips from 3.13 and off Linux and FreeBSD; run them with one of those
interpreters. The C file
differs between v3.10.19, v3.11.14 and v3.12.12 in the import-time
DeprecationWarning added in 3.11, in `setparameters()` parsing `strict` as a
truth value from 3.12 rather than an `int`, and in changes that move no bound.

Measurement scope:

* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* `open()`: a mode other than `'r'`, `'w'` or `'rw'` raises `OSSAudioError`
  even when the device does not exist, so the mode is checked first; a
  missing device raises `FileNotFoundError` naming it; with one argument the
  path comes from `AUDIODEV`; `/dev/null`, which is not an audio device,
  raises `OSError` from `open()` itself. `open()` and `openmixer()` reject
  keyword arguments, and `openmixer(None)` raises `TypeError`.
* `openmixer()`: `/dev/null` opens, and `controls()`, `stereocontrols()`,
  `reccontrols()`, `get_recsrc()`, `set_recsrc()`, and `get()` and `set()`
  on a valid control then raise `OSError`; without an argument the path
  comes from `MIXERDEV`. `get()` and `set()` with control -1 or
  `SOUND_MIXER_NRDEVICES + 1`, and `set()` with a volume of 101 or -1, raise
  `OSSAudioError` on that same file, so those checks precede the ioctl;
  `get(SOUND_MIXER_NRDEVICES)` passes the check and raises `OSError`.
  After `close()`, a second `close()` returns `None`, and `fileno()` and every
  control call raise `ValueError`; a `with` block returns the mixer itself
  and closes it on exit.
* `OSSAudioError` is `error`, an `Exception` and not an `OSError`.
  `control_labels` and `control_names` each have `SOUND_MIXER_NRDEVICES`
  entries, and `control_names[SOUND_MIXER_PCM]` is `'pcm'`. The `AFMT_*`,
  `SOUND_MIXER_*` and `SNDCTL_*` names are `int`s.
* Every fenced Python block runs in its own subprocess and working directory
  with a stand-in `ossaudiodev` put in `sys.modules` before it runs, since
  3.10 to 3.12 build the real one in and would import it ahead of anything on
  `sys.path`. A mutated assertion in one block, and dropping the scaling of
  `obuffree()` to bytes in another, are each asserted to make it fail; the
  stand-in's buffer holds 4,096 bytes, exactly the chunk that block writes,
  so an unscaled comparison skips the write, which a check appended to the
  block detects. On 3.10 to 3.12 the stand-in is
  checked against the real module: every name it defines exists there, with
  the same value for the constants; its two device classes' methods exist on
  the real `oss_audio_device` and `oss_mixer_device`; and its mode and
  volume errors carry the real messages. The stand-in counts `obuffree()`
  in samples, as the source does. It shows that each block's own Python is
  sound; it says nothing about a device.

Not settled here (source-only, `Modules/ossaudiodev.c` at v3.12.12, or the
official documentation where the driver decides):

* `read(size)` allocates a `size`-byte object before one `read()` system
  call and shrinks it to what was read; that a blocking read waits for all
  `size` bytes is the driver's behaviour, as the official documentation
  states it. `write()` is one `write()` system call from the caller's buffer,
  which is not copied; `writeall()` loops `select()` and `write()` over the
  same buffer until it is consumed. That a blocking `write()` takes all the
  data is the driver's, per the documentation.
* `setfmt()`, `channels()`, `speed()`, `getfmts()`, `nonblock()`, `sync()`,
  `reset()` and `post()` are one ioctl each; `setparameters()` is three,
  returns the three values the ioctls left, and raises `OSSAudioError` under
  `strict` when one comes back changed; `writeall()` returns `None`. Every
  method and both functions are `METH_VARARGS` or `METH_NOARGS`, so they take
  no keywords;
  `bufsize()`, `obufcount()` and `obuffree()` are three each and divide a
  byte count by the sample width times the channel count, so they count
  samples per channel. `open()` makes one `open()`, one `fcntl()` and one
  ioctl, and falls back to `/dev/dsp` without `AUDIODEV`; `openmixer()` falls
  back to `/dev/mixer` without `MIXERDEV`. Neither default is opened here,
  as a machine with an OSS device would open it. The audio device's
  `close()` is idempotent, its `__exit__` calls it, and `fileno()` and every
  ioctl or transfer method check the descriptor first and raise
  `ValueError`; `closed`, `name` and `mode` are read-only.
* What waiting costs, that `sync()` returns once the buffer has played and
  that `close()` waits for it too, that `reset()` discards what is buffered,
  that `post()` tells the driver a pause is likely, that a write within `obuffree()` does not wait, that `nonblock()` cannot
  be undone, the meaning of each control's bit, and the volume a device
  actually sets: the driver's, per the official documentation.
* `oss_audio_device.flush()`, an alias of `sync()`, and
  `oss_audio_device.getptr()` exist but are not in the official API inventory
  or the documentation, so the page leaves them out.
* The official documentation gives the module's platforms as Linux and
  FreeBSD, and the tests that touch it skip elsewhere. `configure.ac` builds
  it wherever an OSS `soundcard.h` is found, except on macOS; that is a build
  fact, not run. The page-scoped audit run on
  3.12.14 reports no missing names. Its device members are listed as
  unresolved because the two device types are not module attributes, and
  `control_labels` and `control_names` as needing classification because
  the official inventory omits them; the page prices all of them. The 3.13
  and later inventories have no `ossaudiodev` names.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ossaudiodev.md"
EXPECTED_BLOCKS = 4

STAND_IN = '''
"""A stand-in for the ossaudiodev module, following Modules/ossaudiodev.c."""

AFMT_S16_LE = 16
SOUND_MIXER_NRDEVICES = 25
SOUND_MIXER_PCM = 4
control_names = [
    "vol", "bass", "treble", "synth", "pcm", "speaker", "line", "mic", "cd", "mix",
    "pcm2", "rec", "igain", "ogain", "line1", "line2", "line3", "dig1", "dig2", "dig3",
    "phin", "phout", "video", "radio", "monitor",
]
control_labels = [name.capitalize() for name in control_names]


class OSSAudioError(Exception):
    pass


error = OSSAudioError

_BUFFER_BYTES = 4096


class _Device:
    def __init__(self, fd):
        self._fd = fd

    def _check(self):
        if self._fd < 0:
            raise ValueError("Operation on closed OSS device.")

    def fileno(self):
        self._check()
        return self._fd

    def close(self):
        self._fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


class oss_audio_device(_Device):
    def __init__(self, name, mode):
        super().__init__(3)
        self.name = name
        self.mode = mode
        self._fmt, self._channels, self._rate = AFMT_S16_LE, 1, 8000
        self._queued = 0

    @property
    def closed(self):
        return self._fd == -1

    def setparameters(self, format, nchannels, samplerate, strict=False, /):
        self._check()
        self._fmt, self._channels, self._rate = format, nchannels, samplerate
        return (format, nchannels, samplerate)

    def _frame(self):
        return 2 * self._channels

    def obuffree(self):
        self._check()
        return (_BUFFER_BYTES - self._queued) // self._frame()

    def write(self, data, /):
        self._check()
        if "w" not in self.mode:
            raise OSError(9, "Bad file descriptor")
        self._queued = min(_BUFFER_BYTES, self._queued + len(data))
        return len(data)

    def writeall(self, data, /):
        self.write(data)

    def sync(self):
        self._check()
        self._queued = 0

    def read(self, size, /):
        self._check()
        if "r" not in self.mode:
            raise OSError(9, "Bad file descriptor")
        return bytes(size)


class oss_mixer_device(_Device):
    def __init__(self):
        super().__init__(4)
        self._volumes = {SOUND_MIXER_PCM: (75, 75)}

    def _control(self, control):
        self._check()
        if control < 0 or control > SOUND_MIXER_NRDEVICES:
            raise OSSAudioError("Invalid mixer channel specified.")

    def controls(self):
        self._check()
        mask = 0
        for control in self._volumes:
            mask |= 1 << control
        return mask

    def get(self, control, /):
        self._control(control)
        return self._volumes[control]

    def set(self, control, volumes, /):
        self._control(control)
        left, right = volumes
        if not (0 <= left <= 100 and 0 <= right <= 100):
            raise OSSAudioError("Volumes must be between 0 and 100.")
        self._volumes[control] = (left, right)
        return (left, right)


def open(device, mode=None, /):
    if mode is None:
        device, mode = None, device
    if mode not in ("r", "w", "rw"):
        raise OSSAudioError("mode must be 'r', 'w', or 'rw'")
    return oss_audio_device(device or "/dev/dsp", mode)


def openmixer(*device):
    if len(device) > 1 or (device and not isinstance(device[0], str)):
        raise TypeError("openmixer() takes one optional str argument")
    return oss_mixer_device()
'''


# The platforms the official documentation gives for the module.
DOCUMENTED_PLATFORM = sys.platform.startswith(("linux", "freebsd"))


@pytest.fixture
def ossaudiodev() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: ossaudiodev was removed in Python 3.13")
    if not DOCUMENTED_PLATFORM:
        pytest.skip("platform: ossaudiodev is documented for Linux and FreeBSD only")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("ossaudiodev")


@pytest.fixture
def mixer(ossaudiodev: Any) -> Iterator[Any]:
    """A real mixer object on /dev/null, which answers no ioctl."""
    device = ossaudiodev.openmixer(os.devnull)
    yield device
    device.close()


def _real_type(name: str) -> type:
    return next(
        t for t in object.__subclasses__() if t.__module__ == "ossaudiodev" and t.__name__ == name
    )


class TestAvailability:
    """`import ossaudiodev` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError) as caught:
            importlib.import_module("ossaudiodev")
        assert caught.value.name == "ossaudiodev"

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="ossaudiodev was removed in 3.13")
    @pytest.mark.skipif(not DOCUMENTED_PLATFORM, reason="documented for Linux and FreeBSD only")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import ossaudiodev"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "ossaudiodev" in result.stderr


class TestOpen:
    """`ossaudiodev.open(mode)`, `open(device, mode)` | O(1): the mode is
    checked before the device is touched, the one-argument form reads
    `AUDIODEV`, and a file that is not an audio device fails here."""

    def test_a_bad_mode_is_rejected_before_the_device_is_opened(
        self, ossaudiodev: Any, tmp_path: pathlib.Path
    ) -> None:
        missing = str(tmp_path / "no-such-device")
        with pytest.raises(ossaudiodev.OSSAudioError, match="mode must be"):
            ossaudiodev.open(missing, "x")

    def test_a_missing_device_raises_file_not_found(
        self, ossaudiodev: Any, tmp_path: pathlib.Path
    ) -> None:
        missing = str(tmp_path / "no-such-device")
        with pytest.raises(FileNotFoundError) as caught:
            ossaudiodev.open(missing, "w")
        assert caught.value.filename == missing

    def test_one_argument_reads_audiodev(
        self, ossaudiodev: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = str(tmp_path / "audiodev")
        monkeypatch.setenv("AUDIODEV", missing)
        with pytest.raises(FileNotFoundError) as caught:
            ossaudiodev.open("w")
        assert caught.value.filename == missing

    def test_a_file_that_is_not_an_audio_device_fails_at_open(self, ossaudiodev: Any) -> None:
        with pytest.raises(OSError) as caught:
            ossaudiodev.open(os.devnull, "w")
        assert not isinstance(caught.value, FileNotFoundError)
        assert caught.value.filename == os.devnull


class TestOpenMixer:
    """`ossaudiodev.openmixer(device=None)` | O(1): any readable and writable
    file opens; the first control call is what fails on a non-mixer."""

    def test_a_non_mixer_opens_and_fails_at_the_first_control(self, mixer: Any) -> None:
        assert mixer.fileno() >= 0
        for call in (
            mixer.controls,
            mixer.stereocontrols,
            mixer.reccontrols,
            mixer.get_recsrc,
            lambda: mixer.set_recsrc(1),
            lambda: mixer.get(0),
            lambda: mixer.set(0, (50, 50)),
        ):
            with pytest.raises(OSError):
                call()

    def test_arguments_are_positional_only(self, ossaudiodev: Any) -> None:
        with pytest.raises(TypeError, match="keyword"):
            ossaudiodev.openmixer(device=os.devnull)
        with pytest.raises(TypeError, match="keyword"):
            ossaudiodev.open(device=os.devnull, mode="w")
        with pytest.raises(TypeError):
            ossaudiodev.openmixer(None)

    def test_no_argument_reads_mixerdev(
        self, ossaudiodev: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = str(tmp_path / "mixerdev")
        monkeypatch.setenv("MIXERDEV", missing)
        with pytest.raises(FileNotFoundError) as caught:
            ossaudiodev.openmixer()
        assert caught.value.filename == missing


class TestMixerChecksBeforeTheDevice:
    """`get(control)` and `set(control, (left, right))` raise `OSSAudioError`
    for a control number or a volume out of range. On `/dev/null` any ioctl
    raises `OSError`, so an `OSSAudioError` shows the check came first."""

    @pytest.mark.parametrize("control", [-1, 26])
    @pytest.mark.parametrize("call", ["get", "set"])
    def test_a_control_out_of_range_is_rejected(
        self, ossaudiodev: Any, mixer: Any, control: int, call: str
    ) -> None:
        assert ossaudiodev.SOUND_MIXER_NRDEVICES + 1 == 26
        with pytest.raises(ossaudiodev.OSSAudioError, match="Invalid mixer channel"):
            if call == "get":
                mixer.get(control)
            else:
                mixer.set(control, (50, 50))

    def test_sound_mixer_nrdevices_itself_reaches_the_device(
        self, ossaudiodev: Any, mixer: Any
    ) -> None:
        """The check rejects only numbers above `SOUND_MIXER_NRDEVICES`, so
        that number itself is passed to the ioctl, which `/dev/null` fails."""
        with pytest.raises(OSError):
            mixer.get(ossaudiodev.SOUND_MIXER_NRDEVICES)

    @pytest.mark.parametrize("volume", [(101, 0), (0, 101), (-1, 50)])
    def test_set_rejects_a_volume_out_of_range(
        self, ossaudiodev: Any, mixer: Any, volume: tuple[int, int]
    ) -> None:
        with pytest.raises(ossaudiodev.OSSAudioError, match="between 0 and 100"):
            mixer.set(ossaudiodev.SOUND_MIXER_PCM, volume)


class TestClosingTheMixer:
    """`oss_mixer_device.close()`: a second call does nothing, a `with` block
    calls it, and `fileno()` and every control call then raise
    `ValueError`."""

    def test_close_is_idempotent_and_later_calls_raise(self, ossaudiodev: Any) -> None:
        mixer = ossaudiodev.openmixer(os.devnull)
        assert mixer.close() is None
        assert mixer.close() is None
        for call in (
            mixer.fileno,
            mixer.controls,
            mixer.stereocontrols,
            mixer.reccontrols,
            mixer.get_recsrc,
            lambda: mixer.set_recsrc(1),
            lambda: mixer.get(0),
            lambda: mixer.set(0, (50, 50)),
        ):
            with pytest.raises(ValueError, match="closed OSS device"):
                call()

    def test_a_with_block_closes_it(self, ossaudiodev: Any) -> None:
        mixer = ossaudiodev.openmixer(os.devnull)
        with mixer as entered:
            assert entered is mixer
            assert mixer.fileno() >= 0
        with pytest.raises(ValueError):
            mixer.fileno()


class TestConstantsAndExceptions:
    """`OSSAudioError` and `error` are one class; `control_labels` and
    `control_names` are indexed by control number; the constants are ints."""

    def test_error_is_one_class_under_two_names(self, ossaudiodev: Any) -> None:
        assert ossaudiodev.error is ossaudiodev.OSSAudioError
        assert issubclass(ossaudiodev.OSSAudioError, Exception)
        assert not issubclass(ossaudiodev.OSSAudioError, OSError)

    def test_the_name_lists_have_one_entry_per_control(self, ossaudiodev: Any) -> None:
        count = ossaudiodev.SOUND_MIXER_NRDEVICES
        assert len(ossaudiodev.control_labels) == count
        assert len(ossaudiodev.control_names) == count
        assert ossaudiodev.control_names[ossaudiodev.SOUND_MIXER_PCM] == "pcm"

    def test_the_constants_are_ints(self, ossaudiodev: Any) -> None:
        prefixes = ("AFMT_", "SOUND_MIXER_", "SNDCTL_")
        names = [name for name in dir(ossaudiodev) if name.startswith(prefixes)]
        assert {name.split("_")[0] for name in names} == {"AFMT", "SOUND", "SNDCTL"}
        assert all(type(getattr(ossaudiodev, name)) is int for name in names)


def _load_stand_in(tmp_path: pathlib.Path) -> Any:
    path = tmp_path / "stand_in_ossaudiodev.py"
    path.write_text(STAND_IN, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("stand_in_ossaudiodev", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheStandInFollowsTheModule:
    """The examples run against a stand-in. On 3.10 to 3.12 its names,
    constant values, device methods and error messages are checked against
    the real module, so a block cannot pass by calling something the module
    lacks."""

    def test_every_module_name_exists_with_the_same_value(
        self, ossaudiodev: Any, tmp_path: pathlib.Path
    ) -> None:
        stand_in = _load_stand_in(tmp_path)
        devices = {"oss_audio_device", "oss_mixer_device"}
        public = [n for n in vars(stand_in) if not n.startswith("_") and n not in devices]
        assert [name for name in public if not hasattr(ossaudiodev, name)] == []
        for name in public:
            if type(getattr(stand_in, name)) is int:
                assert getattr(stand_in, name) == getattr(ossaudiodev, name), name
        assert stand_in.control_names == ossaudiodev.control_names
        assert len(stand_in.control_labels) == len(ossaudiodev.control_labels)

    def test_every_device_method_exists_on_the_real_type(
        self, ossaudiodev: Any, tmp_path: pathlib.Path
    ) -> None:
        stand_in = _load_stand_in(tmp_path)
        for name in ("oss_audio_device", "oss_mixer_device"):
            real = _real_type(name)
            ours = [n for n in dir(getattr(stand_in, name)) if not n.startswith("_")]
            assert ours
            assert [n for n in ours if not hasattr(real, n)] == [], name
            assert hasattr(real, "__enter__") and hasattr(real, "__exit__")

    def test_the_error_messages_match(
        self, ossaudiodev: Any, mixer: Any, tmp_path: pathlib.Path
    ) -> None:
        stand_in = _load_stand_in(tmp_path)
        pairs = [
            (lambda m: m.open(str(tmp_path / "x"), "x"), None),
            (lambda m: m.openmixer().set(4, (101, 0)), lambda: mixer.set(4, (101, 0))),
            (lambda m: m.openmixer().get(-1), lambda: mixer.get(-1)),
        ]
        for ours, real in pairs:
            with pytest.raises(stand_in.OSSAudioError) as fake_error:
                ours(stand_in)
            with pytest.raises(ossaudiodev.OSSAudioError) as real_error:
                if real is None:
                    ours(ossaudiodev)
                else:
                    real()
            assert str(fake_error.value) == str(real_error.value)


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
    stand_in = cwd / "stand_in"
    stand_in.mkdir()
    (stand_in / "ossaudiodev.py").write_text(STAND_IN, encoding="utf-8")
    script = cwd / "block.py"
    # The interpreters that still have the module build it in, and a built-in
    # module is found before anything on sys.path, so the prelude puts the
    # stand-in in sys.modules instead.
    prelude = (
        "import importlib.util, sys\n"
        f"_spec = importlib.util.spec_from_file_location('ossaudiodev', {str(stand_in / 'ossaudiodev.py')!r})\n"
        "sys.modules['ossaudiodev'] = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(sys.modules['ossaudiodev'])\n"
        "del _spec\n"
    )
    script.write_text(prelude + source)
    return subprocess.run(
        [sys.executable, "-I", "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess against the stand-in, and
    asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import ossaudiodev" in source for _, source in blocks)

    def test_the_stand_in_is_the_module_the_blocks_import(self, tmp_path: pathlib.Path) -> None:
        result = _run_block(
            "import ossaudiodev, pathlib\n"
            "assert pathlib.Path(ossaudiodev.__file__).parent.name == 'stand_in'\n",
            tmp_path,
        )
        assert result.returncode == 0, result.stderr

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
        line, source = next((n, s) for n, s in _blocks() if "len(audio) == 10 * 4096" in s)
        mutated = source.replace("len(audio) == 10 * 4096", "len(audio) == 9 * 4096", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr

    def test_the_runner_notices_an_unscaled_free_space(self, tmp_path: pathlib.Path) -> None:
        """Comparing `obuffree()` samples with a byte length skips the write.
        The stand-in's 4,096-byte buffer is exactly the chunk, so the block
        writes it when it scales and skips it when it does not; a check
        appended to the block tells the two apart."""
        line, source = next((n, s) for n, s in _blocks() if "dsp.obuffree() * frame" in s)
        mutated = source.replace("dsp.obuffree() * frame", "dsp.obuffree()", 1)
        wrote = "\nassert dsp._queued == len(chunk), 'the chunk was not written'\n"

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        original_dir, mutated_dir = tmp_path / "original", tmp_path / "mutated"
        original_dir.mkdir()
        mutated_dir.mkdir()
        original = _run_block(source + wrote, original_dir)
        assert original.returncode == 0, original.stderr
        result = _run_block(mutated + wrote, mutated_dir)
        assert result.returncode != 0
        assert "the chunk was not written" in result.stderr

    def test_the_stand_in_counts_free_space_in_samples(self, tmp_path: pathlib.Path) -> None:
        """The underrun block scales `obuffree()` by the bytes per sample; a
        stand-in counting bytes would let an unscaled comparison pass too."""
        result = _run_block(
            "import ossaudiodev\n"
            "dsp = ossaudiodev.open('w')\n"
            "dsp.setparameters(ossaudiodev.AFMT_S16_LE, 2, 44100)\n"
            "assert dsp.obuffree() * 4 == 4096\n",
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
