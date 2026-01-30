import sys
import math
import time
import pytest
from pathlib import Path

# Add scripts directory to path to import the estimator module
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.append(str(scripts_dir))

try:
    import estimate_complexity
except ImportError:
    pytest.fail("Could not import estimate_complexity from scripts/")

# Define test functions with known complexities

def constant_time(n):
    """O(1) operation."""
    return 42

def linear_time(n):
    """O(n) operation."""
    # Simple accumulation
    x = 0
    for i in range(n):
        x += 1
    return x

def quadratic_time(n):
    """O(n^2) operation."""
    # We use a smaller constant factor to avoid creating overly long tests
    # n=5000^2 is 25 million ops, might be slow.
    # The estimator uses [100, 500, 1000, 2000, 5000].
    # O(n^2) for 5000 is heavy. 
    # We will rely on the fact that execution time scales quadratically.
    s = 0
    # Reduce iterations for the sake of test speed, but keep complexity structure
    limit = n // 10  
    for i in range(limit):
        for j in range(limit):
            s += 1
    return s

def logarithmic_time(n):
    """O(log n) operation."""
    x = 0
    while n > 1:
        n //= 2
        x += 1
    return x

class TestComplexityEstimator:
    
    def test_detect_constant_time(self):
        """Verify O(1) detection."""
        n_values = [100, 1000, 5000, 10000]
        # Simulate times: roughly constant with noise
        # 1e-6 seconds +/- noise
        times = [1e-6 + (i % 2) * 1e-7 for i in range(len(n_values))]
        
        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(1) (Constant)"
        
    def test_detect_linear_time(self):
        """Verify O(n) detection."""
        n_values = [100, 1000, 5000, 10000]
        # Simulate times: strictly proportional to n
        times = [n * 1e-6 for n in n_values]
        
        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"
        assert score > 0.95

    def test_detect_quadratic_time(self):
        """Verify O(n^2) detection."""
        n_values = [100, 500, 1000, 2000]
        # Simulate times: proportional to n^2
        times = [(n**2) * 1e-9 for n in n_values]
        
        complexity, score = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n^2) (Quadratic)"
        assert score > 0.95

    def test_integration_constant(self):
        """Run full measurement on actual constant function."""
        # Use smaller N for actual execution measurement
        n_values = [10, 50, 100, 200]
        times = []
        for n in n_values:
            t = estimate_complexity.measure_execution_time(constant_time, n, iterations=100)
            times.append(t)
        
        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(1) (Constant)"

    def test_integration_linear(self):
        """Run full measurement on actual linear function."""
        n_values = [1000, 5000, 10000, 20000]
        times = []
        for n in n_values:
            t = estimate_complexity.measure_execution_time(linear_time, n, iterations=10)
            times.append(t)
            
        complexity, _ = estimate_complexity.detect_complexity(n_values, times)
        assert complexity == "O(n) (Linear)"

