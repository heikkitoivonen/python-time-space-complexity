# Statistics Module Complexity

The `statistics` module provides functions for calculating basic statistical properties of numeric data.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mean(data)` | O(n) | O(1) | Calculate average |
| `median(data)` | O(n log n) | O(n) | Calculate median; requires sorting |
| `mode(data)` | O(n) | O(n) | Find most common |
| `stdev(data)` | O(n) | O(1) | Standard deviation; two passes |
| `variance(data)` | O(n) | O(1) | Calculate variance; two passes |
| `quantiles(data)` | O(n log n) | O(n) | Calculate quantiles |

## Mean

### mean()

#### Time Complexity: O(n)

Where n = number of data points.

```python
from statistics import mean

# Calculate mean: O(n)
data = [1, 2, 3, 4, 5]
avg = mean(data)  # O(5) = 3.0

# Large dataset: O(n)
large_data = range(1000000)
result = mean(large_data)  # O(1000000)

# Single pass through data
result = mean([10, 20, 30, 40, 50])  # O(5)
```

#### Space Complexity: O(1)

```python
from statistics import mean

result = mean(data)  # O(1) - only stores sum and count
```

## Median

### median()

#### Time Complexity: O(n log n)

```python
from statistics import median

# Calculate median: O(n log n) - requires sorting
data = [5, 2, 8, 1, 9]
mid = median(data)  # O(n log n)

# Sorted data: still O(n log n)
data = [1, 2, 3, 4, 5]
mid = median(data)  # 3 - O(n log n)

# Even/odd length handled automatically
mid = median([1, 2, 3])  # 2 (odd)
mid = median([1, 2, 3, 4])  # 2.5 (even - average)
```

#### Space Complexity: O(n)

```python
from statistics import median

# Sorting requires O(n) space
result = median(large_data)  # O(n) space
```

### median_low() and median_high()

#### Time Complexity: O(n log n)

```python
from statistics import median_low, median_high

data = [1, 2, 3, 4, 5]

# Median low (lower middle): O(n log n)
low = median_low(data)  # 3

# Median high (upper middle): O(n log n)
high = median_high(data)  # 3

# Even-length data
data = [1, 2, 3, 4]
low = median_low(data)   # 2
high = median_high(data)  # 3
```

#### Space Complexity: O(n)

```python
from statistics import median_low

result = median_low(data)  # O(n) space for sorting
```

## Mode

### mode()

#### Time Complexity: O(n)

```python
from statistics import mode

# Find most common: O(n)
data = [1, 1, 1, 2, 2, 3]
most_common = mode(data)  # O(6) = 1

# Multimodal: returns first mode found (Python 3.8+)
data = [1, 1, 2, 2, 3, 3]
m = mode(data)  # Returns 1 (first encountered)

# Python 3.8+: mode() returns first mode if multimodal
# Python 3.7 and earlier: raised StatisticsError for multimodal data
data = [1, 2, 3]  # All equally common
m = mode(data)    # Returns 1 (first encountered)
```

#### Space Complexity: O(n)

```python
from statistics import mode

# Tracks frequencies of all values
result = mode(data)  # O(n) space for frequency table
```

### multimode() - All Modes

#### Time Complexity: O(n)

```python
from statistics import multimode

# Get all modes: O(n)
data = [1, 1, 2, 2, 3]
modes = multimode(data)  # O(5) = [1, 2]

# Single mode returns list
data = [1, 1, 1, 2, 3]
modes = multimode(data)  # O(5) = [1]

# Multiple modes
data = [5, 5, 5, 6, 6, 6]
modes = multimode(data)  # [5, 6]
```

#### Space Complexity: O(n)

```python
from statistics import multimode

modes = multimode(data)  # O(n) for frequency tracking
```

## Variance and Standard Deviation

### variance() and stdev()

#### Time Complexity: O(n)

```python
from statistics import variance, stdev, pvariance, pstdev

data = [1, 2, 3, 4, 5]

# Calculate variance: O(n) - two passes through data
var = variance(data)  # O(5) = 2.5

# Standard deviation: O(n) - two passes (mean then variance)
std = stdev(data)  # O(5) ≈ 1.58

