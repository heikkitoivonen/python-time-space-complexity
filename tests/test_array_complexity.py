"""Tests to verify documented time complexity of array module operations.

A spot check of docs/stdlib/array.md against the interpreter: every row of
its complexity table, plus the per-operation annotations in its code blocks.

The complexity claims all hold. At a hundred times the size, the operations
documented O(1) came in at 1.0-1.3x and the ones documented O(n) at 97-125x.

The memory section did not, and both tests for it were written against
measurements rather than the page:

* an array is *larger* than a list below about a dozen elements, because its
  header is 80 bytes against a list's 56. The page demonstrated the saving
  with five elements
* at useful sizes the page understates the saving by more than four times,
  because `sys.getsizeof(list)` counts the pointers and not the int objects
  they point at
"""

import array
import math
import sys
import time
from collections.abc import Callable
from typing import Any


def trimmed_mean(samples: list[float], trim_fraction: float = 0.1) -> float:
    """Return the trimmed mean to reduce outlier impact."""
    if not samples:
        return 0.0
    if trim_fraction <= 0:
        return sum(samples) / len(samples)
    k = int(len(samples) * trim_fraction)
    if len(samples) - 2 * k <= 0:
        return sum(samples) / len(samples)
    samples = sorted(samples)
    core = samples[k : len(samples) - k]
    return sum(core) / len(core)


