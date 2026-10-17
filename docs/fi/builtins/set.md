---
source_sha: bc1c0d5a1529618fadecea5515f24b98a32b01bad53b2296163318b2ea145d27
translated: machine
---

# Joukko-operaatioiden vaativuus

Tyyppi `set` on muuttuva, järjestämätön kokoelma uniikkeja hajautettavia alkioita. Se on
hajautustaulu kuten `dict` ilman arvoja, joten jäsenyystesti, lisääminen ja poistaminen maksavat
keskimäärin O(1), ja joukko-operaatiot maksavat niiden alkioiden verran, jotka niiden on haettava.

`n` on joukon alkioiden määrä ja `m` toisen operandin alkioiden määrä tai iteroitavan operandin
tuottamien alkioiden määrä. Rivit hinnoittelevat yhden operandin; metodi, jolle annetaan useita,
käsittelee ne peräkkäin, ja kustannukset lasketaan yhteen. Alkioiden hajautus ja vertailu oletetaan
O(1)-operaatioiksi.

## Vaativuustaulukko

### set

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | Lukumäärä on tallennettu |
| `x in s` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku; pahin tapaus tiivistetörmäyksillä. Joukko `x` hajautetaan kuten frozenset: O(k) sen k alkiolle, ja ennen versiota 3.14 tilaa O(k) |
| `set`-olion iterointi | O(n) | O(1) | Mielivaltainen järjestys |
| `s.add(x)` | O(1) tasoitettu | O(1) tasoitettu | Kokomuutos rakentaa taulun toisinaan uudelleen ajassa O(n) |
| `s.remove(x)`, `s.discard(x)` | O(1) keskim., O(n) pahin | O(1) | `remove()` nostaa `KeyError`-poikkeuksen, kun `x` puuttuu; joukko `x` hajautetaan kuten `x in s` -testissä |
| `s.pop()` | O(1) tasoitettu tyhjennettäessä | O(1) | Poistaa mielivaltaisen alkion aloittaen siitä, mihin edellinen `pop()` jäi; nostaa `KeyError`-poikkeuksen, kun joukko on tyhjä. Muiden poistojen jälkeen yksi kutsu voi maksaa taulun aiemman koon verran |
| `s.clear()` | O(n) | O(1) | Vapauttaa jokaisen alkion |
| `s.copy()` | O(n) | O(n) | Pinnallinen; kopion koko vastaa sen sisältämiä alkioita |
| `s == other`, `s != other` | O(n) | O(1) | O(1), kun pituudet eroavat |
| `s <= other`, `s < other` | O(n) | O(1) | Sama kuin `issubset()` joukolla |
| `s >= other`, `s > other` | O(m) | O(1) | Sama kuin `issuperset()` joukolla |

### Joukko-operaatiot

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `s.union(other)`, `s \| other` | O(n+m) | O(n+m) | Palauttaa uuden joukon |
| `s.intersection(other)`, `s & other` | O(min(n,m)); O(m), jos `other` ei ole joukko | O(min(n,m)) | Hakee pienemmän joukon alkiot suuremmasta |
| `s.difference(other)`, `s - other` | O(n); O(n+m), jos `other` ei ole joukko | O(n) | Palauttaa uuden joukon |
| `s.symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | Palauttaa uuden joukon |
| `s.issubset(other)` | O(n); O(n+m), jos `other` ei ole joukko | O(1); O(m), jos `other` ei ole joukko | O(1), kun `other` on lyhyempi joukko |
| `s.issuperset(other)` | O(m) | O(1) | Pysähtyy ensimmäiseen `other`-alkioon, joka puuttuu joukosta `s` |
| `s.isdisjoint(other)` | O(min(n,m)); O(m), jos `other` ei ole joukko | O(1) | Pysähtyy ensimmäiseen yhteiseen alkioon; joukon aliluokka iteroidaan kuten mikä tahansa iteroitava |

### Päivitykset paikallaan

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `s.update(other)`, `s \|= other` | O(m) tasoitettu | O(m) tasoitettu | `s` kasvaa enintään m alkiolla |
| `s.intersection_update(other)`, `s &= other` | O(min(n,m)) tasoitettu; O(m) tasoitettu, jos `other` ei ole joukko | O(min(n,m)) | Rakentaa leikkauksen ja vaihtaa sen tilalle; vanhan taulun vapauttaminen on O(n), jonka sen täyttäneet lisäykset ovat jo maksaneet |
| `s.difference_update(other)`, `s -= other` | O(min(n,m)) tasoitettu; O(m) tasoitettu, jos `other` ei ole joukko | O(n) | Poistaa joukosta `s` paikallaan |
| `s.symmetric_difference_update(other)`, `s ^= other` | O(m) tasoitettu | O(m) tasoitettu | `s` kasvaa enintään m alkiolla; operandi `other`, joka ei ole joukko, kopioidaan ensin joukoksi |

Operaattorit hyväksyvät vain joukkoja ja frozenset-olioita; metodit hyväksyvät myös minkä tahansa
iteroitavan. Pahimmassa tapauksessa, kun jokaisella alkiolla on sama tiiviste, O(1)-operaatiot
vievät O(n), ja operaatiot, jotka hakevat yhden joukon jokaisen alkion toisesta, hidastuvat
vastaavasti.

Alkioiden poistaminen metodeilla `remove()`, `discard()` tai `pop()` ei pienennä taulua. Kun
suurin osa alkioista on poistettu, taulun läpikäyvät operaatiot - iterointi, `copy()`, `clear()`,
`|`, `-`, `^`, `&=`, vertailut ja `set(s)` - vievät yhä aikaa suhteessa joukon aiempaan kokoon,
kunnes myöhemmät lisäykset käynnistävät kokomuutoksen, ja niin voi viedä yksittäinen `pop()`.
`len()` ja jäsenyystestit eivät muutu. `&=` ja sen metodi jättävät aina tiiviin taulun.

## Joukko-operaatiot

Operaattorit hyväksyvät vain joukkoja ja frozenset-olioita, joten lista oikealla puolella aiheuttaa
`TypeError`-poikkeuksen; metodit hyväksyvät minkä tahansa iteroitavan ja muuttavat sen alkioiksi
edetessään.

```python
a = {1, 2, 3}
b = {2, 3, 4}

