# ipaddress Module Complexity

The `ipaddress` module parses, compares and does arithmetic on IPv4 and IPv6 addresses, networks
and interfaces. Every object holds one integer of fixed width - 32 bits or 128 - and a network
adds a prefix length, so nearly every operation is O(1) whatever the size of the network. The
costs that grow are the ones that enumerate: iterating a network, `hosts()`, `subnets()`, and
the functions that summarise, collapse or exclude ranges.

`n` is the addresses in a network (`num_addresses`), `s` is the networks or subnets an operation
produces, and `m` is the addresses or networks passed to a function. `d` is the difference
between two prefix lengths. Arithmetic on a 128-bit integer is priced O(1), and so is parsing or
formatting an address string, whose length is bounded. The one exception is an IPv6 `%scope`
suffix, which is kept as written: parsing, formatting and comparing a scoped address also cost
the length of its scope.

## Complexity Reference

### Factory functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ipaddress.ip_address(address)` | O(1) | O(1) | Tries IPv4, then IPv6; raises `ValueError` if neither parses |
| `ipaddress.ip_network(address, strict=True)` | O(1) | O(1) | With `strict=True`, host bits set in the address raise `ValueError` |
| `ipaddress.ip_interface(address)` | O(1) | O(1) | An address together with the network it sits on |

### IPv4Address and IPv6Address

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ipaddress.IPv4Address(address)`, `ipaddress.IPv6Address(address)` | O(1) | O(1) | From a string, an integer, or packed bytes |
| `str(addr)`, `int(addr)`, `IPv4Address.packed`, `IPv4Address.exploded`, `IPv6Address.compressed` | O(1) | O(1) | |
| `IPv4Address.reverse_pointer` | O(1) | O(1) | The name for a reverse DNS lookup |
| `addr + k`, `addr - k`, `a < b`, `a == b`, `hash(addr)` | O(1) | O(1) | Ordering an IPv4 address against an IPv6 one raises `TypeError` |
| `IPv4Address.version`, `IPv4Address.max_prefixlen` | O(1) | O(1) | 4 and 32, or 6 and 128 |
| `IPv4Address.is_private`, `IPv4Address.is_global` | O(1) | O(1) | Checked against a fixed table of special-purpose ranges |
| `IPv4Address.is_multicast`, `IPv4Address.is_reserved`, `IPv4Address.is_loopback`, `IPv4Address.is_link_local`, `IPv4Address.is_unspecified` | O(1) | O(1) | |
| `IPv6Address.is_private`, `IPv6Address.is_global`, `IPv6Address.is_multicast`, `IPv6Address.is_reserved`, `IPv6Address.is_loopback`, `IPv6Address.is_link_local`, `IPv6Address.is_unspecified`, `IPv6Address.is_site_local` | O(1) | O(1) | |
| `IPv4Address.ipv6_mapped` | O(1) | O(1) | The `::ffff:a.b.c.d` form; Python 3.13+ |
| `IPv6Address.ipv4_mapped`, `IPv6Address.sixtofour`, `IPv6Address.teredo` | O(1) | O(1) | The embedded IPv4 address - for `teredo`, a (server, client) pair - or `None` when the address is not of that form |
| `IPv6Address.scope_id` | O(1) | O(1) | The `%zone` suffix, or `None` |
| `IPv6Address.max_prefixlen` | O(1) | O(1) | 128 |

### IPv4Network and IPv6Network

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ipaddress.IPv4Network(address, strict=True)`, `ipaddress.IPv6Network(address, strict=True)` | O(1) | O(1) | Holds the network address and prefix, not its addresses |
| `IPv4Network.network_address`, `IPv4Network.broadcast_address`, `IPv4Network.netmask`, `IPv4Network.hostmask`, `IPv4Network.prefixlen` | O(1) | O(1) | |
| `IPv6Network.network_address`, `IPv6Network.netmask` | O(1) | O(1) | |
| `IPv4Network.num_addresses` | O(1) | O(1) | n, computed from the prefix; there is no `len()` |
| `IPv4Network.with_prefixlen`, `IPv4Network.with_netmask`, `IPv4Network.with_hostmask` | O(1) | O(1) | String forms |
| `addr in net` | O(1) | O(1) | Masks the address; the network is not scanned. A network is never `in` another - use `subnet_of()` |
| `IPv4Network.subnet_of(other)`, `IPv4Network.supernet_of(other)`, `IPv4Network.overlaps(other)` | O(1) | O(1) | |
| `IPv4Network.compare_networks(other)`, `a < b`, `a == b`, `hash(net)` | O(1) | O(1) | |
| `net[i]` | O(1) | O(1) | Negative indexes count from the broadcast address |
| Iterating a network, `list(net)` | O(n) | O(1) per address | Lazy; `list()` holds all n |
| `IPv4Network.hosts()`, `IPv6Network.hosts()` | O(n) | O(1) per address | Lazy, except that a /32 or /128 returns a one-element list before Python 3.13.10 and 3.14.1. Skips the network and broadcast addresses of an IPv4 network, and the network address of an IPv6 one, except in /31 and /32 (/127 and /128) |
| `IPv4Network.subnets(prefixlen_diff=1, new_prefix=None)` | O(s) | O(1) per subnet | Lazy; s = 2 to the power of the prefix lengthening, and a /32 or /128 yields only itself |
| `IPv4Network.supernet(prefixlen_diff=1, new_prefix=None)` | O(1) | O(1) | |
| `IPv4Network.address_exclude(network)` | O(d) | O(1) per network | Lazy; yields d networks, d = the difference of the prefix lengths |
| `IPv4Network.is_private`, `IPv4Network.is_global`, `IPv4Network.is_multicast`, `IPv4Network.is_reserved`, `IPv4Network.is_loopback`, `IPv4Network.is_link_local`, `IPv4Network.is_unspecified` | O(1) | O(1) | |
| `IPv6Network.is_site_local` | O(1) | O(1) | |

