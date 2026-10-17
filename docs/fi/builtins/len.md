---
source_sha: 0aa31d8e74b3cf287660536daef3aa50acfed3e07167aeb3888371da0ed5c807
translated: machine
---

# len()-funktion vaativuus

`len(obj)` palauttaa säiliön alkioiden lukumäärän. Jokainen sisäänrakennettu säiliö pitää
alkiomääränsä tallessa oliossa, joten `len()` lukee sen laskematta, oli säiliö kuinka suuri
tahansa. Muille olioille `len()` kutsuu olion luokan määrittelemää `__len__`-metodia ja maksaa
sen, mitä metodi maksaa.

Sisäänrakennettujen tyyppien rivit eivät riipu säiliön koosta. `f` on aika, jonka luokan itse
määrittelemä metodi - `__len__`, `__bool__` tai `__length_hint__` - vie O(1)-kutsun päälle;
kaiken, mitä metodi varaa muistia, se varaa O(1)-tilan päälle. `ChainMap`-oliolle `m` on sen
sanakirjojen määrä, `t` niiden avainten määrä laskettuna yhteen kaikista sanakirjoista
kaksoiskappaleet mukaan lukien, ja `u` niistä erillisten avainten määrä.

## Vaativuusviite

### Sisäänrakennetut tyypit

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(lst)`, `len(tpl)` | O(1) | O(1) | `list` ja `tuple` |
| `len(s)` | O(1) | O(1) | `str`: laskee merkit (koodipisteet), ei koodattuja tavuja |
| `len(b)`, `len(ba)` | O(1) | O(1) | `bytes` ja `bytearray`: laskee tavut |
| `len(mv)` | O(1) | O(1) | `memoryview`, jolla on vähintään yksi ulottuvuus: ensimmäisen ulottuvuuden pituus, ei alkioiden kokonaismäärä |
| `len(d)`, `len(d.keys())`, `len(d.values())`, `len(d.items())` | O(1) | O(1) | `dict` ja sen näkymät |
| `len(fd)` | O(1) | O(1) | `frozendict`, Python 3.15+ |
| `len(st)`, `len(fs)` | O(1) | O(1) | `set` ja `frozenset` |
| `len(r)` | O(1) | O(1) | `range`: pituus lasketaan kerran, kun range luodaan; nostaa `OverflowError`-poikkeuksen, kun pituus ylittää `sys.maxsize`:n |

### Standardikirjaston säiliöt

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(dq)` | O(1) | O(1) | `collections.deque` |
| `len(dd)`, `len(od)`, `len(c)` | O(1) | O(1) | `defaultdict`, `OrderedDict` ja `Counter` ovat `dict`-tyypin aliluokkia |
| `len(cm)` | O(m + t) | O(m + u) | `collections.ChainMap` rakentaa jokaisella kutsulla joukon kaikkien sanakirjojensa kaikista avaimista |

### Muut oliot

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(obj)` | O(f) | O(1) | Kutsuu `type(obj).__len__`; olion omaa `__len__`-nimistä attribuuttia ei huomioida. Tuloksen on oltava kokonaisluku (`int` tai olio, jolla on `__index__`) väliltä 0 - `sys.maxsize` |
| `len(gen)`, `len(iterator)` | O(1) | O(1) | Generaattoreilla ja iteraattoreilla, joilla ei ole `__len__`-metodia, ei ole pituutta: nostaa `TypeError`-poikkeuksen |
| `bool(obj)`, `if obj:` | O(1) tai O(f) | O(1) | O(1) sisäänrakennetulle säiliölle; luokka, jolla on `__len__` mutta ei `__bool__`-metodia, on tosi, kun `__len__` palauttaa nollasta poikkeavan arvon |
| `operator.length_hint(obj, default=0)` | O(1) tai O(f) | O(1) | `len(obj)`, jos oliolla on pituus, muuten `obj.__length_hint__()`, muuten `default`; ei koskaan iteroi oliota `obj` itse |

## Sisäänrakennetut säiliöt

`len()` maksaa saman kolmen alkion säiliölle kuin miljoonan alkion säiliölle. Merkkijonosta
(`str`) se laskee merkit, joten tulos voi poiketa koodattujen tavujen (`bytes`) määrästä.

```python
items = list(range(1_000_000))
assert len(items) == 1_000_000  # O(1)
assert len((1, 2, 3)) == 3  # O(1)

d = {"a": 1, "b": 2}
assert len(d) == len(d.keys()) == len(d.items()) == 2  # O(1)
assert len({1, 2, 2, 3}) == 3  # O(1)

s = "café"
assert len(s) == 4  # O(1) - characters
assert len(s.encode("utf-8")) == 5  # O(1) - bytes, after an O(n) encode

grid = memoryview(bytes(12)).cast("B", shape=[3, 4])
assert len(grid) == 3  # O(1) - the first dimension
assert grid.nbytes == 12
```

## Range-oliot

Range laskee pituutensa arvoista `start`, `stop` ja `step` luontihetkellä, ja `len()` palauttaa
tallennetun arvon. Range voi olla pidempi kuin `sys.maxsize`, mutta `len()`:n on palautettava
indeksin kokoinen kokonaisluku, joten se nostaa tällaiselle rangelle `OverflowError`-poikkeuksen.
Indeksointi ja `in` toimivat silti.

```python
import sys

