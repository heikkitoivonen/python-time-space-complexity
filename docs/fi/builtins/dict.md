---
source_sha: a15a59a2e896d04888dafc57e64dd677615bec4310ef7fc6de1e8eb9c35a355e
translated: machine
---

# Sanakirjaoperaatioiden vaativuus

Tyyppi `dict` on muuttuva kuvaus, joka tallentaa avain-arvo-parit lisäysjärjestyksessä. CPythonissa
se on hajautustaulu, joten haut, lisäykset ja poistot eivät riipu sanakirjan koosta, ja jokaiseen
alkioon koskevat operaatiot - kopiointi, iterointi, vertailu - ovat lineaarisia.

`n` on sanakirjan alkioiden määrä ja `m` toisen operandin alkioiden määrä: `update()`- tai
`fromkeys()`-metodille annetun kuvauksen tai iteroitavan, tai `|`-operaattorin tai näkymän
joukko-operaation oikeanpuoleisen operandin. Avainten hajautus ja vertailu oletetaan
O(1)-operaatioiksi, samoin kahden arvon vertailu. O(1)-haut ovat keskimääräisiä tapauksia: jos
jokainen avain saa saman tiivisteen, kukin niistä vie sen sijaan O(n).

## Vaativuustaulukko

### dict

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(d)` | O(1) | O(1) | Lukumäärä on tallennettu |
| `d[key]`, `d.get(key, default=None)` | O(1) keskim., O(n) pahin | O(1) | `d[key]` nostaa `KeyError`-poikkeuksen puuttuvalle avaimelle |
| `key in d` | O(1) keskim., O(n) pahin | O(1) | |
| `d[key] = value` | O(1) tasoitettu | O(1) | Kutsu, joka kasvattaa taulua, rakentaa sen uudelleen ajassa O(n) |
| `del d[key]`, `d.pop(key[, default])` | O(1) keskim., O(n) pahin | O(1) | Puuttuva avain nostaa `KeyError`-poikkeuksen, ellei `pop()`-metodille anneta oletusarvoa; taulua ei pienennetä |
| `d.setdefault(key, default=None)` | O(1) tasoitettu | O(1) | Yksi haku sekä lisäys, kun avain puuttuu |
| `d.popitem()` | O(1) tasoitettu | O(1) | Poistaa viimeksi lisätyn parin; nostaa `KeyError`-poikkeuksen, kun sanakirja on tyhjä |
| `d.clear()` | O(n) | O(1) | Vapauttaa jokaisen avaimen ja arvon |
| `d.copy()` | O(n) | O(n) | Pinnallinen: avaimet ja arvot jaetaan, niitä ei kopioida |
| `dict.fromkeys(iterable, value=None)` | O(m) | O(m) | Jokainen avain osoittaa samaan `value`-olioon |
| `d.update(other)`, `d \|= other` | O(m) tasoitettu | O(m) | Paikallaan, lisäksi `other`-olion iteroinnin kustannus: kuvaus tai parien iteroitava |
| `d \| other` | O(n + m) | O(n + m) | Uusi sanakirja: kopio `d`:stä päivitettynä `other`-oliosta. `dict` käsittelee vain `dict`- tai `frozendict`-tyyppisen `other`-olion; muut jätetään `other.__ror__`-metodille |
| `d`:n iterointi, `reversed(d)` | O(n) | O(1) | Lisäysjärjestyksessä tai sen käänteisessä järjestyksessä |
| `d == other`, `d != other` | O(n) | O(1) | Järjestyksellä ei ole väliä; O(1), kun pituudet eroavat |

### Näkymät

`d.keys()`, `d.values()` ja `d.items()` ovat näkymiä: ne viittaavat `d`:hen ja näkevät jokaisen
myöhemmän muutoksen siihen kopioimatta mitään.

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `d.keys()`, `d.values()`, `d.items()` | O(1) | O(1) | |
| `len(view)`, `view.mapping` | O(1) | O(1) | `mapping` on `d`:n vain luku -välityskuvaus |
| Näkymän iterointi, `reversed(view)` | O(n) | O(1) | |
| `key in d.keys()`, `(key, value) in d.items()` | O(1) keskim., O(n) pahin | O(1) | Yksi avainhaku sekä `items()`-näkymällä arvojen vertailu |
| `value in d.values()` | O(n) | O(1) | Arvoja ei ole indeksoitu, joten tämä käy ne läpi |
| `view & other` | O(m) | O(min(n, m)) | `keys()`- ja `items()`-näkymät; aika O(min(n, m)), kun `other` on joukko tai `keys()`- tai `items()`-näkymä |
| `view \| other`, `view - other`, `view ^ other` | O(n + m) | O(n + m) | Kukin rakentaa uuden `set`-olion |
| `view.isdisjoint(other)` | O(m) | O(1) | O(min(n, m)), kun `other` on joukko tai `keys()`- tai `items()`-näkymä; pysähtyy ensimmäiseen yhteiseen alkioon |

Alkioiden poistaminen ei pienennä taulua. Kun suurin osa alkioista on poistettu, taulun läpi
käyvät operaatiot - `d`:n tai näkymän iterointi, `copy()`, `d | other`, `other.update(d)`,
`d == other` ja `dict(d)` - vievät yhä aikaa suhteessa sanakirjan aiempaan kokoon, kunnes
myöhemmät lisäykset laukaisevat koon muuttamisen. `len()` ja haut eivät muutu.

## Haut ja törmäykset

Haku hajauttaa avaimen ja vertaa sitä vain niihin tallennettuihin avaimiin, joilla on sama
tiiviste. Hyvin jakautuvalla tiivisteellä vertailuja on enintään yksi. Kun monella avaimella on sama
tiiviste, haku vertaa vuorollaan jokaiseen niistä, joten se heikkenee O(n):ään.

```python
class Key:
    comparisons = 0

    def __init__(self, name, hash_value):
        self.name = name
        self.hash_value = hash_value

    def __hash__(self):
        return self.hash_value

    def __eq__(self, other):
        Key.comparisons += 1
        return self.name == other.name

