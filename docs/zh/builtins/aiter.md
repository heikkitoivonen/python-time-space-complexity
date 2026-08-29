---
source_sha: f1a1cdf5164fe4494e87ed868f67429ccba7e2c329e36cd0b820142d360f510a
translated: machine
---

# aiter() 函数

`aiter()` 函数从异步可迭代对象中返回一个异步迭代器。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| `aiter()` | O(1) | O(1) | 创建迭代器 |
| `__aiter__()` | O(1) | O(1) | 在可迭代对象上调用 |

## 基本用法

### 创建异步迭代器

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

### 从异步可迭代对象获取

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

## 配合 async for 使用

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

## 与 iter() 的比较

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

## 相关函数

- [anext() 函数](anext.md) - 从异步迭代器获取下一个元素
- [iter() 函数](../builtins/iter.md) - 同步迭代器
- [next() 函数](../builtins/next.md) - 获取下一个同步元素
