# csv Module Complexity

The `csv` module reads and writes delimited text with correct handling of quoting, embedded
delimiters and embedded newlines. The parser and formatter are C, and both work a row at a time:
nothing in the module holds a whole file unless you ask it to.

Rows are the unit throughout. `n` is rows, `k` is the characters in one row, `m` is the fields in
the header, `h` is the characters in the header row, and `d` is registered dialects.
Data-row dictionary bounds treat field-name hashing and comparison as O(1). A `DictReader`
also retains its O(m + h) header separately from the per-row storage.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `csv.reader(csvfile, dialect, **fmtparams)` | O(1) | O(1) | Wraps any iterable of strings; nothing is read yet |
| `next(reader)`, iterating a reader | O(k) | O(k) | k = row length; the parsed row is the only thing held |
| `csv.writer(csvfile, dialect, **fmtparams)` | O(1) | O(1) | Needs only a `write()` method |
| `writer.writerow(row)` | O(k) | O(k) | The whole line is built as one string before it is written |
| `writer.writerows(rows)` | O(n·k) | O(k) | One `writerow` per row, so the peak is the widest row, not the batch |
| `csv.DictReader(f, fieldnames=None, restkey=None, restval=None)` | O(1) | O(1) | The header is not read until `.fieldnames` is touched or iteration starts |
| `DictReader.fieldnames` | O(m + h) | O(m + h) | Reads and keeps the header on first access when fieldnames are omitted; subsequent access is O(1) |
| Iterating a `DictReader` | O(k + m) per row | O(k + m) per row | After one-time header processing; missing fields use `restval`, and `restkey` collects surplus fields |
| `csv.DictWriter(f, fieldnames, restval='', extrasaction='raise')` | O(m) | O(m) | Keeps the field order it was given |
| `DictWriter.writeheader()` | O(m + h) | O(m + h) | Builds a header dictionary and renders all header characters |
| `DictWriter.writerow(rowdict)` | O(m + k) | O(m + k) | Successful rows without surplus keys: projects the field order, validates keys by default, and renders all row characters |
| `csv.field_size_limit([new_limit])` | O(1) | O(1) | Returns the previous limit; a field longer than it raises `csv.Error` mid-parse |
| `csv.register_dialect(name, dialect, **fmtparams)` | O(1) | O(1) | One dict entry |
| `csv.unregister_dialect(name)` | O(1) | O(1) | Raises `csv.Error` if the name is unknown |
| `csv.get_dialect(name)` | O(1) | O(1) | Dict lookup |
| `csv.list_dialects()` | O(d) | O(d) | d = registered dialects |
| `csv.Sniffer()` | O(1) | O(1) | Holds no state between calls |
| `Sniffer.sniff(sample, delimiters=None)` | O(s) | O(s) | s = sample length; several regex passes plus per-character frequency tables |
| `Sniffer.has_header(sample)` | O(s) | O(s) | Calls `sniff()` first, which is what dominates; only the first 20 rows are then typed |
| `csv.Dialect`, `csv.excel`, `csv.excel_tab`, `csv.unix_dialect` | O(1) | O(1) | Attribute holders; validated once when a reader or writer is built |
| `csv.QUOTE_ALL`, `csv.QUOTE_MINIMAL`, `csv.QUOTE_NONE`, `csv.QUOTE_NONNUMERIC` | O(1) | O(1) | Integer flags; they change what gets quoted, not the bound |
| `csv.QUOTE_NOTNULL`, `csv.QUOTE_STRINGS` | O(1) | O(1) | Python 3.12+ |
| `csv.Error` | O(1) | O(1) | Raised for a bad dialect, an unknown dialect name, or an oversized field |

## Reading CSV Files

### Lazy vs Eager Reading

A reader holds one row. Building it reads nothing, and each step parses exactly one line, so
memory follows the widest row rather than the file.

