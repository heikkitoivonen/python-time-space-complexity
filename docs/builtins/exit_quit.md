# exit() and quit() Functions

The `exit()` and `quit()` functions terminate the Python interpreter. Typically used in interactive mode.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `exit()` | O(1) | O(1) | Terminate immediately |
| `quit()` | O(1) | O(1) | Terminate immediately |

## Basic Usage

### Exit from Interactive Mode

```python
# In Python REPL:
>>> exit()
# Interpreter terminates

# Or:
>>> quit()
# Interpreter terminates

# Can also use Ctrl+D on Unix/Mac or Ctrl+Z+Enter on Windows
```

### Using sys.exit() in Scripts

```python
import sys

def main():
    if not valid_input():
        sys.exit(1)  # Exit with error code
    
    process_data()
    sys.exit(0)  # Exit successfully

if __name__ == "__main__":
    main()
```

## Exit Codes

### Exit Code Meanings

```python
import sys

# Exit codes convention:
# 0 = success
# non-zero = error

sys.exit(0)   # Success
sys.exit(1)   # General error
sys.exit(2)   # Misuse of shell command
sys.exit(126) # Command invoked cannot execute
sys.exit(127) # Command not found
```

### Checking Exit Code

```bash
# In shell:
$ python script.py
$ echo $?  # Prints exit code
# 0
```

## Difference Between exit() and quit()

### exit() vs quit()

```python
# Both behave identically in interactive mode
# In scripts, neither should be used - use sys.exit() instead

# ✅ DO: Use sys.exit() in scripts
import sys
sys.exit(0)

# ❌ DON'T: Use exit() or quit() in scripts
exit()  # May not work if site module not loaded
quit()  # May not work if site module not loaded
```

### In Scripts vs Interactive

```python
# REPL (interactive):
>>> exit
# <site._Printers.Quitter object at 0x...>

>>> exit()
# Quits interpreter

# Script (non-interactive):
# exit and quit are only available via site module
# Use sys.exit() instead
```

## Practical Examples

### Conditional Exit

```python
import sys

def validate_config(config_file):
    try:
        with open(config_file) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {config_file} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: {config_file} is not valid JSON")
        sys.exit(1)

if __name__ == "__main__":
    config = validate_config("config.json")
    process(config)
    sys.exit(0)
```

### Exit with Message

```python
import sys

def process_data(filename):
    if not filename:
        print("Error: Filename required")
        sys.exit(2)
    
    if not os.path.exists(filename):
        print(f"Error: File not found: {filename}")
        sys.exit(1)
    
    # Process file
    with open(filename) as f:
        data = f.read()
    
    return data

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: script.py <filename>")
        sys.exit(2)
    
    data = process_data(sys.argv[1])
    print(data)
    sys.exit(0)
```

### Exit in Exception Handler

```python
import sys
import logging

logging.basicConfig(level=logging.INFO)

try:
    result = risky_operation()
except Exception as e:
    logging.error(f"Operation failed: {e}")
    sys.exit(1)
else:
    logging.info("Operation succeeded")
    sys.exit(0)
finally:
    cleanup()
```

## Cleanup with finally

### Ensure Cleanup Runs

```python
import sys

def main():
    resource = acquire_resource()
    
    try:
        process(resource)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # This ALWAYS runs, even with sys.exit()
        cleanup(resource)

if __name__ == "__main__":
    main()
```

### Using atexit Module

```python
import sys
import atexit

def cleanup():
    print("Cleaning up...")
    # Cleanup code

# Register cleanup to run before exit
atexit.register(cleanup)

# Now cleanup() will run on any exit
sys.exit(0)
```

## Exit Status Conventions

### Standard Exit Codes

```python
import sys

# 0: Success
# 1: General errors
# 2: Misuse of shell builtin
# 126: Command cannot execute
# 127: Command not found
# 128+N: Fatal signal N
# 130: Script terminated by Ctrl+C (128 + 2)

def main():
    if validation_failed():
        sys.exit(1)  # General error
    
    if permission_denied():
        sys.exit(13)  # Permission denied
    
    if file_not_found():
        sys.exit(2)   # Misuse/not found
    
    sys.exit(0)  # Success

if __name__ == "__main__":
    main()
```

## Testing Exit Behavior

### Using pytest

```python
import pytest
import sys

def application_exit():
    sys.exit(42)

def test_exit_code():
    with pytest.raises(SystemExit) as exc_info:
        application_exit()
    
    assert exc_info.value.code == 42
```

### Using unittest

```python
import unittest
import sys

class TestExit(unittest.TestCase):
    def test_exit_code(self):
        with self.assertRaises(SystemExit) as cm:
            sys.exit(5)
        
        self.assertEqual(cm.exception.code, 5)
```

## Best Practices

```python
import sys

# ✅ DO: Use sys.exit() in scripts
import sys
sys.exit(0)

# ✅ DO: Use meaningful exit codes
sys.exit(1)  # Error

# ✅ DO: Print error message before exit
print("Error: something failed", file=sys.stderr)
sys.exit(1)

# ✅ DO: Use finally for cleanup
try:
    code()
finally:
    cleanup()

# ❌ DON'T: Use exit() in scripts
exit()  # May not work

# ❌ DON'T: Use exit() in libraries
# Libraries should raise exceptions, not exit

# ❌ DON'T: Exit silently
sys.exit(0)  # Should print why before exiting
```

## Related Modules

- [sys Module](../stdlib/sys.md) - System exit and status
- [atexit Module](../stdlib/atexit.md) - Register exit handlers
- [signal Module](../stdlib/signal.md) - Signal handling