spread = {Key(i, i): i for i in range(100)}     # O(n)
Key.comparisons = 0
assert spread[Key(99, 99)] == 99                # O(1)
assert Key.comparisons == 1                     # only the key with the same hash

colliding = {Key(i, 1): i for i in range(100)}  # O(n²) - each insertion compares
Key.comparisons = 0
assert colliding[Key(99, 1)] == 99              # O(n) - compares every key before it
assert Key.comparisons == 100
```

## Poistaminen ei pienennä taulua

`del` ja `pop()` jättävät taulun suurimpaan kokoonsa, joten sen läpikäynti käy yhä jokaisen
paikan, joka sillä on ollut. `copy()` sanakirjasta, joka on menettänyt suurimman osan
alkioistaan, rakentaa tiiviin sanakirjan, mikä tekee myöhemmistä läpikäynneistä taas halpoja.

```python
import sys

d = {i: i for i in range(100_000)}
full = sys.getsizeof(d)
for i in range(10, 100_000):
    del d[i]                       # O(1) each

assert len(d) == 10                # O(1)
assert sys.getsizeof(d) == full    # still sized for 100,000 items
keys = list(d)                     # O(100,000): walks the old table

d = d.copy()                       # O(100,000) once
assert sys.getsizeof(d) < full     # sized for 10 items
assert list(d) == keys             # O(10)
```

### Vanhimman alkion poistaminen

Sama pätee taulun alkupäähän. `next(iter(d))` ohittaa jokaisen paikan, jonka aiemmat poistot
tyhjensivät, joten vanhimman avaimen poistaminen silmukassa maksaa O(n) kutsua kohden ja O(n²)
koko sanakirjalle. `collections.OrderedDict.popitem(last=False)` poistaa vanhimman alkion ajassa
O(1).

```python
from collections import OrderedDict

d = dict.fromkeys(range(5))
oldest = next(iter(d))      # O(1) here; O(deleted so far) in a loop
del d[oldest]
assert list(d) == [1, 2, 3, 4]

od = OrderedDict.fromkeys(range(5))
assert od.popitem(last=False) == (0, None)   # O(1)
assert list(od) == [1, 2, 3, 4]
```

## Näkymät

Näkymä luodaan ajassa O(1), ja se heijastaa sanakirjaa sellaisena kuin se on käyttöhetkellä.
Jäsenyys `keys()`- ja `items()`-näkymissä on hajautushaku; jäsenyys `values()`-näkymässä on
läpikäynti. `keys()`- ja `items()`-näkymien joukko-operaatiot palauttavat uuden `set`-olion.

```python
d = {'a': 1, 'b': 2}
keys = d.keys()                 # O(1) - no copy
d['c'] = 3
assert list(keys) == ['a', 'b', 'c']  # O(n) - sees the new key

assert 'b' in keys              # O(1)
assert ('b', 2) in d.items()    # O(1) - key lookup, then one value comparison
assert 3 in d.values()          # O(n) - a scan

