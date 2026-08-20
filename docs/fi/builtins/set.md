---
source_sha: 481ae7e0eb06ad0f4ca7fba108eb1d8b8d8dfb70d13bf0b405746fc83f0d311c
translated: machine
---

# Joukko-operaatioiden vaativuus

Tyyppi `set` on järjestämätön kokoelma uniikkeja alkioita. CPythonissa se on toteutettu hajautustauluna samaan tapaan kuin sanakirjat.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Suora lukumäärä |
| `add(x)` | O(1) keskim., O(n) pahin | O(1) tasoitettu | Tiivistetörmäykset aiheuttavat O(n) |
| `remove(x)` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku + poisto |
| `discard(x)` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku + poisto |
| `pop()` | O(1) keskim. | O(1) | Poistaa mielivaltaisen alkion |
| `clear()` | O(n) | O(1) | Vapauttaa kaiken |
| `x in set` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku; törmäykset aiheuttavat O(n) |
| `copy()` | O(n) | O(n) | Pinnallinen kopio |
| `union(other)` | O(n+m) | O(n+m) | n, m = joukkojen koot |
| `intersection(other)` | O(min(n,m)) | O(min(n,m)) | Käy läpi pienemmän joukon |
| `difference(other)` | O(n) | O(n) | n = joukon koko |
| `symmetric_difference(other)` | O(n+m) | O(n+m) | Yhdistetyt joukko-operaatiot |
| `issubset()` | O(n) | O(1) | Tarkistaa kaikki alkiot |
| `issuperset()` | O(m) | O(1) | m = toisen joukon koko |
| `isdisjoint()` | O(min(n,m)) | O(1) | Päättyy heti löydöksen jälkeen |
| `update(other)` | O(m) | O(1) | Yhdiste paikallaan; m = len(other) |
| `difference_update(other)` | O(m) | O(1) | Erotus paikallaan |
| `intersection_update(other)` | O(n) | O(1) | Leikkaus paikallaan; rakentaa joukon uudelleen |
| `symmetric_difference_update(other)` | O(m) | O(1) | Symmetrinen erotus paikallaan |

## Toteutuksen yksityiskohdat

### Hajautustaulutoteutus

Joukot käyttävät samaa hajautustaulurakennetta kuin sanakirjat, mutta:

- Tallentavat vain avaimet (ei arvoja)
- Ovat muistitehokkaampia kuin sanakirjat
- Tarjoavat saman keskimääräisen O(1)-haun

### Joukko-operaatiot

```python
# Union: combines both sets
{1, 2} | {2, 3}  # {1, 2, 3} - O(len(s1) + len(s2))

# Intersection: common elements
{1, 2, 3} & {2, 3, 4}  # {2, 3} - O(min(len(s1), len(s2)))

# Difference: elements in first but not second
{1, 2, 3} - {2, 4}  # {1, 3} - O(len(s1))

# Symmetric difference: elements in either but not both
{1, 2} ^ {2, 3}  # {1, 3} - O(len(s1) + len(s2))
```

### Jäsenyyden testaus

```python
# Very fast - O(1) hash lookup
s = {1, 2, 3, 4, 5}
if 3 in s:  # O(1), not O(n)
    pass
```

## Vertailu listoihin

```python
# List membership: O(n) - must scan entire list
numbers_list = [1, 2, 3, 4, 5]
3 in numbers_list  # O(n)

# Set membership: O(1) - hash lookup
numbers_set = {1, 2, 3, 4, 5}
3 in numbers_set  # O(1) - much faster for large collections!
```

## Versiohuomiot

- **Kaikki Python 3 -versiot**: Perusvaativuudet ennallaan
- **Python 3.9+**: Uudet joukkojen yhdiste- ja leikkausoperaattorit

## Toteutusten vertailu

### CPython
Standardi hajautustaulutoteutus.

### PyPy
JIT-käännös voi tuoda lisäoptimointia.

### Jython
Taustalla Javan HashSet, samat O(1)-ominaisuudet.

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä joukkoja jäsenyyden testaamiseen suurissa kokoelmissa
- Käytä joukko-operaattoreita (`|`, `&`, `-`, `^`) joukkojen yhdistelyyn
- Käytä joukkoja duplikaattien poistoon: `set(list_with_dups)`
- Käytä `frozenset`-tyyppiä hajautuskelpoisiin uniikkeihin alkioihin

❌ **Vältä**:

- Listojen käyttöä toistuvissa jäsenyystarkistuksissa
- Joukon järjestykseen luottamista (ei taattu)
- Hajautuskelvottomia tyyppejä (listat, sanakirjat) joukoissa

## Yleisiä ratkaisumalleja

### Duplikaattien poisto

```python
# Bad: preserves list, but O(n²)
unique = []
for item in items:
    if item not in unique:
        unique.append(item)

# Good: O(n), but loses order
unique = list(set(items))

# Best: O(n) and preserves order (Python 3.7+)
unique = list(dict.fromkeys(items))
```

### Nopea suodatus

```python
# Bad: O(n*m) - checks membership in list for each element
large_list = list(range(1000000))
exclusions = [1, 2, 3, ...]
filtered = [x for x in large_list if x not in exclusions]

# Good: O(n) - fast set lookup
exclusions_set = set(exclusions)
filtered = [x for x in large_list if x not in exclusions_set]
```

## Liittyvät tyypit

- **[Frozenset](index.md)** - Muuttumaton joukko
- **[Dict](dict.md)** - Muuttuva kuvaus
- **[Deque](../stdlib/collections.md#deque)** - Järjestetty kokoelma

## Lisälukemista

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin joukkototeutukseen
