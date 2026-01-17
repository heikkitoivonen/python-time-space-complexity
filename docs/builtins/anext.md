# anext() Function

The `anext()` function returns the next item from an asynchronous iterator.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `anext()` | O(n) | O(n) | n = time to compute next item |
| With default | O(n) | O(n) | Returns default if exhausted |

## Basic Usage

### Get Next Async Item

```python
import asyncio

async def async_generator():
    for i in range(3):
        yield i

async def main():
    async_iter = aiter(async_generator())
    
    # Get next item - O(n)
    value = await anext(async_iter)
    print(value)  # 0
    
    value = await anext(async_iter)
    print(value)  # 1

asyncio.run(main())
```

### With Default Value

```python
import asyncio

async def async_generator():
    yield 1
    yield 2
    # Iterator exhausted after

async def main():
    async_iter = aiter(async_generator())
    
    print(await anext(async_iter))  # 1
    print(await anext(async_iter))  # 2
    
    # Default when exhausted - O(n)
    value = await anext(async_iter, "END")
    print(value)  # "END"

asyncio.run(main())
```

### Without Default (Raises Exception)

```python
import asyncio

async def async_generator():
    yield 1

async def main():
    async_iter = aiter(async_generator())
    
    print(await anext(async_iter))  # 1
    
    try:
        # No default - raises StopAsyncIteration - O(n)
        print(await anext(async_iter))
    except StopAsyncIteration:
        print("Iterator exhausted")

asyncio.run(main())
```

## Practical Example

```python
import asyncio

async def fetch_items(items):
    for item in items:
        await asyncio.sleep(0.1)  # Simulate async work
        yield item

async def main():
    # Create async iterator - O(1)
    iterator = aiter(fetch_items(["a", "b", "c"]))
    
    # Get items manually - O(n) each
    first = await anext(iterator)
    print(f"First: {first}")  # First: a
    
    second = await anext(iterator, None)
    print(f"Second: {second}")  # Second: b
    
    # Get remaining with loop
    async for item in iterator:
        print(f"Item: {item}")  # Item: c

asyncio.run(main())
```

## Comparison with next()

```python
import asyncio

# next() - synchronous - O(1)
def sync_gen():
    yield 1
    yield 2

sync_iter = iter(sync_gen())
print(next(sync_iter))  # Synchronous

# anext() - asynchronous - O(n)
async def async_gen():
    yield 1
    yield 2

async def main():
    async_iter = aiter(async_gen())
    print(await anext(async_iter))  # Must await

asyncio.run(main())
```

## Related Functions

- [aiter() Function](aiter.md) - Create async iterator
- [next() Function](../builtins/next.md) - Synchronous next
- [iter() Function](../builtins/iter.md) - Create synchronous iterator
