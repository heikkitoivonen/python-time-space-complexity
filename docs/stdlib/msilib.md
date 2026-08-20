# msilib Module

⚠️ **REMOVED IN PYTHON 3.13**: The `msilib` module was deprecated in Python 3.11 and removed in Python 3.13.

The `msilib` module creates and manipulates Microsoft Installer (`.msi`) files.
An MSI file is a small relational database, and the module exposes it as such:
databases, tables, records, views, and SQL-like queries.

It was Windows-only. On other platforms importing it raised
`ModuleNotFoundError`.

## Complexity Reference

### Database and Views

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OpenDatabase(path, persist)` | O(1) + I/O | O(1) | Open or create an MSI database |
| `CreateRecord(count)` | O(1) | O(count) | Allocate a record with `count` fields |
| `db.OpenView(sql)` | O(1) | O(1) | Compile a query |
| `view.Execute(params)` | O(1) | O(1) | Run the compiled query |
| `view.Fetch()` | O(1) | O(f) | One row; f = field count |
| `view.Modify(mode, record)` | O(log n) | O(1) | Insert, update, or delete; n = table rows |
| `view.Close()` | O(1) | O(1) | Release the view |
| `db.Commit()` | O(n) + I/O | O(1) | Flush all pending changes |
| Full table scan | O(n) | O(f) | n `Fetch()` calls, one per row |

### Records

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `record.GetString(field)` | O(k) | O(k) | k = string length |
| `record.SetString(field, value)` | O(k) | O(k) | k = string length |
| `record.GetInteger(field)` | O(1) | O(1) | Integer field |
| `record.SetInteger(field, value)` | O(1) | O(1) | Integer field |
| `record.SetStream(field, path)` | O(n) + I/O | O(1) | n = file size; embeds a file |
| `record.GetFieldCount()` | O(1) | O(1) | Number of fields |
| `record.ClearData()` | O(f) | O(1) | Reset all fields |

### Helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `add_data(db, table, records)` | O(r log n) | O(1) | r = records inserted |
| `add_tables(db, module)` | O(t) | O(1) | t = table definitions |
| `init_database(name, schema, ...)` | O(t) + I/O | O(1) | Create a database from a schema |
| `gen_uuid()` | O(1) | O(1) | New GUID string |
| `Directory` / `Feature` / `CAB` classes | varies | varies | Wrappers over the above |

Inserts go through the installer's indexed tables, hence the O(log n) per row
rather than O(1). Building a package is therefore O(r log n) in the number of
rows, plus linear I/O for any embedded streams.

## Reading a Table

```python
import msilib

db = msilib.OpenDatabase("package.msi", msilib.MSIDBOPEN_READONLY)
view = db.OpenView("SELECT Property, Value FROM Property")   # O(1)
view.Execute(None)                                           # O(1)

# O(n) - one Fetch per row
while True:
    record = view.Fetch()
    if record is None:
        break
    print(record.GetString(1), record.GetString(2))
view.Close()
```

## Inserting Rows

```python
import msilib

db = msilib.OpenDatabase("package.msi", msilib.MSIDBOPEN_TRANSACT)

# O(r log n) - each row is inserted into an indexed table
msilib.add_data(db, "Property", [
    ("ProductName", "Example"),
    ("ProductVersion", "1.0.0"),
])

db.Commit()   # O(n) - flush to disk
```

## Embedding a File

```python
import msilib

record = msilib.CreateRecord(2)          # O(1)
record.SetString(1, "readme.txt")        # O(k)
record.SetStream(2, "docs/readme.txt")   # O(n) in file size
```

!!! warning "Removed in Python 3.13"
    There is no standard-library replacement. Use the WiX Toolset, or a
    third-party packaging tool, to build MSI installers.

!!! tip "Batch inserts before committing"
    `Commit()` is the expensive call. Accumulate rows and commit once rather
    than committing per row.

## Version Notes

- **Python 3.11**: deprecated (PEP 594)
- **Python 3.13**: removed
- **Before 3.13**: Windows-only; wrapped the Windows Installer API
- **All versions**: query and insert complexity is governed by the installer's
  own table indexes

## Related Documentation

- [Zipfile Module](zipfile.md)
- [Tarfile Module](tarfile.md)
- [Sqlite3 Module](sqlite3.md)
- [Winreg Module](winreg.md)
