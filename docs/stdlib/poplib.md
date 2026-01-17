# poplib Module

The `poplib` module provides POP3 client functionality for retrieving emails from POP3 servers.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Connect | O(1) + network latency | O(1) | Network latency and auth handshake dominate |
| List messages | O(n) | O(n) | n = messages |
| Retrieve | O(n) | O(n) | n = message size |

## Retrieving Mail via POP3

### Basic POP3 Operations

```python
import poplib

# Connect - O(1)
pop = poplib.POP3('pop.gmail.com', 995)  # SSL
pop.user('user@gmail.com')
pop.pass_('password')

# Get message count - O(1)
num_messages = len(pop.list()[1])

# List messages - O(n)
response, messages, octets = pop.list()
for msg_info in messages:
    print(msg_info)

# Retrieve message - O(n)
response, lines, octets = pop.retr(1)
message_text = b'\r\n'.join(lines).decode()
print(message_text)

# Delete message - O(1)
pop.dele(1)

# Commit changes - O(1)
pop.quit()
```

## Related Documentation

- [imaplib Module](imaplib.md)
- [smtplib Module](smtplib.md)
