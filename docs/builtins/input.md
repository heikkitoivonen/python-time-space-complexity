# input() Function Complexity

The `input()` function reads a line of text from standard input (keyboard), displays an optional prompt, and returns the input as a string.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `input()` | O(k) | O(k) | k = line length |
| `input(prompt)` | O(k) | O(k) | k = line length |

## Basic Input

### Reading User Input

```python
# Read single line - O(k) where k = line length
name = input()  # Waits for user input
# User types: "Alice"
# Result: "Alice" - O(5)

# With prompt - O(k)
name = input("What is your name? ")  # O(k)
# Displays prompt and waits for input
```

### Prompt Display

```python
# Prompt is displayed before input - O(m) for prompt, O(k) for input
age = input("Enter your age: ")  # O(m + k)
# m = prompt length, k = input length

# Complex prompt - O(m)
message = input(f"Hi {name}, what's your age? ")  # O(m + k)
```

## Processing Input

### String Processing

```python
# input() returns string - requires conversion
age_str = input("Age: ")  # O(k)
age = int(age_str)  # O(k) - string to int conversion

price_str = input("Price: ")  # O(k)
price = float(price_str)  # O(k) - string to float conversion

# Parse multiple values
data = input("Enter two numbers: ")  # "5 10" - O(k)
num1, num2 = map(int, data.split())  # O(k) - split and convert
```

### Stripping Whitespace

```python
# input() automatically strips trailing newline
user_input = input("Enter name: ")  # O(k)
# If user types "Alice\n", result is "Alice"

# But leading/trailing spaces are preserved
name = input("Name: ")  # "  Alice  " - O(k)
name = name.strip()  # O(k) - remove spaces
```

## Reading Multiple Lines

### Sequential Input

```python
# Read multiple lines - O(n*k) where n = lines, k = avg length
lines = []
print("Enter 3 numbers (one per line):")

for _ in range(3):
    line = input()  # O(k) per line
    lines.append(line)  # O(1)

# Total: O(3*k) = O(n*k)
```

### Reading Until Empty

```python
# Read until empty line - O(n*k)
lines = []
print("Enter lines (empty line to stop):")

while True:
    line = input()  # O(k) per line
    if not line:  # Empty line
        break
    lines.append(line)  # O(1)

# Total: O(n*k) where n = number of lines
```

## Performance Considerations

### Input Speed

```python
# input() is relatively slow (I/O operation)
import time

start = time.time()
value = input("Enter: ")  # O(k) - slow (depends on user)
elapsed = time.time() - start  # Could be seconds!

# For reading many lines from files, use file operations instead
# File I/O is faster than keyboard input
```

### Batch Processing

```python
# If you have many values to read, consider:
# 1. File input (faster)
# 2. Command-line arguments (faster)
# 3. Batch input in one line

# Option 1: File input - O(n)
with open('data.txt', 'r') as f:
    values = f.read().split()  # O(n)

# Option 2: Command-line - O(1)
import sys
values = sys.argv[1:]  # O(1)

# Option 3: Batch input - O(k)
values = input("Enter all values: ").split()  # O(k)
```

## Version Notes

- **Python 2.x**: `raw_input()` for strings, `input()` for evaluation (different!)
- **Python 3.x**: `input()` always returns string (recommended)
- **All versions**: `input()` reads from stdin

## Related Functions

- **[open()](open.md)** - Read from files
- **sys.stdin** - Direct stdin access
- **[print()](print.md)** - Output to stdout

## Best Practices

✅ **Do**:

- Use `input()` for interactive programs
- Use file input for large data sets

❌ **Avoid**:

- Using `input()` for performance-critical code
