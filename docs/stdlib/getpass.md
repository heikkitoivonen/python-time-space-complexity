# Getpass Module

The `getpass` module provides utilities for prompting the user for passwords without echoing the input to the screen.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getpass()` | O(n) | O(n) | n = password length |
| `getuser()` | O(1) | O(1) | Get current user |

## Common Operations

### Getting Password Input

```python
import getpass

# O(n) where n = password length
password = getpass.getpass()
# Prompts: "Password: " (input hidden)

# Custom prompt - O(n)
password = getpass.getpass(prompt="Enter secret: ")

# Returns: user-entered password as string
# Input is not echoed to screen
```

### Getting Current User

```python
import getpass

# O(1) - get current user from environment
username = getpass.getuser()
# Returns: string like 'john', 'alice', etc.

# Works across platforms
import platform
print(f"User {username} on {platform.system()}")
```

## Common Use Cases

### Secure Login Prompt

```python
import getpass

def login():
    """Prompt for credentials - O(n+m)"""
    # O(1) - auto-fill username
    username = getpass.getuser()
    
    # O(n) where n = password length
    password = getpass.getpass(f"Password for {username}: ")
    
    if password == "correct_password":
        print("Login successful")
        return True
    else:
        print("Login failed")
        return False
```

### Authenticate User

```python
import getpass
import hashlib

def authenticate(stored_hash):
    """Authenticate against stored password hash - O(n)"""
    # O(n) to get password
    password = getpass.getpass("Enter password: ")
    
    # O(n) to hash (depends on hash algorithm)
    entered_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        b'salt',
        iterations=100000
    )
    
    # O(n) to compare
    return entered_hash == stored_hash
```

### Multi-step Authentication

```python
import getpass

def multi_factor_auth(max_attempts=3):
    """Multi-step authentication - O(n)"""
    attempts = 0
    
    while attempts < max_attempts:
        # O(1) - get username
        username = getpass.getuser()
        
        # O(n) - get password where n = length
        password = getpass.getpass("Password: ")
        
        # O(n) - get 2FA code
        code = getpass.getpass("2FA Code: ")
        
        # Verify credentials (simplified)
        if verify_credentials(username, password, code):
            return True
        
        attempts += 1
        if attempts < max_attempts:
            print(f"Invalid. {max_attempts - attempts} attempts left.")
    
    return False

def verify_credentials(user, pwd, code):
    # Placeholder
    return len(pwd) > 0 and len(code) == 6
```

### Secure Config Input

```python
import getpass
import json

def setup_database_config():
    """Get database credentials securely - O(n)"""
    config = {
        'host': input("Database host: "),  # O(n)
        'port': int(input("Port [5432]: ") or 5432),  # O(n)
        'database': input("Database name: "),  # O(n)
        'username': input("Username: "),  # O(n)
        # O(n) - password hidden
        'password': getpass.getpass("Password: "),
    }
    
    return config

# Usage - O(n) for user interaction
config = setup_database_config()

# Don't print password!
print(f"Connecting to {config['host']}:{config['port']}/{config['database']}")
```

## Performance Tips

### Cache Username

```python
import getpass

# Bad: Call getuser() multiple times
def get_user_from_env():
    user = getpass.getuser()  # O(1) but repeated
    return user

# Good: Call once and cache
_cached_user = None

def get_current_user():
    global _cached_user
    if _cached_user is None:
        _cached_user = getpass.getuser()  # O(1) first call
    return _cached_user
```

### Validate During Input

```python
import getpass

def get_password_with_validation(min_length=8):
    """Get password with validation - O(n*m)"""
    while True:
        # O(n) where n = password length
        password = getpass.getpass("Password (min 8 chars): ")
        
        # O(n) to validate length
        if len(password) >= min_length:
            return password
        
        # Validation failed, try again
        print("Password too short. Try again.")

# Usage - O(n*m) where m = attempts
password = get_password_with_validation()
```

### Securely Handle Sensitive Data

```python
import getpass
import os

def secure_password_entry():
    """Get and clear password securely - O(n)"""
    import sys
    
    # O(n) to get password
    password = getpass.getpass()
    
    try:
        # Use password
        authenticate(password)
    finally:
        # O(n) to clear from memory (best effort)
        # Python doesn't guarantee memory clearing, but this helps
        password = '0' * len(password)
        password = None
        
        # Force garbage collection in sensitive cases
        import gc
        gc.collect()
```

## Version Notes

- **Python 2.6+**: getpass() and getuser()
- **Python 3.x**: Full support on all platforms
- **Unix/Linux**: Disables terminal echo with termios
- **Windows**: Uses Windows API for hiding input
- **macOS**: Uses termios (Unix-based)

## Related Documentation

- [Input/Output](builtins/input.md) - Regular input()
- [Sys Module](sys.md) - System interactions
- [Os Module](os.md) - Environment variables
