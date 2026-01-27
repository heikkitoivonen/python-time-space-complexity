# imaplib Module

The `imaplib` module provides IMAP4 client functionality for accessing email on IMAP servers.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `login()` | Varies | Varies | Network round‑trip, server auth |
| List mailboxes | Varies | Varies | Depends on server and response size |
| Fetch messages | Varies | Varies | Depends on server, message sizes, and network |

## Accessing IMAP Mailboxes

### Basic IMAP Operations

```python
import imaplib

# Connect - O(1)
imap = imaplib.IMAP4('imap.gmail.com')
imap.starttls()
imap.login('user@gmail.com', 'password')

# List mailboxes - O(n)
code, mailboxes = imap.list()
for mailbox in mailboxes:
    print(mailbox)

# Select mailbox - O(1)
imap.select('INBOX')

# Search - O(n)
code, ids = imap.search(None, 'ALL')
email_ids = ids[0].split()

# Fetch - O(n)
for email_id in email_ids[:5]:  # First 5
    code, data = imap.fetch(email_id, '(RFC822)')
    print(data[0][1])

# Close - O(1)
imap.close()
imap.logout()
```

## Related Documentation

- [smtplib Module](smtplib.md)
- [poplib Module](poplib.md)