### IPv4Interface and IPv6Interface

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ipaddress.IPv4Interface(address)`, `ipaddress.IPv6Interface(address)` | O(1) | O(1) | An address subclass: every address row applies |
| `IPv4Interface.ip`, `IPv4Interface.network` | O(1) | O(1) | The address, and the network with the host bits cleared |
| `IPv4Interface.with_prefixlen`, `IPv4Interface.with_netmask`, `IPv4Interface.with_hostmask` | O(1) | O(1) | String forms that keep the host bits |
| `IPv6Interface.ip`, `IPv6Interface.network`, `IPv6Interface.with_prefixlen`, `IPv6Interface.with_netmask`, `IPv6Interface.with_hostmask` | O(1) | O(1) | |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ipaddress.collapse_addresses(addresses)` | O(m log m) | O(m) | Merges adjacent and overlapping networks; the input is sorted, and mixing versions raises `TypeError` |
| `ipaddress.summarize_address_range(first, last)` | O(s) | O(1) per network | Lazy; s is at most twice the address width in bits, however many addresses the range holds |
| `ipaddress.get_mixed_type_key(obj)` | O(1) | O(1) | A sort key that orders addresses and networks together |
| `ipaddress.v4_int_to_packed(address)`, `ipaddress.v6_int_to_packed(address)` | O(1) | O(1) | 4 or 16 bytes, big-endian |
| `sorted(addresses)` | O(m log m) | O(m) | One version at a time; pass `key=get_mixed_type_key` to mix them |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ipaddress.IPV4LENGTH`, `ipaddress.IPV6LENGTH` | O(1) | O(1) | 32 and 128 |
| `ipaddress.AddressValueError` | O(1) | O(1) | Subclass of `ValueError`; raised for a malformed address |
| `ipaddress.NetmaskValueError` | O(1) | O(1) | Subclass of `ValueError`; raised for a malformed prefix or netmask |

## Addresses Are Integers

An address object is its integer. Parsing, formatting, arithmetic and comparison work on that one
value, so none of them depends on anything but the fixed width.

```python
import ipaddress

