# smtpd Module

⚠️ **REMOVED IN PYTHON 3.12**: The `smtpd` module was deprecated and removed in Python 3.12. Use `aiosmtpd` or another `asyncio`-based server.

The `smtpd` module implements an SMTP server (daemon), allowing you to receive and process email.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Server startup | O(1) | O(1) | Listen on port |
| Handle message | O(n) | O(n) | n = message size |
| Run loop | O(m) | O(m) | m = concurrent connections |

## Creating SMTP Server

### Simple SMTP Listener

```python
# Legacy example (Python <= 3.11)
import smtpd
import asyncore

class MyServer(smtpd.SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data):
        """Process received message - O(n)"""
        print(f"From: {mailfrom}")
        print(f"To: {rcpttos}")
        print(f"Message:\\n{data.decode()}")
        return  # Accept message

# Create server - O(1)
server = MyServer(('localhost', 25), None)

# Run event loop - O(m)
asyncore.loop()
```

## Related Documentation

- [smtplib Module](smtplib.md)
- [asyncore Module](asyncore.md)
