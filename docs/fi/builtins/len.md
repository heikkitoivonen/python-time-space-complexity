---
source_sha: d121e0a8af5ee71633a5877aead4146b5a677a147d64343c227a3ee27348715b
translated: machine
---

# len()-funktion vaativuus

Funktio `len()` palauttaa säiliöolion sisältämien alkioiden lukumäärän.

## Vaativuus tyypeittäin

| Tyyppi | Aika | Tila | Huomiot |
|------|------|-------|-------|
| `list` | O(1) | O(1) | Suora pituusattribuutti |
| `tuple` | O(1) | O(1) | Muuttumaton, välimuistissa |
| `dict` | O(1) | O(1) | Ylläpitää kokoa |
| `set` | O(1) | O(1) | Ylläpitää kokoa |
| `str` | O(1) | O(1) | Muuttumaton, välimuistissa |
| `bytes` | O(1) | O(1) | Muuttumaton, välimuistissa |
| `range` | O(1) | O(1) | Laskettu, ei tallennettu |
| `deque` | O(1) | O(1) | Ylläpitää kokoa |
| `defaultdict` | O(1) | O(1) | Peritty sanakirjalta |
| `OrderedDict` | O(1) | O(1) | Ylläpitää kokoa |

## Sisäänrakennetut säiliötyypit

Kaikki sisäänrakennetut säiliötyypit pitävät pituutensa muistissa ja palauttavat sen vakioajassa:

```python
# All O(1)
lst = [1, 2, 3, 4, 5]
length = len(lst)  # O(1) - stored length

tpl = (1, 2, 3)
length = len(tpl)  # O(1) - immutable

dct = {'a': 1, 'b': 2}
length = len(dct)  # O(1) - maintains size

s = "hello"
length = len(s)    # O(1) - immutable string
```

## Omat oliot

Omille luokille `len()` kutsuu metodia `__len__()`:

```python
class MyContainer:
    def __init__(self, items):
        self.items = items
    
    def __len__(self):
        # Your implementation determines complexity
        return len(self.items)  # O(1) if efficient

# Usage
obj = MyContainer([1, 2, 3])
length = len(obj)  # O(1) - delegates to cached length

# Inefficient implementation
class BadContainer:
    def __init__(self, items):
        self.items = items
    
    def __len__(self):
        # Recomputes from scratch - O(n)!
        return sum(1 for _ in self.items)

obj = BadContainer([1, 2, 3])
length = len(obj)  # O(n) - iterates through items
```

## Generaattorilausekkeet ja iteraattorit

`len()` EI toimi generaattoreiden eikä iteraattoreiden kanssa:

```python
# Works - list has cached length
lst = [1, 2, 3, 4, 5]
length = len(lst)  # O(1)

# Fails - generators don't have length
gen = (x for x in range(5))
# length = len(gen)  # TypeError: object of type 'generator' has no len()

# Must consume iterator to count
count = sum(1 for x in gen)  # O(n) - must iterate
```

## Yleisiä ratkaisumalleja

### Säiliön tyhjyyden tarkistaminen

```python
# Correct - O(1), doesn't create list
if len(container) > 0:
    process(container)

# Also correct - O(1), more Pythonic
if container:
    process(container)

# Inefficient - creates a list
if len(list(generator)) > 0:  # O(n) - forces evaluation
    process(generator)
```

### Koon tarkistaminen

```python
def process_list(items):
    if len(items) == 0:      # O(1)
        raise ValueError("Empty list")
    if len(items) > 1000:    # O(1)
        raise ValueError("Too large")
    
    # Process items
    for item in items:
        pass
```

### Säiliöiden kokojen vertailu

```python
# All O(1)
if len(list1) > len(list2):
    smaller = list2
    larger = list1
else:
    smaller = list1
    larger = list2

# More efficient than computing actual difference
if len(list1) != len(list2):
    print("Different sizes")
```

## Suorituskykyhuomioita

### Pituusoperaatiot silmukoissa

```python
# O(n) - good, length is O(1)
for i in range(len(items)):
    process(items[i])

# Also O(n) - length check is O(1) per iteration
count = 0
while count < len(items):
    process(items[count])
    count += 1
```

### Pituuden esilaskenta

```python
items = get_large_list()

# Don't do this - wastes a variable
length = len(items)
for i in range(length):  # length already O(1)
    process(items[i])

# Instead - directly use len() which is O(1)
for i in range(len(items)):
    process(items[i])
```

## Erikoistapaukset

### Range-oliot

```python
# Range length is O(1), not O(n)
r = range(10**1000)
length = len(r)  # O(1) - computed from start, stop, step

# This is computed, not stored
# So even huge ranges have O(1) length
```

### Merkkijonojen koodaus

```python
# All string types have O(1) length
s = "hello"
length = len(s)  # O(1) - character count

b = b"hello"
length = len(b)  # O(1) - byte count

# Note: len(str) counts characters, not bytes
s = "café"
print(len(s))      # 4 - four characters
print(len(s.encode('utf-8')))  # 5 - five bytes
```

## Versiohuomiot

- **Python 2.x**: `len()` toimii sisäänrakennetuilla tyypeillä ja omalla `__len__`-metodilla
- **Python 3.x**: Sama käyttäytyminen, johdonmukaisemmin
- **Kaikki versiot**: O(1) sisäänrakennetuille säiliöille (ne pitävät pituuden muistissa)

## Liittyvät funktiot

- **[all()](all.md)** - Tarkistaa, ovatko kaikki alkiot tosia
- **[any()](any.md)** - Tarkistaa, onko jokin alkio tosi
- **[max()](max.md)** - Etsii suurimman arvon
- **[min()](min.md)** - Etsii pienimmän arvon
- **[sum()](sum.md)** - Laskee alkioiden summan

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä `len()`-funktiota säiliön tyhjyyden tarkistamiseen (se on O(1))
- Käytä muotoa `if container:` totuusarvotarkistuksiin
- Tallenna pituus muuttujaan vain, jos sitä käytetään toistuvasti tiukoissa silmukoissa

❌ **Vältä**:

- `len(list(generator))` generaattorin alkioiden laskemiseen (O(n))
- Pituuden uudelleenlaskentaa `__len__`-metodissa (se tulisi pitää muistissa)
- Oletusta, että generaattoreilla on pituus (niillä ei ole)
