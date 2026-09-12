"""Field access and conversion tests for docs/stdlib/namedtuple.md.

Field counts vary while field names and values have bounded size.
"""

from collections import namedtuple

import pytest

from tests.collection_timing import is_constant_time, is_linear_time, measure_time


class TestNamedTupleComplexity:
    """Test namedtuple operation complexities."""

    @pytest.mark.timing
    def test_attribute_access_is_o1(self) -> None:
        """Field access should be O(1)."""
        SmallPoint = namedtuple("SmallPoint", ["x", "y"])
        LargePoint = namedtuple("LargePoint", ["x", *[f"f{i}" for i in range(999)]])
        small_pt = SmallPoint(1, 2)
        large_pt = LargePoint(*range(1000))

        small_time = measure_time(lambda: small_pt.x)
        large_time = measure_time(lambda: large_pt.x)

        assert is_constant_time(small_time, large_time), (
            f"namedtuple attribute access appears non-constant: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_asdict_is_on(self) -> None:
        """_asdict() should be O(n) in number of fields."""
        SmallNT = namedtuple("SmallNT", [f"f{i}" for i in range(10)])
        LargeNT = namedtuple("LargeNT", [f"f{i}" for i in range(1000)])
        small_nt = SmallNT(*range(10))
        large_nt = LargeNT(*range(1000))

        small_time = measure_time(lambda: small_nt._asdict(), iterations=50)
        large_time = measure_time(lambda: large_nt._asdict(), iterations=50)

        assert is_linear_time(small_time, large_time, 100), (
            f"_asdict() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
