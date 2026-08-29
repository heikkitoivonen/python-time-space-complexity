# tomllib Module

The `tomllib` module parses TOML (Tom's Obvious, Minimal Language) files. Available in Python 3.11+.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `loads()` | O(n) | O(n) | n = string length; parses entire content |
| `load()` | O(n) | O(n) | n = file size; reads entire file |

## Basic Parsing

### Load from String

```python
import tomllib

# Parse TOML string - O(n)
toml_string = """
[database]
server = "192.168.1.1"
ports = [8001, 8001, 8002]
enabled = true
"""

config = tomllib.loads(toml_string)
print(config['database']['server'])  # "192.168.1.1"
```

### Load from File

```python
import tomllib

# Parse from file - O(n)
with open("config.toml", "rb") as f:
    config = tomllib.load(f)
    # config is a dict
    print(config)
```

## TOML Data Types

### Supported Types

```python
import tomllib

toml_data = """
# String
name = "John Doe"

# Integer
age = 30

# Float
height = 5.9

# Boolean
active = true

# DateTime
created = 2024-01-16T10:30:00Z

# Array
tags = ["python", "toml", "config"]

# Table (dict)
[address]
street = "123 Main St"
city = "Springfield"

# Array of tables
[[users]]
name = "Alice"
age = 25

[[users]]
name = "Bob"
age = 30
"""

config = tomllib.loads(toml_data)  # O(n) in the text length
# config is a dict with nested structures. Every type above parses in one
# pass - nesting and arrays of tables cost no more per character than a
# flat key does
```

## Working with Configuration Files

### Typical Config Structure

```toml
# pyproject.toml example
[project]
name = "myapp"
version = "1.0.0"
description = "My application"

[project.optional-dependencies]
dev = ["pytest", "black"]
test = ["coverage"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"

[build-system]
requires = ["setuptools>=45"]
```

### Parse Configuration

```python
import tomllib

# Read project config - O(n)
with open("pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)

# Access nested data
project_name = pyproject['project']['name']
dev_deps = pyproject['project']['optional-dependencies']['dev']
test_paths = pyproject['tool']['pytest']['ini_options']['testpaths']
```

## Common Patterns

### Application Configuration

```python
import tomllib
from pathlib import Path

def load_config(config_file="config.toml"):
    # O(n) where n = file size
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"{config_file} not found")
    
    with open(config_path, "rb") as f:
        return tomllib.load(f)

config = load_config()
db_url = config['database']['url']
debug = config['server']['debug']
```

### Merging Defaults

```python
import tomllib

def load_config_with_defaults(user_config_file, defaults):
    # O(n) where n = file size
    defaults_copy = defaults.copy()
    
    try:
        with open(user_config_file, "rb") as f:
            user_config = tomllib.load(f)
            defaults_copy.update(user_config)
    except FileNotFoundError:
        pass  # Use defaults
    
    return defaults_copy

# Usage
defaults = {
    'port': 8000,
    'debug': False,
    'workers': 4
}

config = load_config_with_defaults("app.toml", defaults)
```

### Environment-Specific Config

```python
import tomllib
from pathlib import Path

def load_env_config(env="development"):
    # O(n) per config file
    base_config = {}
    
    # Load base config
    with open("config.toml", "rb") as f:
        base_config.update(tomllib.load(f))
    
    # Load environment-specific
    env_file = f"config.{env}.toml"
    if Path(env_file).exists():
        with open(env_file, "rb") as f:
            base_config.update(tomllib.load(f))
    
    return base_config

# Load for current environment
prod_config = load_env_config("production")
dev_config = load_env_config("development")
```

## Limitations

### Read-Only

```python
import tomllib

# ❌ Cannot write TOML with tomllib
# tomllib only reads - it's not designed for writing

# ✅ For writing, use third-party libraries:
# import tomli_w
# with open("config.toml", "wb") as f:
#     tomli_w.dump(config, f)
```

### Python Version

```python
import sys

# tomllib available in Python 3.11+
if sys.version_info >= (3, 11):
    import tomllib
else:
    # Fallback for older versions
    import tomli as tomllib
```

## Related Modules

- [json Module](json.md) - JSON parsing (alternative format)
- [configparser Module](configparser.md) - INI file parsing
- [pathlib Module](pathlib.md) - File path handling
- [sys Module](sys.md) - Access to Python version info
