# imghdr Module

⚠️ **REMOVED IN PYTHON 3.13**: The `imghdr` module was deprecated in Python 3.11 and removed in Python 3.13.

The `imghdr` module detects the type of image files by examining their file headers, supporting common formats like PNG, JPEG, GIF, etc.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `what()` | O(1) | O(1) | Read file header |
| Type detection | O(1) | O(1) | Magic number match |

## Detecting Image Types

### Identify Image Format

```python
import imghdr

# Detect from file - O(1)
image_type = imghdr.what('image.png')
print(image_type)  # 'png'

# Detect from filename
image_type = imghdr.what('photo.jpg')
print(image_type)  # 'jpeg'

# Detect from data - O(1)
with open('image.gif', 'rb') as f:
    data = f.read(32)  # Read header
    image_type = imghdr.what(None, h=data)
    print(image_type)  # 'gif'
```

## Related Documentation

- [mimetypes Module](mimetypes.md)
- [PIL/Pillow Library](https://pillow.readthedocs.io)
