import sys
import math
import time
import pytest
from typing import List
from unittest.mock import MagicMock
from pathlib import Path

# Add scripts directory to path to import the estimator module
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.append(str(scripts_dir))

try:
    import estimate_complexity
except ImportError:
    pytest.fail("Could not import estimate_complexity from scripts/")

# Define test functions with type hints

def constant_time(n: int):
    """O(1) operation taking an int."""
    return 42

def linear_time_list(data: List[int]):
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
        times = [1e-6 + (i % 2) * 1e-7 for i in range(len(n_values))]
        
        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(1) (Constant)"
        
    def test_detect_linear_time(self):
        """Verify O(n) detection (pure logic)."""
        n_values = [100, 1000, 5000, 10000]
        times = [n * 1e-6 for n in n_values]
        
        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"

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
        def hinted(data: List[int]):
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
        """Run measurement on linear function (List[int] hint)."""
        # Increase data points and iterations for stability
        n_values = [1000, 2500, 5000, 7500, 10000]
        times = []
        for n in n_values:
            t = estimate_complexity.measure_execution_time(linear_time_list, n, iterations=500)
            times.append(t)
            
        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"


