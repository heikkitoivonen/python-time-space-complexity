"""Tests for docs/stdlib/winsound.md.

Every function is one Win32 call. `PlaySound()` is the one with a size
term, and the page's claims about it are settled by what the process reads
and holds while and after it plays. Windows' own buffers do not pass
through tracemalloc, so Win32 counters stand in: the private bytes
committed and the page faults taken (GetProcessMemoryInfo), which paging
and working-set trimming do not lower; the bytes read through file I/O
(GetProcessIoCounters); and whether given pages are resident
(QueryWorkingSetEx). The WAV
images are silent - 8 kHz, 8-bit mono, every sample 0x80, unless a test
says otherwise - and the large ones carry their bulk as a zero-filled
`junk` chunk, placed before the `fmt ` chunk or after the `data` chunk, so
image size and audio length vary independently. No test calls `Beep()`
with a valid frequency or `MessageBeep()` at all, and none plays a sound
that is not silent. Every play passes `SND_NODEFAULT`, so a sound that
cannot be found or played raises instead of playing the default one.

Measurement scope:

* `SND_MEMORY` reads the image in place. A 0.2 s image padded to
  50,000,000 bytes, either side of the audio, is laid out in freshly
  committed pages with the padding's pages never written: after the play,
  none of those 12,207 pages is resident and the play took fewer page
  faults than a quarter of their number (a first touch of each would fault
  once, whether or not the page was later trimmed), so neither Python nor
  Windows copied or scanned the padding, while reading the image back in
  Python makes over 80% of them resident (the control). 4 s of 16-bit stereo
  192 kHz audio, 6,144,000 bytes, raises private bytes by under 2 MB,
  sampled every 2 ms throughout the play, so the audio is not copied
  either. A 0.1 s image padded to 1,000,000 bytes peaks under 10,000 traced
  bytes while it plays; PC/winsound.c takes a PyBUF_SIMPLE view and hands
  its pointer to PlaySoundW on every supported version. `bytearray` and
  `memoryview` are accepted; a `str` is TypeError.
* `SND_ASYNC` with `SND_MEMORY` raises RuntimeError("Cannot play
  asynchronously from memory"), with or without `SND_LOOP`, before
  PlaySoundW is reached; the check is the same in PC/winsound.c from
  v3.10.21 to v3.14.7 and was run on 3.10 to 3.14.
* `SND_FILENAME` reads the whole file. A synchronous play of 0.2 s of
  audio padded to a 50,000,000-byte file, the padding before the audio or
  after it, reads over 45 MB and leaves private bytes over 40 MB above
  where they started, where an unpadded file reads and leaves under 5 MB;
  `PlaySound(None, flags)` with flags 0, `SND_PURGE` and `SND_MEMORY`, or
  the next play, brings private bytes back within 5 MB.
* `SND_ASYNC` does not wait for the file to be read: of three plays of the
  same padded file, at least one has read under 10 MB when the call returns
  (0 bytes on every play on the machine these tests were written on), and
  each has read over 45 MB, with private bytes over 40 MB higher, within five
  seconds after. One sample per play can race the background reader, which is
  why a single play is not required to be caught; a reader that finished
  before returning would show 50 MB on all three.
* `SND_ALIAS` and `SND_ALIAS | SND_APPLICATION` play the file a registry
  event names: a scratch event under HKCU\\AppEvents\\Schemes\\Apps\\.Default,
  and under the running executable's name, pointing at the padded file,
  plays and leaves over 40 MB of private bytes; an unknown alias with
  `SND_NODEFAULT` is RuntimeError. The scratch keys are deleted afterwards,
  and so is the application's key when the test created it.
* Timing tests, each asserting only lower bounds on a sound's length or an
  upper bound far from it: a synchronous 1 s play from memory takes at
  least 0.9 s; a synchronous 2 s play of a file takes at least 1.8 s and an
  asynchronous one returns in under 1 s, as does one of the same audio
  padded to 50,000,000 bytes; `PlaySound(None, 0)` from the main thread
  0.3 s into a 2 s synchronous play in another thread leaves that play
  taking at least 1.8 s.
* A sound in progress: an asynchronous loop of a 0.3 s file padded to
  50,000,000 bytes, started and waited on until its file has been read,
  then for 0.5 s more. That it is sounding is inferred from its file having
  been read, not observed. While it plays, a play with `SND_NOSTOP` raises
  RuntimeError("Failed to play sound") and the loop still holds its file
  (private bytes over 40 MB up), where with nothing playing the same call
  plays. On Windows 11 (build 22000 or later; skipped before), a 1 s
  synchronous play with `SND_PURGE` or `SND_NOWAIT` during the loop returns
  None after at least 0.9 s (a timing test), so it was neither refused nor
  cut short.
* A synchronous `SND_LOOP` of a 0.3 s file returns, in a subprocess given
  30 s.
* `os.PathLike` is accepted from 3.12 and TypeError before; `bytes` without
  `SND_MEMORY` is TypeError on every version; a missing file and an invalid
  image, each with `SND_NODEFAULT`, are RuntimeError("Failed to play
  sound").
* `Beep()` raises ValueError for frequencies 0, 36 and 32,768, which the
  range check in PC/winsound.c rejects before calling Beep.
  `MessageBeep()`'s `type` defaults to `MB_OK`, which is 0.
* `SND_SYNC` is 0, and `MB_ICONERROR`, `MB_ICONSTOP`, `MB_ICONINFORMATION`
  and `MB_ICONWARNING` equal `MB_ICONHAND`, `MB_ICONHAND`, `MB_ICONASTERISK`
  and `MB_ICONEXCLAMATION`, on 3.14+; those five names, `SND_SENTRY` and
  `SND_SYSTEM` are all absent before 3.14, which added them to
  PC/winsound.c. `SND_SENTRY`, `SND_SYSTEM`, `SND_SYNC` and `SND_APPLICATION`
  are accepted in a play from memory.
* Every fenced block on the page but the audible one runs in its own
  subprocess, and a mutated assertion in one of them is asserted to fail.
  The runner is not timing-marked, so it asserts that no block reads a
  clock; the blocks' O(1) and O(d) comments rest on the timing tests.

Not settled here:

* That `Beep()` blocks for its duration and that `MessageBeep()` returns
  once the sound is queued. Both are audible, so the page follows the Win32
  documentation of Beep and MessageBeep. The tones block on the page is not
  run for the same reason. So is the default sound a missing file or alias
  plays without `SND_NODEFAULT`: the tests observe only the RuntimeError
  with it.
* That `PlaySound(None, flags)` stops an asynchronous sound and that
  `SND_LOOP` repeats one: a silent sound gives no signal that it stopped or
  repeated. The tests observe only that stopping releases the file's bytes.
  What `SND_SENTRY` and `SND_SYSTEM` change is likewise not observable.
* A machine without an audio device. The machine these tests were written
  on has one wave output device; every test that plays a sound skips where
  `waveOutGetNumDevs()` reports none, so such a machine verifies nothing
  about playback.
* `SND_NOWAIT` and `SND_PURGE` being ignored is Windows 11's behaviour;
  the test skips on older Windows, which may honour them. `SND_NOSTOP`
  was observed on Windows 11 only, where it behaves as the Win32
  documentation of PlaySound describes.
* What Windows holds while a sound from memory plays beyond the private
  bytes counted here, such as buffers in the audio service's own process.
* Held fixed: the audio format (8 kHz, 8-bit mono, except the one 192 kHz
  stereo play) and the padding's chunk type (`junk`). The O(f) of a file
  was measured at one size, 50,000,000 bytes, against an unpadded file.
* Every test except the block count is Windows-only and skips elsewhere, so
  a run on Linux or macOS verifies none of the page's claims.
"""

