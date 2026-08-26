---
source_sha: 8c74d4dceb60daaf6846dcebf2ff05fd139381765e1c29853f7d1df29f28613e
translated: machine
---

# enumerate()-funktion vaativuus

Funktio `enumerate()` palauttaa iteraattorin, joka tuottaa (indeksi, alkio) -monikoita iteroituvasta.

## Vaativuusanalyysi

| Tapaus | Aika | Tila | Huomiot |
|------|------|-------|-------|
| Iteraattorin luonti | O(1) | O(1) | Luo vain iteraattoriolion |
| Iteraattorin kuluttaminen | O(n) | O(1) | n = läpikäytyjen alkioiden määrä; tuottaa yhden kerrallaan |
| Oma aloitusarvo | O(n) | O(1) | start-parametri ei muuta vaativuutta |

*Huomio: enumerate() palauttaa iteraattorin, joka tuottaa monikot laiskasti. Tilavaativuus on O(1), koska se ei säilytä kaikkia monikoita muistissa. Muuntaminen listaksi `list(enumerate(x))`-kutsulla vie O(n) tilaa.*

## Peruskäyttö

### Yksinkertainen numerointi

```python
# O(1) - creates iterator
items = ['a', 'b', 'c']
enumerated = enumerate(items)  # Iterator

# O(n) - consumed when needed
for index, item in enumerated:
    print(index, item)
# 0 a
# 1 b
# 2 c

# Convert to list - O(n) time and space
result = list(enumerate(items))
# [(0, 'a'), (1, 'b'), (2, 'c')]
```

### Oma aloitusindeksi

```python
# O(1) - creates iterator
items = ['a', 'b', 'c']
enumerated = enumerate(items, start=1)

# O(n) - consumed
result = list(enumerated)
# [(1, 'a'), (2, 'b'), (3, 'c')]

# Works with any start value
result = list(enumerate(items, start=10))
# [(10, 'a'), (11, 'b'), (12, 'c')]
```

## Suorituskykymallit

### Laiska evaluointi

```python
# O(1) - creates iterator, doesn't process yet
big_list = range(10**9)
enumerated = enumerate(big_list)

# O(n) - only when you consume
for i, item in enumerate(big_list):
    print(i, item)
    if i >= 10:
        break  # O(10) - stops early

# vs list comprehension
result = [(i, x) for i, x in enumerate(range(10**9))]  # O(10^9)!
```

### Sisäkkäinen numerointi

```python
# O(n*m*k) - enumerate nested structures
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

# O(n*m) - enumerate rows and columns
for i, row in enumerate(matrix):
    for j, item in enumerate(row):
        print(f"[{i}][{j}] = {item}")
```

## Yleisiä ratkaisumalleja

### Iterointi indeksin kanssa

```python
# ✅ O(n) - preferred way
items = ['a', 'b', 'c', 'd', 'e']
for index, item in enumerate(items):
    print(index, item)

# ❌ O(n) but less Pythonic
for i in range(len(items)):
    print(i, items[i])

# ❌ O(n) with unnecessary zip
for i, item in zip(range(len(items)), items):
    print(i, item)
```

### Suodatus indeksin avulla

```python
# O(n) - enumerate and filter
items = ['a', 'b', 'c', 'd', 'e']
result = [item for i, item in enumerate(items) if i % 2 == 0]
# ['a', 'c', 'e']

# Get only indices
indices = [i for i, item in enumerate(items) if 'a' in item]
# [0]
```

### Uuden rakenteen rakentaminen

```python
# O(n) - enumerate to create dict
items = ['apple', 'banana', 'cherry']
item_dict = {i: item for i, item in enumerate(items)}
# {0: 'apple', 1: 'banana', 2: 'cherry'}

# With custom start
item_dict = {i: item for i, item in enumerate(items, start=1)}
# {1: 'apple', 2: 'banana', 3: 'cherry'}
```

## Työskentely useiden iteroituvien kanssa

### Rinnakkainen iterointi indeksin kanssa

```python
# O(n) - enumerate with zip
names = ['Alice', 'Bob', 'Charlie']
ages = [30, 25, 35]

for i, (name, age) in enumerate(zip(names, ages)):
    print(f"{i}: {name} is {age}")
# 0: Alice is 30
# 1: Bob is 25
# 2: Charlie is 35
```

### Sisäkkäiset rakenteet

```python
# O(n*m*k) - multiple levels of enumeration
data = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
]

for i, row in enumerate(data):
    for j, item in enumerate(row):
        print(f"[{i}][{j}] = {item}")
```

## Edistyneet ratkaisumallit

### enumerate oman indeksin kanssa

