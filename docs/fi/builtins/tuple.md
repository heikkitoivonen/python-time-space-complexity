---
source_sha: 0f682082c1e815cf6cb74518bbbdc670c90d687d42c87d1afd5e6f989b5ac7c8
translated: machine
---

# Monikko-operaatioiden vaativuus

Tyyppi `tuple` on muuttumaton, järjestetty jono. CPython tallentaa sen kiinteän kokoisena
viittausten taulukkona, joten indeksointi on suoraa eikä mitään tarvitse koskaan lisätä, poistaa
tai muuttaa kooltaan. Koska monikko ei voi muuttua, täsmälleen `tuple`-tyyppisen monikon kopiointi
palauttaa monikon itsensä.

`n` on monikon pituus, `k` on numeerisen argumentin arvo (indeksi tai toistokerroin), `i:j` ovat
viipaleen rajat ja `len(t1)`, `len(t2)` ovat operandien pituudet. Askeleellinen viipale valitsee
`m` alkiota. Indeksit lasketaan sen jälkeen, kun negatiiviset arvot on normalisoitu. Yhden alkion
vertailu tai hajautus lasketaan O(1):ksi.

## Vaativuustaulukko

### tuple

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | Pituus on tallennettu monikkoon, sitä ei lasketa |
| `t[k]` | O(1) | O(1) | Suora indeksointi |
| `t[i:j]` (viipalointi) | O(j-i) | O(j-i) | Askeleen kanssa O(m); täsmälleen `tuple`-tyyppisen monikon `t[:]` palauttaa `t`:n itsensä |
| `t.index(x)` | O(n) | O(1) | Lineaarinen haku; `t.index(x, i, j)` hakee vain alueelta `t[i:j]`, O(j-i) |
| `t.count(x)` | O(n) | O(1) | Lineaarinen läpikäynti |
| `x in t` (jäsenyys) | O(n) | O(1) | Lineaarinen haku |
| `tuple(t)`, `copy.copy(t)` | O(1) | O(1) | Palauttavat `t`:n itsensä, kun `t` on täsmälleen `tuple`-tyyppinen; monikoilla ei ole `copy()`-metodia |
| `tuple(iterable)` | O(n) | O(n) | n = iteroitavan tuottamat alkiot; katso [tuple()](tuple_func.md) |
| `t1 + t2` (yhdistäminen) | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k` (toisto) | O(nk) | O(nk) | k ≤ 0 antaa tyhjän monikon |
| `t1 == t2` | O(min(len(t1), len(t2))) | O(1) | Vertaa alkioita, vaikka pituudet eroavat; pysähtyy ensimmäiseen erisuureen pariin |
| `t1 < t2`, `<=`, `>`, `>=` | O(min(len(t1), len(t2))) | O(1) | Pysähtyy ensimmäiseen erisuureen pariin |
| `for x in t` (iterointi) | O(n) | O(1) | O(1) askelta kohden |
| `reversed(t)` | O(1) | O(1) | Laiska iteraattori; sen läpikäynti on O(n) |
| `min(t)`, `max(t)` | O(n) | O(1) | n-1 vertailua |
| `hash(t)` | O(n) ensimmäisellä kerralla; sen jälkeen O(1) versiosta 3.14 alkaen | O(1) | 3.11-3.13 laskevat sen joka kutsulla uudelleen; hajautuskelvoton alkio nostaa `TypeError`-poikkeuksen eikä mitään tallenneta |

## Kopiointi palauttaa saman monikon

Täsmälleen `tuple`-tyyppisen monikon kopio ei voisi koskaan erota alkuperäisestä, joten
`tuple(t)`, `copy.copy(t)` ja `t[:]` palauttavat `t`:n itsensä ajassa O(1). Aliluokan ilmentymä
kopioidaan ajassa O(n).

```python
import copy

t = tuple(range(1_000))
assert tuple(t) is t  # O(1)
assert copy.copy(t) is t  # O(1)
assert t[:] is t  # O(1)


class Pair(tuple):
    pass