# Sample vs population variance
var_sample = variance(data)        # O(n) - sample (n-1 denominator)
var_pop = pvariance(data)          # O(n) - population (n denominator)

# Sample vs population stdev
std_sample = stdev(data)           # O(n) - sample
std_pop = pstdev(data)             # O(n) - population
```

#### Space Complexity: O(1)

```python
from statistics import variance, stdev

# Two passes through data: O(1) space
var = variance(data)  # O(1) - only stores intermediate values
```

## Quantiles

### quantiles()

#### Time Complexity: O(n log n)

```python
from statistics import quantiles

data = list(range(1, 101))  # 1-100

# Get quartiles: O(n log n) - sorting required
q = quantiles(data, n=4)  # O(n log n) = [25.75, 50.5, 75.25]

# Deciles: O(n log n)
dec = quantiles(data, n=10)  # O(n log n) - 10 quantiles

# Custom quantiles: O(n log n)
q = quantiles(data, n=100)  # O(n log n) - percentiles
```

#### Space Complexity: O(n)

```python
from statistics import quantiles

result = quantiles(data, n=4)  # O(n) space for sorting
```

## Common Patterns

### Analyze Dataset

```python
from statistics import mean, stdev, median

def analyze(data):
    """Comprehensive analysis: O(n log n)"""
    return {
        'mean': mean(data),           # O(n)
        'median': median(data),       # O(n log n)
        'stdev': stdev(data),         # O(n)
        'count': len(data),           # O(1)
        'min': min(data),             # O(n)
        'max': max(data),             # O(n)
    }

stats = analyze([10, 20, 30, 40, 50])  # O(n log n) total
```

### Quality Control

```python
from statistics import mean, stdev

def is_outlier(data, value, stddev_limit=2):
    """Check if value is outlier: O(n)"""
    avg = mean(data)      # O(n)
    std = stdev(data)     # O(n)
    
    return abs(value - avg) > stddev_limit * std  # O(1)

if is_outlier(measurements, 5.5):
    print("Outlier detected")
```

### Data Validation

```python
from statistics import mean, stdev, StatisticsError

def validate_data(data, min_size=3):
    """Validate statistical data: O(n)"""
    if len(data) < min_size:
        raise ValueError(f"Need at least {min_size} values")
    
    try:
        avg = mean(data)     # O(n)
        std = stdev(data)    # O(n)
        return True
    except StatisticsError:
        return False
```

## Performance Characteristics

### Best Practices

```python
from statistics import mean, median, stdev

# Good: Calculate multiple stats in one pass
data = [1, 2, 3, 4, 5]
m = mean(data)      # O(n)
std = stdev(data)   # O(n)
# Total: O(2n)

# Avoid: Sorting multiple times
med = median(data)  # O(n log n) - sorts once
q = quantiles(data) # O(n log n) - sorts again

# Better: Use sorted data
sorted_data = sorted(data)  # O(n log n)
# Then analyze (still O(n) for each stat)
```

### Memory Usage

```python
from statistics import mean, median, stdev

# Good: mean() uses O(1) memory
avg = mean(huge_dataset)  # O(1) memory

# Careful: median() uses O(n) memory (sorts)
med = median(huge_dataset)  # O(n) memory - creates sorted copy

# Good: stdev() uses O(1) memory
std = stdev(huge_dataset)  # O(1) memory
```

## Comparison with NumPy

```python
from statistics import mean
import numpy as np

# statistics module (simple)
data = [1, 2, 3, 4, 5]
avg = mean(data)  # O(n) - Python

# NumPy (powerful)
arr = np.array([1, 2, 3, 4, 5])
avg = np.mean(arr)  # Faster - optimized C code

# Use statistics for small datasets
# Use NumPy for large datasets or advanced operations
```

## Exception Handling

```python
from statistics import mode, median, StatisticsError

# mode() with no mode
try:
    m = mode([1, 2, 3])  # All equally common
except StatisticsError:
    print("No unique mode")

# Empty data
try:
    avg = statistics.mean([])
except StatisticsError:
    print("No data")
```

## Version Notes

- **Python 3.4+**: statistics module introduced
- **Python 3.8+**: quantiles() function added

## Related Documentation

- [Math Module](math.md) - Mathematical functions
- [Random Module](random.md) - Random number generation