from __future__ import annotations

import contextlib
import ctypes
import importlib
import inspect
import io
import mmap
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import uuid
import wave
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "winsound.md"
EXPECTED_BLOCKS = 6
# Blocks that are never run, keyed by a line they contain, with the reason.
SKIPPED_BLOCKS = {
    "winsound.Beep(440, 500)": "plays an audible tone and a system alert",
}

WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="winsound is Windows-only")
winsound: Any = importlib.import_module("winsound") if sys.platform == "win32" else None


def _wave_output_devices() -> int:
    windll: Any = getattr(ctypes, "WinDLL")  # noqa: B009 - absent from typeshed on Linux
    return windll("winmm").waveOutGetNumDevs()


AUDIO = pytest.mark.skipif(
    sys.platform != "win32" or _wave_output_devices() == 0,
    reason="playing a sound needs Windows and a wave output device",
)

WINDOWS_11 = sys.platform == "win32" and getattr(sys, "getwindowsversion")().build >= 22_000  # noqa: B009

MB = 1_000_000
PADDING = 50 * MB


def silent_wav(
    seconds: float,
    padding: int = 0,
    *,
    pad_after: bool = False,
    channels: int = 1,
    width: int = 1,
    rate: int = 8000,
) -> bytes:
    """A silent WAV image, 8 kHz 8-bit mono unless told otherwise, padded by
    a `junk` chunk before the `fmt ` chunk, or after the `data` chunk with
    `pad_after`."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        # Silence is the midpoint: 0x80 for unsigned 8-bit, zero otherwise.
        frames = int(rate * seconds) * channels
        w.writeframes(b"\x80" * frames if width == 1 else bytes(frames * width))
    image = buffer.getvalue()
    if not padding:
        return image
    junk = b"junk" + struct.pack("<I", padding) + bytes(padding)
    body = image[12:] + junk if pad_after else junk + image[12:]
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def write_wav(
    path: pathlib.Path, seconds: float, padding: int = 0, *, pad_after: bool = False
) -> str:
    path.write_bytes(silent_wav(seconds, padding, pad_after=pad_after))
    return str(path)


def _kernel32() -> Any:
    from ctypes import wintypes

    windll: Any = getattr(ctypes, "WinDLL")  # noqa: B009 - absent from typeshed on Linux
    kernel32 = windll("kernel32")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    return kernel32


def _memory_counters() -> Any:
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    windll: Any = getattr(ctypes, "WinDLL")  # noqa: B009 - absent from typeshed on Linux
    psapi = windll("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    assert psapi.GetProcessMemoryInfo(
        _kernel32().GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    return counters


def private_bytes() -> int:
    """The private bytes committed by this process: the memory Windows holds
    for it, whether or not it is paged in."""
    return _memory_counters().PrivateUsage


def page_faults() -> int:
    """Page faults this process has taken so far, a count trimming cannot lower."""
    return _memory_counters().PageFaultCount


def bytes_read() -> int:
    """Bytes this process has read through file and device I/O so far."""
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    kernel32 = _kernel32()
    kernel32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    counters = Counters()
    assert kernel32.GetProcessIoCounters(kernel32.GetCurrentProcess(), ctypes.byref(counters))
    return counters.ReadTransferCount


@contextlib.contextmanager
def untouched_padding(image: bytes) -> Iterator[tuple[memoryview, Callable[[], int]]]:
    """`image` in fresh pages of its own, every byte written except the body
    of its `junk` chunk, whose pages stay demand-zero and out of the working
    set until something reads them. Yields a view of it and a function
    counting how many of those padding pages are resident."""
    from ctypes import wintypes

    class WorkingSetInfo(ctypes.Structure):
        _fields_ = [("VirtualAddress", ctypes.c_void_p), ("VirtualAttributes", ctypes.c_size_t)]

    windll: Any = getattr(ctypes, "WinDLL")  # noqa: B009 - absent from typeshed on Linux
    kernel32, psapi = _kernel32(), windll("psapi")
    kernel32.VirtualAlloc.restype = ctypes.c_void_p
    kernel32.VirtualAlloc.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    psapi.QueryWorkingSetEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    mem_commit_reserve, mem_release, page_readwrite = 0x3000, 0x8000, 0x04

    start = image.index(b"junk") + 8
    end = start + struct.unpack_from("<I", image, start - 4)[0]
    address = kernel32.VirtualAlloc(None, len(image), mem_commit_reserve, page_readwrite)
    assert address
    try:
        ctypes.memmove(address, image[:start], start)
        ctypes.memmove(address + end, image[end:], len(image) - end)
        first = -(-(address + start) // mmap.PAGESIZE)
        pages = (WorkingSetInfo * ((address + end) // mmap.PAGESIZE - first))()
        for index, page in enumerate(pages):
            page.VirtualAddress = (first + index) * mmap.PAGESIZE

        def resident() -> int:
            assert psapi.QueryWorkingSetEx(
                kernel32.GetCurrentProcess(), pages, ctypes.sizeof(pages)
            )
            return sum(page.VirtualAttributes & 1 for page in pages)

        view = memoryview((ctypes.c_char * len(image)).from_address(address))
        try:
            yield view, resident
        finally:
            view.release()
    finally:
        kernel32.VirtualFree(address, 0, mem_release)


def private_peak_during(func: Callable[[], Any]) -> int:
    """Rise in private bytes above the start, sampled every 2 ms while func runs."""
    base = private_bytes()
    peak = base
    done = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not done.is_set():
            peak = max(peak, private_bytes())
            time.sleep(0.002)

    sampler = threading.Thread(target=sample)
    sampler.start()
    try:
        func()
    finally:
        done.set()
        sampler.join()
    return peak - base


def elapsed(func: Callable[[], Any]) -> float:
    start = time.perf_counter()
    func()
    return time.perf_counter() - start


@pytest.fixture
def quiet() -> Iterator[None]:
    """Nothing playing and no file kept, before and after the test."""
    winsound.PlaySound(None, 0)
    try:
        yield
    finally:
        winsound.PlaySound(None, 0)


def memory_flags(*names: str) -> int:
    flags = winsound.SND_MEMORY | winsound.SND_NODEFAULT
    for name in names:
        flags |= getattr(winsound, name)
    return flags


def file_flags(*names: str) -> int:
    flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
    for name in names:
        flags |= getattr(winsound, name)
    return flags


@AUDIO
@pytest.mark.usefixtures("quiet")
class TestMemoryIsReadInPlace:
    """`PlaySound(sound, SND_MEMORY)` | O(d) | O(1) - the image is neither
    copied by Python nor by Windows, so only its audio costs anything.

    The wrong answers are a copy of the image (or of its audio) and a scan
    of it: the padding's pages are shown never to be read at all, and
    seconds of high-rate audio are shown not to be copied."""

    @pytest.mark.serial
    def test_python_copies_nothing(self) -> None:
        image = silent_wav(0.1, padding=MB)
        winsound.PlaySound(silent_wav(0.1), memory_flags())
        tracemalloc.start()
        try:
            winsound.PlaySound(image, memory_flags())
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert peak < 10_000, f"a {len(image)}-byte image peaked at {peak} B"

    @pytest.mark.parametrize("pad_after", [False, True], ids=["padded-first", "padded-last"])
    def test_the_padding_is_never_read(self, pad_after: bool) -> None:
        image = silent_wav(0.2, padding=PADDING, pad_after=pad_after)
        with untouched_padding(image) as (view, resident):
            padding_pages = PADDING // mmap.PAGESIZE
            assert resident() == 0
            faults = page_faults()
            winsound.PlaySound(view, memory_flags())
            faults = page_faults() - faults
            after_play = resident()
            assert bytes(view) == image
            after_read = resident()
        # A page read and then trimmed would leave no resident page, but its
        # first touch still counts a fault, so the fault count backs this up.
        assert after_play == 0, f"playing read {after_play} padding pages"
        assert faults < padding_pages // 4, f"playing took {faults} page faults"
        assert after_read > padding_pages * 0.8, "the probe does not see a read of the padding"

    def test_the_audio_is_not_copied(self) -> None:
        # 4 s of 16-bit stereo at 192 kHz: 6,144,000 bytes of audio.
        image = silent_wav(4.0, channels=2, width=2, rate=192_000)
        rise = private_peak_during(lambda: winsound.PlaySound(image, memory_flags()))
        assert rise < 2 * MB, f"{len(image)} bytes of audio raised private bytes by {rise} B"

    def test_any_bytes_like_object_plays(self) -> None:
        image = silent_wav(0.05)
        winsound.PlaySound(bytearray(image), memory_flags())
        winsound.PlaySound(memoryview(image), memory_flags())
        with pytest.raises(TypeError):
            winsound.PlaySound("not bytes", memory_flags())

    @pytest.mark.timing
    def test_a_play_from_memory_blocks_for_the_sound(self) -> None:
        image = silent_wav(1.0)
        winsound.PlaySound(silent_wav(0.05), memory_flags())
        took = elapsed(lambda: winsound.PlaySound(image, memory_flags()))
        assert took >= 0.9, f"a 1 s sound returned after {took:.2f} s"

    @pytest.mark.parametrize("extra", ["SND_ASYNC", "SND_ASYNC | SND_LOOP"])
    def test_asynchronous_play_from_memory_raises(self, extra: str) -> None:
        with pytest.raises(RuntimeError, match="asynchronously from memory"):
            winsound.PlaySound(silent_wav(0.05), memory_flags(*extra.split(" | ")))

    def test_an_invalid_image_raises_with_nodefault(self) -> None:
        with pytest.raises(RuntimeError, match="Failed to play sound"):
            winsound.PlaySound(b"not a wav" * 10, memory_flags())


@AUDIO
@pytest.mark.usefixtures("quiet")
class TestFilesAreReadWhole:
    """`PlaySound(sound, SND_FILENAME)` | O(f + d) | O(f) - Windows reads the
    whole file, padding included, and keeps it until the next call.

    The process's read counter separates reading the whole file from reading
    only its audio, and private bytes separate keeping it from dropping it."""

    @pytest.mark.parametrize("pad_after", [False, True], ids=["padded-first", "padded-last"])
    def test_the_whole_file_is_read_and_kept(self, tmp_path: pathlib.Path, pad_after: bool) -> None:
        bare = write_wav(tmp_path / "bare.wav", 0.2)
        padded = write_wav(tmp_path / "padded.wav", 0.2, padding=PADDING, pad_after=pad_after)
        winsound.PlaySound(bare, file_flags())

        base, read = private_bytes(), bytes_read()
        winsound.PlaySound(bare, file_flags())
        assert private_bytes() - base < 5 * MB
        assert bytes_read() - read < 5 * MB

        read = bytes_read()
        winsound.PlaySound(padded, file_flags())
        assert bytes_read() - read > 45 * MB, "the file's bytes were not read"
        assert private_bytes() - base > 40 * MB, "the file's bytes were not kept"

        winsound.PlaySound(silent_wav(0.05), memory_flags())
        assert private_bytes() - base < 5 * MB, "the next play did not release it"

    @pytest.mark.parametrize("flags", ["0", "SND_PURGE", "SND_MEMORY"])
    def test_none_releases_the_file_whatever_the_flags(
        self, tmp_path: pathlib.Path, flags: str
    ) -> None:
        padded = write_wav(tmp_path / "padded.wav", 0.2, padding=PADDING)
        base = private_bytes()
        winsound.PlaySound(padded, file_flags())
        assert private_bytes() - base > 40 * MB

        winsound.PlaySound(None, 0 if flags == "0" else getattr(winsound, flags))
        assert private_bytes() - base < 5 * MB

    @pytest.mark.timing
    def test_an_asynchronous_play_reads_the_file_after_returning(
        self, tmp_path: pathlib.Path
    ) -> None:
        # The sample right after the call can race the background reader, so
        # one attempt in three must catch it unfinished. A play that read the
        # whole file before returning would show all 50 MB on every attempt.
        padded = write_wav(tmp_path / "padded.wav", 0.2, padding=PADDING)
        at_returns = []
        for _ in range(3):
            winsound.PlaySound(None, 0)
            base, read = private_bytes(), bytes_read()
            winsound.PlaySound(padded, file_flags("SND_ASYNC"))
            at_returns.append(bytes_read() - read)

            deadline = time.monotonic() + 5
            while bytes_read() - read <= 45 * MB and time.monotonic() < deadline:
                time.sleep(0.01)
            assert bytes_read() - read > 45 * MB, "the file was never read"
            assert private_bytes() - base > 40 * MB, "the file's bytes were not kept"
        assert min(at_returns) < 10 * MB, f"bytes read by the time each call returned: {at_returns}"

    @pytest.mark.timing
    def test_a_synchronous_play_blocks_and_an_asynchronous_one_does_not(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = write_wav(tmp_path / "two.wav", 2.0)
        padded = write_wav(tmp_path / "padded.wav", 2.0, padding=PADDING)
        winsound.PlaySound(silent_wav(0.05), memory_flags())

        sync = elapsed(lambda: winsound.PlaySound(path, file_flags()))
        async_ = elapsed(lambda: winsound.PlaySound(path, file_flags("SND_ASYNC")))
        async_padded = elapsed(lambda: winsound.PlaySound(padded, file_flags("SND_ASYNC")))

        assert sync >= 1.8, f"a 2 s sound returned after {sync:.2f} s"
        assert async_ < 1.0, f"an asynchronous play took {async_:.2f} s to return"
        assert async_padded < 1.0, f"a 50 MB file took {async_padded:.2f} s to return"

    def test_a_missing_file_raises_with_nodefault(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(RuntimeError, match="Failed to play sound"):
            winsound.PlaySound(str(tmp_path / "missing.wav"), file_flags())

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="os.PathLike accepted from 3.12")
    def test_a_path_object_plays(self, tmp_path: pathlib.Path) -> None:
        path = pathlib.Path(write_wav(tmp_path / "s.wav", 0.05))
        assert winsound.PlaySound(path, file_flags()) is None

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="os.PathLike accepted from 3.12")
    def test_a_path_object_is_rejected_before_3_12(self, tmp_path: pathlib.Path) -> None:
        path = pathlib.Path(write_wav(tmp_path / "s.wav", 0.05))
        with pytest.raises(TypeError, match="must be str or None"):
            winsound.PlaySound(path, file_flags())

    def test_bytes_are_not_a_filename(self, tmp_path: pathlib.Path) -> None:
        path = write_wav(tmp_path / "s.wav", 0.05)
        with pytest.raises(TypeError):
            winsound.PlaySound(path.encode(), file_flags())


def _module_path() -> str:
    """The running executable's path, which names its application events."""
    buffer = ctypes.create_unicode_buffer(32_768)
    windll: Any = getattr(ctypes, "WinDLL")  # noqa: B009 - absent from typeshed on Linux
    assert windll("kernel32").GetModuleFileNameW(None, buffer, len(buffer))
    return buffer.value


