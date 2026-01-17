# struct Module Complexity

The `struct` module handles binary data conversions, packing Python values into bytes and unpacking bytes into Python values using format strings.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Struct()` compilation | O(m) | O(m) | m = format string length; compile once |
| `pack()` | O(k) | O(k) | k = number of fields; add O(m) parsing if not pre-compiled |
| `unpack()` | O(k) | O(k) | k = number of fields |
| `pack_into()` | O(n) | O(1) | n = number of fields |
| `unpack_from()` | O(n) | O(n) | n = number of fields |
| `calcsize()` | O(m) | O(1) | m = format string length |

## Format Strings

### Character Types

```python
import struct

# Format string characters
# 'b' = signed char      (1 byte)
# 'B' = unsigned char    (1 byte)
# 'h' = signed short     (2 bytes)
# 'H' = unsigned short   (2 bytes)
# 'i' = signed int       (4 bytes)
# 'I' = unsigned int     (4 bytes)
# 'l' = signed long      (4 bytes)
# 'L' = unsigned long    (4 bytes)
# 'q' = signed long long (8 bytes)
# 'Q' = unsigned long long (8 bytes)
# 'f' = float            (4 bytes)
# 'd' = double           (8 bytes)
# 's' = char[]           (variable)
# 'p' = pascal string    (variable)
# 'P' = void*            (pointer)

# Calculate size - O(m) where m = format length
size = struct.calcsize('i')      # 4 bytes
size = struct.calcsize('ihh')    # 8 bytes (4+2+2)
size = struct.calcsize('ihhf')   # 12 bytes (4+2+2+4)
```

### Byte Order and Alignment

```python
import struct

# Byte order prefix (optional, default='@' native)
# '@' = native (default)
# '=' = native (no alignment)
# '<' = little-endian
# '>' = big-endian
# '!' = network (big-endian)

# Native order - O(1) lookup
native = struct.calcsize('i')       # 4

# Little-endian - O(1) lookup
little = struct.calcsize('<i')      # 4

# Big-endian - O(1) lookup
big = struct.calcsize('>i')         # 4

# With alignment - O(1) lookup
aligned = struct.calcsize('@ii')    # 8 (with padding)
unaligned = struct.calcsize('=ii')  # 8 (no padding)
```

## Packing Data

### Simple Packing

```python
import struct

# Pack single value - O(n)
# Format: integer (4 bytes)
bytes_data = struct.pack('i', 42)
print(bytes_data)  # b'*\x00\x00\x00' (little-endian)

# Pack multiple values - O(n) for n values
bytes_data = struct.pack('ihh', 100, 200, 300)
# 4 bytes (int) + 2 bytes (short) + 2 bytes (short) = 8 bytes

# Pack with byte order - O(n)
bytes_data = struct.pack('>i', 42)    # Big-endian
bytes_data = struct.pack('<i', 42)    # Little-endian
```

### String Packing

```python
import struct

# Pack fixed-length string - O(n)
text = "Hello"
bytes_data = struct.pack('5s', text.encode())  # 5-byte string

# Pack with padding
name = "Bob"
bytes_data = struct.pack('10s', name.encode())  # Padded to 10 bytes

# Pack multiple strings
bytes_data = struct.pack('5s3s', b"Hello", b"Bob")  # 8 bytes total
```

### Pack Into Buffer

```python
import struct

# Pack into existing buffer - O(n) for n fields
buffer = bytearray(20)

# Write at offset 0
struct.pack_into('i', buffer, 0, 42)

# Write at offset 4
struct.pack_into('h', buffer, 4, 100)

# Write at offset 6
struct.pack_into('f', buffer, 6, 3.14)

print(buffer[:10])  # First 10 bytes with packed data
```

## Unpacking Data

### Simple Unpacking

```python
import struct

# Pack first
bytes_data = struct.pack('ihhf', 100, 200, 300, 3.14)

# Unpack all - O(n)
values = struct.unpack('ihhf', bytes_data)
print(values)  # (100, 200, 300, 3.140000104904175)

# Unpack specific subset
values = struct.unpack('ih', bytes_data[:6])  # Skip last values
print(values)  # (100, 200)
```

### Unpack From Buffer

```python
import struct

# Create buffer with packed data
buffer = bytearray(20)
struct.pack_into('i', buffer, 0, 42)
struct.pack_into('h', buffer, 4, 100)
struct.pack_into('f', buffer, 6, 3.14)

# Unpack from buffer - O(n)
value1 = struct.unpack_from('i', buffer, 0)[0]   # 42
value2 = struct.unpack_from('h', buffer, 4)[0]   # 100
value3 = struct.unpack_from('f', buffer, 6)[0]   # 3.14
```

## Struct Objects (Compiled Format)

### Create and Reuse Struct

```python
import struct

# Create compiled struct - O(n) once, then O(1) per operation
header_format = struct.Struct('4sI')  # 4-char string + unsigned int

# Pack with compiled struct - O(n)
bytes_data = header_format.pack(b"HEAD", 12345)

# Unpack with compiled struct - O(n)
header, version = header_format.unpack(bytes_data)
print(header)    # b'HEAD'
print(version)   # 12345

# Size calculation - O(1)
size = header_format.size  # 8
```

### Struct for Network Protocol

```python
import struct

