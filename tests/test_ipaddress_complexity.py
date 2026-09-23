"""Tests for docs/stdlib/ipaddress.md.

The page prices every object as one fixed-width integer plus a prefix, so
almost every row is O(1), and puts the growing costs in enumeration and in
the three range functions. The O(1) rows that a network's size could
plausibly affect - membership, indexing, the `is_*` properties - are timed
on a small network against a large one; that networks hold no addresses is settled
by traced allocation; laziness by taking one item from a network too large to
enumerate. Output-size bounds are settled by counting what is yielded.

Measurement scope:

* An `IPv4Network` /8 and an `IPv6Network` /32 each peak under 10 KB to
  build; `list()` over a /16 peaks over 3 MB. The first item of iteration,
  `hosts()` and `subnets()` over an IPv6 /32 arrives in a generator, as do
  `address_exclude()` and `summarize_address_range()`.
* `addr in net` for the last address of a /30 and of a /8, `net[i]` for
  index 250 of an IPv6 /120 and index 2 ** 96 - 5 of a /32, and `is_private`
  on an IPv4 /30 and /8 each cost under 3x the smaller case.
* `hosts()` on a /32 and a /128 is asserted to be an iterator from 3.13.10
  and 3.14.1 and a one-element list before; `subnets()` on either yields the
  network itself. `hosts()` is asserted to skip the network and broadcast addresses of an
  IPv4 /29, the network address alone of an IPv6 /126, and nothing in /31,
  /32, /127 and /128. `subnets(new_prefix=p)` yields 2 ** (p - prefixlen)
  networks for differences of 1, 4 and 8. `address_exclude()` yields exactly
  d networks for d of 2, 8 and 24.
* `summarize_address_range()` yields 62 networks over the whole IPv4 range
  less its ends, and 254 over the IPv6 one, within twice the width; they are
  asserted contiguous from the first address to the last. A single address
  yields one. `address_exclude()`'s networks are asserted inside the outer
  network, clear of the hole and of each other.
* `collapse_addresses()` merges 256 /32s into one /24 and a covered /16 into
  its /8, and raises `TypeError` for mixed versions. 1,000, 10,000 and
  100,000 shuffled /32s each cost under 30x the previous tenth, which
  excludes quadratic growth; the m log m and the linear shapes are not told
  apart.
* Parsing from a string, an integer and packed bytes is asserted to give the
  same address, `str`, `packed`, `exploded`, `compressed` and
  `reverse_pointer` are asserted by value, and ordering an IPv4 against an
  IPv6 address raises `TypeError` while `get_mixed_type_key` sorts them.
* `is_private` and `is_global` are asserted for 192.0.0.8, 192.0.0.9 and
  100.64.0.1 on
  the patch releases that carry the IANA registry fix, 3.10.15, 3.11.10,
  3.12.4 and 3.13.0, and the test is skipped on an earlier patch.
  `ipv6_mapped` is guarded to 3.13+.
* Leading zeros in an IPv4 string raise `AddressValueError`; both exceptions
  subclass `ValueError`.
* Every fenced Python block runs in its own subprocess and temporary working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That earlier patch releases answer `is_private` and `is_global` differently.
  CI runs the newest patch of each minor, which all carry the fix; the
  boundary is read from `git tag --contains` on the backport commits.
* Parsing is priced O(1) because a valid address string has a bounded
  length. An over-long string is rejected after `str.split`, O(its length),
  which is not measured. The IPv6 `%scope` exception the page names is
  observed by a million-character scope that survives `str()` and peaks
  over a megabyte to parse; the cost of comparing scoped addresses is not
  measured.
* `collapse_addresses()` is measured only on /32 networks in random order;
  prefix lengths and pre-sorted input are not varied.
* The audit's unclassified runtime members - `IPv4Interface.hostmask`,
  `IPv4Network.is_global` and the like - are inherited from the rows the page
  prices for the base class.
"""

from __future__ import annotations

import ipaddress
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from functools import partial
from itertools import islice, pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ipaddress.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def v4(text: str) -> ipaddress.IPv4Network:
    return ipaddress.IPv4Network(text)


def v6(text: str) -> ipaddress.IPv6Network:
    return ipaddress.IPv6Network(text)