@pytest.fixture
def registered_event(tmp_path: pathlib.Path, request: pytest.FixtureRequest) -> Iterator[str]:
    """A scratch sound event pointing at a padded silent file, removed afterwards.

    Parametrised with the application key: `.Default` for `SND_ALIAS`, the
    executable's name for `SND_APPLICATION`."""
    winreg: Any = importlib.import_module("winreg")
    app = request.param or pathlib.Path(_module_path()).stem
    root = rf"AppEvents\Schemes\Apps\{app}"
    # Short on purpose: Windows 11 found a 33-character event name and not a
    # 40-character one.
    name = f"PyComplexity{uuid.uuid4().hex[:8]}"
    path = write_wav(tmp_path / "event.wav", 0.2, padding=PADDING)

    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, root).Close()
        created_root = False
    except FileNotFoundError:
        created_root = True
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{root}\{name}\.Current") as key:
        winreg.SetValue(key, "", winreg.REG_SZ, path)
    try:
        yield name
    finally:
        winsound.PlaySound(None, 0)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{root}\{name}\.Current")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{root}\{name}")
        if created_root:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)


@AUDIO
@pytest.mark.usefixtures("quiet")
class TestAliasesPlayTheirFile:
    """`PlaySound(sound, SND_ALIAS)` | O(f + d) | O(f) - the registry names a
    file, which is then read whole as `SND_FILENAME` reads it."""

    @pytest.mark.parametrize(
        ("registered_event", "extra"),
        [(".Default", 0), ("", "SND_APPLICATION")],
        indirect=["registered_event"],
        ids=["alias", "application"],
    )
    def test_an_event_plays_and_keeps_its_file(
        self, registered_event: str, extra: int | str
    ) -> None:
        flags = winsound.SND_ALIAS | winsound.SND_NODEFAULT
        if extra:
            flags |= getattr(winsound, str(extra))
        base = private_bytes()
        winsound.PlaySound(registered_event, flags)
        assert private_bytes() - base > 40 * MB

    def test_an_unknown_alias_raises_with_nodefault(self) -> None:
        with pytest.raises(RuntimeError, match="Failed to play sound"):
            winsound.PlaySound(
                f"PyMissing{uuid.uuid4().hex[:8]}",
                winsound.SND_ALIAS | winsound.SND_NODEFAULT,
            )


