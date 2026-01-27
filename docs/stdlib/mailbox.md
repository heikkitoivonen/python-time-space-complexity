# mailbox Module

The `mailbox` module provides classes for reading, writing, and manipulating various mailbox formats (mbox, Maildir, MMDF, etc.).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Open mailbox | Varies | Varies | Depends on mailbox format and indexing |
| Add message | Varies | Varies | Depends on mailbox type and file I/O |
| Iterate messages | O(n) | O(1) | Sequential access |

## Working with Mailboxes

### Reading Mailbox

```python
import mailbox

# Open mbox - cost depends on format and file size
mbox = mailbox.mbox('mail.mbox')

# Iterate - O(n)
for key, message in mbox.items():
    print(message['Subject'])
    print(message.get_payload())

mbox.close()
```

### Adding Messages

```python
import mailbox
from email.message import EmailMessage

# Open - cost depends on format and file size
mbox = mailbox.mbox('mail.mbox')

# Create message - O(1)
msg = EmailMessage()
msg['Subject'] = 'Test'
msg.set_content('Hello')

# Add - cost depends on mailbox type and I/O
key = mbox.add(msg)

# Flush to disk - cost depends on pending changes
mbox.flush()
mbox.close()
```

## Related Documentation

- [email Module](email.md)
- [smtplib Module](smtplib.md)
