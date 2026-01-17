# Platform Module

The `platform` module provides functions to access platform-specific information about the system and Python interpreter.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `platform()` | O(1) | O(1) | Get platform string |
| `system()` | O(1) | O(1) | Get OS name |
| `release()` | O(1) | O(1) | Get OS release |
| `version()` | O(1) | O(1) | Get OS version |
| `machine()` | O(1) | O(1) | Get machine type |
| `node()` | O(1) | O(1) | Get hostname |
| `python_version()` | O(1) | O(1) | Get Python version |
| `uname()` | O(1) | O(1) | Get uname info |

## Common Operations

### Getting System Information

```python
import platform

# O(1) - get operating system name
os_name = platform.system()  # 'Linux', 'Windows', 'Darwin'

# O(1) - get OS release
os_release = platform.release()  # '5.15.0-1234-generic'

# O(1) - get OS version
os_version = platform.version()
# '#1234-Ubuntu SMP ...'

# O(1) - get machine architecture
machine = platform.machine()  # 'x86_64', 'arm64'

# O(1) - get hostname
hostname = platform.node()  # 'mycomputer'
```

### Getting Python Information

```python
import platform

# O(1) - get Python version
py_version = platform.python_version()  # '3.11.2'

# O(1) - get version as tuple
py_version_tuple = platform.python_version_info()
# (3, 11, 2, 'final', 0)

# O(1) - get Python implementation
implementation = platform.python_implementation()  # 'CPython'

# O(1) - get compiler info
compiler = platform.python_compiler()
# 'GCC 11.2.0'
```

### Getting Complete Platform String

```python
import platform

# O(1) - get complete platform description
platform_str = platform.platform()
# 'Linux-5.15.0-1234-generic-x86_64-with-glibc2.35'

# O(1) - with detailed version
detailed = platform.platform(aliased=True)
# Uses common OS aliases like 'Ubuntu' instead of 'Linux'

# O(1) - with specific details
custom = platform.platform(aliased=True, terse=True)
```

### Getting Detailed System Info

```python
import platform

# O(1) - get uname data (Unix-like systems)
uname_info = platform.uname()
# Returns: (system, node, release, version, machine, processor)

# Access individual components - O(1)
print(uname_info.system)      # 'Linux'
print(uname_info.node)        # hostname
print(uname_info.release)     # kernel version
print(uname_info.version)     # kernel details
print(uname_info.machine)     # architecture
print(uname_info.processor)   # processor
```

## Common Use Cases

### Version Checking

```python
import platform

def check_python_version(required_major, required_minor):
    """Check Python version - O(1)"""
    # O(1) to get version info
    major, minor, micro, _, _ = platform.python_version_info()
    
    # O(1) to compare
    if (major, minor) >= (required_major, required_minor):
        return True
    return False

# Usage - O(1)
if check_python_version(3, 11):
    print("Python 3.11+")
else:
    print("Python < 3.11")
```

### Platform-Specific Code

```python
import platform

def get_config_path():
    """Get platform-appropriate config path - O(1)"""
    # O(1) to get OS
    os_name = platform.system()
    
    # O(1) conditional logic
    if os_name == 'Windows':
        return r'C:\Users\AppData\Local\MyApp'
    elif os_name == 'Darwin':  # macOS
        return '~/Library/Application Support/MyApp'
    else:  # Linux
        return '~/.config/myapp'

# Usage - O(1)
config_dir = get_config_path()
```

### System Requirements Check

```python
import platform

def validate_environment():
    """Validate system meets requirements - O(1)"""
    checks = {
        'python_version': platform.python_version(),
        'python_impl': platform.python_implementation(),
        'os': platform.system(),
        'architecture': platform.machine(),
    }
    
    # O(1) for each check
    valid = (
        checks['python_impl'] == 'CPython' and
        checks['os'] in ('Linux', 'Darwin', 'Windows') and
        checks['architecture'] in ('x86_64', 'arm64')
    )
    
    return valid, checks

# Usage - O(1)
is_valid, info = validate_environment()
print(f"Environment valid: {is_valid}")
print(f"System: {info['os']}")
```

### Logging System Information

```python
import platform
import logging

def log_system_info():
    """Log comprehensive system info - O(1)"""
    # O(1) to gather all info
    info = {
        'platform': platform.platform(),
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'compiler': platform.python_compiler(),
        'os': platform.system(),
        'release': platform.release(),
        'architecture': platform.machine(),
    }
    
    # O(1) per log call
    logger = logging.getLogger('system')
    for key, value in info.items():
        logger.info(f"{key}: {value}")

# Usage - O(1)
log_system_info()
```

### Runtime Behavior Optimization

```python
import platform

class SystemOptimizer:
    """Adjust behavior based on platform - O(1)"""
    
    def __init__(self):
        # O(1) - cache system info
        self.os = platform.system()
        self.arch = platform.machine()
        self._setup_optimizations()
    
    def _setup_optimizations(self):
        """Configure based on platform - O(1)"""
        # O(1) conditionals
        if self.os == 'Windows':
            self.thread_pool_size = 4
            self.file_buffer = 8192
        elif self.arch == 'arm64':
            self.thread_pool_size = 2
            self.file_buffer = 4096
        else:
            self.thread_pool_size = 8
            self.file_buffer = 16384
    
    def get_pool_size(self):
        """O(1) - get cached value"""
        return self.thread_pool_size

# Usage - O(1) after init
opt = SystemOptimizer()
pool_size = opt.get_pool_size()  # O(1)
```

### Feature Detection

```python
import platform

def has_64bit_architecture():
    """Check for 64-bit system - O(1)"""
    # O(1) to check architecture
    return platform.machine() in ('x86_64', 'arm64', 'ppc64')

def is_unix_like():
    """Check if Unix-like system - O(1)"""
    # O(1) to check OS
    return platform.system() in ('Linux', 'Darwin', 'BSD')

def is_windows():
    """Check if Windows - O(1)"""
    return platform.system() == 'Windows'

# Usage - O(1)
if has_64bit_architecture():
    print("64-bit system")
if is_unix_like():
    print("Unix-like system")
```

## Performance Tips

### Cache Platform Information

```python
import platform

class PlatformCache:
    """Cache platform info - O(1) access"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            # O(1) first access, populate cache
            cls._instance = super().__new__(cls)
            cls._instance._init_cache()
        return cls._instance
    
    def _init_cache(self):
        """O(1) to cache all info"""
        self.os = platform.system()
        self.arch = platform.machine()
        self.python_version = platform.python_version()
        self.hostname = platform.node()
    
    def get_os(self):
        """O(1) - return cached"""
        return self.os

# Usage - O(1) after first access
cache = PlatformCache()
os_name = cache.get_os()  # O(1)
os_name = cache.get_os()  # O(1) - same object
```

### Batch Information Gathering

```python
import platform

def get_system_summary():
    """Get all info at once - O(1)"""
    # O(1) for each call, batched together
    return {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'node': platform.node(),
        'python': platform.python_version(),
    }

# Usage - O(1) single call instead of multiple
summary = get_system_summary()
```

## Version Notes

- **Python 2.6+**: Core functions available
- **Python 3.x**: All features available
- **Python 3.13+**: Minor improvements

## Related Documentation

- [Sys Module](sys.md) - sys.platform and version info
- [Os Module](os.md) - OS interface
- [Distutils Module](distutils.md) - Distribution utilities
