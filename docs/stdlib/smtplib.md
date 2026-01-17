# Smtplib Module

The `smtplib` module provides a Simple Mail Transfer Protocol (SMTP) client for sending emails.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SMTP()` | O(n) | O(n) | n = connection time |
| `sendmail()` | O(n) | O(n) | n = message size |
| `send_message()` | O(n) | O(n) | n = message size |
| `login()` | O(n) | O(n) | n = handshake |
| `quit()` | O(1) | O(1) | Close connection |

## Common Operations

### Sending Simple Email

```python
import smtplib
from email.message import EmailMessage

# O(n) where n = connection time
server = smtplib.SMTP('smtp.gmail.com', 587)

# O(n) - TLS handshake
server.starttls()

# O(n) - authenticate where n = handshake time
server.login('your_email@gmail.com', 'your_password')

# O(n) - send message where n = message size
message = EmailMessage()
message['Subject'] = 'Hello'
message['From'] = 'your_email@gmail.com'
message['To'] = 'recipient@example.com'
message.set_content('Email body')

server.send_message(message)

# O(1) - close connection
server.quit()
```

### Sending with Authentication

```python
import smtplib

def send_email(smtp_host, smtp_port, sender, password, recipient, subject, body):
    """Send email with full details - O(n)"""
    # O(n) - establish connection
    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        
        # O(n) - enable encryption
        server.starttls()
        
        # O(n) - authenticate
        server.login(sender, password)
        
        # O(n) - compose message where n = message size
        message = f"""Subject: {subject}

{body}"""
        
        # O(n) - send message
        server.sendmail(sender, [recipient], message)

# Usage - O(n)
send_email(
    'smtp.gmail.com',
    587,
    'user@gmail.com',
    'password',
    'recipient@example.com',
    'Test Subject',
    'Test message body'
)
```

## Common Use Cases

### Batch Email Sending

```python
import smtplib
from email.message import EmailMessage

def send_bulk_emails(recipients, subject, body):
    """Send emails to multiple recipients - O(n*m)"""
    # O(n) - connection setup
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('sender@gmail.com', 'password')
        
        # O(k*n) where k = recipients, n = avg message size
        for recipient in recipients:
            message = EmailMessage()
            message['Subject'] = subject
            message['From'] = 'sender@gmail.com'
            message['To'] = recipient
            message.set_content(body)
            
            # O(n) to send each message
            server.send_message(message)

# Usage - O(k*n)
recipients = ['user1@example.com', 'user2@example.com', 'user3@example.com']
send_bulk_emails(recipients, 'Newsletter', 'Monthly update...')
```

### Sending HTML Email with Attachments

```python
import smtplib
from email.message import EmailMessage

def send_html_email(recipient, subject, html_body, attachments=None):
    """Send HTML email with attachments - O(n)"""
    # O(1) - create message
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = 'sender@gmail.com'
    message['To'] = recipient
    
    # O(n) - set HTML content where n = body length
    message.set_content('Plain text version')
    message.add_alternative(html_body, subtype='html')
    
    # O(k*m) where k = attachments, m = avg file size
    if attachments:
        for filename, filedata in attachments.items():
            message.add_attachment(
                filedata,
                maintype='application',
                subtype='octet-stream',
                filename=filename
            )
    
    # O(n) - send
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('sender@gmail.com', 'password')
        server.send_message(message)  # O(n)

# Usage - O(n)
html = '<html><body><h1>Hello</h1></body></html>'
send_html_email('user@example.com', 'HTML Email', html)
```

### Email Queue System

```python
import smtplib
from email.message import EmailMessage
from queue import Queue
import threading

class EmailQueue:
    """Background email queue - O(1) add, O(n) send"""
    
    def __init__(self, host, port, username, password):
        self.queue = Queue()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
        # Start background worker - O(1)
        self.worker = threading.Thread(target=self._process_queue, daemon=True)
        self.worker.start()
    
    def queue_email(self, to, subject, body):
        """Add to queue - O(1)"""
        # O(1) - queue operation
        self.queue.put({
            'to': to,
            'subject': subject,
            'body': body
        })
    
    def _process_queue(self):
        """Background worker - O(n) per email"""
        # O(n) - connect once
        server = smtplib.SMTP(self.host, self.port)
        server.starttls()
        server.login(self.username, self.password)
        
        try:
            while True:
                # O(1) - get from queue
                email_data = self.queue.get()
                
                # O(n) - create and send
                message = EmailMessage()
                message['Subject'] = email_data['subject']
                message['From'] = self.username
                message['To'] = email_data['to']
                message.set_content(email_data['body'])
                
                server.send_message(message)
        finally:
            server.quit()

# Usage - O(1) to queue
queue = EmailQueue('smtp.gmail.com', 587, 'user@gmail.com', 'password')
queue.queue_email('user1@example.com', 'Subject 1', 'Body 1')  # O(1)
queue.queue_email('user2@example.com', 'Subject 2', 'Body 2')  # O(1)
# Background worker sends - O(n) per email
```

### Error Handling and Retry

```python
import smtplib
import time

def send_email_with_retry(host, port, sender, password, recipient, subject, body, retries=3):
    """Send with retry logic - O(n*r)"""
    # O(r*n) where r = retries, n = operation time
    for attempt in range(retries):
        try:
            # O(n) - send
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                server.login(sender, password)
                
                message = f"Subject: {subject}\n\n{body}"
                server.sendmail(sender, [recipient], message)
            
            return True  # Success
        
        except smtplib.SMTPException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < retries - 1:
                # O(1) - wait before retry
                time.sleep(2 ** attempt)  # Exponential backoff
    
    return False  # Failed after retries

# Usage - O(n*r)
success = send_email_with_retry(
    'smtp.gmail.com',
    587,
    'user@gmail.com',
    'password',
    'recipient@example.com',
    'Test',
    'Body'
)
```

## Performance Tips

### Reuse SMTP Connection

```python
import smtplib

# Bad: Create connection for each email - O(n*k) per email
for recipient in recipients:
    server = smtplib.SMTP('smtp.gmail.com', 587)  # O(n)
    server.starttls()
    server.login(user, pwd)
    server.sendmail(user, recipient, msg)  # O(m)
    server.quit()  # O(1)

# Good: Reuse connection - O(n + k*m)
with smtplib.SMTP('smtp.gmail.com', 587) as server:  # O(n)
    server.starttls()
    server.login(user, pwd)
    
    for recipient in recipients:
        server.sendmail(user, recipient, msg)  # O(m) per email
```

### Batch Multiple Recipients

```python
import smtplib

def send_to_list(recipients, message):
    """Send to multiple recipients in one call - O(n)"""
    # O(n) - connection and auth
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(user, password)
        
        # O(n) - single sendmail call for all
        server.sendmail(user, recipients, message)

# Usage - O(n) where n = total recipient count
recipients = ['user1@example.com', 'user2@example.com']
send_to_list(recipients, msg_text)  # More efficient than multiple calls
```

### Use Context Manager

```python
import smtplib

# Good: Automatic cleanup with context manager
with smtplib.SMTP('smtp.gmail.com', 587) as server:  # O(n)
    server.starttls()
    server.login('user', 'pass')
    server.sendmail('from', 'to', msg)  # O(m)
# quit() called automatically
```

## Version Notes

- **Python 2.6+**: Core functionality
- **Python 3.x**: All features available
- **Python 3.6+**: EmailMessage support

## Related Documentation

- [Email Module](email.md) - Message construction
- [Base64 Module](base64.md) - Encoding for MIME
- [Socket Module](socket.md) - Low-level networking
