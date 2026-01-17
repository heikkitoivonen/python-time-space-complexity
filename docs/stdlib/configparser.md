# Configparser Module

The `configparser` module provides facilities for reading and writing configuration files in INI format.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ConfigParser()` | O(1) | O(1) | Create parser |
| `read(file)` | O(n) | O(n) | n = file size |
| `read_string(string)` | O(n) | O(n) | Parse string |
| `write(file)` | O(n) | O(n) | n = config size |
| `get(section, option)` | O(1) | O(1) | Dict-based lookup; O(n) with interpolation |
| `getint/getfloat/getboolean` | O(1) | O(1) | O(1) lookup + O(1) conversion |
| `sections()` | O(n) | O(n) | n = section count |
| `options(section)` | O(n) | O(n) | n = option count |

## Common Operations

### Reading Configuration Files

```python
import configparser

# O(1) - create parser
config = configparser.ConfigParser()

# O(n) where n = file size
files_read = config.read('config.ini')

# O(1) - get value
database_url = config.get('database', 'url')

# O(1) - get with type conversion
debug = config.getboolean('app', 'debug')
port = config.getint('server', 'port')
timeout = config.getfloat('network', 'timeout')
```

### Creating Configuration Programmatically

```python
import configparser

# O(1) - create parser
config = configparser.ConfigParser()

# O(1) - add section
config.add_section('database')

# O(1) per option - set values
config.set('database', 'host', 'localhost')
config.set('database', 'port', '5432')
config.set('database', 'name', 'mydb')

# O(1) per option - alternative
config['database'] = {
    'host': 'localhost',
    'port': '5432'
}
```

### Writing Configuration to File

```python
import configparser

config = configparser.ConfigParser()
config['app'] = {'debug': 'true', 'version': '1.0'}
config['db'] = {'host': 'localhost', 'port': '5432'}

# O(n) where n = config size
with open('config.ini', 'w') as f:
    config.write(f)

# O(n) - also can get as string
config_str = config.write_string()
```

## Common Use Cases

### Application Configuration

```python
import configparser
import os

def load_config(config_file='config.ini'):
    """Load application configuration - O(n)"""
    config = configparser.ConfigParser()
    
    # O(n) to read file
    config.read(config_file)
    
    # O(1) per access
    return {
        'debug': config.getboolean('app', 'debug', fallback=False),
        'host': config.get('server', 'host', fallback='localhost'),
        'port': config.getint('server', 'port', fallback=8000),
        'db_url': config.get('database', 'url'),
    }

# Usage - O(n)
config = load_config()
print(f"Debug: {config['debug']}")
```

### Multiple Configuration Files

```python
import configparser

def load_configs(*config_files):
    """Load multiple config files - O(n*m)"""
    config = configparser.ConfigParser()
    
    # O(n*m) where n = files, m = avg file size
    files_read = config.read(config_files)
    
    return config, files_read

# Usage - O(n*m)
config, loaded = load_configs('defaults.ini', 'config.ini', 'local.ini')
print(f"Loaded {len(loaded)} files")
```

### Environment Variable Interpolation

```python
import configparser
import os

def create_interpolating_parser(env_vars=None):
    """Create parser with interpolation - O(1)"""
    # O(1) - create with interpolation
    config = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation()
    )
    
    # Set defaults - O(k) where k = defaults
    if env_vars:
        config.read_dict({
            'DEFAULT': env_vars
        })
    
    return config

# Usage - O(1)
config = create_interpolating_parser({'home': '/home/user'})
config.read_string("""
[paths]
config_dir = ${home}/.config
""")
```

### Configuration Validation

```python
import configparser

def validate_config(config_file, required_sections, required_options):
    """Validate configuration - O(n+m)"""
    config = configparser.ConfigParser()
    
    # O(n) to read
    config.read(config_file)
    
    errors = []
    
    # O(m) to check sections where m = required section count
    for section in required_sections:
        if not config.has_section(section):
            errors.append(f"Missing section: {section}")
        else:
            # O(k) to check options where k = required option count
            for option in required_options.get(section, []):
                if not config.has_option(section, option):
                    errors.append(f"Missing option: {section}.{option}")
    
    return len(errors) == 0, errors

# Usage - O(n+m)
valid, errors = validate_config(
    'config.ini',
    ['database', 'server'],
    {'database': ['host', 'port'], 'server': ['host', 'port']}
)
```

### Default Values and Fallbacks

```python
import configparser

def get_config_with_defaults(config_file):
    """Get config with sensible defaults - O(n)"""
    config = configparser.ConfigParser(
        defaults={
            'host': 'localhost',
            'port': '8000',
            'debug': 'false',
            'timeout': '30'
        }
    )
    
    # O(n) to read - overrides defaults
    config.read(config_file)
    
    return config

# Usage - O(n)
config = get_config_with_defaults('config.ini')

# O(1) - returns default if not in file
host = config.get('server', 'host')
debug = config.getboolean('app', 'debug')
```

### Dynamic Configuration Sections

```python
import configparser

def get_section_dict(config_file, section):
    """Get entire section as dict - O(n)"""
    config = configparser.ConfigParser()
    
    # O(n) to read
    config.read(config_file)
    
    # O(k) where k = options in section
    if config.has_section(section):
        return dict(config.items(section))
    return {}

# Usage - O(n)
db_config = get_section_dict('config.ini', 'database')
# {'host': 'localhost', 'port': '5432', 'name': 'mydb'}
```

## Performance Tips

### Cache Config Parser

```python
import configparser

class ConfigCache:
    """Cache parsed configuration - O(1) access"""
    
    def __init__(self, config_file):
        self.config_file = config_file
        self._config = None
    
    def get_config(self):
        """O(1) cached access"""
        if self._config is None:
            # O(n) first load
            self._config = configparser.ConfigParser()
            self._config.read(self.config_file)
        return self._config
    
    def reload(self):
        """O(n) forced reload"""
        self._config = None
        return self.get_config()

# Usage - O(1) after first call
cache = ConfigCache('config.ini')
config = cache.get_config()  # O(n) first time
config = cache.get_config()  # O(1) cached
```

### Use get() with fallback

```python
import configparser

# Bad: Multiple lookups and checks - O(k) per check
config = configparser.ConfigParser()
config.read('config.ini')

if config.has_section('app') and config.has_option('app', 'debug'):
    debug = config.getboolean('app', 'debug')
else:
    debug = False

# Good: Single fallback lookup - O(1)
debug = config.getboolean('app', 'debug', fallback=False)
```

### Lazy Load Sections

```python
import configparser

class LazyConfigParser:
    """Load sections on demand - O(1) initial"""
    
    def __init__(self, config_file):
        self.config_file = config_file
        self._loaded_sections = set()
        self._config = configparser.ConfigParser()
    
    def get(self, section, option, fallback=None):
        """O(n) first section load, O(1) thereafter"""
        if section not in self._loaded_sections:
            # O(n) to load section
            self._config.read(self.config_file)
            self._loaded_sections.add(section)
        
        return self._config.get(section, option, fallback=fallback)
```

## Version Notes

- **Python 2.6+**: configparser available
- **Python 3.x**: ConfigParser renamed to configparser
- **Python 3.2+**: Extended interpolation available
- **Python 3.6+**: Dict-like access support

## Related Documentation

- [Pathlib Module](pathlib.md) - Path handling for config files
- [Sys Module](sys.md) - sys.argv for config file paths
- [JSON Module](json.md) - Alternative serialization format
