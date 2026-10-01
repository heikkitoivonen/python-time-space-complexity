# audioop Module Complexity

The `audioop` module operates on fragments of raw PCM audio: signed integer samples 1, 2, 3 or 4
bytes wide, held in any contiguous bytes-like object such as `bytes`, `bytearray`, `memoryview` or
`array.array`. Every function is C, reads the fragment in place without copying it, and returns
numbers or new `bytes` objects; nothing is kept between calls except the state tuple you
pass back to `ratecv()`, `lin2adpcm()` and `adpcm2lin()`.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples need
    Python 3.10, 3.11 or 3.12.

`n` is the bytes in a fragment (each fragment, where a function takes two of the same length),
`m` is the bytes in the `reference` passed to `findfit()`, and `o` is the bytes `ratecv()`
returns. The sample width is at most 4 bytes, so the work per sample is O(1), and an output that
is a fixed multiple of the input, such as `ulaw2lin()`'s n·width bytes, is O(n).

## Complexity Reference

### Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `audioop.getsample(fragment, width, index)` | O(1) | O(1) | Raises `audioop.error` for an index outside the fragment |
| `audioop.max(fragment, width)` | O(n) | O(1) | Largest absolute sample value |
| `audioop.minmax(fragment, width)` | O(n) | O(1) | Smallest and largest sample, in one pass |
| `audioop.avg(fragment, width)` | O(n) | O(1) | Mean of the samples |
| `audioop.rms(fragment, width)` | O(n) | O(1) | Root mean square, a measure of power |
| `audioop.cross(fragment, width)` | O(n) | O(1) | Number of zero crossings |
| `audioop.avgpp(fragment, width)`, `audioop.maxpp(fragment, width)` | O(n) | O(1) | Average and largest peak-to-peak value |

### Transformation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `audioop.add(fragment1, fragment2, width)` | O(n) | O(n) | The fragments must be the same length; a sum that overflows is clipped |
| `audioop.mul(fragment, width, factor)` | O(n) | O(n) | A product that overflows is clipped |
| `audioop.bias(fragment, width, bias)` | O(n) | O(n) | A sum that overflows wraps around |
| `audioop.reverse(fragment, width)` | O(n) | O(n) | Reverses the sample order |
| `audioop.byteswap(fragment, width)` | O(n) | O(n) | Swaps the byte order of every sample |
| `audioop.tomono(fragment, width, lfactor, rfactor)` | O(n) | O(n) | Returns n/2 bytes |
| `audioop.tostereo(fragment, width, lfactor, rfactor)` | O(n) | O(n) | Returns 2n bytes |
| `audioop.lin2lin(fragment, width, newwidth)` | O(n) | O(n) | Returns n·newwidth/width bytes |
| `audioop.ratecv(fragment, width, nchannels, inrate, outrate, state, weightA=1, weightB=0)` | O(n + o) | O(o) | o is about n·outrate/inrate. Returns `(data, state)`; passing the state to the next call makes chunked output identical to one call. The buffer is rounded up to a multiple of outrate/gcd(inrate, outrate) frames, so rates with a small gcd allocate up to that many extra frames per call |

### Codecs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `audioop.lin2ulaw(fragment, width)`, `audioop.lin2alaw(fragment, width)` | O(n) | O(n) | One byte per sample: n/width bytes |
| `audioop.ulaw2lin(fragment, width)`, `audioop.alaw2lin(fragment, width)` | O(n) | O(n) | One sample per byte: n·width bytes |
| `audioop.lin2adpcm(fragment, width, state)` | O(n) | O(n) | Four bits per sample: n/(2·width) bytes, rounded down. Returns `(data, state)`; the state does not carry an odd sample's half byte |
| `audioop.adpcm2lin(fragment, width, state)` | O(n) | O(n) | Two samples per byte: 2·n·width bytes. Returns `(data, state)` |

### Search