p = Pair((1, 2))
assert tuple(p) is not p and type(tuple(p)) is tuple  # O(n): a subclass is copied
```

## Hajautus

`hash(t)` yhdistää jokaisen alkion tiivisteen, joten ensimmäinen kutsu on O(n). Versiosta 3.14
alkaen tulos säilytetään monikossa ja myöhemmät kutsut ovat O(1); versioissa 3.11-3.13 jokainen
kutsu käy alkiot uudelleen läpi. Välimuisti kuuluu oliolle: erikseen rakennettu yhtä suuri monikko
maksaa oman ensimmäisen hajautuksensa.

```python
import sys

calls = 0


class Key:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Key) and self.value == other.value

    def __hash__(self):
        global calls
        calls += 1
        return hash(self.value)


t = tuple(Key(i) for i in range(100))
hash(t)  # O(n): hashes every element
assert calls == 100

calls = 0
hash(t)  # O(1) on 3.14+, O(n) before
assert calls == (0 if sys.version_info >= (3, 14) else 100)

try:
    hash((1, []))
except TypeError as exc:
    assert "unhashable type: 'list'" in str(exc)
else:
    raise AssertionError("expected TypeError")
```

## Monikoiden vertailu

`==` ei tarkista pituuksia ensin. Se käy läpi yhteisen alkuosan, pysähtyy ensimmäiseen erisuureen
pariin ja katsoo pituuksia vasta, kun lyhyempi monikko loppuu kaikkien parien ollessa yhtä suuria.
Toisin kuin [listalla](list.md), eripituisetkin monikot vertaavat yhteisen alkuosansa.

```python
compared = 0


class Item:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        global compared
        compared += 1
        return self.value == other.value

    __hash__ = None


short = tuple(Item(i) for i in range(999))
long = tuple(Item(i) for i in range(1_000))
assert short != long  # O(min(len(t1), len(t2))): the common prefix is compared
assert compared == 999

compared = 0
assert list(short) != list(long)  # a list answers from the lengths alone
assert compared == 0
```

## Monikon rakentaminen

`t += (x,)` rakentaa uuden monikon, joten silmukassa se kopioi kaiken siihen mennessä kerätyn joka
askeleella: yhteensä O(n²). Kerää alkiot listaan ja muunna kerran.

```python
slow = ()
for i in range(1_000):
    slow += (i,)  # O(len(slow)): copies the tuple each time

items = []
for i in range(1_000):
    items.append(i)  # O(1) amortized
fast = tuple(items)  # O(n), once

assert slow == fast == tuple(range(1_000))
```

## Suorituskyvyn parhaat käytännöt

✅ **Tee näin**:

- Kopioi vapaasti: täsmälleen `tuple`-tyyppisen monikon `tuple(t)` ja `t[:]` ovat O(1)
- Käytä monikkoa sanakirjan avaimena tai joukon alkiona, kun sen alkiot ovat hajautettavia;
  versiosta 3.14 alkaen sen tiiviste lasketaan kerran monikkoa kohden
- Kerää alkiot listaan ja kutsu `tuple()` kerran: yhteensä O(n)

❌ **Vältä**:

- `t += (x,)` silmukassa: jokainen askel kopioi monikon, yhteensä O(n²)
- `x in t` toisen silmukan sisällä: O(n) testiä kohden - rakenna kerran [joukko](set.md), niin
  haut ovat keskimäärin O(1)

## Versiohuomiot

- **Python 3.14+**: `hash(t)` säilyttää tuloksensa monikossa, joten toistuvat kutsut ovat O(1)

## Liittyvät tyypit

- **[Lista](list.md)** - Muuttuva vaihtoehto
- **[tuple()](tuple_func.md)** - Monikon rakentaminen iteroitavasta
- **[namedtuple](../stdlib/namedtuple.md)** - Monikot nimetyillä kentillä
- **[Dataclass](../stdlib/dataclasses.md)** - Muuttuvat tietueet nimetyillä kentillä

## Lisälukemista

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin monikkototeutukseen