r = range(0, 10**9, 3)
assert len(r) == 333_333_334  # O(1)

huge = range(10**20)
try:
    len(huge)
except OverflowError as error:
    assert "too large" in str(error)
else:
    raise AssertionError("expected OverflowError")

assert 10**20 > sys.maxsize
assert huge[-1] == 10**20 - 1  # O(1)
assert 10**19 in huge  # O(1)
```

## Luokat, joilla on __len__

`len(obj)` kutsuu olion luokan `__len__`-metodia, joten metodi määrää kustannuksen. Jos metodi
pitää lukua yllä tai delegoi sisäänrakennetulle säiliölle, se on O(1); jos se laskee iteroimalla,
se on O(n) jokaisella kutsulla. `len()` tarkistaa tuloksen: negatiivinen arvo nostaa
`ValueError`-poikkeuksen, ja arvo, joka ei ole kokonaisluku, nostaa `TypeError`-poikkeuksen.

```python
class Stored:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return len(self.items)  # O(1) - delegates to the list


class Counted:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return sum(1 for _ in self.items)  # O(n) - walks every item on each call


assert len(Stored(range(5))) == len(Counted(range(5))) == 5


class Negative:
    def __len__(self):
        return -1


try:
    len(Negative())
except ValueError as error:
    assert ">= 0" in str(error)
else:
    raise AssertionError("expected ValueError")
```

Totuusarvon testaus käyttää myös `__len__`-metodia, kun luokka ei määrittele `__bool__`-metodia,
joten `if obj:` maksaa saman kuin `len(obj)`.

```python
class Box:
    calls = 0

    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        Box.calls += 1
        return len(self.items)


assert not Box([])  # calls __len__
assert Box([1])
assert Box.calls == 2
```

## Iteraattorit ja generaattorit

Generaattori, kuten mikä tahansa iteraattori ilman `__len__`-metodia, ei tiedä, montako alkiota
se tuottaa, joten `len()` nostaa `TypeError`-poikkeuksen. Alkioiden laskeminen kuluttaa ne, ajassa
O(n). `operator.length_hint()` kysyy iteroimatta: se antaa tarkan jäljellä olevien alkioiden määrän sisäänrakennetun säiliön
iteraattorille ja generaattorille arvon `default`.

```python
import operator

gen = (x * x for x in range(5))
try:
    len(gen)
except TypeError as error:
    assert "has no len()" in str(error)
else:
    raise AssertionError("expected TypeError")

assert operator.length_hint(gen, -1) == -1  # O(1) - a generator gives no hint
assert sum(1 for _ in gen) == 5  # O(n) - and the generator is now exhausted
assert list(gen) == []

it = iter([10, 20, 30])
next(it)
assert operator.length_hint(it) == 2  # O(1)
assert list(it) == [20, 30]  # nothing was consumed
```

## ChainMap

`ChainMap` ei tallenna alkiomäärää. Jokainen `len()`-kutsu rakentaa joukon kaikkien sen
sanakirjojen avaimista, joten se maksaa jokaisen sanakirjan ja jokaisen niiden avaimen verran, ja
useassa sanakirjassa oleva avain lasketaan kerran.

```python
from collections import ChainMap

defaults = {"color": "red", "size": 10}
overrides = {"color": "blue"}
settings = ChainMap(overrides, defaults)

assert len(settings) == 2  # O(m + t) - "color" is in both maps
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Kutsu `len()`-funktiota vapaasti sisäänrakennetuille säiliöille, myös silmukan ehdossa; se on O(1)
- Käytä tyhjyyden tarkistukseen `if container:`; se on O(1) sisäänrakennetuille säiliöille
- Pidä omassa säiliössäsi lukua yllä tai delegoi sisäänrakennetulle säiliölle, jotta `__len__` on O(1)
- Käytä `operator.length_hint()`-funktiota puskurin mitoittamiseen sisäänrakennetun säiliön
  iteraattorista kuluttamatta sitä

❌ **Vältä**:

- `len(list(iterator))` pelkkään laskemiseen: se rakentaa O(n)-kokoisen listan;
  `sum(1 for _ in iterator)` laskee O(1)-tilassa, mutta kummassakin tapauksessa iteraattori kuluu
- Iteroivaa `__len__`-metodia; `if obj:` kutsuu sitä myös, kun luokalla ei ole `__bool__`-metodia
- `len()`-kutsua `ChainMap`-oliolle silmukassa: jokainen kutsu käy läpi jokaisen sanakirjan

## Versiohuomiot

- **Python 3.15+**: `len()` on O(1) `frozendict`-oliolle

## Liittyvät funktiot

- **[bool()](bool_func.md)** - Totuusarvon testaus turvautuu `__len__`-metodiin
- **[iter()](iter.md)** - Generaattoreilla ja useimmilla iteraattoreilla ei ole pituutta
- **[range](range.md)** - Range laskee pituutensa luontihetkellä
- **[sum()](sum.md)** - Iteraattorin alkioiden laskeminen
- **[collections](../stdlib/collections.md)** - `deque`, `Counter` ja `ChainMap`
- **[operator](../stdlib/operator.md)** - `length_hint()` iteraattoreille
