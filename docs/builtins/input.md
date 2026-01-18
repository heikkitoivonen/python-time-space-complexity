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

## Common Patterns

### Menu Selection

```python
# Simple menu - O(k)
def show_menu():
    print("1. Option A")
    print("2. Option B")
    print("3. Exit")
    choice = input("Choose: ")  # O(k)
    return choice

# Usage
choice = show_menu()  # O(k)
if choice == "1":
    do_a()
elif choice == "2":
    do_b()
```

### Validation Loop

```python
# Repeat until valid input - O(n*k)
def get_positive_number():
    while True:
        try:
            num_str = input("Enter positive number: ")  # O(k)
            num = int(num_str)  # O(k)
            if num > 0:
                return num
            print("Must be positive")
        except ValueError:
            print("Invalid number")

# Usage - might need multiple attempts
value = get_positive_number()  # O(k) per attempt
```

### Yes/No Question

```python
# Simple yes/no - O(k)
def confirm(message):
    while True:
        response = input(f"{message} (yes/no): ").lower()  # O(k)
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        print("Please answer yes or no")

# Usage
if confirm("Delete file?"):  # O(k)
    delete_file()
```

## Error Handling

### Handling Input Errors

```python
# Catch conversion errors - O(k)
try:
    age = int(input("Age: "))  # O(k)
except ValueError:
    print("Invalid age")
    age = 0

# Catch EOF (Ctrl+D on Unix, Ctrl+Z on Windows)
try:
    name = input("Name: ")  # O(k)
except EOFError:
    print("Input cancelled")
    name = ""

# Catch keyboard interrupt (Ctrl+C)
try:
    data = input("Data: ")  # O(k)
except KeyboardInterrupt:
    print("\nCancelled")
    data = ""
```

## Advanced Patterns

### Interactive Session

```python
# Multi-step input session - O(n*k)
def interactive_form():
    print("Fill in the form:")
    
    data = {}
    fields = ['name', 'email', 'phone']
    
    for field in fields:  # O(n) iterations
        value = input(f"Enter {field}: ")  # O(k) per field
        data[field] = value
    
    return data

# Usage - O(n*k)
user_data = interactive_form()
```

### Parsing Structured Input

```python
# Parse CSV-like input - O(n*m)
print("Enter records (name,age,city):")
records = []

while True:
    line = input("Record (empty to stop): ")  # O(k)
    if not line:
        break
    
    # Parse - O(k)
    fields = line.split(',')  # O(k)
    record = {
        'name': fields[0].strip(),  # O(k)
        'age': fields[1].strip(),
        'city': fields[2].strip()
    }
    records.append(record)  # O(1)

# Total: O(n*m) where n = records, m = avg fields
```

## Input from Files (Not input())

```python
# input() reads from keyboard only
# For file input, use open()

# Read from file - O(k) per line
with open('data.txt', 'r') as f:
    for line in f:  # O(1) each iteration
        # line includes newline, unlike input()
        line = line.strip()  # O(k) to remove it
        process(line)

# Read all at once - O(n)
with open('data.txt', 'r') as f:
    all_lines = f.readlines()  # O(n)
```

## Input in Scripts vs Interactive

### Interactive Mode

```python
# Works in interactive Python
name = input("Name: ")  # O(k) - waits for user
print(f"Hello, {name}")
```

### Script Mode

```python
# Script with input() - O(k)
#!/usr/bin/env python3

name = input("What is your name? ")  # O(k)
age = int(input("What is your age? "))  # O(k)
print(f"Hello {name}, you are {age} years old")
```

### Testing Scripts with input()

```python
# For testing, redirect stdin or mock input()
import sys
from io import StringIO

# Simulate user input
sys.stdin = StringIO("Alice\n30\n")

name = input()  # O(k) - reads "Alice"
age = int(input())  # O(k) - reads "30"

print(f"{name} is {age}")
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
- Validate and convert input with error handling
- Use `strip()` to remove whitespace
- Provide clear prompts
- Use file input for large data sets

❌ **Avoid**:

- Using `input()` in production servers (won't work)
- Forgetting input returns a string (requires conversion)
- Assuming input is safe (validate it!)
- Using `input()` for performance-critical code
- Trusting user input without validation
