# logging Module Complexity

The `logging` module provides functionality for flexible event logging, with different severity levels and output destinations.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `logging.basicConfig()` | Varies | Varies | Creates handlers/formatters |
| `logger.debug/info/warning/error()` | Varies | Varies | Depends on handlers, filters, and I/O |
| `getLogger()` | O(1) avg | O(1) | Get logger instance |
| Formatting message | O(k) | O(k) | k = formatted string |

## Basic Usage

### Simple Logging

```python
import logging

# Configure logging - cost depends on handlers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Log messages - cost depends on handlers and I/O
logging.debug('Debug message')      # Not shown (level=INFO)
logging.info('Info message')        # O(10)
logging.warning('Warning message')  # O(15)
logging.error('Error message')      # O(13)
```

### Logger Instances

```python
import logging

# Get logger - O(1)
logger = logging.getLogger(__name__)

# Set level - O(1)
logger.setLevel(logging.DEBUG)

# Log messages - cost depends on handlers and I/O
logger.debug('Debug: %s', variable)      # O(k)
logger.info('Processing: %s', item)      # O(k)
logger.warning('Issue: %s', issue)       # O(k)
logger.error('Error: %s', error)         # O(k)
```

## Configuration

### Handlers and Formatters

```python
import logging

# Create logger - O(1)
logger = logging.getLogger('myapp')
logger.setLevel(logging.DEBUG)

# File handler - O(1)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.ERROR)

# Console handler - O(1)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter - O(1)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers - O(1) each (list append)
logger.addHandler(file_handler)      # O(1)
logger.addHandler(console_handler)   # O(1)

# Log - cost depends on handlers and I/O
logger.info('Application started')
```

## Log Levels

### Severity Levels

```python
import logging

# Levels (in order) - O(1) check
logging.DEBUG       # 10 - Detailed info for debugging
logging.INFO        # 20 - Confirmation events
logging.WARNING     # 30 - Something unexpected
logging.ERROR       # 40 - Serious problem
logging.CRITICAL    # 50 - Very serious problem

# Set level - O(1)
logger.setLevel(logging.WARNING)

# Only WARNING and above are logged
logger.debug('Not logged')      # Skipped
logger.warning('Is logged')
```

## Common Patterns

### Application Logging

```python
import logging

# Setup - O(1)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)

logger = logging.getLogger(__name__)

def process_file(filename):
    try:
        logger.info(f'Processing {filename}')
        with open(filename) as f:
            data = f.read()  # O(n)
        logger.debug(f'Read {len(data)} bytes')
        return process(data)
    except FileNotFoundError:
        logger.error(f'File not found: {filename}')
        return None
    except Exception as e:
        logger.exception(f'Unexpected error: {e}')
        return None
```

### Exception Logging

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = risky_operation()  # Might fail
except ValueError as e:
    logger.error(f'Invalid value: {e}')
except Exception as e:
    logger.exception('Unexpected error')    # Includes traceback
```

## Performance Considerations

### Message Formatting

```python
import logging

logger = logging.getLogger(__name__)

# Lazy formatting - O(1) if not logged
logger.debug('User %s logged in', username)  # Only format if DEBUG level

# vs eager formatting - O(k) always
logger.debug(f'User {username} logged in')   # Always format string

# Lazy approach is more efficient when DEBUG is disabled
```

### File I/O

```python
import logging

# File handler - cost depends on I/O and buffering
handler = logging.FileHandler('app.log')

# Buffering affects performance
# Default: buffered (fast)
# Unbuffered: flush each write (slow but safer)

# Rotating file handler - cost depends on I/O and rollover
rotating = logging.handlers.RotatingFileHandler(
    'app.log',
    maxBytes=1000000,  # 1MB
    backupCount=5      # Keep 5 backups
)
```

## Version Notes

- **Python 3.x**: `logging` module is available

## Related Modules

- **[sys.stderr](sys.md)** - Direct error output
- **[traceback](traceback.md)** - Exception details

## Best Practices

✅ **Do**:

- Use logging instead of print() for production
- Set appropriate log levels
- Use lazy formatting with %s
- Include context in messages
- Use exception() for exceptions

❌ **Avoid**:

- Logging sensitive information (passwords)
- Excessive debug logging in production
- Eager string formatting
- Using print() in libraries
