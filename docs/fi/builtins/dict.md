---
source_sha: 1ce9ec38802382a00f950d40de21191bc041a2d77c11e823222eb83a57ab0475
translated: machine
---

# Sanakirjaoperaatioiden vaativuus

Tyyppi `dict` on muuttuva kuvaus, joka tallentaa avain-arvo-pareja. CPythonissa se on toteutettu hajautustauluna.

## Vaativuustaulukko

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Suora lukumäärä |
| `access[key]` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku; pahin tapaus törmäysten kanssa |
| `set[key] = value` | O(1) tasoitettu | O(1) | Hajautuslisäys; voi laukaista kokomuutoksen |
| `del[key]` | O(1) keskim., O(n) pahin | O(1) | Hajautuspoisto |
| `key in dict` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku |
| `get(key)` | O(1) keskim., O(n) pahin | O(1) | Hajautushaku |
| `pop(key)` | O(1) keskim., O(n) pahin | O(1) | Hajautuspoisto |
| `clear()` | O(n) | O(1) | Kaikki tietueet on vapautettava |
| `keys()` | O(1) | O(1) | Näkymäolio (iterointi O(n)) |
| `values()` | O(1) | O(1) | Näkymäolio (iterointi O(n)) |
| `items()` | O(1) | O(1) | Näkymäolio (iterointi O(n)) |
| `copy()` | O(n) | O(n) | Pinnallinen kopio kaikista pareista |
| `update(other)` | O(k) | O(1) | k = len(other), tasoitettu; muokkaa paikallaan |
| `setdefault(key, val)` | O(1) keskim. | O(1) | Hajautushaku + lisäys |
| `fromkeys(keys)` | O(k) | O(k) | k = len(keys) |
| `popitem()` | O(1) | O(1) | Poistaa viimeksi lisätyn parin (LIFO versiosta 3.7 alkaen) |

*Huomio: keskimääräinen O(1) edellyttää hyvää tiivisteiden jakaumaa. Pahin tapaus O(n) syntyy patologisista tiivistetörmäyksistä, mikä on harvinaista Pythonin satunnaistetun hajautuksen ansiosta.*

## Toteutuksen yksityiskohdat

### Hajautustaulun rakenne

CPython käyttää hajautustaulua, jossa on:

- **Hajautusfunktio**: SipHash13 tyypeille `str`/`bytes` (oletus Python 3.11:stä alkaen); muut tyypit käyttävät tyyppikohtaista hajautusta
- **Törmäysten käsittely**: Avoin osoitus luotauksella
- **Kasvukerroin**: noin 2-4x, kun täyttöaste ylittyy
- **Python 3.6 (CPython)**: Tiivis sanakirja säilyttää lisäysjärjestyksen toteutuksen yksityiskohtana

### Tiivistetörmäysten vaikutus

```python
# Best case: perfect hashing (O(1))
d = {i: i for i in range(1000)}
value = d[500]  # O(1)

# Worst case: hash collisions (degraded, but very rare)
# CPython mitigates this with randomized hashing
```

### Lisäysjärjestyksen takuu

```python
# Python 3.7+ guarantees insertion order (language guarantee)
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
# Iteration order: a, b, c (guaranteed)
```

## Versiohuomiot

| Versio | Muutos |
|---------|--------|
| Python 3.6 | CPythonin tiivis sanakirja säilyttää lisäysjärjestyksen (toteutuksen yksityiskohta) |
| Python 3.7+ | Kielimäärittely takaa lisäysjärjestyksen |
| Python 3.9+ | Sanakirjojen yhdistämis- ja päivitysoperaattorit (`\|`, `\|=`) |
| Python 3.10+ | Hahmontunnistus sanakirjoilla |
| Python 3.11+ | 23 % pienempi, kun kaikki avaimet ovat Unicode-merkkijonoja |

## Toteutusten vertailu

### CPython
Standardi hajautustaulutoteutus, erittäin optimoitu.

### PyPy
Samankaltainen vaativuus, JIT-käännös voi tuoda lisäoptimointia.

### Jython
Käyttää taustalla Javan HashMap-rakennetta, samat O(1)-ominaisuudet.

### IronPython
Samankaltainen hajautustaulutoteutus kuin CPythonissa.

## Parhaat käytännöt

✅ **Tee näin**:

- Käytä sanakirjaa avain-arvo-hakuihin
- Hyödynnä sanakirjakoosteita: `{k: v for k, v in items}`
- Käytä `setdefault()`-metodia ehdolliseen lisäykseen

❌ **Vältä**:

- Älä luota lisäysjärjestykseen Python-versioissa < 3.7, jos tarvitset siirrettävää käyttäytymistä
- Hajautuskelvottomia tyyppejä avaimina (listat, sanakirjat, joukot)
- Erittäin suuria sanakirjoja huonoilla hajautusfunktioilla

## Hajautusfunktioon liittyviä huomioita

```python
# Hashable types work as keys
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key'
}

# Unhashable types will fail
# d[[1, 2]] = 'fails'  # TypeError
# d[{1, 2}] = 'fails'  # TypeError
```

## Liittyvät tyypit

- **[Joukko](set.md)** - Järjestämättömät uniikit alkiot
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - Automaattiset oletusarvot
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - Eksplisiittinen järjestys (ennen 3.6)
- **[ChainMap](../stdlib/collections.md#chainmap)** - Useita sanakirjanäkymiä

## Lisälukemista

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Syväluotaus CPythonin sanakirjatoteutukseen
