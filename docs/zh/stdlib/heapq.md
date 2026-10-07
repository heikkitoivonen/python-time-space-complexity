---
source_sha: bc027a0b06cdd8740a2521704ec5280e0839aa5d5e037704f37c0fb6913b975e
translated: machine
---

# heapq 模块的复杂度

`heapq` 模块把二叉堆保存在普通的 `list` 中：没有堆类型，只有一组函数在你自己拥有的列表里移动元素，
使 `heap[0]` 始终是最小的元素。每个操作都是原地进行的，只有 `nlargest`、`nsmallest` 和 `merge`
会保存属于自己的数据。

`n` 是堆中的元素数，`m` 是从输入可迭代对象中取出的元素数，`k` 是要求 `nlargest` 或 `nsmallest`
返回的元素数，`r` 是传给 `merge` 的可迭代对象个数。每个界都以元素之间的比较次数计，并把一次比较和
一次 `key` 函数调用视为 O(1)。

## 复杂度参考

### 最小堆函数

| 操作 | 时间 | 空间 | 备注 |
|------|------|------|------|
| `heapq.heapify(x)` | O(n) | O(1) | 原地进行 |
| `heapq.heappush(heap, item)` | 均摊 O(log n) | 均摊 O(1) | 列表的增长方式与 `append` 相同 |
| `heapq.heappop(heap)` | 均摊 O(log n) | O(1) | 列表的缩容方式与 `pop` 相同；堆为空时抛出 `IndexError` |
| `heapq.heappushpop(heap, item)` | O(log n) | O(1) | 堆为空或 `item` 不大于 `heap[0]` 时为 O(1)，堆保持不变 |
| `heapq.heapreplace(heap, item)` | O(log n) | O(1) | 先弹出再压入，因此可能返回比 `item` 更大的元素；堆为空时抛出 `IndexError` |
| 读取 `heap[0]` | O(1) | O(1) | 得到最小元素而不移除它 |

### 最大堆函数

| 操作 | 时间 | 空间 | 备注 |
|------|------|------|------|
| `heapq.heapify_max(x)` | O(n) | O(1) | Python 3.14+；之后 `heap[0]` 是最大元素 |
| `heapq.heappush_max(heap, item)` | 均摊 O(log n) | 均摊 O(1) | Python 3.14+ |
| `heapq.heappop_max(heap)` | 均摊 O(log n) | O(1) | Python 3.14+；堆为空时抛出 `IndexError` |
| `heapq.heappushpop_max(heap, item)` | O(log n) | O(1) | Python 3.14+；堆为空或 `item` 不小于 `heap[0]` 时为 O(1)，堆保持不变 |
| `heapq.heapreplace_max(heap, item)` | O(log n) | O(1) | Python 3.14+；堆为空时抛出 `IndexError` |

### 选择与合并

| 操作 | 时间 | 空间 | 备注 |
|------|------|------|------|
| `heapq.nlargest(k, iterable, key=None)` | O(m log k) | O(k) | 无法进入结果的元素只需一次比较，因此 k 较小时随机输入的开销接近 O(m)；升序输入会让每个元素都进入结果。k = 1 是一次 `max()` 遍历，O(m)。`key` 对每个元素调用一次 |
| `heapq.nsmallest(k, iterable, key=None)` | O(m log k) | O(k) | 镜像情况：降序输入是最坏情况，k = 1 是一次 `min()` 遍历 |
| `heapq.merge(*iterables, key=None, reverse=False)` | O(r + m log r) | O(r) | 惰性：每个输入只保留一个元素。每个输入都必须已按输出方向排好序，这一点不会被检查。`key` 对每个元素最多调用一次 |

## 堆的布局

堆是这样一个列表：位置 `i` 上的元素不大于位置 `2*i + 1` 和 `2*i + 2` 上的两个元素。`heapify`
以 O(n) 建立的仅此而已：列表并没有排序，只能确定 `heap[0]` 是最小的。

```python
import heapq

data = [5, 3, 7, 1, 9, 4]
heapq.heapify(data)  # O(n), in place

assert data[0] == 1          # O(1) - the root is the smallest
assert data != sorted(data)  # a heap, not a sorted list
for parent in range(len(data)):
    for child in (2 * parent + 1, 2 * parent + 2):
        if child < len(data):
            assert data[parent] <= data[child]
```

## 压入与弹出

