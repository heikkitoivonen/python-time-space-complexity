"""Tests to verify documented complexity of abc.get_cache_token().

docs/stdlib/abc.md's `get_cache_token()` row had no test coverage at all
before this file. It was previously tested indirectly under
tests/test_functools_complexity.py, because `functools.get_cache_token`
happens to work too -- `functools.py` imports the name from `abc` for its
own internal use. That import is not part of the documented functools API
(it is not in `functools.__all__`), so the test now uses the import the
documentation actually recommends: `from abc import get_cache_token`.
"""

from abc import ABC, abstractmethod, get_cache_token


class TestGetCacheToken:
    """docs/stdlib/abc.md: `get_cache_token()` -- O(1), "Monotonic token for
    ABC cache invalidation"."""

    def test_token_changes_after_an_abc_registers_a_virtual_subclass(self) -> None:
        class Interface(ABC):
            @abstractmethod
            def do_something(self) -> None: ...

        class Unrelated:
            pass

        before = get_cache_token()
        Interface.register(Unrelated)
        after = get_cache_token()

        assert after != before, "registering a virtual subclass must bump the token"

    def test_token_is_stable_without_a_registration(self) -> None:
        first = get_cache_token()
        second = get_cache_token()
        assert first == second

    def test_the_token_is_monotonic(self) -> None:
        """The page's "monotonic" means it only ever moves in one direction."""

        class InterfaceA(ABC):
            @abstractmethod
            def do_a(self) -> None: ...

        class InterfaceB(ABC):
            @abstractmethod
            def do_b(self) -> None: ...

        class First:
            pass

        class Second:
            pass

        # get_cache_token() is typed as `object` (an opaque, equality-testable
        # token per the docs), but CPython's implementation is an int, which
        # is what makes a monotonicity check meaningful here.
        readings: list[int] = [get_cache_token()]  # type: ignore[list-item]
        InterfaceA.register(First)
        readings.append(get_cache_token())  # type: ignore[arg-type]
        InterfaceB.register(Second)
        readings.append(get_cache_token())  # type: ignore[arg-type]

        assert readings == sorted(readings), "the token never decreases"
        assert len(set(readings)) == 3, "each registration should bump it further"