addr = ipaddress.ip_address("192.0.2.1")  # O(1)
assert isinstance(addr, ipaddress.IPv4Address)
assert int(addr) == 3221225985  # O(1)
assert addr + 1 == ipaddress.IPv4Address("192.0.2.2")  # O(1)
assert addr.packed == b"\xc0\x00\x02\x01"  # O(1)
assert addr.reverse_pointer == "1.2.0.192.in-addr.arpa"

v6 = ipaddress.ip_address("2001:db8::1")  # O(1)
assert v6.exploded == "2001:0db8:0000:0000:0000:0000:0000:0001"
assert ipaddress.IPv6Address(int(v6)) == v6

try:
    ipaddress.ip_address("192.0.2.256")
except ValueError as error:
    assert "does not appear to be an IPv4 or IPv6 address" in str(error)
else:
    raise AssertionError("an octet over 255 was accepted")
```

## Membership and Containment

`addr in net` masks the address with the network's prefix and compares, so a /8 answers as fast
as a /30. It only accepts an address: a network is never `in` another network, and
`subnet_of()` is the containment test for networks.

```python
import ipaddress

big = ipaddress.ip_network("10.0.0.0/8")
small = ipaddress.ip_network("10.1.2.0/24")

assert ipaddress.ip_address("10.1.2.3") in big  # O(1) - not a scan of 16 million
assert small not in big  # a network is never `in` another
assert small.subnet_of(big)  # O(1)
assert big.supernet_of(small)
assert big.overlaps(small)

try:
    ipaddress.ip_network("10.1.2.3/24")  # host bits set
except ValueError as error:
    assert "host bits set" in str(error)
else:
    raise AssertionError("a network with host bits was accepted")
assert ipaddress.ip_network("10.1.2.3/24", strict=False) == small
```

## Enumerating Networks

### Iteration and Indexing

A network does not hold its addresses. Iteration, `hosts()` and `subnets()` make each one as it
is asked for, so taking the first few from a /8 costs only those few; `list()` is what costs all
n. To reach one address, index the network rather than iterating to it, and to count, read
`num_addresses`.

```python
import ipaddress
from itertools import islice

net = ipaddress.ip_network("10.0.0.0/8")

assert net.num_addresses == 2 ** 24  # O(1)
assert net[1_000_000] == ipaddress.ip_address("10.15.66.64")  # O(1)
assert net[-1] == net.broadcast_address

first = list(islice(net.hosts(), 3))  # O(3), not O(n)
assert [str(a) for a in first] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]

subnets = net.subnets(new_prefix=24)  # O(1) - a generator
assert next(subnets) == ipaddress.ip_network("10.0.0.0/24")

small = ipaddress.ip_network("192.0.2.0/29")
assert len(list(small)) == 8  # O(n)
assert len(list(small.hosts())) == 6  # network and broadcast skipped
```

### Summarising, Collapsing and Excluding

These three turn ranges into networks. `summarize_address_range()` covers any range with at most
twice the address width in networks, `address_exclude()` yields one network per bit of prefix
difference, and `collapse_addresses()` sorts what it is given and merges neighbours.

```python
import ipaddress

first = ipaddress.ip_address("192.0.2.0")
last = ipaddress.ip_address("192.0.2.130")
summary = list(ipaddress.summarize_address_range(first, last))  # O(s)
assert [str(n) for n in summary] == ["192.0.2.0/25", "192.0.2.128/31", "192.0.2.130/32"]

outer = ipaddress.ip_network("192.0.2.0/24")
hole = ipaddress.ip_network("192.0.2.64/26")
rest = sorted(outer.address_exclude(hole))  # O(d), d = 26 - 24
assert [str(n) for n in rest] == ["192.0.2.0/26", "192.0.2.128/25"]

