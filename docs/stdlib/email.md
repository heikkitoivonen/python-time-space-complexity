# Email Module

The `email` module provides utilities for constructing and parsing email messages.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `message_from_string()` | O(n) | O(n) | n = email size |
| `message_from_file()` | O(n) | O(n) | n = file size |
| `email.parser.Parser()` | O(n) | O(n) | Parse email |
| `EmailMessage()` | O(1) | O(1) | Create message |
| `set_content()` | O(n) | O(n) | n = content size |
| `get_payload()` | O(n) | O(n) | n = payload size |

## Common Operations

### Parsing Email Messages

```python
from email import message_from_string

# O(n) where n = email string length
email_text = """From: sender@example.com
To: recipient@example.com
Subject: Test Email

Hello, this is a test email.
"""

message = message_from_string(email_text)

# O(1) field access
from_addr = message['From']  # 'sender@example.com'
to_addr = message['To']      # 'recipient@example.com'
subject = message['Subject'] # 'Test Email'

# O(n) get full payload where n = size
body = message.get_payload()
```

### Parsing Email from File

```python
from email import message_from_file

# O(n) where n = file size
with open('email.eml', 'r') as f:
    message = message_from_file(f)

# O(1) access headers
subject = message['Subject']

# O(n) to get payload
body = message.get_payload()
```

### Creating Email Messages

```python
from email.message import EmailMessage

# O(1) to create
message = EmailMessage()

# O(n) to set each field where n = value length
message['Subject'] = 'Hello'       # O(n)
message['From'] = 'sender@ex.com'  # O(n)
message['To'] = 'recip@ex.com'     # O(n)
message['Date'] = 'Mon, 1 Jan 2024'# O(n)

# O(n) to set content where n = content size
message.set_content('This is the email body')

# O(n) to convert to string where n = message size
email_str = message.as_string()
```

### Handling Multipart Messages

```python
from email.message import EmailMessage

# O(1) to create
message = EmailMessage()

# O(n) to set headers
message['Subject'] = 'Mixed Content'

# O(n) to set main content
message.set_content('This is the main message')

# O(n) to attach files where n = file size
# Add HTML alternative - O(n)
message.add_alternative(
    '<html><body>This is <b>HTML</b></body></html>',
    subtype='html'
)

# O(n) to attach attachment where n = file size
with open('attachment.pdf', 'rb') as attachment:
    message.add_attachment(
        attachment.read(),
        maintype='application',
        subtype='octet-stream',
        filename='attachment.pdf'
    )

# O(n) to convert to string
email_str = message.as_string()
```

## Common Use Cases

### Extract Email Information

```python
from email import message_from_string

def extract_email_info(email_text):
    """Extract key information - O(n)"""
    # O(n) to parse where n = email size
    message = message_from_string(email_text)
    
    # O(1) field access
    info = {
        'from': message['From'],
        'to': message['To'],
        'subject': message['Subject'],
        'date': message['Date'],
        # O(n) to get body
        'body': message.get_payload()
    }
    
    return info
```

### Build Email with Attachments

```python
from email.message import EmailMessage
import os

def build_email_with_files(to_addr, files):
    """Build email with multiple attachments - O(n)"""
    message = EmailMessage()
    
    # O(n) to set headers where n = header size
    message['Subject'] = 'Files'
    message['From'] = 'sender@example.com'
    message['To'] = to_addr
    
    # O(1) to set text body
    message.set_content('See attached files')
    
    # O(k*n) where k = file count, n = avg file size
    for filepath in files:
        if os.path.exists(filepath):
            # O(n) per file to attach
            with open(filepath, 'rb') as f:
                data = f.read()
                filename = os.path.basename(filepath)
                
                message.add_attachment(
                    data,
                    maintype='application',
                    subtype='octet-stream',
                    filename=filename
                )
    
    return message

# Usage - O(n*k) where k = files
message = build_email_with_files(
    'recipient@example.com',
    ['report.pdf', 'data.csv', 'image.png']
)
```

### Parse Complex Email

```python
from email import message_from_string

def extract_all_parts(email_text):
    """Extract all message parts - O(n)"""
    # O(n) to parse
    message = message_from_string(email_text)
    
    parts = {
        'headers': {},
        'text': None,
        'html': None,
        'attachments': []
    }
    
    # O(n) to extract headers
    for key, value in message.items():
        parts['headers'][key] = value
    
    # O(k) where k = number of parts
    if message.is_multipart():
        for part in message.iter_parts():  # O(k)
            content_type = part.get_content_type()
            
            # O(n) per part to get payload
            payload = part.get_payload(decode=True)
            
            if content_type == 'text/plain':
                parts['text'] = payload.decode('utf-8')
            elif content_type == 'text/html':
                parts['html'] = payload.decode('utf-8')
            elif content_type == 'application/octet-stream':
                filename = part.get_filename()
                parts['attachments'].append({
                    'filename': filename,
                    'data': payload
                })
    else:
        # Single part - O(n)
        parts['text'] = message.get_payload(decode=True)
    
    return parts
```

## Performance Tips

### Cache Parsed Messages

```python
from email import message_from_string

class EmailCache:
    """Cache parsed emails - O(1) lookup"""
    
    def __init__(self):
        self._cache = {}
    
    def get_message(self, email_id, email_text):
        """O(1) if cached, O(n) first time"""
        if email_id not in self._cache:
            # O(n) first parse
            self._cache[email_id] = message_from_string(email_text)
        
        return self._cache[email_id]

# Usage
cache = EmailCache()
msg = cache.get_message(1, email_text)  # O(n)
msg = cache.get_message(1, email_text)  # O(1)
```

### Process Large Email Streams

```python
from email import message_from_file

def process_emails_stream(file_path):
    """Process multiple emails - O(k*n)"""
    processed = []
    
    # O(k*n) where k = emails, n = avg email size
    with open(file_path, 'r') as f:
        while True:
            # O(n) per email
            message = message_from_file(f)
            if not message:
                break
            
            # Process email - O(n)
            processed.append({
                'subject': message['Subject'],
                'from': message['From']
            })
    
    return processed
```

## Version Notes

- **Python 2.6+**: Basic email module
- **Python 3.6+**: EmailMessage (recommended over older Message)
- **Python 3.x**: Full Unicode support

## Related Documentation

- [SMTP Client](smtplib.md) - Sending emails
- [Base64 Module](base64.md) - Encoding attachments
- [Html Module](html.md) - HTML email parsing
