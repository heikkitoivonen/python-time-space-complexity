---
source_sha: c0bc8604cd865955e9bee5e9ce07ac587f5fc37659a6f2d952c5a11560725f18
translated: machine
---

# Monikko-operaatioiden vaativuus

Tyyppi `tuple` on muuttumaton, järjestetty jono. Muuttumattomuus mahdollistaa monenlaisia optimointeja CPythonissa.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Suora haku |
| `access[i]` | O(1) | O(1) | Suora indeksointi |
| `index(x)` | O(n) | O(1) | Lineaarinen haku |
| `count(x)` | O(n) | O(1) | Lineaarinen läpikäynti |
| `in` (jäsenyys) | O(n) | O(1) | Lineaarinen haku |
| `copy()` | O(1) | O(1) | Kasvattaa vain viittauslaskuria |
| `x + y` (yhdistäminen) | O(m+n) | O(m+n) | m ja n ovat pituuksia |
| `t * n` (toisto) | O(n*len(t)) | O(n*len(t)) | Luo uuden monikon |
| `hash()` | O(n) ensimmäisellä kerralla, O(1) välimuistista | O(1) | Tiiviste lasketaan kerran ja tallennetaan kenttään `ob_hash` |
| `reversed()` | O(1) | O(1) | Iteraattori, ei materialisoida |
| `tuple()`-konstruktori | O(n) | O(n) | n = iteroituvan pituus |
| `slice [::2]` | O(k) | O(k) | k = viipaleen pituus |

## Toteutuksen yksityiskohdat

### Muuttumattomuuden edut

```python
# Tuples are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### Tiivisteen laskenta

```python
# hash() computes hash value by iterating all elements
t = (1, 2, 3)
h1 = hash(t)  # O(n) first call - computes by iterating elements

# CPython caches the hash in the tuple's ob_hash field
# Subsequent calls return the cached value
h2 = hash(t)  # O(1) - returns cached hash
```

### Viittaus vai kopio

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
print(t1 is t2)  # True - same object in memory!

# This is safe because tuples are immutable
```

## Suorituskyky listoihin verrattuna

```python
# List access: O(1) with bounds checking
lst = [0] * 1000000
value = lst[500000]  # O(1)

# Tuple access: O(1) same as list
tup = tuple(lst)
value = tup[500000]  # O(1)

# But tuple creation from list: O(n)
tup = tuple(lst)  # O(n) - must copy all elements
```

## Versiohuomiot

- **Kaikki versiot**: Perusvaativuudet vakaat
- **Python 3.8+**: Monikoiden purku parantunut joissakin tapauksissa
- **Python 3.11+**: Mukautuva erikoistaminen voi optimoida toistuvia monikko-operaatioita

## Toteutusten vertailu

### CPython
Suora jonotyyppi, jossa on muuttumattomuuteen perustuvia optimointeja.

### PyPy
JIT-käännös ja escape-analyysi voivat optimoida edelleen.

### Jython
Samankaltaiset ominaisuudet, taustalla Javan taulukot.

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä monikoita muuttumattomiin jonoihin
- Käytä monikoita sanakirjan avaimina, kun tarvitset rakenteisia avaimia
- Käytä monikoita useiden paluuarvojen palauttamiseen
- Käytä monikon purkua: `x, y = point`

❌ **Vältä**:

- Toistuvaa yhdistämistä: `t += (item,)` silmukoissa - käytä sen sijaan listaa
- Monikoiden luomista suurista iteroituvista silmukan sisällä
- Oletusta, että monikon kopiointi on nopeaa - se viittaa edelleen samoihin alkioihin

## Yleisiä ratkaisumalleja

### Nimetyt paluuarvot

```python
# Basic tuples
def get_coordinates():
    return (10, 20)

x, y = get_coordinates()

# Better: use named tuples
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])

def get_point():
    return Point(10, 20)

p = get_point()
print(p.x, p.y)  # More readable
```

### Monikon ja listan suorituskyky

```python
# Tuple creation: O(n) once, then fast access
tup = tuple(range(1000000))
for i in range(1000):
    x = tup[i]  # O(1)

# List creation: O(n) once, then fast access
lst = list(range(1000000))
for i in range(1000):
    x = lst[i]  # O(1)

# Both have same access time; tuple is hashable and immutable
```

## Liittyvät tyypit

- **[Lista](list.md)** - Muuttuva vaihtoehto
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - Monikot nimetyillä kentillä
- **[Dataclass](../stdlib/dataclasses.md)** - Monipuolisempi rakennetyyppi

## Lisälukemista

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin monikkototeutukseen