一次压入或弹出沿根与叶之间的一条路径进行，因此开销是堆的高度，即 O(log n)。所以把整个堆弹空是
O(n log n)。

```python
import heapq

heap = []
for priority in [5, 1, 4, 2, 3]:
    heapq.heappush(heap, priority)  # O(log n) amortized

assert heap[0] == 1  # O(1) peek
drained = [heapq.heappop(heap) for _ in range(len(heap))]  # O(n log n) in total
assert drained == [1, 2, 3, 4, 5]

try:
    heapq.heappop(heap)
except IndexError as error:
    assert 'index out of range' in str(error)
else:
    raise AssertionError('popped from an empty heap')
```

### 优先级相同与不可比较的负载

元组逐个字段比较，所以优先级相同的两个条目会继续比较下一个字段。在那里放一个唯一的计数器，负载就
永远不会被比较：优先级相同的条目按插入顺序出队，不支持 `<` 的负载也永远不会被要求比较。

```python
import heapq
import itertools

class Job:
    def __init__(self, name):
        self.name = name

heap = []
try:
    heapq.heappush(heap, (1, Job('a')))
    heapq.heappush(heap, (1, Job('b')))  # equal priority reaches Job < Job
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('two Jobs were compared')

counter = itertools.count()
heap = []
for name in ['a', 'b', 'c']:
    heapq.heappush(heap, (1, next(counter), Job(name)))  # O(log n)

assert [heapq.heappop(heap)[2].name for _ in range(3)] == ['a', 'b', 'c']
```

## 压入与弹出的组合

`heappushpop` 和 `heapreplace` 在一次调用中完成一次压入和一次弹出，堆的大小保持不变。它们的区别
在于顺序：`heappushpop` 先压入，所以不大于根的元素在一次比较后就被直接返回；`heapreplace` 先弹出，
所以它总是返回旧的根，即使旧根比新元素更大。

```python
import heapq

heap = [2, 4, 6]
heapq.heapify(heap)

assert heapq.heappushpop(heap, 1) == 1  # O(1) here - 1 never enters the heap
assert heap == [2, 4, 6]

assert heapq.heapreplace(heap, 1) == 2  # O(log n) - pops 2, then pushes 1
assert sorted(heap) == [1, 4, 6]

assert heapq.heappushpop([], 7) == 7  # an empty heap returns the item
```

## 选出前 k 个

当 k 大于 1 时，`nlargest` 在堆中保存目前见到的最好的 k 个元素，并把每个新元素与其中最弱的那个
比较。进不去的元素只花这一次比较，所以在 k 较小的随机输入上堆很少被改动；能进去的元素花费
O(log k)。已经按升序排列的输入是 `nlargest` 的最坏情况，因为每个元素都胜过之前的所有元素；降序输入
则是 `nsmallest` 的最坏情况。无论哪种情况，它都是只保存 k 个元素的一次遍历，而 `sorted()` 要保存
全部 m 个元素。

```python
import heapq

scores = [31, 7, 88, 54, 12, 99, 63, 5]

assert heapq.nlargest(3, scores) == [99, 88, 63]  # O(m log k), O(k) memory
assert heapq.nsmallest(2, scores) == [5, 7]       # O(m log k)
assert heapq.nlargest(3, scores) == sorted(scores, reverse=True)[:3]  # same answer, O(m log m)

# key is called once per item, and the items themselves are returned
words = ['pear', 'fig', 'banana', 'kiwi']
assert heapq.nlargest(2, words, key=len) == ['banana', 'pear']

# The input can be any iterable, consumed in one pass
assert heapq.nsmallest(2, (x * x for x in range(-3, 4))) == [0, 1]
```

## 合并已排序的输入

`merge` 是一个生成器。第一次 `next()` 从每个输入各取一个元素并把它们堆化，开销 O(r)；此后每产出
一个元素，最多花一次 O(log r) 的筛选来取入该输入的下一个元素。除了每个输入的那一个元素之外不会
预读，因此它可以合并内存放不下的输入，但它信任给定的顺序：未排序的输入会产生未排序的输出，且不会
报错。

