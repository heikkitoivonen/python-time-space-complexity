# cgitb Module

⚠️ **REMOVED IN PYTHON 3.13**: The `cgitb` module was deprecated in Python 3.11 and removed in Python 3.13.

The `cgitb` module provides a CGI error handler that displays detailed tracebacks in HTML format for debugging CGI scripts.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enable()` | O(1) | O(1) | Install handler |
| `hook()` | O(1) | O(1) | Install hook |
| Traceback generation | O(n) | O(n) | n = stack depth |

## Basic Usage

### Enable HTML Error Handling

```python
#!/usr/bin/env python3

import cgitb

# Enable HTML error display - O(1)
cgitb.enable()

# Now any exception will show detailed HTML traceback
# instead of plain text

print("Content-Type: text/html\n")
print("<h1>My CGI Script</h1>")

# This error will show detailed traceback
undefined_variable  # NameError
```

### Custom Configuration

```python
import cgitb

# Enable with custom display - O(1)
cgitb.enable(display=1, logdir='/tmp/cgi_errors')

# display=1: show traceback
# logdir: save copies of tracebacks
```

## Error Handling Pattern

### Exception Handler

```python
import cgitb
import sys
from io import StringIO

def run_cgi_script():
    cgitb.enable()
    
    print("Content-Type: text/html\n")
    print("<h1>Processing</h1>")
    
    # Your CGI code
    try:
        result = 10 / 0  # Will trigger cgitb handler
    except ZeroDivisionError:
        # cgitb will catch and format it
        pass

if __name__ == "__main__":
    run_cgi_script()
```

## Manual Error Display

### Generating HTML Tracebacks

```python
import cgitb
import sys

def display_error():
    # Generate HTML traceback manually - O(n)
    try:
        result = int("not a number")
    except ValueError:
        # Get exception info - O(1)
        etype, value, tb = sys.exc_info()
        
        # Create handler - O(1)
        handler = cgitb.Hook(display=1, logdir='/tmp')
        
        # Format as HTML - O(n)
        html = handler(etype, value, tb)
        
        print("Content-Type: text/html\n")
        print(html)

display_error()
```

## Logging Errors

### Save Error Reports

```python
import cgitb
import os

# Setup error directory
error_dir = '/var/log/cgi_errors'
os.makedirs(error_dir, exist_ok=True)

# Enable with logging - O(1)
cgitb.enable(display=1, logdir=error_dir)

# Exceptions will be logged to disk
# and displayed in HTML format

print("Content-Type: text/html\n")
print("<h1>Safe to fail now</h1>")

# Error will be logged
1 / 0  # ZeroDivisionError
```

## Modern Alternatives

### Using Standard Logging

```python
# ✅ Modern approach: Use logging module
import logging
import traceback
from html import escape

logging.basicConfig(
    filename='/var/log/app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def safe_handler():
    try:
        # Your code
        result = 10 / 0
    except Exception as e:
        # Log error - O(1)
        logging.exception("CGI script failed")
        
        # Return error to user
        print("Content-Type: text/html\n")
        print("<h1>Error</h1>")
        print("<p>An error occurred. Please contact support.</p>")
```

### Using Framework Error Handling

```python
# ✅ Using Flask (recommended)
from flask import Flask
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_error(error):
    # Automatic HTML error page
    return f"<h1>Error</h1><p>{escape(str(error))}</p>", 500

@app.route('/')
def index():
    # If error occurs, it's handled automatically
    return undefined_var  # Error caught and displayed

if __name__ == '__main__':
    app.run()
```

### Using WSGI Middleware

```python
from wsgiref.simple_server import make_server
import traceback
from html import escape

class ErrorHandlingMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except Exception as e:
            # Generate error HTML - O(n)
            html = f"""
            <h1>Internal Server Error</h1>
            <pre>{escape(traceback.format_exc())}</pre>
            """
            
            start_response('500 Internal Server Error',
                         [('Content-Type', 'text/html')])
            return [html.encode()]

def simple_app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'Hello World']

app = ErrorHandlingMiddleware(simple_app)

if __name__ == '__main__':
    server = make_server('localhost', 8000, app)
    server.serve_forever()
```

## Removal Notice

```python
# ❌ DON'T: Use cgitb (removed in 3.13)
import cgitb
cgitb.enable()

# ✅ DO: Use modern alternatives
# - logging module for production
# - Framework error handling (Flask, Django, FastAPI)
# - Custom WSGI middleware
# - Proper monitoring/alerting tools
```

## Best Practices

```python
# ✅ DO: Use error handling in development
import cgitb
cgitb.enable()  # Use only in development

# ✅ DO: Log errors in production
import logging
logging.exception("Error details")

# ✅ DO: Show safe error messages to users
print("<h1>Error</h1>")
print("<p>An error occurred. Please try again later.</p>")

# ❌ DON'T: Show detailed tracebacks to users
# ❌ DON'T: Expose sensitive information
# ❌ DON'T: Use cgitb in production
```

## Related Modules

- [logging Module](logging.md) - Error logging
- [traceback Module](traceback.md) - Traceback handling
- [sys Module](sys.md) - System information
- [html Module](#) - HTML utilities
