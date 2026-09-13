---
source_sha: 5887991529740bb5adcce25dab9f9ae4d8131508c4c2034aa2cec0283c2507ae
translated: machine
---

# anext() 函数

`anext()` 函数从异步迭代器中返回下一个元素。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| `anext()` 调用 | O(1) | O(1) | 外加一次 `__anext__()` 调用本身；对于 `async def` 或异步生成器，它只会构建可等待对象 |
| 等待结果 | O(k) | O(1) | k = 一次 `__anext__()` 步骤的工作量，包括其中的 await；空间不含该步骤自身的分配 |
| 带默认值 | O(k) | O(1) | 迭代耗尽时返回默认值；每次挂起额外 O(1) |

<!-- 注意：复杂度取决于异步生成器内部执行的操作，而不是 anext() 本身 -->

!!! warning "手写的可等待对象与默认值"
    传入默认值时，`anext()` 会包装 `__anext__()` 返回的可等待对象，并在这次 await 的每一步都调用它的 `__await__()`，而不是只调用一次。`async def __anext__()` 或异步生成器会从上次停下的地方继续并正常完成。而 `__await__()` 是生成器函数的类每次调用都会从头开始；如果每次调用都挂起，这个 await 就永远不会完成。对于这样的迭代器，请不要传入默认值，而是自行捕获 `StopAsyncIteration`。

## 基本用法

### 获取下一个异步元素

```python
import asyncio

async def async_generator():
    for i in range(3):
        yield i

async def main():
    async_iter = aiter(async_generator())
    
    # Get next item - O(k) where k = async iterator work for this step
    value = await anext(async_iter)
    print(value)  # 0
    
    value = await anext(async_iter)
    print(value)  # 1

asyncio.run(main())
```

### 使用默认值

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
    
    # Default when exhausted - O(1) once iterator is exhausted
    value = await anext(async_iter, "END")
    print(value)  # "END"

asyncio.run(main())
```

### 不带默认值（抛出异常）

```python
import asyncio

async def async_generator():
    yield 1

async def main():
    async_iter = aiter(async_generator())
    
    print(await anext(async_iter))  # 1
    
    try:
        # No default - raises StopAsyncIteration when exhausted (O(1) at exhaustion)
        print(await anext(async_iter))
    except StopAsyncIteration:
        print("Iterator exhausted")

asyncio.run(main())
```

## 实际示例

```python
import asyncio

async def fetch_items(items):
    for item in items:
        await asyncio.sleep(0.1)  # Simulate async work
        yield item

async def main():
    # Create async iterator - O(1)
    iterator = aiter(fetch_items(["a", "b", "c"]))
    
    # Get items manually - O(k) each where k depends on iterator body
    first = await anext(iterator)
    print(f"First: {first}")  # First: a
    
    second = await anext(iterator, None)
    print(f"Second: {second}")  # Second: b
    
    # Get remaining with loop
    async for item in iterator:
        print(f"Item: {item}")  # Item: c

asyncio.run(main())
```

## 与 next() 的比较

```python
import asyncio

# next() - synchronous - O(1) call, the generator's step runs inside it
def sync_gen():
    yield 1
    yield 2

sync_iter = iter(sync_gen())
print(next(sync_iter))  # Synchronous

# anext() - asynchronous - O(1) call, awaiting depends on generator
async def async_gen():
    yield 1
    yield 2

async def main():
    async_iter = aiter(async_gen())
    print(await anext(async_iter))  # Must await

asyncio.run(main())
```

## 相关函数

- [aiter() 函数](aiter.md) - 创建异步迭代器
- [next() 函数](../builtins/next.md) - 同步的 next
- [iter() 函数](../builtins/iter.md) - 创建同步迭代器