@AUDIO
@pytest.mark.usefixtures("quiet")
class TestStoppingAndIgnoredFlags:
    """`PlaySound(None, flags)` does not reach a synchronous play;
    `SND_NOSTOP` refuses to interrupt a sound that is playing; Windows 11
    plays through `SND_PURGE` and `SND_NOWAIT`.

    Each of the last two needs a sound in progress to mean anything, so an
    asynchronous loop of a padded file is started and waited on until its
    file has been read before the flag is tried."""

    @staticmethod
    def start_a_loop(tmp_path: pathlib.Path) -> None:
        loop = write_wav(tmp_path / "loop.wav", 0.3, padding=PADDING)
        read = bytes_read()
        winsound.PlaySound(loop, file_flags("SND_ASYNC", "SND_LOOP"))
        deadline = time.monotonic() + 5
        while bytes_read() - read <= 45 * MB and time.monotonic() < deadline:
            time.sleep(0.01)
        assert bytes_read() - read > 45 * MB, "the loop's file was never read"
        time.sleep(0.5)

    def test_nostop_refuses_while_another_sound_plays(self, tmp_path: pathlib.Path) -> None:
        short = write_wav(tmp_path / "short.wav", 0.05)
        assert winsound.PlaySound(short, file_flags("SND_NOSTOP")) is None

        base = private_bytes()
        self.start_a_loop(tmp_path)
        with pytest.raises(RuntimeError, match="Failed to play sound"):
            winsound.PlaySound(short, file_flags("SND_NOSTOP"))
        assert private_bytes() - base > 40 * MB, "the playing loop was stopped"

    @pytest.mark.timing
    def test_none_does_not_stop_a_synchronous_play_in_another_thread(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = write_wav(tmp_path / "two.wav", 2.0)
        winsound.PlaySound(silent_wav(0.05), memory_flags())
        took: list[float] = []
        player = threading.Thread(
            target=lambda: took.append(elapsed(lambda: winsound.PlaySound(path, file_flags())))
        )
        player.start()
        time.sleep(0.3)
        winsound.PlaySound(None, 0)
        player.join()
        assert took[0] >= 1.8, f"the 2 s play ended after {took[0]:.2f} s"

    @pytest.mark.timing
    @pytest.mark.skipif(not WINDOWS_11, reason="the flags were observed ignored on Windows 11")
    @pytest.mark.parametrize("flag", ["SND_PURGE", "SND_NOWAIT"])
    def test_the_flag_neither_refuses_nor_cuts_short(
        self, tmp_path: pathlib.Path, flag: str
    ) -> None:
        one = write_wav(tmp_path / "one.wav", 1.0)
        self.start_a_loop(tmp_path)

        result: list[object] = []
        took = elapsed(lambda: result.append(winsound.PlaySound(one, file_flags(flag))))

        assert result == [None]
        assert took >= 0.9, f"a 1 s play with {flag} returned after {took:.2f} s"

    def test_a_synchronous_loop_returns(self, tmp_path: pathlib.Path) -> None:
        path = write_wav(tmp_path / "loop.wav", 0.3)
        code = (
            "import sys, winsound\n"
            "winsound.PlaySound(sys.argv[1], winsound.SND_FILENAME | winsound.SND_NODEFAULT"
            " | winsound.SND_LOOP)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, path],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert result.returncode == 0, result.stderr


@WINDOWS
class TestTonesAndAlerts:
    """`Beep()` checks its frequency before anything plays; `MessageBeep()`
    defaults to `MB_OK`. Neither is called audibly."""

    @pytest.mark.parametrize("frequency", [0, 36, 32_768])
    def test_beep_rejects_a_frequency_out_of_range(self, frequency: int) -> None:
        with pytest.raises(ValueError, match="37 thru 32767"):
            winsound.Beep(frequency, 1)

    def test_messagebeep_defaults_to_mb_ok(self) -> None:
        default = inspect.signature(winsound.MessageBeep).parameters["type"].default
        assert default == winsound.MB_OK == 0


ADDED_IN_3_14 = [
    "SND_SYNC",
    "SND_SENTRY",
    "SND_SYSTEM",
    "MB_ICONERROR",
    "MB_ICONINFORMATION",
    "MB_ICONSTOP",
    "MB_ICONWARNING",
]


@WINDOWS
class TestConstants:
    """The Constants table: integer flags, seven of them new in 3.14."""

    def test_the_older_names_are_distinct_integers(self) -> None:
        snd = [
            "SND_FILENAME",
            "SND_ALIAS",
            "SND_MEMORY",
            "SND_APPLICATION",
            "SND_ASYNC",
            "SND_LOOP",
            "SND_NODEFAULT",
            "SND_NOSTOP",
            "SND_NOWAIT",
            "SND_PURGE",
        ]
        mb = ["MB_OK", "MB_ICONASTERISK", "MB_ICONEXCLAMATION", "MB_ICONHAND", "MB_ICONQUESTION"]
        for group in (snd, mb):
            values = [getattr(winsound, name) for name in group]
            assert all(type(value) is int for value in values)
            assert len(set(values)) == len(values)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_the_3_14_names_and_their_aliases(self) -> None:
        assert winsound.SND_SYNC == 0
        assert winsound.MB_ICONERROR == winsound.MB_ICONSTOP == winsound.MB_ICONHAND
        assert winsound.MB_ICONINFORMATION == winsound.MB_ICONASTERISK
        assert winsound.MB_ICONWARNING == winsound.MB_ICONEXCLAMATION

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="added in 3.14")
    def test_the_3_14_names_are_absent_before(self) -> None:
        assert [name for name in ADDED_IN_3_14 if hasattr(winsound, name)] == []

    @AUDIO
    @pytest.mark.usefixtures("quiet")
    @pytest.mark.parametrize("flag", ["SND_APPLICATION", "SND_SYNC", "SND_SENTRY", "SND_SYSTEM"])
    def test_the_flag_is_accepted_from_memory(self, flag: str) -> None:
        if not hasattr(winsound, flag):
            pytest.skip(f"{flag} is Python 3.14+")
        winsound.PlaySound(silent_wav(0.05), memory_flags(flag))


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
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result. Every
    block that runs plays only silence; the one that would make a sound is
    skipped with its reason."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @AUDIO
    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        skipped: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            # This test runs in the parallel phase: no block may time itself.
            clock = re.search(r"perf_counter|monotonic|time\.time\b|timeit", source)
            assert clock is None, f"{PAGE.name}:{line} measures elapsed time"
            reasons = [why for marker, why in SKIPPED_BLOCKS.items() if marker in source]
            if reasons:
                skipped.append(f"{PAGE.name}:{line}: {reasons[0]}")
                continue
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert len(skipped) == len(SKIPPED_BLOCKS), skipped
        assert not failures, "\n\n".join(failures)

    @WINDOWS
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if '== "Failed to play sound"' in s)
        mutated = source.replace('== "Failed to play sound"', '== "Failed to play"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