def net(text: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    return v6(text) if ":" in text else v4(text)


def addr(text: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    return ipaddress.ip_address(text)


class TestAddressesAreIntegers:
    """Addresses parse, format, compare and do arithmetic in O(1)."""

    def test_every_constructor_gives_the_same_address(self) -> None:
        text = ipaddress.IPv4Address("192.0.2.1")

        assert ipaddress.IPv4Address(3221225985) == text
        assert ipaddress.IPv4Address(b"\xc0\x00\x02\x01") == text
        assert ipaddress.IPv6Address(int(addr("2001:db8::1"))) == addr("2001:db8::1")

    def test_the_forms_it_formats_to(self) -> None:
        v4 = ipaddress.IPv4Address("192.0.2.1")
        v6 = ipaddress.IPv6Address("2001:db8::1")

        assert (str(v4), v4.packed, v4.exploded) == ("192.0.2.1", b"\xc0\x00\x02\x01", "192.0.2.1")
        assert v4.reverse_pointer == "1.2.0.192.in-addr.arpa"
        assert v6.compressed == "2001:db8::1"
        assert v6.exploded == "2001:0db8:0000:0000:0000:0000:0000:0001"

    def test_arithmetic_and_comparison(self) -> None:
        a = ipaddress.IPv4Address("192.0.2.1")

        assert a + 1 == ipaddress.IPv4Address("192.0.2.2")
        assert a - 1 < a
        assert hash(a) == hash(ipaddress.IPv4Address(int(a)))

    def test_ordering_across_versions_raises_and_the_key_mixes_them(self) -> None:
        mixed = [addr("2001:db8::1"), addr("192.0.2.1")]

        with pytest.raises(TypeError, match="not of the same version"):
            sorted(mixed)
        assert sorted(mixed, key=lambda a: ipaddress.get_mixed_type_key(a)) == mixed[::-1]
        assert ipaddress.get_mixed_type_key(mixed[1]) == (4, mixed[1])

    def test_version_and_width(self) -> None:
        v4, v6 = addr("192.0.2.1"), addr("::1")

        assert (v4.version, v4.max_prefixlen) == (4, 32)
        assert (v6.version, v6.max_prefixlen) == (6, 128)
        assert (ipaddress.IPV4LENGTH, ipaddress.IPV6LENGTH) == (32, 128)

    def test_the_factories_try_both_versions(self) -> None:
        assert isinstance(addr("10.0.0.1"), ipaddress.IPv4Address)
        assert isinstance(addr("::1"), ipaddress.IPv6Address)
        assert isinstance(ipaddress.ip_interface("10.0.0.1/8"), ipaddress.IPv4Interface)
        with pytest.raises(ValueError, match="does not appear to be an IPv4 or IPv6 address"):
            addr("192.0.2.256")

    def test_packing_helpers(self) -> None:
        assert ipaddress.v4_int_to_packed(1) == b"\x00\x00\x00\x01"
        assert ipaddress.v6_int_to_packed(1) == b"\x00" * 15 + b"\x01"

    def test_embedded_ipv4_forms(self) -> None:
        assert ipaddress.IPv6Address("::ffff:192.0.2.1").ipv4_mapped == addr("192.0.2.1")
        assert ipaddress.IPv6Address("2002:c000:204::1").sixtofour == addr("192.0.2.4")
        assert ipaddress.IPv6Address("2001:0:4136:e378:8000:63bf:3fff:fdd2").teredo == (
            addr("65.54.227.120"),
            addr("192.0.2.45"),
        )
        plain = ipaddress.IPv6Address("2001:db8::1")
        assert (plain.ipv4_mapped, plain.sixtofour, plain.teredo) == (None, None, None)

    def test_scope_id(self) -> None:
        assert ipaddress.IPv6Address("fe80::1%eth0").scope_id == "eth0"
        assert ipaddress.IPv6Address("fe80::1").scope_id is None

    def test_a_scope_is_kept_as_written(self) -> None:
        text = "fe80::1%" + "x" * 1_000_000

        scoped = ipaddress.IPv6Address(text)

        assert scoped.scope_id == "x" * 1_000_000
        assert str(scoped) == text
        assert peak_bytes(partial(ipaddress.IPv6Address, text)) > 1_000_000

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_ipv6_mapped(self) -> None:
        mapped = ipaddress.IPv4Address("192.0.2.1").ipv6_mapped  # type: ignore[attr-defined]

        assert mapped == ipaddress.IPv6Address("::ffff:192.0.2.1")

    def test_leading_zeros_are_rejected(self) -> None:
        with pytest.raises(ipaddress.AddressValueError, match="Leading zeros"):
            ipaddress.IPv4Address("010.0.0.1")
        assert issubclass(ipaddress.AddressValueError, ValueError)
        assert issubclass(ipaddress.NetmaskValueError, ValueError)
        with pytest.raises(ipaddress.NetmaskValueError):
            ipaddress.IPv4Network("10.0.0.0/33")


class TestNetworksHoldNoAddresses:
    """A network is its address and prefix: building one allocates nothing
    per address, membership and indexing are arithmetic, and enumeration is
    lazy."""

    def test_building_a_huge_network_allocates_nothing_for_its_addresses(self) -> None:
        v4("10.0.0.0/8")
        v6("2001:db8::/32")  # warm the netmask caches

        assert peak_bytes(partial(ipaddress.IPv4Network, "10.0.0.0/8")) < 10_000
        assert peak_bytes(partial(ipaddress.IPv6Network, "2001:db8::/32")) < 10_000

    def test_listing_one_holds_every_address(self) -> None:
        peak = peak_bytes(lambda: list(v4("10.0.0.0/16")))

        assert peak > 3_000_000, f"list() of 65,536 addresses peaked at {peak}"

    def test_attributes(self) -> None:
        network = v4("192.0.2.0/24")

        assert network.network_address == addr("192.0.2.0")
        assert network.broadcast_address == addr("192.0.2.255")
        assert (str(network.netmask), str(network.hostmask)) == ("255.255.255.0", "0.0.0.255")
        assert (network.prefixlen, network.num_addresses) == (24, 256)
        assert network.with_prefixlen == "192.0.2.0/24"
        assert network.with_netmask == "192.0.2.0/255.255.255.0"
        assert network.with_hostmask == "192.0.2.0/0.0.0.255"
        with pytest.raises(TypeError):
            len(network)  # type: ignore[arg-type]

    def test_strict_rejects_host_bits(self) -> None:
        with pytest.raises(ValueError, match="host bits set"):
            ipaddress.ip_network("10.1.2.3/24")
        assert ipaddress.ip_network("10.1.2.3/24", strict=False) == v4("10.1.2.0/24")

    def test_containment(self) -> None:
        big, small = v4("10.0.0.0/8"), v4("10.1.2.0/24")

        assert addr("10.1.2.3") in big
        assert small not in big, "a network is never `in` another"
        assert small.subnet_of(big) and big.supernet_of(small)
        assert big.overlaps(small) and not small.overlaps(v4("10.2.0.0/16"))
        assert small.compare_networks(v4("10.1.3.0/24")) == -1
        assert small.supernet() == v4("10.1.2.0/23")
        assert small.supernet(new_prefix=8) == big

    def test_indexing(self) -> None:
        network = v4("10.0.0.0/8")

        assert network[1_000_000] == addr("10.15.66.64")
        assert network[-1] == network.broadcast_address

    @pytest.mark.timing
    def test_membership_does_not_scan_the_network(self) -> None:
        cases = [(v4("10.0.0.0/30"), addr("10.0.0.3")), (v4("10.0.0.0/8"), addr("10.255.255.255"))]
        assert all(target in network for network, target in cases)

        durations = [
            best_ns(partial(network.__contains__, target), inner=1_000) for network, target in cases
        ]

        assert durations[1] < durations[0] * 3, f"the last of 4, then of 2**24: {durations} ns"

    @pytest.mark.timing
    def test_indexing_does_not_walk_the_network(self) -> None:
        cases = [(v6("2001:db8::/120"), 250), (v6("2001:db8::/32"), 2**96 - 5)]
        assert all(
            int(network[index]) == int(network.network_address) + index for network, index in cases
        )

        durations = [
            best_ns(partial(network.__getitem__, index), inner=1_000) for network, index in cases
        ]

        assert durations[1] < durations[0] * 3, f"index 250, then 2**96 - 5: {durations} ns"

    @pytest.mark.timing
    def test_is_private_does_not_grow_with_the_network(self) -> None:
        networks = [v4("10.0.0.0/30"), v4("10.0.0.0/8")]
        durations = [best_ns(lambda n=n: n.is_private, inner=1_000) for n in networks]  # type: ignore[misc]

        assert durations[1] < durations[0] * 3, f"a /30 and a /8: {durations} ns"


class TestEnumerationIsLazy:
    """Iteration, `hosts()`, `subnets()` and `address_exclude()` produce one
    item at a time, and produce exactly the items the page counts."""

    HUGE = "2001:db8::/32"

    @pytest.mark.parametrize("method", ["__iter__", "hosts", "subnets"])
    def test_the_first_item_arrives_without_the_rest(self, method: str) -> None:
        network = net(self.HUGE)
        items = getattr(network, method)()

        first = next(items)

        assert first in (network.network_address, network.network_address + 1, v6("2001:db8::/33"))

    def test_address_exclude_and_summarize_are_generators(self) -> None:
        excluded = v4("10.0.0.0/8").address_exclude(v4("10.1.2.3/32"))
        summary = ipaddress.summarize_address_range(addr("10.0.0.0"), addr("10.0.0.5"))

        assert isinstance(excluded, types.GeneratorType)
        assert isinstance(summary, types.GeneratorType)

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("192.0.2.0/29", [f"192.0.2.{i}" for i in range(1, 7)]),
            ("192.0.2.0/31", ["192.0.2.0", "192.0.2.1"]),
            ("192.0.2.0/32", ["192.0.2.0"]),
            ("2001:db8::/126", ["2001:db8::1", "2001:db8::2", "2001:db8::3"]),
            ("2001:db8::/127", ["2001:db8::", "2001:db8::1"]),
            ("2001:db8::/128", ["2001:db8::"]),
        ],
    )
    def test_which_addresses_hosts_skips(self, text: str, expected: list[str]) -> None:
        assert [str(a) for a in net(text).hosts()] == expected

    @pytest.mark.skipif(
        sys.version_info[:2] == (3, 13)
        and sys.version_info < (3, 13, 10)
        or sys.version_info[:2] == (3, 14)
        and sys.version_info < (3, 14, 1)
        or sys.version_info < (3, 13),
        reason="a one-element list before 3.13.10 and 3.14.1",
    )
    @pytest.mark.parametrize("text", ["192.0.2.0/32", "2001:db8::/128"])
    def test_a_host_network_s_hosts_is_an_iterator(self, text: str) -> None:
        hosts = net(text).hosts()

        assert iter(hosts) is hosts
        assert next(hosts) == net(text).network_address

    @pytest.mark.skipif(sys.version_info >= (3, 14, 1), reason="an iterator from 3.14.1")
    @pytest.mark.skipif(
        (3, 13, 10) <= sys.version_info < (3, 14), reason="an iterator from 3.13.10"
    )
    @pytest.mark.parametrize("text", ["192.0.2.0/32", "2001:db8::/128"])
    def test_a_host_network_s_hosts_was_a_list(self, text: str) -> None:
        assert net(text).hosts() == [net(text).network_address]

    @pytest.mark.parametrize("text", ["192.0.2.0/32", "2001:db8::/128"])
    def test_a_host_network_s_subnets_is_itself(self, text: str) -> None:
        assert list(net(text).subnets()) == [net(text)]

    @pytest.mark.parametrize("difference", [1, 4, 8])
    def test_subnets_yields_two_to_the_difference(self, difference: int) -> None:
        network = v4("10.0.0.0/16")

        subnets = list(network.subnets(new_prefix=16 + difference))

        assert len(subnets) == 2**difference
        assert subnets == list(network.subnets(prefixlen_diff=difference))

    @pytest.mark.parametrize("excluded_prefix", [10, 16, 32])
    def test_address_exclude_yields_one_network_per_bit(self, excluded_prefix: int) -> None:
        outer = v4("10.0.0.0/8")
        hole = ipaddress.IPv4Network(("10.1.2.3", excluded_prefix), strict=False)

        rest = list(outer.address_exclude(hole))

        assert len(rest) == excluded_prefix - 8
        assert sum(n.num_addresses for n in rest) + hole.num_addresses == outer.num_addresses
        assert all(n.subnet_of(outer) and not n.overlaps(hole) for n in rest)
        assert not any(a.overlaps(b) for a, b in pairwise(sorted(rest)))

    def test_islice_takes_only_what_it_asks_for(self) -> None:
        assert [str(a) for a in islice(v4("10.0.0.0/8").hosts(), 3)] == [
            "10.0.0.1",
            "10.0.0.2",
            "10.0.0.3",
        ]


