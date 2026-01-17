# io Module Complexity

The `io` module provides core I/O classes for working with binary and text data, including in-memory streams and file-like objects.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `StringIO()` creation | O(1) | O(1) | Create empty string buffer |
| `StringIO.write()` | O(n) amortized | O(n) | n = string length, amortized due to buffer resizing |
| `StringIO.read()` | O(n) | O(n) | n = available bytes |
| `BytesIO()` creation | O(1) | O(1) | Create empty bytes buffer |
| `BytesIO.write()` | O(n) amortized | O(n) | n = bytes length, amortized due to buffer resizing |
| `BytesIO.read()` | O(n) | O(n) | n = available bytes |
| `seek()` position change | O(1) | O(1) | Random access pointer |
| `tell()` get position | O(1) | O(1) | Return current position |

## In-Memory Text Streams

### StringIO Basics

```python
from io import StringIO

# Create in-memory text stream - O(1)
stream = StringIO()

# Write strings - O(k) amortized for k bytes
stream.write("Hello\n")   # O(5)
stream.write("World\n")   # O(5)

# Get all content - O(n)
content = stream.getvalue()  # O(11) for "Hello\nWorld\n"
print(content)
# Hello
# World

# Reset position to beginning - O(1)
stream.seek(0)

# Read all - O(n)
data = stream.read()
print(data)  # "Hello\nWorld\n"
```

### Writing and Reading

```python
from io import StringIO

stream = StringIO()

# Write data - O(k)
lines = ['apple', 'banana', 'cherry']
for line in lines:
    stream.write(line + '\n')

# Get value - O(n)
output = stream.getvalue()
print(output)
# apple
# banana
# cherry

# Reset and read line by line - O(n)
stream.seek(0)
for line in stream:  # O(n) iteration
    print(f"Line: {line.strip()}")

# Clear stream - O(1)
stream.close()
```

## In-Memory Binary Streams

### BytesIO Basics

```python
from io import BytesIO

# Create in-memory bytes stream - O(1)
stream = BytesIO()

# Write bytes - O(k) amortized
stream.write(b"Binary ")     # O(7)
stream.write(b"data")        # O(4)

# Get all content - O(n)
content = stream.getvalue()  # b"Binary data"
print(content)

# Reset and read - O(1) seek + O(n) read
stream.seek(0)
data = stream.read()
print(data)  # b"Binary data"
```

### Binary Data Manipulation

```python
from io import BytesIO
import struct

stream = BytesIO()

# Pack binary data - O(k) per write
stream.write(struct.pack('i', 42))      # 4 bytes
stream.write(struct.pack('f', 3.14))    # 4 bytes
stream.write(struct.pack('2s', b'AB'))  # 2 bytes

# Get packed data - O(n)
binary = stream.getvalue()  # 10 bytes total

# Unpack from stream - O(1) seek + O(n) read
stream.seek(0)
value1 = struct.unpack('i', stream.read(4))[0]
value2 = struct.unpack('f', stream.read(4))[0]
value3 = struct.unpack('2s', stream.read(2))[0]
```

## Stream Position Operations

### Seeking and Telling

```python
from io import StringIO

stream = StringIO("Hello World")

# Current position - O(1)
print(stream.tell())  # 0

# Seek to position - O(1)
stream.seek(6)
print(stream.tell())  # 6

# Read from position - O(n)
print(stream.read())  # "World"

# Seek from end - O(1)
stream.seek(-5, 2)  # 2 = os.SEEK_END
print(stream.read())  # "World"

# Seek from current - O(1)
stream.seek(0)
stream.read(5)       # Read "Hello"
stream.seek(1, 1)    # 1 = os.SEEK_CUR
print(stream.read())  # "World"
```

### Truncate and Resize

```python
from io import StringIO

stream = StringIO("Hello World")

# Get length via tell - O(1)
stream.seek(0, 2)  # Seek to end
size = stream.tell()
print(size)  # 11

# Truncate to position - O(1)
stream.seek(5)
stream.truncate()  # Truncate at position 5

# Get value after truncate - O(n)
print(stream.getvalue())  # "Hello"

# Truncate to size - O(1)
stream.truncate(3)
print(stream.getvalue())  # "Hel"
```

## Using Streams in Functions

### Capture Output

```python
from io import StringIO
import sys

# Capture stdout - O(1) setup
captured_output = StringIO()

# Redirect stdout - O(1)
original_stdout = sys.stdout
sys.stdout = captured_output

# Code writes to captured stream
print("Line 1")
print("Line 2")

# Restore stdout - O(1)
sys.stdout = original_stdout

# Get captured output - O(n)
output = captured_output.getvalue()
print(f"Captured:\n{output}")
```

### Stream Wrapping

```python
from io import StringIO, TextIOWrapper
from io import BytesIO

# Wrap BytesIO with text layer
bytes_stream = BytesIO()
text_stream = TextIOWrapper(bytes_stream, encoding='utf-8')

# Write text - O(k)
text_stream.write("Hello\nWorld\n")
text_stream.flush()  # O(1)

# Get bytes - O(n)
print(bytes_stream.getvalue())  # b"Hello\nWorld\n"
```

