# sqlite3 Module Complexity

The `sqlite3` module provides a lightweight embedded SQL database interface for Python applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `connect()` | O(1) | O(1) | Open database (filesystem work varies) |
| `execute()` | Varies | Varies | Depends on query plan, indexes, sorting |
| SELECT | O(n) or O(log n) | O(n) | O(log n) lookup with index, O(n) full scan |
| INSERT | O(log n) | O(1) | B-tree insert (plus I/O) |
| UPDATE/DELETE | O(n) or O(log n) | O(1) | O(log n) with indexed WHERE; O(n) full scan |

## Basic Usage

```python
import sqlite3

# Connect to database (filesystem work varies)
conn = sqlite3.connect('database.db')
cursor = conn.cursor()  # O(1)

# Create table - O(1) for schema change
cursor.execute('''CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER
)''')

# Insert - O(log n)
cursor.execute('INSERT INTO users VALUES (?, ?, ?)', (1, 'Alice', 30))
conn.commit()  # O(1) for small transactions

# Query - varies by plan
cursor.execute('SELECT * FROM users WHERE age > ?', (25,))
rows = cursor.fetchall()  # O(n)

# Update - O(n) without index
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

# Select with WHERE - O(log n) with index, O(n) without
cursor.execute('SELECT * FROM posts WHERE id = ?', (1,))
post = cursor.fetchone()  # O(1) first match

# Select with ORDER - O(n log n) for sorting (unless index covers)
cursor.execute('SELECT * FROM posts ORDER BY id DESC')
rows = cursor.fetchall()  # O(n)

# Count rows - O(n) full scan
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

# Automatic commit/rollback
with sqlite3.connect('db.db') as conn:
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
    # Multiple operations - varies by query plan
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

# Inefficient - commit per item (I/O heavy)
for item in items:  # n items
    cursor.execute('INSERT INTO data VALUES (?)', (item,))
    conn.commit()  # Slow (fsync per commit)

# Efficient - O(n) inserts, single commit
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
- **All versions**: Query complexity depends on plan and indexes

## Related Modules

- **sqlalchemy** - ORM (external)
- **pandas** - Data analysis with SQL support

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