def measure_time(func: Callable[[], Any], iterations: int = 100) -> float:
    """Measure trimmed mean time for a function over multiple iterations."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return trimmed_mean(times)


def is_constant_time(small_time: float, large_time: float, tolerance: float = 3.0) -> bool:
    """Check if two times are within tolerance (suggesting O(1))."""
    if small_time == 0:
        return large_time < 1e-6
    return large_time / small_time < tolerance


def is_linear_time(
    small_time: float,
    large_time: float,
    size_ratio: float,
    tolerance: float = 3.0,
) -> bool:
    """Check if time scales linearly with size."""
    if small_time == 0:
        return True
    return large_time / small_time < size_ratio * tolerance


def scales_with_size(small_time: float, large_time: float, size_ratio: float) -> bool:
    """Check that time actually grew with size, roughly in proportion."""
    if small_time == 0:
        return False
    ratio = large_time / small_time
    return size_ratio / 3 < ratio < size_ratio * 3


class TestArrayComplexity:
    """Test array operation complexities as documented in docs/stdlib/array.md."""

    SMALL_SIZE = 10_000
    LARGE_SIZE = 1_000_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_creation_is_on(self) -> None:
        """array.array() should be O(n)."""
        small_source = [0] * self.SMALL_SIZE
        large_source = [0] * self.LARGE_SIZE

        small_time = measure_time(lambda: array.array("i", small_source), iterations=10)
        large_time = measure_time(lambda: array.array("i", large_source), iterations=10)

        assert scales_with_size(small_time, large_time, self.SIZE_RATIO), (
            f"array() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_indexing_is_o1(self) -> None:
        """Indexing should be O(1) - direct offset into the buffer."""
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small[self.SMALL_SIZE // 2])
        large_time = measure_time(lambda: large[self.LARGE_SIZE // 2])

        assert is_constant_time(small_time, large_time), (
            f"indexing appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_len_is_o1(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        small_time = measure_time(lambda: len(small))
        large_time = measure_time(lambda: len(large))

        assert is_constant_time(small_time, large_time), (
            f"len() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_append_is_o1_amortized(self) -> None:
        """append() should be O(1) amortized."""
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        def append_to(target: array.array) -> None:
            target.append(1)
            target.pop()

        small_time = measure_time(lambda: append_to(small))
        large_time = measure_time(lambda: append_to(large))

        assert is_constant_time(small_time, large_time), (
            f"append() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_append_resizes_in_jumps(self) -> None:
        """The table's "O(n) worst case when resizing" - the buffer grows in
        steps, so most appends touch only a free slot."""
        values = array.array("i")
        sizes: set[int] = set()
        for _ in range(2_000):
            values.append(0)
            sizes.add(sys.getsizeof(values))

        assert 1 < len(sizes) < 2_000, (
            f"expected occasional reallocation, saw {len(sizes)} distinct sizes"
        )

    def test_extend_is_ok_not_on(self) -> None:
        """extend() should be O(k) in what is added, not O(n) in the array."""
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))
        addition = [0] * 100

        def extend_then_trim(target: array.array) -> None:
            target.extend(addition)
            del target[-100:]

        small_time = measure_time(lambda: extend_then_trim(small), iterations=50)
        large_time = measure_time(lambda: extend_then_trim(large), iterations=50)

        assert is_constant_time(small_time, large_time), (
            f"extend() should not depend on the existing length: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_search_is_on(self) -> None:
        """Search should be O(n) - linear scan."""
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        small_time = measure_time(lambda: (self.SMALL_SIZE - 1) in small, iterations=20)
        large_time = measure_time(lambda: (self.LARGE_SIZE - 1) in large, iterations=20)

        assert scales_with_size(small_time, large_time, self.SIZE_RATIO), (
            f"membership doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_is_on(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small.index(self.SMALL_SIZE - 1), iterations=20)
        large_time = measure_time(lambda: large.index(self.LARGE_SIZE - 1), iterations=20)

        assert scales_with_size(small_time, large_time, self.SIZE_RATIO), (
            f"index() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_insert_is_on(self) -> None:
        """Insert should be O(n) - the tail shifts."""
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        def insert_then_remove(target: array.array) -> None:
            target.insert(0, 1)
            target.pop(0)

        small_time = measure_time(lambda: insert_then_remove(small), iterations=20)
        large_time = measure_time(lambda: insert_then_remove(large), iterations=20)

        assert scales_with_size(small_time, large_time, self.SIZE_RATIO), (
            f"insert() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_remove_is_on(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        def remove_last_value(target: array.array, value: int) -> None:
            target.remove(value)
            target.append(value)

        small_time = measure_time(
            lambda: remove_last_value(small, self.SMALL_SIZE - 1), iterations=20
        )
        large_time = measure_time(
            lambda: remove_last_value(large, self.LARGE_SIZE - 1), iterations=20
        )

        assert scales_with_size(small_time, large_time, self.SIZE_RATIO), (
            f"remove() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_typecodes_is_o1(self) -> None:
        """typecodes is a module-level string, not computed."""
        assert isinstance(array.typecodes, str)
        assert set("bBhHiIlLqQfd") <= set(array.typecodes)


class TestPopPosition:
    """docs/stdlib/array.md: "Pop - O(1) at end, O(n) elsewhere"."""

    SMALL_SIZE = 10_000
    LARGE_SIZE = 1_000_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_pop_from_the_end_is_o1(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        def pop_and_restore(target: array.array) -> None:
            value = target.pop()
            target.append(value)

        small_time = measure_time(lambda: pop_and_restore(small))
        large_time = measure_time(lambda: pop_and_restore(large))

        assert is_constant_time(small_time, large_time), (
            f"pop() at the end appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_pop_from_the_front_is_on(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))

        def pop_front_and_restore(target: array.array) -> None:
            value = target.pop(0)
            target.insert(0, value)

        small_time = measure_time(lambda: pop_front_and_restore(small), iterations=20)
        large_time = measure_time(lambda: pop_front_and_restore(large), iterations=20)

        assert scales_with_size(small_time, large_time, self.SIZE_RATIO), (
            f"pop(0) doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestConversions:
    """docs/stdlib/array.md prices every conversion at O(n)."""

    SMALL_SIZE = 10_000
    LARGE_SIZE = 1_000_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def _linear(self, small: Callable[[], Any], large: Callable[[], Any], label: str) -> None:
        small_time = measure_time(small, iterations=10)
        large_time = measure_time(large, iterations=10)
        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"{label} doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 10, (
            f"{label} should scale with the array: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_tolist_is_on(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))
        self._linear(small.tolist, large.tolist, "tolist()")

    def test_tobytes_is_on(self) -> None:
        small = array.array("i", range(self.SMALL_SIZE))
        large = array.array("i", range(self.LARGE_SIZE))
        self._linear(small.tobytes, large.tobytes, "tobytes()")

    def test_frombytes_is_on(self) -> None:
        small_bytes = array.array("i", range(self.SMALL_SIZE)).tobytes()
        large_bytes = array.array("i", range(self.LARGE_SIZE)).tobytes()
        self._linear(
            lambda: array.array("i").frombytes(small_bytes),
            lambda: array.array("i").frombytes(large_bytes),
            "frombytes()",
        )

    def test_fromlist_is_on(self) -> None:
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))
        self._linear(
            lambda: array.array("i").fromlist(small_list),
            lambda: array.array("i").fromlist(large_list),
            "fromlist()",
        )

    def test_round_trips_preserve_the_values(self) -> None:
        source = array.array("i", range(100))
        assert array.array("i", source.tolist()) == source

        rebuilt = array.array("i")
        rebuilt.frombytes(source.tobytes())
        assert rebuilt == source


class TestTypeCodesFixItemSize:
    """docs/stdlib/array.md: the type code fixes the bytes per item, which is
    what array buys over list.

    Moved here from tests/test_stdlib_claims.py now that the module has a
    file of its own.
    """

    def test_documented_item_sizes(self) -> None:
        assert array.array("b").itemsize == 1
        assert array.array("B").itemsize == 1
        assert array.array("f").itemsize == 4
        assert array.array("d").itemsize == 8
        # The page says 'i' is 2-4 bytes, which is the C int it maps to.
        assert 2 <= array.array("i").itemsize <= 4
        assert 2 <= array.array("I").itemsize <= 4

    def test_storage_follows_item_size(self) -> None:
        count = 10_000
        as_bytes = array.array("b", [0] * count)
        as_doubles = array.array("d", [0.0] * count)

        overhead = sys.getsizeof(array.array("b"))
        bytes_payload = sys.getsizeof(as_bytes) - overhead
        doubles_payload = sys.getsizeof(as_doubles) - overhead

        assert math.isclose(doubles_payload / bytes_payload, 8, rel_tol=0.1), (
            f"a 'd' array should hold eight times the bytes of a 'b' array: "
            f"{bytes_payload} vs {doubles_payload}"
        )

    def test_the_type_code_is_enforced(self) -> None:
        values = array.array("i", [1, 2, 3])
        try:
            values.append(1.5)  # type: ignore[arg-type]
        except TypeError:
            pass
        else:  # pragma: no cover - would mean array stopped being homogeneous
            raise AssertionError("an int array should reject a float")


class TestMemoryFootprint:
    """docs/stdlib/array.md's memory comparison, as corrected by these tests.

    The page demonstrated "Array size: Smaller" with five elements. At that
    size it is a coin flip, and below about a dozen the array is bigger.
    """

    def test_an_array_is_larger_than_a_list_when_tiny(self) -> None:
        one_list = list(range(1))
        one_array = array.array("i", range(1))

        assert sys.getsizeof(one_array) > sys.getsizeof(one_list), (
            f"array pays a bigger header: list={sys.getsizeof(one_list)} "
            f"array={sys.getsizeof(one_array)}"
        )

    def test_the_header_is_the_reason(self) -> None:
        assert sys.getsizeof(array.array("i")) > sys.getsizeof([])

    def test_the_saving_arrives_by_a_few_dozen_elements(self) -> None:
        values = list(range(50))
        assert sys.getsizeof(array.array("i", values)) < sys.getsizeof(values)

    def test_getsizeof_understates_the_saving(self) -> None:
        """A list also pays for the int objects, which getsizeof omits."""
        count = 10_000
        # Above the small-int cache, so each element is a distinct object.
        values = list(range(256, 256 + count))
        packed = array.array("i", values)

        shallow = sys.getsizeof(values)
        deep = shallow + sum(sys.getsizeof(value) for value in values)
        packed_size = sys.getsizeof(packed)

        assert shallow / packed_size < 3, "the pointer-only comparison is about 2x"
        assert deep / packed_size > 5, (
            f"counting the int objects it is far more: shallow={shallow / packed_size:.1f}x "
            f"deep={deep / packed_size:.1f}x"
        )
