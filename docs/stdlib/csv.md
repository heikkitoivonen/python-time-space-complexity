# csv Module Complexity

The `csv` module provides functionality for reading and writing CSV (Comma-Separated Values) files with proper handling of quoting, delimiters, and special characters.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `csv.reader(file)` | O(1) | O(1) | Create reader object; lazy iteration |
| `reader.next()` or iteration | O(k) | O(k) | k = row length; streaming |
| `csv.writer(file)` | O(1) | O(1) | Create writer object |
| `writer.writerow(row)` | O(k) | O(1) | k = row length |
| `writer.writerows(rows)` | O(n*k) | O(1) | n rows, avg k length |
| `csv.DictReader(file)` | O(1) | O(m) | m = header length |
| `DictReader iteration` | O(k) | O(k) | k = row + header overhead |
| `csv.DictWriter(file)` | O(1) | O(m) | m = field names length |
| `csv.field_size_limit([size])` | O(1) | O(1) | Get/set max field size |
| `csv.register_dialect(name, ...)` | O(1) | O(1) | Register custom dialect |
| `csv.unregister_dialect(name)` | O(1) | O(1) | Remove registered dialect |
| `csv.get_dialect(name)` | O(1) | O(1) | Get dialect by name |
| `csv.list_dialects()` | O(d) | O(d) | List registered dialect names |
| `Sniffer.sniff(sample)` | O(n) | O(1) | Detect CSV format from sample |
| `Sniffer.has_header(sample)` | O(n) | O(1) | Detect if sample has header row |

## Reading CSV Files

### Lazy vs Eager Reading

```python
import csv

# LAZY: O(1) memory - process one row at a time (preferred for large files)
with open('data.csv', 'r', newline='') as file:
    reader = csv.reader(file)  # O(1) - creates iterator
    for row in reader:         # O(k) per row, k = row length
        process(row)           # Row discarded after processing

# EAGER: O(n) memory - loads entire file (only for small files or random access)
with open('data.csv', 'r', newline='') as file:
    reader = csv.reader(file)
    all_rows = list(reader)    # O(n*k) time, O(n*k) memory
```

## Writing CSV Files

### Writing Rows

```python
import csv

# Create writer - O(1)
with open('output.csv', 'w') as file:
    writer = csv.writer(file)  # O(1)
    
    # Write single row - O(k)
    writer.writerow(['Name', 'Age', 'City'])  # O(k)
    
    # Write multiple rows - O(n*k)
    writer.writerows([
        ['Alice', 30, 'NYC'],    # O(k)
        ['Bob', 25, 'LA'],       # O(k)
        ['Charlie', 35, 'SF']    # O(k)
    ])  # O(n*k) total

# File auto-closed
```

## Dictionary-based CSV Operations

### Reading as Dictionaries

```python
import csv

# Create DictReader - O(m) where m = header length
with open('data.csv', 'r') as file:
    reader = csv.DictReader(file)  # O(m)
    
    # Iterate rows as dicts - O(k) per row
    for row in reader:  # O(k) per iteration
        print(row)  # OrderedDict-like
        # row = {'name': 'Alice', 'age': '30', 'city': 'NYC'}
        
        name = row['name']  # O(1)
        age = row['age']    # O(1)
```

### Writing Dictionaries

```python
import csv

# Specify field names - O(m)
fieldnames = ['Name', 'Age', 'City']

with open('output.csv', 'w') as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)  # O(m)
    
    # Write header - O(m)
    writer.writeheader()  # O(m)
    
    # Write rows as dicts - O(k) per row
    writer.writerow({'Name': 'Alice', 'Age': 30, 'City': 'NYC'})  # O(k)
    writer.writerow({'Name': 'Bob', 'Age': 25, 'City': 'LA'})     # O(k)
```

## Handling Different Delimiters

### Custom Delimiters

```python
import csv

# Tab-delimited (TSV) - O(1) setup
with open('data.tsv', 'r') as file:
    reader = csv.reader(file, delimiter='\t')
    for row in reader:  # O(k) per row
        process(row)

# Pipe-delimited - O(1) setup
with open('data.psv', 'r') as file:
    reader = csv.reader(file, delimiter='|')
    for row in reader:  # O(k) per row
        process(row)

# Semicolon-delimited (European CSV) - O(1) setup
with open('data.csv', 'r', encoding='latin-1') as file:
    reader = csv.reader(file, delimiter=';')
    for row in reader:  # O(k) per row
        process(row)
```

