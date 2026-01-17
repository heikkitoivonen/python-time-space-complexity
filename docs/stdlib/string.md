# String Module Complexity

The `string` module provides string constants and utilities for string formatting and templating.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `string.ascii_letters` | O(1) | O(1) | Constant access |
| `string.digits` | O(1) | O(1) | Constant access |
| `Formatter.format()` | O(n) | O(n) | Format string |
| `Template.substitute()` | O(n) | O(n) | Template substitution |
| `capwords(string)` | O(n) | O(n) | Capitalize each word; splits on whitespace |

## String Constants

### Predefined Constants

#### Time Complexity: O(1)

```python
import string

# Access constants: O(1)
letters = string.ascii_letters  # All letters
lowercase = string.ascii_lowercase  # a-z
uppercase = string.ascii_uppercase  # A-Z
digits = string.digits  # 0-9
hex_digits = string.hexdigits  # 0-9a-fA-F
octdigits = string.octdigits  # 0-7
punctuation = string.punctuation  # !"#$%&...

# Generate character set: O(1)
valid_chars = string.ascii_letters + string.digits
# 'abcdefghijklmnopqrstuvwxyzABC...0123456789'
```

#### Space Complexity: O(1)

```python
import string

letters = string.ascii_letters  # O(1) - constants
```

## String Formatting

### Formatter Class

#### Time Complexity: O(n)

Where n = length of format string.

```python
from string import Formatter

# Create formatter: O(1)
fmt = Formatter()

# Format string: O(n) where n = string length
result = fmt.format('{0} {1}', 'Hello', 'World')  # O(n)

# Parse format string: O(n)
parsed = fmt.parse('{name}: {value:.2f}')  # O(n)

# Format with kwargs: O(n)
result = fmt.format_map({'x': 10, 'y': 20})  # O(n)
```

#### Space Complexity: O(n)

```python
from string import Formatter

fmt = Formatter()
result = fmt.format('{0} {1}', 'a', 'b')  # O(n) for result
```

## Template Strings

### Template Substitution

#### Time Complexity: O(n)

```python
from string import Template

# Create template: O(n) to parse
template = Template('$name is $age years old')

# Substitute: O(n) where n = template length
result = template.substitute(name='Alice', age=30)  # O(n)

# Safe substitute (no error on missing): O(n)
result = template.safe_substitute(
    name='Bob'  # age missing
)  # O(n) - returns 'Bob is $age years old'
```

#### Space Complexity: O(n)

```python
from string import Template

template = Template('Hello $name')  # O(n)
result = template.substitute(name='World')  # O(n)
```

## Practical Functions

### capwords()

#### Time Complexity: O(n)

```python
from string import capwords

# Capitalize words: O(n)
text = 'hello world python'
capitalized = capwords(text)  # O(n) = 'Hello World Python'

# With separator: O(n)
text = 'hello-world-python'
result = capwords(text, sep='-')  # O(n)
```

#### Space Complexity: O(n)

```python
from string import capwords

result = capwords('hello world')  # O(n) for result string
```

## Common Patterns

### Generate Valid Characters

```python
import string

def is_valid_identifier(char_set):
    """Check character validity: O(1)"""
    valid = string.ascii_letters + string.digits + '_'  # O(1)
    return all(c in valid for c in char_set)  # O(n)

# Usage
if is_valid_identifier('my_var123'):
    print("Valid")
```

### Template-Based Formatting

```python
from string import Template

def generate_email(user_data):
    """Generate email from template: O(n)"""
    template = Template('''
Dear $name,
Thank you for your purchase of $item.
Total: $${amount}
    ''')  # O(n) template creation
    
    return template.substitute(**user_data)  # O(n)

# Usage
result = generate_email({
    'name': 'Alice',
    'item': 'Book',
    'amount': '29.99'
})
```

### Random String Generation

```python
import string
import random

def generate_password(length=12):
    """Generate random password: O(n)"""
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))  # O(n)

# Usage
password = generate_password(16)  # O(16)
```

### Filter by Character Class

```python
import string

def extract_digits(text):
    """Extract digits: O(n)"""
    return ''.join(c for c in text if c in string.digits)  # O(n)

def extract_letters(text):
    """Extract letters: O(n)"""
    return ''.join(c for c in text if c in string.ascii_letters)  # O(n)

# Usage
text = 'abc123def456'
digits = extract_digits(text)  # O(n) = '123456'
letters = extract_letters(text)  # O(n) = 'abcdef'
```

### Configuration File Parsing

```python
from string import Template
import os

def load_config(template_file, values):
    """Load and substitute config: O(n)"""
    with open(template_file) as f:
        template_text = f.read()  # O(n) read
    
    template = Template(template_text)  # O(n) parse
    return template.safe_substitute(values)  # O(n) substitute
```

## Formatter vs Template

### Comparison

```python
from string import Formatter, Template

# Formatter (powerful, complex)
fmt = Formatter()
result = fmt.format('{name}: {value:.2f}', name='Price', value=19.99)
# More features, format specs

# Template (simple, safer)
tmpl = Template('$name: ${value}')
result = tmpl.substitute(name='Price', value='$19.99')
# Safer with user input

# Both O(n) complexity
```

## Performance Characteristics

### Best Practices

```python
import string

# Good: Cache character sets
valid_chars = set(string.ascii_letters + string.digits)  # O(n) once
for char in user_input:  # O(m)
    if char in valid_chars:  # O(1) with set

# Good: Use Template for user input
template = Template('Hello $name')  # Safer than f-strings

# Avoid: String concatenation
result = ''
for i in range(100):
    result += string.ascii_letters[i % 26]  # O(n^2)!

# Better: Use join
result = ''.join(string.ascii_letters[i % 26] for i in range(100))  # O(n)
```

## Version Notes

- **Python 3.x**: Full string module support
- **Python 3.3+**: Formatter improvements

## Related Documentation

- [Textwrap Module](textwrap.md) - Text wrapping
- [Re Module](re.md) - Regular expressions