assert keys & {'a', 'z'} == {'a'}           # O(min(n, m)) with a set
assert keys - ['a'] == {'b', 'c'}           # O(n + m)
assert keys.isdisjoint({'x', 'y'})          # O(min(n, m)) with a set
assert keys.mapping['a'] == 1               # O(1) - a read-only proxy
```

## Yhdistäminen: | ja update()

`d | other` kopioi `d`:n ja lisää sitten jokaisen `other`-olion alkion, joten se on O(n + m)
riippumatta siitä, kumpi puoli on suurempi. `d |= other` ja `d.update(other)` lisäävät suoraan
`d`:hen ja maksavat vain O(m). `update()` hyväksyy myös parien iteroitavan ja avainsana-argumentit.

```python
defaults = {'color': 'red', 'size': 10}
overrides = {'size': 12}

merged = defaults | overrides       # O(n + m) - a new dict
assert merged == {'color': 'red', 'size': 12}
assert defaults['size'] == 10

config = defaults
config |= overrides                 # O(m) - in place
assert config is defaults and defaults['size'] == 12

config.update([('debug', True)], verbose=False)  # O(m)
assert list(config) == ['color', 'size', 'debug', 'verbose']
```

## Lisäysjärjestys

Iterointi noudattaa lisäysjärjestystä, ja `reversed()` käy sen läpi takaperin. Olemassa olevaan
avaimeen sijoittaminen säilyttää sen paikan. `popitem()` poistaa viimeksi lisätyn parin.

```python
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
d['a'] = 10                         # O(1) - keeps its position

assert list(d) == ['a', 'b', 'c']   # O(n)
assert list(reversed(d)) == ['c', 'b', 'a']  # O(n)
assert d.popitem() == ('c', 3)      # O(1) - last in, first out
assert d == {'b': 2, 'a': 10}       # O(n) - order is ignored
```

## Avainten on oltava hajautettavia

Jokainen haku ja jokainen `d[key] = value` hajauttaa avaimen. Listat, sanakirjat ja joukot ovat
muuttuvia eivätkä hajautettavia, joten ne eivät kelpaa avaimiksi; samoista hajautettavista
alkioista koostuva monikko tai `frozenset` kelpaa.

```python
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key',
}
assert d[frozenset([2, 1])] == 'frozen_key'   # O(1) after hashing the key

for key in ([1, 2], {1, 2}, {'a': 1}):
    try:
        d[key] = 'fails'
    except TypeError as error:
        assert 'unhashable' in str(error)
    else:
        raise AssertionError(f'{type(key).__name__} must not be usable as a key')
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Käytä sanakirjaa avaimella hakemiseen: O(1) listan vaatiman O(n)-läpikäynnin sijaan
- Käytä `get()`- tai `setdefault()`-metodia puuttuvan avaimen käsittelyyn yhdellä haulla kahden sijaan
- Käytä `d |= other` tai `update()` lisätäksesi sanakirjaan ajassa O(m); `d | other` kopioi ensin `d`:n
- Kopioi sanakirja, joka on menettänyt suurimman osan alkioistaan, jotta myöhemmät läpikäynnit maksavat sen nykyisen koon

❌ **Vältä**:

- `value in d.values()` silmukassa - jokainen testi on O(n); pidä käänteistä sanakirjaa tai arvojen joukkoa
- Vanhimman avaimen poistamista `del d[next(iter(d))]` silmukassa - yhteensä O(n²); käytä
  `OrderedDict.popitem(last=False)`
- Sanakirjan kokoamista toistuvalla `d = d | other` - jokainen askel kopioi kaiken siihen asti kertyneen
- Avaimia, joilla on huono `__hash__` - kun moni törmää, jokainen haku heikkenee O(n):ään

## Versiohuomiot

- **Python 3.7+**: Lisäysjärjestys on osa kieltä; CPython 3.6 säilytti sen jo
- **Python 3.9+**: Yhdistämisoperaattori `|` ja päivitysoperaattori `|=`
- **Python 3.15+**: [`frozendict`](frozendict.md), muuttumaton ja hajautettava sanakirja

## Liittyvät tyypit

- **[Joukko](set.md)** - Järjestämättömät uniikit alkiot
- **[frozendict](frozendict.md)** - Muuttumaton, hajautettava sanakirja (Python 3.15+)
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - Automaattiset oletusarvot
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - O(1)-poisto kummastakin päästä ja `move_to_end()`
- **[ChainMap](../stdlib/collections.md#chainmap)** - Useita sanakirjanäkymiä

## Lisälukemista

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin sanakirjatoteutukseen
