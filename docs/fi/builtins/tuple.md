---
source_sha: 94b8516e62742f8991e48fca56d762ca55a09160a862913d1a31bbcba081e372
translated: machine
---

# Monikko-operaatioiden vaativuus

Tyyppi `tuple` on muuttumaton, järjestetty jono. Muuttumattomuus mahdollistaa monenlaisia optimointeja CPythonissa.

`n` on monikon pituus, `k` on indeksi tai toistokerroin, `i:j` ovat viipaleen rajat ja `len(t1)`,
`len(t2)` ovat operandien pituudet. Yhden alkion vertailu tai hajautus lasketaan O(1):ksi.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | Pituus on tallennettu monikkoon, sitä ei lasketa |
| `t[k]` | O(1) | O(1) | Suora indeksointi |
| `index(x)` | O(n) | O(1) | Lineaarinen haku |
| `count(x)` | O(n) | O(1) | Lineaarinen läpikäynti |
| `x in t` (jäsenyys) | O(n) | O(1) | Lineaarinen haku |
| `tuple(t)`, `copy.copy(t)` | O(1) | O(1) | Palauttaa `t`:n itsensä, kun `t` on täsmälleen `tuple`-tyyppinen; monikoilla ei ole `copy()`-metodia |
| `t1 + t2` (yhdistäminen) | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k` (toisto) | O(nk) | O(nk) | |
| `for x in t` (iterointi) | O(n) | O(1) | O(1) askelta kohden |
| `min(t)`, `max(t)` | O(n) | O(1) | n-1 vertailua |
| `hash()` | O(n) ensimmäisellä kerralla; sen jälkeen O(1) versiosta 3.14 alkaen | O(1) | 3.14+ tallentaa tiivisteen kenttään `ob_hash`; 3.11-3.13 laskevat sen joka kutsulla uudelleen |
| `reversed()` | O(1) | O(1) | Iteraattori, ei materialisoida |
| `tuple()`-konstruktori | O(n) | O(n) | n = iteroituvan pituus; täsmälleen `tuple`-tyyppinen monikko palautetaan sellaisenaan |
| `t[i:j]` (viipalointi) | O(j-i) | O(j-i) | Askeleen kanssa O(tuloksen pituus) |

## Toteutuksen yksityiskohdat

### Muuttumattomuuden edut

```python
# Tuples of hashable elements are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### Tiivisteen laskenta

```python
# hash() computes hash value by iterating all elements
t = tuple([1, 2, 3])  # built at run time, so not hashed yet
h1 = hash(t)  # O(n) first call - computes by iterating elements

# Python 3.14+ caches the hash in the tuple's ob_hash field;
# 3.11-3.13 recompute it on every call
h2 = hash(t)  # O(1) on 3.14+, O(n) on 3.11-3.13
assert h1 == h2
```

### Viittaus vai kopio

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
assert t1 is t2  # True - same object in memory!

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

- **Python 3.8+**: Monikoiden purku parantunut joissakin tapauksissa
- **Python 3.11+**: Mukautuva erikoistaminen voi optimoida toistuvia monikko-operaatioita
- **Python 3.14+**: `hash()` tallentaa tuloksensa monikkoon, joten toistuvat kutsut ovat O(1)

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

# Both have O(1) indexing; tuple is hashable and immutable
```

## Liittyvät tyypit

- **[Lista](list.md)** - Muuttuva vaihtoehto
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - Monikot nimetyillä kentillä
- **[Dataclass](../stdlib/dataclasses.md)** - Monipuolisempi rakennetyyppi

## Lisälukemista

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin monikkototeutukseen
