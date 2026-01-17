# secrets Module

The `secrets` module provides cryptographically strong random number generation for security-sensitive applications like password generation and token creation.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `token_bytes()` | O(n) | O(n) | n = number of bytes |
| `token_hex()` | O(n) | O(n) | n = number of bytes |
| `token_urlsafe()` | O(n) | O(n) | n = number of bytes |
| `choice()` | O(1) | O(1) | Cryptographically secure selection |
| `randbelow()` | O(1) | O(1) | Cryptographically secure random int |

## Token Generation

### Bytes and Hex Tokens

```python
import secrets

# Generate random bytes - O(n)
token = secrets.token_bytes(32)  # 32 random bytes

# Generate hex string - O(n)
hex_token = secrets.token_hex(16)
# Example: 'a3f7b2c9d1e4f8a5'

# Generate URL-safe token - O(n)
url_token = secrets.token_urlsafe(32)
# Example: 'pL_kZa7xX-vJmN5qR2sT_uV3wY6zA'
```

### Common Token Uses

```python
import secrets

# Session token - O(n)
session_id = secrets.token_urlsafe(32)

# Password reset link - O(n)
reset_token = secrets.token_hex(32)

# API key - O(n)
api_key = secrets.token_urlsafe(64)

# CSRF token - O(n)
csrf_token = secrets.token_hex(16)
```

## Random Selection

### Secure Choices

```python
import secrets

# Choose from sequence - O(1)
characters = 'abcdefghijklmnopqrstuvwxyz0123456789'
password = ''.join(secrets.choice(characters) for _ in range(12))

# Random element - O(1)
choices = ['apple', 'banana', 'cherry']
selected = secrets.choice(choices)
```

## Secure Integers

### Random Number Generation

```python
import secrets

# Random integer in range [0, k) - O(1)
random_int = secrets.randbelow(100)

# Inclusive range [a, b] - O(1)
def randint(a, b):
    return a + secrets.randbelow(b - a + 1)

rolls = [randint(1, 6) for _ in range(3)]  # 3 dice rolls
```

## Password Generation

### Strong Passwords

```python
import secrets
import string

def generate_password(length=16):
    # O(length)
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

pwd = generate_password(16)
print(f"Generated: {pwd}")
```

### Using Recipes

```python
import secrets
import string

def generate_secure_password(length=12):
    # Ensure mix of character types - O(length)
    while True:
        password = ''.join(
            secrets.choice(string.ascii_letters + string.digits + string.punctuation)
            for _ in range(length)
        )
        # Validate has upper, lower, digit, special
        if (any(c.isupper() for c in password) and
            any(c.islower() for c in password) and
            any(c.isdigit() for c in password)):
            return password
```

## Common Patterns

### Web Authentication

```python
import secrets

# Generate tokens for authentication - O(n)
def create_session_token():
    return secrets.token_urlsafe(32)

def create_password_reset_token():
    return secrets.token_hex(32)

def create_email_verification_token():
    return secrets.token_urlsafe(16)

# Store with expiration
session = {
    'token': create_session_token(),
    'user_id': 123,
    'expires': datetime.now() + timedelta(hours=24)
}
```

### Secure Lottery Selection

```python
import secrets

def lottery_selection(participants, winners=5):
    # O(1) per selection
    selected = []
    for _ in range(min(winners, len(participants))):
        idx = secrets.randbelow(len(participants))
        selected.append(participants.pop(idx))
    return selected

participants = list(range(100))
lucky = lottery_selection(participants, 5)
```

## Security Considerations

### Best Practices

```python
import secrets

# ✅ DO: Use secrets for security-sensitive data
password_reset_token = secrets.token_urlsafe()

# ✅ DO: Use sufficient length
token = secrets.token_hex(32)  # 64 hex chars (256 bits)

# ❌ DON'T: Use random module for security
import random
insecure_token = random.randbytes(16)  # Don't use!

# ❌ DON'T: Use insufficient entropy
short_token = secrets.token_hex(4)  # Too short for security
```

## Related Modules

- [random Module](random.md) - Non-cryptographic randomness
- [hashlib Module](hashlib.md) - Secure hashing
- [hmac Module](hmac.md) - Message authentication codes
- [ssl Module](ssl.md) - SSL/TLS security