class TestSummarizingAndCollapsing:
    """`summarize_address_range` | O(s), s at most twice the width;
    `collapse_addresses` | O(m log m)."""

    @pytest.mark.parametrize(
        ("first", "last", "width"),
        [
            ("0.0.0.1", "255.255.255.254", 32),
            ("::1", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:fffe", 128),
        ],
    )
    def test_any_range_takes_at_most_twice_the_width(
        self, first: str, last: str, width: int
    ) -> None:
        summary = list(ipaddress.summarize_address_range(addr(first), addr(last)))

        assert len(summary) == 2 * width - 2
        assert summary[0].network_address == addr(first)
        assert summary[-1].broadcast_address == addr(last)
        for before, after in pairwise(summary):
            assert int(after.network_address) == int(before.broadcast_address) + 1

    def test_a_single_address_is_one_network(self) -> None:
        one = addr("192.0.2.7")

        assert list(ipaddress.summarize_address_range(one, one)) == [v4("192.0.2.7/32")]

    def test_collapse_merges_neighbours_and_covered_networks(self) -> None:
        pieces = [v4(f"192.0.2.{i}/32") for i in range(256)]

        assert list(ipaddress.collapse_addresses(pieces)) == [v4("192.0.2.0/24")]
        assert list(ipaddress.collapse_addresses([v4("10.0.0.0/8"), v4("10.1.0.0/16")])) == [
            v4("10.0.0.0/8")
        ]

    def test_collapse_refuses_mixed_versions(self) -> None:
        with pytest.raises(TypeError, match="not of the same version"):
            mixed: list[Any] = [v4("10.0.0.0/8"), v6("2001:db8::/32")]
            list(ipaddress.collapse_addresses(mixed))

    @pytest.mark.timing
    def test_collapse_is_not_quadratic(self) -> None:
        rng = random.Random(7)

        def inputs(size: int) -> list[ipaddress.IPv4Network]:
            chosen = rng.sample(range(2**24), size)
            return [ipaddress.IPv4Network((value << 8, 32)) for value in chosen]

        sizes = (1_000, 10_000, 100_000)
        durations = [
            best_ns(
                partial(lambda items: list(ipaddress.collapse_addresses(items)), inputs(size)),
                repeats=3,
            )
            for size in sizes
        ]

        for smaller, larger in pairwise(durations):
            assert larger < smaller * 30, f"10x the networks each step: {durations} ns"


class TestSpecialPurposeRanges:
    """The `is_*` properties answer from a fixed table."""

    def test_common_answers(self) -> None:
        assert addr("10.0.0.1").is_private
        assert addr("8.8.8.8").is_global
        assert addr("127.0.0.1").is_loopback and addr("::1").is_loopback
        assert addr("224.0.0.1").is_multicast and addr("ff02::1").is_multicast
        assert addr("169.254.0.1").is_link_local and addr("fe80::1").is_link_local
        assert addr("0.0.0.0").is_unspecified and addr("::").is_unspecified
        assert addr("240.0.0.1").is_reserved
        assert ipaddress.IPv6Address("fec0::1").is_site_local
        assert v6("fec0::/10").is_site_local
        assert v4("10.0.0.0/8").is_private and not v4("10.0.0.0/8").is_global

    @pytest.mark.skipif(
        sys.version_info[:2] == (3, 10)
        and sys.version_info < (3, 10, 15)
        or sys.version_info[:2] == (3, 11)
        and sys.version_info < (3, 11, 10)
        or sys.version_info[:2] == (3, 12)
        and sys.version_info < (3, 12, 4),
        reason="the IANA registry fix arrived in 3.10.15, 3.11.10, 3.12.4 and 3.13.0",
    )
    def test_the_registry_answers(self) -> None:
        assert addr("192.0.0.9").is_global
        assert addr("192.0.0.8").is_private
        shared = addr("100.64.0.1")
        assert not shared.is_private and not shared.is_global


class TestInterfaces:
    """An interface is an address subclass carrying its network."""

    def test_interface_attributes(self) -> None:
        interface = ipaddress.IPv4Interface("192.0.2.5/24")

        assert isinstance(interface, ipaddress.IPv4Address)
        assert interface.ip == addr("192.0.2.5")
        assert interface.network == v4("192.0.2.0/24")
        assert interface.with_prefixlen == "192.0.2.5/24"
        assert interface.with_netmask == "192.0.2.5/255.255.255.0"
        assert interface.with_hostmask == "192.0.2.5/0.0.0.255"

        interface6 = ipaddress.IPv6Interface("2001:db8::5/64")
        assert isinstance(interface6, ipaddress.IPv6Address)
        assert (interface6.ip, interface6.network) == (addr("2001:db8::5"), v6("2001:db8::/64"))
        assert interface6.with_prefixlen == "2001:db8::5/64"


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, and
    asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "len(list(small)) == 8" in s)
        mutated = source.replace("len(list(small)) == 8", "len(list(small)) == 7", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
