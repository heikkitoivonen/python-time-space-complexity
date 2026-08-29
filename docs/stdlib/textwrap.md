# Textwrap Module Complexity

The `textwrap` module provides utilities for formatting and wrapping text while preserving formatting like indentation.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wrap(text, width)` | O(n) | O(n) | Wrap text to width; n = text length |
| `fill(text, width)` | O(n) | O(n) | Fill and return string |
| `dedent(text)` | O(n) | O(n) | Remove common indent |
| `indent(text, prefix)` | O(n) | O(n) | Add prefix to lines |
| `shorten(text, width)` | O(n) | O(n) | Shorten to width |

## Text Wrapping

### wrap()

#### Time Complexity: O(n)

Where n = text length.

```python
from textwrap import wrap

# Wrap text: O(n) where n = characters
text = "This is a long piece of text that needs to be wrapped to fit within a specific width."
lines = wrap(text, width=40)
# ['This is a long piece of text that', 
#  'needs to be wrapped to fit within a',
#  'specific width.']

# Wrap with break_long_words: O(n)
text = "supercalifragilisticexpialidocious"
lines = wrap(text, width=10, break_long_words=True)  # O(n)

# Wrap with break_on_hyphens: O(n)
text = "The mother-in-law was very helpful"
lines = wrap(text, width=20, break_on_hyphens=True)  # O(n)
```

#### Space Complexity: O(n)

```python
from textwrap import wrap

# Result list of lines
lines = wrap(long_text, width=40)  # O(n) space for all lines
```

### fill()

#### Time Complexity: O(n)

```python
from textwrap import fill

# Fill text: O(n) - wraps then joins
text = "This is a long piece of text"
filled = fill(text, width=30)  # O(n)
# "This is a long piece of\ntext"

# With indentation: O(n)
filled = fill(text, width=30, initial_indent=">>> ", subsequent_indent="... ")  # O(n)
```

#### Space Complexity: O(n)

```python
from textwrap import fill

# Result string stored
result = fill(long_text, width=40)  # O(n) space
```

## Indentation Handling

### dedent()

#### Time Complexity: O(n)

```python
from textwrap import dedent

# Remove common indent: O(n)
indented = """
    This is indented.
    So is this.
    And this too.
"""
dedented = dedent(indented)  # O(n)
# """
# This is indented.
# So is this.
# And this too.
# """

# Works with mixed indent levels: O(n)
mixed = """
    First line
        Indented more
    Back to first
"""
dedented = dedent(mixed)  # O(n)
```

#### Space Complexity: O(n)

```python
from textwrap import dedent

# Result string stored
result = dedent(text)  # O(n) space
```

### indent()

#### Time Complexity: O(n)

Where n = text length.

```python
from textwrap import indent

# Add indent: O(n) where n = characters
text = "First line\nSecond line\nThird line"
indented = indent(text, "  ")  # O(n)
# "  First line\n  Second line\n  Third line"

# With predicate: O(n) to check each line
indented = indent(text, "# ", predicate=lambda line: not line.startswith("#"))  # O(n)

# Common use: comment code
code = "x = 1\ny = 2"
commented = indent(code, "# ")  # O(n)
# "# x = 1\n# y = 2"
```

#### Space Complexity: O(n)

```python
from textwrap import indent

# Result string stored
result = indent(long_text, prefix)  # O(n) space
```

## Text Shortening

### shorten()

#### Time Complexity: O(n)

```python
from textwrap import shorten

# Shorten text: O(n) where n = length
long_text = "This is a very long piece of text that contains lots of words"
shortened = shorten(long_text, width=30)  # O(n)
# "This is a very long piece..."

# With placeholder: O(n)
shortened = shorten(long_text, width=30, placeholder="[...]")  # O(n)
# "This is a very long piece[...]"

# Break on word boundaries: O(n)
text = "Word1 Word2 Word3"
shortened = shorten(text, width=10)  # O(n)
# "Word1 [...]"
```

#### Space Complexity: O(n)

```python
from textwrap import shorten

# Result string stored
result = shorten(text, width=40)  # O(n) space
```

## Performance Characteristics

### Best Practices

```python
from textwrap import wrap, fill, dedent

# Good: dedent at source for cleaner code
code = dedent("""
    def hello():
        print("Hello")
""")

# Good: Use fill for single operation
filled = fill(text, width=80)  # O(n)

# Avoid: Multiple operations
lines = wrap(text, width=80)  # O(n)
filled = '\n'.join(lines)      # O(n) again

# Better: Use fill directly
filled = fill(text, width=80)  # O(n) once
```

### Large Text Handling

```python
from textwrap import wrap

# wrap() returns a list, so it still holds all lines in memory
lines = wrap(huge_text, width=80)  # O(n) memory

# For large inputs, wrap per paragraph to limit peak memory
for paragraph in huge_text.split("\n\n"):
    for line in wrap(paragraph, width=80):
        process(line)
```

## TextWrapper Class

### Time Complexity: O(1) init, O(n) per format

```python
from textwrap import TextWrapper

# Create wrapper with settings: O(1)
wrapper = TextWrapper(
    width=70,
    initial_indent="* ",
    subsequent_indent="  ",
    break_long_words=False,
)

# Use repeatedly: O(n) per use
wrapped1 = wrapper.wrap("First text")  # O(n)
wrapped2 = wrapper.wrap("Second text")  # O(n)
```

## Version Notes

- **Python 3.3+**: `indent()` function added
- **Python 3.4+**: Improvements to wrapping

## Related Documentation

- [String Module](string.md) - String constants
- [Shlex Module](shlex.md) - Shell-like parsing