## Common Patterns

### Reading and Processing

```python
import csv

# Read, transform, write - O(n*k)
with open('input.csv', 'r') as infile, \
     open('output.csv', 'w') as outfile:
    reader = csv.reader(infile)
    writer = csv.writer(outfile)
    
    # Skip header
    next(reader)  # O(m)
    
    # Process rows
    for row in reader:  # O(k) per row
        # Transform
        name = row[0].upper()  # O(n_name)
        age = int(row[1])      # O(1)
        
        # Write
        writer.writerow([name, age])  # O(k)

# Total: O(n*k)
```

### Filtering Data

```python
import csv

# Read and filter - O(n*k)
with open('data.csv', 'r') as infile, \
     open('filtered.csv', 'w') as outfile:
    reader = csv.DictReader(infile)
    writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
    
    # Write header - O(m)
    writer.writeheader()
    
    # Filter and write - O(k) per matching row
    for row in reader:  # O(k) per row
        if int(row['age']) > 25:  # O(1)
            writer.writerow(row)  # O(k)
```

### Aggregating Data

```python
import csv
from collections import defaultdict

# Count occurrences - O(n*k)
city_count = defaultdict(int)

with open('data.csv', 'r') as file:
    reader = csv.DictReader(file)
    
    for row in reader:  # O(k) per row
        city = row['city']  # O(1)
        city_count[city] += 1  # O(1) amortized

# Result - O(unique_cities)
for city, count in city_count.items():
    print(f"{city}: {count}")
```

### Merging CSV Files

```python
import csv

# Merge multiple files - O(n*k)
with open('merged.csv', 'w') as outfile:
    writer = csv.writer(outfile)
    
    # Write header once
    writer.writerow(['Name', 'Age', 'City'])  # O(m)
    
    # Read and merge files
    for filename in ['file1.csv', 'file2.csv', 'file3.csv']:
        with open(filename, 'r') as infile:
            reader = csv.reader(infile)
            next(reader)  # Skip header - O(m)
            
            for row in reader:  # O(k) per row
                writer.writerow(row)  # O(k)

# Total: O(total_rows * avg_row_length)
```

## Performance Optimization

### Batch Writing

```python
import csv

# Write in batches - reduces per-row overhead
with open('output.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Name', 'Age', 'City'])  # Header
    
    # Collect rows in memory, then write batch
    batch = []
    for row in generate_rows():  # O(n)
        batch.append(row)
        
        if len(batch) >= 1000:  # Write every 1000 rows
            writer.writerows(batch)  # O(1000*k) - one call vs 1000
            batch = []
    
    # Write remaining
    if batch:
        writer.writerows(batch)
```

### Reading Large Files Efficiently

```python
import csv

# Process in chunks for memory efficiency - O(n*k)
with open('large_file.csv', 'r') as file:
    reader = csv.DictReader(file)
    
    chunk = []
    for row in reader:  # O(k) per row
        chunk.append(row)
        
        if len(chunk) >= 1000:  # Process every 1000 rows
            process_chunk(chunk)  # O(1000*k)
            chunk = []
    
    # Process final chunk
    if chunk:
        process_chunk(chunk)
```

## Version Notes

- **Python 3.12+**: Added `QUOTE_STRINGS` and `QUOTE_NOTNULL` constants
- **All Python 3**: Use `newline=''` parameter when opening CSV files

## Related Modules

- **pandas** - Higher-level CSV with O(n) memory but faster vectorized operations
- **[json](json.md)** - O(n) parsing; use for hierarchical data
- **[io](io.md)** - StringIO for in-memory CSV processing

## Performance Best Practices

✅ **Do**:

- Process large files lazily (O(1) memory) instead of `list(reader)` (O(n) memory)
- Use `writerows()` for batches - fewer function calls than repeated `writerow()`
- Use `csv.reader` for positional access (O(1) per field vs O(1) dict lookup overhead)

❌ **Avoid**:

- `list(reader)` on large files - loads entire file into memory O(n)
- Manual string splitting with `split(',')` - incorrect for quoted fields, same O(k) complexity but buggy
- Repeated small writes - buffer with batches for better I/O performance
