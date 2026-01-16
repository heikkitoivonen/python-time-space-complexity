# unittest Module Complexity

The `unittest` module provides a framework for unit testing with test cases, fixtures, and test runners.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase()` | O(1) | O(1) | Create test case |
| `setUp()`/`tearDown()` | O(s) | O(1) | s = setup time |
| Assertion | O(1) | O(1) | Check condition |
| Run test suite | O(n*t) | O(n) | n = tests, t = per-test |

## Basic Test Case

```python
import unittest

# Define test class - O(1)
class TestCalculator(unittest.TestCase):
    
    def setUp(self):  # O(s) - called before each test
        self.calc = Calculator()
    
    def tearDown(self):  # O(1) - called after each test
        pass
    
    def test_add(self):  # O(1)
        result = self.calc.add(2, 3)
        self.assertEqual(result, 5)  # Assert
    
    def test_subtract(self):  # O(1)
        result = self.calc.subtract(5, 3)
        self.assertEqual(result, 2)

# Run tests - O(n*t)
if __name__ == '__main__':
    unittest.main()  # O(n*t) - run all
```

## Assertions

```python
import unittest

class TestAssertions(unittest.TestCase):
    
    def test_equality(self):
        self.assertEqual(1, 1)           # O(1)
        self.assertNotEqual(1, 2)        # O(1)
    
    def test_truth(self):
        self.assertTrue(True)            # O(1)
        self.assertFalse(False)          # O(1)
    
    def test_membership(self):
        self.assertIn(1, [1, 2, 3])      # O(n)
        self.assertNotIn(4, [1, 2, 3])   # O(n)
    
    def test_types(self):
        self.assertIsInstance('text', str)  # O(1)
        self.assertIsNone(None)             # O(1)
    
    def test_exceptions(self):
        with self.assertRaises(ValueError):
            int('abc')  # O(1) - verify exception
```

## Test Fixtures

```python
import unittest

class TestWithFixtures(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):  # O(1) - once per class
        cls.shared_resource = create_resource()
    
    @classmethod
    def tearDownClass(cls):  # O(1) - once at end
        cls.shared_resource.cleanup()
    
    def setUp(self):  # O(s) - before each test
        self.data = []
    
    def test_append(self):
        self.data.append(1)
        self.assertEqual(len(self.data), 1)
```

## Test Suite

```python
import unittest

# Load tests - O(n)
loader = unittest.TestLoader()
suite = loader.loadTestsFromTestCase(TestCalculator)  # O(n)

# Run suite - O(n*t)
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)  # O(n*t)

# Check results - O(1)
if result.wasSuccessful():
    print("All passed")
```

## Mocking

```python
import unittest
from unittest.mock import Mock, patch

class TestWithMocks(unittest.TestCase):
    
    def test_with_mock(self):
        # Create mock - O(1)
        mock_obj = Mock()
        mock_obj.method.return_value = 42
        
        # Use mock - O(1)
        result = mock_obj.method()
        self.assertEqual(result, 42)
    
    @patch('module.function')
    def test_with_patch(self, mock_func):  # O(1)
        mock_func.return_value = 'mocked'
        result = call_function()
        self.assertEqual(result, 'mocked')
```

## Running Tests

```bash
# Run all tests in file
python -m unittest test_module.py  # O(n*t)

# Run specific test
python -m unittest test_module.TestClass.test_method  # O(1)

# Discover and run all tests
python -m unittest discover  # O(n*t)

# Verbose output
python -m unittest -v  # O(n*t)
```

## Version Notes

- **Python 2.x**: unittest available (as unittest2 backport)
- **Python 3.x**: Built-in with enhancements
- **Python 3.4+**: Subtests added

## Best Practices

✅ **Do**:
- Write independent tests
- Use setUp/tearDown
- Name tests clearly
- Test one thing per test
- Use mocks for dependencies

❌ **Avoid**:
- Test interdependencies
- Testing implementation details
- Huge test methods
- Ignoring test failures