These three take 16-bit samples only, and have no `width` argument.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `audioop.findfit(fragment, reference)` | O((n − m + 1)·m) | O(1) | Rescores the whole reference at every offset, so a reference half the fragment's length is the quadratic worst case. `fragment` must be at least as long. Returns `(offset, factor)` |
| `audioop.findfactor(fragment, reference)` | O(n) | O(1) | The fragments must be the same length; the factor for one fixed alignment |
| `audioop.findmax(fragment, length)` | O(n) | O(1) | Slides a running sum, so `length` does not change the cost |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `audioop.error` | O(1) | O(1) | Raised for a width other than 1 to 4, a fragment that is not a whole number of samples, and mismatched lengths |

## Measuring a Fragment

The analysis functions read the fragment where it is and return a number, so they cost one pass
and no memory, whatever kind of buffer holds the samples.

```python
import array
import audioop

samples = array.array('h', [0, 1000, -3000, 2000, -500, 0])  # 16-bit samples
fragment = samples.tobytes()

assert audioop.max(fragment, 2) == 3000                # O(n)
assert audioop.minmax(fragment, 2) == (-3000, 2000)    # O(n) - both in one pass
assert audioop.rms(fragment, 2) == 1541                # O(n)
assert audioop.cross(fragment, 2) == 4                 # O(n)
assert audioop.getsample(fragment, 2, 2) == -3000      # O(1)

# Any bytes-like object works, with no copy to bytes first
assert audioop.max(samples, 2) == 3000                 # O(n), O(1) memory
assert audioop.max(memoryview(fragment)[4:], 2) == 3000

try:
    audioop.max(fragment[:-1], 2)  # 11 bytes is not a whole number of samples
except audioop.error as error:
    assert 'whole number' in str(error)
else:
    raise AssertionError('a partial sample was accepted')
```

## Converting and Mixing

Each transformation returns a new fragment, so a chain of them allocates one output per step.
The output's length depends on what the function changes: the channel count, the sample width or
the encoding.

```python
import array
import audioop

mono = array.array('h', [100, -200, 300, -400]).tobytes()  # 4 samples, 8 bytes

louder = audioop.mul(mono, 2, 2.0)          # O(n)
assert audioop.max(louder, 2) == 800

mixed = audioop.add(mono, louder, 2)        # O(n) - same lengths required
assert audioop.getsample(mixed, 2, 3) == -1200

stereo = audioop.tostereo(mono, 2, 1, 1)    # O(n), 2n bytes
assert len(stereo) == 16
assert audioop.tomono(stereo, 2, 0.5, 0.5) == mono  # O(n), n/2 bytes

wide = audioop.lin2lin(mono, 2, 4)          # O(n), n·newwidth/width bytes
assert len(wide) == 16 and audioop.getsample(wide, 4, 0) == 100 << 16

# Overflow clips in add() and mul(), but wraps in bias()
assert audioop.add(b'\x7f', b'\x7f', 1) == b'\x7f'
assert audioop.bias(b'\x7f', 1, 1) == b'\x80'
```

## Resampling and Encoding in Chunks

`ratecv()`, `lin2adpcm()` and `adpcm2lin()` return a state with their output. Passing it to the
next call continues the stream where the last chunk stopped, so a long recording can be
converted a chunk at a time in memory proportional to the chunk, with the same result as one call
on the whole. For `lin2adpcm()` that holds when each chunk has an even number of samples: an odd
one's last half byte is dropped, not carried in the state.

```python
import array
import audioop

signal = array.array('h', (i * 37 % 2000 - 1000 for i in range(4410))).tobytes()

whole, _ = audioop.ratecv(signal, 2, 1, 44100, 8000, None)  # O(n + o)

state = None
pieces = []
for start in range(0, len(signal), 882):
    chunk = signal[start:start + 882]
    converted, state = audioop.ratecv(chunk, 2, 1, 44100, 8000, state)  # O(chunk)
    pieces.append(converted)

assert b''.join(pieces) == whole
assert len(whole) // 2 == 800  # o is about n·outrate/inrate

# The ADPCM coders carry their predictor the same way
encoded, adpcm_state = audioop.lin2adpcm(signal, 2, None)   # O(n), n/4 bytes for 16-bit
assert len(encoded) == len(signal) // 4
decoded, _ = audioop.adpcm2lin(encoded, 2, None)            # O(n), 4 bytes per input byte
assert len(decoded) == len(signal)
```

