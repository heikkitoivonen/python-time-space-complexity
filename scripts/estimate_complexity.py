#!/usr/bin/env python3
"""
Complexity Estimator CLI

This script estimates the time complexity (Big-O) of a Python function by running
it with increasing input sizes and curve-fitting the execution times.

Usage:
    python scripts/estimate_complexity.py <module_path> <function_name>

Example:
    python scripts/estimate_complexity.py my_script my_sorting_function
"""

import sys
import time
import importlib
import math
import statistics
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path.cwd()))


def measure_execution_time(func, input_size, iterations=5):
    """Measure the average execution time of func(input_sized_data)."""
    
    # Generate input data based on expected signature
    # This is a heuristic: we assume func takes a list of ints or an int n
    # Ideally, users could provide a data generator.
    # For now, we try passing 'n' (integer) first, then [range(n)].
    
    try:
        # Try passing integer N
        start_time = time.perf_counter()
        for _ in range(iterations):
            func(input_size)
        end_time = time.perf_counter()
        return (end_time - start_time) / iterations
    except TypeError:
        # Try passing list of size N
        data = list(range(input_size))
        start_time = time.perf_counter()
        for _ in range(iterations):
            func(data)
        end_time = time.perf_counter()
        return (end_time - start_time) / iterations
    except Exception as e:
        print(f"Error executing function: {e}")
        return None

def detect_complexity(n_values, times):
    """
    Estimate complexity by comparing RSquared values for different models.
    Simplified approach: Normalize data and check correlation with theoretical curves.
    """
    if len(times) < 3:
        return "Insufficient Data"

    # Normalize times
    min_time = min(times)
    if min_time == 0: min_time = 1e-9
    normalized_times = [t / min_time for t in times]
    
    models = {
        "O(1) (Constant)": [1 for _ in n_values],
        "O(log n) (Logarithmic)": [math.log(n) if n > 0 else 0 for n in n_values],
        "O(n) (Linear)": [n for n in n_values],
        "O(n log n) (Linearithmic)": [n * math.log(n) if n > 0 else 0 for n in n_values],
        "O(n^2) (Quadratic)": [n**2 for n in n_values],
    }

    best_fit = None
    best_score = -float('inf')

    for name, theoretical in models.items():
        # Calculate correlation coefficient (Pearson)
        try:
            if len(set(theoretical)) == 1: # Handle constant case
                # For constant time, we check variance of times
                score = 1.0 / (statistics.stdev(normalized_times) + 1.0) 
            else:
                 # Correlation between theoretical and actual
                 # Using covariance / (std_dev_x * std_dev_y)
                 correlation = statistics.correlation(theoretical, times)
                 score = correlation
            
            if score > best_score:
                best_score = score
                best_fit = name
        except statistics.StatisticsError:
            continue
            
    return best_fit, best_score

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    module_name = sys.argv[1]
    func_name = sys.argv[2]

    try:
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
    except (ImportError, AttributeError) as e:
        print(f"Error importing {module_name}.{func_name}: {e}")
        sys.exit(1)

    print(f"Estimating complexity for {module_name}.{func_name}...")
    
    # Input sizes to test
    n_values = [100, 500, 1000, 2000, 5000]
    times = []

    print(f"{'Input Size (n)':<15} | {'Avg Time (s)':<15}")
    print("-" * 35)

    for n in n_values:
        t = measure_execution_time(func, n)
        if t is None:
            print("Failed to execute function. ensure it accepts an int or list[int].")
            break
        times.append(t)
        print(f"{n:<15} | {t:.6f}")

    if len(times) == len(n_values):
        complexity, score = detect_complexity(n_values, times)
        print("-" * 35)
        print(f"Estimated Complexity: {complexity}")
        print(f"Fit Score: {score:.3f}")
    
if __name__ == "__main__":
    main()
