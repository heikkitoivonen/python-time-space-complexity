# sqlite3 Module Complexity

The `sqlite3` module provides a lightweight embedded SQL database interface for Python applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `connect()` | O(1) | O(1) | Open database |
| `execute()` | O(n) | O(n) | n = result rows |
| SELECT | O(n log n) | O(n) | Query + sort |
| INSERT | O(log n) | O(1) | n = total rows |
| UPDATE/DELETE | O(n) | O(1) | n = matching rows |

## Basic Usage

```python
import sqlite3

# Connect to database - O(1)
conn = sqlite3.connect('database.db')  # O(1)
cursor = conn.cursor()  # O(1)

# Create table - O(1)
cursor.execute('''CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER
)''')

# Insert - O(log n)
cursor.execute('INSERT INTO users VALUES (?, ?, ?)', (1, 'Alice', 30))
conn.commit()  # O(1)

# Query - O(n log n)
cursor.execute('SELECT * FROM users WHERE age > ?', (25,))
rows = cursor.fetchall()  # O(n)

# Update - O(n)
cursor.execute('UPDATE users SET age = ? WHERE name = ?', (31, 'Alice'))
conn.commit()

# Close - O(1)
conn.close()
```

## CRUD Operations

### Create

```python
import sqlite3

conn = sqlite3.connect(':memory:')  # In-memory DB
cursor = conn.cursor()

# Create table - O(1)
cursor.execute('''CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT
)''')

# Insert single - O(log n)
cursor.execute('INSERT INTO posts VALUES (?, ?, ?)', 
               (1, 'Title', 'Content'))

# Insert multiple - O(n log n)
data = [(2, 'Title2', 'Content2'), (3, 'Title3', 'Content3')]
cursor.executemany('INSERT INTO posts VALUES (?, ?, ?)', data)

conn.commit()  # O(n)
```

### Read

```python
import sqlite3

conn = sqlite3.connect(':memory:')
cursor = conn.cursor()

# Select all - O(n)
cursor.execute('SELECT * FROM posts')
all_posts = cursor.fetchall()  # O(n)

# Select with WHERE - O(n log n)
cursor.execute('SELECT * FROM posts WHERE id = ?', (1,))
post = cursor.fetchone()  # O(1) first match

# Select with ORDER - O(n log n)
cursor.execute('SELECT * FROM posts ORDER BY id DESC')
rows = cursor.fetchall()  # O(n)

# Count rows - O(n)
cursor.execute('SELECT COUNT(*) FROM posts')
count = cursor.fetchone()[0]
```

### Update

```python
import sqlite3

conn = sqlite3.connect(':memory:')
cursor = conn.cursor()

# Update - O(n)
cursor.execute('UPDATE posts SET title = ? WHERE id = ?',
               ('New Title', 1))

conn.commit()  # O(n)
```

### Delete

```python
import sqlite3

conn = sqlite3.connect(':memory:')
cursor = conn.cursor()

# Delete - O(n)
cursor.execute('DELETE FROM posts WHERE id = ?', (1,))

conn.commit()  # O(n)
```

## Context Manager Pattern

```python
import sqlite3

# Automatic commit/rollback - O(1)
with sqlite3.connect('db.db') as conn:  # O(1) open
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users VALUES (?, ?)', (1, 'Alice'))
# Automatically commits when exiting
```

## Transactions

```python
import sqlite3

conn = sqlite3.connect('db.db')
cursor = conn.cursor()

try:
    # Multiple operations - O(n)
    cursor.execute('INSERT INTO users VALUES (?, ?)', (1, 'Alice'))
    cursor.execute('INSERT INTO orders VALUES (?, ?)', (1, 1))
    
    conn.commit()  # Both or nothing
except Exception as e:
    conn.rollback()  # Undo on error
finally:
    conn.close()
```

## Performance Tips

### Using Transactions

```python
import sqlite3

conn = sqlite3.connect('db.db')
cursor = conn.cursor()

# Inefficient - O(n) commits - O(1) each
for item in items:  # n items
    cursor.execute('INSERT INTO data VALUES (?)', (item,))
    conn.commit()  # O(1) - slow!

# Efficient - O(n) inserts, O(1) final commit
conn.execute('BEGIN')  # O(1)
for item in items:  # n items
    cursor.execute('INSERT INTO data VALUES (?)', (item,))
conn.commit()  # O(n) total - much faster
```

### Indexing

```python
import sqlite3

conn = sqlite3.connect('db.db')
cursor = conn.cursor()

# Create index - O(n log n) one-time
cursor.execute('CREATE INDEX idx_name ON users(name)')
conn.commit()

# Queries use index - O(log n) instead of O(n)
cursor.execute('SELECT * FROM users WHERE name = ?', ('Alice',))
# Much faster with index
```

## Version Notes

- **Python 2.x**: sqlite3 available since 2.5
- **Python 3.x**: Built-in
- **All versions**: O(n log n) typical query complexity

## Related Modules

- **[sqlalchemy](sqlalchemy.md)** - ORM (external)
- **[pandas](pandas.md)** - Data analysis with SQL support

## Best Practices

✅ **Do**:
- Use parameterized queries (prevent injection)
- Use transactions for multiple operations
- Use indexes for frequent queries
- Use context managers for cleanup

❌ **Avoid**:
- String concatenation in queries (SQL injection)
- Multiple commits in loops
- Missing indexes on frequently queried columns
