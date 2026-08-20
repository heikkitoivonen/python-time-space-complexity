import math
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add scripts directory to path to import the estimator module
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.append(str(scripts_dir))

try:
    import estimate_complexity  # type: ignore[reportMissingImports]
except ImportError:
    pytest.fail("Could not import estimate_complexity from scripts/")

# Define test functions with type hints


def constant_time(n: int):
    """O(1) operation taking an int."""
    return 42


def linear_time_list(data: list[int]):
    """O(n) operation taking a list."""
    x = 0
    for _ in data:
        x += 1
    return x


def heuristic_func(n):
    """No type hint, relies on heuristic (int)."""
    return n * n


class TestComplexityEstimator:
    def test_detect_constant_time(self):
        """Verify O(1) detection (pure logic)."""
        n_values = [100, 1000, 5000, 10000]
        # Simulate constant time with small random noise (not correlated with n)
        times = [1e-6, 1.02e-6, 0.98e-6, 1.01e-6]

        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(1) (Constant)"

    def test_detect_linear_time(self):
        """Verify O(n) detection (pure logic)."""
        n_values = [100, 1000, 5000, 10000]
        times = [n * 1e-6 for n in n_values]

        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"

    def test_detect_nlogn_time(self):
        """Verify O(n log n) detection (pure logic).

        On clean synthetic data RMSE alone happens to pick correctly, so this
        passes with or without the log-log slope tie-break. It is here to pin
        the expected verdict; the tie-break is what keeps the same verdict
        stable once real timing noise is involved.
        """
        n_values = [1000, 2000, 4000, 8000, 16000]
        times = [n * math.log(n) * 1e-9 for n in n_values]

        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n log n) (Linearithmic)"

    def test_linear_not_misread_as_nlogn(self):
        """Exactly linear data must not be reported as O(n log n)."""
        n_values = [1000, 2000, 4000, 8000, 16000]
        times = [n * 1e-9 for n in n_values]

        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"

    def test_tie_break_runs_when_rmse_gap_is_large(self):
        """The linear-vs-nlogn tie-break must not be gated on close RMSE values.

        It used to bail out unless the two RMSE scores were within 5% of each
        other. In practice the gap is 100-800%, so it never ran and noise
        picked the winner.
        """
        n_values = [1000, 2000, 4000, 8000, 16000]
        times = [n * math.log(n) * 1e-9 for n in n_values]
        # Deliberately far-apart scores: the tie-break must still decide.
        scores = {"O(n) (Linear)": 1.0, "O(n log n) (Linearithmic)": 100.0}

        pick, _ = estimate_complexity._tie_break_linear_vs_nlogn(n_values, times, scores)
        assert pick == "O(n log n) (Linearithmic)"

    def test_detect_quadratic_time(self):
        """Verify O(n^2) detection (pure logic)."""
        n_values = [100, 500, 1000, 2000]
        times = [(n**2) * 1e-9 for n in n_values]

        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n^2) (Quadratic)"

    def test_type_hint_int(self):
        """Verify that int type hint generates int input."""
        mock_func = MagicMock()

        # Add annotation to the mock (a bit tricky dynamically, so we use a wrapper)
        def hinted(n: int):
            mock_func(n)

        estimate_complexity.measure_execution_time(hinted, 100, iterations=1)
        mock_func.assert_called_with(100)

    def test_type_hint_list(self):
        """Verify that List[int] type hint generates list input."""
        mock_func = MagicMock()

        def hinted(data: list[int]):
            mock_func(data)

        estimate_complexity.measure_execution_time(hinted, 10, iterations=1)
        # Check argument was a list of length 10
        args, _ = mock_func.call_args
        assert isinstance(args[0], list)
        assert len(args[0]) == 10

    def test_integration_constant(self):
        """Run measurement on constant function (int hint)."""
        n_values = [10, 50, 100]
        times = []
        for n in n_values:
            t = estimate_complexity.measure_execution_time(constant_time, n, iterations=20)
            times.append(t)

        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        # Constant time is hard to fail unless system is super noisy
        assert complexity == "O(1) (Constant)"

    def test_integration_linear_list(self):
        """Run measurement on linear function (List[int] hint).

        The n values must span a wide range. Separating O(n) from O(n log n)
        means resolving the empirical exponent finely enough to see the log
        factor, and log grows so slowly that a narrow range leaves no signal:
        over 1000..16000 the decision boundary sits at an exponent of 1.06 and
        measured slopes scatter across 0.91-1.11, so the verdict is decided by
        noise. Over 1000..256000 the same slopes land in 1.00-1.04 and the
        verdict is stable. Widening the range matters far more than the number
        of iterations, so this needs fewer of them than the narrow version did.
        """
        n_values = [1000, 4000, 16000, 64000, 256000]
        times = []
        for n in n_values:
            t = estimate_complexity.measure_execution_time(linear_time_list, n, iterations=50)
            times.append(t)

        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"
