# audioop Module

⚠️ **REMOVED IN PYTHON 3.13**: The `audioop` module was deprecated in Python 3.11 and removed in Python 3.13.

The `audioop` module operates on fragments of raw PCM audio held in bytes-like
objects. Every function is implemented in C and makes a single pass over the
fragment, so cost is linear in the number of bytes.

Throughout, `n` is the length of the fragment in bytes and `width` is the
sample width (1, 2, 3, or 4 bytes).

## Complexity Reference

### Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `max(fragment, width)` | O(n) | O(1) | Largest absolute sample value |
| `minmax(fragment, width)` | O(n) | O(1) | Minimum and maximum in one pass |
| `avg(fragment, width)` | O(n) | O(1) | Arithmetic mean |
| `rms(fragment, width)` | O(n) | O(1) | Root mean square (loudness) |
| `cross(fragment, width)` | O(n) | O(1) | Zero-crossing count |
| `avgpp(fragment, width)` | O(n) | O(1) | Average peak-peak value |
| `maxpp(fragment, width)` | O(n) | O(1) | Maximum peak-peak value |
| `getsample(fragment, width, index)` | O(1) | O(1) | Single sample by index |

### Transformation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `add(f1, f2, width)` | O(n) | O(n) | Sample-wise sum of two fragments |
| `mul(fragment, width, factor)` | O(n) | O(n) | Scale amplitude |
| `bias(fragment, width, bias)` | O(n) | O(n) | Add a constant to each sample |
| `reverse(fragment, width)` | O(n) | O(n) | Reverse sample order |
| `tomono(fragment, width, lf, rf)` | O(n) | O(n) | Stereo to mono |
| `tostereo(fragment, width, lf, rf)` | O(n) | O(n) | Mono to stereo; output is 2n |
| `lin2lin(fragment, width, newwidth)` | O(n) | O(n) | Change sample width |
| `ratecv(fragment, width, nchannels, inrate, outrate, state)` | O(n) | O(n) | Resample; output scales with the rate ratio |

### Codecs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lin2ulaw(fragment, width)` | O(n) | O(n) | Linear to u-LAW |
| `ulaw2lin(fragment, width)` | O(n) | O(n) | u-LAW to linear |
| `lin2alaw(fragment, width)` | O(n) | O(n) | Linear to a-LAW |
| `alaw2lin(fragment, width)` | O(n) | O(n) | a-LAW to linear |
| `lin2adpcm(fragment, width, state)` | O(n) | O(n) | Linear to ADPCM |
| `adpcm2lin(fragment, width, state)` | O(n) | O(n) | ADPCM to linear |

### Search

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `findfit(fragment, reference)` | O(n*m) | O(1) | m = reference length; tries every offset |
| `findfactor(fragment, reference)` | O(n) | O(1) | Best scale factor for a fixed alignment |
| `findmax(fragment, length)` | O(n*length) | O(1) | Sliding window of the given length |

`findfit` and `findmax` are the only non-linear operations: both slide a window
across the fragment and score each position.

## Measuring Loudness

```python
import audioop

# O(n) single pass over the fragment
loudness = audioop.rms(sample_bytes, 2)   # 16-bit samples
peak = audioop.max(sample_bytes, 2)       # O(n)

# Both statistics in one pass instead of two
low, high = audioop.minmax(sample_bytes, 2)   # O(n)
```

## Converting and Mixing

```python
import audioop

# Halve the volume - O(n), allocates a new fragment
quieter = audioop.mul(sample_bytes, 2, 0.5)

# Mix two fragments of equal length - O(n)
mixed = audioop.add(track_a, track_b, 2)

# Stereo to mono, equal weighting - O(n)
mono = audioop.tomono(stereo_bytes, 2, 0.5, 0.5)
```

## Resampling

`ratecv` is stateful: pass the returned state into the next call so fragment
boundaries do not click.

```python
import audioop

state = None
for chunk in chunks:
    # O(n); output length scales by outrate/inrate
    converted, state = audioop.ratecv(chunk, 2, 1, 44100, 8000, state)
    output.write(converted)
```

!!! warning "Removed in Python 3.13"
    There is no standard-library replacement. Use a third-party audio library
    such as `numpy` for sample maths, or a dedicated audio processing package.

!!! tip "Every call allocates"
    The transformation functions return new bytes objects, so a chain of
    operations allocates once per step. For long pipelines on large fragments,
    consider a library that supports in-place buffers.

## Version Notes

- **Python 3.11**: deprecated (PEP 594)
- **Python 3.13**: removed
- **Before 3.13**: all operations are single-pass C loops; complexity is
  unchanged across versions

## Related Documentation

- [Wave Module](wave.md)
- [Sunau Module](sunau.md)
- [Aifc Module](aifc.md)
- [Array Module](array.md)
