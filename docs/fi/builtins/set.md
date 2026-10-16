---
source_sha: aed89569718472744efe2fe630c10b81389a8b3acbbbd892311a4aba047ebccc
translated: machine
---

# Joukko-operaatioiden vaativuus

Tyyppi `set` on järjestämätön kokoelma uniikkeja alkioita. CPythonissa se on toteutettu hajautustauluna samaan tapaan kuin sanakirjat.

`n` on joukon alkioiden määrä ja `m` toisen operandin alkioiden määrä. Alkioiden hajautus ja
vertailu oletetaan O(1)-operaatioiksi.

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
| `union(other)`, `s \| other` | O(n+m) | O(n+m) | n, m = joukkojen koot |
| `intersection(other)`, `s & other` | O(min(n,m)); O(m), jos `other` ei ole joukko | O(min(n,m)) | Käy läpi pienemmän joukon |
| `difference(other)`, `s - other` | O(n); O(n+m), jos `other` ei ole joukko | O(n) | n = joukon koko |
| `symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | Yhdistetyt joukko-operaatiot |
| `issubset()` | O(n); O(n+m), jos `other` ei ole joukko | O(1); O(m), jos `other` ei ole joukko | Tarkistaa kaikki alkiot |
| `issuperset()` | O(m) | O(1) | m = toisen joukon koko |
| `isdisjoint()` | O(min(n,m)); O(m), jos `other` ei ole joukko | O(1) | Päättyy heti löydöksen jälkeen |
| `update(other)`, `s \|= other` | O(m) | O(1) | Yhdiste paikallaan; m = len(other) |
| `difference_update(other)`, `s -= other` | O(min(n,m)); O(m), jos `other` ei ole joukko | O(n) | Erotus paikallaan; käy läpi pienemmän puolen |
| `intersection_update(other)`, `s &= other` | O(min(n,m)) tasoitettu; O(m) tasoitettu, jos `other` ei ole joukko | O(min(n,m)) | Leikkaus paikallaan; yksi kutsu vapauttaa vanhan taulun ajassa O(n), jonka pois jäävien alkioiden lisääminen on jo maksanut |
| `symmetric_difference_update(other)`, `s ^= other` | O(m) | O(1); O(m), jos `other` ei ole joukko | Symmetrinen erotus paikallaan |

Operaattorimuodot hyväksyvät vain joukkoja ja frozenset-olioita; metodit hyväksyvät myös minkä
tahansa iteroitavan. Pahimmassa tapauksessa, kun jokaisella alkiolla on sama tiiviste,
O(1)-operaatiot vievät O(n), ja operaatiot, jotka hakevat yhden joukon jokaisen alkion toisesta,
hidastuvat vastaavasti.

Alkioiden poistaminen metodeilla `remove()`, `discard()` tai `pop()` ei pienennä taulua. Kun
suurin osa alkioista on poistettu, taulun läpikäyvät operaatiot - iterointi, `copy()`, `|`, `-`,
`^`, `&=`, vertailut ja `set(s)` - vievät yhä aikaa suhteessa joukon aiempaan kokoon, kunnes myöhemmät
lisäykset laukaisevat kokomuutoksen. `len()` ja jäsenyystestit eivät muutu. `&=` ja sitä vastaava metodi jättävät taulun aina
tiiviiksi, samoin kuin suurimman osan alkioista poistaminen operaattorilla `-=` tai sitä vastaavalla metodilla.

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

### Poistaminen ei pienennä taulua

```python
import sys

s = set(range(100_000))
full = sys.getsizeof(s)
for i in range(10, 100_000):
    s.discard(i)                   # O(1) each

assert len(s) == 10                # O(1)
assert sys.getsizeof(s) == full    # still sized for 100,000 elements
items = list(s)                    # O(100,000): walks the old table

s = s.copy()                       # O(100,000) once
assert sys.getsizeof(s) < full     # sized for 10 elements
assert sorted(s) == sorted(items)  # O(10)
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
items = [3, 1, 3, 2, 1]

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

- **[Frozenset](frozenset.md)** - Muuttumaton joukko
- **[Dict](dict.md)** - Muuttuva kuvaus
- **[Deque](../stdlib/collections.md#deque)** - Järjestetty kokoelma

## Lisälukemista

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin joukkototeutukseen
