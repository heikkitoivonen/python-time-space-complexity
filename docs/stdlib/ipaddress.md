# Ipaddress Module Complexity

The `ipaddress` module provides utilities for creating and manipulating IPv4 and IPv6 addresses and networks.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IPv4Address(addr)` | O(n) | O(1) | Create IPv4 address |
| `IPv6Address(addr)` | O(n) | O(1) | Create IPv6 address |
| `IPv4Network(addr)` | O(n) | O(1) | Create IPv4 network |
| `IPv6Network(addr)` | O(n) | O(1) | Create IPv6 network |
| `ip_address(addr)` | O(n) | O(1) | Auto-detect IP type |
| `ip_network(addr)` | O(n) | O(1) | Auto-detect network type |
| Address membership | O(1) | O(1) | Check in network |
| Subnet iteration | O(2^k) | O(1) | Generate subnets |

## IP Address Creation

### IPv4Address()

#### Time Complexity: O(n)

Where n = length of address string.

```python
from ipaddress import IPv4Address

# Create from string: O(n) to parse
addr = IPv4Address('192.168.1.1')  # O(n)

# Create from integer: O(1)
addr = IPv4Address(3232235777)  # O(1)

# Access parts: O(1)
print(addr.packed)     # Binary representation
print(addr.version)    # 4
print(addr.is_private) # Check if private
```

#### Space Complexity: O(1)

```python
from ipaddress import IPv4Address

addr = IPv4Address('10.0.0.1')  # O(1) fixed size
```

### IPv6Address()

#### Time Complexity: O(n)

```python
from ipaddress import IPv6Address

# Create from string: O(n)
addr = IPv6Address('2001:db8::1')  # O(n)

# Create from integer: O(1)
addr = IPv6Address(42540766411582592)  # O(1)

# Compressed form: O(1)
print(addr.compressed)  # '2001:db8::1'
```

#### Space Complexity: O(1)

```python
from ipaddress import IPv6Address

addr = IPv6Address('::1')  # O(1) fixed size
```

## Network Operations

### IPv4Network()

#### Time Complexity: O(n)

```python
from ipaddress import IPv4Network

# Create network: O(n) to parse CIDR
network = IPv4Network('192.168.0.0/24')  # O(n)

# Network properties: O(1)
print(network.network_address)  # '192.168.0.0'
print(network.broadcast_address)  # '192.168.0.255'
print(network.netmask)  # '255.255.255.0'
print(network.num_addresses)  # 256

# Check membership: O(1)
addr = IPv4Address('192.168.0.5')
if addr in network:
    print("In network")  # O(1)
```

#### Space Complexity: O(1)

```python
from ipaddress import IPv4Network

network = IPv4Network('10.0.0.0/8')  # O(1)
```

## Iteration and Enumeration

### Iterating Addresses

#### Time Complexity: O(n)

Where n = number of addresses.

```python
from ipaddress import IPv4Network

network = IPv4Network('192.168.0.0/24')

# Iterate all addresses: O(n)
for addr in network:  # O(256) for /24
    print(addr)

# Iterate with limit: O(k) where k = limit
count = 0
for addr in network.hosts():  # Excludes network/broadcast - O(n-2)
    if count >= 10:
        break
    count += 1
```

#### Space Complexity: O(1)

```python
from ipaddress import IPv4Network

# Iterator uses O(1) space
for addr in network:  # O(1) memory per iteration
    process(addr)
```

### Subnets

#### Time Complexity: O(2^k)

Where k = number of subnets.

```python
from ipaddress import IPv4Network

network = IPv4Network('192.168.0.0/24')

# Split into subnets: O(2^k) where k = number of new subnets
subnets = list(network.subnets(new_prefix=25))  # O(2) for /24 -> /25
# [192.168.0.0/25, 192.168.0.128/25]

# Multiple levels: O(2^k)
subnets = list(network.subnets(new_prefix=26))  # O(4)
```

#### Space Complexity: O(2^k)

```python
from ipaddress import IPv4Network

# Subnets list stored
subnets = list(network.subnets(new_prefix=25))  # O(2^k) space
```

## Common Patterns

### Check if Address is Private

```python
from ipaddress import ip_address

def is_private(addr_str):
    """Check if address is private: O(n)"""
    addr = ip_address(addr_str)  # O(n) to parse
    return addr.is_private  # O(1)

# Usage
if is_private('10.0.0.1'):
    print("Private network")
```

### Find Supernet

```python
from ipaddress import IPv4Network

def find_common_supernet(networks):
    """Find supernet containing all networks: O(n)"""
    networks = [IPv4Network(n) for n in networks]  # O(n)
    supernet = IPv4Network.supernet_of(networks)  # O(n)
    return supernet
```

### Parse Mixed Address Types

```python
from ipaddress import ip_address, ip_network

def parse_address(addr_str):
    """Auto-detect and parse address: O(n)"""
    try:
        return ip_address(addr_str)  # O(n) - IPv4 or IPv6
    except ValueError:
        return ip_network(addr_str)  # O(n) - Network
```

### Filter Addresses by Type

```python
from ipaddress import IPv4Address, IPv6Address, ip_address

def filter_addresses(addresses):
    """Separate IPv4 and IPv6: O(n)"""
    ipv4, ipv6 = [], []
    
    for addr_str in addresses:  # O(n)
        addr = ip_address(addr_str)  # O(m) where m = addr length
        if addr.version == 4:
            ipv4.append(addr)
        else:
            ipv6.append(addr)
    
    return ipv4, ipv6  # O(n) total
```

## Performance Characteristics

### Best Practices

```python
from ipaddress import IPv4Network, ip_address

# Good: Cache parsed addresses
addr = ip_address('192.168.1.1')  # O(n) once
network = IPv4Network('192.168.0.0/24')  # O(n)

for i in range(1000):
    if addr in network:  # O(1) reuse
        process(addr)

# Good: Use helpers for auto-detection
addr = ip_address(user_input)  # O(n) but handles both IPv4/6

# Avoid: Reparsing repeatedly
for i in range(1000):
    addr = ip_address(addr_str)  # O(n*1000)!

# Better: Parse once
addr = ip_address(addr_str)  # O(n)
for i in range(1000):
    use(addr)  # O(1)
```

### Large Network Iteration

```python
from ipaddress import IPv4Network

# Good: Use hosts() for actual IPs
network = IPv4Network('10.0.0.0/8')
for host in network.hosts():  # Skips network/broadcast
    process(host)

# Avoid: Iterating large networks
network = IPv4Network('10.0.0.0/8')
for addr in network:  # 16 million iterations!
    pass
```

## Comparison with String Parsing

```python
from ipaddress import IPv4Address
import socket

# ipaddress (structured)
addr = IPv4Address('192.168.1.1')  # O(n)
is_private = addr.is_private  # O(1)

# socket (string-based)
packed = socket.inet_aton('192.168.1.1')  # O(n)
# More work needed for checks

# ipaddress is better for validation and network ops
```

## Version Notes

- **Python 3.3+**: Full module support
- **Python 3.10+**: IPv6 scoping improvements

## Related Documentation

- [Socket Module](socket.md) - Low-level networking
- [Urllib Module](urllib.md) - URL handling
- [Ssl Module](ssl.md) - SSL/TLS support