### u-LAW and A-LAW

The logarithmic codecs store one byte per sample, so encoding divides the size by the width and
decoding multiplies it.

```python
import array
import audioop

linear = array.array('h', [0, 1000, -1000, 32000]).tobytes()

ulaw = audioop.lin2ulaw(linear, 2)    # O(n), n/width bytes
assert len(ulaw) == 4
back = audioop.ulaw2lin(ulaw, 2)      # O(n), n·width bytes
assert len(back) == len(linear)
assert abs(audioop.getsample(back, 2, 1) - 1000) < 50  # lossy, but close

alaw = audioop.lin2alaw(linear, 2)    # O(n)
assert len(audioop.alaw2lin(alaw, 4)) == 16  # decode straight to 32-bit samples
```

## Searching a Fragment

`findmax()` keeps a running sum as its window slides, so it is one pass whatever the window
length. `findfit()` recomputes the whole correlation with the reference at every offset; when the
alignment is already known, `findfactor()` gives the factor in linear time instead.

```python
import array
import audioop

quiet = [i * 7 % 21 - 10 for i in range(100)]
loud = [3000, 1000, -2000, -500, 2500, -3000, 100, 0, -1500, 1200]
fragment = array.array('h', quiet + loud + quiet).tobytes()  # 16-bit only

assert audioop.findmax(fragment, 10) == 100  # O(n), whatever the length

reference = array.array('h', loud).tobytes()
offset, factor = audioop.findfit(fragment, reference)  # O((n - m + 1)·m)
assert offset == 100 and abs(factor - 1.0) < 1e-9

aligned = fragment[2 * offset:2 * offset + len(reference)]
assert audioop.findfactor(aligned, reference) == 1.0  # O(n), same lengths

try:
    audioop.findfit(reference, fragment)  # the reference must be the shorter
except audioop.error as error:
    assert 'longer' in str(error)
else:
    raise AssertionError('a longer reference was accepted')
```

## Common Patterns

### Measuring a WAV File

```python
import array
import audioop
import io
import wave

buffer = io.BytesIO()
with wave.open(buffer, 'wb') as out:
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(8000)
    out.writeframes(audioop.tostereo(array.array('h', [16, -16] * 400).tobytes(), 2, 1, 1))

buffer.seek(0)
with wave.open(buffer, 'rb') as wav:
    width = wav.getsampwidth()
    frames = wav.readframes(wav.getnframes())  # O(n)

mono = audioop.tomono(frames, width, 0.5, 0.5)  # O(n)
assert audioop.rms(mono, width) == 16  # O(n)
assert audioop.cross(mono, width) == 799
```

## Performance Best Practices

✅ **Do**:

- Pass `bytearray`, `memoryview` or `array.array` fragments straight in; they are read in place
- Carry the state returned by `ratecv()`, `lin2adpcm()` and `adpcm2lin()` into the next call, and
  process long recordings a chunk at a time
- Use `findfactor()` when the alignment is known: linear instead of a pass per offset
- Keep a `findfit()` search small: it costs the offsets tried times the reference length

❌ **Avoid**:

- A `findfit()` reference near half the fragment's length - that is its quadratic worst case
- Long chains of transformations on a large fragment - each step allocates a full new output
- `audioop` in new code - it does not exist from Python 3.13

## Version Notes

- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import audioop` raises `ModuleNotFoundError`

## Related Modules

- **[wave](wave.md)** - reads and writes the PCM frames these functions take
- **[aifc](aifc.md)** - used `audioop` for its compressed formats, removed in 3.13 too
- **[sunau](sunau.md)** - u-LAW Sun audio files, removed in 3.13 too
- **[array](array.md)** - builds and unpacks 16- and 32-bit sample buffers
