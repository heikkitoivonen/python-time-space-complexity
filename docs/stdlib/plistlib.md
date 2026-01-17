# plistlib Module

The `plistlib` module reads and writes property list (.plist) files, commonly used on macOS for storing application data and configuration.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `loads()` | O(n) | O(n) | n = data size; XML parsing overhead |
| `dumps()` | O(n) | O(n) | n = object size; XML generation |
| `load()` | O(n) | O(n) | n = file size |
| `dump()` | O(n) | O(n) | n = object size |

## Basic Parsing

### Load from Bytes

```python
import plistlib

# Parse plist data - O(n)
plist_bytes = b"""<?xml version="1.0"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Name</key>
  <string>John Doe</string>
  <key>Age</key>
  <integer>30</integer>
</dict>
</plist>"""

data = plistlib.loads(plist_bytes)
print(data['Name'])  # "John Doe"
print(data['Age'])   # 30
```

### Load from File

```python
import plistlib

# Read plist from file - O(n)
with open("settings.plist", "rb") as f:
    data = plistlib.load(f)
    
print(data['version'])
print(data['settings'])
```

## Data Types

### Supported Types

```python
import plistlib

# Create plist-compatible data - O(1)
data = {
    'name': 'MyApp',
    'version': '1.0',
    'count': 42,
    'ratio': 3.14,
    'enabled': True,
    'items': ['a', 'b', 'c'],
    'nested': {
        'key': 'value'
    },
    'binary': b'bytes',
    'date': datetime.datetime.now()
}

# Convert to plist bytes - O(n)
plist_bytes = plistlib.dumps(data, sort_keys=True)
print(plist_bytes.decode('utf-8')[:200])  # Show first 200 chars
```

## Writing Plist Files

### Save Configuration

```python
import plistlib

# Application settings
settings = {
    'version': '1.0',
    'theme': 'dark',
    'window_size': [1024, 768],
    'last_opened': '/Users/john/documents',
    'plugins_enabled': ['plugin1', 'plugin2'],
    'preferences': {
        'auto_save': True,
        'auto_save_interval': 300
    }
}

# Write to file - O(n)
with open("app_settings.plist", "wb") as f:
    plistlib.dump(settings, f)
```

### Binary Vs XML Format

```python
import plistlib

data = {'name': 'test', 'value': 123}

# XML format (text, human-readable) - O(n)
xml_bytes = plistlib.dumps(data, sort_keys=True, fmt=plistlib.FMT_XML)

# Binary format (compact, faster) - O(n)
binary_bytes = plistlib.dumps(data, sort_keys=True, fmt=plistlib.FMT_BINARY)

print(f"XML size: {len(xml_bytes)} bytes")
print(f"Binary size: {len(binary_bytes)} bytes")
```

## macOS Application Data

### Preferences Handling

```python
import plistlib
from pathlib import Path

def get_app_preferences(app_name):
    """
    Load macOS application preferences.
    
    Time: O(n) where n = file size
    Space: O(n)
    """
    # Typical macOS preferences location
    pref_file = Path.home() / f".{app_name}_prefs.plist"
    
    if pref_file.exists():
        with open(pref_file, "rb") as f:
            return plistlib.load(f)
    
    return {}

def save_app_preferences(app_name, prefs):
    """
    Save macOS application preferences.
    
    Time: O(n) where n = data size
    Space: O(n)
    """
    pref_file = Path.home() / f".{app_name}_prefs.plist"
    
    with open(pref_file, "wb") as f:
        plistlib.dump(prefs, f)

# Usage
prefs = get_app_preferences('myapp')
prefs['last_window_pos'] = [100, 200, 800, 600]
save_app_preferences('myapp', prefs)
```

### Info.plist Parsing

```python
import plistlib
from pathlib import Path

def read_app_info(bundle_path):
    """
    Read macOS app bundle Info.plist.
    
    Time: O(n) where n = file size
    Space: O(n)
    """
    info_plist = Path(bundle_path) / "Contents" / "Info.plist"
    
    if info_plist.exists():
        with open(info_plist, "rb") as f:
            return plistlib.load(f)
    
    raise FileNotFoundError(f"No Info.plist in {bundle_path}")

# Usage
app_bundle = "/Applications/MyApp.app"
info = read_app_info(app_bundle)
print(f"App name: {info.get('CFBundleName')}")
print(f"Version: {info.get('CFBundleVersion')}")
print(f"Executable: {info.get('CFBundleExecutable')}")
```

## Data Conversion

### From Dictionary to Plist

```python
import plistlib
from datetime import datetime

# Create structured data - O(1)
manifest = {
    'title': 'Project Files',
    'version': 1,
    'created': datetime.now(),
    'files': [
        {
            'name': 'main.py',
            'size': 2048,
            'modified': datetime.now()
        },
        {
            'name': 'config.yaml',
            'size': 512,
            'modified': datetime.now()
        }
    ]
}

# Serialize - O(n)
plist_data = plistlib.dumps(manifest, sort_keys=True, fmt=plistlib.FMT_XML)

# Write to file
with open("manifest.plist", "wb") as f:
    f.write(plist_data)
```

### Round-trip Operations

```python
import plistlib

# Original data
original = {
    'strings': ['a', 'b', 'c'],
    'numbers': [1, 2, 3],
    'nested': {'key': 'value'}
}

# Serialize - O(n)
plist_bytes = plistlib.dumps(original, fmt=plistlib.FMT_XML)

# Deserialize - O(n)
restored = plistlib.loads(plist_bytes)

# Verify round-trip
assert original == restored
print("✓ Round-trip successful")
```

## Advanced Patterns

### Configuration Manager

```python
import plistlib
from pathlib import Path
from typing import Any, Dict

class PlistConfig:
    """Configuration manager using plist format."""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.data = {}
        self.load()
    
    def load(self):
        """Load config from file - O(n)"""
        if self.config_file.exists():
            with open(self.config_file, "rb") as f:
                self.data = plistlib.load(f)
    
    def save(self):
        """Save config to file - O(n)"""
        with open(self.config_file, "wb") as f:
            plistlib.dump(self.data, f, sort_keys=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value - O(1)"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set config value - O(1)"""
        self.data[key] = value
    
    def update(self, **kwargs):
        """Update multiple values - O(k) where k = keys"""
        self.data.update(kwargs)

# Usage
config = PlistConfig("app.plist")
config.set('debug', True)
config.set('port', 8000)
config.save()
```

## Formats Available

```python
import plistlib

# XML format (default)
# FMT_XML = 'xml'
# - Human readable
# - Larger file size
# - Text format

# Binary format (compact)
# FMT_BINARY = 'binary'
# - Not human readable
# - Smaller file size
# - Binary format

# Use FMT_XML for config files (human readable)
# Use FMT_BINARY for data files (compact)
```

## Related Modules

- [json Module](json.md) - JSON format alternative
- [pickle Module](pickle.md) - Python object serialization
- [configparser Module](configparser.md) - INI configuration files
- [pathlib Module](pathlib.md) - File path handling
