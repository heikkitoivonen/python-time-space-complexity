# Shlex Module

The `shlex` module provides tools for writing simple syntactic analyzers and parsing shell-like syntax.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `split(string)` | O(n) | O(n) | n = string length |
| `quote(string)` | O(n) | O(n) | n = string length |
| `shlex()` | O(1) | O(1) | Create parser |
| `get_token()` | O(k) | O(k) | k = token length |

## Common Operations

### Simple String Splitting

```python
import shlex

# O(n) where n = string length
text = 'echo "Hello World" --flag value'

# Smart split respecting quotes - O(n)
tokens = shlex.split(text)
# Returns: ['echo', 'Hello World', '--flag', 'value']

# Compare to naive split - O(n) but loses quotes
naive = text.split()
# Returns: ['echo', '"Hello', 'World"', '--flag', 'value']
```

### Quoting Strings

```python
import shlex

# O(n) where n = string length
text = "Hello World"

# O(n) - add shell quoting if needed
quoted = shlex.quote(text)
# Returns: "'Hello World'" on Unix

# For use in shell commands
cmd = f'echo {shlex.quote(text)}'
# Safely executable as shell command
```

## Common Use Cases

### Parsing Command-Line Arguments

```python
import shlex

def parse_command_line(command_str):
    """Parse shell-like command - O(n)"""
    # O(n) to split into tokens
    tokens = shlex.split(command_str)
    
    if not tokens:
        return None, []
    
    # O(1) to get command, O(k) for args where k = arg count
    cmd = tokens[0]
    args = tokens[1:]
    
    return cmd, args

# Usage - O(n)
cmd, args = parse_command_line('git commit -m "Initial commit"')
# cmd: 'git'
# args: ['commit', '-m', 'Initial commit']
```

### Parsing Configuration Lines

```python
import shlex

def parse_config_line(line):
    """Parse config file line - O(n)"""
    # O(n) to tokenize
    tokens = shlex.split(line, comments=True)
    
    if not tokens:
        return None, None
    
    # O(1) to extract key-value
    key = tokens[0]
    value = tokens[1] if len(tokens) > 1 else None
    
    return key, value

# Usage - O(n)
line = 'database_url "postgresql://localhost/mydb"'
key, value = parse_config_line(line)
# key: 'database_url'
# value: 'postgresql://localhost/mydb'
```

### Building Safe Shell Commands

```python
import shlex
import subprocess

def run_command_safely(*args):
    """Build and run safe shell command - O(n)"""
    # O(n) where n = total arg length
    # shlex.quote each argument - O(k) per arg
    safe_args = [shlex.quote(str(arg)) for arg in args]
    
    # O(k) to join where k = arg count
    command = ' '.join(safe_args)
    
    # Safe to execute - O(m) for subprocess
    result = subprocess.run(command, shell=True, capture_output=True)
    return result.stdout.decode()

# Usage - O(n)
output = run_command_safely('echo', 'Hello "World"', 'with $variables')
# Safely escapes special characters
```

### Interactive Shell Parser

```python
import shlex

class ShellParser:
    """Parse interactive shell input - O(n) per line"""
    
    def __init__(self):
        # O(1) - create parser
        self.lexer = shlex.shlex(instream=None, posix=True)
    
    def parse_command(self, command_str):
        """Parse command string - O(n)"""
        # O(1) to set input
        self.lexer.input(command_str)
        
        tokens = []
        
        # O(n) where n = string length, O(k) per token
        while True:
            token = self.lexer.get_token()  # O(k) where k = token length
            if not token:
                break
            tokens.append(token)
        
        return tokens

# Usage - O(n)
parser = ShellParser()
tokens = parser.parse_command('ls -la "/home/user/My Documents"')
# ['ls', '-la', '/home/user/My Documents']
```

### Handling Different Quote Styles

```python
import shlex

def parse_with_options(text, posix=True, comments=False):
    """Parse with different behaviors - O(n)"""
    # O(n) - posix mode handles backslashes differently
    tokens = shlex.split(text, posix=posix, comments=comments)
    
    return tokens

# Usage - O(n)
posix_style = parse_with_options('echo "$VAR"')     # O(n)
non_posix = parse_with_options('echo "$VAR"', posix=False)  # O(n)

# Comments enabled - O(n)
with_comment = parse_with_options('command arg1  # this is a comment', 
                                   comments=True)
```

### Customizing Parser Behavior

```python
import shlex

def parse_custom_syntax(text):
    """Parse with custom syntax rules - O(n)"""
    # O(1) - create custom parser
    lexer = shlex.shlex(text, posix=True)
    
    # O(1) - customize behavior
    lexer.whitespace_split = False  # Default - split on whitespace
    lexer.wordchars += '@.-'  # Add to word characters
    
    # Custom delimiters - O(1)
    lexer.delimiters = '|><;'  # Shell-like delimiters
    
    tokens = []
    
    # O(n) to tokenize
    while True:
        token = lexer.get_token()  # O(k)
        if not token:
            break
        tokens.append(token)
    
    return tokens

# Usage - O(n)
tokens = parse_custom_syntax('email@example.com | filter')
```

## Performance Tips

### Cache Common Parse Results

```python
import shlex

class CommandCache:
    """Cache parsed commands - O(1) lookup"""
    
    def __init__(self):
        self._cache = {}
    
    def get_tokens(self, command):
        """Get tokens with caching - O(1) if cached"""
        if command not in self._cache:
            # O(n) first time where n = command length
            self._cache[command] = shlex.split(command)
        
        # O(1) return cached
        return self._cache[command]

# Usage
cache = CommandCache()
tokens = cache.get_tokens('git commit -m "msg"')  # O(n)
tokens = cache.get_tokens('git commit -m "msg"')  # O(1) - cached
```

### Batch Parsing

```python
import shlex

def parse_multiple_commands(commands):
    """Parse multiple commands efficiently - O(n)"""
    # O(n) where n = total characters across all commands
    return [shlex.split(cmd) for cmd in commands]

# Usage - O(n)
commands = [
    'ls -la',
    'grep pattern file.txt',
    'sed "s/old/new/g" file'
]
parsed = parse_multiple_commands(commands)
```

### Use wordchars for Performance

```python
import shlex

def efficient_parse(text, word_chars=None):
    """Optimize parsing with custom word chars - O(n)"""
    lexer = shlex.shlex(text)
    
    if word_chars:
        # O(k) where k = number of extra chars
        lexer.wordchars += word_chars
    
    # Now parsing is more efficient for those chars
    tokens = []
    while True:
        token = lexer.get_token()
        if not token:
            break
        tokens.append(token)
    
    return tokens

# Usage - O(n)
# Treats email addresses as single tokens
tokens = efficient_parse('contact user@example.com', '@.')
```

## Version Notes

- **Python 2.6+**: Basic functionality
- **Python 3.3+**: shlex.quote() available
- **Python 3.x**: Full POSIX compliance

## Related Documentation

- [Subprocess Module](subprocess.md) - Running shell commands
- [Argparse Module](argparse.md) - Argument parsing
- [Re Module](re.md) - Regular expressions