assert a | b == {1, 2, 3, 4}     # O(n+m)
assert a & b == {2, 3}           # O(min(n,m))
assert a - b == {1}              # O(n)
assert a ^ b == {1, 4}           # O(n+m)

assert a.union([3, 4]) == {1, 2, 3, 4}  # O(n+m): a method takes any iterable
try:
    a | [3, 4]
except TypeError as error:
    assert 'unsupported operand' in str(error)
else:
    raise AssertionError('an operator takes only sets')

a |= b                           # O(m): grows a in place
assert a == {1, 2, 3, 4}
```

## Jäsenyystestaus

Lista vertaa `x`:ää alkioihinsa yksi kerrallaan; joukko hajauttaa `x`:n kerran ja tutkii
keskimäärin muutaman paikan. Listan muuntaminen joukoksi maksaa kerran O(n), joten se kannattaa,
kun haet monia arvoja.

```python
numbers = list(range(1_000))
lookup = set(numbers)          # O(n) once

assert 999 in numbers          # O(n): scans the whole list
assert 999 in lookup           # O(1) avg
assert -1 not in lookup        # O(1) avg, found or not

# A set can be looked up in a set of frozensets, hashed as a frozenset
groups = {frozenset({1, 2}), frozenset({3})}
assert {1, 2} in groups        # O(k) to hash the k-element key
```

## Poistaminen ei pienennä taulua

Poistaminen jättää taulun suurimpaan kokoonsa, joten sen läpikäynti maksaa yhä saman kuin täytenä.
`copy()` palauttaa tiiviin taulun.

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

Joukon tyhjentäminen pelkällä `pop()`-metodilla käy jokaisen paikan läpi kerran, koska jokainen
kutsu aloittaa siitä, mihin edellinen jäi. Muiden poistojen jälkeen `pop()` joutuu ensin
ohittamaan edessään olevat tyhjät paikat.

```python
s = set(range(1_000))
drained = 0
while s:
    s.pop()                        # O(1) amortized: the n calls walk the table once
    drained += 1
assert drained == 1_000

try:
    s.pop()
except KeyError as error:
    assert 'pop from an empty set' in str(error)
else:
    raise AssertionError('pop() on an empty set raises')
```

## Yleisiä käyttötapoja

### Kaksoiskappaleiden poistaminen

```python
items = [3, 1, 3, 2, 1]

# Bad: O(n²) - each `in` scans the list built so far
unique = []
for item in items:
    if item not in unique:
        unique.append(item)
assert unique == [3, 1, 2]

# Good: O(n), but the order is arbitrary
unique = set(items)
assert unique == {1, 2, 3}

# Best when order matters: O(n), keeping the first occurrence of each
assert list(dict.fromkeys(items)) == [3, 1, 2]
```

### Nopea suodatus

```python
values = list(range(10_000))
excluded = [3, 30, 300, 3_000]

# Bad: O(n·m) - scans the excluded list for every value
slow = [x for x in values if x not in excluded]

# Good: O(n + m) - one O(m) conversion, then O(1) per value
excluded_set = set(excluded)
fast = [x for x in values if x not in excluded_set]

assert slow == fast and len(fast) == 10_000 - 4
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Käytä joukkoa toistuviin jäsenyystesteihin: O(1) kukin, kun lista maksaa O(n)
- Laske joukkojen leikkaus kummassa järjestyksessä tahansa: `&` ja `intersection()` joukko-operandilla käyvät läpi vain pienemmän
- Käytä `dict.fromkeys()`-metodia, kun tarvitset uniikit alkiot alkuperäisessä järjestyksessään
- Kopioi joukko, joka on menettänyt suurimman osan alkioistaan, ennen kuin käyt sitä usein läpi, jotta läpikäynnit maksavat sen sisällön verran

❌ **Vältä**:

- `x in some_list` -testiä silmukassa toisen kokoelman yli - O(n·m), kun joukolla saa O(n + m)
- Iterointijärjestykseen luottamista; se seuraa hajautustaulua, ei lisäysjärjestystä
- Oletusta, että `pop()` olisi O(1), kun suurin osa alkioista on poistettu muulla tavoin

## Versiohuomiot

- **Python 3.14+**: Joukon hakeminen alkiona (`{1, 2} in s`, `s.discard({1, 2})`) hajauttaa sen
  paikallaan tilassa O(1); aiemmat versiot kopioivat sen väliaikaiseksi frozenset-olioksi, tilaa O(k)

## Liittyvät tyypit

- **[Frozenset](frozenset.md)** - Muuttumaton, hajautettava joukko samoin hakukustannuksin
- **[set()](set_func.md)** - Joukon rakentaminen iteroitavasta
- **[Dict](dict.md)** - Sama hajautustaulu arvoineen; `dict.fromkeys()` säilyttää lisäysjärjestyksen

## Lisälukemista

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin joukkototeutukseen