```python
import csv
import io

data = "name,age\nAlice,30\nBob,25\n"

# LAZY: O(k) memory - one row at a time (preferred for large files)
reader = csv.reader(io.StringIO(data))  # O(1) - reads nothing yet
header = next(reader)                   # O(k)
assert header == ['name', 'age']
for row in reader:                      # O(k) per row
    assert len(row) == 2

# EAGER: O(n·k) memory - the whole file becomes a list of lists
all_rows = list(csv.reader(io.StringIO(data)))  # O(n·k) time and memory
assert all_rows[1] == ['Alice', '30']
```

### The Field Size Limit

Parsing is not unbounded. A single field longer than `csv.field_size_limit()` raises `csv.Error`
rather than allocating it, which is the module's guard against a malformed or hostile file.

```python
import csv

limit = csv.field_size_limit()  # O(1) - 131072 by default
oversized = "x" * (limit + 1)

try:
    list(csv.reader([oversized]))
except csv.Error as error:
    assert 'field limit' in str(error)

# Setting it returns the previous value, so it can be restored
previous = csv.field_size_limit(limit * 4)  # O(1)
assert len(next(csv.reader([oversized]))[0]) == limit + 1
csv.field_size_limit(previous)
```

## Writing CSV Files

### Writing Rows

`writerow()` builds the whole formatted line as one string before handing it to `write()`, so a
row costs its own length in memory. `writerows()` is that in a loop: the peak is the widest row,
not the batch.

```python
import csv
import io

buffer = io.StringIO()
writer = csv.writer(buffer)  # O(1)

# Write single row - O(k) time and memory
writer.writerow(['Name', 'Age', 'City'])  # O(k)

# Write multiple rows - O(n·k) time, still O(k) memory
writer.writerows([
    ['Alice', 30, 'NYC'],
    ['Bob', 25, 'LA'],
])  # O(n·k) total

assert buffer.getvalue().startswith('Name,Age,City\r\n')
```

### Quoting

The `QUOTE_*` flags decide which fields get quotes. They change the output, not the cost: every
strategy still walks the row once.

```python
import csv
import io

def render(quoting):
    buffer = io.StringIO()
    csv.writer(buffer, quoting=quoting).writerow(['a b', 42])  # O(k)
    return buffer.getvalue().strip()

assert render(csv.QUOTE_MINIMAL) == 'a b,42'
assert render(csv.QUOTE_ALL) == '"a b","42"'
assert render(csv.QUOTE_NONNUMERIC) == '"a b",42'
```

## Dictionary-based CSV Operations

### Reading as Dictionaries

`DictReader` reads nothing when it is built. The header arrives on the first access to
`.fieldnames`, which is also what iteration does.

```python
import csv
import io

data = "name,age,city\nAlice,30,NYC\nBob,25,LA\n"

reader = csv.DictReader(io.StringIO(data))  # O(1) - the header is not read yet
assert reader.fieldnames == ['name', 'age', 'city']  # O(m + h) once, then O(1)

for row in reader:      # O(k + m) per row
    name = row['name']  # O(1)
    assert isinstance(name, str)
```

### Ragged Rows

A row with more fields than the header puts the surplus under `restkey`; one with fewer fills the
gap with `restval`. Filling the gap visits each missing header name, so a short row can still
produce an m-entry dictionary.

```python
import csv
import io

reader = csv.DictReader(
    io.StringIO("a,b\n1,2,3\n4\n"), restkey='extra', restval='?'
)

rows = list(reader)  # O(m + h + n·(k + m))
assert rows[0] == {'a': '1', 'b': '2', 'extra': ['3']}
assert rows[1] == {'a': '4', 'b': '?'}
```

### Writing Dictionaries

```python
import csv
import io

buffer = io.StringIO()
writer = csv.DictWriter(buffer, fieldnames=['Name', 'Age'])  # O(m)

writer.writeheader()  # O(m + h)
writer.writerow({'Name': 'Alice', 'Age': 30})  # O(m + k) to project and render

assert buffer.getvalue() == 'Name,Age\r\nAlice,30\r\n'

# A key outside fieldnames is an error unless extrasaction says otherwise
try:
    writer.writerow({'Name': 'Bob', 'Nickname': 'B'})
except ValueError as error:
    assert 'not in fieldnames' in str(error)
```

