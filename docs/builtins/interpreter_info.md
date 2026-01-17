# Interpreter Information Functions

Documentation for `copyright`, `credits`, and `license` - Python interpreter information functions.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copyright` | O(1) | O(1) | Display string |
| `credits` | O(1) | O(1) | Display string |
| `license` | O(1) | O(1) | Display license text |

## Copyright Information

### `copyright` - Python Copyright

Displays Python copyright information.

```python
# Display copyright notice
copyright

# Output:
# Copyright (c) 2001-2024 Python Software Foundation.
# All Rights Reserved.
# 
# Copyright (c) 2000 BeOpen.com
# All Rights Reserved.
# 
# ...
```

### Accessing Programmatically

```python
import sys

# Get copyright string
copyright_text = sys.copyright
print(copyright_text)

# Check if message
print(type(copyright))  # <class 'str'> (acts like string when printed)
```

## Credits Information

### `credits` - Python Credits

Displays credits for Python contributors.

```python
# Display credits
credits

# Output:
#     Thanks to CWI, CNRI, BeOpen.com, Zope Corporation and a cast of thousands
#     for supporting Python development.  See www.python.org for more information.
```

### Accessing Credits

```python
# Credits displayed automatically in interactive mode
credits

# Programmatically access
import sys

# Not directly available as sys.credits, but can get from site module
from site import _Printer
print(f"Credits: {credits}")
```

## License Information

### `license` - Python License

Displays Python Software Foundation License.

```python
# Display full license
license

# Output:
# (Displays entire license text interactively)
```

### License Types

```python
# Interactive mode:
license
# Shows full license text (PSF License)

# Accessing in code
import sys

# PSF license information
license_text = __license__ if '__license__' in dir(__builtins__) else "PSF License"
```

## Practical Usage

### Checking License in Programs

```python
def display_about_dialog():
    """Display application about information."""
    info = f"""
    Python Version: 3.11.x
    Copyright: {copyright}
    
    For full license: python -c "import license; license"
    """
    print(info)

display_about_dialog()
```

### License Compliance

```python
import sys

def check_python_license():
    """Verify Python is properly licensed."""
    # Python is open source - always compliant
    # but you can document it:
    print("This program uses Python")
    print("Python Software Foundation License")
    print("Visit: https://docs.python.org/license.html")

check_python_license()
```

### Exit Interactive Mode

```python
# In interactive interpreter (REPL):
>>> copyright
# ...copyright text...
>>> exit  # Not a function - just type 'exit' or Ctrl+D
>>> quit  # Alternative to exit
```

## Interactive Mode Only

### Note on Availability

```python
# These work in REPL:
>>> copyright
# Prints copyright

>>> credits
# Prints credits

>>> license
# Prints license

# In scripts, they're available but less common:
# python script.py won't automatically print these
```

### Importing

```python
# These are available globally in interactive mode
# In scripts, access via:
import sys
from site import _Printer

# They're site-specific helpers for REPL
```

## Use Cases

### About/Help Commands

```python
def show_about():
    """Show application about information."""
    print("=== About ===")
    print(f"Python: {sys.version}")
    print("\nPython is licensed under the Python Software Foundation License")
    print("See: https://www.python.org/psf/license/")

show_about()
```

### Documentation Generation

```python
def generate_license_file():
    """Generate LICENSE file mentioning Python."""
    with open("LICENSE_PYTHON.txt", "w") as f:
        f.write("This project uses Python\n\n")
        f.write("Python License:\n")
        f.write("Python Software Foundation License\n")
        f.write("See: https://docs.python.org/license.html\n")

generate_license_file()
```

## Related Information

### System Information

```python
import sys
import platform

# Python version
print(f"Python: {sys.version}")
print(f"Platform: {platform.platform()}")

# License info
print("License: PSF License")
print("URL: https://www.python.org/psf/license/")
```

### Interactive Help

```python
# Use help() for documentation
help(copyright)
help(credits)
help(license)

# Or view online at:
# https://docs.python.org/license.html
```

## Related Functions

- [help() Function](../builtins/help.md) - Interactive help
- [sys Module](../stdlib/sys.md) - System information