pieces = [ipaddress.ip_network(f"192.0.2.{i}/32") for i in range(256)]
merged = list(ipaddress.collapse_addresses(pieces))  # O(m log m)
assert merged == [outer]
```

## Special-Purpose Ranges

`is_private`, `is_global` and the other `is_*` properties check the address against a fixed
table of reserved ranges, so each is O(1). On a network they cost the same whatever its size.

```python
import ipaddress

assert ipaddress.ip_address("10.0.0.1").is_private  # O(1)
assert ipaddress.ip_address("8.8.8.8").is_global
assert ipaddress.ip_address("127.0.0.1").is_loopback
assert ipaddress.ip_address("224.0.0.1").is_multicast
assert ipaddress.ip_address("::1").is_loopback

# 100.64.0.0/10, shared address space, is neither
shared = ipaddress.ip_address("100.64.0.1")
assert not shared.is_private and not shared.is_global

assert ipaddress.ip_network("10.0.0.0/8").is_private  # O(1)
```

## Common Patterns

### Checking Addresses Against a List of Networks

Testing one address against k networks is k O(1) membership tests. Collapsing the list first
removes networks that other entries already cover, which can only shorten it.

```python
import ipaddress

allowed = [
    ipaddress.ip_network(text)
    for text in ["10.0.0.0/9", "10.128.0.0/9", "10.1.0.0/16", "192.0.2.0/24"]
]
allowed = list(ipaddress.collapse_addresses(allowed))  # O(k log k), once
assert [str(n) for n in allowed] == ["10.0.0.0/8", "192.0.2.0/24"]

def is_allowed(text):
    address = ipaddress.ip_address(text)  # O(1)
    return any(address in network for network in allowed)  # O(k)

assert is_allowed("10.200.0.1")
assert not is_allowed("198.51.100.1")
```

### Sorting Mixed Versions

IPv4 and IPv6 objects do not compare with each other. `get_mixed_type_key` gives a key that
orders by version first.

```python
import ipaddress

mixed = [ipaddress.ip_address(a) for a in ["2001:db8::1", "192.0.2.1", "10.0.0.1"]]

try:
    sorted(mixed)
except TypeError as error:
    assert "not of the same version" in str(error)
else:
    raise AssertionError("IPv4 and IPv6 addresses compared")

ordered = sorted(mixed, key=ipaddress.get_mixed_type_key)  # O(m log m)
assert [str(a) for a in ordered] == ["10.0.0.1", "192.0.2.1", "2001:db8::1"]
```

## Performance Best Practices

✅ **Do**:

- Parse once and keep the object: comparing it, testing membership and doing arithmetic with it
  are O(1)
- Test membership with `in` and containment with `subnet_of()` - neither scans the network
- Read `num_addresses` and index with `net[i]` instead of materialising the network
- Take what you need from `hosts()` and `subnets()` lazily, with `islice()` or a `break`
- Collapse a list of networks before testing many addresses against it

❌ **Avoid**:

- `list(net)` or `len(list(net.hosts()))` on a large network - O(n), and an IPv6 /64 has 2⁶⁴
  addresses
- Using `in` to ask whether one network contains another - it is always `False`
- Sorting mixed IPv4 and IPv6 objects without `key=get_mixed_type_key`

## Version Notes

- **Python 3.13+**: Added `IPv4Address.ipv6_mapped`
- **Python 3.10.15, 3.11.10, 3.12.4 and 3.13+**: `is_private` and `is_global` follow the IANA
  special-purpose registries; earlier patch releases answer differently for some ranges
- **Python 3.9.5+**: IPv4 strings with leading zeros, such as `010.0.0.1`, raise
  `AddressValueError`

## Related Modules

- **[socket](socket.md)** - `inet_pton()` and `inet_ntop()` convert addresses without building
  objects
- **[urllib](urllib.md)** - parses the host out of a URL before you hand it to `ip_address()`