## Dialects

A dialect is a bundle of format parameters. Registering one is a dict entry, and looking one up
by name is a dict lookup; the validation happens once, when a reader or writer is built.

```python
import csv
import io

csv.register_dialect('pipes', delimiter='|', quoting=csv.QUOTE_MINIMAL)  # O(1)
assert 'pipes' in csv.list_dialects()  # O(d)
assert csv.get_dialect('pipes').delimiter == '|'  # O(1)

buffer = io.StringIO()
csv.writer(buffer, dialect='pipes').writerow(['a', 'b'])
assert buffer.getvalue().strip() == 'a|b'

csv.unregister_dialect('pipes')  # O(1)
try:
    csv.get_dialect('pipes')
except csv.Error as error:
    assert 'unknown dialect' in str(error)

# The three built-in dialects are always registered
assert set(csv.list_dialects()) == {'excel', 'excel-tab', 'unix'}
assert csv.excel.delimiter == ',' and csv.excel_tab.delimiter == '\t'
assert csv.unix_dialect.quoting == csv.QUOTE_ALL
assert issubclass(csv.excel, csv.Dialect)
```

### Custom Delimiters Without Registering

```python
import csv
import io

# Any format parameter can be passed straight to the reader - O(1) setup
tsv = csv.reader(io.StringIO("a\tb\n"), delimiter='\t')
assert next(tsv) == ['a', 'b']

semicolons = csv.reader(io.StringIO("a;b\n"), delimiter=';')
assert next(semicolons) == ['a', 'b']
```

## Sniffing an Unknown Format

`Sniffer` is the one part of the module that is not a single pass over one row. Both of its
methods walk the whole sample you hand them, and `has_header()` calls `sniff()` first — so pass a
few kilobytes, not the file.

```python
import csv

sample = "name;age;city\nAlice;30;NYC\nBob;25;LA\n"

dialect = csv.Sniffer().sniff(sample)  # O(s), s = sample length
assert dialect.delimiter == ';'

assert csv.Sniffer().has_header(sample) is True  # O(s), sniff dominates
```

## Common Patterns

### Read, Transform, Write

```python
import csv
import io

source = io.StringIO("name,age\nalice,30\nbob,25\n")
target = io.StringIO()

reader = csv.reader(source)
writer = csv.writer(target)

next(reader)  # skip the header - O(k)
for row in reader:              # O(k) per row
    writer.writerow([row[0].upper(), int(row[1])])  # O(k)

assert target.getvalue() == 'ALICE,30\r\nBOB,25\r\n'
```

### Aggregating

```python
import csv
import io
from collections import defaultdict

data = "name,city\nAlice,NYC\nBob,LA\nCara,NYC\n"
counts = defaultdict(int)

for row in csv.DictReader(io.StringIO(data)):  # O(k + m) per row
    counts[row['city']] += 1  # O(1) amortized

assert dict(counts) == {'NYC': 2, 'LA': 1}  # O(unique cities)
```

## Version Notes

- **Python 3.12+**: Added `QUOTE_STRINGS` and `QUOTE_NOTNULL`
- **All Python 3**: Open files with `newline=''`, or embedded newlines in quoted fields break

## Related Modules

- **[json](json.md)** - O(n) parsing; use for hierarchical data
- **[io](io.md)** - `StringIO` for in-memory CSV processing

## Performance Best Practices

✅ **Do**:

- Iterate a reader instead of calling `list()` on it, so memory follows the row rather than the file
- Use `writerows()` for a batch: it is one call instead of n, and the peak is unchanged
- Hand `Sniffer` a small sample; it is linear in whatever you give it
- Restore `field_size_limit()` to what it returned you, rather than leaving it raised

❌ **Avoid**:

- `list(reader)` on a large file - that is the one thing here that costs O(n·k) memory
- Splitting on `,` by hand - same O(k), but wrong for quoted fields and embedded newlines
- Sniffing the whole file when a few kilobytes decide it
