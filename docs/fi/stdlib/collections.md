---
source_sha: 45e6ee6587007e1eab2d114700afa7e63063edb6439cf6702f07a5f279051faf
translated: machine
---

# Collections-moduulin vaativuus

Moduuli `collections` tarjoaa erikoistuneita tietorakenteita, jotka on optimoitu tiettyihin käyttötarkoituksiin.

## deque

Katso operaatiot, vaativuudet ja esimerkit sivulta [deque](deque.md).

## DefaultDict

Katso operaatiot, vaativuudet ja esimerkit sivulta [defaultdict](defaultdict.md).

## Counter

Katso operaatiot, vaativuudet ja esimerkit sivulta [Counter](counter.md).

## NamedTuple

Katso operaatiot, vaativuudet ja esimerkit sivulta [namedtuple](namedtuple.md).

## OrderedDict

Katso operaatiot, vaativuudet ja esimerkit sivulta [OrderedDict](ordereddict.md).

## ChainMap

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `access[key]` | O(n) | O(1) | n = kuvausten lukumäärä; hakee kunnes löytyy |
| `set[key]` | O(1) avg | O(1) | Asettaa ensimmäiseen kuvaukseen; pahimmillaan O(m), missä m = ensimmäisen kuvauksen koko |
| `del[key]` | O(1) avg | O(1) | Poistaa ensimmäisestä kuvauksesta; pahimmillaan O(m), missä m = ensimmäisen kuvauksen koko |
| `len()` | O(N) | O(N) | N = avainten kokonaismäärä kaikissa kuvauksissa; muodostaa sisäisesti joukkojen yhdisteen |
| `in` | O(n) | O(1) | Tarkistaa kaikki kuvaukset |

### Käyttötapaukset

```python
from collections import ChainMap

# Layer multiple dicts
defaults = {'timeout': 30, 'retries': 3}
user_config = {'timeout': 60}

config = ChainMap(user_config, defaults)
print(config['timeout'])  # 60 (from user_config)
print(config['retries'])  # 3 (from defaults)

# View layered configuration without merging
```

## UserDict

`UserDict` kietoo tavallisen sanakirjan luokkaan, jota käyttäjä voi mukauttaa.

### Aikavaativuus

Sama kuin `dict` useimmissa operaatioissa:

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| `d[key]` | O(1) avg | O(1) | Pahimmillaan O(n) tiivistetörmäysten vuoksi |
| `d[key] = value` | O(1) avg | O(1) | Pahimmillaan O(n) |
| `del d[key]` | O(1) avg | O(1) | Pahimmillaan O(n) |
| Iterointi | O(n) | O(1) | n = alkioiden lukumäärä |

## UserList

`UserList` kietoo tavallisen listan luokkaan, jota käyttäjä voi mukauttaa.

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| Indeksointi | O(1) | O(1) | Haku indeksillä |
| Lisäys loppuun | O(1) tasoitettu | O(1) | Pahimmillaan O(n) koon muuttuessa |
| Lisäys/poisto | O(n) | O(1) | Siirtää alkioita |
| Iterointi | O(n) | O(1) | n = listan pituus |

## UserString

`UserString` kietoo tavallisen merkkijonon luokkaan, jota käyttäjä voi mukauttaa.

### Aikavaativuus

| Operaatio | Aika | Tila | Huomiot |
|-----------|------|-------|-------|
| Indeksointi | O(1) | O(1) | Haku indeksillä |
| Yhdistäminen | O(n) | O(n) | n = kokonaispituus |
| Viipalointi | O(k) | O(k) | k = viipaleen pituus |
| Iterointi | O(n) | O(1) | n = pituus |

## Liittyvä dokumentaatio

- [Sisäänrakennettu dict](../builtins/dict.md)
- [Sisäänrakennettu tuple](../builtins/tuple.md)
- [Heapq-moduuli](heapq.md)
