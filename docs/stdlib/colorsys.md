# Colorsys Module

The `colorsys` module provides conversions between color systems (RGB, HSV, HLS, YIQ).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `rgb_to_hls()` | O(1) | O(1) | RGB → HLS |
| `hls_to_rgb()` | O(1) | O(1) | HLS → RGB |
| `rgb_to_hsv()` | O(1) | O(1) | RGB → HSV |
| `hsv_to_rgb()` | O(1) | O(1) | HSV → RGB |
| `rgb_to_yiq()` | O(1) | O(1) | RGB → YIQ |
| `yiq_to_rgb()` | O(1) | O(1) | YIQ → RGB |

## Common Operations

### RGB to HSV Conversion

```python
import colorsys

# O(1) - convert RGB to HSV
# RGB values: 0-1 range (or 0-255 scaled)
r, g, b = 255, 128, 64  # Orange-ish
r_norm = r / 255.0
g_norm = g / 255.0
b_norm = b / 255.0

# O(1) conversion
h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)
print(f"HSV: H={h:.2f}, S={s:.2f}, V={v:.2f}")
# HSV: H=0.04, S=0.75, V=1.00

# O(1) - convert back to RGB
r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
print(f"RGB: {r2:.2f}, {g2:.2f}, {b2:.2f}")
```

### RGB to HLS Conversion

```python
import colorsys

# O(1) - convert RGB to HLS (Hue, Lightness, Saturation)
r, g, b = 0.5, 0.3, 0.7  # Purple-ish

# O(1) conversion
h, l, s = colorsys.rgb_to_hls(r, g, b)
print(f"HLS: H={h:.2f}, L={l:.2f}, S={s:.2f}")

# O(1) - convert back
r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
print(f"RGB: {r2:.2f}, {g2:.2f}, {b2:.2f}")
```

## Common Use Cases

### Creating Color Variations

```python
import colorsys

def create_color_palette(base_rgb, num_colors):
    """Create color palette from base - O(n)"""
    # O(1) to normalize
    r, g, b = base_rgb
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0
    
    # O(1) to convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)
    
    palette = []
    
    # O(n) to create variations
    for i in range(num_colors):
        # Vary hue
        h_varied = (h + (i / num_colors)) % 1.0
        
        # O(1) to convert back
        r2, g2, b2 = colorsys.hsv_to_rgb(h_varied, s, v)
        
        # Convert to 0-255 range
        palette.append((int(r2*255), int(g2*255), int(b2*255)))
    
    return palette

# Usage - O(n)
colors = create_color_palette((255, 100, 50), 5)
for color in colors:
    print(color)
```

### Brightness Adjustment

```python
import colorsys

def adjust_brightness(rgb, factor):
    """Adjust color brightness - O(1)"""
    r, g, b = rgb
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0
    
    # O(1) to convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r_norm, g_norm, b_norm)
    
    # O(1) to adjust value (brightness)
    v = min(1.0, v * factor)
    
    # O(1) to convert back
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    
    return (int(r2*255), int(g2*255), int(b2*255))

# Usage - O(1)
original = (200, 100, 50)
brighter = adjust_brightness(original, 1.2)  # 20% brighter
darker = adjust_brightness(original, 0.8)    # 20% darker
```

### Saturation Control

```python
import colorsys

def adjust_saturation(rgb, factor):
    """Adjust color saturation - O(1)"""
    r, g, b = [x/255.0 for x in rgb]
    
    # O(1) to convert
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    
    # O(1) to adjust saturation
    s = min(1.0, s * factor)
    
    # O(1) to convert back
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    
    return tuple(int(x*255) for x in (r2, g2, b2))

# Usage - O(1)
vivid = adjust_saturation((100, 150, 200), 1.5)  # More vivid
muted = adjust_saturation((100, 150, 200), 0.5)  # More muted
```

### Grayscale Conversion

```python
import colorsys

def to_grayscale(rgb):
    """Convert to grayscale using lightness - O(1)"""
    r, g, b = [x/255.0 for x in rgb]
    
    # O(1) to get lightness
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    
    # O(1) to convert back with zero saturation
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, 0.0)
    
    gray = int(l * 255)  # Use lightness as gray value
    
    return gray

# Usage - O(1)
color = (255, 100, 50)
gray = to_grayscale(color)  # Returns 0-255 grayscale value
print(f"Grayscale: {gray}")
```

### Complementary Colors

```python
import colorsys

def get_complementary_color(rgb):
    """Get complementary color - O(1)"""
    r, g, b = [x/255.0 for x in rgb]
    
    # O(1) to convert
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    
    # O(1) - opposite hue (180 degrees)
    h_comp = (h + 0.5) % 1.0
    
    # O(1) to convert back
    r2, g2, b2 = colorsys.hsv_to_rgb(h_comp, s, v)
    
    return tuple(int(x*255) for x in (r2, g2, b2))

# Usage - O(1)
original = (255, 100, 50)      # Orange
complement = get_complementary_color(original)  # Cyan-ish
print(f"Complement: {complement}")
```

### Color Distance

```python
import colorsys

def color_distance_hsl(rgb1, rgb2):
    """Calculate distance in HSL space - O(1)"""
    # Normalize to 0-1
    r1, g1, b1 = [x/255.0 for x in rgb1]
    r2, g2, b2 = [x/255.0 for x in rgb2]
    
    # O(1) to convert both
    h1, l1, s1 = colorsys.rgb_to_hls(r1, g1, b1)
    h2, l2, s2 = colorsys.rgb_to_hls(r2, g2, b2)
    
    # O(1) to calculate distance
    # Handle hue wraparound
    h_dist = min(abs(h1 - h2), 1.0 - abs(h1 - h2))
    l_dist = abs(l1 - l2)
    s_dist = abs(s1 - s2)
    
    # Weighted Euclidean distance
    distance = (h_dist**2 + l_dist**2 + s_dist**2) ** 0.5
    
    return distance

# Usage - O(1)
color1 = (255, 0, 0)      # Red
color2 = (0, 255, 0)      # Green
dist = color_distance_hsl(color1, color2)
print(f"Distance: {dist:.2f}")
```

## Performance Tips

### Cache Conversions for Repeated Use

```python
import colorsys

class ColorCache:
    """Cache color conversions - O(1) lookup"""
    
    def __init__(self):
        self._cache = {}
    
    def rgb_to_hsv(self, rgb):
        """O(1) cached or O(1) new conversion"""
        if rgb not in self._cache:
            r, g, b = [x/255.0 for x in rgb]
            # O(1) conversion
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            self._cache[rgb] = (h, s, v)
        
        return self._cache[rgb]

# Usage
cache = ColorCache()
hsv = cache.rgb_to_hsv((255, 100, 50))  # O(1)
hsv = cache.rgb_to_hsv((255, 100, 50))  # O(1) - cached
```

### Batch Conversions

```python
import colorsys

# Bad: Individual conversions - O(n)
for rgb in colors:
    hsv = colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)

# Good: List comprehension - still O(n) but more efficient
normalized = [(r/255, g/255, b/255) for r, g, b in colors]
hsvs = [colorsys.rgb_to_hsv(r, g, b) for r, g, b in normalized]
```

## Version Notes

- **Python 2.6+**: All functions available
- **Python 3.x**: Full support
- **Range**: Values typically 0-1 or 0-255 (depends on function)

## Related Documentation

- [Math Module](math.md) - Mathematical operations
- [Statistics Module](statistics.md) - Color analysis
