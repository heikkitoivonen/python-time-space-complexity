# subprocess Module Complexity

The `subprocess` module enables spawning new processes, connecting to I/O pipes, and obtaining return codes.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `run()` / `Popen()` | O(1) + exec time | O(1) | fork/exec overhead; process execution time dominates |
| `communicate()` | O(n) | O(n) | n = stdout + stderr size |
| `wait()` | O(1) + process | O(1) | Blocks until process exits |

## Basic Usage

```python
import subprocess

# Simple execution - O(p)
result = subprocess.run(['ls', '-l'])  # O(p) - process time

# Capture output - O(n)
result = subprocess.run(['echo', 'hello'], capture_output=True, text=True)
print(result.stdout)  # 'hello\n'

# Check return code - O(1)
if result.returncode == 0:
    print("Success")
```

## Process Communication

```python
import subprocess

# Execute with input - O(n)
result = subprocess.run(
    ['wc', '-w'],
    input='hello world\n',
    text=True,
    capture_output=True
)
print(result.stdout)  # '2\n'

# Check for errors - O(1)
result = subprocess.run(['false'], capture_output=True)
if result.returncode != 0:
    print("Command failed")
```

## Popen for Advanced Control

```python
import subprocess

# Create process - O(p)
process = subprocess.Popen(
    ['cat'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

# Communicate - O(n)
output, error = process.communicate(input='hello\n')
print(output)  # 'hello\n'
```

## Pipe Chaining

```python
import subprocess

# Pipeline - O(n)
proc1 = subprocess.Popen(['cat', 'file.txt'], stdout=subprocess.PIPE)
proc2 = subprocess.Popen(
    ['grep', 'pattern'],
    stdin=proc1.stdout,
    stdout=subprocess.PIPE,
    text=True
)
proc1.stdout.close()  # Allow proc1 to close

output, _ = proc2.communicate()  # O(n) - n = file size
```

## Version Notes

- **Python 3.5+**: `run()` recommended
- **Earlier**: Use `Popen()` and `communicate()`

## Best Practices

✅ **Do**:
- Use `run()` for simple commands
- Use `capture_output=True`
- Use `text=True` for string output
- Check return codes

❌ **Avoid**:
- Shell injection (use list, not string)
- Ignoring return codes
- No timeout protection