# Message format: type(1) + length(2) + timestamp(4) + data
class Message:
    HEADER_FORMAT = struct.Struct('!BHI')  # Network byte order
    
    def __init__(self, msg_type, timestamp, data):
        self.type = msg_type
        self.timestamp = timestamp
        self.data = data
    
    def serialize(self):
        """Pack to bytes - O(n)"""
        header = self.HEADER_FORMAT.pack(
            self.type,
            len(self.data),
            self.timestamp
        )
        return header + self.data
    
    @classmethod
    def deserialize(cls, data):
        """Unpack from bytes - O(n)"""
        header_size = cls.HEADER_FORMAT.size
        msg_type, length, timestamp = cls.HEADER_FORMAT.unpack(
            data[:header_size]
        )
        payload = data[header_size:header_size + length]
        return cls(msg_type, timestamp, payload)

# Usage
msg = Message(1, 1234567890, b"Hello")
bytes_msg = msg.serialize()
msg2 = Message.deserialize(bytes_msg)
```

## Common Patterns

### Binary File I/O

```python
import struct

class BinaryWriter:
    """Write binary data to file"""
    
    def __init__(self, filename):
        self.file = open(filename, 'wb')
    
    def write_int(self, value):
        """Write integer - O(1)"""
        self.file.write(struct.pack('i', value))
    
    def write_string(self, value, length):
        """Write fixed-length string - O(n)"""
        self.file.write(struct.pack(f'{length}s', value.encode()))
    
    def close(self):
        self.file.close()

class BinaryReader:
    """Read binary data from file"""
    
    def __init__(self, filename):
        self.file = open(filename, 'rb')
    
    def read_int(self):
        """Read integer - O(1)"""
        return struct.unpack('i', self.file.read(4))[0]
    
    def read_string(self, length):
        """Read fixed-length string - O(n)"""
        return struct.unpack(f'{length}s', self.file.read(length))[0]
    
    def close(self):
        self.file.close()

# Usage
writer = BinaryWriter("data.bin")
writer.write_int(42)
writer.write_string("Hello", 10)
writer.close()

reader = BinaryReader("data.bin")
value = reader.read_int()
text = reader.read_string(10)
reader.close()
```

### Network Packet Parsing

```python
import struct

class PacketHeader:
    """Parse binary packet header"""
    
    FORMAT = struct.Struct('!HHBBHH')  # Network byte order
    # Destination port (H)
    # Source port (H)
    # Sequence (B)
    # Flags (B)
    # Window (H)
    # Checksum (H)
    
    def __init__(self, data):
        """Parse header - O(1)"""
        if len(data) < self.FORMAT.size:
            raise ValueError("Insufficient data")
        
        self.dst_port, self.src_port, self.seq, self.flags, \
            self.window, self.checksum = self.FORMAT.unpack(
                data[:self.FORMAT.size]
            )
    
    def to_bytes(self):
        """Serialize header - O(1)"""
        return self.FORMAT.pack(
            self.dst_port, self.src_port, self.seq,
            self.flags, self.window, self.checksum
        )

# Parse packet
packet_data = b'\x00P\x00P\x01\x00\x00\x10\x12\x34'
header = PacketHeader(packet_data)
print(f"Dst: {header.dst_port}, Src: {header.src_port}")
```

### C Structure Mapping

```python
import struct

# Map C struct: typedef struct { int id; float score; } Result;
class CResult:
    """Map to C struct"""
    
    STRUCT_FORMAT = struct.Struct('if')  # int + float
    
    def __init__(self, id=0, score=0.0):
        self.id = id
        self.score = score
    
    def pack(self):
        """Convert to C struct bytes - O(1)"""
        return self.STRUCT_FORMAT.pack(self.id, self.score)
    
    @classmethod
    def unpack(cls, data):
        """Create from C struct bytes - O(1)"""
        id, score = cls.STRUCT_FORMAT.unpack(data)
        return cls(id, score)

# Usage
result = CResult(42, 95.5)
data = result.pack()
result2 = CResult.unpack(data)
```

## Performance Considerations

### Time Complexity
- **pack()**: O(n) for n fields (linear in data size)
- **unpack()**: O(n) for n fields
- **Struct creation**: O(m) one-time cost (m = format length)
- **pack_into()**: O(n) for n fields

### Space Complexity
- **Output**: O(n) for packed data (n = total bytes)
- **Input**: O(n) for unpacked tuple

### Optimization Tips

```python
import struct

# Bad: Compiling format every time - O(n) per operation
for i in range(1000):
    data = struct.pack('i', i)  # Recompile each time

# Good: Compile once, reuse - O(n) compile + O(1000) use
int_struct = struct.Struct('i')
for i in range(1000):
    data = int_struct.pack(i)  # O(1) per use

# Benchmark difference is significant for repeated operations
```

## Format Modifiers

### Repetition

```python
import struct

# Pack 10 integers - O(n)
data = struct.pack('10i', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

# Unpack 10 integers - O(n)
values = struct.unpack('10i', data)
print(len(values))  # 10

# With byte order
data = struct.pack('>10H', *range(10))  # 10 big-endian shorts
```

## Error Handling

```python
import struct

# Format must match data size
try:
    struct.unpack('i', b'AB')  # Only 2 bytes, need 4
except struct.error as e:
    print(f"Unpack error: {e}")

# Invalid format character
try:
    struct.pack('z', 42)  # 'z' is invalid
except struct.error as e:
    print(f"Pack error: {e}")
```

## Related Documentation

- [Array Module](array.md)
- [IO Module](io.md)
- [Codecs Module](codecs.md)
- [Socket Module](socket.md)
