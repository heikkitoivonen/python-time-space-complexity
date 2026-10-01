# colorsys Module Complexity

The `colorsys` module converts one colour at a time between RGB and three other coordinate systems:
YIQ, HLS and HSV. Each function is a fixed sequence of float arithmetic on three components and
returns a new 3-tuple; nothing is cached or validated.

Every function takes and returns three floats, so every bound is O(1): no input has a size. The
model treats float arithmetic as O(1). `n` is colours, in the sections that convert many of them.
Components are expected in [0, 1] (I and Q range a little wider); RGB in 0-255 has to be scaled
first.

## Complexity Reference

### RGB and YIQ

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `colorsys.rgb_to_yiq(r, g, b)` | O(1) | O(1) | |
| `colorsys.yiq_to_rgb(y, i, q)` | O(1) | O(1) | Clamps each channel to [0, 1], so an out-of-gamut YIQ colour does not round-trip |

### RGB and HLS

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `colorsys.rgb_to_hls(r, g, b)` | O(1) | O(1) | A grey returns hue and saturation 0.0 |
| `colorsys.hls_to_rgb(h, l, s)` | O(1) | O(1) | Hue wraps modulo 1, negative values included |

### RGB and HSV

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `colorsys.rgb_to_hsv(r, g, b)` | O(1) | O(1) | A grey returns hue and saturation 0.0 |
| `colorsys.hsv_to_rgb(h, s, v)` | O(1) | O(1) | Hue wraps above 1, but a negative hue can give a channel outside [0, 1]: reduce it with `% 1.0` first |

## Converting a Colour

Each conversion is a constant amount of arithmetic on one colour. A round trip returns the same
colour up to float rounding, so compare the result with `math.isclose()` rather than `==`, with an
`abs_tol` for components near 0.

```python
import colorsys
import math

r, g, b = 255 / 255, 128 / 255, 64 / 255   # scale 0-255 to [0, 1] first

h, s, v = colorsys.rgb_to_hsv(r, g, b)     # O(1)
assert (round(h, 2), round(s, 2), v) == (0.06, 0.75, 1.0)

back = colorsys.hsv_to_rgb(h, s, v)        # O(1)
assert all(math.isclose(x, y, abs_tol=1e-12) for x, y in zip(back, (r, g, b)))

h, l, s = colorsys.rgb_to_hls(r, g, b)     # O(1)
back = colorsys.hls_to_rgb(h, l, s)        # O(1)
assert all(math.isclose(x, y, abs_tol=1e-12) for x, y in zip(back, (r, g, b)))

assert colorsys.rgb_to_hsv(0.5, 0.5, 0.5) == (0.0, 0.0, 0.5)  # a grey has no hue
```

### Out-of-range Input

Nothing is validated. `yiq_to_rgb()` clamps its result into [0, 1], and the two hue-taking
functions treat a negative hue differently.

```python
import colorsys

# A YIQ colour outside the RGB gamut is clamped, not rejected
assert colorsys.yiq_to_rgb(0.5, 0.6, 0.0) == (1.0, 0.33512741222061304, 0.0)  # O(1)

# hls_to_rgb wraps any hue; hsv_to_rgb does not reliably wrap a negative one
assert colorsys.hls_to_rgb(-0.1, 0.5, 1.0) == colorsys.hls_to_rgb(0.9, 0.5, 1.0)
assert colorsys.hsv_to_rgb(-0.1, 1.0, 1.0)[1] < 0
assert colorsys.hsv_to_rgb(-0.1 % 1.0, 1.0, 1.0) == colorsys.hsv_to_rgb(0.9, 1.0, 1.0)
```

## Converting Many Colours

There is no batch form: converting n colours is n calls, O(n) time. Scale each colour as it is
converted rather than building a normalised copy of the list first, which costs O(n) extra memory.

```python
import colorsys

colors = [(255, 100, 50), (0, 128, 255), (30, 30, 30)]

# O(n) time, one result per colour and no intermediate list
hsvs = [colorsys.rgb_to_hsv(r / 255, g / 255, b / 255) for r, g, b in colors]

assert len(hsvs) == 3
assert hsvs[2][:2] == (0.0, 0.0)  # the grey
```

## Common Patterns

### Hue Rotation

A palette of n hues is one conversion into HSV and n back out, O(n) in all.

```python
import colorsys

def palette(base_rgb, count):
    """count colours evenly spaced in hue - O(count)"""
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in base_rgb))  # O(1)
    result = []
    for i in range(count):
        r, g, b = colorsys.hsv_to_rgb((h + i / count) % 1.0, s, v)  # O(1)
        result.append((round(r * 255), round(g * 255), round(b * 255)))
    return result

colors = palette((255, 100, 50), 2)
assert colors[0] == (255, 100, 50)
assert colors[1] == (50, 205, 255)  # the complement, half a turn away
```

### Adjusting Brightness and Saturation

```python
import colorsys

def adjust(rgb, brightness=1.0, saturation=1.0):
    """Scale value and saturation in HSV - O(1)"""
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))   # O(1)
    s = min(1.0, s * saturation)
    v = min(1.0, v * brightness)
    return tuple(round(x * 255) for x in colorsys.hsv_to_rgb(h, s, v))  # O(1)

assert adjust((200, 100, 50), brightness=0.5) == (100, 50, 25)
assert adjust((200, 100, 50), saturation=0.0) == (200, 200, 200)
```

## Performance Best Practices

✅ **Do**:

- Scale 0-255 input to [0, 1] inline as each colour is converted
- Reduce a computed hue with `% 1.0` before `hsv_to_rgb()`
- Compare round-tripped components with `math.isclose()` and an `abs_tol`

❌ **Avoid**:

- Building a normalised copy of a colour list before converting it - O(n) extra memory for the
  same O(n) calls
- Passing 0-255 values to an `rgb_to_*` function: nothing is validated, so the result is wrong or
  the call raises

## Related Modules

- **[math](math.md)** - `math.isclose()` for comparing round-tripped components