## Advanced Stream Operations

### Read Entire File-like Object

```python
from io import StringIO

def process_stream(stream):
    """Process any file-like object - O(n)"""
    lines = stream.readlines()  # O(n) read all lines
    return [line.strip() for line in lines]  # O(n) process

stream = StringIO("line1\nline2\nline3\n")
result = process_stream(stream)
print(result)  # ['line1', 'line2', 'line3']
```

### Read with Buffer

```python
from io import BytesIO

stream = BytesIO(b"x" * 1000)

# Read in chunks - O(n) total, O(1) per chunk
chunk_size = 100
while True:
    chunk = stream.read(chunk_size)  # O(k) per chunk
    if not chunk:
        break
    process(chunk)  # Process chunk

def process(data):
    print(f"Processing {len(data)} bytes")
```

### Seek Performance

```python
from io import BytesIO

# Large stream - O(1) space due to in-memory
stream = BytesIO(b"A" * 1000000)

# Random access is fast - O(1)
stream.seek(500000)
data = stream.read(100)

stream.seek(100000)
data = stream.read(100)

# Much faster than sequential file I/O
```

## Use Cases

### String Formatting

```python
from io import StringIO

def format_table(rows):
    """Format table without disk I/O"""
    output = StringIO()
    
    for row in rows:
        output.write(f"{row[0]:10} {row[1]:10} {row[2]:10}\n")
    
    return output.getvalue()

data = [
    ('Name', 'Age', 'Score'),
    ('Alice', '30', '95'),
    ('Bob', '25', '87')
]

table = format_table(data)
print(table)
```

### CSV Processing

```python
from io import StringIO
import csv

# Generate CSV in memory
output = StringIO()
writer = csv.writer(output)

# Write rows - O(n)
writer.writerow(['Name', 'Age', 'City'])
writer.writerow(['Alice', '30', 'NYC'])
writer.writerow(['Bob', '25', 'LA'])

# Get CSV string - O(n)
csv_data = output.getvalue()
print(csv_data)

# Parse CSV - O(n)
input_stream = StringIO(csv_data)
reader = csv.DictReader(input_stream)
for row in reader:
    print(row)
```

### JSON Processing

```python
from io import StringIO
import json

# Generate JSON in memory
data = {
    'users': [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25}
    ]
}

output = StringIO()

# Write JSON - O(n)
json.dump(data, output, indent=2)

# Get JSON string - O(n)
json_str = output.getvalue()
print(json_str)

# Parse JSON - O(n)
input_stream = StringIO(json_str)
parsed = json.load(input_stream)
```

## Common Patterns

### Multiline String Construction

```python
from io import StringIO

output = StringIO()

# Build multi-line string efficiently - O(n)
lines = [f"Line {i}\n" for i in range(100)]
for line in lines:
    output.write(line)

result = output.getvalue()  # Single string, no concatenation overhead
```

### Filter and Transform

```python
from io import StringIO

def filter_and_transform(text):
    """Process text with streaming"""
    input_stream = StringIO(text)
    output_stream = StringIO()
    
    # Process line by line - O(n)
    for line in input_stream:
        processed = line.upper().strip()
        output_stream.write(processed + '\n')
    
    return output_stream.getvalue()

result = filter_and_transform("hello\nworld\npython")
print(result)
```

## Performance Comparison

### StringIO vs String Concatenation

```python
from io import StringIO

# Bad: String concatenation - O(n²)
result = ""
for i in range(1000):
    result += f"Line {i}\n"  # Creates new string each time

# Good: StringIO - O(n)
output = StringIO()
for i in range(1000):
    output.write(f"Line {i}\n")
result = output.getvalue()

# StringIO is much faster for many writes
```

### File vs In-Memory

```python
from io import StringIO
import time

data = "x" * 1000

# File I/O - slower, disk bound
start = time.time()
with open('temp.txt', 'w') as f:
    for _ in range(1000):
        f.write(data)
file_time = time.time() - start

# In-memory - faster, CPU bound
start = time.time()
stream = StringIO()
for _ in range(1000):
    stream.write(data)
memory_time = time.time() - start

print(f"File: {file_time:.4f}s, Memory: {memory_time:.4f}s")
# Memory is typically 10-100x faster
```

## Memory Efficiency

### When to Use io Module

```python
from io import StringIO, BytesIO

# Good: Temporary buffers, testing
stream = StringIO()
stream.write(some_output)
assert "expected" in stream.getvalue()

# Good: In-memory formatting
output = StringIO()
for item in items:
    output.write(format_item(item))
result = output.getvalue()

# Avoid: Very large data (use generators/streaming)
# Don't use io for multi-megabyte datasets
```

## Related Documentation

- [Open Built-in](../builtins/open.md)
- [Pickle Module](pickle.md)
- [CSV Module](csv.md)
- [JSON Module](json.md)
