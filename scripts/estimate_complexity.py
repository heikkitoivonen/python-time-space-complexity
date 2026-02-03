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

import importlib
import inspect
import math
import statistics
import sys
import time
import typing
from pathlib import Path

# Add current directory to path so we can import local modules
sys.path.insert(0, str(Path.cwd()))


def measure_execution_time(func, input_size, iterations=5):
    """
    Measure the average execution time of func(input_sized_data).
    Uses type hints to determine whether to pass 'n' (int) or data of size 'n'.
    """
    input_data = None

    # 1. Check type hints
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if params:
            first_param = params[0]
            hint = first_param.annotation

            if hint is int:
                input_data = input_size
            elif hint in (list, typing.Sequence):
                # Simple list generation
                input_data = list(range(input_size))
            # Handle generic aliases like list[int] in newer Python
            elif hasattr(hint, "__origin__") and hint.__origin__ in (list, typing.Sequence):
                input_data = list(range(input_size))
    except (ValueError, TypeError):
        # Signature inspection failed or function is weird
        pass

    # 2. Heuristic fallback logic
    if input_data is None:
        return _measure_heuristic(func, input_size, iterations)

    # 3. Execution with determined input
    try:
        # Warm up once to reduce cold-start noise
        func(input_data)
        start_time = time.perf_counter()
        for _ in range(iterations):
            func(input_data)
        end_time = time.perf_counter()
        return (end_time - start_time) / iterations
    except Exception:
        # If specific input failed, maybe try heuristic as last resort?
        # But for now, just report error to avoid infinite fallback loops.
        # print(f"Error with generated input: {e}")
        return None


def _measure_heuristic(func, input_size, iterations):
    """Fallback: Try int first, then list."""
    try:
        # Warm up once to reduce cold-start noise
        func(input_size)
        # Try passing integer N
        start_time = time.perf_counter()
        for _ in range(iterations):
            func(input_size)
        end_time = time.perf_counter()
        return (end_time - start_time) / iterations
    except TypeError:
        # Try passing list of size N
        data = list(range(input_size))
        # Warm up once to reduce cold-start noise
        func(data)
        start_time = time.perf_counter()
        for _ in range(iterations):
            func(data)
        end_time = time.perf_counter()
        return (end_time - start_time) / iterations
    except Exception:
        return None


def _compute_residuals(normalized_times, theoretical):
    """
    Compute residuals using least-squares linear regression with intercept.

    For constant models (all values equal), uses mean as fit.
    For other models, fits t = a * f(n) + b and requires positive slope.

    Returns:
        list of residuals, or None if model is not applicable.
    """
    if len(set(theoretical)) == 1:
        # Constant model: best fit is mean of normalized times
        mean_time = statistics.fmean(normalized_times)
        return [t - mean_time for t in normalized_times]

    # Linear regression with intercept: t = a * f(n) + b
    n = len(theoretical)
    sum_x = sum(theoretical)
    sum_y = sum(normalized_times)
    sum_xx = sum(x * x for x in theoretical)
    sum_xy = sum(x * y for x, y in zip(theoretical, normalized_times))

    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return None

    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n

    # Require positive slope; negative/zero means model doesn't explain growth
    if a <= 1e-12:
        return None

    return [t - (a * x + b) for t, x in zip(normalized_times, theoretical)]


