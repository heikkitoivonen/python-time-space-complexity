# aiter() Function

The `aiter()` function returns an asynchronous iterator from an asynchronous iterable.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `aiter()` | O(1) | O(1) | Create iterator |
| `__aiter__()` | O(1) | O(1) | Call on iterable |

## Basic Usage

### Create Async Iterator

```python
import asyncio

async def async_generator():
    for i in range(3):
        yield i

async def main():
    # Create async iterator - O(1)
    async_iter = aiter(async_generator())
    
    # Iterate
    value = await async_iter.__anext__()
    print(value)  # 0

asyncio.run(main())
```

### From Async Iterable

```python
import asyncio

class AsyncIterable:
    def __aiter__(self):
        return AsyncIterator()

class AsyncIterator:
    def __init__(self):
        self.count = 0
    
    async def __anext__(self):
        if self.count >= 3:
            raise StopAsyncIteration
        self.count += 1
        return self.count

async def main():
    # Get iterator from iterable - O(1)
    iterator = aiter(AsyncIterable())
    
    # Use with async for
    async for value in iterator:
        print(value)  # 1, 2, 3

asyncio.run(main())
```

## With Async For

```python
import asyncio

async def fetch_data(urls):
    """Simulate async data fetching."""
    for url in urls:
        await asyncio.sleep(0.1)
        yield f"Data from {url}"

async def main():
    urls = ["url1", "url2", "url3"]
    
    # aiter is implicit in async for
    async for data in fetch_data(urls):
        print(data)

asyncio.run(main())
```

## Comparison with iter()

```python
import asyncio

# iter() - synchronous iterator - O(1)
def sync_generator():
    yield 1
    yield 2

sync_iter = iter(sync_generator())
print(next(sync_iter))  # Works synchronously

# aiter() - asynchronous iterator - O(1)
async def async_generator():
    yield 1
    yield 2

async def main():
    async_iter = aiter(async_generator())
    print(await async_iter.__anext__())  # Must be awaited

asyncio.run(main())
```

## Related Functions

- [anext() Function](anext.md) - Get next item from async iterator
- [iter() Function](../builtins/iter.md) - Synchronous iterator
- [next() Function](../builtins/next.md) - Get next synchronous item
