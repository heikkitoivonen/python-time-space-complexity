# argparse Module Complexity

The `argparse` module provides a framework for creating command-line argument parsers with automatic help and usage messages.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ArgumentParser()` | O(1) | O(1) | Create parser |
| `add_argument()` | O(1) | O(1) | Add single argument |
| `parse_args()` | O(n) | O(n) | n = number of CLI args |
| Help generation | O(m) | O(m) | m = total help text |

## Basic Usage

### Creating a Parser

```python
import argparse

# Create parser - O(1)
parser = argparse.ArgumentParser(description='My program')  # O(1)

# Add arguments - O(1) each
parser.add_argument('name', help='Your name')  # O(1)
parser.add_argument('--age', type=int, help='Your age')  # O(1)

# Parse arguments - O(n)
args = parser.parse_args()  # O(n) where n = CLI args
print(f"Name: {args.name}, Age: {args.age}")
```

### Argument Types

```python
import argparse

parser = argparse.ArgumentParser()

# Positional arguments - O(1)
parser.add_argument('input_file', help='Input file path')

# Optional arguments - O(1)
parser.add_argument('-o', '--output', help='Output file')
parser.add_argument('-v', '--verbose', action='store_true')  # Boolean flag
parser.add_argument('-n', '--number', type=int, default=10)  # Integer

# Parse - O(n)
args = parser.parse_args()
```

## Advanced Features

### Choices and Validation

```python
import argparse

parser = argparse.ArgumentParser()

# Limited choices - O(1)
parser.add_argument('--format', choices=['json', 'csv', 'xml'])

# Type conversion - O(1)
parser.add_argument('--count', type=int)

# Custom validation
def positive_int(value):
    ivalue = int(value)  # O(k) where k = string length
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be positive")
    return ivalue

parser.add_argument('--positive', type=positive_int)
```

### Subcommands

```python
import argparse

# Create main parser - O(1)
parser = argparse.ArgumentParser()

# Create subparsers - O(1)
subparsers = parser.add_subparsers(dest='command')

# Add subcommands - O(1) each
parser_a = subparsers.add_parser('add', help='Add item')
parser_a.add_argument('item')

parser_r = subparsers.add_parser('remove', help='Remove item')
parser_r.add_argument('item')

# Parse - O(n)
args = parser.parse_args()
```

## Common Patterns

### Command-Line Tool

```python
import argparse

def main():
    # Create parser - O(1)
    parser = argparse.ArgumentParser(
        description='File processor',
        epilog='Example: %(prog)s input.txt -o output.txt'
    )
    
    # Add arguments - O(1) each
    parser.add_argument('input', help='Input file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    
    # Parse - O(n)
    args = parser.parse_args()
    
    # Process
    process(args.input, args.output, args.verbose)

if __name__ == '__main__':
    main()
```

## Performance Notes

### Parsing Speed

```python
import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--count', type=int)

# Parsing is O(n) where n = number of arguments
args_list = ['--verbose', '--count', '10']

start = time.time()
args = parser.parse_args(args_list)  # O(3)
elapsed = time.time() - start
# Very fast for typical argument counts
```

## Version Notes

- **Python 2.x**: argparse available as backport
- **Python 3.x**: Built-in since Python 3.2
- **All versions**: O(n) parsing complexity

## Related Modules

- **[sys.argv](sys.md)** - Raw command-line arguments
- **[click](click.md)** - Alternative argument parsing (external)

## Best Practices

✅ **Do**:
- Use argparse for command-line tools
- Provide helpful descriptions
- Use subparsers for complex tools
- Validate arguments with type and choices

❌ **Avoid**:
- Manual sys.argv parsing
- Unclear help messages
- Too many positional arguments