def _tie_break_linear_vs_nlogn(n_values, times, scores):
    linear_rmse = scores.get("O(n) (Linear)")
    nlogn_rmse = scores.get("O(n log n) (Linearithmic)")
    if linear_rmse is None or nlogn_rmse is None:
        return None, None

    relative_eps = 0.05
    threshold = relative_eps * min(linear_rmse, nlogn_rmse)
    if abs(linear_rmse - nlogn_rmse) > threshold:
        return None, None

    # Filter pairs together to maintain alignment (use n > 1 to avoid log(1)=0)
    pairs = [(n, t) for n, t in zip(n_values, times) if n > 1 and t > 0]
    if len(pairs) < 2:
        return None, None

    log_n = [math.log(n) for n, _ in pairs]
    log_t = [math.log(t) for _, t in pairs]

    mean_ln = statistics.fmean(log_n)
    mean_lt = statistics.fmean(log_t)
    var_ln = sum((x - mean_ln) ** 2 for x in log_n)
    if var_ln == 0:
        return None, None

    cov = sum((x - mean_ln) * (y - mean_lt) for x, y in zip(log_n, log_t))
    slope = cov / var_ln
    n_mid = math.exp(mean_ln)
    ln_mid = math.log(n_mid)

    # Guard against division by zero when n_mid is near 1
    if abs(ln_mid) < 1e-6:
        return None, None

    target_nlogn = 1.0 + (1.0 / ln_mid)

    if abs(slope - 1.0) <= abs(slope - target_nlogn):
        return "O(n) (Linear)", linear_rmse
    return "O(n log n) (Linearithmic)", nlogn_rmse


def _score_models(normalized_times, models, model_priority):
    best_fit = None
    best_score = float("inf")
    scores = {}

    for name, theoretical in models:
        try:
            residuals = _compute_residuals(normalized_times, theoretical)
            if residuals is None:
                continue

            rmse = math.sqrt(statistics.fmean(r * r for r in residuals))
            scores[name] = rmse

            # Use 5% relative epsilon for tie-breaking to handle timing noise
            # and prefer simpler models when fits are comparable
            relative_eps = 0.05
            threshold = relative_eps * best_score if best_score > 0 else 1e-9

            if rmse < best_score - threshold:
                best_score = rmse
                best_fit = name
                continue

            if abs(rmse - best_score) <= threshold:
                current_priority = model_priority[best_fit] if best_fit else 999
                if model_priority[name] < current_priority:
                    best_fit = name
                    best_score = rmse
        except statistics.StatisticsError:
            continue

    return best_fit, best_score, scores


def detect_complexity(n_values, times):
    """
    Estimate complexity by fitting theoretical curves to measured times.

    Uses least-squares linear regression (with intercept) to fit each model
    curve to the timing data, then selects the model with lowest RMSE.
    Prefers simpler models when RMSE values are within 5% of each other.

    Returns:
        tuple: (complexity_name, rmse) or (None, None) if insufficient data.
    """
    if len(times) < 3:
        return (None, None)

    # Normalize times to reduce numerical effects across models
    min_time = min(times)
    if min_time <= 0:
        min_time = 1e-9
    normalized_times = [t / min_time for t in times]

    models = [
        ("O(1) (Constant)", [1 for _ in n_values]),
        ("O(log n) (Logarithmic)", [math.log(n) if n > 0 else 0 for n in n_values]),
        ("O(n) (Linear)", list(n_values)),
        ("O(n log n) (Linearithmic)", [n * math.log(n) if n > 0 else 0 for n in n_values]),
        ("O(n^2) (Quadratic)", [n**2 for n in n_values]),
    ]

    # Prefer simpler models when scores are effectively tied.
    model_priority = {
        "O(1) (Constant)": 0,
        "O(log n) (Logarithmic)": 1,
        "O(n) (Linear)": 2,
        "O(n log n) (Linearithmic)": 3,
        "O(n^2) (Quadratic)": 4,
    }

    best_fit, best_score, scores = _score_models(
        normalized_times,
        models,
        model_priority,
    )

    if best_fit in ("O(n) (Linear)", "O(n log n) (Linearithmic)"):
        tie_fit, tie_score = _tie_break_linear_vs_nlogn(n_values, times, scores)
        if tie_fit is not None:
            best_fit = tie_fit
            best_score = tie_score

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
        complexity, rmse = detect_complexity(n_values, times)
        print("-" * 35)
        if complexity is None:
            print("Insufficient data to estimate complexity.")
        else:
            print(f"Estimated Complexity: {complexity}")
            print(f"RMSE: {rmse:.3f}")


if __name__ == "__main__":
    main()