```python
# O(n) - enumerate with offset
items = ['a', 'b', 'c', 'd', 'e']
for index, item in enumerate(items, start=100):
    print(index, item)
# 100 a
# 101 b
# ... etc
```

### Sijainnin etsiminen

```python
# O(n) - find position of element
items = ['apple', 'banana', 'cherry', 'date']
target = 'cherry'

for index, item in enumerate(items):
    if item == target:
        position = index
        break
# position = 2

# Alternative: use index() method
position = items.index(target)  # O(n) - same complexity
```

### Ehdollinen numerointi

```python
# O(n) - enumerate with filter
items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Only enumerate even items
for index, item in enumerate(items):
    if item % 2 == 0:
        print(index, item)
# 1 2
# 3 4
# ... etc
```

## Vertailu vaihtoehtoihin

### enumerate vs range(len(...))

```python
# ✅ enumerate - preferred, more Pythonic
items = ['a', 'b', 'c']
for i, item in enumerate(items):
    print(i, item)

# ❌ range(len(...)) - less readable
for i in range(len(items)):
    print(i, items[i])

# Both O(n), enumerate is clearer
```

### enumerate vs zip ja range

```python
# ✅ enumerate - simpler and faster
items = ['a', 'b', 'c']
for i, item in enumerate(items):
    process(i, item)

# ❌ zip with range - unnecessary overhead
for i, item in zip(range(len(items)), items):
    process(i, item)

# Both O(n), enumerate is more efficient
```

### enumerate vs index()-metodi

```python
# If finding position of one element
items = ['a', 'b', 'c', 'd', 'e']
target = 'c'

# O(n) - enumerate
for i, item in enumerate(items):
    if item == target:
        print(i)
        break

# O(n) - index method
print(items.index(target))

# If finding multiple positions
# enumerate is more efficient - single pass

# If finding one - index() is clearer
```

## Erikoistapaukset

### Tyhjä iteroituva

```python
# O(1) - creates empty iterator
result = list(enumerate([]))
# []

for i, item in enumerate([]):
    print(i, item)  # Never executes
```

### Yksi alkio

```python
# O(1) - creates iterator with one element
result = list(enumerate(['a']))
# [(0, 'a')]
```

### Suuri aloitusarvo

```python
# O(1) - start value doesn't affect complexity
result = list(enumerate([1, 2, 3], start=10**9))
# [(1000000000, 1), (1000000001, 2), (1000000002, 3)]
```

### Generaattorit

```python
# O(n) - enumerate can consume generators
def generator():
    yield 1
    yield 2
    yield 3

for i, value in enumerate(generator()):
    print(i, value)
# 0 1
# 1 2
# 2 3
```

## Suorituskykyhuomioita

### Muistitehokkuus

```python
# ✅ Iterator - memory efficient
big_list = range(10**9)
for i, item in enumerate(big_list):
    if i < 10:
        print(item)
# Only iterates 10 items

# ❌ List creation - uses memory
indices_items = list(enumerate(range(10**9)))  # Huge memory!
```

### Nopeusvertailu

```python
import timeit

items = list(range(1000))

# Time for enumerate
t1 = timeit.timeit(lambda: [x for i, x in enumerate(items)], number=10000)

# Time for range(len(...))
t2 = timeit.timeit(lambda: [items[i] for i in range(len(items))], number=10000)

# enumerate is generally faster due to optimizations
```

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä `enumerate()`-funktiota, kun tarvitset sekä indeksin että alkion
- Käytä `enumerate(iterable, start=1)`-muotoa ykkösestä alkavaan indeksointiin
- Käytä `enumerate()`-funktiota yhdessä `break`-lauseen kanssa aikaiseen poistumiseen
- Käytä `enumerate()`-funktiota laiskaan evaluointiin suurilla aineistoilla

❌ **Vältä**:

- `range(len(...))`-muodon käyttöä, kun `enumerate()` on selkeämpi
- `zip(range(len(...)), iterable)`-muodon käyttöä - käytä sen sijaan `enumerate()`-funktiota
- Unohtamasta, että `enumerate()` palauttaa iteraattorin
- Turhien välilistojen luomista

## Liittyvät funktiot

- **[zip()](zip.md)** - Yhdistää useita iteroituvia
- **[range()](range.md)** - Tuottaa lukujonoja
- **[iter()](iter.md)** - Luo iteraattoreita
- **[next()](next.md)** - Hakee iteraattorin seuraavan alkion

## Versiohuomiot

- **Python 2.x**: `enumerate()` käytettävissä, toimii samaan tapaan
- **Python 3.x**: Sama toiminta ja suorituskyky
- **Python 3.8+**: Optimoinnit voivat parantaa suorituskykyä, mutta O(n) on taattu