```python
import heapq

merged = heapq.merge([1, 4, 7], [2, 5, 8], [3, 6, 9])  # O(1) - nothing is read yet
assert next(merged) == 1                               # O(r) - one item from each input
assert list(merged) == [2, 3, 4, 5, 6, 7, 8, 9]        # O(log r) per item

# key and reverse: each input must already be sorted that way
by_length = heapq.merge(['fig', 'pear'], ['kiwi', 'banana'], key=len)
assert list(by_length) == ['fig', 'pear', 'kiwi', 'banana']
descending = heapq.merge([9, 5, 1], [8, 2], reverse=True)
assert list(descending) == [9, 8, 5, 2, 1]

# Unsorted input is not detected
assert list(heapq.merge([3, 1], [2])) == [2, 3, 1]
```

## 最大堆

### 最大堆函数

Python 3.14 为五个堆函数各增加了一个 `_max` 版本。它们的开销与最小堆函数相同，只是 `heap[0]`
是最大元素而不是最小元素。

```python
import heapq

data = [3, 1, 4, 1, 5, 9, 2, 6]
heapq.heapify_max(data)  # O(n)
assert data[0] == 9      # O(1) - the root is the largest

heapq.heappush_max(data, 10)          # O(log n) amortized
assert heapq.heappop_max(data) == 10  # O(log n) amortized

assert heapq.heapreplace_max(data, 7) == 9   # O(log n) - pops 9, then pushes 7
assert heapq.heappushpop_max(data, 8) == 8   # O(1) here - 8 is not smaller than the root
assert data[0] == 7
```

### Python 3.14 之前

对数值优先级取负，就能以相同的开销把最小堆函数当作最大堆使用。

```python
import heapq

data = [3, 1, 4, 1, 5]
max_heap = [-x for x in data]  # O(n)
heapq.heapify(max_heap)        # O(n)

assert -max_heap[0] == 5               # O(1) peek
assert -heapq.heappop(max_heap) == 5   # O(log n)
heapq.heappush(max_heap, -9)           # O(log n)
assert -max_heap[0] == 9
```

## 常见模式

### 对数据流维护有界的前 k 个

当元素逐个到达且只关心最大的 k 个时，一个 k 元素的最小堆就能保存它们：根是留存者中最弱的，
`heappushpop` 只有在新元素胜过它时才替换它。

```python
import heapq

k = 3
best = []
for reading in [12, 40, 7, 33, 51, 8, 29, 60]:
    if len(best) < k:
        heapq.heappush(best, reading)      # O(log k)
    else:
        heapq.heappushpop(best, reading)   # O(log k), O(1) if it cannot get in

assert sorted(best, reverse=True) == [60, 51, 40]  # O(k) memory throughout
```

### 任务优先级队列

```python
import heapq
import itertools

counter = itertools.count()
queue = []

def submit(priority, task):
    heapq.heappush(queue, (priority, next(counter), task))  # O(log n)

def take():
    priority, _, task = heapq.heappop(queue)  # O(log n)
    return task

submit(2, 'write report')
submit(1, 'fix outage')
submit(2, 'answer email')

assert [take() for _ in range(3)] == ['fix outage', 'write report', 'answer email']
```

## 最佳实践

✅ **应该**：

- 读取 `heap[0]` 来查看堆顶；它是 O(1)，不需要弹出再压入
- 同时压入和弹出时使用 `heappushpop` 或 `heapreplace`：一次调用，无需扩容或缩容，而且
  `heappushpop` 在一次比较后就返回进不去的元素
- 从大型或流式输入中取少量元素时使用 `nlargest` 或 `nsmallest`；内存随 k 而定
- 在优先级和负载之间放一个计数器，使优先级相同时永远不比较负载
- 对已排序的输入使用 `merge`：它是惰性的，每个输入只保留一个元素

❌ **避免**：

- 为了取几个元素而对整个列表排序 - O(m log m) 时间和 O(m) 内存
- 为了找一个元素而把堆弹空；堆只保证根的顺序
- 每次压入后都调用 `heapify` - 每次 O(n)，而压入只需 O(log n)
- 把未排序的输入传给 `merge`；输出不会有序，也没有任何提示

## 版本说明

- **Python 3.14+**：新增 `heapify_max`、`heappush_max`、`heappop_max`、`heappushpop_max` 和
  `heapreplace_max`

## 相关模块

- **[queue](queue.md)** - `PriorityQueue` 是加锁的 `heapq` 堆，供生产者和消费者线程使用
- **[sched](sched.md)** - 建立在定时事件堆之上的事件调度器
- **[bisect](bisect.md)** - 改为让列表保持完全有序，插入为 O(n)
- **[sorted()](../builtins/sorted.md)** - 需要全部元素而不只是前 k 个时为 O(m log m)
